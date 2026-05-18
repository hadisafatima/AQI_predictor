import requests
from datetime import datetime
import os
from pymongo import MongoClient

API_KEY = os.getenv("OPENWEATHER_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI")

client = MongoClient(MONGODB_URI)
db = client["aqi_db"]
collection = db["weather_data"]

LAT = 25.5961
LON = 68.4467
CITY = "Matiari"

# -----------------------------
# 1. WEATHER API (OpenWeather)
# -----------------------------
weather_url = (
    f"https://api.openweathermap.org/data/2.5/weather"
    f"?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric"
)

weather_response = requests.get(weather_url)

if weather_response.status_code != 200:
    print("Weather API failed")
    print(weather_response.text)
    exit()

weather = weather_response.json()

# -----------------------------
# 2. AQI API (OpenAQ)
# -----------------------------
aqi_url = "https://api.openaq.org/v2/latest"

aqi_response = requests.get(aqi_url, params={
    "coordinates": f"{LAT},{LON}",
    "radius": 5000,
    "limit": 1
})

if aqi_response.status_code != 200:
    print("AQI API failed")
    print(aqi_response.text)
    exit()

aqi_results = aqi_response.json()["results"]

# default pollutant values
pm2_5 = pm10 = no2 = o3 = co = so2 = nh3 = None

if aqi_results:
    measurements = aqi_results[0]["measurements"]

    for m in measurements:
        if m["parameter"] == "pm25":
            pm2_5 = m["value"]
        elif m["parameter"] == "pm10":
            pm10 = m["value"]
        elif m["parameter"] == "no2":
            no2 = m["value"]
        elif m["parameter"] == "o3":
            o3 = m["value"]
        elif m["parameter"] == "co":
            co = m["value"]
        elif m["parameter"] == "so2":
            so2 = m["value"]
        elif m["parameter"] == "nh3":
            nh3 = m["value"]

# -----------------------------
# 3. MERGED DOCUMENT
# -----------------------------
current_time = datetime.utcnow()

document = {
    "city": CITY,
    "lat": LAT,
    "lon": LON,
    "datetime": current_time,

    # time features
    "year": current_time.year,
    "month": current_time.month,
    "day": current_time.day,
    "hour": current_time.hour,
    "day_of_week": current_time.strftime("%A"),

    # WEATHER (OpenWeather)
    "temp": weather["main"]["temp"],
    "feels_like": weather["main"]["feels_like"],
    "humidity": weather["main"]["humidity"],
    "pressure": weather["main"]["pressure"],
    "wind_speed": weather["wind"]["speed"],
    "wind_deg": weather["wind"]["deg"],
    "clouds": weather["clouds"]["all"],

    # AQI (OpenAQ)
    "pm2_5": pm2_5,
    "pm10": pm10,
    "no2": no2,
    "o3": o3,
    "co": co,
    "so2": so2,
    "nh3": nh3
}

# -----------------------------
# 4. SAVE TO MONGODB
# -----------------------------
collection.insert_one(document)

print(f"Inserted merged weather + AQI data for {current_time}")