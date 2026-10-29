"""Shared pytest fixtures for Person C (throwaway SQLite via env)."""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="csi3007_c_tests_")
# TEST_DATABASE_URL lets the same suite run against PostgreSQL (must be an empty DB).
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{_TMP}/test_smart_home_energy.db"
os.environ["DEVIATION_THRESHOLD_PERCENT"] = "10.0"
os.environ["DEFAULT_TARIFF"] = "TNEB-Domestic-Monthly-Seed"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def appliance(client):
    response = client.post(
        "/appliances",
        json={"name": "Heater", "room": "Hall", "rated_power_kw": 1.2,
              "quantity": 1, "typical_hours_per_day": 5.0},
    )
    assert response.status_code == 201, response.text
    return response.json()
