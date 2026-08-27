#!/usr/bin/env bash
# T020 (US1): `spec-resolve resolve --role constitution` against the
# consumer-with-role-only fixture returns byte-identical stdout compared
# to the constitution content pinned at the fixture's harness_sources[0]
# revision. Also exercises exit 0.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
SPEC_RESOLVE="$REPO_ROOT/.specify/scripts/spec-resolve"
FIX="$HERE/fixtures/.tmp"

# shellcheck disable=SC1091
source "$FIX/fixtures.env"

CONSUMER="$FIX/consumer-with-role-only"
RESOLVED="$(mktemp)"
EXPECTED="$(mktemp)"
trap 'rm -f "$RESOLVED" "$EXPECTED"' EXIT

# Actual resolve.
"$SPEC_RESOLVE" --repo "$CONSUMER" resolve --role constitution > "$RESOLVED"

# Expected: the same content as it existed at the pinned SHA.
git -C "$CONSUMER" show "${CONS_ROLE_ONLY_PIN}:.specify/memory/constitution.md" > "$EXPECTED"

diff "$RESOLVED" "$EXPECTED"
echo "PASS: resolve --role constitution byte-identical to pinned SHA content"
