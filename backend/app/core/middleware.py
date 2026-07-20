"""HTTP middleware: correlation IDs, structured access logs, and metrics.

Each request is assigned (or inherits) a correlation id, which is bound to the
logging context and echoed back in the ``X-Correlation-ID`` response header and
in the error envelope.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import correlation_id_ctx, get_logger

logger = get_logger("http")

CORRELATION_HEADER = "X-Correlation-ID"

_REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
_REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency (seconds)",
    ["method", "path"],
)


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Bind a correlation id and emit a structured access log per request."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())
        token = correlation_id_ctx.set(correlation_id)
        route = request.scope.get("route")
        path_template = getattr(route, "path", request.url.path)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - start
            _REQUEST_COUNT.labels(request.method, path_template, status_code).inc()
            _REQUEST_LATENCY.labels(request.method, path_template).observe(elapsed)
            logger.info(
                "request",
                method=request.method,
                path=request.url.path,
                status=status_code,
                duration_ms=round(elapsed * 1000, 2),
            )
            # Response object only exists if call_next succeeded.
            if "response" in locals():
                response.headers[CORRELATION_HEADER] = correlation_id
            correlation_id_ctx.reset(token)
