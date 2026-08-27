#!/usr/bin/env bash
# T021 (US1): `spec-resolve status` on a fresh fixture prints the compact
# summary shape and exit 0; --json mode emits a parseable envelope with
# refs_missing == 0.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
SPEC_RESOLVE="$REPO_ROOT/.specify/scripts/spec-resolve"
FIX="$HERE/fixtures/.tmp"

CONSUMER="$FIX/consumer-with-role-only"

# --- text mode ---
OUT="$("$SPEC_RESOLVE" --repo "$CONSUMER" status)"
echo "text: $OUT"
# Shape: "1 ref, 1 cached, last update-check: never" (self ref is always cached).
grep -qE '^1 ref, 1 cached, last update-check: never$' <<< "$OUT"

# --- JSON mode ---
JSON="$("$SPEC_RESOLVE" --repo "$CONSUMER" status --json)"
echo "json: $JSON"
python3 - "$JSON" <<'PY'
import json, sys
payload = json.loads(sys.argv[1])
assert payload["refs_total"] == 1, payload
assert payload["refs_cached"] == 1, payload
assert payload["refs_missing"] == 0, payload
assert payload["last_update_check"] is None, payload
assert len(payload["sources"]) == 1
assert payload["sources"][0]["repository"] == "self"
assert payload["sources"][0]["cached"] is True
print("json envelope shape ok")
PY

echo "PASS: status text + json shape"
