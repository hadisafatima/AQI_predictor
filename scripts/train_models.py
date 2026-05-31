import os
import io
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
from bson.binary import Binary

# ── CONNECT ───────────────────────────────────────────────────────────────────
MONGODB_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGODB_URI)
db = client["aqi_db"]

collection    = db["weather_data"]
models_col    = db["ml_models"]
forecasts_col = db["aqi_forecasts"]
metadata_col  = db["model_metadata"]

# ── LOAD DATA ─────────────────────────────────────────────────────────────────
df = pd.DataFrame(list(collection.find()))
if "_id" in df.columns:
    df.drop(columns=["_id"], inplace=True)

df["datetime"] = pd.to_datetime(df["datetime"])
df = df.sort_values("datetime")
print("Raw data shape:", df.shape)

# ── FEATURE ENGINEERING ───────────────────────────────────────────────────────
df["aqi_diff"]    = df["aqi_index"].diff()
df["aqi_lag1"]    = df["aqi_index"].shift(1)
df["aqi_lag2"]    = df["aqi_index"].shift(2)
df["aqi_lag3"]    = df["aqi_index"].shift(3)
df["aqi_lag24"]   = df["aqi_index"].shift(24)
df["aqi_roll_3"]  = df["aqi_index"].rolling(3).mean()
df["aqi_roll_6"]  = df["aqi_index"].rolling(6).mean()
df["aqi_roll_24"] = df["aqi_index"].rolling(24).mean()
df = df.dropna()

df_latest = df.copy()   # forecast seed — snapshot before target shift

df["target"] = df["aqi_index"].shift(-1)
df = df.dropna()

features = [
    "temp", "humidity", "pressure", "wind_speed", "wind_deg", "clouds",
    "aqi_lag1", "aqi_lag2", "aqi_lag3", "aqi_lag24",
    "aqi_roll_3", "aqi_roll_6", "aqi_roll_24", "aqi_diff",
]

X, y = df[features], df["target"]

split = int(len(df) * 0.8)
X_train, X_test = X.iloc[:split], X.iloc[split:]
y_train, y_test = y.iloc[:split], y.iloc[split:]

# ── MODELS ────────────────────────────────────────────────────────────────────
models = {
    "LinearRegression": LinearRegression(),
    "Ridge":            Ridge(alpha=1.0),
    "RandomForest":     RandomForestRegressor(n_estimators=200, random_state=42),
    "XGBoost":          XGBRegressor(n_estimators=300, learning_rate=0.05,
                                     max_depth=6, subsample=0.8,
                                     colsample_bytree=0.8),
    "LightGBM":         LGBMRegressor(min_data_in_leaf=5, verbosity=-1),
}

results = {}

# ── TRAIN + EVALUATE + SAVE ALL MODELS ───────────────────────────────────────
print("\nTraining and saving all models...\n")

for name, model in models.items():
    model.fit(X_train, y_train)
    preds = model.predict(X_test)

    mae  = mean_absolute_error(y_test, preds)
    rmse = sqrt(mean_squared_error(y_test, preds))
    r2   = r2_score(y_test, preds)

    results[name] = (model, mae, rmse, r2)

    print(f"{name}  MAE:{mae:.3f}  RMSE:{rmse:.3f}  R2:{r2:.3f}")

    # serialize model to bytes
    buf = io.BytesIO()
    joblib.dump(model, buf)
    buf.seek(0)

    # upsert — one document per model name
    models_col.replace_one(
        {"model_name": name},
        {
            "model_name":   name,
            "model_binary": Binary(buf.read()),
            "features":     features,
            "is_best":      False,          # flagged after loop
            "mae":          round(mae,  3),
            "rmse":         round(rmse, 3),
            "r2":           round(r2,   3),
            "trained_at":   datetime.utcnow(),
        },
        upsert=True,
    )
    print(f"  ✅ '{name}' saved to MongoDB\n")

# ── MARK BEST MODEL ───────────────────────────────────────────────────────────
best_name  = max(results, key=lambda x: results[x][3])
best_model = results[best_name][0]

models_col.update_many({}, {"$set": {"is_best": False}})
models_col.update_one({"model_name": best_name}, {"$set": {"is_best": True}})

print(f"🏆 BEST MODEL: {best_name}  R2: {results[best_name][3]:.3f}")

# ── 72-HOUR RECURSIVE FORECAST ────────────────────────────────────────────────
def forecast_72_hours(model, df, features):
    df_copy     = df.copy().reset_index(drop=True)
    predictions = []

    for i in range(72):
        latest  = df_copy.iloc[-1]
        pred    = model.predict(pd.DataFrame([latest[features]]))[0]
        predictions.append(pred)

        new_row = latest.copy()
        new_row["aqi_index"]   = pred
        new_row["aqi_lag3"]    = latest["aqi_lag2"]
        new_row["aqi_lag2"]    = latest["aqi_lag1"]
        new_row["aqi_lag1"]    = latest["aqi_index"]
        new_row["aqi_lag24"]   = (latest["aqi_lag24"] if i < 24
                                  else df_copy.iloc[-24]["aqi_index"])
        new_row["aqi_roll_3"]  = np.mean(predictions[-3:])
        new_row["aqi_roll_6"]  = np.mean(predictions[-6:])
        new_row["aqi_roll_24"] = (np.mean(predictions[-24:])
                                  if len(predictions) >= 24
                                  else np.mean(predictions))
        new_row["aqi_diff"]    = pred - latest["aqi_index"]
        new_row["datetime"]    = latest["datetime"] + timedelta(hours=1)
        df_copy = pd.concat([df_copy, pd.DataFrame([new_row])], ignore_index=True)

    return predictions

future_72h = forecast_72_hours(best_model, df_latest, features)

# ── SAVE FORECASTS ────────────────────────────────────────────────────────────
base_dt = df_latest["datetime"].iloc[-1]

hourly_docs = [
    {
        "forecast_run":  datetime.utcnow(),
        "model_name":    best_name,
        "hour_offset":   i + 1,
        "datetime":      base_dt + timedelta(hours=i + 1),
        "predicted_aqi": round(float(future_72h[i]), 3),
    }
    for i in range(72)
]

forecasts_col.delete_many({"model_name": best_name})
forecasts_col.insert_many(hourly_docs)
print("✅ 72-hour hourly forecast saved to MongoDB")

daily_docs = []
for day_idx in range(3):
    block = future_72h[day_idx * 24 : (day_idx + 1) * 24]
    daily_docs.append({
        "forecast_run":  datetime.utcnow(),
        "model_name":    best_name,
        "day_label":     f"Day {day_idx + 1}",
        "date":          (base_dt + timedelta(days=day_idx + 1)).date().isoformat(),
        "predicted_aqi": round(float(np.mean(block)), 3),
    })
    print(f"  Day {day_idx + 1}: {daily_docs[-1]['predicted_aqi']:.2f}")

forecasts_col.insert_many(daily_docs)
print("✅ 3-day daily forecast saved to MongoDB")

# ── SAVE METADATA FOR ALL MODELS ─────────────────────────────────────────────
for name, (_, mae, rmse, r2) in results.items():
    metadata_col.replace_one(
        {"model_name": name},
        {
            "model_name": name,
            "mae":        round(mae,  3),
            "rmse":       round(rmse, 3),
            "r2":         round(r2,   3),
            "is_best":    name == best_name,
            "trained_at": datetime.utcnow().isoformat(),
            "features":   features,
        },
        upsert=True,
    )

print("✅ Metadata for all models saved to MongoDB")
print("\n3-DAY FORECAST COMPLETE")