#!/usr/bin/env bash
# test-version-upgrade.sh — FR-028.
#
# Run --yes to completion (writes v=1.0 marker block), then patch a scratch
# copy of the tool to declare v=1.1 with new content + regenerated SHA,
# re-run the scratch tool, assert the marker block was replaced and every
# byte outside the block is untouched.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/sandbox.sh"

setup_sandbox "version-upgrade"
trap teardown_sandbox EXIT

install_fake_bin claude
install_fake_bin code
create_fake_config_dir claude-code
create_fake_config_dir vscode
git init --quiet -b main .

"$HAEX_INIT" --yes >/dev/null

# Confirm the block is at v=1.0.
if ! grep -q 'v=1.0' "$HOME/.claude/CLAUDE.md"; then
    echo "FAIL: initial run did not write v=1.0"
    exit 1
fi

# Snapshot the marker-excised content. Bytes excluding the marker block
# (from begin marker line to end marker line inclusive).
pre_excised=$(python3 - <<'PY'
import re, hashlib, os
p = os.path.expanduser("~/.claude/CLAUDE.md")
raw = open(p, "rb").read()
lines = raw.decode("utf-8").split("\n")
begin_re = re.compile(r'^<!--\s*haex-hive-block:begin\s+v=([^\s>]+)\s*-->$')
end_re = re.compile(r'^<!--\s*haex-hive-block:end\s*-->$')
b = e = None
for i, line in enumerate(lines):
    if begin_re.match(line): b = i
    if end_re.match(line): e = i
if b is None or e is None:
    raise SystemExit("no block found")
outside = lines[:b] + lines[e+1:]
sha = hashlib.sha256("\n".join(outside).encode("utf-8")).hexdigest()
print(sha)
PY
)

# Prepare a scratch copy of haex-init with v=1.1 and different canonical content.
SCRATCH="$SANDBOX_ROOT/haex-init-newer"
cp "$HAEX_INIT" "$SCRATCH"
python3 - <<PY
import hashlib, re
p = "$SCRATCH"
s = open(p, "r").read()
newer = '# haex-hive session instructions (v=1.1 fixture)\n\nUpgraded content for the version-drift test.\n'
sha_new = hashlib.sha256(newer.encode("utf-8")).hexdigest()
# Replace the triple-quoted CANONICAL constant. Use a callable replacement
# so backslashes in 'newer' are not interpreted as re.sub backreferences.
def _repl(_m):
    return "CANONICAL_SESSION_INSTRUCTIONS = " + repr(newer)
# re.subn so a missed substitution surfaces as a named failure here rather
# than as an unrelated hash mismatch later.
s, n = re.subn(
    r'CANONICAL_SESSION_INSTRUCTIONS = """.*?"""',
    _repl,
    s,
    count=1,
    flags=re.DOTALL,
)
assert n == 1, "patch failed: CANONICAL_SESSION_INSTRUCTIONS literal not found in haex-init"
s, n = re.subn(r'INSTRUCTIONS_VERSION = "1\.0"', 'INSTRUCTIONS_VERSION = "1.1"', s, count=1)
assert n == 1, 'patch failed: INSTRUCTIONS_VERSION = "1.0" not found in haex-init'
s, n = re.subn(r'INSTRUCTIONS_SHA256 = "[0-9a-f]+"', 'INSTRUCTIONS_SHA256 = "' + sha_new + '"', s, count=1)
assert n == 1, "patch failed: INSTRUCTIONS_SHA256 not found in haex-init"
open(p, "w").write(s)
PY
chmod +x "$SCRATCH"

# Run the scratch tool.
"$SCRATCH" --yes >/dev/null

# Marker block must now stamp v=1.1.
if ! grep -q 'v=1.1' "$HOME/.claude/CLAUDE.md"; then
    echo "FAIL: v=1.1 marker not present after upgrade run"
    grep 'haex-hive-block' "$HOME/.claude/CLAUDE.md" >&2
    exit 1
fi
if grep -q 'v=1.0' "$HOME/.claude/CLAUDE.md"; then
    echo "FAIL: old v=1.0 marker still present"
    exit 1
fi

# Content outside the marker block must be byte-identical (SC-002).
post_excised=$(python3 - <<'PY'
import re, hashlib, os
p = os.path.expanduser("~/.claude/CLAUDE.md")
raw = open(p, "rb").read()
lines = raw.decode("utf-8").split("\n")
begin_re = re.compile(r'^<!--\s*haex-hive-block:begin\s+v=([^\s>]+)\s*-->$')
end_re = re.compile(r'^<!--\s*haex-hive-block:end\s*-->$')
b = e = None
for i, line in enumerate(lines):
    if begin_re.match(line): b = i
    if end_re.match(line): e = i
outside = lines[:b] + lines[e+1:]
sha = hashlib.sha256("\n".join(outside).encode("utf-8")).hexdigest()
print(sha)
PY
)
assert_eq "content outside marker block byte-identical" "$pre_excised" "$post_excised"

echo "test-version-upgrade: PASS"
