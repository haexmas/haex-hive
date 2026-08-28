# Phase 0 Research: `haex-init`

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Date**: 2026-08-27

## Purpose

Resolve every plan-level decision that would otherwise become
"NEEDS CLARIFICATION" in `plan.md`'s Technical Context. Each decision
below states what was chosen, why, and what was rejected.

## Decisions

### Decision 1 — Marker block detection: line-anchored regex, not free-form parsing

**Chosen**: A pair of exact line-anchored markers with a version
attribute exposed only in `begin`:

```
<!-- haex-hive-block:begin v=<semver> -->
… body …
<!-- haex-hive-block:end -->
```

Detection uses two Python regex patterns applied line-by-line:

```python
BEGIN_RE = re.compile(r'^<!--\s*haex-hive-block:begin\s+v=([^\s>]+)\s*-->$')
END_RE   = re.compile(r'^<!--\s*haex-hive-block:end\s*-->$')
```

Where a file contains:

- neither marker → block is absent → append action.
- exactly one begin + exactly one end, begin appears before end
  → block exists → capture version + inclusive line range.
- any other combination (begin without end, end without begin,
  duplicate begins, begin after end) → refuse per FR-010 with a
  specific inconsistency message quoting the offending lines.

**Rationale**: Line-anchored regex is trivial to reason about, works
byte-safely with any line-ending scheme (LF / CRLF), and lets us
compute an exact byte range for the block. A more elaborate scheme
(comment nesting, structured metadata inside the block, JSON
sidecar) would violate FR-032's English-plain-text bias and add
maintenance surface.

**Rejected**:

- **HTML-comment-aware parser** (nested comments, attributes,
  self-closing forms): overkill for a two-line pattern.
- **Content hash sidecar** (`.haex-hive-block.sha`): breaks
  single-file-write semantics and creates a new drift surface.
- **Placing the version inside the block body** (e.g. as a
  Markdown line): would require touching non-marker content on
  every version bump.

### Decision 2 — Two-signal LLM/IDE detection

**Chosen**: For each candidate tool, both signals must be true to
consider it "detected":

1. Executable-on-`$PATH` signal: `shutil.which(<exe>)` returns a
   non-None path.
2. User-config-dir signal: `<config-dir>` exists as a directory.

Table of detection targets for Phase 1:

| Tool | Exe(s) | Config dir |
|------|--------|------------|
| Claude Code | `claude` | `~/.claude/` |
| Codex | `codex` | `~/.codex/` |
| Gemini | `gemini` | `~/.gemini/` |
| VSCode | `code` | `~/.config/Code/` (Linux) |
| VSCode Insiders | `code-insiders` | `~/.config/Code - Insiders/` |
| Cursor | `cursor` | `~/.config/Cursor/` |
| Windsurf | `windsurf` | `~/.config/Windsurf/` |
| JetBrains (family) | any of `idea`, `pycharm`, `goland`, `webstorm`, `phpstorm`, `rubymine`, `clion`, `datagrip`, `rider`, `studio` | `~/.config/JetBrains/` |

**Rationale**: Either signal alone is unreliable. Executable-only
misses tools installed but never opened; config-dir-only misses
tools where the config dir persists after uninstall. Both signals
match observed operator behavior — the tool has been installed AND
run at least once, which is the state where hooking it up is
meaningful.

For JetBrains, a family-level detection is intentional: the
mapping file `.idea/jsonSchemas.xml` is IDE-agnostic across the
family. A single "JetBrains detected" signal is sufficient; the
operator's specific IDE (IntelliJ vs PyCharm) does not change what
haex-init writes.

**Rejected**:

- **Executable-only**: too many false positives on machines with
  stale binaries.
- **Config-dir-only**: too many false positives on machines that
  have been uninstalled but left the config dir.
- **Running-process signal**: brittle and privacy-adjacent.
- **VSCode-family single-signal**: Cursor and Windsurf ship distinct
  executables and distinct config dirs; treating them as one signal
  would misroute the mapping-file write.

### Decision 3 — External-ref verification: separate scratch cache, not `spec-resolve`'s

**Chosen**: External-ref verification runs in
`$XDG_CACHE_HOME/haex-init/verify/<hash>/` — a dedicated haex-init
cache, distinct from `spec-resolve`'s `$XDG_CACHE_HOME/haex-hive/repos/`.
Verification steps:

1. Ensure the scratch dir exists (init a bare-shape objects-only
   directory the first time).
2. `git fetch --no-tags --depth=1 <url> <sha>` into that dir.
3. `git cat-file -e <sha>:<path>` — reachable path check.
4. `git cat-file -s <sha>:<path>` — non-empty content check.

**Rationale**:

- The operator has not yet approved `spec-resolve` to talk to that
  URL (allowlist entry is what we're about to WRITE). Polluting
  `spec-resolve`'s cache pre-approval would be a Principle-V-adjacent
  violation.
- Scratch cache is short-lived; on verification success `haex-init`
  writes the allowlist entry and lets the next `spec-resolve` run
  populate the real cache from scratch.
- Fetching only the exact SHA (not full history) matches the spec-
  resolve fetch ladder and keeps the disk cost low.

**Rejected**:

- **Fetch into `spec-resolve`'s cache directly**: violates the
  allowlist-first ordering.
- **Fetch into `$TMPDIR`**: repeated retries after correcting a
  wrong path re-download the same objects; wasteful on flaky
  networks.
- **`git ls-remote` only**: verifies the SHA is advertised but
  cannot verify the path exists or is non-empty.

### Decision 4 — Diff preview format: unified diff, plain text, no coloring

**Chosen**: Every Y/N-gated write is preceded by a preview in
standard unified-diff format:

```
--- /home/…/CLAUDE.md (current)
+++ /home/…/CLAUDE.md (proposed)
@@ -12,3 +12,9 @@
 (context)
+<!-- haex-hive-block:begin v=1.0 -->
+…
+<!-- haex-hive-block:end -->
```

Produced via `difflib.unified_diff` (stdlib). No ANSI colour codes.
No custom widths.

**Rationale**: Universal readability, terminal-agnostic, matches
what operators see in `git diff` output. Colour requires TTY
detection and adds a fallback path. Plain unified diff is the
lowest-common-denominator format every operator already knows.

**Rejected**:

- **Colored diff via `colorama`**: third-party dep, not allowed.
- **Side-by-side diff**: too wide for narrow terminals; unified is
  the standard.
- **Only "before/after"**: hides the mechanical delta; a full diff
  makes intent explicit.

### Decision 5 — VSCode `.vscode/settings.json` merge shape

**Chosen**: haex-init writes an `json.schemas` array entry — merging
into any existing JSON file, not overwriting it. When the file does
not exist, create it with:

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

When the file exists:

1. Parse it with `json.load` (fail loud on invalid JSON — refuse to
   touch, print the parse error, exit non-zero).
2. Look up `json.schemas` (create if missing as `[]`).
3. Look for an entry whose `fileMatch` contains `.haex-hive.json`.
   - If present with the same `url` → no action.
   - If present with a different `url` → offer a diff to update.
   - If absent → append the entry.
4. Serialize with `indent=2`, LF newlines, trailing newline.

**Rationale**: Operators frequently have workspace settings for
other purposes (editor rulers, format-on-save). Overwriting them
would be a Principle-VI review-gate violation in spirit even if
YIN-gated. Idempotency requires that a repeat run detect the entry
and skip it.

**Rejected**:

- **Whole-file overwrite**: destroys unrelated operator settings.
- **JSON5 / comments**: `.vscode/settings.json` may contain
  comments in practice; the stdlib `json` module does not parse
  them. Decision: fail loud on the parse and instruct the operator
  to strip comments manually (rare in practice; documented in
  `docs/haex-init.md`).

### Decision 6 — JetBrains `.idea/jsonSchemas.xml` merge shape

**Chosen**: haex-init writes into IntelliJ's `JsonSchemaMappingsProjectConfiguration`
XML element. Reference shape:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project version="4">
  <component name="JsonSchemaMappingsProjectConfiguration">
    <state>
      <map>
        <entry key="haex-hive">
          <value>
            <SchemaInfo>
              <option name="name" value="haex-hive" />
              <option name="relativePathToSchema" value=".specify/schemas/haex-hive.schema.json" />
              <option name="schemaVersion" value="JSON Schema version 7" />
              <option name="patterns">
                <list>
                  <Item>
                    <option name="path" value=".haex-hive.json" />
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
```

Merging rules:

- If the file does not exist: create it with the exact shape above.
- If the file exists: parse with `xml.etree.ElementTree` (stdlib),
  ensure the `JsonSchemaMappingsProjectConfiguration` component is
  present, then look up an entry keyed `haex-hive`.
  - Present with same `relativePathToSchema` → no action.
  - Present with different path → offer a diff to update.
  - Absent → add the entry.
- Serialize with an XML declaration and 2-space indent.

**Rationale**: IntelliJ family reads only `.idea/jsonSchemas.xml`
for JSON-Schema mappings. `xml.etree.ElementTree` in the stdlib
handles the structural manipulation without dependencies. The key
name `haex-hive` is a stable identifier operators can search for.

**Rejected**:

- **Direct string templating without XML parsing**: fragile against
  operators who have added other entries.
- **Write a fresh file even when others exist**: overwrites
  unrelated JetBrains mappings, unacceptable.

### Decision 7 — Interactive TTY detection + non-TTY behavior

**Chosen**: `haex-init` inspects `sys.stdin.isatty()` at startup.

- TTY → normal interactive flow with prompts.
- Non-TTY without `--yes` → refuse to run; print
  `haex-init: refusing to run non-interactively without --yes` on
  stderr and exit 2.
- Non-TTY with `--yes` → run in fully auto-confirming mode; assumes
  the operator has verified everything upstream.

**Rationale**: Interactive prompts on a stdin without a TTY are a
recipe for silent misbehavior (accepting defaults nobody consented
to). Refusing to run is safer than defaulting to `Y`.

**Rejected**:

- **Default to No on every prompt when non-interactive**: makes
  every non-TTY invocation a no-op; masks bugs in scripts.
- **Default to Yes**: catastrophic on user-global config files.

### Decision 8 — `--pin-constitution` HEAD SHA source

**Chosen**: Read `git rev-parse HEAD` inside the project's git
working directory (not a captured value from earlier in the run).
Refuse cleanly if:

- Not inside a git working tree → print
  `haex-init --pin-constitution: not inside a git working tree`
  and exit 2.
- HEAD points at nothing (empty repo) → print
  `haex-init --pin-constitution: repository has no commits yet`
  and exit 2.
- `.specify/memory/constitution.md` does not exist at that SHA →
  print
  `haex-init --pin-constitution: .specify/memory/constitution.md
  is not tracked at HEAD (commit it first)` and exit 2.

**Rationale**: The pin-constitution step exists precisely to close
the gap between "constitution written on disk" and "constitution
committed". Reading HEAD live guarantees the SHA points at a real
commit that actually contains the constitution content. Any other
source (an argument, an environment variable) invites operators to
pin at a stale or fictional SHA.

**Rejected**:

- **`--sha` argument**: bypasses the safety of "read what git
  actually thinks HEAD is".
- **Reflog-based recovery**: over-engineered for a fresh init flow.

### Decision 9 — Where the canonical session-instructions live

**Chosen**: Source-of-truth text file at
`.specify/templates/haex-hive-session-instructions.md`. The
`haex-init` script embeds an exact byte-for-byte copy of that
file's contents as a Python string constant
`CANONICAL_SESSION_INSTRUCTIONS`, together with an
`INSTRUCTIONS_VERSION` semver string and an `INSTRUCTIONS_SHA256`
hex constant. A sync test in `tests/haex-init/test-embedded-content-sync.sh`
asserts:

1. `SHA-256(CANONICAL_SESSION_INSTRUCTIONS) == INSTRUCTIONS_SHA256`.
2. `SHA-256(read_file(.specify/templates/haex-hive-session-instructions.md))
   == INSTRUCTIONS_SHA256`.
3. The marker block written by the tool actually stamps
   `v=<INSTRUCTIONS_VERSION>` in the begin line.

This is the mechanical enforcement for FR-033: a content change
without matching version+SHA constant updates fails CI.

**Rationale**: Two positive assertions and one wiring check is the
minimum sufficient to catch every failure mode:

- Forgetting to bump the version constant → tests still pass but
  block appears with wrong version → covered by assertion 3.
- Changing the embedded string but not the template file → covered
  by assertion 2 (template hash mismatch).
- Changing the template but not the embedded string → same
  assertion 2 catches it (embedded hash mismatch).

**Rejected**:

- **Only version, no SHA**: allows silent content edits.
- **Only SHA, no version**: gives operators no human-readable
  version marker on the block.
- **Fetch template at runtime from GitHub**: requires haex-hive to
  have a public remote (Spec 006), and defeats the "single-file
  download and run" adoption story.

### Decision 10 — Scaffolding commit message strings

**Chosen** (English, no LLM references, present-tense imperative
matching the repo's existing style):

- Self-ref scaffolding commit: `haex-init: initialize haex-hive scaffolding`
- Self-ref pin-constitution commit: `haex-init: pin constitution to HEAD`
- External-ref scaffolding commit: `haex-init: initialize haex-hive with external constitution`
- Optional `git init` (when the project is not yet a git repo): tool
  invokes `git init` but does NOT commit anything by itself; the
  scaffolding commit above is the first commit either way.

**Rationale**: Matches the imperative style visible in recent
commits (`implement: …`, `pin: …`, `spec: …`). Prefixing with the
tool name `haex-init:` makes the origin of the commit unambiguous
for future operators reading `git log`.

**Rejected**:

- **Longer sentences**: no gain, harder to scan in `git log --oneline`.
- **Emoji prefixes**: violates the "no emoji unless requested"
  house rule; also non-portable.

### Decision 11 — Empty-project vs already-populated project

**Chosen**: `haex-init` refuses to touch any file it did not intend
to create. Specifically:

- `.haex-hive.json` present but schema-invalid → refuse, per
  spec edge case; print the schema violation and exit 2.
- `.haex-hive.json` present and valid → proceed in idempotent
  mode; treat as re-run.
- `.vscode/settings.json` present → merge per Decision 5.
- `.gitignore` present → append missing haex-hive patterns only
  (dedupe against existing lines).
- `.specify/schemas/haex-hive.schema.json` present with different
  content → offer a diff-preview overwrite (schema is authoritative
  from the tool's embedded copy).

**Rationale**: A new operator running haex-init inside an existing
project directory is the target for external-ref mode (joining a
family). We must not clobber their work.

**Rejected**:

- **Refuse entirely if any target file exists**: makes the tool
  unusable in exactly the scenario external-ref mode is designed
  for.
- **Silently overwrite everything**: violates Principle VI.

## Best Practices Consulted

- **`argparse` for CLI**: single top-level parser + subparser for
  `--pin-constitution`; matches `spec-resolve`.
- **`difflib.unified_diff` for previews**: reference implementation
  in every Python stdlib since 2.4; no third-party dep needed.
- **`xml.etree.ElementTree` for XML**: adequate for the shape of
  `.idea/jsonSchemas.xml`. Handles namespaces and attribute
  ordering.
- **`shutil.which` for exe detection**: cross-platform equivalent
  of `command -v`, honors `$PATHEXT` on Windows if we ever ship
  that platform.
- **`subprocess.run(check=True)` for all git calls**: raises on
  non-zero exit; caller decides how to surface the error. No
  `shell=True`.
- **Atomic writes**: `os.replace(tmp_path, target_path)` on all
  writes to prevent half-written files if the tool is killed
  mid-write. Especially important for user-global configs.

## Unknowns Resolved

Every "NEEDS CLARIFICATION" the Technical Context could have raised
has an answer above:

- Language/Version: Python 3.10+ stdlib (matches Spec 004).
- Testing: shell-driven with sandbox (Decision 7 covers isolation).
- Marker block detection: Decision 1.
- Detection heuristics: Decision 2.
- External-ref cache location: Decision 3.
- Diff format: Decision 4.
- VSCode merge shape: Decision 5.
- JetBrains merge shape: Decision 6.
- Non-TTY behavior: Decision 7.
- Pin-constitution SHA source: Decision 8.
- Canonical instructions storage + sync: Decision 9.
- Commit message wording: Decision 10.
- Populated-project handling: Decision 11.

No open questions carry forward into Phase 1.
