"""HTTP routes: case registry, evaluation, batch, health.

Thin layer: parse -> registry/validation -> evaluation.evaluate_conditions
-> serialize. No physics lives here.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app import evaluation, validation
from app.registry import CaseRegistry, FlowCase
from app.schemas import BatchRequest, CaseRegistration, FlowConditions

router = APIRouter()
_STARTED_AT = time.monotonic()


def _registry(request: Request) -> CaseRegistry:
    return request.app.state.registry


def _error_response(status_code: int, exc: validation.ShockInputError) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"type": exc.error_type, "message": exc.message}},
    )


def error_status(exc: validation.ShockInputError) -> int:
    if isinstance(exc, validation.UnknownCaseError):
        return status.HTTP_404_NOT_FOUND
    if isinstance(exc, validation.DuplicateCaseError):
        return status.HTTP_409_CONFLICT
    return 422


@router.get("/health")
def health(request: Request) -> dict:
    registry = _registry(request)
    return {
        "status": "ok",
        "service": "normal-shock-service",
        "uptime_seconds": round(time.monotonic() - _STARTED_AT, 3),
        "cases_registered": registry.count(),
    }


@router.post("/cases", status_code=status.HTTP_201_CREATED)
def register_case(payload: CaseRegistration, request: Request) -> dict:
    name = validation.validate_case_name(payload.name)
    case = FlowCase(
        name=name,
        mach=validation.validate_mach(payload.mach),
        gamma=validation.validate_gamma(payload.gamma),
        static_pressure=validation.validate_static_quantity(
            payload.static_pressure, "static_pressure"
        ),
        static_temperature=validation.validate_static_quantity(
            payload.static_temperature, "static_temperature"
        ),
    )
    _registry(request).register(case)
    return {"registered": _case_to_dict(case)}


@router.get("/cases")
def list_cases(request: Request) -> dict:
    cases = _registry(request).list()
    return {"count": len(cases), "cases": [_case_to_dict(c) for c in cases]}


@router.get("/cases/{name}/result")
def evaluate_case(name: str, request: Request) -> dict:
    case = _registry(request).get(name)
    result = evaluation.evaluate_conditions(
        case.mach, case.gamma, case.static_pressure, case.static_temperature
    )
    return {"case": case.name, "result": result}


@router.post("/evaluate")
def evaluate_once(payload: FlowConditions) -> dict:
    return evaluation.evaluate_conditions(
        payload.mach, payload.gamma, payload.static_pressure, payload.static_temperature
    )


@router.post("/batch")
def evaluate_batch(payload: BatchRequest) -> dict:
    """Evaluate a list of Mach numbers; one bad item fails only itself."""
    gamma = payload.gamma
    machs = payload.machs
    if not isinstance(machs, list) or not machs:
        raise validation.ShockInputError("'machs' must be a non-empty list of Mach numbers")

    results = []
    for index, mach in enumerate(machs):
        try:
            results.append(
                {
                    "index": index,
                    "mach": mach,
                    "ok": True,
                    "result": evaluation.evaluate_conditions(
                        mach, gamma, payload.static_pressure, payload.static_temperature
                    ),
                }
            )
        except validation.ShockInputError as exc:
            results.append(
                {
                    "index": index,
                    "mach": mach,
                    "ok": False,
                    "error": {"type": exc.error_type, "message": exc.message},
                }
            )
    succeeded = sum(1 for r in results if r["ok"])
    return {"total": len(results), "succeeded": succeeded, "failed": len(results) - succeeded, "results": results}


def _case_to_dict(case: FlowCase) -> dict:
    return {
        "name": case.name,
        "mach": case.mach,
        "gamma": case.gamma,
        "static_pressure": case.static_pressure,
        "static_temperature": case.static_temperature,
    }
