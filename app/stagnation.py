"""Isentropic stagnation (total) relations.

These relations are only ever applied on ONE side of the shock at a time:
upstream static -> upstream total, and downstream static -> downstream total.
They are never used to jump across the discontinuity itself.
"""
from __future__ import annotations

# Specific gas constant for dry air [J/(kg*K)], used only when dimensional
# static pressure/temperature are supplied.
GAS_CONSTANT_AIR = 287.05


def total_temperature_over_static(mach: float, gamma: float) -> float:
    """T0/T = 1 + (gamma-1)/2 * M^2  (isentropic, single side of the shock)."""
    return 1.0 + 0.5 * (gamma - 1.0) * mach * mach


def total_pressure_over_static(mach: float, gamma: float) -> float:
    """p0/p = (1 + (gamma-1)/2 * M^2)^(gamma/(gamma-1))  (isentropic)."""
    return total_temperature_over_static(mach, gamma) ** (gamma / (gamma - 1.0))


def speed_of_sound(temperature: float, gamma: float) -> float:
    """a = sqrt(gamma * R * T)."""
    return (gamma * GAS_CONSTANT_AIR * temperature) ** 0.5
