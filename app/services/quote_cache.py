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


quote_cache = QuoteCache()


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
