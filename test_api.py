import requests

url = "http://127.0.0.1:5000/predict"

data = {
    "Personal_Vehicle_Km": 12,
    "Public_Vehicle_Km": 8,
    "Plane_Journey_Count": 0,
    "Train_Journey_Count": 1,
    "Electricity_Kwh": 6.5,
    "Water_Usage_Liters": 120,
    "Diet_Type": 1,
    "Waste_Kg": 1.2
}

response = requests.post(url, json=data)

print(response.status_code)
print(response.json())
