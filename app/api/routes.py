from fastapi import APIRouter, Header, HTTPException

from app.schemas.order import OrderAccepted, OrderRequest
from app.services.order_queue import order_queue
from app.services.quote_cache import quote_cache, seed_demo_quote
from app.services.session_state import session_state

router = APIRouter()


@router.get('/session/status')
def get_session_status():
    return session_state.model_dump()


@router.get('/quotes/{symbol}')
def get_quote(symbol: str):
    row = quote_cache.get(symbol)
    if not row:
        seed_demo_quote(symbol)
        row = quote_cache.get(symbol)
    return row.model_dump()


@router.get('/quotes')
def get_quotes(symbols: str):
    req = [s.strip() for s in symbols.split(',') if s.strip()]
    for s in req:
        if not quote_cache.get(s):
            seed_demo_quote(s)
    return [r.model_dump() for r in quote_cache.list_many(req)]


@router.post('/orders', response_model=OrderAccepted)
def create_order(req: OrderRequest, idempotency_key: str | None = Header(default=None, alias='Idempotency-Key')):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail='Idempotency-Key header required')
    return order_queue.enqueue(req, idempotency_key)
