import requests
import yfinance as yf
from datetime import datetime, timedelta

from src import config
from src.db import cache
from src.rate_limiter import finnhub_limiter
from src.market_status import is_indian_ticker

_FINNHUB_BASE = "https://finnhub.io/api/v1"


def get_insider_trades(ticker: str) -> dict | None:
    if is_indian_ticker(ticker):
        return {"available": False, "reason": "Not available for non-US stocks", "trades": []}

    cache_key = f"insider:trades:{ticker}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        t = yf.Ticker(ticker)
        df = t.insider_transactions

        if df is None or (hasattr(df, "empty") and df.empty):
            result = {"available": True, "trades": [], "net_sentiment": "neutral", "source": "yfinance"}
            cache.set(cache_key, result, ttl=86400)
            return result

        trades = []
        buy_shares = 0
        sell_shares = 0

        for _, row in df.iterrows():
            shares = row.get("Shares", row.get("shares", 0))
            text = str(row.get("Text", row.get("text", row.get("Transaction", "")))).lower()
            transaction_type = "Buy" if any(w in text for w in ("purchase", "buy", "bought", "acquisition")) else "Sale"

            try:
                date_val = row.get("Start Date", row.get("Date", row.get("date")))
                date_str = date_val.strftime("%Y-%m-%d") if hasattr(date_val, "strftime") else str(date_val)[:10]
            except Exception:
                date_str = ""

            try:
                shares_int = int(float(shares)) if shares == shares else 0
            except (TypeError, ValueError):
                shares_int = 0

            trades.append({
                "date": date_str,
                "filer_name": str(row.get("Insider", row.get("insider", "Unknown"))),
                "position": str(row.get("Position", row.get("position", ""))),
                "transaction_type": transaction_type,
                "shares": shares_int,
                "value": None,
            })

            if transaction_type == "Buy":
                buy_shares += shares_int
            else:
                sell_shares += shares_int

        net_sentiment = "neutral"
        if buy_shares > sell_shares * 1.2:
            net_sentiment = "positive"
        elif sell_shares > buy_shares * 1.2:
            net_sentiment = "negative"

        result = {
            "available": True,
            "trades": trades[:15],
            "net_sentiment": net_sentiment,
            "buy_shares_total": buy_shares,
            "sell_shares_total": sell_shares,
            "source": "yfinance",
        }
        cache.set(cache_key, result, ttl=86400)
        return result

    except Exception:
        return None


def get_congressional_trades(ticker: str) -> dict | None:
    if is_indian_ticker(ticker):
        return {"available": False, "reason": "Not available for non-US stocks", "trades": []}

    cache_key = f"insider:congressional:{ticker}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    key = config.get_api_key("finnhub")
    if not key:
        return {"available": False, "reason": "Finnhub API key not configured", "trades": []}

    try:
        from_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")

        finnhub_limiter.wait()
        r = requests.get(
            f"{_FINNHUB_BASE}/stock/congressional-trading",
            params={"symbol": ticker, "from": from_date, "to": to_date, "token": key},
            timeout=12,
        )

        if not r.ok:
            result = {"available": True, "trades": [], "source": "finnhub"}
            cache.set(cache_key, result, ttl=86400)
            return result

        raw = r.json()
        trades_raw = raw.get("data", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])

        trades = []
        for item in trades_raw[:20]:
            trades.append({
                "date": item.get("transactionDate", ""),
                "representative": item.get("name", "Unknown"),
                "transaction_type": item.get("transactionType", ""),
                "amount_range": item.get("amount", ""),
                "ticker": item.get("symbol", ticker),
            })

        result = {"available": True, "trades": trades, "source": "finnhub"}
        cache.set(cache_key, result, ttl=86400)
        return result

    except Exception:
        return None
