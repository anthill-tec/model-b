"""Agent definitions: neutral render + per-harness emitters (CR-MDB-025 §S1-§S3).

Each stack x role renders into a **neutral definition** — a plain dict with
``name``, ``description``, ``body``, ``tools`` (intent names), ``thinking``,
``skills`` (list) and, only when the stack TOML sets one, ``model`` — which a
per-harness emitter serialises. ``_emit_pi`` is the only emitter today (DN
§D17); a future harness is one more function in ``EMITTERS``.

Tool intents are translated to harness names through one module-level dict
(§S2); an unknown intent is dropped and the drop is recorded with a reason,
never passed through or renamed.

Stdlib only. Deterministic output: no timestamps, stable ordering.
"""

import tomllib
from pathlib import Path
from string import Template

STACKS = ("arduino", "bun", "python", "quarkus", "rust")
ROLES = ("red", "green", "verify", "fix")

# §S2 — tool intent name -> Pi tool name. Lowercase Pi names only; an intent
# absent from this dict is dropped with a recorded reason.
PI_TOOL_NAMES = {
    "read": "read",
    "write": "write",
    "edit": "edit",
    "grep": "grep",
    "find": "find",
    "ls": "ls",
    "ctx_shell": "ctx_shell",
    "ctx_read": "ctx_read",
    "ctx_grep": "ctx_grep",
    "ctx_glob": "ctx_glob",
    "ctx_find": "ctx_find",
    "ctx_ls": "ctx_ls",
    "ctx_patch": "ctx_patch",
    "ctx_edit": "ctx_edit",
    "ctx_search": "ctx_search",
    "ctx_tree": "ctx_tree",
}

SKILLS_LINE_PREFIX = "Load these skills first:"

# §S4 — tool intents a role's permission policy denies outright, beside the
# allowlist. VERIFY is read-only, so the policy states it as well as the
# tools line (the allowlist never admits these for VERIFY — §S2).
ROLE_DENIED_TOOLS = {"verify": ("write", "edit")}


def load_stack_params(stacks_dir: Path, stack: str) -> dict:
    """Parse one stack TOML (``<stacks_dir>/<stack>.toml``) via tomllib."""
    with (stacks_dir / f"{stack}.toml").open("rb") as fh:
        return tomllib.load(fh)


def neutral_definition(stack: str, role: str, params: dict, templates_dir: Path) -> dict:
    """Render one stack x role into the harness-neutral definition dict."""
    role_table = params["roles"][role]
    template = Template((templates_dir / f"{role}.md.tmpl").read_text(encoding="utf-8"))
    body = template.substitute({
        "display_name": params["display_name"],
        "test_command": params["test_command"],
        "register_command": params["register_command"],
        "unregister_command": params["unregister_command"],
        "crucible_reference": params["crucible_reference"],
        "stack_mechanics": params["mechanics"].strip("\n"),
        "role_gotchas": params["gotchas"][role].strip("\n"),
        # CR-MDB-017 §S6b: the per-stack half of the tier-guidance section.
        "tier_guidance": params["tier_guidance"].strip(),
    })
    defn = {
        "name": f"{stack}-{role}-agent",
        "description": params["description"][role],
        "body": body.strip("\n") + "\n",
        "tools": list(role_table["tools"]),
        "thinking": role_table["thinking"],
        "skills": list(role_table.get("skills", [])),
        "deny": list(ROLE_DENIED_TOOLS.get(role, ())),
    }
    if role_table.get("model"):
        defn["model"] = role_table["model"]
    return defn


def translate_tools(intents: list[str], table: dict[str, str]) -> tuple[list[str], list[dict]]:
    """Translate intent names through ``table``; return (names, drops).

    Order-preserving and de-duplicated. Each drop is a dict naming the
    ``intent`` and the ``reason`` it was dropped.
    """
    names: list[str] = []
    drops: list[dict] = []
    for intent in intents:
        name = table.get(intent)
        if name is None:
            drops.append({"intent": intent, "reason": "unknown tool intent: no harness translation"})
            continue
        if name not in names:
            names.append(name)
    return names, drops


def _emit_pi(defn: dict, drops: list[dict] | None = None) -> str:
    """Serialise a neutral definition as a Pi (``@gotgenes/pi-subagents``) file.

    Frontmatter carries only what the reader reads (§S3): ``name``,
    ``description``, ``tools`` (one comma-separated string), ``thinking``,
    ``permission`` (§S4: ``allow`` for exactly the emitted tools, then
    ``deny`` for the definition's optional ``deny`` intents), and ``model``
    only when the definition sets one. Skills become one body line.
    Dropped tool intents are appended to ``drops`` (when given), each tagged
    with the definition name.
    """
    tools, dropped = translate_tools(defn["tools"], PI_TOOL_NAMES)
    denied, dropped_denies = translate_tools(defn.get("deny", []), PI_TOOL_NAMES)
    if drops is not None:
        drops.extend({"name": defn["name"], **d} for d in dropped + dropped_denies)
    lines = [
        "---",
        f"name: {defn['name']}",
        f"description: {defn['description']}",
        f"tools: {', '.join(tools)}",
        f"thinking: {defn['thinking']}",
        "permission:",
        *(f"  {tool}: allow" for tool in tools),
        *(f"  {tool}: deny" for tool in denied if tool not in tools),
    ]
    if defn.get("model"):
        lines.append(f"model: {defn['model']}")
    lines.extend(["---", ""])
    if defn["skills"]:
        lines.extend([f"{SKILLS_LINE_PREFIX} {', '.join(defn['skills'])}.", ""])
    return "\n".join(lines) + "\n" + defn["body"]


EMITTERS = {"pi": _emit_pi}


def render(
    stack: str,
    role: str,
    params: dict,
    templates_dir: Path,
    harness: str = "pi",
    drops: list[dict] | None = None,
) -> str:
    """Render one stack x role for ``harness``: neutral definition, then emit."""
    return EMITTERS[harness](neutral_definition(stack, role, params, templates_dir), drops)
