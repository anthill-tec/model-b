"""The ``gap-analysis`` skill bundle adopted into Model B — CR-MDB-042 §S4.

Contract: ``docs/changes/CR-MDB-042-orchestrator-definitions-absorbed.md``. ``orchestration-common.md``
makes the ``gap-analysis`` skill "the single authority" for gap-analysis dimensions, yet Model B did
not ship it: it lived only in the user's skill store, so a fresh install left that reference
dangling. §S4 adopts it as ``skills-src/gap-analysis/SKILL.md``, with its ``CLAUDE.md`` references
replaced by the project's ``AGENTS.md``; the installer deploys it like every other bundle, with no
stack scope.

Class map:

- ``GapAnalysisBundleSourceTest`` — the bundle exists with ``name: gap-analysis`` and a
  description, is Model B-owned (not in ``skills-src/CRUCIBLE-HANDOVER.md``'s imported roster, and
  listed as Model B-owned in ``AGENTS.md``), names ``AGENTS.md`` and no ``CLAUDE.md`` anywhere in
  the bundle.
- ``GapAnalysisReferenceResolvesTest`` — every `` `<name>` skill `` that
  ``skills-src/model-b/references/orchestration-common.md`` names ships as
  ``skills-src/<name>/SKILL.md`` — ``gap-analysis`` among them.
- ``GapAnalysisPackagedTest`` — ``skills-src`` is force-included wholesale into the wheel's asset
  map, the resolved asset root carries the bundle, and the deploy engine's discovery selects it
  for every ``--stacks`` selection (no stack scope).
- ``GapAnalysisDeployedTest`` — a sandboxed installer run (``--modelb-home`` / ``--target-root``
  under a temp dir; ``HOME``, ``MODELB_HOME``, ``XDG_DATA_HOME``, ``PI_CODING_AGENT_DIR`` and
  ``PATH`` all sandboxed) deploys ``.agents/skills/gap-analysis/SKILL.md`` byte-identical to the
  source and records it, with its sha256, in ``install.toml`` — with no stack filter and with a
  single-stack selection that scopes ``code-health`` out.

The built wheel's own copy is proved by the installed-package end-to-end test in
``tests.test_installer_assets`` (``MODELB_OWNED_BUNDLE_NAMES`` includes ``gap-analysis``).
The absorbed triage rows and the AC3 neutrality of the bundle's text are gated in
``tests.test_orchestrator_rule_triage``.

Hermetic: nothing here reads the real ``$HOME``. Stdlib only.
"""

import hashlib
import re
import tomllib
import unittest

from modelb_axi import deploy
from tests._helpers import REPO_ROOT, files_under, read_text, split_frontmatter
from tests.test_installer_stack_selection import ALL_STACKS, _StackSandboxCase

BUNDLE = "gap-analysis"
BUNDLE_DIR = REPO_ROOT / "skills-src" / BUNDLE
SKILL_MD = BUNDLE_DIR / "SKILL.md"
HANDOVER_MD = REPO_ROOT / "skills-src" / "CRUCIBLE-HANDOVER.md"
AGENTS_MD = REPO_ROOT / "AGENTS.md"
ORCHESTRATION_COMMON = REPO_ROOT / "skills-src" / "model-b" / "references" / "orchestration-common.md"
DEPLOYED_REL = f".agents/skills/{BUNDLE}/SKILL.md"

_NAMED_SKILL = re.compile(r"`([a-z][a-z0-9-]*)` skill\b")
_HANDOVER_BULLET = re.compile(r"^- `([a-z0-9-]+)`", re.MULTILINE)


def frontmatter_fields(text: str) -> dict[str, str]:
    """The ``key: value`` lines of a SKILL.md frontmatter block (``{}`` when there is none)."""
    frontmatter, _ = split_frontmatter(text)
    fields = {}
    for line in frontmatter.splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    return fields


def _require_skill(case: unittest.TestCase) -> str:
    case.assertTrue(SKILL_MD.is_file(),
                    f"CR-MDB-042 §S4: {SKILL_MD.relative_to(REPO_ROOT)} does not exist")
    return read_text(SKILL_MD)


class GapAnalysisBundleSourceTest(unittest.TestCase):
    def test_skill_md_carries_gap_analysis_name_and_a_description(self):
        fields = frontmatter_fields(_require_skill(self))
        self.assertEqual(fields.get("name"), BUNDLE)
        self.assertGreater(len(fields.get("description", "")), 20,
                           f"the frontmatter description is missing or empty: {fields!r}")

    def test_bundle_is_model_b_owned_not_a_crucible_import(self):
        _require_skill(self)
        imported = _HANDOVER_BULLET.findall(read_text(HANDOVER_MD))
        self.assertEqual(len(imported), 6, f"precondition: the handover roster lists 6: {imported}")
        self.assertNotIn(BUNDLE, imported)
        row = next((ln for ln in read_text(AGENTS_MD).splitlines()
                    if ln.startswith("| `skills-src/`")), "")
        owned = re.search(r"Model[- ]B[- ]owned:(.*?)Imported", row, re.IGNORECASE)
        self.assertIsNotNone(owned, f"AGENTS.md's skills-src/ row names no Model B-owned list: {row!r}")
        assert owned is not None
        self.assertIn(f"`{BUNDLE}`", owned.group(1),
                      "AGENTS.md's skills-src/ row must list gap-analysis as Model B-owned")

    def test_no_file_in_the_bundle_names_claude_md_and_the_skill_names_agents_md(self):
        text = _require_skill(self)
        files = sorted(files_under(BUNDLE_DIR))
        self.assertIn(SKILL_MD, files)
        offenders = [f"{p.relative_to(REPO_ROOT)}:{n}" for p in files
                     for n, line in enumerate(read_text(p).splitlines(), 1) if "CLAUDE.md" in line]
        self.assertEqual(offenders, [], "§S4: CLAUDE.md references are replaced by AGENTS.md")
        self.assertIn("AGENTS.md", text, "§S4: the skill locates project facts via AGENTS.md")


class GapAnalysisReferenceResolvesTest(unittest.TestCase):
    def test_every_skill_orchestration_common_names_ships_in_skills_src_gap_analysis_included(self):
        named = sorted(set(_NAMED_SKILL.findall(read_text(ORCHESTRATION_COMMON))))
        self.assertIn(BUNDLE, named, "orchestration-common.md names the gap-analysis skill")
        dangling = [n for n in named
                    if not (REPO_ROOT / "skills-src" / n / "SKILL.md").is_file()]
        self.assertEqual(dangling, [], "a skill orchestration-common.md names is not shipped")
        self.assertEqual(frontmatter_fields(read_text(SKILL_MD)).get("name"), BUNDLE)


class GapAnalysisPackagedTest(unittest.TestCase):
    def test_skills_src_is_force_included_wholesale_and_the_asset_root_carries_the_bundle(self):
        with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
            force_include = (tomllib.load(fh)["tool"]["hatch"]["build"]["targets"]["wheel"]
                             ["force-include"])
        self.assertEqual(force_include.get("skills-src"), "modelb_axi/_assets/skills-src")
        asset_skill = deploy.default_asset_root() / "skills-src" / BUNDLE / "SKILL.md"
        self.assertTrue(asset_skill.is_file(), f"the asset root carries no {asset_skill}")
        self.assertEqual(asset_skill.read_bytes(), SKILL_MD.read_bytes())

    def test_bundle_discovery_selects_gap_analysis_for_every_stack_selection(self):
        self.assertNotIn(BUNDLE, deploy.STACK_SCOPED_BUNDLES, "§S4: no stack scope")
        root = deploy.default_asset_root()
        missing = []
        for stacks in [None] + [[s] for s in ALL_STACKS]:
            names = {p.name for p in deploy._skill_bundles(root, stacks)}
            if BUNDLE not in names:
                missing.append(stacks)
        self.assertEqual(missing, [], "selections whose bundle discovery lacks gap-analysis")
        # control: the selection really scopes — code-health is rust-only
        self.assertNotIn("code-health", {p.name for p in deploy._skill_bundles(root, ["bun"])})


class GapAnalysisDeployedTest(_StackSandboxCase):
    def sandbox_env(self) -> dict:
        env = super().sandbox_env()
        env["MODELB_HOME"] = str(self.modelb_home)
        env["XDG_DATA_HOME"] = str(self._root / "xdg")
        return env

    def _assert_gap_analysis_deployed_and_recorded(self):
        deployed = self.target_root / DEPLOYED_REL
        self.assertTrue(deployed.is_file(), f"§S4: the install did not deploy {DEPLOYED_REL}")
        self.assertEqual(deployed.read_bytes(), SKILL_MD.read_bytes())
        entries = [f for f in self.install_toml().get("files", []) if f["path"] == DEPLOYED_REL]
        self.assertEqual(len(entries), 1, f"install.toml records {DEPLOYED_REL} {len(entries)} times")
        self.assertEqual(entries[0]["sha256"], hashlib.sha256(SKILL_MD.read_bytes()).hexdigest())

    def test_install_with_no_stack_filter_deploys_and_records_gap_analysis(self):
        self.assert_installed(self.run_installer())
        self._assert_gap_analysis_deployed_and_recorded()

    def test_single_stack_install_deploys_gap_analysis_while_scoping_stack_bundles_out(self):
        self.assert_installed(self.run_installer("--stacks", "bun"))
        bundles = self.deployed_bundles()
        # control: the selection scoped the stack bundles, so gap-analysis is not stack-scoped
        self.assertIn("crucible-report-bun", bundles)
        self.assertNotIn("crucible-report-rust", bundles)
        self.assertNotIn("code-health", bundles)
        self.assertIn(BUNDLE, bundles)
        self._assert_gap_analysis_deployed_and_recorded()


if __name__ == "__main__":
    unittest.main()
