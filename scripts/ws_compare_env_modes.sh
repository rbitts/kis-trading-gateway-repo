#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ACCOUNT_NO="${KIS_ACCOUNT_NO:-${KIS_CANO:-}-${KIS_ACNT_PRDT_CD:-${KIS_ACNT_PRDT_CD_KR:-01}}}"
if [[ -z "${KIS_APP_KEY:-}" || -z "${KIS_APP_SECRET:-}" || -z "$ACCOUNT_NO" ]]; then
  echo "[ERR] KIS_APP_KEY/KIS_APP_SECRET/KIS_ACCOUNT_NO(or KIS_CANO+KIS_ACNT_PRDT_CD) required" >&2
  exit 1
fi

export KIS_ACCOUNT_NO="$ACCOUNT_NO"
export KIS_WS_SYMBOLS="${KIS_WS_SYMBOLS:-005930}"

run_case() {
  local mode="$1"
  export KIS_ENV="$mode"

  local log="/tmp/ws_cmp_${mode}.log"
  local m1="/tmp/ws_cmp_${mode}_m1.json"
  local m2="/tmp/ws_cmp_${mode}_m2.json"
  local q1="/tmp/ws_cmp_${mode}_q1.json"

  timeout 22s uvicorn app.main:app --host 127.0.0.1 --port 8890 >"$log" 2>&1 &
  local pid=$!

  local ok=0
  for _ in 1 2 3 4 5 6 7; do
    if curl -fsS http://127.0.0.1:8890/v1/metrics/quote >"$m1" 2>/dev/null; then
      ok=1
      break
    fi
    sleep 1
  done

  if [[ "$ok" -eq 1 ]]; then
    curl -sS http://127.0.0.1:8890/v1/quotes/005930 >"$q1"
    sleep 8
    curl -sS http://127.0.0.1:8890/v1/metrics/quote >"$m2"
  else
    echo "{}" >"$m1"
    echo "{}" >"$m2"
    echo "{}" >"$q1"
  fi

  wait "$pid" || true
}

run_case mock
run_case live

python3 - <<'PY'
import json
from pathlib import Path

def load(p):
    return json.loads(Path(p).read_text())

rows = []
for mode in ("mock", "live"):
    m1 = load(f"/tmp/ws_cmp_{mode}_m1.json")
    m2 = load(f"/tmp/ws_cmp_{mode}_m2.json")
    q1 = load(f"/tmp/ws_cmp_{mode}_q1.json")
    rows.append({
        "mode": mode,
        "ws_connected_t1": m1.get("ws_connected"),
        "ws_connected_t2": m2.get("ws_connected"),
        "ws_messages_t1": m1.get("ws_messages"),
        "ws_messages_t2": m2.get("ws_messages"),
        "ws_reconnect_t1": m1.get("ws_reconnect_count"),
        "ws_reconnect_t2": m2.get("ws_reconnect_count"),
        "quote_source": q1.get("source"),
        "ws_last_error": m2.get("ws_last_error"),
    })

out = Path("docs/evidence/2026-02-28-ws-debug-compare-mock-live.md")
out.parent.mkdir(parents=True, exist_ok=True)
lines = [
    "# WS Debug Compare: mock vs live (same credentials)",
    "",
    "| mode | ws_connected(t1→t2) | ws_messages(t1→t2) | ws_reconnect(t1→t2) | quote source | ws_last_error |",
    "|---|---|---|---|---|---|",
]
for r in rows:
    lines.append(
        f"| {r['mode']} | {r['ws_connected_t1']} → {r['ws_connected_t2']} | {r['ws_messages_t1']} → {r['ws_messages_t2']} | {r['ws_reconnect_t1']} → {r['ws_reconnect_t2']} | {r['quote_source']} | {r['ws_last_error']} |"
    )
out.write_text("\n".join(lines) + "\n")
print(out)
PY

echo "[OK] docs/evidence/2026-02-28-ws-debug-compare-mock-live.md generated"