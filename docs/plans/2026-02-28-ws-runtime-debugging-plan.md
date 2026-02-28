# WS Runtime Debugging Implementation Plan

> REQUIRED EXECUTION SKILL: `executing-plans`

**Goal:** WS 실시간 경로가 mock/live 모두에서 `ws_connected=false`, `ws_messages=0`, `source="kis-rest"`로 고정되는 원인을 재현 가능한 증거로 특정하고, 최소 수정으로 `source="kis-ws"` 경로를 복구한다.
**Architecture:** FastAPI `lifespan`에서 WS worker를 기동하고, WS 콜백이 quote cache/metrics를 갱신한 뒤 quote API가 장중 fresh 데이터면 `kis-ws`를 반환한다. 현재 실패는 (1) worker 미기동, (2) subscribe 미실행, (3) 메시지 파싱/반영 누락 중 하나일 가능성이 높다. 단계별 경계(기동→연결→구독→수신→캐시반영→응답선택)를 분리해 좁혀간다.
**Tech Stack:** Python 3.10, FastAPI, unittest, uvicorn, curl, rg, 로그 파일(/tmp)

---

### Task 1: WS 경계별 계측 포인트 확인(코드 읽기 + 실패 가설 확정)

**Files**
- Modify: 없음 (읽기/분석)
- Inspect: `app/main.py`, `app/services/*ws*`, `app/services/quote_gateway.py`, `app/api/routes.py`

**Step 1 — Failing check**
```bash
rg -n "run_with_reconnect|connect_once|subscribe|on_message|ws_connected|ws_messages|source" app
```

**Step 2 — Verify fail**
Run: 위 명령
Expect: 경계별 함수/호출순서가 산재되어 있어 단일 원인 파악 불가 상태 확인

**Step 3 — Minimal implementation (분석 산출물)
**
- 아래 가설 3개를 문서화:
  1) lifespan에서 worker 스레드가 실제 루프 진입 전 종료됨
  2) subscribe ACK/메시지 콜백이 metrics에 반영되지 않음
  3) quote 선택 로직이 WS fresh를 제외하고 REST로 고정됨

**Step 4 — Verify pass**
Run:
```bash
python3 - <<'PY'
print('HYPOTHESIS_READY')
PY
```
Expect: `HYPOTHESIS_READY`

**Step 5 — Checkpoint**
- 아직 커밋 없음 (Task2에서 증거 문서와 함께 커밋)

---

### Task 2: 런타임 관측 강화(로그 증거 추가, 동작 변경 없음)

**Files**
- Modify: `app/main.py`, `app/services/...(ws worker/client 관련 파일)`
- Test: `tests/test_quote_e2e_mock_kis.py` (기존 통과 유지)

**Step 1 — Failing test**
```bash
export KIS_ENV=mock
export KIS_ACCOUNT_NO="${KIS_CANO}-${KIS_ACNT_PRDT_CD_KR:-01}"
timeout 20s uvicorn app.main:app --host 127.0.0.1 --port 8890
```

**Step 2 — Verify fail**
Run (별도 터미널):
```bash
curl -sS http://127.0.0.1:8890/v1/metrics/quote
```
Expect: `ws_connected=false`, `ws_messages=0` 상태에서 원인 로그가 부족

**Step 3 — Minimal implementation**
- 구조 로그 4개 추가 (민감정보 마스킹):
  - worker start/stop
  - WS connect attempt/result
  - subscribe request/ack result
  - first message ingest

**Step 4 — Verify pass**
Run:
```bash
(timeout 20s uvicorn app.main:app --host 127.0.0.1 --port 8890 > /tmp/ws_debug.log 2>&1 &) ; sleep 5; rg -n "ws_worker_start|ws_connect|ws_subscribe|ws_first_message" /tmp/ws_debug.log
```
Expect: 최소 2개 이상 단계 로그 확인

**Step 5 — Checkpoint**
Run: `git add app/main.py app/services/* && git commit -m "chore(ws): add runtime stage logs for ws debugging"`

---

### Task 3: 원인 분기 실험 (mock/live 동일키 비교 자동화)

**Files**
- Create: `scripts/ws_compare_env_modes.sh`
- Create: `docs/evidence/2026-02-28-ws-debug-compare-mock-live.md`

**Step 1 — Failing check**
```bash
bash scripts/ws_compare_env_modes.sh
```

**Step 2 — Verify fail**
Expect: 현재와 같이 mock/live 모두 `ws_connected=false`, `ws_messages=0` 재현

**Step 3 — Minimal implementation**
- 비교 스크립트에서 동일 키/계정으로 `KIS_ENV`만 변경해 두 번 기동
- 각 모드에서 metrics 2회 + quote 1회 캡처 후 표 형태로 evidence 저장

**Step 4 — Verify pass**
Run:
```bash
rg -n "mock|live|ws_connected|ws_messages|source" docs/evidence/2026-02-28-ws-debug-compare-mock-live.md
```
Expect: 모드별 비교 라인 생성

**Step 5 — Checkpoint**
Run: `git add scripts/ws_compare_env_modes.sh docs/evidence/2026-02-28-ws-debug-compare-mock-live.md && git commit -m "docs(debug): add mock-live ws compare evidence"`

---

### Task 4: 원인점 최소 수정 (가설 1개만 고치기)

**Files**
- Modify: Task2/3 결과로 특정된 최소 파일
- Test: `tests/test_quote_e2e_mock_kis.py`, `tests/test_kis_ws_live_client.py`

**Step 1 — Failing test**
```bash
python3 -m unittest tests/test_quote_e2e_mock_kis.py -v
```

**Step 2 — Verify fail**
Expect: WS 경로 관련 테스트 또는 수동 재현에서 실패 유지

**Step 3 — Minimal implementation**
- 원인 1개만 수정 (예: subscribe 호출 누락/콜백 누락/상태 동기화 누락)

**Step 4 — Verify pass**
Run:
```bash
python3 -m unittest tests/test_quote_e2e_mock_kis.py -v
python3 -m unittest tests/test_kis_ws_live_client.py -v
```
Expect: 관련 테스트 PASS

**Step 5 — Checkpoint**
Run: `git add ... && git commit -m "fix(ws): restore ws ingest path for runtime worker"`

---

### Task 5: 최종 회귀 + 운영 판정 업데이트

**Files**
- Modify: `docs/evidence/2026-02-28-ws-real-final-report.md`

**Step 1 — Failing check**
```bash
curl -sS http://127.0.0.1:8890/v1/metrics/quote
```

**Step 2 — Verify fail**
Expect: 수정 전 기준값 기록

**Step 3 — Minimal implementation**
- 최종 관측값 반영해 Go/No-Go 재판정

**Step 4 — Verify pass**
Run:
```bash
python3 -m unittest discover -s tests -v
```
Expect: 전체 PASS

**Step 5 — Checkpoint**
Run: `git add docs/evidence/2026-02-28-ws-real-final-report.md && git commit -m "docs(evidence): update ws final decision after runtime debugging"`

---

## Handoff
1) Current session execution: 지금 이 세션에서 Task1부터 연속 수행
2) Subagent execution: coder(구현) + qa(검증)로 Task별 PR 사이클 유지

권장: 2) (현재 운영 원칙과 동일한 PR/QA/merge 파이프라인 유지)
