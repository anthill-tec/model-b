"""RED-phase tests for CR-MDB-010 (worktree-flow.py AXI output).

Asserts SS2 (codec deployment), SS3 (envelope emission for the `status`,
`next`, `progress` safe verbs), and SS4 (consumer-note grep gate) against
the LIVE ~/.claude tree and the DEPLOYED `worktree-flow.py` script on this
machine, invoked read-only against THIS repo (`--project-dir <repo>`).
Written before the GREEN-phase work (codec deployment + `_emit_axi`
conversion + skill consumer notes) lands, so these are expected to FAIL
against the current print-based state:
  - SS2: `~/.claude/scripts/toon.py` does not exist yet.
  - SS3: `status`/`next`/`progress` print plain text on stdout with an
    empty stderr (or crash via `sys.exit` before printing anything), so
    decoding stdout as TOON never yields a top-level `axi` envelope.
  - SS4: none of the worktree-flow-mentioning SKILL.md files carry the
    "stderr"/"TOON" consumer note yet.

Stdlib + subprocess only. The TOON codec used for the TEST's own decoding
is imported read-only from the Crucible source of truth
(`crucible:clients/toon.py`) via a read-only `sys.path` insert -- NOT the
not-yet-deployed `~/.claude/scripts/toon.py` copy, which is SS2's own
deliverable and does not exist yet.

No mutating worktree-flow verbs are invoked (`status`, `next`, `progress`
only, per SS1's "no mutating verbs in tests" scope note).
"""

import subprocess
import sys
import unittest
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
REPO_ROOT = Path(__file__).resolve().parent.parent

WORKTREE_FLOW = CLAUDE_DIR / "scripts" / "worktree-flow.py"
DEPLOYED_TOON = CLAUDE_DIR / "scripts" / "toon.py"
SKILLS_DIR = CLAUDE_DIR / "skills"

# Read-only sys.path insert for the TEST's OWN TOON decoding -- the source
# of truth crucible:clients/toon.py, NOT the not-yet-deployed
# ~/.claude/scripts/toon.py copy (SS2's own deliverable, doesn't exist yet).
_TOON_SRC_DIR = "/home/antonyj/Documents/data_projects/crucible/clients"
if _TOON_SRC_DIR not in sys.path:
    sys.path.insert(0, _TOON_SRC_DIR)
import toon  # noqa: E402  (source-of-truth codec, read-only import)


def _run_wf(*args, timeout=30):
    """Invoke the DEPLOYED worktree-flow.py read-only against THIS repo."""
    cmd = ["python3", str(WORKTREE_FLOW), *args,
           "--project-dir", str(REPO_ROOT)]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _decode_envelope(result, verb_label):
    """Decode `result.stdout` as TOON and return the `axi` sub-object,
    failing with a clear message (not a bare KeyError/decode traceback)
    when it isn't a valid AXI envelope yet -- exactly the gap RED expects."""
    try:
        obj = toon.decode(result.stdout)
    except Exception as exc:  # pragma: no cover - diagnostic path
        raise AssertionError(
            f"{verb_label}: stdout did not decode as TOON ({type(exc).__name__}: {exc}); "
            f"exit={result.returncode} stdout={result.stdout[:1000]!r} "
            f"stderr={result.stderr[:1000]!r}"
        )
    if "axi" not in obj:
        raise AssertionError(
            f"{verb_label}: decoded TOON object has no top-level 'axi' envelope key "
            f"(decoded keys: {list(obj.keys())}); exit={result.returncode} "
            f"stdout={result.stdout[:1000]!r} stderr={result.stderr[:1000]!r}"
        )
    return obj["axi"]


class WorktreeFlowCodecDeploymentTest(unittest.TestCase):
    """SS2 -- codec deployment (single AC bullet: exists + anchors + import)."""

    def test_deployed_toon_exists_with_anchors_and_is_importable(self):
        # POSITIVE -- the deployed copy must exist.
        self.assertTrue(
            DEPLOYED_TOON.is_file(),
            f"{DEPLOYED_TOON} must exist (deployed copy of crucible:clients/toon.py)",
        )
        content = DEPLOYED_TOON.read_text(encoding="utf-8")
        # POSITIVE -- both required header anchors must be present.
        self.assertIn(
            "DEPLOYED COPY", content,
            f"{DEPLOYED_TOON} must contain the header phrase 'DEPLOYED COPY'",
        )
        self.assertIn(
            "TRACKS", content,
            f"{DEPLOYED_TOON} must contain the header phrase 'TRACKS'",
        )
        # BEHAVIOURAL -- the exact import invocation from the AC must succeed
        # cleanly (no traceback on stderr).
        result = subprocess.run(
            ["python3", "-c",
             f"import sys; sys.path.insert(0,'{CLAUDE_DIR / 'scripts'}'); import toon"],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(
            result.returncode, 0,
            f"import of deployed toon.py must succeed (exit 0), got {result.returncode}; "
            f"stderr:\n{result.stderr}",
        )
        self.assertEqual(
            result.stderr.strip(), "",
            f"import of deployed toon.py must produce no stderr, got:\n{result.stderr}",
        )


class WorktreeFlowEnvelopeTest(unittest.TestCase):
    """SS3 -- envelope emission for the three converted safe verbs."""

    def test_status_stdout_decodes_to_ok_true_envelope_with_human_board_on_stderr(self):
        result = _run_wf("status")
        self.assertEqual(
            result.returncode, 0,
            f"status must exit 0, got {result.returncode}; stderr:\n{result.stderr}",
        )
        # NEGATIVE/bound -- the human board must be on stderr, not silently
        # dropped or left on stdout only.
        self.assertNotEqual(
            result.stderr.strip(), "",
            f"status stderr must be non-empty (the human board); "
            f"stdout was:\n{result.stdout[:500]!r}",
        )
        axi = _decode_envelope(result, "status")
        # POSITIVE -- exact verb + ok values required by the AC.
        self.assertEqual(
            axi.get("verb"), "status",
            f"axi.verb must equal 'status', got {axi.get('verb')!r}",
        )
        self.assertIs(
            axi.get("ok"), True,
            f"axi.ok must be True (bool), got {axi.get('ok')!r} "
            f"({type(axi.get('ok')).__name__})",
        )

    def test_next_unknown_track_no_db_row_yields_drained_decision(self):
        result = _run_wf("next", "--track", "Track 99 - Nowhere")
        axi = _decode_envelope(result, "next")
        self.assertEqual(
            axi.get("verb"), "next",
            f"axi.verb must equal 'next', got {axi.get('verb')!r}",
        )
        self.assertIn(
            "decision", axi,
            f"axi must contain a 'decision' field, got keys {list(axi.keys())}",
        )
        # POSITIVE -- an unknown track with no matching ChangeSet row must
        # decide DRAINED (would fail against a stub always returning e.g. NEXT).
        self.assertEqual(
            axi.get("decision"), "DRAINED",
            f"axi.decision must equal 'DRAINED' for an unknown track with no "
            f"rows, got {axi.get('decision')!r}",
        )

    def test_progress_stdout_decodes_to_progress_envelope(self):
        # Read-only call: unknown --cr, no --done/--total -> no DB mutation.
        result = _run_wf("progress", "--cr", "CR-NOWHERE-000")
        axi = _decode_envelope(result, "progress")
        self.assertEqual(
            axi.get("verb"), "progress",
            f"axi.verb must equal 'progress', got {axi.get('verb')!r}",
        )

    def test_all_three_verbs_have_list_type_warnings_field(self):
        cases = [
            ("status", _run_wf("status")),
            ("next", _run_wf("next", "--track", "Track 99 - Nowhere")),
            ("progress", _run_wf("progress", "--cr", "CR-NOWHERE-000")),
        ]
        not_list = []
        for label, result in cases:
            axi = _decode_envelope(result, label)
            warnings = axi.get("warnings")
            if not isinstance(warnings, list):
                not_list.append((label, warnings))
        # NEGATIVE/bound -- every verb's warnings field must be a list
        # (possibly empty), never absent or a non-list type.
        self.assertEqual(
            not_list, [],
            f"expected axi.warnings to be a list on all three verbs, "
            f"non-list/missing: {not_list}",
        )


class WorktreeFlowSkillConsumerNotesTest(unittest.TestCase):
    """SS4 -- consumer skills mentioning worktree-flow output carry a note."""

    def test_worktree_flow_mentioning_skills_have_stderr_or_toon_note_nearby(self):
        skill_files = sorted(str(p) for p in SKILLS_DIR.glob("*/SKILL.md"))
        grep = subprocess.run(
            ["grep", "-l", "worktree-flow", *skill_files],
            capture_output=True, text=True, timeout=15,
        )
        matched_files = [ln for ln in grep.stdout.splitlines() if ln.strip()]
        # Sanity -- today's live tree has matches; guards against this test
        # vacuously passing if the skills directory layout ever changes.
        self.assertGreater(
            len(matched_files), 0,
            "expected at least one ~/.claude/skills/*/SKILL.md to mention "
            "'worktree-flow' (bootstrap/status-report/code-health/shutdown "
            "do today) -- got none; check SKILLS_DIR contents",
        )

        missing_note = []
        for path_str in matched_files:
            path = Path(path_str)
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            mention_idxs = [i for i, ln in enumerate(lines) if "worktree-flow" in ln]
            has_note_nearby = any(
                ("stderr" in lines[j] or "TOON" in lines[j])
                for i in mention_idxs
                for j in range(max(0, i - 2), min(len(lines), i + 3))
            )
            if not has_note_nearby:
                missing_note.append(path_str)

        # NEGATIVE/bound -- every matched file must carry the added note
        # within 2 lines of a worktree-flow mention.
        self.assertEqual(
            missing_note, [],
            f"expected every worktree-flow-mentioning SKILL.md to contain "
            f"'stderr' or 'TOON' within 2 lines of a worktree-flow mention, "
            f"missing in: {missing_note}",
        )


if __name__ == "__main__":
    unittest.main()
