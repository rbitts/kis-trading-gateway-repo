from __future__ import annotations

from app.services.order_queue import OrderQueue, order_queue


class OrderWorker:
    def __init__(self, adapter, queue: OrderQueue | None = None) -> None:
        self.adapter = adapter
        self.queue = queue or order_queue

    def execute_next(self) -> dict | None:
        return self.queue.process_next(adapter=self.adapter)
