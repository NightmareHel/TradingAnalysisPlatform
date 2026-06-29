import json
import requests
import anthropic
from src import config
from src.db import cache
from src import cost_tracker

_GROQ_BASE = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_SUMMARIZE_MODEL = "llama-3.3-70b-versatile"


def _log(msg: str):
    print(f"[SUMMARIZER] {msg}", flush=True)


def summarize_data(aggregated_data: dict) -> dict | None:
    ticker = aggregated_data.get("ticker", "UNKNOWN")
    _log(f"START — {ticker}")
    cache_key = f"summary:{ticker}"
    cached = cache.get(cache_key)
    if cached:
        _log(f"CACHE HIT — {ticker}")
        return cached

    api_key = config.get_api_key("anthropic")
    if not api_key:
        return None

    compact = _build_compact_data(aggregated_data)

    sections_to_summarize = {}

    if aggregated_data.get("fundamentals"):
        sections_to_summarize["fundamentals"] = json.dumps(aggregated_data["fundamentals"], default=str)
    if aggregated_data.get("news_sentiment"):
        articles = aggregated_data["news_sentiment"].get("articles", [])
        sections_to_summarize["news"] = json.dumps(
            [{"headline": a["headline"], "sentiment": a["sentiment_score"], "source": a["source_name"]} for a in articles[:10]],
            default=str,
        )
    if aggregated_data.get("insider_activity") and aggregated_data["insider_activity"].get("available", True):
        sections_to_summarize["insider"] = json.dumps(aggregated_data["insider_activity"], default=str)
    if aggregated_data.get("congressional_trades") and aggregated_data["congressional_trades"].get("available", True):
        sections_to_summarize["congressional"] = json.dumps(aggregated_data["congressional_trades"], default=str)
    if aggregated_data.get("legal_regulatory") and aggregated_data["legal_regulatory"].get("available", True):
        legal_data = aggregated_data["legal_regulatory"].copy()
        if legal_data.get("risk_factors"):
            legal_data["risk_factors"] = legal_data["risk_factors"][:2000]
        if legal_data.get("legal_proceedings"):
            legal_data["legal_proceedings"] = legal_data["legal_proceedings"][:2000]
        sections_to_summarize["legal"] = json.dumps(legal_data, default=str)
    if aggregated_data.get("macro_environment"):
        sections_to_summarize["macro"] = json.dumps(aggregated_data["macro_environment"], default=str)

    if not sections_to_summarize:
        compact["summaries"] = {}
        return compact

    prompt = f"""Summarize the following financial data sections for {ticker} into concise analytical bullets.
For each section, provide 3-5 key takeaways that would be most relevant for predicting stock price movement.
Focus on: trends, anomalies, risks, and catalysts.

DATA SECTIONS:
{json.dumps(sections_to_summarize, indent=1, default=str)}

Return a JSON object with keys matching the section names, each containing a list of concise bullet strings.
Example: {{"fundamentals": ["Revenue grew 12% YoY to $94B", "Debt-to-equity at 1.8, elevated vs peers"], ...}}"""

    provider = config.detect_llm_provider(api_key)
    _log(f"Calling {provider} for {ticker} — sections: {list(sections_to_summarize.keys())}")

    try:
        if provider == "groq":
            summaries = _call_groq(api_key, ticker, prompt)
        else:
            summaries = _call_anthropic(api_key, ticker, prompt)

        _log(f"DONE — {ticker} | summaries keys: {list(summaries.keys()) if isinstance(summaries, dict) else type(summaries)}")
        compact["summaries"] = summaries
        cache.set(cache_key, compact, ttl=1800)
        return compact
    except Exception as exc:
        _log(f"ERROR — {ticker}: {type(exc).__name__}: {exc}")
        compact["summaries"] = {}
        return compact


def _call_anthropic(api_key: str, ticker: str, prompt: str) -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=[{
            "type": "text",
            "text": "You are a financial data analyst. Summarize raw financial data into concise, actionable bullet points. Return valid JSON only.",
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": prompt}],
    )
    cost_tracker.log_usage(
        ticker=ticker,
        pass_name="summarize",
        model="claude-haiku-4-5-20251001",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return json.loads(text)


def _call_groq(api_key: str, ticker: str, prompt: str) -> dict:
    resp = requests.post(
        _GROQ_BASE,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": _GROQ_SUMMARIZE_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a financial data analyst. Summarize raw financial data into concise, actionable bullet points. Return valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 2048,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage", {})
    cost_tracker.log_usage(
        ticker=ticker,
        pass_name="summarize",
        model=_GROQ_SUMMARIZE_MODEL,
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
    )
    return json.loads(data["choices"][0]["message"]["content"])


def _build_compact_data(aggregated_data: dict) -> dict:
    compact = {
        "ticker": aggregated_data.get("ticker"),
        "exchange": aggregated_data.get("exchange"),
        "currency": aggregated_data.get("currency"),
        "timestamp": aggregated_data.get("timestamp"),
        "market_status": aggregated_data.get("market_status"),
        "current_price": aggregated_data.get("current_price"),
        "data_coverage": aggregated_data.get("data_coverage"),
    }

    if aggregated_data.get("company_info"):
        compact["company_info"] = {
            "name": aggregated_data["company_info"].get("name"),
            "sector": aggregated_data["company_info"].get("sector"),
            "industry": aggregated_data["company_info"].get("industry"),
        }

    if aggregated_data.get("price_data"):
        compact["price_data"] = aggregated_data["price_data"]

    if aggregated_data.get("technical_indicators"):
        compact["technical_indicators"] = aggregated_data["technical_indicators"]

    if aggregated_data.get("news_sentiment"):
        compact["news_meta"] = {
            "article_count": aggregated_data["news_sentiment"].get("article_count"),
            "average_sentiment": aggregated_data["news_sentiment"].get("average_sentiment"),
        }

    return compact
