from datetime import datetime, time

from fastapi import APIRouter, Header, HTTPException, Request

from app.schemas.order import OrderAccepted, OrderRequest
from app.schemas.risk import RiskCheckRequest
from app.services.order_queue import order_queue
from app.services.quote_cache import quote_ingest_worker
from app.services.session_state import session_orchestrator

router = APIRouter()

_DEFAULT_PRICE = 70000
_NOTIONAL_CAP = 10000000
_TRADING_START = time(9, 0)
_TRADING_END = time(15, 30)


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
def get_quote(symbol: str, request: Request):
    service = request.app.state.quote_gateway_service
    row = service.get_quote(symbol)
    return row.model_dump()


@router.get('/quotes')
def get_quotes(symbols: str, request: Request):
    service = request.app.state.quote_gateway_service
    req = [s.strip() for s in symbols.split(',') if s.strip()]
    return [service.get_quote(s).model_dump() for s in req]


@router.post('/risk/check')
def check_risk(req: RiskCheckRequest):
    if req.qty < 1:
        return {'ok': False, 'reason': 'INVALID_QTY'}

    if req.price is not None and req.price <= 0:
        return {'ok': False, 'reason': 'INVALID_PRICE'}

    effective_price = req.price if req.price is not None else _DEFAULT_PRICE
    if req.qty * effective_price > _NOTIONAL_CAP:
        return {'ok': False, 'reason': 'NOTIONAL_LIMIT_EXCEEDED'}

    now_time = datetime.now().time().replace(tzinfo=None)
    if not (_TRADING_START <= now_time <= _TRADING_END):
        return {'ok': False, 'reason': 'OUT_OF_TRADING_WINDOW'}

    return {'ok': True, 'reason': None}


@router.post('/orders', response_model=OrderAccepted)
def create_order(req: OrderRequest, idempotency_key: str | None = Header(default=None, alias='Idempotency-Key')):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail='Idempotency-Key header required')

    risk_result = check_risk(
        RiskCheckRequest(
            account_id=req.account_id,
            symbol=req.symbol,
            side=req.side,
            qty=req.qty,
            price=req.price,
        )
    )
    if not risk_result['ok']:
        raise HTTPException(status_code=400, detail=risk_result['reason'])

    try:
        return order_queue.enqueue(req, idempotency_key)
    except ValueError as exc:
        if str(exc) == 'IDEMPOTENCY_KEY_BODY_MISMATCH':
            raise HTTPException(status_code=409, detail='IDEMPOTENCY_KEY_BODY_MISMATCH') from exc
        raise


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
