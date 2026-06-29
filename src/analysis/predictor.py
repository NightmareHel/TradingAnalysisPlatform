import json
import requests
import anthropic
from src import config
from src.db import cache
from src import cost_tracker


def _log(msg: str):
    print(f"[PREDICTOR] {msg}", flush=True)

_GROQ_BASE = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_PREDICT_MODEL = "llama-3.3-70b-versatile"

_GROQ_SCHEMA_INSTRUCTIONS = """
Return ONLY a JSON object with this exact structure (no markdown, no code blocks):
{
  "predictions": {
    "1d": {
      "price_change_low_pct": <number>,
      "price_change_high_pct": <number>,
      "confidence_pct": <integer 0-100>,
      "direction": <one of: "strongly_bearish","bearish","slightly_bearish","neutral","slightly_bullish","bullish","strongly_bullish">,
      "bullish_factors": [<string>, ...],
      "bearish_factors": [<string>, ...],
      "key_catalysts": [<string>, ...],
      "source_citations": [<string>, ...]
    },
    "1w": { <same structure> },
    "1m": { <same structure> },
    "1y": { <same structure> }
  },
  "current_price": <number>,
  "currency": <string>,
  "executive_summary": <string>,
  "risk_assessment": <string>,
  "data_coverage_note": <string>
}"""

PREDICTION_SCHEMA = {
    "type": "object",
    "properties": {
        "predictions": {
            "type": "object",
            "properties": {
                "1d": {"$ref": "#/$defs/timeframe"},
                "1w": {"$ref": "#/$defs/timeframe"},
                "1m": {"$ref": "#/$defs/timeframe"},
                "1y": {"$ref": "#/$defs/timeframe"},
            },
            "required": ["1d", "1w", "1m", "1y"],
            "additionalProperties": False,
        },
        "current_price": {"type": "number"},
        "currency": {"type": "string"},
        "executive_summary": {"type": "string"},
        "risk_assessment": {"type": "string"},
        "data_coverage_note": {"type": "string"},
    },
    "required": ["predictions", "current_price", "currency", "executive_summary", "risk_assessment", "data_coverage_note"],
    "additionalProperties": False,
    "$defs": {
        "timeframe": {
            "type": "object",
            "properties": {
                "price_change_low_pct": {"type": "number"},
                "price_change_high_pct": {"type": "number"},
                "confidence_pct": {"type": "integer"},
                "direction": {"type": "string", "enum": ["strongly_bearish", "bearish", "slightly_bearish", "neutral", "slightly_bullish", "bullish", "strongly_bullish"]},
                "bullish_factors": {"type": "array", "items": {"type": "string"}},
                "bearish_factors": {"type": "array", "items": {"type": "string"}},
                "key_catalysts": {"type": "array", "items": {"type": "string"}},
                "source_citations": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["price_change_low_pct", "price_change_high_pct", "confidence_pct", "direction", "bullish_factors", "bearish_factors", "key_catalysts", "source_citations"],
            "additionalProperties": False,
        }
    },
}

SYSTEM_PROMPT = """You are a senior equity research analyst producing stock predictions for clients.

TASK: Analyze the provided stock data and produce percentage-range predictions for 4 timeframes (1d, 1w, 1m, 1y).

PREDICTION FORMAT:
- Output percentage ranges (e.g., -0.8% to +1.2%) representing expected price change from current price
- Narrower range = higher conviction. Wider range = more uncertainty
- Confidence % reflects how much supporting data was available and how consistent the signals are

WEIGHTING RULES:
- 1 Day / 1 Week: Weight technical indicators (RSI, MACD, Bollinger, volume) most heavily. News sentiment is secondary
- 1 Month: Balance technicals with fundamentals and news. Consider upcoming catalysts (earnings, legal)
- 1 Year: Weight fundamentals (revenue growth, margins, debt) and macro environment most heavily. Technicals are noise at this scale

DATA COVERAGE RULES:
- Check the data_coverage section. If overall_coverage_pct is below 50%, widen ALL ranges and lower confidence
- If fundamental data has coverage_level "basic", note this and widen 1m/1y ranges
- If legal/insider data is unavailable (non-US stock), note this and adjust confidence downward

RANGE BOUNDS:
- 1d: typical range +/- 0.5% to 5%
- 1w: typical range +/- 1% to 10%
- 1m: typical range +/- 3% to 25%
- 1y: typical range +/- 10% to 60%

CITATIONS:
- Every factor must cite a specific data point (e.g., "RSI(14) = 72 — overbought territory", "P/E 28 vs sector avg 22")
- Include the data source in citations (e.g., "yfinance", "FMP", "Finnhub", "FRED")

IMPORTANT: This analysis is for informational and educational purposes only. It is NOT financial advice. Include this disclaimer in the executive_summary."""


def get_prediction(summarized_data: dict) -> dict | None:
    ticker = summarized_data.get("ticker", "UNKNOWN")
    _log(f"START — {ticker}")
    cache_key = f"prediction:{ticker}"
    cached = cache.get(cache_key)
    if cached:
        _log(f"CACHE HIT — {ticker}")
        return cached

    api_key = config.get_api_key("anthropic")
    if not api_key:
        _log(f"ERROR — no API key configured")
        return None

    provider = config.detect_llm_provider(api_key)
    _log(f"Calling {provider} for {ticker}")
    user_content = f"Analyze this stock data and provide percentage-range predictions:\n\n{json.dumps(summarized_data, indent=1, default=str)}"

    try:
        if provider == "groq":
            prediction = _call_groq(api_key, ticker, user_content)
        else:
            conf = config.load_config()
            model = conf.get("settings", {}).get("claude_model", "claude-sonnet-4-6")
            prediction = _call_anthropic(api_key, ticker, model, user_content)

        if prediction.get("error"):
            _log(f"LLM ERROR — {ticker}: {prediction.get('message')}")
            return prediction

        _log(f"DONE — {ticker} | timeframes: {list(prediction.get('predictions', {}).keys())}")
        prediction = _post_validate(prediction)

        for tf_key, tf_data in prediction.get("predictions", {}).items():
            cache.save_prediction(
                ticker=ticker,
                timeframe=tf_key,
                predicted_low_pct=tf_data["price_change_low_pct"],
                predicted_high_pct=tf_data["price_change_high_pct"],
                confidence=tf_data["confidence_pct"],
                current_price=prediction.get("current_price", 0),
                currency=prediction.get("currency", "USD"),
            )

        cache.set(cache_key, prediction, ttl=3600)
        return prediction
    except Exception as exc:
        _log(f"EXCEPTION — {ticker}: {type(exc).__name__}: {exc}")
        return {"error": True, "message": f"Prediction failed: {str(exc)}"}


def _call_anthropic(api_key: str, ticker: str, model: str, user_content: str) -> dict:
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=8192,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_content}],
            output_config={"format": {"type": "json_schema", "schema": PREDICTION_SCHEMA}},
        )
        cost_tracker.log_usage(
            ticker=ticker, pass_name="predict", model=model,
            input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens,
        )
        if response.stop_reason == "max_tokens":
            response = client.messages.create(
                model=model, max_tokens=16384,
                system=[{"type": "text", "text": SYSTEM_PROMPT}],
                messages=[{"role": "user", "content": user_content}],
                output_config={"format": {"type": "json_schema", "schema": PREDICTION_SCHEMA}},
            )
            cost_tracker.log_usage(
                ticker=ticker, pass_name="predict_retry", model=model,
                input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens,
            )
        if response.stop_reason == "refusal":
            return {"error": True, "message": "Claude was unable to analyze this ticker. This may be due to content restrictions. Try a different stock."}
        text_block = next(b for b in response.content if b.type == "text")
        return json.loads(text_block.text)
    except anthropic.AuthenticationError:
        return {"error": True, "message": "Invalid Anthropic API key. Please check your key in Settings."}
    except anthropic.RateLimitError:
        return {"error": True, "message": "Claude API rate limit reached. Please wait a moment and try again."}
    except anthropic.APIConnectionError:
        return {"error": True, "message": "Could not connect to Claude API. Check your internet connection."}


def _call_groq(api_key: str, ticker: str, user_content: str) -> dict:
    resp = requests.post(
        _GROQ_BASE,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": _GROQ_PREDICT_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT + _GROQ_SCHEMA_INSTRUCTIONS},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 8192,
        },
        timeout=60,
    )
    if resp.status_code == 401:
        return {"error": True, "message": "Invalid Groq API key. Please check your key in Settings."}
    if resp.status_code == 429:
        return {"error": True, "message": "Groq rate limit reached. Please wait a moment and try again."}
    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage", {})
    cost_tracker.log_usage(
        ticker=ticker, pass_name="predict", model=_GROQ_PREDICT_MODEL,
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
    )
    finish_reason = data.get("choices", [{}])[0].get("finish_reason", "")
    if finish_reason == "length":
        return {"error": True, "message": "Groq response truncated (output too long). Try again."}
    return json.loads(data["choices"][0]["message"]["content"])


def _post_validate(prediction: dict) -> dict:
    for tf_key in ("1d", "1w", "1m", "1y"):
        tf = prediction.get("predictions", {}).get(tf_key, {})
        if "confidence_pct" in tf:
            tf["confidence_pct"] = max(0, min(100, tf["confidence_pct"]))
        if "price_change_low_pct" in tf and "price_change_high_pct" in tf:
            if tf["price_change_low_pct"] > tf["price_change_high_pct"]:
                tf["price_change_low_pct"], tf["price_change_high_pct"] = tf["price_change_high_pct"], tf["price_change_low_pct"]
    return prediction
