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
