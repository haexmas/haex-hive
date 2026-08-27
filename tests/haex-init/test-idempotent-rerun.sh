#!/usr/bin/env bash
# test-idempotent-rerun.sh — SC-003.
#
# Run haex-init --yes to completion, capture checksum, re-run --yes,
# assert exit 0, stdout starts with "Everything in order.", checksums
# unchanged.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/sandbox.sh"

setup_sandbox "idempotent"
trap teardown_sandbox EXIT

install_fake_bin claude
install_fake_bin code
create_fake_config_dir claude-code
create_fake_config_dir vscode
git init --quiet -b main .

"$HAEX_INIT" --yes >/dev/null

# Snapshot state before re-run.
proj_before=$(checksum_tree "$SANDBOX_ROOT/project")
home_before=$(checksum_tree "$SANDBOX_ROOT/home")

# Second invocation.
out=$("$HAEX_INIT" --yes)

proj_after=$(checksum_tree "$SANDBOX_ROOT/project")
home_after=$(checksum_tree "$SANDBOX_ROOT/home")

assert_contains "idempotent stdout header" "$out" "Everything in order"
assert_eq "project checksum unchanged" "$proj_before" "$proj_after"
assert_eq "home checksum unchanged" "$home_before" "$home_after"

echo "test-idempotent-rerun: PASS"
