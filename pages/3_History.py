import streamlit as st
import pandas as pd
from datetime import datetime
import yfinance as yf

from src import config
from src.db import cache
from src.ui_styles import inject_styles

st.set_page_config(page_title="History — Stock Predictor", layout="wide")
inject_styles()

st.markdown("## Prediction History")
st.info(
    "Predictions are automatically resolved against actual prices when their timeframe expires. "
    "Accuracy updates each time you open this page."
)

TIMEFRAME_SECONDS = {
    "1d": 86400,
    "1w": 86400 * 7,
    "1m": 86400 * 30,
    "1y": 86400 * 365,
}


def resolve_pending_predictions():
    history = cache.get_prediction_history()
    now = datetime.now().timestamp()
    for pred in history:
        if pred["resolved_price"] is not None:
            continue
        elapsed = now - pred["timestamp"]
        required = TIMEFRAME_SECONDS.get(pred["timeframe"], 0)
        if elapsed < required:
            continue
        try:
            t = yf.Ticker(pred["ticker"])
            info = t.fast_info
            if info and hasattr(info, "last_price") and info.last_price:
                current = float(info.last_price)
                orig_price = pred["current_price_at_prediction"]
                if orig_price > 0:
                    actual_change_pct = ((current - orig_price) / orig_price) * 100
                    hit = pred["predicted_low_pct"] <= actual_change_pct <= pred["predicted_high_pct"]
                    cache.resolve_prediction(pred["id"], current, hit)
        except Exception:
            continue


resolve_pending_predictions()

ticker_filter = st.text_input(
    "Filter by ticker",
    placeholder="e.g. AAPL (leave blank to show all)",
    value="",
).strip().upper()

history = cache.get_prediction_history(ticker_filter if ticker_filter else None)

if not history:
    st.markdown(
        '<div style="background:#161b27;border:1px solid #2a3142;border-radius:8px;padding:2rem;text-align:center;margin-top:1.5rem">'
        '<div style="font-size:1rem;font-weight:600;color:#e2e8f0;margin-bottom:0.4rem">No predictions yet</div>'
        '<div style="font-size:0.85rem;color:#94a3b8">Run your first analysis on the Dashboard to start tracking accuracy.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.stop()

df = pd.DataFrame(history)
df["date"] = pd.to_datetime(df["timestamp"], unit="s").dt.strftime("%Y-%m-%d %H:%M")
df["predicted_range"] = df.apply(
    lambda r: f"{r['predicted_low_pct']:+.1f}% to {r['predicted_high_pct']:+.1f}%", axis=1
)
df["status"] = df.apply(
    lambda r: "Hit" if r["hit"] == 1 else "Miss" if r["hit"] == 0 else "Pending",
    axis=1,
)
df["actual_change"] = df.apply(
    lambda r: f"{((r['resolved_price'] - r['current_price_at_prediction']) / r['current_price_at_prediction'] * 100):+.1f}%"
    if r["resolved_price"] else "—",
    axis=1,
)

# --- Accuracy stats with progress bars ---
st.markdown('<div class="section-title">Accuracy by Timeframe</div>', unsafe_allow_html=True)

TF_LABELS = {"1d": "1 Day", "1w": "1 Week", "1m": "1 Month", "1y": "1 Year"}
acc_cols = st.columns(4)
for col, tf in zip(acc_cols, ["1d", "1w", "1m", "1y"]):
    tf_df = df[df["timeframe"] == tf]
    resolved = tf_df[tf_df["hit"].notna()]
    label = TF_LABELS[tf]
    with col:
        if len(resolved) > 0:
            hits = int((resolved["hit"] == 1).sum())
            total = len(resolved)
            pct = hits / total
            st.metric(label, f"{pct*100:.0f}%", help=f"{hits} hits out of {total} resolved")
            st.progress(pct)
            st.caption(f"{hits}/{total} resolved · {len(tf_df) - total} pending")
        else:
            st.metric(label, "—")
            st.progress(0.0)
            pending = len(tf_df)
            st.caption(f"0 resolved · {pending} pending")

# --- Prediction log table ---
st.markdown('<div class="section-title">Prediction Log</div>', unsafe_allow_html=True)

display = df[["date", "ticker", "timeframe", "predicted_range", "confidence", "status", "actual_change"]].rename(
    columns={
        "date": "Date",
        "ticker": "Ticker",
        "timeframe": "Timeframe",
        "predicted_range": "Predicted Range",
        "confidence": "Confidence %",
        "status": "Status",
        "actual_change": "Actual Change",
    }
)

st.dataframe(
    display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Date": st.column_config.TextColumn(width="medium"),
        "Ticker": st.column_config.TextColumn(width="small"),
        "Timeframe": st.column_config.TextColumn(width="small"),
        "Predicted Range": st.column_config.TextColumn(width="medium"),
        "Confidence %": st.column_config.NumberColumn(width="small", format="%d%%"),
        "Status": st.column_config.TextColumn(width="small"),
        "Actual Change": st.column_config.TextColumn(width="small"),
    },
)
