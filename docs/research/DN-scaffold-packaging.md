# DN — Model B packaging, installation & setup (`modelb-axi`)

**Status:** ACTIVE (design record for CR-MDB-014 → CR-MDB-013)
**Scope (per PRD §D10):** release → install → setup — packaging form, install channel, version/update flow, relation to the legacy chezmoi-managed user space.
**Settled by user (lavish review 2026-07-22);** Q5 upgrade story proposed here for ratification.

## 1. Decisions (user-settled)

| # | Decision |
|---|---|
| T | **Technology:** Python package installed via **uv/pipx** — `uv tool install modelb-axi` → isolated venv + globally exported bin. Model proven by Sandesh (`sandesh-relay` uv tool). npx REJECTED (no global CLI export; tooling incl. generators is Python). |
| U | **UX:** ONE adaptive **TUI** CLI (à la the Vercel skill installer). On launch it DETECTS ecosystem state: not set up ⇒ INSTALLER flow; set up ⇒ SCAFFOLD-GENERATOR flow (013). Sensible defaults throughout; the scaffold subsystem runs off this TUI. |
| D | **Dependency orchestration:** installer pre-flight checks ALL dependant tooling — `uv` itself, Sandesh, Crucible — and proactively installs what is missing via each provider's OWN install method. Model B never mirrors provider assets. |
| C | **Config home:** `$MODELB_HOME`, Linux user-home (XDG) conventions per uv/pipx userspace defaults. |
| H | **Initial harness roster:** Claude Code, Hermes, pi (pi.dev), OpenCode. Per-harness support is a FEATURE; additional harnesses are future work. |
| S | **Sequencing:** 014 before 013 — the scaffold flow runs off the installed base. |
| K | **Skills:** deploy ONCE user-scope by the installer; scaffold only references (skill-freeze gating). |
| R | **Repo-local authoring (D9 amended):** all deployable artifacts are authored in this repo; **no CR writes `~/.claude`** — the installer is the ONLY deployment channel. |

## 2. Package shape

- `pyproject.toml` at repo root: package `modelb-axi` (module `modelb_axi/`), console script `modelb-axi`. Installable with `uv tool install .` (dev) — PyPI publication is a later, separate decision; the v1 channel is path/git install.
- **Package assets** (shipped as package data): skill bundles (`skills-src/*` — Vercel-standard layout), memory templates (`skills-src/memory-templates/`), generator (`generator/templates|stacks|build.py`), Model B scripts (`worktree-flow.py`, wrapper template), hook scripts + neutral schema (015 seam), `contracts/`.
- **Generator retarget (deferred from 011):** `build.py` emits into package/repo assets; the chezmoi-source output target is removed.
- **Skill-source imports:** Model B-owned skills still living only in the deployed user space (`model-b`, `cr-authoring`, `git-workflow`, `chezmoi`, `bootstrap`, `shutdown`) are imported into `skills-src/` as assets — a READ-ONLY copy from the deployed state (reading `~/.claude` is allowed; writing never).

## 3. Config seam — `$MODELB_HOME/install.toml`

`$MODELB_HOME` defaults to `${XDG_DATA_HOME:-~/.local/share}/modelb`. Schema (v1):

```toml
[install]
version = "0.1.0"          # package version that performed the deploy
harnesses = ["claude-code", "hermes", "pi", "opencode"]
asset_root = "…"            # resolved package-data root at deploy time

[deps]                      # provider presence recorded at pre-flight
uv = "…"
sandesh = "sandesh-relay/x.y.z (uv tool)"
crucible = "…"              # their installer's report, or "absent"

[files]                     # managed-file manifest: every deployed path + hash
```

Scaffold (013) READS this file via `$MODELB_HOME` → package data → repo fallback; `--harnesses` is a dev-only override; nothing re-asks harnesses per project.

## 4. Flows

TUI form: interactive prompt sequence in the Vercel-skill-installer style (v1: `rich`-based prompts with detected defaults; full-screen TUI not required), every prompt skippable via flags.

**Installer flow** (no `install.toml` found): TUI → (1) dependency pre-flight — `uv` present? Sandesh installed (`uv tool list` / `sandesh` bin)? Crucible installed? Missing ⇒ propose + install via the provider's own method (Sandesh: `uv tool install sandesh-relay`; Crucible: invoke THEIR installer CLI when shipped — until then WARN with instructions, never hand-deploy their assets); (2) harness targeting — probe roster binaries, propose, user confirms (non-interactive flags for CI); (3) deploy — manifest-driven copy of package assets into each selected harness's user-local locations; (4) write `install.toml`. Re-run = upgrade (below).

**Scaffold flow** (`install.toml` present): the TUI adapts and operates as the project scaffold generator — CR-MDB-013's charter, out of 014's scope.

## 5. Upgrade story (Q5 — proposal)

`uv tool upgrade modelb-axi` upgrades the CLI; re-running it re-enters the installer flow **idempotently**: files in the `[files]` manifest are overwritten from package assets (hash-checked; user-modified managed files are listed and confirmed before overwrite — no silent clobber, no three-way merge in v1); files outside the manifest are never touched; the manifest also enables clean uninstall. Scaffolded projects are never touched by upgrades.

## 6. Legacy chezmoi space

At first deploy, paths that chezmoi currently manages become installer-managed: the installer deploys its copy, records it in the manifest, and PRINTS the list of now-superseded chezmoi source paths for the user to retire deliberately (`chezmoi forget`/`destroy` — user-driven, never automatic). The 6 stale `~/.claude/scripts/*crucible*` copies and the 23 agent/hook/memory referencers repoint at deployment time (agents regenerate from package assets; hooks land via 015).

## 7. Testing rule (binds all 014/013 cycles)

Installer/scaffold tests deploy ONLY into throwaway sandbox roots (tmp dirs via env override — `$MODELB_HOME` + per-harness target overrides). The live `~/.claude` is read-only forever in CR work.

## 8. Capability contract and stack selection (2026-09-22 — implements PRD D11)

§4's installer flow checks three PATH binaries (`uv`, `sandesh`, `crucible`) and stops there.
Measurement in wave 2 showed that leaves the installation's most consequential dependencies
unchecked, and the failure is silent: deploying is only writing files, so a harness that cannot
execute the assets accepts every one of them and reports success.

**The pre-flight becomes tier-aware.** Same policy vocabulary as §4 (FAIL / install-on-confirm /
WARN), three new things to say:

| Tier | Probed how | Absence costs |
|---|---|---|
| Harness capabilities (Pi extensions) | the resolved harness config — a package must be in `settings.json` `packages[]`, not merely present on disk | the whole installation is inert |
| Model B's own tools (Sandesh, Crucible clients + server, bundled scripts) | PATH + known install roots | one named capability |
| Per-stack toolchains | `command -v` of the SELECTED stacks only | one stack's agents cannot test |

**Presence is not capability.** The probe reads what the harness will actually load. The
cautionary case is real: `@pi-archimedes/` exists on this machine as an EMPTY directory, absent
from `packages[]`, and was nonetheless named as the dispatch provider in a shipped ruling. A
directory check would have called that healthy.

**Stack selection enters the installer.** `init` has `--stacks`; the installer did not, and
`deploy.py` was stack-blind. The installer gains the same flag with the same vocabulary,
defaulting to all stacks. Selection decides **what is deployed** (a stack's agent definitions and
its `crucible-report-*` bundle; stack-neutral assets always deploy) and **what is probed** — which
is where the cost saving lives. It persists in `install.toml`, so widening later is a re-run, not
a reinstall.

**Probe cost is a design constraint, not an afterthought.** Resolution, not execution: measured,
`command -v` across five toolchains costs ~1 ms while a single `mvn -version` costs ~227 ms
because it spawns a JVM. Version checks run only where a minimum version is genuinely required.

**Remediation keeps §4's boundary.** Model B installs nothing on the user's behalf beyond what
§4 already allowed (Sandesh via `uv`, on confirm). For a missing SDK it names the provider's own
installer and offers to run that, on explicit confirmation; declining is a first-class outcome
that records `absent` and continues. Model B never installs a language toolchain silently, and
never edits the harness config without saying so.

## 9. The install experience is documented for USERS, not just specified

Everything above is a contributor-facing specification. The person running `modelb-axi` on a
fresh machine needs a different document: what to install first, what the stack choice means,
what each pre-flight verdict is telling them, and what to do about a WARN. That guide is a
deliverable of CR-MDB-036 (§S9), not an afterthought — a feature whose whole purpose is to stop
silent failure fails its purpose if its own diagnostics need a spec to interpret.

The guide is authored ONCE and every publishing surface derives from it: the GitHub release
notes, the Pi package README (CR-MDB-029), and the repo README. Four hand-maintained copies of
install instructions is four drifts waiting, and the copy a user follows after it stopped being
true is the expensive one. Extraction is mechanical and gated.

**Reviewing the documentation is a RELEASE step, not a CR gate** (user ruling 2026-09-22) — the
same boundary-event reasoning that keeps the release itself out of the queue. The CR makes the
guide exist and keeps the copies mechanically identical; the release decides whether the doc set
still tells the truth.
