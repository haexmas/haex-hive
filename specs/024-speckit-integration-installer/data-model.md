# Data Model: Declarative Spec Kit Integration Installer

## Molecule `speckit` declaration

The molecule manifest gains an optional top-level `speckit` object. It is
metadata, not a delivered atom category, and is mutually exclusive with an
`install_hook`-based Spec Kit installation path by semantic validation.

```json
{
  "speckit": {
    "version_constraint": "0.12.11",
    "integrations": {
      "claude": {
        "integration_options": ""
      },
      "codex": {
        "integration_options": "--skills"
      }
    }
  }
}
```

### Fields

| Field | Type | Required | Rules |
|---|---|---:|---|
| `version_constraint` | string | yes | Existing spaex grammar: exact `X.Y.Z` or lower bound `>=X.Y.Z`; no `latest`, branch, or wildcard. |
| `integrations` | object | yes | Non-empty map keyed by Spec Kit integration key. Keys are unique by JSON object shape. |
| `integrations.<key>.integration_options` | string | no | Exact text passed as the official CLI's `--integration-options` value. Empty means no extra option. Must not request global installation. |

The declaration does not contain `SKILL.md` paths, remote URLs, executable
scripts, or agent-specific destination paths.

## Consumer selection

Selection is invocation state, not a new consumer-manifest top-level field.

| Source | Shape | Precedence |
|---|---|---:|
| CLI override | `--speckit-agents claude,codex`, `--speckit-agents all`, or `--speckit-agents none` | 1 |
| Existing lock | previous successful selection for the same declaration fingerprint | 2 |
| Interactive prompt | zero or more declared integration keys | 3 |
| Non-interactive absence | refusal with actionable diagnostic | 4 |

The selection is valid only when every selected key occurs in the molecule's
declaration. `all` expands to all declared keys that the installed `specify`
CLI reports as supported. `none` is a successful skip and never invokes the
external installer.

## Declaration fingerprint

The fingerprint is SHA-256 over the canonical JSON representation of the
`speckit` declaration plus the resolved molecule source, revision, and
effective consumer configuration. It is used only for no-op comparison and
does not replace the molecule's immutable source revision.

## Integration outcome

Transient outcome for one requested key:

```text
IntegrationOutcome
├── key: str
├── status: installed | already_satisfied | skipped | cancelled | unsupported | failed
├── cli_version: str | null
├── exit_code: int | null
└── diagnostic: str | null
```

`failed` is reported for the current invocation. A failed invocation does not
produce a successful install-lock generation; the prior lock remains intact.

## Install-lock contribution

The existing molecule entry gains an optional `speckit` record:

```json
{
  "id": "com.example.speckit",
  "source": "https://github.com/example/harness",
  "revision": "0123456789abcdef0123456789abcdef01234567",
  "paths": [],
  "speckit": {
    "cli_version": "0.12.11",
    "declaration_fingerprint": "sha256:...",
    "selected": ["claude", "codex"],
    "outcomes": {
      "claude": "installed",
      "codex": "already_satisfied"
    }
  }
}
```

Rules:

- The `speckit` record is absent for molecules without a declaration.
- `selected` is sorted by UTF-8 key order.
- `outcomes` contains only successful generation states; a failed run is
  emitted as a diagnostic and is not published as a successful lock.
- A `speckit`-only molecule is valid and may have `paths: []`, matching the
  existing hook-only molecule pattern without using a hook.
- Removing the molecule removes its lock record, but does not delete external
  Spec Kit files; removal emits the specified warning.

## State transitions

```text
no declaration ───────────────→ no-op
declaration + no selection ───→ prompt / non-interactive refusal
prompt or override + none ────→ skipped
selected + same lock fingerprint → already_satisfied
selected + changed fingerprint ─→ official CLI install
official CLI success ──────────→ installed
official CLI unsupported/fail ─→ failed diagnostic; prior generation retained
```
