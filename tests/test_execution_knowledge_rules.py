"""Where an orchestrator keeps its execution knowledge, and what the lean-ctx contract records
about the store (CR-MDB-045 §S6, §S7; PRD D5, amended 2026-09-27: instruction tiers versus
execution knowledge; DN-multi-harness §D18: skills name capabilities).

- §S6 — ``orchestration-common.md`` § "Memory" states five rules: where execution knowledge is
  kept when the project's ``.env`` carries ``KNOWLEDGE_CATEGORY`` (the project's knowledge store,
  under that category, one short fact per item, a stable kebab-case key, the same key supersedes);
  what goes there (only execution knowledge, never an orchestrator rule, an agent definition, a
  PRD/DN ruling, or a ``.env``/``AGENTS.md`` fact); who writes (only Mainline or Solo; a Track
  reads, and raises new facts to Mainline); the GC and no-unilateral-write rules still apply;
  without the key nothing changes. The section names the store as a capability.
- §S6 — bootstrap, where ``KNOWLEDGE_CATEGORY`` is set, restores the category's archived facts,
  then lists that category, and reports that the store is in use and how many facts it loaded; it
  never uses a query recall and never loads the automatic rooms. Shutdown needs no step.
- §S6 AC — both surfaces read ``KNOWLEDGE_CATEGORY`` as a schema-declared key and name no
  lean-ctx tool (no ``ctx_*`` tool, no ``lean_ctx`` tool, no MCP-qualified name, no
  ``lean-ctx <verb>`` CLI form). The existing harness-neutral, retired-tool and registry gates
  (``tests.test_harness_neutral_skills``, ``tests.test_bootstrap_shutdown_registry``) keep holding;
  nothing here requires a tool name in a skill.
- §S7 — ``contracts/lean-ctx.md`` records the knowledge verbs Model B relies on (remember, list a
  category, restore, remove), the setup path (the installer's verdict, then ``init``'s key and
  pointer) and the five pitfalls (a query recall is not a full listing; facts get archived
  silently; ``restore`` ignores ``dry_run``; the CLI's project does not follow the working
  directory; the store holds lean-ctx's automatic captures).

How a rule is read: phrase-level, inside ONE unit — a list item together with its nested items,
or a paragraph. An enumeration may also be read as its lead-in paragraph (ending in ``:``)
together with the list attached to it (``lead_in=True``): §S6's bootstrap step and §S7's verbs and
setup path are enumerations. Units are normalised (backticks and ``*`` dropped, whitespace
collapsed, lower-cased). Every detector is proven on synthetic text in ``RuleDetectorTest``; no
test pins a line number.

Hermetic: reads only repo files. Stdlib only.
"""

import re
import unittest

from modelb_axi import scaffold
from tests._helpers import REPO_ROOT, read_text
from tests.test_bootstrap_shutdown_registry import (
    affirmed_findings,
    key_names_named,
    normalise,
)
from tests.test_orchestrator_rule_triage import section_body
from tests.test_project_registry_schema import NOT_REGISTRY_KEYS
from tests.test_skills_handover import IMPORTED_BUNDLE_NAMES

KEY = "KNOWLEDGE_CATEGORY"
COMMON_REL = "skills-src/model-b/references/orchestration-common.md"
MEMORY_HEADING = "Memory"
BOOTSTRAP_REL = "skills-src/bootstrap/SKILL.md"
SHUTDOWN_REL = "skills-src/shutdown/SKILL.md"
CONTRACT_REL = "contracts/lean-ctx.md"

# ------------------------------------------------------------------ rules ----
# Each rule is a tuple of regexes, every one of which must match inside ONE unit (normalised).

#: §S6 "Where to keep it."
MEMORY_WHERE = (
    r"\b(?:where|when|if)\b.{0,80}knowledge_category",
    r"\.env\b",
    r"\bexecution knowledge\b",
    r"\bknowledge store\b",
    r"\bcategory\b",
    r"\bone (?:short )?fact per (?:item|entry)\b",
    r"\bstable kebab-case key\b",
    r"\bsame key supersedes\b",
)
#: §S6 "What goes there."
MEMORY_WHAT = (
    r"\bonly execution knowledge\b",
    r"\bnever\b",
    r"\borchestrator rule\b",
    r"\bagent definition\b",
    r"\bprd\b",
    r"\bdn\b",
    r"\.env\b",
    r"\bagents\.md\b",
)
#: §S6 "Who writes."
MEMORY_WHO = (
    r"\bonly mainline or solo (?:writes|write|may write)\b",
    r"\btracks? (?:only )?reads?\b",
    r"\brais\w*\b.{0,60}\bto mainline\b",
)
#: A sentence that lets a Track write facts (a finding unless negated).
TRACK_WRITES = r"\btracks? (?:writes|may write|records|remembers|stores)\b"
#: §S6 "The GC and no-unilateral-write rules still apply."
MEMORY_GC_STILL_APPLIES = (r"\bgc\b", r"\bunilateral\b", r"\bstill appl(?:y|ies)\b")
#: The two standing rules §S6 keeps in force (regression pins: they exist today).
MEMORY_GC_PRINCIPLE = (r"\bgc principle\b", r"memory holds only what the repo doesn't yet track")
MEMORY_NO_UNILATERAL = (r"\bno unilateral writes\b",)
#: §S6 "Without the key, nothing changes."
MEMORY_WITHOUT_KEY = (
    r"\bwithout (?:the |a |its )?(?:knowledge_category|key)\b",
    r"\bnothing changes\b",
)

#: §S6 bootstrap — where the key is set: restore the archived facts, THEN list that category.
BOOTSTRAP_RESTORE_THEN_LIST = (
    r"\b(?:where|when|if)\b.{0,80}knowledge_category",
    r"\brestor\w*\b.{0,60}\barchived\b",
    r"\brestor\w*\b.*\blists?\b",
    r"\blists?\b.{0,40}\bcategory\b",
)
#: §S6 bootstrap — report the store in use and how many facts it loaded.
BOOTSTRAP_REPORT = (r"\breport\w*\b", r"\bin use\b", r"\b(?:how many|number of) facts\b")
#: §S6 bootstrap — never a query recall; never the automatic rooms.
BOOTSTRAP_NEVER_RECALL = (r"\bnever\b.{0,80}\brecall\b",)
BOOTSTRAP_NEVER_AUTOMATIC = (r"\bnever\b.{0,80}\bautomatic (?:rooms?|captures?)\b",)
RECALL = r"\brecall\b"
AUTOMATIC_ROOMS = r"\bautomatic (?:rooms?|captures?)\b"
#: What a shutdown knowledge step would say (a finding unless negated).
KNOWLEDGE_STEP = r"\bknowledge store\b|\bknowledge_category\b|\brestor\w*\b.{0,40}\bfacts\b"

#: §S7 — the knowledge verbs.
CONTRACT_VERBS = (r"\bremember\b", r"\blist\w*\b.{0,30}\bcategor", r"\brestore\b", r"\bremove\b")
#: §S7 — the setup path: the installer's verdict, then init's key and pointer.
CONTRACT_SETUP = (
    r"\binstaller\b.*\binit\b",
    r"\bverdicts?\b",
    r"knowledge_category",
    r"\bpointer\b|\bagents\.md\b",
)
#: §S7 — the five pitfalls, each in one unit.
PITFALLS = {
    "a query recall is not a full listing": (
        r"\brecall\b", r"\b(?:not|never|isn't)\b.{0,20}\bfull list"),
    "facts get archived silently": (r"\bfacts?\b", r"\barchiv\w*\b", r"\bsilent\w*\b"),
    "restore ignores dry_run": (r"\brestore\b.{0,40}\bignor\w*\b.{0,20}\bdry[_-]?run\b",),
    "the CLI's project does not follow the working directory": (
        r"\bcli\b", r"\bproject\b",
        r"\b(?:not|never|doesn't)\b.{0,40}\b(?:follow|track)\w*\b.{0,20}\bworking directory\b"),
    "the store holds lean-ctx's automatic captures": (
        r"\bstore\b", r"\bautomatic (?:captures?|rooms?)\b"),
}

#: \u00a7S7 \u2014 a monorepo's sub-projects derive the root's category when they share its token.
CONTRACT_SUB_PROJECT_CATEGORY = (
    r"\bsub-projects?\b", r"\bsame category\b", r"\broot\b", r"\btoken\b")

#: A lean-ctx TOOL name: a ``ctx_*`` tool, the ``lean_ctx`` tool, an MCP-qualified name, or a
#: ``lean-ctx <verb>`` CLI form. The product name and "the project's knowledge store" are not tools.
LEAN_CTX_TOOL_RE = re.compile(
    r"(?<![\w])ctx_[a-z_]+|\blean_ctx\b|\bmcp__\w+"
    r"|\blean-ctx\s+(?:knowledge|remember|recall|restore|read|grep|-c)\b"
)

# ------------------------------------------------------------------ units ----

_ITEM_RE = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+")
_HEADING_LINE_RE = re.compile(r"^\s{0,3}#{1,6}\s")
_FENCE_LINE_RE = re.compile(r"^\s*(?:```|~~~)")
_RULE_LINE_RE = re.compile(r"^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")


def _blocks(text: str) -> list[list[str]]:
    """Maximal runs of non-blank, non-heading lines outside fenced code."""
    out, current, fenced = [], [], False
    for line in text.splitlines():
        if _FENCE_LINE_RE.match(line):
            fenced = not fenced
            if current:
                out.append(current)
            current = []
            continue
        if (fenced or not line.strip() or _HEADING_LINE_RE.match(line)
                or _RULE_LINE_RE.match(line)):
            if current:
                out.append(current)
            current = []
            continue
        current.append(line)
    if current:
        out.append(current)
    return out


def rule_units(text: str, lead_in: bool = False) -> list[str]:
    """Every unit a rule may be read in, normalised: each list item with its nested items (and
    lazy continuation lines), and each paragraph before a list. With ``lead_in``, a paragraph
    ending in ``:`` together with the list attached to it is one more unit."""
    units = []
    for block in _blocks(text):
        first_item = next((i for i, ln in enumerate(block) if _ITEM_RE.match(ln)), None)
        paragraph = block if first_item is None else block[:first_item]
        if paragraph:
            units.append(normalise("\n".join(paragraph)))
        if first_item is None:
            continue
        for k in range(first_item, len(block)):
            m = _ITEM_RE.match(block[k])
            if not m:
                continue
            indent, end = len(m.group(1)), k + 1
            while end < len(block):
                nm = _ITEM_RE.match(block[end])
                if nm and len(nm.group(1)) <= indent:
                    break
                end += 1
            units.append(normalise("\n".join(block[k:end])))
        if lead_in and paragraph and paragraph[-1].rstrip().endswith(":"):
            units.append(normalise("\n".join(block)))
    return units


def satisfying_units(text: str, rule: tuple, lead_in: bool = False) -> list[str]:
    return [u for u in rule_units(text, lead_in) if all(re.search(p, u) for p in rule)]


def missing_report(text: str, rule: tuple, lead_in: bool = False) -> str:
    """The closest unit and the phrases it lacks, for a failure message."""
    units = rule_units(text, lead_in)
    if not units:
        return "no bullet or paragraph at all"
    best = max(units, key=lambda u: sum(1 for p in rule if re.search(p, u)))
    lacking = [p for p in rule if not re.search(p, best)]
    return f"closest unit {best[:240]!r} lacks {lacking!r}"


def lean_ctx_tool_findings(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if LEAN_CTX_TOOL_RE.search(ln)]


def _read(rel: str) -> str:
    return read_text(REPO_ROOT / rel)


def _memory_section() -> str:
    body = section_body(_read(COMMON_REL), MEMORY_HEADING)
    if body is None:
        raise AssertionError(f"{COMMON_REL} has no '## {MEMORY_HEADING}' section")
    return body


def _declared_keys() -> set[str]:
    return {e["name"] for e in scaffold.load_schema(scaffold.PROJECT_SCHEMA_PATH)}


class _RuleAssertions(unittest.TestCase):
    def assert_rule(self, text: str, rule: tuple, where: str, lead_in: bool = False):
        found = satisfying_units(text, rule, lead_in)
        self.assertTrue(found, f"{where}: no single bullet or paragraph states the rule; "
                               f"{missing_report(text, rule, lead_in)}")


# ------------------------------------------------------------ §S6 — Memory ----

class MemoryExecutionKnowledgeRulesTest(_RuleAssertions):
    """§S6: ``orchestration-common.md`` § "Memory" says where execution knowledge lives, what
    goes there, who writes, that the GC and no-unilateral-write rules still apply, and that
    nothing changes without the key — naming the store as a capability, never a tool."""

    WHERE = f"{COMMON_REL} § {MEMORY_HEADING}"

    def test_with_knowledge_category_execution_knowledge_is_kept_in_the_store_one_keyed_fact_per_item(self):
        self.assert_rule(_memory_section(), MEMORY_WHERE, self.WHERE)

    def test_only_execution_knowledge_goes_there_never_rules_definitions_rulings_or_project_facts(self):
        self.assert_rule(_memory_section(), MEMORY_WHAT, self.WHERE)

    def test_only_mainline_or_solo_writes_and_a_track_reads_and_raises_new_facts_to_mainline(self):
        memory = _memory_section()
        self.assert_rule(memory, MEMORY_WHO, self.WHERE)
        self.assertEqual(affirmed_findings(memory, TRACK_WRITES), [],
                         f"{self.WHERE}: a Track never writes facts")

    def test_the_gc_and_no_unilateral_write_rules_still_apply_to_the_store(self):
        self.assert_rule(_memory_section(), MEMORY_GC_STILL_APPLIES, self.WHERE)

    def test_the_gc_principle_and_no_unilateral_writes_rules_are_kept(self):
        # Regression pin: §S6 adds to § "Memory"; the two standing rules stay.
        memory = _memory_section()
        self.assert_rule(memory, MEMORY_GC_PRINCIPLE, self.WHERE)
        self.assert_rule(memory, MEMORY_NO_UNILATERAL, self.WHERE)

    def test_without_the_key_nothing_changes(self):
        self.assert_rule(_memory_section(), MEMORY_WITHOUT_KEY, self.WHERE)

    def test_the_section_names_the_store_as_a_capability_and_no_lean_ctx_tool(self):
        memory = _memory_section()
        self.assertTrue("knowledge store" in normalise(memory),
                        f"{self.WHERE}: names the project's knowledge store")
        self.assertEqual(lean_ctx_tool_findings(memory), [],
                         f"{self.WHERE}: names a lean-ctx tool (DN §D18)")

    def test_the_section_reads_knowledge_category_as_a_schema_declared_key(self):
        named = key_names_named(COMMON_REL, _memory_section())
        self.assertIn(KEY, named, f"{self.WHERE}: reads {KEY} by name")
        self.assertEqual(sorted(named - _declared_keys() - set(NOT_REGISTRY_KEYS)), [],
                         f"{self.WHERE}: names a registry key the schema does not declare")


# --------------------------------------------------------- §S6 — bootstrap ----

class BootstrapLoadsExecutionKnowledgeTest(_RuleAssertions):
    """§S6: bootstrap, where ``KNOWLEDGE_CATEGORY`` is set, restores the category's archived
    facts, then lists that category, and reports the store in use and the facts loaded; never a
    query recall, never the automatic rooms. Shutdown needs no step."""

    def test_where_the_key_is_set_it_restores_the_archived_facts_then_lists_the_category(self):
        self.assert_rule(_read(BOOTSTRAP_REL), BOOTSTRAP_RESTORE_THEN_LIST, BOOTSTRAP_REL,
                         lead_in=True)

    def test_it_reports_the_store_in_use_and_how_many_facts_it_loaded(self):
        self.assert_rule(_read(BOOTSTRAP_REL), BOOTSTRAP_REPORT, BOOTSTRAP_REL, lead_in=True)

    def test_it_never_uses_a_query_recall(self):
        text = _read(BOOTSTRAP_REL)
        self.assert_rule(text, BOOTSTRAP_NEVER_RECALL, BOOTSTRAP_REL)
        self.assertEqual(affirmed_findings(text, RECALL), [],
                         f"{BOOTSTRAP_REL}: a recall is only ever named to forbid it")

    def test_it_never_loads_the_automatic_rooms(self):
        text = _read(BOOTSTRAP_REL)
        self.assert_rule(text, BOOTSTRAP_NEVER_AUTOMATIC, BOOTSTRAP_REL)
        self.assertEqual(affirmed_findings(text, AUTOMATIC_ROOMS), [],
                         f"{BOOTSTRAP_REL}: the automatic rooms are only named to exclude them")

    def test_it_names_the_store_as_a_capability_and_no_lean_ctx_tool(self):
        text = _read(BOOTSTRAP_REL)
        self.assertTrue("knowledge store" in normalise(text),
                        f"{BOOTSTRAP_REL}: names the project's knowledge store")
        self.assertEqual(lean_ctx_tool_findings(text), [],
                         f"{BOOTSTRAP_REL}: names a lean-ctx tool (DN §D18)")

    def test_it_reads_knowledge_category_as_a_schema_declared_key(self):
        named = key_names_named(BOOTSTRAP_REL, _read(BOOTSTRAP_REL))
        self.assertIn(KEY, named, f"{BOOTSTRAP_REL}: reads {KEY} by name")
        self.assertIn(KEY, _declared_keys(), f"{KEY} is declared in the packaged schema")

    def test_shutdown_needs_no_knowledge_step(self):
        # Regression pin: §S6 "Shutdown needs no step."
        text = _read(SHUTDOWN_REL)
        self.assertEqual(affirmed_findings(text, KNOWLEDGE_STEP), [],
                         f"{SHUTDOWN_REL}: shutdown takes no knowledge-store step")
        self.assertEqual(lean_ctx_tool_findings(text), [])


# ---------------------------------------------------------- §S7 — contract ----

class LeanCtxContractKnowledgeTest(_RuleAssertions):
    """§S7: ``contracts/lean-ctx.md`` records the knowledge verbs, the setup path and the five
    pitfalls."""

    def test_it_records_the_four_knowledge_verbs_model_b_relies_on(self):
        self.assert_rule(_read(CONTRACT_REL), CONTRACT_VERBS, CONTRACT_REL, lead_in=True)

    def test_it_records_the_setup_path_installer_verdict_then_inits_key_and_pointer(self):
        self.assert_rule(_read(CONTRACT_REL), CONTRACT_SETUP, CONTRACT_REL, lead_in=True)

    def test_it_records_each_of_the_five_pitfalls(self):
        text = _read(CONTRACT_REL)
        for name, rule in PITFALLS.items():
            with self.subTest(pitfall=name):
                self.assert_rule(text, rule, f"{CONTRACT_REL} ({name})")

    def test_it_notes_that_sub_projects_sharing_the_token_derive_the_roots_category(self):
        # Finding F6 (\u00a7S7, amended at 06a4ca4).
        self.assert_rule(_read(CONTRACT_REL), CONTRACT_SUB_PROJECT_CATEGORY, CONTRACT_REL)


# ---------------------------------------------------- \u00a7S6 \u2014 every skill ----

#: The skill sources: every Markdown file under ``skills-src/`` but the memory templates.
SKILL_FILES = sorted(p for p in (REPO_ROOT / "skills-src").rglob("*.md")
                     if "memory-templates" not in p.parts)
#: A unit about the knowledge store.
KNOWLEDGE_STORE_UNIT = r"knowledge_category|\bknowledge[- ]store\b"
#: lean-ctx named, the product or a tool.
LEAN_CTX_NAMED = r"lean[-_]ctx|(?<![\w])ctx_[a-z_]+"


class SkillsNameTheKnowledgeStoreCapabilityTest(unittest.TestCase):
    """\u00a7S6 "so does every other skill: `model-b` names the installation's
    knowledge-store tool, not lean-ctx" (finding F7): no skill unit that
    speaks of the knowledge store or ``KNOWLEDGE_CATEGORY`` names lean-ctx."""

    def test_no_skill_names_lean_ctx_where_it_speaks_of_the_knowledge_store(self):
        self.assertTrue(SKILL_FILES)
        found = [f"{p.relative_to(REPO_ROOT)}: {u[:160]}"
                 for p in SKILL_FILES for u in rule_units(read_text(p))
                 if re.search(KNOWLEDGE_STORE_UNIT, u) and re.search(LEAN_CTX_NAMED, u)]
        self.assertEqual(found, [], "DN \u00a7D18: name the knowledge-store capability")

    def test_the_detector_bites(self):
        for bad in ("- `KNOWLEDGE_CATEGORY` (written when lean-ctx is present)\n",
                    "- keep facts in the knowledge store via `ctx_knowledge`\n"):
            with self.subTest(bad=bad):
                self.assertTrue(re.search(KNOWLEDGE_STORE_UNIT, rule_units(bad)[0])
                                and re.search(LEAN_CTX_NAMED, rule_units(bad)[0]))
        good = "- `KNOWLEDGE_CATEGORY` (written when the knowledge-store tool is present)\n"
        self.assertIsNone(re.search(LEAN_CTX_NAMED, rule_units(good)[0]))


#: Crucible's imported bundles \u2014 byte-faithful to Crucible, so not Model B's to word.
IMPORTED_BUNDLES = frozenset(IMPORTED_BUNDLE_NAMES)
#: lean-ctx named as a TOOL: a tool name or CLI form (:data:`LEAN_CTX_TOOL_RE`), lean-ctx's
#: tools or its reads/shell/search, a compound (``lean-ctx-indexed``), or lean-ctx as the
#: instrument of an action (``with``/``via``/``through``/``using``/``use`` lean-ctx). The
#: product merely named ("where lean-ctx is installed") and a capability are not tools.
LEAN_CTX_AS_TOOL_RE = re.compile(
    LEAN_CTX_TOOL_RE.pattern
    + r"|\blean-ctx(?:'s)?\s+(?:tools?|reads?|shell|search|cache|index)\b"
    + r"|\blean-ctx-[a-z]"
    + r"|\b(?:with|via|through|using|use)\s+(?:the\s+)?lean-ctx\b",
    re.IGNORECASE,
)


def model_b_skill_files() -> list:
    """Every Markdown file of every Model B-owned skill bundle: a ``skills-src/<name>/``
    carrying a ``SKILL.md`` that is not one of Crucible's imported bundles."""
    root = REPO_ROOT / "skills-src"
    bundles = [d for d in sorted(root.iterdir())
               if (d / "SKILL.md").is_file() and d.name not in IMPORTED_BUNDLES]
    return [p for d in bundles for p in sorted(d.rglob("*.md"))]


def lean_ctx_as_tool_findings(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if LEAN_CTX_AS_TOOL_RE.search(ln)]


class ModelBSkillsNameNoLeanCtxToolTest(unittest.TestCase):
    """\u00a7S6 AC "No skill names lean-ctx as a tool" (PRD D10, DN \u00a7D18): every Model
    B-owned skill names the capability \u2014 the project's cached reads, compressed shell,
    knowledge store \u2014 and the project's ``AGENTS.md`` (the lean-ctx pointer ``init``
    scaffolds) is where the tool is named. Crucible's imported bundles are out of scope."""

    def test_the_bundles_checked_are_model_bs_own(self):
        names = {p.relative_to(REPO_ROOT / "skills-src").parts[0] for p in model_b_skill_files()}
        for owned in ("model-b", "code-health", "bootstrap", "shutdown", "crucible"):
            self.assertIn(owned, names)
        self.assertEqual(sorted(names & IMPORTED_BUNDLES), [])

    def test_no_model_b_skill_names_lean_ctx_as_a_tool(self):
        found = [f"{p.relative_to(REPO_ROOT)}: {ln[:160]}"
                 for p in model_b_skill_files() for ln in lean_ctx_as_tool_findings(read_text(p))]
        self.assertEqual(found, [], "DN \u00a7D18: a skill names the capability, never lean-ctx "
                                    "as a tool")

    def test_the_detector_bites_on_tools_and_spares_the_product_and_capabilities(self):
        for bad in ("- **Prefer the lean-ctx tools inside the project** (cached reads)",
                    "Dataset (all git-committed, lean-ctx-indexed, RAG-able):",
                    "   Mainline verifies by hand, e.g. with lean-ctx, then records).",
                    "  cleared; macro-generated references are invisible \u2014 verify with lean-ctx",
                    "use lean-ctx's compressed shell", "via lean-ctx", "lean-ctx's reads",
                    "call `ctx_read`", "use the lean_ctx tool", "run `lean-ctx knowledge list`"):
            with self.subTest(bad=bad):
                self.assertEqual(len(lean_ctx_as_tool_findings(bad)), 1)
        for good in ("where lean-ctx is installed", "the project's knowledge store",
                     "the project's cached reads and compressed shell, where its AGENTS.md "
                     "names them", "verify by reading the reference sites"):
            with self.subTest(good=good):
                self.assertEqual(lean_ctx_as_tool_findings(good), [])


# ------------------------------------------------- detectors, synthetic text ----

GOOD_MEMORY = """\
- **GC principle:** memory holds ONLY what the repo doesn't yet track. Delete it once tracked.
- **No unilateral writes:** raise the learning to the coordinator (Mainline).
- **Where to keep it.** Where the project's `.env` carries `KNOWLEDGE_CATEGORY`, execution
  knowledge is kept in the project's knowledge store under that category, one short fact per
  item, with a stable kebab-case key. The same key supersedes a fact.
- **What goes there.** Only execution knowledge: never an orchestrator rule, an agent
  definition, a ruling that belongs in the PRD or a DN, or a project fact that belongs in `.env`
  or `AGENTS.md`.
- **Who writes.** Only Mainline or Solo writes facts; a Track reads them, and raises new ones to
  Mainline.
- **The GC and no-unilateral-write rules still apply.**
- **Without the key,** nothing changes.
"""

GOOD_BOOTSTRAP = """\
## Step 0.6 — Load the execution knowledge

Where `KNOWLEDGE_CATEGORY` is set:
- restore the category's archived facts;
- list that category;
- report that the knowledge store is in use and how many facts it loaded.

It never uses a query recall and never loads the automatic rooms.
"""

GOOD_CONTRACT = """\
## Knowledge verbs Model B relies on

Model B relies on four verbs:
- remember a fact;
- list a category;
- restore a category's archived facts;
- remove a fact.

## Setup

The installer records the lean-ctx verdict; then `init` writes `KNOWLEDGE_CATEGORY` and the
AGENTS.md pointer.

## Pitfalls

- A query recall is not a full listing.
- Facts get archived silently; restoring the category brings them back.
- `restore` ignores `dry_run`.
- The CLI's project does not follow the working directory.
- The store holds lean-ctx's automatic captures (the `auto:*` and `code_health` rooms).

A monorepo's sub-projects derive the same category as the root when they share its token.
"""


class RuleDetectorTest(unittest.TestCase):
    """The unit reader and every rule, proven both ways on synthetic text."""

    def test_a_rule_split_across_two_bullets_is_not_satisfied(self):
        split = "- Only Mainline or Solo writes facts.\n- A Track reads them, and raises new ones to Mainline.\n"
        self.assertEqual(satisfying_units(split, MEMORY_WHO), [])
        joined = "- Only Mainline or Solo writes facts; a Track reads them, and raises new ones to Mainline.\n"
        self.assertEqual(len(satisfying_units(joined, MEMORY_WHO)), 1)

    def test_nested_items_and_lazy_continuations_belong_to_their_parent_bullet(self):
        text = ("- Only Mainline or Solo writes facts;\n  - a Track reads them,\nand raises new ones "
                "to Mainline.\n- Unrelated.\n")
        self.assertEqual(len(satisfying_units(text, MEMORY_WHO)), 1)

    def test_a_heading_or_a_blank_line_ends_a_unit(self):
        for sep in ("\n## Next\n", "\n\n"):
            with self.subTest(sep=sep):
                text = f"Only Mainline or Solo writes facts;{sep}a Track reads them, and raises new ones to Mainline.\n"
                self.assertEqual(satisfying_units(text, MEMORY_WHO), [])

    def test_a_thematic_break_ends_a_unit(self):
        text = "Only Mainline or Solo writes facts;\n---\na Track reads them, and raises new ones to Mainline.\n"
        self.assertEqual(satisfying_units(text, MEMORY_WHO), [])

    def test_fenced_code_is_not_a_unit(self):
        text = "```\nOnly Mainline or Solo writes facts; a Track reads them and raises it to Mainline.\n```\n"
        self.assertEqual(satisfying_units(text, MEMORY_WHO), [])

    def test_a_lead_in_joins_its_list_only_when_asked_and_only_when_attached(self):
        self.assertEqual(satisfying_units(GOOD_BOOTSTRAP, BOOTSTRAP_RESTORE_THEN_LIST), [])
        self.assertEqual(
            len(satisfying_units(GOOD_BOOTSTRAP, BOOTSTRAP_RESTORE_THEN_LIST, lead_in=True)), 1)
        detached = GOOD_BOOTSTRAP.replace("is set:\n", "is set:\n\n")
        self.assertEqual(satisfying_units(detached, BOOTSTRAP_RESTORE_THEN_LIST, lead_in=True), [])

    def test_the_spec_worded_memory_section_satisfies_every_memory_rule(self):
        for rule in (MEMORY_WHERE, MEMORY_WHAT, MEMORY_WHO, MEMORY_GC_STILL_APPLIES,
                     MEMORY_GC_PRINCIPLE, MEMORY_NO_UNILATERAL, MEMORY_WITHOUT_KEY):
            with self.subTest(rule=rule[0]):
                self.assertTrue(satisfying_units(GOOD_MEMORY, rule), missing_report(GOOD_MEMORY, rule))
        self.assertEqual(affirmed_findings(GOOD_MEMORY, TRACK_WRITES), [])
        self.assertEqual(lean_ctx_tool_findings(GOOD_MEMORY), [])
        self.assertIn(KEY, key_names_named(COMMON_REL, GOOD_MEMORY))

    def test_each_memory_rule_bites_when_its_phrase_is_changed(self):
        mutations = {
            "same key": (MEMORY_WHERE, "The same key supersedes a fact.", "Keys are free-form."),
            "kebab": (MEMORY_WHERE, "stable kebab-case key", "stable key"),
            "condition": (MEMORY_WHERE, "Where the project's `.env` carries `KNOWLEDGE_CATEGORY`, e",
                          "E"),
            "what": (MEMORY_WHAT, "never an orchestrator rule, ", ""),
            "who": (MEMORY_WHO, "Only Mainline or Solo writes", "Any orchestrator writes"),
            "gc": (MEMORY_GC_STILL_APPLIES, "still apply", "are retired"),
            "without": (MEMORY_WITHOUT_KEY, "nothing changes", "ask the user"),
        }
        for name, (rule, old, new) in mutations.items():
            with self.subTest(mutation=name):
                self.assertIn(old, GOOD_MEMORY)
                self.assertEqual(satisfying_units(GOOD_MEMORY.replace(old, new), rule), [])

    def test_a_track_writing_facts_is_a_finding_unless_negated(self):
        self.assertEqual(affirmed_findings("- A Track writes facts to the store.\n", TRACK_WRITES),
                         ["a track writes facts to the store."])
        self.assertEqual(affirmed_findings("- A Track never writes facts.\n", TRACK_WRITES), [])

    def test_the_spec_worded_bootstrap_step_satisfies_every_bootstrap_rule(self):
        for rule, lead_in in ((BOOTSTRAP_RESTORE_THEN_LIST, True), (BOOTSTRAP_REPORT, True),
                              (BOOTSTRAP_NEVER_RECALL, False), (BOOTSTRAP_NEVER_AUTOMATIC, False)):
            with self.subTest(rule=rule[0]):
                self.assertTrue(satisfying_units(GOOD_BOOTSTRAP, rule, lead_in),
                                missing_report(GOOD_BOOTSTRAP, rule, lead_in))
        self.assertEqual(affirmed_findings(GOOD_BOOTSTRAP, RECALL), [])
        self.assertEqual(affirmed_findings(GOOD_BOOTSTRAP, AUTOMATIC_ROOMS), [])
        self.assertIn(KEY, key_names_named(BOOTSTRAP_REL, GOOD_BOOTSTRAP))

    def test_listing_before_restoring_is_not_restore_then_list(self):
        reversed_order = GOOD_BOOTSTRAP.replace(
            "- restore the category's archived facts;\n- list that category;\n",
            "- list that category;\n- restore the category's archived facts;\n")
        self.assertEqual(
            satisfying_units(reversed_order, BOOTSTRAP_RESTORE_THEN_LIST, lead_in=True), [])

    def test_an_affirmed_recall_or_automatic_room_load_is_a_finding(self):
        text = "- Recall the category with a query.\n- Load the automatic rooms too.\n"
        self.assertEqual(len(affirmed_findings(text, RECALL)), 1)
        self.assertEqual(len(affirmed_findings(text, AUTOMATIC_ROOMS)), 1)
        self.assertEqual(satisfying_units(text, BOOTSTRAP_NEVER_RECALL), [])

    def test_a_shutdown_knowledge_step_is_a_finding(self):
        step = "4. Remember the session's facts in the knowledge store.\n"
        self.assertEqual(len(affirmed_findings(step, KNOWLEDGE_STEP)), 1)
        self.assertEqual(affirmed_findings("- Shutdown takes no knowledge store step.\n",
                                           KNOWLEDGE_STEP), [])

    def test_the_tool_detector_bites_on_tools_and_spares_capabilities(self):
        for bad in ("call `ctx_knowledge` with action=list", "use the lean_ctx tool",
                    "mcp__lean-ctx__ctx_knowledge", "run `lean-ctx knowledge list`"):
            with self.subTest(bad=bad):
                self.assertEqual(len(lean_ctx_tool_findings(bad)), 1)
        for good in ("the project's knowledge store", "the session's knowledge capability",
                     "where lean-ctx is installed", "KNOWLEDGE_CATEGORY"):
            with self.subTest(good=good):
                self.assertEqual(lean_ctx_tool_findings(good), [])

    def test_the_spec_worded_contract_satisfies_every_contract_rule(self):
        self.assertTrue(satisfying_units(GOOD_CONTRACT, CONTRACT_VERBS, lead_in=True))
        self.assertTrue(satisfying_units(GOOD_CONTRACT, CONTRACT_SETUP, lead_in=True))
        for name, rule in PITFALLS.items():
            with self.subTest(pitfall=name):
                self.assertTrue(satisfying_units(GOOD_CONTRACT, rule),
                                missing_report(GOOD_CONTRACT, rule))
        self.assertTrue(satisfying_units(GOOD_CONTRACT, CONTRACT_SUB_PROJECT_CATEGORY))

    def test_each_contract_rule_bites_when_its_phrase_is_missing(self):
        mutations = {
            "verbs": (CONTRACT_VERBS, True, "- remove a fact.\n", ""),
            "setup order": (CONTRACT_SETUP, True,
                            "The installer records the lean-ctx verdict; then `init` writes",
                            "`init` writes"),
            "recall": (PITFALLS["a query recall is not a full listing"], False,
                       "is not a full listing", "is fast"),
            "archived": (PITFALLS["facts get archived silently"], False, "silently", "sometimes"),
            "dry_run": (PITFALLS["restore ignores dry_run"], False, "ignores", "honours"),
            "cwd": (PITFALLS["the CLI's project does not follow the working directory"], False,
                    "does not follow", "follows"),
            "automatic": (PITFALLS["the store holds lean-ctx's automatic captures"], False,
                          "automatic captures", "facts"),
            "sub-project category": (CONTRACT_SUB_PROJECT_CATEGORY, False,
                                     "the same category as the root", "their own category"),
        }
        for name, (rule, lead_in, old, new) in mutations.items():
            with self.subTest(mutation=name):
                self.assertIn(old, GOOD_CONTRACT)
                self.assertEqual(
                    satisfying_units(GOOD_CONTRACT.replace(old, new), rule, lead_in), [])


if __name__ == "__main__":
    unittest.main()
