from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests


class KisRestClient:
    """Minimal KIS REST quote client with token issuance and quote retrieval."""

    _BASE_URLS = {
        "mock": "https://openapivts.koreainvestment.com:29443",
        "live": "https://openapi.koreainvestment.com:9443",
    }

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        env: str = "mock",
        session: Optional[Any] = None,
        base_url: Optional[str] = None,
    ) -> None:
        if env not in self._BASE_URLS and base_url is None:
            raise ValueError("env must be one of: mock, live")

        self.app_key = app_key
        self.app_secret = app_secret
        self.env = env
        self.base_url = base_url or self._BASE_URLS[env]
        self.session = session or requests
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def _issue_token(self) -> str:
        response = self.session.post(
            f"{self.base_url}/oauth2/tokenP",
            headers={"content-type": "application/json; charset=utf-8"},
            json={
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
            },
            timeout=5,
        )
        response.raise_for_status()
        payload = response.json()

        token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 3600))
        self._access_token = token

        issued_at = time.time()
        # refresh a bit earlier, but cache briefly even for very short TTL tokens
        refresh_ttl = max(expires_in - 30, min(expires_in, 1))
        self._token_expires_at = issued_at + refresh_ttl
        return token


    def issue_approval_key(self) -> str:
        response = self.session.post(
            f"{self.base_url}/oauth2/Approval",
            headers={"content-type": "application/json; charset=utf-8"},
            json={
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "secretkey": self.app_secret,
            },
            timeout=5,
        )
        response.raise_for_status()
        payload = response.json()

        approval_key = payload.get("approval_key")
        if not approval_key:
            raise ValueError("missing approval_key in response")
        return str(approval_key)

    def get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        return self._issue_token()

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None or value == "":
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        token = self.get_access_token()

        response = self.session.get(
            f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price",
            headers={
                "authorization": f"Bearer {token}",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
                "tr_id": "FHKST01010100",
            },
            params={"fid_cond_mrkt_div_code": "J", "fid_input_iscd": symbol},
            timeout=5,
        )
        response.raise_for_status()
        payload = response.json()
        output = payload.get("output", {})

        return {
            "symbol": symbol,
            "price": self._to_float(output.get("stck_prpr")),
            "change_pct": self._to_float(output.get("prdy_ctrt")),
            "turnover": self._to_float(output.get("acml_tr_pbmn")),
            "source": "kis-rest",
            "ts": int(time.time()),
        }
