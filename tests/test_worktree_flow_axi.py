"""Tests for CR-MDB-010 (worktree-flow.py AXI output) -- SS4 (consumer-note
grep gate) over the repo's skill sources.

CR-MDB-032 SS2 deleted the two classes that drove the DEPLOYED
`~/.claude/scripts/` copies (WorktreeFlowCodecDeploymentTest -- SS2 codec
deployment; WorktreeFlowEnvelopeTest -- SS3 envelope emission): the generated
`scripts/toon.py` and the in-repo `worktree-flow.py` envelope are proved by
tests/test_toon_codec.py. WorktreeFlowSkillConsumerNotesTest now reads
skills-src/, never a deployed copy under the home directory.

Stdlib + subprocess only.
"""

import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SKILLS_DIR = REPO_ROOT / "skills-src"


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
            "expected at least one skills-src/*/SKILL.md to mention "
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
