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
export KIS_WS_SYMBOLS="005930,000660"  # 런타임 WS subscribe 대상(콤마 구분)
```

### Mock env 파일로 실행 (권장)
```bash
cp env/mock.env.example env/mock.env
# env/mock.env 값 채운 뒤
./scripts/run_mock_server.sh
```

> `env/mock.env`가 없으면 `KIS_MOCK_APP_KEY`, `KIS_MOCK_APP_SECRET`, `KIS_MOCK_CANO`, `KIS_MOCK_ACNT_PRDT_CD_KR` 환경변수를 fallback으로 사용합니다.

### Startup/Lifecycle 점검
```bash
curl -s http://127.0.0.1:8890/v1/session/status | jq
curl -s http://127.0.0.1:8890/v1/metrics/quote | jq
```
- startup(lifespan)에서 `KIS_WS_SYMBOLS` 기준 WS subscribe 시작, shutdown(lifespan)에서 stop 수행
- `rest_fallbacks`, `ws_connected`, `last_ws_message_ts`를 운영 지표로 확인
- `ws_heartbeat_fresh`, `ws_reconnect_count`, `ws_last_error`로 reconnect 상태를 함께 점검
- REST 429 발생 시 `RestRateLimitCooldownError` → `REST_RATE_LIMIT_COOLDOWN`(HTTP 503) 응답 정책 확인

### Live WS 연결 검증 체크리스트
- [ ] **Approval Key 발급 확인**: 기동 직후 로그에서 approval key 발급 성공 여부 확인(실패 시 APP_KEY/APP_SECRET/KIS_ENV 우선 점검)
- [ ] **WebSocket 연결 + subscribe ACK 확인**: `ws_connected=true` 확인 후, subscribe 응답 ACK(성공 코드)와 초기 체결/호가 수신 로그 확인
- [ ] **WS 지표 확인**: `/v1/metrics/quote`에서 `ws_messages` 증가, `last_ws_message_ts` 갱신, `ws_heartbeat_fresh=true`, `ws_last_error` 공백/안정 상태 확인
- [ ] **런타임 활성화 확인**: `/v1/quotes/{symbol}` 응답에서 장중 기준 `source="kis-ws"` 확인(예: `005930`), 미활성 시 `KIS_WS_SYMBOLS`/lifespan 기동 로그 재확인

### 장중/장외 동작 기대치
- 장중(09:00~15:30 KST): WS fresh면 `kis-ws`, stale/미수신이면 `kis-rest`
- 장외: `kis-rest`

### 장애 대응 핵심
- WS 끊김(reconnect): metrics 확인 → 프로세스 재기동/재연결 → `ws_connected`, `ws_heartbeat_fresh`, `ws_reconnect_count` 회복 확인
- reconnect backoff는 final attempt 실패 후 추가 sleep 없이 종료되도록 동작
- REST rate limit(429): 조회 빈도 축소, 백오프/재시도, `REST_RATE_LIMIT_COOLDOWN` 처리 확인
- 인증(token): 토큰 발급/갱신 실패 시 APP_KEY/APP_SECRET 및 환경(mock/live) 재확인

### Live 주문 검증 진입 게이트(고정)
1. `GET /v1/session/live-readiness`를 먼저 확인한다.
2. `can_trade=true`일 때만 제한적 주문 검증 단계로 진입한다.
3. `can_trade=false`이면 자격증명/WS blocker를 해소하기 전까지 **제한적 주문 검증 단계에 진입하지 않는다**.

상세 운영 절차: `docs/ops/kis-quote-runbook.md`
주문 실검증 체크리스트: `docs/ops/kis-order-live-validation-checklist.md`

## API Docs
- Consumer Markdown Guide: `docs/api/consumer-api-guide.md`
- Raw specs: `./docs/site/api/openapi-live.json`, `./docs/site/api/openapi-next.yaml`

## Quick API Check
```bash
# session state
curl -s http://127.0.0.1:8890/v1/session/status | jq

# quote
curl -s "http://127.0.0.1:8890/v1/quotes/005930" | jq

# BUY 주문 + 상태조회
BUY_ORDER_ID=$(curl -s -X POST http://127.0.0.1:8890/v1/orders \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: sample-buy-k1' \
  -d '{"account_id":"A1","symbol":"005930","side":"BUY","qty":1,"price":70000,"order_type":"LIMIT"}' | jq -r '.order_id')
curl -s http://127.0.0.1:8890/v1/orders/${BUY_ORDER_ID} | jq

# BUY 멱등성 재호출(동일 key+동일 body)
curl -s -X POST http://127.0.0.1:8890/v1/orders \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: sample-buy-k1' \
  -d '{"account_id":"A1","symbol":"005930","side":"BUY","qty":1,"price":70000,"order_type":"LIMIT"}' | jq

# SELL 주문 + 상태조회
SELL_ORDER_ID=$(curl -s -X POST http://127.0.0.1:8890/v1/orders \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: sample-sell-k1' \
  -d '{"account_id":"A1","symbol":"005930","side":"SELL","qty":1,"price":70000,"order_type":"LIMIT"}' | jq -r '.order_id')
curl -s http://127.0.0.1:8890/v1/orders/${SELL_ORDER_ID} | jq

# SELL 멱등성 충돌(동일 key+상이 body => 409)
curl -s -X POST http://127.0.0.1:8890/v1/orders \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: sample-sell-k1' \
  -d '{"account_id":"A1","symbol":"005930","side":"SELL","qty":2,"price":70000,"order_type":"LIMIT"}' | jq

# 주문 정정/취소
curl -s -X POST http://127.0.0.1:8890/v1/orders/${BUY_ORDER_ID}/modify \
  -H 'Content-Type: application/json' \
  -d '{"qty":2,"price":70100}' | jq
curl -s -X POST http://127.0.0.1:8890/v1/orders/${BUY_ORDER_ID}/cancel | jq

# 잔고/포지션
curl -s "http://127.0.0.1:8890/v1/balances?account_id=A1" | jq
curl -s "http://127.0.0.1:8890/v1/positions?account_id=A1" | jq

# metrics
curl -s http://127.0.0.1:8890/v1/metrics/quote | jq
curl -s http://127.0.0.1:8890/v1/metrics/order | jq
```

## Reconciliation Worker
- 앱 startup 시 reconciliation worker가 시작되고 shutdown 시 종료됩니다.
- 현재는 in-memory 주문 상태와 브로커 상태를 비교/보정하는 기반을 제공하며,
  브로커 상태 provider 연동 고도화는 후속 작업입니다.

## Test
```bash
python -m unittest discover -s tests -v
```
