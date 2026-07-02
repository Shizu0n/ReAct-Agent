from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from agent.graph import MEMORY_NAMESPACE_PREFIX, TOOLS, build_graph
from agent.llms import UsageTracker, configured_model_info, responder_provider
from agent.redaction import configure_secure_logging
from agent.state import MaxIterationsError
from agent.suggestions import generate_suggestions

# Load backend/.env before configuring redaction (so secret values are registered
# for scrubbing) and before the lifespan opens the DB pool. On Vercel the env vars
# are supplied by the platform and no .env exists, so this is a harmless no-op there.
load_dotenv(Path(__file__).resolve().parent / ".env")

configure_secure_logging()
logger = logging.getLogger("react_agent.api")


class ChatMessageRequest(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class QueryRequest(BaseModel):
    query: str
    stream: bool = False
    history: list[ChatMessageRequest] = Field(default_factory=list)


class AgentResponse(BaseModel):
    result: str
    trace: list[dict[str, Any]]
    total_time: float
    run_id: str
    answer: str
    steps: list[dict[str, Any]]
    tools_used: list[str]
    latency_ms: int
    status: str
    usage: dict[str, Any] = Field(default_factory=dict)


class ModelInfoResponse(BaseModel):
    provider: str
    provider_label: str
    model: str
    label: str


class AgentConfigResponse(BaseModel):
    status: str
    active_model: ModelInfoResponse | None
    fallback_models: list[ModelInfoResponse]
    tools: list[str]


class SuggestionsRequest(BaseModel):
    history: list[ChatMessageRequest] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)


class SuggestionsResponse(BaseModel):
    suggestions: list[str]


class UploadResponse(BaseModel):
    status: str
    filename: str
    chunks_stored: int
    chunks_skipped: int
    doc_id: str


class DocumentInfo(BaseModel):
    id: str
    filename: str
    chunk_count: int
    created_at: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]


RUNS: dict[str, AgentResponse] = {}
RUN_ORDER: deque[str] = deque()
MAX_STORED_RUNS = 100
DIST_DIR = Path(__file__).resolve().parents[1] / "frontend" / "dist"
EVALS_BASELINE = Path(__file__).resolve().parent / "evals" / "baseline.json"

limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from agent.db import create_pool
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from langgraph.store.postgres import AsyncPostgresStore

        pool = await create_pool()
        await pool.open()
        checkpointer = AsyncPostgresSaver(conn=pool)
        checkpointer.supports_pipeline = False
        store = AsyncPostgresStore(conn=pool)
        store.supports_pipeline = False
        app.state.pool = pool
        app.state.checkpointer = checkpointer
        app.state.store = store
    except Exception:
        logger.warning("DB unavailable — memory features degraded (pool/checkpointer/store=None)")
        app.state.pool = None
        app.state.checkpointer = None
        app.state.store = None
    yield
    _pool = getattr(app.state, "pool", None)
    if _pool is not None:
        await _pool.close()


app = FastAPI(title="01 React Agent API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed = time.perf_counter() - started_at
        logger.exception(
            "%s %s -> 500 %.4fs", request.method, request.url.path, elapsed
        )
        raise

    elapsed = time.perf_counter() - started_at
    response.headers["X-Process-Time"] = f"{elapsed:.6f}"
    logger.info(
        "%s %s -> %s %.4fs",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


def _history_messages(history: list[ChatMessageRequest]) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for item in history[-8:]:
        content = item.content.strip()
        if not content:
            continue
        messages.append(
            HumanMessage(content=content)
            if item.role == "user"
            else AIMessage(content=content)
        )
    return messages


def _initial_state(
    query: str,
    history: list[ChatMessageRequest] | None = None,
    use_checkpointer: bool = False,
) -> dict:
    messages = (
        [HumanMessage(content=query)]
        if use_checkpointer
        else [*_history_messages(history or []), HumanMessage(content=query)]
    )
    return {
        "messages": messages,
        "intermediate_steps": [],
        "iteration_count": 0,
        "final_answer": None,
    }


_SESSION_ID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _is_valid_session_id(value: str) -> bool:
    return bool(_SESSION_ID_RE.fullmatch(value))


def _get_session_id(request: Request) -> str:
    value = request.headers.get("x-session-id", "").strip()
    return value if _is_valid_session_id(value) else str(uuid.uuid4())


def _graph_config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def _store_response(response: AgentResponse) -> None:
    if response.run_id not in RUNS and len(RUN_ORDER) >= MAX_STORED_RUNS:
        oldest_run_id = RUN_ORDER.popleft()
        RUNS.pop(oldest_run_id, None)

    if response.run_id not in RUNS:
        RUN_ORDER.append(response.run_id)
    RUNS[response.run_id] = response


def _build_response(
    run_id: str,
    started_at: float,
    final_state: dict,
    usage: dict[str, Any] | None = None,
) -> AgentResponse:
    trace = final_state.get("intermediate_steps", [])
    result = final_state.get("final_answer") or ""
    return _response_from_trace(run_id, started_at, result, trace, usage)


def _response_from_trace(
    run_id: str,
    started_at: float,
    result: str,
    trace: list[dict[str, Any]],
    usage: dict[str, Any] | None = None,
) -> AgentResponse:
    total_time = time.perf_counter() - started_at
    tools_used = list(
        dict.fromkeys(step["action"] for step in trace if step.get("action"))
    )

    return AgentResponse(
        result=result,
        trace=trace,
        total_time=total_time,
        run_id=run_id,
        answer=result,
        steps=trace,
        tools_used=tools_used,
        latency_ms=round(total_time * 1000),
        status="success",
        usage=usage or {},
    )


async def _run_agent(
    query: str,
    run_id: str,
    started_at: float,
    history: list[ChatMessageRequest] | None = None,
    session_id: str | None = None,
    checkpointer=None,
    store=None,
    pool=None,
) -> AgentResponse:
    tracker = UsageTracker()
    graph = build_graph(tracker=tracker, checkpointer=checkpointer, store=store, pool=pool)
    use_checkpointer = checkpointer is not None
    config = _graph_config(session_id or str(uuid.uuid4()))
    final_state = await graph.ainvoke(
        _initial_state(query, history, use_checkpointer=use_checkpointer),
        config=config,
    )
    response = _build_response(run_id, started_at, final_state, tracker.summary())
    _store_response(response)
    return response


def _sse_payload(
    event_type: str,
    content: str,
    step: int,
    tool: str | None = None,
    action_input: str | None = None,
    run_id: str | None = None,
    started_at: float | None = None,
    timestamp: str | None = None,
    tools_used: list[str] | None = None,
    status: str = "running",
    usage: dict[str, Any] | None = None,
) -> dict[str, str]:
    payload: dict[str, Any] = {
        "type": event_type,
        "content": content,
        "step": step,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "status": status,
    }
    if tool:
        payload["tool"] = tool
    if action_input:
        payload["action_input"] = action_input
    if run_id:
        payload["run_id"] = run_id
    if started_at is not None:
        payload["elapsed_ms"] = round((time.perf_counter() - started_at) * 1000)
    if tools_used is not None:
        payload["tools_used"] = tools_used
    if usage is not None:
        payload["usage"] = usage

    return {
        "data": json.dumps(
            payload,
            ensure_ascii=False,
        )
    }


async def _stream_agent(
    query: str,
    run_id: str,
    started_at: float,
    history: list[ChatMessageRequest] | None = None,
    session_id: str | None = None,
    checkpointer=None,
    store=None,
    pool=None,
) -> AsyncIterator[dict[str, str]]:
    printed_steps = 0
    tracker = UsageTracker()
    use_checkpointer = checkpointer is not None
    initial_state = _initial_state(query, history, use_checkpointer=use_checkpointer)
    config = _graph_config(session_id or str(uuid.uuid4()))
    final_state = initial_state

    try:
        graph = build_graph(tracker=tracker, checkpointer=checkpointer, store=store, pool=pool)
        async for state in graph.astream(initial_state, config=config, stream_mode="values"):
            final_state = state
            steps = state.get("intermediate_steps", [])
            while printed_steps < len(steps):
                step_number = printed_steps + 1
                step = steps[printed_steps]
                yield _sse_payload(
                    "thought",
                    step["thought"],
                    step_number,
                    run_id=run_id,
                    started_at=started_at,
                    timestamp=step.get("timestamp"),
                )
                yield _sse_payload(
                    "action",
                    f"Executing {step['action']}.",
                    step_number,
                    step["action"],
                    action_input=step.get("action_input"),
                    run_id=run_id,
                    started_at=started_at,
                    timestamp=step.get("timestamp"),
                )
                yield _sse_payload(
                    "observation",
                    step["observation"],
                    step_number,
                    step["action"],
                    action_input=step.get("action_input"),
                    run_id=run_id,
                    started_at=started_at,
                    timestamp=step.get("timestamp"),
                )
                printed_steps += 1
                await asyncio.sleep(0)
    except MaxIterationsError:
        tools_used = list(
            dict.fromkeys(
                step["action"]
                for step in final_state.get("intermediate_steps", [])
                if step.get("action")
            )
        )
        yield _sse_payload(
            "final",
            "Agent reached the step limit without a final answer.",
            printed_steps + 1,
            run_id=run_id,
            started_at=started_at,
            tools_used=tools_used,
            status="error",
        )
        return
    except Exception as exc:
        logger.exception("Agent stream failed for run %s", run_id)
        yield _sse_payload(
            "final",
            f"Agent failed before returning an answer: {type(exc).__name__}: {exc}",
            printed_steps + 1,
            run_id=run_id,
            started_at=started_at,
            tools_used=[],
            status="error",
        )
        return

    response = _build_response(run_id, started_at, final_state, tracker.summary())
    _store_response(response)
    yield _sse_payload(
        "final",
        response.result,
        printed_steps + 1,
        run_id=run_id,
        started_at=started_at,
        tools_used=response.tools_used,
        status="success",
        usage=response.usage,
    )


async def _sse_response(iterator: AsyncIterator[dict[str, str]]) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        async for payload in iterator:
            yield f"data: {payload['data']}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@app.post("/agent/invoke", response_model=AgentResponse)
@app.post("/api/agent/invoke", response_model=AgentResponse)
@app.post("/run", response_model=AgentResponse)
@app.post("/api/run", response_model=AgentResponse)
async def run_agent(request: Request, payload: QueryRequest):
    run_id = uuid.uuid4().hex
    started_at = time.perf_counter()
    session_id = _get_session_id(request)
    checkpointer = getattr(request.app.state, "checkpointer", None)
    store = getattr(request.app.state, "store", None)
    pool = getattr(request.app.state, "pool", None)
    if payload.stream:
        return await _sse_response(
            _stream_agent(
                payload.query, run_id, started_at, payload.history,
                session_id=session_id, checkpointer=checkpointer, store=store, pool=pool,
            )
        )
    return await _run_agent(
        payload.query, run_id, started_at, payload.history,
        session_id=session_id, checkpointer=checkpointer, store=store, pool=pool,
    )


@app.get("/run")
@app.get("/api/run")
async def stream_agent(request: Request, query: str, stream: bool = True):
    run_id = uuid.uuid4().hex
    started_at = time.perf_counter()
    session_id = _get_session_id(request)
    checkpointer = getattr(request.app.state, "checkpointer", None)
    store = getattr(request.app.state, "store", None)
    pool = getattr(request.app.state, "pool", None)
    if stream:
        return await _sse_response(
            _stream_agent(
                query, run_id, started_at,
                session_id=session_id, checkpointer=checkpointer, store=store, pool=pool,
            )
        )
    return await _run_agent(
        query, run_id, started_at,
        session_id=session_id, checkpointer=checkpointer, store=store, pool=pool,
    )


@app.get("/health")
@app.get("/api/health")
async def health() -> dict[str, object]:
    return {"status": "ok", "tools": list(TOOLS.keys())}


@app.get("/keepalive")
@app.get("/api/keepalive")
async def keepalive_handler(request: Request):
    cron_secret = os.getenv("CRON_SECRET", "")
    auth = request.headers.get("authorization", "")
    if cron_secret and auth != f"Bearer {cron_secret}":
        return Response(status_code=401)

    from agent.db import pooler_connection

    now = datetime.now(timezone.utc)
    try:
        async with pooler_connection() as conn:
            await conn.execute(
                "UPDATE keepalive SET pinged_at = %s WHERE id = 1",
                (now,),
            )
    except Exception:
        logger.exception("keepalive DB write failed")
        return Response(status_code=500)
    return {"status": "ok", "pinged_at": now.isoformat()}


@app.get("/config", response_model=AgentConfigResponse)
@app.get("/api/config", response_model=AgentConfigResponse)
async def config() -> AgentConfigResponse:
    models = [
        ModelInfoResponse(**model.__dict__)
        for model in configured_model_info(responder_provider())
    ]
    return AgentConfigResponse(
        status="configured" if models else "unconfigured",
        active_model=models[0] if models else None,
        fallback_models=models[1:],
        tools=list(TOOLS.keys()),
    )


@limiter.exempt
@app.post("/suggestions", response_model=SuggestionsResponse)
@app.post("/api/suggestions", response_model=SuggestionsResponse)
async def suggestions(request: Request, payload: SuggestionsRequest) -> SuggestionsResponse:
    """Generate conversation-aware follow-up prompts via the suggester LLM.
    Exempt from the rate limit: a turn already spends one call on /run, and the
    suggester degrades to a static fallback rather than failing."""
    history = [
        {"role": message.role, "content": message.content}
        for message in payload.history
    ]
    result = generate_suggestions(history, list(TOOLS.keys()), payload.tools_used)
    return SuggestionsResponse(suggestions=result)


@app.get("/evals")
@app.get("/api/evals")
async def evals() -> dict[str, Any]:
    """Serve the published evaluation baseline (backend/evals/baseline.json),
    generated by `python -m evals.evaluate --publish`. Returns an unavailable
    marker when no baseline has been committed yet."""
    if EVALS_BASELINE.is_file():
        try:
            return json.loads(EVALS_BASELINE.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            logger.warning("Failed to read evals baseline at %s", EVALS_BASELINE)
    return {"status": "unavailable"}


@app.get("/trace/{run_id}", response_model=AgentResponse)
@app.get("/api/trace/{run_id}", response_model=AgentResponse)
async def get_trace(run_id: str) -> AgentResponse:
    response = RUNS.get(run_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return response


@app.delete("/memory/{session_id}")
@app.delete("/api/memory/{session_id}")
async def clear_memory(session_id: str, request: Request) -> dict:
    if not _is_valid_session_id(session_id):
        raise HTTPException(status_code=400, detail="invalid session id")
    checkpointer = getattr(request.app.state, "checkpointer", None)
    pool = getattr(request.app.state, "pool", None)
    if checkpointer is not None:
        await checkpointer.adelete_thread(session_id)
    if pool is not None:
        async with pool.connection() as conn:
            await conn.execute(
                "DELETE FROM store WHERE prefix LIKE %s",
                (f"{MEMORY_NAMESPACE_PREFIX}.{session_id}%",),
            )
    return {"status": "cleared", "session_id": session_id}


MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB; headroom under Vercel's 4.5 MB body cap


def _is_allowed_upload(filename: str, content_type: str) -> bool:
    content_type = (content_type or "").lower()
    name = (filename or "").lower()
    if content_type == "application/pdf" or content_type.startswith("text/"):
        return True
    return name.endswith((".pdf", ".txt", ".md"))


@app.post("/upload", response_model=UploadResponse)
@app.post("/api/upload", response_model=UploadResponse)
async def upload_document(request: Request, file: UploadFile = File(...)) -> UploadResponse:
    session_id = _get_session_id(request)
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 2 MB limit")
    if not _is_allowed_upload(file.filename or "", file.content_type or ""):
        raise HTTPException(
            status_code=415, detail="Only PDF and plain-text files are supported"
        )
    from agent.ingest import ingest_document

    result = await ingest_document(
        pool, session_id, file.filename or "upload", content, file.content_type or ""
    )
    return UploadResponse(**result)


@app.get("/documents/{session_id}", response_model=DocumentListResponse)
@app.get("/api/documents/{session_id}", response_model=DocumentListResponse)
async def list_documents(session_id: str, request: Request) -> DocumentListResponse:
    if not _is_valid_session_id(session_id):
        raise HTTPException(status_code=400, detail="invalid session id")
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        return DocumentListResponse(documents=[])
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT d.id, d.filename, d.created_at, COUNT(dc.id) AS chunk_count
            FROM documents d
            LEFT JOIN document_chunks dc ON dc.document_id = d.id
            WHERE d.session_id = %s
            GROUP BY d.id, d.filename, d.created_at
            ORDER BY d.created_at DESC
            """,
            (session_id,),
        )
        rows = await cur.fetchall()
    return DocumentListResponse(
        documents=[
            DocumentInfo(
                id=str(row["id"]),
                filename=row["filename"],
                chunk_count=int(row["chunk_count"]),
                created_at=row["created_at"].isoformat(),
            )
            for row in rows
        ]
    )


@app.get("/", include_in_schema=False)
@app.get("/{path:path}", include_in_schema=False)
async def serve_frontend(path: str = ""):
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")

    dist_root = DIST_DIR.resolve()
    requested_file = (dist_root / path).resolve()

    # Strict path traversal protection: ensure requested file is within dist_root
    try:
        requested_file.relative_to(dist_root)
    except ValueError:
        raise HTTPException(status_code=404, detail="File not found")

    if requested_file.is_file():
        return FileResponse(requested_file)

    index_file = dist_root / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)

    raise HTTPException(status_code=404, detail="Frontend build not found")
