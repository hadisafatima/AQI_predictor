# import requests
# from datetime import datetime, timezone
# import os
# from pymongo import MongoClient
# from dotenv import load_dotenv
# load_dotenv()

# API_KEY = os.getenv("OPENWEATHER_API_KEY")
# MONGODB_URI = os.getenv("MONGODB_URI")

# # MongoDB connection
# # client = MongoClient(MONGODB_URI)
# client = MongoClient(
#     MONGODB_URI,
#     tls=True,
#     tlsAllowInvalidCertificates=True
# )
# db = client["aqi_db"]
# collection = db["weather_data"]

# LAT = 25.5961
# LON = 68.4467
# CITY = "Matiari"

# # CURRENT TIME ONLY
# current_time = datetime.now(timezone.utc)

# timestamp = int(current_time.timestamp())

# # WEATHER API (current time approximation using timemachine is not needed anymore)
# weather_url = (
#     f"https://api.openweathermap.org/data/2.5/weather"
#     f"?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric"
# )

# weather_response = requests.get(weather_url)

# if weather_response.status_code != 200:
#     print("Weather API failed")
#     print(weather_response.status_code)
#     print(weather_response.text)
#     exit()

# weather_data = weather_response.json()

# # Current weather is usually in "current"
# # weather_current = weather_data.get("current", {})
# weather_current = weather_data

# # AQI API (current air pollution)
# aqi_url = (
#     f"https://api.openweathermap.org/data/2.5/air_pollution"
#     f"?lat={LAT}&lon={LON}&appid={API_KEY}"
# )

# aqi_response = requests.get(aqi_url)

# if aqi_response.status_code != 200:
#     print("AQI API failed")
#     exit()

# aqi_data = aqi_response.json()["list"][0]

# # FINAL DOCUMENT
# document = {
#     "city": CITY,

#     # Full timestamp
#     "datetime": current_time,
#     "hour": current_time.hour,
#     "day": current_time.day,
#     "month": current_time.month,
#     "year": current_time.year,
#     "day_of_week": current_time.strftime("%A"),

#     # Weather data
#     "temp": weather_current["main"]["temp"],
#     "humidity": weather_current["main"]["humidity"],
#     "pressure": weather_current["main"]["pressure"],
#     "wind_speed": weather_current["wind"]["speed"],
#     "wind_deg": weather_current["wind"]["deg"],
#     "clouds": weather_current["clouds"]["all"],

#     # AQI data
#     "pm25": aqi_data["components"]["pm2_5"],
#     "pm10": aqi_data["components"]["pm10"],
#     "no2": aqi_data["components"]["no2"],
#     "o3": aqi_data["components"]["o3"],
#     "so2": aqi_data["components"]["so2"],
#     "co": aqi_data["components"]["co"],
    
#     "aqi_index": aqi_data["main"]["aqi"],
# }

# # print(document['temp'])

# # INSERT INTO MONGODB
# collection.insert_one(document)

# print(f"Inserted current hour data: {current_time}")

# print("Mongo URI exists:", bool(MONGODB_URI))

# # print('API Key:', API_KEY)



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

# -----------------------------
# WEATHER API
# -----------------------------
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
weather_current = weather_data

# -----------------------------
# AQI API
# -----------------------------
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

# -----------------------------
# AQI CHANGE RATE FEATURE
# -----------------------------
current_aqi = aqi_data["main"]["aqi"]

# GET LATEST DOCUMENT FOR THIS CITY
latest_doc = collection.find_one(
    {"city": CITY},
    sort=[("datetime", -1)]
)

# DEFAULT CHANGE RATE
aqi_change_rate = 0

# CALCULATE AQI CHANGE RATE
if latest_doc:
    previous_aqi = latest_doc.get("aqi_index", current_aqi)
    aqi_change_rate = current_aqi - previous_aqi

# -----------------------------
# FINAL DOCUMENT
# -----------------------------
document = {
    "city": CITY,

    # TIME FEATURES
    "datetime": current_time,
    "hour": current_time.hour,
    "day": current_time.day,
    "month": current_time.month,
    "year": current_time.year,
    "day_of_week": current_time.strftime("%A"),

    # LOCATION
    # "lat": LAT,
    # "lon": LON,

    # WEATHER DATA
    "temp": weather_current["main"]["temp"],
    # "feels_like": weather_current["main"]["feels_like"],
    "humidity": weather_current["main"]["humidity"],
    "pressure": weather_current["main"]["pressure"],

    "wind_speed": weather_current["wind"]["speed"],
    "wind_deg": weather_current["wind"]["deg"],

    "clouds": weather_current["clouds"]["all"],

    # "weather_main": weather_current["weather"][0]["main"],
    # "weather_description": weather_current["weather"][0]["description"],


    "pm25": aqi_data["components"]["pm2_5"],
    "pm10": aqi_data["components"]["pm10"],
    "no2": aqi_data["components"]["no2"],
    "o3": aqi_data["components"]["o3"],
    "so2": aqi_data["components"]["so2"],
    "co": aqi_data["components"]["co"],
    # "nh3": aqi_data["components"]["nh3"],

    # AQI DATA
    "aqi_index": current_aqi,
    # FEATURE ENGINEERING
    "aqi_change_rate": aqi_change_rate
}

# -----------------------------
# INSERT INTO MONGODB
# -----------------------------
collection.insert_one(document)

print(f"Inserted current hour data: {current_time}")
print(f"AQI Change Rate: {aqi_change_rate}")

print("Mongo URI exists:", bool(MONGODB_URI))




# import requests
# from datetime import datetime
# from pymongo import MongoClient
# import os
# from dotenv import load_dotenv

# load_dotenv()

# MONGODB_URI = os.getenv("MONGODB_URI")

# client = MongoClient(MONGODB_URI)
# db = client["aqi_db"]
# collection = db["weather_data"]

# LAT = 25.5961
# LON = 68.4467
# CITY = "Matiari"

# # ---------------- WEATHER (Open-Meteo)
# weather_url = (
#     "https://archive-api.open-meteo.com/v1/archive"
#     f"?latitude={LAT}&longitude={LON}"
#     "&start_date=2026-04-01"
#     "&end_date=2026-05-17"
#     "&hourly=temperature_2m,relative_humidity_2m,pressure_msl,"
#     "wind_speed_10m,wind_direction_10m,cloud_cover"
#     "&timezone=auto"
# )

# weather = requests.get(weather_url).json()["hourly"]
# print("Weather fetched ✔")

# # ---------------- AQI (Open-Meteo Air Quality)
# aqi_url = (
#     "https://air-quality-api.open-meteo.com/v1/air-quality"
#     f"?latitude={LAT}&longitude={LON}"
#     "&start_date=2026-04-01"
#     "&end_date=2026-05-17"
#     "&hourly=pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,ozone,sulphur_dioxide"
#     "&timezone=auto"
# )

# aqi = requests.get(aqi_url).json()["hourly"]
# print("AQI fetched ✔")

# # ---------------- BUILD WEATHER MAP
# weather_map = {}

# for i, dt in enumerate(weather["time"]):
#     weather_map[dt] = {
#         "temp": weather["temperature_2m"][i],
#         "humidity": weather["relative_humidity_2m"][i],
#         "pressure": weather["pressure_msl"][i],
#         "wind_speed": weather["wind_speed_10m"][i],
#         "wind_deg": weather["wind_direction_10m"][i],
#         "clouds": weather["cloud_cover"][i],
#     }

# # ---------------- BUILD AQI MAP
# aqi_map = {}

# for i, dt in enumerate(aqi["time"]):
#     aqi_map[dt] = {
#         "pm10": aqi["pm10"][i],
#         "pm25": aqi["pm2_5"][i],
#         "co": aqi["carbon_monoxide"][i],
#         "no2": aqi["nitrogen_dioxide"][i],
#         "o3": aqi["ozone"][i],
#         "so2": aqi["sulphur_dioxide"][i],
#     }

# # ---------------- AQI INDEX FUNCTION
# def compute_aqi(p):
#     values = [
#         p.get("pm25"),
#         p.get("pm10"),
#         p.get("no2"),
#         p.get("o3"),
#         p.get("co"),
#         p.get("so2"),
#     ]
#     values = [v for v in values if v is not None]
#     return max(values) if values else None

# # ---------------- GET LATEST AQI FROM DB (ONLY ONCE)
# def get_latest_aqi():
#     latest = collection.find_one(
#         {"aqi_index": {"$ne": None}},
#         sort=[("datetime", -1)]
#     )
#     return latest["aqi_index"] if latest else None

# prev_aqi = get_latest_aqi()

# # ---------------- MERGE & INSERT
# all_times = sorted(set(weather_map.keys()) & set(aqi_map.keys()))

# for dt in all_times:

#     w = weather_map.get(dt, {})
#     a = aqi_map.get(dt, {})

#     # convert datetime string safely
#     dt_obj = datetime.fromisoformat(dt)

#     # AQI index
#     aqi_index = compute_aqi(a)

#     # AQI change rate (compared to last DB value or previous loop)
#     if prev_aqi is None or aqi_index is None:
#         aqi_change_rate = None
#     else:
#         aqi_change_rate = aqi_index - prev_aqi

#     prev_aqi = aqi_index

#     doc = {
#         "city": CITY,
#         "datetime": dt,

#         # TIME FEATURES
#         "hour": dt_obj.hour,
#         "day": dt_obj.day,
#         "month": dt_obj.month,
#         "year": dt_obj.year,
#         "day_of_week": dt_obj.strftime("%A"),

#         # WEATHER
#         "temp": w.get("temp"),
#         "humidity": w.get("humidity"),
#         "pressure": w.get("pressure"),
#         "wind_speed": w.get("wind_speed"),
#         "wind_deg": w.get("wind_deg"),
#         "clouds": w.get("clouds"),

#         # AQI COMPONENTS
#         "pm25": a.get("pm25"),
#         "pm10": a.get("pm10"),
#         "no2": a.get("no2"),
#         "o3": a.get("o3"),
#         "so2": a.get("so2"),
#         "co": a.get("co"),

#         # 🔥 DERIVED FEATURES
#         "aqi_index": aqi_index,
#         "aqi_change_rate": aqi_change_rate
#     }

#     collection.insert_one(doc)

# print("✔ Full historical dataset stored successfully with AQI features")