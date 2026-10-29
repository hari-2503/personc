"""Billing endpoints for Person C: estimate, actual, compare, history, tariffs."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from config import settings
from crud import get_actual_bill, list_tariff_sets, upsert_actual_bill_tracked
from database import get_db
from schemas import (
    ActualBillCreate,
    ActualBillOut,
    CompareResponse,
    EstimateResponse,
    HistoryResponse,
    SlabBreakdown,
    SlabOut,
    TariffSetOut,
    TariffsResponse,
)
from services.analytics import history as history_analytics
from services.analytics import month_estimate
from services.tariff import get_tariff_set

router = APIRouter(tags=["Billing & Tariffs"])

DISCLAIMER = (
    "Deviation is only an investigation signal. It does NOT prove a faulty meter: "
    "usage-pattern changes, seasonal loads, tariffs, meter-reading dates and "
    "estimation error can all explain a gap."
)
SUGGESTED_ACTION = (
    "Analyze the previous 6 months via GET /history?months=6: a persistent gap "
    "suggests a systematic cause (logging error, new appliance, tariff change); "
    "a one-off gap is usually explained by usage or reading-date shifts."
)


@router.get("/bill/estimate", response_model=EstimateResponse)
def estimate_endpoint(
    month: Optional[str] = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: Session = Depends(get_db),
):
    """Estimated bill for one month from logged usage + configured tariff slabs."""
    month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    estimate = month_estimate(db, month, settings.default_tariff)
    return EstimateResponse(
        month=month,
        status=estimate["status"],
        tariff_name=estimate["tariff_name"],
        tariff_verified=estimate["tariff_verified"],
        estimated_kwh=estimate["estimated_kwh"],
        energy_charge=estimate["energy_charge"],
        fixed_charge=estimate["fixed_charge"],
        estimated_amount=estimate["estimated_amount"],
        currency=estimate["currency"],
        slab_breakdown=[SlabBreakdown(**row) for row in estimate["slab_breakdown"]],
        note=estimate["note"],
    )


@router.post(
    "/bill/actual",
    response_model=ActualBillOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Existing actual bill for that month replaced"}},
    description="UPSERT: 201 when the month's actual bill is first recorded, 200 when re-posting "
    "for the same month replaces it.",
)
def record_actual_endpoint(payload: ActualBillCreate, response: Response, db: Session = Depends(get_db)):
    bill, created = upsert_actual_bill_tracked(
        db,
        month=payload.month,
        kwh_actual=payload.kwh_actual,
        amount_actual=payload.amount_actual,
        notes=payload.notes or "",
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return bill


@router.get("/bill/compare", response_model=CompareResponse)
def compare_endpoint(
    month: Optional[str] = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: Session = Depends(get_db),
):
    """Compare estimated vs actual bill.

    D = B_actual - B_estimated and D_% = |D| / B_actual * 100 (spec formula).
    When D_% exceeds the configured threshold the month is flagged for
    investigation - never treated as proof of meter fault.
    """
    month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    estimate = month_estimate(db, month, settings.default_tariff)
    actual = get_actual_bill(db, month)

    if actual is None and estimate["status"] != "ok":
        return CompareResponse(
            month=month, status="no_data", threshold_percent=settings.deviation_threshold_percent,
            disclaimer=DISCLAIMER,
        )
    if actual is None:
        return CompareResponse(
            month=month, status="no_actual", threshold_percent=settings.deviation_threshold_percent,
            estimated_kwh=estimate["estimated_kwh"], estimated_amount=estimate["estimated_amount"],
            disclaimer=DISCLAIMER,
        )
    if estimate["status"] != "ok":
        return CompareResponse(
            month=month, status="no_estimate", threshold_percent=settings.deviation_threshold_percent,
            actual_kwh=actual.kwh_actual, actual_amount=actual.amount_actual,
            disclaimer=DISCLAIMER,
        )

    d_kwh = round(actual.kwh_actual - estimate["estimated_kwh"], 3)
    d_amount = round(actual.amount_actual - estimate["estimated_amount"], 2)
    # Amount basis only makes sense when the estimate itself is non-zero
    # (e.g. all usage inside a free slab yields a 0 estimate - comparing
    # amounts would be meaningless), otherwise fall back to kWh basis.
    if estimate["estimated_amount"] > 0 and actual.amount_actual > 0:
        deviation_percent = round(abs(d_amount) / abs(actual.amount_actual) * 100.0, 2)
        basis = "amount"
    elif actual.kwh_actual > 0:
        deviation_percent = round(abs(d_kwh) / abs(actual.kwh_actual) * 100.0, 2)
        basis = "kwh"
    else:
        deviation_percent = None
        basis = None

    needs_investigation = bool(
        deviation_percent is not None and deviation_percent > settings.deviation_threshold_percent
    )
    return CompareResponse(
        month=month,
        status="ok",
        estimated_kwh=estimate["estimated_kwh"],
        actual_kwh=actual.kwh_actual,
        D_kwh=d_kwh,
        estimated_amount=estimate["estimated_amount"],
        actual_amount=actual.amount_actual,
        D_amount=d_amount,
        deviation_percent=deviation_percent,
        deviation_basis=basis,
        threshold_percent=settings.deviation_threshold_percent,
        needs_investigation=needs_investigation,
        disclaimer=DISCLAIMER,
        suggested_action=SUGGESTED_ACTION if needs_investigation else None,
    )


@router.get("/history", response_model=HistoryResponse)
def history_endpoint(
    months: int = Query(default=6, ge=1, le=24),
    db: Session = Depends(get_db),
):
    """Last N calendar months (most recent first): estimate vs actual + deviation."""
    entries = history_analytics(db, months, settings.default_tariff, settings.deviation_threshold_percent)
    tariff = get_tariff_set(db, settings.default_tariff)
    return HistoryResponse(
        months=entries,
        tariff_name=settings.default_tariff,
        tariff_verified=tariff.verified if tariff else None,
    )


@router.get("/tariffs", response_model=TariffsResponse)
def tariffs_endpoint(db: Session = Depends(get_db)):
    """All configured tariff sets. Seeded sets are UNVERIFIED placeholders."""
    return TariffsResponse(
        default_tariff=settings.default_tariff,
        tariffs=[
            TariffSetOut(
                name=tariff.name,
                billing_cycle=tariff.billing_cycle,
                fixed_charge=tariff.fixed_charge,
                currency=tariff.currency,
                verified=tariff.verified,
                notes=tariff.notes,
                slabs=[SlabOut(slab_min=s.slab_min, slab_max=s.slab_max, rate_per_kwh=s.rate_per_kwh) for s in tariff.slabs],
            )
            for tariff in list_tariff_sets(db)
        ],
    )
