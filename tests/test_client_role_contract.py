"""RED gates for CR-MDB-017 cycle C1 — the register-flag contract sync.

Scope of this module is C1 ONLY: the `register` verb's flag surface across the
surfaces Model B publishes (`skills-src/`, `contracts/`, `AGENTS.md`).
Plan-file / gate-run / endpoint families (C2), the generator (C3) and the
standalone guard module (C4) are deliberately NOT asserted here.

Definitions used by every gate in this module
---------------------------------------------
**register example** — a single LINE that invokes a per-stack Crucible client
with the `register` subcommand: a token matching ``*-crucible.py`` (optionally
path-qualified and/or wrapped in markdown backticks/quotes) followed, with only
whitespace in between, by the word ``register``.  Prose that merely mentions the
word "register" near a client name (e.g. a "Subcommands: register/unregister"
sentence) is NOT a register example and is not required to carry flags; the
retired-flag gate (§S3, family 1) covers such prose independently.

**word-boundary `--cycle`** — ``--cycle`` followed by a word boundary, so the
`plan-file` flag ``--cycles`` (live at `skills-src/crucible/SKILL.md:95` and
`skills-src/model-b/SKILL.md:47`) can never satisfy the cycle-binding gate by
substring accident.  The matcher's word-boundary property is itself unit-tested
against the literal string ``--cycles``.

Contract being pinned (CR-MDB-017 Context, measured against the installed
clients at `~/.crucible/clients/`): ``register --agent <id> --role <ROLE>`` with
the case-exact enumeration ``RED | GREEN | FIX | VERIFY | ORCHESTRATOR |
report``; ``--cycle`` bound at registration and enforced BY THE SERVER (409) for
the four TDD roles, not by argparse; a missing/out-of-enum role refused 400;
``ORCHESTRATOR``/``report`` may register unbound; the agentId free-form with the
role never inferred from it.  ``--phase`` no longer exists.

These gates are expected to FAIL until CR-MDB-017 §S1/§S2/§S3/§S4 land.
"""

import ast
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_SRC = REPO_ROOT / "skills-src"
CONTRACTS = REPO_ROOT / "contracts"
AGENTS_MD = REPO_ROOT / "AGENTS.md"
TESTS_DIR = REPO_ROOT / "tests"
CRUCIBLE_SKILL = SKILLS_SRC / "crucible" / "SKILL.md"

# The flag Crucible retired fleet-wide in their 0.1.0 clean break (no alias).
RETIRED_REGISTER_FLAG = "--phase"

# CR-MDB-023: `--phase` is ALSO the live flag of `rust-code-health.py snapshot`
# (a Model B tool, not a Crucible client). Only that exact occurrence is
# stripped before the retired-flag check; every other `--phase` still bites.
RUST_SNAPSHOT_PHASE_RE = re.compile(r"rust-code-health\.py\s+snapshot\s+--phase\b")


def _carries_retired_register_flag(line):
    """True when `line` carries the retired register flag once the
    `rust-code-health.py snapshot --phase` occurrences are removed
    (CR-MDB-023) -- the guard's intent is otherwise unchanged."""
    return RETIRED_REGISTER_FLAG in RUST_SNAPSHOT_PHASE_RE.sub("", line)

# Case-exact; five uppercase, `report` lowercase.
ROLE_ENUM = ("RED", "GREEN", "FIX", "VERIFY", "ORCHESTRATOR", "report")
# The roles the SERVER refuses (409) when they register without a cycle binding.
TDD_ROLES = ("RED", "GREEN", "FIX", "VERIFY")

# CR-MDB-024 \u00a7S3 (this cycle, C2 RED, 2026-09-22 VS Code ruling): the
# single-member API-path exemption this constant existed for
# (the VS Code crucible-report bundle) is retired outright, not migrated -- the bundle
# is deleted, so nothing needs exempting from the register-flag families any
# more. Left EMPTY rather than deleted so `_register_examples`' existing
# `include_exempt` plumbing (line ~116) stays syntactically valid without a
# structural rewrite; an empty exemption set is itself the correct S3 state
# ("an exemption whose only member is gone").
API_PATH_BUNDLES = ()

# Bundles that DO ship a CLI register example; each must contribute at least one,
# so an accidental deletion cannot turn the flag gates green.
CLIENT_BUNDLES = (
    "crucible-report-arduino",
    "crucible-report-bun",
    "crucible-report-java",
    "crucible-report-python",
    "crucible-report-rust",
)

REGISTER_EXAMPLE_RE = re.compile(r"[\w./~$-]*-crucible\.py[`'\"]?\s+register\b")
ROLE_FLAG_RE = re.compile(r"--role[=\s]+([A-Za-z-]+)")
CYCLE_FLAG_RE = re.compile(r"--cycle\b")

# Test-module names that mark a "this term MUST be present" list.
REQUIRED_TERM_NAME_RE = re.compile(
    r"required|must_contain|must_appear|expected_present|present_terms", re.IGNORECASE
)
PRESENCE_ASSERTIONS = {"assertIn", "assertRegex"}


def _read(path):
    """Read any file in the scanned roots; nothing inside a root is excluded."""
    return path.read_text(encoding="utf-8", errors="replace")


def _iter_files(root):
    if root.is_file():
        return [root]
    return sorted(p for p in root.rglob("*") if p.is_file())


def _rel(path):
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:  # pragma: no cover - defensive
        return str(path)


def _scan_roots():
    """Yield (path, lineno, line) for every line of every file in the C1 roots."""
    for root in (SKILLS_SRC, CONTRACTS, AGENTS_MD):
        if not root.exists():
            continue
        for path in _iter_files(root):
            for lineno, line in enumerate(_read(path).splitlines(), 1):
                yield path, lineno, line


def _register_examples(include_exempt=False):
    """All register examples under `skills-src/` as (path, lineno, line)."""
    found = []
    for path in _iter_files(SKILLS_SRC):
        rel = _rel(path)
        if not include_exempt and any(f"/{b}/" in f"/{rel}" for b in API_PATH_BUNDLES):
            continue
        for lineno, line in enumerate(_read(path).splitlines(), 1):
            if REGISTER_EXAMPLE_RE.search(line):
                found.append((path, lineno, line.strip()))
    return found


def _windows(text, needle, radius):
    """Every ±radius character window around each occurrence of `needle`."""
    out = []
    start = 0
    while True:
        idx = text.find(needle, start)
        if idx < 0:
            return out
        out.append(text[max(0, idx - radius): idx + len(needle) + radius])
        start = idx + len(needle)


class ClientRoleContractS1Test(unittest.TestCase):
    """§S1 — no Model B test may pin the retired flag as a required term."""

    def test_s1_no_test_module_requires_phase_as_a_required_term(self):
        offenders = []
        for path in sorted(TESTS_DIR.glob("*.py")):
            source = _read(path)
            try:
                tree = ast.parse(source)
            except SyntaxError as exc:  # pragma: no cover - defensive
                self.fail(f"{_rel(path)} does not parse: {exc}")
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                    if not any(REQUIRED_TERM_NAME_RE.search(n) for n in names):
                        continue
                    if not isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                        continue
                    for element in node.value.elts:
                        if (
                            isinstance(element, ast.Constant)
                            and isinstance(element.value, str)
                            and RETIRED_REGISTER_FLAG in element.value
                        ):
                            offenders.append(
                                f"{_rel(path)}:{element.lineno}: "
                                f"{names[0]} requires {element.value!r}"
                            )
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr not in PRESENCE_ASSERTIONS or not node.args:
                        continue
                    first = node.args[0]
                    if (
                        isinstance(first, ast.Constant)
                        and isinstance(first.value, str)
                        and RETIRED_REGISTER_FLAG in first.value
                    ):
                        offenders.append(
                            f"{_rel(path)}:{first.lineno}: "
                            f"{node.func.attr}({first.value!r}, ...) asserts its PRESENCE"
                        )
        self.assertEqual(
            offenders,
            [],
            "no test under tests/ may require the retired register flag "
            f"{RETIRED_REGISTER_FLAG!r}; Crucible removed it in 0.1.0 with no alias. "
            "Offending pins:\n  " + "\n  ".join(offenders),
        )


class ClientRoleContractS2Test(unittest.TestCase):
    """§S2 — `skills-src/crucible/SKILL.md` must state the SUBSTANCE of the
    register contract, not merely carry the renamed flag."""

    def setUp(self):
        self.assertTrue(CRUCIBLE_SKILL.is_file(), f"{_rel(CRUCIBLE_SKILL)} must exist")
        self.text = _read(CRUCIBLE_SKILL)

    def test_s2_states_case_exact_role_enumeration(self):
        self.assertIn(
            "--role",
            self.text,
            f"MISSING FACT (role flag): {_rel(CRUCIBLE_SKILL)} never names `--role`, "
            "the flag that replaced the retired `--phase`.",
        )
        enumeration = re.compile(
            r"RED\W{1,12}GREEN\W{1,12}FIX\W{1,12}VERIFY\W{1,24}ORCHESTRATOR\W{1,12}report",
            re.DOTALL,
        )
        self.assertRegex(
            self.text,
            enumeration,
            "MISSING FACT (case-exact enumeration): "
            f"{_rel(CRUCIBLE_SKILL)} must show the role values as the case-exact set "
            f"{' | '.join(ROLE_ENUM)} (five uppercase, `report` lowercase).",
        )

    def test_s2_states_cycle_required_for_tdd_roles_by_server_not_argparse(self):
        bound = any(
            CYCLE_FLAG_RE.search(window) and re.search(r"\b409\b", window)
            for window in _windows(self.text, "409", 400)
        )
        self.assertTrue(
            bound,
            "MISSING FACT (409 cycle binding): "
            f"{_rel(CRUCIBLE_SKILL)} must state that a TDD-role registration without a "
            "word-boundary `--cycle` binding is refused 409 "
            f"(roles {', '.join(TDD_ROLES)}).",
        )
        self.assertRegex(
            self.text,
            re.compile(r"(?i)argparse"),
            "MISSING FACT (server, not argparse): "
            f"{_rel(CRUCIBLE_SKILL)} must state that the per-role cycle rule is enforced "
            "by the SERVER at the route boundary, not by argparse (argparse makes only "
            "`--role` required).",
        )

    def test_s2_states_missing_or_out_of_enum_role_refused_400(self):
        refused = any(
            re.search(r"(?i)role", window) for window in _windows(self.text, "400", 400)
            if re.search(r"\b400\b", window)
        )
        self.assertTrue(
            refused,
            "MISSING FACT (400 on bad role): "
            f"{_rel(CRUCIBLE_SKILL)} must state that a registration reaching the server "
            "with a missing or out-of-enumeration role is refused 400.",
        )

    def test_s2_states_orchestrator_and_report_may_register_unbound(self):
        unbound = any(
            "report" in window
            and re.search(r"(?i)unbound|without a cycle|no cycle", window)
            for window in _windows(self.text, "ORCHESTRATOR", 300)
        )
        self.assertTrue(
            unbound,
            "MISSING FACT (unbound roles): "
            f"{_rel(CRUCIBLE_SKILL)} must state that `ORCHESTRATOR` and `report` may "
            "register WITHOUT a cycle binding.",
        )

    def test_s2_states_agent_id_free_form_and_role_never_inferred(self):
        self.assertRegex(
            self.text,
            re.compile(r"(?i)free[-\s]?form"),
            "MISSING FACT (free-form agentId): "
            f"{_rel(CRUCIBLE_SKILL)} must state that the agentId is FREE-FORM (assigned "
            "by the dispatcher, never minted by the agent).",
        )
        self.assertRegex(
            self.text,
            re.compile(r"(?i)(never|not)\s+(inferred|parsed|derived)"),
            "MISSING FACT (role never inferred): "
            f"{_rel(CRUCIBLE_SKILL)} must state that the role is never inferred from the "
            "agentId's shape — an id ending `-GREEN` registered with `--role RED` is RED.",
        )


class ClientRoleContractS3Test(unittest.TestCase):
    """§S3 — the register-flag surface of everything Model B publishes."""

    def test_s3_zero_retired_phase_flag_across_published_surfaces(self):
        hits = [
            f"{_rel(path)}:{lineno}: {line.strip()}"
            for path, lineno, line in _scan_roots()
            if _carries_retired_register_flag(line)
        ]
        self.assertEqual(
            hits,
            [],
            f"{len(hits)} occurrence(s) of the retired register flag "
            f"{RETIRED_REGISTER_FLAG!r} remain under skills-src/, contracts/ and "
            "AGENTS.md; Crucible removed it in 0.1.0 with no alias, so every one of "
            "these teaches a command that cannot parse. Work list:\n  "
            + "\n  ".join(hits),
        )

    def test_s3_retired_flag_detector_exempts_only_rust_code_health_snapshot(self):
        # CR-MDB-023: the exemption spares ONLY `rust-code-health.py snapshot
        # --phase`; the retired register flag bites alone and alongside it.
        retired = "python3 clients/rust-crucible.py register --agent X --phase RED"
        snapshot = (
            "python3 ~/.agents/scripts/rust-code-health.py snapshot --phase post --slice CR-X"
        )
        self.assertTrue(_carries_retired_register_flag(retired))
        self.assertFalse(_carries_retired_register_flag(snapshot))
        self.assertTrue(_carries_retired_register_flag(f"{snapshot} && {retired}"))

    def test_s3_every_register_example_carries_role_from_enumeration(self):
        examples = _register_examples()
        self.assertNotEqual(
            examples, [], "no register example found under skills-src/ — the gate would "
            "pass vacuously; check REGISTER_EXAMPLE_RE against the bundles."
        )
        offenders = []
        for path, lineno, line in examples:
            match = ROLE_FLAG_RE.search(line)
            if match is None:
                offenders.append(f"{_rel(path)}:{lineno}: no `--role` flag — {line}")
            elif match.group(1) not in ROLE_ENUM:
                offenders.append(
                    f"{_rel(path)}:{lineno}: role {match.group(1)!r} is outside the "
                    f"case-exact enumeration — {line}"
                )
        self.assertEqual(
            offenders,
            [],
            "every register example under skills-src/ must carry `--role` with a value "
            f"from {{{', '.join(ROLE_ENUM)}}} (case-exact). Offenders:\n  "
            + "\n  ".join(offenders),
        )

    def test_s3_client_bundles_each_contribute_a_register_example(self):
        seen = dict.fromkeys(CLIENT_BUNDLES, 0)
        for path, _lineno, _line in _register_examples():
            rel = _rel(path)
            for bundle in CLIENT_BUNDLES:
                if f"skills-src/{bundle}/" in rel:
                    seen[bundle] += 1
        missing = sorted(b for b, count in seen.items() if count == 0)
        self.assertEqual(
            missing,
            [],
            "these client-owning bundles contribute no register example, so the "
            f"`--role`/`--cycle` gates would pass them vacuously: {missing}",
        )

    def test_s3_tdd_role_register_examples_carry_cycle(self):
        offenders = []
        for path, lineno, line in _register_examples():
            match = ROLE_FLAG_RE.search(line)
            role = match.group(1) if match else None
            if role in TDD_ROLES and not CYCLE_FLAG_RE.search(line):
                offenders.append(
                    f"{_rel(path)}:{lineno}: role {role} without a word-boundary "
                    f"`--cycle` binding — {line}"
                )
            if role is None and RETIRED_REGISTER_FLAG in line:
                offenders.append(
                    f"{_rel(path)}:{lineno}: still classifies with the retired "
                    f"{RETIRED_REGISTER_FLAG!r}, so no role/cycle binding exists — {line}"
                )
        self.assertEqual(
            offenders,
            [],
            "every register example whose role is one of "
            f"{{{', '.join(TDD_ROLES)}}} must also carry `--cycle <id>`; the server "
            "refuses an unbound TDD registration 409. Offenders:\n  "
            + "\n  ".join(offenders),
        )

    def test_s3_cycle_matcher_is_word_bounded_and_rejects_cycles(self):
        self.assertIsNone(
            CYCLE_FLAG_RE.search("--cycles"),
            "CYCLE_FLAG_RE must NOT match the literal '--cycles': it is the `plan-file` "
            "flag, and a substring match would make the cycle-binding gate a false green.",
        )
        self.assertIsNone(
            CYCLE_FLAG_RE.search(
                "python3 clients/python-crucible.py plan-file --cr CR-MDB-017 --cycles 3"
            ),
            "a `plan-file --cycles N` line must not satisfy the register cycle gate.",
        )
        for accepted in (
            "register --agent A --role RED --cycle 57",
            "register --agent A --role RED --cycle=57",
            "register --agent A --role GREEN --cycle <cycleId>",
        ):
            self.assertIsNotNone(
                CYCLE_FLAG_RE.search(accepted),
                f"CYCLE_FLAG_RE must match a real cycle binding: {accepted!r}",
            )

    # CR-MDB-024 \u00a7S3 (this cycle, C2 RED, 2026-09-22 VS Code ruling):
    # test_s3_api_path_exemption_constant_names_VS_Code_bundle and
    # test_s3_exempted_bundle_has_no_register_example are DELETED, not
    # migrated -- the VS Code bundle they asserted about is retired outright,
    # so API_PATH_BUNDLES above is now empty and there is nothing left for
    # either test to name or prove truthful ("an exemption whose only member
    # is gone"). The retirement itself is gated by
    # tests/test_ide_overlay_retirement.py.


if __name__ == "__main__":
    unittest.main()
