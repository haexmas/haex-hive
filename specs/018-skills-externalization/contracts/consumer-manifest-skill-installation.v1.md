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
- `agents` is a unique list of non-empty agent identifiers.
- An absent policy is equivalent to `prompt` for the explicit
  `spaex skills install` command, but never authorizes implicit installation by
  `spaex install`.

`spaex skills configure` edits this object. Changing it does not remove
already-installed external skills. Removal or migration requires an explicit
skill-management operation.
