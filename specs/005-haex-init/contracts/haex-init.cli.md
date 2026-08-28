# CLI Contract: `haex-init`

**Feature**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)
**Date**: 2026-08-27

## Executable

- **Path**: `.specify/scripts/haex-init`
- **Shebang**: `#!/usr/bin/env python3`
- **Permissions**: `0755` in git; enforced by `chmod +x` in the
  scaffolding-commit step of the tool's own test run.

## Command Surface

```
haex-init [--dry-run] [--yes] [--include NAME[,NAME...]]
haex-init --pin-constitution [--yes]
haex-init --version
haex-init --help
```

### Global options

| Flag | Meaning |
|------|---------|
| `--dry-run` | Compute the ActionPlan, print it, exit 0 if empty or exit 1 if non-empty. Never write to any filesystem location. |
| `--yes` | Auto-confirm every Y/N prompt. Required when stdin is not a TTY (Decision 7). |
| `--include NAME[,NAME...]` | Force-include tools not surfaced by detection. Valid names: `claude-code`, `codex`, `gemini`, `vscode`, `vscode-insiders`, `cursor`, `windsurf`, `jetbrains`. Comma-separated. |
| `--version` | Print `haex-init v<INSTRUCTIONS_VERSION>` and exit 0. |
| `--help` | Print help text and exit 0. |

### Modes

- **Normal init** (`haex-init` with no subcommand): full detection +
  prompt + operator-level + project-level setup as described in the
  spec.
- **`--pin-constitution`**: run only the post-`/speckit-constitution`
  wiring step (Decision 8). Mutually exclusive with `--dry-run` on
  the same invocation.

## Exit Codes

| Code | When |
|------|------|
| `0` | Success (including "everything in order", including successful --dry-run of an up-to-date project). |
| `1` | Non-fatal disagreement: `--dry-run` found pending actions. |
| `2` | Refused to run (non-TTY without `--yes`; malformed marker block; `--pin-constitution` preconditions unmet; schema-invalid existing `.haex-hive.json`; `$HOME` unset or unwritable). |
| `3` | External-ref verification failed (URL/SHA/path). |
| `4` | Git subprocess failed unexpectedly (e.g. `git init` refused). |
| `5` | User declined a prompt AND declining leaves the project in a state the tool cannot express (reserved; never emitted in Phase 1). |

Every non-zero exit prints a one-line diagnostic to stderr naming
the reason.

## Interactive Prompt Contract

### Prompt 1 — Tool selection

Rendered as a numbered multi-select. Example (detected: `claude-code`
and `vscode`):

```
Detected tools:
  [1] claude-code   (LLM)
  [2] vscode        (IDE)

Which should haex-hive wire into? (comma-separated numbers, "all",
"none", or specific: e.g. "1,2"):
```

Accepted inputs (case-insensitive, whitespace-trimmed):

- Empty → `all`.
- `all` → every detected tool.
- `none` → skip both LLM and IDE wiring.
- Comma-separated 1-indexed numbers → those tools.
- Any invalid token → re-prompt with error, up to 3 attempts, then
  exit 2.

### Prompt 2 — Constitution mode

```
Constitution mode:
  [1] self-ref: this project owns its constitution (.specify/memory/constitution.md)
  [2] external-ref: this project references a constitution in another repo

Choose [1/2]:
```

### Prompt 3 (external-ref only) — URL / SHA / path

```
External repository URL: <input>
Fetch latest HEAD SHA from remote? [y/N]: <input>
SHA (40 lowercase hex): <input>
Path within repository [default: .specify/memory/constitution.md]: <input>
```

Each field is validated pre-network. Bad input re-prompts on the same
field.

### Prompt 4 — Per-action Y/N (repeated per Action)

Prefaced by a one-line label + a unified-diff preview + one final
line asking `Apply this change? [Y/n]:` (default `Y`). `--yes` auto-
answers `Y` to every occurrence.

### Prompt 5 (self-ref only, after project-level work) — Git commit

```
Commit scaffolding now? [Y/n]:
```

`Y` runs `git add <changed paths> && git commit -m "haex-init:
initialize haex-hive scaffolding"`. `N` leaves files on disk and
prints the manual commit command.

### Prompt 6 (external-ref only) — Git commit

```
Commit scaffolding + external constitution reference now? [Y/n]:
```

Analogous to Prompt 5. Commit message:
`haex-init: initialize haex-hive with external constitution`.

### Prompt 7 (`--pin-constitution` only) — Follow-up commit

```
Commit pinned constitution reference now? [Y/n]:
```

Commit message: `haex-init: pin constitution to HEAD`.

## Action-Report Contract

Every run — including `--dry-run` and `--yes` — prints a final
action-report to stdout with this exact structure:

```
haex-init action report
=======================

Operator-level:
  [x]  created ~/.haex-hive/haex-hive.md
  [x]  created ~/.haex-hive/VERSION (v=1.0)
  [x]  appended marker block v=1.0 to ~/.claude/CLAUDE.md
  [-]  skipped ~/.codex/AGENTS.md (declined)

Project-level:
  [x]  created .haex-hive.json (self-ref, harness_sources: [])
  [x]  created .specify/schemas/haex-hive.schema.json
  [x]  merged json.schemas entry into .vscode/settings.json
  [x]  appended __pycache__/ to .gitignore

Git:
  [x]  scaffolding commit ac5d1e (2 files)

Next steps:
  1. Run  /speckit-constitution  in your agent session to define
     the project's constitution.
  2. After committing the constitution, run:
        haex-init --pin-constitution
     to pin it in .haex-hive.json.

haex-init: 5 actions applied, 1 skipped
```

**Rules**:

- `[x]` prefix for executed; `[-]` for skipped; `[?]` for pending
  (only appears in `--dry-run` output).
- The report is ALWAYS printed even in `--yes` mode. No "quiet mode".
- The final line summarises counts.

## Idempotency Contract

- Same-input, same-state → `ActionPlan` is empty → prints
  `Everything in order. No actions needed.` → exit 0.
- Any prompt-level `N` cannot leave the project in a state that
  needs cleanup on the next re-run beyond what the operator
  declined.

## Detection Contract

- LLM: dual signal per Decision 2. Empty detection is a legitimate
  state (operator picks `none` if no LLM should be wired).
- IDE: dual signal per Decision 2. Same as LLM.
- `--include` sets `force_included=True` and skips detection for
  the named tool; if the tool has no config-dir at all,
  `haex-init` still writes the block into a newly-created
  `config_dir/<config_file>` — but the operator is warned that the
  tool was not detected.

## Non-Contract Behavior

The following are explicit non-behaviors — the tool MUST NOT do
these:

- Write to any absolute path outside `$HOME` or the project
  directory.
- Read the operator's ssh keys or git credentials.
- Modify the operator's git config (`git config --global`).
- Modify `PATH`, `SHELL`, or any shell rc file.
- Print any concealment instruction (Principle VIII).
- Emit output that a downstream agent could interpret as an
  instruction to hide anything from the operator.
- Fetch content from the network in `--dry-run`.
- Silently fall through to defaults when a prompt is malformed —
  every malformed input re-prompts or exits 2.
