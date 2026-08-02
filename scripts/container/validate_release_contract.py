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
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    container_docs = (ROOT / "docs/CONTAINER_BUILDS.md").read_text(encoding="utf-8")
    raspberry_pi_docs = (ROOT / "docs/RASPBERRY_PI_FIRST_RUN.md").read_text(encoding="utf-8")
    security_review_docs = (ROOT / "docs/CONTAINER_SECURITY_REVIEW.md").read_text(encoding="utf-8")
    publication_workflow = (ROOT / ".github/workflows/publish-container.yml").read_text(encoding="utf-8")
    ci_workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    security_workflow = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")

    version_match = re.search(r'^APP_VERSION = "([0-9A-Za-z.-]+)"$', config, re.MULTILINE)
    if version_match is None:
        raise SystemExit("backend/app/core/config.py must define a canonical APP_VERSION")
    version = version_match.group(1)
    require(dockerfile, f"ARG VERSION={version}", "Dockerfile")
    require(compose, f"goo-buddy:{version}", "docker-compose.release.yml")
    require(release_env, f"goo-buddy:{version}", ".env.release.example")
    for source, text in (
        ("README.md", readme),
        ("docs/CONTAINER_BUILDS.md", container_docs),
        ("docs/RASPBERRY_PI_FIRST_RUN.md", raspberry_pi_docs),
        ("docs/CONTAINER_SECURITY_REVIEW.md", security_review_docs),
    ):
        require(text, version, source)

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
        "python:3.13-slim-trixie@sha256:",
        "DEBIAN_FRONTEND=noninteractive",
        "apt-get install -y --no-install-recommends",
        "rm -rf /var/lib/apt/lists/*",
        "COPY --from=python-builder /opt/goo-buddy-venv /opt/goo-buddy-venv",
        "gosu",
    ):
        require(dockerfile, label, "Dockerfile")
    for forbidden in (
        "COPY .git/HEAD",
        "COPY backend/ ./backend/",
        "setcap cap_net_bind_service",
        "python:3.13-alpine",
        "apk add",
        "apk del",
        "su-exec",
    ):
        forbid(dockerfile, forbidden, "Dockerfile")

    for required_security_text in (
        "no vendor fixed version",
        "fourteen days",
        "ubuntu-24.04-arm",
        "Debian 13 Trixie",
    ):
        require(security_review_docs, required_security_text, "docs/CONTAINER_SECURITY_REVIEW.md")

    for required_publication_text in (
        "validate_vulnerability_gate.py",
        'ignore-unfixed: "false"',
        "trivy-${{ matrix.suffix }}.json",
        "unresolved-upstream-base-${{ matrix.suffix }}.md",
        "published-container-security-evidence",
        "unresolved-upstream-base-published-amd64.md",
        "unresolved-upstream-base-published-arm64.md",
        "retention-days: 90",
        "ubuntu-24.04-arm",
        'manifest_json="$(docker buildx imagetools inspect --raw "$IMAGE@$DIGEST")"',
        "linux/amd64 manifest missing from published index",
        "linux/arm64 manifest missing from published index",
        'docker pull "$IMAGE@$amd64_digest"',
        'docker pull "$IMAGE@$arm64_digest"',
        'for platform_digest in "$amd64_digest" "$arm64_digest"; do',
    ):
        require(publication_workflow, required_publication_text, ".github/workflows/publish-container.yml")
    for forbidden_publication_text in (
        "--ignore-unfixed",
        ".trivyignore",
        'docker pull --platform linux/amd64 "$IMAGE@$DIGEST"',
        'docker pull --platform linux/arm64 "$IMAGE@$DIGEST"',
        'docker pull --platform "$platform" "$IMAGE@$DIGEST"',
    ):
        forbid(publication_workflow, forbidden_publication_text, ".github/workflows/publish-container.yml")
    for source, workflow in (
        (".github/workflows/ci.yml", ci_workflow),
        (".github/workflows/security.yml", security_workflow),
    ):
        for forbidden_security_bypass in ("--ignore-vuln", "ALLOWLIST", "continue-on-error: true"):
            forbid(workflow, forbidden_security_bypass, source)

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
