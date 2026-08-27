# Quickstart: Cross-Repo References

**Feature**: 004-cross-repo-refs
**Audience**: operator opening this repo (or a future haex-hive-opted-in
repo) for the first time after Spec 004 lands.

Concrete, copy-pasteable steps that prove Spec 004's mechanism works
end-to-end. Written to mirror the User Stories in `spec.md`.

## Prerequisites

- Linux (macOS/WSL2 deferred per spec).
- Python 3.10+ on `$PATH`.
- Git 2.30+ on `$PATH`.
- Fresh clone of the repo (or existing clone with the working tree
  reset to the Spec 004 landing commit).

Sanity check:

```bash
python3 --version    # → Python 3.10+ 
git --version        # → git version 2.30+
```

## Story 1 — Fresh session resolves the pinned constitution

Simulates a fresh session opening the repo for the first time.

```bash
# 1. Ensure cache is absent so we exercise cold path.
rm -rf ~/.cache/haex-hive/

# 2. Verify the config is valid before doing anything else.
.specify/scripts/spec-resolve status
```

Expected output (text mode):

```text
1 ref, 1 cached, last update-check: never
```

`self` references count as always cached — the local repo already
has the constitution's SHA reachable, so nothing needs fetching.

```bash
# 3. Resolve the constitution and verify the content.
.specify/scripts/spec-resolve resolve --role constitution > /tmp/const-resolved.md
diff /tmp/const-resolved.md .specify/memory/constitution.md
```

Expected: `diff` produces no output (exit 0). The resolved content
is byte-identical to the file at the pinned SHA.

## Story 1b — Offline second run

```bash
# Disconnect network here (or use `unshare -n` on Linux).
.specify/scripts/spec-resolve resolve --role constitution > /tmp/const-again.md
diff /tmp/const-resolved.md /tmp/const-again.md
```

Expected: `diff` produces no output. No network was attempted (a
`self` reference always resolves offline).

## Story 2 — Refusal of a reference not in the allowlist

Uses a scratch spec-ref that points outside the allowlist. Does NOT
modify `.haex-hive.json`.

```bash
# 1. Create a scratch spec-ref pointing at an external repo.
mkdir -p /tmp/spec-004-refusal-test/specs/scratch
cat > /tmp/spec-004-refusal-test/specs/scratch/spec-ref.json <<'JSON'
{
  "not-allowed": {
    "repository": "https://gitlab.com/itemis/solutions/pltf/secana-specs",
    "revision": "0000000000000000000000000000000000000000",
    "path": "README.md"
  }
}
JSON

# 2. Copy this repo's .haex-hive.json into the scratch tree
#    (so the resolver sees the same allowlist).
cp .haex-hive.json /tmp/spec-004-refusal-test/.haex-hive.json

# 3. Attempt to resolve.
cd /tmp/spec-004-refusal-test
{{PWD}}/.specify/scripts/spec-resolve resolve --from specs/scratch/spec-ref.json
echo "exit: $?"
```

Expected:

- Exit code: `1`
- Stderr contains a message like: `spec-resolve: refusing reference https://gitlab.com/…@0000…:README.md — not permitted by any entry in harness_sources.`
- No file written under the scratch tree.

Cleanup:

```bash
cd -
rm -rf /tmp/spec-004-refusal-test
```

## Story 3 — Malformed config rejected before harness work starts

Uses a scratch tree with a broken config.

```bash
mkdir -p /tmp/spec-004-invalid-test
cp .haex-hive.json /tmp/spec-004-invalid-test/

# Introduce an unknown role.
python3 <<'PY'
import json, pathlib
p = pathlib.Path("/tmp/spec-004-invalid-test/.haex-hive.json")
data = json.loads(p.read_text())
data["harness_sources"][0]["role"] = "definitely-not-a-real-role"
p.write_text(json.dumps(data, indent=2))
PY

cd /tmp/spec-004-invalid-test
{{PWD}}/.specify/scripts/spec-resolve status
echo "exit: $?"
```

Expected:

- Exit code: `2`
- Stderr contains: `unknown role 'definitely-not-a-real-role'` and
  names the array index (`harness_sources[0]`) plus the valid values
  (`constitution`).

Repeat with each of these malformations, one at a time:

- Remove `revision` from the role entry → exit 2, "required field
  revision missing".
- Add `paths` array to the role entry → exit 2, "path and paths are
  mutually exclusive; role-carrying entries use path".
- Change `revision` to a mixed-case or non-hex value → exit 2, invalid
  SHA pattern.
- Change `repository` to `file:///tmp/foo` → exit 2, rejected URL
  scheme.

Cleanup:

```bash
cd -
rm -rf /tmp/spec-004-invalid-test
```

## Story 4 — Editor validation via JSON Schema

Two mainstream editor setups:

### VSCode

Add to your workspace or user `settings.json`:

```json
{
  "json.schemas": [
    {
      "fileMatch": [".haex-hive.json"],
      "url": "./.specify/schemas/haex-hive.schema.json"
    }
  ]
}
```

Then open `.haex-hive.json`. Break something (e.g., type `"role":
"cons"` in an entry). The editor shows an inline squiggle and a
message like `Value is not accepted. Valid values: "constitution".`

### JetBrains (IntelliJ / PyCharm / GoLand / ...)

Preferences → Languages & Frameworks → Schemas and DTDs → JSON Schema
Mappings → `+` → Schema file: `.specify/schemas/haex-hive.schema.json`,
File pattern: `.haex-hive.json`.

Same test: type an invalid role, observe the inline error.

## Prefetch flow for a repo with an external source

Not exercised by haex-hive itself (which uses only `self`), but
documented for a consuming repo:

```bash
# Assume .haex-hive.json contains one 'self' role entry plus one
# permission-only entry naming an external repo. A spec's spec-ref.json
# pins a real SHA in that external repo.

.specify/scripts/spec-resolve prefetch
```

First run fetches Git objects into `~/.cache/haex-hive/repos/<hash>/`.
Second run is a no-op (cache hit). Dry-run mode (`--dry-run`) lists
which references would be fetched, no side effect.

## Success criteria checkpoint

Running through this quickstart, the operator directly verifies:

- **SC-001** (device-independent resolution): Story 1's `diff` succeeds.
- **SC-002** (offline safety): Story 1b's `diff` succeeds without network.
- **SC-004** (actionable error messages): Story 2 and Story 3 messages
  can be acted on without external doc lookup.
- **SC-006** (allowlist coverage): Story 2 hits the refusal path.
- **SC-008** (`system.yaml` gone): after Spec 004 lands, `git grep
  external_sources` returns matches only in historical files.

SC-003 (cross-machine byte-identical resolution) requires two
machines; run Story 1 on both, `sha256sum` the output on each, verify
equality.

SC-005 (schema/tool agreement) is exercised by the test suite, not
this quickstart.

SC-007 (constitution v1.1.1) is verified by
`.specify/memory/constitution.md`'s version line after Spec 004
lands.
