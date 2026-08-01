# Upstream Bambuddy security and compatibility review

Goo Buddy retains [maziggy/bambuddy](https://github.com/maziggy/bambuddy) as a
technical upstream, even after any separately approved GitHub fork-network
detachment. Ordinary workflows use `origin`
(`https://github.com/James-Jennison/Goo-Buddy.git`) for Goo Buddy and treat
`upstream` (`https://github.com/maziggy/bambuddy.git`) as fetch-only. Never
push to upstream.

The recorded common fork point is
`82656c8760bd620bd31fbb31faa3024062e55e88`. The latest fetched upstream SHA is
`d36632db0f0ad45d91b86a3b772c796fdb478586`; a last-reviewed SHA has not yet
been established under this new recurring process. Goo Buddy retains applicable
AGPL, copyright, attribution, and Git-history obligations.

The 2026-08-01 detachment-readiness package preserves the fork point, Git
history, and this policy without changing the GitHub fork relationship. See
[fork-detachment readiness](FORK_DETACHMENT_READINESS.md). A future detachment
must retain this remote as a technical reference and continue the recurring
human-classified review process.

## Recurring review procedure

Run this review monthly and whenever Bambuddy publishes a security advisory or
significant inherited-functionality release, before a Goo Buddy stable release,
or when Goo Buddy's own security tooling flags a possible inherited issue.

1. Start from clean Goo Buddy `main` aligned with `origin/main`.
2. Fetch `upstream` without merging, rebasing, cherry-picking, or otherwise
   changing the worktree. Record the previous and newly fetched upstream SHAs
   and the bounded commit list between them.
3. Review security-sensitive areas first: authentication/authorization,
   secret and printer credentials, network clients/TLS, uploads/archives, path
   handling, migrations, command execution, virtual-printer services,
   dependencies, and containers.
4. Classify each relevant change as a security fix; dependency vulnerability
   correction; Bambu protocol/model support; inherited bug fix; performance or
   reliability fix; test/CI improvement; upstream branding/product behavior;
   multi-platform conflict; already independently addressed; or breaking/
   ambiguous change requiring design review.
5. Port only applicable work through reviewable Goo Buddy-specific commits.
   Never blindly merge upstream. Record intentionally skipped work and why.
6. Preserve the Elegoo and Moonraker read-only boundaries, capability-driven
   architecture, Workshop UX, migration safety, and production exclusion of
   synthetic preview code. Run relevant regression, security, architecture,
   and migration checks, then require normal review and CI before publication.

## Independent security responsibility

Goo Buddy independently runs CodeQL, dependency auditing, Trivy/container and
secret scanning, AMD64/ARM64 validation, responsible disclosure, and security
documentation/supported-version policy. SBOM and provenance checks are added
when container publication is implemented. Public upstream commits, releases,
and advisories may be reviewed, but Goo Buddy must not rely on Bambuddy finding
vulnerabilities first. Private embargoed advisories are unavailable unless an
upstream maintainer explicitly includes Goo Buddy.

No scheduled workflow may automatically synchronize, merge, or cherry-pick
upstream. A future notification-only workflow may fetch metadata and open an
issue when upstream advances; it may not modify source, create commits or code
PRs, or bypass human classification.

## Fork-network-detachment prerequisite

Any future detachment proposal must verify this remote and fork point, record a
last-reviewed upstream SHA, preserve repository metadata/backups and required
attribution, and show Goo Buddy's independent security workflows green. It is a
separate, irreversible goal; this policy does not authorize detachment or
upstream synchronization.
