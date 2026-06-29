import streamlit as st
from src import config, cost_tracker
from src.ui_styles import inject_styles

st.set_page_config(
    page_title="Stock Predictor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_styles()

conf = config.load_config()

# --- Disclaimer gate ---
if not conf.get("disclaimer_accepted", False):
    st.markdown("""
    <div class="disclaimer-card">
        <div class="disclaimer-title">Important Disclaimer</div>
        <div class="disclaimer-body">
            This tool provides AI-generated analysis for informational and educational purposes only.
            It is <strong>NOT financial advice</strong>. Do not make investment decisions based solely
            on this tool's output. Past predictions do not guarantee future results. Always consult
            a qualified financial advisor before making investment decisions.<br><br>
            By clicking below, you acknowledge and accept these terms.
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("I Understand and Accept", type="primary", use_container_width=True):
        conf["disclaimer_accepted"] = True
        config.save_config(conf)
        st.rerun()
    st.stop()

# --- Sidebar ---
with st.sidebar:
    st.markdown("### Stock Predictor")
    st.markdown("---")

    daily = cost_tracker.get_daily_spend()
    monthly = cost_tracker.get_monthly_spend()
    analyses = cost_tracker.get_total_analyses_today()
    budget = conf.get("settings", {}).get("monthly_budget_usd", 30.0)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f'<div class="metric-mono">${daily:.2f}</div>'
            f'<div class="metric-label">Today</div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div class="metric-mono">${monthly:.2f}</div>'
            f'<div class="metric-label">Month</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    budget_pct = min(monthly / budget, 1.0) if budget > 0 else 0.0
    st.progress(budget_pct, text=f"{analyses} analyses · ${budget:.0f}/mo budget")

    if not config.has_required_keys():
        st.markdown(
            '<div class="setup-warn">Setup incomplete — configure API keys</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.page_link("pages/4_Settings.py", label="Settings")
    st.caption("v1.0.0")

# --- Home page ---
if not config.has_required_keys():
    st.markdown("## Stock Predictor")
    st.markdown('<div class="section-title">Get Started</div>', unsafe_allow_html=True)
    st.markdown(
        "Configure your API keys to start analyzing stocks. "
        "You'll need keys from Anthropic, FRED, Finnhub, and FMP."
    )
    st.page_link("pages/4_Settings.py", label="Go to Settings", icon="⚙️")
    st.stop()

st.markdown("## Stock Predictor")
st.markdown(
    '<div class="section-title">Where do you want to go?</div>',
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)
with col1:
    with st.container(border=True):
        st.markdown('<div class="nav-card-title">Dashboard</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="nav-card-desc">Analyze a stock — percentage-range predictions, price chart, PDF report</div>',
            unsafe_allow_html=True,
        )
        st.page_link("pages/1_Dashboard.py", label="Open Dashboard")
with col2:
    with st.container(border=True):
        st.markdown('<div class="nav-card-title">Compare</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="nav-card-desc">Side-by-side comparison of up to 3 stocks across all timeframes</div>',
            unsafe_allow_html=True,
        )
        st.page_link("pages/2_Compare.py", label="Open Compare")
with col3:
    with st.container(border=True):
        st.markdown('<div class="nav-card-title">History</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="nav-card-desc">Track past prediction accuracy — hit rate by timeframe, resolved vs. pending</div>',
            unsafe_allow_html=True,
        )
        st.page_link("pages/3_History.py", label="Open History")
