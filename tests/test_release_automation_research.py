"""The release-automation research note records Model B's release body (CR-MDB-058 §S7).

Contract: ``docs/changes/CR-MDB-058-release-notes-and-rehearsal.md`` §S7 and its acceptance
criterion "the research doc carries the dated note and the corrected paragraph". The note is
``docs/research/release-automation-crucible-procedure.md``:

- "The shape" keeps its sourced record of Crucible (``gh release create "$TAG"
  --generate-notes``) and gains a dated note that Model B's ``create-release`` now uses
  ``--notes-file``;
- "What this means for Model B" no longer claims Model B has no ``release.yml``.

CR-MDB-067 §S6 adds two pins (:func:`rehearsal_note_findings`):

- "What Model B adopted (2026-09-24)" carries a dated note (2026-10-14) that the manual
  ``rehearse-testpypi`` became the ``rehearse`` job on every release or hotfix push;
- its "Setup status" notes that the ``testpypi`` environment admits ``release/**`` and
  ``hotfix/**`` and has no required reviewers.

A light text pin: each statement is checked in ONE normalised unit (a paragraph, a list item with
its continuation lines, a table row), as ``tests.test_board_holds_the_queue.norm_units`` splits
them; the checker is proved both ways on sample text.

CR-MDB-070 §S6 adds (:func:`cr070_research_findings`, :func:`cr067_superseded_findings`):

- the CR-MDB-070 rulings section (written at its gap analysis) is pinned, each ruling one unit;
- "What Model B adopted (2026-09-24)" carries a dated "superseded by CR-MDB-070, 2026-10-14"
  note that ``create-release`` moved to the ``master`` push;
- the CR-MDB-067 bullet saying the concrete CI workflow lives in ``ci.yml`` carries the same
  dated note, in that bullet's own unit;
- ``docs/changes/CR-MDB-067-release-rehearsal-and-ci.md`` §S2 and §S3 each carry the line
  "superseded by CR-MDB-070, 2026-10-14" exactly once (``CiWorkflowAmendmentNoteTest`` in
  ``tests/test_ci_workflow.py`` is the precedent).

Stdlib only.
"""

import re
import unittest
from pathlib import Path

from tests._helpers import md_section
from tests.test_board_holds_the_queue import norm_units
from tests.test_bootstrap_shutdown_registry import normalise

REPO_ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DOC = REPO_ROOT / "docs" / "research" / "release-automation-crucible-procedure.md"
SHAPE = "## The shape"
MEANING = "## What this means for Model B"

#: Crucible's create-release, as the sourced record states it (normalised).
CRUCIBLE_RECORD = 'gh release create "$tag" --generate-notes'
#: The dated note: a date, Model B, its create-release and --notes-file in one unit.
DATED_NOTE = (r"\b20\d\d-\d\d-\d\d\b", r"\bmodel b\b", r"\bcreate-release\b", r"--notes-file\b")
#: The stale claim the corrected paragraph drops.
STALE_CLAIM = re.compile(r"\bmodel b has no release\.yml\b")

# CR-MDB-067 §S6 — the 2026-09-24 adoption's dated rehearsal note and its setup-status line.
ADOPTED_0924 = "## What Model B adopted (2026-09-24"
SETUP_STATUS = "### Setup status"
#: The dated note: 2026-10-14, the manual rehearse-testpypi, the rehearse job, every release or
#: hotfix push — in one unit of the 2026-09-24 section (its Setup status included).
REHEARSAL_NOTE = (
    r"\b2026-10-14\b", r"\bmanual\b", r"(?<![\w-])rehearse-testpypi(?![\w-])",
    r"(?<![\w-])rehearse job\b", r"\b(?:every|each)\b",
    r"\brelease (?:or|and) hotfix (?:branch )?push(?:es)?\b"
    r"|\bpush(?:es)? (?:to|of) (?:a |every |each )?release (?:or|and) hotfix branch(?:es)?\b",
)
#: The setup-status line: the testpypi environment admits release/** and hotfix/** and has no
#: required reviewers — in one unit of the Setup status subsection.
TESTPYPI_SETUP = (
    # normalisation drops ``*``: ``release/**`` reads as ``release/``, never ``release/x.y.z``.
    r"(?<![\w-])testpypi(?![\w-])", r"\benvironment", r"(?<![\w-])release/(?!\w)",
    r"(?<![\w-])hotfix/(?!\w)", r"\b(?:no|without)\b[^.;]{0,40}\brequired reviewers?\b",
)
NO_REHEARSAL_NOTE = (f"{ADOPTED_0924}): no dated note (2026-10-14) that the manual "
                     "rehearse-testpypi became the rehearse job on every release or hotfix push")
NO_TESTPYPI_SETUP = (f"{SETUP_STATUS}: no note that the testpypi environment admits release/** "
                     "and hotfix/** and has no required reviewers")


def rehearsal_note_findings(text: str) -> list[str]:
    """What ``text`` lacks of CR-MDB-067 §S6's research-doc edits."""
    adopted = md_section(text, ADOPTED_0924)
    if not adopted:
        return [f"no '{ADOPTED_0924})' section"]
    out = []
    if not any(all(re.search(rx, u) for rx in REHEARSAL_NOTE) for u in norm_units(adopted)):
        out.append(NO_REHEARSAL_NOTE)
    setup = md_section(adopted, SETUP_STATUS, stop_prefix="#")
    if not any(all(re.search(rx, u) for rx in TESTPYPI_SETUP) for u in norm_units(setup)):
        out.append(NO_TESTPYPI_SETUP)
    return out


def research_doc_findings(text: str) -> list[str]:
    """What ``text`` lacks of §S7's research-doc edits."""
    out = []
    shape = md_section(text, SHAPE)
    if not shape:
        out.append(f"no '{SHAPE}' section")
    else:
        found = norm_units(shape)
        if not any(CRUCIBLE_RECORD in u for u in found):
            out.append(f"{SHAPE}: the sourced record of Crucible's create-release is gone")
        if not any(all(re.search(rx, u) for rx in DATED_NOTE) for u in found):
            out.append(f"{SHAPE}: no dated note that Model B's create-release now uses "
                       "--notes-file")
    meaning = md_section(text, MEANING)
    if not meaning:
        out.append(f"no '{MEANING}' section")
    else:
        found = norm_units(meaning)
        if any(STALE_CLAIM.search(u) for u in found):
            out.append(f"{MEANING}: still claims Model B has no release.yml")
        if not any("release.yml" in u and not STALE_CLAIM.search(u) for u in found):
            out.append(f"{MEANING}: no corrected paragraph naming Model B's release.yml")
    return out


#: A note in §S7's form.
GOOD = (
    "# Release automation\n"
    "\n"
    "## The shape\n"
    "\n"
    "1. **`create-release`** — `gh release create \"$TAG\" --generate-notes`, guarded by\n"
    "   `gh release view`.\n"
    "\n"
    "**Note (2026-10-14):** Model B's `create-release` now passes the tag's `CHANGELOG.md`\n"
    "section with `--notes-file` instead.\n"
    "\n"
    "## Traps\n"
    "\n"
    "x\n"
    "\n"
    "## What this means for Model B\n"
    "\n"
    "Model B runs Crucible's shape in its own `release.yml` since 2026-09-24.\n"
)


class ResearchDocCheckerProofTest(unittest.TestCase):
    """The checker, both ways on sample text."""

    def test_the_conforming_note_passes(self):
        self.assertEqual(research_doc_findings(GOOD), [])

    def test_each_departure_is_reported_alone(self):
        cases = {
            "the record dropped": (
                GOOD.replace("`gh release create \"$TAG\" --generate-notes`", "a release"),
                f"{SHAPE}: the sourced record of Crucible's create-release is gone"),
            "the note undated": (
                GOOD.replace("**Note (2026-10-14):**", "**Note:**"),
                f"{SHAPE}: no dated note that Model B's create-release now uses --notes-file"),
            "the note without --notes-file": (
                GOOD.replace("with `--notes-file` instead", "as the body"),
                f"{SHAPE}: no dated note that Model B's create-release now uses --notes-file"),
            "the note outside The shape": (
                GOOD.replace("**Note (2026-10-14):** Model B's `create-release` now passes the "
                             "tag's `CHANGELOG.md`\nsection with `--notes-file` instead.\n\n", "")
                .replace("x\n", "x\n\n**Note (2026-10-14):** Model B's `create-release` now "
                         "passes `--notes-file`.\n"),
                f"{SHAPE}: no dated note that Model B's create-release now uses --notes-file"),
        }
        for label, (text, expected) in cases.items():
            with self.subTest(case=label):
                self.assertEqual(research_doc_findings(text), [expected])

    def test_the_stale_paragraph_is_reported_as_the_claim_and_as_no_correction(self):
        stale = GOOD.replace("Model B runs Crucible's shape in its own `release.yml` since "
                             "2026-09-24.",
                             "Model B has **no** `release.yml`. Releases are manual uploads.")
        self.assertEqual(research_doc_findings(stale), [
            f"{MEANING}: still claims Model B has no release.yml",
            f"{MEANING}: no corrected paragraph naming Model B's release.yml"])
        both = stale.replace("Releases are manual uploads.\n", "Releases are manual uploads.\n\n"
                             "Model B now runs its own `release.yml`.\n")
        self.assertEqual(research_doc_findings(both),
                         [f"{MEANING}: still claims Model B has no release.yml"],
                         "a corrected paragraph beside the stale claim does not excuse it")

    def test_a_missing_paragraph_or_section_is_reported(self):
        self.assertEqual(
            research_doc_findings(GOOD.replace(
                "Model B runs Crucible's shape in its own `release.yml` since 2026-09-24.\n",
                "Nothing here.\n")),
            [f"{MEANING}: no corrected paragraph naming Model B's release.yml"])
        self.assertEqual(research_doc_findings("# Note\n\nNothing.\n"),
                         [f"no '{SHAPE}' section", f"no '{MEANING}' section"])


class ResearchDocTest(unittest.TestCase):
    """§S7/AC — the real research note carries the dated note and the corrected paragraph."""

    def test_the_research_doc_records_notes_file_and_drops_the_no_release_yml_claim(self):
        self.assertTrue(RESEARCH_DOC.is_file(), f"{RESEARCH_DOC} must exist")
        self.assertEqual(research_doc_findings(RESEARCH_DOC.read_text(encoding="utf-8")), [])


#: CR-MDB-067 §S6 — a 2026-09-24 section in the edited form.
ADOPTED_GOOD = (
    "# Release automation\n"
    "\n"
    "## What Model B adopted (2026-09-24, user rulings)\n"
    "\n"
    "- **Automate like Crucible:** `release.yml` runs `create-release` and a manual\n"
    "  `rehearse-testpypi`.\n"
    "- **Note (2026-10-14, CR-MDB-067):** the manual `rehearse-testpypi` became the `rehearse` job,\n"
    "  run on every release or hotfix push.\n"
    "\n"
    "### Setup status (user, 2026-09-24)\n"
    "\n"
    "- [x] Environments `pypi`, `npm`\n"
    "- [ ] The `testpypi` environment admits `release/**` and `hotfix/**` and has no required\n"
    "      reviewers\n"
    "\n"
    "## What Model B adopted (2026-10-14, user rulings at CR-MDB-058's gap analysis)\n"
    "\n"
    "- Later rulings.\n"
)
REHEARSAL_NOTE_TEXT = ("- **Note (2026-10-14, CR-MDB-067):** the manual `rehearse-testpypi` became the "
                       "`rehearse` job,\n  run on every release or hotfix push.\n")
TESTPYPI_SETUP_TEXT = ("- [ ] The `testpypi` environment admits `release/**` and `hotfix/**` and has no "
                       "required\n      reviewers\n")


class RehearsalNoteCheckerProofTest(unittest.TestCase):
    """CR-MDB-067 §S6 — :func:`rehearsal_note_findings`, both ways on sample text."""

    def test_the_conforming_section_passes(self):
        self.assertIn(REHEARSAL_NOTE_TEXT, ADOPTED_GOOD)
        self.assertIn(TESTPYPI_SETUP_TEXT, ADOPTED_GOOD)
        self.assertEqual(rehearsal_note_findings(ADOPTED_GOOD), [])

    def test_each_element_of_the_dated_note_bites_alone(self):
        for old, new in (("**Note (2026-10-14, CR-MDB-067):**", "**Note:**"),
                         ("the manual `rehearse-testpypi` became", "`rehearse-testpypi` became"),
                         ("the `rehearse` job", "a new job"),
                         ("on every release or hotfix push", "on a dispatch"),
                         ("every release or hotfix push", "a release or hotfix push")):
            with self.subTest(removed=old):
                self.assertEqual(ADOPTED_GOOD.count(old), 1, old)
                self.assertEqual(rehearsal_note_findings(ADOPTED_GOOD.replace(old, new)),
                                 [NO_REHEARSAL_NOTE])
        self.assertEqual(rehearsal_note_findings(ADOPTED_GOOD.replace(
            "on every release or hotfix push", "on every push to a release or hotfix branch")), [],
            "'every push to a release or hotfix branch' reads the same")

    def test_the_dated_note_counts_only_in_the_2026_09_24_section(self):
        moved = ADOPTED_GOOD.replace(REHEARSAL_NOTE_TEXT, "").replace(
            "- Later rulings.\n", "- Later rulings.\n" + REHEARSAL_NOTE_TEXT)
        self.assertEqual(rehearsal_note_findings(moved), [NO_REHEARSAL_NOTE])

    def test_each_element_of_the_setup_line_bites_alone(self):
        for old, new in (("The `testpypi` environment", "The environment"),
                         ("`testpypi` environment admits", "`testpypi` admits"),
                         ("`release/**` and ", ""), (" and `hotfix/**`", ""),
                         ("has no required\n      reviewers", "has required\n      reviewers")):
            with self.subTest(removed=old):
                self.assertEqual(ADOPTED_GOOD.count(old), 1, old)
                self.assertEqual(rehearsal_note_findings(ADOPTED_GOOD.replace(old, new)),
                                 [NO_TESTPYPI_SETUP])
        self.assertEqual(rehearsal_note_findings(ADOPTED_GOOD.replace(
            "has no required\n      reviewers", "carries no required reviewers")), [])

    def test_the_setup_line_counts_only_in_the_setup_status_subsection(self):
        moved = ADOPTED_GOOD.replace(TESTPYPI_SETUP_TEXT, "").replace(
            REHEARSAL_NOTE_TEXT, REHEARSAL_NOTE_TEXT + TESTPYPI_SETUP_TEXT)
        self.assertEqual(rehearsal_note_findings(moved), [NO_TESTPYPI_SETUP])

    def test_todays_section_and_a_missing_section_are_reported(self):
        today = ADOPTED_GOOD.replace(REHEARSAL_NOTE_TEXT, "").replace(
            TESTPYPI_SETUP_TEXT, "- [ ] Environments `pypi`, `testpypi`, `npm` (required reviewers "
            "now available)\n")
        self.assertEqual(rehearsal_note_findings(today), [NO_REHEARSAL_NOTE, NO_TESTPYPI_SETUP])
        self.assertEqual(rehearsal_note_findings("# Note\n\nNothing.\n"),
                         ["no '## What Model B adopted (2026-09-24)' section"])


class RehearsalNoteTest(unittest.TestCase):
    """CR-MDB-067 §S6 — the real research note carries the dated rehearsal note and the
    testpypi setup line."""

    def test_the_research_doc_records_the_rehearse_job_and_the_testpypi_environment(self):
        self.assertEqual(rehearsal_note_findings(RESEARCH_DOC.read_text(encoding="utf-8")), [])


# ------------------------------------------------------------------ CR-MDB-070 §S6 ----

#: CR-MDB-070 §S6 — the dated note's exact words, matched in a normalised unit (lower-cased,
#: whitespace collapsed, backticks and ``*`` dropped).
SUPERSEDED_BY_070 = re.compile(r"\bsuperseded by cr-mdb-070, 2026-10-14\b")
#: The 2026-09-24 section's note: superseded, and create-release moved to the master push — one unit.
CREATE_RELEASE_MOVED = (
    r"(?<![\w-])create-release(?![\w-])", r"\bmaster push\b|\bpush(?:es)? (?:to|of) master\b",
)
#: The CR-MDB-067 gap-analysis section, and its bullet naming ``ci.yml`` as the CI workflow's home.
ADOPTED_067 = "## What Model B adopted (2026-10-14, user rulings at CR-MDB-067's gap analysis"
CI_YML = r"(?<![\w-])ci\.yml\b"
#: The CR-MDB-070 rulings section (recorded at its gap analysis), each ruling one unit.
ADOPTED_070 = "## What Model B adopted (2026-10-14, user rulings at CR-MDB-070's gap analysis"
CR070_RULINGS = (
    ("one workflow, every publish needs the tests, ci.yml retired",
     (r"\bone workflow\b", r"(?<![\w-])release\.yml\b", r"\bneeds:?", r"\bonly within one run\b",
      CI_YML, r"\bretired\b")),
    ("CI only on release/**, hotfix/** and master pushes and the published release, not on "
     "develop, not on pull requests",
     (r"(?<![\w-])release/(?!\w)", r"(?<![\w-])hotfix/(?!\w)", r"(?<![\w-])master\b",
      r"\bpublished release\b", r"\bnot on develop\b", r"\bnot on pull requests\b")),
    ("the release is created from the master push, the tag-push trigger dropped",
     (r"\brelease is created from the master push\b", r"\bnothing to\s+release\b",
      r"\btag-push trigger is dropped\b")),
    ("the registry publishes guard their ref",
     (r"\bregistry publishes guard their ref\b", r"\bancestor of origin/master\b")),
)
NO_070_SECTION = f"no '{ADOPTED_070})' section"
NO_0924_NOTE = (f"{ADOPTED_0924}): no dated note (superseded by CR-MDB-070, 2026-10-14) that "
                "create-release moved to the master push")
NO_067_CI_YML_NOTE = (f"{ADOPTED_067}): its ci.yml bullet carries no dated note (superseded by "
                      "CR-MDB-070, 2026-10-14)")


def cr070_research_findings(text: str) -> list[str]:
    """What ``text`` (the research note) lacks of CR-MDB-070 §S6: the CR-MDB-070 rulings
    section, each ruling in one unit; the dated "superseded by CR-MDB-070, 2026-10-14" note in
    the 2026-09-24 section saying ``create-release`` moved to the ``master`` push; and the same
    dated note on the CR-MDB-067 bullet naming ``ci.yml`` (in that bullet's own unit)."""
    out = []
    rulings = md_section(text, ADOPTED_070)
    if not rulings:
        out.append(NO_070_SECTION)
    else:
        units = norm_units(rulings)
        out += [f"{ADOPTED_070}): no ruling: {label}" for label, regexes in CR070_RULINGS
                if not any(all(re.search(rx, u) for rx in regexes) for u in units)]
    adopted = norm_units(md_section(text, ADOPTED_0924))
    if not any(SUPERSEDED_BY_070.search(u) and all(re.search(rx, u) for rx in CREATE_RELEASE_MOVED)
               for u in adopted):
        out.append(NO_0924_NOTE)
    ci_bullets = [u for u in norm_units(md_section(text, ADOPTED_067)) if re.search(CI_YML, u)]
    if not ci_bullets or not all(SUPERSEDED_BY_070.search(u) for u in ci_bullets):
        out.append(NO_067_CI_YML_NOTE)
    return out


#: CR-MDB-070 §S6 — a research note in the edited form.
CR070_GOOD = (
    "# Release automation\n"
    "\n"
    "## What Model B adopted (2026-09-24, user rulings)\n"
    "\n"
    "- **Automate like Crucible:** `release.yml` runs `create-release` on a tag push.\n"
    "- **Note (superseded by CR-MDB-070, 2026-10-14):** `create-release` moved to the `master`\n"
    "  push.\n"
    "\n"
    "### Setup status (user, 2026-09-24)\n"
    "\n"
    "- [x] Environments\n"
    "\n"
    "## What Model B adopted (2026-10-14, user rulings at CR-MDB-067's gap analysis)\n"
    "\n"
    "- **The skill carries the CI rule in plain words.** The concrete CI workflow lives only in\n"
    "  `.github/workflows/ci.yml` (superseded by CR-MDB-070, 2026-10-14: the tests are a job of\n"
    "  `release.yml`). No per-stack CI snippet.\n"
    "\n"
    "## What Model B adopted (2026-10-14, user rulings at CR-MDB-070's gap analysis)\n"
    "\n"
    "- **One workflow.** The tests are a job inside `release.yml`, and every publish job `needs:`\n"
    "  them. `needs:` orders jobs only within one run, so a separate CI workflow cannot gate a\n"
    "  publish. `ci.yml` is retired.\n"
    "- **CI runs only on release candidates and production:** pushes to `release/**`, `hotfix/**`\n"
    "  and `master`, and the published release. Not on `develop`, not on pull requests.\n"
    "- **The release is created from the `master` push** for the `X.Y.Z` tag at `HEAD` (none →\n"
    "  nothing to release); the tag-push trigger is dropped.\n"
    "- **The registry publishes guard their ref:** a bare `X.Y.Z` tag whose commit is an ancestor\n"
    "  of `origin/master`.\n"
    "\n"
    "## What this means for Model B\n"
    "\n"
    "Text.\n"
)
NOTE_0924_TEXT = ("- **Note (superseded by CR-MDB-070, 2026-10-14):** `create-release` moved to the "
                  "`master`\n  push.\n")
NOTE_067_TEXT = (" (superseded by CR-MDB-070, 2026-10-14: the tests are a job of\n"
                 "  `release.yml`)")


class Cr070ResearchCheckerProofTest(unittest.TestCase):
    """CR-MDB-070 §S6 — :func:`cr070_research_findings`, both ways on sample text."""

    def test_the_conforming_note_passes(self):
        self.assertIn(NOTE_0924_TEXT, CR070_GOOD)
        self.assertIn(NOTE_067_TEXT, CR070_GOOD)
        self.assertEqual(cr070_research_findings(CR070_GOOD), [])

    def test_todays_text_without_the_two_notes_is_reported_for_both(self):
        today = CR070_GOOD.replace(NOTE_0924_TEXT, "").replace(NOTE_067_TEXT, "")
        self.assertEqual(cr070_research_findings(today), [NO_0924_NOTE, NO_067_CI_YML_NOTE])

    def test_each_element_of_the_0924_note_bites_alone(self):
        for old, new in (("superseded by CR-MDB-070, 2026-10-14", "superseded"),
                         ("(superseded by CR-MDB-070, 2026-10-14):** `create",
                          "(superseded by CR-MDB-070, 2026-10-15):** `create"),
                         ("`create-release` moved to", "the release job moved to"),
                         ("moved to the `master`\n  push", "moved to a dispatch")):
            with self.subTest(removed=old):
                self.assertEqual(NOTE_0924_TEXT.count(old), 1, old)
                self.assertEqual(cr070_research_findings(CR070_GOOD.replace(
                    NOTE_0924_TEXT, NOTE_0924_TEXT.replace(old, new))), [NO_0924_NOTE])
        self.assertEqual(cr070_research_findings(CR070_GOOD.replace(
            NOTE_0924_TEXT, NOTE_0924_TEXT.replace("Superseded", "superseded").replace(
                "(superseded", "(Superseded"))), [], "the note's case does not matter")

    def test_the_0924_note_counts_only_in_the_2026_09_24_section(self):
        moved = CR070_GOOD.replace(NOTE_0924_TEXT, "").replace(
            "## What this means for Model B\n\nText.\n",
            "## What this means for Model B\n\nText.\n\n" + NOTE_0924_TEXT)
        self.assertEqual(cr070_research_findings(moved), [NO_0924_NOTE])

    def test_the_067_note_sits_on_the_ci_yml_bullet_itself(self):
        undated = CR070_GOOD.replace(NOTE_067_TEXT, " (superseded by CR-MDB-070)")
        self.assertEqual(cr070_research_findings(undated), [NO_067_CI_YML_NOTE])
        beside = CR070_GOOD.replace(NOTE_067_TEXT, "").replace(
            " No per-stack CI snippet.\n",
            " No per-stack CI snippet.\n- Note: superseded by CR-MDB-070, 2026-10-14.\n")
        self.assertEqual(cr070_research_findings(beside), [NO_067_CI_YML_NOTE],
                         "a note in another bullet does not mark the ci.yml bullet")
        second = CR070_GOOD.replace(
            "No per-stack CI snippet.\n",
            "No per-stack CI snippet.\n- A second bullet also names `ci.yml`.\n")
        self.assertEqual(cr070_research_findings(second), [NO_067_CI_YML_NOTE],
                         "every bullet naming ci.yml carries the note")
        gone = CR070_GOOD.replace(
            "## What Model B adopted (2026-10-14, user rulings at CR-MDB-067's gap analysis)\n", "")
        self.assertIn(NO_067_CI_YML_NOTE, cr070_research_findings(gone))

    def test_each_cr070_ruling_bites_alone_and_a_missing_section_is_reported(self):
        labels = [label for label, _ in CR070_RULINGS]
        edits = (("`ci.yml` is retired.", "`ci.yml` stays."),
                 (" Not on `develop`, not on pull requests.", ""),
                 ("the tag-push trigger is dropped", "the tag push still releases"),
                 ("an ancestor\n  of `origin/master`", "a tag"))
        for label, (old, new) in zip(labels, edits, strict=True):
            with self.subTest(ruling=label):
                self.assertEqual(CR070_GOOD.count(old), 1, old)
                self.assertEqual(cr070_research_findings(CR070_GOOD.replace(old, new)),
                                 [f"{ADOPTED_070}): no ruling: {label}"])
        self.assertEqual(cr070_research_findings(CR070_GOOD.replace(
            "## What Model B adopted (2026-10-14, user rulings at CR-MDB-070's gap analysis)\n",
            "## Later\n")), [NO_070_SECTION])


class Cr070ResearchNoteTest(unittest.TestCase):
    """CR-MDB-070 §S6 — the real research note carries the CR-MDB-070 rulings and the two dated
    "superseded by CR-MDB-070, 2026-10-14" notes."""

    def test_the_research_doc_records_the_cr070_rulings_and_supersedes_the_older_entries(self):
        self.assertEqual(cr070_research_findings(RESEARCH_DOC.read_text(encoding="utf-8")), [])


#: CR-MDB-070 §S6 — CR-MDB-067's spec, whose §S2 and §S3 each carry one dated line.
CR_067 = REPO_ROOT / "docs" / "changes" / "CR-MDB-067-release-rehearsal-and-ci.md"
CR_067_SUPERSEDED_SECTIONS = ("### §S2", "### §S3")


def cr067_superseded_findings(text: str) -> list[str]:
    """Each of :data:`CR_067_SUPERSEDED_SECTIONS` of ``text`` (CR-MDB-067's spec) not carrying
    "superseded by CR-MDB-070, 2026-10-14" exactly once (case-insensitive, however wrapped)."""
    out = []
    for heading in CR_067_SUPERSEDED_SECTIONS:
        section = md_section(text, heading, stop_prefix="#")
        count = len(SUPERSEDED_BY_070.findall(normalise(section))) if section else 0
        if count != 1:
            out.append(f"{heading}: carries 'superseded by CR-MDB-070, 2026-10-14' {count} times, "
                       "not once")
    return out


CR067_GOOD = (
    "# CR-MDB-067\n"
    "\n"
    "### §S1 — The version stamp\n"
    "\n"
    "Text.\n"
    "\n"
    "### §S2 — The rehearsal job\n"
    "\n"
    "Superseded by CR-MDB-070, 2026-10-14.\n"
    "\n"
    "- **Triggers.** text\n"
    "\n"
    "### §S3 — The CI test workflow\n"
    "\n"
    "Superseded by CR-MDB-070,\n2026-10-14.\n"
    "\n"
    "### §S4 — The suite\n"
)


class Cr067SupersededLinesProofTest(unittest.TestCase):
    """CR-MDB-070 §S6 — :func:`cr067_superseded_findings`, both ways on sample text."""

    def test_the_conforming_spec_passes(self):
        self.assertEqual(cr067_superseded_findings(CR067_GOOD), [])

    def test_a_missing_or_doubled_line_is_reported_per_section(self):
        s2_fault = "### §S2: carries 'superseded by CR-MDB-070, 2026-10-14' 0 times, not once"
        s3_fault = "### §S3: carries 'superseded by CR-MDB-070, 2026-10-14' 0 times, not once"
        self.assertEqual(cr067_superseded_findings(CR067_GOOD.replace(
            "Superseded by CR-MDB-070, 2026-10-14.\n", "")), [s2_fault])
        self.assertEqual(cr067_superseded_findings(CR067_GOOD.replace(
            "Superseded by CR-MDB-070,\n2026-10-14.\n", "Superseded by CR-MDB-070.\n")), [s3_fault])
        self.assertEqual(cr067_superseded_findings(CR067_GOOD.replace(
            "- **Triggers.** text\n",
            "- **Triggers.** text\n\nsuperseded by CR-MDB-070, 2026-10-14.\n")),
            ["### §S2: carries 'superseded by CR-MDB-070, 2026-10-14' 2 times, not once"])
        moved = CR067_GOOD.replace("Superseded by CR-MDB-070, 2026-10-14.\n", "").replace(
            "Text.\n", "Text.\n\nSuperseded by CR-MDB-070, 2026-10-14.\n")
        self.assertEqual(cr067_superseded_findings(moved), [s2_fault],
                         "a line in §S1 is not §S2's")
        self.assertEqual(cr067_superseded_findings("# Other\n"), [s2_fault, s3_fault])


class Cr067SupersededLinesTest(unittest.TestCase):
    """CR-MDB-070 §S6 — CR-MDB-067's §S2 and §S3 each carry one dated line, "superseded by
    CR-MDB-070, 2026-10-14" (``CiWorkflowAmendmentNoteTest`` is the precedent)."""

    def test_cr_mdb_067_s2_and_s3_each_record_their_supersession_by_cr_mdb_070(self):
        self.assertTrue(CR_067.is_file(), f"{CR_067} must exist")
        self.assertEqual(cr067_superseded_findings(CR_067.read_text(encoding="utf-8")), [])


if __name__ == "__main__":
    unittest.main()
