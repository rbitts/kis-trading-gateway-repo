# KIS Trading Gateway

KIS 단일 세션 제약을 만족하는 **시세+주문 게이트웨이** 서비스.

## MVP Scope (Iteration 1)
- Session orchestrator skeleton (single active owner lock) + status API
- Quote ingest worker skeleton (WS hook + cache update + freshness 계산)
- Order executor queue worker skeleton (idempotency + 상태 전이)
- Metrics API
  - `GET /v1/metrics/quote`
  - `GET /v1/metrics/order`

## Run
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8890
```

## Quick API Check
```bash
# session state
curl -s http://127.0.0.1:8890/v1/session/status | jq

# quote
curl -s "http://127.0.0.1:8890/v1/quotes/005930" | jq

# order with idempotency
curl -s -X POST http://127.0.0.1:8890/v1/orders \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: sample-k1' \
  -d '{"account_id":"A1","symbol":"005930","side":"BUY","qty":1}' | jq

# metrics
curl -s http://127.0.0.1:8890/v1/metrics/quote | jq
curl -s http://127.0.0.1:8890/v1/metrics/order | jq
```

## Test
```bash
python -m unittest discover -s tests -v
```
