# `haex-init` — Operator Documentation

`haex-init` is a single stdlib-only Python CLI that bootstraps a project
for haex-hive: it patches the operator's user-global config files
(byte-safely, inside a marker-wrapped block), writes the project-local
`.haex-hive.json` + schema mapping, and — optionally — pins a
constitution reference.

See [`specs/005-haex-init/spec.md`](../specs/005-haex-init/spec.md) for
the full spec, and
[`contracts/haex-init.cli.md`](../specs/005-haex-init/contracts/haex-init.cli.md)
for the mechanical CLI contract.

## Install

`haex-init` ships as a single executable Python file. For Phase 1
adoption, the operator clones the haex-hive repo and copies the file
(or runs it directly from the clone):

```
git clone https://<haex-hive-repo-url>.git
cp haex-hive/.specify/scripts/haex-init ~/bin/haex-init
chmod +x ~/bin/haex-init
```

A public-URL `curl` install (`--fetch-latest`) is Spec 006 territory
and not available yet.

**Requirements**: Python 3.10+, Git 2.30+, both on `$PATH`. Linux is
the validated target for Phase 1; macOS and WSL2 should work but are
not tested.

## Command surface

```
haex-init [--dry-run] [--yes] [--include NAME[,NAME...]]
haex-init --pin-constitution [--yes]
haex-init --version
haex-init --help
```

| Flag | Meaning |
|------|---------|
| `--dry-run` | Compute the ActionPlan, print it, exit 0 if empty or 1 if not. No writes. Mutually exclusive with `--pin-constitution`. |
| `--yes` | Auto-confirm every Y/N prompt. Required when stdin is not a TTY. |
| `--include NAME[,NAME...]` | Force-include tools not surfaced by detection. Valid names: `claude-code`, `codex`, `gemini`, `vscode`, `vscode-insiders`, `cursor`, `windsurf`, `jetbrains`. |
| `--pin-constitution` | Post-`/speckit-constitution` wiring: reads HEAD SHA, adds `role: constitution` to `harness_sources`, offers a follow-up commit. |
| `--version` | Print `haex-init v<INSTRUCTIONS_VERSION>`. |
| `--help` | Print help. |

Exit codes:

| Code | Meaning |
|------|---------|
| 0 | Success (including "everything in order" and successful dry-run of an up-to-date project). |
| 1 | Dry-run found pending actions. |
| 2 | Refused: non-TTY without `--yes`; malformed marker block; `--pin-constitution` preconditions unmet; schema-invalid existing `.haex-hive.json`; bad CLI. |
| 3 | External-ref verification failed. |
| 4 | Git subprocess failed unexpectedly. |

## Self-ref walkthrough

Fresh machine, fresh empty project, Claude Code + VSCode installed:

```
$ cd my-project
$ ../haex-init
Detected tools:
  [1] claude-code   (LLM)
  [2] vscode        (IDE)

Which should haex-hive wire into? [all]:
Constitution mode:
  [1] self-ref
  [2] external-ref
Choose [1/2] [1]: 1
… per-action Y/N prompts …

haex-init action report
=======================
Operator-level:
  [x]  created ~/.haex-hive/haex-hive.md
  [x]  created ~/.haex-hive/VERSION (v=1.0)
  [x]  appended marker block v=1.0 to ~/.claude/CLAUDE.md
Project-level:
  [x]  created .haex-hive.json (self-ref, harness_sources: [])
  [x]  created .specify/schemas/haex-hive.schema.json
  [x]  merged json.schemas entry into .vscode/settings.json (for vscode)
  [x]  appended __pycache__/ to .gitignore
Git:
  [x]  scaffolding commit (…)

Next steps:
  1. Run  /speckit-constitution  in your agent session.
  2. After committing the constitution, run:
       haex-init --pin-constitution
```

Then:

```
$ /speckit-constitution     # (in your agent session)
$ ../haex-init --pin-constitution
```

## External-ref walkthrough

A repo joining a family of sibling repos that share one constitution:

```
$ cd my-consumer-repo
$ ../haex-init
Constitution mode:
  [1] self-ref
  [2] external-ref
Choose [1/2] [1]: 2

External repository URL: ssh://git@example.com/team/specs.git
Fetch latest HEAD SHA from remote? [y/N]:
SHA (40 lowercase hex): 4c8e9a2f1b3d6e0a…
Path within repository [default: .specify/memory/constitution.md]:

Verifying reference…
  ✓ reference verified at 4c8e9a2f…:.specify/memory/constitution.md
… per-action Y/N prompts …
```

Rejected URL schemes: `file://`, `git://`, `http://`, bare paths.
These fail pre-network with a scheme-specific error message.

## Manual editor setup

`haex-init` writes IDE schema-mapping files only for VSCode-family and
JetBrains-family. For other editors, add the mapping manually:

### Neovim (with `nvim-lspconfig` + `jsonls`)

```lua
require('lspconfig').jsonls.setup({
  settings = {
    json = {
      schemas = {
        {
          fileMatch = { ".haex-hive.json" },
          url = "./.specify/schemas/haex-hive.schema.json",
        },
      },
    },
  },
})
```

### Emacs (`lsp-mode` + `lsp-json`)

Add to `init.el`:

```elisp
(with-eval-after-load 'lsp-json
  (setq lsp-json-schemas
        `[(:fileMatch [".haex-hive.json"]
           :url "./.specify/schemas/haex-hive.schema.json")]))
```

### Sublime Text (`LSP-json` package)

Add to Preferences → Package Settings → LSP-json → Settings:

```json
{
  "schemas": [
    {
      "fileMatch": [".haex-hive.json"],
      "url": "./.specify/schemas/haex-hive.schema.json"
    }
  ]
}
```

### Zed

Zed reads `.vscode/settings.json` natively for schema mappings; the
`haex-init`-produced file works as-is.

### Helix

Helix has no JSON schema mapping surface as of writing; the schema is
still available via any other editor pointed at
`.specify/schemas/haex-hive.schema.json`.

## Edge cases

- **`.idea/` is gitignored**: `haex-init` warns before writing the
  JetBrains mapping — the file will not travel with the project.
- **`.vscode/settings.json` contains JSON5 comments**: the stdlib
  `json` module cannot parse these. Strip comments and re-run.
- **Malformed marker block** in `~/.claude/CLAUDE.md` (begin without
  end, etc.): `haex-init` refuses to touch the file, prints the
  specific inconsistency, exits 2.
- **Non-TTY invocation without `--yes`**: refused. Pass `--yes` for
  scripted use (only when you have already reviewed everything).
- **Pre-existing schema-invalid `.haex-hive.json`**: `haex-init`
  refuses, prints the schema violations, exits 2. Fix the file and
  re-run.
- **Pre-existing operator content in `~/.claude/CLAUDE.md`**:
  preserved byte-for-byte outside the marker block boundaries.

## FAQ

- **What is `--fetch-latest`?** A future Spec 006 flag that would let
  `haex-init` update its embedded session-instructions from the
  haex-hive remote at runtime. Not available in Phase 1.
- **What is `add-source`?** A future Spec 006 sub-mode for adding
  permission-only `harness_sources` entries. In Phase 1, hand-edit
  `.haex-hive.json` or re-run `haex-init` after Spec 006 lands.
- **Can I run `haex-init` again after `/speckit-constitution`?** Yes,
  and you should — `haex-init --pin-constitution` is exactly the
  follow-up step.
- **Does `haex-init` modify my git config or shell rc?** No. It never
  touches `~/.gitconfig`, `~/.bashrc`, `~/.zshrc`, or any other
  operator dotfile outside the ones documented in the action-report.

## Tests

The test suite lives at [`tests/haex-init/`](../tests/haex-init/). Run
locally:

```
bash tests/haex-init/run-all.sh
```

Every test runs in a `HOME=$TMPDIR/…` sandbox with
`XDG_CACHE_HOME=$SANDBOX_ROOT/home/.cache` — the developer's real
`~/.claude/`, `~/.codex/`, `~/.gemini/`, `~/.haex-hive/`, and
`~/.cache/haex-init/verify/` are never touched (verified by SC-006).
The manual real-remote smoke test in `.validation-runs/haex-init-real-remote.md`
uses the same isolation via a temp `XDG_CACHE_HOME` so its cleanup
removes only its own cache tree.
