import math
import requests
import pandas as pd
import yfinance as yf

from src import config
from src.db import cache
from src.rate_limiter import finnhub_limiter
from src.market_status import is_indian_ticker

_FMP_BASE = "https://financialmodelingprep.com/api/v3"
_FINNHUB_BASE = "https://finnhub.io/api/v1"


def _safe_float(val):
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _normalize_ticker(ticker: str) -> str:
    """For bare Indian tickers without exchange suffix, append .NS."""
    if is_indian_ticker(ticker) and "." not in ticker:
        return ticker + ".NS"
    return ticker


def get_live_quote(ticker: str) -> dict | None:
    ticker = _normalize_ticker(ticker)
    cache_key = f"price:live:{ticker}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # 1. yfinance fast_info
    try:
        t = yf.Ticker(ticker)
        fi = t.fast_info
        price = _safe_float(fi.last_price)
        if price:
            prev = _safe_float(fi.previous_close) or price
            change_pct = round((price - prev) / prev * 100, 2) if prev else 0.0
            result = {
                "price": price,
                "open": _safe_float(fi.open),
                "high": _safe_float(fi.day_high),
                "low": _safe_float(fi.day_low),
                "volume": int(fi.last_volume) if fi.last_volume else None,
                "change_pct": change_pct,
                "source": "yfinance",
            }
            cache.set(cache_key, result, ttl=60)
            return result
    except Exception:
        pass

    # 2a. Finnhub (US stocks only)
    if not is_indian_ticker(ticker):
        try:
            key = config.get_api_key("finnhub")
            if key:
                finnhub_limiter.wait()
                r = requests.get(
                    f"{_FINNHUB_BASE}/quote",
                    params={"symbol": ticker, "token": key},
                    timeout=10,
                )
                if r.ok:
                    d = r.json()
                    price = _safe_float(d.get("c"))
                    if price:
                        prev = _safe_float(d.get("pc")) or price
                        change_pct = round((price - prev) / prev * 100, 2) if prev else 0.0
                        result = {
                            "price": price,
                            "open": _safe_float(d.get("o")),
                            "high": _safe_float(d.get("h")),
                            "low": _safe_float(d.get("l")),
                            "volume": None,
                            "change_pct": change_pct,
                            "source": "finnhub",
                        }
                        cache.set(cache_key, result, ttl=60)
                        return result
        except Exception:
            pass

    # 2b. yahooquery (Indian + fallback)
    try:
        from yahooquery import Ticker as YQTicker
        yq = YQTicker(ticker)
        price_data = yq.price
        if isinstance(price_data, dict):
            d = price_data.get(ticker, {})
            price = _safe_float(d.get("regularMarketPrice"))
            if price:
                change_pct_raw = _safe_float(d.get("regularMarketChangePercent"))
                change_pct = round(change_pct_raw * 100, 2) if change_pct_raw else 0.0
                result = {
                    "price": price,
                    "open": _safe_float(d.get("regularMarketOpen")),
                    "high": _safe_float(d.get("regularMarketDayHigh")),
                    "low": _safe_float(d.get("regularMarketDayLow")),
                    "volume": int(d["regularMarketVolume"]) if d.get("regularMarketVolume") else None,
                    "change_pct": change_pct,
                    "source": "yahooquery",
                }
                cache.set(cache_key, result, ttl=60)
                return result
    except Exception:
        pass

    return None


def get_historical(ticker: str, period: str = "1y") -> dict | None:
    ticker = _normalize_ticker(ticker)
    cache_key = f"price:historical:{ticker}:{period}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # 1. yfinance Ticker.history
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        if hist is not None and not hist.empty:
            hist = hist.reset_index()
            data = []
            for _, row in hist.iterrows():
                date_val = row.get("Date", row.get("Datetime"))
                if hasattr(date_val, "strftime"):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    date_str = str(date_val)[:10]
                data.append({
                    "date": date_str,
                    "open": round(float(row["Open"]), 4),
                    "high": round(float(row["High"]), 4),
                    "low": round(float(row["Low"]), 4),
                    "close": round(float(row["Close"]), 4),
                    "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
                })
            if data:
                result = {"data": data, "source": "yfinance"}
                cache.set(cache_key, result, ttl=86400)
                return result
    except Exception:
        pass

    # 2a. yahooquery (India primary fallback)
    if is_indian_ticker(ticker):
        try:
            from yahooquery import Ticker as YQTicker
            yq = YQTicker(ticker)
            hist_df = yq.history(period=period, interval="1d")
            if isinstance(hist_df, pd.DataFrame) and not hist_df.empty:
                if isinstance(hist_df.index, pd.MultiIndex):
                    hist_df = hist_df.loc[ticker]
                hist_df = hist_df.reset_index()
                data = []
                for _, row in hist_df.iterrows():
                    date_val = row.get("date", row.get("Date"))
                    date_str = str(date_val)[:10] if date_val is not None else ""
                    data.append({
                        "date": date_str,
                        "open": round(float(row.get("open", row.get("Open", 0))), 4),
                        "high": round(float(row.get("high", row.get("High", 0))), 4),
                        "low": round(float(row.get("low", row.get("Low", 0))), 4),
                        "close": round(float(row.get("close", row.get("Close", 0))), 4),
                        "volume": int(row.get("volume", row.get("Volume", 0))),
                    })
                if data:
                    result = {"data": data, "source": "yahooquery"}
                    cache.set(cache_key, result, ttl=86400)
                    return result
        except Exception:
            pass

    # 2b. FMP (US historical fallback)
    if not is_indian_ticker(ticker):
        try:
            key = config.get_api_key("fmp")
            if key:
                r = requests.get(
                    f"{_FMP_BASE}/historical-price-full/{ticker}",
                    params={"limit": 365, "apikey": key},
                    timeout=15,
                )
                if r.ok:
                    raw = r.json().get("historical", [])
                    data = [
                        {
                            "date": p["date"],
                            "open": p["open"],
                            "high": p["high"],
                            "low": p["low"],
                            "close": p["close"],
                            "volume": p.get("volume", 0),
                        }
                        for p in raw
                        if p.get("close")
                    ]
                    if data:
                        data = sorted(data, key=lambda x: x["date"])
                        result = {"data": data, "source": "fmp"}
                        cache.set(cache_key, result, ttl=86400)
                        return result
        except Exception:
            pass

    return None


def get_info(ticker: str) -> dict | None:
    ticker = _normalize_ticker(ticker)
    cache_key = f"price:info:{ticker}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # 1. yfinance .info
    try:
        t = yf.Ticker(ticker)
        info = t.info
        name = info.get("longName") or info.get("shortName")
        if name:
            result = {
                "name": name,
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "description": (info.get("longBusinessSummary") or "")[:500],
                "country": info.get("country"),
                "employees": info.get("fullTimeEmployees"),
                "source": "yfinance",
            }
            cache.set(cache_key, result, ttl=86400)
            return result
    except Exception:
        pass

    # 2. yahooquery
    try:
        from yahooquery import Ticker as YQTicker
        yq = YQTicker(ticker)
        profile = yq.asset_profile
        if isinstance(profile, dict):
            d = profile.get(ticker, {})
            if isinstance(d, dict) and d.get("longBusinessSummary"):
                result = {
                    "name": ticker,
                    "sector": d.get("sector"),
                    "industry": d.get("industry"),
                    "description": (d.get("longBusinessSummary") or "")[:500],
                    "country": d.get("country"),
                    "employees": d.get("fullTimeEmployees"),
                    "source": "yahooquery",
                }
                cache.set(cache_key, result, ttl=86400)
                return result
    except Exception:
        pass

    return None
