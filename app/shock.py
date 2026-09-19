"""Closed-form Rankine-Hugoniot normal-shock kernel.

All jump relations are evaluated as one consistent set from the same
(M1, gamma): density, pressure, temperature and downstream Mach all derive
from the same M1^2 and gamma, so they cannot drift apart.

  rho2/rho1 = (gamma+1) M1^2 / ((gamma-1) M1^2 + 2)
  p2/p1     = 1 + 2 gamma (M1^2 - 1) / (gamma+1)
  T2/T1     = (p2/p1) / (rho2/rho1)
  M2^2      = (1 + (gamma-1)/2 M1^2) / (gamma M1^2 - (gamma-1)/2)

Stagnation bookkeeping: total temperature is conserved across the shock
(T02 = T01); total pressure drops. The recovery factor p02/p01 is obtained
by isentropically raising each side's static state to its own total state
(see stagnation.py) -- never by an isentropic jump across the shock.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app import stagnation


@dataclass(frozen=True)
class ShockSolution:
    """Dimensionless Rankine-Hugoniot result for one (M1, gamma) pair."""

    mach_upstream: float
    gamma: float
    mach_downstream: float
    pressure_ratio: float           # p2/p1
    density_ratio: float            # rho2/rho1
    temperature_ratio: float        # T2/T1
    total_pressure_ratio: float     # p02/p01  (total-pressure recovery)
    total_temperature_ratio: float  # T02/T01  (identically 1 across a shock)


def density_ratio(mach1: float, gamma: float) -> float:
    """rho2/rho1 = (gamma+1) M1^2 / ((gamma-1) M1^2 + 2)."""
    m1_sq = mach1 * mach1
    return (gamma + 1.0) * m1_sq / ((gamma - 1.0) * m1_sq + 2.0)


def pressure_ratio(mach1: float, gamma: float) -> float:
    """p2/p1 = 1 + 2 gamma (M1^2 - 1) / (gamma+1)."""
    m1_sq = mach1 * mach1
    return 1.0 + 2.0 * gamma * (m1_sq - 1.0) / (gamma + 1.0)


def downstream_mach(mach1: float, gamma: float) -> float:
    """M2^2 = (1 + (gamma-1)/2 M1^2) / (gamma M1^2 - (gamma-1)/2)."""
    m1_sq = mach1 * mach1
    numerator = 1.0 + 0.5 * (gamma - 1.0) * m1_sq
    denominator = gamma * m1_sq - 0.5 * (gamma - 1.0)
    return math.sqrt(numerator / denominator)


@dataclass(frozen=True)
class SideState:
    """Dimensional static + stagnation state on one side of the shock."""

    pressure: float          # static p [Pa]
    temperature: float       # static T [K]
    density: float           # rho = p / (R T) [kg/m^3]
    speed_of_sound: float    # a = sqrt(gamma R T) [m/s]
    velocity: float          # u = M a [m/s]
    mass_flux: float         # rho * u [kg/(m^2 s)]
    total_pressure: float    # p0 [Pa]
    total_temperature: float # T0 [K]


@dataclass(frozen=True)
class DimensionalSolution:
    """Full dimensional state on both sides, built from a ShockSolution."""

    upstream: SideState
    downstream: SideState


def _side_state(pressure: float, temperature: float, mach: float, gamma: float) -> SideState:
    density = pressure / (stagnation.GAS_CONSTANT_AIR * temperature)
    a = stagnation.speed_of_sound(temperature, gamma)
    velocity = mach * a
    return SideState(
        pressure=pressure,
        temperature=temperature,
        density=density,
        speed_of_sound=a,
        velocity=velocity,
        mass_flux=density * velocity,
        total_pressure=pressure * stagnation.total_pressure_over_static(mach, gamma),
        total_temperature=temperature * stagnation.total_temperature_over_static(mach, gamma),
    )


def solve_dimensional(
    solution: ShockSolution, static_pressure: float, static_temperature: float
) -> DimensionalSolution:
    """Lift a dimensionless solution to full dimensional states.

    Upstream statics are the given inflow; downstream statics come from the
    jump ratios; each side's totals come from that side's own isentropic
    relations. Totals are never extrapolated across the shock isentropically.
    """
    up = _side_state(static_pressure, static_temperature, solution.mach_upstream, solution.gamma)
    down = _side_state(
        static_pressure * solution.pressure_ratio,
        static_temperature * solution.temperature_ratio,
        solution.mach_downstream,
        solution.gamma,
    )
    return DimensionalSolution(upstream=up, downstream=down)


def solve(mach1: float, gamma: float) -> ShockSolution:
    """Evaluate the full, mutually consistent set of jump relations."""
    rho_ratio = density_ratio(mach1, gamma)
    p_ratio = pressure_ratio(mach1, gamma)
    t_ratio = p_ratio / rho_ratio
    mach2 = downstream_mach(mach1, gamma)

    # Total pressure on each side via that side's own isentropic lift.
    p01_over_p1 = stagnation.total_pressure_over_static(mach1, gamma)
    p02_over_p2 = stagnation.total_pressure_over_static(mach2, gamma)
    # p02/p01 = (p02/p2) * (p2/p1) / (p01/p1)
    recovery = p02_over_p2 * p_ratio / p01_over_p1

    # Total temperature on each side; must come out equal across the shock.
    t01_over_t1 = stagnation.total_temperature_over_static(mach1, gamma)
    t02_over_t2 = stagnation.total_temperature_over_static(mach2, gamma)
    # T02/T01 = (T02/T2) * (T2/T1) / (T01/T1)
    total_t_ratio = t02_over_t2 * t_ratio / t01_over_t1

    return ShockSolution(
        mach_upstream=mach1,
        gamma=gamma,
        mach_downstream=mach2,
        pressure_ratio=p_ratio,
        density_ratio=rho_ratio,
        temperature_ratio=t_ratio,
        total_pressure_ratio=recovery,
        total_temperature_ratio=total_t_ratio,
    )
