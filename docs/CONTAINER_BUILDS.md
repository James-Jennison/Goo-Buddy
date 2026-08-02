# Container distribution and verification

Goo Buddy publishes `ghcr.io/james-jennison/goo-buddy:0.3.0-alpha.3` as an OCI
multi-architecture image index. It resolves native `linux/amd64` and
`linux/arm64` images. The immutable version tag, `sha-<commit>` tag, and
`latest` are all verified by the guarded tag-publication workflow; `latest` is
promoted only after the immutable release identity, architecture manifests,
SBOM, provenance, vulnerability scan, and public registry checks pass.

## Release identity

`0.3.0-alpha.3` is the first independently published Goo Buddy container
prerelease. The project has
an alpha Moonraker monitor and a first public distribution, so this is not a
stable-release claim. The application, Git tag, image metadata, and immutable
container tag use this same canonical external version spelling.

## Production image contract

The Dockerfile pins supported multi-platform Node and Python base-image
manifests by digest. It labels each image with OCI title, description, source,
URL, revision, version, creation time, and AGPL-3.0-only license. The final
stage contains production backend code, built static assets, and the required
G-code viewer assets, but excludes Git metadata, tests, frontend development
scripts, preview fixtures, local configuration, and build caches.

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
network access. It checks image architecture, final-stage file boundaries, and
Compose configuration. The tag-only publication workflow rejects tags that do
not peel to the current `main` commit, refuses pre-existing immutable image
tags, scans both images, creates a multi-architecture index, records SBOM and
provenance attestations, verifies the remote manifest, makes the new package
public, tests unauthenticated metadata access, and only then applies `latest`.

OCI attestation manifests are legitimate index entries but are not runnable
architectures. Platform verification counts only `linux/amd64` and
`linux/arm64` runnable descriptors.

See [Raspberry Pi and Docker Compose installation](RASPBERRY_PI_FIRST_RUN.md)
for fresh install, compatibility-preserving upgrade, backup, restore, rollback,
and operator steps. Publication evidence records final digests; do not infer a
digest from a mutable `latest` tag.
