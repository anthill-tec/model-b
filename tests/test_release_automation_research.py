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

Stdlib only.
"""

import re
import unittest
from pathlib import Path

from tests._helpers import md_section
from tests.test_board_holds_the_queue import norm_units

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


if __name__ == "__main__":
    unittest.main()
