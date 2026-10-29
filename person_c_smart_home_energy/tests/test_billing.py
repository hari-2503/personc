"""Billing tests for Person C: slab math, estimate, actual, compare, history.

The seeded monthly tariff (UNVERIFIED) is:
  1-50 @ 0.00 | 51-100 @ 2.35 | 101-200 @ 4.70 | 201-250 @ 6.30 | ...
120 kWh -> 50*0 + 50*2.35 + 20*4.70 = 0 + 117.50 + 94.00 = 211.50 (+ fixed 0)

Tests use DISTINCT, fixed months (2001-01, 2002-02, 2003-03) for the exact
math assertions so they never interfere with each other's monthly totals
(the suite shares one session database). The /history test uses the recent
window and derives expectations from the live /bill/estimate response.
"""
from datetime import date, timedelta

TODAY = date.today()
MONTH = TODAY.strftime("%Y-%m")
PREV_MONTH = (TODAY.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")


def _appliance(client, name, power_kw, quantity=1):
    response = client.post(
        "/appliances",
        json={"name": name, "rated_power_kw": power_kw, "quantity": quantity},
    )
    assert response.status_code == 201
    return response.json()


def test_estimate_slab_math_exact(client):
    """120 kWh in month 2001-01 must cost exactly 211.50 with the seeded slabs.
    (5 kW x 24 h = 120 kWh - a single valid reading; hours are capped at 24.)"""
    appliance = _appliance(client, "Isolated Load", 5.0)
    client.post(
        "/readings",
        json={"appliance_id": appliance["id"], "reading_date": "2001-01-05", "hours_used": 24.0},
    )
    estimate = client.get("/bill/estimate", params={"month": "2001-01"}).json()
    assert estimate["status"] == "ok"
    assert estimate["estimated_kwh"] == 120.0
    assert estimate["energy_charge"] == 211.50
    assert estimate["estimated_amount"] == 211.50
    assert estimate["tariff_verified"] is False  # honesty flag present
    slabs = {row["slab_min"]: row for row in estimate["slab_breakdown"]}
    assert slabs[1]["units_in_slab"] == 50 and slabs[1]["subtotal"] == 0.0
    assert slabs[51]["units_in_slab"] == 50 and slabs[51]["subtotal"] == 117.50
    assert slabs[101]["units_in_slab"] == 20 and slabs[101]["subtotal"] == 94.00


def test_estimate_no_data_is_valid_zero(client):
    estimate = client.get("/bill/estimate", params={"month": "1999-01"}).json()
    assert estimate["status"] == "no_data"
    assert estimate["estimated_kwh"] == 0.0
    assert estimate["estimated_amount"] == 0.0
    assert estimate["note"]


def test_actual_bill_upsert_and_validation(client):
    created = client.post(
        "/bill/actual", json={"month": PREV_MONTH, "kwh_actual": 100.0, "amount_actual": 500.0}
    )
    assert created.status_code == 200
    # Upsert same month replaces the stored values.
    updated = client.post(
        "/bill/actual", json={"month": PREV_MONTH, "kwh_actual": 110.0, "amount_actual": 550.0}
    )
    assert updated.status_code == 200
    assert updated.json()["kwh_actual"] == 110.0
    assert updated.json()["amount_actual"] == 550.0

    bad = client.post("/bill/actual", json={"month": "2025/07", "kwh_actual": 1.0, "amount_actual": 1.0})
    assert bad.status_code == 422


def test_compare_deviation_and_investigation_flag(client):
    """Month 2002-02: estimated 120 kWh / 211.50 INR vs actual 100 kWh / 500 INR
    -> D_amount = 288.50, D_% = 57.7% > 10% threshold -> investigate."""
    appliance = _appliance(client, "Isolated Load 2002", 5.0)
    client.post(
        "/readings",
        json={"appliance_id": appliance["id"], "reading_date": "2002-02-05", "hours_used": 24.0},
    )
    client.post(
        "/bill/actual", json={"month": "2002-02", "kwh_actual": 100.0, "amount_actual": 500.0}
    )
    compare = client.get("/bill/compare", params={"month": "2002-02"}).json()
    assert compare["status"] == "ok"
    assert compare["estimated_kwh"] == 120.0
    assert compare["D_kwh"] == -20.0
    assert compare["D_amount"] == 288.50
    assert compare["deviation_percent"] == 57.7
    assert compare["deviation_basis"] == "amount"
    assert compare["threshold_percent"] == 10.0
    assert compare["needs_investigation"] is True
    assert "investigation signal" in compare["disclaimer"]
    assert "6 months" in compare["suggested_action"]


def test_compare_within_threshold_falls_back_to_kwh_basis(client):
    """Month 2003-03: 24 kWh (fully inside the free slab -> estimated amount 0)
    vs actual 26 kWh / 0.50 INR. Amount basis is meaningless (estimate is 0),
    so the API must fall back to the kWh basis: |26-24|/26 = 7.69%."""
    appliance = _appliance(client, "Isolated Load 2003", 1.0)
    client.post(
        "/readings",
        json={"appliance_id": appliance["id"], "reading_date": "2003-03-05", "hours_used": 24.0},
    )
    client.post(
        "/bill/actual", json={"month": "2003-03", "kwh_actual": 26.0, "amount_actual": 0.5}
    )
    compare = client.get("/bill/compare", params={"month": "2003-03"}).json()
    assert compare["status"] == "ok"
    assert compare["deviation_basis"] == "kwh"
    assert compare["deviation_percent"] == 7.69  # |26 - 24| / 26 * 100
    assert compare["needs_investigation"] is False


def test_compare_without_any_data(client):
    compare = client.get("/bill/compare", params={"month": "1999-02"}).json()
    assert compare["status"] == "no_data"
    assert compare["needs_investigation"] is False


def test_history_window_and_flags(client):
    """6-month window: derive expectations from the live estimate so the test
    is robust to other readings recorded for the previous month."""
    appliance = _appliance(client, "History Load", 5.0)
    client.post(
        "/readings",
        json={"appliance_id": appliance["id"], "reading_date": f"{PREV_MONTH}-05", "hours_used": 24.0},
    )
    client.post(
        "/bill/actual", json={"month": PREV_MONTH, "kwh_actual": 100.0, "amount_actual": 500.0}
    )

    estimate = client.get("/bill/estimate", params={"month": PREV_MONTH}).json()
    expected_amount = estimate["estimated_amount"]
    expected_kwh = estimate["estimated_kwh"]
    expected_dev = round(abs(500.0 - expected_amount) / 500.0 * 100.0, 2)

    history = client.get("/history", params={"months": 6}).json()["months"]
    assert len(history) == 6
    assert history[0]["month"] == MONTH  # most recent first
    assert history[1]["month"] == PREV_MONTH

    entry = next(e for e in history if e["month"] == PREV_MONTH)
    assert entry["estimated_kwh"] == expected_kwh
    assert entry["estimated_amount"] == expected_amount
    assert entry["actual_amount"] == 500.0
    assert entry["deviation_percent"] == expected_dev
    assert entry["needs_investigation"] == (expected_dev > 10.0)

    current = next(e for e in history if e["month"] == MONTH)
    assert current["actual_amount"] is None
