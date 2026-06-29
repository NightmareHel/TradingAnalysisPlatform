import os
import yaml
import requests
import anthropic

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")

DEFAULT_CONFIG = {
    "api_keys": {
        "anthropic": "",
        "fred": "",
        "finnhub": "",
        "fmp": "",
    },
    "settings": {
        "claude_model": "claude-sonnet-4-6",
        "max_stocks": 5,
        "monthly_budget_usd": 30.0,
    },
    "disclaimer_accepted": False,
}


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f) or {}
    merged = DEFAULT_CONFIG.copy()
    for section in DEFAULT_CONFIG:
        if section in config:
            if isinstance(DEFAULT_CONFIG[section], dict):
                merged[section] = {**DEFAULT_CONFIG[section], **config[section]}
            else:
                merged[section] = config[section]
    return merged


def save_config(config: dict):
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def get_api_key(service: str) -> str:
    config = load_config()
    key = config.get("api_keys", {}).get(service, "")
    if not key and service == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY", "")
    return key


def detect_llm_provider(key: str) -> str:
    """Returns 'groq' if key starts with gsk_, else 'anthropic'."""
    return "groq" if key.startswith("gsk_") else "anthropic"


def has_required_keys() -> bool:
    config = load_config()
    keys = config.get("api_keys", {})
    return bool(keys.get("anthropic"))


def test_groq_connection(api_key: str) -> tuple[bool, str]:
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
            timeout=10,
        )
        if resp.status_code == 401:
            return False, "Invalid API key"
        if resp.status_code == 429:
            return False, "Rate limited — try again in a moment"
        if resp.status_code == 200:
            return True, "Connected (Groq / llama-3.3-70b-versatile)"
        return False, f"Unexpected response: {resp.status_code}"
    except requests.ConnectionError:
        return False, "Connection failed — check internet"
    except Exception as e:
        return False, f"Error: {str(e)}"


def test_llm_connection(api_key: str) -> tuple[bool, str]:
    """Auto-detect provider from key prefix and test accordingly."""
    if detect_llm_provider(api_key) == "groq":
        return test_groq_connection(api_key)
    return test_anthropic_connection(api_key)


def test_anthropic_connection(api_key: str) -> tuple[bool, str]:
    try:
        client = anthropic.Anthropic(api_key=api_key)
        client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}],
        )
        return True, "Connected successfully"
    except anthropic.AuthenticationError:
        return False, "Invalid API key"
    except anthropic.APIConnectionError:
        return False, "Connection failed — check internet"
    except Exception as e:
        return False, f"Error: {str(e)}"


def test_finnhub_connection(api_key: str) -> tuple[bool, str]:
    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/stock/profile2",
            params={"symbol": "AAPL", "token": api_key},
            timeout=10,
        )
        if resp.status_code == 401:
            return False, "Invalid API key"
        if resp.status_code == 429:
            return False, "Rate limited — try again in a minute"
        if resp.status_code == 200 and resp.json():
            return True, "Connected successfully"
        return False, f"Unexpected response: {resp.status_code}"
    except requests.ConnectionError:
        return False, "Connection failed — check internet"
    except Exception as e:
        return False, f"Error: {str(e)}"


def test_fmp_connection(api_key: str) -> tuple[bool, str]:
    try:
        resp = requests.get(
            "https://financialmodelingprep.com/stable/profile",
            params={"symbol": "AAPL", "apikey": api_key},
            timeout=10,
        )
        if resp.status_code == 401 or resp.status_code == 403:
            return False, "Invalid API key"
        if resp.status_code == 429:
            return False, "Daily limit reached (250 calls)"
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                return True, "Connected successfully"
            if isinstance(data, dict) and "Error Message" in data:
                return False, data["Error Message"]
        return False, f"Unexpected response: {resp.status_code}"
    except requests.ConnectionError:
        return False, "Connection failed — check internet"
    except Exception as e:
        return False, f"Error: {str(e)}"


def test_fred_connection(api_key: str) -> tuple[bool, str]:
    try:
        resp = requests.get(
            "https://api.stlouisfed.org/fred/series",
            params={
                "series_id": "GDP",
                "api_key": api_key,
                "file_type": "json",
            },
            timeout=10,
        )
        if resp.status_code == 400:
            data = resp.json()
            if "api_key" in str(data).lower():
                return False, "Invalid API key"
        if resp.status_code == 200:
            return True, "Connected successfully"
        return False, f"Unexpected response: {resp.status_code}"
    except requests.ConnectionError:
        return False, "Connection failed — check internet"
    except Exception as e:
        return False, f"Error: {str(e)}"
