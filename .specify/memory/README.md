# `.specify/memory/`

`constitution.md` in this directory is haex-hive's own contributed constitution
atom. Alongside it, `manifest.json` is the atom manifest required by FR-022
(Spec 007): it declares this atom's reverse-DNS `id`, `version`, and
`contributes.constitution: "constitution.md"`, so `haex constitution assemble`
can resolve and copy this file the same way it resolves any external
publisher's atom.

haex-hive migrated its own `.haex-hive.json` to v2 and pinned it to this atom
via the FR-023 self-migration commits:

- `39b5ea8` — commit A: root + atom manifests (T047)
- `ca9814c` — commit B: pin v1 `harness_sources` revision to commit A (T048)
- `b9a11cc` — commit C: v2-migrated `.haex-hive.json` (T049)
