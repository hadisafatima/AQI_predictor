import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os

API_KEY = os.getenv("OPENWEATHER_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI")

LAT = 25.5961
LON = 68.4467
CITY = "Matiari"

rows = []

start_date = datetime(2026, 4, 1)
end_date = datetime(2026, 5, 17)

current = start_date

while current <= end_date:

    timestamp = int(current.timestamp())

    # WEATHER API
    weather_url = (
        f"https://api.openweathermap.org/data/3.0/onecall/timemachine"
        f"?lat={LAT}&lon={LON}&dt={timestamp}&appid={API_KEY}&units=metric"
    )

    weather_response = requests.get(weather_url)

    if weather_response.status_code != 200:
        print(f"Weather API failed for {current}")
        current += timedelta(hours=1)
        continue

    weather_data = weather_response.json()

    if "data" not in weather_data:
        current += timedelta(hours=1)
        continue

    weather_hour = weather_data["data"][0]

    # AQI API
    aqi_url = (
        f"http://api.openweathermap.org/data/2.5/air_pollution"
        f"?lat={LAT}&lon={LON}&appid={API_KEY}"
    )

    aqi_response = requests.get(aqi_url)

    if aqi_response.status_code != 200:
        print(f"AQI API failed for {current}")
        current += timedelta(hours=1)
        continue

    aqi_data = aqi_response.json()["list"][0]

    row = {
        "city": CITY,
        "lat": LAT,
        "lon": LON,

        "temp": weather_hour.get("temp"),
        "feels_like": weather_hour.get("feels_like"),
        "humidity": weather_hour.get("humidity"),
        "pressure": weather_hour.get("pressure"),
        "wind_speed": weather_hour.get("wind_speed"),
        "wind_deg": weather_hour.get("wind_deg"),
        "clouds": weather_hour.get("clouds"),
    }

print("Historical dataset created successfully!")