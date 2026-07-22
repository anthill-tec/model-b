# Neutral hook-definition schema — v1

**Version: v1** (CR-MDB-015 §S2)

This is the harness-agnostic hook-definition schema for Model B. A hook is
declared once as a neutral instance in this schema (machine format: **TOML**,
one instance per hook) and compiled per harness (claude-code, opencode,
hermes, pi) by the §S4 compiler. The instance never encodes harness-specific
wiring — that is the compiler's job.

## Fields (six)

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `event` | string | yes | The universal lifecycle event the hook fires on. Valid set (v1): `pre-tool-use`, `post-tool-use`, `session-start`, `turn-stop`, plus the subprocess-tier events `prompt-submit`, `pre-compact`. |
| `matcher` | string | no | Tool/event filter pattern (e.g. `Bash`, `Write|Edit`, `*`). Harness compilers translate it to the native matcher syntax; `*` (or omission) means unfiltered. |
| `command` | string | yes | The protocol script this hook targets — a bare script name from `hooks-src/scripts/` (no `.sh` suffix, no path). The script speaks the stdin/exit protocol below. |
| `tier` | string | no | Portability tier: `core` (every harness must wire it or DECLARE degradation), `extended` (wired where the harness supports it), `harness-specific` (escape hatch — explicitly non-portable, compiled only for its named harness). |
| `timeout` | integer | no | Hook budget in SECONDS (positive). The compiler converts units to whatever the target harness expects. |
| `fail_direction` | string | see below | Failure-intent declaration: `open` (on hook error, allow the action) or `closed` (on hook error, the action must not proceed). REQUIRED for security-class hooks; the compiler REFUSES a `closed` hook on a harness that cannot honor fail-closed. |

Optional per-harness escape fields may accompany an instance but MUST be
marked non-portable (`tier = "harness-specific"`); they are outside the
portable v1 field set above.

## Security-class definition (v1, normative)

A hook is **security-class** when its `command` targets one of the `block-*`
BLOCKING guard scripts in `hooks-src/scripts/` (the imported roster:
`block-direct-cargo-test`, `block-direct-mvn-test`,
`block-bad-cycle-task-name`, `block-cr-completed-without-spec-update`,
`block-write-outside-worktree`). These are enforcement hooks — a harness
failure while running one changes what the guard can guarantee, so the
instance MUST declare `fail_direction` explicitly.

Purely informational hooks (e.g. `ambient-board-status`,
`post-regression-disk-reminder`) never block and are NOT security-class:
`fail_direction` may be omitted (they always degrade open by construction).

## Protocol (script contract)

Every `command` target is an executable at `hooks-src/scripts/<name>` that
reads a JSON payload on stdin and answers by exit code:

- **allow** → exit `0` (optionally with informational JSON on stdout);
- **block** → exit `2` with `{"decision": "block", "reason": "…"}` JSON on
  stdout.

Scripts are self-contained (stdlib only), carry zero `WORKFLOW_CYCLE_ID`
coupling and zero user-dotfile client paths; Crucible client invocation
honors the discovery convention (installed location from install config;
repo path in dev).

## Sample instance (TOML)

```toml
event = "pre-tool-use"
matcher = "Write|Edit"
command = "block-write-outside-worktree"
tier = "core"
timeout = 5
fail_direction = "closed"
```

Validation entry point: `modelb_axi.hooks.validate_schema(instance: dict)
-> list[str]` — empty list when valid, else one `"<field>: …"` error string
per problem.
