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

And the same surface on the wire (added at CR-MDB-017 V1), because not every
register example is a command line: a `POST` to the agents register route whose
payload declares no `role`, or declares a TDD role without a `cycleId`, is the
same defect in the shape the released server actually rejects.  It shipped
undetected in `crucible-register`, which owns no CLI client and therefore
matched the flag families zero times -- passing not because it was correct but
because nothing looked at it.  `HTTP_BODY_BUNDLES` names the bundles whose
register surface is a payload, and the family asserts each one CONTRIBUTES an
example, so the blind spot cannot reopen silently.

Five fixture cases (temp bundles, never a mutation of `skills-src/`) prove each
of those defects makes the checker bite, so the guard is demonstrated rather
than assumed. (CR-MDB-024 \u00a7S3, this cycle: the sixth fixture, the
API-path-exemption case, is retired along with the bundle it exempted.)

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

CR-MDB-024 \u00a7S3 AMENDMENT (this cycle, C2 RED, 2026-09-22 VS Code ruling): the
VS Code crucible-report bundle this module's `API_PATH_BUNDLES` exemption
existed for is retired outright -- an IDE is not a stack. `API_PATH_BUNDLES`
narrows to empty and `ApiPathExemptionTest` (which asserted the exemption was
named and truthful) is deleted rather than migrated: there is no bundle left
for either to be about. The owned-bundle-set pin
(`SkillBundleScanCoverageTest`) narrows from seven to six accordingly.

Stdlib only: unittest + re + tempfile + pathlib.  No subprocess, no server, no
socket, and no path outside this repository.
"""

import re
import tempfile
import unittest
from pathlib import Path

from tests._helpers import (
    carries_retired_register_flag as _carries_retired_register_flag,
    read_text_lenient as _read,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_SRC = REPO_ROOT / "skills-src"

# ------------------------------------------------------------- bundle sets ---

# The lifecycle bundle; it documents the agents API but ships no per-stack tier
# vocabulary, so it is out of the `tier` family below.  Its register surface is
# an HTTP BODY, not a CLI invocation, so it is named in HTTP_BODY_BUNDLES below
# and asserted about there -- CR-MDB-017 V1 found it sitting in no category at
# all, passing every family by incidental zero-match while shipping a payload
# the released server rejects.
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

# Bundles whose register surface is an HTTP BODY posted to the agents API --
# the wire-key equivalent of the CLI flag families.  Named so the body family
# below can assert they CONTRIBUTE one, never pass by matching nothing.
HTTP_BODY_BUNDLES = (
    REGISTER_BUNDLE,
    "crucible-report-python",
    "crucible-report-rust",
)

# Bundles that talk to Crucible over the v2 HTTP API and own NO CLI client.
# EMPTY as of CR-MDB-024 \u00a7S3 (this cycle, C2 RED, 2026-09-22 VS Code ruling):
# the sole exemption, the VS Code crucible-report bundle, is retired outright rather
# than migrated -- an IDE is not a stack, so there is no CLI-client-less
# report bundle left to exempt. Left as an empty tuple (not deleted) so the
# `_is_exempt`/`named` call sites below stay syntactically valid without a
# structural rewrite.
API_PATH_BUNDLES = ()

# The five per-stack report bundles carry the tier vocabulary.
REPORT_BUNDLE_PREFIX = "crucible-report-"

# ------------------------------------------------- the register-flag surface ---

# The retired register flag, its CR-MDB-023 `rust-code-health.py snapshot
# --phase` exemption and the check itself live in tests/_helpers.py.

# CR-MDB-023 detector lines: the retired register flag, the exempt snapshot
# flag, and both on one line (which must still bite).
FIXTURE_LINE_SNAPSHOT_PHASE = (
    "python3 ~/.agents/scripts/rust-code-health.py snapshot --phase post --slice CR-X"
)
FIXTURE_LINE_SNAPSHOT_AND_RETIRED = (
    FIXTURE_LINE_SNAPSHOT_PHASE
    + " && python3 clients/" "rust-crucible.py register --agent X --phase RED"
)

# Case-exact: five uppercase, `report` lowercase.
ROLE_ENUM = ("RED", "GREEN", "FIX", "VERIFY", "ORCHESTRATOR", "report")

# The roles the SERVER refuses (409) when they register without a cycle binding.
TDD_ROLES = ("RED", "GREEN", "FIX", "VERIFY")

REGISTER_EXAMPLE_RE = re.compile(r"[\w./~$-]*-crucible\.py[`'\"]?\s+register\b")
ROLE_FLAG_RE = re.compile(r"--role[=\s]+([A-Za-z-]+)")
# Word-bounded on BOTH sides: `--cycles` (the plan-file flag) must not satisfy
# the binding gate, and neither must `--cycle-kind` (the plan-file pair flag),
# which a bare `\b` accepted because `-` is already a non-word character.
CYCLE_FLAG_RE = re.compile(r"--cycle(?![\w-])")

# Finding codes returned by `_register_flag_findings`.
FINDING_RETIRED_FLAG = "retired-flag"
FINDING_MISSING_ROLE = "missing-role"
FINDING_ROLE_OUT_OF_ENUM = "role-out-of-enum"
FINDING_MISSING_CYCLE = "missing-cycle"

# ------------------------------------------- the register BODY surface ---
#
# Not every register example is a command line.  `crucible-register` and the
# python/rust bundles' fallback snippets post the payload directly, and the
# wire keys `role` / `cycleId` are the exact equivalents of `--role` /
# `--cycle`.  CR-MDB-017 V1: the CLI families above matched none of them, so
# a body carrying NEITHER key -- which the released server rejects -- shipped
# green.  This family closes that blind spot.
REGISTER_API_PATH = "/api/v2/agents/register"

# A body example is a register-path occurrence INSIDE a fenced code block whose
# window carries a quoted `agentId` key -- i.e. an actual payload.  A row in an
# endpoint-reference table names the same route in markdown prose, outside any
# fence, and is correctly not an example.  The window reaches BOTH ways within
# its block: a payload is as often assembled into a variable above the POST as
# written inline below it.
BODY_AGENT_KEY_RE = re.compile(r"[\"']agentId[\"']\s*:")
BODY_ROLE_KEY_RE = re.compile(r"[\"']role[\"']\s*:")
BODY_CYCLE_KEY_RE = re.compile(r"[\"']cycleId[\"']\s*:")
# A TDD role stated as a literal value; a variable or placeholder is not one.
BODY_TDD_ROLE_RE = re.compile(
    r"[\"']role[\"']\s*:\s*[\"'](" + "|".join(TDD_ROLES) + r")[\"']"
)
BODY_WINDOW_LINES = 12
FENCE_RE = re.compile(r"^[ \t]*```")

FINDING_BODY_MISSING_ROLE = "body-missing-role"
FINDING_BODY_MISSING_CYCLE = "body-missing-cycle"

# ------------------------------------------------------ endpoints and verbs ---

# Per-bundle v2 truth ("S5): each owned bundle's OWN measured endpoint floor,
# not a fleet minimum.  The old two-route constant let the five richer bundles
# silently drop the agents/events/projects routes they document and still pass;
# arduino's entry is its true two.  Measured from each SKILL.md 2026-09-21.
# `crucible-register` additionally documents the agents touch route; it is
# omitted here only because tests/test_skills_handover.py:294 owns that family
# and this module may not re-assert it.
V2_ENDPOINTS_BY_BUNDLE = {
    "crucible-register": (
        "/api/v2/runs",
        "/api/v2/runs/parsed",
        "/api/v2/runs/compile",
        "/api/v2/agents",
        "/api/v2/agents/register",
        "/api/v2/agents/unregister",
        "/api/v2/events",
        "/api/v2/projects",
    ),
    "crucible-report-arduino": (
        "/api/v2/runs/parsed",
        "/api/v2/runs/compile",
    ),
    "crucible-report-bun": (
        "/api/v2/runs",
        "/api/v2/runs/parsed",
        "/api/v2/runs/compile",
        "/api/v2/agents",
        "/api/v2/agents/register",
        "/api/v2/agents/unregister",
        "/api/v2/events",
        "/api/v2/projects",
    ),
    "crucible-report-java": (
        "/api/v2/runs",
        "/api/v2/runs/parsed",
        "/api/v2/runs/compile",
        "/api/v2/agents",
        "/api/v2/agents/register",
        "/api/v2/agents/unregister",
        "/api/v2/events",
        "/api/v2/projects",
    ),
    "crucible-report-python": (
        "/api/v2/runs",
        "/api/v2/runs/parsed",
        "/api/v2/runs/compile",
        "/api/v2/agents/register",
        "/api/v2/agents/unregister",
        "/api/v2/projects",
    ),
    "crucible-report-rust": (
        "/api/v2/runs",
        "/api/v2/runs/parsed",
        "/api/v2/runs/compile",
        "/api/v2/agents",
        "/api/v2/agents/register",
        "/api/v2/agents/unregister",
        "/api/v2/events",
        "/api/v2/projects",
    ),
}

# The two routes every owned bundle posts to, whatever else it documents --
# the floor of the floors, asserted so a per-bundle entry cannot be emptied.
V2_ENDPOINTS_UNIVERSAL = ("/api/v2/runs/parsed", "/api/v2/runs/compile")

# The v1 ingest route. Present only inside an explicit retired/legacy note.
V1_ENDPOINT = "/api/ingest"
LEGACY_MARKER_RE = re.compile(r"legacy|shim|retired|v1\b", re.IGNORECASE)
LEGACY_LOOKBACK_LINES = 15

TIER_RE = re.compile(r"\btier\b", re.IGNORECASE)

# Verbs the released client fleet exposes, completed 2026-09-21 as the UNION of
# the five installed clients' own subparser lists (44 verbs: the shared
# lifecycle/tier/plan set plus rust's clippy/workspace verbs and java's docker
# ones).  It is a vocabulary of OUR OWN text's subcommands, not a mirror of
# Crucible's FLAG surface -- the module still reads no client at run time.
# The previous 17-entry list was hand-picked from this CR's prose and missed
# `cr-plan`, which skills-src/memory-templates/rust-orchestration.md:21 uses.
# `gate-report` is listed because it EXISTS; naming it as the gate verb is a
# separate prohibition, owned by tests/test_client_verb_sweep.py.
CLIENT_VERBS = (
    "abort",
    "auto-ingest",
    "bdd",
    "check",
    "checkpoint",
    "clippy",
    "compile",
    "cr-close",
    "cr-depends",
    "cr-plan",
    "cr-supersede",
    "cr-void",
    "cycle-activate",
    "cycle-add",
    "cycle-done",
    "docker-down",
    "docker-e2e-gate",
    "docker-up",
    "e2e",
    "gate-report",
    "gate-run",
    "integration",
    "milestone",
    "module",
    "next",
    "plan-backfill",
    "plan-file",
    "plans",
    "pre-merge-gate",
    "queue",
    "queue-file",
    "register",
    "regression",
    "regression-ingest",
    "release-propose",
    "smoke-test",
    "status",
    "stop",
    "test",
    "unit",
    "unregister",
    "wave-sequence",
    "workspace-clippy",
    "workspace-regression",
)
# NO LINE ANCHOR.  The anchored form reached only the 32 invocations that begin
# their line, so 12 of the 44 under skills-src/ were never scanned at all --
# ordered-list items (`1. \`mvn-crucible.py regression\``), mid-sentence prose
# citations, and inline backticked references.  An invocation in prose teaches
# a verb exactly as loudly as one in a fenced block.
CLIENT_INVOCATION_RE = re.compile(
    r"[\w./~$-]*-crucible\.py[ \t]+([a-z][a-z0-9-]*)"
)

# ----------------------------------------------------------- fixture inputs ---

# Genuine register examples, each carrying exactly one defect. The first is the
# historic pre-CR-MDB-017 form the bundles actually shipped.
FIXTURE_LINE_RETIRED_FLAG = (
    "python3 clients/" "arduino-crucible.py register --agent AGENT_ID --phase RED"
)
FIXTURE_LINE_NO_ROLE = (
    "python3 clients/" "bun-crucible.py register --agent AGENT_ID --cycle 60"
)
FIXTURE_LINE_BAD_ROLE = (
    "python3 clients/" "mvn-crucible.py register --agent AGENT_ID --role red --cycle 60"
)
FIXTURE_LINE_NO_CYCLE = (
    "python3 clients/" "python-crucible.py register --agent AGENT_ID --role GREEN"
)
FIXTURE_LINE_CLEAN = (
    "python3 clients/" "rust-crucible.py register --agent AGENT_ID --role VERIFY --cycle 60"
)

# Register BODY fixtures -- the wire-key equivalents of the four above. The
# first is the exact shape `crucible-register` shipped until CR-MDB-017 V1:
# a payload the released server rejects, which every CLI family passed over.
FIXTURE_BODY_NO_ROLE = """curl -s -X POST http://localhost:3849/api/v2/agents/register \\
  -d '{"agentId":"AGENT_ID","projectKey":"KEY","status":"online"}'"""
FIXTURE_BODY_TDD_NO_CYCLE = """curl -s -X POST http://localhost:3849/api/v2/agents/register \\
  -d '{"agentId":"AGENT_ID","projectKey":"KEY","role":"RED","status":"online"}'"""
FIXTURE_BODY_CLEAN = """curl -s -X POST http://localhost:3849/api/v2/agents/register \\
  -d '{"agentId":"AGENT_ID","projectKey":"KEY","role":"RED","cycleId":"60","status":"online"}'"""
# An unbound registration is LEGAL for the two non-TDD roles, so the body
# family must not report it -- otherwise it would forbid what the server allows.
FIXTURE_BODY_CLEAN_UNBOUND = """curl -s -X POST http://localhost:3849/api/v2/agents/register \\
  -d '{"agentId":"AGENT_ID","projectKey":"KEY","role":"ORCHESTRATOR","status":"online"}'"""
# An endpoint-reference table row names the path but carries no payload; it is
# not an example and must not be reported.
FIXTURE_BODY_TABLE_ROW = (
    "| `/api/v2/agents/register` | POST | Register/touch agent (upsert) |"
)

FIXTURE_BUNDLE_NAME = "crucible-report-fixture"
FIXTURE_BODY = """# Fixture bundle

## Register

```bash
{line}
```
"""


# ---------------------------------------------------------------- helpers ----


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
            if _carries_retired_register_flag(line):
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
    findings.extend(_register_body_findings(root))
    return findings


def _fenced_block_spans(lines):
    """[(start, end)] half-open line-index spans of every fenced code block."""
    spans = []
    start = None
    for index, line in enumerate(lines):
        if not FENCE_RE.match(line):
            continue
        if start is None:
            start = index + 1
        else:
            spans.append((start, index))
            start = None
    if start is not None:  # unterminated fence: treat the tail as the block
        spans.append((start, len(lines)))
    return spans


def _register_body_examples(root, include_exempt=False):
    """Every register BODY example under `root` as (relpath, lineno, window).

    Scoped to fenced code blocks: a register route named in a markdown table or
    a sentence is documentation, not an executable example, and carries no
    payload obligation.  Inside a block the window spans both directions so a
    payload built into a variable above the POST is seen.
    """
    found = []
    for path in _iter_files(root):
        if not include_exempt and _is_exempt(path, root):
            continue
        lines = _read(path).splitlines()
        spans = _fenced_block_spans(lines)
        for index, line in enumerate(lines):
            if REGISTER_API_PATH not in line:
                continue
            block = next(
                ((s, e) for s, e in spans if s <= index < e), None
            )
            if block is None:
                continue
            start = max(block[0], index - BODY_WINDOW_LINES)
            end = min(block[1], index + BODY_WINDOW_LINES)
            window = "\n".join(lines[start:end])
            if BODY_AGENT_KEY_RE.search(window):
                found.append((_rel(path, root), index + 1, window))
    return found


def _register_body_findings(root):
    """Register-BODY defects under `root`, as (code, detail).

    The wire-key half of the checker: `role` is the equivalent of `--role` and
    `cycleId` of `--cycle`, and the server rejects a body missing either one
    for a TDD role exactly as it rejects the command line.
    """
    findings = []
    for rel, lineno, window in _register_body_examples(root):
        first = next(
            (
                line.strip()
                for line in window.splitlines()
                if REGISTER_API_PATH in line
            ),
            window.splitlines()[0].strip(),
        )
        if not BODY_ROLE_KEY_RE.search(window):
            findings.append(
                (FINDING_BODY_MISSING_ROLE, f"{rel}:{lineno}: {first}")
            )
            continue
        match = BODY_TDD_ROLE_RE.search(window)
        if match and not BODY_CYCLE_KEY_RE.search(window):
            findings.append(
                (
                    FINDING_BODY_MISSING_CYCLE,
                    f"{rel}:{lineno}: role {match.group(1)} — {first}",
                )
            )
    return findings


def _documents_endpoint(text, endpoint):
    """True when `text` names `endpoint` as a route in its own right.

    Matched with a trailing path-boundary so `/api/v2/agents` is not satisfied
    by `/api/v2/agents/register` -- without it every shorter route in the
    per-bundle map would pass on a longer one's prefix.
    """
    return re.search(re.escape(endpoint) + r"(?![\w/-])", text) is not None


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
            "the owned bundle set measured from skills-src/ must be the six of "
            f"CR-MDB-024 §S3 (CR-MDB-016 §S1's original seven, less the retired "
            f"VS Code bundle); measured {list(measured)} against named {list(named)}. "
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

    def test_fixture_rust_code_health_snapshot_phase_is_exempt_from_retired_flag(self):
        # CR-MDB-023: the exemption spares ONLY `rust-code-health.py snapshot
        # --phase`; the retired register flag bites alone and alongside it.
        cases = (
            (FIXTURE_LINE_RETIRED_FLAG, True),
            (FIXTURE_LINE_SNAPSHOT_PHASE, False),
            (FIXTURE_LINE_SNAPSHOT_AND_RETIRED, True),
        )
        for line, bites in cases:
            with self.subTest(line=line):
                with tempfile.TemporaryDirectory() as tmp:
                    root = _write_fixture_bundle(tmp, line)
                    findings = _register_flag_findings(root)
                self.assertEqual(
                    FINDING_RETIRED_FLAG in _codes(findings),
                    bites,
                    f"retired-flag finding expected={bites}; checker returned "
                    f"{_codes(findings)} for: {line}",
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

    # CR-MDB-024 \u00a7S3 (this cycle, C2 RED, 2026-09-22 VS Code ruling):
    # test_exempt_bundle_fixture_is_excluded_from_the_register_families is
    # DELETED, not migrated -- API_PATH_BUNDLES is now empty (the bundle it
    # exempted is retired outright), so there is no exempt-bundle fixture
    # case left to construct or prove excluded.


class RegisterBodySurfaceTest(unittest.TestCase):
    """The HTTP-BODY half of the register surface (CR-MDB-017 V1).

    `crucible-register` sat in no category at all: it owns no CLI client, so
    every CLI family matched nothing in it and it passed by incidental
    zero-match -- while shipping a `POST /api/v2/agents/register` body with
    neither `role` nor `cycleId`, which the released server rejects.  That is
    the exact failure mode the register-flag families exist to forbid, so the
    wire keys are gated with the same force as the flags.
    """

    def setUp(self):
        self.examples = _register_body_examples(SKILLS_SRC)
        self.findings = _register_body_findings(SKILLS_SRC)

    def test_body_bundles_are_named_and_each_contributes_a_body_example(self):
        for bundle in HTTP_BODY_BUNDLES:
            self.assertTrue(
                (SKILLS_SRC / bundle).is_dir(),
                f"HTTP_BODY_BUNDLES names {bundle!r}, which does not exist under "
                "skills-src/; a stale category gates nothing.",
            )
        self.assertIn(
            REGISTER_BUNDLE,
            HTTP_BODY_BUNDLES,
            f"{REGISTER_BUNDLE!r} must sit in a category this module asserts "
            "about. Before CR-MDB-017 V1 it was in none, so it passed every "
            "family by matching nothing.",
        )
        contributors = {rel.split("/", 1)[0] for rel, _, _ in self.examples}
        missing = sorted(b for b in HTTP_BODY_BUNDLES if b not in contributors)
        self.assertEqual(
            missing,
            [],
            "every body-surface bundle must contribute at least one register "
            f"payload example, or this family passes it vacuously: {missing}",
        )

    def test_every_register_body_example_carries_a_role_key(self):
        hits = [
            detail
            for code, detail in self.findings
            if code == FINDING_BODY_MISSING_ROLE
        ]
        self.assertEqual(
            hits,
            [],
            "every register payload under skills-src/ must carry a `role` key "
            f"from the case-exact set {{{', '.join(ROLE_ENUM)}}}; the server "
            "rejects a body that declares none. Offenders:\n  " + "\n  ".join(hits),
        )

    def test_tdd_role_register_body_examples_carry_a_cycle_id(self):
        hits = [
            detail
            for code, detail in self.findings
            if code == FINDING_BODY_MISSING_CYCLE
        ]
        self.assertEqual(
            hits,
            [],
            "a register payload declaring one of "
            f"{{{', '.join(TDD_ROLES)}}} must also carry `cycleId`; the server "
            "rejects an unbound TDD registration. Offenders:\n  " + "\n  ".join(hits),
        )


class RegisterBodyFixtureTest(unittest.TestCase):
    """The body family is PROVEN to bite, the same way the four flag defects
    are -- against a temp fixture, never a mutation of skills-src/."""

    def test_fixture_register_body_missing_role_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_fixture_bundle(tmp, FIXTURE_BODY_NO_ROLE)
            findings = _register_flag_findings(root)
        self.assertIn(
            FINDING_BODY_MISSING_ROLE,
            _codes(findings),
            "the payload `crucible-register` shipped until CR-MDB-017 V1 declares "
            "no role and must be reported; the checker returned "
            f"{_codes(findings)}",
        )

    def test_fixture_tdd_role_register_body_missing_cycle_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_fixture_bundle(tmp, FIXTURE_BODY_TDD_NO_CYCLE)
            findings = _register_flag_findings(root)
        self.assertIn(
            FINDING_BODY_MISSING_CYCLE,
            _codes(findings),
            "a payload declaring a TDD role with no cycle binding must be "
            f"reported; the checker returned {_codes(findings)}",
        )

    def test_fixture_clean_register_bodies_are_reported_by_nothing(self):
        for label, body in (
            ("bound TDD role", FIXTURE_BODY_CLEAN),
            ("unbound non-TDD role", FIXTURE_BODY_CLEAN_UNBOUND),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                root = _write_fixture_bundle(tmp, body)
                findings = _register_flag_findings(root)
            self.assertEqual(
                findings,
                [],
                f"a correct register payload ({label}) must produce no finding, "
                f"or the two negative cases above prove nothing: {findings}",
            )

    def test_fixture_endpoint_table_row_is_not_treated_as_a_body_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_fixture_bundle(tmp, FIXTURE_BODY_TABLE_ROW)
            examples = _register_body_examples(root)
            findings = _register_flag_findings(root)
        self.assertEqual(
            examples,
            [],
            "an endpoint-reference table row names the register route in prose "
            f"and carries no payload, so it is not an example: {examples}",
        )
        self.assertEqual(
            findings,
            [],
            "documenting the route in a reference table must stay legal, or "
            f"every bundle's endpoint table becomes an offender: {findings}",
        )


# CR-MDB-024 \u00a7S3 (this cycle, C2 RED, 2026-09-22 VS Code ruling):
# ApiPathExemptionTest is DELETED, not migrated -- API_PATH_BUNDLES is now
# empty (the VS Code bundle it named is retired outright), so there is no
# exemption left to name or prove truthful.
class BundleEndpointTierAndVerbTest(unittest.TestCase):
    """Ported from the inherited Bun guard: v2-endpoint truth, no unmarked v1
    legacy, `tier` presence, and real client verbs — now including arduino."""

    def test_every_owned_bundle_documents_its_own_measured_v2_routes(self):
        """PER-BUNDLE truth, not a fleet minimum: each bundle must keep every v2
        route IT documents, so a richer bundle cannot silently shed the agents,
        events or projects routes and still pass on the two-route floor."""
        measured = _owned_bundle_names(SKILLS_SRC)
        unmapped = [b for b in measured if b not in V2_ENDPOINTS_BY_BUNDLE]
        self.assertEqual(
            unmapped,
            [],
            "every owned bundle needs its OWN measured endpoint floor in "
            f"V2_ENDPOINTS_BY_BUNDLE; unmapped: {unmapped}",
        )
        stale = [b for b in V2_ENDPOINTS_BY_BUNDLE if b not in measured]
        self.assertEqual(
            stale,
            [],
            "V2_ENDPOINTS_BY_BUNDLE names bundles that do not exist under "
            f"skills-src/; a stale entry gates nothing: {stale}",
        )
        missing = []
        for path in _owned_bundle_paths():
            text = _read(path / "SKILL.md")
            for endpoint in V2_ENDPOINTS_BY_BUNDLE[path.name]:
                if not _documents_endpoint(text, endpoint):
                    missing.append(f"{_rel(path)}/SKILL.md: {endpoint}")
        self.assertEqual(
            missing,
            [],
            "each bundle must still document every v2 route it was measured to "
            f"document; dropped: {missing}",
        )

    def test_every_bundle_floor_contains_the_universal_run_ingest_routes(self):
        """The per-bundle map cannot be emptied to make the family above pass."""
        thin = {
            bundle: list(endpoints)
            for bundle, endpoints in V2_ENDPOINTS_BY_BUNDLE.items()
            if not set(V2_ENDPOINTS_UNIVERSAL) <= set(endpoints)
        }
        self.assertEqual(
            thin,
            {},
            "every bundle's floor must contain the two run-ingest routes every "
            f"client path ultimately posts to {list(V2_ENDPOINTS_UNIVERSAL)}; "
            f"these were weakened: {thin}",
        )
        self.assertGreater(
            len(V2_ENDPOINTS_BY_BUNDLE["crucible-report-bun"]),
            len(V2_ENDPOINTS_BY_BUNDLE["crucible-report-arduino"]),
            "the richer bundles must carry a STRICTLY larger floor than "
            "arduino's true two, or the map has collapsed back into the fleet "
            "minimum it replaced.",
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
            5,
            "the five per-stack report bundles must all be measured; found "
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
