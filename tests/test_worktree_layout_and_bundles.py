"""Worktree layout, bundles and contracts — CR-MDB-031 §S3 (worktree convention) and §S4 (bundles and
contracts), cycle C3.

Contract: ``docs/changes/CR-MDB-031-claude-era-substrate-retirement.md`` §S0.1–§S0.2, §S3, §S4 and
the matching acceptance criteria. Worktrees live at ``.worktrees/<cr>`` inside the repository, the
string is declared once in ``contracts/worktree-layout.md`` and six consumers carry it; the
``chezmoi`` bundle is retired; ``contracts/mail-axi.md`` moves to ``archive/``; ``contracts/lean-ctx.md``
is rewritten against Pi and the ``pi-lean-ctx`` extension; ``contracts/`` stops shipping in the wheel.

Class map (one per C3 acceptance criterion or part of one):

- ``WorktreeLayoutContractTest`` — ``contracts/worktree-layout.md`` declares exactly
  ``.worktrees/<cr>``, the §S0.1 placement rationale (project trust + permission scope) and names
  its six consumers.
- ``WorktreeConsumersTest`` — PARSES the six consumers: the hook's ``_WORKTREES_SEGMENT``
  constant, ``worktree-flow.py``'s ``WORKTREE_SUBDIR`` and its docstring ``start`` usage line, and
  every ``…worktrees/<cr>`` spelling in the four skill files; each carries exactly the declared
  string.
- ``LegacyWorktreeSegmentGateTest`` — ``.claude/worktrees`` appears nowhere in the shipped
  surfaces (the C2 ``~/.claude`` gate's surfaces plus ``contracts/``).
- ``WorktreeLayoutBehaviourTest`` — the real ``block-write-outside-worktree`` hook, self-gating from
  its cwd (no ``$WF_WORKTREE_ROOT``), allows a write inside ``<repo>/.worktrees/<cr>/`` and blocks
  one outside; a legacy ``.claude/worktrees/<cr>`` cwd is not a worktree context; the real
  ``worktree-flow.py start`` creates ``<main>/.worktrees/<cr>`` and the hook enforces that tree.
- ``ChezmoiBundleRetiredTest`` — ``skills-src/chezmoi/`` is gone, the deploy engine discovers no
  ``chezmoi`` bundle, and ``chezmoi`` appears nowhere in ``skills-src/``, ``generator/``,
  ``contracts/`` or ``modelb_axi/``.
- ``AgentsMdBundleListTest`` — ``AGENTS.md``'s ``skills-src/`` row states 13 bundles, lists 7
  Model-B-owned and 6 imported, matches what the deploy engine discovers, and nothing in
  ``AGENTS.md`` names ``chezmoi`` as a bundle or skill.
- ``MailAxiArchivedTest`` — ``mail-axi.md`` exists only at ``archive/contracts/mail-axi.md``
  (the location this RED picks), byte-identical to the file it moved from.
- ``ContractsHarnessNeutralTest`` — the C2 gates extended to ``contracts/``: zero ``~/.claude``,
  zero ``CLAUDE.md``, zero ``/tmp/claude-1000`` and zero Crucible "wrapper" instruction in
  ``contracts/``; zero harness tool names in ``contracts/lean-ctx.md`` (the AC scopes the tool gate
  to that file — see the note below); ``lean-ctx.md`` names Pi and ``pi-lean-ctx``.
- ``ContractsNotPackagedTest`` — ``pyproject.toml`` force-includes no ``contracts`` and a wheel
  built from the sdist carries no ``modelb_axi/_assets/contracts/``.

Tool-gate scope. The dispatch asked for zero harness tool names across ``contracts/``; the AC
("``contracts/lean-ctx.md`` … passes the ``~/.claude``, ``CLAUDE.md`` and tool gates") scopes the
tool gate to ``lean-ctx.md``, and ``contracts/sandesh-cli.md:10-12`` names Sandesh's own MCP verbs
(``sandesh_send`` …) as the surface its contract replaces. The AC is the source of truth here.

Every vocabulary (patterns, surfaces, scanners) is IMPORTED from ``tests/test_harness_neutral_skills.py``,
the hook runner from ``tests/test_hooks.py``, the ``worktree-flow.py`` runner and fixture repo from
``tests/test_worktree_flow_dbless.py``, and the build helpers from ``tests/test_package_publishing.py``
— never copied. Every scan gate has a detector fixture proving it bites and spares what it must.
Sandbox: every repository and build lives under a temp dir; nothing reads or writes the real home.
Stdlib only.
"""

import ast
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests._helpers import REPO_ROOT
from tests.test_harness_neutral_skills import (
    CLAUDE_HOME_RE,
    CLAUDE_HOME_SURFACES,
    CLAUDE_MD_RE,
    CRUCIBLE_WRAPPER_RE,
    HARNESS_TOOL_RE,
    TMP_CLAUDE_RE,
    _fixture_root,
    _gate_hits,
    _report,
)
from tests.test_hooks import _run_script
from tests.test_package_publishing import _pyproject, build_sdist, build_wheel, wheel_names
from tests.test_worktree_flow_dbless import _dbless_project, _run_wf

# ------------------------------------------------------------------ §S3 constants ----

#: The one worktree string §S0.1 rules and ``contracts/worktree-layout.md`` declares.
DECLARED_WORKTREE = ".worktrees/<cr>"
#: Its directory segment, as the two code consumers spell it.
DECLARED_SUBDIR = ".worktrees"
WORKTREE_LAYOUT_MD = REPO_ROOT / "contracts" / "worktree-layout.md"
HOOK_SCRIPT = "hooks-src/scripts/block-write-outside-worktree"
WORKTREE_FLOW = "scripts/worktree-flow.py"
SKILL_CONSUMERS = (
    "skills-src/bootstrap/SKILL.md",
    "skills-src/shutdown/SKILL.md",
    "skills-src/model-b/references/orchestration-track.md",
    "skills-src/model-b/references/sub-agent-procedure.md",
)
#: The six consumers §S3 and the AC name, in the AC's order.
WORKTREE_CONSUMERS = (HOOK_SCRIPT, WORKTREE_FLOW) + SKILL_CONSUMERS

#: The shipped surfaces: the C2 ``~/.claude`` gate's surfaces plus ``contracts/`` (C3's addition).
SHIPPED_SURFACES = CLAUDE_HOME_SURFACES + ("contracts",)
LEGACY_WORKTREE_RE = re.compile(r"\.claude/worktrees")
#: Every path token ending in ``worktrees/<cr>`` (``…/.claude/worktrees/<cr>``, ``/.worktrees/<cr>``).
WORKTREE_SPELLING_RE = re.compile(r"[^\s`'\"()\[\]]*worktrees/<cr>")
#: ``worktree-flow.py``'s docstring usage line for ``start``; group 1 is the worktree path.
FLOW_START_USAGE_RE = re.compile(r"^\s*start\s+git worktree add -b \S+ (\S+) <base>\.?\s*$")

#: A write target no test ever creates; outside every tmp root, so the hook's scratch allow
#: (``/tmp``, ``$TMPDIR``) cannot spare it.
OUTSIDE_TARGET = "/etc/modelb-c3-outside-worktree-fixture.txt"
#: Neutralise the hook's explicit signal and escape hatch so only cwd derivation (b) is exercised.
NO_DISPATCH_SIGNAL = {"WF_WORKTREE_ROOT": "", "ALLOW_WRITE_OUTSIDE_WORKTREE": ""}

# ------------------------------------------------------------------ §S4 constants ----

CHEZMOI_SURFACES = ("skills-src", "generator", "contracts", "modelb_axi")
CHEZMOI_RE = re.compile(r"chezmoi", re.IGNORECASE)
#: ``chezmoi`` named as a bundle or skill: a backticked list element, "`chezmoi` skill",
#: "chezmoi bundle", or the bundle's directory.
CHEZMOI_AS_BUNDLE_RE = re.compile(
    r"`chezmoi`\s*(?:skill|bundle|,)|,\s*`chezmoi`|\bchezmoi\s+(?:skill|bundle)\b|skills-src/chezmoi",
    re.IGNORECASE,
)
AGENTS_MD = REPO_ROOT / "AGENTS.md"
#: The ``skills-src/`` row of AGENTS.md's Key Directories table.
BUNDLE_ROW_RE = re.compile(r"^\| `skills-src/` \| (\d+) skill bundles\. (.*)$", re.MULTILINE)
#: The AC's figures: 13 bundles, 6 imported from Crucible, and the Model-B-owned remainder. The
#: owned figure is DERIVED (13 - 6), never a literal: CR-MDB-023 keeps the owned set size-free
#: (``test_code_health_skill.ModelBOwnedTestSetS4Test``), so the total and the imported set carry
#: the pin.
EXPECTED_BUNDLE_COUNT, EXPECTED_IMPORTED = 13, 6
EXPECTED_OWNED = EXPECTED_BUNDLE_COUNT - EXPECTED_IMPORTED

#: Where this RED pins the archived contract (an addition to ``archive/``, §S4).
MAIL_AXI_ARCHIVED_REL = "archive/contracts/mail-axi.md"
#: sha256 of ``contracts/mail-axi.md`` as measured at C3 RED (52 lines) — a move, not an edit.
MAIL_AXI_SHA256 = "af62533f5cf59737c3f7a18d8a3fe2c00c9418f3adb1c601afaafaa944ac65ea"
LEAN_CTX_MD = REPO_ROOT / "contracts" / "lean-ctx.md"
CONTRACTS_ASSET_PREFIX = "modelb_axi/_assets/contracts/"

# ------------------------------------------------------------------ parsers ----

def _module_string_constant(source: str, name: str):
    """The string a module-level ``name = "<str>"`` assigns in ``source``, or ``None``."""
    for node in ast.parse(source).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
            return node.value.value
    return None

def _flow_start_usage_paths(source: str) -> list:
    """The worktree path of every ``start  git worktree add -b … <path> <base>.`` docstring line."""
    doc = ast.get_docstring(ast.parse(source)) or ""
    return [m.group(1) for m in map(FLOW_START_USAGE_RE.match, doc.splitlines()) if m]

def _nonconforming_worktree_spellings(text: str) -> tuple:
    """``(all spellings, the ones that are not the declared string)``. A spelling conforms when it
    IS ``.worktrees/<cr>`` or ends in ``/.worktrees/<cr>`` and carries no ``.claude``."""
    spellings = WORKTREE_SPELLING_RE.findall(text)
    bad = [s for s in spellings
           if ".claude" in s or not (s == DECLARED_WORKTREE or s.endswith("/" + DECLARED_WORKTREE))]
    return spellings, bad

def _expand_braces(name: str) -> list:
    """``crucible-report-{bun,rust}`` → ``["crucible-report-bun", "crucible-report-rust"]``."""
    match = re.fullmatch(r"(.*)\{([^}]*)\}(.*)", name)
    if not match:
        return [name]
    head, alternatives, tail = match.groups()
    return [f"{head}{alt}{tail}" for alt in alternatives.split(",")]

def _agents_md_bundle_row(text: str):
    """``(stated count, owned names, imported names)`` from the ``skills-src/`` row, or ``None``.
    Owned = backticked names after ``Model-B-owned:``; imported = backticked names after
    ``Imported from Crucible`` up to ``Plus`` (``*.md`` citations dropped, braces expanded)."""
    match = BUNDLE_ROW_RE.search(text)
    if not match:
        return None
    owned_part, _, imported_part = match.group(2).partition("Imported from Crucible")
    owned_part = owned_part.split("Model-B-owned:", 1)[-1]
    imported_part = imported_part.split("Plus", 1)[0]
    owned = [n for raw in re.findall(r"`([^`]+)`", owned_part) for n in _expand_braces(raw)]
    imported = [n for raw in re.findall(r"`([^`]+)`", imported_part)
                for n in _expand_braces(raw) if not n.endswith(".md")]
    return int(match.group(1)), owned, imported

def _mail_axi_paths(rels) -> list:
    """The repo-relative paths among ``rels`` whose file name is ``mail-axi.md``, sorted."""
    return sorted(r for r in rels if r.rsplit("/", 1)[-1] == "mail-axi.md")

# ------------------------------------------------------------------ git fixtures ----

def _git_c3(cwd: Path, *argv) -> subprocess.CompletedProcess:
    """Run git hermetically-enough for a throwaway fixture repo (identity + no hooks)."""
    return subprocess.run(
        ["git", "-c", "user.name=CR-MDB-031-C3", "-c", "user.email=cr-mdb-031@example.invalid",
         "-c", "core.hooksPath=/dev/null", *argv],
        cwd=cwd, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
    )

def _registered_worktrees(main: Path) -> list:
    """The absolute paths ``git worktree list --porcelain`` reports for ``main``."""
    out = _git_c3(main, "worktree", "list", "--porcelain").stdout
    return [line.split(" ", 1)[1] for line in out.splitlines() if line.startswith("worktree ")]

def _write_payload(target: str, cwd: Path) -> dict:
    """The neutral write payload the hook reads on stdin (tests/test_hooks.py's shape)."""
    return {"tool_name": "write", "tool_input": {"path": target, "paths": [target]}, "cwd": str(cwd)}

# =================================================================== §S3 ====

class WorktreeLayoutContractTest(unittest.TestCase):
    """AC — ``contracts/worktree-layout.md`` declares ``.worktrees/<cr>``, the placement rationale
    (§S0.1) and its six consumers."""

    def _contract(self) -> str:
        self.assertTrue(WORKTREE_LAYOUT_MD.is_file(),
                        f"§S3: {WORKTREE_LAYOUT_MD.relative_to(REPO_ROOT)} must exist and declare "
                        f"the worktree string `{DECLARED_WORKTREE}`")
        return WORKTREE_LAYOUT_MD.read_text(encoding="utf-8")

    def test_contract_declares_exactly_the_dot_worktrees_string(self):
        text = self._contract()
        declared = sorted(set(re.findall(r"`([^`\s]*worktrees/<cr>/?)`", text)))
        self.assertEqual(declared, [DECLARED_WORKTREE],
                         f"§S3: the contract must declare exactly `{DECLARED_WORKTREE}` as the "
                         f"worktree string; backticked worktree strings found: {declared}")

    def test_contract_names_all_six_consumers(self):
        text = self._contract()
        missing = [rel for rel in WORKTREE_CONSUMERS if rel not in text]
        self.assertEqual(missing, [], f"§S3: the contract must name each consumer by path; missing {missing}")

    def test_contract_states_the_placement_rationale_trust_and_permission_scope(self):
        # §S0.1: inside the project the worktree inherits Pi's project trust and the project's
        # permission scope (a sibling directory would do neither).
        text = self._contract().lower()
        missing = [w for w in ("trust", "permission") if w not in text]
        self.assertEqual(missing, [], f"§S3/§S0.1: the rationale must name {missing}")

class WorktreeConsumersTest(unittest.TestCase):
    """AC — a test parses all six consumers and finds exactly the declared string."""

    def _source(self, rel: str) -> str:
        path = REPO_ROOT / rel
        self.assertTrue(path.is_file(), f"precondition: consumer {rel} exists")
        return path.read_text(encoding="utf-8")

    def test_hook_worktrees_segment_constant_is_dot_worktrees(self):
        value = _module_string_constant(self._source(HOOK_SCRIPT), "_WORKTREES_SEGMENT")
        self.assertEqual(value, f"/{DECLARED_SUBDIR}/",
                         f"§S3: {HOOK_SCRIPT} `_WORKTREES_SEGMENT` must be '/{DECLARED_SUBDIR}/'; got {value!r}")

    def test_worktree_flow_subdir_constant_is_dot_worktrees(self):
        value = _module_string_constant(self._source(WORKTREE_FLOW), "WORKTREE_SUBDIR")
        self.assertEqual(value, DECLARED_SUBDIR,
                         f"§S3: {WORKTREE_FLOW} `WORKTREE_SUBDIR` must be {DECLARED_SUBDIR!r}; got {value!r}")

    def test_worktree_flow_docstring_start_usage_names_dot_worktrees_cr(self):
        paths = _flow_start_usage_paths(self._source(WORKTREE_FLOW))
        self.assertEqual(paths, [DECLARED_WORKTREE],
                         f"§S3: {WORKTREE_FLOW}'s docstring `start` usage line must read "
                         f"`git worktree add -b … {DECLARED_WORKTREE} <base>`; got {paths}")

    def test_every_consumer_spells_the_worktree_exactly_as_declared(self):
        for rel in WORKTREE_CONSUMERS:
            with self.subTest(consumer=rel):
                spellings, bad = _nonconforming_worktree_spellings(self._source(rel))
                self.assertTrue(spellings, f"§S3: {rel} must name the worktree `{DECLARED_WORKTREE}`")
                self.assertEqual(bad, [], f"§S3: {rel} spells the worktree other than "
                                          f"`{DECLARED_WORKTREE}`: {bad}")

    def test_detector_parsers_bite_on_the_legacy_forms_and_accept_the_declared_one(self):
        self.assertEqual(_module_string_constant('X = 1\n_WORKTREES_SEGMENT = "/.worktrees/"\n',
                                                 "_WORKTREES_SEGMENT"), "/.worktrees/")
        self.assertIsNone(_module_string_constant("def f():\n    WORKTREE_SUBDIR = 'x'\n",
                                                  "WORKTREE_SUBDIR"), "module level only")
        doc = ('"""Tool.\n\nSubcommands:\n'
               '  start    git worktree add -b feature/<cr>[-<slug>] .claude/worktrees/<cr> <base>.\n'
               '           Branches off LOCAL develop.\n"""\n')
        self.assertEqual(_flow_start_usage_paths(doc), [".claude/worktrees/<cr>"])
        text = ("root ends in `…/.claude/worktrees/<cr>/`, or `/.claude/worktrees/<cr>`\n"
                "new: `…/.worktrees/<cr>/` and `/.worktrees/<cr>` and `.worktrees/<cr>`\n"
                "odd: /.claude/.worktrees/<cr> and /my-worktrees/<cr>\n")
        spellings, bad = _nonconforming_worktree_spellings(text)
        self.assertEqual(len(spellings), 7)
        self.assertEqual(bad, ["…/.claude/worktrees/<cr>", "/.claude/worktrees/<cr>",
                               "/.claude/.worktrees/<cr>", "/my-worktrees/<cr>"])

class LegacyWorktreeSegmentGateTest(unittest.TestCase):
    """AC — ``.claude/worktrees`` appears nowhere in the shipped surfaces."""

    def test_zero_legacy_worktree_segment_in_the_shipped_surfaces(self):
        missing = [s for s in SHIPPED_SURFACES if not (REPO_ROOT / s).exists()]
        self.assertEqual(missing, [], f"precondition: every gated surface exists; missing {missing}")
        hits = _gate_hits(REPO_ROOT, SHIPPED_SURFACES, LEGACY_WORKTREE_RE)
        self.assertEqual(hits, [], _report(f"§S3 worktree gate (use `{DECLARED_WORKTREE}`)", hits))

    def test_detector_bites_in_every_surface_incl_contracts_and_spares_history(self):
        tmp, root = _fixture_root({
            "skills-src/b/SKILL.md": "ends in `/.claude/worktrees/<cr>`\nends in `/.worktrees/<cr>`\n",
            "hooks-src/scripts/h": '_WORKTREES_SEGMENT = "/.claude/worktrees/"\n',
            "scripts/w.py": 'WORKTREE_SUBDIR = ".claude/worktrees"\n',
            "contracts/worktree-layout.md": "replaces .claude/worktrees/<cr>\n",
            ".pi/agents/python-red-agent.md": "cwd under …/.claude/worktrees/<cr>/\n",
            "archive/wave2/orchestration-track.md": "/.claude/worktrees/<cr>\n",
            "docs/changes/CR-X.md": ".claude/worktrees/<cr>\n",
        })
        with tmp:
            hits = _gate_hits(root, SHIPPED_SURFACES, LEGACY_WORKTREE_RE)
        self.assertEqual(sorted(h.split(": ", 1)[0] for h in hits), [
            ".pi/agents/python-red-agent.md:1", "contracts/worktree-layout.md:1",
            "hooks-src/scripts/h:1", "scripts/w.py:1", "skills-src/b/SKILL.md:1",
        ])

class WorktreeLayoutBehaviourTest(unittest.TestCase):
    """AC (behavioural) — the hook, self-gating from its cwd, enforces ``<repo>/.worktrees/<cr>/``;
    ``worktree-flow.py``'s computed worktree is ``<main>/.worktrees/<cr>``."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mdb-031-c3-wt-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.main = _dbless_project(self.tmp)  # a git repo on `main` with one commit

    def _add_worktree(self, rel: str, branch: str) -> Path:
        path = self.main / rel
        result = _git_c3(self.main, "worktree", "add", "-b", branch, str(path), "main")
        self.assertEqual(result.returncode, 0, f"precondition: git worktree add {rel}: {result.stderr}")
        return path.resolve()

    def _hook(self, target: str, cwd: Path):
        return _run_script("block-write-outside-worktree", _write_payload(target, cwd),
                           env_overrides=NO_DISPATCH_SIGNAL)

    def assert_blocked_naming_root(self, result, root: Path, what: str):
        self.assertEqual(result.returncode, 2,
                         f"§S3: {what} must be BLOCKED (exit 2) — the hook must recognise a "
                         f"`{DECLARED_WORKTREE}` cwd as a worktree context; got exit "
                         f"{result.returncode}, stdout={result.stdout!r}, stderr={result.stderr!r}")
        payload = json.loads(result.stdout)
        self.assertEqual(payload.get("decision"), "block")
        self.assertIn(f"worktree root: {root}", payload.get("reason", ""),
                      "the block names the derived worktree root")

    def test_hook_blocks_outside_and_allows_inside_from_a_dot_worktrees_cwd(self):
        wt = self._add_worktree(".worktrees/CR-XYZ-001", "feature/CR-XYZ-001")
        (wt / "src").mkdir()
        self.assert_blocked_naming_root(self._hook(OUTSIDE_TARGET, wt), wt,
                                        "an absolute write outside the worktree")
        self.assert_blocked_naming_root(self._hook(OUTSIDE_TARGET, wt / "src"), wt,
                                        "the same write from a nested cwd")
        for target in (str(wt / "src" / "main.py"), "src/rel.py"):
            with self.subTest(target=target):
                inside = self._hook(target, wt)
                self.assertEqual(inside.returncode, 0,
                                 f"a write inside the worktree must be allowed; got exit "
                                 f"{inside.returncode}, stdout={inside.stdout!r}")
                self.assertEqual(inside.stdout.strip(), "", "an allow prints no block payload")

    def test_hook_treats_a_legacy_dot_claude_worktrees_cwd_as_no_worktree_context(self):
        # `.worktrees/` is the ONLY worktree segment: under the retired layout the hook self-gates
        # off (a strict no-op), exactly as for any non-Model-B cwd.
        legacy = self._add_worktree(".claude/worktrees/CR-XYZ-002", "feature/CR-XYZ-002")
        result = self._hook(OUTSIDE_TARGET, legacy)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, ""),
                         f"§S3: `.claude/worktrees/<cr>` is no longer a worktree segment — the hook "
                         f"must be a no-op there; got exit {result.returncode}, stdout={result.stdout!r}")

    def test_worktree_flow_dry_run_plans_main_dot_worktrees_cr_and_creates_nothing(self):
        result = _run_wf("start", "--cr", "CR-XYZ-003", "--base", "main",
                         "--project-dir", str(self.main), "--dry-run", cwd=self.tmp)
        self.assertEqual(result.returncode, 0, f"precondition: dry-run start exits 0: {result.stderr}")
        expected = self.main / DECLARED_SUBDIR / "CR-XYZ-003"
        self.assertIn(f"would create worktree {expected} on feature/CR-XYZ-003", result.stdout,
                      f"§S3: the computed worktree dir must be <main>/{DECLARED_WORKTREE}; "
                      f"stdout={result.stdout!r}")
        self.assertEqual(sorted(p.name for p in self.main.iterdir()), [".git"],
                         "--dry-run creates nothing")

    def test_worktree_flow_start_creates_the_worktree_the_hook_enforces(self):
        result = _run_wf("start", "--cr", "CR-XYZ-004", "--base", "main",
                         "--project-dir", str(self.main), cwd=self.tmp)
        self.assertEqual(result.returncode, 0, f"precondition: start exits 0: {result.stderr}")
        expected = self.main / DECLARED_SUBDIR / "CR-XYZ-004"
        registered = _registered_worktrees(self.main)
        self.assertEqual(registered, [str(self.main), str(expected)],
                         f"§S3: `worktree-flow.py start` must create exactly <main>/{DECLARED_WORKTREE}; "
                         f"git registers {registered}")
        self.assertIn(f"worktree={expected} ", result.stdout)
        self.assertFalse((self.main / ".claude").exists(), "no `.claude/` tree is created in the repo")
        self.assert_blocked_naming_root(self._hook(OUTSIDE_TARGET, expected), expected,
                                        "a write outside the worktree-flow worktree")
        inside = self._hook(str(expected / "notes.md"), expected)
        self.assertEqual(inside.returncode, 0, f"inside the worktree-flow worktree is allowed: {inside.stdout!r}")

# =================================================================== §S4 ====

class ChezmoiBundleRetiredTest(unittest.TestCase):
    """AC — ``skills-src/chezmoi/`` is gone; ``chezmoi`` appears nowhere in ``skills-src/``,
    ``generator/``, ``contracts/`` or ``modelb_axi/``."""

    def test_chezmoi_bundle_directory_is_gone(self):
        bundle = REPO_ROOT / "skills-src" / "chezmoi"
        present = sorted(p.relative_to(REPO_ROOT).as_posix() for p in bundle.rglob("*")) if bundle.exists() else []
        self.assertFalse(bundle.exists(), f"§S4: skills-src/chezmoi/ must be deleted; it holds {present}")

    def test_deploy_engine_discovers_no_chezmoi_bundle(self):
        from modelb_axi import deploy
        names = sorted(b.name for b in deploy._skill_bundles(REPO_ROOT))
        self.assertNotIn("chezmoi", names, f"§S4: the installer must not ship a chezmoi bundle; discovers {names}")
        self.assertEqual(len(names), EXPECTED_BUNDLE_COUNT,
                         f"§S4: exactly {EXPECTED_BUNDLE_COUNT} bundles ship; discovers {names}")

    def test_zero_chezmoi_in_skills_generator_contracts_and_modelb_axi(self):
        hits = _gate_hits(REPO_ROOT, CHEZMOI_SURFACES, CHEZMOI_RE)
        self.assertEqual(hits, [], _report("§S4 chezmoi gate", hits))

    def test_detector_bites_case_insensitively_in_the_four_surfaces_only(self):
        tmp, root = _fixture_root({
            "skills-src/git-workflow/SKILL.md": "- its push discipline lives in the `chezmoi` skill\nok\n",
            "skills-src/chezmoi/SKILL.md": "name: chezmoi\n",
            "generator/stacks/x.toml": "# Chezmoi\n",
            "contracts/lean-ctx.md": "- `CHEZMOI` blocked\n",
            "modelb_axi/x.py": "BIN = 'chezmoi'\n",
            "AGENTS.md": "chezmoi\n", "tests/test_x.py": "chezmoi\n", "archive/c.md": "chezmoi\n",
        })
        with tmp:
            hits = _gate_hits(root, CHEZMOI_SURFACES, CHEZMOI_RE)
        self.assertEqual(sorted(h.split(": ", 1)[0] for h in hits), [
            "contracts/lean-ctx.md:1", "generator/stacks/x.toml:1", "modelb_axi/x.py:1",
            "skills-src/chezmoi/SKILL.md:1", "skills-src/git-workflow/SKILL.md:1",
        ])

class AgentsMdBundleListTest(unittest.TestCase):
    """AC — ``AGENTS.md`` lists 13 bundles (7 owned, 6 imported) and names no ``chezmoi`` bundle."""

    def _row(self):
        row = _agents_md_bundle_row(AGENTS_MD.read_text(encoding="utf-8"))
        self.assertIsNotNone(row, "precondition: AGENTS.md keeps its `skills-src/` row "
                                  "('| `skills-src/` | N skill bundles. Model-B-owned: … Imported from Crucible …')")
        assert row is not None  # narrowed for the type checker; the assert above reports
        return row

    def test_bundle_row_states_13_bundles_7_owned_6_imported_and_no_chezmoi(self):
        count, owned, imported = self._row()
        self.assertNotIn("chezmoi", owned + imported, f"§S4: AGENTS.md still lists chezmoi: owned={owned}")
        self.assertEqual((count, len(owned), len(imported)),
                         (EXPECTED_BUNDLE_COUNT, EXPECTED_OWNED, EXPECTED_IMPORTED),
                         f"§S4: AGENTS.md must state {EXPECTED_BUNDLE_COUNT} bundles, {EXPECTED_OWNED} owned by Model B, "
                         f"{EXPECTED_IMPORTED} imported; "
                         f"states {count}, owned {owned}, imported {imported}")

    def test_bundle_row_matches_what_the_deploy_engine_discovers(self):
        # Pin: the row and the tree move together (a row edit without the deletion, or the
        # reverse, fails here).
        from modelb_axi import deploy
        count, owned, imported = self._row()
        discovered = sorted(b.name for b in deploy._skill_bundles(REPO_ROOT))
        self.assertEqual(sorted(owned + imported), discovered)
        self.assertEqual(count, len(discovered))

    def test_no_line_of_agents_md_names_chezmoi_as_a_bundle_or_skill(self):
        hits = [f"AGENTS.md:{n}: {line.strip()[:160]}"
                for n, line in enumerate(AGENTS_MD.read_text(encoding="utf-8").splitlines(), 1)
                if CHEZMOI_AS_BUNDLE_RE.search(line)]
        self.assertEqual(hits, [], _report("§S4 AGENTS.md names the retired chezmoi bundle", hits))

    def test_detector_row_parser_and_bundle_pattern_bite(self):
        before = ("| `skills-src/` | 14 skill bundles. Model-B-owned: `model-b`, `crucible`, "
                  "`cr-authoring`, `git-workflow`, `chezmoi`, `bootstrap`, `shutdown`, `code-health` "
                  "(deployed with the rust stack). Imported from Crucible (byte-identical, see "
                  "`CRUCIBLE-HANDOVER.md`): `crucible-register`, "
                  "`crucible-report-{arduino,bun,java,python,rust}`. Plus `memory-templates/` |")
        row = _agents_md_bundle_row(f"# X\n\n{before}\n| `x/` | y |\n")
        self.assertIsNotNone(row, "detector: the parser finds the row")
        assert row is not None
        count, owned, imported = row
        self.assertEqual((count, len(owned), len(imported)), (14, 8, 6))
        self.assertIn("chezmoi", owned)
        self.assertEqual(imported[-1], "crucible-report-rust")
        self.assertIsNone(_agents_md_bundle_row("| `skills/` | 14 skill bundles. |\n"))
        biting = ("`git-workflow`, `chezmoi`, `bootstrap`", "see the `chezmoi` skill for that",
                  "the chezmoi bundle", "`skills-src/chezmoi/`", "a, `chezmoi`")
        spared = ("Model B carries no chezmoi dependency", "the user's dotfile manager (chezmoi)")
        self.assertEqual([s for s in biting if not CHEZMOI_AS_BUNDLE_RE.search(s)], [])
        self.assertEqual([s for s in spared if CHEZMOI_AS_BUNDLE_RE.search(s)], [])

class MailAxiArchivedTest(unittest.TestCase):
    """AC — ``contracts/mail-axi.md`` exists only under ``archive/`` (pinned:
    ``archive/contracts/mail-axi.md``), moved byte-for-byte."""

    def test_mail_axi_exists_only_at_its_archive_path(self):
        listed = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=60,
        ).stdout.splitlines()
        present = [r for r in _mail_axi_paths(listed) if (REPO_ROOT / r).is_file()]
        self.assertEqual(present, [MAIL_AXI_ARCHIVED_REL],
                         f"§S4: mail-axi.md must exist only at {MAIL_AXI_ARCHIVED_REL}; found {present}")

    def test_archived_copy_is_byte_identical_to_the_retired_contract(self):
        archived = REPO_ROOT / MAIL_AXI_ARCHIVED_REL
        self.assertTrue(archived.is_file(), f"§S4: {MAIL_AXI_ARCHIVED_REL} must exist")
        digest = hashlib.sha256(archived.read_bytes()).hexdigest()
        self.assertEqual(digest, MAIL_AXI_SHA256, "§S4: a move into archive/, not an edit")

    def test_detector_location_filter(self):
        self.assertEqual(_mail_axi_paths(["contracts/mail-axi.md", "archive/contracts/mail-axi.md",
                                          "contracts/lean-ctx.md", "docs/not-mail-axi.md.bak"]),
                         ["archive/contracts/mail-axi.md", "contracts/mail-axi.md"])

class ContractsHarnessNeutralTest(unittest.TestCase):
    """AC — the C2 gates extended to ``contracts/``; ``contracts/lean-ctx.md`` names no Claude Code
    surface and is written against Pi and the ``pi-lean-ctx`` extension."""

    GATES = (("~/.claude", CLAUDE_HOME_RE), ("CLAUDE.md", CLAUDE_MD_RE),
             ("/tmp/claude-1000", TMP_CLAUDE_RE), ("Crucible wrapper", CRUCIBLE_WRAPPER_RE))  # noqa: S108

    def test_zero_claude_home_claude_md_tmp_wrapper_and_wrapper_instruction_in_contracts(self):
        for label, pattern in self.GATES:
            with self.subTest(gate=label):
                hits = _gate_hits(REPO_ROOT, ("contracts",), pattern)
                self.assertEqual(hits, [], _report(f"§S4 contracts/ {label} gate", hits))

    def test_lean_ctx_contract_names_no_harness_tool(self):
        # Pin at RED (no listed tool name in lean-ctx.md today); guards the rewrite.
        hits = _gate_hits(REPO_ROOT, ("contracts/lean-ctx.md",), HARNESS_TOOL_RE)
        self.assertEqual(hits, [], _report("§S4 lean-ctx.md tool gate", hits))

    def test_lean_ctx_contract_names_pi_and_the_pi_lean_ctx_extension(self):
        self.assertTrue(LEAN_CTX_MD.is_file(), "§S4: contracts/lean-ctx.md is rewritten, not deleted")
        text = LEAN_CTX_MD.read_text(encoding="utf-8")
        self.assertIn("pi-lean-ctx", text, "§S4: lean-ctx.md names the `pi-lean-ctx` extension")
        self.assertRegex(text, r"\bPi\b", "§S4: lean-ctx.md names Pi")

    def test_detector_contract_gates_bite_and_spare(self):
        tmp, root = _fixture_root({
            "contracts/lean-ctx.md": (
                "- Governing rules: `~/.claude/rules/lean-ctx.md`\n"          # 1 ~/.claude
                "  imported by the global CLAUDE.md\n"                        # 2 CLAUDE.md
                "  `/tmp/claude-1000/modelb-crucible` test wrapper\n"         # 3 tmp
                "Model B pins these via the per-project context wrapper\n"   # 4 wrapper
                "Pi loads the `pi-lean-ctx` extension; see AGENTS.md\n"      # spared
                "the rust-crucible.py wrapper around cargo\n"                # spared
            ),
            "contracts/other.md": "writes $HOME/.claude/settings.json\n",
            "skills-src/x/SKILL.md": "~/.claude CLAUDE.md /tmp/claude-1000\n",
        })
        with tmp:
            got = {label: sorted(h.split(": ", 1)[0] for h in _gate_hits(root, ("contracts",), pattern))
                   for label, pattern in self.GATES}
        self.assertEqual(got, {
            "~/.claude": ["contracts/lean-ctx.md:1", "contracts/other.md:1"],
            "CLAUDE.md": ["contracts/lean-ctx.md:2"],
            "/tmp/claude-1000": ["contracts/lean-ctx.md:3"],  # noqa: S108 -- a gate label, not a temp path
            "Crucible wrapper": ["contracts/lean-ctx.md:4"],
        })

class ContractsNotPackagedTest(unittest.TestCase):
    """AC — ``pyproject.toml`` force-includes no ``contracts`` (no runtime consumer), and a built
    wheel carries no ``modelb_axi/_assets/contracts/``."""

    def test_pyproject_force_include_drops_contracts_and_keeps_the_four_asset_roots(self):
        force_include = (_pyproject().get("tool", {}).get("hatch", {}).get("build", {})
                         .get("targets", {}).get("wheel", {}).get("force-include", {}))
        self.assertEqual(sorted(force_include), ["generator", "hooks-src", "scripts", "skills-src"],
                         f"§S4: force-include must drop `contracts` and keep the four asset roots; "
                         f"got {force_include}")
        self.assertEqual([d for d in force_include.values() if "_assets/contracts" in d], [])

    def test_wheel_built_from_the_sdist_carries_no_assets_contracts(self):
        root = Path(tempfile.mkdtemp(prefix="mdb-031-c3-wheel-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        wheel = build_wheel(build_sdist(REPO_ROOT, root / "sdist"), root / "wheel")
        names = wheel_names(wheel)
        # Non-vacuous: the wheel carries the asset roots that stay.
        for kept in ("modelb_axi/_assets/skills-src/model-b/SKILL.md",
                     "modelb_axi/_assets/hooks-src/scripts/block-write-outside-worktree"):
            self.assertIn(kept, names, f"precondition: the wheel ships {kept}")
        offenders = sorted(n for n in names if n.startswith(CONTRACTS_ASSET_PREFIX))
        self.assertEqual(offenders, [], f"§S4: the wheel must carry no {CONTRACTS_ASSET_PREFIX}")

if __name__ == "__main__":
    unittest.main()
