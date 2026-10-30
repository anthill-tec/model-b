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
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from tests.pi_capability_sandbox import with_agent_dir

REPO_ROOT = Path(__file__).resolve().parent.parent

#: How every skip reason spells the manifest, so a reader can find it on any machine.
CRUCIBLE_MANIFEST_SPELLING = "~/.crucible/crucible-clients.json"

#: CR-MDB-060 §S1.1 — each stack's orchestrator notes: the stack-skill reference each memory
#: template became (moved with ``git mv``, its headings unchanged), relative to the repository.
ORCHESTRATION_REFERENCES = {
    "arduino": "generator/skills/arduino-stack/references/orchestration.md",
    "java": "generator/skills/java-stack/references/orchestration.md",
    "rust": "generator/skills/rust-stack/references/orchestration.md",
}
#: CR-MDB-060 §S1.1 — the file-move map: each retired memory template -> its reference.
ORCHESTRATION_TEMPLATE_MOVES = {
    f"skills-src/memory-templates/{stack}-orchestration.md": reference
    for stack, reference in ORCHESTRATION_REFERENCES.items()
}

#: The generator's stack files and agent templates, as ``rendered_definition`` reads them.
GENERATOR_STACKS_DIR = REPO_ROOT / "generator" / "stacks"
GENERATOR_TEMPLATES_DIR = REPO_ROOT / "generator" / "templates"


def rendered_definition(stack: str, role: str) -> str:
    """One definition rendered in memory from today's stack file and templates."""
    from modelb_axi import agents

    return agents.render(
        stack, role, agents.load_stack_params(GENERATOR_STACKS_DIR, stack), GENERATOR_TEMPLATES_DIR
    )


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


def unchanged_text(text: str) -> str:
    """``text`` itself, unchanged -- the identity used where a text transform is expected: the
    whole file as a rule's region, or a rule unit kept raw (unnormalised)."""
    return text


def sha256_text(text: str) -> str:
    """The hex sha256 of ``text`` encoded as UTF-8 -- computed test-side, never through
    production's own hashing helper."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    """The hex sha256 of the raw ``data`` -- computed test-side, never through production's own
    hashing helper. Distinct from :func:`sha256_text`, which encodes a ``str`` first."""
    return hashlib.sha256(data).hexdigest()

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


# MIGRATED at CR-MDB-093 (§S4): from tests/test_agent_definition_rules.py, unchanged; shared with
# tests/test_suite_hygiene.py and tests/test_stack_reference_material.py.
def retired_phrases(text: str, phrases: tuple[str, ...]) -> list[str]:
    """Each of ``phrases`` that ``text`` says anywhere, headings included: case-insensitive, as
    whole words, with ``**`` and backticks dropped and whitespace (line breaks too) collapsed."""
    plain = re.sub(r"\s+", " ", text.replace("**", "").replace("`", ""))
    return [phrase for phrase in phrases
            if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", plain, re.IGNORECASE)]


# MIGRATED at CR-MDB-079 (§S8.2): from tests/test_orchestrator_references.py, unchanged; shared with
# tests/test_stack_reference_material.py.
def provenance_header(text: str) -> str:
    """The leading ``#`` comment lines of a TOML file, joined."""
    lines = []
    for line in text.splitlines():
        if not line.startswith("#"):
            break
        lines.append(line)
    return "\n".join(lines)


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
    pointed at the sandbox (never the real home), and deploys every hook script there
    (:func:`deploy_hook_scripts`), as the installer does (CR-MDB-062 §S8)."""
    harnesses_toml = ", ".join(f'"{h}"' for h in harnesses)
    hooks_scripts_dir = deploy_hook_scripts(Path(home) / ".agents" / "hooks" / "scripts")
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

# ------------------------------------------------------------------ hook scripts ----

#: The repo's hook protocol scripts — the real scripts a hook test runs.
HOOK_SCRIPTS_DIR = REPO_ROOT / "hooks-src" / "scripts"

def deploy_hook_scripts(store) -> Path:
    """Copy every ``hooks-src/scripts/*`` into the sandbox store ``store`` (created if absent)
    with mode 0755 and return ``store`` — the deployed hook-script store an install fixture's
    ``hooks_scripts_dir`` names, so an ``init`` driven against it finds every script it would
    wire as an executable file (CR-MDB-062 §S7/§S8). Test infrastructure: the real store is
    the installer's."""
    store = Path(store)
    store.mkdir(parents=True, exist_ok=True)
    for source in sorted(HOOK_SCRIPTS_DIR.iterdir()):
        if source.is_file():
            dest = store / source.name
            shutil.copyfile(source, dest)
            dest.chmod(0o755)
    return store


def run_hook(name: str, payload, *, cwd=None, timeout: int = 10) -> subprocess.CompletedProcess:
    """Run the REAL hook script ``hooks-src/scripts/<name>`` on the test's own interpreter with
    ``payload`` on stdin: a mapping or a list is sent as JSON, a ``str`` as written (so a test can
    send an unreadable payload). ``cwd`` is the script PROCESS's working directory, distinct from
    the payload's ``cwd`` field — a test pins it to prove a hook never falls back to its own."""
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPTS_DIR / name)], input=data, capture_output=True,
        text=True, timeout=timeout, cwd=cwd,
    )


def load_hook_module(name: str):
    """Load the REAL hook script ``hooks-src/scripts/<name>`` in process, as a fresh module, through
    ``importlib.machinery.SourceFileLoader`` (the file name has no ``.py``) with bytecode writing
    off for the load and restored after it, so no ``__pycache__`` lands under
    ``hooks-src/scripts/`` (CR-MDB-066 AC5). The module is not entered in ``sys.modules`` and its
    ``__name__`` is not ``"__main__"``, so loading runs no ``main``; each call is a new module, so
    no state a load leaves carries into the next."""
    path = HOOK_SCRIPTS_DIR / name
    loader = importlib.machinery.SourceFileLoader(f"modelb_hook_{name.replace('-', '_')}",
                                                  str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise ImportError(f"could not build a module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


def build_tree(root, files=(), *, git=None) -> Path:
    """Build a project tree at ``root`` and return it. Each relative path in ``files`` becomes a
    small file, its parents created; a path ending in ``/`` becomes an empty directory. ``git`` is
    the git entry at ``root``: ``"dir"`` a ``.git`` directory (a clone), ``"file"`` a ``.git``
    file ``gitdir: …`` (a worktree's or a submodule's), ``None`` none."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for rel in files:
        path = root / rel
        if rel.endswith("/"):
            path.mkdir(parents=True, exist_ok=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")
    if git == "dir":
        (root / ".git").mkdir(exist_ok=True)
    elif git == "file":
        (root / ".git").write_text("gitdir: ../.git/modules/fixture\n", encoding="utf-8")
    elif git is not None:
        raise ValueError(f"git must be 'dir', 'file' or None, not {git!r}")
    return root


def write_files(root, files) -> Path:
    """Write each ``{relative path: text}`` of ``files`` under ``root``, parents created, and
    return ``root`` -- the seam for a fixture tree whose files carry real content (a Cargo
    workspace's manifests and sources), where :func:`build_tree` writes placeholders."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root

# ------------------------------------------------------------------ tool-script runs ----
#
# CR-MDB-078 §S4: a deployed tool script (``scripts/*``) runs as a subprocess of the test
# interpreter with the test process's environment, only ``PATH`` and git's configuration
# variables changed (§S4.1), so coverage measures it; the external programs on its ``PATH`` are
# the test's choice (§S4.2); git never reads the host's global or system configuration (§S4.3).
# CR-MDB-081 §S9 adds the tools' own variables, each set or cleared by the test and never
# inherited from the session, and a private ``TMPDIR`` set in the test process.

#: The tool scripts' directory in this repository.
TOOL_SCRIPTS_DIR = REPO_ROOT / "scripts"

#: Git's configuration variables every fixture-repository git call and every tool run carries:
#: the host's global and system git configuration excluded (CR-MDB-078 §S4.3).
GIT_ISOLATION_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

#: The host programs a tool run's ``PATH`` links, and the only ones (CR-MDB-078 §S4.2).
TOOL_PATH_PROGRAMS = ("git", "tar")

#: The tool scripts' own environment variables (CR-MDB-081 §S9): a tool run never inherits one
#: from the session; a test that needs one passes it to :func:`run_tool` as ``env``.
TOOL_OWN_ENV = ("WORKTREE_FLOW_PROJECT_DIR", "WF_TRACK", "WF_REQUEST_DIR", "SKILLGATE_SOON")

#: The identity a fixture repository commits as, written to its own config (CR-MDB-078 §S4.3).
FIXTURE_GIT_IDENTITY = {"user.name": "Fixture", "user.email": "fixture@example.invalid"}


def cargo_member_manifest(name: str) -> str:
    """A Cargo manifest whose ``[package]`` table names ``name`` -- the manifest a synthetic
    workspace's member carries in the rust tool tests (CR-MDB-078 §S1/§S2)."""
    return f'[package]\nname = "{name}"\nversion = "0.1.0"\nedition = "2021"\n'


def tool_bin_dir(bin_dir, stand_ins=None) -> Path:
    """Build ``bin_dir`` as a tool run's whole ``PATH`` and return it: a link to the host's
    ``git`` and ``tar`` alone, plus each ``{name: body}`` of ``stand_ins`` written with
    :func:`write_executable` -- so ``cargo``, ``cargo-machete`` and ``dot`` are present only as a
    test's stand-in, never the host's (CR-MDB-078 §S4.2). A stand-in named ``git`` or ``tar``
    takes that program's place: no host link is made for it (CR-MDB-081 §S8, a logging ``git``)."""
    bin_dir = Path(bin_dir)
    bin_dir.mkdir(parents=True, exist_ok=True)
    for program in TOOL_PATH_PROGRAMS:
        if program in (stand_ins or {}):
            continue
        host = shutil.which(program)
        if host is None:
            raise RuntimeError(f"fixture: {program} is not on the host PATH")
        os.symlink(Path(host).resolve(), bin_dir / program)
    for name, body in (stand_ins or {}).items():
        write_executable(bin_dir, name, body)
    return bin_dir


def tool_env(bin_dir, env=None) -> dict:
    """The test process's environment with ``PATH`` set to ``bin_dir`` alone, git's
    configuration isolated (CR-MDB-078 §S4.1) and every :data:`TOOL_OWN_ENV` variable cleared --
    then each ``{name: value}`` of ``env`` set, the only way a tool's own variable reaches a run
    (CR-MDB-081 §S9). Nothing else changed: ``TMPDIR`` is the test process's own, made private
    with :func:`use_private_tmpdir`."""
    run_env = dict(os.environ)
    for name in TOOL_OWN_ENV:
        run_env.pop(name, None)
    run_env["PATH"] = str(bin_dir)
    run_env.update(GIT_ISOLATION_ENV)
    run_env.update(env or {})
    return run_env


def run_tool(script: str, *args, bin_dir, cwd, timeout: int = 60,
             env=None) -> subprocess.CompletedProcess:
    """Run ``scripts/<script>`` with ``args`` on the test's own interpreter, in ``cwd`` (a temp
    directory, never the repository -- CR-MDB-078 §S4.4), under :func:`tool_env` of ``bin_dir``
    and ``env``."""
    return subprocess.run(
        [sys.executable, str(TOOL_SCRIPTS_DIR / script), *map(str, args)],
        capture_output=True, text=True, timeout=timeout, cwd=str(cwd),
        env=tool_env(bin_dir, env), stdin=subprocess.DEVNULL,
    )


def use_private_tmpdir(test, work) -> Path:
    """Point ``TMPDIR`` at a fresh ``tmp`` directory inside the work area ``work`` for the rest
    of ``test`` (a ``unittest.TestCase``) and return it, so a tool's scratch files are made where
    no concurrent run on the host can disturb them, and go with the work area. It is set in the
    TEST PROCESS's environment, which each tool run inherits (CR-MDB-081 §S9; CR-MDB-078 §S4.1)."""
    from unittest import mock
    tmpdir = Path(work) / "tmp"
    tmpdir.mkdir()
    patcher = mock.patch.dict(os.environ, {"TMPDIR": str(tmpdir)})
    patcher.start()
    test.addCleanup(patcher.stop)
    return tmpdir


def repo_git(repo, *args) -> str:
    """Run ``git -C repo <args>`` with the host's global and system git configuration excluded
    and return its stripped stdout; a failure raises, naming the command and its stderr."""
    env = dict(os.environ)
    env.update(GIT_ISOLATION_ENV)
    result = subprocess.run(
        ["git", "-C", str(repo), *map(str, args)], capture_output=True, text=True,
        timeout=30, env=env, stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise AssertionError(f"fixture: git {' '.join(map(str, args))} failed: {result.stderr}")
    return result.stdout.strip()


def git_commit_all(repo, message: str) -> str:
    """Stage everything in the fixture repository ``repo``, commit it as ``message`` and return
    the new commit's full sha."""
    repo_git(repo, "add", "-A")
    repo_git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return repo_git(repo, "rev-parse", "HEAD")


def git_merge_no_ff(repo, branch: str, message: str) -> str:
    """Merge ``branch`` into the checked-out branch of ``repo`` as a ``--no-ff`` merge commit
    and return its full sha (CR-MDB-078 §S4.3)."""
    repo_git(repo, "merge", "-q", "--no-ff", "-m", message, branch)
    return repo_git(repo, "rev-parse", "HEAD")


def git_repo(root, files=None, *, branch: str = "main", message: str = "fixture") -> Path:
    """Build a real git repository at ``root`` and return it -- the one fixture-repository
    builder of CR-MDB-078 §S4.3 / AC16. Its identity and ``commit.gpgsign=false`` are written to
    the repository's own config, so a commit -- a tool's own included, under :func:`tool_env` --
    succeeds on a host with no global git identity. ``files`` (``{relative path: text}``), when
    given, are written and committed as ``message`` on ``branch``."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    repo_git(root, "init", "-q", "-b", branch)
    for key, value in {**FIXTURE_GIT_IDENTITY, "commit.gpgsign": "false"}.items():
        repo_git(root, "config", key, value)
    if files:
        write_files(root, files)
        git_commit_all(root, message)
    return root

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
_globals = {"__name__": "__main__", "__builtins__": __builtins__}
if _argv[0] not in ("-c", "-"):
    # A script runs as a real interpreter runs it: `__file__` is its path and its own
    # directory is `sys.path[0]` (a deployed tool imports a sibling from beside itself).
    _globals["__file__"] = _argv[0]
    sys.path[0] = os.path.dirname(os.path.abspath(_argv[0]))
exec(compile(_code, "<string>" if _argv[0] in ("-c", "-") else _argv[0], "exec"), _globals)
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


# ------------------------------------------------------------------ rendered scripts ----

#: The first line CR-MDB-064 §S3 renders into ``#!<recorded interpreter>``.
PYTHON_SHEBANG = b"#!/usr/bin/env python3"
#: Where the installer deploys the hook and the tool scripts, target-root-relative.
HOOKS_STORE = ".agents/hooks/scripts"
TOOLS_STORE = ".agents/scripts"


def render_script(source: bytes, interpreter: str) -> bytes:
    """The bytes CR-MDB-064 §S3 deploys for a script whose source is ``source``: a first line
    ``#!/usr/bin/env python3`` becomes ``#!<interpreter>``; every other byte, and any other
    script, is the source's. Computed independently of the package's own rendering."""
    first, newline, rest = source.partition(b"\n")
    if first != PYTHON_SHEBANG:
        return source
    return b"#!" + interpreter.encode() + newline + rest


def deployed_scripts() -> dict[str, Path]:
    """Every hook and tool script the installer deploys: target-root-relative path -> its
    packaged source in this checkout (``hooks-src/scripts/*``, ``scripts/*``)."""
    scripts = {f"{HOOKS_STORE}/{p.name}": p
               for p in sorted((REPO_ROOT / "hooks-src" / "scripts").iterdir()) if p.is_file()}
    scripts.update({f"{TOOLS_STORE}/{p.name}": p
                    for p in sorted((REPO_ROOT / "scripts").iterdir()) if p.is_file()})
    return scripts


def python_shebang_scripts() -> dict[str, Path]:
    """The :func:`deployed_scripts` whose source's first line is the python shebang."""
    return {rel: src for rel, src in deployed_scripts().items()
            if src.read_bytes().partition(b"\n")[0] == PYTHON_SHEBANG}


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


# ------------------------------------------------------------- sandesh-pi tools ----

#: The tools sandesh-pi 0.4.3 registers, as CR-MDB-077's Context lists them: the
#: names its §S1 puts in the ``sandesh-pi`` row's ``tools``. Restated here, never read
#: from ``REQUIREMENTS``, so a test pinning them bites while the row is still empty.
SANDESH_PI_TOOLS: tuple[str, ...] = (
    "sandesh_setup", "sandesh_register", "sandesh_unregister",
    "sandesh_send", "sandesh_reply",
    "sandesh_addressbook", "sandesh_fetch", "sandesh_inbox", "sandesh_thread",
    "sandesh_search", "sandesh_status",
    "sandesh_notify_start", "sandesh_notify_stop", "sandesh_notify_status",
    "sandesh_archive", "sandesh_unarchive",
)
#: CR-MDB-077 §S2: the ask-set — the policy leaves these out of its allow-set,
#: whichever requirement row supplies them, so they resolve to ``"*": "ask"``.
SANDESH_ASK_TOOLS: tuple[str, ...] = ("sandesh_archive", "sandesh_unarchive")
#: CR-MDB-077 §S2: the Sandesh tools the policy allows — the sixteen minus the ask-set.
SANDESH_ALLOWED_TOOLS: tuple[str, ...] = tuple(
    t for t in SANDESH_PI_TOOLS if t not in SANDESH_ASK_TOOLS
)


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


# ------------------------------------------------------------------ changelog form ----

#: CR-MDB-058 §S1 — the two links the opening sentence of a Keep a Changelog 1.1.0 file carries.
CHANGELOG_URLS = ("https://keepachangelog.com/en/1.1.0/", "https://semver.org/spec/v2.0.0.html")
#: §S1 — the six Keep a Changelog group names.
CHANGELOG_GROUPS = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")
#: §S1 — the operator note, first in its section when present.
CHANGELOG_UPGRADING = "Upgrading"
CHANGELOG_UNRELEASED_HEADING = "## [Unreleased]"
_CHANGELOG_RELEASE_HEADING = re.compile(
    r"## \[(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\] - \d{4}-\d{2}-\d{2}")
#: A compare link at the foot, ``[label]: url`` — it ends the last section.
_CHANGELOG_LINK_DEFINITION = re.compile(r"\[[^\]]+\]: ")


def _changelog_sections(text: str) -> list[tuple[str, list[str]]]:
    """Every ``## `` heading with its lines, each section ending at the next ``## `` heading,
    the first compare link, or the end of the file."""
    sections = []
    current = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            current = (line, [])
            sections.append(current)
        elif _CHANGELOG_LINK_DEFINITION.match(line):
            current = None
        elif current is not None:
            current[1].append(line)
    return sections


def changelog_form_faults(text: str) -> list[str]:
    """The CR-MDB-058 §S1 form checker, shared by §S1 (Model B's own ``CHANGELOG.md``) and §S5
    (``init``'s skeleton). It checks, and only these:

    - the two URLs (:data:`CHANGELOG_URLS`);
    - ``## [Unreleased]`` as the first ``##`` heading;
    - every later ``##`` heading reading ``## [X.Y.Z] - YYYY-MM-DD``, versions descending;
    - group headings drawn only from :data:`CHANGELOG_GROUPS` and ``### Upgrading``, with
      ``### Upgrading`` first in its section when present, and none empty (no non-blank line
      before the next heading, the first compare link, or the end of the file).

    Returns one message per fault; ``[]`` is a file in form."""
    faults = [f"missing link {url}" for url in CHANGELOG_URLS if url not in text]
    sections = _changelog_sections(text)
    if not sections or sections[0][0] != CHANGELOG_UNRELEASED_HEADING:
        first = sections[0][0] if sections else None
        faults.append(f"first ## heading is not {CHANGELOG_UNRELEASED_HEADING!r}: {first!r}")
    previous = None
    for heading, _lines in sections[1:]:
        match = _CHANGELOG_RELEASE_HEADING.fullmatch(heading)
        if match is None:
            faults.append(f"release heading not in '## [X.Y.Z] - YYYY-MM-DD' form: {heading!r}")
            continue
        version = tuple(int(part) for part in match.groups())
        if previous is not None and version >= previous:
            faults.append(f"versions not descending: {heading!r} follows "
                          f"{'.'.join(map(str, previous))}")
        previous = version
    allowed = (*CHANGELOG_GROUPS, CHANGELOG_UPGRADING)
    for heading, lines in sections:
        groups = []
        for line in lines:
            if line.startswith("### "):
                groups.append([line[len("### "):].strip(), False])
            elif line.strip() and groups:
                groups[-1][1] = True
        names = [name for name, _entry in groups]
        for name, has_entry in groups:
            if name not in allowed:
                faults.append(f"unknown group heading '### {name}' under {heading!r}")
            if not has_entry:
                faults.append(f"empty group heading '### {name}' under {heading!r}")
        if CHANGELOG_UPGRADING in names and names[0] != CHANGELOG_UPGRADING:
            faults.append(f"'### {CHANGELOG_UPGRADING}' is not the first group under {heading!r}")
    return faults


# ------------------------------------------------------------------ GitHub workflow text ----
# A release workflow is read as TEXT, stdlib only (no YAML parser): CR-MDB-058 §S2 reads
# `create-release`, §S4 reads `publish-npm`; CR-MDB-067 §S2 reads `rehearse`, the job keys and the
# `on.push` triggers; CR-MDB-067 §S3 reads `ci.yml`'s top-level `name:` and `permissions:`, its
# job names and a step's `env:`; CR-MDB-070 §S7 adds a step's `id:` and step-level `if:` and the
# `release` event, and points the CI checks at `release.yml`. These readers understand the block layout the
# repository's `.github/workflows/*.yml` use — two-space jobs under `jobs:`, a `steps:`
# list of `- ` items, `run:` inline or as a `|` block — and nothing more.

def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def workflow_job(text: str, name: str) -> list[str]:
    """The lines of ``jobs.<name>``: from its key to the next two-space-indented key."""
    lines = text.splitlines()
    key = f"  {name}:"
    if key not in lines:
        raise AssertionError(f"the workflow has no jobs.{name}")
    start = lines.index(key)
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"  \S", lines[i])), len(lines))
    return lines[start:end]


def workflow_job_env(job: list[str]) -> dict:
    """The job's own ``env:`` scalars as a dict, read at the job's key indent only (never a
    step's ``env:``); ``{}`` when the job declares none (CR-MDB-071 §S3)."""
    base = _indent_of(job[0]) + 2
    for i, line in enumerate(job[1:], start=1):
        if line.strip() and _indent_of(line) == base and re.match(r"\s*env:\s*(?:#.*)?$", line):
            return _scalar_mapping(_nested_lines(job, i + 1, base))
    return {}


def workflow_job_working_directory(job: list[str]) -> str | None:
    """The job's ``defaults.run.working-directory``, or ``None`` when it declares none."""
    for i, line in enumerate(job):
        if line.strip() != "defaults:":
            continue
        base = _indent_of(line)
        for inner in job[i + 1:]:
            if inner.strip() and _indent_of(inner) <= base:
                break
            match = re.match(r"\s*working-directory:\s*(\S.*)$", inner)
            if match:
                return _unquote(match.group(1))
    return None


def _strip_comment(value: str) -> str:
    """A YAML scalar without its trailing `` # comment``: a quoted scalar ends at its closing
    quote, a plain one at the first ``#`` that follows whitespace (CR-MDB-067 §S6)."""
    value = value.strip()
    if value.startswith("#"):
        return ""
    if value[:1] in ("'", '"'):
        close = value.find(value[0], 1)
        if close != -1:
            return value[:close + 1]
        return value
    return re.split(r"\s+#", value, maxsplit=1)[0].rstrip()


def _scalar(value: str) -> str:
    """A one-line YAML scalar's value: its comment stripped, then its quotes."""
    return _unquote(_strip_comment(value))


def _nested_lines(lines: list[str], start: int, indent: int) -> list[str]:
    """The lines from ``start`` that sit deeper than ``indent`` (blank lines kept), up to the
    first non-blank line at ``indent`` or shallower."""
    out = []
    for line in lines[start:]:
        if line.strip() and _indent_of(line) <= indent:
            break
        out.append(line)
    return out


def _scalar_mapping(lines: list[str]) -> dict:
    """The ``key: scalar`` pairs at the shallowest indent of ``lines`` (comments skipped)."""
    keyed = [line for line in lines if line.strip() and not line.strip().startswith("#")]
    if not keyed:
        return {}
    indent = min(_indent_of(line) for line in keyed)
    out = {}
    for line in keyed:
        if _indent_of(line) != indent:
            continue
        match = re.match(r"\s*([\w.-]+):(?:\s+(.*?))?\s*$", line)
        if match:
            out[match.group(1)] = _scalar(match.group(2) or "")
    return out


def _workflow_step(item: list[str]) -> dict:
    """One ``- `` step item as ``{"name", "run", "working-directory", "uses", "with"}``; ``run``
    is the list of its command lines, dedented (``[]`` for a ``uses:`` step); ``uses`` is the
    action reference without its trailing comment (``None`` for a ``run`` step); ``with`` is the
    step's ``with:`` scalars as a dict (``{}`` when it has none) — CR-MDB-067 §S6; ``env`` is the
    step's own ``env:`` scalars as a dict, read the same way (``{}`` when it has none) —
    CR-MDB-067 §S3; ``id`` and ``if`` are the step's own ``id:`` and step-level ``if:``, read as
    :func:`workflow_job_key` reads a job's (a folded ``if:`` joined into one line), ``None`` when
    the step declares none — never a key nested under ``with:`` or ``env:`` (CR-MDB-070 §S7)."""
    first = item[0]
    at = _indent_of(first)
    lines = [first[:at] + "  " + first[at + 2:], *item[1:]]
    key_indent = at + 2
    step = {"name": None, "run": [], "working-directory": None, "uses": None, "with": {},
            "env": {}, "id": _key_at(lines, 0, key_indent, "id"),
            "if": _key_at(lines, 0, key_indent, "if")}
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or _indent_of(line) != key_indent:
            continue
        match = re.match(r"\s*([\w-]+):\s*(.*?)\s*$", line)
        if match is None:
            continue
        key, value = match.groups()
        if key in ("with", "env") and not _strip_comment(value):
            body = _nested_lines(lines, i, key_indent)
            i += len(body)
            step[key] = _scalar_mapping(body)
        elif key == "uses":
            step["uses"] = _scalar(value)
        elif key == "run" and value in ("|", "|-"):
            body = []
            while i < len(lines) and (not lines[i].strip() or _indent_of(lines[i]) > key_indent):
                body.append(lines[i])
                i += 1
            step["run"] = [ln for ln in textwrap.dedent("\n".join(body)).splitlines() if ln.strip()]
        elif key == "run":
            step["run"] = [value]
        elif key in ("name", "working-directory"):
            step[key] = _unquote(value)
    return step


def workflow_steps(job: list[str]) -> list[dict]:
    """The job's ``steps:`` in order, each as :func:`_workflow_step` reads it."""
    starts = [i for i, line in enumerate(job) if line.strip() == "steps:"]
    if len(starts) != 1:
        raise AssertionError(f"expected one steps: key in {job[0].strip()!r}; found {len(starts)}")
    base = _indent_of(job[starts[0]])
    items: list[list[str]] = []
    item_indent = None
    for line in job[starts[0] + 1:]:
        if line.strip() and _indent_of(line) <= base:
            break
        if line.lstrip().startswith("- ") and item_indent in (None, _indent_of(line)):
            item_indent = _indent_of(line)
            items.append([line])
        elif items:
            items[-1].append(line)
    return [_workflow_step(item) for item in items]


def workflow_job_key(job: list[str], key: str) -> str | None:
    """A job-level scalar key of ``job`` (``if``, ``runs-on``, ``environment`` …), read at the
    job's own key indent only, never a step's (CR-MDB-067 §S6). A plain scalar's continuation
    lines and a ``>``/``>-`` block fold into one space-joined line, a ``|``/``|-`` block keeps
    its newlines; the comment and the quotes go. ``""`` for a key whose value is a nested block
    (``defaults:``), ``None`` when the job declares no such key."""
    return _key_at(job, 1, _indent_of(job[0]) + 2, key)


def _key_at(lines: list[str], first: int, base: int, key: str) -> str | None:
    """``key``'s scalar among ``lines[first:]`` at indent ``base`` exactly, read as
    :func:`workflow_job_key` describes; ``None`` when no such key sits there."""
    for i in range(first, len(lines)):
        line = lines[i]
        if not line.strip() or _indent_of(line) != base:
            continue
        match = re.match(r"\s*([\w-]+):(?:\s+(.*?))?\s*$", line)
        if match is None or match.group(1) != key:
            continue
        value = _strip_comment(match.group(2) or "")
        body = [ln.strip() for ln in _nested_lines(lines, i + 1, base)]
        if value in ("|", "|-"):
            return "\n".join(ln for ln in body if ln)
        if value in (">", ">-"):
            return " ".join(ln for ln in body if ln)
        if not value:
            return ""
        return _unquote(" ".join([value, *(ln for ln in body if ln and not ln.startswith("#"))]))
    return None


def workflow_key(text: str, key: str) -> str | None:
    """A top-level scalar key of the workflow (``name`` …), read at column 0 only, never a
    job's or a step's key of the same name; read as :func:`workflow_job_key` reads a job's
    (CR-MDB-067 §S3)."""
    return _key_at(text.splitlines(), 0, 0, key)


def workflow_job_permissions(job: list[str]) -> dict | str | None:
    """The job's ``permissions:`` — a dict of scope to access for the mapping form, the string
    for the scalar form (``read-all``), ``None`` when the job declares none (CR-MDB-067 §S6)."""
    return _permissions_at(job, 1, _indent_of(job[0]) + 2)


def _permissions_at(lines: list[str], first: int, base: int) -> dict | str | None:
    """The ``permissions:`` among ``lines[first:]`` at indent ``base`` exactly, read as
    :func:`workflow_job_permissions` describes; ``None`` when none sits there."""
    for i in range(first, len(lines)):
        line = lines[i]
        if not line.strip() or _indent_of(line) != base:
            continue
        match = re.match(r"\s*permissions:(?:\s+(.*?))?\s*$", line)
        if match is None:
            continue
        value = _scalar(match.group(1) or "")
        if value:
            return value
        return _scalar_mapping(_nested_lines(lines, i + 1, base))
    return None


def workflow_permissions(text: str) -> dict | str | None:
    """The workflow-level ``permissions:`` (column 0), read as :func:`workflow_job_permissions`
    reads a job's; ``None`` when the workflow declares none, whatever its jobs declare
    (CR-MDB-067 §S3)."""
    return _permissions_at(text.splitlines(), 0, 0)


def workflow_job_names(text: str) -> list[str]:
    """The keys under the top-level ``jobs:``, in order (CR-MDB-067 §S3); a workflow with no
    ``jobs:`` raises."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if re.match(r"jobs:\s*(?:#.*)?$", line)),
                 None)
    if start is None:
        raise AssertionError("the workflow has no top-level jobs: key")
    keyed = [line for line in _nested_lines(lines, start + 1, 0)
             if line.strip() and not line.strip().startswith("#")]
    if not keyed:
        return []
    indent = min(_indent_of(line) for line in keyed)
    names = []
    for line in keyed:
        match = re.match(r"\s*([\w-]+):", line)
        if match and _indent_of(line) == indent:
            names.append(match.group(1))
    return names


def _flow_or_block_list(inline: str, nested: list[str]) -> list[str]:
    """A YAML sequence given inline as ``[a, "b"]`` (or one scalar), else as ``- `` lines."""
    inline = _strip_comment(inline)
    if inline.startswith("[") and inline.endswith("]"):
        return [_unquote(part) for part in inline[1:-1].split(",") if part.strip()]
    if inline:
        return [_unquote(inline)]
    return [_scalar(line.strip()[2:]) for line in nested if line.strip().startswith("- ")]


def workflow_push_triggers(text: str) -> dict:
    """The workflow's ``on:`` as ``{"tags", "branches", "pull_request", "workflow_dispatch",
    "release"}``: the ``on.push`` tag and branch patterns (lists, ``[]`` when absent), and whether
    the ``pull_request`` and ``workflow_dispatch`` events are present (CR-MDB-067 §S6); ``release``
    is the ``release`` event's ``types`` as a list (``[]`` for the event with no ``types``),
    ``None`` when the workflow has no ``release`` event (CR-MDB-070 §S7). Reads the block form and
    the flow form ``on: [push, …]``; a workflow with no ``on:`` raises."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines)
                  if re.match(r"""(?:on|"on"|'on'):(?:\s|$)""", line)), None)
    if start is None:
        raise AssertionError("the workflow has no top-level on: key")
    out = {"tags": [], "branches": [], "pull_request": False, "workflow_dispatch": False,
           "release": None}
    inline = _strip_comment(lines[start].split(":", 1)[1])
    if inline:
        events = _flow_or_block_list(inline, [])
        out["pull_request"] = "pull_request" in events
        out["workflow_dispatch"] = "workflow_dispatch" in events
        if "release" in events:
            out["release"] = []
        return out
    block = _nested_lines(lines, start + 1, 0)
    keyed = [line for line in block if line.strip() and not line.strip().startswith("#")]
    if not keyed:
        return out
    event_indent = min(_indent_of(line) for line in keyed)
    for i, line in enumerate(block):
        if not line.strip() or _indent_of(line) != event_indent:
            continue
        match = re.match(r"\s*([\w-]+):", line)
        if match is None:
            continue
        event = match.group(1)
        if event in ("pull_request", "workflow_dispatch"):
            out[event] = True
        if event not in ("push", "release"):
            continue
        if event == "release":
            out["release"] = []
        wanted = ("tags", "branches") if event == "push" else ("types",)
        filters = _nested_lines(block, i + 1, event_indent)
        keyed_filters = [ln for ln in filters if ln.strip() and not ln.strip().startswith("#")]
        if not keyed_filters:
            continue
        filter_indent = min(_indent_of(ln) for ln in keyed_filters)
        for j, inner in enumerate(filters):
            found = re.match(r"(\s*)([\w-]+):(.*)$", inner)
            if (found is None or _indent_of(inner) != filter_indent
                    or found.group(2) not in wanted):
                continue
            values = _flow_or_block_list(
                found.group(3), _nested_lines(filters, j + 1, filter_indent))
            out["release" if event == "release" else found.group(2)] = values
    return out


def _find_pi_package_root(pi_binary_resolved: Path) -> Path | None:
    """Walk up from the resolved `pi` binary looking for the un-bundled
    package root (needs `dist/core/extensions/loader.js` -- the compiled
    single-file `dist/bundle/cli.js` alone does not expose jiti loading).

    One copy, shared by `test_pi_hook_runtime` and `test_skill_frontmatter`
    (CR-MDB-065 §S3.2); each imports it under this name, so a skip test patches
    it on the importing module, where that module's resolver looks it up."""
    for parent in pi_binary_resolved.parents:
        if (parent / "dist" / "core" / "extensions" / "loader.js").is_file():
            return parent
    return None
