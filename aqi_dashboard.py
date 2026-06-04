import io
import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pymongo import MongoClient
from datetime import datetime, timedelta
import joblib
import shap
import warnings
warnings.filterwarnings("ignore")

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
.stApp { background: var(--bg); color: var(--text); }
section[data-testid="stSidebar"] {
    background: var(--surface);
    border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] * { color: var(--text) !important; }
div[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1rem 1.2rem;
}
div[data-testid="stMetricValue"] { color: var(--amber) !important; font-family: 'Syne', sans-serif; font-size: 2rem !important; }
div[data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: 0.7rem !important; letter-spacing: .12em; text-transform: uppercase; }
.stButton > button {
    background: var(--amber); color: #0d0d0f;
    font-family: 'Syne', sans-serif; font-weight: 700;
    font-size: 0.85rem; letter-spacing: .06em;
    border: none; border-radius: 4px;
    padding: .55rem 1.4rem; transition: opacity .15s;
}
.stButton > button:hover { opacity: .85; }
.sec-head {
    font-family: 'Syne', sans-serif; font-size: 1.1rem;
    font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
    color: var(--amber); border-bottom: 1px solid var(--border);
    padding-bottom: .4rem; margin-bottom: 1rem;
}
.alert-box {
    border-left: 4px solid var(--red);
    background: rgba(232,64,64,.10); border-radius: 4px;
    padding: .7rem 1rem; margin-bottom: .5rem;
    font-size: .82rem; font-family: 'IBM Plex Mono', monospace;
}
.alert-box.warn { border-color: #ffb347; background: rgba(255,179,71,.09); }
.alert-box.ok   { border-color: var(--green); background: rgba(62,207,142,.09); }
.day-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.2rem 1rem; text-align: center; }
.day-label { font-size:.7rem; color:var(--muted); letter-spacing:.12em; text-transform:uppercase; margin-bottom:.3rem; }
.day-val   { font-family:'Syne',sans-serif; font-size:2.4rem; font-weight:800; }
.day-cat   { font-size:.72rem; letter-spacing:.1em; margin-top:.3rem; text-transform:uppercase; }
.model-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 1rem 1.2rem; text-align: center;
    transition: border-color .2s;
}
.model-card.best { border-color: var(--amber); }
.model-card-name { font-family:'Syne',sans-serif; font-size:.85rem; font-weight:700;
                   letter-spacing:.06em; margin-bottom:.6rem; }
.model-card-metric { font-size:.7rem; color:var(--muted); letter-spacing:.08em; }
.model-card-val { font-size:1.1rem; font-weight:600; color:var(--text); }
details { border: 1px solid var(--border) !important; border-radius:6px !important; background:var(--surface) !important; }
summary { color: var(--text) !important; font-size:.82rem; }
.stDataFrame { border: 1px solid var(--border) !important; }
hr { border-color: var(--border) !important; }
.stSpinner > div > div { border-top-color: var(--amber) !important; }
</style>
""", unsafe_allow_html=True)


# AQI HELPERS
def aqi_category(val):
    v = float(val)
    if v <= 50:  return "Good",                 "#3ecf8e"
    if v <= 100: return "Moderate",             "#f5a623"
    if v <= 150: return "Unhealthy (Sensitive)", "#ff8c42"
    if v <= 200: return "Unhealthy",            "#e84040"
    if v <= 300: return "Very Unhealthy",       "#9b5de5"
    return             "Hazardous",             "#c70039"

def aqi_gauge(val):
    cat, color = aqi_category(val)
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=val,
        number={"font": {"size": 48, "color": color, "family": "Syne"}},
        gauge={
            "axis": {"range": [0, 500], "tickcolor": "#6b6b7a",
                     "tickfont": {"color": "#6b6b7a", "size": 10}},
            "bar": {"color": color}, "bgcolor": "#141417", "borderwidth": 0,
            "steps": [
                {"range": [0,   50],  "color": "rgba(62,207,142,.18)"},
                {"range": [50,  100], "color": "rgba(245,166,35,.18)"},
                {"range": [100, 150], "color": "rgba(255,140,66,.18)"},
                {"range": [150, 200], "color": "rgba(232,64,64,.18)"},
                {"range": [200, 300], "color": "rgba(155,93,229,.18)"},
                {"range": [300, 500], "color": "rgba(199,0,57,.18)"},
            ],
            "threshold": {"line": {"color": color, "width": 3}, "thickness": .75, "value": val},
        },
        title={"text": f"<span style='font-size:14px;color:#6b6b7a;letter-spacing:.12em'>{cat.upper()}</span>"}
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=30, b=0, l=20, r=20), height=240, font_family="IBM Plex Mono"
    )
    return fig


# MONGO HELPERS
# ✅ FIX: ttl=3600 forces cache to expire every hour on the deployed instance
#         so it always fetches fresh data from MongoDB instead of serving
#         stale results from a previous session.
@st.cache_data(show_spinner=False, ttl=3600)
def load_weather_data(uri: str) -> pd.DataFrame:
    client = MongoClient(uri)
    df = pd.DataFrame(list(client["aqi_db"]["weather_data"].find()))
    if "_id" in df.columns:
        df.drop(columns=["_id"], inplace=True)
    df["datetime"] = pd.to_datetime(df["datetime"])
    return df.sort_values("datetime").reset_index(drop=True)


# ✅ FIX: ttl=3600 ensures models are reloaded every hour, picking up any
#         newly retrained models instead of keeping the old binary in memory.
@st.cache_resource(show_spinner=False, ttl=3600)
def load_all_models_from_mongo(uri: str):
    client = MongoClient(uri)
    collection = client["aqi_db"]["ml_models"]

    # Step 1: fetch lightweight metadata only (no binary) to get names + best flag
    meta_docs = list(collection.find({}, {"model_name": 1, "is_best": 1, "r2": 1}))
    if not meta_docs:
        raise ValueError("No trained models found in MongoDB. Run train_models.py first.")

    # Step 2: determine best model before touching any binary
    best_doc = next((d for d in meta_docs if d.get("is_best")), None)
    if best_doc is None:
        best_doc = max(meta_docs, key=lambda d: d.get("r2", -999))
    best_name = best_doc["model_name"]

    # Step 3: load each model binary individually — one find_one() per model,
    # this avoids holding a long-lived cursor over large documents
    models_dict = {}
    for meta in meta_docs:
        name = meta["model_name"]
        doc  = collection.find_one({"model_name": name}, {"model_binary": 1})
        if doc and "model_binary" in doc:
            buf = io.BytesIO(bytes(doc["model_binary"]))
            models_dict[name] = joblib.load(buf)

    return models_dict, best_name


# ✅ FIX: ttl=3600 so metadata (MAE, RMSE, R²) reflects the latest training run.
@st.cache_data(show_spinner=False, ttl=3600)
def load_all_metadata(uri: str) -> dict:
    """
    Load metadata for all models.
    Returns { model_name: { mae, rmse, r2, is_best, trained_at } }
    """
    client = MongoClient(uri)
    docs = list(client["aqi_db"]["model_metadata"].find())
    return {d["model_name"]: d for d in docs}


# FEATURES
FEATURES = [
    "temp", "humidity", "pressure", "wind_speed", "wind_deg", "clouds",
    "aqi_lag1", "aqi_lag2", "aqi_lag3", "aqi_lag24",
    "aqi_roll_3", "aqi_roll_6", "aqi_roll_24", "aqi_diff",
]

# FEATURE ENGINEERING
def build_forecast_seed(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["aqi_diff"]    = df["aqi_index"].diff()
    df["aqi_lag1"]    = df["aqi_index"].shift(1)
    df["aqi_lag2"]    = df["aqi_index"].shift(2)
    df["aqi_lag3"]    = df["aqi_index"].shift(3)
    df["aqi_lag24"]   = df["aqi_index"].shift(24)
    df["aqi_roll_3"]  = df["aqi_index"].rolling(3).mean()
    df["aqi_roll_6"]  = df["aqi_index"].rolling(6).mean()
    df["aqi_roll_24"] = df["aqi_index"].rolling(24).mean()
    return df.dropna().reset_index(drop=True)


# 72-HOUR FORECAST
def forecast_72h(model, df_seed: pd.DataFrame) -> list:
    df_copy = df_seed.copy().reset_index(drop=True)
    predictions = []
    for i in range(72):
        latest = df_copy.iloc[-1]
        pred   = float(model.predict(pd.DataFrame([latest[FEATURES]]))[0])
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
                                  if len(predictions) >= 24 else np.mean(predictions))
        new_row["aqi_diff"]    = pred - latest["aqi_index"]
        new_row["datetime"]    = latest["datetime"] + timedelta(hours=1)
        df_copy = pd.concat([df_copy, pd.DataFrame([new_row])], ignore_index=True)
    return predictions

# ACTUAL VS PREDICTED AQI
def plot_actual_vs_predicted(df_raw, model, features):
    df = build_forecast_seed(df_raw).copy()

    # create supervised dataset same way as training
    df["target"] = df["aqi_index"].shift(-1)
    df = df.dropna()

    X = df[features]
    y = df["target"]

    split = int(len(df) * 0.8)
    X_test = X.iloc[split:]
    y_test = y.iloc[split:]

    preds = model.predict(X_test)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        y=y_test.values,
        mode="lines",
        name="Actual AQI",
        line=dict(color="#3ecf8e", width=2)
    ))

    fig.add_trace(go.Scatter(
        y=preds,
        mode="lines",
        name="Predicted AQI",
        line=dict(color="#f5a623", width=2)
    ))

    fig.update_layout(
        **DARK_LAYOUT,
        title="Actual vs Predicted AQI (Test Set)",
        height=350,
        xaxis_title="Time Step",
        yaxis_title="AQI"
    )

    return fig

# SHAP
def compute_shap(model, df_seed: pd.DataFrame, model_name: str):
    X_sample = df_seed[FEATURES].tail(200)
    try:
        if model_name in ("XGBoost", "LightGBM", "RandomForest"):
            explainer = shap.TreeExplainer(model)
        else:
            explainer = shap.LinearExplainer(model, X_sample)
        shap_vals = explainer.shap_values(X_sample)
        if isinstance(shap_vals, list):
            shap_vals = shap_vals[0]
        return shap_vals, X_sample
    except Exception as e:
        st.warning(f"⚠️ SHAP computation failed: {e}")
        return None, None


# DARK LAYOUT
DARK_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="IBM Plex Mono", color="#e8e8ec"),
    xaxis=dict(gridcolor="#2a2a30", linecolor="#2a2a30"),
    yaxis=dict(gridcolor="#2a2a30", linecolor="#2a2a30"),
    margin=dict(t=40, b=40, l=50, r=20),
)

# last 7 days' AQI plotting
def plot_historical(df_raw):
    last = df_raw.tail(7 * 24)
    fig  = go.Figure()
    fig.add_trace(go.Scatter(
        x=last["datetime"], y=last["aqi_index"],
        mode="lines", line=dict(color="#f5a623", width=1.5),
        fill="tozeroy", fillcolor="rgba(245,166,35,.08)", name="AQI"
    ))
    fig.update_layout(**DARK_LAYOUT, title="Last 7 Days — Hourly AQI", height=280)
    return fig


# 72 hours (3 days) forecasted AQI plotting
def plot_forecast_line(predictions, base_dt):
    hours  = [base_dt + timedelta(hours=i + 1) for i in range(72)]
    colors = [aqi_category(v)[1] for v in predictions]
    fig    = go.Figure()
    fig.add_trace(go.Scatter(
        x=hours, y=predictions, mode="lines+markers",
        line=dict(color="#4fb3ff", width=2),
        marker=dict(color=colors, size=5), name="Forecast AQI"
    ))
    for lo, hi, col in [(0,50,"#3ecf8e"),(50,100,"#f5a623"),(100,150,"#ff8c42"),
                         (150,200,"#e84040"),(200,300,"#9b5de5"),(300,500,"#c70039")]:
        fig.add_hrect(y0=lo, y1=hi, fillcolor=col, opacity=.06, line_width=0)
    fig.update_layout(**DARK_LAYOUT, title="72-Hour AQI Forecast", height=320)
    return fig


# model comparison
def plot_model_comparison(all_metadata: dict, best_name: str):
    names  = list(all_metadata.keys())
    maes   = [all_metadata[n].get("mae",  0) for n in names]
    rmses  = [all_metadata[n].get("rmse", 0) for n in names]
    r2s    = [all_metadata[n].get("r2",   0) for n in names]

    bar_colors = ["#f5a623" if n == best_name else "#4fb3ff" for n in names]

    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=("MAE ↓  (lower is better)",
                        "RMSE ↓  (lower is better)",
                        "R²  ↑  (higher is better)"),
    )
    for trace_data, col_idx in [(maes, 1), (rmses, 2), (r2s, 3)]:
        fig.add_trace(go.Bar(
            x=names, y=trace_data,
            marker_color=bar_colors, opacity=.9,
            showlegend=False,
        ), row=1, col=col_idx)

    fig.update_layout(
        **DARK_LAYOUT,
        height=340,
        title=f"Model Comparison  ·  🏆 Best: {best_name}",
    )
    for ax in ["xaxis", "xaxis2", "xaxis3"]:
        fig.layout[ax].update(gridcolor="#2a2a30", linecolor="#2a2a30",
                               tickfont=dict(size=10))
    for ax in ["yaxis", "yaxis2", "yaxis3"]:
        fig.layout[ax].update(gridcolor="#2a2a30", linecolor="#2a2a30")
    return fig


# Feature importance chart
def plot_shap(shap_vals, X_sample):
    mean_abs = np.abs(shap_vals).mean(axis=0)
    feat_imp = pd.Series(mean_abs, index=X_sample.columns).sort_values()
    fig = go.Figure(go.Bar(
        x=feat_imp.values, y=feat_imp.index, orientation="h",
        marker=dict(
            color=feat_imp.values,
            colorscale=[[0,"#2a2a30"],[0.5,"#f5a623"],[1,"#e84040"]],
            showscale=False,
        )
    ))
    layout = {**DARK_LAYOUT, "margin": dict(l=130, r=20, t=40, b=40)}
    fig.update_layout(**layout, title="SHAP Feature Importance (mean |SHAP|)", height=400)
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
        Air Quality · Matiari, Sindh, Pakistan
    </div>
    """, unsafe_allow_html=True)

    mongo_uri = os.getenv("MONGODB_URI", "")

    st.markdown("---")
    st.markdown("<div style='font-size:.7rem;color:#6b6b7a;letter-spacing:.1em;"
                "text-transform:uppercase;margin-bottom:.7rem'>AQI Thresholds</div>",
                unsafe_allow_html=True)
    for cat, color, rng in [
        ("Good",          "#3ecf8e", "0 – 50"),
        ("Moderate",      "#f5a623", "51 – 100"),
        ("Unhealthy*",    "#ff8c42", "101 – 150"),
        ("Unhealthy",     "#e84040", "151 – 200"),
        ("Very Unhealthy","#9b5de5", "201 – 300"),
        ("Hazardous",     "#c70039", "301 – 500"),
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
    run_btn = st.button("⚡ Load & Forecast", use_container_width=True)


# HEADER
st.markdown("""
<div style='font-family:Syne,sans-serif;font-size:2rem;font-weight:800;
            letter-spacing:.04em;margin-bottom:.2rem'>
    Air Quality Forecast Dashboard
</div>
<div style='font-size:.78rem;color:#6b6b7a;margin-bottom:2rem'>
    All models loaded · Best model forecasts · SHAP explainability
</div>
""", unsafe_allow_html=True)

if not run_btn:
    st.markdown("""
    <div style='border:1px dashed #2a2a30;border-radius:8px;padding:3rem;
                text-align:center;color:#6b6b7a;font-size:.85rem'>
        Click <strong style='color:#f5a623'>⚡ Load & Forecast</strong> to load all
        saved models from MongoDB and generate a fresh 72-hour forecast.
    </div>
    """, unsafe_allow_html=True)
    st.stop()

if not mongo_uri:
    st.error("⚠️  MONGODB_URI environment variable is not set.")
    st.stop()


# STEP 1 · WEATHER DATA
with st.spinner("Fetching weather data from MongoDB…"):
    try:
        df_raw = load_weather_data(mongo_uri)
    except Exception as e:
        st.error(f"❌ Failed to load weather data: {e}")
        st.stop()

st.success(f"✅ Loaded **{len(df_raw):,}** hourly records — "
           f"`{df_raw['datetime'].min().date()}` → `{df_raw['datetime'].max().date()}`")


# STEP 2 · LOAD ALL MODELS
with st.spinner("Loading all 5 models from MongoDB…"):
    try:
        models_dict, best_name = load_all_models_from_mongo(mongo_uri)
        all_metadata           = load_all_metadata(mongo_uri)
    except ValueError as e:
        st.error(f"❌ {e}")
        st.stop()
    except Exception as e:
        st.error(f"❌ Failed to load models: {e}")
        st.stop()

best_meta  = all_metadata.get(best_name, {})
best_model = models_dict[best_name]
trained_at = best_meta.get("trained_at", "—")

st.info(f"🤖 **{len(models_dict)} models** loaded · "
        f"🏆 Best: **{best_name}** · trained on `{trained_at}`")


# STEP 3 · FORECAST SEED
with st.spinner("Engineering features…"):
    df_seed = build_forecast_seed(df_raw)


# STEP 4 · 72-HOUR FORECAST (best model)
with st.spinner(f"Running 72-hour forecast with {best_name}…"):
    preds_72 = forecast_72h(best_model, df_seed)

base_dt   = df_seed["datetime"].iloc[-1]
daily_aqi = [
    np.mean(preds_72[0:24]),
    np.mean(preds_72[24:48]),
    np.mean(preds_72[48:72]),
]


# STEP 5 · SHAP
with st.spinner("Computing SHAP values…"):
    shap_vals, X_sample = compute_shap(best_model, df_seed, best_name)


# KPIs
st.markdown("<div class='sec-head'>Current Snapshot</div>", unsafe_allow_html=True)

current_aqi      = float(df_raw["aqi_index"].iloc[-1])
cat_now, col_now = aqi_category(current_aqi)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Current AQI", f"{current_aqi:.1f}")
c2.metric("Best Model",  best_name)
c3.metric("R²",          f"{best_meta.get('r2',  '—')}")
c4.metric("MAE",         f"{best_meta.get('mae', '—')}")
c5.metric("RMSE",        f"{best_meta.get('rmse','—')}")


# GAUGE + HISTORY
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
    </div>""", unsafe_allow_html=True); alerts_triggered = True
elif current_aqi > 200:
    st.markdown(f"""<div class='alert-box'>
        🔴 <strong>VERY UNHEALTHY</strong> — Current AQI {current_aqi:.1f}.
        Sensitive groups should remain indoors.
    </div>""", unsafe_allow_html=True); alerts_triggered = True
elif current_aqi > 150:
    st.markdown(f"""<div class='alert-box warn'>
        🟠 <strong>UNHEALTHY</strong> — Current AQI {current_aqi:.1f}.
        Reduce prolonged outdoor activity.
    </div>""", unsafe_allow_html=True); alerts_triggered = True

for day_label, day_val in zip(["Tomorrow", "Day 2", "Day 3"], daily_aqi):
    if day_val > 200:
        st.markdown(f"""<div class='alert-box'>
            🚨 <strong>FORECAST ALERT — {day_label}</strong>: Predicted AQI {day_val:.1f}
            (Very Unhealthy / Hazardous). Plan indoor activities.
        </div>""", unsafe_allow_html=True); alerts_triggered = True
    elif day_val > 150:
        st.markdown(f"""<div class='alert-box warn'>
            ⚠️ <strong>FORECAST WARNING — {day_label}</strong>: Predicted AQI {day_val:.1f}
            (Unhealthy). Sensitive groups should limit outdoor exposure.
        </div>""", unsafe_allow_html=True); alerts_triggered = True

if not alerts_triggered:
    st.markdown(f"""<div class='alert-box ok'>
        ✅ <strong>ALL CLEAR</strong> — Current AQI {current_aqi:.1f} ({cat_now}).
        No hazardous conditions forecast in the next 72 hours.
    </div>""", unsafe_allow_html=True)


# 3-DAY FORECAST CARDS
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
        </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
st.plotly_chart(plot_forecast_line(preds_72, base_dt), use_container_width=True)


# MODEL COMPARISON
st.markdown("<div class='sec-head'>Model Comparison</div>", unsafe_allow_html=True)

if all_metadata:
    st.plotly_chart(plot_model_comparison(all_metadata, best_name), use_container_width=True)

    card_cols = st.columns(len(all_metadata))
    for col, (name, meta) in zip(card_cols, all_metadata.items()):
        is_best    = name == best_name
        crown      = " 🏆" if is_best else ""
        card_cls   = "model-card best" if is_best else "model-card"
        name_color = "#f5a623" if is_best else "#e8e8ec"
        with col:
            st.markdown(f"""
            <div class='{card_cls}'>
                <div class='model-card-name' style='color:{name_color}'>{name}{crown}</div>
                <div class='model-card-metric'>R²</div>
                <div class='model-card-val'>{meta.get('r2','—')}</div>
                <div class='model-card-metric' style='margin-top:.4rem'>MAE</div>
                <div class='model-card-val'>{meta.get('mae','—')}</div>
                <div class='model-card-metric' style='margin-top:.4rem'>RMSE</div>
                <div class='model-card-val'>{meta.get('rmse','—')}</div>
            </div>""", unsafe_allow_html=True)


st.markdown("<br>", unsafe_allow_html=True)
# ACTUAL VS PREDICTED
st.markdown("<div class='sec-head'>Actual vs Predicted AQI</div>", unsafe_allow_html=True)

st.plotly_chart(
    plot_actual_vs_predicted(df_raw, best_model, FEATURES),
    use_container_width=True
)

# SHAP FEATURE IMPORTANCE
st.markdown("<div class='sec-head'>SHAP Feature Importance</div>", unsafe_allow_html=True)

if shap_vals is not None:
    st.plotly_chart(plot_shap(shap_vals, X_sample), use_container_width=True)


# RAW DATA EXPLORER
with st.expander("🗄️ Raw Data Explorer (last 200 rows)"):
    st.dataframe(df_raw.tail(200), use_container_width=True)


# FOOTER
st.markdown("""
<hr style='margin-top:2rem'>
<div style='text-align:center;font-size:.68rem;color:#6b6b7a;
            letter-spacing:.1em;padding:.5rem 0'>
    AQI INTEL · 5-Model Ensemble · SHAP Explainability · Matiari, Sindh
</div>
""", unsafe_allow_html=True)