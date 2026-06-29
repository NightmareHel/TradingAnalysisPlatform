import os
import sqlite3
import threading
import time
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cost.db")

_lock = threading.Lock()

PRICING = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
}


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            ticker TEXT NOT NULL,
            pass_name TEXT NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            estimated_cost_usd REAL NOT NULL
        )"""
    )
    conn.commit()
    return conn


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = PRICING.get(model, PRICING["claude-sonnet-4-6"])
    input_cost = (input_tokens / 1_000_000) * prices["input"]
    output_cost = (output_tokens / 1_000_000) * prices["output"]
    return round(input_cost + output_cost, 6)


def log_usage(
    ticker: str,
    pass_name: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
):
    cost = estimate_cost(model, input_tokens, output_tokens)
    with _lock:
        conn = _get_conn()
        conn.execute(
            """INSERT INTO usage_log
            (timestamp, ticker, pass_name, model, input_tokens, output_tokens, estimated_cost_usd)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (time.time(), ticker, pass_name, model, input_tokens, output_tokens, cost),
        )
        conn.commit()
        conn.close()
    return cost


def get_daily_spend() -> float:
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    conn = _get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(estimated_cost_usd), 0) FROM usage_log WHERE timestamp >= ?",
        (today_start,),
    ).fetchone()
    conn.close()
    return round(row[0], 4)


def get_monthly_spend() -> float:
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
    conn = _get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(estimated_cost_usd), 0) FROM usage_log WHERE timestamp >= ?",
        (month_start,),
    ).fetchone()
    conn.close()
    return round(row[0], 4)


def get_total_analyses_today() -> int:
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(DISTINCT ticker || '-' || CAST(CAST(timestamp/3600 AS INT) AS TEXT)) FROM usage_log WHERE timestamp >= ? AND pass_name = 'predict'",
        (today_start,),
    ).fetchone()
    conn.close()
    return row[0]
