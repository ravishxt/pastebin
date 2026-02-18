from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from flask import Flask, g, request


class _RequestContextFilter(logging.Filter):
    """
    Logging filter that enriches records with request-scoped information.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        try:
            record.correlation_id = getattr(g, "correlation_id", None)
            record.http_method = getattr(request, "method", None)
            record.http_path = getattr(request, "path", None)
        except RuntimeError:
            # No active request context; leave values as-is or None.
            record.correlation_id = getattr(record, "correlation_id", None)
        return True


class JsonFormatter(logging.Formatter):
    """
    Simple JSON log formatter for structured logging.
    """

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        log: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Common structured fields we care about.
        for key in (
            "event",
            "correlation_id",
            "http_method",
            "http_path",
            "paste_id",
            "status_from",
            "status_to",
            "error_type",
        ):
            value = getattr(record, key, None)
            if value is not None:
                log[key] = value

        if record.exc_info:
            log["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(log, ensure_ascii=False)


def get_correlation_id() -> str | None:
    """
    Return the current request's correlation_id, if any.
    """

    try:
        return getattr(g, "correlation_id", None)
    except RuntimeError:
        return None


def _configure_logging() -> None:
    """
    Configure application-wide structured JSON logging.
    """

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    # Replace existing handlers to avoid duplicate logs.
    root.handlers = [handler]
    root.addFilter(_RequestContextFilter())


def init_observability(app: Flask) -> None:
    """
    Initialize observability for the Flask app.

    - Configures JSON logging.
    - Sets up per-request correlation IDs.
    """

    _configure_logging()

    @app.before_request
    def _set_correlation_id() -> None:  # type: ignore[unused-variable]
        incoming = request.headers.get("X-Correlation-ID")
        g.correlation_id = incoming or str(uuid4())

    @app.after_request
    def _propagate_correlation_id(response):  # type: ignore[unused-variable]
        cid = get_correlation_id()
        if cid:
            response.headers["X-Correlation-ID"] = cid
        return response

