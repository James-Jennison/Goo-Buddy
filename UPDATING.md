# Updating Goo Buddy

Goo Buddy does not yet publish a container image. Update a reviewed source
checkout and rebuild locally. The Compose service, volumes, database filename,
and native service identifiers retain their legacy `bambuddy` names so existing
installations keep their data; do not rename them during an update.

## Docker Compose source checkout

1. Back up the stopped persistent data volume or its exact host directory.
2. Update only from the configured Goo Buddy origin:

   ```bash
   git pull --ff-only origin main
   docker compose build --pull
   docker compose up -d
   docker compose logs -f bambuddy
   ```

3. Confirm the health endpoint before exposing the service through a reverse
   proxy:

   ```bash
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
volume. Roll back only to a reviewed source revision that supports the current
schema; test representative data before relying on a rollback in production.

## Future packaged releases

Verified multi-architecture GHCR distribution is planned, not available now.
See the [container distribution and Raspberry Pi installation roadmap goal](docs/GOO_BUDDY_ROADMAP.md#goal-multi-architecture-container-distribution-and-raspberry-pi-installation).
