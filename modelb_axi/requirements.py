"""Every requirement a deployed Model B asset has, declared once
(CR-MDB-036 §S1).

:data:`REQUIREMENTS` is data, read by the installer's pre-flight
(``modelb_axi.preflight``) and — from §S6 — the scaffold. Adding a
requirement touches only this structure and its test. Each row is a plain
dict with the §S1 fields:

``id``              the requirement id (the ``[capabilities]`` key)
``tier``            1 = harness capability, 2 = ecosystem dependency,
                    3 = per-stack toolchain
``provider``        what supplies it (an npm package for tier 1)
``policy``          ``required`` (missing fails the pre-flight, §S3) or
                    ``recommended`` (missing WARNs and continues)
``scope``           ``"always"``, or the tuple of stacks that need it
``probe``           how the pre-flight judges it: ``pi-package`` (Pi's
                    settings + node_modules), ``bootstrap`` (``uv``),
                    ``deps`` (Sandesh), ``crucible-manifest``,
                    ``interpreter`` (the Python floor, CR-MDB-064 §S2),
                    ``toolchain`` (§S8), or ``path`` — a tier-2 tool
                    resolved by ``shutil.which`` and recorded in
                    ``[capabilities]``; a new ``path`` row needs no code
``asset_families``  the deployed asset families that are inert without it
``remediation``     what the user runs to provide it
``tools``           tier 1 only: the tool names the provider supplies
                    (CR-MDB-020 §S5 checks skills against these)
``absent_effect``   optional, ``path`` rows: what stops working when the
                    tool is absent, appended to its absent-warning
                    (CR-MDB-047 §S1)

Stdlib only; no imports, no I/O.
"""

#: Stack -> key of Crucible's released-client manifest ``clients`` object
#: (§S1 amendment): the stack name, except quarkus and java share ``mvn``.
STACK_CLIENT_KEYS: dict[str, str] = {
    "arduino": "arduino",
    "bun": "bun",
    "python": "python",
    "quarkus": "mvn",
    "rust": "rust",
    "java": "mvn",
}

_ALL_STACKS: tuple[str, ...] = tuple(STACK_CLIENT_KEYS)

#: Crucible's released-client manifest, relative to ``$HOME`` — at the
#: install ROOT, not under ``clients/`` (§S1 amendment, measured 2026-09-24).
CRUCIBLE_MANIFEST_RELPATH = ".crucible/crucible-clients.json"

#: Tools ``pi-lean-ctx`` registers (measured on this machine's Pi).
_LEAN_CTX_TOOLS: tuple[str, ...] = (
    "lean_ctx",
    "ctx_call", "ctx_callgraph", "ctx_compose", "ctx_delta", "ctx_edit",
    "ctx_execute", "ctx_expand", "ctx_explore", "ctx_find", "ctx_glob",
    "ctx_graph", "ctx_grep", "ctx_knowledge", "ctx_ls", "ctx_overview",
    "ctx_patch", "ctx_read", "ctx_search", "ctx_session", "ctx_shell",
    "ctx_tree", "ctx_url_read",
)

REQUIREMENTS: tuple[dict, ...] = (
    {
        "id": "dispatch",
        "tier": 1,
        "provider": "@gotgenes/pi-subagents",
        "policy": "required",
        "scope": "always",
        "probe": "pi-package",
        "asset_families": ("agent definitions", "orchestration skills"),
        "remediation": "pi install npm:@gotgenes/pi-subagents",
        "tools": ("subagent", "get_subagent_result", "steer_subagent"),
    },
    {
        "id": "lean-ctx",
        "tier": 1,
        "provider": "pi-lean-ctx",
        "policy": "required",
        "scope": "always",
        "probe": "pi-package",
        "asset_families": ("agent definitions", "tool scripts"),
        "remediation": "pi install npm:pi-lean-ctx",
        "tools": _LEAN_CTX_TOOLS,
    },
    {
        "id": "permissions",
        "tier": 1,
        "provider": "@gotgenes/pi-permission-system",
        "policy": "recommended",
        "scope": "always",
        "probe": "pi-package",
        "asset_families": ("agent definitions' permission: frontmatter",),
        "remediation": "pi install npm:@gotgenes/pi-permission-system",
        "tools": (),
    },
    {
        # CR-MDB-029 §S3: Model B's own Pi package — worktree isolation
        # (CR-MDB-039 §S3). Offered (and run under ``--yes``) by the
        # installer. The ``watcher`` row until CR-MDB-047 §S1, when Sandesh's
        # own Pi extension became the wake path.
        "id": "worktree",
        "tier": 1,
        "provider": "@anthill-tec/modelb-pi",
        "policy": "recommended",
        "scope": "always",
        "probe": "pi-package",
        "asset_families": ("orchestration skills", "worktree isolation"),
        "remediation": "pi install npm:@anthill-tec/modelb-pi",
        "tools": ("modelb_worktree_enter", "modelb_worktree_exit"),
    },
    {
        # CR-MDB-045 §S1: Sandesh's own Pi extension — a third-party
        # package, so ``--yes`` never installs it; its remediation is named.
        # The wake path, so required since CR-MDB-047 §S1.
        "id": "sandesh-pi",
        "tier": 1,
        "provider": "@anthill-tec/sandesh-pi",
        "policy": "required",
        "scope": "always",
        "probe": "pi-package",
        "asset_families": ("bootstrap and shutdown skills",),
        "remediation": "pi install npm:@anthill-tec/sandesh-pi",
        # CR-MDB-077 §S1: the tools sandesh-pi 0.4.3 registers.
        "tools": (
            "sandesh_setup", "sandesh_register", "sandesh_unregister",
            "sandesh_send", "sandesh_reply",
            "sandesh_addressbook", "sandesh_fetch", "sandesh_inbox", "sandesh_thread",
            "sandesh_search", "sandesh_status",
            "sandesh_notify_start", "sandesh_notify_stop", "sandesh_notify_status",
            "sandesh_archive", "sandesh_unarchive",
        ),
    },
    {
        "id": "uv",
        "tier": 2,
        "provider": "uv",
        "policy": "required",
        "scope": "always",
        "probe": "bootstrap",
        "asset_families": ("the modelb-axi installer", "Sandesh install"),
        "remediation": "curl -LsSf https://astral.sh/uv/install.sh | sh",
    },
    {
        "id": "sandesh",
        "tier": 2,
        "provider": "sandesh-relay (via uv tool install)",
        # CR-MDB-047 §S1: required — sandesh-pi refuses a missing or
        # outdated CLI; the pre-flight fails without it.
        "policy": "required",
        "scope": "always",
        "probe": "deps",
        "asset_families": ("bootstrap and shutdown skills",),
        "remediation": "uv tool install sandesh-relay",
    },
    {
        "id": "crucible",
        "tier": 2,
        "provider": f"Crucible's released clients: ~/{CRUCIBLE_MANIFEST_RELPATH}",
        "policy": "recommended",
        "scope": "always",
        "probe": "crucible-manifest",
        "asset_families": ("crucible skills", "crucible-report-* skill bundles"),
        "remediation": "install Crucible's released clients with Crucible's own installer",
    },
    {
        "id": "crucible-client",
        "tier": 2,
        "provider": "the manifest's clients[<key>]: <key>-crucible.py",
        "policy": "recommended",
        "scope": _ALL_STACKS,
        "probe": "crucible-manifest",
        "asset_families": ("crucible-report-<stack> skill bundle",),
        "remediation": "install Crucible's released clients with Crucible's own installer",
    },
    {
        # CR-MDB-064 §S2: the interpreter the deployed scripts run on —
        # required, found by its own ``interpreter`` probe (``python3`` on
        # PATH, else the one uv reports) and recorded as ``[install] python``.
        "id": "python3",
        "tier": 2,
        "provider": "the OS",
        "policy": "required",
        "scope": "always",
        "probe": "interpreter",
        "asset_families": ("tool scripts", "hook scripts"),
        "remediation": "uv python install 3.14",
    },
    {
        "id": "bash",
        "tier": 2,
        "provider": "the OS",
        "policy": "recommended",
        "scope": "always",
        "probe": "path",
        "asset_families": ("tool scripts (gate-lock.sh)",),
        "remediation": "install bash with the OS package manager",
    },
    {
        "id": "gh",
        "tier": 2,
        "provider": "the GitHub CLI project",
        "policy": "recommended",
        "scope": "always",
        "probe": "path",
        "asset_families": ("git-workflow skill",),
        "remediation": "install gh from https://cli.github.com",
    },
    {
        "id": "jq",
        "tier": 2,
        "provider": "the jq project",
        "policy": "recommended",
        "scope": "always",
        "probe": "path",
        "asset_families": ("tool scripts",),
        "remediation": "install jq with the OS package manager",
    },
    {
        # CR-MDB-047 §S1: direnv loads a project's ``.env`` into the
        # environment through the ``.envrc`` ``init`` writes. Only the binary
        # is probed, never the shell hook.
        "id": "direnv",
        "tier": 2,
        "provider": "the direnv project",
        "policy": "recommended",
        "scope": "always",
        "probe": "path",
        "asset_families": ("the project .envrc",),
        "absent_effect": (
            "the project's .env, including its wake identity, is not loaded into "
            "the environment"
        ),
        "remediation": (
            "install direnv with the OS package manager and hook it into the shell: "
            'direnv hook fish | source (fish), or eval "$(direnv hook bash)" (bash)'
        ),
    },
    {
        "id": "toolchain",
        "tier": 3,
        "provider": "each stack's own toolchain provider",
        "policy": "recommended",
        "scope": _ALL_STACKS,
        "probe": "toolchain",
        "asset_families": ("crucible-report-<stack> skill bundle", "agent definitions"),
        "remediation": (
            "install the stack's toolchain with its provider's own installer "
            "(rustup, bun's installer, arduino-cli's installer, a JDK/Maven source)"
        ),
    },
)


# ---------------------------------------------------------------------------
# §S8 — the tier-3 ``toolchain`` row, per stack
# ---------------------------------------------------------------------------

_RUSTUP_INSTALLER = "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
_BUN_INSTALLER = "curl -fsSL https://bun.sh/install | bash"
_ARDUINO_CLI_INSTALLER = (
    "curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh"
)
#: CR-MDB-063 §S2: the project ``.venv`` route for the Crucible python
#: client's modules (``xmlrunner`` ships in ``unittest-xml-reporting``),
#: declared once, in order — the module probes' remediation and ``init``'s
#: Setup task are built from it. It runs in each python project, so it is
#: never offered.
PYTHON_VENV_ROUTE: tuple[str, ...] = (
    "uv venv --python 3.14",
    "uv pip install unittest-xml-reporting coverage",
)
_VENV_ROUTE_HOW = (
    "a python project's tests run under its own .venv: in the project, run "
    + ", then ".join(f"`{command}`" for command in PYTHON_VENV_ROUTE)
)
#: CR-MDB-063 §S1: uv's ``--default`` install is what puts a ``python3``
#: on PATH, in uv's executable directory.
_PYTHON3_INSTALL: tuple[str, ...] = ("uv", "python", "install", "--default", "3.14")
_PYTHON3_EXPECTED = (
    "in uv's executable directory (~/.local/bin, unless UV_PYTHON_BIN_DIR or "
    "XDG_BIN_HOME names another), which must be on PATH"
)
#: CR-MDB-063 §S2: why a probe has no install argv, its ``no_install``.
ELEVATED = "elevated"
PER_PROJECT = "per-project"
_CARGO_BIN = "in ~/.cargo/bin, which must be on PATH"
_LOCAL_BIN = "~/.local/bin"


def install_display(install: tuple[str, ...]) -> str:
    """How a provider installer argv reads as a command: an ``sh -c``
    pipeline is its script; any other argv is joined."""
    return install[-1] if install[:2] == ("sh", "-c") else " ".join(install)


def _probe(
    name: str, how: str, install: tuple[str, ...] | None, kind: str = "binary",
    *, expected: str | None = None, env_dirs: dict[str, str] | None = None,
    no_install: str | None = None,
) -> dict:
    """One toolchain probe. Its ``remediation`` is ``how`` \u2014 prose \u2014 and,
    when the provider's installer can be run, that command set apart in
    backticks: ``<how>: `<command>` `` (the command never carries prose).
    ``expected`` names where a re-probe looks for the tool after its
    installer ran; ``env_dirs`` are environment variables the installer is
    run with, each naming a directory (``~`` expanded) created if missing.
    A probe without ``install`` declares why as ``no_install``
    (CR-MDB-063 §S2): :data:`ELEVATED` or :data:`PER_PROJECT`."""
    if (install is None) != (no_install in (ELEVATED, PER_PROJECT)):
        raise ValueError(f"probe {name!r}: needs exactly one of install or a no_install reason")
    remediation = f"{how}: `{install_display(install)}`" if install else how
    if expected is None:
        expected = "importable by the PATH python3" if kind == "module" else "on PATH"
    return {
        "name": name, "kind": kind, "remediation": remediation, "install": install,
        "no_install": no_install, "expected": expected, "env_dirs": dict(env_dirs or {}),
    }


#: CR-MDB-063 §S1: the ``python3`` PATH probe every stack's group leads with.
_PYTHON3_PROBE = _probe("python3", "put python3 on PATH with uv", _PYTHON3_INSTALL,
                        expected=_PYTHON3_EXPECTED)

_JVM_PROBES: tuple[dict, ...] = (
    _PYTHON3_PROBE,
    _probe("mvn", "install Maven from a JDK/Maven source (a distro package or "
                  "https://maven.apache.org)", None, no_install=ELEVATED),
    _probe("java", "install a JDK from a JDK/Maven source (a distro package or "
                   "https://adoptium.net)", None, no_install=ELEVATED),
)

#: Stack -> its toolchain probes, in §S8 table order. ``kind`` is
#: ``binary`` (resolved by ``shutil.which``, never executed) or ``module``
#: (imported by the PATH ``python3``). Every stack's group begins with the
#: ``python3`` PATH probe (CR-MDB-063 §S1): each stack's Crucible client is a
#: python script run as ``python3 <client>``. ``remediation`` is always
#: named; ``install`` is the provider's own installer as an argv — offered
#: only on an explicit interactive yes, its ``[0]`` resolved on PATH first —
#: or ``None``, and then ``no_install`` states why (CR-MDB-063 §S2):
#: ``elevated`` — it needs elevated privileges, so it is named, never run
#: (``mvn``, ``java``, ``node``, ``g++``) — or ``per-project`` — its route
#: runs in each project, :data:`PYTHON_VENV_ROUTE` (``xmlrunner``,
#: ``coverage``). ``remediation`` states the remediation only (the scaffold
#: writes it into AGENTS.md); what the installer does about it is the
#: installer's wording, not data.
STACK_TOOLCHAINS: dict[str, tuple[dict, ...]] = {
    "python": (
        _PYTHON3_PROBE,
        _probe("xmlrunner", _VENV_ROUTE_HOW, None, kind="module", no_install=PER_PROJECT),
        _probe("coverage", _VENV_ROUTE_HOW, None, kind="module", no_install=PER_PROJECT),
    ),
    "rust": (
        _PYTHON3_PROBE,
        _probe("cargo", "install Rust with rustup", ("sh", "-c", _RUSTUP_INSTALLER),
               expected=_CARGO_BIN),
        _probe("cargo-nextest", "install it with cargo",
               ("cargo", "install", "cargo-nextest"), expected=_CARGO_BIN),
        _probe("cargo-llvm-cov", "install it with cargo",
               ("cargo", "install", "cargo-llvm-cov"), expected=_CARGO_BIN),
    ),
    "quarkus": _JVM_PROBES,
    "java": _JVM_PROBES,
    "bun": (
        _PYTHON3_PROBE,
        _probe("bun", "install bun with bun's installer", ("sh", "-c", _BUN_INSTALLER),
               expected="in ~/.bun/bin, which must be on PATH"),
        _probe("node", "install Node.js from https://nodejs.org or the OS package "
                       "manager", None, no_install=ELEVATED),
    ),
    "arduino": (
        _PYTHON3_PROBE,
        # The installer drops the binary in $BINDIR (default ./bin, the
        # cwd): pin it to ~/.local/bin (finding 2).
        _probe("arduino-cli", "install arduino-cli with its installer",
               ("sh", "-c", _ARDUINO_CLI_INSTALLER),
               expected="in ~/.local/bin (the installer's BINDIR), which must be on PATH",
               env_dirs={"BINDIR": _LOCAL_BIN}),
        _probe("g++", "install g++ with the OS package manager", None, no_install=ELEVATED),
    ),
}


def requirement(requirement_id: str) -> dict:

    """The one row with ``requirement_id``; ``KeyError`` when undeclared."""
    for row in REQUIREMENTS:
        if row["id"] == requirement_id:
            return row
    raise KeyError(f"no requirement declared with id {requirement_id!r}")
