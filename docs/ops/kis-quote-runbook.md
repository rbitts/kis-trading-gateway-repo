# KIS Quote WS/REST Runbook

운영 목적: `/v1/quotes*`가 장중/장외 모두에서 시세를 안정적으로 반환하도록 점검/대응한다.

## 1) Env / Config 설정

필수 환경변수:

```bash
export KIS_APP_KEY="..."
export KIS_APP_SECRET="..."
export KIS_ACCOUNT_NO="12345678-01"
export KIS_ENV="mock"   # mock | live
```

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
- `/v1/metrics/quote`에 최소 키 존재: `cached_symbols`, `ws_messages`, `rest_fallbacks`, `ws_connected`, `last_ws_message_ts`

종료 동작:
- 앱 shutdown 시 WS client stop이 호출되도록 구현됨
- 배포/재기동 시 **graceful stop 후 재시작** 권장

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

### B. REST rate limit / 실패
증상:
- 장외 또는 fallback 시 quote 조회 실패/지연

대응:
1. 호출 빈도 축소(필요 심볼만 조회)
2. 짧은 재시도 간격 대신 백오프 적용(운영 레이어)
3. 일시 장애 시 마지막 캐시값 + 상태 모니터링
4. 지속 실패 시 KIS 앱키 한도/권한/네트워크 점검

## 5) 회귀 검증

문서/설정 변경 후 전체 테스트:

```bash
python3 -m unittest discover -s tests -v
```

PASS를 배포 게이트로 사용한다.
