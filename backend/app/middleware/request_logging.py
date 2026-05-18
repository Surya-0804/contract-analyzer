"""
Request logging middleware.

Logs every incoming request with:
- A unique request ID (X-Request-ID header, generated if absent)
- Client IP address (respects X-Forwarded-For behind a reverse proxy)
- HTTP method, path, status code, and response time in ms
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_utils import get_logger, set_request_id, clear_request_id

logger = get_logger(__name__)


def _get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting proxy headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class RequestLoggingMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        client_ip = _get_client_ip(request)
        start = time.perf_counter()
        set_request_id(request_id)
        try:
            logger.info(
                f"req_start | {request.method} {request.url.path} | "
                f"client={client_ip} | request_id={request_id}"
            )

            response: Response = await call_next(request)

            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

            logger.info(
                f"req_end   | {request.method} {request.url.path} | "
                f"status={response.status_code} | {elapsed_ms}ms | "
                f"client={client_ip} | request_id={request_id}"
            )

            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            clear_request_id()