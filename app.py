from flask import Flask, request, jsonify, render_template
import pandas as pd
import joblib
import logging

app = Flask(__name__, template_folder="templates")
# Logging
logging.basicConfig(level=logging.INFO)

# Load model and metadata
model = joblib.load("models/model_v1.pkl")
metadata = joblib.load("models/model_metadata.pkl")


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


if __name__ == "__main__":
    app.run(debug=True)