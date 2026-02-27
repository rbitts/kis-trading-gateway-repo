from __future__ import annotations

import time
import uuid
from collections import deque

from app.schemas.order import OrderAccepted, OrderRequest


class OrderQueue:
    def __init__(self) -> None:
        self.queue: deque[dict] = deque()
        self.idem: dict[str, OrderAccepted] = {}

    def enqueue(self, req: OrderRequest, idem_key: str) -> OrderAccepted:
        if idem_key in self.idem:
            return self.idem[idem_key]
        oid = f"ord_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        accepted = OrderAccepted(order_id=oid, status="ACCEPTED", idempotency_key=idem_key)
        self.queue.append({"order_id": oid, "request": req.model_dump(), "status": "QUEUED"})
        self.idem[idem_key] = accepted
        return accepted


order_queue = OrderQueue()
