"""HTTP request schemas (Pydantic v2).

Numbers are allowed to be absent at the schema layer so missing-field cases
reach the domain validator and come back with the service's own typed errors
(e.g. ``MACH_MISSING``) instead of a generic framework error.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class EvaluateRequest(BaseModel):
    mach1: Optional[float] = Field(default=None, description="upstream Mach number M1 > 1")
    gamma: Optional[float] = Field(default=None, description="ratio of specific heats > 1")
    p1: Optional[float] = Field(default=None, description="upstream static pressure (Pa)")
    t1: Optional[float] = Field(default=None, description="upstream static temperature (K)")
    R: Optional[float] = Field(default=None, description="specific gas constant, J/(kg K)")


class CaseCreateRequest(BaseModel):
    name: str = Field(..., description="registered case name")
    mach1: Optional[float] = None
    gamma: Optional[float] = None
    p1: Optional[float] = None
    t1: Optional[float] = None
    R: Optional[float] = None


class BatchRequest(BaseModel):
    gamma: Optional[float] = Field(default=None, description="shared ratio of specific heats")
    machs: list[float] = Field(..., description="upstream Mach numbers to evaluate")
    p1: Optional[float] = None
    t1: Optional[float] = None
    R: Optional[float] = None
