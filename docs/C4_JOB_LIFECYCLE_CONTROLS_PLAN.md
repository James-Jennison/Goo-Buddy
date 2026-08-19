# C4 — cross-platform job lifecycle controls

**Status:** C4.0–C4.4 are complete for the configured printer evidence:
the owner's historical P1P confirmation for Bambu, and separately supervised
exact configurations for Elegoo CC1 and Moonraker. Bambu retains its inherited
fixed lifecycle routes with C4 operation-only audit records. Elegoo SDCP v3
and Moonraker remain default-off until their exact observed identity has
separate owner activation. This is the implementation and validation plan for
pause, resume, and cancel across every supported printer family: Bambu Lab,
Elegoo SDCP v3, and Klipper through Moonraker.

This plan does not authorize printer contact or a control action. A separate,
explicit approval is required for each supervised hardware-validation session.
Until a platform and operation meet its activation gate, Goo Buddy continues to
present that platform as monitoring-only and must not send a job command.

## Current baseline

Goo Buddy already contains useful *implementation scaffolding*, not current
control claims:

| Platform | Existing implementation evidence | Current product decision |
| --- | --- | --- |
| Bambu Lab | Inherited MQTT pause, resume, and stop paths plus established printer and queue regression coverage. The owner has confirmed prior successful lifecycle use, reconnect/restart handling, and concurrent-state handling on their configured P1P. | The legacy routes retain their existing fixed behaviour and now write operation-only C4 audit entries. This is historical owner evidence for that configured P1P only; it does not establish controls for another model, firmware, or source. |
| Elegoo SDCP v3 | A closed private mapping for pause, cancel, and resume exists in code, with deterministic fixtures. Separately approved, supervised CC1 sessions confirmed all three operations for Elegoo Centauri Carbon firmware `V0.4.0-o`, acknowledgement-loss handling, reconnect, restart revocation, and concurrent printer-side cancellation. | Default-off. Only that exact current evidence record may request a separate owner acknowledgement; every other Elegoo source remains monitoring-only. |
| Moonraker | A closed private mapping for fixed bodyless print-job endpoints and deterministic fixtures exists in code. Separately approved, supervised sessions for normalized identity `Klipper` / `v0.10.0-31-gd5ee171` confirmed pause, resume, cancel, reconnect, temporary status-client restart, and concurrent printer-side cancellation with fresh status reconciliation. | Default-off. Only that exact current identity may request a separate owner acknowledgement; every other Moonraker source remains monitoring-only. |

The shared command record intentionally admits only `pause_job`,
`resume_job`, and `cancel_job`; it cannot carry an arbitrary path, body,
JSON-RPC method, G-code, or SDCP payload. That is a useful starting point,
but it is not an activation switch, owner acknowledgement, or evidence record.

## C4 activation rules

An individual operation becomes available only when all of the following are
true for the selected saved source:

1. The platform-specific protocol contract is documented and pinned to the
   operation; no model-name or open-port inference is permitted.
2. Deterministic adapter, API, UI, permission, idempotency, timeout, and
   reconciliation tests pass for that exact operation.
3. The source has a separate, explicit owner control acknowledgement. A
   monitoring acknowledgement never doubles as permission to control a
   printer. The default is disabled.
4. A fresh, authoritative source observation establishes the required state:
   `printing` for pause/cancel and `paused` for resume/cancel. Retained,
   stale, idle, finished, error, disconnected, or unknown state fails closed.
5. The caller has the control permission, the target is named in the
   confirmation, and the operation is recorded in an audit ledger with a
   bounded idempotency key.
6. A separately approved, supervised test has established the on-device
   result and the post-command reconciliation rule for that platform,
   firmware/configuration, and operation.

An HTTP route, dormant adapter, fixture, or vendor documentation satisfies
none of steps 3 or 6 by itself. UI code must use the normalized capability
value `job-control`; no control UI may appear merely because a status object
mentions a printing-like state.

## Delivery slices

### C4.0 — fail-closed activation policy

Implemented for the isolated Elegoo and Moonraker sources: the persisted
control gate defaults to disabled, survives restart safely, is cleared by
endpoint/configuration replacement, and prevents both API dispatch and UI
capability projection. It has no owner-facing enable path. Neither platform
is routed through another platform's client.

For Elegoo, the SDCP normalizer itself never infers `job-control` from a
payload declaration. The manager can project it only after the separate source
gate is explicitly enabled and only while a fresh, internally consistent
authoritative state is `printing` or `paused`. A present current-job field must
agree with that state, but an omitted `PrintInfo` record is not stale by
itself; stale, retained, idle, malformed, and conflicting observations remain
control-free.

Bambu's inherited fixed operational paths retain their established response
shape and permission model. C4.1 maps each one into the operation-only audit
ledger without accepting a payload or changing the fixed MQTT vocabulary.

Deterministic tests prove that a copied API request, a stale observation, an
enabled monitoring source, or a dormant adapter cannot bypass the policy.
This slice adds no owner-facing enable switch until the platform-specific
evidence slice has been reviewed.

### C4.1 — platform evidence and reconciliation contracts

For each platform and each operation, record the exact outbound vocabulary,
accepted acknowledgement/status transition, bounded timeout, and safe outcome
when the transport disconnects or the printer changes state concurrently.

- **Bambu Lab:** the inherited fixed MQTT methods now write C4 audit entries
  without changing existing Bambu behaviour. A caller may optionally provide
  a bounded idempotency key; callers that omit it retain the legacy request
  contract and receive a server-generated audit key. Existing MQTT status
  remains the only source of subsequent printer state; this slice does not
  claim a newly implemented post-command physical reconciliation loop.
- **Elegoo SDCP v3:** the separately approved CC1 session established the
  exact command and expected status transition for pause, resume, and cancel
  on Elegoo Centauri Carbon firmware `V0.4.0-o`. Preserve the established
  stale-job rule while validating current state; do not generalize this
  evidence to another source, model, or firmware.
- **Moonraker:** the separately approved session established the fixed
  pause/resume/cancel endpoint transitions for the chosen Klipper
  configuration. Do not widen the existing fixed request vocabulary or add
  JSON-RPC/G-code, and do not generalize this evidence to another source or
  firmware.

Each platform remains disabled for every operation that lacks this contract.

#### C4.1a — offline reconciliation baseline

The first C4.1 implementation slice records a closed, non-dispatching
reconciliation contract for all three supported printer families. It is a
source-of-truth for the pre-command and successful post-command state that a
future activation must observe:

| Platform | Pause | Resume | Cancel | Evidence status |
| --- | --- | --- | --- | --- |
| Bambu Lab | `RUNNING` → `PAUSE` | `PAUSE` → `RUNNING` | `PREPARE`/`SLICING`/`RUNNING`/`PAUSE` → `IDLE`/`FINISH`/`FAILED` | inherited regression coverage plus owner-confirmed lifecycle, reconnect/restart, and concurrent-state handling on the configured P1P; fixed routes are C4-audited, but this remains historical evidence for that printer only |
| Elegoo SDCP v3 | `printing` → `paused` | `paused` → `printing` | `printing`/`paused` → `idle`/`finished`/`error` | supervised CC1 evidence for the exact model/firmware; separate owner acknowledgement remains required |
| Moonraker | `printing` → `paused` | `paused` → `printing` | `printing`/`paused` → `idle`/`finished`/`error`/`cancelled` | supervised evidence for the exact observed Klipper identity/firmware; separate owner acknowledgement remains required |

The offline contract itself has no transport, endpoint, payload, UI, or
capability projection. It cannot enable a printer. The Bambu route bridge is a
separate operation-only audit integration: it maps the inherited fixed MQTT
methods into the ledger while preserving their existing MQTT routes and HTTP
response bodies.

The C4.1b deterministic baseline also pins the inherited Bambu pause, resume,
and stop wire messages to their exact fixed MQTT command names and QoS. Its
mock-only coverage proves a disconnected client publishes nothing. The owner
has separately confirmed lifecycle, reconnect/restart, and concurrent-state
handling for their configured P1P; that historical confirmation is limited to
that printer and does not generalize. Bambu does not use the isolated-source
owner-acknowledgement gate, but every bridged request now receives an
operation-only audit record.

For the dormant non-Bambu adapters, a transport-level acknowledgement alone is
never a completed operation: both must wait only for a bounded fresh,
read-only, internally consistent status transition to the matching success
state. A timeout, disconnect, stale observation, contradictory job field, or
non-success HTTP response is unconfirmed or unavailable. This changes no
source's default-off activation state.

A fresh ready snapshot's authoritative state can reconcile an operation even
when an SDCP status update omits `PrintInfo`; the absence of a current job
object is not itself stale data. The same rule applies to operation
availability. Retained snapshots remain ineligible, and a present job field
must still agree with the authoritative snapshot state.

The deterministic C4.1c coverage exercises the Moonraker wait directly: an
old printing state cannot confirm pause, only a following paused observation
can; a timeout or a stopped connection fails closed. These in-memory tests do
not open a socket or invoke the adapter's POST path.

The terminal lists above are acceptance criteria for a future fresh status
observation, not claims that a platform will reach every listed state. A
missing, stale, conflicting, or disconnected observation remains unconfirmed.

The supervised Moonraker session confirmed the fixed pause and resume endpoint
transitions and observed the fixed cancel endpoint returning the terminal
`print_stats.state` value `cancelled`. The printer physically stopped at its
current position. C4 does not send a parking macro, G-code, or motion command:
safe parking is printer-configuration-specific and requires its own reviewed,
owner-approved motion/cancellation workflow. This observation improves the
closed reconciliation vocabulary only; it does not create a Moonraker owner
acknowledgement or generalize control to another configuration.

### C4.2 — owner acknowledgement, audit, and API activation

Implemented for the exact supervised CC1 evidence record only. An owner must
explicitly confirm the source after a fresh observation matches the validated
Elegoo Centauri Carbon `V0.4.0-o` model/firmware/operation set. The persisted
acknowledgement stores only source revision, normalized model/firmware, and the
three allowlisted operation names; it never stores an address, payload,
credential, raw response, or media. The acknowledgement is visible through
the source projection and is required both by the API route and the active
manager before a control capability can be projected or dispatched.

An endpoint/configuration revision change, disabled source, or application
restart clears the record. A reconnect that lacks a fresh exact identity, a
changed observed identity/firmware, stale observation, or failed
reconciliation removes the capability until the owner reviews it again.
The configured supervised Moonraker source now has an equivalent exact record:
normalized `Klipper` / `v0.10.0-31-gd5ee171`, restricted to the same three
fixed operations. A firmware, endpoint/configuration, status-freshness, or
restart change revokes availability. Bambu remains outside this isolated-source
acknowledgement path because its inherited routes have their own established
permission model; its fixed lifecycle operations are nevertheless recorded in
the common C4 ledger.

The common audit presentation must identify target, requested operation,
principal where authentication is enabled, request time, result, and a
non-sensitive error class. It must never store a protocol payload, API key,
private address, filename, or media.

### C4.3 — capability-gated Workshop controls

Expose exactly pause, resume, and cancel only after C4.2 is active for that
saved source. The control card must show the platform and named target, the
effect of the operation, confirmation, pending state, result, and an
accessible unavailable explanation. It must use the shared normalized
capability and cannot render stale retained job values as a command target.

No print start, upload, file selection, motion, temperature, light, fan,
camera, maintenance, emergency-stop, macro, console, or arbitrary-command UI
belongs to C4.

Implemented: the Elegoo and Moonraker cards provide a named-target owner
activation confirmation only when their exact current evidence is eligible;
otherwise they explain that controls are unavailable or revoked. The control
card appears only for fresh `job-control` capability and retains its own
operation confirmation and pending/result state.

### C4.4 — supervised hardware validation and release decision

The explicitly approved supervised sessions have individually confirmed pause,
resume, and cancel for the configured CC1 and Moonraker sources. The owner has
also confirmed prior lifecycle, reconnect/restart, and concurrent-state
handling for their configured P1P; that historical evidence is limited to that
printer. For the exact CC1
configuration, C4.4 additionally confirmed that pause is successful only
after fresh authoritative state, a read-only reconnect re-establishes a fresh
paused observation before the in-memory gate can reappear, a clean local
restart does not restore that activation, and a printer-side cancellation is
reconciled to idle with retained job data marked stale and no control
capability exposed. Goo Buddy sent no command for that concurrent cancellation.

For the exact Moonraker configuration, C4.4 confirmed that pause and resume
are successful only after fresh authoritative status, a read-only reconnect
independently establishes the exact paused identity/state, a temporary
status-client restart returns fresh printing state while the saved source has
no control activation, and a printer-side cancellation is reconciled to the
terminal `cancelled` state. Goo Buddy sent no command for that concurrent
cancellation and did not request files, camera/media, or other capabilities.

Bambu's historical owner confirmation completes the configured P1P C4.4
evidence for reconnect/restart and concurrent-state handling. It remains
strictly limited to that printer and does not establish a model-, firmware-, or
source-wide Bambu capability claim. Record only redacted results.

Successful validation changes the compatibility table for precisely that
platform/firmware/operation. It does not activate untested models or make
print submission available. Any new Bambu model, firmware, or source requires
its own evidence before making a lifecycle-control claim.

## Explicit exclusions

C4 excludes managed print submission (C5), every file action, slicing,
upload/download, print start, G-code, JSON-RPC escape hatches, SDCP command
tunnels, motion, heaters, fans, lights, maintenance, firmware, camera/media,
subnet discovery, and cloud control. A later milestone must establish each of
those separately.

## Evidence record required before activation

For each approved platform/firmware/operation combination, record:

- the reviewed protocol reference and redacted fixture/simulator coverage;
- the fresh state required before dispatch and the expected authoritative state
  after dispatch;
- timeout, duplicate-request, disconnect, and restart/reconciliation results;
- the explicit owner acknowledgement and audit semantics; and
- the date and outcome of the separately approved supervised validation.

Absent, malformed, stale, unauthenticated, unsupported, or inconclusive data
is unavailable—not a reason to retry a command or advertise a control.
