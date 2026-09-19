"""In-memory registry of named flow cases.

A case binds a caller-chosen name to a set of inflow conditions
(mach, gamma, optional dimensional statics). Registrations live only in
process memory: no database, no persistence across restarts. A lock keeps
concurrent registrations/lookups from interleaving.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

from app import validation


@dataclass(frozen=True)
class FlowCase:
    name: str
    mach: float
    gamma: float
    static_pressure: float | None = None
    static_temperature: float | None = None


class CaseRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cases: dict[str, FlowCase] = {}

    def register(self, case: FlowCase) -> FlowCase:
        with self._lock:
            if case.name in self._cases:
                raise validation.DuplicateCaseError(
                    f"case '{case.name}' is already registered"
                )
            self._cases[case.name] = case
            return case

    def get(self, name: str) -> FlowCase:
        with self._lock:
            try:
                return self._cases[name]
            except KeyError:
                raise validation.UnknownCaseError(f"no case registered under name '{name}'")

    def list(self) -> list[FlowCase]:
        with self._lock:
            return sorted(self._cases.values(), key=lambda c: c.name)

    def count(self) -> int:
        with self._lock:
            return len(self._cases)
