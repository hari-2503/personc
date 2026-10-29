"""Core API tests for Person C: health, tariffs, appliances, readings, consumption."""
from datetime import date, timedelta

TODAY = date.today()
MONTH = TODAY.strftime("%Y-%m")
PREV_MONTH = (TODAY.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
DAY = f"{PREV_MONTH}-15"  # a day guaranteed to be inside the previous month


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["service"] == "smart-home-energy-monitor"
    assert body["database"] == "connected"


def test_tariffs_seeded_and_flagged_unverified(client):
    body = client.get("/tariffs").json()
    names = {t["name"] for t in body["tariffs"]}
    assert "TNEB-Domestic-Monthly-Seed" in names
    assert "TNEB-Domestic-Bimonthly-Seed" in names
    assert body["default_tariff"] == "TNEB-Domestic-Monthly-Seed"
    for tariff in body["tariffs"]:
        assert tariff["verified"] is False  # honesty flag must be false for seeds
        assert tariff["notes"].startswith("UNVERIFIED")


def test_appliance_crud(client):
    created = client.post(
        "/appliances",
        json={"name": "AC", "room": "Bedroom", "rated_power_kw": 1.5, "quantity": 2,
              "typical_hours_per_day": 6.0},
    )
    assert created.status_code == 201
    appliance = created.json()
    assert appliance["id"] > 0

    updated = client.put(f"/appliances/{appliance['id']}", json={"typical_hours_per_day": 5.5})
    assert updated.json()["typical_hours_per_day"] == 5.5

    deleted = client.delete(f"/appliances/{appliance['id']}")
    assert deleted.json()["deleted"] is True
    assert client.get(f"/appliances/{appliance['id']}").status_code == 404


def test_appliance_validation(client):
    bad_power = client.post("/appliances", json={"name": "X", "rated_power_kw": 0})
    assert bad_power.status_code == 422
    bad_qty = client.post("/appliances", json={"name": "X", "rated_power_kw": 1.0, "quantity": 0})
    assert bad_qty.status_code == 422


def test_reading_upsert_and_energy_math(client, appliance):
    appliance_id = appliance["id"]
    first = client.post(
        "/readings",
        json={"appliance_id": appliance_id, "reading_date": DAY, "hours_used": 10.0},
    )
    assert first.status_code == 201, first.text  # created
    body = first.json()
    # E_kWh = 1.2 kW * 1 unit * 10 h = 12.0
    assert body["kwh"] == 12.0
    assert body["source"] == "manual"

    # Upsert same (appliance, date): updates instead of duplicating.
    second = client.post(
        "/readings",
        json={"appliance_id": appliance_id, "reading_date": DAY, "hours_used": 5.0},
    )
    assert second.status_code == 200
    assert second.json()["id"] == body["id"]
    assert second.json()["kwh"] == 6.0

    listed = client.get("/readings", params={"start": DAY, "end": DAY}).json()["readings"]
    assert len(listed) == 1
    assert listed[0]["hours_used"] == 5.0
    assert listed[0]["appliance_name"] == "Heater"


def test_reading_requires_known_appliance(client):
    response = client.post(
        "/readings", json={"appliance_id": 99999, "reading_date": DAY, "hours_used": 1.0}
    )
    assert response.status_code == 404


def test_reading_rejects_impossible_hours(client, appliance):
    response = client.post(
        "/readings",
        json={"appliance_id": appliance["id"], "reading_date": DAY, "hours_used": 25.0},
    )
    assert response.status_code == 422


def test_bulk_default_reads_typical_hours(client, appliance):
    result = client.post("/readings/bulk-default", json={"reading_date": DAY}).json()
    # The fixture appliance has no reading for DAY yet -> must be created.
    own = next(d for d in result["details"] if d["appliance_id"] == appliance["id"])
    assert own["action"] == "created"
    assert result["created"] >= 1
    # Second run: everything skipped (idempotent day fill).
    result2 = client.post("/readings/bulk-default", json={"reading_date": DAY}).json()
    assert result2["created"] == 0
    own2 = next(d for d in result2["details"] if d["appliance_id"] == appliance["id"])
    assert own2["action"] == "already_logged"


def test_daily_consumption(client, appliance):
    # Isolated date so the session-shared database cannot interfere.
    isolated_day = "2001-05-10"
    client.post("/readings", json={"appliance_id": appliance["id"], "reading_date": isolated_day, "hours_used": 5.0})
    data = client.get("/consumption/daily", params={"date": isolated_day}).json()
    assert data["start_date"] == data["end_date"] == isolated_day
    assert len(data["days"]) == 1
    day = data["days"][0]
    assert day["total_kwh"] == 6.0  # 1.2 kW * 1 unit * 5 h
    assert day["by_appliance"][0]["name"] == "Heater"
    assert day["by_appliance"][0]["kwh"] == 6.0


def test_daily_range_validation(client):
    bad = client.get("/consumption/daily", params={"start": DAY, "end": "2000-01-01"})
    assert bad.status_code == 422


def test_monthly_consumption(client, appliance):
    # Isolated month so the session-shared database cannot interfere.
    client.post("/readings", json={"appliance_id": appliance["id"], "reading_date": "2001-06-15", "hours_used": 5.0})
    data = client.get("/consumption/monthly", params={"months": 24}).json()
    months = {row["month"]: row for row in data["months"]}
    isolated = months["2001-06"]
    assert isolated["total_kwh"] == 6.0
    assert isolated["days_with_data"] == 1
    # The most recent month with data comes first.
    assert data["months"][0]["month"] >= "2001-06"


def test_integration_status_endpoint(client, appliance):
    client.post("/readings", json={"appliance_id": appliance["id"], "reading_date": DAY, "hours_used": 5.0})
    body = client.get("/integrations/status").json()
    assert body["service"] == "smart-home-energy-monitor"
    assert body["status"] == "ok"
    assert body["appliances_count"] >= 1
    assert "/history" in body["export_endpoints"]
    assert body["latest_month_summary"]["month"] == MONTH
