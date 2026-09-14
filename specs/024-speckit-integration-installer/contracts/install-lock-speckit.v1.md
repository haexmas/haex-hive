# Contract: Install Lock Spec Kit Record v1

The v4 install-lock molecule entry gains an optional `speckit` object. The
existing molecule identity and path ordering rules remain unchanged.

```json
{
  "speckit": {
    "cli_version": "0.12.11",
    "declaration_fingerprint": "sha256:64-lowercase-hex",
    "selected": ["claude", "codex"],
    "outcomes": {
      "claude": "installed",
      "codex": "already_satisfied"
    }
  }
}
```

Validation rules:

- `cli_version` is the version reported by the official CLI.
- `declaration_fingerprint` is a lowercase SHA-256 fingerprint prefixed with
  `sha256:`.
- `selected` is unique and sorted.
- Outcome values are `installed`, `already_satisfied`, or `skipped` in a
  published successful generation.
- A failed external install is not written as a successful generation; the
  prior lock remains byte-for-byte intact.
- Unknown future top-level fields follow the existing lock forward-compatibility
  behavior, while malformed `speckit` records refuse validation.
