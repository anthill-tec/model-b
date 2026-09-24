#!/usr/bin/env python3
# Owner: Model B (roundhouse/model-b) — adopted by CR-MDB-022 §S1.
# Consuming skills: bootstrap, shutdown, model-b (references/orchestration-common.md,
#   references/orchestration-track.md), memory-templates (java-orchestration.md,
#   rust-orchestration.md); AGENTS.md names it too.
#
"""Git worktree + git-flow orchestration CLI — deterministic start/close ceremony
for PARALLEL CR execution.

The orchestrator (VD) runs two+ CRs at once in separate Claude sessions on the same
filesystem. `git flow feature start` does a `checkout` in ONE shared working tree, so
parallel sessions sharing it collide. The fix is per-CR git worktrees for isolation,
closed with a direct `git merge --no-ff` into develop (the same result `git flow feature
finish` produces, but with NO dependency on the git-flow binary). The close has a fixed,
error-prone "dance" (the branch can only be deleted AFTER its worktree is removed; merges
to develop must be serialized; a feature branch must be rebased onto develop if develop
moved while the CR was in flight). This script encodes that dance once so VD only calls
stable command signatures with the CR id.

Design invariants (see rust-orchestration.md (Tooling — worktree-flow)):
  * Source of truth is GIT, not a sidecar state file. State is derived live from
    `git worktree list --porcelain`, `git merge-base`, `git rev-list`, `git status`.
    There is no JSON to drift out of sync with reality.
  * develop has exactly ONE working tree (the main checkout = the "integration tree").
    All merges serialize through it. `finish` takes an atomic lock in `.git/` so two
    parallel sessions can never merge to develop at the same time.
  * `git branch -d` FAILS on a branch still checked out in a worktree. So `finish`
    merges into develop first, then removes the worktree, then deletes the branch — in
    that order. The merge is a plain `git merge --no-ff` in the integration tree (no
    git-flow binary). Every step is gated; nothing is forced.
  * Destructive steps are precondition-gated (clean worktree, clean integration tree,
    not-inside-the-target-worktree) and abort-and-report on any failure. Use --dry-run
    to preview the exact git commands without mutating anything.

Subcommands:
  start    git worktree add -b feature/<cr>[-<slug>] .claude/worktrees/<cr> <base>.
           Branches off LOCAL develop HEAD (NOT origin) so un-pushed design-phase
           commits are included. Refuses if branch/worktree already exist. Optional
           `--track <label>` (or $WF_TRACK env, set once per session) stamps a human
           track/session name onto the worktree for `status` identification.
  status   Parse all worktrees; show each branch's ahead/behind vs develop, whether
           a rebase is needed before it can cleanly finish, the latest COMMITTED
           Crucible phase (RED/GREEN/RED-fix/close-out, inferred from the commit-message
           convention — git-derived, no sidecar), and the track/session label if one was
           stamped at `start`. This is the parallel-execution dashboard.
  sync     Rebase a CR's feature branch onto the current develop (run when another
           parallel CR has merged and moved develop). Aborts cleanly on conflict —
           never leaves a half-rebased tree.
  finish   The close dance: lock -> verify clean -> auto-rebase if develop moved ->
           git merge --no-ff into develop -> git worktree remove -> git branch -d
           -> (optional) push. Releases the lock on every exit path.
  abort    Abandon a CR worktree without merging: git worktree remove (+ optional
           branch delete). For cancelled / superseded CRs.

Scheduling is NOT here (CR-MDB-028). This tool owns what it can DERIVE FROM GIT
(worktrees, ahead/behind, phase, merge); Crucible owns what used to live in the
local ChangeSet DB (queue membership, release, wave, seq, dependencies,
readiness). The DB backend and its five verbs were REMOVED — run the Crucible
client instead of this tool for any scheduling question:

  cs        -> two explicit steps, not one act: `python-crucible.py cr-plan
               --cr <CR> --title "…" --release <rel> --wave <n>` files the CR,
               then `rust-code-health.py ledger assign --slice <CR> --ids
               F-…,DS-…` stamps the audit-cull findings.
  show      -> `python-crucible.py queue` (the registered CR rows) or
               `python-crucible.py status` (plans + cycles).
  progress  -> `python-crucible.py checkpoint` during a cycle and
               `python-crucible.py cycle-done` at each cycle end.
  next      -> `python-crucible.py next` — the same NEXT / HOLD / DRAINED
               vocabulary, answered from the one board that holds the plan.
  reconcile -> NO replacement, and none is needed: the verb dies with the DB.
               There is no local index left to reconcile against git.

Project path resolution (same convention as rust-crucible.py):
  --project-dir > $WORKTREE_FLOW_PROJECT_DIR > the git repo containing the current
  directory. No project is hardcoded — works in ANY repo. The script then resolves the
  MAIN worktree from git, so it works correctly even when invoked from inside a worktree.

Examples:
  # Start an isolated worktree for CR-NAI-248
  worktree-flow.py start --cr CR-NAI-248 --slug stage-subtask-multiplicity

  # See the parallel-execution dashboard
  worktree-flow.py status

  # Another CR merged; bring CR-NAI-248 up to date before its own finish
  worktree-flow.py sync --cr CR-NAI-248

  # Close CR-NAI-248 (preview first, then for real with a push)
  worktree-flow.py finish --cr CR-NAI-248 --dry-run
  worktree-flow.py finish --cr CR-NAI-248 --push

  # Abandon a superseded CR's worktree and delete its branch
  worktree-flow.py abort --cr CR-NAI-251 --delete-branch
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

WORKTREE_SUBDIR = ".claude/worktrees"

# Model-B scheduler-note board: if $WF_REQUEST_DIR points at the project's
# memory dir, `status` also lists pending `reschedule-request-*.md`
# (track → Mainline) and `directive-*.md` (Mainline → track), so a status pull
# doubles as a poll for scheduler notes and neither side misses a pending one.
REQUEST_DIR_ENV = "WF_REQUEST_DIR"

# Model B's own TOON codec (`toon.py`) sits BESIDE this script; the insert below
# makes it importable wherever the bundle is relocated. There is no local
# scheduling store any more: Crucible's queue owns queue membership, release,
# wave, seq, dependencies and readiness (CR-MDB-028 §S1/§S2/§S4), while this
# script owns only what it can derive from git.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# AXI output (CR-MDB-010): stdout = TOON envelope, stderr = human channel.
# Converted verbs: status, finish (CR-MDB-010's envelope contract stands for
# exactly these two; its `next`/`progress` conversions retired with those verbs
# in CR-MDB-028). The codec is Model B's own
# `toon.py`, sitting beside this script (the sys.path insert above makes it
# importable) — generated from `modelb_axi/toon.py`, the one hand-maintained
# implementation (CR-MDB-022 §S2). It emits a documented valid subset of the
# OFFICIAL TOON spec (toonformat.dev / github.com/toon-format); a NON-EMPTY
# scalar list goes out in the canonical INLINE form `key[N]: a,b`, never as a
# header plus bare indented items, which no conformant decoder accepts
# (CR-MDB-022 §S3). Remaining verbs keep plain output.
# ---------------------------------------------------------------------------
_AXI_PROJECT = None  # basename of the resolved project dir; set by converted verbs


def _axi_set_project(main_wt):
    """Record the project name stamped into every envelope this run."""
    global _AXI_PROJECT
    _AXI_PROJECT = os.path.basename(os.path.realpath(main_wt))


def _emit_axi(verb, ok, payload, warnings=None, help_lines=None):
    """Write the TOON AXI envelope to stdout (the machine channel).

    Shape: `{axi: {verb, ok, project, **payload, warnings[], help[]}}` — the
    stdout/stderr convention mirrored in contracts/crucible-envelope.md.
    Human rendering for converted verbs goes to stderr, never stdout.
    """
    import toon  # Model B's own codec, beside this script (see sys.path insert)
    envelope = {"verb": verb, "ok": ok, "project": _AXI_PROJECT}
    envelope.update(payload)
    envelope["warnings"] = list(warnings or [])
    envelope["help"] = list(help_lines or [])
    print(toon.encode({"axi": envelope}))


# --------------------------------------------------------------------------- #
# Project / git plumbing
# --------------------------------------------------------------------------- #

def _resolve_project_dir(arg_value):
    """Resolution order: --project-dir > $WORKTREE_FLOW_PROJECT_DIR > git repo of CWD > CWD.

    No project is hardcoded — this script works in ANY repo. The default is the git
    repository containing the current directory (`git rev-parse --show-toplevel`),
    falling back to the current directory when not inside a git repo. The MAIN worktree
    is resolved from there, so the default is correct even when run from inside a worktree.
    """
    if arg_value:
        return arg_value
    env_value = os.environ.get("WORKTREE_FLOW_PROJECT_DIR")
    if env_value:
        return env_value
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else os.getcwd()


def _git(args, cwd, check=False):
    """Run a git command, capturing output. Returns CompletedProcess."""
    return subprocess.run(
        ["git", *args], cwd=cwd, check=check, capture_output=True, text=True
    )


def _git_out(args, cwd):
    """Run git and return stripped stdout (empty string on failure)."""
    r = _git(args, cwd)
    return r.stdout.strip() if r.returncode == 0 else ""


def _common_git_dir(project_dir):
    """Absolute path to the shared .git dir (same for main checkout + all worktrees)."""
    out = _git_out(["rev-parse", "--path-format=absolute", "--git-common-dir"], project_dir)
    if not out:
        sys.exit(f"[worktree-flow] ERROR: {project_dir} is not a git repository")
    return out


def _main_worktree(project_dir):
    """The primary checkout (where develop lives) — resolved from git, not the CWD.

    The common git dir is `<main_worktree>/.git`; its parent is the main worktree.
    """
    cgd = _common_git_dir(project_dir)
    if os.path.basename(cgd.rstrip("/")) == ".git":
        return os.path.dirname(cgd.rstrip("/"))
    # Bare repo or unusual layout — fall back to toplevel of project_dir.
    return _git_out(["rev-parse", "--show-toplevel"], project_dir) or project_dir


def _config(repo, key, default):
    val = _git_out(["config", "--get", key], repo)
    return val or default


def _feature_prefix(repo):
    return _config(repo, "gitflow.prefix.feature", "feature/")


def _develop_branch(repo):
    return _config(repo, "gitflow.branch.develop", "develop")


def _worktrees(repo):
    """Parse `git worktree list --porcelain` into dicts.

    Keys: path, head, branch (short name or None), detached (bool), bare (bool).
    """
    out = _git_out(["worktree", "list", "--porcelain"], repo)
    entries, cur = [], {}
    for line in out.splitlines():
        if not line.strip():
            if cur:
                entries.append(cur)
                cur = {}
            continue
        if line.startswith("worktree "):
            cur = {"path": line[len("worktree "):], "branch": None,
                   "detached": False, "bare": False, "head": None}
        elif line.startswith("HEAD "):
            cur["head"] = line[len("HEAD "):]
        elif line.startswith("branch "):
            ref = line[len("branch "):]
            cur["branch"] = ref.replace("refs/heads/", "", 1)
        elif line == "detached":
            cur["detached"] = True
        elif line == "bare":
            cur["bare"] = True
    if cur:
        entries.append(cur)
    return entries


def _branch_exists(repo, branch):
    return _git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], repo).returncode == 0


def _ahead_behind(repo, base, branch):
    """(ahead, behind) of <branch> relative to <base>.

    ahead  = commits on branch not on base (the CR's work)
    behind = commits on base not on branch (how far develop moved → rebase needed)
    """
    out = _git_out(["rev-list", "--left-right", "--count", f"{base}...{branch}"], repo)
    if not out:
        return (None, None)
    behind_str, ahead_str = out.split()
    return (int(ahead_str), int(behind_str))


# Crucible phase keywords, most-specific first. Matched against the commit-subject
# segment after the first ':' (the convention is `type(scope Cn): PHASE — summary`).
_PHASE_TOKENS = (
    ("close-out", "CLOSE-OUT"),
    ("red-fix",   "RED-fix"),
    ("green",     "GREEN"),
    ("verify",    "VERIFY"),
    ("red",       "RED"),
)


def _phase_from_log(repo, base, branch):
    """Infer a CR branch's latest *committed* Crucible phase from its commit-message
    convention. Read-only + git-derived — no stored state (honours the no-sidecar
    invariant). Returns (phase, cycle, commits_ahead, latest_subject).

    Phase is the latest COMMITTED RED/GREEN/RED-fix/close-out. VERIFY is read-only and
    usually leaves no commit, so a GREEN tip often means 'GREEN done, VERIFY next'.
    """
    out = _git_out(["log", f"{base}..{branch}", "--format=%s"], repo)
    subjects = [s for s in out.splitlines() if s.strip()]
    if not subjects:
        return ("started — RED pending", None, 0, "")
    latest = subjects[0]
    # Scan only the segment after the first ':' so scope names don't false-match.
    seg = latest.split(":", 1)[1].lower() if ":" in latest else latest.lower()
    phase = "?"
    for token, label in _PHASE_TOKENS:
        if token in seg:
            phase = label
            break
    if phase == "?":
        if latest.startswith(("feat(", "fix(")):
            phase = "GREEN"
        elif latest.startswith("test("):
            phase = "RED"
        elif latest.startswith(("docs(", "chore(")):
            phase = "docs/chore"
    m = re.search(r"\bC(\d+)\b", latest)
    cycle = f"C{m.group(1)}" if m else None
    return (phase, cycle, len(subjects), latest)


def _is_clean(worktree_path):
    """True if the worktree has no staged/unstaged/untracked changes."""
    r = _git(["status", "--porcelain"], worktree_path)
    return r.returncode == 0 and r.stdout.strip() == ""


def _worktree_dir(main_wt, cr):
    return os.path.join(main_wt, WORKTREE_SUBDIR, cr)


def _find_worktree(repo, path):
    real = os.path.realpath(path)
    for wt in _worktrees(repo):
        if os.path.realpath(wt["path"]) == real:
            return wt
    return None


# --------------------------------------------------------------------------- #
# Track label (human session/track name)
# --------------------------------------------------------------------------- #
# A track LABEL is a human ASSIGNMENT (which session owns this CR), not derived
# state — so it lives in git config (`wf.track.<cr>`), NOT a JSON sidecar, and
# cannot "drift out of sync with reality" the way a cached ahead/behind would.
# `status` reads labels only for LIVE worktrees, so a leftover key from a finished
# CR is harmless (never displayed); finish/abort unset it anyway. The label is set
# at `start` from `--track` or the `$WF_TRACK` env var (set once per session).

def _get_track(repo, cr):
    return _git_out(["config", "--get", f"wf.track.{cr}"], repo)


def _set_track(repo, cr, label):
    _git(["config", f"wf.track.{cr}", label], repo)


def _unset_track(repo, cr):
    _git(["config", "--unset", f"wf.track.{cr}"], repo)


# --------------------------------------------------------------------------- #
# Merge serialization lock (atomic, in the shared .git dir)
# --------------------------------------------------------------------------- #

def _lock_path(repo):
    return os.path.join(_common_git_dir(repo), "worktree-flow-merge.lock")


def _acquire_lock(repo, cr):
    """Atomic O_EXCL create. Returns True on success, False if already held."""
    path = _lock_path(repo)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as f:
        f.write(f"cr={cr} pid={os.getpid()} ts={int(time.time())}\n")
    return True


def _read_lock(repo):
    try:
        with open(_lock_path(repo)) as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def _release_lock(repo):
    try:
        os.remove(_lock_path(repo))
    except FileNotFoundError:
        pass


# --------------------------------------------------------------------------- #
# start
# --------------------------------------------------------------------------- #

def cmd_start(args):
    project_dir = _resolve_project_dir(args.project_dir)
    main_wt = _main_worktree(project_dir)
    base = args.base or _develop_branch(main_wt)
    prefix = _feature_prefix(main_wt)

    if args.branch:
        branch = args.branch
        if not branch.startswith(prefix):
            sys.exit(f"[worktree-flow] ERROR: --branch must start with '{prefix}' "
                     f"(git flow finish strips that prefix). Got: {branch}")
    else:
        suffix = f"{args.cr}-{args.slug}" if args.slug else args.cr
        branch = f"{prefix}{suffix}"

    wt_dir = _worktree_dir(main_wt, args.cr)

    # Preconditions ------------------------------------------------------------
    if _branch_exists(main_wt, branch):
        sys.exit(f"[worktree-flow] ERROR: branch already exists: {branch}")
    if os.path.exists(wt_dir):
        sys.exit(f"[worktree-flow] ERROR: worktree path already exists: {wt_dir}")
    if not _git(["rev-parse", "--verify", "--quiet", base], main_wt).stdout.strip():
        sys.exit(f"[worktree-flow] ERROR: base ref does not resolve: {base}")

    base_head = _git_out(["rev-parse", "--short", base], main_wt)
    # Advisory: warn if local develop is behind its upstream (we still branch off LOCAL).
    upstream = _git_out(["rev-parse", "--abbrev-ref", f"{base}@{{upstream}}"], main_wt)
    if upstream:
        ahead, behind = _ahead_behind(main_wt, upstream, base)
        if behind:
            print(f"[worktree-flow] NOTE: local {base} is {behind} commit(s) behind "
                  f"{upstream}. Branching off LOCAL {base} ({base_head}) per the rule "
                  f"(keeps un-pushed design commits). `git -C {main_wt} pull` first if "
                  f"you wanted the upstream tip.")

    cmd = ["worktree", "add", "-b", branch, wt_dir, base]
    label = args.track or os.environ.get("WF_TRACK")
    if args.dry_run:
        print(f"[dry-run] git -C {main_wt} {' '.join(cmd)}")
        print(f"[dry-run] would create worktree {wt_dir} on {branch} from {base} ({base_head})")
        if label:
            print(f"[dry-run] would tag track label: {label}")
        return 0

    r = _git(cmd, main_wt)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        return 1
    print(f"start: ok worktree={wt_dir} branch={branch} base={base}@{base_head}")
    # Best-effort auto-copy of the main repo's gitignored `.env` into the new worktree.
    # A git worktree does NOT inherit gitignored files, so the main repo's `.env` (which
    # holds CRUCIBLE_PROJECT_KEY) is absent in a fresh worktree → in-worktree
    # `rust-crucible` Crucible ingest hard-fails at close-out. `.env` is gitignored, so
    # copying it into the worktree does not dirty the worktree. NEVER blocks/fails start.
    try:
        env_src = os.path.join(main_wt, ".env")
        env_dst = os.path.join(wt_dir, ".env")
        if os.path.isfile(env_src) and not os.path.exists(env_dst):
            shutil.copy2(env_src, env_dst)
            print(f"  env: copied .env → {env_dst}  (gitignored; Crucible ingest ready)")
    except Exception as _env_err:
        print(f"  NOTE: could not auto-copy .env into worktree: {_env_err} (continuing)")
    print(f"  → enter it: cd {wt_dir}")
    if label:
        _set_track(main_wt, args.cr, label)
        print(f"  track: {label}  ({'--track' if args.track else '$WF_TRACK'} → shown in `status`)")
    return 0


# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #

def _pid_alive(pid):
    """True if the process is still running (PermissionError ⇒ alive, other user)."""
    try:
        os.kill(int(pid), 0)
    except (ProcessLookupError, TypeError, ValueError):
        return False
    except PermissionError:
        return True
    return True


def _dotenv(repo, key):
    """Read a key from <repo>/.env (exported env wins). For WF_REQUEST_DIR etc."""
    if os.environ.get(key):
        return os.environ[key]
    env_path = os.path.join(repo, ".env")
    if not os.path.isfile(env_path):
        return None
    try:
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith(key + "=") or line.startswith(key + " "):
                    return line.partition("=")[2].split("#", 1)[0].strip().strip('"').strip("'")
    except OSError:
        return None
    return None


def _note_description(path):
    """First `description:` line from a note's YAML frontmatter (trimmed)."""
    try:
        with open(path, encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if i > 12:
                    break
                s = line.strip()
                if s.startswith("description:"):
                    d = s[len("description:"):].strip().strip('"').strip("'")
                    return d if len(d) <= 150 else d[:149] + "…"
    except OSError:
        pass
    return ""


def _render_request_board(main_wt):
    """List pending scheduler notes in WF_REQUEST_DIR — so a `status` pull doubles
    as an inbox check, alongside the active request-poll.py watcher.

    reschedule-request-*.md = track → Mainline (Mainline must consume + reschedule).
    directive-*.md          = Mainline → track; still present ⇒ UNCONSUMED by the track.
    """
    req_dir = _dotenv(main_wt, REQUEST_DIR_ENV)
    if not req_dir or not os.path.isdir(req_dir):
        return
    reqs, dirs = [], []
    for name in sorted(os.listdir(req_dir)):
        if not name.endswith(".md"):
            continue
        if name.startswith("reschedule-request-"):
            reqs.append(name)
        elif name.startswith("directive-"):
            dirs.append(name)
    if not reqs and not dirs:
        return
    print(file=sys.stderr)
    print("scheduler inbox ($WF_REQUEST_DIR):", file=sys.stderr)
    for name in reqs:
        print(f"  ⇧ REQUEST   {name}  → Mainline: consume + reschedule", file=sys.stderr)
        d = _note_description(os.path.join(req_dir, name))
        if d:
            print(f"              {d}", file=sys.stderr)
    for name in dirs:
        print(f"  ⇩ DIRECTIVE {name}  → UNCONSUMED by target track", file=sys.stderr)
        d = _note_description(os.path.join(req_dir, name))
        if d:
            print(f"              {d}", file=sys.stderr)


def cmd_status(args):
    project_dir = _resolve_project_dir(args.project_dir)
    main_wt = _main_worktree(project_dir)
    develop = _develop_branch(main_wt)
    main_real = os.path.realpath(main_wt)
    lock = _read_lock(main_wt)

    _axi_set_project(main_wt)
    print(f"integration tree (owns {develop}): {main_wt}", file=sys.stderr)
    if lock:
        print(f"  ⚠ MERGE LOCK HELD: {lock}  (a finish is in progress — do not merge)",
              file=sys.stderr)
    print(f"{'ROLE':<12}{'BRANCH':<48}{'HEAD':<10}{'AHEAD':>6}{'BEHIND':>7}  STATE",
          file=sys.stderr)

    wt_rows = []
    for wt in _worktrees(main_wt):
        is_main = os.path.realpath(wt["path"]) == main_real
        role = "integration" if is_main else "worktree"
        branch = wt["branch"] or ("(detached)" if wt["detached"] else "?")
        head = (wt["head"] or "")[:9]
        ahead = behind = None
        if wt["branch"] and not is_main:
            ahead, behind = _ahead_behind(main_wt, develop, wt["branch"])
        clean = _is_clean(wt["path"])
        if is_main:
            state = "clean" if clean else "DIRTY (has WIP)"
        elif behind:
            state = f"REBASE NEEDED (develop moved {behind})" + ("" if clean else " + DIRTY")
        else:
            state = ("clean — finish-ready" if clean else "DIRTY (commit first)")
        a = "" if ahead is None else str(ahead)
        b = "" if behind is None else str(behind)
        print(f"{role:<12}{branch:<48}{head:<10}{a:>6}{b:>7}  {state}", file=sys.stderr)
        cr_id = track = None
        phase = cycle = subject = None
        commits_ahead = None
        if not is_main:
            cr_id = os.path.basename(wt["path"].rstrip("/"))
            track = _get_track(main_wt, cr_id)
            if track:
                print(f"             track: {track}", file=sys.stderr)
            print(f"             path: {wt['path']}", file=sys.stderr)
            if wt["branch"]:
                phase, cycle, commits_ahead, subject = _phase_from_log(main_wt, develop, wt["branch"])
                cyc = f" {cycle}" if cycle else ""
                tail = ""
                if subject:
                    subj = subject if len(subject) <= 76 else subject[:75] + "…"
                    tail = f'  last: "{subj}"'
                print(f"             phase: {phase}{cyc}  ({commits_ahead} commit(s) ahead){tail}",
                      file=sys.stderr)
        wt_rows.append({
            "role": role, "branch": branch, "head": head, "ahead": ahead,
            "behind": behind, "state": state, "cr": cr_id, "track": track,
            "path": wt["path"], "phase": phase, "cycle": cycle,
            "commits_ahead": commits_ahead, "last_subject": subject,
        })
    _render_request_board(main_wt)
    # `lanes` stays in the envelope — CR-MDB-010's `status` contract is unchanged
    # — but it is now always empty: the lane plan lives in Crucible's queue, and
    # nothing here produces a local scheduling answer (CR-MDB-028 §S1).
    lane_rows = []
    warnings = []
    if lock:
        warnings.append(f"merge lock held: {lock} (a finish is in progress — do not merge)")
    _emit_axi("status", True, {"worktrees": wt_rows, "lanes": lane_rows}, warnings=warnings)
    return 0


# --------------------------------------------------------------------------- #
# sync (rebase feature branch onto develop)
# --------------------------------------------------------------------------- #

def _resolve_cr_worktree(main_wt, cr):
    """Return (wt_dir, branch) for a CR, erroring with guidance if not found/usable."""
    wt_dir = _worktree_dir(main_wt, cr)
    wt = _find_worktree(main_wt, wt_dir)
    if wt is None:
        sys.exit(f"[worktree-flow] ERROR: no worktree at {wt_dir}. "
                 f"Run `start --cr {cr}` first, or check `status`.")
    if wt["detached"] or not wt["branch"]:
        sys.exit(f"[worktree-flow] ERROR: worktree {wt_dir} is in detached HEAD — "
                 f"cannot operate on it safely.")
    return wt_dir, wt["branch"]


def cmd_sync(args):
    project_dir = _resolve_project_dir(args.project_dir)
    main_wt = _main_worktree(project_dir)
    develop = _develop_branch(main_wt)
    wt_dir, branch = _resolve_cr_worktree(main_wt, args.cr)

    ahead, behind = _ahead_behind(main_wt, develop, branch)
    if not behind:
        print(f"sync: ok branch={branch} already up to date with {develop} "
              f"(ahead={ahead}, behind=0) — no rebase needed")
        return 0

    if not _is_clean(wt_dir):
        sys.exit(f"[worktree-flow] ERROR: {wt_dir} has uncommitted changes. "
                 f"Commit or stash before rebasing.")

    if args.dry_run:
        print(f"[dry-run] git -C {wt_dir} rebase {develop}   "
              f"(branch is {behind} behind {develop})")
        return 0

    print(f"sync: rebasing {branch} onto {develop} ({behind} commit(s) behind)…")
    r = _git(["rebase", develop], wt_dir)
    if r.returncode != 0:
        # Never leave a half-rebased tree — abort and report.
        _git(["rebase", "--abort"], wt_dir)
        sys.stderr.write(r.stdout + r.stderr)
        print(f"[worktree-flow] ERROR: rebase hit conflicts — ABORTED cleanly. "
              f"{branch} is unchanged. Resolve manually in {wt_dir}:\n"
              f"  cd {wt_dir} && git rebase {develop}   # then fix conflicts")
        return 1
    new_head = _git_out(["rev-parse", "--short", "HEAD"], wt_dir)
    print(f"sync: ok {branch} rebased onto {develop} (new head {new_head})")
    return 0


# --------------------------------------------------------------------------- #
# finish (the close dance)
# --------------------------------------------------------------------------- #

def cmd_finish(args):
    project_dir = _resolve_project_dir(args.project_dir)
    main_wt = _main_worktree(project_dir)
    develop = _develop_branch(main_wt)
    _axi_set_project(main_wt)
    wt_dir, branch = _resolve_cr_worktree(main_wt, args.cr)

    # --- Preconditions (checked BEFORE any mutation, and before taking the lock) ---
    cwd_real = os.path.realpath(os.getcwd())
    if cwd_real == os.path.realpath(wt_dir) or cwd_real.startswith(os.path.realpath(wt_dir) + os.sep):
        sys.exit(f"[worktree-flow] ERROR: you are INSIDE the worktree being removed "
                 f"({wt_dir}). Step out first (cd {main_wt}), then re-run.")
    if not _is_clean(wt_dir):
        sys.exit(f"[worktree-flow] ERROR: worktree {wt_dir} has uncommitted changes. "
                 f"Commit the CR's work before finishing (no work is silently dropped).")
    if not _is_clean(main_wt):
        sys.exit(f"[worktree-flow] ERROR: integration tree {main_wt} is DIRTY. A parallel "
                 f"session likely has WIP on {develop}. Coordinate — do not merge into a "
                 f"dirty integration tree.")
    main_branch_now = _git_out(["rev-parse", "--abbrev-ref", "HEAD"], main_wt)
    if main_branch_now != develop:
        sys.exit(f"[worktree-flow] ERROR: integration tree is on '{main_branch_now}', not "
                 f"'{develop}'. git flow finish merges into the checked-out develop; refusing "
                 f"to switch a tree another session may be using.")

    ahead, behind = _ahead_behind(main_wt, develop, branch)
    if ahead == 0:
        sys.exit(f"[worktree-flow] ERROR: {branch} has no commits beyond {develop} — "
                 f"nothing to finish.")

    # --- Serialize the merge --------------------------------------------------
    if not args.dry_run:
        if not _acquire_lock(main_wt, args.cr):
            holder = _read_lock(main_wt)
            sys.exit(f"[worktree-flow] ERROR: merge lock held by another finish [{holder}]. "
                     f"Wait for it to release, then retry. (Break a stale lock with "
                     f"`abort --release-lock` only if you are sure no finish is running.)")

    try:
        # --- Rebase if develop moved (rebase at the right time) ---------------
        if behind:
            if args.no_auto_sync:
                sys.exit(f"[worktree-flow] ERROR: {branch} is {behind} behind {develop} and "
                         f"--no-auto-sync was set. Run `sync --cr {args.cr}` first.")
            print(f"finish: {branch} is {behind} behind {develop} → rebasing first…",
                  file=sys.stderr)
            if args.dry_run:
                print(f"[dry-run] git -C {wt_dir} rebase {develop}", file=sys.stderr)
            else:
                rb = _git(["rebase", develop], wt_dir)
                if rb.returncode != 0:
                    _git(["rebase", "--abort"], wt_dir)
                    sys.stderr.write(rb.stdout + rb.stderr)
                    sys.exit(f"[worktree-flow] ERROR: pre-finish rebase conflicted — ABORTED. "
                             f"{branch} unchanged, NOT merged. Resolve in {wt_dir} then retry.")

        # --- The dance: merge --no-ff, THEN remove worktree, THEN delete branch -
        # Direct git — no git-flow binary. Same result git flow feature finish gives.
        # Merge FIRST (worktree still intact) so a (near-impossible, post-rebase) merge
        # failure leaves everything recoverable. The branch is deleted LAST, after its
        # worktree is gone (git refuses to delete a branch checked out in a worktree).
        merge_msg = f"Merge branch '{branch}' into {develop}"
        steps = [
            f"git -C {main_wt} merge --no-ff {branch} -m {merge_msg!r}",
            f"git -C {main_wt} worktree remove {wt_dir}",
            f"git -C {main_wt} worktree prune",
            f"git -C {main_wt} branch -d {branch}",
        ]
        if args.push:
            steps.append(f"git -C {main_wt} push origin {develop}")
        if args.dry_run:
            print("[dry-run] finish plan:", file=sys.stderr)
            for s in steps:
                print(f"  {s}", file=sys.stderr)
            _emit_axi("finish", True,
                      {"cr": args.cr, "branch": branch, "develop": develop,
                       "dry_run": True},
                      help_lines=steps)
            return 0

        print(f"finish: merging {branch} → {develop} (--no-ff)…", file=sys.stderr)
        mg = _git(["merge", "--no-ff", branch, "-m", merge_msg], main_wt)
        sys.stderr.write(mg.stdout)
        if mg.returncode != 0:
            sys.stderr.write(mg.stderr)
            _git(["merge", "--abort"], main_wt)  # leave develop clean; worktree untouched
            sys.exit(f"[worktree-flow] ERROR: `git merge --no-ff {branch}` failed (exit "
                     f"{mg.returncode}) — merge ABORTED, {develop} left clean, worktree and "
                     f"branch untouched (nothing lost). This is unexpected after the rebase; "
                     f"inspect {wt_dir} and merge manually if needed.")

        r = _git(["worktree", "remove", wt_dir], main_wt)
        if r.returncode != 0:
            sys.stderr.write(r.stderr)
            # Benign case (untracked/modified files in the worktree) → --force clears it.
            rf = _git(["worktree", "remove", "--force", wt_dir], main_wt)
            if rf.returncode != 0:
                # PARTIAL DELETION. Common root cause: docker (running as root) created
                # bind-mount target dirs inside the worktree (e.g. deploy/*.yaml created
                # as directories by a compose run); neither `worktree remove` nor --force
                # can unlink root-owned files. Make git as consistent as possible (prune
                # any now-danging admin entry), then surface the leftover FOLDER and the
                # exact sudo recovery so the operator is never left guessing. (CR-NAI-255
                # left exactly this orphan; rust-orchestration.md (Disk hygiene).)
                sys.stderr.write(rf.stderr)
                _git(["worktree", "prune"], main_wt)
                del_r = _git(["branch", "-d", branch], main_wt)
                merged_head = _git_out(["rev-parse", "--short", develop], main_wt)
                warnings = [f"PARTIAL FINISH — merge into {develop} succeeded but worktree removal did not complete"]
                help_lines = []
                print(f"[worktree-flow] PARTIAL FINISH — merge into {develop} SUCCEEDED "
                      f"(now {merged_head}).", file=sys.stderr)
                if os.path.isdir(wt_dir):
                    print(f"[worktree-flow] ⚠ FOLDER NOT FULLY REMOVED: {wt_dir}\n"
                          f"  Leftover files remain — commonly ROOT-OWNED docker bind-mount\n"
                          f"  artifacts (e.g. deploy/*.yaml created as dirs by a compose run).\n"
                          f"  Reclaim it (needs sudo — run in a REAL terminal, not the ! prefix),\n"
                          f"  then finish the git cleanup:\n"
                          f"      sudo rm -rf {wt_dir}\n"
                          f"      git -C {main_wt} worktree prune && git -C {main_wt} branch -d {branch}",
                          file=sys.stderr)
                    warnings.append(f"folder not fully removed: {wt_dir}")
                    help_lines.append(f"sudo rm -rf {wt_dir}")
                    help_lines.append(f"git -C {main_wt} worktree prune && git -C {main_wt} branch -d {branch}")
                elif del_r.returncode != 0:
                    sys.stderr.write(del_r.stderr)
                    print(f"[worktree-flow] WARN: branch '{branch}' not deleted — "
                          f"`git -C {main_wt} branch -d {branch}`", file=sys.stderr)
                    warnings.append(f"branch '{branch}' not deleted")
                    help_lines.append(f"git -C {main_wt} branch -d {branch}")
                else:
                    print(f"[worktree-flow] folder gone, branch '{branch}' deleted — finish complete.",
                          file=sys.stderr)
                _emit_axi("finish", False,
                          {"cr": args.cr, "branch": branch, "develop": develop,
                           "merged_head": merged_head, "partial": True},
                          warnings=warnings, help_lines=help_lines)
                return 1
            # --force succeeded → fall through to prune + branch delete.
        _git(["worktree", "prune"], main_wt)

        warnings = []
        help_lines = []
        del_r = _git(["branch", "-d", branch], main_wt)
        if del_r.returncode != 0:
            sys.stderr.write(del_r.stderr)
            print(f"[worktree-flow] WARN: merge + worktree removal succeeded but "
                  f"`branch -d {branch}` failed (branch kept). Delete manually: "
                  f"git -C {main_wt} branch -d {branch}", file=sys.stderr)
            warnings.append(f"branch -d {branch} failed (branch kept) — delete manually")
            help_lines.append(f"git -C {main_wt} branch -d {branch}")

        merged_head = _git_out(["rev-parse", "--short", develop], main_wt)
        print(f"finish: ok merged {branch} → {develop} (now {merged_head}); branch deleted",
              file=sys.stderr)
        _unset_track(main_wt, args.cr)  # tidy the track label (best-effort; harmless if absent)

        if args.push:
            pr = _git(["push", "origin", develop], main_wt)
            if pr.returncode != 0:
                sys.stderr.write(pr.stderr)
                print(f"[worktree-flow] WARN: merge succeeded but `push origin {develop}` "
                      f"failed. Push manually from {main_wt}.", file=sys.stderr)
                warnings.append(f"merge succeeded but `push origin {develop}` failed — push manually")
                help_lines.append(f"git -C {main_wt} push origin {develop}")
                _emit_axi("finish", False,
                          {"cr": args.cr, "branch": branch, "develop": develop,
                           "merged_head": merged_head, "pushed": False},
                          warnings=warnings, help_lines=help_lines)
                return 1
            print(f"finish: pushed {develop} → origin", file=sys.stderr)
        _emit_axi("finish", True,
                  {"cr": args.cr, "branch": branch, "develop": develop,
                   "merged_head": merged_head, "pushed": bool(args.push)},
                  warnings=warnings, help_lines=help_lines)
        return 0
    finally:
        if not args.dry_run:
            _release_lock(main_wt)


# --------------------------------------------------------------------------- #
# abort (abandon a worktree without merging)
# --------------------------------------------------------------------------- #

def cmd_abort(args):
    project_dir = _resolve_project_dir(args.project_dir)
    main_wt = _main_worktree(project_dir)

    if args.release_lock:
        holder = _read_lock(main_wt)
        if args.dry_run:
            print(f"[dry-run] would release merge lock [{holder}]")
            return 0
        _release_lock(main_wt)
        print(f"abort: released merge lock [{holder}]")
        return 0

    if not args.cr:
        sys.exit("[worktree-flow] ERROR: abort needs --cr (or --release-lock).")
    if not getattr(args, "reason", None):
        sys.exit("[worktree-flow] ERROR: abort/supersede needs --reason — the cause is "
                 "recorded on the CR in Crucible's queue (ABORTED/SUPERSEDED must say why).")
    target = "SUPERSEDED" if getattr(args, "superseded", False) else "ABORTED"

    # Remove the worktree IF one exists; tolerate its absence so a queue-only
    # (never-started) CR can still be aborted with this single command.
    wt_dir = _worktree_dir(main_wt, args.cr)
    wt = _find_worktree(main_wt, wt_dir)
    if wt is not None and wt.get("branch") and not wt.get("detached"):
        branch = wt["branch"]
        if not args.force and not _is_clean(wt_dir):
            sys.exit(f"[worktree-flow] ERROR: {wt_dir} has uncommitted changes. RECOVER first — "
                     f"commit the work worth keeping onto the branch (it is KEPT as the recovery "
                     f"point unless --delete-branch) or stash it, then re-run. --force discards.")
        rm = ["worktree", "remove", wt_dir] + (["--force"] if args.force else [])
        if args.dry_run:
            print(f"[dry-run] git -C {main_wt} {' '.join(rm)}")
            if args.delete_branch:
                print(f"[dry-run] git -C {main_wt} branch -D {branch}")
            print(f"[dry-run] record {args.cr} → {target} on the CR in Crucible's queue  ({args.reason})")
            return 0
        r = _git(rm, main_wt)
        if r.returncode != 0:
            sys.stderr.write(r.stderr)
            return 1
        _git(["worktree", "prune"], main_wt)
        print(f"abort: removed worktree {wt_dir}")
        if args.delete_branch:
            d = _git(["branch", "-D", branch], main_wt)
            if d.returncode != 0:
                sys.stderr.write(d.stderr)
                return 1
            print(f"abort: deleted branch {branch}")
        else:
            print(f"abort: branch {branch} kept (delete with: git -C {main_wt} branch -D {branch})")
    else:
        if args.dry_run:
            print(f"[dry-run] no worktree for {args.cr}; record → {target} on the CR in Crucible's queue  ({args.reason})")
            return 0
        print(f"abort: no live worktree for {args.cr} (queue-only or already removed)")

    _unset_track(main_wt, args.cr)  # tidy the track label (best-effort; harmless if absent)
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _add_project_dir_arg(p):
    p.add_argument(
        "--project-dir",
        help="Override repo root (default: $WORKTREE_FLOW_PROJECT_DIR, else the git repo "
             "containing the current directory). The MAIN worktree is then resolved from "
             "git, so this works even when invoked from inside a worktree.",
    )


def _add_dry_run_arg(p):
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the exact git commands that would run; mutate nothing.",
    )


def main():
    p = argparse.ArgumentParser(prog="worktree-flow", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start", help="Create an isolated worktree + feature branch for a CR.")
    s.add_argument("--cr", required=True, help="CR id, e.g. CR-NAI-248 (also the worktree dir name)")
    s.add_argument("--slug", help="Descriptive branch suffix, e.g. stage-subtask-multiplicity")
    s.add_argument("--branch", help="Full branch name override (must start with the feature prefix)")
    s.add_argument("--base", help="Base ref (default: the gitflow develop branch). Branches off LOCAL.")
    s.add_argument("--track", help="Human track/session label (e.g. 'Track 1 - Nai') stamped onto the "
                                   "worktree (git config wf.track.<cr>) and shown in `status`. "
                                   "Falls back to $WF_TRACK.")
    _add_dry_run_arg(s)
    _add_project_dir_arg(s)
    s.set_defaults(func=cmd_start)

    st = sub.add_parser("status", help="Parallel-execution dashboard: worktrees, ahead/behind, rebase need, inferred phase.")
    _add_project_dir_arg(st)
    st.set_defaults(func=cmd_status)

    sy = sub.add_parser("sync", help="Rebase a CR's feature branch onto develop (aborts cleanly on conflict).")
    sy.add_argument("--cr", required=True, help="CR id whose worktree/branch to rebase")
    _add_dry_run_arg(sy)
    _add_project_dir_arg(sy)
    sy.set_defaults(func=cmd_sync)

    f = sub.add_parser("finish", help="Close dance: lock -> rebase-if-needed -> worktree remove -> git flow finish.")
    f.add_argument("--cr", required=True, help="CR id to finish")
    f.add_argument("--note", dest="close_note",
                   help="close-out delivery/shipped summary (accepted for compatibility; the "
                        "close-out record itself now lives on the CR in Crucible's queue)")
    f.add_argument("--push", action="store_true", help="Also `git push origin develop` after merge")
    f.add_argument("--no-auto-sync", action="store_true",
                   help="Fail (instead of auto-rebasing) if develop moved; forces an explicit `sync`")
    _add_dry_run_arg(f)
    _add_project_dir_arg(f)
    f.set_defaults(func=cmd_finish)

    ab = sub.add_parser("abort", help="Abandon a CR (cancelled/superseded): remove its worktree if one exists (+ optionally its branch).")
    ab.add_argument("--cr", help="CR id to abort (worktree removed if present)")
    ab.add_argument("--delete-branch", action="store_true", help="Also delete the feature branch (git branch -D)")
    ab.add_argument("--force", action="store_true", help="Discard uncommitted changes in the worktree")
    ab.add_argument("--reason", help="REQUIRED cause (unless --release-lock): why it's aborted/superseded (e.g. 'replaced by CR-X') — record it on the CR in Crucible's queue")
    ab.add_argument("--superseded", action="store_true", help="Mark SUPERSEDED (replaced by another CR) instead of the default ABORTED (cancelled/dropped)")
    ab.add_argument("--release-lock", action="store_true",
                    help="Break a stale merge lock (only if you are SURE no finish is running)")
    _add_dry_run_arg(ab)
    _add_project_dir_arg(ab)
    ab.set_defaults(func=cmd_abort)

    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
