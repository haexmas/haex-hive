#!/usr/bin/env bash
# test-pin-constitution.sh — SC-001b + FR-019.
#
# Sequence:
#   1. Run haex-init --yes to establish self-ref scaffolding + commit.
#   2. Seed .specify/memory/constitution.md with placeholder content, commit.
#   3. Run haex-init --pin-constitution --yes; assert
#         .haex-hive.json.harness_sources[0] == {role: constitution, ...HEAD SHA…}
#         one follow-up commit with the pinned message.
#   4. Run haex-init --pin-constitution --yes again; assert exit 2 (idempotent
#      refusal per FR-019).

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/sandbox.sh"

setup_sandbox "pin-constitution"
trap teardown_sandbox EXIT

install_fake_bin claude
install_fake_bin code
create_fake_config_dir claude-code
create_fake_config_dir vscode
git init --quiet -b main .

"$HAEX_INIT" --yes >/dev/null

# Seed the constitution content.
mkdir -p .specify/memory
printf 'Placeholder constitution.\n' > .specify/memory/constitution.md
git add .specify/memory/constitution.md
git commit --quiet -m "seed constitution"

HEAD_SHA=$(git rev-parse HEAD)

out=$("$HAEX_INIT" --pin-constitution --yes 2>&1)

python3 - <<PY
import json
d = json.load(open(".haex-hive.json"))
srcs = d["harness_sources"]
assert len(srcs) == 1, f"expected 1 harness_source; got {len(srcs)}: {srcs!r}"
e = srcs[0]
assert e["role"] == "constitution", e
assert e["repository"] == "self", e
assert e["revision"] == "$HEAD_SHA", e
assert e["path"] == ".specify/memory/constitution.md", e
print("harness_sources[0] shape OK")
PY

# Exactly one new commit from the pin flow. Total = seed + scaffolding + pin = 3.
commits=$(git rev-list --count HEAD)
assert_eq "commit count after pin" "3" "$commits"
git log -1 --pretty=format:'%s' | grep -q 'haex-init: pin constitution to HEAD' \
    || { echo "FAIL: pin commit message not found"; git log -1 --pretty=format:'%s'; exit 1; }

# Idempotency: second --pin-constitution --yes refuses cleanly (exit 2).
set +e
"$HAEX_INIT" --pin-constitution --yes >/dev/null 2>&1
rc=$?
set -e
assert_eq "second --pin-constitution exit code" "2" "$rc"

echo "test-pin-constitution: PASS"
