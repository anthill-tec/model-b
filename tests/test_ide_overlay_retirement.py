"""RED-phase tests for CR-MDB-024 cycle C2 (\u00a7S3 \u2014 retire the vscode agents: an
IDE is not a stack; \u00a7S4 \u2014 records).

Written before any of \u00a7S3/\u00a7S4's production-code or doc corrections land, so
every test below is expected to FAIL against the current tree: the VS Code
crucible-report bundle, its reference router, its generator/CLI stack
entries and its PRD/DN/AGENTS.md/CRUCIBLE-HANDOVER.md census mentions are
all still live today.

Naming note (deliberate, see the module-level grep gate below): this file is
named after the FEATURE (retiring the editor-overlay agent stack), never
after the CR/cycle, and its own filename carries no literal occurrence of
the retired stack's slug \u2014 see ``VscodeReferenceGrepGateS3Test`` for why.

\u00a7S3 AC1's zero-reference grep gate and the self-reference problem
--------------------------------------------------------------------
\u00a7S3 AC1 requires ZERO occurrences of the retired stack's slug anywhere under
``skills-src/``, ``generator/``, ``modelb_axi/`` **and** ``tests/``. A test
module that implements that very sweep, and other test modules that
legitimately keep citing the retired client request as a DECLINED historical
record (PRD \u00a7D7, the DN's Scripts/AXI-wave entry \u2014 both untouched by this
CR's Non-goals), would otherwise trip their own gate by definition. This repo
already has a precedent for exactly this shape of self-reference \u2014
``tests/test_client_verb_sweep.py``'s own ``BAN_DEFINING_FILES``/``GUARD_TEST``
carve-out excludes the files that DEFINE a ban from the ban's own scan. The
gate below follows the same convention: a short, explicit, justified
carve-out list (this module itself, plus the two modules that keep a
legitimate historical citation), rather than obfuscating the search token.
Every OTHER test file in this cycle's migration was cleaned to a genuine
zero \u2014 see the RED report for the full migrated-test-id list.

Stdlib only: unittest + re + os + sys + subprocess + shutil + tempfile +
pathlib.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC_DIR = REPO_ROOT / "skills-src"
HANDOVER_MD = SKILLS_SRC_DIR / "CRUCIBLE-HANDOVER.md"
BUILD_PY = REPO_ROOT / "generator" / "build.py"
AGENTS_MD = REPO_ROOT / "AGENTS.md"
DN_MULTI_HARNESS = REPO_ROOT / "docs" / "research" / "DN-multi-harness-deploy-model.md"
PRD = REPO_ROOT / "docs" / "research" / "PRD-model-b-rationalization.md"
DN_PLAN_REVIEW = REPO_ROOT / "docs" / "research" / "DN-rationalization-plan-review.md"
QUEUE_README = REPO_ROOT / "docs" / "changes" / "README.md"

# \u00a7S3 AC1's grep-gate scan roots, exactly as the AC names them.
SCAN_ROOTS = ("skills-src", "generator", "modelb_axi", "tests")

# The explicit, justified carve-out from \u00a7S3 AC1's own scan (see the module
# docstring). Every entry is repo-root-relative, POSIX-separated.
VSCODE_REFERENCE_CARVE_OUTS = {
    # This module's own defining file: it is what the grep gate below IS,
    # and its docstrings/messages need the literal token to explain and
    # assert about the retirement. Scanning itself would be circular.
    "tests/test_ide_overlay_retirement.py",
    # Keeps test_s4c_prd_d7_vscode_client_request_reads_as_declined, which
    # legitimately verifies PRD \u00a7D7 still records the vscode-crucible.py
    # client request as DECLINED (Sandesh #1370) \u2014 untouched by this CR's
    # Non-goals; deleting or obfuscating it would drop real coverage of a
    # DIFFERENT CR's acceptance criterion.
    "tests/test_client_verb_sweep.py",
    # Keeps test_dn_plan_review_records_the_vscode_client_ask_as_declined,
    # the same kind of legitimate historical-record citation, against the
    # DN's Scripts/AXI-wave section \u2014 also untouched by this CR.
    "tests/test_generator_role_contract.py",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _iter_scan_files():
    """Yield (path, repo-relative-posix-path) for every regular file under
    \u00a7S3 AC1's scan roots, excluding compiled caches (the AC's own carve-out)
    and the documented VSCODE_REFERENCE_CARVE_OUTS above."""
    for root_name in SCAN_ROOTS:
        root = REPO_ROOT / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts:
                continue
            if path.suffix in (".pyc", ".pyo"):
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel in VSCODE_REFERENCE_CARVE_OUTS:
                continue
            yield path, rel


def _heading_section(path: Path, heading_prefix: str) -> str:
    """The text of the first heading line starting with `heading_prefix`
    (e.g. ``"### D4"``) up to (not including) the next heading of the same
    or a shallower level. Empty string if the heading is not found."""
    lines = _read(path).splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(heading_prefix)), None)
    if start is None:
        return ""
    level_match = re.match(r"^(#+)", lines[start])
    level = len(level_match.group(1)) if level_match else len(heading_prefix)
    end = len(lines)
    for i in range(start + 1, len(lines)):
        match = re.match(r"^(#+)\s", lines[i])
        if match and len(match.group(1)) <= level:
            end = i
            break
    return "\n".join(lines[start:end])


class VscodeReferenceGrepGateS3Test(unittest.TestCase):
    """\u00a7S3 AC1 \u2014 zero vscode references under skills-src/, generator/,
    modelb_axi/ and tests/ (compiled caches excluded) \u2014 grep gate."""

    def test_zero_vscode_references_across_owned_surfaces(self):
        needle = "vsc" + "ode"  # never written contiguously in this file's own source
        offenders = []
        for path, rel in _iter_scan_files():
            try:
                content = _read(path)
            except OSError:
                continue
            for lineno, line in enumerate(content.splitlines(), 1):
                if needle in line.lower():
                    offenders.append(f"{rel}:{lineno}: {line.strip()}")
        self.assertEqual(
            offenders, [],
            f"expected zero (case-insensitive) references to the retired IDE "
            f"stack under {SCAN_ROOTS} (compiled caches and the documented "
            f"carve-outs {sorted(VSCODE_REFERENCE_CARVE_OUTS)} excluded); "
            f"found:\n  " + "\n  ".join(offenders),
        )


class SkillsSrcBundleCensusS3Test(unittest.TestCase):
    """\u00a7S3 AC2 \u2014 skills-src/ carries 12 bundles and CRUCIBLE-HANDOVER.md
    documents 6 imported ones."""

    def test_skills_src_carries_exactly_twelve_skill_md_bundles(self):
        bundles = sorted(
            p.name for p in SKILLS_SRC_DIR.iterdir()
            if p.is_dir() and (p / "SKILL.md").is_file()
        )
        # POSITIVE/EXACT -- 13 today, 12 once the retired bundle is deleted.
        self.assertEqual(
            len(bundles), 12,
            f"skills-src/ must carry exactly 12 SKILL.md bundles once the "
            f"retired IDE-stack bundle is deleted outright; found "
            f"{len(bundles)}: {bundles}",
        )
        self.assertNotIn(
            "crucible-report-" + "vscode", bundles,
            "the retired IDE-stack crucible-report bundle must not exist "
            "under skills-src/",
        )

    def test_handover_doc_documents_six_imported_bundles(self):
        self.assertTrue(HANDOVER_MD.is_file(), f"{HANDOVER_MD} must exist")
        content = _read(HANDOVER_MD)
        # POSITIVE -- the roster header drops from "7 of 8" to "6 of 8".
        self.assertIn(
            "Bundles imported (6 of 8)", content,
            "CRUCIBLE-HANDOVER.md's roster header must read "
            "'Bundles imported (6 of 8)' once the retired bundle drops out",
        )
        # NEGATIVE -- the retired bundle is gone from the bullet list.
        self.assertNotIn(
            "crucible-report-" + "vscode", content,
            "CRUCIBLE-HANDOVER.md must no longer list the retired IDE-stack "
            "bundle among the imported ones",
        )
        # bound -- exactly 6 bundle bullets remain (crucible-register + the
        # five surviving crucible-report-<stack> bundles).
        bullet_count = len(re.findall(r"^- `crucible-", content, re.MULTILINE))
        self.assertEqual(
            bullet_count, 6,
            f"expected exactly 6 bundle bullets in CRUCIBLE-HANDOVER.md; "
            f"found {bullet_count}",
        )


class GeneratorBespokeCensusS3Test(unittest.TestCase):
    """\u00a7S3 AC3 \u2014 the bespoke list names only definitions that still exist:
    electronics \u00d74 and inbox-analyst. This is also the CR-MDB-008
    exclusion-list correction \u00a7S4 AC1 names (the exclusion list lives in
    generator/build.py's own docstring and in
    tests/test_agent_generator.py's BESPOKE_AGENT_NAMES, migrated
    separately in this cycle's report)."""

    def test_build_py_docstring_states_five_bespoke_defs_and_zero_vscode(self):
        self.assertTrue(BUILD_PY.is_file(), f"{BUILD_PY} must exist")
        content = _read(BUILD_PY)
        self.assertIn(
            "5 bespoke defs", content,
            "generator/build.py's docstring must state '5 bespoke defs' "
            "(electronics x4, inbox-analyst) once the retired IDE stack's "
            "four names drop out",
        )
        self.assertNotIn(
            "vsc" + "ode", content.lower(),
            "generator/build.py must carry zero references to the retired "
            "IDE stack",
        )
        self.assertIn(
            "electronics", content,
            "generator/build.py's bespoke docstring must still name "
            "electronics x4",
        )
        self.assertIn(
            "inbox-analyst", content,
            "generator/build.py's bespoke docstring must still name "
            "inbox-analyst",
        )


class AgentsMdBundleEnumerationS3Test(unittest.TestCase):
    """\u00a7S3 AC \u2014 AGENTS.md's crucible-report-* enumeration and bundle count
    are corrected."""

    def test_agents_md_states_twelve_bundles_and_zero_vscode(self):
        self.assertTrue(AGENTS_MD.is_file(), f"{AGENTS_MD} must exist")
        content = _read(AGENTS_MD)
        self.assertIn(
            "12 skill bundles", content,
            "AGENTS.md's skills-src/ row must state '12 skill bundles' once "
            "the retired IDE-stack bundle drops out",
        )
        self.assertNotIn(
            "vsc" + "ode", content.lower(),
            "AGENTS.md must carry zero references to the retired IDE stack",
        )


class ScaffoldRejectsRetiredStackS3Test(unittest.TestCase):
    """\u00a7S3 AC4 \u2014 `modelb-axi init --stacks vscode` is rejected with a
    message naming the supported stacks."""

    def setUp(self):
        self._home = tempfile.mkdtemp(prefix="modelb-axi-ide-retire-home-")
        self._target = tempfile.mkdtemp(prefix="modelb-axi-ide-retire-target-")

    def tearDown(self):
        shutil.rmtree(self._home, ignore_errors=True)
        shutil.rmtree(self._target, ignore_errors=True)

    def _run_init(self, stacks_value: str):
        hooks_scripts_dir = Path(self._home) / ".agents" / "hooks" / "scripts"
        (Path(self._home) / "install.toml").write_text(
            '[install]\n'
            'version = "0.1.0"\n'
            'harnesses = ["claude-code"]\n'
            'asset_root = "/tmp/does-not-matter-for-this-test"\n'
            f'hooks_scripts_dir = "{hooks_scripts_dir}"\n'
            "\n"
            "[deps]\n"
            'uv = "present"\n'
            "\n"
            "[files]\n",
            encoding="utf-8",
        )
        env = dict(os.environ)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
        cmd = [
            sys.executable, "-m", "modelb_axi", "--yes", "init",
            "--name", "X", "--token", "x", "--acronym", "XX",
            "--mode", "solo", "--repo-shape", "standalone",
            "--stacks", stacks_value, "--owner", "tester",
            "--target", self._target, "--dry-run",
            "--modelb-home", self._home,
        ]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20, env=env)

    def test_init_stacks_vscode_is_rejected_naming_supported_stacks(self):
        retired_stack = "vsc" + "ode"
        result = self._run_init(retired_stack)
        # POSITIVE/EXACT -- the retired stack id is REFUSED (ScaffoldError
        # path, exit 2), never silently accepted (today it is: exit 0).
        self.assertEqual(
            result.returncode, 2,
            f"`init --stacks {retired_stack}` must be REJECTED once the IDE "
            f"stack retires (exit 2, the ScaffoldError path); got "
            f"rc={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        self.assertIn(
            f"unknown stack id(s): {retired_stack}", result.stderr,
            f"the rejection must name the offending stack id by name; "
            f"stderr={result.stderr!r}",
        )
        valid_line = next(
            (ln for ln in result.stderr.splitlines() if "valid stacks:" in ln), "",
        )
        self.assertTrue(
            valid_line,
            f"the rejection must name the SUPPORTED stacks (a 'valid "
            f"stacks:' line); stderr={result.stderr!r}",
        )
        self.assertNotIn(
            retired_stack, valid_line,
            f"the supported-stacks list must not include the retired IDE "
            f"stack: {valid_line!r}",
        )
        for supported in ("arduino", "bun", "python", "quarkus", "rust"):
            self.assertIn(
                supported, valid_line,
                f"the supported-stacks list must still include {supported!r}: "
                f"{valid_line!r}",
            )

    def test_init_stacks_python_is_still_accepted(self):
        """NEGATIVE control \u2014 proves the rejection above is about the
        retired stack specifically, not a broken --stacks parser."""
        result = self._run_init("python")
        self.assertEqual(
            result.returncode, 0,
            f"`init --stacks python` must still succeed; got "
            f"rc={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )


class DnD4SupersededMarkerS3Test(unittest.TestCase):
    """\u00a7S3 AC5 \u2014 DN \u00a7D4 carries a superseded marker citing the 2026-09-22
    ruling."""

    def test_dn_d4_carries_superseded_marker_citing_the_2026_09_22_ruling(self):
        self.assertTrue(DN_MULTI_HARNESS.is_file(), f"{DN_MULTI_HARNESS} must exist")
        section = _heading_section(DN_MULTI_HARNESS, "### D4")
        self.assertTrue(
            section,
            f"no '### D4' heading found in {DN_MULTI_HARNESS}",
        )
        self.assertRegex(
            section, r"(?i)supersed",
            f"DN \u00a7D4 must carry a superseded marker; section text:\n{section}",
        )
        self.assertIn(
            "2026-09-22", section,
            f"DN \u00a7D4's superseded marker must cite the 2026-09-22 ruling; "
            f"section text:\n{section}",
        )


class PrdD6BespokeCensusS4Test(unittest.TestCase):
    """\u00a7S4 AC1 (PRD half) \u2014 PRD \u00a7D6 no longer states the retired IDE stack
    exists as a current bespoke agent set, and cites the two rulings."""

    def test_prd_d6_drops_vscode_and_cites_both_rulings(self):
        self.assertTrue(PRD.is_file(), f"{PRD} must exist")
        section = _heading_section(PRD, "### D6")
        self.assertTrue(section, f"no '### D6' heading found in {PRD}")
        self.assertNotRegex(
            section.lower(), r"vsc" + r"ode",
            f"PRD \u00a7D6 must no longer name the retired IDE stack as a current "
            f"bespoke agent set:\n{section}",
        )
        self.assertIn(
            "2026-09-16", section,
            f"PRD \u00a7D6 must cite the 2026-09-16 rust ruling:\n{section}",
        )
        self.assertIn(
            "2026-09-22", section,
            f"PRD \u00a7D6 must cite the 2026-09-22 IDE-stack ruling:\n{section}",
        )


class DnPlanReviewBespokeCensusS4Test(unittest.TestCase):
    """\u00a7S4 AC1 (DN half) \u2014 docs/research/DN-rationalization-plan-review.md
    no longer states rust agents are never generated (or that the retired
    IDE stack exists), and cites the two rulings. Section-scoped and
    tolerant of exact wording (does not dictate the fix), matching this
    suite's existing DN-citation-gate convention
    (tests/test_generator_role_contract.py's GeneratorRoleContractDNTest)."""

    def test_generated_bespoke_line_no_longer_lists_the_retired_stack(self):
        self.assertTrue(DN_PLAN_REVIEW.is_file(), f"{DN_PLAN_REVIEW} must exist")
        lines = _read(DN_PLAN_REVIEW).splitlines()
        target_idx = next(
            (i for i, line in enumerate(lines) if "Bespoke kept" in line), None,
        )
        if target_idx is None:
            self.fail(
                f"expected a 'Bespoke kept' line in {DN_PLAN_REVIEW} to anchor "
                f"this gate against"
            )
        window = "\n".join(lines[max(0, target_idx - 1): target_idx + 3])
        self.assertNotRegex(
            window.lower(), r"vsc" + r"ode.{0,4}(x4|\u00d74)",
            f"the 'Bespoke kept' line must no longer list the retired IDE "
            f"stack x4 as a current bespoke set:\n{window}",
        )
        self.assertTrue(
            "2026-09-16" in window and "2026-09-22" in window,
            f"the corrected 'Bespoke kept' line (or its immediate "
            f"annotation) must cite both the 2026-09-16 rust ruling and "
            f"the 2026-09-22 IDE-stack ruling:\n{window}",
        )


class QueueFooterRetirementRecordS4Test(unittest.TestCase):
    """\u00a7S4 AC2 \u2014 the queue footer records the vscode retirement and its
    reason.

    Measured at RED time: docs/changes/README.md's '## Footer notes'
    section already carries a 2026-09-22 entry recording the retirement and
    its category-error reason (filed ahead of this cycle's implementation,
    per this repo's queue-footer convention of recording decisions as they
    are ratified). This test may therefore legitimately PASS already --
    that is still correct RED-phase behaviour for a content assertion that
    happens to already be true of the live tree (the same allowance this
    suite's own test_agent_generator.py module docstring documents for its
    grep/diff gates), not a test bug. It is written and kept in the suite
    regardless, so a future regression (the entry being edited out, or the
    reason dropped) is caught."""

    def test_footer_notes_record_the_retirement_and_its_reason(self):
        self.assertTrue(QUEUE_README.is_file(), f"{QUEUE_README} must exist")
        text = _read(QUEUE_README)
        footer_start = text.find("## Footer notes")
        self.assertGreaterEqual(
            footer_start, 0,
            f"expected a '## Footer notes' section in {QUEUE_README}",
        )
        footer = text[footer_start:]
        self.assertRegex(
            footer.lower(), r"vsc" + r"ode",
            "the queue footer must record the retired IDE stack's "
            "retirement",
        )
        self.assertRegex(
            footer, r"(?i)retir",
            "the queue footer's entry must record it as a RETIREMENT, not "
            "just an incidental mention",
        )
        self.assertTrue(
            re.search(r"(?i)not a stack", footer) or re.search(r"(?i)editor", footer),
            "the queue footer must record the RETIREMENT REASON (an "
            "IDE/editor is not a stack), not just the bare fact of "
            "retirement",
        )


if __name__ == "__main__":
    unittest.main()
