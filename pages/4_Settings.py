import streamlit as st
from src import config, cost_tracker
from src.db import cache
from src.ui_styles import inject_styles

st.set_page_config(page_title="Settings — Stock Predictor", layout="wide")
inject_styles()

st.markdown("## Settings")

conf = config.load_config()
keys = conf.get("api_keys", {})
settings = conf.get("settings", {})

tab_keys, tab_prefs, tab_cost = st.tabs(["API Keys", "Preferences", "Cost & Cache"])

# ─── Tab 1: API Keys ──────────────────────────────────────────────────────────
with tab_keys:
    st.markdown('<div class="section-title">API Keys</div>', unsafe_allow_html=True)
    st.caption("Keys are stored locally in your config file. Test each one before running analyses.")

    KEY_DEFS = [
        ("anthropic", "LLM Key", "Anthropic or Groq — AI analysis engine", config.test_llm_connection, "console.groq.com"),
        ("fred",      "FRED",    "Required — macro indicators",             config.test_fred_connection, "fred.stlouisfed.org/docs/api/fred"),
        ("finnhub",   "Finnhub", "Required — news & sentiment",             config.test_finnhub_connection, "finnhub.io"),
        ("fmp",       "FMP",     "Required — company fundamentals",          config.test_fmp_connection, "financialmodelingprep.com"),
    ]

    if "key_test_results" not in st.session_state:
        st.session_state["key_test_results"] = {}

    # 2-column grid
    row1 = st.columns(2)
    row2 = st.columns(2)
    grid_cols = [row1[0], row1[1], row2[0], row2[1]]

    new_keys = {}
    for col, (key_id, label, desc, test_fn, signup_host) in zip(grid_cols, KEY_DEFS):
        with col:
            with st.container(border=True):
                # Status indicator
                result = st.session_state["key_test_results"].get(key_id)
                if result is True:
                    status_html = '<span style="color:#00c853;font-size:0.75rem">Connected</span>'
                elif result is False:
                    status_html = '<span style="color:#ff1744;font-size:0.75rem">Failed</span>'
                elif keys.get(key_id):
                    status_html = '<span style="color:#ffd600;font-size:0.75rem">Saved — not tested</span>'
                else:
                    status_html = '<span style="color:#4a5568;font-size:0.75rem">Not configured</span>'

                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">'
                    f'<span style="font-weight:600;color:#e2e8f0">{label}</span>'
                    f'{status_html}'
                    f'</div>'
                    f'<div style="font-size:0.75rem;color:#94a3b8;margin-bottom:8px">{desc}</div>',
                    unsafe_allow_html=True,
                )

                val = st.text_input(
                    f"{label} key",
                    value=keys.get(key_id, ""),
                    type="password",
                    label_visibility="collapsed",
                    key=f"key_input_{key_id}",
                )
                new_keys[key_id] = val

                btn_col, link_col = st.columns([1, 2])
                with btn_col:
                    if st.button("Test", key=f"test_{key_id}", use_container_width=True):
                        if val:
                            ok, msg = test_fn(val)
                            st.session_state["key_test_results"][key_id] = ok
                            if ok:
                                st.success(msg)
                            else:
                                st.error(msg)
                        else:
                            st.warning("Enter a key first")
                with link_col:
                    st.caption(f"[Sign up]({signup_host})")

    st.markdown("<br>", unsafe_allow_html=True)

    ta_col, save_col = st.columns(2)
    with ta_col:
        if st.button("Test All", use_container_width=True):
            results = {}
            for key_id, label, _, test_fn, _ in KEY_DEFS:
                val = new_keys.get(key_id, "")
                if val:
                    ok, msg = test_fn(val)
                    results[key_id] = (ok, msg)
                    st.session_state["key_test_results"][key_id] = ok
                else:
                    results[key_id] = (False, "No key entered")
                    st.session_state["key_test_results"][key_id] = False
            for key_id, label, _, _, _ in KEY_DEFS:
                ok, msg = results[key_id]
                if ok:
                    st.success(f"{label}: {msg}")
                else:
                    st.error(f"{label}: {msg}")
    with save_col:
        if st.button("Save API Keys", type="primary", use_container_width=True):
            conf["api_keys"] = new_keys
            config.save_config(conf)
            st.success("API keys saved")
            st.rerun()

# ─── Tab 2: Preferences ───────────────────────────────────────────────────────
with tab_prefs:
    st.markdown('<div class="section-title">Prediction Model</div>', unsafe_allow_html=True)

    MODEL_OPTIONS = {
        "claude-sonnet-4-6":        ("Claude Sonnet 4.6", "Best quality", "~$0.07/analysis"),
        "claude-haiku-4-5-20251001": ("Claude Haiku 4.5", "Faster & cheaper", "~$0.02/analysis"),
    }
    current_model = settings.get("claude_model", "claude-sonnet-4-6")

    selected_model = st.radio(
        "Select model",
        options=list(MODEL_OPTIONS.keys()),
        format_func=lambda x: MODEL_OPTIONS[x][0],
        index=list(MODEL_OPTIONS.keys()).index(current_model) if current_model in MODEL_OPTIONS else 0,
        label_visibility="collapsed",
    )
    name, quality, cost_est = MODEL_OPTIONS[selected_model]
    st.caption(f"{quality} · {cost_est}")

    st.markdown('<div class="section-title">Monthly Budget</div>', unsafe_allow_html=True)

    budget = st.slider(
        "Monthly budget (USD)",
        min_value=5,
        max_value=200,
        value=int(settings.get("monthly_budget_usd", 30)),
        step=5,
        label_visibility="collapsed",
    )
    analyses_per_budget = budget / (0.07 if "sonnet" in selected_model else 0.02)
    st.caption(f"${budget}/mo · ~{analyses_per_budget:.0f} analyses at current model cost")

    if st.button("Save Preferences", type="primary", use_container_width=True):
        conf.setdefault("settings", {})
        conf["settings"]["claude_model"] = selected_model
        conf["settings"]["monthly_budget_usd"] = float(budget)
        config.save_config(conf)
        st.success("Preferences saved")
        st.rerun()

# ─── Tab 3: Cost & Cache ──────────────────────────────────────────────────────
with tab_cost:
    st.markdown('<div class="section-title">API Usage</div>', unsafe_allow_html=True)

    daily = cost_tracker.get_daily_spend()
    monthly = cost_tracker.get_monthly_spend()
    analyses = cost_tracker.get_total_analyses_today()
    budget_val = float(conf.get("settings", {}).get("monthly_budget_usd", 30.0))

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(
            f'<div class="metric-mono">${daily:.4f}</div><div class="metric-label">Today</div>',
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f'<div class="metric-mono">${monthly:.4f}</div><div class="metric-label">This Month</div>',
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f'<div class="metric-mono">{analyses}</div><div class="metric-label">Analyses Today</div>',
            unsafe_allow_html=True,
        )

    budget_pct = min(monthly / budget_val, 1.0) if budget_val > 0 else 0.0
    st.markdown("<br>", unsafe_allow_html=True)
    st.progress(budget_pct, text=f"Monthly budget: ${monthly:.2f} / ${budget_val:.0f}")

    st.markdown('<div class="section-title">Cache</div>', unsafe_allow_html=True)

    cache_size = cache.get_size_mb()
    cache_pct = min(cache_size / 100, 1.0)
    st.progress(cache_pct, text=f"Cache size: {cache_size:.2f} MB")

    cc1, cc2 = st.columns(2)
    with cc1:
        if st.button("Clear Expired", use_container_width=True):
            cache.clear_expired()
            st.success("Expired entries removed")
            st.rerun()
    with cc2:
        if st.button("Clear All Cache", use_container_width=True, type="secondary"):
            st.session_state["confirm_clear_all"] = True

    if st.session_state.get("confirm_clear_all"):
        st.warning("This will delete all cached data and prediction history. Are you sure?")
        conf_col, cancel_col = st.columns(2)
        with conf_col:
            if st.button("Yes, clear everything", type="primary", use_container_width=True):
                cache.clear_all()
                st.session_state["confirm_clear_all"] = False
                st.success("All cache cleared")
                st.rerun()
        with cancel_col:
            if st.button("Cancel", use_container_width=True):
                st.session_state["confirm_clear_all"] = False
                st.rerun()
