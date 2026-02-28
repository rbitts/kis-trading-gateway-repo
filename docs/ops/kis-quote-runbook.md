# KIS Quote WS/REST Runbook

운영 목적: `/v1/quotes*`가 장중/장외 모두에서 시세를 안정적으로 반환하도록 점검/대응한다.

## 0) Live validation 진입 게이트(고정)
1. 제한적 주문 검증 전 반드시 `GET /v1/session/live-readiness`를 먼저 확인한다.
2. `can_trade=true`일 때만 `docs/ops/kis-order-live-validation-checklist.md`의 "제한적 주문 허용 단계"로 진입한다.
3. `can_trade=false`이면 자격증명/WS blocker 해소 전까지 제한적 주문 검증 단계 진입 금지.

## 1) Env / Config 설정

필수 환경변수:

```bash
export KIS_APP_KEY="..."
export KIS_APP_SECRET="..."
export KIS_ACCOUNT_NO="12345678-01"
export KIS_ENV="live"   # mock | live
export KIS_MOCK=false
export KIS_WS_SYMBOLS="005930,000660"  # 런타임 WS subscribe 대상(콤마 구분)
```

안전 가드(실거래소 검증 시):
- 본 검증은 **read-only** 점검이다.
- **주문 금지**: 주문/정정/취소 API 호출 금지.
- 증거 로그/문서에는 APP_KEY/APP_SECRET/계좌번호를 마스킹한다.

앱 실행:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8890
```

## 2) Startup / Lifecycle 점검

기동 직후 확인:

```bash
curl -s http://127.0.0.1:8890/v1/session/status | jq
curl -s http://127.0.0.1:8890/v1/metrics/quote | jq
```

정상 기준:
- `/v1/session/status` 응답 OK
- startup/lifespan 로그에서 WS runtime activation(시작) 확인
- `/v1/metrics/quote`에 최소 키 존재: `cached_symbols`, `ws_messages`, `rest_fallbacks`, `ws_connected`, `last_ws_message_ts`
- 추가 키 확인: `ws_heartbeat_fresh`, `ws_reconnect_count`, `ws_last_error`

종료 동작:
- 앱 shutdown 시 WS client stop이 호출되도록 구현됨
- 배포/재기동 시 **graceful stop 후 재시작** 권장

### 2-1) Live WS 연결 검증 체크리스트
1. **Approval Key 발급 확인**
   - 기동 직후 로그에서 approval key 발급 성공 이벤트 확인
   - 실패 시 `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ENV(live)` 값 우선 재검증
2. **WebSocket 연결 + subscribe ACK 확인**
   - `/v1/metrics/quote`에서 `ws_connected=true` 확인
   - `KIS_WS_SYMBOLS`에 지정한 심볼 기준 subscribe ACK(성공 코드) 및 초기 실시간 메시지 수신 로그 확인
3. **WS 지표 정상성 확인**
   - `ws_messages`가 시간 경과에 따라 증가
   - `last_ws_message_ts`가 최근 시각으로 지속 갱신
   - `ws_heartbeat_fresh=true`, `ws_last_error` 비정상 값 없음

## 3) 장중/장외 기대 동작 (WS vs REST)

- 장중(09:00~15:30 KST):
  - WS cache fresh면 `source="kis-ws"`
  - WS stale/미수신이면 REST fallback(`source="kis-rest"`)
- 장외: REST 사용(`source="kis-rest"`)

빠른 확인:

```bash
curl -s "http://127.0.0.1:8890/v1/quotes/005930" | jq
curl -s "http://127.0.0.1:8890/v1/metrics/quote" | jq
```

판단 포인트:
- `rest_fallbacks` 증가: WS stale/미수신 또는 장외 REST 사용
- `ws_connected=false` + 장중: WS 경로 점검 필요
- 장중 `/v1/quotes/{symbol}` 결과가 `source="kis-ws"`면 runtime activation 정상

## 4) 장애 대응

### A. WS disconnect / 수신 중단
증상:
- 장중인데 `source="kis-rest"` 비율 급증
- `ws_connected=false` 또는 `last_ws_message_ts` 정체

대응:
1. `/v1/metrics/quote`로 현황 확인
2. 프로세스 재기동(WS 재연결 트리거)
3. 재기동 후 `ws_connected`, `ws_messages` 증가 확인
4. 복구 전까지 REST fallback으로 서비스 지속 (기능상 정상)
5. reconnect는 final attempt 실패 시 추가 대기(sleep) 없이 종료됨을 전제로 알람/재기동 정책 구성

### B. REST rate limit / 실패
증상:
- 장외 또는 fallback 시 quote 조회 실패/지연
- 429 이후 내부 `RestRateLimitCooldownError`가 API에서 `REST_RATE_LIMIT_COOLDOWN`(HTTP 503)으로 매핑되어 반환

대응:
1. 호출 빈도 축소(필요 심볼만 조회)
2. 짧은 재시도 간격 대신 백오프 적용(운영 레이어)
3. 일시 장애 시 마지막 캐시값 + 상태 모니터링
4. 지속 실패 시 KIS 앱키 한도/권한/네트워크 점검

### C. 인증 token 이슈
증상:
- REST 호출 전 토큰 발급 실패 또는 토큰 만료 후 연속 실패

대응:
1. KIS 앱키/시크릿 및 `KIS_ENV`(mock/live) 값 재검증
2. 토큰(token) 재발급 로그 확인
3. 발급 endpoint 접근성(방화벽/DNS/TLS) 점검
4. 복구 전까지 WS 지표(`ws_connected`, `last_ws_message_ts`) 기반 상태 판단

## 5) 주문 확장 API 운영 체크 (정정/취소)

기본 확인:

```bash
# 주문 생성 후
curl -s -X POST http://127.0.0.1:8890/v1/orders/{order_id}/modify \
  -H 'Content-Type: application/json' \
  -d '{"qty":2,"price":70100}' | jq

curl -s -X POST http://127.0.0.1:8890/v1/orders/{order_id}/cancel | jq
```

판단 포인트:
- 상태전이 위반 시 400 (`INVALID_TRANSITION`)
- terminal 주문 대상 정정/취소는 409
- 리스크 가드(`LIVE_DISABLED`, `DAILY_LIMIT_EXCEEDED`, `MAX_QTY_EXCEEDED`) 동작 여부 확인

주문 실브로커 검증은 `docs/ops/kis-order-live-validation-checklist.md`를 기준으로 수행한다.

## 6) 잔고/포지션 조회 체크

```bash
curl -s "http://127.0.0.1:8890/v1/balances?account_id=A1" | jq
curl -s "http://127.0.0.1:8890/v1/positions?account_id=A1" | jq
```

판단 포인트:
- 응답은 리스트 스키마 유지
- KIS 연동 미구성 시 `PORTFOLIO_PROVIDER_NOT_CONFIGURED`(HTTP 503) 반환

## 7) Reconciliation 워커 체크

- startup 시 reconciliation worker 시작
- shutdown 시 stop 호출
- 불일치 탐지 시 내부 상태 보정 이벤트 기록

운영 리스크:
- 이벤트 저장은 현재 in-memory(재기동 시 유실)
- 실브로커 상태 provider 고도화 필요

## 8) 회귀 검증

문서/설정 변경 후 전체 테스트:

```bash
python3 -m unittest discover -s tests -v
```

PASS를 배포 게이트로 사용한다.
