from __future__ import annotations

import time
from typing import Callable

from app.errors import RestRateLimitCooldownError
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
        rest_cooldown_sec: int = 3,
    ) -> None:
        self.quote_cache = quote_cache
        self.rest_client = rest_client
        self.market_open_checker = market_open_checker or is_market_open
        self.stale_after_sec = stale_after_sec
        self.rest_cooldown_sec = rest_cooldown_sec
        self.rest_fallbacks = 0
        self._rest_symbol_cooldown_until: dict[str, int] = {}

    def _is_fresh(self, snapshot: QuoteSnapshot, now: int) -> bool:
        age = float(max(now - snapshot.ts, 0))
        snapshot.freshness_sec = age
        snapshot.state = "HEALTHY" if age <= self.stale_after_sec else "STALE"
        return age <= self.stale_after_sec

    def _prune_expired_cooldowns(self, now: int) -> None:
        expired = [s for s, until in self._rest_symbol_cooldown_until.items() if until <= now]
        for s in expired:
            self._rest_symbol_cooldown_until.pop(s, None)

    def _is_symbol_cooldown(self, symbol: str, now: int) -> bool:
        until = self._rest_symbol_cooldown_until.get(symbol, 0)
        return now < until

    def _mark_symbol_cooldown(self, symbol: str, now: int) -> None:
        self._rest_symbol_cooldown_until[symbol] = now + self.rest_cooldown_sec

    @staticmethod
    def _status_code_from_error(exc: Exception) -> int | None:
        response = getattr(exc, "response", None)
        code = getattr(response, "status_code", None)
        if isinstance(code, int):
            return code
        return None

    def _fetch_rest(self, symbol: str, now: int) -> QuoteSnapshot:
        self.rest_fallbacks += 1
        try:
            payload = self.rest_client.get_quote(symbol)
        except Exception as exc:
            if self._status_code_from_error(exc) == 429:
                self._mark_symbol_cooldown(symbol, now)
                cached = self.quote_cache.get(symbol)
                if cached is not None:
                    self._is_fresh(cached, now)
                    return cached
                raise RestRateLimitCooldownError("REST_RATE_LIMIT_COOLDOWN") from exc
            raise
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
        self._prune_expired_cooldowns(now)
        if self._is_symbol_cooldown(symbol, now):
            cached = self.quote_cache.get(symbol)
            if cached is not None:
                self._is_fresh(cached, now)
                return cached
            raise RestRateLimitCooldownError("REST_RATE_LIMIT_COOLDOWN")

        if self.market_open_checker():
            cached = self.quote_cache.get(symbol)
            if cached is not None and self._is_fresh(cached, now):
                return cached
            return self._fetch_rest(symbol, now)
        return self._fetch_rest(symbol, now)

    def metrics(self) -> dict[str, int]:
        return {"rest_fallbacks": self.rest_fallbacks}
