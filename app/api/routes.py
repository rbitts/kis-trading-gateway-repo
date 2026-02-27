from fastapi import APIRouter, Header, HTTPException

from app.schemas.order import OrderAccepted, OrderRequest
from app.services.order_queue import order_queue
from app.services.quote_cache import quote_cache, quote_ingest_worker, seed_demo_quote
from app.services.session_state import session_orchestrator

router = APIRouter()


@router.get('/session/status')
def get_session_status():
    return session_orchestrator.status().model_dump()


@router.post('/session/reconnect')
def reconnect_session(x_operator_token: str | None = Header(default=None, alias='X-Operator-Token')):
    if not x_operator_token:
        raise HTTPException(status_code=400, detail='X-Operator-Token header required')
    success = session_orchestrator.acquire(owner='gateway', ttl_sec=30, source='reconnect-api')
    status = session_orchestrator.status()
    return {
        'success': success,
        'owner': status.owner,
        'state': status.state,
        'source': status.source,
    }


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


@router.get('/orders/{order_id}')
def get_order_status(order_id: str):
    job = order_queue.jobs.get(order_id)
    if not job:
        raise HTTPException(status_code=404, detail='order not found')
    return {
        'order_id': job['order_id'],
        'status': job['status'],
        'error': job['error'],
        'updated_at': job['updated_at'],
    }


@router.get('/metrics/quote')
def quote_metrics():
    return quote_ingest_worker.metrics()


@router.get('/metrics/order')
def order_metrics():
    return order_queue.metrics()
