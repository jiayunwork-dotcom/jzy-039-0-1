"""Pydantic request/response schemas.

Request fields are typed as ``object``/optional on purpose: raw payloads
flow through to app.validation so that EVERY malformed input (missing
mach, non-numeric gamma, negative pressure, ...) surfaces as our typed
structured error instead of a generic framework 422.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FlowConditions(BaseModel):
    mach: Any = None
    gamma: Any = None
    static_pressure: Any = None
    static_temperature: Any = None


class CaseRegistration(FlowConditions):
    name: Any = None


class BatchRequest(BaseModel):
    gamma: Any = None
    machs: Any = None  # expected: list of numbers; validated per item
    static_pressure: Any = None
    static_temperature: Any = None


class ErrorBody(BaseModel):
    type: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
