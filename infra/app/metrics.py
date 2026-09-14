"""Prometheus request metrics for the LyricStats API.

Records the three signals that the alerts and dashboard in infra/monitoring are
built on, per route and status:

  lyricstats_http_requests_total            counter    (rate, errors)
  lyricstats_http_request_duration_seconds  histogram  (latency)
  lyricstats_http_requests_in_flight        gauge      (saturation)

The route label is the path *template* (``/api/artist``), never the raw URL, so
the number of series stays bounded no matter what users type into the search
box. Requests that match no route share the label ``<unmatched>``.
"""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

UNMATCHED = "<unmatched>"

REQUESTS = Counter(
    "lyricstats_http_requests_total",
    "HTTP requests handled by the API.",
    ["method", "route", "status"],
)
LATENCY = Histogram(
    "lyricstats_http_request_duration_seconds",
    "Time from receiving a request to finishing its response.",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
IN_FLIGHT = Gauge(
    "lyricstats_http_requests_in_flight",
    "Requests currently being handled.",
)


class PrometheusMiddleware:
    """Pure ASGI middleware, so it sees the final status of every response,
    including the 500 produced when a handler raises."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        status = 500  # stays 500 if the app raises before starting a response

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        start = time.perf_counter()
        IN_FLIGHT.inc()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            IN_FLIGHT.dec()
            # The router stores the matched route on the shared scope, so it is
            # available here once the request has been handled.
            route = getattr(scope.get("route"), "path", None) or UNMATCHED
            method = scope["method"]
            REQUESTS.labels(method, route, str(status)).inc()
            LATENCY.labels(method, route).observe(time.perf_counter() - start)


async def metrics_endpoint(_request: Request) -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def instrument(app: Any) -> Any:
    """Add the middleware and a /metrics route to a FastAPI/Starlette app."""
    app.add_middleware(PrometheusMiddleware)
    app.add_route("/metrics", metrics_endpoint, include_in_schema=False)
    return app
