"""Neutral hook-definition schema validation + per-harness wiring compiler
(CR-MDB-015 §S2 + §S4).

§S2: validates a parsed schema instance (one TOML table -> ``dict``) against
``hooks-src/schema.md`` v1: the six portable fields (``event``, ``matcher``,
``command``, ``tier``, ``timeout``, ``fail_direction``), the universal event
set, and the security-class rule — a hook whose ``command`` targets a
``block-*`` guard script MUST declare ``fail_direction``.

§S4: :func:`compile_wiring` compiles validated neutral instances into
per-harness native wiring (DN-harness-agnostic-hooks §4): claude-code
``.claude/settings.json``; opencode a generated TS spawn shim; pi full TS
extensions under ``.pi/extensions/``; hermes declared degradation (advisory
user-scope snippet only). ``fail_direction=closed`` hooks are REFUSED for
harnesses that cannot honor fail-closed (claude-code, hermes — DN §4.4);
pi and opencode honor it via shim-blocks-on-spawn-failure (DN §2 roster
addendum). Every (hook x harness) pairing is accounted for in the report —
emitted, refused, or degraded-noted; when every requested harness refuses
every hook, :class:`AllTargetsRefusedError` is raised.

Stdlib only (pure runtime path).
"""

import json
from pathlib import Path

from modelb_axi._fsutil import atomic_write
from modelb_axi.harness import HARNESS_ROSTER_IDS, UnknownHarnessError

SCHEMA_VERSION = "v1"

VALID_EVENTS = frozenset({
    "pre-tool-use",
    "post-tool-use",
    "session-start",
    "turn-stop",
    "prompt-submit",
    "pre-compact",
})

VALID_TIERS = frozenset({"core", "extended", "harness-specific"})

VALID_FAIL_DIRECTIONS = frozenset({"open", "closed"})

#: schema.md v1 security-class signal: the command targets a blocking guard.
_SECURITY_CLASS_PREFIX = "block-"


def is_security_class(command: str) -> bool:
    """True when ``command`` targets a blocking (``block-*``) guard script.

    Per schema.md v1 the ``command`` field is a bare protocol-script name,
    but a defensive basename split keeps a pathy value classified correctly.
    """
    name = command.rsplit("/", 1)[-1]
    return name.startswith(_SECURITY_CLASS_PREFIX)


def validate_schema(instance: dict) -> list[str]:
    """Validate one neutral hook-schema instance against schema.md v1.

    Returns an empty list for a valid instance; otherwise one error string
    per problem, each prefixed ``"<field>: "`` naming the offending field.
    """
    errors: list[str] = []

    event = instance.get("event")
    if event is None:
        errors.append("event: required field is missing")
    elif not isinstance(event, str) or event not in VALID_EVENTS:
        errors.append(
            f"event: {event!r} is not in the universal event set "
            f"{sorted(VALID_EVENTS)}"
        )

    matcher = instance.get("matcher")
    if matcher is not None and (not isinstance(matcher, str) or not matcher):
        errors.append(f"matcher: must be a non-empty string, got {matcher!r}")

    command = instance.get("command")
    if command is None:
        errors.append("command: required field is missing")
    elif not isinstance(command, str) or not command:
        errors.append(f"command: must be a non-empty string, got {command!r}")

    tier = instance.get("tier")
    if tier is not None and (not isinstance(tier, str) or tier not in VALID_TIERS):
        errors.append(f"tier: {tier!r} is not one of {sorted(VALID_TIERS)}")

    timeout = instance.get("timeout")
    if timeout is not None and (
        isinstance(timeout, bool)
        or not isinstance(timeout, int)
        or timeout <= 0
    ):
        errors.append(
            f"timeout: must be a positive integer (seconds), got {timeout!r}"
        )

    fail_direction = instance.get("fail_direction")
    if fail_direction is not None and fail_direction not in VALID_FAIL_DIRECTIONS:
        errors.append(
            f"fail_direction: {fail_direction!r} is not one of "
            f"{sorted(VALID_FAIL_DIRECTIONS)}"
        )
    elif (
        fail_direction is None
        and isinstance(command, str)
        and is_security_class(command)
    ):
        errors.append(
            "fail_direction: required for a security-class hook (command "
            f"{command!r} targets a block-* guard script; see schema.md v1)"
        )

    return errors


# --------------------------------------------------------------------------
# §S4 compiler: neutral schema -> per-harness wiring
# --------------------------------------------------------------------------

#: Universal-event -> Claude Code settings.json event-key mapping (v1 pin).
_CLAUDE_EVENT_KEYS = {
    "pre-tool-use": "PreToolUse",
    "post-tool-use": "PostToolUse",
    "session-start": "SessionStart",
    "turn-stop": "Stop",
    "prompt-submit": "UserPromptSubmit",
    "pre-compact": "PreCompact",
}

#: Harnesses whose shims block on spawn failure, so fail-closed IS honorable
#: (DN §2 roster addendum: pi explicitly; opencode is the same spawn-shim
#: emitter class). claude-code and hermes are fail-open-only (DN §2/§4.4).
_HONORS_FAIL_CLOSED = frozenset({"pi", "opencode"})

_REFUSAL_REASONS = {
    "claude-code": (
        "fail_direction=closed cannot be honored: claude-code hooks are "
        "fail-open (a hook error allows the action; DN §2) — a guard that "
        "silently degrades is worse than none (DN §4.4)"
    ),
    "hermes": (
        "fail_direction=closed cannot be honored: hermes blocking semantics "
        "are unverifiable (exit-code contract under-documented, user-scope "
        "hooks only; DN §2 roster addendum)"
    ),
}


class AllTargetsRefusedError(Exception):
    """Every requested harness refused every hook — zero wiring emitted."""

    def __init__(self, commands: list[str]):
        self.commands = commands
        super().__init__(
            "all requested harnesses refused all hooks; no wiring emitted "
            f"for command(s): {', '.join(commands)}"
        )


def _new_report_entry() -> dict:
    return {"emitted_files": [], "refusals": [], "degraded": False, "notes": []}


def _partition(instances: list[dict], harness: str) -> tuple[list[dict], list[dict]]:
    """Split instances into (emittable, refused) for one harness (DN §4.4)."""
    emittable: list[dict] = []
    refused: list[dict] = []
    for instance in instances:
        if (
            instance.get("fail_direction") == "closed"
            and harness not in _HONORS_FAIL_CLOSED
        ):
            refused.append(instance)
        else:
            emittable.append(instance)
    return emittable, refused


def _emit_claude_code(
    instances: list[dict], target: Path, scripts_root: Path, entry: dict
) -> None:
    """Emit ``.claude/settings.json`` in the native Claude Code hooks shape."""
    hooks_by_event: dict[str, list[dict]] = {}
    for instance in instances:
        command_spec = {
            "type": "command",
            "command": str(scripts_root / instance["command"]),
        }
        if instance.get("timeout") is not None:
            command_spec["timeout"] = instance["timeout"]
        hooks_by_event.setdefault(_CLAUDE_EVENT_KEYS[instance["event"]], []).append(
            {"matcher": instance.get("matcher") or "*", "hooks": [command_spec]}
        )
    settings_path = target / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(
        settings_path,
        (json.dumps({"hooks": hooks_by_event}, indent=2) + "\n").encode("utf-8"),
    )
    entry["emitted_files"].append(".claude/settings.json")


def _spawn_shim_body(instance: dict, script_path: str) -> str:
    """TS spawn-shim body for the pi extension emitter: run the protocol
    script via ``pi.exec``, map exit 2 -> block, honor the declared fail
    direction on spawn failure."""
    fail_closed = instance.get("fail_direction") == "closed"
    on_spawn_failure = (
        '    return { block: true, reason: "fail-closed guard: hook spawn failed" };'
        if fail_closed
        else "    return {}; // fail-open: spawn failure allows the action"
    )
    return (
        f'  const result = await pi.exec("{script_path}", [],'
        " { stdin: JSON.stringify(payload) }).catch(() => null);\n"
        "  if (result === null) {\n"
        f"{on_spawn_failure}\n"
        "  }\n"
        "  if (result.code === 2) { // protocol: exit 2 blocks\n"
        "    return { block: true, reason: result.stdout };\n"
        "  }\n"
        "  return {};\n"
    )


def _emit_opencode(
    instances: list[dict], target: Path, scripts_root: Path, entry: dict
) -> None:
    """Emit a generated TS spawn-shim plugin under ``.opencode/``."""
    lines = [
        "// Generated by modelb_axi hooks compiler (CR-MDB-015 §S4) — do not edit.",
        'import { spawnSync } from "node:child_process";',
        "",
    ]
    for instance in instances:
        script_path = str(scripts_root / instance["command"])
        # Mirror the pi _spawn_shim_body semantics: honor the declared fail
        # direction on spawn failure (status null / thrown) — a fail-closed
        # guard must BLOCK when its script cannot run (DN §4.4).
        fail_closed = instance.get("fail_direction") == "closed"
        on_spawn_failure = (
            '    return { block: true, reason: "fail-closed guard: hook spawn'
            ' failed: " + String(result.error) };'
            if fail_closed
            else "    return {}; // fail-open: spawn failure allows the action"
        )
        lines += [
            f"// {instance['event']} (matcher: {instance.get('matcher') or '*'})",
            f'export async function {instance["command"].replace("-", "_")}(payload: unknown) {{',
            "  let result;",
            "  try {",
            f'    result = spawnSync("{script_path}", {{ input: JSON.stringify(payload) }});',
            "  } catch (err) {",
            "    result = { error: err, status: null };",
            "  }",
            "  if (result.error || result.status === null) { // spawn failed",
            on_spawn_failure,
            "  }",
            "  if (result.status === 2) { // protocol: exit code 2 blocks",
            "    return { block: true, reason: result.stdout?.toString() };",
            "  }",
            "  return {};",
            "}",
            "",
        ]
    shim_rel = Path(".opencode") / "plugin" / "modelb-hooks.ts"
    shim_path = target / shim_rel
    shim_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(shim_path, "\n".join(lines).encode("utf-8"))
    entry["emitted_files"].append(str(shim_rel))


#: pi extension event names (DN §2 roster addendum, event-map citations) per
#: universal event. ``pre-compact`` has NO documented pi counterpart —
#: DECLARED GAP: not emitted for pi, noted in the compiler report (same
#: declared-degradation idiom as hermes; NOT a refusal).
_PI_EVENTS = {
    "pre-tool-use": "tool_call",
    "post-tool-use": "tool_result",
    "session-start": "session_start",
    "turn-stop": "turn_end",
    "prompt-submit": "input",
}


def _emit_pi(
    instances: list[dict], target: Path, scripts_root: Path, entry: dict
) -> None:
    """Emit one full TS extension per hook under ``.pi/extensions/``."""
    extensions_dir = target / ".pi" / "extensions"
    extensions_dir.mkdir(parents=True, exist_ok=True)
    emitted_any = False
    for instance in instances:
        pi_event = _PI_EVENTS.get(instance["event"])
        if pi_event is None:
            # DECLARED GAP (DN §2 roster addendum): the universal event has
            # no pi counterpart — not emitted, reported, never silent.
            entry["degraded"] = True
            entry["notes"].append(
                "pi: DECLARED GAP — universal event "
                f"'{instance['event']}' has no pi counterpart; hook "
                f"'{instance['command']}' not emitted for pi (DN §2 roster "
                "addendum)"
            )
            continue
        script_path = str(scripts_root / instance["command"])
        text = (
            "// Generated by modelb_axi hooks compiler (CR-MDB-015 §S4) — do not edit.\n"
            f'pi.on("{pi_event}", async (payload) => {{\n'
            + _spawn_shim_body(instance, script_path)
            + "});\n"
        )
        ext_rel = Path(".pi") / "extensions" / f"{instance['command']}.ts"
        atomic_write(target / ext_rel, text.encode("utf-8"))
        entry["emitted_files"].append(str(ext_rel))
        emitted_any = True
    if emitted_any:
        entry["notes"].append(
            "pi loads .pi/extensions/*.ts only after the project-TRUST prompt "
            "(recorded in ~/.pi/agent/trust.json); regeneration re-triggers the "
            "trust re-confirm step (DN §4.5)"
        )


def _emit_hermes_advisory(
    instances: list[dict], target: Path, scripts_root: Path, entry: dict
) -> None:
    """Emit the hermes ADVISORY snippet — never project-level wiring."""
    lines = [
        "# Hermes advisory hook config (CR-MDB-015 §S4) — MANUAL adoption only.",
        "# Hermes has no project-level hook declaration; shell hooks are",
        "# USER-SCOPE ONLY. Merge the snippet below into ~/.hermes/config.yaml",
        "# yourself. First use requires human consent via the allowlist at",
        "# ~/.hermes/shell-hooks-allowlist.json (hermes prompts per hook).",
        "hooks:",
    ]
    for instance in instances:
        lines += [
            f"  - event: {instance['event']}",
            f"    command: {scripts_root / instance['command']}",
        ]
        if instance.get("timeout") is not None:
            lines.append(f"    timeout: {instance['timeout']}")
    advisory_rel = Path("hooks") / "hermes-manual.yaml"
    advisory_path = target / advisory_rel
    advisory_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(advisory_path, ("\n".join(lines) + "\n").encode("utf-8"))
    entry["emitted_files"].append(str(advisory_rel))


def compile_wiring(
    schema_instances: list[dict],
    harnesses: list[str],
    target: Path,
    scripts_root: Path,
) -> dict:
    """Compile neutral schema instances into per-harness wiring under
    ``target`` (§S4).

    Returns a report dict keyed by harness id, each value
    ``{"emitted_files": list[str], "refusals": list[dict], "degraded": bool,
    "notes": list[str]}`` accounting for every (hook x harness) pairing.
    Raises :class:`ValueError` for invalid instances,
    :class:`modelb_axi.harness.UnknownHarnessError` for harness ids outside
    the roster, and :class:`AllTargetsRefusedError` when every requested
    harness refuses every hook (zero wiring emitted anywhere).
    """
    for instance in schema_instances:
        errors = validate_schema(instance)
        if errors:
            raise ValueError(
                "invalid schema instance "
                f"(command={instance.get('command')!r}): " + "; ".join(errors)
            )
    unknown = [hid for hid in harnesses if hid not in HARNESS_ROSTER_IDS]
    if unknown:
        raise UnknownHarnessError(unknown)

    report: dict = {}
    any_wiring_emitted = False
    for harness in harnesses:
        entry = _new_report_entry()
        report[harness] = entry
        emittable, refused = _partition(schema_instances, harness)
        for instance in refused:
            entry["refusals"].append(
                {"command": instance["command"], "reason": _REFUSAL_REASONS[harness]}
            )
        if harness == "hermes":
            entry["degraded"] = True
            entry["notes"].append(
                "hermes: DECLARED DEGRADATION — no project-level hook "
                "declaration exists; advisory user-scope snippet emitted for "
                "manual adoption (consent allowlist forces human approval)"
            )
            if emittable:
                _emit_hermes_advisory(emittable, target, scripts_root, entry)
        elif emittable:
            if harness == "claude-code":
                _emit_claude_code(emittable, target, scripts_root, entry)
            elif harness == "opencode":
                _emit_opencode(emittable, target, scripts_root, entry)
            else:  # pi — the roster is validated above
                _emit_pi(emittable, target, scripts_root, entry)
        # Uniform accounting: wiring counts as emitted exactly when this
        # harness entry reports emitted files (hermes advisory included).
        if entry["emitted_files"]:
            any_wiring_emitted = True

    if not any_wiring_emitted and all(
        len(report[h]["refusals"]) == len(schema_instances) for h in harnesses
    ):
        refused_commands = sorted({i["command"] for i in schema_instances})
        raise AllTargetsRefusedError(refused_commands)

    return report
