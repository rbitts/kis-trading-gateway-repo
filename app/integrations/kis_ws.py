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
    """KIS websocket client skeleton (network connection intentionally omitted)."""

    def __init__(
        self,
        on_message: Optional[Callable[[Dict[str, Any]], None]] = None,
        *,
        approval_key: str = "",
        tr_id: str = "H0STCNT0",
        custtype: str = "P",
        tr_type: str = "1",
        content_type: str = "utf-8",
    ) -> None:
        self._on_message = on_message
        self.running = False
        self.approval_key = approval_key
        self.tr_id = tr_id
        self.custtype = custtype
        self.tr_type = tr_type
        self.content_type = content_type
        self.last_error: str | None = None
        self.reconnect_count = 0

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def set_on_message(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._on_message = callback

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

        for attempt in range(max_retries):
            if not self.running:
                return False

            try:
                connect_once()
                self.last_error = None
                return True
            except Exception as exc:
                self.last_error = str(exc)
                self.reconnect_count += 1

                if not self.running:
                    return False

                backoff = min(backoff_base_sec * (2**attempt), backoff_cap_sec)
                sleep_fn(backoff)

        return False
