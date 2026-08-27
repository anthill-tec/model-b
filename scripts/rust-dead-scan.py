#!/usr/bin/env python3
# Owner: Model B (roundhouse/model-b) — adopted by CR-MDB-022 §S1.
# Consuming skills: memory-templates (rust-orchestration.md); invoked by
#   scripts/rust-code-health.py.
#
"""rust-dead-scan.py — layered dead-code detection for Cargo workspaces.

Model-B toolset sibling of rust-crate-map.py (fully parameterized, nothing
project-hardcoded). Implements the detection stack a per-crate `dead_code`
lint cannot: rustc treats every plain-`pub` item as live (it cannot see across
crates), so dead public API survives a lint-clean workspace. Findings emit as
ledger fragments with STABLE IDs (DS-xxxxxxxxxx = hash of kind|crate|path|item)
so they can be cited across snapshots.

Modes (default: inventory pub-scan deps reconcile; lift-lint is opt-in — it builds):
  inventory  static: every #[allow(dead_code)] / #[expect(dead_code)] /
             #[deprecated] site — src-prod vs src-testgated vs tests-dir split,
             reason-clause extraction, class-bucket heuristic.
  pub-scan   static: exported plain-`pub` surface vs classified workspace-wide
             references (prod / test / doc; own-crate vs cross-crate).
             Tiers: dead-pub (0 prod refs, 0 test refs) · test-coat (only test
             refs — dead prod code kept alive by its tests) · internal-only
             (prod refs only in own crate → pub(crate)/unreachable_pub feed).
             Common/short names and cross-crate name collisions are SKIPPED
             (listed for manual lean-ctx verification, never auto-flagged).
  deps       cargo-machete (if installed) + declared-features-nobody-references audit.
  reconcile  every #[expect(dead_code)] mark must match an approved entry in
             the retention register (dead_code_register.toml); orphans both ways
             are findings. The steady-state honesty check.
  boundaries declarative boundary law from <out>/boundary_rules.toml: per-crate
             forbid/allow dep rules (DIRECT prod deps, v1), version-lockstep
             (version.workspace = true), and the hoisting rule (a dep declared
             with its own version by >= min_crates members -> hoist candidate).
             Turns prose invariants into machine-checked findings, every scan.
  lift-lint  (--lift-lint, BUILDS) scratch-copy the tree (git archive HEAD),
             strip the allow/expect(dead_code) attributes, cargo check
             --workspace --all-features, collect which sites the compiler
             itself declares dead. Precise but minutes-long.

Usage:
  rust-dead-scan.py [modes...] [--project-dir DIR] [--out DIR] [--lift-lint]
Outputs (in --out, default <project>/docs/research/assets):
  dead_scan_report.json / dead_scan_report.md
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

try:
    import tomllib
except ImportError:
    tomllib = None

CFG_TEST_RE = re.compile(r"^\s*#\[cfg\((test\)|any\(test)")
SUPPRESS_RE = re.compile(r"#\[(allow|expect)\(dead_code(?:\s*,\s*reason\s*=\s*\"((?:[^\"\\]|\\.)*)\")?\)?\]?")
DEPRECATED_RE = re.compile(r"#\[deprecated(?:\((?:since\s*=\s*\"[^\"]*\"\s*,?\s*)?note\s*=\s*\"((?:[^\"\\]|\\.)*)\")?")
ITEM_RE = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+|unsafe\s+|extern\s+\"[^\"]*\"\s+)*"
    r"(fn|struct|enum|trait|type|mod|static|const|union)\s+([A-Za-z_][A-Za-z0-9_]*)"
)
FIELD_RE = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?([a-z_][A-Za-z0-9_]*)\s*:")
VARIANT_RE = re.compile(r"^\s*([A-Z][A-Za-z0-9_]*)\s*[,({]?")
PUB_RE = re.compile(
    r"^\s*pub\s+(?:async\s+|unsafe\s+|extern\s+\"[^\"]*\"\s+)*"
    r"(fn|struct|enum|trait|type|static|const|union)\s+([A-Za-z_][A-Za-z0-9_]*)"
)
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
TEST_DIRS = ("tests", "benches", "examples")
COMMON_NAMES = {
    "name", "kind", "new", "default", "main", "build", "run", "start", "stop",
    "send", "recv", "read", "write", "open", "close", "push", "insert", "remove",
    "clear", "iter", "next", "from", "into", "with", "get", "set", "init",
    "value", "inner", "state", "config", "error", "event", "record", "schema",
}

CLASS_RULES = [
    ("observability", re.compile(r"observab|diagnostic|lineage|admin endpoint|telemetry", re.I)),
    ("doctest-carrier", re.compile(r"doctest|compile_fail", re.I)),
    ("test-fixture", re.compile(r"test fixture|test helper|by .*tests|for .*tests|in this module — bound", re.I)),
    ("scaffold-inflight", re.compile(r"in-flight|scaffold|upcoming|wiring|reserved", re.I)),
    ("parity-held", re.compile(r"parity|held for|retained for|back-compat|kept for", re.I)),
    ("wrapper-future", re.compile(r"future call|wrapper", re.I)),
]


def fid(kind, crate, path, item):
    return "DS-" + hashlib.sha1(f"{kind}|{crate}|{path}|{item}".encode()).hexdigest()[:10]


def git_head(root):
    try:
        return subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def workspace_members(root):
    text = (root / "Cargo.toml").read_text()
    m = re.search(r"members\s*=\s*\[(.*?)\]", text, re.S)
    members = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    out = []
    for mdir in members:
        mt = (root / mdir / "Cargo.toml").read_text()
        pm = re.search(r'^name\s*=\s*"([^"]+)"', mt, re.M)
        out.append((mdir, pm.group(1).replace("-", "_")))
    return out


def gated_lines(lines):
    """Line indices inside #[cfg(test)]/#[cfg(any(test,..))] gated blocks."""
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
    return gated


def context_of(rel_path, idx, gated):
    top = rel_path.split("/")[0]
    if top in TEST_DIRS:
        return "tests-dir"
    return "src-testgated" if gated[idx] else "src-prod"


def item_after(lines, idx):
    """Name of the item the attribute at lines[idx] decorates."""
    k = idx + 1
    while k < len(lines):
        s = lines[k].strip()
        if not s or s.startswith("//") or s.startswith("#["):
            k += 1
            continue
        m = ITEM_RE.match(lines[k])
        if m:
            return f"{m.group(1)} {m.group(2)}"
        m = FIELD_RE.match(lines[k])
        if m:
            return f"field {m.group(1)}"
        m = VARIANT_RE.match(lines[k])
        if m:
            return f"variant {m.group(1)}"
        return s[:40]
    return "?"


def classify_reason(reason):
    for name, rx in CLASS_RULES:
        if reason and rx.search(reason):
            return name
    return "unclassified"


def iter_rs(root, mdir):
    base = root / mdir
    for sub in ("src",) + TEST_DIRS:
        d = base / sub
        if d.exists():
            for f in sorted(d.rglob("*.rs")):
                yield f


def mode_inventory(root, members):
    findings = []
    for mdir, pkg in members:
        for f in iter_rs(root, mdir):
            rel = str(f.relative_to(root / mdir))
            lines = f.read_text(errors="replace").splitlines()
            gated = gated_lines(lines)
            for i, line in enumerate(lines):
                s = line.lstrip()
                if s.startswith("//"):
                    continue  # D3-scanfix: skip doc/line comments — attrs are code, not prose
                m = SUPPRESS_RE.match(s)  # real #[allow/expect(dead_code)] at code line-start only
                if m:
                    item = item_after(lines, i)
                    reason = m.group(2) or ""
                    findings.append({
                        "id": fid(m.group(1), pkg, rel, item),
                        "attr": m.group(1), "crate": pkg, "path": rel,
                        "line": i + 1, "item": item,
                        "context": context_of(rel, i, gated),
                        "reason": reason, "class": classify_reason(reason),
                    })
                d = DEPRECATED_RE.match(s)
                if d:
                    item = item_after(lines, i)
                    findings.append({
                        "id": fid("deprecated", pkg, rel, item),
                        "attr": "deprecated", "crate": pkg, "path": rel,
                        "line": i + 1, "item": item,
                        "context": context_of(rel, i, gated),
                        "reason": d.group(1) or "", "class": "deprecated",
                    })
    return findings


def mode_pub_scan(root, members):
    defs = {}      # name -> list of {crate,path,line,kind}
    skipped_common = 0
    for mdir, pkg in members:
        src = root / mdir / "src"
        if not src.exists():
            continue
        for f in sorted(src.rglob("*.rs")):
            rel = str(f.relative_to(root / mdir))
            lines = f.read_text(errors="replace").splitlines()
            gated = gated_lines(lines)
            for i, line in enumerate(lines):
                if gated[i]:
                    continue
                m = PUB_RE.match(line)
                if not m:
                    continue
                name = m.group(2)
                if name.lower() in COMMON_NAMES or len(name) < 4:
                    skipped_common += 1
                    continue
                defs.setdefault(name, []).append(
                    {"crate": pkg, "path": rel, "line": i + 1, "kind": m.group(1)})
    collisions = sorted(n for n, sites in defs.items() if len(sites) > 1)
    targets = {n for n, sites in defs.items() if len(sites) == 1}
    refs = {n: {"prod_own": 0, "prod_cross": 0, "test": 0, "doc": 0} for n in targets}

    for mdir, pkg in members:
        for f in iter_rs(root, mdir):
            rel = str(f.relative_to(root / mdir))
            lines = f.read_text(errors="replace").splitlines()
            gated = gated_lines(lines)
            in_tests_dir = rel.split("/")[0] in TEST_DIRS
            for i, line in enumerate(lines):
                s = line.strip()
                is_doc = s.startswith("//")
                for name in set(IDENT_RE.findall(line)) & targets:
                    d = defs[name][0]
                    if d["crate"] == pkg and d["path"] == rel and d["line"] == i + 1:
                        continue  # the definition itself
                    if is_doc:
                        refs[name]["doc"] += 1
                    elif in_tests_dir or gated[i]:
                        refs[name]["test"] += 1
                    elif pkg == d["crate"]:
                        refs[name]["prod_own"] += 1
                    else:
                        refs[name]["prod_cross"] += 1

    candidates = []
    for name in sorted(targets):
        r, d = refs[name], defs[name][0]
        prod = r["prod_own"] + r["prod_cross"]
        if prod == 0 and r["test"] == 0:
            tier = "dead-pub"
        elif prod == 0:
            tier = "test-coat"
        elif r["prod_cross"] == 0:
            tier = "internal-only"
        else:
            continue
        candidates.append({
            "id": fid("pub", d["crate"], d["path"], f"{d['kind']} {name}"),
            "tier": tier, "name": name, **d, **r,
        })
    order = {"dead-pub": 0, "test-coat": 1, "internal-only": 2}
    candidates.sort(key=lambda c: (order[c["tier"]], c["crate"], c["path"]))
    return {"candidates": candidates, "collisions": collisions,
            "skipped_common": skipped_common,
            "note": "regex-based v1 — collisions + common/short names need "
                    "lean-ctx callgraph verification at audit time; macro-generated "
                    "references are invisible here (verify before CULL)."}


def mode_deps(root, members):
    machete = {"available": shutil.which("cargo-machete") is not None, "unused": []}
    if machete["available"]:
        p = subprocess.run(["cargo-machete", str(root)], capture_output=True, text=True)
        crate = None
        for line in p.stdout.splitlines():
            m = re.match(r"^(\S+) -- .*Cargo.toml:$", line.strip())
            if m:
                crate = m.group(1)
                continue
            m = re.match(r"^\s+(\S+)$", line)
            if m and crate:
                machete["unused"].append({"crate": crate.replace("-", "_"), "dep": m.group(1)})

    feature_findings = []
    for mdir, pkg in members:
        ct = (root / mdir / "Cargo.toml").read_text()
        fm = re.search(r"^\[features\]\s*$(.*?)(?=^\[|\Z)", ct, re.S | re.M)
        if not fm:
            continue
        feats = re.findall(r"^([A-Za-z0-9_-]+)\s*=", fm.group(1), re.M)
        src_text = ""
        for f in iter_rs(root, mdir):
            src_text += f.read_text(errors="replace")
        for feat in feats:
            if feat == "default":
                continue
            in_code = f'feature = "{feat}"' in src_text
            forwarded = False
            for m2, p2 in members:
                if m2 == mdir:
                    continue
                other = (root / m2 / "Cargo.toml").read_text()
                if f'{pkg}/{feat}' in other.replace("-", "_") or \
                   (pkg in other.replace("-", "_") and f'"{feat}"' in other):
                    forwarded = True
                    break
            if not in_code and not forwarded:
                feature_findings.append({
                    "id": fid("feature", pkg, "Cargo.toml", feat),
                    "crate": pkg, "feature": feat,
                    "note": "declared but never referenced in code nor forwarded (verify: external consumers/CI may enable it)",
                })
    return {"machete": machete, "features": feature_findings}


def _member_deps_raw(root, mdir):
    """(name, section, is_workspace_ref) for every dep declared by a member."""
    text = (root / mdir / "Cargo.toml").read_text()
    out, section = [], None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("["):
            section = s
            continue
        m = re.match(r'^([A-Za-z0-9_-]+)\s*(=|\.workspace)', s)
        if not m or section is None or "dependencies" not in section:
            continue
        kind = ("dev" if "dev-dependencies" in section
                else "build" if "build-dependencies" in section else "prod")
        ws_ref = ".workspace" in m.group(2) or "workspace = true" in s or "workspace=true" in s
        out.append((m.group(1).replace("-", "_"), kind, ws_ref))
    return out


HOT_PATH_MARKER_DEFAULT = "JSON-BOUNDARY"


def _iter_scope_files(root, paths):
    """Expand a rule's `paths` (files or dirs, relative to root) to concrete .rs files."""
    for p in paths:
        full = root / p
        if full.is_dir():
            yield from (f.relative_to(root) for f in sorted(full.rglob("*.rs")))
        elif full.exists():
            yield Path(p)


def _prod_pattern_hits(root, rel_path, rxs, marker):
    """Yield (line, content) for PRODUCTION lines of rel_path matching any regex
    in `rxs`. Mirrors proto_native_invariants.rs::production_hits — drops
    (1) `//` comment lines, (2) lines inside a #[cfg(test)] block (via gated_lines),
    (3) lines carrying — or immediately preceded by — the `marker` boundary tag."""
    full = root / rel_path
    if not full.exists():
        return
    lines = full.read_text(errors="replace").splitlines()
    gated = gated_lines(lines)
    for i, line in enumerate(lines):
        if line.lstrip().startswith("//") or gated[i]:
            continue
        if marker in line or (i >= 1 and marker in lines[i - 1]):
            continue
        if any(rx.search(line) for rx in rxs):
            yield i + 1, line.strip()


def mode_hot_path(root, rules_path):
    """Source-forbid guard for production hot-paths — absorbs the
    proto_native_invariants.rs family (D3-proto-1) so the scanner owns the
    'no-JSON-in-hot-paths' invariant. `[[forbid]]` rules fail if any `patterns`
    (regex) appear on a production line of any file in `paths`; `[[require_present]]`
    rules fail if `pattern` is absent from `paths` (guards a mis-configured scan)."""
    if not rules_path.exists() or tomllib is None:
        return {"rules_file": str(rules_path), "exists": False,
                "violations": [], "sanity_failures": []}
    cfg = tomllib.loads(rules_path.read_text())
    marker = cfg.get("marker", HOT_PATH_MARKER_DEFAULT)
    violations, sanity_failures = [], []
    for rule in cfg.get("forbid", []):
        rid = rule.get("id", "forbid")
        rxs = [re.compile(p) for p in rule.get("patterns", [])]
        allow = set(rule.get("allow_paths", []))  # forbid in `paths` EXCEPT these (allowlist-inverse)
        for rel in _iter_scope_files(root, rule.get("paths", [])):
            if str(rel) in allow:
                continue
            for lineno, content in _prod_pattern_hits(root, rel, rxs, marker):
                violations.append({
                    "id": fid("hotpath", rid, str(rel), str(lineno)),
                    "rule": rid, "path": str(rel), "line": lineno,
                    "content": content, "source": rule.get("source", "")})
    for rule in cfg.get("require_present", []):
        rid = rule.get("id", "require")
        rx = re.compile(rule.get("pattern", ""))
        found = any((root / rel).exists() and rx.search((root / rel).read_text(errors="replace"))
                    for rel in _iter_scope_files(root, rule.get("paths", [])))
        if not found:
            sanity_failures.append({
                "id": fid("hotpath-sanity", rid, "", ""),
                "rule": rid, "pattern": rule.get("pattern", ""),
                "source": rule.get("source", "")})
    return {"rules_file": str(rules_path), "exists": True,
            "violations": violations, "sanity_failures": sanity_failures}


def mode_boundaries(root, members, rules_path):
    if not rules_path.exists() or tomllib is None:
        return {"rules_file": str(rules_path), "exists": False, "violations": [],
                "hoist_candidates": [], "lockstep_failures": []}
    cfg = tomllib.loads(rules_path.read_text())
    violations, lockstep_failures = [], []
    dep_declarers = {}   # external dep name -> set of members declaring own version

    require_ws_ver = cfg.get("version_lockstep", {}).get("require_workspace_version", False)
    hoist_cfg = cfg.get("hoisting", {})
    min_crates = hoist_cfg.get("min_crates", 3)
    exempt_pref = tuple(hoist_cfg.get("exempt_prefixes", []))

    for mdir, pkg in members:
        deps = _member_deps_raw(root, mdir)
        for name, kind, ws_ref in deps:
            if not ws_ref and not name.startswith(exempt_pref):
                dep_declarers.setdefault(name, set()).add(pkg)
        if require_ws_ver:
            text = (root / mdir / "Cargo.toml").read_text()
            if not re.search(r"^version(\.workspace\s*=\s*true|\s*=\s*\{\s*workspace\s*=\s*true)", text, re.M):
                lockstep_failures.append({
                    "id": fid("lockstep", pkg, "Cargo.toml", "version"),
                    "crate": pkg, "detail": "version is not workspace-inherited"})
        prod = {n for n, k, _ in deps if k == "prod"}
        for rule in cfg.get("rules", []):
            applies = (rule.get("crate") == pkg or
                       ("member_prefix" in rule and mdir.startswith(rule["member_prefix"])))
            if not applies:
                continue
            for bad in set(rule.get("forbid_deps", [])) & prod:
                violations.append({
                    "id": fid("boundary", pkg, "Cargo.toml", bad),
                    "crate": pkg, "dep": bad, "reason": rule.get("reason", "")})
            if "allow_deps_only" in rule:
                for extra in sorted(prod - set(rule["allow_deps_only"])):
                    violations.append({
                        "id": fid("boundary", pkg, "Cargo.toml", extra),
                        "crate": pkg, "dep": extra,
                        "reason": f"not in allow-list ({rule.get('reason', '')})"})
    hoist = [{"id": fid("hoist", "workspace", "Cargo.toml", name),
              "dep": name, "declarers": sorted(crates)}
             for name, crates in sorted(dep_declarers.items())
             if len(crates) >= min_crates]
    return {"rules_file": str(rules_path), "exists": True, "violations": violations,
            "hoist_candidates": hoist, "lockstep_failures": lockstep_failures}


def mode_reconcile(inventory, register_path):
    reg = {"entries": [], "path": str(register_path), "exists": register_path.exists()}
    if register_path.exists() and tomllib:
        data = tomllib.loads(register_path.read_text())
        reg["entries"] = data.get("keep_future", [])
    expects = [f for f in inventory if f["attr"] == "expect"]
    allows = [f for f in inventory if f["attr"] == "allow"]
    reg_keys = {(e.get("crate"), e.get("item")) for e in reg["entries"]}
    unregistered = [e for e in expects if (e["crate"], e["item"]) not in reg_keys]
    exp_keys = {(e["crate"], e["item"]) for e in expects}
    orphaned = [e for e in reg["entries"] if (e.get("crate"), e.get("item")) not in exp_keys]
    return {"register": reg, "expect_marks": len(expects),
            "bare_allows_pending": len(allows),
            "unregistered_marks": unregistered, "orphaned_register_entries": orphaned}


def mode_lift_lint(root):
    """git-archive HEAD to scratch, strip dead_code suppressions, cargo check."""
    scratch = Path(tempfile.mkdtemp(prefix="dead-scan-lift-"))
    subprocess.run(f"git -C {root} archive HEAD | tar -x -C {scratch}",
                   shell=True, check=True)
    strip_re = re.compile(r"^\s*#\[(allow|expect)\(dead_code[^\]]*\]\s*(//.*)?$")
    stripped = 0
    for f in scratch.rglob("*.rs"):
        lines = f.read_text(errors="replace").splitlines()
        kept = [l for l in lines if not strip_re.match(l)]
        if len(kept) != len(lines):
            stripped += len(lines) - len(kept)
            f.write_text("\n".join(kept) + "\n")
    p = subprocess.run(
        ["cargo", "check", "--workspace", "--all-features", "--message-format=json"],
        cwd=scratch, capture_output=True, text=True,
        env={**__import__("os").environ, "CARGO_BUILD_JOBS": "10"})
    fired = []
    for line in p.stdout.splitlines():
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("reason") != "compiler-message":
            continue
        code = (msg["message"].get("code") or {}).get("code", "")
        if code == "dead_code":
            for span in msg["message"].get("spans", []):
                if span.get("is_primary"):
                    fired.append({"path": span["file_name"],
                                  "line": span["line_start"],
                                  "text": msg["message"]["message"]})
    shutil.rmtree(scratch, ignore_errors=True)
    return {"stripped_attr_lines": stripped, "fired": fired,
            "check_ok": p.returncode == 0}


def emit(report, out):
    (out / "dead_scan_report.json").write_text(json.dumps(report, indent=1))
    md = [f"# Dead-code scan — @ `{report['meta']['head']}` ({report['meta']['date']})",
          "", f"Modes: {', '.join(report['meta']['modes'])}. Generated by "
          "`rust-dead-scan.py` — do not hand-edit. IDs are stable across snapshots.", ""]
    inv = report.get("inventory")
    if inv is not None:
        md.append("## Suppression & deprecation inventory")
        md.append("")
        by_crate = {}
        for f in inv:
            by_crate.setdefault(f["crate"], []).append(f)
        for crate in sorted(by_crate):
            md.append(f"### {crate}")
            for f in by_crate[crate]:
                reason = f' — reason: "{f["reason"]}"' if f["reason"] else ""
                md.append(f"- `{f['id']}` [{f['attr']}] `{f['path']}:{f['line']}` "
                          f"{f['item']} · {f['context']} · class **{f['class']}**{reason}")
            md.append("")
    ps = report.get("pub_scan")
    if ps:
        md.append("## Dead-pub candidates (classified reference scan)")
        md.append("")
        md.append(f"_{ps['note']}_ Skipped common/short names: {ps['skipped_common']}; "
                  f"name collisions (manual verify): {len(ps['collisions'])}.")
        md.append("")
        for c in ps["candidates"]:
            md.append(f"- `{c['id']}` **{c['tier']}** `{c['crate']}` "
                      f"`{c['path']}:{c['line']}` {c['kind']} `{c['name']}` — refs: "
                      f"prod-own {c['prod_own']}, prod-cross {c['prod_cross']}, "
                      f"test {c['test']}, doc {c['doc']}")
        md.append("")
    dp = report.get("deps")
    if dp:
        md.append("## Dependencies & features")
        md.append("")
        if not dp["machete"]["available"]:
            md.append("- cargo-machete NOT installed — dep scan skipped.")
        for u in dp["machete"]["unused"]:
            md.append(f"- `{fid('dep', u['crate'], 'Cargo.toml', u['dep'])}` unused dep "
                      f"`{u['dep']}` in `{u['crate']}`")
        for f in dp["features"]:
            md.append(f"- `{f['id']}` feature `{f['feature']}` in `{f['crate']}` — {f['note']}")
        md.append("")
    bd = report.get("boundaries")
    if bd:
        md.append("## Boundary conformance")
        md.append("")
        if not bd["exists"]:
            md.append(f"- no rules file at `{bd['rules_file']}` — skipped.")
        for v in bd["violations"]:
            md.append(f"- 🛑 `{v['id']}` VIOLATION: `{v['crate']}` depends on `{v['dep']}` — {v['reason']}")
        for f in bd["lockstep_failures"]:
            md.append(f"- ⚠ `{f['id']}` lockstep: `{f['crate']}` — {f['detail']}")
        for h in bd["hoist_candidates"]:
            md.append(f"- ⬆ `{h['id']}` hoist candidate `{h['dep']}` — declared by "
                      f"{len(h['declarers'])} crates: {', '.join(h['declarers'])}")
        if bd["exists"] and not (bd["violations"] or bd["lockstep_failures"] or bd["hoist_candidates"]):
            md.append("- all rules pass.")
        md.append("")
    rc = report.get("reconcile")
    if rc:
        md.append("## Retention-register reconciliation")
        md.append("")
        md.append(f"- expect(dead_code) marks: {rc['expect_marks']} · bare allows pending "
                  f"conversion: {rc['bare_allows_pending']} · register: "
                  f"{'present' if rc['register']['exists'] else 'MISSING'} "
                  f"({len(rc['register']['entries'])} entries)")
        for e in rc["unregistered_marks"]:
            md.append(f"- ⚠ UNREGISTERED mark `{e['id']}` `{e['crate']}` `{e['path']}:{e['line']}` {e['item']}")
        for e in rc["orphaned_register_entries"]:
            md.append(f"- ⚠ ORPHANED register entry: {e}")
        md.append("")
    ll = report.get("lift_lint")
    if ll:
        md.append("## Lift-and-lint (compiler verdicts)")
        md.append("")
        md.append(f"- stripped {ll['stripped_attr_lines']} suppression lines; "
                  f"check {'OK' if ll['check_ok'] else 'FAILED'}; "
                  f"{len(ll['fired'])} dead_code warnings fired")
        for w in ll["fired"]:
            md.append(f"- 🔥 `{w['path']}:{w['line']}` — {w['text']}")
        md.append("")
    (out / "dead_scan_report.md").write_text("\n".join(md) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("modes", nargs="*",
                    default=["inventory", "pub-scan", "deps", "reconcile", "boundaries", "hot-path"],
                    help="subset of: inventory pub-scan deps reconcile boundaries hot-path lift-lint")
    ap.add_argument("--project-dir", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--lift-lint", action="store_true",
                    help="add the lift-lint mode (BUILDS the workspace — minutes)")
    args = ap.parse_args()

    if args.project_dir:
        root = Path(args.project_dir).resolve()
    else:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
        root = Path(r.stdout.strip()) if r.returncode == 0 else Path.cwd()
    out = Path(args.out).resolve() if args.out else root / "docs/research/assets"
    out.mkdir(parents=True, exist_ok=True)

    modes = list(args.modes)
    if args.lift_lint and "lift-lint" not in modes:
        modes.append("lift-lint")
    members = workspace_members(root)
    report = {"meta": {"head": git_head(root), "date": date.today().isoformat(),
                       "modes": modes, "members": len(members)}}

    inventory = None
    if "inventory" in modes or "reconcile" in modes:
        inventory = mode_inventory(root, members)
    if "inventory" in modes:
        report["inventory"] = inventory
    if "pub-scan" in modes:
        report["pub_scan"] = mode_pub_scan(root, members)
    if "deps" in modes:
        report["deps"] = mode_deps(root, members)
    if "reconcile" in modes:
        report["reconcile"] = mode_reconcile(inventory, out / "dead_code_register.toml")
    if "boundaries" in modes:
        report["boundaries"] = mode_boundaries(root, members, out / "boundary_rules.toml")
    if "hot-path" in modes:
        report["hot_path"] = mode_hot_path(root, out / "hot_path_rules.toml")
    if "lift-lint" in modes:
        report["lift_lint"] = mode_lift_lint(root)

    emit(report, out)
    counts = []
    if inventory is not None:
        counts.append(f"inventory={len(inventory)}")
    if "pub_scan" in report:
        counts.append(f"pub-candidates={len(report['pub_scan']['candidates'])}")
    if "deps" in report:
        counts.append(f"unused-deps={len(report['deps']['machete']['unused'])} "
                      f"features={len(report['deps']['features'])}")
    if "boundaries" in report:
        b = report["boundaries"]
        counts.append(f"boundary-violations={len(b['violations'])} "
                      f"hoist={len(b['hoist_candidates'])} lockstep={len(b['lockstep_failures'])}")
    if "hot_path" in report:
        hp = report["hot_path"]
        counts.append(f"hot-path-violations={len(hp['violations'])} "
                      f"sanity-fail={len(hp['sanity_failures'])}")
    print(f"[dead-scan] @ {report['meta']['head']}: {' | '.join(counts)}")
    print(f"[dead-scan] wrote dead_scan_report.json / .md in {out}")


if __name__ == "__main__":
    main()
