"""Tariff (slab) math + bill estimation for Person C.

Slab model: contiguous slabs starting at unit 1 (1-based inclusive ranges,
matching how TNEB publishes its tables, e.g. "1-50", "51-100"); each slab
carries a marginal rate per kWh. The top slab may have max=NULL (infinity).
Example (seeded monthly set, UNVERIFIED): 1-50 free, 51-100 @ 2.35, ...
"""
from sqlalchemy.orm import Session

from models import TariffSet


def energy_charge(units: float, slabs: list) -> tuple[float, list[dict]]:
    """Marginal slab computation. Returns (total_energy_charge, breakdown).

    breakdown rows: {slab_min, slab_max, rate_per_kwh, units_in_slab, subtotal}.
    Capacity of a slab = slab_max - slab_min + 1 (inclusive bounds).
    """
    remaining = float(units)
    total = 0.0
    breakdown: list[dict] = []
    for slab in sorted(slabs, key=lambda s: s.slab_min):
        if remaining <= 0:
            break
        upper = slab.slab_max if slab.slab_max is not None else float("inf")
        capacity = upper - slab.slab_min + 1
        units_in_slab = min(remaining, capacity)
        subtotal = round(units_in_slab * slab.rate_per_kwh, 2)
        if units_in_slab > 0:
            breakdown.append(
                {
                    "slab_min": slab.slab_min,
                    "slab_max": slab.slab_max,
                    "rate_per_kwh": slab.rate_per_kwh,
                    "units_in_slab": round(units_in_slab, 2),
                    "subtotal": subtotal,
                }
            )
        total += subtotal
        remaining -= units_in_slab
    return round(total, 2), breakdown


def get_tariff_set(db: Session, name: str | None) -> TariffSet | None:
    if name:
        return db.query(TariffSet).filter(TariffSet.name == name).first()
    return None


def estimate_amount(
    tariff_set: TariffSet, kwh: float
) -> tuple[float, float, list[dict]]:
    """Return (energy_charge, fixed_charge, breakdown) for a kWh figure."""
    energy, breakdown = energy_charge(kwh, tariff_set.slabs)
    fixed = round(float(tariff_set.fixed_charge), 2)
    return energy, fixed, breakdown


def deviation(amount_actual: float, amount_estimated: float) -> float:
    """D = B_actual - B_estimated; D_% = |D| / B_actual * 100 (spec formula)."""
    d = amount_actual - amount_estimated
    if amount_actual == 0:
        return 0.0 if d == 0 else float("inf")
    return round(abs(d) / abs(amount_actual) * 100.0, 2)
