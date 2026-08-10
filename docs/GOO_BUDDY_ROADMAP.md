# Goo Buddy roadmap

This roadmap records outcome-sized goals. Planning a goal does not authorize a
release, deployment, image publication, printer contact, or upstream sync.

## Current sequence

1. **User-facing Goo Buddy branding migration and Goo Buddy Workshop UX** —
   **complete**. Goo Buddy is the active user-facing identity across the
   application, PWA metadata, static output, operator guidance, and supported
   diagnostics. The shared, capability-driven Workshop presentation is in
   place for Bambu Lab, Elegoo SDCP v3, and Moonraker sources; retained
   observations and unavailable capabilities remain explicit. Required
   Bambuddy attribution and compatibility-sensitive persisted identifiers are
   retained where changing them could strand an upgrade.
2. **Repository fork-network detachment and independent-project identity** —
   **complete**. Goo Buddy left GitHub's fork network in place while retaining
   repository ID, URL, Git history, AGPL attribution, the technical `upstream`
   remote, and verified before/after snapshots. The completed audit is recorded
   in [fork-network detachment record](FORK_DETACHMENT_READINESS.md); it did
   not synchronize newer Bambuddy history.
3. **Upstream Bambuddy security and compatibility review** — an ongoing,
   human-classified maintenance track that applies after fork-network
   detachment and continues for the life of Goo Buddy. Its first review is
   complete at frozen upstream SHA `d36632db0f0ad45d91b86a3b772c796fdb478586`;
   later reviews start after that baseline and never automatically merge,
   rebase, cherry-pick, or push upstream code.
4. **Multi-architecture container distribution and Raspberry Pi installation**
   — first independently published alpha distribution **complete** at
   `0.3.0-alpha.5`. Continued validation and a future generally recommended
   stable release remain separate work.
5. **Mature capability-driven multi-platform support** — **active**. Goo Buddy
   will maintain and extend Bambu Lab, Elegoo SDCP v3, and Moonraker support
   through platform-specific, evidence-backed capability contracts. The
   approved scope, safety contract, automated delivery gate, and required
   supervised hardware validation are recorded in
   [the multi-platform control maturity gate](MULTI_PLATFORM_MATURITY.md).

   **Deferred cross-platform milestones — not current capability claims:**

   - **C4: Job lifecycle controls** — pause, resume, and cancel across every
     supported printer type. Each platform/operation requires its own protocol
     evidence, deterministic adapter/API/UI coverage, idempotency and
     status-reconciliation rules, permission and audit review, then separately
     approved supervised hardware validation. Existing Bambu behavior remains
     governed by its inherited regression contract; Elegoo and Moonraker must
     not advertise or exercise a control until their own gates are met. The
     staged, all-platform activation plan is recorded in
     [C4 job lifecycle controls](C4_JOB_LIFECYCLE_CONTROLS_PLAN.md).
   - **C5: Managed print submission** — a platform-specific file-transfer and
     job-start capability for every supported printer type. Each adapter needs
     an exact documented transport contract, bounded upload and integrity
     rules, owner/target confirmation, audit and recovery semantics,
     deterministic fixtures, and separately approved hardware validation.
     Existing slicer/vendor submission paths do not establish a Goo Buddy
     upload or start-print capability for another platform.

## Approved design direction: Goo Buddy Workshop

**Goo Buddy Workshop — a polished, layered maker command center** is the
approved user-experience direction. It uses a warm navy-and-slate workspace,
teal-to-emerald activity accents, layered surfaces, and concise telemetry to
make a printer fleet easy to scan without presenting a generic administration
dashboard or a fictional control panel.

- Shared surface, status, telemetry, progress, identity, and unavailable-
  capability primitives are the default for future printer pages.
- The saved driver contract—not a model name—determines platform labels:
  Bambu Lab, Elegoo SDCP v3, and Klipper via Moonraker remain distinct.
- Current observations and retained snapshots are visually and textually
  distinct. A retained snapshot is never presented as live.
- Capability-gated sections may show only authoritative normalized data.
  Missing cameras, files, console, CANVAS, controls, material data, history,
  or estimated time remain unavailable rather than being fabricated.
- The shell must remain responsive, keyboard-accessible, contrast-aware, and
  usable with reduced motion. Essential state is never hover-only or
  color-only.
- Concept artwork and synthetic preview fixtures are directional review aids,
  not runtime facts. The development-only preview stays loopback-bound,
  fixture-only, mutation-free, and excluded from production output.

## Goal: Upstream Bambuddy security and compatibility review

### Outcome

After it leaves GitHub's fork network, Goo Buddy keeps Bambuddy as a
fetch-only technical reference: `origin` remains
`https://github.com/James-Jennison/Goo-Buddy.git`, `upstream` remains
`https://github.com/maziggy/bambuddy.git`, and the recorded shared fork point
is `82656c8760bd620bd31fbb31faa3024062e55e88`. Goo Buddy preserves applicable
AGPL, copyright, attribution, and Git-history obligations. Detachment does not
end the responsibility to review relevant public upstream security and
compatibility work.

### Recurring review procedure

This is a governance track, not a one-time completion item. Each review starts
from clean `main` aligned with `origin/main`, fetches `upstream` without
changing the worktree, records the prior and newly fetched upstream SHAs, and
produces a bounded commit list since the previous review. It examines
authentication, secret and printer-credential handling, network/TLS clients,
uploads and archives, path handling, migrations, command execution,
virtual-printer services, dependencies, and containers first.

Relevant changes are classified before any Goo Buddy port:

1. Security fix — prioritize a bounded Goo Buddy port.
2. Dependency vulnerability correction — assess against Goo Buddy's dependency
   graph and security tooling.
3. Bambu protocol or model support — normally port when compatible.
4. Inherited backend/frontend bug fix — port when relevant and regression-tested.
5. Performance or reliability fix — evaluate with evidence.
6. Test or CI improvement — adopt only when it strengthens Goo Buddy's gates.
7. Bambuddy branding, marketing, demos, or product-specific behavior — do not
   port.
8. A change conflicting with Goo Buddy's multi-platform architecture — adapt
   manually or document why it does not apply.
9. A change already independently addressed — record it as equivalent or not
   applicable.
10. A breaking or ambiguous change — defer for explicit design review.

Ports use Goo Buddy-specific reviewable branches or commits; the project never
blindly merges all of upstream. They preserve Elegoo and Moonraker read-only
boundaries, the capability-driven architecture, Workshop UX, migration safety,
and production exclusion of the synthetic preview. Intentionally skipped
changes and their reasons are recorded. Relevant regression, security,
architecture, and migration tests, normal review, and CI are required before
publication.

### Cadence and security boundary

Review monthly, immediately after a publicly disclosed Bambuddy security
advisory, after a significant inherited-functionality release, before a Goo
Buddy stable release, and whenever Goo Buddy's own dependency or security
tooling suggests an inherited vulnerability. Goo Buddy independently operates
CodeQL, dependency auditing, Trivy/container and secret scanning, AMD64/ARM64
validation, and its responsible-disclosure documentation and supported-version
policy. SBOM and provenance checks join this set when container publication is
implemented. Goo Buddy cannot depend on Bambuddy finding vulnerabilities first;
private embargoed advisories are unavailable unless their maintainer explicitly
includes Goo Buddy.

No scheduled workflow may merge or cherry-pick upstream. A future
notification-only workflow may fetch metadata and open an issue when upstream
advances, but may not alter source, create commits or code PRs, or bypass human
classification.

## Goal: Multi-architecture container distribution and Raspberry Pi installation

### Outcome

Goo Buddy can be installed on a Raspberry Pi or AMD64 Docker host by pulling a
verified, versioned multi-architecture image from
`ghcr.io/james-jennison/goo-buddy`, rather than compiling the project locally.
The Raspberry Pi remains the application server; GitHub Container Registry only
stores and distributes the packaged image.

### Required scope

- Build native `linux/amd64` and `linux/arm64` images and publish one validated
  multi-architecture manifest.
- Publish immutable semantic-version and commit-SHA tags. Move `latest` only
  after the exact release candidate passes every required gate.
- Pin base images and release tooling appropriately; retain AGPL and applicable
  third-party notices.
- Generate and retain image digests, supported provenance/attestations, an
  SBOM, vulnerability-scan evidence, and architecture-inspection evidence.
- Continue enforcing CI, CodeQL, Security Audit, AMD64 and ARM64 validation,
  non-networked container smoke tests, and Docker Compose validation.
- Provide Goo Buddy-specific Docker Compose installation, upgrade, rollback,
  backup, restore, health-check, restart, persistent-storage, and graceful
  shutdown guidance for Raspberry Pi.
- Exclude synthetic-preview code, test fixtures, development servers, build
  caches, credentials, printer addresses, and raw captures from production
  images.
- Preserve Bambu behavior and existing data. Normal installation must not
  discover or automatically contact printers. Elegoo's separately enabled,
  owner-acknowledged, bounded RFC1918 UDP/3000 broadcast is the sole exception:
  it yields ephemeral candidates only, with manual registration still required.
  Moonraker remains manual opt-in configuration.

### Upgrade compatibility gate

Test both a clean Goo Buddy installation and an upgrade from the existing
Bambuddy-derived deployment layout. The explicit migration or
compatibility-alias decision must cover legacy Compose service and container
names, volumes, persistent-data and database locations, environment variables,
image references, and relevant service-worker caches. Tests must prove data is
not stranded, duplicated, or silently replaced; identifiers cannot be renamed
for appearance alone.

### Release safety boundary

Publication is permitted only by a separately approved release execution using
GitHub Actions and GitHub-provided credentials from an exact reviewed, clean
commit. It must never overwrite immutable version tags, must verify the remote
digest and architecture manifest, and must make no physical-printer contact.
Creating a GitHub Release, tag, deployment, or `latest` update needs explicit
release approval. Stop on any failed security, architecture, migration,
installation, or smoke-test gate.

### Acceptance criteria

- A fresh Raspberry Pi-class ARM64 host and an AMD64 Docker host pull and start
  the same version through one multi-architecture manifest.
- Architecture inspection, health checks, restart/container-replacement data
  persistence, and graceful shutdown all pass.
- Representative inherited data survives tested upgrade and rollback flows.
- Production images contain no development-only preview code.
- Digest, SBOM, provenance, vulnerability, architecture, and post-publication
  GitHub Actions evidence is retained.
- Installation, upgrade, backup, restore, rollback, and troubleshooting
  documentation consistently uses Goo Buddy branding.
