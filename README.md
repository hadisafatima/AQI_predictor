# 🌫️ AQI Forecast — Matiari Air Quality Intelligence Platform

<!-- > End-to-end serverless machine learning pipeline for 72-hour Air Quality Index forecasting in **Matiari, Sindh, Pakistan**.

Automated data collection · Feature engineering · Multi-model training · Real-time Streamlit dashboard · SHAP explainability · Hazard alerts -->

---

## Project Overview

This project delivers a fully automated AQI forecasting system for **Matiari, Sindh, Pakistan** — a region with seasonal smog events, agricultural burning cycles, and proximity to Hyderabad's industrial zone where real-time air quality monitoring is limited.

The system runs end-to-end without manual intervention: it collects live hourly weather and pollutant data, stores it in a cloud database, retrains machine learning models daily, and serves a 3-day AQI forecast through an interactive web dashboard with hazard alerts.

---

## Architecture

```
OpenWeatherMap API          Open-Meteo Archive API
 (live: hourly data)         (historical backfill)
        │                            │
        ▼                            ▼
   hourly_fetch.py          historical_fetch.py
        │                            │
        └──────────┬─────────────────┘
                   ▼
        MongoDB Atlas — Feature Store
        (aqi_db · weather_data collection)
                   │
                   ▼
           train_models.py
     (feature engineering + training)
                   │
                   ▼
          aqi_dashboard.py
   (Streamlit · forecast · SHAP · alerts)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Live Data | OpenWeatherMap API (weather + air pollution) |
| Historical Data | Open-Meteo Archive & Air Quality APIs (free, no key) |
| Feature Store | MongoDB Atlas (serverless, free M0 tier) |
| ML Models | LinearRegression, Ridge, RandomForest, XGBoost, LightGBM |
| Explainability | SHAP (TreeExplainer / LinearExplainer) |
| Dashboard | Streamlit + Plotly |
| Automation | GitHub Actions (hourly + daily schedules) |
| Deployment | Streamlit Community Cloud |

---

## Workflow

The system runs as three independent automated stages:

**Stage 1 — Data Collection (every hour)**
GitHub Actions triggers `hourly_fetch.py` each hour. It pulls current weather and air pollution readings from OpenWeatherMap for Matiari, computes a custom AQI index from the pollutant concentrations, calculates the change rate vs the previous reading, and inserts the enriched record into MongoDB Atlas.

**Stage 2 — Model Training (every day)**
GitHub Actions triggers `train_models.py` each morning. It loads the full feature history from MongoDB, engineers time-series features, trains five ML models, evaluates them, saves the best one, and writes a 3-day forecast CSV.

**Stage 3 — Dashboard (on demand)**
The Streamlit app is always live. When a user clicks Train & Forecast, it runs the complete pipeline in real time — loading data, training models, generating the 72-hour forecast, computing SHAP values, and rendering all visualisations in one pass.

---

## Pipeline Details

### Hourly Feature Pipeline (`hourly_fetch.py`)

Every hour, the pipeline fetches two data streams from OpenWeatherMap for Matiari's coordinates and merges them into a single document stored in MongoDB. The weather stream provides temperature, humidity, atmospheric pressure, wind speed and direction, and cloud cover. The air pollution stream provides concentrations of PM2.5, PM10, NO₂, O₃, SO₂, and CO.

The AQI index is computed as the maximum concentration across all available pollutants — a conservative metric that flags the worst-case pollutant as the dominant risk signal. The pipeline also computes `aqi_change_rate` by comparing the current reading against the most recent document in MongoDB, giving the model a real-time trend signal.

Each document also stores time features (hour, day, month, year, day of week) to support potential future seasonality modelling.

### Historical Backfill (`historical_fetch.py`)

Before the live pipeline had enough data for model training, a one-time backfill script was run to seed MongoDB with months of historical records. It fetches hourly weather from the Open-Meteo Archive API and hourly pollutant concentrations from the Open-Meteo Air Quality API — both free, open APIs that require no key. The two datasets are merged on matching timestamps and inserted into the same MongoDB collection as the live pipeline, creating a seamless unified dataset.

### Training Pipeline (`train_models.py`)

The training pipeline loads all MongoDB records into a DataFrame and engineers a set of time-series features on top of the raw weather and pollutant fields. Lag features capture AQI values from 1, 2, 3, and 24 hours ago. Rolling mean features capture short-term (3h, 6h) and diurnal (24h) trends. An `aqi_diff` feature captures the hourly rate of change.

A critical design decision here is snapshotting a copy of the DataFrame before adding the prediction target. The target column (`next hour's AQI`) is created by shifting `aqi_index` forward by one step, which causes the final row to become NaN and get dropped. That final row — the most recent real reading — is exactly what the forecast needs as its starting point. Snapshotting before the shift preserves it.

The train/test split is strictly time-ordered: the first 80% of records train the model, the last 20% evaluate it. No shuffling occurs so future data never leaks into training.

### 72-Hour Autoregressive Forecast

The forecast function predicts the next hour's AQI, then feeds that prediction back as input for the following hour, rolling forward 72 times. At each step it updates all lag and rolling features using the growing list of predicted values. The `aqi_lag24` feature is handled with special care: for the first 24 steps, the real feature-engineered value from the seed row is carried forward (no predicted history exists yet); from step 24 onward, the prediction from 24 steps back is used instead.

The 72 hourly predictions are grouped into three blocks of 24 and averaged to produce a single daily AQI estimate for each of the three forecast days.

### Dashboard (`aqi_dashboard.py`)

The dashboard connects to MongoDB using the respective URI, then runs the full pipeline when the user clicks Train & Forecast. It displays a real-time AQI gauge for the current reading, a 7-day historical trend chart, a 72-hour forecast line chart with AQI band shading, three day-forecast cards with colour-coded severity, a five-model benchmark comparison, an actual-vs-predicted chart on the test set, and a SHAP feature importance chart. A tiered alert system evaluates both current and forecasted AQI and surfaces contextual warnings.

---

## Models & Evaluation

Five models are trained and benchmarked on every pipeline run. The winner is automatically selected by R² score.

### Models
1. Linear Regression 
2. Ridge Regression
3. Random Forest
4. XGBoost
5. LightGBM 

Models are evaluated on MAE (average AQI units off), RMSE (penalises large errors), and R² (overall fit quality, used for selection).

---

## SHAP Explainability

After training, SHAP values are computed on the test set to explain what the best model learned. The appropriate explainer is selected automatically — TreeExplainer for XGBoost, LightGBM, and Random Forest; LinearExplainer for Ridge and Linear Regression.

The dashboard shows mean absolute SHAP values per feature, indicating how much each feature consistently moves predictions up or down. Lag features (`aqi_lag1`, `aqi_lag2`) typically dominate, confirming that recent AQI history is the strongest short-term signal. Weather features like wind speed and humidity show secondary importance, reflecting their role in pollution dispersion. A top-3 driver callout highlights the most influential features for the winning model on that run.

---

## Alerts System

The dashboard evaluates both the current AQI reading and each of the three forecasted days against four thresholds:

| Level | AQI Range | Recommendation |
|---|---|---|
| ✅ All Clear | 0 – 150 | No restrictions |
| 🟠 Unhealthy | 151 – 200 | Reduce prolonged outdoor activity |
| 🔴 Very Unhealthy | 201 – 300 | Sensitive groups should remain indoors |
| 🚨 Hazardous | 301 – 500 | Avoid all outdoor exposure |

Forecast alerts give Matiari residents up to 72 hours of advance warning to adjust outdoor schedules, school activity, or agricultural work before hazardous conditions arrive.

---

## CI/CD Automation

Two GitHub Actions workflows run on schedule using repository secrets for credentials.

The **hourly workflow** triggers `hourly_fetch.py` at the top of every hour. It installs dependencies, runs the fetch script, and inserts the new record into MongoDB. The only secrets required are the MongoDB URI and the OpenWeatherMap API key.

The **daily workflow** triggers `train_models.py` every morning at 2 AM UTC. It retrains all five models on the latest accumulated dataset and overwrites the saved model artifact and forecast CSV. This ensures the dashboard always serves predictions from a model trained on the most recent data.

---

## Challenges & Resolutions

### 1. Hopsworks Integration Issues
Faced connectivity and setup problems with Hopsworks, so the project was migrated to MongoDB Atlas for easier cloud storage, scalability, and smoother real-time data handling.

### 2. API Reliability Problems
External AQI and weather APIs sometimes returned missing or inconsistent data. This was solved using error handling, retries, and data validation techniques.

### 3. Model Training Complexity
Managing multiple ML models and retraining pipelines was challenging. A modular training pipeline was created to automate preprocessing, training, and evaluation.

### 4. Streamlit & Import Errors
Issues like ModuleNotFoundError and poor project structure were resolved by reorganizing the project into modular folders and reusable components.

### 5. Feature Engineering Challenges
Converting raw AQI/weather data into useful features required extensive preprocessing, including time-based and lag features to improve prediction accuracy.

### 6. Real-Time Prediction Stability
AQI values fluctuate rapidly, affecting forecast consistency. Regular retraining and rolling historical data windows improved prediction reliability.

### 7. Serverless Architecture Management
Integrating cloud services and automation in a fully serverless environment was difficult initially, but optimized workflows and lightweight architecture solved scalability issues.

---

<div align="center">

Built for **Matiari, Sindh, Pakistan 🇵🇰**

</div>