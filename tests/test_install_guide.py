"""Gates for the install guide as the single source of install text:
``docs/install-guide.md``, the repo ``README.md`` pointing at it, the
git-workflow skill's release steps, and the Pi package README's source.

Every term the guide must cover is DERIVED from the code, never hand-copied,
so a rename in the code fails the gate instead of letting it pass silently:

- install outcomes: every string literal passed to ``_emit_install_envelope``
  in ``modelb_axi/cli.py`` (found by AST);
- flags: checked present in ``modelb_axi.cli._build_parser()``;
- stacks: ``modelb_axi.scaffold.KNOWN_STACKS``;
- prerequisites / warnings: ``modelb_axi.requirements.REQUIREMENTS``;
- toolchain installers: ``modelb_axi.requirements.STACK_TOOLCHAINS``;
- pre-flight line prefixes: parsed from a real sandboxed installer run's
  stderr (``<prefix>: k=v ...`` lines);
- verdicts: ``capabilities.DETECTED/ABSENT/UNKNOWN`` + ``toolchains.INSTALLED``;
- the permission-policy directory: ``permission_policy.POLICY_RELPATH``.

Design (proposed at RED, approved by the orchestrator):

(A) The guide carries one exact ``## `` heading per install topic
    (:data:`SECTIONS`); each topic's terms are checked inside its own section
    (heading to the next ``## ``). A term counts only inside an inline code
    span or a fenced block, as a whole token.
(C) Marked regions: ``<!-- install-guide:begin <name> -->`` ...
    ``<!-- install-guide:end <name> -->`` on their own lines, kebab-case
    names, unique, non-empty, never nested; every install topic sits wholly
    inside a region; the ``## Marked regions`` section (which documents the
    convention, showing both markers in code spans) sits outside every region.
(D) No internal vocabulary anywhere in the guide: no ``§``, no CR ids, no
    ``D<n>``/``PRD``/``DN-`` references, and none of :data:`BLOCKED_WORDS`
    (case-sensitive, whole word).
(E) README: <= 20 non-blank lines, a ``# `` title then a description
    paragraph, a markdown link to ``docs/install-guide.md``, and no line or
    inline code span beginning with an installer command.
(F) git-workflow ``## Releases`` names both release steps (copying the
    guide's marked regions verbatim into the release notes; a documentation
    review); CR-MDB-029 ``### §S1`` names the guide's marked regions as the
    Pi package README's source.

Orchestrator rulings (2026-09-24, on the RED design):

- Warnings: AT-LEAST-ONE — for each requirement row, one line of the
  warnings section names the row's id (in a code span) AND at least one of
  its asset families. Whether the prose states consequences well is the
  release documentation review's judgement, not a gate's.
- Install offers: ``pi install``, ``--yes``, and ANY ONE toolchain-installer
  term (a ``STACK_TOOLCHAINS`` probe with an installer, by name or command)
  — no per-toolchain enumeration.
- Blocklist approved as listed; derived required terms were checked for
  collisions with it (none collide, so no code-span exemption exists).

Stdlib only.
"""

import argparse
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GUIDE = REPO_ROOT / "docs" / "install-guide.md"
README = REPO_ROOT / "README.md"
GIT_WORKFLOW_SKILL = REPO_ROOT / "skills-src" / "git-workflow" / "SKILL.md"
CR_029 = REPO_ROOT / "docs" / "changes" / "CR-MDB-029-pi-package.md"
CLI_SOURCE = REPO_ROOT / "modelb_axi" / "cli.py"
GUIDE_LINK_TARGET = "docs/install-guide.md"

# (A) — one exact heading per install topic, in guide order.
PREREQUISITES = "Prerequisites"
STACKS = "Choosing stacks"
PREFLIGHT = "Reading the pre-flight"
WARNINGS = "Warnings: what stops working"
OFFERS = "Install offers"
MISSING = "Missing capabilities"
OUTCOMES = "Install outcomes"
REAL_HOME = "Installing into your home directory"
WIDENING = "Adding stacks later"
TRUST = "Project trust"
MARKED = "Marked regions"
INSTALL_TOPICS = (
    PREREQUISITES, STACKS, PREFLIGHT, WARNINGS, OFFERS, MISSING, OUTCOMES,
    REAL_HOME, WIDENING, TRUST,
)
SECTIONS = INSTALL_TOPICS + (MARKED,)

# (C)
MARKER_PREFIX = "<!-- install-guide:"
_NAME = r"[a-z0-9]+(?:-[a-z0-9]+)*"
BEGIN_RE = re.compile(rf"^<!-- install-guide:begin ({_NAME}) -->$")
END_RE = re.compile(rf"^<!-- install-guide:end ({_NAME}) -->$")

# (D)
BLOCKED_WORDS = (
    "RED", "GREEN", "VERIFY", "FIX", "Mainline", "vidushi", "MDB",
    "orchestrator", "wave", "cycle", "gap-analysis", "tier-1", "tier-2",
    "tier-3", "tier 1", "tier 2", "tier 3", "REQUIREMENTS", "asset_families",
    "user ruling", "dog-food",
)
BLOCKED_PATTERNS = (
    ("section sign", re.compile("§")),
    ("CR id", re.compile(r"\bCR-[A-Z]{2,5}-\d{3}\b")),
    ("decision id", re.compile(r"(?<![\w-])D\d{1,2}(?![\w-])")),
    ("PRD reference", re.compile(r"(?<![\w-])PRD(?![\w-])")),
    ("design-note reference", re.compile(r"(?<![\w-])DN-")),
)

# (E)
README_MAX_NONBLANK_LINES = 20
INSTALLER_COMMAND_PREFIXES = ("modelb-axi", "uv tool install", "pip install", "pi install")

# (F)
RELEASE_STEP_PHRASES = (
    "install guide", "marked region", "verbatim", "release notes", "documentation review",
)
CR_029_S1_TERMS = ("install-guide.md", "marked region", "README")


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")


def _fence_mask(lines: list[str]) -> list[bool]:
    """True for every line that is inside (or delimits) a fenced block."""
    mask, inside, fence = [], False, None
    for line in lines:
        match = _FENCE_RE.match(line)
        if match and (not inside or match.group(1) == fence):
            mask.append(True)
            inside, fence = (not inside), (match.group(1) if not inside else None)
            continue
        mask.append(inside)
    return mask


def code_texts(text: str) -> list[str]:
    """Every inline code span (outside fences) and every fenced-block line."""
    lines = text.splitlines()
    out = []
    for line, fenced in zip(lines, _fence_mask(lines), strict=True):
        if fenced:
            if not _FENCE_RE.match(line):
                out.append(line)
            continue
        out.extend(m.group(2).strip() for m in _INLINE_CODE_RE.finditer(line))
    return out


def _token_re(term: str) -> re.Pattern:
    return re.compile(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])")


def has_code_token(text: str, term: str) -> bool:
    """``term`` appears as a whole token inside a code span or fenced block."""
    pattern = _token_re(term)
    return any(pattern.search(code) for code in code_texts(text))


def sections(text: str, level: str = "## ") -> dict[str, str]:
    """Heading text -> section text (heading line through the line before
    the next heading of the same level). Headings inside fences ignored."""
    lines = text.splitlines()
    mask = _fence_mask(lines)
    starts = [i for i, (ln, f) in enumerate(zip(lines, mask, strict=True))
              if not f and ln.startswith(level) and not ln.startswith(level.strip() + "#")]
    out: dict[str, str] = {}
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        out.setdefault(lines[start][len(level):].strip(), "\n".join(lines[start:end]))
    return out


def heading_counts(text: str) -> dict[str, int]:
    lines = text.splitlines()
    counts: dict[str, int] = {}
    for line, fenced in zip(lines, _fence_mask(lines), strict=True):
        if not fenced and line.startswith("## "):
            key = line[3:].strip()
            counts[key] = counts.get(key, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Derived vocabulary (the gate follows the code)
# ---------------------------------------------------------------------------

def _requirements() -> list[dict]:
    from modelb_axi.requirements import REQUIREMENTS
    return list(REQUIREMENTS)


def _parser_flags() -> set[str]:
    from modelb_axi.cli import _build_parser
    parser = _build_parser()
    flags = set()
    for action in parser._actions:  # stdlib argparse: the declared actions
        if isinstance(action, argparse._SubParsersAction):
            continue
        flags.update(action.option_strings)
    return flags


def parser_flag(flag: str) -> str:
    """``flag`` if the installer's parser declares it, else AssertionError."""
    flags = _parser_flags()
    if flag not in flags:
        raise AssertionError(
            f"the installer parser no longer declares {flag}; the guide gate "
            f"must follow the code (declared: {sorted(flags)})"
        )
    return flag


def install_outcomes() -> list[str]:
    """Every outcome literal ``cli.py`` passes to ``_emit_install_envelope``."""
    tree = ast.parse(CLI_SOURCE.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_emit_install_envelope" and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and node.args[0].value not in found):
            found.append(node.args[0].value)
    return found


def known_stacks() -> list[str]:
    from modelb_axi.scaffold import KNOWN_STACKS
    return list(KNOWN_STACKS)


def verdicts() -> list[str]:
    from modelb_axi.capabilities import ABSENT, DETECTED, UNKNOWN
    from modelb_axi.toolchains import INSTALLED
    return [DETECTED, ABSENT, UNKNOWN, INSTALLED]


def toolchain_installer_terms() -> list[str]:
    """Probe names and installer commands of every toolchain probe that has
    an installer the pre-flight can offer."""
    from modelb_axi.requirements import STACK_TOOLCHAINS, install_display
    terms = []
    for probes in STACK_TOOLCHAINS.values():
        for probe in probes:
            if probe.get("install"):
                for term in (probe["name"], install_display(probe["install"])):
                    if term not in terms:
                        terms.append(term)
    return terms


def policy_dir_name() -> str:
    from modelb_axi.permission_policy import POLICY_RELPATH
    return POLICY_RELPATH.parts[1]


_GROUP_LINE_RE = re.compile(r"^([a-z][a-z0-9-]*(?: [a-z0-9-]+)?): (?:\S+=\S+\s*)+$")


@lru_cache(maxsize=1)
def preflight_prefixes() -> tuple[str, ...]:
    """The pre-flight's group-line prefixes, read from a REAL installer run
    in a sandbox (fake ``uv``/``sandesh``, sandboxed HOME and Pi agent dir,
    ``--stacks python``, no ``--target-root`` so nothing deploys). A stack
    line is normalised to ``stack <name>``."""
    root = Path(tempfile.mkdtemp(prefix="modelb-install-guide-"))
    try:
        bin_dir, home, agent = root / "bin", root / "home", root / "agent"
        for d in (bin_dir, home, agent):
            d.mkdir()
        for name, body in (("uv", "#!/bin/sh\nexit 0\n"), ("sandesh", "#!/bin/sh\nexit 0\n")):
            exe = bin_dir / name
            exe.write_text(body, encoding="utf-8")
            exe.chmod(0o755)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT) + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        env.update(PATH=str(bin_dir), HOME=str(home), PI_CODING_AGENT_DIR=str(agent))
        env.pop("MODELB_TARGET_ROOT", None)
        result = subprocess.run(
            [sys.executable, "-m", "modelb_axi", "--yes", "--harnesses", "pi",
             "--modelb-home", str(root / "modelb-home"), "--stacks", "python",
             "--allow-missing-capabilities"],
            capture_output=True, text=True, timeout=60,
            stdin=subprocess.DEVNULL, env=env,
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)
    stacks = set(known_stacks())
    prefixes: list[str] = []
    for line in result.stderr.splitlines():
        match = _GROUP_LINE_RE.match(line)
        if not match:
            continue
        prefix = match.group(1)
        if prefix.startswith("stack ") and prefix[len("stack "):] in stacks:
            prefix = "stack <name>"
        if prefix not in prefixes:
            prefixes.append(prefix)
    if not prefixes:
        raise AssertionError(
            "no pre-flight group line could be derived from a sandboxed "
            f"installer run; exit={result.returncode} stderr={result.stderr!r}"
        )
    return tuple(prefixes)


def _prefix_present(section: str, prefix: str) -> bool:
    if prefix == "stack <name>":
        pattern = re.compile(r"(?<![\w-])stack <[^<>\s]+>:")
        return any(pattern.search(code) for code in code_texts(section))
    return has_code_token(section, prefix + ":")


# ---------------------------------------------------------------------------
# Checkers — each returns the list of violations (empty = conforming)
# ---------------------------------------------------------------------------

def check_headings(text: str) -> list[str]:
    counts = heading_counts(text)
    return [f"heading '## {h}' appears {counts.get(h, 0)} times (want 1)"
            for h in SECTIONS if counts.get(h, 0) != 1]


def _section(text: str, heading: str) -> str:
    return sections(text).get(heading, "")


def _missing_tokens(section: str, terms, where: str) -> list[str]:
    return [f"{where}: missing `{t}`" for t in terms if not has_code_token(section, t)]


def check_prerequisites(text: str) -> list[str]:
    sec = _section(text, PREREQUISITES)
    codes = code_texts(sec)
    out = []
    rows = _requirements()
    for row in rows:
        if row["scope"] != "always":
            continue
        named = (has_code_token(sec, row["id"])
                 or any(row["provider"] in c or row["remediation"] in c for c in codes))
        if not named:
            out.append(f"{PREREQUISITES}: requirement {row['id']!r} not named "
                       "(id, provider or remediation, in code)")
    pi = re.search(r"(?<![\w-])Pi(?![\w-])", sec)
    for row in rows:
        if row["tier"] != 1:
            continue
        at = sec.find(row["provider"])
        if pi is None or at == -1 or at < pi.start():
            out.append(f"{PREREQUISITES}: Pi must be introduced before {row['provider']}")
    uv = next(r for r in rows if r["id"] == "uv")
    remediations = {r["remediation"] for r in rows}
    uv_at = sec.find(uv["remediation"])
    installer_at = -1
    for match in re.finditer(r"uv tool install[^\n`]*", sec):
        if match.group(0).strip() not in remediations:
            installer_at = match.start()
            break
    if uv_at == -1 or installer_at == -1 or uv_at > installer_at:
        out.append(f"{PREREQUISITES}: uv ({uv['remediation']!r}) must precede "
                   "the `uv tool install` that installs the installer")
    return out


def check_stacks(text: str) -> list[str]:
    sec = _section(text, STACKS)
    out = _missing_tokens(sec, [parser_flag("--stacks"), *known_stacks()], STACKS)
    if not any("crucible-report-" in c for c in code_texts(sec)):
        out.append(f"{STACKS}: must name the `crucible-report-` bundles a stack installs")
    if "does not install" not in sec.lower():
        out.append(f"{STACKS}: must say what a stack 'does not install'")
    return out


def check_preflight(text: str) -> list[str]:
    sec = _section(text, PREFLIGHT)
    out = [f"{PREFLIGHT}: missing pre-flight line `{p}:`"
           for p in preflight_prefixes() if not _prefix_present(sec, p)]
    return out + _missing_tokens(sec, verdicts(), PREFLIGHT)


def check_warnings(text: str) -> list[str]:
    sec = _section(text, WARNINGS)
    out = []
    lines = sec.splitlines()
    for row in _requirements():
        families = [f.lower() for f in row["asset_families"]]
        if not any(has_code_token(line, row["id"]) and any(f in line.lower() for f in families)
                   for line in lines):
            out.append(f"{WARNINGS}: no line names `{row['id']}` with one of "
                       f"{list(row['asset_families'])}")
    return out


def check_offers(text: str) -> list[str]:
    sec = _section(text, OFFERS)
    out = _missing_tokens(sec, ["pi install", parser_flag("--yes")], OFFERS)
    codes = code_texts(sec)
    if not any(has_code_token(sec, t) or any(t in c for c in codes)
               for t in toolchain_installer_terms()):
        out.append(f"{OFFERS}: must show that toolchain installers are offered")
    return out


def check_missing_capabilities(text: str) -> list[str]:
    sec = _section(text, MISSING)
    required = [r["id"] for r in _requirements() if r["tier"] == 1 and r["policy"] == "required"]
    return _missing_tokens(sec, [parser_flag("--allow-missing-capabilities"), *required], MISSING)


def check_outcomes(text: str) -> list[str]:
    return _missing_tokens(_section(text, OUTCOMES), install_outcomes(), OUTCOMES)


def check_real_home(text: str) -> list[str]:
    sec = _section(text, REAL_HOME)
    flag = parser_flag("--target-root")
    pattern = re.compile(r"(?<![\w-])" + re.escape(flag) + r" ~(?![\w/.-])")
    if any(pattern.search(c) for c in code_texts(sec)):
        return []
    return [f"{REAL_HOME}: missing `{flag} ~`"]


def check_widening(text: str) -> list[str]:
    return _missing_tokens(_section(text, WIDENING),
                           [parser_flag("--stacks"), parser_flag("--reinstall")], WIDENING)


def check_trust(text: str) -> list[str]:
    return _missing_tokens(_section(text, TRUST),
                           ["/trust", ".pi/extensions", policy_dir_name()], TRUST)


TOPIC_CHECKERS = {
    PREREQUISITES: check_prerequisites,
    STACKS: check_stacks,
    PREFLIGHT: check_preflight,
    WARNINGS: check_warnings,
    OFFERS: check_offers,
    MISSING: check_missing_capabilities,
    OUTCOMES: check_outcomes,
    REAL_HOME: check_real_home,
    WIDENING: check_widening,
    TRUST: check_trust,
}


def check_marked_regions(text: str) -> list[str]:
    lines = text.splitlines()
    mask = _fence_mask(lines)
    out: list[str] = []
    regions: list[tuple[str, int, int]] = []
    open_region: tuple[str, int] | None = None
    for i, (line, fenced) in enumerate(zip(lines, mask, strict=True)):
        stripped = line.strip()
        if fenced or not stripped.startswith(MARKER_PREFIX):
            continue
        begin, end = BEGIN_RE.match(stripped), END_RE.match(stripped)
        if begin:
            if open_region is not None:
                out.append(f"line {i + 1}: region {begin.group(1)!r} nested in {open_region[0]!r}")
            else:
                open_region = (begin.group(1), i)
        elif end:
            if open_region is None or open_region[0] != end.group(1):
                out.append(f"line {i + 1}: end {end.group(1)!r} has no matching begin")
            else:
                regions.append((open_region[0], open_region[1], i))
                open_region = None
        else:
            out.append(f"line {i + 1}: malformed marker {stripped!r}")
    if open_region is not None:
        out.append(f"region {open_region[0]!r} is never ended")
    if not regions:
        out.append("no marked region")
    names = [r[0] for r in regions]
    out.extend(f"region name {n!r} is not unique" for n in sorted(set(names)) if names.count(n) > 1)
    for name, start, stop in regions:
        if not any(ln.strip() for ln in lines[start + 1:stop]):
            out.append(f"region {name!r} is empty")

    def inside(first: int, last: int) -> bool:
        return any(start < first and last < stop for _n, start, stop in regions)

    heads = [i for i, (ln, f) in enumerate(zip(lines, mask, strict=True)) if not f and ln.startswith("## ")]
    for n, head in enumerate(heads):
        title = lines[head][3:].strip()
        nxt = heads[n + 1] if n + 1 < len(heads) else len(lines)
        body = [j for j in range(head, nxt)
                if lines[j].strip() and not lines[j].strip().startswith(MARKER_PREFIX)]
        last = body[-1] if body else head
        if title in INSTALL_TOPICS and not inside(head, last):
            out.append(f"section '{title}' is not wholly inside a marked region")
        if title == MARKED and any(start < head < stop for _n, start, stop in regions):
            out.append(f"section '{MARKED}' must sit outside every marked region")
    marked = _section(text, MARKED)
    for kind in ("begin", "end"):
        if not any(f"{MARKER_PREFIX}{kind}" in c for c in code_texts(marked)):
            out.append(f"section '{MARKED}' must show the {kind} marker in code")
    return out


def check_vocabulary(text: str) -> list[str]:
    out = [f"{label}: {m.group(0)!r}" for label, pattern in BLOCKED_PATTERNS
           for m in pattern.finditer(text)]
    for word in BLOCKED_WORDS:
        if _token_re(word).search(text):
            out.append(f"internal vocabulary: {word!r}")
    return out


def check_readme(text: str) -> list[str]:
    out = []
    nonblank = [ln for ln in text.splitlines() if ln.strip()]
    if len(nonblank) > README_MAX_NONBLANK_LINES:
        out.append(f"{len(nonblank)} non-blank lines (max {README_MAX_NONBLANK_LINES})")
    if not nonblank or not nonblank[0].startswith("# "):
        out.append("first line must be a '# ' title")
    elif len(nonblank) < 2 or nonblank[1].lstrip().startswith(("#", "```", "~~~", "<!--", "-", "*", "|")):
        out.append("the title must be followed by a description paragraph")
    if not re.search(r"\]\((?:\./)?" + re.escape(GUIDE_LINK_TARGET) + r"(?:#[^)]*)?\)", text):
        out.append(f"no markdown link to {GUIDE_LINK_TARGET}")
    candidates = [ln.strip() for ln in text.splitlines()] + code_texts(text)
    for cand in candidates:
        cand = cand.lstrip("$> ").strip()
        if cand.startswith(INSTALLER_COMMAND_PREFIXES):
            out.append(f"installer command line: {cand!r}")
    return out


def check_release_steps(text: str) -> list[str]:
    sec = next((body for head, body in sections(text).items()
                if head.startswith("Releases")), "").lower()
    if not sec:
        return ["no '## Releases' section"]
    return [f"## Releases: missing {p!r}" for p in RELEASE_STEP_PHRASES if p not in sec]


def check_cr029_s1(text: str) -> list[str]:
    sec = next((body for head, body in sections(text, "### ").items()
                if head.startswith("§S1")), "")
    if not sec:
        return ["no '### §S1' section"]
    lowered = sec.lower()
    return [f"§S1: missing {t!r}" for t in CR_029_S1_TERMS
            if (t.lower() if t != "README" else t) not in (lowered if t != "README" else sec)]


# ---------------------------------------------------------------------------
# A conforming synthetic guide, built from the derived vocabulary — the proof
# that a correct guide CAN pass every checker.
# ---------------------------------------------------------------------------

def conforming_guide() -> str:
    rows = _requirements()
    uv = next(r for r in rows if r["id"] == "uv")
    tier1 = [r for r in rows if r["tier"] == 1]
    always_rest = [r for r in rows if r["scope"] == "always" and r["tier"] != 1 and r["id"] != "uv"]
    prereq = ["Install Pi first; its packages come next."]
    prereq += [f"- `{r['remediation']}`" for r in tier1]
    prereq += [f"- `{uv['remediation']}`", "- `uv tool install git+https://example.invalid/model-b`"]
    prereq += [f"- `{r['id']}`: `{r['remediation']}`" for r in always_rest]
    stack_lines = ["Choose with `--stacks " + ",".join(known_stacks()) + "`.",
                   " ".join(f"`{s}`" for s in known_stacks()),
                   "A stack installs the `crucible-report-<stack>` bundle; it does not install a toolchain."]
    preflight = ["```"]
    for p in preflight_prefixes():
        preflight.append(("stack <name>:" if p == "stack <name>" else f"{p}:") + " x=y")
    preflight.append("```")
    preflight.append(" ".join(f"`{v}`" for v in verdicts()))
    warnings = [f"- `{r['id']}`: the {r['asset_families'][0]} will not work" for r in rows]
    offers = ["`pi install` and `" + toolchain_installer_terms()[0] + "` are offered; `--yes` never confirms them."]
    required = [r["id"] for r in tier1 if r["policy"] == "required"]
    missing = ["`--allow-missing-capabilities` continues without " + ", ".join(f"`{i}`" for i in required)]
    outcomes = [f"- `{o}`" for o in install_outcomes()]
    bodies = {
        PREREQUISITES: prereq, STACKS: stack_lines, PREFLIGHT: preflight,
        WARNINGS: warnings, OFFERS: offers, MISSING: missing, OUTCOMES: outcomes,
        REAL_HOME: ["Pass `--target-root ~` explicitly."],
        WIDENING: ["Re-run with `--reinstall --stacks python,rust`."],
        TRUST: [f"`.pi/extensions` and `{policy_dir_name()}` load once you run `/trust`."],
    }
    out = ["# Installing", "", "<!-- install-guide:begin install -->", ""]
    for heading in INSTALL_TOPICS:
        out += [f"## {heading}", "", *bodies[heading], ""]
    out += ["<!-- install-guide:end install -->", "", f"## {MARKED}", "",
            "Regions open with `<!-- install-guide:begin <name> -->` and close with "
            "`<!-- install-guide:end <name> -->`.", ""]
    return "\n".join(out)


CONFORMING_README = (
    "# Model B\n\n"
    "Skills, agent definitions and hooks for an agent-harness workflow.\n\n"
    "To install, follow the [install guide](docs/install-guide.md).\n"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


# ---------------------------------------------------------------------------
# Gates over the real files
# ---------------------------------------------------------------------------

class InstallGuideTopicsTest(unittest.TestCase):
    """The guide covers every install topic, each by a gate over its heading
    and the derived terms it must name."""

    def setUp(self):
        self.assertTrue(GUIDE.is_file(), f"{GUIDE.relative_to(REPO_ROOT)} must exist")
        self.text = _read(GUIDE)

    def test_guide_carries_each_topic_heading_exactly_once(self):
        self.assertEqual(check_headings(self.text), [])

    def test_prerequisites_name_every_always_requirement_in_dependency_order(self):
        self.assertEqual(check_prerequisites(self.text), [])

    def test_stack_selector_names_flag_every_stack_and_what_a_stack_installs(self):
        self.assertEqual(check_stacks(self.text), [])

    def test_preflight_section_names_every_line_prefix_and_verdict(self):
        self.assertEqual(check_preflight(self.text), [])

    def test_warnings_section_states_what_stops_working_for_every_requirement(self):
        self.assertEqual(check_warnings(self.text), [])

    def test_install_offers_name_pi_install_toolchain_installers_and_yes(self):
        self.assertEqual(check_offers(self.text), [])

    def test_missing_capabilities_section_names_the_override_flag(self):
        self.assertEqual(check_missing_capabilities(self.text), [])

    def test_outcomes_section_names_every_install_outcome_the_cli_emits(self):
        self.assertEqual(check_outcomes(self.text), [])

    def test_real_home_deploy_takes_explicit_target_root_tilde(self):
        self.assertEqual(check_real_home(self.text), [])

    def test_widening_stacks_later_names_reinstall_and_stacks(self):
        self.assertEqual(check_widening(self.text), [])

    def test_project_trust_section_names_what_it_gates_and_slash_trust(self):
        self.assertEqual(check_trust(self.text), [])


class InstallGuideMarkedRegionsTest(unittest.TestCase):

    def test_install_topics_sit_in_well_formed_regions_and_convention_is_documented(self):
        self.assertTrue(GUIDE.is_file(), f"{GUIDE.relative_to(REPO_ROOT)} must exist")
        self.assertEqual(check_marked_regions(_read(GUIDE)), [])


class InstallGuideVocabularyTest(unittest.TestCase):

    def test_guide_carries_no_section_refs_cr_ids_or_internal_vocabulary(self):
        self.assertTrue(GUIDE.is_file(), f"{GUIDE.relative_to(REPO_ROOT)} must exist")
        text = _read(GUIDE)
        self.assertTrue(text.strip(), "the guide must not be empty")
        self.assertEqual(check_vocabulary(text), [])


class RepoReadmeTest(unittest.TestCase):

    def test_readme_describes_project_and_points_at_guide_without_installer_commands(self):
        self.assertTrue(README.is_file(), "README.md must exist at the repo root")
        self.assertEqual(check_readme(_read(README)), [])


class ReleaseDocsTest(unittest.TestCase):

    def test_git_workflow_releases_names_guide_copy_and_documentation_review(self):
        self.assertEqual(check_release_steps(_read(GIT_WORKFLOW_SKILL)), [])

    def test_pi_package_cr_s1_names_guide_marked_regions_as_readme_source(self):
        self.assertEqual(check_cr029_s1(_read(CR_029)), [])


# ---------------------------------------------------------------------------
# Checker proofs — a conforming guide passes; each violation is caught
# ---------------------------------------------------------------------------

class InstallGuideCheckerProofTest(unittest.TestCase):
    """Proves the gates both ways without the real files: the conforming
    synthetic guide (built from the derived vocabulary) passes every checker,
    and each targeted violation is reported."""

    def setUp(self):
        self.guide = conforming_guide()

    def test_conforming_guide_passes_every_checker(self):
        self.assertEqual(check_headings(self.guide), [])
        for heading, checker in TOPIC_CHECKERS.items():
            with self.subTest(topic=heading):
                self.assertEqual(checker(self.guide), [])
        self.assertEqual(check_marked_regions(self.guide), [])
        self.assertEqual(check_vocabulary(self.guide), [])

    def test_derived_vocabulary_matches_the_code(self):
        self.assertIn("preflight_failed", install_outcomes())
        self.assertIn("stacks_rejected", install_outcomes())
        self.assertIn("already_installed", install_outcomes())
        self.assertEqual(verdicts(), ["detected", "absent", "unknown", "installed"])
        self.assertEqual(preflight_prefixes(), ("harness", "deps", "stack <name>"))
        self.assertEqual(policy_dir_name(), "pi-permission-system")
        with self.assertRaises(AssertionError) as ctx:
            parser_flag("--no-such-flag")
        self.assertIn("--no-such-flag", str(ctx.exception))

    def test_derived_required_terms_do_not_collide_with_blocklist(self):
        rows = _requirements()
        terms = [*install_outcomes(), *known_stacks(), *verdicts(),
                 *sorted(_parser_flags()), *toolchain_installer_terms(),
                 *(r["id"] for r in rows), *(r["provider"] for r in rows),
                 *(f for r in rows for f in r["asset_families"])]
        self.assertEqual([t for t in terms if check_vocabulary(t)], [])

    def test_missing_outcome_is_reported(self):
        broken = self.guide.replace("- `preflight_failed`\n", "")
        self.assertEqual(check_outcomes(broken), [f"{OUTCOMES}: missing `preflight_failed`"])

    def test_term_only_in_prose_does_not_count(self):
        broken = self.guide.replace("`/trust`", "/trust")
        self.assertEqual(check_trust(broken), [f"{TRUST}: missing `/trust`"])

    def test_target_root_with_other_path_does_not_count(self):
        broken = self.guide.replace("`--target-root ~`", "`--target-root ~/sandbox`")
        self.assertEqual(check_real_home(broken), [f"{REAL_HOME}: missing `--target-root ~`"])

    def test_term_in_wrong_section_does_not_count(self):
        broken = self.guide.replace("Re-run with `--reinstall --stacks python,rust`.",
                                    "Re-run later.")
        self.assertEqual(check_widening(broken), [f"{WIDENING}: missing `--stacks`",
                                                  f"{WIDENING}: missing `--reinstall`"])

    def test_duplicate_or_missing_heading_is_reported(self):
        broken = self.guide.replace(f"## {TRUST}\n", "## Trusting\n")
        self.assertEqual(check_headings(broken), [f"heading '## {TRUST}' appears 0 times (want 1)"])

    def test_prerequisites_out_of_dependency_order_is_reported(self):
        rows = _requirements()
        uv = next(r for r in rows if r["id"] == "uv")["remediation"]
        broken = self.guide.replace(f"- `{uv}`\n", "").replace(
            "- `uv tool install git+https://example.invalid/model-b`",
            f"- `uv tool install git+https://example.invalid/model-b`\n- `{uv}`")
        self.assertEqual(len([v for v in check_prerequisites(broken) if "must precede" in v]), 1)
        no_pi = self.guide.replace("Install Pi first; its packages come next.", "Start here.")
        self.assertEqual(len([v for v in check_prerequisites(no_pi) if "Pi must" in v]),
                         len([r for r in rows if r["tier"] == 1]))

    def test_warning_line_without_asset_family_is_reported(self):
        row = next(r for r in _requirements() if r["id"] == "sandesh")
        broken = self.guide.replace(
            f"- `sandesh`: the {row['asset_families'][0]} will not work", "- `sandesh`: warns")
        self.assertEqual([v for v in check_warnings(broken) if "`sandesh`" in v],
                         [f"{WARNINGS}: no line names `sandesh` with one of "
                          f"{list(row['asset_families'])}"])

    def test_missing_preflight_prefix_or_verdict_is_reported(self):
        broken = self.guide.replace("stack <name>: x=y", "stacks x=y").replace("`installed`", "")
        self.assertEqual(check_preflight(broken),
                         [f"{PREFLIGHT}: missing pre-flight line `stack <name>:`",
                          f"{PREFLIGHT}: missing `installed`"])

    def test_offers_without_toolchain_installer_is_reported(self):
        term = toolchain_installer_terms()[0]
        broken = self.guide.replace(f"`{term}`", "a toolchain")
        self.assertEqual(check_offers(broken),
                         [f"{OFFERS}: must show that toolchain installers are offered"])

    def test_marker_faults_are_reported(self):
        begin = "<!-- install-guide:begin install -->"
        end = "<!-- install-guide:end install -->"
        cases = {
            "no region": (self.guide.replace(begin + "\n", "").replace(end + "\n", ""),
                          "no marked region"),
            "nested": (self.guide.replace(begin, begin + "\n<!-- install-guide:begin inner -->", 1),
                       "line 4: region 'inner' nested in 'install'"),
            "never ended": (self.guide.replace(end + "\n", ""), "region 'install' is never ended"),
            "malformed": (self.guide.replace(begin, "<!-- install-guide:begin Install -->"),
                          "line 3: malformed marker '<!-- install-guide:begin Install -->'"),
            "topic outside": (self.guide.replace(f"## {TRUST}", f"{end}\n\n## {TRUST}", 1).replace(
                f"{end}\n\n## {MARKED}", f"## {MARKED}"),
                f"section '{TRUST}' is not wholly inside a marked region"),
            "convention inside": (self.guide.replace(f"{end}\n\n## {MARKED}", f"## {MARKED}")
                                  + f"\n{end}\n",
                                  f"section '{MARKED}' must sit outside every marked region"),
            "convention undocumented": (self.guide.replace(
                "`<!-- install-guide:end <name> -->`", "an end marker"),
                f"section '{MARKED}' must show the end marker in code"),
        }
        for label, (text, expected) in cases.items():
            with self.subTest(case=label):
                self.assertIn(expected, check_marked_regions(text))

    def test_internal_vocabulary_is_reported(self):
        for injected, expected in (
                ("See §S1.", "section sign: '§'"),
                ("Per CR-MDB-037.", "CR id: 'CR-MDB-037'"),
                ("Decision D11.", "decision id: 'D11'"),
                ("The PRD says.", "PRD reference: 'PRD'"),
                ("DN-scaffold notes.", "design-note reference: 'DN-'"),
                ("The RED agent.", "internal vocabulary: 'RED'"),
                ("Next wave.", "internal vocabulary: 'wave'"),
                ("tier-1 tools.", "internal vocabulary: 'tier-1'"),
                ("A user ruling.", "internal vocabulary: 'user ruling'"),
                ("The orchestrator.", "internal vocabulary: 'orchestrator'")):
            with self.subTest(injected=injected):
                self.assertEqual(check_vocabulary(self.guide + "\n" + injected + "\n"), [expected])
        self.assertEqual(check_vocabulary("lifecycle, microwave, recycled, Redis"), [])

    def test_readme_checker_both_ways(self):
        self.assertEqual(check_readme(CONFORMING_README), [])
        bad = {
            "no link": (CONFORMING_README.replace("(docs/install-guide.md)", "(docs/other.md)"),
                        "no markdown link to docs/install-guide.md"),
            "command line": (CONFORMING_README + "\n```\nmodelb-axi --yes --target-root ~\n```\n",
                             "installer command line: 'modelb-axi --yes --target-root ~'"),
            "command span": (CONFORMING_README + "\nRun `uv tool install .` first.\n",
                             "installer command line: 'uv tool install .'"),
            "prompt line": (CONFORMING_README + "\n    $ pi install npm:x\n",
                            "installer command line: 'pi install npm:x'"),
            "too long": (CONFORMING_README + "\n".join(f"line {i}" for i in range(20)),
                         "23 non-blank lines (max 20)"),
            "no title": (CONFORMING_README.replace("# Model B", "Model B"),
                         "first line must be a '# ' title"),
            "no description": (CONFORMING_README.replace(
                "Skills, agent definitions and hooks for an agent-harness workflow.", "## About"),
                "the title must be followed by a description paragraph"),
        }
        for label, (text, expected) in bad.items():
            with self.subTest(case=label):
                self.assertIn(expected, check_readme(text))

    def test_release_and_cr029_checkers_both_ways(self):
        good = ("## Releases\n\nCopy the install guide's marked regions verbatim into the "
                "release notes, then hold a documentation review over the doc set.\n\n## Next\n")
        self.assertEqual(check_release_steps(good), [])
        self.assertEqual(check_release_steps(good.replace("documentation review", "check")),
                         ["## Releases: missing 'documentation review'"])
        self.assertEqual(check_release_steps("## Other\n\nverbatim release notes\n"),
                         ["no '## Releases' section"])
        cr = ("### §S1 — Layout\nThe README is the install-guide.md marked regions.\n"
              "### §S2 — Other\n")
        self.assertEqual(check_cr029_s1(cr), [])
        self.assertEqual(check_cr029_s1(cr.replace("marked regions", "text")),
                         ["§S1: missing 'marked region'"])


if __name__ == "__main__":
    unittest.main()
