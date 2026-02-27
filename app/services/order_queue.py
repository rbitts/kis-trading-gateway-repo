from __future__ import annotations

import time
import uuid
from collections import deque

from app.schemas.order import OrderAccepted, OrderRequest


class OrderQueue:
    def __init__(self) -> None:
        self.queue: deque[str] = deque()
        self.idem: dict[str, OrderAccepted] = {}
        self.jobs: dict[str, dict] = {}
        self.metrics_counters = {
            "accepted": 0,
            "deduplicated": 0,
            "processed": 0,
            "sent": 0,
            "rejected": 0,
        }

    def enqueue(self, req: OrderRequest, idem_key: str) -> OrderAccepted:
        if idem_key in self.idem:
            self.metrics_counters["deduplicated"] += 1
            return self.idem[idem_key]

        oid = f"ord_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        accepted = OrderAccepted(order_id=oid, status="ACCEPTED", idempotency_key=idem_key)
        self.jobs[oid] = {
            "order_id": oid,
            "request": req.model_dump(),
            "status": "QUEUED",
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
            "error": None,
        }
        self.queue.append(oid)
        self.idem[idem_key] = accepted
        self.metrics_counters["accepted"] += 1
        return accepted

    def process_next(self, success: bool = True, reason: str | None = None) -> dict | None:
        if not self.queue:
            return None

        oid = self.queue.popleft()
        job = self.jobs[oid]
        job["status"] = "DISPATCHING"
        job["updated_at"] = int(time.time())

        if success:
            job["status"] = "SENT"
            self.metrics_counters["sent"] += 1
        else:
            job["status"] = "REJECTED"
            job["error"] = reason or "unknown"
            self.metrics_counters["rejected"] += 1

        job["updated_at"] = int(time.time())
        self.metrics_counters["processed"] += 1
        return job

    def get_status(self, order_id: str) -> str | None:
        job = self.jobs.get(order_id)
        if not job:
            return None
        return str(job["status"])

    def metrics(self) -> dict:
        return {
            "queue_depth": len(self.queue),
            **self.metrics_counters,
        }


order_queue = OrderQueue()
