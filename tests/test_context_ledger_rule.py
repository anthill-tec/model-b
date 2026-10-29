"""The shared context ledger is left alone; Model B's own ``AGENTS.md`` runs every AXI command raw
(CR-MDB-090 §S3, §S4, §S7).

Contract: ``docs/changes/CR-MDB-090-long-runs-read-whole-and-the-ledger-left-alone.md`` (design
reference PRD D5, ruled 2026-10-29; DN-multi-harness-deploy-model §D18: the skills name the
capability, the tool form lives in the definitions and ``AGENTS.md``).

- §S3 — the context-pressure figure the project's cached-read and compressed-shell tools report
  comes from one context ledger, machine-wide; its hints to evict entries are ignored, and it is
  never evicted or reset during a run. Stated in ``sub-agent-procedure.md`` and
  ``orchestration-common.md`` only (never in the templates), capability-worded; no ledger step is
  added to the ``shutdown`` skill.
- §S4 — ``AGENTS.md`` § Runtime/Tooling gains three bullets: every AXI command runs through
  ``ctx_shell`` with ``raw=true`` (a long run redirected to a file under ``/tmp``, a truncated run
  read whole from Pi's full-output file); lean-ctx's context ledger is machine-wide, never evicted
  or reset; a repo-wide search from the main checkout skips ``.worktrees/``, so a CR's in-flight
  code is searched by its worktree's path, ``.worktrees/<cr>``.
- CR-MDB-092 §S7.1 (PRD D5, ruled 2026-10-29; ``docs/changes/
  CR-MDB-092-lean-ctx-contract-refresh-and-role-tools.md``) — § Runtime/Tooling gains a fourth
  bullet, one list item with no nested list: the reach tools for gap analysis, the spec pre-review
  and close-out (``ctx_graph``, ``ctx_callgraph``, ``ctx_explore``, ``ctx_compose``), served only
  under lean-ctx's ``standard`` or ``power`` tool profile, and a sub-agent having only the tools its
  definition's ``tools:`` lists (``general-purpose`` gets Pi's built-ins). Its pin is §S8.3's.

§S5's scaffolded bullet is pinned by ``pointer_findings`` in ``tests/test_project_tools_setup.py``.

Class map:

- ``LedgerRuleProofTest`` — the ledger pin (``ledger_rule_findings``) proved both ways on synthetic
  text: a conforming sample passes, each cut bites the pin, a split across two units or two
  sections does not count, today's AXI section bites, the ``code-health`` skill's audit-ledger
  wording is spared, evict and reset without "never" or "ignore" bites, and a bad sample meeting
  the pin only through a shown piped AXI call fails on that call.
- ``LedgerRuleInEachPlaceTest`` — the pin on the procedure and ``orchestration-common``; no
  template states the rule; no ``shutdown`` file gains a ledger step.
- ``AgentsMdRuntimePinsProofTest`` — the four ``AGENTS.md`` pins (``agents_md_runtime_findings``)
  proved both ways on synthetic text, and the reach bullet's shape (``reach_bullet_shape_findings``:
  exactly one, with no nested list).
- ``AgentsMdRuntimePinsTest`` — the four pins, and the reach bullet's shape, on the real
  ``AGENTS.md``.

MIGRATED at CR-MDB-092 (§S7, §S8.3): "three pins" became four throughout.

**The gates** match normalised text (``normalise``: lower-cased, backticks and ``*`` dropped), unit
by unit (``units``, imported from ``tests/test_chrome_ui_relay_skill.py``): a unit is a list item
with its nested items and wrapped lines, or a paragraph. Each gate also fails on any shown AXI call
piped or redirected away in the text it reads (``_axi_finding_messages``, imported from
``tests/test_axi_envelope_read_whole.py``).

Hermetic: reads repository files only. Stdlib only.
"""

import re
import unittest

from tests._helpers import REPO_ROOT, md_section, read_text
from tests.test_axi_envelope_read_whole import (
    AXI_WORD,
    CTX_SHELL,
    ORCHESTRATION_COMMON,
    RAW_TRUE,
    ROLE_TEMPLATES,
    SKILLS,
    SUB_AGENT_PROCEDURE,
    _axi_finding_messages,
    _carries,
)
from tests.test_chrome_ui_relay_skill import normalise, units
from tests.test_python_floor import RUNTIME_HEADING

AGENTS_MD = REPO_ROOT / "AGENTS.md"
SHUTDOWN_SKILL_DIR = SKILLS / "shutdown"

# ------------------------------------------------------------------ §S3 the ledger pin ----

#: §S7: one unit carries the context ledger (or its context-pressure figure), machine-wide, evict,
#: reset, and "never" or "ignore".
LEDGER_PIN_NAME = "the machine-wide context ledger: its evict hints ignored, never evicted or reset"
CONTEXT_LEDGER = r"\bcontext ledger\b|\bcontext[- ]pressure\b"
MACHINE_WIDE = r"\bmachine-wide\b"
EVICT = r"\bevict"
RESET = r"\breset"
NEVER_OR_IGNORE = r"\b(?:never|ignore)\b"
LEDGER_PINS = (CONTEXT_LEDGER, MACHINE_WIDE, EVICT, RESET, NEVER_OR_IGNORE)
#: §S3 AC: a ledger step in the ``shutdown`` skill.
SHUTDOWN_LEDGER_STEP = r"\bcontext ledger\b|\bledger status\b"


def ledger_rule_findings(text: str) -> list[str]:
    """§S3: ``[]`` when one unit of ``text`` leaves the machine-wide context ledger alone; and no
    shown AXI call piped or redirected away."""
    out = [] if _carries(units(text), LEDGER_PINS) else [
        f"no unit leaves the context ledger alone; it lacks {[LEDGER_PIN_NAME]}"]
    return out + _axi_finding_messages(text)


def shutdown_ledger_step_findings(text: str) -> list[str]:
    """§S3 AC: every unit of ``text`` naming the context ledger or a ledger status."""
    return [unit for unit in units(text) if re.search(SHUTDOWN_LEDGER_STEP, unit)]


# ------------------------------------------------------------------ §S4 the AGENTS.md pins ----

RAW_PIN_NAME = "every AXI command runs through ctx_shell with raw=true; a truncated run's full-output file"
AGENTS_LEDGER_PIN_NAME = "lean-ctx's context ledger is machine-wide: never evicted or reset"
#: CR-MDB-092 §S7.1, §S8.3: the reach tools, served under lean-ctx's ``standard`` profile; a
#: sub-agent has only its definition's ``tools:``, and ``general-purpose`` has none.
REACH_PIN_NAME = ("the reach tools ctx_graph and ctx_callgraph, served under the standard profile; "
                  "a general-purpose sub-agent has no tools: and no ctx_* tool")
#: CR-MDB-092 §S8.3: the reach unit's five patterns (normalised text).
REACH_PINS = (r"\bctx_graph\b", r"\bctx_callgraph\b", r"\bstandard\b", r"\bgeneral-purpose\b",
              r"tools:")
WORKTREE_PIN_NAME = "a search reaches a CR's in-flight code by its worktree's path, .worktrees/<cr>"
#: §S7: ``(name, patterns)`` — one unit of § Runtime/Tooling carries each pin.
AGENTS_MD_PINS = (
    (RAW_PIN_NAME, (CTX_SHELL, RAW_TRUE, AXI_WORD, r"\btruncat|\bfull[- ]output\b")),
    (AGENTS_LEDGER_PIN_NAME, (MACHINE_WIDE, EVICT, RESET, r"\bnever\b")),
    (WORKTREE_PIN_NAME, (r"\.worktrees/", r"\bsearch", r"<cr>")),
    # MIGRATED at CR-MDB-092 (§S7.1, §S8.3): the fourth pin, the reach unit.
    (REACH_PIN_NAME, REACH_PINS),
)


def agents_md_runtime_findings(text: str) -> list[str]:
    """§S4: one finding per ``AGENTS_MD_PINS`` pin no unit of § Runtime/Tooling carries; and no
    shown AXI call piped or redirected away in that section."""
    section = md_section(text, RUNTIME_HEADING)
    section_units = units(section)
    out = [f"§ Runtime/Tooling lacks {[name]}" for name, patterns in AGENTS_MD_PINS
           if not _carries(section_units, patterns)]
    return out + _axi_finding_messages(section)


_TOP_LEVEL_ITEM = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
_NESTED_ITEM = re.compile(r"^\s+(?:[-*+]|\d+[.)])\s+")


def reach_bullet_shape_findings(text: str) -> list[str]:
    """CR-MDB-092 §S7.1: § Runtime/Tooling carries exactly one top-level list item meeting the
    reach pin (``REACH_PINS``), and that item has no nested list. ``[]`` when it does."""
    items: list[list[str]] = []
    current: list[str] | None = None
    for line in md_section(text, RUNTIME_HEADING).splitlines():
        if _TOP_LEVEL_ITEM.match(line):
            current = [line]
            items.append(current)
        elif not line.strip() or line.lstrip().startswith("#"):
            current = None
        elif current is not None:
            current.append(line)
    reach = [lines for lines in items if _carries([normalise("\n".join(lines))], REACH_PINS)]
    if len(reach) != 1:
        return [f"§ Runtime/Tooling has {len(reach)} reach bullets; exactly one is expected"]
    nested = [line for line in reach[0][1:] if _NESTED_ITEM.match(line)]
    return [f"the reach bullet has a nested list: {nested}"] if nested else []


# ------------------------------------------------------------------ synthetic samples ----

#: §S3, worded as the spec words it: one bullet, its consequences nested.
LEDGER_SAMPLE = """# Sample

## The ledger is left alone

- **The ledger is machine-wide.** The context-pressure figure that the project's cached-read and
  compressed-shell tools report comes from one context ledger, shared by every session, sub-agent
  and project on the machine, and measured against a fixed window, not your context. Ignore its
  hints to evict entries, and never evict entries or reset the ledger during a run:
  - evicting excludes a file for the session;
  - resetting clears the re-read cache that every other session relies on.

## Next

Something else.
"""

#: For each pattern of the ledger pin, the replacements that remove it from ``LEDGER_SAMPLE``
#: (every occurrence; ``str.replace``).
LEDGER_CUTS = (
    ("the context ledger or its context-pressure figure", (("context", "usage"),)),
    ("machine-wide", (("machine-wide", "project-wide"),)),
    ("evict", (("evict", "drop"),)),
    ("reset", (("reset", "wipe"),)),
    ("never or ignore", (("Ignore its\n  hints to evict entries, and never evict entries or reset",
                          "Its\n  hints say when to evict entries, and to evict entries or reset"),)),
)

#: The procedure's § "Every AXI envelope is read whole" as it stands today: no ledger rule.
TODAYS_AXI_SECTION = """# Sample

## Every AXI envelope is read whole (NON-NEGOTIABLE)
- **It covers the output of an AXI command:** the Crucible clients (`<stack>-crucible.py`), `sandesh`, `modelb-axi`, `worktree-flow.py`, `gh-axi`, `chrome-devtools-axi` and `lavish-axi`.
- **Every envelope is read whole, every time:** its `warnings[]`, `help[]` and `error` carry what you need next.
- **Its output is never grepped, headed, tailed or otherwise filtered,** never narrowed with `jq`, and never summarised by pattern.
- **Its output is never redirected away:** neither its stdout nor its stderr goes to `/dev/null`.
- **Every AXI command runs uncompressed:** through the project's compressed shell in its raw mode, as the agent definition or the project's `AGENTS.md` names it, so no compression step cuts or reshapes its envelope.
- **A run the harness truncates names the file that holds its full output.** This is the fallback for a run that was not redirected. The envelope is near the end of the output, and its first line is the **last** line that begins `axi:` (under a JSON output format the envelope is one JSON line). When the output shown does not reach back to the envelope's first line, that file is read in windows, by line offset and limit, until the envelope has been read whole. It is never filtered to fit.
- **A long run redirects both its streams to a file under `/tmp`, outside the tree, so the envelope is read whole:** that file is read with the harness's plain file read from the envelope's first line to its end; a search that only locates that line's number is allowed, and the envelope itself is never searched or filtered (PRD D5, ruled 2026-10-29).
- **A runner log a client writes with `--log` is not an envelope:** searching it for a failure stays allowed. `--log` keeps that runner log beside the run, and does not take the run's output off the console.
"""

#: The ``code-health`` skill's audit-ledger wording: a ledger, but not the context ledger.
CODE_HEALTH_LEDGER = """# Sample

- **Ledger mutation is Mainline-only**, through `~/.agents/scripts/rust-code-health.py ledger`
  `assign`/`sync`; a track never resets or evicts a row of the machine ledger.
"""

#: A bad sample: it meets the ledger pin only through a shown piped AXI call.
LEDGER_BAD = """# Sample

- `sandesh status --note "the context ledger is machine-wide, ignore its evict hints, never reset it" | grep x`
"""

#: §S4, worded as the spec words it, inside a Runtime/Tooling section.
AGENTS_MD_SAMPLE = f"""# Repository Guidelines

{RUNTIME_HEADING}

- **Python ≥ 3.14** (`tomllib`); the published floor.
- Prefer lean-ctx reads (`ctx_read`/`ctx_search`/`ctx_shell`/`ctx_tree`) over raw file/grep/shell calls.
- **Every AXI command runs through `ctx_shell` with `raw=true`.** The AXI commands are the Crucible clients, `sandesh`, `modelb-axi`, `worktree-flow.py`, `gh-axi`, `chrome-devtools-axi` and `lavish-axi`; compression can cut or reshape their envelopes. A long run redirects both streams (`> /tmp/<run>.out 2>&1`) to a file under `/tmp`. That file is read with the built-in `read` from the envelope's first line (the last line that begins `axi:`) to its end; a search may only locate that line's number. When Pi truncates a run, its notice names the full-output file; the envelope is read whole from it with `read` `offset`/`limit`.
- **lean-ctx's context ledger is machine-wide.** Ignore its evict hints, and never evict or reset it during a run.
- **A repo-wide search from the main checkout skips `.worktrees/`.** The directory is gitignored, and lean-ctx's walkers also prune it. Search a CR's in-flight code by passing its worktree's path, `.worktrees/<cr>`, never `.worktrees` itself.
- **Reach tools** for gap analysis, the spec pre-review and close-out: `ctx_graph` (`action=impact`; `action=diff`, `since=develop`), `ctx_callgraph` (`action=callers`), `ctx_explore` and `ctx_compose`. lean-ctx serves `ctx_graph` and `ctx_explore` only under its `standard` or `power` tool profile (or a `tools_enabled` list naming them). A sub-agent has only the tools its definition's `tools:` lists; a dispatch type with none (`general-purpose`) gets Pi's built-ins and no `ctx_*` tool.
- Confirm destructive operations; delegate super-user ops to the user.

## Testing & QA

Something else.
"""
# MIGRATED at CR-MDB-092 (§S7.1): AGENTS_MD_SAMPLE gains the reach bullet, worded as §S7.1 words it.

_RAW_BULLET_START = "- **Every AXI command runs through"
_LEDGER_BULLET = ("- **lean-ctx's context ledger is machine-wide.** Ignore its evict hints, and "
                  "never evict or reset it during a run.\n")
_WORKTREE_BULLET = ("- **A repo-wide search from the main checkout skips `.worktrees/`.** The "
                    "directory is gitignored, and lean-ctx's walkers also prune it. Search a CR's "
                    "in-flight code by passing its worktree's path, `.worktrees/<cr>`, never "
                    "`.worktrees` itself.\n")
#: CR-MDB-092 §S7.1: the reach bullet, as in ``AGENTS_MD_SAMPLE``.
_REACH_BULLET = ("- **Reach tools** for gap analysis, the spec pre-review and close-out: `ctx_graph` "
                 "(`action=impact`; `action=diff`, `since=develop`), `ctx_callgraph` "
                 "(`action=callers`), `ctx_explore` and `ctx_compose`. lean-ctx serves `ctx_graph` "
                 "and `ctx_explore` only under its `standard` or `power` tool profile (or a "
                 "`tools_enabled` list naming them). A sub-agent has only the tools its "
                 "definition's `tools:` lists; a dispatch type with none (`general-purpose`) gets "
                 "Pi's built-ins and no `ctx_*` tool.\n")

#: For each pattern of each ``AGENTS.md`` pin, ``(what is cut, replacements, pin)``.
AGENTS_MD_CUTS = (
    ("ctx_shell", (("runs through `ctx_shell` with", "runs through the shell with"),), RAW_PIN_NAME),
    ("raw=true", (("with `raw=true`.**", "uncompressed.**"),), RAW_PIN_NAME),
    ("axi", (("Every AXI command runs", "Every command runs"),
             ("The AXI commands are the Crucible clients, `sandesh`, `modelb-axi`, "
              "`worktree-flow.py`, `gh-axi`, `chrome-devtools-axi` and `lavish-axi`; compression",
              "Compression"),
             ("the last line that begins `axi:`", "its marker line")), RAW_PIN_NAME),
    ("truncated or full-output", ((" When Pi truncates a run, its notice names the full-output "
                                   "file; the envelope is read whole from it with `read` "
                                   "`offset`/`limit`.", ""),), RAW_PIN_NAME),
    ("machine-wide", (("ledger is machine-wide", "ledger is shared"),), AGENTS_LEDGER_PIN_NAME),
    ("evict", (("Ignore its evict hints, and never evict or reset",
                "Ignore its hints, and never reset"),), AGENTS_LEDGER_PIN_NAME),
    ("reset", (("never evict or reset it", "never evict it"),), AGENTS_LEDGER_PIN_NAME),
    ("never", (("and never evict or reset it", "and evict or reset it only when asked"),),
     AGENTS_LEDGER_PIN_NAME),
    (".worktrees/", (("skips `.worktrees/`.**", "skips the worktrees.**"),
                     ("`.worktrees/<cr>`", "the worktrees dir plus <cr>")), WORKTREE_PIN_NAME),
    ("search", (("A repo-wide search", "A repo-wide walk"), ("Search a CR's", "Reach a CR's")),
     WORKTREE_PIN_NAME),
    ("<cr>", (("`.worktrees/<cr>`", "`.worktrees/` and the CR id"),), WORKTREE_PIN_NAME),
    # MIGRATED at CR-MDB-092 (§S7.1, §S8.3): one cut per pattern of the reach pin.
    ("ctx_graph", (("`ctx_graph` (`action=impact`;", "`ctx_map` (`action=impact`;"),
                   ("serves `ctx_graph` and", "serves the graph tool and")), REACH_PIN_NAME),
    ("ctx_callgraph", (("`ctx_callgraph` (`action=callers`)", "a call search (`action=callers`)"),),
     REACH_PIN_NAME),
    ("standard", (("its `standard` or `power` tool profile", "its `power` tool profile"),),
     REACH_PIN_NAME),
    ("general-purpose", (("(`general-purpose`)", "(the default type)"),), REACH_PIN_NAME),
    ("tools:", (("its definition's `tools:` lists", "its definition lists"),), REACH_PIN_NAME),
)

#: Today's § Runtime/Tooling: none of the four bullets. MIGRATED at CR-MDB-092 (§S7): was three.
TODAYS_RUNTIME_SECTION = f"""# Repository Guidelines

{RUNTIME_HEADING}

- **Python ≥ 3.14** (`tomllib`); the published floor, `requires-python = ">=3.14"`. Package manager: **uv** (`uv tool install --python 3.14 .`); no `uv.lock`, no `requirements.txt`.
- Crucible's installed clients, `~/.crucible/clients/<stack>-crucible.py` (listed in `~/.crucible/crucible-clients.json`, installed by Crucible's own installer), are the only sanctioned client surface — never a checkout of the Crucible project. Model B ships, vendors and maintains none of them.
- Prefer lean-ctx reads (`ctx_read`/`ctx_search`/`ctx_shell`/`ctx_tree`) over raw file/grep/shell calls.
- Confirm destructive operations; delegate super-user ops to the user.

## Testing & QA

Something else.
"""

#: A bad sample: § Runtime/Tooling meets every pin only through a shown piped AXI call.
#: MIGRATED at CR-MDB-092 (§S7, §S8.3): the --note gains the reach words, so it meets the fourth pin.
AGENTS_MD_BAD = f"""# Repository Guidelines

{RUNTIME_HEADING}

- `sandesh status --note "an axi command via ctx_shell with raw=true, a truncated run, machine-wide, evict, reset, never, search .worktrees/<cr>, ctx_graph, ctx_callgraph, the standard profile, general-purpose has no tools: line" | head`

## Testing & QA

Something else.
"""


def _cut(text: str, replacements) -> str:
    for old, new in replacements:
        text = text.replace(old, new)
    return text


# ------------------------------------------------------------------ §S3 tests ----

class LedgerRuleProofTest(unittest.TestCase):
    """§S7 AC "the ledger pin", proved both ways on synthetic text."""

    def test_the_conforming_sample_passes(self):
        self.assertEqual(ledger_rule_findings(LEDGER_SAMPLE), [])

    def test_each_cut_bites_the_ledger_pin(self):
        for pattern, replacements in LEDGER_CUTS:
            with self.subTest(pattern=pattern):
                for old, _new in replacements:
                    self.assertIn(old, LEDGER_SAMPLE)
                found = ledger_rule_findings(_cut(LEDGER_SAMPLE, replacements))
                self.assertEqual(found, [f"no unit leaves the context ledger alone; it lacks "
                                         f"{[LEDGER_PIN_NAME]}"])

    def test_the_pin_split_across_two_units_does_not_count(self):
        old = "not your context. Ignore its\n  hints"
        self.assertIn(old, LEDGER_SAMPLE)
        split = LEDGER_SAMPLE.replace(old, "not your context.\n- Ignore its\n  hints")
        self.assertEqual(ledger_rule_findings(split), [f"no unit leaves the context ledger alone; "
                                                       f"it lacks {[LEDGER_PIN_NAME]}"])

    def test_the_pin_split_across_two_sections_does_not_count(self):
        old = "not your context. Ignore its\n  hints"
        split = LEDGER_SAMPLE.replace(old, "not your context.\n\n## Elsewhere\n\n- Ignore its\n  hints")
        self.assertNotEqual(split, LEDGER_SAMPLE)
        self.assertEqual(ledger_rule_findings(split), [f"no unit leaves the context ledger alone; "
                                                       f"it lacks {[LEDGER_PIN_NAME]}"])

    def test_todays_axi_section_has_no_ledger_rule_and_bites(self):
        self.assertEqual(ledger_rule_findings(TODAYS_AXI_SECTION),
                         [f"no unit leaves the context ledger alone; it lacks {[LEDGER_PIN_NAME]}"])

    def test_the_code_health_audit_ledger_wording_is_not_a_ledger_rule_unit(self):
        self.assertEqual(ledger_rule_findings(CODE_HEALTH_LEDGER),
                         [f"no unit leaves the context ledger alone; it lacks {[LEDGER_PIN_NAME]}"])

    def test_evict_and_reset_without_never_or_ignore_bites(self):
        unit = ("# Sample\n\n- The context ledger is machine-wide: evict entries or reset it when "
                "its pressure rises.\n")
        self.assertEqual(ledger_rule_findings(unit),
                         [f"no unit leaves the context ledger alone; it lacks {[LEDGER_PIN_NAME]}"])
        self.assertEqual(ledger_rule_findings(unit.replace("evict entries", "never evict entries")),
                         [])

    def test_the_bad_sample_meets_the_pin_only_through_a_shown_piped_axi_call(self):
        self.assertTrue(_carries(units(LEDGER_BAD), LEDGER_PINS), "the bad sample must meet the pin")
        found = ledger_rule_findings(LEDGER_BAD)
        self.assertEqual(len(found), 1, found)
        self.assertIn("shows an AXI call piped or redirected away", found[0])

    def test_the_shutdown_ledger_step_detector_bites_and_spares(self):
        step = "# Sample\n\n- Run `lean-ctx ledger status` and report it.\n"
        found = shutdown_ledger_step_findings(step)
        self.assertEqual(len(found), 1, found)
        self.assertIn("lean-ctx ledger status", found[0])
        named = "# Sample\n\n- Report the context ledger's pressure.\n"
        self.assertEqual(len(shutdown_ledger_step_findings(named)), 1)
        spared = ("# Sample\n\n- Never a machine-wide or broad process kill.\n"
                  "- The audit ledger is Mainline's.\n")
        self.assertEqual(shutdown_ledger_step_findings(spared), [])


class LedgerRuleInEachPlaceTest(unittest.TestCase):
    """§S3 AC on the real files: the procedure and ``orchestration-common`` state the rule; the
    templates do not; the ``shutdown`` skill gains no ledger step."""

    def test_the_sub_agent_procedure_leaves_the_context_ledger_alone(self):
        self.assertEqual(ledger_rule_findings(read_text(SUB_AGENT_PROCEDURE)), [])

    def test_orchestration_common_leaves_the_context_ledger_alone(self):
        self.assertEqual(ledger_rule_findings(read_text(ORCHESTRATION_COMMON)), [])

    def test_no_role_template_states_the_ledger_rule(self):
        for template in ROLE_TEMPLATES:
            with self.subTest(template=template.name):
                found = [unit for unit in units(read_text(template))
                         if re.search(CONTEXT_LEDGER, unit)]
                self.assertEqual(found, [], "§S3: the ledger rule is stated in the skills only")

    def test_no_shutdown_file_gains_a_ledger_step(self):
        files = sorted(p for p in SHUTDOWN_SKILL_DIR.rglob("*.md") if p.is_file())
        self.assertIn(SHUTDOWN_SKILL_DIR / "SKILL.md", files)
        for path in files:
            with self.subTest(file=path.relative_to(REPO_ROOT).as_posix()):
                self.assertEqual(shutdown_ledger_step_findings(read_text(path)), [])


# ------------------------------------------------------------------ §S4 tests ----

class AgentsMdRuntimePinsProofTest(unittest.TestCase):
    """§S7 AC "the AGENTS.md pins", proved both ways on synthetic text."""

    def test_the_conforming_sample_passes(self):
        self.assertEqual(agents_md_runtime_findings(AGENTS_MD_SAMPLE), [])

    def test_each_cut_bites_its_one_pin(self):
        for pattern, replacements, pin in AGENTS_MD_CUTS:
            with self.subTest(pattern=pattern, pin=pin):
                for old, _new in replacements:
                    self.assertIn(old, AGENTS_MD_SAMPLE)
                found = agents_md_runtime_findings(_cut(AGENTS_MD_SAMPLE, replacements))
                self.assertEqual(found, [f"§ Runtime/Tooling lacks {[pin]}"])

    def test_todays_runtime_section_lacks_all_four_pins(self):
        # MIGRATED at CR-MDB-092 (§S7, §S8.3): was test_todays_runtime_section_lacks_all_three_pins.
        self.assertEqual(agents_md_runtime_findings(TODAYS_RUNTIME_SECTION),
                         [f"§ Runtime/Tooling lacks {[name]}" for name, _p in AGENTS_MD_PINS])

    def test_each_pin_split_across_two_units_does_not_count(self):
        splits = (
            ("to its end; a search may only locate that line's number. When Pi truncates",
             "to its end; a search may only locate that line's number.\n- When Pi truncates",
             RAW_PIN_NAME),
            ("machine-wide.** Ignore its evict hints", "machine-wide.**\n- Ignore its evict hints",
             AGENTS_LEDGER_PIN_NAME),
            ("by passing its worktree's path, `.worktrees/<cr>`, never",
             "by passing its worktree's path.\n- That path is `.worktrees/<cr>`, never",
             WORKTREE_PIN_NAME),
            # MIGRATED at CR-MDB-092 (§S7.1, §S8.3): the reach pin split at its sub-agent sentence.
            ("(or a `tools_enabled` list naming them). A sub-agent has only",
             "(or a `tools_enabled` list naming them).\n- A sub-agent has only",
             REACH_PIN_NAME),
        )
        for old, new, pin in splits:
            with self.subTest(pin=pin):
                self.assertIn(old, AGENTS_MD_SAMPLE)
                found = agents_md_runtime_findings(AGENTS_MD_SAMPLE.replace(old, new))
                self.assertEqual(found, [f"§ Runtime/Tooling lacks {[pin]}"])

    def test_each_pin_outside_runtime_tooling_does_not_count(self):
        raw_bullet = next(line + "\n" for line in AGENTS_MD_SAMPLE.splitlines()
                          if line.startswith(_RAW_BULLET_START))
        # MIGRATED at CR-MDB-092 (§S7.1, §S8.3): the reach bullet moved out bites too.
        for bullet, pin in ((raw_bullet, RAW_PIN_NAME), (_LEDGER_BULLET, AGENTS_LEDGER_PIN_NAME),
                            (_WORKTREE_BULLET, WORKTREE_PIN_NAME), (_REACH_BULLET, REACH_PIN_NAME)):
            with self.subTest(pin=pin):
                self.assertIn(bullet, AGENTS_MD_SAMPLE)
                moved = AGENTS_MD_SAMPLE.replace(bullet, "").replace(
                    "## Testing & QA\n\n", "## Testing & QA\n\n" + bullet)
                self.assertEqual(agents_md_runtime_findings(moved),
                                 [f"§ Runtime/Tooling lacks {[pin]}"])

    def test_the_bad_sample_meets_every_pin_only_through_a_shown_piped_axi_call(self):
        section_units = units(md_section(AGENTS_MD_BAD, RUNTIME_HEADING))
        for name, patterns in AGENTS_MD_PINS:
            with self.subTest(pin=name):
                self.assertTrue(_carries(section_units, patterns), "the bad sample must meet it")
        found = agents_md_runtime_findings(AGENTS_MD_BAD)
        self.assertEqual(len(found), 1, found)
        self.assertIn("shows an AXI call piped or redirected away", found[0])

    def test_the_reach_bullet_shape_spares_the_conforming_sample(self):
        """CR-MDB-092 §S7.1: one reach bullet, no nested list."""
        self.assertEqual(reach_bullet_shape_findings(AGENTS_MD_SAMPLE), [])

    def test_the_reach_bullet_with_a_nested_list_bites(self):
        """CR-MDB-092 §S7.1: "one list item with no nested list" — its words still pass the pin
        (``units`` joins nested items), so only the shape check catches it."""
        old = " A sub-agent has only"
        self.assertEqual(_REACH_BULLET.count(old), 1)
        nested = AGENTS_MD_SAMPLE.replace(_REACH_BULLET,
                                          _REACH_BULLET.replace(old, "\n  - A sub-agent has only"))
        self.assertNotEqual(nested, AGENTS_MD_SAMPLE)
        self.assertEqual(agents_md_runtime_findings(nested), [], "the pin alone does not bite")
        nested_line = ("  - A sub-agent has only the tools its definition's `tools:` lists; a "
                       "dispatch type with none (`general-purpose`) gets Pi's built-ins and no "
                       "`ctx_*` tool.")
        self.assertEqual(reach_bullet_shape_findings(nested),
                         [f"the reach bullet has a nested list: {[nested_line]}"])

    def test_no_reach_bullet_or_two_reach_bullets_bite_the_shape(self):
        self.assertEqual(reach_bullet_shape_findings(TODAYS_RUNTIME_SECTION),
                         ["§ Runtime/Tooling has 0 reach bullets; exactly one is expected"])
        twice = AGENTS_MD_SAMPLE.replace(_REACH_BULLET, _REACH_BULLET + _REACH_BULLET)
        self.assertEqual(reach_bullet_shape_findings(twice),
                         ["§ Runtime/Tooling has 2 reach bullets; exactly one is expected"])
        moved = AGENTS_MD_SAMPLE.replace(_REACH_BULLET, "").replace(
            "## Testing & QA\n\n", "## Testing & QA\n\n" + _REACH_BULLET)
        self.assertEqual(reach_bullet_shape_findings(moved),
                         ["§ Runtime/Tooling has 0 reach bullets; exactly one is expected"])


class AgentsMdRuntimePinsTest(unittest.TestCase):
    """§S4 AC on the real ``AGENTS.md``: the four pins pass in § Runtime/Tooling (MIGRATED at
    CR-MDB-092 §S7: was three), and its reach bullet is one list item with no nested list."""

    def test_agents_md_runtime_tooling_carries_the_raw_ledger_worktree_and_reach_bullets(self):
        # MIGRATED at CR-MDB-092 (§S7.1, §S8.3): was
        # test_agents_md_runtime_tooling_carries_the_raw_ledger_and_worktree_bullets; the reach pin.
        self.assertEqual(agents_md_runtime_findings(read_text(AGENTS_MD)), [])

    def test_agents_md_reach_bullet_is_one_list_item_with_no_nested_list(self):
        """CR-MDB-092 §S7.1."""
        self.assertEqual(reach_bullet_shape_findings(read_text(AGENTS_MD)), [])


if __name__ == "__main__":
    unittest.main()
