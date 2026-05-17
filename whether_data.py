import requests
import pandas as pd

API_Key = '702588677ff8c18baa589c5dcbfe36c5'
city_name = 'Matiari'

# -----------------------------
# 1. WEATHER API CALL
# -----------------------------
weather_url = f"https://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={API_Key}&units=metric"
weather_response = requests.get(weather_url)

if weather_response.status_code != 200:
    raise Exception(f"Weather API Error: {weather_response.status_code}")

weather_data = weather_response.json()

weather_df = pd.json_normalize(weather_data)

# flatten weather
weather_df["weather_main"] = weather_df["weather"].apply(lambda x: x[0]["main"])
weather_df["weather_description"] = weather_df["weather"].apply(lambda x: x[0]["description"])
weather_df.drop(columns=["weather"], inplace=True)

# keep ONLY relevant weather features
weather_df = weather_df[[
    "name",
    "coord.lat",
    "coord.lon",
    "main.temp",
    "main.feels_like",
    "main.humidity",
    "main.pressure",
    "wind.speed",
    "wind.deg",
    "clouds.all",
    "weather_main",
    "weather_description",
    "dt"
]]

weather_df.rename(columns={
    "name": "city",
    "coord.lat": "lat",
    "coord.lon": "lon",
    "main.temp": "temp",
    "main.feels_like": "feels_like",
    "main.humidity": "humidity",
    "main.pressure": "pressure",
    "wind.speed": "wind_speed",
    "wind.deg": "wind_deg",
    "clouds.all": "clouds"
}, inplace=True)

# convert time
weather_df["datetime"] = pd.to_datetime(weather_df["dt"], unit="s")
weather_df.drop(columns=["dt"], inplace=True)



# -----------------------------
# 2. AQI API CALL
# -----------------------------
lat = weather_df["lat"].iloc[0]
lon = weather_df["lon"].iloc[0]

aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_Key}"
aqi_response = requests.get(aqi_url)

if aqi_response.status_code != 200:
    raise Exception(f"AQI API Error: {aqi_response.status_code}")

aqi_data = aqi_response.json()["list"][0]

aqi_df = pd.DataFrame([{
    "aqi": aqi_data["main"]["aqi"],
    "pm2_5": aqi_data["components"]["pm2_5"],
    "pm10": aqi_data["components"]["pm10"],
    "co": aqi_data["components"]["co"],
    "no2": aqi_data["components"]["no2"],
    "o3": aqi_data["components"]["o3"],
    "so2": aqi_data["components"]["so2"],
    "nh3": aqi_data["components"]["nh3"]
}])


# -----------------------------
# 3. MERGE DATASETS
# -----------------------------
df = pd.concat([weather_df, aqi_df], axis=1)


# -----------------------------
# 4. FEATURE ENGINEERING
# -----------------------------
df = df.sort_values("datetime")

# time-based features
df["hour"] = df["datetime"].dt.hour
df["day"] = df["datetime"].dt.day
df["month"] = df["datetime"].dt.month
df["day_of_week"] = df["datetime"].dt.dayofweek

# optional smart features
# df["is_rush_hour"] = df["hour"].apply(lambda x: 1 if 7 <= x <= 10 or 17 <= x <= 20 else 0)
# df["is_night"] = df["hour"].apply(lambda x: 1 if x >= 20 or x <= 5 else 0)

# AQI change rate
df["aqi_change_rate"] = df["aqi"].diff()
df["aqi_change_rate"] = df["aqi_change_rate"].fillna(0)


# -----------------------------
# 5. FINAL CLEAN DATASET
# -----------------------------
final_columns = [
    "city","datetime", "hour", "day", "month", "day_of_week", "lat", "lon",
    "temp", "feels_like", "humidity", "pressure",
    "wind_speed", "wind_deg", "clouds",
    "weather_main", "weather_description",
    "aqi", "pm2_5", "pm10", "co", "no2", "o3", "so2", "nh3",
    "aqi_change_rate"
]

df = df[final_columns]

# save
df.to_csv("aqi_weather_dataset.csv", index=False)

print("Dataset created successfully!")
print(df.head())