// CR-CRU-008 C6 — clients/skills/* fleet contract (RED).
//
// Spec: docs/changes/CR-CRU-008-cli-fleet-upgrade.md — §S3 Skill fleet
// upgrade (`~/.claude/skills/`): `crucible-register`, `crucible-report-
// {rust,java,python,bun,vscode}`, `agent-protocol` (+ its `heartbeat.sh`):
// v2 endpoints, context fields, TOON-aware examples, removal of the
// dedicated-ping guidance (ingest is the heartbeat). Plus the AC: "Skill
// docs contain no `POST /api/agents/heartbeat` legacy references except in
// an explicit 'legacy/shim' note; `heartbeat.sh` targets
// `/api/v2/agents/heartbeat`." Plus the Risk section: fleet edits live
// OUTSIDE this repo (`~/.claude`) — each upgrade is committed in THIS repo
// under `clients/` as the source of truth (synced to `~/.claude` by an
// install step per CR-CRU-009); VERIFY tests run against `clients/` copies.
//
// RED phase: `clients/skills/` does not exist AT ALL on this branch yet —
// only the LIVE v1 copies at `~/.claude/skills/` exist (surveyed directly
// below; every one of them references v1 endpoints only: `/api/ingest`,
// `/api/ingest/parsed`, `/api/ingest/compile`, `/api/agents/heartbeat`,
// `/api/agents/remove`, `/api/events*`, `/api/projects`; `crucible-register`
// carries a dedicated "Heartbeat (every 5 minutes)" ping section;
// `agent-protocol` carries "send explicit heartbeats" guidance;
// `heartbeat.sh` posts to `$SERVICE_URL/api/agents/heartbeat`). Every test
// below fails because `clients/skills/**` is missing — `existsSync` is
// false / `readFileSync` throws ENOENT. That is expected RED.
//
// v2 route ground truth (read directly from src/v2.ts's routing table, not
// assumed): POST /api/v2/agents/register, POST /api/v2/agents/heartbeat
// (same handler, handleAgentTouch), POST /api/v2/agents/unregister,
// GET /api/v2/agents, POST /api/v2/runs, POST /api/v2/runs/parsed,
// POST /api/v2/runs/compile, GET /api/v2/events, GET/POST /api/v2/projects.
import { afterEach, describe, expect, test } from "bun:test";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { startServer } from "../src/server.ts";

const REPO_ROOT = join(import.meta.dir, "..");
const SKILLS_DIR = join(REPO_ROOT, "clients", "skills");

const PATHS = {
  register: join(SKILLS_DIR, "crucible-register", "SKILL.md"),
  reportRust: join(SKILLS_DIR, "crucible-report-rust", "SKILL.md"),
  reportJava: join(SKILLS_DIR, "crucible-report-java", "SKILL.md"),
  reportPython: join(SKILLS_DIR, "crucible-report-python", "SKILL.md"),
  reportBun: join(SKILLS_DIR, "crucible-report-bun", "SKILL.md"),
  reportVscode: join(SKILLS_DIR, "crucible-report-vscode", "SKILL.md"),
  agentProtocol: join(SKILLS_DIR, "agent-protocol", "SKILL.md"),
  heartbeatSh: join(SKILLS_DIR, "agent-protocol", "scripts", "heartbeat.sh"),
} as const;

const ALL_FILES: ReadonlyArray<{ label: string; path: string }> = [
  { label: "crucible-register/SKILL.md", path: PATHS.register },
  { label: "crucible-report-rust/SKILL.md", path: PATHS.reportRust },
  { label: "crucible-report-java/SKILL.md", path: PATHS.reportJava },
  { label: "crucible-report-python/SKILL.md", path: PATHS.reportPython },
  { label: "crucible-report-bun/SKILL.md", path: PATHS.reportBun },
  { label: "crucible-report-vscode/SKILL.md", path: PATHS.reportVscode },
  { label: "agent-protocol/SKILL.md", path: PATHS.agentProtocol },
  { label: "agent-protocol/scripts/heartbeat.sh", path: PATHS.heartbeatSh },
];

function readSkill(path: string): string {
  if (!existsSync(path)) {
    throw new Error(
      `Expected clients/skills fleet file to exist at ${path} — CR-CRU-008 §S3 ` +
        `upgrade (clients/skills/* as the in-repo source of truth) has not landed yet (RED).`,
    );
  }
  return readFileSync(path, "utf-8");
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Matches `pattern` as a whole path token — not merely a prefix of a longer
 * path segment. E.g. "/api/v2/runs" must NOT match inside
 * "/api/v2/runs/parsed"; it must appear on its own (followed by whitespace,
 * quote, backtick, end-of-line, etc).
 */
function containsExact(content: string, pattern: string): boolean {
  const re = new RegExp(`${escapeRegex(pattern)}(?![\\w/-])`, "i");
  return re.test(content);
}

const LEGACY_MARKER = /legacy|shim/i;

const V1_PATTERNS: ReadonlyArray<{ name: string; regex: RegExp }> = [
  { name: "/api/ingest", regex: /\/api\/ingest\b/i },
  { name: "/api/agents/heartbeat", regex: /\/api\/agents\/heartbeat\b/i },
  { name: "/api/agents/remove", regex: /\/api\/agents\/remove\b/i },
  { name: "/api/projects/add", regex: /\/api\/projects\/add\b/i },
  { name: "/api/events (non-v2)", regex: /\/api\/events\b/i },
];

/**
 * Per-line scan for v1 endpoint strings NOT accompanied by an explicit
 * "legacy"/"shim" note within a `windowSize`-line lookback (covers a
 * markdown heading/note sitting above a fenced code block, or an inline
 * annotation on the same line). Per AC: "Skill docs contain no
 * `POST /api/agents/heartbeat` legacy references except in an explicit
 * 'legacy/shim' note." None of the v1 patterns here can accidentally match
 * inside a v2 URL — every v2 route inserts a `/v2/` segment right after
 * `/api/`, so e.g. "/api/v2/events" never contains "/api/events" as a
 * contiguous substring.
 */
function findUnmarkedLegacyReferences(
  content: string,
  windowSize = 15,
): Array<{ line: number; text: string; pattern: string }> {
  const lines = content.split("\n");
  const violations: Array<{ line: number; text: string; pattern: string }> = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    for (const pat of V1_PATTERNS) {
      if (pat.regex.test(line)) {
        const windowStart = Math.max(0, i - windowSize);
        const nearby = lines.slice(windowStart, i + 1).join("\n");
        if (!LEGACY_MARKER.test(nearby)) {
          violations.push({ line: i + 1, text: line.trim(), pattern: pat.name });
        }
      }
    }
  }
  return violations;
}

// ── 1. Existence — all eight files must exist under clients/skills/ ────────

describe("clients/skills fleet — file existence (CR-CRU-008 §S3, Risk: clients/ is source of truth)", () => {
  for (const { label, path } of ALL_FILES) {
    test(`${label} exists under clients/skills/`, () => {
      expect(existsSync(path)).toBe(true);
    });
  }
});

// ── 2. v2 endpoint references — positive pins per skill's documented verbs ──

describe("clients/skills — v2 endpoint references (mapping table)", () => {
  test("crucible-register/SKILL.md references v2 register/unregister + the full runs/events/projects appendix it currently carries", () => {
    const content = readSkill(PATHS.register);
    for (const ep of [
      "/api/v2/agents/register",
      "/api/v2/agents/unregister",
      "/api/v2/runs",
      "/api/v2/runs/parsed",
      "/api/v2/runs/compile",
      "/api/v2/events",
      "/api/v2/projects",
    ]) {
      expect(containsExact(content, ep)).toBe(true);
    }
  });

  test("crucible-report-rust/SKILL.md references v2 runs (raw/parsed/compile) + agents + events + projects", () => {
    const content = readSkill(PATHS.reportRust);
    for (const ep of [
      "/api/v2/runs",
      "/api/v2/runs/parsed",
      "/api/v2/runs/compile",
      "/api/v2/agents/register",
      "/api/v2/agents/unregister",
      "/api/v2/events",
      "/api/v2/projects",
    ]) {
      expect(containsExact(content, ep)).toBe(true);
    }
  });

  test("crucible-report-java/SKILL.md references v2 runs (raw/parsed/compile) + agents + events + projects", () => {
    const content = readSkill(PATHS.reportJava);
    for (const ep of [
      "/api/v2/runs",
      "/api/v2/runs/parsed",
      "/api/v2/runs/compile",
      "/api/v2/agents/register",
      "/api/v2/agents/unregister",
      "/api/v2/events",
      "/api/v2/projects",
    ]) {
      expect(containsExact(content, ep)).toBe(true);
    }
  });

  test("crucible-report-bun/SKILL.md references v2 runs (raw/parsed/compile) + agents + events + projects", () => {
    const content = readSkill(PATHS.reportBun);
    for (const ep of [
      "/api/v2/runs",
      "/api/v2/runs/parsed",
      "/api/v2/runs/compile",
      "/api/v2/agents/register",
      "/api/v2/agents/unregister",
      "/api/v2/events",
      "/api/v2/projects",
    ]) {
      expect(containsExact(content, ep)).toBe(true);
    }
  });

  test("crucible-report-vscode/SKILL.md references v2 runs (raw/parsed/compile) + agents + events + projects", () => {
    const content = readSkill(PATHS.reportVscode);
    for (const ep of [
      "/api/v2/runs",
      "/api/v2/runs/parsed",
      "/api/v2/runs/compile",
      "/api/v2/agents/register",
      "/api/v2/agents/unregister",
      "/api/v2/events",
      "/api/v2/projects",
    ]) {
      expect(containsExact(content, ep)).toBe(true);
    }
  });

  // python's CURRENT doc documents no /api/events section at all (surveyed:
  // its "API endpoint reference" table has no events row) — do not require it.
  test("crucible-report-python/SKILL.md references v2 runs (raw/parsed/compile) + agents + projects", () => {
    const content = readSkill(PATHS.reportPython);
    for (const ep of [
      "/api/v2/runs",
      "/api/v2/runs/parsed",
      "/api/v2/runs/compile",
      "/api/v2/agents/register",
      "/api/v2/agents/unregister",
      "/api/v2/projects",
    ]) {
      expect(containsExact(content, ep)).toBe(true);
    }
  });

  test("agent-protocol/SKILL.md references /api/v2/agents/heartbeat", () => {
    const content = readSkill(PATHS.agentProtocol);
    expect(containsExact(content, "/api/v2/agents/heartbeat")).toBe(true);
  });

  test("agent-protocol/scripts/heartbeat.sh targets /api/v2/agents/heartbeat (string pin)", () => {
    const content = readSkill(PATHS.heartbeatSh);
    expect(containsExact(content, "/api/v2/agents/heartbeat")).toBe(true);
  });
});

// ── 3. Legacy carve-out — v1 endpoint strings only inside an explicit
//       "legacy"/"shim" note; everywhere else must be gone. ─────────────────

describe("clients/skills — no unmarked v1 legacy endpoint references (AC: legacy/shim carve-out only)", () => {
  for (const { label, path } of ALL_FILES) {
    test(`${label}: every v1 endpoint string is either absent or sits inside a legacy/shim note`, () => {
      const content = readSkill(path);
      const violations = findUnmarkedLegacyReferences(content);
      expect(violations).toEqual([]);
    });
  }
});

// ── 4. Dedicated-ping guidance removed — "ingest is the heartbeat" ──────────

describe("clients/skills — dedicated-ping guidance removed (ingest is the heartbeat)", () => {
  test("crucible-register/SKILL.md drops the 'every 5 minutes' dedicated-ping heading and states ingest is the heartbeat", () => {
    const content = readSkill(PATHS.register);
    expect(content).not.toMatch(/every\s+5\s+minutes/i);
    expect(content).not.toMatch(/send explicit heartbeats?/i);
    expect(content).toMatch(/ingest is the heartbeat/i);
  });

  test("agent-protocol/SKILL.md drops the 'send explicit heartbeats' guidance and states ingest is the heartbeat", () => {
    const content = readSkill(PATHS.agentProtocol);
    expect(content).not.toMatch(/send explicit heartbeats?/i);
    expect(content).toMatch(/ingest is the heartbeat/i);
  });
});

// ── 5. Tier + WORKFLOW_CYCLE (no WORKFLOW_CYCLE_ID — removed in CR-036) ─────

describe("clients/skills — tier + WORKFLOW_CYCLE (no WORKFLOW_CYCLE_ID — removed in CR-036) documented", () => {
  const reportSkills: ReadonlyArray<{ label: string; path: string }> = [
    { label: "crucible-report-rust", path: PATHS.reportRust },
    { label: "crucible-report-java", path: PATHS.reportJava },
    { label: "crucible-report-python", path: PATHS.reportPython },
    { label: "crucible-report-bun", path: PATHS.reportBun },
    { label: "crucible-report-vscode", path: PATHS.reportVscode },
  ];

  for (const { label, path } of reportSkills) {
    test(`${label}/SKILL.md mentions tier and WORKFLOW_CYCLE, but never the removed WORKFLOW_CYCLE_ID`, () => {
      const content = readSkill(path);
      expect(content).toMatch(/\btier\b/i);
      // WORKFLOW_CYCLE_ID was removed in CR-036 (server auto-attaches the
      // cycle) — regression guard that it never reappears in the docs.
      expect(content).not.toContain("WORKFLOW_CYCLE_ID");
      // WORKFLOW_CYCLE (the label string → context.cycle) as its OWN token —
      // still a valid, documented env var.
      expect(content).toMatch(/WORKFLOW_CYCLE(?!_ID)\b/);
    });
  }
});

// ── 6. Example commands use the C2-C4 clients' real script paths + the
//       same subcommand names those upgraded clients expose. ──────────────

function scriptSubcommandPin(content: string, scriptPath: string, subcommands: string[]): boolean {
  if (!content.includes(scriptPath)) return false;
  return subcommands.some((sc) => content.includes(`${scriptPath} ${sc}`));
}

describe("clients/skills — example commands use the C2-C4 clients' real script paths + subcommands", () => {
  test("crucible-report-rust/SKILL.md examples invoke clients/rust-crucible.py with a real subcommand", () => {
    const content = readSkill(PATHS.reportRust);
    expect(
      scriptSubcommandPin(content, "clients/rust-crucible.py", [
        "register",
        "unregister",
        "test",
        "auto-ingest",
        "regression-ingest",
        "check",
      ]),
    ).toBe(true);
  });

  test("crucible-report-java/SKILL.md examples invoke clients/mvn-crucible.py with a real subcommand", () => {
    const content = readSkill(PATHS.reportJava);
    expect(
      scriptSubcommandPin(content, "clients/mvn-crucible.py", [
        "register",
        "unregister",
        "unit",
        "module",
        "e2e",
        "regression",
        "compile",
        "auto-ingest",
      ]),
    ).toBe(true);
  });

  test("crucible-report-python/SKILL.md examples invoke clients/python-crucible.py with a real subcommand", () => {
    const content = readSkill(PATHS.reportPython);
    expect(
      scriptSubcommandPin(content, "clients/python-crucible.py", [
        "register",
        "unregister",
        "test",
        "regression",
        "auto-ingest",
        "check",
      ]),
    ).toBe(true);
  });

  test("crucible-report-bun/SKILL.md examples invoke clients/bun-crucible.py with a real subcommand", () => {
    const content = readSkill(PATHS.reportBun);
    expect(
      scriptSubcommandPin(content, "clients/bun-crucible.py", [
        "register",
        "unregister",
        "test",
        "regression",
        "auto-ingest",
        "check",
      ]),
    ).toBe(true);
  });

  // vscode has NO upgraded *-crucible.py client (Non-goals: "VS Code script
  // (no v1 script exists — skill-only update)") — its canonical example
  // instead calls the v2 runs endpoint directly.
  test("crucible-report-vscode/SKILL.md (no CLI client — Non-goals) examples call /api/v2/runs/parsed directly", () => {
    const content = readSkill(PATHS.reportVscode);
    expect(containsExact(content, "/api/v2/runs/parsed")).toBe(true);
  });
});

// ── 7. heartbeat.sh — live spawn: v2 heartbeat auto-registers the agent ─────

describe("clients/skills/agent-protocol/scripts/heartbeat.sh — live spawn (v2 auto-register)", () => {
  let handle: ReturnType<typeof startServer> | undefined;

  afterEach(() => {
    handle?.stop();
    handle = undefined;
  });

  test("spawning heartbeat.sh against a live v2 server registers the agent (GET /api/v2/agents lists it)", async () => {
    handle = startServer({ port: 0, dbPath: ":memory:" });
    const baseUrl = `http://localhost:${handle.server.port}`;

    const createRes = await fetch(`${baseUrl}/api/v2/projects`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name: "heartbeat-sh-live-spawn" }),
    });
    const created = (await createRes.json()) as { project: { key: string } };
    const projectKey = created.project.key;

    // Would fail against a no-op stub too: `clients/skills/agent-protocol/
    // scripts/heartbeat.sh` does not exist yet on this branch (RED) — bash
    // exits non-zero for "No such file", the agent is never touched, and
    // the assertion below on GET /api/v2/agents fails for the right reason.
    const proc = Bun.spawn({
      cmd: [
        "bash",
        PATHS.heartbeatSh,
        "hb-live-agent-1",
        projectKey,
        "online",
        "heartbeat.sh live spawn RED probe",
        baseUrl,
      ],
      stdout: "pipe",
      stderr: "pipe",
    });
    await proc.exited;

    const agentsRes = await fetch(`${baseUrl}/api/v2/agents?project=${projectKey}`);
    const agentsBody = (await agentsRes.json()) as { agents: Array<{ agentId: string }> };
    expect(agentsBody.agents.map((a) => a.agentId)).toContain("hb-live-agent-1");
  });
});
