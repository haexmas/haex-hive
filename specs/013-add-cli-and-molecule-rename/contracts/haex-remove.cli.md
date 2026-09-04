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
2. Read `.haex-hive.json`. **Preflight**: verify that every named molecule id is present in at least one compound's `molecules[]` array. If any named id is absent from every compound, refuse with `unknown-molecule-id` naming **every** missing id in the diagnostic (not just the first), release the lock, and exit before any manifest mutation. `.haex-hive.json` is not modified.
3. For every named molecule id (all of which the preflight has confirmed as present), scan every entry in `compounds[]` and remove the id from the entry's `molecules[]` array.
4. Drop any compound whose `molecules[]` became empty.
5. Write the updated `.haex-hive.json` via `.haex-hive.json.tmp` + rename-in-place.
6. Call `haex install` in-process with the held manifest-lock context so delete-orphans (Spec 008 US3) removes files contributed only by the retracted molecules.
7. On install success: report the retracted molecule ids and the participating output roots that changed. Exit 0.
8. Release the manifest lock.

**All-or-nothing semantics**: a mixed request like `haex remove <present-id>,<absent-id>` refuses at step 2 without removing `<present-id>`. The operator either fixes the typo and retries, or invokes `haex remove <present-id>` explicitly. This preserves the "no state change on refusal" contract in the exit-code table.

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
