"""Conversation-aware prompt suggestions.

A small, generic LLM pass (the "suggester") that looks at the recent
conversation plus the agent's available tools and proposes follow-up prompts.
It is deliberately tool-agnostic: the tool list is passed in at call time, so it
generalizes to any toolset instead of hardcoding rules for specific tools.

The suggester prefers its own provider (Groq by default) but falls back to any
other configured provider, mirroring the responder's fallback behaviour. Keeping
it on a different provider than the responder spreads free-tier quota and frees
the responder's provider for answering. Any failure degrades to a small generic
static list rather than surfacing an error.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from agent.llms import (
    FreeModelFallback,
    _extract_first_json_object,
    load_model_environment,
    providers_preferring,
)

logger = logging.getLogger("react_agent.suggestions")

MAX_SUGGESTIONS = 3
MAX_SUGGESTION_WORDS = 14
DEFAULT_SUGGESTER_PROVIDER = "groq"

# Generic fallback used when no provider is available or the suggester fails or
# returns nothing usable. Intentionally not tied to any specific tool.
FALLBACK_SUGGESTIONS = [
    "Probe the weakest assumption in the last answer",
    "Ask for the evidence or sources behind that answer",
    "Request one concrete next step based on this answer",
]

_SUGGESTER_SYSTEM_PROMPT = (
    "You generate follow-up prompt suggestions for the user of a tool-using AI "
    "agent. Given the recent conversation and the tools the agent can call, "
    "propose up to {count} short prompts the user could send next to go deeper, "
    "verify, or extend the last answer.\n"
    "Rules:\n"
    "- Each suggestion is a single imperative sentence, at most {max_words} words.\n"
    "- Make them specific to THIS conversation, not generic.\n"
    "- When relevant, prefer prompts that would exercise the agent's tools: {tools}.\n"
    "- Do not repeat a question the user already asked.\n"
    '- Output ONLY a JSON object: {{"suggestions": ["...", "..."]}}. No prose.'
)


def generate_suggestions(
    history: list[dict[str, str]],
    tools: list[str],
    tools_used: list[str] | None = None,
    llm: Any | None = None,
) -> list[str]:
    """Return up to MAX_SUGGESTIONS follow-up prompts for the conversation.

    `history` is a list of {"role", "content"} dicts. `tools` is the agent's full
    tool registry; `tools_used` (optional) are the tools the last run actually
    called. `llm` lets tests inject a scripted model. Never raises — falls back
    to FALLBACK_SUGGESTIONS on any error or empty conversation.
    """
    if not _has_content(history):
        return list(FALLBACK_SUGGESTIONS)

    try:
        active_llm = llm or _suggester_llm()
        messages = _build_messages(history, tools, tools_used or [])
        response = active_llm.invoke(messages, None)
    except Exception:
        logger.warning("Suggestion generation failed; using fallback", exc_info=True)
        return list(FALLBACK_SUGGESTIONS)

    parsed = _parse_suggestions(str(getattr(response, "content", "")))
    return parsed or list(FALLBACK_SUGGESTIONS)


def _suggester_llm() -> FreeModelFallback:
    load_model_environment()
    preferred = os.getenv("SUGGESTER_PROVIDER", DEFAULT_SUGGESTER_PROVIDER)
    return FreeModelFallback(providers_preferring(preferred))


def _build_messages(
    history: list[dict[str, str]], tools: list[str], tools_used: list[str]
) -> list[BaseMessage]:
    system = _SUGGESTER_SYSTEM_PROMPT.format(
        count=MAX_SUGGESTIONS,
        max_words=MAX_SUGGESTION_WORDS,
        tools=", ".join(tools) or "none",
    )
    parts = [f"Conversation so far:\n{_render_conversation(history)}"]
    if tools_used:
        parts.append(f"Tools the last answer used: {', '.join(tools_used)}.")
    parts.append("Return the JSON object now.")
    return [SystemMessage(content=system), HumanMessage(content="\n\n".join(parts))]


def _render_conversation(history: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for item in history[-8:]:
        content = (item.get("content") or "").strip()
        if not content:
            continue
        speaker = "User" if item.get("role") == "user" else "Agent"
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


def _parse_suggestions(text: str) -> list[str]:
    obj = _extract_first_json_object(text)
    if not isinstance(obj, dict):
        return []
    raw = obj.get("suggestions")
    if not isinstance(raw, list):
        return []

    seen: set[str] = set()
    result: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            result.append(cleaned)
    return result[:MAX_SUGGESTIONS]


def _has_content(history: list[dict[str, str]]) -> bool:
    return any((item.get("content") or "").strip() for item in history)
