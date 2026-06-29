from datetime import datetime, time as dtime
import pytz

US_HOLIDAYS_2026 = {
    (1, 1), (1, 19), (2, 16), (4, 3), (5, 25), (7, 3),
    (9, 7), (11, 26), (12, 25),
}

INDIA_HOLIDAYS_2026 = {
    (1, 26), (3, 14), (3, 31), (4, 1), (4, 6), (4, 10),
    (4, 14), (5, 1), (6, 17), (7, 6), (8, 15), (8, 19),
    (10, 2), (10, 20), (10, 21), (11, 5), (11, 12), (12, 25),
}

ET = pytz.timezone("US/Eastern")
IST = pytz.timezone("Asia/Kolkata")


def _is_holiday(dt: datetime, holidays: set) -> bool:
    return (dt.month, dt.day) in holidays


def is_market_open(exchange: str) -> bool:
    if exchange in ("NYSE", "NASDAQ", "US"):
        now = datetime.now(ET)
        if now.weekday() >= 5:
            return False
        if _is_holiday(now, US_HOLIDAYS_2026):
            return False
        market_open = dtime(9, 30)
        market_close = dtime(16, 0)
        return market_open <= now.time() <= market_close

    if exchange in ("NSE", "BSE", "INDIA"):
        now = datetime.now(IST)
        if now.weekday() >= 5:
            return False
        if _is_holiday(now, INDIA_HOLIDAYS_2026):
            return False
        market_open = dtime(9, 15)
        market_close = dtime(15, 30)
        return market_open <= now.time() <= market_close

    return False


def get_exchange(ticker: str) -> str:
    if ticker.endswith(".NS"):
        return "NSE"
    if ticker.endswith(".BO"):
        return "BSE"
    return "US"


def is_indian_ticker(ticker: str) -> bool:
    return ticker.endswith(".NS") or ticker.endswith(".BO")


def get_currency(ticker: str) -> str:
    return "INR" if is_indian_ticker(ticker) else "USD"


def get_status_text(ticker: str) -> str:
    exchange = get_exchange(ticker)
    is_open = is_market_open(exchange)

    if exchange in ("NSE", "BSE"):
        now = datetime.now(IST)
        if is_open:
            return f"{exchange}: Open"
        close_time = "3:30 PM IST"
        if now.weekday() >= 5:
            days_until = 7 - now.weekday()
            return f"{exchange}: Closed — prices as of last Friday, {close_time}. Opens Monday 9:15 AM IST"
        return f"{exchange}: Closed — prices as of today, {close_time}. Opens next trading day 9:15 AM IST"
    else:
        now = datetime.now(ET)
        if is_open:
            return "NYSE/NASDAQ: Open"
        close_time = "4:00 PM ET"
        if now.weekday() >= 5:
            return f"NYSE/NASDAQ: Closed — prices as of last Friday, {close_time}. Opens Monday 9:30 AM ET"
        return f"NYSE/NASDAQ: Closed — prices as of today, {close_time}. Opens next trading day 9:30 AM ET"


def get_1d_label(ticker: str) -> str:
    exchange = get_exchange(ticker)
    if is_market_open(exchange):
        return "1 Day"
    return "Next Trading Day"
