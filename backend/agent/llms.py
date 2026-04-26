from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Callable

import httpx
from langchain_core.messages import AIMessage, BaseMessage


ProviderCall = Callable[[list[BaseMessage]], str]


@dataclass(frozen=True)
class FreeProvider:
    name: str
    call: ProviderCall


class FreeModelFallback:
    def __init__(self, providers: list[FreeProvider]):
        if not providers:
            raise RuntimeError(
                "No free model provider configured. Set GEMINI_API_KEY, GROQ_API_KEY, "
                "OPENROUTER_API_KEY, CF_ACCOUNT_ID + CF_WORKERS_AI_TOKEN, or "
                "GITHUB_MODELS_TOKEN + GITHUB_MODELS_MODEL."
            )
        self.providers = providers

    def invoke(self, messages: list[BaseMessage]) -> AIMessage:
        errors: list[str] = []
        for provider in self.providers:
            try:
                return AIMessage(content=provider.call(messages))
            except Exception as exc:
                errors.append(
                    f"{provider.name}: {type(exc).__name__}: {_safe_exception_message(exc)}"
                )
        raise RuntimeError("All free model providers failed: " + " | ".join(errors)) from None


SECRET_ENV_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
SECRET_QUERY_PARAMS = ("key", "api_key", "token", "access_token")


def _configured_secret_values() -> set[str]:
    return {
        value
        for name, value in os.environ.items()
        if value
        and len(value) >= 8
        and any(marker in name.upper() for marker in SECRET_ENV_MARKERS)
    }


def _redact_secrets(text: str) -> str:
    redacted = text
    for secret in sorted(_configured_secret_values(), key=len, reverse=True):
        redacted = redacted.replace(secret, "[redacted]")

    query_params = "|".join(re.escape(param) for param in SECRET_QUERY_PARAMS)
    redacted = re.sub(
        rf"(?i)([?&](?:{query_params})=)[^&\s'\"<>]+",
        r"\1[redacted]",
        redacted,
    )
    redacted = re.sub(r"(?i)(Bearer\s+)[^\s'\"<>]+", r"\1[redacted]", redacted)
    return redacted


def _safe_exception_message(exc: Exception) -> str:
    return _redact_secrets(str(exc))


def _raise_for_status(response: httpx.Response, provider_name: str) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        reason = exc.response.reason_phrase
        detail = _redact_secrets(exc.response.text[:500]).strip()
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
    return "user"


def _openai_compatible_messages(messages: list[BaseMessage]) -> list[dict[str, str]]:
    return [
        {"role": _role_for_message(message), "content": str(message.content)}
        for message in messages
    ]


def _gemini_prompt(messages: list[BaseMessage]) -> str:
    return "\n\n".join(
        f"{_role_for_message(message).upper()}: {message.content}" for message in messages
    )


def _call_gemini(messages: list[BaseMessage]) -> str:
    api_key = os.environ["GEMINI_API_KEY"]
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {"contents": [{"role": "user", "parts": [{"text": _gemini_prompt(messages)}]}]}
    response = httpx.post(url, params={"key": api_key}, json=payload, timeout=60)
    _raise_for_status(response, "gemini")
    data = response.json()
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(part.get("text", "") for part in parts).strip()


def _call_groq(messages: list[BaseMessage]) -> str:
    headers = {"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}
    payload = {
        "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "messages": _openai_compatible_messages(messages),
        "temperature": 0,
    }
    response = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    _raise_for_status(response, "groq")
    return response.json()["choices"][0]["message"]["content"].strip()


def _call_openrouter(messages: list[BaseMessage]) -> str:
    headers = {
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost"),
        "X-Title": os.getenv("OPENROUTER_APP_NAME", "01-react-agent"),
    }
    payload = {
        "model": os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free"),
        "messages": _openai_compatible_messages(messages),
        "temperature": 0,
    }
    response = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    _raise_for_status(response, "openrouter")
    return response.json()["choices"][0]["message"]["content"].strip()


def _call_cloudflare(messages: list[BaseMessage]) -> str:
    account_id = os.environ["CF_ACCOUNT_ID"]
    token = os.environ["CF_WORKERS_AI_TOKEN"]
    model = os.getenv("CF_WORKERS_AI_MODEL", "@cf/meta/llama-3-8b-instruct")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"messages": _openai_compatible_messages(messages)}
    response = httpx.post(url, headers=headers, json=payload, timeout=60)
    _raise_for_status(response, "cloudflare_workers_ai")
    data = response.json()
    return data["result"]["response"].strip()


def _call_github_models(messages: list[BaseMessage]) -> str:
    headers = {
        "Authorization": f"Bearer {os.environ['GITHUB_MODELS_TOKEN']}",
        "Accept": "application/vnd.github+json",
    }
    payload = {
        "model": os.environ["GITHUB_MODELS_MODEL"],
        "messages": _openai_compatible_messages(messages),
        "temperature": 0,
    }
    response = httpx.post(
        "https://models.github.ai/inference/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    _raise_for_status(response, "github_models")
    return response.json()["choices"][0]["message"]["content"].strip()


def configured_free_providers() -> list[FreeProvider]:
    providers: list[FreeProvider] = []
    if os.getenv("GEMINI_API_KEY"):
        providers.append(FreeProvider("gemini", _call_gemini))
    if os.getenv("GROQ_API_KEY"):
        providers.append(FreeProvider("groq", _call_groq))
    if os.getenv("GITHUB_MODELS_TOKEN") and os.getenv("GITHUB_MODELS_MODEL"):
        providers.append(FreeProvider("github_models", _call_github_models))
    if os.getenv("OPENROUTER_API_KEY"):
        providers.append(FreeProvider("openrouter", _call_openrouter))
    if os.getenv("CF_ACCOUNT_ID") and os.getenv("CF_WORKERS_AI_TOKEN"):
        providers.append(FreeProvider("cloudflare_workers_ai", _call_cloudflare))
    return providers
