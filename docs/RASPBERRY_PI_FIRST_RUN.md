# Raspberry Pi first run

Goo Buddy supports Linux ARM64 on Raspberry Pi 4/5 through the same Docker
Compose configuration used for AMD64. Install a current 64-bit Raspberry Pi
OS, Docker Engine plus the Compose plugin, then clone the tagged source and
run `docker compose up -d --build`. There is not yet a published Goo Buddy
image to pull; this local-build requirement is tracked in the
[container-distribution roadmap goal](GOO_BUDDY_ROADMAP.md#goal-multi-architecture-container-distribution-and-raspberry-pi-installation).
Keep the Compose data volume on reliable
persistent storage; it contains configuration, encrypted secrets, and the
application database.

For updates, back up the stopped data volume or its exact mounted directory,
pull the approved source revision, run `docker compose build`, then `docker
compose up -d`. Restore only from an offline backup made while the service was
stopped. See [container ARM64 validation](CONTAINER_BUILDS.md#raspberry-pi-arm64-validation)
for the equivalent local architecture check.

On first run, open the loopback/reverse-proxied Goo Buddy UI and add printers
manually. Bambu retains its inherited setup. Elegoo SDCP and Moonraker are
explicit opt-in, read-only sources; their saved private endpoints are never
shown on the dashboard. OrcaSlicer continues to use ElegooLink directly for
Elegoo print submission. Goo Buddy does not upload to, print through, or
control Moonraker in this alpha.
