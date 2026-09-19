"""Typed, structured errors.

Illegal input is rejected *before* any physics is computed. Every service
error carries a stable machine-readable ``code`` and an HTTP status; the
exception handlers in :mod:`app.main` render them as::

    {"error": {"code": "...", "message": "..."}}
"""

from __future__ import annotations


class ServiceError(Exception):
    """Base class for all errors raised by the service."""

    code: str = "SERVICE_ERROR"
    status_code: int = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class MachMissing(ServiceError):
    code = "MACH_MISSING"
    status_code = 422


class MachNotSupersonic(ServiceError):
    code = "MACH_NOT_SUPERSONIC"
    status_code = 422


class GammaInvalid(ServiceError):
    code = "GAMMA_INVALID"
    status_code = 422


class NonFiniteNumber(ServiceError):
    code = "NON_FINITE_NUMBER"
    status_code = 422


class DimensionalInputInvalid(ServiceError):
    code = "DIMENSIONAL_INPUT_INVALID"
    status_code = 422


class CaseNameInvalid(ServiceError):
    code = "CASE_NAME_INVALID"
    status_code = 422


class CaseNotFound(ServiceError):
    code = "CASE_NOT_FOUND"
    status_code = 404


class CaseAlreadyExists(ServiceError):
    code = "CASE_ALREADY_EXISTS"
    status_code = 409


class EmptyBatch(ServiceError):
    code = "EMPTY_BATCH"
    status_code = 422


class BatchTooLarge(ServiceError):
    code = "BATCH_TOO_LARGE"
    status_code = 422


def error_body(exc: ServiceError) -> dict:
    """Render a :class:`ServiceError` into the canonical error envelope."""
    return {"error": {"code": exc.code, "message": exc.message}}
