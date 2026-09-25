"""Worktree isolation on Pi — the workflow text (CR-MDB-039 §S2, DN-multi-harness §D19).

Contract: ``docs/changes/CR-MDB-039-worktree-isolation-on-pi.md`` §S2 and its acceptance criteria.
C1 shipped ``pi-package/extensions/worktree.ts``: ``modelb_worktree_enter`` confines the
orchestrator's writes (``WF_WORKTREE_ROOT`` in its process) and ``modelb_worktree_exit`` lifts it;
a workspace provider routes each dispatch into its CR's worktree. The orchestrator's session cwd
never changes. §S2 makes the workflow text say exactly that.

Class map:

- ``WorktreeFlowEnterExitHintTest`` — the real ``scripts/worktree-flow.py`` on a ``/tmp`` fixture
  repository. ``start`` (a plain-output verb: its human lines go to stdout) prints ONE line naming
  ``modelb_worktree_enter`` with the worktree path and no ``→ enter it: cd <wt>`` line. ``finish``
  (an AXI-converted verb: stdout is the TOON envelope, stderr the human channel) reminds on stderr
  to call ``modelb_worktree_exit`` and its stdout still decodes as one envelope. ``abort`` (plain
  output, stdout) reminds on stdout.
- ``WorkingDirectoryInstructionDetectorTest`` / ``WorkingDirectoryInstructionGateTest`` — no
  sentence in a shipped surface instructs making the worktree "your/the session's working
  directory" or says an agent is dispatched/run "with the worktree as its working directory",
  except in a sentence that also names ``modelb_worktree_enter`` (the effect of entering).
- ``SubAgentProcedureEnforcementTest`` — ``sub-agent-procedure.md`` says what enforces the
  boundary: the ``block-write-outside-worktree`` hook, active while the orchestrator has entered
  the worktree (``modelb_worktree_enter``); "HARD-ENFORCED" survives only in that bullet; the
  ``git rev-parse --show-toplevel`` check stays in the Worktree boundary section.
- ``OrchestrationWorktreeToolsTest`` — ``orchestration-common.md`` and ``orchestration-track.md``
  each name ``modelb_worktree_enter`` with ``start`` and ``modelb_worktree_exit`` with ``finish``
  and with ``abort``; neither says the session's working directory goes "back to" the main tree
  nor points at "the ``cd <path>`` it prints". The two files, read together, state the §D19
  session model (one Pi session per orchestrator, launched however the user likes, Mainline
  following the Tracks through Crucible and Sandesh) and the read-by-path note (``.worktrees/`` is
  gitignored; read by explicit path).
- ``TmuxOptionalDetectorTest`` / ``TmuxOptionalGateTest`` — the tmux rule (below).
- ``WorktreeLayoutContractToolsTest`` — ``contracts/worktree-layout.md`` lists the extension in its
  consumers table (naming ``modelb_worktree_enter``), its stated consumer count matches the table,
  and its "Permission scope" bullet names ``modelb_worktree_enter``.
- ``HarnessToolGateAcceptsModelBToolsTest`` — a regression PIN: the two harness-tool gates
  (CR-MDB-020 §S4's ratchet counter in ``tests/test_client_path_anchoring.py`` and CR-MDB-031's
  ``HARNESS_TOOL_RE``) do not count the Model B package's tool names (§S2: a Model B surface, not
  a harness tool — DN §D18 still bars harness tools).

Units and sentences. Markdown is cut into UNITS — a paragraph, a list item, a table row or a heading
— whose lines are joined with single spaces (so a phrase wrapped across lines still matches). A
unit is cut into sentences at ``.``/``!``/``?`` followed by whitespace and a character that is not
a lower-case letter (so "e.g. a" does not split).

The tmux rule (§D19: tmux is "a recommendation … never a requirement"). ``tmux`` may be absent
from every shipped surface. Any sentence that names it (any case) must also carry an optional
qualifier — ``optional``/``optionally``, ``recommend…``, ``not (a) require…`` or ``never (a)
require…``. A sentence that names tmux without one reads as an instruction and fails.

Surfaces. "Shipped" = what the installer and ``init`` deliver: every file inside a skill bundle
(``skills-src/<bundle>/**``, so ``skills-src/README.md`` and ``CRUCIBLE-HANDOVER.md`` — never
deployed — are out), ``generator/templates/*`` and ``contracts/*.md``.

Sandbox: fixture repositories live under ``tempfile.mkdtemp``; nothing reads or writes the real
home. Stdlib only.
"""

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests._helpers import REPO_ROOT, decode_envelope, md_section, read_text
from tests.test_client_path_anchoring import _count_tools
from tests.test_harness_neutral_skills import HARNESS_TOOL_RE
from tests.test_worktree_flow_dbless import _dbless_project, _run_wf
from tests.test_worktree_layout_and_bundles import _git_c3, _registered_worktrees

ENTER_TOOL = "modelb_worktree_enter"
EXIT_TOOL = "modelb_worktree_exit"
HOOK_NAME = "block-write-outside-worktree"
WORKTREE_EXTENSION = "pi-package/extensions/worktree.ts"

MODEL_B_REFS = REPO_ROOT / "skills-src" / "model-b" / "references"
ORCHESTRATION_COMMON = MODEL_B_REFS / "orchestration-common.md"
ORCHESTRATION_TRACK = MODEL_B_REFS / "orchestration-track.md"
SUB_AGENT_PROCEDURE = MODEL_B_REFS / "sub-agent-procedure.md"
ORCHESTRATION_FILES = (ORCHESTRATION_COMMON, ORCHESTRATION_TRACK)
WORKTREE_LAYOUT_MD = REPO_ROOT / "contracts" / "worktree-layout.md"

#: The fixture CR every worktree-flow run uses.
FIXTURE_CR = "CR-XYZ-039"

# ------------------------------------------------------------------ patterns ----

#: The retired ``start`` hint (``→ enter it: cd <wt_dir>``).
BARE_CD_HINT_RE = re.compile(r"\benter\s+it:\s*cd\b")
#: "make the worktree your session's working directory" / "the session's working directory".
SESSION_WORKDIR_RE = re.compile(r"\b(?:your|the)\s+session['\u2019]?s\s+working\s+directory\b",
                                re.IGNORECASE)
#: "dispatch(ed) … with the worktree as its working directory" (any verb before it).
WORKTREE_AS_WORKDIR_RE = re.compile(r"\bwith\s+the\s+worktree\s+as\s+its\s+working\s+directory\b",
                                    re.IGNORECASE)
TMUX_RE = re.compile(r"\btmux\b", re.IGNORECASE)
TMUX_QUALIFIER_RE = re.compile(
    r"\boptional(?:ly)?\b|\brecommend\w*|\b(?:not|never)\s+(?:a\s+)?require\w*", re.IGNORECASE)
#: §D19 "one Pi session per orchestrator" (or "each orchestrator … its own Pi session").
ONE_SESSION_RE = re.compile(
    r"\bone\s+Pi\s+session\s+per\s+orchestrator\b"
    r"|\beach\s+orchestrator\b[^.]{0,60}\bown\s+Pi\s+session\b", re.IGNORECASE)
#: §D19 "launched however the user likes".
LAUNCH_FREEDOM_RE = re.compile(
    r"\blaunch\w*\b[^.]{0,60}\b(?:however|any\s+way|as\s+(?:you|the\s+user)\s+(?:likes?|prefers?))\b"
    r"|\bhowever\b[^.]{0,60}\blaunch\w*", re.IGNORECASE)
FOLLOW_RE = re.compile(r"\b(?:follow\w*|view\w*|watch\w*)\b", re.IGNORECASE)
GITIGNORED_RE = re.compile(r"\bgit-?ignore[ds]?\b|\.gitignore\b", re.IGNORECASE)
BY_PATH_RE = re.compile(r"\bpaths?\b", re.IGNORECASE)
#: The session's working directory going "back to" the main/integration tree (the cwd never moves).
WORKDIR_BACK_RE = re.compile(r"\bworking\s+directory\s+back\s+to\b", re.IGNORECASE)
#: "the `cd <path>` it prints" — the retired hint the track file pointed at.
CD_IT_PRINTS_RE = re.compile(r"`cd\s+<path>`\s+it\s+prints", re.IGNORECASE)
#: The "N files carry the string" sentence of the layout contract.
CONSUMER_COUNT_RE = re.compile(r"\b(\w+)\s+files\s+carry\s+the\s+string\b", re.IGNORECASE)
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10}

# ------------------------------------------------------------------ text units ----

_UNIT_START_RE = re.compile(r"(?:[-*+]|\d+\.)\s|\|")


def markdown_units(text: str) -> list:
    """Paragraphs, list items, table rows and headings of ``text``, each joined to one line."""
    units, current = [], []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or _UNIT_START_RE.match(line):
            if current:
                units.append(" ".join(current))
                current = []
            if line.startswith("#"):
                units.append(line)
                continue
        if line:
            current.append(line)
    if current:
        units.append(" ".join(current))
    return units


def sentences(text: str) -> list:
    """Every sentence of every unit of ``text``."""
    return [s for unit in markdown_units(text)
            for s in re.split(r"(?<=[.!?])\s+(?=[^a-z])", unit) if s.strip()]


def working_directory_violations(text: str) -> list:
    """Sentences that make the worktree the session's working directory, or dispatch an agent with
    the worktree as its working directory, without naming ``modelb_worktree_enter``."""
    return [s for s in sentences(text)
            if (SESSION_WORKDIR_RE.search(s) or WORKTREE_AS_WORKDIR_RE.search(s))
            and ENTER_TOOL not in s]


def tmux_violations(text: str) -> list:
    """Sentences that name tmux without an optional/recommendation qualifier."""
    return [s for s in sentences(text) if TMUX_RE.search(s) and not TMUX_QUALIFIER_RE.search(s)]


def shipped_surface_texts():
    """``(repo-relative path, text)`` for every shipped surface (see the module docstring)."""
    files = []
    for bundle in sorted(p for p in (REPO_ROOT / "skills-src").iterdir() if p.is_dir()):
        files.extend(sorted(f for f in bundle.rglob("*")
                            if f.is_file() and "__pycache__" not in f.parts))
    files.extend(sorted(f for f in (REPO_ROOT / "generator" / "templates").iterdir() if f.is_file()))
    files.extend(sorted((REPO_ROOT / "contracts").glob("*.md")))
    out = []
    for path in files:
        try:
            out.append((str(path.relative_to(REPO_ROOT)), read_text(path)))
        except UnicodeDecodeError:
            continue
    return out


def _orchestration_pair_text() -> str:
    return "\n\n".join(read_text(p) for p in ORCHESTRATION_FILES)


# =================================================================== worktree-flow ====

class WorktreeFlowEnterExitHintTest(unittest.TestCase):
    """AC — ``worktree-flow.py start`` names ``modelb_worktree_enter`` with the worktree path;
    ``finish`` and ``abort`` remind the orchestrator to exit."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mdb-039-c2-wf-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.main = _dbless_project(self.tmp)  # a git repo on `main` with one commit
        # `finish` merges into the gitflow develop branch; the fixture's is `main`. The merge
        # needs an identity, and a nested worktree must not dirty the integration tree.
        for key, value in (("gitflow.branch.develop", "main"),
                           ("user.name", "CR-MDB-039-C2"),
                           ("user.email", "cr-mdb-039@example.invalid"),
                           ("core.hooksPath", "/dev/null")):
            _git_c3(self.main, "config", key, value)
        exclude = self.main / ".git" / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a", encoding="utf-8") as fh:
            fh.write(".worktrees/\n")
        self.wt_dir = self.main / ".worktrees" / FIXTURE_CR

    def _start(self):
        result = _run_wf("start", "--cr", FIXTURE_CR, "--base", "main",
                         "--project-dir", str(self.main), cwd=self.tmp)
        self.assertEqual(result.returncode, 0,
                         f"precondition: start exits 0: stdout={result.stdout!r} stderr={result.stderr!r}")
        self.assertIn(str(self.wt_dir), _registered_worktrees(self.main),
                      "precondition: start registers <main>/.worktrees/<cr>")
        return result

    def test_start_prints_exactly_one_line_naming_modelb_worktree_enter_with_the_worktree_path(self):
        result = self._start()
        lines = [ln for ln in result.stdout.splitlines() if ENTER_TOOL in ln]
        self.assertEqual(len(lines), 1,
                         f"§S2: `start` (plain output, stdout) must print exactly one line naming "
                         f"`{ENTER_TOOL}`; stdout={result.stdout!r}")
        self.assertIn(str(self.wt_dir), lines[0],
                      f"§S2: the enter instruction must name the worktree path {self.wt_dir}; "
                      f"got {lines[0]!r}")

    def test_start_prints_no_bare_cd_enter_hint_on_either_channel(self):
        result = self._start()
        for channel, text in (("stdout", result.stdout), ("stderr", result.stderr)):
            with self.subTest(channel=channel):
                self.assertIsNone(BARE_CD_HINT_RE.search(text),
                                  f"§S2: the `→ enter it: cd <wt_dir>` line is replaced by the "
                                  f"`{ENTER_TOOL}` instruction; {channel}={text!r}")
                self.assertNotIn(f"cd {self.wt_dir}", text,
                                 f"§S2: `start` must not instruct `cd {self.wt_dir}` (a Pi session's "
                                 f"cwd is fixed at launch); {channel}={text!r}")

    def test_finish_reminds_on_stderr_to_exit_with_modelb_worktree_exit_and_keeps_a_pure_envelope(self):
        self._start()
        (self.wt_dir / "work.txt").write_text("done\n", encoding="utf-8")
        for argv in (("add", "-A"), ("commit", "-q", "-m", "work")):
            done = _git_c3(self.wt_dir, *argv)
            self.assertEqual(done.returncode, 0, f"precondition: git {argv}: {done.stderr}")
        result = _run_wf("finish", "--cr", FIXTURE_CR, "--project-dir", str(self.main), cwd=self.tmp)
        self.assertEqual(result.returncode, 0,
                         f"precondition: finish exits 0: stdout={result.stdout!r} stderr={result.stderr!r}")
        reminders = [ln for ln in result.stderr.splitlines() if EXIT_TOOL in ln]
        self.assertEqual(len(reminders), 1,
                         f"§S2: `finish` (AXI verb: stderr is the human channel) must print exactly "
                         f"one reminder naming `{EXIT_TOOL}`; stderr={result.stderr!r}")
        envelope = decode_envelope(result.stdout).get("axi", {})
        self.assertEqual((envelope.get("verb"), envelope.get("ok"), envelope.get("cr")),
                         ("finish", True, FIXTURE_CR),
                         f"stdout stays one decodable finish envelope; stdout={result.stdout!r}")

    def test_abort_reminds_on_stdout_to_exit_with_modelb_worktree_exit(self):
        self._start()
        result = _run_wf("abort", "--cr", FIXTURE_CR, "--reason", "fixture",
                         "--project-dir", str(self.main), cwd=self.tmp)
        self.assertEqual(result.returncode, 0,
                         f"precondition: abort exits 0: stdout={result.stdout!r} stderr={result.stderr!r}")
        self.assertNotIn(str(self.wt_dir), _registered_worktrees(self.main),
                         "precondition: abort removed the worktree")
        reminders = [ln for ln in result.stdout.splitlines() if EXIT_TOOL in ln]
        self.assertEqual(len(reminders), 1,
                         f"§S2: `abort` (plain output, stdout) must print exactly one reminder "
                         f"naming `{EXIT_TOOL}`; stdout={result.stdout!r}")


# =================================================================== the working-directory gate ====

class WorkingDirectoryInstructionDetectorTest(unittest.TestCase):
    """Detector fixtures — the gate bites on the retired instructions and spares the effect of
    entering with ``modelb_worktree_enter``."""

    def test_bites_on_making_the_worktree_your_sessions_working_directory(self):
        text = "- Right after `start`, make the worktree your session's working directory.\n"
        self.assertEqual(len(working_directory_violations(text)), 1)

    def test_bites_on_the_sessions_working_directory(self):
        text = "The worktree becomes the session's working directory.\n"
        self.assertEqual(len(working_directory_violations(text)), 1)

    def test_bites_on_dispatching_with_the_worktree_as_its_working_directory_across_a_line_wrap(self):
        text = "A sub-agent dispatched\n  with the worktree as its working directory runs there.\n"
        self.assertEqual(len(working_directory_violations(text)), 1)

    def test_a_tool_named_in_another_sentence_does_not_spare_the_violation(self):
        text = ("- Dispatch every sub-agent with the worktree as its working directory. "
                "Call `modelb_worktree_enter` first.\n")
        found = working_directory_violations(text)
        self.assertEqual(len(found), 1, found)
        self.assertNotIn(ENTER_TOOL, found[0])

    def test_spares_the_effect_of_entering_with_the_tool(self):
        text = ("- After `start`, enter it with `modelb_worktree_enter`: every agent you dispatch then "
                "runs with the worktree as its working directory.\n")
        self.assertEqual(working_directory_violations(text), [])

    def test_spares_unrelated_working_directory_text(self):
        text = "| `cwd` | The working directory of the session making the call. |\n## Working Directory\n"
        self.assertEqual(working_directory_violations(text), [])


class WorkingDirectoryInstructionGateTest(unittest.TestCase):
    """AC — no shipped skill, template or contract instructs making the worktree the session's
    working directory, or dispatching with the worktree as its working directory, except as the
    effect of entering it with ``modelb_worktree_enter``."""

    def test_no_shipped_surface_carries_a_working_directory_instruction(self):
        hits = [f"{rel}: {s[:160]}" for rel, text in shipped_surface_texts()
                for s in working_directory_violations(text)]
        self.assertEqual(hits, [], "§S2: these sentences instruct a working directory a Pi session "
                                   "cannot take; say what entering with `modelb_worktree_enter` "
                                   "does instead:\n" + "\n".join(hits))


# =================================================================== sub-agent procedure ====

class SubAgentProcedureEnforcementTest(unittest.TestCase):
    """AC — ``sub-agent-procedure.md`` says what enforces the boundary: the hook, active while the
    orchestrator has entered the worktree."""

    @classmethod
    def setUpClass(cls):
        cls.section = md_section(read_text(SUB_AGENT_PROCEDURE), "## Worktree boundary")

    def test_the_worktree_boundary_section_exists(self):
        self.assertTrue(self.section.strip(), "sub-agent-procedure.md keeps its Worktree boundary section")

    def test_a_boundary_bullet_names_the_hook_and_the_orchestrator_entering_the_worktree(self):
        units = [u for u in markdown_units(self.section)
                 if HOOK_NAME in u and ENTER_TOOL in u and re.search(r"\borchestrator\b", u, re.I)]
        self.assertEqual(len(units), 1,
                         f"§S2: exactly one Worktree-boundary bullet must say what enforces the "
                         f"boundary — `{HOOK_NAME}`, active while the orchestrator has entered the "
                         f"worktree with `{ENTER_TOOL}`; found {len(units)}")

    def test_hard_enforced_survives_only_beside_the_hook_and_the_enter_tool(self):
        claims = [u for u in markdown_units(self.section) if "HARD-ENFORCED" in u]
        bad = [u[:160] for u in claims if HOOK_NAME not in u or ENTER_TOOL not in u]
        self.assertEqual(bad, [], f"§S2: 'HARD-ENFORCED' may stand only in the bullet naming "
                                  f"`{HOOK_NAME}` and `{ENTER_TOOL}` (what holds, and when): {bad}")

    def test_the_show_toplevel_check_stays_in_the_worktree_boundary_section(self):
        # Regression pin (§D19 consequence 1): the per-dispatch check stays as the agent's own
        # first check. It passes today; it fails if the §S2 rewrite drops the check.
        self.assertIn("git rev-parse --show-toplevel", self.section,
                      "§S2: the `git rev-parse --show-toplevel` check stays as the check an agent "
                      "makes before its first write")

    def test_detector_hard_enforced_rule_bites_without_the_tool_and_spares_with_it(self):
        bare = "- **This is HARD-ENFORCED.** The `block-write-outside-worktree` hook blocks writes.\n"
        named = ("- **This is HARD-ENFORCED** while the orchestrator has entered the worktree "
                 "(`modelb_worktree_enter`): the `block-write-outside-worktree` hook blocks writes.\n")
        self.assertEqual([u for u in markdown_units(bare)
                          if "HARD-ENFORCED" in u and ENTER_TOOL not in u], [bare.strip()])
        self.assertEqual([u for u in markdown_units(named)
                          if "HARD-ENFORCED" in u and ENTER_TOOL not in u], [])


# =================================================================== orchestration skills ====

class OrchestrationWorktreeToolsTest(unittest.TestCase):
    """AC — the orchestration skills name the enter/exit tools where they are load-bearing, state the
    §D19 session model and the read-by-path note, and drop the cwd instructions."""

    def _units(self, path: Path) -> list:
        return markdown_units(read_text(path))

    def test_each_file_names_modelb_worktree_enter_with_start(self):
        for path in ORCHESTRATION_FILES:
            with self.subTest(file=path.name):
                units = [u for u in self._units(path) if ENTER_TOOL in u and re.search(r"\bstart\b", u)]
                self.assertTrue(units, f"§S2: {path.name} must name `{ENTER_TOOL}` in the step that "
                                       f"follows `start` (one bullet naming both)")

    def test_each_file_names_modelb_worktree_exit_with_finish(self):
        for path in ORCHESTRATION_FILES:
            with self.subTest(file=path.name):
                units = [u for u in self._units(path) if EXIT_TOOL in u and re.search(r"\bfinish\b", u)]
                self.assertTrue(units, f"§S2: {path.name} must name `{EXIT_TOOL}` beside `finish` "
                                       f"(exit after finish)")

    def test_each_file_names_modelb_worktree_exit_with_abort(self):
        for path in ORCHESTRATION_FILES:
            with self.subTest(file=path.name):
                units = [u for u in self._units(path) if EXIT_TOOL in u and re.search(r"\babort\b", u)]
                self.assertTrue(units, f"§S2: {path.name} must name `{EXIT_TOOL}` beside `abort` "
                                       f"(exit after abort)")

    def test_no_file_moves_the_session_working_directory_or_points_at_the_printed_cd(self):
        for path in ORCHESTRATION_FILES:
            with self.subTest(file=path.name):
                text = " ".join(self._units(path))
                self.assertEqual((WORKDIR_BACK_RE.findall(text), CD_IT_PRINTS_RE.findall(text)), ([], []),
                                 f"§S2/§D19: the orchestrator's session cwd never changes — no "
                                 f"'working directory back to' the main tree, no 'the `cd <path>` it "
                                 f"prints' in {path.name}")

    def test_the_pair_states_one_pi_session_per_orchestrator(self):
        hits = [s for s in sentences(_orchestration_pair_text()) if ONE_SESSION_RE.search(s)]
        self.assertTrue(hits, "§S2/§D19: the orchestration skills must state one Pi session per "
                              "orchestrator")

    def test_the_pair_states_a_session_is_launched_however_the_user_likes(self):
        hits = [s for s in sentences(_orchestration_pair_text()) if LAUNCH_FREEDOM_RE.search(s)]
        self.assertTrue(hits, "§S2/§D19: the orchestration skills must say a session is launched "
                              "however the user likes")

    def test_the_pair_states_mainline_follows_the_tracks_through_crucible_and_sandesh(self):
        hits = [s for s in sentences(_orchestration_pair_text())
                if re.search(r"\bMainline\b", s) and re.search(r"\bTracks?\b", s)
                and "Crucible" in s and "Sandesh" in s and FOLLOW_RE.search(s)]
        self.assertTrue(hits, "§S2/§D19: one sentence must say Mainline follows the Tracks through "
                              "Crucible and Sandesh")

    def test_the_pair_states_worktree_files_are_read_by_explicit_path(self):
        hits = [u for u in markdown_units(_orchestration_pair_text())
                if ".worktrees/" in u and GITIGNORED_RE.search(u) and BY_PATH_RE.search(u)]
        self.assertTrue(hits, "§S2/§D19: one bullet must say `.worktrees/` is gitignored (a "
                              "gitignore-aware listing does not show it) and its files are read by "
                              "explicit path")

    def test_detector_session_model_patterns_bite_on_the_d19_wording_and_spare_others(self):
        d19 = ("One Pi session per orchestrator, launched however the user likes. Mainline follows "
               "the Tracks through Crucible and Sandesh, never through a shared process.")
        other = "Solo (one orchestrator, no worktrees) runs in a single session. Mainline reads Crucible."
        self.assertEqual([bool(ONE_SESSION_RE.search(d19)), bool(LAUNCH_FREEDOM_RE.search(d19)),
                          bool(FOLLOW_RE.search(d19))], [True, True, True])
        self.assertEqual([bool(ONE_SESSION_RE.search(other)), bool(LAUNCH_FREEDOM_RE.search(other))],
                         [False, False])


# =================================================================== tmux ====

class TmuxOptionalDetectorTest(unittest.TestCase):
    """Detector fixtures for the tmux rule (module docstring)."""

    def test_bites_on_tmux_as_an_instruction(self):
        self.assertEqual(len(tmux_violations("- Launch each Track in its own tmux pane.\n")), 1)

    def test_bites_regardless_of_case(self):
        self.assertEqual(len(tmux_violations("Use Tmux windows for the Tracks.\n")), 1)

    def test_spares_tmux_as_a_recommendation_never_a_requirement(self):
        text = ("Panes of a multiplexer such as tmux are a recommendation, never a requirement. "
                "Running the Tracks in tmux is optional.\n")
        self.assertEqual(tmux_violations(text), [])

    def test_spares_text_without_tmux(self):
        self.assertEqual(tmux_violations("One Pi session per orchestrator.\n"), [])


class TmuxOptionalGateTest(unittest.TestCase):
    """§D19 — tmux is a recommendation, never a requirement, on every shipped surface."""

    def test_no_shipped_surface_names_tmux_without_an_optional_qualifier(self):
        hits = [f"{rel}: {s[:160]}" for rel, text in shipped_surface_texts() for s in tmux_violations(text)]
        self.assertEqual(hits, [], "§D19: tmux may be named only as optional/recommended:\n"
                                   + "\n".join(hits))


# =================================================================== layout contract ====

class WorktreeLayoutContractToolsTest(unittest.TestCase):
    """AC — ``contracts/worktree-layout.md`` records the tools as a consumer of the layout and
    restates "Permission scope" in their terms."""

    @classmethod
    def setUpClass(cls):
        cls.text = read_text(WORKTREE_LAYOUT_MD)
        cls.consumers = md_section(cls.text, "## Consumers")

    def _rows(self) -> list:
        return [u for u in markdown_units(self.consumers)
                if u.startswith("| `") and not u.startswith("|---")]

    def test_consumers_table_lists_the_worktree_extension_naming_the_enter_tool(self):
        rows = [r for r in self._rows() if r.startswith(f"| `{WORKTREE_EXTENSION}` |")]
        self.assertEqual(len(rows), 1, f"§S2: the consumers table must list `{WORKTREE_EXTENSION}` "
                                       f"exactly once; rows={[r[:60] for r in self._rows()]}")
        self.assertIn(ENTER_TOOL, rows[0], f"§S2: the extension's row must name `{ENTER_TOOL}`")

    def test_the_stated_consumer_count_matches_the_table(self):
        match = CONSUMER_COUNT_RE.search(self.consumers)
        self.assertIsNotNone(match, "the contract states how many files carry the string")
        assert match is not None  # narrowed by the assertion above
        stated = NUMBER_WORDS.get(match.group(1).lower(), match.group(1))
        rows = self._rows()
        self.assertEqual(stated, len(rows),
                         f"the stated count ({match.group(1)!r}) must equal the table's {len(rows)} rows")
        self.assertIn(WORKTREE_EXTENSION, " ".join(rows), "§S2: the extension is one of them")

    def test_permission_scope_bullet_names_the_enter_tool(self):
        bullets = [u for u in markdown_units(self.text) if u.startswith("- **Permission scope.**")]
        self.assertEqual(len(bullets), 1, "the contract keeps one 'Permission scope' bullet")
        self.assertIn(ENTER_TOOL, bullets[0],
                      f"§S2: 'Permission scope' must be restated in terms of entering the worktree "
                      f"with `{ENTER_TOOL}` and the dispatch routing; got {bullets[0][:200]!r}")


# =================================================================== harness-tool gates ====

class HarnessToolGateAcceptsModelBToolsTest(unittest.TestCase):
    """Regression PIN (§S2 naming rule; DN §D18) — the Model B package's tools are a Model B
    surface, not a harness tool, so neither harness-tool gate counts them. Passes today; fails if
    either gate's vocabulary grows to include them."""

    SAMPLE = (f"After `start`, enter it with `{ENTER_TOOL}` and, after `finish`, call "
              f"`{EXIT_TOOL}`; the {ENTER_TOOL} tool confines your writes.")

    def test_the_ratchet_counter_counts_no_model_b_tool(self):
        self.assertEqual(_count_tools(self.SAMPLE), {})

    def test_the_harness_tool_pattern_matches_no_model_b_tool(self):
        self.assertEqual(HARNESS_TOOL_RE.findall(self.SAMPLE), [])

    def test_the_gates_still_bite_on_a_harness_tool_beside_them(self):
        bitten = self.SAMPLE + " Or use EnterWorktree."
        self.assertEqual(HARNESS_TOOL_RE.findall(bitten), ["EnterWorktree"])


if __name__ == "__main__":
    unittest.main()
