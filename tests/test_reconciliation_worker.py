import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.order import OrderRequest
from app.services.order_queue import order_queue
from app.services.reconciliation import ReconciliationService


class TestReconciliationService(unittest.TestCase):
    def setUp(self):
        order_queue.queue.clear()
        order_queue.idem.clear()
        order_queue.idem_body_hash.clear()
        order_queue.jobs.clear()

    def test_reconcile_detects_diff_and_corrects_terminal_status(self):
        accepted = order_queue.enqueue(
            OrderRequest(account_id="A1", symbol="005930", side="BUY", qty=1, price=70000),
            "idem-reconcile-1",
        )
        order_queue.jobs[accepted.order_id]["status"] = "SENT"

        worker = ReconciliationService(
            order_queue=order_queue,
            broker_status_provider=lambda _order_id, _job: "FILLED",
        )

        result = worker.reconcile_once()

        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["mismatched"], 1)
        self.assertEqual(result["corrected"], 1)
        self.assertEqual(order_queue.jobs[accepted.order_id]["status"], "FILLED")
        self.assertTrue(order_queue.jobs[accepted.order_id]["terminal"])

        event = result["events"][0]
        self.assertEqual(event["order_id"], accepted.order_id)
        self.assertEqual(event["internal_status"], "SENT")
        self.assertEqual(event["broker_status"], "FILLED")
        self.assertEqual(event["corrected_status"], "FILLED")

    def test_reconcile_skips_when_status_is_same(self):
        accepted = order_queue.enqueue(
            OrderRequest(account_id="A1", symbol="005930", side="BUY", qty=1, price=70000),
            "idem-reconcile-2",
        )
        order_queue.jobs[accepted.order_id]["status"] = "SENT"

        worker = ReconciliationService(
            order_queue=order_queue,
            broker_status_provider=lambda _order_id, _job: "SENT",
        )

        result = worker.reconcile_once()

        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["mismatched"], 0)
        self.assertEqual(result["corrected"], 0)
        self.assertEqual(result["events"], [])

    def test_reconcile_persists_events_and_recovers_recent_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            event_log_path = Path(tmpdir) / "reconciliation-events.jsonl"

            accepted = order_queue.enqueue(
                OrderRequest(account_id="A1", symbol="005930", side="BUY", qty=1, price=70000),
                "idem-reconcile-3",
            )
            order_queue.jobs[accepted.order_id]["status"] = "SENT"

            worker = ReconciliationService(
                order_queue=order_queue,
                broker_status_provider=lambda _order_id, _job: "FILLED",
                event_log_path=event_log_path,
            )
            worker.reconcile_once()

            self.assertTrue(event_log_path.exists())
            self.assertEqual(len(event_log_path.read_text(encoding="utf-8").splitlines()), 1)

            recovered_worker = ReconciliationService(
                order_queue=order_queue,
                broker_status_provider=lambda _order_id, _job: None,
                event_log_path=event_log_path,
            )
            metrics = recovered_worker.metrics()
            self.assertEqual(metrics["persisted_count"], 1)
            self.assertEqual(len(metrics["recent_events"]), 1)
            self.assertEqual(metrics["recent_events"][0]["order_id"], accepted.order_id)


class TestMainWiringForReconciliationWorker(unittest.TestCase):
    def test_lifespan_calls_reconciliation_worker_start_and_stop(self):
        worker = app.state.reconciliation_worker
        original_start = worker.start
        original_stop = worker.stop

        start_mock = Mock()
        stop_mock = Mock()

        worker.start = start_mock
        worker.stop = stop_mock

        try:
            with TestClient(app):
                start_mock.assert_called_once_with()
                stop_mock.assert_not_called()

            stop_mock.assert_called_once_with()
        finally:
            worker.start = original_start
            worker.stop = original_stop


if __name__ == "__main__":
    unittest.main()
