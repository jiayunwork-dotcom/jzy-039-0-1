"""Input validation — every illegal condition is rejected before solving."""

from __future__ import annotations

import math
from typing import Any

from app import errors


def _is_real_number(value: Any) -> bool:
    """True for real, finite numbers (bools are not valid flow numbers)."""
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def require_mach(mach1: Any) -> float:
    """Validate the upstream Mach number is present, finite and supersonic."""
    if mach1 is None:
        raise errors.MachMissing("missing upstream Mach number 'mach1'")
    if not _is_real_number(mach1):
        raise errors.NonFiniteNumber("'mach1' must be a finite number")
    if float(mach1) <= 1.0:
        # A normal shock requires supersonic upstream flow; M1 == 1 is the
        # degenerate limit, not a standing shock.
        raise errors.MachNotSupersonic(
            f"upstream Mach number must be > 1, got {mach1}"
        )
    return float(mach1)


def require_gamma(gamma: Any) -> float:
    """Validate the ratio of specific heats is finite and > 1."""
    if gamma is None:
        raise errors.GammaInvalid("missing ratio of specific heats 'gamma'")
    if not _is_real_number(gamma):
        raise errors.NonFiniteNumber("'gamma' must be a finite number")
    if float(gamma) <= 1.0:
        raise errors.GammaInvalid(
            f"ratio of specific heats must be > 1, got {gamma}"
        )
    return float(gamma)


def require_positive(name: str, value: Any) -> float:
    """Validate an optional dimensional quantity is finite and strictly > 0."""
    if value is None:
        raise errors.DimensionalInputInvalid(f"'{name}' must not be null")
    if not _is_real_number(value):
        raise errors.DimensionalInputInvalid(
            f"'{name}' must be a finite positive number"
        )
    if float(value) <= 0.0:
        raise errors.DimensionalInputInvalid(
            f"'{name}' must be positive, got {value}"
        )
    return float(value)


def require_optional_positive(name: str, value: Any) -> float | None:
    """:func:`require_positive` that tolerates an absent (None) quantity."""
    if value is None:
        return None
    return require_positive(name, value)


def validate_condition(
    mach1: Any,
    gamma: Any,
    p1: Any = None,
    t1: Any = None,
    gas_constant: Any = None,
) -> tuple[float, float, float | None, float | None, float | None]:
    """Validate one set of upstream conditions.

    Dimensional inputs are all-or-nothing for static pressure/temperature:
    a non-positive value is rejected up front. ``gas_constant`` is only
    required when sound speed / velocity is reported.
    """
    m1 = require_mach(mach1)
    g = require_gamma(gamma)
    p = require_optional_positive("p1", p1)
    t = require_optional_positive("t1", t1)
    r = require_optional_positive("R", gas_constant)
    return m1, g, p, t, r
