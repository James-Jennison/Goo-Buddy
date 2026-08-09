#!/usr/bin/env bash
#
# Local implementation supervisor for Goo Buddy's multi-platform maturity
# milestone.  It runs one bounded Codex implementation task at a time and
# waits between tasks. It pushes only fully validated, bounded milestones to
# the documented source-of-truth branch. It never publishes, deploys, or
# contacts a printer.

set -Eeuo pipefail
umask 077

readonly ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly CODEX_BIN="${GOO_BUDDY_CODEX_BIN:-$(command -v codex || true)}"
readonly STATE_DIR="${GOO_BUDDY_SUPERVISOR_DIR:-$ROOT/.multi-platform-supervisor}"
readonly WORKER_LOG="$STATE_DIR/worker.log"
readonly SUPERVISOR_LOG="$STATE_DIR/supervisor.log"
readonly STATUS_PATH="$STATE_DIR/implementation-status.md"
readonly LOCK_PATH="$STATE_DIR/implementation.lock"
readonly STOP_SENTINEL="$STATE_DIR/human-only-blocker"
readonly RESUME_FINGERPRINT="$STATE_DIR/resume-dirty-worktree.fingerprint"
readonly TMUX_SESSION="goo-buddy-codex-supervisor"
readonly CHECKLIST="$ROOT/docs/MULTI_PLATFORM_MATURITY.md"
readonly INTERVAL_SECONDS="${GOO_BUDDY_SUPERVISOR_INTERVAL_SECONDS:-60}"
readonly TASK_FOCUS="${GOO_BUDDY_SUPERVISOR_TASK_FOCUS:-Implement the closed Elegoo SDCP v3 and Moonraker control protocol adapters now. Add exact pause, resume, and cancel operation mappings only, with direct unit tests that reject arbitrary command values, paths, payloads, and G-code. Reuse the existing PlatformControlOperation contract.}"

usage() {
    printf '%s\n' "Usage: ${0##*/} [--worker|--once|--resume|--status-path|--log-path|--stop]"
}

prepare_state() {
    mkdir -p -- "$STATE_DIR"
    chmod 700 -- "$STATE_DIR"
    touch -- "$WORKER_LOG" "$SUPERVISOR_LOG"
    chmod 600 -- "$WORKER_LOG" "$SUPERVISOR_LOG"
}

log() {
    printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >> "$SUPERVISOR_LOG"
}

safe_text() {
    local value="${1:-}"
    value="${value//$'\r'/ }"
    value="${value//$'\n'/ }"
    value="${value:0:300}"
    if [[ "$value" =~ (authorization:|cookie:|set-cookie:|x-api-key:|bearer[[:space:]]|api[_-]?key|token=|secret=|password=|signature=|private[[:space:]_]?key) ]]; then
        printf '%s' '[redacted]'
    else
        printf '%s' "$value"
    fi
}

redact_worker_output() {
    sed -E \
        -e "s#https?://[^[:space:]\"'<>]+#<endpoint>#gI" \
        -e 's#([0-9]{1,3}\.){3}[0-9]{1,3}#<ipv4>#g' \
        -e 's#([[:xdigit:]]{2}:){5}[[:xdigit:]]{2}#<mac-address>#gI' \
        -e "s#((api[_-]?key|access[_-]?code|token|password|authorization|mainboard_?id|serial_?number|request_?id|task_?id)[[:space:]\"':=]+)[^,[:space:]\"'}]+#\\1<redacted>#gI"
}

automated_remaining() {
    awk '
        /^## Automated delivery checklist$/ { enabled = 1; next }
        /^## / { if (enabled) exit }
        enabled && /^- \[ \]/ { count += 1 }
        END { print count + 0 }
    ' "$CHECKLIST"
}

write_status() {
    local state="$1" task="$2" validation="$3" next_action="$4" blocker="${5:-none}"
    local temporary
    temporary="$(mktemp "$STATE_DIR/.implementation-status.XXXXXX")"
    {
        printf '# Goo Buddy implementation supervisor\n\n'
        printf -- '- State: %s\n' "$(safe_text "$state")"
        printf -- '- Current task: %s\n' "$(safe_text "$task")"
        printf -- '- Automated checklist items remaining: %s\n' "$(automated_remaining)"
        printf -- '- Most recent validation: %s\n' "$(safe_text "$validation")"
        printf -- '- Next action: %s\n' "$(safe_text "$next_action")"
        printf -- '- Blocker: %s\n' "$(safe_text "$blocker")"
        printf -- '- Updated (UTC): %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    } > "$temporary"
    chmod 600 -- "$temporary"
    mv -f -- "$temporary" "$STATUS_PATH"
}

stop_cleanly() {
    local state="$1" reason="$2"
    write_status "$state" 'No active task' "$reason" 'Supervisor stopped; restart after resolving the stated condition.' "$reason"
    log "stopped state=$state reason=$(safe_text "$reason")"
    exit 0
}

fingerprint() {
    {
        git -C "$ROOT" status --porcelain=v1 --untracked-files=all
        git -C "$ROOT" diff --no-ext-diff
    } | sha256sum | awk '{print $1}'
}

meaningful_worktree_status() {
    # .codex/ is an owner-managed local workspace directory. It must be
    # preserved, but it is not a product change that should block the worker.
    git -C "$ROOT" status --porcelain=v1 --untracked-files=all | grep -vE '^\?\? \.codex/' || true
}

resume_matches_current_worktree() {
    [[ -f "$RESUME_FINGERPRINT" ]] || return 1
    [[ "$(<"$RESUME_FINGERPRINT")" == "$(fingerprint)" ]]
}

upstream_is_not_ahead() {
    git -C "$ROOT" rev-parse --verify --quiet '@{upstream}' >/dev/null &&
        git -C "$ROOT" merge-base --is-ancestor '@{upstream}' HEAD
}

readonly TASK_PROMPT="You are the Goo Buddy implementation worker. Read AGENTS.md and inspect only the files relevant to the task before acting. Continue the already-authorized multi-platform control milestone: mature Elegoo/OpenCentauri SDCP v3 and Klipper/Moonraker support, including safe permission-gated printer control. Complete exactly one bounded, user-visible unchecked item from the 'Automated delivery checklist' in docs/MULTI_PLATFORM_MATURITY.md. Priority focus for this run: $TASK_FOCUS Begin implementation immediately after inspecting the relevant contract, manager, and adjacent test files; do not perform repository-wide searches. You must implement and test it; do not merely analyze, report status, or refactor without delivering the selected capability. Preserve all existing user and worker changes: never reset, checkout, clean, stash, or overwrite unrelated work. Do not publish, deploy, install, activate services, access credentials, scan any network, or contact/control any printer. Do not edit ignored supervisor device configuration. Keep controls closed and capability-driven: no arbitrary G-code, generic command tunnels, arbitrary HTTP paths, arbitrary payloads, or unreviewed write paths. Run focused relevant tests plus backend ruff check and format check when backend changes, then run ./test_all.sh before committing. Commit only the selected, validated milestone with a clear conventional subject. Do not push, tag, create releases, or run publishing scripts. Update the checklist only when the selected item is actually complete and evidence-backed. If a genuine human-only blocker requires missing credentials, a production/public change, hardware action, destructive operation, or material product decision, write a concise non-secret explanation to $STOP_SENTINEL and exit; normal implementation choices are not blockers. When the one task is finished, leave a clean worktree with the committed milestone on local main and exit successfully."

worker() {
    prepare_state
    trap 'stop_cleanly idle "Supervisor stopped by local user."' INT TERM

    [[ -n "$CODEX_BIN" && -x "$CODEX_BIN" ]] || stop_cleanly failed 'Codex CLI is unavailable.'
    [[ -d "$ROOT/.git" && -f "$ROOT/AGENTS.md" && -f "$CHECKLIST" ]] || stop_cleanly failed 'Goo Buddy repository guidance or checklist is unavailable.'
    [[ "$INTERVAL_SECONDS" =~ ^[1-9][0-9]*$ ]] || stop_cleanly failed 'Supervisor interval must be a positive integer.'

    exec 9>"$LOCK_PATH"
    if ! flock -n 9; then
        write_status idle 'No active task' 'Another Goo Buddy implementation supervisor owns the lock.' 'Wait for the active implementation worker.'
        exit 0
    fi

    while :; do
        if [[ -e "$STOP_SENTINEL" ]]; then
            stop_cleanly blocked 'A human-only blocker sentinel is present.'
        fi
        if [[ "$(automated_remaining)" -eq 0 ]]; then
            stop_cleanly ready 'Automated implementation checklist is complete; hands-on testing remains.'
        fi
        if [[ "$(git -C "$ROOT" branch --show-current)" != "main" ]]; then
            stop_cleanly blocked 'Repository is not on the documented main branch.'
        fi
        if [[ -n "$(meaningful_worktree_status)" ]]; then
            if resume_matches_current_worktree; then
                log 'resuming the exact interrupted worktree authorized by the local user'
            else
                stop_cleanly blocked 'Repository has uncommitted product changes; preserve and resolve them before the next task.'
            fi
        fi
        if ! upstream_is_not_ahead; then
            stop_cleanly blocked 'Repository is behind or has diverged from its upstream before the next task.'
        fi

        local before after worker_status
        before="$(fingerprint)"
        write_status running 'One bounded automated delivery item' 'Preflight passed.' 'Run the current Codex implementation task.'
        log "starting implementation task remaining=$(automated_remaining)"
        set +e
        "$CODEX_BIN" -s danger-full-access -a never exec -C "$ROOT" --color never "$TASK_PROMPT" 2>&1 | redact_worker_output | tee -a "$WORKER_LOG"
        worker_status=${PIPESTATUS[0]}
        set -e
        if [[ "$worker_status" -ne 0 ]]; then
            stop_cleanly failed 'Codex implementation task exited nonzero; inspect worker.log.'
        fi
        if [[ -e "$STOP_SENTINEL" ]]; then
            stop_cleanly blocked 'The implementation worker recorded a human-only blocker.'
        fi
        if [[ -n "$(meaningful_worktree_status)" ]]; then
            stop_cleanly blocked 'Implementation worker left uncommitted product changes.'
        fi
        rm -f -- "$RESUME_FINGERPRINT"
        if ! upstream_is_not_ahead; then
            stop_cleanly blocked 'Implementation worker left local main behind or diverged from its upstream.'
        fi

        after="$(fingerprint)"
        if [[ "$after" == "$before" ]]; then
            write_status idle 'No active task' 'Worker exited without a source change.' 'Retry the next bounded implementation task after the configured interval.'
            log 'worker exited without a source change'
        else
            write_status idle 'No active task' 'Worker completed a source change; inspect focused test output in worker.log.' 'Start the next bounded implementation task after the configured interval.'
            log "worker completed a source change remaining=$(automated_remaining)"
        fi
        sleep "$INTERVAL_SECONDS"
    done
}

controller() {
    prepare_state
    if ! command -v tmux >/dev/null 2>&1; then
        log 'tmux unavailable; running the implementation worker in the foreground'
        exec "$0" --worker
    fi
    if ! tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
        log "starting tmux session $TMUX_SESSION"
        tmux new-session -d -s "$TMUX_SESSION" "exec $(printf '%q' "$0") --worker"
    else
        log "using existing tmux session $TMUX_SESSION"
    fi
}

resume() {
    prepare_state
    if [[ -z "$(meaningful_worktree_status)" ]]; then
        rm -f -- "$RESUME_FINGERPRINT" "$STOP_SENTINEL"
        controller
        return
    fi

    local temporary
    temporary="$(mktemp "$STATE_DIR/.resume-dirty-worktree.XXXXXX")"
    fingerprint > "$temporary"
    chmod 600 -- "$temporary"
    mv -f -- "$temporary" "$RESUME_FINGERPRINT"
    rm -f -- "$STOP_SENTINEL"
    log 'local user authorized resumption of the exact interrupted worktree'
    controller
}

case "${1:-}" in
    --worker) worker ;;
    --once)
        export GOO_BUDDY_SUPERVISOR_INTERVAL_SECONDS=1
        worker
        ;;
    --resume) resume ;;
    --status-path) printf '%s\n' "$STATUS_PATH" ;;
    --log-path) printf '%s\n' "$WORKER_LOG" ;;
    --stop)
        prepare_state
        printf '%s\n' 'Stopped by local user.' > "$STOP_SENTINEL"
        chmod 600 -- "$STOP_SENTINEL"
        ;;
    -h|--help) usage ;;
    '') controller ;;
    *) usage >&2; exit 64 ;;
esac
