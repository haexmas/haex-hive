# Personal Agent Plane (Design)

**Status**: Design draft. Captured 2026-09-04 from a brainstorming session that revisited the ACP-over-Nostr direction retired by [Scope Realignment Decision 1](2026-09-03-scope-realignment-design.md#decision-1-haex-hive-builds-no-execution-plane-it-defines-a-handoff-contract-instead) one day earlier. The operator has decided to combine both scopes rather than choose between them: haex-hive keeps its speckit-driven harness core AND takes on a signaling and transport plane implemented in a Tauri application. This document records the direction; it does not by itself revise Decision 1. A follow-up ADR is required for that.

**Purpose**: hold today's architecture in the repository so the next session picks up on the same footing, and mark the concrete follow-up work that has to happen before any code lands.

**Related**:

- [Main haex-hive design](2026-08-26-haex-hive-design.md): the original Phase 3/4 vision is partially reinstated in a different shape (Nostr + iroh + MCP + Tauri, not ACP-over-Nostr).
- [Scope Realignment](2026-09-03-scope-realignment-design.md): Decision 1 (no execution plane, no daemon, no transport, no device identity plane, no session protocol, no mobile client) is superseded in intent by this document but not yet by an ADR. Decisions 2 through 11 remain in force.
- [ADR 0009](../adr/0009-declared-speckit-workflow-adherence.md): the speckit workflow still governs how anything below turns into a landing spec.
- [Spec 007: Unified Manifest v2/v3](../../specs/007-unified-manifest-v2/spec.md): the manifest continues to describe what a harness contributes; the agent runtime is a new consumer of it.
- [Spec 010: Compiler & Agent Adapters](2026-08-31-spec-010-compiler-preview.md): the compiler surface stays; a new adapter target (the Tauri agent runtime) will be added later.

---

## 0. Normative status

This is a design record. It fixes direction, not contracts. Every requirement below has to be re-expressed as a numbered spec under `specs/` before any code moves. Field names, event kinds, wire formats and identity derivations are working proposals, not settled interfaces.

## 1. Scope decision

The operator has decided on 2026-09-04 to combine the two directions previously treated as alternatives:

- **The speckit-driven harness core**: manifest v2/v3, install transaction, hook boundary, compiler and adapters, handoff contract. All decisions from Scope Realignment other than Decision 1 remain in force.
- **A personal-agent plane**: a Tauri application that runs on desktop, server, Android and iOS, each installation being a Nostr node and an iroh peer, with an explicit user-chosen model per request (local or provider-fronted).

Decision 1 of the Scope Realignment is therefore reversed in intent. This document does not carry that reversal formally; a follow-up ADR must state the reversal, its rationale, and its consequences (including an answer to the "why not Buzz" question, which the Scope Realignment left standing as a precondition).

Until that ADR lands, no spec descended from this document may claim Decision 1 as retired.

## 2. Architecture summary

### Two planes, disjoint by intent

- **Nostr** carries identity, presence, discovery, capability advertisement, commands, LLM prompts and text responses (including chunked text-token streams), DMs, and control-plane events (including iroh handshake tickets).
- **iroh** carries bulk bytes in two shapes over the same peer connection: content-addressed blobs for persistent artifacts (user-facing files, generated media saved as images, video, audio) via iroh-blobs' BAO tree (chunked, resumable, verifiable); and ephemeral QUIC streams for real-time media (voice call, video call, screen share, live playback of a large file whose bytes are not being captured as a blob).

LLM text-token streams stay on Nostr because each chunk is a small semantic event that benefits from audit-friendly ingress checks, and the throughput is trivial (a few KB/s per session). Anything at real-time media bitrate (audio, video, screen) is on iroh: Nostr's per-event JSON envelope, base64 encoding, and per-event policy check are the wrong tool for that traffic profile, and public relays will drop the connection under it.

### Device equals relay equals Tauri application

Each installation is one process that hosts:

- The Tauri UI.
- The agent runtime, including local and provider model adapters (local LLM, OpenAI/Codex, Claude, further providers, chosen explicitly by the user per request).
- An embedded Nostr relay endpoint.
- An iroh endpoint.
- A local encrypted database.
- A permission/policy layer.

"Relay" and "device" are the same trust boundary. There is no wire protocol between the app and the relay; policy checks are local function calls before an event is written to the relay database.

### Local-first, user-chosen models

- A local model is available whenever the device has the capacity to host one.
- The user selects model and reasoning tier explicitly. No automatic model routing overrides that choice.
- Relay and network faults must not block local work.

### Two-track ingress policy

The relay treats two classes of events differently:

- **Command events** (device-to-device: MCP calls, presence refresh, ticket handshake, status queries, policy updates). Accepted only from pubkeys in the master-attested device registry, with NIP-42 auth. Egress only to the relay endpoints of the operator's other devices. Since device equals relay one-to-one, the home-relay identity for a target device is the relay URL announced in that device's most recent valid presence event, signed by its attested `nostr_pubkey`; stale or revoked presence entries are excluded from egress. This is the closed federation.
- **DM events** (NIP-17 gift-wrapped, `kind:1059`). The outer wrapper carries a per-event random pubkey by design, so the operator blocklist is applied against the actual sender pubkey after gift-wrap decryption and sender validation, not against the outer pubkey. Wrapper events are admitted subject to explicit size, rate, and retention limits set on the relay. NIP-42 authenticates the local client publishing wrappers to the operator's own relays. Egress to whatever public relay set the user chose. This is the open channel.

Both handlers live in the same relay instance, dispatched by event kind.

### Identity model

- **Master key**: held offline (hardware token, a Nostr signer such as NIP-46, or paper backup). Not used for daily traffic.
- **Device keys**: one per installation. Each device holds its own Nostr keypair AND an iroh NodeId; both are bound in the same master-signed attestation event. Attestations are short-lived (working default: 7 days) and renewed while the master is present. Revocation is a single event that invalidates both endpoint identities.
- The attestation event kind is a haex-hive-specific kind, not NIP-26 (deprecated).

### Trust store covers both endpoints

Ingress checks share one table: `(alias, nostr_pubkey, iroh_node_id, valid_until, capabilities, epoch)`. Nostr ingress validates against `nostr_pubkey`, iroh accept-handler validates against `iroh_node_id`, and both check the current epoch and reject decisions that would be taken on a stale epoch value. Revocation bumps the epoch atomically for both endpoints; iroh transfers in flight against a stale epoch are cancelled by the accept-handler on the next chunk exchange. Any drift between the two trust states is structurally impossible. The precise epoch propagation, revocation ordering, and in-flight cancellation contract is spec-phase work.

### iroh authorization piggybacks Nostr

Two iroh session shapes exist, authorized identically by a signed offer event on Nostr plus a peer-bound iroh ticket:

- **Blob offer** (`blob.offer`): announces a content-addressed transfer. Carries the Blake3 hash, filename, MIME, size, and a short-lived iroh ticket.
- **Stream offer** (`stream.offer`): announces an ephemeral QUIC stream for real-time media. Carries a stream kind (voice, video, screen, generic), codec parameters, direction (unidirectional or bidirectional), an expected duration hint, and a short-lived iroh ticket. No content hash, since the payload is generated in real time.

The iroh accept-handler admits connections only for currently-issued, unexpired, single-use tickets bound to the intended recipient's `nostr_pubkey` and `iroh_node_id` and tied to the event ID of the announcing offer. Connections presenting a valid ticket from any other peer identity are rejected, so a leaked ticket cannot authorize a session by a third party even before its single-use consumption. Single-use means "one download session per ticket" for a blob and "one live session per ticket" for a stream, with the stream closing when the session ends or a heartbeat lapses. No separate authorization layer sits on top of iroh.

### MCP as capability schema

- Local tools are exposed by a local MCP server per device.
- A compact capability summary (tool names, resource URIs, version) is published in the presence event; the full MCP schema is fetched over the direct connection once a session is opened.
- Remote MCP invocation is translated by an adapter into Nostr command events. The receiving device's adapter dispatches the tool call against its local MCP server and returns the result over Nostr.
- For results above a size threshold, or of a file-artifact type, the response event carries only metadata plus a `blob.offer`; the bytes travel via iroh. The calling LLM sees a normal MCP result with a resource URI.

### Confirmation for write actions

Policy may mark any capability class as `require-confirmation`. The relay holds such intents until it receives a signed release event from a device whose current attestation carries a `confirmation-authority` capability, master-attested and rotatable or revocable through the same attestation flow. The release event names the exact intent ID it authorizes; receivers verify the attestation binding and the intent scope before accepting the release, then forward the intent.

### Explicit device targeting

Any cross-device command must name a target device by alias. A skill enforces this: the resolved target (alias plus `nostr_pubkey` plus `iroh_node_id`, both stable across sessions and both drawn from the current device attestation) is shown to the operator before dispatch. The signed intent payload carries `target_nostr_pubkey`, `target_iroh_node_id`, and the attestation epoch that was current at resolution time; the receiver validates all three against its own current attestation before executing. An alias rebinding between confirmation and dispatch therefore cannot silently route an authorized command to a different device: the alias is used for display and lookup only, never as the authorization binding. Alias uniqueness within the operator's device registry is enforced by the master signing at most one active attestation per alias, and rebinding requires a fresh master-signed attestation with a new epoch. When the command carries a file transfer, the ticket fingerprint of the accompanying `blob.offer` is shown alongside; pure control commands have no ticket at this stage. Stale presence is surfaced.

## 3. Integration with the existing haex-hive core

The speckit-driven harness core is not replaced; the personal agent is a new consumer of it.

- **Handoff contract**: unchanged. A task delegated to another device still carries a harness pin and lockfile hash. The receiver still runs `haex install` at that pin before starting the agent session. What changes is the transport of the handoff manifest: it can now travel as a signed Nostr command event between the operator's own devices, and the harness materialization happens locally on the receiving device before the agent turn begins.
- **Manifest v2/v3**: the current declarations (skills, hooks, prompts, MCP servers) are unchanged. The declaration of which capabilities the agent runtime exposes to remote devices needs a normative home, and the two candidate placements have different downstream consequences that the follow-up spec MUST decide, not defer: (a) keeping the declaration inside the manifest bumps the schema version, extends canonicalization, and covers the field with both the install transaction and the handoff hash, or (b) keeping it in a separate versioned runtime-capability artifact requires an explicit binding to the handoff, either by hashing the artifact from the manifest or by carrying a second pinned entry in the handoff manifest. Leaving both open at implementation time is not permitted; the follow-up spec picks one and this design does not.
- **Install transaction**: unchanged. Installation of the harness on any device is still atomic with a lockfile, orphan deletion and integrity checks.
- **Compiler and adapters**: the Tauri agent runtime is a new adapter target. The compiler emits per-tool artifacts as it does today; a new adapter emits the runtime's configuration file. This is future spec 010-follow-up work, not this document.
- **Environment plane** (Scope Realignment Decision 2): unchanged. The Tauri build's own toolchain is declared via the same environment block. No provider is installed by haex-hive.
- **Speckit workflow** (ADR 0009): unchanged. Everything in Section 2 must pass through `/speckit-specify` before any implementation.

## 4. What Nostr does that iroh does not, and vice versa

Recorded here so future readers do not relitigate:

- Nostr provides asynchronous publish to an offline recipient (relay stores events), identity-based discovery (a pubkey reaches all its posts), a cross-client public data model, censorship resistance through relay pluralism, zero infrastructure to publish, and Lightning-native payments.
- iroh provides two efficient direct-P2P transports over the same QUIC connection with hole-punching: content-addressed blob transfer (chunked, resumable, verifiable via BAO tree) for persistent artifacts, and ephemeral QUIC streams for real-time media. Both inherit the same peer-identity binding.

The split in Section 2 is chosen so each layer does what it is good at. No layer is asked to do the other's job.

## 5. What this document does not decide

Recorded here so the follow-up ADR and specs know their scope:

1. Event kind numbering for command events, presence events, `blob.offer`, `stream.offer`, attestation, revocation, confirmation. Working proposals only; numbers not fixed.
2. Wire format of the device attestation event (fields, signature scheme, replay protection). Replay protection is normative for every state-changing event kind (attestation, revocation, command, MCP call, confirmation release, `blob.offer`, `stream.offer`, handoff), covering event or intent ID, expiry, sender-and-target binding, durable deduplication or monotonic sequence checks, and explicit idempotency rules. The attestation spec fixes the mechanism once; the ingress, blob, MCP, and runtime specs reuse it.
3. Policy language for the ingress ACL (per-tool, per-argument, per-device-pair).
4. Relay implementation choice (nostr-rs-relay embedded, strfry embedded, or a purpose-built minimal relay). Trade-offs not yet weighed.
5. Encrypted-at-rest storage choice (SQLCipher, Sled + AGE, or other).
6. Master-key custody options (which of NIP-46, hardware token, or paper backup are supported at v1).
7. Mobile scope for v1. The operator has flagged mobile as an eventual target; whether v1 ships mobile at all, or only desktop and server, is unresolved.
8. Multi-device routing when several devices offer the same capability. The explicit-target skill covers UX; how presence events express load hints and "prefer for capability X" flags is unresolved.
9. Reason to build this rather than adopt Buzz (Decision 1 named this as a precondition). The follow-up ADR must answer it.
10. Sequencing: which of `attestation and ingress policy`, `ping round-trip`, `iroh blob roundtrip`, `MCP adapter and LLM` lands first, and against which milestone in the existing speckit backlog.
11. Stream session semantics for `stream.offer`: codec negotiation, session lifecycle (heartbeat interval, teardown, migration on network change), bandwidth adaptation, and optional in-session blob capture (e.g. saving a video call to a persistent blob mid-stream). Not settled by this document.

## 6. Follow-up work

Ordered by the earliest thing that must exist for the rest to have a normative home.

1. **ADR that reverses Scope Realignment Decision 1.** Must state the reversal, the "why not Buzz" answer, and the consequence for the retired Phase 3/4 framing in the main design doc. Once landed, this document is quotable as haex-hive scope, not just as design input.
2. **Update to the Scope Realignment document** noting that Decision 1 is superseded, with a pointer to the ADR and this design.
3. **Speckit spec for the attestation event and device registry.** The smallest normative slice, no transport yet.
4. **Speckit spec for the two-track ingress policy** with concrete event kinds and the relay policy engine surface.
5. **Speckit spec for the `blob.offer` announcement, ticket lifecycle, and iroh accept-handler.**
6. **Speckit spec for the MCP-to-Nostr adapter** and remote capability advertisement.
7. **Speckit spec for the Tauri runtime adapter** produced by the compiler.

Mobile scope, encryption-at-rest choice, and provider-model adapters are further follow-ups whose priority is set once the specs above are in flight.
