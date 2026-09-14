# Molecule manifest external skills contract v1

The manifest remains a v4 molecule manifest. The additive field is:

```json
"external_skills": {
  "type": "array",
  "minItems": 1,
  "uniqueItems": true,
  "items": {
    "type": "string",
    "minLength": 1,
    "pattern": "^[^\\u0000-\\u001F\\u007F\\r\\n]+$"
  }
}
```

The property is optional. If present and non-empty, `install_hook` is
required. `atoms.skill` and `atoms.skills` are invalid property names. All
other atom categories retain the existing open-category behavior.

The hook is responsible for invoking the upstream installer. spaex does not
interpret the references or add them to the installed file paths.
