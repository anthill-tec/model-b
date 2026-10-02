"""The Crucible board holds the queue and the execution state; the skills say so, and no shipped
surface names the queue README as a step (CR-MDB-048 §S1; PRD D3.2, rulings 1–6 of 2026-10-02).

Contract: ``docs/changes/CR-MDB-048-board-holds-the-queue.md`` §S1 and its acceptance criteria.

Class map — one class per acceptance criterion of §S1:

- ``QueueVerbsSectionTest`` — the ``crucible`` skill's queue-verbs section: ``queue`` and
  ``next`` as read verbs without ``--agent``; the six write verbs with their required flags and
  ``--agent`` on the same line; ``cr-plan`` exits 2 and never guesses; ``cr-depends`` and
  ``wave-sequence`` replace the whole set; ``--track``; ``plan-file --release`` as the same
  registration; ``queue-file`` never run.
- ``CrAuthoringBoardFilingTest`` — ``cr-authoring`` files a CR on the board under its kept
  heading, allocates ids, supersedes/voids, re-posts a title, records a first release, covers
  Crucible absent / unregistered / an older project, routes the rest, closes a board-absent CR by
  the ``**Status:**`` flip alone, and lists ``docs/changes/`` as specs only.
- ``ModelBSkillBoardTest`` — ``model-b`` § 4 items 2 and 5 and its description; the role table's
  ontology term ``CR queue`` unchanged.
- ``OrchestrationMainlineBoardTest`` / ``OrchestrationCommonBoardTest`` — the board as the
  queue's home in the two orchestration references.
- ``JavaOrchestrationTemplateBoardTest`` — the memory template's ``docs/changes/`` and its
  pre-merge close-out step.
- ``QueueReadmeReachTest`` — no shipped skill, reference, template, stack file or memory template
  names ``queue-file`` (except as never run), ``docs/changes/README.md``, a queue row, the Notes
  log or the queue README as a step — except the older-project cases of ``bootstrap``,
  ``shutdown`` and ``cr-authoring``.
- ``ReachDetectorOnSyntheticTextTest`` — the reach detector proven on synthetic text.

§S3 — Model B's own records (one class per record):

- ``ModelBReadmeFrozenHistoryTest`` — Model B's ``docs/changes/README.md`` keeps all its content
  (every line of it as it stood at C1's head, ``README_BASE``, in order) under a header — before
  its ``## Queue`` — that calls it read-only history frozen at CR-MDB-048's merge, says the queue
  and the execution state are on the Crucible board, and warns that ``queue-file`` is never run
  against it, since it would replace the board's queue with these rows.
- ``ModelBAgentsMdBoardTest`` — Model B's ``AGENTS.md``: the ``docs/changes/`` row, the
  Important-files line and the architecture flow say the README is frozen history and the board
  holds the queue (the flow no longer renders a queue README); it carries the Design contract,
  Evidence base and Ontology lines from the README's header.
- ``DnD20SetupSectionTest`` — DN-multi-harness §D20 names ``AGENTS.md``'s Setup section, not the
  queue README's setup task, for the user's direnv steps.
- ``ModelBRecordsDetectorsOnSyntheticTextTest`` — the §S3 detectors proven on synthetic text.

``bootstrap`` / ``shutdown``'s not-registered pointer is pinned where it always was, in
``tests.test_bootstrap_shutdown_registry.UnregisteredProjectTest`` (migrated there).

Rules are checked phrase-level within ONE bullet, numbered item, table row or paragraph (a
"unit"), on normalised text (backticks and ``*`` dropped, whitespace collapsed, lower-cased);
never whole sentences, never line numbers.

The write verbs' required flags were read from the installed client's own ``--help``
(``python-crucible.py <verb> --help``, 2026-10-02): ``cr-plan --cr --title [--release]
[--wave]`` (each undeclared → lists and exits 2), ``cr-depends --cr [--on]`` (the WHOLE set),
``wave-sequence --release --wave --crs [--track]`` (the WHOLE ordered list),
``cr-supersede --cr --by``, ``cr-void --cr --reason``, ``release-propose --label --target``;
``queue`` and ``next [--track]`` take no ``--agent``; ``plan-file --release`` registers the CR
in the queue by the same call.

Hermetic: reads repo files only (and, for the README's kept content, the repo's own history
through ``git show``). Stdlib only.
"""

import re
import subprocess
import unittest

from tests._helpers import REPO_ROOT, read_text, split_frontmatter
from tests.test_bootstrap_shutdown_registry import normalise

CRUCIBLE_SKILL = "skills-src/crucible/SKILL.md"
CR_AUTHORING = "skills-src/cr-authoring/SKILL.md"
MODEL_B_SKILL = "skills-src/model-b/SKILL.md"
MAINLINE_REF = "skills-src/model-b/references/orchestration-mainline.md"
COMMON_REF = "skills-src/model-b/references/orchestration-common.md"
JAVA_TEMPLATE = "skills-src/memory-templates/java-orchestration.md"
BOOTSTRAP = "skills-src/bootstrap/SKILL.md"
SHUTDOWN = "skills-src/shutdown/SKILL.md"

#: The CR-042 triage headings §S1 keeps verbatim while their bodies change.
CR_AUTHORING_QUEUE_HEADING = "The CR queue — structure only (queue idiom, 2026-07-20)"
MAINLINE_OWNERSHIP_HEADING = "Ownership — queue, CR-gen, scheduling"
MAINLINE_FILING_HEADING = "Filing/assigning a CR — COMMIT docs FIRST, schedule write LAST"

#: Each write verb's required flags, as the installed client's ``--help`` states them.
WRITE_VERB_FLAGS = {
    "cr-plan": ("--cr", "--title", "--release", "--wave"),
    "cr-depends": ("--cr", "--on"),
    "wave-sequence": ("--release", "--wave", "--crs"),
    "cr-supersede": ("--cr", "--by"),
    "cr-void": ("--cr", "--reason"),
    "release-propose": ("--label", "--target"),
}
READ_VERBS = ("queue", "next")
#: The close-out verb itself — never the ``check-cr-close`` gate's name.
CR_CLOSE = r"(?<![\w-])cr-close(?![\w-])"

#: The shipped surfaces the reach AC covers: every skill bundle, reference and memory template
#: under ``skills-src/``, and the generator's templates and stack files.
REACH_ROOTS = ("skills-src", "generator/templates", "generator/stacks")
REACH_SUFFIXES = {".md", ".tmpl", ".toml"}

#: The files whose older-project case may still name the README (AC: "except bootstrap's and
#: shutdown's older-project case and cr-authoring's older-project filing").
OLDER_PROJECT_EXEMPT = frozenset({BOOTSTRAP, SHUTDOWN, CR_AUTHORING})
#: How a unit says it is about an older project (one scaffolded before the board held the queue).
OLDER_PROJECT_MARKER = re.compile(r"scaffolded before|older project|predates")

#: Naming the queue README (or what only it carried) as a step, on normalised text.
README_STEP_PATTERNS = (
    ("docs/changes/README.md", re.compile(r"docs/changes/readme\.md")),
    ("the queue README", re.compile(r"\bqueue readme\b")),
    ("a queue row", re.compile(r"\bqueue rows?\b")),
    ("the Notes log", re.compile(r"\bnotes log\b|\bfooter notes\b|\bdated footer\b")),
    ("the README's setup task", re.compile(r"\breadme'?s setup tasks?\b")),
)
QUEUE_FILE = re.compile(r"(?<![\w-])queue-file(?![\w-])")
NEVER_RUN = re.compile(r"\b(?:never|not)\s+(?:be\s+|to\s+be\s+)?run\b")
#: A sentence carrying one of these does not name the README as a step — it negates or retires it.
NEGATION = re.compile(
    r"\b(?:never|not|no|nor|without|instead of|rather than|don't|do not|no longer|retired|"
    r"replaces?|replaced)\b")

#: Clauses: a negation reaches only its own clause — "do the queue README's setup task, and
#: never read the board as idle" still names the README as a step.
_CLAUSE_SPLIT = re.compile(r"(?<=[.!?])\s+|[,:;()\u2014]|\s(?:and|but|then)\s")
_ITEM_START = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_CODE_SPAN = re.compile(r"`([^`]+)`")


# ------------------------------------------------------------------ helpers ----

def units(text: str) -> list[str]:
    """``text`` split into raw units — one per bullet / numbered item (with its continuation
    lines), table row, heading, fenced-code line or paragraph."""
    out: list[str] = []
    cur: list[str] = []
    fenced = False

    def flush():
        if cur:
            out.append("\n".join(cur))
            cur.clear()

    for line in text.splitlines():
        if _FENCE.match(line):
            flush()
            fenced = not fenced
            continue
        if fenced:
            if line.strip():
                out.append(line)
            continue
        stripped = line.strip()
        if not stripped:
            flush()
        elif _HEADING.match(line) or stripped.startswith("|"):
            flush()
            out.append(line)
        elif _ITEM_START.match(line):
            flush()
            cur.append(line)
        else:
            cur.append(line)
    flush()
    return out


def norm_units(text: str) -> list[str]:
    return [normalise(u) for u in units(text)]


def section(text: str, heading: str) -> str:
    """The body under the heading (any level) whose title is exactly ``heading``, up to the
    next heading of the same or a higher level; ``""`` when there is none."""
    lines = text.splitlines()
    fenced = False
    start: int | None = None
    level = 0
    for i, line in enumerate(lines):
        if _FENCE.match(line):
            fenced = not fenced
        m = None if fenced else _HEADING.match(line)
        if start is None:
            if m and m.group(2) == heading:
                start, level = i + 1, len(m.group(1))
        elif m and len(m.group(1)) <= level:
            return "\n".join(lines[start:i])
    return "" if start is None else "\n".join(lines[start:])


def section_matching(text: str, pattern: str) -> str:
    """The body under the first heading whose normalised title matches ``pattern``."""
    for line in text.splitlines():
        m = _HEADING.match(line)
        if m and re.search(pattern, normalise(m.group(2))):
            return section(text, m.group(2))
    return ""


def units_with(text: str, *patterns: str) -> list[str]:
    """The normalised units of ``text`` matching EVERY regex in ``patterns``."""
    return [u for u in norm_units(text) if all(re.search(p, u) for p in patterns)]


def code_spans(line: str) -> list[str]:
    return _CODE_SPAN.findall(line)


def _flag(flag: str) -> re.Pattern:
    return re.compile(r"(?<![\w-])" + re.escape(flag) + r"(?![\w-])")


def _verb(verb: str) -> re.Pattern:
    return re.compile(r"(?:^|[\s>])" + re.escape(verb) + r"(?![\w-])")


def invocation_lines(text: str, verb: str) -> list[tuple[str, str]]:
    """``(line, span)`` for every code span in ``text`` that invokes ``verb``."""
    return [(line, span) for line in text.splitlines() for span in code_spans(line)
            if _verb(verb).search(span)]


def reach_findings(rel: str, text: str) -> list[str]:
    """Where ``text`` (the file ``rel``) names ``queue-file`` other than as never run, or names
    the queue README, a queue row, the Notes log or the README's setup task as a step — one
    finding per offending clause. A clause that negates or retires it is not a finding; in
    an ``OLDER_PROJECT_EXEMPT`` file, a unit about an older project is not either."""
    out = []
    for unit in norm_units(text):
        if QUEUE_FILE.search(unit) and not NEVER_RUN.search(unit):
            out.append(f"{rel}: queue-file not as never run: {unit[:160]!r}")
        if rel in OLDER_PROJECT_EXEMPT and OLDER_PROJECT_MARKER.search(unit):
            continue
        for clause in _CLAUSE_SPLIT.split(unit):
            if NEGATION.search(clause):
                continue
            for what, rx in README_STEP_PATTERNS:
                if rx.search(clause):
                    out.append(f"{rel}: names {what} as a step: {clause.strip()[:160]!r}")
                    break
    return out


def shipped_surfaces() -> list[str]:
    files = []
    for root in REACH_ROOTS:
        for path in sorted((REPO_ROOT / root).rglob("*")):
            if path.is_file() and path.suffix in REACH_SUFFIXES:
                files.append(path.relative_to(REPO_ROOT).as_posix())
    return files


# ------------------------------------------------------------- crucible skill ----

class QueueVerbsSectionTest(unittest.TestCase):
    """AC 1 — the ``crucible`` skill has a queue-verbs section, as the installed client's
    ``--help`` states the verbs."""

    def setUp(self):
        self.text = read_text(REPO_ROOT / CRUCIBLE_SKILL)
        self.sec = section_matching(self.text, r"\bqueue[- ]verbs?\b")

    def _require_section(self):
        self.assertNotEqual(self.sec.strip(), "",
                            f"{CRUCIBLE_SKILL}: no section headed 'queue verbs'")

    def test_queue_and_next_are_read_verbs_without_agent(self):
        self._require_section()
        hits = units_with(self.sec, r"(?<![\w-])queue(?![\w-])", r"(?<![\w-])next(?![\w-])",
                          r"\bread\b", r"\b(?:no|without|never)\b[^.]{0,40}--agent")
        self.assertTrue(hits, "no unit states queue and next as read verbs without --agent")
        with_agent = [span for verb in READ_VERBS for _line, span in
                      invocation_lines(self.sec, verb) if "--agent" in span]
        self.assertEqual(with_agent, [], "a read verb is shown with --agent")

    def test_next_answers_next_hold_or_drained_and_needs_track_with_several_tracks(self):
        self._require_section()
        raw = [u for u in units(self.sec) if re.search(r"`next\b", u)
               and all(w in u for w in ("NEXT", "HOLD", "DRAINED"))]
        self.assertTrue(raw, "no unit says next answers NEXT, HOLD or DRAINED")
        track = units_with(self.sec, r"(?<![\w-])next(?![\w-])", r"--track",
                           r"more than one track")
        self.assertTrue(track, "no unit says next needs --track once more than one track is declared")

    def test_each_write_verb_shows_its_required_flags_with_agent_on_the_same_line(self):
        self._require_section()
        missing = []
        for verb, flags in WRITE_VERB_FLAGS.items():
            ok = [span for line, span in invocation_lines(self.sec, verb)
                  if all(_flag(f).search(span) for f in flags) and "--agent" in line]
            if not ok:
                missing.append(f"{verb} {' '.join(flags)} --agent")
        self.assertEqual(missing, [], "write verbs not shown with their required flags + --agent")

    def test_write_verbs_are_the_orchestrators_only(self):
        self._require_section()
        self.assertTrue(units_with(self.sec, r"\bwrite verbs?\b", r"\borchestrator"),
                        "no unit says the write verbs are the orchestrator's only")

    def test_cr_plan_exits_2_and_never_guesses(self):
        self._require_section()
        self.assertTrue(units_with(self.sec, r"cr-plan", r"\bexits? (?:with )?(?:code )?2\b",
                                   r"\bnever guess"),
                        "no unit says cr-plan exits 2 and never guesses")

    def test_cr_depends_and_wave_sequence_replace_the_whole_set(self):
        self._require_section()
        hits = units_with(self.sec, r"cr-depends", r"wave-sequence", r"replaces? the whole set",
                          r"re-?sends?[^.]{0,80}\b(?:full|whole) order")
        self.assertTrue(hits, "no unit says cr-depends and wave-sequence replace the whole set "
                              "(adding a CR re-sends the wave's full order)")

    def test_wave_sequence_track_assigns_a_lane(self):
        self._require_section()
        self.assertTrue(units_with(self.sec, r"wave-sequence", r"--track", r"\blane\b"),
                        "no unit says wave-sequence --track assigns the wave's CRs to a lane")

    def test_plan_file_release_is_the_same_registration_as_cr_plan(self):
        self._require_section()
        self.assertTrue(units_with(self.sec, r"plan-file[^.]{0,20}--release", r"cr-plan",
                                   r"same registration"),
                        "no unit says plan-file --release is the same registration as cr-plan")

    def test_queue_file_is_never_run_because_it_replaces_the_whole_queue(self):
        self._require_section()
        self.assertTrue(units_with(self.sec, r"queue-file", r"\bnever (?:be )?run\b",
                                   r"replaces? the whole[^.]{0,40}queue"),
                        "no unit says queue-file replaces the whole board queue and is never run")
        flagged = [span for _line, span in invocation_lines(self.text, "queue-file")
                   if re.search(r"--\w", span)]
        self.assertEqual(flagged, [], "the skill shows a queue-file invocation")


# --------------------------------------------------------------- cr-authoring ----

class CrAuthoringBoardFilingTest(unittest.TestCase):
    """AC 2 — ``cr-authoring`` files a CR on the board under its kept heading."""

    def setUp(self):
        self.text = read_text(REPO_ROOT / CR_AUTHORING)
        self.queue = section(self.text, CR_AUTHORING_QUEUE_HEADING)

    def test_the_kept_heading_stays_verbatim(self):
        self.assertNotEqual(self.queue.strip(), "",
                            f"the heading '{CR_AUTHORING_QUEUE_HEADING}' is gone or empty")

    def test_filing_is_spec_then_cr_plan_cr_depends_wave_sequence_with_the_full_order(self):
        hits = [u for u in units_with(self.queue, r"\bspec\b", r"cr-plan", r"cr-depends",
                                      r"wave-sequence", r"\b(?:full|whole) order")
                if u.index("spec") < u.index("cr-plan") < u.index("cr-depends")
                < u.index("wave-sequence")]
        self.assertTrue(hits, "no unit files a CR as spec → cr-plan → cr-depends → "
                              "wave-sequence (the wave's full order)")

    def test_ids_are_allocated_from_the_boards_queue_and_the_spec_files(self):
        hits = units_with(self.text, r"\ballocat", r"(?<![\w-])queue(?![\w-])", r"\bboard\b",
                          r"spec files")
        self.assertTrue(hits, "no unit allocates the next id from the board's queue and the spec files")

    def test_supersede_and_void_use_the_verbs(self):
        self.assertTrue(units_with(self.queue, r"cr-supersede", r"cr-void"),
                        "no unit supersedes and voids with cr-supersede and cr-void")

    def test_a_changed_h1_re_posts_its_title_with_cr_plan(self):
        self.assertTrue(units_with(self.queue, r"\bh1\b", r"re-?posts?", r"\btitle\b", r"cr-plan"),
                        "no unit re-posts a changed H1's title with cr-plan")

    def test_a_first_release_is_asked_of_the_user_and_recorded_with_release_propose(self):
        hits = units_with(self.queue, r"release-propose", r"\bask", r"\buser\b", r"\blabel\b",
                          r"target date")
        self.assertTrue(hits, "no unit asks the user for a label and target date and records "
                              "the first release with release-propose")
        self.assertTrue(units_with(self.queue, r"release membership", r"user's call"),
                        "release membership is no longer the user's call")

    def test_header_slots_live_in_agents_md_and_the_target_release_on_the_board(self):
        hits = units_with(self.queue, r"header slots?", r"agents\.md",
                          r"target release[^.]{0,60}\bboard\b")
        self.assertTrue(hits, "no unit puts the header slots in AGENTS.md and the target release "
                              "on the board")

    def test_waves_and_a_release_is_not_a_cr_keep_their_rules(self):
        norm = normalise(self.queue)
        self.assertIn("grouping of crs", norm)
        self.assertIn("a release is not a cr", norm)
        self.assertIn("boundary event", norm)

    def test_crucible_absent_files_the_spec_alone_with_ids_from_the_spec_files(self):
        hits = units_with(self.queue, r"crucible[^.]{0,20}\babsent\b", r"\bspec(?: file)? alone\b",
                          r"spec files")
        self.assertTrue(hits, "no unit says: Crucible absent → the spec file alone, ids from "
                              "the spec files")

    def test_an_unregistered_project_does_the_setup_section_first(self):
        hits = units_with(self.queue, r"\bunregistered\b", r"crucible_project_key",
                          r"setup section", r"\bfirst\b")
        self.assertTrue(hits, "no unit sends an unregistered project to the Setup section first")

    def test_an_older_project_files_its_open_rows_once_and_keeps_the_readme_as_history(self):
        hits = units_with(self.queue, OLDER_PROJECT_MARKER.pattern, r"\bopen rows?\b",
                          r"cr-plan", r"\bhistory\b")
        self.assertTrue(hits, "no unit files an older project's open rows with cr-plan once, "
                              "the README kept as history")

    def test_where_the_rest_goes_rulings_merges_and_follow_ups(self):
        hits = units_with(self.text, r"\bruling", r"\bprd\b", r"\bdn\b", CR_CLOSE,
                          r"\bmilestone", r"follow-?ups?", r"\bboard\b")
        self.assertTrue(hits, "no unit sends rulings to the PRD or a DN, merges to cr-close and "
                              "a milestone, follow-ups to a CR filed on the board")

    def test_the_retired_queue_destinations_are_gone(self):
        norm = normalise(self.text)
        retired = [p for p in ("the queue (structure + dated footer notes",
                               "queue/prd/dn/memory edits",
                               "the tracking docs (queue + board)",
                               "the queue default") if p in norm]
        self.assertEqual(retired, [], "cr-authoring still names the retired queue destinations")

    def test_a_board_absent_cr_closes_by_the_status_flip_alone(self):
        sec = section(self.text, "Closing a CR")
        self.assertTrue(units_with(sec, r"\babsent\b", r"status:", r"\balone\b"),
                        "no unit closes a board-absent CR by the **Status:** flip alone")
        norm = normalise(sec)
        for gone in ("two-file", "both files", "queue row"):
            self.assertNotIn(gone, norm, f"'Closing a CR' still names {gone!r}")

    def test_cr_vs_task_and_patch_crs_name_filing_on_the_board(self):
        crt = section_matching(self.text, r"^cr vs task")
        self.assertTrue(units_with(crt, r"\bspec\b", r"\bboard\b"),
                        "'CR vs task' does not name filing on the board")
        self.assertNotIn("queue row", normalise(crt))
        patch = units_with(self.text, r"\bpatch cr\b", r"\bboard\b")
        self.assertTrue(patch, "the patch-CR rule does not name filing on the board")
        self.assertEqual([u for u in units_with(self.text, r"\bpatch cr\b")
                          if "queue row" in u], [], "a patch CR still carries a queue row")

    def test_docs_layout_lists_docs_changes_as_specs_only(self):
        sec = section_matching(self.text, r"^docs/ layout$")
        self.assertNotEqual(sec.strip(), "", "no 'docs/ layout' section")
        norm = normalise(sec)
        self.assertNotIn("readme.md", norm, "docs/ layout still lists the queue README")
        self.assertIn("cr-<proj>-nnn-<slug>.md", norm)
        self.assertRegex(norm, r"\bspecs only\b|\bonly the specs\b|\bspec files only\b")

    def test_the_document_types_cr_row_names_the_spec_file_and_the_board(self):
        rows = [u for u in units(self.text) if u.startswith("|") and "**CR**" in u]
        self.assertEqual(len(rows), 1, f"one CR row in 'Document types': {rows!r}")
        row = normalise(rows[0])
        self.assertIn("docs/changes/cr-<proj>-nnn-", row)
        self.assertRegex(row, r"\bboard\b")
        self.assertNotIn("docs/changes/readme.md", row)


# --------------------------------------------------------------------- model-b ----

def _numbered_item(sec: str, n: int) -> str:
    """The normalised text of numbered item ``n`` (``n.`` at line start) in ``sec``."""
    hit = [u for u in units(sec) if re.match(rf"^\s*{n}\.\s", u)]
    return normalise(hit[0]) if hit else ""


class ModelBSkillBoardTest(unittest.TestCase):
    """AC 4 — ``model-b`` § 4 items 2 and 5 and its description name the board."""

    def setUp(self):
        self.text = read_text(REPO_ROOT / MODEL_B_SKILL)
        self.conventions = section_matching(self.text, r"^4\. universal conventions")

    def test_item_2_says_the_board_holds_the_queue_and_the_execution_state(self):
        item = _numbered_item(self.conventions, 2)
        self.assertNotEqual(item, "", "§ 4 has no item 2")
        self.assertRegex(item, r"\bboard\b[^.]{0,40}\bholds?\b[^.]{0,20}\bqueue\b")
        self.assertIn("execution state", item)
        self.assertIn("docs/changes/", item)
        for gone in ("readme", "notes log", "release-boundary", "footer"):
            self.assertNotIn(gone, item, f"§ 4 item 2 still names {gone!r}")

    def test_item_5_says_a_release_is_a_boundary_event_not_a_cr(self):
        item = _numbered_item(self.conventions, 5)
        self.assertNotEqual(item, "", "§ 4 has no item 5")
        self.assertIn("boundary event", item)
        self.assertRegex(item, r"\bnot a cr\b")
        self.assertNotIn("release-boundary row", item)
        self.assertNotRegex(item, r"release cr bundles")

    def test_description_names_the_board(self):
        frontmatter, _ = split_frontmatter(self.text)
        desc = [ln for ln in frontmatter.splitlines() if ln.startswith("description:")]
        self.assertEqual(len(desc), 1)
        self.assertRegex(normalise(desc[0]), r"\bboard\b")

    def test_role_table_keeps_the_ontology_term_cr_queue(self):
        rows = [u for u in units(self.text) if u.startswith("| **ORCHESTRATOR** (track)")]
        self.assertEqual(len(rows), 1)
        self.assertIn("one lane's CR queue", rows[0])


# --------------------------------------------------------- orchestration refs ----

class OrchestrationMainlineBoardTest(unittest.TestCase):
    """AC 4 — ``orchestration-mainline``: ownership, filing with ``--track``, process-state,
    merge-gate close-out."""

    def setUp(self):
        self.text = read_text(REPO_ROOT / MAINLINE_REF)

    def test_mainline_owns_the_boards_queue_with_cr_depends_and_wave_sequence_track(self):
        sec = section(self.text, MAINLINE_OWNERSHIP_HEADING)
        self.assertNotEqual(sec.strip(), "", "the kept Ownership heading is gone or empty")
        hits = units_with(sec, r"\bowns?\b", r"\bboard'?s? queue\b|\bqueue on the board\b",
                          r"cr-depends", r"wave-sequence", r"--track")
        self.assertTrue(hits, "no unit says Mainline owns the board's queue (filing, cr-depends, "
                              "wave-sequence with --track)")
        self.assertEqual(reach_findings(MAINLINE_REF, sec), [])

    def test_filing_writes_the_spec_and_files_it_on_the_board(self):
        sec = section(self.text, MAINLINE_FILING_HEADING)
        self.assertNotEqual(sec.strip(), "", "the kept Filing heading is gone or empty")
        self.assertTrue(units_with(sec, r"write the spec", r"file (?:it )?on the board",
                                   r"git commit"),
                        "the filing order is not 'write the spec, file it on the board'")
        self.assertNotIn("queue row", normalise(sec))

    def test_a_filed_crs_process_state_is_on_the_board(self):
        hits = units_with(self.text, r"process-state", r"\bboard\b")
        self.assertTrue(hits, "no unit puts a filed CR's process-state on the board")
        self.assertEqual([u for u in units_with(self.text, r"process-state")
                          if "readme" in u], [])

    def test_the_merge_gate_close_out_is_the_board_close_out(self):
        sec = section(self.text, "Merge gate enforcement")
        norm = normalise(sec)
        self.assertNotIn("two-file close-out", norm)
        self.assertTrue(units_with(sec, CR_CLOSE, r"\bmilestone", r"status:"),
                        "the merge gate does not confirm the board close-out "
                        "(cr-close, milestone, the spec's **Status:**)")


class OrchestrationCommonBoardTest(unittest.TestCase):
    """AC 4 — ``orchestration-common``: the design phase, the batched design and the GC
    principle name the board."""

    def setUp(self):
        self.text = read_text(REPO_ROOT / COMMON_REF)
        self.two_phase = section(self.text, "Two-phase workflow")

    def test_the_design_phase_names_the_board_not_queue_edits(self):
        hits = units_with(self.two_phase, r"^- design phase")
        self.assertEqual(len(hits), 1, hits)
        self.assertRegex(hits[0], r"\bboard\b")
        self.assertNotRegex(hits[0], r"/queue\b|\bqueue edits\b")

    def test_batched_design_names_the_board_not_a_queue(self):
        hits = units_with(self.two_phase, r"batched per wave")
        self.assertEqual(len(hits), 1, hits)
        self.assertRegex(hits[0], r"\bboard\b")
        self.assertNotRegex(hits[0], r"→ queue up front")

    def test_the_gc_principle_names_the_board_not_a_queue_row(self):
        hits = units_with(self.text, r"gc principle")
        self.assertEqual(len(hits), 1, hits)
        self.assertRegex(hits[0], r"\bboard\b")
        self.assertNotIn("queue row", hits[0])


class JavaOrchestrationTemplateBoardTest(unittest.TestCase):
    """§S1 — the ``java-orchestration`` memory template."""

    def setUp(self):
        self.text = read_text(REPO_ROOT / JAVA_TEMPLATE)

    def test_docs_changes_is_not_called_the_cr_queue(self):
        called = re.findall(r"docs/changes/[^.;]{0,20}\bcr queue\b", normalise(self.text))
        self.assertEqual(called, [], "the template still calls docs/changes/ the CR queue")

    def test_the_pre_merge_close_out_names_cr_close_and_the_status_flip(self):
        sec = section_matching(self.text, r"^pre-merge gate")
        hits = units_with(sec, r"feature finish")
        self.assertEqual(len(hits), 1, hits)
        self.assertRegex(hits[0], CR_CLOSE)
        self.assertIn("status:", hits[0])
        self.assertNotRegex(hits[0], r"\bupdate readme\b|\breadme \(")


# ----------------------------------------------------------------------- reach ----

class QueueReadmeReachTest(unittest.TestCase):
    """AC 3 — no shipped surface names the queue README as a step."""

    def test_the_reach_covers_the_skills_references_templates_and_stack_files(self):
        surfaces = shipped_surfaces()
        for rel in (CRUCIBLE_SKILL, CR_AUTHORING, MAINLINE_REF, JAVA_TEMPLATE,
                    "generator/templates/red.md.tmpl", "generator/stacks/python.toml"):
            self.assertIn(rel, surfaces)

    def test_no_shipped_surface_names_the_queue_readme_as_a_step(self):
        findings = [f for rel in shipped_surfaces()
                    for f in reach_findings(rel, read_text(REPO_ROOT / rel))]
        self.assertEqual(findings, [], "\n".join(findings))


class ReachDetectorOnSyntheticTextTest(unittest.TestCase):
    """The reach detector, proven on synthetic text."""

    def test_an_affirmed_step_is_found_for_each_pattern(self):
        text = ("- Write the spec + queue row.\n\n"
                "- Update `docs/changes/README.md` on merge.\n\n"
                "- Append to the dated footer Notes.\n\n"
                "- Mainline owns the queue README.\n\n"
                "- Do the queue README's setup task first.\n")
        found = reach_findings("skills-src/x/SKILL.md", text)
        self.assertEqual(len(found), 5, found)

    def test_a_negated_or_retired_mention_is_not_a_finding(self):
        text = ("- The board holds the queue, not a queue README.\n\n"
                "- Never append to the Notes log.\n\n"
                "- `docs/changes/README.md` is retired.\n")
        self.assertEqual(reach_findings("skills-src/x/SKILL.md", text), [])

    def test_a_negation_reaches_only_its_own_clause(self):
        text = ("- An empty key means not registered: do the queue README's setup task, and "
                "never read the board as idle.\n")
        found = reach_findings("skills-src/x/SKILL.md", text)
        self.assertEqual(len(found), 1, found)
        self.assertIn("do the queue readme's setup task", found[0])

    def test_queue_file_is_a_finding_unless_stated_as_never_run(self):
        self.assertEqual(len(reach_findings("skills-src/x/SKILL.md",
                                            "- Run `queue-file` to sync the board.\n")), 1)
        self.assertEqual(reach_findings(
            "skills-src/x/SKILL.md",
            "- `queue-file` replaces the whole board queue, so it is never run.\n"), [])

    def test_the_older_project_case_is_exempt_only_in_the_three_named_files(self):
        unit = ("- An empty key: do the Setup section; otherwise (a project scaffolded before "
                "the board held the queue) do its README's setup tasks.\n")
        for rel in (BOOTSTRAP, SHUTDOWN, CR_AUTHORING):
            self.assertEqual(reach_findings(rel, unit), [], rel)
        self.assertEqual(len(reach_findings(MAINLINE_REF, unit)), 1)
        bare = "- An empty key: do the queue README's setup task.\n"
        self.assertEqual(len(reach_findings(BOOTSTRAP, bare)), 1)

    def test_units_split_bullets_rows_and_paragraphs(self):
        text = ("Intro line\ncontinued.\n\n- one\n  wrapped\n- two\n| a | b |\n| c | d |\n"
                "```\ncode line\n```\n")
        self.assertEqual(units(text), ["Intro line\ncontinued.", "- one\n  wrapped", "- two",
                                       "| a | b |", "| c | d |", "code line"])

    def test_section_stops_at_a_same_or_higher_level_heading(self):
        text = "## A\nbody\n### A.1\nsub\n## B\nother\n"
        self.assertEqual(section(text, "A"), "body\n### A.1\nsub")
        self.assertEqual(section(text, "A.1"), "sub")
        self.assertEqual(section(text, "missing"), "")


# ------------------------------------------------------------ §S3: Model B's records ----

MODEL_B_README = "docs/changes/README.md"
MODEL_B_AGENTS = "AGENTS.md"
DN_MULTI_HARNESS = "docs/research/DN-multi-harness-deploy-model.md"
#: C1's head (``docs: CR-MDB-048 — AGENTS.md module count``): the README as it stood before §S3.
README_BASE = "2037608"
#: Measured on the README at ``README_BASE`` (2026-10-02), for a tree without that history.
README_BASE_ROWS, README_BASE_NOTES = 45, 122
#: The README's header slots, as its header carried them at ``README_BASE``.
MODEL_B_HEADER_SLOTS = (
    ("design contract", ("docs/research/prd-model-b-rationalization.md",)),
    ("evidence base", ("audits/2026-07-20-", "docs/research/dn-rationalization-plan-review.md")),
    ("ontology", ("docs/research/dn-model-b-language.md",)),
)
#: "the README is frozen history" — frozen / read-only / history(ical), on normalised text.
FROZEN = r"\bfrozen\b|\bread-only\b|\bhistor(?:y|ical)\b"
#: The README's old role: "README.md = CR queue" / "README.md — the CR queue".
README_AS_QUEUE = re.compile(r"readme(?:\.md)?\s*(?:=|—|-|:)\s*(?:the\s+)?cr queue\b")


def readme_header_findings(text: str) -> list[str]:
    """What Model B's README header (its text before ``## Queue``) lacks (CR-MDB-048 §S3)."""
    head = text.split("\n## Queue", 1)[0]
    out = []
    if not units_with(head, FROZEN, r"\bcr-mdb-048\b"):
        out.append("no header unit calls it read-only history frozen at CR-MDB-048's merge")
    if not units_with(head, r"\bcrucible board\b|\bboard\b", r"\bqueue\b", r"\bexecution state\b"):
        out.append("no header unit puts the queue and the execution state on the Crucible board")
    if not units_with(head, QUEUE_FILE.pattern, NEVER_RUN.pattern, r"\breplac"):
        out.append("no header unit warns that queue-file is never run (it would replace the queue)")
    return out


def frozen_board_findings(where: str, units_found: list[str]) -> list[str]:
    """``units_found`` (normalised) must say the README is frozen history and the board holds the
    queue, and never call the README the CR queue."""
    if not units_found:
        return [f"{where}: not found"]
    joined = " ".join(units_found)
    out = []
    if not re.search(FROZEN, joined):
        out.append(f"{where}: does not say the README is frozen history")
    if not (re.search(r"\bboard\b", joined) and re.search(r"\bqueue\b", joined)):
        out.append(f"{where}: does not say the board holds the queue")
    if README_AS_QUEUE.search(joined):
        out.append(f"{where}: still calls the README the CR queue")
    return out


def model_b_agents_findings(text: str) -> list[str]:
    """What Model B's ``AGENTS.md`` lacks (CR-MDB-048 §S3): its ``docs/changes/`` row, its
    Important-files ``docs/changes/README.md`` line and its architecture flow say the README is
    frozen history and the board holds the queue; the flow renders no queue README; and it carries
    the README header's Design contract, Evidence base and Ontology lines."""
    out = []
    row = [u for u in norm_units(text) if u.startswith("| docs/changes/ |")]
    out += frozen_board_findings("the docs/changes/ row", row)
    important = [u for u in norm_units(section(text, "Important Files"))
                 if "docs/changes/readme.md" in u]
    out += frozen_board_findings("the Important-files line", important)
    flow = section(text, "Architecture & Data Flow")
    if "_render_queue_readme" in flow:
        out.append("the architecture flow still renders a queue README")
    flow_units = norm_units(flow)
    if not [u for u in flow_units if re.search(r"\bboard\b", u) and re.search(r"\bqueue\b", u)]:
        out.append("the architecture flow does not say the board holds the queue")
    if not [u for u in flow_units if re.search(r"\breadme\b", u) and re.search(FROZEN, u)]:
        out.append("the architecture flow does not say the README is frozen history")
    for slot, paths in MODEL_B_HEADER_SLOTS:
        if not units_with(text, r"\b" + slot + r"\b", *(re.escape(p) for p in paths)):
            out.append(f"no {slot} line citing {', '.join(paths)}")
    return out


def d20_findings(text: str) -> list[str]:
    """What DN §D20 lacks (CR-MDB-048 §S3): the user's direnv steps are named by ``AGENTS.md``'s
    Setup section, and §D20 names no queue README setup task."""
    d20 = section_matching(text, r"^d20\b")
    if not d20.strip():
        return ["no §D20 section"]
    out = []
    steps = units_with(d20, r"direnv allow")
    if not [u for u in steps if "agents.md" in u and re.search(r"\bsetup\b.{0,15}\bsection\b", u)]:
        out.append("the user's direnv steps do not name AGENTS.md's Setup section")
    named = units_with(d20, r"\bqueue readme\b|\breadme'?s setup tasks?\b")
    if named:
        out.append(f"§D20 still names the queue README's setup task: {named[0][:120]!r}")
    return out


def _readme_at_base() -> str | None:
    """Model B's README at ``README_BASE``, or ``None`` where that history is absent."""
    try:
        done = subprocess.run(["git", "-C", str(REPO_ROOT), "show",
                               f"{README_BASE}:{MODEL_B_README}"],
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


class ModelBReadmeFrozenHistoryTest(unittest.TestCase):
    """AC — Model B's README keeps all its content under a frozen-history header pointing to the
    board and warning off ``queue-file``."""

    def setUp(self):
        self.text = read_text(REPO_ROOT / MODEL_B_README)

    def test_the_header_freezes_it_points_to_the_board_and_warns_off_queue_file(self):
        self.assertEqual(readme_header_findings(self.text), [])

    def test_the_header_sits_above_the_queue_table(self):
        head = self.text.split("\n## Queue", 1)
        self.assertEqual(len(head), 2, "the ## Queue section is kept")
        self.assertTrue(units_with(head[0], FROZEN, r"\bcr-mdb-048\b"),
                        "the frozen-history header comes before ## Queue")

    def test_all_its_content_is_kept_in_order(self):
        base = _readme_at_base()
        lines = self.text.splitlines()
        if base is not None:
            remaining = iter(lines)
            lost = [ln for ln in base.splitlines() if not any(ln == seen for seen in remaining)]
            self.assertEqual(lost, [], f"{len(lost)} line(s) of the README were dropped or moved")
            return
        rows = [ln for ln in lines if ln.startswith("| [CR-")]
        notes = [ln for ln in section(self.text, "Footer notes").splitlines()
                 if re.match(r"- 20\d\d-", ln)]
        self.assertGreaterEqual((len(rows), len(notes)), (README_BASE_ROWS, README_BASE_NOTES))


class ModelBAgentsMdBoardTest(unittest.TestCase):
    """AC — Model B's ``AGENTS.md`` (incl. the header-slot lines) says the README is frozen
    history and the board holds the queue."""

    def test_the_row_the_important_file_line_the_flow_and_the_header_slots(self):
        findings = model_b_agents_findings(read_text(REPO_ROOT / MODEL_B_AGENTS))
        self.assertEqual(findings, [], "\n".join(findings))


class DnD20SetupSectionTest(unittest.TestCase):
    """AC — DN §D20 names ``AGENTS.md``'s Setup section instead of the queue README's setup task."""

    def test_d20_names_the_setup_section(self):
        findings = d20_findings(read_text(REPO_ROOT / DN_MULTI_HARNESS))
        self.assertEqual(findings, [], "\n".join(findings))


class ModelBRecordsDetectorsOnSyntheticTextTest(unittest.TestCase):
    """The §S3 detectors, proven on synthetic text both ways."""

    HEADER = ("# Model B — CR queue\n\n"
              "> **Read-only history, frozen at CR-MDB-048's merge.** The queue and the execution "
              "state are on the Crucible board. Never run `queue-file` against this file: it "
              "would replace the board's queue with these rows.\n\n"
              "## Queue\n\n| CR | Title |\n")

    def test_readme_header_both_ways(self):
        self.assertEqual(readme_header_findings(self.HEADER), [])
        for cut in ("Read-only history, frozen at CR-MDB-048's merge.",
                    "The queue and the execution state are on the Crucible board.",
                    "Never run `queue-file` against this file: it would replace the board's "
                    "queue with these rows."):
            with self.subTest(cut=cut[:30]):
                self.assertEqual(len(readme_header_findings(self.HEADER.replace(cut, ""))), 1)
        below = "# Model B — CR queue\n\n## Queue\n\n" + self.HEADER.split("\n\n", 1)[1]
        self.assertEqual(len(readme_header_findings(below)), 3, "a header below ## Queue")
        run = self.HEADER.replace("Never run `queue-file` against this file",
                                  "Run `queue-file` against this file")
        self.assertEqual(len(readme_header_findings(run)), 1)

    AGENTS = ("## Architecture & Data Flow\n\n```\n"
              "SCAFFOLD\n  -> render (_render_env, _render_agents_md incl. its Setup section)\n"
              "  -> docs/changes/.gitkeep  # the Crucible board holds the queue; Model B's README is"
              " frozen history\n```\n\n"
              "## Key Directories\n\n| Path | Purpose |\n|---|---|\n"
              "| `docs/changes/` | `CR-MDB-NNN-*.md` specs; `README.md` is frozen history — the "
              "Crucible board holds the queue |\n\n"
              "## Important Files\n\n"
              "- `docs/changes/README.md` — read-only history frozen at CR-MDB-048; the queue is "
              "on the Crucible board.\n\n"
              "Design contract: `docs/research/PRD-model-b-rationalization.md`. Evidence base: "
              "`audits/2026-07-20-*.md` + `docs/research/DN-rationalization-plan-review.md`.\n\n"
              "- Ontology `docs/research/DN-model-b-language.md` is LOCKED.\n")

    def test_model_b_agents_both_ways(self):
        self.assertEqual(model_b_agents_findings(self.AGENTS), [])
        for old, new in (
                ("`README.md` is frozen history — the Crucible board holds the queue",
                 "`README.md` = CR queue (structure only)"),
                ("read-only history frozen at CR-MDB-048; the queue is on the Crucible board",
                 "the CR queue: structure only"),
                ("_render_agents_md incl. its Setup section", "_render_queue_readme"),
                ("# the Crucible board holds the queue; Model B's README is frozen history", ""),
                (" Evidence base: `audits/2026-07-20-*.md` + "
                 "`docs/research/DN-rationalization-plan-review.md`.", ""),
                ("Ontology `docs/research/DN-model-b-language.md`", "Ontology is LOCKED")):
            with self.subTest(old=old[:30]):
                bad = self.AGENTS.replace(old, new)
                self.assertNotEqual(bad, self.AGENTS)
                self.assertTrue(model_b_agents_findings(bad), bad)

    def test_d20_both_ways(self):
        good = ("### D20 — direnv\n\n- **The user's steps.** Installing direnv, its shell hook, "
                "and `direnv allow` are the user's steps, named by the installer and `AGENTS.md`'s "
                "Setup section.\n\n### D21 — next\n\n- the queue README's setup task\n")
        self.assertEqual(d20_findings(good), [])
        self.assertEqual(len(d20_findings(good.replace(
            "`AGENTS.md`'s Setup section", "the queue README's setup task"))), 2)
        self.assertEqual(d20_findings("### D19 — other\n"), ["no §D20 section"])


if __name__ == "__main__":
    unittest.main()
