"""Input validation with typed, structured errors.

Every invalid input is rejected BEFORE any computation happens, by raising
a ShockInputError subclass. The HTTP layer turns these into structured
JSON error bodies; nothing here raises bare exceptions or returns empties.
"""
from __future__ import annotations


class ShockInputError(Exception):
    """Base class for all rejected inputs. Carries a stable error type."""

    error_type: str = "invalid_input"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class MissingMachError(ShockInputError):
    error_type = "missing_mach"


class InvalidMachError(ShockInputError):
    error_type = "invalid_mach"


class InvalidGammaError(ShockInputError):
    error_type = "invalid_gamma"


class InvalidStaticQuantityError(ShockInputError):
    error_type = "invalid_static_quantity"


class UnknownCaseError(ShockInputError):
    error_type = "unknown_case"


class DuplicateCaseError(ShockInputError):
    error_type = "duplicate_case"


def _is_finite_number(value: object) -> bool:
    import math

    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_mach(mach: object) -> float:
    """Upstream Mach must be present, numeric, finite and strictly > 1."""
    if mach is None:
        raise MissingMachError("upstream Mach number 'mach' is required")
    if not _is_finite_number(mach):
        raise InvalidMachError(f"upstream Mach number must be a finite number, got {mach!r}")
    mach_f = float(mach)
    if mach_f <= 1.0:
        raise InvalidMachError(
            f"a normal shock requires supersonic inflow: mach={mach_f} is not > 1"
        )
    return mach_f


def validate_gamma(gamma: object) -> float:
    """Specific-heat ratio must be present, numeric, finite and strictly > 1."""
    if gamma is None:
        raise InvalidGammaError("specific-heat ratio 'gamma' is required")
    if not _is_finite_number(gamma):
        raise InvalidGammaError(f"gamma must be a finite number, got {gamma!r}")
    gamma_f = float(gamma)
    if gamma_f <= 1.0:
        raise InvalidGammaError(f"gamma must be > 1, got {gamma_f}")
    return gamma_f


def validate_static_quantity(value: object, field: str) -> float | None:
    """Optional dimensional static pressure/temperature must be positive."""
    if value is None:
        return None
    if not _is_finite_number(value) or float(value) <= 0.0:
        raise InvalidStaticQuantityError(
            f"'{field}' must be a positive finite number when supplied, got {value!r}"
        )
    return float(value)


def validate_case_name(name: object) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ShockInputError("case name must be a non-empty string")
    return name.strip()
