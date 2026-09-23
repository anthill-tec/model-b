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
        "asset_families": ("agent definitions' permission: frontmatter",),
        "remediation": "pi install npm:@gotgenes/pi-permission-system",
        "tools": (),
    },
    {
        "id": "uv",
        "tier": 2,
        "provider": "uv",
        "policy": "required",
        "scope": "always",
        "asset_families": ("the modelb-axi installer", "Sandesh install"),
        "remediation": "curl -LsSf https://astral.sh/uv/install.sh | sh",
    },
    {
        "id": "sandesh",
        "tier": 2,
        "provider": "sandesh-relay (via uv tool install)",
        "policy": "recommended",
        "scope": "always",
        "asset_families": ("bootstrap and shutdown skills",),
        "remediation": "uv tool install sandesh-relay",
    },
    {
        "id": "crucible",
        "tier": 2,
        "provider": f"Crucible's released clients: ~/{CRUCIBLE_MANIFEST_RELPATH}",
        "policy": "recommended",
        "scope": "always",
        "asset_families": ("crucible skills", "crucible-report-* skill bundles"),
        "remediation": "install Crucible's released clients with Crucible's own installer",
    },
    {
        "id": "crucible-client",
        "tier": 2,
        "provider": "the manifest's clients[<key>]: <key>-crucible.py",
        "policy": "recommended",
        "scope": _ALL_STACKS,
        "asset_families": ("crucible-report-<stack> skill bundle",),
        "remediation": "install Crucible's released clients with Crucible's own installer",
    },
    {
        "id": "python3",
        "tier": 2,
        "provider": "the OS",
        "policy": "recommended",
        "scope": "always",
        "asset_families": ("tool scripts", "hook scripts"),
        "remediation": "install python3 with the OS package manager",
    },
    {
        "id": "bash",
        "tier": 2,
        "provider": "the OS",
        "policy": "recommended",
        "scope": "always",
        "asset_families": ("tool scripts (gate-lock.sh)",),
        "remediation": "install bash with the OS package manager",
    },
    {
        "id": "gh",
        "tier": 2,
        "provider": "the GitHub CLI project",
        "policy": "recommended",
        "scope": "always",
        "asset_families": ("git-workflow skill",),
        "remediation": "install gh from https://cli.github.com",
    },
    {
        "id": "jq",
        "tier": 2,
        "provider": "the jq project",
        "policy": "recommended",
        "scope": "always",
        "asset_families": ("tool scripts",),
        "remediation": "install jq with the OS package manager",
    },
    {
        "id": "toolchain",
        "tier": 3,
        "provider": "each stack's own toolchain provider",
        "policy": "recommended",
        "scope": _ALL_STACKS,
        "asset_families": ("crucible-report-<stack> skill bundle", "agent definitions"),
        "remediation": (
            "install the stack's toolchain with its provider's own installer "
            "(rustup, bun's installer, arduino-cli's installer, a JDK/Maven source)"
        ),
    },
)


def requirement(requirement_id: str) -> dict:
    """The one row with ``requirement_id``; ``KeyError`` when undeclared."""
    for row in REQUIREMENTS:
        if row["id"] == requirement_id:
            return row
    raise KeyError(f"no requirement declared with id {requirement_id!r}")
