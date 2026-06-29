import streamlit as st

BULL = "#00c853"
BEAR = "#ff1744"
NEUTRAL = "#ffd600"
CARD_BG = "#161b27"
BORDER = "#2a3142"
MUTED = "#94a3b8"
ACCENT = "#2962ff"

_CSS = """
<style>
/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #0d1117 !important;
    border-right: 1px solid #2a3142;
}
[data-testid="stSidebarContent"] { padding-top: 1rem; }

/* Section titles */
.section-title {
    font-size: 0.72rem;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin: 1.4rem 0 0.6rem 0;
    padding-bottom: 0.35rem;
    border-bottom: 1px solid #2a3142;
}

/* Range bar */
.range-wrap { margin: 0.5rem 0 0.25rem 0; }
.range-track {
    position: relative;
    height: 22px;
    border-radius: 6px;
    background: linear-gradient(to right, #ff1744 0%, #ff6d00 30%, #ffd600 50%, #69f0ae 70%, #00c853 100%);
    overflow: visible;
}
.range-fill {
    position: absolute;
    top: -4px;
    height: 30px;
    border-radius: 5px;
    border: 2px solid rgba(255,255,255,0.85);
    background: rgba(255,255,255,0.15);
    box-shadow: 0 0 10px rgba(255,255,255,0.25);
}
.range-zero {
    position: absolute;
    top: -5px;
    height: 32px;
    width: 2px;
    background: rgba(255,255,255,0.55);
    left: 50%;
    transform: translateX(-50%);
}
.range-labels {
    display: flex;
    justify-content: space-between;
    margin-top: 6px;
    font-family: 'Courier New', monospace;
    font-size: 0.82rem;
    color: #94a3b8;
}

/* Direction badge */
.badge {
    display: inline-block;
    padding: 3px 11px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.badge-bull  { background: rgba(0,200,83,0.14);  color: #00c853; border: 1px solid rgba(0,200,83,0.4); }
.badge-bear  { background: rgba(255,23,68,0.14);  color: #ff1744; border: 1px solid rgba(255,23,68,0.4); }
.badge-neutral { background: rgba(255,214,0,0.12); color: #ffd600; border: 1px solid rgba(255,214,0,0.4); }

/* Confidence badge */
.conf-badge {
    display: inline-block;
    padding: 3px 9px;
    border-radius: 999px;
    font-size: 0.73rem;
    font-weight: 600;
    font-family: 'Courier New', monospace;
}
.conf-high { background: rgba(0,200,83,0.12);  color: #00c853; }
.conf-mid  { background: rgba(255,214,0,0.12); color: #ffd600; }
.conf-low  { background: rgba(255,23,68,0.12);  color: #ff1744; }

/* Source chips */
.chip-row { display: flex; flex-wrap: wrap; gap: 5px; margin: 0.4rem 0; }
.chip {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 0.7rem;
    font-weight: 500;
    cursor: default;
}
.chip-ok   { background: rgba(0,200,83,0.1);  color: #00c853; border: 1px solid rgba(0,200,83,0.25); }
.chip-fail { background: rgba(255,23,68,0.1);  color: #ff5252; border: 1px solid rgba(255,23,68,0.25); }

/* Market status pills */
.mkt-pill {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 600;
}
.mkt-open   { background: rgba(0,200,83,0.14);  color: #00c853; border: 1px solid rgba(0,200,83,0.35); }
.mkt-closed { background: rgba(255,214,0,0.1);  color: #ffd600; border: 1px solid rgba(255,214,0,0.3); }

/* Monospace price display */
.metric-mono {
    font-family: 'Courier New', monospace;
    font-size: 1.35rem;
    font-weight: 700;
    color: #e2e8f0;
    line-height: 1.2;
}
.metric-label {
    font-size: 0.72rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 2px;
}

/* Card header row */
.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}
.card-tf-label {
    font-size: 0.82rem;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

/* Disclaimer card */
.disclaimer-card {
    background: #161b27;
    border: 1px solid #2a3142;
    border-left: 4px solid #2962ff;
    border-radius: 8px;
    padding: 1.6rem;
    max-width: 660px;
    margin: 2rem auto;
}
.disclaimer-title { font-size: 1.25rem; font-weight: 700; color: #e2e8f0; margin-bottom: 0.75rem; }
.disclaimer-body  { font-size: 0.88rem; color: #94a3b8; line-height: 1.75; }
.disclaimer-body strong { color: #e2e8f0; }

/* Setup warning chip in sidebar */
.setup-warn {
    background: rgba(255,23,68,0.1);
    border: 1px solid rgba(255,23,68,0.3);
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 0.78rem;
    color: #ff5252;
    margin: 0.5rem 0;
    text-align: center;
}

/* Nav cards on home page */
.nav-card {
    background: #161b27;
    border: 1px solid #2a3142;
    border-radius: 10px;
    padding: 1.25rem 1rem;
    text-align: center;
    height: 100%;
}
.nav-card-title { font-size: 1rem; font-weight: 600; color: #e2e8f0; margin-bottom: 0.3rem; }
.nav-card-desc  { font-size: 0.8rem; color: #94a3b8; line-height: 1.5; margin-bottom: 0.75rem; }

/* Price current display */
.price-display {
    font-family: 'Courier New', monospace;
    font-size: 2rem;
    font-weight: 700;
    color: #e2e8f0;
}
.price-label {
    font-size: 0.72rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

/* Not financial advice footer note */
.nfa-note {
    font-size: 0.7rem;
    color: #4a5568;
    text-align: center;
    margin-top: 0.5rem;
}
</style>
"""


def inject_styles():
    st.markdown(_CSS, unsafe_allow_html=True)


def range_bar_html(low: float, high: float) -> str:
    max_r = max(abs(low), abs(high), 3) * 1.6
    left = max(0.5, min((low + max_r) / (2 * max_r) * 100, 98.5))
    width = max(1.0, min((high - low) / (2 * max_r) * 100, 99 - left))
    return (
        '<div class="range-wrap">'
        '<div class="range-track">'
        f'<div class="range-fill" style="left:{left:.1f}%;width:{width:.1f}%;"></div>'
        '<div class="range-zero"></div>'
        '</div>'
        f'<div class="range-labels"><span>{low:+.1f}%</span><span>{high:+.1f}%</span></div>'
        '</div>'
    )


def conf_badge_html(confidence: int) -> str:
    cls = "conf-high" if confidence >= 65 else "conf-mid" if confidence >= 45 else "conf-low"
    return f'<span class="conf-badge {cls}">{confidence}% conf</span>'


def dir_badge_html(direction: str) -> str:
    ldir = direction.lower()
    cls = "badge-bull" if "bull" in ldir else "badge-bear" if "bear" in ldir else "badge-neutral"
    label = direction.replace("_", " ").title()
    return f'<span class="badge {cls}">{label}</span>'


def coverage_chips_html(coverage: dict) -> str:
    chips = []
    for src, info in coverage.items():
        if src == "overall_coverage_pct":
            continue
        if not isinstance(info, dict):
            continue
        if info.get("available"):
            chips.append(f'<span class="chip chip-ok">{src}</span>')
        else:
            reason = info.get("reason", "unavailable")
            chips.append(f'<span class="chip chip-fail" title="{reason}">{src}</span>')
    return f'<div class="chip-row">{"".join(chips)}</div>' if chips else ""


def mkt_pill_html(is_open: bool, status_text: str) -> str:
    cls = "mkt-open" if is_open else "mkt-closed"
    return f'<span class="mkt-pill {cls}">{status_text}</span>'
