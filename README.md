# KIS Trading Gateway

KIS 단일 세션 제약을 만족하는 **시세+주문 게이트웨이** 서비스.

## MVP Scope
- Quote read API (`/v1/quotes`)
- Order command API (`/v1/orders`) with idempotency key
- Session status API (`/v1/session/status`)
- In-memory queue worker skeleton

## Run
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8890
```
