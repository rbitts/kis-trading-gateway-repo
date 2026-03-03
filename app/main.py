from __future__ import annotations

import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.config.settings import get_settings
from app.integrations.kis_rest import KisRestClient
from app.integrations.kis_ws import KisWsClient
from app.services.order_queue import order_queue
from app.services.quote_cache import quote_cache, quote_ingest_worker
from app.services.quote_gateway import QuoteGatewayService
from app.services.reconciliation import ReconciliationService


class _DemoRestQuoteClient:
    def get_quote(self, symbol: str) -> dict:
        return {
            'symbol': symbol,
            'price': 70000.0,
            'change_pct': 0.0,
            'turnover': 0.0,
            'source': 'kis-rest',
            'ts': int(time.time()),
        }


def _bind_runtime_clients(app: FastAPI, settings) -> None:
    app.state.ws_client.env = settings.KIS_ENV
    if app.state.ws_client._approval_key_client is None:
        app.state.ws_client._approval_key_client = KisRestClient(
            app_key=settings.KIS_APP_KEY,
            app_secret=settings.KIS_APP_SECRET,
            env=settings.KIS_ENV,
        )

    # When runtime KIS env is available, bind portfolio-capable REST client.
    app.state.quote_gateway_service.rest_client = KisRestClient(
        app_key=settings.KIS_APP_KEY,
        app_secret=settings.KIS_APP_SECRET,
        env=settings.KIS_ENV,
    )


def _should_enable_order_worker() -> bool:
    # Keep deterministic tests: pytest sets PYTEST_CURRENT_TEST.
    if os.getenv('PYTEST_CURRENT_TEST'):
        return False
    raw = str(os.getenv('ORDER_WORKER_ENABLED', 'true')).strip().lower()
    return raw in {'1', 'true', 'yes', 'on'}


def _order_worker_loop(app: FastAPI, stop_event: threading.Event, interval_sec: float) -> None:
    while not stop_event.wait(interval_sec):
        try:
            adapter = getattr(app.state.quote_gateway_service, 'rest_client', None)
            if adapter is None or not hasattr(adapter, 'place_order'):
                continue
            app.state.order_queue.process_next(adapter=adapter)
        except Exception:
            continue


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        settings = app.state.get_settings()
        _bind_runtime_clients(app, settings)
    except Exception:
        # keep app import/lifecycle resilient in test env without KIS secrets
        pass

    app.state.reconciliation_worker.start()

    order_worker_thread = None
    order_worker_stop_event = None
    if _should_enable_order_worker():
        order_worker_stop_event = threading.Event()
        app.state.order_worker_stop_event = order_worker_stop_event
        interval_sec = float(os.getenv('ORDER_WORKER_INTERVAL_SEC', '0.5'))
        order_worker_thread = threading.Thread(
            target=_order_worker_loop,
            args=(app, order_worker_stop_event, interval_sec),
            daemon=True,
            name='order-worker',
        )
        app.state.order_worker_thread = order_worker_thread
        print("[ORDER][worker_start] thread=order-worker", flush=True)
        order_worker_thread.start()

    ws_worker = threading.Thread(
        target=lambda: app.state.ws_client.run_with_reconnect(
            connect_once=lambda: app.state.ws_client.connect_and_subscribe(
                symbols=app.state.get_settings().KIS_WS_SYMBOLS
            )
        ),
        daemon=True,
        name='kis-ws-worker',
    )
    app.state.ws_worker_thread = ws_worker
    print("[WS][ws_worker_start] thread=kis-ws-worker", flush=True)
    ws_worker.start()

    try:
        yield
    finally:
        app.state.reconciliation_worker.stop()
        if order_worker_stop_event is not None:
            order_worker_stop_event.set()
        if order_worker_thread is not None and order_worker_thread.is_alive():
            order_worker_thread.join(timeout=1.0)
            print("[ORDER][worker_stop] thread=order-worker", flush=True)
        app.state.ws_client.stop()
        ws_worker.join(timeout=1.0)
        print("[WS][ws_worker_stop] thread=kis-ws-worker", flush=True)


app = FastAPI(title="KIS Trading Gateway", version="0.1.0", lifespan=lifespan)
app.include_router(router, prefix="/v1")

# NOTE: lazy-loaded so app import does not require env during tests.
app.state.get_settings = get_settings
app.state.ws_client = KisWsClient(
    on_message=quote_ingest_worker.on_ws_message,
    on_state_change=quote_ingest_worker.sync_ws_state,
)
app.state.quote_gateway_service = QuoteGatewayService(
    quote_cache=quote_cache,
    rest_client=_DemoRestQuoteClient(),
)
app.state.order_queue = order_queue
app.state.reconciliation_worker = ReconciliationService(order_queue=order_queue)
