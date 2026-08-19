# Moonraker C5 managed-submission evidence

**Status:** official-documentation review plus an offline-only deterministic
serializer/receipt/reconciliation contract. This is not an enabled Goo Buddy
capability. No configured Moonraker source was contacted, and no file or print
request was sent.

## Evidence examined

Moonraker's official [File Management API](https://moonraker.readthedocs.io/en/latest/external_api/file_manager/)
documents `POST /server/files/upload` as `multipart/form-data`. It identifies
`gcodes` as the default and permitted print-artifact root. A client can include
a SHA-256 `checksum`; the server compares it after upload and reports a
mismatch as HTTP 422. A successful upload returns HTTP 201, an `item` with its
root-relative `path`, and a `Location` header.

The same reference offers two optional conveniences that Goo Buddy must not
use: `path` can address a subdirectory (and may cause it to be created), and
`print=true` can start or queue a print as part of the upload. Goo Buddy must
send neither field. This preserves a bounded, single-target flow and prevents
an upload acknowledgement from being mistaken for a controlled start.

Moonraker's official [Printer Administration API](https://moonraker.readthedocs.io/en/latest/external_api/printer/)
documents the separate fixed HTTP request
`POST /printer/print/start?filename=<gcode-relative-path>`. The filename is
required and is relative to the G-code folder. The response is `"ok"`; its
documentation also states that Klippy must be connected and, in many cases,
ready. JSON-RPC is documented by Moonraker too, but is not a C5 transport
option for Goo Buddy.

## Candidate bounded sequence

Subject to future source-scoped owner acknowledgement and implementation
review, a source may eventually use only this sequence:

1. Validate an immutable local artifact as a supported G-code input and bind
   its SHA-256 to the closed C5 submission intent.
2. Upload that exact byte sequence through the fixed multipart endpoint to
   `gcodes`, without `path` and with `print=false`/omitted.
3. Require a successful upload response whose root is `gcodes`, whose returned
   filename is safe under Goo Buddy's future normalization rule, and whose
   checksum verification did not fail.
4. Make exactly one separate fixed HTTP start request using the returned
   G-code-relative filename.
5. Reconcile the result through a fresh authoritative `printing` observation
   whose job identity agrees with that returned filename.

Neither HTTP 201 nor the `"ok"` start acknowledgement may be presented as a
confirmed print without that final observation. A lost acknowledgement, target
state change, disconnect, timeout, mismatch, malformed response, or failed
reconciliation must fail closed and must not cause an automatic start retry.

## Unresolved safety blockers

The documentation review does not establish the configured source's
authorization configuration, accepted artifact restrictions, maximum upload
size, collision/overwrite behavior, concurrent-job behavior, filesystem free
space, or a recovery/cleanup contract for a partially completed upload. It
also does not prove that this printer/firmware will accept a selected Goo Buddy
artifact or that the returned job identity will match later status telemetry.

No C5 submission integration exists. The bounded inventory/preview and
separately gated C4 lifecycle work must not be repurposed to enumerate
directories, download/delete/move files, read Moonraker configuration, use
JSON-RPC, issue generic G-code, or expose file or start controls. No camera or
media capability follows from this evidence.

## Implemented offline boundary

`backend.app.submission.moonraker` models this candidate flow without a
network client, file reader, API route, UI, capability projection, or printer
command. Its deterministic tests enforce safe `.gcode` input basenames, a
content-addressed remote basename, `gcodes`-only upload, client SHA-256,
rejection of `path` and upload-triggered printing, exact success receipt
validation, a single claimed start request, and fresh matching `printing`
reconciliation. A timeout, conflicting job, or stale observation becomes
`unconfirmed`; the contract provides no retry path.

The C5.2 source activation boundary is present but remains unavailable: a
source can only retain owner consent when its current observed identity matches
an explicit C5.3 supervised-evidence record. There are no such records today.
The acknowledgement status is deliberately separate from both read-only
monitoring and C4 lifecycle control, and cannot be used to expose an upload or
start operation.

## Dormant C5.3 transport preparation

The Moonraker manager now contains a private, test-only dispatch seam. It is
not reachable from the API, UI, source configuration, or capability model. It
accepts already-resolved in-memory bytes only, verifies their exact size and
SHA-256 against the closed intent, and can issue no request unless a future
source has a fresh matching C5 acknowledgement. Its deterministic peer accepts
only the documented multipart upload and the following fixed HTTP start path.
It never reads a file, retries either physical operation, uses JSON-RPC, or
accepts a filename/path/URL/body from a caller.

This preparation does not resolve an artifact from Goo Buddy's library or
archive storage. Choosing the first supported artifact source and defining its
path-containment, managed-versus-external, hash-verification, and ownership
rules is a separate review before any live session. A C5.3 hardware validation
still requires explicit owner approval for each physical upload and start.

## Required next bounded milestone

Before adding an adapter or UI, review the offline contract's source-scoped
activation, permission, audit-persistence, and request-dispatch boundary.
Then a distinct owner-approved C5.3 hardware session with a disposable
artifact is required to validate upload and start behavior for a specific
source/firmware. Until then `job-submission` stays unavailable.
