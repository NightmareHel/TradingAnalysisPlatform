import streamlit as st
import pandas as pd
from src import config
from src.analysis.aggregator import aggregate_stock_data, check_connectivity
from src.analysis.summarizer import summarize_data
from src.analysis.predictor import get_prediction
from src.db import cache
from src.ui_styles import inject_styles, dir_badge_html, conf_badge_html

st.set_page_config(page_title="Compare — Stock Predictor", layout="wide")
inject_styles()

st.markdown("## Compare Stocks")
st.caption("Percentage changes are comparable across currencies. Absolute prices shown in native currency.")

if not config.has_required_keys():
    st.warning("Please configure your API keys in Settings first.")
    st.stop()

# --- Ticker inputs ---
c1, c2, c3 = st.columns(3)
ticker1 = c1.text_input("Ticker 1 (required)", placeholder="AAPL").strip().upper()
ticker2 = c2.text_input("Ticker 2 (required)", placeholder="MSFT").strip().upper()
ticker3 = c3.text_input("Ticker 3 (optional)", placeholder="GOOGL").strip().upper()

tickers = [t for t in [ticker1, ticker2, ticker3] if t]

if len(tickers) < 2:
    st.caption("Enter at least 2 tickers to compare.")

compare_btn = st.button("Compare", type="primary", disabled=len(tickers) < 2, use_container_width=True)

if compare_btn and len(tickers) >= 2:
    if not check_connectivity():
        st.error("No internet connection")
        st.stop()

    predictions = {}
    cache_used = {}
    for t in tickers:
        with st.spinner(f"Analyzing {t}..."):
            cached_pred = cache.get(f"prediction:{t}")
            if cached_pred and not cached_pred.get("error"):
                predictions[t] = cached_pred
                cache_used[t] = True
            else:
                agg = aggregate_stock_data(t)
                if not agg or not agg.get("price_data"):
                    st.error(f"Could not fetch data for {t}")
                    continue
                summ = summarize_data(agg)
                pred = get_prediction(summ)
                if pred and not pred.get("error"):
                    predictions[t] = pred
                    cache_used[t] = False
                else:
                    err = pred.get("message", "Unknown error") if pred else "No response"
                    st.error(f"Prediction failed for {t}: {err}")

    if len(predictions) >= 2:
        st.session_state["compare_predictions"] = predictions
        st.session_state["compare_cache_used"] = cache_used

compare_preds = st.session_state.get("compare_predictions", {})
cache_used = st.session_state.get("compare_cache_used", {})

if not compare_preds or len(compare_preds) < 2:
    st.stop()

st.markdown("---")
tickers_list = list(compare_preds.keys())

# --- Ticker header row ---
hdr_cols = st.columns([1] + [2] * len(tickers_list))
hdr_cols[0].markdown('<div class="section-title">Timeframe</div>', unsafe_allow_html=True)
for i, t in enumerate(tickers_list):
    pred = compare_preds[t]
    currency = pred.get("currency", "USD")
    sym = "₹" if currency == "INR" else "$"
    price = pred.get("current_price", 0)
    cached_label = " · cached" if cache_used.get(t) else ""
    hdr_cols[i + 1].markdown(
        f'<div class="section-title">{t}</div>'
        f'<div style="font-family:\'Courier New\',monospace;font-size:1.1rem;color:#e2e8f0">{sym}{price:,.2f}</div>'
        f'<div style="font-size:0.7rem;color:#4a5568">{currency}{cached_label}</div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# --- Per-timeframe comparison ---
TIMEFRAMES = [("1d", "1 Day"), ("1w", "1 Week"), ("1m", "1 Month"), ("1y", "1 Year")]

for tf_key, tf_label in TIMEFRAMES:
    row_cols = st.columns([1] + [2] * len(tickers_list))
    row_cols[0].markdown(
        f'<div style="padding-top:0.6rem;font-weight:600;color:#94a3b8;font-size:0.85rem;text-transform:uppercase;letter-spacing:0.08em">{tf_label}</div>',
        unsafe_allow_html=True,
    )

    # Find best midpoint for highlighting
    midpoints = {}
    for t in tickers_list:
        tf = compare_preds[t].get("predictions", {}).get(tf_key, {})
        low = tf.get("price_change_low_pct", 0)
        high = tf.get("price_change_high_pct", 0)
        midpoints[t] = (low + high) / 2
    best_ticker = max(midpoints, key=midpoints.get)

    for i, t in enumerate(tickers_list):
        pred = compare_preds[t]
        tf = pred.get("predictions", {}).get(tf_key, {})
        low = tf.get("price_change_low_pct", 0)
        high = tf.get("price_change_high_pct", 0)
        confidence = tf.get("confidence_pct", 0)
        direction = tf.get("direction", "neutral")

        is_best = t == best_ticker
        border_style = "border: 1px solid #2962ff;" if is_best else ""

        with row_cols[i + 1]:
            with st.container(border=True):
                range_str = f"{low:+.1f}% to {high:+.1f}%"
                st.markdown(
                    f'<div style="font-family:\'Courier New\',monospace;font-size:0.95rem;color:#e2e8f0;margin-bottom:4px">{range_str}</div>'
                    f'{dir_badge_html(direction)}&nbsp;{conf_badge_html(confidence)}',
                    unsafe_allow_html=True,
                )
                if is_best:
                    st.markdown('<div style="font-size:0.68rem;color:#2962ff;margin-top:4px">Best midpoint this period</div>', unsafe_allow_html=True)

    st.markdown("---")
