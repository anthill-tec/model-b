# Owner: Model B (roundhouse/model-b) — adopted by CR-MDB-022 §S1.
# Consuming skills: memory-templates (rust-orchestration.md); scripts/rust-code-health.py
#   imports it directly for its board→ledger full true-up.
#
# TRANSITIONAL — this file is on its way out; build nothing new on it.
# Superseded FOR MODEL B by: Crucible's queue — it owns workflow plan state/storage
#   from Crucible 0.2.0 onward; CR-MDB-028 retired Model B's last caller, so
#   scripts/worktree-flow.py is now purely git-derived and imports nothing from here.
# The MODULE ITSELF REMAINS shipped for its other consumers, which still hold live
#   state on it; migrating them is a CR-MDB-012 release item and not Model B's call
#   alone, so NO removal date is implied for this file.
# Until then it must not be extended: fix defects only; no new schema, verbs or callers.

"""schedule_db.py — shared scheduling library for the Model-B worktree-flow tooling.

A SQLite-backed **ChangeSet** store (the per-track lane plan) + git-derived trigger
evaluation. One row per CR (the "ChangeSet"). CR-MDB-028 removed Model B's last
caller — `worktree-flow.py` is now purely git-derived and imports nothing from here,
and Crucible's queue owns Model B's scheduling; the module remains for its other
consumers, which still drive it directly. reconcile() rebuilds the store from git
anytime. The DB file (.wf-schedule.db; a legacy
.nai-schedule.db is used when present) is GITIGNORED — a local, rebuildable index,
NOT a committed authority. Git stays the ground truth.

Board→ledger auto-link: every state transition of a `maintenance`-type ChangeSet
mirrors into the project's audit-cull ledger (docs/research/assets/
audit-cull-ledger.jsonl) via rust-code-health.py `ledger sync` — best-effort,
never fails the caller, no-op in projects without a ledger.

Trigger DSL (the PAUSE-UNTIL field), clauses AND-ed by ';':
  merged:CR-NAI-A,CR-NAI-B   → each CR's `Merge branch 'feature/<CR>…' into develop` is on develop
  quiet                      → no OTHER feature worktrees are live
  <empty/None>               → ready now
e.g.  "merged:CR-NAI-282,CR-NAI-285b,CR-NAI-306;quiet"
"""

import os
import re
import subprocess

DB_NAME = ".wf-schedule.db"            # neutral default (Model-B generic)
LEGACY_DB_NAME = ".nai-schedule.db"    # pre-2026-07-03 deployments keep working


def db_path(repo):
    """The ChangeSet DB file for a repo. One-time migration: a legacy-named DB
    is COPIED to the neutral name on first touch — state fully preserved, the
    legacy file kept untouched as a backup; all subsequent access uses the new
    name. (Both names belong in .gitignore.)"""
    new = os.path.join(repo, DB_NAME)
    legacy = os.path.join(repo, LEGACY_DB_NAME)
    if not os.path.exists(new) and os.path.exists(legacy):
        import shutil
        import sys
        shutil.copy2(legacy, new)
        print(f"[schedule_db] migrated {LEGACY_DB_NAME} -> {DB_NAME} (state copied; "
              f"legacy kept as backup; ensure {DB_NAME} is gitignored)", file=sys.stderr)
    return new


CR_TYPES = ("feature", "maintenance", "bugfix", "docs")


def slugify(text):
    """Branch-safe kebab derived from a heading (one value serves both):
    lowercase, non-alnum runs → '-', trimmed, capped. So `heading` is the single
    source of truth — the slug is just its branch-safe form, never a 2nd input."""
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]
STATES = ("DRAFT", "PENDING", "IN_PROGRESS", "COMPLETED", "ABORTED", "SUPERSEDED")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS changeset (
    cr          TEXT PRIMARY KEY,                 -- "CR-NAI-315" (unique key)
    track       TEXT,                             -- "Track 2 - Nai" (NULL = queue-only)
    seq         INTEGER,                          -- order within the lane (NULL until assigned)
    state       TEXT NOT NULL DEFAULT 'PENDING',  -- DRAFT|PENDING|IN_PROGRESS|COMPLETED|ABORTED|SUPERSEDED (DRAFT = planned/pre-spec, Mainline-only, never handed to a track; ABORTED/SUPERSEDED carry the cause in `note`)
    trigger     TEXT,                             -- PAUSE-UNTIL DSL (NULL = ready)
    wave        TEXT,
    depends_on  TEXT,                             -- comma-sep CRs (from the spec)
    cr_type     TEXT,                             -- feature|maintenance|bugfix|docs (NULL = feature); maintenance transitions mirror into the audit-cull ledger
    heading     TEXT,                             -- CR human title; the branch slug is slugify(heading)
    spec_path   TEXT,                             -- relative path to the CR spec file (e.g. docs/changes/CR-NAI-329-….md) so a track fetches metadata + spec location from the DB, not the README
    note        TEXT,                             -- freeform planning context (Mainline, set at `cs`)
    close_note  TEXT,                             -- close-out delivery/shipped summary — the track attaches it at `finish` (the detail that used to be hand-written into the README queue row)
    weight_done  INTEGER,                         -- Σ weight of COMPLETED tasks (track updates at each task end via `progress`)
    weight_total INTEGER,                         -- Σ weight of ALL planned tasks (grows when a FIX/cycle is added); Mainline estimates % ≈ weight_done/weight_total
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);
"""


# --------------------------------------------------------------------------- #
# repo / git plumbing (shared, so callers don't reimplement)

def _git(args, cwd="."):
    p = subprocess.run(["git"] + args, cwd=cwd,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return (p.returncode, p.stdout.strip())


def main_repo_root(cwd="."):
    """The main integration tree (where develop + the DB live), from any worktree."""
    rc, common = _git(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd)
    if rc != 0 or not common:
        raise RuntimeError("not inside a git repository")
    return os.path.dirname(os.path.normpath(common))


def _develop(repo):
    rc, out = _git(["config", "--get", "gitflow.branch.develop"], repo)
    return out if (rc == 0 and out) else "develop"


def read_env(repo, key, default=None):
    """Read KEY from <repo>/.env (gitignored, shared by every worktree of the
    repo). Strips inline `#` comments + surrounding quotes; exact-key match (so
    `FOO` never matches `FOO_BAR`). Returns the string value, or `default` if the
    file/key is absent. Shared so callers don't each reimplement
    .env parsing."""
    path = os.path.join(repo, ".env")
    if not os.path.isfile(path):
        return default
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, rhs = line.partition("=")
            if k.strip() == key:
                return rhs.split("#", 1)[0].strip().strip('"').strip("'")
    return default


def is_merged(repo, cr):
    """True once `Merge branch 'feature/<cr>…' into <develop>` is on develop
    (finish-direction only, never a sync merge; CR boundary so 285 != 285a)."""
    develop = _develop(repo)
    rc, out = _git(["log", develop, "--merges", "--pretty=%s"], repo)
    if rc != 0:
        return False
    prefix, suffix = f"Merge branch 'feature/{cr}", f"into {develop}"
    for s in out.splitlines():
        if s.startswith(prefix) and s.endswith(suffix) and s[len(prefix):len(prefix) + 1] in ("'", "-"):
            return True
    return False


def live_feature_worktrees(repo):
    """CR ids with a live worktree (excludes the main checkout)."""
    rc, out = _git(["worktree", "list", "--porcelain"], repo)
    crs, main_real = [], os.path.realpath(repo)
    if rc != 0:
        return crs
    for block in out.split("\n\n"):
        path = next((l[len("worktree "):] for l in block.splitlines()
                     if l.startswith("worktree ")), None)
        if path and os.path.realpath(path) != main_real:
            crs.append(os.path.basename(path.rstrip("/")))
    return crs


def _except_set(except_cr):
    """Normalize the `quiet`-clause exception arg → a set.
    Accepts a single CR id (str), an iterable of ids, or None. So callers can
    pass one cr (next_for_track: the row's own cr) or many (a quiet-clause exclude)."""
    if not except_cr:
        return set()
    if isinstance(except_cr, str):
        return {except_cr}
    return set(except_cr)


def trigger_met(con, trigger, except_cr=None):
    """Evaluate a trigger DSL string against the **ChangeSet DB** — the operational
    source of truth. `start`/`finish` maintain each row's state, so the DB already
    records what's merged; **no git scan happens here.** (reconcile() is the ONLY
    thing that consults git — to validate/rebuild the DB. That separation is the
    whole point: operational reads hit the DB; git is just the backing reconcile
    rebuilds from.) None/empty trigger → True.
      merged:CR  → CR's changeset state == COMPLETED  (set by `finish`)
      quiet      → no changeset is IN_PROGRESS         (set/cleared by `start`/`finish`)
    A CR named in `merged:` with no DB row → **unmet** (a scheduling gap to surface,
    never silently satisfied). `except_cr` (str | iterable | None) names rows the
    `quiet` clause ignores (e.g. the caller's own CR)."""
    if not trigger:
        return True
    exc = _except_set(except_cr)
    for clause in (c.strip() for c in trigger.split(";") if c.strip()):
        if clause == "quiet":
            if any(r["state"] == "IN_PROGRESS" and r["cr"] not in exc for r in all_rows(con)):
                return False
        elif clause.startswith("merged:"):
            for cr in (x.strip() for x in clause[len("merged:"):].split(",") if x.strip()):
                row = get(con, cr)
                if row is None or row["state"] != "COMPLETED":
                    return False
        else:
            return False  # unknown clause → treat as unmet (fail safe)
    return True


def trigger_unmet_reason(con, trigger, except_cr=None):
    """A short human reason a trigger is unmet (for HOLD output), or '' if met.
    DB-native — mirrors trigger_met (no git)."""
    if trigger_met(con, trigger, except_cr):
        return ""
    parts = []
    exc = _except_set(except_cr)
    for clause in (c.strip() for c in (trigger or "").split(";") if c.strip()):
        if clause == "quiet":
            busy = [r["cr"] for r in all_rows(con)
                    if r["state"] == "IN_PROGRESS" and r["cr"] not in exc]
            if busy:
                parts.append("in progress: " + ", ".join(busy))
        elif clause.startswith("merged:"):
            pend = []
            for cr in (x.strip() for x in clause[len("merged:"):].split(",") if x.strip()):
                row = get(con, cr)
                if row is None:
                    pend.append(f"{cr}(no changeset)")
                elif row["state"] != "COMPLETED":
                    pend.append(cr)
            if pend:
                parts.append("not completed: " + ", ".join(pend))
    return " | ".join(parts)


# --------------------------------------------------------------------------- #
# DB access (lazy import of sqlite3 so pure git-only callers stay light)

def connect(repo):
    import sqlite3
    con = sqlite3.connect(db_path(repo))
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    _migrate(con)
    con.commit()
    return con


def _migrate(con):
    """Additive column migrations for DBs created before a column existed.
    `CREATE TABLE IF NOT EXISTS` never alters an existing table, so new columns
    are added here — idempotent (PRAGMA-checked), so it is a no-op once applied."""
    cols = {r["name"] for r in con.execute("PRAGMA table_info(changeset)")}
    if "spec_path" not in cols:
        con.execute("ALTER TABLE changeset ADD COLUMN spec_path TEXT")
    if "close_note" not in cols:
        con.execute("ALTER TABLE changeset ADD COLUMN close_note TEXT")
    if "weight_done" not in cols:
        con.execute("ALTER TABLE changeset ADD COLUMN weight_done INTEGER")
    if "weight_total" not in cols:
        con.execute("ALTER TABLE changeset ADD COLUMN weight_total INTEGER")
    if "cr_type" not in cols:
        con.execute("ALTER TABLE changeset ADD COLUMN cr_type TEXT")


def upsert(con, cr, **fields):
    """Insert or update a changeset by cr; always touches updated_at."""
    row = get(con, cr)
    fields = {k: v for k, v in fields.items() if v is not None}
    if row is None:
        cols = ["cr"] + list(fields)
        con.execute(f"INSERT INTO changeset ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                    [cr] + list(fields.values()))
    elif fields:
        sets = ", ".join(f"{k}=?" for k in fields) + ", updated_at=datetime('now')"
        con.execute(f"UPDATE changeset SET {sets} WHERE cr=?", list(fields.values()) + [cr])
    con.commit()


def set_state(con, cr, state):
    if state not in STATES:
        raise ValueError(f"bad state {state!r}; one of {STATES}")
    con.execute("UPDATE changeset SET state=?, updated_at=datetime('now') WHERE cr=?", (state, cr))
    con.commit()
    _ledger_hook(con, cr, state)


def _repo_of(con):
    for row in con.execute("PRAGMA database_list"):
        if row["name"] == "main" and row["file"]:
            return os.path.dirname(row["file"])
    return None


def _ledger_hook(con, cr, state):
    """Board→ledger auto-link (the single state-change choke point, so EVERY
    transition path mirrors — start/finish/abort AND reconcile). Only fires for
    cr_type='maintenance'; best-effort: warns, never fails the caller."""
    import sys
    try:
        row = get(con, cr)
        if row is None or (row["cr_type"] or "feature") != "maintenance":
            return
        repo = _repo_of(con)
        tool = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rust-code-health.py")
        if not repo or not os.path.exists(tool):
            return
        p = subprocess.run(
            [sys.executable, tool, "ledger", "sync", "--slice", cr,
             "--db-state", state, "--project-dir", repo],
            capture_output=True, text=True, timeout=60)
        if p.stdout.strip():
            print(p.stdout.strip())
        if p.returncode != 0:
            print(f"[schedule_db] warn: ledger sync exited {p.returncode} for {cr}: "
                  f"{p.stderr.strip()[:200]}", file=sys.stderr)
    except Exception as e:  # the board op must never fail on ledger mirroring
        print(f"[schedule_db] warn: ledger hook failed for {cr}: {e}", file=sys.stderr)


def get(con, cr):
    return con.execute("SELECT * FROM changeset WHERE cr=?", (cr,)).fetchone()


def pct_complete(row):
    """Advisory % complete from the track's weighted task progress, or None if not
    reported. weight_total = Σ task weights in the cycle plan (grows when a FIX/cycle
    is added); weight_done = Σ completed task weights. ESTIMATE only — it regresses
    when scope is discovered, and is never a commitment."""
    wt = row["weight_total"]
    wd = row["weight_done"] or 0
    if not wt:
        return None
    return max(0, min(100, round(100 * wd / wt)))


def by_track(con, track):
    return con.execute(
        "SELECT * FROM changeset WHERE track=? ORDER BY seq IS NULL, seq, cr", (track,)).fetchall()


def all_rows(con):
    return con.execute(
        "SELECT * FROM changeset ORDER BY track IS NULL, track, seq IS NULL, seq, cr").fetchall()


def _split_deps(depends_on):
    """The comma-sep `depends_on` string → a clean list of CR ids."""
    if not depends_on:
        return []
    return [c.strip() for c in depends_on.split(",") if c.strip()]


def deps_met(con, depends_on):
    """True if every CR in `depends_on` is COMPLETED (or there are none). A named dep
    with no DB row → unmet (a scheduling gap to surface, never silently satisfied)."""
    for cr in _split_deps(depends_on):
        row = get(con, cr)
        if row is None or row["state"] != "COMPLETED":
            return False
    return True


def deps_unmet(con, depends_on):
    """The `depends_on` CRs not yet COMPLETED (for HOLD output); [] when all met."""
    out = []
    for cr in _split_deps(depends_on):
        row = get(con, cr)
        if row is None:
            out.append(f"{cr}(no changeset)")
        elif row["state"] != "COMPLETED":
            out.append(cr)
    return out


def hold_reason(con, row):
    """Combined human reason a PENDING row is not yet ready — unmet `depends_on`
    PLUS unmet `trigger` — or '' when ready."""
    parts = []
    du = deps_unmet(con, row["depends_on"])
    if du:
        parts.append("deps not complete: " + ", ".join(du))
    tr = trigger_unmet_reason(con, row["trigger"], except_cr=row["cr"])
    if tr:
        parts.append(tr)
    return " | ".join(parts)


def next_for_track(con, track):
    """The track's next actionable changeset — pure DB read, no git.
    READY ⟺ every `depends_on` CR is COMPLETED AND the `trigger` is met.
    → ('NEXT', row)      lowest-seq PENDING that is READY
    → ('HOLD', row)      lowest-seq PENDING but deps/trigger unmet
    → ('DRAINED', None)  no actionable (PENDING + waved) rows for this track (await assignment)
    """
    # Actionable = PENDING *with a wave*. NEVER handed to a track: DRAFT (pre-spec), terminal states,
    # AND a PENDING CR with NO wave — that's effectively DEFERRED (planned/specced but not scheduled
    # into a wave). 'DEFERRED' is INFERRED from (DRAFT|PENDING)+wave, not a stored state.
    pend = [r for r in by_track(con, track) if r["state"] == "PENDING" and r["wave"]]
    if not pend:
        return ("DRAINED", None)
    row = pend[0]
    if deps_met(con, row["depends_on"]) and trigger_met(con, row["trigger"], except_cr=row["cr"]):
        return ("NEXT", row)
    return ("HOLD", row)


def reconcile(con, repo):
    """Validate DB state vs git (the rebuildable-index guarantee). Returns a list
    of (cr, db_state, git_state) disagreements; does NOT auto-write (caller decides)."""
    live = set(live_feature_worktrees(repo))
    issues = []
    for r in all_rows(con):
        cr, st = r["cr"], r["state"]
        git_state = ("COMPLETED" if is_merged(repo, cr)
                     else "IN_PROGRESS" if cr in live else "PENDING")
        # DRAFT/ABORTED/SUPERSEDED are human (Mainline) decisions git can't infer; skip them.
        if st not in ("DRAFT", "ABORTED", "SUPERSEDED") and st != git_state:
            issues.append((cr, st, git_state))
    return issues
