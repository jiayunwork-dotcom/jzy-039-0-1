"""Acceptance checks against the closed-form normal-shock table values."""

from __future__ import annotations

import math

import pytest

from app.physics import shock, stagnation
from app.services import evaluator

GAMMA = 1.4


def test_closed_form_m2_gamma14():
    """M1=2, gamma=1.4 must match the hand-computable gas-table values."""
    s = shock.shock_ratios(2.0, GAMMA)

    assert s.mach2 == pytest.approx(math.sqrt(1.0 / 3.0), abs=1e-12)  # 0.57735
    assert s.pressure_ratio == pytest.approx(4.5, abs=1e-12)
    assert s.density_ratio == pytest.approx(8.0 / 3.0, abs=1e-12)  # 2.66667
    assert s.temperature_ratio == pytest.approx(27.0 / 16.0, abs=1e-12)  # 1.6875
    assert s.total_pressure_ratio == pytest.approx(0.7208738614847, abs=1e-9)


def test_ratios_are_mutually_consistent():
    """The five relations must hold together at an arbitrary M1, not just M1=2."""
    m1, g = 3.0, 1.4
    m1sq = m1 * m1
    s = shock.shock_ratios(m1, g)

    rho_r = (g + 1) * m1sq / ((g - 1) * m1sq + 2)
    p_r = 1 + 2 * g * (m1sq - 1) / (g + 1)
    t_r = p_r / rho_r
    m2sq = (1 + 0.5 * (g - 1) * m1sq) / (g * m1sq - 0.5 * (g - 1))

    assert s.density_ratio == pytest.approx(rho_r, rel=1e-14)
    assert s.pressure_ratio == pytest.approx(p_r, rel=1e-14)
    assert s.temperature_ratio == pytest.approx(t_r, rel=1e-14)
    assert s.mach2 * s.mach2 == pytest.approx(m2sq, rel=1e-14)
    # Temperature ratio is pressure ratio over density ratio — same sources.
    assert s.temperature_ratio == pytest.approx(
        s.pressure_ratio / s.density_ratio, rel=1e-14
    )


def test_mach_one_limit_all_ratios_approach_one():
    """As M1 -> 1 from above, every jump ratio and M2 approach 1."""
    s = shock.shock_ratios(1.0 + 1e-9, GAMMA)
    assert s.mach2 == pytest.approx(1.0, abs=1e-6)
    assert s.pressure_ratio == pytest.approx(1.0, abs=1e-6)
    assert s.temperature_ratio == pytest.approx(1.0, abs=1e-6)
    assert s.density_ratio == pytest.approx(1.0, abs=1e-6)
    assert s.total_pressure_ratio == pytest.approx(1.0, abs=1e-6)


def test_directionality_pressure_up_mach_down():
    """As M1 grows, p2/p1 and T2/T1 rise while M2 falls."""
    machs = [1.2, 1.5, 2.0, 3.0, 5.0, 10.0]
    solutions = [shock.shock_ratios(m, GAMMA) for m in machs]

    for prev, nxt in zip(solutions, solutions[1:]):
        assert nxt.pressure_ratio > prev.pressure_ratio
        assert nxt.temperature_ratio > prev.temperature_ratio
        assert nxt.density_ratio > prev.density_ratio
        assert nxt.mach2 < prev.mach2
        assert nxt.total_pressure_ratio < prev.total_pressure_ratio


def test_downstream_mach_limit():
    """M2 tends to sqrt((gamma-1)/(2 gamma)) for strong shocks."""
    limit = math.sqrt((GAMMA - 1) / (2 * GAMMA))
    s = shock.shock_ratios(10_000.0, GAMMA)
    assert s.mach2 == pytest.approx(limit, rel=1e-6)
    # ... and is subsonic everywhere finite.
    assert s.mach2 < 1.0


def test_density_ratio_upper_bound_follows_gamma():
    """The density-ratio ceiling (gamma+1)/(gamma-1) changes with gamma."""
    for g, expected in [(1.4, 6.0), (5.0 / 3.0, 4.0), (1.1, 21.0)]:
        bound = (g + 1) / (g - 1)
        strong = shock.shock_ratios(100_000.0, g)
        assert strong.density_ratio == pytest.approx(bound, rel=1e-4)
        # Finite shocks never quite reach it.
        assert shock.shock_ratios(2.0, g).density_ratio < bound


def test_compression_not_expansion():
    """Across the shock density and pressure rise, velocity drops, M2 < 1."""
    for m1 in (1.01, 1.5, 2.0, 5.0):
        s = shock.shock_ratios(m1, GAMMA)
        assert s.density_ratio > 1.0
        assert s.pressure_ratio > 1.0
        assert s.temperature_ratio > 1.0
        assert s.mach2 < 1.0
        # u2/u1 = (rho1/rho2) = 1/(rho ratio): the flow is slowed down.
        assert 1.0 / s.density_ratio < 1.0


def test_gamma_enters_both_density_and_mach2():
    """Changing gamma while fixing M1 must move both the density jump and M2."""
    a = shock.shock_ratios(3.0, 1.4)
    b = shock.shock_ratios(3.0, 1.667)
    assert a.density_ratio != pytest.approx(b.density_ratio)
    assert a.mach2 != pytest.approx(b.mach2)
    # Recomputed independently from the stated closed forms.
    g = 1.667
    m1sq = 9.0
    assert b.density_ratio == pytest.approx(
        (g + 1) * m1sq / ((g - 1) * m1sq + 2), rel=1e-12
    )
    assert b.mach2 ** 2 == pytest.approx(
        (1 + 0.5 * (g - 1) * m1sq) / (g * m1sq - 0.5 * (g - 1)), rel=1e-12
    )


def test_total_temperature_conserved_and_mass_flux_equal():
    """Dimensional evaluation: T0 across the shock is conserved and rho*u matches."""
    sol = evaluator.evaluate(2.0, 1.4, p1=101_325.0, t1=288.15)
    assert sol.dimensional is True

    up, down = sol.upstream, sol.downstream
    # Total temperature unchanged across the discontinuity.
    assert down.total_temperature == pytest.approx(
        up.total_temperature, rel=1e-12
    )
    assert sol.total_temperature_ratio == 1.0

    # Static post-shock state comes from RH jumps (not isentropic p01).
    assert down.pressure == pytest.approx(up.pressure * 4.5, rel=1e-12)
    assert down.temperature == pytest.approx(
        up.temperature * (27.0 / 16.0), rel=1e-12
    )

    # Mass flux rho*u equal on both sides (continuity through the shock).
    assert down.mass_flux == pytest.approx(up.mass_flux, rel=1e-10)

    # Total pressure drops.
    assert down.total_pressure < up.total_pressure
    assert down.total_pressure / up.total_pressure == pytest.approx(
        sol.total_pressure_ratio, rel=1e-12
    )


def test_mass_flux_matches_a_and_velocity():
    """rho*u = p/(R T) * M * sqrt(gamma R T), equal both sides."""
    sol = evaluator.evaluate(3.0, 1.4, p1=50_000.0, t1=250.0, gas_constant=287.053)
    for state, m in ((sol.upstream, 3.0), (sol.downstream, sol.mach2)):
        a = math.sqrt(1.4 * 287.053 * state.temperature)
        rho = state.pressure / (287.053 * state.temperature)
        assert state.speed_of_sound == pytest.approx(a, rel=1e-12)
        assert state.velocity == pytest.approx(m * a, rel=1e-12)
        assert state.mass_flux == pytest.approx(rho * m * a, rel=1e-10)


def test_dimensionless_mode_has_no_dimensional_block():
    """With ratios only, no dimensional block is fabricated."""
    sol = evaluator.evaluate(2.0, 1.4)
    assert sol.dimensional is False
    assert sol.upstream is None and sol.downstream is None
    assert sol.gas_constant is None


def test_rankine_hugoniot_conservation_laws_hold():
    """The jump solution must satisfy mass, momentum and energy conservation.

    Working with dimensionless states (p1=T1=1, R=1) so numbers are direct:
      mass:   rho1 u1 = rho2 u2
      momentum: p1 + rho1 u1^2 = p2 + rho2 u2^2
      energy: h0 (cp T0) equal both sides
    """
    R = g = 1.4
    sol = evaluator.evaluate(2.5, g, p1=1.0, t1=1.0, gas_constant=R)
    up, dn = sol.upstream, sol.downstream

    # mass
    assert up.mass_flux == pytest.approx(dn.mass_flux, rel=1e-12)
    # momentum flux p + rho u^2
    assert up.pressure + up.density * up.velocity ** 2 == pytest.approx(
        dn.pressure + dn.density * dn.velocity ** 2, rel=1e-12
    )
    # stagnation enthalpy cp T0, cp = gamma R/(gamma-1) -> compare T0 directly
    assert up.total_temperature == pytest.approx(dn.total_temperature, rel=1e-12)


def test_postshock_state_not_built_from_isentropic_crossing():
    """p2 must be the RH jump, not p01 expanded isentropically to M2."""
    m1, g = 2.0, 1.4
    sol = evaluator.evaluate(m1, g, p1=1.0, t1=1.0, gas_constant=1.4)
    pi_m2 = stagnation.total_pressure_ratio(sol.mach2, g)
    isentropic_crossing = sol.upstream.total_pressure / pi_m2
    # The forbidden construction gives a different (wrong) p2.
    assert isentropic_crossing != pytest.approx(sol.downstream.pressure, rel=1e-6)
    assert sol.downstream.pressure == pytest.approx(4.5, rel=1e-12)
