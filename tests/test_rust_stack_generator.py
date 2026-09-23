"""RED-phase tests for CR-MDB-024 §S1/§S2 (cycle C1) — the new `rust.toml`
stack params file and the generator's five-stack census.

Written BEFORE the GREEN-phase work lands (`generator/stacks/rust.toml`,
`generator/build.py`'s `STACKS` tuple gaining `"rust"`, and the four rendered
`generator/agents/rust-{red,green,verify,fix}-agent.md`), so most assertions
here are expected to FAIL against the current tree — `rust.toml` does not
exist yet and `build.py` does not know the stack name `"rust"`.

Scope boundary (dispatch, cycle C1): this module covers §S1 (the stack TOML's
own shape and content) and §S2 (the generator's census widening from 16 to 20
targets). It does NOT touch §S3 (VS Code retirement) or §S4 (doc/record
corrections) — those are cycle C2, gated in tests/test_ide_overlay_retirement.py
and this cycle's migrated files. The pre-existing generic gates in
`test_generator_role_contract.py` (§S6a/§S6b) already derive their stack and
role lists by globbing `generator/stacks/*.toml` / `generator/templates/*.tmpl`
/ `generator/agents/*.md` rather than hardcoding the current four, so they
widen automatically once `rust.toml` and the four rust agent files exist and
need no edits here — see that module's own docstring. In particular the
`--role`/`--cycle` half of the AC ("every register example carries --role,
and for the four TDD roles --cycle") is already covered THERE against the
RENDERED agent files: the sibling stacks' own `register_command` values are
bare (no `--role`/`--cycle` — confirmed by reading all four existing
`generator/stacks/*.toml`), because the shared per-role TEMPLATE appends
those flags itself. A `rust.toml`-text-only check for those substrings would
therefore misfire against a CORRECT implementation that follows the exact
shape `quarkus.toml` establishes, so this module deliberately does not
duplicate that check at the TOML-text layer.

The "no statement in the rendered rust definitions contradicts
rust-orchestration.md" AC (§S1, final bullet) is a soft, exhaustive-comparison
requirement that cannot be fully mechanized; per the RED escalation rule this
module operationalizes it as a partial, testable slice — the mechanics text
must retain a set of key facts named in `rust-orchestration.md` (the released
client name, the coverage tool, and the three gate/tier verbs the CR's own
tier_guidance bullet names) — rather than a full semantic diff. This is a
documented, deliberate narrowing, not a silent substitution.

Stdlib only (unittest + subprocess + sys + tomllib + importlib.util +
pathlib), matching the generator test suite's existing conventions.
"""

import importlib.util
import re
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATOR_DIR = REPO_ROOT / "generator"
STACKS_DIR = GENERATOR_DIR / "stacks"
AGENTS_DIR = GENERATOR_DIR / "agents"
BUILD_PY = GENERATOR_DIR / "build.py"

RUST_TOML = STACKS_DIR / "rust.toml"
QUARKUS_TOML = STACKS_DIR / "quarkus.toml"
ORCHESTRATION_MEMORY = (
    REPO_ROOT / "skills-src" / "memory-templates" / "rust-orchestration.md"
)

ROLES = ("red", "green", "verify", "fix")

RELEASED_RUST_CLIENT = "~/.crucible/clients/rust-crucible.py"

# CR-MDB-024 §S1: retired/wrong-scope items the memory template's fragment
# carries but that a PRD/DN rule has since retired for a freshly authored
# stack — never imported into rust.toml.
FORBIDDEN_SUBSTRINGS = ("--phase", "~/.claude", "data_projects")

# Every `*-crucible.py` client-script reference anywhere in rust.toml's text.
CRUCIBLE_CLIENT_RE = re.compile(r"[~/.\w-]*-crucible\.py")

# §S1: "tier_guidance states Cargo's unit/integration split and the
# smoke-test/docker-e2e-gate mapping of §S1" — the exact vocabulary bullet
# from the CR's own Scope section, checked verbatim (case-sensitive; these
# are client verbs, not prose).
TIER_GUIDANCE_ANCHORS = (
    "#[cfg(test)]",
    "--lib",
    "tests/*.rs",
    "--test <name>",
    "smoke-test --profile e2e",
    "docker-e2e-gate",
    "-P ci",
    "workspace-regression",
)

# §S1 final bullet, narrowed per this module's docstring: key facts from
# rust-orchestration.md that a reconciled (not verbatim-copied) mechanics
# section must still carry forward.
ORCHESTRATION_FACT_ANCHORS = (
    "rust-crucible.py",
    "nextest",
    "llvm-cov",
    "pre-merge-gate",
    "docker-e2e-gate",
    "workspace-regression",
    "smoke-test",
)


def _raw(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_build_module():
    """Import generator/build.py as a standalone module (pure at module
    level — constant definitions only) to read its declared STACKS tuple
    without duplicating it as a string here. generator/ has no __init__.py,
    hence importlib.util over a package import."""
    spec = importlib.util.spec_from_file_location("_cr_mdb_024_c1_build", BUILD_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rust_params() -> dict:
    with RUST_TOML.open("rb") as fh:
        return tomllib.load(fh)


def _quarkus_params() -> dict:
    with QUARKUS_TOML.open("rb") as fh:
        return tomllib.load(fh)


class RustStackTomlShapeS1Test(unittest.TestCase):
    """§S1 — `generator/stacks/rust.toml` exists, parses, and carries every
    key and per-role table `quarkus.toml` has, including `tier_guidance`."""

    def test_s1_rust_toml_exists(self):
        # POSITIVE — the new stack params file must exist before any content
        # assertion about it means anything.
        self.assertTrue(
            RUST_TOML.is_file(),
            f"{RUST_TOML} must exist (CR-MDB-024 §S1)",
        )

    def test_s1_rust_toml_parses_via_tomllib(self):
        self.assertTrue(RUST_TOML.is_file(), f"{RUST_TOML} must exist to parse")
        try:
            _rust_params()
        except tomllib.TOMLDecodeError as exc:
            self.fail(f"{RUST_TOML} failed to parse via tomllib: {exc}")

    def test_s1_rust_toml_declares_every_top_level_key_quarkus_toml_has(self):
        """rust.toml's top-level key set is a SUPERSET of quarkus.toml's —
        the shape quarkus.toml establishes, verbatim per §S1's own words."""
        self.assertTrue(RUST_TOML.is_file(), f"{RUST_TOML} must exist")
        quarkus_keys = set(_quarkus_params().keys())
        rust_keys = set(_rust_params().keys())
        missing = quarkus_keys - rust_keys
        # POSITIVE/EXACT — every key quarkus.toml declares must also be
        # present in rust.toml (quarkus_keys is a strict, named set here —
        # display_name, test_command, register_command, unregister_command,
        # crucible_reference, mechanics, tier_guidance, description,
        # frontmatter, gotchas).
        self.assertEqual(
            missing, set(),
            f"rust.toml is missing key(s) quarkus.toml declares: {sorted(missing)} "
            f"(quarkus.toml keys: {sorted(quarkus_keys)}, rust.toml keys: {sorted(rust_keys)})",
        )
        # sanity — quarkus.toml itself declares tier_guidance (CR-MDB-017),
        # so the superset check above already implies rust.toml must too;
        # this pins the sanity assumption explicitly.
        self.assertIn("tier_guidance", quarkus_keys)

    def test_s1_rust_toml_scalar_keys_are_non_empty_strings(self):
        self.assertTrue(RUST_TOML.is_file(), f"{RUST_TOML} must exist")
        params = _rust_params()
        scalar_keys = (
            "display_name", "test_command", "register_command",
            "unregister_command", "crucible_reference", "mechanics",
            "tier_guidance",
        )
        problems = []
        for key in scalar_keys:
            value = params.get(key)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{key!r}: expected a non-empty string, got {value!r}")
        # POSITIVE — every scalar key carries a real (non-empty) value.
        self.assertEqual(problems, [], "\n".join(problems))

    def test_s1_rust_toml_per_role_tables_cover_all_four_roles(self):
        """[description] and [gotchas] each carry all four roles (red,
        green, verify, fix) as non-empty string values, and [roles] carries
        a table for each of the four roles (CR-MDB-025 §S1 AC3)."""
        self.assertTrue(RUST_TOML.is_file(), f"{RUST_TOML} must exist")
        params = _rust_params()
        problems = []
        for table_name in ("description", "gotchas"):
            table = params.get(table_name)
            if not isinstance(table, dict):
                problems.append(f"[{table_name}]: missing or not a table")
                continue
            for role in ROLES:
                value = table.get(role)
                if not isinstance(value, str) or not value.strip():
                    problems.append(
                        f"[{table_name}].{role}: expected a non-empty string, got {value!r}"
                    )
        roles_table = params.get("roles")
        if not isinstance(roles_table, dict):
            problems.append("[roles]: missing or not a table")
        else:
            for role in ROLES:
                if not isinstance(roles_table.get(role), dict):
                    problems.append(
                        f"[roles.{role}]: expected a table, got {roles_table.get(role)!r}"
                    )
        # POSITIVE/bound — 2 string tables x 4 roles = 8 entries, plus the
        # 4 [roles.<role>] tables, none missing.
        self.assertEqual(problems, [], "\n".join(problems))


class RustStackClientInvocationS1Test(unittest.TestCase):
    """§S1 "Client" bullet — every client invocation in rust.toml names the
    released client, and zero retired/wrong-scope items are ever imported
    from the memory-template fragment."""

    def test_s1_every_crucible_client_reference_names_the_released_rust_client(self):
        self.assertTrue(RUST_TOML.is_file(), f"{RUST_TOML} must exist")
        text = _raw(RUST_TOML)
        matches = sorted(set(CRUCIBLE_CLIENT_RE.findall(text)))
        self.assertTrue(
            matches,
            f"no *-crucible.py client invocation found anywhere in {RUST_TOML}",
        )
        # POSITIVE/EXACT — every *-crucible.py reference in the file is the
        # one released client, at its released path; a wrong script name or
        # a stale ~/.claude/scripts/ path fails this.
        self.assertEqual(
            matches, [RELEASED_RUST_CLIENT],
            f"every client invocation in rust.toml must name {RELEASED_RUST_CLIENT!r}, "
            f"found: {matches}",
        )

    def test_s1_rust_toml_carries_zero_retired_or_wrong_scope_items(self):
        self.assertTrue(RUST_TOML.is_file(), f"{RUST_TOML} must exist")
        text = _raw(RUST_TOML)
        present = [item for item in FORBIDDEN_SUBSTRINGS if item in text]
        # NEGATIVE/EXACT bound — zero occurrences of any retired/wrong-scope
        # item (this stack is authored fresh, not adopted stale — §S1).
        self.assertEqual(
            present, [],
            f"rust.toml must carry none of {list(FORBIDDEN_SUBSTRINGS)}, found: {present}",
        )


class RustStackTierGuidanceS1Test(unittest.TestCase):
    """§S1 — `tier_guidance` states Cargo's own unit/integration split and
    the smoke-test/docker-e2e-gate/workspace-regression mapping."""

    def test_s1_tier_guidance_states_cargos_unit_integration_split_and_gate_mapping(self):
        self.assertTrue(RUST_TOML.is_file(), f"{RUST_TOML} must exist")
        guidance = _rust_params().get("tier_guidance")
        assert isinstance(guidance, str)
        missing = [anchor for anchor in TIER_GUIDANCE_ANCHORS if anchor not in guidance]
        # POSITIVE — every named anchor from the CR's own tier_guidance bullet
        # is present verbatim; a generic/paraphrased tier paragraph fails this.
        self.assertEqual(
            missing, [],
            f"rust.toml's tier_guidance must state every one of {TIER_GUIDANCE_ANCHORS}, "
            f"missing: {missing}\ngot:\n{guidance}",
        )


class RustStackMechanicsReconciliationS1Test(unittest.TestCase):
    """§S1 final bullet (narrowed per this module's docstring) — the
    mechanics section preserves the key facts named in rust-orchestration.md
    rather than silently dropping them during reconciliation."""

    def test_s1_mechanics_preserves_orchestration_source_facts(self):
        self.assertTrue(RUST_TOML.is_file(), f"{RUST_TOML} must exist")
        self.assertTrue(
            ORCHESTRATION_MEMORY.is_file(),
            f"{ORCHESTRATION_MEMORY} must exist to reconcile against",
        )
        mechanics = _rust_params().get("mechanics")
        assert isinstance(mechanics, str)
        source_text = _raw(ORCHESTRATION_MEMORY)
        missing = [
            fact for fact in ORCHESTRATION_FACT_ANCHORS
            if fact in source_text and fact not in mechanics
        ]
        # POSITIVE — every source fact that rust-orchestration.md itself
        # actually names is preserved in the reconciled mechanics text.
        self.assertEqual(
            missing, [],
            f"rust.toml's mechanics must preserve these facts from "
            f"{ORCHESTRATION_MEMORY.name}: {missing}\ngot mechanics:\n{mechanics}",
        )


class RustStackGeneratorCensusS2Test(unittest.TestCase):
    """§S2 — the generator's own STACKS enumeration widens to five; `--list`
    restricted to `--stacks rust` names exactly the four rust role files
    (plus the always-present codec target), and `--check` on that filter
    exits 0 once GREEN has rendered them."""

    def test_s2_build_module_declares_rust_in_its_stacks_tuple(self):
        self.assertTrue(BUILD_PY.is_file(), f"{BUILD_PY} must exist")
        build_module = _load_build_module()
        # POSITIVE — build.py's own STACKS constant must name "rust".
        self.assertIn(
            "rust", build_module.STACKS,
            f"generator/build.py's STACKS tuple must include 'rust', got {build_module.STACKS}",
        )

    def test_s2_list_restricted_to_rust_names_exactly_the_four_role_files_plus_codec(self):
        self.assertTrue(BUILD_PY.is_file(), f"{BUILD_PY} must exist to run --list")
        result = subprocess.run(
            [sys.executable, str(BUILD_PY), "--list", "--stacks", "rust"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(
            result.returncode, 0,
            f"generator/build.py --list --stacks rust must exit 0 once 'rust' is a known "
            f"stack, got rc={result.returncode}\nstdout:\n{result.stdout[:2000]}\n"
            f"stderr:\n{result.stderr[:2000]}",
        )
        listed_paths = {
            Path(line.strip()) for line in result.stdout.splitlines() if line.strip()
        }
        build_module = _load_build_module()
        expected_paths = {
            AGENTS_DIR / f"rust-{role}-agent.md" for role in ROLES
        } | {build_module.CODEC_TARGET}
        # POSITIVE/EXACT — restricted to the rust stack, the target list is
        # exactly the 4 rust role files plus the always-present codec target.
        self.assertEqual(
            listed_paths, expected_paths,
            f"--list --stacks rust must report exactly the 4 rust role files plus the "
            f"codec target, got {sorted(str(p) for p in listed_paths)}, expected "
            f"{sorted(str(p) for p in expected_paths)}",
        )

    def test_s2_check_restricted_to_rust_stack_exits_zero_once_generated(self):
        self.assertTrue(BUILD_PY.is_file(), f"{BUILD_PY} must exist to run --check")
        result = subprocess.run(
            [sys.executable, str(BUILD_PY), "--check", "--stacks", "rust"],
            capture_output=True, text=True, timeout=60,
        )
        # POSITIVE/EXACT — once rust.toml exists and build.py build has
        # rendered its 4 role files, --check --stacks rust must report a
        # clean (in-sync) tree (the §S2 drift-gate proof that every
        # generator/agents/rust-*.md line arrives via build.py build).
        self.assertEqual(
            result.returncode, 0,
            "generator/build.py --check --stacks rust must exit 0 once the rust role "
            f"files are generated and in sync, got rc={result.returncode}\n"
            f"stdout:\n{result.stdout[:2000]}\nstderr:\n{result.stderr[:2000]}",
        )


if __name__ == "__main__":
    unittest.main()
