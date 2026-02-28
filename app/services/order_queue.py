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
            "filled": 0,
            "retried": 0,
            "retry_exhausted": 0,
            "terminal": 0,
        }

    def _inc(self, key: str, value: int = 1) -> None:
        self.metrics_counters[key] = self.metrics_counters.get(key, 0) + value

    def enqueue(self, req: OrderRequest, idem_key: str) -> OrderAccepted:
        body_hash = self._hash_request(req)

        if idem_key in self.idem:
            if self.idem_body_hash.get(idem_key) != body_hash:
                raise ValueError("IDEMPOTENCY_KEY_BODY_MISMATCH")
            self._inc("deduplicated")
            return self.idem[idem_key]

        oid = f"ord_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        accepted = OrderAccepted(order_id=oid, status="ACCEPTED", idempotency_key=idem_key)
        self.jobs[oid] = {
            "order_id": oid,
            "request": req.model_dump(),
            "status": "NEW",
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
            "error": None,
            "broker_order_id": None,
            "attempts": 0,
            "max_attempts": 3,
            "terminal": False,
        }
        self.queue.append(oid)
        self.idem[idem_key] = accepted
        self.idem_body_hash[idem_key] = body_hash
        self._inc("accepted")
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

    @staticmethod
    def _is_retryable(error_code: str) -> bool:
        return error_code in {"RATE_LIMIT", "UNKNOWN"}

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
        if job.get("terminal"):
            return job

        job["status"] = "DISPATCHING"
        job["updated_at"] = int(time.time())

        if adapter is not None:
            req = job["request"]
            job["attempts"] = int(job.get("attempts", 0)) + 1
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
                job["error"] = None
                job["broker_order_id"] = result.get("broker_order_id")
                self._inc("sent")
            except Exception as exc:  # pragma: no cover
                mapped_error = self._map_adapter_error(exc)
                max_attempts = int(job.get("max_attempts", 3))
                if self._is_retryable(mapped_error) and job["attempts"] < max_attempts:
                    job["status"] = "NEW"
                    job["error"] = mapped_error
                    self.queue.append(oid)
                    self._inc("retried")
                else:
                    if self._is_retryable(mapped_error) and job["attempts"] >= max_attempts:
                        job["error"] = "RETRY_EXHAUSTED"
                        self._inc("retry_exhausted")
                    else:
                        job["error"] = mapped_error
                    job["status"] = "REJECTED"
                    job["terminal"] = True
                    self._inc("rejected")
                    self._inc("terminal")

            job["updated_at"] = int(time.time())
            self._inc("processed")
            return job

        if success:
            job["status"] = "SENT"
            self._inc("sent")
        else:
            job["status"] = "REJECTED"
            job["error"] = reason or "unknown"
            job["terminal"] = True
            self._inc("rejected")
            self._inc("terminal")

        job["updated_at"] = int(time.time())
        self._inc("processed")
        return job

    def mark_execution_result(self, order_id: str, status: str, reason: str | None = None) -> dict:
        job = self.jobs[order_id]
        normalized = status.upper()
        if normalized not in {"FILLED", "REJECTED"}:
            raise ValueError("INVALID_FINAL_STATUS")
        if job.get("terminal"):
            return job

        job["status"] = normalized
        job["terminal"] = True
        job["updated_at"] = int(time.time())

        if normalized == "FILLED":
            job["error"] = None
            self._inc("filled")
        else:
            job["error"] = reason or "BROKER_REJECTED"
            self._inc("rejected")

        self._inc("terminal")
        return job

    def get_status(self, order_id: str) -> str | None:
        job = self.jobs.get(order_id)
        if not job:
            return None
        return str(job["status"])

    def request_cancel(self, order_id: str) -> dict:
        job = self.jobs.get(order_id)
        if not job:
            raise KeyError("ORDER_NOT_FOUND")
        if job.get("terminal"):
            raise RuntimeError("ORDER_ALREADY_TERMINAL")

        job["status"] = "CANCEL_PENDING"
        job["updated_at"] = int(time.time())
        return job

    def request_modify(self, order_id: str, *, qty: int, price: float | None = None) -> dict:
        job = self.jobs.get(order_id)
        if not job:
            raise KeyError("ORDER_NOT_FOUND")
        if job.get("terminal"):
            raise RuntimeError("ORDER_ALREADY_TERMINAL")

        request_payload = job.get("request", {})
        request_payload["qty"] = qty
        request_payload["price"] = price

        job["status"] = "MODIFY_PENDING"
        job["updated_at"] = int(time.time())
        return job

    def metrics(self) -> dict:
        base = {
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
        merged = {k: self.metrics_counters.get(k, 0) for k in base}
        return {
            "queue_depth": len(self.queue),
            **merged,
        }

    def _hash_request(self, req: OrderRequest) -> str:
        payload = json.dumps(req.model_dump(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


order_queue = OrderQueue()
