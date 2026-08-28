# Quickstart: Multi-Spec External-Ref

**Phase**: 1 (planning)
**Spec references**: US1 (P1 MVP), US4 (P3) — from-scratch and
`--from-repo` bootstrap flows

End-to-end walkthrough. Two paths:
1. **Fresh consumer → new producer** (from-scratch mode)
2. **Fresh consumer → existing producer already used elsewhere on the device** (`--from-repo` bootstrap mode)

Both paths target the SC-001 3-minute completion time on a Linux
machine with SSH credentials pre-configured for the producer host.

## Prerequisites

- **Operating system**: Linux (mechanical target). macOS and
  Windows-under-WSL2 semantically supported but not part of
  Spec 006's mechanical validation (Assumption A9).
- **Tools on `$PATH`**: git ≥ 2.30, python3 ≥ 3.10
- **haex-init**: installed at `~/bin/haex-init` per Spec 005 install
  documentation (`git clone haex-hive; cp .specify/scripts/haex-init
  ~/bin/haex-init; chmod +x ~/bin/haex-init`)
- **spec-resolve**: installed at `~/bin/spec-resolve` per Spec 004
  install documentation (analogous flow)
- **SSH credentials**: configured for the producer host (e.g.,
  `ssh -T git@gitlab.com` returns "welcome"). Or:
  credential-manager state configured for HTTPS.
- **Environment**: `$HAEX_HIVE_STATE` either explicitly set, or
  defaulted per Research §1 (Linux: `$XDG_STATE_HOME/haex-hive` or
  `~/.local/state/haex-hive`)

## Path A — Fresh consumer, from-scratch

Scenario: `secure-web-frontend` is not haex-hive-managed yet.
Operator wants to opt into `secana-specs`' Constitution.

```bash
# 1. Start in the consumer project
cd ~/Projekte/secure-web-frontend

# 2. Bootstrap the project (Spec 005). Creates .haex-hive.json,
#    patches ~/.claude/CLAUDE.md, etc.
haex-init
# → follow prompts (Spec 005 flow)

# 3. Add secana-specs as external-harness source with only the
#    Constitution referenced (US1 P1 MVP acceptance).
haex-init add-source \
    --url git@gitlab.com:itemis/solutions/secana-specs.git \
    --revision b2f884158dc90fbd4ab956f00ee100a82b6ec3eb \
    --role constitution:.specify/memory/constitution.md:constitution
# → prompts operator to confirm the entry; writes .haex-hive.json;
#   then triggers `haex-init sync` (unless --no-sync).

# 4. Verify state
cat .haex-hive.local.json | python3 -m json.tool
# → should show a `resolved` map with `secana-specs:constitution`
#   pointing at an absolute path under $HAEX_HIVE_STATE/repos/.

# 5. Verify session-start injection (open a fresh Claude Code
#    session in this project).
claude
# → session-start snippet reads .haex-hive.local.json, extracts
#   the Constitution content, injects it. Ask the agent to quote a
#   specific Principle — it should quote from secana-specs'
#   Constitution unprompted.
```

**Expected outcome after step 3** (SC-001 timing):
- `.haex-hive.json` extended with one `external-harness` entry
- `.haex-hive.local.json` generated with `resolved.secana-specs:constitution`
- `$HAEX_HIVE_STATE/repos/secana-specs/` full clone present
- `$HAEX_HIVE_STATE/repos/secana-specs/.extracts/@b2f8841.../.specify/memory/constitution.md` present with `0600` mode
- `.gitignore` in the consumer contains `.haex-hive.local.json` inside a `haex-init`-managed marker block
- Total wall-clock: **under 3 minutes** on typical hardware

## Path B — Fresh consumer, bootstrapped from a neighbor

Scenario: same machine already has `secure-web-frontend` fully
configured with `secana-specs`. Now the operator initialises a
second consumer (`another-team-project`) and wants to use the
same producer entry.

```bash
# 1. Bootstrap the new consumer
cd ~/Projekte/another-team-project
haex-init

# 2. Copy the producer entry from the neighbor
haex-init add-source --from-repo ~/Projekte/secure-web-frontend
# → CLI lists secure-web-frontend's external-harness entries;
#   operator picks 'secana-specs'; add-source re-validates against
#   the current consumer's context; on accept, writes
#   .haex-hive.json.
# → sync runs automatically.

# 3. Verify state (same as Path A step 4)
cat .haex-hive.local.json | python3 -m json.tool
```

**Expected outcome**:
- The `secana-specs` entry in `another-team-project/.haex-hive.json`
  is a byte-copy of the neighbor's entry (same `repository`,
  `revision`, `name`, `auto_include`, `additional_include`, `items`)
- `$HAEX_HIVE_STATE/repos/secana-specs/` is REUSED — not re-cloned
  (FR-014 origin verification succeeds; SC-006 tested)
- The producer clone is shared, but each consumer has its own
  `.haex-hive.local.json` mapping into it
- Total wall-clock: **noticeably faster than Path A** because the
  clone is skipped

## Path C — Bumping the pinned revision (US3)

Scenario: `secana-specs` moved forward. Operator wants to bump.

```bash
cd ~/Projekte/secure-web-frontend

# 1. Edit .haex-hive.json manually, or use a future
#    `haex-init update-source` (out of Spec 006 scope — for now,
#    hand-edit the `revision:` field).
# For Spec 006 MVP, hand-edit:
#   "revision": "a1c4d92<new>...", # change from b2f8841
# In a later spec, add `haex-init update-source` for this too.

# 2. Sync
haex-init sync
# → fetches new SHA if missing, extracts new content, regenerates
#   .haex-hive.local.json
```

**Expected outcome**:
- New `.extracts/@a1c4d92.../` subtree
- Old `.extracts/@b2f8841.../` remains (NG-5: no eviction)
- `.haex-hive.local.json` `resolved` map now points into new SHA
- If a pinned path was RENAMED between b2f8841 and a1c4d92, sync
  refuses with structured error naming the offending path
  (SC-007 timing: < 5 seconds)

## Failure mode walk-through

For SC-003 (100% atomicity), trigger a controlled failure:

```bash
cd ~/Projekte/secure-web-frontend

# 1. Change a pinned path to something that doesn't exist at the
#    pinned SHA (edit .haex-hive.json manually).
# Example: change items[0].path to ".specify/does-not-exist.md"

# 2. Run sync
haex-init sync
# → exit code 2 (refused, precondition unmet)
# → stderr:
#   haex-init sync: item-path-missing: pinned path
#   .specify/does-not-exist.md not present at revision b2f8841
#     entry: harness_sources[1] (name: secana-specs, ...)
#     detail: path=.specify/does-not-exist.md, sha=b2f8841
#     fix: update path in .haex-hive.json or revert revision

# 3. Verify no state change
cat .haex-hive.local.json | python3 -m json.tool
# → still the pre-failure content, unchanged
```

## Common troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `add-source` refuses with "HTTPS URL contains credentials" | The URL you passed embeds a token like `https://user:token@…` | Switch to SSH URL, or use plain HTTPS with credential-manager state |
| `sync` refuses with "cannot reach producer" (exit 3) | SSH agent not running, key not loaded, or VPN required | Run `ssh -T git@<host>`; load the correct SSH key; connect VPN if applicable |
| `sync` refuses with "origin mismatch" (exit 2, case e) | The device-local clone was cloned from a different URL than the entry declares | Move the local clone aside (`mv $HAEX_HIVE_STATE/repos/<name> …bak`); re-run `sync` (clones fresh) — OR rename the storage `name:` in the entry |
| Content missing from `.haex-hive.local.json` | Include glob matched nothing at the pinned SHA (exit 2, case c) | Check the glob; check the pinned SHA; check the producer's tree at that SHA (`cd $HAEX_HIVE_STATE/repos/<name> && git ls-tree <sha> --name-only`) |
| Session-start snippet doesn't inject Constitution | `.haex-hive.local.json` is stale (config hash mismatch) | Run `haex-init sync` |
| `sync` hangs | Another `sync` for the same producer is running elsewhere; lockfile held | Wait; if stale, remove `$HAEX_HIVE_STATE/repos/<name>/.sync.lock` manually |

## Cleanup

```bash
# Remove Spec 006's device-local state (regenerable):
rm -rf $HAEX_HIVE_STATE/repos/

# Remove one consumer's local state (regenerable):
rm ~/Projekte/secure-web-frontend/.haex-hive.local.json
# Next `haex-init sync` recreates both.
```

Neither operation touches `.haex-hive.json` in any consumer — that
is the source of truth and stays committed.

## Success-criteria coverage

This quickstart exercises:

- **SC-001** (Path A step 3 timing < 3 min)
- **SC-002** (Path A step 3 second invocation timing < 1 s)
- **SC-003** (Failure walk-through, atomicity assertion)
- **SC-006** (Path B origin verification pathway)
- **SC-007** (Path C rename-refuse timing < 5 s)
- **SC-008** (Backward-compatibility — implicit: a
  Spec-004-only-config consumer still gets byte-identical
  session-start content)
- **SC-009** (Path B — `--from-repo` bootstrap zero manual JSON
  editing)
