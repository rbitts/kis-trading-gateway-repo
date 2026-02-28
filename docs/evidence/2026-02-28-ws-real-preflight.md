# WS Real Exchange Preflight Evidence (2026-02-28)

## Command (before)
```bash
rg -n "KIS_MOCK=false|KIS_WS_SYMBOLS|주문 금지|read-only" docs/ops/kis-quote-runbook.md
```

## Output (before)
```text
14:export KIS_WS_SYMBOLS="005930,000660"  # 런타임 WS subscribe 대상(콤마 구분)
51:   - `KIS_WS_SYMBOLS`에 지정한 심볼 기준 subscribe ACK(성공 코드) 및 초기 실시간 메시지 수신 로그 확인
```

## Changes
- Added live-mode preflight vars:
  - `KIS_ENV="live"`
  - `KIS_MOCK=false`
- Added safety guard text:
  - read-only validation
  - 주문 금지
  - secret/account masking rule

## Command (after)
```bash
rg -n "KIS_MOCK=false|KIS_WS_SYMBOLS|주문 금지|read-only" docs/ops/kis-quote-runbook.md
```

## Output (after)
```text
14:export KIS_MOCK=false
15:export KIS_WS_SYMBOLS="005930,000660"  # 런타임 WS subscribe 대상(콤마 구분)
19:- 본 검증은 **read-only** 점검이다.
20:- **주문 금지**: 주문/정정/취소 API 호출 금지.
57:   - `KIS_WS_SYMBOLS`에 지정한 심볼 기준 subscribe ACK(성공 코드) 및 초기 실시간 메시지 수신 로그 확인
```
