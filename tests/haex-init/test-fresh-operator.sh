#!/usr/bin/env bash
# test-fresh-operator.sh — SC-001a plus US1 acceptance scenarios 3 and 4.
# Sub-cases:
#   (A) select-all happy path (--yes drives full auto-confirmation)
#   (B) partial selection — IDE only (interactive scripted stdin)
#   (C) declined-prompt propagation (interactive scripted stdin, first N + rest Y)

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/sandbox.sh"
FIXTURES="$HERE/fixtures/.tmp/fixtures.env"
[[ -f "$FIXTURES" ]] || (cd "$HERE" && ./fixtures/build-fixtures.sh)
# shellcheck disable=SC1090
source "$FIXTURES"

# ---------------------------------------------------------------------------
# (A) select-all happy path via --yes.
# ---------------------------------------------------------------------------
echo "-- (A) select-all happy path via --yes"

setup_sandbox "fresh-operator-A"
trap teardown_sandbox EXIT

install_fake_bin claude
install_fake_bin code
create_fake_config_dir claude-code
create_fake_config_dir vscode
git init --quiet -b main .

out=$("$HAEX_INIT" --yes 2>&1 || true)

if [[ ! -f "$HOME/.haex-hive/haex-hive.md" ]]; then
    echo "FAIL(A): ~/.haex-hive/haex-hive.md was not created"
    echo "$out" >&2
    exit 1
fi
python3 - <<PY
import hashlib, importlib.machinery, importlib.util, sys
loader = importlib.machinery.SourceFileLoader("hi", "$HAEX_INIT")
spec = importlib.util.spec_from_loader("hi", loader)
m = importlib.util.module_from_spec(spec); sys.modules["hi"]=m; loader.exec_module(m)
p = "$HOME/.haex-hive/haex-hive.md"
actual = hashlib.sha256(open(p,'rb').read()).hexdigest()
assert actual == m.INSTRUCTIONS_SHA256, f"(A) FAIL: instructions file SHA {actual} != {m.INSTRUCTIONS_SHA256}"
print("(A) instructions file SHA matches")
PY

version=$(cat "$HOME/.haex-hive/VERSION")
assert_eq "(A) VERSION content" "1.0" "$version"

if ! grep -q "haex-hive-block:begin v=1.0" "$HOME/.claude/CLAUDE.md"; then
    echo "FAIL(A): ~/.claude/CLAUDE.md missing v=1.0 marker block"
    cat "$HOME/.claude/CLAUDE.md"
    exit 1
fi

# Verify .haex-hive.json shape.
python3 - <<PY
import json
d = json.load(open(".haex-hive.json"))
assert d["haex_hive_version"] == "1", f"(A) FAIL haex_hive_version: {d['haex_hive_version']!r}"
assert d["harness_sources"] == [], f"(A) FAIL harness_sources: {d['harness_sources']!r}"
assert isinstance(d["identity"], str) and len(d["identity"]) > 0, "(A) FAIL identity"
print("(A) .haex-hive.json shape OK")
PY

# Byte-identity check on schema file.
python3 - <<PY
import hashlib, importlib.machinery, importlib.util, sys
loader = importlib.machinery.SourceFileLoader("hi", "$HAEX_INIT")
spec = importlib.util.spec_from_loader("hi", loader)
m = importlib.util.module_from_spec(spec); sys.modules["hi"]=m; loader.exec_module(m)
p = ".specify/schemas/haex-hive.schema.json"
actual = hashlib.sha256(open(p,'rb').read()).hexdigest()
expected = hashlib.sha256(m.EMBEDDED_SCHEMA_JSON.encode('utf-8')).hexdigest()
assert actual == expected, f"(A) FAIL: schema file SHA {actual} != EMBEDDED {expected}"
print("(A) schema file byte-identical to EMBEDDED_SCHEMA_JSON")
PY

if ! grep -q '"fileMatch"' .vscode/settings.json; then
    echo "FAIL(A): .vscode/settings.json missing schema-mapping entry"
    cat .vscode/settings.json
    exit 1
fi

# One scaffolding commit exists.
commit_count=$(git rev-list --count HEAD 2>/dev/null || echo 0)
assert_eq "(A) commit count" "1" "$commit_count"

# Action-report contains expected [x] lines.
assert_contains "(A) report banner" "$out" "haex-init action report"
assert_contains "(A) marker block" "$out" "appended marker block v=1.0"

echo "-- (A) OK"
teardown_sandbox
trap - EXIT

# ---------------------------------------------------------------------------
# (B) IDE-only selection — scripted stdin, both LLM and IDE detected.
# Prompt 1 accepts 1-indexed numbers; we pick the IDE only.
# ---------------------------------------------------------------------------
echo "-- (B) IDE-only selection via scripted stdin"

setup_sandbox "fresh-operator-B"
trap teardown_sandbox EXIT

install_fake_bin claude
install_fake_bin code
create_fake_config_dir claude-code
create_fake_config_dir vscode
git init --quiet -b main .

# Pre-record ~/.claude/CLAUDE.md SHA before to prove it stays untouched.
mkdir -p "$HOME/.claude"
printf 'Pre-existing operator content\n' > "$HOME/.claude/CLAUDE.md"
sha_before=$(sha256sum "$HOME/.claude/CLAUDE.md" | awk '{print $1}')

# Selection order: LLMs sorted then IDEs sorted; two tools total → [1] claude-code, [2] vscode.
# We pick "2" → IDE only.
# Then constitution mode "1" (self-ref). Then Y to every per-action prompt.
# Then Y to git init prompt (project is already git) and Y to commit prompt.
{
    printf '2\n'    # tool selection
    printf '1\n'    # self-ref
    for _ in $(seq 1 30); do printf 'y\n'; done  # apply every prompt
} > "$SANDBOX_ROOT/stdin.txt"

# Simulate a TTY by using `script -qc`? Simpler: use --yes wrapped variant.
# The test spec requires the interactive path here — we drive it by piping
# stdin, and the tool's non-TTY guard requires --yes. We resolve this by
# ALSO passing --yes AND scripting stdin — --yes short-circuits any Y/N,
# but tool-selection is a free-form prompt that --yes does NOT bypass in
# the "no auto-answer" path. Instead: use a Python pty wrapper.
python3 - <<PY
import os, pty, subprocess, sys, time, select

env = os.environ.copy()
proc_out = []

def run_with_pty(cmd, stdin_data):
    master, slave = pty.openpty()
    p = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
    os.close(slave)
    # Write stdin over a small delay so the child sees prompts first.
    remaining = stdin_data
    deadline = time.time() + 20
    while time.time() < deadline:
        r, w, _ = select.select([master], [master] if remaining else [], [], 0.2)
        if master in r:
            try:
                chunk = os.read(master, 4096)
            except OSError:
                break
            if not chunk:
                break
            proc_out.append(chunk)
        if master in w and remaining:
            try:
                n = os.write(master, remaining[:512].encode())
                remaining = remaining[n:]
            except OSError:
                remaining = b""
        if p.poll() is not None:
            # Drain remaining output.
            try:
                while True:
                    r2, _, _ = select.select([master], [], [], 0.1)
                    if not r2: break
                    chunk = os.read(master, 4096)
                    if not chunk: break
                    proc_out.append(chunk)
            except OSError:
                pass
            break
    os.close(master)
    return p.wait(), b"".join(proc_out).decode("utf-8", errors="replace")

stdin_data = open("$SANDBOX_ROOT/stdin.txt").read()
rc, out = run_with_pty(["$HAEX_INIT"], stdin_data)
print(out)
print(f"exit={rc}")
sys.exit(0 if rc == 0 else rc)
PY
rc=$?
if [[ $rc -ne 0 ]]; then
    echo "FAIL(B): haex-init exited $rc"
    exit 1
fi

sha_after=$(sha256sum "$HOME/.claude/CLAUDE.md" | awk '{print $1}')
assert_eq "(B) CLAUDE.md byte-identical (LLM was skipped)" "$sha_before" "$sha_after"

if ! grep -q '"fileMatch"' .vscode/settings.json; then
    echo "FAIL(B): .vscode/settings.json missing entry"
    exit 1
fi

echo "-- (B) OK"
teardown_sandbox
trap - EXIT

# ---------------------------------------------------------------------------
# (C) Declined-prompt propagation.
# ---------------------------------------------------------------------------
echo "-- (C) declined-prompt propagation via scripted stdin"

setup_sandbox "fresh-operator-C"
trap teardown_sandbox EXIT

install_fake_bin claude
install_fake_bin code
create_fake_config_dir claude-code
create_fake_config_dir vscode
git init --quiet -b main .

# Selection: all. Mode: self-ref. First per-action prompt (haex-hive.md create) → N.
# Every subsequent Y/N → Y.
python3 - <<'PY'
import os, pty, subprocess, sys, time, select

env = os.environ.copy()
proc_out = []

def run_with_pty(cmd, stdin_bytes):
    master, slave = pty.openpty()
    p = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
    os.close(slave)
    remaining = stdin_bytes
    deadline = time.time() + 20
    while time.time() < deadline:
        r, w, _ = select.select([master], [master] if remaining else [], [], 0.2)
        if master in r:
            try:
                chunk = os.read(master, 4096)
            except OSError:
                break
            if not chunk:
                break
            proc_out.append(chunk)
        if master in w and remaining:
            try:
                n = os.write(master, remaining[:512])
                remaining = remaining[n:]
            except OSError:
                remaining = b""
        if p.poll() is not None:
            try:
                while True:
                    r2, _, _ = select.select([master], [], [], 0.1)
                    if not r2: break
                    chunk = os.read(master, 4096)
                    if not chunk: break
                    proc_out.append(chunk)
            except OSError:
                pass
            break
    os.close(master)
    return p.wait(), b"".join(proc_out).decode("utf-8", errors="replace")

# Selection: all; mode: 1 (self-ref); first Apply prompt: n; then y * 30.
stdin_data = b"all\n1\nn\n" + b"y\n" * 30
rc, out = run_with_pty([os.environ["HAEX_INIT"]], stdin_data)
print(out)
if "haex-init action report" not in out:
    print("FAIL(C): no action report", file=sys.stderr)
    sys.exit(1)
if "[-]" not in out:
    print("FAIL(C): expected at least one [-] in report", file=sys.stderr)
    sys.exit(1)
sys.exit(0)
PY

# The declined action was ~/.haex-hive/haex-hive.md.
if [[ -f "$HOME/.haex-hive/haex-hive.md" ]]; then
    echo "FAIL(C): declined ~/.haex-hive/haex-hive.md was still created"
    exit 1
fi
# But subsequent independent actions should have executed (VERSION, .haex-hive.json, etc.)
if [[ ! -f ".haex-hive.json" ]]; then
    echo "FAIL(C): .haex-hive.json not created — declined prompt starved subsequent actions"
    exit 1
fi

echo "-- (C) OK"
teardown_sandbox
trap - EXIT

echo "test-fresh-operator: PASS"
