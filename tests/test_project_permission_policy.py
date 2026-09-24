"""The workflow permission policy, rendered per project, and the installer's
report on the GLOBAL permission config (CR-MDB-037 §S3).

``init`` renders ``<target>/.pi/extensions/pi-permission-system/config.json``
for every project with Pi among its harnesses: JSON carrying CR-MDB-025
§S6's ownership marker as a leading ``//`` comment, ``"*": "ask"`` as the
fallback, ``allow`` by exact tool name for the §S3 tool set (the
``dispatch`` and ``lean-ctx`` names READ FROM ``REQUIREMENTS``), ``skill:
allow`` and the §S3 external-directory rules. The installer reports the
global config as ``absent | no-fallback | missing-tools | ok | unknown`` and
never writes it.

Orchestrator rulings (2026-09-24, cycle 95) these tests pin:
- P1: the install envelope carries ``global_permission_policy`` (+
  ``global_permission_missing_tools`` only for ``missing-tools``), asserted
  on the ``installed`` outcome only.
- P2: "workflow tools" = exactly the §S3 project allow-set; a tool is
  missing unless ``permission[<tool>] == "allow"``; precedence absent ->
  unknown (unparseable after stripping ``//`` comments, or non-object) ->
  no-fallback -> missing-tools -> ok.
- P3: ownership is driven through the real CLI into a pre-seeded target,
  ``modelb-axi --yes [--force-managed] init ... --no-commit``.
- P4: the marker is the FIRST line, starts ``//``, names ``modelb-axi`` and
  ends with the sha256 hex of the file minus that line.
- P5: built-in file tools = read, write, edit, grep, find, ls (no bash);
  ``~/.bun/install/*`` is not asserted.

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
# §S3 AC4 — the installer reports the GLOBAL config (rulings P1/P2)
# ---------------------------------------------------------------------------

_FAKE_UV = (
    "#!/bin/sh\n"
    'if [ "$1" = "tool" ] && [ "$2" = "install" ]; then exit 0; fi\n'
    'echo "uv 0.0.0-fake"\n'
    "exit 0\n"
)
_FAKE_SANDESH = "#!/bin/sh\necho sandesh-fake\nexit 0\n"


class GlobalPermissionPolicyReportTest(unittest.TestCase):
    """§S3 AC4 — the ``installed`` envelope's ``global_permission_policy``
    is ``absent`` / ``no-fallback`` / ``missing-tools`` (with
    ``global_permission_missing_tools``) / ``ok`` / ``unknown``, one test
    each, against a sandboxed ``PI_CODING_AGENT_DIR``; the global file is
    byte-identical afterwards (Model B never writes it)."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modelb-cr037-global-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.home = make_home(self.root / "home", crucible_manifest=False)
        self.agent_dir = make_provisioned_agent_dir(self.root / "agent")
        self.modelb_home = self.root / "modelb-home"
        self.target_root = self.root / "target"
        self.bin_dir = self.root / "bin"
        for d in (self.modelb_home, self.target_root, self.bin_dir):
            d.mkdir(parents=True)
        for name, body in (("uv", _FAKE_UV), ("sandesh", _FAKE_SANDESH)):
            exe = self.bin_dir / name
            exe.write_text(body, encoding="utf-8")
            exe.chmod(0o755)
        self.global_policy = self.agent_dir / GLOBAL_POLICY_RELPATH

    def _seed_global(self, text: str) -> bytes:
        self.global_policy.parent.mkdir(parents=True, exist_ok=True)
        self.global_policy.write_text(text, encoding="utf-8")
        return self.global_policy.read_bytes()

    def _install(self) -> dict:
        env = dict(os.environ)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
        env["PATH"] = str(self.bin_dir)
        env["HOME"] = str(self.home)
        env[AGENT_DIR_ENV] = str(self.agent_dir)
        result = subprocess.run(
            [sys.executable, "-m", "modelb_axi", "--yes", "--harnesses", "pi",
             "--stacks", "python", "--modelb-home", str(self.modelb_home),
             "--target-root", str(self.target_root)],
            capture_output=True, text=True, timeout=90,
            stdin=subprocess.DEVNULL, env=env,
        )
        axi = decode_axi(result.stdout)
        self.assertEqual(
            axi.get("outcome"), "installed",
            f"precondition: the install must reach `installed`; exit="
            f"{result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        return axi

    @staticmethod
    def _policy(permission: dict, comment: str | None = None) -> str:
        text = json.dumps({"permission": permission}, indent=2) + "\n"
        return f"// {comment}\n{text}" if comment else text

    def test_absent_global_config_is_reported_absent_and_not_created(self):
        axi = self._install()
        self.assertEqual(axi.get("global_permission_policy"), "absent", f"axi={axi!r}")
        self.assertNotIn("global_permission_missing_tools", axi)
        self.assertFalse(
            self.global_policy.exists(),
            "§S3 / Non-goals: the installer never writes the global config",
        )

    def test_global_config_without_star_fallback_is_no_fallback(self):
        before = self._seed_global(
            self._policy(dict.fromkeys(sorted(expected_allow_tools()), "allow")),
        )
        axi = self._install()
        self.assertEqual(axi.get("global_permission_policy"), "no-fallback", f"axi={axi!r}")
        self.assertNotIn("global_permission_missing_tools", axi)
        self.assertEqual(self.global_policy.read_bytes(), before, "global config untouched")

    def test_global_config_lacking_workflow_tools_names_them(self):
        dispatch_tool = _requirements.requirement("dispatch")["tools"][0]
        permission = {"*": "ask"}
        permission.update(dict.fromkeys(sorted(expected_allow_tools()), "allow"))
        permission[dispatch_tool] = "ask"   # present but not allowed -> missing
        del permission["ask_parent"]        # absent -> missing
        before = self._seed_global(self._policy(permission))
        axi = self._install()
        self.assertEqual(axi.get("global_permission_policy"), "missing-tools", f"axi={axi!r}")
        self.assertEqual(
            sorted(axi.get("global_permission_missing_tools") or []),
            sorted([dispatch_tool, "ask_parent"]),
            f"P2: the missing workflow tools are named, exactly; axi={axi!r}",
        )
        self.assertEqual(self.global_policy.read_bytes(), before, "global config untouched")

    def test_global_config_with_fallback_and_every_workflow_tool_is_ok(self):
        permission = {"*": "ask"}
        permission.update(dict.fromkeys(sorted(expected_allow_tools()), "allow"))
        before = self._seed_global(self._policy(permission, comment="user's own policy"))
        axi = self._install()
        self.assertEqual(axi.get("global_permission_policy"), "ok", f"axi={axi!r}")
        self.assertNotIn("global_permission_missing_tools", axi)
        self.assertEqual(self.global_policy.read_bytes(), before, "global config untouched")

    def test_unparseable_global_config_is_unknown(self):
        before = self._seed_global('{ "permission": { "*": "ask", \n')
        axi = self._install()
        self.assertEqual(axi.get("global_permission_policy"), "unknown", f"axi={axi!r}")
        self.assertNotIn("global_permission_missing_tools", axi)
        self.assertEqual(self.global_policy.read_bytes(), before, "global config untouched")


if __name__ == "__main__":
    unittest.main()
