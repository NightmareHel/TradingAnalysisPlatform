import math
import requests
import yfinance as yf

from src import config
from src.db import cache
from src.market_status import is_indian_ticker

_FMP_BASE = "https://financialmodelingprep.com/stable"


def _safe(val) -> float | None:
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _fmp_get(endpoint: str, ticker: str, key: str) -> dict | None:
    try:
        r = requests.get(
            f"{_FMP_BASE}/{endpoint}",
            params={"symbol": ticker, "limit": 1, "apikey": key},
            timeout=12,
        )
        if r.ok:
            data = r.json()
            return data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else None)
    except Exception:
        pass
    return None


def get_fundamentals(ticker: str) -> dict | None:
    cache_key = f"fundamentals:{ticker}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Indian stocks: yfinance .info (basic coverage)
    if is_indian_ticker(ticker):
        result = _get_from_yfinance(ticker, coverage_level="basic")
        if result:
            cache.set(cache_key, result, ttl=86400)
        return result

    # US stocks: FMP (full coverage), fallback to yfinance
    key = config.get_api_key("fmp")
    if key:
        result = _get_from_fmp(ticker, key)
        if result:
            cache.set(cache_key, result, ttl=86400)
            return result

    # FMP unavailable — fall back to yfinance basic
    result = _get_from_yfinance(ticker, coverage_level="basic")
    if result:
        cache.set(cache_key, result, ttl=86400)
    return result


def _get_from_fmp(ticker: str, key: str) -> dict | None:
    try:
        metrics = _fmp_get("key-metrics", ticker, key)
        ratios = _fmp_get("ratios", ticker, key)
        income = _fmp_get("income-statement", ticker, key)

        if not metrics:
            return None

        result = {
            "coverage_level": "full",
            "source": "fmp",
            # pe/pb now live in ratios in the stable API
            "pe_ratio": _safe((ratios or {}).get("priceToEarningsRatio")),
            "pb_ratio": _safe((ratios or {}).get("priceToBookRatio")),
            "market_cap": _safe(metrics.get("marketCap")),
            "ev": _safe(metrics.get("enterpriseValue")),
            "ev_to_ebitda": _safe(metrics.get("evToEBITDA")),
            "price_to_sales": _safe((ratios or {}).get("priceToSalesRatio")),
            "eps": _safe((ratios or {}).get("netIncomePerShare")),
            "book_value_per_share": _safe((ratios or {}).get("bookValuePerShare")),
            "dividend_yield": _safe((ratios or {}).get("dividendYield")),
            "revenue_per_share": _safe((ratios or {}).get("revenuePerShare")),
            "free_cash_flow_per_share": _safe((ratios or {}).get("freeCashFlowPerShare")),
        }

        if ratios:
            result.update({
                "gross_margin": _safe(ratios.get("grossProfitMargin")),
                "net_margin": _safe(ratios.get("netProfitMargin")),
                "roe": _safe(metrics.get("returnOnEquity")),
                "roa": _safe(metrics.get("returnOnAssets")),
                "debt_to_equity": _safe(ratios.get("debtToEquityRatio")),
                "current_ratio": _safe(ratios.get("currentRatio")),
                "interest_coverage": _safe(ratios.get("interestCoverageRatio")),
            })

        if income:
            result.update({
                "revenue": _safe(income.get("revenue")),
                "net_income": _safe(income.get("netIncome")),
                "ebitda": _safe(income.get("ebitda")),
                "gross_profit": _safe(income.get("grossProfit")),
                "fiscal_year": income.get("date", "")[:4],
            })

        return result
    except Exception:
        return None


def _get_from_yfinance(ticker: str, coverage_level: str = "basic") -> dict | None:
    try:
        info = yf.Ticker(ticker).info
        if not info or not info.get("symbol"):
            return None
        return {
            "coverage_level": coverage_level,
            "source": "yfinance",
            "pe_ratio": _safe(info.get("trailingPE")),
            "forward_pe": _safe(info.get("forwardPE")),
            "pb_ratio": _safe(info.get("priceToBook")),
            "market_cap": _safe(info.get("marketCap")),
            "revenue": _safe(info.get("totalRevenue")),
            "net_income": None,
            "gross_margin": _safe(info.get("grossMargins")),
            "net_margin": _safe(info.get("profitMargins")),
            "operating_margin": _safe(info.get("operatingMargins")),
            "roe": _safe(info.get("returnOnEquity")),
            "roa": _safe(info.get("returnOnAssets")),
            "debt_to_equity": _safe(info.get("debtToEquity")),
            "current_ratio": _safe(info.get("currentRatio")),
            "book_value_per_share": _safe(info.get("bookValue")),
            "eps": _safe(info.get("trailingEps")),
            "dividend_yield": _safe(info.get("dividendYield")),
            "analyst_target": _safe(info.get("targetMeanPrice")),
            "beta": _safe(info.get("beta")),
            "52w_high": _safe(info.get("fiftyTwoWeekHigh")),
            "52w_low": _safe(info.get("fiftyTwoWeekLow")),
        }
    except Exception:
        return None
