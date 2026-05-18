# import requests
# from datetime import datetime
# import os
# from pymongo import MongoClient

# API_KEY = os.getenv("OPENWEATHER_API_KEY")
# MONGODB_URI = os.getenv("MONGODB_URI")

# client = MongoClient(MONGODB_URI)
# db = client["aqi_db"]
# collection = db["weather_data"]

# LAT = 25.5961
# LON = 68.4467
# CITY = "Matiari"

# # -----------------------------
# # 1. WEATHER API (OpenWeather)
# # -----------------------------
# weather_url = (
#     f"https://api.openweathermap.org/data/2.5/weather"
#     f"?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric"
# )

# weather_response = requests.get(weather_url)

# if weather_response.status_code != 200:
#     print("Weather API failed")
#     print(weather_response.text)
#     exit()

# weather = weather_response.json()

# # -----------------------------
# # 2. AQI API (OpenAQ)
# # -----------------------------
# aqi_url = "https://api.openaq.org/v2/latest"

# aqi_response = requests.get(aqi_url, params={
#     "coordinates": f"{LAT},{LON}",
#     "radius": 5000,
#     "limit": 1
# })

# if aqi_response.status_code != 200:
#     print("AQI API failed")
#     print(aqi_response.text)
#     exit()

# aqi_results = aqi_response.json()["results"]

# # default pollutant values
# pm2_5 = pm10 = no2 = o3 = co = so2 = nh3 = None

# if aqi_results:
#     measurements = aqi_results[0]["measurements"]

#     for m in measurements:
#         if m["parameter"] == "pm25":
#             pm2_5 = m["value"]
#         elif m["parameter"] == "pm10":
#             pm10 = m["value"]
#         elif m["parameter"] == "no2":
#             no2 = m["value"]
#         elif m["parameter"] == "o3":
#             o3 = m["value"]
#         elif m["parameter"] == "co":
#             co = m["value"]
#         elif m["parameter"] == "so2":
#             so2 = m["value"]
#         elif m["parameter"] == "nh3":
#             nh3 = m["value"]

# # -----------------------------
# # 3. MERGED DOCUMENT
# # -----------------------------
# current_time = datetime.utcnow()

# document = {
#     "city": CITY,
#     "lat": LAT,
#     "lon": LON,
#     "datetime": current_time,

#     # time features
#     "year": current_time.year,
#     "month": current_time.month,
#     "day": current_time.day,
#     "hour": current_time.hour,
#     "day_of_week": current_time.strftime("%A"),

#     # WEATHER (OpenWeather)
#     "temp": weather["main"]["temp"],
#     "feels_like": weather["main"]["feels_like"],
#     "humidity": weather["main"]["humidity"],
#     "pressure": weather["main"]["pressure"],
#     "wind_speed": weather["wind"]["speed"],
#     "wind_deg": weather["wind"]["deg"],
#     "clouds": weather["clouds"]["all"],

#     # AQI (OpenAQ)
#     "pm2_5": pm2_5,
#     "pm10": pm10,
#     "no2": no2,
#     "o3": o3,
#     "co": co,
#     "so2": so2,
#     "nh3": nh3
# }

# # -----------------------------
# # 4. SAVE TO MONGODB
# # -----------------------------
# collection.insert_one(document)

# print(f"Inserted merged weather + AQI data for {current_time}")




import requests
from datetime import datetime
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# LOAD ENV FILE (THIS WAS MISSING)
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY")

client = MongoClient(MONGODB_URI)
db = client["aqi_db"]
collection = db["weather_data"]

LAT = 25.5961
LON = 68.4467
CITY = "Matiari"

# ---------------- WEATHER (Open-Meteo)
url = (
    "https://archive-api.open-meteo.com/v1/archive"
    f"?latitude={LAT}&longitude={LON}"
    "&start_date=2026-04-01"
    "&end_date=2026-05-17"
    "&hourly=temperature_2m,relative_humidity_2m,pressure_msl,"
    "wind_speed_10m,wind_direction_10m,cloud_cover"
    "&timezone=auto"
)

weather = requests.get(url).json()["hourly"]
print("Weather fetched ✔")
# print(weather)

# ---------------- AQI (OpenAQ v3)
# aqi_url = "https://api.openaq.org/v3/locations"

# headers = {
#     "X-API-Key": os.getenv("OPENAQ_API_KEY")
# }

# params = {
#     "coordinates": f"{LAT},{LON}",
#     "radius": 25000,   # increase radius for Pakistan coverage
#     "limit": 1
# }

# resp = requests.get(aqi_url, headers=headers, params=params)

# print("AQI status:", resp.status_code)

# data = resp.json()
# print(data)

# aqi = requests.get(aqi_url, params=params).json()["results"]

# print("AQI fetched ✔")

from datetime import datetime

weather_map = {}

for i in range(len(weather["time"])):
    dt = weather["time"][i]

    weather_map[dt] = {
        "temp": weather["temperature_2m"][i],
        "humidity": weather["relative_humidity_2m"][i],
        "pressure": weather["pressure_msl"][i],
        "wind_speed": weather["wind_speed_10m"][i],
        "wind_deg": weather["wind_direction_10m"][i],
        "clouds": weather["cloud_cover"][i],
    }


# from collections import defaultdict

# aqi_map = defaultdict(dict)

# for item in aqi:
#     dt = item["date"]["utc"][:13]  # hour bucket

#     param = item["parameter"]
#     val = item["value"]

#     aqi_map[dt][param] = val


for dt in weather_map:

    w = weather_map[dt]
    # a = aqi_map.get(dt, {})

    doc = {
        "city": CITY,
        "datetime": dt,

        # TIME FEATURES
        "hour": dt.split("T")[1][:2],
        "day": dt.split("T")[0],
        "month": dt.split("T")[0].split("-")[1],

        # WEATHER
        "temp": w["temp"],
        "humidity": w["humidity"],
        "pressure": w["pressure"],
        "wind_speed": w["wind_speed"],
        "wind_deg": w["wind_deg"],
        "clouds": w["clouds"],

        # AQI
        # "pm25": a.get("pm25"),
        # "pm10": a.get("pm10"),
        # "no2": a.get("no2"),
        # "o3": a.get("o3"),
        # "so2": a.get("so2"),
        # "co": a.get("co"),
    }

    collection.insert_one(doc)

print("✔ Full historical dataset stored")