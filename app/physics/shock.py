"""Rankine-Hugoniot kernel for a single normal shock.

Pure functions of (M1, gamma); input is assumed already validated
(see :mod:`app.physics.validation`). All five relations are derived from the
same M1^2/gamma and are mutually consistent — they are not computed
independently from separate sources:

    r = rho2/rho1 = (gamma+1) M1^2 / ((gamma-1) M1^2 + 2)
    p = p2/p1     = 1 + 2 gamma (M1^2 - 1) / (gamma + 1)
    t = T2/T1     = p / r
    M2^2          = (1 + (gamma-1)/2 M1^2) / (gamma M1^2 - (gamma-1)/2)

Note gamma enters *both* the density ratio and the downstream Mach number.
For M1 > 1 and gamma > 1: r > 1 (compression, never expansion), p > 1,
t > 1 and M2 < 1.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import stagnation


@dataclass(frozen=True)
class ShockRatios:
    """Dimensionless result across one normal shock."""

    mach1: float
    mach2: float
    pressure_ratio: float  # p2/p1
    temperature_ratio: float  # T2/T1
    density_ratio: float  # rho2/rho1
    total_pressure_ratio: float  # p02/p01 across the shock


def density_ratio(mach1: float, gamma: float) -> float:
    """rho2/rho1 = (gamma+1) M1^2 / ((gamma-1) M1^2 + 2).

    Monotone increasing in M1^2, bounded above by (gamma+1)/(gamma-1).
    """
    m2 = mach1 * mach1
    return (gamma + 1.0) * m2 / ((gamma - 1.0) * m2 + 2.0)


def pressure_ratio(mach1: float, gamma: float) -> float:
    """p2/p1 = 1 + 2 gamma (M1^2 - 1) / (gamma + 1)."""
    m2 = mach1 * mach1
    return 1.0 + 2.0 * gamma * (m2 - 1.0) / (gamma + 1.0)


def temperature_ratio(mach1: float, gamma: float) -> float:
    """T2/T1 = (p2/p1) / (rho2/rho1) — never an independent formula."""
    return pressure_ratio(mach1, gamma) / density_ratio(mach1, gamma)


def downstream_mach_squared(mach1: float, gamma: float) -> float:
    """M2^2 = (1 + (gamma-1)/2 M1^2) / (gamma M1^2 - (gamma-1)/2)."""
    m2 = mach1 * mach1
    return (1.0 + 0.5 * (gamma - 1.0) * m2) / (
        gamma * m2 - 0.5 * (gamma - 1.0)
    )


def downstream_mach(mach1: float, gamma: float) -> float:
    """M2 = sqrt(M2^2); positive root, the physical downstream Mach number."""
    return downstream_mach_squared(mach1, gamma) ** 0.5


def total_pressure_recovery(mach1: float, gamma: float) -> float:
    """p02/p01 across the shock.

    Each side is lifted static->total by its *own* isentropic factor:
        p01 = p1 * pi(M1), p02 = p2 * pi(M2),  pi(M) = p0/p isentropic.
    Hence p02/p01 = (p2/p1) * pi(M2) / pi(M1).
    """
    pr = pressure_ratio(mach1, gamma)
    m2 = downstream_mach(mach1, gamma)
    return (
        pr
        * stagnation.total_pressure_ratio(m2, gamma)
        / stagnation.total_pressure_ratio(mach1, gamma)
    )


def shock_ratios(mach1: float, gamma: float) -> ShockRatios:
    """Evaluate the whole, mutually consistent set of shock ratios."""
    rho_r = density_ratio(mach1, gamma)
    p_r = pressure_ratio(mach1, gamma)
    t_r = p_r / rho_r
    m2 = downstream_mach(mach1, gamma)
    p0_r = (
        p_r
        * stagnation.total_pressure_ratio(m2, gamma)
        / stagnation.total_pressure_ratio(mach1, gamma)
    )
    return ShockRatios(
        mach1=mach1,
        mach2=m2,
        pressure_ratio=p_r,
        temperature_ratio=t_r,
        density_ratio=rho_r,
        total_pressure_ratio=p0_r,
    )
