# Render Deployment Guide - Person C (Smart Home Energy Monitor)

Deploy **two Render services from this one repository**: the FastAPI backend
and the Streamlit dashboard.

## 0. Prerequisites

- The project pushed to a GitHub repo (e.g. `csi3007-smart-home-energy-monitor`),
  repo root = this folder (`main.py` at top level).
- A free Render account.

## 1. Service 1 - REST API

1. **New +** -> **Web Service** -> connect the repo.
2. Settings:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free (or any)
3. Environment variables:

   | Key | Value |
   |---|---|
   | `SERVICE_NAME` | `smart-home-energy-monitor` |
   | `DATABASE_URL` | `sqlite:////data/smart_home_energy.db` (needs a disk, see below) |
   | `DEVIATION_THRESHOLD_PERCENT` | `10.0` |
   | `DEFAULT_TARIFF` | `TNEB-Domestic-Monthly-Seed` |

4. **Persistent disk**: SQLite needs writable storage. Add a Disk (mount
   `/data`, 1 GB) on a paid instance; on Free tier the DB resets on deploy
   (fine for demos, documented honestly).
5. Deploy, then verify `https://<api-host>/health` -> `{"status": "ok", ...}`.
   Tariff sets seed automatically on startup (idempotent, `verified: false`).
6. Optional: run the seed for demo readings by adding a one-off **Shell**
   command on a paid instance (`python seed_data.py`) or POST readings via
   `/docs`.

## 2. Service 2 - Streamlit dashboard

1. **New +** -> **Web Service** -> same repo.
2. Settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`
3. Environment variables:

   | Key | Value |
   |---|---|
   | `API_BASE_URL` | `https://<api-host-from-step-1>` |

4. Deploy and open the dashboard.

## 3. Wiring Person A to this app

Copy this API's public URL into Person A's environment (both of A's
services):

```
INTEGRATION_C_BASE_URL=https://<this-api-host>.onrender.com
```

A's sync then imports the most recent **actual** bill; if none exists yet it
uses the most recent **completed month's estimate** (stable external ids
`C:actual:{month}` / `C:estimated:{month}` prevent duplicates).

> Reminder: keep this API's `DEFAULT_TARIFF` verified before trusting the
> amounts A imports - see the UNVERIFIED notes in `README.md`.

## 4. Verification checklist

- [x] `GET /health` -> `status: ok`, `database: connected`
- [x] `GET /tariffs` -> two seeded sets, `verified: false` + honest notes
- [x] Create an appliance, POST a reading, see `kwh` = kW x quantity x hours
- [x] `GET /bill/estimate` -> slab breakdown with UNVERIFIED note
- [x] `POST /bill/actual`, then `GET /bill/compare` -> D_% math + disclaimer
- [x] `GET /history?months=6` -> most-recent-first rows
- [x] Dashboard loads and renders the same numbers

## 5. Free-tier caveats (stated honestly)

- Free services sleep after ~15 min idle; first request wakes them
  (~30-60 s). Person A's sync across sleeping services may need a higher
  `INTEGRATION_TIMEOUT_SECONDS` (A defaults to 3 s, configurable).
- Free tier has no persistent disks -> SQLite is ephemeral there.
- `allow_origins=["*"]` CORS is deliberate for the course demo; restrict it
  for real deployments.
