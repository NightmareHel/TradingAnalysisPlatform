import json
import os
import sqlite3
import threading
import time

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "cache.db")

_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            created_at REAL NOT NULL,
            ttl INTEGER NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS prediction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            timestamp REAL NOT NULL,
            timeframe TEXT NOT NULL,
            predicted_low_pct REAL NOT NULL,
            predicted_high_pct REAL NOT NULL,
            confidence REAL NOT NULL,
            current_price_at_prediction REAL NOT NULL,
            currency TEXT NOT NULL,
            resolved_price REAL,
            resolved_at REAL,
            hit INTEGER
        )"""
    )
    conn.commit()
    return conn


def get(key: str) -> dict | list | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT value, created_at, ttl FROM cache WHERE key = ?", (key,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    value, created_at, ttl = row
    if time.time() > created_at + ttl:
        return None
    return json.loads(value)


def get_with_age(key: str) -> tuple[dict | list | None, float | None]:
    conn = _get_conn()
    row = conn.execute(
        "SELECT value, created_at, ttl FROM cache WHERE key = ?", (key,)
    ).fetchone()
    conn.close()
    if row is None:
        return None, None
    value, created_at, ttl = row
    age_seconds = time.time() - created_at
    if age_seconds > ttl:
        return None, None
    return json.loads(value), age_seconds


def set(key: str, value, ttl: int):
    serialized = json.dumps(value, default=str)
    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, created_at, ttl) VALUES (?, ?, ?, ?)",
            (key, serialized, time.time(), ttl),
        )
        conn.commit()
        conn.close()


def clear_expired():
    with _lock:
        conn = _get_conn()
        conn.execute("DELETE FROM cache WHERE created_at + ttl < ?", (time.time(),))
        conn.commit()
        conn.close()


def clear_for_ticker(ticker: str):
    with _lock:
        conn = _get_conn()
        conn.execute("DELETE FROM cache WHERE key LIKE ?", (f"%:{ticker}:%",))
        conn.execute("DELETE FROM cache WHERE key LIKE ?", (f"%:{ticker}",))
        conn.commit()
        conn.close()


def clear_all():
    with _lock:
        conn = _get_conn()
        conn.execute("DELETE FROM cache")
        conn.commit()
        conn.close()


def get_size_mb() -> float:
    if not os.path.exists(DB_PATH):
        return 0.0
    return os.path.getsize(DB_PATH) / (1024 * 1024)


def save_prediction(
    ticker: str,
    timeframe: str,
    predicted_low_pct: float,
    predicted_high_pct: float,
    confidence: float,
    current_price: float,
    currency: str,
):
    with _lock:
        conn = _get_conn()
        conn.execute(
            """INSERT INTO prediction_history
            (ticker, timestamp, timeframe, predicted_low_pct, predicted_high_pct,
             confidence, current_price_at_prediction, currency)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticker, time.time(), timeframe, predicted_low_pct, predicted_high_pct,
             confidence, current_price, currency),
        )
        conn.commit()
        conn.close()


def get_prediction_history(ticker: str = None) -> list[dict]:
    conn = _get_conn()
    if ticker:
        rows = conn.execute(
            "SELECT * FROM prediction_history WHERE ticker = ? ORDER BY timestamp DESC",
            (ticker,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM prediction_history ORDER BY timestamp DESC"
        ).fetchall()
    conn.close()
    cols = [
        "id", "ticker", "timestamp", "timeframe", "predicted_low_pct",
        "predicted_high_pct", "confidence", "current_price_at_prediction",
        "currency", "resolved_price", "resolved_at", "hit",
    ]
    return [dict(zip(cols, row)) for row in rows]


def resolve_prediction(pred_id: int, resolved_price: float, hit: bool):
    with _lock:
        conn = _get_conn()
        conn.execute(
            "UPDATE prediction_history SET resolved_price = ?, resolved_at = ?, hit = ? WHERE id = ?",
            (resolved_price, time.time(), int(hit), pred_id),
        )
        conn.commit()
        conn.close()
