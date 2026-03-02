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

    def __init__(
        self,
        cache: QuoteCache,
        stale_after_sec: int = 5,
        ws_heartbeat_timeout_sec: int = 10,
        auto_sync_ws_state: bool = False,
    ) -> None:
        self.cache = cache
        self.stale_after_sec = stale_after_sec
        self.ws_heartbeat_timeout_sec = ws_heartbeat_timeout_sec
        self.ws_messages = 0
        self.upserts = 0
        self.ws_connected = False
        self.last_ws_message_ts: int | None = None
        self.last_ws_heartbeat_ts: int | None = None
        self.ws_last_error: str | None = None
        self.ws_reconnect_count = 0
        self.auto_sync_ws_state = auto_sync_ws_state

    def on_ws_message(self, payload: dict) -> QuoteSnapshot:
        now = int(time.time())
        snapshot = QuoteSnapshot(
            symbol=payload["symbol"],
            symbol_name=str(payload.get("symbol_name") or "").strip() or None,
            price=float(payload["price"]),
            change_pct=float(payload.get("change_pct", 0.0)),
            turnover=float(payload.get("turnover", 0.0)),
            source=str(payload.get("source", "kis-ws")),
            ts=int(payload.get("ts", now)),
            freshness_sec=0.0,
            state="HEALTHY",
        )
        self.cache.upsert(snapshot)
        self.ws_messages += 1
        self.upserts += 1
        self.ws_connected = True
        self.last_ws_message_ts = snapshot.ts
        self.last_ws_heartbeat_ts = now
        return snapshot

    def sync_ws_state(
        self,
        *,
        connected: bool,
        reconnect_count: int,
        last_error: str | None,
        heartbeat_ts: int | None = None,
    ) -> None:
        self.ws_connected = bool(connected)
        self.ws_reconnect_count = int(reconnect_count)
        self.ws_last_error = last_error
        if heartbeat_ts is not None:
            self.last_ws_heartbeat_ts = int(heartbeat_ts)

    def _sync_from_app_ws_client(self) -> None:
        try:
            from app.main import app

            ws_client = getattr(app.state, "ws_client", None)
            if ws_client is None:
                return
            self.ws_reconnect_count = int(getattr(ws_client, "reconnect_count", 0))
            self.ws_last_error = getattr(ws_client, "last_error", None)
        except Exception:
            return

    def refresh_freshness(self, now: int | None = None) -> None:
        ref = int(time.time()) if now is None else now
        for row in self.cache.list_all():
            age = float(max(ref - row.ts, 0))
            row.freshness_sec = age
            row.state = "HEALTHY" if age <= self.stale_after_sec else "STALE"

    def metrics(self, now: int | None = None) -> dict:
        if self.auto_sync_ws_state:
            self._sync_from_app_ws_client()
        ref = int(time.time()) if now is None else now
        self.refresh_freshness(now=ref)
        rows = self.cache.list_all()
        stale = sum(1 for r in rows if r.state == "STALE")

        heartbeat_fresh = False
        if self.last_ws_heartbeat_ts is not None:
            heartbeat_fresh = (ref - self.last_ws_heartbeat_ts) <= self.ws_heartbeat_timeout_sec

        return {
            "cached_symbols": len(rows),
            "ws_messages": self.ws_messages,
            "upserts": self.upserts,
            "stale_symbols": stale,
            "ws_connected": self.ws_connected,
            "ws_heartbeat_fresh": heartbeat_fresh,
            "last_ws_message_ts": self.last_ws_message_ts,
            "last_ws_heartbeat_ts": self.last_ws_heartbeat_ts,
            "ws_last_error": self.ws_last_error,
            "ws_reconnect_count": self.ws_reconnect_count,
        }


quote_cache = QuoteCache()
quote_ingest_worker = QuoteIngestWorker(quote_cache, auto_sync_ws_state=True)


def seed_demo_quote(symbol: str) -> None:
    now = int(time.time())
    quote_cache.upsert(
        QuoteSnapshot(
            symbol=symbol,
            symbol_name=None,
            price=70000.0,
            change_pct=0.0,
            turnover=0.0,
            source="demo",
            ts=now,
            freshness_sec=0.0,
            state="HEALTHY",
        )
    )
