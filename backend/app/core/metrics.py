"""Prometheus metrics: a small request middleware + a mountable /metrics app."""
import time

from prometheus_client import Counter, Histogram, make_asgi_app
from starlette.types import ASGIApp, Receive, Scope, Send

REQUESTS = Counter("jarvis_http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("jarvis_http_request_seconds", "HTTP request latency", ["method", "path"])

metrics_app = make_asgi_app()


class MetricsMiddleware:
    """Pure-ASGI middleware so it never touches FastAPI route internals."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = scope.get("method", "GET")
        path = scope.get("path", "")
        status_holder = {"code": 500}

        async def _send(message) -> None:
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
            await send(message)

        start = time.perf_counter()
        try:
            await self.app(scope, receive, _send)
        finally:
            LATENCY.labels(method, path).observe(time.perf_counter() - start)
            REQUESTS.labels(method, path, status_holder["code"]).inc()
