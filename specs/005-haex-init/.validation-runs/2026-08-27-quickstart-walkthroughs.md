# Quickstart Walkthrough Validation — 2026-08-27

**Feature**: [../spec.md](../spec.md)
**Quickstart**: [../quickstart.md](../quickstart.md)
**Date**: 2026-08-27

## Purpose

Capture the actual outputs of the six quickstart walkthroughs against
the shipped tool, in a fresh sandbox. This is the T053 evidence that
SC-001a/SC-001b/SC-001c/SC-002/SC-003/SC-005 pass end-to-end (SC-001c
tested against the fixture remote — the real-remote variant lives in
`.validation-runs/haex-init-real-remote.md`).

## Walkthrough 1 — Self-ref mode (SC-001a + SC-001b)

Exercised mechanically by `tests/haex-init/test-fresh-operator.sh`
(sub-case A: full `--yes` flow) and `test-self-ref.sh` (self-ref
assertions) and `test-pin-constitution.sh` (SC-001b). All three tests
pass in `tests/haex-init/run-all.sh`.

Key evidence:

- `~/.haex-hive/haex-hive.md` created with SHA matching the tool's
  `INSTRUCTIONS_SHA256` constant.
- `~/.haex-hive/VERSION` contains `1.0`.
- `~/.claude/CLAUDE.md` carries a marker block stamped `v=1.0`.
- `.haex-hive.json` schema-valid with `harness_sources: []`.
- `.specify/schemas/haex-hive.schema.json` byte-identical to the
  embedded schema.
- `.vscode/settings.json` carries the `json.schemas` mapping entry.
- One scaffolding commit lands.

Following `/speckit-constitution` + `haex-init --pin-constitution`:

- `.haex-hive.json.harness_sources[0]` carries `role: "constitution",
  repository: "self", revision: <HEAD SHA>, path:
  ".specify/memory/constitution.md"`.
- One follow-up commit with the pinned message.
- Second `--pin-constitution` invocation refuses with exit 2
  (idempotency per FR-019).

## Walkthrough 2 — External-ref mode (SC-001c + US2)

Exercised by `tests/haex-init/test-external-ref.sh` — verification
happy path uses the built-in `family-spec-repo.git` fixture (`file://`
URL). Scheme-rejection cases confirmed for `file://`, `git://`,
`http://`, and bare-path inputs. Unreachable-SHA case produces git's
actual `upload-pack: not our ref` message and does not write
`.haex-hive.json`.

## Walkthrough 3 — Idempotent re-run (SC-003)

Exercised by `test-idempotent-rerun.sh`. Second `haex-init --yes`
invocation prints `Everything in order. No actions needed.` and
leaves both the project directory and `$HOME` byte-identical
(SHA-256 tree checksums equal before/after).

## Walkthrough 4 — Version-aware upgrade (US3 acceptance 4)

Exercised by `test-version-upgrade.sh`. A scratch copy of the tool
with `INSTRUCTIONS_VERSION = "1.1"` and a regenerated
`INSTRUCTIONS_SHA256` replaces the `v=1.0` marker block; the diff
preview surfaces the change; content outside the marker block is
byte-identical after replacement (SC-002 invariant proven by the
excise-and-compare assertion).

## Walkthrough 5 — Dry-run diagnostic (SC-005)

Exercised by `test-dry-run.sh`. Two sub-cases:

- Up-to-date project: `--dry-run` prints `Everything in order.`, exit
  0, filesystem checksums (project + home) equal before/after.
- Missing `.gitignore`: `--dry-run` reports the pending action,
  exit 1, filesystem checksums equal before/after.

## Walkthrough 6 — Non-TTY safety (Decision 7)

Verified informally by inspecting the `_resolve_home` + non-TTY guard
at the top of `run_init`. Automated coverage is implicit — every test
in the suite invokes the tool through a non-TTY stdin and passes
`--yes`, which is the "run in fully auto-confirming mode" branch of
Decision 7. The negative case (non-TTY without `--yes`) exits 2, per
the guard in `haex-init`:

```
if not sys.stdin.isatty() and not args.yes:
    print("haex-init: refusing to run non-interactively without --yes",
          file=sys.stderr)
    return EXIT_REFUSED
```

## Summary

SC-001a: PASS (via T030 sub-case A + T031)
SC-001b: PASS (via T032)
SC-001c: PASS (via T038 fixture-repo happy path)
SC-002: PASS (via T049 sub-cases A/B/C)
SC-003: PASS (via T044)
SC-005: PASS (via T047)
SC-006: PASS (every test runs in a sandbox HOME; developer's real
        `~/.claude/`, `~/.codex/`, `~/.gemini/`, `~/.haex-hive/`
        untouched).
SC-007: PASS (via T017 — 3-way byte-identity check).
