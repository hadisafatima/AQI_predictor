import os
import numpy as np
import pandas as pd
from pymongo import MongoClient
from datetime import datetime

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
import joblib

from math import sqrt

# Statistical models
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing

# Deep learning
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense

# =========================
# 1. CONNECT TO MONGODB (FEATURE STORE)
# =========================
MONGODB_URI = os.getenv("MONGODB_URI")

client = MongoClient(MONGODB_URI)
db = client["aqi_db"]
collection = db["weather"]

data = list(collection.find())
df = pd.DataFrame(data)

if "_id" in df.columns:
    df.drop(columns=["_id"], inplace=True)

print("Data loaded:", df.shape)

# =========================
# 2. FEATURE ENGINEERING
# =========================
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values("timestamp")

df["aqi_lag1"] = df["aqi"].shift(1)
df["aqi_lag2"] = df["aqi"].shift(2)
df["aqi_roll_mean"] = df["aqi"].rolling(3).mean()
df = df.dropna()

# =========================
# 3. ML DATASET
# =========================
features = [
    "temp", "feels_like", "humidity",
    "pressure", "wind_speed", "wind_deg",
    "clouds", "aqi_lag1", "aqi_lag2", "aqi_roll_mean"
]

X = df[features]
y = df["aqi"]

split = int(len(df) * 0.8)

X_train, X_test = X.iloc[:split], X.iloc[split:]
y_train, y_test = y.iloc[:split], y.iloc[split:]

results = {}

# =========================
# 4. MACHINE LEARNING MODELS
# =========================
ml_models = {
    "LinearRegression": LinearRegression(),
    "RandomForest": RandomForestRegressor(n_estimators=100, random_state=42),
    "XGBoost": XGBRegressor(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=5
    ),
    "LightGBM": LGBMRegressor()
}

for name, model in ml_models.items():
    model.fit(X_train, y_train)
    preds = model.predict(X_test)

    mae = mean_absolute_error(y_test, preds)
    rmse = sqrt(mean_squared_error(y_test, preds))
    r2 = r2_score(y_test, preds)

    results[name] = (model, mae, rmse, r2)

    print(f"\n{name} -> MAE:{mae:.3f}, RMSE:{rmse:.3f}, R2:{r2:.3f}")

# =========================
# 5. STATISTICAL MODELS
# =========================
train_series = df["aqi"].iloc[:split]

# ARIMA
try:
    arima_model = ARIMA(train_series, order=(5,1,0)).fit()
    arima_pred = arima_model.forecast(steps=len(df) - split)

    mae = mean_absolute_error(y_test, arima_pred)
    rmse = sqrt(mean_squared_error(y_test, arima_pred))
    r2 = r2_score(y_test, arima_pred)

    results["ARIMA"] = (arima_model, mae, rmse, r2)
    print(f"\nARIMA -> MAE:{mae:.3f}, RMSE:{rmse:.3f}, R2:{r2:.3f}")
except:
    print("ARIMA failed")

# Holt-Winters
try:
    hw_model = ExponentialSmoothing(train_series, seasonal="add", seasonal_periods=24).fit()
    hw_pred = hw_model.forecast(len(df) - split)

    mae = mean_absolute_error(y_test, hw_pred)
    rmse = sqrt(mean_squared_error(y_test, hw_pred))
    r2 = r2_score(y_test, hw_pred)

    results["HoltWinters"] = (hw_model, mae, rmse, r2)
    print(f"\nHoltWinters -> MAE:{mae:.3f}, RMSE:{rmse:.3f}, R2:{r2:.3f}")
except:
    print("HoltWinters failed")

# =========================
# 6. LSTM MODEL (Deep Learning)
# =========================

def create_sequences(data, target, step=10):
    X_seq, y_seq = [], []
    for i in range(len(data) - step):
        X_seq.append(data[i:i+step])
        y_seq.append(target[i+step])
    return np.array(X_seq), np.array(y_seq)

dl_df = df[features].values
dl_target = df["aqi"].values

X_seq, y_seq = create_sequences(dl_df, dl_target)

split_dl = int(len(X_seq) * 0.8)

X_train_dl, X_test_dl = X_seq[:split_dl], X_seq[split_dl:]
y_train_dl, y_test_dl = y_seq[:split_dl], y_seq[split_dl:]

lstm = Sequential([
    LSTM(64, return_sequences=True, input_shape=(X_train_dl.shape[1], X_train_dl.shape[2])),
    LSTM(32),
    Dense(1)
])

lstm.compile(optimizer="adam", loss="mse")
lstm.fit(X_train_dl, y_train_dl, epochs=5, batch_size=16, verbose=0)

lstm_preds = lstm.predict(X_test_dl).flatten()

mae = mean_absolute_error(y_test_dl, lstm_preds)
rmse = sqrt(mean_squared_error(y_test_dl, lstm_preds))
r2 = r2_score(y_test_dl, lstm_preds)

results["LSTM"] = (lstm, mae, rmse, r2)

print(f"\nLSTM -> MAE:{mae:.3f}, RMSE:{rmse:.3f}, R2:{r2:.3f}")

# =========================
# 7. SELECT BEST MODEL
# =========================
best_model_name = min(results, key=lambda x: results[x][1])
best_model = results[best_model_name][0]

print("\nBEST MODEL:", best_model_name)

# =========================
# 8. SAVE MODEL (MODEL REGISTRY SIMULATION)
# =========================
os.makedirs("models", exist_ok=True)

if best_model_name == "LSTM":
    best_model.save(f"models/{best_model_name}_model.h5")
else:
    joblib.dump(best_model, f"models/{best_model_name}_model.pkl")

metadata = pd.DataFrame([{
    "model": best_model_name,
    "mae": results[best_model_name][1],
    "rmse": results[best_model_name][2],
    "r2": results[best_model_name][3],
    "trained_at": str(datetime.now())
}])

metadata.to_csv("models/model_metadata.csv", index=False)

print("\nModel saved successfully!")