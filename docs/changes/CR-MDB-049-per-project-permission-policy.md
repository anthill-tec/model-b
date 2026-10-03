# CR-MDB-049 — A strict per-project permission policy: one shell tool, named commands allowed, the rest asks

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-02 into release 1.1.0, wave 3).
Gap analysis, the design record, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (permission policy, scaffold)
**Priority:** P1 — release 1.1.0, wave 3, first.
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** permissions, pi, scaffold, lean-ctx
**Design reference:** DN-multi-harness-deploy-model §D17 (per-project rendering); user ruling
"option (a), strict per project" (2026-10-01) — to be recorded in the DN before the spec derives from it

## Context

`modelb_axi.permission_policy.render_policy` renders each project's
`.pi/extensions/pi-permission-system/config.json`: `"*": "ask"`, and `allow` by exact tool name for
the set `workflow_tools` builds (the file tools, the UI and child-side tools, and the `dispatch` and
`lean-ctx` rows of `modelb_axi.requirements.REQUIREMENTS`; `bash` joins only when lean-ctx is
absent). A shell tool allowed by name allows every command it can run.

## Scope (seed — the user's ruling, to be measured)

- `ctx_shell` is treated as a shell tool (`shellTool`), not a plain allowed tool.
- `bash` allows by command: the stack's Crucible clients, the stack toolchain, `git`, the Sandesh
  CLI, `worktree-flow.py`, `gate-lock.sh` and `modelb-axi`.
- Extension tools the workflow needs are declared in `REQUIREMENTS`, never restated in the policy.
- Everything else asks.

## Open questions for gap analysis

- Does `ctx_shell` enforce lean-ctx's `shell_allowlist_extra` (`~/.config/lean-ctx/config.toml`)?
  Measure it through lean-ctx's published interface before choosing where the command list lives.
- What does `@gotgenes/pi-permission-system` 36.2.1 accept for a command-scoped shell rule (its
  README and installed source)?
- Interim state to retire: the `sandesh_*` allows in the user's global Pi policy (a release step).
