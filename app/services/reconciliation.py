from __future__ import annotations

import threading
import time
from typing import Callable


class ReconciliationService:
    def __init__(
        self,
        *,
        order_queue,
        broker_status_provider: Callable[[str, dict], str | None] | None = None,
        interval_sec: float = 5.0,
    ) -> None:
        self.order_queue = order_queue
        self.broker_status_provider = broker_status_provider or (lambda _order_id, _job: None)
        self.interval_sec = interval_sec
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._metrics = {
            "runs": 0,
            "checked": 0,
            "mismatched": 0,
            "corrected": 0,
        }
        self._recent_events: list[dict] = []

    def _record_event(self, event: dict) -> None:
        self._recent_events.append(event)
        if len(self._recent_events) > 100:
            self._recent_events = self._recent_events[-100:]

    def _apply_correction(self, *, job: dict, broker_status: str) -> str:
        corrected_status = broker_status
        terminal_states = {"FILLED", "REJECTED", "CANCELED"}

        job["status"] = corrected_status
        if corrected_status in terminal_states:
            job["terminal"] = True
            if corrected_status == "FILLED":
                job["error"] = None
            elif corrected_status == "REJECTED":
                job["error"] = job.get("error") or "BROKER_REJECTED"
            else:
                job["error"] = None
        job["updated_at"] = int(time.time())
        return corrected_status

    def reconcile_once(self) -> dict:
        checked = 0
        mismatched = 0
        corrected = 0
        events: list[dict] = []

        for order_id, job in list(self.order_queue.jobs.items()):
            checked += 1
            broker_status = self.broker_status_provider(order_id, job)
            if not broker_status:
                continue

            internal_status = str(job.get("status", "UNKNOWN"))
            normalized_broker = str(broker_status).upper()
            if internal_status == normalized_broker:
                continue

            mismatched += 1
            corrected_status = self._apply_correction(job=job, broker_status=normalized_broker)
            corrected += 1
            event = {
                "order_id": order_id,
                "internal_status": internal_status,
                "broker_status": normalized_broker,
                "corrected_status": corrected_status,
                "ts": int(time.time()),
            }
            events.append(event)
            self._record_event(event)

        self._metrics["runs"] += 1
        self._metrics["checked"] += checked
        self._metrics["mismatched"] += mismatched
        self._metrics["corrected"] += corrected

        return {
            "checked": checked,
            "mismatched": mismatched,
            "corrected": corrected,
            "events": events,
        }

    def trigger(self) -> dict:
        return self.reconcile_once()

    def _loop(self) -> None:
        while not self._stop_event.wait(self.interval_sec):
            try:
                self.reconcile_once()
            except Exception:  # pragma: no cover
                continue

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="reconciliation-worker")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def metrics(self) -> dict:
        return {
            **self._metrics,
            "recent_events": list(self._recent_events),
        }
