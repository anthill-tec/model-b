"""Sandesh's wake watcher in the skills: started through the harness's Sandesh
extension, supervised by it, never relaunched by the orchestrator (CR-MDB-047
§S3; design reference DN-multi-harness §D20 with its Sandesh 0.4.0 amendment,
and §D18 — skills name capabilities and CLIs, never a harness tool).

Six skill surfaces state the wake rules and must agree:
``skills-src/bootstrap/SKILL.md``, ``skills-src/shutdown/SKILL.md`` and, under
``skills-src/model-b/references/``, ``sandesh.md``, ``orchestration-common.md``,
``orchestration-mainline.md`` and ``orchestration-track.md``.

- Bootstrap Step 1: the role's address (``Mainline - <Project>`` / ``Track <N> -
  <Project>``, ``<Project>`` = ``SANDESH_PROJECT``); the warning for an unset or
  mismatched ``$SANDESH_ADDRESS`` (a Track launched without its ``env
  SANDESH_ADDRESS=…`` override, direnv exporting the Mainline address), its
  remediation, and carrying on with the address passed explicitly; register when
  absent or inactive, THEN start Sandesh's wake watcher for that address and
  project, THEN confirm with ``sandesh addressbook --project <Project> --format
  toon --fields address,status,listening``; a missing extension leaves the
  session without a wake, says so and names the remediation.
- After a wake: fetch only, never relaunch; on a stop notice re-check liveness,
  start the watcher again once for exit 1 or a signal, report a tombstone (3) or
  an eviction (4) — Mainline to the user, a Track to Mainline.
- Removed everywhere under ``skills-src/``: "relaunch" for the wake (the
  relaunch-on-exit rule), the plain background ``sandesh notify`` launch, the
  Model B watcher and its ``/watcher`` command, ``pkill``, the human addressbook
  table (``● live``), and every harness tool name (``sandesh_*`` included).
- Shutdown's final step stops its own watcher by address (Sandesh's extension or
  ``/sandesh-watcher stop <your address>``), then unregisters with the CLI; the
  stop is the step's documented exception.
- ``sandesh.md`` (wake section, exit table, Mainline's own watcher),
  ``orchestration-common`` (the bracket and the notifier-kill override),
  ``orchestration-mainline`` (the inbox watcher) and ``orchestration-track``
  (shutdown) agree.

Rules are checked phrase-level inside ONE bullet, paragraph or table row (see
:func:`_blocks`), never as whole sentences and never by line number; every gate
detector is proven on synthetic text first.

MIGRATED at CR-MDB-047 C2 RED. Until this CR the module gated CR-MDB-026: the
Model B watcher first, a plain background ``sandesh notify`` as the fallback,
and a seven-row relaunch table. §S3 removes all three, so:

- RETIRED (they pinned what §S3 removes):
  ``SandeshReferenceS1Test`` (all 15: the Model B watcher before the fallback,
  only-fetch with the Model B watcher, the background-process fallback, never
  inline / no shorter deadline, the seven relaunch rows 0–5 and 128+n, the last
  log line, the ``sandesh notify --help`` citation, fetch-before-relaunch);
  ``NoRelaunchAfterTerminalExitS1Test.test_s1_notifies_on_exit_detector_ignores_a_bare_notify_that_exits``;
  ``RelaunchIsQualifiedF6Test`` (all 3 — superseded by the unconditional
  :class:`WakeIsNeverRelaunchedTest`);
  ``BootstrapNotifierS2Test.test_s2_step1_names_the_model_b_watcher_before_the_background_process_fallback``,
  ``…test_s2_step1_fallback_is_never_inline_and_never_under_a_shorter_deadline``;
  ``ShutdownFinalStepS3Test.test_s3_final_step_stops_through_model_b_watcher_then_facility_then_targeted_kill``,
  ``…test_s3_targeted_kill_of_your_own_address_is_the_last_resort``,
  ``…test_s3_final_step_still_forbids_machine_wide_kills`` (named ``pkill sandesh``),
  ``…test_s3_kill_last_and_no_relaunch_sentences_are_unchanged``;
  ``WatcherLinesAgreeS4Test`` (all 3);
  ``CapabilitiesNotHarnessToolsS5Test.test_s5_rewritten_watcher_sections_fetch_through_the_cli_not_the_mcp_verb``
  (superseded by the all-skills ``sandesh_*`` gate).
- MIGRATED (intent kept, new wording):
  ``BootstrapNotifierS2Test.test_s2_step1_woken_session_fetches_with_the_cli_form``
  → :meth:`BootstrapStep1WakeTest.test_a_woken_session_only_fetches_with_the_cli_form`;
  ``…test_s2_step1_keeps_the_addressbook_check_before_any_launch`` and
  ``…test_s2_step1_keeps_exactly_one_per_address_and_the_listening_reprobe``
  → :meth:`BootstrapStep1WakeTest.test_registers_then_starts_then_confirms_in_that_order`;
  ``…test_s2_guardrails_name_the_model_b_watcher_with_exactly_one_per_address``
  → :meth:`BootstrapStep1WakeTest.test_guardrails_keep_exactly_one_per_address_and_no_machine_wide_kill`;
  ``ShutdownFinalStepS3Test.test_s3_final_step_names_no_harness_stop_tool``
  → :meth:`ShutdownFinalStepTest.test_final_step_names_no_harness_stop_tool`;
  ``CapabilitiesNotHarnessToolsS5Test.test_s5_gated_files_name_no_harness_or_watcher_tool``
  and its detector → :class:`NoHarnessToolNameTest` (now every ``sandesh_*`` name,
  across every skill).
- KEPT unchanged: ``NoRelaunchAfterTerminalExitS1Test``'s gate and its two
  detectors; the Sandesh data-directory gate and its detector.

Stdlib only; reads the repo tree only.
"""

import re
import unittest
from pathlib import Path

from tests._helpers import read_text as _read
from tests._helpers import rel_to_repo as _rel

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC = REPO_ROOT / "skills-src"

BOOTSTRAP_SKILL = SKILLS_SRC / "bootstrap" / "SKILL.md"
SHUTDOWN_SKILL = SKILLS_SRC / "shutdown" / "SKILL.md"
REFERENCES = SKILLS_SRC / "model-b" / "references"
SANDESH_REF = REFERENCES / "sandesh.md"
COMMON_REF = REFERENCES / "orchestration-common.md"
MAINLINE_REF = REFERENCES / "orchestration-mainline.md"
TRACK_REF = REFERENCES / "orchestration-track.md"

#: §S3 — the six files that state the wake rules.
WAKE_RULE_FILES = (BOOTSTRAP_SKILL, SHUTDOWN_SKILL, SANDESH_REF, COMMON_REF, MAINLINE_REF, TRACK_REF)

#: §D18 — one harness's own tool names, banned from the wake-rule files.
FORBIDDEN_TOOL_TOKENS = ("run_in_background", "TaskStop")
#: §D18 / §S3 — every Sandesh tool name (``sandesh_send``, ``sandesh_watcher``, the
#: extension's ``sandesh_notify_start``…): sandesh-pi's tools share them with Sandesh's MCP
#: server, so no skill names one. Case-sensitive: ``SANDESH_PROJECT`` is a registry key.
SANDESH_TOOL_RE = re.compile(r"(?<![A-Za-z0-9])sandesh_[a-z][a-z0-9_]*")

#: Section headings (``## …`` substrings) a test locates its text by.
BOOTSTRAP_STEP1_HEADING = "Step 1"
GUARDRAILS_HEADING = "Guardrails"
SHUTDOWN_FINAL_HEADING = "final step"

# ------------------------------------------------------------------ phrases ----

#: §S3 — the wake named as a capability.
CAPABILITY_RE = re.compile(r"sandesh's wake watcher", re.IGNORECASE)
EXTENSION_RE = re.compile(r"harness's sandesh extension", re.IGNORECASE)
#: §S3 — the CLI fetch form (the quote style is free; ``<address>`` or ``<your address>``).
CLI_FETCH_RE = re.compile(r"sandesh fetch --project <Project> --to ['\"]<(?:your )?address>['\"]")
#: §S3 — the one liveness read, verbatim from the spec.
TOON_ADDRESSBOOK = "sandesh addressbook --project <Project> --format toon --fields address,status,listening"
#: Sandesh's own command for the watcher, stopping one address.
SANDESH_WATCHER_STOP_RE = re.compile(r"/sandesh-watcher stop <(?:your )?address>")
#: The CLI unregister form shutdown ends with.
CLI_UNREGISTER_RE = re.compile(r"sandesh unregister --project <Project>")
#: The CLI register form bootstrap uses when the address is absent or inactive.
CLI_REGISTER_RE = re.compile(r"sandesh register --project <Project> --address")
#: The three ordered bootstrap stages: register, start the watcher, confirm.
REGISTER_STEP = (CLI_REGISTER_RE,)
START_STEP = (CAPABILITY_RE, re.compile(r"\bstart", re.IGNORECASE))
CONFIRM_STEP = (TOON_ADDRESSBOOK,)

RELAUNCH_RE = re.compile(r"\brelaunch", re.IGNORECASE)
#: A relaunch under a negation in the same clause ("never relaunches anything").
NEGATED_RELAUNCH_RE = re.compile(
    r"\b(?:do not|don't|never|not|no)\b[^|.;,]{0,30}\brelaunch\w*", re.IGNORECASE
)
#: Relaunching the SESSION (Pi, with the Track's ``env SANDESH_ADDRESS=…`` override) is
#: bootstrap's remediation, not a wake relaunch.
SESSION_RELAUNCH_RE = re.compile(
    r"\brelaunch\w*\s+(?:pi\b|the session|your session|the track|this session|with\b)", re.IGNORECASE
)
#: A sentence about the wake.
WAKE_CONTEXT_RE = re.compile(
    r"watcher|notifier|\bnotify\b|\bwak(?:e|es|ing|en|ened)\b|\bmail\b|\bfetch", re.IGNORECASE
)

#: §S3 Removed — the phrases no skill may carry.
REMOVED_PHRASES = {
    "the Model B watcher": re.compile(r"model[- ]?b(?:'s)? watcher", re.IGNORECASE),
    "Model B's /watcher command": re.compile(r"/watcher\b"),
    "the relaunch-on-exit rule": re.compile(r"relaunch-on-exit", re.IGNORECASE),
    "pkill": re.compile(r"\bpkill\b"),
    "the human addressbook table (● live)": re.compile("\u25cf live"),
}
#: §S3 Removed — a runnable ``sandesh notify`` form (``--help`` is a citation, not a launch).
NOTIFY_FORM_RE = re.compile(r"sandesh notify --(?!help\b)[a-z]")
BACKGROUND_RE = re.compile(r"\bbackground\b", re.IGNORECASE)

#: §S3 — "says so" for the identity warning.
SAYS_SO_RE = re.compile(r"\bsay(?:s)? so\b|\bwarn|\bstate(?:s)?\b|\breport(?:s)?\b|\btell(?:s)?\b", re.IGNORECASE)
CARRY_ON_RE = re.compile(
    r"\bcarr(?:y|ies) on\b|\b(?:does not|do not|doesn't|never) stops?\b|\bcontinues?\b", re.IGNORECASE
)
EXPLICIT_RE = re.compile(r"\bexplicit(?:ly)?\b", re.IGNORECASE)

# ---------------------------------------------- CR-MDB-026 gates still in force ----

#: The reasons after which a relaunch is forbidden.
TERMINAL_REASON_RE = re.compile(r"tombston|evict|already[- ]live", re.IGNORECASE)
#: Prose that reads an exit as mail without naming which exit.
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
#: Direct paths into Sandesh's own data directory.
SANDESH_DATA_DIR_RE = re.compile(
    r"(?:~|\$HOME|\$\{?XDG_DATA_HOME\}?|\.local/share)/sandesh\b"
    r"|sandesh[\w./-]*\.(?:db|sqlite3?)\b",
    re.IGNORECASE,
)

FENCE_RE = re.compile(r"^\s*(```|~~~)")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


# ------------------------------------------------------------------ helpers ----

def _flat(text: str) -> str:
    """Backticks and ``*`` emphasis dropped, curly quotes straightened, whitespace
    collapsed — so a phrase matches however the line is wrapped or marked up."""
    text = text.replace("`", "").replace("*", "")
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r"\s+", " ", text).strip()


def _blocks(text: str) -> list:
    """``[(first_line, flat_text)]`` — one entry per list item (its continuation lines
    and any fenced lines inside it included, its marker dropped), per prose paragraph,
    and per table row. Headings and blank lines end a block; a nested list item starts
    its own."""
    blocks, current, first, fenced = [], [], 0, False
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if FENCE_RE.match(line):
            fenced = not fenced
            continue
        if fenced:
            if line:
                if not current:
                    first = lineno
                current.append(line)
            continue
        boundary = (not line or line.startswith(("#", "|"))
                    or LIST_ITEM_RE.match(raw) is not None)
        if boundary and current:
            blocks.append((first, _flat(" ".join(current))))
            current = []
        if not line or line.startswith("#"):
            continue
        if line.startswith("|"):
            blocks.append((lineno, _flat(line)))
            continue
        if not current:
            first = lineno
            line = LIST_ITEM_RE.sub("", line, count=1)
        current.append(line)
    if current:
        blocks.append((first, _flat(" ".join(current))))
    return blocks


def _matching_blocks(text: str, *patterns) -> list:
    """The flat blocks of ``text`` in which EVERY pattern (a compiled regex or a plain
    substring) matches."""
    hits = []
    for _, block in _blocks(text):
        if all((p.search(block) if hasattr(p, "search") else p in block) for p in patterns):
            hits.append(block)
    return hits


def _blocks_in_order(text: str, *groups) -> list:
    """Indices (in :func:`_blocks` order) of a first block matching every pattern of
    ``groups[0]``, then the first LATER block matching ``groups[1]``, and so on \u2014 the
    list stops short at the first group with no such later block."""
    found, after = [], -1
    blocks = _blocks(text)
    for group in groups:
        for index in range(after + 1, len(blocks)):
            block = blocks[index][1]
            if all((p.search(block) if hasattr(p, "search") else p in block) for p in group):
                found.append(index)
                after = index
                break
        else:
            break
    return found


def _section(test: unittest.TestCase, path: Path, heading: str) -> str:
    """The text under the ``## `` heading containing ``heading`` (case-insensitive), up
    to the next ``## `` heading. A missing heading FAILS (never errors)."""
    lines = _read(path).splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.startswith("## ") and heading.lower() in line.lower():
            start = idx
            break
    if start is None:
        test.fail(f"{path.relative_to(REPO_ROOT)} has no '## …{heading}…' heading")
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if lines[idx].startswith("## "):
            end = idx
            break
    return "\n".join(lines[start:end])


def _units(text: str):
    """Split markdown into judgeable units: each table row, and each sentence of each
    prose block (a block ends at a blank line, heading, list item or table row). Yields
    ``(line_number, unit_text)``."""
    blocks = []
    current, current_line = [], None
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        starts_block = (
            not line
            or line.startswith(("#", "|"))
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


def _wake_relaunch_claims(text: str) -> list:
    """Units that relaunch something in a wake context — not under a negation, and not
    the session relaunch bootstrap names as a remediation (§S3 Removed)."""
    hits = []
    for lineno, unit in _units(text):
        residue = SESSION_RELAUNCH_RE.sub(" ", NEGATED_RELAUNCH_RE.sub(" ", unit))
        if RELAUNCH_RE.search(residue) and WAKE_CONTEXT_RE.search(unit):
            hits.append((lineno, unit))
    return hits


def _removed_phrase_hits(text: str) -> list:
    """``[(line, label)]`` for every §S3-removed phrase, per line."""
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for label, pattern in REMOVED_PHRASES.items():
            if pattern.search(line):
                hits.append((lineno, label))
    return hits


def _notify_launch_hits(text: str) -> list:
    """Units that launch ``sandesh notify`` — a runnable form (any flag but ``--help``),
    or the command named as a background process (§S3 Removed)."""
    hits = []
    for lineno, unit in _units(text):
        flat = _flat(unit)
        if NOTIFY_FORM_RE.search(flat) or ("sandesh notify" in flat and BACKGROUND_RE.search(flat)):
            hits.append((lineno, unit))
    return hits


def _harness_tool_hits(text: str, extra_tokens=()) -> list:
    """``[(line, token)]`` for every Sandesh tool name and every ``extra_tokens`` token."""
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in SANDESH_TOOL_RE.finditer(line):
            hits.append((lineno, match.group(0)))
        for token in extra_tokens:
            if token in line:
                hits.append((lineno, token))
    return hits


def _addressbook_forms(text: str) -> list:
    """Every flagged ``sandesh addressbook --…`` form written as code — an inline span (it
    may wrap a line) or a fenced line — from the verb to the end of the span, whitespace
    collapsed. A bare ``sandesh addressbook`` names the verb and is no form."""
    code, fenced = list(re.findall(r"`([^`]+)`", text)), False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            fenced = not fenced
        elif fenced:
            code.append(line)
    forms = []
    for snippet in code:
        snippet = re.sub(r"\s+", " ", snippet).strip()
        match = re.search(r"sandesh addressbook --.*", snippet)
        if match:
            forms.append(match.group(0))
    return forms


def _relaunch_after_terminal_claims(text: str):
    """Units naming tombstoned / evicted / already live that relaunch without any
    negated relaunch."""
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
    """Units that act on an exit whose code/reason they never name."""
    hits = []
    for lineno, unit in _units(text):
        if (
            UNQUALIFIED_EXIT_RE.search(unit)
            and re.search(r"fetch|relaunch|mail", unit, re.IGNORECASE)
            and not EXIT_QUALIFIER_RE.search(unit)
        ):
            hits.append((lineno, unit))
    return hits


def _names_exit(block: str, code: str) -> bool:
    """``block`` names exit ``code``: a table row with a cell that is exactly the code,
    or prose such as "exit 1", "exits 3 and 4", "exit code 4", "(3)"."""
    if block.startswith("|"):
        return any(c.strip() == code for c in block.strip("|").split("|"))
    return re.search(
        rf"\bexit\w*\s+(?:code\s+)?(?:\d+\s*(?:,|or|and|/)\s*)*{code}\b|\({code}\)", block, re.IGNORECASE
    ) is not None


def _skill_markdown_files():
    return sorted(p for p in SKILLS_SRC.rglob("*.md") if p.is_file())


def _stops_before_unregistering(block: str) -> bool:
    """``block`` says "stop" before it says "unregister"."""
    stop = re.search(r"\bstop", block, re.IGNORECASE)
    unregister = re.search(r"\bunregister", block, re.IGNORECASE)
    return bool(stop and unregister and stop.start() < unregister.start())


# ---------------------------------------------------------------------------
# Bootstrap Step 1
# ---------------------------------------------------------------------------

class BootstrapStep1IdentityTest(unittest.TestCase):
    """§S3 Bootstrap Step 1 — the role's address, and the warning when the environment
    disagrees (unset or another ``$SANDESH_ADDRESS``), which never stops bootstrap."""

    def setUp(self):
        self.step1 = _section(self, BOOTSTRAP_SKILL, BOOTSTRAP_STEP1_HEADING)

    def test_role_address_is_mainline_or_track_n_of_sandesh_project(self):
        hits = _matching_blocks(
            self.step1, "Mainline - <Project>", re.compile(r"Track <?N>? - <Project>"), "SANDESH_PROJECT",
        )
        self.assertTrue(
            hits,
            "Step 1 must state, in one bullet or paragraph, that the role's address is "
            "`Mainline - <Project>` or `Track <N> - <Project>` with <Project> = SANDESH_PROJECT",
        )

    def test_unset_or_mismatched_sandesh_address_is_stated(self):
        hits = _matching_blocks(
            self.step1, "$SANDESH_ADDRESS", re.compile(r"\bunset\b", re.IGNORECASE),
            re.compile(r"\banother\b|\bdifferent\b|\bother\b|mismatch|disagree", re.IGNORECASE), SAYS_SO_RE,
        )
        self.assertTrue(
            hits,
            "Step 1 must say so when `$SANDESH_ADDRESS` is unset or names another address",
        )

    def test_track_without_its_override_is_explained_by_direnv_exporting_the_mainline_address(self):
        hits = _matching_blocks(
            self.step1, re.compile(r"\btrack\b", re.IGNORECASE), re.compile(r"\bwithout\b", re.IGNORECASE),
            "env SANDESH_ADDRESS=", "direnv", re.compile(r"\bmainline\b", re.IGNORECASE),
        )
        self.assertTrue(
            hits,
            "Step 1 must explain a mismatch: a Track launched without its `env SANDESH_ADDRESS=…` "
            "override, while direnv exports the Mainline address",
        )

    def test_mismatch_remediation_is_load_direnv_or_relaunch_with_the_override(self):
        hits = _matching_blocks(
            self.step1, "direnv",
            re.compile(r"\b(?:re)?launch\w*\b[^.]{0,40}(?:override|env SANDESH_ADDRESS=)", re.IGNORECASE),
        )
        self.assertTrue(hits, "Step 1 must give the remediation: load direnv, or relaunch with the override")

    def test_bootstrap_carries_on_with_the_address_passed_explicitly(self):
        hits = _matching_blocks(
            self.step1, CARRY_ON_RE, EXPLICIT_RE, re.compile(r"\baddress\b", re.IGNORECASE),
        )
        self.assertTrue(
            hits,
            "Step 1 must not stop on the warning: it carries on with the role's address passed explicitly",
        )


class BootstrapStep1WakeTest(unittest.TestCase):
    """§S3 Bootstrap Step 1 — register if absent or inactive, start Sandesh's wake watcher
    for the address and project passed explicitly, confirm from the toon addressbook; a
    missing extension; a woken session only fetches. Guardrails keep exactly one watcher
    per address and no machine-wide kill."""

    def setUp(self):
        self.step1 = _section(self, BOOTSTRAP_SKILL, BOOTSTRAP_STEP1_HEADING)

    def test_registers_with_the_cli_when_absent_or_inactive(self):
        hits = _matching_blocks(
            self.step1, CLI_REGISTER_RE, re.compile(r"\babsent\b", re.IGNORECASE),
            re.compile(r"inactive|active:\s*false|not active", re.IGNORECASE),
        )
        self.assertTrue(hits, "Step 1 registers with the CLI when the address is absent or inactive")

    def test_starts_sandeshs_wake_watcher_through_the_extension_with_address_and_project_explicit(self):
        hits = _matching_blocks(
            self.step1, CAPABILITY_RE, EXTENSION_RE, re.compile(r"\bstart", re.IGNORECASE), EXPLICIT_RE,
            re.compile(r"\baddress\b", re.IGNORECASE), re.compile(r"\bproject\b", re.IGNORECASE),
        )
        self.assertTrue(
            hits,
            "Step 1 must START Sandesh's wake watcher, started through the harness's Sandesh "
            "extension, for the address and project passed explicitly — in one bullet or paragraph",
        )

    def test_confirms_active_and_listening_from_the_toon_addressbook(self):
        hits = _matching_blocks(
            self.step1, TOON_ADDRESSBOOK, re.compile(r"\bactive\b"), re.compile(r"\blistening\b"),
        )
        self.assertTrue(
            hits,
            f"Step 1 must confirm with `{TOON_ADDRESSBOOK}`: the address `active` and listening",
        )

    def test_registers_then_starts_then_confirms_in_that_order(self):
        found = _blocks_in_order(self.step1, REGISTER_STEP, START_STEP, CONFIRM_STEP)
        stages = ("a `sandesh register --project <Project> --address`",
                  "a later start of Sandesh's wake watcher",
                  f"a later confirmation with `{TOON_ADDRESSBOOK}`")
        self.assertEqual(len(found), 3, f"Step 1 must register, THEN start, THEN confirm; missing: "
                                        f"{stages[len(found)] if len(found) < 3 else ''}")

    def test_missing_extension_leaves_no_wake_names_the_remediation_and_carries_on(self):
        hits = _matching_blocks(
            self.step1, re.compile(r"\bextension\b", re.IGNORECASE),
            re.compile(r"missing|not installed|isn't installed|absent|not loaded", re.IGNORECASE),
            re.compile(r"wake[^.]{0,40}unavailable|unavailable[^.]{0,40}wake|without a wake", re.IGNORECASE),
            "sandesh-pi", CARRY_ON_RE,
        )
        self.assertTrue(
            hits,
            "Step 1 must handle a missing extension: say the wake is unavailable, name the "
            "remediation (sandesh-pi) and carry on without a wake",
        )

    def test_a_woken_session_only_fetches_with_the_cli_form(self):
        hits = _matching_blocks(
            self.step1, CLI_FETCH_RE,
            re.compile(r"\bonly fetch|\bfetch(?:es)? only\b|\bnever relaunch", re.IGNORECASE),
        )
        self.assertTrue(
            hits,
            "after a wake the session only fetches — `sandesh fetch --project <Project> --to "
            "'<your address>'` — and never relaunches anything",
        )

    def test_guardrails_keep_exactly_one_per_address_and_no_machine_wide_kill(self):
        guardrails = _flat(_section(self, BOOTSTRAP_SKILL, GUARDRAILS_HEADING))
        self.assertRegex(guardrails, re.compile(r"exactly one\b[^.]{0,30}per address", re.IGNORECASE))
        self.assertRegex(guardrails, re.compile(r"never machine-wide", re.IGNORECASE),
                         "the machine-wide-kill guardrail stays")
        self.assertRegex(guardrails, CAPABILITY_RE, "the Guardrails name the wake as Sandesh's wake watcher")


# ---------------------------------------------------------------------------
# After a wake — sandesh.md (the wake section and the exit table)
# ---------------------------------------------------------------------------

class SandeshReferenceWakeTest(unittest.TestCase):
    """§S3 After a wake + ``sandesh.md`` agrees: the wake section, the exit table as
    sandesh-pi's supervision surfaces it, Mainline's own watcher."""

    def setUp(self):
        self.text = _read(SANDESH_REF)

    def test_wake_section_names_the_capability_started_through_the_extension(self):
        self.assertTrue(
            _matching_blocks(self.text, CAPABILITY_RE, EXTENSION_RE),
            "sandesh.md must name the wake as Sandesh's wake watcher, started through the "
            "harness's Sandesh extension, in one bullet or paragraph",
        )

    def test_bootstrap_registers_then_starts_then_confirms_from_the_toon_addressbook(self):
        self.assertTrue(
            _matching_blocks(self.text, TOON_ADDRESSBOOK, re.compile(r"\blistening\b")),
            f"sandesh.md must confirm with `{TOON_ADDRESSBOOK}`",
        )
        found = _blocks_in_order(self.text, REGISTER_STEP, START_STEP, CONFIRM_STEP)
        self.assertEqual(len(found), 3, "sandesh.md must register, THEN start Sandesh's wake watcher, "
                                        f"THEN confirm with the toon addressbook; stages found: {len(found)}")

    def test_a_woken_session_only_fetches_the_named_ids(self):
        self.assertTrue(
            _matching_blocks(
                self.text, CLI_FETCH_RE,
                re.compile(r"\bonly fetch|\bfetch(?:es)? only\b|\bnever relaunch", re.IGNORECASE),
            ),
            "sandesh.md: after a wake, fetch only (CLI form), never relaunch",
        )

    def test_on_a_stop_notice_liveness_is_rechecked(self):
        self.assertTrue(
            _matching_blocks(
                self.text, re.compile(r"stop notice", re.IGNORECASE),
                re.compile(r"re-?check|check", re.IGNORECASE),
                re.compile(r"liveness|listening|addressbook", re.IGNORECASE),
            ),
            "sandesh.md: on a stop notice the orchestrator re-checks its liveness",
        )

    def test_exit_1_starts_the_watcher_again_once(self):
        hits = [b for _, b in _blocks(self.text)
                if _names_exit(b, "1") and re.search(r"\bagain\b|\brestart", b, re.IGNORECASE)
                and re.search(r"\bonce\b", b, re.IGNORECASE)]
        self.assertTrue(hits, "sandesh.md: exit 1 → start the watcher again, once")

    def test_a_signal_starts_the_watcher_again_once(self):
        hits = _matching_blocks(
            self.text, re.compile(r"\bsignal\b", re.IGNORECASE),
            re.compile(r"\bagain\b|\brestart", re.IGNORECASE), re.compile(r"\bonce\b", re.IGNORECASE),
        )
        self.assertTrue(hits, "sandesh.md: a signal → start the watcher again, once")

    def test_exit_3_tombstoned_is_reported(self):
        hits = [b for _, b in _blocks(self.text)
                if _names_exit(b, "3") and re.search(r"tombston", b, re.IGNORECASE)
                and re.search(r"\breport", b, re.IGNORECASE)]
        self.assertTrue(hits, "sandesh.md: exit 3 (tombstoned) is reported")

    def test_exit_4_evicted_is_reported(self):
        hits = [b for _, b in _blocks(self.text)
                if _names_exit(b, "4") and re.search(r"evict", b, re.IGNORECASE)
                and re.search(r"\breport", b, re.IGNORECASE)]
        self.assertTrue(hits, "sandesh.md: exit 4 (evicted) is reported")

    def test_reports_route_mainline_to_the_user_and_a_track_to_mainline(self):
        hits = _matching_blocks(
            self.text, re.compile(r"\breport", re.IGNORECASE),
            re.compile(r"mainline[^.|]{0,40}\buser\b", re.IGNORECASE),
            re.compile(r"track[^.|]{0,40}\bmainline\b", re.IGNORECASE),
        )
        self.assertTrue(hits, "sandesh.md: a tombstone or eviction is reported — Mainline to the user, a Track to Mainline")

    def test_mainlines_own_watcher_is_sandeshs_wake_watcher_and_it_fetches_and_replies(self):
        hits = _matching_blocks(
            self.text, re.compile(r"\bmainline\b", re.IGNORECASE), CAPABILITY_RE,
            re.compile(r"\bfetch", re.IGNORECASE), re.compile(r"\brepl", re.IGNORECASE),
        )
        self.assertTrue(hits, "sandesh.md: Mainline's own watcher is Sandesh's wake watcher; it fetches and replies")


# ---------------------------------------------------------------------------
# Shutdown's final step
# ---------------------------------------------------------------------------

class ShutdownFinalStepTest(unittest.TestCase):
    """§S3 — shutdown's final step stops its own watcher by address, then unregisters it
    with the CLI; the stop is the step's documented exception."""

    def setUp(self):
        self.final = _section(self, SHUTDOWN_SKILL, SHUTDOWN_FINAL_HEADING)
        self.flat = _flat(self.final)

    def test_final_step_stops_sandeshs_wake_watcher_by_address(self):
        self.assertRegex(self.flat, CAPABILITY_RE, "the final step names Sandesh's wake watcher")
        self.assertRegex(self.flat, re.compile(r"sandesh's extension|harness's sandesh extension", re.IGNORECASE),
                         "it stops through Sandesh's extension")
        self.assertRegex(self.flat, SANDESH_WATCHER_STOP_RE,
                         "or `/sandesh-watcher stop <your address>` — by address")

    def test_final_step_stops_then_unregisters(self):
        stop = SANDESH_WATCHER_STOP_RE.search(self.flat)
        unregister = CLI_UNREGISTER_RE.search(self.flat)
        self.assertIsNotNone(stop, "the final step names no `/sandesh-watcher stop <your address>`")
        self.assertIsNotNone(unregister, "the final step names no `sandesh unregister --project <Project>`")
        assert stop is not None and unregister is not None
        self.assertLess(stop.start(), unregister.start(), "stop the watcher FIRST, then unregister")

    def test_the_stop_is_the_steps_documented_exception(self):
        self.assertRegex(self.flat, re.compile(r"documented exception", re.IGNORECASE))

    def test_the_watcher_is_stopped_only_when_everything_else_is_done(self):
        self.assertRegex(self.flat, re.compile(r"only when everything else[^.]{0,80}\bdone\b", re.IGNORECASE),
                         "the stop stays LAST: only once everything else is done")

    def test_the_watcher_command_never_stops_without_an_address(self):
        whole = _read(SHUTDOWN_SKILL)
        bare = [line.strip() for line in whole.splitlines()
                if re.search(r"/sandesh-watcher stop(?! <)", line)
                and not re.search(r"\b(?:never|not|no)\b", line, re.IGNORECASE)]
        self.assertEqual(bare, [], "a `/sandesh-watcher stop` without an address stops another identity's watcher")

    def test_final_step_names_no_harness_stop_tool(self):
        for token in ("TaskStop", "run_in_background"):
            self.assertNotIn(token, self.final, f"the final step names the capability, not {token}")
        self.assertEqual(SANDESH_TOOL_RE.findall(self.final), [], "and no Sandesh tool name")


# ---------------------------------------------------------------------------
# The orchestration files agree
# ---------------------------------------------------------------------------

class OrchestrationFilesAgreeTest(unittest.TestCase):
    """§S3 — ``orchestration-common`` (the bracket and the notifier-kill override),
    ``orchestration-mainline`` (the inbox watcher) and ``orchestration-track`` (shutdown)
    agree with bootstrap and shutdown."""

    def test_common_bracket_starts_sandeshs_wake_watcher_at_bootstrap(self):
        hits = _matching_blocks(_read(COMMON_REF), "/bootstrap <role>", CAPABILITY_RE,
                                re.compile(r"\bregister", re.IGNORECASE))
        self.assertTrue(hits, "common's bracket: `/bootstrap <role>` registers and starts Sandesh's wake watcher")

    def test_common_bracket_stops_then_unregisters_at_shutdown(self):
        hits = _matching_blocks(_read(COMMON_REF), "/shutdown", re.compile(r"\bstop", re.IGNORECASE),
                                re.compile(r"\bunregister", re.IGNORECASE))
        self.assertTrue(hits, "common's bracket: `/shutdown` stops the watcher, then unregisters")
        for block in hits:
            stop = re.search(r"\bstop\w*[^.;]{0,40}\bwatcher|\bwatcher[^.;]{0,40}\bstop", block, re.IGNORECASE)
            unregister = re.search(r"\bunregister", block, re.IGNORECASE)
            if stop and unregister and stop.start() < unregister.start():
                return
        self.fail(f"common's bracket must stop the watcher BEFORE it unregisters: {hits}")

    def test_common_override_is_the_shutdown_stop_as_the_single_exception(self):
        hits = _matching_blocks(
            _read(COMMON_REF), re.compile(r"\bshutdown\b", re.IGNORECASE), re.compile(r"\bstop", re.IGNORECASE),
            re.compile(r"\bwatcher\b", re.IGNORECASE), re.compile(r"exception|override", re.IGNORECASE),
            re.compile(r"\baddress\b", re.IGNORECASE),
        )
        self.assertTrue(
            hits,
            "common's override: stopping the watcher by address at shutdown is the single exception",
        )

    def test_mainline_inbox_watcher_is_sandeshs_wake_watcher_and_keeps_fetch_and_reply(self):
        hits = _matching_blocks(
            _read(MAINLINE_REF), CAPABILITY_RE, re.compile(r"\bfetch", re.IGNORECASE),
            re.compile(r"\breply|\bdirective", re.IGNORECASE),
        )
        self.assertTrue(hits, "mainline's inbox watcher is Sandesh's wake watcher; a request is fetched and answered")

    def test_track_shutdown_acks_then_stops_its_watcher_by_address_then_unregisters(self):
        hits = _matching_blocks(
            _read(TRACK_REF), re.compile(r"\back\b", re.IGNORECASE), re.compile(r"\bstop", re.IGNORECASE),
            re.compile(r"\bwatcher\b", re.IGNORECASE), re.compile(r"\baddress\b", re.IGNORECASE),
            re.compile(r"\bunregister", re.IGNORECASE),
        )
        self.assertTrue(hits, "orchestration-track's shutdown: ack, then stop the watcher by address, then unregister")
        ordered = [b for b in hits if _stops_before_unregistering(b)]
        self.assertTrue(ordered, f"orchestration-track: stop BEFORE unregister: {hits}")


# ---------------------------------------------------------------------------
# Liveness is read from machine output, never the human table
# ---------------------------------------------------------------------------

class LivenessFromToonTest(unittest.TestCase):
    """§S3 — every addressbook read in the wake-rule files is the toon form; Tracks' and
    Mainline's liveness is read the same way."""

    def test_every_addressbook_form_is_the_toon_field_read(self):
        offending = []
        for path in WAKE_RULE_FILES:
            for form in _addressbook_forms(_read(path)):
                if not form.startswith(TOON_ADDRESSBOOK):
                    offending.append(f"{_rel(path)}: {form}")
        self.assertEqual(offending, [], "addressbook read without the toon fields:\n  " + "\n  ".join(offending))

    def test_bootstrap_reads_the_other_roles_liveness_from_the_toon_addressbook(self):
        text = _read(BOOTSTRAP_SKILL)
        tracks = _matching_blocks(text, TOON_ADDRESSBOOK, re.compile(r"\btracks?\b", re.IGNORECASE))
        mainline = _matching_blocks(text, TOON_ADDRESSBOOK, "Mainline - <Project>")
        self.assertTrue(tracks, "Mainline reads the Tracks' liveness from the toon addressbook")
        self.assertTrue(mainline, "a Track reads Mainline's liveness from the toon addressbook")

    def test_addressbook_form_detector_bites(self):
        text = ("Check `sandesh addressbook --project <Project>` first.\n\n"
                f"Confirm with `{TOON_ADDRESSBOOK}`: active and listening.\n\n"
                "The `sandesh addressbook` verb lists the roster.\n")
        forms = _addressbook_forms(text)
        self.assertEqual(forms, ["sandesh addressbook --project <Project>", TOON_ADDRESSBOOK], forms)


# ---------------------------------------------------------------------------
# Removed everywhere under skills-src/
# ---------------------------------------------------------------------------

class WakeIsNeverRelaunchedTest(unittest.TestCase):
    """§S3 Removed — no skill relaunches anything for the wake; the session relaunch
    with the Track's override is a remediation, not a wake relaunch."""

    def test_no_skill_relaunches_for_the_wake(self):
        offending = []
        for path in _skill_markdown_files():
            for lineno, unit in _wake_relaunch_claims(_read(path)):
                offending.append(f"{_rel(path)}:{lineno}: {unit}")
        self.assertEqual(offending, [], "skills relaunch for the wake:\n  " + "\n  ".join(offending))

    def test_wake_relaunch_detector_bites(self):
        for violating in (
            "Relaunch the Mainline inbox watcher after any fetch.",
            "Next run, `/bootstrap` brings you back (re-register + relaunch the watcher).",
            "registered but its watcher is down — NOT reachable for a wake until it relaunches",
            "| mail arrived | `0` | fetch, then relaunch |",
            "Sandesh's wake watcher relaunches itself after every wake.",
        ):
            self.assertEqual(len(_wake_relaunch_claims(violating)), 1, violating)
        for permitted in (
            "After a wake, fetch the named ids and never relaunch anything.",
            "Load direnv, or relaunch Pi with `env SANDESH_ADDRESS=\"Track 2 - Foo\" pi`, before the watcher starts.",
            "The remediation: load direnv, or relaunch with the override; then start the watcher.",
            "Start the watcher again once for exit 1 or a signal.",
            "Relaunch the build after a fix.",
        ):
            self.assertEqual(_wake_relaunch_claims(permitted), [], permitted)


class RemovedPhrasesTest(unittest.TestCase):
    """§S3 Removed — the Model B watcher, ``/watcher``, the relaunch-on-exit rule,
    ``pkill``, the human table, and the plain background ``sandesh notify`` launch."""

    def test_no_skill_carries_a_removed_phrase(self):
        offending = []
        for path in _skill_markdown_files():
            for lineno, label in _removed_phrase_hits(_read(path)):
                offending.append(f"{_rel(path)}:{lineno}: {label}")
        self.assertEqual(offending, [], "removed wake phrases remain:\n  " + "\n  ".join(offending))

    def test_removed_phrase_detector_bites_and_spares_sandeshs_own_command(self):
        synthetic = (
            "Start it with the **Model B watcher**.\n"
            "`/watcher status` lists the watchers.\n"
            "the relaunch-on-exit prime directive\n"
            "`pkill -f \"sandesh notify --to x\"`\n"
            "LISTENING shows \u25cf live while a watcher holds it\n"
            "Stop it with `/sandesh-watcher stop <your address>`, through Sandesh's extension.\n"
        )
        self.assertEqual(
            _removed_phrase_hits(synthetic),
            [(1, "the Model B watcher"), (2, "Model B's /watcher command"), (3, "the relaunch-on-exit rule"),
             (4, "pkill"), (5, "the human addressbook table (● live)")],
        )

    def test_no_skill_launches_sandesh_notify(self):
        offending = []
        for path in _skill_markdown_files():
            for lineno, unit in _notify_launch_hits(_read(path)):
                offending.append(f"{_rel(path)}:{lineno}: {unit}")
        self.assertEqual(offending, [], "skills launch `sandesh notify` themselves:\n  " + "\n  ".join(offending))

    def test_notify_launch_detector_bites_and_spares_the_help_citation(self):
        for violating in (
            "Run `sandesh notify --to \"<your address>\" --project <Project>` and wait.",
            "run the notifier `sandesh notify` as a background process that notifies you when it exits",
            "a bare `sandesh notify --to …` exits 1 and silently never listens",
        ):
            self.assertEqual(len(_notify_launch_hits(violating)), 1, violating)
        for permitted in (
            "`sandesh notify --help` is Sandesh's authority for the exit reasons.",
            "Sandesh's wake watcher, started through the harness's Sandesh extension.",
        ):
            self.assertEqual(_notify_launch_hits(permitted), [], permitted)


class NoHarnessToolNameTest(unittest.TestCase):
    """§D18 — skills name capabilities and CLIs: no Sandesh tool name in any skill, and no
    harness tool name in the wake-rule files."""

    def test_no_skill_names_a_sandesh_tool(self):
        offending = []
        for path in _skill_markdown_files():
            for lineno, token in _harness_tool_hits(_read(path)):
                offending.append(f"{_rel(path)}:{lineno} names `{token}`")
        self.assertEqual(offending, [], "Sandesh tool names in the skills:\n  " + "\n  ".join(offending))

    def test_wake_rule_files_name_no_harness_tool(self):
        offending = []
        for path in WAKE_RULE_FILES:
            self.assertTrue(path.is_file(), f"{path} must exist")
            for lineno, token in _harness_tool_hits(_read(path), FORBIDDEN_TOOL_TOKENS):
                offending.append(f"{_rel(path)}:{lineno} names `{token}`")
        self.assertEqual(offending, [], "harness tool names in the wake-rule files:\n  " + "\n  ".join(offending))

    def test_harness_tool_detector_bites_and_spares_registry_keys_and_the_command(self):
        synthetic = (
            "Launch it with Bash `run_in_background`.\n"
            "Stop it with `TaskStop` on its task id.\n"
            "Or call the `sandesh_watcher` tool.\n"
            "Start it with sandesh_notify_start, then fetch via mcp__sandesh__sandesh_fetch.\n"
            "`SANDESH_PROJECT` names the project; `/sandesh-watcher stop <your address>`.\n"
        )
        self.assertEqual(
            _harness_tool_hits(synthetic, FORBIDDEN_TOOL_TOKENS),
            [(1, "run_in_background"), (2, "TaskStop"), (3, "sandesh_watcher"),
             (4, "sandesh_notify_start"), (4, "sandesh_fetch")],
        )


# ---------------------------------------------------------------------------
# CR-MDB-026 gates still in force
# ---------------------------------------------------------------------------

class NoRelaunchAfterTerminalExitS1Test(unittest.TestCase):
    """Across ``skills-src/``: no relaunch after tombstoned, evicted or already live; no
    unqualified exit read as mail (CR-MDB-026 §S1, kept)."""

    def test_s1_no_skill_relaunches_after_terminal_exit_or_reads_any_exit_as_mail(self):
        offending = []
        for path in _skill_markdown_files():
            text = _read(path)
            for lineno, unit in _relaunch_after_terminal_claims(text):
                offending.append(f"{_rel(path)}:{lineno} relaunches after a terminal exit: {unit}")
            for lineno, unit in _exit_as_mail_claims(text):
                offending.append(f"{_rel(path)}:{lineno} acts on an unqualified exit: {unit}")
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


class SandeshDataDirectoryTest(unittest.TestCase):
    """No skill reads or writes Sandesh's data directory (CR-MDB-026 §S5, kept)."""

    def test_s5_no_skill_touches_the_sandesh_data_directory(self):
        offending = []
        for path in _skill_markdown_files():
            for lineno, line in enumerate(_read(path).splitlines(), start=1):
                if SANDESH_DATA_DIR_RE.search(line):
                    offending.append(f"{_rel(path)}:{lineno}: {line.strip()}")
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


# ---------------------------------------------------------------------------
# The block splitter and exit naming, proven on synthetic text
# ---------------------------------------------------------------------------

class BlockSplitterTest(unittest.TestCase):
    """:func:`_blocks` keeps a bullet with its wrapped lines and fenced command, splits
    nested items, paragraphs and table rows; :func:`_names_exit` reads rows and prose."""

    def test_blocks_split_bullets_paragraphs_and_rows(self):
        text = (
            "## Step 1\n"
            "1. **Register** with\n"
            "   `sandesh register --project <Project> --address \"<your address>\"`\n"
            "   ```\n"
            "   # a comment, not a heading\n"
            "   ```\n"
            "   - nested item\n"
            "\n"
            "A paragraph that\nwraps.\n"
            "| `1` | start it again once |\n"
        )
        self.assertEqual(
            [b for _, b in _blocks(text)],
            ["Register with sandesh register --project <Project> --address \"<your address>\" "
             "# a comment, not a heading",
             "nested item", "A paragraph that wraps.", "| 1 | start it again once |"],
        )

    def test_names_exit_reads_rows_and_prose(self):
        self.assertTrue(_names_exit("| error | 1 | start it again once |", "1"))
        self.assertFalse(_names_exit("| error | 128+n | report |", "1"))
        self.assertTrue(_names_exit("Report exits 3 and 4.", "4"))
        self.assertTrue(_names_exit("Start it again once for exit 1 or a signal.", "1"))
        self.assertTrue(_names_exit("a tombstone (3) is reported", "3"))
        self.assertFalse(_names_exit("Track 1 - Foo is live.", "1"))

    def test_blocks_in_order_needs_each_stage_after_the_previous(self):
        register = "`sandesh register --project <Project> --address \"x\"`"
        start = "Start Sandesh's wake watcher for the address."
        confirm = f"Confirm with `{TOON_ADDRESSBOOK}`."
        stages = (REGISTER_STEP, START_STEP, CONFIRM_STEP)
        self.assertEqual(_blocks_in_order("\n\n".join((register, start, confirm)), *stages), [0, 1, 2])
        self.assertEqual(_blocks_in_order("\n\n".join((start, register, confirm)), *stages), [1])
        self.assertEqual(_blocks_in_order("\n\n".join((confirm, register, start)), *stages), [1, 2])


if __name__ == "__main__":
    unittest.main()
