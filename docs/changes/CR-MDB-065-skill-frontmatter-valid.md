# CR-MDB-065 — Skill frontmatter parses, and stays within Pi's limits

**Status:** PENDING — **SEED, not the finished spec.** Gap analysis, the design record, the spec and
its pre-review happen in order when this CR starts.
**Type:** fix (skill metadata, guard test)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-056 (it edits the same skills; board-authoritative: read `queue`)
**Labels:** skills, frontmatter, pi, guard
**Design reference:** Pi's skill loader's frontmatter rules, as Pi reports them; DN-multi-harness-deploy-model
§D18 (skills are the shared surface).

## Context

Pi reports three of Model B's deployed skills as conflicts (2026-10-13):
- `~/.agents/skills/cr-authoring/SKILL.md` and `~/.agents/skills/model-b/SKILL.md`: "Nested mappings
  are not allowed in compact mappings at line 2, column 14" — each `description` is an unquoted
  YAML plain scalar containing `: ` (measured in `skills-src/`: `cr-authoring` and `model-b` are the
  only two);
- `~/.agents/skills/shutdown/SKILL.md`: "description exceeds 1024 characters (1206)" (the only one
  over; `bootstrap` 851 and `code-health` 856 are the next longest).

The deployed copies equal `skills-src/`, so the defects are in the source.

## Scope (seed)

1. **The two descriptions parse:** `cr-authoring`'s and `model-b`'s `description` are written so YAML
   reads one string (quoted, or reworded without `: `).
2. **`shutdown`'s description is at most 1024 characters**, keeping what a model needs to decide when
   to load the skill.
3. **A guard test** over every `skills-src/*/SKILL.md` (and every frontmatter Model B renders — the
   generated agent definitions): the frontmatter parses as YAML the way Pi reads it — `name` and
   `description` are single strings — and `description` is at most 1024 characters. Measure how to
   check "parses" with the stdlib only (Model B has no YAML dependency): a conservative rule (a plain
   scalar has no `: ` and no ` #`, or the value is quoted) proved on samples both ways.
4. **The user redeploys** after merge (`modelb-axi --reinstall …`); the conflicts clear.

## To measure at gap analysis

- Pi's exact limits and parser behaviour (its error texts are the evidence), and whether `name` has
  rules too (length, characters).
- Whether the imported/other bundles' extra `metadata` keys are read by Pi.
