from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from agent.llms import FreeModelFallback, configured_free_providers, load_model_environment
from agent.prompts import SYSTEM_PROMPT
from agent.state import AgentState, MaxIterationsError, Step
from agent.tools import calculator, python_executor, web_search

MAX_ITERATIONS = 10
TOOLS = {
    web_search.name: web_search,
    python_executor.name: python_executor,
    calculator.name: calculator,
}
TOOL_INPUT_KEYS = {
    web_search.name: "query",
    python_executor.name: "code",
    calculator.name: "expression",
}
CURRENT_FACT_PATTERNS = (
    r"\blatest version\b",
    r"\bcurrent version\b",
    r"\bnewest release\b",
    r"\bwhat\s+is\s+the\s+(?:current|latest|newest)\b",
    r"\bis\s+.+\s+(?:still|now|currently)\b",
    r"\b(?:price|stock|news|today|this year|2024|2025|2026)\b",
)
WEB_SEARCH_GATE_DISABLE_ENV = "REACT_AGENT_DISABLE_WEB_SEARCH_GATE"
MAX_CURRENT_FACT_WEB_SEARCHES = 2


@dataclass
class ParsedResponse:
    thought: str
    action: str | None = None
    action_input: str | None = None
    final_answer: str | None = None


def _extract_field(label: str, content: str) -> str | None:
    pattern = (
        rf"(?:^|\n){re.escape(label)}\s*:\s*"
        rf"(.*?)(?=\n(?:Thought|Action|Action Input|Observation|Final Answer)\s*:|\Z)"
    )
    match = re.search(pattern, content, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else None


def parse_react_response(content: str) -> ParsedResponse:
    thought = _extract_field("Thought", content) or ""
    final_answer = _extract_field("Final Answer", content)
    if final_answer is not None:
        return ParsedResponse(thought=thought, final_answer=final_answer)

    action = _extract_field("Action", content)
    action_input = _extract_field("Action Input", content)
    if action and action_input is not None:
        return ParsedResponse(
            thought=thought,
            action=action.strip(),
            action_input=action_input,
        )

    return ParsedResponse(thought=thought, final_answer=content.strip())


def _last_ai_message(messages: list[BaseMessage]) -> AIMessage | None:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return message
    return None


def _last_user_message(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        content = str(message.content)
        if isinstance(message, HumanMessage) and not content.startswith("Observation:"):
            return content
    return ""


def _web_search_gate_disabled() -> bool:
    import os

    return os.getenv(WEB_SEARCH_GATE_DISABLE_ENV, "").lower() in {"1", "true", "yes"}


def _requires_web_search(query: str) -> bool:
    if _web_search_gate_disabled():
        return False

    return any(
        re.search(pattern, query, flags=re.IGNORECASE)
        for pattern in CURRENT_FACT_PATTERNS
    )


def _runtime_system_prompt() -> str:
    current_date = datetime.now(timezone.utc).date().isoformat()
    return (
        f"{SYSTEM_PROMPT}\n\n"
        "Runtime context:\n"
        f"- Current date: {current_date}.\n"
        "- Dates before the current date are past dates, not future dates.\n"
        "- For current-fact questions, answer from web_search observations after "
        "you have relevant results; do not repeat web_search just because your "
        "training knowledge feels inconsistent."
    )


def _web_search_count(steps: list[Step]) -> int:
    return sum(1 for step in steps if step.get("action") == web_search.name)


def _latest_web_search_observation(steps: list[Step]) -> str:
    for step in reversed(steps):
        if step.get("action") == web_search.name:
            return str(step.get("observation", "")).strip()
    return ""


def _forced_final_from_search_observation(observation: str) -> str:
    return (
        "Thought: I already searched the web and have current results; repeating "
        "web_search would risk a loop.\n"
        "Final Answer: Based on the latest web_search observation, the current "
        f"answer is:\n{observation}"
    )


def _parsed_from_state(state: AgentState) -> ParsedResponse:
    last_ai = _last_ai_message(state.get("messages", []))
    if last_ai is None:
        return ParsedResponse(thought="", final_answer="")

    parsed = last_ai.additional_kwargs.get("react")
    if parsed:
        return ParsedResponse(**parsed)
    return parse_react_response(str(last_ai.content))


def _create_default_llm() -> Any:
    load_model_environment()
    return FreeModelFallback(configured_free_providers())


def agent_node(state: AgentState, llm: Any) -> dict[str, Any]:
    prompt_messages = [SystemMessage(content=_runtime_system_prompt()), *state.get("messages", [])]
    response = llm.invoke(prompt_messages)
    content = str(getattr(response, "content", response))
    parsed = parse_react_response(content)
    latest_query = _last_user_message(state.get("messages", []))
    steps = state.get("intermediate_steps", [])
    if (
        parsed.final_answer is not None
        and not steps
        and _requires_web_search(latest_query)
    ):
        content = (
            "Thought: I must search the web before answering this - my training "
            "data may be outdated.\n"
            "Action: web_search\n"
            f"Action Input: {latest_query}"
        )
        parsed = parse_react_response(content)
    elif (
        parsed.action == web_search.name
        and _requires_web_search(latest_query)
        and _web_search_count(steps) >= MAX_CURRENT_FACT_WEB_SEARCHES
    ):
        content = _forced_final_from_search_observation(
            _latest_web_search_observation(steps)
        )
        parsed = parse_react_response(content)

    ai_message = AIMessage(content=content, additional_kwargs={"react": asdict(parsed)})
    update: dict[str, Any] = {"messages": [ai_message]}
    if parsed.final_answer is not None:
        update["final_answer"] = parsed.final_answer
    return update


def _run_tool(action: str, action_input: str) -> str:
    tool = TOOLS.get(action)
    if tool is None:
        return f"Error: unknown tool '{action}'. Available tools: {', '.join(TOOLS)}"

    input_key = TOOL_INPUT_KEYS[action]
    try:
        return str(tool.invoke({input_key: action_input}))
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"


def tool_node(state: AgentState) -> dict[str, Any]:
    parsed = _parsed_from_state(state)
    action = parsed.action or ""
    action_input = parsed.action_input or ""
    observation = _run_tool(action, action_input)
    step: Step = {
        "thought": parsed.thought,
        "action": action,
        "action_input": action_input,
        "observation": observation,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    steps = [*state.get("intermediate_steps", []), step]
    return {
        "messages": [HumanMessage(content=f"Observation: {observation}")],
        "intermediate_steps": steps,
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def should_continue(state: AgentState) -> str:
    if state.get("final_answer") is not None:
        return "end"

    if state.get("iteration_count", 0) >= MAX_ITERATIONS:
        raise MaxIterationsError(f"Reached max iterations: {MAX_ITERATIONS}")

    parsed = _parsed_from_state(state)
    return "tools" if parsed.action else "end"


def build_graph(llm: Any | None = None):
    active_llm = llm or _create_default_llm()
    workflow = StateGraph(AgentState)
    workflow.add_node("agent_node", lambda state: agent_node(state, active_llm))
    workflow.add_node("tool_node", tool_node)
    workflow.add_edge(START, "agent_node")
    workflow.add_conditional_edges(
        "agent_node",
        should_continue,
        {"tools": "tool_node", "end": END},
    )
    workflow.add_edge("tool_node", "agent_node")
    return workflow.compile()
