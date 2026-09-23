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
harnesses that cannot honor fail-closed (claude-code, hermes — DN-harness-agnostic-hooks §4.4);
pi honors it because its shim blocks on every non-protocol outcome (spawn
error, other exit code, kill on timeout, unparseable output — CR-MDB-030
§S5), opencode via shim-blocks-on-spawn-failure (DN-harness-agnostic-hooks §2
roster addendum). Every (hook x harness) pairing is accounted for in the report —
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

#: Neutral tool class -> Claude Code tool-name alternation (CR-MDB-030 §S4).
#: A name absent here has no Claude Code equivalent and passes through.
_CLAUDE_TOOL_NAMES = {
    "bash": "Bash",
    "write": "Write",
    "edit": "Edit|MultiEdit|NotebookEdit",
    "read": "Read",
    "grep": "Grep",
    "find": "Glob",
    "ls": "LS",
}


def _claude_matcher(matcher: str | None) -> str:
    """The neutral ``matcher`` in Claude Code's own tool names, translated
    per alternation member; ``*`` for an absent matcher (CR-MDB-030 §S4)."""
    if not matcher:
        return "*"
    return "|".join(
        _CLAUDE_TOOL_NAMES.get(member, member) for member in matcher.split("|")
    )

#: Harnesses whose shims can honor fail-closed. pi: its shim blocks on every
#: non-protocol outcome — spawn error, other exit code, kill on timeout,
#: unparseable output (CR-MDB-030 §S5, proven through Pi's own loader by §S8).
#: opencode: its spawn shim blocks on spawn failure (DN-harness-agnostic-hooks
#: §2 roster addendum). claude-code and hermes are fail-open-only
#: (DN-harness-agnostic-hooks §2/§4.4).
_HONORS_FAIL_CLOSED = frozenset({"pi", "opencode"})

_REFUSAL_REASONS = {
    "claude-code": (
        "fail_direction=closed cannot be honored: claude-code hooks are "
        "fail-open (a hook error allows the action; DN-harness-agnostic-hooks §2) — a guard that "
        "silently degrades is worse than none (DN-harness-agnostic-hooks §4.4)"
    ),
    "hermes": (
        "fail_direction=closed cannot be honored: hermes blocking semantics "
        "are unverifiable (exit-code contract under-documented, user-scope "
        "hooks only; DN-harness-agnostic-hooks §2 roster addendum)"
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
    """Split instances into (emittable, refused) for one harness (DN-harness-agnostic-hooks §4.4)."""
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


def _record_emitted(entry: dict, rel: str, emitted: list[str] | None) -> None:
    """Record a just-written wiring file (relative to ``target``) in the
    harness report entry and, when given, the caller's ``emitted`` out-list.
    Called only AFTER the file's ``atomic_write`` succeeds (CR-MDB-033 §S4)."""
    entry["emitted_files"].append(rel)
    if emitted is not None:
        emitted.append(rel)


def _emit_claude_code(
    instances: list[dict],
    target: Path,
    scripts_root: Path,
    entry: dict,
    emitted: list[str] | None = None,
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
            {"matcher": _claude_matcher(instance.get("matcher")), "hooks": [command_spec]}
        )
    settings_path = target / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(
        settings_path,
        (json.dumps({"hooks": hooks_by_event}, indent=2) + "\n").encode("utf-8"),
    )
    _record_emitted(entry, ".claude/settings.json", emitted)


#: Hook budget applied when an instance declares no ``timeout`` (seconds) —
#: the pi shim always enforces SOME budget, so a hung script can never stall
#: a tool call indefinitely (CR-MDB-030 §S2).
_PI_DEFAULT_TIMEOUT_S = 60

#: TS body of every emitted pi extension, after its generated constants
#: (``SCRIPT``, ``TIMEOUT_MS``, ``FAIL_CLOSED``, ``MATCH``) — CR-MDB-030
#: §S1–§S5.
#: The protocol script is spawned with ``node:child_process`` (``pi.exec``
#: has no stdin option), the payload is written to its piped stdin, and the
#: outcome is decided here: exit 0 allows; exit 2 with a parseable
#: ``{"decision":"block"}`` blocks; ANY other outcome (spawn error, other
#: exit code, kill on timeout, unparseable output) blocks with a reason when
#: fail-closed and allows when fail-open. Before any of that, the Pi event
#: is mapped into the NEUTRAL payload of hooks-src/schema.md (CR-MDB-030
#: §S3) and a tool event whose neutral ``tool_name`` the instance's ``MATCH``
#: does not name returns before spawning (CR-MDB-030 §S4).
_PI_SHIM_RUNTIME = """\
const SHELL_LANGUAGES = new Set(["shell", "bash", "sh"]);

// Pi toolName -> neutral file class (hooks-src/schema.md, Pi mapping).
const FILE_TOOLS = new Map([
  ["write", "write"],
  ["edit", "edit"],
  ["ctx_edit", "edit"],
  ["ctx_patch", "edit"],
  ["read", "read"],
  ["grep", "grep"],
  ["find", "find"],
  ["ls", "ls"],
]);

type NeutralPayload = {
  tool_name: string | null;
  tool_input: unknown;
  cwd: string;
  session_id: string | null;
  harness_tool: string | null;
};

function nonEmptyString(value: unknown): string | null {
  return typeof value === "string" && value !== "" ? value : null;
}

// Every path the call targets: the primary `path`, plus each per-operation
// `path` a ctx_patch call carries -- de-duplicated, in order.
function targetPaths(toolName: string, input: any): string[] {
  const paths: string[] = [];
  const add = (value: unknown) => {
    const path = nonEmptyString(value);
    if (path !== null && !paths.includes(path)) paths.push(path);
  };
  add(input.path);
  if (toolName === "ctx_patch" && Array.isArray(input.ops)) {
    for (const op of input.ops) {
      if (op !== null && typeof op === "object") add(op.path);
    }
  }
  return paths;
}

function neutralTool(toolName: string, rawInput: unknown) {
  const input: any = rawInput !== null && typeof rawInput === "object" ? rawInput : {};
  if (toolName === "bash" || toolName === "ctx_shell") {
    return { tool_name: "bash", tool_input: { command: String(input.command ?? "") } };
  }
  if (toolName === "ctx_execute" && SHELL_LANGUAGES.has(input.language)) {
    return { tool_name: "bash", tool_input: { command: String(input.code ?? "") } };
  }
  const fileClass = FILE_TOOLS.get(toolName);
  if (fileClass !== undefined) {
    return {
      tool_name: fileClass,
      tool_input: { path: nonEmptyString(input.path), paths: targetPaths(toolName, input) },
    };
  }
  return { tool_name: toolName, tool_input: rawInput ?? {} }; // unmapped: passed through
}

function toNeutral(event: any, ctx: any): NeutralPayload {
  const cwd = typeof ctx?.cwd === "string" ? ctx.cwd : process.cwd();
  const id = ctx?.sessionManager?.getSessionId?.();
  const session_id = typeof id === "string" ? id : null;
  if (typeof event?.toolName !== "string") {
    // Not a tool event (session start, turn end, input, compaction).
    return { tool_name: null, tool_input: {}, cwd, session_id, harness_tool: null };
  }
  const { tool_name, tool_input } = neutralTool(event.toolName, event.input);
  return { tool_name, tool_input, cwd, session_id, harness_tool: event.toolName };
}

// matcher on the NEUTRAL tool_name; it filters tool events only.
function matches(payload: NeutralPayload): boolean {
  if (MATCH === null || payload.harness_tool === null) return true;
  return payload.tool_name !== null && MATCH.includes(payload.tool_name);
}

type HookOutcome = {
  code: number | null;
  stdout: string;
  killed: boolean;
  spawnError: string | null;
};

function runHook(payload: unknown): Promise<HookOutcome> {
  return new Promise((resolve) => {
    let settled = false;
    let killed = false;
    let stdout = "";
    let timer: ReturnType<typeof setTimeout> | undefined;
    const finish = (outcome: HookOutcome) => {
      if (settled) return;
      settled = true;
      if (timer !== undefined) clearTimeout(timer);
      resolve(outcome);
    };
    let child;
    try {
      child = spawn(SCRIPT, [], { stdio: ["pipe", "pipe", "ignore"] });
    } catch (err) {
      finish({ code: null, stdout, killed, spawnError: String(err) });
      return;
    }
    timer = setTimeout(() => {
      killed = true;
      child.kill("SIGKILL");
    }, TIMEOUT_MS);
    child.stdout.setEncoding("utf-8");
    child.stdout.on("data", (chunk: string) => {
      stdout += chunk;
    });
    child.on("error", (err: Error) => {
      finish({ code: null, stdout, killed, spawnError: String(err) });
    });
    child.on("close", (code: number | null) => {
      finish({ code, stdout, killed, spawnError: null });
    });
    // A script may exit without reading its stdin (EPIPE on write). That is
    // not a hook outcome in itself: the exit code / kill above decides it.
    child.stdin.on("error", () => undefined);
    child.stdin.end(JSON.stringify(payload));
  });
}

function onFailure(reason: string) {
  return FAIL_CLOSED
    ? { block: true, reason: "fail-closed guard: " + reason }
    : {}; // fail-open: a hook failure allows the action
}

async function decide(payload: unknown) {
  const outcome = await runHook(payload);
  if (outcome.spawnError !== null) {
    return onFailure("hook spawn failed: " + outcome.spawnError);
  }
  if (outcome.killed) {
    return onFailure("hook exceeded its timeout (" + TIMEOUT_MS + " ms) and was killed");
  }
  if (outcome.code === 0) {
    return {}; // protocol: exit 0 allows
  }
  if (outcome.code === 2) { // protocol: exit 2 blocks
    let parsed: unknown;
    try {
      parsed = JSON.parse(outcome.stdout);
    } catch (err) {
      return onFailure("hook printed unparseable output: " + String(err));
    }
    if (parsed !== null && typeof parsed === "object" && (parsed as any).decision === "block") {
      const reason = (parsed as any).reason;
      return { block: true, reason: typeof reason === "string" ? reason : outcome.stdout };
    }
    return onFailure("hook printed unparseable output: exit 2 without a decision=block object");
  }
  return onFailure("hook exited with code " + String(outcome.code));
}
"""


def _pi_matcher(matcher: str | None) -> list[str] | None:
    """The instance ``matcher`` as the neutral tool names it names
    (CR-MDB-030 §S4): ``|``-separated exact names; ``None`` (unfiltered)
    for an absent matcher or one containing ``*``."""
    if not matcher:
        return None
    names = [name.strip() for name in matcher.split("|") if name.strip()]
    if not names or "*" in names:
        return None
    return names


def _pi_extension_text(instance: dict, pi_event: str, script_path: str) -> str:
    """Full TS source of one pi extension (CR-MDB-030 §S1–§S5): a
    default-export factory registering one handler with the 0.87.1
    ``(event, ctx)`` signature that maps the event into the neutral payload,
    honours the matcher, then runs the script. Every interpolated string
    goes through ``json.dumps`` so no raw ``"`` reaches a TypeScript
    literal."""
    timeout_s = instance.get("timeout") or _PI_DEFAULT_TIMEOUT_S
    fail_closed = instance.get("fail_direction") == "closed"
    match = _pi_matcher(instance.get("matcher"))
    return (
        "// Generated by modelb_axi hooks compiler (CR-MDB-030 §S1–§S5) — do not edit.\n"
        'import { spawn } from "node:child_process";\n'
        "\n"
        f"const SCRIPT = {json.dumps(script_path)};\n"
        f"const TIMEOUT_MS = {timeout_s * 1000};\n"
        f"const FAIL_CLOSED = {'true' if fail_closed else 'false'};\n"
        f"const MATCH: string[] | null = {json.dumps(match)};\n"
        "\n"
        + _PI_SHIM_RUNTIME
        + "\n"
        "export default function (pi) {\n"
        f"  pi.on({json.dumps(pi_event)}, async (event, ctx) => {{\n"
        "    const payload = toNeutral(event, ctx);\n"
        "    if (!matches(payload)) return {}; // matcher: never spawned\n"
        "    return decide(payload);\n"
        "  });\n"
        "}\n"
    )


def _emit_opencode(
    instances: list[dict],
    target: Path,
    scripts_root: Path,
    entry: dict,
    emitted: list[str] | None = None,
) -> None:
    """Emit a generated TS spawn-shim plugin under ``.opencode/``."""
    lines = [
        "// Generated by modelb_axi hooks compiler (CR-MDB-015 §S4) — do not edit.",
        'import { spawnSync } from "node:child_process";',
        "",
    ]
    for instance in instances:
        script_path = str(scripts_root / instance["command"])
        # Honor the declared fail
        # direction on spawn failure (status null / thrown) — a fail-closed
        # guard must BLOCK when its script cannot run (DN-harness-agnostic-hooks §4.4).
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
    _record_emitted(entry, str(shim_rel), emitted)


#: pi extension event names (DN-harness-agnostic-hooks §2 roster addendum,
#: event-map citations; ``pre-compact`` -> ``session_before_compact`` per
#: CR-MDB-030 §S5) per universal event.
_PI_EVENTS = {
    "pre-tool-use": "tool_call",
    "post-tool-use": "tool_result",
    "session-start": "session_start",
    "turn-stop": "turn_end",
    "prompt-submit": "input",
    "pre-compact": "session_before_compact",
}


def _emit_pi(
    instances: list[dict],
    target: Path,
    scripts_root: Path,
    entry: dict,
    emitted: list[str] | None = None,
) -> None:
    """Emit one full TS extension per hook under ``.pi/extensions/``."""
    extensions_dir = target / ".pi" / "extensions"
    extensions_dir.mkdir(parents=True, exist_ok=True)
    emitted_any = False
    for instance in instances:
        pi_event = _PI_EVENTS[instance["event"]]  # every VALID_EVENTS member maps
        script_path = str(scripts_root / instance["command"])
        text = _pi_extension_text(instance, pi_event, script_path)
        ext_rel = Path(".pi") / "extensions" / f"{instance['command']}.ts"
        atomic_write(target / ext_rel, text.encode("utf-8"))
        _record_emitted(entry, str(ext_rel), emitted)
        emitted_any = True
    if emitted_any:
        entry["notes"].append(
            "pi loads .pi/extensions/*.ts only after the project-TRUST prompt "
            "(recorded in ~/.pi/agent/trust.json); regeneration re-triggers the "
            "trust re-confirm step (DN-harness-agnostic-hooks §4.5)"
        )


def _emit_hermes_advisory(
    instances: list[dict],
    target: Path,
    scripts_root: Path,
    entry: dict,
    emitted: list[str] | None = None,
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
    _record_emitted(entry, str(advisory_rel), emitted)


def compile_wiring(
    schema_instances: list[dict],
    harnesses: list[str],
    target: Path,
    scripts_root: Path,
    *,
    emitted: list[str] | None = None,
) -> dict:
    """Compile neutral schema instances into per-harness wiring under
    ``target`` (§S4).

    ``emitted`` is an optional caller-owned out-list: when given, each
    wiring file's path (relative to ``target``, the same form as the
    report's ``emitted_files``) is appended to it immediately AFTER that
    file's write succeeds, so the caller still holds exactly the files
    written if compilation raises part-way (CR-MDB-033 §S4). When ``None``
    (the default) nothing beyond the returned report is recorded.

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
                _emit_hermes_advisory(
                    emittable, target, scripts_root, entry, emitted
                )
        elif emittable:
            if harness == "claude-code":
                _emit_claude_code(emittable, target, scripts_root, entry, emitted)
            elif harness == "opencode":
                _emit_opencode(emittable, target, scripts_root, entry, emitted)
            else:  # pi — the roster is validated above
                _emit_pi(emittable, target, scripts_root, entry, emitted)
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
