#!/bin/sh
# Bambuddy container entrypoint.
#
# When the runtime retains the required capabilities, this runs as root (the
# image leaves USER unset), chowns /app/data and /app/logs to PUID:PGID, then
# drops to PUID:PGID via su-exec and execs the application. The hardened release
# Compose profile drops every capability and follows its capless branch below.
# The normal path fixes the class of "Permission denied" errors that bit users
# when:
#
#   - a Docker named volume was first created with root ownership and
#     the container was running with `user: 1000:1000` (named volumes
#     created by the daemon take its ownership; Dockerfile chmod hacks
#     cover the parent path but not subdirs created at runtime).
#   - a bind-mount source path didn't exist on the host yet, so dockerd
#     created it as root before the container started, leaving it
#     unwritable by uid 1000 inside the container — see #1211 / #668
#     for the virtual_printer bind-mount case the shipped compose
#     template ships uncommented.
#
# If the container is started with an explicit `user:` directive
# (compose `user:` or `docker run --user`), the entrypoint runs as that
# user instead of root and chown isn't possible. The script falls
# through to direct exec without modifying ownership — preserving the
# previous behavior for users who pin a specific uid via compose.

set -eu

# Default to 1000:1000 to match the legacy `user: "1000:1000"` default
# in our previously-shipped compose template; overridable via env so
# users who run docker as a different uid can match their host without
# editing the compose user: directive.
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

case "$PUID:$PGID" in
    *[!0-9:]*|:|*::* )
        echo "[entrypoint] error: PUID and PGID must be numeric" >&2
        exit 1
        ;;
esac

# If requested, update and use the system trust store inside the container.
# Users can set USE_SYSTEM_TRUST_STORE to any non-empty value to enable.
if [ -n "${USE_SYSTEM_TRUST_STORE:-}" ]; then
    echo "[entrypoint] USE_SYSTEM_TRUST_STORE is set"
    if [ "$(id -u)" -ne 0 ]; then
        echo "[entrypoint] error: USE_SYSTEM_TRUST_STORE is set but not running as root; cannot update trust store"
        exit 1
    fi
    # Check if we have any certificates to process. Error if directory is empty
    if ls -1 /usr/local/share/ca-certificates/*.crt >/dev/null 2>&1; then
        echo "[entrypoint] .crt files found in /usr/local/share/ca-certificates"
    else
        echo "[entrypoint] no .crt files in /usr/local/share/ca-certificates"
        exit 1
    fi
    if command -v update-ca-certificates >/dev/null 2>&1; then
        echo "[entrypoint] update-ca-certificates found; updating system trust store"
        if update-ca-certificates --fresh ; then
            echo "[entrypoint] update-ca-certificates succeeded; exporting SSL_CERT_DIR=/etc/ssl/certs"
            export SSL_CERT_DIR="/etc/ssl/certs"
        else
            echo "[entrypoint] error: update-ca-certificates failed"
            exit 1
        fi
    else
        echo "[entrypoint] error: update-ca-certificates not found; cannot update trust store"
        exit 1
    fi
else
    echo "[entrypoint] USE_SYSTEM_TRUST_STORE not set; skipping system trust store update"
fi

# If we're not root, we can't chown anything. Exec the original command
# and trust that the user has set up host-side ownership themselves.
if [ "$(id -u)" -ne 0 ]; then
    exec "$@"
fi

# The published Compose contract deliberately drops every Linux capability.
# That also removes CAP_CHOWN, CAP_SETUID, and CAP_SETGID, so a root
# entrypoint cannot safely normalize volume ownership or switch to PUID:PGID.
# In that intentionally capless mode, run the application as UID 0 with an
# empty capability set instead of entering a restart loop. Root without Linux
# capabilities cannot perform privileged kernel operations; callers that need
# a non-root UID can use an unrestricted runtime or pre-own their volumes.
if grep -Eq '^CapEff:[[:space:]]*0+$' /proc/self/status; then
    echo "[entrypoint] capability set is empty; running without UID switch"
    exec "$@"
fi

# `chown -R` is gated behind a top-level ownership check so a correctly-
# owned directory isn't traversed on every container start. A user with
# a multi-GB archive directory would otherwise pay seconds-to-minutes
# of chown traversal at every restart.
chown_if_needed() {
    target="$1"
    [ -d "$target" ] || mkdir -p "$target"
    current="$(stat -c '%u:%g' "$target" 2>/dev/null || echo '')"
    if [ "$current" != "$PUID:$PGID" ]; then
        echo "[entrypoint] chown -R ${PUID}:${PGID} ${target}"
        chown -R "${PUID}:${PGID}" "$target" || true
    fi
}

chown_if_needed /app/data
chown_if_needed /app/logs

# Bind-mount-source path needs the same treatment when present. dockerd
# creates missing bind-mount sources as root on the host before the
# container starts; the chown here propagates through the bind mount to
# the host-side directory and fixes the issue once and for all.
if [ -d /app/data/virtual_printer ]; then
    chown_if_needed /app/data/virtual_printer
fi

# Drop privileges and run the application when the runtime retains the
# capabilities needed for the UID switch. The hardened release Compose profile
# takes the capless branch above instead.
exec su-exec "${PUID}:${PGID}" "$@"
