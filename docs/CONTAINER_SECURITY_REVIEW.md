# Container security-review procedure

Every Goo Buddy container release runs pinned Trivy scans for both native
`linux/amd64` and `linux/arm64` images. The release workflow retains the raw
JSON and human-readable output, SPDX SBOM, and generated upstream-base report
as evidence artifacts. The current prerelease candidate is `0.3.0-alpha.4`.

The gate fails on every HIGH or CRITICAL application dependency finding and on
every Debian OS finding for which Trivy reports a vendor fixed version unless
the final SPDX SBOM proves the image contains that fixed version instead of the
scanner-reported stale base metadata. That reconciliation is reported alongside
the raw finding; it is not an ignore or an exploitability judgement. The gate
does not suppress Debian OS findings that have no vendor fixed version. Instead,
it generates a report showing the advisory, package, installed version, scanner
status, image/base origin, scan timestamp, and a human-review deadline no more
than fourteen days later.

## Required review

By the deadline in each generated report, a human security reviewer must:

1. Read the raw Trivy JSON, table output, SPDX SBOM, provenance, and generated
   report for both architectures.
2. Check whether Debian has released a vendor fixed version.
3. Require a rebuilt image and fresh scan before a later release when a fix is
   available; the gate will block an image still containing that vulnerable
   version.
4. Record the review outcome in the release's GitHub Actions evidence. The
   next release must create a new report from its new scan; no CVE allowlist is
   inherited.

The final application image is official Debian 13 Trixie, not Raspberry Pi OS.
GitHub's `ubuntu-24.04` and native `ubuntu-24.04-arm` runners are build and
runtime-validation hosts only.
