# Spec Kit integrations

Molecules may declare the official Spec Kit integrations they support without
shipping copies of Spec Kit skills:

```json
{
  "speckit": {
    "version_constraint": ">=0.8.1",
    "integrations": {
      "claude": { "integration_options": "--skills" },
      "codex": { "integration_options": "--skills" }
    }
  }
}
```

During `spaex install`, select integrations explicitly with
`--speckit-agents claude,codex`, choose interactively, or disable the step for
one invocation with `--no-speckit-integrations`. spaex delegates file layout,
managed-file conflicts, and agent-specific behavior to the installed official
`specify` CLI.

The `specify` CLI is provisioned separately. spaex does not install Python, uv,
Spec Kit, or an agent runtime implicitly. Since the official CLI owns the
external agent files, removing a molecule warns about files that may remain;
spaex does not automatically uninstall them.
