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
  "external_skills": ["example-org/example-skills"],
  "install_hook": {
    "interpreter": "python3",
    "script": "install.py",
    "on_failure": "warn"
  }
}
```

`install.py` may call the upstream tool, for example `npx skills add
example-org/example-skills`. The hook runs with the normal Spec 016 trust and
failure semantics. A consumer can opt out for one invocation with
`spaex install --no-install-hooks`.

The skill may live in the same `haexmas/atoms` repository as the molecule.
The reference is metadata for spaex: spaex itself does not copy it into the
consumer repository and does not claim to pin the upstream skill content; the
hook delegates that work to the external skills installer.
