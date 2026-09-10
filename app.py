from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import (
    LoginManager, UserMixin, login_user, login_required, logout_user, current_user
)
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.consumer import oauth_authorized
from sqlalchemy import func
from datetime import datetime, timezone
import pandas as pd
import joblib
import logging
import os
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__, template_folder="templates")
# Logging
logging.basicConfig(level=logging.INFO)

# Load model and metadata
model = joblib.load("models/model_v1.pkl")
metadata = joblib.load("models/model_metadata.pkl")

# ---------------------------------------------------------------------------
# Database configuration
#
# Uses PostgreSQL in production via the DATABASE_URL environment variable
# (set this on Render once a Postgres database is attached). Falls back to a
# local SQLite file for development when DATABASE_URL is not set. Render's
# managed Postgres URLs use the legacy "postgres://" scheme, which SQLAlchemy
# 1.4+ no longer accepts, so it's rewritten to "postgresql://" below.
# ---------------------------------------------------------------------------
database_url = os.environ.get("DATABASE_URL", "sqlite:///carbonlens.db")
IS_LOCAL_DEV = "DATABASE_URL" not in os.environ
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Google's OAuth2 flow refuses plain-HTTP redirect URIs by default, which
# breaks it against the local dev server (http://127.0.0.1:5000). This is
# scoped to the same "no DATABASE_URL means local dev" signal already used
# for the SQLite fallback above, so it can never accidentally apply in
# production (Render always sets DATABASE_URL).
if IS_LOCAL_DEV:
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

# SECRET_KEY signs Flask-Login's session cookie. Must be set via environment
# variable in production (Render generates one automatically, see render.yaml)
# so sessions can't be forged and stay valid across restarts/deploys. The
# fallback below only fires for local development.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-key")
if app.config["SECRET_KEY"] == "dev-only-insecure-secret-key" and not app.debug:
    logging.warning("SECRET_KEY is not set — using an insecure development fallback.")

db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login_page"

# Google OAuth. client_id/client_secret are blank until GOOGLE_OAUTH_CLIENT_ID
# and GOOGLE_OAUTH_CLIENT_SECRET are set (see README) — Flask-Dance only
# errors when someone actually clicks "Sign in with Google", not at import
# time, so the rest of the app (including guest calculator use) still works
# without them configured.
google_bp = make_google_blueprint(
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    scope=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile"
    ],
    redirect_to="home",
)

app.register_blueprint(google_bp, url_prefix="/login")
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=True, index=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    avatar_url = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@oauth_authorized.connect_via(google_bp)
def google_logged_in(blueprint, token):
    if not token:
        logging.error("Google OAuth failed: no token returned")
        return False

    resp = blueprint.session.get("/oauth2/v2/userinfo")
    if not resp.ok:
        logging.error("Google OAuth failed: could not fetch userinfo (%s)", resp.status_code)
        return False

    info = resp.json()
    google_id = info["id"]
    email = (info.get("email") or "").strip().lower()
    name = info.get("name") or (email.split("@")[0] if email else "Google User")
    avatar_url = info.get("picture")

    user = User.query.filter_by(google_id=google_id).first()
    if user is None and email:
        # Link to an account that already existed under this email (e.g. one
        # created before Google Sign-In existed) instead of creating a
        # second, disconnected account and orphaning its prediction history.
        user = User.query.filter_by(email=email).first()

    if user:
        user.google_id = google_id
        user.name = name
        user.avatar_url = avatar_url
    else:
        user = User(google_id=google_id, name=name, email=email, avatar_url=avatar_url)
        db.session.add(user)

    db.session.commit()
    login_user(user)

    # False tells Flask-Dance not to also persist the OAuth token itself
    # (via its default storage) — nothing else in the app calls the Google
    # API again after this one userinfo lookup, so there's nothing to keep.
    return False


@login_manager.unauthorized_handler
def unauthorized():
    # /analytics/* is called via fetch() from the frontend, so it needs a
    # JSON 401 the JS can branch on — a redirect would just hand the SPA an
    # HTML login page where it expected JSON. /predict has no login
    # requirement (guests get a live estimate too). Page routes like
    # /profile and /history are plain navigations, so those redirect normally.
    if request.path.startswith("/analytics"):
        return jsonify({"error": "Authentication required"}), 401
    return redirect(url_for("login_page", next=request.path))


class PredictionHistory(db.Model):
    __tablename__ = "prediction_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    prediction = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(20), nullable=False, index=True)
    Personal_Vehicle_Km = db.Column(db.Float, nullable=False)
    Public_Vehicle_Km = db.Column(db.Float, nullable=False)
    Plane_Journey_Count = db.Column(db.Integer, nullable=False)
    Train_Journey_Count = db.Column(db.Integer, nullable=False)
    Electricity_Kwh = db.Column(db.Float, nullable=False)
    Water_Usage_Liters = db.Column(db.Float, nullable=False)
    Diet_Type = db.Column(db.Integer, nullable=False)
    Waste_Kg = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.replace(tzinfo=timezone.utc).isoformat(),
            "prediction": self.prediction,
            "category": self.category,
            "Personal_Vehicle_Km": self.Personal_Vehicle_Km,
            "Public_Vehicle_Km": self.Public_Vehicle_Km,
            "Plane_Journey_Count": self.Plane_Journey_Count,
            "Train_Journey_Count": self.Train_Journey_Count,
            "Electricity_Kwh": self.Electricity_Kwh,
            "Water_Usage_Liters": self.Water_Usage_Liters,
            "Diet_Type": self.Diet_Type,
            "Waste_Kg": self.Waste_Kg,
        }


with app.app_context():
    db.create_all()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login")
def login_page():
    # Signup and login are the same action with Google OAuth — a first-time
    # Google sign-in creates the account (see google_logged_in above), so
    # there's no separate /signup route or form to fill in.
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


@app.route("/profile")
@login_required
def profile_page():
    return render_template("profile.html")


@app.route("/history")
@login_required
def history_page():
    return render_template("history.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "model_version": metadata["model_version"],
        "algorithm": metadata["algorithm"],
        "r2": round(metadata["r2"], 3)
    })


@app.route("/predict", methods=["POST"])
def predict():
    # Guests can still get a live estimate — the model doesn't care who's
    # asking — they just don't get a saved history entry (see below).
    try:
        data = request.get_json()

        logging.info(f"Prediction request: {data}")

        required = [
            "Personal_Vehicle_Km",
            "Public_Vehicle_Km",
            "Plane_Journey_Count",
            "Train_Journey_Count",
            "Electricity_Kwh",
            "Water_Usage_Liters",
            "Diet_Type",
            "Waste_Kg"
        ]

        # Check missing fields
        for field in required:
            if field not in data:
                return jsonify({"error": f"Missing field: {field}"}), 400

        # Check negative values
        for field in required:
            if data[field] < 0:
                return jsonify({"error": f"{field} cannot be negative"}), 400

        # Build DataFrame in the exact order the model expects
        features = pd.DataFrame([{
            "Personal_Vehicle_Km": data["Personal_Vehicle_Km"],
            "Public_Vehicle_Km": data["Public_Vehicle_Km"],
            "Plane_Journey_Count": data["Plane_Journey_Count"],
            "Train_Journey_Count": data["Train_Journey_Count"],
            "Electricity_Kwh": data["Electricity_Kwh"],
            "Water_Usage_Liters": data["Water_Usage_Liters"],
            "Diet_Type": data["Diet_Type"],
            "Waste_Kg": data["Waste_Kg"]
        }])

        prediction = round(float(model.predict(features)[0]), 2)

        # Carbon category
        if prediction < 8:
            category = "Low"
            color = "Green"
            tip = "Your estimated emissions are relatively low. Maintaining efficient travel and energy habits can help keep them low."

        elif prediction < 16:
            category = "Medium"
            color = "Yellow"
            tip = "Reducing personal vehicle use and improving energy efficiency could lower your estimated emissions."

        else:
            category = "High"
            color = "Red"
            tip = "Frequent private transport, flights, or high electricity usage are likely contributing to higher emissions."

        # Persist the prediction — only for signed-in users; guests get a
        # result but nothing is saved for them. A logging failure here
        # should not prevent the caller from getting their result, so it
        # never re-raises.
        if current_user.is_authenticated:
            try:
                record = PredictionHistory(
                    user_id=current_user.id,
                    prediction=prediction,
                    category=category,
                    Personal_Vehicle_Km=data["Personal_Vehicle_Km"],
                    Public_Vehicle_Km=data["Public_Vehicle_Km"],
                    Plane_Journey_Count=data["Plane_Journey_Count"],
                    Train_Journey_Count=data["Train_Journey_Count"],
                    Electricity_Kwh=data["Electricity_Kwh"],
                    Water_Usage_Liters=data["Water_Usage_Liters"],
                    Diet_Type=data["Diet_Type"],
                    Waste_Kg=data["Waste_Kg"],
                )
                db.session.add(record)
                db.session.commit()
            except Exception:
                db.session.rollback()
                logging.exception("Failed to save prediction history")

        return jsonify({
            "prediction": prediction,
            "unit": "kg CO₂/day",
            "category": category,
            "color": color,
            "eco_tip": tip,
            "model_version": metadata["model_version"],
            "r2": round(metadata["r2"], 3)
        })

    except Exception as e:
        logging.exception("Prediction failed")
        return jsonify({"error": str(e)}), 500


@app.route("/analytics/history")
@login_required
def analytics_history():
    limit = request.args.get("limit", default=50, type=int) or 50
    limit = max(1, min(limit, 500))

    records = (
        PredictionHistory.query
        .filter_by(user_id=current_user.id)
        .order_by(PredictionHistory.timestamp.desc())
        .limit(limit)
        .all()
    )

    return jsonify({
        "count": len(records),
        "history": [record.to_dict() for record in records]
    })


@app.route("/analytics/summary")
@login_required
def analytics_summary():
    total = (
        db.session.query(func.count(PredictionHistory.id))
        .filter(PredictionHistory.user_id == current_user.id)
        .scalar() or 0
    )

    if total == 0:
        return jsonify({
            "total_predictions": 0,
            "average_emission": None,
            "highest_emission": None,
            "lowest_emission": None,
            "category_distribution": {"Low": 0, "Medium": 0, "High": 0}
        })

    average_emission, highest_emission, lowest_emission = db.session.query(
        func.avg(PredictionHistory.prediction),
        func.max(PredictionHistory.prediction),
        func.min(PredictionHistory.prediction)
    ).filter(PredictionHistory.user_id == current_user.id).one()

    category_counts = dict(
        db.session.query(PredictionHistory.category, func.count(PredictionHistory.id))
        .filter(PredictionHistory.user_id == current_user.id)
        .group_by(PredictionHistory.category)
        .all()
    )

    return jsonify({
        "total_predictions": total,
        "average_emission": round(float(average_emission), 2),
        "highest_emission": round(float(highest_emission), 2),
        "lowest_emission": round(float(lowest_emission), 2),
        "category_distribution": {
            "Low": category_counts.get("Low", 0),
            "Medium": category_counts.get("Medium", 0),
            "High": category_counts.get("High", 0)
        }
    })


@app.route("/analytics/latest")
@login_required
def analytics_latest():
    record = (
        PredictionHistory.query
        .filter_by(user_id=current_user.id)
        .order_by(PredictionHistory.timestamp.desc())
        .first()
    )
    return jsonify({"latest": record.to_dict() if record else None})


if __name__ == "__main__":
    app.run(debug=True)