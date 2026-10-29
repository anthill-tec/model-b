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

CR-MDB-088 (PRD D5, amended 2026-10-14 and 2026-10-29) — MIGRATED at CR-MDB-088 (§S3–§S6): the
key is unconditional and the store is reconciled automatically.

- §S3 — § "Memory" has no conditional on the key and no "without the key nothing changes". It
  states the one home (a fact about a CR names its id; the store starts empty), a missing key or
  store reported (the category from ``AGENTS.md``, else ask the user once; never a file
  fallback), the reconciliation's three moments and its writes, the one-listing bound, the
  re-confirmation of restored facts (decide, then rewrite the kept restored facts before any
  other write, only then the other writes), what a restore brings back, and the store's limits.
  ``orchestration-mainline.md`` § "Memory stewardship" has a Track raise what it finds to
  Mainline, which keeps it in the knowledge store under its key.
- §S4 — bootstrap Step 0.5 drops the key's "no fallback"; Step 0.6 runs for BOTH roles: Mainline
  or Solo restores (scoped to the category by name, repeated until nothing), then lists, decides,
  re-confirms before any other write, only then makes the other writes, and reports; a Track only
  lists, never restores, writes nothing and raises overtaken facts; a missing key or capability
  is reported and bootstrap continues.
- §S5 — shutdown Step 2B item 4 lists the category and reconciles the facts the run overtook;
  Step 2A item 4's ack names the overtaken facts raised to Mainline; Step 1B skips the
  reconciliation. Shutdown now reads ``KNOWLEDGE_CATEGORY``.
- §S6 — § "Close-out" gains an after-``cr-close`` bullet in "The rest of the close-out".
- §S7 — MIGRATED at CR-MDB-088 (§S7): ``contracts/lean-ctx.md``'s section is titled "Knowledge
  store", with no CR reference. It records five verbs (export joins them), each with its
  ``ctx_knowledge`` form: list is ``recall`` with ``category``, at most the listing limit, with
  ``showing <n>/<total>``; restore is ``store=facts`` and ``query=<category>``, repeated until it
  restores nothing; restore by key is ``store=facts`` and ``query="<category> <key>"``; export is
  the fallback for an incomplete listing. MIGRATED at CR-MDB-088 (§S7, amended at cycle 295's
  VERIFY): restore was ``category=facts``; no restore form names ``category=``, and the listing is
  never "every fact in the category". ``init`` writes the
  key and the pointer whatever the verdict, and "Absent or unknown, neither is written" is gone.
  The five pitfalls stay; each new pitfall is one unit (``NEW_PITFALLS``), citing lean-ctx 3.11.4's
  source: each new pitfall's unit names a source path under ``rust/src/`` and a symbol (amended at
  cycle 295's VERIFY). The project-scoped levers (no trust needed) carry CR-MDB-091's values (PRD D5,
  2026-10-29: ``memory.knowledge.max_facts`` 500, ``autonomy.auto_consolidate = false``), with
  what that does not stop, the project root they apply through (normally the git top level), and
  the user's own raise of the global ``recall_facts_limit``.

How a rule is read: phrase-level, inside ONE unit — a list item together with its nested items,
or a paragraph. An enumeration may also be read as its lead-in paragraph (ending in ``:``)
together with the list attached to it (``lead_in=True``): §S6's bootstrap step and §S7's verbs,
setup path and levers are enumerations. Units are normalised (backticks and ``*`` dropped, whitespace
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
from tests.test_orchestrator_rule_triage import markdown_headings, section_body
from tests.test_project_registry_schema import NOT_REGISTRY_KEYS
from tests.test_skills_handover import IMPORTED_BUNDLE_NAMES

KEY = "KNOWLEDGE_CATEGORY"
COMMON_REL = "skills-src/model-b/references/orchestration-common.md"
MEMORY_HEADING = "Memory"
BOOTSTRAP_REL = "skills-src/bootstrap/SKILL.md"
SHUTDOWN_REL = "skills-src/shutdown/SKILL.md"
MAINLINE_REL = "skills-src/model-b/references/orchestration-mainline.md"
STEWARDSHIP_HEADING = "Memory stewardship"
CLOSE_OUT_HEADING = "Close-out"
CONTRACT_REL = "contracts/lean-ctx.md"

# ------------------------------------------------------------------ rules ----
# Each rule is a tuple of regexes, every one of which must match inside ONE unit (normalised).

#: §S6 "Where to keep it." MIGRATED at CR-MDB-088 (§S3): the ``(where|when|if)…knowledge_category``
#: conditional is gone — it is now a finding (:func:`conditional_key_findings`) — and the one home
#: names the category its ``.env`` names in the key, a CR's id in a fact about it, and an empty
#: start.
MEMORY_WHERE = (
    r"\bexecution knowledge\b",
    r"\bknowledge store\b",
    r"\bcategory\b.{0,40}\.env\b.{0,20}knowledge_category",
    r"\bone (?:short )?fact per (?:item|entry)\b",
    r"\bstable kebab-case key\b",
    r"\bsame key supersedes\b",
    r"\bfact about a cr\b.{0,30}\bnames? its id\b",
    r"\bstore starts empty\b",
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
#: §S6 "Without the key, nothing changes." MIGRATED at CR-MDB-088 (§S3): inverted — no unit of
#: § "Memory" may state it.
MEMORY_WITHOUT_KEY = (
    r"\bwithout (?:the |a |its )?(?:knowledge_category|key)\b",
    r"\bnothing changes\b",
)

#: §S6 bootstrap — restore the archived facts, THEN list that category. MIGRATED at CR-MDB-088
#: (§S4): the ``(where|when|if)…knowledge_category`` conditional is gone (Step 0.6 runs for both
#: roles, whatever the key).
BOOTSTRAP_RESTORE_THEN_LIST = (
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
# MIGRATED at CR-MDB-088 (§S5): ``KNOWLEDGE_STEP`` ("shutdown takes no knowledge step") is retired —
# shutdown now reconciles the facts the run overtook (SHUTDOWN_2B_ITEM_4 below).

# ------------------------------------------- CR-MDB-088 §S3 — § "Memory" ----

#: §S3 "A missing key or store is reported, never worked around."
MEMORY_MISSING = (
    r"knowledge_category",
    r"\.env\b",
    r"\b(?:takes?|taken|reads?)\b[^.;]{0,40}\bfrom\b[^.;]{0,20}\bagents\.md\b",
    r"\breports?\b[^.;]{0,40}\bmissing\b",
    r"\bask(?:s|ed)? the user once\b|\buser is asked once\b",
    r"\bwithout\b[^.;]{0,30}\bknowledge[- ]store capability\b",
    r"\bremediation\b",
    r"\bcapability contract\b",
    r"\bnever falls? back to a file\b|\bno file fallback\b|\bnever\b[^.;]{0,20}\bfile fallback\b",
)
#: §S3 "Reconciled automatically, never on request" — the three moments.
MEMORY_RECONCILE_MOMENTS = (
    r"\breconcil\w*\b.{0,20}\bautomatically\b",
    r"\bnever on request\b",
    r"\bat bootstrap\b.{0,40}\bafter the category is loaded\b",
    r"\bafter every cr-close\b.{0,40}\bnaming the closed cr\b",
    r"\btrack's cr-close\b.{0,60}\bonce mainline confirms\b",
    r"\bat shutdown\b.{0,40}\bthe run overtook\b",
)
#: §S3 "At each moment, Mainline or Solo checks every fact…" — what a reconciliation does.
MEMORY_RECONCILE_ACTIONS = (
    r"\bmainline or solo\b",
    r"\bagainst the (?:board and the repo|repo and the board)\b",
    r"\brewrites?\b.{0,40}\bunder its key\b",
    r"\bremoves?\b.{0,60}\btracks\b",
    r"\breports? what changed\b",
    r"\bnever only flagged\b",
    r"\btracks? raises?\b.{0,40}\bovertaken\b.{0,20}\bto mainline\b",
)
#: §S3 "One listing holds the category" (PRD D5, 2026-10-29).
MEMORY_ONE_LISTING = (
    r"\bkept within\b.{0,30}\bone listing\b",
    r"\blists?\b.{0,10}\bbefore\b.{0,40}\bfirst remember- or remove-class write\b",
    r"\bhow many\b.{0,30}\bof how many\b",
    r"\bfewer than all\b.{0,20}\breport\w*\b",
    r"\brest\b.{0,50}\bexport\b",
    r"\breconcil\w*\b.{0,40}\bdown to the limit\b",
    r"\bmainline or solo\b",
    r"\btracks? reports? it\b",
)
#: §S3 "Restored facts are re-confirmed" (PRD D5, 2026-10-29).
MEMORY_RECONFIRM = (
    r"\bre-?confirm\w*\b",
    r"\brestored facts are\b.{0,60}\bbelow 30% confidence\b",
    r"\brestored by its key\b.{0,30}\brewritten at once\b",
    r"\bfeedback\b.{0,20}\b(?:does not|doesn't|never)\b.{0,10}\bre-?confirm",
)
#: §S3 — the re-confirmation's order, enforced as order inside the one unit.
RECONFIRM_ORDER = (
    ("decide each fact's outcome", r"\bdecide\w*\b.{0,30}\boutcome\b"),
    ("rewrite the kept restored facts before any other write",
     r"\bbefore any other write\b.{0,20}\b(?:re-?confirm\w*|rewrit\w*)\b"),
    ("only then the reconciliation's other writes", r"\bonly then\b.{0,60}\bother writes\b"),
)
#: §S3 "What a restore brings back."
MEMORY_RESTORE_BRINGS_BACK = (
    r"\brestored fact that is not this project's\b.{0,40}\bremoved\b.{0,30}\breported\b",
    r"\b(?:repo or the board|board or the repo) already tracks\b.{0,20}\bremoved again\b"
    r".{0,20}\breported\b",
    r"\bmiss\w*\b.{0,40}\bpruned\b",
    r"\bprevention is the one-listing bound\b|\bone-listing bound\b.{0,30}\bprevent\w*\b",
)
#: §S3 "The store's limits."
MEMORY_LIMITS = (
    r"\bcap is shared with\b.{0,30}\bautomatic captures\b",
    r"\bdecay compounds on every write\b",
    r"\brestore has no dry[ _-]?run\b",
)
#: A store made conditional on the key (a finding): "where/when/if … carries/sets/has
#: KNOWLEDGE_CATEGORY", "where KNOWLEDGE_CATEGORY is set". A negated span ("has no", "lacks") is
#: the missing-key rule, not a condition on the store.
_SAME_CLAUSE = r"(?:[^.;:]|\.(?=env\b))"  # no clause break; the dot of ".env" is not one
CONDITIONAL_KEY_RE = re.compile(
    rf"\b(?:where|when|if)\b{_SAME_CLAUSE}{{0,60}}?\b(?:carries|sets|has|defines)\b"
    rf"{_SAME_CLAUSE}{{0,20}}?knowledge_category"
    rf"|\b(?:where|when|if)\b{_SAME_CLAUSE}{{0,20}}?knowledge_category\b{_SAME_CLAUSE}{{0,20}}?"
    r"\b(?:is set|is present|exists)\b")
_CONDITION_NEGATED = re.compile(r"\b(?:no|not|lacks?|without|missing|never)\b")

#: §S3 — ``orchestration-mainline.md`` § "Memory stewardship".
STEWARDSHIP = (
    r"\btracks? raises?\b.{0,60}\bto mainline\b",
    r"\bkeeps?\b.{0,30}\bin the knowledge store\b",
    r"\bunder (?:their|its) keys?\b",
)
#: §S3 — the file-memory era's wording the stewardship section drops.
FILE_MEMORY_ERA = r"\bcorrect bucket\b|\bdated\b"

# --------------------------------------- CR-MDB-088 §S4 — bootstrap ----

#: §S4.1 — Step 0.5's unit about the key follows the general fallback: the project's
#: ``AGENTS.md`` names the category, else the user is asked once.
STEP_0_5_KEY_FALLBACK = (
    r"knowledge_category",
    r"\bagents\.md\b.{0,40}\bcategory\b|\bcategory\b.{0,40}\bagents\.md\b",
    r"\bask(?:s|ed)? the user once\b|\buser is asked once\b",
)
#: §S4.1 — the retired exception: the key "has no fallback", the step "never asked about".
STEP_0_5_NO_FALLBACK = r"knowledge_category[^.]{0,20}\bhas no fallback\b|\bnever asked about\b"
#: §S4.2 — Mainline or Solo's enumeration (with its lead-in): what it must carry.
BOOTSTRAP_MAINLINE = (
    r"\bmainline or solo\b",
    r"\bbelow 30% confidence\b",
    r"\bhow many facts\b",
    r"\bwhat\b.{0,30}\bchanged\b",
)
#: §S4.2 — Mainline or Solo's enumeration, enforced as order.
BOOTSTRAP_MAINLINE_ORDER = (
    ("restore the archived facts", r"\brestor\w*\b.{0,40}\barchived facts\b"),
    ("then list the category", r"\blists?\b.{0,10}\b(?:that|the) category\b"),
    ("decide each fact's outcome", r"\bdecide\w*\b.{0,30}\boutcome\b"),
    ("re-confirm the kept restored facts before any other write",
     r"\bbefore any other write\b.{0,20}\b(?:re-?confirm\w*|rewrit\w*)\b"),
    ("only then the reconciliation's other writes", r"\bonly then\b.{0,60}\bother writes\b"),
    ("report the facts loaded", r"\breport\w*\b.{0,80}\bhow many facts\b"),
)
#: §S4.2 item 1 — the restore's scope: the category by name, repeated until nothing.
BOOTSTRAP_RESTORE_SCOPE = (
    r"\brestor\w*\b.{0,40}\barchived facts\b",
    r"\bscoped?\b.{0,20}\bcategory\b.{0,5}\bby name\b",
    r"\brepeated until\b.{0,40}\b(?:brings back|restores) nothing\b",
)
#: §S4.2 item 1 — a restored fact that is not this project's is removed and reported.
BOOTSTRAP_FOREIGN_FACT = (r"\bnot this project's\b.{0,40}\bremoved\b.{0,40}\breported\b",)
#: §S4.2 — a Track never restores, only lists, writes nothing, raises overtaken facts.
BOOTSTRAP_TRACK = (
    r"\btracks?\b.{0,10}\bnever restores?\b",
    r"\blists? the category only\b|\bonly lists?\b",
    r"\bno write of its own\b|\bwrites? nothing\b|\bmakes? no writes?\b",
    r"\brais\w*\b.{0,40}\bovertaken\b",
    r"\bmainline\b",
)
#: §S4.2 — a missing key or knowledge-store capability is reported, and bootstrap continues.
BOOTSTRAP_MISSING = (
    r"\bmissing\b.{0,10}\b(?:key|knowledge_category)\b",
    r"\bknowledge[- ]store capability\b",
    r"\breported\b",
    r"\bbootstrap continues\b",
)

# ---------------------------------------- CR-MDB-088 §S5 — shutdown ----

#: §S5.1 — Step 2B item 4: list the category, reconcile the facts the run overtook, name what
#: changed in the report.
SHUTDOWN_2B_ITEM_4 = (
    r"\blists?\b.{0,20}\bcategory\b",
    r"\.env\b",
    r"knowledge_category",
    r"\breconcil\w*\b.{0,30}\bfacts? the run overtook\b",
    r"\breport\b.{0,40}\bnames? what changed\b",
)
#: §S5.2 — Step 2A item 4: the ack names the overtaken facts raised to Mainline; no fact written.
SHUTDOWN_2A_ITEM_4 = (
    r"\back\b.{0,20}\bnames?\b.{0,40}\bovertaken\b",
    r"\braised to mainline\b|\brais\w*\b.{0,30}\bto mainline\b",
    r"\btracks? writes? no facts?\b",
)
#: §S5.3 — Step 1B: the emergency skips the reconciliation.
SHUTDOWN_1B_SKIPS = (
    r"\bno reconciliation\b|\bskip\w*\b.{0,40}\breconcil\w*\b|\breconcil\w*\b.{0,40}\bskip\w*\b"
    r"|\b(?:not|never) reconcil\w*\b",)

# --------------------------------------- CR-MDB-088 §S6 — close-out ----

#: §S6 — the after-``cr-close`` bullet.
AFTER_CR_CLOSE = (
    r"\bafter cr-close\b",
    r"\bmainline or solo\b",
    r"\blists? the category\b",
    r"\breconcil\w*\b.{0,20}\beach fact naming the closed cr\b",
)
#: §S6 — the lead-in of the list the bullet joins.
REST_OF_CLOSE_OUT = "The rest of the close-out:"

#: §S7 — the knowledge verbs. MIGRATED at CR-MDB-088 (§S7): five verbs — export (the fallback
#: for an incomplete listing) joins remember, list a category, restore and remove.
CONTRACT_VERBS = (r"\bremember\b", r"\blist\w*\b.{0,30}\bcategor", r"\brestore\b", r"\bremove\b",
                  r"\bexport\b")
#: §S7 — the setup path: the installer's verdict, then init's key and pointer. MIGRATED at
#: CR-MDB-088 (§S7): ``init`` writes them whatever the verdict.
CONTRACT_SETUP = (
    r"\binstaller\b.*\binit\b",
    r"\bverdicts?\b",
    r"knowledge_category",
    r"\bpointer\b|\bagents\.md\b",
    r"\bwhatever the verdict\b",
)
#: CR-MDB-088 §S7 — the setup sentence the rewrite removes (a finding wherever it is still found).
CONTRACT_SETUP_RETIRED = r"\babsent or unknown, neither is written\b"
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

# ------------------------------- CR-MDB-088 §S7 — the knowledge-store section ----

#: §S7 — the section's title, retitled without the CR reference.
KNOWLEDGE_STORE_HEADING = "Knowledge store"
#: A CR or a § reference in a heading ("(CR-MDB-045 §S7)").
HEADING_CR_REFERENCE_RE = re.compile(r"\bCR-[A-Z]+-\d+|§S\d")
#: §S7 "The verbs" — each verb's ``ctx_knowledge`` form, each in its own item.
#: MIGRATED at CR-MDB-088 (§S7, amended at cycle 295's VERIFY): the restore forms select their
#: store with ``store=facts`` (lean-ctx 3.11.4's restore reads ``store`` and ignores
#: ``category``: ``CtxKnowledgeTool``, rust/src/tools/registered/ctx_knowledge.rs), and the
#: listing names its limit; they named ``category=facts``, and the listing had no limit.
CONTRACT_VERB_FORMS = {
    "list a category is recall with category, at most the listing limit, with showing <n>/<total>": (
        r"\blist a category\b", r"\brecall\b.{0,30}\bcategory\b",
        r"\bat most the listing limit\b", r"showing <n>/<total>"),
    "restore is store=facts and query=<category>, repeated until it restores nothing": (
        r"\brestore\b", r"(?<![\w-])store=facts\b.{0,30}query=<category>",
        r"\brepeated until it restores nothing\b"),
    "restore by key is store=facts and query=\"<category> <key>\"": (
        r"\brestore by key\b", r"\brestore by key\b.{0,30}(?<![\w-])store=facts\b",
        r'query=["“]<category> <key>["”]'),
    "export is the fallback for an incomplete listing": (
        r"\bexport\b", r"\bfallback\b.{0,30}\bincomplete listing\b"),
}
LIST_FORM = ("list a category is recall with category, at most the listing limit, with showing "
             "<n>/<total>")
RESTORE_FORM = "restore is store=facts and query=<category>, repeated until it restores nothing"
RESTORE_BY_KEY_FORM = "restore by key is store=facts and query=\"<category> <key>\""
#: §S7 "The new pitfalls" — each one unit (a list item with its nested items), in §S7's words.
NEW_PITFALLS = {
    "the listing limit": (
        r"\blisting shows at most\b.{0,10}\bmemory\.knowledge\.recall_facts_limit\b",
        r"\(10\)",
        r"\bglobal-only\b",
        r"\bnot settable\b.{0,30}\.lean-ctx\.toml\b",
        r"showing <n>/<total>",
        r"\bonly the listed facts are retrieved\b"),
    "decay on every write": (
        r"\bretrieved or confirmed within the last day does not decay\b",
        r"\bevery other fact decays on every lifecycle run\b",
        r"\bcompounding\b",
        r"\bevery remember and remove runs the lifecycle\b",
        r"\ba restore runs none\b"),
    # MIGRATED at CR-MDB-088 (§S7, amended at cycle 295's VERIFY): the restore selects its store
    # with ``store`` and ignores a ``category`` argument; was "its category argument is the store".
    "restore: the store argument, cross-project reach, the 50-item cap, kept confidence": (
        r"\bselects its store with store\b",
        r"\(default: all four\)",
        r"\bignores a category argument\b",
        r"\bunscoped, it restores every store\b",
        r"\bother projects' archived facts from the shared legacy facts archive\b",
        r"\bat most 50 items, scoped or not\b",
        r"\brepeated until it restores nothing\b",
        r"\bkeeps each fact's archived confidence\b",
        r"\bnext write re-archives a fact below 0\.3\b"),
    "the restore's scope is a substring": (
        r"\bquery is a case-insensitive substring match\b",
        r"\bcategory, key and value\b",
        r"\brestore_facts\b",
        r"\barchive root shared by every unprotected project\b",
        r"\banother project's facts under the same category\b",
        r"\ba category whose name contains it\b",
        r"\bany fact whose key or value mentions it\b",
        r"\bremoves such a fact at reconciliation and reports it\b"),
    "removed facts come back from the archive": (
        r"\bremove deletes only the live fact\b",
        r"\bremove_fact\b",
        r"\bthe archive keeps its copy\b",
        r"\bnext restore brings back a fact removed at reconciliation\b",
        r"\buntil its archive file is pruned\b",
        r"\bremoves it again and reports it\b"),
    "the archive keeps 16 shared files": (
        r"\bkeeps 16 files\b",
        r"\bdefault_max_archive_files\b",
        r"\bshared by every unprotected project\b",
        r"\beach archiving lifecycle run adds one\b",
        r"\bother projects' activity can prune this project's archived facts\b",
        r"\ba restore is best-effort\b",
        r"\bthe one-listing bound is the prevention\b"),
    "re-confirmation, and feedback does not change confidence": (
        r"\bsame-key rewrite re-confirms\b",
        r"\bconfidence goes to the midpoint\b",
        r"\bfeedback does not change confidence\b"),
    "export writes a file and retrieves nothing": (
        r"\bexport\b",
        r"\bwrites a json file of the whole store\b",
        r"\bretrieves nothing\b"),
    "the cap is shared with automatic captures, auto_capture global-only": (
        r"\b200-fact cap is shared with automatic captures\b",
        r"\bauto_capture is global-only\b"),
    "rehydration is a listing's write": (
        r"\bcategory listing that finds no current fact rehydrates at most 3 archived facts\b",
        r"≥ ?0\.6",
        r"\bthrough remember\b",
        r"\brehydrate_from_archives\b",
        r"\ba listing can write\b",
        r"\btrack that only lists makes no write of its own, but its listing may\b"),
}
#: §S7 — the new pitfalls cite lean-ctx 3.11.4's source.
CONTRACT_SOURCE_VERSION = (r"\blean-ctx 3\.11\.4\b", r"\bsource\b")
#: CR-MDB-088 §S7 / AC-S7 (amended at cycle 295's VERIFY): each new pitfall's unit names a
#: lean-ctx source path under ``rust/src/`` and a symbol, as two adjacent code spans (either
#: order: ``(`restore_facts`, `rust/src/tools/ctx_knowledge/restore.rs`)``), or one span
#: ``path::symbol``. Read on the RAW unit, because the symbol is a code span.
_SOURCE_PATH = r"`rust/src/(?:[\w.-]+/)*[\w-]+\.rs"
_SOURCE_SYMBOL = r"[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*"
_CITATION_SEPARATOR = r"[ \t\n,;:]*(?:\b(?:in|at|from)\b[ \t\n]*)?"
SOURCE_CITATION_RE = re.compile(
    rf"`{_SOURCE_SYMBOL}`{_CITATION_SEPARATOR}{_SOURCE_PATH}`"
    rf"|{_SOURCE_PATH}`{_CITATION_SEPARATOR}`{_SOURCE_SYMBOL}`"
    rf"|{_SOURCE_PATH}::{_SOURCE_SYMBOL}`")
#: CR-MDB-088 §S7 / AC-S7 (amended at cycle 295's VERIFY): the wording the section must not carry
#: — a restore form naming ``category=`` (lean-ctx's restore ignores it), the restore's
#: ``category`` argument called the store, and the listing as "every fact in the category" (a
#: listing shows at most the listing limit).
RETIRED_VERB_WORDING = {
    "a restore form names category=": (r"\brestore\b", r"(?<![\w-])category="),
    "its category argument is the store": (r"\bits category argument is the store\b",),
    "every fact in the category": (r"\bevery fact in the category\b",),
}
#: §S7 "The project-scoped levers" (an enumeration, read with its lead-in): no trust needed, and
#: the values CR-MDB-091 sets (PRD D5, 2026-10-29).
CONTRACT_LEVERS = (
    r"\bproject-scoped levers\b",
    r"\bno trust needed\b",
    r"\bcr-mdb-091\b",
    r"\bprd d5\b",
    r"\bmemory\.knowledge\.max_facts\b.{0,20}\b500\b",
    r"\bautonomy\.auto_consolidate\s*=\s*false\b",
)
#: §S7 — what ``auto_consolidate = false`` does not stop.
CONTRACT_NOT_STOPPED = (
    r"\bauto_consolidate\s*=\s*false\b.{0,20}\bdoes not stop\b",
    r"\bconsolidation on mcp shutdown\b",
    r"\bcompaction\b",
    r"\bautomatic captures\b",
)
#: §S7 — the levers apply through the bridge process's resolved project root.
CONTRACT_LEVERS_ROOT = (
    r"\blevers apply through\b.{0,30}\bbridge process's resolved project root\b",
    r"\bnormally the git top level\b",
    r"\bmonorepo's root\b",
)
#: §S7 — a larger category is the user's own raise of the global listing limit.
CONTRACT_LARGER_CATEGORY = (
    r"\buser who wants a larger category\b",
    r"\braises the global recall_facts_limit\b",
    r"\bthemselves\b",
)

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


def rule_units(text: str, lead_in: bool = False, raw: bool = False) -> list[str]:
    """Every unit a rule may be read in, normalised: each list item with its nested items (and
    lazy continuation lines), and each paragraph before a list. With ``lead_in``, a paragraph
    ending in ``:`` together with the list attached to it is one more unit. With ``raw``, the
    same units in the same order, unnormalised (their code spans kept)."""
    normalise = _keep if raw else _normalise
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


def _keep(text: str) -> str:
    return text


_normalise = normalise


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

def order_findings(unit: str, steps: tuple) -> list[str]:
    """The label of each ``(label, pattern)`` step not found in ``unit`` after the step before it
    (empty = every step present, in order)."""
    out, pos = [], 0
    for label, pattern in steps:
        m = re.compile(pattern).search(unit, pos)
        if m is None:
            out.append(label)
        else:
            pos = m.end()
    return out

def ordered_units(text: str, rule: tuple, steps: tuple, lead_in: bool = False) -> list[str]:
    """The units satisfying every regex of ``rule`` and carrying ``steps`` in order."""
    return [u for u in satisfying_units(text, rule, lead_in) if not order_findings(u, steps)]

def order_report(text: str, steps: tuple, lead_in: bool = False) -> str:
    """The unit carrying most steps in order, and the steps it misses, for a failure message."""
    units = rule_units(text, lead_in)
    if not units:
        return "no bullet or paragraph at all"
    best = min(units, key=lambda u: len(order_findings(u, steps)))
    return f"closest unit {best[:240]!r} misses, in order, {order_findings(best, steps)!r}"

def conditional_key_findings(text: str) -> list[str]:
    """Each unit making the knowledge store conditional on ``KNOWLEDGE_CATEGORY`` being present
    (:data:`CONDITIONAL_KEY_RE`, a negated span spared)."""
    return [u for u in rule_units(text)
            if any(not _CONDITION_NEGATED.search(m.group(0))
                   for m in CONDITIONAL_KEY_RE.finditer(u))]

def section_starting(text: str, prefix: str) -> str | None:
    """The body under the first heading whose text starts with ``prefix``, up to the next heading
    of the same or a higher level; ``None`` when there is none."""
    heading = next((h for _, _, h in markdown_headings(text) if h.startswith(prefix)), None)
    return None if heading is None else section_body(text, heading)

def numbered_item_units(region: str, number: int) -> list[str]:
    """The normalised units of ``region`` that are its item ``number.`` (nested items kept)."""
    return [u for u in rule_units(region) if u.startswith(f"{number}. ")]

def rest_of_close_out(close_out: str) -> str:
    """The part of \u00a7 "Close-out" after the "The rest of the close-out:" lead-in (``""`` when the
    lead-in is missing)."""
    _, lead, rest = close_out.partition(REST_OF_CLOSE_OUT)
    return rest if lead else ""

def after_cr_close_units(close_out: str) -> list[str]:
    """The bullets (never numbered steps) of the rest of the close-out that state \u00a7S6's
    after-``cr-close`` reconciliation."""
    return [u for u in satisfying_units(rest_of_close_out(close_out), AFTER_CR_CLOSE)
            if re.match(r"[-*+] ", u)]

def step_0_5_key_units(step: str) -> list[str]:
    """The units of Step 0.5 stating the key's general fallback without naming lean-ctx."""
    return [u for u in satisfying_units(step, STEP_0_5_KEY_FALLBACK)
            if not re.search(LEAN_CTX_NAMED, u)]

def shutdown_parts(text: str) -> dict:
    """Step 2B's graceful item 4, Step 2A's graceful item 4 (normalised units), and Step 1B's body."""
    step_2b = section_starting(text, "Step 2B") or ""
    step_2a = section_starting(text, "Step 2A") or ""
    return {
        "2B4": numbered_item_units(step_2b.partition("**Emergency (Mainline):**")[0], 4),
        "2A4": numbered_item_units(step_2a.partition("**Emergency (1B):**")[0], 4),
        "1B": section_starting(text, "Step 1B") or "",
    }

def _units_satisfying(units: list[str], rule: tuple) -> list[str]:
    return [u for u in units if all(re.search(p, u) for p in rule)]

def knowledge_store_heading_findings(text: str) -> list[str]:
    """CR-MDB-088 §S7: empty when exactly one heading starts with "Knowledge store" and it
    carries no CR or § reference; else what is wrong."""
    headings = [h for _, _, h in markdown_headings(text)
                if h.startswith(KNOWLEDGE_STORE_HEADING)]
    if len(headings) != 1:
        return [f"{len(headings)} headings start with {KNOWLEDGE_STORE_HEADING!r}: {headings!r}"]
    return [h for h in headings if HEADING_CR_REFERENCE_RE.search(h)]

def knowledge_store_section(text: str) -> str:
    """CR-MDB-088 §S7: the body of the section titled "Knowledge store" (its subsections
    kept); an ``AssertionError`` when there is none, so no check passes on an empty body."""
    body = section_starting(text, KNOWLEDGE_STORE_HEADING)
    if body is None:
        raise AssertionError(f"no heading starting {KNOWLEDGE_STORE_HEADING!r}")
    return body

def retired_setup_findings(text: str) -> list[str]:
    """CR-MDB-088 §S7: each unit still saying "Absent or unknown, neither is written"."""
    return [u for u in rule_units(text) if re.search(CONTRACT_SETUP_RETIRED, u)]

def pitfall_citation_findings(section: str) -> list[str]:
    """CR-MDB-088 §S7 / AC-S7 (amended at cycle 295's VERIFY): the name of each new pitfall
    (:data:`NEW_PITFALLS`) whose unit cites no lean-ctx source path under ``rust/src/`` with a
    symbol (:data:`SOURCE_CITATION_RE`) — a pitfall with no unit at all is a finding too."""
    pairs = list(zip(rule_units(section), rule_units(section, raw=True), strict=True))
    out = []
    for name, rule in NEW_PITFALLS.items():
        units = [raw for norm, raw in pairs if all(re.search(p, norm) for p in rule)]
        if not any(SOURCE_CITATION_RE.search(u) for u in units):
            out.append(name)
    return out

def retired_verb_wording_findings(section: str) -> list[str]:
    """CR-MDB-088 §S7 / AC-S7 (amended at cycle 295's VERIFY): the name of each
    :data:`RETIRED_VERB_WORDING` entry some unit of ``section`` still carries."""
    units = rule_units(section)
    return [name for name, rule in RETIRED_VERB_WORDING.items()
            if any(all(re.search(p, u) for p in rule) for u in units)]


def _read(rel: str) -> str:
    return read_text(REPO_ROOT / rel)


def _memory_section() -> str:
    body = section_body(_read(COMMON_REL), MEMORY_HEADING)
    if body is None:
        raise AssertionError(f"{COMMON_REL} has no '## {MEMORY_HEADING}' section")
    return body


def _contract_knowledge_section() -> str:
    return knowledge_store_section(_read(CONTRACT_REL))


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
    goes there, who writes, and that the GC and no-unilateral-write rules still apply \u2014 naming
    the store as a capability, never a tool. MIGRATED at CR-MDB-088 (§S3): the store is
    unconditional \u2014 no unit says nothing changes without the key, and none makes the store
    conditional on it."""

    WHERE = f"{COMMON_REL} § {MEMORY_HEADING}"

    def test_execution_knowledge_has_one_home_the_store_under_the_env_category_one_keyed_fact_per_item(self):
        # MIGRATED at CR-MDB-088 (§S3): was
        # test_with_knowledge_category_execution_knowledge_is_kept_in_the_store_one_keyed_fact_per_item
        # \u2014 MEMORY_WHERE lost its conditional and gained a CR's id and the empty start.
        self.assert_rule(_memory_section(), MEMORY_WHERE, self.WHERE)

    def test_no_unit_makes_the_store_conditional_on_the_key(self):
        # CR-MDB-088 (§S3): "where/when/if \u2026 carries KNOWLEDGE_CATEGORY" is gone.
        self.assertEqual(conditional_key_findings(_memory_section()), [],
                         f"{self.WHERE}: the knowledge store is not conditional on {KEY}")

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

    def test_no_unit_says_nothing_changes_without_the_key(self):
        # MIGRATED at CR-MDB-088 (§S3): was test_without_the_key_nothing_changes \u2014 inverted.
        self.assertEqual(satisfying_units(_memory_section(), MEMORY_WITHOUT_KEY), [],
                         f"{self.WHERE}: says nothing changes without the key")

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

    def test_it_restores_the_archived_facts_then_lists_the_category(self):
        # MIGRATED at CR-MDB-088 (§S4): was
        # test_where_the_key_is_set_it_restores_the_archived_facts_then_lists_the_category \u2014
        # BOOTSTRAP_RESTORE_THEN_LIST lost its conditional.
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

    def test_shutdown_reads_knowledge_category_as_a_schema_declared_key_and_names_no_lean_ctx_tool(self):
        # MIGRATED at CR-MDB-088 (§S5): was test_shutdown_needs_no_knowledge_step — inverted:
        # shutdown now reconciles the facts the run overtook, so it reads KNOWLEDGE_CATEGORY by
        # name (which makes it one of the key's readers, §S1.1), still naming no lean-ctx tool.
        text = _read(SHUTDOWN_REL)
        self.assertIn(KEY, key_names_named(SHUTDOWN_REL, text),
                      f"{SHUTDOWN_REL}: reads {KEY} by name (§S5)")
        self.assertEqual(lean_ctx_tool_findings(text), [],
                         f"{SHUTDOWN_REL}: names a lean-ctx tool (DN §D18)")


# ---------------------------------------------------------- §S7 — contract ----

# --------------------------------- CR-MDB-088 \u00a7S3 \u2014 \u00a7 "Memory", the new rules ----

class MemoryReconciledStoreRulesTest(_RuleAssertions):
    """CR-MDB-088 \u00a7S3 / AC-S3: \u00a7 "Memory" states each new rule in one unit \u2014 a missing key or
    store reported, the reconciliation's moments and writes, the one-listing bound, the
    re-confirmation (in order), what a restore brings back, and the store's limits."""

    WHERE = f"{COMMON_REL} \u00a7 {MEMORY_HEADING}"

    def test_a_missing_key_or_store_is_reported_else_ask_the_user_once_never_a_file_fallback(self):
        self.assert_rule(_memory_section(), MEMORY_MISSING, self.WHERE)

    def test_reconciliation_is_automatic_never_on_request_at_its_three_moments(self):
        self.assert_rule(_memory_section(), MEMORY_RECONCILE_MOMENTS, self.WHERE)

    def test_reconciliation_checks_board_and_repo_rewrites_removes_reports_and_a_track_raises(self):
        self.assert_rule(_memory_section(), MEMORY_RECONCILE_ACTIONS, self.WHERE)

    def test_one_listing_holds_the_category_listed_before_the_first_write(self):
        self.assert_rule(_memory_section(), MEMORY_ONE_LISTING, self.WHERE)

    def test_restored_facts_are_re_confirmed_before_any_other_write_in_order(self):
        memory = _memory_section()
        self.assert_rule(memory, MEMORY_RECONFIRM, self.WHERE)
        self.assertTrue(ordered_units(memory, MEMORY_RECONFIRM, RECONFIRM_ORDER),
                        f"{self.WHERE}: {order_report(memory, RECONFIRM_ORDER)}")

    def test_what_a_restore_brings_back_is_reconciled_and_the_bound_is_the_prevention(self):
        self.assert_rule(_memory_section(), MEMORY_RESTORE_BRINGS_BACK, self.WHERE)

    def test_the_stores_limits_shared_cap_compounding_decay_no_dry_run(self):
        self.assert_rule(_memory_section(), MEMORY_LIMITS, self.WHERE)

    def test_orchestration_common_names_no_lean_ctx_tool(self):
        # Gate (DN \u00a7D18) over the whole changed file.
        self.assertEqual(lean_ctx_tool_findings(_read(COMMON_REL)), [], COMMON_REL)


class MemoryStewardshipKeepsTheStoreTest(unittest.TestCase):
    """CR-MDB-088 \u00a7S3 / AC-S3: ``orchestration-mainline.md`` \u00a7 "Memory stewardship" has a Track
    raise what it finds to Mainline, which keeps it in the knowledge store under its key; the
    file-memory era's "dated, in the correct bucket" is gone."""

    def _section(self) -> str:
        body = section_body(_read(MAINLINE_REL), STEWARDSHIP_HEADING)
        if body is None:
            self.fail(f"{MAINLINE_REL} has no '## {STEWARDSHIP_HEADING}' section")
        return body

    def test_a_track_raises_to_mainline_which_keeps_it_in_the_store_under_its_key(self):
        body = self._section()
        self.assertTrue(satisfying_units(body, STEWARDSHIP),
                        f"{MAINLINE_REL} \u00a7 {STEWARDSHIP_HEADING}: "
                        f"{missing_report(body, STEWARDSHIP)}")

    def test_it_no_longer_says_dated_in_the_correct_bucket(self):
        body = normalise(self._section())
        self.assertIsNone(re.search(FILE_MEMORY_ERA, body),
                          f"{MAINLINE_REL} \u00a7 {STEWARDSHIP_HEADING}: still the file-memory era's "
                          "'dated, in the correct bucket'")

    def test_orchestration_mainline_names_no_lean_ctx_tool(self):
        # Gate (DN \u00a7D18) over the whole changed file.
        self.assertEqual(lean_ctx_tool_findings(_read(MAINLINE_REL)), [], MAINLINE_REL)


# --------------------------------------------- CR-MDB-088 \u00a7S4 \u2014 bootstrap ----

class BootstrapReconcilesAndReconfirmsTest(_RuleAssertions):
    """CR-MDB-088 \u00a7S4 / AC-S4: Step 0.5 drops the key's exception; Step 0.6 runs for both roles \u2014
    Mainline or Solo restores (scoped by name, repeated), then lists, decides, re-confirms before
    any other write, only then writes the rest, and reports; a Track only lists; a missing key or
    capability is reported and bootstrap continues."""

    def _step(self, prefix: str) -> str:
        body = section_starting(_read(BOOTSTRAP_REL), prefix)
        if body is None:
            self.fail(f"{BOOTSTRAP_REL} has no '## {prefix}\u2026' heading")
        return body

    def test_step_0_6_heading_carries_both_roles_and_no_only_where(self):
        heads = [ln for ln in _read(BOOTSTRAP_REL).splitlines() if ln.startswith("## Step 0.6 ")]
        self.assertEqual(len(heads), 1, f"{BOOTSTRAP_REL}: one '## Step 0.6 ' heading")
        self.assertIn("BOTH roles", heads[0])
        self.assertNotIn("only where", heads[0].lower(),
                         f"{BOOTSTRAP_REL}: Step 0.6 is not conditional on {KEY}")

    def test_step_0_6_makes_no_load_conditional_on_the_key(self):
        self.assertEqual(conditional_key_findings(self._step("Step 0.6 ")), [],
                         f"{BOOTSTRAP_REL} Step 0.6: loads whatever the key")

    def test_mainline_or_solo_restores_lists_decides_reconfirms_then_writes_the_rest_and_reports(self):
        step = self._step("Step 0.6 ")
        self.assert_rule(step, BOOTSTRAP_MAINLINE, f"{BOOTSTRAP_REL} Step 0.6", lead_in=True)
        self.assertTrue(ordered_units(step, BOOTSTRAP_MAINLINE, BOOTSTRAP_MAINLINE_ORDER, lead_in=True),
                        f"{BOOTSTRAP_REL} Step 0.6: "
                        f"{order_report(step, BOOTSTRAP_MAINLINE_ORDER, lead_in=True)}")

    def test_the_restore_is_scoped_to_the_category_by_name_and_repeated_until_nothing(self):
        self.assert_rule(self._step("Step 0.6 "), BOOTSTRAP_RESTORE_SCOPE,
                         f"{BOOTSTRAP_REL} Step 0.6")

    def test_a_restored_fact_that_is_not_this_projects_is_removed_and_reported(self):
        self.assert_rule(self._step("Step 0.6 "), BOOTSTRAP_FOREIGN_FACT,
                         f"{BOOTSTRAP_REL} Step 0.6")

    def test_a_track_never_restores_only_lists_writes_nothing_and_raises_overtaken_facts(self):
        step = self._step("Step 0.6 ")
        self.assert_rule(step, BOOTSTRAP_TRACK, f"{BOOTSTRAP_REL} Step 0.6")
        self.assertEqual(affirmed_findings(step, TRACK_WRITES), [],
                         f"{BOOTSTRAP_REL} Step 0.6: a Track never writes facts")

    def test_a_missing_key_or_capability_is_reported_and_bootstrap_continues(self):
        self.assert_rule(self._step("Step 0.6 "), BOOTSTRAP_MISSING, f"{BOOTSTRAP_REL} Step 0.6")

    def test_step_0_5_no_longer_exempts_the_key_from_the_fallback(self):
        step = self._step("Step 0.5 ")
        self.assertEqual(affirmed_findings(step, STEP_0_5_NO_FALLBACK)
                         + [u for u in rule_units(step) if re.search(STEP_0_5_NO_FALLBACK, u)], [],
                         f"{BOOTSTRAP_REL} Step 0.5: {KEY} follows the general fallback")

    def test_step_0_5_takes_the_category_from_the_projects_agents_md_else_asks_once(self):
        step = self._step("Step 0.5 ")
        self.assertTrue(step_0_5_key_units(step),
                        f"{BOOTSTRAP_REL} Step 0.5: no unit naming {KEY}, the category in the "
                        "project's AGENTS.md and asking the user once, without naming lean-ctx; "
                        f"{missing_report(step, STEP_0_5_KEY_FALLBACK)}")


# ---------------------------------------------- CR-MDB-088 \u00a7S5 \u2014 shutdown ----

class ShutdownReconcilesOvertakenFactsTest(unittest.TestCase):
    """CR-MDB-088 \u00a7S5 / AC-S5: Step 2B item 4 lists the category and reconciles each fact the run
    overtook, naming what changed; Step 2A item 4's ack names the overtaken facts raised to
    Mainline, and a Track writes no fact; Step 1B skips the reconciliation."""

    def test_step_2b_item_4_lists_the_category_reconciles_and_reports_what_changed(self):
        units = shutdown_parts(_read(SHUTDOWN_REL))["2B4"]
        self.assertEqual(len(units), 1, f"{SHUTDOWN_REL}: Step 2B has one item 4")
        self.assertEqual(_units_satisfying(units, SHUTDOWN_2B_ITEM_4), units,
                         f"{SHUTDOWN_REL} Step 2B item 4: "
                         f"{missing_report(units[0], SHUTDOWN_2B_ITEM_4)}")

    def test_step_2a_item_4_ack_names_overtaken_facts_raised_and_a_track_writes_no_fact(self):
        text = _read(SHUTDOWN_REL)
        units = shutdown_parts(text)["2A4"]
        self.assertEqual(len(units), 1, f"{SHUTDOWN_REL}: Step 2A's graceful path has one item 4")
        self.assertEqual(_units_satisfying(units, SHUTDOWN_2A_ITEM_4), units,
                         f"{SHUTDOWN_REL} Step 2A item 4: "
                         f"{missing_report(units[0], SHUTDOWN_2A_ITEM_4)}")
        self.assertEqual(affirmed_findings(text, TRACK_WRITES), [],
                         f"{SHUTDOWN_REL}: a Track never writes facts")

    def test_step_1b_says_the_emergency_skips_the_reconciliation(self):
        step = shutdown_parts(_read(SHUTDOWN_REL))["1B"]
        self.assertTrue(step.strip(), f"{SHUTDOWN_REL} has no Step 1B")
        self.assertTrue(satisfying_units(step, SHUTDOWN_1B_SKIPS),
                        f"{SHUTDOWN_REL} Step 1B: says nothing of skipping the reconciliation")


# --------------------------------------------- CR-MDB-088 \u00a7S6 \u2014 close-out ----

class CloseOutReconcilesAfterCrCloseTest(unittest.TestCase):
    """CR-MDB-088 \u00a7S6 / AC-S6: \u00a7 "Close-out" carries, in "The rest of the close-out" list (never a
    numbered step), a bullet: after ``cr-close`` Mainline or Solo lists the category and
    reconciles each fact naming the closed CR."""

    def test_the_rest_of_the_close_out_has_the_after_cr_close_reconciliation_bullet(self):
        close_out = section_body(_read(COMMON_REL), CLOSE_OUT_HEADING)
        if close_out is None:
            self.fail(f"{COMMON_REL} has no '## {CLOSE_OUT_HEADING}' section")
        self.assertTrue(rest_of_close_out(close_out).strip(),
                        f"{COMMON_REL}: \u00a7 Close-out lost '{REST_OF_CLOSE_OUT}'")
        self.assertEqual(len(after_cr_close_units(close_out)), 1,
                         f"{COMMON_REL} \u00a7 Close-out: one bullet after '{REST_OF_CLOSE_OUT}' "
                         "saying after cr-close Mainline or Solo lists the category and "
                         "reconciles each fact naming the closed CR; "
                         f"{missing_report(rest_of_close_out(close_out), AFTER_CR_CLOSE)}")


class LeanCtxContractKnowledgeTest(_RuleAssertions):
    """§S7: ``contracts/lean-ctx.md`` records the knowledge verbs, the setup path and the five
    pitfalls. MIGRATED at CR-MDB-088 (§S7): the section is retitled without its CR reference;
    the verbs are five, each with its ``ctx_knowledge`` form; ``init`` writes the key and the
    pointer whatever the verdict; the new pitfalls and the project-scoped levers are recorded."""

    def test_the_section_is_titled_knowledge_store_without_a_cr_reference(self):
        found = knowledge_store_heading_findings(_read(CONTRACT_REL))
        self.assertEqual(found, [], f"{CONTRACT_REL}: §S7 retitles the section "
                                    f"{KNOWLEDGE_STORE_HEADING!r}, with no CR reference")

    def test_it_records_the_five_knowledge_verbs_model_b_relies_on(self):
        # MIGRATED at CR-MDB-088 (§S7): was test_it_records_the_four_knowledge_verbs_model_b_relies_on
        # — export joins the four.
        self.assert_rule(_read(CONTRACT_REL), CONTRACT_VERBS, CONTRACT_REL, lead_in=True)

    def test_it_records_each_verbs_knowledge_tool_form(self):
        text = _contract_knowledge_section()
        for name, rule in CONTRACT_VERB_FORMS.items():
            with self.subTest(verb=name):
                self.assert_rule(text, rule, f"{CONTRACT_REL} (verb: {name})")

    def test_it_records_the_setup_path_installer_verdict_then_inits_key_and_pointer(self):
        # MIGRATED at CR-MDB-088 (§S7): CONTRACT_SETUP now requires "whatever the verdict".
        self.assert_rule(_read(CONTRACT_REL), CONTRACT_SETUP, CONTRACT_REL, lead_in=True)

    def test_the_absent_or_unknown_sentence_is_gone(self):
        self.assertEqual(retired_setup_findings(_read(CONTRACT_REL)), [],
                         f"{CONTRACT_REL}: §S7 removes \"Absent or unknown, neither is written\"")

    def test_it_records_each_of_the_five_pitfalls(self):
        text = _read(CONTRACT_REL)
        for name, rule in PITFALLS.items():
            with self.subTest(pitfall=name):
                self.assert_rule(text, rule, f"{CONTRACT_REL} ({name})")

    def test_it_notes_that_sub_projects_sharing_the_token_derive_the_roots_category(self):
        # Finding F6 (\u00a7S7, amended at 06a4ca4).
        self.assert_rule(_read(CONTRACT_REL), CONTRACT_SUB_PROJECT_CATEGORY, CONTRACT_REL)

    def test_it_records_each_new_pitfall_in_one_unit(self):
        text = _contract_knowledge_section()
        for name, rule in NEW_PITFALLS.items():
            with self.subTest(pitfall=name):
                self.assert_rule(text, rule, f"{CONTRACT_REL} (new pitfall: {name})")

    def test_the_new_pitfalls_cite_lean_ctx_3_11_4_source(self):
        self.assert_rule(_contract_knowledge_section(), CONTRACT_SOURCE_VERSION, CONTRACT_REL,
                         lead_in=True)

    def test_each_new_pitfall_cites_a_lean_ctx_source_path_and_symbol(self):
        """AC-S7 (amended at cycle 295's VERIFY): each new pitfall's unit names a lean-ctx source
        path under ``rust/src/`` and a symbol, never the lead-in alone."""
        found = pitfall_citation_findings(_contract_knowledge_section())
        self.assertEqual(found, [], f"{CONTRACT_REL}: these new pitfalls cite no lean-ctx source "
                                    f"path under rust/src/ with a symbol: {found!r}")

    def test_no_restore_form_names_category_and_the_listing_names_its_limit(self):
        """AC-S7 (amended at cycle 295's VERIFY): no restore form names ``category=``, the
        restore's ``category`` argument is not called the store, and the listing verb never says
        "every fact in the category"."""
        found = retired_verb_wording_findings(_contract_knowledge_section())
        self.assertEqual(found, [], f"{CONTRACT_REL}: retired wording still carried: {found!r}")

    def test_it_records_the_project_scoped_levers_and_the_values_cr_mdb_091_sets(self):
        self.assert_rule(_contract_knowledge_section(), CONTRACT_LEVERS, CONTRACT_REL,
                         lead_in=True)

    def test_it_records_what_auto_consolidate_false_does_not_stop(self):
        self.assert_rule(_contract_knowledge_section(), CONTRACT_NOT_STOPPED, CONTRACT_REL)

    def test_it_records_the_levers_apply_through_the_project_root_normally_the_git_top_level(self):
        self.assert_rule(_contract_knowledge_section(), CONTRACT_LEVERS_ROOT, CONTRACT_REL)

    def test_it_records_a_larger_category_is_the_users_raise_of_the_global_listing_limit(self):
        self.assert_rule(_contract_knowledge_section(), CONTRACT_LARGER_CATEGORY, CONTRACT_REL)


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

# MIGRATED at CR-MDB-088 (\u00a7S3): GOOD_MEMORY is \u00a7S3's wording \u2014 the one home, unconditional,
# replaces "Where to keep it"; "Without the key, nothing changes" is gone; the new rules are added.
GOOD_MEMORY = """\
- **GC principle:** memory holds ONLY what the repo doesn't yet track. Delete it once tracked.
- **No unilateral writes:** raise the learning to the coordinator (Mainline).
- **The one home.** Execution knowledge is kept in the project's knowledge store, under the
  category its `.env` names in `KNOWLEDGE_CATEGORY`, and nowhere else:
  - one short fact per item, each with a stable kebab-case key;
  - the same key supersedes;
  - a fact about a CR names its id;
  - the store starts empty.
- **A missing key or store is reported, never worked around.**
  - A project whose `.env` lacks `KNOWLEDGE_CATEGORY` takes the category from its `AGENTS.md`
    and reports that the key is missing from `.env`.
  - A project with neither the key in `.env` nor the category in its `AGENTS.md`: ask the user
    once.
  - A session without the knowledge-store capability reports it, with the remediation the
    project's `AGENTS.md` capability contract names.
  - Execution knowledge never falls back to a file.
- **Reconciled automatically, never on request.** There are three moments:
  - at bootstrap, right after the category is loaded;
  - after every `cr-close`, for each fact naming the closed CR. For a Track's `cr-close`, this
    happens once Mainline confirms it;
  - at shutdown, for each fact the run overtook.

  At each moment, Mainline or Solo checks every fact concerned against the board and the repo. It
  rewrites an overtaken fact under its key, removes one the repo or the board now tracks, and
  reports what changed. A fact is never only flagged for the user's approval. A Track raises the
  facts it finds overtaken to Mainline.
- **One listing holds the category** (PRD D5, 2026-10-29).
  - The category is kept within what one listing of it shows. Every load lists it before the
    run's first remember- or remove-class write (a restore runs no lifecycle), because a fact
    listed or confirmed within the last day is the only kind the store keeps from decaying.
  - A listing names how many facts it shows of how many. One that shows fewer than all is
    reported, the rest is read from the store's complete export, and the category is reconciled
    down to the limit by Mainline or Solo; a Track reports it.
- **Restored facts are re-confirmed** (PRD D5, 2026-10-29).
  - Why it is needed: a restore brings a fact back at the confidence it was archived with, often
    below the store's archive threshold, and every remember- or remove-class write archives each
    fact below that threshold again.
  - The restored facts are those the listing (or the export) shows below 30% confidence.
  - So, in order: decide each fact's outcome against the board and the repo; then, before any
    other write, rewrite under its key each restored fact the reconciliation keeps; only then
    make the reconciliation's other writes (removals, other rewrites).
  - When a rewrite leaves another restored fact archived again, that fact is restored by its key
    and rewritten at once.
  - Positive feedback does not re-confirm a fact.
- **What a restore brings back.**
  - The restore matches the category by name, through an archive shared between projects. A
    restored fact that is not this project's is removed at reconciliation and reported.
  - A restored fact the repo or the board already tracks is removed again and reported.
  - A restore can miss facts the store has already pruned; the prevention is the one-listing
    bound.
- **The store's limits.**
  - Its fact cap is shared with the store's automatic captures.
  - Decay compounds on every write.
  - A restore has no dry run.
- **What goes there.** Only execution knowledge: never an orchestrator rule, an agent
  definition, a ruling that belongs in the PRD or a DN, or a project fact that belongs in `.env`
  or `AGENTS.md`.
- **Who writes.** Only Mainline or Solo writes facts; a Track reads them, and raises new ones to
  Mainline.
- **The GC and no-unilateral-write rules still apply.**
"""

# MIGRATED at CR-MDB-088 (§S4): GOOD_BOOTSTRAP is §S4.2's Step 0.6 — both roles, no condition on
# the key; Mainline or Solo's ordered enumeration, a Track's paragraph, the missing key reported.
RESTORE_ITEM = ("1. restore the category's archived facts, scoped to the category by name and\n"
                "   repeated until a restore brings back nothing. The scope is a substring match\n"
                "   through an archive shared between projects, so a restored fact that is not\n"
                "   this project's is removed at reconciliation and reported;\n")
LIST_ITEM = ("2. then list that category (a restore runs no lifecycle, so the listing still comes\n"
             "   before the run's first remember- or remove-class write);\n")
RECONFIRM_ITEM = ("5. then, before any other write, re-confirm each restored fact it keeps by\n"
                  "   rewriting it under its key, restoring by its key and rewriting at once any\n"
                  "   fact a rewrite archives again;\n")
OTHER_WRITES_ITEM = ("6. only then make the reconciliation's other writes (removals, other\n"
                     "   rewrites);\n")
GOOD_BOOTSTRAP = (
    "## Step 0.6 — Load the execution knowledge (BOTH roles)\n\n"
    "The category is the one the project's `.env` names in `KNOWLEDGE_CATEGORY`.\n\n"
    "Mainline or Solo, in order:\n"
    + RESTORE_ITEM + LIST_ITEM
    + "3. when the listing shows fewer facts than the category holds, report it and read the\n"
      "   rest from the store's complete export;\n"
      "4. decide each fact's outcome against the board and the repo (§ \"Memory\"). The restored\n"
      "   facts are those the listing (or the export) shows below 30% confidence;\n"
    + RECONFIRM_ITEM + OTHER_WRITES_ITEM
    + "7. report that the knowledge store is in use, how many facts it loaded, and what the\n"
      "   reconciliation changed. Mainline and Solo report to the user.\n\n"
      "A Track never restores, lists the category only, and makes no write of its own. It\n"
      "reports the count to Mainline in its status, and raises the facts it finds overtaken.\n\n"
      "Load that category and nothing else: never a query recall, and never the store's\n"
      "automatic rooms.\n\n"
      "A missing key or knowledge-store capability is reported (§ \"Memory\"), and bootstrap\n"
      "continues.\n"
)

#: CR-MDB-088 §S4.1 — Step 0.5's fallback paragraph, today's and the spec's.
TODAY_STEP_0_5 = (
    "**Fallback** — a project with no `.env` registry, or a missing key: take the same value from\n"
    "the project's `AGENTS.md`; a value found in neither, ask the user once. `KNOWLEDGE_CATEGORY`\n"
    "has no fallback: without it, Step 0.6 is skipped, never asked about.\n")
GOOD_STEP_0_5 = (
    "**Fallback** — a project with no `.env` registry, or a missing key: take the same value from\n"
    "the project's `AGENTS.md`; a value found in neither, ask the user once. `KNOWLEDGE_CATEGORY`\n"
    "follows it too: the project's `AGENTS.md` names the category, else the user is asked once.\n")

#: CR-MDB-088 §S3 — ``orchestration-mainline.md`` § "Memory stewardship", the spec's and today's.
GOOD_STEWARDSHIP = (
    "- Mainline owns memory. A Track raises the facts and learnings it finds to Mainline, which\n"
    "  keeps them in the knowledge store under their keys (`orchestration-common` § \"Memory\"), so\n"
    "  the store stays single-authored across parallel sessions.\n")
TODAY_STEWARDSHIP = (
    "- Mainline owns memory. Tracks RAISE rules/learnings (request); Mainline (or the user) records\n"
    "  them centrally, dated, in the correct bucket — keeping memory single-authored across\n"
    "  parallel sessions.\n")

#: CR-MDB-088 §S5 — the shutdown skill's three places, the spec's wording.
GOOD_SHUTDOWN = """\
## Step 1 — Classify the shutdown (BOTH roles)

### Step 1B — EMERGENCY (`emergency` flag set)
Host is going down. After closing the active write:
- **Fast-abort** the rest — do NOT attempt a CR merge. No reconciliation: the fast-abort skips it.
- Then the common final step.

## Step 2A — TRACK shutdown

**Graceful (1A):** your session is in the main tree.
1. **Finish the active step.**
2. **Escalate first.**
3. **No dangling work.**
4. **ACK that you are safe to shut down** — to Mainline. The ack names the facts the Track
   found overtaken, raised to Mainline. A Track writes no fact.
5. **LAST — the common final step.**

**Emergency (1B):**
1. Close the active write only.
4. **LAST — the common final step.**

## Step 2B — MAINLINE shutdown

1. **Dispatch the shutdown to ALL active Tracks.**
2. **WAIT for every active Track to ACK.**
3. **No dangling work on the integration tree.**
4. **Report to the USER** — all tracks confirmed down. Before the report, list the category the
   project's `.env` names in `KNOWLEDGE_CATEGORY` (the project's `AGENTS.md` names it
   otherwise), and reconcile each fact the run overtook (`orchestration-common` § "Memory").
   The report to the user names what changed.
5. **LAST — the common final step.**

**Emergency (Mainline):** dispatch the emergency directive to all tracks immediately.
"""

#: CR-MDB-088 §S6 — § "Close-out", the spec's wording.
AFTER_CR_CLOSE_BULLET = ("- **After `cr-close`,** Mainline or Solo lists the category and reconciles\n"
                         "  each fact naming the closed CR (§ \"Memory\").\n")
GOOD_CLOSE_OUT = (
    "The CR's close-out order:\n\n"
    "1. Merge `develop` into the feature branch until behind=0.\n"
    "8. `cr-close`.\n\n"
    "The rest of the close-out:\n\n"
    "- Steps 6 and 8 bracket the merge: after it, `cr-close --commit <merge sha>`.\n"
    + AFTER_CR_CLOSE_BULLET
    + "- **A release-fix CR** follows steps 2–5 and 8.\n")

# MIGRATED at CR-MDB-088 (§S7): GOOD_CONTRACT is §S7's section "Knowledge store" — retitled without the CR
# reference, five verbs with their `ctx_knowledge` forms, the setup path whatever the verdict, the
# five kept pitfalls, the new pitfalls in §S7's words, and the project-scoped levers.
# MIGRATED at CR-MDB-088 (§S7, amended at cycle 295's VERIFY): the restore forms name `store=facts`
# (they named `category=facts`), the restore pitfall says it selects its store with `store` and
# ignores `category` (it said "Its `category` argument is the store"), the listing verb names its
# limit, and each new pitfall cites a lean-ctx source path under `rust/src/` and a symbol.
GOOD_CONTRACT = """\
## Knowledge store

Model B keeps a project's execution knowledge in lean-ctx's knowledge store, under the
category the project's `.env` names in `KNOWLEDGE_CATEGORY`.

### Knowledge verbs Model B relies on

Model B relies on five knowledge verbs, each with its `ctx_knowledge` form:
- remember a fact (`remember`);
- list a category (`recall` + `category`): at most the listing limit, with `showing <n>/<total>`;
- restore (`restore`, `store=facts`, `query=<category>`, repeated until it restores nothing),
  and restore by key (`restore`, `store=facts`, `query="<category> <key>"`);
- remove a fact (`remove`);
- export (`export`), the fallback for an incomplete listing.

### Setup path

The installer records the lean-ctx verdict; then `init` writes `KNOWLEDGE_CATEGORY` and the
AGENTS.md pointer whatever the verdict.

A monorepo's sub-projects derive the same category as the root when they share its token.

### Pitfalls

- A query recall is not a full listing.
- Facts get archived silently; restoring the category brings them back.
- `restore` ignores `dry_run`.
- The CLI's project does not follow the working directory.
- The store holds lean-ctx's automatic captures (the `auto:*` and `code_health` rooms).

The new pitfalls, each citing its lean-ctx 3.11.4 source path and symbol:
- **The listing limit.** A listing shows at most `memory.knowledge.recall_facts_limit` facts (10).
  The key is global-only, not settable in a project's `.lean-ctx.toml`. The listing says
  `showing <n>/<total>`, and only the listed facts are retrieved. Source: `handle_recall`,
  `rust/src/tools/ctx_knowledge/remember.rs`.
- **Decay.** A fact retrieved or confirmed within the last day does not decay. Every other fact
  decays on every lifecycle run, compounding, and every `remember` and `remove` runs the
  lifecycle. A restore runs none. Source: `apply_confidence_decay`,
  `rust/src/core/memory_lifecycle.rs`.
- **Restore.** (`CtxKnowledgeTool`, `rust/src/tools/registered/ctx_knowledge.rs`)
  - It selects its store with `store` (default: all four) and ignores a `category` argument.
  - Unscoped, it restores every store, and other projects' archived facts from the shared legacy
    facts archive.
  - It returns at most 50 items, scoped or not, so it is repeated until it restores nothing.
  - It keeps each fact's archived confidence.
  - The next write re-archives a fact below 0.3.
- **The restore's scope is a substring.** `query` is a case-insensitive substring match over each
  archived fact's category, key and value (`restore_facts`,
  `rust/src/tools/ctx_knowledge/restore.rs`), through the archive root shared by
  every unprotected project. `query=<category>` therefore also restores another project's facts
  under the same category, a category whose name contains it, and any fact whose key or value
  mentions it. Model B removes such a fact at reconciliation and reports it.
- **Removed facts come back.** `remove` deletes only the live fact (`remove_fact`,
  `rust/src/core/knowledge/core.rs`), and the
  archive keeps its copy, so the next restore brings back a fact removed at reconciliation, until
  its archive file is pruned. Model B removes it again and reports it.
- **The archive is bounded and shared.** It keeps 16 files (`DEFAULT_MAX_ARCHIVE_FILES`,
  `rust/src/core/memory_archive.rs`) in the
  root shared by every unprotected project, and each archiving lifecycle run adds one, so other
  projects' activity can prune this project's archived facts. A restore is best-effort; the
  one-listing bound is the prevention.
- **Re-confirmation.** A same-key rewrite re-confirms (the confidence goes to the midpoint).
  `feedback` does not change confidence. Source: `handle_feedback`,
  `rust/src/tools/ctx_knowledge/mod.rs`.
- **Export.** It writes a JSON file of the whole store, and retrieves nothing. Source:
  `handle_export`, `rust/src/tools/ctx_knowledge/mod.rs`.
- **The cap.** The 200-fact cap is shared with automatic captures. `auto_capture` is global-only.
  Source: `KnowledgePolicy`, `rust/src/core/memory_policy.rs`.
- **Rehydration.** A category listing that finds no current fact rehydrates at most 3 archived
  facts at ≥0.6, through `remember` (`rehydrate_from_archives`,
  `rust/src/tools/ctx_knowledge/remember.rs`). So a listing can write: a
  Track that only lists makes no write of its own, but its listing may.

### Project-scoped levers

**The project-scoped levers** (no trust needed), and the values Model B sets through CR-MDB-091
(PRD D5, 2026-10-29: a cap of 500, automatic consolidation off):
- `memory.knowledge.max_facts` raised to 500;
- `autonomy.auto_consolidate = false`.

`auto_consolidate = false` does not stop consolidation on MCP shutdown and on compaction, nor
automatic captures.

The levers apply through the bridge process's resolved project root (normally the git top
level, so a monorepo's root file). A user who wants a larger category raises the global
`recall_facts_limit` themselves.

## Filed requests / gaps (operational findings)

This paragraph is outside the section.
"""
#: CR-MDB-088 §S7 — the section today: titled with its CR reference, and the retired setup
#: sentence.
TODAY_CONTRACT_HEADING_AND_SETUP = (
    "## Knowledge store (CR-MDB-045 §S7)\n\n"
    "### Setup path\n\n"
    "- then `modelb-axi init` reads that verdict. With lean-ctx present it writes\n"
    "  `KNOWLEDGE_CATEGORY` and the pointer. Absent or unknown, neither is written.\n")


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
        # MIGRATED at CR-MDB-088 (\u00a7S4): the lead-in is "Mainline or Solo, in order:".
        detached = GOOD_BOOTSTRAP.replace("in order:\n", "in order:\n\n")
        self.assertNotEqual(detached, GOOD_BOOTSTRAP)
        self.assertEqual(satisfying_units(detached, BOOTSTRAP_RESTORE_THEN_LIST, lead_in=True), [])

    def test_the_spec_worded_memory_section_satisfies_every_memory_rule(self):
        # MIGRATED at CR-MDB-088 (\u00a7S3): MEMORY_WITHOUT_KEY is no longer satisfied, and the new
        # rules are.
        for rule in (MEMORY_WHERE, MEMORY_WHAT, MEMORY_WHO, MEMORY_GC_STILL_APPLIES,
                     MEMORY_GC_PRINCIPLE, MEMORY_NO_UNILATERAL, MEMORY_MISSING,
                     MEMORY_RECONCILE_MOMENTS, MEMORY_RECONCILE_ACTIONS, MEMORY_ONE_LISTING,
                     MEMORY_RECONFIRM, MEMORY_RESTORE_BRINGS_BACK, MEMORY_LIMITS):
            with self.subTest(rule=rule[0]):
                self.assertTrue(satisfying_units(GOOD_MEMORY, rule), missing_report(GOOD_MEMORY, rule))
        self.assertTrue(ordered_units(GOOD_MEMORY, MEMORY_RECONFIRM, RECONFIRM_ORDER),
                        order_report(GOOD_MEMORY, RECONFIRM_ORDER))
        self.assertEqual(satisfying_units(GOOD_MEMORY, MEMORY_WITHOUT_KEY), [])
        self.assertEqual(conditional_key_findings(GOOD_MEMORY), [])
        self.assertEqual(affirmed_findings(GOOD_MEMORY, TRACK_WRITES), [])
        self.assertEqual(lean_ctx_tool_findings(GOOD_MEMORY), [])
        self.assertIn(KEY, key_names_named(COMMON_REL, GOOD_MEMORY))

    def test_each_memory_rule_bites_when_its_phrase_is_changed(self):
        mutations = {
            # MIGRATED at CR-MDB-088 (\u00a7S3): "same key" mutates \u00a7S3's nested item.
            "same key": (MEMORY_WHERE, "the same key supersedes;", "keys are free-form;"),
            "kebab": (MEMORY_WHERE, "stable kebab-case key", "stable key"),
            # MIGRATED at CR-MDB-088 (\u00a7S3): "condition" and "without" retired (the conditional
            # and "nothing changes" are findings now); the one home's new phrases bite instead.
            "env category": (MEMORY_WHERE, "category its `.env` names in", "category named in"),
            "cr id": (MEMORY_WHERE, "a fact about a CR names its id", "a fact is short"),
            "starts empty": (MEMORY_WHERE, "the store starts empty", "the store is seeded"),
            "what": (MEMORY_WHAT, "never an orchestrator rule, ", ""),
            "who": (MEMORY_WHO, "Only Mainline or Solo writes", "Any orchestrator writes"),
            "gc": (MEMORY_GC_STILL_APPLIES, "still apply", "are retired"),
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
        # MIGRATED at CR-MDB-088 (\u00a7S4): the items are \u00a7S4.2's.
        reversed_order = GOOD_BOOTSTRAP.replace(RESTORE_ITEM + LIST_ITEM, LIST_ITEM + RESTORE_ITEM)
        self.assertNotEqual(reversed_order, GOOD_BOOTSTRAP)
        self.assertEqual(
            satisfying_units(reversed_order, BOOTSTRAP_RESTORE_THEN_LIST, lead_in=True), [])

    def test_an_affirmed_recall_or_automatic_room_load_is_a_finding(self):
        text = "- Recall the category with a query.\n- Load the automatic rooms too.\n"
        self.assertEqual(len(affirmed_findings(text, RECALL)), 1)
        self.assertEqual(len(affirmed_findings(text, AUTOMATIC_ROOMS)), 1)
        self.assertEqual(satisfying_units(text, BOOTSTRAP_NEVER_RECALL), [])

    # MIGRATED at CR-MDB-088 (\u00a7S5): test_a_shutdown_knowledge_step_is_a_finding retired with
    # KNOWLEDGE_STEP; the shutdown detectors are proved in ReconciliationDetectorTest.

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
        # MIGRATED at CR-MDB-088 (§S7): §S7's new rules hold on its wording, each in exactly one unit.
        self.assertEqual(knowledge_store_heading_findings(GOOD_CONTRACT), [])
        self.assertEqual(retired_setup_findings(GOOD_CONTRACT), [])
        section = knowledge_store_section(GOOD_CONTRACT)
        rules = {**{f"verb: {k}": (v, False) for k, v in CONTRACT_VERB_FORMS.items()},
                 **{f"pitfall: {k}": (v, False) for k, v in NEW_PITFALLS.items()},
                 "source version": (CONTRACT_SOURCE_VERSION, False),
                 "levers": (CONTRACT_LEVERS, True), "not stopped": (CONTRACT_NOT_STOPPED, False),
                 "levers root": (CONTRACT_LEVERS_ROOT, False),
                 "larger category": (CONTRACT_LARGER_CATEGORY, False)}
        for name, (rule, lead_in) in rules.items():
            with self.subTest(rule=name):
                self.assertEqual(len(satisfying_units(section, rule, lead_in)), 1,
                                 missing_report(section, rule, lead_in))

    def test_each_contract_rule_bites_when_its_phrase_is_missing(self):
        mutations = {
            # MIGRATED at CR-MDB-088 (§S7): the verb items carry their `ctx_knowledge` forms, and
            # dropping export bites too.
            "verbs": (CONTRACT_VERBS, True, "- remove a fact (`remove`);\n", ""),
            "export verb": (CONTRACT_VERBS, True,
                            "- export (`export`), the fallback for an incomplete listing.\n", ""),
            "setup order": (CONTRACT_SETUP, True,
                            "The installer records the lean-ctx verdict; then `init` writes",
                            "`init` writes"),
            # MIGRATED at CR-MDB-088 (§S7): the key and pointer are written whatever the verdict.
            "whatever the verdict": (CONTRACT_SETUP, True, "pointer whatever the verdict.",
                                     "pointer when lean-ctx is present."),
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


class ContractKnowledgeStoreDetectorTest(unittest.TestCase):
    """CR-MDB-088 §S7 / AC-S7: every new contract detector, proved both ways on synthetic text —
    §S7's wording (``GOOD_CONTRACT``) passes, and each phrase changed fails."""

    def _assert_bites(self, rule: tuple, old: str, new: str, lead_in: bool = False):
        self.assertEqual(GOOD_CONTRACT.count(old), 1, f"{old!r} must occur once in GOOD_CONTRACT")
        mutated = knowledge_store_section(GOOD_CONTRACT.replace(old, new))
        self.assertEqual(satisfying_units(mutated, rule, lead_in), [])

    def test_the_heading_detector_passes_the_retitled_section_and_bites_on_a_cr_reference(self):
        self.assertEqual(knowledge_store_heading_findings(GOOD_CONTRACT), [])
        self.assertEqual(knowledge_store_heading_findings(TODAY_CONTRACT_HEADING_AND_SETUP),
                         ["Knowledge store (CR-MDB-045 §S7)"])
        no_section = GOOD_CONTRACT.replace("## Knowledge store\n", "## Memory\n")
        self.assertEqual(len(knowledge_store_heading_findings(no_section)), 1)
        two = GOOD_CONTRACT + "\n## Knowledge store, again\n"
        self.assertEqual(len(knowledge_store_heading_findings(two)), 1)

    def test_the_section_reader_stops_at_the_next_section(self):
        section = knowledge_store_section(GOOD_CONTRACT)
        self.assertIn("auto_consolidate = false", section)
        self.assertNotIn("outside the section", section)
        self.assertNotIn("Filed requests", section)

    def test_the_retired_setup_sentence_is_a_finding_and_the_new_setup_is_not(self):
        self.assertEqual(len(retired_setup_findings(TODAY_CONTRACT_HEADING_AND_SETUP)), 1)
        self.assertEqual(satisfying_units(TODAY_CONTRACT_HEADING_AND_SETUP, CONTRACT_SETUP), [])
        self.assertEqual(retired_setup_findings(GOOD_CONTRACT), [])

    def test_each_verb_form_bites_when_its_phrase_is_changed(self):
        forms = CONTRACT_VERB_FORMS
        mutations = {
            # MIGRATED at CR-MDB-088 (§S7, amended at cycle 295's VERIFY): the forms' keys name
            # `store=facts` and the listing limit; each new phrase bites too.
            "list form": (forms[LIST_FORM], "list a category (`recall` + `category`)",
                          "list a category"),
            "list limit": (forms[LIST_FORM], ": at most the listing limit, with",
                           ": every fact in the category, with"),
            "list showing": (forms[LIST_FORM], "limit, with `showing <n>/<total>`;", "limit;"),
            "restore query": (forms[RESTORE_FORM], "`query=<category>`, repeated", "repeated"),
            "restore repeated": (forms[RESTORE_FORM], ", repeated until it restores nothing),", "),"),
            "restore store": (forms[RESTORE_FORM],
                              "- restore (`restore`, `store=facts`, `query=<category>`",
                              "- restore (`restore`, `category=facts`, `query=<category>`"),
            "restore by key": (forms[RESTORE_BY_KEY_FORM], '`query="<category> <key>"`',
                               "`query=<key>`"),
            "restore by key store": (forms[RESTORE_BY_KEY_FORM],
                                     "(`restore`, `store=facts`, `query=\"<category> <key>\"`)",
                                     "(`restore`, `category=facts`, `query=\"<category> <key>\"`)"),
            "export fallback": (forms["export is the fallback for an incomplete listing"],
                                "the fallback for an incomplete listing", "a backup"),
        }
        for name, (rule, old, new) in mutations.items():
            with self.subTest(mutation=name):
                self._assert_bites(rule, old, new)

    def test_each_new_pitfall_bites_when_its_phrase_is_changed(self):
        p = NEW_PITFALLS
        mutations = {
            "limit key": (p["the listing limit"], "`memory.knowledge.recall_facts_limit` facts",
                          "a few facts"),
            "limit global": (p["the listing limit"], "The key is global-only",
                             "The key is per project"),
            # MIGRATED at CR-MDB-088 (§S7): the listing verb names `showing <n>/<total>` too, so
            # the anchor carries the pitfall's own words.
            "limit showing": (p["the listing limit"], "The listing says\n  `showing <n>/<total>`",
                              "The listing says nothing"),
            "limit retrieved": (p["the listing limit"], "only the listed facts are retrieved",
                                "every fact is retrieved"),
            "decay every write": (p["decay on every write"],
                                  "every `remember` and `remove` runs the\n  lifecycle",
                                  "only consolidation runs the\n  lifecycle"),
            "decay compounding": (p["decay on every write"], ", compounding,", ","),
            "decay restore": (p["decay on every write"], "A restore runs none.",
                              "A restore runs it too."),
            # MIGRATED at CR-MDB-088 (§S7, amended at cycle 295's VERIFY): was "Its `category`
            # argument is the store."
            "restore store argument": (
                p["restore: the store argument, cross-project reach, the 50-item cap, kept "
                  "confidence"],
                "It selects its store with `store` (default: all four) and ignores a `category` "
                "argument.", "It selects its store with `category`."),
            "restore ignores category": (
                p["restore: the store argument, cross-project reach, the 50-item cap, kept "
                  "confidence"], "and ignores a `category` argument.", "and reads `category`."),
            "restore cross-project": (
                p["restore: the store argument, cross-project reach, the 50-item cap, kept "
                  "confidence"], "other projects' archived facts from the shared legacy\n    facts archive",
                "nothing else"),
            "restore 50 cap": (
                p["restore: the store argument, cross-project reach, the 50-item cap, kept "
                  "confidence"], "at most 50 items, scoped or not", "every item"),
            "restore confidence": (
                p["restore: the store argument, cross-project reach, the 50-item cap, kept "
                  "confidence"], "It keeps each fact's archived confidence.",
                "It resets each fact's confidence."),
            "substring": (p["the restore's scope is a substring"],
                          "case-insensitive substring match", "exact match"),
            # MIGRATED at CR-MDB-088 (§S7): the symbol now sits beside its source path.
            "substring symbol": (p["the restore's scope is a substring"], "`restore_facts`,\n  ", ""),
            "substring other project": (p["the restore's scope is a substring"],
                                        "another project's facts\n  under the same category",
                                        "this project's facts"),
            "substring removed": (p["the restore's scope is a substring"],
                                  "Model B removes such a fact at reconciliation and reports it.",
                                  "Model B keeps such a fact."),
            "removed live only": (p["removed facts come back from the archive"],
                                  "`remove` deletes only the live fact", "`remove` deletes the fact"),
            "removed come back": (p["removed facts come back from the archive"],
                                  "the next restore brings back a fact removed at reconciliation",
                                  "the next restore leaves it"),
            "removed again": (p["removed facts come back from the archive"],
                              "Model B removes it again and reports it.", ""),
            "archive 16": (p["the archive keeps 16 shared files"], "It keeps 16 files",
                           "It keeps every file"),
            # MIGRATED at CR-MDB-088 (§S7): the symbol now sits beside its source path.
            "archive symbol": (p["the archive keeps 16 shared files"],
                               "`DEFAULT_MAX_ARCHIVE_FILES`,\n  ", ""),
            "archive prune": (p["the archive keeps 16 shared files"],
                              "other\n  projects' activity can prune this project's archived facts",
                              "nothing\n  else touches them"),
            "archive prevention": (p["the archive keeps 16 shared files"],
                                   "the\n  one-listing bound is the prevention", "nothing\n  prevents it"),
            "midpoint": (p["re-confirmation, and feedback does not change confidence"],
                         "the confidence goes to the midpoint", "the confidence is kept"),
            "feedback": (p["re-confirmation, and feedback does not change confidence"],
                         "`feedback` does not change confidence", "`feedback` re-confirms"),
            "export file": (p["export writes a file and retrieves nothing"],
                            "It writes a JSON file of the whole store", "It lists the store"),
            "export retrieves": (p["export writes a file and retrieves nothing"],
                                 "and retrieves nothing", "and retrieves every fact"),
            "cap shared": (p["the cap is shared with automatic captures, auto_capture global-only"],
                           "The 200-fact cap is shared with automatic captures.",
                           "The 200-fact cap is the project's own."),
            "auto_capture global": (
                p["the cap is shared with automatic captures, auto_capture global-only"],
                "`auto_capture` is global-only.", "`auto_capture` is per project."),
            # MIGRATED at CR-MDB-088 (§S7): the symbol now sits beside its source path.
            "rehydrate symbol": (p["rehydration is a listing's write"],
                                 "`rehydrate_from_archives`,\n  ", ""),
            "rehydrate at most 3": (p["rehydration is a listing's write"], "at most 3 archived",
                                    "every archived"),
            "listing writes": (p["rehydration is a listing's write"], "So a listing can write:",
                               "So a listing is read-only:"),
            "track listing": (p["rehydration is a listing's write"],
                              "makes no write of its own, but its listing may",
                              "makes no write at all"),
        }
        for name, (rule, old, new) in mutations.items():
            with self.subTest(mutation=name):
                self._assert_bites(rule, old, new)

    def test_the_citation_detector_passes_each_cited_pitfall_and_bites_on_a_missing_half(self):
        """AC-S7 (amended at cycle 295's VERIFY): :func:`pitfall_citation_findings`, both ways —
        each pitfall loses its finding only with both its path and its symbol."""
        self.assertEqual(pitfall_citation_findings(knowledge_store_section(GOOD_CONTRACT)), [])
        #: pitfall -> its citation in GOOD_CONTRACT (symbol, path), as written there.
        cited = {
            "the listing limit": ("`handle_recall`,\n  ", "`rust/src/tools/ctx_knowledge/remember.rs`."),
            "decay on every write": ("`apply_confidence_decay`,\n  ", "`rust/src/core/memory_lifecycle.rs`."),
            "restore: the store argument, cross-project reach, the 50-item cap, kept confidence": (
                "`CtxKnowledgeTool`, ", "`rust/src/tools/registered/ctx_knowledge.rs`)"),
            "the restore's scope is a substring": (
                "`restore_facts`,\n  ", "`rust/src/tools/ctx_knowledge/restore.rs`)"),
            "removed facts come back from the archive": (
                "`remove_fact`,\n  ", "`rust/src/core/knowledge/core.rs`)"),
            "the archive keeps 16 shared files": (
                "`DEFAULT_MAX_ARCHIVE_FILES`,\n  ", "`rust/src/core/memory_archive.rs`)"),
            "re-confirmation, and feedback does not change confidence": (
                "`handle_feedback`,\n  ", "`rust/src/tools/ctx_knowledge/mod.rs`.\n- **Export"),
            "export writes a file and retrieves nothing": (
                "`handle_export`, ", "`rust/src/tools/ctx_knowledge/mod.rs`.\n- **The cap"),
            "the cap is shared with automatic captures, auto_capture global-only": (
                "`KnowledgePolicy`, ", "`rust/src/core/memory_policy.rs`."),
            "rehydration is a listing's write": (
                "`rehydrate_from_archives`,\n  ", "`rust/src/tools/ctx_knowledge/remember.rs`). So"),
        }
        self.assertEqual(set(cited), set(NEW_PITFALLS))
        for name, (symbol, path) in cited.items():
            citation = symbol + path
            self.assertEqual(GOOD_CONTRACT.count(citation), 1, f"citation anchor {citation!r}")
            # The pitfall's path moved out of rust/src/: a finding for that pitfall, and only it.
            outside = citation.replace("`rust/src/", "`rust/tests/")
            with self.subTest(pitfall=name, half="path outside rust/src/"):
                self.assertEqual(pitfall_citation_findings(knowledge_store_section(
                    GOOD_CONTRACT.replace(citation, outside))), [name])
            # The path dropped, the symbol kept.
            no_path = symbol.rstrip(",\n ") + path[path.index("`", 1) + 1:]
            with self.subTest(pitfall=name, half="no path"):
                self.assertIn(name, pitfall_citation_findings(knowledge_store_section(
                    GOOD_CONTRACT.replace(citation, no_path))))
            # The symbol dropped, the path kept.
            with self.subTest(pitfall=name, half="no symbol"):
                self.assertIn(name, pitfall_citation_findings(knowledge_store_section(
                    GOOD_CONTRACT.replace(citation, path))))

    def test_the_citation_shape_accepts_either_order_and_rejects_prose_or_a_config_key(self):
        path = "`rust/src/core/memory_archive.rs`"
        for good in (f"(`DEFAULT_MAX_ARCHIVE_FILES`, {path})", f"({path}, `DEFAULT_MAX_ARCHIVE_FILES`)",
                     f"`prune_archives` in {path}", "`rust/src/core/memory_archive.rs::prune`",
                     f"`crate::core::memory_archive::prune`,\n  {path}"):
            with self.subTest(good=good):
                self.assertIsNotNone(SOURCE_CITATION_RE.search(good))
        for bad in (f"{path} and nothing else", "(`DEFAULT_MAX_ARCHIVE_FILES`)",
                    f"`memory.knowledge.max_facts`, {path}", "`src/core/memory_archive.rs`, `prune`",
                    "lean-ctx's source, `prune`", f"`prune`, the archive, {path}"):
            with self.subTest(bad=bad):
                self.assertIsNone(SOURCE_CITATION_RE.search(bad))

    def test_a_pitfall_citing_its_source_only_in_the_lead_in_is_a_finding(self):
        """The lead-in "each citing its lean-ctx 3.11.4 source path and symbol" alone cites
        nothing: a pitfall whose own unit carries no citation is a finding."""
        lead_in = ("The new pitfalls, each citing its lean-ctx 3.11.4 source path and symbol "
                   "(`apply_confidence_decay`, `rust/src/core/memory_lifecycle.rs`):\n")
        bare = GOOD_CONTRACT.replace(
            "The new pitfalls, each citing its lean-ctx 3.11.4 source path and symbol:\n", lead_in
        ).replace(" Source: `apply_confidence_decay`,\n  `rust/src/core/memory_lifecycle.rs`.", "")
        self.assertNotEqual(bare, GOOD_CONTRACT)
        self.assertIn(lead_in, bare)
        self.assertEqual(pitfall_citation_findings(knowledge_store_section(bare)),
                         ["decay on every write"])

    def test_the_retired_verb_wording_detector_passes_the_good_section_and_bites_on_each(self):
        """AC-S7 (amended at cycle 295's VERIFY): :func:`retired_verb_wording_findings`, both
        ways, on §S7's wording and on the wording the contract carries today."""
        self.assertEqual(retired_verb_wording_findings(knowledge_store_section(GOOD_CONTRACT)), [])
        mutations = {
            "a restore form names category=": (
                "- restore (`restore`, `store=facts`, `query=<category>`",
                "- restore (`restore`, `category=facts`, `query=<category>`"),
            "its category argument is the store": (
                "It selects its store with `store` (default: all four) and ignores a `category` "
                "argument.", "Its `category` argument is the store."),
            "every fact in the category": (
                ": at most the listing limit, with `showing <n>/<total>`;",
                " — every fact in the category (bootstrap's load);"),
        }
        for name, (old, new) in mutations.items():
            with self.subTest(wording=name):
                self.assertEqual(GOOD_CONTRACT.count(old), 1, old)
                self.assertEqual(retired_verb_wording_findings(
                    knowledge_store_section(GOOD_CONTRACT.replace(old, new))), [name])
        # A listing's own `category=<name>` is not a restore form.
        listing = "- list a category (`recall`, `category=kb-cat`).\n"
        self.assertEqual(retired_verb_wording_findings(listing), [])
        self.assertEqual(retired_verb_wording_findings(
            "- restore by key (`restore`, `category=facts`, `query=\"kb <key>\"`);\n"),
            ["a restore form names category="])

    def test_a_new_pitfall_split_across_two_bullets_is_not_one_unit(self):
        # MIGRATED at CR-MDB-088 (§S7): the anchor carries the citation's source path.
        old = ("`rust/src/tools/ctx_knowledge/remember.rs`). So a listing can write: a\n"
               "  Track that only lists")
        new = ("`rust/src/tools/ctx_knowledge/remember.rs`).\n- So a listing can write: a\n"
               "  Track that only lists")
        self._assert_bites(NEW_PITFALLS["rehydration is a listing's write"], old, new)

    def test_each_lever_rule_bites_when_its_phrase_is_changed(self):
        mutations = {
            "project-scoped": (CONTRACT_LEVERS, True, "**The project-scoped levers** (no trust needed)",
                               "**The levers** (trust needed)"),
            "cr-mdb-091": (CONTRACT_LEVERS, True, "sets through CR-MDB-091", "sets"),
            "max_facts 500": (CONTRACT_LEVERS, True, "`memory.knowledge.max_facts` raised to 500;",
                              "`memory.knowledge.max_facts` left at 200;"),
            "auto_consolidate false": (CONTRACT_LEVERS, True, "- `autonomy.auto_consolidate = false`.",
                                       "- `autonomy.auto_consolidate = true`."),
            "not stopped": (CONTRACT_NOT_STOPPED, False, "`auto_consolidate = false` does not stop",
                            "`auto_consolidate = false` stops"),
            "mcp shutdown": (CONTRACT_NOT_STOPPED, False, "consolidation on MCP shutdown and on "
                             "compaction", "nothing else"),
            "project root": (CONTRACT_LEVERS_ROOT, False,
                             "through the bridge process's resolved project root",
                             "through the working directory"),
            "git top level": (CONTRACT_LEVERS_ROOT, False, "normally the git top\nlevel",
                              "the sub-project"),
            "larger category": (CONTRACT_LARGER_CATEGORY, False, "raises the global\n"
                                "`recall_facts_limit` themselves", "asks Model B"),
        }
        for name, (rule, lead_in, old, new) in mutations.items():
            with self.subTest(mutation=name):
                self._assert_bites(rule, old, new, lead_in)
        detached = GOOD_CONTRACT.replace("automatic consolidation off):\n",
                                         "automatic consolidation off):\n\n")
        self.assertNotEqual(detached, GOOD_CONTRACT)
        self.assertEqual(satisfying_units(detached, CONTRACT_LEVERS, lead_in=True), [])

    def test_the_source_version_rule_bites_without_3_11_4(self):
        self._assert_bites(CONTRACT_SOURCE_VERSION, "its lean-ctx 3.11.4 source path",
                           "its source path")


class ReconciliationDetectorTest(unittest.TestCase):
    """CR-MDB-088 \u00a7S3\u2013\u00a7S6: every new detector, proved both ways on synthetic text \u2014 the spec's
    wording passes, and each phrase changed (or the order swapped) fails."""

    def test_the_conditional_key_detector_bites_on_a_condition_and_spares_a_missing_key(self):
        for bad in ("- Where the project's `.env` carries `KNOWLEDGE_CATEGORY`, keep facts in the "
                    "knowledge store.\n",
                    "Where the project's `.env` sets `KNOWLEDGE_CATEGORY`, load that category.\n",
                    "- Only where `KNOWLEDGE_CATEGORY` is set, load the category.\n"):
            with self.subTest(bad=bad):
                self.assertEqual(len(conditional_key_findings(bad)), 1)
        for good in ("- If the `.env` has no `KNOWLEDGE_CATEGORY`, take the category from `AGENTS.md`.\n",
                     "- A project whose `.env` lacks `KNOWLEDGE_CATEGORY` reports it.\n",
                     "- Keep it under the category its `.env` names in `KNOWLEDGE_CATEGORY`.\n"):
            with self.subTest(good=good):
                self.assertEqual(conditional_key_findings(good), [])
        self.assertEqual(conditional_key_findings(GOOD_BOOTSTRAP), [])

    def test_each_new_memory_rule_bites_when_its_phrase_is_changed(self):
        mutations = {
            "agents.md": (MEMORY_MISSING, "takes the category from its `AGENTS.md`",
                          "keeps no category"),
            "reported missing": (MEMORY_MISSING, "reports that the key is missing", "carries on"),
            "ask once": (MEMORY_MISSING, "ask the user\n    once", "skip the store"),
            "capability": (MEMORY_MISSING, "the remediation", "no word"),
            "file fallback": (MEMORY_MISSING, "never falls back to a file", "falls back to a file"),
            "never on request": (MEMORY_RECONCILE_MOMENTS, "never on request", "on request"),
            "bootstrap moment": (MEMORY_RECONCILE_MOMENTS, "right after the category is loaded",
                                 "at the end"),
            "cr-close moment": (MEMORY_RECONCILE_MOMENTS, "naming the closed CR", "of the wave"),
            "track cr-close": (MEMORY_RECONCILE_MOMENTS, "once Mainline confirms it", "at once"),
            "shutdown moment": (MEMORY_RECONCILE_MOMENTS, "the run overtook", "it holds"),
            "board and repo": (MEMORY_RECONCILE_ACTIONS, "against the board and the repo",
                               "by eye"),
            "rewrite": (MEMORY_RECONCILE_ACTIONS, "rewrites an overtaken fact under its key",
                        "keeps an overtaken fact"),
            "never flagged": (MEMORY_RECONCILE_ACTIONS, "never only flagged", "flagged"),
            "what changed": (MEMORY_RECONCILE_ACTIONS, "reports what changed", "moves on"),
            "track raises": (MEMORY_RECONCILE_ACTIONS, "A Track raises the\n  facts it finds overtaken",
                             "A Track rewrites the\n  facts it finds overtaken"),
            "one listing": (MEMORY_ONE_LISTING, "kept within what one listing", "grown past what one listing"),
            "listed first": (MEMORY_ONE_LISTING, "lists it before the", "lists it after the"),
            "of how many": (MEMORY_ONE_LISTING, "of how many", ""),
            "export": (MEMORY_ONE_LISTING, "the rest is read from the store's complete export",
                       "the rest is ignored"),
            "down to the limit": (MEMORY_ONE_LISTING, "down to the limit", "later"),
            "track reports": (MEMORY_ONE_LISTING, "a Track reports it", "a Track trims it"),
            "below 30%": (MEMORY_RECONFIRM, "below 30% confidence", "with a low score"),
            "by its key": (MEMORY_RECONFIRM, "restored by its key\n    and rewritten at once",
                           "left archived"),
            "feedback": (MEMORY_RECONFIRM, "Positive feedback does not re-confirm a fact.",
                         "Positive feedback is enough."),
            "not this project's": (MEMORY_RESTORE_BRINGS_BACK,
                                   "is removed at reconciliation and reported", "is kept"),
            "already tracked": (MEMORY_RESTORE_BRINGS_BACK, "removed again and reported", "kept"),
            "pruned": (MEMORY_RESTORE_BRINGS_BACK, "the prevention is the one-listing\n    bound",
                       "nothing prevents it"),
            "shared cap": (MEMORY_LIMITS, "shared with the store's automatic captures", "its own"),
            "decay": (MEMORY_LIMITS, "Decay compounds on every write.", "Decay is slow."),
            "dry run": (MEMORY_LIMITS, "A restore has no dry run.", "A restore is safe."),
        }
        for name, (rule, old, new) in mutations.items():
            with self.subTest(mutation=name):
                self.assertIn(old, GOOD_MEMORY)
                self.assertEqual(satisfying_units(GOOD_MEMORY.replace(old, new), rule), [])

    def test_the_reconfirmation_order_is_enforced(self):
        clause = ("decide each fact's outcome against the board and the repo; then, before any\n"
                  "    other write, rewrite under its key each restored fact the reconciliation keeps; only then\n"
                  "    make the reconciliation's other writes (removals, other rewrites).")
        self.assertIn(clause, GOOD_MEMORY)
        swapped = GOOD_MEMORY.replace(clause, (
            "make the reconciliation's other writes (removals, other rewrites); only then\n"
            "    decide each fact's outcome against the board and the repo; then, before any\n"
            "    other write, rewrite under its key each restored fact the reconciliation keeps."))
        self.assertEqual(ordered_units(swapped, MEMORY_RECONFIRM, RECONFIRM_ORDER), [])
        after = GOOD_MEMORY.replace("then, before any\n    other write, rewrite",
                                    "then, after the\n    other writes, rewrite")
        self.assertEqual(ordered_units(after, MEMORY_RECONFIRM, RECONFIRM_ORDER), [])

    def test_a_reconciliation_split_across_two_bullets_is_not_one_rule(self):
        split = ("- Reconciled automatically, never on request.\n"
                 "- At bootstrap, right after the category is loaded; after every `cr-close`, for "
                 "each fact naming the closed CR; for a Track's `cr-close`, once Mainline confirms "
                 "it; at shutdown, for each fact the run overtook.\n")
        self.assertEqual(satisfying_units(split, MEMORY_RECONCILE_MOMENTS), [])
        joined = split.replace("never on request.\n- At", "never on request: at")
        self.assertEqual(len(satisfying_units(joined, MEMORY_RECONCILE_MOMENTS)), 1)

    def test_the_stewardship_detector_passes_the_spec_and_bites_on_today(self):
        self.assertEqual(len(satisfying_units(GOOD_STEWARDSHIP, STEWARDSHIP)), 1)
        self.assertIsNone(re.search(FILE_MEMORY_ERA, normalise(GOOD_STEWARDSHIP)))
        self.assertEqual(satisfying_units(TODAY_STEWARDSHIP, STEWARDSHIP), [])
        self.assertIsNotNone(re.search(FILE_MEMORY_ERA, normalise(TODAY_STEWARDSHIP)))
        no_key = GOOD_STEWARDSHIP.replace(" under their keys", "")
        self.assertEqual(satisfying_units(no_key, STEWARDSHIP), [])
        self.assertEqual(lean_ctx_tool_findings(GOOD_STEWARDSHIP), [])

    def test_the_spec_worded_bootstrap_step_satisfies_every_new_bootstrap_rule(self):
        self.assertEqual(
            len(ordered_units(GOOD_BOOTSTRAP, BOOTSTRAP_MAINLINE, BOOTSTRAP_MAINLINE_ORDER,
                              lead_in=True)), 1,
            order_report(GOOD_BOOTSTRAP, BOOTSTRAP_MAINLINE_ORDER, lead_in=True))
        for rule in (BOOTSTRAP_RESTORE_SCOPE, BOOTSTRAP_FOREIGN_FACT, BOOTSTRAP_TRACK,
                     BOOTSTRAP_MISSING):
            with self.subTest(rule=rule[0]):
                self.assertTrue(satisfying_units(GOOD_BOOTSTRAP, rule),
                                missing_report(GOOD_BOOTSTRAP, rule))
        self.assertEqual(affirmed_findings(GOOD_BOOTSTRAP, TRACK_WRITES), [])
        self.assertEqual(lean_ctx_tool_findings(GOOD_BOOTSTRAP), [])

    def test_the_bootstrap_order_is_enforced(self):
        cases = {
            "list before restore": GOOD_BOOTSTRAP.replace(RESTORE_ITEM + LIST_ITEM,
                                                          LIST_ITEM + RESTORE_ITEM),
            "other writes before re-confirm": GOOD_BOOTSTRAP.replace(
                RECONFIRM_ITEM + OTHER_WRITES_ITEM, OTHER_WRITES_ITEM + RECONFIRM_ITEM),
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(text, GOOD_BOOTSTRAP)
                self.assertEqual(ordered_units(text, BOOTSTRAP_MAINLINE, BOOTSTRAP_MAINLINE_ORDER,
                                               lead_in=True), [])
        # Without its lead-in joined, no single item carries the whole order.
        self.assertEqual(ordered_units(GOOD_BOOTSTRAP, BOOTSTRAP_MAINLINE, BOOTSTRAP_MAINLINE_ORDER), [])

    def test_each_new_bootstrap_rule_bites_when_its_phrase_is_changed(self):
        mutations = {
            "mainline below 30%": (BOOTSTRAP_MAINLINE, True, "below 30% confidence", "low"),
            "mainline what changed": (BOOTSTRAP_MAINLINE, True,
                                      "and what the\n   reconciliation changed", "and stop\n  "),
            "scope by name": (BOOTSTRAP_RESTORE_SCOPE, False, "scoped to the category by name",
                              "unscoped"),
            "scope repeated": (BOOTSTRAP_RESTORE_SCOPE, False,
                               "repeated until a restore brings back nothing", "run once"),
            "foreign": (BOOTSTRAP_FOREIGN_FACT, False,
                        "is removed at reconciliation and reported", "is kept"),
            "track never restores": (BOOTSTRAP_TRACK, False, "A Track never restores",
                                     "A Track restores"),
            "track only lists": (BOOTSTRAP_TRACK, False, "lists the category only",
                                 "lists the category"),
            "track no write": (BOOTSTRAP_TRACK, False, ", and makes no write of its own", ""),
            "track raises": (BOOTSTRAP_TRACK, False, "raises the facts it finds overtaken",
                             "keeps the rest"),
            "missing continues": (BOOTSTRAP_MISSING, False, "and bootstrap\ncontinues",
                                  "and bootstrap\nstops"),
            "missing capability": (BOOTSTRAP_MISSING, False, "or knowledge-store capability ", ""),
        }
        for name, (rule, lead_in, old, new) in mutations.items():
            with self.subTest(mutation=name):
                self.assertIn(old, GOOD_BOOTSTRAP)
                self.assertEqual(
                    satisfying_units(GOOD_BOOTSTRAP.replace(old, new), rule, lead_in), [])

    def test_the_step_0_5_detectors_pass_the_spec_and_bite_on_today(self):
        self.assertEqual(len(step_0_5_key_units(GOOD_STEP_0_5)), 1)
        self.assertEqual([u for u in rule_units(GOOD_STEP_0_5)
                          if re.search(STEP_0_5_NO_FALLBACK, u)], [])
        self.assertEqual(step_0_5_key_units(TODAY_STEP_0_5), [])
        self.assertEqual(len([u for u in rule_units(TODAY_STEP_0_5)
                              if re.search(STEP_0_5_NO_FALLBACK, u)]), 1)
        lean = GOOD_STEP_0_5.replace("the project's `AGENTS.md` names the category",
                                     "the lean-ctx section of `AGENTS.md` names the category")
        self.assertNotEqual(lean, GOOD_STEP_0_5)
        self.assertEqual(step_0_5_key_units(lean), [], "a unit naming lean-ctx is not accepted")

    def test_the_heading_check_tells_both_roles_from_only_where(self):
        today = "## Step 0.6 \u2014 Load the execution knowledge (BOTH roles, only where `KNOWLEDGE_CATEGORY` is set)"
        good = GOOD_BOOTSTRAP.splitlines()[0]
        self.assertTrue(good.startswith("## Step 0.6 ") and "BOTH roles" in good
                        and "only where" not in good.lower())
        self.assertIn("only where", today.lower())

    def test_the_spec_worded_shutdown_satisfies_every_shutdown_rule(self):
        parts = shutdown_parts(GOOD_SHUTDOWN)
        self.assertEqual(len(parts["2B4"]), 1)
        self.assertEqual(_units_satisfying(parts["2B4"], SHUTDOWN_2B_ITEM_4), parts["2B4"],
                         missing_report(parts["2B4"][0], SHUTDOWN_2B_ITEM_4))
        self.assertEqual(len(parts["2A4"]), 1)
        self.assertEqual(_units_satisfying(parts["2A4"], SHUTDOWN_2A_ITEM_4), parts["2A4"],
                         missing_report(parts["2A4"][0], SHUTDOWN_2A_ITEM_4))
        self.assertTrue(satisfying_units(parts["1B"], SHUTDOWN_1B_SKIPS))
        self.assertIn(KEY, key_names_named(SHUTDOWN_REL, GOOD_SHUTDOWN))
        self.assertEqual(affirmed_findings(GOOD_SHUTDOWN, TRACK_WRITES), [])
        self.assertEqual(lean_ctx_tool_findings(GOOD_SHUTDOWN), [])

    def test_the_shutdown_parts_are_the_graceful_items_not_the_emergency_ones(self):
        parts = shutdown_parts(GOOD_SHUTDOWN)
        self.assertTrue(parts["2A4"][0].startswith("4. ack that you are safe"))
        self.assertTrue(parts["2B4"][0].startswith("4. report to the user"))
        self.assertNotIn("step 2a", normalise(parts["1B"]))

    def test_each_shutdown_rule_bites_when_its_phrase_is_changed(self):
        mutations = {
            "2B list": ("2B4", SHUTDOWN_2B_ITEM_4, "list the category the",
                        "keep the category the"),
            "2B reconcile": ("2B4", SHUTDOWN_2B_ITEM_4, "reconcile each fact the run overtook",
                             "remember the session's facts"),
            "2B what changed": ("2B4", SHUTDOWN_2B_ITEM_4, "names what changed", "names the tracks"),
            "2A ack overtaken": ("2A4", SHUTDOWN_2A_ITEM_4,
                                 "The ack names the facts the Track\n   found overtaken",
                                 "The ack names the CR"),
            "2A raised": ("2A4", SHUTDOWN_2A_ITEM_4, "raised to Mainline", "kept"),
            "2A no fact": ("2A4", SHUTDOWN_2A_ITEM_4, " A Track writes no fact.", ""),
        }
        for name, (part, rule, old, new) in mutations.items():
            with self.subTest(mutation=name):
                self.assertIn(old, GOOD_SHUTDOWN)
                units = shutdown_parts(GOOD_SHUTDOWN.replace(old, new))[part]
                self.assertEqual(_units_satisfying(units, rule), [])
        no_skip = GOOD_SHUTDOWN.replace(" No reconciliation: the fast-abort skips it.", "")
        self.assertNotEqual(no_skip, GOOD_SHUTDOWN)
        self.assertEqual(satisfying_units(shutdown_parts(no_skip)["1B"], SHUTDOWN_1B_SKIPS), [])
        self.assertEqual(satisfying_units("- Reconcile each fact the run overtook.\n",
                                          SHUTDOWN_1B_SKIPS), [])

    def test_the_after_cr_close_detector_passes_the_bullet_and_bites_elsewhere(self):
        self.assertEqual(len(after_cr_close_units(GOOD_CLOSE_OUT)), 1)
        cases = {
            "no bullet": GOOD_CLOSE_OUT.replace(AFTER_CR_CLOSE_BULLET, ""),
            "a numbered step": GOOD_CLOSE_OUT.replace(AFTER_CR_CLOSE_BULLET, "").replace(
                "8. `cr-close`.\n", "8. `cr-close`.\n" + AFTER_CR_CLOSE_BULLET.replace("- ", "9. ", 1)),
            "before the lead-in": AFTER_CR_CLOSE_BULLET + GOOD_CLOSE_OUT.replace(
                AFTER_CR_CLOSE_BULLET, ""),
            "not the closed CR": GOOD_CLOSE_OUT.replace("each fact naming the closed CR",
                                                        "each fact"),
            "no listing": GOOD_CLOSE_OUT.replace("lists the category and ", ""),
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(text, GOOD_CLOSE_OUT)
                self.assertEqual(after_cr_close_units(text), [])


if __name__ == "__main__":
    unittest.main()
