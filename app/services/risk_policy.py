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
