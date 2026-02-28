from datetime import datetime, time

from fastapi import APIRouter, Header, HTTPException, Request

from app.errors import RestRateLimitCooldownError
from app.schemas.order import OrderAccepted, OrderRequest
from app.schemas.risk import RiskCheckRequest
from app.services.order_queue import order_queue
from app.services.quote_cache import quote_ingest_worker
from app.services.risk_policy import (
    evaluate_trade_risk,
    get_available_sell_qty,
    validate_order_action_transition,
)
from app.services.session_state import session_orchestrator

router = APIRouter()

_TRADING_START = time(9, 0)
_TRADING_END = time(15, 30)


_ALLOWED_SIDES = {"BUY", "SELL"}
_ALLOWED_ORDER_TYPES = {"LIMIT", "MARKET"}



_LIVE_TRADING_ENABLED = True
_DAILY_ORDER_LIMIT = 50
_MAX_ORDER_QTY = 100
_daily_order_count = 0


def _current_daily_order_count() -> int:
    return _daily_order_count


def _increment_daily_order_count() -> None:
    global _daily_order_count
    _daily_order_count += 1


def _ensure_transition_allowed(*, current_status: str, action: str) -> None:
    transition_result = validate_order_action_transition(action=action, current_status=current_status)
    if not transition_result['ok']:
        raise HTTPException(status_code=400, detail=transition_result['reason'])

def _validate_order_contract(req: OrderRequest) -> str | None:
    if req.side not in _ALLOWED_SIDES:
        return 'INVALID_SIDE'

    if req.order_type not in _ALLOWED_ORDER_TYPES:
        return 'INVALID_ORDER_TYPE'

    if req.order_type == 'LIMIT' and req.price is None and 'order_type' in req.model_fields_set:
        return 'PRICE_REQUIRED_FOR_LIMIT'

    if req.order_type == 'MARKET' and req.price is not None:
        return 'PRICE_NOT_ALLOWED_FOR_MARKET'

    return None


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
    try:
        row = service.get_quote(symbol)
    except RestRateLimitCooldownError as exc:
        raise HTTPException(status_code=503, detail='REST_RATE_LIMIT_COOLDOWN') from exc
    return row.model_dump()


@router.get('/quotes')
def get_quotes(symbols: str, request: Request):
    service = request.app.state.quote_gateway_service
    req = [s.strip() for s in symbols.split(',') if s.strip()]
    out = []
    for s in req:
        try:
            out.append(service.get_quote(s).model_dump())
        except RestRateLimitCooldownError as exc:
            raise HTTPException(status_code=503, detail='REST_RATE_LIMIT_COOLDOWN') from exc
    return out


@router.post('/risk/check')
def check_risk(req: RiskCheckRequest):
    if req.qty < 1:
        return {'ok': False, 'reason': 'INVALID_QTY'}

    if req.price is not None and req.price <= 0:
        return {'ok': False, 'reason': 'INVALID_PRICE'}

    trade_risk_result = evaluate_trade_risk(
        req,
        live_enabled=_LIVE_TRADING_ENABLED,
        daily_order_count=_current_daily_order_count(),
        daily_order_limit=_DAILY_ORDER_LIMIT,
        max_qty=_MAX_ORDER_QTY,
        get_available_sell_qty=get_available_sell_qty,
    )
    if not trade_risk_result['ok']:
        return trade_risk_result

    now_time = datetime.now().time().replace(tzinfo=None)
    if not (_TRADING_START <= now_time <= _TRADING_END):
        return {'ok': False, 'reason': 'OUT_OF_TRADING_WINDOW'}

    return {'ok': True, 'reason': None}


@router.post('/orders', response_model=OrderAccepted)
def create_order(req: OrderRequest, idempotency_key: str | None = Header(default=None, alias='Idempotency-Key')):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail='Idempotency-Key header required')

    contract_error = _validate_order_contract(req)
    if contract_error:
        raise HTTPException(status_code=400, detail=contract_error)

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
        accepted = order_queue.enqueue(req, idempotency_key)
        _increment_daily_order_count()
        return accepted
    except ValueError as exc:
        if str(exc) == 'IDEMPOTENCY_KEY_BODY_MISMATCH':
            raise HTTPException(status_code=409, detail='IDEMPOTENCY_KEY_BODY_MISMATCH') from exc
        raise


@router.get('/orders/{order_id}')
def get_order_status(order_id: str):
    job = order_queue.jobs.get(order_id)
    if not job:
        raise HTTPException(status_code=404, detail='order not found')

    status = job['status']
    if status == 'NEW':
        status = 'QUEUED'

    return {
        'order_id': job['order_id'],
        'status': status,
        'error': job['error'],
        'updated_at': job['updated_at'],
    }


@router.get('/orders/{order_id}/state')
def get_order_state(order_id: str):
    job = order_queue.jobs.get(order_id)
    if not job:
        raise HTTPException(status_code=404, detail='order not found')

    return {
        'order_id': job['order_id'],
        'status': job['status'],
        'error': job['error'],
        'updated_at': job['updated_at'],
        'attempts': job.get('attempts', 0),
        'max_attempts': job.get('max_attempts', 0),
        'terminal': job.get('terminal', False),
    }


@router.get('/metrics/quote')
def quote_metrics(request: Request):
    metrics = quote_ingest_worker.metrics()
    service = request.app.state.quote_gateway_service
    metrics.update(service.metrics())
    return metrics


@router.get('/metrics/order')
def order_metrics():
    return order_queue.metrics()
