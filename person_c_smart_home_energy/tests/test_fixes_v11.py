"""Regression tests for defects fixed in v1.1 plus tariff boundary checks."""
from datetime import date, timedelta
from types import SimpleNamespace

from services.tariff import energy_charge

# Seeded monthly set (UNVERIFIED, see README "Tariff assumptions").
MONTHLY = [
    SimpleNamespace(slab_min=1, slab_max=50, rate_per_kwh=0.00),
    SimpleNamespace(slab_min=51, slab_max=100, rate_per_kwh=2.35),
    SimpleNamespace(slab_min=101, slab_max=200, rate_per_kwh=4.70),
    SimpleNamespace(slab_min=201, slab_max=250, rate_per_kwh=6.30),
    SimpleNamespace(slab_min=251, slab_max=300, rate_per_kwh=8.40),
    SimpleNamespace(slab_min=301, slab_max=400, rate_per_kwh=9.45),
    SimpleNamespace(slab_min=401, slab_max=500, rate_per_kwh=10.50),
    SimpleNamespace(slab_min=501, slab_max=None, rate_per_kwh=11.55),
]


def test_daily_consumption_default_window_no_longer_500(client):
    """v1.0 crashed with 500 because the `date` query param shadowed datetime.date."""
    response = client.get("/consumption/daily")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["end_date"] == date.today().isoformat()
    assert body["start_date"] == (date.today() - timedelta(days=6)).isoformat()

    response = client.get("/consumption/daily", params={"days": 3})
    assert response.status_code == 200
    assert response.json()["start_date"] == (date.today() - timedelta(days=2)).isoformat()


def test_daily_consumption_single_date_param(client, appliance):
    client.post("/readings", json={"appliance_id": appliance["id"], "reading_date": "2004-04-04", "hours_used": 2.0})
    body = client.get("/consumption/daily", params={"date": "2004-04-04"}).json()
    assert body["start_date"] == body["end_date"] == "2004-04-04"
    assert body["days"][0]["total_kwh"] >= 2.4  # 1.2 kW x 2 h from this fixture (other heaters may add)


def test_daily_consumption_rejects_bad_dates(client):
    assert client.get("/consumption/daily", params={"date": "2026-13-01"}).status_code == 422
    assert client.get("/consumption/daily", params={"days": 0}).status_code == 422


def test_slab_boundaries_are_exact():
    assert energy_charge(0, MONTHLY)[0] == 0.0
    assert energy_charge(50, MONTHLY)[0] == 0.0          # top of the free slab
    assert energy_charge(51, MONTHLY)[0] == 2.35         # first chargeable unit
    assert energy_charge(100, MONTHLY)[0] == 117.50      # 50 x 2.35
    assert energy_charge(101, MONTHLY)[0] == 122.20      # + 1 x 4.70
    assert energy_charge(200, MONTHLY)[0] == 587.50      # 117.50 + 100 x 4.70
    # 117.5 + 470 + 315 + 420 + 945 + 1050 = 3317.50 for 500 units
    assert energy_charge(500, MONTHLY)[0] == 3317.50
    # open-ended top slab: 600 units -> + 100 x 11.55
    total, breakdown = energy_charge(600, MONTHLY)
    assert total == 4472.50
    assert breakdown[-1]["slab_max"] is None and breakdown[-1]["units_in_slab"] == 100


def test_fractional_units_split_correctly():
    total, breakdown = energy_charge(50.5, MONTHLY)
    assert total == round(0.5 * 2.35, 2)
    assert breakdown[-1]["units_in_slab"] == 0.5


def test_actual_bill_post_returns_201_then_200(client):
    first = client.post("/bill/actual", json={"month": "2005-05", "kwh_actual": 10, "amount_actual": 0})
    assert first.status_code == 201
    again = client.post("/bill/actual", json={"month": "2005-05", "kwh_actual": 12, "amount_actual": 5})
    assert again.status_code == 200 and again.json()["id"] == first.json()["id"]


def test_missing_resources_are_404(client):
    assert client.get("/appliances/999999").status_code == 404
    assert client.put("/appliances/999999", json={"name": "x"}).status_code == 404
    assert client.delete("/appliances/999999").status_code == 404


def test_history_contract_marks_estimates(client):
    body = client.get("/history", params={"months": 2}).json()
    assert len(body["months"]) == 2
    for entry in body["months"]:
        assert set(entry) >= {"month", "estimated_amount", "actual_amount", "deviation_percent"}
    assert client.get("/history", params={"months": 0}).status_code == 422
    assert client.get("/history", params={"months": 25}).status_code == 422


def test_unhandled_errors_are_generic_json(client, monkeypatch):
    import routers.billing as billing

    def boom(*args, **kwargs):
        raise RuntimeError("secret connection string postgresql://user:pw@host/db")

    monkeypatch.setattr(billing, "month_estimate", boom)
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app, raise_server_exceptions=False) as raw:
        response = raw.get("/bill/estimate", params={"month": "2006-06"})
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "postgresql" not in response.text
