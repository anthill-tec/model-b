/**
 * Worktree isolation (CR-MDB-039 §S1, DN-multi-harness §D19).
 *
 * Routing: when the pi-subagents service is present (looked up lazily, at
 * session start, on a dispatch or on a tool call, so load order does not
 * matter) this registers ONE workspace provider, and keeps the service
 * instance that accepted it: `prepare` reads records from that instance only.
 * Every child session loads pi-subagents too and republishes, then deletes,
 * the global service entry, so a `globalThis` lookup inside `prepare` would
 * miss. `prepare` sends a child to the registered git worktree `.worktrees/<CR>`
 * of the CR id that OPENS the dispatch description (`CR-MDB-039 C1 RED`; a CR
 * id elsewhere does not route); otherwise to the entered root; otherwise
 * nowhere (the child keeps the parent's cwd). An entered root that no longer
 * exists is an error, never a silent fall-back to the main tree. While a root
 * is entered, a dispatch whose CR has a DIFFERENT worktree is an error naming
 * both: `WF_WORKTREE_ROOT` is process-wide and the hook prefers it, so that
 * child would be confined to the wrong worktree.
 *
 * Tools: `modelb_worktree_enter` sets `WF_WORKTREE_ROOT` (the variable the
 * block-write-outside-worktree hook reads) and records the entered root (its
 * real path); `modelb_worktree_exit` clears both. The session cwd never
 * changes. The hook governs file-tool writes (write/edit), not writes a shell
 * command makes.
 */

import { execFileSync } from "node:child_process";
import { existsSync, realpathSync, statSync } from "node:fs";
import path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const SERVICE_KEY = Symbol.for("@gotgenes/pi-subagents:service");
const CR_ID_RE = /^CR-[A-Z][A-Z0-9]*-[0-9]+/;
const WORKTREE_SEGMENT_RE = /\/\.worktrees\/[^/]+(\/|$)/;
const ROOT_ENV = "WF_WORKTREE_ROOT";

/** The slice of the pi-subagents service (src/service/service.ts) this uses. */
interface Workspace {
	readonly cwd: string;
	dispose(outcome: unknown): undefined;
}
interface WorkspaceProvider {
	prepare(ctx: { agentId: string; baseCwd: string }): Promise<Workspace | undefined>;
}
interface SubagentsService {
	getRecord(id: string): { description?: string } | undefined;
	registerWorkspaceProvider(provider: WorkspaceProvider): () => void;
}

const EnterParams = Type.Object({
	path: Type.String({ description: "The worktree to enter, e.g. '.worktrees/CR-MDB-039' (relative to the session cwd)" }),
});
const ExitParams = Type.Object({});

function text(t: string) {
	return { content: [{ type: "text" as const, text: t }], details: undefined };
}

function isDir(p: string): boolean {
	return existsSync(p) && statSync(p).isDirectory();
}

/** The real path of `p`, or `p` itself when it cannot be resolved. */
function realOrSelf(p: string): string {
	try {
		return realpathSync(p);
	} catch {
		return p;
	}
}

/**
 * The worktree paths `git worktree list --porcelain` reports for the
 * repository containing `dir`, main worktree first. Throws when `dir` is not
 * inside a git repository.
 */
function worktreesOf(dir: string): string[] {
	const out = execFileSync("git", ["-C", dir, "worktree", "list", "--porcelain"], {
		encoding: "utf-8",
		stdio: ["ignore", "pipe", "pipe"],
	});
	return out
		.split("\n")
		.filter((line) => line.startsWith("worktree "))
		.map((line) => line.slice("worktree ".length));
}

/** The registered worktree `.worktrees/<cr>` of the repository containing `baseCwd`, if any. */
function crWorktree(baseCwd: string, cr: string): string | undefined {
	let worktrees: string[];
	try {
		worktrees = worktreesOf(baseCwd);
	} catch {
		return undefined; // baseCwd is not in a git repository: it has no CR worktrees.
	}
	if (worktrees.length === 0) return undefined;
	const candidate = path.join(worktrees[0], ".worktrees", cr);
	return worktrees.includes(candidate) && isDir(candidate) ? candidate : undefined;
}

export default function worktreeIsolation(pi: ExtensionAPI) {
	let enteredRoot: string | undefined;
	let providerState: "none" | "registered" | string = "none";
	/** The service instance that accepted the provider; records are read from it alone. */
	let registeredService: SubagentsService | undefined;

	const provider: WorkspaceProvider = {
		async prepare({ agentId, baseCwd }) {
			const description = registeredService?.getRecord(agentId)?.description ?? "";
			const cr = CR_ID_RE.exec(description)?.[0];
			const own = cr ? crWorktree(baseCwd, cr) : undefined;
			if (own !== undefined && enteredRoot !== undefined && realOrSelf(own) !== enteredRoot) {
				throw new Error(
					`${cr} has its own worktree ${own}, but ${enteredRoot} is entered: WF_WORKTREE_ROOT is process-wide ` +
						`and the write hook prefers it, so this agent would be confined to ${enteredRoot}. ` +
						`An entered session works one CR; run modelb_worktree_exit (or enter ${own}) before dispatching.`,
				);
			}
			const cwd = own ?? enteredRoot;
			if (cwd === undefined) return undefined;
			if (!isDir(cwd)) {
				throw new Error(
					`The entered worktree ${cwd} no longer exists; run modelb_worktree_exit (or enter another worktree) before dispatching.`,
				);
			}
			return { cwd, dispose: () => undefined };
		},
	};

	function service(): SubagentsService | undefined {
		return (globalThis as Record<symbol, SubagentsService | undefined>)[SERVICE_KEY];
	}

	/** Register the one provider the first time the service is seen. */
	function ensureProvider(): void {
		if (providerState !== "none") return;
		const svc = service();
		if (!svc) return;
		try {
			svc.registerWorkspaceProvider(provider);
			registeredService = svc;
			providerState = "registered";
		} catch (err) {
			providerState = `pi-subagents refused the workspace provider: ${err instanceof Error ? err.message : String(err)}`;
		}
	}

	function relocationNote(): string {
		ensureProvider();
		if (providerState === "registered") {
			return "Dispatched agents without their own CR worktree run in it.";
		}
		const why = providerState === "none" ? "the pi-subagents service is absent" : providerState;
		return `Dispatched agents will not be relocated (${why}).`;
	}

	pi.registerTool({
		name: "modelb_worktree_enter",
		label: "Enter worktree",
		description:
			"Enter a Model B CR worktree (`.worktrees/<cr>`, a registered git worktree): file-tool writes outside it are blocked " +
			"(not writes a shell command makes) and dispatched agents run in it. The session cwd does not change. " +
			"Exit with modelb_worktree_exit.",
		parameters: EnterParams,
		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			const resolved = path.resolve(ctx.cwd, params.path);
			if (!isDir(resolved)) throw new Error(`Not entered: ${resolved} does not exist. Active root: ${enteredRoot ?? "none"}.`);
			const root = realpathSync(resolved);
			if (!WORKTREE_SEGMENT_RE.test(root)) {
				throw new Error(`Not entered: ${root} is not under a /.worktrees/<cr> segment. Active root: ${enteredRoot ?? "none"}.`);
			}
			let registered: string[];
			try {
				registered = worktreesOf(root);
			} catch (err) {
				const why = err instanceof Error ? err.message : String(err);
				throw new Error(`Not entered: ${root} is not in a git repository (${why}). Active root: ${enteredRoot ?? "none"}.`);
			}
			if (!registered.includes(root)) {
				throw new Error(
					`Not entered: ${root} is not a registered git worktree (git worktree list). Active root: ${enteredRoot ?? "none"}.`,
				);
			}
			enteredRoot = root;
			process.env[ROOT_ENV] = root;
			return text(
				`Entered worktree. Active root: ${root}. File-tool writes outside it are blocked (not writes a shell command makes). ${relocationNote()}`,
			);
		},
	});

	pi.registerTool({
		name: "modelb_worktree_exit",
		label: "Exit worktree",
		description: "Leave the entered Model B worktree: lifts the write boundary. Idempotent.",
		parameters: ExitParams,
		async execute() {
			ensureProvider();
			const was = enteredRoot;
			enteredRoot = undefined;
			delete process.env[ROOT_ENV];
			return text(was ? `Exited worktree ${was}. Active root: none.` : "No worktree was entered. Active root: none.");
		},
	});

	pi.on("session_start", async () => {
		ensureProvider();
	});

	pi.on("tool_call", async () => {
		ensureProvider();
		return undefined;
	});
}
