# Data Model: External Skill References

The v4 molecule manifest gains one optional property:

```json
{
  "atoms": {"constitution": ["constitution.md"]},
  "external_skills": ["vercel-labs/skills", "https://agentskills.io/example"] ,
  "install_hook": {
    "interpreter": "python3",
    "script": "install.py",
    "on_failure": "warn"
  }
}
```

`external_skills` is a unique ordered JSON array of strings. Strings are
opaque to spaex and may represent a skills.sh slug or an agentskills.io
repository/path. They are not file paths and are not added to `paths` in
`install.lock`.

At the Python boundary, `MoleculeManifest.external_skills` is an immutable
`tuple[str, ...]`. Absent input becomes `()`.

The schema condition is: `external_skills` with one or more entries requires
`install_hook`. A hook-less molecule may omit the field or use an empty array.
