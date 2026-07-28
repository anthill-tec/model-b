"""RED-phase tests for CR-MDB-008 (agent generator: templates + stack params
+ drift gate).

These tests assert the acceptance criteria of CR-MDB-008 SS2-SS4 against the
generator sources under <repo>/generator/, the archived pre-generation
originals under <repo>/archive/wave3/agents/, and the LIVE ~/.claude/agents/
tree on this machine. They are written before the GREEN-phase work (the 4
role templates, the 4 stack TOML files, build.py, the wave-3 archive, and
the regenerated live agent files) lands, so most of them are expected to
FAIL against the current (pre-CR-MDB-008) state. The suite overall must be
RED, not necessarily every single test -- some content greps/diffs may
vacuously pass depending on what already happens to be true of the live
tree today (e.g. no agent currently references a retired artifact, and the
13 bespoke agents are currently untouched by this CR) -- that is still
correct behaviour, not a test bug.

CR-MDB-014 §S7 AMENDMENT (sanctioned follow-up, cycle C4): build.py's
generated-output target is superseded from the real ``Path.home() /
".claude" / "agents"`` to the repo-local package asset dir
``<repo>/generator/agents/`` (the ``AGENTS_DIR`` retarget contract pinned in
``tests/test_installer_assets.py``). Every assertion below that checks
build.py's OWN generated-output location (the mutation-detection probe, the
frontmatter/description/citation/anchor content checks, and the
retired-artifact grep gate) now targets ``GENERATOR_AGENTS_DIR`` instead of
the live ``AGENTS_DIR``. The 13 BESPOKE defs were never part of build.py's
target list and still live ONLY in the real deployed ``~/.claude/agents/``
tree -- ``BespokeUntouchedS4Test`` originally verified this via live
``chezmoi diff`` against ``AGENTS_DIR``. A new
``DeployedAgentsConsumerConstraintTest`` (§S7 addition) pins the
opposite-direction guarantee: the DEPLOYED ``~/.claude/agents/`` tree still
carries the 16 generated files (existence only, no content coupling) until
the installer (CR-MDB-014) actually redeploys them there -- mirroring the
CR-MDB-011 AC6 "already-deployed content must remain reachable" pattern.

CR-MDB-016 AMENDMENT (skills-handover branch; orchestrator-approved user
directive: the Model B system carries NO chezmoi dependencies -- Model B
tests must not introspect the user's live chezmoi tree/history): two
``BespokeUntouchedS4Test`` methods whose MECHANISM shelled out to
``chezmoi diff`` on live agent files, and to the chezmoi SOURCE repo's last
git commit, were flapping on unrelated user dotfile activity. The class is
re-mechanized to pin the same CR-MDB-008 AC (the generator never
writes/overwrites a bespoke agent def) with repo-side-only assertions
driven from the generator's own inputs/outputs (``generator/`` templates +
stacks + ``build.py``'s emitted-name set), built into an isolated tmp
output dir -- no ``chezmoi`` invocation and no read of the live
``~/.claude`` tree anywhere in the class.

Stdlib only (unittest + subprocess + pathlib + shutil + sys + tomllib). No
production-module import: build.py is invoked as a subprocess per the CR's
own mechanics (`python3 generator/build.py --check`), matching how the spec
itself describes driving the gate.
"""

import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_DIR = Path.home() / ".claude"
# The real DEPLOYED tree: still used by BespokeUntouchedS4Test (the 13
# bespoke defs never move) and by the new §S7 consumer-constraint test.
AGENTS_DIR = CLAUDE_DIR / "agents"

GENERATOR_DIR = REPO_ROOT / "generator"
TEMPLATES_DIR = GENERATOR_DIR / "templates"
STACKS_DIR = GENERATOR_DIR / "stacks"
BUILD_PY = GENERATOR_DIR / "build.py"
# CR-MDB-014 §S7 retarget contract: build.py's OWN generated-output dir,
# superseding the live AGENTS_DIR as the target for content/drift checks.
GENERATOR_AGENTS_DIR = GENERATOR_DIR / "agents"

ARCHIVE_WAVE3_AGENTS = REPO_ROOT / "archive" / "wave3" / "agents"

STACKS = ["arduino", "bun", "python", "quarkus"]
ROLES = ["red", "green", "verify", "fix"]

# The 16 small-stack agent files build.py must own (never the 13 bespoke ones).
TARGET_AGENT_NAMES = [f"{stack}-{role}-agent.md" for stack in STACKS for role in ROLES]

# The 13 bespoke defs build.py must NEVER touch (rust x4, vscode x4,
# electronics x4, inbox-analyst).
BESPOKE_AGENT_NAMES = [
    "rust-red-agent.md",
    "rust-green-agent.md",
    "rust-verify-agent.md",
    "rust-fix-agent.md",
    "vscode-red-agent.md",
    "vscode-green-agent.md",
    "vscode-verify-agent.md",
    "vscode-fix-agent.md",
    "electronics-bench-test-engineer.md",
    "electronics-board-designer.md",
    "electronics-production-engineer.md",
    "electronics-quality-engineer.md",
    "inbox-analyst.md",
]

# Per-stack mechanic anchor that must survive distillation into every one of
# that stack's 4 generated agent files.
STACK_ANCHORS = {
    "python": "--tests",
    "bun": "bun test",
    "quarkus": "mvn",
    "arduino": "arduino-cli",
}

# The AC names this exact grep invocation verbatim (S4 bullet 3).
RETIRED_ARTIFACT_PATTERN = (
    r"agent-baseline\|crucible-report\|orchestration-universal\|"
    r"bun-red-testing\|quarkus-regression-testing"
)


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


class GeneratorSourcesS2Test(unittest.TestCase):
    """SS2 -- generator/templates/{red,green,verify,fix}.md.tmpl +
    generator/stacks/{arduino,bun,python,quarkus}.toml exist; each TOML
    parses via tomllib and contains keys display_name, test_command,
    crucible_reference."""

    def test_s2_all_four_role_templates_exist(self):
        missing = [
            role for role in ROLES
            if not (TEMPLATES_DIR / f"{role}.md.tmpl").is_file()
        ]
        # POSITIVE/bound -- exactly the 4 role templates, none missing.
        self.assertEqual(
            missing, [],
            f"missing role templates under {TEMPLATES_DIR}: {missing}",
        )

    def test_s2_all_four_stack_toml_files_exist(self):
        missing = [
            stack for stack in STACKS
            if not (STACKS_DIR / f"{stack}.toml").is_file()
        ]
        # POSITIVE/bound -- exactly the 4 stack TOML files, none missing.
        self.assertEqual(
            missing, [],
            f"missing stack TOML files under {STACKS_DIR}: {missing}",
        )

    def test_s2_each_stack_toml_parses_via_tomllib_with_required_keys(self):
        required_keys = {"display_name", "test_command", "crucible_reference"}
        failures = []
        for stack in STACKS:
            path = STACKS_DIR / f"{stack}.toml"
            if not path.is_file():
                failures.append(f"{stack}: {path} does not exist")
                continue
            try:
                with path.open("rb") as fh:
                    data = tomllib.load(fh)
            except tomllib.TOMLDecodeError as exc:
                failures.append(f"{stack}: {path} failed to parse via tomllib: {exc}")
                continue
            missing_keys = required_keys - set(data.keys())
            if missing_keys:
                failures.append(f"{stack}: {path} missing keys {sorted(missing_keys)}")
                continue
            for key in required_keys:
                value = data.get(key)
                if not isinstance(value, str) or not value.strip():
                    failures.append(
                        f"{stack}: {path} key {key!r} must be a non-empty string, got {value!r}"
                    )
        # POSITIVE -- every stack TOML parses and carries all 3 required keys
        # with real (non-empty) values.
        self.assertEqual(failures, [], "\n".join(failures))


class BuildPyIdempotenceS3Test(unittest.TestCase):
    """SS3 -- generator/build.py (stdlib only): --check re-renders to memory
    and diffs against live -- exit 0 clean / exit 1 listing drifted files;
    the 13 bespoke defs are never in the target list."""

    def test_s3_check_flag_exits_zero_when_tree_in_sync(self):
        # build.py must exist before we can even attempt to drive --check --
        # fail cleanly here rather than let subprocess raise FileNotFoundError.
        self.assertTrue(BUILD_PY.is_file(), f"{BUILD_PY} must exist to run --check")
        result = subprocess.run(
            [sys.executable, str(BUILD_PY), "--check"],
            capture_output=True, text=True, timeout=60,
        )
        # POSITIVE/EXACT -- a synced tree (post-SS4 regeneration) must exit 0.
        self.assertEqual(
            result.returncode, 0,
            "generator/build.py --check must exit 0 when the live tree matches "
            f"regeneration (idempotence), got rc={result.returncode}\n"
            f"stdout:\n{result.stdout[:2000]}\nstderr:\n{result.stderr[:2000]}",
        )

    def test_s3_check_flag_exits_one_and_names_the_mutated_file(self):
        self.assertTrue(BUILD_PY.is_file(), f"{BUILD_PY} must exist to run --check")
        target = GENERATOR_AGENTS_DIR / "python-red-agent.md"
        self.assertTrue(target.is_file(), f"{target} must exist to be mutated")
        original_bytes = target.read_bytes()
        try:
            with target.open("a", encoding="utf-8") as fh:
                fh.write("\n<!-- CR-MDB-008 drift-marker (test-injected) -->\n")
            result = subprocess.run(
                [sys.executable, str(BUILD_PY), "--check"],
                capture_output=True, text=True, timeout=60,
            )
            # EXACT -- a drifted live file must be reported as exit 1.
            self.assertEqual(
                result.returncode, 1,
                "generator/build.py --check must exit 1 when a generated live "
                f"file has been mutated, got rc={result.returncode}\n"
                f"stdout:\n{result.stdout[:2000]}\nstderr:\n{result.stderr[:2000]}",
            )
            # POSITIVE -- the mutated file's name must be named in the output.
            combined_output = result.stdout + result.stderr
            self.assertIn(
                target.name, combined_output,
                f"--check output must name the drifted file {target.name!r}, "
                f"got:\n{combined_output[:2000]}",
            )
        finally:
            # Restore regardless of pass/fail -- never leave the live agent
            # tree mutated by this test.
            target.write_bytes(original_bytes)
        # NEGATIVE/bound -- after restoration the file is back to its
        # original content (no residual drift left behind by the test itself).
        self.assertEqual(
            target.read_bytes(), original_bytes,
            f"{target} must be restored to its original content after the test",
        )

    def test_s3_build_py_target_list_is_exactly_the_16_small_stack_files(self):
        self.assertTrue(BUILD_PY.is_file(), f"{BUILD_PY} must exist to run --list")
        result = subprocess.run(
            [sys.executable, str(BUILD_PY), "--list"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(
            result.returncode, 0,
            f"generator/build.py --list must exit 0, got rc={result.returncode}\n"
            f"stderr:\n{result.stderr[:2000]}",
        )
        listed_names = {
            Path(line.strip()).name
            for line in result.stdout.splitlines()
            if line.strip()
        }
        expected_names = set(TARGET_AGENT_NAMES)
        # POSITIVE/EXACT -- the target list is exactly the 16 small-stack files.
        self.assertEqual(
            listed_names, expected_names,
            f"--list must report exactly the 16 small-stack agent files, "
            f"got {sorted(listed_names)}, expected {sorted(expected_names)}",
        )
        # NEGATIVE -- zero bespoke names present in the target list.
        bespoke_overlap = listed_names & set(BESPOKE_AGENT_NAMES)
        self.assertEqual(
            bespoke_overlap, set(),
            f"--list must never include a bespoke agent name, found: {bespoke_overlap}",
        )


class ArchiveOriginalsS4Test(unittest.TestCase):
    """SS4 -- archive the 16 current agent files to
    <repo>/archive/wave3/agents/ (pre-generation originals) before build.py
    overwrites them in place."""

    def test_s4_all_16_pregeneration_originals_archived(self):
        missing = [
            name for name in TARGET_AGENT_NAMES
            if not (ARCHIVE_WAVE3_AGENTS / name).is_file()
        ]
        # POSITIVE/bound -- all 16 originals, none missing.
        self.assertEqual(
            missing, [],
            f"missing archived pre-generation originals under "
            f"{ARCHIVE_WAVE3_AGENTS}: {missing}",
        )
        self.assertEqual(len(TARGET_AGENT_NAMES), 16, "sanity: 4 stacks x 4 roles")


class GeneratedContentRequirementsS4Test(unittest.TestCase):
    """SS4 -- each of the 16 live files: frontmatter name == filename stem;
    non-empty description; cites sub-agent-procedure + the crucible skill;
    contains its stack's mechanic anchor."""

    def test_s4_each_live_agent_frontmatter_name_equals_filename_stem(self):
        failures = []
        for name in TARGET_AGENT_NAMES:
            path = GENERATOR_AGENTS_DIR / name
            if not path.is_file():
                failures.append(f"{name}: file does not exist at {path}")
                continue
            frontmatter, _body = _split_frontmatter(_read(path))
            name_lines = [
                ln for ln in frontmatter.splitlines() if ln.strip().startswith("name:")
            ]
            if len(name_lines) != 1:
                failures.append(
                    f"{name}: expected exactly one 'name:' frontmatter key, found {name_lines}"
                )
                continue
            value = name_lines[0].split(":", 1)[1].strip()
            expected_stem = Path(name).stem
            if value != expected_stem:
                failures.append(
                    f"{name}: frontmatter name={value!r} must equal filename stem {expected_stem!r}"
                )
        # POSITIVE/EXACT -- every one of the 16 files has name == stem.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s4_each_live_agent_description_non_empty(self):
        failures = []
        for name in TARGET_AGENT_NAMES:
            path = GENERATOR_AGENTS_DIR / name
            if not path.is_file():
                failures.append(f"{name}: file does not exist at {path}")
                continue
            frontmatter, _body = _split_frontmatter(_read(path))
            description_lines = [
                ln for ln in frontmatter.splitlines()
                if ln.strip().startswith("description:")
            ]
            if len(description_lines) != 1:
                failures.append(
                    f"{name}: expected exactly one 'description:' frontmatter key, "
                    f"found {description_lines}"
                )
                continue
            description = description_lines[0].split(":", 1)[1].strip()
            if not description:
                failures.append(f"{name}: description: must be non-empty")
        # POSITIVE -- every one of the 16 files has a non-empty description.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s4_each_live_agent_cites_sub_agent_procedure_and_crucible(self):
        failures = []
        for name in TARGET_AGENT_NAMES:
            path = GENERATOR_AGENTS_DIR / name
            if not path.is_file():
                failures.append(f"{name}: file does not exist at {path}")
                continue
            content = _read(path)
            missing_terms = [
                term for term in ("sub-agent-procedure", "crucible")
                if term not in content
            ]
            if missing_terms:
                failures.append(f"{name}: missing required citation terms {missing_terms}")
        # POSITIVE -- every one of the 16 files cites both anchors.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s4_each_live_agent_contains_its_stack_mechanic_anchor(self):
        failures = []
        for stack in STACKS:
            anchor = STACK_ANCHORS[stack]
            for role in ROLES:
                name = f"{stack}-{role}-agent.md"
                path = GENERATOR_AGENTS_DIR / name
                if not path.is_file():
                    failures.append(f"{name}: file does not exist at {path}")
                    continue
                content = _read(path)
                if anchor not in content:
                    failures.append(
                        f"{name}: must contain stack anchor {anchor!r} (stack={stack})"
                    )
        # POSITIVE -- every one of the 16 files retains its stack's mechanic anchor.
        self.assertEqual(failures, [], "\n".join(failures))


class RetiredArtifactGrepGateS4Test(unittest.TestCase):
    """SS4 -- zero references to retired artifacts (agent-baseline,
    crucible-report, orchestration-universal, bun-red-testing,
    quarkus-regression-testing) anywhere under the generated-output dir
    (CR-MDB-014 §S7: retargeted from ~/.claude/agents/ to
    GENERATOR_AGENTS_DIR)."""

    def test_s4_grep_gate_zero_retired_artifact_references(self):
        # A missing retargeted output dir must FAIL loudly -- grep against
        # a non-existent path would otherwise vacuously "pass" with empty
        # stdout, masking the real §S7 retarget gap.
        self.assertTrue(
            GENERATOR_AGENTS_DIR.is_dir(),
            f"{GENERATOR_AGENTS_DIR} must exist (build.py retargeted per "
            f"CR-MDB-014 §S7) before the retired-artifact grep gate means "
            f"anything",
        )
        # EXACT -- the AC names this exact grep invocation verbatim (now
        # against the repo-local retargeted output dir).
        result = subprocess.run(
            ["grep", "-rl", RETIRED_ARTIFACT_PATTERN, str(GENERATOR_AGENTS_DIR)],
            capture_output=True, text=True, timeout=30,
        )
        matched_files = [ln for ln in result.stdout.splitlines() if ln.strip()]
        # NEGATIVE/EXACT bound -- zero files may reference a retired artifact.
        self.assertEqual(
            matched_files, [],
            f"grep gate must return 0 files referencing a retired artifact, "
            f"found: {matched_files}",
        )


class BespokeUntouchedS4Test(unittest.TestCase):
    """SS4 -- CR-MDB-008 AC: the generator never writes/overwrites a bespoke
    agent def. Re-mechanized under CR-MDB-016 (skills-handover branch;
    orchestrator-approved user directive: the Model B system carries NO
    chezmoi dependencies -- Model B tests must not introspect the user's
    chezmoi tree/history). No chezmoi invocation, no read of the live
    ~/.claude tree: this class drives the generator's own inputs/outputs
    (generator/templates + generator/stacks + build.py) end to end into an
    isolated tmp output dir and asserts, from build.py's own emitted-name
    set, that (a) the generated agent name set is exactly the 16 stack x
    role names and (b) none of the 13 bespoke names (rust x4, vscode x4,
    electronics x4, inbox-analyst) is ever in that set or ever written to
    disk by a build."""

    def setUp(self):
        self._tmp_generator_dir = Path(
            tempfile.mkdtemp(prefix="modelb-axi-s4-generator-")
        )
        shutil.copytree(TEMPLATES_DIR, self._tmp_generator_dir / "templates")
        shutil.copytree(STACKS_DIR, self._tmp_generator_dir / "stacks")
        shutil.copy(BUILD_PY, self._tmp_generator_dir / "build.py")
        self._tmp_build_py = self._tmp_generator_dir / "build.py"
        self._tmp_output_agents_dir = self._tmp_generator_dir / "agents"

    def tearDown(self):
        shutil.rmtree(self._tmp_generator_dir, ignore_errors=True)

    def _run_isolated_build(self):
        result = subprocess.run(
            [sys.executable, str(self._tmp_build_py), "build"],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(
            result.returncode, 0,
            f"an isolated `build.py build` (repo-side inputs, tmp output "
            f"dir) must exit 0, got rc={result.returncode}\n"
            f"stdout:\n{result.stdout[:2000]}\nstderr:\n{result.stderr[:2000]}",
        )
        return result

    def test_s4_isolated_build_writes_exactly_the_16_target_files(self):
        self._run_isolated_build()
        self.assertTrue(
            self._tmp_output_agents_dir.is_dir(),
            f"{self._tmp_output_agents_dir} must be created by the build",
        )
        written_names = {
            p.name for p in self._tmp_output_agents_dir.iterdir() if p.is_file()
        }
        expected_names = set(TARGET_AGENT_NAMES)
        # POSITIVE/EXACT -- an isolated build's written-file set is exactly
        # the 16 stack x role names, no more and no fewer.
        self.assertEqual(
            written_names, expected_names,
            f"an isolated build must write exactly the 16 small-stack agent "
            f"files, got {sorted(written_names)}, expected "
            f"{sorted(expected_names)}",
        )
        # bound -- exactly 16 files land on disk, nothing extra silently
        # emitted alongside them.
        self.assertEqual(
            len(written_names), 16,
            f"expected exactly 16 written files, got {len(written_names)}",
        )

    def test_s4_isolated_build_never_writes_a_bespoke_agent_file(self):
        self._run_isolated_build()
        written_names = {
            p.name for p in self._tmp_output_agents_dir.iterdir() if p.is_file()
        }
        # NEGATIVE -- none of the 13 bespoke defs is ever written by a build.
        bespoke_overlap = written_names & set(BESPOKE_AGENT_NAMES)
        self.assertEqual(
            bespoke_overlap, set(),
            f"a build must never write a bespoke agent file, found: "
            f"{bespoke_overlap}",
        )


class DeployedAgentsConsumerConstraintTest(unittest.TestCase):
    """CR-MDB-014 §S7 addition -- the opposite-direction guarantee from the
    build.py retarget: the DEPLOYED ~/.claude/agents/ tree still carries
    all 16 generated agent files (existence only, no content coupling --
    they stay live from a prior build run until the installer actually
    redeploys them there). Mirrors the CR-MDB-011 AC6 pattern of pinning
    that already-deployed content remains reachable across a source-side
    reorganisation."""

    def test_s7_deployed_claude_agents_still_contains_sixteen_generated_files(self):
        missing = [
            name for name in TARGET_AGENT_NAMES
            if not (AGENTS_DIR / name).is_file()
        ]
        # POSITIVE/EXACT, existence-only -- all 16 generated files remain
        # reachable at the real deployed location; content is deliberately
        # NOT asserted here (that coupling now lives with GENERATOR_AGENTS_DIR).
        self.assertEqual(
            missing, [],
            f"deployed {AGENTS_DIR} must still contain all 16 generated "
            f"agent files (existence only) until the installer redeploys "
            f"them there; missing: {missing}",
        )


if __name__ == "__main__":
    unittest.main()
