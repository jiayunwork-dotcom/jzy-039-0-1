"""Application assembly: app factory, typed-error handler, seed case."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import routes, validation
from app.registry import CaseRegistry, FlowCase

# Pre-registered hand-checkable reference case: M1 = 2, gamma = 1.4.
SEED_CASE = FlowCase(
    name="m2_gamma14",
    mach=2.0,
    gamma=1.4,
    static_pressure=101325.0,
    static_temperature=288.15,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Normal Shock Service",
        version="1.0.0",
        description="Rankine-Hugoniot normal-shock calculator with named flow cases.",
    )
    app.state.registry = CaseRegistry()
    app.state.registry.register(SEED_CASE)

    @app.exception_handler(validation.ShockInputError)
    async def shock_input_error_handler(
        request: Request, exc: validation.ShockInputError
    ) -> JSONResponse:
        return routes._error_response(routes.error_status(exc), exc)

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "type": "malformed_request",
                    "message": "request body could not be parsed",
                }
            },
        )

    app.include_router(routes.router)
    return app


app = create_app()
