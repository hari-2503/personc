"""Appliance CRUD endpoints for Person C."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from crud import create_appliance, delete_appliance, get_appliance, list_appliances, update_appliance
from database import get_db
from schemas import ApplianceCreate, ApplianceOut, ApplianceUpdate

router = APIRouter(prefix="/appliances", tags=["Appliances"])


@router.post("", response_model=ApplianceOut, status_code=status.HTTP_201_CREATED)
def create_appliance_endpoint(payload: ApplianceCreate, db: Session = Depends(get_db)):
    """Register an appliance (rated power in kW; quantity for duplicate units)."""
    return create_appliance(db, **payload.model_dump())


@router.get("", response_model=list[ApplianceOut])
def list_appliances_endpoint(
    active: Optional[bool] = Query(default=None), db: Session = Depends(get_db)
):
    return list_appliances(db, active=active)


@router.get("/{appliance_id}", response_model=ApplianceOut)
def get_appliance_endpoint(appliance_id: int, db: Session = Depends(get_db)):
    appliance = get_appliance(db, appliance_id)
    if appliance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Appliance {appliance_id} not found")
    return appliance


@router.put("/{appliance_id}", response_model=ApplianceOut)
def update_appliance_endpoint(
    appliance_id: int, payload: ApplianceUpdate, db: Session = Depends(get_db)
):
    appliance = get_appliance(db, appliance_id)
    if appliance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Appliance {appliance_id} not found")
    return update_appliance(db, appliance, payload.model_dump(exclude_unset=True))


@router.delete("/{appliance_id}")
def delete_appliance_endpoint(appliance_id: int, db: Session = Depends(get_db)):
    appliance = get_appliance(db, appliance_id)
    if appliance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Appliance {appliance_id} not found")
    readings_deleted = delete_appliance(db, appliance)
    return {"deleted": True, "id": appliance_id, "readings_deleted": readings_deleted}
