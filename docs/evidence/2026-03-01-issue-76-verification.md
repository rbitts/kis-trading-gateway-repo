# Issue #76 Verification

## Targeted tests
Command:
`python3 -m unittest tests.test_balance_position_endpoints -v`

Result:
- 6 tests run
- all OK
- provider call failure path now returns 503 + `PORTFOLIO_PROVIDER_UNAVAILABLE`

## Smoke + full regression
Command:
`python3 -m unittest tests.test_smoke -v && python3 -m unittest discover -s tests -v`

Result:
- smoke: 6 tests OK
- full: 118 tests OK

## Runtime repro/verify
Command:
`KIS_APP_KEY=dummy KIS_APP_SECRET=dummy KIS_ACCOUNT_NO=12345678-01 KIS_ENV=mock python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8890`

Calls:
- `GET /v1/balances?account_id=12345678-01`
- `GET /v1/positions?account_id=12345678-01`

Result:
- both return `503` with `{"detail":"PORTFOLIO_PROVIDER_UNAVAILABLE"}`
- previous uncaught 500 path is removed.

## Verdict
PASS
