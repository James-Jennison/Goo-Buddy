# C4 — cross-platform job lifecycle controls

**Status:** C4.0 is implemented for Elegoo SDCP v3 and Moonraker as a
default-off gate; C4 remains otherwise not enabled. This is the implementation
and validation plan for pause, resume, and cancel across every supported
printer family: Bambu Lab, Elegoo SDCP v3, and Klipper through Moonraker.

This plan does not authorize printer contact or a control action. A separate,
explicit approval is required for each supervised hardware-validation session.
Until a platform and operation meet its activation gate, Goo Buddy continues to
present that platform as monitoring-only and must not send a job command.

## Current baseline

Goo Buddy already contains useful *implementation scaffolding*, not current
control claims:

| Platform | Existing implementation evidence | Current product decision |
| --- | --- | --- |
| Bambu Lab | Inherited MQTT pause, resume, and stop paths plus established printer and queue regression coverage. | Keep its existing behaviour governed by the inherited contract. It is not proof that a non-Bambu source can use those paths, and it has not yet been incorporated into the shared C4 ledger and reconciliation model. |
| Elegoo SDCP v3 | A closed private mapping for pause, cancel, and resume exists in code, with deterministic fixtures. The CC1 observation was read-only and did not observe or exercise control. | Monitoring-only. `job-control` must not be advertised, surfaced, or dispatched. The command mapping alone is not capability evidence. |
| Moonraker | A closed private mapping for fixed bodyless print-job endpoints and deterministic fixtures exists in code. The current Moonraker source contract is read-only and no supervised control observation has occurred. | Monitoring-only. `job-control` must not be advertised, surfaced, or dispatched. A documented endpoint alone is not hardware-validation evidence. |

The shared non-Bambu command record intentionally admits only `pause_job`,
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

Bambu's inherited operational paths remain unchanged in this first slice;
C4.1 must map them into an equivalent policy and reconciliation contract
before Goo Buddy treats any result as a cross-platform control capability.

Deterministic tests prove that a copied API request, a stale observation, an
enabled monitoring source, or a dormant adapter cannot bypass the policy.
This slice adds no owner-facing enable switch until the platform-specific
evidence slice has been reviewed.

### C4.1 — platform evidence and reconciliation contracts

For each platform and each operation, record the exact outbound vocabulary,
accepted acknowledgement/status transition, bounded timeout, and safe outcome
when the transport disconnects or the printer changes state concurrently.

- **Bambu Lab:** map the inherited MQTT methods and printer/queue state
  transitions into the C4 audit and reconciliation model without changing
  existing Bambu behaviour.
- **Elegoo SDCP v3:** obtain redacted, supervised evidence for the exact
  command and expected status transition. The prior CC1 read-only evidence
  does not qualify. Preserve the established stale-job rule while validating
  current state.
- **Moonraker:** obtain redacted, supervised evidence for each fixed endpoint
  and expected `print_stats` transition on the chosen Klipper configuration.
  Do not widen the existing fixed request vocabulary or add JSON-RPC/G-code.

Each platform remains disabled for every operation that lacks this contract.

#### C4.1a — offline reconciliation baseline

The first C4.1 implementation slice records a closed, non-dispatching
reconciliation contract for all three supported printer families. It is a
source-of-truth for the pre-command and successful post-command state that a
future activation must observe:

| Platform | Pause | Resume | Cancel | Evidence status |
| --- | --- | --- | --- | --- |
| Bambu Lab | `RUNNING` → `PAUSE` | `PAUSE` → `RUNNING` | `PREPARE`/`SLICING`/`RUNNING`/`PAUSE` → `IDLE`/`FINISH`/`FAILED` | inherited regression coverage; not yet C4-audited or hardware-validated |
| Elegoo SDCP v3 | `printing` → `paused` | `paused` → `printing` | `printing`/`paused` → `idle`/`finished`/`error` | dormant adapter only; no control evidence |
| Moonraker | `printing` → `paused` | `paused` → `printing` | `printing`/`paused` → `idle`/`finished`/`error` | dormant adapter only; no control evidence |

The contract has no transport, endpoint, payload, UI, API activation, audit
write, owner-facing switch, or capability projection. It cannot enable a
printer. The normalized helper deliberately excludes Bambu from the non-Bambu
adapter path; the table maps Bambu's inherited state model without changing its
existing MQTT routes.

The C4.1b deterministic baseline also pins the inherited Bambu pause, resume,
and stop wire messages to their exact fixed MQTT command names and QoS. Its
mock-only coverage proves a disconnected client publishes nothing. This is
implementation evidence, not a live-printer acknowledgement or a claim that
the route now satisfies C4 owner-acknowledgement and audit gates.

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

### C4.2 — owner acknowledgement, audit, and API activation

After C4.1 approval, add an explicit per-source acknowledgement scoped to the
validated platform/firmware/operation set. It must be visible in source status
without exposing endpoint, credentials, payloads, or raw responses. A config
revision change, disabled source, reconnect ambiguity, or failed
reconciliation removes availability until the owner reviews it again.

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

### C4.4 — supervised hardware validation and release decision

Use a non-production printer for one explicitly approved, supervised session
per platform/firmware/operation. Validate pause, resume, and cancel
individually; include lost acknowledgement, reconnect, restart, and a
concurrent state-change scenario where safe. Record only redacted results.

Successful validation changes the compatibility table for precisely that
platform/firmware/operation. It does not activate untested models or make
print submission available. The current offline/printer-repair period is an
appropriate time for C4.0 and deterministic C4.1 work, not for claiming or
exercising control.

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
