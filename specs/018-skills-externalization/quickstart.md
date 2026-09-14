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

`install.py` may inspect the pinned molecule `manifest.json` via
`SPAEX_MOLECULE_MANIFEST`, but provider hooks do not select the consumer's
skill installer. Normal `spaex install` only reports the reference as pending.
The consumer explicitly runs `spaex skills install`, chooses an adapter,
agent, and scope on first use, and spaex stores that choice in
`.spaex/manifest.json`. Later changes use `spaex skills configure`.

The skill may live in the same `haexmas/atoms` repository as the molecule.
The reference is metadata for spaex: spaex itself does not copy it into the
consumer repository. The explicitly selected installer owns the external
skill lifecycle, while the skill content remains outside spaex's install lock.
