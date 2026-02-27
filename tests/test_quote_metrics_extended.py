import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.services.quote_cache import quote_cache, quote_ingest_worker


class QuoteMetricsExtendedTest(unittest.TestCase):
    def setUp(self):
        quote_cache._rows.clear()
        quote_ingest_worker.ws_messages = 0
        quote_ingest_worker.upserts = 0
        quote_ingest_worker.ws_connected = False
        quote_ingest_worker.last_ws_message_ts = None
        quote_ingest_worker.last_ws_heartbeat_ts = None

        app.state.quote_gateway_service.rest_fallbacks = 0
        app.state.quote_gateway_service.market_open_checker = lambda: False
        self.client = TestClient(app)

    def test_quote_metrics_contains_operational_fields(self):
        res = self.client.get('/v1/metrics/quote')
        self.assertEqual(res.status_code, 200)
        payload = res.json()

        self.assertIn('cached_symbols', payload)
        self.assertIn('ws_messages', payload)
        self.assertIn('upserts', payload)
        self.assertIn('stale_symbols', payload)

        self.assertIn('rest_fallbacks', payload)
        self.assertIn('ws_connected', payload)
        self.assertIn('ws_heartbeat_fresh', payload)
        self.assertIn('last_ws_message_ts', payload)

        self.assertEqual(payload['rest_fallbacks'], 0)
        self.assertFalse(payload['ws_connected'])
        self.assertFalse(payload['ws_heartbeat_fresh'])
        self.assertIsNone(payload['last_ws_message_ts'])

    def test_quote_metrics_updates_after_ws_and_rest_fallback(self):
        app.state.quote_gateway_service.get_quote('005930')
        quote_ingest_worker.on_ws_message({'symbol': '005930', 'price': 70100, 'ts': 1700000000})

        res = self.client.get('/v1/metrics/quote')
        self.assertEqual(res.status_code, 200)
        payload = res.json()

        self.assertEqual(payload['rest_fallbacks'], 1)
        self.assertEqual(payload['ws_messages'], 1)
        self.assertEqual(payload['upserts'], 1)
        self.assertTrue(payload['ws_connected'])
        self.assertTrue(payload['ws_heartbeat_fresh'])
        self.assertEqual(payload['last_ws_message_ts'], 1700000000)

    def test_quote_metrics_splits_ws_connection_and_heartbeat_freshness(self):
        quote_ingest_worker.ws_connected = True
        quote_ingest_worker.last_ws_heartbeat_ts = 100
        quote_ingest_worker.ws_heartbeat_timeout_sec = 5

        # stale heartbeat (now=200) but connection flag remains true
        payload = quote_ingest_worker.metrics(now=200)

        self.assertTrue(payload['ws_connected'])
        self.assertFalse(payload['ws_heartbeat_fresh'])


if __name__ == '__main__':
    unittest.main()
