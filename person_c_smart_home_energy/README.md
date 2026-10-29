# Smart Home Electricity Monitoring & Bill Estimation (Person C)

CSI3007 - Advanced Python Programming | Person C: **Hariharan S (23MID0182)**

A home-energy tracker that logs appliance operating hours, converts them to
energy with the physics model **E_kWh = P_kW x t_hours**, aggregates daily /
monthly consumption, estimates bills from **configurable TNEB-style tariff
slabs**, and compares estimated vs actual bills with the deviation signal
**D = B_actual - B_estimated**, **D_% = |D| / B_actual x 100**.

```
   Person C (this app) ──GET /history?months=6──► Person A
   (consumption + bill estimates)                 imports the electricity bill
```

## Honesty first (course discipline)

- Seeded tariff slabs are **UNVERIFIED** best-effort representations of the
  TNEB/TANGEDCO domestic tariff (2023-24 era). Every response that uses them
  carries `verified: false` plus a "verify against the official tariff order"
  note (`GET /tariffs`, `/bill/estimate`, dashboard warning). Nothing here
  pretends an approximate rate is the official one.
- A deviation above threshold is an **investigation signal only** - the API's
  own response text states it can never prove a faulty meter (usage changes,
  seasonal loads, reading dates and tariff changes explain most gaps).

## Features

- **Appliances**: rated power (kW), quantity, room, typical hours/day, active flag.
- **Usage readings**: hours-per-unit per appliance per day, **upsert**
  semantics (re-posting a day updates it). Energy per reading =
  `rated_power_kw x quantity x hours_used`. Bulk helper fills a whole day
  from each appliance's typical hours.
- **Consumption analytics**: daily totals with per-appliance breakdown
  (single day, explicit range, or rolling window) and monthly totals.
- **Bill estimation**: month's kWh -> marginal slab computation with a full
  breakdown (units in each slab x rate), plus the tariff's fixed charge.
  Statuses distinguish `ok` / `no_data` / `no_tariff`.
- **Actual bills**: record the real bill per month (`POST /bill/actual`,
  upsert per month).
- **Deviation analysis**: `GET /bill/compare` computes D (kWh and amount),
  `D_% = |D| / B_actual x 100`, compares against the configurable threshold
  (`DEVIATION_THRESHOLD_PERCENT`, default 10%) and flags
  `needs_investigation` with the 6-month-history suggestion. When the
  estimate amount is zero (usage fully inside a free slab), the comparison
  sensibly falls back to the kWh basis.
- **6-month history**: `GET /history?months=6` - estimate vs actual per
  calendar month with deviation flags (most recent first). **This is the
  endpoint Person A consumes.**
- **Streamlit dashboard**: month KPIs, estimate cards with slab table,
  actual-bill form, deviation gauge with investigation warnings, appliance
  CRUD, reading logger + bulk fill, daily/monthly charts, history comparison
  bars, tariff viewer with UNVERIFIED badges.

## Tech stack

| Layer     | Technology |
|-----------|------------|
| Backend   | Python 3.12, FastAPI, Pydantic v2 |
| Database  | SQLite via SQLAlchemy 2 (own file: `data/smart_home_energy.db`) |
| Frontend  | Streamlit + Plotly (pure REST client) |
| Testing   | pytest + FastAPI TestClient (19 tests) |
| Deploy    | Render (see `RENDER_DEPLOYMENT.md`) |

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                 # placeholders only
python seed_data.py                  # tariffs + 8 appliances + 60 days of readings

uvicorn main:app --host 127.0.0.1 --port 8003 --reload   # terminal 1
streamlit run app.py                                      # terminal 2

python -m pytest -q
```

Interactive API docs: <http://127.0.0.1:8003/docs>

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/smart_home_energy.db` | Own SQLite file (never shared) |
| `APP_PORT` | `8003` | Backend port |
| `API_BASE_URL` (frontend) | `http://127.0.0.1:8003` | Where Streamlit finds the API |
| `DEVIATION_THRESHOLD_PERCENT` | `10.0` | D_% above which a month is flagged for investigation |
| `DEFAULT_TARIFF` | `TNEB-Domestic-Monthly-Seed` | Tariff set used by `/bill/estimate` |

## API summary

Full reference with examples: `API_DOCUMENTATION.md`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness + DB probe |
| GET/POST | `/appliances` | List / register appliance |
| GET/PUT/DELETE | `/appliances/{id}` | Read / update / delete (cascades readings) |
| POST | `/readings` | Upsert hours for (appliance, date) |
| POST | `/readings/bulk-default` | Fill a day from typical hours (extension) |
| GET | `/readings` | Recent readings |
| GET | `/consumption/daily` | Daily kWh + per-appliance breakdown |
| GET | `/consumption/monthly` | Monthly kWh totals |
| GET | `/bill/estimate?month=` | Slab-based estimate + breakdown |
| POST | `/bill/actual` | Record the real bill (upsert per month) |
| GET | `/bill/compare?month=` | D, D_% , investigation flag + disclaimer |
| GET | `/history?months=6` | Estimate vs actual per month (consumed by A) |
| GET | `/tariffs` | Tariff sets with verified flags |
| GET | `/integrations/status` | Self-describing status for consumers |

## Project structure

```
person_c_smart_home_energy/
├── main.py                    # FastAPI app + lifespan (seeds tariff sets)
├── config.py                  # 12-factor env-var settings
├── database.py                # SQLAlchemy engine/session (own SQLite file)
├── models.py                  # Appliance / UsageReading / TariffSet / TariffSlab / ActualBill
├── schemas.py                 # Pydantic v2 contracts
├── crud.py                    # All DB access
├── routers/
│   ├── appliances.py          # /appliances CRUD
│   ├── readings.py            # /readings upsert + bulk-default
│   ├── consumption.py         # /consumption/daily + /monthly
│   ├── billing.py             # /bill/*, /history, /tariffs
│   └── system.py              # /health, /integrations/status
├── services/
│   ├── tariff.py              # Marginal slab math + D_% formula
│   └── analytics.py           # Daily/monthly aggregation + history
├── app.py                     # Streamlit frontend (REST client)
├── ui_common.py               # HTTP helpers for the frontend
├── seed_data.py               # UNVERIFIED tariffs + 60 days of demo readings
├── tests/                     # pytest suite (incl. exact slab-math proofs)
├── .env.example               # Placeholders ONLY
└── requirements.txt
```

## The billing model (documented formulas)

- Energy per reading: `E_kWh = P_kW x quantity x t_hours`
- Month estimate: sum of reading energies -> marginal slab application
  (slabs are 1-based inclusive ranges, e.g. 1-50 free, 51-100 @ 2.35, ...) ->
  energy charge + fixed charge = estimated amount.
- Deviation: `D = B_actual - B_estimated`; `D_% = |D| / B_actual x 100`
  (amount basis when meaningful, kWh basis otherwise - documented).
- Investigation threshold: configurable; flagged months get an actionable
  hint pointing at `GET /history?months=6`.

## Known limitations & unverified items

- [!] Tariff slabs are UNVERIFIED seeds (see `GET /tariffs` notes and every
  estimate response). Verify against the latest official TNEB/TANGEDCO
  notification before trusting amounts; fixed charge is seeded at 0.
- The monthly seed set approximates TNEB's bi-monthly slabs by halving unit
  thresholds - explicitly labeled as an approximation, not an official tariff.
- Readings are per-appliance hours (no smart-meter integration); the estimate
  is only as good as the logged hours.
- Solar/net-metering, duty charges and subsidies beyond the free slab are out
  of scope.

## Git quickstart (GitHub-ready)

```bash
git init
git add .
git commit -m "CSI3007 Person C: smart home energy monitor"
git branch -M main
git remote add origin https://github.com/<your-user>/csi3007-smart-home-energy-monitor.git
git push -u origin main
```
