# Raspberry Pi and Docker Compose installation

Goo Buddy runs on the Raspberry Pi; GitHub Container Registry (GHCR) only
distributes the image. It does not provide a hosted Goo Buddy server.

## Supported hosts

Use a Raspberry Pi 4 or 5 running a current **64-bit** Raspberry Pi OS, Docker
Engine, and the Docker Compose plugin. `linux/arm/v7` (32-bit ARM) is not
published. AMD64 Linux Docker hosts use the same image by setting
`GOO_BUDDY_PLATFORM=linux/amd64`.

The first independently published Goo Buddy image is
`ghcr.io/james-jennison/goo-buddy:0.3.0-alpha.3`. It is an alpha release:
Bambu support is inherited and mature; Elegoo SDCP monitoring is read-only;
Moonraker monitoring is alpha and read-only.

## Fresh installation

```bash
git clone https://github.com/James-Jennison/Goo-Buddy.git
cd Goo-Buddy
cp .env.release.example .env
docker compose -f docker-compose.release.yml pull
docker compose -f docker-compose.release.yml up -d
curl -f http://127.0.0.1:8000/health
```

The release Compose file uses bridge networking, has no Docker socket or host
network mount, drops Linux capabilities, and binds the web UI to loopback by
default. Set `GOO_BUDDY_BIND_ADDRESS` only after choosing an appropriate host
firewall or reverse-proxy boundary. Inspect logs with:

```bash
docker compose -f docker-compose.release.yml logs -f goo-buddy
```

To confirm Docker selected a 64-bit image:

```bash
docker image inspect ghcr.io/james-jennison/goo-buddy:0.3.0-alpha.3 \
  --format '{{.Architecture}}/{{.Os}}'
```

For maximum reproducibility, replace the image tag in `.env` with the verified
`@sha256:...` digest recorded by the release publication report. An immutable
version tag remains pinned to its release image. `latest` is a convenience tag
advanced only after a release passes its gates; it is not a rollback pin.

## Manual printer configuration

Opening a healthy Goo Buddy installation does not contact a printer. Add
sources manually in the UI. Elegoo and Moonraker sources remain disabled until
their owner explicitly enables them; no discovery, broadcast, or automatic
contact is part of this installation process.

## Upgrade from a Bambuddy-derived Compose installation

Do not rename, delete, or copy the inherited `bambuddy_data` or
`bambuddy_logs` volumes. First stop the old service and make an offline backup.
The included read-only planner refuses ambiguous layouts and prints the volume
variables for a complete legacy pair:

```bash
docker compose down
./scripts/container/legacy_volume_plan.sh
GOO_BUDDY_DATA_VOLUME=bambuddy_data \
GOO_BUDDY_LOGS_VOLUME=bambuddy_logs \
docker compose -f docker-compose.release.yml up -d
```

If both legacy and new volume pairs exist, stop. Determine which pair contains
the established data before starting a new service. Goo Buddy keeps the
database path and migration ordering inside the selected data volume; it does
not rename volumes automatically or create a parallel empty database during a
recognised legacy upgrade.

## Backup, restore, and rollback

Stop the service before an offline volume backup. Keep archives and any
encrypted-secret material private. A simple Docker-volume backup is:

```bash
mkdir -p backups
docker compose -f docker-compose.release.yml down
docker run --rm -v goo_buddy_data:/data:ro -v "$PWD/backups:/backup" \
  alpine:3.22 tar -C /data -czf /backup/goo-buddy-data.tgz .
sha256sum backups/goo-buddy-data.tgz > backups/goo-buddy-data.tgz.sha256
```

To restore, verify the checksum, stop Goo Buddy, and extract into a **new,
empty** target volume before using it as `GOO_BUDDY_DATA_VOLUME`:

```bash
sha256sum -c backups/goo-buddy-data.tgz.sha256
docker volume create goo-buddy-restored
docker run --rm -v goo-buddy-restored:/data -v "$PWD/backups:/backup:ro" \
  alpine:3.22 tar -C /data -xzf /backup/goo-buddy-data.tgz
GOO_BUDDY_DATA_VOLUME=goo-buddy-restored \
docker compose -f docker-compose.release.yml up -d
```

Never extract over an unknown existing volume. Backward rollback is safe only
when the selected older image supports the database schema already present;
stop and restore the pre-upgrade backup if a schema downgrade is unsupported.

## Upgrade and rollback

To update, back up first, select a known immutable version in `.env`, then:

```bash
docker compose -f docker-compose.release.yml pull
docker compose -f docker-compose.release.yml up -d
curl -f http://127.0.0.1:8000/health
```

To roll back, stop the stack, change `GOO_BUDDY_IMAGE` to the previously
validated immutable version or digest, then start it again. Do not use `latest`
for a rollback target.

## Shutdown and uninstall

`docker compose -f docker-compose.release.yml down` sends the application its
graceful stop signal and leaves named volumes intact. Add `-v` only when you
have independently verified and intentionally backed up the named volumes;
that permanently removes persisted Goo Buddy data.

## Troubleshooting

- `exec format error`: confirm a 64-bit OS and `GOO_BUDDY_PLATFORM` matches
  the host (`linux/arm64` on Raspberry Pi, `linux/amd64` on x86_64).
- Unhealthy container: inspect `docker compose -f docker-compose.release.yml
  logs goo-buddy`; do not add a printer merely to test application health.
- Upgrade planner reports ambiguity: do not start another stack. Preserve the
  existing volumes and resolve ownership from a backup first.
- Permission errors in a runtime that permits ownership changes: set `PUID`
  and `PGID` in `.env` to the intended host user IDs, then restart. The
  entrypoint normalises only the selected data/log volumes before dropping
  runtime privileges. The supplied hardened Compose profile removes every
  Linux capability, so it instead runs with an empty capability set and cannot
  change volume ownership or UID at startup.
