#!/usr/bin/env bash
# test-partial-state.sh — FR-027.
#
# Run to completion, delete .vscode/settings.json, re-run --yes, assert
# only that file is recreated and everything else is untouched.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/sandbox.sh"

setup_sandbox "partial"
trap teardown_sandbox EXIT

install_fake_bin claude
install_fake_bin code
create_fake_config_dir claude-code
create_fake_config_dir vscode
git init --quiet -b main .

"$HAEX_INIT" --yes >/dev/null

# Snapshot file-by-file before delete.
declare -A pre_shas
while IFS= read -r -d '' f; do
    pre_shas["$f"]=$(sha256sum "$f" | awk '{print $1}')
done < <(cd "$SANDBOX_ROOT/project" && find . -type f -print0)

rm .vscode/settings.json

"$HAEX_INIT" --yes >/dev/null

# Assert .vscode/settings.json re-appeared with the SAME content.
if [[ ! -f .vscode/settings.json ]]; then
    echo "FAIL: .vscode/settings.json not recreated"
    exit 1
fi
sha_after=$(sha256sum .vscode/settings.json | awk '{print $1}')
assert_eq ".vscode/settings.json unchanged after re-create" "${pre_shas[./.vscode/settings.json]}" "$sha_after"

# Assert every other file unchanged. New files are also flagged.
while IFS= read -r -d '' f; do
    sha_now=$(sha256sum "$f" | awk '{print $1}')
    pre_sha="${pre_shas[$f]:-MISSING}"
    if [[ "$pre_sha" == "MISSING" ]]; then
        # A new file appeared post-rerun — likely git object under .git/.
        # We only care about non-.git files here.
        if [[ "$f" == ./.git/* ]]; then
            continue
        fi
        echo "FAIL: unexpected new file after re-run: $f"
        exit 1
    fi
    if [[ "$pre_sha" != "$sha_now" ]]; then
        # Ignore drift under .git/ — a fresh commit can rewrite pack indexes.
        if [[ "$f" == ./.git/* ]]; then
            continue
        fi
        echo "FAIL: file changed unexpectedly: $f ($pre_sha → $sha_now)"
        exit 1
    fi
done < <(cd "$SANDBOX_ROOT/project" && find . -type f -print0)

echo "test-partial-state: PASS"
