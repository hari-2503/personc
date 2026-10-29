"""Consumption aggregation endpoints for Person C."""
import datetime as dt
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas import DailyConsumptionResponse, MonthlyConsumptionResponse
from services.analytics import daily_consumption as daily_aggregate
from services.analytics import monthly_consumption as monthly_aggregate

router = APIRouter(prefix="/consumption", tags=["Consumption"])

MAX_RANGE_DAYS = 92
MAX_MONTHS = 24


@router.get("/daily", response_model=DailyConsumptionResponse)
def daily_endpoint(
    day: Optional[date] = Query(default=None, alias="date", description="Single day view"),
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    days: int = Query(default=7, ge=1, le=92, description="Rolling window when start/end omitted"),
    db: Session = Depends(get_db),
):
    """Daily kWh totals with per-appliance breakdown.

    E_kWh = rated_power_kw * quantity * hours_used (per reading).
    Days without readings simply do not appear (missing data != zero usage).
    """
    # The query parameter is named "date" publicly but bound to `day` so it
    # does not shadow the datetime.date type used below.
    if day is not None:
        start = end = day
    elif start is None or end is None:
        end = dt.date.today()
        start = end - timedelta(days=days - 1)
    if start > end:
        raise HTTPException(status_code=422, detail="start must be <= end")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail=f"Range too large (max {MAX_RANGE_DAYS} days)")
    return DailyConsumptionResponse(
        start_date=start, end_date=end, days=daily_aggregate(db, start, end)
    )


@router.get("/monthly", response_model=MonthlyConsumptionResponse)
def monthly_endpoint(
    months: int = Query(default=6, ge=1, le=MAX_MONTHS), db: Session = Depends(get_db)
):
    """Monthly kWh totals (most recent month with data first)."""
    return MonthlyConsumptionResponse(months=monthly_aggregate(db, months))
