# Phase 1 Data Model: `haex-init`

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Date**: 2026-08-27

`haex-init` is a CLI tool with no persistent data model of its own —
it mutates two on-disk regions (the operator's home and the project
directory) based on a live-computed state comparison. This document
formalizes the entities, invariants, and state transitions the tool
reasons about at runtime.

## Runtime Entities

### 1. `DetectedTool`

Represents a single LLM tool or IDE that the two-signal check
(Decision 2 in research) confirmed as installed.

| Field | Type | Notes |
|-------|------|-------|
| `name` | str | Canonical name (`"claude-code"`, `"codex"`, `"gemini"`, `"vscode"`, `"vscode-insiders"`, `"cursor"`, `"windsurf"`, `"jetbrains"`). |
| `category` | Literal[`"llm"`, `"ide"`] | Determines which prompt group the tool appears in. |
| `family` | str | `"vscode-family"`, `"jetbrains-family"`, or `"standalone"`. Drives IDE mapping-file selection. |
| `executable_path` | Path | Absolute path returned by `shutil.which`. |
| `config_dir` | Path | Absolute path to the user-config directory. |
| `user_global_config_file` | Path or None | For LLM tools: the file whose marker block gets patched (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`). None for IDEs. |
| `force_included` | bool | True if surfaced via `--include` rather than detection. |

**Invariant**: For LLM tools, `user_global_config_file`'s parent
directory equals `config_dir`.

### 2. `MarkerBlockState`

Represents the state of a haex-init marker block within one target
file (user-global config file per Decision 1 in research).

| Field | Type | Values |
|-------|------|--------|
| `target_file` | Path | Absolute path to the file. |
| `presence` | Enum | `ABSENT`, `PRESENT_MATCHING_VERSION`, `PRESENT_MISMATCHED_VERSION`, `MALFORMED`. |
| `existing_version` | str or None | The `v=…` value captured from the begin marker; None if `presence == ABSENT`. |
| `existing_line_range` | Tuple[int, int] or None | 1-indexed inclusive range of lines the current block spans; None if `presence == ABSENT`. |
| `existing_body_sha256` | str or None | SHA-256 of the inclusive block byte range; None if `presence == ABSENT`. |

State transitions triggered by `haex-init`:

```
ABSENT
  → (append block) → PRESENT_MATCHING_VERSION

PRESENT_MATCHING_VERSION
  → (no-op) → PRESENT_MATCHING_VERSION

PRESENT_MISMATCHED_VERSION
  → (Y confirm on diff-preview) → PRESENT_MATCHING_VERSION
  → (N declines diff-preview) → PRESENT_MISMATCHED_VERSION

MALFORMED
  → (refuse to touch, print error) → MALFORMED
```

**Invariant**: haex-init never writes a state that is not
`PRESENT_MATCHING_VERSION`. Malformed and mismatched states are only
observed on read, never produced.

### 3. `ProjectState`

Snapshot of the current project directory's haex-hive-relevant files
at the start of a `haex-init` run.

| Field | Type | Notes |
|-------|------|-------|
| `is_git_repo` | bool | `git rev-parse --git-dir` succeeded. |
| `has_haex_hive_json` | bool | `.haex-hive.json` exists at project root. |
| `haex_hive_json_valid` | bool or None | None if absent; True/False result of JSON Schema validation against the canonical schema. |
| `haex_hive_json_content` | dict or None | Parsed content if present and valid. May carry `managed_tools: [names]` recording the operator's persisted tool-selection intent — a prompt-free rerun (`--yes`) treats this list as the effective selection, so a tool the operator deliberately excluded on the initial run stays excluded even when it becomes newly detectable. An explicit `managed_tools: []` is schema-valid and means "select-none": on `--yes` rerun no tool is configured. Only an *absent* field is treated as legacy scaffolding (falls back to "all detected"). |
| `has_canonical_schema_file` | bool | `.specify/schemas/haex-hive.schema.json` present. |
| `canonical_schema_matches_embedded` | bool or None | SHA-256 comparison against tool's embedded constant. |
| `has_constitution_file` | bool | `.specify/memory/constitution.md` present. |
| `has_vscode_settings` | bool | `.vscode/settings.json` present. |
| `vscode_settings_wired` | bool or None | None if absent; True/False on whether the file already carries the haex-hive schema-mapping entry. |
| `has_idea_json_schemas` | bool | `.idea/jsonSchemas.xml` present. |
| `idea_json_schemas_wired` | bool or None | None if absent; True/False on entry presence. |
| `idea_is_gitignored` | bool | Result of `git check-ignore .idea/`. |
| `gitignore_missing_patterns` | list[str] | Subset of `["__pycache__/"]` not present in `.gitignore`. |

### 4. `UserGlobalState`

Snapshot of the operator's user-global haex-hive-relevant state.

| Field | Type | Notes |
|-------|------|-------|
| `haex_hive_dir_exists` | bool | `~/.haex-hive/` present. |
| `instructions_file_exists` | bool | `~/.haex-hive/haex-hive.md` present. |
| `instructions_matches_embedded` | bool or None | SHA-256 comparison. |
| `version_file_exists` | bool | `~/.haex-hive/VERSION` present. |
| `version_file_content` | str or None | Trimmed content. |
| `per_tool_marker_states` | dict[str, MarkerBlockState] | Keyed by `DetectedTool.name`. |

### 5. `Action`

A single unit of work the tool proposes to perform, subject to Y/N
confirmation.

| Field | Type | Notes |
|-------|------|-------|
| `kind` | Enum | `CREATE_FILE`, `MERGE_JSON`, `MERGE_XML`, `APPEND_BLOCK`, `REPLACE_BLOCK`, `APPEND_GITIGNORE_LINES`, `GIT_INIT`, `GIT_COMMIT`, `PATCH_HAEX_HIVE_JSON`. |
| `target` | Path | The file (or directory for `GIT_INIT`) the action operates on. |
| `preview` | str | Rendered text shown before the Y/N prompt (unified diff for content-touching actions; command-line preview for git actions). |
| `execute` | Callable[[], None] | The side-effect function; invoked only if operator confirms. |
| `label` | str | Human-readable one-liner for the final action-report. |

### 6. `ActionPlan`

Ordered list of `Action` instances produced by the planning pass.
Execution replays the list in order; user Y/N replies apply per-item.

**Invariant**: The plan is fully computed before any `Action.execute`
runs. `--dry-run` prints the plan and exits without executing.

## Cross-Entity Invariants

| Invariant | Enforced by |
|-----------|-------------|
| `haex-init` writes to a user-global config file only via a `MarkerBlockState` transition to `PRESENT_MATCHING_VERSION`. | FR-009 + Decision 1. |
| Every filesystem `Action.execute` (CREATE_FILE, MERGE_JSON, MERGE_XML, APPEND_BLOCK, REPLACE_BLOCK, APPEND_GITIGNORE_LINES, PATCH_HAEX_HIVE_JSON) in the plan corresponds to a state transition that moves either `UserGlobalState` or `ProjectState` strictly forward toward the tool's expected end state (idempotency). `GIT_INIT` and `GIT_COMMIT` are VCS-shaped actions and do not participate in this invariant — their idempotency is enforced by the git tool itself (no-op init on an existing repo; `git commit` skipped when the index is clean). | FR-026 + FR-027. |
| No `Action` in the plan writes to a path that resolves outside `$HOME`, the project directory, or `$XDG_CACHE_HOME/haex-init/verify/` (the external-ref verification cache; same path-safety and cleanup rules apply). | Path allow-list check at Action construction. |
| No `Action` in the plan writes to `.haex-hive.json` in a way that adds an entry the operator did not explicitly confirm (self-ref → empty array; external-ref → exactly the confirmed triple; `--pin-constitution` → exactly the `role: constitution` entry). | Constitution Principle V. |
| For every `PATCH_HAEX_HIVE_JSON` action, the resulting JSON MUST validate against the embedded schema before being written. | Fail-fast schema check inside `execute`. |

## `.haex-hive.json` Content Shapes (produced by this tool)

### Self-ref mode initial state

```json
{
  "haex_hive_version": "1",
  "identity": "<derived git remote URL or local:<name>>",
  "managed_tools": ["vscode"],
  "harness_sources": []
}
```

### Self-ref mode after `--pin-constitution`

```json
{
  "haex_hive_version": "1",
  "identity": "<derived git remote URL or local:<name>>",
  "harness_sources": [
    {
      "role": "constitution",
      "repository": "self",
      "revision": "<HEAD SHA at pin time>",
      "path": ".specify/memory/constitution.md"
    }
  ]
}
```

### External-ref mode

```json
{
  "haex_hive_version": "1",
  "identity": "<derived git remote URL or local:<name>>",
  "harness_sources": [
    {
      "role": "constitution",
      "repository": "https://…",
      "revision": "<validated SHA>",
      "path": ".specify/memory/constitution.md"
    }
  ]
}
```

The exact `identity` field default and prompting is inherited from
Spec 003. `haex-init` does not modify or re-derive `identity`; it uses
whatever the schema requires and prompts for missing pieces if any.

## State Machine: Whole-Tool Flow

```
                       ┌────────────────────────────┐
                       │        haex-init           │
                       │      (parse argv)          │
                       └───────────┬────────────────┘
                                   │
             ┌─────────────────────┼─────────────────────┐
             ▼                     ▼                     ▼
      --pin-constitution     --dry-run only         normal init
             │                     │                     │
             │                     │                     ▼
             │                     │           1. detect tools
             │                     │           2. prompt tool selection
             │                     │           3. prompt self-ref / external-ref
             │                     │           4. build ActionPlan
             │                     │                     │
             │                     │                     ▼
             │                     └──── plan-only ── print plan, exit
             │                                           │
             │                                           ▼
             │                             per Action: preview + Y/N
             │                                           │
             │                                           ▼
             │                             execute confirmed Actions
             │                                           │
             │                                           ▼
             ▼                                    action-report
   read HEAD SHA                                        │
   validate constitution.md exists                       ▼
   patch .haex-hive.json.harness_sources                exit 0
   offer commit
   action-report
   exit 0
```

## Testable Assertions Derived From This Model

The following assertions become concrete test predicates in
`tests/haex-init/`:

1. Given `UserGlobalState.per_tool_marker_states[t].presence ==
   PRESENT_MATCHING_VERSION` for every selected LLM tool AND
   `UserGlobalState.instructions_matches_embedded == True` AND
   `ProjectState` all-fields-satisfied → re-run produces an empty
   `ActionPlan` → exit 0 with idempotent message (SC-003).

2. Given any single field flips to a not-yet-satisfied state → the
   `ActionPlan` contains exactly one `Action` targeting the flipped
   region — no other actions, no cascading rewrites (FR-027).

3. Given `--dry-run` → `ActionPlan` is printed, `Action.execute` is
   NOT called for any action → filesystem checksum before ≡ after
   (SC-005).

4. Given external-ref mode with a URL that fails Decision-3
   verification → `Action.execute` for `PATCH_HAEX_HIVE_JSON` is NOT
   called → `.haex-hive.json` state before ≡ after (SC-004).

5. Given user-global config file with pre-existing content outside
   any marker block → after `APPEND_BLOCK` executes, SHA-256 of the
   file's byte range excluding the newly-appended marker block ≡
   SHA-256 of the pre-run file (SC-002).
