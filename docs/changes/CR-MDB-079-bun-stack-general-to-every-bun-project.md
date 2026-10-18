# CR-MDB-079 — The bun stack is general to every Bun project

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-18 into release 1.0.0, wave 2).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** fix (generator stack content)
**Priority:** P1 — release 1.0.0, wave 2; before CR-MDB-052.
**Depends on:** nothing on the board (board-authoritative: read `queue`).
**Labels:** generator, stacks, bun
**Design reference:** DN-multi-harness-deploy-model §D25.

## Context

`generator/stacks/bun.toml` was distilled from the Sandesh Pi-extension agents and never made
general. About 30 of its 99 lines describe one project's architecture: a thin TypeScript shim that
shells to the `sandesh` CLI, `pi.exec` and `registerTool` mocks, exact `sandesh` argv assertions, the
tool-parameter → CLI-flag mapping table, TypeBox schemas, Sandesh-core's purity, the Pi extension API
sources, and `integrations/pi/` as the default package dir. They sit in `mechanics` and in every role's
`gotchas`.

Every project with `bun` in `PROJECT_STACKS` gets the four bun agents rendered from it. Crucible
(`bun,python`) runs them today, so its RED agent is told to mock `pi.exec` and assert `sandesh` argv.
A new frontend project (Arduino App Lab, `go,bun`) would get the same.

The stack also presumes Bun's own test runner ("Bun's test runner", `bun:test` imports). A Bun project
may declare another runner on the Bun runtime: Arduino App Lab runs Vitest under Bun in its packages and
keeps `bun test` for structural gates only.

## Scope (seed)

1. **`bun.toml` carries only what holds for every Bun project:** the client verbs and their known gaps,
   running in the package dir of a Bun workspace (the dir is the project's, through the client's
   package-dir setting, with no default naming one project), the `check` typecheck gate, tiers from
   the scripts the project declares, a workspace package as the `module` tier, generated files never
   hand-edited, and the runner-neutral quality rules (`strict`, no `any`, no `.only`, the test count
   moves).
2. **Runner-neutral:** tests use the runner the project declares (`bun test`, or another runner such
   as Vitest on the Bun runtime) and import from it; the stack presumes neither.
3. **Bun runtime facts every Bun project meets:**
   - Bun reads `bunfig.toml` from the current directory only, so a root `[run] bun = true` does not
     reach a package-local run: confirm a package's runs execute on Bun, not on a system Node.
   - Bun links ES modules strictly: a named import the module does not export fails at link time
     (other runtimes yield `undefined`), and such a failure is a real defect, not a runner quirk — a
     VERIFY and FIX heuristic.
4. **No framework, test library or project architecture in it:** no React, DOM environment, Testing
   Library or MSW guidance, and none of Sandesh's shim text. Sandesh's text leaves Model B; it goes
   into no memory template.
5. **The four bun agents are regenerated** (`generator/build.py build`), and a guard keeps
   project-specific terms out of the stack file.
6. **Projects re-render** their bun agents with `modelb-axi agents` after the release. Sandesh and
   Crucible are told before the merge, so Sandesh keeps its specifics in its own project first.

## To measure at gap analysis

- Which tests pin the current `bun.toml` text, and which shipped-text gates (the registry-key
  detector included) the rewritten text meets.
- What Sandesh's own project already holds of the removed text, and what it must add.
- What Crucible's bun client offers for a targeted run under a project-declared runner, and with no
  project-specific default package dir (requested of Crucible 2026-10-18); the text states the client
  as released.
- The re-score.
