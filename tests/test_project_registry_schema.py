"""The project-settings schema and the schema-driven ``init`` generator
(CR-MDB-043 §S1–§S2; PRD D3.1, amended 2026-09-26).

``modelb_axi/project_schema.toml`` declares every project-registry key once —
its file, scope, source (``ask`` / ``derive`` / ``capture``), validation and
readers — and ``modelb-axi init`` asks, derives, validates, previews and renders
a project's settings from it alone.

Seams these tests pin (GREEN implements them):

* the schema is ONE top-level TOML array of tables, one table per key, each keyed
  by its ``name`` field (§S1 lists ``name`` as a field);
* ``scaffold.PROJECT_SCHEMA_PATH`` — the default schema path, the packaged
  ``modelb_axi/project_schema.toml`` — is read by ``run_init`` AT CALL TIME, so a
  test swaps in a fixture schema with ``mock.patch.object``;
* ``scaffold.load_schema(path)`` loads and checks a schema, raising
  :class:`scaffold.ScaffoldError` naming an unknown derive/validate rule;
* an ``ask`` key's value is read from the ``argparse`` dest of its flag
  (``--team-lead`` -> ``team_lead``), exactly as argparse names it.

Every ``modelb-axi`` run is sandboxed: ``--target``/``--modelb-home`` under a
temp dir and ``HOME``, ``MODELB_HOME``, ``XDG_DATA_HOME``,
``PI_CODING_AGENT_DIR`` pointed there. The one read outside the sandbox is
Crucible's installed python client, resolved through
``~/.crucible/crucible-clients.json`` (skipped, naming it, when absent) and run
against an in-test stub server on an ephemeral port.

Stdlib only.
"""

import argparse
import contextlib
import datetime
import http.server
import importlib.util
import inspect
import io
import json
import os
import re
import shutil
import site
import subprocess
import sys
import tempfile
import threading
import tomllib
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from modelb_axi import agents as _agents
from modelb_axi import cli as _cli
from modelb_axi import permission_policy as _permission_policy
from modelb_axi import scaffold
from modelb_axi.hooks import compile_wiring
from tests._helpers import decode_axi, installed_crucible_file, parse_env_file
from tests._helpers import run_module, write_install_toml
# The sibling grep gate's provenance exemption (imported as a module so its
# TestCase classes are not re-collected here).
from tests import test_crucible_skill as _crucible_skill_gates

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "modelb_axi" / "project_schema.toml"
SCHEMA_WHEEL_MEMBER = "modelb_axi/project_schema.toml"

#: The eight keys §S1 declares — exactly these.
SCHEMA_KEYS = frozenset({
    "PROJECT_NAME", "PROJECT_TOKEN", "PROJECT_ACRONYM", "ORCHESTRATOR_LABEL",
    "REPO_OWNER", "PROJECT_STACKS", "CRUCIBLE_PROJECT_KEY", "SANDESH_PROJECT",
})

#: Every §S1 field; nothing else may appear in an entry (no value, no default:
#: "it carries rules only, never a project's value").
S1_FIELDS = frozenset({
    "name", "description", "required", "file", "scope", "source",
    "flag", "rule", "inputs", "step", "override", "validate", "readers",
})
LEGAL_FILES = frozenset({".env", ".env.local"})
LEGAL_SCOPES = frozenset({"root", "root+sub"})
LEGAL_SOURCES = frozenset({"ask", "derive", "capture"})

#: Today's ask keys and their `init` flags (the flag names do not change).
ASK_FLAGS = {
    "PROJECT_NAME": "--name",
    "PROJECT_TOKEN": "--token",
    "PROJECT_ACRONYM": "--acronym",
    "REPO_OWNER": "--owner",
    "PROJECT_STACKS": "--stacks",
}

#: `init` flags that set no registry key (plan inputs, run switches, globals).
NON_REGISTRY_INIT_FLAGS = frozenset({
    "-h", "--help", "--mode", "--repo-shape", "--harnesses", "--target",
    "--dry-run", "--no-commit", "--register", "--yes", "--force-managed",
    "--modelb-home",
})

# The scaffold inputs every byte-identity golden below is derived from.
NAME, TOKEN, ACRONYM, OWNER, STACKS = "My Project", "myproj", "MYP", "tester", "python"
DERIVED_SANDESH = "MyProject"

#: What `.env.local`'s comment must no longer say: the overlay is not where the
#: Crucible project key is filled (it moved to `.env`, CR-MDB-043 §S1/§S2).
_ENV_LOCAL_KEY_HINT_RE = re.compile(
    r"crucible|regist(?:er|ering|ration)|project[ _-]?key|projectkey", re.IGNORECASE)

#: The user site of THIS interpreter, resolved before any HOME override, so a
#: sandboxed subprocess still imports what the real user site provides.
_USER_BASE = site.getuserbase()


# ------------------------------------------------------------------ helpers ----

def _scaffold_seam(name: str):
    """A §S2 seam GREEN adds to ``modelb_axi.scaffold`` (``load_schema``,
    ``PROJECT_SCHEMA_PATH``); a ``KeyError`` names it while it is absent."""
    return vars(scaffold)[name]


def _sandbox_env(root: Path) -> dict:
    """The env overrides that pin every home-derived path under ``root``."""
    env = {
        "HOME": root / "home",
        "MODELB_HOME": root / "mbhome",
        "XDG_DATA_HOME": root / "xdg",
        "PI_CODING_AGENT_DIR": root / "pi-agent",
    }
    for path in env.values():
        path.mkdir(parents=True, exist_ok=True)
    out = {k: str(v) for k, v in env.items()}
    out["PYTHONUSERBASE"] = _USER_BASE
    return out


def _init(root: Path, target: Path, *extra: str, mode="solo", shape="standalone",
          name=NAME):
    """A sandboxed ``modelb-axi --yes init`` through the real CLI entry."""
    env = _sandbox_env(root)
    home = env["MODELB_HOME"]
    if not (Path(home) / "install.toml").is_file():
        write_install_toml(home, harnesses=("pi",))
    return run_module(
        "--yes", "init",
        "--name", name, "--token", TOKEN, "--acronym", ACRONYM,
        "--mode", mode, "--repo-shape", shape, "--stacks", STACKS,
        "--owner", OWNER, "--target", str(target), "--modelb-home", home,
        *extra, env_overrides=env, timeout=180,
    )


def _schema_table(path: Path = SCHEMA_PATH) -> tuple[str, list[dict]]:
    """``(table_name, entries)`` of the schema's one top-level array of tables."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    tables = [
        (key, value) for key, value in data.items()
        if isinstance(value, list) and value and all(isinstance(e, dict) for e in value)
    ]
    if len(tables) != 1:
        raise AssertionError(
            f"{path} must hold exactly ONE top-level array of tables (one table "
            f"per key); found {[k for k, _ in tables]}"
        )
    return tables[0]


def _entries_by_name(path: Path = SCHEMA_PATH) -> dict:
    return {e.get("name"): e for e in _schema_table(path)[1]}


def _init_parser() -> argparse.ArgumentParser:
    parser = _cli._build_parser()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return sub.choices["init"]


def _registry_value_in(obj, key: str):
    """The value reported for registry ``key`` anywhere in a decoded envelope:
    a mapping ``{key: value}``, a ``{name|key: key, value: v}`` row, or a
    ``"KEY=value"`` string. ``None`` when not reported."""
    if isinstance(obj, dict):
        if isinstance(obj.get(key), str):
            return obj[key]
        if key in (obj.get("name"), obj.get("key")) and isinstance(obj.get("value"), str):
            return obj["value"]
        values = obj.values()
    elif isinstance(obj, list):
        values = obj
    elif isinstance(obj, str) and obj.startswith(key + "="):
        return obj[len(key) + 1:]
    else:
        return None
    for value in values:
        found = _registry_value_in(value, key)
        if found is not None:
            return found
    return None


def _key_lines(text: str, key: str) -> list[str]:
    return [line for line in text.splitlines(keepends=True) if line.startswith(key + "=")]


def _without_keys(text: str, *keys: str) -> str:
    return "".join(
        line for line in text.splitlines(keepends=True)
        if not line.startswith(tuple(k + "=" for k in keys))
    )


# ------------------------------------------------------------------ goldens ----
# Today's (pre-CR-MDB-043) renderings for the inputs above, pinned literally.

def _golden_env(label: str, *, with_stacks: bool) -> str:
    text = (
        "# Project naming registry (CR-MDB-013 scaffold; committed).\n"
        f"PROJECT_NAME={NAME}\n"
        f"PROJECT_TOKEN={TOKEN}\n"
        f"PROJECT_ACRONYM={ACRONYM}\n"
        f"ORCHESTRATOR_LABEL={label}\n"
        f"REPO_OWNER={OWNER}\n"
    )
    return text + (f"PROJECT_STACKS={STACKS}\n" if with_stacks else "")


#: Today's `.gitignore` description of `.env.local` — the one `.gitignore` line
#: the amended AC2 lets change (it must no longer call `.env.local` a registry
#: file; C4 FIX F7).
GOLDEN_GITIGNORE_ENV_LOCAL_COMMENT = "# Local-only registry overlay — never committed.\n"

GOLDEN_GITIGNORE = (
    GOLDEN_GITIGNORE_ENV_LOCAL_COMMENT +
    ".env.local\n"
    "\n"
    "# CR worktrees live inside the repo (inheriting Pi's project trust).\n"
    ".worktrees/\n"
    "\n"
    "# Tooling debris.\n"
    "__pycache__/\n"
    "test-reports/\n"
)

#: Today's project-key setup task — the one README line §S2 changes.
GOLDEN_KEY_TASK = (
    "- [ ] Register the project in Crucible and paste the key into `.env.local` "
    "(`CRUCIBLE_PROJECT_KEY=`) — manual step (registrations are manual in "
    "scaffold v1)"
)


def _golden_readme(label: str, mode: str, today: str) -> str:
    # MIGRATED PIN (CR-MDB-043 C4 FIX F1, amended AC2): the multi-mode Sandesh
    # setup task names SANDESH_PROJECT's value and address, not PROJECT_NAME.
    sandesh_task = (
        f"- [ ] Sandesh setup + register (`{DERIVED_SANDESH}`, "
        f"`Mainline - {DERIVED_SANDESH}`) — "
        "manual step (registrations are manual in scaffold v1)\n"
        if mode != "solo" else ""
    )
    return (
        f"# {NAME} — CR queue\n"
        "\n"
        f"**Project:** {NAME} (acronym: {ACRONYM} · orchestrator: `{label}`) · "
        "**Design contract:** _fill in (`docs/research/PRD-….md`)_ · "
        "**Evidence base:** _fill in_ · "
        "**Ontology:** `~/.agents/skills/model-b/SKILL.md` · "
        "**Target release:** 0.1.0\n"
        "\n"
        "Queue rows enumerate the whole delivery (STRUCTURE only). Live status "
        "is DERIVED on the Crucible board (plans/cycles/milestones) — never "
        "hand-maintained here.\n"
        "\n"
        "## Queue\n"
        "\n"
        "| CR | Title | Wave | Depends on |\n"
        "|---|---|---|---|\n"
        "\n"
        "## Setup tasks (pre-wave — not a wave; a wave is a grouping of CRs)\n"
        "\n"
        f"- [x] Scaffold via `modelb-axi init` — {today}\n"
        f"{GOLDEN_KEY_TASK}\n"
        f"{sandesh_task}"
        "- [ ] Confirm the remote owner matches `REPO_OWNER` in `.env` before "
        "the first wave-boundary gate\n"
        "\n"
        "## Notes\n"
        "\n"
        f"- {today}: repository scaffolded by `modelb-axi init`.\n"
    )


def _golden_agents_md(label: str, mode: str) -> str:
    """Today's project AGENTS.md. The capability-contract section is rendered
    from the requirements data (CR-MDB-036 §S6), which this CR does not touch."""
    return (
        f"# {NAME} — project AGENTS.md\n"
        "\n"
        "Project-level conventions for every session/agent working this repo. "
        "Scaffolded by `modelb-axi init`.\n"
        "\n"
        "## Identity & naming (registry: `.env` at the project root)\n"
        f"- Project **{NAME}** · token `{TOKEN}` · acronym `{ACRONYM}` · owner `{OWNER}`.\n"
        f"- Orchestrator label: `{label}` (mode: {mode}; mode-aware — solo "
        "`vidushi-<token>`, multi `Mainline-<token>`).\n"
        f"- CR ids: `CR-{ACRONYM}-NNN`. Crucible agentIds follow the stack "
        "client's agent-naming header — never improvised.\n"
        "\n"
        "## Workflow rules\n"
        "- A **wave** is a grouping of CRs marking an execution boundary; setup "
        "tasks and releases are NOT waves.\n"
        "- Queue (`docs/changes/README.md`) holds STRUCTURE only; live status is "
        "DERIVED on the Crucible board.\n"
        "- Run context (post-036): workflow cycle context is attached by the "
        "tooling at ingest time — never hand-export cycle identifiers into the "
        "environment or into this file.\n"
        "- Registrations are manual in scaffold v1 — complete the manual setup "
        "tasks in the queue README.\n"
        "\n"
        f"## Skill freeze (derived from --stacks: {STACKS})\n"
        f"- {STACKS}: use the `{STACKS}` stack skills and generated "
        "RED/GREEN/VERIFY/FIX agents as frozen at scaffold time.\n"
        "\n"
        "## Harness anchors (installed set: pi)\n"
        "- pi (pi.dev): reads `AGENTS.md` natively — no separate anchor file emitted.\n"
        "\n"
        + scaffold._render_capability_contract([STACKS], ("pi",))
        + "\n"
        "## Generator note\n"
        "- Agents regenerate from the INSTALLATION's generator assets — never "
        "from a per-project copy.\n"
    )


def _golden_memory_index(template_names: list[str]) -> str:
    lines = "\n".join(f"- [{n}]({n})" for n in template_names)
    return (
        f"# {NAME} — project memory index\n"
        "\n"
        "Seeded by `modelb-axi init` from the installation's `memory-templates/` "
        f"filtered by --stacks ({STACKS}).\n"
        "\n"
        f"{lines}\n"
    )


def _golden_sub_agents_md(sub: str) -> str:
    return (
        f"# {NAME} / {sub} — sub-project AGENTS.md\n"
        "\n"
        f"Sub-project override for `{sub}/` (token `{TOKEN}`, acronym `{ACRONYM}`). "
        "Tools resolve THIS directory's `.env` registry — never the repo root's on "
        "this sub-project's behalf. Repo-wide conventions live in the root "
        "`AGENTS.md`.\n"
    )


def _reference_other_files(home: Path, mode: str, scratch: Path) -> dict:
    """Today's bytes for every emitted file init renders WITHOUT any registry
    value — hook instances + compiled wiring + compiler report, agent
    definitions, the permission policy, memory templates, the research
    placeholder — produced by the modules that own them (none in this CR's
    scope), into ``scratch``."""
    stacks, harnesses = [STACKS], ["pi"]
    files: dict = {"docs/research/.gitkeep": b""}
    instances = scaffold._hook_instances(stacks, mode)
    for instance in instances:
        files[f"hooks/instances/{instance['command']}.toml"] = (
            scaffold._render_instance_toml(instance).encode("utf-8"))
    report = compile_wiring(instances, harnesses, scratch, scaffold._hook_scripts_root(home))
    files["hooks/README.md"] = scaffold._render_hooks_readme(
        report, instances, harnesses).encode("utf-8")
    _agents.render_project(scratch, stacks, harnesses, *scaffold._agent_sources(home))
    _permission_policy.place_project_policy(scratch)
    for path in scratch.rglob("*"):
        if path.is_file():
            files[str(path.relative_to(scratch))] = path.read_bytes()
    for template in scaffold._select_memory_templates(
            scaffold._memory_templates_dir(home), stacks):
        files[f"docs/memory/{template.name}"] = template.read_bytes()
    return files


def _emitted_files(target: Path) -> set:
    return {
        str(p.relative_to(target)) for p in target.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(target).parts
    }


def _run_init_in_process(env: dict, home: Path, target: Path, schema: Path = SCHEMA_PATH,
                         **fields):
    """``scaffold.run_init`` in process against ``schema`` (sandboxed by
    ``env``); ``fields`` override the default ``init`` args. Returns
    ``(rc, decoded axi, stderr)``."""
    args = argparse.Namespace(
        name=NAME, token=TOKEN, acronym=ACRONYM, mode="solo",
        repo_shape="standalone", stacks=STACKS, owner=OWNER,
        target=str(target), dry_run=False, no_commit=True, register=False,
    )
    for key, value in fields.items():
        setattr(args, key, value)
    out, err = io.StringIO(), io.StringIO()
    with (
        mock.patch.object(scaffold, "PROJECT_SCHEMA_PATH", schema),
        mock.patch.dict(os.environ, {"PI_CODING_AGENT_DIR": env["PI_CODING_AGENT_DIR"]}),
        contextlib.redirect_stdout(out), contextlib.redirect_stderr(err),
    ):
        rc = scaffold.run_init(args, home)
    return rc, decode_axi(out.getvalue()), err.getvalue()


def _schema_with(root: Path, extra: str, name: str = "fixture-schema.toml") -> Path:
    """A fixture schema: the packaged schema plus the ``extra`` TOML tables."""
    path = root / name
    path.write_text(SCHEMA_PATH.read_text(encoding="utf-8") + extra, encoding="utf-8")
    return path


# ------------------------------------------------------------------ §S1 schema ----

class ProjectSchemaAssetTest(unittest.TestCase):
    """§S1 — ``modelb_axi/project_schema.toml`` declares the eight registry
    keys, each with every §S1 field and legal values, and no project value."""

    def _entries(self) -> list[dict]:
        self.assertTrue(
            SCHEMA_PATH.is_file(),
            f"§S1: the project-settings schema must exist at {SCHEMA_PATH}",
        )
        return _schema_table()[1]

    def test_schema_declares_exactly_the_eight_registry_keys(self):
        names = [str(e.get("name")) for e in self._entries()]
        self.assertEqual(
            len(names), len(set(names)), f"§S1: a key is declared twice: {names}")
        self.assertEqual(
            set(names), SCHEMA_KEYS,
            f"§S1/AC: exactly the eight keys; extra {sorted(set(names) - SCHEMA_KEYS)}, "
            f"missing {sorted(SCHEMA_KEYS - set(names))}",
        )

    def test_every_entry_carries_every_s1_field_with_a_legal_value(self):
        for entry in self._entries():
            name = str(entry.get("name"))
            with self.subTest(key=name):
                stray = sorted(set(entry) - S1_FIELDS)
                self.assertEqual(
                    stray, [],
                    f"§S1: {name} carries fields outside §S1 (a schema holds rules, "
                    f"never a value): {stray}",
                )
                for field in ("name", "description", "required", "file", "scope",
                              "source", "validate", "readers"):
                    self.assertIn(field, entry, f"§S1: {name} lacks `{field}`")
                self.assertRegex(name, r"^[A-Z][A-Z0-9_]*$")
                self.assertIsInstance(entry["description"], str)
                self.assertTrue(entry["description"].strip(), f"§S1: {name} description empty")
                self.assertIsInstance(entry["required"], bool, f"§S1: {name}.required")
                self.assertIn(entry["file"], LEGAL_FILES, f"§S1: {name}.file")
                self.assertIn(entry["scope"], LEGAL_SCOPES, f"§S1: {name}.scope")
                self.assertIn(entry["source"], LEGAL_SOURCES, f"§S1: {name}.source")
                self.assertIsInstance(entry["validate"], str)
                self.assertTrue(entry["validate"].strip(), f"§S1: {name}.validate empty")
                readers = entry["readers"]
                self.assertIsInstance(readers, list, f"§S1: {name}.readers")
                self.assertTrue(readers, f"§S1: {name}.readers names no reader")
                self.assertTrue(
                    all(isinstance(r, str) and r.strip() for r in readers),
                    f"§S1: {name}.readers must be non-empty strings; got {readers!r}",
                )

    def test_each_source_carries_its_own_fields_and_no_other(self):
        keys = {e.get("name") for e in self._entries()}
        for entry in self._entries():
            name, source = entry.get("name"), entry.get("source")
            with self.subTest(key=name, source=source):
                if source == "ask":
                    self.assertRegex(entry.get("flag", ""), r"^--[a-z][a-z0-9-]*$")
                    for absent in ("rule", "inputs", "step", "override"):
                        self.assertNotIn(absent, entry, f"§S1: ask key {name} has `{absent}`")
                elif source == "derive":
                    self.assertIsInstance(entry.get("rule"), str, f"§S1: {name}.rule")
                    self.assertTrue(entry["rule"].strip())
                    inputs = entry.get("inputs") or []
                    self.assertIsInstance(inputs, list, f"§S1: {name}.inputs")
                    self.assertTrue(inputs, f"§S1: derive key {name} names no input")
                    for item in inputs:
                        self.assertTrue(
                            item in keys or (isinstance(item, str) and item.isidentifier()
                                             and item.islower()),
                            f"§S1: {name} input {item!r} is neither a schema key nor "
                            "an init input",
                        )
                    self.assertNotIn("flag", entry)
                    self.assertNotIn("step", entry)
                    if "override" in entry:
                        self.assertRegex(entry["override"], r"^--[a-z][a-z0-9-]*$")
                else:
                    self.assertIsInstance(entry.get("step"), str, f"§S1: {name}.step")
                    self.assertTrue(entry["step"].strip())
                    for absent in ("flag", "rule", "inputs", "override"):
                        self.assertNotIn(absent, entry, f"§S1: capture key {name} has `{absent}`")

    def test_todays_asked_keys_keep_their_init_flags(self):
        by_name = _entries_by_name() if SCHEMA_PATH.is_file() else {}
        for key, flag in ASK_FLAGS.items():
            with self.subTest(key=key):
                entry = by_name.get(key, {})
                self.assertEqual(
                    (entry.get("source"), entry.get("flag")), ("ask", flag),
                    f"§S1: {key} is asked by `init {flag}`; got {entry!r}",
                )

    def test_crucible_project_key_is_captured_into_the_root_env(self):
        entry = _entries_by_name().get("CRUCIBLE_PROJECT_KEY", {}) if SCHEMA_PATH.is_file() else {}
        self.assertEqual(
            (entry.get("file"), entry.get("source"), entry.get("scope")),
            (".env", "capture", "root"),
            "§S1: CRUCIBLE_PROJECT_KEY moves to the committed root `.env` and is "
            f"captured at Crucible registration; got {entry!r}",
        )

    def test_sandesh_project_derives_from_project_name_with_an_override_flag(self):
        entry = _entries_by_name().get("SANDESH_PROJECT", {}) if SCHEMA_PATH.is_file() else {}
        self.assertEqual(
            (entry.get("source"), entry.get("inputs"), entry.get("override"),
             entry.get("file")),
            ("derive", ["PROJECT_NAME"], "--sandesh-project", ".env"),
            f"§S1: SANDESH_PROJECT derives from PROJECT_NAME, overridable by "
            f"--sandesh-project, in `.env`; got {entry!r}",
        )

    def test_orchestrator_label_derives_from_the_init_mode_and_the_token(self):
        entry = _entries_by_name().get("ORCHESTRATOR_LABEL", {}) if SCHEMA_PATH.is_file() else {}
        self.assertEqual(entry.get("source"), "derive", f"§S1: got {entry!r}")
        self.assertIn("mode", entry.get("inputs", []), f"§S1: init input `mode`; got {entry!r}")
        self.assertIn("PROJECT_TOKEN", entry.get("inputs", []), f"§S1: got {entry!r}")
        self.assertNotIn("override", entry, "the label has no override flag")

    def test_scopes_reproduce_todays_sub_project_registry(self):
        """A monorepo sub-project's `.env` carries today's five keys and never
        PROJECT_STACKS or the project key (§S2 byte-identity)."""
        by_name = _entries_by_name() if SCHEMA_PATH.is_file() else {}
        expected = {
            "PROJECT_NAME": "root+sub", "PROJECT_TOKEN": "root+sub",
            "PROJECT_ACRONYM": "root+sub", "ORCHESTRATOR_LABEL": "root+sub",
            "REPO_OWNER": "root+sub", "PROJECT_STACKS": "root",
            "CRUCIBLE_PROJECT_KEY": "root",
        }
        actual = {k: by_name.get(k, {}).get("scope") for k in expected}
        self.assertEqual(actual, expected)

    def test_every_key_lives_in_the_committed_env(self):
        """`.env.local` stays the gitignored overlay with no schema key today."""
        by_name = _entries_by_name() if SCHEMA_PATH.is_file() else {}
        self.assertEqual(
            {k: e.get("file") for k, e in by_name.items()},
            dict.fromkeys(SCHEMA_KEYS, ".env"),
        )

    def test_scaffold_reads_the_packaged_schema_by_default(self):
        self.assertTrue(
            hasattr(scaffold, "PROJECT_SCHEMA_PATH"),
            "§S2 seam: scaffold.PROJECT_SCHEMA_PATH names the default schema",
        )
        self.assertEqual(Path(_scaffold_seam("PROJECT_SCHEMA_PATH")).resolve(),
                         SCHEMA_PATH.resolve())


class ProjectSchemaWheelTest(unittest.TestCase):
    """§S1/AC — the schema ships in the wheel (asserted against a genuinely
    built wheel, like test_tooling_detachment's built-wheel check)."""

    def test_built_wheel_ships_the_schema_with_the_eight_keys(self):
        if importlib.util.find_spec("build") is None:
            self.skipTest(
                "the `build` frontend is unavailable, so no genuine wheel can be "
                "produced; the source tree is not an acceptable substitute"
            )
        with tempfile.TemporaryDirectory(prefix="r43-wheel-") as outdir:
            result = subprocess.run(
                [sys.executable, "-m", "build", "--wheel", "--no-isolation",
                 "--outdir", outdir, str(REPO_ROOT)],
                capture_output=True, text=True, timeout=600,
            )
            self.assertEqual(
                0, result.returncode,
                f"the wheel build failed: {(result.stderr or result.stdout).strip()[-600:]}",
            )
            wheels = sorted(Path(outdir).glob("*.whl"))
            self.assertEqual(1, len(wheels), f"got {[w.name for w in wheels]}")
            with zipfile.ZipFile(wheels[0]) as archive:
                members = set(archive.namelist())
                self.assertIn(
                    SCHEMA_WHEEL_MEMBER, members,
                    f"§S1/AC: the built wheel {wheels[0].name} must ship the schema",
                )
                shipped = tomllib.loads(archive.read(SCHEMA_WHEEL_MEMBER).decode("utf-8"))
        tables = [v for v in shipped.values() if isinstance(v, list)]
        self.assertEqual(len(tables), 1)
        self.assertEqual({e.get("name") for e in tables[0]}, SCHEMA_KEYS)


# ------------------------------------------------------------------ §S2 CLI ----

class ProjectSchemaCliAgreementTest(unittest.TestCase):
    """§S2 — the CLI stays argparse, and the schema and the `init` parser agree."""

    def setUp(self):
        self.assertTrue(SCHEMA_PATH.is_file(), f"§S1: schema absent at {SCHEMA_PATH}")
        self.entries = _schema_table()[1]
        self.parser = _init_parser()
        self.flags = {s for a in self.parser._actions for s in a.option_strings}

    def _declared_flags(self) -> set:
        declared = {e["flag"] for e in self.entries if e.get("source") == "ask"}
        return declared | {e["override"] for e in self.entries if "override" in e}

    def test_every_ask_and_override_flag_exists_on_the_init_parser(self):
        declared = self._declared_flags()
        self.assertEqual(
            declared, set(ASK_FLAGS.values()) | {"--sandesh-project"},
            "§S1: today's five ask flags plus the SANDESH_PROJECT override",
        )
        self.assertEqual(
            sorted(declared - self.flags), [],
            "§S2: every ask/override flag the schema declares is an `init` flag",
        )

    def test_every_registry_setting_init_flag_is_declared_in_the_schema(self):
        registry_flags = self.flags - NON_REGISTRY_INIT_FLAGS
        self.assertIn("--sandesh-project", registry_flags)
        self.assertEqual(
            sorted(registry_flags - self._declared_flags()), [],
            "§S2: an `init` flag that sets a registry key must be declared in the schema",
        )

    def test_every_init_input_a_derive_rule_names_is_an_init_parser_dest(self):
        keys = {e["name"] for e in self.entries}
        dests = {a.dest for a in self.parser._actions}
        inputs = {i for e in self.entries if e.get("source") == "derive"
                  for i in e.get("inputs", []) if i not in keys}
        self.assertIn("mode", inputs)
        self.assertEqual(sorted(inputs - dests), [], "§S1: an init input is an `init` dest")


# ------------------------------------------------------------------ §S2 byte-identity ----

class _Shared:
    """Holder: the loader collects only module-level TestCase classes, so
    the shared base below runs only through its configured subclasses."""

    class InitAgainstToday(unittest.TestCase):
        """One sandboxed `init` per configuration, compared with today's output for
        the same inputs: only the four §S2 differences may appear."""

        MODE = "solo"
        SHAPE = "standalone"
        SUBS: tuple = ()
        LABEL = "vidushi-myproj"

        @classmethod
        def setUpClass(cls):
            cls._root = Path(tempfile.mkdtemp(prefix="r43-diff-"))
            cls._target = cls._root / "proj"
            cls._result = _init(cls._root, cls._target, mode=cls.MODE, shape=cls.SHAPE)
            cls._today = datetime.date.today().isoformat()
            home = cls._root / "mbhome"
            scratch = cls._root / "reference"
            scratch.mkdir()
            # Same HOME as the init subprocess: the policy reads Path.home().
            with mock.patch.dict(os.environ, {"HOME": str(cls._root / "home")}):
                cls._reference = _reference_other_files(home, cls.MODE, scratch)
            cls._template_names = [
                t.name for t in scaffold._select_memory_templates(
                    scaffold._memory_templates_dir(home), [STACKS])
            ]

        @classmethod
        def tearDownClass(cls):
            shutil.rmtree(cls._root, ignore_errors=True)

        def _read(self, rel: str) -> str:
            path = self._target / rel
            self.assertTrue(
                path.is_file(),
                f"{rel} not emitted; init exit={self._result.returncode} "
                f"stderr={self._result.stderr[-800:]!r}",
            )
            return path.read_text(encoding="utf-8")

        def test_root_env_is_todays_plus_sandesh_project_and_the_project_key(self):
            text = self._read(".env")
            self.assertEqual(
                _key_lines(text, "SANDESH_PROJECT"), [f"SANDESH_PROJECT={DERIVED_SANDESH}\n"],
                f"§S2/AC: SANDESH_PROJECT defaults to PROJECT_NAME without whitespace; .env={text!r}",
            )
            self.assertEqual(
                _key_lines(text, "CRUCIBLE_PROJECT_KEY"), ["CRUCIBLE_PROJECT_KEY=\n"],
                f"§S2/AC: CRUCIBLE_PROJECT_KEY= is rendered empty in the root .env; .env={text!r}",
            )
            self.assertEqual(
                _without_keys(text, "SANDESH_PROJECT", "CRUCIBLE_PROJECT_KEY"),
                _golden_env(self.LABEL, with_stacks=True),
                "§S2/AC: every other root .env line is today's, in today's order",
            )

        def test_env_local_carries_no_schema_key(self):
            text = self._read(".env.local")
            self.assertEqual(
                parse_env_file(self._target / ".env.local"), {},
                f"§S2/AC: CRUCIBLE_PROJECT_KEY moved out of .env.local, which holds no "
                f"schema key today; .env.local={text!r}",
            )

        def test_env_local_does_not_send_the_crucible_key_there(self):
            """§S2 defect: the key lives in `.env`; the overlay's comment must
            not tell the user to fill a Crucible project key into `.env.local`."""
            text = self._read(".env.local")
            lines = text.splitlines()
            self.assertEqual(
                [line for line in lines
                 if any(key in line for key in SCHEMA_KEYS)], [],
                f"§S2: .env.local names no schema key, commented or not; {text!r}",
            )
            self.assertEqual(
                [line for line in lines if _ENV_LOCAL_KEY_HINT_RE.search(line)], [],
                f"§S2: CRUCIBLE_PROJECT_KEY is filled in .env, so .env.local's comment "
                f"must not mention Crucible registration or the project key; {text!r}",
            )

        def test_queue_readme_differs_only_in_the_project_key_setup_task(self):
            actual = self._read("docs/changes/README.md").splitlines(keepends=True)
            golden = _golden_readme(self.LABEL, self.MODE, self._today).splitlines(keepends=True)
            index = golden.index(GOLDEN_KEY_TASK + "\n")
            self.assertEqual(len(actual), len(golden), f"README={''.join(actual)!r}")
            self.assertEqual(actual[:index] + actual[index + 1:], golden[:index] + golden[index + 1:])
            task = actual[index]
            self.assertTrue(task.startswith("- [ ] Register the project in Crucible"), task)
            self.assertIn("`.env`", task, "§S2: the setup task names `.env` for the key")
            self.assertIn("CRUCIBLE_PROJECT_KEY", task)
            self.assertNotIn(".env.local", task, "§S2: the key no longer goes to .env.local")

        def test_agents_md_differs_only_in_its_identity_section_naming_sandesh_project(self):
            actual = self._read("AGENTS.md")
            golden = _golden_agents_md(self.LABEL, self.MODE)
            head, rules = "## Identity & naming", "## Workflow rules"
            a_pre, a_rest = actual.split(head, 1)
            g_pre, g_rest = golden.split(head, 1)
            a_identity, a_post = a_rest.split(rules, 1)
            g_identity, g_post = g_rest.split(rules, 1)
            self.assertEqual((a_pre, a_post), (g_pre, g_post),
                             "§S2/AC: AGENTS.md outside the identity section is today's")
            self.assertIn("SANDESH_PROJECT", a_identity,
                          f"§S2: the Identity & naming section names SANDESH_PROJECT; got {a_identity!r}")
            remaining = iter(a_identity.splitlines())
            missing = [line for line in g_identity.splitlines()
                       if not any(line == seen for seen in remaining)]
            self.assertEqual(missing, [], "§S2/AC: today's identity lines are all kept, in order")

        def test_every_other_emitted_file_is_byte_identical_to_today(self):
            """Regression pin (passes before GREEN): guards the AC's 'exactly these
            differences' against a schema-driven rewrite leaking into files that
            carry no registry key."""
            literal = {
                "docs/memory/INDEX.md": _golden_memory_index(self._template_names).encode("utf-8"),
            }
            for sub in self.SUBS:
                literal[f"{sub}/AGENTS.md"] = _golden_sub_agents_md(sub).encode("utf-8")
            for rel, expected in {**self._reference, **literal}.items():
                with self.subTest(file=rel):
                    path = self._target / rel
                    self.assertTrue(path.is_file(), f"{rel} not emitted")
                    self.assertEqual(path.read_bytes(), expected, f"{rel} differs from today")

        def test_gitignore_differs_only_in_its_description_of_env_local(self):
            """MIGRATED PIN (C4 FIX F7, amended AC2): `.gitignore` was pinned
            byte-identical; its `.env.local` comment may now change, and must no
            longer call `.env.local` a registry file."""
            actual = self._read(".gitignore").splitlines(keepends=True)
            golden = GOLDEN_GITIGNORE.splitlines(keepends=True)
            index = golden.index(GOLDEN_GITIGNORE_ENV_LOCAL_COMMENT)
            self.assertEqual(len(actual), len(golden), f".gitignore={''.join(actual)!r}")
            self.assertEqual(actual[:index] + actual[index + 1:],
                             golden[:index] + golden[index + 1:],
                             "AC2: every other .gitignore line is today's")
            comment = actual[index]
            self.assertTrue(comment.startswith("# "), comment)
            self.assertNotRegex(
                comment, re.compile("registry", re.IGNORECASE),
                "AC2/§S2: `.env.local` is not a registry file; the .gitignore "
                f"comment must not describe it as one; got {comment!r}")

        def test_the_emitted_file_set_is_todays(self):
            """Regression pin (passes before GREEN): no file added or dropped."""
            expected = set(self._reference) | {
                ".env", ".env.local", ".gitignore", "AGENTS.md",
                "docs/changes/README.md", "docs/memory/INDEX.md",
            }
            for sub in self.SUBS:
                expected |= {f"{sub}/.env", f"{sub}/AGENTS.md"}
            self.assertEqual(_emitted_files(self._target), expected)


class SoloStandaloneInitAgainstTodayTest(_Shared.InitAgainstToday):
    pass


class MultiStandaloneInitAgainstTodayTest(_Shared.InitAgainstToday):
    MODE = "multi:2"
    LABEL = "Mainline-myproj"


class SoloMonorepoInitAgainstTodayTest(_Shared.InitAgainstToday):
    SHAPE = "monorepo:a,b"
    SUBS = ("a", "b")

    def test_sub_project_envs_are_todays_plus_keys_scoped_to_sub_projects(self):
        self.assertTrue(SCHEMA_PATH.is_file(), f"§S1: schema absent at {SCHEMA_PATH}")
        scope = _entries_by_name()["SANDESH_PROJECT"]["scope"]
        expected_sandesh = [f"SANDESH_PROJECT={DERIVED_SANDESH}\n"] if scope == "root+sub" else []
        for sub in self.SUBS:
            with self.subTest(sub=sub):
                text = self._read(f"{sub}/.env")
                self.assertEqual(_key_lines(text, "SANDESH_PROJECT"), expected_sandesh,
                                 f"§S2: SANDESH_PROJECT per its scope ({scope}); {sub}/.env={text!r}")
                self.assertEqual(_key_lines(text, "CRUCIBLE_PROJECT_KEY"), [],
                                 "§S1: the project key is root-scoped")
                self.assertEqual(_without_keys(text, "SANDESH_PROJECT"),
                                 _golden_env(self.LABEL, with_stacks=False))


# ------------------------------------------------------------------ SANDESH_PROJECT ----

class SandeshProjectInitTest(unittest.TestCase):
    """§S2/AC — SANDESH_PROJECT defaults, overrides, is validated before any
    write, and is shown by --dry-run."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="r43-sandesh-"))
        self.target = self.root / "proj"

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _axi(self, result) -> dict:
        axi = decode_axi(result.stdout)
        self.assertEqual(axi.get("verb"), "init",
                         f"no init envelope: rc={result.returncode} stdout={result.stdout!r} "
                         f"stderr={result.stderr[-600:]!r}")
        return axi

    def test_dry_run_reports_the_derived_value_with_all_whitespace_removed(self):
        # MIGRATED PIN (C4 FIX F8): the name was "My Big\tProject"; a tab is a
        # control character, which no rendered value may now carry ("Values",
        # §S2). A no-break space and a doubled space keep "all whitespace".
        self.target.mkdir()
        result = _init(self.root, self.target, "--dry-run", name="My  Big\u00a0Project")
        axi = self._axi(result)
        self.assertIs(axi.get("ok"), True, f"got {axi!r}")
        self.assertEqual(_registry_value_in(axi, "SANDESH_PROJECT"), "MyBigProject",
                         f"§S2/AC: --dry-run shows SANDESH_PROJECT; got {axi!r}")
        self.assertEqual(os.listdir(self.target), [], "--dry-run writes nothing")

    def test_dry_run_reports_the_override(self):
        self.target.mkdir()
        result = _init(self.root, self.target, "--dry-run", "--sandesh-project", "Foo_Bar")
        axi = self._axi(result)
        self.assertIs(axi.get("ok"), True, f"got {axi!r}")
        self.assertEqual(_registry_value_in(axi, "SANDESH_PROJECT"), "Foo_Bar", f"got {axi!r}")
        self.assertEqual(os.listdir(self.target), [])

    def test_override_is_rendered_into_the_env_instead_of_the_derived_value(self):
        result = _init(self.root, self.target, "--sandesh-project", "Foo_Bar")
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr[-800:]!r}")
        text = (self.target / ".env").read_text(encoding="utf-8")
        self.assertEqual(_key_lines(text, "SANDESH_PROJECT"), ["SANDESH_PROJECT=Foo_Bar\n"],
                         f"§S2/AC: --sandesh-project overrides; .env={text!r}")

    def test_multi_readme_sandesh_task_names_the_override_and_its_address(self):
        """§S2/AC2 (C4 FIX F1): the multi-mode Sandesh setup task names
        SANDESH_PROJECT's value and address, not PROJECT_NAME."""
        result = _init(self.root, self.target, "--sandesh-project", "Foo_Bar", mode="multi:2")
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr[-800:]!r}")
        readme = (self.target / "docs" / "changes" / "README.md").read_text(encoding="utf-8")
        tasks = [line for line in readme.splitlines() if "Sandesh setup" in line]
        self.assertEqual(len(tasks), 1, readme)
        self.assertIn("(`Foo_Bar`, `Mainline - Foo_Bar`)", tasks[0])
        self.assertNotIn(NAME, tasks[0], "the task no longer names PROJECT_NAME")

    def test_whitespace_override_is_refused_before_anything_is_written(self):
        result = _init(self.root, self.target, "--sandesh-project", "a b")
        self.assertNotEqual(result.returncode, 0, f"stdout={result.stdout!r}")
        axi = self._axi(result)
        self.assertIs(axi.get("ok"), False, f"got {axi!r}")
        warnings = " ".join(str(w) for w in axi.get("warnings", []))
        self.assertTrue(
            "SANDESH_PROJECT" in warnings or "--sandesh-project" in warnings,
            f"§S2: the refusal names the key or its flag; warnings={warnings!r}",
        )
        self.assertTrue(
            not self.target.exists() or not any(self.target.iterdir()),
            f"§S2/AC: refused before anything is written; found "
            f"{sorted(os.listdir(self.target)) if self.target.exists() else []}",
        )


# ------------------------------------------------------------------ Crucible client ----

class CrucibleKeySetupNoticeTest(unittest.TestCase):
    """§S2/AC (C4 FIX F2) — `init`'s stderr summary and its envelope say
    that CRUCIBLE_PROJECT_KEY is empty until the project is registered in
    Crucible and must be filled in `.env` before any Crucible client call."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="r43-keynote-"))
        cls.real = _init(cls.root, cls.root / "proj")
        (cls.root / "dry").mkdir()
        cls.dry = _init(cls.root, cls.root / "dry", "--dry-run")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def _check(self, result):
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr[-800:]!r}")
        axi = decode_axi(result.stdout)
        self.assertIs(axi.get("ok"), True, f"got {axi!r}")
        required = axi.get("setup_required")
        self.assertIsInstance(required, list, f"§S2: envelope field setup_required; got {axi!r}")
        rows = [r for r in (required or []) if isinstance(r, dict) and r.get("key") == "CRUCIBLE_PROJECT_KEY"]
        self.assertEqual(len(rows), 1, f"setup_required={required!r}")
        self.assertEqual(rows[0].get("file"), ".env", f"the key is filled in .env; got {rows[0]!r}")
        note = str(rows[0].get("note", ""))
        for word in ("Crucible", "regist", ".env"):
            self.assertIn(word, note, f"the envelope note says {word!r}; got {note!r}")
        lines = [line for line in result.stderr.splitlines() if "CRUCIBLE_PROJECT_KEY" in line]
        self.assertEqual(len(lines), 1, f"one stderr summary line names the key; stderr={result.stderr!r}")
        for word in ("empty", "Crucible", "regist", ".env"):
            self.assertIn(word, lines[0], f"the stderr summary says {word!r}; got {lines[0]!r}")
        self.assertEqual([w for w in axi.get("warnings", []) if "CRUCIBLE_PROJECT_KEY" in str(w)],
                         [], "a setup notice is not a warning")

    def test_a_real_init_reports_the_key_to_fill(self):
        self._check(self.real)

    def test_a_dry_run_reports_the_key_to_fill(self):
        self._check(self.dry)


class RenderedValueHygieneTest(unittest.TestCase):
    """§S2 "Values" (C4 FIX F8) — no rendered value carries a control
    character, and SANDESH_PROJECT holds only letters, digits, `_`, `-`, `.`;
    each refusal happens before anything is written."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="r43-values-"))
        self.env = _sandbox_env(self.root)
        self.home = Path(self.env["MODELB_HOME"])
        write_install_toml(str(self.home), harnesses=("pi",))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _refused(self, key: str, **fields) -> str:
        target = self.root / f"t{len(os.listdir(self.root))}"
        rc, axi, err = _run_init_in_process(self.env, self.home, target, **fields)
        self.assertEqual((rc, axi.get("ok")), (2, False), f"{fields!r}: stderr={err[-600:]!r}")
        warnings = " ".join(str(w) for w in axi.get("warnings", []))
        self.assertIn(key, warnings, f"the refusal names {key}; warnings={warnings!r}")
        self.assertFalse(target.exists(), f"{fields!r}: refused before anything is written")
        return warnings

    def test_a_control_character_in_any_asked_value_is_refused(self):
        for dest, key, value in (
            ("name", "PROJECT_NAME", "My\nProject"),
            ("owner", "REPO_OWNER", "tes\tter"),
            ("acronym", "PROJECT_ACRONYM", "MY\x1bP"),
            ("token", "PROJECT_TOKEN", "my\x7fproj"),
            ("name", "PROJECT_NAME", "My\rProject"),
        ):
            with self.subTest(key=key, value=value):
                self._refused(key, **{dest: value})

    def test_an_illegal_sandesh_project_character_is_refused(self):
        for value in ("a=b", "a#b", 'a"b', "a'b", "a\u200bb", "a/b", "a\nb"):
            with self.subTest(value=value):
                self._refused("SANDESH_PROJECT", sandesh_project=value)

    def test_a_derived_sandesh_project_with_an_illegal_character_suggests_the_override(self):
        warnings = self._refused("SANDESH_PROJECT", name="My#Project")
        self.assertIn("--sandesh-project", warnings)
        self.assertIn("My#Project", warnings)

    def test_legal_values_still_render(self):
        target = self.root / "ok"
        rc, axi, err = _run_init_in_process(
            self.env, self.home, target, sandesh_project="Foo.Bar-1_x")
        self.assertEqual(rc, 0, f"stderr={err[-800:]!r}")
        self.assertEqual(parse_env_file(target / ".env").get("SANDESH_PROJECT"), "Foo.Bar-1_x")
        target = self.root / "derived"
        rc, axi, err = _run_init_in_process(self.env, self.home, target)
        self.assertEqual(rc, 0, f"stderr={err[-800:]!r}")
        self.assertEqual(parse_env_file(target / ".env").get("SANDESH_PROJECT"), DERIVED_SANDESH)


class _StubCrucible(http.server.BaseHTTPRequestHandler):
    """Answers every GET with an empty plan list; records the request paths."""

    seen: list = []

    def do_GET(self):  # noqa: N802 -- http.server's method name
        type(self).seen.append(self.path)
        body = json.dumps({"ok": True, "plans": []}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002 -- the base's name
        pass


class CrucibleClientResolvesScaffoldedKeyTest(unittest.TestCase):
    """§S2/AC — once its key is filled in `.env`, a freshly scaffolded project
    resolves through Crucible's installed client, out of process: the client's
    read-only `status` verb against an in-test stub server on an ephemeral port."""

    FILLED_KEY = "r43-stub-project-key"

    def setUp(self):
        self.client, reason = installed_crucible_file("python")
        if self.client is None:
            self.skipTest(reason)
        self.root = Path(tempfile.mkdtemp(prefix="r43-crucible-"))
        _StubCrucible.seen = []
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _StubCrucible)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_filled_env_key_resolves_through_the_installed_client(self):
        target = self.root / "proj"
        result = _init(self.root, target)
        self.assertEqual(result.returncode, 0, f"init failed: {result.stderr[-800:]!r}")
        env_path = target / ".env"
        # Fill the key the way the setup task says: in `.env`, on its empty line.
        env_path.write_text(
            env_path.read_text(encoding="utf-8").replace(
                "CRUCIBLE_PROJECT_KEY=\n", f"CRUCIBLE_PROJECT_KEY={self.FILLED_KEY}\n"),
            encoding="utf-8",
        )
        env = dict(os.environ)
        env.pop("PY_CRUCIBLE_PROJECT_DIR", None)
        env.update(HOME=str(self.root / "home"),
                   CRUCIBLE_URL=f"http://127.0.0.1:{self.server.server_address[1]}")
        run = subprocess.run(
            [sys.executable, str(self.client), "status", "--project-dir", str(target)],
            capture_output=True, text=True, env=env, cwd=str(target), timeout=60,
        )
        self.assertNotIn(
            "CRUCIBLE_PROJECT_KEY not found", run.stderr,
            "§S2/AC: Crucible's client reads the key from <project>/.env only; "
            f"the scaffold must put it there. client stderr={run.stderr[-400:]!r}",
        )
        self.assertEqual(run.returncode, 0, f"stdout={run.stdout[-400:]!r} stderr={run.stderr[-400:]!r}")
        self.assertIn(f"/api/v2/projects/{self.FILLED_KEY}/plans", _StubCrucible.seen,
                      "the client addressed the filled project key")


# ------------------------------------------------------------------ extensibility ----

class FixtureSchemaExtensibilityTest(unittest.TestCase):
    """§S2/AC — adding an entry to a fixture schema alone makes `init` require
    or derive, validate and render it (the generator fed the fixture through
    ``scaffold.PROJECT_SCHEMA_PATH``; run in process, since a fixture's ask
    flag has no parser flag and the args carry its dest directly)."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="r43-fixture-"))
        self.env = _sandbox_env(self.root)
        self.home = Path(self.env["MODELB_HOME"])
        write_install_toml(str(self.home), harnesses=("pi",))
        self.assertTrue(SCHEMA_PATH.is_file(), f"§S1: schema absent at {SCHEMA_PATH}")
        self.assertTrue(hasattr(scaffold, "PROJECT_SCHEMA_PATH"),
                        "§S2 seam: scaffold.PROJECT_SCHEMA_PATH")
        self.table, _ = _schema_table()
        sandesh = _entries_by_name()["SANDESH_PROJECT"]
        self.derive_rule, self.no_space = sandesh["rule"], sandesh["validate"]

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _fixture(self, *, rule=None, validate=None) -> Path:
        extra = (
            f"\n[[{self.table}]]\n"
            'name = "TEAM_LEAD"\n'
            'description = "fixture: an asked key"\n'
            "required = true\n"
            'file = ".env"\n'
            'scope = "root"\n'
            'source = "ask"\n'
            'flag = "--team-lead"\n'
            f'validate = "{validate or self.no_space}"\n'
            'readers = ["fixture"]\n'
            f"\n[[{self.table}]]\n"
            'name = "TEAM_CHANNEL"\n'
            'description = "fixture: a derived key"\n'
            "required = true\n"
            'file = ".env"\n'
            'scope = "root+sub"\n'
            'source = "derive"\n'
            f'rule = "{rule or self.derive_rule}"\n'
            'inputs = ["PROJECT_NAME"]\n'
            f'validate = "{self.no_space}"\n'
            'readers = ["fixture"]\n'
        )
        path = self.root / "fixture-schema.toml"
        path.write_text(SCHEMA_PATH.read_text(encoding="utf-8") + extra, encoding="utf-8")
        return path

    def _run(self, schema: Path, target: Path, **overrides):
        fields = {"repo_shape": "monorepo:a", "team_lead": "Ada", **overrides}
        return _run_init_in_process(self.env, self.home, target, schema, **fields)

    def test_a_fixture_ask_key_is_required(self):
        target = self.root / "missing"
        rc, axi, err = self._run(self._fixture(), target, team_lead=None)
        self.assertEqual(rc, 2, f"stderr={err[-600:]!r}")
        self.assertIs(axi.get("ok"), False)
        warnings = " ".join(axi.get("warnings", []))
        self.assertIn("missing required value(s)", warnings)
        self.assertIn("--team-lead", warnings, "§S2: the required check names the ask flag")
        self.assertFalse(target.exists(), "refused before anything is written")

    def test_a_fixture_ask_key_is_validated_before_any_write(self):
        target = self.root / "invalid"
        rc, axi, err = self._run(self._fixture(), target, team_lead="Ada Lovelace")
        self.assertEqual(rc, 2, f"stderr={err[-600:]!r}")
        self.assertIs(axi.get("ok"), False)
        warnings = " ".join(axi.get("warnings", []))
        self.assertTrue("TEAM_LEAD" in warnings or "--team-lead" in warnings, warnings)
        self.assertFalse(target.exists(), "refused before anything is written")

    def test_fixture_keys_are_asked_derived_and_rendered_per_scope(self):
        target = self.root / "proj"
        rc, axi, err = self._run(self._fixture(), target)
        self.assertEqual(rc, 0, f"stderr={err[-800:]!r}")
        root_env = parse_env_file(target / ".env")
        self.assertEqual((root_env.get("TEAM_LEAD"), root_env.get("TEAM_CHANNEL")),
                         ("Ada", DERIVED_SANDESH), f"root .env={root_env!r}")
        sub_env = parse_env_file(target / "a" / ".env")
        self.assertEqual(sub_env.get("TEAM_CHANNEL"), DERIVED_SANDESH, f"a/.env={sub_env!r}")
        self.assertNotIn("TEAM_LEAD", sub_env, "a root-scoped key stays out of a sub-project")

    def test_without_the_fixture_entries_nothing_extra_is_rendered(self):
        """Control: the same args against the real schema render no fixture key."""
        target = self.root / "control"
        rc, _axi, err = self._run(SCHEMA_PATH, target)
        self.assertEqual(rc, 0, f"stderr={err[-800:]!r}")
        text = (target / ".env").read_text(encoding="utf-8")
        self.assertEqual((_key_lines(text, "TEAM_LEAD"), _key_lines(text, "TEAM_CHANNEL")),
                         ([], []))
        self.assertEqual(_key_lines(text, "SANDESH_PROJECT"), [f"SANDESH_PROJECT={DERIVED_SANDESH}\n"])

    def test_an_unknown_rule_name_is_a_load_time_error(self):
        self.assertIsInstance(_scaffold_seam("load_schema")(SCHEMA_PATH), object)
        for kwargs, bad in (({"rule": "no_such_rule_r43"}, "no_such_rule_r43"),
                            ({"validate": "no_such_check_r43"}, "no_such_check_r43")):
            with self.subTest(bad=bad):
                with self.assertRaises(scaffold.ScaffoldError) as ctx:
                    _scaffold_seam("load_schema")(self._fixture(**kwargs))
                self.assertIn(bad, str(ctx.exception))
                target = self.root / f"unknown-{bad}"
                rc, axi, _err = self._run(self._fixture(**kwargs), target)
                self.assertEqual((rc, axi.get("ok")), (2, False))
                self.assertFalse(target.exists(), "refused before anything is written")


# ------------------------------------------------------------------ strict schema load ----

#: A well-formed fixture ask entry; each malformed case below edits one field.
_GOOD_ASK = {
    "name": '"TEAM_LEAD"', "description": '"fixture: an asked key"', "required": "true",
    "file": '".env"', "scope": '"root"', "source": '"ask"', "flag": '"--team-lead"',
    "validate": '"non_empty"', "readers": '["fixture"]',
}


def _table(table: str, fields: dict) -> str:
    return f"\n[[{table}]]\n" + "".join(f"{k} = {v}\n" for k, v in fields.items())


class StrictSchemaLoadTest(unittest.TestCase):
    """§S2 "Loading and validating the schema" (C4 FIX F5/F6) —
    ``load_schema`` itself refuses each malformed entry, naming the key and
    the field, before ``init`` does anything."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="r43-strict-"))
        self.table, _ = _schema_table()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _refused(self, fields: dict, key: str, *words: str) -> None:
        path = _schema_with(self.root, _table(self.table, fields))
        with self.assertRaises(scaffold.ScaffoldError) as ctx:
            scaffold.load_schema(path)
        message = str(ctx.exception)
        for word in (key, *words):
            self.assertIn(word, message, f"the refusal names {word!r}; got {message!r}")

    def test_the_packaged_schema_loads(self):
        self.assertEqual({e["name"] for e in scaffold.load_schema(SCHEMA_PATH)}, SCHEMA_KEYS)

    def test_an_entry_without_a_description_is_refused(self):
        fields = dict(_GOOD_ASK)
        del fields["description"]
        self._refused(fields, "TEAM_LEAD", "description")

    def test_an_entry_without_readers_is_refused(self):
        fields = dict(_GOOD_ASK)
        del fields["readers"]
        self._refused(fields, "TEAM_LEAD", "readers")

    def test_readers_that_are_not_a_list_of_strings_are_refused(self):
        self._refused({**_GOOD_ASK, "readers": '"fixture"'}, "TEAM_LEAD", "readers")

    def test_a_capture_entry_without_a_step_is_refused(self):
        fields = {k: v for k, v in _GOOD_ASK.items() if k != "flag"}
        self._refused({**fields, "source": '"capture"'}, "TEAM_LEAD", "step")

    def test_an_override_not_starting_with_dashes_is_refused(self):
        fields = {k: v for k, v in _GOOD_ASK.items() if k != "flag"}
        fields.update(source='"derive"', rule='"remove_whitespace"',
                      inputs='["PROJECT_NAME"]', override='"team-lead"')
        self._refused(fields, "TEAM_LEAD", "override")

    def test_a_non_boolean_required_is_refused(self):
        self._refused({**_GOOD_ASK, "required": '"yes"'}, "TEAM_LEAD", "required")

    def test_a_derive_input_neither_a_key_nor_an_init_input_is_refused_at_load_time(self):
        fields = {k: v for k, v in _GOOD_ASK.items() if k != "flag"}
        fields.update(source='"derive"', rule='"remove_whitespace"',
                      inputs='["no_such_input_r43"]')
        self._refused(fields, "TEAM_LEAD", "inputs", "no_such_input_r43")

    def test_an_env_local_key_scoped_to_sub_projects_is_refused(self):
        self._refused({**_GOOD_ASK, "file": '".env.local"', "scope": '"root+sub"'},
                      "TEAM_LEAD", ".env.local", "root+sub")


class RootEnvLocalKeyTest(unittest.TestCase):
    """§S2 (C4 FIX F6) — a root-scoped `.env.local` key renders into
    `.env.local` (not `.env`) and is read back by ``read_registry_value``."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="r43-local-"))
        self.env = _sandbox_env(self.root)
        self.home = Path(self.env["MODELB_HOME"])
        write_install_toml(str(self.home), harnesses=("pi",))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_a_root_env_local_key_renders_there_and_reads_back(self):
        table, _ = _schema_table()
        schema = _schema_with(self.root, _table(table, {
            **_GOOD_ASK, "name": '"LOCAL_NOTE"', "flag": '"--local-note"',
            "file": '".env.local"'}))
        target = self.root / "proj"
        rc, _axi, err = _run_init_in_process(self.env, self.home, target, schema,
                                             local_note="hello")
        self.assertEqual(rc, 0, f"stderr={err[-800:]!r}")
        self.assertEqual(parse_env_file(target / ".env.local").get("LOCAL_NOTE"), "hello")
        self.assertNotIn("LOCAL_NOTE", parse_env_file(target / ".env"))
        self.assertEqual(
            scaffold.read_registry_value(target, scaffold.load_schema(schema), "LOCAL_NOTE"),
            "hello")


# ------------------------------------------------------------------ C4 FIX F10 ----

class EmitPlanTakesTheResolvedRegistryTest(unittest.TestCase):
    """C4 FIX F10 — ``_emit_plan`` has no schema fallback of its own: its
    one production caller, ``run_init``, always passes the schema and the
    registry it resolved in validation."""

    def test_schema_and_registry_are_required_keywords(self):
        params = inspect.signature(scaffold._emit_plan).parameters
        for name in ("schema", "registry"):
            with self.subTest(param=name):
                self.assertIs(params[name].default, inspect.Parameter.empty,
                              f"_emit_plan({name}=...) has a dead default")


class SchemaReadersAndSkillKeyListTest(unittest.TestCase):
    """C4 FIX F10 — SANDESH_PROJECT's readers name only real readers today
    (a reader still to come is marked pending), and the model-b skill's
    §4.1 key list names every schema key."""

    def test_sandesh_project_readers_are_real_or_marked_pending(self):
        readers = _entries_by_name()["SANDESH_PROJECT"]["readers"]
        self.assertTrue(any(r.startswith("modelb-axi init") for r in readers), readers)
        for reader in readers:
            with self.subTest(reader=reader):
                self.assertTrue(
                    reader.startswith("modelb-axi init") or "pending" in reader,
                    f"a reader that does not read the key today is marked pending: {reader!r}")

    def test_the_model_b_skill_key_list_names_every_schema_key(self):
        text = (REPO_ROOT / "skills-src" / "model-b" / "SKILL.md").read_text(encoding="utf-8")
        section = text.split("## 4. ", 1)[1].split("\n## ", 1)[0]
        item = next(line for line in section.splitlines()
                    if line.startswith("1. **Naming registry"))
        self.assertEqual(sorted(k for k in SCHEMA_KEYS if f"`{k}`" not in item), [],
                         "§4.1 names every key the schema declares")


# ------------------------------------------------------------------ run_agents ----

class AgentsVerbReadsScaffoldedStacksTest(unittest.TestCase):
    """§S2 regression pin — `modelb-axi agents` still reads PROJECT_STACKS from
    a scaffolded `.env` (now carrying the schema's new keys), and `--stacks`
    rewrites that one line only."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="r43-agents-"))
        cls.target = cls.root / "proj"
        cls.result = _init(cls.root, cls.target)
        cls.home = cls.root / "mbhome"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def _agents(self, stacks):
        out, err = io.StringIO(), io.StringIO()
        args = argparse.Namespace(stacks=stacks, force_managed=False)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = scaffold.run_agents(args, self.home, project_root=self.target)
        return rc, decode_axi(out.getvalue()), err.getvalue()

    def test_agents_renders_from_the_recorded_project_stacks_then_rewrites_only_that_line(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr[-800:])
        rc, axi, err = self._agents(None)
        self.assertEqual((rc, axi.get("stacks")), (0, [STACKS]), f"stderr={err[-600:]!r}")
        before = (self.target / ".env").read_text(encoding="utf-8")
        rc, axi, err = self._agents("bun")
        self.assertEqual((rc, axi.get("stacks")), (0, ["bun"]), f"stderr={err[-600:]!r}")
        after = (self.target / ".env").read_text(encoding="utf-8")
        self.assertEqual(_key_lines(after, "PROJECT_STACKS"), ["PROJECT_STACKS=bun\n"])
        self.assertEqual(_without_keys(after, "PROJECT_STACKS"),
                         _without_keys(before, "PROJECT_STACKS"))


# ------------------------------------------------ §S3 gates: shipped text ----
#
# The gates read the SHIPPED trees only — `skills-src/`, `generator/templates/`,
# `hooks-src/` (and, for the no-project-value gate, the schema itself). The
# records (`docs/`, `archive/`, `audits/`) and tests are not shipped and are out
# of scope. Crucible's imported bundles are exempt from both gates: their keys
# and examples are Crucible's contract (skills-src/CRUCIBLE-HANDOVER.md).

GATE_ROOTS = ("skills-src", "generator/templates", "hooks-src")
HANDOVER_MD = REPO_ROOT / "skills-src" / "CRUCIBLE-HANDOVER.md"

#: A registry key's shape.
_KEY_SHAPE = r"[A-Z][A-Z0-9_]+"
#: (a) ``KEY=`` — never ``KEY==`` (a comparison) and never inside a longer
#: identifier or a ``$KEY`` reference.
_ASSIGNED_NAME_RE = re.compile(r"(?<![A-Za-z0-9_$])(" + _KEY_SHAPE + r")=(?!=)")
#: (b) an env-style name (it carries an underscore) on a line that also
#: mentions a ``.env`` file or "registry". The underscore keeps ordinary
#: upper-case prose words (NEVER, ONCE, CR, NNN) out.
_ENV_STYLE_NAME_RE = re.compile(
    r"(?<![A-Za-z0-9_])([A-Z][A-Z0-9]*_[A-Z0-9_]*[A-Z0-9])(?![A-Za-z0-9_])")
#: A line about project settings: a ``.env`` / ``.env.local`` file (never
#: ``os.environ``), the registry, or "project settings" (C4 FIX F3).
_REGISTRY_LINE_RE = re.compile(r"\.env\b|registry|project settings", re.IGNORECASE)
#: (c) a ``$KEY`` / ``${KEY}`` reference — anywhere (C4 FIX F3).
_DOLLAR_NAME_RE = re.compile(r"\$\{?(" + _KEY_SHAPE + r")(?![A-Za-z0-9_])")
#: (d) a read through ``environ[...]`` / ``environ.get(...)`` / ``getenv(...)``.
_ENVIRON_NAME_RE = re.compile(
    r"(?:\benviron\s*\[|\benviron\.get\(|\bgetenv\()\s*[\"'](" + _KEY_SHAPE + r")[\"']")
#: (e) an inline-code span that IS a key-shaped name (``OWNER`` included, no
#: underscore needed), on a line about project settings.
_CODE_NAME_RE = re.compile(r"^(" + _KEY_SHAPE + r")$")
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
#: Files whose prose is Markdown: only their fenced blocks and inline code
#: spans are "code". Any other file (the extension-less hook scripts) is code.
_MARKDOWN_SUFFIXES = (".md", ".tmpl")

#: Names that match the registry-key shape in the shipped trees but are NOT
#: project-registry keys — runtime environment, tool configuration or example
#: text. Every entry is matched in today's tree (a stale entry would hide a
#: future registry key of the same name).
NOT_REGISTRY_KEYS = {
    # hook escape hatches — per-command environment, read by the hook scripts
    "ALLOW_RAW_CARGO": "block-direct-cargo-test escape hatch (per-command env)",
    "ALLOW_RAW_MVN": "block-direct-mvn-test escape hatch (per-command env)",
    "ALLOW_WRITE_OUTSIDE_WORKTREE": "block-write-outside-worktree escape hatch (env)",
    # Crucible client configuration — optional `.env` keys Crucible's clients own
    "CRUCIBLE_MAVEN_DIR": "Crucible mvn client config (non-root pom), Crucible's contract",
    "CRUCIBLE_COMPOSE_FILE": "Crucible mvn client config (compose e2e), Crucible's contract",
    "CRUCIBLE_DOCKER_SERVICES": "Crucible mvn client config (compose e2e), Crucible's contract",
    "CRUCIBLE_BIND_MOUNT_PATHS": "Crucible mvn client config (bind mounts), Crucible's contract",
    "CRUCIBLE_COVERAGE_PROFILE": "Crucible mvn client config (JaCoCo profile), Crucible's contract",
    "MVN_CRUCIBLE_PROJECT_DIR": "Crucible mvn client --project-dir env override",
    "RUST_CRUCIBLE_PROJECT_DIR": "Crucible rust client --project-dir env override",
    # third-party tool environment
    "CARGO_BUILD_JOBS": "cargo's parallelism env var (rust memory template)",
    "DOCKER_HOST": "Docker/Podman socket env var (java testing template)",
    "TESTCONTAINERS_RYUK_DISABLED": "Testcontainers env var (java testing template)",
    "MAVEN_OPTS": "Maven JVM options env var (java maven template)",
    "UID": "shell user id in a compose `user:` example (rust template)",
    "GID": "shell group id in a compose `user:` example (rust template)",
    # example / placeholder text
    "COMMIT": "enum-variant example in cr-authoring's AC-precision guidance",
    "ROLLBACK": "enum-variant example in cr-authoring's AC-precision guidance",
    "DD": "RediSearch FT.DROPINDEX argument (java orchestration template)",
    "SOME_ENV_VAR": "placeholder in a `docker run -e` example (operational commands)",
    "VAR": "generic `VAR=value` wording in the block-direct-*-test hook docstrings",
    # runtime names the widened detector (C4 FIX F3: `$KEY`, `${KEY}`,
    # environ reads) matches — none is a project-registry key
    "ARGUMENTS": "the harness's skill-argument substitution (`$ARGUMENTS`, bootstrap skill)",
    "USER": "the shell login name in `loginctl enable-linger $USER` (java testing template)",
    "TMPDIR": "the POSIX temp-dir env var (block-write-outside-worktree scratch rule)",
    "WF_TRACK": "worktree-flow.py's per-session track-label env var (rust orchestration template)",
    "WF_WORKTREE_ROOT": "the dispatch worktree root exported to block-write-outside-worktree",
    "MODELB_HOME": "the Model B installation home (installer env), read by ambient-board-status",
    "MODELB_STATUS_CMD": "ambient-board-status's feed-command override (env)",
}

#: Real projects, derived from this repo's own records (docs/, audits/,
#: archive/, AGENTS.md; proved by RealProjectSetIsDerivedFromTheRecordsTest):
#: Sandesh ids from `Mainline - ModelB`, `Mainline - Crucible`, `Mainline - Nai`,
#: `Mainline - Sandesh`, `Track N - Nai`; `Roundhouse` the umbrella; `Valmik`
#: (CR-MDB-041/042); `Switchyard` the Roundhouse routing layer (C4 FIX F4).
REAL_SANDESH_PROJECTS = ("ModelB", "Roundhouse", "Crucible", "Nai", "Sandesh", "Valmik",
                         "Switchyard")
#: Their tokens — the lower-case short names (`PROJECT_TOKEN=modelb`).
REAL_PROJECT_TOKENS = tuple(name.lower() for name in REAL_SANDESH_PROJECTS)
#: Real acronyms, each recorded as a `CR-<ACRONYM>-NNN` id. `MB` (Model B's
#: retired acronym) is left out: as a bare word it is a unit ("2 MB"). `CF` and
#: `SH` occur only as example CR ids in shipped skills, never in the records.
REAL_PROJECT_ACRONYMS = ("MDB", "MODELB", "RND", "CRU", "NAI", "SAN", "SHE", "SY", "OA")
#: Real remote owners (`REPO_OWNER=antojk` in AGENTS.md; the work account the
#: git-workflow skill named).
REAL_REPO_OWNERS = ("antojk", "Antojk71")


def _alt(words) -> str:
    return "|".join(map(re.escape, sorted(set(words), key=len, reverse=True)))


_REAL = _alt(REAL_SANDESH_PROJECTS)
_SANDESH_ADDRESS_RE = re.compile(
    r"\b(?:Mainline|Track\s+\S+)\s+-\s+(" + _REAL + r")(?![A-Za-z0-9_])")
_SANDESH_PROJECT_FLAG_RE = re.compile(
    r"--project(?:\s+|=)[\"']?(" + _REAL + r")(?![A-Za-z0-9_])")
#: A real name, token or owner in prose as a project's identity: right after
#: `token`, `acronym`, `project name`, `named`, `owner` or `account`, or after
#: `project` when set off as code, bold or a quote (`project `ModelB``, never
#: "the project Sandesh note" nor the `--project` flag, matched above).
_REAL_IDENTITY = _alt(REAL_SANDESH_PROJECTS + REAL_PROJECT_TOKENS + REAL_REPO_OWNERS)
_IDENTITY_PROSE_RE = re.compile(
    r"(?<![-\w])(?:(?:token|acronym|project\s+name|named|owner|account)\b[\s:=*`\"']*"
    r"|project\s*[:=]?\s*[`*\"']+)(" + _REAL_IDENTITY + r")(?![A-Za-z0-9_-])")
#: An orchestrator label of a real project: `vidushi-mdb`, `Mainline-modelb`.
_REAL_LABEL_RE = re.compile(
    r"\b(?:vidushi|Mainline)-("
    + _alt(REAL_PROJECT_TOKENS + REAL_SANDESH_PROJECTS
           + tuple(a.lower() for a in REAL_PROJECT_ACRONYMS))
    + r")(?![A-Za-z0-9_-])")
#: A real acronym as a word — never inside a CR id (`CR-MDB-043`, `CR-RND`),
#: which is a provenance citation, not a project value.
_REAL_ACRONYM_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?<!CR-)(" + _alt(REAL_PROJECT_ACRONYMS) + r")(?![A-Za-z0-9_])")
#: A real remote owner as a word (`github.com-antojk` included).
_REAL_OWNER_RE = re.compile(
    r"(?<![A-Za-z0-9_])(" + _alt(REAL_REPO_OWNERS) + r")(?![A-Za-z0-9_])")
_UUID_RE = re.compile(
    r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}"
    r"-[0-9A-Fa-f]{12}(?![0-9A-Fa-f])")
#: A schema field whose NAME says it carries a value.
VALUE_LIKE_FIELDS = frozenset({"value", "default", "example", "examples", "sample"})


def _imported_crucible_bundles() -> frozenset:
    """The imported roster, read from the provenance record's "Bundles imported"
    list — the single place it is declared."""
    text = HANDOVER_MD.read_text(encoding="utf-8")
    section = text.split("## Bundles imported", 1)[1].split("\n## ", 1)[0]
    return frozenset(re.findall(r"^- `(crucible-[a-z-]+)`\s*$", section, re.MULTILINE))


#: The no-project-value gate's provenance exemption: the SAME file the sibling
#: grep gate exempts (test_crucible_skill.CrucibleSkillS5Test.GREP_GATE_EXEMPT,
#: also test_client_path_anchoring.PROVENANCE_EXEMPTION) — a record at the
#: skills-src root, not a bundle, never deployed, naming real Sandesh
#: addresses as history.
PROVENANCE_RECORDS = frozenset(
    f"skills-src/{name}"
    for name in _crucible_skill_gates.CrucibleSkillS5Test.GREP_GATE_EXEMPT
)


def _shipped_files(exempt: frozenset = frozenset()) -> list[tuple[str, str]]:
    """``(repo-relative path, text)`` of every shipped file under GATE_ROOTS,
    minus Crucible's imported bundles, ``__pycache__`` and ``exempt``."""
    bundles = _imported_crucible_bundles()
    out = []
    for root in GATE_ROOTS:
        for path in sorted((REPO_ROOT / root).rglob("*")):
            rel = path.relative_to(REPO_ROOT)
            if not path.is_file() or "__pycache__" in rel.parts:
                continue
            if rel.parts[0] == "skills-src" and len(rel.parts) > 2 and rel.parts[1] in bundles:
                continue
            if rel.as_posix() in exempt:
                continue
            out.append((rel.as_posix(), path.read_text(encoding="utf-8")))
    return out


def _registry_names_named(path: str, text: str) -> list[tuple[int, str]]:
    """``(line, name)`` for every registry key ``text`` NAMES: a name of the
    key shape that appears (a) as ``KEY=`` in code — a fenced block or inline
    code span in Markdown, anywhere in any other file; (b) env-style on a
    line about project settings; (c) as ``$KEY`` / ``${KEY}``; (d) read
    through ``environ[...]`` / ``environ.get(...)`` / ``getenv(...)``; or (e)
    as a whole inline-code span on a line about project settings (§S3,
    C4 FIX F3)."""
    markdown = path.endswith(_MARKDOWN_SUFFIXES)
    found, in_fence = [], False
    for number, line in enumerate(text.splitlines(), 1):
        if markdown and _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        spans = _INLINE_CODE_RE.findall(line)
        codes = [line] if (in_fence or not markdown) else spans
        names = {m.group(1) for code in codes for m in _ASSIGNED_NAME_RE.finditer(code)}
        names |= {m.group(1) for m in _DOLLAR_NAME_RE.finditer(line)}
        names |= {m.group(1) for m in _ENVIRON_NAME_RE.finditer(line)}
        if _REGISTRY_LINE_RE.search(line):
            names |= {m.group(1) for m in _ENV_STYLE_NAME_RE.finditer(line)}
            names |= {s.strip() for s in spans if _CODE_NAME_RE.match(s.strip())}
        found.extend((number, name) for name in sorted(names))
    return found


def _undeclared_registry_names(files, declared, allowlist) -> list[str]:
    """``path:line NAME`` for every named registry key neither declared in the
    schema nor allowlisted as a non-registry name."""
    return [
        f"{path}:{line} {name}"
        for path, text in files
        for line, name in _registry_names_named(path, text)
        if name not in declared and name not in allowlist
    ]


def _is_placeholder(value: str) -> bool:
    """Empty, quoted-empty, an ``<angle>`` placeholder, or a ``$reference``
    (a value read from elsewhere, not a literal)."""
    bare = value.strip("\"'")
    return (bare == "" or (bare.startswith("<") and bare.endswith(">"))
            or bare.startswith("$"))


def _project_value_findings(path: str, text: str, keys) -> list[str]:
    """``path:line: reason`` for every literal project value in ``text``: a
    schema key assigned a non-placeholder value (``KEY=value`` or YAML-style
    ``KEY: value``), a UUID-shaped project key, a real project's Sandesh
    address or ``--project`` id, a real name/token/owner given as a
    project's identity, a real orchestrator label, a real acronym (CR ids
    exempt) or a real remote owner (§S3, C4 FIX F4)."""
    alternation = "|".join(map(re.escape, sorted(keys)))
    assign = re.compile(
        r"(?<![A-Za-z0-9_$])(" + alternation
        + r")=(\"[^\"\n]*\"|'[^'\n]*'|[^\s`'\",;)]*)")
    yaml = re.compile(
        r"(?<![A-Za-z0-9_$`])(" + alternation
        + r"):[ \t]+(\"[^\"\n]*\"|'[^'\n]*'|[^\s`'\",;)]+)[ \t`]*$")
    out = []
    for number, line in enumerate(text.splitlines(), 1):
        for regex in (assign, yaml):
            for m in regex.finditer(line):
                if not _is_placeholder(m.group(2)):
                    out.append(f"{path}:{number}: {m.group(1)} assigned {m.group(2)!r}")
        out.extend(f"{path}:{number}: UUID {m.group(0)}" for m in _UUID_RE.finditer(line))
        for regex in (_SANDESH_ADDRESS_RE, _SANDESH_PROJECT_FLAG_RE):
            out.extend(f"{path}:{number}: Sandesh id {m.group(0)!r}"
                       for m in regex.finditer(line))
        for kind, regex in (("project identity", _IDENTITY_PROSE_RE),
                            ("orchestrator label", _REAL_LABEL_RE),
                            ("acronym", _REAL_ACRONYM_RE),
                            ("remote owner", _REAL_OWNER_RE)):
            out.extend(f"{path}:{number}: {kind} {m.group(0)!r}"
                       for m in regex.finditer(line))
    return out


def _schema_value_fields(entries: list[dict]) -> list[str]:
    """``KEY.field`` for every field outside §S1 or named like a value."""
    return [
        f"{entry.get('name')}.{field}"
        for entry in entries for field in sorted(entry)
        if field not in S1_FIELDS or field in VALUE_LIKE_FIELDS
    ]


class RegistryKeyDetectorTest(unittest.TestCase):
    """§S3 gate 1's detector: what counts as a registry key NAMED — proved on
    synthetic texts, so the gate can fail."""

    def _names(self, path: str, text: str) -> list[tuple[int, str]]:
        return _registry_names_named(path, text)

    def test_an_assignment_in_a_fenced_block_is_named(self):
        text = "Prose.\n```\nTEAM_LEAD=alice\n```\n"
        self.assertEqual(self._names("fixture.md", text), [(3, "TEAM_LEAD")])

    def test_an_assignment_in_inline_code_is_named(self):
        self.assertEqual(self._names("fixture.md", "Write `TEAM_LEAD=` first.\n"),
                         [(1, "TEAM_LEAD")])

    def test_an_env_style_name_on_a_dotenv_or_registry_line_is_named(self):
        text = ("Set TEAM_LEAD in `.env`.\n"
                "The naming registry holds BUDGET_CODE too.\n"
                "Local overlay `.env.local` carries SECRET_TOKEN.\n")
        self.assertEqual(self._names("fixture.md", text),
                         [(1, "TEAM_LEAD"), (2, "BUDGET_CODE"), (3, "SECRET_TOKEN")])

    def test_an_extensionless_script_is_code_throughout(self):
        text = '"""Docstring: set TEAM_LEAD=1 to skip."""\n'
        self.assertEqual(self._names("hooks-src/scripts/x", text), [(1, "TEAM_LEAD")])

    def test_runtime_names_in_prose_and_comparisons_are_not_named(self):
        # MIGRATED PIN (C4 FIX F3, amended §S3): this test also pinned
        # `os.environ.get("TMPDIR_ROOT")` and `${HOME_DIR}` as NOT named; the
        # amended §S3 makes both forms names (see the tests below).
        clean = (
            "The WORKFLOW_CYCLE variable is exported by the harness.\n"
            "Outside code, FOO_BAR=1 in prose is not an assignment.\n"
            "NEVER read the ONCE-declared value.\n"
            "`WORKFLOW_CYCLE` is exported by the harness.\n"
        )
        self.assertEqual(self._names("fixture.md", clean), [])
        script = "if MODE_FLAG==1: pass\n"
        self.assertEqual(self._names("hooks-src/scripts/x", script), [])

    def test_an_inline_code_name_on_a_project_settings_line_is_named(self):
        self.assertEqual(
            self._names("fixture.md", "Read `TEAM_LEAD` from the project settings.\n"),
            [(1, "TEAM_LEAD")])
        self.assertEqual(self._names("fixture.md", "Set the `OWNER` key in `.env`.\n"),
                         [(1, "OWNER")], "a name without an underscore, as inline code")

    def test_a_dollar_reference_is_named_in_code_and_prose(self):
        text = ('```\nsandesh inbox --project "$TEAM_LEAD"\necho ${BUDGET_CODE}\n```\n'
                "Pass `$SECRET_TOKEN` through.\n")
        self.assertEqual(self._names("fixture.md", text),
                         [(2, "TEAM_LEAD"), (3, "BUDGET_CODE"), (5, "SECRET_TOKEN")])

    def test_an_environ_read_in_a_hook_script_is_named(self):
        script = ("a = os.environ.get('TEAM_LEAD')\n"
                  'b = os.environ["BUDGET_CODE"]\n'
                  "c = os.getenv('SECRET_TOKEN', '')\n"
                  'x = os.environ.get("TMPDIR_ROOT", "")\n'
                  "y = f'${HOME_DIR}'\n")
        self.assertEqual(self._names("hooks-src/scripts/x", script),
                         [(1, "TEAM_LEAD"), (2, "BUDGET_CODE"), (3, "SECRET_TOKEN"),
                          (4, "TMPDIR_ROOT"), (5, "HOME_DIR")])

    def test_a_name_inside_a_longer_identifier_is_not_the_shorter_key(self):
        self.assertEqual(self._names("fixture.md", "`MY_PROJECT_NAME=x`\n"),
                         [(1, "MY_PROJECT_NAME")])

    def test_the_gate_flags_an_undeclared_key_and_passes_declared_and_allowlisted(self):
        files = [("fixture.md", "```\nTEAM_LEAD=alice\nPROJECT_NAME=\n"
                                "ALLOW_RAW_CARGO=1\n```\n")]
        self.assertEqual(
            _undeclared_registry_names(files, SCHEMA_KEYS, NOT_REGISTRY_KEYS),
            ["fixture.md:2 TEAM_LEAD"])
        clean = [("fixture.md", "`PROJECT_NAME=` and `ALLOW_RAW_MVN=1`\n")]
        self.assertEqual(
            _undeclared_registry_names(clean, SCHEMA_KEYS, NOT_REGISTRY_KEYS), [])


class RegistryKeysDeclaredGateTest(unittest.TestCase):
    """§S3 gate 1: every registry key named in the shipped skills (Crucible's
    imported bundles exempt), templates and hooks is declared in the schema."""

    @classmethod
    def setUpClass(cls):
        cls.files = _shipped_files()
        cls.declared = frozenset(_entries_by_name())
        cls.named = {name for path, text in cls.files
                     for _, name in _registry_names_named(path, text)}

    def test_the_scan_reads_every_root_and_skips_the_imported_bundles(self):
        bundles = _imported_crucible_bundles()
        self.assertEqual(len(bundles), 6, f"imported roster parsed as {sorted(bundles)}")
        paths = [p for p, _ in self.files]
        for root in GATE_ROOTS:
            self.assertTrue(any(p.startswith(root + "/") for p in paths), root)
        self.assertEqual([p for p in paths if p.split("/")[1] in bundles], [])
        self.assertIn("PROJECT_NAME", self.named,
                      "the model-b skill's naming registry names PROJECT_NAME")

    def test_every_named_registry_key_is_declared_in_the_schema(self):
        self.assertEqual(
            _undeclared_registry_names(self.files, self.declared, NOT_REGISTRY_KEYS), [],
            "§S3: a registry key named in shipped text is not declared in "
            "modelb_axi/project_schema.toml (declare it, or allowlist a runtime name "
            "in NOT_REGISTRY_KEYS with its reason)",
        )

    def test_the_allowlist_holds_no_schema_key_and_no_stale_name(self):
        self.assertEqual(sorted(set(NOT_REGISTRY_KEYS) & self.declared), [])
        self.assertEqual(sorted(set(NOT_REGISTRY_KEYS) - self.named), [],
                         "allowlisted names no shipped text matches any more")
        for name, reason in NOT_REGISTRY_KEYS.items():
            self.assertRegex(name, r"^" + _KEY_SHAPE + r"$")
            self.assertTrue(reason.strip(), f"{name} carries no reason")


class ProjectValueDetectorTest(unittest.TestCase):
    """§S3 gate 2's detector — proved on synthetic texts, so the gate can fail."""

    def _find(self, text: str) -> list[str]:
        return _project_value_findings("fixture.md", text, SCHEMA_KEYS)

    def test_a_schema_key_assigned_a_literal_value_is_found(self):
        text = ('PROJECT_NAME=Acme\n'
                '`SANDESH_PROJECT="Acme Corp"`\n'
                "export PROJECT_ACRONYM='ACM'\n")
        self.assertEqual(self._find(text), [
            "fixture.md:1: PROJECT_NAME assigned 'Acme'",
            "fixture.md:2: SANDESH_PROJECT assigned '\"Acme Corp\"'",
            "fixture.md:3: PROJECT_ACRONYM assigned \"'ACM'\"",
        ])

    def test_placeholders_and_non_schema_keys_are_not_values(self):
        clean = ("PROJECT_ACRONYM=<acronym>\n"
                 "`PROJECT_NAME=<Project>`\n"
                 'CRUCIBLE_PROJECT_KEY=\n'
                 'REPO_OWNER=""\n'
                 "SANDESH_PROJECT=$PROJECT_NAME\n"
                 "CRUCIBLE_MAVEN_DIR=backend\n"
                 "MY_PROJECT_NAME=Acme\n")
        self.assertEqual(self._find(clean), [])

    def test_a_uuid_shaped_project_key_is_found(self):
        text = "key `019c9ff7-222f-7ae5-9121-2ae549e4d97A` here; not 019c9ff7-222f\n"
        self.assertEqual(self._find(text),
                         ["fixture.md:1: UUID 019c9ff7-222f-7ae5-9121-2ae549e4d97A"])

    def test_a_real_projects_sandesh_address_or_project_flag_is_found(self):
        text = ("Send to Mainline - ModelB.\n"
                "sandesh send --project Roundhouse --to x\n"
                "Track 2 - Nai reports.\n"
                "--project=Crucible\n")
        self.assertEqual(self._find(text), [
            "fixture.md:1: Sandesh id 'Mainline - ModelB'",
            "fixture.md:2: Sandesh id '--project Roundhouse'",
            "fixture.md:3: Sandesh id 'Track 2 - Nai'",
            "fixture.md:4: Sandesh id '--project=Crucible'",
        ])

    def test_placeholder_sandesh_addresses_are_not_values(self):
        clean = ("Send to `Mainline - <Project>` or `Track N - <Project>`.\n"
                 "sandesh inbox --project <Project>\n"
                 "sandesh inbox --project \"$SANDESH_PROJECT\"\n"
                 "Crucible's client and the Sandesh CLI are tools, not ids.\n")
        self.assertEqual(self._find(clean), [])

    def test_a_real_projects_name_token_or_acronym_in_prose_is_found(self):
        findings = self._find("Crucible: token `crucible` · acronym `CRU`.\n"
                              "Sandesh project `ModelB` routes it.\n"
                              "The MDB-owned bundles ship.\n")
        for expected in ("fixture.md:1: project identity 'token `crucible'",
                         "fixture.md:1: acronym 'CRU'",
                         "fixture.md:2: project identity 'project `ModelB'",
                         "fixture.md:3: acronym 'MDB'"):
            self.assertIn(expected, findings)

    def test_a_real_orchestrator_label_is_found(self):
        self.assertEqual(self._find("The orchestrator `vidushi-mdb` runs it.\n"),
                         ["fixture.md:1: orchestrator label 'vidushi-mdb'"])
        self.assertIn("fixture.md:1: orchestrator label 'Mainline-roundhouse'",
                      self._find("Label Mainline-roundhouse.\n"))

    def test_a_yaml_style_assignment_is_found(self):
        self.assertIn("fixture.md:1: PROJECT_ACRONYM assigned 'MDB'",
                      self._find("PROJECT_ACRONYM: MDB\n"))
        self.assertIn("fixture.md:1: REPO_OWNER assigned 'acme'",
                      self._find("  REPO_OWNER: acme\n"))

    def test_a_new_real_projects_sandesh_address_is_found(self):
        self.assertEqual(self._find("Track 3 - Switchyard reports.\n"),
                         ["fixture.md:1: Sandesh id 'Track 3 - Switchyard'"])

    def test_a_real_remote_owner_is_found(self):
        findings = self._find("gh auth switch --user antojk\n"
                              "host alias `github.com-antojk`\n")
        self.assertEqual(findings, ["fixture.md:1: remote owner 'antojk'",
                                    "fixture.md:2: remote owner 'antojk'"])

    def test_cr_ids_placeholders_and_tool_names_are_not_values(self):
        clean = ("Cited as CR-MDB-043 §S3 and `CR-RND-001`; a `CR-RND` item.\n"
                 "Agent CR-MDB-043-C4-FIX, CR-SAN-013-C1-RED.\n"
                 "Solo `vidushi-<token>`, multi `Mainline-<token>`.\n"
                 "PROJECT_ACRONYM: <acronym>\n"
                 "`PROJECT_NAME`: the project's display name\n"
                 "Load the crucible skill; Crucible's client and the Sandesh CLI.\n"
                 "Run `~/.crucible/clients/python-crucible.py`; skill name `crucible-register`.\n"
                 "The project in Crucible; 2 MB of RAM.\n"
                 "name: crucible\n"
                 "Each project Sandesh note names its id.\n")
        self.assertEqual(self._find(clean), [])

    def test_a_schema_entry_with_a_value_like_or_non_s1_field_is_found(self):
        entries = [
            {"name": "TEAM_LEAD", "description": "d", "default": "alice"},
            {"name": "BUDGET", "value": "42", "colour": "red"},
            {"name": "CLEAN", "description": "d", "validate": "non_empty"},
        ]
        self.assertEqual(_schema_value_fields(entries),
                         ["TEAM_LEAD.default", "BUDGET.colour", "BUDGET.value"])


class NoProjectValueShipsGateTest(unittest.TestCase):
    """§S3 gate 2: no shipped skill (Crucible's imported bundles exempt),
    template, hook or the schema carries a literal project value."""

    def test_the_real_project_set_is_derived_from_the_repos_own_records(self):
        """Every real name, acronym and owner the detector knows is recorded in
        this repo's own records (never read from `$HOME`); each token is the
        lower-cased recorded name."""
        records = [REPO_ROOT / "AGENTS.md"] + [
            path for root in ("docs", "audits", "archive")
            for path in sorted((REPO_ROOT / root).rglob("*.md"))]
        text = "\n".join(p.read_text(encoding="utf-8") for p in records if p.is_file())
        for name in REAL_SANDESH_PROJECTS + REAL_REPO_OWNERS:
            with self.subTest(value=name):
                self.assertRegex(text, r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])")
        for acronym in REAL_PROJECT_ACRONYMS:
            with self.subTest(acronym=acronym):
                self.assertIn(f"CR-{acronym}-", text)
        self.assertEqual(REAL_PROJECT_TOKENS,
                         tuple(n.lower() for n in REAL_SANDESH_PROJECTS))

    def test_the_provenance_exemption_is_exactly_the_handover_record(self):
        self.assertEqual(PROVENANCE_RECORDS, {"skills-src/CRUCIBLE-HANDOVER.md"})
        self.assertTrue(HANDOVER_MD.is_file())
        self.assertFalse((HANDOVER_MD.parent / "SKILL.md").exists(),
                         "the exempt record must sit outside any bundle")

    def test_no_shipped_text_carries_a_project_value(self):
        files = _shipped_files(exempt=PROVENANCE_RECORDS)
        files.append((SCHEMA_WHEEL_MEMBER, SCHEMA_PATH.read_text(encoding="utf-8")))
        findings = [f for path, text in files
                    for f in _project_value_findings(path, text, SCHEMA_KEYS)]
        self.assertEqual(findings, [], "§S3: shipped text carries a project value")

    def test_the_schema_has_no_value_like_field(self):
        self.assertEqual(_schema_value_fields(_schema_table()[1]), [],
                         "§S3: the schema carries rules only, never a value")


# ------------------------------------ the Crucible key is never in .env.local ----

#: A reference to the Crucible project key: a schema key name, or the phrase.
_KEY_REFERENCE_RE = re.compile(
    r"\b(?:" + "|".join(sorted(SCHEMA_KEYS)) + r")\b|project[ _-]?key|projectkey",
    re.IGNORECASE)
_ENV_LOCAL_RE = re.compile(r"\.env\.local\b")
#: A sentence that names `.env.local` only to say the key is NOT there.
_NEGATION_RE = re.compile(
    r"\b(?:never|not|no longer|moved out of|instead of|rather than)\b", re.IGNORECASE)
_SENTENCE_END_RE = re.compile(r"(?<=[.;!?])\s+")


def _key_in_env_local_findings(path: str, text: str) -> list[str]:
    """``path:line`` for every sentence that places a registry key (or "the
    project key") in ``.env.local``: one sentence naming both, with no
    negation. Sentences are read per paragraph, so a wrapped line still
    counts; the line reported is the sentence's first."""
    out = []
    bounds = [0, *(m.end() for m in re.finditer(r"\n[ \t]*\n", text)), len(text)]
    for p_start, p_end in zip(bounds, bounds[1:], strict=False):
        paragraph = text[p_start:p_end]
        start = 0
        for match in [*_SENTENCE_END_RE.finditer(paragraph), None]:
            end = match.start() if match else len(paragraph)
            sentence = paragraph[start:end]
            if (_ENV_LOCAL_RE.search(sentence) and _KEY_REFERENCE_RE.search(sentence)
                    and not _NEGATION_RE.search(sentence)):
                line = text.count("\n", 0, p_start + start) + 1
                out.append(f"{path}:{line}")
            start = match.end() if match else end
    return out


class KeyInEnvLocalDetectorTest(unittest.TestCase):
    """The detector for shipped text placing the Crucible key in `.env.local`,
    proved on synthetic texts in both directions."""

    def test_a_sentence_placing_the_key_in_env_local_is_found(self):
        text = ("Intro line.\n\n"
                "Tool config like `CRUCIBLE_PROJECT_KEY` (which lives in the gitignored\n"
                "`.env.local` overlay). Next sentence.\n\n"
                "Paste the project key into `.env.local` after registering.\n")
        self.assertEqual(_key_in_env_local_findings("f.md", text), ["f.md:3", "f.md:6"])

    def test_negated_or_unrelated_env_local_mentions_are_not_found(self):
        clean = ("`CRUCIBLE_PROJECT_KEY` lives in `.env`, never `.env.local`.\n"
                 "The key moved out of `.env.local` into `.env`.\n"
                 "`.env.local` is the gitignored overlay for local-only values.\n"
                 "Put `CRUCIBLE_PROJECT_KEY` in `.env`. `.env.local` is gitignored.\n")
        self.assertEqual(_key_in_env_local_findings("f.md", clean), [])


class NoShippedTextPutsTheKeyInEnvLocalTest(unittest.TestCase):
    """§S1/§S2 defect: Model B-owned shipped text (Crucible's imported bundles
    and the provenance record exempt) never says the Crucible project key
    lives in, or is filled in, `.env.local` — it lives in `.env`."""

    def test_no_shipped_text_places_the_key_in_env_local(self):
        files = _shipped_files(exempt=PROVENANCE_RECORDS)
        self.assertTrue(any(p == "skills-src/model-b/SKILL.md" for p, _ in files))
        findings = [f for path, text in files for f in _key_in_env_local_findings(path, text)]
        self.assertEqual(
            findings, [],
            "§S2: CRUCIBLE_PROJECT_KEY is in `.env` (Crucible's client reads only "
            "`<project-dir>/.env`); shipped text still places it in `.env.local`",
        )


if __name__ == "__main__":
    unittest.main()
