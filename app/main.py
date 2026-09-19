"""ASGI entry point: app wiring, exception handlers, startup seeding."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import config
from app.api import router
from app.errors import ServiceError, error_body
from app.services.registry import registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.started_at = time.monotonic()

    def _uptime() -> float:
        return time.monotonic() - app.state.started_at

    app.state.uptime = _uptime

    # Hand-checkable case: M1=2, gamma=1.4.
    registry.seed([(config.SEED_CASE_NAME, dict(config.SEED_CASE_CONDITION))])

    yield


app = FastAPI(
    title=config.SERVICE_NAME,
    version=config.SERVICE_VERSION,
    description="Rankine-Hugoniot normal-shock calculation service",
    lifespan=lifespan,
)

app.include_router(router)


@app.exception_handler(ServiceError)
async def _service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=error_body(exc))


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Framework-level shape errors get the same structured envelope rather
    # than leaking a raw stack trace or an empty object.
    detail = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in detail.get("loc", [])) or "request"
    message = f"{location}: {detail.get('msg', 'invalid request')}"
    body = {"error": {"code": "INVALID_REQUEST", "message": message}}
    return JSONResponse(status_code=422, content=body)


@app.exception_handler(Exception)
async def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Last-resort guard: never leak an uncaught exception as a 500 stack page.
    body = {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": f"unexpected error: {type(exc).__name__}",
        }
    }
    return JSONResponse(status_code=500, content=body)
