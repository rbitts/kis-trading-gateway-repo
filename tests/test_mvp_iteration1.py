import time
import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.order import OrderRequest
from app.services.order_queue import order_queue
from app.services.quote_cache import quote_cache, quote_ingest_worker
from app.services.session_state import SessionOrchestrator


class Iteration1Test(unittest.TestCase):
    def setUp(self):
        quote_cache._rows.clear()
        quote_ingest_worker.ws_messages = 0
        quote_ingest_worker.upserts = 0

        order_queue.queue.clear()
        order_queue.idem.clear()
        order_queue.jobs.clear()
        order_queue.metrics_counters = {
            "accepted": 0,
            "deduplicated": 0,
            "processed": 0,
            "sent": 0,
            "rejected": 0,
        }
        self.client = TestClient(app)

    def test_session_orchestrator_single_owner_lock(self):
        orchestrator = SessionOrchestrator()
        self.assertTrue(orchestrator.acquire("owner-a", ttl_sec=60))
        self.assertFalse(orchestrator.acquire("owner-b", ttl_sec=60))
        self.assertEqual(orchestrator.status().owner, "owner-a")

    def test_quote_ws_hook_and_freshness(self):
        quote_ingest_worker.on_ws_message({"symbol": "005930", "price": 71200, "ts": int(time.time()) - 10})
        quote_ingest_worker.refresh_freshness(now=int(time.time()))
        row = quote_cache.get("005930")
        self.assertIsNotNone(row)
        assert row
        self.assertEqual(row.state, "STALE")
        self.assertGreaterEqual(row.freshness_sec, 10.0)

    def test_order_idempotency(self):
        req = OrderRequest(account_id="A1", symbol="005930", side="BUY", qty=1)
        first = order_queue.enqueue(req, "idem-1")
        second = order_queue.enqueue(req, "idem-1")
        self.assertEqual(first.order_id, second.order_id)
        self.assertEqual(order_queue.metrics()["deduplicated"], 1)

    def test_order_worker_state_transition_sent(self):
        req = OrderRequest(account_id="A1", symbol="005930", side="BUY", qty=1)
        accepted = order_queue.enqueue(req, "idem-2")
        job = order_queue.process_next(success=True)
        self.assertIsNotNone(job)
        assert job
        self.assertEqual(job["order_id"], accepted.order_id)
        self.assertEqual(job["status"], "SENT")

    def test_order_worker_state_transition_rejected(self):
        req = OrderRequest(account_id="A1", symbol="005930", side="SELL", qty=1)
        accepted = order_queue.enqueue(req, "idem-3")
        job = order_queue.process_next(success=False, reason="risk-check-failed")
        self.assertEqual(job["order_id"], accepted.order_id)
        self.assertEqual(job["status"], "REJECTED")
        self.assertEqual(job["error"], "risk-check-failed")

    def test_metrics_endpoints(self):
        quote_ingest_worker.on_ws_message({"symbol": "005930", "price": 70100})
        self.client.post('/v1/orders', headers={'Idempotency-Key': 'm1'}, json={
            'account_id': 'A1', 'symbol': '005930', 'side': 'BUY', 'qty': 1
        })

        quote_metrics = self.client.get('/v1/metrics/quote')
        order_metrics = self.client.get('/v1/metrics/order')

        self.assertEqual(quote_metrics.status_code, 200)
        self.assertEqual(order_metrics.status_code, 200)
        self.assertEqual(quote_metrics.json()["cached_symbols"], 1)
        self.assertEqual(order_metrics.json()["accepted"], 1)


if __name__ == '__main__':
    unittest.main()
