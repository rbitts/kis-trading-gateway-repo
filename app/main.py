from __future__ import annotations

import time

from fastapi import FastAPI

from app.api.routes import router
from app.config.settings import get_settings
from app.services.quote_cache import quote_cache
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


app = FastAPI(title="KIS Trading Gateway", version="0.1.0")
app.include_router(router, prefix="/v1")

# NOTE: lazy-loaded so app import does not require env during tests.
app.state.get_settings = get_settings
app.state.quote_gateway_service = QuoteGatewayService(
    quote_cache=quote_cache,
    rest_client=_DemoRestQuoteClient(),
)
