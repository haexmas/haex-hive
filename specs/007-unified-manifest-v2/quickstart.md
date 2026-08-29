# Quickstart: Spec 007 Unified Manifest v2

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-08-29

This quickstart walks a maintainer through the three user-story paths delivered by Spec 007. Each path is independently testable — you can validate US1 without touching US2/US3/US4, and vice versa. Every command shown here is provided by the `haex` console script (installed via `pip install haex-hive`).

## Prerequisites

- Python 3.10+ on PATH (`python3 --version`).
- `pip install haex-hive` (or `pipx install haex-hive`).
- `git` 2.30+ on PATH.
- For US3 only: an operator-attached LLM (running `haex` inside Claude Code, or a shell with a compatible agent-runtime).

## Path 1 — Migrate haex-hive itself from v1 to v2 (US1, P1 MVP)

This is the reference case for `haex migrate`. It exercises the deterministic v1→v2 rewrite against a real v1 file.

### Setup

You are working in a clone of the haex-hive repo whose `.haex-hive.json` is still v1 shaped (this is the state at the moment Spec 007 lands):

```bash
cd ~/Projekte/haex-hive
cat .haex-hive.json
# {
#   "haex_hive_version": "1",
#   "identity": "github.com/haexmas/haex-hive",
#   "harness_sources": [ ... ],
#   ...
# }
```

You also have this repo cloned (as a bare or non-bare clone) under `$HAEX_HIVE_STATE/repos/<clone-hash>/` at the revision the v1 file pins. In development, this is prepared by the test-fixture setup (see Spec 007's `research.md` §"Deferred / open technical questions").

### Preview the migration (dry-run)

```bash
haex migrate --dry-run
```

Expected output: a unified diff between the v1 and proposed v2 shape printed to stdout, exit code 0. No files written. If the v1 file cannot be migrated (permission-only entries, credential-URL, ambiguous role mapping), a diagnostic on stderr with a non-zero exit code (2 or 3 per the CLI contract).

### Write the sidecar

```bash
haex migrate
ls .haex-hive.json*
# .haex-hive.json           <- untouched
# .haex-hive.json.migrated  <- new proposal
```

The diff printed on stdout matches the one from `--dry-run`. Review the sidecar content:

```bash
cat .haex-hive.json.migrated
```

You will see the v2 shape:

```json
{
  "haex_hive_version": "2",
  "haex_hive_min_version": ">=2.0.0",
  "identity": "com.github.haexmas.haex-hive",
  "atoms": [
    {
      "source": "https://github.com/haexmas/haex-hive.git",
      "revision": "b2f884158dc90fbd4ab956f00ee100a82b6ec3eb",
      "includes": [
        "com.github.haexmas.haex-hive.constitution"
      ],
      "config": {}
    }
  ],
  "groups": [],
  "active_feature": null
}
```

### Land the migration via PR

```bash
git checkout -b docs/migrate-to-v2
mv .haex-hive.json.migrated .haex-hive.json
git add .haex-hive.json
git commit -m "feat!: migrate .haex-hive.json to v2 (Spec 007)"
git push -u origin docs/migrate-to-v2
gh pr create --base main --head docs/migrate-to-v2 --title "..." --body "..."
```

The PR includes the migration diff and lands as one reviewed unit. This satisfies Constitution v1.3.0's Principle VI clarification.

### Verify idempotence

After the merge, re-run:

```bash
haex migrate
# already migrated to v2 (haex_hive_version: 2)
```

Exit 0, no files written. This proves FR-012's already-v2 guard.

## Path 2 — Single-source `haex constitution assemble` (US2)

This exercises the byte-for-byte straight-copy path.

### Setup

Your `.haex-hive.json` v2 has exactly one constitution atom in `atoms[].includes[]`. The pinned publisher revision has a `manifest.json` at the repo root and an atom `manifest.json` in the atom directory declaring `contributes.constitution: "constitution.md"`.

### Assemble

```bash
haex constitution assemble
```

No LLM is invoked (single-source). Two files are written atomically:

- `.haex-hive/constitution.md`: byte-identical copy of the source file at the pinned SHA. Verify:

  ```bash
  sha256sum .haex-hive/constitution.md
  # compare with the source file's SHA-256 at the pinned SHA:
  git -C $HAEX_HIVE_STATE/repos/<clone-hash> show <sha>:<source-path> | sha256sum
  # digests match.
  ```

- `.haex-hive/install.lock`:

  ```json
  {
    "haex_hive_version": "2",
    "generated_by": "haex 2.0.0",
    "constitution": {
      "sources": [
        {
          "id": "com.github.haexmas.haex-hive.constitution",
          "revision": "b2f884158dc90fbd4ab956f00ee100a82b6ec3eb",
          "source": "https://github.com/haexmas/haex-hive.git"
        }
      ],
      "content_integrity": "sha256-<base64-of-constitution-md-sha256>"
    }
  }
  ```

### Verify determinism

```bash
haex constitution assemble
diff <(cat .haex-hive/constitution.md) <(git show HEAD:.haex-hive/constitution.md)  # empty
diff <(cat .haex-hive/install.lock)   <(git show HEAD:.haex-hive/install.lock)      # empty
```

Two runs → byte-identical outputs. This proves FR-031 and FR-036.

## Path 3 — Multi-source `haex constitution assemble` (US3)

This exercises the LLM-merge path.

### Setup

Your `.haex-hive.json` v2 has two or more constitution atoms in `atoms[].includes[]` (e.g., a base plus a team overlay). You are running `haex` inside an environment with LLM access.

### Assemble (`stdio` method)

```bash
haex constitution assemble
# (LLM is auto-detected via TTY; --llm=stdio is the default in a TTY environment)
```

The command prints the source constitutions plus a merge instruction to stdout and blocks on stdin. In Claude Code (or with a human present), the agent/operator reads the sources, produces the merged content, and pastes it back on stdin (terminating with EOF or a sentinel line). The command writes `.haex-hive/constitution.md` and `.haex-hive/install.lock` atomically.

### Alternative: two-phase file flow (`file` method)

If you prefer explicit control or run in a non-TTY agent context:

```bash
haex constitution assemble --llm=file
# writes .haex-hive/constitution.merge.pending.json, exits with code 5.
```

The agent (or a human) reads `.haex-hive/constitution.merge.pending.json`, produces the merged content, writes it to a candidate file:

```bash
# ...agent produces the merged output...
cat > .haex-hive/constitution.md.candidate <<EOF
# Merged Constitution
...
EOF

haex constitution assemble --accept-merged .haex-hive/constitution.md.candidate
# writes the final files, exits 0.
```

### Verify byte-identity on another device

After committing the multi-source-assembled `.haex-hive/constitution.md` and `.haex-hive/install.lock`, on a second device that pulls the branch:

```bash
git pull
sha256sum .haex-hive/constitution.md
# base64-encode: "sha256-<base64>"
# compare with:
jq -r '.constitution.content_integrity' .haex-hive/install.lock
# equal.
```

`haex constitution assemble` is NOT re-run on this device; the committed file is verified via `install.lock`.

### Refuse on missing LLM

On a device with no attached LLM (e.g., a CI runner) and a multi-source repo:

```bash
haex constitution assemble
# error: exit=4 key=llm-required-for-multi-source
```

Exit 4, no files modified. This proves FR-028.

## Path 4 — `haex constitution show` (US4)

Read-only inspection of the effective constitution.

### With preface

```bash
haex constitution show
```

Output:

```
# Assembled from
- com.github.haexmas.haex-hive.constitution @ b2f8841 (https://github.com/haexmas/haex-hive.git)

---

# haex-hive Constitution

...
```

The preface comes from `.haex-hive/install.lock`; the body comes from `.haex-hive/constitution.md`. The `constitution.md` file itself does NOT contain the preface (FR-029).

### Without preface (scripting)

```bash
haex constitution show --no-preface | some-validator
```

Output: exactly the byte-for-byte content of `.haex-hive/constitution.md`.

### Missing-file refuse

If `.haex-hive/constitution.md` is missing (fresh clone with no v2 setup yet, or `haex constitution assemble` never ran):

```bash
haex constitution show
# error: exit=2 key=constitution-not-assembled
```

## Cross-cutting checks

### Schema validation of an arbitrary `.haex-hive.json` v2 file

The JSON Schema is packaged with `haex-hive`. External tools (e.g., a JSON Schema validator in an editor) can consume it directly:

```bash
python -c "from haex_hive.schema.loader import load; print(load('haex-hive.v2.schema.json'))"
```

### Version-gate refuse

If `.haex-hive.json` declares `haex_hive_min_version: ">=3.0.0"` but the installed `haex` is at 2.0.0:

```bash
haex migrate
# error: exit=5 key=version-below-min
#   required: >=3.0.0
#   installed: 2.0.0
#   hint: pip install --upgrade haex-hive
```

This applies uniformly to every `haex` verb (FR-006).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `haex migrate` exits 2 with `key=permission-only-entry` | v1 file has a permission-only `harness_sources[]` entry (bare repo or repo+revision only) | Manually edit the v1 file to remove the permission-only entry OR replace it with a concrete atom reference before migrating. |
| `haex migrate` exits 3 with `key=missing-remote-origin` | The repo has no `remote.origin.url` configured | `git remote add origin <url>` and retry. |
| `haex constitution assemble` exits 2 with `key=atom-manifest-not-found` | Publisher's root `manifest.json` maps the atom-id but the atom directory has no `manifest.json` at that SHA | Verify with `git show <sha>:<path>/manifest.json` in the publisher clone. |
| `haex constitution show` exits 3 with `key=install-lock-missing` | `haex constitution assemble` has never run in this repo | Run `haex constitution assemble` first. |
| Multi-source assemble hangs after prompting on stdout | `--llm=stdio` is waiting for EOF on stdin | Send the merged content followed by Ctrl-D (Unix) or Ctrl-Z+Enter (Windows), OR use `--llm=file` for explicit two-phase flow. |
