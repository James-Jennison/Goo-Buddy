# Container build validation

Goo Buddy preserves Bambuddy's Linux container support for both `linux/amd64`
and `linux/arm64` (Raspberry Pi 4/5). The production Dockerfile uses BuildKit
cache mounts, so use Docker Buildx rather than Docker's legacy builder.

The official `node:22-bookworm-slim` and `python:3.13-slim-trixie` base tags
are resolved afresh with `--pull`; both publish Linux amd64 and arm64/v8
manifests. No platform is hard-coded in either Compose file.

## Local native build

On a machine matching the desired runtime architecture:

```bash
docker buildx build --pull --progress=plain --load -t goo-buddy:local .
docker run --rm --network none goo-buddy:local python -c "import backend.app.main"
```

`--load` is appropriate here because this is a single-platform local image.
The smoke check has no network access and does not start the application,
expose ports, or contact a printer.

## Raspberry Pi ARM64 build

On a native ARM64 Raspberry Pi:

```bash
docker buildx build --platform linux/arm64 --pull --progress=plain --load \
  -t goo-buddy:local-arm64 .
docker image inspect goo-buddy:local-arm64 --format '{{.Architecture}}/{{.Os}}'
DOCKER_DEFAULT_PLATFORM=linux/arm64 docker compose -f docker-compose.yml config --quiet
```

An x86_64 workstation requires an arm64 `binfmt_misc` emulator before Buildx
can execute the Dockerfile's ARM64 `RUN` steps. Installing it changes host
kernel state and requires explicit administrator approval. The one-time
command is:

```bash
docker run --privileged --rm tonistiigi/binfmt --install arm64
```

After approval, create an isolated builder without changing the default
builder:

```bash
docker buildx create --name goo-buddy-arm64 --driver docker-container --use --bootstrap
docker buildx inspect --bootstrap
```

Confirm that the builder reports `linux/arm64` before running the ARM64 build.
Do not remove unrelated builders, images, caches, containers, or volumes as a
substitute for platform support.

## Authorized multi-architecture release build

Only an explicitly authorized release process may publish an image:

```bash
docker buildx build --platform linux/amd64,linux/arm64 --pull --progress=plain \
  -t ghcr.io/james-jennison/goo-buddy:VERSION --push .
```

`--load` cannot load a combined multi-platform manifest into Docker's classic
local image store. Validate each platform separately with `--load`, as CI
does, or use an explicit OCI output when a local artifact is required.

## CI policy

`.github/workflows/container-platforms.yml` resolves current registry
manifests, builds amd64 and arm64 separately with Buildx, loads each image,
and runs import/static smoke checks with `--network none`. It never pushes or
publishes a container image.
