import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.order import OrderRequest
from app.services.order_queue import order_queue


class TestOrderModifyCancelFlow(unittest.TestCase):
    def setUp(self):
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
            "filled": 0,
            "retried": 0,
            "retry_exhausted": 0,
            "terminal": 0,
        }
        self.client = TestClient(app)

    def test_cancel_order_transitions_to_cancel_pending(self):
        accepted = order_queue.enqueue(OrderRequest(account_id="A1", symbol="005930", side="BUY", qty=1), "idem-cancel-1")

        resp = self.client.post(f"/v1/orders/{accepted.order_id}/cancel")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["order_id"], accepted.order_id)
        self.assertEqual(order_queue.jobs[accepted.order_id]["status"], "CANCEL_PENDING")

    def test_modify_order_transitions_to_modify_pending_and_updates_request(self):
        accepted = order_queue.enqueue(OrderRequest(account_id="A1", symbol="005930", side="BUY", qty=1, price=70000), "idem-modify-1")
        order_queue.jobs[accepted.order_id]["status"] = "SENT"

        resp = self.client.post(
            f"/v1/orders/{accepted.order_id}/modify",
            json={"qty": 2, "price": 69900},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["order_id"], accepted.order_id)
        self.assertEqual(order_queue.jobs[accepted.order_id]["status"], "MODIFY_PENDING")
        self.assertEqual(order_queue.jobs[accepted.order_id]["request"]["qty"], 2)
        self.assertEqual(order_queue.jobs[accepted.order_id]["request"]["price"], 69900)

    def test_cancel_invalid_transition_returns_400(self):
        accepted = order_queue.enqueue(OrderRequest(account_id="A1", symbol="005930", side="BUY", qty=1), "idem-cancel-2")
        order_queue.jobs[accepted.order_id]["status"] = "FILLED"
        order_queue.jobs[accepted.order_id]["terminal"] = False

        resp = self.client.post(f"/v1/orders/{accepted.order_id}/cancel")

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json(), {"detail": "INVALID_TRANSITION"})

    def test_modify_terminal_order_returns_409(self):
        accepted = order_queue.enqueue(OrderRequest(account_id="A1", symbol="005930", side="BUY", qty=1, price=70000), "idem-modify-2")
        order_queue.jobs[accepted.order_id]["status"] = "CANCELED"
        order_queue.jobs[accepted.order_id]["terminal"] = True

        resp = self.client.post(
            f"/v1/orders/{accepted.order_id}/modify",
            json={"qty": 3, "price": 69800},
        )

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json(), {"detail": "ORDER_ALREADY_TERMINAL"})


if __name__ == "__main__":
    unittest.main()
