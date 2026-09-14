# Contract: Spec Kit Integration CLI Surface v1

## spaex options

The `install` command gains:

```text
spaex install [--speckit-agents <selection>] [--no-speckit-integrations]
```

The `add` command forwards the same options to its internal installation so a
new molecule can be adopted and configured in one operation.

`<selection>` is one of:

- `none` — record a successful skip and do not invoke `specify`;
- `all` — select all declared integrations reported by `specify integration list`;
- comma-separated integration keys such as `claude,codex`.

`--no-speckit-integrations` is a per-invocation opt-out. It does not remove the
molecule declaration or external files and does not change the saved selection.

Molecules that need to install integrations which the official CLI does not
declare multi-install safe may set the declaration's boolean `force` field.
spaex then passes the official CLI's explicit `--force` option; this is not a
shell escape hatch and does not enable global installation.

Precedence is explicit selection, matching install-lock selection, interactive
prompt, then non-interactive refusal.

## Diagnostics

The implementation MUST expose stable diagnostic keys for at least:

| Key | Meaning |
|---|---|
| `speckit-declaration-invalid` | Molecule declaration is malformed or unsafe. |
| `speckit-cli-missing` | A legacy `specify` executable is not available on `PATH` when no provisioning block is declared. |
| `speckit-cli-version-incompatible` | `specify version` does not satisfy the declaration. |
| `speckit-integration-unsupported` | Selection is not reported by `specify integration list`. |
| `speckit-selection-required` | Non-interactive install has no explicit or persisted selection. |
| `speckit-cli-failed` | Official install operation failed. |
| `speckit-declaration-conflict` | Multiple molecules declare incompatible Spec Kit policies. |

Diagnostics MUST name the molecule, integration key when applicable, and the
operator action needed to continue.

## Machine-readable result

The normal human output remains readable CLI output. With the repository's
existing machine-readable diagnostic mechanism, each requested integration MUST
be representable as one outcome with:

```json
{
  "integration": "codex",
  "status": "installed",
  "cli_version": "0.12.11"
}
```

Failure outcomes include `diagnostic` and, when available, the official CLI
exit code. A successful install-lock generation contains only successful or
skip/already-satisfied outcomes.
