"""CRUD + query layer for Person C. Routers never touch the ORM directly."""
from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import ActualBill, Appliance, TariffSet, TariffSlab, UsageReading


# --------------------------------------------------------------- appliances
def get_appliance(db: Session, appliance_id: int) -> Optional[Appliance]:
    return db.get(Appliance, appliance_id)


def create_appliance(db: Session, **fields) -> Appliance:
    appliance = Appliance(**fields)
    db.add(appliance)
    db.commit()
    db.refresh(appliance)
    return appliance


def update_appliance(db: Session, appliance: Appliance, changes: dict) -> Appliance:
    for field, value in changes.items():
        if value is not None:
            setattr(appliance, field, value)
    db.commit()
    db.refresh(appliance)
    return appliance


def delete_appliance(db: Session, appliance: Appliance) -> int:
    """Delete appliance and cascade its readings (manual cascade for SQLite)."""
    deleted_readings = (
        db.query(UsageReading).filter(UsageReading.appliance_id == appliance.id).delete()
    )
    db.delete(appliance)
    db.commit()
    return deleted_readings


def list_appliances(db: Session, active: Optional[bool] = None) -> list[Appliance]:
    stmt = select(Appliance)
    if active is not None:
        stmt = stmt.where(Appliance.active == active)
    return list(db.scalars(stmt.order_by(Appliance.id)).all())


# ----------------------------------------------------------------- readings
def upsert_reading(
    db: Session, *, appliance_id: int, reading_date: date, hours_used: float, source: str = "manual"
) -> tuple[UsageReading, bool]:
    """Create or update the reading for (appliance, date). Returns (row, created)."""
    reading = db.scalar(
        select(UsageReading).where(
            UsageReading.appliance_id == appliance_id, UsageReading.reading_date == reading_date
        )
    )
    created = reading is None
    if created:
        reading = UsageReading(
            appliance_id=appliance_id, reading_date=reading_date, hours_used=hours_used, source=source
        )
        db.add(reading)
    else:
        reading.hours_used = hours_used
        reading.source = source
    db.commit()
    db.refresh(reading)
    return reading, created


def list_readings(
    db: Session, *, start: Optional[date] = None, end: Optional[date] = None,
    appliance_id: Optional[int] = None, limit: int = 200,
) -> list[UsageReading]:
    stmt = select(UsageReading).join(Appliance)
    if start:
        stmt = stmt.where(UsageReading.reading_date >= start)
    if end:
        stmt = stmt.where(UsageReading.reading_date <= end)
    if appliance_id:
        stmt = stmt.where(UsageReading.appliance_id == appliance_id)
    stmt = stmt.order_by(UsageReading.reading_date.desc(), UsageReading.appliance_id)
    return list(db.scalars(stmt.limit(limit)).all())


def readings_for_month(db: Session, month: str) -> list[UsageReading]:
    return list(
        db.scalars(
            select(UsageReading)
            .join(Appliance)
            .where(func.strftime("%Y-%m", UsageReading.reading_date) == month)
        ).all()
    )


def months_with_data(db: Session) -> list[str]:
    rows = db.execute(
        select(func.strftime("%Y-%m", UsageReading.reading_date)).distinct()
    ).all()
    return sorted(row[0] for row in rows)


# ------------------------------------------------------------------ billing
def upsert_actual_bill(db: Session, *, month: str, kwh_actual: float, amount_actual: float, notes: str) -> ActualBill:
    bill = db.scalar(select(ActualBill).where(ActualBill.month == month))
    if bill is None:
        bill = ActualBill(month=month, kwh_actual=kwh_actual, amount_actual=amount_actual, notes=notes or "")
        db.add(bill)
    else:
        bill.kwh_actual = kwh_actual
        bill.amount_actual = amount_actual
        bill.notes = notes or bill.notes
    db.commit()
    db.refresh(bill)
    return bill


def get_actual_bill(db: Session, month: str) -> Optional[ActualBill]:
    return db.scalar(select(ActualBill).where(ActualBill.month == month))


def list_actual_bills(db: Session, limit: int = 36) -> list[ActualBill]:
    return list(db.scalars(select(ActualBill).order_by(ActualBill.month.desc()).limit(limit)).all())


# ------------------------------------------------------------------ tariffs
def get_tariff_set_by_name(db: Session, name: str) -> Optional[TariffSet]:
    return db.scalar(select(TariffSet).where(TariffSet.name == name))


def list_tariff_sets(db: Session) -> list[TariffSet]:
    return list(db.scalars(select(TariffSet).order_by(TariffSet.name)).all())


def create_tariff_set(
    db: Session, *, name: str, billing_cycle: str, fixed_charge: float,
    currency: str = "INR", verified: bool = False, notes: str = "", slabs: list[tuple],
) -> TariffSet:
    """slabs: list of (slab_min, slab_max_or_None, rate_per_kwh)."""
    tariff_set = TariffSet(
        name=name, billing_cycle=billing_cycle, fixed_charge=fixed_charge,
        currency=currency, verified=verified, notes=notes,
    )
    db.add(tariff_set)
    db.flush()
    for slab_min, slab_max, rate in slabs:
        db.add(TariffSlab(tariff_set_id=tariff_set.id, slab_min=slab_min, slab_max=slab_max, rate_per_kwh=rate))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(tariff_set)
    return tariff_set
