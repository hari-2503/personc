"""Usage reading endpoints for Person C (upsert semantics)."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from crud import get_appliance, list_readings, upsert_reading
from database import get_db
from models import Appliance
from schemas import BulkDefaultRequest, BulkDefaultResult, ReadingCreate, ReadingOut

router = APIRouter(prefix="/readings", tags=["Readings"])


@router.post("", response_model=ReadingOut, description="POST is an UPSERT: re-posting the same (appliance_id, reading_date) updates hours_used.")
def upsert_reading_endpoint(payload: ReadingCreate, db: Session = Depends(get_db)):
    appliance = get_appliance(db, payload.appliance_id)
    if appliance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Appliance {payload.appliance_id} not found")
    reading, _created = upsert_reading(
        db,
        appliance_id=payload.appliance_id,
        reading_date=payload.reading_date,
        hours_used=payload.hours_used,
        source=payload.source,
    )
    reading.appliance_name = appliance.name  # transient attr for serialization
    return reading


@router.post("/bulk-default", response_model=BulkDefaultResult, description="Convenience endpoint (extension): log typical_hours_per_day for every ACTIVE appliance on one date; existing readings are skipped.")
def bulk_default_endpoint(payload: BulkDefaultRequest, db: Session = Depends(get_db)):
    created = skipped = 0
    details: list[dict] = []
    for appliance in db.query(Appliance).filter(Appliance.active.is_(True)).all():
        if appliance.typical_hours_per_day <= 0:
            skipped += 1
            details.append({"appliance_id": appliance.id, "name": appliance.name, "action": "skipped_no_typical_hours"})
            continue
        _reading, was_created = upsert_reading(
            db,
            appliance_id=appliance.id,
            reading_date=payload.reading_date,
            hours_used=appliance.typical_hours_per_day,
            source="default",
        )
        if was_created:
            created += 1
            details.append({"appliance_id": appliance.id, "name": appliance.name, "action": "created"})
        else:
            skipped += 1
            details.append({"appliance_id": appliance.id, "name": appliance.name, "action": "already_logged"})
    return BulkDefaultResult(reading_date=payload.reading_date, created=created, skipped=skipped, details=details)


class ReadingListResponse(BaseModel):
    readings: list[ReadingOut]


@router.get("", response_model=ReadingListResponse)
def list_readings_endpoint(
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    appliance_id: Optional[int] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    readings = list_readings(db, start=start, end=end, appliance_id=appliance_id, limit=limit)
    out = []
    for reading in readings:
        reading.appliance_name = reading.appliance.name  # transient attr for serialization
        out.append(ReadingOut.model_validate(reading))
    return ReadingListResponse(readings=out)
