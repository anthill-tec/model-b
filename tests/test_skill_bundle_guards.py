"""CR-MDB-017 §S5 — the guard that would have caught it.

The register-flag drift this CR repairs (`--phase`, retired fleet-wide by
Crucible's 0.1.0 clean break with no alias) survived in `skills-src/` because
nothing in this repo asserted the flag surface of our own bundle text.  This
module is that assertion.  It is a port of the transferable families of the
inherited Bun guard (`docs/research/crucible-clients-skills-guard.test.ts`) —
per-bundle v2-endpoint truth, no unmarked v1 legacy, `tier` presence, and real
client verbs in examples — extended to `crucible-report-arduino`, which the
inherited suite never covered, and built around the family it lacked: the
flag-surface check.

Reads our own text, never a client
----------------------------------
Every assertion here is about text under `skills-src/`.  The module reads no
client source, no `~/.crucible` path, no Crucible dev checkout and no `--help`
output, and it carries no allow-list mirroring Crucible's flag surface.  That
design was rejected at the 2026-09-21 gap-analysis: shelling a sibling
checkout's client requires an allow-list of Crucible's flags maintained HERE,
which is a second source of truth for a surface Model B does not own — it rots
silently, and a stale entry is indistinguishable from a real hit.  The
flag-surface family therefore asserts POSITIVE facts about our own examples:

* every `register` example carries `--role` with a value from the case-exact
  enumeration `RED | GREEN | FIX | VERIFY | ORCHESTRATOR | report`;
* every example whose role is `RED|GREEN|FIX|VERIFY` also carries `--cycle`,
  matched on a WORD BOUNDARY so the `plan-file` flag `--cycles` can never
  satisfy it by substring accident;
* the retired register flag appears nowhere.

Four fixture cases (temp bundles, never a mutation of `skills-src/`) prove each
of those defects makes the checker bite, so the guard is demonstrated rather
than assumed.

What this module deliberately does NOT assert (§S5, re-scoped 2026-09-21)
------------------------------------------------------------------------
Three families originally listed for §S5 are already gated by
`tests/test_skills_handover.py` and are CITED here instead of repeated, because
two sources for one property is exactly the drift the 2026-09-21 audit records:

* `tests/test_skills_handover.py:226` — zero occurrences of the removed
  workflow-cycle-id environment variable across the imported bundles;
* `tests/test_skills_handover.py:294` — the v2 touch contract;
* `tests/test_skills_handover.py:386` — the v2 liveness/ping form.

The two agent-protocol families of the inherited suite are not ported either:
the standalone protocol skill and its shell helper are ratified out of existence
(CR-MDB-016 Option B; PRD §4.2 helper-script ban) and their ABSENCE is asserted
by `tests/test_skills_handover.py:130-137` and `:360-384`.  Nothing here may
assert they exist.

`crucible-report-vscode` owns no CLI client and has no `register` example, so it
is exempted from the register-flag families BY NAME through `API_PATH_BUNDLES`
— read once to exclude it from the scan and once by the test that proves the
exemption truthful, never an incidental zero-match.

Stdlib only: unittest + re + tempfile + pathlib.  No subprocess, no server, no
socket, and no path outside this repository.
"""

import re
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_SRC = REPO_ROOT / "skills-src"

# ------------------------------------------------------------- bundle sets ---

# The lifecycle bundle; it documents the agents API but ships no per-stack tier
# vocabulary, so it is out of the `tier` family below.
REGISTER_BUNDLE = "crucible-register"

# Bundles that ship a CLI client and therefore MUST contribute a register
# example; an accidental deletion must not turn the flag families green.
CLIENT_BUNDLES = (
    "crucible-report-arduino",
    "crucible-report-bun",
    "crucible-report-java",
    "crucible-report-python",
    "crucible-report-rust",
)

# Bundles that talk to Crucible over the v2 HTTP API and own NO CLI client.
# EXEMPT BY NAME from the register-flag families (same constant name
# `tests/test_client_role_contract.py` uses for the same ruling, Sandesh #1370).
API_PATH_BUNDLES = ("crucible-report-vscode",)

# The six per-stack report bundles carry the tier vocabulary.
REPORT_BUNDLE_PREFIX = "crucible-report-"

# ------------------------------------------------- the register-flag surface ---

# The flag Crucible retired in 0.1.0 with no alias.
RETIRED_REGISTER_FLAG = "--phase"

# Case-exact: five uppercase, `report` lowercase.
ROLE_ENUM = ("RED", "GREEN", "FIX", "VERIFY", "ORCHESTRATOR", "report")

# The roles the SERVER refuses (409) when they register without a cycle binding.
TDD_ROLES = ("RED", "GREEN", "FIX", "VERIFY")

REGISTER_EXAMPLE_RE = re.compile(r"[\w./~$-]*-crucible\.py[`'\"]?\s+register\b")
ROLE_FLAG_RE = re.compile(r"--role[=\s]+([A-Za-z-]+)")
CYCLE_FLAG_RE = re.compile(r"--cycle\b")

# Finding codes returned by `_register_flag_findings`.
FINDING_RETIRED_FLAG = "retired-flag"
FINDING_MISSING_ROLE = "missing-role"
FINDING_ROLE_OUT_OF_ENUM = "role-out-of-enum"
FINDING_MISSING_CYCLE = "missing-cycle"

# ------------------------------------------------------ endpoints and verbs ---

# Per-bundle v2 truth: every owned bundle documents the parsed and compile run
# ingest routes, the two every client path ultimately posts to.
V2_ENDPOINTS_REQUIRED = ("/api/v2/runs/parsed", "/api/v2/runs/compile")

# The v1 ingest route. Present only inside an explicit retired/legacy note.
V1_ENDPOINT = "/api/ingest"
LEGACY_MARKER_RE = re.compile(r"legacy|shim|retired|v1\b", re.IGNORECASE)
LEGACY_LOOKBACK_LINES = 15

TIER_RE = re.compile(r"\btier\b", re.IGNORECASE)

# Verbs the released clients actually expose, taken from THIS CR's own text
# (§S3/§S4a/§S4b and the per-stack surfaces it enumerates) rather than from any
# client's `argparse` — the module never reads one.
CLIENT_VERBS = (
    "register",
    "unregister",
    "test",
    "regression",
    "regression-ingest",
    "auto-ingest",
    "check",
    "compile",
    "unit",
    "module",
    "e2e",
    "pre-merge-gate",
    "next",
    "plan-file",
    "gate-run",
    "cr-close",
    "milestone",
)
CLIENT_INVOCATION_RE = re.compile(
    r"^[ \t]*(?:\$[ \t]*)?(?:python3[ \t]+)?[\w./~$-]*-crucible\.py[ \t]+([a-z][a-z0-9-]*)",
    re.MULTILINE,
)

# ----------------------------------------------------------- fixture inputs ---

# Genuine register examples, each carrying exactly one defect. The first is the
# historic pre-CR-MDB-017 form the bundles actually shipped.
FIXTURE_LINE_RETIRED_FLAG = (
    "python3 clients/arduino-crucible.py register --agent AGENT_ID --phase RED"
)
FIXTURE_LINE_NO_ROLE = (
    "python3 clients/bun-crucible.py register --agent AGENT_ID --cycle 60"
)
FIXTURE_LINE_BAD_ROLE = (
    "python3 clients/mvn-crucible.py register --agent AGENT_ID --role red --cycle 60"
)
FIXTURE_LINE_NO_CYCLE = (
    "python3 clients/python-crucible.py register --agent AGENT_ID --role GREEN"
)
FIXTURE_LINE_CLEAN = (
    "python3 clients/rust-crucible.py register --agent AGENT_ID --role VERIFY --cycle 60"
)

FIXTURE_BUNDLE_NAME = "crucible-report-fixture"
FIXTURE_BODY = """# Fixture bundle

## Register

```bash
{line}
```
"""


# ---------------------------------------------------------------- helpers ----

def _read(path):
    return path.read_text(encoding="utf-8", errors="replace")


def _iter_files(root):
    root = Path(root)
    if root.is_file():
        return [root]
    return sorted(p for p in root.rglob("*") if p.is_file())


def _rel(path, root=REPO_ROOT):
    try:
        return str(Path(path).relative_to(root))
    except ValueError:  # pragma: no cover - defensive
        return str(path)


def _is_exempt(path, root):
    """True when `path` lives inside an API-path (no-CLI-client) bundle."""
    rel = f"/{_rel(path, root)}"
    return any(f"/{bundle}/" in rel for bundle in API_PATH_BUNDLES)


def _owned_bundle_names(root):
    """MEASURE the owned bundle set from `root` rather than hard-coding it.

    A bundle is a directory carrying a SKILL.md and named `crucible-register` or
    `crucible-report-<stack>`.  Returns a sorted tuple.
    """
    root = Path(root)
    if not root.is_dir():
        return ()
    found = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or not (child / "SKILL.md").is_file():
            continue
        if child.name == REGISTER_BUNDLE or child.name.startswith(REPORT_BUNDLE_PREFIX):
            found.append(child.name)
    return tuple(found)


def _register_examples(root, include_exempt=False):
    """Every register example under `root` as (relpath, lineno, line).

    A register example is a LINE invoking a per-stack client with the `register`
    subcommand.  Prose that merely mentions the word "register" near a client
    name is not an example and carries no flag obligation.
    """
    found = []
    for path in _iter_files(root):
        if not include_exempt and _is_exempt(path, root):
            continue
        for lineno, line in enumerate(_read(path).splitlines(), 1):
            if REGISTER_EXAMPLE_RE.search(line):
                found.append((_rel(path, root), lineno, line.strip()))
    return found


def _register_flag_findings(root):
    """THE CHECKER. Every register-flag defect under `root`, as (code, detail).

    Four defect codes, one per §S5 acceptance criterion: the retired flag
    anywhere in the scanned text, a register example without `--role`, one whose
    role is outside the case-exact enumeration, and a TDD-role example without a
    word-boundary cycle binding.
    """
    findings = []
    for path in _iter_files(root):
        rel = _rel(path, root)
        for lineno, line in enumerate(_read(path).splitlines(), 1):
            if RETIRED_REGISTER_FLAG in line:
                findings.append(
                    (FINDING_RETIRED_FLAG, f"{rel}:{lineno}: {line.strip()}")
                )
    for rel, lineno, line in _register_examples(root):
        match = ROLE_FLAG_RE.search(line)
        if match is None:
            findings.append((FINDING_MISSING_ROLE, f"{rel}:{lineno}: {line}"))
            continue
        role = match.group(1)
        if role not in ROLE_ENUM:
            findings.append(
                (FINDING_ROLE_OUT_OF_ENUM, f"{rel}:{lineno}: role {role!r} — {line}")
            )
            continue
        if role in TDD_ROLES and not CYCLE_FLAG_RE.search(line):
            findings.append(
                (FINDING_MISSING_CYCLE, f"{rel}:{lineno}: role {role} — {line}")
            )
    return findings


def _codes(findings):
    return sorted({code for code, _ in findings})


def _write_fixture_bundle(tmpdir, register_line):
    """Build a throwaway bundle carrying `register_line`; return its root.

    Negative cases are proven against a temp fixture, never by mutating
    `skills-src/`.
    """
    root = Path(tmpdir) / "skills-src"
    bundle = root / FIXTURE_BUNDLE_NAME
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text(
        FIXTURE_BODY.format(line=register_line), encoding="utf-8"
    )
    return root


def _unmarked_v1_hits(text):
    """Lines naming the v1 ingest route with no retired/legacy note above them."""
    lines = text.splitlines()
    hits = []
    for index, line in enumerate(lines):
        if V1_ENDPOINT not in line:
            continue
        window = "\n".join(lines[max(0, index - LEGACY_LOOKBACK_LINES): index + 1])
        if not LEGACY_MARKER_RE.search(window):
            hits.append((index + 1, line.strip()))
    return hits


def _client_verbs(text):
    """(lineno, verb) for every command-line client invocation in `text`."""
    out = []
    for match in CLIENT_INVOCATION_RE.finditer(text):
        lineno = text.count("\n", 0, match.start()) + 1
        out.append((lineno, match.group(1)))
    return out


def _owned_bundle_paths():
    return [SKILLS_SRC / name for name in _owned_bundle_names(SKILLS_SRC)]


# ------------------------------------------------------------------ tests ----

class SkillBundleScanCoverageTest(unittest.TestCase):
    """The owned bundle set is MEASURED from `skills-src/`, and every member of
    it is genuinely reached by the scan."""

    def test_owned_bundle_set_is_measured_and_matches_the_named_sets(self):
        measured = _owned_bundle_names(SKILLS_SRC)
        named = tuple(sorted((REGISTER_BUNDLE,) + CLIENT_BUNDLES + API_PATH_BUNDLES))
        self.assertEqual(
            sorted(measured),
            list(named),
            "the owned bundle set measured from skills-src/ must be the seven of "
            f"CR-MDB-016 §S1; measured {list(measured)} against named {list(named)}. "
            "If they disagree, a bundle was added or removed without updating this "
            "guard, and the flag families would silently stop covering it.",
        )
        self.assertIn(
            "crucible-report-arduino",
            measured,
            "arduino must be covered — the inherited Bun guard never reached it, "
            "which is half of §S5's reason to exist.",
        )

    def test_every_owned_bundle_is_actually_read_by_the_scan(self):
        scanned = {
            rel.split("/", 1)[0]
            for rel in (
                _rel(path, SKILLS_SRC) for path in _iter_files(SKILLS_SRC)
            )
        }
        missing = [b for b in _owned_bundle_names(SKILLS_SRC) if b not in scanned]
        self.assertEqual(
            missing,
            [],
            "these owned bundles are named but never reached by the file scan, so "
            f"every family below would pass them vacuously: {missing}",
        )

    def test_scan_root_is_inside_the_repository(self):
        self.assertTrue(
            SKILLS_SRC.is_dir(),
            f"{_rel(SKILLS_SRC)} must exist — the guard asserts about our own text "
            "only, and has no fallback outside this repository.",
        )


class RegisterFlagSurfaceTest(unittest.TestCase):
    """§S5's reason to exist — the register flag surface of our own examples."""

    def setUp(self):
        self.examples = _register_examples(SKILLS_SRC)
        self.findings = _register_flag_findings(SKILLS_SRC)

    def test_register_examples_exist_so_the_flag_families_are_not_vacuous(self):
        self.assertNotEqual(
            self.examples,
            [],
            "no register example found under skills-src/ — every flag family below "
            "would pass vacuously; check REGISTER_EXAMPLE_RE against the bundles.",
        )
        contributors = {rel.split("/", 1)[0] for rel, _, _ in self.examples}
        missing = sorted(b for b in CLIENT_BUNDLES if b not in contributors)
        self.assertEqual(
            missing,
            [],
            "every CLI-owning bundle must contribute at least one register example; "
            f"these contribute none, so a deletion could turn the gate green: {missing}",
        )

    def test_retired_register_flag_appears_nowhere_under_skills_src(self):
        hits = [detail for code, detail in self.findings if code == FINDING_RETIRED_FLAG]
        self.assertEqual(
            hits,
            [],
            "the register flag Crucible retired in 0.1.0 (no alias) still occurs "
            "under skills-src/; every occurrence teaches a command that cannot "
            "parse. Work list:\n  " + "\n  ".join(hits),
        )

    def test_every_register_example_carries_a_case_exact_role(self):
        hits = [
            detail
            for code, detail in self.findings
            if code in (FINDING_MISSING_ROLE, FINDING_ROLE_OUT_OF_ENUM)
        ]
        self.assertEqual(
            hits,
            [],
            "every register example under skills-src/ must carry `--role` with a "
            f"value from the case-exact set {{{', '.join(ROLE_ENUM)}}}; a missing or "
            "out-of-enumeration role is refused 400 by the server. Offenders:\n  "
            + "\n  ".join(hits),
        )

    def test_tdd_role_register_examples_carry_a_cycle_binding(self):
        hits = [detail for code, detail in self.findings if code == FINDING_MISSING_CYCLE]
        self.assertEqual(
            hits,
            [],
            "every register example whose role is one of "
            f"{{{', '.join(TDD_ROLES)}}} must also bind a cycle; the server refuses "
            "an unbound TDD registration 409. Offenders:\n  " + "\n  ".join(hits),
        )

    def test_cycle_matcher_is_word_bounded(self):
        self.assertIsNone(
            CYCLE_FLAG_RE.search("--cycles"),
            "the cycle matcher must not match the plan-file flag '--cycles' — a "
            "substring match would make the binding gate a false green.",
        )
        self.assertIsNotNone(
            CYCLE_FLAG_RE.search(FIXTURE_LINE_CLEAN),
            "the cycle matcher must match a real binding: " + FIXTURE_LINE_CLEAN,
        )


class RegisterFlagFixtureTest(unittest.TestCase):
    """Each §S5 defect is PROVEN to bite against a temp fixture, so the guard is
    demonstrated rather than assumed."""

    def test_fixture_register_example_with_retired_phase_flag_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_fixture_bundle(tmp, FIXTURE_LINE_RETIRED_FLAG)
            findings = _register_flag_findings(root)
        self.assertIn(
            FINDING_RETIRED_FLAG,
            _codes(findings),
            "a register example carrying the retired flag must be reported; the "
            f"checker returned {_codes(findings)} for: {FIXTURE_LINE_RETIRED_FLAG}",
        )

    def test_fixture_register_example_missing_role_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_fixture_bundle(tmp, FIXTURE_LINE_NO_ROLE)
            findings = _register_flag_findings(root)
        self.assertIn(
            FINDING_MISSING_ROLE,
            _codes(findings),
            "a register example with no role flag must be reported; the checker "
            f"returned {_codes(findings)} for: {FIXTURE_LINE_NO_ROLE}",
        )

    def test_fixture_register_example_with_out_of_enum_role_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_fixture_bundle(tmp, FIXTURE_LINE_BAD_ROLE)
            findings = _register_flag_findings(root)
        self.assertIn(
            FINDING_ROLE_OUT_OF_ENUM,
            _codes(findings),
            "the role enumeration is CASE-EXACT, so a lowercase role must be "
            f"reported; the checker returned {_codes(findings)} for: "
            f"{FIXTURE_LINE_BAD_ROLE}",
        )

    def test_fixture_tdd_role_register_example_missing_cycle_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_fixture_bundle(tmp, FIXTURE_LINE_NO_CYCLE)
            findings = _register_flag_findings(root)
        self.assertIn(
            FINDING_MISSING_CYCLE,
            _codes(findings),
            "a TDD-role register example with no cycle binding must be reported "
            f"(the server 409s it); the checker returned {_codes(findings)} for: "
            f"{FIXTURE_LINE_NO_CYCLE}",
        )

    def test_fixture_clean_register_example_is_reported_by_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_fixture_bundle(tmp, FIXTURE_LINE_CLEAN)
            findings = _register_flag_findings(root)
        self.assertEqual(
            findings,
            [],
            "a correct register example must produce no finding at all, or the four "
            f"negative cases above prove nothing: {findings}",
        )

    def test_exempt_bundle_fixture_is_excluded_from_the_register_families(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_fixture_bundle(tmp, FIXTURE_LINE_NO_ROLE)
            exempt = root / API_PATH_BUNDLES[0]
            exempt.mkdir()
            (exempt / "SKILL.md").write_text(
                FIXTURE_BODY.format(line=FIXTURE_LINE_NO_CYCLE), encoding="utf-8"
            )
            examples = _register_examples(root)
        leaked = [rel for rel, _, _ in examples if rel.startswith(API_PATH_BUNDLES[0])]
        self.assertEqual(
            leaked,
            [],
            "the API-path bundle must be excluded from the register-flag scan BY "
            f"NAME via API_PATH_BUNDLES; these lines leaked in: {leaked}",
        )


class ApiPathExemptionTest(unittest.TestCase):
    """The vscode exemption is an assertion, never an incidental zero-match."""

    def test_api_path_exemption_names_vscode_and_is_truthful(self):
        self.assertIn(
            "crucible-report-vscode",
            API_PATH_BUNDLES,
            "the vscode bundle must be exempted from the register-flag families BY "
            "NAME — it owns no CLI client (user ruling, Sandesh #1370) — never by "
            "having happened to match nothing.",
        )
        for bundle in API_PATH_BUNDLES:
            self.assertTrue(
                (SKILLS_SRC / bundle).is_dir(),
                f"API_PATH_BUNDLES names {bundle!r}, which does not exist under "
                "skills-src/; a stale exemption silently widens the blind spot.",
            )
        leaked = [
            f"{rel}:{lineno}: {line}"
            for rel, lineno, line in _register_examples(SKILLS_SRC, include_exempt=True)
            if rel.split("/", 1)[0] in API_PATH_BUNDLES
        ]
        self.assertEqual(
            leaked,
            [],
            "the exemption claims the API-path bundles have no CLI register "
            "example. They now do, so the exemption is a lie and the bundle is "
            f"escaping the flag families: {leaked}",
        )


class BundleEndpointTierAndVerbTest(unittest.TestCase):
    """Ported from the inherited Bun guard: v2-endpoint truth, no unmarked v1
    legacy, `tier` presence, and real client verbs — now including arduino."""

    def test_every_owned_bundle_documents_the_v2_run_ingest_routes(self):
        missing = []
        for path in _owned_bundle_paths():
            text = _read(path / "SKILL.md")
            for endpoint in V2_ENDPOINTS_REQUIRED:
                if endpoint not in text:
                    missing.append(f"{_rel(path)}/SKILL.md: {endpoint}")
        self.assertEqual(
            missing,
            [],
            "every owned bundle must document the v2 run-ingest routes it posts "
            f"to {list(V2_ENDPOINTS_REQUIRED)}; missing: {missing}",
        )

    def test_no_owned_bundle_carries_an_unmarked_v1_ingest_reference(self):
        offenders = []
        for path in _owned_bundle_paths():
            for lineno, line in _unmarked_v1_hits(_read(path / "SKILL.md")):
                offenders.append(f"{_rel(path)}/SKILL.md:{lineno}: {line}")
        self.assertEqual(
            offenders,
            [],
            f"a {V1_ENDPOINT} reference is acceptable only inside an explicit "
            "retired/legacy note; these read as live instructions and violate PRD "
            "§11 criterion 2:\n  " + "\n  ".join(offenders),
        )

    def test_every_report_bundle_documents_the_tier_vocabulary(self):
        report_bundles = [
            path
            for path in _owned_bundle_paths()
            if path.name.startswith(REPORT_BUNDLE_PREFIX)
        ]
        self.assertEqual(
            len(report_bundles),
            6,
            "the six per-stack report bundles must all be measured; found "
            f"{[p.name for p in report_bundles]}",
        )
        silent = [
            f"{_rel(path)}/SKILL.md"
            for path in report_bundles
            if not TIER_RE.search(_read(path / "SKILL.md"))
        ]
        self.assertEqual(
            silent,
            [],
            "every per-stack report bundle must name the tier axis — an ingest with "
            f"no tier lands unclassified on the board; silent bundles: {silent}",
        )

    def test_client_examples_use_verbs_the_released_clients_expose(self):
        unknown = []
        for path in _iter_files(SKILLS_SRC):
            for lineno, verb in _client_verbs(_read(path)):
                if verb not in CLIENT_VERBS:
                    unknown.append(f"{_rel(path)}:{lineno}: {verb!r}")
        self.assertEqual(
            unknown,
            [],
            "every documented client invocation must use a verb the released "
            f"clients expose {list(CLIENT_VERBS)}; these teach a subcommand that "
            "does not exist:\n  " + "\n  ".join(unknown),
        )

    def test_each_cli_bundle_shows_at_least_one_real_client_invocation(self):
        silent = []
        for bundle in CLIENT_BUNDLES:
            text = _read(SKILLS_SRC / bundle / "SKILL.md")
            verbs = {verb for _, verb in _client_verbs(text)}
            if not verbs & set(CLIENT_VERBS):
                silent.append(bundle)
        self.assertEqual(
            silent,
            [],
            "every CLI-owning bundle must show at least one real client invocation, "
            f"or the verb gate passes it vacuously: {silent}",
        )


if __name__ == "__main__":
    unittest.main()
