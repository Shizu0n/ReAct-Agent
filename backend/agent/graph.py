from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, cast
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.store.base import BaseStore

from agent.llms import (
    FreeModelFallback,
    UsageTracker,
    UsageTrackingLLM,
    load_model_environment,
    providers_preferring,
    responder_provider,
)
from agent.prompts import SYSTEM_PROMPT
from agent.state import AgentState, MaxIterationsError, Step
from agent.tools import (
    calculator,
    normalize_python_code_input,
    python_executor,
    web_search,
)

MAX_ITERATIONS = 10
WEB_SEARCH_TOOL_NAME = cast(Any, web_search).name
PYTHON_EXECUTOR_TOOL_NAME = cast(Any, python_executor).name
CALCULATOR_TOOL_NAME = cast(Any, calculator).name
MEMORY_READ_TOOL_NAME = "memory_read"
MEMORY_WRITE_TOOL_NAME = "memory_write"
DOCUMENT_SEARCH_TOOL_NAME = "document_search"
MEMORY_NAMESPACE_PREFIX = "memories"
MAX_MEMORIES_STORED = int(os.getenv("MEMORY_MAX_STORED", "20"))
TOOLS = {
    WEB_SEARCH_TOOL_NAME: web_search,
    PYTHON_EXECUTOR_TOOL_NAME: python_executor,
    CALCULATOR_TOOL_NAME: calculator,
}
TOOL_INPUT_KEYS = {
    WEB_SEARCH_TOOL_NAME: "query",
    PYTHON_EXECUTOR_TOOL_NAME: "code",
    CALCULATOR_TOOL_NAME: "expression",
    MEMORY_READ_TOOL_NAME: "query",
    MEMORY_WRITE_TOOL_NAME: "content",
    DOCUMENT_SEARCH_TOOL_NAME: "query",
}

# OpenAI-style tool schemas. The descriptions are deliberately directive: tool
# selection is driven by these strings, so they tell the model to call the tool
# rather than reason the answer out itself.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": CALCULATOR_TOOL_NAME,
            "description": (
                "Evaluate an arithmetic or numeric math expression and return the "
                "exact result. Use this for ANY arithmetic the user asks about "
                "(addition, subtraction, multiplication, division, powers, roots, "
                "percentages) instead of computing it yourself. Supports Python "
                "operators and the math module, e.g. '17 * 23 + math.sqrt(1764)'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The math expression to evaluate.",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": PYTHON_EXECUTOR_TOOL_NAME,
            "description": (
                "Run a snippet of Python and return its stdout. Use for multi-step "
                "computation, sequences, statistics, list/data processing, or "
                "symbolic algebra with sympy. The code must be runnable Python with "
                "no Markdown fences; print the value you need. Do not use names that "
                "start with an underscore."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Runnable Python source that prints its result.",
                    }
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": WEB_SEARCH_TOOL_NAME,
            "description": (
                "Search the web for current, external, or citable facts: latest "
                "versions, release dates, prices, news, or public documentation. "
                "Returns titled results with URLs. Use this instead of answering "
                "current-fact questions from memory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": MEMORY_READ_TOOL_NAME,
            "description": (
                "Read facts the user has shared in previous sessions. Call this at "
                "the start of any conversation where the user refers to a past "
                "interaction or where you want to personalize your response. Returns "
                "stored facts ordered by recency."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Brief description of what to recall.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": MEMORY_WRITE_TOOL_NAME,
            "description": (
                "Store a fact the user has shared for recall in future sessions. "
                "Call this when the user shares a durable personal fact, preference, "
                "or goal. Store one discrete fact per call."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The fact to remember, written as a brief statement.",
                    }
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": DOCUMENT_SEARCH_TOOL_NAME,
            "description": (
                "Search the documents the user uploaded in this session. Call this "
                "when the user asks about the content of an uploaded file. Returns "
                "relevant passages with citations. If no documents are uploaded or "
                "nothing relevant is found, it returns a clear message; do not guess "
                "the answer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question to search for in uploaded documents.",
                    }
                },
                "required": ["query"],
            },
        },
    },
]

CURRENT_FACT_PATTERNS = (
    r"\blatest version\b",
    r"\bcurrent version\b",
    r"\bnewest release\b",
    r"\bwhat\s+is\s+the\s+(?:current|latest|newest)\b",
    r"\bis\s+.+\s+(?:still|now|currently)\b",
    r"\b(?:price|stock|news|today|this year)\b",
    # Year mentions only count as a current-fact signal in temporal phrasing
    # ("in 2025", "during 2026"), not as bare numbers inside a math expression
    # such as "square root of 2025".
    r"\b(?:in|during|since|throughout)\s+202[4-9]\b",
)
EXTERNAL_LOOKUP_PATTERNS = (
    r"\bsearch(?:\s+the\s+web)?\b",
    r"\blook\s+up\b",
    r"\bfind\s+(?:sources|references|current|latest)\b",
    r"\b(?:sources?|citations?|references?)\b",
    r"\bpublic\s+documentation\b",
)
SOURCE_FOLLOWUP_PATTERNS = (
    r"\b(?:sources?|citations?|references?)\b",
    r"\bwhere\s+did\s+.+\s+come\s+from\b",
    r"\bverify\s+the\s+last\s+answer\b",
)
WEB_SEARCH_GATE_DISABLE_ENV = "REACT_AGENT_DISABLE_WEB_SEARCH_GATE"
MAX_CURRENT_FACT_WEB_SEARCHES = 2
URL_PATTERN = re.compile(r"https?://[^\s)>\]]+")


def _last_user_message(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        content = str(message.content)
        if isinstance(message, HumanMessage) and not content.startswith("Observation:"):
            return content
    return ""


def _previous_user_subject(messages: list[BaseMessage]) -> str:
    for message in reversed(messages[:-1]):
        content = str(message.content).strip()
        if (
            isinstance(message, HumanMessage)
            and content
            and not content.startswith("Observation:")
            and not _is_source_followup(content)
        ):
            return content
    return ""


def _web_search_gate_disabled() -> bool:
    return os.getenv(WEB_SEARCH_GATE_DISABLE_ENV, "").lower() in {"1", "true", "yes"}


def _requires_web_search(query: str) -> bool:
    if _web_search_gate_disabled():
        return False

    return any(
        re.search(pattern, query, flags=re.IGNORECASE)
        for pattern in (*CURRENT_FACT_PATTERNS, *EXTERNAL_LOOKUP_PATTERNS)
    )


def _is_source_followup(query: str) -> bool:
    return any(
        re.search(pattern, query, flags=re.IGNORECASE)
        for pattern in SOURCE_FOLLOWUP_PATTERNS
    )


def _web_search_action_input(query: str, messages: list[BaseMessage]) -> str:
    if _is_source_followup(query):
        previous_subject = _previous_user_subject(messages)
        if previous_subject:
            return f"{previous_subject} sources"
    return query


def _runtime_system_prompt() -> str:
    current_date = datetime.now(timezone.utc).date().isoformat()
    return (
        f"{SYSTEM_PROMPT}\n\n"
        "Runtime context:\n"
        f"- Current date: {current_date}.\n"
        "- Dates before the current date are past dates, not future dates.\n"
        "- For current-fact questions, answer from web_search results once you "
        "have them; do not repeat web_search just because your training knowledge "
        "feels inconsistent.\n"
        "- If the user explicitly asks to search, cite sources, list sources, or "
        "verify with public documentation, call web_search before answering. If it "
        "is a follow-up, search for sources about the previous substantive request."
    )


def _web_search_count(steps: list[Step]) -> int:
    return sum(1 for step in steps if step.get("action") == WEB_SEARCH_TOOL_NAME)


def _latest_web_search_observation(steps: list[Step]) -> str:
    for step in reversed(steps):
        if step.get("action") == WEB_SEARCH_TOOL_NAME:
            return str(step.get("observation", "")).strip()
    return ""


def _source_urls_from_observation(observation: str) -> list[str]:
    urls = [url.rstrip(".,;:") for url in URL_PATTERN.findall(observation)]
    return list(dict.fromkeys(urls))


def _with_source_urls_if_needed(answer: str, steps: list[Step]) -> str:
    if WEB_SEARCH_TOOL_NAME not in {step.get("action") for step in steps}:
        return answer
    if URL_PATTERN.search(answer):
        return answer

    urls = _source_urls_from_observation(_latest_web_search_observation(steps))
    if not urls:
        return answer

    source_lines = "\n".join(f"- {url}" for url in urls[:3])
    return f"{answer.rstrip()}\n\nSources:\n{source_lines}"


def _tool_call_action_input(call: dict[str, Any]) -> str:
    """Reduce a tool call's structured args to the single display string the
    trace and UI expect (the expression / code / query)."""
    args = call.get("args", {}) or {}
    key = TOOL_INPUT_KEYS.get(call.get("name", ""))
    if key and key in args:
        return str(args[key])
    if len(args) == 1:
        return str(next(iter(args.values())))
    return str(args)


def _last_ai_message(messages: list[BaseMessage]) -> AIMessage | None:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return message
    return None


def _forced_web_search_message(query: str, messages: list[BaseMessage]) -> AIMessage:
    return AIMessage(
        content=(
            "I should verify this with a web search before answering, since my "
            "training data may be outdated or the user asked for sources."
        ),
        tool_calls=[
            {
                "name": WEB_SEARCH_TOOL_NAME,
                "args": {"query": _web_search_action_input(query, messages)},
                "id": "forced_web_search",
            }
        ],
    )


def _create_default_llm() -> Any:
    load_model_environment()
    return FreeModelFallback(providers_preferring(responder_provider()))


def agent_node(state: AgentState, llm: Any) -> dict[str, Any]:
    messages = state.get("messages", [])
    prompt_messages = [SystemMessage(content=_runtime_system_prompt()), *messages]
    response = llm.invoke(prompt_messages, tools=TOOL_SCHEMAS)
    if not isinstance(response, AIMessage):
        response = AIMessage(content=str(getattr(response, "content", response)))

    query = _last_user_message(messages)
    steps = state.get("intermediate_steps", [])
    tool_calls = list(response.tool_calls or [])

    wants_web_search = any(
        call.get("name") == WEB_SEARCH_TOOL_NAME for call in tool_calls
    )

    # Guardrail: do not let the model answer a current-fact question from memory.
    if not tool_calls and not steps and _requires_web_search(query):
        forced = _forced_web_search_message(query, messages)
        return {"messages": [forced]}

    # Guardrail: stop a web_search loop after enough current-fact searches.
    if (
        wants_web_search
        and _requires_web_search(query)
        and _web_search_count(steps) >= MAX_CURRENT_FACT_WEB_SEARCHES
    ):
        observation = _latest_web_search_observation(steps)
        answer = (
            "Based on the latest web_search results, the current answer is:\n"
            f"{observation}"
        )
        final = AIMessage(content=answer)
        return {"messages": [final], "final_answer": answer}

    if tool_calls:
        return {"messages": [response]}

    # Final answer: ground it with source URLs if web_search was used.
    answer = _with_source_urls_if_needed(str(response.content), steps)
    final = AIMessage(content=answer)
    return {"messages": [final], "final_answer": answer}


async def _run_memory_read(store: BaseStore, session_id: str, query: str) -> str:
    namespace = (MEMORY_NAMESPACE_PREFIX, session_id)
    items = await store.asearch(namespace, limit=MAX_MEMORIES_STORED)
    if not items:
        return "No memories found for this session."
    facts = [item.value.get("text", "") for item in items if item.value.get("text")]
    if not facts:
        return "No memories found for this session."
    return (
        "--- BEGIN USER MEMORIES ---\n"
        + "\n".join(f"- {f}" for f in facts)
        + "\n--- END USER MEMORIES ---"
    )


async def _run_memory_write(store: BaseStore, session_id: str, content: str) -> str:
    if not content or not content.strip():
        return "Memory not stored: empty content."
    namespace = (MEMORY_NAMESPACE_PREFIX, session_id)
    existing = await store.asearch(namespace, limit=MAX_MEMORIES_STORED + 1)
    if len(existing) >= MAX_MEMORIES_STORED:
        oldest = existing[-1]
        await store.adelete(namespace, oldest.key)
    key = str(uuid4())
    await store.aput(namespace, key, {"text": content})
    return f"Stored: {content}"


async def _run_document_search(pool, session_id: str, query: str) -> str:
    if pool is None:
        return "Document search is unavailable in this session."
    from agent.embedding import embed_query

    query_embedding = await embed_query(query, os.getenv("GEMINI_API_KEY", ""))
    vec_str = "[" + ",".join(str(round(x, 8)) for x in query_embedding) + "]"
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT dc.content, d.filename, dc.chunk_index
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.session_id = %s
            ORDER BY dc.embedding <=> %s::vector(768)
            LIMIT 5
            """,
            (session_id, vec_str),
        )
        rows = await cur.fetchall()
    if not rows:
        return (
            "No relevant content was found in the documents uploaded for this "
            "session. If no documents were uploaded, tell the user so; do not "
            "answer from general knowledge."
        )
    lines = ["--- BEGIN RETRIEVED DOCUMENTS ---"]
    for row in rows:
        lines.append(f"[Source: {row['filename']}, chunk {row['chunk_index'] + 1}]")
        lines.append(row["content"])
        lines.append("")
    lines.append("--- END RETRIEVED DOCUMENTS ---")
    lines.append(
        f"{len(rows)} passage(s) retrieved. Cite sources as "
        "[Source: filename, chunk N] in your answer. If these passages do not "
        "answer the question, say so explicitly instead of guessing."
    )
    return "\n".join(lines)


def _run_tool(action: str, action_input: str) -> str:
    tool = TOOLS.get(action)
    if tool is None:
        return f"Error: unknown tool '{action}'. Available tools: {', '.join(TOOLS)}"

    input_key = TOOL_INPUT_KEYS[action]
    try:
        return str(tool.invoke({input_key: action_input}))
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"


def _normalize_tool_input(action: str, action_input: str) -> str:
    if action == PYTHON_EXECUTOR_TOOL_NAME:
        return normalize_python_code_input(action_input)
    return action_input


async def tool_node(state: AgentState, store: BaseStore, config: RunnableConfig, pool=None) -> dict[str, Any]:
    messages = state.get("messages", [])
    last_ai = _last_ai_message(messages)
    tool_calls = list(last_ai.tool_calls) if last_ai and last_ai.tool_calls else []

    thought = str(last_ai.content) if last_ai else ""
    session_id = config.get("configurable", {}).get("thread_id", "")
    new_messages: list[BaseMessage] = []
    new_steps: list[Step] = []
    for call in tool_calls:
        action = call.get("name", "")
        action_input = _normalize_tool_input(action, _tool_call_action_input(call))
        if action == MEMORY_READ_TOOL_NAME:
            if store is None:
                observation = "Memory is unavailable in this session."
            else:
                observation = await _run_memory_read(store, session_id, action_input)
        elif action == MEMORY_WRITE_TOOL_NAME:
            if store is None:
                observation = "Memory is unavailable in this session."
            else:
                observation = await _run_memory_write(store, session_id, action_input)
        elif action == DOCUMENT_SEARCH_TOOL_NAME:
            if pool is None:
                observation = "Document search is unavailable in this session."
            else:
                observation = await _run_document_search(pool, session_id, action_input)
        else:
            observation = _run_tool(action, action_input)
        new_messages.append(
            ToolMessage(content=observation, tool_call_id=call.get("id", action))
        )
        new_steps.append(
            {
                "thought": thought,
                "action": action,
                "action_input": action_input,
                "observation": observation,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    return {
        "messages": new_messages,
        "intermediate_steps": [*state.get("intermediate_steps", []), *new_steps],
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def should_continue(state: AgentState) -> str:
    if state.get("final_answer") is not None:
        return "end"

    if state.get("iteration_count", 0) >= MAX_ITERATIONS:
        raise MaxIterationsError(f"Reached max iterations: {MAX_ITERATIONS}")

    last_ai = _last_ai_message(state.get("messages", []))
    return "tools" if last_ai and last_ai.tool_calls else "end"


def build_graph(llm: Any | None = None, tracker: UsageTracker | None = None, checkpointer=None, store=None, pool=None):
    active_llm = llm or _create_default_llm()
    if tracker is not None:
        active_llm = UsageTrackingLLM(active_llm, tracker)
    workflow = StateGraph(AgentState)
    workflow.add_node("agent_node", lambda state: agent_node(state, active_llm))  # type: ignore

    async def _tool_node(state: AgentState, store: BaseStore, config: RunnableConfig) -> dict[str, Any]:
        return await tool_node(state, store, config, pool=pool)

    workflow.add_node("tool_node", _tool_node)
    workflow.add_edge(START, "agent_node")
    workflow.add_conditional_edges(
        "agent_node",
        should_continue,
        {"tools": "tool_node", "end": END},
    )
    workflow.add_edge("tool_node", "agent_node")
    return workflow.compile(checkpointer=checkpointer, store=store)
