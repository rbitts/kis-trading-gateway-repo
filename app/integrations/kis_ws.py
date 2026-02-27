from __future__ import annotations

import json
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

    symbol = (
        raw.get("symbol")
        or raw.get("fid_input_iscd")
        or raw.get("stck_shrn_iscd")
        or raw.get("code")
    )
    if not symbol:
        raise ValueError("missing symbol in payload")

    price_raw = raw.get("price")
    if price_raw is None:
        price_raw = raw.get("stck_prpr")
    if price_raw is None:
        price_raw = raw.get("last_price")
    if price_raw is None:
        raise ValueError("missing price in payload")

    now = int(time.time())

    return {
        "symbol": str(symbol),
        "price": _to_float(price_raw, field_name="price"),
        "change_pct": _to_float_default(
            raw.get("change_pct", raw.get("prdy_ctrt", raw.get("chg_rate"))),
            default=0.0,
        ),
        "turnover": _to_float_default(
            raw.get("turnover", raw.get("acml_tr_pbmn", raw.get("acc_trade_value"))),
            default=0.0,
        ),
        "source": str(raw.get("source", "kis-ws")),
        "ts": int(raw.get("ts", now)),
        "freshness_sec": float(raw.get("freshness_sec", 0.0)),
        "state": str(raw.get("state", "HEALTHY")),
    }


class KisWsClient:
    """KIS websocket client skeleton (network connection intentionally omitted)."""

    def __init__(self, on_message: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        self._on_message = on_message
        self.running = False

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def set_on_message(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._on_message = callback

    def handle_raw_message(self, payload: dict | str) -> Dict[str, Any]:
        quote = parse_message(payload)
        if self._on_message is not None:
            self._on_message(quote)
        return quote
