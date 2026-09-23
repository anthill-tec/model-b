#!/usr/bin/env node
// Test-only fixture (CR-MDB-030 §S8) — NOT production code, NOT a hook
// protocol script. Loads ONE emitted `.pi/extensions/*.ts` file with the
// SAME jiti mechanism Pi's own loader uses (`jiti.import(path, { default:
// true })`), invokes the factory with a recording `pi`, and (optionally)
// drives the first handler registered for the requested event with an
// event/ctx pair read from stdin, shaped as Pi 0.87.1 defines them.
//
// argv: <extensionPath> <jitiMjsPath>
// stdin (optional): JSON `{"event": {...}, "ctx": {...}}` — "event.type"
// selects the registered handler to drive; omitted/empty stdin means
// "just report what the factory registered, don't drive anything".
// stdout: one JSON object, always, even on an import/factory failure:
//   {
//     "defaultIsFunction": bool,
//     "importError": string | null,
//     "registeredEvents": string[],
//     "handlerResult": <value> | null,
//     "handlerThrew": string | null
//   }
//
// Every path below reaches an explicit `process.exit(...)` — no dangling
// timers/handles are allowed to keep the event loop (and the parent
// Python `subprocess.run(timeout=...)`) alive.

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

function emit(out, code = 0) {
  process.stdout.write(JSON.stringify(out));
  process.exit(code);
}

async function main() {
  const [, , extPath, jitiMjsPath] = process.argv;
  if (!extPath || !jitiMjsPath) {
    process.stderr.write("usage: pi_hook_loader_harness.mjs <extensionPath> <jitiMjsPath>\n");
    process.exit(2);
  }

  const { createJiti } = await import(pathToFileURL(jitiMjsPath).href);
  const jiti = createJiti(import.meta.url, { moduleCache: false });

  const out = {
    defaultIsFunction: false,
    importError: null,
    registeredEvents: [],
    handlerResult: null,
    handlerThrew: null,
  };

  let factory;
  try {
    factory = await jiti.import(extPath, { default: true });
  } catch (err) {
    out.importError = err instanceof Error ? (err.stack || err.message) : String(err);
    emit(out);
    return;
  }
  out.defaultIsFunction = typeof factory === "function";
  if (!out.defaultIsFunction) {
    emit(out);
    return;
  }

  const registered = [];
  const recordingPi = {
    on(event, handler) {
      registered.push({ event, handler });
      return () => {};
    },
  };

  try {
    await factory(recordingPi);
  } catch (err) {
    out.importError = "factory threw: " + (err instanceof Error ? (err.stack || err.message) : String(err));
    emit(out);
    return;
  }
  out.registeredEvents = registered.map((r) => r.event);

  const stdinText = readFileSync(0, "utf-8").trim();
  if (stdinText) {
    const { event, ctx } = JSON.parse(stdinText);
    const entry = registered.find((r) => r.event === event.type) ?? registered[0];
    if (entry) {
      try {
        const returned = await entry.handler(event, ctx ?? {});
        out.handlerResult = returned ?? null;
      } catch (err) {
        out.handlerThrew = err instanceof Error ? (err.stack || err.message) : String(err);
      }
    }
  }

  emit(out);
}

main().catch((err) => {
  process.stderr.write(String((err && err.stack) || err) + "\n");
  process.exit(1);
});
