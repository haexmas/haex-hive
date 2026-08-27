#!/usr/bin/env bash
# Test entrypoint for spec-resolve.
# Iterates every test-*.sh in this directory in sorted order and aggregates a
# pass/fail count. Each test script is expected to `set -euo pipefail` and exit
# non-zero on any assertion failure; stdout/stderr are streamed through so the
# operator (or CI) can read the details of failures inline.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

# Build fixtures once before any tests run. Fixtures live under fixtures/.tmp/
# and are regenerated deterministically each run.
if [[ -x fixtures/build-fixtures.sh ]]; then
    echo "== building fixtures =="
    ./fixtures/build-fixtures.sh
fi

shopt -s nullglob
tests=(test-*.sh)
shopt -u nullglob

if [[ ${#tests[@]} -eq 0 ]]; then
    echo "run-all.sh: no test-*.sh scripts found in $HERE" >&2
    exit 1
fi

passed=0
failed=0
failed_names=()

for t in "${tests[@]}"; do
    echo "== $t =="
    if bash "$t"; then
        passed=$((passed + 1))
    else
        failed=$((failed + 1))
        failed_names+=("$t")
    fi
done

total=$((passed + failed))
echo
echo "== summary =="
echo "passed: $passed / $total"
if [[ $failed -gt 0 ]]; then
    echo "failed: $failed"
    for name in "${failed_names[@]}"; do
        echo "  - $name"
    done
    exit 1
fi
