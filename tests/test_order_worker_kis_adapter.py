import unittest
from unittest.mock import MagicMock

from app.integrations.kis_rest import KisRestClient
from app.schemas.order import OrderRequest
from app.services.order_queue import OrderQueue
from app.services.order_worker import OrderWorker


class TestKisAdapterContract(unittest.TestCase):
    def test_place_order_maps_buy_side_for_mock(self):
        session = MagicMock()

        token_response = MagicMock()
        token_response.raise_for_status.return_value = None
        token_response.json.return_value = {"access_token": "token-123", "expires_in": 3600}

        order_response = MagicMock()
        order_response.raise_for_status.return_value = None
        order_response.json.return_value = {
            "rt_cd": "0",
            "output": {"ODNO": "1001"},
            "msg_cd": "M000",
            "msg1": "ok",
        }

        session.post.side_effect = [token_response, order_response]

        client = KisRestClient(
            app_key="app-key",
            app_secret="app-secret",
            env="mock",
            session=session,
            base_url="https://example.test",
        )

        placed = client.place_order(
            account_id="12345678-01",
            symbol="005930",
            side="BUY",
            qty=1,
            price=70000,
            order_type="LIMIT",
        )

        self.assertEqual(placed["broker_order_id"], "1001")
        order_call = session.post.call_args_list[1]
        self.assertEqual(order_call.kwargs["headers"]["tr_id"], "VTTC0802U")
        self.assertEqual(order_call.kwargs["json"]["SLL_BUY_DVSN_CD"], "02")

    def test_get_order_status_maps_response(self):
        session = MagicMock()

        token_response = MagicMock()
        token_response.raise_for_status.return_value = None
        token_response.json.return_value = {"access_token": "token-123", "expires_in": 3600}

        status_response = MagicMock()
        status_response.raise_for_status.return_value = None
        status_response.json.return_value = {
            "rt_cd": "0",
            "output1": [{"odno": "1001", "ord_stts": "01"}],
        }

        session.post.return_value = token_response
        session.get.return_value = status_response

        client = KisRestClient(
            app_key="app-key",
            app_secret="app-secret",
            env="live",
            session=session,
            base_url="https://example.test",
        )

        status = client.get_order_status(account_id="12345678-01", broker_order_id="1001")

        self.assertEqual(status["broker_order_id"], "1001")
        self.assertEqual(status["status"], "01")


class TestOrderWorkerKisAdapter(unittest.TestCase):
    def setUp(self):
        self.queue = OrderQueue()

    def test_order_worker_sends_to_adapter_and_marks_sent(self):
        accepted = self.queue.enqueue(
            OrderRequest(account_id="A1", symbol="005930", side="BUY", qty=1, price=70000),
            "idem-adapter-1",
        )

        adapter = MagicMock()
        adapter.place_order.return_value = {"broker_order_id": "1001", "status": "SENT"}

        worker = OrderWorker(adapter=adapter, queue=self.queue)
        job = worker.execute_next()

        self.assertEqual(job["order_id"], accepted.order_id)
        self.assertEqual(job["status"], "SENT")
        self.assertEqual(job["broker_order_id"], "1001")

    def test_order_worker_maps_adapter_error(self):
        self.queue.enqueue(
            OrderRequest(account_id="A1", symbol="005930", side="SELL", qty=1, price=70000),
            "idem-adapter-2",
        )

        adapter = MagicMock()
        adapter.place_order.side_effect = RuntimeError("AUTH")

        worker = OrderWorker(adapter=adapter, queue=self.queue)
        job = worker.execute_next()

        self.assertEqual(job["status"], "REJECTED")
        self.assertEqual(job["error"], "AUTH")


if __name__ == "__main__":
    unittest.main()
