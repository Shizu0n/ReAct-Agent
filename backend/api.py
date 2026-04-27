from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from pathlib import Path
from typing import AsyncIterator, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from agent.graph import TOOLS, build_graph
from agent.llms import configured_model_info
from agent.redaction import configure_secure_logging
from agent.shortcuts import ShortcutResult, try_contextual_shortcut, try_shortcut
from agent.state import Step

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
    trace: list[Step]
    total_time: float
    run_id: str
    answer: str
    steps: list[Step]
    tools_used: list[str]
    latency_ms: int
    status: str


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


RUNS: dict[str, AgentResponse] = {}
RUN_ORDER: deque[str] = deque()
MAX_STORED_RUNS = 100
DIST_DIR = Path(__file__).resolve().parents[1] / "frontend" / "dist"

limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])
app = FastAPI(title="01 React Agent API")
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
        logger.exception("%s %s -> 500 %.4fs", request.method, request.url.path, elapsed)
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
        messages.append(HumanMessage(content=content) if item.role == "user" else AIMessage(content=content))
    return messages


def _history_text(history: list[ChatMessageRequest] | None = None) -> list[str]:
    return [item.content for item in history or [] if item.content.strip()]


def _initial_state(query: str, history: list[ChatMessageRequest] | None = None) -> dict:
    return {
        "messages": [*_history_messages(history or []), HumanMessage(content=query)],
        "intermediate_steps": [],
        "iteration_count": 0,
        "final_answer": None,
    }


def _store_response(response: AgentResponse) -> None:
    if response.run_id not in RUNS and len(RUN_ORDER) >= MAX_STORED_RUNS:
        oldest_run_id = RUN_ORDER.popleft()
        RUNS.pop(oldest_run_id, None)

    if response.run_id not in RUNS:
        RUN_ORDER.append(response.run_id)
    RUNS[response.run_id] = response


def _build_response(run_id: str, started_at: float, final_state: dict) -> AgentResponse:
    trace = final_state.get("intermediate_steps", [])
    result = final_state.get("final_answer") or ""
    total_time = time.perf_counter() - started_at
    tools_used = list(dict.fromkeys(step["action"] for step in trace if step.get("action")))

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
    )


def _shortcut_state(
    query: str,
    shortcut: ShortcutResult,
    history: list[ChatMessageRequest] | None = None,
) -> dict:
    return {
        "messages": [*_history_messages(history or []), HumanMessage(content=query)],
        "intermediate_steps": [shortcut.step],
        "iteration_count": 1,
        "final_answer": shortcut.final_answer,
    }


def _run_agent(
    query: str,
    run_id: str,
    started_at: float,
    history: list[ChatMessageRequest] | None = None,
) -> AgentResponse:
    shortcut = try_shortcut(query) or try_contextual_shortcut(query, _history_text(history))
    if shortcut is not None:
        response = _build_response(run_id, started_at, _shortcut_state(query, shortcut, history))
        _store_response(response)
        return response

    graph = build_graph()
    final_state = graph.invoke(_initial_state(query, history))
    response = _build_response(run_id, started_at, final_state)
    _store_response(response)
    return response


def _sse_payload(
    event_type: str,
    content: str,
    step: int,
    tool: str | None = None,
) -> dict[str, str]:
    payload: dict[str, object] = {"type": event_type, "content": content, "step": step}
    if tool:
        payload["tool"] = tool

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
) -> AsyncIterator[dict[str, str]]:
    shortcut = try_shortcut(query) or try_contextual_shortcut(query, _history_text(history))
    if shortcut is not None:
        response = _build_response(run_id, started_at, _shortcut_state(query, shortcut, history))
        _store_response(response)
        yield _sse_payload("thought", shortcut.step["thought"], 1)
        yield _sse_payload("action", shortcut.step["action"], 1)
        yield _sse_payload("observation", shortcut.step["observation"], 1)
        yield _sse_payload("final", response.result, 2)
        return

    graph = build_graph()
    printed_steps = 0
    final_state = _initial_state(query, history)

    for state in graph.stream(final_state, stream_mode="values"):
        final_state = state
        steps = state.get("intermediate_steps", [])
        while printed_steps < len(steps):
            step_number = printed_steps + 1
            step = steps[printed_steps]
            yield _sse_payload("thought", step["thought"], step_number)
            yield _sse_payload("action", f"Executing {step['action']}.", step_number, step["action"])
            yield _sse_payload("observation", step["observation"], step_number)
            printed_steps += 1
            await asyncio.sleep(0)

    response = _build_response(run_id, started_at, final_state)
    _store_response(response)
    yield _sse_payload("final", response.result, printed_steps + 1)


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
    if payload.stream:
        return await _sse_response(_stream_agent(payload.query, run_id, started_at, payload.history))
    return _run_agent(payload.query, run_id, started_at, payload.history)


@app.get("/run")
@app.get("/api/run")
async def stream_agent(query: str, stream: bool = True):
    run_id = uuid.uuid4().hex
    started_at = time.perf_counter()
    if stream:
        return await _sse_response(_stream_agent(query, run_id, started_at))
    return _run_agent(query, run_id, started_at)


@app.get("/health")
@app.get("/api/health")
async def health() -> dict[str, object]:
    return {"status": "ok", "tools": list(TOOLS.keys())}


@app.get("/config", response_model=AgentConfigResponse)
@app.get("/api/config", response_model=AgentConfigResponse)
async def config() -> AgentConfigResponse:
    models = [ModelInfoResponse(**model.__dict__) for model in configured_model_info()]
    return AgentConfigResponse(
        status="configured" if models else "unconfigured",
        active_model=models[0] if models else None,
        fallback_models=models[1:],
        tools=list(TOOLS.keys()),
    )


@app.get("/trace/{run_id}", response_model=AgentResponse)
@app.get("/api/trace/{run_id}", response_model=AgentResponse)
async def get_trace(run_id: str) -> AgentResponse:
    response = RUNS.get(run_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return response


@app.get("/", include_in_schema=False)
@app.get("/{path:path}", include_in_schema=False)
async def serve_frontend(path: str = ""):
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")

    dist_root = DIST_DIR.resolve()
    requested_file = (dist_root / path).resolve()
    if requested_file.is_file() and dist_root in requested_file.parents:
        return FileResponse(requested_file)

    index_file = dist_root / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)

    raise HTTPException(status_code=404, detail="Frontend build not found")
