# Molecule manifest external skills contract v1

The manifest remains a v4 molecule manifest. The additive field is:

```json
"external_skills": {
  "type": "array",
  "minItems": 1,
  "uniqueItems": true,
  "items": {
    "type": "object",
    "additionalProperties": false,
    "required": ["repository", "revision", "path"],
    "properties": {
      "repository": {
        "type": "string",
        "minLength": 1,
        "pattern": "^(?=.*\\S)[^\\u0000-\\u001F\\u007F\\r\\n]+$"
      },
      "revision": {
        "type": "string",
        "pattern": "^[0-9a-f]{40}$"
      },
      "path": { "$ref": "#/$defs/repoRelativePath" }
    }
  }
}
```

The property is optional. If present and non-empty, `install_hook` is
required. `atoms.skill` and `atoms.skills` are invalid property names. All
other atom categories retain the existing open-category behavior.

The hook is responsible for invoking the external installer, normally through
`uvx --from skillsmd==<version> skillsmd add ...`. spaex does not copy the
referenced skill or add it to the installed file paths. The hook reads the
existing pinned molecule manifest through `SPAEX_MOLECULE_MANIFEST`.
