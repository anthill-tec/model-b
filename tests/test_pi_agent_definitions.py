"""RED-phase tests for CR-MDB-025 (Pi agent definitions: neutral schema,
per-harness emitter, rendered per project) -- cycle C1, covering §S1
(neutral definition + per-harness emitter, in the package), §S2 (tool
translation, per role, lean-ctx explicit) and §S3 (frontmatter: only what
the reader reads).

Out of scope THIS cycle (later cycles): §S4 permission blocks, §S5 template
rules, §S6 `init`/`agents` verb and file-ownership, §S7 Model B dog-fooding.
No test below asserts permission: block CONTENT, a template-body rule, the
`agents` CLI verb, `PROJECT_STACKS`, or the real `~/.pi/agents/` tree.

CR-MDB-025 CYCLE C2 AMENDMENT (this cycle, C2 RED, 2026-09-2x): §S4
(permission policy beside the tools) and §S5 (the role templates carry the
rules the live definitions carry) join the covered scope below via three
new test classes -- `PermissionPolicyS4Test`, `TemplateRulesS5Test`,
`ToolNamesRuleS5Test`. §S6/§S7 remain out of scope (no test asserts the
`agents` CLI verb, `PROJECT_STACKS`, file-ownership markers, or the real
`~/.pi/agents/` tree). Written BEFORE §S4/§S5's production code lands: the
20 committed `generator/agents/*.md` files (post-C1 GREEN) carry a `tools:`
line but NO `permission:` key at all, and their bodies still carry the
pre-CR-025 Claude-Code-shaped prose -- `Bash` named repeatedly as the tool
to run the crucible client and git writes, no out-of-repository read rule,
no RED prove-both-ways rule, no RED test-migration rule (measured
2026-09-2x by reading `generator/templates/*.md.tmpl` and one rendered
file per role directly).

Exact wording source for §S5 AC1's three named rules: the CR's own Scope
prose says the templates "gain what was applied by hand to the live
definitions on 2026-09-22/23, so the next render does not erase it" --
that hand-made source is `.pi/agents/python-{red,green,verify,fix}-agent.md`
in THIS repo, dated 2026-09-23. Its wording is measured, not invented: the
out-of-repository read rule's anchor ("Reading outside the repository
(NON-NEGOTIABLE)") is present verbatim in all four hand-made role files;
the prove-both-ways and test-migration rule anchors are present verbatim
only in the hand-made RED file, matching §S5 AC1's RED-only scoping; none
of the three anchors, and zero capitalised `Bash` mentions, appear
anywhere in `generator/templates/*.md.tmpl` today (grepped 2026-09-2x).

Migration (§ Migration AC, THIS cycle's slice -- §S4/§S5 only): re-grepped
all five gap-analysis-named files for `permission`, `Bash` (as a positive
expected-value assertion), `generator`, `.pi/agents`, and `render(`. Zero
matches requiring migration for this slice:
  - tests/test_agent_generator.py -- no `permission`/`Bash` assertions at all.
  - tests/test_installer_assets.py::GeneratorAgentsAssetTest -- its
    byte-identity check treats render()'s output as opaque (no old-shape
    coupling) and its banned-literal set does not include `Bash` or
    `permission`; unaffected by §S4/§S5's changes to that same opaque
    output.
  - tests/test_realhome_supersede.py, tests/test_tooling_adoption.py,
    tests/test_git_chezmoi_skills.py -- zero `generator`/`.pi/agents`/
    `render(` references (confirmed by the same grep C1 already ran for
    the §S1-§S3 slice; nothing new for §S4/§S5 either).
No test anywhere in the suite asserts `Bash` as an EXPECTED (positive)
body value (grepped `assertIn("Bash"` / `assertIn('Bash'` fleet-wide --
zero hits), so removing it from the templates regresses nothing.

Written BEFORE any of §S1-§S3's production code lands:
  - `modelb_axi/agents.py` does not exist yet -- the neutral render + Pi
    emitter (`_emit_pi`, the one name §S1 pins verbatim) have not moved out
    of `generator/build.py`.
  - `generator/stacks/*.toml` still carry the free-text `[frontmatter]`
    blocks this CR retires, not the `[roles.<role>]` tables §S1 AC3 pins
    (tools/thinking/skills/optional model, per §S1's own Scope prose).
  - the 20 committed `generator/agents/*.md` files still carry the retired
    Claude-Code-shaped frontmatter (`model:`, `effort:`, `color:`,
    `maxTurns:`, `skills:`) and, for red/green/fix, carry NO `tools:` line
    at all (verify's is the capitalised `Read, Grep, Glob, Bash` the CR's
    own Context section names as the broken input this fixes).

Internal-surface note: §S1 names exactly one function verbatim -- `_emit_pi`
-- and otherwise describes the module's shape in prose ("renders each stack
x role into a neutral definition -- a plain dict ... and serialises it with
a per-harness emitter"), without pinning the neutral-render function's own
name. Rather than invent and pin that name, every test below drives the
REAL observable interfaces the AC's other bullets already name explicitly:
the committed `generator/agents/*.md` output, `generator/stacks/*.toml`'s
own pinned `[roles.<role>]` shape (tools/thinking/skills/model -- literal
per §S1 AC3), `generator/build.py`'s existing `render()`/`load_stack_params()`
re-export surface (already pinned by `tests/test_installer_assets.py` and
`tests/test_agent_generator.py`, and consistent with §S1's "thin wrapper ...
keep their behaviour" framing), and `modelb_axi/agents.py`'s `_emit_pi`. The
one test exercising §S2 AC1's "unknown intent dropped" behaviour drives the
real `generator/build.py` CLI end to end against an isolated fixture stack
TOML written in the exact `[roles.<role>]` shape §S1 AC3 pins -- never a
hand-built harness that bypasses the real wiring, and never a guess at an
un-pinned internal function name.

Migration (§ Migration AC, this cycle's slice -- §S1-§S3 only): searched all
five gap-analysis-named files. Two needed migration for this slice:
  - tests/test_agent_generator.py::BespokeUntouchedS4Test -- migrated (fixture
    mechanism only, no asserted value changed): its isolated-repo-copy setUp
    depended on build.py never importing a sibling package, without ever
    naming that assumption; §S1 gives build.py exactly that import, so the
    fixture now mirrors the whole modelb_axi/ package into the isolated
    repo root.
  - tests/test_installer_assets.py::GeneratorAgentsAssetTest::
    test_generator_agents_dir_contains_twenty_files_matching_render --
    migrated (strengthened): it already asserted render() output generically
    (opaque params, no old-shape coupling), so no existing assertion needed
    a value change; it is now ALSO pinned against §S3 AC2's banned-literal
    set, taken from the spec, against render()'s own output.
  The other three named files (test_realhome_supersede, test_tooling_adoption,
  test_git_chezmoi_skills) were grepped for `generator`, `.pi/agents`,
  `stacks/`, `frontmatter`, `render(`, `effort`, `maxTurns`, `color:`,
  `skills:`, `model:` and matched NONE of them -- their content is entirely
  about deployed ~/.claude state, the tooling-scripts store, and the
  git-workflow/chezmoi skills, none of it §S1-S3-relevant. No migration for
  this slice; they may need one at a later §S6/§S7 cycle when this repo's
  own `.pi/agents/` and `PROJECT_STACKS` land.

CR-MDB-025 CYCLE C3 AMENDMENT (this cycle, C3 RED): §S6 (`init` renders the
project's agents; `modelb-axi agents` re-render verb; ownership markers;
the installer writes no agents) plus the Migration AC as it applies to §S6
join the covered scope below via the new `*S6Test` classes at the end of
this file. §S7 (Model B dog-fooding, measured at close-out) stays out of
scope -- nothing below asserts against THIS repo's own `.pi/agents/` or
regenerates `generator/agents/*.md`.

CR-MDB-025 CYCLE C3 RED2 AMENDMENT (this round, committed amendment
bcd5cf6, cycle 83): new §S5 AC3 -- "Every rendered definition's First
Actions list has registration with Crucible as item 1, ahead of the AC
cross-check" -- joins the covered scope via `RegisterFirstOrderS5Test`.
Written BEFORE the amendment's production code lands (measured 2026-09-2x
directly from `generator/templates/{red,green}.md.tmpl` and their
`generator/agents/*-{red,green}-agent.md` renders): both templates' First
Actions item 1 is `**AC Cross-Check** (below/above) -- BEFORE/before
Crucible registration.`, with `**Register with Crucible**` as item 2 --
the pre-amendment order the new detector fixture reproduces verbatim.
`fix.md.tmpl` and `verify.md.tmpl` (and their ten rendered fix/verify
files) already open item 1 with `**Register with Crucible**` and pass this
gate already; only the ten red/green files fail it. Migration (this
slice): grepped this whole `tests/` directory for `First Actions`,
`AC Cross-Check` and `Register with Crucible` -- zero matches outside this
file's own new class, so no existing test asserts the pre-amendment order
and none needs migrating.

Written BEFORE any §S6 production code exists (measured 2026-09-2x):
`scaffold.py::_emit_plan` has no `agents` import and no `.pi/agents` write
site at all -- `init` today emits nothing under `.pi/agents/` for any
stack/harness combination; `cli.py` has no `agents` subparser, so
`modelb-axi agents` fails as an unrecognised subcommand (a clean
subprocess-level argparse failure, matching this suite's established
not-yet-existing-subcommand RED shape, e.g. tests/test_installer.py's own
note on AC3/AC8).

Design assumptions this cycle's tests had to fix, in the absence of a
pinned literal (documented, not guessed -- each is the only reading that
keeps ALL of §S6's own AC bullets mutually satisfiable, or mirrors an
established sibling pattern already in this codebase):
  - Ownership marker SYNTAX: the AC pins only that it is "a marker comment
    ... naming the generator and the sha256 of the rest of the file", never
    a literal string. Tested STRUCTURALLY: a `#`-prefixed line inside the
    frontmatter block, containing a bare 64-hex-digit token and the
    substring "modelb" (case-insensitive -- the only generator-name family
    this codebase has: modelb-axi/modelb_axi). A `#`-comment (not a new
    top-level key) is required by the AC's own wording AND is the only
    choice that does not regress the already-GREEN §S3 AC1 frontmatter-
    key-set gate (`FrontmatterKeySetS3Test`, allowed set unchanged this
    cycle).
  - AC1's "byte-identical to what build.py renders" and the Ownership AC's
    per-file marker are BOTH true only if the marker lives inside the ONE
    shared render/emit path §S1 already established (`agents.render()` /
    `_emit_pi()`) -- so every byte-identity assertion below simply calls
    `agents.render(...)` and compares raw bytes, never a hand-built
    expectation, and never assumes the marker is a project-render-only
    post-processing step layered outside that function.
  - Envelope OUTCOME field names: the CR's own prose names the vocabulary
    ("written, unchanged, skipped and unmanaged") but not the exact TOON
    keys. Tested via `_find_path_in_envelope_bucket`, which accepts any
    list-valued envelope field whose KEY contains the keyword substring --
    binds to the vocabulary, not to one hand-picked key spelling.
  - Asset-root resolution for `generator/templates`/`generator/stacks`:
    assumed to follow the SAME `install.toml [install].asset_root` ->
    `default_asset_root()` fallback chain `scaffold._memory_templates_dir`
    already uses for `skills-src/memory-templates` -- the established
    idiom in this same module for exactly this asset-root-resolution
    problem, not a fresh invention.
  - CLI surface: `agents` subcommand, `--stacks` (its own flag, mirroring
    `init`'s), and the EXISTING top-level `--force-managed`/`--modelb-home`
    flags (given BEFORE the subcommand token, exactly as `--yes` already is
    in every `init` invocation in this suite) -- never a new, separately-
    declared `--force-managed` on the `agents` subparser, since one already
    exists globally.

Migration (§ Migration AC, this cycle's slice -- §S6, scaffold/init/CLI/
installer tests included): re-surveyed the five gap-analysis-named files
PLUS tests/test_scaffold.py, tests/test_installer.py and
tests/test_installer_correctness.py for §S6 coupling (`PROJECT_STACKS`,
`.pi/agents`, an exact `.env` key set, an exact target-tree listing, or an
`agents` CLI reference). Zero required migrations -- reasoned per file:
  - tests/test_agent_generator.py, tests/test_installer_assets.py -- their
    generated-content assertions all treat `render()`'s output dynamically
    (byte-compared against a live call, never a hardcoded string), so they
    track whatever §S1's shared render path emits (marker included) with
    no test-file change needed; and neither references `.pi/agents`,
    `PROJECT_STACKS` or the `agents` verb (re-grepped, zero hits).
  - tests/test_realhome_supersede.py, tests/test_tooling_adoption.py,
    tests/test_git_chezmoi_skills.py -- zero `PROJECT_STACKS`/`.pi/agents`/
    `agents_dir`/`modelb-axi agents` references (re-grepped this cycle);
    entirely about deployed ~/.claude state, the tooling-scripts store, and
    the git-workflow/chezmoi skills. No migration.
  - tests/test_scaffold.py -- surveyed every fixture that installs `pi` in
    its harness set or asserts `.env`'s exact key set. None assert an
    exact `.env` key SET (only `.get("KEY")` presence/value checks), so an
    added `PROJECT_STACKS` key regresses nothing there. Two fixtures
    render agents as a side effect and are directly protected instead of
    migrated (their existing assertions never touch `.pi/agents/`'s
    contents, so they need no edit, but a NEW regression-guard test below,
    `InitToleratesStackWithoutAgentTemplateS6Test`, pins the exact
    behaviour `PiWorktreeCarryAndClosedGuardsTest`'s own fixture --
    `--stacks rust,java` -- depends on: `agents.STACKS` has no `java`
    entry (only `quarkus`, distinct from scaffold's own `KNOWN_STACKS`,
    which lists both), so agent rendering must silently skip `java` rather
    than fail `init`, or that pre-existing baseline test regresses).
  - tests/test_installer.py, tests/test_installer_correctness.py -- their
    installer-flow (non-`init`) fixtures never touch `.pi/agents` today
    and §S6 pins the installer must go on writing nothing there (a NEW
    test below, `InstallerWritesNoAgentsS6Test`, pins this as a fresh
    assertion; no existing installer-flow test asserted the opposite, so
    none needed migrating).

Stdlib only: unittest + tomllib + re + shutil + subprocess + sys + tempfile
+ importlib.util + pathlib + hashlib + os, matching the sibling generator
test modules' existing conventions.
"""

import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from modelb_axi import agents as agents_mod

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATOR_DIR = REPO_ROOT / "generator"
TEMPLATES_DIR = GENERATOR_DIR / "templates"
STACKS_DIR = GENERATOR_DIR / "stacks"
AGENTS_DIR = GENERATOR_DIR / "agents"
BUILD_PY = GENERATOR_DIR / "build.py"
AGENTS_MODULE_PATH = REPO_ROOT / "modelb_axi" / "agents.py"

STACKS = ("arduino", "bun", "python", "quarkus", "rust")
ROLES = ("red", "green", "verify", "fix")

# §S2 -- the exact, spec-pinned emitted tool sets (Pi names, lowercase).
WRITE_CAPABLE_TOOLS = (
    "read", "write", "edit", "grep", "find", "ls",
    "ctx_shell", "ctx_read", "ctx_grep", "ctx_glob", "ctx_find", "ctx_ls",
    "ctx_patch", "ctx_edit", "ctx_search", "ctx_tree",
)
READ_ONLY_TOOLS = (
    "read", "grep", "find", "ls",
    "ctx_shell", "ctx_read", "ctx_grep", "ctx_glob", "ctx_find", "ctx_ls",
    "ctx_search", "ctx_tree",
)
FORBIDDEN_FOR_VERIFY = ("write", "edit", "ctx_patch", "ctx_edit")

# §S3 AC1 -- the allowed frontmatter key set (superset; permission is §S4's
# content, out of scope this cycle, but named in the AC's own allowed set).
ALLOWED_FRONTMATTER_KEYS = {"name", "description", "tools", "thinking", "permission", "model"}

# §S3 AC2 -- zero of these literals anywhere under generator/ (templates,
# stacks, rendered output). Word-boundary matched to avoid incidental prose
# hits; "skills:" is checked as a literal substring separately (the colon
# already disambiguates it from ordinary English "skills").
BANNED_LITERAL_RE = re.compile(r"\b(sonnet|inherit|opus|haiku|effort|color|maxTurns)\b")

# §S4 AC2 -- VERIFY's tools: line never admits write/edit (§S2), so its
# permission: block must ALSO state both denies explicitly (belt-and-
# suspenders: the CR's own §S4 prose -- "so the read-only property is
# enforced by both the allowlist and the policy").
VERIFY_DENIED_TOOLS = ("write", "edit")

# §S5 AC1 -- exact anchor phrases, measured from the hand-made 2026-09-23
# live definitions this repo already carries at .pi/agents/python-*-agent.md
# (the CR's own Scope prose: the templates "gain what was applied by hand
# to the live definitions on 2026-09-22/23"). Present verbatim in all four
# hand-made role files (out-of-repo rule) or only the RED one (the other
# two), and absent everywhere under generator/templates/ today.
OUT_OF_REPO_READ_RULE_ANCHOR = "Reading outside the repository (NON-NEGOTIABLE)"
PROVE_BOTH_WAYS_RULE_ANCHOR = "Prove every test BOTH ways before you report (NON-NEGOTIABLE)"
TEST_MIGRATION_RULE_ANCHOR = "Migrating existing tests when the contract changes (NON-NEGOTIABLE)"

# \u00a7S5 AC3 (bcd5cf6 amendment) -- the "## First Actions" heading anchor and
# the phrase that must open item 1: registration with Crucible, ahead of
# the AC cross-check. Measured verbatim from generator/templates/*.md.tmpl
# (all four roles share the identical heading text).
FIRST_ACTIONS_HEADING = "## First Actions (IN THIS ORDER \u2014 NON-NEGOTIABLE)"
REGISTER_FIRST_ANCHOR = "Register with Crucible"

# §S5 AC2 -- no rendered body names this token (case-sensitive, word-
# boundary matched so lowercase markdown fence tags like ```bash`` never
# false-positive).
BASH_TOKEN_RE = re.compile(r"\bBash\b")

# \u00a7S5 AC2, second clause -- "no body instructs a tool its own frontmatter
# does not grant". A Pi tool is named in a body either as a backticked
# built-in (`read`, `write`, `edit`, `bash`, `grep`, `find`, `ls` -- the
# backticks disambiguate the tool from the ordinary English word) or as any
# `ctx_*` identifier (unambiguous bare or backticked). A mention inside a
# DENIAL run -- a negation word heading a list of tool names, e.g. VERIFY's
# "(VERIFY is granted none: no `write`, `edit`, `ctx_patch` or `ctx_edit`)"
# -- is a statement of what is NOT granted, never an instruction.
_PI_BUILTIN_TOOL_NAMES = ("read", "write", "edit", "bash", "grep", "find", "ls")
TOOL_MENTION_RE = re.compile(
    r"(?<![`\w])`(" + "|".join(_PI_BUILTIN_TOOL_NAMES) + r")`(?!`)"
    r"|\b(ctx_[a-z_]+)\b"
)
_TOOL_NAME_PATTERN = r"(?:`[a-z_]+`|\bctx_[a-z_]+\b)"
TOOL_DENIAL_RUN_RE = re.compile(
    r"\b(?:[Nn]o|[Nn]ever|[Nn]ot|[Ww]ithout|[Nn]or)\s+" + _TOOL_NAME_PATTERN
    + r"(?:(?:\s*,\s*|\s+(?:or|and|nor)\s+|\s*,\s*(?:or|and|nor)\s+)" + _TOOL_NAME_PATTERN + r")*"
)

# §S3, this cycle's snapshot: the skill list each stack x role currently
# declares under [frontmatter].<role>'s "skills:" sub-list (read 2026-09-23
# from generator/stacks/*.toml). §S1-§S3 change HOW skills are declared and
# rendered (a TOML list -> a body line), never WHICH skills apply to a
# role -- nothing in scope this cycle touches skill CONTENT -- so this
# hardcoded snapshot, not a live re-parse of the doomed [frontmatter] shape,
# is the expected-value source for the "Load these skills first:" tests
# below (taken from the CURRENT spec-honoured TOML content, not invented).
CURRENT_SKILLS = {
    ("arduino", "red"): [], ("arduino", "green"): [],
    ("arduino", "verify"): ["reviewer", "reviewer-coverage", "reviewer-syntax"],
    ("arduino", "fix"): [],
    ("bun", "red"): [], ("bun", "green"): [],
    ("bun", "verify"): ["reviewer", "reviewer-coverage", "reviewer-security", "reviewer-style"],
    ("bun", "fix"): [],
    ("python", "red"): ["reviewer-coverage"], ("python", "green"): ["reviewer-coverage"],
    ("python", "verify"): [
        "reviewer", "reviewer-coverage", "reviewer-architecture",
        "reviewer-security", "reviewer-style", "reviewer-syntax",
    ],
    ("python", "fix"): ["reviewer-coverage"],
    ("quarkus", "red"): ["crucible", "refactorer-java", "reviewer-coverage"],
    ("quarkus", "green"): ["crucible", "refactorer-java", "reviewer-coverage"],
    ("quarkus", "verify"): [
        "reviewer", "reviewer-coverage", "reviewer-quarkus", "reviewer-architecture",
        "reviewer-security", "reviewer-style", "reviewer-syntax",
    ],
    ("quarkus", "fix"): ["crucible", "refactorer-java", "reviewer-coverage"],
    ("rust", "red"): ["crucible", "refactorer-rust", "reviewer-coverage"],
    ("rust", "green"): ["crucible", "refactorer-rust", "reviewer-coverage"],
    ("rust", "verify"): [
        "reviewer", "reviewer-coverage", "reviewer-architecture",
        "reviewer-security", "reviewer-style", "reviewer-syntax",
    ],
    ("rust", "fix"): ["crucible", "refactorer-rust", "reviewer-coverage"],
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _split_frontmatter(content: str):
    """Split a markdown file into (frontmatter, body) on the '---'
    delimiters. Returns ("", content) if there is no well-formed '---'
    frontmatter block."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", content
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            frontmatter = "\n".join(lines[1:idx])
            body = "\n".join(lines[idx + 1:])
            return frontmatter, body
    return "", content


def _frontmatter_keys(path: Path) -> list:
    """Top-level frontmatter keys only (lines not starting with whitespace)."""
    frontmatter, _ = _split_frontmatter(_read(path))
    keys = []
    for ln in frontmatter.splitlines():
        if not ln or ln[0].isspace():
            continue
        m = re.match(r"^([A-Za-z_]+):", ln)
        if m:
            keys.append(m.group(1))
    return keys


def _tools_line_value(path: Path):
    frontmatter, _ = _split_frontmatter(_read(path))
    for ln in frontmatter.splitlines():
        if ln.strip().startswith("tools:"):
            return ln.split(":", 1)[1].strip()
    return None

def _permission_dict(frontmatter: str) -> dict:
    """§S4 -- the permission: block as {tool: status}, read from its
    indented child lines only (never the top-level 'permission:' line
    itself). Returns {} when no top-level 'permission:' key is present
    (the pre-§S4 state)."""
    lines = frontmatter.splitlines()
    result: dict = {}
    in_block = False
    for ln in lines:
        if not in_block:
            if ln == "permission:":
                in_block = True
            continue
        if ln[:1] in (" ", "\t"):
            stripped = ln.strip()
            if stripped:
                key, _, value = stripped.partition(":")
                result[key.strip()] = value.strip()
            continue
        break
    return result


def _capitalised_tool_names(tools_value: str) -> list:
    names = [n.strip() for n in tools_value.split(",") if n.strip()]
    return [n for n in names if n[:1].isupper()]


def _tool_mentions(body: str) -> list:
    """\u00a7S5 AC2 -- every Pi tool named in ``body`` as [(name, offset,
    is_denial)], where ``is_denial`` is True when the mention sits inside a
    TOOL_DENIAL_RUN_RE span (a negation, not an instruction)."""
    denial_spans = [m.span() for m in TOOL_DENIAL_RUN_RE.finditer(body)]
    mentions = []
    for m in TOOL_MENTION_RE.finditer(body):
        name = m.group(1) or m.group(2)
        pos = m.start()
        is_denial = any(start <= pos < end for start, end in denial_spans)
        mentions.append((name, pos, is_denial))
    return mentions


def _ungranted_tool_instructions(body: str, granted) -> list:
    """\u00a7S5 AC2 -- sorted distinct tool names ``body`` instructs (names
    outside a denial run) that are absent from ``granted``."""
    granted = set(granted)
    return sorted({
        name for name, _, is_denial in _tool_mentions(body)
        if not is_denial and name not in granted
    })


def _role_of(agent_filename: str) -> str:
    stem = agent_filename[: -len("-agent.md")]
    return stem.rsplit("-", 1)[-1]


def _first_actions_section(body: str) -> str:
    """\u00a7S5 AC3 -- the text of the '## First Actions' section only, up to
    (not including) the next '## ' heading. Empty string if the section is
    absent from this body."""
    idx = body.find(FIRST_ACTIONS_HEADING)
    if idx == -1:
        return ""
    rest = body[idx + len(FIRST_ACTIONS_HEADING):]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def _first_actions_item_one(body: str) -> str:
    """\u00a7S5 AC3 -- the rest-of-line text of numbered item '1.' inside the
    '## First Actions' section, e.g. '**Register with Crucible** via ...'
    or '**AC Cross-Check** (below) -- BEFORE Crucible registration.'.
    Empty string if no numbered item 1 is found in that section."""
    section = _first_actions_section(body)
    m = re.search(r"^\s*1\.\s+(.*)$", section, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _all_agent_files():
    return sorted(AGENTS_DIR.glob("*-agent.md"))


def _load_build_module():
    """Import generator/build.py as a standalone module (pure at module
    level -- constant definitions only), matching the sibling generator
    test modules' existing helper. generator/ has no __init__.py, hence
    importlib.util over a package import."""
    spec = importlib.util.spec_from_file_location("_cr_mdb_025_c1_build", BUILD_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _generator_content_files():
    """Every text asset §S3 AC2's grep gate is scoped to: templates, stack
    TOMLs, and the rendered output -- never the whole generator/ tree
    (build.py itself is exempt, per the AC's own parenthetical)."""
    files = []
    files.extend(sorted(TEMPLATES_DIR.glob("*.tmpl")))
    files.extend(sorted(STACKS_DIR.glob("*.toml")))
    files.extend(_all_agent_files())
    return files


class NeutralRenderModuleS1Test(unittest.TestCase):
    """§S1 AC1 -- modelb_axi/agents.py holds the neutral render and
    _emit_pi; generator/build.py imports it and contains no rendering
    logic of its own."""

    def test_s1_agents_module_exists_and_defines_emit_pi(self):
        self.assertTrue(
            AGENTS_MODULE_PATH.is_file(),
            f"{AGENTS_MODULE_PATH} must exist (§S1 AC1)",
        )
        spec = importlib.util.spec_from_file_location(
            "_cr_mdb_025_c1_agents", AGENTS_MODULE_PATH
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # POSITIVE -- the spec names this function verbatim.
        self.assertTrue(
            hasattr(module, "_emit_pi"),
            "modelb_axi/agents.py must define '_emit_pi' (§S1 AC1, the one "
            "emitter name the spec pins verbatim)",
        )
        self.assertTrue(
            callable(module._emit_pi),
            "modelb_axi/agents.py's _emit_pi must be callable",
        )

    def test_s1_build_py_imports_agents_module_and_defines_no_template_rendering_itself(self):
        self.assertTrue(BUILD_PY.is_file(), f"{BUILD_PY} must exist")
        text = _read(BUILD_PY)
        # POSITIVE -- build.py must import the neutral-render module.
        self.assertRegex(
            text,
            r"from\s+modelb_axi\.agents\s+import|import\s+modelb_axi\.agents",
            "generator/build.py must import modelb_axi.agents (§S1 AC1: "
            "'generator/build.py imports it')",
        )
        # NEGATIVE -- build.py must contain no rendering logic of its own;
        # a direct string.Template(...).substitute(...) call is exactly the
        # rendering logic §S1 AC1 says must move out.
        self.assertNotIn(
            ".substitute(",
            text,
            "generator/build.py must contain no rendering logic of its own "
            "(§S1 AC1) -- found a Template(...).substitute(...) call, "
            "meaning it still renders templates itself",
        )


class StackTomlRolesShapeS1Test(unittest.TestCase):
    """§S1 AC3 -- generator/stacks/*.toml carry [roles.<role>] tables; no
    [frontmatter] block remains. Shape per §S1's own Scope prose: tools,
    thinking, skills, and an optional model."""

    def test_s1_every_stack_toml_declares_a_roles_table_for_all_four_roles(self):
        failures = []
        for stack in STACKS:
            path = STACKS_DIR / f"{stack}.toml"
            with path.open("rb") as fh:
                data = tomllib.load(fh)
            roles = data.get("roles")
            if not isinstance(roles, dict):
                failures.append(f"{stack}.toml: missing top-level [roles] table")
                continue
            missing_roles = [r for r in ROLES if r not in roles]
            if missing_roles:
                failures.append(f"{stack}.toml: [roles] missing role table(s) {missing_roles}")
        # POSITIVE/bound -- all 5 stacks x 4 roles declare a [roles.<role>] table.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s1_every_roles_table_carries_tools_thinking_and_optional_skills(self):
        failures = []
        for stack in STACKS:
            path = STACKS_DIR / f"{stack}.toml"
            with path.open("rb") as fh:
                data = tomllib.load(fh)
            roles = data.get("roles", {})
            for role in ROLES:
                role_table = roles.get(role)
                if not isinstance(role_table, dict):
                    failures.append(f"{stack}.toml [roles.{role}]: missing or not a table")
                    continue
                tools = role_table.get("tools")
                if not isinstance(tools, list) or not tools:
                    failures.append(f"{stack}.toml [roles.{role}].tools: must be a non-empty list, got {tools!r}")
                thinking = role_table.get("thinking")
                if not isinstance(thinking, str) or not thinking.strip():
                    failures.append(f"{stack}.toml [roles.{role}].thinking: must be a non-empty string, got {thinking!r}")
                if "skills" in role_table and not isinstance(role_table["skills"], list):
                    failures.append(f"{stack}.toml [roles.{role}].skills: must be a list when present, got {role_table['skills']!r}")
        # POSITIVE -- every declared role table carries the §S1 AC3 shape.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s1_no_stack_toml_carries_a_frontmatter_table(self):
        failures = []
        for stack in STACKS:
            path = STACKS_DIR / f"{stack}.toml"
            with path.open("rb") as fh:
                data = tomllib.load(fh)
            if "frontmatter" in data:
                failures.append(f"{stack}.toml: [frontmatter] block still present")
        # NEGATIVE/EXACT -- zero stacks retain the retired [frontmatter] table.
        self.assertEqual(failures, [], "\n".join(failures))


class EmittedToolsFleetGateS2Test(unittest.TestCase):
    """§S2 AC2/AC3 -- a gate over the generated fleet's tools: line, plus
    a detector fixture proving the capitalised-name gate itself bites on
    'Read' (matching the ChezmoiInvocationGateTest detector-bites pattern
    already used elsewhere in this suite)."""

    def test_s2_detector_bites_on_capitalised_tool_name_but_not_on_lowercase(self):
        # Fixture proof the DETECTOR itself fires correctly, independent of
        # any live file -- feeds one capitalised name (per the AC's own
        # wording: "a detector fixture proving it bites on Read").
        self.assertEqual(
            _capitalised_tool_names("Read, ctx_shell, write"), ["Read"],
            "the capitalised-tool-name detector must fire on 'Read'",
        )
        # NEGATIVE -- a clean, all-lowercase line must not false-positive.
        self.assertEqual(
            _capitalised_tool_names("read, ctx_shell, write"), [],
            "the detector must not fire on an all-lowercase tools: line",
        )

    def test_s2_every_emitted_definition_tools_line_is_lowercase_csv_containing_ctx_shell(self):
        failures = []
        agent_files = _all_agent_files()
        self.assertEqual(
            len(agent_files), 20,
            f"expected exactly 20 generated agent files under {AGENTS_DIR}, "
            f"found {len(agent_files)}",
        )
        for path in agent_files:
            tools_value = _tools_line_value(path)
            if tools_value is None:
                failures.append(f"{path.name}: frontmatter has no 'tools:' key")
                continue
            names = [n.strip() for n in tools_value.split(",") if n.strip()]
            if "ctx_shell" not in names:
                failures.append(f"{path.name}: tools: must contain 'ctx_shell', got {names}")
            bad = _capitalised_tool_names(tools_value)
            if bad:
                failures.append(f"{path.name}: tools: must contain no capitalised name, found {bad}")
        # POSITIVE -- every one of the 20 files carries a lowercase,
        # ctx_shell-inclusive tools: line.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s2_red_green_fix_definitions_carry_exactly_the_write_capable_tool_set(self):
        failures = []
        for path in _all_agent_files():
            if _role_of(path.name) not in ("red", "green", "fix"):
                continue
            tools_value = _tools_line_value(path) or ""
            names = [n.strip() for n in tools_value.split(",") if n.strip()]
            if set(names) != set(WRITE_CAPABLE_TOOLS) or len(names) != len(WRITE_CAPABLE_TOOLS):
                failures.append(
                    f"{path.name}: tools: must be exactly the 16 write-capable "
                    f"names {sorted(WRITE_CAPABLE_TOOLS)}, got {sorted(names)}"
                )
        # POSITIVE/EXACT -- every RED/GREEN/FIX definition carries exactly
        # the 16-name write-capable set, no more, no fewer.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s2_verify_definitions_carry_exactly_the_read_only_tool_set_and_no_write_tools(self):
        failures = []
        for path in _all_agent_files():
            if _role_of(path.name) != "verify":
                continue
            tools_value = _tools_line_value(path) or ""
            names = [n.strip() for n in tools_value.split(",") if n.strip()]
            if set(names) != set(READ_ONLY_TOOLS) or len(names) != len(READ_ONLY_TOOLS):
                failures.append(
                    f"{path.name}: tools: must be exactly the 12-name "
                    f"read-only set {sorted(READ_ONLY_TOOLS)}, got {sorted(names)}"
                )
            forbidden_present = sorted(set(names) & set(FORBIDDEN_FOR_VERIFY))
            if forbidden_present:
                failures.append(f"{path.name}: tools: must not contain {forbidden_present}")
        # POSITIVE/EXACT + NEGATIVE -- every VERIFY definition carries
        # exactly the read-only set and none of write/edit/ctx_patch/ctx_edit.
        self.assertEqual(failures, [], "\n".join(failures))


class FrontmatterKeySetS3Test(unittest.TestCase):
    """§S3 AC1 -- every emitted frontmatter key set is a subset of {name,
    description, tools, thinking, permission, model}; model appears only
    where the stack TOML sets it (no stack sets one yet)."""

    def test_s3_every_emitted_frontmatter_key_set_is_subset_of_allowed_keys(self):
        failures = []
        for path in _all_agent_files():
            keys = set(_frontmatter_keys(path))
            extra = keys - ALLOWED_FRONTMATTER_KEYS
            if extra:
                failures.append(f"{path.name}: frontmatter carries disallowed key(s) {sorted(extra)}")
        # NEGATIVE -- zero files carry a key outside the allowed set.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s3_no_live_definition_sets_model_since_no_stack_toml_sets_one_yet(self):
        failures = []
        for path in _all_agent_files():
            if "model" in _frontmatter_keys(path):
                failures.append(
                    f"{path.name}: frontmatter must not carry 'model:' -- no "
                    f"stack TOML sets a role model yet (§S3 AC1, Roundhouse "
                    f"PRD §D4 gate)"
                )
        # NEGATIVE -- model appears nowhere until a stack TOML sets one.
        self.assertEqual(failures, [], "\n".join(failures))


class BannedLegacyLiteralsS3Test(unittest.TestCase):
    """§S3 AC2 -- zero sonnet/inherit/opus/haiku/effort/color/maxTurns or
    'skills:' anywhere under generator/ (templates, stacks, rendered
    output)."""

    def test_s3_zero_banned_legacy_frontmatter_literals_under_generator_templates_stacks_and_agents(self):
        failures = []
        for path in _generator_content_files():
            text = _read(path)
            hits = sorted(set(BANNED_LITERAL_RE.findall(text)))
            if "skills:" in text:
                hits.append("skills:")
            if hits:
                failures.append(f"{path.relative_to(REPO_ROOT)}: carries banned literal(s) {hits}")
        # NEGATIVE/EXACT bound -- zero files (templates, stacks, rendered
        # output) reference any retired literal.
        self.assertEqual(failures, [], "\n".join(failures))


class SkillsBodyLineS3Test(unittest.TestCase):
    """§S3 AC3 -- every definition whose role lists skills carries one
    "Load these skills first: ..." body line naming them; a role with no
    skills carries no such line."""

    def test_s3_role_with_skills_carries_load_these_skills_first_body_line_naming_them(self):
        failures = []
        for (stack, role), skills in CURRENT_SKILLS.items():
            if not skills:
                continue
            path = AGENTS_DIR / f"{stack}-{role}-agent.md"
            _, body = _split_frontmatter(_read(path))
            line = next((ln for ln in body.splitlines() if "Load these skills first:" in ln), None)
            if line is None:
                failures.append(
                    f"{path.name}: body must carry one 'Load these skills "
                    f"first:' line naming {skills}"
                )
                continue
            missing = [s for s in skills if s not in line]
            if missing:
                failures.append(f"{path.name}: 'Load these skills first:' line missing {missing}, got: {line!r}")
        # POSITIVE -- every role with skills carries the named body line.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s3_role_without_skills_carries_no_load_these_skills_first_line(self):
        failures = []
        for (stack, role), skills in CURRENT_SKILLS.items():
            if skills:
                continue
            path = AGENTS_DIR / f"{stack}-{role}-agent.md"
            if "Load these skills first:" in _read(path):
                failures.append(f"{path.name}: role carries no skills but body has a 'Load these skills first:' line")
        # NEGATIVE -- a skill-less role never gets the line (regression guard).
        self.assertEqual(failures, [], "\n".join(failures))


class UnknownIntentDropS2Test(unittest.TestCase):
    """§S2 AC1 -- "an unknown intent name is dropped with a recorded
    reason -- asserted by a test feeding one." Drives the REAL
    generator/build.py CLI end to end against an isolated fixture copy of
    the repo, whose python.toml has its retired [frontmatter] table
    replaced by a [roles.red] table in the exact §S1 AC3-pinned shape
    (tools/thinking/skills/model), with one deliberately unknown tool
    intent ("NotARealToolXYZ") injected alongside every valid one. This
    also incidentally proves the model/skills wiring end to end (§S3),
    exercising the real production entry point rather than a hand-built
    harness that bypasses it."""

    def setUp(self):
        self._build_module = _load_build_module()
        origin_root = self._build_module.REPO_ROOT
        codec_source_rel = self._build_module.CODEC_SOURCE.relative_to(origin_root)
        codec_target_rel = self._build_module.CODEC_TARGET.relative_to(origin_root)
        agents_rel = self._build_module.AGENTS_DIR.relative_to(origin_root)
        modelb_axi_pkg_rel = codec_source_rel.parent

        self._tmp_repo_root = Path(tempfile.mkdtemp(prefix="cr-mdb-025-s2-repo-"))
        tmp_generator_dir = self._tmp_repo_root / "generator"
        tmp_generator_dir.mkdir()
        shutil.copytree(TEMPLATES_DIR, tmp_generator_dir / "templates")
        shutil.copytree(STACKS_DIR, tmp_generator_dir / "stacks")
        shutil.copy(BUILD_PY, tmp_generator_dir / "build.py")
        # Mirror the whole modelb_axi/ package -- build.py's cross-package
        # import (§S1 AC1) must resolve inside the isolated copy too, not
        # just against the real repo (see the BespokeUntouchedS4Test
        # migration note in tests/test_agent_generator.py for the same
        # reasoning).
        shutil.copytree(
            origin_root / modelb_axi_pkg_rel,
            self._tmp_repo_root / modelb_axi_pkg_rel,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        (self._tmp_repo_root / codec_target_rel).parent.mkdir(parents=True, exist_ok=True)

        fixture_toml = tmp_generator_dir / "stacks" / "python.toml"
        original_text = fixture_toml.read_text(encoding="utf-8")
        match = re.search(r"\n\[roles\.red\]\n.*?(?=\n\[|\Z)", original_text, re.S)
        self.assertIsNotNone(
            match,
            "fixture setup: python.toml must carry a [roles.red] table "
            "to replace with the fixture's (§S1 AC3 shape)",
        )
        assert match is not None
        valid_tools_csv = ", ".join(f'"{t}"' for t in WRITE_CAPABLE_TOOLS)
        roles_block = (
            "\n[roles.red]\n"
            f"tools = [{valid_tools_csv}, \"NotARealToolXYZ\"]\n"
            "thinking = \"high\"\n"
            "skills = [\"reviewer-coverage\"]\n"
            "model = \"cr-mdb-025-fixture-model\"\n"
        )
        mutated_text = original_text[: match.start()] + roles_block + original_text[match.end():]
        fixture_toml.write_text(mutated_text, encoding="utf-8")
        # sanity -- the fixture itself must still be valid TOML.
        with fixture_toml.open("rb") as fh:
            tomllib.load(fh)

        self._tmp_build_py = tmp_generator_dir / "build.py"
        self._tmp_agents_dir = self._tmp_repo_root / agents_rel

    def tearDown(self):
        shutil.rmtree(self._tmp_repo_root, ignore_errors=True)

    def test_s2_unknown_tool_intent_dropped_valid_ones_and_model_skill_survive(self):
        result = subprocess.run(
            [sys.executable, str(self._tmp_build_py), "build", "--stacks", "python", "--roles", "red"],
            capture_output=True, text=True, timeout=60,
        )
        # POSITIVE -- an unknown tool intent must be DROPPED, never fail the
        # whole build (§S2 AC1: "is dropped", not "is refused").
        self.assertEqual(
            result.returncode, 0,
            f"an unknown tool intent must be dropped, not fail the whole "
            f"build (§S2 AC1), got rc={result.returncode}\n"
            f"stdout:\n{result.stdout[:2000]}\nstderr:\n{result.stderr[:2000]}",
        )
        rendered_path = self._tmp_agents_dir / "python-red-agent.md"
        self.assertTrue(rendered_path.is_file(), f"{rendered_path} must be written by the build")
        rendered = rendered_path.read_text(encoding="utf-8")
        frontmatter, body = _split_frontmatter(rendered)
        tools_line = next((ln for ln in frontmatter.splitlines() if ln.strip().startswith("tools:")), None)
        self.assertIsNotNone(tools_line, "rendered frontmatter must carry a tools: key")
        assert tools_line is not None
        tools_value = tools_line.split(":", 1)[1].strip()
        tool_names = [n.strip() for n in tools_value.split(",") if n.strip()]
        # NEGATIVE/EXACT -- the unknown intent is never passed through or renamed.
        self.assertNotIn(
            "NotARealToolXYZ", tool_names,
            f"unknown tool intent must be dropped, not passed through or "
            f"renamed, got: {tool_names}",
        )
        # POSITIVE/EXACT -- every valid intent survives translation
        # untouched by the unknown one riding alongside it.
        self.assertEqual(
            set(tool_names), set(WRITE_CAPABLE_TOOLS),
            f"every valid intent must translate through unharmed, got {sorted(tool_names)}",
        )
        combined_output = result.stdout + result.stderr
        # POSITIVE -- the drop is RECORDED with a reason naming what was
        # dropped (§S2 AC1's "recorded reason"), not silently discarded.
        self.assertIn(
            "NotARealToolXYZ", combined_output,
            f"dropping an unknown tool intent must record a reason naming "
            f"it (§S2 AC1), found nothing in the build's own output:\n"
            f"stdout:\n{result.stdout[:2000]}\nstderr:\n{result.stderr[:2000]}",
        )
        # §S3 wiring proof, exercised through this same real CLI run.
        self.assertIn(
            "model: cr-mdb-025-fixture-model", frontmatter,
            "a role-level model set in [roles.<role>] must be emitted verbatim (§S3 AC1)",
        )
        self.assertIn("thinking: high", frontmatter)
        self.assertIn(
            "Load these skills first:", body,
            "a role with skills must carry the 'Load these skills first:' body line (§S3 AC3)",
        )
        self.assertIn("reviewer-coverage", body)


class PermissionPolicyS4Test(unittest.TestCase):
    """\u00a7S4 AC1/AC2 -- every definition's permission: block grants allow to
    exactly the tools its tools: line admits (a gate cross-checking the two
    keys across the fleet); every VERIFY definition additionally states
    write: deny and edit: deny, so the read-only property is enforced by
    both the allowlist and the policy."""

    def test_s4_emit_pi_permission_allow_set_tracks_an_arbitrary_tools_list(self):
        # Module-level, controlled fixture -- proves the MECHANISM derives
        # allow from the tools actually passed, not a per-stack hardcode
        # that would merely happen to agree with today's 20 committed
        # files (would FAIL against a no-op stub that emits an empty or
        # constant permission: block).
        from modelb_axi import agents
        fixture_tools = ["read", "ctx_shell", "ctx_search"]
        defn = {
            "name": "fixture-red-agent",
            "description": "fixture description for \u00a7S4",
            "body": "fixture body\n",
            "tools": list(fixture_tools),
            "thinking": "medium",
            "skills": [],
        }
        rendered = agents._emit_pi(defn)
        frontmatter, _ = _split_frontmatter(rendered)
        permission = _permission_dict(frontmatter)
        allowed = {tool for tool, status in permission.items() if status == "allow"}
        # POSITIVE/EXACT -- allow grants exactly the fixture's own tools.
        self.assertEqual(
            allowed, set(fixture_tools),
            f"permission: must grant allow to exactly the tools: line "
            f"admits (\u00a7S4 AC1), got allow={sorted(allowed)} for tools={fixture_tools}",
        )
        # NEGATIVE -- a tool this fixture did not admit must not appear in
        # the permission block at all (nothing to grant or deny for it).
        self.assertNotIn(
            "write", permission,
            "permission: must not mention a tool absent from this "
            "definition's own tools: line",
        )

    def test_s4_permission_allow_set_equals_tools_line_exactly_across_the_fleet(self):
        failures = []
        agent_files = _all_agent_files()
        self.assertEqual(
            len(agent_files), 20,
            f"expected exactly 20 generated agent files under {AGENTS_DIR}, "
            f"found {len(agent_files)}",
        )
        for path in agent_files:
            frontmatter, _ = _split_frontmatter(_read(path))
            tools_value = _tools_line_value(path) or ""
            tool_names = {n.strip() for n in tools_value.split(",") if n.strip()}
            permission = _permission_dict(frontmatter)
            allowed = {tool for tool, status in permission.items() if status == "allow"}
            if allowed != tool_names:
                failures.append(
                    f"{path.name}: permission allow-set {sorted(allowed)} "
                    f"!= tools: set {sorted(tool_names)} (\u00a7S4 AC1)"
                )
        # POSITIVE/EXACT -- every one of the 20 files grants allow to
        # exactly the tools its own tools: line admits, no gate skipped.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s4_every_verify_definition_states_write_deny_and_edit_deny(self):
        failures = []
        verify_files = [p for p in _all_agent_files() if _role_of(p.name) == "verify"]
        self.assertEqual(
            len(verify_files), 5,
            f"expected exactly 5 VERIFY definitions (one per stack), found {len(verify_files)}",
        )
        for path in verify_files:
            frontmatter, _ = _split_frontmatter(_read(path))
            permission = _permission_dict(frontmatter)
            for tool in VERIFY_DENIED_TOOLS:
                if permission.get(tool) != "deny":
                    failures.append(
                        f"{path.name}: permission.{tool} must be 'deny' "
                        f"(\u00a7S4 AC2), got {permission.get(tool)!r}"
                    )
        # POSITIVE/EXACT -- every VERIFY definition states both denies.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s4_non_verify_definitions_carry_no_write_or_edit_deny_entry(self):
        # NEGATIVE/bound -- AC2 names VERIFY only; RED/GREEN/FIX admit
        # write+edit in their own tools: line (\u00a7S2), so a deny entry
        # there would directly contradict their own grant.
        failures = []
        for path in _all_agent_files():
            if _role_of(path.name) == "verify":
                continue
            frontmatter, _ = _split_frontmatter(_read(path))
            permission = _permission_dict(frontmatter)
            for tool in VERIFY_DENIED_TOOLS:
                if permission.get(tool) == "deny":
                    failures.append(
                        f"{path.name}: non-VERIFY definition must not deny {tool}"
                    )
        self.assertEqual(failures, [], "\n".join(failures))


class TemplateRulesS5Test(unittest.TestCase):
    """\u00a7S5 AC1 -- every rendered definition carries the
    out-of-repository read rule; every rendered RED definition additionally
    carries the prove-both-ways rule and the test-migration rule (gates
    over the fleet). Anchor phrases are measured verbatim from this repo's
    own hand-made .pi/agents/python-*-agent.md (see module docstring)."""

    def test_s5_every_definition_carries_the_out_of_repository_read_rule(self):
        failures = []
        agent_files = _all_agent_files()
        self.assertEqual(
            len(agent_files), 20,
            f"expected exactly 20 generated agent files under {AGENTS_DIR}, "
            f"found {len(agent_files)}",
        )
        for path in agent_files:
            _, body = _split_frontmatter(_read(path))
            if OUT_OF_REPO_READ_RULE_ANCHOR not in body:
                failures.append(
                    f"{path.name}: body must carry the out-of-repository "
                    f"read rule (\u00a7S5 AC1): {OUT_OF_REPO_READ_RULE_ANCHOR!r}"
                )
        # POSITIVE -- all four roles, every stack, carry the rule.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s5_every_red_definition_carries_the_prove_both_ways_rule(self):
        failures = []
        red_files = [p for p in _all_agent_files() if _role_of(p.name) == "red"]
        self.assertEqual(len(red_files), 5, f"expected exactly 5 RED definitions, found {len(red_files)}")
        for path in red_files:
            _, body = _split_frontmatter(_read(path))
            if PROVE_BOTH_WAYS_RULE_ANCHOR not in body:
                failures.append(
                    f"{path.name}: RED body must carry the prove-both-ways "
                    f"rule (\u00a7S5 AC1): {PROVE_BOTH_WAYS_RULE_ANCHOR!r}"
                )
        # POSITIVE -- every one of the 5 RED definitions carries the rule.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s5_every_red_definition_carries_the_test_migration_rule(self):
        failures = []
        red_files = [p for p in _all_agent_files() if _role_of(p.name) == "red"]
        self.assertEqual(len(red_files), 5, f"expected exactly 5 RED definitions, found {len(red_files)}")
        for path in red_files:
            _, body = _split_frontmatter(_read(path))
            if TEST_MIGRATION_RULE_ANCHOR not in body:
                failures.append(
                    f"{path.name}: RED body must carry the test-migration "
                    f"rule (\u00a7S5 AC1): {TEST_MIGRATION_RULE_ANCHOR!r}"
                )
        # POSITIVE -- every one of the 5 RED definitions carries the rule.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s5_non_red_definitions_carry_no_prove_both_ways_or_migration_rule(self):
        # NEGATIVE/bound -- AC1 scopes these two rules to RED only; a
        # GREEN/VERIFY/FIX body carrying either would be scope creep the
        # spec's own template-per-role rendering must not introduce.
        failures = []
        for path in _all_agent_files():
            if _role_of(path.name) == "red":
                continue
            _, body = _split_frontmatter(_read(path))
            if PROVE_BOTH_WAYS_RULE_ANCHOR in body:
                failures.append(f"{path.name}: non-RED body must not carry the RED-only prove-both-ways rule")
            if TEST_MIGRATION_RULE_ANCHOR in body:
                failures.append(f"{path.name}: non-RED body must not carry the RED-only test-migration rule")
        self.assertEqual(failures, [], "\n".join(failures))


class ToolNamesRuleS5Test(unittest.TestCase):
    """\u00a7S5 AC2 -- no rendered body names Bash, and no body instructs a
    tool absent from its own tools: line. The CR's own Context section
    measures 'Bash' as the concrete instance of this drift (a capitalised
    Claude Code tool name matching no registered Pi tool), so a zero-count
    gate over the literal token is the direct, currently-failing proof of
    both clauses of this AC bullet."""

    def test_s5_zero_bash_mentions_across_every_rendered_body(self):
        failures = []
        agent_files = _all_agent_files()
        self.assertEqual(
            len(agent_files), 20,
            f"expected exactly 20 generated agent files under {AGENTS_DIR}, "
            f"found {len(agent_files)}",
        )
        for path in agent_files:
            _, body = _split_frontmatter(_read(path))
            hits = len(BASH_TOKEN_RE.findall(body))
            if hits:
                failures.append(f"{path.name}: body names 'Bash' {hits} time(s) (\u00a7S5 AC2)")
        # NEGATIVE/EXACT bound -- zero of the 20 rendered bodies name Bash.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s5_detector_bites_on_bash_but_not_on_lowercase_bash_fence_tag(self):
        # Fixture proof the DETECTOR itself fires correctly, independent of
        # any live file -- a capitalised 'Bash' mention must bite, while a
        # markdown fenced-code-block language tag (lowercase ```bash```)
        # must not false-positive (it names a syntax highlighter, not a
        # tool the agent is instructed to use).
        self.assertEqual(
            len(BASH_TOKEN_RE.findall("Run via `Bash` for this.")), 1,
            "the Bash-token detector must fire on a capitalised 'Bash' mention",
        )
        self.assertEqual(
            len(BASH_TOKEN_RE.findall("```bash\npython3 foo.py\n```")), 0,
            "the detector must not fire on a lowercase ```bash``` fence tag",
        )

    def test_s5_no_body_instructs_a_tool_absent_from_its_own_tools_line(self):
        # \u00a7S5 AC2, second clause -- fleet gate over all 20 rendered
        # definitions: every Pi tool a body names as an instruction (i.e.
        # outside a denial run) is in that file's own tools: set.
        failures = []
        agent_files = _all_agent_files()
        self.assertEqual(
            len(agent_files), 20,
            f"expected exactly 20 generated agent files under {AGENTS_DIR}, "
            f"found {len(agent_files)}",
        )
        instruction_count = 0
        denial_count = 0
        for path in agent_files:
            tools_value = _tools_line_value(path)
            self.assertIsNotNone(tools_value, f"{path.name}: no tools: line")
            granted = {n.strip() for n in (tools_value or "").split(",") if n.strip()}
            _, body = _split_frontmatter(_read(path))
            mentions = _tool_mentions(body)
            instruction_count += sum(1 for _, _, d in mentions if not d)
            denial_count += sum(1 for _, _, d in mentions if d)
            ungranted = _ungranted_tool_instructions(body, granted)
            if ungranted:
                failures.append(
                    f"{path.name}: body instructs tool(s) {ungranted} absent "
                    f"from its own tools: line (\u00a7S5 AC2)"
                )
        # Non-vacuity: the detector actually sees tool instructions in the
        # fleet, and the VERIFY denial sentence is exercised as a denial.
        self.assertGreater(instruction_count, 0, "detector saw no tool instructions in the fleet")
        self.assertGreater(denial_count, 0, "detector saw no denial run in the fleet (VERIFY's)")
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s5_ungranted_tool_detector_bites_on_instruction_not_on_denial(self):
        # Fixture proof, independent of any live file.
        verify_granted = set(READ_ONLY_TOOLS)
        # BITES -- a VERIFY-shaped body instructing ctx_patch / `write`.
        self.assertEqual(
            _ungranted_tool_instructions(
                "3. Apply the correction with `ctx_patch` on the reported line.",
                verify_granted,
            ),
            ["ctx_patch"],
        )
        self.assertEqual(
            _ungranted_tool_instructions("Save the report with `write`.", verify_granted),
            ["write"],
        )
        # DOES NOT BITE -- the live VERIFY denial sentence, verbatim.
        denial = (
            "any file-writing tool on repo files (VERIFY is granted none: no "
            "`write`, `edit`, `ctx_patch` or `ctx_edit`)."
        )
        self.assertEqual(_ungranted_tool_instructions(denial, verify_granted), [])
        # A denial does not launder an instruction later on the same line.
        self.assertEqual(
            _ungranted_tool_instructions(denial + " Then fix it with `edit`.", verify_granted),
            ["edit"],
        )
        # DOES NOT BITE -- the same instruction where the tool IS granted,
        # nor on plain-English 'write'/'edit' (no backticks = not a tool).
        self.assertEqual(
            _ungranted_tool_instructions(
                "Apply the fix with `ctx_patch`.", set(WRITE_CAPABLE_TOOLS)
            ),
            [],
        )
        self.assertEqual(
            _ungranted_tool_instructions(
                "never let any incidental write land outside /tmp; edit nothing",
                verify_granted,
            ),
            [],
        )


class RegisterFirstOrderS5Test(unittest.TestCase):
    """\u00a7S5 AC3 (2026-09-23 amendment, commit bcd5cf6) -- every rendered
    definition's First Actions list carries registration with Crucible as
    item 1, ahead of the AC cross-check -- a gate over the fleet (all 20),
    with a detector fixture proving it bites on the pre-amendment order.
    Measured 2026-09-2x directly from generator/templates/{red,green}.md.tmpl
    and their generator/agents/*-{red,green}-agent.md renders: item 1 today
    is '**AC Cross-Check** (below/above) -- BEFORE/before Crucible
    registration.', with registration as item 2 -- the exact pre-amendment
    order this AC's detector fixture reproduces verbatim below.
    generator/templates/{fix,verify}.md.tmpl (and their ten rendered
    fix/verify files) already comply."""

    def test_s5_every_definitions_first_actions_item_one_is_register_with_crucible(self):
        failures = []
        agent_files = _all_agent_files()
        self.assertEqual(
            len(agent_files), 20,
            f"expected exactly 20 generated agent files under {AGENTS_DIR}, "
            f"found {len(agent_files)}",
        )
        for path in agent_files:
            _, body = _split_frontmatter(_read(path))
            item_one = _first_actions_item_one(body)
            self.assertNotEqual(
                item_one, "",
                f"{path.name}: no numbered item 1 found under "
                f"{FIRST_ACTIONS_HEADING!r} (\u00a7S5 AC3)",
            )
            if REGISTER_FIRST_ANCHOR not in item_one:
                failures.append(
                    f"{path.name}: First Actions item 1 must open with "
                    f"registration ahead of the AC cross-check (\u00a7S5 AC3), "
                    f"found: {item_one!r}"
                )
        # POSITIVE -- all four roles, every stack, register first.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s5_detector_bites_on_pre_amendment_order_but_not_on_register_first_order(self):
        # Fixture proof the DETECTOR itself fires correctly, independent of
        # any live file. The pre-amendment fixture text is measured
        # verbatim from generator/templates/red.md.tmpl's own First Actions
        # list today (item 1 = AC Cross-Check, item 2 = Register); the
        # post-amendment fixture is the compliant order \u00a7S5 AC3 requires.
        pre_amendment_body = (
            FIRST_ACTIONS_HEADING + "\n\n"
            "1. **AC Cross-Check** (below) \u2014 BEFORE Crucible registration.\n"
            "2. **Register with Crucible** via the stable stack client "
            "(NOT inline curl/python), with the agentId from your dispatch "
            "prompt.\n"
            "3. **Read project context** \u2014 CLAUDE.md, then any docs it "
            "references.\n"
            "\n## Acceptance Criteria Cross-Check (STEP 1 \u2014 BEFORE CRUCIBLE, BEFORE ANYTHING)\n"
        )
        pre_item_one = _first_actions_item_one(pre_amendment_body)
        self.assertEqual(
            pre_item_one,
            "**AC Cross-Check** (below) \u2014 BEFORE Crucible registration.",
            "the detector's own item-1 extraction must return the AC "
            "cross-check text unmodified from the pre-amendment fixture",
        )
        self.assertNotIn(
            REGISTER_FIRST_ANCHOR, pre_item_one,
            "the detector must BITE (the anchor must be absent from item 1) "
            "on the pre-amendment order",
        )

        post_amendment_body = (
            FIRST_ACTIONS_HEADING + "\n\n"
            "1. **Register with Crucible** via the stable stack client "
            "(NOT inline curl/python), with the agentId from your dispatch "
            "prompt.\n"
            "2. **Read project context** \u2014 CLAUDE.md, then any docs it "
            "references.\n"
            "\n## Acceptance Criteria Cross-Check (STEP 1 \u2014 BEFORE CRUCIBLE, BEFORE ANYTHING)\n"
        )
        post_item_one = _first_actions_item_one(post_amendment_body)
        self.assertIn(
            REGISTER_FIRST_ANCHOR, post_item_one,
            "the detector must NOT bite (the anchor must be present in item "
            "1) on the compliant, post-amendment register-first order",
        )


# ---------------------------------------------------------------------------
# CR-MDB-025 CYCLE C3 -- \u00a7S6: `init` renders the project's agents; the
# `agents` CLI re-render verb; file-ownership markers; the installer writes
# no agent definitions. See the module docstring's "CYCLE C3 AMENDMENT"
# section for the design assumptions these tests had to fix.
# ---------------------------------------------------------------------------

# \u00a7S6 -- the one rendered-agents directory this CR's Pi emitter writes to.
PI_AGENTS_RELDIR = Path(".pi") / "agents"

# \u00a7S6 Ownership -- structural marker detection (see the module docstring's
# design-assumptions note): a bare 64-hex-digit sha256 token, matched inside
# a `#`-prefixed comment line that also names this project ("modelb",
# case-insensitive).
_MARKER_HASH_RE = re.compile(r"\b[0-9a-f]{64}\b")


def _run_module_c3(*args, cwd=None, env_overrides=None, timeout=60, stdin=subprocess.DEVNULL):
    """Invoke `python -m modelb_axi <args>`, optionally inside `cwd` -- the
    `agents` verb re-renders "the project in the current directory" per the
    CR's own \u00a7S6 prose, so exercising it means actually chdir-ing there, not
    just passing a --target-shaped flag. Mirrors tests/test_scaffold.py's
    own `_run_module` (not imported from it -- every sibling test module in
    this suite keeps its own copy)."""
    env = dict(os.environ)
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
    if env_overrides:
        env.update(env_overrides)
    cmd = [sys.executable, "-m", "modelb_axi", *args]
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        stdin=stdin, env=env,
    )


def _copy_c3_asset_root(dest: Path) -> Path:
    """A PRIVATE, mutable copy of the asset roots `init`/`agents` need
    (`generator/` for templates+stacks, `skills-src/memory-templates/` for
    the \u00a7S3.4 memory seam every `init` run still exercises) -- so a test can
    edit a template file to prove re-render WITHOUT ever touching the real
    repo tree (the sandbox-guard rule every sibling scaffold test module in
    this suite honours)."""
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(GENERATOR_DIR, dest / "generator")
    (dest / "skills-src").mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        REPO_ROOT / "skills-src" / "memory-templates",
        dest / "skills-src" / "memory-templates",
    )
    return dest


def _write_install_toml_c3(home: Path, asset_root: Path, harnesses=("pi",)) -> Path:
    """A valid install.toml fixture pointed at a PRIVATE `asset_root`
    (never the real repo) -- mirrors tests/test_scaffold.py's own
    `_write_install_toml`, extended with a real, controllable asset root so
    \u00a7S6 tests can mutate a template and observe the re-render pick it up."""
    harnesses_toml = ", ".join(f'"{h}"' for h in harnesses)
    hooks_scripts_dir = home / ".agents" / "hooks" / "scripts"
    home.mkdir(parents=True, exist_ok=True)
    install_toml = home / "install.toml"
    install_toml.write_text(
        "[install]\n"
        'version = "0.1.0"\n'
        f"harnesses = [{harnesses_toml}]\n"
        f'asset_root = "{asset_root}"\n'
        f'hooks_scripts_dir = "{hooks_scripts_dir}"\n'
        "\n"
        "[deps]\n"
        'uv = "present"\n'
        "\n"
        "[files]\n",
        encoding="utf-8",
    )
    return install_toml


def _parse_env_file_c3(path: Path) -> dict:
    """Minimal `KEY=VALUE` parser for the emitted `.env` -- mirrors
    tests/test_scaffold.py's own `_parse_env_file` (test-side only, no
    production coupling)."""
    values: dict = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw_value = stripped.partition("=")
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _decode_envelope_c3(stdout: str) -> dict:
    """Decode a TOON AXI envelope via Model B's OWN codec
    (`modelb_axi.toon`) -- the production emitter's exact counterpart, per
    `axi.py`'s own module docstring (never Crucible's client copy)."""
    from modelb_axi.toon import decode
    return decode(stdout)


def _snapshot_hashes(root: Path) -> dict:
    """{relpath: sha256} for every regular file under `root`, `.git/`
    excluded (internal git housekeeping can touch loose-object files for
    reasons unrelated to what a test is proving) and symlinks excluded
    (e.g. CLAUDE.md)."""
    snap = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if ".git" in rel.parts:
            continue
        if path.is_file() and not path.is_symlink():
            snap[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snap


def _marker_line(frontmatter: str):
    """The \u00a7S6 Ownership marker COMMENT line, or None. See the module
    docstring's design-assumptions note for the structural-detection
    rationale (a `#`-prefixed line, a bare 64-hex sha256, and the
    substring "modelb")."""
    for ln in frontmatter.splitlines():
        stripped = ln.strip()
        if (
            stripped.startswith("#")
            and _MARKER_HASH_RE.search(stripped)
            and "modelb" in stripped.lower()
        ):
            return ln
    return None


def _strip_exact_line(text: str, line: str) -> str:
    """Remove exactly ONE occurrence of `line` from `text` -- used to turn a
    genuinely rendered file into a "no marker" fixture (Ownership AC's 4th
    subtest: a same-named file that was never generated, or whose marker
    was stripped, carries no marker at all)."""
    lines = text.splitlines(keepends=True)
    for idx, ln in enumerate(lines):
        if ln.rstrip("\n") == line:
            del lines[idx]
            return "".join(lines)
    raise AssertionError(f"line {line!r} not found to strip")


def _find_path_in_envelope_bucket(envelope: dict, rel_path: str, keyword: str) -> bool:
    """True if `rel_path` appears in a list-valued envelope field whose KEY
    contains `keyword` (case-insensitive substring) -- binds to the \u00a7S6
    outcome VOCABULARY the CR's own prose names ("written, unchanged,
    skipped and unmanaged") without pinning one hand-picked TOON key
    spelling."""
    axi = envelope.get("axi", envelope)
    for key, value in axi.items():
        if keyword.lower() in key.lower() and isinstance(value, list) and any(
            rel_path in str(item) for item in value
        ):
            return True
    return False


def _init_pi_project(tmp_dir_prefix: str, stacks="python", harnesses=("pi",)):
    """Run a real, fully isolated `init` (private asset-root copy, sandboxed
    home+target -- never the real repo/home) and return
    `(result, home, asset_root, target)` as `Path`s."""
    tmp_home = Path(tempfile.mkdtemp(prefix=f"{tmp_dir_prefix}-home-"))
    tmp_asset_root = Path(tempfile.mkdtemp(prefix=f"{tmp_dir_prefix}-assets-"))
    tmp_target = Path(tempfile.mkdtemp(prefix=f"{tmp_dir_prefix}-target-"))
    _copy_c3_asset_root(tmp_asset_root)
    _write_install_toml_c3(tmp_home, tmp_asset_root, harnesses=harnesses)
    result = _run_module_c3(
        "--yes", "init",
        "--name", "X", "--token", "xproj", "--acronym", "XP",
        "--mode", "solo", "--repo-shape", "standalone",
        "--stacks", stacks, "--owner", "tester",
        "--target", str(tmp_target),
        "--modelb-home", str(tmp_home),
    )
    return result, tmp_home, tmp_asset_root, tmp_target


class InitRendersPiProjectAgentsS6Test(unittest.TestCase):
    """\u00a7S6 AC1 -- `init --stacks python` with installed harnesses `[pi]`
    writes exactly `.pi/agents/python-{red,green,verify,fix}-agent.md`,
    records `PROJECT_STACKS=python` in `.env`, and each written file is
    byte-identical to `agents.render()` for the same stack x role.

    Written before any \u00a7S6 production code exists: `run_init` never renders
    agent definitions today (`scaffold.py::_emit_plan` has no `agents`
    import or `.pi/agents` write site).
    """

    @classmethod
    def setUpClass(cls):
        cls._result, cls._home, cls._asset_root, cls._target = _init_pi_project(
            "modelb-axi-c3-s6-solo",
        )

    @classmethod
    def tearDownClass(cls):
        for root in (cls._home, cls._asset_root, cls._target):
            shutil.rmtree(root, ignore_errors=True)

    def test_s6_init_succeeded_precondition(self):
        # Fixture precondition, not an S6 assertion itself.
        self.assertEqual(
            self._result.returncode, 0,
            f"S6 fixture precondition: init must succeed; "
            f"stdout={self._result.stdout!r} stderr={self._result.stderr!r}",
        )

    def test_s6_init_writes_exactly_the_four_python_pi_agent_files(self):
        agents_dir = self._target / PI_AGENTS_RELDIR
        self.assertTrue(
            agents_dir.is_dir(),
            f"S6 AC1: {agents_dir} must exist after `init --stacks python` "
            f"with installed harnesses [pi]; init stderr={self._result.stderr!r}",
        )
        found = sorted(p.name for p in agents_dir.glob("*"))
        expected = sorted(f"python-{role}-agent.md" for role in ROLES)
        # POSITIVE/EXACT -- exactly these four files, nothing else.
        self.assertEqual(
            found, expected,
            f"S6 AC1: {agents_dir} must contain exactly {expected}; found {found}",
        )

    def test_s6_each_written_file_is_byte_identical_to_agents_render_output(self):
        params = agents_mod.load_stack_params(STACKS_DIR, "python")
        for role in ROLES:
            written = self._target / PI_AGENTS_RELDIR / f"python-{role}-agent.md"
            self.assertTrue(
                written.is_file(),
                f"S6 AC1 fixture precondition: {written} must exist "
                f"(see test_s6_init_writes_exactly_the_four_python_pi_agent_files)",
            )
            expected = agents_mod.render("python", role, params, TEMPLATES_DIR, harness="pi")
            # POSITIVE/EXACT -- byte-for-byte, not merely equivalent.
            self.assertEqual(
                written.read_text(encoding="utf-8"), expected,
                f"S6 AC1: {written} must be byte-identical to "
                f"agents.render('python', {role!r}, ...); it is not",
            )

    def test_s6_env_records_project_stacks_equal_to_python(self):
        env = _parse_env_file_c3(self._target / ".env")
        self.assertEqual(
            env.get("PROJECT_STACKS"), "python",
            f"S6 AC1: `.env` must record PROJECT_STACKS=python; got env={env!r}",
        )


class InitToleratesStackWithoutAgentTemplateS6Test(unittest.TestCase):
    """\u00a7S6 regression guard -- `scaffold.KNOWN_STACKS` names `java` as a
    stack id distinct from `quarkus` (memory-template selection and
    hook-instance selection both already branch on it), but
    `agents.STACKS` has no `java` entry at all (only `quarkus` --
    "Quarkus/Java projects"). A `--stacks rust,java` init -- exactly
    tests/test_scaffold.py's existing `PiWorktreeCarryAndClosedGuardsTest`
    fixture, which this CR must not break -- must still succeed, rendering
    agent definitions only for the stack(s) that HAVE one; `java` is
    silently skipped, never a fatal error.
    """

    def test_s6_stacks_rust_java_with_pi_harness_renders_rust_only_and_succeeds(self):
        tmp_home = tempfile.mkdtemp(prefix="modelb-axi-c3-s6-java-home-")
        tmp_target = tempfile.mkdtemp(prefix="modelb-axi-c3-s6-java-target-")
        self.addCleanup(shutil.rmtree, tmp_home, ignore_errors=True)
        self.addCleanup(shutil.rmtree, tmp_target, ignore_errors=True)
        # Mirrors tests/test_scaffold.py's own `_write_install_toml` fixture
        # EXACTLY (a bogus configured asset_root relying on the real repo's
        # default_asset_root() fallback) -- the SAME configuration
        # PiWorktreeCarryAndClosedGuardsTest already uses.
        hooks_scripts_dir = Path(tmp_home) / ".agents" / "hooks" / "scripts"
        Path(tmp_home, "install.toml").write_text(
            "[install]\n"
            'version = "0.1.0"\n'
            'harnesses = ["claude-code", "pi"]\n'
            'asset_root = "/tmp/does-not-matter-for-this-test"\n'
            f'hooks_scripts_dir = "{hooks_scripts_dir}"\n'
            "\n[deps]\nuv = \"present\"\n\n[files]\n",
            encoding="utf-8",
        )
        result = _run_module_c3(
            "--yes", "init",
            "--name", "X", "--token", "xproj", "--acronym", "XP",
            "--mode", "multi:2", "--repo-shape", "standalone",
            "--stacks", "rust,java", "--owner", "tester",
            "--target", tmp_target,
            "--modelb-home", tmp_home,
        )
        # POSITIVE -- `java` in --stacks must never be fatal.
        self.assertEqual(
            result.returncode, 0,
            f"S6: `init --stacks rust,java` (no java stack TOML for agent "
            f"rendering) must still succeed; got exit={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        agents_dir = Path(tmp_target) / PI_AGENTS_RELDIR
        found = sorted(p.name for p in agents_dir.glob("*")) if agents_dir.is_dir() else []
        expected = sorted(f"rust-{role}-agent.md" for role in ROLES)
        # POSITIVE/EXACT -- rust's four files, and nothing named `java-*`.
        self.assertEqual(
            found, expected,
            f"S6: --stacks rust,java must render exactly rust's four "
            f"files (java silently skipped, no java-*-agent.md); found {found}",
        )


class InstalledWheelInitRendersAgentsS6Test(unittest.TestCase):
    """\u00a7S6 AC2 -- an installed-wheel `init` (never a repo checkout) also
    renders `.pi/agents/*`: the wheel's force-included package data
    (`modelb_axi/_assets/generator/...`) is what a genuinely-installed
    `init` resolves its templates/stacks from -- the same CR-MDB-014/022
    missing-asset-class shape `InstalledPackageAssetRootEndToEndTest`
    (tests/test_installer_assets.py) already proved for the deploy engine,
    applied here to `init`.
    """

    def setUp(self):
        self._tmp_dirs = []
        self._uv_tool_dir = self._mkdtemp("modelb-axi-c3-e2e-uvtool-")
        self._uv_tool_bin_dir = self._mkdtemp("modelb-axi-c3-e2e-uvbin-")
        self._tmp_home = self._mkdtemp("modelb-axi-c3-e2e-home-")
        self._tmp_target_root = self._mkdtemp("modelb-axi-c3-e2e-target-root-")
        self._tmp_init_target = self._mkdtemp("modelb-axi-c3-e2e-init-target-")

    def _mkdtemp(self, prefix: str) -> str:
        path = tempfile.mkdtemp(prefix=prefix)
        self._tmp_dirs.append(path)
        return path

    def tearDown(self):
        for root in self._tmp_dirs:
            shutil.rmtree(root, ignore_errors=True)

    def test_s6_installed_wheel_init_renders_pi_agents_from_packaged_assets(self):
        uv = shutil.which("uv")
        if uv is None:
            self.fail(
                "installed-wheel e2e: `uv` binary not found on PATH -- "
                "cannot verify installability (guarded, not skipped)"
            )
        install_env = dict(os.environ)
        install_env["UV_TOOL_DIR"] = self._uv_tool_dir
        install_env["UV_TOOL_BIN_DIR"] = self._uv_tool_bin_dir
        install = subprocess.run(
            [uv, "tool", "install", str(REPO_ROOT), "--force"],
            capture_output=True, text=True, timeout=240, env=install_env,
        )
        self.assertEqual(
            install.returncode, 0,
            f"`uv tool install {REPO_ROOT} --force` must exit 0; got "
            f"exit={install.returncode}\nstdout={install.stdout[-2000:]}"
            f"\nstderr={install.stderr[-2000:]}",
        )
        installed_bin = Path(self._uv_tool_bin_dir) / "modelb-axi"
        self.assertTrue(installed_bin.exists(), f"{installed_bin} must exist")

        run_env = dict(os.environ)
        # The dev-mode repo copy of modelb_axi must never shadow the
        # installed package.
        run_env.pop("PYTHONPATH", None)

        # Stage 1: a real installer run -> install.toml with asset_root
        # pointing INSIDE the installed package, harnesses=[pi].
        installer_result = subprocess.run(
            [str(installed_bin), "--yes", "--harnesses", "pi",
             "--modelb-home", self._tmp_home,
             "--target-root", self._tmp_target_root],
            capture_output=True, text=True, timeout=60,
            stdin=subprocess.DEVNULL, env=run_env,
        )
        self.assertEqual(
            installer_result.returncode, 0,
            f"installed `modelb-axi` installer run must exit 0; got "
            f"exit={installer_result.returncode} "
            f"stdout={installer_result.stdout!r} stderr={installer_result.stderr!r}",
        )
        install_toml_path = Path(self._tmp_home) / "install.toml"
        with open(install_toml_path, "rb") as fh:
            data = tomllib.load(fh)
        asset_root = Path(str(data.get("install", {}).get("asset_root", "")))
        self.assertEqual(
            asset_root.parts[-2:], ("modelb_axi", "_assets"),
            f"[install].asset_root must point inside the installed "
            f"package (.../modelb_axi/_assets); got {asset_root}",
        )

        # Stage 2: `init` from the SAME installed binary -- never REPO_ROOT.
        init_result = subprocess.run(
            [str(installed_bin), "--yes", "init",
             "--name", "X", "--token", "xproj", "--acronym", "XP",
             "--mode", "solo", "--repo-shape", "standalone",
             "--stacks", "python", "--owner", "tester",
             "--target", self._tmp_init_target,
             "--modelb-home", self._tmp_home],
            capture_output=True, text=True, timeout=60,
            stdin=subprocess.DEVNULL, env=run_env,
        )
        self.assertEqual(
            init_result.returncode, 0,
            f"installed `modelb-axi init` must exit 0 (never a repo "
            f"checkout -- REPO_ROOT is not even on PYTHONPATH here); got "
            f"exit={init_result.returncode} stdout={init_result.stdout!r} "
            f"stderr={init_result.stderr!r}",
        )
        agents_dir = Path(self._tmp_init_target) / PI_AGENTS_RELDIR
        found = sorted(p.name for p in agents_dir.glob("*")) if agents_dir.is_dir() else []
        expected = sorted(f"python-{role}-agent.md" for role in ROLES)
        self.assertEqual(
            found, expected,
            f"S6 AC2: installed-wheel init must render exactly {expected} "
            f"under {agents_dir}; found {found}",
        )
        # POSITIVE/EXACT -- the packaged-asset render is byte-identical to
        # this dev checkout's own agents.render() (same template content,
        # force-included verbatim into the wheel).
        params = agents_mod.load_stack_params(STACKS_DIR, "python")
        for role in ROLES:
            written = (agents_dir / f"python-{role}-agent.md").read_text(encoding="utf-8")
            expected_content = agents_mod.render("python", role, params, TEMPLATES_DIR, harness="pi")
            self.assertEqual(
                written, expected_content,
                f"S6 AC2: installed-wheel python-{role}-agent.md must be "
                f"byte-identical to this checkout's agents.render() output",
            )


class AgentsCliReRenderS6Test(unittest.TestCase):
    """\u00a7S6 AC3 -- `modelb-axi agents` in an initialised project re-renders
    from `PROJECT_STACKS`, touching nothing else; `--stacks python,rust`
    adds the four rust definitions and rewrites `PROJECT_STACKS`.

    Written before the `agents` CLI subcommand exists at all -- every
    invocation below fails at the argparse level (unrecognised subcommand)
    against the current tree.
    """

    def setUp(self):
        self._result, self._home, self._asset_root, self._target = _init_pi_project(
            "modelb-axi-c3-s6-rerender",
        )
        self.assertEqual(
            self._result.returncode, 0,
            f"S6 fixture precondition: init must succeed; "
            f"stderr={self._result.stderr!r}",
        )

    def tearDown(self):
        for root in (self._home, self._asset_root, self._target):
            shutil.rmtree(root, ignore_errors=True)

    def test_s6_agents_verb_rerenders_after_template_change_and_touches_no_other_file(self):
        before = _snapshot_hashes(self._target)
        # Mutate the RED template in the PRIVATE asset-root copy only --
        # never the real repo (sandbox-guard rule).
        red_template = self._asset_root / "generator" / "templates" / "red.md.tmpl"
        original = red_template.read_text(encoding="utf-8")
        marker_text = "S6-C3-TEMPLATE-CHANGE-PROBE"
        red_template.write_text(original + f"\n{marker_text}\n", encoding="utf-8")

        result = _run_module_c3(
            "--modelb-home", str(self._home), "agents",
            cwd=str(self._target),
        )
        self.assertEqual(
            result.returncode, 0,
            f"S6 AC3: `modelb-axi agents` must exit 0; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        after = _snapshot_hashes(self._target)

        red_path_rel = str(Path(".pi") / "agents" / "python-red-agent.md")
        # POSITIVE -- the RED definition actually picked up the changed
        # template's new content.
        self.assertIn(
            marker_text,
            (self._target / PI_AGENTS_RELDIR / "python-red-agent.md").read_text(encoding="utf-8"),
            "S6 AC3: re-render must pick up the changed RED template",
        )
        # NEGATIVE/EXACT -- the ONLY relpath whose content changed is the
        # one whose SOURCE template changed; every other file in the whole
        # target tree (including the other three .pi/agents/*.md files) is
        # untouched.
        changed = {p for p in before if before.get(p) != after.get(p)} | (set(after) - set(before))
        self.assertEqual(
            changed, {red_path_rel},
            f"S6 AC3: `modelb-axi agents` must change no file other than "
            f"the one whose template changed; got changed={changed!r}",
        )

    def test_s6_agents_verb_with_stacks_flag_adds_rust_and_rewrites_project_stacks(self):
        result = _run_module_c3(
            "--modelb-home", str(self._home), "agents", "--stacks", "python,rust",
            cwd=str(self._target),
        )
        self.assertEqual(
            result.returncode, 0,
            f"S6 AC3: `modelb-axi agents --stacks python,rust` must exit "
            f"0; got exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        agents_dir = self._target / PI_AGENTS_RELDIR
        found = sorted(p.name for p in agents_dir.glob("*"))
        expected = sorted(
            f"{stack}-{role}-agent.md" for stack in ("python", "rust") for role in ROLES
        )
        # POSITIVE/EXACT -- python's four files survive AND rust's four
        # new ones appear; nothing else.
        self.assertEqual(
            found, expected,
            f"S6 AC3: --stacks python,rust must yield exactly {expected}; found {found}",
        )
        params = agents_mod.load_stack_params(STACKS_DIR, "rust")
        for role in ROLES:
            written = (agents_dir / f"rust-{role}-agent.md").read_text(encoding="utf-8")
            expected_content = agents_mod.render("rust", role, params, TEMPLATES_DIR, harness="pi")
            self.assertEqual(
                written, expected_content,
                f"S6 AC3: rust-{role}-agent.md must be byte-identical to "
                f"agents.render('rust', {role!r}, ...)",
            )
        env = _parse_env_file_c3(self._target / ".env")
        stacks_value = env.get("PROJECT_STACKS", "")
        # POSITIVE/EXACT (order-independent) -- PROJECT_STACKS is
        # rewritten to name both stacks, comma-separated.
        self.assertEqual(
            {s.strip() for s in stacks_value.split(",") if s.strip()},
            {"python", "rust"},
            f"S6 AC3: `.env` PROJECT_STACKS must be rewritten to name both "
            f"stacks (order-independent); got {stacks_value!r}",
        )
        self.assertIn(
            ",", stacks_value,
            f"S6 AC3: PROJECT_STACKS must be comma-separated; got {stacks_value!r}",
        )


class AgentsAxiEnvelopeS6Test(unittest.TestCase):
    """\u00a7S6 AC6 -- `modelb-axi agents` emits exactly ONE AXI envelope on
    stdout (verb `agents`), listing each rendered file's outcome."""

    def setUp(self):
        self._result, self._home, self._asset_root, self._target = _init_pi_project(
            "modelb-axi-c3-s6-envelope",
        )
        self.assertEqual(self._result.returncode, 0, self._result.stderr)

    def tearDown(self):
        for root in (self._home, self._asset_root, self._target):
            shutil.rmtree(root, ignore_errors=True)

    def test_s6_agents_verb_stdout_is_exactly_one_envelope_naming_verb_agents(self):
        result = _run_module_c3(
            "--modelb-home", str(self._home), "agents", cwd=str(self._target),
        )
        self.assertEqual(
            result.returncode, 0,
            f"S6 AC6: `modelb-axi agents` must exit 0; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        try:
            envelope = _decode_envelope_c3(result.stdout)
        except Exception as exc:
            self.fail(
                f"S6 AC6: `modelb-axi agents` stdout must parse as a TOON "
                f"envelope; decode failed with {exc!r} on "
                f"stdout={result.stdout!r}"
            )
        axi = envelope.get("axi", {})
        self.assertEqual(
            axi.get("verb"), "agents",
            f"S6 AC6: envelope axi.verb must be 'agents'; got envelope={envelope!r}",
        )
        self.assertIs(
            axi.get("ok"), True,
            f"S6 AC6: a clean re-render must report ok:true; got envelope={envelope!r}",
        )

    def test_s6_agents_verb_envelope_lists_each_files_outcome(self):
        result = _run_module_c3(
            "--modelb-home", str(self._home), "agents", cwd=str(self._target),
        )
        self.assertEqual(
            result.returncode, 0,
            f"S6 AC6: `modelb-axi agents` must exit 0; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        envelope = _decode_envelope_c3(result.stdout)
        for role in ROLES:
            rel = str(Path(".pi") / "agents" / f"python-{role}-agent.md")
            found = (
                _find_path_in_envelope_bucket(envelope, rel, "written")
                or _find_path_in_envelope_bucket(envelope, rel, "unchanged")
            )
            self.assertTrue(
                found,
                f"S6 AC6: {rel} must be listed under a 'written' or "
                f"'unchanged' outcome field in the envelope; got "
                f"envelope={envelope!r}",
            )


class InstallerWritesNoAgentsS6Test(unittest.TestCase):
    """\u00a7S6 AC5 -- the installer writes nothing under any agents directory,
    and `install.toml` carries no agent key."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-c3-s6-noagents-home-")
        self._tmp_target_root = tempfile.mkdtemp(prefix="modelb-axi-c3-s6-noagents-target-")

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_target_root, ignore_errors=True)

    def test_s6_installer_run_writes_no_pi_agents_directory(self):
        result = _run_module_c3(
            "--yes", "--harnesses", "pi",
            "--modelb-home", self._tmp_home,
            "--target-root", self._tmp_target_root,
        )
        self.assertEqual(
            result.returncode, 0,
            f"S6 fixture precondition: installer run must succeed; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        agents_dir = Path(self._tmp_target_root) / PI_AGENTS_RELDIR
        # NEGATIVE -- the installer must write NOTHING under any agents
        # directory.
        self.assertFalse(
            agents_dir.exists(),
            f"S6 AC5: the installer must write NOTHING under any agents "
            f"directory; found {agents_dir}",
        )

    def test_s6_install_toml_carries_no_agent_key(self):
        result = _run_module_c3(
            "--yes", "--harnesses", "pi",
            "--modelb-home", self._tmp_home,
            "--target-root", self._tmp_target_root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        install_toml_path = Path(self._tmp_home) / "install.toml"
        with open(install_toml_path, "rb") as fh:
            data = tomllib.load(fh)
        install_section = data.get("install", {})
        agent_keys = [k for k in install_section if "agent" in k.lower()]
        # NEGATIVE/EXACT -- zero [install] keys name "agent".
        self.assertEqual(
            agent_keys, [],
            f"S6 AC5: [install] must carry no agent key; got "
            f"install_section={install_section!r}",
        )
        agent_file_entries = [
            entry for entry in data.get("files", [])
            # Path-COMPONENT match ("agents" as an exact path segment, or
            # the generated `<stack>-<role>-agent.md` filename suffix) --
            # never a bare substring: every deployed skill lives under the
            # `.agents/` STORE dir, whose name itself contains "agent" as a
            # substring, which would false-positive on every entry.
            if "agents" in Path(str(entry.get("path", ""))).parts
            or str(entry.get("path", "")).endswith("-agent.md")
        ]
        # NEGATIVE/EXACT -- zero [[files]] manifest entries name "agent".
        self.assertEqual(
            agent_file_entries, [],
            f"S6 AC5: install.toml's [[files]] manifest must carry no "
            f"agent-path entry; got {agent_file_entries!r}",
        )


class AgentOwnershipRulesS6Test(unittest.TestCase):
    """\u00a7S6 Ownership AC -- one subtest per rule: a missing file is
    written; an intact marked file is rewritten (content updates when its
    template does); a hand-modified marked file is skipped as
    `hand_modified` unless `--force-managed`, which overwrites it; a
    same-named file with no marker is NEVER written (not even with
    `--force-managed`) and is reported `unmanaged`; a file of another name
    in the directory is left completely untouched.
    """

    def setUp(self):
        self._result, self._home, self._asset_root, self._target = _init_pi_project(
            "modelb-axi-c3-s6-ownership",
        )
        self.assertEqual(
            self._result.returncode, 0,
            f"S6 fixture precondition: init must succeed; "
            f"stderr={self._result.stderr!r}",
        )
        self._agents_dir = self._target / PI_AGENTS_RELDIR

    def tearDown(self):
        for root in (self._home, self._asset_root, self._target):
            shutil.rmtree(root, ignore_errors=True)

    def _run_agents(self, *extra_args):
        return _run_module_c3(
            "--modelb-home", str(self._home), "agents", *extra_args,
            cwd=str(self._target),
        )

    def test_s6_ownership_missing_file_is_written(self):
        target_file = self._agents_dir / "python-fix-agent.md"
        self.assertTrue(
            target_file.is_file(),
            f"S6 Ownership fixture precondition: `init` must already have "
            f"rendered {target_file} (\u00a7S6 AC1) before this test can delete "
            f"it and prove re-render",
        )
        target_file.unlink()
        self.assertFalse(target_file.exists())

        result = self._run_agents()
        self.assertEqual(result.returncode, 0, result.stderr)
        # POSITIVE -- the missing file reappears, rendered.
        self.assertTrue(
            target_file.is_file(),
            f"S6 Ownership: a missing rendered file must be (re)written; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        rel = str(Path(".pi") / "agents" / "python-fix-agent.md")
        envelope = _decode_envelope_c3(result.stdout)
        self.assertTrue(
            _find_path_in_envelope_bucket(envelope, rel, "written"),
            f"S6 Ownership: {rel} must be reported under a 'written' "
            f"outcome; got envelope={envelope!r}",
        )

    def test_s6_ownership_intact_marked_file_is_rewritten_on_template_change(self):
        target_file = self._agents_dir / "python-green-agent.md"
        self.assertTrue(
            target_file.is_file(),
            f"S6 Ownership fixture precondition: `init` must already have "
            f"rendered {target_file} (\u00a7S6 AC1)",
        )
        before = target_file.read_text(encoding="utf-8")

        green_template = self._asset_root / "generator" / "templates" / "green.md.tmpl"
        green_template.write_text(
            green_template.read_text(encoding="utf-8") + "\nS6-OWNERSHIP-REWRITE-PROBE\n",
            encoding="utf-8",
        )
        result = self._run_agents()
        self.assertEqual(result.returncode, 0, result.stderr)
        after = target_file.read_text(encoding="utf-8")

        # POSITIVE -- content actually changed to the new render.
        self.assertNotEqual(
            before, after,
            "S6 Ownership: an intact-marker file must be REWRITTEN "
            "(picking up the changed template), not left as-is",
        )
        self.assertIn("S6-OWNERSHIP-REWRITE-PROBE", after)
        rel = str(Path(".pi") / "agents" / "python-green-agent.md")
        envelope = _decode_envelope_c3(result.stdout)
        self.assertTrue(
            _find_path_in_envelope_bucket(envelope, rel, "written"),
            f"S6 Ownership: a changed, intact-marker file must be "
            f"reported 'written'; got envelope={envelope!r}",
        )

    def test_s6_ownership_hand_modified_marked_file_skipped_then_forced(self):
        target_file = self._agents_dir / "python-verify-agent.md"
        self.assertTrue(
            target_file.is_file(),
            f"S6 Ownership fixture precondition: `init` must already have "
            f"rendered {target_file} (\u00a7S6 AC1)",
        )
        rendered = target_file.read_text(encoding="utf-8")
        frontmatter, _ = _split_frontmatter(rendered)
        marker = _marker_line(frontmatter)
        self.assertIsNotNone(
            marker,
            f"S6 Ownership fixture precondition: a rendered file must "
            f"carry the ownership marker comment inside its frontmatter "
            f"(a '#'-prefixed line naming the generator + a 64-hex "
            f"sha256, per the AC's own wording); got frontmatter={frontmatter!r}",
        )
        hand_edited = rendered.replace("description:", "description: HAND-EDITED", 1)
        self.assertNotEqual(hand_edited, rendered)
        target_file.write_text(hand_edited, encoding="utf-8")

        # Without --force-managed: left untouched, reported hand_modified.
        result = self._run_agents()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            target_file.read_text(encoding="utf-8"), hand_edited,
            "S6 Ownership: a hand-modified marked file must be left "
            "byte-identical to the hand edit without --force-managed",
        )
        rel = str(Path(".pi") / "agents" / "python-verify-agent.md")
        envelope = _decode_envelope_c3(result.stdout)
        reported = (
            _find_path_in_envelope_bucket(envelope, rel, "skipped")
            or _find_path_in_envelope_bucket(envelope, rel, "hand_modified")
        )
        self.assertTrue(
            reported,
            f"S6 Ownership: {rel} must be reported skipped/hand_modified; "
            f"got envelope={envelope!r} stderr={result.stderr!r}",
        )

        # With --force-managed: overwritten, back to a fresh render.
        forced = _run_module_c3(
            "--modelb-home", str(self._home), "--force-managed", "agents",
            cwd=str(self._target),
        )
        self.assertEqual(forced.returncode, 0, forced.stderr)
        params = agents_mod.load_stack_params(STACKS_DIR, "python")
        expected = agents_mod.render("python", "verify", params, TEMPLATES_DIR, harness="pi")
        self.assertEqual(
            target_file.read_text(encoding="utf-8"), expected,
            "S6 Ownership: --force-managed must overwrite a hand-modified "
            "marked file back to a fresh render",
        )

    def test_s6_ownership_file_with_no_marker_never_written_reported_unmanaged(self):
        target_file = self._agents_dir / "python-red-agent.md"
        self.assertTrue(
            target_file.is_file(),
            f"S6 Ownership fixture precondition: `init` must already have "
            f"rendered {target_file} (\u00a7S6 AC1)",
        )
        rendered = target_file.read_text(encoding="utf-8")
        frontmatter, _ = _split_frontmatter(rendered)
        marker = _marker_line(frontmatter)
        self.assertIsNotNone(marker, "fixture precondition: marker must be present")
        assert marker is not None  # narrows for the type checker; proven above
        no_marker_content = _strip_exact_line(rendered, marker)
        self.assertNotIn(
            marker.strip(), no_marker_content,
            "fixture precondition: the marker line must be fully removed",
        )
        target_file.write_text(no_marker_content, encoding="utf-8")

        result = self._run_agents("--force-managed")
        self.assertEqual(result.returncode, 0, result.stderr)
        # POSITIVE/EXACT -- byte-identical to the no-marker fixture: not
        # even --force-managed adopts an unmarked file (deploy.py's own
        # "no flag overwrites it" rule, applied here).
        self.assertEqual(
            target_file.read_text(encoding="utf-8"), no_marker_content,
            "S6 Ownership: a same-named file with no marker must NEVER be "
            "written, not even with --force-managed",
        )
        rel = str(Path(".pi") / "agents" / "python-red-agent.md")
        envelope = _decode_envelope_c3(result.stdout)
        self.assertTrue(
            _find_path_in_envelope_bucket(envelope, rel, "unmanaged"),
            f"S6 Ownership: {rel} must be reported 'unmanaged'; got "
            f"envelope={envelope!r}",
        )

    def test_s6_ownership_file_of_another_name_left_completely_untouched(self):
        # Fixture setup only (not a production-behaviour assumption): the
        # AC's own wording ("a file of ANOTHER NAME IN THE DIRECTORY")
        # presupposes the directory exists -- true once \u00a7S6 lands (init
        # already populated it with the four generated files in setUp).
        self._agents_dir.mkdir(parents=True, exist_ok=True)
        other_file = self._agents_dir / "custom-hand-authored-notes.md"
        other_content = "# not a generated agent\n\nhand-authored, unrelated filename.\n"
        other_file.write_text(other_content, encoding="utf-8")
        other_mtime_before = other_file.stat().st_mtime_ns

        result = self._run_agents("--force-managed")
        self.assertEqual(result.returncode, 0, result.stderr)

        self.assertTrue(other_file.is_file(), "must not be deleted")
        self.assertEqual(
            other_file.read_text(encoding="utf-8"), other_content,
            "S6 Ownership: a file of another name in the directory must "
            "be left byte-identical",
        )
        self.assertEqual(
            other_file.stat().st_mtime_ns, other_mtime_before,
            "S6 Ownership: a file of another name must not even be "
            "touched (mtime must be unchanged)",
        )


# ---------------------------------------------------------------------------
# \u00a7S8 -- the released client in the generator inputs (moved from CR-MDB-020
# \u00a7S2 by user ruling 2026-09-23, committed 0246f6a). The three command
# strings in every generator/stacks/*.toml name the released Crucible client
# ~/.crucible/clients/<client>-crucible.py, never the retired mirror
# ~/.claude/scripts/<client>-crucible.py (absent on a Pi install, so First
# Action 1 of every rendered definition could not run). Measured at 0246f6a:
# arduino/bun/python/quarkus carry the retired form in all three commands
# (17 occurrences each across stacks + rendered output); rust alone already
# carries the released form. `crucible_reference` is out of this scope and
# must stay byte-identical to its 0246f6a value.
# ---------------------------------------------------------------------------

RELEASED_CLIENT_DIR = "~/.crucible/clients/"
# The client script each stack's commands invoke (quarkus drives Maven, so
# its client is mvn-crucible.py -- the released filename under
# ~/.crucible/clients/, measured 2026-09-23).
STACK_CLIENT_SCRIPT = {
    "arduino": "arduino-crucible.py",
    "bun": "bun-crucible.py",
    "python": "python-crucible.py",
    "quarkus": "mvn-crucible.py",
    "rust": "rust-crucible.py",
}
S8_COMMAND_KEYS = ("test_command", "register_command", "unregister_command")
# \u00a7S8 AC1 "crucible_reference is unchanged" -- the exact 0246f6a values.
CRUCIBLE_REFERENCE_AT_0246F6A = {
    "arduino": (
        "~/.claude/skills/crucible/SKILL.md (no per-stack reference file for arduino "
        "yet \u2014 client limits: `arduino-crucible.py` currently offers the `unit` and "
        "`compile` tiers with `--project-dir sheetal-firmware`; the `regression` tier "
        "with lcov coverage lands with CR-SHE-006 \u2014 until then use `unit`)"
    ),
    "bun": "~/.claude/skills/crucible/references/bun.md",
    "python": "~/.claude/skills/crucible/references/python.md",
    "quarkus": "~/.claude/skills/crucible/references/java.md",
    "rust": "~/.agents/skills/crucible/references/rust.md",
}
# A path-qualified client token: everything up to the last '/' is the
# directory, the rest is the <client>-crucible.py script name.
CLIENT_PATH_TOKEN_RE = re.compile(r"([~\w./-]*/)([\w-]+-crucible\.py)")
# \u00a7S8 AC2 -- the retired mirror paired with a crucible client.
RETIRED_CLIENT_PATH_RE = re.compile(r"\.claude/scripts/[\w./-]*-crucible\.py")


def _retired_client_paths(text: str) -> list:
    """\u00a7S8 AC2 -- every `.claude/scripts/...-crucible.py` pairing in ``text``."""
    return RETIRED_CLIENT_PATH_RE.findall(text)


def _non_released_client_tokens(text: str) -> list:
    """\u00a7S8 AC3 -- every path-qualified `*-crucible.py` token in ``text`` whose
    directory is not the released ~/.crucible/clients/."""
    return [
        d + s for d, s in CLIENT_PATH_TOKEN_RE.findall(text)
        if d != RELEASED_CLIENT_DIR
    ]


class ReleasedClientPathS8Test(unittest.TestCase):
    """\u00a7S8 -- the generator inputs and the rendered fleet name the released
    Crucible client, never the retired ~/.claude/scripts/ mirror."""

    def _stack_toml(self, stack: str) -> dict:
        path = STACKS_DIR / f"{stack}.toml"
        self.assertTrue(path.is_file(), f"{path} must exist")
        with path.open("rb") as fh:
            return tomllib.load(fh)

    def test_s8_every_stack_toml_command_string_names_the_released_client(self):
        problems = []
        for stack in STACKS:
            data = self._stack_toml(stack)
            expected = RELEASED_CLIENT_DIR + STACK_CLIENT_SCRIPT[stack]
            for key in S8_COMMAND_KEYS:
                value = data.get(key)
                if not isinstance(value, str):
                    problems.append(f"{stack}.toml: {key} missing or not a string")
                    continue
                tokens = [d + s for d, s in CLIENT_PATH_TOKEN_RE.findall(value)]
                if tokens != [expected]:
                    problems.append(
                        f"{stack}.toml: {key} names {tokens}, expected exactly [{expected!r}]"
                    )
        self.assertEqual(problems, [], "\n".join(problems))

    def test_s8_crucible_reference_is_unchanged_from_0246f6a(self):
        changed = []
        for stack in STACKS:
            actual = self._stack_toml(stack).get("crucible_reference")
            if actual != CRUCIBLE_REFERENCE_AT_0246F6A[stack]:
                changed.append(f"{stack}.toml: crucible_reference = {actual!r}")
        self.assertEqual(changed, [], "\n".join(changed))

    def test_s8_detector_bites_on_retired_client_path_but_not_on_released(self):
        retired = "python3 ~/.claude/scripts/python-crucible.py register --agent X"
        released = "python3 ~/.crucible/clients/python-crucible.py register --agent X"
        unrelated = "see ~/.claude/scripts/toon.py and `arduino-crucible.py` (bare)"
        self.assertEqual(
            _retired_client_paths(retired), [".claude/scripts/python-crucible.py"]
        )
        self.assertEqual(_retired_client_paths(released), [])
        self.assertEqual(_retired_client_paths(unrelated), [])
        self.assertEqual(
            _non_released_client_tokens(retired), ["~/.claude/scripts/python-crucible.py"]
        )
        self.assertEqual(_non_released_client_tokens(released), [])

    def test_s8_zero_retired_client_paths_under_generator_templates_stacks_and_agents(self):
        files = _generator_content_files()
        self.assertTrue(files, "no generator content files found")
        hits = []
        for path in files:
            for match in _retired_client_paths(_read(path)):
                hits.append(f"{path.relative_to(REPO_ROOT)}: {match}")
        self.assertEqual(hits, [], "\n".join(hits))

    def test_s8_all_twenty_rendered_definitions_carry_the_released_client_form(self):
        files = _all_agent_files()
        self.assertEqual(len(files), len(STACKS) * len(ROLES), [f.name for f in files])
        problems = []
        for path in files:
            stack = path.name.split("-", 1)[0]
            client = RELEASED_CLIENT_DIR + STACK_CLIENT_SCRIPT[stack]
            text = _read(path)
            for verb in ("register", "unregister"):
                if f"{client} {verb} --agent" not in text:
                    problems.append(f"{path.name}: no `{client} {verb} --agent` command")
            stray = _non_released_client_tokens(text)
            if stray:
                problems.append(f"{path.name}: non-released client paths {sorted(set(stray))}")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_s8_build_check_is_clean(self):
        result = subprocess.run(
            [sys.executable, str(BUILD_PY), "--check"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(
            result.returncode, 0,
            f"build.py --check must be clean:\n{result.stdout}\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
