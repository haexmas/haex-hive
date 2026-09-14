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
contain an installer; the consumer selects the installer and its target policy.

At the Python boundary, `MoleculeManifest.external_skills` is an immutable
`tuple[ExternalSkillReference, ...]`. Each value is frozen and absent input
becomes `()`.

External skills do not require a provider `install_hook`. A molecule without
`external_skills` remains unchanged.

The consumer manifest may persist an explicit policy separately from provider
references:

```json
{
  "skill_installation": {
    "mode": "managed",
    "adapter": "skillsmd",
    "scope": "project",
    "agents": ["codex"]
  }
}
```

`mode` is consumer-owned and may be `prompt`, `managed`, or `disabled`.
`adapter`, `scope`, and `agents` are selected by the consumer. The policy is
not copied from a provider molecule. An absent policy means that normal
`spaex install` reports pending external skills but performs no installation.
