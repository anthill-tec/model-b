"""``modelb-axi init`` writes a ``CHANGELOG.md`` skeleton at the root (CR-MDB-058 §S5).

Contract: ``docs/changes/CR-MDB-058-release-notes-and-rehearsal.md`` §S5 and its acceptance
criterion; rulings in ``docs/research/release-automation-crucible-procedure.md`` § "What Model B
adopted (2026-10-14 …)" (Templates: ``init`` writes a ``CHANGELOG.md`` skeleton for every project).

Class map:

- ``ScaffoldChangelogPlanTest`` — ``plan_files`` lists ``CHANGELOG.md`` once, at the root, for a
  standalone and a monorepo project, and never as ``<sub>/CHANGELOG.md``.
- ``ScaffoldChangelogSkeletonTest`` — through the real ``run_init`` in a sandbox, for solo,
  ``multi:2`` and ``monorepo:a,b`` (every shape of ``tests.test_project_setup_section.SHAPES``):
  ``CHANGELOG.md`` appears once in the envelope's ``planned`` and once in ``emitted``; exactly one
  is written, at the root; it passes the §S1 form checker (``changelog_form_faults``, the one copy
  in ``tests/_helpers.py``) in §S1's starting form — a ``# Changelog`` title, an empty
  ``## [Unreleased]`` as the only ``##`` section, no release section and no compare link.
  ``--dry-run`` plans it once at the root and writes nothing.
- ``ExistingChangelogTest`` — a target already holding a ``CHANGELOG.md`` keeps it byte for byte;
  the envelope reports it in ``unmanaged`` (the field ``.envrc`` uses, CR-MDB-047 §S2), never in
  ``emitted`` or ``skipped``, with one ``unmanaged:`` warning naming it; the rest of the scaffold
  is still written. A ``CHANGELOG.md`` byte-identical to the skeleton ``init`` writes is left as
  it is and reported nowhere — not ``unmanaged``, not ``emitted``, no warning — as an
  ``.envrc`` already reading as ``init`` writes it is.

Isolation (NON-NEGOTIABLE): every ``init`` runs in process in the sandbox of
``tests.test_init_tool_verdicts`` (via ``tests.test_project_setup_section``'s case). No test
reads the real ``~/.local/share/modelb``, ``~/.pi`` or ``~/.crucible``.

Stdlib only.
"""

import re
import unittest

from modelb_axi import scaffold
from tests import test_project_setup_section as _setup
from tests._helpers import CHANGELOG_UNRELEASED_HEADING, changelog_form_faults

CHANGELOG = "CHANGELOG.md"
#: §S1: a compare link at the foot, ``[label]: url`` — the starting form has none.
COMPARE_LINK_RE = re.compile(r"^\[[^\]]+\]: ")


def starting_form_faults(text: str) -> list[str]:
    """What ``text`` lacks of §S1's starting form, beyond the form checker: a ``# Changelog``
    title as the first non-blank line, ``## [Unreleased]`` as the ONLY ``##`` heading (no release
    section), nothing under it, and no compare link."""
    lines = text.splitlines()
    nonblank = [ln for ln in lines if ln.strip()]
    faults = []
    if not nonblank or nonblank[0].rstrip() != "# Changelog":
        faults.append(f"the first line is not '# Changelog': {nonblank[:1]!r}")
    headings = [ln.rstrip() for ln in lines if ln.startswith("## ")]
    if headings != [CHANGELOG_UNRELEASED_HEADING]:
        faults.append(f"the ## headings are not exactly [Unreleased]: {headings!r}")
    stripped = [ln.rstrip() for ln in lines]
    if CHANGELOG_UNRELEASED_HEADING in stripped:
        body = []
        for line in lines[stripped.index(CHANGELOG_UNRELEASED_HEADING) + 1:]:
            if line.startswith("## ") or COMPARE_LINK_RE.match(line):
                break
            if line.strip():
                body.append(line)
        if body:
            faults.append(f"[Unreleased] is not empty: {body!r}")
    links = [ln for ln in lines if COMPARE_LINK_RE.match(ln)]
    if links:
        faults.append(f"a compare link: {links!r}")
    return faults


class StartingFormDetectorTest(unittest.TestCase):
    """The starting-form detector, both ways on sample text."""

    PREAMBLE = ("# Changelog\n\nAll notable changes are documented here, in the form of "
                "[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow "
                "[Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n\n")

    def test_the_starting_form_passes_and_each_departure_bites(self):
        good = self.PREAMBLE + "## [Unreleased]\n"
        self.assertEqual(starting_form_faults(good), [])
        self.assertEqual(changelog_form_faults(good), [])
        cases = {
            "no title": good.replace("# Changelog\n", "# Notes\n"),
            "a release section": good + "\n## [1.0.0] - 2026-10-14\n\n### Added\n\n- x.\n",
            "an entry under [Unreleased]": good + "\n### Added\n\n- x.\n",
            "a compare link": good + "\n[Unreleased]: https://example.invalid/compare/1.0.0...HEAD\n",
        }
        for label, text in cases.items():
            with self.subTest(case=label):
                self.assertEqual(len(starting_form_faults(text)), 1, starting_form_faults(text))


class ScaffoldChangelogPlanTest(unittest.TestCase):
    """§S5 — ``plan_files`` lists ``CHANGELOG.md`` once, at the root only."""

    def test_plan_files_lists_changelog_once_at_the_root(self):
        for subs in ([], [str(s) for s in _setup.SUBS]):
            with self.subTest(subs=subs):
                plan = scaffold.plan_files(subs)
                self.assertEqual(plan.count(CHANGELOG), 1, plan)
                self.assertEqual([p for p in plan if p.endswith("/" + CHANGELOG)], [],
                                 "§S5: a sub-project gets none")


class ScaffoldChangelogSkeletonTest(_setup._Case):
    """§S5/AC — solo, ``multi:2`` and ``monorepo:a,b``: one root ``CHANGELOG.md`` in §S1's
    starting form, planned once and emitted once, never written as ``<sub>/CHANGELOG.md``."""

    def test_every_shape_writes_one_root_changelog_in_its_starting_form(self):
        for mode, shape in _setup.SHAPES:
            with self.subTest(mode=mode, shape=shape):
                self.target = self.root / f"proj-{mode.replace(':', '')}-{shape.split(':')[0]}"
                axi, _err = self.init_ok(mode=mode, repo_shape=shape)
                planned, emitted = axi.get("planned", []), axi.get("emitted", [])
                self.assertEqual((planned.count(CHANGELOG), emitted.count(CHANGELOG)), (1, 1),
                                 f"planned={planned!r} emitted={emitted!r}")
                self.assertEqual([p for p in planned + emitted if p.endswith("/" + CHANGELOG)],
                                 [], "§S5: never written as <sub>/CHANGELOG.md")
                found = sorted(p.relative_to(self.target).as_posix()
                               for p in self.target.rglob(CHANGELOG))
                self.assertEqual(found, [CHANGELOG], "exactly one, at the root")
                text = self.text(CHANGELOG)
                self.assertEqual(changelog_form_faults(text), [], text)
                self.assertEqual(starting_form_faults(text), [], text)
                self.assertNotIn(CHANGELOG, axi.get("unmanaged", []),
                                 "a fresh target's skeleton is Model B's, not unmanaged")

    def test_dry_run_plans_changelog_once_at_the_root_and_writes_nothing(self):
        axi, _err = self.init_ok(mode=_setup.MULTI, repo_shape=_setup.MONOREPO, dry_run=True)
        planned = axi.get("planned", [])
        self.assertEqual(planned.count(CHANGELOG), 1, planned)
        self.assertEqual([p for p in planned if p.endswith("/" + CHANGELOG)], [], planned)
        self.assertEqual(axi.get("emitted", []), [], "a dry run emits nothing")
        self.assertFalse(self.target.exists(), "--dry-run writes nothing")


class ExistingChangelogTest(_setup._Case):
    """§S5/AC — an existing root ``CHANGELOG.md`` is never overwritten: left as it is and
    reported ``unmanaged``, as ``.envrc`` is."""

    #: A project's own changelog, in no particular form, with real UTF-8 in it.
    OWN = "# Release history — ours\n\n* 0.3 — first cut, written by hand\n".encode()

    def test_an_existing_changelog_is_kept_byte_for_byte_and_reported_unmanaged(self):
        self.target.mkdir()
        (self.target / CHANGELOG).write_bytes(self.OWN)
        axi, _err = self.init_ok()
        self.assertEqual((self.target / CHANGELOG).read_bytes(), self.OWN,
                         "§S5: the existing CHANGELOG.md is never overwritten")
        self.assertEqual(axi.get("unmanaged", []).count(CHANGELOG), 1,
                         f"§S5: reported unmanaged, once; axi={axi!r}")
        self.assertNotIn(CHANGELOG, axi.get("emitted", []), "an unmanaged file is not emitted")
        self.assertNotIn(CHANGELOG, axi.get("skipped", []), "unmanaged, not hand-modified")
        warned = [w for w in axi.get("warnings", [])
                  if w.startswith("unmanaged:") and CHANGELOG in w]
        self.assertEqual(len(warned), 1,
                         f"one `unmanaged:` warning names it; warnings={axi.get('warnings')!r}")
        self.assertTrue((self.target / ".env").is_file(), "the rest of the scaffold is written")
        self.assertTrue((self.target / "AGENTS.md").is_file(), "the rest of the scaffold is written")

    def test_a_changelog_identical_to_the_skeleton_is_left_silently_as_envrc_is(self):
        # The skeleton is what the real init writes into a fresh target.
        project_target = self.target
        self.target = self.root / "skeleton-source"
        self.init_ok()
        skeleton = (self.target / CHANGELOG).read_bytes()
        self.target = project_target
        self.target.mkdir()
        (self.target / CHANGELOG).write_bytes(skeleton)
        axi, _err = self.init_ok()
        self.assertEqual((self.target / CHANGELOG).read_bytes(), skeleton,
                         "the identical CHANGELOG.md is left as it is")
        # Mirrors write_envrc's identical case: left as it is, reported nowhere.
        self.assertNotIn(CHANGELOG, axi.get("unmanaged", []),
                         f"init's own skeleton is not unmanaged; axi={axi!r}")
        self.assertNotIn(CHANGELOG, axi.get("emitted", []), "an untouched file is not emitted")
        self.assertNotIn(CHANGELOG, axi.get("skipped", []), "an untouched file is not skipped")
        warned = [w for w in axi.get("warnings", []) if CHANGELOG in w]
        self.assertEqual(warned, [], "no warning names init's own skeleton")


if __name__ == "__main__":
    unittest.main()
