from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional, Any, Dict
from contextvars import ContextVar

# ─────────────────────────────────────────────────────────────
# Context (only request_id)
# ─────────────────────────────────────────────────────────────

_request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def set_request_id(request_id: Optional[str]):
    _request_id_ctx.set(request_id)


def clear_request_id():
    _request_id_ctx.set(None)


# ─────────────────────────────────────────────────────────────
# JSON Formatter
# ─────────────────────────────────────────────────────────────

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.name,
            "file": record.filename,
            "line": record.lineno,
            "request_id": _request_id_ctx.get(),
        }

        if record.exc_info:
            import traceback
            log_data["stack_trace"] = traceback.format_exc()

        return json.dumps(log_data, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────
# Configure Logging
# ─────────────────────────────────────────────────────────────

def configure_logging(
    log_file: str = "app.log",
    level: int = logging.INFO,
):
    logger = logging.getLogger()
    logger.setLevel(level)

    formatter = JSONFormatter()

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.handlers = [file_handler, stream_handler]

    # Optional: reduce noisy libs
    noisy = ["httpx", "urllib3", "asyncio"]
    for name in noisy:
        logging.getLogger(name).setLevel(logging.WARNING)


# ─────────────────────────────────────────────────────────────
# Logger Wrapper (very thin now)
# ─────────────────────────────────────────────────────────────

class AppLogger:
    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def info(self, message: str, *args, **kwargs):
        self._logger.info(message, *args, stacklevel=2, **kwargs)

    def debug(self, message: str, *args, **kwargs):
        self._logger.debug(message, *args, stacklevel=2, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self._logger.warning(message, *args, stacklevel=2, **kwargs)

    def error(self, message: str, *args, exc_info: bool = False, **kwargs):
        self._logger.error(message, *args, exc_info=exc_info, stacklevel=2, **kwargs)

    def critical(self, message: str, *args, exc_info: bool = False, **kwargs):
        self._logger.critical(message, *args, exc_info=exc_info, stacklevel=2, **kwargs)


def get_logger(name: str) -> AppLogger:
    return AppLogger(name)
