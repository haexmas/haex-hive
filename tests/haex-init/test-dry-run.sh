#!/usr/bin/env bash
# test-dry-run.sh — SC-005.
#
# Case (a): up-to-date project → --dry-run prints "Everything in order.",
#          exit 0, filesystem checksums equal before/after.
# Case (b): project with a missing artifact → --dry-run reports the pending
#          action, exit 1, filesystem checksums equal before/after.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/sandbox.sh"

setup_sandbox "dry-run"
trap teardown_sandbox EXIT

install_fake_bin claude
install_fake_bin code
create_fake_config_dir claude-code
create_fake_config_dir vscode
git init --quiet -b main .

"$HAEX_INIT" --yes >/dev/null

# (a) up-to-date → --dry-run exit 0.
proj_before=$(checksum_tree "$SANDBOX_ROOT/project")
home_before=$(checksum_tree "$SANDBOX_ROOT/home")
rc=0
out=$("$HAEX_INIT" --dry-run --yes) || rc=$?
proj_after=$(checksum_tree "$SANDBOX_ROOT/project")
home_after=$(checksum_tree "$SANDBOX_ROOT/home")

assert_eq "(a) exit code up-to-date --dry-run" "0" "$rc"
assert_contains "(a) stdout up-to-date" "$out" "Everything in order"
assert_eq "(a) project unchanged" "$proj_before" "$proj_after"
assert_eq "(a) home unchanged" "$home_before" "$home_after"

# (b) needs-work project: delete .gitignore, re-run --dry-run.
rm .gitignore
proj_before=$(checksum_tree "$SANDBOX_ROOT/project")
home_before=$(checksum_tree "$SANDBOX_ROOT/home")
set +e
out=$("$HAEX_INIT" --dry-run --yes 2>&1)
rc=$?
set -e
proj_after=$(checksum_tree "$SANDBOX_ROOT/project")
home_after=$(checksum_tree "$SANDBOX_ROOT/home")

assert_eq "(b) exit code pending --dry-run" "1" "$rc"
# Pending action label mentions .gitignore.
assert_contains "(b) stdout mentions .gitignore" "$out" ".gitignore"
assert_eq "(b) project unchanged" "$proj_before" "$proj_after"
assert_eq "(b) home unchanged" "$home_before" "$home_after"

echo "test-dry-run: PASS"
