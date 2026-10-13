"""The verb surface the ``crucible`` skill documents, and the release runs ``git-workflow`` files
(CR-MDB-057 §S5; DN-multi-harness-deploy-model §D21).

Crucible 0.3.0 put new verbs and flags on all five installed clients: ``--cycle``/``--release`` on
the run verbs, ``history``, ``landings``, ``project-meta``, ``cr-plan --points``, the recorded
``cycle-add`` insert, ``cycle-skip``, ``gate-respond`` and the gate run's own board identity. The
skill's per-stack table and verb sections say so, with the exceptions the installed ``--help``
shows named: rust ``regression`` takes no ``--cycle``, and ``--log`` is absent on rust
``regression`` and on ``pre-merge-gate`` for the arduino, mvn and rust clients.
Contract: ``docs/changes/CR-MDB-057-crucible-0-3-0-doc-sync.md`` §S5.

Class map:

- ``CrucibleSkillVerbSurfaceTest`` — §S5/AC: every statement in ``VERB_SURFACE_STATEMENTS`` is made
  by one unit (a paragraph, a bullet with its continuation lines, a table row) of the ``crucible``
  skill; no "clientless stack" clause or "documented urllib procedure" remains. The detector is
  proven both ways on a synthetic skill.
- ``GitWorkflowReleaseRunsTest`` — §S5/AC: ``git-workflow`` § Releases files the release's
  ``regression`` and ``pre-merge-gate`` verification runs with ``--release <label>``.

What this module does not do: it reads no client and checks no flag against a client's ``--help``.
That check is the extended ``test_client_examples_use_verbs_the_released_clients_expose``
(``tests/test_skill_bundle_guards.py``, §S7), so there is one gate for it, not two. The
``project-meta`` paragraph (§S3) is gated by ``CrucibleSkillProjectMetaTest``
(``tests/test_crucible_project_config.py``) and the gate's ``[gate] skip`` declaration (§S2) by
``tests/test_client_verb_sweep.py``; neither is repeated here.

Stdlib only.
"""

import re
import unittest
from pathlib import Path

from tests._helpers import md_section
from tests.test_board_holds_the_queue import norm_units

REPO_ROOT = Path(__file__).resolve().parent.parent
CRUCIBLE_SKILL = REPO_ROOT / "skills-src" / "crucible" / "SKILL.md"
GIT_WORKFLOW_SKILL = REPO_ROOT / "skills-src" / "git-workflow" / "SKILL.md"

#: The run verbs §S5 names: ``test``, the tier verbs, ``regression`` and ``pre-merge-gate``.
RUN_VERBS = ("test", "unit", "module", "integration", "e2e", "bdd", "regression",
             "pre-merge-gate")


def _word(token: str) -> str:
    """``token`` as a whole verb or flag: not part of a longer hyphenated word."""
    return r"(?<![\w-])" + re.escape(token) + r"(?![\w-])"


#: §S5: what the ``crucible`` skill states, on normalised text (backticks and emphasis dropped,
#: lower-cased). Each entry is ``(what, regexes)``; one unit must match every regex of an entry.
VERB_SURFACE_STATEMENTS = (
    ("the run verbs take --cycle and --release, not auto-ingest",
     (_word("--cycle"), _word("--release"), *(_word(v) for v in RUN_VERBS),
      r"\b(?:not|except|excluding|never|nor)\b[^.;]{0,30}auto-ingest"
      r"|auto-ingest[^.;]{0,60}\b(?:not|never|no|neither)\b")),
    ("--release files the run as release verification",
     (_word("--release"), r"\brelease verification\b")),
    ("--release is never given beside --cycle",
     (_word("--release"),
      r"\b(?:never|not)\b[^.;]{0,30}\b(?:beside|with|alongside|together with)\b[^.;]{0,10}"
      + _word("--cycle"))),
    ("the exception: rust regression takes no --cycle",
     (r"\brust\b[^.;]{0,80}" + _word("regression") + r"[^.;]{0,80}\b(?:no|not|without|lacks?)\b"
      r"[^.;]{0,20}" + _word("--cycle"),)),
    ("history lists releases that shipped or have a completed CR; planned ones are read with "
     "queue --fields release,seq,points,dependsOn",
     (_word("history"), r"\bshipped\b", r"\bcompleted cr\b",
      r"queue --fields release,\s?seq,\s?points,\s?dependson\b")),
    ("queue --full shows every column, including warning",
     (r"queue --full\b", r"\bwarning\b")),
    ("status shows the work in flight (status contract 3.0.0)",
     (_word("status"), r"\bwork in flight\b", r"\b3\.0\.0\b")),
    ("landings lists each closed CR's merge commit",
     (_word("landings"), r"\bmerge commits?\b")),
    ("cr-plan --points takes the scale 1, 2, 3, 5, 8, 13",
     (_word("cr-plan"), _word("--points"), r"\b1,\s?2,\s?3,\s?5,\s?8,\s?13\b")),
    ("re-sending a CR's title, release and wave with --points changes only its points",
     (_word("--points"), r"\bonly (?:its|the) points\b")),
    ("cycle-add: a fix append needs nothing more; --before or another kind is a recorded plan "
     "change needing --reason, --cause (spec-design or gap-analysis) and --spec-ref",
     (_word("cycle-add"), r"\bfix\b[^.;]{0,20}\bappend", _word("--before"), _word("--reason"),
      _word("--cause"), r"\bspec-design\b", r"\bgap-analysis\b", _word("--spec-ref"),
      r"\brecorded plan change\b")),
    ("cycle-skip takes the same three flags and is recorded as a failure",
     (_word("cycle-skip"),
      r"--reason[^.;]{0,40}--cause[^.;]{0,40}--spec-ref|\bsame three flags\b",
      r"\brecorded as a failure\b")),
    ("gate-run gives each run its own board identity <caller>·gate·<run>, removed when the run "
     "ends; the decision stays the caller's",
     (_word("gate-run"), r"·gate·", r"\bremoved when\b", r"\bcaller'?s\b")),
    ("gate-respond answers with --action approve|fix|skip, recorded even when the wait elapses, "
     "and has no --release",
     (_word("gate-respond"), _word("--action"), r"\bapprove\b", r"\bfix\b", r"\bskip\b",
      r"\beven when the wait elapses\b",
      r"\bno " + _word("--release") + r"|\b(?:not|never) (?:take|takes|accept|accepts) "
      + _word("--release") + r"|\bwithout " + _word("--release"))),
    ("after an elapsed wait, check status and reattach with gate-run --intent <goal>",
     (r"\breattach", r"gate-run --intent\b", _word("status"))),
    ("client output goes to a file: --log where the verb takes it, a redirect otherwise, never "
     "through | head",
     (_word("--log"), r"\bredirect", r"\b(?:never|not)\b[^.;]{0,60}\|\s?head\b")),
    ("--log is absent on rust regression and on pre-merge-gate for arduino, mvn and rust",
     (_word("--log"), r"\b(?:no|not|absent|lacks?|without)\b",
      r"\brust\b[^.;]{0,60}" + _word("regression"), _word("pre-merge-gate"), r"\barduino\b",
      r"\b(?:mvn|java)\b", r"\brust\b")),
    ("history, landings, project-meta, cycle-skip and gate-respond are on all five clients",
     (r"\ball five\b|\bevery client\b|\bfleet-wide\b", _word("history"), _word("landings"),
      _word("project-meta"), _word("cycle-skip"), _word("gate-respond"))),
)

#: §S5: what no longer appears — every stack has a client.
RETIRED_CLAUSES = (
    ("a clientless-stack clause", re.compile(r"\bclient-?less\b", re.I)),
    ("the documented urllib procedure", re.compile(r"\burllib procedure\b", re.I)),
)


def verb_surface_findings(text: str) -> list[str]:
    """What ``text`` (the ``crucible`` skill) lacks of §S5's statements, and the retired clauses it
    still carries."""
    found = norm_units(text)
    out = [f"the skill does not state that {what}" for what, rxs in VERB_SURFACE_STATEMENTS
           if not any(all(re.search(rx, u) for rx in rxs) for u in found)]
    out += [f"the skill still carries {what}" for what, rx in RETIRED_CLAUSES if rx.search(text)]
    return out


#: A synthetic skill making every statement once, one bullet each — the passing shape.
GOOD_SKILL = """# Crucible

## Verbs on all five clients

- The run verbs `test`, `unit`, `module`, `integration`, `e2e`, `bdd`, `regression` and
  `pre-merge-gate` take `--cycle` and `--release <label>`; not `auto-ingest`.
- `--release <label>` files the run as release verification under a declared release.
- `--release` is never given beside `--cycle`.
- The exception: rust `regression` takes no `--cycle`.
- `history` lists past releases: one appears once it has shipped or has a completed CR, so read
  planned ones with `queue --fields release,seq,points,dependsOn`.
- `queue --full` shows every column, including `warning`.
- `status` shows the work in flight (status contract 3.0.0).
- `landings` lists each closed CR's merge commit.
- `cr-plan --points` takes a score on the scale 1, 2, 3, 5, 8, 13.
- Re-sending a CR's title, release and wave with `--points` changes only its points.
- `cycle-add`: a `fix` append needs nothing more; a `--before <cycle id>` insert or any other kind
  is a recorded plan change needing `--reason`, `--cause` (`spec-design` or `gap-analysis`) and
  `--spec-ref`.
- `cycle-skip <cycle id>` takes the same three flags; a skipped cycle is recorded as a failure.
- `gate-run` gives each run its own board identity, `<caller>·gate·<run>`, removed when the run
  ends; the decision stays the caller's.
- `gate-respond` answers a held step with `--action approve|fix|skip`; a decision the tool accepted
  is recorded even when the wait elapses. It has no `--release`.
- After a wait that elapsed mid-step, check `status` and reattach with `gate-run --intent <goal>`.
- Client output goes to a file — `--log <path>` where the verb takes it, a redirect otherwise —
  never through `| head`.
- `--log` is absent on rust `regression`, and on `pre-merge-gate` for the arduino, mvn and rust
  clients.
- `history`, `landings`, `project-meta`, `cycle-skip` and `gate-respond` are on all five clients.
"""

#: For each statement, a cut that removes it from ``GOOD_SKILL`` and nothing else.
GOOD_SKILL_CUTS = (
    ("; not `auto-ingest`", "the run verbs take --cycle and --release"),
    ("files the run as release verification", "release verification"),
    ("is never given beside `--cycle`", "never given beside --cycle"),
    ("takes no `--cycle`.", "rust regression takes no --cycle"),
    (" or has a completed CR", "history lists releases"),
    ("including `warning`", "queue --full"),
    ("the work in flight", "status shows the work in flight"),
    ("merge commit.", "landings lists"),
    ("1, 2, 3, 5, 8, 13", "cr-plan --points takes the scale"),
    ("changes only its points", "changes only its points"),
    ("is a recorded plan change", "cycle-add"),
    ("is recorded as a failure", "cycle-skip"),
    ("`<caller>·gate·<run>`, ", "gate-run gives each run"),
    (" It has no `--release`.", "gate-respond answers"),
    ("reattach with", "reattach"),
    ("a redirect otherwise", "client output goes to a file"),
    ("on `pre-merge-gate` for the arduino, mvn and rust\n  clients", "--log is absent"),
    ("are on all five clients", "on all five clients"),
)


class CrucibleSkillVerbSurfaceTest(unittest.TestCase):
    """§S5/AC — the ``crucible`` skill's verb sections name the 0.3.0 surface on all five clients,
    with the installed ``--help``'s exceptions."""

    def test_the_crucible_skill_documents_the_0_3_0_verb_surface(self):
        self.assertEqual(verb_surface_findings(CRUCIBLE_SKILL.read_text(encoding="utf-8")), [])

    def test_the_verb_surface_detector_passes_the_good_shape(self):
        self.assertEqual(verb_surface_findings(GOOD_SKILL), [])

    def test_the_verb_surface_detector_bites_on_each_missing_statement(self):
        self.assertEqual(len(GOOD_SKILL_CUTS), len(VERB_SURFACE_STATEMENTS),
                         "one cut per statement")
        for cut, missing in GOOD_SKILL_CUTS:
            with self.subTest(cut=cut):
                self.assertIn(cut, GOOD_SKILL)
                found = verb_surface_findings(GOOD_SKILL.replace(cut, " "))
                self.assertEqual(len(found), 1, found)
                self.assertIn(missing, found[0])

    def test_the_verb_surface_detector_bites_on_a_retired_clause(self):
        for clause in ("on a clientless stack, the documented urllib procedure",):
            with self.subTest(clause=clause):
                found = verb_surface_findings(GOOD_SKILL + f"\nUse the client (or, {clause}).\n")
                self.assertEqual(sorted(found), [
                    "the skill still carries a clientless-stack clause",
                    "the skill still carries the documented urllib procedure"])

    def test_a_run_verb_statement_that_includes_auto_ingest_bites(self):
        text = GOOD_SKILL.replace("; not `auto-ingest`", " and `auto-ingest`")
        self.assertEqual(len(verb_surface_findings(text)), 1)


#: §S5: the release's verification runs, filed under the release (normalised text).
RELEASE_RUN_STATEMENT = (_word("regression"), _word("pre-merge-gate"), _word("--release"))


def release_run_findings(text: str) -> list[str]:
    """What ``text`` (the ``git-workflow`` skill) lacks: a unit of § Releases filing the
    ``regression`` and ``pre-merge-gate`` verification runs with ``--release <label>``."""
    section = md_section(text, "## Releases")
    if not section:
        return ["there is no § Releases"]
    if any(all(re.search(rx, u) for rx in RELEASE_RUN_STATEMENT) for u in norm_units(section)):
        return []
    return ["§ Releases does not file regression and pre-merge-gate with --release <label>"]


class GitWorkflowReleaseRunsTest(unittest.TestCase):
    """§S5/AC — ``git-workflow`` § Releases files the release verification runs under the
    release."""

    def test_releases_files_regression_and_pre_merge_gate_with_release(self):
        self.assertEqual(release_run_findings(GIT_WORKFLOW_SKILL.read_text(encoding="utf-8")), [])

    def test_the_release_run_detector_both_ways(self):
        good = ("# Git\n\n## Releases (NON-NEGOTIABLE)\n\n- The release's verification runs, "
                "`regression` and `pre-merge-gate`, are filed with `--release <label>`.\n\n"
                "## Next\n")
        self.assertEqual(release_run_findings(good), [])
        for cut in ("`regression` and ", "`pre-merge-gate`, ", " with `--release <label>`"):
            with self.subTest(cut=cut):
                self.assertEqual(len(release_run_findings(good.replace(cut, " "))), 1)
        outside = good.replace("## Releases (NON-NEGOTIABLE)\n\n- The", "## Releases\n\nx\n\n## Other\n\n- The")
        self.assertEqual(len(release_run_findings(outside)), 1,
                         "the statement counts only inside § Releases")


if __name__ == "__main__":
    unittest.main()
