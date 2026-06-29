import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from src import config
from src.analysis.aggregator import aggregate_stock_data, check_connectivity
from src.analysis.summarizer import summarize_data
from src.analysis.predictor import get_prediction
from src.market_status import get_status_text, is_market_open, get_exchange, get_1d_label
from src.db import cache
from src.ui_styles import (
    inject_styles,
    range_bar_html,
    conf_badge_html,
    dir_badge_html,
    coverage_chips_html,
    mkt_pill_html,
)

st.set_page_config(page_title="Dashboard — Stock Predictor", layout="wide")
inject_styles()

if not config.has_required_keys():
    st.warning("Please configure your API keys in Settings first.")
    st.page_link("pages/4_Settings.py", label="Go to Settings", icon="⚙️")
    st.stop()

# --- Page header + market status ---
ref_ticker = st.session_state.get("last_ticker", "AAPL")
try:
    _exchange = get_exchange(ref_ticker)
    _is_open = is_market_open(_exchange)
    _status_text = get_status_text(ref_ticker)
except Exception:
    _is_open = False
    _status_text = "Market status unavailable"

hdr_col, mkt_col = st.columns([4, 1])
with hdr_col:
    st.markdown("## Stock Analysis Dashboard")
with mkt_col:
    st.markdown(
        f'<div style="text-align:right;padding-top:0.9rem">{mkt_pill_html(_is_open, _status_text)}</div>',
        unsafe_allow_html=True,
    )

# --- Analyze form ---
with st.form("analyze_form", clear_on_submit=False):
    c1, c2 = st.columns([3, 2])
    ticker_raw = c1.text_input("Ticker Symbol", placeholder="AAPL, MSFT, RELIANCE.NS...")
    market = c2.selectbox("Market", ["US (NYSE/NASDAQ)", "India (NSE/BSE)"])
    submitted = st.form_submit_button("Analyze", type="primary", use_container_width=True)

if submitted and ticker_raw.strip():
    ticker = ticker_raw.strip().upper()
    if market == "India (NSE/BSE)" and "." not in ticker:
        ticker = ticker + ".NS"

    if not check_connectivity():
        cached_pred = cache.get(f"prediction:{ticker}")
        if cached_pred:
            st.warning("No internet connection — showing last cached prediction (may be stale)")
            st.session_state["last_prediction"] = cached_pred
            st.session_state["last_aggregated"] = None
            st.session_state["last_ticker"] = ticker
        else:
            st.error("No internet connection and no cached data available.")
    else:
        progress_container = st.status(f"Fetching data for {ticker}...", expanded=True)
        status_items = {}

        def progress_cb(source, status, detail=""):
            icon = {"loading": "⏳", "done": "✅", "failed": "❌", "skipped": "⏭️"}.get(status, "⏳")
            status_items[source] = f"{icon} {source} — {detail}" if detail else f"{icon} {source}"
            # Dict update only — no Streamlit calls from threads (causes delta path corruption)

        aggregated = aggregate_stock_data(ticker, progress_callback=progress_cb)

        # Worker threads can't safely write to st.status — flush collected statuses here from main thread
        with progress_container:
            for line in status_items.values():
                st.text(line)

        if not aggregated or not aggregated.get("price_data"):
            with progress_container:
                st.error(f"Could not fetch data for {ticker}. Check the ticker symbol.")
        else:
            with progress_container:
                st.text("⏳ Summarizing with Claude Haiku...")
            summarized = summarize_data(aggregated)

            with progress_container:
                st.text("⏳ Generating predictions with Claude Sonnet...")
            prediction = get_prediction(summarized)

            progress_container.update(label=f"Analysis complete for {ticker}", state="complete")

            if prediction and prediction.get("error"):
                st.error(prediction.get("message", "Prediction failed"))
            elif prediction:
                st.session_state["last_aggregated"] = aggregated
                st.session_state["last_prediction"] = prediction
                st.session_state["last_ticker"] = ticker


# --- Display results ---
prediction = st.session_state.get("last_prediction")
aggregated = st.session_state.get("last_aggregated")
last_ticker = st.session_state.get("last_ticker")

if not prediction or prediction.get("error") or not last_ticker:
    st.stop()

st.markdown("---")

currency = prediction.get("currency", "USD")
symbol = "₹" if currency == "INR" else "$"
current_price = prediction.get("current_price", 0)

# Predictions header row
pred_hdr, price_col = st.columns([3, 1])
with pred_hdr:
    st.markdown(f"### Predictions — {last_ticker}")
with price_col:
    st.markdown(
        f'<div style="text-align:right">'
        f'<div class="price-display">{symbol}{current_price:,.2f}</div>'
        f'<div class="price-label">Current Price</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# --- Prediction cards (2x2 grid) ---
timeframes = {
    "1d": get_1d_label(last_ticker),
    "1w": "1 Week",
    "1m": "1 Month",
    "1y": "1 Year",
}

cols = st.columns(2)
for i, (tf_key, tf_label) in enumerate(timeframes.items()):
    tf = prediction["predictions"].get(tf_key, {})
    low = tf.get("price_change_low_pct", 0)
    high = tf.get("price_change_high_pct", 0)
    confidence = tf.get("confidence_pct", 0)
    direction = tf.get("direction", "neutral")

    with cols[i % 2]:
        with st.container(border=True):
            # Header: timeframe label + confidence badge
            st.markdown(
                f'<div class="card-header">'
                f'<span class="card-tf-label">{tf_label}</span>'
                f'{conf_badge_html(confidence)}'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Range bar
            st.markdown(range_bar_html(low, high), unsafe_allow_html=True)

            # Direction badge
            st.markdown(dir_badge_html(direction), unsafe_allow_html=True)

            # Factors expander
            with st.expander("Factors & Sources"):
                bull = tf.get("bullish_factors", [])
                bear = tf.get("bearish_factors", [])
                cats = tf.get("key_catalysts", [])
                cites = tf.get("source_citations", [])
                if bull:
                    st.markdown("**Bullish**")
                    for f_item in bull[:3]:
                        st.markdown(f"- {f_item}")
                if bear:
                    st.markdown("**Bearish**")
                    for f_item in bear[:3]:
                        st.markdown(f"- {f_item}")
                if cats:
                    st.markdown("**Key Catalysts**")
                    for c_item in cats[:3]:
                        st.markdown(f"- {c_item}")
                if cites:
                    st.markdown("**Sources**")
                    for s in cites[:4]:
                        st.markdown(f"- _{s}_")

# Action buttons row
st.markdown("<br>", unsafe_allow_html=True)
act1, act2 = st.columns(2)
with act1:
    if st.button("Refresh All", use_container_width=True):
        cache.clear_for_ticker(last_ticker)
        st.session_state.pop("last_prediction", None)
        st.session_state.pop("last_aggregated", None)
        st.rerun()
with act2:
    if st.button("Generate PDF Report", type="primary", use_container_width=True):
        with st.spinner("Generating report..."):
            from src.reports.generator import generate_report
            pdf_bytes = generate_report(aggregated, prediction)
        if pdf_bytes:
            st.session_state["pdf_bytes"] = pdf_bytes
            st.session_state["pdf_ticker"] = last_ticker
        else:
            st.error("Failed to generate report")

if st.session_state.get("pdf_bytes") and st.session_state.get("pdf_ticker") == last_ticker:
    st.download_button(
        "Download PDF",
        data=st.session_state["pdf_bytes"],
        file_name=f"StockReport_{last_ticker}_{datetime.now().strftime('%Y%m%d')}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

st.markdown('<div class="nfa-note">Not financial advice — for informational purposes only</div>', unsafe_allow_html=True)

# --- Price chart ---
st.markdown("---")
st.markdown('<div class="section-title">Price Chart</div>', unsafe_allow_html=True)

if aggregated and aggregated.get("historical_data"):
    hist = aggregated["historical_data"]["data"]
    df = pd.DataFrame(hist)
    df["date"] = pd.to_datetime(df["date"])

    show_sma200 = st.checkbox("Show SMA 200", value=False)

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df["date"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="Price",
        increasing_line_color="#00c853", decreasing_line_color="#ff1744",
    ))

    sma20 = df["close"].rolling(20).mean()
    sma50 = df["close"].rolling(50).mean()
    fig.add_trace(go.Scatter(x=df["date"], y=sma20, name="SMA 20", line=dict(color="#2962ff", width=1.2)))
    fig.add_trace(go.Scatter(x=df["date"], y=sma50, name="SMA 50", line=dict(color="#ffd600", width=1.2)))

    if show_sma200:
        sma200 = df["close"].rolling(200).mean()
        fig.add_trace(go.Scatter(x=df["date"], y=sma200, name="SMA 200", line=dict(color="#ff6d00", width=1)))

    fig.update_layout(
        height=480,
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        xaxis=dict(gridcolor="#2a3142", title="Date"),
        yaxis=dict(gridcolor="#2a3142", title=f"Price ({symbol})"),
        xaxis_rangeslider_visible=False,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8")),
        font=dict(color="#e2e8f0"),
        margin=dict(t=20, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.caption("Historical price data unavailable")

# --- Executive summary + risk (2 columns) ---
st.markdown("---")
sum_col, risk_col = st.columns(2)
with sum_col:
    st.markdown('<div class="section-title">Executive Summary</div>', unsafe_allow_html=True)
    st.markdown(prediction.get("executive_summary", ""))
with risk_col:
    st.markdown('<div class="section-title">Risk Assessment</div>', unsafe_allow_html=True)
    st.markdown(prediction.get("risk_assessment", ""))

if prediction.get("data_coverage_note"):
    st.caption(prediction["data_coverage_note"])

# --- Data coverage chips ---
if aggregated and aggregated.get("data_coverage"):
    coverage = aggregated["data_coverage"]
    overall = coverage.get("overall_coverage_pct", 0)
    chips = coverage_chips_html(coverage)
    st.markdown(
        f'<div style="margin-top:0.5rem">'
        f'<span style="font-size:0.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em">Data Coverage {overall}%</span>'
        f'{chips}'
        f'</div>',
        unsafe_allow_html=True,
    )
