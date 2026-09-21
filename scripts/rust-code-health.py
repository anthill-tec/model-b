#!/usr/bin/env python3
# Owner: Model B (roundhouse/model-b) — adopted by CR-MDB-022 §S1.
# Consuming skills: memory-templates (rust-orchestration.md); driven by the code-health
#   skill, which this repo's skills-src does not publish yet.
#
"""rust-code-health.py — code-health snapshots for Cargo workspaces.

Thin Model-B orchestrator over rust-crate-map.py + rust-dead-scan.py.
A SNAPSHOT = { crate/module map + dead-code scan + frozen ledger + frozen
retention register } pinned to a git commit — the manifest records HEAD sha,
branch, and tree cleanliness (dirty snapshots warn loudly; git history is the
checkpoint reference). Snapshots are IMMUTABLE, append-only directories under
<out>/health/, so pre-cull claims can never be quietly rewritten.

Snapshot-taking is the MAINLINE orchestrator's responsibility, at defined
points in time: the exercise baseline, PRE (at slice dispatch) and POST
(after merge) for EVERY cull run, and on demand for decision support.

Usage:
  rust-code-health.py snapshot --phase {baseline,pre,post,adhoc} [--slice ID]
                               [--project-dir DIR] [--out DIR] [--name NAME]
  rust-code-health.py query trend
  rust-code-health.py query crate <pkg>
  rust-code-health.py query delta <snap-a> <snap-b>
  rust-code-health.py query ledger [FILTER]      # status/verdict/crate filter
  rust-code-health.py ledger assign --slice CR-X --ids F-1,DS-...   # CR filing stamps findings
  rust-code-health.py ledger sync [--slice CR-X --db-state STATE]   # board->ledger mirror / full true-up

Board->ledger auto-link (Maintenance CRs ONLY): the ledger is the SOURCE for
maintenance-CR planning, filed in TWO EXPLICIT STEPS (CR-MDB-028 §S6 — the
one-act convenience is gone with the local ChangeSet DB):
  1. `python-crucible.py cr-plan --cr CR-X --title "..." --release R --wave N`
     files the CR on Crucible's queue (the board that owns the plan).
  2. `rust-code-health.py ledger assign --slice CR-X --ids F-...,DS-...`
     stamps each finding's `slice` with that CR (this tool, standalone).
Every subsequent board transition mirrors via schedule_db.set_state -> `ledger
sync` (IN_PROGRESS -> IN_PROGRESS, COMPLETED -> COMPLETED + merge commit,
ABORTED/SUPERSEDED -> findings return to the APPROVED pool). POST snapshots
RATIFY completion: a finding whose stable id still appears in the fresh scan is
flagged NOT-RATIFIED in health_delta.md and the ledger.

The audit-cull ledger is MACHINE-READABLE: audit-cull-ledger.jsonl, one JSON
object per finding (schema v1). Its keys join every snapshot asset:
  crate  -> crate_map_baseline.json .crates[].pkg
  path   -> .crates[].modules[].path      line -> dead-scan site
  id     -> dead_scan_report finding ids (stable DS-* hashes)
  register -> dead_code_register.toml keep_future[].ledger
  first_seen/resolved_in -> health/<snapshot-dir> names (embed date+sha+phase)
  commit -> git history        slice -> ChangeSet-DB CR id

Layout produced (all git-committed):
  <out>/health/<date>_<sha>_<phase>[_<slice>]/
    snapshot.json          manifest: head, branch, dirty, phase, slice, totals
    crate_map_baseline.{json,md} + <name>_crate_map.{dot,svg}
    dead_scan_report.{json,md}
    audit-cull-ledger.jsonl frozen copy of the living ledger
    dead_code_register.toml frozen copy of the retention register
    health_delta.md        (post only) delta vs the paired pre snapshot
  <out>/health/index.json  regenerated series index (the RAG/trend entry point)
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
LIVING = ["crate_map_baseline.json", "crate_map_baseline.md",
          "dead_scan_report.json", "dead_scan_report.md"]


def sh(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def resolve_root(args):
    if args.project_dir:
        return Path(args.project_dir).resolve()
    r = sh(["git", "rev-parse", "--show-toplevel"])
    return Path(r.stdout.strip()) if r.returncode == 0 else Path.cwd()


def git_info(root):
    head = sh(["git", "-C", str(root), "rev-parse", "--short", "HEAD"]).stdout.strip()
    branch = sh(["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    dirty = bool(sh(["git", "-C", str(root), "status", "--porcelain"]).stdout.strip())
    return head or "unknown", branch or "?", dirty


def scan_counts(ds):
    inv = ds.get("inventory", [])
    cand = ds.get("pub_scan", {}).get("candidates", [])
    tiers = {}
    for c in cand:
        tiers[c["tier"]] = tiers.get(c["tier"], 0) + 1
    return {
        "allow_bare": sum(1 for f in inv if f["attr"] == "allow"),
        "expect_marks": sum(1 for f in inv if f["attr"] == "expect"),
        "deprecated": sum(1 for f in inv if f["attr"] == "deprecated"),
        "pub_candidates": len(cand), "pub_tiers": tiers,
        "unused_deps": len(ds.get("deps", {}).get("machete", {}).get("unused", [])),
        "unused_features": len(ds.get("deps", {}).get("features", [])),
        "boundary_violations": len(ds.get("boundaries", {}).get("violations", [])),
        "hoist_candidates": len(ds.get("boundaries", {}).get("hoist_candidates", [])),
    }


def rebuild_index(health_dir):
    entries = []
    for d in sorted(health_dir.iterdir()) if health_dir.exists() else []:
        mf = d / "snapshot.json"
        if d.is_dir() and mf.exists():
            m = json.loads(mf.read_text())
            entries.append({"dir": d.name, **{k: m.get(k) for k in
                            ("date", "head", "branch", "dirty", "phase", "slice")},
                            "totals": m.get("totals", {})})
    (health_dir / "index.json").write_text(json.dumps(entries, indent=1))
    return entries


def totals_row(t):
    return {
        "prod_loc": t.get("prod_loc"), "test_loc":
            (t.get("src_testgated_loc", 0) + t.get("tests_dir_loc", 0)),
        "tests": t.get("tests"), "ignored": t.get("ignored"),
        "allow_bare": t.get("allow_bare"), "expect_marks": t.get("expect_marks"),
        "deprecated": t.get("deprecated"), "pub_candidates": t.get("pub_candidates"),
        "unused_deps": t.get("unused_deps"), "unused_features": t.get("unused_features"),
    }


def delta_md(pre_dir, post_dir):
    pre = json.loads((pre_dir / "snapshot.json").read_text())
    post = json.loads((post_dir / "snapshot.json").read_text())
    a, b = totals_row(pre["totals"]), totals_row(post["totals"])
    lines = [f"# Health delta — `{pre_dir.name}` → `{post_dir.name}`", "",
             "| metric | pre | post | Δ |", "|---|---:|---:|---:|"]
    for k in a:
        if a[k] is None and b[k] is None:
            continue
        av, bv = a[k] or 0, b[k] or 0
        d = bv - av
        lines.append(f"| {k} | {av} | {bv} | {'+' if d > 0 else ''}{d} |")
    # per-crate LOC movers
    pm = {c["pkg"]: c for c in json.loads((pre_dir / "crate_map_baseline.json").read_text())["crates"]}
    qm = {c["pkg"]: c for c in json.loads((post_dir / "crate_map_baseline.json").read_text())["crates"]}
    movers = []
    for pkg in set(pm) | set(qm):
        pa = pm.get(pkg, {}).get("total_loc", 0)
        pb = qm.get(pkg, {}).get("total_loc", 0)
        if pa != pb:
            movers.append((pb - pa, pkg, pa, pb))
    if movers:
        lines += ["", "## Per-crate LOC movers", "",
                  "| crate | pre | post | Δ |", "|---|---:|---:|---:|"]
        for d, pkg, pa, pb in sorted(movers):
            lines.append(f"| {pkg} | {pa} | {pb} | {'+' if d > 0 else ''}{d} |")
    removed = set(pm) - set(qm)
    added = set(qm) - set(pm)
    if removed:
        lines.append(f"\nCrates REMOVED: {', '.join(sorted(removed))}")
    if added:
        lines.append(f"\nCrates ADDED: {', '.join(sorted(added))}")
    return "\n".join(lines) + "\n"


def _ledger_path(out, domain="cull"):
    # Generalized audit-ledger mechanism (2026-07-06): the same assign/sync/ratify
    # lifecycle serves ANY itemized audit domain, not just cull. `cull` keeps the
    # historical filename; any other domain -> `<domain>-audit-ledger.jsonl`.
    # Snapshot + health-report stay cull-only (they measure cull-effect vs baseline).
    fname = "audit-cull-ledger.jsonl" if domain == "cull" else f"{domain}-audit-ledger.jsonl"
    return out / fname


def _load_ledger(out, domain="cull"):
    p = _ledger_path(out, domain)
    if not p.exists():
        return None
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def _save_ledger(out, rows, domain="cull"):
    _ledger_path(out, domain).write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")


def _commit_ledger(root, out, message, domain="cull"):
    """Immediately commit the ledger file after a mutation (user directive
    2026-07-03: no uncommitted mirror-write windows on the integration tree).
    Scoped to the ledger path only; best-effort with index.lock retry — a
    failure never fails the caller (Mainline eager-commit is the backstop)."""
    lp = _ledger_path(out, domain)
    try:
        rel = str(lp.relative_to(root))
    except ValueError:
        return  # ledger outside the repo — nothing to commit
    for attempt in (1, 2, 3):
        sh(["git", "-C", str(root), "add", "--", rel])
        p = sh(["git", "-C", str(root), "commit", "-m", message, "--", rel])
        combined = (p.stdout or "") + (p.stderr or "")
        if p.returncode == 0:
            print(f"[health] ledger committed: {message}")
            return
        if "nothing to commit" in combined or "no changes added" in combined:
            return
        if "index.lock" in combined and attempt < 3:
            time.sleep(0.5 * attempt)
            continue
        print(f"[health] warn: ledger auto-commit failed (Mainline eager-commit "
              f"is the backstop): {combined.strip()[:160]}", file=sys.stderr)
        return


def _commit_paths(root, paths, message):
    """Scoped best-effort auto-commit for snapshot output (snapshot dir + the
    refreshed LIVING asset copies + health index). Same contract as
    _commit_ledger: never fails the caller; index.lock retry x3."""
    rels = []
    for p in paths:
        try:
            rels.append(str(Path(p).relative_to(root)))
        except ValueError:
            continue  # outside the repo — nothing to commit
    if not rels:
        return
    for attempt in (1, 2, 3):
        sh(["git", "-C", str(root), "add", "--"] + rels)
        p = sh(["git", "-C", str(root), "commit", "-m", message, "--"] + rels)
        combined = (p.stdout or "") + (p.stderr or "")
        if p.returncode == 0:
            print(f"[health] committed: {message}")
            return
        if "nothing to commit" in combined or "no changes added" in combined:
            return
        if "index.lock" in combined and attempt < 3:
            time.sleep(0.5 * attempt)
            continue
        print(f"[health] warn: snapshot auto-commit failed (commit manually): "
              f"{combined.strip()[:160]}", file=sys.stderr)
        return


def _merge_commit(root, cr):
    r = sh(["git", "-C", str(root), "log", "--merges", "-1",
            "--format=%h", "--grep", cr])
    return r.stdout.strip() or None


def _open_hist(r, cr, today):
    """Ensure an OPEN slice_history entry for cr (the finding's CR lineage —
    the across-time M:N, git-diffable in place)."""
    h = r.setdefault("slice_history", [])
    if not any(e["cr"] == cr and e.get("outcome") is None for e in h):
        h.append({"cr": cr, "assigned": today, "outcome": None})


def _close_hist(r, cr, outcome, today):
    h = r.setdefault("slice_history", [])
    for e in h:
        if e["cr"] == cr and e.get("outcome") is None:
            e["outcome"], e["closed"] = outcome, today
            return
    # legacy row without an open entry — backfill so lineage stays complete
    h.append({"cr": cr, "assigned": r.get("verdict_date") or today,
              "outcome": outcome, "closed": today})


def _apply_db_state(rows, cr, db_state, commit, today):
    """Mirror ONE CR's board state onto its assigned ledger rows (maintenance link)."""
    changed = 0
    for r in rows:
        if r.get("slice") != cr:
            continue
        s = r.get("status")
        if db_state == "IN_PROGRESS" and s in ("PROPOSED", "APPROVED"):
            r["status"], r["status_date"], changed = "IN_PROGRESS", today, changed + 1
            _open_hist(r, cr, today)
        elif db_state == "COMPLETED" and s in ("PROPOSED", "APPROVED", "IN_PROGRESS"):
            r["status"], r["status_date"], changed = "COMPLETED", today, changed + 1
            if commit and not r.get("commit"):
                r["commit"] = commit
            _close_hist(r, cr, "COMPLETED", today)
        elif db_state in ("ABORTED", "SUPERSEDED") and s != "COMPLETED":
            r["status"], r["status_date"] = "APPROVED", today
            _close_hist(r, cr, db_state, today)
            r["slice"] = None  # finding returns to the pool
            changed += 1
    return changed


def cmd_ledger(args):
    root = resolve_root(args)
    out = Path(args.out).resolve() if args.out else root / "docs/research/assets"
    rows = _load_ledger(out, args.domain)
    if rows is None:
        print(f"[health] no ledger at {_ledger_path(out, args.domain)} — nothing to do")
        return
    today = date.today().isoformat()
    if args.action == "assign":
        ids = [i.strip() for i in (args.ids or "").split(",") if i.strip()]
        hit = 0
        for r in rows:
            if r["id"] in ids:
                if r.get("status") not in ("PROPOSED", "APPROVED"):
                    print(f"[health] warn: {r['id']} is {r.get('status')} — not reassignable")
                    continue
                if r.get("slice") and r["slice"] != args.slice:
                    # single-active-owner invariant: close the old lineage entry
                    _close_hist(r, r["slice"], "REASSIGNED", today)
                r["slice"] = args.slice
                _open_hist(r, args.slice, today)
                hit += 1
        _save_ledger(out, rows, args.domain)
        missing = set(ids) - {r["id"] for r in rows}
        print(f"[health] ledger assign: {hit}/{len(ids)} findings -> slice {args.slice}"
              + (f" (UNKNOWN ids: {', '.join(sorted(missing))})" if missing else ""))
        if hit and not args.no_commit:
            _commit_ledger(root, out, f"chore(ledger): assign {hit} finding(s) -> {args.slice}", args.domain)
    elif args.action == "sync":
        if args.slice and args.db_state:
            commit = args.commit
            if args.db_state == "COMPLETED" and not commit:
                commit = _merge_commit(root, args.slice)
            n = _apply_db_state(rows, args.slice, args.db_state, commit, today)
            _save_ledger(out, rows, args.domain)
            print(f"[health] ledger sync: {args.slice} -> {args.db_state}: {n} row(s) updated")
            if n and not args.no_commit:
                _commit_ledger(root, out,
                               f"chore(ledger): {args.slice} -> {args.db_state} mirror ({n} row(s))", args.domain)
        else:
            total = _true_up_against_board(root, rows, today)
            if total is None:
                print("[health] no ChangeSet DB / schedule_db — full sync skipped")
                return
            _save_ledger(out, rows, args.domain)
            print(f"[health] ledger full sync: {total} row(s) trued up against the board")
            if total and not args.no_commit:
                _commit_ledger(root, out, f"chore(ledger): full board true-up ({total} row(s))", args.domain)


def _true_up_against_board(root, rows, today):
    """Mirror every assigned slice's board state onto the ledger (pull true-up)."""
    sys.path.insert(0, str(SCRIPTS))
    try:
        import schedule_db as sdb
    except ImportError:
        return None
    import os as _os
    if not _os.path.exists(sdb.db_path(str(root))):
        return None
    con = sdb.connect(str(root))
    total = 0
    for cr in sorted({r["slice"] for r in rows if r.get("slice")}):
        row = sdb.get(con, cr)
        if row is None:
            continue
        commit = _merge_commit(root, cr) if row["state"] == "COMPLETED" else None
        total += _apply_db_state(rows, cr, row["state"], commit, today)
    return total


def _ratify(rows, slice_id, snap, snap_name, today):
    """POST-snapshot ratification: a COMPLETED finding whose stable id still
    appears in the fresh scan did NOT actually get culled."""
    ds = json.loads((snap / "dead_scan_report.json").read_text())
    live_ids = {f["id"] for f in ds.get("inventory", [])} | \
               {c["id"] for c in ds.get("pub_scan", {}).get("candidates", [])}
    cm_pkgs = {c["pkg"] for c in
               json.loads((snap / "crate_map_baseline.json").read_text())["crates"]}
    results = []
    for r in rows:
        if r.get("slice") != slice_id or r.get("status") != "COMPLETED":
            continue
        if r["id"].startswith("DS-") and r.get("source") not in ("seed", "manual"):
            verdict = "NOT-RATIFIED" if r["id"] in live_ids else "RATIFIED"
        elif r.get("verdict") == "CULL" and r.get("crate") and r["crate"] not in cm_pkgs:
            verdict = "RATIFIED"  # whole-crate cull: the member is gone from the map
        elif r["id"] in live_ids:
            verdict = "NOT-RATIFIED"
        else:
            verdict = "MANUAL"    # seed/manual finding — Mainline confirms by hand
        r["ratified"] = verdict
        r["ratified_in"] = snap_name
        if verdict != "NOT-RATIFIED":
            r["resolved_in"] = snap_name
        r["status_date"] = today
        results.append((r["id"], verdict, r.get("item") or ""))
    return results


def cmd_snapshot(args):
    root = resolve_root(args)
    out = Path(args.out).resolve() if args.out else root / "docs/research/assets"
    name = args.name or root.name
    head, branch, dirty = git_info(root)
    if dirty:
        print("[health] ⚠ WORKING TREE DIRTY — a snapshot should pin a real commit; "
              "recorded as dirty=true, treat with suspicion.", file=sys.stderr)
    snap_name = f"{date.today().isoformat()}_{head}_{args.phase}" + \
                (f"_{args.slice}" if args.slice else "")
    snap = out / "health" / snap_name
    if snap.exists():
        sys.exit(f"[health] REFUSED: {snap} exists — snapshots are immutable.")
    snap.mkdir(parents=True)

    # seed configs so sub-tools behave identically to the living run
    for cfg in ("crate_map.toml", "dead_code_register.toml", "boundary_rules.toml"):
        if (out / cfg).exists():
            shutil.copy2(out / cfg, snap / cfg)

    r1 = sh([sys.executable, str(SCRIPTS / "rust-crate-map.py"),
             "--project-dir", str(root), "--out", str(snap), "--name", name])
    print(r1.stdout, end="")
    r2 = sh([sys.executable, str(SCRIPTS / "rust-dead-scan.py"),
             "--project-dir", str(root), "--out", str(snap)])
    print(r2.stdout, end="")
    if r1.returncode or r2.returncode:
        sys.exit(f"[health] sub-tool failed:\n{r1.stderr}\n{r2.stderr}")

    # true up the ledger against the board, ratify (post), THEN freeze it
    ratification = []
    rows = _load_ledger(out)
    if rows is not None:
        today = date.today().isoformat()
        try:
            _true_up_against_board(root, rows, today)
        except Exception as e:
            print(f"[health] warn: board true-up failed: {e}", file=sys.stderr)
        if args.phase == "post" and args.slice:
            ratification = _ratify(rows, args.slice, snap, snap_name, today)
        _save_ledger(out, rows)
        shutil.copy2(_ledger_path(out), snap / "audit-cull-ledger.jsonl")

    cm = json.loads((snap / "crate_map_baseline.json").read_text())
    ds = json.loads((snap / "dead_scan_report.json").read_text())
    totals = {**cm["meta"]["totals"], **scan_counts(ds)}
    manifest = {"schema": 1, "project": name, "date": date.today().isoformat(),
                "head": head, "branch": branch, "dirty": dirty,
                "phase": args.phase, "slice": args.slice,
                "keys": "crate(pkg) -> module(file path) -> site(line); "
                        "finding IDs DS-* stable across snapshots",
                "totals": totals,
                "files": sorted(p.name for p in snap.iterdir())}
    (snap / "snapshot.json").write_text(json.dumps(manifest, indent=1))

    # refresh the LIVING copies in assets root from this snapshot
    for f in LIVING + [f"{name}_crate_map.dot", f"{name}_crate_map.svg"]:
        if (snap / f).exists():
            shutil.copy2(snap / f, out / f)

    if args.phase == "post":
        idx = rebuild_index(out / "health")
        pres = [e for e in idx if e["phase"] in ("pre", "baseline")
                and (e.get("slice") == args.slice or e["phase"] == "baseline")]
        pres = [e for e in pres if e["dir"] != snap_name]
        if pres:
            paired = next((e for e in reversed(pres) if e.get("slice") == args.slice),
                          pres[-1])
            delta = delta_md(out / "health" / paired["dir"], snap)
            if ratification:
                delta += "\n## Ratification (ledger vs fresh scan)\n\n"
                for fid_, verdict, item in ratification:
                    mark = {"RATIFIED": "✅", "NOT-RATIFIED": "🛑", "MANUAL": "❓"}[verdict]
                    delta += f"- {mark} `{fid_}` **{verdict}** {item}\n"
                bad = sum(1 for _, v, _ in ratification if v == "NOT-RATIFIED")
                delta += (f"\n**{bad} NOT-RATIFIED finding(s) — the slice claimed "
                          f"completion but they survive. Do not sign off.**\n" if bad
                          else "\nAll scan-verifiable findings ratified.\n")
            (snap / "health_delta.md").write_text(delta)
            print(f"[health] delta vs {paired['dir']} -> health_delta.md"
                  + (f" ({sum(1 for _, v, _ in ratification if v == 'NOT-RATIFIED')} "
                     f"NOT-RATIFIED)" if ratification else ""))
        else:
            print("[health] no paired pre/baseline snapshot found — no delta")
    rebuild_index(out / "health")
    # auto-commit the snapshot dir + refreshed LIVING copies + index (user
    # directive 2026-07-04: snapshot runs must not leave the tree dirty)
    living_paths = [out / f for f in LIVING + [f"{name}_crate_map.dot",
                                               f"{name}_crate_map.svg"]]
    _commit_paths(root, [snap, out / "health" / "index.json"] + living_paths,
                  f"docs(health): {args.phase.upper()} snapshot {snap_name}")
    print(f"[health] snapshot {snap_name} @ {head} ({branch}"
          f"{', DIRTY' if dirty else ''}) — {len(manifest['files'])} files")


def cmd_query(args):
    root = resolve_root(args)
    out = Path(args.out).resolve() if args.out else root / "docs/research/assets"
    health = out / "health"
    idx = rebuild_index(health)
    if args.what == "trend":
        print("| snapshot | phase | prod | test | tests# | allows | expects | pub-cand | deps |")
        print("|---|---|---:|---:|---:|---:|---:|---:|---:|")
        for e in idx:
            t = totals_row(e["totals"])
            print(f"| {e['dir']} | {e['phase']} | {t['prod_loc']} | {t['test_loc']} | "
                  f"{t['tests']} | {t['allow_bare']} | {t['expect_marks']} | "
                  f"{t['pub_candidates']} | {t['unused_deps']} |")
    elif args.what == "crate":
        pkg = args.a
        print(f"# {pkg} across snapshots")
        for e in idx:
            cm = json.loads((health / e["dir"] / "crate_map_baseline.json").read_text())
            row = next((c for c in cm["crates"] if c["pkg"] == pkg), None)
            if row:
                print(f"- {e['dir']} ({e['phase']}): prod {row['prod_loc']}, "
                      f"test {row['src_testgated_loc'] + row['tests_dir_loc']}, "
                      f"tests# {row['tests']}, dead {row['allow_dead']}, fan-in {row['fan_in']}")
        if idx:
            ds = json.loads((health / idx[-1]["dir"] / "dead_scan_report.json").read_text())
            open_f = [f for f in ds.get("inventory", []) if f["crate"] == pkg]
            cand = [c for c in ds.get("pub_scan", {}).get("candidates", []) if c["crate"] == pkg]
            print(f"\nOpen findings @ {idx[-1]['dir']}: {len(open_f)} suppressions, "
                  f"{len(cand)} pub candidates")
            for f in open_f:
                print(f"- {f['id']} [{f['attr']}] {f['path']}:{f['line']} {f['item']} ({f['class']})")
            for c in cand:
                print(f"- {c['id']} [{c['tier']}] {c['path']}:{c['line']} {c['kind']} {c['name']}")
    elif args.what == "delta":
        print(delta_md(health / args.a, health / args.b), end="")
    elif args.what == "ledger":
        lpath = out / "audit-cull-ledger.jsonl"
        if not lpath.exists():
            sys.exit(f"[health] no ledger at {lpath}")
        rows = [json.loads(l) for l in lpath.read_text().splitlines() if l.strip()]
        if args.a:
            rows = [r for r in rows if r.get("status") == args.a or
                    r.get("verdict") == args.a or r.get("crate") == args.a]
        by_status, by_verdict = {}, {}
        for r in rows:
            by_status[r.get("status")] = by_status.get(r.get("status"), 0) + 1
            by_verdict[r.get("verdict")] = by_verdict.get(r.get("verdict"), 0) + 1
        print(f"ledger rows: {len(rows)} | status {by_status} | verdict {by_verdict}")
        for r in rows:
            loc = f"{r.get('path') or ''}{':' + str(r['line']) if r.get('line') else ''}"
            print(f"- {r['id']} [{r.get('verdict')}/{r.get('status')}] "
                  f"{r.get('crate') or '(workspace)'} {loc} {r.get('item') or ''} — "
                  f"{r.get('finding', '')[:100]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("--phase", required=True, choices=["baseline", "pre", "post", "adhoc"])
    s.add_argument("--slice", default=None, help="slice/CR id for pre/post pairing")
    s.add_argument("--project-dir", default=None)
    s.add_argument("--out", default=None)
    s.add_argument("--name", default=None)
    q = sub.add_parser("query")
    q.add_argument("what", choices=["trend", "crate", "delta", "ledger"])
    q.add_argument("a", nargs="?", help="crate name | snapshot-a | ledger filter")
    q.add_argument("b", nargs="?", help="snapshot-b (delta)")
    q.add_argument("--project-dir", default=None)
    q.add_argument("--out", default=None)
    lg = sub.add_parser("ledger", help="mutate an audit ledger (assign findings / mirror board state) — any domain")
    lg.add_argument("action", choices=["assign", "sync"])
    lg.add_argument("--domain", default="cull",
                    help="audit-ledger domain: cull (default -> audit-cull-ledger.jsonl) | temporal | <name> -> <name>-audit-ledger.jsonl")
    lg.add_argument("--slice", default=None, help="CR id")
    lg.add_argument("--ids", default=None, help="comma-sep finding ids (assign)")
    lg.add_argument("--db-state", dest="db_state", default=None,
                    help="ChangeSet state to mirror (sync): IN_PROGRESS|COMPLETED|ABORTED|SUPERSEDED")
    lg.add_argument("--commit", default=None, help="merge sha (sync COMPLETED; auto-detected if omitted)")
    lg.add_argument("--no-commit", dest="no_commit", action="store_true",
                    help="skip the immediate git commit of the ledger (for batching callers)")
    lg.add_argument("--project-dir", default=None)
    lg.add_argument("--out", default=None)
    args = ap.parse_args()
    if args.cmd == "snapshot":
        cmd_snapshot(args)
    elif args.cmd == "ledger":
        cmd_ledger(args)
    else:
        cmd_query(args)


if __name__ == "__main__":
    main()
