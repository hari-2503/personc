"""Seed Person C's database: tariff reference sets + demo appliances/readings.

Usage:  python seed_data.py

HONESTY NOTE ON TARIFFS
-----------------------
The seeded tariff sets below are UNVERIFIED best-effort representations of
the Tamil Nadu (TNEB/TANGEDCO) domestic tariff as publicly described around
2023-24. They exist so the app is usable out of the box. They MUST be
verified against the latest official tariff notification before relying on
the bill estimates; `verified=False` is exposed by GET /tariffs and in every
estimate response. Users can freely edit rows in the tariff tables.

DERIVATION OF THE MONTHLY SET
-----------------------------
TNEB domestic slabs are bi-monthly. The "Monthly-Seed" set approximates a
monthly bill by halving the unit thresholds of the bimonthly slabs (keeping
the same rates). Halving thresholds is an approximation, not an official
monthly tariff - flagged in the notes and via verified=False.
"""
import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from crud import (
    create_appliance,
    create_tariff_set,
    list_appliances,
    list_tariff_sets,
    upsert_actual_bill,
    upsert_reading,
)
from database import Base, SessionLocal, engine

# Bimonthly slabs (UNVERIFIED seed): (min, max inclusive, rate)
# Units are 1-based: "1-100" = the first 100 units, matching how TNEB
# publishes slab tables. capacity = max - min + 1.
BIMONTHLY_SLABS = [
    (1, 100, 0.00),
    (101, 200, 2.35),
    (201, 400, 4.70),
    (401, 500, 6.30),
    (501, 600, 8.40),
    (601, 800, 9.45),
    (801, 1000, 10.50),
    (1001, None, 11.55),
]

# Monthly set derived by halving thresholds (UNVERIFIED approximation).
MONTHLY_SLABS = [
    (1, 50, 0.00),
    (51, 100, 2.35),
    (101, 200, 4.70),
    (201, 250, 6.30),
    (251, 300, 8.40),
    (301, 400, 9.45),
    (401, 500, 10.50),
    (501, None, 11.55),
]

SEED_NOTES_BIMONTHLY = (
    "UNVERIFIED seed: TNEB domestic bi-monthly slabs as publicly described 2023-24 "
    "(first 100 units zero-rated under the Government of Tamil Nadu subsidy). "
    "Verify against the latest official TNEB/TANGEDCO tariff order before use."
)
SEED_NOTES_MONTHLY = (
    "UNVERIFIED seed: derived from the TNEB bi-monthly domestic slabs by halving "
    "unit thresholds (approximation - NOT an official monthly tariff). "
    "Verify against the latest official tariff order before use."
)

DEMO_APPLIANCES = [
    # name, room, kW, quantity, typical hours/day
    ("LED Lights", "Living Room", 0.06, 8, 5.0),
    ("Ceiling Fan", "Bedroom", 0.075, 3, 8.0),
    ("Refrigerator", "Kitchen", 0.15, 1, 24.0),
    ("Air Conditioner 1.5T", "Bedroom", 1.5, 1, 5.0),
    ("Television", "Living Room", 0.10, 1, 4.0),
    ("Washing Machine", "Utility", 0.5, 1, 1.0),
    ("Geyser", "Bathroom", 2.0, 1, 1.0),
    ("Laptop + Router", "Study", 0.08, 1, 10.0),
]


def seed_tariffs(db: Session) -> None:
    """Idempotently insert the two reference tariff sets."""
    if not list_tariff_sets(db):
        create_tariff_set(
            db,
            name="TNEB-Domestic-Bimonthly-Seed",
            billing_cycle="bimonthly",
            fixed_charge=0.0,
            verified=False,
            notes=SEED_NOTES_BIMONTHLY,
            slabs=BIMONTHLY_SLABS,
        )
        create_tariff_set(
            db,
            name="TNEB-Domestic-Monthly-Seed",
            billing_cycle="monthly",
            fixed_charge=0.0,
            verified=False,
            notes=SEED_NOTES_MONTHLY,
            slabs=MONTHLY_SLABS,
        )


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_tariffs(db)
        print("Tariff sets ensured (verified=False - see GET /tariffs).")

        if list_appliances(db):
            print("Appliances already exist; demo data seeding skipped.")
            return

        rng = random.Random(42)  # deterministic demo data
        today = date.today()
        appliances = []
        for name, room, power, quantity, hours in DEMO_APPLIANCES:
            appliances.append(
                create_appliance(
                    db,
                    name=name,
                    room=room,
                    rated_power_kw=power,
                    quantity=quantity,
                    typical_hours_per_day=hours,
                    notes="Demo seed row",
                )
            )

        # 60 days of readings with mild random variation.
        for offset in range(59, -1, -1):
            day = today - timedelta(days=offset)
            for appliance in appliances:
                variation = rng.uniform(-0.15, 0.15)
                hours = max(0.0, round(appliance.typical_hours_per_day * (1 + variation), 2))
                if hours > 0:
                    upsert_reading(
                        db,
                        appliance_id=appliance.id,
                        reading_date=day,
                        hours_used=hours,
                        source="default",
                    )

        # Actual bills for the two previous months (slightly above estimate to
        # trigger the deviation-investigation path in the demo).
        current_month = today.strftime("%Y-%m")
        prev_month_date = (today.replace(day=1) - timedelta(days=1))
        prev_month = prev_month_date.strftime("%Y-%m")
        prev2_date = (prev_month_date.replace(day=1) - timedelta(days=1))
        prev2_month = prev2_date.strftime("%Y-%m")
        upsert_actual_bill(db, month=prev_month, kwh_actual=420.0, amount_actual=1250.0,
                           notes="Demo actual bill (from electricity board)")
        upsert_actual_bill(db, month=prev2_month, kwh_actual=380.0, amount_actual=1090.0,
                           notes="Demo actual bill (from electricity board)")
        print(f"Seeded {len(DEMO_APPLIANCES)} appliances, 60 days of readings, "
              f"and actual bills for {prev2_month} and {prev_month}.")
        print(f"(Current month {current_month} intentionally has no actual bill - "
              "use /bill/compare to see the no_actual path.)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
