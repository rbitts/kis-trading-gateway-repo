from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import deque

from app.schemas.order import OrderAccepted, OrderRequest


class OrderQueue:
    def __init__(self) -> None:
        self.queue: deque[str] = deque()
        self.idem: dict[str, OrderAccepted] = {}
        self.idem_body_hash: dict[str, str] = {}
        self.jobs: dict[str, dict] = {}
        self.metrics_counters = {
            "accepted": 0,
            "deduplicated": 0,
            "processed": 0,
            "sent": 0,
            "rejected": 0,
        }

    def enqueue(self, req: OrderRequest, idem_key: str) -> OrderAccepted:
        body_hash = self._hash_request(req)

        if idem_key in self.idem:
            if self.idem_body_hash.get(idem_key) != body_hash:
                raise ValueError("IDEMPOTENCY_KEY_BODY_MISMATCH")
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
            "broker_order_id": None,
        }
        self.queue.append(oid)
        self.idem[idem_key] = accepted
        self.idem_body_hash[idem_key] = body_hash
        self.metrics_counters["accepted"] += 1
        return accepted

    @staticmethod
    def _map_adapter_error(exc: Exception) -> str:
        text = str(exc).upper()
        if "RATE_LIMIT" in text or "429" in text:
            return "RATE_LIMIT"
        if "AUTH" in text or "TOKEN" in text:
            return "AUTH"
        if "INVALID_ORDER" in text or "INVALID" in text:
            return "INVALID_ORDER"
        return "UNKNOWN"

    def process_next(
        self,
        success: bool = True,
        reason: str | None = None,
        adapter=None,
    ) -> dict | None:
        if not self.queue:
            return None

        oid = self.queue.popleft()
        job = self.jobs[oid]
        job["status"] = "DISPATCHING"
        job["updated_at"] = int(time.time())

        if adapter is not None:
            req = job["request"]
            try:
                result = adapter.place_order(
                    account_id=req["account_id"],
                    symbol=req["symbol"],
                    side=req["side"],
                    qty=req["qty"],
                    price=req.get("price"),
                    order_type=req.get("order_type", "LIMIT"),
                )
                job["status"] = "SENT"
                job["broker_order_id"] = result.get("broker_order_id")
                self.metrics_counters["sent"] += 1
            except Exception as exc:  # pragma: no cover - narrow mapping is unit tested
                job["status"] = "REJECTED"
                job["error"] = self._map_adapter_error(exc)
                self.metrics_counters["rejected"] += 1

            job["updated_at"] = int(time.time())
            self.metrics_counters["processed"] += 1
            return job

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

    def _hash_request(self, req: OrderRequest) -> str:
        payload = json.dumps(req.model_dump(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


order_queue = OrderQueue()
