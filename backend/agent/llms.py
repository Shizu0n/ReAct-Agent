from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from agent.redaction import redact_secrets


# A provider takes the conversation plus optional OpenAI-style tool schemas and
# returns an AIMessage. The message may carry tool_calls (native function
# calling) or just text content.
ProviderCall = Callable[[list[BaseMessage], list[dict] | None], AIMessage]


@dataclass(frozen=True)
class FreeProvider:
    name: str
    call: ProviderCall


@dataclass(frozen=True)
class ModelInfo:
    provider: str
    provider_label: str
    model: str
    label: str


class FreeModelFallback:
    def __init__(self, providers: list[FreeProvider]):
        if not providers:
            raise RuntimeError(
                "No free model provider configured. Set GEMINI_API_KEY, GROQ_API_KEY, "
                "or GITHUB_MODELS_TOKEN + GITHUB_MODELS_MODEL."
            )
        self.providers = providers

    def invoke(
        self, messages: list[BaseMessage], tools: list[dict] | None = None
    ) -> AIMessage:
        errors: list[str] = []
        for provider in self.providers:
            try:
                return provider.call(messages, tools)
            except Exception as exc:
                errors.append(
                    f"{provider.name}: {type(exc).__name__}: {_safe_exception_message(exc)}"
                )
        raise RuntimeError(
            "All free model providers failed: " + " | ".join(errors)
        ) from None


def load_model_environment() -> None:
    if os.getenv("REACT_AGENT_SKIP_DOTENV") != "1":
        load_dotenv()


def _model_label(provider_label: str, model: str) -> str:
    if model.startswith("gemini-"):
        model_name = model.removeprefix("gemini-").replace("-", " ").title()
        return f"{provider_label} {model_name}"
    return f"{provider_label} {model}"


def configured_model_info() -> list[ModelInfo]:
    load_model_environment()

    models: list[ModelInfo] = []
    if os.getenv("GEMINI_API_KEY"):
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        models.append(
            ModelInfo("gemini", "Gemini", model, _model_label("Gemini", model))
        )
    if os.getenv("GROQ_API_KEY"):
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        models.append(ModelInfo("groq", "Groq", model, _model_label("Groq", model)))
    if os.getenv("GITHUB_MODELS_TOKEN") and os.getenv("GITHUB_MODELS_MODEL"):
        model = os.environ["GITHUB_MODELS_MODEL"]
        models.append(
            ModelInfo(
                "github_models",
                "GitHub Models",
                model,
                _model_label("GitHub Models", model),
            )
        )
    return models


def _safe_exception_message(exc: Exception) -> str:
    return redact_secrets(exc)


def _raise_for_status(response: httpx.Response, provider_name: str) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        reason = exc.response.reason_phrase
        detail = redact_secrets(exc.response.text[:500]).strip()
        message = f"{provider_name} request failed with HTTP {status} {reason}"
        if detail:
            message = f"{message}: {detail}"
        raise RuntimeError(message) from None


def _role_for_message(message: BaseMessage) -> str:
    message_type = getattr(message, "type", "human")
    if message_type == "system":
        return "system"
    if message_type == "ai":
        return "assistant"
    if message_type == "tool":
        return "tool"
    return "user"


def _openai_messages(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    """Render the conversation in OpenAI chat-completions format, including
    assistant tool_calls and tool result messages."""
    rendered: list[dict[str, Any]] = []
    for message in messages:
        role = _role_for_message(message)
        if isinstance(message, ToolMessage):
            rendered.append(
                {
                    "role": "tool",
                    "tool_call_id": message.tool_call_id,
                    "content": str(message.content),
                }
            )
            continue

        entry: dict[str, Any] = {"role": role, "content": str(message.content)}
        tool_calls = getattr(message, "tool_calls", None)
        if role == "assistant" and tool_calls:
            entry["tool_calls"] = [
                {
                    "id": call.get("id") or f"call_{index}",
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call.get("args", {})),
                    },
                }
                for index, call in enumerate(tool_calls)
            ]
        rendered.append(entry)
    return rendered


def _usage_metadata(usage: dict[str, Any] | None) -> dict[str, int]:
    usage = usage or {}
    input_tokens = int(usage.get("prompt_tokens", 0) or 0)
    output_tokens = int(usage.get("completion_tokens", 0) or 0)
    total = int(usage.get("total_tokens", input_tokens + output_tokens) or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
    }


def _ai_message_from_openai(
    message: dict[str, Any],
    usage: dict[str, Any] | None = None,
    response_metadata: dict[str, Any] | None = None,
) -> AIMessage:
    content = message.get("content") or ""
    raw_tool_calls = message.get("tool_calls") or []
    tool_calls: list[dict[str, Any]] = []
    for index, call in enumerate(raw_tool_calls):
        function = call.get("function", {})
        raw_args = function.get("arguments") or "{}"
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
        except json.JSONDecodeError:
            args = {"__raw__": raw_args}
        tool_calls.append(
            {
                "name": function.get("name", ""),
                "args": args,
                "id": call.get("id") or f"call_{index}",
            }
        )
    return AIMessage(
        content=str(content),
        tool_calls=tool_calls,
        usage_metadata=_usage_metadata(usage),
        response_metadata=response_metadata or {},
    )


def _extract_first_json_object(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : index + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _is_unsupported_temperature(response: httpx.Response) -> bool:
    """OpenAI's gpt-5 / o-series models (served via GitHub Models) reject any
    non-default temperature with HTTP 400. Detect that specific error so the
    request can be retried without the temperature field instead of failing."""
    try:
        error = response.json().get("error", {})
    except (ValueError, AttributeError):
        return False
    return (
        error.get("param") == "temperature"
        and error.get("code") == "unsupported_value"
    )


def _recover_tool_use_failed(response: httpx.Response) -> AIMessage | None:
    """Some OpenAI-compatible providers (notably Groq's llama models) return
    HTTP 400 tool_use_failed when the model emits a function call in a
    non-standard <function=name{...}> wire format. The intended call is in
    error.failed_generation; parse it back into a proper tool call."""
    try:
        error = response.json().get("error", {})
    except (ValueError, AttributeError):
        return None
    if error.get("code") != "tool_use_failed":
        return None

    generation = str(error.get("failed_generation", ""))
    match = re.search(r"<function=([A-Za-z_]\w*)", generation)
    if not match:
        return None
    args = _extract_first_json_object(generation[match.end():])
    if args is None:
        return None
    return AIMessage(
        content="",
        tool_calls=[{"name": match.group(1), "args": args, "id": "recovered_0"}],
        usage_metadata=_usage_metadata(None),
    )


@dataclass(frozen=True)
class OpenAICompatProvider:
    name: str
    url: str
    model_env: str
    model_default: str
    headers_factory: Callable[[], dict[str, str]]
    extra_payload: dict[str, Any] | None = None

    def model(self) -> str:
        return os.getenv(self.model_env, self.model_default)

    def __call__(
        self, messages: list[BaseMessage], tools: list[dict] | None
    ) -> AIMessage:
        payload: dict[str, Any] = {
            "model": self.model(),
            "messages": _openai_messages(messages),
            "temperature": 0,
        }
        if self.extra_payload:
            payload.update(self.extra_payload)
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        started = time.perf_counter()
        response = httpx.post(
            self.url, headers=self.headers_factory(), json=payload, timeout=60
        )
        metadata = {
            "provider": self.name,
            "model": self.model(),
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }
        if response.status_code == 400 and tools:
            recovered = _recover_tool_use_failed(response)
            if recovered is not None:
                recovered.response_metadata = metadata
                return recovered
        if response.status_code == 400 and _is_unsupported_temperature(response):
            payload.pop("temperature", None)
            started = time.perf_counter()
            response = httpx.post(
                self.url, headers=self.headers_factory(), json=payload, timeout=60
            )
            metadata["latency_ms"] = round((time.perf_counter() - started) * 1000)
        _raise_for_status(response, self.name)
        data = response.json()
        choice = data["choices"][0]
        message = _ai_message_from_openai(
            choice["message"], data.get("usage"), metadata
        )
        # An HTTP 200 with empty content and no tool call is not a usable answer
        # (Gemini does this under quota pressure or safety/recitation stops).
        # Treat it as a provider failure so the fallback chain tries the next one
        # instead of returning a blank "success" to the user.
        if not str(message.content).strip() and not message.tool_calls:
            finish_reason = choice.get("finish_reason", "unknown")
            raise RuntimeError(
                f"{self.name} returned an empty completion "
                f"(finish_reason={finish_reason})"
            )
        return message


def _gemini_provider() -> OpenAICompatProvider:
    return OpenAICompatProvider(
        name="gemini",
        url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        model_env="GEMINI_MODEL",
        model_default="gemini-2.5-flash",
        headers_factory=lambda: {
            "Authorization": f"Bearer {os.environ['GEMINI_API_KEY']}"
        },
    )


def _groq_provider() -> OpenAICompatProvider:
    return OpenAICompatProvider(
        name="groq",
        url="https://api.groq.com/openai/v1/chat/completions",
        model_env="GROQ_MODEL",
        model_default="llama-3.3-70b-versatile",
        headers_factory=lambda: {
            "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"
        },
    )


def _github_models_provider() -> OpenAICompatProvider:
    return OpenAICompatProvider(
        name="github_models",
        url="https://models.github.ai/inference/chat/completions",
        model_env="GITHUB_MODELS_MODEL",
        model_default="openai/gpt-4o-mini",
        headers_factory=lambda: {
            "Authorization": f"Bearer {os.environ['GITHUB_MODELS_TOKEN']}",
            "Accept": "application/vnd.github+json",
        },
    )


def configured_free_providers() -> list[FreeProvider]:
    load_model_environment()

    providers: list[FreeProvider] = []
    if os.getenv("GEMINI_API_KEY"):
        providers.append(FreeProvider("gemini", _gemini_provider()))
    if os.getenv("GROQ_API_KEY"):
        providers.append(FreeProvider("groq", _groq_provider()))
    if os.getenv("GITHUB_MODELS_TOKEN") and os.getenv("GITHUB_MODELS_MODEL"):
        providers.append(FreeProvider("github_models", _github_models_provider()))
    return providers


# Approximate public list prices (USD per 1M tokens) for the underlying models,
# used only to estimate what a run would cost at paid rates. Free-tier usage is
# billed at $0; this is an at-scale reference, not an invoice.
MODEL_PRICING_USD_PER_1M: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.30, 2.50),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "openai/gpt-4o-mini": (0.15, 0.60),
}


def _estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    input_price, output_price = MODEL_PRICING_USD_PER_1M.get(model, (0.0, 0.0))
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


class UsageTracker:
    """Collects per-call token usage, latency, and estimated cost across a run."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def record(self, message: AIMessage) -> None:
        usage = getattr(message, "usage_metadata", None) or {}
        metadata = getattr(message, "response_metadata", None) or {}
        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)
        model = str(metadata.get("model", ""))
        self.calls.append(
            {
                "provider": metadata.get("provider", ""),
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": int(usage.get("total_tokens", input_tokens + output_tokens)),
                "latency_ms": int(metadata.get("latency_ms", 0) or 0),
                "estimated_cost_usd": _estimate_cost_usd(model, input_tokens, output_tokens),
            }
        )

    def summary(self) -> dict[str, Any]:
        return {
            "llm_calls": len(self.calls),
            "input_tokens": sum(c["input_tokens"] for c in self.calls),
            "output_tokens": sum(c["output_tokens"] for c in self.calls),
            "total_tokens": sum(c["total_tokens"] for c in self.calls),
            "estimated_cost_usd": round(
                sum(c["estimated_cost_usd"] for c in self.calls), 6
            ),
            "providers": list(
                dict.fromkeys(c["provider"] for c in self.calls if c["provider"])
            ),
        }


class UsageTrackingLLM:
    """Wraps an llm, recording each call's usage into a UsageTracker."""

    def __init__(self, llm: Any, tracker: UsageTracker) -> None:
        self._llm = llm
        self._tracker = tracker

    def invoke(self, messages: list[BaseMessage], tools: list[dict] | None = None) -> AIMessage:
        message = self._llm.invoke(messages, tools)
        self._tracker.record(message)
        return message
