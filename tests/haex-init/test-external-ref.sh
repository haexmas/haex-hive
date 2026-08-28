#!/usr/bin/env bash
# test-external-ref.sh — SC-001c + SC-004 + US2.
#
# Three layers:
#
#   1. validate_external_url() scheme table
#      Rejects file://, git://, http://, and bare paths per FR-021.
#      Accepts https://, ssh://, and SCP-style user@host:path.
#
#   2. verify_external_ref() against the built fixture
#      Happy path: real SHA + real path at file://$BARE → (True, '').
#      Unreachable SHA: same URL, all-zero SHA → (False, <git error>).
#      (verify_external_ref() runs after scheme validation, so we can
#      drive it with a file:// URL that would otherwise be rejected.)
#
#   3. End-to-end CLI invocation in external-ref mode
#      Non-interactive: --yes --constitution-mode=external-ref with
#      --constitution-url/sha/path. Asserts .haex-hive.json's
#      harness_sources carries the triple back.
#      Failure branch: bogus SHA → exit 3 and no .haex-hive.json left
#      behind in the project.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/sandbox.sh"
FIXTURES="$HERE/fixtures/.tmp/fixtures.env"
[[ -f "$FIXTURES" ]] || (cd "$HERE" && ./fixtures/build-fixtures.sh)
# shellcheck disable=SC1090
source "$FIXTURES"

setup_sandbox "external-ref"
trap 'teardown_sandbox' EXIT

# ---------------------------------------------------------------------------
# 1 + 2: unit-shape tests driven directly against the Python surface.
# ---------------------------------------------------------------------------
python3 - <<PY
import importlib.machinery, importlib.util, sys
loader = importlib.machinery.SourceFileLoader("hi", "$HAEX_INIT")
spec = importlib.util.spec_from_loader("hi", loader)
m = importlib.util.module_from_spec(spec); sys.modules["hi"]=m; loader.exec_module(m)

# Scheme rejection.
for url in ("file:///tmp/foo", "git://example.com/x", "http://example.com/x", "just-a-path"):
    err = m.validate_external_url(url)
    assert err is not None, f"expected rejection for {url!r}"
    print(f"  reject OK: {url} → {err[:60]}")

# Scheme acceptance.
for url in ("https://example.com/x.git", "ssh://git" + "@" + "example.com/x.git", "git" + "@" + "example.com:org/repo.git"):
    err = m.validate_external_url(url)
    assert err is None, f"expected acceptance for {url!r}, got {err!r}"
    print(f"  accept OK: {url}")

# Unreachable-SHA (using our file:// fixture URL and a bogus SHA).
url = "$FAMILY_REPO_URL_FILE"
ok, msg = m.verify_external_ref(url, "0000000000000000000000000000000000000000", "$FAMILY_REPO_PATH")
assert not ok, f"unreachable SHA verification unexpectedly succeeded (msg={msg!r})"
print(f"  unreachable-SHA rejected: {msg[:80]}")

# Happy-path: real SHA + real path in the fixture.
ok, msg = m.verify_external_ref(url, "$FAMILY_REPO_SHA", "$FAMILY_REPO_PATH")
assert ok, f"verify_external_ref happy path failed: {msg!r}"
print("  happy-path verified against fixture repo")

print("all external-ref unit assertions passed")
PY

# ---------------------------------------------------------------------------
# 3: end-to-end CLI in external-ref mode.
# ---------------------------------------------------------------------------

# 3a — happy path: non-interactive external-ref, assert the triple lands in
# .haex-hive.json under harness_sources. The CLI rejects file:// URLs at
# validation time, so we drive it with an https:// URL and let git rewrite
# it to the sandbox bare fixture via `insteadOf` (scoped to the sandbox
# HOME via --global, cleaned up in teardown).
REMOTE_URL="https://haex-init.test/family-spec-repo.git"
git config --global "url.${FAMILY_REPO_URL_FILE}.insteadOf" "$REMOTE_URL"

"$HAEX_INIT" \
    --yes \
    --constitution-mode=external-ref \
    --constitution-url="$REMOTE_URL" \
    --constitution-sha="$FAMILY_REPO_SHA" \
    --constitution-path="$FAMILY_REPO_PATH" \
    >"$SANDBOX_ROOT/haex-yes-stdout" 2>"$SANDBOX_ROOT/haex-yes-stderr"

cfg="$SANDBOX_ROOT/project/.haex-hive.json"
if [[ ! -f "$cfg" ]]; then
    echo "FAIL(3a): $cfg not written"
    cat "$SANDBOX_ROOT/haex-yes-stderr" >&2
    exit 1
fi

python3 - "$cfg" "$REMOTE_URL" "$FAMILY_REPO_SHA" "$FAMILY_REPO_PATH" <<'PY'
import json, sys
cfg_path, url, sha, path = sys.argv[1:5]
with open(cfg_path, encoding="utf-8") as f:
    doc = json.load(f)
sources = doc.get("harness_sources", [])
assert isinstance(sources, list) and sources, f"harness_sources empty: {doc!r}"
constitutions = [s for s in sources if s.get("role") == "constitution"]
assert len(constitutions) == 1, f"expected exactly 1 constitution entry, got {len(constitutions)}: {sources!r}"
entry = constitutions[0]
assert entry.get("repository") == url, f"repository mismatch: {entry!r} vs {url!r}"
assert entry.get("revision") == sha, f"revision mismatch: {entry!r} vs {sha!r}"
assert entry.get("path") == path, f"path mismatch: {entry!r} vs {path!r}"
print(f"  (3a) harness_sources[0] = {entry}")
PY

# 3b — failure path: bogus SHA, no prior config. Assert exit 3 and no
# .haex-hive.json is left behind.
teardown_sandbox
setup_sandbox "external-ref-fail"
trap 'teardown_sandbox' EXIT

REMOTE_URL="https://haex-init.test/family-spec-repo.git"
git config --global "url.${FAMILY_REPO_URL_FILE}.insteadOf" "$REMOTE_URL"
rc=0
"$HAEX_INIT" \
    --yes \
    --constitution-mode=external-ref \
    --constitution-url="$REMOTE_URL" \
    --constitution-sha="0000000000000000000000000000000000000000" \
    --constitution-path="$FAMILY_REPO_PATH" \
    >"$SANDBOX_ROOT/haex-fail-stdout" 2>"$SANDBOX_ROOT/haex-fail-stderr" || rc=$?

if [[ "$rc" -ne 3 ]]; then
    echo "FAIL(3b): expected exit 3 (EXTERNAL_REF), got $rc"
    cat "$SANDBOX_ROOT/haex-fail-stderr" >&2
    exit 1
fi
if [[ -f "$SANDBOX_ROOT/project/.haex-hive.json" ]]; then
    echo "FAIL(3b): .haex-hive.json written despite verification failure"
    exit 1
fi
# A failing verification MUST also clean up the cache it created —
# the sandbox's XDG_CACHE_HOME must be byte-empty for this URL slug.
cache_root="$XDG_CACHE_HOME/haex-init/verify"
if [[ -d "$cache_root" ]] && [[ -n "$(ls -A "$cache_root" 2>/dev/null)" ]]; then
    echo "FAIL(3b): verification cache not cleaned up after failure"
    find "$cache_root" -maxdepth 2 -type d
    exit 1
fi
echo "  (3b) verification failure left no .haex-hive.json and no cache behind"

echo "test-external-ref: PASS"
