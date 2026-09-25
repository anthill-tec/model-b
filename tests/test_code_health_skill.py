"""The adopted ``code-health`` skill bundle (CR-MDB-023).

The bundle is the Model B workflow skill that takes git-pinned code-health
snapshots of a Cargo workspace and ratifies maintenance CRs. Its only
source was a deployed, local-machine copy; CR-MDB-023 adopts it into
``skills-src/code-health/``, detaches every invocation from the local
machine, teaches the audit ledger as it works after CR-MDB-028, and ships
it scoped to the Rust stack.

- §S1: frontmatter ``name: code-health`` and a trigger-bearing description
  carrying the Mainline-only restriction and the snapshot points; the
  adopted text keeps the deployed copy's substance section by section.
  The expected anchors are ENCODED HERE (read from the deployed copy at
  authoring time) -- no test reads the real home.
- §S2: zero ``~/.claude/`` paths; every ``rust-*`` invocation names the
  tool-scripts store derived from ``deploy.TOOL_SCRIPTS_STORE_RELDIR``; no
  Crucible source-checkout path.
- §S3: the two-step filing (``cr-plan`` on ``rust-crucible.py`` then
  ``ledger assign``), hand-mirrored transitions tied to board events,
  ratification after the COMPLETED sync, the recorded drift (``hot-path``,
  multi-domain ledger), no removed/retired mechanism taught, no harness
  tool named (DN §D18).
- §S4: deployed to the store + per-harness link when ``rust`` is selected
  or no stack filter is given, unchanged on a second run, absent under
  ``--stacks python``; carried by the built wheel; ``AGENTS.md`` roster.

Isolation (NON-NEGOTIABLE): every installer run pins HOME, PATH (fake-bin),
PI_CODING_AGENT_DIR, ``--modelb-home`` and ``--target-root`` to per-test
sandboxes via ``tests.test_installer_stack_selection._StackSandboxCase``;
the wheel is built into a temp dir by ``tests.test_package_publishing``'s
own builders. Stdlib only.
"""

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from modelb_axi import deploy
from tests.test_installer_stack_selection import _StackSandboxCase
from tests.test_package_publishing import build_sdist, build_wheel, wheel_names, wheel_read
from tests.test_worktree_flow_surfaces import HISTORY_MARK, WF_CS

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC = REPO_ROOT / "skills-src"
BUNDLE_NAME = "code-health"
BUNDLE_DIR = SKILLS_SRC / BUNDLE_NAME
SKILL_MD = BUNDLE_DIR / "SKILL.md"
AGENTS_MD = REPO_ROOT / "AGENTS.md"
DEAD_SCAN_PY = REPO_ROOT / "scripts" / "rust-dead-scan.py"

#: §S2 -- the store path every rust-* invocation must name, DERIVED from the
#: deploy constant (never a literal): "~/.agents/scripts/".
STORE_PREFIX = f"~/{deploy.TOOL_SCRIPTS_STORE_RELDIR.as_posix()}/"

#: The three adopted Rust health tools (CR-MDB-022).
RUST_TOOLS = ("rust-code-health.py", "rust-dead-scan.py", "rust-crate-map.py")

#: A tool INVOCATION: a rust-* tool name followed by one of its subcommands
#: or modes (or a flag). The optional prefix group captures the path the
#: invocation names, so a bare / relative / ~/.claude path is caught.
RUST_INVOCATION_RE = re.compile(
    r"(?P<prefix>[~\w./-]*?)"
    r"(?P<tool>rust-(?:code-health|dead-scan|crate-map)\.py)"
    r"\s+(?P<verb>snapshot|query|ledger|inventory|pub-scan|deps|reconcile"
    r"|boundaries|hot-path|lift-lint|--[a-z])"
)

#: DN §D18 -- harness tool names a skill must never name (capabilities and
#: CLIs only). ``Bash(`` is Claude Code's permission/tool spelling; the
#: ``process`` tool is Pi's background-process tool.
HARNESS_TOOL_TOKENS = ("run_in_background", "TaskStop", "sandesh_watcher", "Bash(")
PROCESS_TOOL_RE = re.compile(
    r"`process`|\bthe process tool\b|\bprocess tool\b"
    r"|\bprocess\s+(?:start|list|output|wait|kill|stop)\b",
    re.IGNORECASE,
)

#: §S1 section-by-section substance, encoded from the deployed July copy.
#: Each entry: (label, heading regex, meaning-bearing anchors). An anchor is
#: a regex searched INSIDE that section only (case-sensitive unless it
#: carries its own flag), so moving a meaning out of its section fails too.
SECTION_SUBSTANCE = {
    "ownership and snapshot points": (
        r"Ownership",
        (
            r"Mainline-owned",
            r"Tracks never take snapshots",
            r"\bPRE\b|\bpre\b",
            r"\bPOST\b|\bpost\b",
            r"`baseline`",
            r"`adhoc`",
            r"--slice",
            r"(?i)pin(s|ned)? a git commit|git commit",
            r"(?i)dirty",
        ),
    ),
    "snapshot and query verbs": (
        r"Tools",
        (
            r"snapshot --phase \{baseline\|pre\|post\|adhoc\}",
            r"query trend",
            r"query crate <pkg>",
            r"query delta <a> <b>",
            r"query ledger",
            r"rust-dead-scan\.py",
            r"(?i)builds",
        ),
    ),
    "dataset": (
        r"Dataset|Tools",
        (
            r"docs/research/assets/",
            r"crate_map_baseline",
            r"dead_scan_report",
            r"audit-cull-ledger\.jsonl",
            r"dead_code_register\.toml",
            r"health/index\.json",
            r"PROPOSED",
            r"APPROVED",
            r"IN_PROGRESS",
            r"COMPLETED",
            r"STRUCK",
            r"first_seen",
            r"resolved_in",
        ),
    ),
    "procedure": (
        r"Procedure",
        (
            r"git status",
            r"snapshot\.json",
            r"health_delta\.md",
            r"query trend",
            r"query ledger OPEN",
            r"docs\(health\): <phase> snapshot",
            r"(?i)never estimated",
        ),
    ),
    "report template": (
        r"Report template",
        (
            r"Headline",
            r"Size",
            r"Dead-code posture",
            r"Deps/features",
            r"Ledger",
            r"Ratification",
            r"Trend",
            r"Recommended next actions",
            r"allow\(dead_code\)",
        ),
    ),
    "ratification": (
        r"Ratif",
        (
            r"(?i)mainline",
            r"snapshot --phase post --slice",
            r"health_delta\.md",
            r"(?<!NOT-)\bRATIFIED\b",
            r"NOT-RATIFIED",
            r"MANUAL",
            r"(?i)block sign-off|blocks sign-off",
            r"ratified_in",
        ),
    ),
    "caveats": (
        r"Caveats",
        (
            r"pub-scan is regex-based",
            r"(?i)macro-generated",
            r"Coverage masks deadness",
            r"testing = \[\]",
        ),
    ),
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _bundle_text(test: unittest.TestCase) -> str:
    """The adopted SKILL.md, or a clean assertion FAILURE naming the gap."""
    if not SKILL_MD.is_file():
        test.fail(
            f"{SKILL_MD.relative_to(REPO_ROOT)} does not exist -- the "
            f"code-health bundle is not adopted into skills-src/ yet (§S1)"
        )
    return SKILL_MD.read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict:
    """``key: value`` pairs of a leading ``---`` block (continuation lines
    folded into the previous key)."""
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    fields: dict[str, str] = {}
    last = None
    for line in text[4:end].splitlines():
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if match:
            last = match.group(1)
            fields[last] = match.group(2).strip()
        elif last and line.strip():
            fields[last] += " " + line.strip()
    return fields


def _sections(text: str) -> list[tuple[str, str]]:
    """``[(heading, body)]`` for every ``## `` section of the body."""
    parts = re.split(r"^## +(.+)$", text, flags=re.MULTILINE)
    return [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]


def _section(test: unittest.TestCase, text: str, heading_re: str, label: str) -> str:
    """The concatenated heading lines + bodies of every section whose
    heading matches (a heading is part of its section's substance)."""
    bodies = [f"## {heading}{body}" for heading, body in _sections(text)
              if re.search(heading_re, heading, re.IGNORECASE)]
    if not bodies:
        test.fail(
            f"§S1: no `## ` section heading matches /{heading_re}/ -- the "
            f"{label} section of the deployed copy is missing; headings: "
            f"{[h for h, _ in _sections(text)]}"
        )
    return "\n".join(bodies)


def _window(lines: list[str], index: int, radius: int = 2) -> str:
    return "\n".join(lines[max(0, index - radius): index + radius + 1])


def _cs_instruction_sites(lines: list[str]) -> list[tuple[int, str]]:
    """Lines naming ``worktree-flow.py cs`` WITHOUT a history marker on the
    line or an immediate neighbour (CR-MDB-028's approach)."""
    sites = []
    for i, line in enumerate(lines):
        if WF_CS.search(line) and not HISTORY_MARK.search(_window(lines, i, 1)):
            sites.append((i + 1, line.strip()))
    return sites


def _mention_instruction_sites(lines: list[str], token_re: re.Pattern) -> list[tuple[int, str]]:
    """Lines naming ``token_re`` that are not history-marked (±1 line)."""
    return [
        (i + 1, line.strip()) for i, line in enumerate(lines)
        if token_re.search(line) and not HISTORY_MARK.search(_window(lines, i, 1))
    ]


def _dead_scan_modes_from_help() -> list[str]:
    """The tool's own mode list, parsed from ``rust-dead-scan.py --help``."""
    result = subprocess.run(
        [sys.executable, str(DEAD_SCAN_PY), "--help"],
        capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise AssertionError(f"rust-dead-scan.py --help failed: {result.stderr!r}")
    flat = " ".join(result.stdout.split())
    match = re.search(r"subset of:\s*(.+?)\s+(?:options:|-h,)", flat)
    if match is None:
        raise AssertionError(f"no 'subset of:' mode list in --help: {result.stdout!r}")
    return match.group(1).split()


def _token_re(word: str) -> re.Pattern:
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(word) + r"(?![A-Za-z0-9_-])")


_CULL_ONLY_RE = re.compile(
    r"\bcull[- ]only\b|\bonly\b[^.\n]{0,30}\bcull\b|\bcull\b[^.\n]{0,30}\bonly\b",
    re.IGNORECASE,
)


def _cull_only_sentences(text: str) -> list[str]:
    """Sentences that describe the LEDGER as cull-only."""
    sentences = re.split(r"(?<=[.!?])\s+|\n", text)
    return [s.strip() for s in sentences
            if re.search(r"ledger", s, re.IGNORECASE) and _CULL_ONLY_RE.search(s)]


_AUTOMATIC_RE = re.compile(r"\bautomatic\w*|\bauto-?mirror\w*", re.IGNORECASE)
_NEGATION_RE = re.compile(r"\b(not|no longer|never|nothing|no)\b", re.IGNORECASE)


def _automatic_ledger_claims(lines: list[str]) -> list[tuple[int, str]]:
    """Lines asserting the ledger mirrors/fills itself AUTOMATICALLY (a
    line that negates it -- "never automatic" -- is not a claim)."""
    return [
        (i + 1, line.strip()) for i, line in enumerate(lines)
        if _AUTOMATIC_RE.search(line) and not _NEGATION_RE.search(line)
    ]


def _harness_tool_hits(lines: list[str]) -> list[tuple[int, str]]:
    hits = []
    for i, line in enumerate(lines):
        for token in HARNESS_TOOL_TOKENS:
            if token in line:
                hits.append((i + 1, token))
        if PROCESS_TOOL_RE.search(line):
            hits.append((i + 1, "process tool"))
    return hits


# ---------------------------------------------------------------------------
# §S1 -- author the bundle in the repo
# ---------------------------------------------------------------------------

class CodeHealthFrontmatterS1Test(unittest.TestCase):
    """§S1 AC1 -- ``name: code-health`` and a trigger-bearing description
    with the Mainline-only restriction and the snapshot points."""

    def test_s1_frontmatter_name_is_code_health(self):
        fields = _frontmatter(_bundle_text(self))
        self.assertEqual(fields.get("name"), "code-health",
                         f"§S1: frontmatter must declare `name: code-health`; got {fields!r}")

    def test_s1_description_carries_the_mainline_only_restriction(self):
        description = _frontmatter(_bundle_text(self)).get("description", "")
        self.assertRegex(description, re.compile(r"\bmainline\b", re.I),
                         "§S1: the description must name the Mainline orchestrator")
        self.assertRegex(
            description, re.compile(r"exclusive|\bonly\b", re.I),
            "§S1: the description must RESTRICT snapshots/ratification to Mainline",
        )
        self.assertRegex(
            description, re.compile(r"never a track|not a track|tracks? never", re.I),
            "§S1: the description must exclude tracks explicitly -- a track "
            "taking a snapshot corrupts the ratification record",
        )

    def test_s1_description_names_every_snapshot_point(self):
        description = _frontmatter(_bundle_text(self)).get("description", "")
        points = {
            "baseline": r"\bbaseline\b",
            "PRE": r"\bpre\b",
            "POST": r"\bpost\b",
            "wave boundaries": r"wave boundar",
            "ad hoc": r"\bad[- ]?hoc\b",
        }
        missing = [name for name, pattern in points.items()
                   if not re.search(pattern, description, re.IGNORECASE)]
        self.assertEqual(missing, [],
                         f"§S1: the description must name every snapshot point; "
                         f"missing {missing} in {description!r}")

    def test_s1_bundle_runs_no_chezmoi(self):
        text = _bundle_text(self)
        hits = [ln for ln in text.splitlines() if re.search(r"\bchezmoi\b", ln)]
        self.assertEqual(hits, [], "§S1: the adopted bundle names no chezmoi command")


class CodeHealthSubstanceS1Test(unittest.TestCase):
    """§S1 AC2 -- the adopted text keeps the deployed copy's substance
    section by section. One test per section; each asserts that section's
    meaning-bearing anchors appear INSIDE it."""

    def _assert_section(self, label: str):
        heading_re, anchors = SECTION_SUBSTANCE[label]
        body = _section(self, _bundle_text(self), heading_re, label)
        missing = [a for a in anchors if not re.search(a, body)]
        self.assertEqual(missing, [],
                         f"§S1: the {label} section lost deployed substance; "
                         f"missing anchors {missing}")

    def test_s1_ownership_and_snapshot_points_section_keeps_its_substance(self):
        self._assert_section("ownership and snapshot points")

    def test_s1_snapshot_and_query_verbs_section_keeps_its_substance(self):
        self._assert_section("snapshot and query verbs")

    def test_s1_dataset_description_keeps_its_substance(self):
        self._assert_section("dataset")

    def test_s1_procedure_section_keeps_its_substance(self):
        self._assert_section("procedure")

    def test_s1_report_template_section_keeps_its_substance(self):
        self._assert_section("report template")

    def test_s1_ratification_section_keeps_its_substance(self):
        self._assert_section("ratification")

    def test_s1_caveats_section_keeps_its_substance(self):
        self._assert_section("caveats")


# ---------------------------------------------------------------------------
# §S2 -- detach every invocation
# ---------------------------------------------------------------------------

class CodeHealthDetachmentS2Test(unittest.TestCase):
    """§S2 -- no local-machine path; tools at the deployed store."""

    def test_s2_store_prefix_is_derived_from_the_deploy_constant(self):
        # Precondition pin on the derivation itself (not a literal compare
        # of the bundle): the constant resolves to the .agents/scripts store.
        self.assertEqual(STORE_PREFIX, "~/.agents/scripts/")

    def test_s2_bundle_has_zero_dot_claude_paths(self):
        text = _bundle_text(self)
        hits = [f"{i}: {ln.strip()}" for i, ln in enumerate(text.splitlines(), 1)
                if "~/.claude/" in ln or ".claude/scripts" in ln]
        self.assertEqual(hits, [], "§S2: zero `~/.claude/` paths may remain")

    def test_s2_every_rust_tool_invocation_names_the_tool_scripts_store(self):
        text = _bundle_text(self)
        invocations = list(RUST_INVOCATION_RE.finditer(text))
        tools_invoked = {m.group("tool") for m in invocations}
        self.assertTrue(
            {"rust-code-health.py", "rust-dead-scan.py"} <= tools_invoked,
            f"§S2: the bundle must invoke rust-code-health.py and "
            f"rust-dead-scan.py; invoked {sorted(tools_invoked)}",
        )
        wrong = [
            f"{m.group('prefix') or '<bare>'}{m.group('tool')} {m.group('verb')}"
            for m in invocations if m.group("prefix") != STORE_PREFIX
        ]
        self.assertEqual(
            wrong, [],
            f"§S2: every rust-* invocation must name {STORE_PREFIX}<tool> "
            f"(from deploy.TOOL_SCRIPTS_STORE_RELDIR); offenders: {wrong}",
        )

    def test_s2_no_crucible_source_checkout_path(self):
        text = _bundle_text(self)
        self.assertNotIn("data_projects", text,
                         "§S2: no path to a Crucible source checkout")
        self.assertNotIn("crucible:clients", text,
                         "§S2: no source-checkout shorthand for Crucible clients")
        prefixed = re.findall(r"([~\w./-]+/)rust-crucible\.py", text)
        wrong = [p for p in prefixed if p != "~/.crucible/clients/"]
        self.assertEqual(
            wrong, [],
            f"§S2: rust-crucible.py is named at Crucible's manifest path "
            f"(~/.crucible/clients/ by default); got prefixes {wrong}",
        )


# ---------------------------------------------------------------------------
# §S3 -- teach the ledger as it now works
# ---------------------------------------------------------------------------

class CodeHealthLedgerS3Test(unittest.TestCase):
    """§S3 -- filing, hand-mirrored transitions, ratification order."""

    def test_s3_filing_is_cr_plan_on_rust_crucible_then_ledger_assign(self):
        text = _bundle_text(self)
        cr_plan = re.search(r"rust-crucible\.py[^\n]*\bcr-plan\b", text)
        assign = re.search(
            r"ledger\s+assign\b[^\n]*--slice\s+\S+[^\n]*--ids\s+\S+", text
        )
        self.assertIsNotNone(cr_plan, "§S3: filing step 1 is `rust-crucible.py … cr-plan …`")
        self.assertIsNotNone(
            assign, "§S3: filing step 2 is `rust-code-health.py ledger assign --slice <CR> --ids …`"
        )
        assert cr_plan is not None and assign is not None
        self.assertLess(cr_plan.start(), assign.start(),
                        "§S3: cr-plan files the CR BEFORE ledger assign stamps its findings")

    def test_s3_in_progress_sync_is_tied_to_first_cycle_activation(self):
        lines = _bundle_text(self).splitlines()
        sites = [i for i, ln in enumerate(lines)
                 if re.search(r"ledger\s+sync\b[^\n]*--slice\s+\S+[^\n]*--db-state\s+IN_PROGRESS\b", ln)]
        self.assertTrue(sites, "§S3: `ledger sync --slice <CR> --db-state IN_PROGRESS` must be shown")
        tied = [i for i in sites
                if re.search(r"activat", _window(lines, i), re.I)
                and re.search(r"\bcycle\b", _window(lines, i), re.I)]
        self.assertTrue(tied, "§S3: the IN_PROGRESS sync is tied to the CR's first cycle activating")

    def test_s3_completed_sync_carries_commit_and_is_tied_to_cr_close(self):
        lines = _bundle_text(self).splitlines()
        sites = [
            i for i, ln in enumerate(lines)
            if re.search(r"ledger\s+sync\b", ln) and re.search(r"--slice\s+\S+", ln)
            and re.search(r"--db-state\s+COMPLETED\b", ln) and re.search(r"--commit\s+\S+", ln)
        ]
        self.assertTrue(
            sites,
            "§S3: `ledger sync --slice <CR> --db-state COMPLETED --commit <merge sha>` must be shown",
        )
        tied = [i for i in sites if "cr-close" in _window(lines, i)]
        self.assertTrue(tied, "§S3: the COMPLETED sync is tied to `cr-close`")

    def test_s3_no_automatic_or_auto_mirror_ledger_claim(self):
        claims = _automatic_ledger_claims(_bundle_text(self).splitlines())
        self.assertEqual(claims, [], "§S3: the ledger is mirrored BY HAND now; no "
                                     "AUTOMATIC / auto-mirror claim may remain")

    def test_s3_full_sync_is_limited_to_a_legacy_changeset_db(self):
        lines = _bundle_text(self).splitlines()
        stated = [i for i, ln in enumerate(lines)
                  if re.search(r"\blegacy\b", _window(lines, i, 1), re.I)
                  and "ChangeSet" in _window(lines, i, 1)
                  and re.search(r"\bsync\b", ln)]
        self.assertTrue(stated, "§S3: the no-argument full sync is stated to work only "
                                "where a legacy ChangeSet DB exists")

    def test_s3_ratification_follows_the_completed_sync(self):
        text = _bundle_text(self)
        completed = re.search(r"ledger\s+sync\b[^\n]*--db-state\s+COMPLETED\b", text)
        self.assertIsNotNone(completed, "§S3: a COMPLETED sync must be shown")
        ratify_body = _section(self, text, r"Ratif", "ratification")
        post = re.search(r"snapshot --phase post --slice", ratify_body)
        self.assertIsNotNone(post, "§S3: ratification runs `snapshot --phase post --slice <CR>`")
        assert completed is not None and post is not None
        heading = re.search(r"^## +[^\n]*Ratif", text, re.MULTILINE | re.IGNORECASE)
        assert heading is not None
        post_in_text = re.search(r"snapshot --phase post --slice", text[heading.start():])
        assert post_in_text is not None
        self.assertLess(completed.start(), heading.start() + post_in_text.start(),
                        "§S3: the COMPLETED sync precedes the ratification snapshot")
        self.assertRegex(ratify_body, re.compile(r"COMPLETED[^\n]{0,80}\bsync|\bsync\b[^\n]{0,80}COMPLETED"),
                         "§S3: the ratification section runs AFTER the COMPLETED sync, and says so")

    def test_s3_three_verdicts_and_the_not_ratified_block_are_stated(self):
        body = _section(self, _bundle_text(self), r"Ratif", "ratification")
        for verdict in (r"(?<!NOT-)\bRATIFIED\b", r"NOT-RATIFIED", r"\bMANUAL\b"):
            self.assertRegex(body, verdict, f"§S3: verdict /{verdict}/ must be stated")
        self.assertRegex(
            body, re.compile(r"NOT-RATIFIED[^\n]{0,40}\bblocks?\b[^\n]{0,10}sign-off", re.I),
            "§S3: any NOT-RATIFIED blocks sign-off",
        )

    def test_s3_dead_scan_mode_list_matches_the_tools_own_help(self):
        modes = _dead_scan_modes_from_help()
        self.assertIn("hot-path", modes, f"precondition: the tool carries hot-path; modes={modes}")
        self.assertEqual(len(modes), 7, f"precondition: seven modes; got {modes}")
        lines = _bundle_text(self).splitlines()
        sites = [i for i, ln in enumerate(lines) if "rust-dead-scan.py" in ln]
        self.assertTrue(sites, "§S3: the bundle must show rust-dead-scan.py")
        best_missing = modes
        for i in sites:
            window = "\n".join(lines[i: i + 3])
            missing = [m for m in modes if not _token_re(m).search(window)]
            if len(missing) < len(best_missing):
                best_missing = missing
        self.assertEqual(best_missing, [],
                         f"§S3: the rust-dead-scan.py mode list must name every mode "
                         f"of the tool's --help ({modes}); missing {best_missing}")

    def test_s3_ledger_is_documented_as_multi_domain(self):
        lines = _bundle_text(self).splitlines()
        documented = [i for i, ln in enumerate(lines)
                      if "--domain" in ln
                      and re.search(r"\bcull\b", _window(lines, i, 1))
                      and re.search(r"\btemporal\b", _window(lines, i, 1))]
        self.assertTrue(documented, "§S3: `--domain cull|temporal|<name>` must be documented")

    def test_s3_no_sentence_calls_the_ledger_cull_only(self):
        offenders = _cull_only_sentences(_bundle_text(self))
        self.assertEqual(offenders, [], "§S3: the ledger is multi-domain, never cull-only")

    def test_s3_bundle_teaches_no_removed_or_retired_mechanism(self):
        lines = _bundle_text(self).splitlines()
        self.assertEqual(_cs_instruction_sites(lines), [],
                         "§S3: `worktree-flow.py cs` was removed by CR-MDB-028")
        for token in ("set_state", "schedule_db"):
            with self.subTest(token=token):
                self.assertEqual(
                    _mention_instruction_sites(lines, re.compile(re.escape(token))), [],
                    f"§S3: `{token}` may not appear as an instruction",
                )

    def test_s3_no_claim_that_crucible_scheduling_is_unreleased(self):
        lines = _bundle_text(self).splitlines()
        claims = [
            (i + 1, ln.strip()) for i, ln in enumerate(lines)
            if re.search(r"unreleased|not (yet )?released|pre-?release", ln, re.I)
            and re.search(r"crucible|schedul", _window(lines, i, 1), re.I)
        ]
        self.assertEqual(claims, [], "§S3: no statement that Crucible's scheduling is unreleased")

    def test_s3_no_worktree_flow_cs_instruction_across_skills_src_and_scripts(self):
        # Pin (true today; bites if the adoption or any later edit teaches
        # the removed verb anywhere a published surface ships).
        offenders = []
        for root in (SKILLS_SRC, REPO_ROOT / "scripts"):
            for path in sorted(root.rglob("*")):
                if not path.is_file() or "__pycache__" in path.parts:
                    continue
                try:
                    lines = path.read_text(encoding="utf-8").splitlines()
                except (UnicodeDecodeError, OSError):
                    continue
                offenders.extend(f"{path.relative_to(REPO_ROOT)}:{n}: {ln}"
                                 for n, ln in _cs_instruction_sites(lines))
        self.assertEqual(offenders, [], "§S3: `worktree-flow.py cs` appears nowhere as an instruction")

    def test_s3_bundle_names_no_harness_tool(self):
        hits = _harness_tool_hits(_bundle_text(self).splitlines())
        self.assertEqual(hits, [], "§S3 / DN §D18: skills name capabilities and CLIs, not harness tools")


class CodeHealthDetectorProofS3Test(unittest.TestCase):
    """Detector proofs: each text gate BITES on the defect it guards and
    spares the correct text, so a green §S3 result means something."""

    def test_s3_cs_detector_flags_a_live_step_and_spares_history(self):
        live = ["filing: worktree-flow.py cs --cr CR-X --type maintenance"]
        history = ["`worktree-flow.py cs` was removed by CR-MDB-028; use cr-plan"]
        self.assertEqual(len(_cs_instruction_sites(live)), 1)
        self.assertEqual(_cs_instruction_sites(history), [])

    def test_s3_automatic_detector_flags_the_deployed_claim_and_spares_a_negation(self):
        claim = ["# ledger lifecycle (Maintenance CRs only — normally AUTOMATIC via worktree-flow):"]
        mirror = ["#   transitions: schedule_db.set_state auto-mirrors IN_PROGRESS/COMPLETED"]
        negated = ["The ledger does not mirror automatically; sync it by hand."]
        self.assertEqual(len(_automatic_ledger_claims(claim)), 1)
        self.assertEqual(len(_automatic_ledger_claims(mirror)), 1)
        self.assertEqual(_automatic_ledger_claims(negated), [])

    def test_s3_cull_only_detector_flags_a_cull_only_ledger_sentence(self):
        self.assertEqual(len(_cull_only_sentences("The ledger is cull-only.")), 1)
        self.assertEqual(len(_cull_only_sentences("The ledger tracks only cull findings.")), 1)
        self.assertEqual(_cull_only_sentences(
            "The ledger is multi-domain: --domain cull|temporal|<name>."), [])

    def test_s3_harness_tool_detector_flags_each_token(self):
        lines = ["Launch with Bash(run_in_background)", "stop via TaskStop",
                 "start sandesh_watcher", "use the process tool", "plain CLI: git status"]
        hit_lines = {n for n, _ in _harness_tool_hits(lines)}
        self.assertEqual(hit_lines, {1, 2, 3, 4})

    def test_s2_invocation_detector_flags_bare_and_claude_paths(self):
        text = ("python3 ~/.claude/scripts/rust-code-health.py snapshot --phase pre\n"
                "`rust-code-health.py ledger sync --slice CR-1`\n"
                f"python3 {STORE_PREFIX}rust-dead-scan.py inventory\n")
        prefixes = [m.group("prefix") for m in RUST_INVOCATION_RE.finditer(text)]
        self.assertEqual(prefixes, ["~/.claude/scripts/", "", STORE_PREFIX])


# ---------------------------------------------------------------------------
# §S4 -- ship it, scoped to Rust
# ---------------------------------------------------------------------------

class CodeHealthBundleScopeS4Test(unittest.TestCase):
    """§S4 -- deploy's bundle discovery scopes code-health to the Rust
    stack (CR-MDB-036 §S7 rule), measured on a fixture asset root so the
    rule is proven independently of the repo's own bundle set."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modelb-cr023-assets-"))
        for name in ("code-health", "model-b", "crucible-report-python",
                     "crucible-report-rust"):
            d = self.root / "skills-src" / name
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _names(self, stacks):
        return {p.name for p in deploy._skill_bundles(self.root, stacks)}

    def test_s4_python_selection_excludes_code_health(self):
        self.assertEqual(self._names(["python"]), {"model-b", "crucible-report-python"})

    def test_s4_rust_selection_includes_code_health(self):
        self.assertEqual(self._names(["rust"]),
                         {"code-health", "model-b", "crucible-report-rust"})

    def test_s4_no_stack_filter_includes_code_health(self):
        self.assertEqual(self._names(None), {"code-health", "model-b",
                                             "crucible-report-python", "crucible-report-rust"})


class CodeHealthInstallS4Test(_StackSandboxCase):
    """§S4 AC1 -- sandboxed installer runs (HOME, PATH, agent dir,
    --modelb-home, --target-root all sandboxed), for the Pi-only roster
    (CR-MDB-031 §S1: flipped from claude-code; the per-harness skills-dir
    link asserts are retired with the link writer)."""

    STORE_REL = f".agents/skills/{BUNDLE_NAME}/SKILL.md"

    def _installer_args(self, *extra) -> list[str]:
        return ["--harnesses", "pi", "--modelb-home", str(self.modelb_home),
                "--target-root", str(self.target_root), *extra]

    def _manifest(self) -> dict[str, str]:
        return {f["path"]: f["sha256"] for f in self.install_toml().get("files", [])}

    def _assert_code_health_deployed(self):
        store_md = self.target_root / self.STORE_REL
        self.assertTrue(store_md.is_file(), f"§S4: {self.STORE_REL} must be deployed to the store")
        self.assertTrue(SKILL_MD.is_file(), "§S4: the source bundle must exist")
        self.assertEqual(store_md.read_bytes(), SKILL_MD.read_bytes(),
                         "§S4: the store copy is the source bundle, byte for byte")
        self.assertEqual(self._manifest().get(self.STORE_REL), deploy.sha256_file(SKILL_MD),
                         "§S4: install.toml records the bundle's sha256")

    def test_s4_rust_selection_deploys_code_health_with_link_and_manifest(self):
        self.assert_installed(self.run_installer("--stacks", "rust"))
        self._assert_code_health_deployed()

    def test_s4_no_stack_filter_deploys_code_health_with_link_and_manifest(self):
        self.assert_installed(self.run_installer())
        self._assert_code_health_deployed()

    def test_s4_second_rust_run_reports_code_health_unchanged(self):
        self.assert_installed(self.run_installer("--stacks", "rust"))
        store_md = self.target_root / self.STORE_REL
        self.assertTrue(store_md.is_file(), f"§S4: {self.STORE_REL} must be deployed on the first run")
        before_sha = self._manifest().get(self.STORE_REL)
        before_mtime = store_md.stat().st_mtime_ns

        result = self.run_installer("--reinstall", "--stacks", "rust")
        axi = self.assert_installed(result)
        self.assertEqual(self._manifest().get(self.STORE_REL), before_sha,
                         "§S4: the second run records the same sha256")
        self.assertEqual(store_md.stat().st_mtime_ns, before_mtime,
                         "§S4: the second run leaves the deployed file untouched")
        flagged = [p for p in list(axi.get("skipped", [])) + list(axi.get("unmanaged", []))
                   if BUNDLE_NAME in str(p)]
        self.assertEqual(flagged, [], "§S4: nothing of code-health is skipped or unmanaged")

    def test_s4_python_selection_does_not_deploy_code_health(self):
        # Pin today (no bundle yet); bites once the bundle exists and the
        # deploy is not scoped to rust.
        self.assert_installed(self.run_installer("--stacks", "python"))
        self.assertFalse((self.target_root / ".agents" / "skills" / BUNDLE_NAME).exists())
        self.assertEqual([p for p in self._manifest()
                          if p.startswith(f".agents/skills/{BUNDLE_NAME}/")], [])


class CodeHealthWheelS4Test(unittest.TestCase):
    """§S4 AC2 -- the BUILT wheel (sdist -> wheel, via the publishing
    suite's own builders) carries the bundle."""

    WHEEL_MEMBER = f"modelb_axi/_assets/skills-src/{BUNDLE_NAME}/SKILL.md"

    @classmethod
    def setUpClass(cls):
        cls.build_root = Path(tempfile.mkdtemp(prefix="modelb-cr023-wheel-"))
        sdist = build_sdist(REPO_ROOT, cls.build_root / "sdist")
        cls.wheel = build_wheel(sdist, cls.build_root / "wheel")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.build_root, ignore_errors=True)

    def test_s4_built_wheel_carries_the_code_health_skill(self):
        names = wheel_names(self.wheel)
        self.assertIn(self.WHEEL_MEMBER, names,
                      f"§S4: the built wheel must carry {self.WHEEL_MEMBER}")
        self.assertEqual(wheel_read(self.wheel, self.WHEEL_MEMBER), SKILL_MD.read_bytes())


class AgentsMdBundleRosterS4Test(unittest.TestCase):
    """§S4 AC4 -- AGENTS.md: 13 bundles (14 until CR-MDB-031 §S4 retired
    chezmoi), code-health Model B-owned, 6 imported wherever it counts them."""

    def setUp(self):
        self.text = AGENTS_MD.read_text(encoding="utf-8")

    def test_s4_agents_md_states_thirteen_skill_bundles(self):
        counts = re.findall(r"\b(\d+) skill bundles\b", self.text)
        self.assertEqual(counts, ["13"],
                         f"\u00a7S4: AGENTS.md must state '13 skill bundles' (and no other "
                         f"count); found counts {counts}")

    def test_s4_agents_md_lists_code_health_as_model_b_owned(self):
        row = next((ln for ln in self.text.splitlines() if ln.startswith("| `skills-src/`")), "")
        self.assertTrue(row, "precondition: AGENTS.md carries the skills-src/ inventory row")
        owned = re.search(r"Model[- ]B[- ]owned:(.*?)Imported", row, re.IGNORECASE)
        self.assertIsNotNone(owned, f"the row names a Model B-owned list: {row!r}")
        assert owned is not None
        self.assertIn("`code-health`", owned.group(1))

    def test_s4_agents_md_counts_six_imported_bundles_wherever_it_counts(self):
        counts = re.findall(r"\b(\d+)\s+imported\s+bundles\b", self.text, re.IGNORECASE)
        self.assertTrue(counts, "AGENTS.md counts its imported bundles somewhere")
        self.assertEqual(sorted(set(counts)), ["6"],
                         f"§S4: every imported-bundle count must say 6; got {counts}")


class ModelBOwnedTestSetS4Test(unittest.TestCase):
    """§S4 AC3 -- the installer-asset suite's Model B-owned set includes
    code-health under a size-free name; no test pins a seven-count of the
    Model B-owned bundles."""

    def test_s4_model_b_owned_set_includes_code_health(self):
        from tests import test_installer_assets
        self.assertIn(BUNDLE_NAME, test_installer_assets.MODELB_OWNED_BUNDLE_NAMES)

    def test_s4_no_test_constant_name_carries_a_bundle_count(self):
        count_name = re.compile(
            r"\b(?:[A-Z0-9]+_)*(?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|"
            r"ELEVEN|TWELVE|THIRTEEN|FOURTEEN|\d+)_(?:[A-Z0-9]+_)*BUNDLES?(?:_[A-Z0-9]+)*\b"
        )
        seven_owned = re.compile(r"\b(?:7|seven)\s+Model[- ]B[- ]owned", re.IGNORECASE)
        offenders = []
        for path in sorted((REPO_ROOT / "tests").glob("*.py")):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if count_name.search(line) or seven_owned.search(line):
                    offenders.append(f"{path.name}:{n}: {line.strip()}")
        self.assertEqual(offenders, [], "§S4: no size-bearing bundle constant, no "
                                        "seven-count assertion on the Model B-owned bundles")


# ---------------------------------------------------------------------------
# C3 VERIFY findings F2 / F3 / F5 -- pinned before the fix
# ---------------------------------------------------------------------------

INSTALL_GUIDE = REPO_ROOT / "docs" / "install-guide.md"
RUST_ORCHESTRATION = SKILLS_SRC / "memory-templates" / "rust-orchestration.md"

#: F3 -- the flags ``rust-crucible.py cr-close --help`` takes: ``--commit``
#: (required by argparse), ``--agent`` (required by the server, §S2b: every
#: workflow verb posts as a live registered caller) and ``--cr`` (names the
#: plan being closed). Pinned, not read from the installed client, so no test
#: reads the real home.
CR_CLOSE_FLAGS = ("--cr", "--commit", "--agent")

#: F2 -- `rust` paired with `code-health` inside one sentence.
_RUST_CODE_HEALTH_PAIR_RE = re.compile(r"`rust`[^.]{0,80}`code-health`")


def _guide_region(test: unittest.TestCase, name: str) -> str:
    """The body of one ``install-guide:begin/end <name>`` region."""
    text = INSTALL_GUIDE.read_text(encoding="utf-8")
    match = re.search(
        rf"<!-- install-guide:begin {re.escape(name)} -->\n(.*?)"
        rf"<!-- install-guide:end {re.escape(name)} -->",
        text, re.DOTALL,
    )
    if match is None:
        test.fail(f"precondition: docs/install-guide.md carries the `{name}` region")
    return match.group(1)


def _sentences(text: str) -> list[str]:
    """Sentences of prose, line breaks folded."""
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", " ".join(text.split())) if s.strip()]


class CodeHealthCrCloseFlagsTest(unittest.TestCase):
    """F3 -- the skill's ``cr-close`` invocation carries the flags the
    client takes; without ``--agent`` the server refuses the verb."""

    def test_cr_close_invocation_carries_cr_commit_and_agent(self):
        lines = _bundle_text(self).splitlines()
        sites = [(i + 1, ln) for i, ln in enumerate(lines)
                 if re.search(r"rust-crucible\.py\s+cr-close\b", ln)]
        self.assertTrue(sites, "F3: the skill shows `rust-crucible.py cr-close …`")
        missing = [
            (n, [f for f in CR_CLOSE_FLAGS if not re.search(re.escape(f) + r"\s+\S+", ln)])
            for n, ln in sites
        ]
        self.assertEqual([m for m in missing if m[1]], [],
                         f"F3: every cr-close invocation carries {CR_CLOSE_FLAGS} with a value")


class CodeHealthStackScopeDocsTest(unittest.TestCase):
    """F2 -- the install guide and the ``--stacks`` help say that `rust`
    also deploys the ``code-health`` bundle."""

    def test_choosing_stacks_pairs_rust_with_code_health(self):
        self.assertRegex(_guide_region(self, "choosing-stacks"), _RUST_CODE_HEALTH_PAIR_RE,
                         "F2: `Choosing stacks` says selecting `rust` also deploys `code-health`")

    def test_adding_stacks_later_pairs_rust_with_code_health(self):
        self.assertRegex(_guide_region(self, "adding-stacks-later"), _RUST_CODE_HEALTH_PAIR_RE,
                         "F2: `Adding stacks later` says adding `rust` also deploys `code-health`")

    def test_guide_no_longer_deploys_every_other_skill_whatever_the_stacks(self):
        text = INSTALL_GUIDE.read_text(encoding="utf-8")
        offenders = [s for s in _sentences(text)
                     if re.search(r"\bskills?\b", s) and re.search(r"whatever stacks", s)
                     and "code-health" not in s]
        self.assertEqual(offenders, [], "F2: code-health is stack-scoped; no sentence may say "
                                        "every non-report skill deploys whatever stacks are chosen")

    def test_stacks_help_pairs_rust_with_code_health(self):
        from modelb_axi.cli import _build_parser
        action = next(a for a in _build_parser()._actions if "--stacks" in a.option_strings)
        self.assertRegex(action.help or "", re.compile(r"\brust\b[^()]{0,40}\bcode-health\b"),
                         "F2: the --stacks help says `rust` also deploys code-health")


class RustOrchestrationLedgerTemplateTest(unittest.TestCase):
    """F5 -- the Rust memory template teaches the ledger as it works after
    CR-MDB-028: cr-plan on rust-crucible.py, ledger assign, hand sync."""

    def setUp(self):
        self.text = RUST_ORCHESTRATION.read_text(encoding="utf-8")

    def test_no_present_tense_set_state_auto_mirror_claim(self):
        claims = [s for s in _sentences(self.text)
                  if re.search(r"set_state[^.]{0,200}\b(?:auto-?mirrors|mirrors)\b", s)]
        self.assertEqual(claims, [], "F5: `schedule_db.set_state` no longer mirrors the ledger")

    def test_filing_names_rust_crucible_cr_plan(self):
        wrong = [ln.strip()[:160] for ln in self.text.splitlines()
                 if re.search(r"python-crucible\.py[^\n]{0,20}\bcr-plan\b", ln)]
        self.assertEqual(wrong, [], "F5: the Rust template files with rust-crucible.py, "
                                    "not python-crucible.py")
        self.assertRegex(self.text, r"rust-crucible\.py[^\n]{0,20}\bcr-plan\b",
                         "F5: filing is `rust-crucible.py cr-plan`")

    def test_points_at_the_code_health_skills_manual_ledger_sync(self):
        hits = [s for s in _sentences(self.text)
                if re.search(r"ledger sync[^.]*--db-state", s)
                and "code-health" in s and re.search(r"(?i)by hand|manual", s)]
        self.assertTrue(hits, "F5: the template points at the code-health skill's manual "
                              "`ledger sync --db-state …` steps")


if __name__ == "__main__":
    unittest.main()
