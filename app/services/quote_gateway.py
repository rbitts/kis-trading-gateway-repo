from __future__ import annotations

import time
from typing import Callable

from app.schemas.quote import QuoteSnapshot
from app.services.market_hours import is_market_open
from app.services.quote_cache import QuoteCache


class QuoteGatewayService:
    """WS-first quote source selector with REST fallback."""

    def __init__(
        self,
        *,
        quote_cache: QuoteCache,
        rest_client,
        market_open_checker: Callable | None = None,
        stale_after_sec: int = 5,
    ) -> None:
        self.quote_cache = quote_cache
        self.rest_client = rest_client
        self.market_open_checker = market_open_checker or is_market_open
        self.stale_after_sec = stale_after_sec
        self.rest_fallbacks = 0

    def _is_fresh(self, snapshot: QuoteSnapshot, now: int) -> bool:
        age = float(max(now - snapshot.ts, 0))
        snapshot.freshness_sec = age
        snapshot.state = "HEALTHY" if age <= self.stale_after_sec else "STALE"
        return age <= self.stale_after_sec

    def _fetch_rest(self, symbol: str) -> QuoteSnapshot:
        self.rest_fallbacks += 1
        payload = self.rest_client.get_quote(symbol)
        now = int(time.time())
        return QuoteSnapshot(
            symbol=str(payload["symbol"]),
            price=float(payload["price"]),
            change_pct=float(payload.get("change_pct", 0.0)),
            turnover=float(payload.get("turnover", 0.0)),
            source=str(payload.get("source", "kis-rest")),
            ts=int(payload.get("ts", now)),
            freshness_sec=0.0,
            state="HEALTHY",
        )

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        now = int(time.time())
        if self.market_open_checker():
            cached = self.quote_cache.get(symbol)
            if cached is not None and self._is_fresh(cached, now):
                return cached
            return self._fetch_rest(symbol)
        return self._fetch_rest(symbol)

    def metrics(self) -> dict[str, int]:
        return {"rest_fallbacks": self.rest_fallbacks}
