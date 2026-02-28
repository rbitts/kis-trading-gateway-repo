# WS Real Exchange Quote Source Evidence (Task3)

## Objective
장중 실시간 quote 경로에서 `source="kis-ws"` 달성 여부 확인.

## Commands
```bash
export KIS_ENV=live
export KIS_MOCK=false

# app runtime (30s)
timeout 30s uvicorn app.main:app --host 127.0.0.1 --port 8890

# 5회 반복 조회
for i in 1 2 3 4 5; do
  date '+%T'
  curl -sS http://127.0.0.1:8890/v1/quotes/005930
  sleep 3
done

curl -sS http://127.0.0.1:8890/v1/metrics/quote
```

## Output Summary
- quote 5회 모두 `source="kis-rest"`
- `/v1/metrics/quote`:
  - `ws_connected=false`
  - `ws_messages=0`
  - `rest_fallbacks=5`
  - `ws_last_error`: live credential missing (`KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`)

## Result
- Task3 성공 조건(장중 `source="kis-ws"` 관측) **미충족**.
- 현재 환경은 live credentials 미주입으로 WS 경로가 비활성 상태.

## Unblock Required
1. live credential 주입 (`KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`)
2. 재기동 후 `/v1/metrics/quote`에서 `ws_connected=true`, `ws_messages>0` 확인
3. 동일 루프 재실행 시 최소 3회 이상 `source="kis-ws"` 확인
