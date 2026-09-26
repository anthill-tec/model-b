# Archive map — where every relocated path went

This is the index from a path that no longer exists (in a closed CR, an audit, a commit message or
another project) to where its content lives now, who owns it, and which CR or commit moved it.

- **Horizon.** Derived 2026-09-25, through CR-MDB-035, from the CR specs in `docs/changes/`, the
  queue's dated footer notes (`docs/changes/README.md`), `archive/` (+ `archive/BASELINE.md`), the
  2026-07-20 audits (`audits/2026-07-20-*.md`), `docs/research/PRD-model-b-rationalization.md` and
  `git log --diff-filter=DR` / `git log --follow` — never from memory.
- **Living and gated.** `tests/test_archive_mapping.py` gates this file: one table, the five
  columns, the Kind vocabulary, every `moved`/`absorbed` **Now** resolving in this repo, every
  **Moved by** resolving to a CR spec or a commit, and a row for every archived file and every
  named retired path. **Any CR that moves, renames or deletes a mapped path must update its row in
  the same change.**
- **Kind.** `moved` — lives on at **Now** in this repo; `absorbed` — merged into **Now**;
  `deleted` — no successor, **Authority** gives the reason; `external` — authority left Model B,
  **Now** is where it lives and **Authority** names the owner.
- **Patterns.** `<name>` stands for one path component; `{a,b}` for one of the listed names. A
  family row covers members that went to the same place by the same CR. Rows for archived files use
  the file's original location, spelled literally or with `{a,b}` — a `<name>` never stands for
  the name that identifies an archived file; its archived copy is under `archive/wave1..3/` or
  `archive/contracts/`.

| Old path | Kind | Now | Authority | Moved by |
|---|---|---|---|---|
| `~/.claude/AGENTS.md` | moved | `skills-src/model-b/references/sub-agent-procedure.md` | Model B; the `# AGENTS` sub-agent-procedure tail, relocated when the 621-line core was cut to ≤100 lines; deployed to `~/.agents/skills/` | CR-MDB-001, CR-MDB-014 |
| `~/.claude/AGENTS.md` | external | `~/.claude/AGENTS.md` (the frugal core) | the user; Claude Code is not a Model B target (DN-multi-harness §D14), projects carry their own `AGENTS.md` | CR-MDB-001, CR-MDB-031 |
| `~/.claude/memory/agent-baseline.md` | deleted | — | redirect shim to `AGENTS.md`; its 17 referencers repointed to `sub-agent-procedure.md` | CR-MDB-001 |
| `~/.claude/memory/orchestration-universal.md` | deleted | — | redirect shim superseded by the orchestration common/mainline/track split | CR-MDB-001 |
| `~/.claude/memory/{orchestration-common,orchestration-mainline,orchestration-track,sandesh}.md` | moved | `skills-src/model-b/references/` | Model B; same basenames; deployed to `~/.agents/skills/model-b/references/` | CR-MDB-002, CR-MDB-014 |
| `~/.claude/memory/plan_b_workflow_model.md` | deleted | — | broken mis-paste (stub + copy of `project-management.md`); the canonical model is the `model-b` skill | CR-MDB-006 |
| `~/.claude/memory/crucible-ingest.md` | deleted | — | 9-line stub subsumed by the `crucible` skill (`skills-src/crucible/SKILL.md`) | CR-MDB-003 |
| `~/.claude/skills/agent-protocol/` | absorbed | `skills-src/crucible/SKILL.md` | Model B; lifecycle absorbed into the `crucible` skill (Option B — never a standalone bundle) | CR-MDB-003, CR-MDB-016 |
| `~/.claude/skills/agent-protocol/scripts/heartbeat.sh` | deleted | — | not adopted: the client's `register` verb is the touch and ingest is the heartbeat | CR-MDB-003, CR-MDB-016 |
| `~/.claude/skills/{bun-red-testing,bun-green-testing,bun-regression-testing,quarkus-regression-testing}/` | absorbed | `skills-src/crucible/SKILL.md` | Model B; TDD-phase procedure folded into who-runs-what and the stack references (PRD §D4 removal list) | CR-MDB-003 |
| `~/.claude/skills/crucible-report-{bun,java,python,rust}/` | absorbed | `skills-src/crucible/references/` | Model B; `references/<stack>.md` routes to the Crucible-authored `skills-src/crucible-report-<stack>/` imported by CR-MDB-016 | CR-MDB-003, CR-MDB-016 |
| `~/.claude/skills/crucible-report-vscode/` | deleted | — | VS Code is an editor, not a stack: no client ever shipped; its router and re-imported bundle were retired too | CR-MDB-003, CR-MDB-024 |
| `skills-src/crucible-report-vscode/` | deleted | — | vscode retired (an IDE is not a stack; ruling 2026-09-22) | CR-MDB-024, cfefbb5 |
| `skills-src/crucible/references/vscode.md` | deleted | — | vscode retired with its bundle | CR-MDB-024, cfefbb5 |
| `~/.claude/skills/crucible/` | moved | `skills-src/crucible/` | Model B; rewritten against the real client surfaces, authored repo-local; deployed to `~/.agents/skills/` | CR-MDB-003, CR-MDB-011, CR-MDB-016 |
| `crucible:clients/skills/{crucible-register,crucible-report-<stack>}/` | moved | `skills-src/` | Model B owns content, bundling and deploy (handover #1336/#1337); provenance in `skills-src/CRUCIBLE-HANDOVER.md` | CR-MDB-016 |
| `~/.claude/scripts/<stack>-crucible.py` | external | `~/.crucible/clients/<stack>-crucible.py` (discovered via `~/.crucible/crucible-clients.json`) | Crucible; installed by `crucible-axi install`; the retired mirrors and their `__pycache__` residue removed, every reference anchored on the released client | CR-MDB-016, CR-MDB-020, CR-MDB-032 |
| `~/Documents/data_projects/crucible/clients/` | external | `~/.crucible/clients/` | Crucible; no Model B surface or test reads the development checkout | CR-MDB-020, CR-MDB-032 |
| `crucible:docs/research/DN-model-b-language.md` | external | the Crucible repository's `docs/research/DN-model-b-language.md` (origin `a9a8f57`) | Crucible owns the LOCKED ontology; Model B cites a frozen import at `docs/research/DN-model-b-language.md` and never forks it (divergence goes to Crucible over Sandesh) | 2616ad9 |
| `~/.claude/memory/cr-prd-dn-conventions.md` | absorbed | `skills-src/cr-authoring/SKILL.md` | Model B; deployed to `~/.agents/skills/cr-authoring/` | CR-MDB-004, CR-MDB-014 |
| `~/.claude/memory/project-management.md` | absorbed | `skills-src/cr-authoring/references/creq-cres.md` | Model B; only the CReq/CRes pattern kept, the rest dropped as legacy (full text archived) | CR-MDB-004, CR-MDB-014 |
| `~/.claude/memory/git-workflow.md` | absorbed | `skills-src/git-workflow/SKILL.md` | Model B; deployed to `~/.agents/skills/git-workflow/` | CR-MDB-005, CR-MDB-014 |
| `~/.claude/memory/git-multi-account.md` | absorbed | `skills-src/git-workflow/SKILL.md` | Model B (the git half); the chezmoi half went to the `chezmoi` skill, now the user's | CR-MDB-005, CR-MDB-031 |
| `~/.claude/memory/chezmoi-integration.md` | external | the user's own chezmoi practice (no Model B surface) | the user; absorbed into the `chezmoi` skill, which Model B then retired (no chezmoi dependency) | CR-MDB-005, CR-MDB-021, CR-MDB-031 |
| `~/.claude/skills/chezmoi/` | external | the user's own dotfile tooling | the user; chezmoi discipline is not Model B's (user directive 2026-08-27) | CR-MDB-014, CR-MDB-021, CR-MDB-031 |
| `skills-src/chezmoi/` | deleted | — | Model B carries no chezmoi dependency; the discipline is the user's | CR-MDB-031, ab239b1 |
| `/tmp/claude-1000/chezmoi-noauto.toml` | external | the user's own chezmoi practice | the user; the non-TTY workaround recorded in `archive/BASELINE.md` left with the `chezmoi` skill | CR-MDB-021, CR-MDB-031 |
| `~/.claude/memory/QUICK_REFERENCE.md` | deleted | — | superseded by the trigger table; stale `/mnt/project` paths | CR-MDB-006 |
| `~/.claude/memory/stack-detection.md` | deleted | — | routing superseded by the `crucible` skill; taught hand-rolled curl ingest | CR-MDB-006 |
| `~/.claude/memory/devops-environment.md` | absorbed | `skills-src/memory-templates/java-testing-practices.md` | Model B; merged into `java-testing-practices.md`, which became a memory template | CR-MDB-006, 2616ad9 |
| `~/.claude/memory/{java-orchestration,rust-orchestration,operational-commands}.md` | moved | `skills-src/memory-templates/` | Model B; scaffolded per stack into `<project>/docs/memory/` | CR-MDB-006 |
| `~/.claude/memory/{java-coding-standards,java-testing-practices,java-modern-syntax,maven-best-practices,quarkus-patterns}.md` | moved | `skills-src/memory-templates/` | Model B; the five Java references by their original names (`audits/2026-07-20-memory-corpus.md`), all `java-`-prefixed as templates (`maven-best-practices` → `java-maven-best-practices`, `quarkus-patterns` → `java-quarkus-patterns`); PRD §D5 amended — no global memory tier; the originals remain in `~/.claude/memory/` until the user removes them | 2616ad9, CR-MDB-035, CR-MDB-042 |
| `~/.claude/memory/convex-client-server.md` | external | `~/.claude/memory/convex-client-server.md` | the user; not a Model B stack reference | 2616ad9 |
| `~/.claude/agents/{arduino,bun,python,quarkus}-{red,green,verify,fix}-agent.md` | absorbed | `generator/templates/` | Model B; role templates + `generator/stacks/*.toml`, rendered to `generator/agents/` and per project into `.pi/agents/` | CR-MDB-008, CR-MDB-014, CR-MDB-025 |
| `~/.claude/agents/rust-<role>-agent.md` | absorbed | `generator/stacks/rust.toml` | Model B; rust became the fifth generated stack (`generator/agents/rust-*-agent.md`) | CR-MDB-024 |
| `~/.claude/agents/vscode-<role>-agent.md` | deleted | — | an IDE is not a stack (ruling 2026-09-22); the live copies were deleted 2026-09-22 and the substrate retired | CR-MDB-024 |
| `~/.claude/agents/` | external | `<project>/.pi/agents/` (Model B stack × role definitions, rendered by `modelb-axi init`/`agents`) | the user owns the rest of the set (electronics, `inbox-analyst`); Model B renders its stack × role definitions per project (DN-multi-harness §D17) | CR-MDB-025, CR-MDB-024 |
| `~/.claude/skills/{model-b,cr-authoring,git-workflow,bootstrap,shutdown}/` | moved | `skills-src/` | Model B; authored repo-local, deployed by the installer to `~/.agents/skills/` | CR-MDB-014 |
| `~/.claude/skills/code-health/` | moved | `skills-src/code-health/` | Model B; published bundle, deployed with the rust stack | CR-MDB-023 |
| `~/.agents/skills/gap-analysis/` | moved | `skills-src/gap-analysis/` | Model B; adopted with its `CLAUDE.md` references pointed at the project's `AGENTS.md`, deployed to every stack; the unmanaged store copy remains until the user removes it | CR-MDB-042 |
| `~/.claude/projects/-home-antonyj-Documents-data-projects-nai/memory/ORCHESTRATOR-RULES.md` | absorbed | `audits/2026-09-26-orchestrator-rule-triage.md` | Model B; triaged heading by heading, each `common`/`stack` rule landed at its named skill section | CR-MDB-042 |
| `~/.claude/projects/-home-antonyj-Documents-data-projects-nai/memory/ORCHESTRATOR-NAI.md` | absorbed | `audits/2026-09-26-orchestrator-rule-triage.md` | Model B; triaged heading by heading, project facts left to that project's `AGENTS.md` | CR-MDB-042 |
| `~/.claude/projects/-home-antonyj-Documents-configurations-roundhouse/memory/ORCHESTRATOR-Roundhouse.md` | absorbed | `audits/2026-09-26-orchestrator-rule-triage.md` | Model B; triaged heading by heading, project facts left to that project's `AGENTS.md` | CR-MDB-042 |
| `~/.claude/AGENTS.md` | absorbed | `audits/2026-09-26-orchestrator-rule-triage.md` | Model B; the Non-negotiables (1)–(7), triaged rule by rule (Pi has no global agent file) | CR-MDB-042 |
| `~/.claude/projects/-home-antonyj-Documents-data-projects-nai/memory/<topic>.md` | absorbed | `audits/2026-09-26-orchestrator-rule-triage.md` | Model B; the project's inventoried `type: feedback` memories, triaged one topic file per row | CR-MDB-042 |
| `~/.claude/projects/-home-antonyj-Documents-data-projects-crucible/memory/<topic>.md` | absorbed | `audits/2026-09-26-orchestrator-rule-triage.md` | Model B; the project's inventoried `type: feedback` memories, triaged one topic file per row | CR-MDB-042 |
| `~/.claude/projects/-home-antonyj-Documents-data-projects-sandesh/memory/<topic>.md` | absorbed | `audits/2026-09-26-orchestrator-rule-triage.md` | Model B; the project's inventoried `type: feedback` memories, triaged one topic file per row | CR-MDB-042 |
| `~/.claude/projects/-home-antonyj-Documents-configurations-roundhouse-model-b/memory/<topic>.md` | absorbed | `audits/2026-09-26-orchestrator-rule-triage.md` | Model B; the project's inventoried `type: feedback` memories, triaged one topic file per row | CR-MDB-042 |
| `~/.claude/projects/-home-antonyj-Documents-device-projects-Arduino-Valmik/memory/<topic>.md` | absorbed | `audits/2026-09-26-orchestrator-rule-triage.md` | Model B; the project's inventoried `type: feedback` memories, triaged one topic file per row | CR-MDB-042 |
| `~/.claude/projects/-home-antonyj-Documents-device-projects-Arduino-PumpControl/memory/<topic>.md` | absorbed | `audits/2026-09-26-orchestrator-rule-triage.md` | Model B; the project's inventoried `type: feedback` memories, triaged one topic file per row | CR-MDB-042 |
| `~/.claude/skills/<bundle>` | deleted | — | per-harness symlinks into the store; Pi reads `~/.agents/skills/` natively (DN §D15.1), link writer removed | CR-MDB-031 |
| `~/.claude/scripts/worktree-flow.py` | moved | `scripts/worktree-flow.py` | Model B; git/worktree half; deployed to `~/.agents/scripts/` | CR-MDB-022 |
| `scripts/worktree-flow.py` | external | Crucible's plan/queue API (`next`, `checkpoint`, `cycle-done`, the queue verbs) | Crucible; the scheduling half (`next`, `progress`, `cs`, `show`, `reconcile`) removed from Model B | CR-MDB-028 |
| `~/.claude/scripts/schedule_db.py` | moved | `scripts/schedule_db.py` | Model B publishes it TRANSITIONAL (NAI still depends on it); no longer Model B's backend | CR-MDB-022, CR-MDB-028 |
| `~/.claude/scripts/toon.py` | absorbed | `modelb_axi/toon.py` | Model B; the one hand-maintained codec; `scripts/toon.py` is generated from it | CR-MDB-022 |
| `~/.claude/scripts/{skill-release-gate.py,rust-code-health.py,rust-crate-map.py,rust-dead-scan.py,gate-lock.sh}` | moved | `scripts/` | Model B; deployed to `~/.agents/scripts/`; the gate-lock wire contract is `contracts/gate-lock.md` | CR-MDB-022 |
| `~/.claude/hooks/{block-direct-cargo-test,block-direct-mvn-test,block-cr-completed-without-spec-update,block-write-outside-worktree,post-regression-disk-reminder}.sh` | moved | `hooks-src/scripts/` | Model B; normalised to the neutral stdin/exit protocol, compiled per project into `.pi/extensions/` | CR-MDB-015, CR-MDB-030 |
| `~/.claude/hooks/block-bad-cycle-task-name.sh` | deleted | — | guarded a Claude Code task-tool naming rule; Pi has no such tool (script, schema entry and tests retired) | CR-MDB-015, CR-MDB-030 |
| `hooks-src/scripts/block-bad-cycle-task-name` | deleted | — | retired with its Claude-only subject | CR-MDB-030, 7ac3a47 |
| `.claude/settings.json` | deleted | — | Claude Code hook wiring emitter removed; Pi is the only harness (`.pi/extensions/*.ts`) | CR-MDB-031 |
| `.opencode/plugin/<hook>.ts` | deleted | — | OpenCode emitter removed; Pi is the only harness | CR-MDB-031 |
| `hooks/hermes-manual.yaml` | deleted | — | Hermes emitter removed; Pi is the only harness | CR-MDB-031 |
| `CLAUDE.md` | deleted | — | `init` no longer emits the `CLAUDE.md` → `AGENTS.md` symlink; Pi reads `AGENTS.md` (DN §D14). This repo's own symlink stays for harness compatibility | CR-MDB-031 |
| `/tmp/claude-1000/modelb-crucible` | deleted | — | run-context wrapper retired; skills call the installed Crucible client directly | CR-MDB-011, CR-MDB-031 |
| `.claude/worktrees/<cr>` | moved | `contracts/worktree-layout.md` | Model B; worktrees now live at the gitignored `.worktrees/<cr>` inside the repo, and `contracts/worktree-layout.md` is the authority (it names the six consumers) | CR-MDB-031, d688257 |
| `contracts/mail-axi.md` | moved | `archive/contracts/mail-axi.md` | Model B history only; no Pi-era consumer | CR-MDB-031, 63c884b |
| `tests/test_realhome_supersede.py` | deleted | — | real-home gate; the suite is hermetic and CR-MDB-020's anchoring gate supersedes its mirror-absence check | CR-MDB-032, 7b8cb6b |
| `tests/test_<topic>.py::{_read,_raw,_text,_files_under,_files_containing,_archive_has_content_move,_split_frontmatter,_decode,decode_axi,_decode_envelope,_write_exe,_write_fake_executable,_md_section,_parse_env_file,_client_source,_docstring_nodes,_code_string_literals,_carries_retired_register_flag,_rel,_requirements}` | absorbed | `tests/_helpers.py` | Model B; the module-level helper bodies duplicated across test modules, hoisted one family per commit (7b81219 … c6086e9) and kept single by the §S3 duplicate-body gate | CR-MDB-032 |
| `plans/2026-07-20-rationalization-plan.md` | moved | `docs/research/DN-rationalization-plan-review.md` | Model B; `plans/` retired for the standard docs model | f5a03ba |
| `docs/changes/CR-MB-001-core-split.md` | moved | `docs/changes/CR-MDB-001-core-split.md` | Model B; renamed via `CR-MODELB-001` to the MDB acronym | c8dd160, 639333e |
| `docs/changes/CR-MDB-025-omp-harness-support.md` | absorbed | `docs/changes/CR-MDB-025-pi-agent-definitions.md` | Model B; re-specced for Pi, OMP dropped as a target | 542ff8e |
