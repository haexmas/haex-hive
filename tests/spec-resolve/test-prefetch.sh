#!/usr/bin/env bash
# T022 (US1): `spec-resolve prefetch --dry-run` on a fixture whose
# spec-ref.json names an external SHA-refspec pointing at an
# unreachable-by-design URL prints MISSING for that ref and OK for the
# self constitution ref.
#
# Actually populating the cache from a live remote is exercised by the
# Phase 7 smoke test (T038); this test focuses on the enumeration and
# dry-run reporting code paths.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
SPEC_RESOLVE="$REPO_ROOT/.specify/scripts/spec-resolve"
FIX="$HERE/fixtures/.tmp"

# shellcheck disable=SC1091
source "$FIX/fixtures.env"

CONSUMER="$FIX/consumer-with-spec-ref"

# The consumer-with-spec-ref fixture points at ssh://git@fixtures.invalid/...
# Nuke any leftover cache for that URL from a previous run so the miss is
# guaranteed even locally.
python3 - <<'PY'
import hashlib, os, pathlib, shutil
url = "ssh://git@fixtures.invalid/external-repo-a"
h = hashlib.sha256(url.encode()).hexdigest()[:16]
xdg = os.environ.get("XDG_CACHE_HOME")
base = pathlib.Path(xdg) if xdg else pathlib.Path.home() / ".cache"
cache = base / "haex-hive" / "repos" / h
if cache.exists():
    shutil.rmtree(cache)
    print(f"removed {cache}")
else:
    print(f"no cache at {cache}, good")
PY

OUT="$("$SPEC_RESOLVE" --repo "$CONSUMER" prefetch --dry-run)"
echo "$OUT"

# Expect one OK line (the self constitution ref) and one MISSING line
# (the external ref from spec-ref.json).
if ! grep -qE "^OK self@${CONS_SPEC_REF_PIN}:\.specify/memory/constitution\.md$" <<< "$OUT"; then
    echo "FAIL: expected OK line for self constitution ref" >&2
    exit 1
fi
if ! grep -qE "^MISSING ssh://git@fixtures\.invalid/external-repo-a@${SHA_A2}:docs/pinned\.md$" <<< "$OUT"; then
    echo "FAIL: expected MISSING line for external spec-ref" >&2
    exit 1
fi

echo "PASS: prefetch --dry-run reports OK for self, MISSING for external"
