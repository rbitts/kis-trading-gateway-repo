#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/env/mock.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  . "$ENV_FILE"
  set +a
else
  # Fallback to OpenClaw env vars if present
  export KIS_APP_KEY="${KIS_APP_KEY:-${KIS_MOCK_APP_KEY:-}}"
  export KIS_APP_SECRET="${KIS_APP_SECRET:-${KIS_MOCK_APP_SECRET:-}}"
  if [[ -n "${KIS_MOCK_CANO:-}" ]]; then
    export KIS_ACCOUNT_NO="${KIS_ACCOUNT_NO:-${KIS_MOCK_CANO}-${KIS_MOCK_ACNT_PRDT_CD_KR:-01}}"
  fi
  export KIS_ENV="${KIS_ENV:-mock}"
  export KIS_WS_SYMBOLS="${KIS_WS_SYMBOLS:-005930,000660}"
fi

: "${KIS_APP_KEY:?KIS_APP_KEY is required}"
: "${KIS_APP_SECRET:?KIS_APP_SECRET is required}"
: "${KIS_ACCOUNT_NO:?KIS_ACCOUNT_NO is required}"

exec uvicorn app.main:app --host 127.0.0.1 --port 8890
