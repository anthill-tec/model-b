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

Stdlib only: unittest + tomllib + re + shutil + subprocess + sys + tempfile
+ importlib.util + pathlib, matching the sibling generator test modules'
existing conventions.
"""

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

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

# §S5 AC2 -- no rendered body names this token (case-sensitive, word-
# boundary matched so lowercase markdown fence tags like ```bash`` never
# false-positive).
BASH_TOKEN_RE = re.compile(r"\bBash\b")

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


def _role_of(agent_filename: str) -> str:
    stem = agent_filename[: -len("-agent.md")]
    return stem.rsplit("-", 1)[-1]


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


if __name__ == "__main__":
    unittest.main()
