from __future__ import annotations

import json
import os
import time
from typing import Any, Callable, Dict, Optional


def _to_float(value: Any, *, field_name: str) -> float:
    try:
        if value is None or value == "":
            raise ValueError(f"missing value for {field_name}")
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid numeric value for {field_name}: {value!r}") from exc


def _to_float_default(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_message(payload: dict | str) -> Dict[str, Any]:
    """Parse raw KIS WS payload into quote snapshot-compatible dict."""
    raw: Dict[str, Any]

    if isinstance(payload, str):
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("payload must be valid JSON string or dict") from exc
        if not isinstance(decoded, dict):
            raise ValueError("decoded payload must be an object")
        raw = decoded
    elif isinstance(payload, dict):
        raw = payload
    else:
        raise ValueError("payload must be dict or JSON string")

    body = raw.get("body")
    nested_output = body.get("output") if isinstance(body, dict) else None
    normalized = {**raw, **nested_output} if isinstance(nested_output, dict) else raw

    symbol = (
        normalized.get("symbol")
        or normalized.get("fid_input_iscd")
        or normalized.get("stck_shrn_iscd")
        or normalized.get("mksc_shrn_iscd")
        or normalized.get("code")
    )
    if not symbol:
        raise ValueError("missing symbol in payload")

    price_raw = normalized.get("price")
    if price_raw is None:
        price_raw = normalized.get("stck_prpr")
    if price_raw is None:
        price_raw = normalized.get("last_price")
    if price_raw is None:
        raise ValueError("missing price in payload")

    now = int(time.time())

    return {
        "symbol": str(symbol),
        "price": _to_float(price_raw, field_name="price"),
        "change_pct": _to_float_default(
            normalized.get("change_pct", normalized.get("prdy_ctrt", normalized.get("chg_rate"))),
            default=0.0,
        ),
        "turnover": _to_float_default(
            normalized.get("turnover", normalized.get("acml_tr_pbmn", normalized.get("acc_trade_value"))),
            default=0.0,
        ),
        "source": str(normalized.get("source", "kis-ws")),
        "ts": int(normalized.get("ts", now)),
        "freshness_sec": float(normalized.get("freshness_sec", 0.0)),
        "state": str(normalized.get("state", "HEALTHY")),
    }


class KisWsClient:
    """KIS websocket client with subscribe and ingest callback flow."""

    _WS_URLS = {
        "mock": "ws://ops.koreainvestment.com:31000",
        "live": "ws://ops.koreainvestment.com:21000",
    }

    def __init__(
        self,
        on_message: Optional[Callable[[Dict[str, Any]], None]] = None,
        *,
        approval_key: str = "",
        approval_key_client: Optional[Any] = None,
        tr_id: str = "H0STCNT0",
        custtype: str = "P",
        tr_type: str = "1",
        content_type: str = "utf-8",
        env: str = "mock",
        websocket_app_factory: Optional[Callable[..., Any]] = None,
        on_state_change: Optional[Callable[..., None]] = None,
    ) -> None:
        self._on_message = on_message
        self.running = False
        self.approval_key = approval_key
        self._approval_key_client = approval_key_client
        self.tr_id = tr_id
        self.custtype = custtype
        self.tr_type = tr_type
        self.content_type = content_type
        self.last_error: str | None = None
        self.reconnect_count = 0
        self.env = env
        self._websocket_app_factory = websocket_app_factory or self._default_websocket_app_factory
        self._on_state_change = on_state_change
        self._first_message_logged = False

    def _emit_state(self, *, connected: bool, heartbeat_ts: int | None = None) -> None:
        if self._on_state_change is None:
            return
        self._on_state_change(
            connected=connected,
            reconnect_count=self.reconnect_count,
            last_error=self.last_error,
            heartbeat_ts=heartbeat_ts,
        )

    @property
    def ws_url(self) -> str:
        if self.env == "live":
            return os.getenv("KIS_WS_URL_LIVE", self._WS_URLS["live"])
        return os.getenv("KIS_WS_URL_MOCK", self._WS_URLS["mock"])

    def _default_websocket_app_factory(self, *args: Any, **kwargs: Any) -> Any:
        from websocket import WebSocketApp

        return WebSocketApp(*args, **kwargs)

    def start(self) -> None:
        self.running = True
        self._emit_state(connected=False)

    def stop(self) -> None:
        self.running = False
        self._first_message_logged = False
        self._emit_state(connected=False)

    def set_on_message(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._on_message = callback

    def ensure_approval_key(self) -> str:
        if self.approval_key:
            return self.approval_key
        if self._approval_key_client is None:
            raise ValueError("approval key client is not configured")

        self.approval_key = str(self._approval_key_client.issue_approval_key())
        return self.approval_key

    def build_subscribe_message(self, symbol: str) -> Dict[str, Any]:
        return {
            "header": {
                "approval_key": self.approval_key,
                "custtype": self.custtype,
                "tr_type": self.tr_type,
                "content-type": self.content_type,
            },
            "body": {
                "input": {
                    "tr_id": self.tr_id,
                    "tr_key": symbol,
                }
            },
        }

    def handle_raw_message(self, payload: dict | str) -> Dict[str, Any]:
        quote = parse_message(payload)
        if self._on_message is not None:
            self._on_message(quote)
        return quote

    def connect_and_subscribe(self, symbols: list[str], *, run_forever: bool = True) -> Any:
        self.ensure_approval_key()
        print(f"[WS][ws_connect] env={self.env} url={self.ws_url} symbols={','.join(symbols)}", flush=True)
        state = {"opened": False}

        def _on_open(ws: Any) -> None:
            state["opened"] = True
            print("[WS][ws_connect_result] status=open", flush=True)
            self._emit_state(connected=True, heartbeat_ts=int(time.time()))
            for symbol in symbols:
                message = self.build_subscribe_message(symbol)
                ws.send(json.dumps(message))
                print(f"[WS][ws_subscribe] symbol={symbol}", flush=True)

        def _on_message(_: Any, raw_message: Any) -> None:
            if not self._first_message_logged:
                print("[WS][ws_first_message] received=1", flush=True)
                self._first_message_logged = True
            try:
                self.handle_raw_message(raw_message)
            except ValueError as exc:
                # KIS ACK/heartbeat/control messages may not include quote fields.
                print(f"[WS][ws_message_skip] reason={exc}", flush=True)

        def _on_error(_: Any, error: Any) -> None:
            self.last_error = str(error)
            print(f"[WS][ws_error] {self.last_error}", flush=True)
            self._emit_state(connected=False)

        def _on_close(_: Any, code: Any, reason: Any) -> None:
            print(f"[WS][ws_close] code={code} reason={reason}", flush=True)
            self._emit_state(connected=False)

        ws_app = self._websocket_app_factory(
            self.ws_url,
            on_open=_on_open,
            on_message=_on_message,
            on_error=_on_error,
            on_close=_on_close,
        )

        if run_forever:
            ws_app.run_forever()
            if not state["opened"]:
                raise RuntimeError("ws_open_not_confirmed")

        return ws_app

    def run_with_reconnect(
        self,
        *,
        connect_once: Callable[[], None],
        sleep_fn: Callable[[float], None] = time.sleep,
        max_retries: int = 5,
        backoff_base_sec: float = 1.0,
        backoff_cap_sec: float = 30.0,
    ) -> bool:
        """Run connect loop with exponential backoff. Returns True on success."""
        if max_retries < 1:
            return False

        self.running = True
        self.last_error = None
        self.reconnect_count = 0
        self._emit_state(connected=False)

        for attempt in range(max_retries):
            if not self.running:
                return False

            try:
                connect_once()
                self.last_error = None
                self._emit_state(connected=True, heartbeat_ts=int(time.time()))
                return True
            except Exception as exc:
                self.last_error = str(exc)
                self.reconnect_count += 1
                self._emit_state(connected=False)

                if not self.running:
                    return False

                if attempt == max_retries - 1:
                    break

                backoff = min(backoff_base_sec * (2**attempt), backoff_cap_sec)
                sleep_fn(backoff)

        return False
