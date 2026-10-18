# CR-MDB-080 — Go as a generated stack

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-18 into release 1.1.0, wave 3).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (generator, scaffold, installer, hooks, release workflow)
**Priority:** P2 — release 1.1.0, wave 3.
**Depends on:** Crucible's released `go-crucible.py` and its build-tag tiers (Crucible's CR-CRU-195 and
CR-CRU-196, in Crucible 0.4.0; not on this board), installed by the user; and CR-MDB-060 (where per-stack orchestration notes live) and CR-MDB-079 (what a stack file carries).
The board is authoritative: read `queue`, not this line.
**Labels:** generator, stacks, go, scaffold
**Design reference:** DN-multi-harness-deploy-model §D25 (and §D17, §D18); CR-MDB-024 (the shape a new
stack follows); `PROPOSAL-go-stack-and-bun-frontend-generality.md` §3.

## Context

Model B generates agents for five stacks: arduino, bun, python, quarkus and rust. A Go project has no
stack: no agents, no Crucible client, no blocking hook, no release test job. Arduino App Lab (a Go
backend in a Wails desktop shell, with a Bun frontend) is `PROJECT_STACKS=go,bun`; its frontend is the
existing bun stack, its Go half is uncovered. Crucible authors the client first; this CR adds the stack
on Model B's side once that client is released. The client runs `go test -json`, decodes on the server,
resolves the module dir from flag, environment, the project's `crucible.toml`, then the nearest `go.mod`,
and declares a tier by the build tag of the same name.

## Scope (seed)

1. **`generator/stacks/go.toml`** in the shape the other stacks establish, `tier_guidance` included:
   what holds for any Go project (the `testing` package, subtests, build tags as the integration
   boundary, more than one `go.mod`, generated code never hand-edited, the read-only VERIFY tools).
   No framework guidance: Wails and the project's architecture stay in the project.
2. **Every place a stack lives:** the client key and the toolchain probes in `requirements.py`, the
   stack lists in `scaffold.py`, `agents.py` and `cli.py`, the release workflow's test part and its
   pinned setup action, and the census gates that count stacks, agents, bundles and hooks.
3. **A blocking hook** for direct Go test runs, on the convention the other four runner hooks share.
4. **The `crucible-report-go` bundle and the `crucible` skill's `references/go.md`,** authored by Model B
   from the released client's `--help` and envelopes. Model B owns every skill bundle in full; the six
   in `CRUCIBLE-HANDOVER.md` were imported once and are maintained here, and a new one is written here.
5. **The four go agents generated,** and a sandboxed `init --stacks go` (and `go,bun`) rendering them,
   the hook and the test job.

## To measure at gap analysis

- The released client's verbs, flags and manifest key, from its `--help` and envelopes.
- Whether the integration tier needs a project-declared backend, brought up by the project's own
  services (§D25).
- The live check: the go agents' RED → GREEN on a Go module through the released client.
- The re-score.
