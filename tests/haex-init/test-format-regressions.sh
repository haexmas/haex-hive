#!/usr/bin/env bash
# test-format-regressions.sh — parser-shape fixtures the review flagged.
#
# 1. Marker-block detection MUST recognise the block on both LF and
#    CRLF files. A CRLF file classified as ABSENT would trigger a
#    duplicate insertion on rerun.
# 2. compose_idea_xml() MUST match by local name so a JetBrains
#    document with an XML namespace on <project> still parses and
#    round-trips with its namespace intact.
#
# Both fixtures drive the Python surface directly — no CLI invocation
# needed — so this test runs quickly under run-all.sh.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib/sandbox.sh"

setup_sandbox "format-regressions"
trap 'teardown_sandbox' EXIT

python3 - <<PY
import importlib.machinery, importlib.util, sys
from pathlib import Path
loader = importlib.machinery.SourceFileLoader("hi", "$HAEX_INIT")
spec = importlib.util.spec_from_loader("hi", loader)
m = importlib.util.module_from_spec(spec); sys.modules["hi"]=m; loader.exec_module(m)

# --------------------------------------------------------------------
# 1. Marker detection on LF vs CRLF fixtures.
# --------------------------------------------------------------------
lf_body = (
    "# operator notes\n"
    "\n"
    "<!-- haex-hive-block:begin v=1.0 -->\n"
    "## haex-hive\n"
    "\n"
    "one line\n"
    "<!-- haex-hive-block:end -->\n"
    "\n"
    "post-marker text\n"
)
crlf_body = lf_body.replace("\n", "\r\n")

sandbox = Path("$SANDBOX_ROOT")
lf = sandbox / "lf.md"
crlf = sandbox / "crlf.md"
lf.write_bytes(lf_body.encode("utf-8"))
crlf.write_bytes(crlf_body.encode("utf-8"))

lf_state = m.detect_marker_block(lf)
crlf_state = m.detect_marker_block(crlf)

for name, state in (("LF", lf_state), ("CRLF", crlf_state)):
    assert state.presence in (
        m.MarkerPresence.PRESENT_MATCHING_VERSION,
        m.MarkerPresence.PRESENT_MISMATCHED_VERSION,
    ), f"{name} marker misclassified as {state.presence!r} (should be PRESENT_*)"
    assert state.existing_byte_range is not None, f"{name} missing byte range"
    print(f"  marker {name}: {state.presence.value} range={state.existing_byte_range}")

# Byte-range covers the exact BEGIN..END block for both fixtures.
for name, body, state in (("LF", lf_body, lf_state), ("CRLF", crlf_body, crlf_state)):
    start, end = state.existing_byte_range
    slice_bytes = body.encode("utf-8")[start:end]
    assert b"haex-hive-block:begin" in slice_bytes and b"haex-hive-block:end" in slice_bytes, (
        f"{name} byte range does not enclose the full block"
    )
print("  marker LF+CRLF regression fixtures pass")

# --------------------------------------------------------------------
# 2. Namespaced JetBrains XML round-trip.
# --------------------------------------------------------------------
ns_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="urn:test:jetbrains" version="4">
  <component name="JsonSchemaMappingsProjectConfiguration">
    <state>
      <map>
        <entry key="pre-existing">
          <value>
            <SchemaInfo>
              <option name="name" value="pre-existing"/>
              <option name="relativePathToSchema" value="./other.json"/>
              <option name="applicationLevel" value="false"/>
              <option name="projectLevel" value="true"/>
              <option name="patterns">
                <list>
                  <Item>
                    <option name="pattern" value="other-config.json"/>
                  </Item>
                </list>
              </option>
            </SchemaInfo>
          </value>
        </entry>
      </map>
    </state>
  </component>
</project>
"""
merged = m.compose_idea_xml(ns_xml)
merged_str = merged.decode("utf-8")
assert 'xmlns="urn:test:jetbrains"' in merged_str, (
    "namespace attribute lost on re-serialize:\n" + merged_str
)
assert 'key="pre-existing"' in merged_str, "pre-existing entry dropped"
assert 'key="haex-hive"' in merged_str, "haex-hive entry not merged in"
print("  namespaced JetBrains XML: parsed + merged + namespace preserved")

# --------------------------------------------------------------------
# 3. Symlink outside HOME → MALFORMED refusal.
# --------------------------------------------------------------------
outside = sandbox / "outside-of-home.md"
outside.write_bytes(b"# somewhere outside\n")
link = Path("$HOME") / ".claude" / "CLAUDE.md"
link.parent.mkdir(parents=True, exist_ok=True)
link.symlink_to(outside)
state = m.detect_marker_block(link)
assert state.presence is m.MarkerPresence.MALFORMED, (
    f"symlink outside HOME should be MALFORMED, got {state.presence!r}"
)
assert "outside" in (state.malformed_reason or "") and "HOME" in (state.malformed_reason or ""), (
    f"unexpected malformed reason: {state.malformed_reason!r}"
)
print("  symlink outside HOME: refused as MALFORMED")

# --------------------------------------------------------------------
# 4. managed_tools == [] is preserved as "select-none" (not None).
# --------------------------------------------------------------------
class _FakeState:
    has_haex_hive_json = True
    haex_hive_json_valid = True
    haex_hive_json_content = {"managed_tools": []}

result = m._read_persisted_managed_tools(_FakeState())
assert result == set(), (
    f"managed_tools=[] should preserve as empty set, got {result!r}"
)

class _AbsentState:
    has_haex_hive_json = True
    haex_hive_json_valid = True
    haex_hive_json_content = {}  # managed_tools absent → legacy fallback

assert m._read_persisted_managed_tools(_AbsentState()) is None, (
    "absent managed_tools should read as None (legacy fallback)"
)
print("  managed_tools=[] preserved as select-none; absent → None")

# --------------------------------------------------------------------
# 5. validate_external_sha rejects short prefixes.
# --------------------------------------------------------------------
short = "0" * 39
err = m.validate_external_sha(short)
assert err is not None, "short SHA should be rejected"
full = "0" * 40
assert m.validate_external_sha(full) is None, (
    f"full 40-char SHA should be accepted, got {m.validate_external_sha(full)!r}"
)
print(f"  SHA length: rejected {len(short)}-char prefix, accepted 40-char full SHA")

print("test-format-regressions: PASS")
PY
