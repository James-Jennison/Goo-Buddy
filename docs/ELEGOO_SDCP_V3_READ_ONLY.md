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

When enabled, Goo Buddy opens a WebSocket and consumes printer-pushed status
and attributes. The outbound surface is a closed, non-mutating allowlist:

- exact text heartbeat `ping`;
- Cmd `0` status refresh; and
- Cmd `1` attributes refresh.

Both information envelopes use the documented JSON shape: locally generated
outer/request UUIDs, empty `Data`, Unix-seconds `TimeStamp`, `From: 0`, and
`sdcp/request/{MainboardID}`. Their MainboardID is held in memory only. Goo
Buddy first obtains it through one exact-address UDP/3000 unicast `M99999`
identity lookup per explicitly enabled source before opening the fixed
WebSocket endpoint. It can also validate a matching identity from a pushed
status, attributes, or response topic. It never broadcasts, enumerates,
resolves names, or probes a subnet.

No other SDCP command, request payload, G-code, credential, file, history,
video, control, configuration, motion, lighting, fan, temperature, print, or
maintenance operation is serializable. Each connection makes one bounded
initial liveness exchange. An exact text `pong` or a structurally valid inbound
status, attributes, or Cmd 0/Cmd 1 response establishes liveness; no other
topic, command, or malformed envelope does. After that, a separate 45-second
no-valid-inbound-traffic timeout closes an idle session. No periodic heartbeat
cadence is inferred because the reference does not document one; a disconnect
creates a new session rather than a heartbeat loop. Disable, edit, delete,
reconnect, and shutdown cancel the active session.

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

- No broadcast discovery, automatic discovery, or unbounded physical-printer
  probing is performed.
- Only the explicitly documented non-mutating ping/Cmd 0/Cmd 1 operations
  above are implemented; arbitrary SDCP commands are rejected before sending.
- CANVAS is unavailable. There is no tested authoritative mapping here.
- Printer tick units are not interpreted. Progress is only a bounded ratio of
  observed current/total values; freshness uses local arrival time.
- Moonraker/Klipper transport remains planned and is not part of this feature.
