"""A scaffolded project's setup lives in its root ``AGENTS.md``; ``init`` writes no queue README
(CR-MDB-048 §S2; PRD D3.2 and D10.2, rulings 1–6 of 2026-10-02).

Contract: ``docs/changes/CR-MDB-048-board-holds-the-queue.md`` §S2 and its acceptance criteria.

Class map:

- ``ScaffoldDocsChangesTest`` — ``init`` (standalone and monorepo, solo and multi) writes no
  ``docs/changes/README.md`` and writes an empty ``docs/changes/.gitkeep``; ``plan_files`` and
  the envelope's ``planned`` list ``.gitkeep`` and not the README; ``emitted`` matches the files
  on disk — on a real run and after a mid-emission failure (CR-MDB-033); ``--dry-run`` writes
  nothing; the scaffold commit carries ``.gitkeep``.
- ``RootSetupSectionTest`` — the root ``AGENTS.md`` has exactly one ``## Setup`` section carrying
  every setup task the README carried: the dated scaffold line, the Crucible registration (its
  absent-tool remediation first, CR-MDB-045), in multi mode the Sandesh and direnv task
  (CR-MDB-047, its absent-tool remediation first), and the ``REPO_OWNER`` check; no sub-project
  ``AGENTS.md`` has one.
- ``RootHeaderLinesTest`` — Design contract and Evidence base as fill-in lines, Ontology citing
  ``~/.agents/skills/model-b/SKILL.md``; no target release; no queue table.
- ``RootWorkflowRulesTest`` — the Workflow rules name the Crucible board as the holder of the
  queue and the execution state, ``docs/changes/`` as the specs' home, and point the manual
  registrations to the Setup section; no README anywhere in the root ``AGENTS.md``.
- ``SetupReadersTest`` — ``init``'s stderr note after a write, ``setup_required``'s note and
  ``project_schema.toml``'s ``readers``/``step`` entries that named the queue README name the
  Setup section; ``setup_required`` keeps its shape and keys.
- ``SetupDetectorsOnSyntheticTextTest`` — each phrase-level detector below proven on synthetic
  text, both ways.
- ``EmitPlanLayoutTest`` — ``_emit_plan`` keeps no double blank line where its ``label`` was
  removed; the blank-line detector proven on synthetic text.

Rules are checked phrase-level within ONE bullet, table row or paragraph (a "unit", as
``tests.test_board_holds_the_queue.units`` splits them), on normalised text; never line numbers.

Isolation (NON-NEGOTIABLE): every ``init`` runs in process in the sandbox of
``tests.test_init_tool_verdicts`` — a hand-written ``install.toml`` under a per-test temp
``MODELB_HOME``, ``HOME`` and ``PI_CODING_AGENT_DIR`` pinned to per-test temp dirs. No test reads
the real ``~/.local/share/modelb``, ``~/.pi`` or ``~/.crucible``.

Stdlib only.
"""

import datetime
import inspect
import re
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from modelb_axi import scaffold
from modelb_axi.requirements import REQUIREMENTS
from tests import test_init_tool_verdicts as _verdicts
from tests._helpers import md_section
from tests.test_board_holds_the_queue import norm_units, units, units_with
from tests.test_bootstrap_shutdown_registry import normalise

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "modelb_axi" / "project_schema.toml"

README = "docs/changes/README.md"
GITKEEP = "docs/changes/.gitkeep"
SUBS = ("a", "b")
MONOREPO = "monorepo:" + ",".join(SUBS)
MULTI = "multi:2"
PROJECT = _verdicts.DERIVED_CHANNEL
ONTOLOGY_PATH = "~/.agents/skills/model-b/SKILL.md"

#: A ``## Setup`` heading (any suffix after a word boundary), outside fenced code.
SETUP_HEADING = re.compile(r"^##\s+Setup\b")
_FENCE_LINE = re.compile(r"^\s*(```|~~~)")
#: "the Setup section" / "the ``## Setup`` section" / "AGENTS.md's Setup section", normalised.
SETUP_SECTION_RE = re.compile(r"\bsetup\b.{0,15}\bsection\b")
#: The schema entries that named the queue README before CR-MDB-048, and the field that did.
README_NAMING_ENTRIES = (("PROJECT_NAME", "readers"), ("CRUCIBLE_PROJECT_KEY", "step"),
                         ("SANDESH_PROJECT", "readers"))


def _remediation(requirement_id: str) -> str:
    return next(r for r in REQUIREMENTS if r["id"] == requirement_id)["remediation"]


# ------------------------------------------------------------------ detectors ----

def setup_heading_count(text: str) -> int:
    """How many ``## Setup`` headings ``text`` has outside fenced code."""
    fenced, count = False, 0
    for line in text.splitlines():
        if _FENCE_LINE.match(line):
            fenced = not fenced
        elif not fenced and SETUP_HEADING.match(line):
            count += 1
    return count


def setup_body(text: str) -> str:
    """The ``## Setup`` section of ``text`` (heading to the next ``## ``), or ``""``."""
    for line in text.splitlines():
        if SETUP_HEADING.match(line):
            return md_section(text, line)
    return ""


def _remediation_first(unit: str, remediation: str, anchor: str, label: str) -> list[str]:
    rem = normalise(remediation)
    if rem not in unit:
        return [f"{label}: the absent tool's remediation {remediation!r} is not named: {unit!r}"]
    if unit.index(rem) > unit.index(anchor):
        return [f"{label}: the remediation does not come first: {unit!r}"]
    return []


def setup_task_findings(body: str, *, today: str, multi: bool, project: str,
                        crucible_absent: bool = False, sandesh_absent: bool = False) -> list[str]:
    """What the Setup section ``body`` lacks of the README's setup tasks (CR-MDB-048 §S2): the
    dated scaffold line; one Crucible registration task naming ``CRUCIBLE_PROJECT_KEY`` in
    ``.env`` (its remediation first when Crucible is absent, none when present); one
    ``REPO_OWNER`` check; in multi mode one Sandesh task naming the Mainline address, direnv and
    its hook, ``direnv allow`` per ``.envrc`` and the Track launch line (its remediation first
    when Sandesh is absent); in solo mode no Sandesh/direnv task."""
    out: list[str] = []
    if not units_with(body, r"modelb-axi init", re.escape(today)):
        out.append(f"no dated scaffold line ({today}, modelb-axi init)")
    crucible = units_with(body, r"crucible_project_key", r"\bregist")
    if len(crucible) != 1:
        out.append(f"want one Crucible registration task, found {len(crucible)}")
    else:
        task = crucible[0]
        if not re.search(r"\.env(?!\.local)\b", task) or ".env.local" in task:
            out.append(f"the registration task does not name .env for the key: {task!r}")
        if crucible_absent:
            out += _remediation_first(task, _remediation("crucible"), "crucible_project_key",
                                      "Crucible")
    if not crucible_absent and normalise(_remediation("crucible")) in normalise(body):
        out.append("a present Crucible's remediation is named")
    if len(units_with(body, r"\brepo_owner\b", r"\bowner\b")) != 1:
        out.append("want one REPO_OWNER check")
    mainline = f"mainline - {project.lower()}"
    sandesh = units_with(body, re.escape(mainline))
    if multi:
        if len(sandesh) != 1:
            out.append(f"want one Sandesh task naming {mainline!r}, found {len(sandesh)}")
        else:
            task = sandesh[0]
            checks = (
                ("installing direnv", r"\binstall\w*\b.*\bdirenv\b"),
                ("the direnv shell hook", r"direnv hook"),
                ("direnv allow per .envrc", r"direnv allow.*\.envrc"),
                ("the Track launch line",
                 r'env sandesh_address="track <n> - (?:<project>|' + re.escape(project.lower())
                 + r')" pi'),
            )
            out += [f"the Sandesh task does not name {what}: {task!r}"
                    for what, rx in checks if not re.search(rx, task)]
            if sandesh_absent:
                out += _remediation_first(task, _remediation("sandesh"), mainline, "Sandesh")
    else:
        if sandesh or units_with(body, r"\bdirenv\b"):
            out.append("a solo project's Setup section carries a Sandesh/direnv task")
    if not sandesh_absent and normalise(_remediation("sandesh")) in normalise(body):
        out.append("a present Sandesh's remediation is named")
    return out


def header_line_findings(text: str) -> list[str]:
    """What the root ``AGENTS.md`` lacks of the README's header slots (CR-MDB-048 §S2): one
    Design contract and one Evidence base fill-in line, one Ontology line citing
    ``~/.agents/skills/model-b/SKILL.md`` without a ``crucible:`` prefix; no target release."""
    out: list[str] = []
    for slot in ("design contract", "evidence base"):
        found = units_with(text, r"\b" + slot + r"\b")
        if len(found) != 1:
            out.append(f"want one {slot} line, found {len(found)}")
        elif not re.search(r"\b" + slot + r"\b.{0,12}fill in", found[0]):
            out.append(f"the {slot} line is not a fill-in line: {found[0]!r}")
    ontology = units_with(text, r"\bontology\b")
    if len(ontology) != 1:
        out.append(f"want one ontology line, found {len(ontology)}")
    elif (normalise(ONTOLOGY_PATH) not in ontology[0]) or "crucible:" in ontology[0]:
        out.append(f"the ontology line does not cite {ONTOLOGY_PATH} unprefixed: {ontology[0]!r}")
    if units_with(text, r"\btarget release\b"):
        out.append("a target release is scaffolded")
    return out


def workflow_rules_findings(rules: str) -> list[str]:
    """What the Workflow rules section ``rules`` lacks (CR-MDB-048 §S2): the Crucible board holds
    the queue and the execution state; ``docs/changes/`` holds the specs; the manual
    registrations point to the Setup section; and no README is named."""
    out: list[str] = []
    if not units_with(rules, r"\bcrucible\b", r"\bboard\b", r"\bqueue\b",
                           r"\bexecution state\b"):
        out.append("no rule says the Crucible board holds the queue and the execution state")
    if not units_with(rules, r"docs/changes/?", r"\bspecs?\b"):
        out.append("no rule says docs/changes/ holds the specs")
    if not units_with(rules, r"\bregistrations?\b", SETUP_SECTION_RE.pattern):
        out.append("no rule points the manual registrations to the Setup section")
    named = units_with(rules, r"\breadme\b")
    if named:
        out.append(f"a rule names a README: {named[0]!r}")
    return out


# ------------------------------------------------------------------ sandbox ----

class _Case(_verdicts._InitSandboxCase):
    """The CR-MDB-045 init sandbox; every tool recorded present unless a test says otherwise."""

    def setUp(self):
        super().setUp()
        self.write_install(_verdicts._complete_verdicts("detected"))
        self.target = self.root / "proj"
        self.today = datetime.date.today().isoformat()

    def install_with(self, **states) -> None:
        verdicts = _verdicts._complete_verdicts("detected")
        verdicts.update(states)
        self.write_install(verdicts)

    def init_ok(self, **fields) -> tuple[dict, str]:
        rc, axi, err = self.run_init(self.target, **fields)
        self.assertEqual((rc, axi.get("ok")), (0, True), f"init must succeed; stderr={err!r}")
        return axi, err

    def text(self, rel: str) -> str:
        path = self.target / rel
        self.assertTrue(path.is_file(), f"{rel} was not emitted")
        return path.read_text(encoding="utf-8")

    def on_disk(self) -> set:
        return {p.relative_to(self.target).as_posix() for p in self.target.rglob("*")
                if p.is_file() and ".git" not in p.relative_to(self.target).parts}


SHAPES = (("solo", "standalone"), ("solo", MONOREPO), (MULTI, "standalone"), (MULTI, MONOREPO))


# ------------------------------------------------------------------ docs/changes/ ----

class ScaffoldDocsChangesTest(_Case):
    """AC — ``init`` writes no ``docs/changes/README.md`` and writes ``docs/changes/.gitkeep``;
    ``planned`` lists ``.gitkeep`` and not the README; ``emitted`` matches the files on disk."""

    def test_plan_files_lists_the_gitkeep_and_not_the_readme(self):
        for subs in ([], [str(s) for s in SUBS]):
            with self.subTest(subs=subs):
                plan = scaffold.plan_files(subs)
                self.assertEqual(plan.count(GITKEEP), 1, plan)
                self.assertNotIn(README, plan)
                self.assertEqual(plan.count("docs/research/.gitkeep"), 1,
                                 "the research placeholder stays")

    def test_every_shape_writes_the_gitkeep_and_no_readme(self):
        for mode, shape in SHAPES:
            with self.subTest(mode=mode, shape=shape):
                self.target = self.root / f"proj-{mode.replace(':', '')}-{shape.split(':')[0]}"
                axi, _err = self.init_ok(mode=mode, repo_shape=shape)
                self.assertFalse((self.target / README).exists(), "no queue README is written")
                self.assertTrue((self.target / GITKEEP).is_file(), f"{GITKEEP} is written")
                self.assertEqual((self.target / GITKEEP).read_bytes(), b"", "an empty .gitkeep")
                self.assertEqual(sorted(p.name for p in (self.target / "docs/changes").iterdir()),
                                 [".gitkeep"], "docs/changes/ holds the .gitkeep alone")
                planned, emitted = axi.get("planned", []), axi.get("emitted", [])
                self.assertEqual((planned.count(GITKEEP), emitted.count(GITKEEP)), (1, 1),
                                 f"planned={planned!r}")
                self.assertNotIn(README, planned)
                self.assertNotIn(README, emitted)
                for sub in (SUBS if shape == MONOREPO else ()):
                    self.assertFalse((self.target / sub / README).exists(),
                                     f"no README under {sub}/ either")

    def test_emitted_matches_the_files_on_disk(self):
        axi, _err = self.init_ok(mode=MULTI, repo_shape=MONOREPO)
        emitted = axi.get("emitted", [])
        self.assertEqual(len(emitted), len(set(emitted)), "each file emitted once")
        self.assertEqual(set(emitted), self.on_disk())

    def test_a_mid_emission_failure_reports_exactly_the_files_on_disk_and_no_readme(self):
        with mock.patch.object(scaffold, "_render_agents_md",
                               side_effect=OSError("injected mid-emission failure")):
            rc, axi, err = self.run_init(self.target)
        self.assertEqual((rc, axi.get("ok")), (3, False), f"stderr={err!r}")
        on_disk = self.on_disk()
        self.assertTrue(on_disk, "the failure lands after some files are written")
        self.assertEqual(set(axi.get("emitted") or []), on_disk, "CR-MDB-033: emitted is on disk")
        self.assertNotIn(README, on_disk)

    def test_dry_run_plans_the_gitkeep_and_writes_nothing(self):
        axi, _err = self.init_ok(mode=MULTI, repo_shape=MONOREPO, dry_run=True)
        planned = axi.get("planned", [])
        self.assertEqual(planned.count(GITKEEP), 1, planned)
        self.assertNotIn(README, planned)
        self.assertEqual(axi.get("emitted"), [], "a dry run emits nothing")
        self.assertFalse(self.target.exists(), "--dry-run writes nothing")

    def test_the_scaffold_commit_carries_the_gitkeep_and_no_readme(self):
        self.init_ok(no_commit=False)
        tracked = subprocess.run(["git", "-C", str(self.target), "ls-files"], capture_output=True,
                                 text=True, timeout=30, check=True).stdout.splitlines()
        self.assertIn(GITKEEP, tracked)
        self.assertNotIn(README, tracked)


# ------------------------------------------------------------------ the Setup section ----

class RootSetupSectionTest(_Case):
    """AC — the root ``AGENTS.md`` has ONE ``## Setup`` section carrying every setup task the
    README carried, with the same absent-tool remediations and the multi-mode Sandesh/direnv
    task; no sub-project ``AGENTS.md`` has one."""

    def setup_of(self, **fields) -> str:
        self.init_ok(**fields)
        agents_md = self.text("AGENTS.md")
        self.assertEqual(setup_heading_count(agents_md), 1,
                         f"one ## Setup section in the root AGENTS.md; AGENTS.md={agents_md!r}")
        return setup_body(agents_md)

    def test_solo_carries_the_scaffold_line_registration_and_owner_check(self):
        body = self.setup_of()
        self.assertEqual(setup_task_findings(body, today=self.today, multi=False,
                                             project=PROJECT), [], body)

    def test_multi_also_carries_the_sandesh_and_direnv_task(self):
        body = self.setup_of(mode=MULTI)
        self.assertEqual(setup_task_findings(body, today=self.today, multi=True,
                                             project=PROJECT), [], body)

    def test_multi_sandesh_task_names_the_sandesh_project_override(self):
        body = self.setup_of(mode=MULTI, sandesh_project="Foo_Bar")
        self.assertEqual(setup_task_findings(body, today=self.today, multi=True,
                                             project="Foo_Bar"), [], body)

    def test_an_absent_crucible_puts_its_remediation_first(self):
        self.install_with(crucible="absent")
        body = self.setup_of()
        self.assertEqual(setup_task_findings(body, today=self.today, multi=False, project=PROJECT,
                                             crucible_absent=True), [], body)

    def test_an_absent_sandesh_puts_its_remediation_first_in_multi_mode(self):
        self.install_with(sandesh="absent")
        body = self.setup_of(mode=MULTI)
        self.assertEqual(setup_task_findings(body, today=self.today, multi=True, project=PROJECT,
                                             sandesh_absent=True), [], body)

    def test_the_monorepo_root_has_the_section_and_no_sub_project_has_one(self):
        body = self.setup_of(mode=MULTI, repo_shape=MONOREPO)
        self.assertEqual(setup_task_findings(body, today=self.today, multi=True,
                                             project=PROJECT), [], body)
        for sub in SUBS:
            with self.subTest(sub=sub):
                text = self.text(f"{sub}/AGENTS.md")
                self.assertEqual(setup_heading_count(text), 0, text)
                self.assertNotIn("CRUCIBLE_PROJECT_KEY", text, "no setup task in a sub-project")


# ------------------------------------------------------------------ header lines ----

class RootHeaderLinesTest(_Case):
    """AC — the root ``AGENTS.md`` carries Design contract, Evidence base and Ontology lines, the
    Ontology citing ``~/.agents/skills/model-b/SKILL.md``; no target release, no queue table."""

    def test_the_header_slots_are_lines_of_the_root_agents_md(self):
        for mode, shape in ((("solo", "standalone"), (MULTI, MONOREPO))):
            with self.subTest(mode=mode, shape=shape):
                self.target = self.root / f"proj-{mode.replace(':', '')}"
                self.init_ok(mode=mode, repo_shape=shape)
                text = self.text("AGENTS.md")
                self.assertEqual(header_line_findings(text), [], text)
                self.assertNotIn("| CR | Title | Wave | Depends on |", text, "no queue table")


# ------------------------------------------------------------------ Workflow rules ----

class RootWorkflowRulesTest(_Case):
    """AC — the Workflow rules name the board and the Setup section, not the README."""

    def test_the_workflow_rules_name_the_board_the_specs_and_the_setup_section(self):
        self.init_ok(mode=MULTI)
        rules = md_section(self.text("AGENTS.md"), "## Workflow rules")
        self.assertTrue(rules, "the Workflow rules section stays")
        self.assertEqual(workflow_rules_findings(rules), [], rules)

    def test_the_root_agents_md_names_no_readme_as_the_queue_or_setup(self):
        self.init_ok(mode=MULTI, repo_shape=MONOREPO)
        for rel in ("AGENTS.md", *(f"{s}/AGENTS.md" for s in SUBS)):
            with self.subTest(file=rel):
                named = [u for u in norm_units(self.text(rel))
                         if "docs/changes/readme" in u or re.search(r"\bqueue readme\b", u)]
                self.assertEqual(named, [])


# ------------------------------------------------------------------ readers ----

class SetupReadersTest(_Case):
    """AC — ``init``'s stderr note, ``setup_required``'s note and ``project_schema.toml`` name the
    Setup section, not the README; ``setup_required`` keeps its shape and keys."""

    def test_the_stderr_note_after_a_write_names_the_setup_section(self):
        _axi, err = self.init_ok()
        notes = [ln for ln in err.splitlines() if re.search(r"(?i)registrations are manual", ln)]
        self.assertEqual(len(notes), 1, f"one manual-registration note; stderr={err!r}")
        self.assertIn("AGENTS.md", notes[0])
        self.assertRegex(normalise(notes[0]), SETUP_SECTION_RE)
        self.assertNotRegex(err, r"docs/changes/README|(?i:queue README)", "stderr names no README")

    def test_setup_required_keeps_its_shape_and_its_note_names_the_setup_section(self):
        for dry_run in (False, True):
            with self.subTest(dry_run=dry_run):
                self.target = self.root / f"proj-{dry_run}"
                axi, err = self.init_ok(dry_run=dry_run)
                rows = axi.get("setup_required")
                if not isinstance(rows, list):
                    self.fail(f"setup_required is a list; axi={axi!r}")
                self.assertEqual([sorted(r) for r in rows], [["file", "key", "note"]], rows)
                row = rows[0]
                self.assertEqual((row["key"], row["file"]), ("CRUCIBLE_PROJECT_KEY", ".env"))
                note = row["note"]
                for word in ("Crucible", "regist", ".env", "AGENTS.md"):
                    self.assertIn(word, note, f"the note names {word!r}: {note!r}")
                self.assertRegex(normalise(note), SETUP_SECTION_RE)
                self.assertNotIn("README", note)
                lines = [ln for ln in err.splitlines() if "setup required" in ln]
                self.assertEqual(len(lines), 1, err)
                self.assertRegex(normalise(lines[0]), SETUP_SECTION_RE)

    def test_the_schema_entries_that_named_the_readme_name_the_setup_section(self):
        entries = {e["name"]: e for e in scaffold.load_schema(SCHEMA_PATH)}
        for name, field in README_NAMING_ENTRIES:
            with self.subTest(key=name, field=field):
                value = entries[name][field]
                text = " ".join(value) if isinstance(value, list) else value
                self.assertIn("AGENTS.md", text)
                self.assertRegex(normalise(text), SETUP_SECTION_RE)
        for entry in entries.values():
            for field in ("readers", "step"):
                value = entry.get(field) or ""
                text = " ".join(value) if isinstance(value, list) else value
                with self.subTest(key=entry["name"], field=field):
                    self.assertNotRegex(text, r"(?i)\breadme\b")


# ------------------------------------------------------------------ detectors, proven ----

class SetupDetectorsOnSyntheticTextTest(unittest.TestCase):
    """Each detector bites on a defect and passes a conforming text."""

    TODAY = "2026-10-02"
    CRU = _remediation("crucible")
    SAN = _remediation("sandesh")
    GOOD_SOLO = (
        "- [x] Scaffold via `modelb-axi init` — 2026-10-02\n"
        "- [ ] Register the project in Crucible and paste the key into `.env` "
        "(`CRUCIBLE_PROJECT_KEY=`) — manual step\n"
        "- [ ] Confirm the remote owner matches `REPO_OWNER` in `.env`\n"
    )
    SANDESH_TASK = (
        "- [ ] Sandesh setup + register (`P`, `Mainline - P`) — install direnv and its "
        "shell hook (`direnv hook fish | source`), then run `direnv allow` in each "
        "directory with an `.envrc`; launch a Track with "
        '`env SANDESH_ADDRESS="Track <N> - P" pi`\n'
    )

    def findings(self, body: str, **kw) -> list[str]:
        return setup_task_findings(body, today=self.TODAY, project="P", **kw)

    def test_setup_tasks_pass_conforming_solo_and_multi_text(self):
        self.assertEqual(self.findings(self.GOOD_SOLO, multi=False), [])
        self.assertEqual(self.findings(self.GOOD_SOLO + self.SANDESH_TASK, multi=True), [])

    def test_setup_tasks_bite_on_each_missing_task(self):
        for drop, word in (("Scaffold via", "scaffold"), ("Register the", "registration"),
                           ("Confirm the remote", "REPO_OWNER")):
            with self.subTest(drop=word):
                body = "".join(ln for ln in self.GOOD_SOLO.splitlines(True) if drop not in ln)
                self.assertEqual(len(self.findings(body, multi=False)), 1, body)
        self.assertTrue(self.findings(self.GOOD_SOLO, multi=True), "multi without Sandesh task")
        self.assertTrue(self.findings(self.GOOD_SOLO + self.SANDESH_TASK, multi=False),
                        "a solo Setup section with a Sandesh task")
        self.assertTrue(self.findings(self.GOOD_SOLO.replace("`.env` (", "`.env.local` ("),
                                      multi=False), "the key sent to .env.local")

    def test_setup_tasks_bite_on_a_sandesh_task_missing_a_step(self):
        for cut in ("install direnv and its shell hook (`direnv hook fish | source`), then ",
                    "run `direnv allow` in each directory with an `.envrc`; ",
                    'launch a Track with `env SANDESH_ADDRESS="Track <N> - P" pi`'):
            with self.subTest(cut=cut[:20]):
                task = self.SANDESH_TASK.replace(cut, "")
                self.assertNotEqual(task, self.SANDESH_TASK)
                self.assertTrue(self.findings(self.GOOD_SOLO + task, multi=True), task)

    def test_remediation_first_both_ways(self):
        first = self.GOOD_SOLO.replace(
            "Register the", f"Crucible is absent — first: {self.CRU}. Then: Register the")
        self.assertEqual(self.findings(first, multi=False, crucible_absent=True), [])
        self.assertTrue(self.findings(self.GOOD_SOLO, multi=False, crucible_absent=True),
                        "absent Crucible without its remediation")
        self.assertTrue(self.findings(first, multi=False), "a present Crucible's remediation")
        late = self.GOOD_SOLO.replace("manual step", f"manual step; first: {self.CRU}")
        self.assertTrue(self.findings(late, multi=False, crucible_absent=True), "remediation last")
        san = self.SANDESH_TASK.replace("Sandesh setup", f"Sandesh is absent — first: {self.SAN}. "
                                        "Then: Sandesh setup")
        self.assertEqual(self.findings(self.GOOD_SOLO + san, multi=True, sandesh_absent=True), [])
        self.assertTrue(self.findings(self.GOOD_SOLO + self.SANDESH_TASK, multi=True,
                                      sandesh_absent=True))

    def test_setup_heading_count_ignores_fenced_code_and_counts_each_heading(self):
        self.assertEqual(setup_heading_count("## Setup\n- x\n"), 1)
        self.assertEqual(setup_heading_count("```\n## Setup\n```\n"), 0)
        self.assertEqual(setup_heading_count("## Setup\n## Setup tasks\n"), 2)
        self.assertEqual(setup_heading_count("## Setupx\n### Setup\n"), 0)
        self.assertEqual(setup_body("# T\n## Setup\n- a\n## Next\n- b\n"), "## Setup\n- a")

    def test_header_lines_both_ways(self):
        good = ("- Design contract: _fill in (`docs/research/PRD-….md`)_\n"
                "- Evidence base: _fill in_\n"
                f"- Ontology: `{ONTOLOGY_PATH}`\n")
        self.assertEqual(header_line_findings(good), [])
        for bad in (good.replace("- Evidence base: _fill in_\n", ""),
                    good.replace("Design contract: _fill in", "Design contract: `docs/x.md`"),
                    good.replace(ONTOLOGY_PATH, "crucible:docs/research/DN-model-b-language.md"),
                    good + "- Target release: 0.1.0\n",
                    good + "- Ontology: again\n"):
            with self.subTest(bad=bad[-40:]):
                self.assertTrue(header_line_findings(bad), bad)

    def test_workflow_rules_both_ways(self):
        good = ("- The Crucible board holds the queue and the execution state; `docs/changes/` "
                "holds the specs.\n"
                "- Registrations are manual — complete them from the Setup section.\n")
        self.assertEqual(workflow_rules_findings(good), [])
        for bad in (good.replace("and the execution state", ""),
                    good.replace("holds the specs", "holds the work"),
                    good.replace("from the Setup section", "in the queue README"),
                    good + "- Queue (`docs/changes/README.md`) holds STRUCTURE only.\n"):
            with self.subTest(bad=bad[-50:]):
                self.assertTrue(workflow_rules_findings(bad), bad)

    def test_units_split_bullets_so_a_rule_is_judged_in_one_bullet(self):
        split = ("- The Crucible board holds the queue.\n- And the execution state.\n"
                 "- `docs/changes/` holds the specs.\n- Registrations: the Setup section.\n")
        self.assertEqual(len(units(split)), 4)
        self.assertTrue(workflow_rules_findings(split), "a rule split over two bullets")


def consecutive_blank_lines(source: str) -> list[int]:
    """The 1-based line numbers in ``source`` that are a second blank line in a row."""
    lines = source.splitlines()
    return [i + 1 for i in range(1, len(lines))
            if not lines[i].strip() and not lines[i - 1].strip()]


class EmitPlanLayoutTest(unittest.TestCase):
    """F6 — ``_emit_plan`` (modelb_axi/scaffold.py) keeps no double blank line where its
    orchestrator ``label`` was removed (§S2)."""

    def test_emit_plan_has_no_double_blank_line(self):
        source = inspect.getsource(scaffold._emit_plan)
        self.assertEqual(consecutive_blank_lines(source), [],
                         "_emit_plan has a double blank line (lines relative to its def)")

    def test_consecutive_blank_lines_both_ways(self):
        self.assertEqual(consecutive_blank_lines("def f():\n    a = 1\n\n    b = 2\n"), [])
        self.assertEqual(consecutive_blank_lines("def f():\n    a = 1\n\n\n    b = 2\n"), [4])
        self.assertEqual(consecutive_blank_lines("def f():\n    a = 1\n\n    \n    b = 2\n"), [4])


if __name__ == "__main__":
    unittest.main()
