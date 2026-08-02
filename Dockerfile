# syntax=docker/dockerfile:1.7

ARG VERSION=0.3.0-alpha.1
ARG REVISION=unknown
ARG CREATED=unknown

# Build frontend
# Pinned multi-platform index for node:22-bookworm-slim, refreshed only through
# a reviewed dependency/security update. It resolves natively for amd64/arm64.
FROM node:22-bookworm-slim@sha256:f32b81066cde10a75dbac96646099533316d94bac4150c55da1636e1f0ffdc46 AS frontend-builder

WORKDIR /app/frontend

# Copy package files first for better caching
COPY frontend/package*.json ./

# Use cache mount for npm
RUN --mount=type=cache,target=/root/.npm \
    npm ci

COPY frontend/ ./
RUN npm run build

# Production image
# Pinned multi-platform index for python:3.13-slim-trixie, refreshed only
# through a reviewed dependency/security update.
FROM python:3.13-slim-trixie@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91

ARG VERSION
ARG REVISION
ARG CREATED
LABEL org.opencontainers.image.title="Goo Buddy" \
      org.opencontainers.image.description="Self-hosted multi-platform 3D-printer management" \
      org.opencontainers.image.source="https://github.com/James-Jennison/Goo-Buddy" \
      org.opencontainers.image.url="https://github.com/James-Jennison/Goo-Buddy" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${CREATED}" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

WORKDIR /app

# Install system dependencies
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    gnupg \
    gosu \
    iproute2 \
    libcap2-bin \
    openssh-client \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install the Tailscale CLI only (no tailscaled — the daemon runs on the host).
# Goo Buddy calls `tailscale status` / `tailscale cert` via the host's socket,
# which the user mounts in via docker-compose when they want to enable the
# Tailscale integration for virtual printers. Without the socket mount, the
# binary is harmless — the code logs a hint and falls back to self-signed.
RUN curl -fsSL https://pkgs.tailscale.com/stable/debian/trixie.noarmor.gpg \
        -o /usr/share/keyrings/tailscale-archive-keyring.gpg \
    && curl -fsSL https://pkgs.tailscale.com/stable/debian/trixie.tailscale-keyring.list \
        -o /etc/apt/sources.list.d/tailscale.list \
    && apt-get update && apt-get install -y --no-install-recommends tailscale \
    && rm -rf /var/lib/apt/lists/*

# Allow binding to privileged ports (e.g. 990/FTPS) as non-root user.
# File capabilities are more reliable than Docker cap_add with user: directive,
# which depends on ambient capability support in the container runtime.
RUN setcap cap_net_bind_service=+ep "$(readlink -f /usr/local/bin/python3)"

# Install Python dependencies with cache mount.
# pip is upgraded to >=26.1 first to close CVE-2026-6357 — the python:3.13-slim
# base image ships pip 26.0.1, which runs its self-update check after installing
# wheels (so a hostile wheel could hijack stdlib imports during install).
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --root-user-action=ignore --upgrade 'pip>=26.1.2' \
 && pip install --root-user-action=ignore -r requirements.txt

# Copy only production backend code. Tests and source-control metadata are
# deliberately excluded from the production image by .dockerignore.
COPY backend/app/ ./backend/app/

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/static ./static

# Copy embedded GCode viewer static assets (PrettyGCode + Goo Buddy adapter).
# Served by the explicit @app.get("/gcode-viewer/{...}") routes in main.py,
# which resolve files under (static_dir.parent / "gcode_viewer") = /app/gcode_viewer/.
# Without this COPY the routes return a bare 404 at request time and the 3D
# Preview iframe shows {"detail":"Not Found"} (see #1218). The directory is
# vendored third-party JS — the Vite build does NOT stage it into static/,
# the dev server serves it via a configureServer middleware that's dev-only.
COPY gcode_viewer/ ./gcode_viewer/

# Create data directories. Ownership is normalised at startup by the
# entrypoint (chowns to PUID:PGID and drops privileges via gosu before
# exec'ing the app), so we don't need a chmod 777 hack here — that was
# the workaround for the previous compose `user: "1000:1000"` model and
# only worked when the volume's perms happened to survive (named volume
# first-create case; bind-mount-source case bit users in #1211 / #668).
#
# The sentinel file is needed so a freshly-created Docker named volume
# isn't "empty" from Docker's POV. On empty volumes Docker resyncs the
# directory metadata (incl. ownership) from the image on every mount,
# which would mean our entrypoint chown gets reverted on every restart
# and re-fired on every start (slow on multi-GB archive dirs). With a
# sentinel inside the volume on first mount, Docker considers the
# volume populated and stops resyncing, so the chown is genuinely
# one-shot.
RUN mkdir -p /app/data /app/logs && \
    : >/app/data/.bambuddy && \
    : >/app/logs/.bambuddy

# Entrypoint script: handles PUID/PGID + ownership normalisation +
# privilege drop. See deploy/docker-entrypoint.sh for the full rationale.
COPY deploy/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/app/data
ENV LOG_DIR=/app/logs
ENV PORT=8000
ENV GIT_BRANCH=main
# Provide a local username + home for tools that call getpass.getuser() /
# os.path.expanduser() under arbitrary PUIDs. With `user: "1001:1001"` the
# stock python:3.13-slim image has no /etc/passwd entry for that UID, so
# pwd.getpwuid() raises and breaks libraries that do host-level user lookups
# (notably asyncssh, which uses the local username for ~/.ssh/config host
# matching during the SpoolBuddy remote-update flow). Setting LOGNAME/USER
# makes getpass.getuser() resolve via env vars instead of the passwd db;
# HOME=/app gives a writable home that is guaranteed to exist.
ENV HOME=/app
ENV USER=bambuddy
ENV LOGNAME=bambuddy

# Matplotlib (imported lazily by the STL thumbnail generator) tries to create
# its font/style cache at $HOME/.config/matplotlib on first import. /app is
# root-owned and not writable by the PUID:PGID the entrypoint drops to,
# which trips an EPERM warning in everyone's logs and forces matplotlib
# to fall back to a per-restart temp dir (paying the font-scan cost on
# every container restart). Pinning the cache dir to /tmp/matplotlib
# silences the warning and keeps the cache alive for the container's
# lifetime. /tmp is writable by any uid, so this works regardless of PUID.
ENV MPLCONFIGDIR=/tmp/matplotlib

EXPOSE 322
EXPOSE 990
EXPOSE 3000
EXPOSE 3002
EXPOSE 6000
EXPOSE 8000
EXPOSE 8883
EXPOSE 50000-50100

# Health check (uses PORT env var via shell)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", \"8000\")}/health')" || exit 1

# Run the application
# Use standard asyncio loop (uvloop has permission issues in some Docker environments)
# Port is configurable via PORT (default 8000); bind address via HOST (default
# 0.0.0.0). Set HOST=127.0.0.1 to bind loopback only, e.g. when a reverse proxy
# on the same host fronts the app.
#
# `exec` is load-bearing, not style. Without it the shell stays as PID 1 and
# uvicorn runs as its child; dash does not forward signals, so `docker stop`
# SIGTERMs the shell and uvicorn never hears about it. Every stop then ran to
# the end of the grace period and died on SIGKILL (exit 137) — no WAL
# checkpoint, no MQTT disconnect, no virtual-printer teardown, on every restart
# and every image update. With `exec`, uvicorn *is* PID 1 and gets the signal.
#
# --timeout-graceful-shutdown caps the wait on in-flight requests. Uvicorn's
# default is to wait forever, and an MJPEG camera stream is a response that
# never completes, so a single open camera tile would otherwise pin the process
# past Docker's 10s grace and back into SIGKILL. On timeout uvicorn cancels the
# request tasks; the camera generators already unwind cleanly on CancelledError.
ENV UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN=5
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["sh", "-c", "exec uvicorn backend.app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000} --loop asyncio --timeout-graceful-shutdown ${UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN}"]
