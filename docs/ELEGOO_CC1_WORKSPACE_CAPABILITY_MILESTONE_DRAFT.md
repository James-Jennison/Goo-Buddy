# Elegoo CC1 workspace capability milestone

**Status:** M1 read-only telemetry mapping is implemented with deterministic,
redacted fixtures. No additional hardware contact is part of this milestone.

## Evidence recorded 2026-08-09

The configured Centauri Carbon source was observed through one bounded,
read-only session using only the existing exact-host SDCP identity lookup,
WebSocket `ping`, Cmd 0, and Cmd 1. It was idle and returned nozzle, bed, and
chamber temperatures plus `CurrentFanSpeed` and `LightStatus.SecondLight`.
No raw SDCP frames, endpoint address, mainboard identity, filename, or camera
URL is retained by this adapter or recorded here.

The [OpenCentauri SDCP v3 reference](https://docs.opencentauri.cc/software/api/)
documents pushed status and attributes data, the FDM nozzle/bed/chamber
temperature and target fields, and Cmd 0/1 information refreshes. It also
documents substantially broader protocol features. Those features are not
evidence that Goo Buddy can safely present or use them.

## Capability decision

| Area | Evidence-backed status | Workspace decision |
| --- | --- | --- |
| Connection, model, firmware, and temperature readings | Current CC1 observation and the fixed status/attributes adapter. | Show in a read-only thermals panel. |
| Job state, progress, and layers | An idle CC1 retained prior-job counters despite not printing. | Project these only as `stale_job`; live progress/layers exist only for authoritative `printing` state. Tick values never become elapsed or remaining time. |
| Fan and chamber-light telemetry | The CC1 status shape included `CurrentFanSpeed` and `LightStatus.SecondLight`. | Show their observed, missing, unknown, or unsupported monitoring state without a control affordance. |
| Pause, resume, cancel | Not observed or exercised. | Do not advertise or surface a control. |
| Camera/video, files, history, CANVAS, position, UV LED, maintenance, configuration, motion, HTTP/media, RTSP, or G-code | No Goo Buddy evidence-backed read-only contract exists for these. | Explicitly unavailable; no request or UI route is added. |

## M0 — shared read-only workspace frame

Give the Elegoo source the same compact, rearrangeable individual-printer
workspace frame as Moonraker. Layout order is local to that printer and can be
reset. The initial panels are Thermals and Job status only. This uses the
existing local dashboard projection; it sends no additional SDCP command,
does not change the source configuration, and adds no printer action.

## M1 — stale job and environmental telemetry mapping

Deterministic fixtures cover the observed idle-after-job shape, active
printing, missing/unknown/unsupported environmental values, and unsupported
time estimates. The UI and API distinguish `job` from `stale_job`; a filename
is never retained. A paused, idle, finished, error, unavailable, or otherwise
non-printing state cannot render retained progress as current.

## Deferred work

Any camera, file, history, CANVAS, UV LED, HTTP/media, RTSP, temperature
target, motion, maintenance, or control capability needs its own approved
milestone, closed protocol adapter, deterministic negative coverage, and
supervised hardware evidence.
