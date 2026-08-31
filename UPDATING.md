# Updating Goo Buddy

Goo Buddy publishes the `0.3.0-alpha.6` multi-architecture OCI image for
AMD64 and ARM64 hosts. The normal operator update path pulls a reviewed,
immutable published image through `docker-compose.release.yml`; it does not
rebuild the application on the host. This is an alpha distribution, not a
generally recommended stable release.

## Published Docker Compose installation

1. Back up the selected persistent data volume before changing images. Keep
   backups and protected-secret material private.
2. In the checked-out Goo Buddy release directory, select a known immutable
   version tag or verified digest in `.env`. Do not use `latest` as a rollback
   target.
3. Pull, replace the container, and verify the local health endpoint:

   ```bash
   docker compose -f docker-compose.release.yml pull
   docker compose -f docker-compose.release.yml up -d
   curl -f http://127.0.0.1:8000/health
   docker compose -f docker-compose.release.yml logs -f goo-buddy
   ```

The published Compose contract remains loopback-bound at `127.0.0.1:8000` by
default. Do not widen it without an independently chosen firewall or reverse
proxy boundary. For ARM64/AMD64 selection, legacy-volume upgrades, backup,
restore, and digest-pinned rollback, follow the [Raspberry Pi and Docker
Compose guide](docs/RASPBERRY_PI_FIRST_RUN.md).

## Legacy source checkout

The legacy `docker-compose.yml` source-build path and native helpers remain
available for development and compatibility-sensitive existing deployments.
Their Compose service, volumes, database filename, and native service
identifiers retain their legacy `bambuddy` names so established data is not
stranded; do not rename them during an update.

To update a reviewed source checkout:

```bash
git pull --ff-only origin main
docker compose build --pull
docker compose up -d
docker compose logs -f bambuddy
curl -f http://127.0.0.1:8000/health
```

## Native source checkout

The supported update helper retains its legacy path and service defaults for
upgrade compatibility:

```bash
sudo /opt/bambuddy/install/update.sh
```

To update manually, stop the compatibility-preserved service, fast-forward the
Goo Buddy checkout, install dependencies, rebuild the frontend, then restart:

```bash
cd /opt/bambuddy
sudo systemctl stop bambuddy
sudo -u bambuddy git pull --ff-only origin main
sudo -u bambuddy venv/bin/pip install -r requirements.txt
sudo -u bambuddy npm --prefix frontend ci
sudo -u bambuddy npm --prefix frontend run build
sudo systemctl start bambuddy
```

Database migrations run automatically at startup. Never delete
`bambuddy.db`, named volumes, or `DATA_DIR` merely to change a displayed
product name.

## Restore and rollback

Use Settings → Backup → **Create Backup** before a manual update and keep the
result private: it contains application state and protected secrets. Restore
only while the service is stopped, using the same install path and persistent
volume. Roll back only to a reviewed image or source revision that supports the
current schema; test representative data before relying on a rollback in
production.
