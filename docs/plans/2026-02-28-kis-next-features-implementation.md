# KIS Next Features (Risk-first, Contract-first) Implementation Plan

> REQUIRED EXECUTION SKILL: `executing-plans`

**Goal:** 리스크 우선 정책을 반영한 주문 확장(정정/취소), 잔고/포지션 조회, 리컨실리에이션 기능을 계약 기반으로 안전하게 추가한다.
**Architecture:** 기존 FastAPI + service/adaptor 구조를 유지하며, OpenAPI 계약을 먼저 확정하고 테스트를 통해 상태전이/에러코드/멱등성을 잠근다. 타팀 엔드포인트 명명은 별도 매핑 가능하도록 스키마와 operationId 중심으로 문서화한다.
**Tech Stack:** FastAPI, Pydantic, unittest, existing KIS REST/WS adapters

---

### Task 1: OpenAPI 계약 초안(리스크 + 확장 주문) 고정

**Files**
- Create: `docs/api/openapi-next.yaml`
- Modify: `docs/ops/order-api-contract.md`
- Test: `tests/test_api_contract_next.py`

**Step 1 — Failing test**
```python
# tests/test_api_contract_next.py
# openapi-next.yaml 존재 + 필수 schema/operationId/assert
```

**Step 2 — Verify fail**
Run: `python3 -m unittest tests.test_api_contract_next -v`
Expect: `FAIL (file/schema missing)`

**Step 3 — Minimal implementation**
- openapi에 아래 operationId/schema 추가
  - createOrder, cancelOrder, modifyOrder, getBalances, getPositions, reconcileOrders
  - Error schema(code, message, retryable)

**Step 4 — Verify pass**
Run: `python3 -m unittest tests.test_api_contract_next -v`
Expect: `OK`

**Step 5 — Checkpoint**
Run: `git add docs/api/openapi-next.yaml docs/ops/order-api-contract.md tests/test_api_contract_next.py && git commit -m "docs: add contract-first openapi for next KIS features"`

### Task 2: 리스크 정책 확장 (주문/정정/취소 공통 가드)

**Files**
- Modify: `app/services/risk_policy.py`
- Modify: `app/api/routes.py`
- Test: `tests/test_risk_policy_extended.py`

**Step 1 — Failing test**
- live 주문 차단 플래그, 일일 주문횟수, 최대수량, 정정/취소 가능 상태 검증 테스트 추가

**Step 2 — Verify fail**
Run: `python3 -m unittest tests.test_risk_policy_extended -v`
Expect: `FAIL`

**Step 3 — Minimal implementation**
- 리스크 결과코드 추가: `LIVE_DISABLED`, `DAILY_LIMIT_EXCEEDED`, `INVALID_TRANSITION`
- 주문/정정/취소에 공통 risk check 적용

**Step 4 — Verify pass**
Run: `python3 -m unittest tests.test_risk_policy_extended -v`
Expect: `OK`

**Step 5 — Checkpoint**
Run: `git add app/services/risk_policy.py app/api/routes.py tests/test_risk_policy_extended.py && git commit -m "feat: extend risk guard for order modify/cancel"`

### Task 3: 정정/취소 주문 API + 상태전이 추가

**Files**
- Modify: `app/services/order_queue.py`
- Modify: `app/api/routes.py`
- Modify: `app/integrations/kis_rest.py`
- Test: `tests/test_order_modify_cancel_flow.py`

**Step 1 — Failing test**
- `POST /v1/orders/{order_id}/cancel`
- `POST /v1/orders/{order_id}/modify`
- 상태전이 위반 시 400/409 테스트

**Step 2 — Verify fail**
Run: `python3 -m unittest tests.test_order_modify_cancel_flow -v`
Expect: `FAIL`

**Step 3 — Minimal implementation**
- 상태 추가: `CANCEL_PENDING`, `MODIFY_PENDING`, `CANCELED`
- KIS adapter 메서드 추가(취소/정정 요청)

**Step 4 — Verify pass**
Run: `python3 -m unittest tests.test_order_modify_cancel_flow -v`
Expect: `OK`

**Step 5 — Checkpoint**
Run: `git add app/services/order_queue.py app/api/routes.py app/integrations/kis_rest.py tests/test_order_modify_cancel_flow.py && git commit -m "feat: add order cancel/modify flow with state transitions"`

### Task 4: 잔고/포지션 조회 API 추가

**Files**
- Modify: `app/integrations/kis_rest.py`
- Modify: `app/api/routes.py`
- Create: `app/schemas/portfolio.py`
- Test: `tests/test_balance_position_endpoints.py`

**Step 1 — Failing test**
- `/v1/balances`, `/v1/positions` 응답 스키마 테스트

**Step 2 — Verify fail**
Run: `python3 -m unittest tests.test_balance_position_endpoints -v`
Expect: `FAIL`

**Step 3 — Minimal implementation**
- KIS 잔고/보유종목 조회 응답 정규화
- Pydantic schema로 응답 계약 고정

**Step 4 — Verify pass**
Run: `python3 -m unittest tests.test_balance_position_endpoints -v`
Expect: `OK`

**Step 5 — Checkpoint**
Run: `git add app/integrations/kis_rest.py app/api/routes.py app/schemas/portfolio.py tests/test_balance_position_endpoints.py && git commit -m "feat: add balances/positions endpoints"`

### Task 5: 리컨실리에이션 워커 추가

**Files**
- Create: `app/services/reconciliation.py`
- Modify: `app/main.py`
- Test: `tests/test_reconciliation_worker.py`

**Step 1 — Failing test**
- 내부 주문 상태 vs 브로커 상태 diff 검출/보정 테스트

**Step 2 — Verify fail**
Run: `python3 -m unittest tests.test_reconciliation_worker -v`
Expect: `FAIL`

**Step 3 — Minimal implementation**
- 주기 워커 추가(초기: 수동 트리거 가능)
- 불일치 이벤트 메트릭/로그 기록

**Step 4 — Verify pass**
Run: `python3 -m unittest tests.test_reconciliation_worker -v`
Expect: `OK`

**Step 5 — Checkpoint**
Run: `git add app/services/reconciliation.py app/main.py tests/test_reconciliation_worker.py && git commit -m "feat: add reconciliation worker for order consistency"`

### Task 6: 회귀 검증 + 문서 동기화

**Files**
- Modify: `README.md`
- Modify: `docs/ops/kis-quote-runbook.md`
- Test: `tests/test_smoke.py`

**Step 1 — Failing test**
- 신규 API가 README/runbook에 명시되었는지 문서 검증 테스트 추가

**Step 2 — Verify fail**
Run: `python3 -m unittest tests.test_smoke -v`
Expect: `FAIL`

**Step 3 — Minimal implementation**
- 실행 예시/에러코드/운영 체크리스트 업데이트

**Step 4 — Verify pass**
Run: `python3 -m unittest discover -s tests -v`
Expect: `OK`

**Step 5 — Checkpoint**
Run: `git add README.md docs/ops/kis-quote-runbook.md tests/test_smoke.py && git commit -m "docs: sync runbook and readme for next features"`

---

## 실행 모드 선택
1) 현재 세션에서 순차 실행 (Task 1부터)
2) 서브에이전트 위임 실행 (coder 구현 + qa 검증, task 단위 PR)

## 완료 기준
- Task 1~6 모두 검증 PASS
- 문서(OpenAPI/Runbook)와 코드 동작 일치
- 리스크 가드가 live 경로에서 기본 차단/제한 정책을 보장
