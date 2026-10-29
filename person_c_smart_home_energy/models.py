"""SQLAlchemy ORM models for Person C - Smart Home Energy Monitor."""
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Appliance(Base):
    __tablename__ = "appliances"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    room: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    # Rated power in kilowatts (e.g. 1.5 for a 1.5 kW AC).
    rated_power_kw: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Default operating hours per unit per day, used by the bulk-default logger.
    typical_hours_per_day: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    notes: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    readings: Mapped[list["UsageReading"]] = relationship(back_populates="appliance")


class UsageReading(Base):
    """Operating hours logged for one appliance on one date.

    Energy per row: E_kWh = rated_power_kw * quantity * hours_used
    (hours_used = average operating hours PER UNIT that day).
    POST /readings upserts on (appliance_id, reading_date).
    """
    __tablename__ = "usage_readings"
    __table_args__ = (UniqueConstraint("appliance_id", "reading_date", name="uq_reading_appliance_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    appliance_id: Mapped[int] = mapped_column(ForeignKey("appliances.id"), index=True, nullable=False)
    reading_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    hours_used: Mapped[float] = mapped_column(Float, nullable=False)
    # manual (user entered) | default (bulk-default logger)
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    appliance: Mapped["Appliance"] = relationship(back_populates="readings")

    @property
    def kwh(self) -> float:
        return round(self.appliance.rated_power_kw * self.appliance.quantity * self.hours_used, 4)


class TariffSet(Base):
    """A named slab tariff configuration (e.g. TNEB domestic).

    SEED SETS ARE UNVERIFIED: they are best-effort placeholders and MUST be
    checked against the latest official TNEB/TANGEDCO tariff order. The
    `verified` flag surfaces this honestly in API responses and the UI.
    """
    __tablename__ = "tariff_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    # monthly | bimonthly
    billing_cycle: Mapped[str] = mapped_column(String(20), nullable=False)
    # Fixed charge per bill (currency), independent of consumption.
    fixed_charge: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str] = mapped_column(String(500), default="", nullable=False)

    slabs: Mapped[list["TariffSlab"]] = relationship(back_populates="tariff_set", order_by="TariffSlab.slab_min")


class TariffSlab(Base):
    __tablename__ = "tariff_slabs"

    id: Mapped[int] = mapped_column(primary_key=True)
    tariff_set_id: Mapped[int] = mapped_column(ForeignKey("tariff_sets.id"), index=True, nullable=False)
    slab_min: Mapped[int] = mapped_column(Integer, nullable=False)   # inclusive, 1-based
    slab_max: Mapped[int | None] = mapped_column(Integer, nullable=True)  # inclusive; NULL = infinity
    rate_per_kwh: Mapped[float] = mapped_column(Float, nullable=False)

    tariff_set: Mapped["TariffSet"] = relationship(back_populates="slabs")


class ActualBill(Base):
    """The bill actually received from the utility for one month (YYYY-MM)."""
    __tablename__ = "actual_bills"

    id: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[str] = mapped_column(String(7), unique=True, index=True, nullable=False)
    kwh_actual: Mapped[float] = mapped_column(Float, nullable=False)
    amount_actual: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
