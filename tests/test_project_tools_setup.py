"""A project is set up for the workflow's tools the installation recorded
(CR-MDB-045 §S4, §S5, §S8; PRD D10, amended 2026-09-27, and D5).

- §S4 — lean-ctx's project setup. The schema key ``KNOWLEDGE_CATEGORY``
  (``.env``, scope ``root+sub``, ``when = "lean-ctx"``, derived as
  ``<PROJECT_TOKEN>-workflow``, overridable by ``--knowledge-category``,
  validated as a kebab-case id) and, when lean-ctx is present, a lean-ctx
  section in the scaffolded ``AGENTS.md`` naming the category — a monorepo
  sub-project's ``AGENTS.md`` names its own. With lean-ctx absent or unknown
  neither the key nor the section is written.
- §S5 — the ``AGENTS.md`` capability contract lists each of the project's
  tools with its state (``present`` / ``absent`` / ``unknown``) and the
  remediation where it is not present; the queue README's Sandesh and
  Crucible setup tasks name the tool's remediation first when it is absent.
- §S8 — the project's agents match its tools. With lean-ctx present the
  agents ``init`` and ``modelb-axi agents`` render are byte-identical to
  today's (the committed ``generator/agents/`` set, which stays unchanged).
  With lean-ctx absent or unknown — per the orchestrator's ruling of
  2026-09-27, which the spec is amended to match — every ``ctx_*`` tool is
  replaced by Pi's built-in equivalent (the allowlist is today's non-ctx
  tools, in order, plus ``bash``), and the whole rendered definition names
  no ``ctx_*`` tool and no lean-ctx instruction.

How the contract is read (§S5): each tool is a bullet whose FIRST code span
is its id (a toolchain probe: its probe name), as the contract writes it
today; a line carries exactly one state word.

Isolation (NON-NEGOTIABLE): every ``install.toml``, Pi agent dir and home is
a fixture under a per-test temp dir (the sandbox of
``tests.test_init_tool_verdicts``); a subprocess runs with ``HOME``,
``MODELB_HOME``, ``XDG_DATA_HOME`` and ``PI_CODING_AGENT_DIR`` all pinned
there. No test reads the real ``~/.local/share/modelb``, ``~/.pi`` or
``~/.crucible``.

Stdlib only.
"""

import argparse
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from modelb_axi import agents, scaffold
from modelb_axi.requirements import REQUIREMENTS, STACK_TOOLCHAINS
from tests import test_init_tool_verdicts as _verdicts
from tests._helpers import decode_axi, parse_env_file, run_module
from tests.pi_capability_sandbox import AGENT_DIR_ENV

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "modelb_axi" / "project_schema.toml"
GENERATOR_DIR = REPO_ROOT / "generator"
COMMITTED_AGENTS_DIR = GENERATOR_DIR / "agents"
STACKS_DIR = GENERATOR_DIR / "stacks"
PI_AGENTS_RELDIR = Path(".pi") / "agents"

KEY = "KNOWLEDGE_CATEGORY"
OVERRIDE_FLAG = "--knowledge-category"
TOKEN = _verdicts.TOKEN
DERIVED_CATEGORY = f"{TOKEN}-workflow"
SANDESH_ID = _verdicts.DERIVED_CHANNEL
STACK = _verdicts.STACK
PRESENT, ABSENT, UNKNOWN = _verdicts.PRESENT, _verdicts.ABSENT, _verdicts.UNKNOWN

#: Every stack with agent definitions, for the per stack x role sweeps.
AGENT_STACKS = agents.STACKS
ROLES = agents.ROLES

#: Pi's built-in tools: what an agent rendered without lean-ctx may name.
PI_BUILTIN_SHELL = "bash"

_STATE_RE = re.compile(r"\b(present|absent|unknown)\b")
_FIRST_CODE_SPAN_RE = re.compile(r"`([^`]+)`")
_HEADING_RE = re.compile(r"^(#{2,3}) (.*)$")


# ------------------------------------------------------------------ helpers ----

def _row(requirement_id: str) -> dict:
    return next(r for r in REQUIREMENTS if r["id"] == requirement_id)


def _always_ids() -> list[str]:
    """Every tier-1 and tier-2 row the project always carries."""
    return [r["id"] for r in REQUIREMENTS if r["scope"] == "always"]


def _sections(text: str) -> list[tuple[str, str]]:
    """``(heading, body)`` of every level-2/3 markdown heading in ``text``;
    a body runs to the next heading of any level."""
    out: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            out.append((match.group(2), []))
        elif line.startswith("#"):
            out.append(("", []))
        elif out:
            out[-1][1].append(line)
    return [(h, "\n".join(body)) for h, body in out if h]


def _contract(text: str) -> str:
    found = [body for heading, body in _sections(text)
             if "capability contract" in heading.lower()]
    if len(found) != 1:
        raise AssertionError(f"exactly one capability-contract section expected; "
                             f"found {len(found)} in {text!r}")
    return found[0]


def _lean_ctx_sections(text: str) -> list[str]:
    """The body of each heading naming lean-ctx, the contract excepted."""
    return [
        f"{heading}\n{body}" for heading, body in _sections(text)
        if "lean-ctx" in heading.lower() and "capability contract" not in heading.lower()
    ]


def _subject_lines(section: str, name: str) -> list[str]:
    """Contract bullets whose first code span is ``name``."""
    lines = []
    for line in section.splitlines():
        if not line.lstrip().startswith("- "):
            continue
        match = _FIRST_CODE_SPAN_RE.search(line)
        if match and match.group(1) == name:
            lines.append(line)
    return lines


def _frontmatter_lines(text: str) -> list[str]:
    lines = text.splitlines()
    end = lines.index("---", 1)
    return lines[1:end]


def _tools(text: str) -> list[str]:
    line = next(ln for ln in _frontmatter_lines(text) if ln.startswith("tools: "))
    return [t.strip() for t in line[len("tools: "):].split(",") if t.strip()]


def _allowed(text: str) -> list[str]:
    return [ln.strip()[:-len(": allow")] for ln in _frontmatter_lines(text)
            if ln.startswith("  ") and ln.endswith(": allow")]


def _todays_tools(stack: str, role: str) -> list[str]:
    params = agents.load_stack_params(STACKS_DIR, stack)
    return list(params["roles"][role]["tools"])


def _agent_name(stack: str, role: str) -> str:
    return f"{stack}-{role}-agent.md"


def _names_word(text: str, word: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", text) is not None


def _lean_ctx_mentions(text: str) -> list[str]:
    """Every line naming a ``ctx_*`` tool, the ``lean_ctx`` tool or lean-ctx."""
    return [ln for ln in text.splitlines()
            if "ctx_" in ln or re.search(r"(?i)lean[-_]ctx", ln)]


def _tool_usage_sections(text: str) -> list[str]:
    return [body for heading, body in _sections(text)
            if heading.lower().startswith("tool usage")]


class _ProjectCase(_verdicts._InitSandboxCase):
    """The C1 sandbox (temp ``install.toml``, empty Pi agent dir, a home
    without Crucible's manifest) plus a verdict builder."""

    def verdicts(self, **states) -> dict:
        """Complete python-project verdicts, ``detected`` unless named:
        ``states`` maps a ``[capabilities]`` key (``_`` for ``-`` and
        ``.``: ``lean_ctx``, ``python_client``) to a verdict, or to ``None``
        to leave that key unrecorded."""
        verdicts = _verdicts._complete_verdicts("detected")
        by_alias = {k.replace("-", "_").replace(".", "_"): k for k in verdicts}
        for alias, verdict in states.items():
            key = by_alias[alias]
            if verdict is None:
                del verdicts[key]
            else:
                verdicts[key] = verdict
        return verdicts

    def init_ok(self, target: Path, **fields) -> tuple[dict, str]:
        rc, axi, err = self.run_init(target, **fields)
        self.assertEqual((rc, axi.get("ok")), (0, True), f"init must succeed; stderr={err!r}")
        return axi, err

    def read(self, path: Path) -> str:
        self.assertTrue(path.is_file(), f"{path} not emitted")
        return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# §S4 — the KNOWLEDGE_CATEGORY key
# ---------------------------------------------------------------------------

class KnowledgeCategorySchemaEntryTest(unittest.TestCase):
    """§S4 "The key": declared once in the packaged schema with its file,
    scope, condition, derivation, override and readers."""

    def _entry(self) -> dict:
        data = tomllib.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        table = next(v for v in data.values() if isinstance(v, list))
        found = [e for e in table if e.get("name") == KEY]
        self.assertEqual(len(found), 1, f"§S4: exactly one {KEY} entry; "
                                        f"names={[e.get('name') for e in table]!r}")
        return found[0]

    def test_it_is_a_root_and_sub_env_key_rendered_only_when_lean_ctx_is_present(self):
        entry = self._entry()
        self.assertEqual(
            (entry.get("file"), entry.get("scope"), entry.get("when")),
            (".env", "root+sub", "lean-ctx"), entry)

    def test_it_derives_from_the_token_and_is_overridable_by_its_flag(self):
        entry = self._entry()
        self.assertEqual((entry.get("source"), entry.get("override")),
                         ("derive", OVERRIDE_FLAG), entry)
        self.assertIn("PROJECT_TOKEN", entry.get("inputs", []), entry)

    def test_its_readers_are_init_orchestration_common_and_bootstrap(self):
        readers = self._entry().get("readers", [])
        for reader in ("modelb-axi init", "orchestration-common", "bootstrap"):
            with self.subTest(reader=reader):
                self.assertTrue(any(reader in r for r in readers),
                                f"§S4 names {reader!r} among the readers; got {readers!r}")

    def test_the_packaged_schema_loads_with_it(self):
        from modelb_axi import scaffold
        names = [e["name"] for e in scaffold.load_schema(SCHEMA_PATH)]
        self.assertEqual(names.count(KEY), 1, names)


class KnowledgeCategoryRenderedTest(_ProjectCase):
    """§S4 AC "lean-ctx present" / "absent or unknown", driven through
    ``run_init``."""

    def test_present_lean_ctx_writes_the_derived_category_into_the_root_env(self):
        self.write_install(self.verdicts())
        target = self.root / "proj"
        axi, _err = self.init_ok(target)
        text = self.read(target / ".env")
        lines = [ln for ln in text.splitlines() if ln.startswith(f"{KEY}=")]
        self.assertEqual(lines, [f"{KEY}={DERIVED_CATEGORY}"], f".env={text!r}")
        self.assertEqual((axi.get("registry") or {}).get(KEY), DERIVED_CATEGORY,
                         "the envelope's registry reports the rendered value")

    def test_installed_lean_ctx_counts_as_present(self):
        self.write_install(self.verdicts(lean_ctx="installed"))
        target = self.root / "proj"
        self.init_ok(target)
        self.assertEqual(parse_env_file(target / ".env").get(KEY), DERIVED_CATEGORY)

    def test_the_override_flag_wins_over_the_derived_value(self):
        self.write_install(self.verdicts())
        target = self.root / "proj"
        self.init_ok(target, knowledge_category="shared-kb-2")
        text = self.read(target / ".env")
        self.assertEqual([ln for ln in text.splitlines() if ln.startswith(f"{KEY}=")],
                         [f"{KEY}=shared-kb-2"], text)
        self.assertNotIn(DERIVED_CATEGORY, text)

    def test_each_monorepo_sub_project_carries_its_own_key(self):
        self.write_install(self.verdicts())
        target = self.root / "mono"
        self.init_ok(target, repo_shape="monorepo:a,b")
        self.assertEqual(parse_env_file(target / ".env").get(KEY), DERIVED_CATEGORY)
        for sub in ("a", "b"):
            with self.subTest(sub=sub):
                self.assertEqual(parse_env_file(target / sub / ".env").get(KEY),
                                 DERIVED_CATEGORY, f"§S4: {sub}/.env carries its own")

    def test_absent_unknown_or_unrecorded_lean_ctx_writes_no_key(self):
        for verdict in ("absent", "unknown", None):
            with self.subTest(lean_ctx=verdict):
                self.write_install(self.verdicts(lean_ctx=verdict))
                target = self.root / f"proj-{verdict}"
                axi, _err = self.init_ok(target, repo_shape="monorepo:a",
                                         knowledge_category="shared-kb")
                for rel in (".env", "a/.env", ".env.local"):
                    self.assertNotIn(KEY, self.read(target / rel), f"{rel}: no key")
                self.assertNotIn(KEY, axi.get("registry") or {},
                                 "a key for an absent tool is not resolved at all")

    def test_a_pre_capabilities_install_toml_writes_no_key(self):
        self.write_install(None)
        target = self.root / "proj"
        self.init_ok(target)
        self.assertNotIn(KEY, self.read(target / ".env"))

    def test_dry_run_reports_the_category_and_writes_nothing(self):
        self.write_install(self.verdicts())
        target = self.root / "dry"
        axi, _err = self.init_ok(target, dry_run=True)
        self.assertEqual((axi.get("registry") or {}).get(KEY), DERIVED_CATEGORY, axi)
        self.assertFalse(target.exists(), "--dry-run writes nothing")


class KnowledgeCategoryValidationTest(_ProjectCase):
    """§S4 "validated as a kebab-case id": an invalid value is refused
    before anything is written, naming the key and its flag."""

    def _refused(self, target: Path, **fields) -> str:
        rc, axi, err = self.run_init(target, **fields)
        self.assertEqual((rc, axi.get("ok")), (2, False), f"stderr={err!r}")
        self.assertFalse(target.exists(), "refused before anything is written")
        return " ".join(axi.get("warnings", []))

    def test_a_non_kebab_override_is_refused_naming_the_key_and_its_flag(self):
        self.write_install(self.verdicts())
        for bad in ("Not Kebab", "under_score", "UPPER-case", "-leading", "trailing-",
                    "dot.ted"):
            with self.subTest(value=bad):
                message = self._refused(self.root / f"bad-{abs(hash(bad))}",
                                        knowledge_category=bad)
                self.assertIn(KEY, message)
                self.assertIn(OVERRIDE_FLAG, message)

    def test_a_kebab_case_override_is_accepted(self):
        self.write_install(self.verdicts())
        for good in ("kb", "shared-kb-2", "a1-b2-c3"):
            with self.subTest(value=good):
                target = self.root / f"good-{good}"
                self.init_ok(target, knowledge_category=good)
                self.assertEqual(parse_env_file(target / ".env").get(KEY), good)

    def test_a_token_that_is_not_kebab_case_still_derives_a_kebab_case_category(self):
        # MIGRATED PIN (CR-MDB-045 C5 FIX, spec amended at 06a4ca4, finding F2):
        # was ..._is_refused_only_when_lean_ctx_is_present. §S4 now normalises
        # the derived category to kebab-case, and a token accepted before this
        # CR never makes init fail.
        self.write_install(self.verdicts())
        for token, category in (("MyProj", "myproj-workflow"),
                                ("my_proj", "my-proj-workflow"),
                                ("My_Proj", "my-proj-workflow")):
            with self.subTest(token=token):
                target = self.root / f"token-{token}"
                self.init_ok(target, token=token)
                self.assertEqual(parse_env_file(target / ".env").get(KEY), category)

    def test_every_token_init_accepts_derives_a_valid_category(self):
        derive = scaffold.DERIVE_RULES["knowledge_category"]
        for token in ("MyProj", "my_proj", "My Proj", "a.b", "x--y", "_x_", "Ünï",
                      "___", "proj2", "A-B-C"):
            with self.subTest(token=token):
                category = derive(token)
                self.assertEqual(scaffold.VALIDATE_RULES["kebab_id"](category), category)
                self.assertTrue(category.endswith("workflow"), category)


class KnowledgeCategoryNotAppliedNoteTest(_ProjectCase):
    """§S4: ``--knowledge-category`` given while lean-ctx is not present is
    noted on stderr as not applied (finding F3)."""

    @staticmethod
    def _notes(err: str) -> list[str]:
        return [ln for ln in err.splitlines()
                if OVERRIDE_FLAG in ln and "not applied" in ln]

    def test_the_override_without_lean_ctx_present_is_noted_as_not_applied(self):
        for verdict in ("absent", "unknown", None):
            with self.subTest(lean_ctx=verdict):
                self.write_install(self.verdicts(lean_ctx=verdict))
                for dry_run in (False, True):
                    target = self.root / f"proj-{verdict}-{dry_run}"
                    _axi, err = self.init_ok(target, knowledge_category="shared-kb",
                                             dry_run=dry_run)
                    self.assertEqual(len(self._notes(err)), 1, f"stderr={err!r}")

    def test_no_note_without_the_flag_or_with_lean_ctx_present(self):
        self.write_install(self.verdicts(lean_ctx="absent"))
        _axi, err = self.init_ok(self.root / "no-flag")
        self.assertEqual(self._notes(err), [], err)
        self.write_install(self.verdicts())
        _axi, err = self.init_ok(self.root / "present", knowledge_category="shared-kb")
        self.assertEqual(self._notes(err), [], err)


class KnowledgeCategoryCliFlagTest(_ProjectCase):
    """§S4: ``--knowledge-category`` through the production entry, sandboxed."""

    def test_the_cli_override_reaches_the_env(self):
        self.write_install(self.verdicts())
        xdg = self.root / "xdg"
        xdg.mkdir()
        target = self.root / "cli-proj"
        env = {"HOME": str(self.home), "MODELB_HOME": str(self.modelb_home),
               "XDG_DATA_HOME": str(xdg), AGENT_DIR_ENV: str(self.agent_dir)}
        for name, value in env.items():
            self.assertTrue(value.startswith(str(self.root)), f"sandbox guard: {name}")
        result = run_module(
            "--yes", "init", "--name", _verdicts.NAME, "--token", TOKEN,
            "--acronym", _verdicts.ACRONYM, "--mode", "solo", "--repo-shape", "standalone",
            "--stacks", STACK, "--owner", _verdicts.OWNER, "--target", str(target),
            "--no-commit", "--modelb-home", str(self.modelb_home),
            OVERRIDE_FLAG, "cli-kb", env_overrides=env, timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(parse_env_file(target / ".env").get(KEY), "cli-kb")


# ---------------------------------------------------------------------------
# §S4 — the orchestrator's pointer in AGENTS.md
# ---------------------------------------------------------------------------

class LeanCtxPointerTest(_ProjectCase):
    """§S4 "The pointer": with lean-ctx present the scaffolded ``AGENTS.md``
    carries ONE lean-ctx section naming the category, telling the
    orchestrator to prefer lean-ctx's reads and shell, to keep execution
    knowledge in the store through the session's knowledge capability — never
    the ``lean-ctx knowledge`` CLI — and to load that category at bootstrap."""

    def _section(self, text: str) -> str:
        found = _lean_ctx_sections(text)
        self.assertEqual(len(found), 1, f"§S4: exactly one lean-ctx section; got {text!r}")
        return found[0]

    def test_present_lean_ctx_adds_one_section_naming_the_category_and_key(self):
        self.write_install(self.verdicts())
        target = self.root / "proj"
        self.init_ok(target)
        section = self._section(self.read(target / "AGENTS.md"))
        self.assertIn(DERIVED_CATEGORY, section)
        self.assertIn(KEY, section, "the pointer names the registry key")

    def test_the_section_carries_the_three_instructions(self):
        self.write_install(self.verdicts())
        target = self.root / "proj"
        self.init_ok(target)
        section = self._section(self.read(target / "AGENTS.md"))
        lowered = section.lower()
        for word in ("read", "shell", "knowledge", "bootstrap"):
            with self.subTest(word=word):
                self.assertIn(word, lowered, section)
        cli_lines = [ln for ln in section.splitlines() if "lean-ctx knowledge" in ln]
        self.assertTrue(cli_lines, f"§S4 names the `lean-ctx knowledge` CLI; {section!r}")
        self.assertTrue(all(re.search(r"(?i)\bnever\b", ln) for ln in cli_lines),
                        f"§S4: the CLI is named only to forbid it; {cli_lines!r}")

    def test_the_section_follows_the_override(self):
        self.write_install(self.verdicts())
        target = self.root / "proj"
        self.init_ok(target, knowledge_category="shared-kb")
        section = self._section(self.read(target / "AGENTS.md"))
        self.assertIn("shared-kb", section)
        self.assertNotIn(DERIVED_CATEGORY, section)

    def test_each_sub_project_agents_md_names_the_category_in_its_own_env(self):
        self.write_install(self.verdicts())
        target = self.root / "mono"
        self.init_ok(target, repo_shape="monorepo:a,b")
        for sub in ("a", "b"):
            with self.subTest(sub=sub):
                own = parse_env_file(target / sub / ".env").get(KEY)
                self.assertEqual(own, DERIVED_CATEGORY)
                section = self._section(self.read(target / sub / "AGENTS.md"))
                self.assertIn(own, section)

    def test_the_bootstrap_instruction_says_restore_then_list(self):
        # Finding F5 (§S4 "restore its archived facts, then list it").
        self.write_install(self.verdicts())
        target = self.root / "proj"
        self.init_ok(target)
        section = self._section(self.read(target / "AGENTS.md"))
        lines = [ln.lower() for ln in section.splitlines() if "bootstrap" in ln.lower()]
        self.assertTrue(
            any(re.search(r"\brestor\w*\b.{0,60}\barchived\b.*\bthen\b.*\blists?\b", ln)
                for ln in lines),
            f"§S4: at bootstrap, restore the archived facts, then list; {lines!r}")

    def test_absent_or_unknown_lean_ctx_writes_no_section(self):
        for verdict in ("absent", "unknown", None):
            with self.subTest(lean_ctx=verdict):
                self.write_install(self.verdicts(lean_ctx=verdict))
                target = self.root / f"proj-{verdict}"
                self.init_ok(target, repo_shape="monorepo:a")
                for rel in ("AGENTS.md", "a/AGENTS.md"):
                    text = self.read(target / rel)
                    self.assertEqual(_lean_ctx_sections(text), [], f"{rel}: {text!r}")
                    self.assertNotIn(KEY, text)
                    self.assertNotIn(DERIVED_CATEGORY, text)


# ---------------------------------------------------------------------------
# §S5 — the capability contract shows the project's state
# ---------------------------------------------------------------------------

class CapabilityContractStateTest(_ProjectCase):
    """§S5 AC: the contract lists each of the project's tools — every
    tier-1 and tier-2 row, the stack's ``crucible-client`` and each of its
    toolchain probes (the per-stack detail) — with its state, and the
    remediation where it is not present."""

    def assert_listed(self, section: str, name: str, state: str, remediation: str):
        lines = _subject_lines(section, name)
        self.assertTrue(lines, f"§S5: `{name}` is listed; section={section!r}")
        for line in lines:
            self.assertEqual(_STATE_RE.findall(line), [state],
                             f"§S5: `{name}` is listed as {state}: {line!r}")
            if state == PRESENT:
                self.assertNotIn(remediation, line, "no remediation for a present tool")
            else:
                self.assertIn(remediation, line, f"the remediation of `{name}`")

    def contract_for(self, verdicts: dict | None, **fields) -> str:
        self.write_install(verdicts)
        target = self.root / "proj"
        self.init_ok(target, **fields)
        return _contract(self.read(target / "AGENTS.md"))

    def test_mixed_verdicts_are_each_listed_with_their_state(self):
        section = self.contract_for(self.verdicts(
            dispatch="absent", sandesh_pi=None, gh="absent", jq="unknown",
            python_client="absent", python_xmlrunner="absent"))
        expected: dict[str, str] = dict.fromkeys(_always_ids(), PRESENT)
        expected.update({"dispatch": ABSENT, "sandesh-pi": UNKNOWN, "gh": ABSENT,
                         "jq": UNKNOWN})
        for rid, state in expected.items():
            with self.subTest(tool=rid):
                self.assert_listed(section, rid, state, _row(rid)["remediation"])
        with self.subTest(tool="crucible-client"):
            self.assert_listed(section, "crucible-client", ABSENT,
                               _row("crucible-client")["remediation"])
        probes = {p["name"]: p for p in STACK_TOOLCHAINS[STACK]}
        for name, state in (("python3", PRESENT), ("xmlrunner", ABSENT),
                            ("coverage", PRESENT)):
            with self.subTest(probe=name):
                self.assert_listed(section, name, state, probes[name]["remediation"])

    def test_everything_present_lists_no_remediation_at_all(self):
        section = self.contract_for(self.verdicts())
        for rid in _always_ids() + ["crucible-client"]:
            with self.subTest(tool=rid):
                self.assert_listed(section, rid, PRESENT, _row(rid)["remediation"])
        remediations = {r["remediation"] for r in REQUIREMENTS}
        remediations |= {p["remediation"] for p in STACK_TOOLCHAINS[STACK]}
        self.assertEqual(sorted(r for r in remediations if r in section), [],
                         f"§S5: nothing to remediate; section={section!r}")

    def test_a_pre_capabilities_install_lists_the_unrecorded_tools_as_unknown(self):
        section = self.contract_for(None)
        # MIGRATED at CR-MDB-047 C1 RED (\u00a7S1): watcher -> worktree, + direnv.
        for rid in ("dispatch", "lean-ctx", "permissions", "worktree", "sandesh-pi",
                    "python3", "bash", "gh", "jq", "direnv", "crucible-client"):
            with self.subTest(tool=rid):
                self.assert_listed(section, rid, UNKNOWN, _row(rid)["remediation"])
        for rid in ("uv", "sandesh", "crucible"):
            with self.subTest(tool=rid):
                self.assert_listed(section, rid, PRESENT, _row(rid)["remediation"])

    def test_only_the_projects_stacks_are_listed(self):
        section = self.contract_for(self.verdicts())
        for stack, probes in STACK_TOOLCHAINS.items():
            if stack == STACK:
                continue
            for probe in probes:
                if probe["name"] in {p["name"] for p in STACK_TOOLCHAINS[STACK]}:
                    continue
                with self.subTest(stack=stack, probe=probe["name"]):
                    self.assertEqual(_subject_lines(section, probe["name"]), [])

    def test_each_tool_appears_once(self):
        # Finding F4 (\u00a7S5 "each tool appears once"): a tier-2 row and a
        # stack toolchain probe for the same tool (`python3`) are one line.
        section = self.contract_for(self.verdicts())
        names = [m.group(1) for ln in section.splitlines() if ln.lstrip().startswith("- ")
                 for m in [_FIRST_CODE_SPAN_RE.search(ln)] if m]
        doubled = sorted({n for n in names if names.count(n) > 1})
        self.assertEqual(doubled, [], f"\u00a7S5: each tool once; section={section!r}")

    def test_the_merged_line_carries_the_worse_state(self):
        section = self.contract_for(self.verdicts(python_python3="absent"))
        self.assertEqual(len(_subject_lines(section, "python3")), 1, section)
        self.assert_listed(section, "python3", ABSENT, _row("python3")["remediation"])


class SetupTasksNameRemediationTest(_ProjectCase):
    """§S5: the identity section's Sandesh project and the queue README's
    setup tasks stay; where Sandesh or Crucible is absent, its setup task
    first names the tool's remediation."""

    def _readme_line(self, target: Path, anchor: str) -> str:
        text = self.read(target / "docs" / "changes" / "README.md")
        lines = [ln for ln in text.splitlines() if anchor in ln and ln.startswith("- [ ]")]
        self.assertEqual(len(lines), 1, f"one setup task names {anchor!r}; README={text!r}")
        return lines[0]

    def test_an_absent_crucible_puts_its_remediation_first_in_the_registration_task(self):
        remediation = _row("crucible")["remediation"]
        self.write_install(self.verdicts(crucible="absent"))
        target = self.root / "proj"
        self.init_ok(target)
        task = self._readme_line(target, "CRUCIBLE_PROJECT_KEY")
        self.assertIn(remediation, task)
        self.assertLess(task.index(remediation), task.index("CRUCIBLE_PROJECT_KEY"),
                        f"§S5: the remediation comes first; {task!r}")

    def test_a_present_crucible_task_names_no_remediation(self):
        self.write_install(self.verdicts())
        target = self.root / "proj"
        self.init_ok(target)
        self._readme_line(target, "CRUCIBLE_PROJECT_KEY")
        text = self.read(target / "docs" / "changes" / "README.md")
        self.assertNotIn(_row("crucible")["remediation"], text)
        self.assertNotIn(_row("sandesh")["remediation"], text)

    def test_an_absent_sandesh_puts_its_remediation_first_in_the_sandesh_task(self):
        remediation = _row("sandesh")["remediation"]
        self.write_install(self.verdicts(sandesh="absent"))
        target = self.root / "proj"
        self.init_ok(target, mode="multi:2")
        anchor = f"`Mainline - {SANDESH_ID}`"
        task = self._readme_line(target, anchor)
        self.assertIn(remediation, task)
        self.assertLess(task.index(remediation), task.index(anchor), task)
        text = self.read(target / "docs" / "changes" / "README.md")
        self.assertNotIn(_row("crucible")["remediation"], text,
                         "a present Crucible's task is unchanged")
        agents_md = self.read(target / "AGENTS.md")
        self.assertIn(f"- Sandesh project: `{SANDESH_ID}`", agents_md,
                      "§S5: the identity section's Sandesh pointer stays")

    def test_a_present_sandesh_task_names_no_remediation(self):
        self.write_install(self.verdicts())
        target = self.root / "proj"
        self.init_ok(target, mode="multi:2")
        task = self._readme_line(target, f"`Mainline - {SANDESH_ID}`")
        self.assertNotIn(_row("sandesh")["remediation"], task)


# ---------------------------------------------------------------------------
# §S8 — the project's agents match its tools
# ---------------------------------------------------------------------------

class _AgentsCase(_ProjectCase):
    """What an agent rendered for a present / absent lean-ctx is."""

    def assert_todays_form(self, agents_dir: Path, stacks=AGENT_STACKS):
        for stack in stacks:
            for role in ROLES:
                name = _agent_name(stack, role)
                with self.subTest(agent=name):
                    self.assertEqual(
                        (agents_dir / name).read_bytes(),
                        (COMMITTED_AGENTS_DIR / name).read_bytes(),
                        f"§S8: with lean-ctx present {name} is byte-identical to today's")

    def assert_builtin_form(self, agents_dir: Path, stacks=AGENT_STACKS):
        for stack in stacks:
            for role in ROLES:
                name = _agent_name(stack, role)
                with self.subTest(agent=name):
                    text = (agents_dir / name).read_text(encoding="utf-8")
                    todays = _todays_tools(stack, role)
                    tools = _tools(text)
                    self.assertEqual([t for t in tools if t != PI_BUILTIN_SHELL],
                                     [t for t in todays if not t.startswith("ctx_")],
                                     "today's non-ctx tools, in order")
                    self.assertEqual(tools.count(PI_BUILTIN_SHELL), 1,
                                     f"ruling: `bash` replaces ctx_shell; tools={tools!r}")
                    self.assertIn(PI_BUILTIN_SHELL, _allowed(text), "bash is allowed")
                    self.assertEqual(_lean_ctx_mentions(text), [],
                                     "ruling: no ctx_* tool and no lean-ctx instruction "
                                     "anywhere in the definition")
                    usage = _tool_usage_sections(text)
                    self.assertEqual(len(usage), 1, "one tool-usage section")
                    for tool in ("read", "grep", PI_BUILTIN_SHELL):
                        self.assertTrue(_names_word(usage[0], tool),
                                        f"the section names the built-in `{tool}`; "
                                        f"{usage[0]!r}")
                    self.assertEqual(agents.ownership_state(text), agents.OWNED_INTACT,
                                     "still an owned, re-renderable definition")


class InitRendersAgentsForItsToolsTest(_AgentsCase):
    """§S8 AC through ``run_init``, for every stack x role."""

    ALL_STACKS = ",".join(AGENT_STACKS)

    def test_present_lean_ctx_renders_todays_agents(self):
        self.write_install(self.verdicts())
        target = self.root / "proj"
        self.init_ok(target, stacks=self.ALL_STACKS)
        self.assert_todays_form(target / PI_AGENTS_RELDIR)

    def test_absent_lean_ctx_renders_agents_for_the_builtin_tools(self):
        self.write_install(self.verdicts(lean_ctx="absent"))
        target = self.root / "proj"
        self.init_ok(target, stacks=self.ALL_STACKS)
        self.assert_builtin_form(target / PI_AGENTS_RELDIR)

    def test_unknown_lean_ctx_renders_agents_for_the_builtin_tools(self):
        for verdict in ("unknown", None):
            with self.subTest(lean_ctx=verdict):
                self.write_install(self.verdicts(lean_ctx=verdict))
                target = self.root / f"proj-{verdict}"
                self.init_ok(target, stacks=self.ALL_STACKS)
                self.assert_builtin_form(target / PI_AGENTS_RELDIR)

    def test_a_pre_capabilities_install_renders_agents_for_the_builtin_tools(self):
        self.write_install(None)
        target = self.root / "proj"
        self.init_ok(target)
        self.assert_builtin_form(target / PI_AGENTS_RELDIR, stacks=(STACK,))


class AgentsVerbRendersForItsToolsTest(_AgentsCase):
    """§S8 AC through ``modelb-axi agents``: the verb reads the lean-ctx
    verdict from ``install.toml`` each time it runs."""

    def _agents_verb(self, target: Path) -> subprocess.CompletedProcess:
        xdg = self.root / "xdg"
        xdg.mkdir(exist_ok=True)
        env = dict(os.environ)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing if existing else "")
        env.update({"HOME": str(self.home), "MODELB_HOME": str(self.modelb_home),
                    "XDG_DATA_HOME": str(xdg), AGENT_DIR_ENV: str(self.agent_dir)})
        for name in ("HOME", "MODELB_HOME", "XDG_DATA_HOME", AGENT_DIR_ENV):
            self.assertTrue(env[name].startswith(str(self.root)), f"sandbox guard: {name}")
        return subprocess.run(
            [sys.executable, "-m", "modelb_axi", "--modelb-home", str(self.modelb_home),
             "agents"],
            cwd=str(target), capture_output=True, text=True, timeout=120,
            stdin=subprocess.DEVNULL, env=env,
        )

    def test_the_verb_follows_the_recorded_verdict_both_ways(self):
        self.write_install(self.verdicts())
        target = self.root / "proj"
        self.init_ok(target)
        agents_dir = target / PI_AGENTS_RELDIR
        self.assert_todays_form(agents_dir, stacks=(STACK,))

        self.write_install(self.verdicts(lean_ctx="absent"))
        result = self._agents_verb(target)
        self.assertEqual(result.returncode, 0, result.stderr)
        axi = decode_axi(result.stdout)
        self.assertEqual(
            sorted(axi.get("written", [])),
            sorted(str(PI_AGENTS_RELDIR / _agent_name(STACK, r)) for r in ROLES),
            f"every definition is re-rendered; stdout={result.stdout!r}")
        self.assert_builtin_form(agents_dir, stacks=(STACK,))

        self.write_install(self.verdicts())
        result = self._agents_verb(target)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_todays_form(agents_dir, stacks=(STACK,))


class CanonicalAgentsKeepTheLeanCtxFormTest(unittest.TestCase):
    """§S8 "``generator/agents/`` … keeps the lean-ctx form" — a regression
    pin (passes today): it fails if the committed canonical set is rendered
    in the built-in form."""

    def test_every_committed_definition_keeps_ctx_shell_and_the_lean_ctx_section(self):
        for stack in AGENT_STACKS:
            for role in ROLES:
                name = _agent_name(stack, role)
                with self.subTest(agent=name):
                    text = (COMMITTED_AGENTS_DIR / name).read_text(encoding="utf-8")
                    self.assertIn("ctx_shell", _tools(text))
                    self.assertNotIn(PI_BUILTIN_SHELL, _tools(text))
                    headings = [h for h, _ in _sections(text)
                                if h.lower().startswith("tool usage")]
                    self.assertEqual(len(headings), 1, headings)
                    self.assertIn("lean-ctx", headings[0])


# ---------------------------------------------------------------------------
# VERIFY findings (CR-MDB-045 C5 FIX; spec amended at 06a4ca4)
# ---------------------------------------------------------------------------

#: A lean-ctx tool or instruction named in a scaffolded file.
_LEAN_CTX_NAME_RE = re.compile(r"ctx_|(?i:lean[-_]ctx)")
POLICY_REL = Path(".pi") / "extensions" / "pi-permission-system" / "config.json"


class ProjectPolicyMatchesToolsTest(_ProjectCase):
    """\u00a7S8 "The permission policy" (finding a): with lean-ctx absent or
    unknown the project's Pi permission policy allows ``bash`` and names no
    ``ctx_*`` tool; with lean-ctx present it allows the lean-ctx tools and
    not ``bash``, as today."""

    def _policy(self, verdict, name: str) -> tuple[str, dict]:
        self.write_install(self.verdicts(lean_ctx=verdict) if verdict != "no-caps" else None)
        target = self.root / name
        self.init_ok(target)
        text = self.read(target / POLICY_REL)
        body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("//"))
        return text, json.loads(body)["permission"]

    def test_absent_or_unknown_lean_ctx_allows_bash_and_names_no_ctx_tool(self):
        dispatch = set(_row("dispatch")["tools"])
        for verdict in ("absent", "unknown", None, "no-caps"):
            with self.subTest(lean_ctx=verdict):
                text, permission = self._policy(verdict, f"proj-{verdict}")
                self.assertEqual(permission.get(PI_BUILTIN_SHELL), "allow", permission)
                self.assertIsNone(_LEAN_CTX_NAME_RE.search(text), text)
                allowed = {k for k, v in permission.items() if v == "allow"}
                self.assertTrue(dispatch <= allowed, "the dispatch tools stay allowed")
                self.assertEqual(permission.get("*"), "ask")

    def test_present_lean_ctx_keeps_todays_policy(self):
        _text, permission = self._policy("detected", "proj")
        for tool in _row("lean-ctx")["tools"]:
            self.assertEqual(permission.get(tool), "allow", tool)
        self.assertNotEqual(permission.get(PI_BUILTIN_SHELL), "allow")


class MemorySlicesMatchToolsTest(_ProjectCase):
    """\u00a7S8 "The memory slices" (finding b): with lean-ctx absent or unknown
    no stack memory template ``init`` scaffolds into ``docs/memory/`` names a
    lean-ctx tool \u2014 every stack family selected."""

    def test_no_scaffolded_memory_slice_names_lean_ctx(self):
        for verdict in ("absent", "unknown"):
            with self.subTest(lean_ctx=verdict):
                self.write_install(self.verdicts(lean_ctx=verdict))
                target = self.root / f"proj-{verdict}"
                self.init_ok(target, stacks=",".join(scaffold.KNOWN_STACKS))
                slices = sorted((target / "docs" / "memory").glob("*.md"))
                self.assertIn("rust-orchestration.md", [p.name for p in slices])
                found = {p.name: [ln for ln in p.read_text(encoding="utf-8").splitlines()
                                  if _LEAN_CTX_NAME_RE.search(ln)] for p in slices}
                self.assertEqual({k: v for k, v in found.items() if v}, {})


class AgentRenderFailureRefusedTest(_ProjectCase):
    """\u00a7S8 "Validated before the first write" (finding F1): ``init`` and
    ``modelb-axi agents`` render every agent in memory during validation; a
    render failure \u2014 a missing or unreadable built-in passages file, or a
    definition still naming lean-ctx \u2014 exits 2 with an error envelope and
    writes nothing, ``--dry-run`` included. The assets are a private copy of
    ``generator/`` at the fixture's configured asset root."""

    def setUp(self):
        super().setUp()
        # _install_toml_text's asset_root is <modelb_home>/no-asset-root-here.
        self.assets = self.modelb_home / "no-asset-root-here"
        shutil.copytree(GENERATOR_DIR, self.assets / "generator",
                        ignore=shutil.ignore_patterns("agents", "__pycache__"))
        self.passages = self.assets / "generator" / "templates" / agents.BUILTIN_PASSAGES_NAME

    def _break(self, how: str) -> None:
        if how == "missing":
            self.passages.unlink()
        elif how == "unreadable":
            self.passages.write_text("[[passage]\nlean = ", encoding="utf-8")
        else:  # a definition still naming lean-ctx: no passages at all
            self.passages.write_text("# no passages\n", encoding="utf-8")

    def _restore(self) -> None:
        shutil.copy2(GENERATOR_DIR / "templates" / agents.BUILTIN_PASSAGES_NAME, self.passages)

    def assert_refused(self, rc: int, axi: dict, err: str) -> None:
        self.assertEqual((rc, axi.get("ok")), (2, False), f"stderr={err!r}")
        self.assertTrue(axi.get("warnings"), f"the error envelope names the failure; {axi!r}")

    def test_init_refuses_a_render_failure_before_writing_dry_run_included(self):
        for how in ("missing", "unreadable", "leftover"):
            for dry_run in (False, True):
                with self.subTest(failure=how, dry_run=dry_run):
                    self._restore()
                    self._break(how)
                    self.write_install(self.verdicts(lean_ctx="absent"))
                    target = self.root / f"proj-{how}-{dry_run}"
                    self.assert_refused(*self.run_init(target, dry_run=dry_run))
                    self.assertFalse(target.exists(), "nothing is written")

    def test_present_lean_ctx_does_not_need_the_passages_file(self):
        self._break("missing")
        self.write_install(self.verdicts())
        target = self.root / "proj"
        self.init_ok(target)
        self.assertTrue((target / PI_AGENTS_RELDIR / _agent_name(STACK, "red")).is_file())

    def _run_agents(self, target: Path) -> tuple[int, dict, str]:
        args = argparse.Namespace(stacks=None, force_managed=False)
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.dict(os.environ, {"HOME": str(self.home),
                                         AGENT_DIR_ENV: str(self.agent_dir)}),
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err),
        ):
            rc = scaffold.run_agents(args, self.modelb_home, project_root=target)
        return rc, decode_axi(out.getvalue()), err.getvalue()

    def test_the_agents_verb_refuses_a_render_failure_and_writes_nothing(self):
        self.write_install(self.verdicts())
        target = self.root / "proj"
        self.init_ok(target)
        before = {p: p.read_bytes() for p in target.rglob("*")
                  if p.is_file() and ".git" not in p.parts}
        self.write_install(self.verdicts(lean_ctx="absent"))
        for how in ("missing", "unreadable", "leftover"):
            with self.subTest(failure=how):
                self._restore()
                self._break(how)
                self.assert_refused(*self._run_agents(target))
                after = {p: p.read_bytes() for p in target.rglob("*")
                         if p.is_file() and ".git" not in p.parts}
                self.assertEqual(after, before, "nothing is written")


class ContractCheckersTest(unittest.TestCase):
    """The checkers above, proved on synthetic input so they can fail."""

    CONTRACT = (
        "# P\n\n## Harness capability contract (x)\nintro\n"
        "- `dispatch` (required): absent — `pi install npm:x`\n"
        "- `uv`: present\n"
        "- `sandesh`: unknown — `uv tool install sandesh-relay`\n"
        "\n## lean-ctx (orchestrator)\n- keep facts under `k-workflow`\n"
        "\n## Generator note\n- n\n"
    )

    def test_contract_section_and_subject_lines(self):
        section = _contract(self.CONTRACT)
        self.assertNotIn("Generator note", section)
        self.assertNotIn("k-workflow", section)
        self.assertEqual(len(_subject_lines(section, "uv")), 1,
                         "the sandesh line mentions uv but is not uv's line")
        self.assertEqual(_STATE_RE.findall(_subject_lines(section, "sandesh")[0]), ["unknown"])
        self.assertEqual(_subject_lines(section, "gh"), [])

    def test_lean_ctx_sections(self):
        self.assertEqual(len(_lean_ctx_sections(self.CONTRACT)), 1)
        self.assertEqual(_lean_ctx_sections("# P\n## Harness capability contract\n"
                                            "- `lean-ctx`: present\n"), [])

    def test_agent_checkers(self):
        text = ("---\nname: a\ntools: read, bash, grep\npermission:\n  read: allow\n"
                "  bash: allow\n  write: deny\n---\n\n## Tool Usage (built-ins)\n"
                "Use `read`, `grep` and `bash`.\n")
        self.assertEqual(_tools(text), ["read", "bash", "grep"])
        self.assertEqual(_allowed(text), ["read", "bash"])
        self.assertEqual(_lean_ctx_mentions(text), [])
        self.assertEqual(_lean_ctx_mentions(text + "Run via `ctx_shell`.\n"),
                         ["Run via `ctx_shell`."])
        self.assertEqual(_lean_ctx_mentions("Prefer lean-ctx.\n"), ["Prefer lean-ctx."])
        self.assertEqual(len(_tool_usage_sections(text)), 1)


if __name__ == "__main__":
    unittest.main()
