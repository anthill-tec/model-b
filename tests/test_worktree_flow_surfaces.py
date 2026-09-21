"""RED-phase tests for CR-MDB-028 cycle C2 (§S3 §S7 + the two cross-CR ACs).

C1 made `scripts/worktree-flow.py` DB-less: its roster is exactly
`start status sync finish abort` and `cs`/`show`/`reconcile`/`next`/`progress`
are gone. C2 repoints the PUBLISHED SURFACES so no orchestrator is taught to
ask a retired verb a scheduling question, and states the architectural line
the CR draws once, plainly (§S3):

    `worktree-flow` owns what it can derive from git (worktrees, ahead/behind,
    phase, merge). Crucible owns what used to live in the DB (queue
    membership, release, wave, seq, dependencies, readiness).

Gates here:

* §S7's grep gate — zero `worktree-flow <retired verb>` invocations under
  `skills-src/`, `scripts/`, `hooks-src/` and in `AGENTS.md` (`archive/`,
  `audits/`, `docs/` and the test tree excluded). Its failure message is the
  GREEN work list, `file:line` per hit.
* Per-surface content gates, one or more method per repointed file, asserting
  the surface teaches the new split rather than merely dropping the old verb.
* The split statement itself, in an orchestration reference, matched by two
  tolerant regexes rather than an exact string.
* CR-MDB-010 lineage (amendment 5): its `next`/`progress` envelope ACs struck
  with a dated note naming this CR.
* CR-MDB-023 cross-CR coordination: `worktree-flow.py cs` survives there only
  as history, never as an instruction.

Everything reads repo files; stdlib only, no subprocess, no deployed copies.

Expected against the pre-GREEN tree: every gate above FAILS except
`test_s3_agents_md_does_not_name_worktree_flow_for_scheduling`, which is a
positive-absence guard — `AGENTS.md` names `worktree-flow` only as a member of
the tool-script asset class and must never acquire a scheduling route.
"""

import os
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# --- §S7 grep gate -----------------------------------------------------------

#: The retired verbs. C1 removed them from the tool; C2 removes every call.
RETIRED_VERBS = ("cs", "show", "reconcile", "next", "progress")

#: The AC's regex, verbatim (CR-MDB-028 §S7 / amendment 2).
RETIRED_VERB_CALL = re.compile(
    r"worktree-flow(\.py)?\s+(cs|show|reconcile|next|progress)\b"
)

#: Trees the AC pins. `AGENTS.md` is a file, the rest are directories.
GREP_ROOTS = ("skills-src", "scripts", "hooks-src", "AGENTS.md")

#: `archive/` is immutable history (§S7 table); `audits/` is dated evidence;
#: `docs/` holds the CR specs that must be able to NAME the retired verbs to
#: discuss them; the test tree must be able to spell its own gate.
EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    "archive",
    "audits",
    "docs",
    "tests",
    "test-reports",
}

# --- surface vocabulary ------------------------------------------------------

#: Every verb name worktree-flow has ever carried, surviving or retired.
ALL_WF_VERBS = (
    "start",
    "status",
    "sync",
    "finish",
    "abort",
    "cs",
    "show",
    "reconcile",
    "next",
    "progress",
)

#: A line routes a SCHEDULING question when it names one of these NEAR
#: `worktree-flow`. `schedule_db` is stripped before matching: that module
#: stays shipped (§S5) and naming it is not a scheduling route. Proximity
#: matters — unrelated prose ("reverted on the next apply") is not a route.
SCHEDULING_TOKENS = re.compile(
    r"\b(next|readiness|schedul\w*|depends_on|ChangeSet|progress|reconcile|cs)\b",
    re.IGNORECASE,
)

#: Characters either side of a `worktree-flow` mention that count as "near".
ROUTE_WINDOW = 90

#: `python-crucible.py next` — or the client and the verb on one line. Written
#: so `nextest` (a cargo runner, all over the Rust template) cannot match.
CRUCIBLE_NEXT_LINE = re.compile(
    r"(?:(?:python-)?crucible(?:\.py)?\b[^\n]{0,140}?\bnext\b)"
    r"|(?:\bnext\b[^\n]{0,140}?(?:python-)?crucible(?:\.py)?\b)",
    re.IGNORECASE,
)

# --- §S3 split statement (two tolerant regexes, not an exact string) ---------

GIT_HALF = re.compile(r"worktree-flow[^\n]{0,80}?\b(?:owns|derives?|derive)\b", re.I)
CRUCIBLE_HALF = re.compile(r"crucible[^\n]{0,80}?\bowns\b", re.I)
GIT_SIDE_NOUNS = ("worktree", "ahead", "behind", "phase", "merge")
CRUCIBLE_SIDE_NOUNS = ("queue", "release", "wave", "seq", "depend", "readiness")

# --- cross-CR lineage --------------------------------------------------------

CR010 = REPO_ROOT / "docs" / "changes" / "CR-MDB-010-worktree-flow-axi.md"
CR023 = REPO_ROOT / "docs" / "changes" / "CR-MDB-023-code-health-skill-adoption.md"

STRUCK_MARK = re.compile(r"~~|SUPERSEDED|STRUCK|RETIRED|WITHDRAWN")

WF_CS = re.compile(r"worktree-flow(\.py)?\s+cs\b")

#: Vocabulary that marks a `worktree-flow.py cs` mention as HISTORY rather than
#: an instruction. Deliberately narrow: "supersedes" is excluded because the
#: original CR-023 text used it while still describing the call in the present
#: tense ("the ChangeSet-filing step ... runs through `worktree-flow.py cs`").
HISTORY_MARK = re.compile(
    r"(removed?|removes|retired?|two-step|CR-MDB-028|void|gone|no longer)",
    re.IGNORECASE,
)

BOOTSTRAP_SKILL = REPO_ROOT / "skills-src" / "bootstrap" / "SKILL.md"
TRACK_REF = (
    REPO_ROOT / "skills-src" / "model-b" / "references" / "orchestration-track.md"
)
COMMON_REF = (
    REPO_ROOT / "skills-src" / "model-b" / "references" / "orchestration-common.md"
)
RUST_TEMPLATE = REPO_ROOT / "skills-src" / "memory-templates" / "rust-orchestration.md"
JAVA_TEMPLATE = REPO_ROOT / "skills-src" / "memory-templates" / "java-orchestration.md"
AGENTS_MD = REPO_ROOT / "AGENTS.md"
SKILLS_SRC = REPO_ROOT / "skills-src"

#: DB-era verb names that only ever belonged to `worktree-flow`'s removed half.
#: Spelled as inline-code tokens they are unambiguous: the Crucible client has
#: no `cs`/`reconcile`/`show`/`progress` verb, so a backticked one on a
#: worktree-flow surface can only be teaching a verb C1 deleted. `next` is
#: excluded deliberately — it is the CLIENT's verb now and must be spellable.
DB_ERA_VERB_TOKEN = re.compile(r"`(cs|reconcile|show|progress)`")

#: Frontmatter routing tokens. Superset of SCHEDULING_TOKENS: a `description:`
#: summarises a whole skill, so it routes the reader with nouns (`queue`,
#: `board`) where a body line uses verbs. CR-MDB-028 F1 VERIFY finding 2: the
#: body-line list had no `queue` token, so a frontmatter clause advertising a
#: "worktree-flow queue board" passed every existing gate.
FRONTMATTER_ROUTING_TOKENS = re.compile(
    r"\b(queue|board|next|readiness|schedul\w*|depends_on|ChangeSet|progress|reconcile|cs)\b",
    re.IGNORECASE,
)


def _read(path):
    """Read a repo text file, failing loudly if a pinned surface moved."""
    if not path.exists():
        raise AssertionError(f"pinned surface is missing: {path.relative_to(REPO_ROOT)}")
    return path.read_text(encoding="utf-8")


def _numbered(path):
    """[(lineno, line)] for a surface, 1-based like every `file:line` we print."""
    return list(enumerate(_read(path).splitlines(), start=1))


def _iter_surface_files():
    """Yield every text file the §S7 grep gate covers, excluded trees pruned."""
    for root_name in GREP_ROOTS:
        root = REPO_ROOT / root_name
        if root.is_file():
            yield root
            continue
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(
                d for d in dirnames if d not in EXCLUDED_DIR_NAMES and not d.startswith(".")
            )
            for name in sorted(filenames):
                yield Path(dirpath) / name


def _verb_tokens(line):
    """Which worktree-flow verb names this line spells, as whole words."""
    return {
        verb
        for verb in ALL_WF_VERBS
        if re.search(rf"\b{re.escape(verb)}\b", line)
    }


def _verb_enumeration_lines(path):
    """Lines that ENUMERATE worktree-flow's roster: name the tool + 2+ verbs.

    A roster line is the surface that teaches which verbs exist, so it is the
    one that must not advertise a verb C1 deleted.
    """
    out = []
    for lineno, line in _numbered(path):
        if "worktree-flow" not in line:
            continue
        verbs = _verb_tokens(line)
        if len(verbs) >= 2:
            out.append((lineno, line, verbs))
    return out


def _scheduling_route_lines(path):
    """Lines routing a scheduling question at worktree-flow, `file:line` tagged.

    Only tokens within ``ROUTE_WINDOW`` characters of the `worktree-flow`
    mention count, so incidental prose elsewhere on a long line (an asset-class
    table row saying "reverted on the next apply") is not mistaken for a route.
    """
    name = path.relative_to(REPO_ROOT)
    offenders = []
    for lineno, line in _numbered(path):
        for match in re.finditer(r"worktree-flow", line):
            start = max(0, match.start() - ROUTE_WINDOW)
            window = line[start : match.end() + ROUTE_WINDOW].replace(
                "schedule_db", ""
            )
            if SCHEDULING_TOKENS.search(window):
                offenders.append(f"{name}:{lineno}: {line.strip()}")
                break
    return offenders


def _blocks(text):
    """Blank-line-separated blocks, with the first line number of each."""
    out = []
    lineno = 1
    for chunk in re.split(r"\n\s*\n", text):
        out.append((lineno, chunk))
        lineno += chunk.count("\n") + 2
    return out


def _states_the_split(text):
    """True when ONE block carries both halves of the §S3 split statement."""
    for _lineno, block in _blocks(text):
        low = block.lower()
        git_side = (
            GIT_HALF.search(block)
            and "git" in low
            and sum(noun in low for noun in GIT_SIDE_NOUNS) >= 3
        )
        crucible_side = (
            CRUCIBLE_HALF.search(block)
            and sum(noun in low for noun in CRUCIBLE_SIDE_NOUNS) >= 4
        )
        if git_side and crucible_side:
            return True
    return False


def _sections(path):
    """[(heading, [(lineno, line)])] split on markdown `## ` headings."""
    sections = []
    current = ("<preamble>", [])
    for lineno, line in _numbered(path):
        if line.startswith("## "):
            sections.append(current)
            current = (line.strip(), [])
        current[1].append((lineno, line))
    sections.append(current)
    return sections


def _frontmatter_description(path):
    """The YAML frontmatter `description:` value of a SKILL.md, or "".

    Folded continuation lines (an indented next line) are joined, so a wrapped
    description is matched as the single sentence a harness actually reads.
    """
    lines = _read(path).splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    parts = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if parts:
            if line[:1].isspace() and line.strip():
                parts.append(line.strip())
                continue
            break
        if line.startswith("description:"):
            parts.append(line[len("description:") :].strip())
    return " ".join(parts)


class WorktreeFlowSurfacesS7Test(unittest.TestCase):
    """§S7's grep gate plus the two cross-CR lineage ACs."""

    def test_s7_no_retired_verb_invocation_in_published_surfaces(self):
        """Zero `worktree-flow <cs|show|reconcile|next|progress>` calls remain.

        Covers `skills-src/`, `scripts/`, `hooks-src/` and `AGENTS.md`;
        `archive/`, `audits/`, `docs/` and `tests/` are excluded. The failure
        message IS the GREEN work list.
        """
        hits = []
        for path in _iter_surface_files():
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if RETIRED_VERB_CALL.search(line):
                    rel = path.relative_to(REPO_ROOT)
                    hits.append(f"{rel}:{lineno}: {line.strip()}")
        self.assertEqual(
            [],
            hits,
            "published surfaces still invoke verbs CR-MDB-028 C1 removed "
            f"({len(hits)} site(s)); repoint each at the Crucible client:\n  "
            + "\n  ".join(hits),
        )

    def test_s7_cr010_carries_dated_note_naming_cr_mdb_028(self):
        """CR-MDB-010's lineage is recorded, not silently invalidated (amendment 5)."""
        dated = [
            f"{lineno}: {line.strip()}"
            for lineno, line in _numbered(CR010)
            if "2026-09-21" in line and "CR-MDB-028" in line
        ]
        self.assertTrue(
            dated,
            "docs/changes/CR-MDB-010-worktree-flow-axi.md has no dated "
            "2026-09-21 note naming CR-MDB-028: 010 converted `next` and "
            "`progress` to AXI and this CR retires both, so the amendment "
            "must be recorded on 010 itself (its envelope contract stands "
            "for `status` and `finish` only).",
        )

    def test_s7_cr010_next_and_progress_envelope_acs_are_struck(self):
        """010's `next` and `progress` AC lines are marked struck, not left live."""
        unmarked = []
        for lineno, line in _numbered(CR010):
            is_next_ac = "next --track" in line
            is_progress_ac = "`progress` stdout envelope" in line
            if not (is_next_ac or is_progress_ac):
                continue
            if not STRUCK_MARK.search(line):
                unmarked.append(f"CR-MDB-010:{lineno}: {line.strip()}")
        self.assertEqual(
            [],
            unmarked,
            "CR-MDB-010 AC line(s) for retired verbs are still asserted as "
            "live; strike each (`~~…~~` or a SUPERSEDED prefix):\n  "
            + "\n  ".join(unmarked),
        )

    def test_s7_cr023_names_worktree_flow_cs_only_as_history(self):
        """CR-MDB-023 must not instruct a verb CR-MDB-028 removed (cross-CR AC).

        Every `worktree-flow.py cs` mention must sit in a removal-aware
        context — the line itself or an immediate neighbour saying
        removed/retired/two-step/void/gone/CR-MDB-028.
        """
        lines = _numbered(CR023)
        by_no = dict(lines)
        instructed = []
        for lineno, line in lines:
            if not WF_CS.search(line):
                continue
            window = " ".join(
                by_no.get(n, "") for n in (lineno - 1, lineno, lineno + 1)
            )
            if not HISTORY_MARK.search(window):
                instructed.append(f"CR-MDB-023:{lineno}: {line.strip()}")
        self.assertEqual(
            [],
            instructed,
            "CR-MDB-023 still presents `worktree-flow.py cs` as a live step; "
            "each site must read as history (the two-step `cr-plan` + "
            "`ledger assign` replaces it):\n  " + "\n  ".join(instructed),
        )


class WorktreeFlowSurfacesS3Test(unittest.TestCase):
    """§S3 — every published instruction teaches the git-vs-Crucible split."""

    def test_s3_bootstrap_skill_routes_readiness_at_the_crucible_client(self):
        """bootstrap/SKILL.md Step 3A asks Crucible the readiness question."""
        matches = [
            f"{lineno}: {line.strip()}"
            for lineno, line in _numbered(BOOTSTRAP_SKILL)
            if CRUCIBLE_NEXT_LINE.search(line)
        ]
        self.assertTrue(
            matches,
            "skills-src/bootstrap/SKILL.md never names the Crucible client's "
            "`next` verb: Step 3A must ask `python-crucible.py next` the "
            "readiness/scheduling question (worktree-flow cannot answer it).",
        )

    def test_s3_bootstrap_skill_does_not_route_scheduling_at_worktree_flow(self):
        """No bootstrap line pairs `worktree-flow` with a scheduling question."""
        offenders = _scheduling_route_lines(BOOTSTRAP_SKILL)
        self.assertEqual(
            [],
            offenders,
            "bootstrap/SKILL.md still routes scheduling at worktree-flow "
            "(git-derived worktree state, yes; scheduling truth, no):\n  "
            + "\n  ".join(offenders),
        )

    def test_s3_orchestration_track_has_no_worktree_flow_next(self):
        """orchestration-track.md never names `worktree-flow next` (§S2 removal)."""
        offenders = [
            f"orchestration-track.md:{lineno}: {line.strip()}"
            for lineno, line in _numbered(TRACK_REF)
            if re.search(r"worktree-flow(\.py)?\s+next\b", line)
        ]
        self.assertEqual(
            [],
            offenders,
            "orchestration-track.md still names `worktree-flow next`, which "
            "C1 deleted:\n  " + "\n  ".join(offenders),
        )

    def test_s3_orchestration_track_routes_the_next_instruction_at_crucible(self):
        """After `finish`, the track's next instruction comes from Crucible.

        Amendment 1: `finish` no longer prints a next line, so the section
        that teaches the `finish --cr` loop must name the Crucible client as
        the source of the next instruction.
        """
        loop_sections = [
            (heading, body)
            for heading, body in _sections(TRACK_REF)
            if any("finish --cr" in line for _lineno, line in body)
        ]
        self.assertTrue(
            loop_sections,
            "orchestration-track.md no longer has a section teaching "
            "`finish --cr`; the loop section is where the next instruction "
            "must be repointed.",
        )
        for heading, body in loop_sections:
            found = [
                f"orchestration-track.md:{lineno}: {line.strip()}"
                for lineno, line in body
                if CRUCIBLE_NEXT_LINE.search(line)
            ]
            self.assertTrue(
                found,
                f"orchestration-track.md section {heading!r} teaches "
                "`finish --cr` but never names the Crucible client's `next` "
                "— `finish` no longer prints a next line (amendment 1), so "
                "the track would be left with no instruction source.",
            )

    def test_s3_orchestration_track_verb_rosters_list_only_surviving_verbs(self):
        """Track-side worktree-flow verb enumerations advertise no retired verb."""
        offenders = [
            f"orchestration-track.md:{lineno}: {line.strip()}"
            f"  [retired: {','.join(sorted(verbs & set(RETIRED_VERBS)))}]"
            for lineno, line, verbs in _verb_enumeration_lines(TRACK_REF)
            if verbs & set(RETIRED_VERBS)
        ]
        self.assertEqual(
            [],
            offenders,
            "orchestration-track.md enumerates worktree-flow verbs that no "
            "longer exist; the roster is exactly start/status/sync/finish/"
            "abort:\n  " + "\n  ".join(offenders),
        )

    def test_s3_orchestration_common_verb_roster_lists_only_surviving_verbs(self):
        """orchestration-common.md's worktree-flow roster names surviving verbs only."""
        offenders = [
            f"orchestration-common.md:{lineno}: {line.strip()}"
            f"  [retired: {','.join(sorted(verbs & set(RETIRED_VERBS)))}]"
            for lineno, line, verbs in _verb_enumeration_lines(COMMON_REF)
            if verbs & set(RETIRED_VERBS)
        ]
        self.assertEqual(
            [],
            offenders,
            "orchestration-common.md enumerates retired worktree-flow verbs "
            "(currently `status/next/progress`); the roster is exactly "
            "start/status/sync/finish/abort:\n  " + "\n  ".join(offenders),
        )

    def test_s3_rust_orchestration_template_drops_next_reconcile_and_cs_lines(self):
        """The Rust memory template's `next`/`reconcile`/`cs` command lines are gone."""
        offenders = [
            f"rust-orchestration.md:{lineno}: {line.strip()}"
            for lineno, line in _numbered(RUST_TEMPLATE)
            if re.search(r"worktree-flow(\.py)?\s+(next|reconcile|cs)\b", line)
        ]
        self.assertEqual(
            [],
            offenders,
            "skills-src/memory-templates/rust-orchestration.md still ships "
            "command lines for verbs C1 removed; delete the `reconcile` and "
            "`cs` lines and repoint `next` (§S3):\n  " + "\n  ".join(offenders),
        )

    def test_s3_rust_orchestration_template_names_the_crucible_client_for_next(self):
        """A Crucible-client line replaces the template's `next` command line."""
        matches = [
            f"{lineno}: {line.strip()}"
            for lineno, line in _numbered(RUST_TEMPLATE)
            if CRUCIBLE_NEXT_LINE.search(line)
        ]
        self.assertTrue(
            matches,
            "rust-orchestration.md deletes the `worktree-flow.py next` line "
            "without replacing it: the WHERE-AM-I/WHAT'S-NEXT question must "
            "be routed at the Crucible client's `next` verb, or the template "
            "teaches a loop with no scheduler.",
        )

    def test_s3_agents_md_does_not_name_worktree_flow_for_scheduling(self):
        """AGENTS.md names worktree-flow as an asset only — never as a scheduler.

        Measured pre-GREEN: the single mention is the `scripts/` asset-class
        row, which carries no scheduling route. Asserted positively so a
        repoint elsewhere cannot quietly reintroduce one here.
        """
        offenders = _scheduling_route_lines(AGENTS_MD)
        self.assertEqual(
            [],
            offenders,
            "AGENTS.md routes a scheduling question at worktree-flow; state "
            "the git-vs-Crucible split instead:\n  " + "\n  ".join(offenders),
        )

    def test_s3_java_orchestration_template_teaches_the_post_db_scheduling_story(self):
        """java-orchestration.md: no DB-era verb, and readiness routed at Crucible.

        CR-MDB-028 F1 VERIFY finding 1. The Java memory template taught the
        `next → start → finish` loop with `cs`/`status`/`reconcile` and
        "ChangeSet DB mechanics" in the present tense. §S7's grep gate could not
        see it: the verbs are spelled as a BARE backticked list, never as
        `worktree-flow <verb>`, so no existing regex matched. This gate is
        per-surface and shape-independent — a roster check plus a DB-era token
        check plus the positive Crucible route.
        """
        rosters = [
            f"java-orchestration.md:{lineno}: {line.strip()}"
            f"  [retired: {','.join(sorted(verbs & set(RETIRED_VERBS)))}]"
            for lineno, line, verbs in _verb_enumeration_lines(JAVA_TEMPLATE)
            if verbs & set(RETIRED_VERBS)
        ]
        self.assertEqual(
            [],
            rosters,
            "skills-src/memory-templates/java-orchestration.md enumerates "
            "worktree-flow verbs C1 deleted; the roster is exactly "
            "start/status/sync/finish/abort:\n  " + "\n  ".join(rosters),
        )

        db_era = [
            f"java-orchestration.md:{lineno}: {line.strip()}"
            for lineno, line in _numbered(JAVA_TEMPLATE)
            if DB_ERA_VERB_TOKEN.search(line)
        ]
        self.assertEqual(
            [],
            db_era,
            "java-orchestration.md still spells a DB-era worktree-flow verb "
            "(`cs`/`reconcile`/`show`/`progress`) as a live instruction — the "
            "Crucible client has no such verb, so the reader is taught a "
            "command that cannot run:\n  " + "\n  ".join(db_era),
        )

        routed = [
            f"{lineno}: {line.strip()}"
            for lineno, line in _numbered(JAVA_TEMPLATE)
            if CRUCIBLE_NEXT_LINE.search(line)
        ]
        self.assertTrue(
            routed,
            "java-orchestration.md never names the Crucible client's `next` "
            "verb: a Java track's readiness question must be routed at "
            "`python-crucible.py next`, or the template teaches a loop with "
            "no scheduler.",
        )

        self.assertTrue(
            _states_the_split(_read(JAVA_TEMPLATE)),
            "java-orchestration.md drops the ChangeSet DB without stating "
            "what replaced it: one block must say worktree-flow owns what it "
            "derives from git (worktrees, ahead/behind, phase, merge) and "
            "Crucible owns queue membership, release, wave, seq, "
            "dependencies and readiness (§S3).",
        )

    def test_s3_no_skill_frontmatter_description_routes_the_queue_at_worktree_flow(self):
        """Skill `description:` frontmatter never advertises worktree-flow as the queue.

        CR-MDB-028 F1 VERIFY finding 2. A skill's frontmatter description is
        the ONLY text a harness reads before loading the bundle, so a stale
        route there misdirects every session that never opens the file —
        bootstrap's said a Mainline session "reads the worktree-flow queue
        board" while its own Step 3A already asked Crucible. No existing gate
        looked at frontmatter, and `SCHEDULING_TOKENS` carries no `queue`
        token, so the clause was invisible twice over.
        """
        offenders = []
        for path in sorted(SKILLS_SRC.glob("*/SKILL.md")):
            description = _frontmatter_description(path)
            if not description:
                continue
            for match in re.finditer(r"worktree-flow", description):
                start = max(0, match.start() - ROUTE_WINDOW)
                window = description[start : match.end() + ROUTE_WINDOW].replace(
                    "schedule_db", ""
                )
                if FRONTMATTER_ROUTING_TOKENS.search(window):
                    rel = path.relative_to(REPO_ROOT)
                    offenders.append(f"{rel} description: …{window.strip()}…")
                    break
        self.assertEqual(
            [],
            offenders,
            "a skill's frontmatter `description:` routes queue/scheduling at "
            "worktree-flow; the queue lives in Crucible and worktree-flow "
            "answers only git-derived worktree state:\n  "
            + "\n  ".join(offenders),
        )

    def test_s3_git_vs_crucible_split_is_stated_in_an_orchestration_reference(self):
        """The split is STATED, not implied (§S3): both halves, in one block.

        At least one of orchestration-common.md / orchestration-track.md must
        say that worktree-flow owns what it derives from git (worktrees,
        ahead/behind, phase, merge) and Crucible owns queue membership,
        release, wave, seq, dependencies and readiness.
        """
        stated = {
            path.name: _states_the_split(_read(path))
            for path in (COMMON_REF, TRACK_REF)
        }
        self.assertTrue(
            any(stated.values()),
            "neither orchestration reference states the git-vs-Crucible "
            "split; §S3 requires it verbatim so the next reader does not "
            f"have to infer it. Measured: {stated}",
        )


if __name__ == "__main__":
    unittest.main()
