# Data Model: External Skill References

The v4 molecule manifest gains one optional property:

```json
{
  "atoms": {"constitution": ["constitution.md"]},
  "external_skills": [
    {
      "repository": "https://github.com/haexmas/atoms",
      "revision": "0123456789abcdef0123456789abcdef01234567",
      "path": "skills/example-skill"
    }
  ],
  "install_hook": {
    "interpreter": "python3",
    "script": "install.py",
    "on_failure": "warn"
  }
}
```

`external_skills` is a unique ordered JSON array of objects. Each object has a
`repository`, a lowercase 40-character immutable Git revision `revision`, and
a repository-relative skill `path`. The object is source metadata, not a
delivered file path, and is not added to `paths` in `install.lock`. It does not
contain an installer; the molecule's hook selects the installer, with
`skillsmd` as the default adapter.

At the Python boundary, `MoleculeManifest.external_skills` is an immutable
`tuple[ExternalSkillReference, ...]`. Each value is frozen and absent input
becomes `()`.

The schema condition is: `external_skills` with one or more entries requires
`install_hook`. A hook-less molecule may omit the field or use an empty array.
