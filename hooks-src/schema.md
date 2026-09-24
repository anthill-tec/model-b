# Neutral hook-definition schema — v1

**Version: v1** (CR-MDB-015 §S2; neutral payload + matcher per CR-MDB-030 §S3/§S4)

This is the harness-agnostic hook-definition schema for Model B. A hook is
declared once as a neutral instance in this schema (machine format: **TOML**,
one instance per hook) and compiled into Pi wiring by the §S4 compiler.
The instance never encodes harness-specific wiring — that is the compiler's
job.

## Fields (six)

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `event` | string | yes | The universal lifecycle event the hook fires on. Valid set (v1): `pre-tool-use`, `post-tool-use`, `session-start`, `turn-stop`, plus the subprocess-tier events `prompt-submit`, `pre-compact`. |
| `matcher` | string | no | Filter over the **neutral** `tool_name` of the payload below (e.g. `bash`, `write|edit`, `*`): `|`-separated alternatives, each an exact neutral tool name. `*` (or omission) means unfiltered. It never names a harness's own tool — `write|edit` also covers every harness tool the mapping sends to `edit` (CR-MDB-030 §S4). |
| `command` | string | yes | The protocol script this hook targets — a bare script name from `hooks-src/scripts/` (no `.sh` suffix, no path). The script speaks the stdin/exit protocol below. |
| `tier` | string | no | Portability tier: `core` (every harness must wire it or DECLARE degradation), `extended` (wired where the harness supports it), `harness-specific` (escape hatch — explicitly non-portable, compiled only for its named harness). |
| `timeout` | integer | no | Hook budget in SECONDS (positive). The compiler converts units to whatever the target harness expects. |
| `fail_direction` | string | see below | Failure-intent declaration: `open` (on hook error, allow the action) or `closed` (on hook error, the action must not proceed). REQUIRED for security-class hooks; Pi honours `closed` (its shim blocks on every non-protocol outcome). |

Optional per-harness escape fields may accompany an instance but MUST be
marked non-portable (`tier = "harness-specific"`); they are outside the
portable v1 field set above.

## Security-class definition (v1, normative)

A hook is **security-class** when its `command` targets one of the `block-*`
BLOCKING guard scripts in `hooks-src/scripts/` (the roster:
`block-direct-cargo-test`, `block-direct-mvn-test`,
`block-cr-completed-without-spec-update`, `block-write-outside-worktree`).
These are enforcement hooks — a harness failure while running one changes
what the guard can guarantee, so the instance MUST declare `fail_direction`
explicitly.

Purely informational hooks (e.g. `ambient-board-status`,
`post-regression-disk-reminder`) never block and are NOT security-class:
`fail_direction` may be omitted (they always degrade open by construction).

## Neutral payload (script input, normative)

Every script reads the **neutral payload** on stdin — never a harness's own
event shape. The harness shim builds it:

| Key | Meaning |
|-----|---------|
| `tool_name` | The neutral tool class (table below). Scripts and `matcher` branch on this. |
| `tool_input` | Shell class (`bash`): `{"command": …}`. File classes (`write`, `edit`, `read`, `grep`, `find`, `ls`): `{"path": …, "paths": […]}` — `paths` is every path the call targets; a file guard checks every entry. Any other tool: the harness input unchanged. |
| `cwd` | The working directory of the session making the call. |
| `session_id` | The harness session id (`null` when the harness exposes none). |
| `harness_tool` | The harness's own tool name — for audit only; no script branches on it. |

An event that carries no tool call (`session-start`, `turn-stop`,
`prompt-submit`, `pre-compact`) delivers the same keys with `tool_name` and
`harness_tool` `null` and `tool_input` `{}`; `matcher` does not filter it.

### Pi mapping (`toolName` → neutral)

| Pi `toolName` | neutral `tool_name` | `tool_input` from |
|---|---|---|
| `bash`, `ctx_shell` | `bash` | `input.command` |
| `ctx_execute` with a shell language (`shell`, `bash`, `sh`) | `bash` | `input.code` as `command` |
| `write` | `write` | `input.path` |
| `edit`, `ctx_edit`, `ctx_patch` | `edit` | `input.path`, and every per-operation `path` a `ctx_patch` call carries, into `paths` |
| `read`, `grep`, `find`, `ls` | same name | `input.path` |
| any other tool (incl. `ctx_execute` in a non-shell language) | passed through under its own name | `input` unchanged |

A tool this table does not map passes through unmatched — a guard silently
stops applying to it. This table is the one place to extend.

**Known limit:** the write boundary governs the file tools. A write performed
by a shell command (`cat > file`, `rm`) is not path-gated by a hook predicate.

## Protocol (script contract)

Every `command` target is an executable at `hooks-src/scripts/<name>` that
reads the neutral payload (JSON) on stdin and answers by exit code:

- **allow** → exit `0` (optionally with informational JSON on stdout);
- **block** → exit `2` with `{"decision": "block", "reason": "…"}` JSON on
  stdout.

Scripts are self-contained (stdlib only), carry zero `WORKFLOW_CYCLE_ID`
coupling and zero user-dotfile client paths. The ambient status hook
(`ambient-board-status`) discovers its Crucible client from Crucible's own
released-client manifest `~/.crucible/crucible-clients.json` (the
`clients[<key>]` entry for the cwd's stack; `MODELB_STATUS_CMD` overrides);
any unresolved manifest or client degrades, and no other location is tried.

## Sample instance (TOML)

```toml
event = "pre-tool-use"
matcher = "write|edit"
command = "block-write-outside-worktree"
tier = "core"
timeout = 5
fail_direction = "closed"
```

Validation entry point: `modelb_axi.hooks.validate_schema(instance: dict)
-> list[str]` — empty list when valid, else one `"<field>: …"` error string
per problem.
