"""The workflow permission policy, rendered per project (CR-MDB-037 §S3),
and the RETIRED installer report on the GLOBAL permission config
(CR-MDB-038 §S3).

``init`` renders ``<target>/.pi/extensions/pi-permission-system/config.json``
for every project with Pi among its harnesses: JSON carrying CR-MDB-025
§S6's ownership marker as a leading ``//`` comment, ``"*": "ask"`` as the
fallback, ``allow`` by exact tool name for the §S3 tool set (the
``dispatch`` and ``lean-ctx`` names READ FROM ``REQUIREMENTS``), ``skill:
allow`` and the §S3 external-directory rules. CR-MDB-038 §S3 (user ruling
2026-09-24) removes the installer's global-config report: no install
envelope carries ``global_permission_policy`` or
``global_permission_missing_tools``, and the installer never opens the
global config (observed with an audit hook, as CR-MDB-037's freshness test
does).

Orchestrator rulings (2026-09-24, cycle 95) these tests pin:
- P1 / P2: RETIRED by CR-MDB-038 §S3 (they classified the global config
  as ``absent | no-fallback | missing-tools | ok | unknown``).
- P3: ownership is driven through the real CLI into a pre-seeded target,
  ``modelb-axi --yes [--force-managed] init ... --no-commit``.
- P4: the marker is the FIRST line, starts ``//``, names ``modelb-axi`` and
  ends with the sha256 hex of the file minus that line.
- P5: built-in file tools = read, write, edit, grep, find, ls (no bash).
  ``~/.bun/install/*`` is asserted in-process only, by
  :class:`HarnessCodeReadsTest` (VERIFY finding 5), against a sandbox
  ``HOME`` holding a ``pi`` stand-in.

Isolation: every run pins ``HOME`` and ``PI_CODING_AGENT_DIR`` to a
throw-away sandbox; the real ``~/.pi`` is never read.

Stdlib only.
"""

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from modelb_axi import requirements as _requirements
from tests.pi_capability_sandbox import (
    AGENT_DIR_ENV,
    make_home,
    make_provisioned_agent_dir,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

POLICY_REL = str(Path(".pi") / "extensions" / "pi-permission-system" / "config.json")
GLOBAL_POLICY_RELPATH = Path("extensions") / "pi-permission-system" / "config.json"

#: Top-level keys ``@gotgenes/pi-permission-system``'s
#: ``schemas/permissions.schema.json`` declares (``additionalProperties:
#: false`` — any other key makes the file invalid and clamps the project to
#: ``ask``). Read from the installed package's schema on 2026-09-24.
SCHEMA_TOP_LEVEL_KEYS = frozenset({
    "$schema", "debugLog", "permissionReviewLog", "yoloMode",
    "doublePressToConfirm", "permissionDialogKeys", "forwardingTimeoutMs",
    "promptMaxRows", "promptFieldMaxWidth", "reviewLogFieldMaxWidth",
    "toolInputPreviewMaxLength", "toolTextSummaryMaxLength",
    "piInfrastructureReadPaths", "authorizerChain", "permission", "shellTools",
})

#: §S3 / ruling P5 — the built-in file tools.
BUILTIN_FILE_TOOLS = ("read", "write", "edit", "grep", "find", "ls")
#: §S3 — the UI tools and the child-side tools.
FIXED_WORKFLOW_TOOLS = ("todo", "ask_user_question", "notify_parent", "ask_parent")

#: §S3 — the external-directory reads that must be allowed.
REQUIRED_EXTERNAL_READS = ("~/.agents/*", "~/.crucible/*", "~/.pi/agent/*", "/tmp/*")
#: Patterns no external-directory read allowance may be (they would allow
#: the whole home / the whole filesystem).
OVERBROAD_PATTERNS = frozenset({"*", "**", "~", "~/*", "~/**", "/", "/*", "/**", "$HOME/*"})

_SHA256_TAIL = re.compile(r"([0-9a-f]{64})\s*$")


def expected_allow_tools() -> set[str]:
    """The §S3 allow-set, with the dispatch and lean-ctx names read from
    ``REQUIREMENTS`` at call time (never restated)."""
    tools = set(_requirements.requirement("dispatch")["tools"])
    tools |= set(_requirements.requirement("lean-ctx")["tools"])
    return tools | set(BUILTIN_FILE_TOOLS) | set(FIXED_WORKFLOW_TOOLS)


def strip_line_comments(text: str) -> str:
    """Drop whole-line ``//`` comments, as the package's loader does."""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


def split_marker(text: str) -> tuple[str, str]:
    """``(first line, rest of the file)`` — ruling P4's marker layout."""
    first, sep, rest = text.partition("\n")
    return first, rest if sep else ""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def decode_axi(stdout: str) -> dict:
    from modelb_axi.toon import decode
    try:
        return decode(stdout).get("axi", {})
    except Exception:  # noqa: BLE001 -- a non-envelope stdout is reported by the caller
        return {}


def write_install_toml(modelb_home: Path, harnesses=("pi",)) -> None:
    """install.toml fixture the scaffold reads (mirrors test_scaffold's
    ``_write_install_toml``), its hooks_scripts_dir inside the sandbox."""
    hooks_scripts_dir = modelb_home / ".agents" / "hooks" / "scripts"
    harnesses_toml = ", ".join(f'"{h}"' for h in harnesses)
    modelb_home.mkdir(parents=True, exist_ok=True)
    (modelb_home / "install.toml").write_text(
        "[install]\n"
        'version = "0.1.0"\n'
        f"harnesses = [{harnesses_toml}]\n"
        'asset_root = "/tmp/does-not-matter-for-this-test"\n'
        f'hooks_scripts_dir = "{hooks_scripts_dir}"\n'
        "\n[deps]\nuv = \"present\"\n\n[files]\n",
        encoding="utf-8",
    )


_INIT_FLAGS = (
    "--name", "X", "--token", "xproj", "--acronym", "XP",
    "--mode", "solo", "--repo-shape", "standalone",
    "--stacks", "python", "--owner", "tester",
)


class _InitSandbox(unittest.TestCase):
    """Per-test sandbox: HOME, PI_CODING_AGENT_DIR, MODELB_HOME, targets."""

    harnesses = ("pi",)

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modelb-cr037-policy-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.home = make_home(self.root / "home", crucible_manifest=False)
        self.agent_dir = make_provisioned_agent_dir(self.root / "agent")
        self.modelb_home = self.root / "modelb-home"
        write_install_toml(self.modelb_home, harnesses=self.harnesses)
        self.work = self.root / "work"
        self.work.mkdir()

    def env(self) -> dict:
        env = dict(os.environ)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
        env["HOME"] = str(self.home)
        env[AGENT_DIR_ENV] = str(self.agent_dir)
        return env

    def new_target(self, name: str) -> Path:
        target = self.work / name
        target.mkdir(parents=True)
        return target

    def run_init(self, target: Path, *, force_managed=False, dry_run=False):
        pre = ["--yes"] + (["--force-managed"] if force_managed else [])
        post = ["--no-commit"] + (["--dry-run"] if dry_run else [])
        return subprocess.run(
            [sys.executable, "-m", "modelb_axi", *pre, "init", *_INIT_FLAGS,
             "--target", str(target), "--modelb-home", str(self.modelb_home), *post],
            capture_output=True, text=True, timeout=90,
            stdin=subprocess.DEVNULL, env=self.env(),
        )

    def assert_ok(self, result):
        self.assertEqual(
            result.returncode, 0,
            f"precondition: init must succeed; stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )

    def render(self, name="render") -> tuple[str, dict]:
        """A fresh init into an empty target: (policy text, envelope)."""
        target = self.new_target(name)
        result = self.run_init(target)
        self.assert_ok(result)
        policy = target / POLICY_REL
        self.assertTrue(
            policy.is_file(),
            f"§S3: init with Pi among the harnesses must write {POLICY_REL}; "
            f"stderr={result.stderr!r}",
        )
        return policy.read_text(encoding="utf-8"), decode_axi(result.stdout)


def _parsed_policy(test: unittest.TestCase, text: str) -> dict:
    try:
        data = json.loads(strip_line_comments(text))
    except json.JSONDecodeError as exc:
        test.fail(f"§S3: the policy must parse as JSON after `//` comments are "
                  f"stripped; {exc}; text={text!r}")
    test.assertIsInstance(data, dict, f"§S3: top level must be an object; {text!r}")
    test.assertIsInstance(data.get("permission"), dict,
                          f"§S3: the policy must carry a `permission` object; {text!r}")
    return data


# ---------------------------------------------------------------------------
# §S3 AC1 — written with Pi, not without
# ---------------------------------------------------------------------------

class PermissionPolicyEmissionTest(_InitSandbox):
    """§S3 AC1 — ``init`` with Pi among the harnesses writes the policy (and
    lists it in the envelope's ``emitted``); with no Pi it writes none."""

    def test_init_with_pi_writes_the_policy_and_without_pi_writes_none(self):
        text, axi = self.render("with-pi")
        self.assertTrue(text.strip(), "§S3: the policy file must not be empty")
        self.assertIn(
            POLICY_REL, axi.get("emitted") or [],
            f"§S3 / CR-MDB-033 §S4: the written policy must be listed in the "
            f"envelope's `emitted`; got axi={axi!r}",
        )

        # NEGATIVE — no Pi among the harnesses, no policy.
        write_install_toml(self.modelb_home, harnesses=("claude-code",))
        target = self.new_target("without-pi")
        result = self.run_init(target)
        self.assert_ok(result)
        self.assertFalse(
            (target / POLICY_REL).exists(),
            "§S3: init without Pi among the harnesses must write no permission policy",
        )
        self.assertFalse(
            (target / ".pi" / "extensions" / "pi-permission-system").exists(),
            "§S3: without Pi, nothing is written under .pi/extensions/pi-permission-system",
        )
        self.assertNotIn(POLICY_REL, decode_axi(result.stdout).get("emitted") or [])


# ---------------------------------------------------------------------------
# §S3 AC2 — the rendered file's contents
# ---------------------------------------------------------------------------

class PermissionPolicyContentTest(_InitSandbox):
    """§S3 AC2 — one real render, inspected: comment-stripped JSON, leading
    ``//`` ownership marker (P4), schema-declared top-level keys only,
    ``"*": "ask"``, no ``"*": "allow"``, exactly the §S3 tool allows, and
    the external-directory rules."""

    def setUp(self):
        super().setUp()
        self.text, _ = self.render()
        self.data = _parsed_policy(self, self.text)
        self.permission = self.data["permission"]

    def test_policy_carries_the_ownership_marker_as_its_leading_comment(self):
        first, rest = split_marker(self.text)
        self.assertTrue(
            first.startswith("//"),
            f"§S3/P4: the ownership marker is the FIRST line, a `//` comment; "
            f"got first line {first!r}",
        )
        self.assertIn("modelb-axi", first, f"P4: the marker names modelb-axi; {first!r}")
        match = _SHA256_TAIL.search(first)
        if match is None:
            self.fail(f"P4: the marker ends with a sha256 hex; {first!r}")
        self.assertEqual(
            match.group(1), sha256_text(rest),
            "P4 / CR-MDB-025 §S6: the marker's digest is the sha256 of the "
            "file minus the marker line",
        )
        # NEGATIVE — the marker is a comment, never a key (a marker key would
        # make the file invalid and clamp the project to `ask`).
        self.assertFalse(
            any("modelb" in key.lower() for key in self.data),
            f"§S3: no marker KEY in the JSON; keys={sorted(self.data)!r}",
        )

    def test_policy_has_only_schema_declared_top_level_keys(self):
        unknown = sorted(set(self.data) - SCHEMA_TOP_LEVEL_KEYS)
        self.assertEqual(
            unknown, [],
            f"§S3: only top-level keys the package's schema declares; got extra "
            f"keys {unknown!r} in {sorted(self.data)!r}",
        )

    def test_policy_fallback_is_ask_and_no_star_rule_allows(self):
        self.assertEqual(
            self.permission.get("*"), "ask",
            f"§S3: `\"*\": \"ask\"` is the explicit fallback; got "
            f"{self.permission.get('*')!r}",
        )
        allowing_stars = [
            surface for surface, rule in self.permission.items()
            if isinstance(rule, dict) and rule.get("*") == "allow"
        ]
        self.assertEqual(
            allowing_stars, [],
            f"§S3: no `\"*\": \"allow\"` anywhere in the policy; found under "
            f"{allowing_stars!r}",
        )

    def test_policy_allows_exactly_the_workflow_tools_and_skill(self):
        allowed = {
            surface for surface, rule in self.permission.items()
            if rule == "allow" and surface != "skill"
        }
        expected = expected_allow_tools()
        self.assertEqual(
            sorted(allowed - expected), [],
            "§S3: nothing beyond the §S3 tools is allowed by name",
        )
        self.assertEqual(
            sorted(expected - allowed), [],
            "§S3: every §S3 tool (REQUIREMENTS dispatch + lean-ctx tools, the "
            "built-in file tools, todo, ask_user_question, notify_parent, "
            "ask_parent) is allowed by exact name",
        )
        self.assertEqual(self.permission.get("skill"), "allow", "§S3: `skill: allow`")
        self.assertNotEqual(
            self.permission.get("bash"), "allow",
            "P5: bash is not a built-in file tool and is not allowed",
        )

    def test_policy_external_directory_rules(self):
        reads = self.permission.get("external_directory_read")
        self.assertIsInstance(reads, dict, f"§S3: external_directory_read map; got {reads!r}")
        self.assertEqual(reads.get("*"), "ask", f"§S3: reads else `ask`; got {reads!r}")
        for pattern in REQUIRED_EXTERNAL_READS:
            with self.subTest(pattern=pattern):
                self.assertEqual(
                    reads.get(pattern), "allow",
                    f"§S3: external_directory_read allows {pattern!r}; got {reads!r}",
                )
        overbroad = sorted(
            p for p, action in reads.items()
            if action == "allow" and p in OVERBROAD_PATTERNS
        )
        self.assertEqual(overbroad, [], f"§S3: no over-broad read allowance; {reads!r}")

        writes = self.permission.get("external_directory_write")
        self.assertEqual(
            writes, {"*": "ask", "/tmp/*": "allow"},  # noqa: S108 -- the spec's pattern
            "§S3: external_directory_write allows /tmp/* only, else ask — no "
            "write allowance outside /tmp",
        )
        # NEGATIVE — the sugar keys must not widen either direction.
        for sugar in ("external_directory", "path", "path_write"):
            with self.subTest(sugar=sugar):
                self.assertNotEqual(self.permission.get(sugar), "allow")


# ---------------------------------------------------------------------------
# §S3 — the installed harness's own code (VERIFY finding 5)
# ---------------------------------------------------------------------------

class HarnessCodeReadsTest(unittest.TestCase):
    """§S3: ``external_directory_read`` allows ``~/.bun/install/*`` exactly
    when the ``pi`` on PATH is a bun-installed Pi — its resolved path lies
    under ``$HOME/.bun/install``. In-process ``render_policy`` with ``HOME``
    and ``PATH`` pinned to a sandbox; a ``pi`` stand-in shaped like bun's
    global install (``~/.bun/bin/pi`` -> ``~/.bun/install/global/...``)."""

    BUN_READ = "~/.bun/install/*"

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modelb-cr037-bunread-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.home = self.root / "home"
        self.home.mkdir()

    @staticmethod
    def _exe(path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        path.chmod(0o755)
        return path

    def _reads(self, path_dir: Path) -> dict:
        from modelb_axi import permission_policy
        with mock.patch.dict(os.environ, {"HOME": str(self.home), "PATH": str(path_dir)}):
            text = permission_policy.render_policy()
        return _parsed_policy(self, text)["permission"]["external_directory_read"]

    def test_bun_installed_pi_allows_reading_bun_install(self):
        cli = self._exe(self.home / ".bun" / "install" / "global" / "node_modules"
                        / "pi-coding-agent" / "dist" / "cli.js")
        bin_dir = self.home / ".bun" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "pi").symlink_to(cli)
        reads = self._reads(bin_dir)
        self.assertEqual(reads.get(self.BUN_READ), "allow",
                         f"§S3: a bun-installed Pi's own code is readable; reads={reads!r}")

    def test_pi_resolving_elsewhere_adds_no_bun_read(self):
        bin_dir = self.root / "elsewhere" / "bin"
        self._exe(bin_dir / "pi")
        (self.home / ".bun" / "install").mkdir(parents=True)
        reads = self._reads(bin_dir)
        self.assertNotIn(self.BUN_READ, reads,
                         f"§S3: no bun read for a Pi installed elsewhere; reads={reads!r}")

    def test_no_pi_on_path_adds_no_bun_read(self):
        empty = self.root / "empty-bin"
        empty.mkdir()
        reads = self._reads(empty)
        self.assertNotIn(self.BUN_READ, reads, f"reads={reads!r}")


# ---------------------------------------------------------------------------
# §S3 AC2 — the dispatch / lean-ctx names are READ from REQUIREMENTS
# ---------------------------------------------------------------------------

class PermissionPolicyReadsRequirementsDataTest(unittest.TestCase):
    """§S3 AC2 — mutating the ``dispatch`` and ``lean-ctx`` rows' ``tools``
    in-process changes the rendered allow-set, and the replaced names
    disappear. In-process ``scaffold.run_init`` (the only way to alter the
    data mid-run); rows are patched IN PLACE so the patch lands whatever
    import style the scaffold uses."""

    _DISPATCH_SENTINEL = ("sentinel_dispatch_tool_037",)
    _LEAN_CTX_SENTINEL = ("sentinel_lean_ctx_tool_037", "ctx_sentinel_second_037")

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modelb-cr037-policy-data-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.home = make_home(self.root / "home", crucible_manifest=False)
        self.agent_dir = make_provisioned_agent_dir(self.root / "agent")
        self.modelb_home = self.root / "modelb-home"
        write_install_toml(self.modelb_home, harnesses=("pi",))
        self.target = self.root / "target"
        self.target.mkdir()

    def test_allow_set_follows_the_requirements_rows_not_a_copy(self):
        from modelb_axi import scaffold

        original = (
            set(_requirements.requirement("dispatch")["tools"])
            | set(_requirements.requirement("lean-ctx")["tools"])
        )
        args = argparse.Namespace(
            name="X", token="xproj", acronym="XP", mode="solo",  # noqa: S106 -- project token
            repo_shape="standalone", stacks="python", owner="tester",
            target=str(self.target), dry_run=False, no_commit=True,
            register=False, harnesses=None, force_managed=False,
        )
        with mock.patch.dict(
            _requirements.requirement("dispatch"), {"tools": self._DISPATCH_SENTINEL},
        ), mock.patch.dict(
            _requirements.requirement("lean-ctx"), {"tools": self._LEAN_CTX_SENTINEL},
        ), mock.patch.dict(
            os.environ, {"HOME": str(self.home), AGENT_DIR_ENV: str(self.agent_dir)},
        ), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            exit_code = scaffold.run_init(args, self.modelb_home)
        self.assertEqual(exit_code, 0, f"precondition: init must succeed; {err.getvalue()!r}")
        policy = self.target / POLICY_REL
        self.assertTrue(policy.is_file(), f"§S3: {POLICY_REL} must be written")
        permission = _parsed_policy(self, policy.read_text(encoding="utf-8"))["permission"]
        allowed = {s for s, r in permission.items() if r == "allow" and s != "skill"}
        expected = (
            set(self._DISPATCH_SENTINEL) | set(self._LEAN_CTX_SENTINEL)
            | set(BUILTIN_FILE_TOOLS) | set(FIXED_WORKFLOW_TOOLS)
        )
        self.assertEqual(
            sorted(allowed), sorted(expected),
            "§S3: the dispatch and lean-ctx allows are derived from REQUIREMENTS "
            "at render time, never restated",
        )
        leaked = sorted((original - set(BUILTIN_FILE_TOOLS)) & set(permission))
        self.assertEqual(leaked, [], f"§S3: replaced tool names must be gone; found {leaked!r}")


# ---------------------------------------------------------------------------
# §S3 AC3 — ownership, one subtest per rule (ruling P3)
# ---------------------------------------------------------------------------

class PermissionPolicyOwnershipTest(_InitSandbox):
    """§S3 AC3 — CR-MDB-025 §S6's rules for the policy file: missing ->
    written; intact marker -> rewritten; hand-edited -> skipped, then
    rewritten with ``--force-managed``; unmarked -> never written (not even
    with ``--force-managed``). Each rule gets its own pre-seeded target."""

    def setUp(self):
        super().setUp()
        self.fresh, _ = self.render("reference")

    def _seed(self, name: str, text: str) -> Path:
        target = self.new_target(name)
        path = target / POLICY_REL
        path.parent.mkdir(parents=True)
        path.write_text(text, encoding="utf-8")
        return target

    def _marker_prefix(self) -> str:
        first, _ = split_marker(self.fresh)
        match = _SHA256_TAIL.search(first)
        if match is None:
            self.fail(f"P4 precondition: marker ends in sha256; {first!r}")
        return first[:match.start(1)]

    def test_ownership_rules(self):
        with self.subTest(rule="missing -> written"):
            target = self.new_target("missing")
            result = self.run_init(target)
            self.assert_ok(result)
            self.assertEqual(
                (target / POLICY_REL).read_text(encoding="utf-8"), self.fresh,
                "§S3 ownership: a missing policy is written",
            )

        with self.subTest(rule="intact -> rewritten"):
            body = '{\n  "permission": {\n    "*": "deny"\n  }\n}\n'
            intact = f"{self._marker_prefix()}{sha256_text(body)}\n{body}"
            target = self._seed("intact", intact)
            result = self.run_init(target)
            self.assert_ok(result)
            self.assertEqual(
                (target / POLICY_REL).read_text(encoding="utf-8"), self.fresh,
                "§S3 ownership: a policy whose marker is intact is rewritten",
            )

        with self.subTest(rule="hand-edited -> skipped, then --force-managed rewrites"):
            first, rest = split_marker(self.fresh)
            edited_data = json.loads(strip_line_comments(rest))
            edited_data["permission"]["bash"] = "allow"
            edited = f"{first}\n{json.dumps(edited_data, indent=2)}\n"
            self.assertNotEqual(edited, self.fresh, "fixture precondition")
            target = self._seed("hand-edited", edited)
            result = self.run_init(target)
            self.assert_ok(result)
            self.assertEqual(
                (target / POLICY_REL).read_text(encoding="utf-8"), edited,
                "§S3 ownership: a hand-edited policy is skipped (byte-identical) "
                "without --force-managed",
            )
            self.assertNotIn(
                POLICY_REL, decode_axi(result.stdout).get("emitted") or [],
                "CR-MDB-033 §S4: a skipped file is not listed as emitted",
            )
            forced = self.run_init(target, force_managed=True)
            self.assert_ok(forced)
            self.assertEqual(
                (target / POLICY_REL).read_text(encoding="utf-8"), self.fresh,
                "§S3 ownership: --force-managed rewrites a hand-edited policy",
            )

        with self.subTest(rule="unmarked -> never written"):
            unmarked = '{\n  "permission": {\n    "*": "ask"\n  }\n}\n'
            target = self._seed("unmarked", unmarked)
            for force in (False, True):
                result = self.run_init(target, force_managed=force)
                self.assert_ok(result)
                self.assertEqual(
                    (target / POLICY_REL).read_text(encoding="utf-8"), unmarked,
                    f"§S3 ownership: an unmarked policy is never written "
                    f"(force_managed={force})",
                )


# ---------------------------------------------------------------------------
# §S3 AC3 — init's surface for the ownership rules (VERIFY finding 6)
# ---------------------------------------------------------------------------

class InitPolicyOwnershipSurfaceTest(_InitSandbox):
    """``init`` accepts ``--force-managed`` after the subcommand too (as
    ``agents`` does), and its envelope reports a hand-edited policy it
    skipped — in ``skipped`` and as a warning naming ``--force-managed``."""

    def setUp(self):
        super().setUp()
        self.fresh, _ = self.render("reference")
        first, rest = split_marker(self.fresh)
        data = json.loads(strip_line_comments(rest))
        data["permission"]["bash"] = "allow"
        self.edited = f"{first}\n{json.dumps(data, indent=2)}\n"
        self.assertNotEqual(self.edited, self.fresh, "fixture precondition")

    def _seed_hand_edited(self, name: str) -> Path:
        target = self.new_target(name)
        path = target / POLICY_REL
        path.parent.mkdir(parents=True)
        path.write_text(self.edited, encoding="utf-8")
        return target

    def test_force_managed_after_the_subcommand_rewrites_a_hand_edited_policy(self):
        target = self._seed_hand_edited("post-flag")
        result = subprocess.run(
            [sys.executable, "-m", "modelb_axi", "--yes", "init", *_INIT_FLAGS,
             "--target", str(target), "--modelb-home", str(self.modelb_home),
             "--no-commit", "--force-managed"],
            capture_output=True, text=True, timeout=90,
            stdin=subprocess.DEVNULL, env=self.env(),
        )
        self.assert_ok(result)
        self.assertEqual(
            (target / POLICY_REL).read_text(encoding="utf-8"), self.fresh,
            "`init ... --force-managed` (flag after the subcommand) rewrites a "
            "hand-edited policy, as the flag before it does",
        )

    def test_skipped_hand_edited_policy_is_reported_in_the_envelope(self):
        target = self._seed_hand_edited("skipped")
        result = self.run_init(target)
        self.assert_ok(result)
        self.assertEqual((target / POLICY_REL).read_text(encoding="utf-8"), self.edited,
                         "precondition: the hand-edited policy is left alone")
        axi = decode_axi(result.stdout)
        self.assertEqual(axi.get("skipped"), [POLICY_REL],
                         f"init's envelope lists the skipped policy; axi={axi!r}")
        hits = [w for w in axi.get("warnings", [])
                if POLICY_REL in w and "--force-managed" in w]
        self.assertEqual(len(hits), 1,
                         f"one warning naming the file and --force-managed; "
                         f"warnings={axi.get('warnings')!r}")
        self.assertIn(POLICY_REL, result.stderr, "the summary on stderr names it too")

    def test_unmarked_policy_is_reported_unmanaged_in_the_envelope(self):
        """VERIFY (cycle 100) finding 4: the ``unmanaged`` branch \u2014
        an unmarked policy is left alone and reported in ``unmanaged`` (not
        ``skipped``) with one warning naming the file and no flag."""
        unmarked = '{\n  "permission": {\n    "*": "ask"\n  }\n}\n'
        target = self.new_target("unmarked-surface")
        path = target / POLICY_REL
        path.parent.mkdir(parents=True)
        path.write_text(unmarked, encoding="utf-8")
        result = self.run_init(target, force_managed=True)
        self.assert_ok(result)
        self.assertEqual(path.read_text(encoding="utf-8"), unmarked,
                         "precondition: an unmarked policy is never written")
        axi = decode_axi(result.stdout)
        self.assertEqual(axi.get("unmanaged"), [POLICY_REL],
                         f"init's envelope lists the unmanaged policy; axi={axi!r}")
        self.assertNotIn(POLICY_REL, axi.get("skipped") or [],
                         f"unmanaged is not skipped; axi={axi!r}")
        self.assertNotIn(POLICY_REL, axi.get("emitted") or [],
                         f"an unmanaged file is not emitted; axi={axi!r}")
        hits = [w for w in axi.get("warnings", [])
                if POLICY_REL in w and w.startswith("unmanaged:")]
        self.assertEqual(len(hits), 1,
                         f"one `unmanaged:` warning naming the file; "
                         f"warnings={axi.get('warnings')!r}")
        self.assertNotIn("--force-managed", hits[0],
                         "no flag overwrites an unmanaged file, so none is named")
        self.assertIn(f"unmanaged: {POLICY_REL}", result.stderr,
                      "the warning reaches stderr too")


# ---------------------------------------------------------------------------
# CR-MDB-038 §S3 — the global permission report is REMOVED (user ruling
# 2026-09-24): no install envelope carries it; the global config is unread.
# ---------------------------------------------------------------------------

_FAKE_UV = (
    "#!/bin/sh\n"
    'if [ "$1" = "tool" ] && [ "$2" = "install" ]; then exit 0; fi\n'
    'echo "uv 0.0.0-fake"\n'
    "exit 0\n"
)
_FAKE_SANDESH = "#!/bin/sh\necho sandesh-fake\nexit 0\n"

#: The two envelope fields CR-MDB-038 §S3 removes.
RETIRED_GLOBAL_FIELDS = ("global_permission_policy", "global_permission_missing_tools")
#: The stderr line the retired report printed (``  global permission policy: <state>``).
RETIRED_GLOBAL_STDERR = "global permission policy"

#: Runs ``modelb_axi.cli.main`` with an audit hook logging every path
#: OPENED (builtins/io/os.open all raise the ``open`` audit event) — the
#: technique of CR-MDB-037's freshness test
#: (``tests/test_deployed_asset_freshness.py``).
_OPEN_LOGGING_WRAPPER = r"""
import json, os, sys
_log_path = os.environ["MODELB_TEST_OPEN_LOG"]
_opened = []
def _hook(event, args):
    if event == "open" and args:
        target = args[0]
        if isinstance(target, (str, bytes, os.PathLike)):
            _opened.append(os.fsdecode(target))
sys.addaudithook(_hook)
import atexit
def _dump():
    snapshot = list(_opened)
    with open(_log_path, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh)
atexit.register(_dump)
from modelb_axi.cli import main
sys.exit(main(sys.argv[1:]))
"""


def _policy_text(permission: dict, comment: str | None = None) -> str:
    text = json.dumps({"permission": permission}, indent=2) + "\n"
    return f"// {comment}\n{text}" if comment else text


def _global_config_shapes() -> dict[str, str | None]:
    """Every shape the retired report used to classify, keyed by the state
    it reported (``None`` = no global config at all)."""
    everything = {"*": "ask"}
    everything.update(dict.fromkeys(sorted(expected_allow_tools()), "allow"))
    lacking = dict(everything)
    lacking[_requirements.requirement("dispatch")["tools"][0]] = "ask"
    del lacking["ask_parent"]
    return {
        "absent": None,
        "no-fallback": _policy_text(dict.fromkeys(sorted(expected_allow_tools()), "allow")),
        "missing-tools": _policy_text(lacking),
        "ok": _policy_text(everything, comment="user's own policy"),
        "unknown": '{ "permission": { "*": "ask", \n',
    }


class InstallerGlobalPolicyRetiredTest(unittest.TestCase):
    """CR-MDB-038 §S3 — against a sandboxed ``PI_CODING_AGENT_DIR``, no
    install outcome's envelope carries ``global_permission_policy`` or
    ``global_permission_missing_tools``, the installer prints no global-policy
    line, and a present global config is never opened (nor written)."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modelb-cr038-global-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.home = make_home(self.root / "home", crucible_manifest=False)
        self.agent_dir = make_provisioned_agent_dir(self.root / "agent")
        self.bin_dir = self.root / "bin"
        self.xdg = self.root / "xdg"
        for d in (self.bin_dir, self.xdg):
            d.mkdir(parents=True)
        for name, body in (("uv", _FAKE_UV), ("sandesh", _FAKE_SANDESH)):
            exe = self.bin_dir / name
            exe.write_text(body, encoding="utf-8")
            exe.chmod(0o755)
        self.global_policy = self.agent_dir / GLOBAL_POLICY_RELPATH

    def _seed_global(self, text: str | None) -> bytes | None:
        if self.global_policy.exists():
            self.global_policy.unlink()
        if text is None:
            return None
        self.global_policy.parent.mkdir(parents=True, exist_ok=True)
        self.global_policy.write_text(text, encoding="utf-8")
        return self.global_policy.read_bytes()

    def _sandbox(self, label: str) -> tuple[Path, Path]:
        """A fresh (modelb home, target root) pair — a fresh home means the
        run reaches ``installed``, not ``already_installed``."""
        modelb_home = self.root / label / "modelb-home"
        target_root = self.root / label / "target"
        for d in (modelb_home, target_root):
            d.mkdir(parents=True)
        return modelb_home, target_root

    def _env(self, modelb_home: Path, extra: dict | None = None) -> dict:
        env = dict(os.environ)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
        env["PATH"] = str(self.bin_dir)
        env["HOME"] = str(self.home)
        env["XDG_DATA_HOME"] = str(self.xdg)
        env["MODELB_HOME"] = str(modelb_home)
        env[AGENT_DIR_ENV] = str(self.agent_dir)
        env.pop("MODELB_TARGET_ROOT", None)
        env.update(extra or {})
        return env

    @staticmethod
    def _argv(modelb_home: Path, target_root: Path) -> list[str]:
        return ["--yes", "--harnesses", "pi", "--stacks", "python",
                "--modelb-home", str(modelb_home), "--target-root", str(target_root)]

    def _install(self, modelb_home: Path, target_root: Path,
                 want: str = "installed") -> tuple[dict, subprocess.CompletedProcess]:
        result = subprocess.run(
            [sys.executable, "-m", "modelb_axi", *self._argv(modelb_home, target_root)],
            capture_output=True, text=True, timeout=90,
            stdin=subprocess.DEVNULL, env=self._env(modelb_home),
        )
        axi = decode_axi(result.stdout)
        self.assertEqual(
            axi.get("outcome"), want,
            f"precondition: the run must reach `{want}`; exit="
            f"{result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        return axi, result

    def _assert_no_global_report(self, axi: dict, stderr: str) -> None:
        for field in RETIRED_GLOBAL_FIELDS:
            self.assertNotIn(field, axi,
                             f"CR-MDB-038 \u00a7S3: the envelope must not carry {field!r}; "
                             f"axi={axi!r}")
        self.assertNotIn(RETIRED_GLOBAL_STDERR, stderr.lower(),
                         "CR-MDB-038 \u00a7S3: no global-policy report line on stderr")

    def test_installed_envelope_carries_no_global_report_for_any_global_config(self):
        """Replaces the seven CR-MDB-037 value tests: whatever the global
        config's shape, ``installed`` reports nothing about it and the file
        is byte-identical (never created when absent)."""
        for state, text in _global_config_shapes().items():
            with self.subTest(retired_state=state):
                before = self._seed_global(text)
                modelb_home, target_root = self._sandbox(f"installed-{state}")
                axi, result = self._install(modelb_home, target_root)
                self._assert_no_global_report(axi, result.stderr)
                self.assertTrue(axi.get("ok"), f"the install still succeeds; axi={axi!r}")
                if before is None:
                    self.assertFalse(self.global_policy.exists(),
                                     "the installer never creates the global config")
                else:
                    self.assertEqual(self.global_policy.read_bytes(), before,
                                     "the installer never writes the global config")

    def test_already_installed_envelope_carries_no_global_report(self):
        """A re-run on an installed machine (``already_installed``) carries
        no global report either — \u00a7S3 covers every install outcome."""
        self._seed_global(_global_config_shapes()["missing-tools"])
        modelb_home, target_root = self._sandbox("rerun")
        self._install(modelb_home, target_root)
        axi, result = self._install(modelb_home, target_root, want="already_installed")
        self._assert_no_global_report(axi, result.stderr)

    def test_installer_never_opens_a_present_global_config(self):
        """CR-MDB-038 \u00a7S3: with a global config present, an install that
        reaches ``installed`` leaves it UNREAD \u2014 no ``open`` audit event
        names it. The hook is proved live by the files the install writes
        under the target root."""
        before = self._seed_global(_global_config_shapes()["ok"])
        modelb_home, target_root = self._sandbox("audit")
        log_path = self.root / "open-log.json"
        result = subprocess.run(
            [sys.executable, "-c", _OPEN_LOGGING_WRAPPER, *self._argv(modelb_home, target_root)],
            capture_output=True, text=True, timeout=90, stdin=subprocess.DEVNULL,
            env=self._env(modelb_home, {"MODELB_TEST_OPEN_LOG": str(log_path)}),
        )
        if not log_path.is_file():
            self.fail(f"open log not written; exit={result.returncode} stderr={result.stderr!r}")
        opened = json.loads(log_path.read_text(encoding="utf-8"))
        axi = decode_axi(result.stdout)
        self.assertEqual(axi.get("outcome"), "installed",
                         f"precondition: the install reaches `installed`; stderr={result.stderr!r}")
        resolved = {Path(p).resolve() for p in opened}
        self.assertTrue(
            any(target_root in p.parents for p in resolved),
            f"audit hook live: the deployed files must be seen opened; opened={opened!r}",
        )
        global_reads = [p for p in opened if Path(p).resolve() == self.global_policy.resolve()]
        self.assertEqual(
            global_reads, [],
            "CR-MDB-038 \u00a7S3: the installer must not read the global permission config",
        )
        self.assertEqual(self.global_policy.read_bytes(), before, "global config untouched")


if __name__ == "__main__":
    unittest.main()
