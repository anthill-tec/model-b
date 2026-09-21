"""RED-phase tests for CR-MDB-022 cycle C2 — §S2 (one TOON codec, owned by
Model B, no third-party dependency) and §S3 (fix the real wire defect, pin the
round trip, and stop the four type-preservation defects).

Written before any §S2/§S3 production code lands on this branch, against the
spec as rewritten at commit 693c8d1, which is authoritative.

MEASURED PRE-STATE (2026-08-27, HEAD 693c8d1; C1 GREEN is 91ff12f):
  - `modelb_axi/toon.py` DOES NOT EXIST. `modelb_axi/axi.py` (95 lines) is the
    only hand-maintained codec in the package and exposes `encode` +
    `envelope` and NO `decode`; its `_encode_into()` raises `TypeError` for a
    list of dicts ("may hold scalars only in the envelope subset"), so it
    cannot emit the uniform-object-table construct `worktree-flow.py` already
    prints. Every round-trip assertion below therefore fails on the missing
    module, and the table case would fail on the encoder too.
  - `scripts/toon.py` (258 lines) is the hand-adopted 254-line copy plus C1's
    ownership header. It carries NO generated-artifact banner: line 5 still
    reads "DEPLOYED COPY — source of truth crucible:clients/toon.py (TRACKS
    Crucible)". It IS already self-contained, so only the banner and the
    drift-gate halves of §S2/AC3-AC4 are red; the isolated-import half is
    a standing guard the generator must not break.
  - `generator/build.py --list` names the 16 agent files and nothing else;
    `scripts/toon.py` is not under any drift gate. `--check` prints
    "clean: live tree matches regeneration" and exits 0 — over the agents
    only, which is why membership in `--list` is this gate's discriminator.
  - `modelb_axi/axi.py:10-12` still claims wire-compatibility with a "pinned"
    four-construct subset, citing DN-crucible-toon-subset.md as its authority;
    `scripts/toon.py:11` still cites that note as "the normative wire spec".
    The note is RETIRED (Crucible CR-CRU-046, 2026-08-01) and survives only
    as a pointer at the OFFICIAL spec (toonformat.dev /
    github.com/toon-format), so neither citation may stand as a live contract.
  - `scripts/worktree-flow.py:122` and `tests/test_worktree_flow_axi.py:82`
    both carry the provenance phrase §S2/AC8 forbids.
  - `python3 scripts/worktree-flow.py status --project-dir .` exits 0 and its
    stdout decodes cleanly against Crucible's port — including its
    `lanes[0]:`, `warnings[0]:` and `help[0]:` headers.

THE WIRE DEFECT, MEASURED — NOT the empty arrays:
Probed against `crucible:clients/toon.py` (their spec-conformant port,
validated upstream against the first-party `@toon-format/toon` reference),
driven OUT OF PROCESS only:

    warnings: []                            ACCEPTED (canonical empty form)
    warnings[0]:                            ACCEPTED
    warnings[0]: []                         REJECTED
    warnings[1]: <text>                     ACCEPTED (canonical non-empty —
                                            what their own encoder emits)
    warnings[1]: + "  - <text>"             ACCEPTED
    warnings[1]: + "  <text>" (BARE item)   REJECTED — "Expected 1 list-form
                                            items, but got 0"

`crucible:clients/toon.py:1243` counts a line as an item only when it starts
with `- ` or equals `-`. The bare-item form is what `worktree-flow.py` emits on
its degrade path, measured at `next` line 8 and `progress` line 7 — always the
`[1]` header, never a `[0]` header.

THE QUOTING RULE, READ FROM THE PORT (`_is_safe_unquoted`, their :211-228) and
confirmed by probing their encoder: a string scalar is emitted BARE only when
it is non-empty, has no leading/trailing space or tab, is not `true`/`false`/
`null` and not numeric-like, contains no colon, double quote, backslash,
`[`, `]`, `{` or `}` and no control character, does not contain the active
delimiter (`,`), and does not start with `-` or `#`. Otherwise it is
JSON-quoted. A plain em dash is BARE.
That single rule is simultaneously the wire rule and the fix for the four
type-preservation defects: quoting `"4"`, `"42"`, `"true"`, `"null"`, `""` and
whitespace-bearing strings is exactly what stops the decoder re-typing them.

Stdlib only: ast, json, subprocess, sys, tempfile, tomllib, unittest, pathlib.
Nothing here reads, writes or deletes under `~/.claude`, and nothing invokes
`chezmoi`. Crucible's port is used as an OUT-OF-PROCESS oracle: the child
program text is a string literal executed by a separate interpreter, so no
module from their checkout is ever imported into this process (§S2). Invoking
their client as a subprocess is sanctioned and is asserted as PERMITTED below.
"""

import ast
import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from modelb_axi import axi  # noqa: E402  (repo-local envelope emit seam)

SCRIPTS_DIR = REPO_ROOT / "scripts"
SCRIPTS_TOON = SCRIPTS_DIR / "toon.py"
WORKTREE_FLOW = SCRIPTS_DIR / "worktree-flow.py"
PYPROJECT = REPO_ROOT / "pyproject.toml"
GENERATOR_BUILD = REPO_ROOT / "generator" / "build.py"
MODELB_TOON = REPO_ROOT / "modelb_axi" / "toon.py"

#: Crucible's spec-conformant port, used as an out-of-process oracle only.
CRUCIBLE_CLIENTS_DIR = Path.home() / "Documents/data_projects/crucible/clients"
CRUCIBLE_TOON = CRUCIBLE_CLIENTS_DIR / "toon.py"

#: The §S2/§S3 gate surface, positively enumerated. `docs/changes/` is
#: deliberately absent: the CR ledger is the SPECIFICATION of these gates and
#: must quote the forbidden phrase and the retired note's filename verbatim in
#: order to define them, so sweeping it would make them unsatisfiable.
LIVE_SURFACE_DIRS = (
    "modelb_axi", "scripts", "tests", "contracts", "generator",
    "skills-src", "hooks-src",
)
LIVE_SURFACE_FILES = ("AGENTS.md",)

SKIP_DIR_NAMES = frozenset(
    {".git", "__pycache__", ".pytest_cache", ".ruff_cache", "build", "dist"}
)

#: The `.py` subtrees §S2/AC6 names.
PYTHON_GATE_DIRS = ("scripts", "modelb_axi", "tests")

#: Assembled at run time so the literal phrase never appears in this module's
#: own source — the gate then covers `tests/` INCLUDING this file, with no
#: self-exclusion carve-out.
FORBIDDEN_PROVENANCE = "copy of " + "crucible:"

#: §S3/AC10. The retired note may be cited only by a file that also records
#: its retirement; a bare citation reads as a live wire contract.
DN_FILENAME = "DN-crucible-" + "toon-subset.md"
RETIREMENT_MARKER = "RETIRED"

#: §S3/AC10 — the specific stale claim the CR names at `modelb_axi/axi.py:10-12`.
STALE_SUBSET_CLAIM = "4-construct" + " TOON subset"

#: §S2/AC6. Module names that must never resolve to Crucible's checkout.
CRUCIBLE_MODULE_NAMES = ("toon", "_crucible_axi")

#: §S2/AC7. The sanctioned exception: INVOKING their client as a subprocess is
#: required, not forbidden.
SANCTIONED_INVOCATION = "clients/python-crucible.py"

#: §S2/AC1. Distribution names that must never be declared.
FORBIDDEN_DISTRIBUTIONS = frozenset({"toon", "toon-format", "toon_format"})

#: §S2/AC3. The generated artifact's banner contract, established by this CR:
#: it names itself generated, names its single source, and forbids hand edits.
BANNER_MARKERS = ("GENERATED", "modelb_axi/toon.py", "hand-edit")
BANNER_WINDOW = 20

DEGRADE_WARNING = "schedule_db unavailable — queue-only project"

WF_VERBS = (("status",),)

#: Executed by a SEPARATE interpreter — never imported here. Takes the clients
#: directory as argv[1] and TOON text on stdin, prints the decoded JSON.
_ORACLE_PROGRAM = (
    "import json, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import toon\n"
    "sys.stdout.write(json.dumps(toon.decode(sys.stdin.read())))\n"
)


class OracleRejected(AssertionError):
    """Crucible's port refused the text Model B emitted."""


def _oracle_decode(text: str):
    """Decode ``text`` with `crucible:clients/toon.py` OUT OF PROCESS."""
    result = subprocess.run(
        [sys.executable, "-c", _ORACLE_PROGRAM, str(CRUCIBLE_CLIENTS_DIR)],
        input=text, capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        tail = [ln for ln in result.stderr.strip().splitlines() if ln.strip()]
        raise OracleRejected(tail[-1] if tail else "oracle exited non-zero")
    return json.loads(result.stdout)


def _model_b_codec():
    """Model B's one hand-maintained codec, or ``None`` while it is absent.

    Imported defensively so the §S2/AC1 landmine guard — which must stay green
    through this cycle — still runs before the codec exists.
    """
    try:
        from modelb_axi import toon
    except ImportError:
        return None
    return toon


CODEC = _model_b_codec()


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _live_surface_files() -> list:
    found = []
    for rel in LIVE_SURFACE_DIRS:
        base = REPO_ROOT / rel
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if SKIP_DIR_NAMES & set(path.relative_to(REPO_ROOT).parts):
                continue
            found.append(path)
    for rel in LIVE_SURFACE_FILES:
        path = REPO_ROOT / rel
        if path.is_file():
            found.append(path)
    return found


def _python_gate_files() -> list:
    return [
        path for path in _live_surface_files()
        if path.suffix == ".py"
        and path.relative_to(REPO_ROOT).parts[0] in PYTHON_GATE_DIRS
    ]


def _requirement_name(requirement: str) -> str:
    """The bare distribution name of a PEP 508 requirement string."""
    name = requirement.strip()
    for stop in (";", "[", "@", "=", "<", ">", "!", "~", " "):
        name = name.split(stop, 1)[0]
    return name.strip().lower()


def _pyproject_requirements() -> list:
    """Every declared requirement in `pyproject.toml`, as (where, name)."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    found = []
    for where, raw in (
        ("build-system.requires", data.get("build-system", {}).get("requires", [])),
        ("project.dependencies", data.get("project", {}).get("dependencies", [])),
    ):
        found.extend((where, _requirement_name(item)) for item in raw)
    for table in ("optional-dependencies",):
        for extra, items in (data.get("project", {}).get(table, {}) or {}).items():
            found.extend(
                (f"project.{table}.{extra}", _requirement_name(item))
                for item in items
            )
    for group, items in (data.get("dependency-groups", {}) or {}).items():
        found.extend(
            (f"dependency-groups.{group}", _requirement_name(item))
            for item in items
        )
    return found


def _inline_metadata_requirements(path: Path) -> list:
    """PEP 723 ``# /// script`` inline-metadata requirements in ``path``."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    found, inside = [], False
    for line in lines:
        stripped = line.strip()
        if stripped == "# /// script":
            inside = True
            continue
        if inside and stripped == "# ///":
            inside = False
            continue
        if not inside or not stripped.startswith("#"):
            continue
        body = stripped.lstrip("#").strip()
        for token in body.split('"'):
            name = _requirement_name(token)
            if name in FORBIDDEN_DISTRIBUTIONS:
                found.append((f"{_rel(path)} (PEP 723)", name))
    return found


def _module_string_constants(tree: ast.Module) -> dict:
    """Module-level ``NAME = "literal"`` bindings, so a `sys.path` insert fed
    by a named constant is resolved rather than silently skipped."""
    consts = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not (isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                consts[target.id] = node.value.value
    return consts


def _is_sys_path_mutation(func: ast.expr) -> bool:
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr not in ("insert", "append", "extend"):
        return False
    inner = func.value
    return (
        isinstance(inner, ast.Attribute) and inner.attr == "path"
        and isinstance(inner.value, ast.Name) and inner.value.id == "sys"
    )


def _resolve_literal(node: ast.expr, consts: dict):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    return None


def _path_inserts_outside_repo(path: Path) -> list:
    """AST-level `sys.path` mutations whose literal argument is an absolute
    path outside this repo.

    Matching the CALL NODE rather than file text is what makes §S2's
    IMPORT-vs-INVOCATION distinction mechanical: a path string handed to
    `subprocess.run`, or embedded in a program text a child interpreter runs,
    is never a `sys.path` mutation node in THIS process and so cannot be
    swept. An argument computed at run time (`str(REPO_ROOT)`,
    `os.path.dirname(os.path.abspath(__file__))`) is repo-relative by
    construction and is not flagged.
    """
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), str(path))
    consts = _module_string_constants(tree)
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_sys_path_mutation(node.func):
            continue
        index = 1 if node.func.attr == "insert" else 0
        if len(node.args) <= index:
            continue
        raw = _resolve_literal(node.args[index], consts)
        if raw is None:
            continue
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            continue
        if not candidate.is_relative_to(REPO_ROOT):
            offenders.append((node.lineno, raw))
    return offenders


def _crucible_imports(path: Path) -> list:
    """`import toon` / `import _crucible_axi` that cannot resolve inside this
    repo. `scripts/worktree-flow.py`'s `import toon` resolves to its sibling
    `scripts/toon.py` and is correct."""
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), str(path))
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module.split(".")[0]]
        else:
            continue
        for name in names:
            if name not in CRUCIBLE_MODULE_NAMES:
                continue
            resolvable_here = (
                (path.parent / f"{name}.py").is_file()
                or (REPO_ROOT / f"{name}.py").is_file()
            )
            if not resolvable_here:
                offenders.append((node.lineno, name))
    return offenders


def _top_level_codec_definitions(path: Path) -> list:
    """Top-level ``def encode`` / ``def decode`` in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), str(path))
    return sorted(
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in ("encode", "decode")
    )


def _run_generator(*args):
    return subprocess.run(
        [sys.executable, str(GENERATOR_BUILD), *args],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
        stdin=subprocess.DEVNULL,
    )


def _run_worktree_flow(project_dir: Path, argv):
    return subprocess.run(
        [sys.executable, str(WORKTREE_FLOW), *argv,
         "--project-dir", str(project_dir)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
        stdin=subprocess.DEVNULL,
    )


def _queue_only_project(parent: Path) -> Path:
    """A git repo with NO ChangeSet DB, so `worktree-flow.py` takes its
    `schedule_db unavailable — queue-only project` degrade path."""
    project_dir = parent / "queue-only"
    project_dir.mkdir()
    git = ["git", "-c", "user.name=CR-MDB-022",
           "-c", "user.email=cr-mdb-022@example.invalid"]
    for argv in (["init", "-q", "-b", "main", "."],
                 ["commit", "-q", "--allow-empty", "-m", "init"]):
        subprocess.run([*git, *argv], cwd=project_dir, check=True,
                       capture_output=True, timeout=60)
    return project_dir


def _array_block(text: str, key: str):
    """Return ``(header_line, item_lines)`` for ``key``'s array rendering."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not (stripped.startswith(f"{key}[") or stripped.startswith(f"{key}:")):
            continue
        indent = len(line) - len(line.lstrip())
        items = []
        for follower in lines[index + 1:]:
            if not follower.strip():
                break
            if len(follower) - len(follower.lstrip()) <= indent:
                break
            items.append(follower.strip())
        return stripped, items
    return None, []


class ToonCodecS2Test(unittest.TestCase):
    """§S2 — one TOON codec, owned by Model B, with no third-party dependency."""

    def _require_codec(self):
        if CODEC is None:
            self.fail(
                f"§S2/AC2: {_rel(MODELB_TOON)} does not exist, so Model B has "
                "no owned codec to exercise — it is the prerequisite for every "
                "other assertion in this module"
            )
        return CODEC

    def test_s2_no_model_b_file_declares_a_toon_dependency(self):
        """STANDING LANDMINE GUARD — expected GREEN at RED and forever after.

        PyPI `toon-format` 0.1.0 is the official project by identity but is a
        name-reservation stub whose `encode`/`decode` both raise
        `NotImplementedError`; PyPI `toon` 0.15.9 is "Tools for neuroscience
        experiments", unrelated and a silent landmine if installed. There is no
        usable generic Python TOON library, so Model B stays stdlib-only and no
        file may ever pin either distribution. This test exists to fail LOUDLY
        the day somebody re-litigates that, which is why it is the one test in
        this module that is green at RED.
        """
        declared = [
            (where, name) for where, name in _pyproject_requirements()
            if name in FORBIDDEN_DISTRIBUTIONS
        ]
        inline = []
        for path in _python_gate_files():
            inline.extend(_inline_metadata_requirements(path))
        self.assertEqual(
            declared, [],
            "§S2/AC1: pyproject.toml must declare no `toon`/`toon-format` "
            f"dependency (the working implementation is TypeScript); found "
            f"{declared}",
        )
        self.assertEqual(
            inline, [],
            "§S2/AC1: no PEP 723 inline-metadata block under "
            f"{', '.join(PYTHON_GATE_DIRS)} may declare `toon`/`toon-format`; "
            f"found {inline}",
        )

    def test_s2_modelb_axi_toon_is_the_one_hand_maintained_implementation(self):
        self.assertTrue(
            MODELB_TOON.is_file(),
            f"§S2/AC2: the single hand-maintained TOON implementation must "
            f"live at {_rel(MODELB_TOON)}; it does not exist",
        )
        codec = self._require_codec()
        # The module under test must be the REPO's, not an installed wheel's.
        self.assertEqual(
            Path(codec.__file__).resolve(), MODELB_TOON.resolve(),
            f"§S2/AC2: `modelb_axi.toon` must resolve to {_rel(MODELB_TOON)} "
            f"in this repo, got {codec.__file__}",
        )
        missing = [
            name for name in ("encode", "decode")
            if not callable(getattr(codec, name, None))
        ]
        self.assertEqual(
            missing, [],
            f"§S2/AC2: {_rel(MODELB_TOON)} must expose BOTH `encode` and "
            f"`decode`; missing/not callable: {missing}. It currently exports: "
            f"{sorted(n for n in vars(codec) if not n.startswith('_'))}",
        )
        # EXACTLY ONE. `scripts/toon.py` is exempt because it is GENERATED
        # from this module (asserted separately), not hand-maintained.
        implementations = {}
        for path in _python_gate_files():
            if path == SCRIPTS_TOON:
                continue
            defined = _top_level_codec_definitions(path)
            if defined:
                implementations[_rel(path)] = defined
        self.assertEqual(
            implementations, {_rel(MODELB_TOON): ["decode", "encode"]},
            "§S2/AC2: EXACTLY ONE hand-maintained implementation may define "
            f"`encode`/`decode` — {_rel(MODELB_TOON)}, with both. "
            f"scripts/toon.py is exempt as a generated artifact. Found: "
            f"{implementations}",
        )

    def test_s2_scripts_toon_is_generated_and_self_contained(self):
        self.assertTrue(
            SCRIPTS_TOON.is_file(), f"{_rel(SCRIPTS_TOON)} must exist (§S1)"
        )
        header = "\n".join(
            SCRIPTS_TOON.read_text(encoding="utf-8").splitlines()[:BANNER_WINDOW]
        )
        missing = [marker for marker in BANNER_MARKERS if marker not in header]
        self.assertEqual(
            missing, [],
            f"§S2/AC3: {_rel(SCRIPTS_TOON)}'s first {BANNER_WINDOW} lines must "
            "carry a do-not-hand-edit banner naming it GENERATED and naming "
            f"its single source {_rel(MODELB_TOON)}; missing markers "
            f"{missing}. Header is:\n{header}",
        )
        # SELF-CONTAINMENT, proved the hard way: the file alone in a temp dir,
        # imported by a child interpreter run with -E (ignore PYTHONPATH) and
        # -S (no site-packages), so neither this repo nor the isolated uv-tool
        # venv holding `modelb_axi` is reachable. A re-export would raise
        # ModuleNotFoundError here — and that is exactly how a DEPLOYED
        # worktree-flow.py, invoked as a bare `python3`, resolves its codec.
        program = (
            "import importlib.util, sys\n"
            "assert importlib.util.find_spec('modelb_axi') is None, "
            "'modelb_axi must be unreachable for this to prove anything'\n"
            "import toon\n"
            "assert callable(toon.encode) and callable(toon.decode), "
            "'encode/decode must be callable in isolation'\n"
            "sys.stdout.write('ok')\n"
        )
        with tempfile.TemporaryDirectory(prefix="mdb022-iso-") as tmp:
            island = Path(tmp) / "island"
            island.mkdir()
            (island / "toon.py").write_bytes(SCRIPTS_TOON.read_bytes())
            result = subprocess.run(
                ["python3", "-E", "-S", "-c", program],
                cwd=island, capture_output=True, text=True, timeout=60,
                stdin=subprocess.DEVNULL,
            )
        self.assertEqual(
            result.returncode, 0,
            f"§S2/AC3: {_rel(SCRIPTS_TOON)} must be a real, SELF-CONTAINED "
            "module — importable alone in a temp dir by a bare interpreter "
            "that cannot reach this repo or the modelb_axi venv. Exit "
            f"{result.returncode}; stderr:\n{result.stderr}",
        )
        self.assertEqual(
            result.stdout, "ok",
            f"§S2/AC3: the isolated import of {_rel(SCRIPTS_TOON)} must expose "
            f"callable encode/decode; child stdout was {result.stdout!r}",
        )

    def test_s2_generated_codec_is_under_a_drift_gate_that_reports_clean(self):
        listed = _run_generator("--list")
        self.assertEqual(
            listed.returncode, 0,
            f"§S2/AC4: `generator/build.py --list` must exit 0, got "
            f"{listed.returncode}; stderr:\n{listed.stderr}",
        )
        targets = [line.strip() for line in listed.stdout.splitlines() if line.strip()]
        under_gate = [
            target for target in targets
            if Path(target).name == "toon.py" and "scripts" in Path(target).parts
        ]
        self.assertNotEqual(
            under_gate, [],
            "§S2/AC4: `scripts/toon.py` must be a GENERATED target of the "
            "drift gate, in the same spirit as generator/agents/*.md — "
            f"`generator/build.py --list` names {len(targets)} target(s) and "
            "none of them is scripts/toon.py, so nothing gates the codec "
            "copy against modelb_axi/toon.py",
        )
        checked = _run_generator("--check")
        self.assertEqual(
            checked.returncode, 0,
            "§S2/AC4: the drift gate must report CLEAN — `scripts/toon.py` "
            f"byte-identical to what the generator produces from "
            f"{_rel(MODELB_TOON)}. Exit {checked.returncode}; "
            f"stdout:\n{checked.stdout}\nstderr:\n{checked.stderr}",
        )
        self.assertIn(
            "clean", checked.stdout,
            "§S2/AC4: the drift gate must say so when clean; "
            f"`--check` printed:\n{checked.stdout}",
        )

    def test_s2_in_repo_worktree_flow_status_survives_the_codec_move(self):
        result = _run_worktree_flow(REPO_ROOT, ("status",))
        self.assertEqual(
            result.returncode, 0,
            "§S2/AC5: `python3 scripts/worktree-flow.py status` must keep "
            f"working from the repo, resolving `toon` from beside itself. Exit "
            f"{result.returncode}; stderr:\n{result.stderr[:2000]}",
        )
        # The in-repo run and the one owned codec must agree: a status that
        # exits 0 while emitting something Model B cannot read back is not
        # survival, it is a silent split between the deployed copy and the
        # source it is generated from.
        codec = self._require_codec()
        try:
            decoded = codec.decode(result.stdout)
        except Exception as exc:
            raise AssertionError(
                "§S2/AC5: the in-repo `status` stdout must decode with Model "
                f"B's own codec ({type(exc).__name__}: {exc}); stdout was:\n"
                f"{result.stdout[:2000]}"
            )
        self.assertIn(
            "axi", decoded,
            "§S2/AC5: the in-repo `status` envelope must carry a top-level "
            f"`axi` key, decoded keys {list(decoded)}",
        )

    def test_s2_no_repo_file_imports_a_module_from_crucible_checkout(self):
        insert_offenders, import_offenders = {}, {}
        for path in _python_gate_files():
            inserts = _path_inserts_outside_repo(path)
            if inserts:
                insert_offenders[_rel(path)] = inserts
            imports = _crucible_imports(path)
            if imports:
                import_offenders[_rel(path)] = imports
        self.assertEqual(
            insert_offenders, {},
            "§S2/AC6: zero `sys.path` inserts naming a path outside this repo "
            f"are permitted under {', '.join(PYTHON_GATE_DIRS)}; found "
            f"{insert_offenders}",
        )
        self.assertEqual(
            import_offenders, {},
            "§S2/AC6: no repo file may IMPORT a Python module out of "
            "Crucible's checkout — that forks another project's code into our "
            f"process; found {import_offenders}",
        )
        # SANCTIONED, asserted as PERMITTED rather than forbidden: INVOKING
        # clients/python-crucible.py as a subprocess is how a consumer uses
        # their tool. Model B dogfoods Crucible and this machine drives their
        # DEV server, so the checkout is the live client source. The gate
        # distinguishes IMPORT (forbidden) from INVOCATION (required) and must
        # never sweep an invocation site.
        invocation_sites = sorted(
            _rel(path) for path in _live_surface_files()
            if SANCTIONED_INVOCATION
            in path.read_text(encoding="utf-8", errors="replace")
        )
        self.assertNotEqual(
            invocation_sites, [],
            f"§S2/AC7: the repo must still INVOKE {SANCTIONED_INVOCATION} as a "
            "subprocess; the import gate above must not have removed it",
        )
        swept = sorted(
            set(invocation_sites)
            & (set(insert_offenders) | set(import_offenders))
        )
        self.assertEqual(
            swept, [],
            f"§S2/AC7: invoking {SANCTIONED_INVOCATION} as a subprocess is "
            "SANCTIONED and must not be flagged; the gate flagged "
            f"{swept} for invocation rather than import",
        )

    def test_s2_no_file_claims_a_crucible_copy_or_a_live_retired_contract(self):
        provenance, stale_claim, unretired_dn = {}, {}, {}
        for path in _live_surface_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            hits = [
                lineno for lineno, line in enumerate(lines, start=1)
                if FORBIDDEN_PROVENANCE in line
            ]
            if hits:
                provenance[_rel(path)] = hits
            claims = [
                lineno for lineno, line in enumerate(lines, start=1)
                if STALE_SUBSET_CLAIM in line
            ]
            if claims:
                stale_claim[_rel(path)] = claims
            citations = [
                lineno for lineno, line in enumerate(lines, start=1)
                if DN_FILENAME in line
            ]
            if citations and RETIREMENT_MARKER not in text:
                unretired_dn[_rel(path)] = citations
        self.assertEqual(
            provenance, {},
            f"§S2/AC8: the phrase {FORBIDDEN_PROVENANCE!r} must not appear on "
            "the live surface — a Model B file that self-describes as a copy "
            "of a Crucible file cannot be owned here without contradicting "
            f"the no-client-maintenance directive; found {provenance}",
        )
        self.assertEqual(
            stale_claim, {},
            f"§S3/AC10: the {STALE_SUBSET_CLAIM!r} claim is STALE — there is no "
            "private subset to be wire-compatible with; the OFFICIAL spec "
            "(toonformat.dev / github.com/toon-format) is the wire contract "
            f"and contracts/crucible-envelope.md records what Model B emits. "
            f"Found at {stale_claim}",
        )
        self.assertEqual(
            unretired_dn, {},
            f"§S3/AC10: no file may cite {DN_FILENAME} as a live contract — it "
            "is RETIRED (Crucible CR-CRU-046) and survives only as a pointer "
            f"at the official spec, so any citation must record that. Bare "
            f"citations at {unretired_dn}",
        )


class ToonEnvelopeS3Test(unittest.TestCase):
    """§S3 — the round trip, the four type-preservation defects, the real wire
    form, and the surviving list-emitting verb on a project with NO ChangeSet DB
    (the `schedule_db unavailable — queue-only project` degrade path, which is
    where the defect lived; CR-MDB-028 left `status` as the only such verb)."""

    EMPTY_LIST_ENVELOPE = {
        "axi": {
            "verb": "status", "ok": True, "project": "model-b",
            "lanes": [], "warnings": [], "help": [],
        }
    }
    NONEMPTY_LIST_ENVELOPE = {
        "axi": {
            "verb": "next", "ok": True, "project": "queue-only",
            "warnings": [DEGRADE_WARNING],
            "help": ["next --track <track>", "status"],
        }
    }
    TABLE_ENVELOPE = {
        "axi": {
            "verb": "status", "ok": True, "project": "model-b",
            "worktrees": [
                {"role": "integration", "branch": "develop",
                 "ahead": 0, "cr": None, "state": "clean"},
                {"role": "worktree", "branch": "feature/CR-MDB-022",
                 "ahead": 7, "cr": "CR-MDB-022", "state": "clean — finish-ready"},
            ],
            "warnings": [],
        }
    }
    SCALAR_ENVELOPE = {
        "axi": {
            "verb": "next", "ok": True, "project": "model-b",
            "track": None, "decision": "DRAINED", "cr": None, "ratio": 0.5,
        }
    }

    def _require_codec(self):
        if CODEC is None:
            self.fail(
                f"§S3: {_rel(MODELB_TOON)} does not exist, so Model B has no "
                "`decode` and the round trip cannot even be attempted — §S2's "
                "codec is the prerequisite for every §S3 assertion"
            )
        return CODEC

    def _require_oracle(self):
        if not CRUCIBLE_TOON.is_file():
            self.skipTest(
                f"Crucible's port {CRUCIBLE_TOON} is not on this machine, so "
                "the out-of-process conformance oracle cannot run"
            )

    def _assert_string_survives(self, label, value, why):
        """Round-trip ``value`` in BOTH scalar and list-item position."""
        codec = self._require_codec()
        payload = {"axi": {"verb": "probe", "note": value, "warnings": [value]}}
        text = codec.encode(payload)
        try:
            decoded = codec.decode(text)
        except Exception as exc:
            raise AssertionError(
                f"§S3/AC4 type preservation ({label}): decode raised "
                f"{type(exc).__name__}: {exc} on:\n{text}"
            )
        note = decoded.get("axi", {}).get("note")
        items = decoded.get("axi", {}).get("warnings")
        self.assertIsInstance(
            note, str,
            f"§S3/AC4 type preservation ({label}): the scalar {value!r} must "
            f"decode as a str, got {note!r} ({type(note).__name__}). {why}. "
            f"Wire text was:\n{text}",
        )
        self.assertEqual(
            decoded, payload,
            f"§S3/AC4 type preservation ({label}): {value!r} must survive "
            f"byte-exact in scalar AND list-item position. {why}. Decoded "
            f"{decoded!r} from:\n{text}",
        )
        self.assertEqual(
            items, [value],
            f"§S3/AC4 type preservation ({label}): the list item {value!r} must "
            f"survive as itself, got {items!r}",
        )

    def test_s3_the_four_envelope_shapes_round_trip(self):
        codec = self._require_codec()
        for label, payload in (
            ("empty list", self.EMPTY_LIST_ENVELOPE),
            ("non-empty scalar list", self.NONEMPTY_LIST_ENVELOPE),
            ("populated uniform table", self.TABLE_ENVELOPE),
            ("scalar-only envelope", self.SCALAR_ENVELOPE),
        ):
            with self.subTest(shape=label):
                text = codec.encode(payload)
                self.assertEqual(
                    codec.decode(text), payload,
                    f"§S3/AC1: decode(encode(x)) == x must hold for the "
                    f"{label} shape; encoded text was:\n{text}",
                )

    def test_s3_numeral_string_four_survives_as_a_string(self):
        self._assert_string_survives(
            "defect 1 — numeral-looking string",
            "4",
            "the scalar decoder promotes any bare token matching a JSON "
            "number literal, so an unquoted `4` returns as the int 4; this is "
            "the defect that is LIVE in Model B's own envelopes",
        )

    def test_s3_number_bool_and_null_lookalike_strings_survive_as_strings(self):
        for value in ("42", "true", "null"):
            with self.subTest(value=value):
                self._assert_string_survives(
                    "defect 2 — literal-lookalike string",
                    value,
                    "emitted BARE it is indistinguishable from the int 42, "
                    "the bool true or None, and the decoder re-types it",
                )

    def test_s3_empty_string_survives_and_is_not_an_empty_object(self):
        self._assert_string_survives(
            "defect 3 — empty string",
            "",
            "an empty scalar tail (`note: `) is indistinguishable from a "
            "`note:` nested-object header, so the empty string decodes as {}",
        )

    def test_s3_meaningful_leading_and_trailing_whitespace_survives(self):
        for label, value in (
            ("leading", "  indented note"),
            ("trailing", "note with trailing  "),
            ("both", "\tboth sides\t"),
        ):
            with self.subTest(whitespace=label):
                self._assert_string_survives(
                    "defect 4 — significant whitespace",
                    value,
                    "a blind `.strip()` on every decoded line discards it",
                )

    def test_s3_real_envelope_context_wave_string_survives_the_round_trip(self):
        """Defect 1 on the REAL envelope shape, not a synthetic dict.

        Built through the actual emit seam `modelb_axi.axi.envelope`, whose
        `context` sub-object is the client-adopter shape recorded in
        `contracts/crucible-envelope.md`. `wave` arrives from `$WORKFLOW_WAVE`,
        so it is a STRING — and an unquoted `wave: 4` decodes back as the int
        4, silently corrupting a Model B envelope today.
        """
        codec = self._require_codec()
        text = axi.envelope(
            "register", True,
            agent="CR-MDB-022-C2-RED",
            context={"projectKey": "019f7eb8-8cad-7000-9838-854eca8e7c20",
                     "agentId": "CR-MDB-022-C2-RED",
                     "role": "RED",
                     "wave": "4"},
        )
        try:
            decoded = codec.decode(text)
        except Exception as exc:
            raise AssertionError(
                f"§S3/AC5: the real envelope must decode "
                f"({type(exc).__name__}: {exc}); emitted:\n{text}"
            )
        wave = decoded.get("axi", {}).get("context", {}).get("wave")
        self.assertIsInstance(
            wave, str,
            "§S3/AC5: a real AXI envelope carrying `context.wave` as the "
            f"STRING '4' must round-trip with `wave` still a str, got "
            f"{wave!r} ({type(wave).__name__}) — the live instance of defect "
            f"1. Emitted wire text was:\n{text}",
        )
        self.assertEqual(
            wave, "4",
            f"§S3/AC5: `context.wave` must equal the string '4', got {wave!r}",
        )

    def test_s3_emitted_wire_form_is_accepted_by_crucibles_port(self):
        """The out-of-process conformance oracle (§S3/AC2 + AC6).

        Model B does not implement the TOON spec; it emits a documented valid
        SUBSET and PROVES that by round-tripping through Crucible's
        spec-conformant port as a SUBPROCESS. `crucible:clients/toon.py:1243`
        counts a list item only when the line starts with `- ` or equals `-`,
        so a non-empty header plus BARE indented items is refused. Accepted:
        the canonical INLINE `key[N]: <items>` (what their own encoder emits)
        or the hyphenated `- <item>` form. The inline form carries the quoting
        rule from their `_is_safe_unquoted` — an item that could be read as a
        delimiter, a structural token or another scalar TYPE is JSON-quoted.
        """
        self._require_oracle()
        codec = self._require_codec()

        # The exact defect shape from the degrade path, first.
        payload = {"axi": {"verb": "next", "ok": True,
                           "warnings": [DEGRADE_WARNING], "help": []}}
        text = codec.encode(payload)
        header, items = _array_block(text, "warnings")
        self.assertIsNotNone(
            header, f"§S3/AC2: no `warnings` array block emitted in:\n{text}"
        )
        bare_items = [
            item for item in items
            if not (item == "-" or item.startswith("- "))
        ]
        self.assertEqual(
            bare_items, [],
            "§S3/AC2: a NON-EMPTY scalar list must be emitted INLINE "
            "(`warnings[1]: <item>`) or in hyphenated list form "
            "(`warnings[1]:` + `- <item>`). A header plus BARE indented items "
            "is REJECTED by the reference port with `Expected 1 list-form "
            "items, but got 0` — this is the actual defect behind the "
            f"`next`/`progress` failures. Emitted header={header!r} "
            f"bare items {bare_items} in:\n{text}",
        )
        try:
            self.assertEqual(
                _oracle_decode(text), payload,
                "§S3/AC2: Crucible's port must decode Model B's non-empty-list "
                f"envelope back to the same value; emitted:\n{text}",
            )
        except OracleRejected as exc:
            raise AssertionError(
                f"§S3/AC2: Crucible's spec-conformant port REJECTED Model B's "
                f"non-empty-list envelope ({exc}); emitted:\n{text}"
            )

        # The quoting rule, item by item. `must_quote` items would change TYPE
        # or split on the delimiter if emitted bare; the em dash must NOT be
        # quoted, matching their encoder's own output.
        must_quote = ("a, b", "key: value", "arr[0]", "x]y",
                      "4", "42", "true", "null", "", "  leading", "trailing  ")
        must_stay_bare = (DEGRADE_WARNING, "schedule_db unavailable")
        for value in must_quote:
            with self.subTest(quoting=value, expected="quoted"):
                wire = codec.encode({"warnings": [value]})
                _, wire_items = _array_block(wire, "warnings")
                inline = wire.splitlines()[0]
                rendered = wire_items[0] if wire_items else inline.split(":", 1)[1].strip()
                rendered = rendered[2:].strip() if rendered.startswith("- ") else rendered
                self.assertEqual(
                    rendered, json.dumps(value),
                    f"§S3/AC6: {value!r} must be JSON-quoted on the wire — "
                    "bare it would be read as another scalar type or split on "
                    f"the `,` delimiter. Emitted {rendered!r} in:\n{wire}",
                )
                self.assertEqual(
                    _oracle_decode(wire), {"warnings": [value]},
                    f"§S3/AC6: Crucible's port must read {value!r} back "
                    f"unchanged from:\n{wire}",
                )
        for value in must_stay_bare:
            with self.subTest(quoting=value, expected="bare"):
                wire = codec.encode({"warnings": [value]})
                self.assertNotIn(
                    '"', wire,
                    f"§S3/AC6: {value!r} is safe unquoted (a plain em dash is "
                    "not a special character), so quoting it would diverge "
                    f"from the reference encoder. Emitted:\n{wire}",
                )
                self.assertEqual(
                    _oracle_decode(wire), {"warnings": [value]},
                    f"§S3/AC6: Crucible's port must accept the bare form "
                    f"of {value!r} from:\n{wire}",
                )

    def test_s3_empty_list_headers_are_left_alone(self):
        """§S3/AC3 — `status`'s envelope is entirely `[0]` headers and already
        decodes. Asserted through the SUBPROCESS oracle so it is meaningful
        TODAY, then through Model B's codec so the cycle cannot regress it.
        A change to the empty form would be churn, not a fix."""
        self._require_oracle()
        result = _run_worktree_flow(REPO_ROOT, ("status",))
        self.assertEqual(
            result.returncode, 0,
            f"status must exit 0, got {result.returncode}; "
            f"stderr:\n{result.stderr[:1000]}",
        )
        empty_headers = [
            line.strip() for line in result.stdout.splitlines()
            if line.strip().endswith("[0]:")
        ]
        self.assertNotEqual(
            empty_headers, [],
            "§S3/AC3: `status` must still emit `[0]` headers "
            "(`lanes[0]:`/`warnings[0]:`/`help[0]:`) — they are VALID and this "
            f"cycle must not touch them. stdout was:\n{result.stdout}",
        )
        try:
            before = _oracle_decode(result.stdout)
        except OracleRejected as exc:
            raise AssertionError(
                "§S3/AC3: `status`'s empty list headers decode cleanly against "
                f"Crucible's port TODAY and must keep doing so; got {exc} on:\n"
                f"{result.stdout}"
            )
        codec = self._require_codec()
        try:
            after = codec.decode(result.stdout)
        except Exception as exc:
            raise AssertionError(
                "§S3/AC3: `status` must ALSO decode with Model B's own codec "
                f"({type(exc).__name__}: {exc}); stdout was:\n{result.stdout}"
            )
        self.assertEqual(
            after, before,
            "§S3/AC3: Model B's decoder and the reference port must agree on "
            f"`status`; Model B read {after!r}, the port read {before!r}",
        )

    def test_s3_the_surviving_list_verb_decodes_on_a_queue_only_project(self):
        codec = self._require_codec()
        rejected = []
        with tempfile.TemporaryDirectory(prefix="mdb022-wf-") as tmp:
            project_dir = _queue_only_project(Path(tmp))
            for argv in WF_VERBS:
                label = " ".join(argv)
                result = _run_worktree_flow(project_dir, argv)
                try:
                    decoded = codec.decode(result.stdout)
                except Exception as exc:
                    rejected.append(
                        f"  {label}: {type(exc).__name__}: {exc} "
                        f"(exit={result.returncode})\n"
                        f"    stdout={result.stdout!r}\n"
                        f"    stderr={result.stderr[:400]!r}"
                    )
                    continue
                if "axi" not in decoded:
                    rejected.append(
                        f"  {label}: decoded but carries no top-level `axi` "
                        f"envelope (keys={list(decoded)})"
                    )
                    continue
                envelope = decoded["axi"]
                if envelope.get("verb") != argv[0]:
                    rejected.append(
                        f"  {label}: envelope must name its verb, got "
                        f"{envelope.get('verb')!r}"
                    )
        self.assertEqual(
            rejected, [],
            "§S3/AC7: `worktree-flow.py status` must "
            "emit stdout Model B's own decoder accepts on a project with "
            "no ChangeSet DB:\n" + "\n".join(rejected),
        )


if __name__ == "__main__":
    unittest.main()
