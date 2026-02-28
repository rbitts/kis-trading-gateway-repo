# WS Real Exchange Validation Final Report (2026-02-28)

## 검증 범위/환경
- 범위: `docs/plans/2026-02-28-kis-ws-real-exchange-validation.md` + `docs/plans/2026-02-28-ws-runtime-debugging-plan.md` 실행 증거 기반 종합 판정
- 환경: 로컬 런타임 `127.0.0.1:8890`, `KIS_ENV=live`, `KIS_MOCK=false`
- 제약: 장종료 시간대(16:00+) 검증으로 체결성 quote payload 유입량 제한 가능

## 태스크별 요약
1. **Task1 (preflight safety)**: PASS
   - read-only/주문 금지/마스킹 규칙 문서화 완료
2. **Task2 (connect + ACK/control)**: PASS
   - WS worker 시작/연결/subscribe/control 수신 로그 확인
   - `ws_connected=true` 상태 동기화 복구 완료
3. **Task3 (source="kis-ws")**: PARTIAL
   - mock/live 모두 연결은 성공했으나 quote payload 미수신으로 `source="kis-rest"` 유지
4. **Task4 (reconnect baseline)**: PARTIAL
   - 연결 상태는 유지되나 quote 메시지 누적으로 이어지지 않음

## 핵심 관측치
- `/v1/metrics/quote` (mock/live A/B 동일)
  - `ws_connected=true`
  - `ws_messages=0`
  - `ws_last_error=None`
- 서버 로그
  - `[WS][ws_connect_result] status=open`
  - `[WS][ws_subscribe] symbol=005930`
  - `[WS][ws_message_skip] reason=missing symbol in payload` (control/ACK로 해석)
- `/v1/quotes/005930`
  - `source="kis-rest"` 지속

## 리스크
- 연결은 살아있지만 quote payload가 없어 WS-first 소스 전환(`kis-ws`)을 입증하지 못함.
- 장종료 시간대 검증/실키 권한(TR/상품 권한) 이슈가 겹치면 원인 분리가 어려움.

## 판정 (Go/No-Go)
- **No-Go 유지** (연결 복구는 확인했으나 `ws_messages>0` 및 `source="kis-ws"` 미충족)

## Go 전환 조건 (즉시 실행 체크리스트)
1. 장중(09:00~15:30) 동일 시나리오 재실행
2. 런타임 재기동 후 `/v1/metrics/quote`에서
   - `ws_connected=true`
   - `ws_messages>0`
   - `ws_heartbeat_fresh=true`
3. `/v1/quotes/{symbol}` 장중 3회 이상 `source="kis-ws"` 확인
4. 필요 시 TR_ID/구독 채널 권한 점검(계좌/앱 권한)
5. reconnect 이벤트 후 회복 시간(TTR) 기록

## 관련 증거 문서
- `docs/evidence/2026-02-28-ws-real-preflight.md`
- `docs/evidence/2026-02-28-ws-real-connect.md`
- `docs/evidence/2026-02-28-ws-real-quote-source.md`
- `docs/evidence/2026-02-28-ws-real-reconnect.md`
- `docs/evidence/2026-02-28-ws-debug-compare-mock-live.md`
