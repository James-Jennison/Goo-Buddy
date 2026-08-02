# Fork-network detachment record

Status: **COMPLETE** as of 2026-08-02. Goo Buddy left GitHub's Bambuddy fork
network in place through **Settings → General → Danger Zone → Leave fork
network**. GitHub's permanent metadata-loss warning was accepted by the
repository owner. No delete/recreate, transfer, rename, visibility change,
upstream synchronization, or remote change occurred.

## Independent repository state

- Repository: `James-Jennison/Goo-Buddy`, public, default branch `main`.
- GitHub repository ID: `1318841601` (preserved).
- URL: `https://github.com/James-Jennison/Goo-Buddy` (preserved).
- Detachment baseline commit: `4d037de1c42e3576371db18c7537b9f8736c8de3`.
- GitHub state: `fork=false`; `parent` and `source` are absent.
- Historical common fork point:
  `82656c8760bd620bd31fbb31faa3024062e55e88`.
- Technical upstream remains
  `https://github.com/maziggy/bambuddy.git`; it is fetch-only by policy. Do
  not push to it. See [upstream review policy](UPSTREAM_SYNC.md).

Goo Buddy retains the complete Git history, applicable Bambuddy attribution,
copyright notices, and AGPL-3.0 obligations. Detachment established an
independent GitHub repository; it did not end the recurring, human-classified
review of relevant upstream security and compatibility changes.

## Mechanism and accepted risk

GitHub's documented in-place mechanism preserves Git commit metadata but is
permanent and does not retain issues, pull requests, wikis, stars, watchers,
comments, child forks, or other GitHub metadata. GitHub also does not promise
continuity for Actions history/artifacts, packages, settings, secrets, apps,
or individual security features.

- [Detaching a fork — GitHub Docs](https://docs.github.com/en/pull-requests/how-tos/work-with-forks/detaching-a-fork)
  (retrieved 2026-08-01)
- [Working with forks — GitHub Docs](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks)
  (retrieved 2026-08-01)
- [Duplicating a repository — GitHub Docs](https://docs.github.com/en/repositories/creating-and-managing-repositories/duplicating-a-repository)
  (retrieved 2026-08-01)

The manual delete/recreate alternative remains inappropriate: it would risk
additional loss of repository identity and configuration. Leaving the fork
network cannot be reversed or reconnected.

## Historical readiness evidence

The original before-state backup is retained unchanged outside this checkout:

```text
/mnt/faststorage/goo-buddy-backups/fork-detachment-readiness-20260801T231557Z/
```

Its `SHA256SUMS-COMPLETE` manifest digest is:

```text
0f44d077bc8862154e72662d717c5e7304d31c11dc66594934e38e0b2c98dbb1
```

All 271 manifest entries still verified after detachment. That snapshot records
122 origin refs, 77 tags, a 631 MiB bare mirror, a 629 MiB all-ref bundle, a
restoration rehearsal, sanitized GitHub metadata, and the pre-detachment
manual prerequisites. It ends at `c911a36d2403b8755a3aa1762fa5717d983fc66f`;
the documented readiness commit advanced `main` to `4d037de1…` before the UI
operation.

## Post-detachment comparison and snapshot

A separate, non-overwriting after-state snapshot was created at:

```text
/mnt/faststorage/goo-buddy-backups/fork-detachment-post-20260802T003432Z/
```

Its `SHA256SUMS-COMPLETE` digest is:

```text
1711eab675e1b2bffc2d15edd3c38939682c278af9b4cd96542924024a9b73d0
```

The snapshot includes an independent-origin bare mirror, an all-ref origin
bundle containing `main` at `4d037de1…`, a supplemental local-ref bundle,
sanitized post-detachment metadata, restoration notes, and the machine-readable
comparison. Both bundles verify, the mirror passes `git fsck`, and the final
commit plus the historical common fork point resolve. The original backup was
not modified.

| Resource | Before | After | Classification |
| --- | --- | --- | --- |
| Repository identity, URL, visibility, default branch | ID `1318841601`, public, `main` | Same | Preserved unchanged |
| Fork relationship | `fork=true`, parent/source `maziggy/bambuddy` | `fork=false`, no parent/source | Expected permanent detachment effect |
| Origin refs and tags | 122 refs, 77 tags | 122 refs, 77 tags | Preserved; only known `main` advance from `c911…` to `4d037…` |
| Labels, collaborators, rulesets | 9, 1, 0 | 9, 1, 0 | Preserved unchanged |
| Issues, pull requests, releases, child forks | 0 each | 0 each | No metadata to lose |
| Actions workflow definitions | 10 | 10 in the after-state snapshot; 9 after closeout | Preserved; inherited Repo Stats is removed below |
| Actions run/artifact records | 37 / 74 | 41 / 80 | Preserved at observation time; no continuity guarantee |
| Environments, variables, secret names, deploy keys, webhooks | 0 each | 0 each | Preserved unchanged |
| Pages, packages, installed Apps | API-limited | API-limited | Unavailable through the captured read-only scope; not inferred |
| Private vulnerability reporting | Disabled | Disabled | Preserved unchanged |

No workflow was triggered by the detachment itself. The failed historical
**GitHub Repo Stats** run predates detachment and is documented as inherited
automation, not a detachment failure.

## Inherited Repo Stats disposition

The scheduled **GitHub Repo Stats** workflow was removed after the
post-detachment audit. It had no README, documentation, Pages, badge, product,
or governance consumer; it was a Bambuddy-specific report generator that
hard-coded `maziggy/bambuddy`, an upstream Pages prefix, upstream GHCR paths,
and the absent `GHRS_GITHUB_API_TOKEN`. It also held `contents: write` and
used an unpinned third-party action. Reconfiguration would have required
retaining an unused statistics system and introducing credential scope with no
demonstrated Goo Buddy value.

The workflow file and its sole `ghcr_inject.py` helper were removed. The
existing `github-repo-stats` branch, its historical runs, artifacts, and data
were deliberately not deleted; they are separate archival-cleanup candidates
requiring future explicit approval. No active workflow now targets
`maziggy/bambuddy` for this automation.

## Ongoing audit and escalation

Future audits begin from clean `main` aligned with `origin/main`, verify the
independent repository fields and the two snapshots, and compare visible GitHub
settings against their sanitized exports. Re-enter or rotate secrets only by
name through GitHub's protected UI; never place secret values in source, logs,
or backup metadata.

If an unexpected GitHub result is found, stop administration, preserve the
snapshots and screenshots, avoid delete/recreate, and seek a separately
approved owner or GitHub Support escalation. The verified mirror/bundle can
recover Git objects only into a new controlled location; it cannot recreate
original GitHub identities, relationships, comments, stars, or Actions history.

Detachment is complete. It must not be attempted again, and it does not
authorize upstream synchronization, release publication, deployment, or
printer contact.
