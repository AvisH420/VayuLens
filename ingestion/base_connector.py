"""Role 1: abstract base connector.

Every data-source connector inherits from this. It provides:
  * Exponential-backoff retry for real API calls
  * Token-bucket rate-limit throttling
  * A single `pull()` entry-point that routes to mock or real
"""

from __future__ import annotations

import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime

from ingestion import config as cfg

logger = logging.getLogger("vayulens.ingestion")


class BaseConnector(ABC):
    """Abstract base for all environmental-data connectors."""

    source_name: str = "base"

    def __init__(self) -> None:
        self._rate_limit = cfg.RATE_LIMITS.get(self.source_name, 1.0)
        self._last_req_ts = 0.0

    # ── public entry-point ────────────────────────────────────────────
    def pull(
        self,
        bbox: tuple[float, float, float, float],
        since: datetime,
        until: datetime,
        *,
        use_mock: bool | None = None,
    ) -> list[dict]:
        """Fetch records for *bbox* between *since* and *until*.

        When ``use_mock`` is None the global ``USE_MOCK`` flag decides.
        """
        mock = cfg.USE_MOCK if use_mock is None else use_mock
        tag = "MOCK" if mock else "REAL"
        logger.info("[%s] %s pull  %s → %s", self.source_name, tag, since, until)

        if mock:
            return self._pull_mock(bbox, since, until)
        return self._with_retry(bbox, since, until)

    # ── retry wrapper ─────────────────────────────────────────────────
    def _with_retry(
        self,
        bbox: tuple[float, float, float, float],
        since: datetime,
        until: datetime,
        max_retries: int = 3,
        backoff: float = 2.0,
    ) -> list[dict]:
        delay = 1.0
        for attempt in range(1, max_retries + 1):
            try:
                self._throttle()
                return self._pull_real(bbox, since, until)
            except Exception as exc:
                logger.warning(
                    "[%s] attempt %d/%d failed: %s",
                    self.source_name, attempt, max_retries, exc,
                )
                if attempt == max_retries:
                    raise
                time.sleep(delay)
                delay *= backoff
        return []                    # unreachable, keeps type-checker happy

    # ── rate-limit throttle ───────────────────────────────────────────
    def _throttle(self) -> None:
        if self._rate_limit <= 0:
            return
        interval = 1.0 / self._rate_limit
        wait = interval - (time.time() - self._last_req_ts)
        if wait > 0:
            time.sleep(wait)
        self._last_req_ts = time.time()

    # ── subclass hooks ────────────────────────────────────────────────
    @abstractmethod
    def _pull_real(
        self, bbox: tuple[float, float, float, float],
        since: datetime, until: datetime,
    ) -> list[dict]:
        """Hit the real upstream API.  Subclasses must implement."""

    @abstractmethod
    def _pull_mock(
        self, bbox: tuple[float, float, float, float],
        since: datetime, until: datetime,
    ) -> list[dict]:
        """Return deterministic, realistic synthetic records."""
