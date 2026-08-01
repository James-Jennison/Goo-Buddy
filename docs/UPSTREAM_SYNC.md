# Upstream sync policy

Goo Buddy tracks [maziggy/bambuddy](https://github.com/maziggy/bambuddy) as
the `upstream` remote. The fork's `origin` is
`James-Jennison/Goo-Buddy`.

## Safe workflow

1. Fetch both remotes without altering a working tree.
2. Create a dedicated, reviewable sync branch from the production fork's
   default branch.
3. Merge or rebase only after recording the exact upstream SHA and reviewing
   licensing, migration, security, and printer-control changes.
4. Run the affected backend, frontend, Docker, and ARM64 checks before any
   merge proposal.
5. Keep Goo Buddy driver additions isolated under `backend.app.drivers` where
   possible; do not rename Bambuddy database objects, APIs, package names, or
   legal notices merely for branding.

## Conflict policy

Never resolve a conflict by discarding either side. Favor upstream behavior for
existing Bambu paths unless a separately reviewed Goo Buddy safety requirement
requires a change. Re-evaluate capability claims, read-only safety gates,
schema compatibility, and licensing after every conflict resolution. Stop for
an unresolved security, migration, attribution, or physical-printer-control
conflict; record the conflict and request review rather than guessing.

No upstream sync may force-push, rewrite history, change a production deployment,
or contact a printer without explicit authorization.
