# Quickstart: external skill references

A publisher declares the external reference and a hook that delegates to the
upstream tool:

```json
{
  "spaex_version": "4",
  "id": "com.example.publisher.agent-tools",
  "version": "2.0.0",
  "priority": 100,
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

`install.py` reads `external_skills` from the pinned molecule `manifest.json`
via `SPAEX_MOLECULE_MANIFEST` and may call the pinned Python adapter, for
example `uvx --from skillsmd==0.1.0 skillsmd add ...`. The hook runs with the
normal Spec 016 trust and failure semantics. A consumer can opt out for one invocation with
`spaex install --no-install-hooks`.

The skill may live in the same `haexmas/atoms` repository as the molecule.
The reference is metadata for spaex: spaex itself does not copy it into the
consumer repository. The hook delegates that work to `skillsmd`, while the
skill content remains outside spaex's install lock.
