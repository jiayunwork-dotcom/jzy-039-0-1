"""Isentropic stagnation relations.

Used *on each side of the shock independently* to lift a static state to its
stagnation state. Never used to jump across the discontinuity: the post-shock
static pressure comes from the Rankine-Hugoniot momentum relation, not from
an isentropic expansion off the upstream total pressure.
"""

from __future__ import annotations


def total_temperature_ratio(mach: float, gamma: float) -> float:
    """T0/T for an isentropic flow: 1 + (gamma-1)/2 * M^2."""
    return 1.0 + 0.5 * (gamma - 1.0) * mach * mach


def total_pressure_ratio(mach: float, gamma: float) -> float:
    """p0/p for an isentropic flow: (1 + (gamma-1)/2 * M^2) ** (gamma/(gamma-1))."""
    return total_temperature_ratio(mach, gamma) ** (gamma / (gamma - 1.0))


def speed_of_sound(temperature: float, gamma: float, gas_constant: float) -> float:
    """a = sqrt(gamma * R * T)."""
    return (gamma * gas_constant * temperature) ** 0.5
