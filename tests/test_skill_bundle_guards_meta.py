"""RED-phase META gates for CR-MDB-017 cycle C4 (§S5 — "the guard that
would have caught it").

C4 is unusual: its deliverable IS a test module, `tests/test_skill_bundle_guards.py`.
This module is therefore the RED for that module — it asserts nothing about
`skills-src/` content itself, only that the guard module GREEN writes has the
properties §S5's acceptance criteria demand. Every gate below fails today for one
reason: `tests/test_skill_bundle_guards.py` does not exist yet.

Which "six owned bundles" (\u00a7S5 AC3, narrowed by CR-MDB-024 \u00a7S3)
------------------------------------------------------------------------
The owned set is MEASURED from `skills-src/` at run time by `_owned_bundles()` --
every directory carrying a `SKILL.md` whose name is `crucible-register` or starts
with `crucible-report-` -- and cross-checked against the bullet list in
`skills-src/CRUCIBLE-HANDOVER.md` ("Bundles imported (6 of 8)"). That measurement
yields exactly six as of CR-MDB-024 \u00a7S3 (this cycle, C2 RED, 2026-09-22 VS Code
ruling -- the VS Code crucible-report bundle is retired outright, narrowing the
CR-MDB-016 \u00a7S1 original seven by one): `crucible-register` plus
`crucible-report-{arduino,bun,java,python,rust}`. The set is measured rather than
hard-coded because the CR's prose and the dispatch brief both gloss it loosely;
the handover doc is the ratified record of what Model B owns (CR-MDB-016 \u00a7S1,
Sandesh #1336/#1337).
`skills-src/crucible/` is deliberately NOT in the set: it is Model-B-authored
routing content, not one of the six Crucible-origin bundles -- a guard that also
covers it satisfies these gates (they assert the six are present, never that
nothing else is).

The no-duplication criterion
----------------------------
§S5 was re-scoped at the 2026-09-21 gap-analysis: three families were REMOVED from
its scope because `tests/test_skills_handover.py` already gates them —
zero `WORKFLOW_CYCLE_ID` across the bundles (`:226`), the v2 touch contract
(`:294`), the v2 heartbeat form (`:386`). An AC now FORBIDS duplicating them, and
requires the guard to cite them in its docstring instead. `test_s5_defers_...`
below therefore matches on the guard's EFFECTIVE CODE only — docstrings and
comments (whole-line and trailing) are stripped before the scan — so a comment or
docstring explaining the deferral is explicitly safe, while the same marker
appearing in executable code (a constant, a scan, an assertion argument) is a
duplicate assertion and fails.

Markers that other repo gates grep for are built by concatenation here, the idiom
`tests/test_skills_handover.py` and `tests/test_realhome_supersede.py` already use.

Stdlib only: unittest + ast + tokenize + importlib + re + io + sys + pathlib.
"""

import ast
import importlib.util
import io
import re
import sys
import tokenize
import unittest
from pathlib import Path

from tests._helpers import read_text_lenient as _read

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = REPO_ROOT / "tests"
SKILLS_SRC = REPO_ROOT / "skills-src"
HANDOVER_MD = SKILLS_SRC / "CRUCIBLE-HANDOVER.md"

# The C4 deliverable this module is the RED for.
GUARD_MODULE = TESTS_DIR / "test_skill_bundle_guards.py"
META_MODULE = Path(__file__).resolve()

# The module whose gates §S5 defers to, and the three line references the guard's
# docstring must cite instead of re-asserting them.
HANDOVER_TEST_REL = "tests/test_skills_handover.py"
DEFERRED_LINE_REFS = (":226", ":294", ":386")

# Built by concatenation so this file never itself trips a grep gate for either
# term (same idiom as tests/test_skills_handover.py and test_realhome_supersede.py).
CYCLE_ID_ENV_MARKER = "WORKFLOW_" + "CYCLE_ID"
HEARTBEAT_MARKER = "heartbeat"
AGENT_PROTOCOL_MARKER = "agent-" + "protocol"
HEARTBEAT_SCRIPT_MARKER = "heartbeat" + ".sh"

# Properties tests/test_skills_handover.py already gates; the guard must cite,
# never re-assert. (marker, property, owning line reference)
DEFERRED_PROPERTIES = (
    (CYCLE_ID_ENV_MARKER, "zero WORKFLOW_"
     "CYCLE_ID across the bundles", ":226"),
    (HEARTBEAT_MARKER, "the v2 touch contract / the v2 heartbeat form",
     ":294 and :386"),
)

# §S5: the guard spawns no subprocess and starts no server.
BANNED_IMPORT_ROOTS = (
    "subprocess",
    "socket",
    "socketserver",
    "http",
    "urllib",
    "urllib3",
    "requests",
    "httpx",
    "ftplib",
    "xmlrpc",
    "multiprocessing",
    "asyncio",
)
BANNED_OS_CALLS = (
    "system",
    "popen",
    "fork",
    "forkpty",
    "posix_spawn",
    "posix_spawnp",
    "execv",
    "execve",
    "execvp",
    "execlp",
    "spawnv",
    "spawnl",
    "spawnlp",
)

# §S5: the guard reads NO client source and no `--help` output. These are PATH
# shapes that can only mean "reach outside this repo into a Crucible checkout" —
# the token `-crucible.py` is deliberately NOT banned, because matching it inside
# OUR OWN bundle text is exactly what the flag-surface check is for.
CLIENT_PATH_MARKERS = (
    "~/.crucible",
    ".crucible/clients",
    "crucible/clients",
    "clients/skills",
    "data" "_projects/crucible",  # split literal (CR-MDB-032 S1)
    "--help",
)
# Escaping the repo is how a client gets read; the guard must not try.
HOME_ESCAPE_MARKERS = ("Path.home", "expanduser", "expandvars")

# A flag allow-list mirroring Crucible's surface is a second source of truth for
# a surface Model B does not own (§S5, and "Rejected alternatives"). The guard
# needs a handful of flag literals of its own (--role/--cycle/--cycles/the
# retired one/--agent); a mirror of the client surface needs dozens.
MAX_DISTINCT_FLAG_LITERALS = 10
FLAG_LITERAL_RE = re.compile(r"--[A-Za-z][A-Za-z0-9-]+")

# CR-MDB-024 \u00a7S3 (this cycle, C2 RED, 2026-09-22 VS Code ruling): \u00a7S5 AC5's
# API-path exemption constant is retired along with the bundle it named --
# the VS Code crucible-report bundle is deleted outright, so
# tests/test_skill_bundle_guards.py's API_PATH_BUNDLES is correctly EMPTY
# and there is nothing left for a constant-name/exempt-bundle pair here to
# demand.

# §S5 AC4 — the four register defects, each of which must be proven to bite by a
# FIXTURE case. Matched on the guard's test-method NAMES (predictable for GREEN,
# and the accepted tokens are printed in the failure message).
FIXTURE_DEFECT_FAMILIES = (
    ("retired register flag present", ("phase",)),
    (
        "register example omits --role",
        ("missing_role", "role_missing", "omits_role", "no_role",
         "without_role", "role_absent", "roleless"),
    ),
    (
        "register example uses an out-of-enum role",
        ("out_of_enum", "role_enum", "enum_role", "invalid_role", "bad_role",
         "unknown_role", "role_out_of", "nonenum", "non_enum"),
    ),
    (
        "TDD-role register example omits --cycle",
        ("missing_cycle", "cycle_missing", "omits_cycle", "no_cycle",
         "without_cycle", "cycle_absent", "unbound", "cycleless"),
    ),
)
FIXTURE_MARKERS = (
    "tempfile",
    "TemporaryDirectory",
    "mkdtemp",
    "mkstemp",
    "NamedTemporaryFile",
    "write_text",
)

# §S5 AC7 — nothing may assert the EXISTENCE of the ratified-out artifacts.
EXISTENCE_ASSERTIONS = ("assertTrue", "assertIsNotNone")
EXISTENCE_PREDICATES = ("exists(", "is_dir(", "is_file(", "isdir(", "isfile(")

# Local (non-third-party) import roots a test module may legitimately use.
LOCAL_IMPORT_ROOTS = ("modelb_axi", "tests", "generator")


def _rel(path):
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:  # pragma: no cover - defensive
        return str(path)


def _owned_bundles():
    """MEASURE the owned bundle set from `skills-src/` (see module docstring).

    A bundle is a directory carrying a SKILL.md and named `crucible-register` or
    `crucible-report-<stack>`. Returns a sorted tuple.
    """
    if not SKILLS_SRC.is_dir():
        return ()
    found = []
    for child in sorted(SKILLS_SRC.iterdir()):
        if not child.is_dir() or not (child / "SKILL.md").is_file():
            continue
        if child.name == "crucible-register" or child.name.startswith("crucible-report-"):
            found.append(child.name)
    return tuple(found)


def _handover_bundles():
    """The same set as recorded in the ratified provenance doc, for cross-check."""
    if not HANDOVER_MD.is_file():
        return ()
    names = re.findall(
        r"`(crucible-register|crucible-report-[a-z0-9]+)`", _read(HANDOVER_MD)
    )
    return tuple(sorted(set(names)))


def _docstring_line_spans(tree):
    spans = []
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            doc = body[0].value
            spans.append((doc.lineno, doc.end_lineno or doc.lineno))
    return spans


def _comment_spans(source):
    spans = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                spans.setdefault(tok.start[0], []).append((tok.start[1], tok.end[1]))
    except (tokenize.TokenError, IndentationError, SyntaxError):  # pragma: no cover
        pass
    return spans


def _effective_code_lines(source, tree):
    """(lineno, text) for every line with docstrings and comments removed.

    This is what makes the no-duplication gate precise: a comment or docstring
    that MENTIONS a deferred property is prose and survives; the same marker in
    executable code is a duplicate assertion and is caught.
    """
    doc_spans = _docstring_line_spans(tree)
    comments = _comment_spans(source)
    out = []
    for lineno, line in enumerate(source.splitlines(), 1):
        if any(start <= lineno <= end for start, end in doc_spans):
            continue
        for col_start, col_end in sorted(comments.get(lineno, []), reverse=True):
            line = line[:col_start] + line[col_end:]
        if line.strip():
            out.append((lineno, line))
    return out


def _non_docstring_str_literals(tree):
    """Every string constant that is not a module/class/function docstring."""
    doc_nodes = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)) and body:
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                doc_nodes.add(id(first.value))
    out = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in doc_nodes
        ):
            out.append((node.lineno, node.value))
    return out


def _import_roots(tree):
    """(root_module, lineno) for every absolute import; relative imports skipped."""
    roots = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.append((alias.name.split(".")[0], node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            if node.module:
                roots.append((node.module.split(".")[0], node.lineno))
    return roots


def _test_methods(tree):
    """{method_name: FunctionDef} for every `test_*` method in the module."""
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                        item.name.startswith("test_"):
                    found[item.name] = item
    return found


def _module_level_functions(tree):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("test_")
    }


def _called_names(node):
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
            names.add(sub.func.id)
    return names


def _loaded_names(tree):
    counts = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            counts[node.id] = counts.get(node.id, 0) + 1
    return counts


def _module_level_constants(tree):
    """{NAME: (literal_value_or_None, lineno)} for module-level assignments."""
    out = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if not isinstance(target, ast.Name):
                continue
            value = None
            if node.value is not None:
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, TypeError, SyntaxError):
                    value = None
            out[target.id] = (value, node.lineno)
    return out


def _flatten_strings(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set, frozenset)):
        out = []
        for item in value:
            out.extend(_flatten_strings(item))
        return out
    if isinstance(value, dict):
        out = []
        for key, item in value.items():
            out.extend(_flatten_strings(key))
            out.extend(_flatten_strings(item))
        return out
    return []


class SkillBundleGuardsMetaTest(unittest.TestCase):
    """CR-MDB-017 §S5 — meta gates on the guard module C4 must deliver.

    Every method states what it demands of `tests/test_skill_bundle_guards.py`;
    all of them except the repo-wide §S5 AC7 gate fail today because the guard
    module does not exist.
    """

    # ---------------------------------------------------------------- helpers

    def _require_guard(self):
        """Fail (never skip) when the C4 deliverable is missing, then parse it."""
        self.assertTrue(
            GUARD_MODULE.is_file(),
            f"MISSING DELIVERABLE: {_rel(GUARD_MODULE)} must exist — §S5's guard "
            f"module is the C4 deliverable itself.",
        )
        source = _read(GUARD_MODULE)
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            self.fail(f"{_rel(GUARD_MODULE)} does not parse: {exc}")
        return source, tree

    def _guard_code_text(self, source, tree):
        return "\n".join(text for _, text in _effective_code_lines(source, tree))

    # ------------------------------------------------------------------ gates

    def test_s5_guard_module_exists_is_importable_and_is_stdlib_unittest(self):
        """DEMANDS: the module exists, imports cleanly, uses `unittest`, and
        imports nothing outside the standard library (or this repo)."""
        source, tree = self._require_guard()

        roots = _import_roots(tree)
        imported = {name for name, _ in roots}
        self.assertIn(
            "unittest",
            imported,
            f"{_rel(GUARD_MODULE)} must be a stdlib `unittest` module; it never "
            f"imports unittest. Imported roots: {sorted(imported)}",
        )
        third_party = sorted(
            f"{name} (line {lineno})"
            for name, lineno in roots
            if name not in sys.stdlib_module_names and name not in LOCAL_IMPORT_ROOTS
        )
        self.assertEqual(
            third_party,
            [],
            f"{_rel(GUARD_MODULE)} must be stdlib-only (pyproject declares zero "
            f"runtime dependencies and the suite is pure unittest — no pytest, no "
            f"fixtures). Third-party imports: {third_party}",
        )
        self.assertTrue(
            any(
                isinstance(node, ast.ClassDef)
                and any(
                    (isinstance(base, ast.Attribute) and base.attr == "TestCase")
                    or (isinstance(base, ast.Name) and base.id == "TestCase")
                    for base in node.bases
                )
                for node in ast.walk(tree)
            ),
            f"{_rel(GUARD_MODULE)} must define at least one unittest.TestCase class.",
        )

        spec = importlib.util.spec_from_file_location(
            "modelb_guard_under_meta_test", GUARD_MODULE
        )
        if spec is None or spec.loader is None:
            self.fail(
                f"{_rel(GUARD_MODULE)} must be importable as a Python module; no "
                f"import spec/loader could be built for it."
            )
        loader = spec.loader
        module = importlib.util.module_from_spec(spec)
        try:
            loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 - any import-time failure is a fail
            self.fail(
                f"{_rel(GUARD_MODULE)} must import cleanly (module-level code runs "
                f"at collection time); import raised {type(exc).__name__}: {exc}"
            )

    def test_s5_guard_module_spawns_no_subprocess_and_starts_no_server(self):
        """DEMANDS: zero process/network surface — no subprocess, os.system,
        socket, http, urllib or requests. Stricter than the rest of the suite
        (`tests/test_generator_role_contract.py` legitimately shells
        `build.py --check`); §S5 makes it explicit for THIS module."""
        source, tree = self._require_guard()

        banned_imports = sorted(
            f"{name} (line {lineno})"
            for name, lineno in _import_roots(tree)
            if name in BANNED_IMPORT_ROOTS
        )
        self.assertEqual(
            banned_imports,
            [],
            f"{_rel(GUARD_MODULE)} must spawn no subprocess and start no server; "
            f"banned imports found: {banned_imports}. Banned roots: "
            f"{list(BANNED_IMPORT_ROOTS)}",
        )

        banned_calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute):
                owner = func.value
                owner_name = owner.id if isinstance(owner, ast.Name) else None
                if owner_name == "os" and func.attr in BANNED_OS_CALLS:
                    banned_calls.append(f"os.{func.attr} (line {node.lineno})")
                if owner_name in ("subprocess", "socket", "urllib", "requests"):
                    banned_calls.append(
                        f"{owner_name}.{func.attr} (line {node.lineno})"
                    )
            elif isinstance(func, ast.Name) and func.id in (
                "system", "popen", "check_output", "check_call", "getoutput"
            ):
                banned_calls.append(f"{func.id}() (line {node.lineno})")
        self.assertEqual(
            sorted(banned_calls),
            [],
            f"{_rel(GUARD_MODULE)} must execute nothing: process-spawning or "
            f"network calls found: {sorted(banned_calls)}",
        )

    def test_s5_guard_module_reads_no_client_and_mirrors_no_flag_surface(self):
        """DEMANDS: every assertion is about text under `skills-src/` — no path
        into a Crucible checkout or `~/.crucible`, no `--help` output, no escape
        from the repo root, and no maintained allow-list of Crucible's flags."""
        source, tree = self._require_guard()
        literals = _non_docstring_str_literals(tree)

        client_reads = sorted(
            f"line {lineno}: {value!r} contains {marker!r}"
            for lineno, value in literals
            for marker in CLIENT_PATH_MARKERS
            if marker in value
        )
        self.assertEqual(
            client_reads,
            [],
            f"{_rel(GUARD_MODULE)} must read NO client source and no `--help` "
            f"output — the shell-the-client design was cut at the 2026-09-21 "
            f"gap-analysis. Offending literals (docstrings are exempt, so explain "
            f"the rejected design in prose, not in code): {client_reads}",
        )

        code_text = self._guard_code_text(source, tree)
        escapes = sorted(m for m in HOME_ESCAPE_MARKERS if m in code_text)
        self.assertEqual(
            escapes,
            [],
            f"{_rel(GUARD_MODULE)} must never leave the repo root (reaching a "
            f"client is the only reason to); found: {escapes}",
        )

        flags = set()
        for _, value in literals:
            flags.update(FLAG_LITERAL_RE.findall(value))
        self.assertLessEqual(
            len(flags),
            MAX_DISTINCT_FLAG_LITERALS,
            f"{_rel(GUARD_MODULE)} carries {len(flags)} distinct flag literals "
            f"({sorted(flags)}) — at that size it is an allow-list MIRRORING "
            f"Crucible's flag surface, a second source of truth for a surface "
            f"Model B does not own. The guard needs only the register flags it "
            f"asserts about our own bundle text (bound: "
            f"{MAX_DISTINCT_FLAG_LITERALS}).",
        )

    def test_s5_guard_module_covers_all_six_owned_bundles_including_arduino(self):
        """DEMANDS: the guard names every owned bundle measured from
        `skills-src/` -- arduino included, which the inherited suite never
        covered. CR-MDB-024 \u00a7S3 AMENDMENT (this cycle, C2 RED, 2026-09-22 VS
        Code ruling): narrowed from seven to six -- the VS Code crucible-report
        bundle is retired outright."""
        owned = _owned_bundles()
        handover = _handover_bundles()
        self.assertEqual(
            len(owned),
            6,
            f"the owned bundle set measured from {_rel(SKILLS_SRC)} must be the "
            f"six of CR-MDB-024 \u00a7S3; measured {len(owned)}: {list(owned)}",
        )
        self.assertEqual(
            sorted(owned),
            sorted(handover),
            f"the set measured from {_rel(SKILLS_SRC)} ({list(owned)}) must match "
            f"the ratified record in {_rel(HANDOVER_MD)} ({list(handover)}) -- if "
            f"they disagree, the provenance doc is the authority and this CR is "
            f"working from a stale set.",
        )
        self.assertIn(
            "crucible-report-arduino",
            owned,
            "arduino must be in the measured owned set -- \u00a7S5 exists partly to "
            "extend the inherited suite to it.",
        )

        source, tree = self._require_guard()
        code_text = self._guard_code_text(source, tree)
        uncovered = []
        for bundle in owned:
            if bundle in code_text:
                continue
            stack = bundle.replace("crucible-report-", "", 1)
            composed = (
                "crucible-report-" in code_text
                and re.search(rf"""["']{re.escape(stack)}["']""", code_text)
            )
            if not composed:
                uncovered.append(bundle)
        self.assertEqual(
            uncovered,
            [],
            f"{_rel(GUARD_MODULE)} must cover all six owned bundles (named "
            f"directly, or composed from a `crucible-report-` prefix and a stack "
            f"token). Never named: {uncovered}",
        )

    # CR-MDB-024 \u00a7S3 (this cycle, C2 RED, 2026-09-22 VS Code ruling):
    # test_s5_guard_module_exempts_VS_Code_bundle_by_name_via_constant is
    # DELETED, not migrated -- the VS Code bundle it demanded an explicit
    # API-path exemption for is retired outright, so
    # tests/test_skill_bundle_guards.py's own API_PATH_BUNDLES is correctly
    # EMPTY now (see that module's own \u00a7S3 amendment); there is no longer
    # anything for this meta-gate to demand.
    def test_s5_guard_module_defers_handover_gated_properties_and_cites_them(self):
        """DEMANDS: the guard does NOT re-assert the three families
        `tests/test_skills_handover.py` already gates, and cites them with their
        line references in its docstring instead. Only EFFECTIVE CODE is scanned
        — a comment or docstring explaining the deferral is safe by design."""
        source, tree = self._require_guard()

        duplicates = []
        for lineno, text in _effective_code_lines(source, tree):
            for marker, prop, owner_ref in DEFERRED_PROPERTIES:
                if marker in text:
                    duplicates.append(
                        f"line {lineno}: {text.strip()[:88]!r} re-implements "
                        f"{prop} (owned by {HANDOVER_TEST_REL}{owner_ref})"
                    )
        self.assertEqual(
            duplicates,
            [],
            f"{_rel(GUARD_MODULE)} must NOT re-assert what {HANDOVER_TEST_REL} "
            f"already gates — two sources for one property is exactly the drift "
            f"the 2026-09-21 audit records. Move the mention into a comment or "
            f"the docstring. Duplicate assertions in code: {duplicates}",
        )

        docstring = ast.get_docstring(tree) or ""
        self.assertIn(
            HANDOVER_TEST_REL,
            docstring,
            f"{_rel(GUARD_MODULE)}'s module docstring must CITE "
            f"{HANDOVER_TEST_REL} as the owner of the three deferred families.",
        )
        missing_refs = [ref for ref in DEFERRED_LINE_REFS if ref not in docstring]
        self.assertEqual(
            missing_refs,
            [],
            f"{_rel(GUARD_MODULE)}'s docstring must cite all three line "
            f"references {list(DEFERRED_LINE_REFS)} ({HANDOVER_TEST_REL}:226 zero "
            f"env-var, :294 the v2 touch contract, :386 the v2 heartbeat form); "
            f"missing: {missing_refs}",
        )

    def test_s5_guard_module_proves_each_register_defect_with_a_fixture_case(self):
        """DEMANDS: the guard's checker is a reusable module-level function, and
        each of the four register defects (retired flag, missing role, out-of-enum
        role, TDD role without cycle) is proven to BITE by a temp-fixture negative
        case — not asserted in prose."""
        source, tree = self._require_guard()

        imported = {name for name, _ in _import_roots(tree)}
        self.assertIn(
            "tempfile",
            imported,
            f"{_rel(GUARD_MODULE)} must build its negative cases as temp fixtures "
            f"(`tempfile`), never by mutating {_rel(SKILLS_SRC)}.",
        )

        helpers = _module_level_functions(tree)
        self.assertTrue(
            helpers,
            f"{_rel(GUARD_MODULE)} must expose its register-example checker as a "
            f"module-level function so a fixture case can call it; the module "
            f"defines no module-level helper.",
        )
        # A shared fixture helper is a legitimate shape, so fixture-building
        # counts transitively: a case may write the temp bundle itself or call a
        # module-level helper that does.
        fixture_helpers = {
            name
            for name, node in helpers.items()
            if any(
                marker in (ast.get_source_segment(source, node) or "")
                for marker in FIXTURE_MARKERS
            )
        }

        methods = _test_methods(tree)
        fixture_methods = {}
        for name, node in methods.items():
            segment = ast.get_source_segment(source, node) or ""
            called = _called_names(node)
            builds_fixture = any(marker in segment for marker in FIXTURE_MARKERS) or bool(
                called & fixture_helpers
            )
            if not builds_fixture:
                continue
            if not (called & set(helpers)):
                continue
            fixture_methods[name] = segment

        self.assertGreaterEqual(
            len(fixture_methods),
            4,
            f"{_rel(GUARD_MODULE)} must carry at least four fixture-driven "
            f"negative cases (a temp bundle with a bad register line, fed to the "
            f"module's own checker). Fixture-driven methods found: "
            f"{sorted(fixture_methods)}; all test methods: {sorted(methods)}",
        )

        unproven = []
        for label, tokens in FIXTURE_DEFECT_FAMILIES:
            hit = [
                name
                for name in fixture_methods
                if any(token in name.lower() for token in tokens)
            ]
            if not hit:
                unproven.append(f"{label} (name one method with any of {list(tokens)})")
        self.assertEqual(
            unproven,
            [],
            f"{_rel(GUARD_MODULE)}: every register defect must be proven to bite "
            f"by its own fixture case, so the guard is not merely assumed to work. "
            f"Unproven defect families: {unproven}. Fixture-driven methods "
            f"present: {sorted(fixture_methods)}",
        )

    def test_s5_no_test_asserts_ratified_out_artifacts_exist(self):
        """DEMANDS (repo-wide): no test under `tests/` asserts the EXISTENCE of
        `skills-src/agent-protocol/` or any heartbeat helper script — both are
        ratified out of existence (Option B / the PRD §4.2 helper-script ban).
        Asserting their ABSENCE stays legal, and is what the suite already does."""
        offenders = []
        for path in sorted(TESTS_DIR.glob("*.py")):
            if path.resolve() == META_MODULE:
                continue
            source = _read(path)
            try:
                tree = ast.parse(source)
            except SyntaxError as exc:  # pragma: no cover - defensive
                self.fail(f"{_rel(path)} does not parse: {exc}")
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                segment = ast.get_source_segment(source, node) or ""
                markers = [
                    m
                    for m in (AGENT_PROTOCOL_MARKER, HEARTBEAT_SCRIPT_MARKER)
                    if m in segment
                ]
                if not markers:
                    continue
                if node.func.attr in EXISTENCE_ASSERTIONS and any(
                    predicate in segment for predicate in EXISTENCE_PREDICATES
                ):
                    offenders.append(
                        f"{_rel(path)}:{node.lineno}: {node.func.attr}(...) asserts "
                        f"{markers} EXISTS"
                    )
                elif node.func.attr == "assertIn" and node.args:
                    first = node.args[0]
                    if (
                        isinstance(first, ast.Constant)
                        and isinstance(first.value, str)
                        and any(
                            f"skills-src/{m}" in first.value or f"/{m}/" in first.value
                            for m in markers
                        )
                    ):
                        offenders.append(
                            f"{_rel(path)}:{node.lineno}: assertIn({first.value!r}, ...) "
                            f"asserts a ratified-out path is present"
                        )
        self.assertEqual(
            offenders,
            [],
            f"no test may assert the existence of `skills-src/"
            f"{AGENT_PROTOCOL_MARKER}/` or any `{HEARTBEAT_SCRIPT_MARKER}` — both "
            f"are ratified out (CR-MDB-016 Option B; PRD §4.2 helper-script ban) "
            f"and {HANDOVER_TEST_REL}:130-137/:360-384 asserts their ABSENCE. "
            f"Offenders: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
