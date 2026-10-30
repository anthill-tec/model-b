# CR-MDB-095 — Every workflow tool is allowed by default, and Model B trusts the project root

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-30 from the user's rulings).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (permission policy, requirements, project trust)
**Priority:** P1 — release 1.0.0, wave 2, after CR-MDB-079 (user 2026-10-30; board-authoritative: read
`queue`).
**Depends on:** nothing on the board.
**Labels:** pi, permissions, trust, requirements
**Design reference:** DN-multi-harness-deploy-model §D27 (amended 2026-10-30) and §D25's 2026-10-30
amendment (the workflow's own tools); CR-MDB-037 §S3/§S4; CR-MDB-077; CR-MDB-089.

## Context

Sandesh, Crucible, lean-ctx and the Pi extensions Model B relies on are the workflow's own tools: with them
every Model B project meets its context-management and security requirements and gets its functionality
— sub-agent dispatch and worktree isolation, supervised background processes, the wake path, the
permission policy (DN §D25, amended 2026-10-30). The user ruled (2026-10-30) that these tools are allowed
by default, and that Model B trusts at least the project root of every Model B project on Pi.

Measured 2026-10-30, the generated policy (`modelb_axi/permission_policy.py` `workflow_tools`) already
allows the Sandesh tools (less archive/unarchive), `process`, `web_fetch`/`web_search`,
`subagent`/`get_subagent_result`/`steer_subagent`, every `ctx_*` tool and `lean_ctx`. Two gaps:

- the `worktree` requirement row's tools, `modelb_worktree_enter` and `modelb_worktree_exit` (Model B's
  own Pi package), are not among `_TOOL_REQUIREMENTS`, so they ask;
- pi-lens is no requirement row; its tools (`lens_diagnostics`, `symbol_search`, `module_report`,
  `read_symbol`, `read_enclosing`, `project_report`, `effective_config`, `pi_lens_activate_tools`, and the
  ones it activates) ask.

Project trust: `modelb_axi/project_trust.py` only reads Pi's saved decision and warns when the project is
not trusted (CR-MDB-037 §S4: "Model B never edits `trust.json`"). The user's own `trust.json` holds
`"/home/antonyj": false`, so every new project starts untrusted until the user runs `/trust`, and Pi then
loads none of its hooks or its permission policy.

## Scope (seed)

1. **The worktree tools are allowed:** the `worktree` row joins the policy's tool rows.
2. **A `code-intelligence` requirement row for pi-lens** — recommended, third-party, remediation named and
   never run, as the `processes` and `web-search` rows (CR-MDB-089) — whose tools the policy allows. Its
   exact tool list is measured from the installed package at gap analysis, including the situational tools
   it activates.
3. **`init` and `agents` trust the project root on Pi:** they write `"<root>": true` into
   `<agent-dir>/trust.json` (`$PI_CODING_AGENT_DIR`, else `~/.pi/agent`), atomically, every other entry
   untouched; the file is created when absent. An existing `false` for that exact root is reported and
   left unless `--force-managed`. The envelope reports what was written; the read-only resolver's warning
   stays for the cases left alone.
4. **Records:** the install guide and its `pi-package/README.md` copy, the AGENTS.md section `init`
   scaffolds, the `model-b` skill's setup text and the policy's docstrings say so.
5. **Existing projects** take both with `modelb-axi agents` (and, after 1.0.0, `migrate`).

## To measure at gap analysis

- pi-lens's installed package: its tool names (base and situational), whether a `pi-package` probe finds it,
  and what its `pi_lens_activate_tools` names.
- Pi's trust store (`trust-manager.js`, Pi 1.4.0, read 2026-10-30): `trust.json` is USER-level, at
  `<agent-dir>/trust.json`, keyed by the canonical absolute project path — never inside the project's own
  `.pi/`, so a repository cannot trust itself. Resolution walks from the cwd up to the nearest `true`/`false`
  entry, so the root's own `true` wins over an ancestor's `false`, and a `.worktrees/<cr>` checkout inherits
  the root's entry. Pi reads and writes it under a `proper-lockfile` lock: Model B's write must take the same
  lock (or fail safely when it is held) and keep Pi's key form (canonical path, symlinks resolved). What
  `hasTrustRequiringProjectResources` gates (`.pi/settings.json`, `extensions`, `skills`, `prompts`, …,
  `.agents/skills`).
- The tests that pin the allow-set (`workflow_tools`), the requirement rows, CR-MDB-037 §S4's read-only
  rule and its warning, and the installer's sandboxing (`PI_CODING_AGENT_DIR` in every test).
- The re-score.
