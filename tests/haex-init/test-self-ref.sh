#!/usr/bin/env bash
# test-self-ref.sh — targeted self-ref-mode assertions on the same fresh-operator
# sandbox: no constitution stub file, exactly one scaffolding commit, next-step
# guidance printed to stdout.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/sandbox.sh"

setup_sandbox "self-ref"
trap teardown_sandbox EXIT

install_fake_bin claude
install_fake_bin code
create_fake_config_dir claude-code
create_fake_config_dir vscode
git init --quiet -b main .

out=$("$HAEX_INIT" --yes 2>&1)

# .specify/memory/constitution.md must NOT be created (Q2 clarification).
if [[ -e ".specify/memory/constitution.md" ]]; then
    echo "FAIL: self-ref should NOT create .specify/memory/constitution.md"
    exit 1
fi

# Exactly one commit.
commits=$(git rev-list --count HEAD)
assert_eq "commit count" "1" "$commits"

# Next-step guidance references both /speckit-constitution and --pin-constitution.
assert_contains "next-step /speckit-constitution" "$out" "/speckit-constitution"
assert_contains "next-step --pin-constitution" "$out" "haex-init --pin-constitution"

echo "test-self-ref: PASS"
