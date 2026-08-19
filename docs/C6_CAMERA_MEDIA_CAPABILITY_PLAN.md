# C6 — cross-platform camera and media capabilities

**Status:** Planned. C6 begins only with platform-specific evidence review;
it does not authorize camera contact, stream activation, media retrieval, or
storage.

C6 will provide a truthful camera experience across Bambu Lab, Elegoo SDCP v3,
and Klipper through Moonraker. Each platform earns a narrowly defined camera
capability independently. It is not enough for a model to commonly include a
camera or for a port to be reachable.

## Current evidence boundary

| Platform | Existing Goo Buddy evidence | C6 decision |
| --- | --- | --- |
| Bambu Lab | Goo Buddy retains its inherited, tested camera integration. | Preserve it while mapping its exact security and freshness behaviour into the common C6 contract. |
| Elegoo SDCP v3 | CC1 read-only observation did not evidence HTTP/media, RTSP, MJPEG, camera activation, or a stream description. | Camera is `not-evidenced`; do not probe a port, send stream-enable commands, retrieve frames, or render a camera UI. |
| Moonraker | The bounded read-only workspace work documents a same-origin, fixed JPEG preview path under its own evidence and safety controls. | Keep that limited contract separate until C6 reviews its freshness, proxy, authentication, and stream semantics. It does not establish generic camera access. |

## C6 activation rules

A camera feature is available only after a reviewed protocol contract defines
the exact source type (snapshot or stream), authentication boundary, redirect
and host policy, maximum request/frame size, timeout, freshness semantics,
failure state, browser-exposure policy, and the distinction between preview,
live stream, recording, and camera control. The feature also needs deterministic
fixtures, source-scoped owner acknowledgement where appropriate, and separate
supervised hardware validation.

## Delivery slices

### C6.0 — common read-model and fail-closed capability vocabulary

Define shared camera availability states that distinguish `observed`,
`unavailable`, `unsupported`, `unauthenticated`, `not-evidenced`, `stale`, and
`error`. The default is no camera capability or UI. A camera status never
creates a control, recording, media-library, timelapse, or arbitrary URL
capability.

### C6.1 — platform evidence and bounded adapters

Review each platform separately. A snapshot adapter may issue only the one
documented safe request; a stream adapter must have a documented handshake and
proxy boundary. Never crawl endpoints, enumerate media, probe port ranges, use
credentials outside the configured source contract, enable a camera, or save
frames as part of evidence gathering.

### C6.2 — owner-enabled Workshop presentation

After C6.1 acceptance, surface only the validated camera mode with clear
freshness/error status, accessible controls, and bounded resource handling.
Opening a full-screen view is a presentation of the already authorized source;
it must not activate a previously inactive camera or change printer state.

### C6.3 — supervised validation and recovery

For each approved platform/firmware/configuration, validate initial connection,
disconnect/reconnect, timeout, stale/unavailable presentation, and owner
disablement without recording media. A successful preview validation does not
automatically authorize video recording, timelapse, thumbnails, or control.

## Explicit exclusions

C6 excludes camera activation, lights, fans, motion, print controls, file
management, recordings, timelapses, media indexing, downloads, cloud relays,
subnet discovery, broad service scans, and generic RTSP/MJPEG/HTTP probing.
Future media features require their own evidence and approval.
