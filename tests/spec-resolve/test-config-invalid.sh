#!/usr/bin/env bash
# T031 (US3): for a representative slice of malformed configs, running
# `spec-resolve status` (the same call the session-start snippet makes)
# must exit 2 and stderr must pinpoint the offending entry — array
# index, field, constraint. Proves the snippet would refuse to start
# harness work on a broken config without requiring the actual snippet
# in this repo.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
SPEC_RESOLVE="$REPO_ROOT/.specify/scripts/spec-resolve"
SAMPLES="$HERE/fixtures/config-samples"

# Malformations covering the load-bearing error paths.
CASES=(
    "invalid-unknown-role"
    "invalid-paths-on-role"
    "invalid-bad-sha"
    "invalid-short-sha"
    "invalid-sha-trailing-newline"
    "invalid-file-scheme"
)

fail=0

for case in "${CASES[@]}"; do
    sample="$SAMPLES/$case.json"
    expected="$SAMPLES/$case.expected.json"
    tmpdir="$(mktemp -d)"
    cp "$sample" "$tmpdir/.haex-hive.json"

    expected_substring="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["expected_error_substring"])' "$expected")"

    err="$(mktemp)"
    set +e
    "$SPEC_RESOLVE" --repo "$tmpdir" status > /dev/null 2> "$err"
    ec=$?
    set -e

    if [[ $ec -ne 2 ]]; then
        echo "FAIL [$case]: expected exit 2, got $ec. Stderr:" >&2
        cat "$err" >&2
        fail=1
    elif ! grep -qF "$expected_substring" "$err"; then
        echo "FAIL [$case]: stderr missing substring '$expected_substring'. Stderr:" >&2
        cat "$err" >&2
        fail=1
    elif ! grep -qE "harness_sources\[[0-9]+\]|harness_sources|haex_hive_version" "$err"; then
        # Every error should mention the offending scope by name.
        echo "FAIL [$case]: stderr does not pinpoint the offending field. Stderr:" >&2
        cat "$err" >&2
        fail=1
    else
        echo "PASS [$case]: exit 2, stderr pinpoints the problem"
    fi

    rm -rf "$tmpdir" "$err"
done

if [[ $fail -ne 0 ]]; then
    echo "FAIL: some malformed configs did not produce the required error UX" >&2
    exit 1
fi
echo "PASS: config-invalid pinpointing works across the sampled malformations"
