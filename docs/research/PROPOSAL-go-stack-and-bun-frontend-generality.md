# PROPOSAL — A `go` generated stack, and a `bun` stack that serves a browser frontend

**Status:** PROPOSAL — for the Model B maintainers' review; nothing here is filed on the board yet.
**Filed:** 2026-10-18, against Model B at `b4c7ea2` (2026-10-17) and Crucible clients `0.3.0`.
**Revised:** 2026-10-18 (same day), after the motivating project's Bun migration shipped — §1 is now the
measured state, not an assumption, and §4.1 adds what the migration taught about Bun.
**Reviewed:** 2026-10-18 by the Model B maintainers. Rulings: DN-multi-harness-deploy-model §D25; filed as CR-MDB-079 and CR-MDB-080, folded into CR-MDB-055, CR-MDB-066 and CR-MDB-074.
**Motivating project:** Arduino App Lab — a Go 1.26 backend inside a Wails v2 desktop shell, with
a React 18 / TypeScript browser frontend in a workspace monorepo.
**Built against the project's target state (§1) — reached on 2026-10-18** (four CRs, `CR-AAL-001`–`004`, on
the project's `develop`).
**Shape followed:** CR-MDB-024 (Rust as a fifth generated stack) — the precedent for "add a stack".
**Design references:** DN-multi-harness-deploy-model §D17–§D18; PRD D3.1; AGENTS.md "Crucible's
installed clients … are the only sanctioned client surface"; CR-MDB-074 (project type, `frontend`);
Crucible CR-CRU-054 (client fleet DRY), CR-CRU-111 (tier declared by the client), CR-CRU-133 and
CR-CRU-015 (a declared target is run by name; the client never classifies the runner),
CR-CRU-151/153 (stack stamp, compile-error decoding).

> **Ask of the maintainers.** Two rulings (§2), one new stack (§3), one generality finding on the
> existing `bun` stack (§4), one note for CR-MDB-074 (§5), and the CR set in order (§6).
> Everything measured below was measured on this workstation on 2026-10-18.

---

## 1. The state this proposal is built against (measured 2026-10-18, after the migration)

The project moved from Node.js/Yarn/Lerna to a **full Bun environment** on 2026-10-18 (its
`CR-AAL-001`–`004`; design record `docs/research/DN-bun-environment.md` in that repository):

| Layer | State |
|---|---|
| Backend | Go 1.26, **two `go.mod`s** (repo root; `standalone-apps/app-lab-desktop/`), `testing` + testify, 36 `*_test.go` |
| Desktop shell | Wails v2 — `wails.json` `frontend:install`/`build`/`dev:watcher` call `bun` |
| Frontend runtime / PM | Bun 1.4.2: `bun.lock`, root `bunfig.toml` + a two-line `bunfig.toml` (`[run] bun = true`) in each of the 18 workspaces, Bun workspaces; `tsc`, `vite`, `vitest` execute on the Bun runtime with **no Node on `PATH`** (proven by a gate) |
| Frontend tests | **Vitest stays the package test runner, run through Bun** (`bun run test` → `vitest`; 60 files, 7 packages, jsdom + Testing Library + MSW 2). `bun test` runs the repository's structural gates only. The `bun test` migration was spiked and declined — see §4.1 |
| Generated artefacts | `wailsjs/` (Wails), `routeTree.gen.ts` (TanStack Router), `lang/compiled/` (FormatJS), OpenAPI types, Style Dictionary tokens |

**Consequence for Model B:** the frontend is the **existing `bun` stack** — no new frontend stack,
no new client, no new hook. `bun-crucible.py`'s tier verbs run a declared `package.json` script by
name and never classify the runner (Crucible CR-CRU-133), so a `test:unit` that is `vitest run
--reporter=junit` is served as-is. Only the Go half is uncovered. What the frontend *does* expose
is that `bun.toml`'s content is not yet general enough to serve it (§4).

## 2. Rulings requested

| # | Ruling | Proposed answer | Why |
|---|---|---|---|
| R1 | How is a Go + Bun + Wails project expressed? | **`PROJECT_STACKS=go,bun`, `PROJECT_TYPE=frontend`.** One new stack (`go`); no new project type. | A stack is *runner + reporter + client*; Go has its own. Wails is a shell with no test runner — the same category rule as the 2026-09-22 vscode ruling. CR-MDB-074's `frontend` type already parameterises everything a Wails dev loop varies (§5). `PROJECT_STACKS` is already a CSV. |
| R2 | Who authors `go-crucible.py`? | **Crucible, first.** The Model B `go` CR is blocked on it. | AGENTS.md: Model B "ships, vendors and maintains none of" `~/.crucible/clients/*`. |

## 3. The `go` stack

### 3.1 Client (Crucible-owned): `~/.crucible/clients/go-crucible.py`

Same verb surface as the fleet (`register` / `unregister` / `test` / `regression` / `check` /
`pre-merge-gate` / `plan-file` / `cycle-activate` / `cycle-done` / `cr-close` / `auto-ingest`),
built on `_crucible_axi.py` (CR-CRU-054). Manifest key `go`; stack stamp on every ingest
(CR-CRU-151).

| Verb | Toolchain | Notes |
|---|---|---|
| `test` | `gotestsum --junitfile <reports>/junit.xml -- <pkg> [-run <regex>]` | gotestsum emits JUnit natively; fallback without it: `go test -json` → inline JUnit (stdlib). Go has a real one-test filter (`-run`) — a gap the bun client documents. |
| `check` | `go build ./... && go vet ./...` → `/runs/compile` | Go's `file.go:L:C: message` lines are the whole decoder (arduino's analogue: CR-CRU-153). |
| `regression` | `go test ./... -coverprofile=cover.out` across **every module** | `-coverprofile` is not lcov. **Recommend** a small stdlib coverprofile→lcov converter in the client (no new tool, no server change); the alternative is a board codec per CR-CRU-015's `rawReport` route — decide at the client CR's gap analysis. |
| cwd | `--module-dir` > `$GO_CRUCIBLE_MODULE_DIR` > nearest `go.mod` above cwd | The motivating project has two modules — bun's `--package-dir` by another name. |

### 3.2 `generator/stacks/go.toml`

In the shape `quarkus.toml` / `rust.toml` establish — every key, `tier_guidance` included
(CR-MDB-017). Content reconciled from a new `skills-src/memory-templates/go-orchestration.md`, the
memory template winning where they disagree (CR-MDB-024 §S1's rule).

**Tier guidance:**

| Tier | Go mechanism |
|---|---|
| `unit` | packages with no build tag, or `go test -short` |
| `integration` | `//go:build integration` files, run with `-tags integration` |
| `module` | one `go.mod` at a time — meaningful here, two modules |
| `regression` | every module, `./...`, coverage on — the orchestrator's merge gate, never the agent's |
| `e2e` / `bdd` | unavailable until the project declares a driver; report the tier actually run and raise the gap |

**Mechanics and gotchas the TOML carries:**

- **The purity rule** — arduino's "native tests cover PURE modules only", in Go: code touching the
  Wails runtime (`runtime.*`, the `OnStartup` context), serial/board I/O, or the `arduino-cli`
  gRPC daemon is integration; interface it out and unit-test the pure logic. RED targets a
  package, never `./...`.
- Table-driven tests, `t.Run` subtests, testify `require` for preconditions / `assert` for
  outcomes; `t.Parallel()` only where the SUT has no package-level state. Verify the test count
  moved; no `t.Skip` left on new tests.
- Never hand-edit generated artefacts: `wailsjs/` bindings, protobuf/gRPC stubs. VERIFY
  diff-gates them.
- GREEN quality rules: no swallowed errors (`_ = err`, empty `if err != nil {}`); wrap with `%w`;
  no `panic` on recoverable paths; contexts passed, never stored; no `init()` side effects;
  exported Wails-bound methods documented — they are the frontend's API.
- VERIFY read-only list: `go vet`, `staticcheck`, `golangci-lint run` (check mode), `go build`,
  the client's verbs. Forbidden: `gofmt -w`, `goimports -w`, `go fix`, `golangci-lint run --fix`.

### 3.3 Model B touchpoints (every place a stack lives today, grep-verified)

| Touchpoint | Change |
|---|---|
| `requirements.STACK_CLIENT_KEYS` | `"go": "go"` |
| `requirements.STACK_TOOLCHAINS["go"]` | `python3` (the fleet's lead probe, CR-MDB-063 §S1) · `go` — `no_install=ELEVATED` (remediation names go.dev's tarball and the distro package) · `gotestsum` — `("go", "install", "gotest.tools/gotestsum@latest")`, `expected="in ~/go/bin (GOPATH/bin), which must be on PATH"` |
| `scaffold.KNOWN_STACKS`, `agents.STACKS`, `cli.py` | add `go` |
| `workflows._TEST_PARTS` + `workflows-src/release/test-go.yml` + `ACTION_PINS` | `actions/setup-go` pinned by sha |
| `hooks-src/scripts/block-direct-go-test` + `scaffold._hook_instances` (§S7 loop) | positions `go test`, `gotestsum`, `task test` / `task <ns>:test`; marker `go.mod` by the walk `block-direct-bun-test` defines; `closed` |
| `skills-src/crucible/SKILL.md` + `references/go.md`, `CRUCIBLE-HANDOVER.md` (6 → 7 imported) | import Crucible's `crucible-report-go` byte-identical |
| `skills-src/memory-templates/go-orchestration.md` | new |
| Census gates | `--list` 20 → 24 agents; bundles 15 → 16; `block-direct-*` 4 → 5; `KNOWN_STACKS` 6 → 7; `_TEST_PARTS` 6 → 7 |

The Wails CLI and `webkit2gtk` are **not** `go`-stack probes: the generated TDD agents never build
the desktop app. They are a project AGENTS.md / services-skill concern (§5).

## 4. Finding — `bun.toml` is Sandesh-specific, and a browser frontend exposes it

The `bun` stack's *mechanics* are right for any Bun project (client verbs, package-dir cwd,
`bun:test` imports, the `check` typecheck gate, declared-script tiers). Its *content* is not.
Measured in `generator/stacks/bun.toml`:

| Section | What it says | Holds for a React/DOM frontend? |
|---|---|---|
| `mechanics` | "The SUT is a thin TS shim that shells to the `sandesh` CLI"; "read the Pi extension API via `opensrc fetch earendil-works/pi`"; "Sandesh-core stays Python-pure (PE3)" | No — this is one project's architecture. |
| `gotchas.red` | assertion patterns are exact `sandesh` argv; "Mocking `pi` (the harness)"; "For a CLI-mapping CR read the tool-param → CLI-flag table" | No. |
| `gotchas.green` | "Build argv exactly per the mapping table"; "Keep the shim thin"; TypeBox schemas for `registerTool` | No. |
| `gotchas.verify` | "each verb is `pi.registerTool`-ed"; "`git diff … -- sandesh/` is EMPTY" | No. |
| `gotchas.fix` | argv / `--to-msg` / `$SANDESH_PROJECT` fixes | No. |
| `tier_guidance` | project-declared `test:<tier>` scripts; hand-picked lists are `unit`; `module` needs declared package boundaries | **Yes — and Bun workspaces make `module` real.** |
| the `strict`/no-`any`/no-`.only`/count-must-move rules | runner-neutral | Yes. |

Every other stack's TOML is written for the stack (`rust.toml`, `quarkus.toml`, `python.toml`);
`bun.toml` was distilled from the Sandesh pi-extension agents (its header says so) and never
generalised. A rendered `bun-red-agent` for Arduino App Lab would instruct the agent to mock
`pi.exec` and assert `sandesh` argv.

**Proposed CR — `bun.toml` generality** (small, content-only; the generator and the client are
untouched):

- Move the Sandesh-specific text to where project specifics live — `skills-src/memory-templates/`
  / the project's own knowledge store (CR-MDB-045/060) — and keep in `bun.toml` only what holds
  for every Bun project.
- Add the frontend half that is missing, written **runner-neutrally** — a Bun-stack project may
  run its suites with `bun test` or with Vitest under Bun, and the client serves both (CR-CRU-133):
  DOM environment (jsdom/happy-dom) with Testing Library queries by role/label, MSW 2 for HTTP,
  `fake-indexeddb`, module mocks through the runner's own API, never a live network call from a
  unit test; run in the **package** dir of a Bun workspace (`bun run --filter <pkg> test` is the
  `module` tier; the root script is the whole suite); never hand-edit generated artefacts
  (`routeTree.gen.ts`, `lang/compiled/`, OpenAPI types, token output, `wailsjs/`) — VERIFY
  diff-gates them.
- The `bun` hook needs no change: `bun.lock` / `bunfig.toml` are its markers and both exist in the
  target state.

### 4.1 Measured on Arduino App Lab (2026-10-18) — what a Bun-stack project runs into

Everything below was measured during the migration, each with a gate that now guards it. The
ones marked **TOML** belong in `bun.toml`'s `mechanics`/`gotchas` as stack facts; the ones marked
**DN** are migration guidance a project's own design note should carry, not the stack file.

| Finding | Where it belongs |
|---|---|
| **Bun reads `bunfig.toml` from the current directory only.** A root `[run] bun = true` does not reach a package-local `bun run test`/`bun run build`: those executed `vitest`/`tsc`/`vite` on the system Node for days unnoticed. Each workspace needs its own `bunfig.toml` (a byte-identical two-liner, gate-kept). `bun.toml`'s "run tests in the bun package dir" silently assumes this is in place. | **TOML** |
| **Bun's native `Worker` leaks into jsdom tests.** A conditional stub (`globalThis.Worker ??= Noop`) is a no-op under Bun — the native one is handed a jsdom `URL` and throws at module load. Stub unconditionally in the shared Vitest setup. The one Bun-runtime divergence found across 60 files; everything else (build status, `tsc` counts, per-file outcomes) was identical to Node. | **TOML** |
| **`bun test` for existing Vitest suites — declined after a spike.** `mock.module` is process-wide and leaks across files in one invocation; `mock.restore()` does not undo it; async factories (`vi.mock(spec, async (importOriginal) => …)`, 22 sites) are unsupported; `vi.mock` hoisting has no equivalent (73 sites, structural rewrite). `bun test` is kept for structural gates with no module mocks and no DOM. The stack text should not presume `bun test` is the runner. | **TOML** |
| **Bun 1.4 chose the isolated linker** (`node_modules/.bun/`) for this workspace; `tsc` resolves `types` by walking ancestor `node_modules/` and could not see `@testing-library/jest-dom`. `linker = "hoisted"` restores the Yarn layout. | **DN** |
| **Peer ranges are resolved against the registry even with `[install] peer = false`.** An exact peer on a workspace package (`1.2.12` vs the workspace's `1.4.3`) sent Bun to GitHub Packages. Internal peers must be ranges the workspace version satisfies. | **DN** |
| **Regenerating the lockfile is a dependency upgrade.** Bun cannot import a Yarn Berry lockfile; a fresh `bun.lock` moved 14 direct ranges and 689 transitive packages to newer versions (one of them broke `moduleResolution: Node` typing). Carried Yarn's resolution back in through temporary `overrides`, then removed them; a lock-parity gate against the Yarn fixture now stands. A `bun` stack project migrating from Yarn/pnpm needs this step named. | **DN** |
| **Bun runs workspace lifecycle scripts** — a `prepare: husky install` inside a workspace (no `.git` there) fails the install. | **DN** |
| **Strict ESM linking exposes what Vite-node hid.** Bun refuses at link time a named import the module does not export; Vite-node yields `undefined`. Running a suite under Bun surfaced ≥ 20 such defects in the fork's placeholder packages — real bugs, found only because the runtime was strict. | **TOML** (as a VERIFY heuristic) |

The declared-script model held throughout: `bun run --filter '*' test` at the root, `bun run test`
in a package, and a Crucible tier verb are the same invocation shape; nothing in the client or the
stack needed to know the runner.

## 5. A note for CR-MDB-074 (no new type)

CR-MDB-074's `frontend` services skill parameterises the dev-server command, its ready pattern,
the page URLs, a production instance to protect, Lavish, and the teardown order. A Wails project
fits every slot: command `wails dev` (it runs `frontend:dev:watcher` itself), the frontend served
*with* Go bindings on a browser URL (Wails' default `:34115`), production instance = the installed
binary. One shape detail for 074's spec, measured against `wails.json`: `frontend:dev:serverUrl`
is `auto`, so the port is not in a config-file key but on the command (`wails dev -devserver
host:port`). The spec's "config file and key holding the port" should admit a port that the
dev-server command itself pins. Nothing else.

## 6. Proposed CR set, in dependency order

| Step | Owner | CR (working title) | Depends on | Size |
|---|---|---|---|---|
| 1 | Model B | **Rulings R1–R2 recorded** (queue footer / DN entry, as the vscode ruling was) | — | — |
| 2 | Crucible | **`go-crucible.py`**: client, `go` manifest key, stack stamp, compile decoder, coverprofile→lcov, `crucible-report-go` bundle + `references/go.md` | — | medium |
| 3 | Model B | **`bun.toml` generality** (§4) | — | small; independent of 2 |
| 4 | Model B | **`go` stack** — CR-MDB-024's shape (§3.2–§3.3), incl. the per-section triage and "tell Crucible" | 2 | medium |
| 5 | Model B | **CR-MDB-074 note** folded into its spec before its gap analysis runs (it is PENDING) | — | a sentence |
| 6 | Project | Arduino App Lab's own Bun migration — **done 2026-10-18** (`CR-AAL-001`–`004`) | — | — |
| 7 | Both | **Pilot** on a fork: `modelb-axi init --stacks go,bun`, `PROJECT_TYPE=frontend`; render the 8 agents; one RED→GREEN→VERIFY cycle on a pure Go package (`internal/emoji`, `internal/errors`, `internal/featureflags`) and one on a workspace package (`app/common`) through the board | 3, 4, 6 | the acceptance test for all of the above |

## 7. Non-goals

- No `vitest` stack, no `desktop` project type (both considered and withdrawn: the target state is
  Bun, and `frontend` covers the Wails dev loop).
- No change to the other four stacks' content; the `bun` change is content-only and keeps every
  runner-neutral rule.
- No Go analogue of `code-health` (`staticcheck` / `deadcode` / `govulncheck` under
  `deploy.STACK_SCOPED_BUNDLES`) in this set — a later CR once the stack is in use.
- No Playwright / e2e stack: `e2e` stays "unavailable until declared".
- No Wails v3 consideration (v2.13 in use; v3 is alpha).
- Nothing deployed to the project's upstream; the pilot runs on a fork.

## 8. Risks

- **Two owners, one sequence.** Step 4 is blocked on Crucible's step 2. File step 2 on the
  Crucible board first and record the dependency on both boards; §S5 "tell Crucible" closes the
  loop.
- **Go coverage shape** — client-side converter vs board codec; decide at step 2's gap analysis.
- **Multi-stack projects are new ground.** Every deployed project today names one stack; the
  pilot is where `PROJECT_STACKS=go,bun` is proven end to end — two clients, two hooks, two agent
  sets, one board project.
- **The pilot no longer waits on the project's migration** — it shipped the same day; both halves
  can be piloted together.

---

*Prepared from a read of `generator/stacks/*.toml`, `modelb_axi/{requirements,toolchains,scaffold,workflows,agents,deploy}.py`, `hooks-src/`, `skills-src/`, CR-MDB-024, CR-MDB-062, CR-MDB-074, the installed Crucible client fleet (`~/.crucible/clients/`, manifest 0.3.0 — in particular `bun-crucible.py`'s declared-target route) and the Arduino App Lab repository.*
