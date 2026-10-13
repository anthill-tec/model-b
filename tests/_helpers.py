"""Shared test helpers (CR-MDB-032).

``installed_crucible_file`` resolves an installed Crucible client file through Crucible's
manifest ``~/.crucible/crucible-clients.json`` — the one sanctioned out-of-repo dependency
(standing rule 2026-09-18). No test reaches a personal Crucible checkout (CR-MDB-032 §S1): a
test that needs an installed client resolves it here and SKIPS, naming the manifest, when the
manifest, its entry or the file is missing.

Every other helper here is one that several test modules used to define privately with an
identical body (CR-MDB-032 §S3); a module imports it under its old local name. Where two
look-alikes behave differently they stay two helpers — ``read_text`` (strict UTF-8) and
``read_text_lenient`` (undecodable bytes replaced) are not one function.

Stdlib only.
"""

import ast
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

from tests.pi_capability_sandbox import with_agent_dir

REPO_ROOT = Path(__file__).resolve().parent.parent

#: How every skip reason spells the manifest, so a reader can find it on any machine.
CRUCIBLE_MANIFEST_SPELLING = "~/.crucible/crucible-clients.json"


def installed_crucible_file(stack: str, sibling: str | None = None) -> tuple:
    """``(path, "")`` for the installed client ``clients[stack]`` listed in Crucible's manifest,
    or — when ``sibling`` is given — for the file of that name beside it (the installed clients
    directory also ships ``toon.py``). ``(None, reason)`` when anything is missing; ``reason``
    names ``~/.crucible/crucible-clients.json`` and what was missing, ready for ``skipTest``.

    Manifest paths are used as written: Crucible's installer records absolute paths.
    """
    manifest = Path.home() / ".crucible" / "crucible-clients.json"
    if not manifest.is_file():
        return None, f"{CRUCIBLE_MANIFEST_SPELLING} is absent ({manifest}); no installed Crucible client to use"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"{CRUCIBLE_MANIFEST_SPELLING} is unreadable ({type(exc).__name__}: {exc})"
    clients = data.get("clients") if isinstance(data, dict) else None
    entry = clients.get(stack) if isinstance(clients, dict) else None
    if not isinstance(entry, str) or not entry:
        return None, f"{CRUCIBLE_MANIFEST_SPELLING} lists no clients[{stack!r}] entry"
    client = Path(entry)
    target = client.parent / sibling if sibling else client
    if not target.is_file():
        what = f"{sibling} beside clients[{stack!r}]" if sibling else f"clients[{stack!r}]"
        return None, f"{CRUCIBLE_MANIFEST_SPELLING} names {what}, but {target} is not a file"
    return target, ""


# ------------------------------------------------------------------ file reads ----

def read_text(path: Path) -> str:
    """``path`` as strict UTF-8 text (a decode error raises)."""
    return path.read_text(encoding="utf-8")


def read_text_lenient(path: Path) -> str:
    """``path`` as UTF-8 text with undecodable bytes replaced (never raises on encoding)."""
    return path.read_text(encoding="utf-8", errors="replace")


def files_under(dir_path: Path):
    """Yield all regular files under dir_path (recursive). Empty if dir absent."""
    if not dir_path.is_dir():
        return
    for root, _dirs, files in os.walk(dir_path):
        for name in files:
            yield Path(root) / name


def files_containing(dir_path: Path, needle: str):
    """Return sorted relative paths of files under dir_path whose content contains needle."""
    hits = []
    for f in files_under(dir_path):
        try:
            content = read_text_lenient(f)
        except (UnicodeDecodeError, OSError):
            continue
        if needle in content:
            hits.append(str(f.relative_to(dir_path)))
    return sorted(hits)


#: The wave-2 archive the retired-content moves landed in.
ARCHIVE_WAVE2 = REPO_ROOT / "archive" / "wave2"


def archive_has_content_move(name: str, anchor: str) -> bool:
    """True if some file under archive/wave2/ has `name` as a path component
    (or matching filename) and its content contains `anchor` -- tolerant of
    exact archival layout (flat file vs mirrored subdirectory) while still
    proving it is a REAL content-preserving copy, not a stub."""
    for f in files_under(ARCHIVE_WAVE2):
        if name not in f.parts and f.name != name:
            continue
        try:
            content = read_text_lenient(f)
        except (UnicodeDecodeError, OSError):
            continue
        if anchor in content:
            return True
    return False


# ------------------------------------------------------------------ AXI envelopes ----

def decode_axi(stdout: str) -> dict:
    """The ``axi`` mapping of a TOON envelope printed on stdout, decoded with the package's OWN
    codec; ``{}`` when stdout is not an envelope (the caller's assertions then report it)."""
    from modelb_axi.toon import decode
    try:
        return decode(stdout).get("axi", {})
    except Exception:  # noqa: BLE001 -- a non-envelope stdout fails the caller's asserts
        return {}


def decode_envelope(stdout: str) -> dict:
    """Decode a ``modelb_axi`` TOON envelope printed on stdout, whole, using the package's OWN
    codec (a decode error raises)."""
    from modelb_axi.toon import decode
    return decode(stdout)


# ------------------------------------------------------------------ markdown ----

def split_frontmatter(content: str):
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


def md_section(content: str, heading_prefix: str, stop_prefix: str = "## ") -> str:
    """The Markdown section whose heading line starts with
    ``heading_prefix``, up to (not including) the next line starting with
    ``stop_prefix`` -- by default the next ``## `` heading; ``stop_prefix="#"``
    stops at the next heading of any level (a ``### `` subsection). ``""``
    when no such heading exists."""
    out: list[str] = []
    inside = False
    for line in content.splitlines():
        if not inside and line.startswith(heading_prefix):
            inside = True
            out.append(line)
            continue
        if inside and line.startswith(stop_prefix):
            break
        if inside:
            out.append(line)
    return "\n".join(out)


def parse_env_file(path: Path) -> dict:
    """Minimal ``KEY=VALUE`` parser for an emitted ``.env``/``.env.local``
    (values may be bare or double-quoted; blank lines and ``#``-comments are
    skipped; ``{}`` when the file is absent) -- test-side only, no production
    coupling."""
    values: dict = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw_value = stripped.partition("=")
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        values[key.strip()] = value
    return values


# ------------------------------------------------------------------ fixtures ----

def run_module(*args, env_overrides=None, timeout=15, stdin=subprocess.DEVNULL):
    """Invoke `python -m modelb_axi <args>` with the repo root on
    PYTHONPATH (mirrors tests/test_installer.py's `_run_module`), so a
    not-yet-existing subcommand surfaces as a clean subprocess-level
    argparse failure instead of an in-process error."""
    env = dict(os.environ)
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
    if env_overrides:
        env.update(env_overrides)
    # CR-MDB-037 migration: init now reads Pi's trust.json and settings
    # from the agent dir (§S4) -- pin PI_CODING_AGENT_DIR to a sandbox so
    # no run reads the real ~/.pi.
    env.update(with_agent_dir(env_overrides))
    cmd = [sys.executable, "-m", "modelb_axi", *args]
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, stdin=stdin, env=env,
    )


def write_install_toml(home: str, harnesses=("pi",)) -> Path:
    """Valid install.toml fixture -- the seam §S2 reads the installed
    harness set from (DN-scaffold-packaging.md §3). Records
    ``hooks_scripts_dir`` as every install after CR-MDB-033 §S1 does,
    pointed at the sandbox (never the real home)."""
    harnesses_toml = ", ".join(f'"{h}"' for h in harnesses)
    hooks_scripts_dir = Path(home) / ".agents" / "hooks" / "scripts"
    install_toml = Path(home) / "install.toml"
    install_toml.write_text(
        "[install]\n"
        'version = "0.1.0"\n'
        f"harnesses = [{harnesses_toml}]\n"
        'asset_root = "/tmp/does-not-matter-for-this-test"\n'
        f'hooks_scripts_dir = "{hooks_scripts_dir}"\n'
        "\n"
        "[deps]\n"
        'uv = "present"\n'
        "\n"
        "[files]\n",
        encoding="utf-8",
    )
    return install_toml

def write_executable(bin_dir, name: str, body: str) -> Path:
    """Write an executable script fixture at ``bin_dir/name`` (mode 0755) and return its path --
    the seam for fake ``uv``/``sandesh``/``pi`` binaries on an isolated tmp ``PATH``."""
    path = Path(bin_dir) / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def client_source(key: str, log_path: Path, envelope: str) -> str:
    """An executable fixture client: logs its key + argv to ``log_path``, prints
    ``envelope``, exits 0."""
    return (
        f"#!{sys.executable}\n"
        "import json, sys\n"
        f"with open({str(log_path)!r}, 'a', encoding='utf-8') as fh:\n"
        f"    fh.write(json.dumps({{'key': {key!r}, 'argv': sys.argv[1:]}}) + '\\n')\n"
        f"print({envelope!r})\n"
    )

# ------------------------------------------------------------------ interpreter fixture ----

#: The published Python floor (CR-MDB-064 §S2): the installer accepts an interpreter at or
#: above it and records it.
PYTHON_FLOOR = "3.14"
#: The version the shared installer fixture's ``python3`` reports: exactly the floor.
FIXTURE_PYTHON_VERSION = "3.14.0"
#: The remediation §S2 names when no interpreter meets the floor.
PYTHON_REMEDIATION = "uv python install 3.14"
#: The uv query §S2 names for the second candidate: ``uv python find --system '>=3.14'``.
UV_PYTHON_FIND_ARGS = ("python", "find", "--system", ">=3.14")

#: What a fake ``uv`` does for every invocation but the interpreter query: a ``tool install``
#: succeeds, anything else prints a version and exits 0.
DEFAULT_UV_BODY = (
    "#!/bin/sh\n"
    'if [ "$1" = "tool" ] && [ "$2" = "install" ]; then exit 0; fi\n'
    'echo "uv 0.0.0-fake"\n'
    "exit 0\n"
)

_PYTHON3_STUB_BODY = r'''
import collections
import os
import re
import sys

_args = sys.argv[1:]
if _LOG:
    with open(_LOG, "a", encoding="utf-8") as _fh:
        _fh.write(" ".join(["python3", *_args]).replace("\n", "\\n") + "\n")
_major, _minor, _micro = (int(_p) for _p in _VERSION.split("."))
_i = 0
while _i < len(_args):
    _a = _args[_i]
    if _a in ("-V", "--version", "-VV"):
        print(f"Python {_VERSION}")
        sys.exit(0)
    if _a in ("-c", "-m", "-") or not _a.startswith("-"):
        break
    _i += 2 if _a in ("-X", "-W") else 1
_rest = _args[_i:]
if not _rest:
    sys.exit(0)
if _rest[0] == "-m":
    sys.exit(0)
if _rest[0] == "-c":
    _code, _argv = (_rest[1] if len(_rest) > 1 else ""), ["-c", *_rest[2:]]
elif _rest[0] == "-":
    _code, _argv = sys.stdin.read(), ["-", *_rest[1:]]
else:
    with open(_rest[0], encoding="utf-8") as _fh:
        _code = _fh.read()
    _argv = list(_rest)
# An import-only program is a module check (the stack python probe's `-c "import …"`):
# answered without importing anything, as a bare `exit 0` stub answered it.
if re.fullmatch(r"\s*(?:import\s+[\w.]+(?:\s*,\s*[\w.]+)*\s*;?\s*)+", _code):
    sys.exit(0 if _IMPORTS_OK else 1)
_info = collections.namedtuple("version_info", "major minor micro releaselevel serial")(
    _major, _minor, _micro, "final", 0)
sys.version_info = _info
sys.version = f"{_VERSION} (main, Oct  1 2026, 00:00:00) [GCC 14.2.0]"
sys.hexversion = (_major << 24) | (_minor << 16) | (_micro << 8) | 0xF0
try:
    sys.implementation.version = _info
except (AttributeError, TypeError):
    pass
sys.base_prefix = sys.base_exec_prefix = "/usr"
sys.prefix = sys.exec_prefix = "/opt/fixture-venv" if _VENV else "/usr"
sys.executable = os.path.abspath(sys.argv[0])
sys.argv = _argv
exec(compile(_code, "<string>" if _argv[0] in ("-c", "-") else _argv[0], "exec"),
     {"__name__": "__main__", "__builtins__": __builtins__})
'''


def python3_stub(version: str = FIXTURE_PYTHON_VERSION, *, venv: bool = False,
                 imports_ok: bool = True, log=None) -> str:
    """An executable ``python3`` stand-in reporting ``version`` (``X.Y.Z``) — the shared
    installer fixture's interpreter (CR-MDB-064 §S7).

    It answers the way a real interpreter does, whatever the caller asks: ``-V``/``--version``
    print ``Python <version>``; a program (``-c``, a script path, or ``-`` on stdin) runs on the
    test's own interpreter with ``sys.version_info``, ``sys.version``, ``sys.hexversion`` and
    ``sys.implementation.version`` reporting ``version``, ``sys.base_prefix`` ``/usr`` and
    ``sys.prefix`` ``/usr`` — or, with ``venv``, a virtual environment's prefix — and
    ``sys.executable`` its own path as invoked. An import-only program (the stack ``python``
    probe's module check) imports nothing and exits 0, or 1 without ``imports_ok``; ``-m``
    (``-m pip install …``) runs nothing and exits 0. ``log``, when given, gets one
    ``python3 <args>`` line per run, a newline in an argument written ``\\n``."""
    header = (
        f"#!{sys.executable}\n"
        f"_VERSION = {version!r}\n"
        f"_VENV = {bool(venv)!r}\n"
        f"_IMPORTS_OK = {bool(imports_ok)!r}\n"
        f"_LOG = {str(log) if log else None!r}\n"
    )
    return header + _PYTHON3_STUB_BODY


def uv_stub(found=None, body: str = DEFAULT_UV_BODY, *, log=None) -> str:
    """An executable ``uv`` stand-in (CR-MDB-064 §S7). ``uv python find`` called with both
    ``--system`` and ``>=3.14`` prints ``found`` and exits 0; with ``found`` ``None``, or without
    either argument, it reports no interpreter and exits 2, as uv does. Every other invocation
    runs ``body`` (a ``/bin/sh`` script; its shebang line is dropped). ``log``, when given, gets
    the arguments of every ``python find`` call, one line each."""
    lines = ["#!/bin/sh", 'if [ "$1" = "python" ] && [ "$2" = "find" ]; then']
    if log:
        lines.append(f"    printf '%s\\n' \"$*\" >> {shlex.quote(str(log))}")
    lines += [
        "    system=; floor=",
        '    for arg in "$@"; do',
        '        case "$arg" in',
        "            --system) system=1 ;;",
        "            '>=3.14') floor=1 ;;",
        "        esac",
        "    done",
    ]
    if found is not None:
        lines.append('    if [ -n "$system" ] && [ -n "$floor" ]; then '
                     f"printf '%s\\n' {shlex.quote(str(found))}; exit 0; fi")
    lines += [
        "    echo 'error: No interpreter found for Python >=3.14 in virtual environments, "
        "managed installations, or search path' >&2",
        "    exit 2",
        "fi",
    ]
    rest = body.split("\n", 1)[1] if body.startswith("#!") else body
    return "\n".join(lines) + "\n" + rest


#: ``write_interpreter_fixture``'s default for ``uv_found``: the ``python3`` it wrote.
FIXTURE_PYTHON3 = object()


def write_interpreter_fixture(bin_dir, *, version: str = FIXTURE_PYTHON_VERSION,
                              venv: bool = False, imports_ok: bool = True,
                              python3: bool = True, uv_found=FIXTURE_PYTHON3,
                              uv_body: str = DEFAULT_UV_BODY, uv_log=None,
                              python3_log=None):
    """The shared installer fixture (CR-MDB-064 §S7): writes ``bin_dir/python3`` — a
    :func:`python3_stub` reporting ``version`` (the floor, 3.14, by default), not a virtual
    environment unless ``venv`` — and ``bin_dir/uv`` — a :func:`uv_stub` answering
    ``uv python find --system '>=3.14'`` with ``uv_found`` (by default that ``python3``'s path;
    ``None`` finds none) and running ``uv_body`` for everything else. ``python3=False`` writes
    no ``python3``. Returns the ``python3`` path, or ``None``."""
    bin_dir = Path(bin_dir)
    python3_path = None
    if python3:
        python3_path = write_executable(bin_dir, "python3", python3_stub(
            version, venv=venv, imports_ok=imports_ok, log=python3_log))
    if uv_found is FIXTURE_PYTHON3:
        uv_found = python3_path
    write_executable(bin_dir, "uv", uv_stub(uv_found, uv_body, log=uv_log))
    return python3_path


# ------------------------------------------------------------------ source scans ----

def docstring_nodes(tree: ast.AST) -> set[int]:
    """``id()`` of every docstring constant (module, function, class) in ``tree``."""
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


def code_string_literals(source: str) -> list[str]:
    """Every string constant in ``source`` except docstrings."""
    tree = ast.parse(source)
    skip = docstring_nodes(tree)
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in skip]


def rel_to_repo(path) -> str:
    """``path`` relative to the repo root, or ``path`` itself when it lies outside."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:  # pragma: no cover - defensive
        return str(path)


def requirements_rows():
    """The \u00a7S1 declarative structure: ``modelb_axi.requirements.REQUIREMENTS``,
    a sequence of plain-dict rows keyed by the \u00a7S1 field names."""
    from modelb_axi.requirements import REQUIREMENTS
    return list(REQUIREMENTS)


# ------------------------------------------------------------------ register flag ----

#: The register flag Crucible retired fleet-wide in their 0.1.0 clean break (no alias).
RETIRED_REGISTER_FLAG = "--phase"

#: CR-MDB-023: ``--phase`` is ALSO the live flag of ``rust-code-health.py snapshot`` (a Model B
#: tool, not a Crucible client). Only that exact occurrence is stripped before the retired-flag
#: check; every other ``--phase`` still bites.
RUST_SNAPSHOT_PHASE_RE = re.compile(r"rust-code-health\.py\s+snapshot\s+--phase\b")


def carries_retired_register_flag(line):
    """True when `line` carries the retired register flag once the
    `rust-code-health.py snapshot --phase` occurrences are removed
    (CR-MDB-023) -- the guard's intent is otherwise unchanged."""
    return RETIRED_REGISTER_FLAG in RUST_SNAPSHOT_PHASE_RE.sub("", line)



def at_line(path: str, line: int) -> str:
    """``path``, a colon, then ``line`` — the location form a checker reports a finding under.

    Assembled at run time, so a test expecting a checker's located finding never carries a
    path-and-line citation in its own source (CR-MDB-044 §S4: code is cited by symbol)."""
    return ":".join((path, str(line)))
