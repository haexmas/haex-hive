#!/usr/bin/env bash
# test-marker-safety.sh — SC-002 + FR-009 + FR-010.
#
# Four scenarios verify the invariants of contracts/marker-block.format.md:
#   A) no block: content outside the appended block is byte-identical.
#   B) matching block: file byte-identical before/after (idempotency at
#      the file level).
#   C) mismatched-version block: outside marker range byte-identical,
#      block replaced.
#   D) MALFORMED (begin without end): tool refuses (exit 2), file
#      byte-identical.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/sandbox.sh"
FIXTURES="$HERE/fixtures/.tmp/fixtures.env"
[[ -f "$FIXTURES" ]] || (cd "$HERE" && ./fixtures/build-fixtures.sh)
# shellcheck disable=SC1090
source "$FIXTURES"

excise_marker_sha() {
    # Return SHA of file content EXCLUDING the marker block byte range AND
    # any single-LF separator immediately before the begin marker (that LF
    # is synthesized by the append action, per contracts/marker-block.format.md).
    local path="$1"
    python3 - <<PY
import hashlib, os, re
p = "$path"
if not os.path.exists(p):
    print(""); raise SystemExit(0)
raw = open(p, "rb").read()
text = raw.decode("utf-8")
begin_re = re.compile(r'^<!--\s*haex-hive-block:begin\s+v=([^\s>]+)\s*-->\$', re.M)
end_re = re.compile(r'^<!--\s*haex-hive-block:end\s*-->\$', re.M)
mb = begin_re.search(text)
me = end_re.search(text)
if mb is None or me is None:
    outside = text.rstrip("\n")
    print(hashlib.sha256(outside.encode("utf-8")).hexdigest()); raise SystemExit(0)
prefix_end = mb.start()
# Trim trailing LFs that were introduced by the append separator.
while prefix_end > 0 and text[prefix_end - 1] == "\n":
    prefix_end -= 1
suffix_start = me.end()
if suffix_start < len(text) and text[suffix_start] == "\n":
    suffix_start += 1
outside = text[:prefix_end] + text[suffix_start:]
# Normalize a single trailing LF to be optional (append preserves file end).
outside = outside.rstrip("\n")
print(hashlib.sha256(outside.encode("utf-8")).hexdigest())
PY
}

# ---------------------------------------------------------------------------
# (A) No block: append preserves outside content.
# ---------------------------------------------------------------------------
echo "-- (A) no block → append preserves outside content"
setup_sandbox "marker-safety-A"
trap teardown_sandbox EXIT

install_fake_bin claude
create_fake_config_dir claude-code
git init --quiet -b main .

# Seed CLAUDE.md with byte-known payload.
mkdir -p "$HOME/.claude"
cp "$SEEDED_CLAUDE_MD" "$HOME/.claude/CLAUDE.md"
sha_pre=$(excise_marker_sha "$HOME/.claude/CLAUDE.md")

"$HAEX_INIT" --yes >/dev/null

sha_post=$(excise_marker_sha "$HOME/.claude/CLAUDE.md")
assert_eq "(A) outside-marker SHA unchanged" "$sha_pre" "$sha_post"

teardown_sandbox
trap - EXIT

# ---------------------------------------------------------------------------
# (B) Matching block: rerun does nothing to the file.
# ---------------------------------------------------------------------------
echo "-- (B) matching block → rerun byte-identical"
setup_sandbox "marker-safety-B"
trap teardown_sandbox EXIT

install_fake_bin claude
create_fake_config_dir claude-code
git init --quiet -b main .

"$HAEX_INIT" --yes >/dev/null
sha_pre=$(sha256sum "$HOME/.claude/CLAUDE.md" | awk '{print $1}')
"$HAEX_INIT" --yes >/dev/null
sha_post=$(sha256sum "$HOME/.claude/CLAUDE.md" | awk '{print $1}')
assert_eq "(B) CLAUDE.md byte-identical after rerun" "$sha_pre" "$sha_post"

teardown_sandbox
trap - EXIT

# ---------------------------------------------------------------------------
# (C) Mismatched-version block: outside byte-identical, block replaced.
# ---------------------------------------------------------------------------
echo "-- (C) mismatched-version block → replace only the block"
setup_sandbox "marker-safety-C"
trap teardown_sandbox EXIT

install_fake_bin claude
create_fake_config_dir claude-code
git init --quiet -b main .

# Seed a v=0.9 block wrapping some content, plus operator content around it.
mkdir -p "$HOME/.claude"
cat > "$HOME/.claude/CLAUDE.md" <<'EOF'
# operator notes above the block

<!-- haex-hive-block:begin v=0.9 -->
## haex-hive (older)

Older bootstrap content that must be replaced.
<!-- haex-hive-block:end -->

# operator notes below the block
EOF

sha_pre_outside=$(excise_marker_sha "$HOME/.claude/CLAUDE.md")

"$HAEX_INIT" --yes >/dev/null

if ! grep -q 'v=1.0' "$HOME/.claude/CLAUDE.md"; then
    echo "FAIL(C): block was not upgraded to v=1.0"
    exit 1
fi
if grep -q 'v=0.9' "$HOME/.claude/CLAUDE.md"; then
    echo "FAIL(C): old v=0.9 block still present"
    exit 1
fi

sha_post_outside=$(excise_marker_sha "$HOME/.claude/CLAUDE.md")
assert_eq "(C) outside-marker SHA unchanged" "$sha_pre_outside" "$sha_post_outside"

teardown_sandbox
trap - EXIT

# ---------------------------------------------------------------------------
# (D) MALFORMED — begin without end → refuse.
# ---------------------------------------------------------------------------
echo "-- (D) MALFORMED begin-without-end → refuse"
setup_sandbox "marker-safety-D"
trap teardown_sandbox EXIT

install_fake_bin claude
create_fake_config_dir claude-code
git init --quiet -b main .

mkdir -p "$HOME/.claude"
cat > "$HOME/.claude/CLAUDE.md" <<'EOF'
# operator notes

<!-- haex-hive-block:begin v=1.0 -->
## haex-hive
Body without an end marker
EOF

sha_pre=$(sha256sum "$HOME/.claude/CLAUDE.md" | awk '{print $1}')

set +e
"$HAEX_INIT" --yes >"$SANDBOX_ROOT/haex-stdout" 2>"$SANDBOX_ROOT/haex-stderr"
rc=$?
set -e

sha_post=$(sha256sum "$HOME/.claude/CLAUDE.md" | awk '{print $1}')

assert_eq "(D) exit code MALFORMED" "2" "$rc"
assert_eq "(D) CLAUDE.md unchanged after refusal" "$sha_pre" "$sha_post"
if ! grep -q 'no matching end marker' "$SANDBOX_ROOT/haex-stderr"; then
    echo "FAIL(D): stderr did not name the malformed inconsistency"
    cat "$SANDBOX_ROOT/haex-stderr"
    exit 1
fi

teardown_sandbox
trap - EXIT

echo "test-marker-safety: PASS"
