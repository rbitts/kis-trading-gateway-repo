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

        self.fallback_triggered = 0
        self.rest_filled_count = 0
        self.ws_count = 0
        self.last_batch_target = 0
        self.last_batch_final = 0
        self.last_batch_market_open = True

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

    def _get_cached_ws(self, symbol: str, now: int) -> QuoteSnapshot | None:
        cached = self.quote_cache.get(symbol)
        if cached is None:
            return None
        if self._is_fresh(cached, now):
            return cached
        return None

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

    def get_quotes(self, symbols: list[str]) -> list[QuoteSnapshot]:
        now = int(time.time())
        self._prune_expired_cooldowns(now)

        unique_symbols: list[str] = []
        seen: set[str] = set()
        for symbol in symbols:
            value = str(symbol).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            unique_symbols.append(value)

        market_open = self.market_open_checker()
        ws_rows: dict[str, QuoteSnapshot] = {}
        for symbol in unique_symbols:
            cached = self._get_cached_ws(symbol, now)
            if cached is not None:
                ws_rows[symbol] = cached

        target_count = len(unique_symbols)
        ws_count = len(ws_rows)
        rest_filled_count = 0
        fallback_triggered = (not market_open) or (ws_count < target_count)

        out: list[QuoteSnapshot] = []
        for symbol in unique_symbols:
            if symbol in ws_rows:
                out.append(ws_rows[symbol])
                continue

            if self._is_symbol_cooldown(symbol, now):
                cached = self.quote_cache.get(symbol)
                if cached is not None:
                    self._is_fresh(cached, now)
                    out.append(cached)
                continue

            try:
                quote = self._fetch_rest(symbol, now)
                out.append(quote)
                rest_filled_count += 1
            except RestRateLimitCooldownError:
                continue
            except Exception as exc:
                print(
                    f"[QUOTE][rest_fallback_error] symbol={symbol} error={exc}",
                    flush=True,
                )
                continue

        self.ws_count = ws_count
        self.rest_filled_count = rest_filled_count
        self.last_batch_target = target_count
        self.last_batch_final = len(out)
        self.last_batch_market_open = market_open
        if fallback_triggered:
            self.fallback_triggered += 1

        print(
            "[QUOTE][batch_resolve] "
            f"market_open={market_open} target_count={target_count} ws_count={ws_count} "
            f"rest_filled_count={rest_filled_count} final_count={len(out)} "
            f"fallback_triggered={int(fallback_triggered)}",
            flush=True,
        )

        return out

    def metrics(self) -> dict[str, int | bool]:
        return {
            "rest_fallbacks": self.rest_fallbacks,
            "fallback_triggered": self.fallback_triggered,
            "rest_filled_count": self.rest_filled_count,
            "ws_count": self.ws_count,
            "batch_target_count": self.last_batch_target,
            "batch_final_count": self.last_batch_final,
            "batch_market_open": self.last_batch_market_open,
        }
