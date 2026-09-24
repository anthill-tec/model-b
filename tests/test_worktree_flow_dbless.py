"""RED-phase tests for CR-MDB-028 cycle C1 (§S1 §S2 §S4 §S5 §S6).

`scripts/worktree-flow.py` drops its `schedule_db` backend: the five
DB-coupled verbs (`cs`, `show`, `reconcile`, `next`, `progress`) are REMOVED
(not stubbed) and their absence is documented with the Crucible verb that
replaces each; the optional DB mirrors inside `start`/`finish`/`abort` go
too (amendment 1). `scripts/schedule_db.py` itself STAYS shipped for its
remaining consumer (§S5) with a corrected banner, and
`scripts/rust-code-health.py`'s docstring teaches the explicit two-step that
replaces `worktree-flow.py cs` (§S6).

Everything here runs against THIS repo's `scripts/` (never a deployed copy),
stdlib + subprocess only; the one Model B import is the repo's own TOON
codec (`modelb_axi.toon`) for decoding the `status` envelope. The five
TRANSITIONAL-banner regexes are imported from `tests.test_tooling_adoption`
rather than copied, so the banner contract has exactly one definition.

Expected against the pre-GREEN tree: §S1/§S2/§S4/§S5-banner/§S6 FAIL; the
DB-less `status` guard (§S1 regression) passes today and must keep passing.
"""

import ast
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.test_tooling_adoption import (  # noqa: E402
    DO_NOT_EXTEND_PATTERN,
    PLAN_STATE_STORAGE_PATTERN,
    SUCCESSOR_PATTERN,
    TRANSITIONAL_PATTERN,
    TRIGGER_RELEASE_PATTERN,
)

SCRIPTS_DIR = REPO_ROOT / "scripts"
WORKTREE_FLOW = SCRIPTS_DIR / "worktree-flow.py"
SCHEDULE_DB = SCRIPTS_DIR / "schedule_db.py"
RUST_CODE_HEALTH = SCRIPTS_DIR / "rust-code-health.py"

#: §S1 AC: `worktree-flow --help` lists EXACTLY these.
SURVIVING_VERBS = frozenset({"start", "status", "sync", "finish", "abort"})

#: §S1/§S2/§S4: removed verb -> (regex naming its Crucible replacement,
#: human description of that replacement for the failure message).
REMOVED_VERBS = {
    "cs": (
        re.compile(r"\bcr-plan\b[\s\S]{0,400}?\bledger\s+assign\b|"
                   r"\bledger\s+assign\b[\s\S]{0,400}?\bcr-plan\b"),
        "`cr-plan` + `ledger assign` (the two-step, §S6)",
    ),
    "show": (
        re.compile(r"\bqueue\b|crucible[^\n]{0,80}\bstatus\b", re.IGNORECASE),
        "Crucible `queue` / `status`",
    ),
    "reconcile": (
        re.compile(r"\bno\s+(?:\w+\s+){0,3}(?:replacement|successor)\b",
                   re.IGNORECASE),
        "'no replacement' (the verb dies with the DB)",
    ),
    "next": (
        re.compile(r"crucible(?:\.py)?[^\n]{0,80}\bnext\b", re.IGNORECASE),
        "`python-crucible.py next`",
    ),
    "progress": (
        re.compile(r"\bcheckpoint\b|\bcycle-done\b", re.IGNORECASE),
        "Crucible `checkpoint` / `cycle-done`",
    ),
}

#: §S1 source tokens that must be gone (amendment 1: including the mirrors).
FORBIDDEN_SOURCE_TOKENS = ("import schedule_db", "_sdb_con", "_sdb")

#: §S5: the banner's first lines; the five regexes must still match here.
SCHEDULE_DB_HEADER_LINES = 15
#: §S6: the docstring window under test.
RUST_CODE_HEALTH_DOCSTRING_LINES = 40

#: argparse renders the sub-command roster as `{a,b,c}` in usage/help.
_CHOICES_LISTING = re.compile(r"\{([A-Za-z0-9_\-]+(?:,[A-Za-z0-9_\-]+)*)\}")


def _run_wf(*argv, cwd=REPO_ROOT, timeout=60):
    return subprocess.run(
        [sys.executable, str(WORKTREE_FLOW), *argv],
        cwd=cwd, capture_output=True, text=True, timeout=timeout,
        stdin=subprocess.DEVNULL,
    )


def _dbless_project(parent: Path) -> Path:
    """A git repo with no `.wf-schedule.db` (and no `.nai-schedule.db`)."""
    project_dir = parent / "dbless"
    project_dir.mkdir()
    git = ["git", "-c", "user.name=CR-MDB-028",
           "-c", "user.email=cr-mdb-028@example.invalid"]
    for argv in (["init", "-q", "-b", "main", "."],
                 ["commit", "-q", "--allow-empty", "-m", "init"]):
        subprocess.run([*git, *argv], cwd=project_dir, check=True,
                       capture_output=True, timeout=60)
    return project_dir


def _help_verbs(help_text: str):
    """The sub-command set argparse advertises, or None if no `{…}` roster."""
    match = _CHOICES_LISTING.search(help_text)
    if match is None:
        return None
    return frozenset(match.group(1).split(","))


def _head_lines(path: Path, count: int) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    return "\n".join(text.splitlines()[:count])


def _assert_verb_removed(case: unittest.TestCase, verb: str):
    """Shared assertion: `verb` is gone AND its replacement is documented
    somewhere the operator will see it — the failed invocation itself,
    `<verb> --help`, or the top-level `--help`."""
    pattern, replacement = REMOVED_VERBS[verb]
    with tempfile.TemporaryDirectory(prefix="mdb028-wf-") as tmp:
        project_dir = _dbless_project(Path(tmp))
        bare = _run_wf(verb, "--project-dir", str(project_dir))
        verb_help = _run_wf(verb, "--help")
    top_help = _run_wf("--help")
    case.assertNotEqual(
        bare.returncode, 0,
        f"`worktree-flow.py {verb}` must no longer be a working verb "
        f"(non-zero exit); it exited 0 with stdout:\n{bare.stdout[:600]}",
    )
    surfaces = "\n".join(
        r.stdout + "\n" + r.stderr for r in (bare, verb_help, top_help)
    )
    case.assertRegex(
        surfaces, pattern,
        f"the removal of `{verb}` must be documented with its Crucible "
        f"replacement {replacement} — none of the failed invocation, "
        f"`{verb} --help` or `--help` names it. Failed invocation "
        f"(exit={bare.returncode}) stderr:\n{bare.stderr[:600]}",
    )


class WorktreeFlowDblessS1Test(unittest.TestCase):
    """§S1 — the `schedule_db` backend is gone from worktree-flow.py."""

    def _source(self) -> str:
        self.assertTrue(
            WORKTREE_FLOW.is_file(),
            f"{WORKTREE_FLOW.relative_to(REPO_ROOT)} must exist; every "
            "assertion in this module targets it",
        )
        return WORKTREE_FLOW.read_text(encoding="utf-8")

    def test_s1_ast_has_no_schedule_db_import(self):
        tree = ast.parse(self._source(), filename=str(WORKTREE_FLOW))
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders.extend(
                    f"line {node.lineno}: import {alias.name}"
                    for alias in node.names
                    if alias.name.split(".")[0] == "schedule_db"
                )
            elif (isinstance(node, ast.ImportFrom)
                  and (node.module or "").split(".")[0] == "schedule_db"):
                offenders.append(f"line {node.lineno}: from {node.module} import …")
        self.assertEqual(
            offenders, [],
            "§S1: worktree-flow.py must not import schedule_db in any form "
            "(AST scan); found:\n" + "\n".join(offenders),
        )

    def test_s1_source_carries_no_sdb_tokens(self):
        source = self._source()
        found = {}
        for token in FORBIDDEN_SOURCE_TOKENS:
            lines = [
                f"{n}: {line.strip()}"
                for n, line in enumerate(source.splitlines(), 1)
                if token in line
            ]
            if lines:
                found[token] = lines
        self.assertEqual(
            found, {},
            "§S1 (+ amendment 1): no `import schedule_db`, `_sdb` or "
            "`_sdb_con` reference may remain — including the optional "
            "mirrors in start/finish/abort. Found:\n"
            + "\n".join(f"  {t}:\n    " + "\n    ".join(ls)
                        for t, ls in found.items()),
        )

    def test_s1_help_exits_zero_and_lists_exactly_the_five_git_verbs(self):
        result = _run_wf("--help")
        self.assertEqual(
            result.returncode, 0,
            f"`worktree-flow.py --help` must exit 0, got {result.returncode}; "
            f"stderr:\n{result.stderr}",
        )
        verbs = _help_verbs(result.stdout)
        self.assertIsNotNone(
            verbs,
            "could not find argparse's `{a,b,c}` sub-command roster in "
            f"--help output:\n{result.stdout[:800]}",
        )
        verbs = verbs or frozenset()
        self.assertEqual(
            verbs, SURVIVING_VERBS,
            "§S1 AC: `worktree-flow --help` must list EXACTLY "
            f"{sorted(SURVIVING_VERBS)}; extra={sorted(verbs - SURVIVING_VERBS)} "
            f"missing={sorted(SURVIVING_VERBS - verbs)}",
        )

    def test_s1_help_no_longer_advertises_any_removed_verb(self):
        result = _run_wf("--help")
        verbs = _help_verbs(result.stdout) or frozenset()
        still_listed = sorted(verbs & frozenset(REMOVED_VERBS))
        self.assertEqual(
            still_listed, [],
            "§S1/§S2/§S4: the DB-coupled verbs must be REMOVED, not kept as "
            f"stubs; --help still lists {still_listed}",
        )

    def test_s1_cs_is_removed_and_names_cr_plan_plus_ledger_assign(self):
        _assert_verb_removed(self, "cs")

    def test_s1_show_is_removed_and_names_queue_or_status(self):
        _assert_verb_removed(self, "show")

    def test_s1_reconcile_is_removed_and_recorded_as_having_no_replacement(self):
        _assert_verb_removed(self, "reconcile")

    def test_s1_status_on_a_dbless_project_still_emits_an_ok_envelope(self):
        """Regression guard (AC: git-derived verbs unchanged in DB-less
        behaviour). Passes before GREEN and must keep passing after."""
        from modelb_axi import toon

        with tempfile.TemporaryDirectory(prefix="mdb028-wf-") as tmp:
            project_dir = _dbless_project(Path(tmp))
            self.assertFalse((project_dir / ".wf-schedule.db").exists())
            result = _run_wf("status", "--project-dir", str(project_dir))
        self.assertEqual(
            result.returncode, 0,
            f"`status` on a DB-less project must exit 0, got "
            f"{result.returncode}; stderr:\n{result.stderr}",
        )
        try:
            decoded = toon.decode(result.stdout)
        except Exception as exc:
            self.fail(
                f"`status` stdout must decode with modelb_axi.toon "
                f"({type(exc).__name__}: {exc}); stdout was:\n{result.stdout}"
            )
        self.assertIn(
            "axi", decoded,
            f"`status` stdout must carry a top-level `axi` envelope, "
            f"keys={list(decoded)}",
        )
        axi = decoded["axi"]
        self.assertEqual(axi.get("verb"), "status",
                         f"axi.verb must be 'status', got {axi.get('verb')!r}")
        self.assertIs(axi.get("ok"), True,
                      f"axi.ok must be True (bool), got {axi.get('ok')!r}")
        # Machine channel is stdout (the envelope above); the human board
        # goes to stderr. Pinned here after the retired envelope test.
        self.assertNotEqual(
            result.stderr.strip(), "",
            "`status` must print the human board to stderr alongside the "
            "stdout envelope; stderr was empty",
        )


class WorktreeFlowDblessS2Test(unittest.TestCase):
    """§S2 — `next` is removed (not delegated); callers use Crucible's."""

    def test_s2_next_is_removed_and_names_python_crucible_next(self):
        _assert_verb_removed(self, "next")


class WorktreeFlowDblessS4Test(unittest.TestCase):
    """§S4 — `progress` is removed; Crucible's checkpoint/cycle-done carry it."""

    def test_s4_progress_is_removed_and_names_checkpoint_or_cycle_done(self):
        _assert_verb_removed(self, "progress")


class WorktreeFlowDblessS5Test(unittest.TestCase):
    """§S5 — schedule_db.py STAYS shipped; its banner is corrected, not removed."""

    def _header(self) -> str:
        self.assertTrue(
            SCHEDULE_DB.is_file(),
            "§S5: scripts/schedule_db.py must STILL be present — its removal "
            "is explicitly NOT part of CR-MDB-028",
        )
        return _head_lines(SCHEDULE_DB, SCHEDULE_DB_HEADER_LINES)

    def test_s5_banner_keeps_the_five_transitional_facts(self):
        header = self._header()
        for label, pattern in (
            ("TRANSITIONAL", TRANSITIONAL_PATTERN),
            ("Crucible … owns", SUCCESSOR_PATTERN),
            ("plan … state/storage", PLAN_STATE_STORAGE_PATTERN),
            ("0.2.0", TRIGGER_RELEASE_PATTERN),
            ("must not be extended", DO_NOT_EXTEND_PATTERN),
        ):
            with self.subTest(fact=label):
                self.assertRegex(
                    header, pattern,
                    f"§S5 / amendment 4: the rewritten banner must still "
                    f"satisfy test_tooling_adoption's '{label}' regex "
                    f"(first {SCHEDULE_DB_HEADER_LINES} lines):\n{header}",
                )

    def test_s5_banner_names_crucible_queue_as_model_b_successor(self):
        header = self._header()
        self.assertRegex(
            header, re.compile(r"\bModel\s*B\b"),
            f"§S5: the banner must scope the succession to MODEL B (it is no "
            f"longer Model B's backend); header:\n{header}",
        )
        self.assertRegex(
            header, re.compile(r"Crucible[^\n]{0,120}\bqueue\b|\bqueue\b[^\n]{0,120}Crucible",
                               re.IGNORECASE),
            f"§S5: the banner must name Crucible's QUEUE as Model B's "
            f"successor; header:\n{header}",
        )

    def test_s5_banner_states_the_module_persists_for_other_consumers(self):
        header = self._header()
        self.assertRegex(
            header,
            re.compile(r"\bother\s+consumers?\b|\bremains?\b|\bpersists?\b|"
                       r"\bstill\s+(?:ships|shipped|deployed|published)\b|"
                       r"\bremaining\s+consumers?\b", re.IGNORECASE),
            f"§S5: the banner must state the module itself persists for other "
            f"consumers (NAI holds live state on it); header:\n{header}",
        )

    def test_s5_banner_implies_no_removal_date(self):
        header = self._header()
        self.assertNotRegex(
            header, re.compile(r"\bunreleased\b|\bis\s+deleted\b|\bdeleted\b",
                               re.IGNORECASE),
            f"§S5: the banner must not present 0.2.0 as unreleased nor promise "
            f"the file 'is deleted' — retirement is gated on remaining "
            f"consumers migrating, not this CR; header:\n{header}",
        )

    def test_s5_banner_no_longer_claims_worktree_flow_imports_it(self):
        header = self._header()
        self.assertNotRegex(
            header, re.compile(r"imported\s+as\s+a\s+library\s+by[\s\S]{0,80}?worktree-flow",
                               re.IGNORECASE),
            f"§S5 (follows from §S1): the banner may not claim worktree-flow.py "
            f"still imports this module; header:\n{header}",
        )


class WorktreeFlowDblessS6Test(unittest.TestCase):
    """§S6 — rust-code-health.py's docstring teaches the explicit two-step."""

    def _docstring(self) -> str:
        self.assertTrue(RUST_CODE_HEALTH.is_file(),
                        "scripts/rust-code-health.py must exist")
        return _head_lines(RUST_CODE_HEALTH, RUST_CODE_HEALTH_DOCSTRING_LINES)

    def test_s6_docstring_no_longer_cites_worktree_flow_cs(self):
        doc = self._docstring()
        self.assertNotRegex(
            doc, re.compile(r"worktree-flow(?:\.py)?\s+cs\b"),
            f"§S6 AC: rust-code-health.py's docstring must no longer cite "
            f"`worktree-flow.py cs` (first {RUST_CODE_HEALTH_DOCSTRING_LINES} "
            f"lines):\n{doc}",
        )

    def test_s6_docstring_teaches_cr_plan_then_ledger_assign(self):
        doc = self._docstring()
        self.assertRegex(
            doc, re.compile(r"\bcr-plan\b"),
            f"§S6 AC: the docstring must name `cr-plan` as the step that files "
            f"the CR:\n{doc}",
        )
        self.assertRegex(
            doc, re.compile(r"\bledger\s+assign\b"),
            f"§S6 AC: the docstring must name `ledger assign` as the step that "
            f"stamps the findings:\n{doc}",
        )


if __name__ == "__main__":
    unittest.main()
