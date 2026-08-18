# Elegoo C5 managed-submission evidence

**Status:** documentation research plus one bounded CC1 read-only capability
observation. This is not an implementation contract and leaves Elegoo
submission unavailable.

## Evidence examined

The existing Goo Buddy SDCP integration already cites the
[OpenCentauri SDCP v3 API reference](https://docs.opencentauri.cc/software/api/)
for the Centauri Carbon. Its documented upload shape is a multipart HTTP POST
to the fixed SDCP service with a file part and transfer metadata: MD5,
verification flag, offset, transfer UUID, and total size. The same reference
documents one fixed SDCP print-start command carrying a filename and start
layer, response acknowledgement categories, and automatic status updates. It
also says transfers use chunks and documents a transfer-termination command.

This is useful protocol documentation, not CC1 hardware evidence. No request
was sent from this documentation review. The later approved observation used
the saved source connection details in memory without logging or persisting
them; no source configuration was changed, and no filename, address, response,
credential, or artifact content is retained here.

## CC1 read-only capability observation

One separately approved session used only the existing CC1 identity lookup,
WebSocket `ping`, and Cmd 0/1 status/attributes flow. Its attributes record
advertised file transfer as `advertised-not-exercised`, but did **not**
advertise G-code as a supported file type. `job-submission` remained absent
from the Goo Buddy projection.

This observation did not list files, contact an HTTP transfer surface, read a
file, transfer bytes, or send a start command. It establishes neither that a
transfer works nor that the current CC1 firmware accepts any C5 artifact.

## What it supports

Future review may consider only this narrow candidate sequence:

1. A validated local G-code artifact is transferred through the documented
   multipart service with an integrity value derived from its immutable bytes.
2. A separate fixed SDCP start request may name only the destination produced
   by that completed transfer.
3. Success must still be reconciled through a fresh, authoritative SDCP
   `printing` observation whose job identity is consistent with the submitted
   artifact.

Neither an HTTP success response nor a start acknowledgement is sufficient to
report a successful submission.

## Unresolved safety blockers

The reference does not yet establish all of the following for the configured
CC1 firmware:

- canonical safe destination and filename normalization rules;
- whether the multipart response proves a completed MD5 verification rather
  than request acceptance only;
- offset/chunk order, retry, and resume semantics;
- transfer UUID lifetime and idempotency across client reconnects;
- safe cleanup after partial transfer, including the exact relationship
  between termination data and a remote artifact;
- maximum size, accepted G-code subset, free-space rule, target-busy behavior,
  and start-layer restrictions;
- authoritative job identity needed to correlate a submitted artifact with a
  following `printing` state; and
- actual CC1 firmware compatibility with every documented request/response
  field.

The absent G-code advertisement is itself a hard compatibility blocker.
Therefore Goo Buddy must not serialize these requests, expose a submission
capability, use the file-list or deletion commands, or perform a live probe.

## Required next bounded milestone

Before C5.1 implementation, obtain evidence from a compatible printer/firmware
that explicitly advertises an accepted artifact type, then review its exact
destination, integrity, resume, cleanup, and start semantics. A future
read-only capability observation may use only an established status/attribute
path; it must not list files, initiate a transfer, start a print, or use a
cloud/vendor route.

Only after that observation and a reviewed contract resolving the blockers
above may Goo Buddy add deterministic offline serializers and fixtures. Actual
transfer or print-start validation remains C5.3 and requires a distinct,
per-step owner approval with a disposable artifact.
