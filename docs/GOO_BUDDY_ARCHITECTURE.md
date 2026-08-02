# Goo Buddy architecture

## Foundation and licensing

Goo Buddy is an AGPL-3.0 derivative fork of
[Bambuddy](https://github.com/maziggy/bambuddy). Bambuddy's complete history,
`LICENSE`, notices, and attribution remain in this repository. Goo Buddy does
not imply endorsement by Bambuddy or its maintainers.

[Goo-Buddy-Proto](https://github.com/James-Jennison/Goo-Buddy-Proto) is the
preserved TypeScript protocol/dashboard prototype. It is a reference for safety
and presentation concepts, not a source of mechanically copied implementation.

## Driver boundary

`backend.app.drivers` is a deliberately read-only, capability-based observation
boundary. A driver reports a normalized identity, state, explicitly observed
temperatures and job data, freshness phase, and an explicit current or retained
snapshot. A capability is never granted from a model name. Missing or ambiguous
fields remain unavailable.

The first boundary is intentionally adjacent to—not a rewrite of—Bambuddy's
existing `PrinterManager` and Bambu MQTT/FTP services. `BambuStateAdapter`
passively projects an already cached Bambu state, so existing Bambu behavior,
commands, storage, routes, and migrations remain unchanged.

## Sources

| Source | Initial role | Status |
| --- | --- | --- |
| Bambu | Existing Bambuddy MQTT/FTP integration, passively adaptable to the observation contract | Unchanged |
| Elegoo SDCP v3 | Stock and OpenCentauri read-only observations | Manual, opt-in transport with a closed ping/Cmd 0/Cmd 1 information allowlist |
| Moonraker | Klipper sources exposing Moonraker | Manual, opt-in alpha monitor with fixed HTTP discovery and closed object query/subscribe allowlist |

The Elegoo source accepts manual canonical-private-IPv4 configuration and
normalizes synthetic or SDCP status and attributes payloads. Its transport is
restricted to the documented text `ping`, Cmd 0 status-refresh, and Cmd 1
attributes-refresh operations; it has no generic command surface, G-code,
controls, files, camera, CANVAS fabrication, or discovery scanning. The
source has isolated persistence and models waiting, ready, stale,
disconnected, and invalid phases. A snapshot
is current only while fresh; otherwise the last valid snapshot is explicitly
retained and labeled with its retention reason. Observations are session-bound:
superseded and out-of-order observations fail closed.

Moonraker follows the same isolated-source model. It accepts a manual private
IPv4 literal, explicit port, HTTP/HTTPS selection, and an optional protected
API key. Fixed HTTP discovery (`/server/info`, `/printer/objects/list`) is
followed by only `printer.objects.query` and `printer.objects.subscribe` on
the fixed WebSocket path. Its object selection is intersected with a local
temperature/job-status allowlist. It has no generic JSON-RPC, G-code, file,
or control surface; endpoint or credential edits cancel a session and require
explicit re-enablement.

## Platform target

Raspberry Pi ARM64 is a primary Goo Buddy target. The driver foundation is pure
Python and architecture-neutral. Goo Buddy's independently published container
contract builds native AMD64 and ARM64 images, while preserving the inherited
legacy data-volume identifiers only where upgrades require them. See
[container distribution and verification](CONTAINER_BUILDS.md) and the
[Raspberry Pi installation guide](RASPBERRY_PI_FIRST_RUN.md). Publication does
not deploy Goo Buddy or contact a printer.
