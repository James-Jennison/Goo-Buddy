# First classified Bambuddy upstream review — 2026-08-02

## Scope and method

This is Goo Buddy's first recurring upstream security and compatibility review.
It was performed from clean Goo Buddy `main` at
`64bd8d4d67a2e703a669b69f13047860f6d970cf` with no upstream merge, rebase,
cherry-pick, patch application, code import, dependency change, or upstream
push.

- Reviewer method: human-classified, evidence-backed inspection of each
  upstream commit and its current Goo Buddy counterpart.
- Historical common fork point:
  `82656c8760bd620bd31fbb31faa3024062e55e88`.
- Previous classified baseline: none; this is the first classified review.
- Review branch: `upstream/main`, confirmed as Bambuddy's default branch by
  read-only remote inspection.
- Locally known pre-fetch tip and fetched tip:
  `d36632db0f0ad45d91b86a3b772c796fdb478586`.
- Fetch time: `2026-08-02T01:04:03Z`.
- Frozen target: `d36632db0f0ad45d91b86a3b772c796fdb478586`. Later upstream
  movement is outside this review.
- Exact reviewed range:
  `82656c8760bd620bd31fbb31faa3024062e55e88..d36632db0f0ad45d91b86a3b772c796fdb478586`.

The range contains two non-merge commits and no merge groups. No upstream tag
points at the frozen target. Bambuddy's `v1.2.6b1-daily.20260801` release is
on a different history path and is not part of this frozen `main` review.

The machine-readable companion inventory is
[`2026-08-02-first-classified-review.json`](2026-08-02-first-classified-review.json).

## Summary

| Primary category | Items | Disposition | Priority |
| --- | ---: | --- | --- |
| Inherited bug fix | 1 | ADOPTED — CONTRIBUTOR GUIDANCE ALIGNED | P3 complete |
| Inapplicable branding or project administration | 1 | REJECT — INAPPLICABLE BRANDING/ADMINISTRATION | N/A |
| Security fix, dependency correction, Bambu protocol/model support, conflicting architecture, already superseded, needs deeper investigation | 0 | — | — |

There are no open P0, P1, P2, or P3 findings. The single P3 item was
contributor-documentation accuracy only; its adoption does not change runtime,
dependencies, printer behaviour, or security behaviour. No public upstream
security advisory was published in this two-commit range. A public upstream
advisory visible during the review predates the common fork point and is
outside this range; it is not evidence of a new post-fork finding.

## Per-commit evidence and disposition

| Upstream commit | Subject / upstream reference | Changed paths | Classification and evidence | Goo Buddy counterpart and exposure | Disposition / priority |
| --- | --- | --- | --- | --- | --- |
| [`aa074152`](https://github.com/maziggy/bambuddy/commit/aa07415270f811c653aadfca31a9b53268ee8347) | `Updated CONTRIBUTING.md`; no associated PR or issue exposed by GitHub | `CONTRIBUTING.md` (12 additions, 15 deletions) | **Inherited bug fix.** Replaces a stale fixed locale list and “all three” wording with runtime-discovered locale parity guidance. It changes contributor documentation only: no authentication, secret, dependency, network, Bambu protocol, printer-control, or multi-platform behaviour. | Goo Buddy's `CONTRIBUTING.md` now directs contributors to the locale directory as the source of truth and to `npm run check:i18n`; the existing implementation discovers every locale and validates the stronger contract. | **ADOPTED — CONTRIBUTOR GUIDANCE ALIGNED — P3 complete.** The wording was adapted in Goo Buddy language without changing runtime or importing upstream code. |
| [`d36632d`](https://github.com/maziggy/bambuddy/commit/d36632db0f0ad45d91b86a3b772c796fdb478586) | `Updated README`; no associated PR or issue exposed by GitHub | `README.md` (1 addition, 1 deletion) | **Inapplicable branding or project administration.** Changes Bambuddy’s marketing phrase from a model-count claim to “an entire print farm.” It has no security, dependency, Bambu protocol, persistence, lifecycle, or compatibility effect. | Goo Buddy has its own multi-platform README and attribution boundary. This wording targets Bambuddy-only identity and is not a functional correction. Patch-id comparison found no equivalent commit, as expected for intentionally different branding. | **REJECT — INAPPLICABLE BRANDING/ADMINISTRATION — N/A.** Do not port. |

## Security, dependency, and product-boundary assessment

- **Security and dependencies:** neither reviewed patch touches code, lockfiles,
  containers, authentication, credentials, TLS, uploads, archives, paths,
  migrations, command execution, virtual-printer services, or dependencies.
  There is no confirmed Goo Buddy exposure or remediation action from this
  range.
- **Bambu compatibility:** neither patch changes Bambu protocol, models, MQTT,
  camera, AMS, telemetry, controls, or firmware handling.
- **Multi-platform and read-only boundaries:** neither patch affects the
  driver-authoritative labels, retained/current semantics, Elegoo SDCP
  allowlist, Moonraker read-only method set, discovery policy, or synthetic
  preview exclusion. No architectural conflict requires remediation.
- **Upstream sources consulted:** commit detail and related-pull endpoints for
  both commits returned no associated pull request; Bambuddy's public releases
  and advisory metadata were inspected read-only. The reviewed commits have
  no associated release or advisory.

## Sources

- [Bambuddy `main` at the frozen target](https://github.com/maziggy/bambuddy/tree/d36632db0f0ad45d91b86a3b772c796fdb478586)
- [Upstream commit `aa074152`](https://github.com/maziggy/bambuddy/commit/aa07415270f811c653aadfca31a9b53268ee8347)
- [Upstream commit `d36632d`](https://github.com/maziggy/bambuddy/commit/d36632db0f0ad45d91b86a3b772c796fdb478586)
- [Public upstream release metadata](https://github.com/maziggy/bambuddy/releases)
- [Public upstream advisory metadata](https://github.com/maziggy/bambuddy/security/advisories)

## Follow-up and next baseline

Completed follow-up: **Goo Buddy contributor i18n guidance now matches the
runtime-discovered locale parity contract.** This was P3 documentation
maintenance, not a security or product remediation; it introduced no runtime
or upstream synchronization change.

The next recurring review starts strictly after the frozen target:

```text
d36632db0f0ad45d91b86a3b772c796fdb478586..upstream/main-at-next-freeze
```

The historical common fork point remains unchanged. `upstream` remains a
fetch-only technical reference by policy; future reviews must be human
classified and must never automatically merge, rebase, cherry-pick, or push
upstream code.
