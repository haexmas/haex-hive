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

print("test-embedded-content-sync: all 3 assertions passed")
PY
