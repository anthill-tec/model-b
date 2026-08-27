#!/usr/bin/env python3
# Owner: Model B (roundhouse/model-b) — adopted by CR-MDB-022 §S1.
# Consuming skills: memory-templates (rust-orchestration.md); invoked by
#   scripts/rust-code-health.py.
#
"""rust-crate-map.py — Cargo-workspace crate map + LOC metrics generator.

Model-B toolset sibling of worktree-flow.py / rust-crucible.py. Rerunnable:
collects per-crate LOC/test/audit metrics + workspace-internal dependency
edges, then renders a clustered Graphviz map. Artifacts land in
<project>/docs/research/assets/ by default so they are repo-committed,
doc-referenced, and indexable.

Usage:
  rust-crate-map.py [--project-dir DIR] [--out DIR] [--no-render] [--name NAME]

Outputs (in --out):
  crate_map_baseline.json   per-crate metrics + dep edges + totals (machine truth)
  crate_map_baseline.md     same as markdown table + edge list (diff-able)
  <name>_crate_map.dot      Graphviz source
  <name>_crate_map.svg      rendered map (needs `dot` on PATH)

Optional cluster config (checked at <out>/crate_map.toml):
  [render]
  omit_edges_into = ["pkg_a", "pkg_b"]        # near-universal fan-in magnets
  [render.aggregates.AGG_KEY]
  label = "scenarios (xN bins)"
  pattern = "pkg_prefix_*"                     # fnmatch on package name
  [clusters.key]
  label = "Cluster title"
  color = "#E8F0FE"
  members = ["pkg_a", "AGG_KEY", ...]          # package names or aggregate keys
Without a config, crates cluster by top-level member dir (crates/, bin/, ...).

LOC classification: code = non-blank, non-`//` lines (doc comments count as
comments). Test-gated attribution brace-matches #[cfg(test)]/#[cfg(any(test,..))]
blocks — an approximation (±1% at workspace scale), not a parser.
"""
import argparse
import fnmatch
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

try:
    import tomllib
except ImportError:  # < 3.11
    tomllib = None

SIGNALS = {
    "tests": re.compile(r"#\[(tokio::)?test[\]\(]|#\[rstest"),
    "ignored": re.compile(r"#\[ignore"),
    "allow_dead": re.compile(r"#\[allow\(dead_code"),
    "deprecated": re.compile(r"#\[deprecated"),
    "todo_fixme": re.compile(r"\b(TODO|FIXME)\b"),
}
CFG_TEST_RE = re.compile(r"^\s*#\[cfg\((test\)|any\(test)")
DEAD_HEAT_THRESHOLD = 10
FALLBACK_COLORS = ["#E8F0FE", "#E6F4EA", "#FEF7E0", "#FCE8E6", "#F3E8FD",
                   "#E0F7FA", "#FFF3E0", "#F1F8E9", "#ECEFF1"]

# Attribute-style signals count ONLY as a real `#[...]` attribute at the START of
# a line's code — never inside `//`/`///`/`//!` comments or string/doc prose
# (D3-scanfix: doc comments like "this test is `#[ignore]`'d" and source-scan
# test strings were inflating counts, e.g. 33 `#[ignore` hits / 1 real attr).
# `todo_fixme` is prose-level (lives in comments) and is counted across all lines.
ATTR_SIGNALS = ("tests", "ignored", "allow_dead", "deprecated")


def count_signals(text: str) -> dict:
    counts = {k: 0 for k in SIGNALS}
    for raw in text.splitlines():
        s = raw.lstrip()
        if not s.startswith("//"):
            for k in ATTR_SIGNALS:
                if SIGNALS[k].match(s):
                    counts[k] += 1
        counts["todo_fixme"] += len(SIGNALS["todo_fixme"].findall(raw))
    return counts


def git_head(root: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def classify_lines(path: Path):
    lines = path.read_text(errors="replace").splitlines()
    code = comment = blank = tg_code = 0
    n = len(lines)
    gated = [False] * n
    j = 0
    while j < n:
        if CFG_TEST_RE.match(lines[j]):
            k = j
            while k < n and (re.match(r"^\s*(#\[|//)", lines[k]) or not lines[k].strip()):
                k += 1
            depth, opened, end = 0, False, k
            while end < n:
                depth += lines[end].count("{") - lines[end].count("}")
                if lines[end].count("{"):
                    opened = True
                if opened and depth <= 0:
                    break
                if not opened and lines[end].rstrip().endswith(";"):
                    break
                end += 1
            for g in range(j, min(end + 1, n)):
                gated[g] = True
            j = end + 1
        else:
            j += 1
    for idx, raw in enumerate(lines):
        s = raw.strip()
        if not s:
            blank += 1
        elif s.startswith("//"):
            comment += 1
        else:
            code += 1
            if gated[idx]:
                tg_code += 1
    return code, comment, blank, tg_code


def scan_dir(d: Path, base: Path = None, kind: str = "src", modules: list = None):
    """Aggregate a dir; when `modules` is a list, append one per-file row to it
    (path relative to `base`, classified LOC + signals) — the module-level
    granularity that joins the crate map to dead-scan/ledger rows."""
    agg = {"code": 0, "comment": 0, "blank": 0, "tg_code": 0, "files": 0}
    sig = {k: 0 for k in SIGNALS}
    if not d.exists():
        return agg, sig
    for f in sorted(d.rglob("*.rs")):
        c, cm, b, tg = classify_lines(f)
        agg["code"] += c; agg["comment"] += cm; agg["blank"] += b
        agg["tg_code"] += tg; agg["files"] += 1
        text = f.read_text(errors="replace")
        fsig = count_signals(text)
        for k, v in fsig.items():
            sig[k] += v
        if modules is not None:
            modules.append({
                "path": str(f.relative_to(base)) if base else str(f),
                "kind": kind,
                "code": c, "testgated": tg, "comment": cm,
                **{k: v for k, v in fsig.items() if v},
            })
    return agg, sig


def parse_deps(member_dir: Path, pkg_names: set):
    text = (member_dir / "Cargo.toml").read_text()
    prod, dev = set(), set()
    section = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("["):
            section = s
            continue
        m = re.match(r'^([A-Za-z0-9_-]+)\s*(=|\.workspace)', s)
        if not m or section is None:
            continue
        name = m.group(1).replace("-", "_")
        if name not in pkg_names:
            continue
        if "dev-dependencies" in section:
            dev.add(name)
        elif "dependencies" in section and "build" not in section:
            prod.add(name)
        elif "build-dependencies" in section:
            prod.add(name + " (build)")
    return sorted(prod), sorted(dev)


def collect(root: Path):
    text = (root / "Cargo.toml").read_text()
    m = re.search(r"members\s*=\s*\[(.*?)\]", text, re.S)
    if not m:
        sys.exit("error: no [workspace] members in Cargo.toml")
    members = re.findall(r'"([^"]+)"', m.group(1))
    pkg_of = {}
    for mdir in members:
        mt = (root / mdir / "Cargo.toml").read_text()
        pm = re.search(r'^name\s*=\s*"([^"]+)"', mt, re.M)
        pkg_of[mdir] = pm.group(1).replace("-", "_")
    pkg_names = set(pkg_of.values())

    rows = []
    for mdir in members:
        base = root / mdir
        modules = []
        src_agg, src_sig = scan_dir(base / "src", base, "src", modules)
        t_agg, t_sig = scan_dir(base / "tests", base, "tests", modules)
        b_agg, _ = scan_dir(base / "benches", base, "benches", modules)
        e_agg, _ = scan_dir(base / "examples", base, "examples", modules)
        prod_deps, dev_deps = parse_deps(base, pkg_names)
        it_loc = t_agg["code"] + b_agg["code"] + e_agg["code"]
        rows.append({
            "dir": mdir, "pkg": pkg_of[mdir],
            "prod_loc": src_agg["code"] - src_agg["tg_code"],
            "src_testgated_loc": src_agg["tg_code"],
            "tests_dir_loc": it_loc,
            "total_loc": src_agg["code"] + it_loc,
            "comment_loc": src_agg["comment"] + t_agg["comment"],
            "files": src_agg["files"] + t_agg["files"] + b_agg["files"] + e_agg["files"],
            "tests": src_sig["tests"] + t_sig["tests"],
            "ignored": src_sig["ignored"] + t_sig["ignored"],
            "allow_dead": src_sig["allow_dead"] + t_sig["allow_dead"],
            "deprecated": src_sig["deprecated"] + t_sig["deprecated"],
            "todo_fixme": src_sig["todo_fixme"] + t_sig["todo_fixme"],
            "deps": prod_deps, "dev_deps": dev_deps,
            "modules": modules,
        })

    fan_in = {r["pkg"]: 0 for r in rows}
    for r in rows:
        for d in r["deps"]:
            d = d.replace(" (build)", "")
            if d in fan_in:
                fan_in[d] += 1
    for r in rows:
        r["fan_in"] = fan_in[r["pkg"]]
    rows.sort(key=lambda r: -r["total_loc"])
    tot = lambda k: sum(r[k] for r in rows)
    meta = {"head": git_head(root), "date": date.today().isoformat(),
            "members": len(rows),
            "totals": {k: tot(k) for k in
                       ("prod_loc", "src_testgated_loc", "tests_dir_loc", "total_loc",
                        "comment_loc", "files", "tests", "ignored", "allow_dead",
                        "deprecated", "todo_fixme")}}
    return meta, rows


def write_json_md(meta, rows, out: Path):
    (out / "crate_map_baseline.json").write_text(
        json.dumps({"meta": meta, "crates": rows}, indent=1))
    md = [f"# Crate metrics — @ `{meta['head']}` ({meta['date']})", "",
          "Generated by `rust-crate-map.py` — do not hand-edit. "
          "prod = src code LOC minus test-gated; src-tg = `#[cfg(test)]`-gated LOC in src; "
          "tests/ = tests+benches+examples dirs.", "",
          "| crate | prod | src-tg | tests/ | total | tests# | ign | dead | depr | todo | fan-in |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        md.append(f"| {r['pkg']} | {r['prod_loc']} | {r['src_testgated_loc']} | "
                  f"{r['tests_dir_loc']} | {r['total_loc']} | {r['tests']} | {r['ignored']} | "
                  f"{r['allow_dead']} | {r['deprecated']} | {r['todo_fixme']} | {r['fan_in']} |")
    t = meta["totals"]
    md.append(f"| **TOTAL ({meta['members']})** | **{t['prod_loc']}** | "
              f"**{t['src_testgated_loc']}** | **{t['tests_dir_loc']}** | **{t['total_loc']}** | "
              f"**{t['tests']}** | **{t['ignored']}** | **{t['allow_dead']}** | "
              f"**{t['deprecated']}** | **{t['todo_fixme']}** | |")
    md += ["", "## Workspace-internal dependency edges", ""]
    for r in sorted(rows, key=lambda r: r["dir"]):
        if r["deps"] or r["dev_deps"]:
            dep_s = ", ".join(r["deps"]) or "—"
            dev_s = f" · dev: {', '.join(r['dev_deps'])}" if r["dev_deps"] else ""
            md.append(f"- `{r['pkg']}` → {dep_s}{dev_s}")
    (out / "crate_map_baseline.md").write_text("\n".join(md) + "\n")


def load_config(out: Path):
    cfg_path = out / "crate_map.toml"
    if not cfg_path.exists() or tomllib is None:
        return {}
    return tomllib.loads(cfg_path.read_text())


def build_dot(meta, rows, cfg, name: str):
    by_pkg = {r["pkg"]: r for r in rows}
    render = cfg.get("render", {})
    omit = set(render.get("omit_edges_into", []))
    aggregates = render.get("aggregates", {})

    agg_of = {}   # pkg -> aggregate key
    for key, spec in aggregates.items():
        for pkg in by_pkg:
            if fnmatch.fnmatch(pkg, spec.get("pattern", "")):
                agg_of[pkg] = key

    clusters = cfg.get("clusters")
    if not clusters:  # fallback: cluster by top-level member dir
        clusters = {}
        for i, top in enumerate(sorted({r["dir"].split("/")[0] for r in rows})):
            members = [r["pkg"] for r in rows if r["dir"].split("/")[0] == top
                       and r["pkg"] not in agg_of]
            members += sorted({agg_of[r["pkg"]] for r in rows
                               if r["dir"].split("/")[0] == top and r["pkg"] in agg_of})
            clusters[top] = {"label": f"{top}/", "members": members,
                             "color": FALLBACK_COLORS[i % len(FALLBACK_COLORS)]}

    def metrics(node):
        if node in aggregates:
            rs = [r for r in rows if agg_of.get(r["pkg"]) == node]
        else:
            rs = [by_pkg[node]] if node in by_pkg else []
        prod = sum(r["prod_loc"] for r in rs)
        test = sum(r["src_testgated_loc"] + r["tests_dir_loc"] for r in rs)
        dead = sum(r["allow_dead"] for r in rs)
        return prod, test, dead

    t = meta["totals"]
    test_total = t["src_testgated_loc"] + t["tests_dir_loc"]
    omit_s = ", ".join(sorted(omit)) if omit else "none"
    lines = [
        "digraph crate_map {",
        "  rankdir=LR; compound=true; splines=true; ranksep=1.1; nodesep=0.35;",
        f'  fontname="Helvetica"; labelloc=t; fontsize=22; label="{name} crate map — @ {meta["head"]} ({meta["date"]})\\n'
        f'prod {t["prod_loc"]:,} LOC | test {test_total:,} LOC | {meta["members"]} crates | {t["tests"]:,} tests\\n'
        f'edges = prod deps; edges into [{omit_s}] omitted (near-universal fan-in)\\n'
        f'RED border = >={DEAD_HEAT_THRESHOLD} allow(dead_code) sites | ORANGE = empty crate";',
        '  node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=12];',
    ]
    placed = set()
    for key, spec in clusters.items():
        lines.append(f'  subgraph cluster_{key} {{')
        lines.append(f'    label="{spec.get("label", key)}"; style="rounded,filled"; '
                     f'fillcolor="{spec.get("color", "#EEEEEE")}"; fontsize=16;')
        for node in spec.get("members", []):
            prod, test, dead = metrics(node)
            disp = aggregates.get(node, {}).get("label", node)
            label = f"{disp}\\nprod {prod:,} | test {test:,}"
            extra = ""
            if prod + test == 0:
                label, extra = f"{disp}\\nEMPTY (0 LOC)", ' color="#E8710A" penwidth=3'
            elif dead >= DEAD_HEAT_THRESHOLD:
                extra = ' color="#C5221F" penwidth=3'
                label += f"\\nallow(dead_code) x{dead}"
            lines.append(f'    "{node}" [label="{label}" fillcolor="white"{extra}];')
            placed.add(node)
        lines.append("  }")
    for r in rows:  # anything unclustered still gets a node
        node = agg_of.get(r["pkg"], r["pkg"])
        if node not in placed:
            prod, test, dead = metrics(node)
            lines.append(f'  "{node}" [label="{node}\\nprod {prod:,} | test {test:,}" fillcolor="white"];')
            placed.add(node)

    seen = set()
    for r in rows:
        src = agg_of.get(r["pkg"], r["pkg"])
        for dep in r["deps"]:
            d = dep.replace(" (build)", "")
            d = agg_of.get(d, d)
            if d in omit or d == src or (src, d) in seen:
                continue
            seen.add((src, d))
            lines.append(f'  "{src}" -> "{d}";')
    lines.append("}")
    return "\n".join(lines), len(seen)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project-dir", default=None,
                    help="workspace root (default: git toplevel of cwd)")
    ap.add_argument("--out", default=None,
                    help="artifact dir (default: <project>/docs/research/assets)")
    ap.add_argument("--name", default=None,
                    help="map title prefix + file stem (default: root dir name)")
    ap.add_argument("--no-render", action="store_true", help="skip the dot -> svg render")
    args = ap.parse_args()

    if args.project_dir:
        root = Path(args.project_dir).resolve()
    else:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
        root = Path(r.stdout.strip()) if r.returncode == 0 else Path.cwd()
    out = Path(args.out).resolve() if args.out else root / "docs/research/assets"
    out.mkdir(parents=True, exist_ok=True)
    name = args.name or root.name

    meta, rows = collect(root)
    write_json_md(meta, rows, out)
    dot_src, n_edges = build_dot(meta, rows, load_config(out), name)
    dot_path = out / f"{name}_crate_map.dot"
    dot_path.write_text(dot_src)

    t = meta["totals"]
    print(f"[crate-map] @ {meta['head']}: {meta['members']} crates | "
          f"prod={t['prod_loc']} test={t['src_testgated_loc'] + t['tests_dir_loc']} | {n_edges} edges")
    print(f"[crate-map] wrote crate_map_baseline.json / .md / {dot_path.name} in {out}")

    if not args.no_render:
        if shutil.which("dot"):
            svg = out / f"{name}_crate_map.svg"
            subprocess.run(["dot", "-Tsvg", str(dot_path), "-o", str(svg)], check=True)
            print(f"[crate-map] rendered {svg}")
        else:
            print("[crate-map] graphviz `dot` not on PATH — skipped render (--no-render to silence)")


if __name__ == "__main__":
    main()
