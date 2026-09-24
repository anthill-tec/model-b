#!/usr/bin/env node
// Test-only fixture (CR-MDB-029 §S2) — NOT production code. It loads
// `pi-package/extensions/sandesh-watcher.ts` with the jiti mechanism Pi's
// own loader uses (`jiti.import(path, { default: true })` and the same
// module aliases Pi's `getAliases()` gives an unbundled Node install). It
// calls the factory with a recording fake `pi`, then runs a JSON step
// script from stdin against the registered tool and command.
//
// argv: <extensionPath> <jitiMjsPath> <piPackageRoot>
// stdin: JSON {
//   "fakeClock": bool,          // install a Date.now offset BEFORE load
//   "fakeDir": string,          // the fake sandesh's state dir (launches.log)
//   "markerPath": string|null,  // sampled when each tool call resolves
//   "steps": [ {op: ...}, ... ]
// }
// ops:
//   {"op":"tool", "params":{...}, "timeoutMs":8000}
//   {"op":"command", "name":"watcher", "args":"status", "timeoutMs":8000}
//   {"op":"sleep", "ms":N}
//   {"op":"advanceClock", "ms":N}           // needs fakeClock
//   {"op":"touch", "path":P}
//   {"op":"waitUntil", "launches":N?, "surfaced":N?, "userMessages":N?, "timeoutMs":N}
//   {"op":"waitPidDead", "launch":N, "timeoutMs":N}  // 1-based launch index
//   {"op":"snapshot", "label":S}
// stdout: one JSON object, always. Every path reaches an explicit
// process.exit(): Pi's loader and the spawned children keep Node's event
// loop alive, so nothing may be left to end on its own.

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";

const out = {
  defaultIsFunction: false,
  importError: null,
  tools: [],
  toolParameters: {},
  commands: [],
  userMessages: [],
  messages: [],
  notifies: [],
  steps: [],
  snapshots: {},
  launches: [],
  harnessError: null,
};

let fakeDir = null;

function launchPids() {
  if (!fakeDir) return [];
  const log = path.join(fakeDir, "launches.log");
  if (!existsSync(log)) return [];
  return readFileSync(log, "utf-8").split("\n").filter((l) => l.trim()).map((l) => Number(l.trim()));
}

function killAllFakes() {
  for (const pid of launchPids()) {
    try { process.kill(pid, "SIGKILL"); } catch { /* already gone */ }
  }
}

function emit(code = 0) {
  out.launches = launchPids();
  killAllFakes();
  process.stdout.write(JSON.stringify(out));
  process.exit(code);
}

function textOf(content) {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content.map((p) => (p && typeof p.text === "string" ? p.text : JSON.stringify(p))).join("\n");
  }
  return JSON.stringify(content);
}

function surfacedCount() {
  return out.userMessages.length + out.messages.length + out.notifies.length;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function pidAlive(pid) {
  try { process.kill(pid, 0); return true; } catch { return false; }
}

function noopProxy(target) {
  return new Proxy(target, {
    get(t, k) {
      if (k in t) return t[k];
      if (k === "then") return undefined;
      return () => undefined;
    },
  });
}

async function withTimeout(promiseFactory, ms) {
  let timer;
  const timeout = new Promise((resolve) => {
    timer = setTimeout(() => resolve({ timedOut: true }), ms);
  });
  const run = (async () => {
    try {
      const value = await promiseFactory();
      return { value };
    } catch (err) {
      return { threw: err instanceof Error ? err.message : String(err) };
    }
  })();
  const res = await Promise.race([run, timeout]);
  clearTimeout(timer);
  return res;
}

async function main() {
  const [, , extPath, jitiMjsPath, piPkgRoot] = process.argv;
  if (!extPath || !jitiMjsPath || !piPkgRoot) {
    process.stderr.write("usage: pi_watcher_harness.mjs <extensionPath> <jitiMjsPath> <piPackageRoot>\n");
    process.exit(2);
  }
  const scenario = JSON.parse(readFileSync(0, "utf-8") || "{}");
  fakeDir = scenario.fakeDir ?? null;

  let clockOffset = 0;
  if (scenario.fakeClock) {
    const realNow = Date.now.bind(Date);
    Date.now = () => realNow() + clockOffset;
  }

  // The same aliases Pi's loader gives an unbundled Node install
  // (dist/core/extensions/loader.js getAliases()).
  const req = createRequire(path.join(piPkgRoot, "package.json"));
  const alias = { "@earendil-works/pi-coding-agent": path.join(piPkgRoot, "dist", "index.js") };
  for (const spec of ["typebox", "typebox/compile", "typebox/value"]) {
    try {
      const resolved = req.resolve(spec);
      alias[spec] = resolved;
      alias[spec.replace(/^typebox/, "@sinclair/typebox")] = resolved;
    } catch { /* not resolvable: the extension import will say so */ }
  }

  const { createJiti } = await import(pathToFileURL(jitiMjsPath).href);
  const jiti = createJiti(import.meta.url, { moduleCache: false, alias });

  let factory;
  try {
    factory = await jiti.import(extPath, { default: true });
  } catch (err) {
    out.importError = err instanceof Error ? (err.stack || err.message) : String(err);
    emit();
    return;
  }
  out.defaultIsFunction = typeof factory === "function";
  if (!out.defaultIsFunction) { emit(); return; }

  const tools = new Map();
  const commands = new Map();
  const handlers = [];
  const pi = noopProxy({
    on(event, handler) { handlers.push({ event, handler }); return () => {}; },
    registerTool(tool) { tools.set(tool.name, tool); },
    registerCommand(name, options) { commands.set(name, options); },
    sendUserMessage(content, options) {
      out.userMessages.push({ text: textOf(content), options: options ?? null });
    },
    sendMessage(message, options) {
      out.messages.push({ text: textOf(message && message.content) + "\n" + JSON.stringify(message), options: options ?? null });
    },
  });
  const ui = noopProxy({
    notify(message, type) { out.notifies.push({ text: String(message), type: type ?? null }); },
  });
  const ctx = noopProxy({ cwd: process.cwd(), hasUI: true, mode: "tui", ui, signal: undefined });

  try {
    await factory(pi);
  } catch (err) {
    out.importError = "factory threw: " + (err instanceof Error ? (err.stack || err.message) : String(err));
    emit();
    return;
  }
  out.tools = [...tools.keys()];
  out.commands = [...commands.keys()];
  for (const [name, tool] of tools) {
    out.toolParameters[name] = JSON.stringify(tool.parameters ?? null);
  }

  let callN = 0;
  for (const step of scenario.steps ?? []) {
    const rec = { op: step.op };
    if (step.op === "tool") {
      const tool = tools.get(step.name ?? "sandesh_watcher");
      if (!tool) { rec.missing = true; out.steps.push(rec); continue; }
      callN += 1;
      const res = await withTimeout(
        () => tool.execute(`call-${callN}`, step.params, undefined, undefined, ctx),
        step.timeoutMs ?? 8000,
      );
      rec.markerExistedAtResolve = scenario.markerPath ? existsSync(scenario.markerPath) : null;
      rec.timedOut = !!res.timedOut;
      rec.threw = res.threw ?? null;
      rec.text = res.value ? textOf(res.value.content) : null;
    } else if (step.op === "command") {
      const cmd = commands.get(step.name ?? "watcher");
      if (!cmd) { rec.missing = true; out.steps.push(rec); continue; }
      const res = await withTimeout(() => cmd.handler(step.args ?? "", ctx), step.timeoutMs ?? 8000);
      rec.timedOut = !!res.timedOut;
      rec.threw = res.threw ?? null;
    } else if (step.op === "sleep") {
      await sleep(step.ms);
    } else if (step.op === "advanceClock") {
      clockOffset += step.ms;
    } else if (step.op === "touch") {
      writeFileSync(step.path, "");
    } else if (step.op === "waitUntil") {
      const deadline = Date.now() - clockOffset + (step.timeoutMs ?? 5000);
      const ok = () =>
        (step.launches === undefined || launchPids().length >= step.launches) &&
        (step.surfaced === undefined || surfacedCount() >= step.surfaced) &&
        (step.userMessages === undefined || out.userMessages.length >= step.userMessages);
      while (!ok() && Date.now() - clockOffset < deadline) await sleep(25);
      rec.met = ok();
    } else if (step.op === "waitPidDead") {
      const pid = launchPids()[step.launch - 1];
      rec.pid = pid ?? null;
      const deadline = Date.now() - clockOffset + (step.timeoutMs ?? 3000);
      while (pid && pidAlive(pid) && Date.now() - clockOffset < deadline) await sleep(25);
      rec.dead = pid ? !pidAlive(pid) : null;
    } else if (step.op === "snapshot") {
      out.snapshots[step.label] = {
        launches: launchPids().length,
        userMessages: out.userMessages.length,
        messages: out.messages.length,
        notifies: out.notifies.length,
        surfaced: surfacedCount(),
      };
    }
    out.steps.push(rec);
  }

  for (const h of handlers.filter((x) => x.event === "session_shutdown")) {
    try { await withTimeout(() => h.handler({ type: "session_shutdown" }, ctx), 2000); } catch { /* cleanup only */ }
  }
  emit();
}

main().catch((err) => {
  out.harnessError = String((err && err.stack) || err);
  emit(0);
});
