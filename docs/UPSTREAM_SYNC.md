# Upstream Bambuddy security and compatibility review

Goo Buddy is an independent GitHub repository after its completed 2026-08-02
in-place fork-network detachment. It retains
[maziggy/bambuddy](https://github.com/maziggy/bambuddy) as a technical
upstream. Ordinary workflows use `origin`
(`https://github.com/James-Jennison/Goo-Buddy.git`) for Goo Buddy and treat
`upstream` (`https://github.com/maziggy/bambuddy.git`) as fetch-only. Never
push to upstream.

The recorded common fork point is
`82656c8760bd620bd31fbb31faa3024062e55e88`. The first human-classified review
froze `upstream/main` at `d36632db0f0ad45d91b86a3b772c796fdb478586` on
2026-08-02. That SHA is now the recurring-review baseline: the next review
starts after it, never from the common fork point again. See the
[first classified review record](upstream-reviews/2026-08-02-first-classified-review.md).
Goo Buddy retains applicable AGPL, copyright, attribution, and Git-history
obligations.

The 2026-08-01 before-state readiness package and 2026-08-02 after-state
snapshot preserve the fork point, Git history, and this policy. See the
[fork-network detachment record](FORK_DETACHMENT_READINESS.md). The completed
detachment leaves this remote as a technical reference and the recurring
human-classified review process remains mandatory.

## Recurring review procedure

Run this review monthly and whenever Bambuddy publishes a security advisory or
significant inherited-functionality release, before a Goo Buddy stable release,
or when Goo Buddy's own security tooling flags a possible inherited issue.

1. Start from clean Goo Buddy `main` aligned with `origin/main`.
2. Fetch the documented upstream review branch without merging, rebasing,
   cherry-picking, or otherwise changing the worktree. Record the previous and
   newly fetched SHAs, freeze the latter immediately, and inspect only the
   bounded range after the last classified baseline through that frozen SHA.
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

## Completed detachment audit record

The completed detachment preserved `origin`, this `upstream` remote, the
recorded fork point, attribution, and independent security workflows. It did
not synchronize, merge, rebase, or cherry-pick upstream history. Future work
continues under the recurring review procedure above; it must never attempt to
rejoin a fork network or automatically synchronize Bambuddy.
