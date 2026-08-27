#!/usr/bin/env python3
# Owner: Model B (roundhouse/model-b) — adopted by CR-MDB-022 §S1.
# Consuming skills: none in-tree yet — run directly as the pre-`git flow release finish`
#   gate for skill-bundle projects; docs/research/DN-rationalization-plan-review.md
#   (Wave 3) is where the wiring is planned.
#
"""skill-release-gate — generic release gate for skill-bundle projects.

Runs BEFORE `git flow release finish` on any project that ships as an Agent Skill
bundle (Vercel `npx skills` / agentskills.io standard). It validates the *shipped
artifacts*, not the source tree, so it catches packaging + conformance regressions
the unit suite can't see.

Phases (each auto-skips when its config is absent):
  1. skill conformance — wraps the official `agentskills validate` (pip: skills-ref);
     auto-provisions it in a throwaway venv if not on PATH.
  2. engine build      — `python -m build --wheel`; asserts entry point + bundled
     package-data globs (+ optional exact counts) + forbidden entry points absent.
  3. clean install     — installs the wheel into a FRESH venv and confirms the
     console command + that it imports from site-packages (neutral cwd).
  4. lifecycle/AXI      — declarative checks run against the INSTALLED console over a
     THROWAWAY env/DB (each check: expect / expect_re / reject / json_type /
     allow_nonzero / combine_stderr), then teardown.

Config lives in the project's `pyproject.toml` under `[tool.skill-release]`
(or a standalone `.skill-release.toml`). Substitutions available in `env`,
check argv/cmd, and teardown: `$TMP` (a scratch dir) and `$THROWAWAY_DB`
(a unique per-run name). Nothing touches a live store.

  python3 ~/.agents/scripts/skill-release-gate.py [--project-dir .]

Exit 0 = all gates passed (safe to finish); non-zero = a gate failed.
Self-test: point a check's data outside its window (or break a value) — the gate must FAIL.
"""
import argparse
import datetime
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile

try:
    import tomllib
except ModuleNotFoundError:  # py<3.11
    import tomli as tomllib  # type: ignore

G, R, B, X = "\033[32m", "\033[31m", "\033[1m", "\033[0m"


class Gate:
    def __init__(self, project_dir, tmp):
        self.root = os.path.abspath(project_dir)
        self.tmp = tmp
        self.passed = 0
        self.failed = 0
        self.db = f"skillrelcheck_{os.getpid()}"
        self.today = datetime.date.today().isoformat()
        # $SOON = a date inside a typical renewal window; overridable to self-test the gate
        # (push it out of the window and the due-sweep-style checks must then FAIL).
        self.soon = os.environ.get(
            "SKILLGATE_SOON",
            (datetime.date.today() + datetime.timedelta(days=10)).isoformat())

    # ---- reporting ----
    def say(self, msg):
        print(f"\n{B}== {msg}{X}")

    def ok(self, msg, _detail=None):  # _detail ignored — lets `(ok if … else bad)(m, d)` work
        self.passed += 1
        print(f"  {G}PASS{X} {msg}")

    def bad(self, msg, detail=None):
        self.failed += 1
        print(f"  {R}FAIL{X} {msg}")
        if detail:
            for line in str(detail).rstrip().splitlines():
                print(f"      | {line}")

    def subst(self, s):
        return (s.replace("$TMP", self.tmp)
                 .replace("$THROWAWAY_DB", self.db)
                 .replace("$SOON", self.soon)
                 .replace("$TODAY", self.today))

    # ---- config ----
    @staticmethod
    def _extract(path):
        """A config file may nest under [tool.skill-release] (pyproject style) or be
        the config at top level (standalone .skill-release.toml)."""
        with open(path, "rb") as fh:
            doc = tomllib.load(fh)
        nested = doc.get("tool", {}).get("skill-release")
        return nested if nested is not None else doc

    def load_config(self, override=None):
        if override:
            return self._extract(override)
        pyproject = os.path.join(self.root, "pyproject.toml")
        if os.path.isfile(pyproject):
            with open(pyproject, "rb") as fh:
                cfg = tomllib.load(fh).get("tool", {}).get("skill-release")
            if cfg:
                return cfg
        standalone = os.path.join(self.root, ".skill-release.toml")
        if os.path.isfile(standalone):
            return self._extract(standalone)
        return None

    # ---- venv helper ----
    def make_venv(self, name, install=()):
        path = os.path.join(self.tmp, name)
        venv.EnvBuilder(with_pip=True).create(path)
        py = os.path.join(path, "bin", "python")
        if install:
            subprocess.run([py, "-m", "pip", "install", "-q", "--upgrade", "pip", *install],
                           check=True, capture_output=True)
        return path, py

    # =================== phase 1: skill conformance ===================
    def phase_skills(self, cfg):
        skcfg = cfg.get("skills", {})
        paths = skcfg.get("paths")
        if not paths:
            # auto-discover flat skills/<name>/SKILL.md and .claude/skills/<name>/
            paths = []
            for base in ("skills", ".claude/skills"):
                d = os.path.join(self.root, base)
                if os.path.isdir(d):
                    for entry in sorted(os.listdir(d)):
                        if os.path.isfile(os.path.join(d, entry, "SKILL.md")):
                            paths.append(os.path.join(base, entry))
        if not paths:
            return  # not a skill project — nothing to validate
        self.say("1. skill conformance (agentskills validate — skills-ref)")
        agentskills = shutil.which("agentskills")
        if not agentskills:
            print("  (agentskills not on PATH — provisioning skills-ref in a throwaway venv)")
            _, py = self.make_venv("srefvenv", install=["skills-ref"])
            agentskills = os.path.join(os.path.dirname(py), "agentskills")
        for rel in paths:
            skdir = os.path.join(self.root, rel)
            res = subprocess.run([agentskills, "validate", skdir], capture_output=True, text=True)
            if res.returncode == 0:
                self.ok(f"{rel}: {res.stdout.strip() or 'valid skill'}")
            else:
                self.bad(f"{rel}: agentskills validate failed", res.stdout + res.stderr)

    # =================== phase 2/3: engine build + install ===================
    def phase_engine(self, cfg):
        eng = cfg.get("engine")
        if not eng or not eng.get("build"):
            return None
        self.say("2. engine build + packaging invariants")
        _, buildpy = self.make_venv("buildvenv", install=["build"])
        dist = os.path.join(self.tmp, "dist")
        res = subprocess.run([buildpy, "-m", "build", "--wheel", "--outdir", dist, self.root],
                             capture_output=True, text=True)
        wheels = [f for f in os.listdir(dist)] if os.path.isdir(dist) else []
        whl = os.path.join(dist, next((w for w in wheels if w.endswith(".whl")), ""))
        if not whl.endswith(".whl") or not os.path.isfile(whl):
            self.bad("wheel build failed", res.stdout + res.stderr)
            return None
        self.ok(f"built {os.path.basename(whl)}")
        names = zipfile.ZipFile(whl).namelist()
        # entry point present / forbidden absent
        ep_txt = "\n".join(n for n in names if n.endswith("entry_points.txt"))
        ep_content = ""
        with zipfile.ZipFile(whl) as z:
            for n in names:
                if n.endswith("entry_points.txt"):
                    ep_content += z.read(n).decode()
        if "entry_point" in eng:
            (self.ok if eng["entry_point"] in ep_content else self.bad)(
                f"entry point '{eng['entry_point']}'", None if eng["entry_point"] in ep_content else ep_content)
        for forbidden in eng.get("forbid_entry_points", []):
            if re.search(rf"^\s*{re.escape(forbidden)}\s*=", ep_content, re.M):
                self.bad(f"forbidden entry point '{forbidden}' present")
            else:
                self.ok(f"no forbidden entry point '{forbidden}'")
        # wheel globs (+ optional exact counts)
        counts = eng.get("wheel_glob_counts", {})
        for glob, want in counts.items():
            rx = "^" + re.escape(glob).replace(r"\*", "[^/]*") + "$"
            got = sum(1 for n in names if re.match(rx, n))
            (self.ok if got == want else self.bad)(f"wheel bundles {want}x '{glob}' (found {got})")
        for glob in eng.get("wheel_globs", []):
            rx = "^" + re.escape(glob).replace(r"\*", "[^/]*") + "$"
            got = sum(1 for n in names if re.match(rx, n))
            (self.ok if got else self.bad)(f"wheel bundles '{glob}' (found {got})")

        # phase 3: clean install
        self.say("3. clean-install smoke (fresh venv — simulates pip install)")
        runpath, runpy = self.make_venv("runvenv")
        inst = subprocess.run([runpy, "-m", "pip", "install", "-q", whl], capture_output=True, text=True)
        console = os.path.join(runpath, "bin", eng.get("console", ""))
        if eng.get("console") and os.path.isfile(console):
            self.ok(f"console '{eng['console']}' installed")
        else:
            self.bad(f"console '{eng.get('console')}' not installed", inst.stdout + inst.stderr)
            return None
        if eng.get("import_check"):
            imp = subprocess.run([runpy, "-c", f"import {eng['import_check']},os;print(os.path.dirname({eng['import_check']}.__file__))"],
                                 capture_output=True, text=True, cwd=self.tmp)
            (self.ok if "site-packages" in imp.stdout else self.bad)(
                f"'{eng['import_check']}' imports from site-packages (not the repo)", imp.stdout + imp.stderr)
        return console

    # =================== phase 4: declarative lifecycle/AXI ===================
    def phase_checks(self, cfg, console):
        checks = cfg.get("check", [])
        if not checks or not console:
            return
        self.say("4. lifecycle + AXI conformance (declarative checks, throwaway env)")
        env = dict(os.environ)
        for k, v in cfg.get("env", {}).items():
            env[k] = self.subst(str(v))
        os.makedirs(os.path.join(self.tmp, "data"), exist_ok=True)
        for chk in checks:
            argv = chk.get("argv") or shlex.split(chk.get("cmd", ""))
            argv = [self.subst(a) for a in argv]
            res = subprocess.run([console, *argv], capture_output=True, text=True, env=env, cwd=self.tmp)
            out = res.stdout + (res.stderr if chk.get("combine_stderr") else "")
            name = chk.get("name", " ".join(argv) or "<bare>")
            fails = []
            if not chk.get("allow_nonzero") and res.returncode != 0:
                fails.append(f"exit {res.returncode}")
            for sub in chk.get("expect", []):
                if self.subst(sub) not in out:
                    fails.append(f"missing '{sub}'")
            for rx in chk.get("expect_re", []):
                if not re.search(rx, out):
                    fails.append(f"no regex match /{rx}/")
            for sub in chk.get("reject", []):
                if self.subst(sub) in out:
                    fails.append(f"unexpected '{sub}'")
            jt = chk.get("json_type")
            if jt:
                import json
                try:
                    val = json.loads(res.stdout)
                    want = list if jt in ("list", "array") else dict
                    if not isinstance(val, want):
                        fails.append(f"json is {type(val).__name__}, expected {jt}")
                except Exception as e:
                    fails.append(f"json parse error: {e}")
            if fails:
                self.bad(name, "; ".join(fails) + "\n" + out)
            else:
                self.ok(name)
        self.teardown(cfg, env)

    def teardown(self, cfg, env):
        td = cfg.get("teardown", {})
        dbname = td.get("drop_mongo_db")
        if dbname:
            dbname = self.subst(dbname)
            uri = env.get("VIDUSHI_MONGO_URI", "mongodb://127.0.0.1:27017")
            runpy = os.path.join(self.tmp, "runvenv", "bin", "python")
            if os.path.isfile(runpy):
                subprocess.run([runpy, "-c",
                                "import sys;from pymongo import MongoClient;"
                                "MongoClient(sys.argv[1],serverSelectionTimeoutMS=2000).drop_database(sys.argv[2])",
                                uri, dbname], capture_output=True)
        if td.get("cmd"):
            subprocess.run(self.subst(td["cmd"]), shell=True, env=env, capture_output=True)

    def run(self, cfg):
        self.phase_skills(cfg)
        console = self.phase_engine(cfg)
        self.phase_checks(cfg, console)
        self.say(f"RESULT: {self.passed} passed, {self.failed} failed")
        if self.failed:
            print(f"{R}Release gate FAILED — do not finish the release.{X}")
            return 1
        print(f"{G}Release gate PASSED — skill + artifact conformance OK; safe to `git flow release finish`.{X}")
        return 0


def main():
    ap = argparse.ArgumentParser(description="Generic release gate for skill-bundle projects.")
    ap.add_argument("--project-dir", default=".")
    ap.add_argument("--config", default=None, help="explicit config toml (else pyproject [tool.skill-release])")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="skill-relgate.")
    gate = Gate(a.project_dir, tmp)
    try:
        cfg = gate.load_config(a.config)
        if cfg is None:
            print(f"{R}no [tool.skill-release] config found in {gate.root}{X}")
            return 2
        return gate.run(cfg)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
