import requests
from datetime import datetime
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")

client = MongoClient(MONGODB_URI)
db = client["aqi_db"]
collection = db["weather_data"]

LAT = 25.5961
LON = 68.4467
CITY = "Matiari"

#  WEATHER (Open-Meteo)
weather_url = (
    "https://archive-api.open-meteo.com/v1/archive"
    f"?latitude={LAT}&longitude={LON}"
    "&start_date=2026-03-01"
    "&end_date=2026-05-31"
    "&hourly=temperature_2m,relative_humidity_2m,pressure_msl,"
    "wind_speed_10m,wind_direction_10m,cloud_cover"
    "&timezone=auto"
)

weather = requests.get(weather_url).json()["hourly"]
print("Weather fetched ✔")

# AQI (Open-Meteo Air Quality)
aqi_url = (
    "https://air-quality-api.open-meteo.com/v1/air-quality"
    f"?latitude={LAT}&longitude={LON}"
    "&start_date=2026-04-01"
    "&end_date=2026-05-17"
    "&hourly=pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,ozone,sulphur_dioxide"
    "&timezone=auto"
)

aqi = requests.get(aqi_url).json()["hourly"]
print("AQI fetched ✔")

# WEATHER MAP
weather_map = {}

for i, dt in enumerate(weather["time"]):
    weather_map[dt] = {
        "temp": weather["temperature_2m"][i],
        "humidity": weather["relative_humidity_2m"][i],
        "pressure": weather["pressure_msl"][i],
        "wind_speed": weather["wind_speed_10m"][i],
        "wind_deg": weather["wind_direction_10m"][i],
        "clouds": weather["cloud_cover"][i],
    }

# AQI MAP
aqi_map = {}

for i, dt in enumerate(aqi["time"]):
    aqi_map[dt] = {
        "pm10": aqi["pm10"][i],
        "pm25": aqi["pm2_5"][i],
        "co": aqi["carbon_monoxide"][i],
        "no2": aqi["nitrogen_dioxide"][i],
        "o3": aqi["ozone"][i],
        "so2": aqi["sulphur_dioxide"][i],
    }

# AQI INDEX FUNCTION
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

# AQI INDEX FUNCTION
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
    return sum(values) / len(values) if values else None

# SORT TIME KEYS
all_times = sorted(set(weather_map.keys()) & set(aqi_map.keys()))

prev_aqi = None

# MERGE & INSERT
for dt in all_times:

    w = weather_map.get(dt, {})
    a = aqi_map.get(dt, {})

    aqi_index = compute_aqi(a)

    # AQI change rate (trend feature)
    if prev_aqi is None or aqi_index is None:
        aqi_change = None
    else:
        aqi_change = aqi_index - prev_aqi

    prev_aqi = aqi_index

    dt_obj = datetime.fromisoformat(dt)

    doc = {
        "city": CITY,
        "datetime": dt,

        # TIME FEATURES
        "hour": dt_obj.hour,
        "day": dt_obj.day,
        "month": dt_obj.month,
        "year": dt_obj.year,
        "day_of_week": dt_obj.strftime("%A"),

        # WEATHER
        "temp": w.get("temp"),
        "humidity": w.get("humidity"),
        "pressure": w.get("pressure"),
        "wind_speed": w.get("wind_speed"),
        "wind_deg": w.get("wind_deg"),
        "clouds": w.get("clouds"),

        # AQI COMPONENTS
        "pm25": a.get("pm25"),
        "pm10": a.get("pm10"),
        "no2": a.get("no2"),
        "o3": a.get("o3"),
        "so2": a.get("so2"),
        "co": a.get("co"),

        # DERIVED FEATURES
        "aqi_index": aqi_index,
        "aqi_change_rate": aqi_change
    }

    collection.insert_one(doc)

print("✔ Full historical dataset stored successfully")