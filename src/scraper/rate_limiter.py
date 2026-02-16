"""도메인별 요청 간격 제한."""

from __future__ import annotations

import time
import threading
from collections import defaultdict
from urllib.parse import urlparse


class RateLimiter:
    """같은 도메인에 대해 최소 delay초 간격을 보장."""

    def __init__(self, default_delay: float = 2.0):
        self.default_delay = default_delay
        self._last_request: dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()

    def wait(self, url: str) -> None:
        domain = urlparse(url).netloc
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request[domain]
            if elapsed < self.default_delay:
                time.sleep(self.default_delay - elapsed)
            self._last_request[domain] = time.time()
