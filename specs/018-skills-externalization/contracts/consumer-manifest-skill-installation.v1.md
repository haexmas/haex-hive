# Consumer manifest skill-installation contract v1

The consumer's `.spaex/manifest.json` may contain:

```json
"skill_installation": {
  "mode": "managed",
  "adapter": "skillsmd",
  "scope": "project",
  "agents": ["codex"]
}
```

- `mode` is required when the object is present and is one of `prompt`,
  `managed`, or `disabled`.
- `adapter` is a consumer-selected non-empty identifier and is not read from
  provider molecule manifests.
- `scope` is one of `project` or `global`.
- `agents` is a non-empty, unique list of non-blank agent identifiers.
- Unknown policy properties are rejected. Adapter and agent identifiers must
  not contain control characters or consist only of whitespace.
- `managed` requires `adapter`, `scope`, and `agents`; none is defaulted from
  provider data. These fields are optional for `prompt` and `disabled`, but
  must satisfy the same validation when supplied.
- An absent policy is equivalent to `prompt` for the explicit
  `spaex skills install` command, but never authorizes implicit installation by
  `spaex install`.

`spaex skills configure` edits this object. Changing it does not remove
already-installed external skills. Removal or migration requires an explicit
skill-management operation.

## Command behavior

| Policy | Explicit `spaex skills install` |
| --- | --- |
| Absent or `prompt` | In a TTY, ask the consumer to select/confirm mode, adapter, agents, and scope and persist the accepted policy before any adapter execution. `prompt` asks again on subsequent invocations; `managed` remembers consent. |
| `managed` | Invoke the selected adapter with the complete persisted policy; no additional prompt is required. |
| `disabled` | Report that skill installation is disabled and exit successfully without invoking an adapter or changing configuration. |

For absent or `prompt` policy without a TTY, fail with a non-zero exit status
and guidance to run `spaex skills configure` interactively. Cancellation or
EOF likewise leaves configuration and installed skills unchanged. A failed
policy write must prevent adapter execution. A consumer who confirms `prompt`
for this invocation must still choose adapter, scope, and agents before it runs.

`spaex skills configure` uses the same interactive selection and validation,
including mode changes, but never invokes an adapter. Without a TTY it fails
without writing. Saving policy preserves unrelated consumer-manifest fields.
Changing from `disabled` requires this explicit configuration command.

Normal `spaex install` does not prompt, mutate this policy, or invoke a skill
adapter in any mode. An unavailable adapter or unsupported target fails
without falling back to another installer, agent, or scope. Adapter failures
return a non-zero status and do not change atom files or `install.lock`;
external installer side effects may remain and are not automatically rolled back.
