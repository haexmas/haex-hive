# Quickstart: external skill references

**Design preview**: These structured references and skill commands are planned
and are not implemented by this documentation-only PR. The SHA below is a
placeholder; replace it with the full commit SHA containing the skill.

A publisher declares source metadata without an installation hook:

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
  ]
}
```

The consumer-selected adapter reads the pinned molecule `manifest.json` via
`SPAEX_MOLECULE_MANIFEST`. Normal `spaex install` only reports the reference as pending.
The consumer explicitly runs `spaex skills install`, chooses an adapter,
agent, and scope on first use, and spaex stores that choice in
`.spaex/manifest.json`. Later changes use `spaex skills configure`.

The skill may live in the same `haexmas/atoms` repository as the molecule.
The reference is metadata for spaex: spaex itself does not copy it into the
consumer repository. The explicitly selected installer owns the external
skill lifecycle, while the skill content remains outside spaex's install lock.
