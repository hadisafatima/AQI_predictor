import requests
from datetime import datetime, timezone
import os
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI")

# MongoDB connection
# client = MongoClient(MONGODB_URI)
client = MongoClient(
    MONGODB_URI,
    tls=True,
    tlsAllowInvalidCertificates=True
)
db = client["aqi_db"]
collection = db["weather_data"]

LAT = 25.5961
LON = 68.4467
CITY = "Matiari"

# CURRENT TIME ONLY
current_time = datetime.now(timezone.utc)

timestamp = int(current_time.timestamp())

# WEATHER API (current time approximation using timemachine is not needed anymore)
weather_url = (
    f"https://api.openweathermap.org/data/2.5/weather"
    f"?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric"
)

weather_response = requests.get(weather_url)

if weather_response.status_code != 200:
    print("Weather API failed")
    print(weather_response.status_code)
    print(weather_response.text)
    exit()

weather_data = weather_response.json()

# Current weather is usually in "current"
# weather_current = weather_data.get("current", {})
weather_current = weather_data

# AQI API (current air pollution)
aqi_url = (
    f"https://api.openweathermap.org/data/2.5/air_pollution"
    f"?lat={LAT}&lon={LON}&appid={API_KEY}"
)

aqi_response = requests.get(aqi_url)

if aqi_response.status_code != 200:
    print("AQI API failed")
    exit()

aqi_data = aqi_response.json()["list"][0]

# FINAL DOCUMENT
# document = {
#     "city": CITY,
#     "lat": LAT,
#     "lon": LON,
#     "datetime": current_time,

#     "temp": weather_current.get("temp"),
#     "feels_like": weather_current.get("feels_like"),
#     "humidity": weather_current.get("humidity"),
#     "pressure": weather_current.get("pressure"),
#     "wind_speed": weather_current.get("wind_speed"),
#     "wind_deg": weather_current.get("wind_deg"),
#     "clouds": weather_current.get("clouds"),

#     "aqi": aqi_data["main"]["aqi"],
#     "pm2_5": aqi_data["components"]["pm2_5"],
#     "pm10": aqi_data["components"]["pm10"],
#     "co": aqi_data["components"]["co"],
#     "no2": aqi_data["components"]["no2"],
#     "o3": aqi_data["components"]["o3"],
#     "so2": aqi_data["components"]["so2"],
#     "nh3": aqi_data["components"]["nh3"],
# }

document = {
    "city": CITY,
    # "lat": LAT,
    # "lon": LON,

    # Full timestamp
    "datetime": current_time,

    # Useful ML time features
    "hour": current_time.hour,
    "day": current_time.day,
    "month": current_time.month,
    "year": current_time.year,
    # "minute": current_time.minute,
    "day_of_week": current_time.strftime("%A"),

    # Weather data
    "temp": weather_current["main"]["temp"],
    # "feels_like": weather_current["main"]["feels_like"],
    "humidity": weather_current["main"]["humidity"],
    "pressure": weather_current["main"]["pressure"],

    "wind_speed": weather_current["wind"]["speed"],
    "wind_deg": weather_current["wind"]["deg"],

    "clouds": weather_current["clouds"]["all"],

    # AQI data

    "pm25": aqi_data["components"]["pm2_5"],
    "pm10": aqi_data["components"]["pm10"],
    "no2": aqi_data["components"]["no2"],
    "o3": aqi_data["components"]["o3"],
    "so2": aqi_data["components"]["so2"],
    # "nh3": aqi_data["components"]["nh3"],
    "co": aqi_data["components"]["co"],
    
    "aqi_index": aqi_data["main"]["aqi"],
}

# print(document['temp'])

# print(document)
# INSERT INTO MONGODB
collection.insert_one(document)

print(f"Inserted current hour data: {current_time}")

print("Mongo URI exists:", bool(MONGODB_URI))

# print('API Key:', API_KEY)