"""Person C - Smart Home Electricity Monitoring & Bill Estimation (FastAPI backend).

Run locally:  uvicorn main:app --host 127.0.0.1 --port 8003 --reload
Interactive docs: http://127.0.0.1:8003/docs
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from config import settings
from database import Base, SessionLocal, engine, get_db
from routers import appliances, billing, consumption, readings, system
from seed_data import seed_tariffs


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create tables and idempotently seed the tariff reference sets."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_tariffs(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Smart Home Electricity Monitoring & Bill Estimation API",
    description=(
        "CSI3007 Advanced Python Programming - Person C (Hariharan S, 23MID0182). "
        "Tracks appliance usage (E_kWh = P_kW * t_hours), aggregates daily/monthly "
        "consumption, estimates bills from configurable TNEB-style tariff slabs, "
        "and compares estimated vs actual bills (D_% = |D|/B_actual * 100) as an "
        "investigation signal only. Exposes a stable REST contract consumed by "
        "Person A over HTTP."
    ),
    version=settings.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(appliances.router)
app.include_router(readings.router)
app.include_router(consumption.router)
app.include_router(billing.router)
app.include_router(system.router)


@app.get("/", tags=["System"], include_in_schema=False)
def root():
    return {"service": settings.service_name, "docs": "/docs", "health": "/health"}
