#!/usr/bin/env python3
"""CR-MDB-008 — agent generator: renders the 16 small-stack agent definitions.

Renders ``generator/templates/{red,green,verify,fix}.md.tmpl`` (string.Template)
with the per-stack parameters from ``generator/stacks/{arduino,bun,python,
quarkus}.toml`` into the LIVE ``~/.claude/agents/`` tree.

Verbs:
  build          render and write the target files in place
  --check        re-render to memory and diff against the live files;
                 exit 0 when clean, exit 1 listing the drifted filenames
  --list         print the target file paths
  --stacks S,..  restrict to the given stacks (with any verb)
  --roles R,..   restrict to the given roles (with any verb)

Stdlib only. Deterministic output: stable target ordering, no timestamps.
The 13 bespoke defs (rust x4, vscode x4, electronics x4, inbox-analyst) are
NEVER targets.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path
from string import Template

GENERATOR_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = GENERATOR_DIR / "templates"
STACKS_DIR = GENERATOR_DIR / "stacks"
AGENTS_DIR = Path.home() / ".claude" / "agents"

STACKS = ("arduino", "bun", "python", "quarkus")
ROLES = ("red", "green", "verify", "fix")

# The 16 small-stack agent files this generator owns — never the bespoke defs.
TARGETS = tuple(f"{stack}-{role}-agent.md" for stack in STACKS for role in ROLES)


def load_stack_params(stack: str) -> dict:
    """Parse one stack TOML via tomllib."""
    path = STACKS_DIR / f"{stack}.toml"
    with path.open("rb") as fh:
        return tomllib.load(fh)


def render(stack: str, role: str, params: dict) -> str:
    """Render one agent file's full content deterministically."""
    template = Template((TEMPLATES_DIR / f"{role}.md.tmpl").read_text(encoding="utf-8"))
    mapping = {
        "name": f"{stack}-{role}-agent",
        "description": params["description"][role],
        "frontmatter_extra": params["frontmatter"][role].strip("\n"),
        "display_name": params["display_name"],
        "test_command": params["test_command"],
        "register_command": params["register_command"],
        "unregister_command": params["unregister_command"],
        "crucible_reference": params["crucible_reference"],
        "stack_mechanics": params["mechanics"].strip("\n"),
        "role_gotchas": params["gotchas"][role].strip("\n"),
    }
    content = template.substitute(mapping)
    return content.rstrip("\n") + "\n"


def selected_targets(stacks: tuple[str, ...], roles: tuple[str, ...]):
    """Yield (stack, role, filename) in stable TARGETS order."""
    for stack in STACKS:
        if stack not in stacks:
            continue
        params = load_stack_params(stack)
        for role in ROLES:
            if role not in roles:
                continue
            yield stack, role, f"{stack}-{role}-agent.md", params


def cmd_build(stacks, roles) -> int:
    for _stack, role, name, params in selected_targets(stacks, roles):
        target = AGENTS_DIR / name
        target.write_text(render(_stack, role, params), encoding="utf-8")
        print(f"wrote {target}")
    return 0


def cmd_check(stacks, roles) -> int:
    drifted = []
    for stack, role, name, params in selected_targets(stacks, roles):
        live = AGENTS_DIR / name
        rendered = render(stack, role, params)
        if not live.is_file() or live.read_text(encoding="utf-8") != rendered:
            drifted.append(name)
    if drifted:
        print("drifted (live differs from regeneration):")
        for name in drifted:
            print(name)
        return 1
    print("clean: live tree matches regeneration")
    return 0


def cmd_list(stacks, roles) -> int:
    for _stack, _role, name, _params in selected_targets(stacks, roles):
        print(AGENTS_DIR / name)
    return 0


def parse_filter(raw: str | None, allowed: tuple[str, ...], label: str) -> tuple[str, ...]:
    if raw is None:
        return allowed
    picked = tuple(item.strip() for item in raw.split(",") if item.strip())
    unknown = [item for item in picked if item not in allowed]
    if unknown:
        raise SystemExit(f"unknown {label}: {', '.join(unknown)} (allowed: {', '.join(allowed)})")
    return picked


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", nargs="?", choices=["build"],
                        help="build: render and write the live agent files")
    parser.add_argument("--check", action="store_true",
                        help="diff in-memory regeneration against the live files")
    parser.add_argument("--list", action="store_true", dest="list_targets",
                        help="print the target file paths")
    parser.add_argument("--stacks", help="comma-separated stack filter")
    parser.add_argument("--roles", help="comma-separated role filter")
    args = parser.parse_args(argv)

    actions = [bool(args.command), args.check, args.list_targets]
    if sum(actions) != 1:
        parser.error("exactly one of: build, --check, --list")

    stacks = parse_filter(args.stacks, STACKS, "stack")
    roles = parse_filter(args.roles, ROLES, "role")

    if args.check:
        return cmd_check(stacks, roles)
    if args.list_targets:
        return cmd_list(stacks, roles)
    return cmd_build(stacks, roles)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
