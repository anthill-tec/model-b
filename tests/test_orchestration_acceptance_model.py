"""The orchestrator's acceptance model and parallel agents in one tree — CR-MDB-044 §S1, §S2.

Contract: ``docs/changes/CR-MDB-044-agent-definitions-and-briefs.md`` (design reference PRD D5,
amended 2026-09-27). The file under test is ``skills-src/model-b/references/orchestration-common.md``.

What the file must carry (pinned here; GREEN writes to it):

- §S1 — a heading, any level, exactly ``Never author code — dispatch with an accurate brief``, and
  no heading ``Never author code — always dispatch + diff-verify``. Its body carries each rule of
  ``ACCEPTANCE_RULES`` (the brief's duty and no over-specifying; what the brief names; agents commit
  the code they write and are never reset and recommitted; acceptance from the report, the ingested
  run and the commit range with no re-runs; VERIFY, FIX and the pre-merge gate as the correctness
  gates; revert or a FIX agent for spec-breaking work) and each rule §S1 keeps (``STAYING_RULES``).
- §S1 — no line of the file says ``diff-verify EVERY cycle``, ``reset+recommit`` or ``Validate an
  agent's work at module level first`` (``REMOVED_PHRASES``, matched case-insensitively).
- §S2 — a section "Parallel agents in one tree" carrying each of the eight rules of
  ``PARALLEL_RULES``.
- § "Cycle discipline" refers to "Parallel agents in one tree" for splitting a phase, keeps "one
  active cycle at a time" and parallel CRs in Track orchestrators (``CYCLE_DISCIPLINE_RULES``), and
  states the Crucible #1407 rules: VERIFY closes before its FIX cycle, the switch happens between
  agents (a closed cycle refuses runs), a new contract VERIFY finds runs RED in the FIX cycle
  (``VERIFY_FIX_RULES``).
- §S1 — ``skills-src/model-b/references/orchestration-track.md`` agrees: no block of it carries a
  rule to diff-verify the worktree or the commit range, or assumes agents are told not to commit
  (``TRACK_CONTRADICTING_RULES``).

A rule is carried when ONE block of the section — a list item with its wrapped lines, or a paragraph
— matches every pattern of the rule (case-insensitive, after ``**`` and backticks are dropped and
whitespace collapsed), so a rule is stated in one place, not assembled from scattered words. The
patterns are the spec's own words; how GREEN phrases the rest of the sentence is free.

Class map:

- ``AcceptanceModelSectionTest`` — §S1 heading, body rules, the staying rules, the removed phrases.
- ``ParallelAgentsSectionTest`` — §S2's section and its eight rules.
- ``CycleDisciplineTest`` — § "Cycle discipline": the §S2 reference and the #1407 rules.
- ``TrackChecklistAgreesTest`` — ``orchestration-track.md`` carries none of
  ``TRACK_CONTRADICTING_RULES``.
- ``RuleCheckersOnSyntheticTextTest`` — the same pure functions on in-memory text: a well-formed
  fixture yields nothing, and each missing or contradicting rule is reported by name.

Every check is a pure function returning a list of problem strings (``[]`` = clean). Stdlib only.
"""

import re
import unittest

from tests._helpers import REPO_ROOT, read_text
from tests.test_orchestrator_rule_triage import markdown_headings, section_body

COMMON_REL = "skills-src/model-b/references/orchestration-common.md"
COMMON_FILE = REPO_ROOT / COMMON_REL
TRACK_REL = "skills-src/model-b/references/orchestration-track.md"
TRACK_FILE = REPO_ROOT / TRACK_REL

NEW_HEADING = "Never author code \u2014 dispatch with an accurate brief"
OLD_HEADING = "Never author code \u2014 always dispatch + diff-verify"
PARALLEL_HEADING = "Parallel agents in one tree"
CYCLE_HEADING = "Cycle discipline"

#: §S1 — the renamed section's new rules (AC 1).
ACCEPTANCE_RULES = {
    "brief duty, no over-specifying": (r"\bbrief\b", r"\bduty\b", r"over-specif"),
    "brief names spec, scope, rules, boundaries; agent definition carries the how": (
        r"\bbrief\b", r"\bspec\b", r"\bscope\b", r"\brules\b", r"\bboundar", r"agent definition"),
    "agents commit the code they write": (r"agents commit the code they write",),
    "never resets and recommits an agent's commits": (r"never reset\w* and recommit",),
    "accepted from report, ingested run and commit range, no re-runs": (
        r"\breport\b", r"ingested run", r"commit range", r"re-run"),
    "VERIFY, FIX and the pre-merge gate are the correctness gates": (
        r"correctness gates?", r"\bVERIFY\b", r"\bFIX\b", r"pre-merge gate"),
    "spec-breaking work reverted or sent to a FIX agent, never edited": (
        r"\brevert", r"FIX agent", r"\bspec\b", r"never edit"),
}

#: §S1 — the rules that stay in the renamed section.
STAYING_RULES = {
    "never author code": (r"never author",),
    "first action after approval is the RED dispatch": (r"first action", r"RED dispatch"),
    "Identity block and the register command": (r"Identity block", r"register command"),
    "post-RED rejection of nested builds": (r"\breject", r"nested builds"),
    "a fix round goes to a FIX agent": (r"fix round", r"FIX agent"),
    "salvage a crashed agent's complete diff": (r"crashed agent", r"salvag", r"complete"),
    "refactor, not revert, a wrong pattern": (r"refactor\w*,? not revert",),
    "beyond-mandate findings are unverified": (r"beyond its mandate", r"unverified"),
    "git status after an interrupted agent": (r"interrupted", r"git status"),
    "stop a stalled agent": (r"\bstop\b", r"stalled"),
}

#: §S1 — the rules the acceptance model replaces; no line of the file may say these.
REMOVED_PHRASES = (
    "diff-verify EVERY cycle",
    "reset+recommit",
    "Validate an agent's work at module level first",
)

#: §S2 — the eight rules of "Parallel agents in one tree".
PARALLEL_RULES = {
    "only with the user's explicit go, else one agent per phase": (
        r"explicit go", r"one agent per phase"),
    "split by file, never within a file; each brief lists the agent's files": (
        r"by file", r"never within a file", r"\bbrief\b", r"\bfiles\b"),
    "commit only own files; never stage everything, stash, reset or restore": (
        r"only its own files", r"stag\w* everything|git add -A", r"\bstash", r"\breset",
        r"\brestor"),
    "private reports directory via --reports, else one at a time": (
        r"private reports? dir", r"--reports", r"one at a time"),
    "ids suffixed -1 … -N": (r"suffix", r"(?<![\w-])-1\b", r"(?<![\w-])-N\b"),
    "sized to the harness's concurrency cap (maxConcurrent, default 4)": (
        r"concurrency cap", r"pi-subagents", r"maxConcurrent", r"default\w*\W{1,4}(?:to\W+)?4\b"),
    "no agent's output verified on its own; VERIFY covers the combined result": (
        r"on its own", r"VERIFY cycle", r"combined"),
    "follow-up to an expired session goes to a fresh agent under the same id": (
        r"expired", r"fresh agent", r"same id"),
}

#: §S2 — what § "Cycle discipline" keeps and how it refers to the new section.
CYCLE_DISCIPLINE_RULES = {
    "one active cycle at a time": (r"one active cycle at a time",),
    "a phase is split across agents only under Parallel agents in one tree": (
        r"\bphase\b", r"\bsplit", r"Parallel agents in one tree"),
    "parallel CRs belong to Track orchestrators": (r"parallel CRs?\b", r"track orchestrators?"),
}

#: §S1 (Crucible #1407) — the VERIFY → FIX switch in § "Cycle discipline".
VERIFY_FIX_RULES = {
    "an approved VERIFY finding is fixed in its own FIX cycle": (r"own FIX cycle",),
    "VERIFY closes with its findings before the FIX cycle is added and activated": (
        r"VERIFY(?: cycle)? closes", r"\bbefore\b", r"FIX cycle"),
    "the switch happens between agents; a closed cycle refuses runs": (
        r"between agents", r"closed cycle", r"refused"),
    "a new contract VERIFY finds runs RED in the FIX cycle, alongside the FIX agent": (
        r"new contract", r"\bRED\b", r"in the FIX cycle", r"alongside"),
}

#: §S1 — the rules the acceptance model replaced, as ``orchestration-track.md`` could restate them.
#: A block matching every pattern of one of these contradicts PRD D5 and ``orchestration-common.md``.
TRACK_CONTRADICTING_RULES = {
    "diff-verify the worktree": (r"diff-verif", r"\bwork(?:ing )?tree\b"),
    "verify the commit range": (r"\bverif", r"commit range"),
    "agents are told not to commit": (r"do not commit|don't commit|self-commit",),
}

_ITEM_START = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_HEADING_LINE = re.compile(r"^#{1,6}\s")


def rule_blocks(body: str) -> list[str]:
    """The body's blocks — each list item with its wrapped lines, or each paragraph — normalised:
    ``**`` and backticks dropped, whitespace collapsed. Headings are not rule text."""
    blocks, current = [], []

    def flush():
        if current:
            text = " ".join(current).replace("**", "").replace("`", "")
            blocks.append(re.sub(r"\s+", " ", text).strip())
            current.clear()

    for line in body.splitlines():
        if not line.strip() or _HEADING_LINE.match(line):
            flush()
            continue
        if _ITEM_START.match(line):
            flush()
        current.append(line.strip())
    flush()
    return blocks


def missing_rules(body: str | None, rules: dict[str, tuple[str, ...]]) -> list[str]:
    """The name of each rule no single block of ``body`` states (every rule when ``body`` is
    ``None``)."""
    blocks = rule_blocks(body) if body is not None else []
    return [name for name, patterns in rules.items()
            if not any(all(re.search(p, block, re.IGNORECASE) for p in patterns) for block in blocks)]


def heading_findings(text: str) -> list[str]:
    """The renamed heading is present exactly once and the old heading is gone."""
    headings = [h for _, _, h in markdown_headings(text)]
    problems = []
    if headings.count(NEW_HEADING) != 1:
        problems.append(f"heading '{NEW_HEADING}' appears {headings.count(NEW_HEADING)} times, not once")
    if OLD_HEADING in headings:
        problems.append(f"heading '{OLD_HEADING}' is still present")
    return problems


def section_rule_findings(text: str, heading: str, rules: dict[str, tuple[str, ...]]) -> list[str]:
    """``<heading>: no heading`` when the section is absent, else ``<heading>: <rule>`` for each
    rule it does not state."""
    body = section_body(text, heading)
    if body is None:
        return [f"{heading}: no heading"]
    return [f"{heading}: {name}" for name in missing_rules(body, rules)]


def removed_phrase_findings(text: str) -> list[str]:
    """``<line>: <phrase>`` for each line carrying a replaced rule (case-insensitive)."""
    return [f"{n}: {phrase}" for n, line in enumerate(text.splitlines(), 1)
            for phrase in REMOVED_PHRASES if phrase.lower() in line.lower()]


def contradicting_rules(text: str, rules: dict[str, tuple[str, ...]]) -> list[str]:
    """The name of each rule some single block of ``text`` states — the inverse of
    ``missing_rules``."""
    blocks = rule_blocks(text)
    return [name for name, patterns in rules.items()
            if any(all(re.search(p, block, re.IGNORECASE) for p in patterns) for block in blocks)]


class _CommonFileMixin(unittest.TestCase):
    def common(self) -> str:
        self.assertTrue(COMMON_FILE.is_file(), f"{COMMON_REL} does not exist")
        return read_text(COMMON_FILE)


class AcceptanceModelSectionTest(_CommonFileMixin):
    """§S1 — "Never author code — dispatch with an accurate brief"."""

    def test_section_is_retitled_dispatch_with_an_accurate_brief(self):
        self.assertEqual(heading_findings(self.common()), [])

    def test_section_states_the_brief_commit_and_acceptance_rules(self):
        self.assertEqual(section_rule_findings(self.common(), NEW_HEADING, ACCEPTANCE_RULES), [])

    def test_section_keeps_every_rule_s1_lists_as_staying(self):
        self.assertEqual(section_rule_findings(self.common(), NEW_HEADING, STAYING_RULES), [])

    def test_no_line_carries_a_rule_the_acceptance_model_replaces(self):
        self.assertEqual(removed_phrase_findings(self.common()), [])


class ParallelAgentsSectionTest(_CommonFileMixin):
    """§S2 — "Parallel agents in one tree"."""

    def test_section_exists_exactly_once(self):
        headings = [h for _, _, h in markdown_headings(self.common())]
        self.assertEqual(headings.count(PARALLEL_HEADING), 1)

    def test_section_carries_each_of_the_eight_rules(self):
        self.assertEqual(len(PARALLEL_RULES), 8)
        self.assertEqual(section_rule_findings(self.common(), PARALLEL_HEADING, PARALLEL_RULES), [])


class CycleDisciplineTest(_CommonFileMixin):
    """§S2 and §S1 (#1407) — § "Cycle discipline"."""

    def test_cycle_discipline_refers_to_parallel_agents_and_keeps_one_active_cycle(self):
        self.assertEqual(
            section_rule_findings(self.common(), CYCLE_HEADING, CYCLE_DISCIPLINE_RULES), [])

    def test_cycle_discipline_closes_verify_before_fix_and_runs_red_in_the_fix_cycle(self):
        self.assertEqual(section_rule_findings(self.common(), CYCLE_HEADING, VERIFY_FIX_RULES), [])


class TrackChecklistAgreesTest(unittest.TestCase):
    """§S1 — ``orchestration-track.md`` agrees with the acceptance model."""

    def test_track_carries_no_rule_to_diff_verify_the_worktree_or_the_commit_range(self):
        self.assertTrue(TRACK_FILE.is_file(), f"{TRACK_REL} does not exist")
        self.assertEqual(contradicting_rules(read_text(TRACK_FILE), TRACK_CONTRADICTING_RULES), [])


# ------------------------------------------------------------------ synthetic ----

_GOOD_ACCEPTANCE = f"""## {NEW_HEADING}
- The orchestrator never authors RED/GREEN/FIX edits.
- **The brief is the orchestrator's paramount duty.** It never compromises the workflow rules or the
  CR spec, and it does not over-specify.
- The brief names the spec and the cycle's scope, points to the rules that bind the phase and
  states its boundaries; the agent definition carries the how.
- **Agents commit the code they write.** The orchestrator never resets and recommits an agent's
  commits.
- A phase is accepted from the agent's report, its ingested run on the board and the phase's
  `commit range`; no suite is re-run between phases.
- The correctness gates are the CR's VERIFY cycle, the FIX cycles it opens and the pre-merge gate.
- Work that breaks the spec is reverted or sent to a FIX agent, never edited by the orchestrator.
- After approval the first action is the RED dispatch.
- Every brief opens with an Identity block; its step 1 is the exact register command.
- At post-RED review, reject tests that spawn nested builds.
- A fix round's production diff goes to a FIX agent.
- A crashed agent that left a complete diff is salvaged.
- A chunk with the wrong pattern is refactored, not reverted.
- Treat any finding beyond its mandate as unverified.
- After an interrupted agent, inspect `git status`.
- Stop a stalled sub-agent before taking over.
"""

_GOOD_PARALLEL = f"""## {PARALLEL_HEADING}
- Only with the user's explicit go; otherwise one agent per phase.
- The work is split by file, never within a file, and each brief lists that agent's files.
- Each agent commits only its own files, and never stages everything, stashes, resets or restores.
- Each agent's test runs use a private reports directory where its client takes one (`--reports`);
  otherwise its agents' tests run one at a time.
- Ids are suffixed `-1` … `-N`.
- The split is sized to the harness's concurrency cap (pi-subagents `maxConcurrent`, default 4).
- No agent's output is verified on its own; the CR's VERIFY cycle covers the combined result.
- A follow-up to an agent whose session expired goes to a fresh agent under the same id.
"""

_GOOD_CYCLE = f"""## {CYCLE_HEADING}
- **One active cycle at a time per orchestrator.** A phase may be split across agents only under
  "{PARALLEL_HEADING}". Parallel CRs still belong to Track orchestrators.
- **A VERIFY finding the user approves for fixing is fixed in its own FIX cycle.**
  - The VERIFY cycle closes with its findings before the FIX cycle is added and activated.
  - The switch happens between agents, never under one: an agent bound to a closed cycle has its
    runs refused.
  - A new contract VERIFY finds still goes AC → RED → FIX; the RED agent runs in the FIX cycle,
    alongside the FIX agent.
"""


def _good_text() -> str:
    return "# Orchestration\n\n" + _GOOD_CYCLE + "\n" + _GOOD_ACCEPTANCE + "\n" + _GOOD_PARALLEL


def _drop(text: str, fragment: str) -> str:
    assert text.count(fragment) == 1, fragment
    return text.replace(fragment, "")


class RuleCheckersOnSyntheticTextTest(unittest.TestCase):
    def test_well_formed_fixture_yields_no_finding(self):
        text = _good_text()
        self.assertEqual(heading_findings(text), [])
        self.assertEqual(removed_phrase_findings(text), [])
        for heading, rules in ((NEW_HEADING, ACCEPTANCE_RULES), (NEW_HEADING, STAYING_RULES),
                               (PARALLEL_HEADING, PARALLEL_RULES),
                               (CYCLE_HEADING, CYCLE_DISCIPLINE_RULES),
                               (CYCLE_HEADING, VERIFY_FIX_RULES)):
            self.assertEqual(section_rule_findings(text, heading, rules), [], heading)

    def test_old_heading_or_missing_new_heading_is_reported(self):
        old = _good_text().replace(NEW_HEADING, OLD_HEADING)
        self.assertEqual(heading_findings(old), [
            f"heading '{NEW_HEADING}' appears 0 times, not once",
            f"heading '{OLD_HEADING}' is still present",
        ])
        both = _good_text() + f"\n## {OLD_HEADING}\n- x\n"
        self.assertEqual(heading_findings(both), [f"heading '{OLD_HEADING}' is still present"])
        twice = _good_text() + f"\n## {NEW_HEADING}\n- x\n"
        self.assertEqual(heading_findings(twice), [f"heading '{NEW_HEADING}' appears 2 times, not once"])

    def test_a_heading_inside_a_fence_or_as_a_prefix_does_not_count(self):
        text = _good_text().replace(f"## {NEW_HEADING}", "## Never author code")
        text += f"\n```\n# {NEW_HEADING}\n```\n"
        self.assertIn(f"heading '{NEW_HEADING}' appears 0 times, not once", heading_findings(text))

    def test_absent_section_is_reported_once_not_per_rule(self):
        self.assertEqual(section_rule_findings("# x\n", PARALLEL_HEADING, PARALLEL_RULES),
                         [f"{PARALLEL_HEADING}: no heading"])

    def test_each_missing_acceptance_rule_is_named(self):
        text = _drop(_good_text(), "- The correctness gates are the CR's VERIFY cycle, the FIX cycles it "
                                   "opens and the pre-merge gate.\n")
        text = _drop(text, "  commits.\n").replace("never resets and recommits an agent's", "resets")
        self.assertEqual(section_rule_findings(text, NEW_HEADING, ACCEPTANCE_RULES), [
            f"{NEW_HEADING}: never resets and recommits an agent's commits",
            f"{NEW_HEADING}: VERIFY, FIX and the pre-merge gate are the correctness gates",
        ])

    def test_a_rule_scattered_across_blocks_is_not_carried(self):
        body = ("- The report matters.\n- So does the ingested run.\n- And the commit range.\n"
                "- Nothing is re-run.\n")
        self.assertEqual(missing_rules(body, {"acceptance": ACCEPTANCE_RULES[
            "accepted from report, ingested run and commit range, no re-runs"]}), ["acceptance"])
        wrapped = "- The report, the ingested run and\n  the `commit range`; nothing is re-run.\n"
        self.assertEqual(missing_rules(wrapped, {"acceptance": ACCEPTANCE_RULES[
            "accepted from report, ingested run and commit range, no re-runs"]}), [])

    def test_a_rule_in_another_section_does_not_count_for_this_one(self):
        text = _drop(_good_text(), "- Stop a stalled sub-agent before taking over.\n")
        text += "\n## Elsewhere\n- Stop a stalled sub-agent before taking over.\n"
        self.assertEqual(section_rule_findings(text, NEW_HEADING, STAYING_RULES),
                         [f"{NEW_HEADING}: stop a stalled agent"])

    def test_each_missing_staying_rule_is_named(self):
        text = _drop(_good_text(), "- A crashed agent that left a complete diff is salvaged.\n")
        text = _drop(text, "- A chunk with the wrong pattern is refactored, not reverted.\n")
        self.assertEqual(section_rule_findings(text, NEW_HEADING, STAYING_RULES), [
            f"{NEW_HEADING}: salvage a crashed agent's complete diff",
            f"{NEW_HEADING}: refactor, not revert, a wrong pattern",
        ])

    def test_removed_phrases_are_reported_per_line_case_insensitively(self):
        text = ("- Agents confabulate — diff-verify every cycle against ground truth.\n"
                "- Verify the COMMIT RANGE, reset+recommit cleanly.\n"
                "- Validate an agent's work at module level first.\n"
                "- When diff-verify finds a defect, dispatch a FIX agent.\n"
                "- The orchestrator never resets and recommits an agent's commits.\n")
        self.assertEqual(removed_phrase_findings(text), [
            "1: diff-verify EVERY cycle",
            "2: reset+recommit",
            "3: Validate an agent's work at module level first",
        ])

    def test_track_checklist_rules_the_acceptance_model_replaced_are_reported_by_name(self):
        text = ("## Cull / re-layer execution checklist\n"
                "- Diff-verify the WORKTREE, not the agent's narrative.\n"
                "- A defect \u2192 dispatch a fix-agent, never self-edit.\n"
                "- Verify the COMMIT RANGE, not just the working tree (agents self-commit despite\n"
                "  \"do not commit\").\n")
        self.assertEqual(contradicting_rules(text, TRACK_CONTRADICTING_RULES), [
            "diff-verify the worktree", "verify the commit range", "agents are told not to commit"])
        clean = ("## Cull / re-layer execution checklist\n"
                 "- A phase is accepted from the agent's report, its ingested run and its commit range\n"
                 "  (`<base>..<head>`); agents commit the code they write.\n"
                 "- A defect \u2192 dispatch a FIX agent, never self-edit; VERIFY covers the result.\n")
        self.assertEqual(contradicting_rules(clean, TRACK_CONTRADICTING_RULES), [])

    def test_each_missing_parallel_rule_is_named(self):
        text = _good_text().replace("default 4", "a small number").replace(
            "fresh agent under the same id", "new agent")
        text = _drop(text, "- Ids are suffixed `-1` … `-N`.\n")
        self.assertEqual(section_rule_findings(text, PARALLEL_HEADING, PARALLEL_RULES), [
            f"{PARALLEL_HEADING}: ids suffixed -1 … -N",
            f"{PARALLEL_HEADING}: sized to the harness's concurrency cap (maxConcurrent, default 4)",
            f"{PARALLEL_HEADING}: follow-up to an expired session goes to a fresh agent under the same id",
        ])

    def test_parallel_commit_rule_accepts_the_git_add_spelling_and_needs_every_forbidden_verb(self):
        rule = {"commit": PARALLEL_RULES[
            "commit only own files; never stage everything, stash, reset or restore"]}
        ok = "- Each agent commits only its own files; never `git add -A`, stash, reset or restore.\n"
        self.assertEqual(missing_rules(ok, rule), [])
        no_restore = "- Each agent commits only its own files; never stages everything, stashes or resets.\n"
        self.assertEqual(missing_rules(no_restore, rule), ["commit"])

    def test_id_suffix_rule_needs_both_ends_of_the_range(self):
        rule = {"ids": PARALLEL_RULES["ids suffixed -1 … -N"]}
        self.assertEqual(missing_rules("- Ids are suffixed `-1` … `-N`.\n", rule), [])
        self.assertEqual(missing_rules("- Ids are suffixed `-1`.\n", rule), ["ids"])
        self.assertEqual(missing_rules("- Ids are suffixed `CR-1-N`.\n", rule), ["ids"])

    def test_cycle_discipline_without_the_parallel_reference_or_1407_rules_is_reported(self):
        text = _good_text().replace(f'A phase may be split across agents only under\n  "{PARALLEL_HEADING}". ',
                                    "")
        text = text.replace("between agents, never under one", "under the same agent")
        text = text.replace("the RED agent runs in the FIX cycle,\n    alongside the FIX agent",
                            "RED runs in the VERIFY cycle")
        self.assertEqual(section_rule_findings(text, CYCLE_HEADING, CYCLE_DISCIPLINE_RULES), [
            f"{CYCLE_HEADING}: a phase is split across agents only under Parallel agents in one tree",
        ])
        self.assertEqual(section_rule_findings(text, CYCLE_HEADING, VERIFY_FIX_RULES), [
            f"{CYCLE_HEADING}: the switch happens between agents; a closed cycle refuses runs",
            f"{CYCLE_HEADING}: a new contract VERIFY finds runs RED in the FIX cycle, alongside the FIX agent",
        ])

    def test_the_current_cycle_discipline_parallelism_rule_is_not_enough(self):
        body = ("- **One active cycle at a time per orchestrator**, even for disjoint code — "
                "parallelism belongs to separate track orchestrators.\n")
        self.assertEqual(missing_rules(body, CYCLE_DISCIPLINE_RULES), [
            "a phase is split across agents only under Parallel agents in one tree",
            "parallel CRs belong to Track orchestrators",
        ])


if __name__ == "__main__":
    unittest.main()
