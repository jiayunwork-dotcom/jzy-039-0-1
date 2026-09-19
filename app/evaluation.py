"""Single evaluation pipeline shared by every endpoint.

One-shot evaluation, named-case evaluation and batch evaluation ALL funnel
through ``evaluate_conditions`` so a given (M1, gamma) can never produce
different answers depending on which HTTP route was used.
"""
from __future__ import annotations

from typing import Any

from app import shock, validation


def evaluate_conditions(
    mach: Any,
    gamma: Any,
    static_pressure: Any = None,
    static_temperature: Any = None,
) -> dict:
    """Validate inputs, solve the shock, and serialize the full result.

    Raises validation.ShockInputError subclasses on any invalid input;
    callers (routes) convert those into structured error responses.
    """
    mach_f = validation.validate_mach(mach)
    gamma_f = validation.validate_gamma(gamma)
    p1 = validation.validate_static_quantity(static_pressure, "static_pressure")
    t1 = validation.validate_static_quantity(static_temperature, "static_temperature")

    solution = shock.solve(mach_f, gamma_f)

    result: dict[str, Any] = {
        "input": {
            "mach": mach_f,
            "gamma": gamma_f,
            "static_pressure": p1,
            "static_temperature": t1,
        },
        "ratios": {
            "mach_downstream": solution.mach_downstream,
            "pressure_ratio": solution.pressure_ratio,
            "density_ratio": solution.density_ratio,
            "temperature_ratio": solution.temperature_ratio,
            "total_pressure_ratio": solution.total_pressure_ratio,
            "total_temperature_ratio": solution.total_temperature_ratio,
        },
    }

    if p1 is not None and t1 is not None:
        dim = shock.solve_dimensional(solution, p1, t1)
        result["dimensional"] = {
            "upstream": _side_to_dict(dim.upstream),
            "downstream": _side_to_dict(dim.downstream),
        }
    return result


def _side_to_dict(side: shock.SideState) -> dict:
    return {
        "pressure": side.pressure,
        "temperature": side.temperature,
        "density": side.density,
        "speed_of_sound": side.speed_of_sound,
        "velocity": side.velocity,
        "mass_flux": side.mass_flux,
        "total_pressure": side.total_pressure,
        "total_temperature": side.total_temperature,
    }
