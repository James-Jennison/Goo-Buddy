# Local virtual FDM printer farm

This opt-in, deterministic compatibility environment is software-only. It is never started by Goo Buddy, never discovers devices, and binds every host listener to `127.0.0.1`.

Start it with `docker compose -f docker-compose.virtual-farm.yml --profile virtual-farm up --abort-on-container-exit`; stop it with `down`. It contains only a narrow Moonraker read-only simulator: fixed monitoring requests, camera metadata, and a fixed `gcodes` inventory. The inventory accepts only `GET /server/files/list?root=gcodes` and supplies deterministic relative display data; it has no file-transfer or control endpoint. Bambu and SDCP contract coverage is exercised by their existing Goo Buddy adapter fixtures; no proprietary protocol is guessed or exposed.

`virtual_farm/profiles.v1.json` is the versioned compatibility matrix. `simulated-contract-tested` means a real Goo Buddy boundary has deterministic contract coverage; `hardware-verified` requires reproducible committed hardware evidence; `deferred-research-required` means no safe, authoritative adapter contract exists; `unsupported` means deliberately unsupported. Simulation is not hardware validation and never controls a physical printer.

## Optional camera mode

Camera is off by default. Fixture mode is deterministic and localhost-only: `docker compose -f docker-compose.virtual-farm.yml --profile virtual-farm-camera up`. It advertises a clearly labelled virtual-farm camera whose snapshot and stream paths both return a fixed JPEG.

USB mode is manual workstation validation only. Set one explicit device, for example `export VIRTUAL_FARM_VIDEO_DEVICE=/dev/video0`, then run `docker compose -f docker-compose.virtual-farm-camera-usb.yml --profile virtual-farm-camera-usb up`. The USB-only Compose file maps exactly that device and starts the simulator in V4L2 mode. For each snapshot or stream request it invokes local `ffmpeg` with that mapped V4L2 device and returns the resulting JPEG; it never probes or selects a camera itself and never contacts a printer. The virtual-farm image contains only `aiohttp` and `ffmpeg` for this isolated simulator.

The selected device must be accessible to Docker (including the host's video-device permissions). A missing, busy, inaccessible, unsupported, disconnected, frame-lost, or failed-start device returns a local HTTP 503 camera-unavailable response instead of fixture or stale imagery. The simulator process listens on the container interface so Docker can forward its port, but Compose publishes every host port only on `127.0.0.1`. USB mode is excluded from CI. Shut either mode down with `docker compose -f <its-compose-file> down`; all published ports are loopback-only.
