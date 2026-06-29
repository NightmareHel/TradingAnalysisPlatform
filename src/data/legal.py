from src.db import cache
from src.rate_limiter import edgar_limiter
from src.market_status import is_indian_ticker


def get_legal_filings(ticker: str) -> dict | None:
    if is_indian_ticker(ticker):
        return {
            "available": False,
            "reason": "SEC filings not applicable to non-US stocks",
        }

    cache_key = f"legal:{ticker}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        from edgar import Company

        edgar_limiter.wait()
        company = Company(ticker)

        edgar_limiter.wait()
        filings = company.get_filings(form="10-K")

        if not filings:
            result = {
                "available": False,
                "reason": "No 10-K filings found for this ticker",
            }
            cache.set(cache_key, result, ttl=86400)
            return result

        # Get most recent 10-K
        edgar_limiter.wait()
        try:
            recent = filings.latest(1)
            filing = recent[0] if hasattr(recent, "__getitem__") else recent
        except Exception:
            filing = filings[0] if filings else None

        if not filing:
            result = {"available": False, "reason": "Could not access 10-K filing"}
            cache.set(cache_key, result, ttl=86400)
            return result

        # Extract filing date
        filing_date = ""
        try:
            filing_date = str(getattr(filing, "filing_date", "") or getattr(filing, "date", ""))[:10]
        except Exception:
            pass

        # Extract document sections
        legal_text = ""
        risk_text = ""
        parser_warnings = []

        try:
            edgar_limiter.wait()
            doc = filing.document() if callable(getattr(filing, "document", None)) else None

            if doc is None:
                # Try alternative access pattern
                doc = filing.obj() if callable(getattr(filing, "obj", None)) else None

            if doc is not None:
                # Extract Item 3 — Legal Proceedings
                try:
                    section = doc.get("Item 3") or doc.get("item_3") or doc.get("legal_proceedings")
                    if section is not None:
                        if hasattr(section, "text"):
                            legal_text = str(section.text)[:2000]
                        elif hasattr(section, "warnings"):
                            parser_warnings.extend(section.warnings or [])
                            legal_text = str(section)[:2000]
                        else:
                            legal_text = str(section)[:2000]
                except Exception:
                    pass

                # Extract Item 1A — Risk Factors
                try:
                    section = doc.get("Item 1A") or doc.get("item_1a") or doc.get("risk_factors")
                    if section is not None:
                        if hasattr(section, "text"):
                            risk_text = str(section.text)[:2000]
                        elif hasattr(section, "warnings"):
                            parser_warnings.extend(section.warnings or [])
                            risk_text = str(section)[:2000]
                        else:
                            risk_text = str(section)[:2000]
                except Exception:
                    pass

        except Exception as e:
            parser_warnings.append(f"Document parsing error: {str(e)[:100]}")

        result = {
            "available": True,
            "legal_proceedings": legal_text or "Legal proceedings section could not be extracted.",
            "risk_factors": risk_text or "Risk factors section could not be extracted.",
            "filing_date": filing_date,
            "parser_warnings": parser_warnings,
            "source": "edgartools",
        }
        cache.set(cache_key, result, ttl=86400)
        return result

    except ImportError:
        return {"available": False, "reason": "edgartools not installed"}
    except Exception as e:
        # edgar company not found, no internet, etc.
        result = {
            "available": False,
            "reason": f"SEC data unavailable: {str(e)[:100]}",
        }
        cache.set(cache_key, result, ttl=3600)
        return result
