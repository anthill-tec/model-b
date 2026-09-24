"""``init`` reports Pi project trust (CR-MDB-037 §S4).

When ``init`` writes anything under ``<target>/.pi/extensions/`` it resolves
Pi's SAVED trust decision for the target — the entry for the target or its
closest ancestor in ``<agent-dir>/trust.json``, else ``defaultProjectTrust``
from ``<agent-dir>/settings.json`` (``ask`` when unset) — and reports
``trust: trusted | untrusted | ask | unknown`` in its envelope. ``untrusted``
and ``ask`` WARN that the hooks and permission policy will not load until
the project is trusted, naming ``/trust`` and stating that a command-line
override or an extension may still decide otherwise. An unreadable or
unrecognised file gives ``unknown``, never a crash. Model B never edits
``trust.json``. The scaffolded ``AGENTS.md`` capability section carries a
project-trust line with ``/trust``.

Isolation: every run pins ``HOME`` and ``PI_CODING_AGENT_DIR`` to a
throw-away sandbox; the real ``~/.pi`` (whose ``trust.json`` holds
``"/home/antonyj": false``) is never read.

Stdlib only.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.pi_capability_sandbox import (
    AGENT_DIR_ENV,
    make_home,
    make_provisioned_agent_dir,
    write_settings,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

_INIT_FLAGS = (
    "--name", "X", "--token", "xproj", "--acronym", "XP",
    "--mode", "solo", "--repo-shape", "standalone",
    "--stacks", "python", "--owner", "tester",
)

_TRUST_STATES = ("trusted", "untrusted", "ask", "unknown")


def decode_axi(stdout: str) -> dict:
    from modelb_axi.toon import decode
    try:
        return decode(stdout).get("axi", {})
    except Exception:  # noqa: BLE001 -- a non-envelope stdout is reported by the caller
        return {}


def md_section(content: str, heading_prefix: str) -> str:
    """The Markdown section whose heading starts with ``heading_prefix``,
    up to the next ``## `` heading; ``""`` when absent."""
    out: list[str] = []
    inside = False
    for line in content.splitlines():
        if not inside and line.startswith(heading_prefix):
            inside = True
            out.append(line)
            continue
        if inside and line.startswith("## "):
            break
        if inside:
            out.append(line)
    return "\n".join(out)


def trust_warnings(axi: dict) -> list[str]:
    """Envelope warnings that name ``/trust``."""
    return [w for w in axi.get("warnings") or [] if "/trust" in str(w)]


class _TrustSandbox(unittest.TestCase):
    """Per-test sandbox: HOME, PI_CODING_AGENT_DIR, MODELB_HOME and a
    target at ``<root>/work/proj`` so both an exact and an ancestor entry
    can be written for it."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modelb-cr037-trust-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.home = make_home(self.root / "home", crucible_manifest=False)
        self.agent_dir = make_provisioned_agent_dir(self.root / "agent")
        self.modelb_home = self.root / "modelb-home"
        self.work = self.root / "work"
        self.target = self.work / "proj"
        self.target.mkdir(parents=True)
        self.write_install_toml(("pi",))

    def write_install_toml(self, harnesses) -> None:
        hooks_scripts_dir = self.modelb_home / ".agents" / "hooks" / "scripts"
        harnesses_toml = ", ".join(f'"{h}"' for h in harnesses)
        self.modelb_home.mkdir(parents=True, exist_ok=True)
        (self.modelb_home / "install.toml").write_text(
            "[install]\n"
            'version = "0.1.0"\n'
            f"harnesses = [{harnesses_toml}]\n"
            'asset_root = "/tmp/does-not-matter-for-this-test"\n'
            f'hooks_scripts_dir = "{hooks_scripts_dir}"\n'
            "\n[deps]\nuv = \"present\"\n\n[files]\n",
            encoding="utf-8",
        )

    def write_trust(self, payload) -> bytes:
        """``<agent-dir>/trust.json``: a str verbatim, else JSON."""
        path = self.agent_dir / "trust.json"
        text = payload if isinstance(payload, str) else json.dumps(payload, indent=2) + "\n"
        path.write_text(text, encoding="utf-8")
        return path.read_bytes()

    def set_default_project_trust(self, value: str) -> None:
        settings = json.loads((self.agent_dir / "settings.json").read_text(encoding="utf-8"))
        settings["defaultProjectTrust"] = value
        write_settings(self.agent_dir, settings)

    def run_init(self, *, dry_run=False, target: Path | None = None):
        env = dict(os.environ)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
        env["HOME"] = str(self.home)
        env[AGENT_DIR_ENV] = str(self.agent_dir)
        post = ["--no-commit"] + (["--dry-run"] if dry_run else [])
        result = subprocess.run(
            [sys.executable, "-m", "modelb_axi", "--yes", "init", *_INIT_FLAGS,
             "--target", str(target or self.target),
             "--modelb-home", str(self.modelb_home), *post],
            capture_output=True, text=True, timeout=90,
            stdin=subprocess.DEVNULL, env=env,
        )
        self.assertEqual(
            result.returncode, 0,
            f"§S4: init must succeed (never crash on trust); stdout="
            f"{result.stdout!r} stderr={result.stderr!r}",
        )
        axi = decode_axi(result.stdout)
        self.assertIs(axi.get("ok"), True, f"precondition: ok envelope; {result.stdout!r}")
        return axi

    def assert_untrusted_warning(self, axi: dict, state: str) -> None:
        hits = trust_warnings(axi)
        self.assertEqual(
            len(hits), 1,
            f"§S4: `{state}` WARNs exactly once, naming /trust; warnings="
            f"{axi.get('warnings')!r}",
        )
        text = hits[0].lower()
        for needle in ("hook", "permission", "override", "extension"):
            with self.subTest(needle=needle):
                self.assertIn(
                    needle, text,
                    f"§S4: the `{state}` warning names what will not load (hooks, "
                    f"permission policy) and that an override or extension may "
                    f"decide otherwise; got {hits[0]!r}",
                )


class ProjectTrustResolutionTest(_TrustSandbox):
    """§S4 AC1/AC2 — one test per saved-decision case, against a sandboxed
    ``PI_CODING_AGENT_DIR``; ``trust.json`` is byte-identical afterwards."""

    def test_exact_true_entry_is_trusted_and_does_not_warn(self):
        # The exact entry wins over a less specific (ancestor) `false`.
        before = self.write_trust({str(self.work): False, str(self.target): True})
        axi = self.run_init()
        self.assertEqual(axi.get("trust"), "trusted", f"axi={axi!r}")
        self.assertEqual(trust_warnings(axi), [], "§S4: trusted gives no /trust warning")
        self.assertEqual((self.agent_dir / "trust.json").read_bytes(), before)

    def test_closest_ancestor_false_entry_is_untrusted_and_warns(self):
        # The /home/antonyj shape: a false entry on an ancestor. The CLOSEST
        # ancestor decides, over a farther `true`.
        before = self.write_trust({str(self.root): True, str(self.work): False})
        axi = self.run_init()
        self.assertEqual(axi.get("trust"), "untrusted", f"axi={axi!r}")
        self.assert_untrusted_warning(axi, "untrusted")
        self.assertEqual(
            (self.agent_dir / "trust.json").read_bytes(), before,
            "§S4: Model B never edits trust.json",
        )

    def test_no_entry_and_no_setting_is_ask_and_warns(self):
        before = self.write_trust({str(self.root / "elsewhere"): True})
        axi = self.run_init()
        self.assertEqual(axi.get("trust"), "ask", f"axi={axi!r}")
        self.assert_untrusted_warning(axi, "ask")
        self.assertEqual((self.agent_dir / "trust.json").read_bytes(), before)

    def test_string_prefix_that_is_not_an_ancestor_does_not_decide(self):
        # `<root>/wo` is a string prefix of `<root>/work/proj` but not an
        # ancestor directory: it must not match.
        self.write_trust({str(self.root / "wo"): False, str(self.work / "pr"): True})
        axi = self.run_init()
        self.assertEqual(axi.get("trust"), "ask", f"§S4: ancestry is by path component; axi={axi!r}")

    def test_default_project_trust_always_is_trusted(self):
        before = self.write_trust({str(self.root / "elsewhere"): False})
        self.set_default_project_trust("always")
        axi = self.run_init()
        self.assertEqual(axi.get("trust"), "trusted", f"axi={axi!r}")
        self.assertEqual(trust_warnings(axi), [], "§S4: trusted gives no /trust warning")
        self.assertEqual((self.agent_dir / "trust.json").read_bytes(), before)

    def test_malformed_trust_json_is_unknown_without_crashing(self):
        before = self.write_trust('{"/tmp": tru\n')
        axi = self.run_init()
        self.assertEqual(axi.get("trust"), "unknown", f"axi={axi!r}")
        self.assertEqual((self.agent_dir / "trust.json").read_bytes(), before)


class ProjectTrustFieldPresenceTest(_TrustSandbox):
    """§S4 AC3 — ``trust`` is reported only when init writes under
    ``.pi/extensions/``: a Pi init reports one of the four states; a
    no-Pi init and a ``--dry-run`` (writes nothing) report no field."""

    def test_trust_field_present_only_when_init_writes_under_pi_extensions(self):
        axi = self.run_init()
        self.assertIn(
            axi.get("trust"), _TRUST_STATES,
            f"§S4: a Pi init writes under .pi/extensions/ and reports trust; axi={axi!r}",
        )

        dry_target = self.work / "dry"
        dry_target.mkdir()
        dry = self.run_init(dry_run=True, target=dry_target)
        self.assertNotIn("trust", dry, f"§S4: --dry-run writes nothing, reports no trust; {dry!r}")

        self.write_install_toml(("claude-code",))
        cc_target = self.work / "cc"
        cc_target.mkdir()
        cc = self.run_init(target=cc_target)
        self.assertFalse((cc_target / ".pi" / "extensions").exists(), "precondition: no .pi writes")
        self.assertNotIn("trust", cc, f"§S4: nothing under .pi/extensions/, no trust field; {cc!r}")
        self.assertEqual(trust_warnings(cc), [])


class AgentsMdProjectTrustLineTest(_TrustSandbox):
    """§S4 AC4 — the scaffolded AGENTS.md capability section carries one
    line: the project's hooks and permission policy need project trust,
    remediation ``/trust``."""

    def test_capability_section_carries_the_project_trust_line(self):
        self.run_init()
        content = (self.target / "AGENTS.md").read_text(encoding="utf-8")
        section = md_section(content, "## Harness capability contract")
        self.assertTrue(section, f"precondition: capability section present; {content!r}")
        lines = [line for line in section.splitlines() if "/trust" in line]
        self.assertEqual(
            len(lines), 1,
            f"§S4: exactly one project-trust line with /trust in the capability "
            f"section; got section={section!r}",
        )
        line = lines[0].lower()
        for needle in ("trust", "hook", "permission"):
            with self.subTest(needle=needle):
                self.assertIn(needle, line, f"§S4: the line names {needle!r}; got {lines[0]!r}")


if __name__ == "__main__":
    unittest.main()
