# Isolated simulator runtime. This target intentionally does not run Goo Buddy.
FROM python:3.13-slim-trixie

WORKDIR /farm

# aiohttp serves the narrow Moonraker contract; ffmpeg provides the optional
# manual V4L2 single-frame path. Neither is used by normal Goo Buddy startup.
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ffmpeg \
 && pip install --no-cache-dir 'aiohttp==3.14.3' \
 && rm -rf /var/lib/apt/lists/*
