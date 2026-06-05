# 🌫️ AQI Forecast — Matiari Air Quality Intelligence Platform

An automated AQI forecasting system for **Matiari, Sindh, Pakistan** — a region affected by seasonal smog, agricultural burning cycles, and proximity to Hyderabad's industrial zone. The system collects live hourly data, retrains ML models daily, and serves a 3-day forecast through an interactive dashboard with hazard alerts.

---

🔴 **Live Demo** → [hadisafatima-aqi-predictor.streamlit.app](https://hadisafatima-aqi-predictor-aqi-dashboard-khghxu.streamlit.app/)

---

## Architecture

```
OpenWeatherMap API          Open-Meteo Archive API
 (live: hourly data)         (historical backfill)
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
        MongoDB Atlas — Model Store
        (aqi_db · models collection)
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
| Feature Store | MongoDB Atlas — `weather_data` collection |
| Model Store | MongoDB Atlas — `models` collection (serialised with GridFS) |
| ML Models | LinearRegression, Ridge, RandomForest, XGBoost, LightGBM |
| Explainability | SHAP (TreeExplainer / LinearExplainer) |
| Dashboard | Streamlit + Plotly |
| Automation | GitHub Actions (hourly + daily schedules) |
| Deployment | Streamlit Community Cloud |

---

## Workflow

**Stage 1 — Data Collection (every hour)**
`hourly_fetch.py` pulls weather and air pollution data from OpenWeatherMap, computes a custom AQI index, calculates change rate vs the previous reading, and inserts the enriched record into MongoDB.

**Stage 2 — Model Training (every day)**
`train_models.py` loads the full feature history, engineers time-series features, trains five ML models, evaluates them, saves the best one, and writes a 3-day forecast CSV.

**Stage 3 — Dashboard (on demand)**
The Streamlit app runs the full pipeline on user request — loading data, training models, generating the 72-hour forecast, computing SHAP values, and rendering all visualisations.

---

## Pipeline Details

### Hourly Feature Pipeline (`hourly_fetch.py`)
Fetches weather (temperature, humidity, pressure, wind, cloud cover) and air pollution (PM2.5, PM10, NO₂, O₃, SO₂, CO) from OpenWeatherMap. AQI is computed as the avearge of all the pollutants — a conservative worst-case signal. `aqi_change_rate` is derived by comparing against the previous MongoDB record. Time features (hour, day, month, etc.) are also stored for seasonality modelling.

### Historical Backfill (`historical_fetch.py`)
A one-time script that seeded MongoDB with months of historical data using the Open-Meteo Archive and Air Quality APIs (free, no key required). Records are merged on matching timestamps and inserted into the same collection as live data, creating a unified dataset.

### Training Pipeline (`train_models.py`)
Loads all MongoDB records and engineers lag features (1h, 2h, 3h, 24h), rolling means (3h, 6h, 24h), and an `aqi_diff` change signal. The DataFrame is snapshotted before the prediction target is created (next hour's AQI via a forward shift) to preserve the most recent row as the forecast seed. Train/test split is strictly time-ordered (80/20) — no shuffling. The winning model is serialised and saved back to MongoDB, so the dashboard always loads the latest trained model directly from the cloud.

### 72-Hour Autoregressive Forecast
Predicts the next hour's AQI, feeds that prediction back as input, and rolls forward 72 steps — updating all lag and rolling features at each step. `aqi_lag24` uses real seed values for the first 24 steps, then switches to predictions. The 72 hourly values are grouped into three 24-hour blocks and averaged for the daily forecast cards.

### Dashboard (`aqi_dashboard.py`)
Displays: a real-time AQI gauge, 7-day historical trend, 72-hour forecast chart with AQI band shading, three day-forecast cards, a five-model benchmark table, actual-vs-predicted chart, and SHAP feature importance. A tiered alert system evaluates both current and forecasted AQI.

---

## Models & Evaluation

Five models are trained and benchmarked on every run. The best R² score wins automatically and is serialised back to MongoDB — so the dashboard always loads the latest model directly from the cloud without relying on local files.

1. Linear Regression
2. Ridge Regression
3. Random Forest
4. XGBoost
5. LightGBM

Evaluation metrics: **MAE** (average units off), **RMSE** (penalises large errors), **R²** (overall fit, used for selection).

---

## SHAP Explainability

SHAP values are computed on the test set after training. TreeExplainer is used for XGBoost, LightGBM, and Random Forest; LinearExplainer for Ridge and Linear Regression. `aqi_roll_3` & `aqi_lag2` typically dominate. `aqi_diff` & `aqi_roll_6` have secondary importance. A top-3 driver callout highlights the most influential features for that run.

---

## Alerts System

| Level | AQI Range | Recommendation |
|---|---|---|
| ✅ All Clear | 0 – 150 | No restrictions |
| 🟠 Unhealthy | 151 – 200 | Reduce prolonged outdoor activity |
| 🔴 Very Unhealthy | 201 – 300 | Sensitive groups should remain indoors |
| 🚨 Hazardous | 301 – 500 | Avoid all outdoor exposure |

Alerts cover both current readings and all three forecast days, giving residents up to 72 hours of advance warning.

---

## CI/CD Automation

Two GitHub Actions workflows run on schedule using repository secrets.

- **Hourly workflow** — triggers `hourly_fetch.py` at the top of every hour; inserts new records into MongoDB.
- **Daily workflow** — triggers `train_models.py` at 2 AM UTC; retrains all five models, selects the best, and saves it to MongoDB alongside a fresh forecast CSV.

---

## Challenges & Resolutions

| Challenge | Resolution |
|---|---|
| Hopsworks connectivity issues | Migrated to MongoDB Atlas for easier cloud storage and real-time handling |
| API missing/inconsistent data | Added error handling, retries, and data validation |
| Loading models | Implemented Streamlit's @st.cache_resource mechanism to keep models in memory and avoid repeated downloads from MongoDB.
| Streamlit import errors | Reorganised project into modular folders and reusable components |
| Feature engineering complexity | Implemented time-based and lag features for better prediction accuracy |
| Forecast Future AQI | Implemented recursive forecasting, where each predicted AQI value becomes an input for predicting subsequent hours, enabling 72-hour forecasting. |

---

## What I Learned

- **GitHub Actions** — Built fully automated scheduled pipelines for hourly data collection and daily retraining, learning cron scheduling, secret management, and debugging from workflow logs.
- **API Data Fetching** — Integrated multiple external APIs and handled real-world issues like missing fields, inconsistent responses, and rate limits through resilient error handling.
- **Cloud Storage with MongoDB Atlas** — Used MongoDB as both a feature store (time-series weather/AQI records) and a model store (serialised trained models). This eliminated local file dependencies entirely, making the pipeline fully cloud-native.
- **Autoregressive Forecasting** — Learned how prediction errors compound when fed back as inputs, and how to carefully manage lag features (like `aqi_lag24`) that lack predicted history in early forecast steps.
- **SHAP Explainability** — Applied model-agnostic and model-specific explainers to understand feature importance, turning a black-box ensemble into interpretable, actionable insights.
- **End-to-End ML System Design** - Learned how to build, deploy, monitor, and maintain a complete machine learning pipeline. Gained practical experience in combining data engineering, ML, cloud storage, and visualization into a production-ready solution.

---

<div align="center">

Built for **Matiari, Sindh, Pakistan 🇵🇰**

</div>