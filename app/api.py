"""HTTP routes.

Thin adapters only: validation, the RH math, stagnation conversion and case
storage all live in their own modules. Single evaluation, named-case lookup
and batch evaluation share :func:`app.services.evaluator.evaluate`.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app import config
from app.errors import (
    BatchTooLarge,
    EmptyBatch,
    ServiceError,
    error_body,
)
from app.physics.validation import require_gamma, validate_condition
from app.schemas import BatchRequest, CaseCreateRequest, EvaluateRequest
from app.services import evaluator
from app.services.registry import registry

router = APIRouter()


@router.get("/")
def root() -> dict:
    return {
        "service": config.SERVICE_NAME,
        "version": config.SERVICE_VERSION,
        "description": "normal shock (Rankine-Hugoniot) calculation service",
        "endpoints": [
            "GET /healthz",
            "POST /shock/evaluate",
            "POST /shock/batch",
            "POST /cases",
            "GET /cases",
            "GET /cases/{name}",
        ],
    }


@router.get("/healthz")
def healthz(request: Request) -> dict:
    return {
        "status": "ok",
        "service": config.SERVICE_NAME,
        "version": config.SERVICE_VERSION,
        "uptime_seconds": round(request.app.state.uptime(), 6),
        "registered_cases": registry.count(),
    }


@router.post("/shock/evaluate")
def evaluate_shock(payload: EvaluateRequest) -> dict:
    solution = evaluator.evaluate(
        payload.mach1, payload.gamma, payload.p1, payload.t1, payload.R
    )
    return {"status": "ok", "solution": solution.to_dict()}


@router.post("/shock/batch")
def evaluate_batch(payload: BatchRequest) -> dict:
    """Evaluate a run of upstream Mach numbers for a shock polar.

    The shared gamma (and dimensional inputs) is checked once up front; each
    Mach number is evaluated independently through the *same* function as the
    single endpoint, so one bad entry fails alone and the rest still return.
    """
    if not payload.machs:
        raise EmptyBatch("'machs' must contain at least one Mach number")
    if len(payload.machs) > config.MAX_BATCH_SIZE:
        raise BatchTooLarge(
            f"batch size must be at most {config.MAX_BATCH_SIZE}, "
            f"got {len(payload.machs)}"
        )
    gamma = require_gamma(payload.gamma)

    results = []
    for mach in payload.machs:
        try:
            solution = evaluator.evaluate(
                mach, gamma, payload.p1, payload.t1, payload.R
            )
        except ServiceError as exc:
            results.append(
                {
                    "mach1": mach if isinstance(mach, (int, float)) else None,
                    "status": "error",
                    "error": error_body(exc)["error"],
                }
            )
        else:
            results.append(
                {
                    "mach1": solution.mach1,
                    "status": "ok",
                    "solution": solution.to_dict(),
                }
            )

    ok_count = sum(1 for item in results if item["status"] == "ok")
    return {
        "status": "ok",
        "gamma": gamma,
        "count": len(results),
        "succeeded": ok_count,
        "failed": len(results) - ok_count,
        "results": results,
    }


@router.post("/cases", status_code=201)
def register_case(payload: CaseCreateRequest) -> dict:
    # Validate flow inputs before anything is stored.
    m1, g, p, t, r = validate_condition(
        payload.mach1, payload.gamma, payload.p1, payload.t1, payload.R
    )
    condition = registry.register(payload.name, m1, g, p, t, r)
    return {"status": "registered", "case": condition.to_dict()}


@router.get("/cases")
def list_cases() -> dict:
    cases = [condition.to_dict() for condition in registry.list()]
    return {"count": len(cases), "cases": cases}


@router.get("/cases/{name}")
def get_case(name: str) -> dict:
    condition = registry.get(name)
    solution = evaluator.evaluate(
        condition.mach1,
        condition.gamma,
        condition.p1,
        condition.t1,
        condition.gas_constant,
    )
    return {
        "status": "ok",
        "case": condition.to_dict(),
        "solution": solution.to_dict(),
    }
