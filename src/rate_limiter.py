import time
import threading
from collections import deque


class RateLimiter:
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls: deque[float] = deque()
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = time.time()
            while self.calls and self.calls[0] < now - self.period:
                self.calls.popleft()
            if len(self.calls) >= self.max_calls:
                sleep_time = self.calls[0] + self.period - now
                if sleep_time > 0:
                    time.sleep(sleep_time)
            self.calls.append(time.time())


finnhub_limiter = RateLimiter(max_calls=55, period=60)
edgar_limiter = RateLimiter(max_calls=9, period=1)
