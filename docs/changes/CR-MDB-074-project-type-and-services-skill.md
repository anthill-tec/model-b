# CR-MDB-074 — The project type, and a generated services skill for frontend projects

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-15 into release 1.1.0, wave 3).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (project schema, scaffold, a generated skill)
**Priority:** P2 — release 1.1.0, wave 3.
**Depends on:** CR-MDB-061 (the global Chrome-UI skill it calls), CR-MDB-050 (`init` and the
schema) and CR-MDB-055 (`migrate`). The board is authoritative: read `queue`, not this line.
**Labels:** scaffold, schema, skills, frontend
**Design reference:** DN-multi-harness-deploy-model §D23, §D25; PRD D3.1 (the schema-driven registry);
Crucible #1456–#1458.

## Context

Crucible keeps a hand-written project skill that brings its services up at `/bootstrap` and down at
`/shutdown`. CR-MDB-061 takes the browser half global. The rest is project-specific: a dev server,
its pages, Lavish sessions, and a production instance to leave alone. For a frontend project
(a node or bun server with a browser UI, alongside Lavish design docs), Model B generates that skill
from project parameters. A backend project writes its own, by hand, and Model B never touches it.
Whatever the type, the generated skill starts one dev server: a project's other services — its own
backends, services it consumes, the backends its integration tests need — are its own, declared by its
orchestrator and run by a Model B tool (DN §D25).

## Scope (seed)

1. **`PROJECT_TYPE`** in the project-settings schema: a description, the values `frontend` and
   `backend`, and its readers. `init` and `migrate` ask it.
2. **The generated services skill** goes into the project's skills folder, for `frontend` only,
   from project parameters asked at `init` or `migrate`:
   - **The dev server, one.** It runs under Pi's `process` tool with a ready pattern. The command
     and where the port comes from are parameters — a config file and key, or the command itself
     pinning it (a Wails project: `wails dev -devserver host:port`); the port is never hardcoded. It
     restarts after merges to develop. Crucible's: `bun run src/server.ts`, with the port at
     `data/crucible.toml` `[server] port`.
   - **The pages.** A UI URL template. Crucible's:
     `http://127.0.0.1:<port>/p/<CRUCIBLE_PROJECT_KEY>/roadmap`.
   - **Lavish.** One session per design artifact, taking each printed `url:`, plus one supervised
     `lavish-axi poll` on the primary artifact (reply and re-arm in one call).
   - **Other.**
     - Any production instance to leave alone; its port becomes a protected tab pattern for
       CR-MDB-061's skill.
     - The orchestrator's board registration.
   - **Tabs.** It calls CR-MDB-061's global Chrome-UI skill for every tab.
   - **Teardown order.** Close the tabs before stopping Lavish, because a stopped Lavish server
     makes its tabs unrecognisable. Then stop the poll and the Lavish server, and stop the dev
     server last.
3. **`bootstrap` and `shutdown`** start and stop a project's services, of either type: the generated
   skill's dev server, and the project's declared dependency services through the tool of item 4.
4. **Declared dependency services, and the scripts that run them** — in every project, of either
   type: nearly every project has dependency services to bring up, so bootstrap and shutdown always
   run the start and stop steps, and an empty section starts nothing. A section of the project's
   configuration where its orchestrator declares each service the project depends on — its own
   backends, services it consumes, the backends its integration tests need — with a description of
   what it is for and the commands (or the described action) that start and stop it. Model B utility
   scripts register a service, remove one, and run the declared start and stop sequences; bootstrap and
   shutdown call them, and the orchestrator registers and removes services through them at any point
   in the project's life. The scripts are generic and Model B's, but live in the project's own folder:
   `init` drops them in at scaffold time, beside the configuration section, created empty. The
   project's rendered permission policy allows them by path, so starting, stopping, registering and
   removing services asks no permission and no global allowance is widened. An
   orchestrator rule: the project's Mainline maintains the declarations; no project's service is named
   in a shared skill, stack, template or tool.
5. **Re-generation.** `migrate` (and a re-run of `init`, per CR-MDB-050) regenerates a frontend
   project's services skill from its parameters, and drops in or updates Model B's service scripts in
   an existing project, never touching its declarations. Crucible will regenerate its own this way and
   retire its hand-written one.

## To measure at gap analysis

- Where the parameters live: the registry, a project file, or the skill's own front matter. Which
  of them are secrets or local-only (`.env.local`)?
- The project skills folder Pi loads, and how a generated skill is marked as owned by Model B
  (the first-line ownership marker) so that hand edits are detected, not clobbered.
- How a backend project's hand-written services skill is told apart, so the scaffold never touches
  it.
- Where the declarations live (the registry, `crucible.toml`, a project file of their own), their
  shape (description, start and stop commands or a described action, readiness, order and dependencies
  between services, local-only values), the scripts' register and remove verbs, and how they report a
  service that fails to start or stop.
- Where in the project the scripts go, how they are marked as Model B's so a hand edit is detected and
  never clobbered, and how `init` and `migrate` keep them current.
- How the rendered permission policy names the scripts (CR-MDB-077's re-render, CR-MDB-049's strict
  policy), and that a run of each verb raises no prompt.
- A project that kept hand-written service skills before this CR (Crucible's): how it moves to
  declarations.
- The re-score.
