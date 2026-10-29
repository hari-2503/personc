"""Pydantic v2 schemas defining the public JSON contract of Person C's API."""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

MonthPattern = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="Month as YYYY-MM")


# --------------------------------------------------------------- appliances
class ApplianceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    room: Optional[str] = Field(default=None, max_length=60)
    rated_power_kw: float = Field(gt=0, description="Rated power in kW, e.g. 1.5")
    quantity: int = Field(default=1, ge=1)
    typical_hours_per_day: float = Field(default=0.0, ge=0, le=24)
    active: bool = True
    notes: Optional[str] = Field(default=None, max_length=500)


class ApplianceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    room: Optional[str] = Field(default=None, max_length=60)
    rated_power_kw: Optional[float] = Field(default=None, gt=0)
    quantity: Optional[int] = Field(default=None, ge=1)
    typical_hours_per_day: Optional[float] = Field(default=None, ge=0, le=24)
    active: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=500)


class ApplianceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    room: str
    rated_power_kw: float
    quantity: int
    typical_hours_per_day: float
    active: bool
    notes: str
    created_at: datetime


# ----------------------------------------------------------------- readings
class ReadingCreate(BaseModel):
    appliance_id: int
    reading_date: date
    hours_used: float = Field(ge=0, le=24, description="Operating hours per unit that day")
    source: Literal["manual", "default"] = "manual"


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    appliance_id: int
    appliance_name: str
    reading_date: date
    hours_used: float
    source: str
    kwh: float


class BulkDefaultRequest(BaseModel):
    reading_date: date


class BulkDefaultResult(BaseModel):
    reading_date: date
    created: int
    skipped: int
    details: list[dict]


# -------------------------------------------------------------- consumption
class ApplianceUsage(BaseModel):
    appliance_id: int
    name: str
    hours_used: float
    kwh: float


class DailyConsumption(BaseModel):
    date: date
    total_kwh: float
    by_appliance: list[ApplianceUsage]


class DailyConsumptionResponse(BaseModel):
    start_date: date
    end_date: date
    days: list[DailyConsumption]


class MonthlyConsumption(BaseModel):
    month: str
    total_kwh: float
    days_with_data: int


class MonthlyConsumptionResponse(BaseModel):
    months: list[MonthlyConsumption]


# ------------------------------------------------------------------ billing
class SlabBreakdown(BaseModel):
    slab_min: int
    slab_max: Optional[int] = None
    rate_per_kwh: float
    units_in_slab: float
    subtotal: float


class EstimateResponse(BaseModel):
    month: str
    status: Literal["ok", "no_data", "no_tariff"]
    tariff_name: Optional[str] = None
    tariff_verified: Optional[bool] = None
    estimated_kwh: float = 0.0
    energy_charge: float = 0.0
    fixed_charge: float = 0.0
    estimated_amount: float = 0.0
    currency: str = "INR"
    slab_breakdown: list[SlabBreakdown] = []
    note: Optional[str] = None


class ActualBillCreate(BaseModel):
    month: str = MonthPattern
    kwh_actual: float = Field(ge=0)
    amount_actual: float = Field(ge=0)
    notes: Optional[str] = Field(default=None, max_length=500)


class ActualBillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    month: str
    kwh_actual: float
    amount_actual: float
    notes: str


class CompareResponse(BaseModel):
    month: str
    status: Literal["ok", "no_actual", "no_estimate", "no_data"]
    estimated_kwh: Optional[float] = None
    actual_kwh: Optional[float] = None
    D_kwh: Optional[float] = None
    estimated_amount: Optional[float] = None
    actual_amount: Optional[float] = None
    D_amount: Optional[float] = None
    deviation_percent: Optional[float] = None
    deviation_basis: Optional[Literal["amount", "kwh"]] = None
    threshold_percent: float
    needs_investigation: bool = False
    disclaimer: str
    suggested_action: Optional[str] = None


class HistoryEntry(BaseModel):
    month: str
    estimated_kwh: Optional[float] = None
    actual_kwh: Optional[float] = None
    estimated_amount: Optional[float] = None
    actual_amount: Optional[float] = None
    deviation_percent: Optional[float] = None
    needs_investigation: bool = False


class HistoryResponse(BaseModel):
    months: list[HistoryEntry]


# ------------------------------------------------------------------ tariffs
class SlabOut(BaseModel):
    slab_min: int
    slab_max: Optional[int] = None
    rate_per_kwh: float


class TariffSetOut(BaseModel):
    name: str
    billing_cycle: str
    fixed_charge: float
    currency: str
    verified: bool
    notes: str
    slabs: list[SlabOut]


class TariffsResponse(BaseModel):
    default_tariff: str
    tariffs: list[TariffSetOut]
