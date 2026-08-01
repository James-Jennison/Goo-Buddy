# Elegoo SDCP v3 read-only connection

This is Goo Buddy's first usable Centauri/OpenCentauri integration. It is
opt-in, supports one source in this release, and is intentionally read-only.

## Confirmed protocol surface

OpenCentauri's SDCP v3 reference documents the WebSocket endpoint
`ws://{MainboardIP}:3030/websocket`, JSON envelopes with `Topic` and `Data`,
and pushed `sdcp/status/{MainboardID}` and
`sdcp/attributes/{MainboardID}` observations. Goo Buddy consumes only those
two pushed topic families. It reads the documented machine name, firmware,
machine state, nozzle/bed temperatures and targets, job state, layers, and
progress ratio fields.

The source is configured with a canonical RFC1918 IPv4 literal only. Goo
Buddy constructs the fixed endpoint internally; ordinary list, detail, and
dashboard responses redact it. The implementation does not log raw frames,
printer identifiers, filenames, or endpoint addresses.

Primary reference: [OpenCentauri SDCP WebSocket API](https://docs.opencentauri.cc/software/api/).

## Deliberate safety boundary

When enabled, Goo Buddy opens a WebSocket and waits for printer-pushed status
and attributes. It sends no SDCP request, command, G-code, application
heartbeat, discovery, credential, or control traffic. Consequently a newly
connected printer can remain in **waiting** until it emits an observation.

Only fresh, complete status plus attributes data is current. Stale,
disconnected, and invalid states retain the last valid snapshot separately and
the UI labels it as retained, never live. Camera, CANVAS, files, console,
maintenance and printer controls are unavailable; no capability is inferred
from an advertised protocol field alone.

## Lifecycle and persistence

`elegoo_sdcp_sources` is an additive, isolated migration. It does not alter
the legacy Bambu `printers` table or its serial/access-code contract. Its
rollback is safe: removing use of the feature leaves the additive table unused
and does not touch Bambu configuration. Endpoint changes cancel the active
session, increment the configuration revision, disable the source, and require
an explicit later enable action.

The transport uses bounded connection/handshake timeouts, a 128 KiB text-frame
limit, JSON/object validation, session IDs, per-topic deterministic ordering,
duplicate suppression, 45-second freshness, capped exponential reconnect
backoff with bounded jitter, and clean cancellation on disable, edit, delete,
or application shutdown. Its user-visible errors are sanitized categories
rather than exception or endpoint text.

## Known limits and non-assumptions

- No automatic discovery or physical-printer test is performed.
- No SDCP command, request, polling, or heartbeat is implemented.
- CANVAS is unavailable. There is no tested authoritative mapping here.
- Printer tick units are not interpreted. Progress is only a bounded ratio of
  observed current/total values; freshness uses local arrival time.
- Moonraker/Klipper transport remains planned and is not part of this feature.
