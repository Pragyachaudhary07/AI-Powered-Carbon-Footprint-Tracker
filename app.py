from flask import Flask, request, jsonify
import pickle
import numpy as np

app = Flask(__name__)

# Load model
model = pickle.load(open("carbon_model.pkl", "rb"))

@app.route("/")
def home():
    return "Carbon Footprint API is running!"

@app.route("/predict", methods=["POST"])
def predict():
    data = request.json

    travel = data["travel"]
    electricity = data["electricity"]
    transport = data["transport"]
    diet = data["diet"]

    # Convert to model format (9 features)
    transport_map = {
        "bike": [1,0,0,0],
        "bus": [0,1,0,0],
        "car": [0,0,1,0],
        "walk": [0,0,0,1]
    }

    diet_map = {
        "nonveg": [1,0,0],
        "veg": [0,1,0],
        "vegan": [0,0,1]
    }

    features = [travel, electricity] + transport_map[transport] + diet_map[diet]

    prediction = model.predict([features])

    return jsonify({
        "carbon_footprint": float(prediction[0])
    })

if __name__ == "__main__":
    app.run(debug=True)