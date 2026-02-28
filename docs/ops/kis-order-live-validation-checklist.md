# KIS Order Live Validation Checklist

목적: 실브로커 환경에서 주문 연동을 단계적으로 검증하되, 위험을 최소화하고 롤백 가능성을 확보한다.

## 1) 사전 안전 가드 (주문 금지 단계)
- [ ] `GET /v1/session/live-readiness` 선확인
- [ ] `can_trade=true` 확인 전에는 제한적 주문 검증 단계로 진입하지 않음
- [ ] `can_trade=false`이면 자격증명/WS blocker 해소 전까지 주문 검증 금지
- [ ] `KIS_ENV=live` 외 민감 값(APP_KEY/APP_SECRET/계좌) 마스킹 확인
- [ ] 운영 공지/변경 윈도우 승인 확인
- [ ] **주문/정정/취소 API 호출 금지** 원칙 확인
- [ ] `/v1/session/status`, `/v1/metrics/quote` 정상 응답 확인
- [ ] WS 연결 지표(`ws_connected`, `last_ws_message_ts`, `ws_heartbeat_fresh`) 정상 확인

## 2) Read-only 점검 증거 캡처
- [ ] quote 조회 결과(`source`, `price`, `ts`) 캡처
- [ ] quote metrics 스냅샷(`ws_messages`, `rest_fallbacks`, `ws_reconnect_count`) 캡처
- [ ] 장애 징후(`ws_last_error`, REST 429, token 실패) 유무 기록

## 3) 제한적 주문 허용 단계 (승인 후)
- [ ] 운영자 승인 기록(시간/담당자) 확보
- [ ] 최소 주문 단위(1주) + 제한 심볼 1개로 테스트
- [ ] Idempotency-Key 고정 및 주문 요청/응답 원문 보관
- [ ] 주문 상태 조회(`/v1/orders/{order_id}`)로 최종 상태 확인
- [ ] 필요 시 정정/취소 API 테스트는 별도 승인 후 진행

## 4) 롤백 절차
1. 신규 주문 트래픽 즉시 중단
2. 워커/프로세스 재기동으로 WS 상태 초기화
3. 문제 구간 로그/메트릭 스냅샷 보존
4. `KIS_ENV=mock` 전환 또는 read-only 모드로 회귀
5. 원인 분석 전까지 주문 허용 단계 재진입 금지

## 5) 증거 템플릿
```text
[Validation Window]
- Date/Time(KST):
- Operator:
- Env: live

[Checks]
- Session status: PASS/FAIL
- Quote metrics health: PASS/FAIL
- Read-only quote capture: PASS/FAIL
- Limited order validation (if approved): PASS/FAIL

[Incidents]
- ws_last_error:
- 429 cooldown observed:
- token issue observed:

[Decision]
- GO / NO-GO
- Follow-up actions:
```
