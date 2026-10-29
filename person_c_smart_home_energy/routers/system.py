"""System-level endpoints for Person C: health + integration status."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from config import settings
from crud import list_appliances, months_with_data
from database import get_db
from models import UsageReading
from services.analytics import month_estimate

router = APIRouter(tags=["System"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    database_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover
        database_status = "unavailable"
    return {
        "status": "ok" if database_status == "connected" else "degraded",
        "service": settings.service_name,
        "owner": settings.service_owner,
        "version": settings.version,
        "database": database_status,
        "time": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/integrations/status")
def integrations_status(db: Session = Depends(get_db)):
    """Self-describing status for consumers (Person A polls /history?months=6).

    Persons integrating with this app use documented REST endpoints only:
      - GET /consumption/monthly?months=N
      - GET /bill/estimate?month=YYYY-MM
      - GET /history?months=N
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m")
    readings_count = db.scalar(select(func.count(UsageReading.id))) or 0
    appliances = list_appliances(db)
    months = months_with_data(db)
    latest_estimate = month_estimate(db, today, settings.default_tariff)
    return {
        "service": settings.service_name,
        "version": settings.version,
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "appliances_count": len(appliances),
        "active_appliances_count": len([a for a in appliances if a.active]),
        "readings_count": int(readings_count),
        "months_with_data": months,
        "default_tariff": settings.default_tariff,
        "latest_month_summary": {
            "month": today,
            "estimated_kwh": latest_estimate["estimated_kwh"],
            "estimated_amount": latest_estimate["estimated_amount"],
            "status": latest_estimate["status"],
        },
        "export_endpoints": ["/consumption/monthly", "/bill/estimate", "/history"],
    }
