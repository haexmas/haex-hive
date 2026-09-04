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

The split is by traffic class, not by a runtime bitrate check. LLM text-token streams are always on Nostr: each chunk is a small semantic event that benefits from audit-friendly ingress checks, throughput is trivial (a few KB/s per session), no measurement needed. Real-time media sessions (voice, video, screen, live large-file playback) are always on iroh: Nostr's per-event JSON envelope, base64 encoding, and per-event policy check are the wrong tool for that traffic profile, and public relays would drop the connection under it. A session's transport is fixed at offer time by the offer kind and does not migrate between Nostr and iroh at runtime; a session that changes character (an audio call gaining a video track, for example) opens a new offer.

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

Authorization is per iroh QUIC stream, not per underlying iroh connection. iroh multiplexes multiple streams onto a single connection between two peers, and every new stream carries its own ticket check at accept time. On each new-stream accept:

- The ticket must be currently issued, unexpired, bound to the intended recipient's `nostr_pubkey` and `iroh_node_id`, and tied to the event ID of the announcing offer. A ticket presented from any other peer identity is rejected, so a leaked ticket cannot authorize a session by a third party even before its single-use consumption.
- Ticket consumption is atomic and durable, keyed by the pair (`ticket`, offer event ID). Concurrent accepts race exactly one to success; every other concurrent accept fails. The ticket is consumed at the start of the handshake (fail-closed): a failed handshake does not release the ticket, the offer must re-issue.

Single-use therefore means "one accepted stream per ticket": one blob download session, or one `stream.offer` session. Session lifetime after the accept (ordinary teardown, heartbeat behavior on transient loss, and behavior on iroh endpoint reconnection or migration) is spec-phase work and listed in Section 5, item 11. No separate authorization layer sits on top of iroh.

### MCP as capability schema

- Local tools are exposed by a local MCP server per device.
- A compact capability summary (tool names, resource URIs, version) is published in the presence event; the full MCP schema is fetched over the direct connection once a session is opened.
- Remote MCP invocation is translated by an adapter into Nostr command events. The receiving device's adapter dispatches the tool call against its local MCP server and returns the result over Nostr.
- For results above a size threshold, or of a file-artifact type, the response event carries only metadata plus a `blob.offer`; the bytes travel via iroh. The calling LLM sees a normal MCP result with a resource URI.

### Confirmation for write actions

Policy may mark any capability class as `require-confirmation`. The relay holds such intents until it receives a signed release event from a device whose current attestation carries a `confirmation-authority` capability, master-attested and rotatable or revocable through the same attestation flow. The release event names the exact intent ID it authorizes; receivers verify the attestation binding and the intent scope before accepting the release, then forward the intent.

### Explicit device targeting

Any cross-device command must name a target device by alias. Aliases are assigned when a device is added to the trusted network: the master-signed attestation binds the alias to the initial `nostr_pubkey` and `iroh_node_id` pair. In the chat surface, aliases are typed with an `@`-mention convention (e.g. `@laptop-home`); the LLM sees the mention as a routed instruction, and the same explicit-target skill governs resolution and confirmation regardless of whether the target was typed as `@alias`, chosen from a picker, or supplied by another tool. A skill enforces this: the resolved target (alias plus `nostr_pubkey` plus `iroh_node_id`, both stable across sessions and both drawn from the current device attestation) is shown to the operator before dispatch. The signed intent payload carries `target_nostr_pubkey`, `target_iroh_node_id`, and the attestation epoch that was current at resolution time; the receiver validates all three against its own current attestation before executing. An alias rebinding between confirmation and dispatch therefore cannot silently route an authorized command to a different device: the alias is used for display and lookup only, never as the authorization binding. Alias uniqueness within the operator's device registry is enforced by the master signing at most one active attestation per alias, and rebinding requires a fresh master-signed attestation with a new epoch. When the command carries a file transfer, the ticket fingerprint of the accompanying `blob.offer` is shown alongside; pure control commands have no ticket at this stage. Stale presence is surfaced.

## 3. Harness model and haex-hive core integration

### Environment-scoped harnesses

Every LLM interaction happens in some **environment**, meaning a host process with its own tool space: the Tauri app itself, an IDE with an AI assistant (VSCode, JetBrains), a terminal LLM CLI (`claude`, `codex`, `gemini`). Each environment consumes exactly one harness at a time; harnesses do not merge, layer, or cascade across environments. The question "what is active where" is answered by making the environment itself the boundary.

Typical mapping:

- **Tauri app** → Jarvis harness. The operator's personal assistant with general skills, MCPs, prompts, and hooks. Active whenever the operator chats in the Tauri UI.
- **IDE (VSCode, JetBrains, ...)** → coding harness. Code-aware skills, project-specific MCPs, coding-oriented constitution. Active whenever the operator uses the IDE's AI assistant.
- **Terminal LLM CLI** → typically the coding harness, or a specialized shell harness.

Jarvis is **not** implicitly present in the IDE. To reach Jarvis from the IDE, the operator writes `@jarvis <message>`; see below.

### Placement: user-global vs project-local

Harnesses live in one of two roots, both using the same manifest format:

- **User-global**: `~/.haex-hive/` (or platform equivalent). Materialized on Tauri-app first launch and on updates. Natural home for the Jarvis harness.
- **Project-local**: `<repo>/.haex-hive/`. Materialized when the operator opens the project. Natural home for a coding harness scoped to that project (this is the classic haex-hive placement).

Combinations follow: a user-global harness may also target an IDE (a default coding harness for sessions outside any repo); a project-local harness may in principle target the Tauri app (rare in practice). The two dominant cases are (user-global, Tauri app) and (project-local, IDE).

### Cross-environment addressing: `@jarvis` and the bridge tool

From a non-Jarvis environment, the operator addresses another agent by `@`-mention. The coding harness ships a **bridge MCP tool** (working name: `jarvis-bridge`) that the environment's LLM sees among its available tools, and the tool resolves the mention:

1. The LLM parses `@<name> <message>` in a turn and calls the bridge tool with the mention name and message.
2. The bridge tool resolves `<name>`:
   - If it resolves to the local Jarvis (typically `@jarvis`), the bridge routes to the Tauri app on the same device via a local transport (Unix socket, Named Pipe, or localhost).
   - If it resolves to a device alias in the operator's registry (e.g. `@home-server`), the bridge forwards the call cross-device as a signed Nostr command event per Section 2.
3. The receiving Tauri app authenticates the caller (see below), applies its policy, runs the Jarvis turn, returns the answer as an MCP tool result to the calling LLM, which surfaces it to the operator.

Bridging is directional at v1: from a non-Jarvis environment into Jarvis. The reverse (Jarvis reaching into an open IDE session) is a later extension.

### Caller authentication for cross-environment MCP calls

The Tauri app verifies that an incoming MCP call really comes from a legitimate caller in a legitimate environment on a legitimate device. Two cases:

- **Same device**: on first setup the Tauri app issues a **signed session token** bound to `(device_id, environment_id, install_time)`. The token is materialized into the environment-side bridge config by the coding-harness install. The bridge presents the token on every MCP call; the Tauri app verifies the signature and looks the token up in its own registry. Token issuance is user-confirmed once (a prompt "allow VSCode on this device to talk to Jarvis"), not per call. Tokens are rotatable and revocable; uninstalling the bridge triggers a revocation event on the Tauri side.
- **Different device**: the cross-device call travels as a signed Nostr command event per Section 2. The device attestation is the auth path; no separate token is needed. The environment id still travels in the payload so the policy engine can distinguish `laptop:vscode` from `laptop:shell`.

### Policy shape: `(device, environment, capability)`

The policy engine authorizes on the triple `(source_device, source_environment, capability_class)`. Example rules:

- `laptop:vscode` may call `jarvis.ask`, `jarvis.remember`, `jarvis.retrieve_note`.
- `workstation:shell` may call `jarvis.ask` only.
- `phone:tauri` may call any capability marked `personal`; anything marked `write` requires confirmation.

The confirmation-authority mechanic from Section 2 still applies to write-marked calls, whether the caller is another own-device Jarvis or a local IDE.

### What the existing haex-hive core provides, unchanged

The speckit-driven core is not replaced; the personal agent and the harness model above extend its scope without changing its shape.

- **Handoff contract**: unchanged. A delegated task still carries a harness pin and lockfile hash; the receiver still runs `haex install` at that pin before starting the agent session. Applies to both user-global (Jarvis) and project-local (coding) harnesses. Cross-device transport is Section 2's signed Nostr command event.
- **Manifest v2/v3**: current declarations (skills, hooks, prompts, MCP servers) are unchanged. Gains a **target-environment declaration**: a harness names the environments it is intended for so the compiler dispatches per target. The runtime-capability declaration for cross-device MCP exposure remains the must-decide item from earlier (in-manifest schema bump vs. separate versioned artifact); leaving both interpretations open at implementation time is still not permitted.
- **Install transaction**: unchanged. Atomic materialization at the chosen install root, lockfile, orphan deletion, integrity checks.
- **Compiler and adapters**: adapter surface expands with one new target, the Tauri agent runtime. The other targets (Claude Code, Codex, Gemini CLI, IDE extensions) stay as they are today.
- **Environment plane** (Scope Realignment Decision 2): unchanged. Applies to build toolchains for a project's toolset; independent of the harness model above.
- **Speckit workflow** (ADR 0009): unchanged. Everything in this section must land through numbered specs before any code moves.

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
11. Stream session semantics for `stream.offer`, unresolved and normative in the stream spec:
    - Session identifier and its relationship to the announcing offer's event ID.
    - Ticket lifetime relative to session lifetime: strict single-use per stream, or session-scoped so a normal iroh QUIC connection migration continues the same authorized session without a fresh ticket.
    - Heartbeat interval, missed-heartbeat grace period, and behavior during transient network loss, so dead sessions are removed without terminating valid ones under short outages.
    - Reconnection semantics on iroh endpoint address change: same session continues under the existing authorization, or fresh authorization is required.
    - Codec negotiation and bandwidth adaptation within a session.
    - Optional in-session blob capture (for example, saving a video call to a persistent blob mid-stream).
12. Cross-environment addressing internals: bridge MCP tool schema (name, arguments, session-token transport in the call), session-token lifecycle (issuance flow, rotation, revocation on uninstall, encrypted at-rest storage on the environment side), environment identifier derivation (install-path-based, human-declared, or a combination), and handling of multiple concurrent instances of the same environment kind (two VSCode windows on the same device: shared environment id or per-window).

## 6. Follow-up work

Ordered by the earliest thing that must exist for the rest to have a normative home.

1. **ADR that reverses Scope Realignment Decision 1.** Must state the reversal, the "why not Buzz" answer, and the consequence for the retired Phase 3/4 framing in the main design doc. Once landed, this document is quotable as haex-hive scope, not just as design input.
2. **Update to the Scope Realignment document** noting that Decision 1 is superseded, with a pointer to the ADR and this design.
3. **Speckit spec for the attestation event and device registry.** The smallest normative slice, no transport yet.
4. **Speckit spec for the two-track ingress policy** with concrete event kinds and the relay policy engine surface.
5. **Speckit spec for the `blob.offer` announcement, ticket lifecycle, and iroh accept-handler.**
6. **Speckit spec for the MCP-to-Nostr adapter** and remote capability advertisement.
7. **Speckit spec for the Tauri runtime adapter** produced by the compiler.
8. **Speckit spec for the harness model and environment declarations**: environment enumeration, target-environment field in the manifest, placement conventions (user-global vs project-local), and the mapping of environments to compiler adapters.
9. **Speckit spec for the bridge MCP and same-device caller auth**: bridge tool schema, signed session-token protocol, installation and revocation lifecycle, at-rest storage on the environment side.
10. **Speckit spec for the `(device, environment, capability)` policy engine**, covering both cross-device MCP calls and cross-environment MCP calls under one authorization model.

Mobile scope, encryption-at-rest choice, and provider-model adapters are further follow-ups whose priority is set once the specs above are in flight.

## 7. Future direction beyond v1

Cross-user file and data sharing is a deliberate future extension. In v1 the trust model is a closed federation of one operator's own devices. A later version extends it to a **half-open sharing model**: an operator (Alice) can grant read (or richer) rights on a specific resource to another operator (Bob), either targeted to Bob's master pubkey or as a limited public share, for a defined period.

Sketched (not settled, not part of v1 scope):

- Two new event kinds signed by the resource owner: `access.grant` (names the resource, the grantee master pubkey, the rights, an expiry, optional device restriction) and `access.revoke` (references the grant event id, effective immediately).
- A third ingress track on the relay alongside command events and DMs: **guest events** (`access.request`, `blob.request`, `stream.request`) accepted only from pubkeys with a currently valid grant on the referenced resource, per a `guest_grants` table on the granter's device.
- Cross-operator attestation trust: the granter's device accepts the grantee's master-signed device attestations as proof of the grantee-device-to-grantee-master binding, but does not otherwise inherit trust from the foreign fleet. Pure signature verification, no persistent trust state.
- Grants are delivered to the grantee via NIP-17 DM plus published directly to the grantee's home relay if reachable; the grantee's UI shows a "granted access to R until D" entry.
- Existing `blob.offer` and `stream.offer` primitives are reused unchanged: the ticket binds to the grantee device's `nostr_pubkey` and `iroh_node_id` per the same rules that today bind to own-fleet identities.
- Revocation piggybacks the trust-store epoch mechanic: a revoke event flips the grant's epoch, in-flight iroh sessions tied to the grant are cancelled by the accept-handler on the next chunk exchange. The grantee does not have to observe the revoke for it to take effect; the granter's device simply stops honoring requests.

Open sub-questions for the future spec:

- Whether grants can reference dynamic resource sets (e.g. `/shared/*`) or only enumerated resources.
- Public share limits (per-grantee quotas, per-resource rate limits, aggregate egress budgets, abuse response).
- Discovery and change notification: does the grantee poll the resource, or does the granter push updates through the same DM channel that delivered the grant.
- Whether recursive delegation (Bob re-grants to Charlie) is allowed at all, and if so under what constraints.

This section is a scope pointer, not design input for the v1 specs listed in Section 6.
