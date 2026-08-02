# Container distribution and verification

Goo Buddy publishes `ghcr.io/james-jennison/goo-buddy:0.3.0-alpha.5` as an OCI
multi-architecture image index. It resolves native `linux/amd64` and
`linux/arm64` images. The immutable version tag, `sha-<commit>` tag, and
`latest` are all verified by the guarded tag-publication workflow; `latest` is
promoted only after the immutable release identity, architecture manifests,
SBOM, provenance, vulnerability scan, and public registry checks pass.

## Release identity

`0.3.0-alpha.5` is the first independently published Goo Buddy container
prerelease. The project has
an alpha Moonraker monitor and a first public distribution, so this is not a
stable-release claim. The application, Git tag, image metadata, and immutable
container tag use this same canonical external version spelling.

## Production image contract

The Dockerfile pins supported multi-platform Node and Python base-image
manifests by digest. The final application stage is Debian 13 Trixie
(`python:3.13-slim-trixie`), rather than Alpine, so it uses a maintained
glibc-based Debian-family runtime aligned with Raspberry Pi OS and
Debian/Ubuntu hosts. It is an official Debian container image, not Raspberry
Pi OS itself and not a bit-for-bit Raspberry Pi OS replacement. It labels each
image with OCI title, description, source, URL, revision, version, creation
time, and AGPL-3.0-only license. The final stage contains production backend
code, built static assets, and the required G-code viewer assets, but excludes
Git metadata, tests, frontend development scripts, preview fixtures, local
configuration, and build caches.

Where the runtime retains the required Unix capabilities, the root entrypoint
normalises the chosen data/log-volume ownership and drops to `PUID:PGID`. The
published Compose contract deliberately drops every Linux capability; in that
mode it runs capless as UID 0 rather than attempting an impossible ownership or
UID switch. It has a local health check and a five-second application
graceful-shutdown bound inside Compose's 30-second stop grace period. The
published Compose contract runs without host networking, privileged mode,
Docker socket access, or added capabilities.

## Validation and publication

The source workflow builds and smoke-tests both architectures with no runtime
network access. AMD64 validation runs on GitHub's `ubuntu-24.04` runner and
ARM64 validation runs natively on `ubuntu-24.04-arm`, with an early host
architecture assertion in each job. Those Ubuntu runners build and exercise
the Debian 13 Trixie application image; the runner operating system is not the
image operating system. The workflow checks image architecture, Debian-family
identity, OpenCV import, final-stage file boundaries, and Compose
configuration. The tag-only publication workflow rejects tags that do not peel
to the current `main` commit, refuses pre-existing immutable image tags, scans
both images, creates a multi-architecture index, records SBOM and provenance
attestations, verifies the remote manifest, makes the new package public, tests
unauthenticated metadata access, and only then applies `latest`.

If an immutable publication completes but a later public-access or verification
step fails, operators must not rerun the tag publication or replace its tags.
The dispatch-only recovery path accepts that annotated tag and its expected
index digest, re-verifies the public manifests, OCI labels, attestations, and
platform set, and promotes a previously absent `latest` only after those checks
pass.

OCI attestation manifests are legitimate index entries but are not runnable
architectures. Platform verification counts only `linux/amd64` and
`linux/arm64` runnable descriptors.

## Vulnerability evidence and review

The exact pinned Trivy scan retains its complete HIGH/CRITICAL raw JSON and
table evidence for each architecture. A release is blocked by every
HIGH/CRITICAL application finding and every Debian OS finding with a vendor
fixed version that is not in the final image. Debian Trixie base findings with
no vendor fixed version stay visible in a generated upstream-risk report; they
are not suppressed or treated as passed. See the
[security-review procedure](CONTAINER_SECURITY_REVIEW.md) for the required
human review due within fourteen days and the fresh-evidence requirement for
each subsequent release.

See [Raspberry Pi and Docker Compose installation](RASPBERRY_PI_FIRST_RUN.md)
for fresh install, compatibility-preserving upgrade, backup, restore, rollback,
and operator steps. Publication evidence records final digests; do not infer a
digest from a mutable `latest` tag.
