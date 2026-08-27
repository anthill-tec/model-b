"""RED-phase tests for CR-MDB-022 cycle C2 (§S2 -- one TOON codec, owned by
Model B; §S3 -- fix the empty-array defect and pin the round trip).

Written before any of §S2/§S3's production code lands on this branch.

MEASURED PRE-STATE (2026-08-27, commit 91ff12f -- C1 GREEN):
  - `modelb_axi/axi.py` (95 lines) exposes `encode` and `envelope` and NO
    `decode`, and its `_encode_into()` raises `TypeError` for a list of
    dicts ("may hold scalars only in the envelope subset"), so it cannot
    emit the uniform-object-table construct `worktree-flow.py` already
    prints. Every §S3 round-trip assertion therefore fails on the missing
    decoder, and the populated-table one fails on the encoder too.
  - `scripts/toon.py` (258 lines) is a SECOND, independent implementation
    with its own `def encode` / `def decode`, not a re-export, so the
    identity assertion fails. Its header line 5 reads
    "DEPLOYED COPY -- source of truth crucible:clients/toon.py (TRACKS
    Crucible)" and `scripts/worktree-flow.py:122` repeats the same
    provenance claim in a comment; both carry the phrase §S2/AC5 forbids.
  - `modelb_axi/axi.py:12` cites the governing note by bare filename and
    `scripts/toon.py:11` cites it as `docs/research/<file>` -- neither
    carries the `crucible:` anchor §S3/AC5 requires.
  - `tests/test_worktree_flow_axi.py` inserted
    `<crucible-checkout>/clients` on `sys.path` and imported `toon` from
    it. That insert and import are REMOVED by this cycle's sanctioned
    amendment, so the §S2/AC3 scan below finds no remaining path insert
    resolving outside this repo and PASSES.
  - Corroboration for the finding below: with CRUCIBLE's decoder as the
    oracle, `tests/test_worktree_flow_axi.py` failed exactly 3 of 6, and
    the one envelope test that PASSED was `status` -- the verb whose every
    list is empty (`lanes[0]:`/`warnings[0]:`/`help[0]:`). The 3 that
    failed are the ones reaching a NON-EMPTY `warnings[1]:` block. The
    empty-list headers were therefore never the defect; after the
    amendment all 4 envelope tests fail uniformly on the absent
    `modelb_axi.axi.decode`, which is this cycle's sanctioned RED.

THE WIRE CONTRACT, ESTABLISHED EMPIRICALLY (not assumed):
`crucible:docs/research/DN-crucible-toon-subset.md` is RETIRED (by
CR-CRU-046, 2026-08-01) and now points at the OFFICIAL TOON spec
(toonformat.dev) as the wire contract, with `crucible:clients/toon.py`
as the spec-conformant Python port validated against the first-party
`@toon-format/toon` reference implementation. That port was therefore
probed as the live reference (read as reference and driven out-of-process
only -- nothing in this repo imports it), yielding:

  EMPTY primitive array   ACCEPTED: `key: []`  (canonical -- the form their
                                    encoder emits) and `key[0]:`
                          REJECTED: `key[0]: []`
  NON-EMPTY prim. array   ACCEPTED: `key[N]: a,b` (canonical, inline) and
                                    `key[N]:` + `- item` per indented line
                          REJECTED: `key[N]:` + BARE indented item lines
  Zero-row uniform table  ACCEPTED: `key: []`, `key[0]:`, `key[0]{a,b}:`

That relocates the defect. `rows[0]:`/`help[0]:`/`lanes[0]:` -- the
empty-list headers -- DECODE CLEANLY; `worktree-flow.py status`, whose
lists are all empty, already round-trips. What the reference decoder
refuses is the NON-EMPTY scalar list rendered as a header plus bare
indented items (`_decode_list_array` requires a `- ` prefix per item,
`crucible:clients/toon.py:1243`), which is why `next` and `progress` fail
with `Expected 1 list-form items, but got 0` on their
`warnings[1]:` block and not on their `[0]` headers. Both wire forms are
pinned below, because a codec whose decoder merely tolerates its own
encoder's private dialect satisfies a round-trip assertion while staying
unreadable to every other subset decoder -- the exact failure this cycle
exists to remove.

Stdlib only: ast + pathlib + subprocess + tempfile + unittest. Nothing
here reads, writes or deletes under `~/.claude`, and nothing invokes
`chezmoi`.
"""

import ast
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from modelb_axi import axi  # noqa: E402  (repo-local codec under test)

SCRIPTS_DIR = REPO_ROOT / "scripts"
SCRIPTS_TOON = SCRIPTS_DIR / "toon.py"
WORKTREE_FLOW = SCRIPTS_DIR / "worktree-flow.py"

#: §S2/AC5 + §S3/AC5 gate surface. Positively enumerated in the same shape
#: §S6 uses, rather than "the whole repo minus exclusions". `docs/changes/`
#: is deliberately absent: the CR ledger is the SPECIFICATION of these two
#: gates and must quote the forbidden phrase and the bare filename verbatim
#: in order to define them, so sweeping it would make both gates
#: unsatisfiable by construction.
LIVE_SURFACE_DIRS = (
    "modelb_axi", "scripts", "tests", "contracts", "skills-src", "hooks-src",
)
LIVE_SURFACE_FILES = ("AGENTS.md",)

SKIP_DIR_NAMES = frozenset(
    {".git", "__pycache__", ".pytest_cache", ".ruff_cache", "build", "dist"}
)

#: Assembled at run time so the literal phrase never appears in this
#: module's own source -- the gate then covers `tests/` INCLUDING itself,
#: with no self-exclusion carve-out.
FORBIDDEN_PROVENANCE = "copy of " + "crucible:"

#: §S3/AC5. Every citation of Crucible's note must carry the `crucible:`
#: anchor; `crucible:docs/research/` is 23 characters, so a 24-character
#: look-behind window covers both `crucible:<file>` and the canonical
#: `crucible:docs/research/<file>`.
#: Assembled like FORBIDDEN_PROVENANCE above, so this needle is not itself
#: an unanchored citation and the gate can cover its own source file.
DN_FILENAME = "DN-crucible-" + "toon-subset.md"
DN_ANCHOR = "crucible:"
DN_ANCHOR_WINDOW = 24

#: §S2/AC3. Module names that must never resolve to Crucible's checkout.
CRUCIBLE_MODULE_NAMES = ("toon", "_crucible_axi")

#: §S2/AC4. The sanctioned exception: INVOKING their client as a
#: subprocess is required, not forbidden.
SANCTIONED_INVOCATION = "clients/python-crucible.py"

#: §S3. The empty-primitive-array renderings `crucible:clients/toon.py`
#: accepts; the first is canonical (its own encoder's output).
EMPTY_ARRAY_FORMS = ("{key}: []", "{key}[0]:")

WF_VERBS = (("status",), ("next",), ("progress", "--cr", "CR-MDB-000-probe"))

DEGRADE_MARKER = "schedule_db unavailable"


def _live_surface_files() -> list:
    """Every text file on the §S2/§S3 gate surface."""
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
    """The `.py` files §S2/AC3 names: scripts/, modelb_axi/, tests/."""
    return [
        path for path in _live_surface_files()
        if path.suffix == ".py"
        and path.relative_to(REPO_ROOT).parts[0] in ("scripts", "modelb_axi", "tests")
    ]


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _module_string_constants(tree: ast.Module) -> dict:
    """Module-level ``NAME = "literal"`` bindings, so a `sys.path` insert
    fed by a named constant is resolved rather than silently skipped."""
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

    Matching on the CALL NODE rather than on file text is what makes the
    §S2/AC4 distinction mechanical: a path string handed to
    `subprocess.run` is an INVOCATION and is never a `sys.path` mutation
    node, so it cannot be swept here. An argument computed at run time
    (`str(REPO_ROOT)`, `os.path.dirname(os.path.abspath(__file__))`) is
    repo-relative by construction and is not flagged.
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
    """`import toon` / `import _crucible_axi` that cannot resolve inside
    this repo. `scripts/worktree-flow.py`'s `import toon` resolves to its
    sibling `scripts/toon.py` and is correct."""
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


def _load_scripts_toon():
    """Load `scripts/toon.py` under a private module name (never `toon`,
    so `sys.modules` is not polluted for any other test)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_mdb022_scripts_toon", SCRIPTS_TOON
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    """§S2 -- exactly one TOON implementation, owned by Model B."""

    def test_s2_codec_exposes_encode_and_decode(self):
        missing = [
            name for name in ("encode", "decode")
            if not callable(getattr(axi, name, None))
        ]
        self.assertEqual(
            missing, [],
            "§S2/AC1: Model B's codec in modelb_axi/ must expose BOTH encode "
            f"and decode; missing/not callable: {missing}. modelb_axi.axi "
            f"currently exports: "
            f"{sorted(n for n in vars(axi) if not n.startswith('_'))}",
        )

    def test_s2_scripts_toon_is_a_thin_reexport_of_the_one_codec(self):
        self.assertTrue(
            SCRIPTS_TOON.is_file(), f"{_rel(SCRIPTS_TOON)} must exist (§S1)"
        )
        # STRUCTURAL -- "holds no second implementation".
        tree = ast.parse(
            SCRIPTS_TOON.read_text(encoding="utf-8", errors="replace"),
            str(SCRIPTS_TOON),
        )
        redefined = sorted(
            node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in ("encode", "decode")
        )
        self.assertEqual(
            redefined, [],
            f"§S2/AC2: {_rel(SCRIPTS_TOON)} must be a thin re-export of the "
            "modelb_axi codec and hold no second implementation, but it "
            f"defines {redefined} itself",
        )
        # IDENTITY -- the AC's own discriminator, not a line count.
        module = _load_scripts_toon()
        for name in ("encode", "decode"):
            self.assertIs(
                getattr(module, name, None), getattr(axi, name, None),
                f"§S2/AC2: {_rel(SCRIPTS_TOON)}.{name} must BE the same "
                f"callable object as modelb_axi.axi.{name} (re-export), got "
                f"{getattr(module, name, None)!r} vs "
                f"{getattr(axi, name, None)!r}",
            )

    def test_s2_no_repo_file_imports_a_module_from_crucible_checkout(self):
        insert_offenders = {}
        import_offenders = {}
        for path in _python_gate_files():
            inserts = _path_inserts_outside_repo(path)
            if inserts:
                insert_offenders[_rel(path)] = inserts
            imports = _crucible_imports(path)
            if imports:
                import_offenders[_rel(path)] = imports
        self.assertEqual(
            insert_offenders, {},
            "§S2/AC3: zero sys.path inserts naming a path outside this repo "
            "are permitted under scripts/, modelb_axi/ or tests/; found "
            f"{insert_offenders}",
        )
        self.assertEqual(
            import_offenders, {},
            "§S2/AC3: no repo file may IMPORT a Python module out of "
            "Crucible's checkout (forking their code into our process); "
            f"found {import_offenders}",
        )
        # §S2/AC4 -- the sanctioned exception, asserted as PERMITTED rather
        # than forbidden. Model B dogfoods Crucible as a consumer and this
        # machine drives their DEV server, so INVOKING
        # clients/python-crucible.py as a subprocess is correct and must
        # never be swept by the gate above. Only IMPORTS are.
        invocation_sites = sorted(
            _rel(path) for path in _live_surface_files()
            if SANCTIONED_INVOCATION
            in path.read_text(encoding="utf-8", errors="replace")
        )
        self.assertNotEqual(
            invocation_sites, [],
            f"§S2/AC4: the repo must still INVOKE {SANCTIONED_INVOCATION} as "
            "a subprocess -- that is how a consumer uses their tool, and the "
            "import gate must not have removed it",
        )
        swept = sorted(
            set(invocation_sites)
            & (set(insert_offenders) | set(import_offenders))
        )
        self.assertEqual(
            swept, [],
            f"§S2/AC4: invoking {SANCTIONED_INVOCATION} as a subprocess is "
            "SANCTIONED; the gate distinguishes IMPORT (forbidden) from "
            f"INVOCATION (required) and must not flag {swept}",
        )

    def test_s2_no_file_claims_to_be_a_copy_of_a_crucible_file(self):
        offenders = {}
        for path in _live_surface_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            hits = [
                lineno for lineno, line in enumerate(text.splitlines(), start=1)
                if FORBIDDEN_PROVENANCE in line
            ]
            if hits:
                offenders[_rel(path)] = hits
        self.assertEqual(
            offenders, {},
            f"§S2/AC5: the phrase {FORBIDDEN_PROVENANCE!r} must not appear on "
            "the live surface -- a Model B file that self-describes as a copy "
            "of a Crucible file cannot be owned here without contradicting "
            f"the no-client-maintenance directive; found {offenders}",
        )

    def test_s2_every_dn_citation_carries_the_crucible_anchor(self):
        offenders = {}
        for path in _live_surface_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            bare = []
            start = text.find(DN_FILENAME)
            while start != -1:
                window = text[max(0, start - DN_ANCHOR_WINDOW):start]
                if DN_ANCHOR not in window:
                    bare.append(text.count("\n", 0, start) + 1)
                start = text.find(DN_FILENAME, start + 1)
            if bare:
                offenders[_rel(path)] = bare
        self.assertEqual(
            offenders, {},
            f"§S3/AC5: every citation of {DN_FILENAME} must carry the "
            f"{DN_ANCHOR!r} anchor (the note is CRUCIBLE-owned and Model B "
            f"may not edit it); unanchored citations at {offenders}",
        )


class ToonEnvelopeS3Test(unittest.TestCase):
    """§S3 -- the empty-array form, the round trip that pins it, and the
    zero-row verbs on a project with NO ChangeSet DB (the
    `schedule_db unavailable -- queue-only project` degrade path, which is
    the path that emits the empty-list headers)."""

    EMPTY_ENVELOPE = {
        "axi": {
            "verb": "status", "ok": True, "project": "model-b",
            "lanes": [], "warnings": [], "help": [],
        }
    }
    TABLE_ENVELOPE = {
        "axi": {
            "verb": "status", "ok": True,
            "worktrees": [
                {"role": "integration", "branch": "develop", "ahead": 0},
                {"role": "track", "branch": "feature/CR-MDB-022", "ahead": 3},
            ],
            "warnings": [],
        }
    }
    SCALAR_ENVELOPE = {
        "axi": {
            "verb": "next", "ok": True, "project": "model-b",
            "track": None, "decision": "DRAINED", "cr": None,
        }
    }

    def _require_decode(self):
        decode = getattr(axi, "decode", None)
        if not callable(decode):
            self.fail(
                "§S3/AC1: modelb_axi.axi.decode does not exist, so the "
                "round trip cannot even be attempted -- §S2's decoder is "
                "the prerequisite for every §S3 assertion"
            )
        return decode

    def test_s3_empty_list_envelope_round_trips(self):
        text = axi.encode(self.EMPTY_ENVELOPE)
        # WIRE FORM first: the empty array must be rendered in a form the
        # published reference decoder accepts, so the round trip below is
        # interoperability and not a codec agreeing with itself.
        accepted = [form.format(key="lanes") for form in EMPTY_ARRAY_FORMS]
        header, items = _array_block(text, "lanes")
        self.assertIn(
            header, accepted,
            "§S3: the empty-array form must be one the published reference "
            "decoder (crucible:clients/toon.py, validated against "
            f"@toon-format/toon) accepts -- {accepted[0]!r} is canonical, "
            f"{accepted[1]!r} is also accepted, and `lanes[0]: []` is "
            f"REJECTED. Emitted {header!r} in:\n{text}",
        )
        self.assertEqual(
            items, [],
            f"§S3: an empty array must carry no item lines, got {items}",
        )
        decode = self._require_decode()
        self.assertEqual(
            decode(text), self.EMPTY_ENVELOPE,
            "§S3/AC1: decode(encode(x)) == x must hold for an envelope "
            f"carrying an empty list; encoded text was:\n{text}",
        )

    def test_s3_populated_table_and_scalar_envelopes_round_trip(self):
        decode = self._require_decode()
        for label, payload in (
            ("populated uniform table", self.TABLE_ENVELOPE),
            ("scalar-only envelope", self.SCALAR_ENVELOPE),
        ):
            with self.subTest(payload=label):
                text = axi.encode(payload)
                self.assertEqual(
                    decode(text), payload,
                    f"§S3/AC1: the {label} must round-trip too -- the empty "
                    "case must not be special-cased into existence at the "
                    f"cost of the normal ones; encoded text was:\n{text}",
                )

    def test_s3_nonempty_scalar_list_uses_a_reference_accepted_wire_form(self):
        warning = "schedule_db unavailable - queue-only project"
        text = axi.encode({"axi": {"verb": "next", "warnings": [warning]}})
        header, items = _array_block(text, "warnings")
        self.assertIsNotNone(
            header, f"§S3: no `warnings` array block emitted in:\n{text}"
        )
        inline = header != "warnings[1]:" and not items
        hyphenated = bool(items) and all(
            item == "-" or item.startswith("- ") for item in items
        )
        self.assertTrue(
            inline or hyphenated,
            "§S3: a NON-EMPTY scalar list must be emitted either inline "
            "(`warnings[1]: <item>`) or in hyphenated list form "
            "(`warnings[1]:` + `- <item>` per line). A header plus BARE "
            "indented items is REJECTED by the reference decoder "
            "(crucible:clients/toon.py:1243 requires the `- ` prefix, "
            "raising `Expected 1 list-form items, but got 0`) -- this is the "
            "actual defect behind the `next`/`progress` failures, not the "
            f"`[0]` headers. Emitted header={header!r} items={items} in:\n{text}",
        )

    @staticmethod
    def _queue_only_project(parent: Path) -> Path:
        """A git repo with NO ChangeSet DB, so `worktree-flow.py` takes its
        `schedule_db unavailable -- queue-only project` degrade path."""
        project_dir = parent / "queue-only"
        project_dir.mkdir()
        git = [
            "git", "-c", "user.name=CR-MDB-022", "-c",
            "user.email=cr-mdb-022@example.invalid",
        ]
        for argv in (
            ["init", "-q", "-b", "main", "."],
            ["commit", "-q", "--allow-empty", "-m", "init"],
        ):
            subprocess.run(
                [*git, *argv], cwd=project_dir, check=True,
                capture_output=True, timeout=60,
            )
        return project_dir

    @staticmethod
    def _run_verb(project_dir: Path, argv):
        return subprocess.run(
            [sys.executable, str(WORKTREE_FLOW), *argv,
             "--project-dir", str(project_dir)],
            capture_output=True, text=True, timeout=60,
            stdin=subprocess.DEVNULL,
        )

    def test_s3_worktree_flow_zero_row_verbs_decode_with_model_bs_codec(self):
        decode = getattr(axi, "decode", None)
        if not callable(decode):
            self.fail(
                "§S3/AC2: modelb_axi.axi.decode does not exist, so "
                "worktree-flow.py's stdout cannot be checked against Model "
                "B's own decoder at all"
            )
        rejected = []
        degrade_seen = []
        with tempfile.TemporaryDirectory(prefix="mdb022-wf-") as tmp:
            project_dir = self._queue_only_project(Path(tmp))
            for argv in WF_VERBS:
                label = " ".join(argv)
                result = self._run_verb(project_dir, argv)
                try:
                    obj = decode(result.stdout)
                except Exception as exc:
                    rejected.append(
                        f"  {label}: {type(exc).__name__}: {exc} "
                        f"(exit={result.returncode})\n"
                        f"    stdout={result.stdout!r}\n"
                        f"    stderr={result.stderr[:400]!r}"
                    )
                    continue
                if "axi" not in obj:
                    rejected.append(
                        f"  {label}: decoded but has no top-level `axi` "
                        f"envelope (keys={list(obj)})"
                    )
                    continue
                envelope = obj["axi"]
                if envelope.get("verb") != argv[0]:
                    rejected.append(
                        f"  {label}: envelope must name its verb, got "
                        f"{envelope.get('verb')!r}"
                    )
                if any(
                    DEGRADE_MARKER in str(warning)
                    for warning in envelope.get("warnings") or ()
                ):
                    degrade_seen.append(label)
        self.assertEqual(
            rejected, [],
            "§S3/AC2: `worktree-flow.py status`, `next` and `progress` must "
            "each emit stdout Model B's own decoder accepts on a project "
            "with no ChangeSet DB:\n" + "\n".join(rejected),
        )
        self.assertNotEqual(
            degrade_seen, [],
            "§S3/AC2: at least one verb must surface the "
            f"'{DEGRADE_MARKER} -- queue-only project' warning, proving the "
            "no-ChangeSet-DB degrade path is the path under test rather than "
            "a project that happened to have a DB",
        )


if __name__ == "__main__":
    unittest.main()
