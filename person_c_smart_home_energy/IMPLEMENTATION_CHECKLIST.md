# Implementation Checklist - Person C (Smart Home Energy Monitor)

Status legend: `[x]` done with evidence - `[!]` done but flagged / unverified -
`[ ]` not done.

## Backend (FastAPI + SQLAlchemy + SQLite)

- [x] Own SQLite database file `data/smart_home_energy.db` (never shared) - `database.py`
- [x] Models: Appliance / UsageReading (unique per appliance+date) / TariffSet /
      TariffSlab / ActualBill (unique month) - `models.py`
- [x] Pydantic v2 contracts with explicit status fields - `schemas.py`
- [x] CRUD layer isolated from routers - `crud.py`
- [x] `GET /health` with DB probe - `routers/system.py`
- [x] Appliance CRUD with validation (kW > 0, quantity >= 1, hours in [0,24]) - `routers/appliances.py`
- [x] `POST /readings` UPSERT per (appliance, date); E_kWh = P x qty x t - `routers/readings.py`
- [x] `POST /readings/bulk-default` idempotent day-fill (documented extension)
- [x] `GET /consumption/daily` (single day / range / rolling window, max 92 days)
- [x] `GET /consumption/monthly?months=N`
- [x] `GET /bill/estimate?month=` marginal slab computation + breakdown - `routers/billing.py`
- [x] `POST /bill/actual` upsert per month
- [x] `GET /bill/compare?month=` D + D_% = |D|/B_actual x 100 + threshold + disclaimer
- [x] `GET /history?months=N` most-recent-first estimate-vs-actual
- [x] `GET /tariffs` with honest `verified: false` flags + notes
- [x] `GET /integrations/status` self-describing consumer info
- [x] 12-factor config (threshold + default tariff) - `config.py`

## Correctness proofs (pytest, all passing)

- [x] Exact slab math: 120 kWh -> 50x0 + 50x2.35 + 20x4.70 = 211.50 (slab off-by-one bug found & fixed during QA)
- [x] D_% math: est 211.50 vs actual 500 -> D_amount 288.50, D_% 57.7 -> needs_investigation
- [x] kWh-basis fallback when estimated amount is 0 (free-slab month): |26-24|/26 = 7.69%
- [x] Reading upsert (same day twice -> single row, updated kWh)
- [x] Bulk-default idempotency (second run: created 0)
- [x] `no_data` / `no_actual` / `no_estimate` status paths (valid zeros, no 500s)
- [x] Validation: hours > 24 -> 422; bad month format -> 422; unknown appliance -> 404
- [x] 19 tests total - `python -m pytest -q` -> `19 passed`

## Integration (exposing the contract)

- [x] `GET /history?months=6` is the stable endpoint Person A consumes
- [x] No shared database files - C never opens A's or B's data
- [x] Live smoke test: A imported C's actual bill for 2026-09 (1250.00) as a
      Bills expense; re-sync imported 0 - see `docs/FINAL_VERIFICATION_REPORT.md`
- [x] Streamlit boot check: `/_stcore/health` -> ok

## Frontend (Streamlit)

- [x] Dashboard: month KPIs + estimate cards + UNVERIFIED tariff warning
- [x] Appliances: table + add form + delete (cascades readings)
- [x] Readings: per-appliance logger (upsert) + bulk day-fill + recent table
- [x] Consumption: daily bar chart with breakdown + monthly line chart
- [x] Billing: estimate + slab table, actual-bill form, compare with deviation
      gauge + investigation banner, tariff viewer with UNVERIFIED badges
- [x] History: table + grouped bars + flagged-months callout
- [x] UI is a pure REST client - `ui_common.py`

## Documentation & packaging

- [x] `README.md` (features, formulas, honesty section, limitations)
- [x] `ENVIRONMENT_SETUP.md` (PowerShell + zsh, demo tips, troubleshooting)
- [x] `API_DOCUMENTATION.md` (every endpoint + worked examples incl. full slab breakdown)
- [x] `RENDER_DEPLOYMENT.md` (two services, disk caveats, A-wiring)
- [x] `.env.example` placeholders only; `.gitignore` covers `.env`, `data/*.db`, caches
- [x] `seed_data.py` (tariffs + 8 appliances + 60 days readings + 2 actual bills, idempotent)

## Flagged / unverified (the honesty section)

- [!] TNEB/TANGEDCO slab values are UNVERIFIED seeds - every response using
      them carries `verified: false` and a "verify against the official
      tariff order" note. Fixed charge seeded at 0.00 pending verification.
- [!] Monthly tariff set is derived by halving bi-monthly thresholds -
      explicitly documented as an approximation, not an official tariff.
- [!] Deviation flags are investigation signals only (disclaimer embedded in
      every compare/history response); they cannot prove a meter fault.
- [ ] Solar / net-metering / duty charges - out of scope, documented.
