import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.quote_cache import quote_cache, quote_ingest_worker
from app.services.quote_gateway import QuoteGatewayService


class StubRestClient:
    def __init__(self) -> None:
        self.calls = 0

    def get_quote(self, symbol: str) -> dict:
        self.calls += 1
        return {
            "symbol": symbol,
            "price": 69900.0,
            "change_pct": -0.15,
            "turnover": 150.0,
            "source": "kis-rest",
            "ts": 1700000100,
        }


class QuoteE2EMockKisTest(unittest.TestCase):
    def setUp(self):
        quote_cache._rows.clear()
        quote_ingest_worker.ws_messages = 0
        quote_ingest_worker.upserts = 0
        quote_ingest_worker.ws_connected = False
        quote_ingest_worker.last_ws_message_ts = None

    def _make_client_with_service(self, market_open_checker):
        rest_client = StubRestClient()
        app.state.quote_gateway_service = QuoteGatewayService(
            quote_cache=quote_cache,
            rest_client=rest_client,
            market_open_checker=market_open_checker,
            stale_after_sec=5,
        )
        return TestClient(app), rest_client

    def test_market_open_with_fresh_ws_path_returns_ws_quote(self):
        client, rest_client = self._make_client_with_service(lambda: True)

        with patch("app.services.quote_cache.time.time", return_value=1700000100), patch(
            "app.services.quote_gateway.time.time", return_value=1700000100
        ):
            quote_ingest_worker.on_ws_message(
                {
                    "symbol": "005930",
                    "price": 72100,
                    "change_pct": 0.3,
                    "turnover": 250.0,
                    "source": "kis-ws",
                    "ts": 1700000098,
                }
            )
            response = client.get("/v1/quotes/005930")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["symbol"], "005930")
        self.assertEqual(payload["source"], "kis-ws")
        self.assertEqual(payload["price"], 72100.0)
        self.assertEqual(rest_client.calls, 0)
        self.assertEqual(app.state.quote_gateway_service.metrics()["rest_fallbacks"], 0)

    def test_market_open_with_stale_or_missing_ws_falls_back_to_rest(self):
        client, rest_client = self._make_client_with_service(lambda: True)

        with patch("app.services.quote_cache.time.time", return_value=1700000100), patch(
            "app.services.quote_gateway.time.time", return_value=1700000100
        ):
            quote_ingest_worker.on_ws_message(
                {
                    "symbol": "005930",
                    "price": 72100,
                    "source": "kis-ws",
                    "ts": 1700000000,
                }
            )
            stale_res = client.get("/v1/quotes/005930")
            missing_res = client.get("/v1/quotes/000660")

        self.assertEqual(stale_res.status_code, 200)
        self.assertEqual(stale_res.json()["source"], "kis-rest")
        self.assertEqual(missing_res.status_code, 200)
        self.assertEqual(missing_res.json()["source"], "kis-rest")
        self.assertEqual(rest_client.calls, 2)
        self.assertEqual(app.state.quote_gateway_service.metrics()["rest_fallbacks"], 2)

    def test_market_closed_uses_rest_even_with_fresh_ws_cache(self):
        client, rest_client = self._make_client_with_service(lambda: False)

        with patch("app.services.quote_cache.time.time", return_value=1700000100), patch(
            "app.services.quote_gateway.time.time", return_value=1700000100
        ):
            quote_ingest_worker.on_ws_message(
                {
                    "symbol": "005930",
                    "price": 72200,
                    "source": "kis-ws",
                    "ts": 1700000099,
                }
            )
            response = client.get("/v1/quotes/005930")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "kis-rest")
        self.assertEqual(payload["price"], 69900.0)
        self.assertEqual(rest_client.calls, 1)
        self.assertEqual(app.state.quote_gateway_service.metrics()["rest_fallbacks"], 1)


if __name__ == "__main__":
    unittest.main()
