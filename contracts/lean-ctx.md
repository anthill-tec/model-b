# Contract — lean-ctx CLI preference + operational findings

**Owner:** LEAN-CTX project (upstream tool provider).
**Status:** FILED FINDINGS — the surface already exists dual MCP + CLI; this contract
documents the preference order Model B relies on and the operational findings raised.

## Current state

- lean-ctx is already **dual** MCP + CLI (v3.7.5 observed in-session):
  - MCP: 69 `ctx_*` tools (read/search/shell/tree/edit/overview/knowledge/…), 10 read
    modes, tree-sitter AST, compression patterns;
  - CLI: `lean-ctx -c "command"` (compressed shell), `lean-ctx read <file>`,
    `lean-ctx grep <pattern>`, plus management verbs (`onboard`, `doctor`, `status`,
    `gain`, `tools <profile>`, `allow`).
- Governing rules: `~/.claude/rules/lean-ctx.md` (present, imported by the global
  CLAUDE.md) — the mandatory tool mapping and workflow.

## Preference order (as ruled)

1. `ctx_read` over Read/cat/head/tail (mode table: full for edits, signatures for API
   context, diff post-edit, map for large files, lines:N-M for known regions).
2. `ctx_shell` over bash/Shell; `ctx_search` over Grep/rg; `ctx_tree` over ls/find.
3. Native Edit/StrReplace stay native; `ctx_edit` only when Edit's Read precondition is
   unavailable. Write/Delete/Glob are used normally.
4. Compression bypass ladder (only when compressed output hides needed detail):
   `lines:N-M` → `full` → `ctx_shell(cmd, raw=true)`, then return to compressed defaults.

## Filed requests / gaps (operational findings)

### (a) Shell-allowlist friction for project tooling
`ctx_shell` enforces a restricted command allowlist (~204 built-in commands,
`~/.config/lean-ctx/config.toml`). Observed blocks in real orchestration sessions:
- `chezmoi` blocked — this is the user's own dotfile-manager operation invoked in-session, not a Model B mutation (Model B never mutates `~/.claude` itself; the `modelb-axi` installer is the only deployment channel, PRD §D9/§D10), so the block still forces a fallback to the native shell whenever that user-level workflow runs;
- project wrapper scripts blocked — per-project context wrappers (e.g. the
  `/tmp/claude-1000/modelb-crucible` test wrapper) and the `*-crucible.py` clients are
  not on the built-in list, pushing test runs off the compressed channel.

Mitigation in place: the additive `lean-ctx allow <cmd>` flow appends to
`shell_allowlist_extra` WITHOUT replacing the built-in list (currently extra: `sandesh`,
`opensrc`, `python-crucible.py`). Finding filed: project-tool friction recurs per tool;
requested a smoother path (e.g. per-project allowlist file or trust-the-wrapper-dir).

### (b) File-write redirect block × orchestration scripts
The `ctx_shell` file-write redirect block (guarding against uncontrolled writes) collides
with orchestration scripts whose normal operation writes files (test-report generation,
wrapper-managed logs). The block cannot distinguish a sanctioned orchestration write from
an uncontrolled one, so those invocations must leave the compressed channel entirely.
Finding filed: an escape for declared write-targets (or wrapper-level exemption) so
orchestration scripts can stay on `ctx_shell`.
