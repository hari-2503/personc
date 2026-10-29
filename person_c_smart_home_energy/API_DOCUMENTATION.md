# API Documentation - Person C (Smart Home Energy Monitor API)

- Base URL (local): `http://127.0.0.1:8003`
- Interactive OpenAPI docs: `http://127.0.0.1:8003/docs`
- Auth: none (course demo scope)
- Content type: `application/json`
- Status semantics: data absence is reported via explicit `status` fields
  (`no_data`, `no_actual`, `no_estimate`, `no_tariff`) so "valid zero" is
  never confused with "missing" or "broken".

---

## System

### `GET /health`
```json
{
  "status": "ok",
  "service": "smart-home-energy-monitor",
  "owner": "Person C - Hariharan S (23MID0182)",
  "version": "1.0.0",
  "database": "connected",
  "time": "2026-10-28T13:34:56.532990+00:00"
}
```

### `GET /integrations/status`
Self-describing status for consumers (Person A polls `/history?months=6`):

```json
{
  "service": "smart-home-energy-monitor", "version": "1.0.0", "status": "ok",
  "appliances_count": 8, "active_appliances_count": 8, "readings_count": 480,
  "months_with_data": ["2026-08", "2026-09", "2026-10"],
  "default_tariff": "TNEB-Domestic-Monthly-Seed",
  "latest_month_summary": {"month": "2026-10", "estimated_kwh": 213.5,
                            "estimated_amount": 453.45, "status": "ok"},
  "export_endpoints": ["/consumption/monthly", "/bill/estimate", "/history"]
}
```

## Appliances

### `POST /appliances` -> 201
```bash
curl -X POST http://127.0.0.1:8003/appliances \
  -H "Content-Type: application/json" \
  -d '{"name": "Air Conditioner 1.5T", "room": "Bedroom", "rated_power_kw": 1.5,
       "quantity": 1, "typical_hours_per_day": 5.0}'
```

Validation: `rated_power_kw` > 0; `quantity` >= 1; `typical_hours_per_day`
in [0, 24]. Violations -> 422.

### `GET /appliances` (filter `active=true|false`)
### `GET /appliances/{id}` -> 200 | 404
### `PUT /appliances/{id}` -> 200 (partial update)
### `DELETE /appliances/{id}` -> 200
Deletes the appliance AND its readings:
```json
{"deleted": true, "id": 3, "readings_deleted": 60}
```

## Usage readings

Energy per reading: **E_kWh = rated_power_kw x quantity x hours_used**
(`hours_used` = average operating hours per unit that day).

### `POST /readings` -> 200 (UPSERT)
Posting the same `(appliance_id, reading_date)` again updates the hours -
the API never accumulates duplicate rows for a day.

```bash
curl -X POST http://127.0.0.1:8003/readings \
  -H "Content-Type: application/json" \
  -d '{"appliance_id": 1, "reading_date": "2026-10-27", "hours_used": 5.5}'
```

```json
{"id": 473, "appliance_id": 1, "appliance_name": "LED Lights",
 "reading_date": "2026-10-27", "hours_used": 5.5, "source": "manual", "kwh": 2.64}
```

Validation: `hours_used` in [0, 24]; unknown appliance -> 404.

### `POST /readings/bulk-default` (convenience extension)
Fills a date for every ACTIVE appliance using its `typical_hours_per_day`;
existing rows are skipped (idempotent day-fill):

```json
{"reading_date": "2026-10-27", "created": 8, "skipped": 0,
 "details": [{"appliance_id": 1, "name": "LED Lights", "action": "created"}]}
```

### `GET /readings?start=&end=&appliance_id=&limit=`
Recent readings, newest first, each including computed `kwh`.

## Consumption

### `GET /consumption/daily`
Three ways to call it: `?date=YYYY-MM-DD` (single day), `?start=&end=`
(explicit range, max 92 days), or `?days=7` (rolling window). Days without
readings are omitted - missing data is not zero usage.

```json
{
  "start_date": "2026-10-27", "end_date": "2026-10-27",
  "days": [{"date": "2026-10-27", "total_kwh": 21.84,
            "by_appliance": [
              {"appliance_id": 4, "name": "Air Conditioner 1.5T",
               "hours_used": 5.1, "kwh": 7.65} ] }]
}
```

### `GET /consumption/monthly?months=6`
Monthly totals (most recent with data first) + `days_with_data` coverage.

## Billing

### `GET /bill/estimate?month=YYYY-MM`
Applies the configured tariff set (env `DEFAULT_TARIFF`) marginally:
slabs are 1-based inclusive ranges (1-50 free, 51-100 @ 2.35, ...) and the
top slab may be open-ended. Includes the full breakdown.

```json
{
  "month": "2026-09", "status": "ok",
  "tariff_name": "TNEB-Domestic-Monthly-Seed", "tariff_verified": false,
  "estimated_kwh": 420.0, "energy_charge": 1369.75, "fixed_charge": 0.0,
  "estimated_amount": 1369.75, "currency": "INR",
  "slab_breakdown": [
    {"slab_min": 1, "slab_max": 50, "rate_per_kwh": 0.0, "units_in_slab": 50, "subtotal": 0.0},
    {"slab_min": 51, "slab_max": 100, "rate_per_kwh": 2.35, "units_in_slab": 50, "subtotal": 117.5},
    {"slab_min": 101, "slab_max": 200, "rate_per_kwh": 4.7, "units_in_slab": 100, "subtotal": 470.0},
    {"slab_min": 201, "slab_max": 250, "rate_per_kwh": 6.3, "units_in_slab": 50, "subtotal": 315.0},
    {"slab_min": 251, "slab_max": 300, "rate_per_kwh": 8.4, "units_in_slab": 50, "subtotal": 420.0},
    {"slab_min": 301, "slab_max": 400, "rate_per_kwh": 9.45, "units_in_slab": 100, "subtotal": 945.0},
    {"slab_min": 401, "slab_max": 500, "rate_per_kwh": 10.5, "units_in_slab": 20, "subtotal": 210.0}
  ],
  "note": "Tariff rates are UNVERIFIED seed values - confirm against the official TNEB/TANGEDCO tariff order"
}
```

Statuses: `ok` | `no_data` (zero readings -> estimated_kwh 0.0, valid zero)
| `no_tariff` (kwh known, no tariff set found).

### `POST /bill/actual` -> 200 (UPSERT per month)
```bash
curl -X POST http://127.0.0.1:8003/bill/actual \
  -H "Content-Type: application/json" \
  -d '{"month": "2026-09", "kwh_actual": 412.0, "amount_actual": 1340.0,
       "notes": "From the electricity board bill"}'
```

### `GET /bill/compare?month=YYYY-MM`
**D = B_actual - B_estimated;  D_% = |D| / B_actual x 100** (spec formula).
Amount basis when the estimate is meaningful; kWh basis otherwise.

```json
{
  "month": "2026-09", "status": "ok",
  "estimated_kwh": 420.0, "actual_kwh": 412.0, "D_kwh": -8.0,
  "estimated_amount": 1369.75, "actual_amount": 1340.0, "D_amount": -29.75,
  "deviation_percent": 2.22, "deviation_basis": "amount",
  "threshold_percent": 10.0, "needs_investigation": false,
  "disclaimer": "Deviation is only an investigation signal. It does NOT prove a faulty meter: usage-pattern changes, seasonal loads, tariffs, meter-reading dates and estimation error can all explain a gap.",
  "suggested_action": null
}
```

When `needs_investigation` is true, `suggested_action` points the analyst at
`GET /history?months=6` (persistent gap = systematic cause; one-off gap =
usually usage or reading-date shift). Statuses `no_data`, `no_actual`,
`no_estimate` return the available side with the disclaimer - never a 500.

### `GET /history?months=6`
Last N calendar months, most recent first, estimate vs actual + deviation
flag per month. **Consumed by Person A.**

```json
{"months": [
  {"month": "2026-10", "estimated_kwh": 213.5, "actual_kwh": null,
   "estimated_amount": 453.45, "actual_amount": null,
   "deviation_percent": null, "needs_investigation": false},
  {"month": "2026-09", "estimated_kwh": 420.0, "actual_kwh": 412.0,
   "estimated_amount": 1369.75, "actual_amount": 1340.0,
   "deviation_percent": 2.22, "needs_investigation": false} ]}
```

## Tariffs

### `GET /tariffs`
All tariff sets with their `verified` flag. Seeded sets are **UNVERIFIED**
placeholders (bimonthly TNEB slabs + a monthly approximation derived by
halving thresholds) - the notes explain exactly what to verify and against
which official source.

```json
{
  "default_tariff": "TNEB-Domestic-Monthly-Seed",
  "tariffs": [
    {"name": "TNEB-Domestic-Monthly-Seed", "billing_cycle": "monthly",
     "fixed_charge": 0.0, "currency": "INR", "verified": false,
     "notes": "UNVERIFIED seed: derived from the TNEB bi-monthly domestic slabs by halving unit thresholds (approximation - NOT an official monthly tariff). Verify against the latest official tariff order before use.",
     "slabs": [{"slab_min": 1, "slab_max": 50, "rate_per_kwh": 0.0},
               {"slab_min": 51, "slab_max": 100, "rate_per_kwh": 2.35} ]}
  ]
}
```
