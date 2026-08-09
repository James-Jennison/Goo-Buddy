# Multi-platform control maturity gate

## Product outcome

Goo Buddy will provide mature, capability-driven support for Bambu Lab,
Elegoo/OpenCentauri SDCP v3, and Klipper installations exposing Moonraker.
Elegoo and Moonraker support is not complete while it is monitoring-only:
where a printer's documented protocol and observed capabilities support an
operation, Goo Buddy must offer that operation safely and truthfully.

This is an approved product milestone for developing control capabilities. It
does **not** authorize a test run against a physical printer, a release,
publication, discovery, or a widening of network exposure. Those actions need
their own explicit approval.

## Non-negotiable safety contract

- Sources remain manual and opt-in. Goo Buddy never discovers printers or
  contacts a saved source until its owner enables it.
- Every command is capability-gated by the saved driver, the validated device
  capability report, and the caller's permission. A missing or uncertain
  capability is unavailable, never guessed.
- Controls must be explicit user actions with clear target, effect, and
  confirmation appropriate to their risk. A background refresh may never
  issue a control command.
- The command surface is closed and protocol-specific. It must not accept
  arbitrary URLs, JSON-RPC methods, G-code, shell commands, or raw SDCP
  payloads from a client.
- Sensitive endpoint configuration and API keys remain protected and are never
  exposed in ordinary API responses, UI views, logs, fixtures, or reports.
- Bambu behaviour remains covered by its existing regression surface. No new
  multi-platform feature may route a non-Bambu source through a Bambu command,
  queue, virtual-printer, upload, camera, file, maintenance, or credential
  path.
- An operation is advertised only after protocol evidence, simulator coverage,
  and approved hardware validation establish its behaviour. Until then the UI
  says unavailable.

## Delivery sequence

1. Establish the common capability and command contract, including permissions,
   idempotency, cancellation, status reconciliation, audit events, timeouts,
   and error states.
2. Implement each protocol through a closed adapter backed by documented,
   captured, redacted, or simulator-confirmed evidence. No generic transport
   escape hatch is allowed.
3. Build capability-gated Workshop controls and clear unavailable states.
4. Exercise the contract with deterministic protocol simulators, API tests,
   frontend tests, migration tests, and the complete local gate.
5. Conduct an explicitly approved, supervised hands-on validation with a
   compatible non-production printer. Record only redacted evidence and update
   the compatibility table.

## Automated delivery checklist

The supervisor treats every unchecked item in this section as an implementation
blocker. Mark an item complete only with its code, tests, and review evidence
in the same change.

- [x] Define a shared, persisted command and capability model that cannot
  represent an arbitrary transport request.
- [ ] Add role/permission checks and an auditable command lifecycle for
  non-Bambu sources, with idempotency, cancellation, timeout, and reconciliation
  behaviour.
- [ ] Add deterministic Elegoo SDCP v3 control simulators and redacted fixtures
  for each operation considered for support.
- [ ] Implement the closed Elegoo capability adapter and its API/UI paths,
  preserving manual activation, endpoint validation, and secret redaction.
- [ ] Add deterministic Moonraker control simulators and redacted fixtures for
  each operation considered for support.
- [ ] Implement the closed Moonraker capability adapter and its API/UI paths,
  preserving private-endpoint validation, protected API keys, and no generic
  JSON-RPC or G-code route.
- [ ] Add Workshop controls that disclose the target, operation, confirmation,
  pending state, result, and unavailable-capability explanation accessibly.
- [ ] Add regression coverage proving non-Bambu sources cannot use Bambu-only
  command, queue, upload, virtual-printer, file, camera, or maintenance paths.
- [ ] Add API, driver, simulator, and frontend tests for success, denial,
  disconnect, timeout, duplicate-command, stale-state, and restart recovery
  behaviour.
- [ ] Pass the complete local validation gate from a disposable Docker test
  context: `./test_all.sh`.

## Hands-on validation checklist

These items are intentionally outside the automated-ready state. They require
the later, specific approval to operate a physical device.

- [ ] Validate each claimed Elegoo model/firmware combination with a supervised
  test printer and record redacted compatibility evidence.
- [ ] Validate each claimed Moonraker/Klipper configuration with a supervised
  test printer and record redacted compatibility evidence.
- [ ] Validate disconnect, restart, and cancellation/reconciliation behaviour
  without leaving a printer in an unsafe or ambiguous state.
- [ ] Perform an accessibility and operator-review pass of destructive or
  consequential controls.

## Readiness definitions

**Automated candidate ready for hands-on test** means every automated delivery
item is checked and the selected automated gate passes for the same worktree.
It is not a release or a mature-support claim.

**Mature support** may be claimed only when the supervised hardware evidence
also completes, the compatibility documentation is updated, and the relevant
release approval is obtained. The scope remains limited to the validated
models, firmware, and operations.

## Supervisors

`scripts/goo_buddy_codex_supervisor.sh` is the implementation supervisor. It
runs one bounded Codex product task at a time in the named local tmux session
`goo-buddy-codex-supervisor`, waits 60 seconds, and continues until the
automated checklist is complete or a genuine human-only blocker is recorded.
It starts only from a clean product worktree aligned with `origin/main`. For
each completed bounded milestone, it runs the complete local gate, creates a
scoped commit, and pushes it to `origin/main`. It never publishes, deploys,
discovers devices, or contacts a printer. The owner-managed local `.codex/`
directory is preserved and ignored by the supervisor's clean-worktree check.

```bash
./scripts/goo_buddy_codex_supervisor.sh
tmux attach -t goo-buddy-codex-supervisor
tail -F .multi-platform-supervisor/worker.log
cat .multi-platform-supervisor/implementation-status.md
```

`scripts/supervise_multi_platform.sh` is the separate validation supervisor.
It provides evidence for the implementation worker; it is not a code-writing
worker.

Use [`scripts/supervise_multi_platform.sh`](../scripts/supervise_multi_platform.sh)
to continuously check the delivery state without modifying source code. By
default it does not contact a printer. Its optional local hardware mode makes
only the read-only checks described below.

```bash
# Run the focused, non-Docker gate once and write a local readiness report.
./scripts/supervise_multi_platform.sh --once

# Watch the worktree; run the focused gate after each source change.
./scripts/supervise_multi_platform.sh --watch --interval 60

# Wait until the automated candidate is ready, then exit successfully.
./scripts/supervise_multi_platform.sh --until-ready

# Include the explicitly configured lab printers in each focused validation.
./scripts/supervise_multi_platform.sh --until-ready --hardware-read-only --interval 60

# Run the project-wide local gate once, only in a disposable Docker context.
./scripts/supervise_multi_platform.sh --once --full
```

The focused gate runs Ruff, the integration-specific backend tests, and the
frontend type, lint, and test gates. `--full` delegates to `./test_all.sh`.
That script builds containers and tears down Docker Compose test resources, so
do not use it against a Docker context that holds valued application data. The
supervisor reports state under `.multi-platform-supervisor/`, which is ignored
by Git. `latest.md` is the current readiness report and `supervisor.log` is a
timestamped status-only stream suitable for `tail -f`. `worker.log` retains
the detailed gate output for monitoring. Before it is persisted, the
supervisor redacts endpoints, credentials, hardware/request identifiers,
filenames, and raw protocol payloads; it is deliberately not a packet capture.

### Authorized local hardware mode

`--hardware-read-only` is an explicit opt-in for an owner-provided lab setup.
It reads the two canonical private IPv4 values from the ignored file
`.multi-platform-supervisor/test-devices.env`:

```dotenv
ELEGOO_SDCP_HOST=private-ipv4-of-authorized-elegoo-printer
MOONRAKER_HOST=private-ipv4-of-authorized-moonraker-printer
```

The mode sends only the SDCP unicast identity lookup, heartbeat, and Cmd 0/1
information requests to Elegoo; and Moonraker's `GET /server/info`. It does
not send control, file, camera, G-code, JSON-RPC, upload, or configuration
requests. The addresses and raw responses are neither printed nor written to
the report. Any control validation remains a separate, explicitly approved
hands-on step. An unavailable configured lab printer is recorded as a skipped
hardware check, not a software-gate failure; the latest successful hardware
evidence remains distinct from current availability.
