# Elegoo SDCP v3 read-only connection

This is Goo Buddy's opt-in Centauri/OpenCentauri monitoring integration. It
supports one explicitly registered source in this release and exposes only
evidence-backed read-only telemetry. It does not advertise printer controls.

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
status, attributes, or response topic. Each connection makes one bounded
initial liveness exchange. An exact text `pong` or a structurally valid inbound
status, attributes, or Cmd 0/Cmd 1 response establishes liveness; no other
topic, command, or malformed envelope does. After that, Goo Buddy sends the
same documented Cmd 0/Cmd 1 information pair every 15 seconds, well inside the
separate 45-second no-valid-inbound-traffic deadline. This supports printers
that only answer requests while retaining the fail-closed deadline when no
validated response arrives. It does not introduce a heartbeat loop or any new
SDCP command. Disable, edit, delete, reconnect, and shutdown cancel the active
session.

Only fresh, complete status plus attributes data is current. Stale,
disconnected, and invalid states retain the last valid snapshot separately and
the UI labels it as retained, never live. SDCP may retain prior job counters
while its authoritative state is idle or otherwise non-printing; Goo Buddy
projects those only as `stale_job`, never as a current print. Tick fields have
no approved time conversion, so elapsed and remaining time are unsupported.
Observed fan and chamber-light fields remain telemetry only. Camera, CANVAS,
files, console, media, maintenance, and all printer controls are unavailable
or not evidenced; no capability is inferred from metadata alone.

## Owner-configured discovery boundary

Discovery is separately disabled by default. An owner with printer-management
authority must save and acknowledge exactly one canonical RFC1918 IPv4 CIDR.
Only `/24` through `/30` are accepted; public, loopback, link-local,
multicast, malformed, non-canonical, and broader networks are rejected.

An explicitly enabled scan sends exactly `M99999` to that CIDR's calculated
IPv4 broadcast address on UDP port `3000`, with two bounded receive windows,
an 8 KiB response cap, response validation, and identity deduplication. It
does not enumerate hosts, select interfaces, resolve names, use ARP, scan
ports, or contact an address that did not respond. Each valid responder may
receive one bounded WebSocket observation using only `ping`, Cmd `0`, and Cmd
`1`; it is classified as observed, unavailable, or error without persistence
or a reconnect loop. Candidates are never enabled automatically. The existing
manual source creation and acknowledgement step is required before any
candidate becomes a source.

This limited broadcast exception does not authorize HTTP/media probing,
directory or file operations, RTSP/MJPEG negotiation, camera activation or
frame retrieval, credentials, cloud APIs, or any control command. Future
file/media, video, and control work requires a separately approved milestone
with an exact documented contract, fixture coverage, and hardware evidence
that does not exercise an unsafe operation.

## Lifecycle and persistence

`elegoo_sdcp_sources` is an additive, isolated migration. It does not alter
the legacy Bambu `printers` table or its serial/access-code contract. Its
rollback is safe: removing use of the feature leaves the additive table unused
and does not touch Bambu configuration. Endpoint changes cancel the active
session, increment the configuration revision, disable the source, and require
an explicit later enable action.

The transport uses bounded connection/handshake timeouts, a 128 KiB text-frame
limit, JSON/object validation, session IDs, per-topic deterministic ordering,
refreshed arrival timestamps for valid unchanged observations, 45-second
freshness, capped exponential reconnect backoff with bounded jitter, and clean
cancellation on disable, edit, delete, or application shutdown. Its
user-visible errors are sanitized categories rather than exception or endpoint
text.

## Known limits and non-assumptions

- No automatic discovery or unbounded physical-printer probing is performed.
  The only broadcast is the separately enabled, owner-bounded UDP/3000
  discovery exchange described above; only validated responders receive the
  one bounded SDCP observation exchange.
- Only the explicitly documented ping/Cmd 0/Cmd 1 observation operations are
  used by the monitoring transport; arbitrary SDCP commands are rejected
  before sending.
- CANVAS is unavailable. There is no tested authoritative mapping here.
- Printer tick units are not interpreted. Progress is only a bounded ratio of
  observed current/total values; freshness uses local arrival time.
- Moonraker/Klipper is a separate alpha read-only source; see
  [Moonraker read-only alpha](MOONRAKER_READ_ONLY_ALPHA.md). It does not
  broaden the Elegoo SDCP transport or its ping/Cmd 0/Cmd 1 allowlist.
