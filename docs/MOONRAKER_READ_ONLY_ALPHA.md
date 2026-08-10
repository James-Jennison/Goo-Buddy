# Moonraker/Klipper read-only alpha

Goo Buddy's Moonraker integration is a manual, opt-in monitoring source. It
accepts only a canonical RFC1918 IPv4 literal, an explicit port (default
`7125`), and HTTP or HTTPS. It derives the following fixed endpoints itself:
`/server/info`, `/printer/objects/list`, `/server/webcams/list`,
`/server/files/list?root=gcodes`, and `/websocket`. Redirects, URLs,
hostnames, queries, fragments, proxies, and alternate paths are rejected.

An optional API key is held by the existing protected-secret mechanism and is
used only in the `X-Api-Key` request header. It is never returned by source,
list, dashboard, or validation-error APIs. Neither the address nor raw
Moonraker data is logged.

## Closed monitoring surface

The HTTP GET allowlist is `/server/info`, `/printer/objects/list`, the
documented Moonraker webcam inventory endpoint `/server/webcams/list`, and
the documented fixed-root G-code inventory endpoint
`/server/files/list?root=gcodes`. The G-code response is capped at 100 entries
and validated as relative display data; Goo Buddy never accepts a file name,
path, root, filter, or query from the browser. It shows no inventory when the
fixed request fails or is malformed. The
WebSocket JSON-RPC allowlist is exactly:

- `printer.objects.query`
- `printer.objects.subscribe`

The locally selected object set is limited to `webhooks`, `print_stats`,
`virtual_sdcard`, `display_status`, `toolhead`, `extruder`, `heater_bed`, and
`chamber`, and is intersected with the server's discovered list. No generic
JSON-RPC API exists in Goo Buddy.

In particular Goo Buddy cannot serialize `printer.gcode.script`, print start,
pause/resume/cancel, emergency stop, heating, fans, lights, motion, homing,
extrusion, file download/upload/delete/move, G-code execution, restart/update,
or machine/service operations.

Validated status result/notification data is the sole inbound liveness signal.
Malformed, unknown, binary, oversized, or unsupported-object frames do not
refresh it. A session closes after 45 seconds without validated inbound status;
reconnect backoff is capped. Disable, delete, endpoint/API-key replacement,
and shutdown cancel the active task. Transport or secret edits always leave a
source disabled until the owner explicitly enables it again.

## Alpha compatibility and privacy

The dashboard shows only validated Klipper/Moonraker state, available
temperatures, safe job display name, progress, current/total layers when
reported in `print_stats.info`, elapsed duration, and a progress-derived
remaining estimate when both input values are present. It labels retained
data separately from current data. When Moonraker reports an enabled webcam
with a same-origin relative JPEG snapshot path, Goo Buddy may expose one
bounded, token-protected snapshot preview. If that endpoint fails, it may
extract one bounded JPEG frame from the webcam's same-origin MJPEG stream.
For Mainsail installations that place the webcam on a separate local proxy,
the owner may explicitly configure its HTTP(S) port and a narrow `/webcam/`
stream or snapshot path. The proxy host is never configurable or returned:
Goo Buddy always derives it from the saved private printer address, discards
cache-busting query values, follows no redirects, and never forwards the
Moonraker API key to the camera proxy.
The camera URL itself is never returned to the browser, redirects and external
authorities are rejected, and the preview does not imply streaming, camera
control, files, console, uploads, or maintenance support. Every other camera
shape remains unavailable.

The inventory is a convenience for operator awareness, not file management:
it does not imply browsing, download, upload, deletion, printing, metadata,
thumbnails, or any other file capability.

Moonraker API reference: [File management](https://moonraker.readthedocs.io/en/latest/external_api/file_manager/), [Server administration](https://moonraker.readthedocs.io/en/latest/external_api/server/), [Printer objects](https://moonraker.readthedocs.io/en/latest/printer_objects/), and [WebSocket/API overview](https://moonraker.readthedocs.io/en/latest/external_api/introduction/).

For an alpha report, provide Goo Buddy version, connection phase, and a
redacted description of the available fields. Do not publish raw payloads,
API keys, access codes, serials, MAC addresses, filenames, paths, or network
addresses.
