"""``modelb-axi agents`` re-renders the project's permission policy (CR-MDB-077 §S3).

When the resolved harnesses include ``pi``, the verb places the project's policy,
``.pi/extensions/pi-permission-system/config.json``, after its agent definitions:

- through ``place_project_policy``, under ``init``'s ownership rules — a hand-modified
  policy is skipped unless ``--force-managed``, an unmarked one is never written;
- for the lean-ctx verdict the installation recorded, the one the agents use;
- reported, by its project-relative path, in the envelope's ``written``, ``unchanged``,
  ``skipped`` or ``unmanaged`` list beside the agent files, a skipped or unmanaged policy
  getting the warning a skipped or unmanaged agent file gets;
- unchanged by ``--stacks``;
- inside the agents' I/O-error handling (exit 3, ``ok: false``, the error named) and never
  after a validation refusal (exit 2).

The verb's help, description and stderr progress line name the permission policy.

How the tests compare (§S3 AC): a written policy equals
``permission_policy.render_policy(lean_ctx=<the recorded verdict>)`` computed in-process
under the subprocess's ``HOME`` and ``PATH`` (the render reads both, through
``_harness_code_reads``); a skipped or unmanaged policy is byte-identical to its seed.

Every case drives the real entry point, ``python3 -m modelb_axi agents``, in a SEEDED
sandbox project — a ``.env`` recording ``PROJECT_STACKS`` and a sandbox ``install.toml``
recording the ``pi`` harness and a lean-ctx verdict — not a full ``init`` per case. Not
tested: the no-Pi case (the roster is Pi alone, so no run reaches it; the spec says no test
drives it).

Isolation (NON-NEGOTIABLE): every subprocess runs with ``HOME``, ``MODELB_HOME``,
``XDG_DATA_HOME`` and ``PI_CODING_AGENT_DIR`` pinned under a per-test temp dir.

Stdlib only.
"""

import argparse
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

from modelb_axi import agents, permission_policy
from modelb_axi.cli import _build_parser
from tests._helpers import SANDESH_ALLOWED_TOOLS, decode_axi
from tests._helpers import sha256_text as _sha256
from tests.pi_capability_sandbox import AGENT_DIR_ENV, make_agent_dir, make_home

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATOR_DIR = REPO_ROOT / "generator"

POLICY_REL = str(Path(".pi") / "extensions" / "pi-permission-system" / "config.json")
STACK = "python"
ROLES = ("red", "green", "verify", "fix")
AGENT_RELS = tuple(str(Path(".pi") / "agents" / f"{STACK}-{role}-agent.md") for role in ROLES)
#: The definition each "same warning" case seeds beside the policy.
SKIPPED_AGENT_REL = AGENT_RELS[0]
UNMANAGED_AGENT_REL = AGENT_RELS[1]

DETECTED, ABSENT = "detected", "absent"
#: A lean-ctx tool named anywhere in a policy.
_CTX_TOOL_RE = re.compile(r"\bctx_\w+")

UNMARKED_POLICY = '{\n  "permission": {\n    "*": "ask"\n  }\n}\n'
UNMARKED_AGENT = "# the project's own agent\n\nNo marker here.\n"


def _permission(text: str) -> dict:
    """The ``permission`` map of a policy text, its ``//`` marker line dropped."""
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("//"))
    return json.loads(body)["permission"]


class _AgentsVerbPolicyCase(unittest.TestCase):
    """A seeded sandbox project and the sandbox the verb runs in."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modelb-cr077-agents-policy-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.home = make_home(self.root / "home", crucible_manifest=False)
        self.agent_dir = make_agent_dir(self.root / "pi-agent", packages=[], on_disk=())
        self.modelb_home = self.root / "modelb-home"
        self.modelb_home.mkdir()
        self.xdg = self.root / "xdg"
        self.xdg.mkdir()
        self.project = self.root / "proj"
        self.project.mkdir()
        (self.project / ".env").write_text(f"PROJECT_STACKS={STACK}\n", encoding="utf-8")
        self.policy = self.project / POLICY_REL
        self.path = os.environ.get("PATH", "")
        self.write_install(DETECTED)

    # ---------------------------------------------------------------- fixtures ----

    def write_install(self, lean_ctx: str) -> None:
        """The sandbox ``install.toml``: the ``pi`` harness and ``lean_ctx`` as the
        recorded lean-ctx verdict; its asset root absent, so the agents render from this
        checkout's ``generator/``."""
        (self.modelb_home / "install.toml").write_text(
            "[install]\n"
            'version = "0.1.0"\n'
            'harnesses = ["pi"]\n'
            f'asset_root = "{self.modelb_home / "no-asset-root-here"}"\n'
            f'stacks = ["{STACK}"]\n'
            "\n[deps]\n"
            'uv = "detected"\n'
            "\n[capabilities]\n"
            f'"lean-ctx" = "{lean_ctx}"\n',
            encoding="utf-8",
        )

    def env(self) -> dict:
        env = dict(os.environ)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing if existing else "")
        env.update({"HOME": str(self.home), "MODELB_HOME": str(self.modelb_home),
                    "XDG_DATA_HOME": str(self.xdg), AGENT_DIR_ENV: str(self.agent_dir),
                    "PATH": self.path})
        for name in ("HOME", "MODELB_HOME", "XDG_DATA_HOME", AGENT_DIR_ENV):
            self.assertTrue(env[name].startswith(str(self.root)), f"sandbox guard: {name}")
        return env

    def run_agents(self, *extra: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        """``python3 -m modelb_axi --modelb-home <sandbox> agents <extra>`` from the project's
        root (or ``cwd``)."""
        return subprocess.run(
            [sys.executable, "-m", "modelb_axi", "--modelb-home", str(self.modelb_home),
             "agents", *extra],
            cwd=str(cwd or self.project), capture_output=True, text=True, timeout=120,
            stdin=subprocess.DEVNULL, env=self.env(),
        )

    def agents_ok(self, *extra: str) -> tuple[dict, subprocess.CompletedProcess]:
        result = self.run_agents(*extra)
        axi = decode_axi(result.stdout)
        self.assertEqual((result.returncode, axi.get("ok")), (0, True),
                         f"the verb succeeds; stdout={result.stdout!r} stderr={result.stderr!r}")
        return axi, result

    def expected_policy(self, lean_ctx: bool) -> str:
        """``render_policy(lean_ctx=...)`` under the subprocess's ``HOME`` and ``PATH``."""
        with mock.patch.dict(os.environ, {"HOME": str(self.home), "PATH": self.path}):
            return permission_policy.render_policy(lean_ctx=lean_ctx)

    def seed(self, rel: str, text: str) -> Path:
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def rendered_agent(self, rel: str) -> str:
        """The definition the verb renders at ``rel`` for a present lean-ctx."""
        texts = agents.render_definitions(
            [STACK], ["pi"], GENERATOR_DIR / "templates", GENERATOR_DIR / "stacks",
            lean_ctx=True)
        return texts[rel]

    def hand_modified_policy(self) -> str:
        """The current render's marker line over a hand-edited body."""
        first, _, rest = self.expected_policy(True).partition("\n")
        data = json.loads(rest)
        data["permission"]["bash"] = "allow"
        edited = f"{first}\n{json.dumps(data, indent=2)}\n"
        self.assertEqual(permission_policy.ownership_state(edited), agents.OWNED_HAND_MODIFIED,
                         "fixture precondition: a hand-modified policy")
        return edited

    def older_intact_policy(self) -> str:
        """A render from before the Sandesh tools were allowed: the current body less every
        ``sandesh_*`` entry, under an intact marker."""
        _first, _, rest = self.expected_policy(True).partition("\n")
        data = json.loads(rest)
        for name in [k for k in data["permission"] if k.startswith("sandesh_")]:
            del data["permission"][name]
        body = json.dumps(data, indent=2) + "\n"
        older = f"{permission_policy.MARKER_PREFIX}{_sha256(body)}\n{body}"
        self.assertEqual(permission_policy.ownership_state(older), agents.OWNED_INTACT,
                         "fixture precondition: an intact marker")
        self.assertNotEqual(older, self.expected_policy(True),
                            "fixture precondition: an older render, not today's")
        return older

    # -------------------------------------------------------------- assertions ----

    def assert_listed_once(self, axi: dict, bucket: str, rel: str = POLICY_REL) -> None:
        """``rel`` sits in ``bucket`` exactly once and in no other outcome list."""
        for key in ("written", "unchanged", "skipped", "unmanaged"):
            listed = axi.get(key) or []
            with self.subTest(bucket=key):
                self.assertEqual(listed.count(rel), 1 if key == bucket else 0,
                                 f"§S3: {rel} is reported in `{bucket}` only; {key}={listed!r}")

    def assert_same_warning(self, axi: dict, agent_rel: str) -> None:
        """The policy's warning is the one ``agent_rel`` gets, with the policy's path."""
        warnings = axi.get("warnings") or []
        agent_hits = [w for w in warnings if agent_rel in w]
        self.assertEqual(len(agent_hits), 1,
                         f"fixture precondition: one warning for {agent_rel}; {warnings!r}")
        expected = agent_hits[0].replace(agent_rel, POLICY_REL)
        self.assertEqual([w for w in warnings if POLICY_REL in w], [expected],
                         "§S3: the policy gets the warning an agent file gets")


# ---------------------------------------------------------------------------
# §S3 — the wired path
# ---------------------------------------------------------------------------

class AgentsVerbPlacesThePolicyTest(_AgentsVerbPolicyCase):
    """§S3 AC "the wired path", one test per bullet."""

    def test_an_absent_policy_is_written_after_the_agents_and_reported_in_written(self):
        self.assertFalse(self.policy.exists(), "fixture precondition: no policy yet")
        axi, _ = self.agents_ok()
        self.assertTrue(self.policy.is_file(), "§S3: the verb writes the missing policy")
        self.assertEqual(self.policy.read_text(encoding="utf-8"), self.expected_policy(True),
                         "§S3: the written policy is the recorded verdict's render")
        self.assert_listed_once(axi, "written")
        written = axi.get("written") or []
        self.assertEqual(sorted(written), sorted((*AGENT_RELS, POLICY_REL)),
                         "the agent files and the policy, nothing else")
        self.assertGreater(written.index(POLICY_REL), max(written.index(r) for r in AGENT_RELS),
                           "§S3: the policy is placed after the agent definitions")
        permission = _permission(self.policy.read_text(encoding="utf-8"))
        self.assertEqual({t for t in SANDESH_ALLOWED_TOOLS if permission.get(t) == "allow"},
                         set(SANDESH_ALLOWED_TOOLS), "the re-rendered policy allows them")

    def test_an_identical_policy_is_reported_in_unchanged(self):
        current = self.expected_policy(True)
        self.seed(POLICY_REL, current)
        axi, _ = self.agents_ok()
        self.assertEqual(self.policy.read_text(encoding="utf-8"), current)
        self.assert_listed_once(axi, "unchanged")

    def test_an_older_render_with_an_intact_marker_is_rewritten_and_reported_in_written(self):
        self.seed(POLICY_REL, self.older_intact_policy())
        axi, _ = self.agents_ok()
        self.assertEqual(self.policy.read_text(encoding="utf-8"), self.expected_policy(True),
                         "§S3: an intact older render is rewritten to today's")
        self.assert_listed_once(axi, "written")

    def test_a_hand_modified_policy_is_skipped_with_the_warning_and_rewritten_when_forced(self):
        edited = self.hand_modified_policy()
        self.seed(POLICY_REL, edited)
        self.seed(SKIPPED_AGENT_REL, self.rendered_agent(SKIPPED_AGENT_REL) + "\nhand edit\n")
        axi, result = self.agents_ok()
        self.assertEqual(self.policy.read_bytes(), edited.encode("utf-8"),
                         "§S3: a skipped policy is byte-identical to its seed")
        self.assert_listed_once(axi, "skipped")
        self.assertEqual(sorted(axi.get("skipped") or []), sorted((SKIPPED_AGENT_REL, POLICY_REL)))
        self.assert_same_warning(axi, SKIPPED_AGENT_REL)
        self.assertIn(POLICY_REL, result.stderr, "the warning reaches stderr too")

        forced, _ = self.agents_ok("--force-managed")
        self.assertEqual(self.policy.read_text(encoding="utf-8"), self.expected_policy(True),
                         "§S3: --force-managed rewrites a hand-modified policy")
        self.assert_listed_once(forced, "written")

    def test_an_unmarked_policy_is_never_written_and_is_reported_unmanaged_with_the_warning(self):
        self.seed(POLICY_REL, UNMARKED_POLICY)
        self.seed(UNMANAGED_AGENT_REL, UNMARKED_AGENT)
        for extra in ((), ("--force-managed",)):
            with self.subTest(flags=extra):
                axi, _ = self.agents_ok(*extra)
                self.assertEqual(self.policy.read_bytes(), UNMARKED_POLICY.encode("utf-8"),
                                 "§S3: an unmanaged policy is byte-identical to its seed")
                self.assert_listed_once(axi, "unmanaged")
                self.assertEqual(sorted(axi.get("unmanaged") or []),
                                 sorted((UNMANAGED_AGENT_REL, POLICY_REL)))
                self.assert_same_warning(axi, UNMANAGED_AGENT_REL)

    def test_switching_the_recorded_verdict_to_absent_rewrites_the_lean_ctx_absent_render(self):
        self.seed(POLICY_REL, self.expected_policy(True))
        self.write_install(ABSENT)
        axi, _ = self.agents_ok()
        text = self.policy.read_text(encoding="utf-8")
        self.assertEqual(text, self.expected_policy(False),
                         "§S3: the policy follows the recorded verdict, absent")
        self.assert_listed_once(axi, "written")
        self.assertEqual(_permission(text).get("bash"), "allow", "lean-ctx absent allows bash")
        self.assertEqual(_CTX_TOOL_RE.findall(text), [], "and names no ctx_* tool")

        self.write_install(DETECTED)
        back, _ = self.agents_ok()
        self.assertEqual(self.policy.read_text(encoding="utf-8"), self.expected_policy(True),
                         "§S3: and back to the lean-ctx render when it is detected again")
        self.assert_listed_once(back, "written")

    def test_the_stacks_flag_leaves_an_intact_current_policy_byte_identical(self):
        current = self.expected_policy(True)
        self.seed(POLICY_REL, current)
        axi, _ = self.agents_ok("--stacks", "python,rust")
        self.assertEqual(axi.get("stacks"), ["python", "rust"], "fixture: the new stack set")
        self.assertEqual(self.policy.read_bytes(), current.encode("utf-8"),
                         "§S3: --stacks changes nothing in the policy")
        self.assert_listed_once(axi, "unchanged")


#: CR-MDB-089 §S2 — the process tool and the read-only web tools the policy now allows.
PROCESS_AND_WEB_TOOLS = ("process", "web_fetch", "web_search")


class AgentsVerbAllowsTheProcessAndWebToolsTest(_AgentsVerbPolicyCase):
    """CR-MDB-089 §S3, the wired path: ``python3 -m modelb_axi agents`` in a seeded sandbox
    project rewrites an intact policy rendered without the three tools to the new render, and
    skips a hand-modified one unless ``--force-managed``."""

    def policy_without_the_three(self) -> str:
        """The current render less ``process``, ``web_fetch`` and ``web_search``, its marker
        re-computed (``agents.sha256_text``) so it is intact."""
        _first, _, rest = self.expected_policy(True).partition("\n")
        data = json.loads(rest)
        for tool in PROCESS_AND_WEB_TOOLS:
            data["permission"].pop(tool, None)
        body = json.dumps(data, indent=2) + "\n"
        older = f"{permission_policy.MARKER_PREFIX}{agents.sha256_text(body)}\n{body}"
        self.assertEqual(permission_policy.ownership_state(older), agents.OWNED_INTACT,
                         "fixture precondition: an intact marker")
        self.assertEqual([t for t in PROCESS_AND_WEB_TOOLS if t in _permission(older)], [],
                         "fixture precondition: the seed allows none of the three")
        return older

    def test_an_intact_policy_without_the_three_tools_is_rewritten_to_allow_them(self):
        self.seed(POLICY_REL, self.policy_without_the_three())
        axi, _ = self.agents_ok()
        text = self.policy.read_text(encoding="utf-8")
        self.assertEqual({t: _permission(text).get(t) for t in PROCESS_AND_WEB_TOOLS},
                         dict.fromkeys(PROCESS_AND_WEB_TOOLS, "allow"),
                         "CR-MDB-089 §S3: the re-rendered policy allows the three tools")
        self.assertEqual(text, self.expected_policy(True), "it is today's render")
        self.assert_listed_once(axi, "written")

    def test_a_hand_modified_policy_without_the_three_is_skipped_until_forced(self):
        first, _, rest = self.policy_without_the_three().partition("\n")
        data = json.loads(rest)
        data["permission"]["bash"] = "allow"
        edited = f"{first}\n{json.dumps(data, indent=2)}\n"
        self.assertEqual(permission_policy.ownership_state(edited), agents.OWNED_HAND_MODIFIED,
                         "fixture precondition: a hand-modified policy")
        self.seed(POLICY_REL, edited)
        axi, _ = self.agents_ok()
        self.assertEqual(self.policy.read_bytes(), edited.encode("utf-8"),
                         "CR-MDB-089 §S3: a hand-modified policy is skipped, byte-identical")
        self.assert_listed_once(axi, "skipped")
        forced, _ = self.agents_ok("--force-managed")
        text = self.policy.read_text(encoding="utf-8")
        self.assertEqual({t: _permission(text).get(t) for t in PROCESS_AND_WEB_TOOLS},
                         dict.fromkeys(PROCESS_AND_WEB_TOOLS, "allow"),
                         "CR-MDB-089 §S3: --force-managed rewrites it to allow the three tools")
        self.assert_listed_once(forced, "written")


# ---------------------------------------------------------------------------
# §S3 — failure paths
# ---------------------------------------------------------------------------

class AgentsVerbPolicyFailurePathsTest(_AgentsVerbPolicyCase):
    """§S3 AC "failure paths"."""

    def test_an_unwritable_policy_path_exits_3_with_ok_false_naming_the_error(self):
        blocker = self.seed(str(Path(".pi") / "extensions"), "not a directory\n")
        result = self.run_agents()
        axi = decode_axi(result.stdout)
        self.assertEqual((result.returncode, axi.get("verb"), axi.get("ok")), (3, "agents", False),
                         f"§S3: an I/O error exits 3 with an ok:false envelope; "
                         f"stdout={result.stdout!r} stderr={result.stderr!r}")
        warnings = axi.get("warnings") or []
        self.assertEqual(len(warnings), 1, f"one warning, the error; {warnings!r}")
        self.assertIn(str(Path(".pi") / "extensions"), warnings[0],
                      "§S3: the warning names the error, on the policy's path")
        self.assertEqual(sorted(axi.get("written") or []), sorted(AGENT_RELS),
                         "§S3: the envelope lists the files already written, the agents")
        self.assertEqual(blocker.read_text(encoding="utf-8"), "not a directory\n")

    def test_a_run_without_a_env_exits_2_and_creates_no_policy(self):
        (self.project / ".env").unlink()
        result = self.run_agents()
        axi = decode_axi(result.stdout)
        self.assertEqual((result.returncode, axi.get("ok")), (2, False),
                         f"§S3: a validation refusal exits 2; stderr={result.stderr!r}")
        self.assertFalse(self.policy.exists(), "§S3: a refused run writes no policy")
        self.assertFalse((self.project / ".pi").exists(), "nothing under .pi at all")


# ---------------------------------------------------------------------------
# §S3 — text
# ---------------------------------------------------------------------------

def _names_the_policy(text: str | None) -> bool:
    return "permission policy" in " ".join((text or "").split()).lower()


class AgentsVerbNamesThePolicyTest(_AgentsVerbPolicyCase):
    """§S3 AC "text": the ``agents`` subparser's help and description, and its stderr
    progress line, name the permission policy."""

    def _agents_subcommand(self) -> tuple[argparse.Action, argparse.ArgumentParser]:
        sub = next(a for a in _build_parser()._actions  # stdlib argparse: the declared actions
                   if isinstance(a, argparse._SubParsersAction))
        choice = next(a for a in sub._get_subactions() if a.dest == "agents")
        return choice, sub.choices["agents"]

    def test_the_help_and_the_description_name_the_permission_policy(self):
        choice, parser = self._agents_subcommand()
        self.assertTrue(_names_the_policy(choice.help), f"§S3: the help; {choice.help!r}")
        self.assertTrue(_names_the_policy(parser.description),
                        f"§S3: the description; {parser.description!r}")

    def test_the_stderr_progress_line_names_the_permission_policy(self):
        _axi, result = self.agents_ok()
        progress = [ln for ln in result.stderr.splitlines() if ln.startswith("modelb-axi: agents")]
        self.assertEqual(len(progress), 1, f"one progress line; stderr={result.stderr!r}")
        self.assertTrue(_names_the_policy(progress[0]), f"§S3: the progress line; {progress[0]!r}")

    def test_the_policy_checker_needs_the_phrase(self):
        self.assertTrue(_names_the_policy("re-render the agents and the\npermission  Policy"))
        self.assertFalse(_names_the_policy("re-render project agent definitions"))
        self.assertFalse(_names_the_policy("the policy and its permissions"))
        self.assertFalse(_names_the_policy(None))


if __name__ == "__main__":
    unittest.main()
