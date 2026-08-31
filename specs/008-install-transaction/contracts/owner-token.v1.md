# Contract: Owner Token v1

**Spec**: [Spec 008 — Install Transaction Contract](../spec.md)
**Referenced by**: FR-001, FR-010, research §R4

## Format

An owner token is a single ASCII string of the shape:

```text
<pid>:<hostname>:<start_ns>:<uuid4_hex>
```

exactly four colon-separated fields, no leading or trailing whitespace, no embedded control characters, total length ≤ 128 bytes.

## Field constraints

| Field | Type | Constraint |
|---|---|---|
| `pid` | integer as decimal string | 1 ≤ value ≤ 2^32 - 1 (accommodates every POSIX/Windows pid range) |
| `hostname` | ASCII string | Matches `[A-Za-z0-9.-]{1,64}` — RFC 952 / 1123 acceptable subset. Longer or non-matching hostnames are truncated to the first 64 matching characters at token generation and the truncation is logged. |
| `start_ns` | non-negative integer as decimal string | `time.monotonic_ns()` value at lock acquisition. Purely for diagnostics; NOT compared with wall-clock. |
| `uuid4_hex` | 32-hex-char string | `uuid.uuid4().hex` — lowercase hex, no dashes. Provides the uniqueness guarantee. |

## Usage in `install.mutex`

`install.mutex` is a JSON file (see [install.mutex on-disk layout](#install-mutex-on-disk-layout) below) whose `owner_token` field carries this string verbatim. Recovery reads `install.mutex`, parses the token, and uses the four fields as follows:

- **`pid` + `hostname`**: displayed in the "lock owned by …" diagnostic when a lock conflict is detected. NOT used for ownership verification — a hostile process could forge these.
- **`start_ns`**: displayed in the diagnostic as an operator hint (paired with the current-time delta so the operator can see "the lock has been held for 4 minutes").
- **`uuid4_hex`**: the sole ownership-verification field. Recovery MUST re-read the mutex file's `owner_token` and confirm the entire token string is byte-identical between the "stale read" and the "reclaim moment" reads before overwriting the lease.

## `install.mutex` on-disk layout

Alongside this contract for completeness — the mutex file is a JSON object with these fields:

```json
{
  "owner_token": "31245:laptop-hex.local:1727612345678901234:8f3a2d1c9e7b4a5680c2e14f7d6b3a95",
  "acquired_at": "2026-08-31T14:20:11.000000Z",
  "heartbeat_at": "2026-08-31T14:20:16.000000Z",
  "heartbeat_at_ns_wallclock": 1788186016000000000,
  "heartbeat_interval_ns": 5000000000,
  "ttl_ns": 60000000000,
  "safety_margin_ns": 5000000000
}
```

- `heartbeat_at` and `heartbeat_at_ns_wallclock` are updated in place through the
  already-locked file handle and fsynced by the owner's background heartbeat
  thread every 5 seconds. The lock pathname and inode MUST remain stable while
  the advisory lock is held; an implementation MUST NOT use `os.replace()` for
  lease updates.
- `heartbeat_at_ns_wallclock` is the result of `time.time_ns()` at the same
  heartbeat and is the persisted, reboot-safe value used for expiry. The ISO
  `heartbeat_at` string is a diagnostic mirror and is not parsed for reclaim.
- `ttl_ns` is fixed at 60_000_000_000 (60 seconds) and `safety_margin_ns` at 5_000_000_000 (5 seconds) for MVP; a future revision MAY expose an override.
- `acquired_at` never changes after acquisition — recovery uses it for the operator diagnostic only, not for TTL logic.

## Recovery timing rules

- **Stale threshold**: recovery requires `time.time_ns() - heartbeat_at_ns_wallclock > ttl_ns + safety_margin_ns` (65 seconds for the MVP). A persisted monotonic timestamp MUST NOT be used for this cross-reboot comparison.
- **OS-lock fence**: recovery first obtains the same non-blocking exclusive OS lock. A process that is merely paused or slow still holds that lock and MUST NOT be reclaimed, even when its recorded heartbeat is old.
- **Atomic revalidation**: after obtaining the lock, recovery reads the lease, checks the stale threshold, then re-reads it under the exclusive handle. The owner token and wall-clock heartbeat MUST be byte-identical and still expired. Recovery then rewrites the record in place with its own token. A prior owner MUST check its token before every mutation and stop if it was fenced.
- **Clock semantics**: monotonic time is used to schedule the owner's 5-second heartbeat and populate `start_ns`; UTC timestamps are the cross-process expiry values. A backward wall-clock jump delays reclamation (safe); the 5-second safety margin absorbs the permitted clock skew. `mtime` is never used as an expiry signal.

## Emission

The token string is generated once at lock-acquisition time by:

```python
import os, socket, time, uuid, re

_HOSTNAME_ALLOWED = re.compile(r"[A-Za-z0-9.-]+")

def emit_owner_token() -> str:
    pid = os.getpid()
    raw_hostname = socket.gethostname()
    # Sanitise per contract: first 64 matching chars, or "unknown" if none match.
    match = _HOSTNAME_ALLOWED.findall(raw_hostname)
    hostname = ("".join(match) or "unknown")[:64]
    start_ns = time.monotonic_ns()
    uuid4_hex = uuid.uuid4().hex
    return f"{pid}:{hostname}:{start_ns}:{uuid4_hex}"
```

## Non-goals

- Cryptographic authentication of the token: this is a cooperation contract between well-behaved haex processes, not a security boundary. A malicious process can forge a token — the fenced-lease mechanism does not defend against that; OS-level file permissions on `$HAEX_HIVE_STATE/locks/` do.
- Cross-satellite ownership: `install.mutex` is device-local per FR-021 and never shared across satellites.
