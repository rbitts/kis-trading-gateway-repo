from __future__ import annotations

import time

from app.schemas.quote import QuoteSnapshot


class QuoteCache:
    def __init__(self) -> None:
        self._rows: dict[str, QuoteSnapshot] = {}

    def upsert(self, snapshot: QuoteSnapshot) -> None:
        self._rows[snapshot.symbol] = snapshot

    def get(self, symbol: str) -> QuoteSnapshot | None:
        return self._rows.get(symbol)

    def list_many(self, symbols: list[str]) -> list[QuoteSnapshot]:
        out: list[QuoteSnapshot] = []
        for s in symbols:
            row = self.get(s)
            if row:
                out.append(row)
        return out

    def list_all(self) -> list[QuoteSnapshot]:
        return list(self._rows.values())


class QuoteIngestWorker:
    """MVP skeleton: websocket payload hook -> cache update + freshness calc."""

    def __init__(self, cache: QuoteCache, stale_after_sec: int = 5) -> None:
        self.cache = cache
        self.stale_after_sec = stale_after_sec
        self.ws_messages = 0
        self.upserts = 0

    def on_ws_message(self, payload: dict) -> QuoteSnapshot:
        now = int(time.time())
        snapshot = QuoteSnapshot(
            symbol=payload["symbol"],
            price=float(payload["price"]),
            change_pct=float(payload.get("change_pct", 0.0)),
            turnover=float(payload.get("turnover", 0.0)),
            source=str(payload.get("source", "ws")),
            ts=int(payload.get("ts", now)),
            freshness_sec=0.0,
            state="HEALTHY",
        )
        self.cache.upsert(snapshot)
        self.ws_messages += 1
        self.upserts += 1
        return snapshot

    def refresh_freshness(self, now: int | None = None) -> None:
        ref = int(time.time()) if now is None else now
        for row in self.cache.list_all():
            age = float(max(ref - row.ts, 0))
            row.freshness_sec = age
            row.state = "HEALTHY" if age <= self.stale_after_sec else "STALE"

    def metrics(self) -> dict:
        self.refresh_freshness()
        rows = self.cache.list_all()
        stale = sum(1 for r in rows if r.state == "STALE")
        return {
            "cached_symbols": len(rows),
            "ws_messages": self.ws_messages,
            "upserts": self.upserts,
            "stale_symbols": stale,
        }


quote_cache = QuoteCache()
quote_ingest_worker = QuoteIngestWorker(quote_cache)


def seed_demo_quote(symbol: str) -> None:
    now = int(time.time())
    quote_cache.upsert(
        QuoteSnapshot(
            symbol=symbol,
            price=70000.0,
            change_pct=0.0,
            turnover=0.0,
            source="demo",
            ts=now,
            freshness_sec=0.0,
            state="HEALTHY",
        )
    )
