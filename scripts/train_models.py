import os
import numpy as np
import pandas as pd
from pymongo import MongoClient
from datetime import datetime, timedelta

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
import joblib

from math import sqrt


# =========================
# 1. LOAD DATA (HOURLY)
# =========================

MONGODB_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGODB_URI)

db = client["aqi_db"]
collection = db["weather_data"]

df = pd.DataFrame(list(collection.find()))

if "_id" in df.columns:
    df.drop(columns=["_id"], inplace=True)

df["datetime"] = pd.to_datetime(df["datetime"])
df = df.sort_values("datetime")

print("Raw data shape:", df.shape)


# =========================
# 2. FEATURE ENGINEERING (HOURLY)
# =========================

df["aqi_diff"] = df["aqi_index"].diff()

# lag features (VERY IMPORTANT)
df["aqi_lag1"] = df["aqi_index"].shift(1)
df["aqi_lag2"] = df["aqi_index"].shift(2)
df["aqi_lag3"] = df["aqi_index"].shift(3)
df["aqi_lag24"] = df["aqi_index"].shift(24)

# rolling features
df["aqi_roll_3"] = df["aqi_index"].rolling(3).mean()
df["aqi_roll_6"] = df["aqi_index"].rolling(6).mean()
df["aqi_roll_24"] = df["aqi_index"].rolling(24).mean()

df = df.dropna()


# =========================
# 3. TARGET (NEXT HOUR AQI)
# =========================

df["target"] = df["aqi_index"].shift(-1)
df = df.dropna()


# =========================
# 4. FEATURES
# =========================

features = [
    "temp",
    "humidity",
    "pressure",
    "wind_speed",
    "wind_deg",
    "clouds",

    "aqi_lag1",
    "aqi_lag2",
    "aqi_lag3",
    "aqi_lag24",

    "aqi_roll_3",
    "aqi_roll_6",
    "aqi_roll_24",

    "aqi_diff"
]

X = df[features]
y = df["target"]


# =========================
# 5. TRAIN TEST SPLIT (TIME ORDERED)
# =========================

split = int(len(df) * 0.8)

X_train, X_test = X.iloc[:split], X.iloc[split:]
y_train, y_test = y.iloc[:split], y.iloc[split:]

results = {}


# =========================
# 6. MODELS
# =========================

models = {
    "LinearRegression": LinearRegression(),

    "Ridge": Ridge(alpha=1.0),

    "RandomForest": RandomForestRegressor(
        n_estimators=200,
        random_state=42
    ),

    "XGBoost": XGBRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8
    ),

    "LightGBM": LGBMRegressor(
        min_data_in_leaf=5,
        verbosity=-1
    )
}


# =========================
# 7. TRAIN + COMPARE MODELS
# =========================

for name, model in models.items():

    model.fit(X_train, y_train)
    preds = model.predict(X_test)

    mae = mean_absolute_error(y_test, preds)
    rmse = sqrt(mean_squared_error(y_test, preds))
    r2 = r2_score(y_test, preds)

    results[name] = (model, mae, rmse, r2)

    print(f"\n{name}")
    print(f"MAE : {mae:.3f}")
    print(f"RMSE: {rmse:.3f}")
    print(f"R2  : {r2:.3f}")


# =========================
# 8. BEST MODEL
# =========================

best_model_name = max(results, key=lambda x: results[x][3])
best_model = results[best_model_name][0]

print("\n🏆 BEST MODEL:", best_model_name)
print("R2:", results[best_model_name][3])


# =========================
# 9. 72-HOUR FORECAST (3 DAYS)
# =========================

def forecast_72_hours(model, df, features):

    df_copy = df.copy()
    predictions = []

    for i in range(72):  # 24h × 3 days

        latest = df_copy.iloc[-1]

        X_input = pd.DataFrame([latest[features]])
        pred = model.predict(X_input)[0]

        predictions.append(pred)

        new_row = latest.copy()

        new_row["aqi_index"] = pred

        # shift lags
        new_row["aqi_lag3"] = latest["aqi_lag2"]
        new_row["aqi_lag2"] = latest["aqi_lag1"]
        new_row["aqi_lag1"] = latest["aqi_index"]
        new_row["aqi_lag24"] = latest["aqi_lag1"]

        # rolling updates
        new_row["aqi_roll_3"] = np.mean(predictions[-3:])
        new_row["aqi_roll_6"] = np.mean(predictions[-6:])
        new_row["aqi_roll_24"] = np.mean(predictions[-24:]) if len(predictions) >= 24 else np.mean(predictions)

        new_row["datetime"] = latest["datetime"] + timedelta(hours=1)

        df_copy = pd.concat([df_copy, pd.DataFrame([new_row])], ignore_index=True)

    return predictions


future_72h = forecast_72_hours(best_model, df, features)


# =========================
# 10. CONVERT TO DAILY FORECAST
# =========================

future_hours = pd.DataFrame({
    # "hour": range(1, 73),
    "predicted_aqi": np.round(future_72h, 3)
})

daily_forecast = future_hours.groupby(future_hours.index // 24).mean().round(3)

daily_forecast["day"] = ["Day 1", "Day 2", "Day 3"]

print("\n🌍 NEXT 3 DAYS AQI FORECAST:")
for _, row in daily_forecast.iterrows():
    print(f"{row['day']}: {row['predicted_aqi']:.2f}")


# =========================
# 11. SAVE MODEL
# =========================

os.makedirs("models", exist_ok=True)
joblib.dump(best_model, f"models/{best_model_name}_model.pkl")


# =========================
# 12. SAVE FORECAST
# =========================

daily_forecast.to_csv("models/next_3_days_aqi.csv", index=False)


# =========================
# 13. METADATA
# =========================

pd.DataFrame([{
    "model": best_model_name,
    "mae": np.round(results[best_model_name][1], 3),
    "rmse": np.round(results[best_model_name][2], 3),
    "r2": np.round(results[best_model_name][3], 3),
    "trained_at": str(datetime.now().date())
}]).to_csv("models/model_metadata.csv", index=False)


print("\n✅ HOURLY PIPELINE + 3-DAY FORECAST COMPLETE")