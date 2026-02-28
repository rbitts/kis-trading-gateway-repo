from app.schemas.risk import RiskCheckRequest

_DEFAULT_PRICE = 70000
_BUY_NOTIONAL_CAP = 10000000


def get_available_sell_qty(account_id: str, symbol: str) -> int:
    # TODO(task3+): replace with broker/account adapter lookup.
    return 0


def evaluate_side_policy(
    req: RiskCheckRequest,
    *,
    get_available_sell_qty=get_available_sell_qty,
) -> dict[str, bool | str | None]:
    if req.side == 'BUY':
        effective_price = req.price if req.price is not None else _DEFAULT_PRICE
        if req.qty * effective_price > _BUY_NOTIONAL_CAP:
            return {'ok': False, 'reason': 'NOTIONAL_LIMIT_EXCEEDED'}
        return {'ok': True, 'reason': None}

    if req.side == 'SELL':
        available_qty = get_available_sell_qty(req.account_id, req.symbol)
        if req.qty > available_qty:
            return {'ok': False, 'reason': 'INSUFFICIENT_POSITION_QTY'}
        return {'ok': True, 'reason': None}

    return {'ok': False, 'reason': 'INVALID_SIDE'}


def evaluate_trade_risk(
    req: RiskCheckRequest,
    *,
    live_enabled: bool,
    daily_order_count: int,
    daily_order_limit: int,
    max_qty: int,
    get_available_sell_qty=get_available_sell_qty,
) -> dict[str, bool | str | None]:
    if not live_enabled:
        return {'ok': False, 'reason': 'LIVE_DISABLED'}

    if daily_order_count >= daily_order_limit:
        return {'ok': False, 'reason': 'DAILY_LIMIT_EXCEEDED'}

    side_result = evaluate_side_policy(req, get_available_sell_qty=get_available_sell_qty)
    if not side_result['ok']:
        return side_result

    # T2 정책: max_qty는 BUY 경로 우선 적용(SELL은 보유수량 정책 우선)
    if req.side == 'BUY' and req.qty > max_qty:
        return {'ok': False, 'reason': 'MAX_QTY_EXCEEDED'}

    return {'ok': True, 'reason': None}


_ALLOWED_TRANSITIONS = {
    'cancel': {'NEW', 'DISPATCHING', 'SENT', 'ACCEPTED', 'QUEUED'},
    'modify': {'NEW', 'DISPATCHING', 'SENT', 'ACCEPTED', 'QUEUED'},
}


def validate_order_action_transition(*, action: str, current_status: str) -> dict[str, bool | str | None]:
    normalized_action = action.lower()
    normalized_status = current_status.upper()
    allowed = _ALLOWED_TRANSITIONS.get(normalized_action, set())
    if normalized_status not in allowed:
        return {'ok': False, 'reason': 'INVALID_TRANSITION'}
    return {'ok': True, 'reason': None}
