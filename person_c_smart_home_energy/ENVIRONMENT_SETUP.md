# Environment Setup - Person C (Smart Home Energy Monitor)

Target: Python **3.11 or 3.12** (tested on 3.12). No database server needed -
the app uses its own SQLite file under `data/`.

---

## Windows (PowerShell)

```powershell
# 1. Verify Python
python --version          # expect 3.11+

# 2. Create and activate a virtual environment (inside the project folder)
cd person_c_smart_home_energy
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# If script execution is blocked:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 3. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Configuration
Copy-Item .env.example .env
# Optional: tune DEVIATION_THRESHOLD_PERCENT / DEFAULT_TARIFF

# 5. Seed demo data (recommended: 8 appliances + 60 days of readings + 2 actual bills)
python seed_data.py

# 6. Run the backend (keep this terminal open)
uvicorn main:app --host 127.0.0.1 --port 8003 --reload

# 7. Run the frontend in a SECOND terminal (activate venv first)
.\.venv\Scripts\Activate.ps1
$env:API_BASE_URL = "http://127.0.0.1:8003"
streamlit run app.py
```

Dashboard: <http://localhost:8503> - API docs: <http://127.0.0.1:8003/docs>

## macOS (zsh)

```zsh
# 1. Verify Python
python3 --version         # expect 3.11+

# 2. Create and activate a virtual environment (inside the project folder)
cd person_c_smart_home_energy
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
python3 -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Configuration
cp .env.example .env

# 5. Seed demo data (recommended)
python seed_data.py

# 6. Run the backend (keep this terminal open)
uvicorn main:app --host 127.0.0.1 --port 8003 --reload

# 7. Run the frontend in a SECOND terminal (activate venv first)
source .venv/bin/activate
export API_BASE_URL="http://127.0.0.1:8003"
streamlit run app.py
```

## Running all three teammates' apps together (integration demo)

| App | Backend port | Frontend port |
|---|---|---|
| B - Subscription Tracker | 8002 | 8502 |
| **C - this app** | 8003 | 8503 |
| A - Expense & Budget | 8001 | 8501 |

Start all backends, then in Person A's `.env` set
`INTEGRATION_C_BASE_URL=http://127.0.0.1:8003`. A's sync imports the most
recent electricity bill (actual if recorded, else the last closed month's
estimate) as a `Bills` expense.

**Demo tip**: the seed intentionally leaves the CURRENT month without an
actual bill, so you can demonstrate the `no_actual` path, then record the
"real" bill via the dashboard and show the deviation/investigation flow.

## Tests

```bash
python -m pytest -q          # 19 tests, uses a throwaway SQLite file
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Activate.ps1 cannot be loaded` | PowerShell policy - see step 2 comment. |
| Estimate says `no_tariff` | Tariff sets missing - run `python seed_data.py` (idempotent) and check `GET /tariffs`. |
| Estimate says `no_data` | No readings for that month - log some (or use bulk-default). |
| "UNVERIFIED" warnings everywhere | By design: seeded slabs are placeholders; edit tariff rows after verifying the official TNEB order. |
| Streamlit shows "Cannot reach API" | Backend not running, or `API_BASE_URL` mismatch. |
| Port 8003 already in use | Change `--port` (and restart the UI with matching `API_BASE_URL`). |
