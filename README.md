# CarbonLens — AI-Powered Carbon Footprint Tracker

A Flask web app that estimates a person's daily carbon footprint (kg CO₂/day) from travel, energy, diet, and waste habits, using a trained Random Forest regression model.

**Live demo:** _add your deployed Render URL here once live, e.g. `https://carbon-tracker.onrender.com`_

**Screenshot:** _add a screenshot of the dashboard here, e.g. `![CarbonLens dashboard](docs/screenshot.png)`_

---

## Features

* Instant daily CO₂ estimate from 8 daily-habit inputs (travel, electricity, water, diet, waste)
* Low / Medium / High emissions categorization with a tailored eco tip
* Every successful prediction is persisted (PostgreSQL in production, SQLite locally) with its inputs, result, and timestamp
* Real analytics — category breakdown, 7-day trend, and weekly goal progress — computed live from stored prediction history via `/analytics/summary` and `/analytics/history`
* Single-page dashboard UI (dashboard, calculator, analytics, reports) — no separate CSS/JS build step
* Live `/health` endpoint surfacing model version, algorithm, and R² in the UI
* JSON export of your latest prediction

---

## Architecture

```
Browser (templates/index.html)
   │  fetch()
   ▼
Flask app (app.py)
   │  GET  /                  → renders templates/index.html
   │  GET  /health             → model metadata (version, algorithm, R²)
   │  POST /predict            → validates payload → model.predict() → saves PredictionHistory row
   │  GET  /analytics/history  → recent PredictionHistory rows
   │  GET  /analytics/summary  → aggregates (avg/min/max, category distribution) over PredictionHistory
   ▼                                    ▼
joblib-loaded artifacts (models/)   SQLAlchemy → PredictionHistory table
   ├── model_v1.pkl          (RandomForestRegressor, R² ≈ 0.933)      (PostgreSQL via DATABASE_URL in
   └── model_metadata.pkl    (version, algorithm, r2)                  production, SQLite file locally)
```

The entire frontend (HTML, CSS, JavaScript) lives in a single file, `templates/index.html` — there is no separate `static/` folder or build pipeline. The Analytics section fetches `/analytics/summary` and `/analytics/history` on load and after every prediction, so its category breakdown, 7-day trend, and goal-progress ring always reflect real stored data.

---

## Tech Stack

**Frontend:** HTML, CSS, vanilla JavaScript (inline in `templates/index.html`)
**Backend:** Flask (Python)
**Database:** PostgreSQL in production (Flask-SQLAlchemy + psycopg2), SQLite fallback for local dev
**Machine Learning:** scikit-learn `RandomForestRegressor`, pandas, joblib

---

## Project Structure

```
app.py                    Flask app: routes, validation, inference, DB models, analytics
templates/index.html      Full frontend (HTML + CSS + JS)
models/
  model_v1.pkl             Trained Random Forest model
  model_metadata.pkl       Model version / algorithm / R²
  label_encoders.pkl       Reserved for future categorical encoding
carbonlens.db              SQLite dev database (auto-created, gitignored, local only)
requirements.txt          Python runtime dependencies
Procfile                  Process command for Heroku-style hosts
render.yaml               Render.com deploy configuration (web service + managed Postgres)
test_api.py               Manual smoke-test script for /predict
```

---

## API Endpoints

### `GET /`
Renders the dashboard (`templates/index.html`).

### `GET /health`
Returns model metadata used to populate the UI's status pill and KPI cards.

```json
{
  "status": "healthy",
  "model_version": "v1",
  "algorithm": "RandomForestRegressor",
  "r2": 0.933
}
```

### `POST /predict`
Body (all fields required, all numeric, none negative):

```json
{
  "Personal_Vehicle_Km": 12,
  "Public_Vehicle_Km": 8,
  "Plane_Journey_Count": 0,
  "Train_Journey_Count": 1,
  "Electricity_Kwh": 6.5,
  "Water_Usage_Liters": 120,
  "Diet_Type": 1,
  "Waste_Kg": 1.2
}
```

`Diet_Type` is encoded as `0 = Vegetarian`, `1 = Mixed`, `2 = Vegan`.

Response:

```json
{
  "prediction": 9.63,
  "unit": "kg CO₂/day",
  "category": "Medium",
  "color": "Yellow",
  "eco_tip": "Reducing personal vehicle use and improving energy efficiency could lower your estimated emissions.",
  "model_version": "v1",
  "r2": 0.933
}
```

Missing or negative fields return `400` with `{"error": "..."}`; unexpected failures return `500`.

Every successful prediction is saved as a `PredictionHistory` row (timestamp, prediction, category, and all 8 inputs). A database failure while saving is logged but does not fail the request — the caller still gets their prediction.

### `GET /analytics/history`

Query params: `limit` (optional, default `50`, max `500`).

```json
{
  "count": 2,
  "history": [
    {
      "id": 4,
      "timestamp": "2026-09-10T05:52:29.845911+00:00",
      "prediction": 30.94,
      "category": "High",
      "Personal_Vehicle_Km": 60.0,
      "Public_Vehicle_Km": 0.0,
      "Plane_Journey_Count": 2,
      "Train_Journey_Count": 0,
      "Electricity_Kwh": 20.0,
      "Water_Usage_Liters": 300.0,
      "Diet_Type": 1,
      "Waste_Kg": 4.0
    }
  ]
}
```

### `GET /analytics/summary`

Aggregates computed directly from stored predictions (no placeholders):

```json
{
  "total_predictions": 7,
  "average_emission": 14.97,
  "highest_emission": 30.94,
  "lowest_emission": 7.0,
  "category_distribution": { "Low": 2, "Medium": 3, "High": 2 }
}
```

When no predictions have been logged yet, `total_predictions` is `0`, the emission fields are `null`, and `category_distribution` is all zeros.

---

## Run Locally

```bash
git clone <this-repo-url>
cd "AI-Powered Carbon Footprint Tracker"

python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

**Database:** no setup needed for local development. If `DATABASE_URL` is not set, the app automatically falls back to a local SQLite file (`carbonlens.db`, created next to `app.py` on first run, and gitignored). Tables are created automatically at startup via `db.create_all()` — no separate migration step required for this schema.

To run against a local PostgreSQL instance instead, set `DATABASE_URL` before starting the app:

```bash
# Windows PowerShell
$env:DATABASE_URL = "postgresql://user:password@localhost:5432/carbonlens"
python app.py

# bash
export DATABASE_URL="postgresql://user:password@localhost:5432/carbonlens"
python app.py
```

To reset local data, stop the app and delete `carbonlens.db` — it will be recreated empty on the next run.

> `gunicorn` (used in production, see below) depends on POSIX-only modules and will not start on native Windows — use `python app.py` for local development there. It runs normally on Render's Linux containers.

---

## Deployment (Render)

This repo is set up for Render's native Python environment, including a managed PostgreSQL database:

* **`requirements.txt`** — pinned runtime dependencies, including `gunicorn`, `flask-sqlalchemy`, and `psycopg2-binary`.
* **`Procfile`** — `web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2`
* **`render.yaml`** — defines the web service **and** a `carbon-tracker-db` Postgres database, and wires the database's connection string into the web service's `DATABASE_URL` environment variable automatically.

**Deploying via Blueprint (recommended):** push this repo to GitHub, then apply the Render Blueprint (`render.yaml`) from the Render dashboard. Render provisions both the web service and the Postgres database, and sets `DATABASE_URL` on the web service for you — no manual environment variable entry needed. On first boot, `db.create_all()` creates the `prediction_history` table automatically.

**Deploying manually (without the Blueprint):** if you create the Web Service and Postgres database separately instead of via `render.yaml`:
1. Create a Render PostgreSQL instance.
2. On the Web Service, go to **Environment** and add `DATABASE_URL` set to that database's **Internal Connection String**.
3. Deploy — the app reads `DATABASE_URL` at startup and creates its tables automatically.

---

## Future Improvements
* SHAP-based explainability surfaced in the `/predict` response and UI
* PDF export of results
* User accounts, so prediction history is scoped per-user instead of global
* Flask-Migrate for schema migrations as the data model grows beyond `db.create_all()`

---

## Author

Pragya Chaudhary
BTech CSE | AI & Full Stack Enthusiast
