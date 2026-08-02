#!/usr/bin/env python3
"""Validate non-runtime invariants of Goo Buddy's published-image contract.

This tool deliberately reads repository files only. It performs no Docker,
network, printer, credential, or persistence operation, so it is safe in CI
and before a public package publication.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def require(text: str, needle: str, source: str) -> None:
    if needle not in text:
        raise SystemExit(f"{source} is missing required contract text: {needle!r}")


def forbid(text: str, needle: str, source: str) -> None:
    if needle in text:
        raise SystemExit(f"{source} contains forbidden production contract text: {needle!r}")


def main() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.release.yml").read_text(encoding="utf-8")
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    config = (ROOT / "backend/app/core/config.py").read_text(encoding="utf-8")
    release_env = (ROOT / ".env.release.example").read_text(encoding="utf-8")

    version_match = re.search(r'^APP_VERSION = "([0-9A-Za-z.-]+)"$', config, re.MULTILINE)
    if version_match is None:
        raise SystemExit("backend/app/core/config.py must define a canonical APP_VERSION")
    version = version_match.group(1)
    require(compose, f"goo-buddy:{version}", "docker-compose.release.yml")
    require(release_env, f"goo-buddy:{version}", ".env.release.example")

    for label in (
        "org.opencontainers.image.title",
        "org.opencontainers.image.description",
        "org.opencontainers.image.source",
        "org.opencontainers.image.url",
        "org.opencontainers.image.revision",
        "org.opencontainers.image.version",
        "org.opencontainers.image.created",
        "org.opencontainers.image.licenses",
        "HEALTHCHECK",
        "GIT_BRANCH=main",
        "COPY backend/app/ ./backend/app/",
    ):
        require(dockerfile, label, "Dockerfile")
    for forbidden in (
        "COPY .git/HEAD",
        "COPY backend/ ./backend/",
        "setcap cap_net_bind_service",
    ):
        forbid(dockerfile, forbidden, "Dockerfile")

    for excluded in (".git/", "frontend/scripts/", "backend/tests/"):
        require(ignore, excluded, ".dockerignore")

    for required in (
        "ghcr.io/james-jennison/goo-buddy",
        "linux/arm64",
        "127.0.0.1",
        "no-new-privileges:true",
        "cap_drop:",
        "- ALL",
        "restart: unless-stopped",
        "stop_grace_period: 30s",
        "goo_buddy_data:/app/data",
        "goo_buddy_logs:/app/logs",
    ):
        require(compose, required, "docker-compose.release.yml")
    for forbidden in ("build:", "network_mode:", "privileged:", "/var/run/docker.sock"):
        forbid(compose, forbidden, "docker-compose.release.yml")

    print("release container contract: OK")


if __name__ == "__main__":
    main()
