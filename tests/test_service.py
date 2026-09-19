"""Physics invariants and API behaviour tests for the normal-shock service."""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

GAMMA = 1.4
R_AIR = 287.05


@pytest.fixture()
def client() -> TestClient:
    # Fresh app per test: in-memory registry starts with only the seed case.
    return TestClient(create_app())


# ---------------------------------------------------------------------------
# Closed-form reference values at M1 = 2, gamma = 1.4
# ---------------------------------------------------------------------------

def test_seed_case_matches_closed_form(client: TestClient) -> None:
    resp = client.get("/cases/m2_gamma14/result")
    assert resp.status_code == 200
    ratios = resp.json()["result"]["ratios"]

    m1, g = 2.0, 1.4
    m1_sq = m1 * m1
    expected_rho = (g + 1) * m1_sq / ((g - 1) * m1_sq + 2)          # 2.666666...
    expected_p = 1 + 2 * g * (m1_sq - 1) / (g + 1)                  # 4.5
    expected_t = expected_p / expected_rho                          # 1.6875
    expected_m2 = math.sqrt((1 + 0.5 * (g - 1) * m1_sq) / (g * m1_sq - 0.5 * (g - 1)))

    assert ratios["density_ratio"] == pytest.approx(expected_rho, rel=1e-12)
    assert ratios["pressure_ratio"] == pytest.approx(expected_p, rel=1e-12)
    assert ratios["temperature_ratio"] == pytest.approx(expected_t, rel=1e-12)
    assert ratios["mach_downstream"] == pytest.approx(expected_m2, rel=1e-12)
    assert ratios["mach_downstream"] == pytest.approx(0.5773503, rel=1e-6)
    assert ratios["total_pressure_ratio"] == pytest.approx(0.7208739, rel=1e-6)
    assert ratios["total_temperature_ratio"] == pytest.approx(1.0, abs=1e-12)


def test_seed_case_is_listed(client: TestClient) -> None:
    resp = client.get("/cases")
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()["cases"]]
    assert "m2_gamma14" in names


# ---------------------------------------------------------------------------
# Directional invariants
# ---------------------------------------------------------------------------

def test_pressure_ratio_rises_and_m2_falls_with_mach(client: TestClient) -> None:
    machs = [1.2, 1.5, 2.0, 3.0, 5.0]
    prev_p, prev_m2 = None, None
    for m in machs:
        ratios = client.post("/evaluate", json={"mach": m, "gamma": GAMMA}).json()["ratios"]
        if prev_p is not None:
            assert ratios["pressure_ratio"] > prev_p
            assert ratios["mach_downstream"] < prev_m2
        prev_p, prev_m2 = ratios["pressure_ratio"], ratios["mach_downstream"]


def test_weak_shock_limit_mach_approaches_one(client: TestClient) -> None:
    ratios = client.post("/evaluate", json={"mach": 1.000001, "gamma": GAMMA}).json()["ratios"]
    assert ratios["pressure_ratio"] == pytest.approx(1.0, abs=1e-4)
    assert ratios["density_ratio"] == pytest.approx(1.0, abs=1e-4)
    assert ratios["temperature_ratio"] == pytest.approx(1.0, abs=1e-4)
    assert ratios["mach_downstream"] == pytest.approx(1.0, abs=1e-3)


def test_strong_shock_asymptotes(client: TestClient) -> None:
    ratios = client.post("/evaluate", json={"mach": 1e6, "gamma": GAMMA}).json()["ratios"]
    m2_limit = math.sqrt((GAMMA - 1) / (2 * GAMMA))
    rho_limit = (GAMMA + 1) / (GAMMA - 1)
    assert ratios["mach_downstream"] == pytest.approx(m2_limit, rel=1e-3)
    assert ratios["density_ratio"] == pytest.approx(rho_limit, rel=1e-3)


def test_density_ratio_limit_tracks_gamma(client: TestClient) -> None:
    for g in (1.2, 1.4, 1.667):
        ratios = client.post("/evaluate", json={"mach": 1e6, "gamma": g}).json()["ratios"]
        assert ratios["density_ratio"] == pytest.approx((g + 1) / (g - 1), rel=1e-3)


def test_compression_not_expansion(client: TestClient) -> None:
    """Density ratio numerator/denominator must not be flipped."""
    for m in (1.1, 2.0, 4.0, 10.0):
        ratios = client.post("/evaluate", json={"mach": m, "gamma": GAMMA}).json()["ratios"]
        assert ratios["density_ratio"] > 1.0, "shock must compress"
        assert ratios["pressure_ratio"] > 1.0
        assert ratios["temperature_ratio"] > 1.0
        assert ratios["mach_downstream"] < 1.0, "post-shock flow must be subsonic"
        assert ratios["total_pressure_ratio"] < 1.0, "total pressure must drop"


# ---------------------------------------------------------------------------
# Stagnation bookkeeping
# ---------------------------------------------------------------------------

def test_total_temperature_constant_across_shock(client: TestClient) -> None:
    resp = client.post(
        "/evaluate",
        json={"mach": 2.5, "gamma": GAMMA, "static_pressure": 50000.0, "static_temperature": 250.0},
    )
    dim = resp.json()["dimensional"]
    assert dim["upstream"]["total_temperature"] == pytest.approx(
        dim["downstream"]["total_temperature"], rel=1e-9
    )
    assert dim["downstream"]["total_pressure"] < dim["upstream"]["total_pressure"]


def test_mass_flux_conserved_across_shock(client: TestClient) -> None:
    """rho*u must match on both sides, using a = sqrt(gamma R T), u = M a."""
    p1, t1, m1 = 80000.0, 270.0, 3.0
    resp = client.post(
        "/evaluate",
        json={"mach": m1, "gamma": GAMMA, "static_pressure": p1, "static_temperature": t1},
    )
    body = resp.json()
    dim = body["dimensional"]
    assert dim["upstream"]["mass_flux"] == pytest.approx(
        dim["downstream"]["mass_flux"], rel=1e-9
    )

    # Independent recomputation from the raw ratios and sqrt(gamma R T).
    r = body["ratios"]
    p2, t2 = p1 * r["pressure_ratio"], t1 * r["temperature_ratio"]
    rho1, rho2 = p1 / (R_AIR * t1), p2 / (R_AIR * t2)
    u1 = m1 * math.sqrt(GAMMA * R_AIR * t1)
    u2 = r["mach_downstream"] * math.sqrt(GAMMA * R_AIR * t2)
    assert rho1 * u1 == pytest.approx(rho2 * u2, rel=1e-9)


def test_downstream_totals_consistent_with_isentropic_lift(client: TestClient) -> None:
    """p02 must equal p2 lifted isentropically at M2 -- not p01 carried over."""
    resp = client.post(
        "/evaluate",
        json={"mach": 2.0, "gamma": GAMMA, "static_pressure": 101325.0, "static_temperature": 288.15},
    )
    body = resp.json()
    dim, r = body["dimensional"], body["ratios"]
    m2 = r["mach_downstream"]
    lift = (1 + 0.5 * (GAMMA - 1) * m2 * m2) ** (GAMMA / (GAMMA - 1))
    assert dim["downstream"]["total_pressure"] == pytest.approx(
        dim["downstream"]["pressure"] * lift, rel=1e-12
    )
    # And the recovery coefficient ties the two totals together.
    assert dim["downstream"]["total_pressure"] / dim["upstream"]["total_pressure"] == pytest.approx(
        r["total_pressure_ratio"], rel=1e-12
    )


# ---------------------------------------------------------------------------
# Input validation: typed structured errors, no 500s, no empty bodies
# ---------------------------------------------------------------------------

def test_subsonic_mach_rejected(client: TestClient) -> None:
    for m in (0.5, 1.0):
        resp = client.post("/evaluate", json={"mach": m, "gamma": GAMMA})
        assert resp.status_code == 422
        assert resp.json()["error"]["type"] == "invalid_mach"


def test_gamma_at_or_below_one_rejected(client: TestClient) -> None:
    for g in (1.0, 0.9, -2.0):
        resp = client.post("/evaluate", json={"mach": 2.0, "gamma": g})
        assert resp.status_code == 422
        assert resp.json()["error"]["type"] == "invalid_gamma"


def test_missing_mach_rejected(client: TestClient) -> None:
    resp = client.post("/evaluate", json={"gamma": GAMMA})
    assert resp.status_code == 422
    assert resp.json()["error"]["type"] == "missing_mach"


def test_nonpositive_statics_rejected(client: TestClient) -> None:
    resp = client.post(
        "/evaluate",
        json={"mach": 2.0, "gamma": GAMMA, "static_pressure": -1.0, "static_temperature": 300.0},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["type"] == "invalid_static_quantity"
    resp = client.post(
        "/evaluate",
        json={"mach": 2.0, "gamma": GAMMA, "static_pressure": 1e5, "static_temperature": 0.0},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["type"] == "invalid_static_quantity"


def test_unknown_case_rejected(client: TestClient) -> None:
    resp = client.get("/cases/no_such_case/result")
    assert resp.status_code == 404
    assert resp.json()["error"]["type"] == "unknown_case"


def test_duplicate_case_rejected(client: TestClient) -> None:
    payload = {"name": "dup", "mach": 2.0, "gamma": GAMMA}
    assert client.post("/cases", json=payload).status_code == 201
    resp = client.post("/cases", json=payload)
    assert resp.status_code == 409
    assert resp.json()["error"]["type"] == "duplicate_case"


def test_registration_then_evaluation_roundtrip(client: TestClient) -> None:
    payload = {"name": "case_a", "mach": 1.8, "gamma": 1.4, "static_pressure": 90000.0,
               "static_temperature": 280.0}
    assert client.post("/cases", json=payload).status_code == 201
    by_name = client.get("/cases/case_a/result").json()["result"]
    direct = client.post("/evaluate", json={k: v for k, v in payload.items() if k != "name"}).json()
    assert by_name == direct


# ---------------------------------------------------------------------------
# Batch evaluation
# ---------------------------------------------------------------------------

def test_batch_matches_single_evaluation(client: TestClient) -> None:
    machs = [1.5, 2.0, 2.5, 3.0]
    batch = client.post("/batch", json={"gamma": GAMMA, "machs": machs}).json()
    assert batch["total"] == 4 and batch["succeeded"] == 4 and batch["failed"] == 0
    for item in batch["results"]:
        single = client.post("/evaluate", json={"mach": item["mach"], "gamma": GAMMA}).json()
        assert item["result"] == single, "batch and single paths must agree exactly"


def test_batch_partial_failure_isolated(client: TestClient) -> None:
    batch = client.post("/batch", json={"gamma": GAMMA, "machs": [2.0, 0.8, 3.0]}).json()
    assert batch["succeeded"] == 2 and batch["failed"] == 1
    by_index = {r["index"]: r for r in batch["results"]}
    assert by_index[0]["ok"] and by_index[2]["ok"]
    assert not by_index[1]["ok"]
    assert by_index[1]["error"]["type"] == "invalid_mach"


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------

def test_concurrent_requests_do_not_crosstalk(client: TestClient) -> None:
    machs = [1.2 + 0.1 * i for i in range(40)]

    def call(m: float):
        resp = client.post("/evaluate", json={"mach": m, "gamma": GAMMA})
        return m, resp.json()["ratios"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(pool.map(call, machs))

    for m, ratios in results.items():
        solo = client.post("/evaluate", json={"mach": m, "gamma": GAMMA}).json()["ratios"]
        assert ratios == solo
        assert ratios["mach_downstream"] < 1.0


def test_concurrent_registration_and_lookup(client: TestClient) -> None:
    def register_and_read(i: int):
        name = f"case_{i}"
        assert client.post("/cases", json={"name": name, "mach": 2.0 + i * 0.01,
                                           "gamma": GAMMA}).status_code == 201
        return name, client.get(f"/cases/{name}/result").json()["result"]["input"]["mach"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(register_and_read, range(20)))

    for i, (name, mach_echoed) in enumerate(outcomes):
        assert name == f"case_{i}"
        assert mach_echoed == pytest.approx(2.0 + i * 0.01)


def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["cases_registered"] >= 1
