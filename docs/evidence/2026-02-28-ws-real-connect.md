# WS Real Exchange Connect Evidence (Task2 baseline)

## Objective
실거래소 WS 연결/ACK 검증 전, 런타임 접근 가능 여부를 먼저 확인.

## Command
```bash
curl -sS http://127.0.0.1:8890/v1/session/status
curl -sS http://127.0.0.1:8890/v1/metrics/quote
```

## Output
```text
curl: (7) Failed to connect to 127.0.0.1 port 8890 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 8890 after 0 ms: Connection refused
```

## Result
- 현재 시점 기준 로컬 API 런타임 미기동으로 연결 검증 블로킹.
- 다음 단계(실연결/ACK 확인)는 앱을 live 모드로 기동한 뒤 동일 명령 재실행 필요.

## Next Action
1. `KIS_ENV=live`, `KIS_MOCK=false`로 앱 기동
2. `/v1/metrics/quote`에서 `ws_connected`, `ws_messages`, `ws_last_error` 확인
3. subscribe ACK 로그 첨부

---

## Live-mode startup attempt (same-day follow-up)

### Startup command
```bash
export KIS_ENV=live
export KIS_MOCK=false
uvicorn app.main:app --host 127.0.0.1 --port 8890
```

### Runtime check commands
```bash
curl -sS http://127.0.0.1:8890/v1/session/status
curl -sS http://127.0.0.1:8890/v1/metrics/quote
curl -sS http://127.0.0.1:8890/v1/quotes/005930
```

### Output summary
- `/v1/session/status`: 200 OK (session active)
- `/v1/metrics/quote`:
  - `ws_connected=false`
  - `ws_messages=0`
  - `ws_reconnect_count=3`
  - `ws_last_error` contains missing required live credentials (`KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`)
- `/v1/quotes/005930`: `source="kis-rest"`

### Blocker statement (updated)
- 앱은 기동되지만, **live 필수 자격증명 미주입으로 WS 연결/subscribe ACK 검증이 불가**.
- 현재 상태는 Task2의 "실연결 + ACK" PASS 조건 미충족.

### Required unblock
1. live env 주입: `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`
2. 재기동 후 `/v1/metrics/quote`에서 `ws_connected=true`, `ws_messages>0` 확인
3. subscribe ACK 로그 캡처 후 본 문서 업데이트
