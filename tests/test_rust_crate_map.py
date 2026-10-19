"""``scripts/rust-crate-map.py``'s behaviour (CR-MDB-078 §S1.2, §S1.5 — AC1, AC4).

- ``FailedRenderTest`` — AC4: with a ``dot`` stand-in that exits 1, the crate map exits non-zero
  with an ``error:`` line and no ``Traceback``, and its JSON, markdown and Graphviz files exist.
- AC1, one class per §S1.2 behaviour, each over :data:`WORKSPACE` (a root package and five
  members in a real git repository):

  - ``LineClassificationTest`` — code, comment, blank and ``#[cfg(test)]``-gated code, per file
    and per crate;
  - ``AttributeSignalsTest`` — an attribute signal counts only as a real attribute at the start
    of a code line, never in a comment or a string; ``TODO`` / ``FIXME`` count in comments too;
  - ``DependencyEdgesTest`` — workspace-internal prod, dev and build edges, and fan-in;
  - ``TotalsAndReportsTest`` — the totals, the JSON and the markdown;
  - ``FallbackGraphTest`` / ``ConfiguredGraphTest`` — the Graphviz source without and with
    ``crate_map.toml`` (clusters, aggregates, ``omit_edges_into``; the root package's fallback
    cluster ``root``; the empty-crate and dead-code markers);
  - ``RenderTest`` — ``dot`` present, ``dot`` absent and ``--no-render``;
  - ``DefaultOutAndNameTest`` — the default ``--out`` and ``--name``.

The tool runs as a subprocess of the test interpreter under ``tests/_helpers.py``'s
``run_tool``: the test process's environment with only ``PATH`` and git's configuration
variables changed, a ``PATH`` of ``git`` and ``tar`` links plus the test's ``dot`` stand-in (never
the host's ``dot``), a temp working directory and ``--project-dir`` / ``--out`` pinned to temp
directories (§S4, AC15). The stand-in logs every call, so the test asserts it ran.

Stdlib only.
"""

import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from tests._helpers import git_repo, repo_git, run_tool, tool_bin_dir, write_files

CRATE_MAP = "rust-crate-map.py"

#: A one-member workspace in the form today's manifest reading already handles, so the only
#: fault is the render's.
ONE_MEMBER_WORKSPACE = {
    "Cargo.toml": '[workspace]\nmembers = ["crates/alpha"]\n',
    "crates/alpha/Cargo.toml": '[package]\nname = "alpha"\nversion = "0.1.0"\n',
    "crates/alpha/src/lib.rs": "pub fn alpha() -> u32 {\n    1\n}\n",
}


def _failing_dot(log: Path) -> str:
    """A ``dot`` stand-in that appends its argv to ``log`` and exits 1."""
    return f'#!/bin/sh\nprintf \'%s\\n\' "$*" >> \'{log}\'\nexit 1\n'


class FailedRenderTest(unittest.TestCase):
    """AC4 (§S1.5) — a failed render is reported, its other artifacts kept."""

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="mdb-rust-render-"))
        self.addCleanup(shutil.rmtree, self.work, True)
        self.dot_log = self.work / "dot.log"
        self.bin_dir = tool_bin_dir(self.work / "bin", {"dot": _failing_dot(self.dot_log)})
        self.project = write_files(self.work / "proj", ONE_MEMBER_WORKSPACE)
        self.out = self.work / "out"
        self.cwd = self.work / "cwd"
        self.cwd.mkdir()
        self.result = run_tool(CRATE_MAP, "--project-dir", self.project, "--out", self.out,
                               "--name", "fixture", bin_dir=self.bin_dir, cwd=self.cwd)

    def test_a_failing_dot_is_reported_with_an_error_line_and_the_other_files_kept(self):
        calls = self.dot_log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(calls), 1, "AC15: the dot stand-in ran exactly once")
        self.assertIn("-Tsvg", calls[0])
        report = json.loads((self.out / "crate_map_baseline.json").read_text(encoding="utf-8"))
        self.assertEqual([row["pkg"] for row in report["crates"]], ["alpha"])
        self.assertIn("| alpha |", (self.out / "crate_map_baseline.md").read_text(encoding="utf-8"))
        graph = (self.out / "fixture_crate_map.dot").read_text(encoding="utf-8")
        self.assertTrue(graph.startswith("digraph crate_map {"), graph[:80])
        self.assertIn('"alpha"', graph)
        output = self.result.stdout + self.result.stderr
        self.assertNotIn("Traceback", output, f"AC4: no traceback:\n{self.result.stderr}")
        self.assertNotEqual(self.result.returncode, 0, "AC4: a failed render exits non-zero")
        errors = [line for line in output.splitlines() if line.startswith("error:")]
        self.assertEqual(len(errors), 1, f"AC4: one 'error:' line, got:\n{output}")


# ------------------------------------------------------------------ AC1 ----

#: ``crates/core/src/lib.rs`` — 13 code lines (8 of them in the ``#[cfg(test)]`` block), 4
#: comment lines, 3 blank lines. Real attributes: one ``#[deprecated]``, one ``#[test]``. Not
#: attributes: ``#[allow(dead_code)]`` in a doc comment, ``#[ignore]`` in a string literal,
#: ``#[test]`` in a comment. ``TODO`` and ``FIXME`` each appear once, both in comments.
CORE_LIB = (
    "//! Core crate. #[allow(dead_code)] in a doc comment is not an attribute.\n"
    "// TODO: tidy this\n"
    "\n"
    "#[deprecated]\n"
    "pub fn core_fn() -> u32 {\n"
    "    // FIXME: later\n"
    '    let _s = "#[ignore]";\n'
    "    1\n"
    "}\n"
    "\n"
    "#[cfg(test)]\n"
    "mod tests {\n"
    "    use super::*;\n"
    "\n"
    "    // a #[test] inside a comment\n"
    "    #[test]\n"
    "    fn it_works() {\n"
    "        assert_eq!(core_fn(), 1);\n"
    "    }\n"
    "}\n"
)

#: ``crates/core/tests/integration.rs`` — 8 code lines, 2 blank; a ``#[tokio::test]``, a
#: ``#[test]`` and an ``#[ignore]``.
CORE_INTEGRATION = (
    "use core_lib::core_fn;\n"
    "\n"
    "#[tokio::test]\n"
    "async fn async_case() {\n"
    "    assert_eq!(core_fn(), 1);\n"
    "}\n"
    "\n"
    "#[test]\n"
    "#[ignore]\n"
    "fn slow_case() {}\n"
)

#: ``crates/util/src/lib.rs`` — 9 code lines, 1 comment, 2 blank. Gated: a ``#[cfg(test)]`` item
#: ending in ``;`` (2 lines) and a ``#[cfg(any(test, …))]`` item behind a comment (4 code lines),
#: so 6 gated and 3 prod — the prod function right after the ``;`` item is not gated.
UTIL_LIB = (
    "#[cfg(test)]\n"
    "use std::fmt;\n"
    "\n"
    "pub fn util_fn() -> u32 {\n"
    "    2\n"
    "}\n"
    "\n"
    '#[cfg(any(test, feature = "extra"))]\n'
    "// a comment between the attribute and its item\n"
    "fn helper() -> u8 {\n"
    "    0\n"
    "}\n"
)

#: ``tools/gen/src/main.rs`` — 22 code lines carrying ten ``#[allow(dead_code)]`` sites, the
#: dead-code marker's threshold.
GEN_MAIN = "".join(f"#[allow(dead_code)]\nfn unused_{i}() {{}}\n" for i in range(10)) + (
    "fn extra() {}\nfn main() {}\n"
)

#: The fixture workspace: a root package ``root`` and the members ``crates/core`` (package
#: ``core-lib``, so ``core_lib``), ``crates/util``, ``crates/app``, ``crates/empty`` (no source:
#: an empty crate) and ``tools/gen``. Internal edges: ``root`` → ``app``; ``util`` → ``core_lib``
#: and a build edge to ``gen``; ``app`` → ``util`` and ``core_lib`` (``.workspace`` form) and a dev
#: edge to ``gen``. ``serde`` is external and never an edge.
WORKSPACE = {
    "Cargo.toml": (
        '[package]\nname = "root"\nversion = "0.1.0"\n\n'
        "[workspace]\n"
        'members = ["crates/core", "crates/util", "crates/app", "crates/empty", "tools/gen"]\n\n'
        '[dependencies]\napp = { path = "crates/app" }\n'
    ),
    "src/main.rs": "fn main() {}\n",
    "crates/core/Cargo.toml": '[package]\nname = "core-lib"\nversion = "0.1.0"\n',
    "crates/core/src/lib.rs": CORE_LIB,
    "crates/core/tests/integration.rs": CORE_INTEGRATION,
    "crates/util/Cargo.toml": (
        '[package]\nname = "util"\nversion = "0.1.0"\n\n'
        '[dependencies]\ncore-lib = { path = "../core" }\nserde = "1"\n\n'
        '[build-dependencies]\ngen = { path = "../../tools/gen" }\n'
    ),
    "crates/util/src/lib.rs": UTIL_LIB,
    "crates/app/Cargo.toml": (
        '[package]\nname = "app"\nversion = "0.1.0"\n\n'
        '[dependencies]\nutil = { path = "../util" }\ncore-lib.workspace = true\n\n'
        '[dev-dependencies]\ngen = { path = "../../tools/gen" }\n'
    ),
    "crates/app/src/main.rs": "fn main() {\n    util::util_fn();\n}\n",
    "crates/app/examples/demo.rs": "fn main() {}\n",
    "crates/empty/Cargo.toml": '[package]\nname = "empty"\nversion = "0.1.0"\n',
    "tools/gen/Cargo.toml": '[package]\nname = "gen"\nversion = "0.1.0"\n',
    "tools/gen/src/main.rs": GEN_MAIN,
}

#: The crates in the reports' order: by total LOC, largest first.
CRATE_ORDER = ["gen", "core_lib", "util", "app", "root", "empty"]

#: The workspace's totals, counted by hand from :data:`WORKSPACE`.
TOTALS = {"prod_loc": 34, "src_testgated_loc": 14, "tests_dir_loc": 9, "total_loc": 57,
          "comment_loc": 5, "files": 7, "tests": 3, "ignored": 1, "allow_dead": 10,
          "deprecated": 1, "todo_fixme": 2}

#: A ``crate_map.toml``: edges into ``core_lib`` omitted, ``gen`` folded into the aggregate
#: ``toolchain``, and two clusters — ``app``, ``root`` and ``empty`` left unclustered.
CRATE_MAP_TOML = (
    "[render]\n"
    'omit_edges_into = ["core_lib"]\n\n'
    "[render.aggregates.toolchain]\n"
    'label = "toolchain (x1 bins)"\n'
    'pattern = "ge*"\n\n'
    "[clusters.base]\n"
    'label = "Base layer"\n'
    'color = "#ABCDEF"\n'
    'members = ["core_lib", "util"]\n\n'
    "[clusters.tools]\n"
    'label = "Tools"\n'
    'color = "#FEDCBA"\n'
    'members = ["toolchain"]\n'
)

#: A Graphviz label's line break as the ``.dot`` file carries it: a backslash and an ``n``.
NL = "\\n"


def _rendering_dot(log: Path) -> str:
    """A ``dot`` stand-in that appends its argv to ``log``, writes a one-line SVG to the path
    after ``-o`` and exits 0."""
    return (
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" >> '{log}'\n"
        'out=""; prev=""\n'
        'for a in "$@"; do [ "$prev" = "-o" ] && out="$a"; prev="$a"; done\n'
        "printf '<svg/>\\n' > \"$out\"\n"
        "exit 0\n"
    )


def _clusters(graph: str) -> dict:
    """``{cluster key: {"header": its label line, "nodes": [node ids in order]}}`` of a
    Graphviz source the crate map wrote."""
    clusters, current = {}, None
    for line in graph.splitlines():
        if line.startswith("  subgraph cluster_"):
            current = line[len("  subgraph cluster_"):].rstrip(" {")
            clusters[current] = {"header": None, "nodes": []}
        elif current is not None and line == "  }":
            current = None
        elif current is not None and line.startswith("    label="):
            clusters[current]["header"] = line.strip()
        elif current is not None and line.startswith('    "'):
            clusters[current]["nodes"].append(line.split('"')[1])
    return clusters


def _edges(graph: str) -> set:
    """The ``(source, target)`` edges of a Graphviz source the crate map wrote."""
    edges = set()
    for line in graph.splitlines():
        if " -> " in line:
            source, target = line.strip().rstrip(";").split(" -> ")
            edges.add((source.strip('"'), target.strip('"')))
    return edges


def _node_lines(graph: str, node: str) -> list:
    """Every node-statement line of ``node`` in a Graphviz source, stripped."""
    return [line.strip() for line in graph.splitlines()
            if line.strip().startswith(f'"{node}" [')]


class _CrateMapRun(unittest.TestCase):
    """One crate-map run over :data:`WORKSPACE` in a real git repository, shared by a class's
    tests: a ``PATH`` of ``git`` and ``tar`` links plus a logging ``dot`` stand-in, a temp working
    directory, ``--project-dir`` / ``--out`` pinned to temp directories (§S4, AC15). The run passes
    ``--no-render`` unless a subclass's :attr:`RENDER` is set, and writes :attr:`CONFIG`, when
    set, as ``<out>/crate_map.toml`` first."""

    RENDER = False
    CONFIG = None
    WITH_DOT = True

    @classmethod
    def setUpClass(cls):
        cls.work = Path(tempfile.mkdtemp(prefix="mdb-rust-crate-map-")).resolve()
        cls.addClassCleanup(shutil.rmtree, cls.work, True)
        cls.dot_log = cls.work / "dot.log"
        stand_ins = {"dot": _rendering_dot(cls.dot_log)} if cls.WITH_DOT else {}
        cls.bin_dir = tool_bin_dir(cls.work / "bin", stand_ins)
        cls.project = git_repo(cls.work / "ws", WORKSPACE)
        cls.head = repo_git(cls.project, "rev-parse", "--short", "HEAD")
        cls.out = cls.work / "out"
        cls.out.mkdir()
        if cls.CONFIG is not None:
            (cls.out / "crate_map.toml").write_text(cls.CONFIG, encoding="utf-8")
        cwd = cls.work / "cwd"
        cwd.mkdir()
        args = ["--project-dir", cls.project, "--out", cls.out, "--name", "fixture"]
        if not cls.RENDER:
            args.append("--no-render")
        cls.day_before = date.today().isoformat()
        cls.result = run_tool(CRATE_MAP, *args, bin_dir=cls.bin_dir, cwd=cwd)
        cls.day_after = date.today().isoformat()

    def setUp(self):
        output = self.result.stdout + self.result.stderr
        self.assertNotIn("Traceback", output, f"the run prints no traceback:\n{output}")
        self.assertEqual(self.result.returncode, 0, f"exit {self.result.returncode}:\n{output}")

    def dot_calls(self) -> list:
        if not self.dot_log.exists():
            return []
        return self.dot_log.read_text(encoding="utf-8").splitlines()

    def report(self) -> dict:
        return json.loads((self.out / "crate_map_baseline.json").read_text(encoding="utf-8"))

    def crate(self, pkg: str) -> dict:
        rows = [row for row in self.report()["crates"] if row["pkg"] == pkg]
        self.assertEqual(len(rows), 1, f"exactly one row for {pkg}")
        return rows[0]

    def markdown(self) -> str:
        return (self.out / "crate_map_baseline.md").read_text(encoding="utf-8")

    def graph(self) -> str:
        return (self.out / "fixture_crate_map.dot").read_text(encoding="utf-8")


class LineClassificationTest(_CrateMapRun):
    """AC1 (§S1.2) — each line is code, comment or blank, and code inside a ``#[cfg(test)]`` or
    ``#[cfg(any(test, …))]`` item is test-gated."""

    def test_the_dot_stand_in_never_ran_under_no_render(self):
        self.assertEqual(self.dot_calls(), [], "AC15: --no-render runs no dot")

    def test_each_file_row_carries_its_code_test_gated_and_comment_lines(self):
        self.assertEqual(
            [{k: m[k] for k in ("path", "kind", "code", "testgated", "comment")}
             for m in self.crate("core_lib")["modules"]],
            [{"path": "src/lib.rs", "kind": "src", "code": 13, "testgated": 8, "comment": 4},
             {"path": "tests/integration.rs", "kind": "tests", "code": 8, "testgated": 0,
              "comment": 0}])
        self.assertEqual(
            [{k: m[k] for k in ("path", "kind", "code", "testgated", "comment")}
             for m in self.crate("util")["modules"]],
            [{"path": "src/lib.rs", "kind": "src", "code": 9, "testgated": 6, "comment": 1}],
            "a ';'-ended cfg(test) item gates 2 lines, a cfg(any(test, …)) item behind a comment "
            "gates 4 more, and the prod function between them stays prod")

    def test_examples_count_as_test_side_files_and_the_root_package_is_scanned(self):
        self.assertEqual(
            [(m["path"], m["kind"], m["code"]) for m in self.crate("app")["modules"]],
            [("src/main.rs", "src", 3), ("examples/demo.rs", "examples", 1)])
        self.assertEqual(
            [(m["path"], m["kind"], m["code"]) for m in self.crate("root")["modules"]],
            [("src/main.rs", "src", 1)])
        self.assertEqual(self.crate("empty")["modules"], [], "an empty crate has no file rows")

    def test_each_crate_splits_prod_test_gated_and_test_directory_lines(self):
        fields = ("dir", "prod_loc", "src_testgated_loc", "tests_dir_loc", "total_loc",
                  "comment_loc", "files")
        expected = {
            "gen": ("tools/gen", 22, 0, 0, 22, 0, 1),
            "core_lib": ("crates/core", 5, 8, 8, 21, 4, 2),
            "util": ("crates/util", 3, 6, 0, 9, 1, 1),
            "app": ("crates/app", 3, 0, 1, 4, 0, 2),
            "root": (".", 1, 0, 0, 1, 0, 1),
            "empty": ("crates/empty", 0, 0, 0, 0, 0, 0),
        }
        for pkg, values in expected.items():
            with self.subTest(pkg=pkg):
                row = self.crate(pkg)
                self.assertEqual(tuple(row[f] for f in fields), values)


class AttributeSignalsTest(_CrateMapRun):
    """AC1 (§S1.2) — ``tests``, ``ignored``, ``allow_dead`` and ``deprecated`` count only a real
    attribute at the start of a code line; ``todo_fixme`` counts comments too."""

    SIGNALS = ("tests", "ignored", "allow_dead", "deprecated", "todo_fixme")

    def test_the_dot_stand_in_never_ran_under_no_render(self):
        self.assertEqual(self.dot_calls(), [], "AC15: --no-render runs no dot")

    def test_a_file_row_names_only_its_real_attributes_and_its_comment_todos(self):
        lib, integration = self.crate("core_lib")["modules"]
        self.assertEqual(
            {k: lib[k] for k in self.SIGNALS if k in lib},
            {"tests": 1, "deprecated": 1, "todo_fixme": 2},
            "the doc comment's #[allow(dead_code)], the string's #[ignore] and the commented "
            "#[test] are not attributes; TODO and FIXME in comments count")
        self.assertEqual({k: integration[k] for k in self.SIGNALS if k in integration},
                         {"tests": 2, "ignored": 1}, "#[tokio::test] and #[test] both count")
        util_lib, = self.crate("util")["modules"]
        self.assertEqual([k for k in self.SIGNALS if k in util_lib], [],
                         "#[cfg(test)] is no test signal; a file with none carries no keys")

    def test_each_crate_sums_its_files_signals(self):
        expected = {
            "gen": (0, 0, 10, 0, 0),
            "core_lib": (3, 1, 0, 1, 2),
            "util": (0, 0, 0, 0, 0),
            "app": (0, 0, 0, 0, 0),
            "root": (0, 0, 0, 0, 0),
            "empty": (0, 0, 0, 0, 0),
        }
        for pkg, values in expected.items():
            with self.subTest(pkg=pkg):
                row = self.crate(pkg)
                self.assertEqual(tuple(row[k] for k in self.SIGNALS), values)


class DependencyEdgesTest(_CrateMapRun):
    """AC1 (§S1.2) — workspace-internal prod, dev and build edges, and fan-in from prod and
    build edges alone."""

    def test_the_dot_stand_in_never_ran_under_no_render(self):
        self.assertEqual(self.dot_calls(), [], "AC15: --no-render runs no dot")

    def test_each_crate_carries_its_internal_prod_build_and_dev_edges(self):
        expected = {
            "root": (["app"], []),
            "app": (["core_lib", "util"], ["gen"]),
            "util": (["core_lib", "gen (build)"], []),
            "core_lib": ([], []),
            "empty": ([], []),
            "gen": ([], []),
        }
        for pkg, (deps, dev_deps) in expected.items():
            with self.subTest(pkg=pkg):
                row = self.crate(pkg)
                self.assertEqual(row["deps"], deps, "serde is external, never an edge")
                self.assertEqual(row["dev_deps"], dev_deps)

    def test_fan_in_counts_prod_and_build_edges_but_not_dev_edges(self):
        self.assertEqual({row["pkg"]: row["fan_in"] for row in self.report()["crates"]},
                         {"core_lib": 2, "util": 1, "gen": 1, "app": 1, "root": 0, "empty": 0})

    def test_the_markdown_lists_each_crate_with_edges_once(self):
        md = self.markdown()
        section = md.split("## Workspace-internal dependency edges\n", 1)[1]
        self.assertEqual(
            [line for line in section.splitlines() if line],
            ["- `root` → app",
             "- `app` → core_lib, util · dev: gen",
             "- `util` → core_lib, gen (build)"],
            "by member directory; crates with no internal edge are not listed")


class TotalsAndReportsTest(_CrateMapRun):
    """AC1 (§S1.2) — the totals, ``crate_map_baseline.json`` and ``crate_map_baseline.md``."""

    def test_the_dot_stand_in_never_ran_under_no_render(self):
        self.assertEqual(self.dot_calls(), [], "AC15: --no-render runs no dot")

    def test_the_json_meta_carries_the_head_the_day_the_member_count_and_the_totals(self):
        meta = self.report()["meta"]
        self.assertEqual(meta["head"], self.head)
        self.assertIn(meta["date"], {self.day_before, self.day_after})
        self.assertEqual(meta["members"], 6)
        self.assertEqual(meta["totals"], TOTALS)

    def test_the_json_lists_the_crates_largest_first(self):
        crates = self.report()["crates"]
        self.assertEqual([row["pkg"] for row in crates], CRATE_ORDER)

    def test_the_markdown_table_has_one_row_per_crate_and_the_total_row(self):
        meta = self.report()["meta"]
        lines = self.markdown().splitlines()
        self.assertEqual(lines[0], f"# Crate metrics — @ `{self.head}` ({meta['date']})")
        header = lines.index(
            "| crate | prod | src-tg | tests/ | total | tests# | ign | dead | depr | todo "
            "| fan-in |")
        self.assertEqual(lines[header + 2:header + 9], [
            "| gen | 22 | 0 | 0 | 22 | 0 | 0 | 10 | 0 | 0 | 1 |",
            "| core_lib | 5 | 8 | 8 | 21 | 3 | 1 | 0 | 1 | 2 | 2 |",
            "| util | 3 | 6 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 1 |",
            "| app | 3 | 0 | 1 | 4 | 0 | 0 | 0 | 0 | 0 | 1 |",
            "| root | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |",
            "| empty | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |",
            "| **TOTAL (6)** | **34** | **14** | **9** | **57** | **3** | **1** | **10** | **1** "
            "| **2** | |",
        ])
        self.assertEqual(lines[header + 9], "", "the table ends after the total row")

    def test_the_summary_line_reports_the_crates_lines_and_edges(self):
        self.assertIn(f"[crate-map] @ {self.head}: 6 crates | prod=34 test=23 | 5 edges\n",
                      self.result.stdout)
        self.assertIn(f"wrote crate_map_baseline.json / .md / fixture_crate_map.dot in {self.out}",
                      self.result.stdout)


class FallbackGraphTest(_CrateMapRun):
    """AC1 (§S1.2) — with no ``crate_map.toml``, crates cluster by top-level member directory, the
    root package's cluster is ``root``, and the empty-crate and dead-code markers are drawn."""

    def test_the_dot_stand_in_never_ran_under_no_render(self):
        self.assertEqual(self.dot_calls(), [], "AC15: --no-render runs no dot")

    def test_crates_cluster_by_top_level_directory_and_the_root_package_by_root(self):
        clusters = _clusters(self.graph())
        self.assertEqual(list(clusters), ["root", "crates", "tools"],
                         "the root package's cluster id is 'root', a valid DOT id, never '.'")
        self.assertEqual(clusters["root"]["header"],
                         'label="./"; style="rounded,filled"; fillcolor="#E8F0FE"; fontsize=16;')
        self.assertEqual(clusters["crates"]["header"],
                         'label="crates/"; style="rounded,filled"; fillcolor="#E6F4EA"; '
                         'fontsize=16;')
        self.assertEqual(clusters["tools"]["header"],
                         'label="tools/"; style="rounded,filled"; fillcolor="#FEF7E0"; '
                         'fontsize=16;')
        self.assertEqual(clusters["root"]["nodes"], ["root"])
        self.assertEqual(clusters["crates"]["nodes"], ["core_lib", "util", "app", "empty"])
        self.assertEqual(clusters["tools"]["nodes"], ["gen"])
        self.assertNotIn("cluster_.", self.graph())

    def test_nodes_carry_their_lines_and_the_empty_and_dead_code_markers(self):
        graph = self.graph()
        self.assertEqual(_node_lines(graph, "core_lib"),
                         [f'"core_lib" [label="core_lib{NL}prod 5 | test 16" fillcolor="white"];'])
        self.assertEqual(_node_lines(graph, "app"),
                         [f'"app" [label="app{NL}prod 3 | test 1" fillcolor="white"];'])
        self.assertEqual(_node_lines(graph, "empty"),
                         [f'"empty" [label="empty{NL}EMPTY (0 LOC)" fillcolor="white" '
                          'color="#E8710A" penwidth=3];'])
        self.assertEqual(_node_lines(graph, "gen"),
                         [f'"gen" [label="gen{NL}prod 22 | test 0{NL}allow(dead_code) x10" '
                          'fillcolor="white" color="#C5221F" penwidth=3];'])

    def test_edges_are_the_prod_and_build_edges_with_no_dev_edge(self):
        self.assertEqual(_edges(self.graph()), {
            ("root", "app"), ("app", "util"), ("app", "core_lib"), ("util", "core_lib"),
            ("util", "gen")})

    def test_the_title_carries_the_name_head_totals_and_no_omitted_edges(self):
        graph = self.graph()
        self.assertTrue(graph.startswith("digraph crate_map {\n"), graph[:80])
        self.assertTrue(graph.endswith("\n}"), graph[-80:])
        day = self.report()["meta"]["date"]
        self.assertIn(f'label="fixture crate map — @ {self.head} ({day}){NL}'
                      f"prod 34 LOC | test 23 LOC | 6 crates | 3 tests{NL}"
                      "edges = prod deps; edges into [none] omitted", graph)


class ConfiguredGraphTest(_CrateMapRun):
    """AC1 (§S1.2) — ``<out>/crate_map.toml`` sets the clusters, folds packages into an
    aggregate and omits edges into ``omit_edges_into``."""

    CONFIG = CRATE_MAP_TOML

    def test_the_dot_stand_in_never_ran_under_no_render(self):
        self.assertEqual(self.dot_calls(), [], "AC15: --no-render runs no dot")

    def test_the_configured_clusters_replace_the_fallback(self):
        clusters = _clusters(self.graph())
        self.assertEqual(list(clusters), ["base", "tools"])
        self.assertEqual(clusters["base"]["header"],
                         'label="Base layer"; style="rounded,filled"; fillcolor="#ABCDEF"; '
                         'fontsize=16;')
        self.assertEqual(clusters["base"]["nodes"], ["core_lib", "util"])
        self.assertEqual(clusters["tools"]["header"],
                         'label="Tools"; style="rounded,filled"; fillcolor="#FEDCBA"; '
                         'fontsize=16;')
        self.assertEqual(clusters["tools"]["nodes"], ["toolchain"])

    def test_an_aggregate_replaces_its_packages_and_sums_their_lines(self):
        graph = self.graph()
        self.assertEqual(_node_lines(graph, "toolchain"),
                         [f'"toolchain" [label="toolchain (x1 bins){NL}prod 22 | test 0{NL}'
                          'allow(dead_code) x10" fillcolor="white" color="#C5221F" penwidth=3];'])
        self.assertEqual(_node_lines(graph, "gen"), [], "gen is drawn only as its aggregate")

    def test_unclustered_crates_still_get_a_node(self):
        graph = self.graph()
        self.assertEqual(_node_lines(graph, "app"),
                         [f'"app" [label="app{NL}prod 3 | test 1" fillcolor="white"];'])
        self.assertEqual(_node_lines(graph, "root"),
                         [f'"root" [label="root{NL}prod 1 | test 0" fillcolor="white"];'])
        self.assertEqual(len(_node_lines(graph, "empty")), 1)

    def test_edges_into_omitted_packages_are_dropped_and_aggregates_are_edge_ends(self):
        self.assertEqual(_edges(self.graph()),
                         {("root", "app"), ("app", "util"), ("util", "toolchain")})
        self.assertIn("edges into [core_lib] omitted", self.graph())
        self.assertIn("| 3 edges\n", self.result.stdout)


class RenderTest(unittest.TestCase):
    """AC1 (§S1.2) — the SVG render with a ``dot`` stand-in present, with ``dot`` absent, and
    skipped by ``--no-render``."""

    SKIPPED = ("[crate-map] graphviz `dot` not on PATH — skipped render "
               "(--no-render to silence)")

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="mdb-rust-render-")).resolve()
        self.addCleanup(shutil.rmtree, self.work, True)
        self.dot_log = self.work / "dot.log"
        self.project = git_repo(self.work / "ws", WORKSPACE)
        self.out = self.work / "out"
        self.cwd = self.work / "cwd"
        self.cwd.mkdir()

    def run_map(self, *extra, with_dot: bool):
        stand_ins = {"dot": _rendering_dot(self.dot_log)} if with_dot else {}
        bin_dir = tool_bin_dir(self.work / "bin", stand_ins)
        result = run_tool(CRATE_MAP, "--project-dir", self.project, "--out", self.out,
                          "--name", "fixture", *extra, bin_dir=bin_dir, cwd=self.cwd)
        output = result.stdout + result.stderr
        self.assertNotIn("Traceback", output)
        self.assertEqual(result.returncode, 0, output)
        self.assertTrue((self.out / "fixture_crate_map.dot").is_file())
        return result, bin_dir

    def dot_calls(self) -> list:
        if not self.dot_log.exists():
            return []
        return self.dot_log.read_text(encoding="utf-8").splitlines()

    def test_dot_on_path_renders_the_graphviz_source_to_svg(self):
        result, _ = self.run_map(with_dot=True)
        dot_path, svg = self.out / "fixture_crate_map.dot", self.out / "fixture_crate_map.svg"
        self.assertEqual(self.dot_calls(), [f"-Tsvg {dot_path} -o {svg}"],
                         "AC15: the dot stand-in ran exactly once, on the written source")
        self.assertEqual(svg.read_text(encoding="utf-8"), "<svg/>\n")
        self.assertIn(f"[crate-map] rendered {svg}\n", result.stdout)
        self.assertNotIn("skipped render", result.stdout)

    def test_dot_absent_skips_the_render_with_a_note_and_exits_zero(self):
        result, bin_dir = self.run_map(with_dot=False)
        self.assertIsNone(shutil.which("dot", path=str(bin_dir)), "AC15: no dot on the PATH")
        self.assertIn(self.SKIPPED + "\n", result.stdout)
        self.assertFalse((self.out / "fixture_crate_map.svg").exists())
        self.assertNotIn("rendered", result.stdout)

    def test_no_render_runs_no_dot_even_when_one_is_on_path(self):
        result, _ = self.run_map("--no-render", with_dot=True)
        self.assertEqual(self.dot_calls(), [], "AC15: the dot stand-in never ran")
        self.assertFalse((self.out / "fixture_crate_map.svg").exists())
        self.assertNotIn("rendered", result.stdout)
        self.assertNotIn("skipped render", result.stdout)


class DefaultOutAndNameTest(unittest.TestCase):
    """AC1 (§S1.2) — ``--out`` defaults to ``<project>/docs/research/assets`` and ``--name`` to the
    project directory's name; the project defaults to the git toplevel of the working directory."""

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="mdb-rust-defaults-")).resolve()
        self.addCleanup(shutil.rmtree, self.work, True)
        self.dot_log = self.work / "dot.log"
        self.bin_dir = tool_bin_dir(self.work / "bin", {"dot": _rendering_dot(self.dot_log)})
        self.project = git_repo(self.work / "my_ws", WORKSPACE)
        self.assets = self.project / "docs" / "research" / "assets"

    def assertDefaultArtifacts(self, result):
        output = result.stdout + result.stderr
        self.assertNotIn("Traceback", output)
        self.assertEqual(result.returncode, 0, output)
        self.assertFalse(self.dot_log.exists(), "AC15: --no-render runs no dot stand-in")
        self.assertEqual(sorted(p.name for p in self.assets.iterdir()),
                         ["crate_map_baseline.json", "crate_map_baseline.md",
                          "my_ws_crate_map.dot"])
        report = json.loads((self.assets / "crate_map_baseline.json").read_text(encoding="utf-8"))
        self.assertEqual([row["pkg"] for row in report["crates"]], CRATE_ORDER)
        graph = (self.assets / "my_ws_crate_map.dot").read_text(encoding="utf-8")
        self.assertIn('label="my_ws crate map — @ ', graph)
        self.assertIn(f"my_ws_crate_map.dot in {self.assets}\n", result.stdout)

    def test_with_no_project_dir_the_git_toplevel_of_the_working_directory_is_used(self):
        result = run_tool(CRATE_MAP, "--no-render", bin_dir=self.bin_dir,
                          cwd=self.project / "crates" / "core")
        self.assertDefaultArtifacts(result)

    def test_with_a_project_dir_and_no_out_the_artifacts_land_in_the_project(self):
        cwd = self.work / "cwd"
        cwd.mkdir()
        result = run_tool(CRATE_MAP, "--project-dir", self.project, "--no-render",
                          bin_dir=self.bin_dir, cwd=cwd)
        self.assertDefaultArtifacts(result)
        self.assertEqual(list(cwd.iterdir()), [], "nothing is written to the working directory")


if __name__ == "__main__":
    unittest.main()
