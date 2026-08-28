#!/usr/bin/env bash
# Test entrypoint for haex-init.
# Iterates every test-*.sh in this directory in a fixed order (declared below)
# and aggregates a pass/fail count. Each test script sets `set -euo pipefail`
# and exits non-zero on any assertion failure; stdout/stderr stream through so
# the operator (or CI) can read the details of failures inline.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

if [[ -x fixtures/build-fixtures.sh ]]; then
    echo "== building fixtures =="
    ./fixtures/build-fixtures.sh
fi

# Fixed order: content-sync first (fastest, purest); then MVP path
# (fresh-operator, self-ref, pin-constitution); then external-ref;
# then idempotency + partial + version-upgrade + dry-run; then marker-safety.
tests=(
    test-embedded-content-sync.sh
    test-format-regressions.sh
    test-non-tty-refusal.sh
    test-fresh-operator.sh
    test-self-ref.sh
    test-pin-constitution.sh
    test-external-ref.sh
    test-idempotent-rerun.sh
    test-partial-state.sh
    test-version-upgrade.sh
    test-dry-run.sh
    test-marker-safety.sh
)

passed=0
failed=0
failed_names=()

for t in "${tests[@]}"; do
    if [[ ! -f "$t" ]]; then
        echo "run-all.sh: expected test $t not found in $HERE" >&2
        failed=$((failed + 1))
        failed_names+=("$t (missing)")
        continue
    fi
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

echo "haex-init: all tests passed"
