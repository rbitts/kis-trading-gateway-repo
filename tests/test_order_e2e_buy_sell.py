import unittest
from datetime import datetime as real_datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.services.order_queue import order_queue


class _E2ERestClient:
    def get_quote(self, symbol: str):
        return {
            'symbol': symbol,
            'price': 70000.0,
            'change_pct': 0.0,
            'turnover': 0.0,
            'source': 'kis-rest',
            'ts': 1700000000,
        }

    def get_positions(self, account_id: str):
        return [
            {'account_id': account_id, 'symbol': '005930', 'qty': 5},
        ]


class TestOrderE2EBuySell(unittest.TestCase):
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
        routes._daily_order_count = 0
        app.state.quote_gateway_service.rest_client = _E2ERestClient()
        self.client = TestClient(app)

    def test_buy_then_status_and_idempotency(self):
        body = {
            "account_id": "A1",
            "symbol": "005930",
            "side": "BUY",
            "qty": 1,
            "price": 70000,
            "order_type": "LIMIT",
        }

        with patch("app.api.routes.datetime") as mock_datetime:
            mock_datetime.now.return_value = real_datetime(2026, 1, 2, 10, 0, 0)
            first = self.client.post("/v1/orders", headers={"Idempotency-Key": "e2e-buy-1"}, json=body)
            second = self.client.post("/v1/orders", headers={"Idempotency-Key": "e2e-buy-1"}, json=body)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

        order_id = first.json()["order_id"]
        self.assertEqual(order_id, second.json()["order_id"])

        status = self.client.get(f"/v1/orders/{order_id}")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["status"], "QUEUED")

    def test_sell_then_status_and_idempotency_body_mismatch(self):
        sell_body = {
            "account_id": "A1",
            "symbol": "005930",
            "side": "SELL",
            "qty": 1,
            "price": 70000,
            "order_type": "LIMIT",
        }

        with patch("app.api.routes.datetime") as mock_datetime, patch(
            "app.api.routes.get_available_sell_qty", return_value=5
        ):
            mock_datetime.now.return_value = real_datetime(2026, 1, 2, 10, 0, 0)
            first = self.client.post("/v1/orders", headers={"Idempotency-Key": "e2e-sell-1"}, json=sell_body)
            mismatch = self.client.post(
                "/v1/orders",
                headers={"Idempotency-Key": "e2e-sell-1"},
                json={**sell_body, "qty": 2},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(mismatch.status_code, 409)
        self.assertEqual(mismatch.json(), {"detail": "IDEMPOTENCY_KEY_BODY_MISMATCH"})

        status = self.client.get(f"/v1/orders/{first.json()['order_id']}")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["status"], "QUEUED")

    def test_runbook_evidence_and_readme_examples_exist(self):
        repo_root = Path(__file__).resolve().parents[1]
        evidence_path = repo_root / "docs" / "evidence" / "2026-02-28-buy-sell-e2e.md"
        readme_path = repo_root / "README.md"

        self.assertTrue(evidence_path.exists(), "E2E evidence doc is required")

        readme = readme_path.read_text(encoding="utf-8")
        self.assertIn("BUY 주문 + 상태조회", readme)
        self.assertIn("SELL 주문 + 상태조회", readme)


if __name__ == "__main__":
    unittest.main()
