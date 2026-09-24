"""The wake watcher stays alive: the Model B watcher first, and the exits
Sandesh reports (CR-MDB-026 §S1–§S5).

Five skill surfaces move together — ``skills-src/bootstrap/SKILL.md``,
``skills-src/shutdown/SKILL.md``, ``skills-src/model-b/references/sandesh.md``,
``orchestration-common.md`` and ``orchestration-mainline.md`` — so every
session launches, reads and stops its notifier the same way:

- §S1 ``sandesh.md`` §Bootstrap names the Model B watcher first (with it a
  woken session only fetches) and, as the fallback, ``sandesh notify`` run
  as a background process that notifies on exit — never inline, never under
  a deadline shorter than the watcher's timeout. The PRIME DIRECTIVE carries
  the seven-row exit table (``0 1 2 3 4 5 128+n``: reason, how to recognise
  it from the last log line, response) and cites ``sandesh notify --help``.
  Nothing under ``skills-src/`` relaunches after tombstoned / evicted /
  already live, or reads an unqualified exit as mail.
- §S2 ``bootstrap`` Step 1 + Guardrails name the same mechanism; the
  addressbook-first, exactly-one, never-inline and ``listening:true``
  re-probe rules remain.
- §S3 ``shutdown``'s final step stops the watcher through the Model B
  watcher, then the harness facility, then a targeted kill of your own
  address as the last resort; the machine-wide-kill ban and the kill-last /
  no-relaunch sentences are unchanged.
- §S4 the mainline inbox-watcher line and common's lifecycle bracket name
  the same mechanism.
- §S5 capabilities, not harness tools (DN §D18): the five files carry none
  of ``run_in_background``, ``TaskStop``, ``sandesh_watcher`` (gate proven
  to bite), rewritten fetch lines use the CLI form, and no skill reads or
  writes the Sandesh data directory.

Assertions pin meaning-bearing phrases and anchors, never whole rewritten
sentences, so the rewrite keeps its wording freedom. Stdlib only; reads the
repo tree only.
"""

import re
import unittest
from pathlib import Path

from tests._helpers import read_text as _read

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC = REPO_ROOT / "skills-src"

BOOTSTRAP_SKILL = SKILLS_SRC / "bootstrap" / "SKILL.md"
SHUTDOWN_SKILL = SKILLS_SRC / "shutdown" / "SKILL.md"
REFERENCES = SKILLS_SRC / "model-b" / "references"
SANDESH_REF = REFERENCES / "sandesh.md"
COMMON_REF = REFERENCES / "orchestration-common.md"
MAINLINE_REF = REFERENCES / "orchestration-mainline.md"

#: §S4/§S5 AC — the five files the forbidden-token gate covers.
GATED_FILES = (BOOTSTRAP_SKILL, SHUTDOWN_SKILL, SANDESH_REF, COMMON_REF, MAINLINE_REF)

#: §S4/§S5 AC — one harness's tool names and the Model B watcher's own tool.
FORBIDDEN_TOOL_TOKENS = ("run_in_background", "TaskStop", "sandesh_watcher")

#: Section headings (``## …`` line substrings) each test locates its text by.
#: Pinned: the AC keeps existing headings and anchors unchanged.
SANDESH_BOOTSTRAP_HEADING = "Bootstrap"
SANDESH_PRIME_HEADING = "PRIME DIRECTIVE"
BOOTSTRAP_STEP1_HEADING = "Step 1"
GUARDRAILS_HEADING = "Guardrails"
SHUTDOWN_FINAL_HEADING = "The common final step — kill your notifier LAST"
MAINLINE_INBOX_HEADING = "Inbox / coordination"
COMMON_LIFECYCLE_HEADING = "Session lifecycle"

#: §S5 — the CLI fetch form the rewritten lines use (quote style is free).
CLI_FETCH_RE = re.compile(
    r"sandesh fetch --project <Project> --to ['\"]<your address>['\"]"
)

MODEL_B_WATCHER_RE = re.compile(r"model b watcher", re.IGNORECASE)
#: The fallback capability: "a background process that notifies you when it
#: exits" — the words may move, the two ideas may not. The notification is
#: addressed to the SESSION ("notifies you / the session when"), so a bare
#: mention of the ``sandesh notify`` command near the word "exits" (e.g. "a
#: bare `sandesh notify --to …` exits 1") does not satisfy it (VERIFY F5).
BACKGROUND_PROCESS_RE = re.compile(r"background[- ]process", re.IGNORECASE)
NOTIFIES_ON_EXIT_RE = re.compile(
    r"\bnotif\w*\s+(?:you|the session)\s+when\b[^.|\n]{0,40}\bexit", re.IGNORECASE
)
NEGATED_RELAUNCH_RE = re.compile(
    r"\b(?:do not|don't|never|not|no)\b[^|.;]{0,30}\brelaunch", re.IGNORECASE
)
RELAUNCH_RE = re.compile(r"\brelaunch", re.IGNORECASE)

#: §S1 AC bullet 3 — the reasons after which a relaunch is forbidden.
TERMINAL_REASON_RE = re.compile(r"tombston|evict|already[- ]live", re.IGNORECASE)
#: §S1 AC bullet 3 — prose that reads an exit as mail without naming which
#: exit ("fires/exits", "any non-zero exit", "a watcher that exits is
#: relaunched", "the process is gone").
UNQUALIFIED_EXIT_RE = re.compile(
    r"fires/exits|fires or exits"
    r"|\b(?:any|every|a)\s+(?:non-zero\s+)?exit\b"
    r"|\b(?:a|any|every)\s+(?:watcher|notifier)\s+that\s+exits\b"
    r"|process is gone",
    re.IGNORECASE,
)
#: A unit that names which exit it means is qualified, not a violation.
EXIT_QUALIFIER_RE = re.compile(
    r"unless|except|terminal|tombston|evict|already[- ]live|dedup"
    r"|exit\s*`?\d|exit code\s*`?\d|128\s*\+\s*n",
    re.IGNORECASE,
)

#: §S5 AC — direct paths into Sandesh's own data directory.
SANDESH_DATA_DIR_RE = re.compile(
    r"(?:~|\$HOME|\$\{?XDG_DATA_HOME\}?|\.local/share)/sandesh\b"
    r"|sandesh[\w./-]*\.(?:db|sqlite3?)\b",
    re.IGNORECASE,
)

#: §S1 — the seven exit rows: (reason pattern, response check).
#: Response kinds: "relaunch" (a positive, un-negated relaunch) or
#: "no-relaunch" (a negated relaunch).
EXIT_ROWS = {
    "0": (r"mail|✉|unread", "relaunch"),
    "1": (r"error", "relaunch"),
    "2": (r"timed out|timeout", "relaunch"),
    "3": (r"tombston", "no-relaunch"),
    "4": (r"evict", "no-relaunch"),
    "5": (r"already[- ]live|dedup", "no-relaunch"),
    "128+n": (r"signal", "relaunch"),
}


def _norm(text: str) -> str:
    """Collapse all whitespace runs to one space (prose wraps freely)."""
    return re.sub(r"\s+", " ", text).strip()


def _section(test: unittest.TestCase, path: Path, heading: str) -> str:
    """The text under the ``## `` heading containing ``heading``, up to the
    next ``## `` heading. A missing heading FAILS (never errors): the AC keeps
    pinned headings unchanged."""
    lines = _read(path).splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.startswith("## ") and heading in line:
            start = idx
            break
    if start is None:
        test.fail(f"{path.relative_to(REPO_ROOT)} lost its '## …{heading}…' heading")
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if lines[idx].startswith("## "):
            end = idx
            break
    return "\n".join(lines[start:end])


def _units(text: str):
    """Split markdown into judgeable units: each table row, and each sentence
    of each prose block (a block ends at a blank line, heading, list item or
    table row). Yields ``(line_number, unit_text)``."""
    blocks = []
    current, current_line = [], None
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        starts_block = (
            not line
            or line.startswith("#")
            or line.startswith("|")
            or re.match(r"^(?:[-*]|\d+\.)\s", line) is not None
        )
        if starts_block and current:
            blocks.append((current_line, " ".join(current)))
            current, current_line = [], None
        if not line or line.startswith("#"):
            continue
        if line.startswith("|"):
            blocks.append((lineno, line))
            continue
        if current_line is None:
            current_line = lineno
        current.append(line)
    if current:
        blocks.append((current_line, " ".join(current)))
    for lineno, block in blocks:
        if block.startswith("|"):
            yield lineno, block
            continue
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z*`(])", block):
            yield lineno, sentence


def _relaunch_after_terminal_claims(text: str):
    """Units naming tombstoned / evicted / already live that relaunch without
    any negated relaunch (§S1 AC bullet 3, first half)."""
    hits = []
    for lineno, unit in _units(text):
        if (
            TERMINAL_REASON_RE.search(unit)
            and RELAUNCH_RE.search(unit)
            and not NEGATED_RELAUNCH_RE.search(unit)
        ):
            hits.append((lineno, unit))
    return hits


def _exit_as_mail_claims(text: str):
    """Units that act on an exit whose code/reason they never name — reading
    "the process is gone" as mail (§S1 AC bullet 3, second half)."""
    hits = []
    for lineno, unit in _units(text):
        if (
            UNQUALIFIED_EXIT_RE.search(unit)
            and re.search(r"fetch|relaunch|mail", unit, re.IGNORECASE)
            and not EXIT_QUALIFIER_RE.search(unit)
        ):
            hits.append((lineno, unit))
    return hits


#: VERIFY F6 — a relaunch the session performs must be qualified as the
#: fallback path ("without the Model B watcher") or as a terminal-exit
#: exception; the Model B watcher relaunches itself.
RELAUNCH_QUALIFIER_RE = re.compile(
    r"fallback|without (?:it|the model b watcher)|model b watcher is not installed"
    r"|terminal|tombston|evict|already[- ]live",
    re.IGNORECASE,
)
#: Mentions of relaunch that are names, the Model B watcher's own behaviour, or
#: a roster-liveness description ("not reachable \u2026 until it relaunches"),
#: never an instruction to the session.
RELAUNCH_NON_INSTRUCTION_RE = re.compile(
    r"relaunch-on-exit|watcher-relaunch|relaunch\w*\s+itself|until it relaunches",
    re.IGNORECASE,
)
#: VERIFY F6 — the explicit allowlist beyond the exit-table rows:
#: bootstrap's "fix the command and relaunch" after ``listening:false``, and
#: shutdown's "next run, /bootstrap relaunches the watcher".
RELAUNCH_ALLOWLIST = {
    BOOTSTRAP_SKILL: (re.compile(r"listening:false`?, fix the command and relaunch"),),
    SHUTDOWN_SKILL: (re.compile(r"`/bootstrap` brings you back \(re-register \+ relaunch the watcher\)"),),
}


def _is_exit_table_row(unit: str) -> bool:
    if not unit.startswith("|"):
        return False
    cells = [c.strip() for c in unit.strip("|").split("|")]
    return any(_exit_cell_key(c) in EXIT_ROWS for c in cells)


def _unqualified_relaunch_claims(text: str, allow=()):
    """Units instructing a relaunch without naming the fallback path or a
    terminal-exit exception (VERIFY F6). Exit-table rows and ``allow``
    patterns are exempt; negated relaunches are not instructions."""
    hits = []
    for lineno, unit in _units(text):
        if _is_exit_table_row(unit) or any(p.search(unit) for p in allow):
            continue
        residue = NEGATED_RELAUNCH_RE.sub(" ", RELAUNCH_NON_INSTRUCTION_RE.sub(" ", unit))
        if RELAUNCH_RE.search(residue) and not RELAUNCH_QUALIFIER_RE.search(unit):
            hits.append((lineno, unit))
    return hits


def _forbidden_tool_hits(text: str):
    """Every (line, token) where a gated harness tool name appears (§S4/§S5)."""
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for token in FORBIDDEN_TOOL_TOKENS:
            if token in line:
                hits.append((lineno, token))
    return hits


def _skill_markdown_files():
    return sorted(p for p in SKILLS_SRC.rglob("*.md") if p.is_file())


def _table_rows(section: str):
    """Markdown table rows of ``section`` as lists of stripped cells
    (separator rows dropped)."""
    rows = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", c) for c in cells if c):
            continue
        rows.append(cells)
    return rows


def _exit_cell_key(cell: str) -> str:
    return re.sub(r"[\s`*]", "", cell)


def _pos(test: unittest.TestCase, pattern, text: str, msg: str) -> int:
    """Start offset of the first ``pattern`` match in ``text``; a missing
    match FAILS the test with ``msg`` (never an AttributeError)."""
    match = re.search(pattern, text)
    if match is None:
        test.fail(msg)
    return match.start()


# ---------------------------------------------------------------------------
# §S1 — sandesh.md: the launch mechanism and the exit table
# ---------------------------------------------------------------------------


class SandeshReferenceS1Test(unittest.TestCase):
    """§S1 — ``sandesh.md`` §Bootstrap and the PRIME DIRECTIVE."""

    def setUp(self):
        self.bootstrap = _norm(_section(self, SANDESH_REF, SANDESH_BOOTSTRAP_HEADING))
        self.prime = _section(self, SANDESH_REF, SANDESH_PRIME_HEADING)

    def test_s1_bootstrap_names_the_model_b_watcher_before_the_fallback(self):
        watcher = _pos(
            self, MODEL_B_WATCHER_RE, self.bootstrap,
            "sandesh.md §Bootstrap must name the Model B watcher as the way to start the notifier",
        )
        fallback = _pos(
            self, BACKGROUND_PROCESS_RE, self.bootstrap,
            "sandesh.md §Bootstrap must name the background-process fallback",
        )
        self.assertLess(
            watcher, fallback,
            "the Model B watcher is named FIRST; the background process is the fallback",
        )

    def test_s1_bootstrap_states_a_woken_session_only_fetches_with_the_model_b_watcher(self):
        self.assertRegex(
            self.bootstrap, re.compile(r"\bonly fetch", re.IGNORECASE),
            "with the Model B watcher a woken session ONLY fetches — the watcher relaunches itself",
        )

    def test_s1_bootstrap_fallback_runs_sandesh_notify_as_a_background_process_notifying_on_exit(self):
        self.assertRegex(
            self.bootstrap,
            re.compile(r"not installed|without the model b watcher|isn't installed|is absent", re.IGNORECASE),
            "the fallback applies when the Model B watcher is not installed",
        )
        self.assertIn('sandesh notify --to "<your address>" --project <Project>', self.bootstrap)
        self.assertRegex(
            self.bootstrap, NOTIFIES_ON_EXIT_RE,
            "the fallback is a background process that NOTIFIES the session when it exits",
        )

    def test_s1_bootstrap_fallback_is_never_inline_and_never_under_a_shorter_deadline(self):
        self.assertRegex(
            self.bootstrap, re.compile(r"\binline\b", re.IGNORECASE),
            "never inline (it blocks) must remain",
        )
        self.assertRegex(
            self.bootstrap, re.compile(r"\bdeadline\b[^.]{0,80}\bshorter\b|\bshorter\b[^.]{0,80}\bdeadline\b", re.IGNORECASE),
            "never as a job with a deadline shorter than the watcher's timeout",
        )
        self.assertRegex(
            self.bootstrap, re.compile(r"\btimeout\b", re.IGNORECASE),
            "the deadline is measured against the watcher's own timeout",
        )

    def test_s1_prime_directive_table_carries_exactly_the_seven_exit_rows(self):
        rows = _table_rows(self.prime)
        keys = []
        for cells in rows:
            keys.extend(k for k in (_exit_cell_key(c) for c in cells) if k in EXIT_ROWS)
        for code in EXIT_ROWS:
            self.assertEqual(
                keys.count(code), 1,
                f"the PRIME DIRECTIVE table must carry exactly one row for exit {code!r}; "
                f"exit cells found: {keys}",
            )

    def _row(self, code: str) -> str:
        for cells in _table_rows(self.prime):
            if any(_exit_cell_key(c) == code for c in cells):
                return " | ".join(cells)
        self.fail(f"the PRIME DIRECTIVE table has no row for exit {code!r}")

    def _assert_row(self, code: str):
        reason_re, response = EXIT_ROWS[code]
        row = self._row(code)
        self.assertRegex(row, re.compile(reason_re, re.IGNORECASE), f"exit {code} row must name its reason")
        if response == "relaunch":
            self.assertRegex(row, RELAUNCH_RE, f"exit {code}'s response relaunches")
            self.assertNotRegex(row, NEGATED_RELAUNCH_RE, f"exit {code} must not forbid the relaunch")
        else:
            self.assertRegex(row, NEGATED_RELAUNCH_RE, f"exit {code}'s response is: do NOT relaunch")
        return row

    def test_s1_exit_0_mail_arrived_row_fetches_then_relaunches(self):
        row = self._assert_row("0")
        fetch = _pos(self, re.compile(r"fetch", re.IGNORECASE), row, "exit 0 (mail) is answered by a fetch")
        relaunch = _pos(self, RELAUNCH_RE, row, "exit 0 relaunches")
        self.assertLess(fetch, relaunch, "exit 0: fetch BEFORE relaunch")

    def test_s1_exit_1_error_row_fixes_the_command_then_relaunches(self):
        row = self._assert_row("1")
        self.assertRegex(row, re.compile(r"usage|config", re.IGNORECASE), "exit 1 is a usage or configuration error")
        fix = _pos(self, re.compile(r"\bfix", re.IGNORECASE), row, "exit 1: fix the command")
        relaunch = _pos(self, RELAUNCH_RE, row, "exit 1 relaunches")
        self.assertLess(fix, relaunch, "exit 1: fix, THEN relaunch")

    def test_s1_exit_2_timed_out_row_relaunches_with_nothing_to_fetch(self):
        row = self._assert_row("2")
        self.assertRegex(
            row, re.compile(r"nothing to fetch|no mail|without fetch|no fetch", re.IGNORECASE),
            "exit 2 (timed out): relaunch; there is nothing to fetch",
        )

    def test_s1_exit_3_tombstoned_row_is_reported_and_never_relaunched(self):
        row = self._assert_row("3")
        self.assertRegex(row, re.compile(r"report", re.IGNORECASE), "exit 3: report it")

    def test_s1_exit_4_evicted_row_is_reported_and_never_relaunched(self):
        row = self._assert_row("4")
        self.assertRegex(row, re.compile(r"report", re.IGNORECASE), "exit 4: report it")

    def test_s1_exit_5_already_live_row_is_never_relaunched(self):
        row = self._assert_row("5")
        self.assertRegex(
            row, re.compile(r"already holds|already running|already listening|holds the address", re.IGNORECASE),
            "exit 5: a watcher already holds the address",
        )

    def test_s1_exit_128_plus_n_signal_row_relaunches_unless_you_stopped_it(self):
        row = self._assert_row("128+n")
        self.assertRegex(
            row, re.compile(r"unless[^|]{0,40}\byou(?:rself)?\b|\byourself\b", re.IGNORECASE),
            "a signal exit relaunches — unless you stopped it yourself",
        )

    def test_s1_prime_directive_recognises_each_reason_from_the_last_log_line(self):
        self.assertRegex(
            _norm(self.prime), re.compile(r"last log line", re.IGNORECASE),
            "the table says how to recognise each reason from the last log line",
        )

    def test_s1_prime_directive_cites_sandesh_notify_help_as_the_authority(self):
        self.assertIn(
            "sandesh notify --help", self.prime,
            "the PRIME DIRECTIVE must cite `sandesh notify --help` as Sandesh's authority for the reasons",
        )

    def test_s1_prime_directive_fetches_with_the_cli_form_before_relaunching(self):
        prime = _norm(self.prime)
        fetch = CLI_FETCH_RE.search(prime)
        self.assertIsNotNone(
            fetch,
            "fetching in the PRIME DIRECTIVE uses the CLI form "
            "`sandesh fetch --project <Project> --to '<your address>'` (§S5)",
        )
        self.assertRegex(
            prime,
            re.compile(
                r"fetch\w*[^.]{0,160}\b(?:before|then|first)\b[^.]{0,80}\brelaunch"
                r"|relaunch\w*[^.]{0,40}\bafter\b[^.]{0,80}\bfetch",
                re.IGNORECASE,
            ),
            "fetching precedes relaunching whenever mail may have arrived",
        )


class NoRelaunchAfterTerminalExitS1Test(unittest.TestCase):
    """§S1 AC bullet 3 — across ``skills-src/``: no relaunch after tombstoned,
    evicted or already live; no unqualified exit read as mail."""

    def test_s1_no_skill_relaunches_after_terminal_exit_or_reads_any_exit_as_mail(self):
        offending = []
        for path in _skill_markdown_files():
            rel = path.relative_to(REPO_ROOT)
            text = _read(path)
            for lineno, unit in _relaunch_after_terminal_claims(text):
                offending.append(f"{rel}:{lineno} relaunches after a terminal exit: {unit}")
            for lineno, unit in _exit_as_mail_claims(text):
                offending.append(f"{rel}:{lineno} acts on an unqualified exit: {unit}")
        self.assertEqual(offending, [], "\n  ".join(["skills-src violations:"] + offending))

    def test_s1_relaunch_after_terminal_detector_bites(self):
        violating = "If the project was tombstoned, fetch and relaunch the watcher at once."
        self.assertEqual(len(_relaunch_after_terminal_claims(violating)), 1, violating)
        table_row = "| evicted (another notifier took the address) | `4` | relaunch |"
        self.assertEqual(len(_relaunch_after_terminal_claims(table_row)), 1, table_row)
        permitted = "| tombstoned (project retired) | `3` | do **not** relaunch; report it |"
        self.assertEqual(_relaunch_after_terminal_claims(permitted), [], permitted)

    def test_s1_exit_as_mail_detector_bites(self):
        for violating in (
            "The instant the watcher fires/exits (you get the task-notification), "
            "`sandesh_fetch` AND relaunch in the SAME turn.",
            "Any non-zero exit means mail arrived: fetch it.",
            "Everywhere else a watcher that exits is relaunched the same turn (never left dead).",
        ):
            self.assertEqual(len(_exit_as_mail_claims(violating)), 1, violating)
        for permitted in (
            "On exit `0` (mail arrived) fetch, then relaunch.",
            "A watcher that exits is relaunched unless the exit was terminal (tombstoned, evicted, already live).",
        ):
            self.assertEqual(_exit_as_mail_claims(permitted), [], permitted)

    def test_s1_notifies_on_exit_detector_ignores_a_bare_notify_that_exits(self):
        """VERIFY F5 \u2014 the command merely exiting is not the fallback
        capability; the process must notify the SESSION when it exits."""
        bare = ("The CLI REQUIRES `--project <Project>`; a bare `sandesh notify --to \u2026` "
                "exits 1 and silently never listens (`listening:false`).")
        self.assertNotRegex(bare, NOTIFIES_ON_EXIT_RE, bare)
        for permitted in (
            "run it as a background process that notifies you when it exits",
            "a background process that notifies the session when it exits",
        ):
            self.assertRegex(permitted, NOTIFIES_ON_EXIT_RE, permitted)


class RelaunchIsQualifiedF6Test(unittest.TestCase):
    """VERIFY F6 \u2014 across the five gated files, every sentence that tells
    the session to relaunch the watcher names the fallback path ("without the
    Model B watcher") or a terminal-exit exception. Allowlisted: the exit-table
    rows, bootstrap's fix-and-relaunch after ``listening:false``, and
    shutdown's bootstrap-relaunches-next-run line."""

    def test_f6_every_session_relaunch_is_qualified(self):
        offending = []
        for path in GATED_FILES:
            allow = RELAUNCH_ALLOWLIST.get(path, ())
            for lineno, unit in _unqualified_relaunch_claims(_read(path), allow):
                offending.append(f"{path.relative_to(REPO_ROOT)}:{lineno} unqualified relaunch: {unit}")
        self.assertEqual(offending, [], "\n  ".join(["unqualified relaunch instructions:"] + offending))

    def test_f6_allowlist_entries_still_match_their_lines(self):
        for path, patterns in RELAUNCH_ALLOWLIST.items():
            text = _norm(_read(path))
            for pattern in patterns:
                self.assertRegex(text, pattern, f"stale allowlist entry for {path.relative_to(REPO_ROOT)}")

    def test_f6_unqualified_relaunch_detector_bites(self):
        for violating in (
            "The standalone `sandesh notify` watcher exits when To-addressed mail arrives \u2192 "
            "the host re-invokes the session \u2192 it `sandesh_fetch`es \u2192 **relaunches the watcher**.",
            "Acks arrive as Sandesh mail; your watcher wakes on them (fetch + relaunch as normal \u2014 the "
            "notifier stays up until *your* final step).",
        ):
            self.assertEqual(len(_unqualified_relaunch_claims(violating)), 1, violating)
        for permitted in (
            "The standalone `sandesh notify` watcher exits when To-addressed mail arrives \u2192 the host "
            "re-invokes the session \u2192 it fetches (`sandesh fetch --project <Project> --to '<your address>'`) "
            "\u2192 and, on the fallback path, relaunches the watcher (the Model B watcher relaunches itself).",
            "It supervises `sandesh notify`, stays running and relaunches itself.",
            "Do not relaunch.",
            "| error (usage or configuration) | `1` | fix the command, then relaunch |",
        ):
            self.assertEqual(_unqualified_relaunch_claims(permitted), [], permitted)


# ---------------------------------------------------------------------------
# §S2 — bootstrap Step 1 and Guardrails
# ---------------------------------------------------------------------------


class BootstrapNotifierS2Test(unittest.TestCase):
    """§S2 — ``bootstrap`` Step 1 + Guardrails name the §S1 mechanism and keep
    the existing discipline."""

    def setUp(self):
        self.step1 = _norm(_section(self, BOOTSTRAP_SKILL, BOOTSTRAP_STEP1_HEADING))
        self.guardrails = _norm(_section(self, BOOTSTRAP_SKILL, GUARDRAILS_HEADING))

    def test_s2_step1_names_the_model_b_watcher_before_the_background_process_fallback(self):
        watcher = _pos(self, MODEL_B_WATCHER_RE, self.step1,
                       "bootstrap Step 1 must start the notifier with the Model B watcher")
        fallback = _pos(self, BACKGROUND_PROCESS_RE, self.step1,
                        "bootstrap Step 1 must name the background-process fallback")
        self.assertLess(watcher, fallback, "Model B watcher first, fallback second")
        self.assertRegex(self.step1, NOTIFIES_ON_EXIT_RE, "the fallback notifies the session when it exits")
        self.assertIn('sandesh notify --to "<your address>" --project <Project>', self.step1)

    def test_s2_step1_fallback_is_never_inline_and_never_under_a_shorter_deadline(self):
        self.assertRegex(self.step1, re.compile(r"\binline\b", re.IGNORECASE), "never inline — it blocks")
        self.assertRegex(
            self.step1,
            re.compile(r"\bdeadline\b[^.]{0,80}\bshorter\b|\bshorter\b[^.]{0,80}\bdeadline\b", re.IGNORECASE),
            "never under a deadline shorter than the watcher's timeout",
        )

    def test_s2_step1_woken_session_fetches_with_the_cli_form(self):
        self.assertRegex(
            self.step1, CLI_FETCH_RE,
            "Step 1's fetch uses `sandesh fetch --project <Project> --to '<your address>'` (§S5)",
        )
        self.assertNotIn("sandesh_fetch", self.step1, "the rewritten Step 1 fetch is the CLI form, not the MCP verb")

    def test_s2_step1_keeps_the_addressbook_check_before_any_launch(self):
        addressbook = self.step1.find("sandesh_addressbook")
        launch = self.step1.find("sandesh notify --to")
        self.assertNotEqual(addressbook, -1, "Step 1 checks the addressbook first")
        self.assertNotEqual(launch, -1, "Step 1 still names the notify command")
        self.assertLess(addressbook, launch, "the addressbook check precedes the launch")
        self.assertRegex(
            self.step1, re.compile(r"only if not already `?listening:true`?", re.IGNORECASE),
            "a watcher is started ONLY if the address is not already listening:true",
        )

    def test_s2_step1_keeps_exactly_one_per_address_and_the_listening_reprobe(self):
        self.assertRegex(self.step1, re.compile(r"exactly one\b[^.]{0,20}per address", re.IGNORECASE))
        launch = self.step1.find("sandesh notify --to")
        reprobe = self.step1.rfind("listening:true")
        self.assertNotEqual(launch, -1)
        self.assertGreater(reprobe, launch, "listening:true is re-probed AFTER starting the watcher")
        self.assertRegex(self.step1, re.compile(r"re-?confirm|re-?probe", re.IGNORECASE))

    def test_s2_guardrails_name_the_model_b_watcher_with_exactly_one_per_address(self):
        self.assertRegex(self.guardrails, MODEL_B_WATCHER_RE, "the Guardrails launch line names the Model B watcher")
        self.assertRegex(self.guardrails, BACKGROUND_PROCESS_RE, "and the background-process fallback")
        self.assertRegex(self.guardrails, re.compile(r"exactly one\b[^.]{0,20}per address", re.IGNORECASE))
        self.assertRegex(
            self.guardrails, re.compile(r"never machine-wide", re.IGNORECASE),
            "the machine-wide-kill guardrail stays",
        )


# ---------------------------------------------------------------------------
# §S3 — shutdown's final step
# ---------------------------------------------------------------------------

#: §S3 AC — "the kill-last / no-relaunch sentences are unchanged" (normalised).
SHUTDOWN_UNCHANGED_SENTENCES = (
    "For **every** orchestrator, the final action is killing the notifier it owns, with **no "
    "relaunch** — the single documented override of the relaunch-on-exit prime directive, applying "
    "ONLY here, at a confirmed shutdown's last step.",
    "Kill it only when everything else (drain, merge, commit, ack/report) is done.",
    "Shutdown kills; bootstrap revives.",
    "**Kill ONLY your own notifier**, as the LAST step, and do NOT relaunch it. This is the sole "
    "place the relaunch-on-exit directive is overridden — everywhere else, a dead watcher is a bug.",
)


class ShutdownFinalStepS3Test(unittest.TestCase):
    """§S3 — the watcher stops through the Model B watcher, then the harness
    facility, then a targeted kill of your own address."""

    def setUp(self):
        self.final = _norm(_section(self, SHUTDOWN_SKILL, SHUTDOWN_FINAL_HEADING))

    def test_s3_final_step_stops_through_model_b_watcher_then_facility_then_targeted_kill(self):
        watcher = _pos(self, MODEL_B_WATCHER_RE, self.final,
                       "the final step stops the notifier through the Model B watcher first")
        facility = _pos(self, re.compile(r"facility|background process", re.IGNORECASE), self.final,
                        "then through the harness facility that runs the fallback process")
        kill = _pos(self, re.compile(re.escape("pkill -f")), self.final, "then the targeted kill")
        self.assertLess(watcher, facility, "Model B watcher before the harness facility")
        self.assertLess(facility, kill, "harness facility before the targeted kill")

    def test_s3_targeted_kill_of_your_own_address_is_the_last_resort(self):
        self.assertIn("sandesh notify --to '<your exact address>'", self.final, "the kill targets your own address")
        self.assertRegex(self.final, re.compile(r"last resort", re.IGNORECASE),
                         "the targeted kill is the LAST resort")
        self.assertRegex(self.final, re.compile(r"your own process only|own process only|only your own", re.IGNORECASE))

    def test_s3_final_step_still_forbids_machine_wide_kills(self):
        self.assertRegex(self.final, re.compile(r"never\W*\s*a machine-wide", re.IGNORECASE))
        self.assertIn("pkill sandesh", self.final, "the forbidden broad-kill example stays named")

    def test_s3_kill_last_and_no_relaunch_sentences_are_unchanged(self):
        whole = _norm(_read(SHUTDOWN_SKILL))
        missing = [s for s in SHUTDOWN_UNCHANGED_SENTENCES if _norm(s) not in whole]
        self.assertEqual(missing, [], f"shutdown's kill-last / no-relaunch sentences changed: {missing}")

    def test_s3_final_step_names_no_harness_stop_tool(self):
        for token in ("TaskStop", "run_in_background"):
            self.assertNotIn(token, self.final, f"the final step names the capability, not {token}")
        self.assertRegex(self.final, re.compile(r"stop your watcher|stop the watcher", re.IGNORECASE),
                         "the capability phrase: stop your watcher")


# ---------------------------------------------------------------------------
# §S4 — the other watcher lines agree
# ---------------------------------------------------------------------------


class WatcherLinesAgreeS4Test(unittest.TestCase):
    """§S4 — mainline's inbox-watcher line and common's bracket lines name the
    §S1 mechanism."""

    def _inbox_watcher_line(self) -> str:
        section = _section(self, MAINLINE_REF, MAINLINE_INBOX_HEADING)
        items = [u for _, u in _units(section) if re.search(r"inbox watcher", u, re.IGNORECASE)]
        self.assertEqual(len(items), 1, f"exactly one inbox-watcher line under '{MAINLINE_INBOX_HEADING}': {items}")
        return items[0]

    def test_s4_mainline_inbox_watcher_line_names_the_model_b_watcher_and_fallback(self):
        line = self._inbox_watcher_line()
        self.assertRegex(line, MODEL_B_WATCHER_RE, "the inbox watcher runs as the Model B watcher")
        self.assertRegex(line, BACKGROUND_PROCESS_RE, "or, without it, as a background process")
        self.assertNotRegex(line, re.compile(r"\bin the background at session start\b"),
                            "the bare 'in the background' launch is replaced by the named mechanism")

    def test_s4_mainline_inbox_watcher_line_keeps_the_fetch_and_reply_discipline(self):
        line = self._inbox_watcher_line()
        self.assertRegex(line, re.compile(r"fetch", re.IGNORECASE), "a request is still fetched")
        self.assertRegex(line, re.compile(r"reply|directive", re.IGNORECASE), "and answered")

    def test_s4_common_lifecycle_bracket_names_the_model_b_watcher_and_fallback(self):
        section = _norm(_section(self, COMMON_REF, COMMON_LIFECYCLE_HEADING))
        self.assertRegex(section, MODEL_B_WATCHER_RE, "the bootstrap bracket names the Model B watcher")
        self.assertRegex(section, BACKGROUND_PROCESS_RE, "and the background-process fallback")
        self.assertIn("/bootstrap <role>", section, "the bracket's bootstrap anchor stays")
        self.assertIn("/shutdown", section, "the bracket's shutdown anchor stays")


# ---------------------------------------------------------------------------
# §S5 — capabilities, not harness tools (DN §D18)
# ---------------------------------------------------------------------------


class CapabilitiesNotHarnessToolsS5Test(unittest.TestCase):
    """§S4/§S5 AC — the forbidden-token gate over the five files, proven to
    bite; no direct Sandesh data-directory access anywhere in the skills."""

    def test_s5_gated_files_name_no_harness_or_watcher_tool(self):
        offending = []
        for path in GATED_FILES:
            self.assertTrue(path.is_file(), f"{path} must exist")
            for lineno, token in _forbidden_tool_hits(_read(path)):
                offending.append(f"{path.relative_to(REPO_ROOT)}:{lineno} names `{token}`")
        self.assertEqual(offending, [], "\n  ".join(["harness tool names in the gated skills:"] + offending))

    def test_s5_forbidden_tool_gate_detector_bites(self):
        synthetic = (
            "Launch it with Bash `run_in_background`.\n"
            "Stop it with `TaskStop` on its task id.\n"
            "Or call the `sandesh_watcher` tool.\n"
            "Stop your watcher through the Model B watcher.\n"
        )
        self.assertEqual(
            _forbidden_tool_hits(synthetic),
            [(1, "run_in_background"), (2, "TaskStop"), (3, "sandesh_watcher")],
            "the gate must report each forbidden token on its own line, and nothing on the capability line",
        )

    def test_s5_rewritten_watcher_sections_fetch_through_the_cli_not_the_mcp_verb(self):
        sections = {
            "sandesh.md §Bootstrap": _section(self, SANDESH_REF, SANDESH_BOOTSTRAP_HEADING),
            "sandesh.md PRIME DIRECTIVE": _section(self, SANDESH_REF, SANDESH_PRIME_HEADING),
            "bootstrap Step 1": _section(self, BOOTSTRAP_SKILL, BOOTSTRAP_STEP1_HEADING),
            "shutdown final step": _section(self, SHUTDOWN_SKILL, SHUTDOWN_FINAL_HEADING),
        }
        offending = [name for name, text in sections.items() if "sandesh_fetch" in text]
        self.assertEqual(offending, [], f"rewritten watcher lines still fetch through the MCP verb: {offending}")

    def test_s5_no_skill_touches_the_sandesh_data_directory(self):
        offending = []
        for path in _skill_markdown_files():
            for lineno, line in enumerate(_read(path).splitlines(), start=1):
                if SANDESH_DATA_DIR_RE.search(line):
                    offending.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
        self.assertEqual(offending, [], "skills reach into Sandesh's data directory:\n  " + "\n  ".join(offending))

    def test_s5_sandesh_data_directory_detector_bites(self):
        for violating in (
            "Read ~/.local/share/sandesh/inbox to see pending mail.",
            "rm $XDG_DATA_HOME/sandesh/lock",
            "sqlite3 sandesh.db 'select * from messages'",
        ):
            self.assertRegex(violating, SANDESH_DATA_DIR_RE, violating)
        self.assertNotRegex(
            "Run `sandesh fetch --project <Project> --to '<your address>'`.", SANDESH_DATA_DIR_RE,
        )


if __name__ == "__main__":
    unittest.main()
