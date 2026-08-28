# Contract: Marker-Wrapped Reference Block

**Feature**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)
**Date**: 2026-08-27

## Purpose

Defines the exact byte-shape of the block `haex-init` writes into an
operator's per-tool user-global config file, and the rules governing
detection, replacement, and idempotency.

## Canonical Block Content

```
<!-- haex-hive-block:begin v=<INSTRUCTIONS_VERSION> -->
## haex-hive

At session start, and in any repository containing `.haex-hive.json`
at its root, read `~/.haex-hive/haex-hive.md` and follow the
instructions there.
<!-- haex-hive-block:end -->
```

**Byte-level rules**:

- The begin and end marker lines are ASCII exactly as shown, with a
  single trailing LF.
- `<INSTRUCTIONS_VERSION>` is substituted from the tool's
  `INSTRUCTIONS_VERSION` constant (a semver like `1.0`, `1.1`).
- The block body is exactly the three lines shown between begin and
  end (a Markdown H2, one blank line, one paragraph), each with a
  trailing LF.
- The block is prefixed by exactly one LF (i.e. blank line before
  the begin marker) when appended to a file that does not already
  end with a blank line. When replacing an existing block, the
  surrounding whitespace of the original block's boundaries is
  preserved byte-for-byte outside the block.

## Detection Regex (Decision 1 in research)

```python
BEGIN_RE = re.compile(r'^<!--\s*haex-hive-block:begin\s+v=([^\s>]+)\s*-->$')
END_RE   = re.compile(r'^<!--\s*haex-hive-block:end\s*-->$')
```

Applied line-by-line to the file's contents. The scanner splits with
`str.splitlines(keepends=True)` (so every physical line ending is
preserved for byte-accurate range calculations) and strips only the
trailing `\r?\n` from each line before matching. This means CRLF and
LF files are both recognised without the regex needing to describe
its own transport. Case-sensitive. UTF-8 assumed. Regression fixtures
MUST cover both LF-only and CRLF files.

## Presence States

| State | Condition |
|-------|-----------|
| `ABSENT` | No line matches `BEGIN_RE` AND no line matches `END_RE`. |
| `PRESENT_MATCHING_VERSION` | Exactly one `BEGIN_RE` match at line `b` AND exactly one `END_RE` match at line `e` AND `b < e` AND the captured version equals `INSTRUCTIONS_VERSION`. |
| `PRESENT_MISMATCHED_VERSION` | Same shape as `PRESENT_MATCHING_VERSION` but captured version differs from `INSTRUCTIONS_VERSION`. |
| `MALFORMED` | Any other combination: begin without end, end without begin, duplicate begins, duplicate ends, or begin appearing after end. |

## Actions Per State (Decision 1 + FR-009 + FR-010)

| From state | Action | Requires confirmation |
|------------|--------|-----------------------|
| `ABSENT` | `APPEND_BLOCK` at end of file (add one leading LF if file does not already end with blank line). | Yes (Y/N). |
| `PRESENT_MATCHING_VERSION` | No action (idempotency). | No prompt. |
| `PRESENT_MISMATCHED_VERSION` | `REPLACE_BLOCK` (byte-range from line `b` to line `e` inclusive, together with the newline after line `e`). | Yes (Y/N with unified-diff preview). |
| `MALFORMED` | Refuse. Print the exact inconsistency (e.g. "begin marker at line 42 has no matching end marker") to stderr and exit 2. | N/A. |

## Byte-Safety Invariants (SC-002)

For any file `F` and its post-action counterpart `F'`:

- If action was `APPEND_BLOCK`:
  - `F'[:len(F)]` may equal `F` (append at exact end) OR
    `F'[:len(F)+1]` may equal `F + "\n"` (append after a synthesized
    trailing LF) — but only the trailing LF is allowed to be
    synthesized.
- If action was `REPLACE_BLOCK`:
  - Content strictly before the begin-marker line's starting byte
    is byte-identical.
  - Content strictly after the end-marker line's terminating LF is
    byte-identical.
- If action was `REFUSED` (malformed): `F' == F`.

Formalized: SHA-256 of `F` with the marker block's byte range
excised MUST equal SHA-256 of `F'` with the same excision.

## Atomic Write Protocol

All writes to user-global config files follow:

1. Read `F` into memory.
2. Compute proposed `F'`.
3. Write `F'` to a sibling temp file (`F.tmp-haex-init-<pid>`).
4. `os.replace(F.tmp-haex-init-<pid>, F)` — atomic on POSIX.
5. On any exception in steps 3-4, unlink the temp file if it exists;
   never leave `F` half-written.

## Version Bump Semantics (FR-033 + Decision 9)

- `INSTRUCTIONS_VERSION` is human-readable semver (e.g. `1.0`,
  `1.1`).
- `INSTRUCTIONS_SHA256` is the exact hex-lowered SHA-256 of the
  embedded `CANONICAL_SESSION_INSTRUCTIONS` string.
- CI-enforced coupling (Decision 9): the sync test
  (`tests/haex-init/test-embedded-content-sync.sh`) asserts
  `SHA256(embedded_string) == INSTRUCTIONS_SHA256`,
  `SHA256(read_file(template.md)) == INSTRUCTIONS_SHA256`,
  `SHA256(EMBEDDED_SCHEMA_JSON) == SHA256(read_file(schema.json))`,
  AND a diff-aware assertion (d): if the current
  `CANONICAL_SESSION_INSTRUCTIONS` differs from its value at the
  merge-base against `origin/main` (falling back to `HEAD^`), then
  `INSTRUCTIONS_VERSION` MUST also differ. A tool-code-only change is
  therefore allowed to leave `INSTRUCTIONS_VERSION` intact; a canonical
  content change without a matching version bump fails the test with a
  named diagnostic.
- A content change without matching updates to both hash constants
  fails assertions (a)/(b) with a hash-mismatch diagnostic. A hash
  change without a matching version bump fails assertion (d) with a
  version-bump diagnostic. The test SKIPs (d) — but leaves the hash
  assertions in force — when no parent revision is available (fresh
  clone / shallow CI checkout without `origin/main`).

**Bump rules**:

- Tool-code-only change (bugfix, refactor, added test, added
  detection target that does NOT alter the block body) → do NOT
  bump `INSTRUCTIONS_VERSION`.
- Canonical instructions content change → MUST bump
  `INSTRUCTIONS_VERSION` (semver level: PATCH for wording, MINOR
  for a new instruction line, MAJOR for a breaking rewrite) AND
  regenerate `INSTRUCTIONS_SHA256`.

## Failure Modes and Their Contracts

| Symptom | Handler |
|---------|---------|
| File has begin but no end | Refuse (`MALFORMED`), print "begin marker at line N has no matching end marker in <path>". |
| File has end but no begin | Refuse, print "end marker at line N has no matching begin marker in <path>". |
| File has two begin markers | Refuse, print "multiple begin markers in <path> (lines M and N); haex-init managed only one block". |
| File is not writable | Refuse, print "cannot write <path>: permission denied". |
| File contains invalid UTF-8 | Refuse, print "cannot parse <path>: invalid UTF-8 at byte N". |
| File is a symlink pointing outside `$HOME` | Refuse per the path-allowlist invariant in data-model. |

All refusals set exit code `2` and leave the file byte-unchanged.
