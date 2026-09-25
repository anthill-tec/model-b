"""Harness-neutral skill and template text — CR-MDB-031 §S2 (DN §D18, option A).

Contract: ``docs/changes/CR-MDB-031-claude-era-substrate-retirement.md`` §S2 and its acceptance
criteria (amended at ``82305e2``). The skills, the memory templates, the generator's templates and
stacks, and every definition rendered from them are written in capability words: they name
capabilities and harness-neutral CLIs (``sandesh``, ``~/.crucible/clients/<stack>-crucible.py``,
``worktree-flow.py``), never a harness's own tools, and they cite the ``~/.agents`` store, never
``~/.claude``.

Class map (one per C2 acceptance criterion):

- ``ClaudeHomePathGateTest`` — zero live ``~/.claude`` paths in the shipped surfaces; the only
  exemptions are ``CLAUDE_HOME_EXEMPT_LINES``.
- ``HarnessToolNameGateTest`` — zero Claude Code tool / MCP-verb names in ``skills-src/``,
  ``generator/``, ``hooks-src/`` and ``scripts/``.
- ``ClaudeMdGateTest`` — zero ``CLAUDE.md`` in the shipped surfaces; project context is
  ``AGENTS.md`` (the four role templates and the Sheetal line of ``arduino.toml``).
- ``ToolRatchetDrainedTest`` — CR-MDB-020 §S4's ratchet passes with ``TOOL_BASELINE == {}``.
- ``SandeshCliFormTest`` — a ``sandesh send``, ``sandesh fetch`` and ``sandesh reply`` form each
  survive in ``skills-src/``.
- ``CrucibleWrapperRetiredTest`` — zero ``/tmp/claude-1000`` and zero per-project Crucible
  "wrapper" instructions in the ``~/.claude`` gate's surfaces.
- ``SkillsReadmeD18Test`` / ``SkillsReadmeNotDeployedTest`` — ``skills-src/README.md`` states the
  §D18 rule once, names the ratchet test, and is never deployed.
- ``RegenerationCleanTest`` — ``generator/build.py --check`` is clean and ``.pi/agents/`` equals a
  fresh sandboxed ``modelb-axi agents`` render.
- ``TargetedTextFixesTest`` — the named one-line fixes: ``arduino.toml``'s ``crucible_reference``,
  Panache's ``find()``, the ontology line of the ``model-b`` skill, no NAI project-memory example.

Scope boundaries (C3 is done — no scope boundary remains):

- ``contracts/`` IS scanned by the ``~/.claude`` and wrapper gates (``HOME_GATE_SURFACES``): C3
  rewrote ``contracts/lean-ctx.md`` and archived ``contracts/mail-axi.md``.
- Nothing under ``skills-src/`` is excluded: C3 deleted the ``chezmoi`` bundle, so every gate
  scans the whole tree.
- The worktree PATH segment ``.worktrees/<cr>`` (C3's rename) is not a ``~/.claude`` path — the
  home gate requires the ``~/`` (or ``$HOME/``) prefix.

Every scan gate has a detector fixture proving it bites (and spares what it must spare), and every
failure names the offending ``file:line``. Stdlib only.
"""

import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from tests import test_deployed_asset_freshness as freshness
from tests._helpers import REPO_ROOT, parse_env_file
from tests.test_client_path_anchoring import (
    TOOL_BASELINE,
    _ratchet_violations,
    _tool_occurrences,
)
from tests.test_pi_agent_definitions import (
    _copy_c3_asset_root,
    _run_module_c3,
    _write_install_toml_c3,
)

SKILLS_SRC = REPO_ROOT / "skills-src"
SKILLS_README = SKILLS_SRC / "README.md"
STACKS_DIR = REPO_ROOT / "generator" / "stacks"
TEMPLATES_DIR = REPO_ROOT / "generator" / "templates"
PI_AGENTS_DIR = REPO_ROOT / ".pi" / "agents"
BUILD_PY = REPO_ROOT / "generator" / "build.py"

# ------------------------------------------------------------------ surfaces ----

#: The shipped surfaces of the ``~/.claude`` gate (AC 9), as the AC lists them (other modules
#: import this tuple and extend it themselves).
CLAUDE_HOME_SURFACES = (
    "skills-src", "generator", "hooks-src", "scripts", "modelb_axi", ".pi/agents",
    "AGENTS.md", "docs/install-guide.md",
)
#: What the ``~/.claude`` and wrapper gates scan: AC 9's surfaces plus ``contracts/`` (C3's rewrite).
HOME_GATE_SURFACES = CLAUDE_HOME_SURFACES + ("contracts",)
#: The tool-name gate's surfaces (AC 10), exactly as the spec lists them.
TOOL_SURFACES = ("skills-src", "generator", "hooks-src", "scripts")
#: The ``CLAUDE.md`` gate's surfaces (AC 11), exactly as the spec lists them.
CLAUDE_MD_SURFACES = ("skills-src", "generator", "hooks-src", "scripts", "modelb_axi", ".pi/agents")

#: AC 9's exemptions, as MEASURED at C2 RED (develop-line ``82305e2``): prose that names
#: ``~/.claude`` as the tree Model B never writes. Matched on (file, exact line text) so a rewrite
#: above them cannot shift them; the line number is the measured position, for the reader. The
#: ``CRUCIBLE-HANDOVER.md`` provenance line the AC also allows carries no ``~/.claude`` (measured),
#: so it needs no entry. ``AGENTS.md:14`` ("nothing writes to ``~/.claude`` except through the
#: installer") is NOT exempt: it says the installer writes there, which §S1 made false.
#: C3 NOTE: C3's chezmoi retirement rewrote ``AGENTS.md:109`` (its chezmoi-skill pointer dropped,
#: CR-MDB-031 \u00a7S4); this text was updated to match.
CLAUDE_HOME_EXEMPT_LINES = (
    ("AGENTS.md", 49,
     "| `scripts/` | The tool-script asset class (7 adopted + 1 generated): `worktree-flow.py`, "
     "`schedule_db.py` (TRANSITIONAL), `skill-release-gate.py`, `rust-code-health.py`, "
     "`rust-crate-map.py`, `rust-dead-scan.py`, `gate-lock.sh`, and `toon.py` generated from "
     "`modelb_axi/toon.py`. Deployed to `~/.agents/scripts/` (`deploy.TOOL_SCRIPTS_STORE_RELDIR`) "
     "\u2014 the ONLY path a Model B surface names; never a `~/.claude` path (not Model B-owned) |"),
    ("AGENTS.md", 109,
     "- Model B never mutates `~/.claude` directly \u2014 the `modelb-axi` installer is the only "
     "deployment channel (PRD \u00a7D9/\u00a7D10), and the repo-local authoring rule means no CR "
     "writes there at all. The user's own dotfile-manager discipline is out of scope for this "
     "file."),
)

# ------------------------------------------------------------------ patterns ----

#: A live home-tree ``.claude`` path. The ``~/`` / ``$HOME/`` prefix is required, so the C3
#: worktree segment ``…/.claude/worktrees/<cr>`` never matches.
CLAUDE_HOME_RE = re.compile(r"(?:~|\$HOME|\$\{HOME\})/\.claude(?![\w-])")
#: AC 10's names. Bounded by alphanumerics on the left only, so an MCP-qualified spelling
#: (``mcp__sandesh__sandesh_send``) still counts; ``PreToolUse-hook-blocked`` counts too.
HARNESS_TOOL_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:EnterWorktree|ExitWorktree|TaskList|TaskUpdate|TaskStop|AskUserQuestion"
    r"|PreToolUse|NotebookEdit|dangerouslyDisableSandbox|run_in_background"
    r"|sandesh_(?:send|reply|fetch|inbox|register|unregister|addressbook|setup))(?![A-Za-z0-9_])"
)
CLAUDE_MD_RE = re.compile(r"CLAUDE\.md")
#: The retired per-project wrapper's directory.
TMP_CLAUDE_RE = re.compile(r"/tmp/claude-1000")  # noqa: S108 -- a pattern to forbid, not a temp path
#: The retired wrapper INSTRUCTION, as the skills phrased it ("per-project context wrapper",
#: "wrapper pattern", "when your prompt names a wrapper", ``<project>-crucible``). A Crucible client
#: described as wrapping ``cargo``/``mvn`` ("the rust-crucible.py wrapper") is not the idiom.
CRUCIBLE_WRAPPER_RE = re.compile(
    r"\b(?:context|per-project)\s+wrapper\b|\bwrapper\s+pattern\b|\bnames\s+a\s+wrapper\b"
    r"|<project>-crucible\b",
    re.IGNORECASE,
)
#: A Sandesh CLI form (``sandesh send``), never the MCP verb (``sandesh_send``).
SANDESH_CLI_RE = re.compile(r"(?<![\w-])sandesh (send|fetch|reply)(?![\w-])")
REQUIRED_SANDESH_VERBS = ("send", "fetch", "reply")

# ------------------------------------------------------------------ scanning ----


def _surface_texts(root: Path, surfaces, excluded=()):
    """Yield ``(rel, text)`` for every UTF-8 file under ``root/<surface>`` (a directory, walked
    recursively, or a single file). Dot-directories are scanned (``.pi/agents``); ``__pycache__``
    and any ``rel`` starting with one of ``excluded`` are skipped."""
    for surface in surfaces:
        target = root / surface
        if target.is_file():
            paths = [target]
        elif target.is_dir():
            paths = sorted(p for p in target.rglob("*") if p.is_file())
        else:
            continue
        for path in paths:
            rel = path.relative_to(root).as_posix()
            if "__pycache__" in rel.split("/") or rel.startswith(tuple(excluded)):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            yield rel, text


def _gate_hits(root: Path, surfaces, pattern, excluded=(), exempt=()):
    """``["<rel>:<lineno>: <line>"]`` for every line ``pattern`` matches, except lines whose
    ``(rel, exact text)`` is in ``exempt`` (``(rel, lineno, text)`` triples)."""
    exempt_pairs = {(rel, text) for rel, _lineno, text in exempt}
    hits = []
    for rel, text in _surface_texts(root, surfaces, excluded):
        for lineno, line in enumerate(text.splitlines(), 1):
            if pattern.search(line) and (rel, line) not in exempt_pairs:
                hits.append(f"{rel}:{lineno}: {line.strip()[:180]}")
    return hits


def _fixture_root(files: dict):
    """A throwaway tree: ``(TemporaryDirectory, root)`` with ``files`` ({rel: text}) written."""
    tmp = tempfile.TemporaryDirectory(prefix="mdb-031-c2-")
    root = Path(tmp.name)
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp, root


def _report(label: str, hits) -> str:
    return f"{label}: {len(hits)} offending line(s):\n  " + "\n  ".join(hits)


class _SurfacesExist(unittest.TestCase):
    """Precondition shared by the scan gates: a missing surface would make a gate vacuous."""

    def assert_surfaces_exist(self, surfaces):
        missing = [s for s in surfaces if not (REPO_ROOT / s).exists()]
        self.assertEqual(missing, [], f"precondition: every gated surface exists; missing {missing}")


# ------------------------------------------------------------------ AC 9: ~/.claude ----


class ClaudeHomePathGateTest(_SurfacesExist):
    """AC 9 — zero live ``~/.claude`` paths in ``skills-src/``, ``generator/`` (templates, stacks,
    agents), ``hooks-src/``, ``scripts/``, ``modelb_axi/``, ``.pi/agents/``, ``AGENTS.md`` and
    ``docs/install-guide.md``; exempt only ``CLAUDE_HOME_EXEMPT_LINES``."""

    def test_zero_live_claude_home_paths_in_the_shipped_surfaces(self):
        self.assert_surfaces_exist(HOME_GATE_SURFACES)
        hits = _gate_hits(REPO_ROOT, HOME_GATE_SURFACES, CLAUDE_HOME_RE,
                          exempt=CLAUDE_HOME_EXEMPT_LINES)
        self.assertEqual(hits, [], _report("§S2 ~/.claude gate (cite ~/.agents/skills/<name>/…)", hits))

    def test_every_exemption_is_a_live_line_that_names_the_tree_model_b_never_writes(self):
        # A stale exemption would silently widen the gate; each must match a line verbatim and
        # carry both `~/.claude` and a "never" (the only prose the AC allows).
        for rel, _lineno, text in CLAUDE_HOME_EXEMPT_LINES:
            with self.subTest(rel=rel, text=text[:60]):
                self.assertIn(text, (REPO_ROOT / rel).read_text(encoding="utf-8").splitlines(),
                              f"exemption no longer matches a line of {rel} verbatim")
                self.assertRegex(text, CLAUDE_HOME_RE)
                self.assertIn("never", text)
        self.assertEqual(len(CLAUDE_HOME_EXEMPT_LINES), 2, "the exemption list stays minimal")

    def test_detector_bites_on_home_paths_in_contracts_and_every_bundle_and_spares_worktrees_agents_and_exempt_lines(self):
        exempt_rel, exempt_lineno, exempt_text = CLAUDE_HOME_EXEMPT_LINES[0]
        tmp, root = _fixture_root({
            "skills-src/b/SKILL.md": (
                "Read `~/.claude/skills/model-b/SKILL.md` first.\n"           # 1 hit
                "Worktree: `…/.claude/worktrees/<cr>/` and /.claude/worktrees/\n"  # C3's, spared
                "Read `~/.agents/skills/model-b/SKILL.md`.\n"                 # spared
                "Also $HOME/.claude/settings.json and ~/.claude.json\n"      # 4 hit
            ),
            ".pi/agents/python-red-agent.md": "see ~/.claude/skills/crucible/SKILL.md\n",
            "AGENTS.md": f"{exempt_text}\n{exempt_text} extra\n",
            "skills-src/chezmoi/SKILL.md": "edit ~/.claude then apply\n",
            "contracts/lean-ctx.md": "writes ~/.claude/settings.json\n",
            "generator/__pycache__/x.md": "~/.claude\n",
        })
        with tmp:
            hits = _gate_hits(root, HOME_GATE_SURFACES, CLAUDE_HOME_RE,
                              exempt=CLAUDE_HOME_EXEMPT_LINES)
        self.assertEqual(sorted(h.split(": ", 1)[0] for h in hits), [
            ".pi/agents/python-red-agent.md:1",
            f"{exempt_rel}:2",
            "contracts/lean-ctx.md:1",
            "skills-src/b/SKILL.md:1",
            "skills-src/b/SKILL.md:4",
            "skills-src/chezmoi/SKILL.md:1",
        ])


# ------------------------------------------------------------------ AC 10: tool names ----


class HarnessToolNameGateTest(_SurfacesExist):
    """AC 10 — zero ``EnterWorktree``, ``ExitWorktree``, ``TaskList``, ``TaskUpdate``,
    ``TaskStop``, ``AskUserQuestion``, ``PreToolUse``, ``NotebookEdit``,
    ``dangerouslyDisableSandbox``, ``run_in_background`` and ``sandesh_<verb>`` in
    ``skills-src/``, ``generator/``, ``hooks-src/`` and ``scripts/`` (no exemption)."""

    def test_zero_harness_tool_names_in_skills_generator_hooks_and_scripts(self):
        self.assert_surfaces_exist(TOOL_SURFACES)
        hits = _gate_hits(REPO_ROOT, TOOL_SURFACES, HARNESS_TOOL_RE)
        self.assertEqual(hits, [], _report("§S2 tool gate (capability words / the sandesh CLI)", hits))

    def test_detector_bites_on_every_listed_name_and_spares_cli_forms(self):
        names = ("EnterWorktree", "ExitWorktree", "TaskList", "TaskUpdate", "TaskStop",
                 "AskUserQuestion", "PreToolUse-hook-blocked", "NotebookEdit",
                 "dangerouslyDisableSandbox", "run_in_background",
                 "mcp__sandesh__sandesh_send", "sandesh_reply", "`sandesh_fetch`es",
                 "sandesh_inbox", "sandesh_register", "sandesh_unregister",
                 "sandesh_addressbook", "sandesh_setup")
        body = "".join(f"use {n} here\n" for n in names)
        spared = ("sandesh send --to X --project P\nsandesh fetch\nsandesh reply --to-msg 7\n"
                  "your task list; ask the user; sandesh_watcher; TaskListing\n")
        tmp, root = _fixture_root({"skills-src/b/SKILL.md": body + spared,
                                   "scripts/w.py": "print('EnterWorktree(x)')\n",
                                   "skills-src/chezmoi/SKILL.md": "TaskUpdate\n"})
        with tmp:
            hits = _gate_hits(root, TOOL_SURFACES, HARNESS_TOOL_RE)
        self.assertEqual(sorted(h.split(": ", 1)[0] for h in hits),
                         sorted(["scripts/w.py:1", "skills-src/chezmoi/SKILL.md:1"]
                                + [f"skills-src/b/SKILL.md:{n}" for n in range(1, len(names) + 1)]))


# ------------------------------------------------------------------ AC 11: CLAUDE.md ----


class ClaudeMdGateTest(_SurfacesExist):
    """AC 11 — zero ``CLAUDE.md`` in ``skills-src/``, ``generator/`` (templates, stacks, agents),
    ``hooks-src/``, ``scripts/``, ``modelb_axi/`` and ``.pi/agents/``; project context is named
    ``AGENTS.md`` (Sheetal carries ``AGENTS.md`` at both levels)."""

    def test_zero_claude_md_in_the_shipped_surfaces(self):
        self.assert_surfaces_exist(CLAUDE_MD_SURFACES)
        hits = _gate_hits(REPO_ROOT, CLAUDE_MD_SURFACES, CLAUDE_MD_RE)
        self.assertEqual(hits, [], _report("§S2 CLAUDE.md gate (project context is AGENTS.md)", hits))

    def test_every_role_template_reads_agents_md_as_project_context(self):
        wrong = {}
        for role in ("red", "green", "verify", "fix"):
            lines = [ln for ln in (TEMPLATES_DIR / f"{role}.md.tmpl").read_text(encoding="utf-8").splitlines()
                     if "**Read project context**" in ln]
            if len(lines) != 1 or "AGENTS.md" not in lines[0]:
                wrong[f"{role}.md.tmpl"] = lines
        self.assertEqual(wrong, {}, "§S2: each role template's one 'Read project context' step "
                                    "names AGENTS.md")

    def test_arduino_stack_names_agents_md_at_both_sheetal_levels(self):
        text = (STACKS_DIR / "arduino.toml").read_text(encoding="utf-8")
        self.assertTrue("sheetal-firmware/AGENTS.md" in text,
                        "§S2 (AC amended at C2 RED): Sheetal carries AGENTS.md at both levels "
                        "(arduino.toml names no sheetal-firmware/AGENTS.md)")
        self.assertFalse("sheetal-firmware/CLAUDE.md" in text,
                         "§S2: arduino.toml still names sheetal-firmware/CLAUDE.md")

    def test_detector_bites_in_dot_dirs_and_python_and_spares_agents_md(self):
        tmp, root = _fixture_root({
            ".pi/agents/a.md": "Read project context — CLAUDE.md.\n",
            "modelb_axi/s.py": "LINK = 'CLAUDE.md'\n",
            "generator/templates/r.md.tmpl": "Read project context — AGENTS.md.\n",
            "skills-src/chezmoi/SKILL.md": "CLAUDE.md\n",
        })
        with tmp:
            hits = _gate_hits(root, CLAUDE_MD_SURFACES, CLAUDE_MD_RE)
        self.assertEqual(sorted(h.split(": ", 1)[0] for h in hits),
                         [".pi/agents/a.md:1", "modelb_axi/s.py:1", "skills-src/chezmoi/SKILL.md:1"])


# ------------------------------------------------------------------ AC 12: ratchet ----


class ToolRatchetDrainedTest(unittest.TestCase):
    """AC 12 — CR-MDB-020 §S4's ratchet passes with ``TOOL_BASELINE == {}`` and no exemption."""

    def test_tool_baseline_is_drained_to_empty(self):
        remaining = dict(TOOL_BASELINE)
        self.assertEqual(remaining, {}, "§S2: tests.test_client_path_anchoring.TOOL_BASELINE must "
                                        f"be {{}}; still baselined: {sorted(remaining)}")

    def test_skills_tree_passes_the_ratchet_against_an_empty_baseline(self):
        violations = _ratchet_violations(_tool_occurrences(REPO_ROOT), {})
        self.assertEqual(violations, [], "§S2 ratchet with an empty baseline:\n  " + "\n  ".join(violations))


# ------------------------------------------------------------------ AC 13: sandesh CLI ----


def _sandesh_cli_forms(root: Path) -> dict:
    """``{verb: first "<rel>:<lineno>"}`` for each ``sandesh <verb>`` CLI form under skills-src/."""
    found = {}
    for rel, text in _surface_texts(root, ("skills-src",)):
        for lineno, line in enumerate(text.splitlines(), 1):
            for verb in SANDESH_CLI_RE.findall(line):
                found.setdefault(verb, f"{rel}:{lineno}")
    return found


class SandeshCliFormTest(unittest.TestCase):
    """AC 13 — every Sandesh step names the ``sandesh`` CLI; at least one ``sandesh send``,
    ``sandesh fetch`` and ``sandesh reply`` form survives in ``skills-src/``."""

    def test_send_fetch_and_reply_cli_forms_each_survive_in_skills_src(self):
        found = _sandesh_cli_forms(REPO_ROOT)
        missing = [v for v in REQUIRED_SANDESH_VERBS if v not in found]
        self.assertEqual(missing, [], f"§S2: skills-src/ names no `sandesh <verb>` form for {missing} "
                                      f"(found {found}); the MCP verbs become the CLI")

    def test_detector_counts_cli_forms_only(self):
        tmp, root = _fixture_root({
            "skills-src/b/SKILL.md": ("mcp__sandesh__sandesh_send; sandesh_reply; sandesh sender\n"
                                      "run `sandesh fetch --project P --to 'Me'`\n"),
            "skills-src/chezmoi/SKILL.md": "sandesh send --to X\n",
        })
        with tmp:
            self.assertEqual(_sandesh_cli_forms(root), {"fetch": "skills-src/b/SKILL.md:2",
                                                        "send": "skills-src/chezmoi/SKILL.md:1"})


# ------------------------------------------------------------------ AC 15: wrapper ----


class CrucibleWrapperRetiredTest(_SurfacesExist):
    """AC 15 — zero ``/tmp/claude-1000`` and zero Crucible "wrapper" instructions in the
    ``~/.claude`` gate's surfaces (``contracts/`` included): skills name the installed client."""

    def test_zero_tmp_claude_1000_in_the_shipped_surfaces(self):
        self.assert_surfaces_exist(HOME_GATE_SURFACES)
        hits = _gate_hits(REPO_ROOT, HOME_GATE_SURFACES, TMP_CLAUDE_RE)
        self.assertEqual(hits, [], _report("§S2 /tmp/claude-1000 gate", hits))

    def test_zero_crucible_wrapper_instructions_in_the_shipped_surfaces(self):
        hits = _gate_hits(REPO_ROOT, HOME_GATE_SURFACES, CRUCIBLE_WRAPPER_RE)
        self.assertEqual(hits, [], _report(
            "§S2 wrapper gate (name ~/.crucible/clients/<stack>-crucible.py directly)", hits))

    def test_detector_bites_on_the_wrapper_idiom_and_spares_client_and_retry_wrappers(self):
        tmp, root = _fixture_root({
            "skills-src/crucible/references/python.md": (
                "- When your prompt names a per-project context wrapper (e.g.\n"
                "  `/tmp/claude-1000/<project>-crucible`), run every call THROUGH it\n"
                "- **Per-project wrapper pattern:** projects ship one.\n"
                "  When your prompt names a wrapper, use it.\n"
                "no `while`/retry wrapper, exactly ONE per address\n"
            ),
            "hooks-src/scripts/block-direct-cargo-test": "redirects to the rust-crucible.py wrapper.\n",
            "AGENTS.md": "# Per-project context wrapper (pins CRUCIBLE_PROJECT_KEY)\n",
        })
        with tmp:
            wrapper = _gate_hits(root, HOME_GATE_SURFACES, CRUCIBLE_WRAPPER_RE)
            tmp_dir = _gate_hits(root, HOME_GATE_SURFACES, TMP_CLAUDE_RE)
        self.assertEqual(sorted(h.split(": ", 1)[0] for h in wrapper), [
            "AGENTS.md:1",
            "skills-src/crucible/references/python.md:1",
            "skills-src/crucible/references/python.md:2",
            "skills-src/crucible/references/python.md:3",
            "skills-src/crucible/references/python.md:4",
        ])
        self.assertEqual([h.split(": ", 1)[0] for h in tmp_dir],
                         ["skills-src/crucible/references/python.md:2"])


# ------------------------------------------------------------------ AC 14: README ----


def _d18_rule_sentences(text: str) -> list:
    """Sentences stating §D18: capabilities AND CLIs, NEVER a harness's own tools."""
    flat = " ".join(text.split())
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+", flat):
        low = sentence.lower()
        if ("capabilit" in low and re.search(r"\bCLIs?\b", sentence) and "never" in low
                and "harness" in low and re.search(r"\btools?\b", low)):
            out.append(sentence)
    return out


class SkillsReadmeD18Test(unittest.TestCase):
    """AC 14 — ``skills-src/README.md`` exists, states the §D18 rule once citing DN §D18, names
    the ratchet test, and is no bundle."""

    def _readme(self) -> str:
        self.assertTrue(SKILLS_README.is_file(), f"§S2: {SKILLS_README.relative_to(REPO_ROOT)} must exist")
        return SKILLS_README.read_text(encoding="utf-8")

    def test_readme_states_the_d18_rule_and_cites_dn_d18(self):
        text = self._readme()
        self.assertTrue(_d18_rule_sentences(text),
                        "§S2: the README states the rule — skills name capabilities and CLIs, never "
                        "a harness's own tools")
        self.assertIn("D18", text, "§S2: the README cites DN §D18")
        self.assertIn("DN-multi-harness-deploy-model.md", text, "§S2: the DN §D18 lives in")

    def test_readme_names_the_ratchet_test(self):
        self.assertIn("test_client_path_anchoring", self._readme(),
                      "§S2: the README names CR-MDB-020 §S4's ratchet test")

    def test_readme_is_top_level_and_skills_src_is_not_itself_a_bundle(self):
        self._readme()
        self.assertFalse((SKILLS_SRC / "SKILL.md").exists(), "§S2: the README is not a bundle")

    def test_rule_detector_bites_and_spares(self):
        self.assertEqual(len(_d18_rule_sentences(
            "Intro. A shared skill names capabilities and CLIs,\nnever a harness's own tools. End.")), 1)
        self.assertEqual(_d18_rule_sentences("Skills name capabilities. Use the CLI. Never a tool."), [])


class SkillsReadmeNotDeployedTest(freshness._InstalledMachineCase):
    """AC 14 — the README is never deployed: absent from a sandboxed Pi install's manifest and from
    the deployed store (the shared fixture pins HOME/PATH/MODELB_HOME/XDG_DATA_HOME/
    PI_CODING_AGENT_DIR to a sandbox)."""

    ROOT_PREFIX = "mdb-031-c2-readme-"

    def test_readme_is_absent_from_a_sandboxed_install_manifest_and_store(self):
        self.assertTrue(SKILLS_README.is_file(), "§S2: skills-src/README.md must exist to prove it "
                                                 "is not deployed")
        paths = self.manifest_paths()
        self.assertIn(freshness.SKILL_REL, paths, "fixture: the install deployed the skill store")
        readme = SKILLS_README.read_bytes()
        store = self.target_root / ".agents" / "skills"
        copies = sorted(p.relative_to(self.target_root).as_posix() for p in store.rglob("*")
                        if p.is_file() and p.read_bytes() == readme)
        self.assertNotIn(".agents/skills/README.md", paths)
        self.assertFalse((store / "README.md").exists(), "§S2: README deployed into the store")
        self.assertEqual(copies, [], "§S2: the README's content was deployed")


# ------------------------------------------------------------------ AC 16: regeneration ----


def _tree_differences(expected: Path, actual: Path) -> list:
    """Sorted ``["<name>: <why>"]`` over the ``*.md`` files of two directories."""
    exp = {p.name: p.read_bytes() for p in expected.glob("*.md")}
    act = {p.name: p.read_bytes() for p in actual.glob("*.md")}
    out = [f"{n}: missing" for n in sorted(set(exp) - set(act))]
    out += [f"{n}: unexpected" for n in sorted(set(act) - set(exp))]
    out += [f"{n}: differs" for n in sorted(set(exp) & set(act)) if exp[n] != act[n]]
    return sorted(out)


class RegenerationCleanTest(unittest.TestCase):
    """AC 16 — ``generator/build.py --check`` is clean and ``.pi/agents/`` equals a fresh
    sandboxed ``modelb-axi agents`` render (never hand-edited)."""

    def test_build_check_is_clean(self):
        result = subprocess.run([sys.executable, str(BUILD_PY), "--check"], cwd=REPO_ROOT,
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, f"§S2: build.py --check drift:\n{result.stdout}\n{result.stderr}")

    def test_pi_agents_equal_a_fresh_sandboxed_agents_render(self):
        stacks = parse_env_file(REPO_ROOT / ".env").get("PROJECT_STACKS") or "python"
        with tempfile.TemporaryDirectory(prefix="mdb-031-c2-render-") as tmp:
            sandbox = Path(tmp)
            home, assets, project, user_home = (sandbox / n for n in ("mh", "assets", "proj", "home"))
            for d in (project, user_home, sandbox / "xdg"):
                d.mkdir(parents=True)
            _copy_c3_asset_root(assets)
            _write_install_toml_c3(home, assets, harnesses=("pi",))
            (project / ".env").write_text(f"PROJECT_STACKS={stacks}\n", encoding="utf-8")
            result = _run_module_c3("--modelb-home", str(home), "agents", cwd=str(project),
                                    env_overrides={"HOME": str(user_home), "MODELB_HOME": str(home),
                                                   "XDG_DATA_HOME": str(sandbox / "xdg")})
            self.assertEqual(result.returncode, 0, f"fixture: agents render failed: {result.stderr}")
            diffs = _tree_differences(project / ".pi" / "agents", PI_AGENTS_DIR)
        self.assertEqual(diffs, [], "§S2: .pi/agents/ differs from a fresh `modelb-axi agents` render "
                                    f"(PROJECT_STACKS={stacks}): {diffs}")

    def test_tree_difference_detector_bites(self):
        tmp, root = _fixture_root({"a/x.md": "1", "a/y.md": "2", "b/x.md": "1!", "b/z.md": "3"})
        with tmp:
            self.assertEqual(_tree_differences(root / "a", root / "b"),
                             ["x.md: differs", "y.md: missing", "z.md: unexpected"])
            self.assertEqual(_tree_differences(root / "a", root / "a"), [])


# ------------------------------------------------------------------ targeted fixes ----


#: The shipped per-stack Crucible reference each stack's ``crucible_reference`` cites.
STACK_REFERENCE_FILE = {
    "arduino": "arduino.md", "bun": "bun.md", "python": "python.md", "quarkus": "java.md", "rust": "rust.md",
}
AGENTS_CRUCIBLE_REFERENCES = "~/.agents/skills/crucible/references/"


def _crucible_reference(stack: str) -> str:
    with (STACKS_DIR / f"{stack}.toml").open("rb") as fh:
        return tomllib.load(fh).get("crucible_reference", "")


class TargetedTextFixesTest(unittest.TestCase):
    """The named §S2 one-line fixes."""

    def test_arduino_crucible_reference_points_at_the_shipped_arduino_reference(self):
        value = _crucible_reference("arduino")
        self.assertTrue((SKILLS_SRC / "crucible" / "references" / "arduino.md").is_file())
        self.assertEqual(value.split()[0] if value else "", AGENTS_CRUCIBLE_REFERENCES + "arduino.md",
                         f"§S2: arduino.toml crucible_reference = {value!r}")
        self.assertNotIn("no per-stack reference file", value)

    def test_every_other_crucible_reference_is_its_agents_store_reference(self):
        wrong = {s: _crucible_reference(s) for s, f in STACK_REFERENCE_FILE.items()
                 if s != "arduino" and _crucible_reference(s) != AGENTS_CRUCIBLE_REFERENCES + f}
        self.assertEqual(wrong, {}, "§S2: crucible_reference cites ~/.agents/skills/crucible/references/")

    def test_java_testing_practices_writes_panache_find_as_a_call(self):
        lines = (SKILLS_SRC / "memory-templates" / "java-testing-practices.md").read_text(
            encoding="utf-8").splitlines()
        bare = [f"java-testing-practices.md:{n}: {ln.strip()}" for n, ln in enumerate(lines, 1)
                if "`find`" in ln]
        self.assertEqual(bare, [], "§S2: Panache's method is written `find()`, not the Pi tool name")
        mock = [ln for ln in lines if "Mock static query methods" in ln]
        self.assertEqual(len(mock), 1)
        self.assertIn("`find()`", mock[0])

    def test_model_b_skill_ontology_line_cites_model_bs_frozen_dn_without_crucible_prefix(self):
        lines = [ln for ln in (SKILLS_SRC / "model-b" / "SKILL.md").read_text(encoding="utf-8").splitlines()
                 if ln.startswith("Ontology (LOCKED):")]
        self.assertEqual(len(lines), 1, "precondition: one ontology line")
        self.assertIn("`docs/research/DN-model-b-language.md`", lines[0])
        self.assertNotIn("crucible:", lines[0], f"§S2: ontology line: {lines[0]}")

    def test_bootstrap_carries_no_nai_project_memory_example(self):
        lines = (SKILLS_SRC / "bootstrap" / "SKILL.md").read_text(encoding="utf-8").splitlines()
        hits = [f"bootstrap/SKILL.md:{n}: {ln.strip()[:120]}" for n, ln in enumerate(lines, 1)
                if "-nai/memory" in ln]
        self.assertEqual(hits, [], "§S2: the NAI project-memory examples are removed")


if __name__ == "__main__":
    unittest.main()
