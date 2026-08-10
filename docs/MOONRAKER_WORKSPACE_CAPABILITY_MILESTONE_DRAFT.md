# Proposed Moonraker workspace capability milestone

**Status:** M0–M3 are implementation-complete and fixture-validated.
Hardware validation and release remain separate approvals. M4 retains its
individual gate below.

## Outcome

Extend the Klipper via Moonraker workspace from a monitoring dashboard into a
capability-gated operator workspace inspired by established Klipper frontends.
The UI must show only features that Goo Buddy has independently validated for
that source. It must never turn into a generic Moonraker, HTTP, JSON-RPC, or
G-code console.

This proposal extends, but does not replace, the existing
[multi-platform maturity gate](MULTI_PLATFORM_MATURITY.md). That gate already
defines the closed, bodyless pause/resume/cancel command contract. This draft
does not broaden that contract by implication.

## Scope boundaries

| Workspace area | Proposed first increment | Explicitly excluded |
| --- | --- | --- |
| Jobs | Read-only display of the already validated fixed-root G-code inventory, current job, and selected-file metadata. | Start, queue, upload, download, delete, move, copy, archive, or arbitrary path browsing. |
| G-code Preview | Metadata and trusted thumbnail preview for a file that is already present in the bounded inventory. | Downloading or executing raw G-code, browser-selected paths, rendering arbitrary file bytes, or mutation-triggering metadata scans. |
| Console | Bounded cached history, with filters and copy-to-clipboard only. | Live command input, replay, `printer.gcode.script`, `M112`, or any other raw G-code route. |
| Thermals | Current temperatures and history from the closed object subscription. | Changing heater targets, fans, lights, PID, or configuration. |
| Tools | Read-only toolhead, homing, and motion telemetry only if a separately fixed object subset is validated. | Movement, homing, extrusion/retraction, motor enable/disable, pressure advance, or speed/flow changes. |
| Macros | A visible unavailable state only. | Listing, inspecting, or executing arbitrary macros. |
| Job controls | Surface the existing closed pause/resume/cancel operations only after their existing maturity-gate evidence is complete. | Print start and all other job operations. |

## Delivery stages

### M0 — dashboard frame

The responsive desktop grid may reserve the panel locations shown in the
workspace design: Tool telemetry and macros on the left; Jobs and G-code
Preview on the right. A reserved panel may not resemble an enabled control and
must state that the capability is unavailable. This stage changes no Moonraker
request, source configuration, command, or persisted capability.

### M1 — read-only job detail

Expand the existing fixed `gcodes` inventory into a selected-file detail
panel. The backend may request Moonraker's documented G-code metadata endpoint
only when all of the following hold:

1. the selected path exactly matches an entry in the current, validated,
   fixed-root inventory;
2. the source remains enabled and has a fresh validated observation;
3. the request uses the already-derived private origin, no redirects, a fixed
   endpoint, bounded encoded path, protected API key header, and a strict
   response-size/type/schema limit; and
4. only an allowlisted metadata projection reaches the browser.

The projection is limited to display-safe slicer name/version, dimensions,
estimated time, filament totals, layer/nozzle details, and bounded thumbnail
metadata. The UI must label unavailable or malformed metadata as unavailable;
it may not infer values from raw G-code.

### M2 — trusted thumbnail preview

Add a token-protected backend thumbnail proxy only for a thumbnail returned by
the validated M1 metadata projection. The path must remain bound to the
selected cached inventory record, use a fixed local `gcodes` root, reject
redirects, limit MIME type and bytes, and never expose a Moonraker URL or API
key. This is a thumbnail preview, not a raw G-code download or a G-code parser.

A true layer-by-layer G-code viewer is deferred until a separate design proves
bounded acquisition, parser isolation, resource limits, cancellation, and a
safe error model for untrusted file content.

### M3 — read-only tool telemetry

Completed with the documented `toolhead.extruder` and `toolhead.homed_axes`
fields from Moonraker's [Printer Objects](https://moonraker.readthedocs.io/en/latest/printer_objects/)
reference. The WebSocket query/subscription now names every field used by Goo
Buddy, object discovery intersects locally, and status messages containing
unknown objects or fields are discarded before status normalization. The
workspace shows the active configured tool and homed axes only; it exposes no
position, motion, homing, configuration, or physical operation.

### M4 — closed job controls in the workspace

Expose only the existing `pause_job`, `resume_job`, and `cancel_job` operations
when the multi-platform maturity gate's automated and supervised validation
requirements are met for the selected Moonraker configuration. The UI must use
the existing permission, confirmation, idempotency, audit, timeout, and status
reconciliation model. It must not add print start.

### Deferred milestone — macros and physical tools

Macros, motion, homing, extrusion, heater/fan targets, and similar physical
actions require their own explicit design and approval. A future proposal must
define an operation enum, an owner-approved per-source allowlist, risk-specific
confirmation, a fixed protocol adapter, audit events, idempotency and
reconciliation rules, deterministic simulator coverage, and supervised
hardware evidence. It may not pass macro text, G-code, coordinates, speeds,
temperatures, or a method/path from the browser to Moonraker.

## Required evidence and gates

- Moonraker API evidence for every endpoint and field, pinned in the change
  documentation. Relevant current references are [File Management](https://moonraker.readthedocs.io/en/latest/external_api/file_manager/)
  and [Printer Administration](https://moonraker.readthedocs.io/en/latest/external_api/printer/).
- Contract tests proving the request vocabulary remains closed; negative tests
  for paths, traversal, redirects, host changes, unsupported content, stale
  selections, oversize bodies, and user-provided protocol data.
- Deterministic redacted Moonraker fixtures for valid, absent, malformed, and
  adversarial responses; no production source, credential, raw payload, or
  file content in fixtures.
- API, frontend, permission, token, accessibility, and migration tests for
  each visible capability and unavailable state.
- `ruff check` and `ruff format --check` from `backend/`, plus the full local
  gate before a candidate is presented for hands-on validation.
- Explicit, supervised hardware validation before any new capability becomes a
  supported claim. No implementation test may contact a physical printer
  without that separate approval.

## Approval record and remaining decisions

M0–M3 were approved for staged implementation and have completed automated
fixture validation. M2 accepts only a metadata-derived, fixed-root thumbnail
reference; it proxies bounded PNG, JPEG, or WebP bytes through Goo Buddy with
no redirects and a browser image-stream token. This is not approval to contact
a physical printer, release, or represent the feature as hardware-validated.
M4 and the deferred physical-action milestone retain their individual approval
and evidence gates.
