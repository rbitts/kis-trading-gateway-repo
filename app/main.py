from __future__ import annotations

import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.config.settings import get_settings
from app.integrations.kis_rest import KisRestClient
from app.integrations.kis_ws import KisWsClient
from app.services.quote_cache import quote_cache, quote_ingest_worker
from app.services.quote_gateway import QuoteGatewayService


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        settings = app.state.get_settings()
        app.state.ws_client.env = settings.KIS_ENV
        if app.state.ws_client._approval_key_client is None:
            app.state.ws_client._approval_key_client = KisRestClient(
                app_key=settings.KIS_APP_KEY,
                app_secret=settings.KIS_APP_SECRET,
                env=settings.KIS_ENV,
            )
    except Exception:
        # keep app import/lifecycle resilient in test env without KIS secrets
        pass

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
