# WS Real Exchange Validation Final Report (2026-02-28)

## 검증 범위/환경
- 범위: `docs/plans/2026-02-28-kis-ws-real-exchange-validation.md` Task1~Task4 실행 증거 기반 종합 판정
- 환경: 로컬 런타임 `127.0.0.1:8890`, `KIS_ENV=live`, `KIS_MOCK=false`
- 제약: 실제 live credential(`KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`) 미주입 상태

## 태스크별 요약
1. **Task1 (preflight safety)**: PASS
   - read-only/주문 금지/마스킹 규칙 문서화 완료
2. **Task2 (connect + ACK)**: PARTIAL
   - 앱 기동/metrics 조회는 가능
   - WS 실연결/ACK은 credential 부재로 미달
3. **Task3 (source="kis-ws")**: FAIL
   - 5회 샘플 모두 `source="kis-rest"`
4. **Task4 (reconnect baseline)**: PARTIAL
   - `ws_reconnect_count` 증가는 관측
   - `ws_connected=true` 회복은 미달

## 핵심 관측치
- `/v1/metrics/quote`
  - `ws_connected=false`
  - `ws_messages=0`
  - `ws_last_error`:
    - `KIS_APP_KEY`/`KIS_APP_SECRET`/`KIS_ACCOUNT_NO` validation error
- `/v1/quotes/005930`
  - `source="kis-rest"` 지속

## 리스크
- 현재 상태에서 실거래소 WS 경로가 비활성이라 장중 WS-first 운영 검증 실패.
- 실키 주입 전까지 실시간 경로 품질(SLA/TTR) 실측 불가.

## 판정 (Go/No-Go)
- **No-Go** (실거래소 WS 운영 검증 완료 기준 미충족)

## Go 전환 조건 (즉시 실행 체크리스트)
1. live credential 주입 (`KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`)
2. 런타임 재기동 후 `/v1/metrics/quote`에서
   - `ws_connected=true`
   - `ws_messages>0`
   - `ws_heartbeat_fresh=true`
3. `/v1/quotes/{symbol}` 장중 3회 이상 `source="kis-ws"` 확인
4. reconnect 이벤트 후 회복 시간(TTR) 기록

## 관련 증거 문서
- `docs/evidence/2026-02-28-ws-real-preflight.md`
- `docs/evidence/2026-02-28-ws-real-connect.md`
- `docs/evidence/2026-02-28-ws-real-quote-source.md`
- `docs/evidence/2026-02-28-ws-real-reconnect.md`
