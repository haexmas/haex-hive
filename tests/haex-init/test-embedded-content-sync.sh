#!/usr/bin/env bash
# test-embedded-content-sync.sh — verifies the three content-hash
# invariants named in Decision 9 (research.md):
#   (a) sha256(CANONICAL_SESSION_INSTRUCTIONS) == INSTRUCTIONS_SHA256
#   (b) sha256(.specify/templates/haex-hive-session-instructions.md)
#       == INSTRUCTIONS_SHA256
#   (c) sha256(EMBEDDED_SCHEMA_JSON) == sha256(.specify/schemas/haex-hive.schema.json)
# All three are pure content-hash checks with no tool invocation, so
# this test runs first in run-all.sh.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"

python3 - <<'PY'
import hashlib
import importlib.machinery
import importlib.util
import sys
from pathlib import Path

repo = Path(__file__).parent.parent.parent  # not used at runtime; heredoc lacks __file__
# The Python heredoc uses cwd (the test dir's parent) — compute repo root from cwd.
PY

python3 - <<PY
import hashlib, importlib.machinery, importlib.util, sys
from pathlib import Path

repo_root = Path("$REPO_ROOT")
tool = repo_root / ".specify/scripts/haex-init"

loader = importlib.machinery.SourceFileLoader("haex_init_sync", str(tool))
spec = importlib.util.spec_from_loader("haex_init_sync", loader)
m = importlib.util.module_from_spec(spec)
sys.modules["haex_init_sync"] = m
loader.exec_module(m)

# (a) Embedded string constant hashes to declared INSTRUCTIONS_SHA256.
sha_str = hashlib.sha256(m.CANONICAL_SESSION_INSTRUCTIONS.encode("utf-8")).hexdigest()
assert sha_str == m.INSTRUCTIONS_SHA256, (
    f"(a) FAIL: hash of CANONICAL_SESSION_INSTRUCTIONS {sha_str} != "
    f"declared INSTRUCTIONS_SHA256 {m.INSTRUCTIONS_SHA256}"
)
print(f"(a) OK: sha256(CANONICAL) == INSTRUCTIONS_SHA256 == {sha_str}")

# (b) Template file on disk hashes to INSTRUCTIONS_SHA256.
tpl = repo_root / ".specify/templates/haex-hive-session-instructions.md"
sha_tpl = hashlib.sha256(tpl.read_bytes()).hexdigest()
assert sha_tpl == m.INSTRUCTIONS_SHA256, (
    f"(b) FAIL: hash of {tpl} {sha_tpl} != "
    f"declared INSTRUCTIONS_SHA256 {m.INSTRUCTIONS_SHA256}"
)
print(f"(b) OK: sha256(template.md) == INSTRUCTIONS_SHA256")

# (c) Embedded schema string == canonical schema file.
canon = repo_root / ".specify/schemas/haex-hive.schema.json"
sha_emb = hashlib.sha256(m.EMBEDDED_SCHEMA_JSON.encode("utf-8")).hexdigest()
sha_canon = hashlib.sha256(canon.read_bytes()).hexdigest()
assert sha_emb == sha_canon, (
    f"(c) FAIL: sha256(EMBEDDED_SCHEMA_JSON)={sha_emb} != "
    f"sha256({canon})={sha_canon}"
)
print(f"(c) OK: sha256(EMBEDDED_SCHEMA_JSON) == sha256(canonical schema) == {sha_emb}")

# (d) Version-bump discipline (FR-033 + marker-block.format.md).
# When CANONICAL_SESSION_INSTRUCTIONS content changes on this branch
# vs. its parent commit, INSTRUCTIONS_VERSION MUST also change. This
# catches the "silently updated the hash without bumping the version"
# regression that (a)+(b) alone cannot detect.
import subprocess
def _extract_constant(source, name):
    """Return the value literal for the named constant, or None."""
    import re
    if name == "CANONICAL_SESSION_INSTRUCTIONS":
        mobj = re.search(
            r'CANONICAL_SESSION_INSTRUCTIONS\s*=\s*"""(.*?)"""',
            source,
            re.DOTALL,
        )
        return mobj.group(1) if mobj else None
    if name == "INSTRUCTIONS_VERSION":
        mobj = re.search(r'INSTRUCTIONS_VERSION\s*=\s*"([^"]+)"', source)
        return mobj.group(1) if mobj else None
    if name == "INSTRUCTIONS_SHA256":
        mobj = re.search(r'INSTRUCTIONS_SHA256\s*=\s*"([0-9a-f]+)"', source)
        return mobj.group(1) if mobj else None
    return None

# Find the parent revision to compare against. Prefer origin/main; fall
# back to HEAD^ inside a checked-out branch. On a fresh clone or CI shallow
# clone with no parent to compare, the check is skipped with a printed note
# rather than failing — the (a)+(b) hash-sync assertions above still hold.
inside_git = subprocess.run(
    ["git", "-C", str(repo_root), "rev-parse", "--is-inside-work-tree"],
    capture_output=True, text=True, check=False,
).stdout.strip() == "true"
if not inside_git:
    print("(d) SKIP: not inside a git working tree")
else:
    ref_probe = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", "HEAD", "origin/main"],
        capture_output=True, text=True, check=False,
    )
    parent = ref_probe.stdout.strip() if ref_probe.returncode == 0 else ""
    if not parent:
        alt = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD^"],
            capture_output=True, text=True, check=False,
        )
        parent = alt.stdout.strip() if alt.returncode == 0 else ""
    if not parent:
        print("(d) SKIP: no parent commit to compare against")
    else:
        prior = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{parent}:.specify/scripts/haex-init"],
            capture_output=True, text=True, check=False,
        )
        if prior.returncode != 0:
            # merge-base predates haex-init; fall back to the direct parent
            # of HEAD (which does have haex-init once the initial landing
            # commit exists on this branch).
            alt = subprocess.run(
                ["git", "-C", str(repo_root), "rev-parse", "HEAD^"],
                capture_output=True, text=True, check=False,
            )
            fallback_parent = alt.stdout.strip() if alt.returncode == 0 else ""
            if fallback_parent and fallback_parent != parent:
                prior = subprocess.run(
                    ["git", "-C", str(repo_root), "show",
                     f"{fallback_parent}:.specify/scripts/haex-init"],
                    capture_output=True, text=True, check=False,
                )
                if prior.returncode == 0:
                    parent = fallback_parent
        if prior.returncode != 0:
            print(f"(d) SKIP: haex-init not present at any reachable parent revision")
        else:
            prior_src = prior.stdout
            prior_canon = _extract_constant(prior_src, "CANONICAL_SESSION_INSTRUCTIONS")
            prior_ver = _extract_constant(prior_src, "INSTRUCTIONS_VERSION")
            cur_canon = m.CANONICAL_SESSION_INSTRUCTIONS
            cur_ver = m.INSTRUCTIONS_VERSION
            if prior_canon is None or prior_ver is None:
                print("(d) SKIP: parent revision predates versioned canonical constants")
            elif prior_canon == cur_canon:
                print(f"(d) OK: canonical text unchanged since {parent[:8]}; version bump not required")
            else:
                assert cur_ver != prior_ver, (
                    f"(d) FAIL: CANONICAL_SESSION_INSTRUCTIONS changed vs {parent[:8]} "
                    f"but INSTRUCTIONS_VERSION is still {prior_ver!r}. "
                    "Bump INSTRUCTIONS_VERSION (semver: PATCH wording, MINOR new "
                    "instruction line, MAJOR breaking rewrite) alongside the hash "
                    "update. See specs/005-haex-init/contracts/marker-block.format.md "
                    "\"Version Bump Semantics\"."
                )
                print(f"(d) OK: canonical changed vs {parent[:8]}, version bumped {prior_ver} → {cur_ver}")

print("test-embedded-content-sync: assertions passed")
PY
