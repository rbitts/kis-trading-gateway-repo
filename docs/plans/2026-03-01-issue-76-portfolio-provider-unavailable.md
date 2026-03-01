# Issue #76 Portfolio Endpoint Error Mapping Implementation Plan

> REQUIRED EXECUTION SKILL: `executing-plans`

**Goal:** 포트폴리오 provider가 구성되어 있어도 KIS 토큰/호출 실패 시 `/v1/balances`, `/v1/positions`가 500 대신 안정적인 503 + 에러코드로 응답하게 만든다.
**Architecture:** API 라우트 계층에서 portfolio provider 호출 예외를 제어된 도메인 에러로 매핑한다. 미구성(`PORTFOLIO_PROVIDER_NOT_CONFIGURED`)과 미가용(`PORTFOLIO_PROVIDER_UNAVAILABLE`)을 분리해 컨슈머가 복구 가능 시나리오를 구분할 수 있게 한다.
**Tech Stack:** FastAPI, requests exceptions mapping, unittest, gh PR/QA

---

### Task 1: 실패 재현 테스트 추가

**Files**
- Modify: `tests/test_balance_position_endpoints.py`

**Step 1 — Failing test**
```python
# provider가 requests.exceptions.HTTPError를 발생시키는 stub 추가
# balances/positions 각각 503 + PORTFOLIO_PROVIDER_UNAVAILABLE 기대
```

**Step 2 — Verify fail**
Run: `python3 -m unittest tests.test_balance_position_endpoints -v`
Expect: 신규 케이스 FAIL (현재 500)

**Step 3 — Minimal implementation**
- 없음 (테스트만 추가)

**Step 4 — Verify fail evidence**
Run: `python3 -m unittest tests.test_balance_position_endpoints -v`
Expect: FAIL 유지

**Step 5 — Checkpoint**
Run: `git add tests/test_balance_position_endpoints.py && git commit -m "test: cover portfolio provider unavailable mapping"`

---

### Task 2: 라우트 예외 매핑 구현

**Files**
- Modify: `app/api/routes.py`
- (optional) Modify: `docs/api/consumer-api-guide.md`

**Step 1 — Minimal implementation**
- portfolio 호출 helper를 추가해 `requests.exceptions.RequestException`/런타임 호출 에러를 503 `PORTFOLIO_PROVIDER_UNAVAILABLE`로 매핑
- 기존 미구성 503(`PORTFOLIO_PROVIDER_NOT_CONFIGURED`) 유지

**Step 2 — Verify pass (targeted)**
Run: `python3 -m unittest tests.test_balance_position_endpoints -v`
Expect: 전체 PASS

**Step 3 — Verify pass (full regression)**
Run: `python3 -m unittest discover -s tests -v`
Expect: 전체 PASS

**Step 4 — Checkpoint**
Run: `git add app/api/routes.py docs/api/consumer-api-guide.md tests/test_balance_position_endpoints.py && git commit -m "fix(api): map portfolio provider call failures to 503 unavailable"`

---

### Task 3: 증적/이슈 연계/머지

**Files**
- Create: `docs/evidence/2026-03-01-issue-76-verification.md`

**Step 1 — Evidence write**
- 실행 명령/결과/PASS 판정을 문서화

**Step 2 — PR + QA comment**
- PR 본문에 issue #76 링크
- QA 코멘트에 Command/Result/Verdict/Links 기록

**Step 3 — Merge**
- squash merge

**Step 4 — Post verify**
- 런타임 스모크에서 `/v1/balances`, `/v1/positions`가 provider failure 시 503 + code 반환 확인
