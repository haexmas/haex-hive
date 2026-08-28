---
description: "Tasks for Spec 005 — haex-init CLI-driven project initialization"
---

# Tasks: Spec 005 — `haex-init` CLI-Driven Project Initialization

**Input**: Design documents from `specs/005-haex-init/`
**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: this feature ships shell-driven tests (Python-stdlib tool
tested via bash + `set -e` + string assertions inside an isolation
sandbox). Tests are REQUIRED, not optional — FR-036, FR-037, FR-038,
FR-039 name them as deliverables and SC-002/003/005/006/007 are only
verifiable by test.

**Checkbox freshness is load-bearing.** When a task is completed, tick
its checkbox in the same commit as the task's output — or at the
latest in the next commit, before starting the next task. Handoff
queries ("what was just done, what remains, what is the next step?")
read this file's checkbox state as the primary state document; stale
ticks systematically drift the answers toward pending items that are
secretly done. See [ADR 0004](../../docs/adr/0004-eager-checkbox-update-rule.md).

**Organization**: tasks grouped by phase. Foundational work is heavy
because every user story consumes the same detection + block-
manipulation + action-framework surface. User Story phases (US1..US4)
then extend that surface with mode-specific behavior and their own
tests. Within each US phase, tests and implementation are interleaved
rather than strictly test-first — the shell harness is easier to
write against a partially-working tool than purely predictively.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: `[US1]`, `[US2]`, `[US3]`, `[US4]` mapping to the user stories in `spec.md`
- File paths in each task are repo-relative

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: directory scaffolding and test-harness stubs everything below depends on.

- [X] T001 Create the new source directories `.specify/templates/`, `tests/haex-init/`, `tests/haex-init/lib/`, `tests/haex-init/fixtures/`, and `.validation-runs/` (empty; contents land in later tasks)
- [X] T002 [P] Create `tests/haex-init/run-all.sh` as the test entrypoint (executable stub calling each `test-*.sh` in order, `set -euo pipefail`, aggregates pass/fail count) at `tests/haex-init/run-all.sh`
- [X] T003 [P] Add `tests/haex-init/fixtures/.tmp/` and any generated fixture output to `.gitignore` (the generated homes and repos are never committed) at `.gitignore`

**Checkpoint**: directories in place, test runner stub commits.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: canonical template + embedded constants, detection + block-manipulation + validator code, action framework, and the test-fixture/isolation harness that every user story consumes.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete — every story exercises the tool's detection + action-plan path.

### 2a — Canonical template + embedded constants

- [X] T004 Write the canonical session-instructions text at `.specify/templates/haex-hive-session-instructions.md` — byte-identical to the "Canonical Content" block in `specs/005-haex-init/contracts/haex-hive.md.template.md` (single trailing LF; no BOM); this file is the source-of-truth for the embedded string constant in the tool
- [X] T005 Create the tool skeleton at `.specify/scripts/haex-init` — `#!/usr/bin/env python3` shebang, executable bit set, `argparse` top-level with global options (`--dry-run`, `--yes`, `--include`, `--version`, `--help`) plus a `--pin-constitution` mutually-exclusive-with-`--dry-run` flag; main entry dispatches to `run_init()` or `run_pin_constitution()`; each handler is a stub raising `NotImplementedError` for now
- [X] T006 Embed the canonical instructions in `haex-init` as the `CANONICAL_SESSION_INSTRUCTIONS` Python string constant (byte-identical to T004's file), plus adjacent constants `INSTRUCTIONS_VERSION = "1.0"` and `INSTRUCTIONS_SHA256 = "<hex-lowered sha256 of CANONICAL_SESSION_INSTRUCTIONS>"` — same file `.specify/scripts/haex-init`
- [X] T007 Embed the canonical JSON Schema in `haex-init` as the `EMBEDDED_SCHEMA_JSON` string constant (byte-identical to `.specify/schemas/haex-hive.schema.json` from Spec 004); implement a targeted schema-mirror validator function `validate_haex_hive_config(cfg: dict) -> list[str]` matching the same constraints spec-resolve uses (Draft-07 subset checking `additionalProperties: false`, `role` enum, URL/SHA patterns, `allOf` shape constraints) — same file `.specify/scripts/haex-init`

### 2b — Detection + block-manipulation code

- [X] T008 Implement `MarkerBlockState` detection in `haex-init` per `contracts/marker-block.format.md`: two line-anchored regexes (`BEGIN_RE`, `END_RE`), single-pass line scan producing one of the four presence states (`ABSENT`, `PRESENT_MATCHING_VERSION`, `PRESENT_MISMATCHED_VERSION`, `MALFORMED`), captured version string, inclusive line range, and SHA-256 of the block's byte range — same file `.specify/scripts/haex-init`
- [X] T009 Implement two-signal `DetectedTool` detection in `haex-init` per research Decision 2: `shutil.which(<exe>)` AND `<config-dir>.is_dir()` for the full detection matrix (Claude Code, Codex, Gemini, VSCode, VSCode Insiders, Cursor, Windsurf, JetBrains-family); `--include NAME[,NAME...]` override sets `force_included=True` and skips the two-signal check; unknown `--include` names exit 2 with a named-set-of-valid-names error — same file `.specify/scripts/haex-init`
- [X] T010 Implement diff-preview + atomic-write helpers in `haex-init`: `render_unified_diff(old_bytes, new_bytes, label)` via `difflib.unified_diff` (plain text, no color) per research Decision 4, and `atomic_write(target: Path, content: bytes)` via `os.replace(tempfile → target)` per `contracts/marker-block.format.md`'s atomic-write protocol — same file `.specify/scripts/haex-init`
- [X] T011 Implement `ProjectState` snapshotter in `haex-init` per `data-model.md`: git-repo check, `.haex-hive.json` presence + schema-validate via T007, canonical schema file presence + hash comparison against `EMBEDDED_SCHEMA_JSON`, `.vscode/settings.json` presence + entry-wired check, `.idea/jsonSchemas.xml` presence + entry-wired check, `.idea/` gitignored check via `git check-ignore`, `.gitignore` missing-pattern set — same file `.specify/scripts/haex-init`
- [X] T012 Implement `UserGlobalState` snapshotter in `haex-init` per `data-model.md`: `~/.haex-hive/` presence, `haex-hive.md` presence + hash comparison against `CANONICAL_SESSION_INSTRUCTIONS`, `VERSION` presence + content, per-tool `MarkerBlockState` map keyed by selected `DetectedTool.name` — same file `.specify/scripts/haex-init`

### 2c — Action framework

- [X] T013 Implement `Action` + `ActionPlan` runner in `haex-init` per `data-model.md`: `Action(kind, target, preview, execute, label)` dataclass; `ActionPlan` collects instances in planning order; runner mode `execute` prints each `preview`, prompts `Apply this change? [Y/n]:` (unless `--yes`), calls `execute()` on Y; runner mode `dry_run` prints all `preview` blocks with `[?]` markers and skips `execute()`; runner ALWAYS renders the action-report at the end per `contracts/haex-init.cli.md`, even in `--yes` and `--dry-run`; exit codes per contract — same file `.specify/scripts/haex-init`
- [X] T014 Implement non-TTY detection + refusal in `haex-init` per research Decision 7: at startup, if `sys.stdin.isatty()` is False AND `--yes` was not passed, print `haex-init: refusing to run non-interactively without --yes` to stderr and exit 2; if `--yes` was passed, proceed with auto-confirmation — same file `.specify/scripts/haex-init`

### 2d — Test-fixture harness + sync test

- [X] T015 Write `tests/haex-init/lib/sandbox.sh` — provides `setup_sandbox()`/`teardown_sandbox()` functions that create a fresh `$SANDBOX_ROOT/{home,project,fake-bin}` tree, export `HOME=$SANDBOX_ROOT/home`, prepend `$SANDBOX_ROOT/fake-bin` to `$PATH`, and delete the sandbox on teardown; plus `install_fake_bin(NAME)` that drops a stub executable printing `<NAME>` and returning 0, and `create_fake_config_dir(TOOL)` that mkdir's the tool's expected config dir under `$HOME`; also `checksum_tree(path)` which returns a stable SHA-256 of the directory contents (sorted) for byte-safety tests — at `tests/haex-init/lib/sandbox.sh`
- [X] T016 Write `tests/haex-init/fixtures/build-fixtures.sh` — deterministic (`GIT_AUTHOR_DATE`, `GIT_COMMITTER_DATE`, `GIT_AUTHOR_NAME=fixture`, `GIT_AUTHOR_EMAIL=fixture@invalid` all fixed strings) builder that creates: (a) `tests/haex-init/fixtures/.tmp/family-spec-repo/` — a synthetic bare-shape repo with a committed `.specify/memory/constitution.md` at a stable SHA, addressable via `ssh://git@fixtures.invalid/family-spec-repo` alias for scheme-validation tests OR via `file://` for negative-scheme tests, and (b) `tests/haex-init/fixtures/.tmp/seeded-claude-md.txt` — a byte-known payload for the marker-safety test's pre-existing operator content; output the generated fixture SHAs to `tests/haex-init/fixtures/.tmp/fixtures.env` for downstream test scripts to source — at `tests/haex-init/fixtures/build-fixtures.sh`
- [X] T017 Write `tests/haex-init/test-embedded-content-sync.sh` — verifies the three static content-sync assertions: (a) `sha256(CANONICAL_SESSION_INSTRUCTIONS)` (extracted from the tool source) equals the tool's declared `INSTRUCTIONS_SHA256`; (b) `sha256(read_file(.specify/templates/haex-hive-session-instructions.md))` equals `INSTRUCTIONS_SHA256`; (c) `sha256(EMBEDDED_SCHEMA_JSON)` equals `sha256(read_file(.specify/schemas/haex-hive.schema.json))` — the schema-parity assertion required by FR-011. All three assertions are pure content-hash checks (no tool invocation), so this test runs first in `run-all.sh`. The runtime check that "the marker block written by the tool actually stamps `v=INSTRUCTIONS_VERSION`" (research Decision 9 assertion c) is covered separately by T030's assertion that `~/.claude/CLAUDE.md` contains a `v=<INSTRUCTIONS_VERSION>` marker block after the fresh-operator run — at `tests/haex-init/test-embedded-content-sync.sh`

**Checkpoint**: canonical template + embedded constants landed; detection, block manipulation, and validator code implemented; action framework wired; test harness (sandbox + fixtures + sync test) buildable. User-story work can begin.

---

## Phase 3: User Story 1 — Fresh operator adopts haex-hive (self-ref) (Priority: P1) 🎯 MVP

**Goal**: an operator with a fresh machine + fresh empty project runs `haex-init` once, answers the prompts choosing self-ref mode + at least one LLM + one IDE, and lands on a `spec-resolve status`-green project with empty `harness_sources` and correct scaffolding; a follow-up `haex-init --pin-constitution` adds and pins the constitution entry.

**Independent Test**: run [quickstart.md](./quickstart.md) Walkthrough 1 end-to-end from a fresh sandbox and verify SC-001a + SC-001b pass.

### Implementation for User Story 1

- [X] T018 [US1] Implement the tool-selection prompt in `haex-init` per `contracts/haex-init.cli.md` Prompt 1: numbered multi-select of `DetectedTool` instances (LLM group + IDE group, category-sorted); accept `all`, `none`, empty (= `all`), or comma-separated 1-indexed numbers; re-prompt up to 3 attempts on malformed input, then exit 2 — same file `.specify/scripts/haex-init`
- [X] T019 [US1] Implement the constitution-mode prompt in `haex-init` per `contracts/haex-init.cli.md` Prompt 2 (self-ref/external-ref choice); dispatch to `plan_self_ref()` or `plan_external_ref()`; the external-ref stub raises `NotImplementedError` for now (US2 fills it in T037) — same file `.specify/scripts/haex-init`
- [X] T020 [US1] Implement the `CREATE_FILE` Actions for `~/.haex-hive/haex-hive.md` (from `CANONICAL_SESSION_INSTRUCTIONS`) and `~/.haex-hive/VERSION` (single line: `<INSTRUCTIONS_VERSION>\n`); both use the atomic-write helper from T010 — same file `.specify/scripts/haex-init`
- [X] T021 [US1] Implement the `APPEND_BLOCK` and `REPLACE_BLOCK` Actions for per-tool user-global config files (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`) per `contracts/marker-block.format.md`: refuse on `MALFORMED` state per T048's semantics (a stub refusal is fine for now; T048 puts the friendly error message in place), append with one leading LF if file does not already end with a blank line, replace by byte-range for `PRESENT_MISMATCHED_VERSION` — same file `.specify/scripts/haex-init`
- [X] T022 [US1] Implement the `.haex-hive.json` writer for self-ref mode in `haex-init`: writes `{haex_hive_version: "1", identity: "<derived git remote URL or local:<name>>", managed_tools: [<sorted selected tool names>], harness_sources: []}` (schema constant + identity string + tool-selection intent, matching `EMBEDDED_SCHEMA_JSON`); runs `validate_haex_hive_config` from T007 before write; refuses via exit 2 if the operator's pre-existing `.haex-hive.json` fails the same validation. On a subsequent `--yes` rerun, `managed_tools` is the effective selection so deliberately excluded tools stay excluded — same file `.specify/scripts/haex-init`
- [X] T023 [US1] Implement the `.specify/schemas/haex-hive.schema.json` writer in `haex-init` (from `EMBEDDED_SCHEMA_JSON`); on file-exists-with-different-content, offer a diff-preview overwrite Action per `data-model.md` — same file `.specify/scripts/haex-init`
- [X] T024 [US1] Implement the `.vscode/settings.json` merger in `haex-init` per `contracts/ide-mapping.format.md`: file-missing → create with the canonical entry; file-exists → `json.load` (fail loud on parse error), locate/insert the `json.schemas` entry matching `.haex-hive.json`, re-serialize with `indent=2` + LF + trailing newline; VSCode-family selection (VSCode, VSCode Insiders, Cursor, Windsurf) collapses to one merge — same file `.specify/scripts/haex-init`
- [X] T025 [US1] Implement the `.idea/jsonSchemas.xml` merger in `haex-init` per `contracts/ide-mapping.format.md`: file-missing → create with the full canonical XML; file-exists → parse with `xml.etree.ElementTree`, ensure `JsonSchemaMappingsProjectConfiguration` component present, locate/insert the `haex-hive` entry, re-serialize with 2-space indent (`ET.indent`) + XML declaration + LF; run `git check-ignore .idea/` and warn per FR-013 if ignored — same file `.specify/scripts/haex-init`
- [X] T026 [US1] Implement the `.gitignore` appender in `haex-init`: read lines, dedup against existing content, append the missing haex-hive-relevant patterns (at minimum `__pycache__/`) with a leading blank line if the file did not already end with one; skip entirely if all patterns already present — same file `.specify/scripts/haex-init`
- [X] T027 [US1] Implement the `GIT_INIT` (optional prompt: `Initialize git repo? [Y/n]:`) and `GIT_COMMIT` Actions for self-ref mode in `haex-init`: run `git add <touched paths>` + `git commit -m "haex-init: initialize haex-hive scaffolding"`; on operator declining commit, print the exact manual command they can run — same file `.specify/scripts/haex-init`
- [X] T028 [US1] Implement the action-report renderer in `haex-init` per `contracts/haex-init.cli.md`: emit the "haex-init action report" header, sections (Operator-level, Project-level, Git, Next steps), `[x]`/`[-]`/`[?]` markers, and the final counts line; the "Next steps" section is emitted only for self-ref mode and lists the two follow-up actions per FR-018 — same file `.specify/scripts/haex-init`
- [X] T029 [US1] Implement `--pin-constitution` sub-mode in `haex-init` per research Decision 8: verify (a) inside a git working tree (exit 2 otherwise), (b) HEAD points at a commit (exit 2 if empty repo), (c) `.specify/memory/constitution.md` tracked at HEAD via `git ls-files --error-unmatch` at HEAD (exit 2 otherwise), (d) `.haex-hive.json.harness_sources` does not already contain a `role: "constitution"` entry (exit 2 if already pinned, with clear "already pinned" message per FR-019); then patch `.haex-hive.json.harness_sources` with the new entry, run `validate_haex_hive_config` from T007 on the patched result and refuse via exit 2 with a specific schema-violation message if it does not validate (same guard T022 applies to the initial write, ensuring `--pin-constitution` cannot leave `.haex-hive.json` schema-invalid), then offer `GIT_COMMIT` action with message `haex-init: pin constitution to HEAD` — same file `.specify/scripts/haex-init`

### Tests for User Story 1

- [X] T030 [P] [US1] Write `tests/haex-init/test-fresh-operator.sh` covering three sub-cases in one file: **(A) select-all happy path** — sourced `sandbox.sh` + built fixtures, install fake `claude` + fake `code` bins, create fake `~/.claude/` + `~/.config/Code/` dirs, `cd` into a fresh project, run `haex-init --yes` end-to-end; assert exit 0, `~/.haex-hive/haex-hive.md` exists with SHA matching `CANONICAL_SESSION_INSTRUCTIONS`, `~/.haex-hive/VERSION` contains `1.0`, `~/.claude/CLAUDE.md` contains a `v=1.0` marker block, `.haex-hive.json` schema-valid with `harness_sources: []`, `.specify/schemas/haex-hive.schema.json` byte-matches `EMBEDDED_SCHEMA_JSON`, `.vscode/settings.json` contains the `json.schemas` entry, one scaffolding commit made, action-report contains all expected `[x]` lines → SC-001a. **(B) partial selection — IDE only** — same fixture setup (both `claude` and `code` detected); drive the tool with a scripted stdin sequence that answers the tool-selection prompt with only the IDE's number and answers Y to every remaining Y/N; assert exit 0 AND `~/.claude/CLAUDE.md` is byte-identical before/after (SHA-256 comparison — no marker block appended) AND `.vscode/settings.json` did get the mapping entry AND the action-report lists the LLM as skipped → US1 acceptance scenario 3. **(C) declined-prompt propagation** — same fixture setup; script stdin to answer N to the FIRST Y/N (the operator-level `~/.haex-hive/haex-hive.md` create prompt) and Y to every subsequent independent Y/N; assert exit 0, assert `~/.haex-hive/haex-hive.md` was NOT created (that action skipped), assert subsequent independent project-level actions (`.haex-hive.json`, `.vscode/settings.json`, etc.) DID execute, assert the action-report's first entry is `[-]` and the subsequent entries are `[x]`, assert the final counts line reads `N applied, 1 skipped` → US1 acceptance scenario 4 — at `tests/haex-init/test-fresh-operator.sh`
- [X] T031 [P] [US1] Write `tests/haex-init/test-self-ref.sh` — targeted self-ref-mode assertions on the same sandbox setup: assert `.specify/memory/constitution.md` is NOT created (self-ref no-stub per Q2 clarification), assert exactly one scaffolding commit exists (no two-commit dance), assert stdout contains the next-step guidance phrasing from FR-018 (mentions `/speckit-constitution` and `haex-init --pin-constitution`) — at `tests/haex-init/test-self-ref.sh`
- [X] T032 [P] [US1] Write `tests/haex-init/test-pin-constitution.sh` — SC-001b: run the fresh-operator sequence, seed `.specify/memory/constitution.md` with placeholder content and commit it, run `haex-init --pin-constitution --yes`, assert `.haex-hive.json.harness_sources[0]` equals `{role: "constitution", repository: "self", revision: "<HEAD-SHA>", path: ".specify/memory/constitution.md"}`, assert one follow-up commit made with message `haex-init: pin constitution to HEAD`, assert a second `--pin-constitution` invocation refuses cleanly per FR-019 idempotency — at `tests/haex-init/test-pin-constitution.sh`

**Checkpoint**: MVP works. Fresh-operator can scaffold and pin a self-ref constitution. Everything downstream layers on top.

---

## Phase 4: User Story 2 — Wiring into a multi-repo family (external-ref) (Priority: P1)

**Goal**: `haex-init` in external-ref mode accepts a URL + SHA + path, verifies the reference resolves against the actual remote via a scratch cache pre-write, then writes `.haex-hive.json` with the external triple as the sole `harness_sources` entry.

**Independent Test**: run [quickstart.md](./quickstart.md) Walkthrough 2 against the synthetic bare-repo fixture from T016 and verify SC-001c + SC-004.

### Implementation for User Story 2

- [X] T033 [US2] Implement external-ref URL scheme validation in `haex-init` per FR-021: accept `^https://`, `^ssh://`, SCP-style `^[^/@:\s]+@[^/@:\s]+:.+$` (reuse the same set spec-resolve enforces so both tools agree); reject `file://`, `git://`, `http://`, and bare paths pre-network with actionable scheme-specific messages — same file `.specify/scripts/haex-init`
- [X] T034 [US2] Implement SHA input validation (`^[0-9a-f]{7,40}$`, lowercase-normalize) in `haex-init` per FR-022, and the optional `git ls-remote <url> HEAD` assist prompt per FR-023 offering the returned SHA as the default answer — same file `.specify/scripts/haex-init`
- [X] T035 [US2] Implement the scratch cache setup + pre-write git fetch verification in `haex-init` per research Decision 3: cache path `$XDG_CACHE_HOME/haex-init/verify/<sha256(url)[:16]>/` (default `~/.cache/haex-init/verify/…`); init a bare-shape objects directory on first use; `git fetch --no-tags --depth=1 <url> <sha>`; then `git cat-file -e <sha>:<path>` and `git cat-file -s <sha>:<path>` for reachability + non-empty checks per FR-024 — same file `.specify/scripts/haex-init`
- [X] T036 [US2] Implement the external-ref failure path in `haex-init` per FR-025: on any verification failure, surface `subprocess.CalledProcessError.stderr` verbatim, offer the operator to correct URL/SHA/path within the same invocation (bounded to 3 retries per field to prevent runaway); guarantee no partial `.haex-hive.json` written on failure (no `Action.execute` runs before verification succeeds) — same file `.specify/scripts/haex-init`
- [X] T037 [US2] Implement the `.haex-hive.json` writer for external-ref mode in `haex-init`: writes `{haex_hive_version, identity, harness_sources: [{role: "constitution", repository: <url>, revision: <sha>, path: <path>}]}`; schema-validate via T007 before write; offer scaffolding commit action with message `haex-init: initialize haex-hive with external constitution`; unblock the `plan_external_ref()` stub from T019 — same file `.specify/scripts/haex-init`

### Tests for User Story 2

- [X] T038 [P] [US2] Write `tests/haex-init/test-external-ref.sh` — happy path: sandbox + `build-fixtures.sh`-produced synthetic bare repo, run `haex-init --yes` in external-ref mode with the fixture's URL alias + real SHA + `.specify/memory/constitution.md` path, assert exit 0 and `.haex-hive.json.harness_sources[0]` matches the input triple, assert `spec-resolve status` prints `1 ref, 1 cached`; scheme-rejection cases: for each of `file:///tmp/foo`, `git://example.com/x`, `http://example.com/x`, `just-a-path`, run `haex-init --yes` with that URL, assert exit 3 and stderr names the scheme; unreachable-SHA case: valid URL + valid syntactic SHA that does not exist at the remote, assert exit 3 with git's actual error surfaced AND `.haex-hive.json` is not created (SHA-256 of project dir before ≡ after) → SC-001c + SC-004 — at `tests/haex-init/test-external-ref.sh`

**Checkpoint**: external-ref mode lands. Family-repo pattern is fully working.

---

## Phase 5: User Story 3 — Idempotent re-run + version-aware upgrade (Priority: P2)

**Goal**: `haex-init` re-runs are safe and cheap; idempotent when up-to-date, targeted when partial-state, version-aware on marker-block drift; `--dry-run` and `--yes` behave per contract.

**Independent Test**: run [quickstart.md](./quickstart.md) Walkthrough 3 (idempotent), Walkthrough 4 (version upgrade), and Walkthrough 5 (dry-run) and verify SC-003 + SC-005 + FR-027 + FR-028.

### Implementation for User Story 3

- [X] T039 [US3] Implement the up-to-date detection in `haex-init` per FR-026: at the end of the planning pass, if the `ActionPlan` is empty, print `Everything in order. No actions needed.` and exit 0 without emitting any Y/N prompt (this task extends T013's runner) — same file `.specify/scripts/haex-init`
- [X] T040 [US3] Implement partial-state detection in `haex-init` per FR-027: the planner iterates `ProjectState`/`UserGlobalState` and emits an `Action` per not-yet-satisfied field, skipping fields already up-to-date; assert (via test T045) that a re-run with a single deleted file re-creates only that file — same file `.specify/scripts/haex-init`
- [X] T041 [US3] Implement `--dry-run` mode in `haex-init` per FR-029: populate the plan the same way, print each Action's preview with `[?]` markers instead of `[x]`, skip every `execute()`, exit 0 if plan is empty else exit 1; assertion via test T047 that the filesystem SHA before ≡ after — same file `.specify/scripts/haex-init`
- [X] T042 [US3] Implement `--yes` mode in `haex-init` per FR-030: short-circuit every `confirm()` call to True; still render each diff-preview to stdout so operator can audit after-the-fact; combined with non-TTY, `--yes` allows script use per Decision 7 — same file `.specify/scripts/haex-init`
- [X] T043 [US3] Implement version-mismatch detection + `REPLACE_BLOCK` action in `haex-init` per FR-028: `MarkerBlockState.presence == PRESENT_MISMATCHED_VERSION` triggers a `REPLACE_BLOCK` action; the action's preview is the unified diff between old block and new block; Y replaces byte-range, N leaves file untouched — this task extends T021 with the version-drift branch — same file `.specify/scripts/haex-init`

### Tests for User Story 3

- [X] T044 [P] [US3] Write `tests/haex-init/test-idempotent-rerun.sh` — run `haex-init --yes` to completion, capture directory SHA via `checksum_tree`, re-run `haex-init --yes`, assert exit 0, assert stdout starts with `Everything in order. No actions needed.`, assert zero prompts written to stdin (verify by asserting no reads occurred if measurable, else assert the tool completed in under 1 second), assert directory SHA unchanged → SC-003 — at `tests/haex-init/test-idempotent-rerun.sh`
- [X] T045 [P] [US3] Write `tests/haex-init/test-partial-state.sh` — run `haex-init --yes` to completion, delete `.vscode/settings.json`, re-run `haex-init --yes`, assert exactly one file was created (`.vscode/settings.json` re-appeared with correct content), assert every other file's mtime/SHA unchanged → FR-027 — at `tests/haex-init/test-partial-state.sh`
- [X] T046 [P] [US3] Write `tests/haex-init/test-version-upgrade.sh` — run `haex-init --yes` to completion (writes `v=1.0` marker block), copy the tool into a scratch path and patch `INSTRUCTIONS_VERSION = "1.1"` + `CANONICAL_SESSION_INSTRUCTIONS = "…newer…"` + regenerated `INSTRUCTIONS_SHA256`, re-run the scratch tool with `--yes`, assert `~/.claude/CLAUDE.md` block now stamps `v=1.1`, assert everything outside the block byte-identical to pre-run (leverage the marker-safety helper from T049), assert stdout preview contained a unified diff → FR-028 — at `tests/haex-init/test-version-upgrade.sh`
- [X] T047 [P] [US3] Write `tests/haex-init/test-dry-run.sh` — case (a) up-to-date project: `checksum_tree(project) + checksum_tree(home)` before, run `haex-init --dry-run`, assert exit 0 and stdout contains `Everything in order`, assert checksums equal after; case (b) needs-work project (delete `.gitignore`): checksums before, run `haex-init --dry-run`, assert exit 1 and stdout contains `[?] append __pycache__/ to .gitignore` (or the equivalent action label), assert checksums equal after → SC-005 — at `tests/haex-init/test-dry-run.sh`

**Checkpoint**: idempotency + partial-state + version-aware upgrades + dry-run all pass.

---

## Phase 6: User Story 4 — Safety on operator's existing user-global config (Priority: P2)

**Goal**: `haex-init` never touches a single byte outside its marker-wrapped block; a MALFORMED marker state refuses the whole write; existing operator content is preserved byte-identical across every code path.

**Independent Test**: run [quickstart.md](./quickstart.md)-equivalent flow (see US4 acceptance scenarios) with a seeded fake `~/.claude/CLAUDE.md` payload and verify SC-002.

### Implementation for User Story 4

- [X] T048 [US4] Implement the MALFORMED refusal path in `haex-init` per FR-010 + `contracts/marker-block.format.md`: detect begin-without-end, end-without-begin, duplicate begins, duplicate ends, begin-after-end; for each case, produce a specific stderr message quoting the offending line numbers (e.g. `haex-init: begin marker at line 42 has no matching end marker in /path/to/CLAUDE.md`); exit 2; assert file byte-unchanged after refusal (i.e. no partial writes, no locks left behind) — extends T021 with the refusal branch — same file `.specify/scripts/haex-init`

### Tests for User Story 4

- [X] T049 [P] [US4] Write `tests/haex-init/test-marker-safety.sh` — seed a fake `~/.claude/CLAUDE.md` with a byte-known payload from `fixtures/.tmp/seeded-claude-md.txt` (T016); scenario A (no block): run `haex-init --yes`, compute `sha256(pre-run bytes) == sha256(post-run bytes excluding the newly-appended marker block)` → SC-002; scenario B (matching block): run again with the block in place, assert exit 0 and file byte-identical before/after; scenario C (mismatched-version block): run with a patched tool bumped to a later version, assert file post-run == pre-run OUTSIDE the marker range but marker range differs (block replaced); scenario D (MALFORMED — begin without end): assert exit 2, assert stderr names the specific inconsistency, assert file byte-identical before/after (SC-002-extended) — at `tests/haex-init/test-marker-safety.sh`

**Checkpoint**: user-global byte-safety mechanically guaranteed by test. Every path preserves operator content outside the marker range.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: operator-facing docs, validation-run captures, and the final run-all green.

- [X] T050 [P] Write `docs/haex-init.md` — operator-facing documentation covering: install (single-file download + `chmod +x`), command surface (all flags + `--pin-constitution` sub-mode), self-ref vs external-ref walkthroughs, manual editor setup for the non-auto-supported IDEs (Neovim + Emacs LSP snippets, Sublime schema mapping, Zed schema mapping, Helix), edge-case handling (`.idea/` gitignored, JSON5 comments, malformed marker block, non-TTY use), FAQ on `--fetch-latest` and `add-source` being Spec 006 territory — at `docs/haex-init.md`
- [X] T051 [P] Write `.validation-runs/haex-init-real-remote.md` — template documenting the manual smoke test against a real external remote (recommended: github.com/octocat/Hello-World or any small public repo): exact `haex-init` invocation, expected prompts, expected `.haex-hive.json` shape, expected `spec-resolve resolve --role constitution` output; do NOT include the actual result of running it yet (see T054) — at `.validation-runs/haex-init-real-remote.md`
- [X] T052 Wire every `test-*.sh` produced in Phases 2–6 into `tests/haex-init/run-all.sh` in the order (embedded-content-sync, fresh-operator, self-ref, pin-constitution, external-ref, idempotent-rerun, partial-state, version-upgrade, dry-run, marker-safety), with `set -euo pipefail`, pass/fail aggregation, and a final green banner; run the whole thing and assert every test passes — at `tests/haex-init/run-all.sh`
- [X] T053 [P] Run all six walkthroughs from `quickstart.md` against the actual tool in a fresh sandbox, capture the outputs in `specs/005-haex-init/.validation-runs/2026-08-27-quickstart-walkthroughs.md`, verify SC-001a + SC-001b + SC-001c + SC-002 + SC-003 + SC-005 pass in real invocations
- [X] T054 [P] Perform the manual real-remote smoke test per T051's template, capture the output in `.validation-runs/haex-init-real-remote.md` (extending the template with the actual invocation timestamp + result); this MUST NOT be added to `run-all.sh` (network dependency) per FR-039
- [X] T055 Final documentation pass: confirm `docs/haex-init.md` covers every FR (mechanical trace); update the "Non-Goals" section of `spec.md` if any deferred item was accidentally implemented (unlikely — this is a hygiene check); ensure the top-level README (if any) points at `docs/haex-init.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies; three tasks, T002/T003 parallel.
- **Phase 2 (Foundational)**: depends on Phase 1. Within Phase 2:
  - T004 (canonical template) is independent; can start immediately.
  - T005 (tool skeleton) is independent; can start immediately.
  - T006 (embedded constants) depends on T004 (needs the template bytes to compute SHA) and T005 (embeds into the skeleton).
  - T007 (schema constant + validator) depends on T005 (embeds into the skeleton); independent of T004/T006.
  - T008–T012 (detection + block + state code) depend on T005 (same file); T008/T009/T010/T011/T012 sequential on the same file.
  - T013 (action runner) depends on T005 + T010 (uses diff/atomic-write helpers); goes into the same file.
  - T014 (non-TTY refusal) depends on T005 + T013; same file.
  - T015 (sandbox.sh) is independent; can start alongside T004.
  - T016 (fixtures) depends on T015 (uses sandbox helpers).
  - T017 (sync test) depends on T006 + T007 + T015 (needs both the instructions + schema constants for the three content-hash assertions, and sandbox helpers for path derivation).
- **Phase 3 (US1)**: depends on Phase 2 checkpoint (needs the whole tool foundation + fixtures). Within US1:
  - T018–T029 mostly sequential on the same file (`.specify/scripts/haex-init`).
  - T030/T031/T032 are parallel among themselves (separate test files) but depend on T018–T029 being at least skeleton-complete.
- **Phase 4 (US2)**: depends on Phase 3 for the shared framework (T013 action runner, T017's sync test infrastructure). T033–T037 sequential on the same file; T038 test parallel among itself.
- **Phase 5 (US3)**: depends on Phase 3 (idempotency needs the ProjectState/UserGlobalState snapshotters + ActionPlan runner). T039–T043 sequential on the same file; T044–T047 tests parallel.
- **Phase 6 (US4)**: depends on Phase 2 (needs T008 MarkerBlockState detector) + T021 (existing APPEND_BLOCK code to extend with refusal branch). May run in parallel with Phase 4/5 in terms of file conflicts — but tests T049 depends on T048 landing.
- **Phase 7 (Polish)**: depends on Phases 3–6 all being complete. T050/T051 fully parallel (independent docs); T052 depends on all tests existing; T053/T054 depend on T052 green; T055 is the final hygiene pass.

### Within Each User Story

- Within US1: T018–T029 are sequential on `.specify/scripts/haex-init` (same file); T030–T032 are parallel among themselves (separate `test-*.sh` files) but each depends on T018–T029 being complete enough for their assertions.
- Within US2: T033 → T034 → T035 → T036 → T037 sequential (same file, shared external-ref code path); T038 depends on the chain.
- Within US3: T039 → T040 → T041 → T042 → T043 sequential (same file, all extending T013's runner and T008's detector); T044–T047 tests parallel and depend on their target FR's implementation task landing.
- Within US4: T048 is the sole implementation task; T049 depends on it.

### Parallel Opportunities

- Phase 1: T002 + T003.
- Phase 2: {T004, T015} in parallel; {T005 → T006 → T007 → T008–T012 → T013 → T014} sequential (same file); {T016, T017} parallel with each other once T006 + T015 are done.
- Phase 3: T030 + T031 + T032 parallel.
- Phase 4: T038 alone (single test).
- Phase 5: T044 + T045 + T046 + T047 parallel.
- Phase 6: T049 alone (single test).
- Phase 7: T050 + T051 parallel; T052 sequential (needs the tool green); T053 + T054 parallel; T055 final.
- Cross-phase: **US4 (Phase 6) can proceed in parallel with US3 (Phase 5)** — US4's T048 extends T021's marker refusal semantics but does not collide with US3's runner/detector changes. **US2 (Phase 4) can proceed in parallel with US3 + US4** once US1 lands.

---

## Implementation Strategy

### MVP scope

Phases 1 + 2 + 3 alone = MVP. If the operator ships nothing else, they have:

- The canonical instructions template landed in `.specify/templates/`.
- A working `haex-init` that scaffolds a self-ref project + patches
  one operator's user-global config file byte-safely.
- A working `haex-init --pin-constitution` that completes the self-ref
  flow after `/speckit-constitution`.
- Green shell tests for the fresh-operator + self-ref + pin-constitution
  paths.

That closes the load-bearing claim of "the first new operator can
adopt haex-hive in three minutes without hand-editing anything". US2
(external-ref), US3 (idempotency + version-upgrade), and US4 (marker
safety mechanical guarantee) harden it — necessary before calling
Spec 005 complete, but not blocking the "the mechanism works" verdict.

### Incremental delivery

1. Phases 1–3 → MVP works, commit, take stock. Verifiable: sandbox test-fresh-operator + test-self-ref + test-pin-constitution green; walkthrough 1 passes end-to-end.
2. Phase 4 (US2) → external-ref mode live. Family-repo pattern usable.
3. Phase 5 (US3) → idempotency + `--dry-run` + version-upgrade behavior.
4. Phase 6 (US4) → user-global byte-safety mechanically guaranteed by test.
5. Phase 7 (Polish) → operator docs + smoke test against real external remote + final green run of `tests/haex-init/run-all.sh`.
6. Merge feature branch to `main`. Advance design roadmap Phase 1 to "haex-init available for new-operator adoption".

### Solo strategy (this project's expected mode)

You are the only operator. Sequential execution phase by phase. The
`[P]` markers indicate where solo-serial can be re-ordered without
dependency risk — useful for interleaving doc-writing (T050/T051)
with test-writing (T030+, T044+) if you need a change of gears.

---

## Notes

- Every code change should trace to a specific FR in `spec.md`. If a
  task's diff doesn't map to at least one FR, either the task is out
  of scope or an FR is missing.
- Commits after each Phase are recommended so a failure in a later
  phase can be diagnosed against a known-good earlier state.
- Do not mark Phase 7 tasks complete until every earlier task's tests
  pass in T052's `run-all.sh` output.
- The `.specify/templates/haex-hive-session-instructions.md` created in
  T004 is the source-of-truth for the embedded string constant in T006;
  changing either without updating the other AND the SHA constant is
  caught by T017's sync test.
- Non-Goals from `spec.md` MUST remain out of scope through Phase 7;
  `--fetch-latest`, `add-source`, and multi-spec external-ref are Spec
  006 territory. If a task starts creeping toward one of these, split
  it into a separate Spec-006-scoped task instead.
