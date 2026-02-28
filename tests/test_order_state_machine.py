import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.order import OrderRequest
from app.services.order_queue import OrderQueue, order_queue


class _FlakyAdapter:
    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0

    def place_order(self, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("RATE_LIMIT")
        return {"broker_order_id": f"broker-{self.calls}"}


class OrderStateMachineTest(unittest.TestCase):
    def setUp(self):
        self.q = OrderQueue()
        self.client = TestClient(app)
        order_queue.queue.clear()
        order_queue.idem.clear()
        order_queue.idem_body_hash.clear()
        order_queue.jobs.clear()
        order_queue.metrics_counters = {
            "accepted": 0,
            "deduplicated": 0,
            "processed": 0,
            "sent": 0,
            "rejected": 0,
        }

    def test_state_transition_new_sent_filled(self):
        accepted = self.q.enqueue(OrderRequest(account_id="A1", symbol="005930", side="BUY", qty=1), "idem-1")

        self.assertEqual(self.q.jobs[accepted.order_id]["status"], "NEW")

        sent = self.q.process_next(adapter=_FlakyAdapter(failures=0))
        self.assertEqual(sent["status"], "SENT")

        final = self.q.mark_execution_result(accepted.order_id, "FILLED")
        self.assertEqual(final["status"], "FILLED")
        self.assertTrue(final["terminal"])

    def test_retry_then_success(self):
        accepted = self.q.enqueue(OrderRequest(account_id="A1", symbol="005930", side="BUY", qty=1), "idem-2")
        adapter = _FlakyAdapter(failures=2)

        first_status = self.q.process_next(adapter=adapter)["status"]
        second_status = self.q.process_next(adapter=adapter)["status"]
        third_status = self.q.process_next(adapter=adapter)["status"]

        self.assertEqual(first_status, "NEW")
        self.assertEqual(second_status, "NEW")
        self.assertEqual(third_status, "SENT")
        self.assertEqual(self.q.jobs[accepted.order_id]["attempts"], 3)
        self.assertEqual(self.q.metrics()["retried"], 2)

    def test_retry_exhausted_goes_rejected_terminal(self):
        self.q.enqueue(OrderRequest(account_id="A1", symbol="005930", side="BUY", qty=1), "idem-3")
        adapter = _FlakyAdapter(failures=99)

        self.q.process_next(adapter=adapter)
        self.q.process_next(adapter=adapter)
        last = self.q.process_next(adapter=adapter)

        self.assertEqual(last["status"], "REJECTED")
        self.assertEqual(last["error"], "RETRY_EXHAUSTED")
        self.assertTrue(last["terminal"])
        self.assertEqual(self.q.metrics()["retry_exhausted"], 1)

    def test_order_status_endpoint_exposes_attempts_and_terminal(self):
        accepted = order_queue.enqueue(OrderRequest(account_id="A1", symbol="005930", side="BUY", qty=1), "idem-api-1")
        order_queue.jobs[accepted.order_id]["attempts"] = 2
        order_queue.jobs[accepted.order_id]["terminal"] = False

        r = self.client.get(f"/v1/orders/{accepted.order_id}/state")

        self.assertEqual(r.status_code, 200)
        self.assertIn("attempts", r.json())
        self.assertIn("terminal", r.json())


if __name__ == "__main__":
    unittest.main()
