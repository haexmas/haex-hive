#!/usr/bin/env bash
# T030 (US3): for every curated valid/invalid sample, the canonical JSON
# Schema (via lib/schema-validate.py, an independent Draft-07-subset
# implementation) and the spec-resolve tool MUST agree on accept/reject.
# On reject, the tool's stderr MUST contain the sample's expected error
# substring.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
SPEC_RESOLVE="$REPO_ROOT/.specify/scripts/spec-resolve"
SCHEMA="$REPO_ROOT/.specify/schemas/haex-hive.schema.json"
VALIDATOR="$HERE/lib/schema-validate.py"
SAMPLES="$HERE/fixtures/config-samples"

fail=0

# Iterate every sample .json that is not itself an .expected.json.
for sample in "$SAMPLES"/*.json; do
    base="$(basename "$sample" .json)"
    if [[ "$base" == *.expected ]]; then
        continue
    fi
    expected_file="$SAMPLES/$base.expected.json"
    if [[ ! -f "$expected_file" ]]; then
        echo "SKIP [$base]: no .expected.json companion" >&2
        continue
    fi
    expected_result="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["expected_result"])' "$expected_file")"

    # Schema outcome
    if python3 "$VALIDATOR" "$SCHEMA" "$sample" > /dev/null 2>&1; then
        schema_result="accept"
    else
        schema_result="reject"
    fi

    # Tool outcome (via `status` — same call the snippet makes)
    tmpdir="$(mktemp -d)"
    cp "$sample" "$tmpdir/.haex-hive.json"
    err="$(mktemp)"
    set +e
    "$SPEC_RESOLVE" --repo "$tmpdir" status > /dev/null 2> "$err"
    ec=$?
    set -e
    if [[ $ec -eq 0 ]]; then
        tool_result="accept"
    elif [[ $ec -eq 2 ]]; then
        tool_result="reject"
    else
        echo "FAIL [$base]: tool exited $ec (expected 0 or 2)" >&2
        cat "$err" >&2
        fail=1
        rm -rf "$tmpdir" "$err"
        continue
    fi

    # Cross-check
    if [[ "$schema_result" != "$expected_result" ]]; then
        echo "FAIL [$base]: schema expected $expected_result, got $schema_result" >&2
        python3 "$VALIDATOR" "$SCHEMA" "$sample" >&2 || true
        fail=1
    fi
    if [[ "$tool_result" != "$expected_result" ]]; then
        echo "FAIL [$base]: tool expected $expected_result, got $tool_result" >&2
        cat "$err" >&2
        fail=1
    fi
    if [[ "$tool_result" == "reject" && "$expected_result" == "reject" ]]; then
        expected_substring="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["expected_error_substring"])' "$expected_file")"
        if ! grep -qF "$expected_substring" "$err"; then
            echo "FAIL [$base]: tool stderr missing substring '$expected_substring'" >&2
            cat "$err" >&2
            fail=1
        fi
    fi
    if [[ "$schema_result" == "$tool_result" && "$tool_result" == "$expected_result" ]]; then
        echo "PASS [$base]: schema=$schema_result tool=$tool_result"
    fi
    rm -rf "$tmpdir" "$err"
done

if [[ $fail -ne 0 ]]; then
    echo "FAIL: schema/tool agreement failed for one or more samples" >&2
    exit 1
fi
echo "PASS: schema and tool agree on all curated samples"
