# KIS Trading Gateway 확장 구조설계 (Risk-first, Contract-first)

## 목표
정정/취소 주문, 잔고/포지션 조회, 리컨실리에이션을 기존 구조를 크게 깨지 않고 점진적으로 추가한다. 구현 우선순위는 리스크 가드 강화를 최상위로 둔다.

## 설계 원칙
- Contract-first: OpenAPI 확정 → 테스트 작성 → 구현
- Risk-first: 주문 경로의 검증/차단 정책을 기능 추가보다 먼저 반영
- Incremental: 기존 `app/api`, `app/services`, `app/integrations` 구조 유지
- Idempotent-by-default: 주문/정정/취소 모두 멱등키 기반

## 컴포넌트 경계
1. API Layer (`app/api/routes.py`)
   - 계약 검증(필수 필드, enum, 상태 가능 전이)
   - 에러 매핑(400/409/422/503)
2. Domain Service Layer (`app/services/*`)
   - `order_queue`: 상태 전이, 재시도, terminal 처리
   - `risk_policy`: side/time/notional/position 기반 정책
   - `reconciliation`: 브로커 상태와 내부 상태 비교/보정
3. Broker Adapter Layer (`app/integrations/kis_rest.py`, `kis_ws.py`)
   - KIS API 호출/응답 정규화
   - 에러 코드 분류(RATE_LIMIT/AUTH/INVALID_ORDER)
4. Persistence/In-memory State
   - 현재 in-memory 유지, 인터페이스 분리로 저장소 교체 준비

## 데이터 플로우
1) 주문/정정/취소 요청 수신
2) 계약 검증 + 리스크 체크
3) Idempotency-Key 및 body hash 검증
4) 큐 적재/상태 전이(NEW→DISPATCHING)
5) KIS REST 호출
6) 응답 반영(SENT/REJECTED) + 메트릭/감사 로그
7) 백그라운드 리컨실로 상태 정합성 확인

## 주문 상태 전이(확장)
- NEW → DISPATCHING → SENT
- SENT → PARTIAL_FILLED | FILLED | CANCEL_PENDING | MODIFY_PENDING | REJECTED
- CANCEL_PENDING → CANCELED | REJECTED
- MODIFY_PENDING → SENT(수정 주문 재진입) | REJECTED
- FILLED/CANCELED/REJECTED는 terminal

## 실패/재시도/중복방지
- 재시도 대상: RATE_LIMIT, UNKNOWN(일시 오류)
- 재시도 비대상: AUTH, INVALID_ORDER
- 멱등 충돌: 동일 키 + 다른 body는 409
- 리컨실 작업에서 중복/유실 탐지 시 상태 보정 이벤트 기록

## Mock → Live 안전 가드
- 기본 환경은 `mock`
- live는 명시 플래그 + 계좌 화이트리스트 + 최대수량/일일한도 체크 통과 시만 허용
- live 경로는 dry-run 검증 로그 없으면 배포 차단
- kill switch(환경변수)로 live 주문 즉시 차단 가능

## API 문서화 전략
- 타팀 endpoint naming이 달라도 연동 가능하도록 OpenAPI에
  - operationId
  - request/response schema
  - error code contract
  를 먼저 고정한다.
- 실제 path는 임시(`x-path-draft`)로 두고 협의 후 매핑 가능하게 설계한다.
