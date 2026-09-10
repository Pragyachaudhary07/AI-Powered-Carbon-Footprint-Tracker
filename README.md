# CarbonLens — AI-Powered Carbon Footprint Tracker

A Flask web app that estimates a person's daily carbon footprint (kg CO₂/day) from travel, energy, diet, and waste habits, using a trained Random Forest regression model.

**Live demo:** _add your deployed Render URL here once live, e.g. `https://carbon-tracker.onrender.com`_

**Screenshot:** _add a screenshot of the dashboard here, e.g. `![CarbonLens dashboard](docs/screenshot.png)`_

---

## Features

* Instant daily CO₂ estimate from 8 daily-habit inputs (travel, electricity, water, diet, waste)
* Low / Medium / High emissions categorization with a tailored eco tip
* **Sign in with Google** (OAuth2 via Flask-Dance) — no passwords anywhere in this app, nothing to reset or leak
* Guests can use the calculator and get a live estimate with zero sign-in, but nothing is saved for them — sign in to build a history
* Every successful prediction from a signed-in user is persisted (PostgreSQL in production, SQLite locally) under their account, with its inputs, result, and timestamp
* Real analytics — category breakdown, 7-day trend, and weekly goal progress — computed live from that user's stored prediction history via `/analytics/summary`, `/analytics/history`, and `/analytics/latest`, and strictly isolated per user at the database query level
* Refreshing the page restores your latest saved prediction (gauge, badge, eco tip) automatically — no need to recalculate
* Dedicated Profile page (account details + lifetime emission stats) and History page (full, searchable prediction log)
* Single-page dashboard UI (dashboard, calculator, analytics, reports) — no separate CSS/JS build step
* Live `/health` endpoint surfacing model version, algorithm, and R² in the UI
* JSON export of your latest prediction

---

## Architecture

```
Browser (templates/*.html)
   │  fetch() / navigation
   ▼
Flask app (app.py)
   │  GET  /                     → landing page + dashboard (public)
   │  GET  /login                 → "Continue with Google" page (public)
   │  GET  /login/google           → Flask-Dance: redirects to accounts.google.com
   │  GET  /login/google/authorized → Flask-Dance's OAuth callback (handled internally;
   │                                   fires the oauth_authorized signal → google_logged_in())
   │  GET  /logout                 → clears session                                       [login required]
   │  GET  /profile, /history      → account pages                                        [login required]
   │  GET  /health                → model metadata (public)
   │  POST /predict                → model.predict() always; saves a PredictionHistory row
   │                                   for current_user only if signed in — guests get a
   │                                   result with nothing persisted                       [public]
   │  GET  /analytics/history      → current_user's PredictionHistory rows                 [login required]
   │  GET  /analytics/summary      → aggregates over current_user's PredictionHistory rows  [login required]
   │  GET  /analytics/latest       → current_user's single most recent prediction           [login required]
   ▼                                    ▼
joblib-loaded artifacts (models/)   SQLAlchemy → User, PredictionHistory (FK: user_id → User.id)
   ├── model_v1.pkl          (RandomForestRegressor, R² ≈ 0.933)      (PostgreSQL via DATABASE_URL in
   └── model_metadata.pkl    (version, algorithm, r2)                  production, SQLite file locally)
```

**How Google sign-in works, end to end:** clicking "Sign in with Google" (navbar, or the button on `/login`) hits Flask-Dance's `/login/google`, which redirects the browser to Google's real OAuth consent screen. After the user approves, Google redirects back to `/login/google/authorized`, which Flask-Dance handles automatically — it exchanges the code for a token and fires the `oauth_authorized` signal. `google_logged_in()` in `app.py` catches that signal, calls Google's `userinfo` endpoint for the profile (id, email, name, picture), and either finds the matching `User` by `google_id`, links to an existing account by `email` (so anyone who used the old password-based version of this app keeps their history), or creates a new `User` — then calls Flask-Login's `login_user()`. No password is ever collected, stored, or checked anywhere in the app.

The frontend is still plain HTML/CSS/JS with no build step, spread across five Jinja templates: `index.html` (landing/dashboard), `login.html`, `profile.html`, `history.html` (there's no `signup.html` — Google sign-in unifies signup and login into one action: the first time someone signs in, `google_logged_in()` creates their account). They share one design system via server-side includes — `templates/_head_style.html` (all CSS), `templates/_navbar.html` (nav bar, auth-aware: "Sign in with Google" button for guests, an avatar/initials + name + Profile/History/Logout dropdown for signed-in users), `templates/_footer_toast.html`, and `templates/_shared_scripts.html` (toast/nav-toggle/reveal JS every page needs) — so the premium theme and navbar only exist in one place. The Analytics section on the dashboard fetches `/analytics/summary`, `/analytics/history`, and `/analytics/latest` on load (only when signed in — guests get the empty-state UI without ever calling these endpoints) and after every prediction.

---

## Tech Stack

**Frontend:** HTML, CSS, vanilla JavaScript (inline per template, shared via Jinja includes)
**Backend:** Flask (Python)
**Auth:** Google Sign-In via Flask-Dance (OAuth2) + Flask-Login (session management) — no password storage, no `generate_password_hash`/hashing code in this app at all
**Database:** PostgreSQL in production (Flask-SQLAlchemy + psycopg2), SQLite fallback for local dev, Flask-Migrate/Alembic for schema migrations
**Machine Learning:** scikit-learn `RandomForestRegressor`, pandas, joblib

---

## Project Structure

```
app.py                          Flask app: routes, Google OAuth, validation, inference, DB models, analytics
templates/
  index.html                     Landing page + dashboard (calculator, analytics, reports)
  login.html                     "Continue with Google" page
  profile.html                   Account page (details + lifetime stats)
  history.html                   Full searchable prediction history
  _head_style.html                Shared <style> block (design tokens, every component)
  _navbar.html                    Shared nav bar (auth-aware: Google button vs. user dropdown)
  _footer_toast.html              Shared footer + toast notification region
  _shared_scripts.html            Shared JS: toasts, nav toggle, user-menu dropdown, reveal animation
migrations/                     Flask-Migrate/Alembic scaffold
  versions/                       Migration scripts: (1) adds users table + prediction_history.user_id,
                                    (2) switches users to Google OAuth (+google_id/avatar_url, -password_hash)
models/
  model_v1.pkl                    Trained Random Forest model
  model_metadata.pkl              Model version / algorithm / R²
  label_encoders.pkl              Reserved for future categorical encoding
carbonlens.db                   SQLite dev database (auto-created under instance/, gitignored, local only)
requirements.txt                Python runtime dependencies
Procfile                        Process command for Heroku-style hosts
render.yaml                     Render.com deploy configuration (web service + managed Postgres + migrations)
test_api.py                     Manual smoke-test script for /predict
```

---

## API Endpoints

### `GET /`
Renders the landing page / dashboard (`templates/index.html`). Fully public — guests can browse it **and** use the calculator; only saving a result to history requires signing in.

### `GET /login`
Renders `templates/login.html` — a single "Continue with Google" button (no form, no password field anywhere). Redirects to `/` if already signed in.

### `GET /login/google` and `GET /login/google/authorized`
Provided automatically by the Flask-Dance blueprint registered in `app.py` (`make_google_blueprint(..., url_prefix="/login")`) — not hand-written routes. The first redirects to Google's consent screen; the second is where Google redirects back to after the user approves, and it's handled entirely by Flask-Dance internally (token exchange), which then fires the `oauth_authorized` signal.

`google_logged_in()` (the signal handler in `app.py`) is where the app's own logic runs: it calls Google's `userinfo` endpoint, then finds-or-creates the `User` —
1. look up by `google_id` (returning user),
2. else look up by `email` (an account that pre-dates Google Sign-In — this is what lets anyone who signed up under the old password-based version keep their account and history),
3. else create a new `User`.

Then `login_user()` starts the session. No route here ever sees or stores a password.

### `GET /logout`
Clears the session (`logout_user()`) and redirects to `/`. Requires login.

### `GET /profile`
Renders the profile page: name, email, joined date (from `current_user`, server-rendered) plus total/average/highest/lowest emissions (fetched client-side from `/analytics/summary`, so the numbers are never duplicated server-side). Requires login.

### `GET /history`
Renders a searchable table of the current user's full prediction history (fetched client-side from `/analytics/history?limit=500`; search filters client-side across category, date, and value). Requires login.

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
**Public — works for guests.** The model doesn't care who's asking; a guest gets exactly the same estimate a signed-in user would. The only difference is what happens after: if `current_user.is_authenticated`, the result is also saved as a `PredictionHistory` row; if not, nothing is persisted and there's no way to retrieve that estimate again later.

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

When signed in, every successful prediction is saved as a `PredictionHistory` row (timestamp, prediction, category, all 8 inputs, and the `user_id` of whoever was signed in). A database failure while saving is logged but does not fail the request — the caller still gets their prediction either way.

### `GET /analytics/history`
**Requires login.** Returns only the current user's rows — another user's predictions are never visible, at the database query level (`filter_by(user_id=current_user.id)`), not just hidden in the UI.

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
**Requires login.** Aggregates computed directly from the current user's stored predictions only (no placeholders, no cross-user data):

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

### `GET /analytics/latest`
**Requires login.** The current user's single most recent prediction (or `null`) — this is what the dashboard calls to restore the gauge/badge/eco-tip/result-card on page load, so a refresh always shows your latest saved result without recalculating anything.

```json
{ "latest": { "id": 4, "timestamp": "2026-09-10T05:52:29+00:00", "prediction": 30.94, "category": "High", "...": "...all 8 inputs" } }
```

or, if the user has never saved a prediction:

```json
{ "latest": null }
```

---

## Run Locally

```bash
git clone <this-repo-url>
cd "AI-Powered Carbon Footprint Tracker"

python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`. The landing page and calculator work immediately with zero configuration — you'll just get a Google error page if you click "Sign in with Google" before setting up OAuth credentials (see **Google OAuth Setup** below). Guests can still get live predictions in the meantime; they just won't be saved.

**Database:** no setup needed for a brand-new clone. If `DATABASE_URL` is not set, the app falls back to a local SQLite file (created automatically the first time the app runs, at `instance/carbonlens.db` — Flask resolves relative `sqlite:///` URIs against its `instance/` folder, not the project root; the whole `instance/` folder is gitignored). Tables are created automatically at startup via `db.create_all()`.

**Upgrading an existing database** (one from before this Google Sign-In change, or even from before user accounts existed at all): `db.create_all()` only creates *missing* tables — it never alters one that already exists — so an older database won't automatically gain new columns. Run the migrations once to bring it up to date:

```bash
# Windows PowerShell
$env:FLASK_APP = "app.py"
python -m flask db upgrade

# bash
export FLASK_APP=app.py
python -m flask db upgrade
```

This is safe to run on a brand-new database too (it detects nothing is missing and does nothing), and it never deletes data — see **Database Setup** below for exactly what each migration does and why. In particular, an account created under the old email/password login keeps its `id`, `name`, `email`, and full prediction history; the very first time that person signs in with Google, `google_logged_in()` links their existing account to their Google identity by matching `email` rather than creating a duplicate (see **Google OAuth Setup** and the API Endpoints section above for exactly how).

**SECRET_KEY:** local development falls back to an insecure hardcoded key automatically, so nothing to configure. Production must set a real one (see Deployment below) — a guessable `SECRET_KEY` lets an attacker forge session cookies.

To run against a local PostgreSQL instance instead, set `DATABASE_URL` before starting the app:

```bash
# Windows PowerShell
$env:DATABASE_URL = "postgresql://user:password@localhost:5432/carbonlens"
python app.py

# bash
export DATABASE_URL="postgresql://user:password@localhost:5432/carbonlens"
python app.py
```

To reset local data, stop the app and delete the `instance/` folder — it (and `carbonlens.db` inside it) will be recreated empty on the next run.

> `gunicorn` (used in production, see below) depends on POSIX-only modules and will not start on native Windows — use `python app.py` for local development there. It runs normally on Render's Linux containers.

---

## Database Setup

Two mechanisms coexist, each covering a different situation:

* **`db.create_all()`** (runs automatically every time `app.py` starts) creates any table that's completely missing, matching the current models — this is why a brand-new database needs zero manual setup.
* **Flask-Migrate / Alembic** (`migrations/`) handles the one thing `create_all()` can't: altering a table that already exists. Phase 2 added `User` and `PredictionHistory.user_id` — on a database that already has a Phase-1 `prediction_history` table, that table needs an actual `ALTER TABLE` to gain the new `user_id` column, which is exactly what the migration in `migrations/versions/` does. It's written to be safe to run against *either* an already-migrated, a pre-Phase-2, or a completely empty database — it inspects the live schema first and only makes the change that's actually missing.

**Commands** (set `FLASK_APP=app.py` first, as shown in Run Locally):

```bash
flask db upgrade          # apply any pending migrations (safe to (re)run anytime)
flask db current           # show which migration the database is currently at
flask db history            # list all migrations
```

You do not need `flask db migrate` (which *generates* a new migration by diffing models against the database) unless you're changing the schema further yourself.

**What each migration does**, precisely — both inspect the live schema first and only change what's actually missing, so they're safe to run against a brand-new, partially-upgraded, or already-current database alike:

1. **`add users table and prediction_history.user_id`** — creates `users` if missing; if `prediction_history` exists without a `user_id` column, adds it (nullable — rows from before accounts existed have no owner and become invisible to the app's per-user queries, but are not deleted) plus its foreign key to `users.id`.
2. **`switch users to google oauth`** — adds `google_id` (unique, nullable) and `avatar_url` to `users` if missing; drops `password_hash` if present. This only ever removes the now-unused password column — `id`, `name`, `email`, `created_at`, and every linked `prediction_history` row are untouched. An account migrated this way has `google_id = NULL` until its owner actually signs in with Google, at which point `google_logged_in()` links it by matching `email` (see API Endpoints above).

## Google OAuth Setup

Required for anyone to actually sign in (guest calculator use works fine without this). CarbonLens never talks to any other Google API — this is purely "prove who you are" sign-in — so the setup is minimal:

1. In the [Google Cloud Console](https://console.cloud.google.com/), create a project (or reuse one) and go to **APIs & Services → Credentials**.
2. **Create Credentials → OAuth client ID**, application type **Web application**.
3. Under **Authorized redirect URIs**, add:
   - Local dev: `http://127.0.0.1:5000/login/google/authorized`
   - Production: `https://<your-render-domain>/login/google/authorized`
4. Save, then copy the **Client ID** and **Client Secret**.
5. Set them as environment variables — locally:

   ```bash
   # Windows PowerShell
   $env:GOOGLE_OAUTH_CLIENT_ID = "your-client-id"
   $env:GOOGLE_OAUTH_CLIENT_SECRET = "your-client-secret"
   python app.py

   # bash
   export GOOGLE_OAUTH_CLIENT_ID="your-client-id"
   export GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret"
   python app.py
   ```

   — and on Render, in the Web Service's **Environment** tab (see Deployment below; `render.yaml` declares these two variables but, being secrets from an external provider, Render always asks you to fill in the actual values by hand rather than generating or syncing them).

**Local HTTP note:** Google's OAuth2 flow refuses to redirect to a plain-HTTP callback URL by default, which would break it against `http://127.0.0.1:5000`. `app.py` already sets `OAUTHLIB_INSECURE_TRANSPORT=1` automatically for local development (the same "no `DATABASE_URL` set" signal that triggers the SQLite fallback), so this needs no action from you locally — and that override can never accidentally reach production, since Render always sets `DATABASE_URL`.

Without `GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_CLIENT_SECRET` set at all, clicking "Sign in with Google" still redirects to Google, which will then show its own `invalid_client` error page — the rest of the app (landing page, guest calculator) is completely unaffected.

## Deployment (Render)

This repo is set up for Render's native Python environment, including a managed PostgreSQL database:

* **`requirements.txt`** — pinned runtime dependencies, including `gunicorn`, `flask-sqlalchemy`, `psycopg2-binary`, `flask-login`, `flask-migrate`, and `flask-dance` (Flask-Dance pulls in `oauthlib` and `requests-oauthlib` itself for the actual OAuth2 mechanics — `authlib` isn't used anywhere in this app).
* **`Procfile`** — `web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2` (used only if you deploy without `render.yaml`; see below).
* **`render.yaml`** — defines the web service **and** a `carbon-tracker-db` Postgres database; wires the database's connection string into `DATABASE_URL`; generates a real `SECRET_KEY` automatically (Render's `generateValue: true`); sets `FLASK_APP=app.py` so migration commands work; declares (but, being secrets, does not auto-fill) `GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_CLIENT_SECRET`; and runs `flask db upgrade` before `gunicorn` starts on every deploy, so schema changes are applied automatically — no manual migration step on Render.

**Deploying via Blueprint (recommended):** push this repo to GitHub, then apply the Render Blueprint (`render.yaml`) from the Render dashboard. Render provisions the web service, the Postgres database, `DATABASE_URL`, and `SECRET_KEY` for you automatically, and prompts you to fill in `GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_CLIENT_SECRET` (from **Google OAuth Setup** above) during setup.

**Deploying manually (without the Blueprint):** if you create the Web Service and Postgres database separately instead of via `render.yaml`:
1. Create a Render PostgreSQL instance.
2. On the Web Service, go to **Environment** and add: `DATABASE_URL` (that database's **Internal Connection String**), `SECRET_KEY` (any long random string — Render can generate one for you), `FLASK_APP=app.py`, `GOOGLE_OAUTH_CLIENT_ID`, and `GOOGLE_OAUTH_CLIENT_SECRET`.
3. Set the **Start Command** to `flask db upgrade && gunicorn app:app --bind 0.0.0.0:$PORT --workers 2` so migrations run before the server starts accepting traffic.
4. In Google Cloud Console, add `https://<your-render-domain>/login/google/authorized` as an authorized redirect URI (see **Google OAuth Setup**).
5. Deploy.

**I was not able to test against a live Render PostgreSQL instance** in this environment (no provisioned Render service or real Postgres server was reachable here) — what *is* verified: the `postgres://` → `postgresql://` URL rewrite, the SQLAlchemy engine accepting a `postgresql://` URI, `psycopg2-binary` installed and importable, and the exact same migration path (`flask db upgrade`) proven correct against SQLite in this session. The connection code path is identical for both databases (SQLAlchemy abstracts the driver), so the remaining risk is purely "does Render's Postgres accept a connection," which can only be confirmed by an actual deploy.

---

## Future Improvements
* SHAP-based explainability surfaced in the `/predict` response and UI
* PDF export of results
* CSRF protection on forms (out of scope so far — no form on the site currently uses CSRF tokens)
* Rate limiting on `/predict` for guests, since it now has no auth gate at all

---

## Author

Pragya Chaudhary
BTech CSE | AI & Full Stack Enthusiast
