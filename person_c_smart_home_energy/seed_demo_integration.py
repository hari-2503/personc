"""Seed Person C's database with the CSI3007 integration demo data.

Usage:  python seed_demo_integration.py

Seeds EXACTLY the demo dataset used for the Person A integration showcase
and is safe to run repeatedly (idempotent upsert by name/month, using the
same CRUD/validation layer as the API - no raw SQL, no schema bypass):

    Air Conditioner  1.5 kW  Bedroom   quantity 1  4 h/day
    Refrigerator     0.2 kW  Kitchen   quantity 1  8 h/day
    Actual EB bill for 2026-10: 280 kWh, Rs 1210 (settled)

Run this against a fresh PostgreSQL database to reproduce the verified demo
state, then trigger "Sync now" in Person A (it imports the settled October
bill as C:2026-10). The tariff honesty rules are untouched: seed tariffs
stay `verified=False` with UNVERIFIED disclaimers (see seed_data.py).
"""
from crud import (
    create_appliance,
    get_actual_bill,
    list_appliances,
    update_appliance,
    upsert_actual_bill,
)
from database import Base, SessionLocal, engine

DEMO_APPLIANCES = [
    # name, room, rated_power_kw, quantity, typical_hours_per_day
    ("Air Conditioner", "Bedroom", 1.5, 1, 4.0),
    ("Refrigerator", "Kitchen", 0.2, 1, 8.0),
]

DEMO_ACTUAL_BILL = {"month": "2026-10", "kwh_actual": 280.0, "amount_actual": 1210.0}


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = {a.name.strip().lower(): a for a in list_appliances(db)}
        for name, room, power_kw, quantity, hours in DEMO_APPLIANCES:
            fields = {
                "room": room,
                "rated_power_kw": power_kw,
                "quantity": quantity,
                "typical_hours_per_day": hours,
                "active": True,
            }
            row = existing.get(name.lower())
            if row is None:
                row = create_appliance(db, name=name, **fields)
                print(f"created  {name}: {power_kw} kW x{quantity} {room}")
            else:
                row = update_appliance(db, row, fields)
                print(f"updated  {name}: {power_kw} kW x{quantity} {room}")

        bill = get_actual_bill(db, DEMO_ACTUAL_BILL["month"])
        if bill is None:
            bill = upsert_actual_bill(
                db,
                month=DEMO_ACTUAL_BILL["month"],
                kwh_actual=DEMO_ACTUAL_BILL["kwh_actual"],
                amount_actual=DEMO_ACTUAL_BILL["amount_actual"],
                notes="October 2026 EB bill - settled (integration demo reference record)",
            )
            print(f"created  actual bill {bill.month}: {bill.kwh_actual} kWh / {bill.amount_actual}")
        else:
            print(f"kept     actual bill {bill.month}: {bill.kwh_actual} kWh / {bill.amount_actual} (already present)")
        print("\nDone. GET /history now exposes the settled month; Person A imports it as C:2026-10.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
