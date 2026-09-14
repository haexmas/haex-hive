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

The property is optional; if present, it must be non-empty. `install_hook`
is not required, including for reference-only molecules with `atoms: {}`. `atoms.skill` and `atoms.skills` are invalid property names. All
other atom categories retain the existing open-category behavior.

Only `spaex skills install` may invoke the consumer-selected adapter. Normal
`spaex install` does not invoke it. spaex does not copy the referenced skill
or add it to installed file paths. The adapter reads the existing pinned
molecule manifest through `SPAEX_MOLECULE_MANIFEST`; provider hooks are not
required or selected as skill installers.
