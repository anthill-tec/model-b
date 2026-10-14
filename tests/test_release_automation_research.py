"""The release-automation research note records Model B's release body (CR-MDB-058 §S7).

Contract: ``docs/changes/CR-MDB-058-release-notes-and-rehearsal.md`` §S7 and its acceptance
criterion "the research doc carries the dated note and the corrected paragraph". The note is
``docs/research/release-automation-crucible-procedure.md``:

- "The shape" keeps its sourced record of Crucible (``gh release create "$TAG"
  --generate-notes``) and gains a dated note that Model B's ``create-release`` now uses
  ``--notes-file``;
- "What this means for Model B" no longer claims Model B has no ``release.yml``.

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


if __name__ == "__main__":
    unittest.main()
