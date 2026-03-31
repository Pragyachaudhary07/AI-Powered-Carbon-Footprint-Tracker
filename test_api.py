import requests

url = "http://127.0.0.1:5000/predict"

data = {
    "travel": 10,
    "electricity": 5,
    "transport": "car",
    "diet": "nonveg"
}

response = requests.post(url, json=data)

print(response.json())