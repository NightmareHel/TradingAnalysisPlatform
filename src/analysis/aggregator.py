import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

from src.data import price, fundamentals, news, insider, legal, macro, technical
from src.market_status import get_exchange, get_currency, get_status_text, is_market_open, get_1d_label


def _log(msg: str):
    print(f"[PIPELINE] {msg}", flush=True)


def check_connectivity() -> bool:
    try:
        requests.get("https://www.google.com", timeout=5)
        return True
    except Exception:
        return False


def aggregate_stock_data(ticker: str, progress_callback=None) -> dict | None:
    _log(f"aggregate_stock_data START — {ticker}")

    def _report(source: str, status: str, detail: str = ""):
        _log(f"  {source} [{status}] {detail}")
        if progress_callback:
            try:
                progress_callback(source, status, detail)
            except Exception:
                pass

    exchange = get_exchange(ticker)
    currency = get_currency(ticker)
    market_open = is_market_open(exchange)

    result = {
        "ticker": ticker,
        "exchange": exchange,
        "currency": currency,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "market_status": {
            "is_open": market_open,
            "status_text": get_status_text(ticker),
            "day_label": get_1d_label(ticker),
        },
        "price_data": None,
        "historical_data": None,
        "company_info": None,
        "technical_indicators": None,
        "fundamentals": None,
        "news_sentiment": None,
        "insider_activity": None,
        "congressional_trades": None,
        "legal_regulatory": None,
        "macro_environment": None,
        "data_coverage": {},
        "fetch_times": {},
    }

    tasks = {
        "Price data": lambda: _fetch_price(ticker, result, _report),
        "Company info": lambda: _fetch_info(ticker, result, _report),
        "Historical data": lambda: _fetch_historical(ticker, result, _report),
        "Fundamentals": lambda: _fetch_fundamentals(ticker, result, _report),
        "News & sentiment": lambda: _fetch_news(ticker, result, _report),
        "Insider trading": lambda: _fetch_insider(ticker, result, _report),
        "SEC filings": lambda: _fetch_legal(ticker, result, _report),
        "Macro indicators": lambda: _fetch_macro(result, _report),
    }

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
            except Exception as exc:
                _log(f"  {name} THREAD EXCEPTION: {type(exc).__name__}: {exc}")

    if result["historical_data"]:
        _report("Technical indicators", "loading")
        start = time.time()
        result["technical_indicators"] = technical.calculate_all(result["historical_data"])
        elapsed = round(time.time() - start, 1)
        if result["technical_indicators"]:
            _report("Technical indicators", "done", f"{elapsed}s")
            result["data_coverage"]["technical"] = {"available": True, "source": "calculated", "fetched_at": datetime.utcnow().isoformat()}
        else:
            _report("Technical indicators", "failed", "Insufficient data")
            result["data_coverage"]["technical"] = {"available": False, "reason": "Insufficient historical data"}
    else:
        result["data_coverage"]["technical"] = {"available": False, "reason": "No historical data available"}

    available = sum(1 for v in result["data_coverage"].values() if v.get("available", False))
    total = len(result["data_coverage"])
    result["data_coverage"]["overall_coverage_pct"] = round((available / total) * 100) if total > 0 else 0

    has_price = bool(result.get("price_data"))
    _log(f"aggregate_stock_data DONE — {ticker} | price_data={has_price} | coverage={result['data_coverage']['overall_coverage_pct']}%")
    return result


def _fetch_price(ticker, result, report):
    report("Price data", "loading")
    start = time.time()
    data = price.get_live_quote(ticker)
    elapsed = round(time.time() - start, 1)
    if data:
        result["price_data"] = data
        result["current_price"] = data.get("price")
        report("Price data", "done", f"{elapsed}s via {data.get('source', 'unknown')}")
        result["data_coverage"]["price"] = {"available": True, "source": data.get("source"), "fetched_at": datetime.utcnow().isoformat()}
    else:
        report("Price data", "failed", "All sources failed")
        result["data_coverage"]["price"] = {"available": False, "reason": "All price sources failed"}


def _fetch_info(ticker, result, report):
    report("Company info", "loading")
    start = time.time()
    data = price.get_info(ticker)
    elapsed = round(time.time() - start, 1)
    if data:
        result["company_info"] = data
        report("Company info", "done", f"{elapsed}s")
    else:
        report("Company info", "failed", "Not available")


def _fetch_historical(ticker, result, report):
    report("Historical data", "loading")
    start = time.time()
    data = price.get_historical(ticker, period="1y")
    elapsed = round(time.time() - start, 1)
    if data:
        result["historical_data"] = data
        report("Historical data", "done", f"{elapsed}s — {len(data.get('data', []))} data points")
    else:
        report("Historical data", "failed", "Not available")


def _fetch_fundamentals(ticker, result, report):
    report("Fundamentals", "loading")
    start = time.time()
    data = fundamentals.get_fundamentals(ticker)
    elapsed = round(time.time() - start, 1)
    if data:
        result["fundamentals"] = data
        coverage = data.get("coverage_level", "unknown")
        report("Fundamentals", "done", f"{elapsed}s ({coverage} coverage)")
        result["data_coverage"]["fundamentals"] = {
            "available": True, "coverage": coverage,
            "source": data.get("source"), "fetched_at": datetime.utcnow().isoformat(),
        }
    else:
        report("Fundamentals", "failed", "Not available")
        result["data_coverage"]["fundamentals"] = {"available": False, "reason": "No fundamental data available"}


def _fetch_news(ticker, result, report):
    report("News & sentiment", "loading")
    start = time.time()
    data = news.get_company_news(ticker)
    elapsed = round(time.time() - start, 1)
    if data:
        result["news_sentiment"] = data
        count = data.get("article_count", 0)
        report("News & sentiment", "done", f"{elapsed}s — {count} articles")
        result["data_coverage"]["news"] = {
            "available": True, "count": count,
            "source": data.get("source"), "fetched_at": datetime.utcnow().isoformat(),
        }
    else:
        report("News & sentiment", "failed", "No news available")
        result["data_coverage"]["news"] = {"available": False, "reason": "No news data available"}


def _fetch_insider(ticker, result, report):
    report("Insider trading", "loading")
    start = time.time()
    data = insider.get_insider_trades(ticker)
    elapsed = round(time.time() - start, 1)
    cong = insider.get_congressional_trades(ticker)

    if data and data.get("available") is False:
        report("Insider trading", "skipped", data.get("reason", ""))
        result["insider_activity"] = data
        result["data_coverage"]["insider"] = {"available": False, "reason": data.get("reason")}
    elif data:
        result["insider_activity"] = data
        report("Insider trading", "done", f"{elapsed}s")
        result["data_coverage"]["insider"] = {"available": True, "source": data.get("source"), "fetched_at": datetime.utcnow().isoformat()}
    else:
        report("Insider trading", "failed", "Not available")
        result["data_coverage"]["insider"] = {"available": False, "reason": "API error"}

    result["congressional_trades"] = cong


def _fetch_legal(ticker, result, report):
    report("SEC filings", "loading")
    start = time.time()
    data = legal.get_legal_filings(ticker)
    elapsed = round(time.time() - start, 1)
    if data and data.get("available") is False:
        report("SEC filings", "skipped", data.get("reason", ""))
        result["legal_regulatory"] = data
        result["data_coverage"]["legal"] = {"available": False, "reason": data.get("reason")}
    elif data:
        result["legal_regulatory"] = data
        warnings = data.get("parser_warnings", [])
        detail = f"{elapsed}s"
        if warnings:
            detail += f" ({len(warnings)} parser warnings)"
        report("SEC filings", "done", detail)
        result["data_coverage"]["legal"] = {
            "available": True, "source": data.get("source"),
            "parser_warnings": warnings, "fetched_at": datetime.utcnow().isoformat(),
        }
    else:
        report("SEC filings", "failed", "Not available")
        result["data_coverage"]["legal"] = {"available": False, "reason": "Could not fetch SEC data"}


def _fetch_macro(result, report):
    report("Macro indicators", "loading")
    start = time.time()
    data = macro.get_macro_indicators()
    elapsed = round(time.time() - start, 1)
    if data:
        result["macro_environment"] = data
        count = len(data.get("indicators", {}))
        report("Macro indicators", "done", f"{elapsed}s — {count} indicators")
        result["data_coverage"]["macro"] = {"available": True, "source": "fred", "fetched_at": datetime.utcnow().isoformat()}
    else:
        report("Macro indicators", "failed", "FRED API error")
        result["data_coverage"]["macro"] = {"available": False, "reason": "FRED API error or missing key"}
