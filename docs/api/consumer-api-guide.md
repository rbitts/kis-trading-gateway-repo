# Consumer API Guide

이 문서는 KIS Trading Gateway 컨슈머를 위한 단일 가이드입니다.

## 0) Quick Start (5분)
1. 서버 실행
2. `GET /v1/session/status` 확인
3. `GET /v1/quotes/{symbol}` 조회
4. `POST /v1/orders` 주문 생성
5. `GET /v1/orders/{order_id}` 상태 확인

## 1) Base URL
- Local: `http://127.0.0.1:8890/v1`

## 2) Auth / Headers
- `Content-Type: application/json`
- `Idempotency-Key` (주문 생성 시 필수)

## 3) First Flow Preview
- Quotes → Orders → Order Status

## 4) Reference (Appendix)
- 상세 엔드포인트/에러/운영 체크는 아래 부록 섹션에서 확장 예정
