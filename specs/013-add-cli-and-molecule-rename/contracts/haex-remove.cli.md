# `haex remove` — CLI Contract

**Spec**: 013
**Purpose**: retract one or more molecules from `.haex-hive.json` and run `haex install` in the same invocation so Spec 008's delete-orphans removes whatever the retracted molecules contributed.

## Synopsis

```
haex remove <molecule-id>[,<molecule-id>...]
```

## Arguments

| Argument | Kind | Meaning |
|---|---|---|
| `<molecule-id>[,<molecule-id>...]` | required positional | One or more reverse-DNS molecule ids to retract. Comma-separated on a single positional argument. |

## Behavior

### Successful retraction

1. Acquire the permanent advisory manifest lock at `.haex-hive.json.lock`.
2. Read `.haex-hive.json`. For every named molecule id, scan every entry in `compounds[]` and remove the id from the entry's `molecules[]` array.
3. Drop any compound whose `molecules[]` became empty.
4. If nothing changed (every named id was already absent), refuse with `unknown-molecule-id` naming the missing ids; do not modify `.haex-hive.json`.
5. Otherwise write the updated `.haex-hive.json` via `.haex-hive.json.tmp` + rename-in-place.
6. Call `haex install` in-process with the held manifest-lock context so delete-orphans (Spec 008 US3) removes files contributed only by the retracted molecules.
7. On install success: report the retracted molecule ids and the participating output roots that changed. Exit 0.
8. Release the manifest lock.

### Workflow-molecule fallback

When the retracted set includes the currently adopted workflow molecule, the ensuing install causes the tool to fall back to the bundled `speckit` workflow on the next resolve. No activation step is needed (Spec 011 amendment FR-008). `haex remove` does not emit a warning; the operator asked for the retraction, and the fallback is documented.

### Refusal keys

| Key | Meaning | Exit code |
|---|---|---|
| `unknown-molecule-id` | A named molecule id is not present in any current compound. Nothing written. | 2 |
| `install-transaction-failed` | Underlying `haex install` failed. Manifest edit is rolled back atomically under the still-held manifest lock. | matches install |
| `manifest-lock-contended` | Another process holds `.haex-hive.json.lock`. Nothing written. | 6 |

## Exit codes

- `0`: retraction complete; install succeeded; orphan files removed.
- `2`: at least one named molecule id was absent; no state changed.
- `6`: lock contention.
- Other: propagated from `haex install` per Spec 008.

## Determinism

- The written `.haex-hive.json` preserves the order of unaffected compounds and the order of unaffected molecule ids within compounds.
- Concurrent `haex remove` and `haex install` serialize via `.haex-hive.json.lock`.

## Non-goals

- **Purge cache**: `haex remove` does not delete anything under `$HAEX_HIVE_STATE/repos/<clone-hash>/`; publisher clones persist for future adoptions.
- **`haex replace`**: sugar for `remove` followed by `add` under one command. Deferred.
