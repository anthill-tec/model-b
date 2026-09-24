"""C2 gates for CR-MDB-017 — the verb / endpoint / doc sweep (§S4a, §S4b, §S4c, §S4d).

Scope of THIS module (cycle C2 of CR-MDB-017):

- §S4a — the ``plan-file`` surface: the comma-split ``--cycles`` form and the retired
  ``--orchestrator`` flag are gone; every ``plan-file`` example shows repeated ``--cycle``
  each paired with its own ``--cycle-kind``; every documented workflow-verb invocation
  carries ``--agent``; the refusal rules are stated.
- §S4b — the gate verb: ``gate-run`` is THE gate verb, ``gate-report`` may only appear in a
  retired/legacy ROLE, and the ``--skip`` rationale is stated. The released-only rule
  (``portRule`` / the ``/api/health`` listener block) rides with this class because it is the
  same family: which verbs/flags a Model B doc is allowed to teach.
- §S4c — the design docs Model B owns (PRD §D3.4 / §D7, ``DN-rationalization-plan-review.md``),
  the contract-document version axis in ``contracts/crucible-envelope.md``, the installed
  product facts, and the ``crucible-report-vscode`` auto-attach comment. Grouped here as the
  "documented-facts" family.
- §S4d — the retired v1 ``/api/ingest`` endpoints, plus the guard-of-the-guard that the files
  which DEFINE the ban keep their own ``/api/ingest`` strings.

Class-to-section mapping is deliberate and stated above: §S4b carries the released-only rule
and §S4c carries the contract-version / vscode families, because the CR's own prose files them
under the same §S4 sweep without giving them their own section number.

**EXPECTED-RED NOTE — `generator/` is C3's edit surface.** The §S4d endpoint gate covers
``generator/stacks/quarkus.toml`` and the four rendered ``generator/agents/quarkus-*`` files.
C2 does not edit ``generator/``; those five lines stay RED until C3 fixes the TOML and
regenerates. That is expected and is not a defect in this gate.

What this module deliberately does NOT do:

- It never shells out: no ``grep``, no ``subprocess``, no server, no client. Every scan is a
  Python tree walk over repo text.
- It reads no Crucible client and mirrors no Crucible flag surface (CR-MDB-017 §S5 risk note).
- It does not re-assert what ``tests/test_skills_handover.py`` already gates (zero
  ``WORKFLOW_CYCLE_ID`` at ``:226``, the v2 touch contract at ``:294``, the v2 heartbeat form
  at ``:386``), nor what ``tests/test_client_role_contract.py`` (C1) gates for
  ``register --role``/``--cycle``.
- It excludes the files that DEFINE a ban from that ban's scan: ``archive/``, ``docs/``,
  ``audits/``, ``docs/research/crucible-clients-skills-guard.test.ts`` and ``tests/`` (this
  module must spell the banned strings to forbid them).

Every failure message lists ``file:line`` so GREEN gets a work list rather than a verdict.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------- scopes ----

# §S4a doc set: the surfaces that teach the plan/cycle idiom.
DOC_SET_S4A = ("skills-src", "contracts", "AGENTS.md", "docs/research")

# §S4b / released-only doc set (design docs are authored prose, not instructions).
DOC_SET_BUNDLES = ("skills-src", "contracts", "AGENTS.md")

# The two normative surfaces that must STATE the refusal rules in prose.
NORMATIVE_SURFACES = (
    "skills-src/crucible/SKILL.md",
    "contracts/crucible-envelope.md",
)

PRD = "docs/research/PRD-model-b-rationalization.md"
DN_PLAN_REVIEW = "docs/research/DN-rationalization-plan-review.md"
ENVELOPE_CONTRACT = "contracts/crucible-envelope.md"
# CR-MDB-024 \u00a7S3 (this cycle, C2 RED, 2026-09-22 vscode ruling): VSCODE_BUNDLE
# retired -- the skills-src/crucible-report-vscode/ bundle it named is deleted
# outright, not migrated, so the cycle-binding-comment test that used it is
# deleted below too (tests/test_ide_overlay_retirement.py gates the deletion).

# §S4d: the ban's own definitions, excluded from the ban's scan.
GUARD_TEST = "docs/research/crucible-clients-skills-guard.test.ts"
API_INGEST_EXCLUDED_PREFIXES = (
    "archive/",
    "docs/",
    "audits/",
    "tests/",
    "test-reports/",
)
BAN_DEFINING_FILES = (
    PRD,
    DN_PLAN_REVIEW,
    "audits/2026-07-20-crucible-drift.md",
    GUARD_TEST,
)

# §S4d, CR-MDB-017 V1 — the `.lavish/` carve-out, made EXPLICIT.
#
# `.lavish/` holds generated lavish-axi renderings of past review sessions. The
# three `/api/ingest` occurrences in `model-b-memory-rationalization.html`
# NARRATE this very migration — they name the defect, the v1→v2 mapping, and
# the grep-gate list — so they describe the ban exactly as the PRD/DN/audit
# hits do, and a sweep there would falsify a record rather than fix an
# instruction. PRD §11 criterion 2 carries the same carve-out in prose.
#
# It is spelled out here because until now the directory escaped this scan
# TWICE BY ACCIDENT: every dot-prefixed path part is skipped, and `.html` is
# not in TEXT_SUFFIXES. The AC was therefore claimed on an incidental
# zero-match — the precise failure mode this CR exists to forbid — while the
# directory sat git-tracked and unignored.
LAVISH_CARVE_OUT = ".lavish/"
GENERATED_ARTIFACT_CARVE_OUTS = (LAVISH_CARVE_OUT,)
# A carved-out hit must still be NARRATION: it names the v2 route it maps to,
# or it names the gate. A live v1 instruction dropped there still fails.
LAVISH_NARRATION_MARKERS = ("/api/v2/", "gate")

TEXT_SUFFIXES = {"", ".md", ".toml", ".ts", ".py", ".txt", ".json", ".yaml", ".yml", ".sh"}

# ------------------------------------------------------------ vocabulary ----

# Develop-only surface Model B may NOT teach (CR-CRU-139, 0.3.0-bound). The version that is
# unreleased is named by the CR, never hardcoded in this module.
DEVELOP_ONLY_BANNED = ("portRule", "/api/health")

# Present in the installed production client and therefore legitimate to document. The
# released-only gate must never forbid any of these.
RELEASED_VERBS_NOT_FORBIDDEN = (
    "queue",
    "queue-file",
    "--from-file",
    "milestone",
    "--released-at",
    "--crs",
    "--packages",
    "--repair-provenance",
    "release-propose",
    "cr-plan",
    "wave-sequence",
    "cr-depends",
    "cr-supersede",
    "cr-void",
    "next",
)

CYCLE_KINDS = ("red-green", "verify", "fix")

WORKFLOW_VERBS = (
    "plan-file",
    "cycle-activate",
    "cycle-done",
    "cr-close",
    "milestone",
    "gate-run",
    "gate-report",
    "queue-file",
    "release-propose",
    "cr-plan",
    "wave-sequence",
    "cr-depends",
    "cr-supersede",
    "cr-void",
)

# --cycle on a word boundary: --cycles and --cycle-kind must never satisfy it.
RE_CYCLE_FLAG = re.compile(r"--cycle(?![\w-])")
RE_CYCLES_FLAG = re.compile(r"--cycles(?![\w-])")
RE_CYCLE_KIND_FLAG = re.compile(r"--cycle-kind(?![\w-])")
RE_ORCHESTRATOR_FLAG = re.compile(r"--orchestrator(?![\w-])")
RE_PLAN_FILE = re.compile(r"(?<![\w-])plan-file(?![\w-])")
RE_GATE_RUN = re.compile(r"(?<![\w-])gate-run(?![\w-])")
RE_GATE_REPORT = re.compile(r"(?<![\w-])gate-report(?![\w-])")
RE_VERB_INVOCATION = re.compile(
    r"(?<![\w-])(?:" + "|".join(re.escape(v) for v in WORKFLOW_VERBS) + r")\s+--"
)
RE_CODE_SPAN = re.compile(r"`([^`]+)`")


# ----------------------------------------------------------------- utils ----


def _iter_files(rel_root):
    """Yield repo-relative text files under ``rel_root`` (a dir or a single file)."""
    target = REPO_ROOT / rel_root
    if target.is_file():
        yield rel_root
        return
    if not target.is_dir():
        return
    for path in sorted(target.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        if any(part.startswith(".") for part in Path(rel).parts):
            continue
        if path.suffix not in TEXT_SUFFIXES:
            continue
        yield rel


def _lines(rel):
    path = REPO_ROOT / rel
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []


def _text(rel):
    path = REPO_ROOT / rel
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _scan(scopes, predicate):
    """Return [(rel, lineno, line)] for every line where ``predicate(line)`` is true."""
    hits = []
    for scope in scopes:
        for rel in _iter_files(scope):
            for lineno, line in enumerate(_lines(rel), 1):
                if predicate(line):
                    hits.append((rel, lineno, line))
    return hits


def _fmt(hits):
    return "\n".join(f"  {rel}:{lineno}: {line.strip()[:160]}" for rel, lineno, line in hits)


def _code_spans(line):
    return RE_CODE_SPAN.findall(line)


def _section(rel, header_re, stop_re):
    """Return [(lineno, line)] for the doc section opened by ``header_re``."""
    out = []
    inside = False
    for lineno, line in enumerate(_lines(rel), 1):
        if inside and stop_re.search(line):
            break
        if header_re.search(line):
            inside = True
        if inside:
            out.append((lineno, line))
    return out


def _d_section(rel, number):
    return _section(
        rel,
        re.compile(rf"^###\s+D{number}\b"),
        re.compile(rf"^###\s+D(?!{number}\b)"),
    )


def _missing_statement(rel, patterns):
    """Return the patterns (as source strings) absent from ``rel``'s text."""
    text = _text(rel)
    return [p.pattern for p in patterns if not p.search(text)]


def _anchor(rel, regex, default=1):
    """First line number in ``rel`` matching ``regex`` — used to cite a surface."""
    for lineno, line in enumerate(_lines(rel), 1):
        if regex.search(line):
            return lineno
    return default


# ------------------------------------------------------------------ §S4a ----


class ClientVerbSweepS4aTest(unittest.TestCase):
    """§S4a — the ``plan-file`` surface and the ``--agent`` requirement.

    Measured against the installed production client (0.2.2): ``--cycle`` is repeatable and
    each occurrence requires its own positional ``--cycle-kind``; the comma-split ``--cycles``
    form is REFUSED for filing; ``plan-file --orchestrator`` was REMOVED (the registered
    ``--agent`` id IS the plan's orchestrator); ``--agent`` is required on every workflow verb
    with no fallback.
    """

    def test_s4a_no_refused_cycles_form_paired_with_plan_file(self):
        """No doc teaches the REFUSED comma-split ``--cycles`` form on ``plan-file``."""
        hits = _scan(
            DOC_SET_S4A,
            lambda line: bool(RE_CYCLES_FLAG.search(line)) and bool(RE_PLAN_FILE.search(line)),
        )
        self.assertEqual(
            [],
            hits,
            "plan-file examples still teach the REFUSED --cycles form; replace each with "
            "repeated --cycle/--cycle-kind pairs:\n" + _fmt(hits),
        )

    def test_s4a_no_orchestrator_flag_paired_with_plan_file(self):
        """``plan-file --orchestrator`` is retired — the registered ``--agent`` id is the plan's."""
        hits = _scan(
            DOC_SET_S4A,
            lambda line: bool(RE_ORCHESTRATOR_FLAG.search(line))
            and bool(RE_PLAN_FILE.search(line)),
        )
        self.assertEqual(
            [],
            hits,
            "plan-file examples still pass the retired --orchestrator flag; drop it and keep "
            "--wave:\n" + _fmt(hits),
        )

    def test_s4a_every_plan_file_example_pairs_cycle_with_cycle_kind(self):
        """Every ``plan-file`` invocation repeats ``--cycle`` with one ``--cycle-kind`` each."""
        offenders = []
        for rel, lineno, line in _scan(
            DOC_SET_S4A, lambda text: bool(RE_PLAN_FILE.search(text))
        ):
            if not RE_VERB_INVOCATION.search(line):
                continue  # prose mention of the verb, not an invocation
            n_cycle = len(RE_CYCLE_FLAG.findall(line))
            n_kind = len(RE_CYCLE_KIND_FLAG.findall(line))
            kinds = re.findall(r"--cycle-kind\s+([\w-]+)", line)
            bad_kind = [k for k in kinds if k not in CYCLE_KINDS and not k.startswith("<")]
            if n_cycle < 1 or n_cycle != n_kind or bad_kind:
                offenders.append(
                    (
                        rel,
                        lineno,
                        f"{line.strip()[:110]}  [--cycle={n_cycle} "
                        f"--cycle-kind={n_kind} kinds={kinds or 'none'}]",
                    )
                )
        self.assertEqual(
            [],
            offenders,
            "each plan-file example must show repeated --cycle, each with its own "
            "--cycle-kind from {red-green, verify, fix}:\n" + _fmt(offenders),
        )

    def test_s4a_normative_surfaces_state_cycle_kind_mismatch_is_refused(self):
        """The normative docs say a cycle/kind count mismatch is refused before anything posts."""
        required = (
            RE_CYCLE_KIND_FLAG,
            re.compile(r"(?is)(mismatch|count)[^\n]{0,240}(refus|reject)"),
            re.compile(r"(?is)(before anything posts|before any(thing)? is posted|nothing posts)"),
        )
        offenders = []
        for rel in NORMATIVE_SURFACES:
            missing = _missing_statement(rel, required)
            if missing:
                offenders.append(
                    (rel, _anchor(rel, RE_PLAN_FILE), "missing: " + " | ".join(missing))
                )
        self.assertEqual(
            [],
            offenders,
            "the plan-file refusal rule is not stated (cited line = the plan-file surface to "
            "edit):\n" + _fmt(offenders),
        )

    def test_s4a_every_workflow_verb_invocation_carries_agent(self):
        """Every documented workflow-verb invocation carries ``--agent``."""
        offenders = []
        for rel, lineno, line in _scan(DOC_SET_BUNDLES, lambda text: True):
            spans = _code_spans(line)
            if not any(RE_VERB_INVOCATION.search(s) for s in spans):
                continue
            if "--agent" in line:
                continue
            offenders.append((rel, lineno, line))
        self.assertEqual(
            [],
            offenders,
            "workflow-verb invocations missing --agent (required on every workflow verb, no "
            "fallback):\n" + _fmt(offenders),
        )

    def test_s4a_normative_surfaces_state_unregistered_agent_is_refused_409(self):
        """The normative docs say an unregistered ``--agent`` id is refused 409, no fallback."""
        required = (
            re.compile(r"--agent"),
            re.compile(r"(?is)unregistered[^\n]{0,200}409|409[^\n]{0,200}unregistered"),
            re.compile(r"(?is)no fallback"),
        )
        offenders = []
        for rel in NORMATIVE_SURFACES:
            missing = _missing_statement(rel, required)
            if missing:
                offenders.append(
                    (rel, _anchor(rel, RE_VERB_INVOCATION), "missing: " + " | ".join(missing))
                )
        self.assertEqual(
            [],
            offenders,
            "the unregistered-id refusal rule is not stated (cited line = the workflow-verb "
            "surface to edit):\n" + _fmt(offenders),
        )


# ------------------------------------------------------------------ §S4b ----


class ClientVerbSweepS4bTest(unittest.TestCase):
    """§S4b — ``gate-run`` is the gate verb; plus the re-pinned released-only rule.

    ``gate-report`` is the one-shot legacy and emits a ``prefer-gate-run`` discouragement
    warning. Naming it as RETIRED is allowed; naming it as THE gate verb is not — so the gate
    asserts on the ROLE the text gives it, never bare absence.
    """

    RETIRED_MARKER = re.compile(
        r"(?i)(retired|legacy|deprecat|superseded|discourag|prefer-gate-run|one-shot)"
    )

    def test_s4b_gate_report_is_never_named_as_the_gate_verb(self):
        """Any ``gate-report`` mention is marked retired/legacy, never presented as the verb."""
        offenders = [
            (rel, lineno, line)
            for rel, lineno, line in _scan(
                DOC_SET_BUNDLES, lambda line: bool(RE_GATE_REPORT.search(line))
            )
            if not self.RETIRED_MARKER.search(line)
        ]
        self.assertEqual(
            [],
            offenders,
            "gate-report is named without a retired/legacy role — replace with gate-run or "
            "mark it as the legacy one-shot:\n" + _fmt(offenders),
        )

    def test_s4b_gate_run_is_named_on_both_normative_surfaces(self):
        """``gate-run`` is named in ``skills-src/crucible/SKILL.md`` and the envelope contract."""
        offenders = []
        for rel in NORMATIVE_SURFACES:
            if not RE_GATE_RUN.search(_text(rel)):
                offenders.append(
                    (rel, _anchor(rel, RE_GATE_REPORT), "missing the gate verb `gate-run`")
                )
        self.assertEqual(
            [],
            offenders,
            "gate-run must replace gate-report as the named gate verb (cited line = the "
            "gate-report line to rewrite):\n" + _fmt(offenders),
        )

    def test_s4b_skip_rationale_is_stated_with_the_gate_verb(self):
        """The ``--skip`` rationale (PR-based ``ci`` step vs a git-flow direct merge) is stated."""
        required = (
            re.compile(r"--skip(?![\w-])"),
            re.compile(r"(?is)\bci\b[^\n]{0,200}(pull request|\bPR\b)|(pull request|\bPR\b)[^\n]{0,200}\bci\b"),
            re.compile(r"(?i)ci_timeout"),
        )
        offenders = []
        for rel in NORMATIVE_SURFACES:
            missing = _missing_statement(rel, required)
            if missing:
                offenders.append(
                    (rel, _anchor(rel, RE_GATE_REPORT), "missing: " + " | ".join(missing))
                )
        self.assertEqual(
            [],
            offenders,
            "the --skip rationale is not stated (no-mistakes' ci step is PR-based; a git-flow "
            "project merging directly has no PR, so the gate blocks until ci_timeout):\n"
            + _fmt(offenders),
        )

    def test_s4b_no_develop_only_port_rule_surface_is_documented(self):
        """No bundle/contract/AGENTS.md text teaches the unreleased ``portRule`` listener block."""
        offenders = _scan(
            DOC_SET_BUNDLES,
            lambda line: any(token in line for token in DEVELOP_ONLY_BANNED),
        )
        self.assertEqual(
            [],
            offenders,
            "develop-only surface documented (portRule / the /api/health listener block is "
            "0.3.0-bound, absent from the installed release):\n" + _fmt(offenders),
        )

    def test_s4b_released_only_gate_does_not_forbid_released_verbs(self):
        """The released-only ban list forbids nothing already shipped in the installed client."""
        wrongly_banned = [
            verb
            for verb in RELEASED_VERBS_NOT_FORBIDDEN
            if any(verb in banned or banned in verb for banned in DEVELOP_ONLY_BANNED)
        ]
        self.assertEqual(
            [],
            wrongly_banned,
            "the released-only ban list may not forbid verbs present in the installed release "
            "(queue-file, --from-file, milestone --released-at/--crs/--packages/"
            "--repair-provenance, and the declared-roadmap verbs): "
            + repr(wrongly_banned),
        )

    def test_s4b_gate_hardcodes_no_release_version_as_unreleased(self):
        """This module pins no Crucible version as unreleased — the CR names it, the gate does not."""
        own = Path(__file__).resolve()
        source = own.read_text(encoding="utf-8")
        stale = [
            (own.relative_to(REPO_ROOT).as_posix(), lineno, line)
            for lineno, line in enumerate(source.splitlines(), 1)
            if re.search(r"0\.2\.0", line)
        ]
        self.assertEqual(
            [],
            stale,
            "a hardcoded release version as 'unreleased' rots silently; name the develop-only "
            "SURFACE instead:\n" + _fmt(stale),
        )


# ------------------------------------------------------------------ §S4c ----


class ClientVerbSweepS4cTest(unittest.TestCase):
    """§S4c — Model B's own design docs and the contract-version axis.

    Corrections here are factual only; no design decision is reopened. The version axis stays
    explicit: the product version is ``0.2.x``, ``/api/v2`` is the API generation, and ``2.0.0``
    is the STATUS-CONTRACT document's own semver.

    CR-MDB-024 §S3 AMENDMENT (this cycle, C2 RED, 2026-09-22 vscode ruling): the
    ``crucible-report-vscode`` bundle this class used to sweep (the cycle-binding
    comment check) is retired outright along with the rest of the vscode substrate --
    an IDE is not a stack -- so that test is deleted rather than migrated: there is no
    replacement bundle for it to check. The declined-client-request check below is
    UNAFFECTED (PRD §D7 is untouched by this CR's Non-goals) and stays.
    """

    def test_s4c_prd_d3_4_plan_cycle_idiom_shows_no_refused_cycles_form(self):
        """PRD §D3.4's plan/cycle idiom drops the refused ``--cycles`` form."""
        offenders = [
            (PRD, lineno, line)
            for lineno, line in _d_section(PRD, 3)
            if RE_CYCLES_FLAG.search(line) or (RE_ORCHESTRATOR_FLAG.search(line) and RE_PLAN_FILE.search(line))
        ]
        self.assertEqual(
            [],
            offenders,
            "PRD §D3.4 still states the plan/cycle idiom with the refused --cycles form (and "
            "the retired --orchestrator flag):\n" + _fmt(offenders),
        )

    def test_s4c_prd_d7_endpoint_list_covers_used_routes_or_declares_a_subset(self):
        """PRD §D7's endpoint list covers the routes now used, or says it enumerates a subset."""
        section = _d_section(PRD, 7)
        body = "\n".join(line for _, line in section)
        anchor = next(
            (lineno for lineno, line in section if "Endpoints:" in line),
            section[0][0] if section else 1,
        )
        covers = all(
            re.search(token, body, re.I)
            for token in (r"queue", r"release-proposal", r"milestone", r"gate")
        )
        declares_subset = re.search(
            r"(?i)(subset|not exhaustive|non-exhaustive|representative)", body
        )
        self.assertTrue(
            covers or declares_subset,
            f"{PRD}:{anchor}: §D7's endpoint list predates the queue, release-proposal, milestone "
            "and gate routes this project uses — extend it or state that it enumerates a "
            "subset.",
        )

    def test_s4c_prd_d7_vscode_client_request_reads_as_declined(self):
        """PRD §D7's ``vscode-crucible.py`` request is recorded DECLINED (Sandesh #1370)."""
        offenders = [
            (PRD, lineno, line)
            for lineno, line in _d_section(PRD, 7)
            if "vscode-crucible.py" in line and not re.search(r"(?i)declin", line)
        ]
        self.assertEqual(
            [],
            offenders,
            "§D7 still carries an OPEN request for vscode-crucible.py; the user DECLINED it "
            "(Sandesh #1370) and an open request invites a future CR to re-raise it:\n"
            + _fmt(offenders),
        )

    def test_s4c_dn_universal_plan_verbs_read_as_delivered(self):
        """``DN-rationalization-plan-review.md``'s universal plan/cycle verbs read as DELIVERED."""
        offenders = [
            (DN_PLAN_REVIEW, lineno, line)
            for lineno, line in enumerate(_lines(DN_PLAN_REVIEW), 1)
            if "universal plan/cycle verbs" in line
            and not re.search(r"(?i)(delivered|shipped|landed|fleet-wide since)", line)
        ]
        self.assertEqual(
            [],
            offenders,
            "the DN still records the universal plan/cycle verbs as an ASK; they are delivered "
            "fleet-wide and must read as such:\n" + _fmt(offenders),
        )

    def test_s4c_dn_smoke_criterion_register_leg_carries_role_and_cycle(self):
        """The DN's per-stack Crucible smoke criterion registers with ``--role`` and ``--cycle``."""
        offenders = []
        for lineno, line in enumerate(_lines(DN_PLAN_REVIEW), 1):
            if not re.search(r"(?i)smoke", line):
                continue
            if "register" not in line or "unregister" not in line:
                continue
            if "--role" in line and RE_CYCLE_FLAG.search(line):
                continue
            offenders.append((DN_PLAN_REVIEW, lineno, line))
        self.assertEqual(
            [],
            offenders,
            "the smoke criterion's register leg omits --role/--cycle, so the smoke test it "
            "specifies cannot pass:\n" + _fmt(offenders),
        )

    def test_s4c_envelope_contract_cites_status_contract_document_version(self):
        """``contracts/crucible-envelope.md`` cites STATUS-CONTRACT.md document version 2.0.0."""
        hits = [
            (ENVELOPE_CONTRACT, lineno, line)
            for lineno, line in enumerate(_lines(ENVELOPE_CONTRACT), 1)
            if "STATUS-CONTRACT" in line and "2.0.0" in line
        ]
        status_anchor = _anchor(ENVELOPE_CONTRACT, re.compile(r"^#"))
        self.assertTrue(
            hits,
            f"{ENVELOPE_CONTRACT}:{status_anchor}: the contract does not cite "
            "STATUS-CONTRACT.md by its DOCUMENT version (2.0.0, verified at "
            "~/.crucible/clients/STATUS-CONTRACT.md).",
        )

    def test_s4c_envelope_contract_never_implies_a_product_version_of_2_0_0(self):
        """No line reads ``2.0.0`` as a Crucible PRODUCT/release version."""
        product_claim = re.compile(
            r"(?i)(crucible\s+v?2\.0\.0|product\s+version[^\n]{0,40}2\.0\.0|"
            r"release\s+2\.0\.0|2\.0\.0\s+release)"
        )
        offenders = [
            (ENVELOPE_CONTRACT, lineno, line)
            for lineno, line in enumerate(_lines(ENVELOPE_CONTRACT), 1)
            if product_claim.search(line)
        ]
        self.assertEqual(
            [],
            offenders,
            "2.0.0 is the STATUS-CONTRACT document's semver, never a Crucible product "
            "version:\n" + _fmt(offenders),
        )

    def test_s4c_envelope_contract_matches_the_installed_product_facts(self):
        """Documented product facts match the installed install (version, install/serve/uninstall)."""
        text = _text(ENVELOPE_CONTRACT)
        required = {
            "product version 0.2.2": re.compile(r"0\.2\.2"),
            "crucible-axi install": re.compile(r"crucible-axi\s+install"),
            "--target-dir": re.compile(r"--target-dir(?![\w-])"),
            "default ~/.crucible": re.compile(r"~/\.crucible"),
            "run verb serve": re.compile(r"crucible-axi\s+serve|`serve`"),
            "uninstall subcommand": re.compile(r"uninstall"),
        }
        missing = [name for name, rx in required.items() if not rx.search(text)]
        order_ok = True
        if not missing:
            idx = [text.find(tok) for tok in ("install", "serve", "uninstall")]
            order_ok = idx[0] < idx[1] < idx[2]
        anchor = _anchor(ENVELOPE_CONTRACT, re.compile(r"^#"))
        detail = missing or "nothing"
        self.assertTrue(
            not missing and order_ok,
            f"{ENVELOPE_CONTRACT}:{anchor}: installed-product facts absent or mis-ordered "
            f"— missing {detail}; install/serve/uninstall order ok={order_ok}",
        )

    def test_s4c_no_doc_states_0_1_2_as_the_latest_release(self):
        """No Model B doc still calls the superseded 0.1.2 snapshot the latest release."""
        stale = re.compile(r"(?i)0\.1\.2[^\n]{0,80}(latest|current|newest)|(latest|current|newest)[^\n]{0,80}0\.1\.2")
        offenders = _scan(DOC_SET_S4A, lambda line: bool(stale.search(line)))
        self.assertEqual(
            [],
            offenders,
            "0.1.2 is not the latest Crucible release; the installed production version is "
            "0.2.2:\n" + _fmt(offenders),
        )

    # CR-MDB-024 \u00a7S3 (this cycle, C2 RED, 2026-09-22 vscode ruling): the
    # cycle-binding-comment test that used to live here
    # (test_s4c_vscode_bundle_states_cycle_binding_is_declared_at_registration)
    # is DELETED, not migrated -- it read
    # skills-src/crucible-report-vscode/SKILL.md, which this CR deletes
    # outright (an IDE is not a stack). There is no replacement bundle for
    # it to check; the deletion itself is gated by
    # tests/test_ide_overlay_retirement.py.


# ------------------------------------------------------------------ §S4d ----


class ClientVerbSweepS4dTest(unittest.TestCase):
    """§S4d — the retired v1 ``/api/ingest`` endpoints (PRD §11 criterion 2).

    **Expected-RED note:** ``generator/stacks/quarkus.toml`` and the four rendered
    ``generator/agents/quarkus-*`` files are inside this gate's scope but are C3's edit surface.
    They stay RED after C2 lands and go green when C3 fixes the TOML and regenerates with
    ``python3 generator/build.py build``. Never hand-edit the four rendered files.
    """

    def test_s4d_zero_v1_api_ingest_references_outside_the_gate_definitions(self):
        """Zero ``/api/ingest`` outside ``archive/``, ``docs/``, ``audits/`` and the guard test."""
        offenders = []
        for path in sorted(REPO_ROOT.rglob("*")):
            if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel.startswith(GENERATED_ARTIFACT_CARVE_OUTS):
                continue
            if any(part.startswith(".") for part in Path(rel).parts):
                continue
            if rel.startswith(API_INGEST_EXCLUDED_PREFIXES) or rel == GUARD_TEST:
                continue
            for lineno, line in enumerate(_lines(rel), 1):
                if "/api/ingest" in line:
                    offenders.append((rel, lineno, line))
        self.assertEqual(
            [],
            offenders,
            "retired v1 endpoints still live — map /api/ingest -> /api/v2/runs, "
            "/api/ingest/parsed -> /api/v2/runs/parsed, /api/ingest/compile -> "
            "/api/v2/runs/compile (generator/* is C3's surface and stays red until C3 "
            "regenerates):\n" + _fmt(offenders),
        )

    def test_s4d_the_files_defining_the_ban_keep_their_api_ingest_strings(self):
        """The PRD, the DN, the audit and the guard test still SPELL ``/api/ingest``."""
        broken = []
        for rel in BAN_DEFINING_FILES:
            path = REPO_ROOT / rel
            if not path.is_file():
                broken.append((rel, 1, "file missing — the ban lost its definition"))
                continue
            if "/api/ingest" not in _text(rel):
                broken.append((rel, 1, "no /api/ingest string left — the gate was 'cleaned'"))
        self.assertEqual(
            [],
            broken,
            "a sweep that edits the gate's own definition defeats the gate; these files "
            "DESCRIBE the ban and must keep their strings:\n" + _fmt(broken),
        )


    def test_s4d_the_lavish_carve_out_is_explicit_and_its_hits_are_narration(self):
        """CR-MDB-017 V1 — the carve-out is NAMED and TRUTHFUL, never incidental.

        `.lavish/` is git-tracked and unignored, so criterion 2 could not be
        claimed while it went unexamined. It is carved out by name; this gate
        proves the carve-out is honest by re-reading the directory the main scan
        skips and requiring every `/api/ingest` line there to be narration.
        """
        self.assertIn(
            LAVISH_CARVE_OUT,
            GENERATED_ARTIFACT_CARVE_OUTS,
            "the carve-out must be NAMED in a constant the scan reads, not left "
            "to the dot-directory and non-text-suffix skips that hid it.",
        )
        carve_root = REPO_ROOT / LAVISH_CARVE_OUT.rstrip("/")
        if not carve_root.is_dir():
            return  # nothing carved out; the criterion is unconditionally met
        instructional = []
        for path in sorted(carve_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if "/api/ingest" not in line:
                    continue
                if not any(m in line for m in LAVISH_NARRATION_MARKERS):
                    instructional.append((rel, lineno, line))
        self.assertEqual(
            [],
            instructional,
            "a carved-out generated artifact may DESCRIBE the retired v1 routes "
            "(naming the v2 route they map to, or naming the gate) but never "
            "teach one as live; these read as instructions:\n" + _fmt(instructional),
        )


if __name__ == "__main__":
    unittest.main()
