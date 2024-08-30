import time
from functools import wraps


class RateLimiter:
    """
    Rate limiter decorator to limit the number of calls to a function within a
    certain period (in seconds).

    Parameters
    ----------
    max_calls
        The maximum number of calls allowed within the period.
    period
        The period (in seconds) within which the maximum number of calls is
        allowed.
    """

    def __init__(self, max_calls: int, period: int):
        self.max_calls = max_calls
        self.period = period
        self.timestamps: list[float] = []

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.perf_counter()
            self.timestamps = [
                t for t in self.timestamps if now - t < self.period
            ]

            if len(self.timestamps) >= self.max_calls:
                sleep_time = self.period - (now - self.timestamps[0])
                time.sleep(max(sleep_time, 0))

            self.timestamps.append(time.perf_counter())
            return func(*args, **kwargs)

        return wrapper
