# Consumer API Guide

이 문서는 KIS Trading Gateway 컨슈머를 위한 단일 가이드입니다.

## 0) Quick Start (5분)
1. 서버 실행
2. `GET /v1/session/status` 확인
3. `GET /v1/quotes/{symbol}` 조회
4. `POST /v1/orders` 주문 생성
5. `GET /v1/orders/{order_id}` 상태 확인

## 1) Base URL
- Local: `http://127.0.0.1:8890/v1`

## 2) Auth / Headers
- `Content-Type: application/json`
- `Idempotency-Key` (주문 생성 시 필수)

## 3) Common Flows

### 3.1 Quote 조회
```bash
curl -s "http://127.0.0.1:8890/v1/quotes/005930" | jq
```

```python
import requests
res = requests.get("http://127.0.0.1:8890/v1/quotes/005930", timeout=5)
print(res.json())
```

```javascript
const res = await fetch("http://127.0.0.1:8890/v1/quotes/005930");
console.log(await res.json());
```

### 3.2 Order Create + Status
```bash
ORDER_ID=$(curl -s -X POST http://127.0.0.1:8890/v1/orders \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: consumer-buy-1' \
  -d '{"account_id":"A1","symbol":"005930","side":"BUY","qty":1,"price":70000,"order_type":"LIMIT"}' | jq -r '.order_id')

curl -s "http://127.0.0.1:8890/v1/orders/${ORDER_ID}" | jq
```

```python
import requests
base = "http://127.0.0.1:8890/v1"
order = requests.post(
    f"{base}/orders",
    headers={"Idempotency-Key": "consumer-buy-1"},
    json={
        "account_id": "A1",
        "symbol": "005930",
        "side": "BUY",
        "qty": 1,
        "price": 70000,
        "order_type": "LIMIT",
    },
    timeout=5,
).json()
print(requests.get(f"{base}/orders/{order['order_id']}", timeout=5).json())
```

```javascript
const base = "http://127.0.0.1:8890/v1";
const createRes = await fetch(`${base}/orders`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Idempotency-Key": "consumer-buy-1",
  },
  body: JSON.stringify({
    account_id: "A1",
    symbol: "005930",
    side: "BUY",
    qty: 1,
    price: 70000,
    order_type: "LIMIT",
  }),
});
const created = await createRes.json();
const statusRes = await fetch(`${base}/orders/${created.order_id}`);
console.log(await statusRes.json());
```

### 3.3 Modify / Cancel
```bash
curl -s -X POST "http://127.0.0.1:8890/v1/orders/${ORDER_ID}/modify" \
  -H 'Content-Type: application/json' \
  -d '{"qty":2,"price":70100}' | jq

curl -s -X POST "http://127.0.0.1:8890/v1/orders/${ORDER_ID}/cancel" | jq
```

```python
requests.post(f"{base}/orders/{order['order_id']}/modify", json={"qty": 2, "price": 70100}, timeout=5)
requests.post(f"{base}/orders/{order['order_id']}/cancel", timeout=5)
```

```javascript
await fetch(`${base}/orders/${created.order_id}/modify`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ qty: 2, price: 70100 }),
});
await fetch(`${base}/orders/${created.order_id}/cancel`, { method: "POST" });
```

### 3.4 Risk Check
```bash
curl -s -X POST "http://127.0.0.1:8890/v1/risk/check" \
  -H 'Content-Type: application/json' \
  -d '{"account_id":"A1","symbol":"005930","side":"BUY","qty":1,"price":70000}' | jq
```

```python
print(requests.post(
    f"{base}/risk/check",
    json={"account_id": "A1", "symbol": "005930", "side": "BUY", "qty": 1, "price": 70000},
    timeout=5,
).json())
```

```javascript
const risk = await fetch(`${base}/risk/check`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ account_id: "A1", symbol: "005930", side: "BUY", qty: 1, price: 70000 }),
});
console.log(await risk.json());
```

## 4) Reference (Appendix)

### Appendix A) Endpoint Reference
- `GET /session/status`
- `GET /session/live-readiness`
- `POST /session/reconnect`
- `GET /quotes/{symbol}`
- `GET /quotes?symbols=...`
- `POST /risk/check`
- `POST /orders`
- `GET /orders/{order_id}`
- `GET /orders/{order_id}/state`
- `POST /orders/{order_id}/modify`
- `POST /orders/{order_id}/cancel`
- `GET /balances?account_id=...`
- `GET /positions?account_id=...`
- `GET /metrics/quote`
- `GET /metrics/order`

### Appendix B) Error Codes & Mapping
주요 에러 코드:
- `INVALID_QTY`
- `INVALID_PRICE`
- `INVALID_SIDE`
- `INVALID_ORDER_TYPE`
- `PRICE_REQUIRED_FOR_LIMIT`
- `PRICE_NOT_ALLOWED_FOR_MARKET`
- `NOTIONAL_LIMIT_EXCEEDED`
- `OUT_OF_TRADING_WINDOW`
- `POSITION_PROVIDER_UNAVAILABLE`
- `PORTFOLIO_PROVIDER_NOT_CONFIGURED`
- `PORTFOLIO_PROVIDER_UNAVAILABLE`
- `IDEMPOTENCY_KEY_BODY_MISMATCH`
- `INVALID_TRANSITION`

HTTP 매핑(요약):
- `400`: 요청 계약/리스크 위반
- `409`: 멱등성 body mismatch 또는 terminal 상태 충돌
- `503`: provider 미구성/쿨다운 등 일시적 가용성 이슈

### Appendix C) Live Readiness 운영 체크
실브로커 검증 전 고정 순서:
1. `GET /v1/session/live-readiness` 호출
2. `can_trade=true` 확인 시에만 제한적 주문 검증 단계 진입
3. `can_trade=false`면 blocker(`required_env_missing`, `WS_DISCONNECTED`, `WS_ERROR_PRESENT`) 해소 전 주문 검증 진행 금지

관련 운영 문서:
- `docs/ops/kis-quote-runbook.md`
- `docs/ops/kis-order-live-validation-checklist.md`
