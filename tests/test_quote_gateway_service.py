import time
import unittest

from app.schemas.quote import QuoteSnapshot
from app.services.quote_cache import QuoteCache
from app.services.quote_gateway import QuoteGatewayService


class StubRestClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0

    def get_quote(self, symbol: str) -> dict:
        self.calls += 1
        data = dict(self.payload)
        data["symbol"] = symbol
        return data


class RateLimitRestClient:
    def __init__(self) -> None:
        self.calls = 0

    def get_quote(self, symbol: str) -> dict:
        self.calls += 1

        class Response:
            status_code = 429

        class RateLimitError(Exception):
            def __init__(self):
                self.response = Response()

        raise RateLimitError()


class QuoteGatewayServiceTest(unittest.TestCase):
    def test_market_open_with_fresh_ws_cache_uses_ws(self):
        cache = QuoteCache()
        cache.upsert(
            QuoteSnapshot(
                symbol="005930",
                price=71000.0,
                change_pct=0.1,
                turnover=100.0,
                source="kis-ws",
                ts=int(time.time()),
                freshness_sec=0.0,
                state="HEALTHY",
            )
        )
        rest_client = StubRestClient({"price": 70000.0, "source": "kis-rest", "ts": int(time.time())})
        service = QuoteGatewayService(
            quote_cache=cache,
            rest_client=rest_client,
            market_open_checker=lambda: True,
            stale_after_sec=5,
        )

        quote = service.get_quote("005930")

        self.assertEqual(quote.source, "kis-ws")
        self.assertEqual(rest_client.calls, 0)
        self.assertEqual(service.metrics()["rest_fallbacks"], 0)

    def test_market_open_with_stale_ws_cache_falls_back_to_rest(self):
        cache = QuoteCache()
        cache.upsert(
            QuoteSnapshot(
                symbol="005930",
                price=71000.0,
                change_pct=0.1,
                turnover=100.0,
                source="kis-ws",
                ts=int(time.time()) - 10,
                freshness_sec=0.0,
                state="HEALTHY",
            )
        )
        rest_client = StubRestClient({
            "price": 70900.0,
            "change_pct": 0.05,
            "turnover": 110.0,
            "source": "kis-rest",
            "ts": int(time.time()),
        })
        service = QuoteGatewayService(
            quote_cache=cache,
            rest_client=rest_client,
            market_open_checker=lambda: True,
            stale_after_sec=5,
        )

        quote = service.get_quote("005930")

        self.assertEqual(quote.source, "kis-rest")
        self.assertEqual(rest_client.calls, 1)
        self.assertEqual(service.metrics()["rest_fallbacks"], 1)

    def test_market_closed_uses_rest(self):
        cache = QuoteCache()
        rest_client = StubRestClient({
            "price": 70500.0,
            "change_pct": -0.2,
            "turnover": 80.0,
            "source": "kis-rest",
            "ts": int(time.time()),
        })
        service = QuoteGatewayService(
            quote_cache=cache,
            rest_client=rest_client,
            market_open_checker=lambda: False,
            stale_after_sec=5,
        )

        quote = service.get_quote("005930")

        self.assertEqual(quote.source, "kis-rest")
        self.assertEqual(rest_client.calls, 1)
        self.assertEqual(service.metrics()["rest_fallbacks"], 1)

    def test_rate_limit_cooldown_suppresses_repeated_fallback_same_symbol(self):
        cache = QuoteCache()
        stale_ts = int(time.time()) - 20
        cache.upsert(
            QuoteSnapshot(
                symbol="005930",
                price=70000.0,
                change_pct=0.0,
                turnover=10.0,
                source="kis-ws",
                ts=stale_ts,
                freshness_sec=0.0,
                state="STALE",
            )
        )
        rest_client = RateLimitRestClient()
        service = QuoteGatewayService(
            quote_cache=cache,
            rest_client=rest_client,
            market_open_checker=lambda: True,
            stale_after_sec=5,
        )

        quote1 = service.get_quote("005930")
        quote2 = service.get_quote("005930")

        self.assertEqual(rest_client.calls, 1)
        self.assertEqual(quote1.source, "kis-ws")
        self.assertEqual(quote2.source, "kis-ws")

    def test_rate_limit_without_cache_raises_cooldown_error(self):
        cache = QuoteCache()
        rest_client = RateLimitRestClient()
        service = QuoteGatewayService(
            quote_cache=cache,
            rest_client=rest_client,
            market_open_checker=lambda: False,
            stale_after_sec=5,
        )

        with self.assertRaises(RuntimeError):
            service.get_quote("000660")

        with self.assertRaises(RuntimeError):
            service.get_quote("000660")

        self.assertEqual(rest_client.calls, 1)


if __name__ == "__main__":
    unittest.main()
