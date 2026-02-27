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

## KIS Quote WS/REST 운영 요약

### Env 설정
```bash
export KIS_APP_KEY="..."
export KIS_APP_SECRET="..."
export KIS_ACCOUNT_NO="12345678-01"
export KIS_ENV="mock"  # mock | live
```

### Startup/Lifecycle 점검
```bash
curl -s http://127.0.0.1:8890/v1/session/status | jq
curl -s http://127.0.0.1:8890/v1/metrics/quote | jq
```
- startup 시 WS client start, shutdown 시 stop 수행
- `rest_fallbacks`, `ws_connected`, `last_ws_message_ts`를 운영 지표로 확인
- `ws_heartbeat_fresh`, `ws_reconnect_count`, `ws_last_error`로 reconnect 상태를 함께 점검
- REST 429 발생 시 `REST_RATE_LIMIT_COOLDOWN`(HTTP 503) 응답 정책 확인

### 장중/장외 동작 기대치
- 장중(09:00~15:30 KST): WS fresh면 `kis-ws`, stale/미수신이면 `kis-rest`
- 장외: `kis-rest`

### 장애 대응 핵심
- WS 끊김(reconnect): metrics 확인 → 프로세스 재기동/재연결 → `ws_connected`, `ws_heartbeat_fresh`, `ws_reconnect_count` 회복 확인
- REST rate limit(429): 조회 빈도 축소, 백오프/재시도, `REST_RATE_LIMIT_COOLDOWN` 처리 확인
- 인증(token): 토큰 발급/갱신 실패 시 APP_KEY/APP_SECRET 및 환경(mock/live) 재확인

상세 운영 절차: `docs/ops/kis-quote-runbook.md`

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
