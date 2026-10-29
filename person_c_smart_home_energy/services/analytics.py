"""Aggregation + history analytics for Person C."""
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from crud import month_bounds
from models import ActualBill, Appliance, UsageReading
from services.tariff import estimate_amount, get_tariff_set


def daily_consumption(db: Session, start: date, end: date) -> list[dict]:
    """Per-day totals + per-appliance breakdown for [start, end]."""
    rows = (
        db.execute(
            select(UsageReading.reading_date, Appliance.id, Appliance.name,
                   UsageReading.hours_used, Appliance.rated_power_kw, Appliance.quantity)
            .join(Appliance, Appliance.id == UsageReading.appliance_id)
            .where(UsageReading.reading_date.between(start, end))
            .order_by(UsageReading.reading_date)
        ).all()
    )
    by_day: dict[date, dict] = {}
    for reading_date, appliance_id, name, hours, power, quantity in rows:
        day = by_day.setdefault(reading_date, {"date": reading_date, "total_kwh": 0.0, "_appl": {}})
        kwh = power * quantity * hours
        day["total_kwh"] += kwh
        entry = day["_appl"].setdefault(appliance_id, {"appliance_id": appliance_id, "name": name, "hours_used": 0.0, "kwh": 0.0})
        entry["hours_used"] += hours
        entry["kwh"] += kwh

    result = []
    for day_key in sorted(by_day):
        day = by_day[day_key]
        result.append(
            {
                "date": day_key,
                "total_kwh": round(day["total_kwh"], 3),
                "by_appliance": [
                    {"appliance_id": a["appliance_id"], "name": a["name"],
                     "hours_used": round(a["hours_used"], 2), "kwh": round(a["kwh"], 3)}
                    for a in sorted(day["_appl"].values(), key=lambda x: -x["kwh"])
                ],
            }
        )
    return result


def monthly_consumption(db: Session, months: int) -> list[dict]:
    """Totals for the last `months` calendar months that have any data.

    Grouped per day in SQL (portable), rolled up to months in Python.
    """
    rows = db.execute(
        select(
            UsageReading.reading_date,
            func.sum(Appliance.rated_power_kw * Appliance.quantity * UsageReading.hours_used),
        )
        .join(Appliance, Appliance.id == UsageReading.appliance_id)
        .group_by(UsageReading.reading_date)
    ).all()
    by_month: dict[str, dict] = {}
    for reading_date, total in rows:
        bucket = by_month.setdefault(reading_date.strftime("%Y-%m"), {"total": 0.0, "days": 0})
        bucket["total"] += float(total or 0.0)
        bucket["days"] += 1
    latest = sorted(by_month, reverse=True)[:months]
    return [
        {"month": month, "total_kwh": round(by_month[month]["total"], 3), "days_with_data": by_month[month]["days"]}
        for month in latest
    ]


def month_kwh(db: Session, month: str) -> float:
    start, end = month_bounds(month)
    total = db.scalar(
        select(func.sum(Appliance.rated_power_kw * Appliance.quantity * UsageReading.hours_used))
        .join(UsageReading, UsageReading.appliance_id == Appliance.id)
        .where(UsageReading.reading_date >= start, UsageReading.reading_date < end)
    )
    return round(float(total or 0.0), 3)


def month_estimate(db: Session, month: str, default_tariff: str) -> dict:
    """Estimate one month: kWh from readings + slab tariff application."""
    kwh = month_kwh(db, month)
    if kwh <= 0:
        return {"status": "no_data", "estimated_kwh": 0.0, "estimated_amount": 0.0,
                "energy_charge": 0.0, "fixed_charge": 0.0, "slab_breakdown": [],
                "tariff_name": default_tariff, "tariff_verified": None, "currency": "INR",
                "note": f"No usage readings recorded for {month} yet"}
    tariff_set = get_tariff_set(db, default_tariff)
    if tariff_set is None:
        return {"status": "no_tariff", "estimated_kwh": kwh, "estimated_amount": 0.0,
                "energy_charge": 0.0, "fixed_charge": 0.0, "slab_breakdown": [],
                "tariff_name": default_tariff, "tariff_verified": None, "currency": "INR",
                "note": f"Tariff set '{default_tariff}' not found - configure via GET /tariffs or seed_data.py"}
    energy, fixed, breakdown = estimate_amount(tariff_set, kwh)
    return {
        "status": "ok",
        "estimated_kwh": kwh,
        "estimated_amount": round(energy + fixed, 2),
        "energy_charge": energy,
        "fixed_charge": fixed,
        "slab_breakdown": breakdown,
        "tariff_name": tariff_set.name,
        "tariff_verified": tariff_set.verified,
        "currency": tariff_set.currency,
        "note": None if tariff_set.verified else "Tariff rates are UNVERIFIED seed values - confirm against the official TNEB/TANGEDCO tariff order",
    }


def history(db: Session, months: int, default_tariff: str, threshold_percent: float) -> list[dict]:
    """Last `months` calendar months (most recent first) with estimate vs actual.

    Deviation is only an INVESTIGATION SIGNAL - it can never prove a meter fault.
    """
    today = date.today()
    entries: list[dict] = []
    current = today.replace(day=1)
    for _ in range(months):
        month = current.strftime("%Y-%m")
        estimate = month_estimate(db, month, default_tariff)
        actual = db.scalar(select(ActualBill).where(ActualBill.month == month))
        entry = {
            "month": month,
            "estimated_kwh": estimate["estimated_kwh"] if estimate["status"] != "no_data" else None,
            "actual_kwh": actual.kwh_actual if actual else None,
            "estimated_amount": estimate["estimated_amount"] if estimate["status"] == "ok" else None,
            "actual_amount": actual.amount_actual if actual else None,
            "deviation_percent": None,
            "needs_investigation": False,
        }
        if actual and estimate["status"] == "ok":
            d_amount = actual.amount_actual - estimate["estimated_amount"]
            if estimate["estimated_amount"] > 0 and actual.amount_actual > 0:
                entry["deviation_percent"] = round(
                    abs(d_amount) / abs(actual.amount_actual) * 100.0, 2
                )
            elif actual.kwh_actual > 0:
                d_kwh = actual.kwh_actual - estimate["estimated_kwh"]
                entry["deviation_percent"] = round(abs(d_kwh) / abs(actual.kwh_actual) * 100.0, 2)
            if entry["deviation_percent"] is not None:
                entry["needs_investigation"] = entry["deviation_percent"] > threshold_percent
        entries.append(entry)
        # Step back one month.
        prev_month_end = current - timedelta(days=1)
        current = prev_month_end.replace(day=1)
    return entries
