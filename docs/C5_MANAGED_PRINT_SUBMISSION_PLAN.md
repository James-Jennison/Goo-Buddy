# C5 — cross-platform managed print submission

**Status:** C5.0 is implemented as a default-off contract and inert audit
schema. C5.1 has recorded documentation-only Elegoo transport evidence plus a
bounded CC1 read-only capability observation, and an offline-only Moonraker
upload/start request and response contract. The current CC1 advertises file
transfer but no compatible G-code artifact type; the Moonraker contract is not
connected to any source. C5.2 persists separate source-scoped submission
acknowledgement fields and a status-only acknowledgement boundary, but the
hardware-validated evidence registry is empty. No printer source may upload a
file or start a job.

C5 makes Goo Buddy capable of submitting a selected, already validated print
artifact to a named printer and reconciling the result. It applies to Bambu
Lab, Elegoo SDCP v3, and Klipper through Moonraker, but a capability is earned
per platform, protocol contract, firmware/configuration, and operation. This
plan does not authorize printer contact, file transfer, job start, discovery,
or a release.

## Current evidence boundary

| Platform | Existing Goo Buddy evidence | C5 decision |
| --- | --- | --- |
| Bambu Lab | The inherited queue, FTP transfer, and fixed MQTT start path are covered by existing regression suites. | Deferred to a future release by owner decision. Preserve its existing behaviour; do not bring it into the C5 common submission contract in this cycle. It is not evidence for another platform. |
| Elegoo SDCP v3 | The CC1 work establishes read-only UDP/WebSocket telemetry and job lifecycle operations only. The OpenCentauri SDCP v3 reference documents a candidate multipart transfer and fixed start command. A bounded CC1 attributes observation advertised file transfer but did not advertise G-code as a supported artifact type. | Submission remains unavailable. Do not guess beyond the documented shape, use vendor/cloud transfer routes, or send any file/start request before separate owner approval and compatible-artifact hardware evidence. |
| Moonraker | The official API documents a multipart upload to the `gcodes` root, optional SHA-256 verification, and a separate fixed HTTP print-start request that names a G-code-relative filename. Goo Buddy has bounded inventory/preview and separately gated C4 lifecycle-control work; none establishes configured-source authorization or hardware validation for submission. | Submission remains unavailable. The documented candidate is recorded in [Moonraker C5 submission evidence](MOONRAKER_C5_SUBMISSION_EVIDENCE.md); no upload, start, JSON-RPC, or G-code request is enabled. |

## C5 activation rules

An individual source may offer managed submission only when all of these hold:

1. A reviewed, platform-specific transport and start contract identifies the
   accepted artifact type, exact destination semantics, integrity signal,
   expected acknowledgement, and authoritative post-start observation.
2. The saved source has a separate explicit owner acknowledgement for file
   transfer and job start. Monitoring or C4 lifecycle-control acknowledgement
   is never sufficient. The default is disabled.
3. Goo Buddy has a bounded artifact reference, a named target, confirmation,
   caller permission, idempotency and audit record. It never accepts a raw
   printer path, arbitrary URL, protocol body, G-code, or unvalidated file.
4. A fresh authoritative observation establishes an eligible target state and
   confirms the expected job identity/state after dispatch. Missing, retained,
   stale, conflicting, or disconnected observations fail closed.
5. Deterministic adapter/API/UI tests pass, followed by a separately approved,
   supervised hardware validation for that platform/firmware/configuration.

## Delivery slices

### C5.0 — closed submission contract and fail-closed projection

Add a common, typed submission-intent and audit/reconciliation model without
transport dispatch. It must bind a selected local library/archive artifact to a
saved source revision and a named target; it must not contain a raw destination
path, URL, request body, protocol command, G-code, credentials, or media.

The normalized `job-submission` capability is absent by default. Existing
monitoring sources remain unable to show a submission UI or route. A changed
source configuration, disabled source, failed reconciliation, or reconnect
ambiguity removes availability until the owner reviews it again.

Implemented: the shared intent accepts only a local archive/library-file ID,
its SHA-256 content hash, a bounded display label for the selected target, the
saved source revision, driver, and an idempotency key. The audit schema mirrors
only those values and a closed lifecycle state; it has no file path, raw
filename, destination, URL, request body, credential, G-code, bytes, or
transport-command field. There is deliberately no C5 API route, UI, manager,
adapter dispatch method, network client, upload, or start request in this
slice. `job-submission` remains absent from every current driver projection.

### C5.1 — platform evidence and bounded transfer adapters

For each platform, document and test only its exact accepted artifact and
transport protocol. Verify size/format limits, filename normalization,
per-target serialization, timeout, retry/idempotency, partial-transfer cleanup,
integrity confirmation, and safe resume/recovery behaviour. A transport error
must never trigger a blind start retry.

- **Bambu Lab:** deferred to a future release. The eventual work must map the
  existing inherited FTP and MQTT behaviour into C5's common
  intent/audit/reconciliation rules without widening its wire contract.
- **Elegoo SDCP v3:** documentation-only evidence is recorded in
  [Elegoo C5 submission evidence](ELEGOO_C5_SUBMISSION_EVIDENCE.md). It
  identifies a candidate fixed multipart transfer and fixed start request but
  does not establish a safe destination, completion/integrity, resume, cleanup,
  idempotency, or CC1-firmware contract. The completed bounded CC1 observation
  also did not advertise G-code as a supported artifact type. No adapter,
  request serializer, transfer client, or start command may be added until a
  compatible-artifact observation and a reviewed bounded contract resolve
  those gaps.
- **Moonraker:** the exact documentation-only candidate is recorded in
  [Moonraker C5 submission evidence](MOONRAKER_C5_SUBMISSION_EVIDENCE.md).
  An offline serializer/receipt/reconciliation contract with deterministic
  fixtures now constrains the future adapter to the fixed multipart endpoint,
  `gcodes` root, a client-supplied SHA-256 checksum with server-side
  verification, and a separate fixed HTTP
  print-start request for the path returned by a verified upload. It must
  never use the upload endpoint's `print` shortcut, the optional directory
  path, JSON-RPC, generic G-code, or current read-only inventory support.
  Source-scoped owner acknowledgement and supervised hardware evidence remain
  required before a submission capability can be exposed.

### C5.2 — explicit owner activation and Workshop submission

After a platform's C5.1 contract is accepted, add source-scoped owner
acknowledgement, permission checks, target/plate/filament confirmation where
the evidence supports them, a non-sensitive audit record, and an accessible
Workshop submission flow. The UI must state the target, artifact, operation,
and pending/confirmed/unconfirmed outcome; it must not invent unavailable
material, plate, ETA, or camera information.

Implemented boundary: the isolated Elegoo and Moonraker source records carry
separate submission-acknowledgement fields bound to source configuration
revision, exact observed model/firmware, and a reviewed contract ID. Their
status API can state `not-evidenced`, `owner-acknowledgement-required`,
`acknowledged`, or `evidence-no-longer-current` without exposing a submission
capability. The only acknowledgement request accepts a boolean; it rejects
artifact names, paths, URLs, request data, and transport data. The evidence
registry is intentionally empty until C5.3, so the current endpoint always
fails closed and records no acknowledgement. Endpoint/configuration changes or
source disable revoke any persisted acknowledgement. There is no Workshop
submission UI, intent-creation API, dispatch route, file reader, or transport
client in this slice.

### C5.3 — supervised hardware validation

Validate one isolated, disposable artifact per platform/firmware/configuration
with the owner present. Confirm upload, integrity, exactly one start request,
post-start reconciliation, duplicate-request behaviour, target-busy handling,
and recovery from a lost acknowledgement. Record redacted results only.

Implemented preparation: Moonraker has a dormant manager method exercised
only by an in-memory peer. It accepts immutable bytes supplied by a future
resolver, verifies their size and SHA-256 against the C5 intent, emits only
the C5.1 multipart upload and separate fixed start request, and requires a
fresh matching `printing` job name. It cannot run from any API route, UI,
source configuration, or capability projection: the source acknowledgement
registry is empty and there is no artifact resolver. It retries neither an
upload nor a start after an unconfirmed outcome.

## Explicit exclusions

C5 excludes discovery, subnet scanning, arbitrary file browsing, download,
delete, move, cloud transfer, slicer command tunnels, generic JSON-RPC,
arbitrary G-code, motion, heaters, fans, lights, maintenance, firmware,
camera/media, and all automatic start or retry behaviour. Camera work belongs
to C6; pause, resume, and cancel remain governed by C4.

## Evidence required for future activation

Before a platform gains C5 capability, retain the reviewed protocol reference,
redacted deterministic fixtures, artifact validation and integrity contract,
owner acknowledgement/audit semantics, exact post-dispatch read-only
reconciliation rule, and supervised-validation result. Absent or incomplete
evidence means `unavailable`, never an inferred capability.
