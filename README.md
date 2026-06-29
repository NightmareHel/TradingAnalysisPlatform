# Trading Analysis Platform

A stock analysis and prediction tool that collects financial data from 7 sources in parallel, compresses it through a two-pass LLM pipeline, and outputs percentage-range price predictions across 4 timeframes (1 day, 1 week, 1 month, 1 year) via a Streamlit dashboard with PDF export.

---

## Features

- Live price data with fallback chains (yfinance, Finnhub, yahooquery, FMP)
- Technical analysis: RSI, MACD, Bollinger Bands, OBV, SMA/EMA
- Fundamentals via Financial Modeling Prep (US) or yfinance (India)
- News sentiment scoring across 25 articles (Finnhub)
- Insider trading and congressional trade data
- SEC 10-K legal/risk filings (US stocks via edgartools)
- Macroeconomic indicators from FRED (GDP, CPI, Fed Funds, Unemployment, Yield Curve, VIX)
- Two-pass LLM pipeline: fast model summarizes, smart model predicts
- Supports both Anthropic Claude and Groq (free tier) as LLM providers
- Indian market support (NSE/BSE tickers with `.NS`/`.BO` suffix)
- SQLite caching to avoid redundant API calls
- Token usage and cost tracking
- PDF report export
- Bloomberg-style dark terminal UI

---

## Supported Markets

| Market | Example Tickers |
|--------|----------------|
| US (NYSE/NASDAQ) | AAPL, MSFT, NVDA, TSLA |
| India (NSE) | RELIANCE.NS, INFY.NS, TCS.NS |
| India (BSE) | RELIANCE.BO, INFY.BO |

---

## Prerequisites

- Python 3.11+
- API keys (see below)

---

## Required API Keys

| Key | Required | Free Tier | Get It |
|-----|----------|-----------|--------|
| LLM (Anthropic or Groq) | Yes | Groq: yes | [console.groq.com](https://console.groq.com) or [console.anthropic.com](https://console.anthropic.com) |
| Finnhub | Yes | Yes (60 req/min) | [finnhub.io](https://finnhub.io) |
| Financial Modeling Prep | Yes | Yes (250 req/day) | [financialmodelingprep.com](https://financialmodelingprep.com) |
| FRED (St. Louis Fed) | Optional | Yes | [fred.stlouisfed.org/docs/api](https://fred.stlouisfed.org/docs/api/api_key.html) |

Groq is recommended for testing — it is free, no credit card required. The app auto-detects the provider from the key prefix (`gsk_` = Groq, `sk-ant-` = Anthropic).

---

## Installation

```bash
git clone https://github.com/nightmarehel/TradingAnalysisPlatform.git
cd TradingAnalysisPlatform

python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

---

## Configuration

1. Launch the app (see below)
2. Navigate to the **Settings** page
3. Enter your API keys and click **Save API Keys**
4. Click **Test All** to verify each connection

Keys are stored in `config.yaml` at the project root (gitignored — never committed).

---

## Running the App

```bash
# Activate venv first
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS / Linux

streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

## Usage

1. Go to the **Dashboard** page
2. Enter a ticker symbol (e.g. `AAPL`, `RELIANCE.NS`)
3. Select the market
4. Click **Analyze**

The pipeline runs in parallel: all 7 data sources are fetched concurrently, then the LLM summarizes and predicts. A full analysis on a cold cache typically takes 10-20 seconds.

Results include:
- Percentage-range predictions per timeframe with direction and confidence
- Bullish/bearish factor breakdown per timeframe
- Candlestick chart with SMA overlays
- Executive summary and risk assessment
- Data source coverage chips

Use **Generate PDF Report** to export a formatted report.

---

## Caching

All API responses are cached in SQLite (`data/cache.db`) to avoid redundant calls and stay within free-tier rate limits:

| Source | TTL |
|--------|-----|
| Live price | 60 seconds |
| Historical / Fundamentals / Insider / Legal / Macro | 24 hours |
| News | 15 minutes |
| LLM summary | 30 minutes |
| LLM prediction | 1 hour |

Use **Refresh All** on the Dashboard to clear the cache for a ticker and force a fresh fetch.

---

## LLM Pipeline

```
Data Collection (parallel, 8 threads)
  price, technicals, fundamentals, news, insider, legal, macro

Pass 1 — Summarizer (fast model)
  Compresses raw JSON into per-section analytical bullets (~3KB output)
  Anthropic: claude-haiku-4-5-20251001
  Groq:      llama-3.3-70b-versatile

Pass 2 — Predictor (smart model)
  Structured JSON with 4 timeframe predictions + executive summary
  Anthropic: claude-sonnet-4-6 (JSON schema enforced)
  Groq:      llama-3.3-70b-versatile (JSON mode + schema in prompt)
```

Two passes reduce token cost by 50-70% compared to sending raw data directly to the prediction model.

---

## Notes

- **SEC filings** require `set_identity("name email")` from edgartools for EDGAR access. Without it, legal data is skipped gracefully.
- **Groq rate limits**: free tier is 6,000 tokens/minute. If you hit a limit mid-analysis, wait 60 seconds and retry — the summarizer result is cached and only the predictor call will be retried.
- **Indian stocks**: insider, congressional, and SEC data are not available. Coverage chips on the dashboard will reflect this. The LLM widens prediction ranges accordingly.
- This tool is for informational and educational purposes only. It is not financial advice.
