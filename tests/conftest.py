"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services.registry import registry


@pytest.fixture()
def client() -> TestClient:
    # Each test starts from the seeded state only; the in-memory registry
    # is process-global so cases created by one test must not leak.
    registry.clear()
    registry.seed([(config.SEED_CASE_NAME, dict(config.SEED_CASE_CONDITION))])
    with TestClient(app) as test_client:
        yield test_client
