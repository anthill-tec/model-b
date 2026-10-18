# CR-MDB-080 — Go as a generated stack

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-18 into release 1.1.0, wave 3).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (generator, scaffold, installer, hooks, release workflow)
**Priority:** P2 — release 1.1.0, wave 3.
**Depends on:** Crucible's released `go-crucible.py` (Crucible's to author; not on this board), and
CR-MDB-060 (where per-stack orchestration notes live) and CR-MDB-079 (what a stack file carries).
The board is authoritative: read `queue`, not this line.
**Labels:** generator, stacks, go, scaffold
**Design reference:** DN-multi-harness-deploy-model §D25 (and §D17, §D18); CR-MDB-024 (the shape a new
stack follows); `PROPOSAL-go-stack-and-bun-frontend-generality.md` §3.

## Context

Model B generates agents for five stacks: arduino, bun, python, quarkus and rust. A Go project has no
stack: no agents, no Crucible client, no blocking hook, no release test job. Arduino App Lab (a Go
backend in a Wails desktop shell, with a Bun frontend) is `PROJECT_STACKS=go,bun`; its frontend is the
existing bun stack, its Go half is uncovered. Crucible authors the client first; this CR adds the stack
on Model B's side once that client is released.

## Scope (seed)

1. **`generator/stacks/go.toml`** in the shape the other stacks establish, `tier_guidance` included:
   what holds for any Go project (the `testing` package, subtests, build tags as the integration
   boundary, more than one `go.mod`, generated code never hand-edited, the read-only VERIFY tools).
   No framework guidance: Wails and the project's architecture stay in the project.
2. **Every place a stack lives:** the client key and the toolchain probes in `requirements.py`, the
   stack lists in `scaffold.py`, `agents.py` and `cli.py`, the release workflow's test part and its
   pinned setup action, and the census gates that count stacks, agents, bundles and hooks.
3. **A blocking hook** for direct Go test runs, on the convention the other four runner hooks share.
4. **The `crucible-report-go` bundle and its reference,** imported byte-identical from Crucible, with
   the handover record updated.
5. **The four go agents generated,** and a sandboxed `init --stacks go` (and `go,bun`) rendering them,
   the hook and the test job.

## To measure at gap analysis

- The released client's verbs, flags and manifest key, from its `--help` and envelopes.
- Whether the integration tier needs a project-declared backend, brought up by the project's own
  services (§D25).
- The live check: the go agents' RED → GREEN on a Go module through the released client.
- The re-score.
