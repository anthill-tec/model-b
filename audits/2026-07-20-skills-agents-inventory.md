# Audit — Skills + agents inventory (2026-07-20)

Scope: 50 skill dirs in `~/.claude/skills/`, 29 agent defs in `~/.claude/agents/`, settings hooks.

## Structural facts
- 4 skill dirs are symlinks → `~/.agents/skills/` (shared axi plugin store): chrome-devtools-axi, find-skills, gh-axi, lavish. `no-mistakes` duplicated in both places.
- `~/.claude/AGENTS.md` (621 lines) canonical; `CLAUDE.md` → symlink.
- 29 agents = 6 TDD stacks × 4 roles (24) + 4 electronics + inbox-analyst.

## Skill classification
- **AXI-CLI:** gh-axi, chrome-devtools-axi, lavish (lavish-axi), no-mistakes (`no-mistakes axi run`); visual-plan/visual-recap use `npx @agent-native/core` (not -axi); lean-ctx is dual (MCP + CLI hooks).
- **MCP-dependent:** mail-tracking-core (ONLY skill with hard `mcp__` calls: FastmailMCP + claude_ai_Gmail + Google Calendar) — 6 downstream mail skills inherit via loading it; bootstrap/shutdown (sandesh_* MCP verbs + `sandesh notify`/`sandesh grant` CLI); lean-ctx. Crucible is NOT MCP (HTTP wrapped by clients). **sys-toolbox-mcp: referenced by NOTHING.**
- **Crucible/TDD:** crucible, crucible-report-{bun,java,python,rust,vscode}, bun-red/green/regression-testing, quarkus-regression-testing, gap-analysis, check-cr-close.
- **Orchestration lifecycle:** bootstrap, shutdown, code-health (MAINLINE-only), status-report, agent-protocol, stay-within-limits.
- **Mail/assistant:** mail-tracking-core, invoice-tracker, purchase-tracker, subscription-watch, warranty-tracker, support-case-manager, product-catalogue.
- **Reviewers/refactorers:** reviewer, reviewer-{architecture,coverage,security,style,syntax,quarkus}, refactorer-{java,rust}.
- **Misc:** git-workflow, git-flow-release, git-flow-develop-gitops, ci-monitor (raw `gh`, not gh-axi), daisyui, read-the-damn-docs, agent-watchdog, plan-arbiter, find-skills, schematic-layout-verify.

## Skill↔memory duplication
1. skills/git-workflow ⟺ memory/git-workflow.md (substantial verbatim); git-flow-release cites memory/git-workflow.md → three-way redundancy.
2. skills/crucible + skills/agent-protocol ⟺ memory/crucible-ingest.md (all defer to AGENTS.md §Crucible-lifecycle).
3. memory/agent-baseline.md = legacy alias; **17 agents still reference it; zero reference AGENTS.md.**
4. bootstrap/shutdown ⟺ orchestration-common/mainline/track + sandesh.md.
5. orchestration-universal.md = dead-weight redirect stub.

## Agent boilerplate (verbatim non-blank line overlap)
- FIX role bun↔python **52%**; VERIFY bun↔python **54%** — templatable.
- RED/GREEN cross-stack 19–30% (diverge on framework syntax).
- Within-stack across roles 10–19% — roles genuinely differ; do NOT merge roles.
- Outliers resisting templates: rust-* (470–814 lines, fully inlined standards) and vscode-* (229–288, ≤28% overlap).
- Verdict: template arduino/bun/python/quarkus × 4 roles (16 generated); rust/vscode/electronics/inbox-analyst stay bespoke.
- Quarkus agents load memory java-* trio (proving on-demand injection works); rust agents inline everything (bloat).
- "sandesh" mentions in python-red/bun-* agents are task-domain artifacts (they were building a sandesh CLI shim), NOT operational deps.

## MCP → AXI replacement surface
- Mail cluster (highest coupling): needs `mail-axi` (or fastmail/gmail/calendar CLIs). Consumers: mail-tracking-core + inbox-analyst + 6 downstream skills.
- sandesh: wake (`sandesh notify`) + admin (`sandesh grant`) already CLI; message verbs (send/reply/fetch/inbox/addressbook/register/unregister) are MCP-only → CLI contract needed. Consumers: bootstrap, shutdown.
- lean-ctx: already dual — lowest cost.

## Hooks (settings.json, active)
PreToolUse-Bash: block-direct-cargo-test.sh, block-direct-mvn-test.sh, block-cr-completed-without-spec-update.sh, lavish-poll-guard.py. TaskCreate: block-bad-cycle-task-name.sh. Write|Edit|NotebookEdit: block-write-outside-worktree.sh. Plus `lean-ctx hook {observe,rewrite,redirect}` on most events. Orphaned (present, NOT wired): mempal_precompact_hook.sh, mempal_save_hook.sh.

## Naming drift
- "Plan B" (agent-protocol, crucible skills, plan_b_workflow_model.md) vs "Model-B" (bootstrap, shutdown, code-health, sandesh MCP description). → unify on **Model B** (decision 5).
- `mvn-crucible.py` keyed to build tool while skill tables say "java".
