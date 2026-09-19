"""Evaluation orchestration: validation -> RH kernel -> stagnation lift.

This is the single evaluation path shared by single-request evaluation,
named-case lookup and the batch window function, so the three can never
disagree at the same (M1, gamma).
"""

from __future__ import annotations

from dataclasses import dataclass

from app import config
from app.physics import shock, stagnation
from app.physics.validation import validate_condition


@dataclass(frozen=True)
class StaticState:
    pressure: float
    temperature: float
    density: float
    mach: float
    speed_of_sound: float
    velocity: float
    total_pressure: float
    total_temperature: float
    mass_flux: float  # rho * u [kg/(m^2 s)]


@dataclass(frozen=True)
class ShockSolution:
    mach1: float
    gamma: float
    mach2: float
    pressure_ratio: float
    temperature_ratio: float
    density_ratio: float
    total_pressure_ratio: float
    total_temperature_ratio: float  # always 1.0 across the shock
    dimensional: bool
    gas_constant: float | None
    upstream: StaticState | None
    downstream: StaticState | None

    def to_dict(self) -> dict:
        return {
            "mach1": self.mach1,
            "gamma": self.gamma,
            "mach2": self.mach2,
            "ratios": {
                "p2_p1": self.pressure_ratio,
                "t2_t1": self.temperature_ratio,
                "rho2_rho1": self.density_ratio,
                "p02_p01": self.total_pressure_ratio,
                "t02_t01": self.total_temperature_ratio,
            },
            "dimensional": self.dimensional,
            "gas_constant": self.gas_constant,
            "upstream": _state_to_dict(self.upstream),
            "downstream": _state_to_dict(self.downstream),
        }


def _state_to_dict(state: StaticState | None) -> dict | None:
    if state is None:
        return None
    return {
        "pressure": state.pressure,
        "temperature": state.temperature,
        "density": state.density,
        "mach": state.mach,
        "speed_of_sound": state.speed_of_sound,
        "velocity": state.velocity,
        "total_pressure": state.total_pressure,
        "total_temperature": state.total_temperature,
        "mass_flux": state.mass_flux,
    }


def _build_state(
    pressure: float,
    temperature: float,
    mach: float,
    gamma: float,
    gas_constant: float,
) -> StaticState:
    """Lift one static state to its stagnation state (same-side isentropic)."""
    density = pressure / (gas_constant * temperature)  # ideal gas p = rho R T
    a = stagnation.speed_of_sound(temperature, gamma, gas_constant)
    u = mach * a
    p0 = pressure * stagnation.total_pressure_ratio(mach, gamma)
    t0 = temperature * stagnation.total_temperature_ratio(mach, gamma)
    return StaticState(
        pressure=pressure,
        temperature=temperature,
        density=density,
        mach=mach,
        speed_of_sound=a,
        velocity=u,
        total_pressure=p0,
        total_temperature=t0,
        mass_flux=density * u,
    )


def evaluate(
    mach1: object,
    gamma: object,
    p1: object = None,
    t1: object = None,
    gas_constant: object = None,
) -> ShockSolution:
    """Evaluate one normal shock from (possibly dimensional) upstream input.

    Raises an :class:`app.errors.ServiceError` subclass before any RH
    arithmetic happens if the input is illegal.
    """
    m1, g, p, t, r = validate_condition(mach1, gamma, p1, t1, gas_constant)
    ratios = shock.shock_ratios(m1, g)

    upstream: StaticState | None = None
    downstream: StaticState | None = None
    dimensional = p is not None and t is not None

    if dimensional:
        R = r if r is not None else config.DEFAULT_GAS_CONSTANT
        # Downstream static state comes straight from the RH jumps —
        # never from an isentropic relation applied across the shock.
        upstream = _build_state(p, t, m1, g, R)
        downstream = _build_state(
            pressure=p * ratios.pressure_ratio,
            temperature=t * ratios.temperature_ratio,
            mach=ratios.mach2,
            gamma=g,
            gas_constant=R,
        )
        effective_r: float | None = R
    else:
        effective_r = None

    return ShockSolution(
        mach1=m1,
        gamma=g,
        mach2=ratios.mach2,
        pressure_ratio=ratios.pressure_ratio,
        temperature_ratio=ratios.temperature_ratio,
        density_ratio=ratios.density_ratio,
        total_pressure_ratio=ratios.total_pressure_ratio,
        # The energy jump condition: total temperature is conserved.
        total_temperature_ratio=1.0,
        dimensional=dimensional,
        gas_constant=effective_r,
        upstream=upstream,
        downstream=downstream,
    )
