# Order API Contract (Task 1)

> Consumer-friendly single guide: `docs/api/consumer-api-guide.md`

## Existing Endpoint
- `POST /v1/orders` (`operationId: createOrder`)

## Request Body
- `account_id` (string, required)
- `symbol` (string, required)
- `side` (string, required): `BUY` | `SELL` (case-insensitive input, normalized to uppercase)
- `qty` (int, required): must be `>= 1`
- `order_type` (string, optional, default `LIMIT`): `LIMIT` | `MARKET` (case-insensitive input, normalized to uppercase)
- `price` (number, optional)
  - `LIMIT`: `price` required
  - `MARKET`: `price` must be omitted
- `strategy_id` (string, optional)

## Required Header
- `Idempotency-Key` (required)

## Success Response
`200 OK`
```json
{
  "order_id": "ord_...",
  "status": "ACCEPTED",
  "idempotency_key": "..."
}
```

## Public API Docs (GitHub Pages)
- Hub: `https://rbitts.github.io/kis-trading-gateway-repo/`
- Redoc Live: `https://rbitts.github.io/kis-trading-gateway-repo/redoc-live.html`
- Redoc Next: `https://rbitts.github.io/kis-trading-gateway-repo/redoc-next.html`

## Next Contract Endpoints (OpenAPI Draft)
- `POST /v1/orders/{order_id}/cancel` (`operationId: cancelOrder`)
- `POST /v1/orders/{order_id}/modify` (`operationId: modifyOrder`)
- `GET /v1/balances` (`operationId: getBalances`)
- `GET /v1/positions` (`operationId: getPositions`)
- `POST /v1/orders/reconcile` (`operationId: reconcileOrders`)

## Error schema
```json
{
  "code": "INVALID_TRANSITION",
  "message": "Order cannot be modified in current state",
  "retryable": false
}
```

## Error Codes
- `INVALID_QTY`
- `INVALID_PRICE`
- `NOTIONAL_LIMIT_EXCEEDED`
- `OUT_OF_TRADING_WINDOW`
- `IDEMPOTENCY_KEY_BODY_MISMATCH` (HTTP 409)
- `INVALID_SIDE`
- `INVALID_ORDER_TYPE`
- `PRICE_REQUIRED_FOR_LIMIT`
- `PRICE_NOT_ALLOWED_FOR_MARKET`
- `INVALID_TRANSITION`

## Error Mapping
- `400`: contract/risk violations
- `409`: idempotency body hash mismatch
