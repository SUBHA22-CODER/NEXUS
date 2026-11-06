"""FastAPI application entry point."""
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from .api import router
from .config import get_settings
from .db import fail_interrupted_investigations, init_db

REQUESTS = Counter("nexus_http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram("nexus_http_request_seconds", "HTTP request latency", ["route"])


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    fail_interrupted_investigations()
    yield


app = FastAPI(title="NEXUS", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    # The route template, not the raw path, so ids cannot blow up metric cardinality.
    route = getattr(request.scope.get("route"), "path", "unmatched")
    REQUESTS.labels(request.method, route, response.status_code).inc()
    LATENCY.labels(route).observe(time.perf_counter() - started)
    return response


app.include_router(router)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
