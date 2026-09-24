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

CR-MDB-022 §S2 AMENDMENT (sanctioned follow-up, cycle C2 FIX): build.py
gained a SECOND target class -- the generated TOON codec copy at its own
``CODEC_TARGET`` (``<repo>/scripts/toon.py``), rendered from ``CODEC_SOURCE``
(``<repo>/modelb_axi/toon.py``) and drift-gated by the SAME ``--check`` gate
(the CR: "inventing a second gate binary would create a parallel
convention"). Three assertions below encoded the now-superseded "exactly 16
targets, all of them under generator/agents/" contract: the ``--list``
target-set pin and both ``BespokeUntouchedS4Test`` isolated-build pins. They
are retargeted to the generator's REAL target set -- the 16 stack x role
agent definitions PLUS that one codec -- named from build.py's own
constants, so a 17th stray target, a missing target or a relocated one
still fails the gate. The method names are kept unchanged (they are cited
by name in the sanctioning FIX dispatch); only the bodies retarget.

CR-MDB-024 \u00a7S1/\u00a7S2 AMENDMENT (sanctioned follow-up, cycle C1 RED): a fifth
stack, ``rust``, joins the generator's own target census (``generator/agents/
rust-{red,green,verify,fix}-agent.md``), widening the SMALL-STACK build/list/
check/content/bespoke gates from 16 to 20 targets and dropping the 4 rust
names out of the 13-strong bespoke list (13 -> 9 at C1; VS Code's four +
electronics x4 + inbox-analyst stayed bespoke then -- CR-MDB-024 \u00a7S3, cycle
C2, narrows it further to 5; see the \u00a7S3 amendment below). Two pins are DELIBERATELY left untouched at their ORIGINAL 16/four-
stack semantics because they assert real machine/repo state this CR does not
touch: ``ArchiveOriginalsS4Test`` (the pre-CR-MDB-008 archive under
``archive/wave3/agents/`` never gained rust originals -- they were never
archived there) and ``DeployedAgentsConsumerConstraintTest`` (the real
deployed ``~/.claude/agents/`` tree never carried the rust definitions --
CR-MDB-024's Context section: they live at ``~/.pi/agent/agents/``, and its
Non-goals rule out any deployment from this CR). Migrating either to the
widened 20-name set would manufacture a RED for the wrong reason -- a gap
this CR does not create and is not asked to close. A new module-level
``TARGET_AGENT_NAMES_WITH_RUST`` (20) is used ONLY by the generator's-own-
census assertions (build/list/check/content/bespoke); ``TARGET_AGENT_NAMES``
(16) keeps its original meaning and its original two consumers.

CR-MDB-024 \u00a7S3 AMENDMENT (this cycle, C2 RED, 2026-09-22 VS Code ruling): the
four VS Code agent names now drop out of the bespoke list too -- an IDE is
not a stack, so they are retired outright rather than adopted as a
generated one. ``BESPOKE_AGENT_NAMES`` narrows from 9 to 5 (electronics x4
+ inbox-analyst). The generator's own target census
(``TARGET_AGENT_NAMES_WITH_RUST``, the build/list/check/content gates) is
UNAFFECTED -- the retired stack was never one of its targets either before
or after -- so only the bespoke-negative assertions move.
``tests/test_ide_overlay_retirement.py`` carries the new module-level gates
this cycle adds (the zero-reference sweep, the skills-src/ bundle census,
the CLI stack-rejection and DN/PRD/README record checks); this file's
amendment is the narrower BESPOKE_AGENT_NAMES migration only.

CR-MDB-032 \u00a7S2 AMENDMENT: ``DeployedAgentsConsumerConstraintTest`` is
deleted -- it asserted the user's real ``~/.claude/agents/`` tree; CR-MDB-025's
rendering tests and the sandboxed installer e2e prove the same. The
``--check`` drift test mutates a TEMP COPY of the build inputs and drives the
copy's build.py, never a tracked file in place. No test here reads the real
home.

Stdlib only (unittest + subprocess + pathlib + shutil + sys + tomllib +
importlib.util). build.py is still driven as a SUBPROCESS for every gate,
per the CR's own mechanics (`python3 generator/build.py --check`), matching
how the spec itself describes driving it; the module is imported (pure --
module level is constant definitions only, no I/O) solely to read its
declared target paths instead of duplicating them as strings here.
"""

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest

from pathlib import Path

from tests._helpers import read_text_lenient as _read

REPO_ROOT = Path(__file__).resolve().parent.parent

GENERATOR_DIR = REPO_ROOT / "generator"
TEMPLATES_DIR = GENERATOR_DIR / "templates"
STACKS_DIR = GENERATOR_DIR / "stacks"
BUILD_PY = GENERATOR_DIR / "build.py"
# CR-MDB-014 §S7 retarget contract: build.py's OWN generated-output dir,
# superseding the live AGENTS_DIR as the target for content/drift checks.
GENERATOR_AGENTS_DIR = GENERATOR_DIR / "agents"

ARCHIVE_WAVE3_AGENTS = REPO_ROOT / "archive" / "wave3" / "agents"

# CR-MDB-029 \u00a7S1: the Pi package README build.py renders from the guide's
# marked regions (orchestrator ruling D3) -- repo-root-relative spec paths.
PI_README_REL = Path("pi-package") / "README.md"
PI_README_TARGET = REPO_ROOT / PI_README_REL
INSTALL_GUIDE_REL = Path("docs") / "install-guide.md"

STACKS = ["arduino", "bun", "python", "quarkus"]
ROLES = ["red", "green", "verify", "fix"]

# CR-MDB-024 \u00a7S2: the generator's own stack set widens to five once
# generator/stacks/rust.toml exists and build.py's STACKS tuple names it.
RUST_STACK = "rust"
GENERATED_STACKS = STACKS + [RUST_STACK]

# The 16 small-stack agent files build.py owned BEFORE CR-MDB-024 -- still
# the correct set for the archive pin and the deployed-tree pin below, which
# assert repo/machine state this CR does not touch.
TARGET_AGENT_NAMES = [f"{stack}-{role}-agent.md" for stack in STACKS for role in ROLES]

# CR-MDB-024 \u00a7S2: the generator's OWN target census after rust joins it --
# 16 legacy + 4 rust = 20. Used only by the build/list/check/content/bespoke
# gates below (never by the archive or deployed-tree pins).
TARGET_AGENT_NAMES_WITH_RUST = [
    f"{stack}-{role}-agent.md" for stack in GENERATED_STACKS for role in ROLES
]

# The 5 bespoke defs build.py must NEVER touch (electronics x4,
# inbox-analyst). CR-MDB-024 \u00a7S2 (2026-09-16 rust ruling) dropped the 4
# rust names that were bespoke before this CR -- rust is now a generated
# stack. CR-MDB-024 \u00a7S3 (2026-09-22 VS Code ruling) drops the four
# VS Code agent names too -- those definitions were retired outright (an
# IDE is not a stack), not adopted as a generated stack, so they leave the
# bespoke list rather than moving to TARGET_AGENT_NAMES_WITH_RUST.
BESPOKE_AGENT_NAMES = [
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
    "rust": "cargo",
}

# The AC names this exact grep invocation verbatim (S4 bullet 3).
RETIRED_ARTIFACT_PATTERN = (
    r"agent-baseline\|crucible-report\|orchestration-universal\|"
    r"bun-red-testing\|quarkus-regression-testing"
)


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


def _load_build_module():
    """Import generator/build.py as a standalone module to read its declared
    target constants (CR-MDB-022 §S2's ``CODEC_SOURCE``/``CODEC_TARGET``, and
    ``AGENTS_DIR``). Pure -- module level is constant definitions only; this
    never invokes cmd_build/cmd_check/cmd_list, which stay subprocess-driven.
    generator/ has no __init__.py, hence importlib.util over a package
    import."""
    spec = importlib.util.spec_from_file_location("_cr_mdb_022_c2_build", BUILD_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _relative_file_set(root: Path) -> set:
    """Every file under ``root``, as a root-relative POSIX path string."""
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


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
        """CR-MDB-032 \u00a7S2: the drift is injected into a TEMP COPY of the
        build inputs (generator/, modelb_axi/ and build.py's other declared
        targets/sources) and the COPY's build.py is driven, so no tracked file
        is ever mutated in place -- build.py resolves every path from its own
        location."""
        self.assertTrue(BUILD_PY.is_file(), f"{BUILD_PY} must exist to run --check")
        tracked = GENERATOR_AGENTS_DIR / "python-red-agent.md"
        self.assertTrue(tracked.is_file(), f"{tracked} must exist to be copied")
        original_bytes = tracked.read_bytes()
        with tempfile.TemporaryDirectory(prefix="mdb-drift-") as tmp:
            copy_root = Path(tmp)
            ignore = shutil.ignore_patterns("__pycache__")
            for rel in ("generator", "modelb_axi"):
                shutil.copytree(REPO_ROOT / rel, copy_root / rel, ignore=ignore)
            for rel in (
                Path("scripts") / "toon.py", INSTALL_GUIDE_REL, PI_README_REL,
            ):
                (copy_root / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(REPO_ROOT / rel, copy_root / rel)
            target = copy_root / "generator" / "agents" / tracked.name
            with target.open("a", encoding="utf-8") as fh:
                fh.write("\n<!-- CR-MDB-008 drift-marker (test-injected) -->\n")
            result = subprocess.run(
                [sys.executable, str(copy_root / "generator" / "build.py"), "--check"],
                capture_output=True, text=True, timeout=60,
            )
        # EXACT -- a drifted generated file must be reported as exit 1.
        self.assertEqual(
            result.returncode, 1,
            "generator/build.py --check must exit 1 when a generated "
            f"file has been mutated, got rc={result.returncode}\n"
            f"stdout:\n{result.stdout[:2000]}\nstderr:\n{result.stderr[:2000]}",
        )
        # POSITIVE -- the mutated file's name must be named in the output.
        combined_output = result.stdout + result.stderr
        self.assertIn(
            tracked.name, combined_output,
            f"--check output must name the drifted file {tracked.name!r}, "
            f"got:\n{combined_output[:2000]}",
        )
        # NEGATIVE/bound -- the tracked file was never touched.
        self.assertEqual(
            tracked.read_bytes(), original_bytes,
            f"{tracked} must be untouched by the drift test",
        )

    def test_s3_build_py_target_list_is_exactly_the_20_generated_files(self):
        """CR-MDB-024 \u00a7S2: renamed from ..._16_small_stack_files (the count is
        no longer 16 once rust joins the generator's own census)."""
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
        listed_paths = [
            Path(line.strip())
            for line in result.stdout.splitlines()
            if line.strip()
        ]
        # CR-MDB-024 \u00a7S2 AMENDMENT -- superseded pin: build.py's own target
        # census widens from 16 to 20 once rust joins it as a fifth stack.
        # The pre-024 form compared against TARGET_AGENT_NAMES (16); the
        # amended form compares against TARGET_AGENT_NAMES_WITH_RUST (20),
        # still named from build.py's own constants for the codec half, so a
        # 21st stray target, a missing target, a relocated target and a
        # renamed directory all still fail here.
        build_module = _load_build_module()
        # CR-MDB-029 \u00a7S1 MIGRATION (orchestrator ruling D3/D6, 2026-09-24):
        # the Pi package README, rendered from the install guide's marked
        # regions, is a target of every invocation like the codec, so --list
        # also prints pi-package/README.md (spec path, not a build.py name).
        expected_paths = {
            GENERATOR_AGENTS_DIR / name for name in TARGET_AGENT_NAMES_WITH_RUST
        } | {build_module.CODEC_TARGET, PI_README_TARGET}
        # POSITIVE/EXACT -- the target list is exactly the 20 small-stack
        # agent files (16 legacy + 4 rust) plus the generated codec.
        self.assertEqual(
            set(listed_paths), expected_paths,
            f"--list must report exactly the 20 small-stack agent files plus "
            f"the generated codec {build_module.CODEC_TARGET}, got "
            f"{sorted(str(p) for p in listed_paths)}, expected "
            f"{sorted(str(p) for p in expected_paths)}",
        )
        # bound -- each target is listed exactly once (no duplicated line
        # hidden by the set comparison above).
        self.assertEqual(
            len(listed_paths), len(expected_paths),
            f"--list must report each target exactly once, got "
            f"{len(listed_paths)} lines for {len(expected_paths)} targets",
        )
        # NEGATIVE -- zero bespoke names present in the target list.
        listed_names = {p.name for p in listed_paths}
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
    """SS4 -- each of the 20 live files (CR-MDB-024 \u00a7S2: 16 legacy + 4 rust):
    frontmatter name == filename stem; non-empty description; cites
    sub-agent-procedure + the crucible skill; contains its stack's mechanic
    anchor."""

    def test_s4_each_live_agent_frontmatter_name_equals_filename_stem(self):
        failures = []
        for name in TARGET_AGENT_NAMES_WITH_RUST:
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
        # POSITIVE/EXACT -- every one of the 20 files has name == stem.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s4_each_live_agent_description_non_empty(self):
        failures = []
        for name in TARGET_AGENT_NAMES_WITH_RUST:
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
        # POSITIVE -- every one of the 20 files has a non-empty description.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s4_each_live_agent_cites_sub_agent_procedure_and_crucible(self):
        failures = []
        for name in TARGET_AGENT_NAMES_WITH_RUST:
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
        # POSITIVE -- every one of the 20 files cites both anchors.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_s4_each_live_agent_contains_its_stack_mechanic_anchor(self):
        failures = []
        for stack in GENERATED_STACKS:
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
        # POSITIVE -- every one of the 20 files retains its stack's mechanic anchor.
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
    (generator/templates + generator/stacks + build.py, plus CR-MDB-022
    §S2's codec source) end to end into an isolated tmp REPO ROOT and
    asserts, from build.py's own declared targets, that (a) the written-file
    set is exactly the generator's declared targets -- the 16 stack x role
    agent definitions plus the one generated codec -- and (b) none of the 13
    bespoke names (rust x4, VS Code x4, electronics x4, inbox-analyst) is ever
    in that set or ever written to disk by a build."""

    def setUp(self):
        # CR-MDB-022 §S2 SANCTIONED AMENDMENT: build.py resolves its REPO_ROOT
        # as generator/'s parent and now also renders CODEC_TARGET from
        # CODEC_SOURCE, so the isolated tree must mirror a whole repo root
        # (generator/ + the codec source + the codec target's committed
        # parent dir), not generator/ alone. Every path below is derived from
        # build.py's own constants, so a relocated target relocates the
        # fixture too instead of silently dropping out of the assertions.
        # CR-MDB-025 §S1 AMENDMENT (this cycle, C1 RED): build.py is expected
        # to gain a cross-package import of modelb_axi.agents; an isolated
        # copy that carries only generator/ (plus the single toon.py codec
        # source file) can no longer resolve that import once GREEN lands
        # it, since build.py's own REPO_ROOT resolves relative to __file__
        # (the tmp copy), not the real repo. The fixture now mirrors the
        # WHOLE modelb_axi/ package into the isolated repo root so a real
        # `from modelb_axi.agents import ...` in build.py keeps resolving
        # inside this isolated build -- a migration of the FIXTURE MECHANISM
        # (kind (2) migration: this class depended on build.py never
        # importing a sibling package, without ever naming that assumption),
        # not of any asserted value.
        self._build_module = _load_build_module()
        origin_root = self._build_module.REPO_ROOT
        agents_rel = self._build_module.AGENTS_DIR.relative_to(origin_root)
        codec_source_rel = self._build_module.CODEC_SOURCE.relative_to(origin_root)
        codec_target_rel = self._build_module.CODEC_TARGET.relative_to(origin_root)
        modelb_axi_pkg_rel = codec_source_rel.parent

        self._tmp_repo_root = Path(tempfile.mkdtemp(prefix="modelb-axi-s4-repo-"))
        self._tmp_generator_dir = self._tmp_repo_root / "generator"
        self._tmp_generator_dir.mkdir()
        shutil.copytree(TEMPLATES_DIR, self._tmp_generator_dir / "templates")
        shutil.copytree(STACKS_DIR, self._tmp_generator_dir / "stacks")
        shutil.copy(BUILD_PY, self._tmp_generator_dir / "build.py")
        shutil.copytree(
            origin_root / modelb_axi_pkg_rel,
            self._tmp_repo_root / modelb_axi_pkg_rel,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        (self._tmp_repo_root / codec_target_rel).parent.mkdir(
            parents=True, exist_ok=True
        )
        # CR-MDB-029 \u00a7S1 MIGRATION (kind 2, orchestrator ruling D6): a build
        # now renders pi-package/README.md from docs/install-guide.md, so the
        # isolated repo root carries the guide (an input) and the package's
        # committed directory, as it carries the codec target's parent.
        (self._tmp_repo_root / INSTALL_GUIDE_REL).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / INSTALL_GUIDE_REL, self._tmp_repo_root / INSTALL_GUIDE_REL)
        (self._tmp_repo_root / PI_README_REL).parent.mkdir(parents=True, exist_ok=True)

        self._tmp_build_py = self._tmp_generator_dir / "build.py"
        self._tmp_output_agents_dir = self._tmp_repo_root / agents_rel
        # CR-MDB-024 \u00a7S2 AMENDMENT: the generator's declared target set is
        # now TARGET_AGENT_NAMES_WITH_RUST (20) once rust joins it, not the
        # pre-024 TARGET_AGENT_NAMES (16) -- repo-root-relative.
        self._expected_written = {
            (agents_rel / name).as_posix() for name in TARGET_AGENT_NAMES_WITH_RUST
        } | {codec_target_rel.as_posix(), PI_README_REL.as_posix()}
        # The fixture inputs, so a build's written-file set is the exact
        # difference against the whole isolated tree afterwards.
        self._inputs_before_build = _relative_file_set(self._tmp_repo_root)

    def tearDown(self):
        shutil.rmtree(self._tmp_repo_root, ignore_errors=True)

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

    def test_s4_isolated_build_writes_exactly_the_20_target_files(self):
        """CR-MDB-024 \u00a7S2: renamed from ..._16_target_files (16 legacy + 4
        rust = 20 once rust joins the generator's own census)."""
        self._run_isolated_build()
        self.assertTrue(
            self._tmp_output_agents_dir.is_dir(),
            f"{self._tmp_output_agents_dir} must be created by the build",
        )
        written = _relative_file_set(self._tmp_repo_root) - self._inputs_before_build
        # CR-MDB-024 \u00a7S2 AMENDMENT -- superseded pin: the generator's target
        # set widens from 16+1 to 20+1 once rust.toml exists and build.py's
        # STACKS tuple names "rust". Still diffs the WHOLE isolated repo tree
        # against the fixture inputs, so a missing target, or an extra file
        # written anywhere, still fails.
        # POSITIVE/EXACT -- an isolated build's written-file set is exactly
        # the declared targets, no more and no fewer.
        self.assertEqual(
            written, self._expected_written,
            f"an isolated build must write exactly its declared targets (the "
            f"20 small-stack agent files plus the generated codec), got "
            f"{sorted(written)}, expected {sorted(self._expected_written)}",
        )
        # bound -- exactly 22 files land on disk (20 agent defs + 1 codec +
        # the Pi package README, CR-MDB-029 \u00a7S1 migration 21 -> 22),
        # nothing extra silently emitted alongside them.
        self.assertEqual(
            len(written), 22,
            f"expected exactly 22 written files (20 agent defs + 1 generated "
            f"codec + pi-package/README.md), got {len(written)}",
        )

    def test_s4_isolated_build_never_writes_a_bespoke_agent_file(self):
        self._run_isolated_build()
        # CR-MDB-022 \u00a7S2 SANCTIONED AMENDMENT -- superseded pin: a build now
        # also writes outside generator/agents/ (the codec at CODEC_TARGET),
        # so scanning that one dir is no longer sufficient. The amended form
        # scans every file in the isolated repo tree; no fixture input carries
        # a bespoke name, so any bespoke name present was written by the
        # build. Strictly stronger: a bespoke def emitted anywhere in the
        # tree, including beside the codec, now fails.
        tree_names = {
            Path(rel).name for rel in _relative_file_set(self._tmp_repo_root)
        }
        # NEGATIVE -- none of the 9 bespoke defs (CR-MDB-024 \u00a7S2: rust's 4
        # names dropped out of bespoke) is ever written by a build.
        bespoke_overlap = tree_names & set(BESPOKE_AGENT_NAMES)
        self.assertEqual(
            bespoke_overlap, set(),
            f"a build must never write a bespoke agent file, found: "
            f"{bespoke_overlap}",
        )


if __name__ == "__main__":
    unittest.main()
