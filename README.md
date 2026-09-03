# CarbonLens — AI-Powered Carbon Footprint Tracker

A Flask web app that estimates a person's daily carbon footprint (kg CO₂/day) from travel, energy, diet, and waste habits, using a trained Random Forest regression model.

**Live demo:** _add your deployed Render URL here once live, e.g. `https://carbon-tracker.onrender.com`_

**Screenshot:** _add a screenshot of the dashboard here, e.g. `![CarbonLens dashboard](docs/screenshot.png)`_

---

## Features

* Instant daily CO₂ estimate from 8 daily-habit inputs (travel, electricity, water, diet, waste)
* Low / Medium / High emissions categorization with a tailored eco tip
* Single-page dashboard UI (dashboard, calculator, analytics, reports) — no separate CSS/JS build step
* Live `/health` endpoint surfacing model version, algorithm, and R² in the UI
* JSON export of your latest prediction

> Note: the Analytics section (contribution breakdown, weekly trend, goal progress) currently renders illustrative placeholder data — it is not yet wired to real prediction history.

---

## Architecture

```
Browser (templates/index.html)
   │  fetch()
   ▼
Flask app (app.py)
   │  GET  /         → renders templates/index.html
   │  GET  /health    → model metadata (version, algorithm, R²)
   │  POST /predict   → validates payload → pandas DataFrame → model.predict()
   ▼
joblib-loaded artifacts (models/)
   ├── model_v1.pkl          (RandomForestRegressor, R² ≈ 0.933)
   └── model_metadata.pkl    (version, algorithm, r2)
```

The entire frontend (HTML, CSS, JavaScript) lives in a single file, `templates/index.html` — there is no separate `static/` folder or build pipeline.

---

## Tech Stack

**Frontend:** HTML, CSS, vanilla JavaScript (inline in `templates/index.html`)
**Backend:** Flask (Python)
**Machine Learning:** scikit-learn `RandomForestRegressor`, pandas, joblib

---

## Project Structure

```
app.py                    Flask app: routes, validation, inference
templates/index.html      Full frontend (HTML + CSS + JS)
models/
  model_v1.pkl             Trained Random Forest model
  model_metadata.pkl       Model version / algorithm / R²
  label_encoders.pkl       Reserved for future categorical encoding
requirements.txt          Python runtime dependencies
Procfile                  Process command for Heroku-style hosts
render.yaml               Render.com deploy configuration
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

---

## Run Locally

```bash
git clone <this-repo-url>
cd "AI-Powered Carbon Footprint Tracker"

python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

> `gunicorn` (used in production, see below) depends on POSIX-only modules and will not start on native Windows — use `python app.py` for local development there. It runs normally on Render's Linux containers.

---

## Deployment (Render)

This repo is set up for Render's native Python environment:

* **`requirements.txt`** — pinned runtime dependencies, including `gunicorn`.
* **`Procfile`** — `web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2`
* **`render.yaml`** — mirrors the same build/start commands for one-click Render Blueprint deploys.

To deploy: push this repo to GitHub, then either apply the Render Blueprint (`render.yaml`) or create a new Web Service pointing at the repo — Render will run the build and start commands automatically.

---

## Future Improvements

* Real analytics: log predictions and replace the placeholder contribution/trend/progress data with actual history
* SHAP-based explainability surfaced in the `/predict` response and UI
* PDF export of results
* User accounts and historical tracking

---

## Author

Pragya Chaudhary
BTech CSE | AI & Full Stack Enthusiast
