# WS Real Exchange Reconnect Evidence (Task4 baseline)

## Objective
실거래소 모드에서 reconnect 관측/회복 지표를 점검.

## Commands
```bash
export KIS_ENV=live
export KIS_MOCK=false

timeout 25s uvicorn app.main:app --host 127.0.0.1 --port 8890

curl -sS http://127.0.0.1:8890/v1/metrics/quote   # t1
sleep 8
curl -sS http://127.0.0.1:8890/v1/metrics/quote   # t2
```

## Output Summary
- t1 metrics:
  - `ws_connected=false`
  - `ws_heartbeat_fresh=false`
  - `ws_reconnect_count=2`
- t2 metrics:
  - `ws_connected=false`
  - `ws_heartbeat_fresh=false`
  - `ws_reconnect_count=4` (증가 확인)
- `ws_last_error`: live credential missing validation errors (`KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`)

## Result
- reconnect 루프 카운트 증가는 관측됨.
- 다만 live credential 미주입으로 실제 WS 연결 회복(`ws_connected=true`)까지는 도달하지 못함.

## Unblock Required
1. live credentials 주입
2. 재기동 후 `ws_connected=true`, `ws_heartbeat_fresh=true` 확인
3. reconnect 발생 후 회복 시간(TTR) 기록
