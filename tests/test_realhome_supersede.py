"""RED-phase tests for CR-MDB-016 cycle C2 (Sec4 -- real-home supersede).

These tests probe the ACTUAL machine home (``~/.claude``, ``~/.agents``),
never a sandboxed target root -- that is why they carry a durability gate:
every test in this module SKIPS unless the environment variable
``MODELB_REALHOME_GATE=1`` is set. Without the gate the suite stays green
on any machine/CI that has no deployed real-home copy at all (a fresh
checkout, a CI runner, a different developer's machine). The gate is
turned on explicitly for this cycle's RED/GREEN/VERIFY runs against THIS
machine's real home, per the CR-MDB-016 Sec4 dispatch.

Written BEFORE Sec4's installer run against the real home lands:
  - AC5-supersede: ``~/.claude/skills/crucible`` (today a plain directory,
    not yet a symlink into the ``.agents`` store) still carries 12
    ``WORKFLOW_CYCLE_ID`` occurrences (SKILL.md + 5 stack references),
    still asserts the phantom "there is NO separate heartbeat endpoint"
    claim instead of documenting the live ``/api/v2/agents/heartbeat``
    v2-form-only contract, and has no ``references/arduino.md`` -- these
    assertions fail cleanly today.
  - AC5-bundles: none of the 7 handover bundles exist yet under
    ``~/.agents/skills/`` or the ``~/.claude/skills`` symlink layer --
    fails cleanly today.
  - AC5-scripts: ``~/.claude/scripts/`` still carries 6 ``*crucible*``
    client mirrors (``arduino-crucible.py``, ``bun-crucible.py``,
    ``hw-crucible.py``, ``mvn-crucible.py``, ``python-crucible.py``,
    ``rust-crucible.py``), and 25 files under ``~/.claude/agents/``,
    ``~/.claude/hooks/``, ``~/.claude/memory/`` still hold live
    ``~/.claude/scripts/<...>crucible<...>`` references -- fails cleanly
    today.
  - AC6 precondition probe: ``chezmoi status`` (read-only) is expected to
    exit 0 already today -- this one MAY pass before the deploy; it is
    the invariant Sec4's deploy must not break.
  - CR-MDB-022 Sec6/AC3 EXTENSION: the same retired-referencer gate, in the
    same shape, for the eight adopted tool scripts. CR-MDB-022 moved them
    into this repo's ``scripts/`` asset class, deployed to
    ``~/.agents/scripts/``, so a live ``~/.claude/scripts/<tool>`` reference
    is now the same defect class as a ``*crucible*`` one. FILES under
    ``~/.claude/scripts/`` are NOT asserted absent for the eight -- that tree
    is chezmoi-managed and this repo never writes or deletes there; only
    REFERENCES to it are gated.

Stdlib only: unittest + subprocess + re + os + pathlib. No SUT import --
this cycle's Sec4 deliverable is a real-home installer run, not a Python
module under this repo.
"""

import os
import re
import subprocess
import unittest
from pathlib import Path

GATE_ENV_VAR = "MODELB_REALHOME_GATE"
GATE_ENABLED = os.environ.get(GATE_ENV_VAR) == "1"
_SKIP_REASON = (
    f"{GATE_ENV_VAR} not set -- real-home Sec4 supersede tests are "
    f"skipped by default so the suite stays green on machines/CI without "
    f"the deployed home (set {GATE_ENV_VAR}=1 to run them against THIS "
    f"machine's real home)"
)

HOME = Path.home()
CLAUDE_SKILLS_DIR = HOME / ".claude" / "skills"
CLAUDE_SCRIPTS_DIR = HOME / ".claude" / "scripts"
AGENTS_STORE_SKILLS_DIR = HOME / ".agents" / "skills"
REFERENCER_DIRS = (
    HOME / ".claude" / "agents",
    HOME / ".claude" / "hooks",
    HOME / ".claude" / "memory",
)

DEPLOYED_CRUCIBLE_SKILL_DIR = CLAUDE_SKILLS_DIR / "crucible"
DEPLOYED_CRUCIBLE_SKILL_MD = DEPLOYED_CRUCIBLE_SKILL_DIR / "SKILL.md"
DEPLOYED_CRUCIBLE_REFERENCES_DIR = DEPLOYED_CRUCIBLE_SKILL_DIR / "references"

IMPORTED_BUNDLE_NAMES = (
    "crucible-register",
    "crucible-report-arduino",
    "crucible-report-bun",
    "crucible-report-java",
    "crucible-report-python",
    "crucible-report-rust",
    "crucible-report-vscode",
)

# Live-reference pattern: a path token that names ~/.claude/scripts/ (the
# retired mirror location) followed by a *crucible* filename, .py or .sh.
# Deliberately narrow -- prose that merely NAMES a crucible script without
# the scripts/ path prefix (e.g. "the hw-crucible.py pattern") is not a
# live reference and must not be flagged.
LIVE_SCRIPTS_CRUCIBLE_REF_RE = re.compile(
    r"\.claude/scripts/[\w-]*crucible[\w-]*\.(?:py|sh)"
)

# CR-MDB-022 Sec1 -- the eight adopted tool scripts (7 hand-maintained +
# generated toon.py), owned by roundhouse/model-b and deployed to
# ~/.agents/scripts/. Same defect class as the *crucible* mirrors above:
# ~/.claude/scripts/ is chezmoi-managed, so any reference pointing there is
# reverted out from under the referencer on the next `chezmoi apply`.
ADOPTED_TOOL_NAMES = (
    "worktree-flow.py",
    "schedule_db.py",
    "skill-release-gate.py",
    "rust-code-health.py",
    "rust-crate-map.py",
    "rust-dead-scan.py",
    "gate-lock.sh",
    "toon.py",
)
AGENTS_STORE_SCRIPTS_DIR = HOME / ".agents" / "scripts"

# Same narrowness as LIVE_SCRIPTS_CRUCIBLE_REF_RE: the retired path prefix
# must be present, so prose that merely NAMES a tool is not flagged.
LIVE_SCRIPTS_TOOL_REF_RE = re.compile(
    r"\.claude/scripts/(?:"
    + "|".join(re.escape(name) for name in ADOPTED_TOOL_NAMES)
    + r")"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _resolve_deployed_skill_dir(name: str) -> Path:
    """Resolve the deployed location of skill ``name``, following the
    ``~/.claude/skills/<name>`` symlink into the ``.agents`` store when
    present (deploy.py's model: store copy + per-harness symlink)."""
    symlinked = CLAUDE_SKILLS_DIR / name
    return symlinked.resolve()


def _bundle_is_deployed(name: str) -> bool:
    """A bundle counts as deployed if EITHER layer deploy.py can produce
    resolves to a real SKILL.md: the harness-neutral store
    (~/.agents/skills/<name>/SKILL.md) OR the ~/.claude/skills symlink
    layer resolved through any symlink it may be."""
    store_skill_md = AGENTS_STORE_SKILLS_DIR / name / "SKILL.md"
    if store_skill_md.is_file():
        return True
    resolved = _resolve_deployed_skill_dir(name)
    return (resolved / "SKILL.md").is_file()


def _find_live_scripts_referencers(pattern) -> dict:
    """Grep (read-only) the three referencer trees for live
    ``~/.claude/scripts/`` mentions matching ``pattern``. Returns
    {relative_path: [line_no, ...]}."""
    offending = {}
    for base in REFERENCER_DIRS:
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            try:
                content = _read(p)
            except OSError:
                continue
            hit_lines = [
                line_no
                for line_no, line in enumerate(content.splitlines(), start=1)
                if pattern.search(line)
            ]
            if hit_lines:
                offending[str(p)] = hit_lines
    return offending


def _find_live_scripts_crucible_referencers() -> dict:
    """Live ``~/.claude/scripts/<...>crucible<...>`` referencers."""
    return _find_live_scripts_referencers(LIVE_SCRIPTS_CRUCIBLE_REF_RE)


def _find_live_scripts_tool_referencers() -> dict:
    """Live ``~/.claude/scripts/<one of the eight adopted tools>``
    referencers (CR-MDB-022 Sec6/AC3)."""
    return _find_live_scripts_referencers(LIVE_SCRIPTS_TOOL_REF_RE)


def _find_crucible_scripts() -> list:
    if not CLAUDE_SCRIPTS_DIR.is_dir():
        return []
    return sorted(
        str(p) for p in CLAUDE_SCRIPTS_DIR.rglob("*")
        if p.is_file() and "crucible" in p.name.lower()
    )


@unittest.skipUnless(GATE_ENABLED, _SKIP_REASON)
class DeployedCrucibleSkillSupersedeTest(unittest.TestCase):
    """AC5 (supersede) -- the deployed ``~/.claude/skills/crucible`` copy
    (may be a plain dir today, a symlink into the ``.agents`` store post
    Sec4 deploy -- resolved either way) must carry ZERO
    ``WORKFLOW_CYCLE_ID`` occurrences across SKILL.md + references/, must
    document the live ``/api/v2/agents/heartbeat`` v2-form-only contract
    (replacing the phantom "no separate heartbeat endpoint" claim, same
    composed-pattern style as test_skills_handover.py's AC8 checks), and
    must ship a ``references/arduino.md`` router."""

    def test_deployed_skill_dir_resolves_to_existing_directory(self):
        resolved = _resolve_deployed_skill_dir("crucible")
        self.assertTrue(
            resolved.is_dir(),
            f"Sec4 must deploy a resolvable ~/.claude/skills/crucible "
            f"(plain dir or symlink into ~/.agents/skills/crucible); "
            f"resolved to {resolved} which is not a directory",
        )

    def test_zero_workflow_cycle_id_occurrences_in_deployed_skill(self):
        resolved = _resolve_deployed_skill_dir("crucible")
        if not resolved.is_dir():
            self.fail(
                f"Sec4 must deploy ~/.claude/skills/crucible before this "
                f"invariant is checkable; resolved dir {resolved} missing"
            )
        offending = {}
        for p in sorted(resolved.rglob("*")):
            if not p.is_file():
                continue
            try:
                content = _read(p)
            except OSError:
                continue
            count = content.count("WORKFLOW_CYCLE_ID")
            if count:
                offending[str(p)] = count
        # EXACT bound -- zero occurrences anywhere in the deployed skill
        # (SKILL.md + references/); today this is 12 (SKILL.md + 5 stack
        # references), so Sec4 must supersede every one of them.
        self.assertEqual(
            offending, {},
            f"Sec4 must supersede ~/.claude/skills/crucible with content "
            f"carrying ZERO 'WORKFLOW_CYCLE_ID' occurrences; found "
            f"(today's 12 stale hits across SKILL.md + 5 references/*.md "
            f"are the ones that must be gone): {offending}",
        )

    def test_deployed_skill_md_documents_v2_heartbeat_form_and_drops_phantom_claim(self):
        resolved = _resolve_deployed_skill_dir("crucible")
        skill_md = resolved / "SKILL.md"
        if not skill_md.is_file():
            self.fail(
                f"Sec4 must deploy {skill_md} before the v2 touch-contract "
                f"invariant is checkable"
            )
        content = _read(skill_md)
        # POSITIVE -- the live v2 touch surface is documented.
        self.assertIn(
            "/api/v2/agents/heartbeat", content,
            f"Sec4 must supersede {skill_md} to document the "
            f"'/api/v2/agents/heartbeat' v2 touch surface (currently "
            f"missing from the deployed copy)",
        )
        # NEGATIVE -- the stale phantom claim must be gone.
        self.assertNotIn(
            "there is NO separate heartbeat endpoint", content,
            f"Sec4 must remove the stale 'there is NO separate heartbeat "
            f"endpoint' claim from {skill_md} -- the v2 upsert handler "
            f"makes it false",
        )
        # EXACT bound -- every '/agents/heartbeat' hit in the deployed
        # SKILL.md must be the v2 form -- no bare/phantom-form hits.
        phantom_endpoint = "/agents" + "/heartbeat"
        live_endpoint = "/api/v2" + phantom_endpoint
        non_v2_hits = [
            line_no
            for line_no, line in enumerate(content.splitlines(), start=1)
            if phantom_endpoint in line and live_endpoint not in line
        ]
        self.assertEqual(
            non_v2_hits, [],
            f"expected every '{phantom_endpoint}' hit in {skill_md} to be "
            f"the '{live_endpoint}' v2 form; non-v2 hit line(s): {non_v2_hits}",
        )
        # EXACT bound -- zero references to the un-adopted shell helper.
        heartbeat_sh_count = content.count("heartbeat" + ".sh")
        self.assertEqual(
            heartbeat_sh_count, 0,
            f"expected zero heartbeat-helper-script occurrences in "
            f"{skill_md}, found {heartbeat_sh_count}",
        )

    def test_deployed_arduino_reference_router_exists(self):
        resolved = _resolve_deployed_skill_dir("crucible")
        arduino_ref = resolved / "references" / "arduino.md"
        self.assertTrue(
            arduino_ref.is_file(),
            f"Sec4 must deploy {arduino_ref} (arduino router parity, "
            f"AC5/AC7) -- missing from the real-home copy today",
        )


@unittest.skipUnless(GATE_ENABLED, _SKIP_REASON)
class DeployedHandoverBundlesTest(unittest.TestCase):
    """AC5 (bundles) -- the 7 handover bundles are present in the deployed
    skill set (store copy under ~/.agents/skills/<name>/SKILL.md and/or
    the ~/.claude/skills symlink layer, per deploy.py's model); NO
    deployed agent-protocol skill exists in either layer."""

    def test_all_seven_handover_bundles_deployed(self):
        missing = [
            name for name in IMPORTED_BUNDLE_NAMES
            if not _bundle_is_deployed(name)
        ]
        # POSITIVE/EXACT -- all 7 bundles resolve to a real SKILL.md in
        # at least one deploy layer.
        self.assertEqual(
            missing, [],
            f"Sec4 must deploy all 7 handover bundles {IMPORTED_BUNDLE_NAMES} "
            f"(store copy under {AGENTS_STORE_SKILLS_DIR}/<name>/SKILL.md "
            f"and/or the {CLAUDE_SKILLS_DIR} symlink layer); missing today: "
            f"{missing}",
        )

    def test_no_deployed_agent_protocol_skill_in_either_layer(self):
        store_present = (AGENTS_STORE_SKILLS_DIR / "agent-protocol" / "SKILL.md").is_file()
        symlink_present = (
            CLAUDE_SKILLS_DIR / "agent-protocol"
        ).exists()
        # NEGATIVE -- Option B stands: agent-protocol is absorbed, never
        # deployed standalone in either the store or the symlink layer.
        self.assertFalse(
            store_present or symlink_present,
            f"agent-protocol must NOT exist as a deployed skill in either "
            f"{AGENTS_STORE_SKILLS_DIR}/agent-protocol or "
            f"{CLAUDE_SKILLS_DIR}/agent-protocol -- Option B absorbs it "
            f"into crucible, it is never deployed standalone "
            f"(store_present={store_present}, symlink_present={symlink_present})",
        )


@unittest.skipUnless(GATE_ENABLED, _SKIP_REASON)
class RetiredScriptMirrorsTest(unittest.TestCase):
    """AC5 (scripts) -- zero ``*crucible*`` client scripts remain under
    ``~/.claude/scripts/``, and zero LIVE references to
    ``~/.claude/scripts/<anything>crucible`` remain from files under
    ``~/.claude/agents/``, ``~/.claude/hooks/``, ``~/.claude/memory/``
    (read-only grep). CR-MDB-022 Sec6/AC3 extends the referencer half, in
    the same shape, to the eight adopted tool scripts."""

    def test_zero_crucible_named_scripts_remain_under_claude_scripts(self):
        offending = _find_crucible_scripts()
        # EXACT bound -- today 6 stale mirrors exist (arduino-, bun-,
        # hw-, mvn-, python-, rust-crucible.py); Sec4 must retire all of
        # them (chezmoi destroy/forget) so this is empty.
        self.assertEqual(
            offending, [],
            f"Sec4 must retire every '*crucible*' client script under "
            f"{CLAUDE_SCRIPTS_DIR} (via chezmoi destroy/forget, never "
            f"plain rm); still present today: {offending}",
        )

    def test_zero_live_referencers_to_retired_scripts_crucible_paths(self):
        offending = _find_live_scripts_crucible_referencers()
        # EXACT bound -- every former referencer under agents/hooks/memory
        # must be repointed to the ~/Documents/data_projects/crucible/
        # clients/ paths (011 close-out item (b)); today 25 files still
        # hold the stale ~/.claude/scripts/<...>crucible<...> reference.
        self.assertEqual(
            offending, {},
            f"Sec4 must repoint every referencer under "
            f"{[str(d) for d in REFERENCER_DIRS]} away from the retired "
            f"'~/.claude/scripts/<...>crucible<...>' paths to the "
            f"crucible-repo client paths "
            f"(~/Documents/data_projects/crucible/clients/); still "
            f"live today (file -> offending line numbers): {offending}",
        )

    def test_zero_live_referencers_to_retired_scripts_tool_paths(self):
        """CR-MDB-022 Sec6/AC3 -- the same gate for the eight adopted tools.

        Only REFERENCES are asserted, never file absence: the eight are what
        CR-MDB-022 Sec1 adopted FROM this tree, ``~/.claude/scripts/`` is
        chezmoi-managed, and no Model B code path writes or deletes there.
        """
        offending = _find_live_scripts_tool_referencers()
        self.assertEqual(
            offending, {},
            f"CR-MDB-022 Sec6 must repoint every referencer under "
            f"{[str(d) for d in REFERENCER_DIRS]} away from "
            f"'~/.claude/scripts/<tool>' for the eight adopted names "
            f"{list(ADOPTED_TOOL_NAMES)} to the deployed store "
            f"({AGENTS_STORE_SCRIPTS_DIR}); {CLAUDE_SCRIPTS_DIR} is "
            f"chezmoi-managed, so a reference there is reverted out from "
            f"under the referencer on the next `chezmoi apply`. Still live "
            f"(file -> offending line numbers): {offending}",
        )


@unittest.skipUnless(GATE_ENABLED, _SKIP_REASON)
class ChezmoiRoundTripPreconditionTest(unittest.TestCase):
    """AC6 pre-condition probe -- ``chezmoi status`` (read-only) must
    exit 0 both BEFORE and AFTER the Sec4 deploy; this test asserts the
    invariant that Sec4's retirement/supersede work must not break. It
    may already PASS today -- that is expected; it exists to catch a
    REGRESSION Sec4 could introduce (a broken chezmoi source state), not
    to fail cleanly pre-deploy."""

    def test_chezmoi_status_exits_zero(self):
        try:
            result = subprocess.run(
                ["chezmoi", "status"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.fail(f"'chezmoi status' could not be run: {exc}")
        # POSITIVE/EXACT -- read-only chezmoi status must exit clean (0);
        # this is the round-trip invariant Sec4's retirements must not
        # break, per AC6.
        self.assertEqual(
            result.returncode, 0,
            f"'chezmoi status' must exit 0 (read-only precondition for "
            f"AC6's post-Sec4 round-trip check); got returncode="
            f"{result.returncode}, stdout={result.stdout!r}, "
            f"stderr={result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
