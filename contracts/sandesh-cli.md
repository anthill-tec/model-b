# Contract — Sandesh message-verb CLI

**Owner:** SANDESH project (upstream tool provider).
**Status:** DRAFTED — files with the SANDESH project when its mainline registers (routing
waits for the user; PRD §D8 non-goal: Model B does not send the register itself).

## Current state

- Sandesh is dual-surface today. The MCP server carries the message verbs for
  orchestrator sessions (`sandesh_send`, `sandesh_reply`, `sandesh_fetch`,
  `sandesh_inbox`, `sandesh_addressbook`, `sandesh_register`, `sandesh_unregister`,
  `sandesh_setup`, …).
- The standalone CLI (`sandesh --help`, observed in-session) already lists subcommands
  covering the full verb set — setup/projects/register/unregister/addressbook/send/reply/
  inbox/fetch/thread/notify/search/reindex plus admin grant/revoke/archive/unarchive/
  tombstone/init — with the wake watcher `notify` CLI-only by design (an MCP server
  cannot re-invoke a sleeping agent; the watcher blocks until To-addressed mail arrives).
- Semantics (per the model-b sandesh reference): `to=` wakes, `cc=` is silent,
  `to=["all-tracks"]` broadcasts; `fetch` = received/acting, `reply` = requested work
  done; addresses `Mainline - <Project>` / `Track N - <Project>`; `--project` is
  REQUIRED (a bare `sandesh notify --to …` exits 1 and silently never listens).

## Required surface

The message-verb CLI replacing MCP-only access — each verb non-interactive, addressable
by any orchestrator session without an MCP server in the loop:

| Verb | Requirement |
|---|---|
| `send` | addressed send with `kind` (request/directive), `to` (wakes) / `cc` (silent), all-tracks broadcast |
| `reply` | threaded reply under a message id; reply signals completion |
| `fetch` | consolidate + read unread mail (marks received/acting) |
| `inbox` | list a recipient's messages without consuming them |
| `addressbook` | roster + `active`/`listening` liveness (dispatch only to listening:true) |
| `register` | self-register an address |
| `unregister` | remove an address (Mainline: anyone; else: self) |

Already CLI (out of scope for this request): wake `notify`; admin `grant` / `revoke` /
`tombstone` / `archive` (+ `unarchive`, `init`).

## Sandesh 0.4.0 — what Model B relies on

- **Version floor.** Model B relies on the `sandesh` CLI 0.4.0 or later. The installer
  probes `sandesh --version` and reports an older CLI as `outdated` (remediation
  `uv tool upgrade sandesh-relay`); `@anthill-tec/sandesh-pi` 0.4.0 refuses an older CLI
  at session start.
- **Home view.** `sandesh status` reports the session's address, whether it is listening,
  and its unread count.
- **Machine output.** `--format toon` emits a toon envelope. Liveness is read from it —
  `sandesh addressbook --project <Project> --format toon --fields address,status,listening`
  — never from the human table.
- **The supervised watcher.** Only the extension, `@anthill-tec/sandesh-pi`, starts the
  supervised watcher; no CLI verb does. Its start, status and stop verbs default to
  `$SANDESH_ADDRESS` and `$SANDESH_PROJECT`; Model B passes both explicitly. Its
  `/sandesh-watcher` command offers status and stop. It arms itself at session start only
  under `SANDESH_AUTOSTART=1`, which Model B leaves unset: bootstrap starts the watcher.

The `notify` exit table as sandesh-pi's supervision treats each exit (`sandesh notify
--help` remains Sandesh's authority for the reasons):

| Exit | Reason | sandesh-pi's supervision |
|---|---|---|
| `0` | mail arrived | injects a turn naming the unread ids, then relaunches the watcher |
| `2` | timeout (no mail before the deadline) | relaunches the watcher silently, with no notice |
| `5` | already live elsewhere (dedup) | retries once; a second exit 5 in a row stops it quietly, with no notice |
| `1` | usage or configuration error | stops with a notice |
| `3` | tombstoned | stops with a notice |
| `4` | evicted | stops with a notice |
| `128+n` | killed by a signal | stops with a notice |

## Filed requests / gaps (dogfooding register)

### (a) Space-named project zombie defect (full AC'd request drafted 2026-07-20)
A zombie project is one that exists in the store but can never be retired:
`setup` accepts project ids that the address grammar rejects, producing a ZOMBIE project:
- `archive` requires action by the project's own Mainline — but that Mainline's address is
  grammar-invalid for a space-named project, so it can never act;
- `tombstone` requires the ARCHIVED state — unreachable per the above;
- jointly unsatisfiable: the project can be neither archived nor tombstoned.

Requested fix:
- **S1** — validate `project_id` at `setup` against the address grammar (reject at the
  door what the grammar cannot address later).
- **S2** — admin `tombstone` accepts zero-address projects WITHOUT the archive
  precondition; tolerant of missing store directories; idempotent; supports `--dry-run`.

### (b) No display-name UPDATE path
There is no way to update the display name of an active address: `register` rejects
duplicates, and `unregister` + re-`register` loses continuity. Requested: an update path
(re-register-in-place or a dedicated verb) for an active address.

### (c) `init --check` prints the admin name — harden
`init --check` reveals the ADMIN NAME to any local caller. Requested: harden — do not
disclose admin identity on an unauthenticated read-only check.
