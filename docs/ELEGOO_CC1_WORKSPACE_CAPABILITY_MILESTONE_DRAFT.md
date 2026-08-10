# Elegoo CC1 workspace capability milestone

**Status:** M0 is ready for implementation. The CC1 has a current,
read-only temperature observation; print-job telemetry remains conditional on
a future fresh job observation and fixture evidence.

## Evidence recorded 2026-08-09

The configured Centauri Carbon source was read through Goo Buddy's local,
redacted dashboard projection only. It was enabled, `ready`, and `current`;
its live state was idle and its normalized capability set contained only
`temperatures`. No raw SDCP frames, endpoint address, mainboard identity,
filename, or camera URL was collected or retained for this review.

The [OpenCentauri SDCP v3 reference](https://docs.opencentauri.cc/software/api/)
documents pushed status and attributes data, the FDM nozzle/bed/chamber
temperature and target fields, and Cmd 0/1 information refreshes. It also
documents substantially broader protocol features. Those features are not
evidence that Goo Buddy can safely present or use them.

## Capability decision

| Area | Evidence-backed status | Workspace decision |
| --- | --- | --- |
| Connection, model, firmware, and temperature readings | Current CC1 observation and the fixed status/attributes adapter. | Show in a read-only thermals panel. |
| Job state, progress, and layers | Normalizer and deterministic fixtures support a bounded projection, but the CC1 has no current job observation. | Reserve a read-only job panel that truthfully states unavailable until a fresh valid job exists. |
| Pause, resume, cancel | Not part of this workspace increment. The current CC1 observation is idle. | Do not surface a control here. |
| Camera/video, files, history, CANVAS, position, fans, lights, maintenance, configuration, motion, or G-code | The protocol documentation mentions some of these, but this review provides no Goo Buddy capability evidence for them. | Explicitly unavailable; no request or UI route is added. |

## M0 — shared read-only workspace frame

Give the Elegoo source the same compact, rearrangeable individual-printer
workspace frame as Moonraker. Layout order is local to that printer and can be
reset. The initial panels are Thermals and Job status only. This uses the
existing local dashboard projection; it sends no additional SDCP command,
does not change the source configuration, and adds no printer action.

## M1 — conditional job projection validation

Before representing a live CC1 job as supported, add or confirm deterministic
fixtures for printing, paused, malformed, retained, and idle-after-completion
states. The UI must distinguish current from retained data and must never show
a filename or completed-job values as a current job. Hardware validation is a
separate, explicit approval.

## Deferred work

Any camera, file, history, CANVAS, temperature target, motion, maintenance,
or control capability needs its own approved milestone, closed protocol
adapter, deterministic negative coverage, and supervised hardware evidence.
