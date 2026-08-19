# Elegoo C4 supervised lifecycle-validation runbook

**Status:** draft; no hardware action is authorized by this document.

This runbook is for the future, explicitly approved validation of exactly one
saved Elegoo SDCP v3 source and exactly one lifecycle operation at a time. It
does not authorize discovery, HTTP, RTSP, media, file activity, print start,
motion, temperature, fan/light changes, maintenance, arbitrary SDCP commands,
or any action against another printer.

## Preconditions

Before each individual pause, resume, or cancel attempt, the operator must
confirm all of the following in the active task:

1. The exact saved Elegoo source and the single requested operation.
2. That the operator is physically present with the printer and can intervene
   using its normal local controls if needed.
3. That the job is a disposable, non-production validation print; it must not
   be a repair, calibration, unattended, or valuable print.
4. The printer model and firmware observed at the start of the session.
5. The source is connected and has a fresh authoritative state: `printing`
   for pause/cancel or `paused` for resume/cancel. Retained, stale, idle,
   finished, error, unavailable, or conflicting state fails closed.
6. The operator has explicitly approved that one action in the current task.

Missing evidence, a changed firmware/configuration, loss of connection, or a
contradictory job record ends the attempt. Goo Buddy must not retry a command
automatically.

## Bounded procedure

1. Capture the redacted pre-action observation: source label, model, firmware,
   authoritative state, and only the current job progress/layer fields needed
   to verify a transition. Do not capture private addresses, raw payloads,
   credentials, filenames, media, or protocol identifiers.
2. Reconfirm the displayed target and operation with the operator.
3. Issue the one fixed operation through Goo Buddy's existing closed Elegoo
   lifecycle adapter. No alternate command, retry, payload, or transport is
   permitted.
4. Wait only for the configured bounded confirmation period and an ensuing
   fresh SDCP status observation.
5. Record one of: `confirmed`, `unconfirmed`, `unavailable`, `error`, or
   `aborted-by-operator`. A transport acknowledgement alone is `unconfirmed`.
6. Stop the session after that operation. Pause, resume, and cancel are three
   separate approvals and sessions; a pause does not authorize a later resume
   or cancel.

## Expected evidence

| Operation | Required pre-state | Confirmation criterion |
| --- | --- | --- |
| Pause | `printing` | Fresh authoritative `paused` state |
| Resume | `paused` | Fresh authoritative `printing` state |
| Cancel | `printing` or `paused` | Fresh authoritative terminal `idle`, `finished`, or `error` state |

The existing CC1 read-only observation must continue to treat retained
progress/layer values as stale whenever the printer is not actively printing.
Elapsed and remaining time remain unsupported; SDCP tick values are not
converted for this validation.

## Abort and reporting rules

- A disconnect, timeout, stale observation, unexpected state, or operator
  concern is an immediate stop condition. Do not retry or issue a compensating
  command.
- Do not use cancel as a recovery mechanism for a failed pause or resume.
- Record only the minimal redacted outcome and state transition necessary for
  the C4 compatibility table. Do not store protocol frames, device identifiers,
  private endpoints, credentials, media, or G-code/file details.
- A successful result validates only that source model, firmware,
  configuration, and operation. It does not enable another operation, another
  source, print submission, files, camera/media, or any other controls.

## Redacted validation record

| Date | Platform / firmware | Operation | Outcome | Scope retained |
| --- | --- | --- | --- | --- |
| 2026-08-10 | Elegoo Centauri Carbon / `V0.4.0-o` | Pause | **confirmed** by the on-site operator after one fixed request; a subsequent fresh read-only status reported `paused`. The first audit result remains `unconfirmed` because that status omitted `PrintInfo`; the reconciliation contract was corrected afterward without replaying the command. | Pause only for this observed configuration. Resume and cancel remain unvalidated; the temporary source gate was restored to disabled. |
| 2026-08-10 | Elegoo Centauri Carbon / `V0.4.0-o` | Resume | **confirmed** after one fixed request: the adapter received its fresh matching `printing` transition, and the on-site post-check remained current `printing`. | Resume only for this observed configuration. Cancel remains unvalidated; the temporary source gate was restored to disabled. |
| 2026-08-10 | Elegoo Centauri Carbon / `V0.4.0-o` | Cancel | **confirmed** by the on-site operator after one fixed request; the adapter acknowledged the fresh terminal `idle` transition. Retained former-job fields remained stale rather than current. | Cancel only for this observed configuration; the temporary source gate was restored to disabled. |

No private address, device identifier, payload, filename, credentials, or media
was retained for this record.
