from src import config
from src.db import cache

_SERIES = {
    "GDP":      ("GDP",       "Gross Domestic Product ($B)"),
    "CPI":      ("CPIAUCSL",  "Consumer Price Index"),
    "FEDFUNDS": ("FEDFUNDS",  "Federal Funds Rate (%)"),
    "UNRATE":   ("UNRATE",    "Unemployment Rate (%)"),
    "DGS10":    ("DGS10",     "10-Year Treasury Yield (%)"),
    "DGS2":     ("DGS2",      "2-Year Treasury Yield (%)"),
    "VIXCLS":   ("VIXCLS",    "VIX Volatility Index"),
}


def get_macro_indicators() -> dict | None:
    cache_key = "macro:indicators"
    cached = cache.get(cache_key)
    if cached:
        return cached

    key = config.get_api_key("fred")
    if not key:
        return None

    try:
        from fredapi import Fred
        fred = Fred(api_key=key)

        indicators = {}
        for name, (series_id, description) in _SERIES.items():
            try:
                series = fred.get_series(series_id)
                latest = float(series.dropna().iloc[-1])
                indicators[name] = {
                    "value": round(latest, 4),
                    "series": series_id,
                    "description": description,
                }
            except Exception:
                indicators[name] = {
                    "value": None,
                    "series": series_id,
                    "description": description,
                }

        # Yield curve analysis
        dgs10 = indicators.get("DGS10", {}).get("value")
        dgs2 = indicators.get("DGS2", {}).get("value")
        yield_curve = {}
        if dgs10 is not None and dgs2 is not None:
            spread = round(dgs10 - dgs2, 3)
            if spread < 0:
                interpretation = f"Inverted ({spread:+.2f}%) — historically a recession indicator"
            elif spread < 0.5:
                interpretation = f"Flat ({spread:+.2f}%) — economic uncertainty"
            else:
                interpretation = f"Normal ({spread:+.2f}%) — growth environment"
            yield_curve = {"spread": spread, "interpretation": interpretation}

        result = {
            "indicators": indicators,
            "yield_curve": yield_curve,
            "source": "fred",
        }
        cache.set(cache_key, result, ttl=86400)
        return result

    except Exception:
        return None
