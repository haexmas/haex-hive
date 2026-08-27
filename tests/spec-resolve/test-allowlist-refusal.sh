#!/usr/bin/env bash
# T026 (US2): exercise the four allowlist-shape refusal cases and one
# self-permission case. Each case runs `spec-resolve resolve` with a
# direct triple, asserts exit code 1, checksums the fixture root
# before/after to prove there were no side effects, and asserts the
# stderr message names the offending reference triple.
#
# Shape catalogue (see data-model.md § entry-shape allOf constraints):
#   1. repository-only permission entry — wrong repo → refused
#   2. repository+revision permission — wrong SHA → refused
#   3. repository+revision+paths permission — wrong path → refused
#   4. role-carrying entry — implicit permission for its own triple only

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
SPEC_RESOLVE="$REPO_ROOT/.specify/scripts/spec-resolve"
FIX="$HERE/fixtures/.tmp"

# shellcheck disable=SC1091
source "$FIX/fixtures.env"

# Utility: assert refused with a stderr substring; also assert no side effects
# by taking a directory checksum before + after.
assert_refused() {
    local label="$1"
    local consumer="$2"
    local repo_arg="$3"
    local rev_arg="$4"
    local path_arg="$5"
    local expected_stderr_substring="$6"

    local before after
    before="$(cd "$consumer" && find . -type f ! -path './.git/*' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum)"

    local err="$(mktemp)"
    trap 'rm -f "$err"' RETURN
    set +e
    "$SPEC_RESOLVE" --repo "$consumer" resolve \
        --repository "$repo_arg" \
        --revision "$rev_arg" \
        --path "$path_arg" \
        > /dev/null 2> "$err"
    local ec=$?
    set -e

    after="$(cd "$consumer" && find . -type f ! -path './.git/*' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum)"

    if [[ $ec -ne 1 ]]; then
        echo "FAIL [$label]: expected exit 1, got $ec" >&2
        cat "$err" >&2
        return 1
    fi
    if ! grep -qF "$expected_stderr_substring" "$err"; then
        echo "FAIL [$label]: expected stderr substring '$expected_stderr_substring' not found. Stderr:" >&2
        cat "$err" >&2
        return 1
    fi
    if [[ "$before" != "$after" ]]; then
        echo "FAIL [$label]: fixture root changed during refused resolve" >&2
        return 1
    fi
    echo "PASS [$label]: exit 1, message names ref, fixture unchanged"
}

# --- Case 1: repository-only permission — wrong REPO ---
# consumer-with-external-permitted permits ssh://git@fixtures.invalid/external-repo-a
# only. A request for external-repo-b must refuse.
assert_refused \
    "shape-1 wrong-repo" \
    "$FIX/consumer-with-external-permitted" \
    "ssh://git@fixtures.invalid/external-repo-b" \
    "$SHA_B1" \
    "README.md" \
    "not permitted by any entry in harness_sources"

# --- Case 2: repository+revision permission — wrong SHA ---
# consumer-with-external-narrow permits external-repo-a @ SHA_A1 only.
# A request for the same repo but SHA_A2 must refuse.
assert_refused \
    "shape-2 wrong-sha" \
    "$FIX/consumer-with-external-narrow" \
    "$EXT_A_URL" \
    "$SHA_A2" \
    "README.md" \
    "not permitted by any entry in harness_sources"

# --- Case 3: repository+revision+paths permission — wrong PATH ---
# Same fixture, correct repo and SHA but a path not in the allowlist.
assert_refused \
    "shape-3 wrong-path" \
    "$FIX/consumer-with-external-narrow" \
    "$EXT_A_URL" \
    "$SHA_A1" \
    "docs/pinned.md" \
    "not permitted by any entry in harness_sources"

# --- Case 4: role-carrying entry permits only its own triple ---
# consumer-with-role-only has a self-role constitution entry. Any direct
# triple naming an EXTERNAL repo (which is not covered by any permission
# entry there) must refuse.
assert_refused \
    "shape-4 role-entry-does-not-authorise-others" \
    "$FIX/consumer-with-role-only" \
    "$EXT_A_URL" \
    "$SHA_A1" \
    "README.md" \
    "not permitted by any entry in harness_sources"

echo "PASS: all four allowlist-refusal cases behaved correctly"
