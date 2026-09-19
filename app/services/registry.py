"""In-memory registry of named upstream conditions.

Storage is process memory only: nothing survives a restart and nothing is
persisted to disk or a database. A re-entrant lock guards registration so
concurrent requests cannot interleave; reads are safe under CPython's GIL
but go through the lock anyway for a clear consistency contract.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Iterable

from app import config, errors


@dataclass(frozen=True)
class CaseCondition:
    name: str
    mach1: float
    gamma: float
    p1: float | None = None
    t1: float | None = None
    gas_constant: float | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "mach1": self.mach1,
            "gamma": self.gamma,
            "p1": self.p1,
            "t1": self.t1,
            "gas_constant": self.gas_constant,
        }


class CaseRegistry:
    def __init__(self) -> None:
        self._cases: dict[str, CaseCondition] = {}
        self._lock = threading.RLock()

    def register(
        self,
        name: str,
        mach1: float,
        gamma: float,
        p1: float | None = None,
        t1: float | None = None,
        gas_constant: float | None = None,
        *,
        overwrite: bool = False,
    ) -> CaseCondition:
        name = self._validate_name(name)
        condition = CaseCondition(
            name=name,
            mach1=mach1,
            gamma=gamma,
            p1=p1,
            t1=t1,
            gas_constant=gas_constant,
        )
        with self._lock:
            if not overwrite and name in self._cases:
                raise errors.CaseAlreadyExists(
                    f"case {name!r} is already registered"
                )
            self._cases[name] = condition
        return condition

    def get(self, name: str) -> CaseCondition:
        key = self._validate_name(name)
        with self._lock:
            condition = self._cases.get(key)
        if condition is None:
            raise errors.CaseNotFound(f"no case registered under name {name!r}")
        return condition

    def list(self) -> list[CaseCondition]:
        with self._lock:
            return list(self._cases.values())

    def count(self) -> int:
        with self._lock:
            return len(self._cases)

    def clear(self) -> None:
        """Drop all cases (test isolation)."""
        with self._lock:
            self._cases.clear()

    def seed(self, conditions: Iterable[tuple[str, dict]]) -> None:
        """Idempotently load built-in cases (used at startup)."""
        for name, payload in conditions:
            self.register(name, overwrite=True, **payload)

    @staticmethod
    def _validate_name(name: object) -> str:
        if not isinstance(name, str):
            raise errors.CaseNameInvalid("case name must be a string")
        stripped = name.strip()
        if not stripped:
            raise errors.CaseNameInvalid("case name must not be empty")
        if len(stripped) > config.MAX_CASE_NAME_LENGTH:
            raise errors.CaseNameInvalid(
                f"case name must be at most {config.MAX_CASE_NAME_LENGTH} chars"
            )
        return stripped


# Process-wide singleton used by the routes.
registry = CaseRegistry()
