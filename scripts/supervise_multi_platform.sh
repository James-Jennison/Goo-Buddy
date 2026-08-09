#!/usr/bin/env bash
#
# Local, non-mutating delivery supervisor for the multi-platform maturity goal.
# It never contacts printers, changes source files, publishes artifacts, or
# starts Docker unless the caller explicitly selects --full.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECKLIST="$ROOT/docs/MULTI_PLATFORM_MATURITY.md"
REPORT_DIR="${GOO_BUDDY_SUPERVISOR_DIR:-$ROOT/.multi-platform-supervisor}"
DEVICE_CONFIG="$REPORT_DIR/test-devices.env"
WORKER_LOG="$REPORT_DIR/worker.log"
MODE="once"
PROFILE="focused"
INTERVAL=60
HARDWARE_READ_ONLY=false

if [ -x "$ROOT/venv/bin/ruff" ]; then
    RUFF="$ROOT/venv/bin/ruff"
else
    RUFF="${GOO_BUDDY_RUFF:-ruff}"
fi

usage() {
    cat <<'EOF'
Usage: ./scripts/supervise_multi_platform.sh [--once|--watch|--until-ready] [--full] [--hardware-read-only] [--interval SECONDS]

Modes:
  --once          Run the selected gate once (default).
  --watch         Run immediately and again after a worktree change.
  --until-ready   Watch until the automated candidate is ready, then exit 0.

Profiles:
  --full          Run ./test_all.sh. This builds containers and may tear down
                  Docker Compose test resources; use only a disposable Docker
                  context. The default focused profile does not use Docker.
  --hardware-read-only
                  Validate the owner-configured Elegoo and Moonraker lab
                  printers through their closed read-only paths. Requires the
                  ignored .multi-platform-supervisor/test-devices.env file.

Other:
  --interval N    Worktree polling interval for --watch/--until-ready (default: 60).
  -h, --help      Show this help.

Reports are written to .multi-platform-supervisor/ and are never committed.
EOF
}

die() {
    printf 'supervisor: %s\n' "$*" >&2
    exit 2
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --once) MODE="once" ;;
        --watch) MODE="watch" ;;
        --until-ready) MODE="until-ready" ;;
        --full) PROFILE="full" ;;
        --hardware-read-only) HARDWARE_READ_ONLY=true ;;
        --interval)
            shift
            [ "$#" -gt 0 ] || die "--interval requires a positive integer"
            INTERVAL="$1"
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *) die "unknown option: $1" ;;
    esac
    shift
done

[[ "$INTERVAL" =~ ^[1-9][0-9]*$ ]] || die "--interval must be a positive integer"
[ -f "$CHECKLIST" ] || die "missing checklist: $CHECKLIST"

umask 077
mkdir -p "$REPORT_DIR"
chmod 700 "$REPORT_DIR"
[ ! -f "$DEVICE_CONFIG" ] || chmod 600 "$DEVICE_CONFIG"
exec 9>"$REPORT_DIR/supervisor.lock"
if ! flock -n 9; then
    die "another multi-platform supervisor is already running"
fi

worktree_fingerprint() {
    {
        git -C "$ROOT" rev-parse HEAD
        git -C "$ROOT" status --porcelain=v1 --untracked-files=all
    } | sha256sum | awk '{print $1}'
}

automated_blockers() {
    awk '
        /^## Automated delivery checklist$/ { in_section = 1; next }
        /^## / { if (in_section) exit }
        in_section && /^- \[ \]/ { sub(/^- \[ \] /, ""); print }
    ' "$CHECKLIST"
}

hardware_blockers() {
    awk '
        /^## Hands-on validation checklist$/ { in_section = 1; next }
        /^## / { if (in_section) exit }
        in_section && /^- \[ \]/ { sub(/^- \[ \] /, ""); print }
    ' "$CHECKLIST"
}

log_event() {
    printf '%s mode=%s profile=%s hardware_read_only=%s %s\n' \
        "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
        "$MODE" "$PROFILE" "$HARDWARE_READ_ONLY" "$*" >> "$REPORT_DIR/supervisor.log"
}

redact_worker_output() {
    sed -E \
        -e 's#https?://[^[:space:]"'"'"'<>]+#<endpoint>#gI' \
        -e 's#([0-9]{1,3}\.){3}[0-9]{1,3}#<ipv4>#g' \
        -e 's#([[:xdigit:]]{2}:){5}[[:xdigit:]]{2}#<mac-address>#gI' \
        -e 's#sdcp/(request|response|status|attributes)/[^[:space:]"'"'"'}]+#sdcp/\1/<redacted>#gI' \
        -e 's#((api[_-]?key|access[_-]?code|token|password|authorization|mainboard_?id|serial_?number|request_?id|task_?id|filename)[[:space:]"'"'"':=]+)[^,[:space:]"'"'"'}]+#\1<redacted>#gI'
}

config_value() {
    local key="$1"
    local value=""
    [ -f "$DEVICE_CONFIG" ] || return 1
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            "$key"=*)
                [ -z "$value" ] || return 1
                value="${line#*=}"
                ;;
        esac
    done < "$DEVICE_CONFIG"
    [ -n "$value" ] || return 1
    printf '%s' "$value"
}

run_gate() {
    local name="$1"
    shift
    printf '\n==> %s\n' "$name"
    log_event "gate-start name=$(printf '%s' "$name" | tr ' ' '-')"
    if "$@" 2>&1 | redact_worker_output | tee -a "$WORKER_LOG"; then
        GATE_RESULTS+=("$name|PASS")
        log_event "gate-pass name=$(printf '%s' "$name" | tr ' ' '-')"
        return 0
    fi
    GATE_RESULTS+=("$name|FAIL")
    log_event "gate-fail name=$(printf '%s' "$name" | tr ' ' '-')"
    return 1
}

run_focused_gate() {
    local outcome=0
    run_gate "Backend format and lint" bash -c 'cd "$1/backend" && "$2" check && "$2" format --check' _ "$ROOT" "$RUFF" || outcome=1
    run_gate "Elegoo and Moonraker backend tests" bash -c '
        cd "$1/backend" &&
        ../venv/bin/python3 -m pytest -q -n auto \
          tests/unit/drivers/test_elegoo_sdcp_v3.py \
          tests/unit/drivers/test_moonraker.py \
          tests/unit/services/test_elegoo_sdcp_manager.py \
          tests/unit/services/test_elegoo_sdcp_read_only.py \
          tests/unit/services/test_moonraker_read_only.py \
          tests/integration/test_elegoo_sdcp_api.py \
          tests/integration/test_moonraker_api.py \
          tests/unit/test_elegoo_sdcp_migration.py \
          tests/unit/test_moonraker_migration.py
    ' _ "$ROOT" || outcome=1
    run_gate "Frontend type, lint, and tests" bash -c 'cd "$1/frontend" && npx tsc --noEmit && npm run lint && npm run test:run' _ "$ROOT" || outcome=1
    return "$outcome"
}

run_hardware_read_only_gate() {
    local elegoo_host moonraker_host status
    elegoo_host="$(config_value ELEGOO_SDCP_HOST)" || {
        printf 'supervisor: missing a valid local Elegoo test-device configuration\n' >&2
        return 1
    }
    moonraker_host="$(config_value MOONRAKER_HOST)" || {
        printf 'supervisor: missing a valid local Moonraker test-device configuration\n' >&2
        return 1
    }
    printf '\n==> Authorized hardware read-only validation\n'
    log_event "gate-start name=Authorized-hardware-read-only-validation"
    env \
        ELEGOO_SDCP_HOST="$elegoo_host" \
        MOONRAKER_HOST="$moonraker_host" \
        "$ROOT/venv/bin/python3" "$ROOT/scripts/validate_test_printers.py" 2>&1 | redact_worker_output | tee -a "$WORKER_LOG"
    status=${PIPESTATUS[0]}
    if [ "$status" -eq 0 ]; then
        GATE_RESULTS+=("Authorized hardware read-only validation|PASS")
        log_event "gate-pass name=Authorized-hardware-read-only-validation"
        return 0
    fi
    if [ "$status" -eq 2 ]; then
        GATE_RESULTS+=("Authorized hardware read-only validation|SKIP")
        log_event "gate-skip name=Authorized-hardware-read-only-validation reason=target-unavailable"
        return 0
    fi
    GATE_RESULTS+=("Authorized hardware read-only validation|FAIL")
    log_event "gate-fail name=Authorized-hardware-read-only-validation"
    return 1
}

write_report() {
    local gate_status="$1"
    local automated_count="$2"
    local hardware_count="$3"
    local report="$REPORT_DIR/latest.md"
    local source_head
    source_head="$(git -C "$ROOT" rev-parse --short HEAD)"

    {
        printf '# Multi-platform delivery supervisor report\n\n'
        printf -- '- Generated: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
        printf -- '- Source commit: `%s`\n' "$source_head"
        printf -- '- Profile: `%s`\n' "$PROFILE"
        printf -- '- Authorized hardware read-only validation: `%s`\n' "$HARDWARE_READ_ONLY"
        printf -- '- Worktree: %s\n\n' "$(if [ -n "$(git -C "$ROOT" status --porcelain)" ]; then printf 'changes present'; else printf 'clean'; fi)"
        printf '## Gate results\n\n'
        for result in "${GATE_RESULTS[@]}"; do
            printf -- '- %s: **%s**\n' "${result%%|*}" "${result##*|}"
        done
        printf '\n## Readiness\n\n'
        if [ "$gate_status" = "PASS" ] && [ "$automated_count" -eq 0 ]; then
            printf 'The automated candidate is **ready for hands-on testing**.\n\n'
        elif [ "$gate_status" = "FAIL" ]; then
            printf 'The automated candidate is **blocked by a failing gate**.\n\n'
        else
            printf 'The automated candidate is **blocked by unchecked delivery work**.\n\n'
        fi
        printf -- '- Automated delivery blockers: %s\n' "$automated_count"
        printf -- '- Hands-on validation items remaining: %s\n' "$hardware_count"
    } > "$report"
}

run_cycle() {
    GATE_RESULTS=()
    local before after gate_status="PASS" automated_count hardware_count
    before="$(worktree_fingerprint)"

    if [ "$PROFILE" = "full" ]; then
        printf 'Running the complete gate. Confirm this is a disposable Docker context.\n'
        run_gate "Complete local gate" bash -c 'cd "$1" && ./test_all.sh' _ "$ROOT" || gate_status="FAIL"
    else
        run_focused_gate || gate_status="FAIL"
    fi
    if [ "$HARDWARE_READ_ONLY" = true ]; then
        run_hardware_read_only_gate || gate_status="FAIL"
    fi

    after="$(worktree_fingerprint)"
    if [ "$before" != "$after" ]; then
        printf 'supervisor: source changed while the gate ran; result is stale and will be rerun.\n' >&2
        GATE_RESULTS+=("Worktree stability|FAIL")
        gate_status="FAIL"
    fi

    automated_count="$(automated_blockers | wc -l | tr -d ' ')"
    hardware_count="$(hardware_blockers | wc -l | tr -d ' ')"
    write_report "$gate_status" "$automated_count" "$hardware_count"

    printf '\nReadiness report: %s\n' "$REPORT_DIR/latest.md"
    if [ "$gate_status" = "PASS" ] && [ "$automated_count" -eq 0 ]; then
        log_event "state=ready automated_blockers=0 hardware_blockers=$hardware_count"
        printf 'Automated candidate ready for hands-on testing.\n'
        return 0
    fi
    if [ "$gate_status" = "FAIL" ]; then
        log_event "state=failed-gate automated_blockers=$automated_count hardware_blockers=$hardware_count"
        printf 'Automated candidate blocked by failing gate.\n' >&2
        return 1
    fi
    log_event "state=delivery-blocked automated_blockers=$automated_count hardware_blockers=$hardware_count"
    printf 'Automated candidate blocked by %s unchecked delivery item(s).\n' "$automated_count" >&2
    return 3
}

last_fingerprint=""
while :; do
    current_fingerprint="$(worktree_fingerprint)"
    if [ "$MODE" = "once" ] || [ "$current_fingerprint" != "$last_fingerprint" ]; then
        run_cycle
        cycle_status=$?
        if [ "$cycle_status" -eq 0 ]; then
            [ "$MODE" = "until-ready" ] && exit 0
        elif [ "$MODE" = "once" ]; then
            exit "$cycle_status"
        fi
        last_fingerprint="$(worktree_fingerprint)"
    fi

    [ "$MODE" = "once" ] && exit 0
    printf 'Watching for source changes; next check in %ss.\n' "$INTERVAL"
    sleep "$INTERVAL"
done
