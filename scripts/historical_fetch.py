# import requests 
# from datetime import datetime, timedelta 
# import os 
# from pymongo import MongoClient 

# API_KEY = os.getenv("OPENWEATHER_API_KEY") 
# MONGODB_URI = os.getenv("MONGODB_URI") 

# # MongoDB connection 
# client = MongoClient(MONGODB_URI) 
# db = client["aqi_db"] 
# collection = db["weather_data"] 

# LAT = 25.5961 
# LON = 68.4467 
# CITY = "Matiari" 
# start_date = datetime(2026, 4, 1) 
# end_date = datetime(2026, 5, 17) 

# current = start_date 
# while current <= end_date: 
#     timestamp = int(current.timestamp()) 
    
#     # WEATHER API 
#     weather_url = ( f"https://api.openweathermap.org/data/3.0/onecall/timemachine" 
#                    f"?lat={LAT}&lon={LON}&dt={timestamp}&appid={API_KEY}&units=metric" ) 
#     weather_response = requests.get(weather_url) 
    
#     if weather_response.status_code != 200: 
#         print(f"Weather API failed for {current}") 
#         current += timedelta(hours=1) 
#         continue 
    
#     weather_data = weather_response.json() 
    
#     if "data" not in weather_data: 
#         current += timedelta(hours=1) 
#         continue 
    
#     weather_hour = weather_data["data"][0] 
    
#     # AQI API 
#     aqi_url = ( f"http://api.openweathermap.org/data/2.5/air_pollution" 
#                f"?lat={LAT}&lon={LON}&appid={API_KEY}" ) 
#     aqi_response = requests.get(aqi_url) 
#     if aqi_response.status_code != 200: 
#         print(f"AQI API failed for {current}") 
#         current += timedelta(hours=1) 
#         continue 
    
#     aqi_data = aqi_response.json()["list"][0] 
    
#     # FINAL DOCUMENT 
#     document = { 
#         "city": CITY, 
#         "lat": LAT, 
#         "lon": LON, 
#         "datetime": current, 
#         "temp": weather_hour.get("temp"), 
#         "feels_like": weather_hour.get("feels_like"), 
#         "humidity": weather_hour.get("humidity"), 
#         "pressure": weather_hour.get("pressure"), 
#         "wind_speed": weather_hour.get("wind_speed"), 
#         "wind_deg": weather_hour.get("wind_deg"), 
#         "clouds": weather_hour.get("clouds"), 
#         "aqi": aqi_data["main"]["aqi"], 
#         "pm2_5": aqi_data["components"]["pm2_5"], 
#         "pm10": aqi_data["components"]["pm10"], 
#         "co": aqi_data["components"]["co"], 
#         "no2": aqi_data["components"]["no2"], 
#         "o3": aqi_data["components"]["o3"], 
#         "so2": aqi_data["components"]["so2"], 
#         "nh3": aqi_data["components"]["nh3"], 
#     } 
    
#     # INSERT INTO MONGODB 
#     collection.insert_one(document) 
#     print(f"Inserted data for {current}") 
#     current += timedelta(hours=1) 
    
# print("Historical dataset stored in MongoDB successfully!") 

# # print('API_KEY: ', API_KEY) 
# # # print('MONGODB_URI: ', MONGODB_URI)




import requests
from datetime import datetime
import os
from pymongo import MongoClient

API_KEY = os.getenv("OPENWEATHER_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI")

# MongoDB connection
client = MongoClient(MONGODB_URI)
db = client["aqi_db"]
collection = db["weather_data"]

LAT = 25.5961
LON = 68.4467
CITY = "Matiari"

# CURRENT TIME ONLY
current_time = datetime.utcnow()

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
weather_current = weather_data.get("current", {})

# AQI API (current air pollution)
aqi_url = (
    f"http://api.openweathermap.org/data/2.5/air_pollution"
    f"?lat={LAT}&lon={LON}&appid={API_KEY}"
)

aqi_response = requests.get(aqi_url)

if aqi_response.status_code != 200:
    print("AQI API failed")
    exit()

aqi_data = aqi_response.json()["list"][0]

# FINAL DOCUMENT
document = {
    "city": CITY,
    "lat": LAT,
    "lon": LON,
    "datetime": current_time,

    "temp": weather_current.get("temp"),
    "feels_like": weather_current.get("feels_like"),
    "humidity": weather_current.get("humidity"),
    "pressure": weather_current.get("pressure"),
    "wind_speed": weather_current.get("wind_speed"),
    "wind_deg": weather_current.get("wind_deg"),
    "clouds": weather_current.get("clouds"),

    "aqi": aqi_data["main"]["aqi"],
    "pm2_5": aqi_data["components"]["pm2_5"],
    "pm10": aqi_data["components"]["pm10"],
    "co": aqi_data["components"]["co"],
    "no2": aqi_data["components"]["no2"],
    "o3": aqi_data["components"]["o3"],
    "so2": aqi_data["components"]["so2"],
    "nh3": aqi_data["components"]["nh3"],
}

# INSERT INTO MONGODB
collection.insert_one(document)

print(f"Inserted current hour data: {current_time}")

print("Mongo URI exists:", bool(MONGODB_URI))