from __future__ import annotations

import logging
from contextvars import ContextVar
from datetime import datetime
from typing import Optional

# ─────────────────────────────────────────────────────────────
# Context (only request_id)
# ─────────────────────────────────────────────────────────────

_request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def set_request_id(request_id: Optional[str]):
    _request_id_ctx.set(request_id)


def clear_request_id():
    _request_id_ctx.set(None)


def _format_context() -> str:
    request_id = _request_id_ctx.get()
    return f"[REQUEST_ID: {request_id}]" if request_id else ""


# ─────────────────────────────────────────────────────────────
# JSON Formatter
# ─────────────────────────────────────────────────────────────

class RequestFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.request_id = _request_id_ctx.get() or "-"
        record.asctime = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        message = super().format(record)
        if record.exc_info:
            message = f"{message}\n{self.formatException(record.exc_info)}"
        return message


# ─────────────────────────────────────────────────────────────
# Configure Logging
# ─────────────────────────────────────────────────────────────

def configure_logging(
    log_file: str = "app.log",
    level: int = logging.INFO,
):
    logger = logging.getLogger()
    logger.setLevel(level)

    formatter = RequestFormatter(
        fmt="%(asctime)s - %(levelname)s - %(message)s - File:%(filename)s - Line:%(lineno)d"
    )

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

    def _msg(self, message: str) -> str:
        context = _format_context()
        return f"{context} {message}" if context else message

    def info(self, message: str, *args, stacklevel: int = 2, **kwargs):
        self._logger.info(self._msg(message), *args, stacklevel=stacklevel, **kwargs)

    def debug(self, message: str, *args, stacklevel: int = 2, **kwargs):
        self._logger.debug(self._msg(message), *args, stacklevel=stacklevel, **kwargs)

    def warning(self, message: str, *args, stacklevel: int = 2, **kwargs):
        self._logger.warning(self._msg(message), *args, stacklevel=stacklevel, **kwargs)

    def error(
        self,
        message: str,
        *args,
        exc_info: bool = False,
        stacklevel: int = 2,
        **kwargs,
    ):
        self._logger.error(
            self._msg(message), *args, exc_info=exc_info, stacklevel=stacklevel, **kwargs
        )

    def critical(
        self,
        message: str,
        *args,
        exc_info: bool = False,
        stacklevel: int = 2,
        **kwargs,
    ):
        self._logger.critical(
            self._msg(message), *args, exc_info=exc_info, stacklevel=stacklevel, **kwargs
        )


def get_logger(name: str) -> AppLogger:
    return AppLogger(name)
