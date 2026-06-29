import requests
from datetime import datetime, timedelta

from src import config
from src.db import cache
from src.rate_limiter import finnhub_limiter

_FINNHUB_BASE = "https://finnhub.io/api/v1"

_POSITIVE = {
    "beat", "beats", "exceed", "exceeds", "exceeded", "surge", "surges", "surged",
    "rally", "rallies", "gain", "gains", "growth", "grows", "profit", "profits",
    "strong", "record", "rise", "rises", "rose", "positive", "outperform",
    "upgrade", "upgrades", "buy", "bullish", "boost", "jump", "jumps", "jumped",
    "higher", "above", "top", "win", "wins", "winning", "expand", "recovery",
    "breakout", "milestone", "innovation", "launches", "partnership", "deal",
}

_NEGATIVE = {
    "miss", "misses", "missed", "decline", "declines", "declined", "fall", "falls",
    "fell", "drop", "drops", "dropped", "loss", "losses", "weak", "weakens",
    "down", "cut", "cuts", "reduce", "reduces", "warning", "warn", "warns",
    "concern", "concerns", "bearish", "downgrade", "downgrades", "sell", "negative",
    "slump", "slumps", "tumble", "tumbles", "below", "disappoints", "disappointing",
    "layoff", "layoffs", "recall", "lawsuit", "investigation", "fraud", "probe",
    "fine", "penalty", "debt", "default", "bankruptcy", "halt", "suspend",
}


def _score_text(text: str) -> float:
    if not text:
        return 0.0
    words = [w.strip(".,!?\"'()[]") for w in text.lower().split()]
    pos = sum(1 for w in words if w in _POSITIVE)
    neg = sum(1 for w in words if w in _NEGATIVE)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 3)


def _fetch_finnhub_news(symbol: str, key: str, from_date: str, to_date: str) -> list:
    try:
        finnhub_limiter.wait()
        r = requests.get(
            f"{_FINNHUB_BASE}/company-news",
            params={"symbol": symbol, "from": from_date, "to": to_date, "token": key},
            timeout=12,
        )
        if r.ok:
            return r.json() if isinstance(r.json(), list) else []
    except Exception:
        pass
    return []


def _fetch_finnhub_market_news(key: str) -> list:
    try:
        finnhub_limiter.wait()
        r = requests.get(
            f"{_FINNHUB_BASE}/news",
            params={"category": "general", "token": key},
            timeout=12,
        )
        if r.ok:
            return r.json()[:20] if isinstance(r.json(), list) else []
    except Exception:
        pass
    return []


def get_company_news(ticker: str) -> dict | None:
    cache_key = f"news:{ticker}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    key = config.get_api_key("finnhub")
    if not key:
        return None

    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    # Strip Indian suffix for Finnhub (it only handles bare tickers for US, limited for India)
    search_ticker = ticker.replace(".NS", "").replace(".BO", "") if "." in ticker else ticker

    raw_articles = _fetch_finnhub_news(search_ticker, key, from_date, to_date)

    # Indian fallback: use market news if company news is empty
    if not raw_articles:
        raw_articles = _fetch_finnhub_market_news(key)

    if not raw_articles:
        return None

    articles = []
    for item in raw_articles[:25]:
        headline = item.get("headline", "")
        summary = item.get("summary", "")
        score = _score_text(headline + " " + summary)
        dt_unix = item.get("datetime", 0)
        try:
            dt_str = datetime.fromtimestamp(dt_unix).strftime("%Y-%m-%d %H:%M") if dt_unix else ""
        except (OSError, OverflowError):
            dt_str = ""
        articles.append({
            "headline": headline,
            "summary": summary[:200] if summary else "",
            "sentiment_score": score,
            "datetime": dt_str,
            "source_name": item.get("source", ""),
            "url": item.get("url", ""),
        })

    if not articles:
        return None

    avg_sentiment = round(sum(a["sentiment_score"] for a in articles) / len(articles), 3)
    result = {
        "articles": articles,
        "article_count": len(articles),
        "avg_sentiment": avg_sentiment,
        "source": "finnhub",
    }
    cache.set(cache_key, result, ttl=900)
    return result
