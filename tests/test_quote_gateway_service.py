import time
import unittest

from app.schemas.quote import QuoteSnapshot
from app.services.quote_cache import QuoteCache
from app.errors import RestRateLimitCooldownError
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


class TimeoutOnceRestClient:
    def __init__(self, payload: dict, timeout_symbols: set[str]) -> None:
        self.payload = payload
        self.timeout_symbols = timeout_symbols
        self.calls = 0

    def get_quote(self, symbol: str) -> dict:
        self.calls += 1
        if symbol in self.timeout_symbols:
            raise TimeoutError(f"timeout:{symbol}")
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


class RetryThenSuccessRestClient:
    def __init__(self, payload: dict, fail_once_symbols: set[str]) -> None:
        self.payload = payload
        self.fail_once_symbols = set(fail_once_symbols)
        self.calls_by_symbol: dict[str, int] = {}

    def get_quote(self, symbol: str) -> dict:
        self.calls_by_symbol[symbol] = self.calls_by_symbol.get(symbol, 0) + 1
        if symbol in self.fail_once_symbols and self.calls_by_symbol[symbol] == 1:
            raise TimeoutError(f"timeout:{symbol}")
        data = dict(self.payload)
        data["symbol"] = symbol
        return data


class AlwaysFailRestClient:
    def __init__(self) -> None:
        self.calls_by_symbol: dict[str, int] = {}

    def get_quote(self, symbol: str) -> dict:
        self.calls_by_symbol[symbol] = self.calls_by_symbol.get(symbol, 0) + 1
        raise TimeoutError(f"timeout:{symbol}")


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

        with self.assertRaises(RestRateLimitCooldownError):
            service.get_quote("000660")

        with self.assertRaises(RestRateLimitCooldownError):
            service.get_quote("000660")

        self.assertEqual(rest_client.calls, 1)

    def test_prunes_expired_symbol_cooldown_entries(self):
        cache = QuoteCache()
        rest_client = StubRestClient({"price": 70500.0, "source": "kis-rest", "ts": int(time.time())})
        service = QuoteGatewayService(
            quote_cache=cache,
            rest_client=rest_client,
            market_open_checker=lambda: False,
            stale_after_sec=5,
        )
        now = int(time.time())
        service._rest_symbol_cooldown_until = {"005930": now - 1, "000660": now + 10}

        service.get_quote("005930")

        self.assertNotIn("005930", service._rest_symbol_cooldown_until)
        self.assertIn("000660", service._rest_symbol_cooldown_until)

    def test_offhours_partial_ws_fills_to_target_with_rest(self):
        cache = QuoteCache()
        now = int(time.time())
        cache.upsert(
            QuoteSnapshot(
                symbol="005930",
                price=71000.0,
                change_pct=0.1,
                turnover=100.0,
                source="kis-ws",
                ts=now,
                freshness_sec=0.0,
                state="HEALTHY",
            )
        )
        cache.upsert(
            QuoteSnapshot(
                symbol="000660",
                price=120000.0,
                change_pct=0.3,
                turnover=200.0,
                source="kis-ws",
                ts=now,
                freshness_sec=0.0,
                state="HEALTHY",
            )
        )
        rest_client = StubRestClient({"price": 70000.0, "source": "kis-rest", "ts": now})
        service = QuoteGatewayService(
            quote_cache=cache,
            rest_client=rest_client,
            market_open_checker=lambda: False,
            stale_after_sec=5,
        )

        symbols = ["005930", "000660", "035420", "051910", "068270", "105560"]
        quotes, meta = service.get_quotes(symbols)

        self.assertEqual(len(quotes), 6)
        self.assertEqual(meta.missing_count, 0)
        self.assertEqual(meta.failed_symbols, [])
        self.assertEqual(service.metrics()["ws_count"], 2)
        self.assertEqual(service.metrics()["rest_filled_count"], 4)
        self.assertEqual(service.metrics()["batch_target_count"], 6)
        self.assertEqual(service.metrics()["batch_final_count"], 6)
        self.assertEqual(service.metrics()["fallback_triggered"], 1)

    def test_offhours_rest_timeout_keeps_partial_but_no_crash(self):
        cache = QuoteCache()
        now = int(time.time())
        cache.upsert(
            QuoteSnapshot(
                symbol="005930",
                price=71000.0,
                change_pct=0.1,
                turnover=100.0,
                source="kis-ws",
                ts=now,
                freshness_sec=0.0,
                state="HEALTHY",
            )
        )
        rest_client = TimeoutOnceRestClient(
            payload={"price": 70000.0, "source": "kis-rest", "ts": now},
            timeout_symbols={"051910"},
        )
        service = QuoteGatewayService(
            quote_cache=cache,
            rest_client=rest_client,
            market_open_checker=lambda: False,
            stale_after_sec=5,
        )

        symbols = ["005930", "000660", "035420", "051910", "068270", "105560"]
        quotes, meta = service.get_quotes(symbols)

        self.assertEqual(len(quotes), 5)
        self.assertEqual(meta.missing_count, 1)
        self.assertEqual(meta.failed_symbols, ["051910"])
        self.assertEqual(service.metrics()["batch_target_count"], 6)
        self.assertEqual(service.metrics()["batch_final_count"], 5)
        self.assertEqual(service.metrics()["rest_filled_count"], 4)

    def test_batch_retry_then_success_fills_target_count(self):
        cache = QuoteCache()
        now = int(time.time())
        rest_client = RetryThenSuccessRestClient(
            payload={"price": 70000.0, "source": "kis-rest", "ts": now},
            fail_once_symbols={"000660", "051910"},
        )
        service = QuoteGatewayService(
            quote_cache=cache,
            rest_client=rest_client,
            market_open_checker=lambda: False,
            stale_after_sec=5,
            rest_retry_attempts=3,
            rest_backoff_base_sec=0.01,
            symbol_delay_min_sec=0.0,
            symbol_delay_max_sec=0.0,
        )

        symbols = ["005930", "000660", "035420", "051910", "068270", "105560"]
        quotes, meta = service.get_quotes(symbols)

        self.assertEqual(len(quotes), 6)
        self.assertEqual(meta.failed_symbols, [])
        self.assertEqual(meta.missing_count, 0)
        self.assertEqual(rest_client.calls_by_symbol["000660"], 2)
        self.assertEqual(rest_client.calls_by_symbol["051910"], 2)

    def test_batch_cooldown_reuses_last_good_quote_after_retries_exhausted(self):
        cache = QuoteCache()
        now = int(time.time())
        cache.upsert(
            QuoteSnapshot(
                symbol="051910",
                price=401000.0,
                change_pct=0.2,
                turnover=50.0,
                source="kis-ws",
                ts=now - 20,
                freshness_sec=0.0,
                state="STALE",
            )
        )
        rest_client = AlwaysFailRestClient()
        service = QuoteGatewayService(
            quote_cache=cache,
            rest_client=rest_client,
            market_open_checker=lambda: False,
            stale_after_sec=5,
            rest_cooldown_sec=60,
            rest_retry_attempts=2,
            rest_backoff_base_sec=0.01,
            symbol_delay_min_sec=0.0,
            symbol_delay_max_sec=0.0,
        )

        quotes1, meta1 = service.get_quotes(["051910"])
        quotes2, meta2 = service.get_quotes(["051910"])

        self.assertEqual(len(quotes1), 1)
        self.assertEqual(len(quotes2), 1)
        self.assertEqual(quotes1[0].source, "kis-ws")
        self.assertEqual(quotes2[0].source, "kis-ws")
        self.assertEqual(meta1.missing_count, 0)
        self.assertEqual(meta2.missing_count, 0)
        self.assertEqual(rest_client.calls_by_symbol["051910"], 2)


if __name__ == "__main__":
    unittest.main()
