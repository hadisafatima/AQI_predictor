# 🌫️ AQI Forecast — Matiari Air Quality Intelligence Platform

> End-to-end serverless machine learning pipeline for 72-hour Air Quality Index forecasting in **Matiari, Sindh, Pakistan**.

Automated data collection · Feature engineering · Multi-model training · Real-time Streamlit dashboard · SHAP explainability · Hazard alerts

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Workflow](#workflow)
5. [Pipeline Details](#pipeline-details)
6. [Models & Evaluation](#models--evaluation)
7. [SHAP Explainability](#shap-explainability)
8. [Alerts System](#alerts-system)
9. [CI/CD Automation](#cicd-automation)
10. [Challenges & Resolutions](#challenges--resolutions)
11. [Results](#results)
12. [Future Improvements](#future-improvements)

---

## Project Overview

This project delivers a fully automated AQI forecasting system for **Matiari, Sindh, Pakistan** (25.5961°N, 68.4467°E) — a region with seasonal smog events, agricultural burning cycles, and proximity to Hyderabad's industrial zone where real-time air quality monitoring is limited.

The system runs end-to-end without manual intervention: it collects live hourly weather and pollutant data, stores it in a cloud database, retrains machine learning models daily, and serves a 3-day AQI forecast through an interactive web dashboard with hazard alerts and explainability.

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
| ML Models | scikit-learn, XGBoost, LightGBM |
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

The dashboard connects to MongoDB using a URI entered in the sidebar, then runs the full pipeline on demand when the user clicks Train & Forecast. It displays a real-time AQI gauge for the current reading, a 7-day historical trend chart, a 72-hour forecast line chart with AQI band shading, three day-forecast cards with colour-coded severity, a five-model benchmark comparison, an actual-vs-predicted chart on the test set, and a SHAP feature importance chart. A tiered alert system evaluates both current and forecasted AQI and surfaces contextual warnings.

---

## Models & Evaluation

Five models are trained and benchmarked on every pipeline run. The winner is automatically selected by R² score.

| Model | Role |
|---|---|
| Linear Regression | Interpretable baseline |
| Ridge Regression | Handles correlated lag features via L2 regularisation |
| Random Forest | Non-linear ensemble baseline |
| XGBoost | Gradient-boosted trees; typically highest accuracy |
| LightGBM | Faster gradient boosting; competitive on larger datasets |

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

### 1. Forecast values exploding on Day 2 and Day 3

The first time the forecast ran, Day 1 looked plausible but Day 2 reached 609 and Day 3 reached 691 — physically impossible AQI values.

The root cause was a single incorrect line in the forecast loop: `aqi_lag24` was being set to the value of `aqi_lag1` (the 1-hour-ago AQI) instead of the actual 24-hours-ago AQI. Since `aqi_lag24` captures the diurnal pollution cycle, feeding it the wrong value immediately corrupted the model's most important contextual signal. Because each step feeds into the next, the error compounded over 48 steps until predictions were completely outside the training distribution.

The fix was to carry the real precomputed `aqi_lag24` value for the first 24 forecast steps (before any predicted history exists), then look back 24 rows into the growing prediction history for all subsequent steps.

---

### 2. Script and dashboard producing different forecast values despite identical models

After fixing the lag24 bug, `train_models.py` gave Day 1 as 226 while the dashboard showed 257 — a persistent ~30 AQI unit gap on the first day.

The root cause was that both forecast functions were starting from different rows. The training script passed its DataFrame to the forecast function after adding the target column and dropping the resulting NaN row — which silently removed the single most recent real data point. The dashboard was already using a pre-snapshot copy, so it started from the true latest reading while the script always started one hour behind.

The fix was to snapshot the DataFrame before the target shift in both files, and pass that snapshot as the forecast seed. Once both functions started from the same row, their outputs matched exactly.

---

### 3. Plotly `update_layout()` crash — duplicate keyword argument

The dashboard crashed on startup with a Python `TypeError` about `margin` being passed twice to `update_layout()`.

The cause was a shared layout dictionary (`DARK_LAYOUT`) that already contained a `margin` definition. The SHAP plot function then also passed its own `margin` as a separate keyword argument. When both were unpacked into the same function call, Python raised an error because the same keyword appeared twice.

The fix was to merge both dictionaries into one before the call, so the SHAP-specific `margin` cleanly overrides the shared default.

---

### 4. MongoDB TLS certificate errors on Windows and GitHub Actions

Connecting to MongoDB Atlas failed on certain Windows development machines and GitHub Actions runners with an SSL certificate verification error.

The cause was that those environments lacked the full CA certificate bundle needed to validate MongoDB Atlas's TLS certificate chain. The fix was to add `tls=True` and `tlsAllowInvalidCertificates=True` to the MongoClient constructor. This is acceptable for a development and low-stakes forecasting context; for a production system, the proper CA certificate path should be specified instead.

---

### 5. Historical backfill inserting duplicate records on re-run

Running `historical_fetch.py` a second time doubled every record in MongoDB, which skewed the training data by giving historical periods twice the weight of recent data.

The cause was that `insert_one()` performs no deduplication — it always creates a new document. The fix was to switch to an upsert operation keyed on the `(city, datetime)` pair, so re-running the backfill safely updates existing records rather than duplicating them.

---

### 6. Streamlit re-running the full MongoDB query on every UI interaction

Every time a user interacted with any widget on the dashboard — even just hovering over a chart — Streamlit reran the entire script, triggering a fresh MongoDB connection and full data load. This caused 5–10 second delays and occasional connection pool exhaustion.

The fix was to wrap the data loading function in Streamlit's `@st.cache_data` decorator, using the MongoDB URI as the cache key. Data is fetched once per session and served from memory on all subsequent reruns, making the dashboard feel instantaneous after the initial load.

---

## Results

The system consistently achieves strong performance on Matiari's hourly AQI data. R² scores typically fall between 0.92 and 0.98, MAE between 5 and 18 AQI units, and RMSE between 8 and 25 AQI units. XGBoost and LightGBM are the most frequent winners. SHAP analysis consistently identifies `aqi_lag1`, `aqi_lag2`, and `aqi_roll_3` as the top prediction drivers, confirming that recent AQI history dominates short-term forecasting for Matiari's pollution patterns.

---

## Future Improvements

- Replace `max(pollutants)` with the official US EPA breakpoint-based AQI formula for each pollutant
- Add LSTM or Temporal Fusion Transformer models for longer-horizon and sequence-aware forecasting
- Migrate from MongoDB to Hopsworks for full feature versioning and point-in-time correctness
- Add forecast confidence intervals via quantile regression or conformal prediction
- Extend coverage to Hyderabad, Sukkur, and other Sindh cities
- Add WhatsApp or SMS push alerts for hazardous AQI events via Twilio

---

<div align="center">

Built for **Matiari, Sindh, Pakistan 🇵🇰** · Predicting air quality so communities can breathe safer.

</div>