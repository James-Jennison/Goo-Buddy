# Fork-network detachment readiness

Status: **READY WITH MANUAL PREREQUISITES** as of 2026-08-01. This document
records preservation work only. Goo Buddy remains a public fork of
`maziggy/bambuddy`; no fork-network, repository-setting, or remote change was
made while preparing it.

## Current relationship and evidence

- Repository: `James-Jennison/Goo-Buddy`, public, default branch `main`.
- Prepared commit: `c911a36d2403b8755a3aa1762fa5717d983fc66f`.
- GitHub repository ID: `1318841601`.
- Parent/source: `maziggy/bambuddy`.
- Recorded common fork point:
  `82656c8760bd620bd31fbb31faa3024062e55e88`.
- Local technical upstream remains
  `https://github.com/maziggy/bambuddy.git`; it is fetch-only by policy. Do
  not push to it. See [upstream review policy](UPSTREAM_SYNC.md).
- Attribution, Git history, and AGPL-3.0 obligations remain in force after any
  future detachment.

The current repository is public, reports 640,464 KiB of GitHub disk usage,
and reports zero child forks. The authenticated reviewer had `ADMIN`
permission when the inventory was made. Those facts meet the documented
eligibility conditions for GitHub's in-place **Leave fork network** option,
but GitHub exposes no read-only API that proves the control is present. Its
appearance in repository Settings must be confirmed on execution day.

## Official GitHub mechanism

GitHub's current official mechanism is **Settings → General → Danger Zone →
Leave fork network**. GitHub documents that it is available only for a public
fork under 1 GB with no child forks; it preserves Git commit metadata, is
permanent, and does **not** retain issues, pull requests, wikis, stars,
watchers, comments, child forks, or other metadata. Operations can be briefly
unavailable during the transition.

- [Detaching a fork — GitHub Docs](https://docs.github.com/en/pull-requests/how-tos/work-with-forks/detaching-a-fork)
  (retrieved 2026-08-01)
- [Working with forks — GitHub Docs](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks)
  (retrieved 2026-08-01)
- [Duplicating a repository — GitHub Docs](https://docs.github.com/en/repositories/creating-and-managing-repositories/duplicating-a-repository)
  (retrieved 2026-08-01)

Do **not** use GitHub's manual delete/recreate alternative for Goo Buddy. Its
own documentation warns that deleting a fork permanently deletes associated
pull requests and configurations. It is only an escalation fallback after a
separate, explicitly approved preservation and migration plan.

GitHub's detachment page does not explicitly guarantee preservation of the
repository ID, URL, redirects, Actions history/artifacts, package namespace,
settings, secrets, apps, or individual security features. Treat any expected
continuity for those resources as an inference to verify, not a promise.

## Readiness backup

The non-repository backup location is:

```text
/mnt/faststorage/goo-buddy-backups/fork-detachment-readiness-20260801T231557Z/
```

It is intentionally outside this checkout and was created without overwriting
an existing directory. Its final `SHA256SUMS-COMPLETE` manifest digest is:

```text
0f44d077bc8862154e72662d717c5e7304d31c11dc66594934e38e0b2c98dbb1
```

The package contains a 631 MiB bare mirror, a 629 MiB all-ref bundle, a 631
MiB retained bare restoration rehearsal, 2.7 MiB of sanitized GitHub metadata,
and reports. `git fsck --full --no-dangling` passed for the mirror and the
rehearsal; `git bundle verify` passed. The rehearsal resolves the prepared
commit and common fork point and contains 122 refs and 77 tags. No Git LFS
objects, wiki, releases, or release assets existed at capture time.

The metadata inventory contains endpoint responses and availability records for
repository settings, branches, refs, tags, collaborators, teams, rulesets,
labels, milestones, issues, pull requests and review comments, releases,
forks, subscribers, stargazers, Actions workflows/runs/artifact metadata,
environments, variables, secret names, deploy keys, webhooks, Pages, custom
properties, and accessible security configuration. Webhook destinations are
redacted. Secret values, private keys, tokens, headers, and downloaded Actions
artifacts are not included. Verify `SHA256SUMS-COMPLETE` before using any
artifact; the included backup manifest has restoration commands.

## Preservation matrix

| Resource | Current state | Git backup | Metadata backup | Expected detachment behavior | Automatic restoration | Manual action / irreversible risk | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Commit graph, branches, tags, refs | 122 refs; 77 tags | Yes: mirror, bundle, rehearsal | Ref inventories | Git commit metadata preserved | Yes | Verify all refs after detachment | `git fsck`, bundle and rehearsal reports |
| Parent/source fork relation | `maziggy/bambuddy` | History only | Repository record | Removed permanently | No | Preserve `upstream` remote and review policy locally | GitHub detachment docs; inventory |
| Repository slug, URL, ID, redirects | Current slug and ID recorded | No | Repository record | Not explicitly guaranteed | No | Confirm exact slug/URL/ID after UI action; stop on unexpected change | GitHub docs/inventory |
| Issues, comments, labels, milestones | 0 issues; 9 labels; 0 milestones/comments | No | Yes | GitHub warns metadata is not retained | Labels could be recreated | Original identities/comments cannot be recreated | REST exports; detachment docs |
| Pull requests, reviews, threads | 0 | Git PR refs when advertised | Yes | Not retained | No | Original identities/threads cannot be recreated | REST exports; detachment docs |
| Discussions | Disabled; none | No | Explicit disabled-state record | Not retained as metadata | No | Re-enable/configure only with separate approval | Repository inventory |
| Wiki | Disabled; absent | No | Explicit absence record | Not retained | N/A | None at capture time | `has_wiki=false` |
| Releases and assets | 0 | Tags only | Release metadata export | Not retained as metadata | Tags only | Release identities/assets would need separate archive/recreation | Releases export; detachment docs |
| Stars, watchers/subscribers | 0 each | No | Counts/list exports | Not retained | No | Original relationships cannot be recreated | Repository/follower exports; detachment docs |
| Child forks | 0 | No | Fork export | Must be zero for UI option; GitHub warns child forks are not retained | No | Recheck immediately before execution; stop if nonzero | Repository API; detachment docs |
| Branch protections/rulesets | 0 rulesets; no protection endpoint returned for 45 branches | No | Per-branch/ruleset exports | Not explicitly guaranteed | Re-enter only if needed | Recheck all branches after action | Branch/ruleset inventory |
| Actions workflows | 10 workflow files | Yes, in Git | Workflow metadata | Source survives with Git; runs/settings not guaranteed | Workflow files only | Re-enable/check permissions and schedules manually | Git mirror and Actions export |
| Actions runs/artifacts/caches | 37 run records; 74 artifact records | No | Run/artifact metadata only | Not explicitly guaranteed | No | Download any payload needed before detachment; caches/runs may be lost | Actions exports; GitHub docs warning |
| Environments, variables, secrets | 0 environments; no repository variable or secret names returned | No | Names/available non-secret values only | Not explicitly guaranteed | No secret values | Record/re-enter/rotate necessary values and environment protections manually | API exports; secrets intentionally unreadable |
| Deploy keys, webhooks, GitHub Apps | 0 deploy keys; 0 hooks; app-installation endpoint unavailable | No | Sanitized key/hook metadata and availability | Not explicitly guaranteed | No | Inventory visible app installation and reauthorize/recreate settings as needed | API export/limitations |
| Packages/GHCR | Publication not authorized; package query lacked `read:packages` | No | Limitation record | Not explicitly guaranteed | No | Manually verify Packages tab and preserve package/version/digest evidence | API scope limitation |
| Security configuration/alerts | CodeQL workflow present; Dependabot and secret scanning disabled/unavailable | Workflow source only | Accessible endpoint results/limitations | Not explicitly guaranteed | Configuration only where exported | Recheck CodeQL, Dependabot, secret scanning, advisories, private reporting after action | Security exports and [security policy](../SECURITY.md) |
| Pages, visibility, permissions, topics, custom properties | Pages absent; public; topics/settings exported | No | Repository/settings exports | Not explicitly guaranteed | Some settings can be recreated | Manually verify visibility, features, collaborators, teams, permissions, topics, homepage | Repository and capability exports |
| Attribution, license, upstream review policy | AGPL-3.0 and attribution in Git | Yes | N/A | Must continue | Yes | Keep upstream remote; never misrepresent provenance | Repository files and [upstream policy](UPSTREAM_SYNC.md) |

## Manual prerequisites and classification

The classification is **READY WITH MANUAL PREREQUISITES**, not `READY`, because
the irreversible action must be observed and confirmed by an administrator and
some GitHub resources cannot be exported or restored with their original
identity.

Before a separately approved execution:

1. Confirm the backup directory, `SHA256SUMS`, mirror, bundle, and restoration
   rehearsal still verify.
2. Confirm `main` is clean and equals `origin/main`; record the exact HEAD.
3. Recheck public visibility, under-1-GB size, zero child forks, and `ADMIN`
   access. Confirm **Leave fork network** appears in Settings.
4. Decide whether any Actions artifact payload must be retained; download only
   specifically approved artifacts before acting.
5. Manually inspect and record any GitHub App installation, Packages/GHCR
   state, security features, branch settings, environments, variables,
   secrets, deploy keys, hooks, Pages, and collaborator/permission settings
   not available through the captured API scope. Never export secret values;
   prepare a secure re-entry/rotation record by name only.
6. Confirm no new issues, PRs, discussions, releases, stars, watchers, or
   child forks need preservation. If any now exist, update the exports and
   reconsider the irreversible metadata loss.
7. Obtain a new, explicit detachment execution approval naming the exact HEAD,
   backup digest, authorized administrator, and acceptable metadata loss.

## Future execution runbook — separate approval required

### Preflight stop conditions

Stop without detaching if the backup checksum fails; the branch is dirty or
diverged; the UI option is absent; visibility/size/child-fork eligibility has
changed; a new metadata resource lacks an approved preservation decision; the
administrator cannot confirm the warning; GitHub presents an unexpected URL,
ownership, permission, or deletion/recreation flow; or any required security
workflow is failing.

### Controlled execution

1. Freeze repository administration and record final before-state screenshots
   and non-secret settings inventory outside the repository.
2. Re-run the backup verification and save the final pre-action HEAD/ref list.
3. In GitHub Settings → General → Danger Zone, use only **Leave fork network**.
   Do not delete, transfer, duplicate, recreate, rename, or change visibility.
4. Read GitHub's warning, verify the repository name, and complete the UI
   confirmation. Do not run a local mirror push or change either Git remote.
5. Wait for GitHub to finish; do not make repository changes during the short
   availability interruption.

### Post-detachment verification

1. Confirm the same expected repository slug/URL and record the resulting ID,
   visibility, default branch, branch list, tags, commit graph, and AGPL files.
2. Confirm the repository no longer shows a fork parent/source relationship.
3. Re-run CI, CodeQL, Security Audit, and AMD64/ARM64 validation from an exact
   reviewed commit; recheck Actions permissions and workflow availability.
4. Verify branch/ruleset, collaborators, repository features, security
   configuration, Pages, environments, variables, secrets, deploy keys,
   webhooks, Apps, Packages, and notification settings against the inventory.
5. Reconfigure only separately authorized settings. Re-enter or rotate secrets
   by name through GitHub's protected UI; never paste them into source, logs,
   or the readiness archive.
6. Confirm the local `upstream` remote remains a fetch-only technical reference
   and retain the recurring upstream security/compatibility review process.

### Escalation and rollback

Leaving the fork network is permanent: GitHub documents that it cannot be
reconnected. There is no automatic rollback. If GitHub produces an unexpected
result, stop all further administration, preserve screenshots and the backup,
avoid delete/recreate, and seek a separately approved GitHub Support or
repository-owner escalation. Use the verified mirror/bundle only to recover
Git objects into a **new** controlled location if necessary; it cannot restore
original GitHub identities, relationships, stars, comments, or Actions history.

## What this readiness work did not do

It did not detach or alter the fork relationship; change any GitHub setting,
remote, protection, secret, release, package, deployment, or repository
metadata; synchronize Bambuddy; contact a printer; or publish a container.
Actual detachment remains a separate, explicit, irreversible goal.
