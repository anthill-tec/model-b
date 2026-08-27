#!/bin/bash
# Owner: Model B (roundhouse/model-b) — adopted by CR-MDB-022 §S1.
# Consuming skills: none in-tree yet — CR-MDB-022 §S5 names it in
#   model-b/references/orchestration-common.md; audits/2026-07-20-crucible-drift.md
#   already records its verb and exit-code surface.
#
# gate-lock.sh — regression / merge-gate coordinator for parallel tracks.
#
# A shared LOCK FILE serializes the heavy gate (only ONE track runs its full
# regression at a time) + a RESOURCE headroom guard (don't run even if unlocked
# when the box is loaded). SELF-SERVICE — a track coordinates without asking
# Mainline for permission. Mainline is the STALE-LOCK ARBITER only: if a lock is
# never released (a track forgot / died), the waiting track ESCALATES and
# Mainline verifies (status + resources + interrogates the holder) then
# force-releases.
#
# Lock file (shared across ALL worktrees of the repo): <git-common-dir>/nai-gate.lock
#
# Subcommands:
#   acquire --cr <CR> --track "<Track>"
#       0 = ACQUIRED (lock written; run your gate now)
#       1 = HOLD: lock held by ANOTHER track
#       2 = HOLD: resources loaded (lock free, but box busy)
#   wait-acquire --cr <CR> --track "<Track>" [--freq 5] [--max 600]
#       loop `acquire` every <freq>s up to <max>s.  0 = acquired (run gate),
#       5 = TIMED OUT (escalate to Mainline — do NOT force-release yourself).
#       Run this in the BACKGROUND (a 600s loop exceeds the 10-min foreground cap).
#   release --cr <CR> --track "<Track>"   remove YOUR lock (always, post-gate)
#   status                                lock holder + age + resource readings
#   check                                 resource-only headroom check (0/1)
#   force-release [--reason "..."]        MAINLINE-only: remove a stale lock
#
# BLOCKING guards are RAM / CPU / disk (the lock already serializes gate-vs-gate).
# The cargo-process count is INFORMATIONAL (shown, not blocking) so per-cycle
# cargo on other tracks doesn't wedge the gate — heavy load is caught by CPU/RAM.
#
# Thresholds (env): GATE_RAM_MAX=70 (used%) · GATE_LOAD_MAX=1.5 (load-per-core oversubscription) · GATE_DISK_MIN_GB=15 (min free GB)
# CPU utilisation (0-100%, /proc/stat delta) is shown for readout; the load-per-core RATIO is the guard.
set -u
RAM_MAX=${GATE_RAM_MAX:-70}; LOAD_MAX=${GATE_LOAD_MAX:-1.5}; DISK_MIN_GB=${GATE_DISK_MIN_GB:-15}
CHECK_DIR=${GATE_CHECK_DIR:-$PWD}

lock_path() {
  # Project ROOT of the MAIN repo (the parent of the common git dir) — NEVER
  # inside .git (don't pollute git's own state), and SHARED across all worktrees
  # so the gate mutex spans every track. It's gitignored (nai-gate.lock).
  local gcd
  gcd=$(git -C "$CHECK_DIR" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
  # fallback for older git: resolve the (possibly relative) common dir to absolute
  [ -z "$gcd" ] && gcd=$(cd "$CHECK_DIR" 2>/dev/null && cd "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null && pwd)
  if [ -n "$gcd" ]; then echo "$(dirname "$gcd")/nai-gate.lock"; else echo "/tmp/nai-gate.lock"; fi
}
LOCK=$(lock_path)

# resource guard: sets RES_SUMMARY (always) + RES_REASONS; return 0=headroom / 1=loaded.
resource_loaded() {
  local reasons=() mem_used mem_total mem_pct ncpu load1 t1 i1 t2 i2 cpu_util ratio over disk_pct disk_free free_kb free_gb heavy
  read -r mem_used mem_total < <(free | awk '/^Mem:/ {print $3, $2}')
  mem_pct=$(( mem_used * 100 / mem_total )); [ "$mem_pct" -gt "$RAM_MAX" ] && reasons+=("RAM ${mem_pct}%>${RAM_MAX}%")
  # real CPU utilisation % (0-100) from a short /proc/stat delta (idle vs total jiffies)
  read -r t1 i1 < <(awk '/^cpu /{s=0;for(k=2;k<=NF;k++)s+=$k;print s,$5}' /proc/stat)
  sleep 0.4
  read -r t2 i2 < <(awk '/^cpu /{s=0;for(k=2;k<=NF;k++)s+=$k;print s,$5}' /proc/stat)
  cpu_util=$(awk -v a="$t1" -v b="$i1" -v c="$t2" -v d="$i2" 'BEGIN{dt=c-a;di=d-b;printf "%d",(dt>0)?100*(1-di/dt):0}')
  # load-per-core ratio (>1.0 = oversubscribed) — the contention GUARD (not a %)
  ncpu=$(nproc); load1=$(awk '{print $1}' /proc/loadavg)
  ratio=$(awk -v l="$load1" -v n="$ncpu" 'BEGIN{printf "%.1f", l/n}')
  over=$(awk -v r="$ratio" -v m="$LOAD_MAX" 'BEGIN{print (r>m)?1:0}')
  [ "$over" = 1 ] && reasons+=("load ${load1}/${ncpu}cpu = ${ratio}x oversubscribed > ${LOAD_MAX}x")
  disk_pct=$(df --output=pcent "$CHECK_DIR" 2>/dev/null | tail -1 | tr -dc '0-9')
  disk_free=$(df -h --output=avail "$CHECK_DIR" 2>/dev/null | tail -1 | tr -d ' ')
  free_kb=$(df -k --output=avail "$CHECK_DIR" 2>/dev/null | tail -1 | tr -dc '0-9'); free_gb=$(( ${free_kb:-0} / 1024 / 1024 ))
  [ "$free_gb" -lt "$DISK_MIN_GB" ] && reasons+=("disk only ${disk_free} free (<${DISK_MIN_GB}G) at ${disk_pct}% used")
  heavy=$(pgrep -a -f 'rustc|cargo[- ](build|test|nextest|llvm-cov|check)|cargo-nextest' 2>/dev/null | grep -viE 'gate-lock|gate-resource|pgrep' | wc -l)
  RES_SUMMARY="RAM ${mem_pct}%, CPU ${cpu_util}% util, load ${load1}/${ncpu}cpu(${ratio}x), disk ${disk_pct}%/${disk_free} free, ${heavy:-0} cargo procs(info)"
  if [ ${#reasons[@]} -eq 0 ]; then RES_REASONS=""; return 0; else RES_REASONS="${reasons[*]}"; return 1; fi
}

# Liveness of the run pid recorded in the lock. crucible stamps the REAL cargo
# pid during smoke/regression runs, so this reflects the ACTUAL test run — not
# the acquiring shell. Read by `status` + the wait-acquire HOLD message.
pid_state() {
  local p; p=$(awk -F= '/^pid=/{print $2}' "$LOCK" 2>/dev/null)
  [ -z "$p" ] && { echo "run pid: (none recorded)"; return; }
  if ps -p "$p" >/dev/null 2>&1; then echo "run pid ${p}: ALIVE (test run active)";
  else echo "run pid ${p}: DEAD — no active test run (likely STALE -> Mainline may force-release)"; fi
}

# Is the gate free to run? FREE = no lock file, or the holder pid is dead (stale
# — crucible reclaims it on start). Also requires resource headroom. Used by
# wait-free. crucible owns the lock FILE now; this only observes it.
lock_is_free() {
  if [ -f "$LOCK" ]; then
    local p; p=$(awk -F= '/^pid=/{print $2}' "$LOCK")
    [ -n "$p" ] && ps -p "$p" >/dev/null 2>&1 && return 1   # live holder → not free
  fi
  resource_loaded || return 1   # resources loaded → not ready to run
  return 0
}

do_acquire() {
  if [ -f "$LOCK" ]; then
    local owner ocr oep now age; owner=$(awk -F= '/^owner=/{print $2}' "$LOCK"); ocr=$(awk -F= '/^cr=/{print $2}' "$LOCK")
    oep=$(awk -F= '/^epoch=/{print $2}' "$LOCK"); now=$(date +%s); age=$(( (now - ${oep:-now}) / 60 ))
    echo "HOLD (locked) — held by '${owner}' for ${ocr} (${age} min); $(pid_state). Wait for release; escalate to Mainline if the run pid is DEAD or it never lifts."; return 1
  fi
  if ! resource_loaded; then echo "HOLD (resources) — $RES_REASONS"; return 2; fi
  { echo "owner=$TRACK"; echo "cr=$CR"; echo "pid=$$"; echo "epoch=$(date +%s)"; echo "started=$(date '+%Y-%m-%d %H:%M:%S')"; } > "$LOCK"
  echo "ACQUIRED — $TRACK holds the gate lock for $CR ($RES_SUMMARY)."; return 0
}

CMD="${1:-status}"; shift 2>/dev/null || true
CR=""; TRACK=""; REASON=""; FREQ=5; MAX=600
while [ $# -gt 0 ]; do case "$1" in
  --cr) CR="$2"; shift 2;; --track) TRACK="$2"; shift 2;; --reason) REASON="$2"; shift 2;;
  --freq) FREQ="$2"; shift 2;; --max) MAX="$2"; shift 2;; *) shift;; esac; done

case "$CMD" in
  check) if resource_loaded; then echo "READY — $RES_SUMMARY"; exit 0; else echo "HOLD (resources) — $RES_REASONS"; exit 1; fi ;;
  status)
    echo "lock: $LOCK"
    if [ -f "$LOCK" ]; then echo "HELD:"; sed 's/^/  /' "$LOCK"
      oep=$(awk -F= '/^epoch=/{print $2}' "$LOCK"); [ -n "${oep:-}" ] && echo "  age: $(( ($(date +%s) - oep)/60 )) min"
      echo "  $(pid_state)"
    else echo "FREE"; fi
    resource_loaded; echo "resources: $RES_SUMMARY" ;;
  acquire) [ -z "$CR" ] || [ -z "$TRACK" ] && { echo "acquire needs --cr and --track"; exit 3; }; do_acquire; exit $? ;;
  wait-acquire)
    [ -z "$CR" ] || [ -z "$TRACK" ] && { echo "wait-acquire needs --cr and --track"; exit 3; }
    elapsed=0
    while :; do
      out=$(do_acquire); rc=$?
      if [ $rc -eq 0 ]; then echo "$out"; exit 0; fi
      if [ $elapsed -ge $MAX ]; then echo "TIMED OUT after ${elapsed}s — $out"; echo ">> ESCALATE to Mainline (do not force-release yourself)."; exit 5; fi
      sleep "$FREQ"; elapsed=$((elapsed + FREQ))
    done ;;
  wait-free)
    # Orchestrator pre-flight: WAIT until the gate is free (crucible will then
    # create + own the lock), escalating to Mainline after --max. Does NOT create
    # the lock — crucible owns the lock-file lifecycle now.
    [ -z "$CR" ] || [ -z "$TRACK" ] && { echo "wait-free needs --cr and --track"; exit 3; }
    elapsed=0
    while :; do
      if lock_is_free; then echo "FREE — go; crucible will create + own the lock. ($RES_SUMMARY)"; exit 0; fi
      if [ $elapsed -ge $MAX ]; then
        echo "TIMED OUT after ${elapsed}s waiting for the gate to free."
        [ -f "$LOCK" ] && echo "  held by: $(awk -F= '/^owner=/{print $2}' "$LOCK") — $(pid_state)"
        echo ">> ESCALATE to Mainline (do not force-release yourself)."; exit 5
      fi
      sleep "$FREQ"; elapsed=$((elapsed + FREQ))
    done ;;
  release)
    [ ! -f "$LOCK" ] && { echo "no lock to release"; exit 0; }
    owner=$(awk -F= '/^owner=/{print $2}' "$LOCK")
    if [ -n "$TRACK" ] && [ "$owner" != "$TRACK" ]; then echo "REFUSED — lock owned by '${owner}', not '${TRACK}'. Escalate to Mainline for a stale lock."; exit 4; fi
    rm -f "$LOCK"; echo "RELEASED — $CR ($owner)"; exit 0 ;;
  force-release)
    [ ! -f "$LOCK" ] && { echo "no lock present"; exit 0; }
    echo "FORCE-RELEASE (Mainline) — reason: ${REASON:-unspecified}; was:"; sed 's/^/  /' "$LOCK"; rm -f "$LOCK"; echo "removed."; exit 0 ;;
  *) echo "usage: gate-lock.sh {wait-free|status|check|force-release|acquire|wait-acquire|release} [--cr X] [--track T] [--freq 5] [--max 600] [--reason R]"; exit 3 ;;
esac
