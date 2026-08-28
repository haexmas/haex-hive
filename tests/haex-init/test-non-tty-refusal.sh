#!/usr/bin/env bash
# test-non-tty-refusal.sh — SC-006 negative case.
#
# When stdin is not a TTY and --yes is absent, haex-init MUST refuse with
# exit code 2 (EXIT_REFUSED) and MUST NOT write into the sandbox HOME or
# project. The positive path (--yes bypass) is covered by every other
# test that already uses --yes non-interactively.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/sandbox.sh"

setup_sandbox "non-tty-refusal"
trap 'teardown_sandbox' EXIT

pre_home=$(checksum_tree "$HOME")
pre_project=$(checksum_tree "$SANDBOX_ROOT/project")

rc=0
"$HAEX_INIT" </dev/null >"$SANDBOX_ROOT/stdout" 2>"$SANDBOX_ROOT/stderr" || rc=$?

assert_eq "exit code on non-TTY without --yes" "2" "$rc"

if ! grep -q "refusing to run non-interactively" "$SANDBOX_ROOT/stderr"; then
    echo "FAIL: refusal message missing"
    cat "$SANDBOX_ROOT/stderr" >&2
    exit 1
fi

post_home=$(checksum_tree "$HOME")
post_project=$(checksum_tree "$SANDBOX_ROOT/project")
assert_eq "HOME unchanged after refusal" "$pre_home" "$post_home"
assert_eq "project unchanged after refusal" "$pre_project" "$post_project"

echo "test-non-tty-refusal: PASS"
