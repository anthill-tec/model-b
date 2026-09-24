"""The ambient hook renders the current Crucible status contract (CR-MDB-019
§S1–§S5): the 2.0.0 document pin, ``lastClosedCr``, open plans only,
unquoted cells, and arduino sketch projects.

Target: ``hooks-src/scripts/ambient-board-status``.

Sandbox discipline (AC "All")
-----------------------------
Every behavioural case runs the REAL hook as a subprocess (``sys.executable``
+ the script path) with ``HOME`` pointed at a temp directory, ``MODELB_HOME``
removed, and ``cwd`` a temp directory. Discovery cases (§S3 end to end, §S5)
also remove ``MODELB_STATUS_CMD`` and resolve the feed from a fixture
``$HOME/.crucible/crucible-clients.json``; rendering-only cases point
``MODELB_STATUS_CMD`` at a fixture client instead. The real ``~/.crucible``
is never read and no Crucible checkout is loaded: every fixture envelope is
built with Model B's own ``modelb_axi.toon``. Each fixture client appends
``{"key", "argv"}`` to a per-test invocation log, so "which client ran" and
"no client ran" are assertable.

Rendering contract pinned here
------------------------------
* §S1 — ``STATUS_CONTRACT_VERSION == "2.0.0"``; the hook source carries no
  ``1.0.0``; the module docstring names the axis (the ``status`` envelope
  contract DOCUMENT) and says the number is not a Crucible product release;
  the "output did not match" degrade note names ``2.0.0``.
* §S2 — a CR id in ``lastClosedCr`` renders as the line
  ``last closed: <id>`` (the spec's own example spelling), exactly once;
  ``null`` renders no ``last closed`` line; the hook's code (string literals
  outside docstrings) never names ``lastRunCr``, and a stray ``lastRunCr``
  field in a feed is not rendered.
* §S3 — rows whose ``status`` is ``closed`` are neither listed (``cr=<id>``
  rows) nor counted: the heading's ``<N> open plan`` count is the number of
  open rows. A board whose rows are all closed prints a note containing the
  stable phrase ``no open plan`` (case-insensitive), exactly once, exits 0,
  and prints neither ``no plan filed`` nor a degrade/``unavailable`` note.
  ``no plan filed`` and the ``status-unavailable`` degrade render as before.
* §S4 — a table cell wrapped in double quotes renders without them
  (``wave=1`` / ``activeCycleId=125``, never ``wave="1"``).

§S5 — the arduino sketch marker contract
----------------------------------------
``_STACK_MARKERS`` stays an ordered sequence of
``(marker_filename, stack, manifest_key)`` ``str`` 3-tuples (CR-MDB-018 §S3).
A ``marker_filename`` MAY be a template carrying the literal placeholder
``{dir}``; at each candidate directory walking up from the cwd the hook
replaces ``{dir}`` with THAT directory's own name before testing for the
file. The arduino entry is exactly::

    ("{dir}.ino", "arduino", "arduino")

and it is the only entry carrying ``{dir}``; every other marker is a literal
file name. So ``sheetal-firmware/sheetal-firmware.ino`` marks
``sheetal-firmware/`` as arduino (the arduino-cli sketch rule), while a
``blink.ino`` in ``firmware/`` — or a file literally named ``{dir}.ino`` —
marks nothing. The nearest marker still wins.
"""

import ast
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from modelb_axi import toon  # noqa: E402
from modelb_axi.requirements import STACK_CLIENT_KEYS  # noqa: E402

HOOK_PATH = REPO_ROOT / "hooks-src" / "scripts" / "ambient-board-status"
MANIFEST_RELPATH = Path(".crucible") / "crucible-clients.json"

#: The arduino sketch entry the hook's marker table must carry (§S5).
ARDUINO_MARKER_ENTRY = ("{dir}.ino", "arduino", "arduino")
#: The five ``clients`` keys of Crucible's manifest (§S5 AC).
MANIFEST_KEYS = ("arduino", "bun", "mvn", "python", "rust")
#: A literal marker file for each non-arduino manifest key.
LITERAL_MARKER_FOR_KEY = {
    "rust": "Cargo.toml",
    "mvn": "pom.xml",
    "bun": "bun.lock",
    "python": "pyproject.toml",
}

LAST_CLOSED = "CR-X-001"
#: The phrase pinned for the all-plans-closed note (§S3).
NO_OPEN_PLAN = "no open plan"
NO_PLAN_FILED = "no plan filed"


# ---------------------------------------------------------------------------
# fixture envelopes (modelb_axi.toon only)
# ---------------------------------------------------------------------------

def _plan(cr: str, status: str, *, wave: int | str = 1,
          cycle: str | None = "C1") -> dict:
    return {"cr": cr, "wave": wave, "status": status, "activeCycleId": cycle}


def _envelope(plans: list[dict], *, last_closed=None, count=None,
              warnings: list[dict] | None = None, extra: dict | None = None) -> str:
    """A STATUS-CONTRACT 2.0.0 ``status`` envelope. ``count`` defaults to
    the number of rows (the live verb counts every row it returns)."""
    axi = {
        "verb": "status",
        "ok": True,
        "plans": plans,
        "lastClosedCr": last_closed,
        "count": len(plans) if count is None else count,
        "help": ["cr-close --commit"],
        "context": {"projectKey": "fixture-project-key"},
        "warnings": warnings or [],
    }
    axi.update(extra or {})
    return toon.encode({"axi": axi})


#: A board with one open plan, used where only "the board rendered" matters.
FIXTURE_CR = "CR-MDB-019"
DEFAULT_ENVELOPE = _envelope([_plan(FIXTURE_CR, "open", wave=2, cycle="C1")],
                             last_closed=LAST_CLOSED)


def _client_source(key: str, log_path: Path, envelope: str) -> str:
    """An executable fixture client: logs its key + argv, prints
    ``envelope``, exits 0."""
    return (
        f"#!{sys.executable}\n"
        "import json, sys\n"
        f"with open({str(log_path)!r}, 'a', encoding='utf-8') as fh:\n"
        f"    fh.write(json.dumps({{'key': {key!r}, 'argv': sys.argv[1:]}}) + '\\n')\n"
        f"print({envelope!r})\n"
    )


# ---------------------------------------------------------------------------
# sandbox
# ---------------------------------------------------------------------------

class _Sandbox:
    """A temp HOME, a temp project dir and an invocation log."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="mdb-019-ambient-"))
        self.home = self.root / "home"
        self.home.mkdir()
        self.project = self.root / "project"
        self.project.mkdir()
        self.log = self.root / "invocations.jsonl"
        self.manifest = self.home / MANIFEST_RELPATH

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write_client(self, key: str, where: Path, envelope: str = DEFAULT_ENVELOPE) -> Path:
        where.mkdir(parents=True, exist_ok=True)
        path = where / f"{key}-crucible.py"
        path.write_text(_client_source(key, self.log, envelope), encoding="utf-8")
        path.chmod(0o755)
        return path

    def write_manifest(self, clients: dict) -> Path:
        """A manifest shaped like Crucible's real one."""
        self.manifest.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "clients": {k: str(v) for k, v in clients.items()},
            "version": "0.2.2",
            "status": "installed",
            "config": str(self.home / ".crucible" / "crucible.toml"),
            "server_config": str(self.home / ".crucible" / "server.toml"),
            "shipped_config": str(self.home / ".crucible" / "shipped.toml"),
        }
        self.manifest.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        return self.manifest

    def write_all_clients_manifest(self, envelope: str = DEFAULT_ENVELOPE) -> None:
        released = self.root / "released"
        self.write_manifest({k: self.write_client(k, released / k, envelope)
                             for k in MANIFEST_KEYS})

    @staticmethod
    def touch(path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return path

    def invocations(self) -> list[dict]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in
                self.log.read_text(encoding="utf-8").splitlines() if line.strip()]

    def run_hook(self, *, cwd: Path | None = None,
                 env_overrides: dict | None = None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.pop("MODELB_STATUS_CMD", None)
        env.pop("MODELB_HOME", None)
        env["HOME"] = str(self.home)
        env.update(env_overrides or {})
        return subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="{}", capture_output=True, text=True, timeout=15,
            cwd=str(cwd if cwd is not None else self.project), env=env,
        )


def _listed_crs(stdout: str) -> list[str]:
    """The ``cr=<id>`` plan rows the hook listed, in order."""
    return re.findall(r"\bcr=(\S+)", stdout)


def _heading_counts(stdout: str) -> list[str]:
    """Every ``<N> open plan`` count the hook printed."""
    return re.findall(r"(\d+) open plan", stdout)


class _SandboxCase(unittest.TestCase):
    def setUp(self):
        self.assertTrue(HOOK_PATH.is_file(), f"expected the hook at {HOOK_PATH}")
        self.sb = _Sandbox()
        self.addCleanup(self.sb.cleanup)

    def render(self, envelope: str) -> subprocess.CompletedProcess:
        """Run the real hook against a fixture feed through the
        ``MODELB_STATUS_CMD`` seam; asserts the fixture ran exactly once and
        the hook exited 0 (every path exits 0, §S3)."""
        client = self.sb.write_client("feed", self.sb.root / "feed-bin", envelope)
        result = self.sb.run_hook(env_overrides={"MODELB_STATUS_CMD": f"{client} status"})
        self.assertEqual(result.returncode, 0,
                         f"a SessionStart hook always exits 0; stderr={result.stderr!r}")
        self.assertEqual(self.sb.invocations(), [{"key": "feed", "argv": ["status"]}],
                         "precondition: the fixture feed ran exactly once")
        return result

    def assert_resolved_to(self, result, key: str):
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr!r}")
        self.assertNotIn("degrad", result.stdout.lower(),
                         f"expected the board, not a degrade note; got {result.stdout!r}")
        self.assertEqual(_listed_crs(result.stdout), [FIXTURE_CR],
                         f"the fixture board's open plan is listed; got {result.stdout!r}")
        self.assertEqual(self.sb.invocations(), [{"key": key, "argv": ["status"]}],
                         f"exactly one client — clients[{key!r}] — run with `status`")

    def assert_no_marker(self, result):
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr!r}")
        self.assertIn("degrad", result.stdout.lower(),
                      f"no marker resolves -> a degrade note; got {result.stdout!r}")
        self.assertIn("no stack marker", result.stdout,
                      f"the degrade is the no-marker one; got {result.stdout!r}")
        self.assertEqual(_listed_crs(result.stdout), [])
        self.assertEqual(self.sb.invocations(), [], "no client may be invoked")


# ---------------------------------------------------------------------------
# hook-source helpers
# ---------------------------------------------------------------------------

def _hook_source() -> str:
    return HOOK_PATH.read_text(encoding="utf-8")


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                ids.add(id(body[0].value))
    return ids


def _code_string_literals(source: str) -> list[str]:
    """Every string constant in ``source`` except docstrings."""
    tree = ast.parse(source)
    skip = _docstring_nodes(tree)
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in skip]


def _load_hook_module():
    """Load the hook as a module without writing bytecode beside it."""
    loader = importlib.machinery.SourceFileLoader("ambient_board_status_hook_019",
                                                  str(HOOK_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None, f"could not build a module spec for {HOOK_PATH}"
    module = importlib.util.module_from_spec(spec)
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("`", "")).lower()


#: A line reading 2.0.0 as a Crucible PRODUCT/release version (the same
#: detector CR-MDB-024's envelope-contract gate uses).
_PRODUCT_CLAIM = re.compile(
    r"(?i)(crucible\s+v?2\.0\.0|product\s+version[^\n]{0,40}2\.0\.0|"
    r"release\s+2\.0\.0|2\.0\.0\s+release)"
)


# ---------------------------------------------------------------------------
# §S1 — pin the current contract document
# ---------------------------------------------------------------------------

class StatusContractPinS1Test(unittest.TestCase):
    """§S1: the 2.0.0 pin and the axis it names."""

    def test_s1_hook_source_contains_no_1_0_0(self):
        hits = [f"{n}: {line.strip()}" for n, line in
                enumerate(_hook_source().splitlines(), 1) if "1.0.0" in line]
        self.assertEqual(hits, [], "the superseded 1.0.0 pin/citations must be gone")

    def test_s1_status_contract_version_is_2_0_0(self):
        self.assertEqual(getattr(_load_hook_module(), "STATUS_CONTRACT_VERSION", None),
                         "2.0.0")

    def test_s1_module_docstring_names_the_status_envelope_contract_document_axis(self):
        doc = ast.get_docstring(ast.parse(_hook_source())) or ""
        norm = _normalise(doc)
        self.assertIn("2.0.0", doc, "the docstring cites the contract version in force")
        self.assertRegex(norm, r"status envelope contract document",
                         "the docstring names the axis: Crucible's `status` envelope "
                         "contract document")
        self.assertRegex(norm, r"\bnot\b[^.;]{0,60}\bproduct (release|version)",
                         "the docstring says the number is not a Crucible product release")

    def test_s1_hook_never_reads_2_0_0_as_a_crucible_product_version(self):
        """Passes by design at RED (no 2.0.0 yet); guards the GREEN wording."""
        offenders = [line.strip() for line in _hook_source().splitlines()
                     if _PRODUCT_CLAIM.search(line)]
        self.assertEqual(offenders, [])

    def test_s1_detector_bites_on_a_product_version_claim(self):
        self.assertTrue(_PRODUCT_CLAIM.search("authored against Crucible 2.0.0"))
        self.assertTrue(_PRODUCT_CLAIM.search("the 2.0.0 release of the server"))
        self.assertFalse(_PRODUCT_CLAIM.search(
            "status envelope contract document 2.0.0, not a product release"))


class StatusContractDegradeS1Test(_SandboxCase):
    """§S1: the pin exists so a degrade note names the contract in force."""

    def test_s1_unmatched_feed_output_degrade_note_names_2_0_0(self):
        result = self.render("this is not a status envelope")
        self.assertIn("degrad", result.stdout.lower(),
                      f"unmatched output degrades; got {result.stdout!r}")
        self.assertIn("2.0.0", result.stdout,
                      f"the degrade note names contract 2.0.0; got {result.stdout!r}")
        self.assertNotIn("1.0.0", result.stdout)


# ---------------------------------------------------------------------------
# §S2 — render lastClosedCr
# ---------------------------------------------------------------------------

class LastClosedCrS2Test(_SandboxCase):
    """§S2: ``lastClosedCr`` renders as ``last closed: <id>``; ``null`` renders
    nothing; ``lastRunCr`` is no longer read."""

    def test_s2_last_closed_cr_id_is_printed_once_as_a_last_closed_line(self):
        result = self.render(_envelope([_plan("CR-T-001", "open")],
                                       last_closed=LAST_CLOSED))
        self.assertIn(f"last closed: {LAST_CLOSED}", result.stdout)
        self.assertEqual(result.stdout.lower().count("last closed"), 1,
                         f"exactly one last-closed line; got {result.stdout!r}")

    def test_s2_last_closed_cr_is_printed_even_when_no_plan_is_open(self):
        result = self.render(_envelope(
            [_plan("CR-T-001", "closed"), _plan(LAST_CLOSED, "closed")],
            last_closed=LAST_CLOSED))
        self.assertIn(f"last closed: {LAST_CLOSED}", result.stdout)

    def test_s2_null_last_closed_cr_prints_no_last_closed_line(self):
        """Passes by design at RED (nothing reads the field yet); pins that
        GREEN never renders ``null`` as a last-closed id."""
        result = self.render(_envelope([_plan("CR-T-001", "open", cycle="C1")],
                                       last_closed=None))
        self.assertIn("lastClosedCr: null", _envelope([], last_closed=None),
                      "precondition: the fixture carries an explicit null")
        self.assertNotIn("last closed", result.stdout.lower())
        self.assertNotIn("null", result.stdout)
        self.assertEqual(_listed_crs(result.stdout), ["CR-T-001"])

    def test_s2_a_legacy_last_run_cr_field_is_not_rendered(self):
        result = self.render(_envelope([_plan("CR-T-001", "open")], last_closed=None,
                                       extra={"lastRunCr": "CR-OLD-999"}))
        self.assertNotIn("CR-OLD-999", result.stdout,
                         f"lastRunCr is gone from the contract; got {result.stdout!r}")
        self.assertNotIn("lastRunCr", result.stdout)

    def test_s2_hook_code_does_not_read_last_run_cr(self):
        hits = [s for s in _code_string_literals(_hook_source()) if "lastRunCr" in s]
        self.assertEqual(hits, [], f"the hook still looks for lastRunCr: {hits!r}")


# ---------------------------------------------------------------------------
# §S3 — show open plans only
# ---------------------------------------------------------------------------

MIXED_PLANS = [
    _plan("CR-T-001", "open", cycle="C1"),
    _plan("CR-T-002", "closed", cycle=None),
    _plan("CR-T-003", "open", cycle="C3"),
    _plan("CR-T-004", "closed", cycle=None),
]


class OpenPlansOnlyS3Test(_SandboxCase):
    """§S3: closed rows are not listed or counted; an all-closed board prints
    a distinct "no open plan" note; the three terminal states stay distinct."""

    def test_s3_mixed_board_lists_only_the_open_rows(self):
        result = self.render(_envelope(MIXED_PLANS, last_closed="CR-T-900"))
        self.assertEqual(_listed_crs(result.stdout), ["CR-T-001", "CR-T-003"])
        self.assertNotIn("CR-T-002", result.stdout)
        self.assertNotIn("CR-T-004", result.stdout)
        self.assertNotIn("status=closed", result.stdout)

    def test_s3_heading_counts_only_the_open_rows(self):
        result = self.render(_envelope(MIXED_PLANS, count=4))
        self.assertEqual(_heading_counts(result.stdout), ["2"],
                         f"the heading counts 2 open rows, not 4; got {result.stdout!r}")

    def test_s3_all_closed_board_prints_the_no_open_plan_note_only(self):
        result = self.render(_envelope(
            [_plan("CR-T-010", "closed", cycle=None),
             _plan("CR-T-011", "closed", cycle=None),
             _plan("CR-T-012", "closed", cycle=None)], last_closed=None))
        lowered = result.stdout.lower()
        self.assertEqual(lowered.count(NO_OPEN_PLAN), 1,
                         f"exactly one 'no open plan' note; got {result.stdout!r}")
        self.assertNotIn(NO_PLAN_FILED, lowered, "distinct from 'no plan filed'")
        self.assertNotIn("degrad", lowered, "an all-closed board is not a degrade")
        self.assertNotIn("unavailable", lowered, "nor the status-unavailable degrade")
        self.assertEqual(_listed_crs(result.stdout), [], "no closed row is listed")
        self.assertEqual(_heading_counts(result.stdout), [],
                         "no '<N> open plan(s)' heading for a board with none open")

    def test_s3_no_plan_filed_still_renders_distinctly(self):
        """Passes by design at RED; pins the unchanged terminal state."""
        result = self.render(_envelope([], last_closed=None, count=0))
        lowered = result.stdout.lower()
        self.assertIn(NO_PLAN_FILED, lowered)
        self.assertNotIn(NO_OPEN_PLAN, lowered)
        self.assertNotIn("degrad", lowered)
        self.assertNotIn("unavailable", lowered)

    def test_s3_status_unavailable_still_renders_as_the_tolerant_degrade(self):
        """Passes by design at RED; pins the unchanged terminal state."""
        result = self.render(_envelope(
            [], last_closed=None, count=0,
            warnings=[{"code": "status-unavailable",
                       "detail": "could not reach the Crucible server"}]))
        lowered = result.stdout.lower()
        self.assertIn("status-unavailable", result.stdout)
        self.assertIn("could not reach the crucible server", lowered)
        self.assertNotIn(NO_PLAN_FILED, lowered)
        self.assertNotIn(NO_OPEN_PLAN, lowered)

    def test_s3_manifest_resolved_board_lists_open_plans_unquoted_with_last_closed(self):
        """End to end through the production seam: manifest + python marker,
        MODELB_STATUS_CMD unset, a live-shaped board (quoted cells, closed
        rows, lastClosedCr)."""
        envelope = _envelope(
            [_plan("CR-L-001", "open", wave="1", cycle="125"),
             _plan("CR-L-002", "closed", wave="1", cycle=None),
             _plan("CR-L-003", "closed", wave="2", cycle=None)],
            last_closed="CR-L-003")
        self.assertIn('"1"', envelope, "precondition: toon quotes numeric-looking strings")
        released = self.sb.root / "released"
        self.sb.write_manifest({"python": self.sb.write_client("python", released, envelope)})
        self.sb.touch(self.sb.project / "pyproject.toml")
        result = self.sb.run_hook()
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr!r}")
        self.assertEqual(self.sb.invocations(), [{"key": "python", "argv": ["status"]}])
        self.assertEqual(_listed_crs(result.stdout), ["CR-L-001"])
        self.assertEqual(_heading_counts(result.stdout), ["1"])
        self.assertIn("last closed: CR-L-003", result.stdout)
        self.assertNotIn('"', result.stdout, f"no quoted cell leaks; got {result.stdout!r}")


# ---------------------------------------------------------------------------
# §S4 — unquote cells
# ---------------------------------------------------------------------------

class UnquotedCellsS4Test(_SandboxCase):
    """§S4: a cell wrapped in double quotes renders without them."""

    def test_s4_quoted_wave_cell_renders_unquoted(self):
        envelope = _envelope([_plan("CR-Q-001", "open", wave="1", cycle="C1")])
        self.assertIn('CR-Q-001,"1",open', envelope, "precondition: the cell is quoted")
        result = self.render(envelope)
        self.assertIn("wave=1 ", result.stdout, f"got {result.stdout!r}")
        self.assertNotIn('wave="1"', result.stdout)

    def test_s4_quoted_active_cycle_id_cell_renders_unquoted(self):
        envelope = _envelope([_plan("CR-Q-002", "open", wave=3, cycle="125")])
        self.assertIn('"125"', envelope, "precondition: the cell is quoted")
        result = self.render(envelope)
        self.assertRegex(result.stdout, r"activeCycleId=125\s*$|activeCycleId=125\n")
        self.assertNotIn('"125"', result.stdout)

    def test_s4_no_rendered_row_carries_a_double_quote_and_bare_cells_are_unchanged(self):
        result = self.render(_envelope([
            _plan("CR-Q-003", "open", wave="7", cycle="42"),
            _plan("CR-Q-004", "open", wave=8, cycle="C2"),
        ]))
        rows = [line for line in result.stdout.splitlines() if "cr=" in line]
        self.assertEqual(len(rows), 2, f"both open rows listed; got {result.stdout!r}")
        self.assertEqual([r for r in rows if '"' in r], [])
        self.assertIn("cr=CR-Q-003 wave=7 status=open activeCycleId=42", rows[0])
        self.assertIn("cr=CR-Q-004 wave=8 status=open activeCycleId=C2", rows[1])


# ---------------------------------------------------------------------------
# §S5 — arduino projects resolve
# ---------------------------------------------------------------------------

def _marker_table_parity_findings(table, stack_client_keys: dict) -> list[str]:
    """Findings where a ``(marker, stack, manifest_key)`` table disagrees with
    ``STACK_CLIENT_KEYS`` or is not shaped as the pinned contract."""
    if not isinstance(table, (tuple, list)) or not table:
        return [f"table is not a non-empty sequence: {table!r}"]
    findings = []
    for entry in table:
        if (not isinstance(entry, (tuple, list)) or len(entry) != 3
                or not all(isinstance(x, str) for x in entry)):
            findings.append(f"entry {entry!r} is not a (marker, stack, key) str 3-tuple")
            continue
        marker, stack, key = entry
        if stack not in stack_client_keys:
            findings.append(f"{marker}: stack {stack!r} is not in STACK_CLIENT_KEYS")
        elif stack_client_keys[stack] != key:
            findings.append(f"{marker}: stack {stack!r} -> key {key!r}, "
                            f"STACK_CLIENT_KEYS says {stack_client_keys[stack]!r}")
    return findings


class ArduinoMarkerTableS5Test(unittest.TestCase):
    """§S5: the marker table carries the arduino sketch template, in parity."""

    def setUp(self):
        self.table = tuple(tuple(e) for e in
                           getattr(_load_hook_module(), "_STACK_MARKERS", ()))

    def test_s5_marker_table_carries_the_arduino_sketch_template_entry(self):
        self.assertIn(ARDUINO_MARKER_ENTRY, self.table)

    def test_s5_only_the_arduino_entry_is_a_dir_template(self):
        templated = [e for e in self.table if "{" in e[0] or "}" in e[0]]
        self.assertEqual(templated, [ARDUINO_MARKER_ENTRY])

    def test_s5_marker_table_is_in_parity_with_stack_client_keys_including_arduino(self):
        self.assertEqual(_marker_table_parity_findings(self.table, STACK_CLIENT_KEYS), [])
        self.assertIn("arduino", {e[1] for e in self.table})
        self.assertEqual(STACK_CLIENT_KEYS["arduino"], "arduino")

    def test_s5_all_five_manifest_keys_are_reachable_from_some_marker(self):
        reachable = {e[2] for e in self.table}
        self.assertEqual(reachable, set(MANIFEST_KEYS))
        self.assertEqual(reachable, set(STACK_CLIENT_KEYS.values()))


class ArduinoProjectResolutionS5Test(_SandboxCase):
    """§S5: ``<dir>/<dir>.ino`` marks an arduino project, resolved from the
    manifest like every other stack; the nearest marker still wins."""

    def _sketch(self, name: str = "sheetal-firmware", parent: Path | None = None) -> Path:
        sketch = (parent if parent is not None else self.sb.root / "work") / name
        self.sb.touch(sketch / f"{name}.ino")
        return sketch

    def test_s5_sketch_resolves_the_arduino_client_from_tests_native(self):
        self.sb.write_all_clients_manifest()
        sketch = self._sketch()
        native = sketch / "tests" / "native"
        native.mkdir(parents=True)
        self.assert_resolved_to(self.sb.run_hook(cwd=native), "arduino")

    def test_s5_sketch_folder_itself_as_cwd_resolves_the_arduino_client(self):
        self.sb.write_all_clients_manifest()
        self.assert_resolved_to(self.sb.run_hook(cwd=self._sketch("blinker")), "arduino")

    def test_s5_sketch_nearer_than_a_python_ancestor_wins(self):
        self.sb.write_all_clients_manifest()
        self.sb.touch(self.sb.project / "pyproject.toml")
        sketch = self._sketch("fw", parent=self.sb.project)
        native = sketch / "tests" / "native"
        native.mkdir(parents=True)
        self.assert_resolved_to(self.sb.run_hook(cwd=native), "arduino")

    def test_s5_python_marker_nearer_than_a_sketch_ancestor_wins(self):
        """Passes by design at RED (python is the only known marker); pins
        nearest-wins against a GREEN that prefers arduino anywhere up."""
        self.sb.write_all_clients_manifest()
        sketch = self._sketch("fw")
        tools = sketch / "tools"
        self.sb.touch(tools / "pyproject.toml")
        self.assert_resolved_to(self.sb.run_hook(cwd=tools), "python")

    def test_s5_stray_ino_whose_stem_differs_from_the_folder_is_not_a_marker(self):
        """Passes by design at RED; pins that GREEN keys on the folder name,
        not on any ``*.ino``."""
        self.sb.write_all_clients_manifest()
        firmware = self.sb.root / "work" / "firmware"
        self.sb.touch(firmware / "blink.ino")
        self.assert_no_marker(self.sb.run_hook(cwd=firmware))

    def test_s5_stray_ino_does_not_shadow_an_ancestor_marker(self):
        """Passes by design at RED; a stray ``.ino`` nearer than a python
        marker must not win."""
        self.sb.write_all_clients_manifest()
        self.sb.touch(self.sb.project / "pyproject.toml")
        sub = self.sb.project / "sub"
        self.sb.touch(sub / "blink.ino")
        self.assert_resolved_to(self.sb.run_hook(cwd=sub), "python")

    def test_s5_ino_named_after_an_ancestor_folder_is_not_a_marker(self):
        """``outer/inner/outer.ino``: the stem names an ancestor, not the
        folder holding it, so nothing resolves. Passes by design at RED."""
        self.sb.write_all_clients_manifest()
        inner = self.sb.root / "work" / "outer" / "inner"
        self.sb.touch(inner / "outer.ino")
        self.assert_no_marker(self.sb.run_hook(cwd=inner))

    def test_s5_a_file_literally_named_dir_placeholder_ino_is_not_a_marker(self):
        """The template is substituted, never matched literally. Passes by
        design at RED; bites a GREEN that forgets the substitution."""
        self.sb.write_all_clients_manifest()
        firmware = self.sb.root / "work" / "firmware"
        self.sb.touch(firmware / "{dir}.ino")
        self.assert_no_marker(self.sb.run_hook(cwd=firmware))

    def test_s5_every_manifest_key_is_run_from_its_marker(self):
        for key in MANIFEST_KEYS:
            with self.subTest(key=key):
                sb = _Sandbox()
                self.addCleanup(sb.cleanup)
                self.sb = sb
                sb.write_all_clients_manifest()
                if key == "arduino":
                    cwd = self._sketch("sketchbook-" + key)
                else:
                    cwd = sb.project
                    sb.touch(cwd / LITERAL_MARKER_FOR_KEY[key])
                self.assert_resolved_to(sb.run_hook(cwd=cwd), key)


if __name__ == "__main__":
    unittest.main()
