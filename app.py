from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime, timezone
import pandas as pd
import joblib
import logging
import os

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
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class PredictionHistory(db.Model):
    __tablename__ = "prediction_history"

    id = db.Column(db.Integer, primary_key=True)
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

        # Persist the prediction. A logging failure here should not prevent
        # the caller from getting their result, so it never re-raises.
        try:
            record = PredictionHistory(
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
def analytics_history():
    limit = request.args.get("limit", default=50, type=int) or 50
    limit = max(1, min(limit, 500))

    records = (
        PredictionHistory.query
        .order_by(PredictionHistory.timestamp.desc())
        .limit(limit)
        .all()
    )

    return jsonify({
        "count": len(records),
        "history": [record.to_dict() for record in records]
    })


@app.route("/analytics/summary")
def analytics_summary():
    total = db.session.query(func.count(PredictionHistory.id)).scalar() or 0

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
    ).one()

    category_counts = dict(
        db.session.query(PredictionHistory.category, func.count(PredictionHistory.id))
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


if __name__ == "__main__":
    app.run(debug=True)