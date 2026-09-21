# Audit 2026-09-21 — documentation-vs-code consistency review (read-only)

**Method:** one read-only reviewer sub-agent (pi-archimedes dispatch, config-less) over `AGENTS.md`, `docs/research/*.md`, `docs/changes/*.md`, `skills-src/CRUCIBLE-HANDOVER.md`, `contracts/*.md` (`archive/` exempt), against tree at `HEAD` (last doc commit `ed948af` at review time; post-0.2.2 sweep `836ecfc` touched only CR-017/018/019/020/024 — `AGENTS.md`, `contracts/`, PRD and the other DNs were **not** swept). Nothing was modified. Companion audits: `-modelb_axi.md`, `-assets.md`, `-tests.md`. Consumed by the 2026-09-21 spec amendments (020/021/024/025/026, DN banners) and CR-MDB-031.

**Ground truth applied (latest wins):** README footer 2026-09-18 / 2026-09-21 · DN-multi-harness §D13 (target = Pi) · §D14 (Claude Code dropped; byte-identity retired) · §D16 (dispatch = `pi-archimedes`; emitter target `~/.agents/agents/`) · CR-MDB-027 (RULED) · CR-MDB-025 (re-specced; OMP is not a target, not even transitional) · 2026-09-18 standing rule (no dev-checkout Crucible surfaces; production server + `~/.crucible/clients/` only) · 2026-08-27 directive (no chezmoi dependency) · Crucible 0.2.2 released.

**Code facts measured:** `harness.py:22-26` roster = `claude-code, hermes, pi, opencode`; `deploy.py:32-34` `HARNESS_SKILL_DIRS` = `{claude-code}` only; `deploy.py:37/42/48` three store reldirs (`.agents/skills`, `.agents/hooks/scripts`, `.agents/scripts`), no agent-defs class; `hooks.py:135` `_HONORS_FAIL_CLOSED = {pi, opencode}`, four emitters (`_emit_claude_code/_opencode/_pi/_hermes_advisory`); `cli.py:239-244` writes `[install] version/harnesses/asset_root/tool_scripts_dir` (no `clients_dir`); `pyproject.toml:22-27` force-includes `skills-src, generator, contracts, scripts, hooks-src`; `generator/stacks/*.toml` = 4 stacks, `[frontmatter]` blocks with `model: sonnet|inherit`, `~/.claude/scripts/<stack>-crucible.py`; templates still `--phase`; `skills-src/` = 14 bundles; `tests/` = 19 modules; `tests/test_toon_codec.py:99` and `tests/test_tooling_detachment.py:375` hard-code `~/Documents/data_projects/crucible/clients`; `~/.crucible/clients/` holds all five clients + `toon.py` + `STATUS-CONTRACT.md`; `~/.agents/agents/` holds 25 files.

Legend: **H** = a later session could act on it wrongly today · **M** = misleading, needs a ruling or a marker · **L** = hygiene.

## 1. DOC-VS-DOC contradictions

### 1.1 OMP / Claude Code still presented as targets or deploy destinations

| Location | Cat | Sev | Evidence | Current ruling | Action / owner |
|---|---|---|---|---|---|
| `docs/research/DN-multi-harness-deploy-model.md:1-6` (header) | stale | **H** | `**Status:** ADOPTED … §D16 added` — no note that D1/D2/D5/D6/D7/D10/D11/D12 and half the Consequences table are overtaken | §D13 (Pi), §D14 (OMP not a target, Claude Code dropped), §D16 | Add a header banner: "D1 partly, D2/D5/D6/D7/D10/D11/D12 wholly SUPERSEDED by D13/D14/D16; read D13+ first". **UNOWNED** (DN hygiene; could ride CR-025 gap-analysis) |
| `DN-multi-harness…:54-59` §D1 | contradiction | **H** | "Claude Code and OMP are both emitters… **Claude Code output must stay byte-identical**" | §D14: byte-identity RETIRED; §D16(2): `_emit_pi()` is the ONE emitter | Mark §D1's second sentence superseded in place. UNOWNED |
| `DN-multi-harness…:61-78` §D2 | unwanted | **H** | "OMP receives: agent definitions → `<agentDir>/agents/*.md`… skill bundles → OMP-local copy… tool scripts → OMP-local copy" | 2026-09-21: OMP is NOT a target | Banner "SUPERSEDED 2026-09-21 — no OMP target". UNOWNED |
| `DN-multi-harness…:97-121` §D5, `:123-127` §D6, `:129-141` §D7 | unwanted | **H** | OMP hook factories, `~/.omp/agent` resolution, `config.yml` `modelRoles` verification | Same | Same banner ×3. UNOWNED |
| `DN-multi-harness…:167-231` §D10 | unwanted | **M** | "OMP's plugin/marketplace system is the RIGHT distribution vehicle… dual catalogs (`.omp-plugin/` + `.claude-plugin/`)" | §D13 (1) says "provisionally void"; §D15.2 replaces it with the Pi package system | Banner "SUPERSEDED by §D15.2". UNOWNED |
| `DN-multi-harness…:233-329` §D11, §D12 | stale | **M** | "Stay on OMP"; "A for 1.0.0; C stays live" — only §D13's *title* says it supersedes them; the sections themselves carry no marker | §D13 | In-place "SUPERSEDED by §D13" line under each heading (the DN's own "so the ruling is not corrected back" logic argues for it). UNOWNED |
| `DN-multi-harness…:143-156` §D8 last bullet | stale | L | "shared store for the four sharing harnesses, OMP-local copy for OMP (§D2)" | No OMP | Strike the OMP clause. UNOWNED |
| `DN-multi-harness…:357` §D13 table row | stale | **M** | "Sub-agent definitions … a separate package (`pi-mono-team-mode`), `.pi/teammates/<role>.md`" | §D16: `pi-archimedes`, `~/.agents/agents/` | Footnote the row "→ §D16". UNOWNED |
| `DN-multi-harness…:380-390` §D13 "Required before CR-025 can be rewritten" | stale | L | Five open measurements incl. `:386` "Whether `pi-mono-team-mode` is the sanctioned sub-agent path" | All answered in §D15/§D16 | Mark list "ANSWERED — §D15.1-5, §D16". UNOWNED |
| `DN-multi-harness…:579` Consequences row **019** | contradiction | **H** | "OMP joins the emitter set; `fail_direction: closed` is honourable there" | CR-019 AC (`:117`): `_HONORS_FAIL_CLOSED` "still contains exactly `pi` and `opencode`"; no OMP | Rewrite row: "no change — pi already honours closed". Owner: CR-019 (row) / UNOWNED (DN) |
| `DN-multi-harness…:580` row **024** | stale | **M** | "emitted to BOTH harnesses, not just Claude Code" | Pi only (§D14/§D16) | Rewrite: "emitted by `_emit_pi()` to `~/.agents/agents/`". UNOWNED |
| `DN-multi-harness…:581` row **014** | stale | **M** | "Per §D10 the OMP path is publication… orchestrates a plugin install" | §D16(1): installer deploys `.agents/agents` once, user-scope | Rewrite. UNOWNED |
| `DN-multi-harness…:582` row **012** | contradiction | **H** | "The release gate must prove … **Claude Code output is byte-identical**" | §D14 retired byte-identity; CR-012 spec is unwritten and will be authored from this row | Strike the clause before CR-012 is authored. Owner: CR-012 authoring |
| `DN-multi-harness…:590-592` "Open" bullet 2 | unwanted | L | "Whether the OMP-local skills copy should be a copy or a symlink farm" | No OMP | Delete. UNOWNED |
| `DN-multi-harness…:6` "Supersedes in part: CR-MDB-025's claim that skills already work on OMP" | stale | L | Refers to the OMP-era 025 spec, now git history | CR-025 header: OMP spec "NOT to be consulted" | Rephrase as historical. UNOWNED |
| `docs/changes/CR-MDB-024-rust-stack-adoption.md:86-91` §S2 | contradiction | **H** | "The deployed `~/.claude/agents/rust-*-agent.md` files … are **superseded** … the installer's deploy becomes authoritative, and `test_realhome_supersede.py`'s pattern extends" (+ AC `:119-121`) | §D14: "The 29 `~/.claude/agents/` files become unowned legacy under §D3: never written, never deleted"; CR-025 §S5: "`~/.claude/agents/` is unowned legacy" | Re-scope 024 §S2/AC to: generate into `generator/agents/`, deploy via 025's `.agents/agents` class; drop the real-home supersede of `~/.claude/agents`. Owner: **CR-MDB-024** (amend before RED) |
| `CR-MDB-024…:63-64, :96-99` §S1 | contradiction | **M** | "`[frontmatter]` per role with its skill list… (skills lists, effort, tools)… matching the shape of the other four stack files" | CR-025 §S1 AC: "no `[frontmatter]` free-text block remains"; `effort`→`thinking`, `skills` dropped | Accepted double-regeneration per 025 Risk, but 024 should say its `[frontmatter]` is transitional and will be restructured by 025. Owner: CR-024 |
| `CR-MDB-024…:127-129` AC | stale | L | "`vscode ×4` … remain excluded" | DN §D4: vscode IS generated (bun/TS editor overlay) via its own CR | Reword "untouched by this CR" only. Owner: CR-024 |
| `docs/research/PRD-model-b-rationalization.md:57` §D6 | stale | **M** | "Bespoke (not generated): rust ×4, vscode ×4, …" | CR-024 (rust generated, user ruling 2026-09-16); DN §D4 (vscode generated overlay) | CR-024 AC `:127` names only `DN-rationalization-plan-review.md:72` and CR-008 — **add PRD §D6 and §4.4** to that AC. Owner: CR-024 (gap) |
| `PRD…:106` §4.4 | stale | **M** | "16 agents generated, 13 bespoke intact" | 20 generated (24 with vscode); 5 bespoke (electronics ×4 + `inbox-analyst`) | Same as above. Owner: CR-024 |
| `PRD…:92` §D10(e) | contradiction | **M** | "Initial harness roster — Claude Code, Hermes, pi, OpenCode… **the agent-deployment shape is finalized PER supported harness**" | §D14/§D16: agent definitions target Pi alone, one emitter; roster kept only for hooks/skills (CR-025 §S5) | Add a PRD amendment note: agent-definition target = Pi (§D13/§D14/§D16); roster ≠ agent-def targets. UNOWNED |
| `PRD…:51` §D5 | contradiction | **M** | "Global user scope (`~/.claude/memory/`) keeps ONLY cross-project language refs" | Claude Code dropped; Pi never reads `~/.claude/memory` | Needs a ruling on where global language refs live on Pi. UNOWNED |
| `PRD…:84, :87` §D10.4/.7; `AGENTS.md:3` | unwanted | L | "`CLAUDE.md` symlink — Claude Code compatibility only"; "Claude Code: the project's `.claude/settings.json`" as the lead example | Claude Code dropped | Do not act (root AGENTS.md still mandates the symlink); record "kept for compat, not a target". UNOWNED |
| `docs/research/DN-scaffold-packaging.md:15` (H), `:34` | stale | L | Roster "Claude Code, Hermes, pi, OpenCode"; example `harnesses = ["claude-code", …]` | Roster unchanged in code, but Claude Code is no longer a target | Footnote to §D14. UNOWNED |
| `AGENTS.md:65` | stale | L | Example `modelb-axi --yes --harnesses claude-code --target-root …` | Pi is the target | Change example to `--harnesses pi`. UNOWNED |
| `docs/changes/CR-MDB-019-hook-runtime-correctness.md:117, :141` | stale | L | "claude-code and hermes still refuse a `closed` instance"; "No change to the pi or claude-code emitters" | Factually true of the code; but presents the claude-code emitter as a live surface | Leave code; add "(claude-code emitter retained for compat, not a target — §D14)". Owner: CR-019 |
| `docs/changes/CR-MDB-026-watcher-launch-supervision.md:101-106, :168` | contradiction | **M** | "supervised long-running process… `restart: on-failure`… Three files, instruction-level edits; no `modelb_axi/` logic change" — no Pi mechanism named | DN §D15.3: on Pi the supervisor is a **Model-B-built Pi extension** (CR-MDB-029 deliverable); §D13(3): without it "the watcher regresses to the very defect 026 exists to fix" | 026 must cite §D15.3 and gain `Depends on: CR-MDB-029` (or state its `run_in_background` fallback is the Pi path until 029). CR-029 is not in the queue. Owner: **CR-MDB-026** (amend) + file CR-029 |

### 1.2 Crucible dev-checkout path presented as canonical (2026-09-18 standing rule violated)

| Location | Cat | Sev | Evidence | Ruling | Action / owner |
|---|---|---|---|---|---|
| `AGENTS.md:106` | contradiction | **H** | "`crucible:` = `~/Documents/data_projects/crucible`. Its `clients/*-crucible.py` are the *source of truth*" | README 2026-09-18: "Model B has NOTHING TO DO with the local Crucible PROJECT at any layer… ONLY … the PUBLISHED, INSTALLED clients at `~/.crucible/clients/`" | Repoint to `~/.crucible/clients/` (manifest `~/.crucible/crucible-clients.json`). Owner: **CR-MDB-020 §S0** (AC `:138-141` is repo-wide, but its size estimate `:170` omits `AGENTS.md`) |
| `AGENTS.md:126-130` | contradiction | **H** | "`/tmp/claude-1000/modelb-crucible test …`" wrapper + "`python3 ~/Documents/data_projects/crucible/clients/python-crucible.py regression …`" as the canonical run | Same; wrapper is `/tmp`-ephemeral and unowned | Replace with `~/.crucible/clients/python-crucible.py …`. Owner: CR-020 §S0 |
| `AGENTS.md:148`; `PRD…:41` | contradiction | **M** | "Ontology `crucible:docs/research/DN-model-b-language.md` is LOCKED — cite it" | 2026-09-18 rule bars reading "that checkout's own docs"; CR-020 §S0 AC: "none instructs reading Crucible's own repository (source, clients, or docs) for any purpose" | Genuine conflict — the LOCKED ontology has no published home. Needs a ruling (CReq to Crucible to ship it with the clients?). **UNOWNED** |
| `contracts/crucible-envelope.md:13-15` | contradiction | **H** | "emits it via the shared `crucible:clients/_crucible_axi.py`… codec is `crucible:clients/toon.py`" | Installed clients only | Repoint to `~/.crucible/clients/…`. Owner: CR-020 §S0 (not enumerated) / CR-017 §S4 (which already rewrites this file) |
| `contracts/crucible-envelope.md:39-41` + `tests/test_toon_codec.py:99` | contradiction / doc-vs-code | **H** | "round-trips … through `crucible:clients/toon.py` out of process"; test hard-codes `Path.home()/"Documents/data_projects/crucible/clients"` | Same; `~/.crucible/clients/toon.py` exists | Repoint the oracle path in test + contract. Owner: CR-020 §S0 — but 020 says "No `modelb_axi/` change… 1 test gate added" and never names `tests/`; **extend 020's scope** |
| `contracts/gate-lock.md:4-5, :38-40` + `tests/test_tooling_detachment.py:375` | contradiction / doc-vs-code | **H** | "CRUCIBLE holds the GATE-RUNNER half (`crucible:clients/rust-crucible.py`)"; test evaluates `_gate_lock_path` from the checkout | Same; `~/.crucible/clients/rust-crucible.py` exists | Repoint. Owner: CR-020 §S0 (extend scope) |
| `contracts/crucible-envelope.md:26`; `CR-MDB-022…:9, :191` | stale | L | Cite `crucible:docs/research/DN-crucible-toon-subset.md` (retired, "lineage only") | Rule bars checkout docs even for reference | Replace with "retired upstream note (CR-CRU-046)" without a path. Owner: CR-020 §S0 |
| `PRD…:65` §D7 | stale | L | "bundle path `crucible:clients/`… skill docs ship BUNDLED … at `crucible:clients/skills/`" | Handover complete; checkout barred | Historical paragraph; mark "history — see CR-016". Owner: CR-017 §S4c (PRD pass) |
| `skills-src/CRUCIBLE-HANDOVER.md:9-10` vs `CR-MDB-020…:138-141` | contradiction | L | HANDOVER: "the ONLY place under `skills-src/` allowed to cite the origin path" vs 020 AC: "zero occurrences of a PERSONAL-CHECKOUT client path **anywhere in the repo** outside `archive/`" | Provenance is legitimate history | 020's gate should whitelist `CRUCIBLE-HANDOVER.md` explicitly. Owner: CR-020 |

### 1.3 Retired Crucible verbs/flags still taught

| Location | Cat | Sev | Evidence | Ruling | Action / owner |
|---|---|---|---|---|---|
| `AGENTS.md:145` | contradiction | **H** | "`--wave <n> --orchestrator vidushi-mdb`" | `plan-file --orchestrator` REMOVED; `--cycle`/`--cycle-kind` pairs required (0.2.2) | Owner: **CR-MDB-017 §S4** (`:163-167`, names `AGENTS.md:145`) |
| `contracts/crucible-envelope.md:129-131` | contradiction | **H** | "`plan-file --cr --title --cycles <n> [--wave] [--orchestrator <id>]`… orchestrator from `--orchestrator`" | `--cycles` REFUSED; `--orchestrator` retired | Owner: CR-017 §S4a (named) |
| `contracts/crucible-envelope.md:136` | stale | **M** | "`gate-report` — wave-boundary no-mistakes gate evidence" | `gate-run` (+`--skip`) is the verb; `gate-report` one-shot legacy | Owner: CR-017 §S4b (named) |
| `PRD…:38` §D3.3a | stale | **M** | "LOCAL substitute gate … ingested via `gate-report`" | Same | **Not** in 017 §S4b's list (only SKILL.md:97 + contract:136) — add. Owner: CR-017 (gap) |
| `PRD…:39` §D3.4 | contradiction | **M** | "`plan-file --cr --title --cycles --wave <n> --orchestrator vidushi-<short>`" | Same | Owner: CR-017 §S4c (named) |
| `PRD…:62-68` §D7 | stale | **M** | 3-route endpoint list; "Requested of Crucible: … new `vscode-crucible.py`"; "TOON is served via `?fmt=toon`" | vscode DECLINED (#1370); TOON removed from the SERVER (CR-CRU-132); roadmap/queue routes exist | Owner: CR-017 §S4c (names endpoints + vscode; **add** the `?fmt=toon` claim) |
| `contracts/crucible-envelope.md:20-21` | stale | L | "GETs additionally serve compact TOON via `?fmt=toon` / `Accept: text/toon`" | CR-CRU-132 removed server TOON | Owner: CR-017 §S4 (contract pass — add item) |
| `contracts/crucible-envelope.md:3-7` status | stale | **M** | "DELIVERED — TRACKS CR-CRU-030 + CR-CRU-036 … crucible develop `949a2f4` … owned by … CR-MDB-011's doc pass" | Contract is the RELEASED 0.2.2 installed client; 011 is COMPLETED | Re-pin status to "tracks Crucible release 0.2.2"; ownership → CR-017/020. Owner: CR-017 §S4 |
| `contracts/crucible-envelope.md:116-118` | stale | L | "Model B pins these via the per-project context wrapper (`/tmp/claude-1000/modelb-crucible`)" | `/tmp` wrapper is not a Model B surface | Drop. Owner: CR-017 §S4 |
| `docs/changes/README.md:54` "External dependency (Wave 3)" | stale | L | "NEW vscode client still its own unscheduled CR on their side" (standing section, not a dated note) | 2026-09-16: vscode client "must NOT be built" | Add one line to the section. UNOWNED |
| `docs/research/DN-rationalization-plan-review.md:21, :78` | stale | **M** | "build both (new `vscode-crucible.py`…)"; full `vscode-crucible.py` spec | Declined #1370 | See §3 (needs a HISTORICAL banner). Owner: CR-017 §S4c partly (`:77`, `:99` named) |

### 1.4 chezmoi presented as a live Model B discipline (2026-08-27 directive; CR-021)

| Location | Cat | Sev | Evidence | Action / owner |
|---|---|---|---|---|
| `AGENTS.md:109` | contradiction | **H** | "Every `~/.claude` mutation follows chezmoi discipline: no-auto temp config, manual source commits, deletions via `chezmoi destroy`/`forget`…" | Owner: **CR-MDB-021 §S4** (AC `:135-137` names `AGENTS.md`) |
| `AGENTS.md:135` | stale | **M** | tests assert "deployed `~/.claude`/`~/.agents` state… `chezmoi diff` cleanliness" | Owner: CR-021 §S4 |
| `AGENTS.md:49` | stale | L | "never a `~/.claude` path (chezmoi-managed, so anything written there is reverted…)" — rationale still hangs on chezmoi | Reword to "not Model B-owned". Owner: CR-021 §S4 |
| `PRD…:108` §4.6 | contradiction | **M** | Success criterion "`chezmoi diff` clean after every wave; deleted files stay deleted after fresh `apply`" | CR-021 §S4 scope is `docs/changes/`, `AGENTS.md`, memory-templates — **`docs/research/` is not covered**. Extend 021 §S4 to the PRD. Owner: CR-021 (gap) |
| `PRD…:75` §D9 | stale | L | "chezmoi remains … for destroying legacy files (`chezmoi destroy`/`forget`, D4)" as a Model B step | Owner: CR-021 (gap, same) |
| `docs/research/DN-scaffold-packaging.md:59-61` §6 | stale | **M** | "installer … PRINTS the list of now-superseded chezmoi source paths … (`chezmoi forget`/`destroy`)" | CR-021 §S3 drops the `chezmoi destroy/forget` instruction from the installer message; DN §6 not marked. Owner: CR-021 (gap) |
| `contracts/lean-ctx.md:33-34` | stale | L | "`chezmoi` blocked — every `~/.claude` mutation in this workflow goes through chezmoi… a mandatory discipline" | Reword as historical finding. UNOWNED (contracts/ outside 021 scope) |
| `docs/changes/CR-MDB-021…:139-142` Suite AC | stale | **M** | "collects 194 − 8 = 186 … = **187**, failures/skips no worse than … 7 and 11" | Baseline moved to 240 (CR-022 shipped) and is 240/7F/12S today. Owner: CR-021 (re-measure at RED) |

### 1.5 Version, count and baseline claims

| Location | Cat | Sev | Evidence | Truth | Action / owner |
|---|---|---|---|---|---|
| `AGENTS.md:46` | stale | **M** | "13 skill bundles" | 14 (measured) | Owner: **CR-MDB-023** (`:73-76` records it) |
| `AGENTS.md:53`, `:114` (×2) | stale | **M** | "17 `unittest` modules" | 19 | UNOWNED — fold into whichever CR next touches the baseline sentence (021/028 both carry an AC to re-measure) |
| `AGENTS.md:138` | stale | **H** | "**240 tests, 1 failure, 12 skips** … The one failure is `test_crucible_skill…ac7`" | 240/**7F**/12S today; six failures unexplained in any doc | Re-measure, diagnose the six, record. **UNOWNED** (no CR records the 1F→7F move) |
| `docs/changes/CR-MDB-017…:347` | stale | L | "the recorded 240/1F/12S baseline" | Same | Owner: CR-017 |
| `docs/changes/CR-MDB-022-tooling-adoption.md:3` | contradiction | **M** | "**Status:** PENDING", 0/43 ACs ticked | README 2026-08-27: "CR-MDB-022 SHIPPED (merge `3c3dbdc`)"; board wave 1 = done incl. 022 | Set COMPLETED + tick ACs. UNOWNED (close-out hygiene) |
| `CR-MDB-022…:66-72, :135, :294-296, :431, :445` | stale | **M** | "Crucible **0.2.0 is not released** … must never be cited as available"; AC "No Model B document presents Crucible 0.2.0 as released" | 0.2.0 shipped (2026-09-16); production 0.2.2; CR-023 `:151` explicitly inverts this AC | Mark those lines "SUPERSEDED — 0.2.2 released; see CR-023/028". Owner: CR-023 (already asserts the inverse) |
| `CR-MDB-022…:71-73` | doc-vs-code | L | "The sunset is recorded in `contracts/`" | No `contracts/*.md` mentions `schedule_db`/sunset (grep: 0) | Either add to `contracts/` or strike. Owner: CR-028 (owns the banner) |
| `scripts/schedule_db.py:5-7` | stale (code) | L | "Sunset trigger: Crucible 0.2.0, unreleased today" | 0.2.2 released | Owner: **CR-MDB-028 §S5** (banner correction — named) |
| `CR-MDB-017:5, 018:5, 020:5, 021:5, 023:5, 026:5` (×6) | stale | L | "blocks release **0.1.0**" | Target release renamed **1.0.0** (2026-09-18) | Bulk `0.1.0→1.0.0` in Priority lines. UNOWNED |
| `PRD…:6`, `:75` | stale | L | Sources cite `plans/2026-07-20-rationalization-plan.md`; §D9 lists `plans/` as a workspace dir | `plans/` removed 2026-07-20 (README) | Point at `DN-rationalization-plan-review.md`. UNOWNED |
| `docs/research/DN-harness-agnostic-hooks.md:6` | stale | L | "**Status:** DRAFT … implementation rides CR-MDB-013/015" | 015 shipped 2026-07-23 | Status → ADOPTED/IMPLEMENTED. UNOWNED |

### 1.6 Queue table vs spec headers (dependency / wave edges)

| Location | Cat | Sev | Evidence | Action / owner |
|---|---|---|---|---|
| `README.md:34` (row 028) vs `CR-MDB-028…:11-14` | contradiction | **M** | Row: `Wave 5 · Depends on 022`; spec: "**Depends on:** nothing in this repo… **Phase:** Wave 1 (proposed)" and `:5` "P0 for wave 1" | Reconcile: the repo wave column is historical (5 is right); the board wave is 2 (wave 1 = shipped CRs), so "Wave 1" in the spec collides with the 2026-09-18 board structure. Fix spec header. Owner: CR-028 |
| `CR-MDB-028…:151-153` AC vs `:69-77` §S2 and `:276-278` Risk | contradiction | L | AC "`next` either delegates … or is removed"; Risk "Delegating `next` couples our script…"; §S2 "REMOVED, not delegated (decided)" | Align AC/Risk with §S2. Owner: CR-028 |
| `README.md:35` (row 012) + footer 2026-09-18 | stale | L | Board "wave 2 = the 10 still to do" — 027 and 028 were since added (028 says "1.0.0 becomes eleven CRs"; 027 also in 1.0.0 ⇒ twelve) | One dated footer line recording the board additions. UNOWNED |
| `README.md:25-33` rows 017/018/020/021/023/026 vs spec `Priority` | stale | L | (see 0.1.0 above) | — |
| `CR-MDB-027…:133` AC | stale | L | "[ ] The CR-MDB-025 rewrite cites this ruling" — 025 cites §D16/CR-027 §S1.1 in header, Design reference and Context | Tick. Owner: CR-027 |
| All other pending rows (016–027) | — | — | Queue `Depends on` **matches** spec headers (verified 016, 017, 018, 019, 020, 021, 022, 023, 024, 025, 026, 027) | none |

## 2. DOC-VS-CODE

| Location | Cat | Sev | Claim | Code | Action / owner |
|---|---|---|---|---|---|
| `AGENTS.md:7-12` "three artifact families" (skills, agents, hooks + CLI) vs `DN-multi-harness…:12-13` "three … — skill bundles, generated agent definitions, tool scripts — plus portable hooks" | doc-vs-code | L | Two different enumerations | `deploy.py` ships **three store classes** (skills, hook scripts, tool scripts); agent defs are NOT deployed (CR-025 §S4 adds them) | AGENTS.md: list `scripts/` tool-script family as a fourth asset family and say agent defs are packaged-not-deployed until 025. UNOWNED |
| `AGENTS.md:22-27` INSTALLER flow diagram | doc-vs-code | L | Shows `skills-src/*` and `hooks-src/scripts/*` deploys only | `cli.py:244` + `deploy.py:48,99` also deploy `scripts/* → .agents/scripts` and write `[install].tool_scripts_dir` | Add the line. UNOWNED |
| `AGENTS.md:25` "+ per-harness symlinks (HARNESS_SKILL_DIRS)" | doc-vs-code | L | Implies per-harness | `deploy.py:32-34`: only `claude-code` maps; pi/hermes/opencode are "deploy-inert" — i.e. the ONLY harness receiving skill wiring is the dropped one; Pi works only because §D15.1 says it reads `~/.agents/skills` natively | State that explicitly. UNOWNED |
| `PRD…:100` §3 | doc-vs-code | L | "AC gates are executable **pytest** checks" | `AGENTS.md:114`: "no pytest"; suite is stdlib `unittest` | Fix PRD. UNOWNED |
| `contracts/crucible-envelope.md:39-41`, `contracts/gate-lock.md:38-40` | doc-vs-code | **H** | Tests oracle from `crucible:clients/…` | `tests/test_toon_codec.py:99`, `tests/test_tooling_detachment.py:375` use `~/Documents/data_projects/crucible/clients` — docs and code AGREE, both violate the 2026-09-18 rule | (see §1.2) Owner: CR-020 §S0, scope to be extended to `tests/` and `contracts/` |
| `CR-MDB-018…:43,55,138,183` | — | — | "`~/.crucible/crucible-clients.json` … six keys… all five clients on disk" | Verified: `~/.crucible/clients/` holds all 5 clients + `toon.py` + `STATUS-CONTRACT.md` | consistent |
| `CR-MDB-025…:32-36` | — | — | "`deploy.py` deploys skills, hook scripts and tool scripts… `generator/agents/*.md` … deployed nowhere"; "25 files in `~/.agents/agents/`" | Verified (`deploy.py:37/42/48`; `ls ~/.agents/agents` = 25) | consistent |
| `CR-MDB-025…:49-51, 138-140` | — | — | "`pi` is already in `HARNESS_ROSTER`; `_emit_pi()` in `hooks.py` already exists" | `harness.py:25`, `hooks.py:287` | consistent |
| `CR-MDB-019…:117` | — | — | "`_HONORS_FAIL_CLOSED` contains exactly `pi` and `opencode`" | `hooks.py:135` | consistent |
| `README.md` 2026-08-27 note (018) | — | — | "`ambient-board-status:66` reads `[install].clients_dir` which `config.py` never writes" | `hooks-src/scripts/ambient-board-status:66`; `cli.py:239-244` writes no `clients_dir` | consistent (defect still live, 018 pending) |
| `AGENTS.md:37` emitters; `:49` scripts (7+1); `:51` contracts list; `:96` force-include | — | — | as listed | `hooks.py`, `scripts/` (8 files), `contracts/` (5), `pyproject.toml:22-27` | consistent |
| `generator/stacks/*.toml`, `templates/*.tmpl` | — | — | as documented in 017/020/025 | Still `~/.claude/scripts/<stack>-crucible.py`, `model: sonnet` / `inherit`, `--phase` | owned by 017 §S6 / 020 §S2 / 025 §S1-S3 |

## 3. UNWANTED — sections serving a dropped target, not marked superseded

| Location | Sev | What it serves | Action / owner |
|---|---|---|---|
| `DN-multi-harness…` §D2, §D5, §D6, §D7, §D10, §D11, §D12, Consequences rows 019/024/014/012, Open bullet 2 (≈290 of 592 lines) | **H** | OMP (dropped 2026-09-21) / Claude Code byte-identity (retired §D14) | Do **not** delete (the DN's own method rule keeps overruled reasoning on record); add per-section SUPERSEDED banners + header index. UNOWNED |
| `docs/research/DN-rationalization-plan-review.md` (whole file; **no status header**) | **M** | chezmoi as the deploy channel (`:13`, `:53`, `:92`), `~/.claude/*` as "Critical files" (`:104-110`), "Wave 5 — Close-out" (`:92`, contradicts "NO close-out wave"), `vscode-crucible.py` build (`:21`, `:78`), rust bespoke (`:72`), repo at `~/Documents/side_projects/model-b` (`:53`) | README header cites it as "Evidence base" so it reads as live. Add "**Status:** HISTORICAL plan record (2026-07-20); decisions superseded by PRD amendments, CR-021, CR-024, DN-multi-harness" at the top. UNOWNED (CR-024 AC `:127` and CR-017 §S4c touch single lines only) |
| `docs/research/DN-scaffold-packaging.md:59-61` §6 "Legacy chezmoi space" | **M** | chezmoi retirement path | Mark superseded by CR-021 §S3. Owner: CR-021 (extend §S4 to `docs/research/`) |
| `contracts/lean-ctx.md:15, :33-36` | L | `~/.claude/rules/…` "imported by the global CLAUDE.md"; chezmoi discipline; `/tmp/claude-1000/modelb-crucible` | Reword as dated findings. UNOWNED |
| `contracts/mail-axi.md:10` | L | Observes `~/.claude/skills/mail-tracking-core/SKILL.md` (a personal skill on a dropped harness) | Cosmetic; leave or note "observed 2026-07-20". UNOWNED |
| `AGENTS.md:109`, `:149` (`chezmoi` in load-on-demand list) | L | `:149` is fine (the `chezmoi` skill stays shipped per CR-021 §S1); `:109` is the problem (see §1.4) | Owner: CR-021 |

## Repeats grouped

- **`crucible:` / `~/Documents/data_projects/crucible` as a live surface** — 9 live sites (`AGENTS.md:106,129,148`; `contracts/crucible-envelope.md:14,15,26,39`; `contracts/gate-lock.md:5`; `PRD:41,65`) + 2 tests (`test_toon_codec.py:99`, `test_tooling_detachment.py:375`). CR-020 §S0's AC covers them all; its scope/size estimate covers none.
- **OMP as a target** — 11 sections/rows in `DN-multi-harness…` (§D2, D5, D6, D7, D8-bullet, D10, D11, D12, rows 019/024/014, Open-2); 1 contextual mention `CR-MDB-024:17` (acceptable history).
- **Claude Code byte-identity as live** — `DN:58`, `DN:582`.
- **`gate-report`** — `PRD:38`, `contracts/crucible-envelope.md:136` (017 owns the second only).
- **`plan-file --cycles … --orchestrator`** — `AGENTS.md:145`, `PRD:39`, `contracts/crucible-envelope.md:129-131` (all owned by CR-017 §S4).
- **chezmoi as discipline** — `AGENTS.md:49,109,135`, `PRD:75,108`, `DN-scaffold-packaging:59-61`, `contracts/lean-ctx.md:33`, `DN-rationalization-plan-review` (multiple). CR-021 §S4 owns only `docs/changes/`+`AGENTS.md`+memory-templates.
- **"blocks release 0.1.0"** — 6 pending spec headers.
- **Counts** — bundles 13→14 (`AGENTS.md:46`, CR-023 owns); test modules 17→19 (`AGENTS.md:53,114`, unowned); baseline 1F→7F (`AGENTS.md:138`, `CR-017:347`, unowned); `CR-021:139-142` suite math on a dead 194 base.
- **`0.2.0 unreleased`** — `CR-022` ×6 lines (+ AC), `scripts/schedule_db.py:7` (028 owns the banner; 023 asserts the inverse of 022's AC).

## Summary

1. The 2026-09-21 rulings landed in **CR-025, CR-027 and DN §D13–§D16 only**; the earlier half of the same DN (§D1–§D12, Consequences, Open) still reads as an adopted OMP/Claude-Code plan with no in-place markers, and CR-024 §S2 still plans to supersede `~/.claude/agents/`.
2. The 2026-09-18 "no dev checkout" rule is violated by **`AGENTS.md` itself (3 lines), two `contracts/` files and two tests** — CR-020 §S0's AC forbids them repo-wide but its scope names only `skills-src/`+`generator/`, so RED would find gaps the spec did not size.
3. The chezmoi retirement (CR-021) and the Crucible-verb sync (CR-017) each have precise ACs, but neither covers `docs/research/` or `contracts/`: PRD §4.6/§D9/§D3.3a, DN-scaffold-packaging §6 and `contracts/lean-ctx.md` survive them untouched.
4. Hygiene drift: CR-022 still says PENDING with 0/43 ACs ticked though shipped; six specs say "release 0.1.0"; `AGENTS.md` carries three wrong counts (13 bundles, 17 modules, 1 failure) and an unexplained 1F→7F baseline move; CR-028's header (Wave 1, no deps) disagrees with its queue row (Wave 5, dep 022).
5. Dependency edges in the queue table match every pending spec header except CR-028; CR-026 lacks the edge to the (unfiled) CR-029 Pi-extension watcher that DN §D15.3 makes it depend on.

**Top 3**

1. **`DN-multi-harness-deploy-model.md` §D1/§D2/§D5–§D7/§D10–§D12 + Consequences rows 019/024/014/012** — add SUPERSEDED banners now; row 012 in particular will seed the unwritten CR-012 with a retired byte-identity gate.
2. **`AGENTS.md:106, :126-130` + `contracts/{crucible-envelope,gate-lock}.md` + `tests/test_toon_codec.py:99`, `tests/test_tooling_detachment.py:375`** — dev-checkout Crucible paths taught as canonical; extend CR-020 §S0 scope to `AGENTS.md`, `contracts/`, `tests/` before its RED.
3. **`CR-MDB-024:86-91` §S2** — "installer's deploy becomes authoritative" over `~/.claude/agents/` contradicts §D14/§D3 ("never written, never deleted"); amend before 024 starts, and add PRD §D6/§4.4 to its doc-update AC.
