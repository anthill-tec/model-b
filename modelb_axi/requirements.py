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
                    ``toolchain`` (§S8), or ``path`` — a tier-2 tool
                    resolved by ``shutil.which`` and recorded in
                    ``[capabilities]``; a new ``path`` row needs no code
``asset_families``  the deployed asset families that are inert without it
``remediation``     what the user runs to provide it
``tools``           tier 1 only: the tool names the provider supplies
                    (CR-MDB-020 §S5 checks skills against these)

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
        # CR-MDB-029 §S3: Model B's own Pi package — the Sandesh watcher
        # supervisor. Offered (and run under ``--yes``) by the installer.
        "id": "watcher",
        "tier": 1,
        "provider": "@anthill-tec/modelb-pi",
        "policy": "recommended",
        "scope": "always",
        "probe": "pi-package",
        "asset_families": ("orchestration skills",),
        "remediation": "pi install npm:@anthill-tec/modelb-pi",
        "tools": ("sandesh_watcher",),
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
        "policy": "recommended",
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
        "id": "python3",
        "tier": 2,
        "provider": "the OS",
        "policy": "recommended",
        "scope": "always",
        "probe": "path",
        "asset_families": ("tool scripts", "hook scripts"),
        "remediation": "install python3 with the OS package manager",
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
#: The Crucible python client's modules; ``xmlrunner`` ships in the
#: ``unittest-xml-reporting`` package (orchestrator ruling, C2).
_PIP_INSTALL = "python3 -m pip install unittest-xml-reporting coverage"
_PIP_HOW = "install the Crucible python client's modules with pip"
_CARGO_BIN = "in ~/.cargo/bin, which must be on PATH"
_LOCAL_BIN = "~/.local/bin"


def install_display(install: tuple[str, ...]) -> str:
    """How a provider installer argv reads as a command: an ``sh -c``
    pipeline is its script; any other argv is joined."""
    return install[-1] if install[:2] == ("sh", "-c") else " ".join(install)


def _probe(
    name: str, how: str, install: tuple[str, ...] | None, kind: str = "binary",
    *, expected: str | None = None, env_dirs: dict[str, str] | None = None,
) -> dict:
    """One toolchain probe. Its ``remediation`` is ``how`` \u2014 prose \u2014 and,
    when the provider's installer can be run, that command set apart in
    backticks: ``<how>: `<command>` `` (the command never carries prose).
    ``expected`` names where a re-probe looks for the tool after its
    installer ran; ``env_dirs`` are environment variables the installer is
    run with, each naming a directory (``~`` expanded) created if missing."""
    remediation = f"{how}: `{install_display(install)}`" if install else how
    if expected is None:
        expected = "importable by the PATH python3" if kind == "module" else "on PATH"
    return {
        "name": name, "kind": kind, "remediation": remediation, "install": install,
        "expected": expected, "env_dirs": dict(env_dirs or {}),
    }


_JVM_PROBES: tuple[dict, ...] = (
    _probe("mvn", "install Maven from a JDK/Maven source (a distro package or "
                  "https://maven.apache.org)", None),
    _probe("java", "install a JDK from a JDK/Maven source (a distro package or "
                   "https://adoptium.net)", None),
)

#: Stack -> its toolchain probes, in §S8 table order. ``kind`` is
#: ``binary`` (resolved by ``shutil.which``, never executed) or ``module``
#: (imported by the PATH ``python3``). ``remediation`` is always named;
#: ``install`` is the provider's own installer as an argv — offered only on
#: an explicit interactive yes, its ``[0]`` resolved on PATH first — or
#: ``None`` when it needs elevated privileges. ``remediation`` states the
#: remediation only (the scaffold writes it into AGENTS.md); what the
#: installer does about it is the installer's wording, not data.
STACK_TOOLCHAINS: dict[str, tuple[dict, ...]] = {
    "python": (
        _probe("python3", "install python3 with the OS package manager", None),
        _probe("xmlrunner", _PIP_HOW, tuple(_PIP_INSTALL.split()), kind="module"),
        _probe("coverage", _PIP_HOW, tuple(_PIP_INSTALL.split()), kind="module"),
    ),
    "rust": (
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
        _probe("bun", "install bun with bun's installer", ("sh", "-c", _BUN_INSTALLER),
               expected="in ~/.bun/bin, which must be on PATH"),
        _probe("node", "install Node.js from https://nodejs.org or the OS package "
                       "manager", None),
    ),
    "arduino": (
        # The installer drops the binary in $BINDIR (default ./bin, the
        # cwd): pin it to ~/.local/bin (finding 2).
        _probe("arduino-cli", "install arduino-cli with its installer",
               ("sh", "-c", _ARDUINO_CLI_INSTALLER),
               expected="in ~/.local/bin (the installer's BINDIR), which must be on PATH",
               env_dirs={"BINDIR": _LOCAL_BIN}),
        _probe("g++", "install g++ with the OS package manager", None),
    ),
}


def requirement(requirement_id: str) -> dict:

    """The one row with ``requirement_id``; ``KeyError`` when undeclared."""
    for row in REQUIREMENTS:
        if row["id"] == requirement_id:
            return row
    raise KeyError(f"no requirement declared with id {requirement_id!r}")
