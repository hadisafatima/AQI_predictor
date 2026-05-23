import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from pymongo import MongoClient
from datetime import datetime, timedelta
from math import sqrt
import warnings
warnings.filterwarnings("ignore")

# ── ML ──────────────────────────────────────────────────────────────────────
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
import shap

# PAGE CONFIG
st.set_page_config(
    page_title="AQI Forecast - Matiari",
    page_icon="🌫️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CUSTOM CSS 
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=IBM+Plex+Mono:wght@300;400;500&display=swap');

:root {
    --bg:      #0d0d0f;
    --surface: #141417;
    --border:  #2a2a30;
    --amber:   #f5a623;
    --red:     #e84040;
    --green:   #3ecf8e;
    --blue:    #4fb3ff;
    --text:    #e8e8ec;
    --muted:   #6b6b7a;
}

html, body, [class*="css"] { font-family: 'IBM Plex Mono', monospace; }

/* ── App background ── */
.stApp { background: var(--bg); color: var(--text); }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: var(--surface);
    border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] * { color: var(--text) !important; }

/* ── Metric cards ── */
div[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1rem 1.2rem;
}
div[data-testid="stMetricValue"] { color: var(--amber) !important; font-family: 'Syne', sans-serif; font-size: 2rem !important; }
div[data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: 0.7rem !important; letter-spacing: .12em; text-transform: uppercase; }

/* ── Buttons ── */
.stButton > button {
    background: var(--amber);
    color: #0d0d0f;
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 0.85rem;
    letter-spacing: .06em;
    border: none;
    border-radius: 4px;
    padding: .55rem 1.4rem;
    transition: opacity .15s;
}
.stButton > button:hover { opacity: .85; }

/* ── Section headers ── */
.sec-head {
    font-family: 'Syne', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: var(--amber);
    border-bottom: 1px solid var(--border);
    padding-bottom: .4rem;
    margin-bottom: 1rem;
}

/* ── Alert boxes ── */
.alert-box {
    border-left: 4px solid var(--red);
    background: rgba(232,64,64,.10);
    border-radius: 4px;
    padding: .7rem 1rem;
    margin-bottom: .5rem;
    font-size: .82rem;
    font-family: 'IBM Plex Mono', monospace;
}
.alert-box.warn {
    border-color: #ffb347;
    background: rgba(255,179,71,.09);
}
.alert-box.ok {
    border-color: var(--green);
    background: rgba(62,207,142,.09);
}

/* ── Forecast day cards ── */
.day-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.2rem 1rem;
    text-align: center;
}
.day-label { font-size:.7rem; color:var(--muted); letter-spacing:.12em; text-transform:uppercase; margin-bottom:.3rem; }
.day-val   { font-family:'Syne',sans-serif; font-size:2.4rem; font-weight:800; }
.day-cat   { font-size:.72rem; letter-spacing:.1em; margin-top:.3rem; text-transform:uppercase; }

/* ── Expander ── */
details { border: 1px solid var(--border) !important; border-radius:6px !important; background:var(--surface) !important; }
summary { color: var(--text) !important; font-size:.82rem; }

/* ── Data frames ── */
.stDataFrame { border: 1px solid var(--border) !important; }

/* ── Divider ── */
hr { border-color: var(--border) !important; }

/* ── Progress / spinner ── */
.stSpinner > div > div { border-top-color: var(--amber) !important; }
</style>
""", unsafe_allow_html=True)


# AQI HELPERS
def aqi_category(val):
    v = float(val)
    if v <= 50:   return "Good",          "#3ecf8e"
    if v <= 100:  return "Moderate",      "#f5a623"
    if v <= 150:  return "Unhealthy (Sensitive)", "#ff8c42"
    if v <= 200:  return "Unhealthy",     "#e84040"
    if v <= 300:  return "Very Unhealthy","#9b5de5"
    return            "Hazardous",        "#c70039"

def aqi_gauge(val):
    cat, color = aqi_category(val)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        number={"font": {"size": 48, "color": color, "family": "Syne"}},
        gauge={
            "axis": {"range": [0, 500], "tickcolor": "#6b6b7a",
                     "tickfont": {"color": "#6b6b7a", "size": 10}},
            "bar": {"color": color},
            "bgcolor": "#141417",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 50],   "color": "rgba(62,207,142,.18)"},
                {"range": [50, 100], "color": "rgba(245,166,35,.18)"},
                {"range": [100,150], "color": "rgba(255,140,66,.18)"},
                {"range": [150,200], "color": "rgba(232,64,64,.18)"},
                {"range": [200,300], "color": "rgba(155,93,229,.18)"},
                {"range": [300,500], "color": "rgba(199,0,57,.18)"},
            ],
            "threshold": {"line": {"color": color, "width": 3}, "thickness": .75, "value": val},
        },
        title={"text": f"<span style='font-size:14px;color:#6b6b7a;letter-spacing:.12em'>{cat.upper()}</span>"}
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=30, b=0, l=20, r=20), height=240,
        font_family="IBM Plex Mono"
    )
    return fig


# DATA LOADING
@st.cache_data(show_spinner=False)
def load_data(uri: str) -> pd.DataFrame:
    client = MongoClient(uri)
    db = client["aqi_db"]
    col = db["weather_data"]
    df = pd.DataFrame(list(col.find()))
    if "_id" in df.columns:
        df.drop(columns=["_id"], inplace=True)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    return df


# FEATURE ENGINEERING
FEATURES = [
    "temp","humidity","pressure","wind_speed","wind_deg","clouds",
    "aqi_lag1","aqi_lag2","aqi_lag3","aqi_lag24",
    "aqi_roll_3","aqi_roll_6","aqi_roll_24","aqi_diff",
]

def engineer_features(df: pd.DataFrame):
    """
    Returns:
        df_model  — includes 'target' col; last row dropped due to shift(-1). Used for training.
        df_latest — same lag/rolling features but NO target drop. Last row = most recent real
                    data point, used as the forecast seed (matches the original train script).
    """
    df = df.copy()
    df["aqi_diff"]    = df["aqi_index"].diff()
    df["aqi_lag1"]    = df["aqi_index"].shift(1)
    df["aqi_lag2"]    = df["aqi_index"].shift(2)
    df["aqi_lag3"]    = df["aqi_index"].shift(3)
    df["aqi_lag24"]   = df["aqi_index"].shift(24)
    df["aqi_roll_3"]  = df["aqi_index"].rolling(3).mean()
    df["aqi_roll_6"]  = df["aqi_index"].rolling(6).mean()
    df["aqi_roll_24"] = df["aqi_index"].rolling(24).mean()
    df = df.dropna()                   # drop NaN rows from lag/rolling only

    df_latest = df.copy()              # ← seed for forecast; last row = true latest reading

    df["target"] = df["aqi_index"].shift(-1)
    df_model = df.dropna()             # ← for training; last row removed due to shift(-1)

    return df_model, df_latest


# MODEL TRAINING
def train_models(df: pd.DataFrame):
    X = df[FEATURES]
    y = df["target"]
    split = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    models = {
        "LinearRegression": LinearRegression(),
        "Ridge":            Ridge(alpha=1.0),
        "RandomForest":     RandomForestRegressor(n_estimators=200, random_state=42),
        "XGBoost":          XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=6,
                                         subsample=0.8, colsample_bytree=0.8),
        "LightGBM":         LGBMRegressor(min_data_in_leaf=5, verbosity=-1),
    }

    results = {}
    for name, model in models.items():
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        results[name] = {
            "model": model,
            "preds": preds,
            "mae":   mean_absolute_error(y_test, preds),
            "rmse":  sqrt(mean_squared_error(y_test, preds)),
            "r2":    r2_score(y_test, preds),
        }

    best_name = max(results, key=lambda x: results[x]["r2"])
    return results, best_name, X_train, X_test, y_test


# 72-HOUR FORECAST
def forecast_72h(model, df: pd.DataFrame) -> list:
    # Exact mirror of forecast_72_hours() in train_models.py
    df_copy = df.copy().reset_index(drop=True)
    predictions = []
    for i in range(72):
        latest = df_copy.iloc[-1]
        X_in = pd.DataFrame([latest[FEATURES]])
        pred = float(model.predict(X_in)[0])
        predictions.append(pred)
        new_row = latest.copy()
        new_row["aqi_index"] = pred
        # shift short lags — identical to train_models.py
        new_row["aqi_lag3"]  = latest["aqi_lag2"]
        new_row["aqi_lag2"]  = latest["aqi_lag1"]
        new_row["aqi_lag1"]  = latest["aqi_index"]
        # aqi_lag24: carry latest["aqi_lag24"] for first 24 steps (no predicted history yet),
        # then use the aqi_index from 24 appended rows ago — matches train_models.py behaviour
        if i < 24:
            new_row["aqi_lag24"] = latest["aqi_lag24"]
        else:
            new_row["aqi_lag24"] = df_copy.iloc[-(24)]["aqi_index"]
        # rolling windows — identical to train_models.py
        new_row["aqi_roll_3"]  = np.mean(predictions[-3:])
        new_row["aqi_roll_6"]  = np.mean(predictions[-6:])
        new_row["aqi_roll_24"] = np.mean(predictions[-24:]) if len(predictions) >= 24 else np.mean(predictions)
        # diff = change from previous predicted step
        new_row["aqi_diff"]   = pred - latest["aqi_index"]
        new_row["datetime"]   = latest["datetime"] + timedelta(hours=1)
        df_copy = pd.concat([df_copy, pd.DataFrame([new_row])], ignore_index=True)
    return predictions


# SHAP COMPUTATION
def compute_shap(model, X_train, X_test, model_name: str):
    try:
        if model_name in ("XGBoost", "LightGBM", "RandomForest"):
            explainer = shap.TreeExplainer(model)
        else:
            explainer = shap.LinearExplainer(model, X_train)
        shap_vals = explainer.shap_values(X_test)
        if isinstance(shap_vals, list):
            shap_vals = shap_vals[0]
        return shap_vals
    except Exception:
        return None


# vISUALIZATION HELPERS
DARK_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="IBM Plex Mono", color="#e8e8ec"),
    xaxis=dict(gridcolor="#2a2a30", linecolor="#2a2a30"),
    yaxis=dict(gridcolor="#2a2a30", linecolor="#2a2a30"),
    margin=dict(t=40, b=40, l=50, r=20),
)

def plot_historical(df_raw: pd.DataFrame):
    last = df_raw.tail(7*24)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=last["datetime"], y=last["aqi_index"],
        mode="lines", line=dict(color="#f5a623", width=1.5),
        fill="tozeroy", fillcolor="rgba(245,166,35,.08)",
        name="AQI"
    ))
    fig.update_layout(**DARK_LAYOUT, title="Last 7 Days — Hourly AQI", height=280)
    return fig

def plot_forecast_line(predictions: list, base_dt):
    hours = [base_dt + timedelta(hours=i+1) for i in range(72)]
    colors = [aqi_category(v)[1] for v in predictions]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hours, y=predictions,
        mode="lines+markers",
        line=dict(color="#4fb3ff", width=2),
        marker=dict(color=colors, size=5),
        name="Forecast AQI"
    ))
    # shading bands
    for lo, hi, col in [(0,50,"#3ecf8e"),(50,100,"#f5a623"),(100,150,"#ff8c42"),
                         (150,200,"#e84040"),(200,300,"#9b5de5"),(300,500,"#c70039")]:
        fig.add_hrect(y0=lo, y1=hi, fillcolor=col, opacity=.06, line_width=0)
    fig.update_layout(**DARK_LAYOUT, title="72-Hour AQI Forecast", height=320)
    return fig

def plot_model_comparison(results: dict):
    names = list(results.keys())
    maes  = [results[n]["mae"]  for n in names]
    rmses = [results[n]["rmse"] for n in names]
    r2s   = [results[n]["r2"]   for n in names]

    fig = make_subplots(rows=1, cols=3,
        subplot_titles=("MAE ↓", "RMSE ↓", "R² ↑"))
    kw = dict(marker_color="#f5a623", opacity=.85)
    fig.add_trace(go.Bar(x=names, y=maes,  **kw, name="MAE"),  1, 1)
    fig.add_trace(go.Bar(x=names, y=rmses, **kw, name="RMSE"), 1, 2)
    fig.add_trace(go.Bar(x=names, y=r2s,   **kw, name="R²"),   1, 3)
    fig.update_layout(**DARK_LAYOUT, height=300, showlegend=False,
                      title="Model Comparison")
    for ax in ["xaxis","xaxis2","xaxis3"]:
        fig.layout[ax].update(gridcolor="#2a2a30", linecolor="#2a2a30")
    for ax in ["yaxis","yaxis2","yaxis3"]:
        fig.layout[ax].update(gridcolor="#2a2a30", linecolor="#2a2a30")
    return fig

def plot_shap(shap_vals, X_test):
    mean_abs = np.abs(shap_vals).mean(axis=0)
    feat_imp = pd.Series(mean_abs, index=X_test.columns).sort_values()
    fig = go.Figure(go.Bar(
        x=feat_imp.values,
        y=feat_imp.index,
        orientation="h",
        marker=dict(
            color=feat_imp.values,
            colorscale=[[0,"#2a2a30"],[0.5,"#f5a623"],[1,"#e84040"]],
            showscale=False,
        )
    ))
    layout = {**DARK_LAYOUT, "margin": dict(l=130, r=20, t=40, b=40)}
    fig.update_layout(**layout, title="SHAP Feature Importance (mean |SHAP|)", height=380)
    return fig

def plot_actual_vs_pred(y_test, preds):
    fig = go.Figure()
    x = list(range(len(y_test)))
    fig.add_trace(go.Scatter(x=x, y=list(y_test),
        mode="lines", name="Actual", line=dict(color="#4fb3ff", width=1.5)))
    fig.add_trace(go.Scatter(x=x, y=list(preds),
        mode="lines", name="Predicted", line=dict(color="#f5a623", width=1.5, dash="dot")))
    fig.update_layout(**DARK_LAYOUT, title="Actual vs Predicted (Test Set)", height=300)
    return fig


# SIDEBAR
with st.sidebar:
    st.markdown("""
    <div style='font-family:Syne,sans-serif;font-size:1.4rem;font-weight:800;
                color:#f5a623;letter-spacing:.06em;margin-bottom:.2rem'>
        🌫️ AQI Dashboard
    </div>
    <div style='font-size:.7rem;color:#6b6b7a;letter-spacing:.1em;
                text-transform:uppercase;margin-bottom:1.5rem'>
        Air Quality - Matiari, sindh, Pakistan
    </div>
    """, unsafe_allow_html=True)

    mongo_uri = os.getenv("MONGODB_URI", "")

    st.markdown("---")
    st.markdown("<div style='font-size:.7rem;color:#6b6b7a;letter-spacing:.1em;text-transform:uppercase;margin-bottom:.7rem'>AQI Thresholds</div>", unsafe_allow_html=True)
    for cat, color, rng in [
        ("Good",        "#3ecf8e", "0 – 50"),
        ("Moderate",    "#f5a623", "51 – 100"),
        ("Unhealthy*",  "#ff8c42", "101 – 150"),
        ("Unhealthy",   "#e84040", "151 – 200"),
        ("Very Unhealthy","#9b5de5","201 – 300"),
        ("Hazardous",   "#c70039", "301 – 500"),
    ]:
        st.markdown(f"""
        <div style='display:flex;align-items:center;gap:.6rem;
                    margin-bottom:.3rem;font-size:.72rem'>
            <div style='width:10px;height:10px;border-radius:50%;
                        background:{color};flex-shrink:0'></div>
            <span style='color:{color};flex:1'>{cat}</span>
            <span style='color:#6b6b7a'>{rng}</span>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    run_btn = st.button("⚡ Train & Forecast", use_container_width=True)


# MAIN AREA — HEADER
st.markdown("""
<div style='font-family:Syne,sans-serif;font-size:2rem;font-weight:800;
            letter-spacing:.04em;margin-bottom:.2rem'>
    Air Quality Forecast Dashboard
</div>
<div style='font-size:.78rem;color:#6b6b7a;margin-bottom:2rem'>
    Real-time training · 72-hour ML forecast · SHAP explainability
</div>
""", unsafe_allow_html=True)

# MAIN LOGIC
if not run_btn:
    st.markdown("""
    <div style='border:1px dashed #2a2a30;border-radius:8px;padding:3rem;
                text-align:center;color:#6b6b7a;font-size:.85rem'>
        Enter your <span style='color:#f5a623'>MongoDB URI</span> in the sidebar
        and click <strong style='color:#f5a623'>⚡ Train & Forecast</strong> to begin.
    </div>
    """, unsafe_allow_html=True)
    st.stop()

if not mongo_uri:
    st.error("⚠️ Please provide a MongoDB URI in the sidebar.")
    st.stop()

# Loading
with st.spinner("Connecting to MongoDB & loading data…"):
    try:
        df_raw = load_data(mongo_uri)
    except Exception as e:
        st.error(f"❌ Failed to connect: {e}")
        st.stop()

st.success(f"✅ Loaded **{len(df_raw):,}** hourly records — from "
           f"`{df_raw['datetime'].min().date()}` to `{df_raw['datetime'].max().date()}`")

# feature engineering
with st.spinner("Engineering features…"):
    df_model, df_latest = engineer_features(df_raw)

# Training
with st.spinner("Training 5 models…"):
    results, best_name, X_train, X_test, y_test = train_models(df_model)

best = results[best_name]

# Forecasting
with st.spinner("Generating 72-hour forecast…"):
    preds_72 = forecast_72h(best["model"], df_latest)

# SHAP
with st.spinner("Computing SHAP values…"):
    shap_vals = compute_shap(best["model"], X_train, X_test, best_name)

# Daily aggregates
daily_aqi = [
    np.mean(preds_72[0:24]),
    np.mean(preds_72[24:48]),
    np.mean(preds_72[48:72]),
]
base_dt = df_latest["datetime"].iloc[-1]


# KPIs
st.markdown("<div class='sec-head'>Current Snapshot</div>", unsafe_allow_html=True)

current_aqi = float(df_raw["aqi_index"].iloc[-1])
cat_now, col_now = aqi_category(current_aqi)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Current AQI",  f"{current_aqi:.1f}")
c2.metric("Best Model",   best_name)
c3.metric("R²",           f"{best['r2']:.4f}")
c4.metric("MAE",          f"{best['mae']:.2f}")
c5.metric("RMSE",         f"{best['rmse']:.2f}")

# Gauge + Historical
g_col, h_col = st.columns([1, 2])
with g_col:
    st.plotly_chart(aqi_gauge(current_aqi), use_container_width=True)
with h_col:
    st.plotly_chart(plot_historical(df_raw), use_container_width=True)


# ALERTS
st.markdown("<div class='sec-head'>Active Alerts</div>", unsafe_allow_html=True)

alerts_triggered = False

if current_aqi > 300:
    st.markdown(f"""<div class='alert-box'>
        🚨 <strong>HAZARDOUS</strong> — Current AQI {current_aqi:.1f} exceeds 300.
        Avoid ALL outdoor activity. Wear N95 masks indoors if possible.
    </div>""", unsafe_allow_html=True)
    alerts_triggered = True
elif current_aqi > 200:
    st.markdown(f"""<div class='alert-box'>
        🔴 <strong>VERY UNHEALTHY</strong> — Current AQI {current_aqi:.1f}.
        Sensitive groups should remain indoors. Limit all outdoor exertion.
    </div>""", unsafe_allow_html=True)
    alerts_triggered = True
elif current_aqi > 150:
    st.markdown(f"""<div class='alert-box warn'>
        🟠 <strong>UNHEALTHY</strong> — Current AQI {current_aqi:.1f}.
        Everyone may experience health effects. Reduce prolonged outdoor activity.
    </div>""", unsafe_allow_html=True)
    alerts_triggered = True

for i, (day_label, day_val) in enumerate(zip(["Tomorrow","Day 2","Day 3"], daily_aqi)):
    if day_val > 200:
        st.markdown(f"""<div class='alert-box'>
            🚨 <strong>FORECAST ALERT — {day_label}</strong>: Predicted AQI {day_val:.1f} (Very Unhealthy / Hazardous).
            Plan indoor activities for this day.
        </div>""", unsafe_allow_html=True)
        alerts_triggered = True
    elif day_val > 150:
        st.markdown(f"""<div class='alert-box warn'>
            ⚠️ <strong>FORECAST WARNING — {day_label}</strong>: Predicted AQI {day_val:.1f} (Unhealthy).
            Sensitive groups should limit outdoor exposure.
        </div>""", unsafe_allow_html=True)
        alerts_triggered = True

if not alerts_triggered:
    st.markdown(f"""<div class='alert-box ok'>
        ✅ <strong>ALL CLEAR</strong> — Current AQI {current_aqi:.1f} ({cat_now}).
        No hazardous conditions forecast in the next 72 hours.
    </div>""", unsafe_allow_html=True)


# DAY FORECAST CARDS
st.markdown("<div class='sec-head'>3-Day AQI Forecast</div>", unsafe_allow_html=True)

day_labels = [
    (base_dt + timedelta(days=1)).strftime("%A, %b %d"),
    (base_dt + timedelta(days=2)).strftime("%A, %b %d"),
    (base_dt + timedelta(days=3)).strftime("%A, %b %d"),
]

cols = st.columns(3)
for col, label, val in zip(cols, day_labels, daily_aqi):
    cat, color = aqi_category(val)
    with col:
        st.markdown(f"""
        <div class='day-card'>
            <div class='day-label'>{label}</div>
            <div class='day-val' style='color:{color}'>{val:.1f}</div>
            <div class='day-cat' style='color:{color}'>{cat}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
st.plotly_chart(plot_forecast_line(preds_72, base_dt), use_container_width=True)


# MODEL COMPARISON
st.markdown("<div class='sec-head'>Model Benchmark</div>", unsafe_allow_html=True)

st.plotly_chart(plot_model_comparison(results), use_container_width=True)

with st.expander("📋 Detailed Metrics Table"):
    rows = []
    for name, r in results.items():
        rows.append({"Model": name, "MAE": round(r["mae"],3),
                     "RMSE": round(r["rmse"],3), "R²": round(r["r2"],4),
                     "Best": "🏆" if name == best_name else ""})
    st.dataframe(pd.DataFrame(rows).set_index("Model"), use_container_width=True)

# Actual vs Predicted
st.plotly_chart(plot_actual_vs_pred(y_test, best["preds"]), use_container_width=True)


# SHAP
st.markdown("<div class='sec-head'>SHAP Feature Importance</div>", unsafe_allow_html=True)

if shap_vals is not None:
    st.plotly_chart(plot_shap(shap_vals, X_test), use_container_width=True)

# RAW DATA EXPLORER
with st.expander("🗄️ Raw Data Explorer (last 200 rows)"):
    st.dataframe(df_raw.tail(200), use_container_width=True)

# FOOTER
st.markdown("""
<hr style='margin-top:2rem'>
<div style='text-align:center;font-size:.68rem;color:#6b6b7a;
            letter-spacing:.1em;padding:.5rem 0'>
    AQI INTEL · Powered by XGBoost / LightGBM · SHAP Explainability
</div>
""", unsafe_allow_html=True)