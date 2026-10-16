"""Every AXI envelope is read whole — the rule in every place, and its guard (CR-MDB-072 §S1–§S3).

Contract: ``docs/changes/CR-MDB-072-axi-envelopes-read-whole.md`` (design reference PRD D5 and its
2026-10-16 ruling on the guard; Crucible #1451). An AXI command prints one envelope on stdout; its
``warnings[]``, ``help[]`` and ``error`` carry what the caller needs next, so the envelope is read
whole — never grepped, headed, tailed, filtered, narrowed with ``jq``, redirected away or
summarised by pattern. §S1's AXI commands are a closed list: the Crucible clients
(``<stack>-crucible.py``, ``<client>``), ``sandesh``, ``modelb-axi``, ``worktree-flow.py``,
``gh-axi``, ``chrome-devtools-axi`` and ``lavish-axi``.

Class map:

- ``AxiEnvelopeDetectorTest`` — §S3 AC "the detector both ways": every finding and every
  non-finding the AC lists, on synthetic text.
- ``AxiEnvelopeGuardedTreeTest`` — §S3 AC "the guard on the real tree": no guarded file (the
  raw-runner guard's ``guarded_files``) shows an AXI call piped or redirected away.
- ``RulePlaceGateProofTest`` — §S1–§S2 AC: each place's gate proved both ways on synthetic text —
  a conforming sample passes, each pin's cut bites that pin, and a bad sample that meets every
  pin only through a shown piped AXI call fails on the §S3 finding.
- ``RuleInEachPlaceTest`` — §S2 items 1–7 on the real files, one test per place.
- ``RenderedOutputDisciplineTest`` — §S2 item 8: the rendered output-discipline lines carry the
  rule in the lean-ctx and the built-in renders, and ``.pi/agents/python-*`` is byte-identical to
  ``generator/agents/python-*``.

**What the guard reads** (§S3): each code span, and each fenced line judged alone with the lines it
continues joined — ``shown`` imported from ``tests/test_chrome_ui_relay_skill.py``, never copied.
A governing "never" spares nothing: the raw-runner guard's ``_governed`` is never applied.

**A finding:** an AXI command (a whole word, not adjacent to a letter, digit, ``_`` or ``-``; a
leading path allowed) followed later in the same span or line, before any ``&&``, ``||`` or ``;``,
by a single ``|`` (never ``||``) with a space on at least one side, or by a redirect to
``/dev/null``. A ``|`` inside a ``<…>``, ``{…}`` or ``[…]`` placeholder, or joining option values
with no space on either side, is not a pipe; a ``|`` inside a quoted argument is.

**The place gates** match on normalised text (``normalise``: backticks and ``*`` dropped,
lower-cased, whitespace collapsed), unit by unit (``units``, imported). Items 1, 2 and 5 state §S1
whole, so each pin there is a set of patterns one unit must carry, and every pin must be carried by
units of ONE section (a heading to the next heading). Items 3 and 4 carry their pins in one unit;
items 6 and 7 in the output-discipline and the debugging line. Every gate also fails on any §S3
finding in its place's text.

Hermetic: reads repository files and renders agent definitions in memory; nothing runs an AXI
command. Stdlib only.
"""

import re
import unittest

from modelb_axi import agents
from tests._helpers import REPO_ROOT, md_section, read_text, split_frontmatter
from tests.test_agent_generator import GENERATOR_AGENTS_DIR, STACKS_DIR, TEMPLATES_DIR
from tests.test_chrome_ui_relay_skill import (
    _FENCE_LINE,
    _HEADING_LINE,
    rule_findings,
    shown,
    units,
)
from tests.test_raw_runner_guard import guarded_files

# ------------------------------------------------------------------ §S3 the detector ----

#: §S1's closed list of AXI commands, each a regex for its name.
AXI_COMMAND_NAMES = (
    r"(?:<stack>|\w+)-crucible\.py",
    r"<client>",
    r"sandesh",
    r"modelb-axi",
    r"worktree-flow\.py",
    r"gh-axi",
    r"chrome-devtools-axi",
    r"lavish-axi",
)
#: §S3: an AXI command as a whole word, not adjacent to a letter, digit, ``_`` or ``-``.
AXI_COMMAND = re.compile(r"(?<![\w-])(?:" + "|".join(AXI_COMMAND_NAMES) + r")(?![\w-])")
#: §S3: a ``<…>``, ``{…}`` or ``[…]`` placeholder — a ``|`` inside one is not a pipe.
_PLACEHOLDER = re.compile(r"<[^<>]*>|\{[^{}]*\}|\[[^\[\]]*\]")
#: §S3: where the AXI command's own command ends.
_COMMAND_END = re.compile(r"&&|\|\||;")
#: §S3: a single ``|``, never part of ``||``.
_SINGLE_PIPE = re.compile(r"(?<!\|)\|(?!\|)")
#: §S3: a redirect to ``/dev/null`` — ``>``, ``>>``, ``N>``, ``&>``, with or without a space.
_DEV_NULL_REDIRECT = re.compile(r"(?:&>>?|\d*>>?)\s*/dev/null(?![\w/.-])")


def _is_pipe(rest: str, index: int) -> bool:
    """A ``|`` at ``rest[index]`` is a pipe unless it joins two values with no space either side."""
    before = rest[index - 1] if index > 0 else " "
    after = rest[index + 1] if index + 1 < len(rest) else " "
    return before.isspace() or after.isspace()


def shows_piped_axi_call(content: str) -> bool:
    """True when ``content`` (one code span or one fenced line) shows an AXI command piped or
    redirected to ``/dev/null`` (§S3)."""
    masked = _PLACEHOLDER.sub(lambda m: "x" * len(m.group()), content)
    for command in AXI_COMMAND.finditer(content):
        rest = masked[command.end():]
        end = _COMMAND_END.search(rest)
        if end:
            rest = rest[:end.start()]
        if _DEV_NULL_REDIRECT.search(rest):
            return True
        if any(_is_pipe(rest, pipe.start()) for pipe in _SINGLE_PIPE.finditer(rest)):
            return True
    return False


def axi_findings(text: str) -> list[tuple[int, str]]:
    """Every code span and fenced line of ``text`` (``shown``) showing an AXI command piped or
    redirected away, as ``(line_number, shown)``. No prohibition spares a shown form."""
    return [(number, content) for number, content, _prefix in shown(text)
            if shows_piped_axi_call(content)]


def _axi_finding_messages(text: str) -> list[str]:
    return [f"line {number} shows an AXI call piped or redirected away: `{content}`"
            for number, content in axi_findings(text)]


# ------------------------------------------------------------------ §S1–§S2 the pins ----

#: The envelope (or the output) — the subject of the rule.
ENVELOPE_OR_OUTPUT = r"\b(?:envelopes?|output)\b"
#: The client's envelope (items 6 and 7, whose line names "output discipline" already).
ENVELOPE = r"\benvelopes?\b"
#: Read whole: "read whole", "read it whole", "read every envelope whole".
READ_WHOLE = r"\bread(?: \S+){0,3} whole\b"
#: At least two of the words grep, head, tail, ``jq`` and filter.
TWO_OF_FILTERS = r"\b(grep|head|tail|jq|filter)\w*\b.*\b(?!\1)(?:grep|head|tail|jq|filter)\w*\b"
#: Redirecting away.
REDIRECTED_AWAY = r"\bredirect(?:ed|s|ing)?\b[^.;]{0,40}\baway\b"
DEV_NULL = r"/dev/null\b"
#: A long run's output goes to a file, whose envelope is read whole.
LONG_RUN = r"\blong(?:er|-running)? (?:runs?|commands?)\b"
A_FILE = r"\bfiles?\b"
#: The ``--log`` runner-log exception: not an envelope, searching it stays allowed.
LOG_FLAG = r"(?<![\w-])--log\b"
LOG_EXCEPTION = r"\bnot an envelope\b|\bsearch(?:ing|ed|es)?\b"
#: §S1's command list, each name.
COMMAND_LIST = (
    r"-crucible\.py\b|\bcrucible clients?\b",
    r"(?<![\w-])sandesh(?![\w-])",
    r"(?<![\w-])modelb-axi(?![\w-])",
    r"(?<![\w-])worktree-flow\.py\b",
    r"(?<![\w-])gh-axi(?![\w-])",
    r"(?<![\w-])chrome-devtools-axi(?![\w-])",
    r"(?<![\w-])lavish-axi(?![\w-])",
)
EVERY_AGENT = r"\borchestrators included\b|\bevery agent\b"
BY_PATTERN = r"\bsummari[sz](?:e|es|ed|ing)\b[^.;]{0,40}\bby pattern\b"
PIPED = r"\bpip(?:e|ed|es|ing)\b"
FILTERED = r"\bfilter(?:ed|s|ing)?\b"
#: The output-discipline line's summary clause: counts, failing names, assertion lines.
SUMMARY_CLAUSE = r"\bcounts\b[^.;]{0,20}\bfailing(?: \w+)? names\b[^.;]{0,20}\bassertion lines\b"
#: Searching the ``--log`` file (``rg`` in it).
SEARCH_THE_LOG = r"\b(?:rg|search(?:ing|ed|es)?)\b"

#: §S2 items 1, 2 and 5 (AC): ``(name, patterns)`` — one unit of the section carries each pin.
RULE_PINS = (
    ("the envelope or output is read whole", (ENVELOPE_OR_OUTPUT, READ_WHOLE)),
    ("two of grep, head, tail, jq and filter", (TWO_OF_FILTERS,)),
    ("redirecting away, with /dev/null", (REDIRECTED_AWAY, DEV_NULL)),
    ("a long run's output goes to a file whose envelope is read whole",
     (LONG_RUN, A_FILE, READ_WHOLE)),
    ("the --log runner-log exception", (LOG_FLAG, LOG_EXCEPTION)),
)
#: §S2 item 1, also (AC): the command list, every agent, summarising by pattern.
ORCHESTRATION_PINS = RULE_PINS + (
    ("the §S1 command list", COMMAND_LIST),
    ("orchestrators included, or every agent", (EVERY_AGENT,)),
    ("summarising by pattern", (BY_PATTERN,)),
)
#: §S2 item 1: the brief bullet naming the rule, in § "Never author code — dispatch with an
#: accurate brief".
BRIEF_SECTION = "## Never author code"
BRIEF_PIN_NAME = "every dispatch brief carries the rule"
BRIEF_PINS = (r"\bevery (?:dispatch )?brief\b", ENVELOPE)
#: §S2 items 3 and 4 (AC): one unit carries every pattern.
UNIT_PINS = (ENVELOPE_OR_OUTPUT, READ_WHOLE, PIPED, FILTERED, REDIRECTED_AWAY)
#: §S2 item 6 (AC): the output-discipline line.
OUTPUT_DISCIPLINE = r"\boutput discipline\b"
OUTPUT_DISCIPLINE_PINS = (ENVELOPE, READ_WHOLE, PIPED, FILTERED, REDIRECTED_AWAY, SUMMARY_CLAUSE)
#: §S2 item 7 (AC): ``generator/stacks/rust.toml``'s debugging line.
DEBUGGING_LINE = r"\bdebugging a failed run\b"
DEBUGGING_PINS = (ENVELOPE, READ_WHOLE, PIPED, FILTERED, REDIRECTED_AWAY, LOG_FLAG, SEARCH_THE_LOG)


def sections(text: str) -> list[str]:
    """``text``'s body (frontmatter left out) split at every heading outside a fence: each section
    is a heading and the lines up to the next heading; the lines before the first heading are a
    section too."""
    _frontmatter, body = split_frontmatter(text)
    out: list[list[str]] = [[]]
    fence = None
    for line in body.splitlines():
        opener = _FENCE_LINE.match(line)
        if fence is not None:
            if opener and opener.group(1)[0] == fence[0] and len(opener.group(1)) >= len(fence):
                fence = None
        elif opener:
            fence = opener.group(1)
        elif _HEADING_LINE.match(line):
            out.append([])
        out[-1].append(line)
    return ["\n".join(lines) for lines in out if lines]


def _carries(unit_texts: list[str], patterns: tuple[str, ...]) -> bool:
    return any(all(re.search(p, unit) for p in patterns) for unit in unit_texts)


def section_rule_findings(text: str, pins) -> list[str]:
    """``[]`` when one section of ``text`` carries every pin of ``pins`` (each pin within one of
    its units); otherwise one finding naming the pins the closest section lacks."""
    best = [name for name, _patterns in pins]
    for section in sections(text):
        section_units = units(section)
        missing = [name for name, patterns in pins if not _carries(section_units, patterns)]
        if not missing:
            return []
        if len(missing) < len(best):
            best = missing
    return [f"no section states the rule; the closest lacks {best}"]


def line_rule_findings(text: str, marker: str, patterns: tuple[str, ...]) -> list[str]:
    """``[]`` when exactly one unit of ``text`` matches ``marker`` and it carries every pattern;
    otherwise one finding."""
    lines = [unit for unit in units(text) if re.search(marker, unit)]
    if len(lines) != 1:
        return [f"expected one unit matching {marker}, found {len(lines)}"]
    missing = [p for p in patterns if not re.search(p, lines[0])]
    return [f"the {marker} line lacks {missing}"] if missing else []


def orchestration_common_findings(text: str) -> list[str]:
    """§S2 item 1: a section stating §S1 whole, the brief bullet, and no §S3 finding."""
    out = section_rule_findings(text, ORCHESTRATION_PINS)
    if not _carries(units(md_section(text, BRIEF_SECTION)), BRIEF_PINS):
        out.append(f"§ {BRIEF_SECTION[3:]!r} lacks {[BRIEF_PIN_NAME]}")
    return out + _axi_finding_messages(text)


def rule_section_findings(text: str) -> list[str]:
    """§S2 items 2 and 5: a section stating §S1 whole, and no §S3 finding."""
    return section_rule_findings(text, RULE_PINS) + _axi_finding_messages(text)


def read_whole_unit_findings(text: str) -> list[str]:
    """§S2 items 3 and 4: one unit says the envelope or output is read whole, never piped,
    filtered or redirected away; and no §S3 finding."""
    return rule_findings(text, UNIT_PINS) + _axi_finding_messages(text)


def output_discipline_findings(text: str) -> list[str]:
    """§S2 items 6 and 8: the output-discipline line carries the rule and its summary clause; and
    no §S3 finding."""
    return (line_rule_findings(text, OUTPUT_DISCIPLINE, OUTPUT_DISCIPLINE_PINS)
            + _axi_finding_messages(text))


def debugging_line_findings(text: str) -> list[str]:
    """§S2 item 7: the debugging line carries the rule, ``--log`` and searching the log; and no
    §S3 finding."""
    return line_rule_findings(text, DEBUGGING_LINE, DEBUGGING_PINS) + _axi_finding_messages(text)


# ------------------------------------------------------------------ the places ----

SKILLS = REPO_ROOT / "skills-src"
MODEL_B_REFERENCES = SKILLS / "model-b" / "references"
ORCHESTRATION_COMMON = MODEL_B_REFERENCES / "orchestration-common.md"
SUB_AGENT_PROCEDURE = MODEL_B_REFERENCES / "sub-agent-procedure.md"
SANDESH_REFERENCE = MODEL_B_REFERENCES / "sandesh.md"
MODEL_B_SKILL = SKILLS / "model-b" / "SKILL.md"
CRUCIBLE_SKILL = SKILLS / "crucible" / "SKILL.md"
ROLE_TEMPLATES = tuple(TEMPLATES_DIR / f"{role}.md.tmpl" for role in ("red", "green", "verify", "fix"))
RUST_STACK = STACKS_DIR / "rust.toml"
PI_AGENTS_DIR = REPO_ROOT / ".pi" / "agents"

# ------------------------------------------------------------------ synthetic samples ----

#: A section stating §S1 whole (items 2 and 5), worded as the spec words it.
RULE_SECTION_SAMPLE = """---
name: sample
---

# Sample

## The AXI envelope rule

- The output of an AXI command is its envelope, and every envelope is read whole, every time.
- Its output is never grepped, headed, tailed, otherwise filtered or narrowed with `jq`.
- Its output is never redirected away: stdout and stderr never go to `/dev/null`.
- A long run writes to a file, and that file is read whole.
- A runner log a client writes with `--log` is not an envelope; searching it for a failure stays
  allowed.

## Next

Something else.
"""

#: For each pin of ``RULE_PINS``, a cut that removes it from ``RULE_SECTION_SAMPLE`` alone.
RULE_SECTION_CUTS = (
    ("every envelope is read whole, every time", "every envelope matters",
     "the envelope or output is read whole"),
    ("never grepped, headed, tailed, otherwise filtered or narrowed with `jq`", "never shortened",
     "two of grep, head, tail, jq and filter"),
    ("redirected away: stdout and stderr never go to `/dev/null`", "kept",
     "redirecting away, with /dev/null"),
    ("A long run writes", "A run writes",
     "a long run's output goes to a file whose envelope is read whole"),
    ("is not an envelope; searching it for a failure stays\n  allowed", "is kept",
     "the --log runner-log exception"),
)

#: §S2 item 1: the rule's section with the command list, every agent and summarising by pattern,
#: and the brief bullet in § "Never author code — dispatch with an accurate brief".
ORCHESTRATION_SAMPLE = RULE_SECTION_SAMPLE.replace("""- A long run""", """\
- It covers the output of an AXI command: the Crucible clients (`<stack>-crucible.py`), `sandesh`,
  `modelb-axi`, `worktree-flow.py`, `gh-axi`, `chrome-devtools-axi` and `lavish-axi`. The list is
  closed.
- It binds every agent, orchestrators included.
- Its output is never summarised by pattern.
- A long run""").replace("""## Next

Something else.
""", """## Never author code — dispatch with an accurate brief

- Every dispatch brief carries the rule: every AXI envelope is read whole.
- The brief names the spec.
""")

ORCHESTRATION_CUTS = RULE_SECTION_CUTS + (
    ("`gh-axi`, ", "", "the §S1 command list"),
    ("every agent, orchestrators included", "the reader", "orchestrators included, or every agent"),
    ("summarised by pattern", "summarised loosely", "summarising by pattern"),
    ("Every dispatch brief carries the rule", "A brief is short", BRIEF_PIN_NAME),
)

#: §S2 items 3 and 4: one unit states the rule.
READ_WHOLE_UNIT_SAMPLE = """# Sample

- **Every envelope is read whole** — its output is never piped, filtered or redirected away.
- Something else.
"""

READ_WHOLE_UNIT_CUTS = (
    ("Every envelope is read whole** — its output", "Everything is read whole** — it", ENVELOPE_OR_OUTPUT),
    ("is read whole", "is read", READ_WHOLE),
    ("never piped, filtered", "never filtered", PIPED),
    ("piped, filtered or redirected", "piped or redirected", FILTERED),
    ("or redirected away", "or moved", REDIRECTED_AWAY),
)

#: §S2 item 6: an output-discipline line carrying the rule and its summary clause.
OUTPUT_DISCIPLINE_SAMPLE = """# Sample

- **Output discipline:** every run goes through the client, which prints only counts + failing
  names + assertion lines; the client's envelope is read whole and is never piped, filtered or
  redirected away.
- Something else.
"""

OUTPUT_DISCIPLINE_CUTS = (
    ("the client's envelope is read whole", "the client's summary is read whole", ENVELOPE),
    ("is read whole and", "is kept and", READ_WHOLE),
    ("never piped, filtered", "never filtered", PIPED),
    ("piped, filtered or", "piped or", FILTERED),
    ("or\n  redirected away", "or\n  moved", REDIRECTED_AWAY),
    ("counts + failing\n  names + assertion lines", "a summary", SUMMARY_CLAUSE),
)

#: §S2 item 7: the debugging line carrying the rule, ``--log`` and searching the log.
DEBUGGING_SAMPLE = """# Sample

- **Debugging a failed run:** pass `--log /tmp/<run>.log` to `test` to keep the full output, then
  `rg` the assertion out of it; the client's envelope is read whole and is never piped, filtered
  or redirected away.
- Something else.
"""

DEBUGGING_CUTS = (
    ("the client's envelope is read whole", "the client's summary is read whole", ENVELOPE),
    ("is read whole and", "is kept and", READ_WHOLE),
    ("never piped, filtered", "never filtered", PIPED),
    ("piped, filtered\n  or", "piped\n  or", FILTERED),
    ("or redirected away", "or moved", REDIRECTED_AWAY),
    ("pass `--log /tmp/<run>.log` to `test`", "run `test`", LOG_FLAG),
    ("`rg` the assertion out of it", "look at it", SEARCH_THE_LOG),
)

#: Bad samples (AC): each meets every pin of its gate ONLY through shown piped AXI calls.
RULE_SECTION_BAD = """# Sample

## Rule

```bash
sandesh status --note "the output is read whole, redirected away to /dev/null, a long run to a file is read whole, --log is not an envelope" | grep x | head
```
"""
ORCHESTRATION_BAD = """# Sample

## Rule

```bash
sandesh status --note "the output is read whole, redirected away to /dev/null, a long run to a file is read whole, --log is not an envelope, every agent, never summarised by pattern, <stack>-crucible.py modelb-axi worktree-flow.py gh-axi chrome-devtools-axi lavish-axi" | grep x | head
```

## Never author code — dispatch with an accurate brief

- `sandesh send --body "every dispatch brief carries the envelope rule" | tail`
"""
READ_WHOLE_UNIT_BAD = """# Sample

- `sandesh fetch --note "every envelope is read whole, never piped, filtered or redirected away" | grep x`
"""
OUTPUT_DISCIPLINE_BAD = """# Sample

- **Output discipline:** `<client> test --note "the envelope is read whole, never piped, filtered or redirected away, counts + failing names + assertion lines" | tail`
"""
DEBUGGING_BAD = """# Sample

- **Debugging a failed run:** `<client> test --log /tmp/r.log --note "the envelope is read whole, never piped, filtered or redirected away, rg the log" | tail`
"""

#: ``(place, gate, conforming sample, cuts, bad sample, shown calls in the bad sample)`` — the
#: AC's "each gate is proved both ways on synthetic text", one row per place of §S2 items 1–7.
PLACE_GATES = (
    ("item 1, orchestration-common.md", orchestration_common_findings, ORCHESTRATION_SAMPLE,
     ORCHESTRATION_CUTS, ORCHESTRATION_BAD, 2),
    ("item 2, sub-agent-procedure.md", rule_section_findings, RULE_SECTION_SAMPLE,
     RULE_SECTION_CUTS, RULE_SECTION_BAD, 1),
    ("item 3, sandesh.md", read_whole_unit_findings, READ_WHOLE_UNIT_SAMPLE,
     READ_WHOLE_UNIT_CUTS, READ_WHOLE_UNIT_BAD, 1),
    ("item 4, the model-b skill", read_whole_unit_findings, READ_WHOLE_UNIT_SAMPLE,
     READ_WHOLE_UNIT_CUTS, READ_WHOLE_UNIT_BAD, 1),
    ("item 5, the crucible skill", rule_section_findings, RULE_SECTION_SAMPLE,
     RULE_SECTION_CUTS, RULE_SECTION_BAD, 1),
    ("item 6, the agent templates", output_discipline_findings, OUTPUT_DISCIPLINE_SAMPLE,
     OUTPUT_DISCIPLINE_CUTS, OUTPUT_DISCIPLINE_BAD, 1),
    ("item 7, rust.toml's debugging line", debugging_line_findings, DEBUGGING_SAMPLE,
     DEBUGGING_CUTS, DEBUGGING_BAD, 1),
)

#: The pins-only half of each gate, to show a bad sample meets every pin.
_PINS_ONLY = {
    orchestration_common_findings: lambda text: (
        section_rule_findings(text, ORCHESTRATION_PINS)
        + ([] if _carries(units(md_section(text, BRIEF_SECTION)), BRIEF_PINS) else ["brief"])),
    rule_section_findings: lambda text: section_rule_findings(text, RULE_PINS),
    read_whole_unit_findings: lambda text: rule_findings(text, UNIT_PINS),
    output_discipline_findings: lambda text: line_rule_findings(
        text, OUTPUT_DISCIPLINE, OUTPUT_DISCIPLINE_PINS),
    debugging_line_findings: lambda text: line_rule_findings(text, DEBUGGING_LINE, DEBUGGING_PINS),
}


# ------------------------------------------------------------------ §S3 tests ----

#: §S3 AC: a sample shown on a fenced line and in a code span alike.
def _fenced(*lines: str) -> str:
    return "Run it:\n\n```bash\n" + "\n".join(lines) + "\n```\n"


def _span(command: str) -> str:
    return f"Run `{command}` now.\n"


#: §S3 AC "it finds": the commands written bare in the AC, each shown fenced and as a code span.
FOUND_COMMANDS = (
    "<client> test --agent x | tail -5",
    "python3 ~/.crucible/clients/python-crucible.py plans 2>&1 | head",
    "lavish-axi poll | jq .",
    "modelb-axi agents > /dev/null",
    "worktree-flow.py status 2>/dev/null",
    "gh-axi run list &>/dev/null",
    "gh-axi run list &> /dev/null",
)
#: §S3 AC "it finds": the code spans the AC lists, in prose.
FOUND_SPANS = (
    "`sandesh status | grep listening`",
    "`~/.crucible/clients/<stack>-crucible.py plans | head`",
    "`modelb-axi agents |& head`",
    '`sandesh fetch --body "a | b"`',
    "`sandesh status >> /dev/null`",
)
#: §S3 AC "it does not find": the commands written bare in the AC.
SPARED_COMMANDS = (
    "<client> test --agent x --log /tmp/run.log",
    "<client> regression --agent x > /tmp/run.out 2>&1",
    "sandesh status || true",
    "sandesh status && git log | head",
    "sandesh status; git log | head",
    "echo x | sandesh send --project P",
    "git log | head",
)
#: §S3 AC "it does not find": the code spans the AC lists.
SPARED_SPANS = (
    "`sandesh fetch --to '<your address>'`",
    "`python3 <client> plan-file --cycle-kind <red-green|verify>`",
    "`<client> gate-respond --action approve|fix|skip`",
    "`sandesh-pi x | y`",
    "`/sandesh-watcher stop | y`",
)


class AxiEnvelopeDetectorTest(unittest.TestCase):
    """§S3 AC "the detector both ways" — every listed finding is found, once; every listed
    non-finding is spared."""

    def test_finds_each_listed_command_on_a_fenced_line(self):
        for command in FOUND_COMMANDS:
            with self.subTest(command=command):
                self.assertEqual(axi_findings(_fenced(command)), [(4, command)])

    def test_finds_each_listed_command_in_a_code_span(self):
        for command in FOUND_COMMANDS:
            with self.subTest(command=command):
                self.assertEqual(axi_findings(_span(command)), [(1, command)])

    def test_finds_each_listed_code_span(self):
        for span in FOUND_SPANS:
            with self.subTest(span=span):
                self.assertEqual(axi_findings(f"Run {span} now.\n"), [(1, span.strip("`"))])

    def test_finds_a_pipe_on_a_backslash_continued_fenced_line(self):
        text = "```bash\nsandesh inbox \\\n  --project P | tail\n```\n"
        self.assertEqual(axi_findings(text), [(2, "sandesh inbox --project P | tail")])

    def test_finds_a_governed_form_no_prohibition_spares_it(self):
        self.assertEqual(axi_findings("Never run `sandesh status | head`.\n"),
                         [(1, "sandesh status | head")])

    def test_spares_each_listed_command_on_a_fenced_line(self):
        for command in SPARED_COMMANDS:
            with self.subTest(command=command):
                self.assertEqual(axi_findings(_fenced(command)), [])

    def test_spares_each_listed_command_in_a_code_span(self):
        for command in SPARED_COMMANDS:
            with self.subTest(command=command):
                self.assertEqual(axi_findings(_span(command)), [])

    def test_spares_each_listed_code_span(self):
        for span in SPARED_SPANS:
            with self.subTest(span=span):
                self.assertEqual(axi_findings(f"Run {span} now.\n"), [])

    def test_spares_a_prose_sentence_naming_sandesh_and_head(self):
        text = "Never pipe sandesh output through head; read it whole.\n"
        self.assertEqual(axi_findings(text), [])

    def test_a_redirect_to_a_file_is_spared_and_the_same_call_to_dev_null_is_found(self):
        self.assertEqual(axi_findings(_span("modelb-axi agents > /tmp/agents.out")), [])
        self.assertEqual(axi_findings(_span("modelb-axi agents > /dev/null")),
                         [(1, "modelb-axi agents > /dev/null")])

    def test_each_finding_is_reported_once_with_its_line(self):
        text = ("Intro.\n\n```bash\nsandesh status | head\ngit log | head\n```\n\n"
                "Then `gh-axi run list | tail` and `gh-axi run list`.\n")
        self.assertEqual(axi_findings(text), [(4, "sandesh status | head"),
                                              (8, "gh-axi run list | tail")])


class AxiEnvelopeGuardedTreeTest(unittest.TestCase):
    """§S3 AC "the guard on the real tree" — no guarded file shows an AXI call piped or
    redirected away."""

    def test_no_guarded_file_shows_an_axi_call_piped_or_redirected_away(self):
        files = guarded_files()
        self.assertTrue(any(f.name == "orchestration-common.md" for f in files),
                        "the guarded set must include the model-b references")
        found = [f"{path.relative_to(REPO_ROOT).as_posix()}:{line}: `{content}`"
                 for path in files for line, content in axi_findings(read_text(path))]
        self.assertEqual(found, [], "§S3: a guarded file shows an AXI call piped or redirected "
                         f"away — read the envelope whole ({len(found)}):\n" + "\n".join(found))


# ------------------------------------------------------------------ §S1–§S2 tests ----

class RulePlaceGateProofTest(unittest.TestCase):
    """§S1–§S2 AC — each place's gate proved both ways on synthetic text."""

    def test_each_gate_passes_its_conforming_sample(self):
        for place, gate, sample, _cuts, _bad, _calls in PLACE_GATES:
            with self.subTest(place=place):
                self.assertEqual(gate(sample), [])

    def test_each_cut_bites_its_one_pin(self):
        for place, gate, sample, cuts, _bad, _calls in PLACE_GATES:
            for cut, replacement, pin in cuts:
                with self.subTest(place=place, pin=pin):
                    self.assertIn(cut, sample)
                    found = gate(sample.replace(cut, replacement))
                    self.assertEqual(len(found), 1, found)
                    self.assertIn(f"lacks {[pin]}", found[0])

    def test_each_bad_sample_meets_every_pin_only_through_a_shown_piped_axi_call(self):
        for place, gate, _sample, _cuts, bad, calls in PLACE_GATES:
            with self.subTest(place=place):
                self.assertEqual(_PINS_ONLY[gate](bad), [], "the bad sample must meet every pin")
                found = gate(bad)
                self.assertEqual(len(found), calls, found)
                for finding in found:
                    self.assertIn("shows an AXI call piped or redirected away", finding)

    def test_each_gate_fails_its_conforming_sample_with_a_piped_axi_call_added(self):
        for place, gate, sample, _cuts, _bad, _calls in PLACE_GATES:
            with self.subTest(place=place):
                found = gate(sample + "\nRun `modelb-axi agents 2>/dev/null` when needed.\n")
                self.assertEqual(found, [f"line {sample.count(chr(10)) + 2} shows an AXI call "
                                         "piped or redirected away: `modelb-axi agents 2>/dev/null`"])

    def test_section_pins_split_across_two_sections_do_not_count(self):
        log_bullet = ("- A runner log a client writes with `--log` is not an envelope; searching "
                      "it for a failure stays\n  allowed.\n")
        split = RULE_SECTION_SAMPLE.replace(log_bullet, "").replace(
            "Something else.\n", "Something else.\n\n" + log_bullet)
        self.assertNotEqual(split, RULE_SECTION_SAMPLE)
        self.assertEqual(rule_section_findings(split),
                         ["no section states the rule; the closest lacks "
                          "['the --log runner-log exception']"])

    def test_a_heading_inside_a_fence_does_not_split_a_section(self):
        fenced_heading = RULE_SECTION_SAMPLE.replace(
            "- A long run", "```bash\n# a comment, not a heading\n```\n\n- A long run")
        self.assertEqual(rule_section_findings(fenced_heading), [])

    def test_unit_pins_split_across_two_units_do_not_count(self):
        split = "# Sample\n\n- Every envelope is read whole.\n- Never piped, filtered or redirected away.\n"
        self.assertEqual(len(read_whole_unit_findings(split)), 1)

    def test_the_brief_bullet_counts_only_in_the_never_author_code_section(self):
        moved = ORCHESTRATION_SAMPLE.replace(
            "## Never author code — dispatch with an accurate brief", "## Elsewhere")
        found = orchestration_common_findings(moved)
        self.assertEqual(found, [f"§ 'Never author code' lacks {[BRIEF_PIN_NAME]}"])

    def test_an_output_discipline_gate_needs_exactly_one_such_line(self):
        self.assertEqual(output_discipline_findings("# Sample\n\nNothing here.\n"),
                         [f"expected one unit matching {OUTPUT_DISCIPLINE}, found 0"])
        twice = OUTPUT_DISCIPLINE_SAMPLE + "\n" + OUTPUT_DISCIPLINE_SAMPLE.replace("# Sample\n", "")
        self.assertEqual(output_discipline_findings(twice),
                         [f"expected one unit matching {OUTPUT_DISCIPLINE}, found 2"])

    def test_todays_template_wording_bites(self):
        green = ("- **Output discipline:** every test run goes through the stack crucible client, "
                 "which prints only the summary (counts + failing names + assertion lines). "
                 "Never `| tail`.\n")
        found = output_discipline_findings(green)
        self.assertEqual(len(found), 1, found)
        self.assertIn(f"lacks {[ENVELOPE, READ_WHOLE, PIPED, FILTERED, REDIRECTED_AWAY]}", found[0])

    def test_todays_model_b_bullet_bites(self):
        bullet = ("- **Never pipe user feedback or poll output through head, tail or grep** — "
                  "read it whole.\n")
        found = read_whole_unit_findings(bullet)
        self.assertEqual(found, [f"no unit states the rule; the closest lacks "
                                 f"{[FILTERED, REDIRECTED_AWAY]}"])


class RuleInEachPlaceTest(unittest.TestCase):
    """§S1–§S2 AC "the rule in each place" — §S2 items 1–7 on the real files."""

    def test_item_1_orchestration_common_states_the_rule_and_the_brief_carries_it(self):
        self.assertEqual(orchestration_common_findings(read_text(ORCHESTRATION_COMMON)), [])

    def test_item_2_the_sub_agent_procedure_states_the_rule(self):
        self.assertEqual(rule_section_findings(read_text(SUB_AGENT_PROCEDURE)), [])

    def test_item_3_the_sandesh_reference_reads_every_envelope_whole(self):
        self.assertEqual(read_whole_unit_findings(read_text(SANDESH_REFERENCE)), [])

    def test_item_4_the_model_b_skill_bullet_gains_axi_output(self):
        self.assertEqual(read_whole_unit_findings(read_text(MODEL_B_SKILL)), [])

    def test_item_5_the_crucible_skill_widens_never_through_head_to_the_rule(self):
        self.assertEqual(rule_section_findings(read_text(CRUCIBLE_SKILL)), [])

    def test_item_6_each_role_templates_output_discipline_line_carries_the_rule(self):
        for template in ROLE_TEMPLATES:
            with self.subTest(template=template.name):
                self.assertEqual(output_discipline_findings(read_text(template)), [])

    def test_item_7_the_rust_debugging_line_carries_the_rule(self):
        self.assertEqual(debugging_line_findings(read_text(RUST_STACK)), [])


class RenderedOutputDisciplineTest(unittest.TestCase):
    """§S2 item 8 AC — the rendered output-discipline lines carry the rule in both renders, and
    ``.pi/agents/python-*`` is byte-identical to ``generator/agents/python-*``."""

    def _render(self, lean_ctx: bool) -> dict[str, str]:
        stacks = sorted(p.stem for p in STACKS_DIR.glob("*.toml"))
        self.assertIn("rust", stacks)
        rendered = agents.render_definitions(stacks, ["pi"], TEMPLATES_DIR, STACKS_DIR,
                                             lean_ctx=lean_ctx)
        self.assertEqual(len(rendered), 4 * len(stacks))
        return rendered

    def test_the_lean_ctx_render_carries_the_rule_in_every_output_discipline_line(self):
        for rel, text in sorted(self._render(lean_ctx=True).items()):
            with self.subTest(definition=rel):
                self.assertEqual(output_discipline_findings(text), [])

    def test_the_built_in_render_carries_the_rule_in_every_output_discipline_line(self):
        for rel, text in sorted(self._render(lean_ctx=False).items()):
            with self.subTest(definition=rel):
                self.assertEqual(output_discipline_findings(text), [])

    def test_the_rendered_rust_debugging_line_carries_the_rule(self):
        for lean_ctx in (True, False):
            for rel, text in sorted(self._render(lean_ctx=lean_ctx).items()):
                if "rust-" not in rel:
                    continue
                with self.subTest(definition=rel, lean_ctx=lean_ctx):
                    self.assertEqual(debugging_line_findings(text), [])

    def test_the_tracked_generated_agents_carry_the_rule(self):
        for path in sorted(GENERATOR_AGENTS_DIR.glob("*.md")):
            with self.subTest(definition=path.name):
                self.assertEqual(output_discipline_findings(read_text(path)), [])

    def test_pi_agents_python_definitions_are_byte_identical_to_the_generated_ones(self):
        for role in ("red", "green", "verify", "fix"):
            name = f"python-{role}-agent.md"
            with self.subTest(definition=name):
                self.assertEqual((PI_AGENTS_DIR / name).read_bytes(),
                                 (GENERATOR_AGENTS_DIR / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
