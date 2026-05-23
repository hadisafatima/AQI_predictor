import requests
from datetime import datetime, timezone
import os
from pymongo import MongoClient
from dotenv import load_dotenv

# LOAD ENV VARIABLES
load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI")

# MONGODB CONNECTION
client = MongoClient(
    MONGODB_URI,
    tls=True,
    tlsAllowInvalidCertificates=True
)

db = client["aqi_db"]
collection = db["weather_data"]

# LOCATION
LAT = 25.5961
LON = 68.4467
CITY = "Matiari"

# CURRENT UTC TIME
current_time = datetime.now(timezone.utc)

# WEATHER API
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

# AQI API
aqi_url = (
    f"https://api.openweathermap.org/data/2.5/air_pollution"
    f"?lat={LAT}&lon={LON}&appid={API_KEY}"
)

aqi_response = requests.get(aqi_url)

if aqi_response.status_code != 200:
    print("AQI API failed")
    print(aqi_response.status_code)
    print(aqi_response.text)
    exit()

aqi_data = aqi_response.json()["list"][0]

# POLLUTANT DATA
pollutants = {
    "pm25": aqi_data["components"]["pm2_5"],
    "pm10": aqi_data["components"]["pm10"],
    "no2": aqi_data["components"]["no2"],
    "o3": aqi_data["components"]["o3"],
    "so2": aqi_data["components"]["so2"],
    "co": aqi_data["components"]["co"],
}

# CUSTOM AQI COMPUTATION
def compute_aqi(p):
    values = [
        p.get("pm25"),
        p.get("pm10"),
        p.get("no2"),
        p.get("o3"),
        p.get("co"),
        p.get("so2"),
    ]

    values = [v for v in values if v is not None]

    return max(values) if values else None

# CURRENT COMPUTED AQI
current_aqi = compute_aqi(pollutants)

# GET PREVIOUS AQI
latest_doc = collection.find_one(
    {"city": CITY},
    sort=[("datetime", -1)]
)

# DEFAULT CHANGE RATE
aqi_change_rate = 0

if latest_doc:

    previous_aqi = latest_doc.get("aqi_index")

    # VALIDATE PREVIOUS AQI
    if isinstance(previous_aqi, (int, float)):
        aqi_change_rate = round(current_aqi - previous_aqi, 2)

# FINAL DOCUMENT
document = {
    "city": CITY,
    "datetime": current_time,

    # TIME FEATURES
    "hour": current_time.hour,
    "day": current_time.day,
    "month": current_time.month,
    "year": current_time.year,
    "day_of_week": current_time.strftime("%A"),

    # WEATHER 
    "temp": weather_data["main"]["temp"],
    "humidity": weather_data["main"]["humidity"],
    "pressure": weather_data["main"]["pressure"],
    "wind_speed": weather_data["wind"]["speed"],
    "wind_deg": weather_data["wind"]["deg"],
    "clouds": weather_data["clouds"]["all"],

    # AQI COMPONENTS
    "pm25": pollutants["pm25"],
    "pm10": pollutants["pm10"],
    "no2": pollutants["no2"],
    "o3": pollutants["o3"],
    "so2": pollutants["so2"],
    "co": pollutants["co"],

    # DERIVED FEATURES
    "aqi_index": current_aqi,
    "aqi_change_rate": aqi_change_rate
}

# INSERT INTO MONGODB
collection.insert_one(document)

# LOGS
print("Inserted document successfully ✔")
print(document)
print(f"AQI Change Rate: {aqi_change_rate}")
print('previous_aqi:', previous_aqi)
print("Mongo URI exists:", bool(MONGODB_URI))