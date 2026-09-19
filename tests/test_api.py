"""HTTP-level tests: routes, structured errors, batching, concurrency."""

from __future__ import annotations

import concurrent.futures

import pytest
from fastapi.testclient import TestClient

from app import config


# ---------- single evaluation ------------------------------------------------

def test_evaluate_closed_form(client: TestClient):
    resp = client.post("/shock/evaluate", json={"mach1": 2.0, "gamma": 1.4})
    assert resp.status_code == 200
    sol = resp.json()["solution"]
    r = sol["ratios"]
    assert sol["mach2"] == pytest.approx(0.5773502691896257, abs=1e-15)
    assert r["p2_p1"] == pytest.approx(4.5)
    assert r["t2_t1"] == pytest.approx(1.6875)
    assert r["rho2_rho1"] == pytest.approx(8 / 3)
    assert r["p02_p01"] == pytest.approx(0.72087386148, rel=1e-9)
    assert r["t02_t01"] == 1.0
    assert sol["dimensional"] is False


def test_evaluate_dimensional_full_state(client: TestClient):
    resp = client.post(
        "/shock/evaluate",
        json={"mach1": 2.0, "gamma": 1.4, "p1": 101325.0, "t1": 288.15},
    )
    assert resp.status_code == 200
    body = resp.json()["solution"]
    assert body["dimensional"] is True
    up, down = body["upstream"], body["downstream"]
    assert down["pressure"] == pytest.approx(up["pressure"] * 4.5)
    assert down["total_temperature"] == pytest.approx(up["total_temperature"], rel=1e-12)
    assert abs(down["mass_flux"] - up["mass_flux"]) / up["mass_flux"] < 1e-10


def test_evaluate_subsonic_typed_error(client: TestClient):
    resp = client.post("/shock/evaluate", json={"mach1": 0.8, "gamma": 1.4})
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "MACH_NOT_SUPERSONIC"
    assert isinstance(err["message"], str) and err["message"]


def test_evaluate_missing_mach_typed_error(client: TestClient):
    resp = client.post("/shock/evaluate", json={"gamma": 1.4})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "MACH_MISSING"


def test_evaluate_bad_gamma_typed_error(client: TestClient):
    resp = client.post("/shock/evaluate", json={"mach1": 2.0, "gamma": 1.0})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "GAMMA_INVALID"


def test_evaluate_nonpositive_pressure_typed_error(client: TestClient):
    resp = client.post(
        "/shock/evaluate",
        json={"mach1": 2.0, "gamma": 1.4, "p1": -1, "t1": 288.15},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "DIMENSIONAL_INPUT_INVALID"


def test_malformed_body_is_structured_error(client: TestClient):
    resp = client.post("/shock/evaluate", json={"mach1": "fast", "gamma": 1.4})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


# ---------- named cases ------------------------------------------------------

def test_register_and_get_case(client: TestClient):
    resp = client.post(
        "/cases", json={"name": "cruise", "mach1": 2.5, "gamma": 1.4}
    )
    assert resp.status_code == 201

    got = client.get("/cases/cruise")
    assert got.status_code == 200
    sol = got.json()["solution"]
    assert sol["mach1"] == 2.5
    assert sol["mach2"] < 1.0
    assert sol["ratios"]["p2_p1"] > 1.0


def test_case_persists_and_re_evaluates_identically(client: TestClient):
    client.post("/cases", json={"name": "c", "mach1": 3.0, "gamma": 1.4})
    a = client.get("/cases/c").json()["solution"]
    b = client.get("/cases/c").json()["solution"]
    assert a == b


def test_unknown_case_name_404(client: TestClient):
    resp = client.get("/cases/ghost")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CASE_NOT_FOUND"


def test_register_duplicate_case_conflict(client: TestClient):
    payload = {"name": "dup", "mach1": 2.0, "gamma": 1.4}
    assert client.post("/cases", json=payload).status_code == 201
    resp = client.post("/cases", json=payload)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CASE_ALREADY_EXISTS"


def test_register_invalid_case_rejected_before_storage(client: TestClient):
    resp = client.post("/cases", json={"name": "bad", "mach1": 0.5, "gamma": 1.4})
    assert resp.status_code == 422
    assert client.get("/cases/bad").status_code == 404


def test_list_cases_is_read_only_echo(client: TestClient):
    client.post("/cases", json={"name": "a", "mach1": 1.5, "gamma": 1.4})
    client.post("/cases", json={"name": "b", "mach1": 2.0, "gamma": 1.3})
    resp = client.get("/cases")
    assert resp.status_code == 200
    names = {c["name"] for c in resp.json()["cases"]}
    # seeded case + the two new ones
    assert names == {config.SEED_CASE_NAME, "a", "b"}


def test_seed_case_matches_hand_table(client: TestClient):
    resp = client.get(f"/cases/{config.SEED_CASE_NAME}")
    assert resp.status_code == 200
    sol = resp.json()["solution"]
    r = sol["ratios"]
    assert sol["mach1"] == 2.0 and sol["gamma"] == 1.4
    assert sol["mach2"] == pytest.approx(0.5773502691896257, abs=1e-15)
    assert r["p2_p1"] == pytest.approx(4.5)
    assert r["t2_t1"] == pytest.approx(1.6875)
    assert r["rho2_rho1"] == pytest.approx(8 / 3)
    assert r["p02_p01"] == pytest.approx(0.72087386148, rel=1e-9)


# ---------- batch ------------------------------------------------------------

def test_batch_matches_single_evaluation(client: TestClient):
    machs = [1.2, 1.5, 2.0, 3.0, 7.0]
    batch = client.post("/shock/batch", json={"gamma": 1.4, "machs": machs}).json()
    for item, m in zip(batch["results"], machs):
        assert item["status"] == "ok" and item["mach1"] == m
        single = client.post(
            "/shock/evaluate", json={"mach1": m, "gamma": 1.4}
        ).json()["solution"]
        # Same window function: results must be identical, not just close.
        assert item["solution"] == single


def test_batch_matches_single_with_dimensional_inputs(client: TestClient):
    payload = {"gamma": 1.4, "machs": [1.5, 2.0, 3.0], "p1": 80000.0, "t1": 260.0}
    batch = client.post("/shock/batch", json=payload).json()
    for item, m in zip(batch["results"], payload["machs"]):
        single = client.post(
            "/shock/evaluate",
            json={"mach1": m, "gamma": 1.4, "p1": 80000.0, "t1": 260.0},
        ).json()["solution"]
        assert item["solution"] == single
        assert item["solution"]["dimensional"] is True


def test_batch_dimensional_input_affects_each_entry_independently(client: TestClient):
    # A shared non-positive pressure makes dimensional evaluation illegal for
    # every entry, but each is rejected on its own with a typed error.
    body = client.post(
        "/shock/batch",
        json={"gamma": 1.4, "machs": [2.0, 3.0], "p1": -1.0, "t1": 288.0},
    ).json()
    assert [i["status"] for i in body["results"]] == ["error", "error"]
    assert body["results"][0]["error"]["code"] == "DIMENSIONAL_INPUT_INVALID"
    assert body["results"][1]["error"]["code"] == "DIMENSIONAL_INPUT_INVALID"

    # Valid dimensional inputs: all entries succeed with full states.
    body = client.post(
        "/shock/batch",
        json={"gamma": 1.4, "machs": [2.0, 3.0], "p1": 101325.0, "t1": 288.15},
    ).json()
    assert body["failed"] == 0
    for item in body["results"]:
        assert item["solution"]["upstream"] is not None
        assert item["solution"]["downstream"]["mass_flux"] == pytest.approx(
            item["solution"]["upstream"]["mass_flux"], rel=1e-10
        )


def test_batch_partial_failure_does_not_take_whole_batch(client: TestClient):
    resp = client.post(
        "/shock/batch",
        json={"gamma": 1.4, "machs": [1.5, 0.8, 2.0, 1.0]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["succeeded"] == 2 and body["failed"] == 2
    statuses = [item["status"] for item in body["results"]]
    assert statuses == ["ok", "error", "ok", "error"]
    bad = body["results"][1]
    assert bad["error"]["code"] == "MACH_NOT_SUPERSONIC"
    assert body["results"][3]["error"]["code"] == "MACH_NOT_SUPERSONIC"
    good = body["results"][0]["solution"]
    assert good["mach1"] == 1.5 and good["mach2"] < 1.0


def test_batch_invalid_shared_gamma_rejected_upfront(client: TestClient):
    resp = client.post("/shock/batch", json={"gamma": 1.0, "machs": [2.0]})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "GAMMA_INVALID"


def test_batch_empty_rejected(client: TestClient):
    resp = client.post("/shock/batch", json={"gamma": 1.4, "machs": []})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "EMPTY_BATCH"


# ---------- ops --------------------------------------------------------------

def test_healthz_reports_status_and_case_count(client: TestClient):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["registered_cases"] == 1  # seeded case only
    assert body["uptime_seconds"] >= 0.0
    client.post("/cases", json={"name": "x", "mach1": 2.0, "gamma": 1.4})
    assert client.get("/healthz").json()["registered_cases"] == 2


def test_root_describes_service(client: TestClient):
    body = client.get("/").json()
    assert body["service"] == config.SERVICE_NAME
    assert any(ep.endswith("/shock/evaluate") for ep in body["endpoints"])


# ---------- concurrency ------------------------------------------------------

def test_concurrent_requests_do_not_cross_contaminate(client: TestClient):
    """Parallel evaluates with different (M1, gamma) must not bleed into each other."""

    def call(m: float, g: float) -> tuple[float, float, float]:
        r = client.post(
            "/shock/evaluate", json={"mach1": m, "gamma": g}
        ).json()["solution"]
        return r["mach1"], r["gamma"], r["mach2"]

    jobs = [(m, g) for m in (1.2, 1.5, 2.0, 3.0, 4.0) for g in (1.1, 1.4, 1.667)] * 4
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        for (m, g), (m1_back, g_back, m2_back) in zip(
            jobs, pool.map(lambda j: call(*j), jobs)
        ):
            assert (m1_back, g_back) == (m, g)
            assert m2_back < 1.0


def test_concurrent_case_registration_is_isolated(client: TestClient):
    def register(i: int) -> int:
        resp = client.post(
            "/cases", json={"name": f"case-{i}", "mach1": 1.0 + 0.1 * i, "gamma": 1.4}
        )
        return resp.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        codes = list(pool.map(register, range(1, 41)))
    assert codes == [201] * 40

    names = {c["name"] for c in client.get("/cases").json()["cases"]}
    assert names == {config.SEED_CASE_NAME, *(f"case-{i}" for i in range(1, 41))}
    # Every case evaluates to its own Mach number, not a neighbour's.
    for i in range(1, 41):
        sol = client.get(f"/cases/case-{i}").json()["solution"]
        assert sol["mach1"] == 1.0 + 0.1 * i
