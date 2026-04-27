from __future__ import annotations

import logging
import os
import re
from typing import Any


REDACTION = "[redacted]"
SECRET_ENV_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
SECRET_QUERY_PARAMS = ("key", "api_key", "token", "access_token")

_BASE_LOG_RECORD_FACTORY = logging.getLogRecordFactory()
_INSTALLED = False


def configured_secret_values() -> set[str]:
    return {
        value
        for name, value in os.environ.items()
        if value
        and len(value) >= 8
        and any(marker in name.upper() for marker in SECRET_ENV_MARKERS)
    }


def redact_secrets(value: object) -> str:
    text = str(value)
    redacted = text
    for secret in sorted(configured_secret_values(), key=len, reverse=True):
        redacted = redacted.replace(secret, REDACTION)

    query_params = "|".join(re.escape(param) for param in SECRET_QUERY_PARAMS)
    redacted = re.sub(
        rf"(?i)([?&](?:{query_params})=)[^&\s'\"<>]+",
        rf"\1{REDACTION}",
        redacted,
    )
    redacted = re.sub(r"(?i)(Bearer\s+)[^\s'\"<>]+", rf"\1{REDACTION}", redacted)
    return redacted


def _redacting_log_record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
    record = _BASE_LOG_RECORD_FACTORY(*args, **kwargs)
    original_get_message = record.getMessage

    def get_redacted_message() -> str:
        try:
            message = original_get_message()
        except Exception:
            message = f"{record.msg} {record.args}"
        return redact_secrets(message)

    record.getMessage = get_redacted_message  # type: ignore[method-assign]
    return record


def install_secret_redaction() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    logging.setLogRecordFactory(_redacting_log_record_factory)
    _INSTALLED = True


def configure_secure_logging(level: int = logging.INFO) -> None:
    install_secret_redaction()
    logging.basicConfig(level=level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
