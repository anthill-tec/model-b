"""The Chrome-UI-Relay skill — its bundle and its text (CR-MDB-061 §S1–§S7, CR-MDB-076 §S1–§S4).

Contract: ``docs/changes/CR-MDB-061-browser-relay-for-pi-sessions.md`` (design reference
DN-multi-harness-deploy-model §D23 and §D18), patched by
``docs/changes/CR-MDB-076-chrome-ui-relay-retries-first-attach.md`` (the warning, the two-minute
bridge wait, no retry, the single ``stop``; DN §D23's 2026-10-16 rulings). The deliverable is one
Markdown skill, ``skills-src/chrome-ui-relay/SKILL.md``; these tests pin its text.

Class map:

- ``ChromeUiRelayBundleTest`` — §S1: the bundle exists, its frontmatter is clean (the
  ``frontmatter_violations`` rule of ``tests/test_skill_frontmatter.py``) with
  ``name: chrome-ui-relay``, its heading is "Chrome-UI-Relay", it carries no stack scope and bundle
  discovery selects it for every stack selection; it writes grep, head and tail as plain words,
  never code spans; its example URL is the ``<dev-url>`` placeholder and it names no host and port.
- ``ChromeUiRelayPhraseRulesTest`` — §S1 (the not-the-omp-relay statement) and §S2–§S7: one
  phrase gate per acceptance rule, one test method per rule, each generated from ``PHRASE_RULES``;
  CR-MDB-076's rules (its §S1 warning, §S2 wait and stop, §S3 causes) sit under their own header
  in the table.
- ``ChromeUiRelayPhraseDetectorProofTest`` — every detector kind proved both ways on
  ``CONFORMING_SAMPLE``, a spec-worded sample skill: the sample passes every gate, each rule's
  cut of the sample bites that rule, and each anchored rule's reversed wording (``REVERSALS``)
  bites it too.
- ``OpenStepGateTest`` — negative gate 1: no ``chrome-devtools-axi open`` shown as a step.
- ``PipedOutputGateTest`` — negative gate 2: no ``chrome-devtools-axi`` output shown piped (any
  single ``|`` after the tool, never ``||``), captured with ``$(…)``, or redirected, with or
  without a space before the redirect (``2>&1`` keeps it).
- ``BridgeWaitTokensGateTest`` — negative gate 3 (CR-MDB-076 AC): every fenced line running
  ``chrome-devtools-axi`` carries the three exact tokens of ``CALL_TOKENS`` — the auto-connect, the
  project session and the two-minute bridge wait.

**A phrase rule** is a set of patterns that must all match inside ONE unit of the skill's body
(``units``): a paragraph, a list item together with its nested items, a heading, a table row or a
whole fenced block; a paragraph ending in ``:`` is a lead-in and takes the list that follows it.
Each unit is normalised (``normalise``) — backticks and ``*`` dropped, curly quotes straightened,
whitespace collapsed, lower-cased — so a phrase matches however the line is wrapped or marked up.

**The negative gates** read the skill as the raw-runner guard does (``_blocks``, ``_code_spans``,
``_QUOTE`` imported from ``tests/test_raw_runner_guard.py``): a fenced line is judged alone, once
the lines it continues with a trailing backslash are joined to it; a code span is judged against the
masked prose before it. A form is exempt when a prohibition governs it — the
guard's ``_governed`` (a ``PROHIBITION`` in the clause ``_CLAUSE_END`` ends), imported, never copied.

Existing gates over every bundle cover the rest of §S1 and are not repeated here: Pi's loader
(``PiSkillLoaderOracleTest``), the frontmatter tree (``FrontmatterTreeTest``), the tool-name
ratchet, the project-name gate and the raw-runner guard.

Hermetic: reads repository files only; nothing runs ``chrome-devtools-axi`` or ``npx``, and
nothing touches a browser. Stdlib only.
"""

import re
import unittest

from modelb_axi import deploy
from tests._helpers import REPO_ROOT, read_text, split_frontmatter
from tests.test_client_path_anchoring import _count_tools
from tests.test_installer_stack_selection import ALL_STACKS
from tests.test_raw_runner_guard import _QUOTE, _blocks, _code_spans, _governed
from tests.test_skill_frontmatter import frontmatter_violations

BUNDLE = "chrome-ui-relay"
SKILL_MD = REPO_ROOT / "skills-src" / BUNDLE / "SKILL.md"
HEADING = "Chrome-UI-Relay"
#: §S1: the placeholder an example URL is written as.
DEV_URL_PLACEHOLDER = "<dev-url>"

# ------------------------------------------------------------------ units ----

_FENCE_LINE = re.compile(r"^\s*(`{3,}|~{3,})")
_HEADING_LINE = re.compile(r"^\s*#{1,6}\s")
_LIST_ITEM = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+")
_CURLY = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})


def normalise(text: str) -> str:
    """Backticks and ``*`` dropped, curly quotes straightened, whitespace collapsed, lower-cased."""
    text = text.replace("`", "").replace("*", "").translate(_CURLY)
    return re.sub(r"\s+", " ", text).strip().lower()


def units(text: str) -> list[str]:
    """The normalised units of ``text``'s body (its frontmatter left out): a paragraph, a
    top-level list item with its nested items and wrapped lines, a heading, a table row, a whole
    fenced block. A paragraph whose last line ends in ``:`` is a lead-in: the list after it joins
    its unit, up to the next paragraph, heading, table row or fence."""
    _frontmatter, body = split_frontmatter(text)
    out: list[str] = []
    current: list[str] = []
    fence = None
    lead_in = False
    after_blank = False

    def flush():
        if current:
            out.append(normalise("\n".join(current)))
            current.clear()

    for line in body.splitlines():
        opener = _FENCE_LINE.match(line)
        if fence is not None:
            current.append(line)
            if opener and opener.group(1)[0] == fence[0] and len(opener.group(1)) >= len(fence):
                flush()
                fence = None
            continue
        if opener:
            flush()
            fence, lead_in = opener.group(1), False
            current.append(line)
            continue
        if not line.strip():
            after_blank = True
            continue
        if _HEADING_LINE.match(line) or line.lstrip().startswith("|"):
            flush()
            out.append(normalise(line))
            lead_in = after_blank = False
            continue
        item = _LIST_ITEM.match(line)
        if item:
            if len(item.group(1)) < 2 and not lead_in:
                flush()
        elif after_blank and not line[:1].isspace():
            flush()
            lead_in = False
        if not current and not item:
            lead_in = False
        current.append(line)
        if not item and not line[:1].isspace() and line.rstrip().endswith(":"):
            lead_in = True
        after_blank = False
    flush()
    return out


def rule_findings(text: str, patterns: tuple[str, ...]) -> list[str]:
    """``[]`` when one unit of ``text`` matches every pattern; otherwise one finding naming the
    patterns the closest unit lacks."""
    compiled = [re.compile(p) for p in patterns]
    best: list[str] = list(patterns)
    for unit in units(text):
        missing = [rx.pattern for rx in compiled if not rx.search(unit)]
        if not missing:
            return []
        if len(missing) < len(best):
            best = missing
    return [f"no unit states the rule; the closest lacks {best}"]


# ------------------------------------------------------------------ shown forms ----

#: Negative gate 1: ``open`` shown as a ``chrome-devtools-axi`` step.
OPEN_STEP = re.compile(r"chrome-devtools-axi\s+open\b")
#: The text after the tool, a ``<placeholder>`` taken whole so its ``>`` is never a redirect.
_AFTER_TOOL = r"chrome-devtools-axi\b(?:<[\w.-]+>|<(?![\w.-]+>)|[^<])*?"
# MIGRATED at CR-MDB-061 (§S7): any single ``|`` (not ``||``), a ``$(…)`` capture, any redirect.
#: Negative gate 2: ``chrome-devtools-axi`` output piped (any single ``|`` after the tool, never
#: ``||``), captured with ``$(…)``, or redirected (``>``, ``>>``, ``N>``, ``&>``, with or without a
#: space before it; ``N>&M`` such as ``2>&1`` keeps it).
PIPED_OUTPUT = re.compile(
    r"\$\([^()]*\bchrome-devtools-axi\b"
    r"|" + _AFTER_TOOL + r"(?:(?<!\|)\|(?!\|)|(?:&>>?|\d*>>?)(?!&))")
#: §S1: grep, head and tail are plain words, never a code span.
PLAIN_WORD_SPAN = re.compile(r"(?:grep|head|tail)\b")
#: §S1: a host with a port — ``localhost``, a dotted quad or a dotted name, then ``:`` and digits.
HOST_PORT = re.compile(
    r"(?<![\w.-])(?:localhost|\d{1,3}(?:\.\d{1,3}){3}|[a-z0-9-]+(?:\.[a-z0-9-]+)+|\[[0-9a-f:]+\])"
    r":\d{2,5}\b", re.IGNORECASE)


def _join_continued(parts: list[str]) -> str:
    """Fenced lines continued with a trailing ``\\``, joined into the one line the shell reads."""
    return " ".join(part[:-1].rstrip() if part.endswith("\\") else part for part in parts)


# MIGRATED at CR-MDB-061 (§S2, §S7): fenced lines continued with ``\`` are joined first.
def shown(text: str):
    """Yield ``(line_number, content, governing_prefix)`` for each code span and each fenced line
    of ``text``, read as the raw-runner guard reads a file. ``governing_prefix`` is the masked
    prose before a span, or ``None`` for a fenced line (judged alone, on its own text). A fenced
    line ending in ``\\`` is joined with the fenced lines it continues, and the joined line is
    yielded once, at its first line's number."""
    lines = [_QUOTE.sub("", line) for line in text.splitlines()]
    pending: list[str] = []
    pending_first = 0
    for first, block in _blocks(lines):
        if pending and (block is not None or first != pending_first + len(pending)):
            yield pending_first + 1, _join_continued(pending), None
            pending = []
        if block is None:
            if not pending:
                pending_first = first
            pending.append(lines[first].strip())
            if not pending[-1].endswith("\\"):
                yield pending_first + 1, _join_continued(pending), None
                pending = []
            continue
        joined = "\n".join(block)
        spans = list(_code_spans(joined))
        masked = list(joined)
        for start, end, _content in spans:
            masked[start:end] = "x" * (end - start)
        masked = "".join(masked)
        for start, _end, content in spans:
            yield first + joined.count("\n", 0, start) + 1, content, masked[:start]
    if pending:
        yield pending_first + 1, _join_continued(pending), None


def shown_form_findings(text: str, form: re.Pattern) -> list[tuple[int, str]]:
    """Every ``form`` a code span or a fenced line of ``text`` shows, ungoverned by a
    prohibition, as ``(line_number, shown)``."""
    findings = []
    for number, content, prefix in shown(text):
        match = form.search(content)
        if not match:
            continue
        before = content[:match.start()] if prefix is None else prefix
        if not _governed(before):
            findings.append((number, content))
    return findings


#: Negative gate 3 (CR-MDB-076 "The negative gate"): the exact tokens every fenced line running
#: ``chrome-devtools-axi`` carries, each a whole shell word.
CALL_TOKENS = (
    "CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1",
    "CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN>",
    "CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000",
)
#: A line that runs the tool: its name as a word of its own.
_RUNS_TOOL = re.compile(r"(?<![\w-])chrome-devtools-axi(?![\w-])")


def missing_call_token_findings(text: str) -> list[tuple[int, str, tuple[str, ...]]]:
    """``(line_number, line, missing_tokens)`` for every fenced line of ``text`` that runs
    ``chrome-devtools-axi`` without every one of ``CALL_TOKENS`` as a whole word. A line continued
    with ``\\`` is judged once joined (``shown``); a code span is never a call, and a ``#`` comment
    line runs nothing."""
    findings = []
    for number, content, prefix in shown(text):
        if prefix is not None or content.lstrip().startswith("#") or not _RUNS_TOOL.search(content):
            continue
        words = content.split()
        missing = tuple(token for token in CALL_TOKENS if token not in words)
        if missing:
            findings.append((number, content, missing))
    return findings


def plain_word_span_findings(text: str) -> list[tuple[int, str]]:
    """Every code span (not a fenced line) of ``text`` that writes grep, head or tail."""
    return [(n, c) for n, c, prefix in shown(text) if prefix is not None and PLAIN_WORD_SPAN.match(c)]


def host_port_findings(text: str) -> list[tuple[int, str]]:
    """Every line of ``text`` naming a host with a port."""
    return [(n, line.strip()) for n, line in enumerate(text.splitlines(), 1) if HOST_PORT.search(line)]


def frontmatter_value(text: str, key: str):
    """The value of ``key`` in ``text``'s frontmatter, stripped, or ``None``."""
    frontmatter, _body = split_frontmatter(text)
    match = re.search(rf"^{re.escape(key)}:[ \t]*(.*)$", frontmatter, re.MULTILINE)
    return None if match is None else match.group(1).strip()


def first_heading(text: str):
    """The text of the body's first level-1 heading, or ``None``."""
    _frontmatter, body = split_frontmatter(text)
    match = re.search(r"^#\s+(.+?)\s*$", body, re.MULTILINE)
    return None if match is None else match.group(1)


# ------------------------------------------------------------------ the rules ----

_NEVER_RETRIED = r"\b(?:never|not|no)\b[^.;]{0,10}\bretr(?:y|ied|ies)\b"
#: CR-MDB-076 §S2: the bridge wait, exactly ``120000`` (``1200000`` and ``120s`` are not it).
BRIDGE_WAIT = r"chrome_devtools_axi_bridge_timeout_ms=120000(?!\d)"
#: CR-MDB-076 §S3: the message three causes share, normalised.
GONE_AWAY = re.escape("the attached cdp target appears to have gone away")
#: CR-MDB-076 §S2: Close's single retry never applies to a ``BRIDGE_NOT_READY`` envelope.
_RETRY_NEVER_APPLIES = r"\bretry never applies to a bridge_not_ready envelope\b"
#: CR-MDB-076 §S2: a ``BRIDGE_NOT_READY`` skip runs ``stop`` once.
_RUNS_STOP_ONCE = r"\bruns stop once\b"
#: CR-MDB-076 §S2: a shutdown whose bootstrap skipped runs one ``stop`` and nothing else.
_ONE_STOP_NOTHING_ELSE = r"\bruns (?:that |the )?one stop and nothing else\b"

#: One phrase gate per acceptance rule: ``(test_name, section, patterns, cut)``. ``patterns`` must
#: all match inside one unit; ``cut`` is the ``(old, new)`` replacements of
#: ``CONFORMING_SAMPLE`` that remove the rule, so the proof can show the gate bites.
PHRASE_RULES = (
    # §S1
    ("s1_states_it_is_not_the_omp_era_cdp_relay_which_never_runs_under_pi", "§S1",
     (r"\bnot\b[^.;]{0,20}\bomp-era cdp relay\b",
      r"\b(?:never|not)(?: be)? run\w*\b[^.;]{0,15}\bunder pi\b"),
     (("must never run under Pi", "is retired"),)),
    # §S2
    # MIGRATED at CR-MDB-076 (§S2, §S4): the invocation rule requires the bridge wait, exactly.
    ("s2_every_call_is_npx_with_auto_connect_and_the_project_token_session", "§S2",
     (re.escape("npx -y chrome-devtools-axi"),
      re.escape("chrome_devtools_axi_auto_connect=1"),
      r"chrome_devtools_axi_session=(?:<project_token>|\"?\$\{?project_token\}?\"?)",
      BRIDGE_WAIT),
     (("`CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1`", "`CHROME_DEVTOOLS_AXI_TRACE=1`"),)),
    ("s2_each_project_has_its_own_bridge_and_its_stop_ends_only_its_own", "§S2",
     (r"\b(?:each|every) project\b", r"\bown bridge\b",
      r"\bstop\b[^.;]{0,30}\bonly\b[^.;]{0,15}\bown\b"),
     (("ends only its own", "ends every bridge"),)),
    ("s2_never_launches_a_browser", "§S2",
     (r"\bnever (?:launch|start)\w* (?:a |the )?(?:browser|chrome)\b",),
     (("never launches a browser and ", ""),)),
    ("s2_never_uses_open", "§S2",
     (r"\bnever (?:use|run|call|send)s? (?:the )?(?:npx -y )?(?:chrome-devtools-axi )?open\b",),
     (("never uses `open`", "uses every verb"),
      ("never run `npx -y chrome-devtools-axi open <dev-url>`",
       "run `npx -y chrome-devtools-axi newpage <dev-url>`"))),
    ("s2_an_absent_malformed_or_default_token_skips_the_browser_steps", "§S2",
     (r"\bproject_token\b", r"\babsent\b", re.escape("[a-za-z0-9._-]{1,64}"),
      r"\bdefault\b", r"\bbrowser steps are skipped\b"),
     (("not of the form `[A-Za-z0-9._-]{1,64}`, ", ""),)),
    ("s2_reports_no_valid_session_name_set_project_token_in_env", "§S2",
     (re.escape("no valid session name: set project_token in .env"),),
     (("no valid session name: set `PROJECT_TOKEN` in `.env`", "the token is wrong"),)),
    ("s2_never_falls_back_to_the_default_session", "§S2",
     (r"\b(?:never|not|no)\b[^.;]{0,20}\bfalls?\s*back\b[^.;]{0,20}\bdefault session\b",),
     (("it never falls back to the default session", "it uses the default session"),)),
    ("s2_project_token_dev_url_and_id_are_values_to_substitute_never_typed_literally", "§S2",
     (re.escape("<project_token>"), re.escape("<dev-url>"), re.escape("<id>"),
      r"\bare values to substitute\b", r"\bnever typed literally\b"),
     (("are values to substitute, never typed literally", "are written as shown"),)),
    ("s2_pages_prints_its_tabs_as_pages_n_id_url_selected_one_row_per_tab", "§S2",
     (r"\bpages prints\b", re.escape("pages[n]{id,url,selected}"), r"\bone row per tab\b"),
     (("`pages[N]{id,url,selected}`", "a list"),)),
    # §S3
    ("s3_the_caller_gives_three_lists_urls_project_patterns_and_protected_patterns", "§S3",
     (r"\bthree\b", r"\burls to open\b", r"\burl patterns\b", r"\bprotected patterns\b",
      r"\bnever selected, evaluated or closed\b"),
     (("the URL patterns the project's tabs match", "the project's tabs"),)),
    ("s3_protected_wins_a_protected_tab_never_counted_chosen_or_closed", "§S3",
     (r"\bprotected wins\b", r"\bnever counted as already open\b", r"\bnever chosen\b",
      r"\bnever closed\b"),
     (("**Protected wins everywhere.** ", ""),)),
    ("s3_a_protected_url_to_open_is_a_caller_error_reported_and_skipped", "§S3",
     (r"\burl to open\b", r"\bprotected pattern\b", r"\bcaller error\b", r"\breported\b",
      r"\bskipped\b"),
     (("is a caller error: it is reported and skipped", "is opened"),)),
    ("s3_urls_are_compared_by_the_callers_project_pattern_never_by_exact_string", "§S3",
     (r"\burls are compared by pattern\b", r"\bmatches the project pattern the caller gives\b",
      r"\bnever by exact string\b"),
     ((", never by exact string", ", by exact string"),)),
    # §S4
    ("s4_open_keeps_the_pages_id_set_as_before", "§S4",
     (r"\bpages\b", r'\bid set as "?before"?'),
     (('Keep its id set as "before".', "Read it."),)),
    ("s4_an_already_open_url_is_not_reopened_and_its_tab_never_touched", "§S4",
     (r"\balready (?:shows|open)\b", r"\b(?:not|never) (?:opened again|reopened)\b",
      r"\bnever selected, evaluated or closed\b"),
     (("is not opened again", "is opened"),)),
    ("s4_opens_with_newpage_only_never_navigating_an_existing_or_selected_tab", "§S4",
     (r"\bnewpage\b", r"\bnever navigates?\b[^.;]{0,20}\b(?:existing|selected)\b"),
     ((" Never navigate an existing or selected tab.", ""),)),
    ("s4_the_new_tabs_are_the_after_ids_minus_the_before_ids", "§S4",
     (r"\bpages again\b", r'"?after"? ids minus the "?before"? ids\b'),
     (('The new tabs are the "after" ids minus the "before" ids.', "The new tabs are the last ones."),)),
    ("s4_every_url_opened_shows_and_every_before_id_stays_or_it_stops_and_reports", "§S4",
     (r"\bevery url opened\b", r'\bevery "?before"? id is still there\b', r"\bstop and report\b"),
     (('   - Every "before" id is still there.\n', ""),)),
    # MIGRATED at CR-MDB-061 (§S4): anchored on "keeps that record", so "no record is kept" fails.
    ("s4_the_new_tabs_are_the_skills_own_for_this_bridge_and_it_keeps_that_record", "§S4",
     (r"\bthe skill's own\b", r"\bfor this bridge\b", r"\bit keeps (?:that|the|its) record\b"),
     (("It keeps that record as", "It lists them as"),)),
    ("s4_the_record_is_kept_as_id_and_url_pairs", "§S4",
     (r"\bkeeps (?:that|the|its) record as \(id, url\) pairs\b",),
     ((" as **(id, URL) pairs**", ""),)),
    ("s4_the_record_is_held_in_the_callers_working_context_a_restarted_session_has_none", "§S4",
     (r"\brecord\b[^.;]{0,40}\bheld in the caller's working context\b",
      r"\ba restarted agent session has no record\b"),
     (("held in the caller's working context", "held for the session"),)),
    ("s4_a_timed_out_newpage_is_confirmed_among_the_new_ids_never_retried", "§S4",
     (r"\btimed out\b", r"\bstill made its tab\b", _NEVER_RETRIED, r"\bduplicat"),
     (("; never retry, since a retry duplicates it", "; retry it"),)),
    ("s4_rendered_text_is_confirmed_on_the_skills_own_tabs_never_the_load_event", "§S4",
     (r"\bselectpage\b", re.escape("eval document.body.innertext.length"), r"\bown tabs only\b",
      r"\b(?:never|not) (?:on |by |from )?the load event\b"),
     ((", never the load event", ""),)),
    # §S5
    # MIGRATED at CR-MDB-061 (§S5): anchored on "those in the skill's record", so "those not in the
    # skill's record" fails.
    ("s5_close_takes_a_fresh_pages_and_closes_recorded_tabs_still_shown_not_protected", "§S5",
     (r"\bpages\b[^.]{0,5}\bfresh\b|\bfresh pages\b", r"\bthose in (?:the skill's|its) record\b",
      r"\bstill shows?\b", r"\bnot protected\b"),
     ((", and are not protected", ""),)),
    ("s5_close_picks_only_recorded_ids_still_showing_with_their_recorded_url", "§S5",
     (r"\bthose in (?:the skill's|its) record\b",
      r"\bwhose id still shows with (?:its|the) recorded url\b"),
     (("whose id still shows with its recorded URL", "that still show"),)),
    ("s5_an_id_or_url_mismatch_is_a_silent_restart_that_closes_nothing_and_reports", "§S5",
     (r"\brecorded id shows with a different url\b",
      r"\bgone while its url shows on another id\b", r"\brestarted silently\b",
      r"\bclose nothing\b", r"\breport the tabs on the project's urls\b"),
     ((", or is gone while its URL shows on another id", ""),)),
    ("s5_pages_again_verifies_and_a_last_tab_no_op_shows_as_still_open", "§S5",
     (r"\bpages again\b", r"\bverify\b", r"\blast.tab\b", r"\bstill open\b"),
     ((" A last-tab no-op shows here as a tab still open.", ""),)),
    ("s5_stop_disconnects_the_bridge_and_never_closes_chrome", "§S5",
     (r"\bstop\b", r"\bdisconnects\b", r"\b(?:never|not) closes? (?:the user's )?chrome\b"),
     ((" and never closes Chrome", ""),)),
    # MIGRATED at CR-MDB-076 (§S2, §S4): the unit carries the BRIDGE_NOT_READY exception.
    ("s5_failed_control_retries_once_then_reports_the_tabs_left_open_by_url", "§S5",
     (r"\bretry once\b", r"\btabs left open\b", r"\burls\b", _RETRY_NEVER_APPLIES),
     (("retry once", "retry"),)),
    ("s5_no_record_closes_nothing_and_reports_project_tabs_for_the_user", "§S5",
     (r"\bno record\b", r"\bnothing is closed\b|\bcloses? nothing\b", r"\bfor the user to close\b"),
     (("nothing is closed", "they are closed"),)),
    # MIGRATED at CR-MDB-076 (§S2, §S4): the skipped shutdown runs its single `stop`.
    ("s5_a_skipped_bootstrap_means_shutdown_skips_and_starts_no_bridge", "§S5",
     (r"\bbootstrap skipped\b", r"\bshutdown skips\b",
      r"\bstarts no bridge\b|\bnever starts a bridge\b|\bno bridge\b", _ONE_STOP_NOTHING_ELSE),
     ((" and starts no bridge", ""),)),
    # §S6
    # MIGRATED at CR-MDB-061 (§S6): keyed on the envelope's "code: BRIDGE_NOT_READY" field.
    # MIGRATED at CR-MDB-076 (§S2, §S4): the bridge-cannot-attach rule carries the single `stop`.
    ("s6_an_envelope_carrying_code_bridge_not_ready_skips_the_browser_steps", "§S6",
     (r"\bcode: bridge_not_ready\b", r"\bbrowser steps are skipped\b", _RUNS_STOP_ONCE),
     (("`code: BRIDGE_NOT_READY`", "`code: FAILED`"),)),
    # MIGRATED at CR-MDB-061 (§S6): the error line and every help line, anchored on "the skill
    # reports", so "the skill never reports ... in full" fails.
    ("s6_reports_the_envelopes_error_line_and_every_help_line_in_full", "§S6",
     (r"\b(?:the skill|it) reports (?:the envelope's )?error line and every help line in full\b",),
     ((" in full", ""),)),
    ("s6_the_suggestions_are_reported_never_run", "§S6",
     (r"\bsuggestions are reported, never run\b",),
     ((", never run", ""),)),
    ("s6_a_skipped_browser_never_fails_bootstrap_or_shutdown", "§S6",
     (r"\b(?:never|not) fails? bootstrap or shutdown\b",),
     (("never fails bootstrap", "fails bootstrap"),)),
    ("s6_chrome_not_running_or_remote_debugging_off_enable_it_at_chrome_inspect", "§S6",
     (r"\bchrome stable\b", r"\bnot running\b", r"\bremote debugging\b",
      re.escape("chrome://inspect/#remote-debugging")),
     ((" enable it at `chrome://inspect/#remote-debugging`", " enable it"),)),
    # MIGRATED at CR-MDB-076 (§S3): the cut follows the spec's "another channel (Chromium)".
    ("s6_chromium_or_another_channel_running_instead_of_chrome_stable", "§S6",
     (r"\bchromium\b", r"\b(?:another|other|wrong) channel\b"),
     (("another channel (Chromium)", "something else"),)),
    # MIGRATED at CR-MDB-076 (§S3, §S4): was s6_the_connection_prompt_not_accepted_within_the_
    # start_up_timeout, whose \btimeout\b became the two-minute wait and the shared message; its
    # cut ("not accepted" -> "seen") is renamed with it.
    ("s6_the_connection_prompt_not_accepted_within_the_two_minute_wait_shares_the_gone_away_message",
     "§S6",
     (r"\bconnection prompt\b", r"\bnot accepted\b", r"\btwo-minute wait\b", GONE_AWAY),
     (("the connection prompt not accepted within the wait", "the connection prompt answered"),)),
    ("s6_a_port_collision_code_48_sets_the_port_for_this_session_only", "§S6",
     (r"\bport collision\b", r"\bcode 48\b", r"\bchrome_devtools_axi_port\b",
      r"\bthis session only\b"),
     ((" for this session only", ""),)),
    ("s6_npx_failing_to_fetch_chrome_devtools_mcp_on_a_cold_start_reports_the_tools_message", "§S6",
     (r"\bnpx failing to fetch chrome-devtools-mcp\b", r"\bcold start\b",
      r"\breport the tool's own message and fix\b"),
     ((" on a cold start", ""),)),
    # §S7
    ("s7_every_envelope_is_read_whole_never_piped_narrowed_or_redirected", "§S7",
     (r"\bread whole\b", r"\bnever piped\b", r"\bgrep\b", r"\bhead\b", r"\btail\b", r"\bjq\b",
      r"\bredirected away\b"),
     ((", narrowed with `jq`,", ","),)),
    # ---- CR-MDB-076: the warning, the two-minute bridge wait, no retry, the single `stop` ----
    # CR-MDB-076 §S1
    ("s1_warns_before_the_first_call_of_every_bootstrap_and_shutdown_relayed_by_a_services_skill",
     "§S1",
     (r"\bbefore the first call of every bootstrap and (?:of )?every shutdown\b",
      r"\bchrome will ask\b[^.;]{0,20}\baccept the connection\b",
      r"\baccept within about a minute\b", r"\bif chrome asks again\b[^.;]{0,20}\baccept again\b",
      r"\bany call may restart the bridge\b", r"\ba restart raises a new prompt\b",
      r"\ba services skill relays the warning\b"),
     ((", and if Chrome asks again, they accept again", ""),)),
    # CR-MDB-076 §S2
    ("s2_every_call_carries_the_bridge_wait_of_exactly_120000_kept_on_stop", "§S2",
     (BRIDGE_WAIT, r"\bon stop it does nothing but is kept\b", r"\bevery call reads the same\b"),
     (("`CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000`, the bridge wait",
       "`CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=60000`, the bridge wait"),)),
    ("s2_each_call_is_given_a_shell_timeout_of_at_least_150_s", "§S2",
     (r"\beach call is given a shell timeout of at least 150 ?s(?:econds)?\b",),
     (("at least 150 s (2.5 minutes)", "at least 30 s"),)),
    ("s2_a_call_killed_by_its_shell_timeout_counts_as_bridge_not_ready", "§S2",
     (r"\bcall killed by its shell timeout counts as bridge_not_ready\b",),
     (("counts as `BRIDGE_NOT_READY`", "is reported as a failure"),)),
    ("s2_never_retries_a_bridge_not_ready_call_since_a_retry_kills_the_bridge_and_raises_a_prompt",
     "§S2",
     (r"\bthe skill never retries a call that ended in bridge_not_ready\b",
      r"\ba retry kills the waiting bridge and raises a new prompt\b"),
     ((": a retry kills the waiting bridge and raises a new prompt", ""),)),
    ("s2_closes_single_retry_never_applies_to_a_bridge_not_ready_envelope_which_skips", "§S2",
     (r"\bretry once\b", _RETRY_NEVER_APPLIES, r"\bthat envelope skips\b"),
     (("; the single retry never applies to a `BRIDGE_NOT_READY` envelope: that envelope skips",
       ""),)),
    ("s2_a_bridge_not_ready_skip_runs_stop_once_which_starts_no_bridge_so_no_late_prompt", "§S2",
     (r"\bcode: bridge_not_ready\b", r"\bbrowser steps are skipped\b", _RUNS_STOP_ONCE,
      r"\bnever starts a bridge\b", r"\bstray bridge raises no late prompt\b"),
     ((", so the call's stray bridge raises no late prompt", ""),)),
    ("s2_a_shutdown_whose_bootstrap_skipped_runs_one_stop_and_nothing_else", "§S2",
     (r"\bbootstrap skipped\b", r"\bshutdown\b", _ONE_STOP_NOTHING_ELSE),
     ((" and nothing else", ", then closes its tabs"),)),
    ("s2_with_no_browser_the_first_call_takes_the_full_two_minutes_before_the_skip", "§S2",
     (r"\bno browser to attach to\b", r"\bfirst call takes the full two minutes before the skip\b"),
     (("the full two minutes", "a moment"),)),
    # CR-MDB-076 §S3
    ("s3_the_gone_away_message_comes_after_the_two_minute_wait_and_is_shared_by_three_causes",
     "§S3",
     ('"' + GONE_AWAY + '"', r"\bafter the two-minute wait\b", r"\bshared by three causes\b"),
     (('**"The attached CDP target appears to have gone away",**', "**A failed attach,**"),)),
    ("s3_its_three_causes_are_reported_together", "§S3",
     (r"\bshared by three causes\b", r"\bwhich the skill reports together\b",
      r"\bchrome stable not running, or remote debugging off\b",
      r"\banother channel \(chromium\) running instead of chrome stable\b",
      r"\bconnection prompt not accepted within the wait\b"),
     ((", which the skill reports together", ""),)),
    ("s3_the_fix_is_the_user_asks_for_the_browser_steps_again_and_accepts_within_a_minute", "§S3",
     (r"\bthe user asks for the browser steps again\b", r"\baccepts within a minute\b"),
     ((", and accepts within a minute", ""),)),
    ("s3_the_skill_never_re_runs_the_browser_steps_on_its_own", "§S3",
     (r"\bthe skill never re-runs them on its own\b",),
     ((" The skill never re-runs them on its own.", ""),)),
    ("s3_the_npx_cause_covers_bridge_failed_to_start_within_n_s", "§S3",
     (r"\bnpx failing to fetch chrome-devtools-mcp\b",
      r'\bincluding "bridge failed to start within <n>s"',
      r"\breport the tool's own message and fix\b"),
     ((', including "Bridge failed to start within <n>s"', ""),)),
)

# MIGRATED at CR-MDB-061 (§S2–§S6): worded as the spec at its VERIFY F1–F9 contracts.
# MIGRATED at CR-MDB-076 (§S1–§S4): the warning, the bridge wait, no retry, the single `stop` and
# the shared message, worded as CR-MDB-076's spec.
#: A spec-worded skill every gate passes — the "conforming" half of each both-ways proof.
CONFORMING_SAMPLE = """---
name: chrome-ui-relay
description: Open, read and close a frontend project's own tabs on the user's running Chrome through chrome-devtools-axi, one bridge per project.
---

# Chrome-UI-Relay

This skill is not the omp-era CDP relay; that relay must never run under Pi.

## Before the first call

Before the first call of every bootstrap and of every shutdown, the skill warns the user, and a services skill relays the warning:

- Chrome will ask them to accept the connection;
- they accept within about a minute, and if Chrome asks again, they accept again;
- any call may restart the bridge, which the tool never reports, and a restart raises a new prompt.

## Invocation and the session

Every call is `npx -y chrome-devtools-axi <verb>` with:

- `CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1`;
- `CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN>`, the value from the project's `.env`;
- `CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000`, the bridge wait of two minutes; on `stop` it does nothing but is kept, so every call reads the same.

Each project has its own bridge, and its `stop` ends only its own.

It never launches a browser and never uses `open`. `<PROJECT_TOKEN>`, `<dev-url>` and `<id>` are values to substitute, never typed literally. `pages` prints its tabs as `pages[N]{id,url,selected}`, one row per tab.

Navigation is `newpage` only: never run `npx -y chrome-devtools-axi open <dev-url>`.

When `PROJECT_TOKEN` is absent, not of the form `[A-Za-z0-9._-]{1,64}`, or `default`:

- the browser steps are skipped;
- the skill reports "no valid session name: set `PROJECT_TOKEN` in `.env`";
- it never falls back to the default session.

## The bridge wait

Each call is given a shell timeout of at least 150 s (2.5 minutes). A call killed by its shell timeout counts as `BRIDGE_NOT_READY`.

The skill never retries a call that ended in `BRIDGE_NOT_READY`: a retry kills the waiting bridge and raises a new prompt.

With no browser to attach to, the first call takes the full two minutes before the skip.

## Inputs

The caller gives three lists:

- the URLs to open;
- the URL patterns the project's tabs match;
- the protected patterns: tabs never selected, evaluated or closed.

**URLs are compared by pattern.** Chrome normalises the URLs it shows (a trailing slash, a redirect), so a tab "shows" a URL to open when its URL matches the project pattern the caller gives for that URL, never by exact string.

**Protected wins everywhere.** A protected tab is never counted as already open, never chosen and never closed. A URL to open that matches a protected pattern is a caller error: it is reported and skipped.

## Open

1. **`pages`.** Keep its id set as "before".
   - A URL to open that already shows in a tab is not opened again.
   - That tab is the user's or a previous bridge's. It is never selected, evaluated or closed.
2. **`newpage <dev-url>`** for each remaining URL. Never navigate an existing or selected tab.
3. **`pages` again.** The new tabs are the "after" ids minus the "before" ids.
   - Every URL opened shows among the new ids.
   - Every "before" id is still there.
   - Otherwise, stop and report.
   - The new tabs are the skill's own for this bridge. It keeps that record as **(id, URL) pairs**, held in the caller's working context; a restarted agent session has no record.
4. **A `newpage` that timed out still made its tab.** Confirm it among the new ids; never retry, since a retry duplicates it.
5. **Rendered text** is confirmed with `selectpage <id>` and `eval document.body.innerText.length` on the skill's own tabs only, never the load event.

## Close

1. **`pages`, fresh.** The tabs to close are those in the skill's record whose id still shows with its recorded URL, and are not protected.
   - If any recorded id shows with a different URL, or is gone while its URL shows on another id, the bridge has restarted silently (the tool never reports a respawn): close nothing, and report the tabs on the project's URLs for the user to close.
2. **`closepage`** each of them.
3. **`pages` again,** to verify. A last-tab no-op shows here as a tab still open.
4. **`stop`.** It disconnects the project's bridge and never closes Chrome.

- **When control fails,** retry once; the single retry never applies to a `BRIDGE_NOT_READY` envelope: that envelope skips. Otherwise report the tabs left open, naming their URLs.
- **When there is no record,** nothing is closed. Tabs on the project's URLs are reported for the user to close.
- **When bootstrap skipped its browser steps,** shutdown skips its own: it runs one `stop` and nothing else, and starts no bridge.

## When the bridge cannot attach

The browser is detected at run time. An envelope carrying `code: BRIDGE_NOT_READY` means:

- the skill's browser steps are skipped;
- the skill runs `stop` once, which never starts a bridge, so the call's stray bridge raises no late prompt;
- the skill reports the envelope's `error` line and every `help` line in full; the suggestions are reported, never run (one of them suggests `open`);
- a skipped browser never fails bootstrap or shutdown.

The causes the tool reports, each with its fix:

- **"The attached CDP target appears to have gone away",** after the two-minute wait. The message is shared by three causes, which the skill reports together:
  - Chrome stable not running, or remote debugging off: enable it at `chrome://inspect/#remote-debugging`;
  - another channel (Chromium) running instead of Chrome stable;
  - the connection prompt not accepted within the wait.

  The fix: the user asks for the browser steps again, and accepts within a minute. The skill never re-runs them on its own.
- **A port collision** ("code 48"): set `CHROME_DEVTOOLS_AXI_PORT` for this session only.
- **`npx` failing to fetch `chrome-devtools-mcp`** on a cold start, including "Bridge failed to start within <n>s": report the tool's own message and fix.

## Reading the output

Every `chrome-devtools-axi` envelope is read whole. It is never piped through grep, head or tail, narrowed with `jq`, or redirected away.
"""


#: The anchored rules' reversed wordings (CR-MDB-061 VERIFY F5): ``(rule_name, (old, new))``. Each
#: reversal keeps the rule's words but turns its meaning around, and must bite its rule.
REVERSALS = (
    ("s5_close_takes_a_fresh_pages_and_closes_recorded_tabs_still_shown_not_protected",
     (("those in the skill's record", "those not in the skill's record"),)),
    ("s6_reports_the_envelopes_error_line_and_every_help_line_in_full",
     (("the skill reports the envelope's", "the skill never reports the envelope's"),)),
    ("s4_the_new_tabs_are_the_skills_own_for_this_bridge_and_it_keeps_that_record",
     (("It keeps that record as **(id, URL) pairs**, held in the caller's working context; "
       "a restarted agent session has no record.", "No record is kept for the session."),)),
    # CR-MDB-076 §S2: the exact value — a longer number keeps the digits but is not it.
    ("s2_every_call_carries_the_bridge_wait_of_exactly_120000_kept_on_stop",
     (("`CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000`",
       "`CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=1200000`"),)),
    # CR-MDB-076 §S2
    ("s2_never_retries_a_bridge_not_ready_call_since_a_retry_kills_the_bridge_and_raises_a_prompt",
     (("The skill never retries a call", "The skill retries a call"),)),
    # CR-MDB-076 §S2
    ("s2_closes_single_retry_never_applies_to_a_bridge_not_ready_envelope_which_skips",
     (("the single retry never applies to", "the single retry also applies to"),)),
    # CR-MDB-076 §S3
    ("s3_the_skill_never_re_runs_the_browser_steps_on_its_own",
     (("The skill never re-runs them on its own.", "The skill re-runs them on its own."),)),
)

#: CR-MDB-076's phrase rules: one per AC bullet of its §S1–§S3, and the renamed prompt-cause rule.
CR_MDB_076_RULES = frozenset({
    "s1_warns_before_the_first_call_of_every_bootstrap_and_shutdown_relayed_by_a_services_skill",
    "s2_every_call_carries_the_bridge_wait_of_exactly_120000_kept_on_stop",
    "s2_each_call_is_given_a_shell_timeout_of_at_least_150_s",
    "s2_a_call_killed_by_its_shell_timeout_counts_as_bridge_not_ready",
    "s2_never_retries_a_bridge_not_ready_call_since_a_retry_kills_the_bridge_and_raises_a_prompt",
    "s2_closes_single_retry_never_applies_to_a_bridge_not_ready_envelope_which_skips",
    "s2_a_bridge_not_ready_skip_runs_stop_once_which_starts_no_bridge_so_no_late_prompt",
    "s2_a_shutdown_whose_bootstrap_skipped_runs_one_stop_and_nothing_else",
    "s2_with_no_browser_the_first_call_takes_the_full_two_minutes_before_the_skip",
    "s3_the_gone_away_message_comes_after_the_two_minute_wait_and_is_shared_by_three_causes",
    "s3_its_three_causes_are_reported_together",
    "s3_the_fix_is_the_user_asks_for_the_browser_steps_again_and_accepts_within_a_minute",
    "s3_the_skill_never_re_runs_the_browser_steps_on_its_own",
    "s3_the_npx_cause_covers_bridge_failed_to_start_within_n_s",
    "s6_the_connection_prompt_not_accepted_within_the_two_minute_wait_shares_the_gone_away_message",
})

#: CR-MDB-076 §S4: each pattern a migrated rule gained, cut from the sample on its own —
#: ``(rule_name, (old, new))``; each must bite its rule, so the migration is proved both ways.
MIGRATED_PATTERN_CUTS = (
    ("s2_every_call_is_npx_with_auto_connect_and_the_project_token_session",
     (("`CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000`",
       "`CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=60000`"),)),
    ("s5_failed_control_retries_once_then_reports_the_tabs_left_open_by_url",
     (("the single retry never applies to", "the single retry also applies to"),)),
    ("s5_a_skipped_bootstrap_means_shutdown_skips_and_starts_no_bridge",
     (("it runs one `stop` and nothing else", "it runs `pages` and `stop`"),)),
    ("s6_an_envelope_carrying_code_bridge_not_ready_skips_the_browser_steps",
     (("the skill runs `stop` once", "the skill runs `stop` after every call"),)),
    ("s6_the_connection_prompt_not_accepted_within_the_two_minute_wait_shares_the_gone_away_message",
     (("after the two-minute wait", "after the start-up timeout"),)),
    ("s6_the_connection_prompt_not_accepted_within_the_two_minute_wait_shares_the_gone_away_message",
     (('**"The attached CDP target appears to have gone away",**', "**A failed attach,**"),)),
)


def _cut(text: str, replacements) -> str:
    for old, new in replacements:
        if text.count(old) != 1:
            raise AssertionError(f"cut {old!r} must occur exactly once in the sample")
        text = text.replace(old, new)
    return text


# ------------------------------------------------------------------ tests ----

class _RealSkillCase(unittest.TestCase):
    """Reads the real skill; a missing bundle is a test failure naming it, never an error."""

    def real_text(self) -> str:
        if not SKILL_MD.is_file():
            self.fail(f"§S1: {SKILL_MD.relative_to(REPO_ROOT)} does not exist")
        return read_text(SKILL_MD)


class ChromeUiRelayBundleTest(_RealSkillCase):
    """§S1 — the bundle, its frontmatter, its heading, its deployment and its text rules."""

    def test_skill_md_frontmatter_is_clean_and_names_chrome_ui_relay(self):
        text = self.real_text()
        self.assertEqual(frontmatter_violations(text, BUNDLE), [])
        self.assertEqual(frontmatter_value(text, "name"), BUNDLE)
        self.assertTrue(frontmatter_value(text, "description"), "§S1: the skill has a description")

    def test_heading_is_chrome_ui_relay(self):
        self.assertEqual(first_heading(self.real_text()), HEADING)

    def test_no_stack_scope_and_discovered_for_every_stack_selection(self):
        self.real_text()
        self.assertNotIn(BUNDLE, deploy.STACK_SCOPED_BUNDLES, "§S1: scoped to no stack")
        missing = [stacks for stacks in [None] + [[s] for s in ALL_STACKS]
                   if BUNDLE not in {p.name for p in deploy._skill_bundles(REPO_ROOT, stacks)}]
        self.assertEqual(missing, [], "§S1: selections whose bundle discovery lacks the skill")

    def test_writes_grep_head_and_tail_as_plain_words_never_code_spans(self):
        self.assertEqual(plain_word_span_findings(self.real_text()), [])

    def test_example_urls_are_the_dev_url_placeholder_never_a_host_and_port(self):
        text = self.real_text()
        self.assertIn(DEV_URL_PLACEHOLDER, text, "§S1: an example URL is written <dev-url>")
        self.assertEqual(host_port_findings(text), [])


def _phrase_test(patterns):
    def test(self):
        self.assertEqual(rule_findings(self.real_text(), patterns), [])
    return test


class ChromeUiRelayPhraseRulesTest(_RealSkillCase):
    """§S1 (the relay statement) and §S2–§S7 — one phrase gate per rule, on the skill's text."""


for _name, _section, _patterns, _cut_pairs in PHRASE_RULES:
    _test = _phrase_test(_patterns)
    _test.__name__ = f"test_{_name}"
    _test.__doc__ = f"{_section}: {_name.split('_', 1)[1].replace('_', ' ')}."
    setattr(ChromeUiRelayPhraseRulesTest, _test.__name__, _test)


class ChromeUiRelayPhraseDetectorProofTest(unittest.TestCase):
    """Every detector kind both ways: the conforming sample passes; each cut bites its rule."""

    def test_rule_names_are_unique(self):
        names = [rule[0] for rule in PHRASE_RULES]
        self.assertEqual(len(names), len(set(names)))

    def test_conforming_sample_passes_every_phrase_rule(self):
        failing = {name: rule_findings(CONFORMING_SAMPLE, patterns)
                   for name, _s, patterns, _c in PHRASE_RULES}
        self.assertEqual({k: v for k, v in failing.items() if v}, {})

    def test_each_cut_of_the_sample_bites_its_rule(self):
        not_biting = [name for name, _s, patterns, cut in PHRASE_RULES
                      if rule_findings(_cut(CONFORMING_SAMPLE, cut), patterns) == []]
        self.assertEqual(not_biting, [])

    def test_reversal_names_are_phrase_rules(self):
        names = {rule[0] for rule in PHRASE_RULES}
        self.assertEqual([name for name, _r in REVERSALS if name not in names], [])
        # MIGRATED at CR-MDB-076 (§S2, §S3): was 3; CR-MDB-076 adds four anchored rules' reversals.
        self.assertEqual(len(REVERSALS), 7)

    def test_each_reversed_wording_of_an_anchored_rule_bites_it(self):
        patterns = {name: rule_patterns for name, _s, rule_patterns, _c in PHRASE_RULES}
        not_biting = [name for name, reversal in REVERSALS
                      if rule_findings(_cut(CONFORMING_SAMPLE, reversal), patterns[name]) == []]
        self.assertEqual(not_biting, [])

    def test_each_migrated_pattern_cut_of_the_sample_bites_its_rule(self):
        # CR-MDB-076 §S4: every pattern a migrated rule gained is proved both ways.
        patterns = {name: rule_patterns for name, _s, rule_patterns, _c in PHRASE_RULES}
        self.assertEqual([name for name, _r in MIGRATED_PATTERN_CUTS if name not in patterns], [])
        not_biting = [(name, cut) for name, cut in MIGRATED_PATTERN_CUTS
                      if rule_findings(_cut(CONFORMING_SAMPLE, cut), patterns[name]) == []]
        self.assertEqual(not_biting, [])

    def test_the_cr_mdb_076_rules_are_all_present(self):
        # CR-MDB-076 §S1–§S3: one rule per AC bullet, plus the renamed prompt-cause rule (§S4).
        names = {rule[0] for rule in PHRASE_RULES}
        self.assertNotIn("s6_the_connection_prompt_not_accepted_within_the_start_up_timeout", names)
        self.assertEqual(sorted(CR_MDB_076_RULES - names), [])

    def test_conforming_sample_names_no_harness_tool(self):
        # CR-MDB-076 §S2: "shell timeout", never a tool's name — the tool-name ratchet's count.
        self.assertEqual(_count_tools(CONFORMING_SAMPLE), {})
        self.assertEqual(_count_tools("Run it with `ctx_shell` and its timeout.\n"), {"ctx_shell": 1},
                         "the count bites on a harness tool's name")

    def test_conforming_sample_passes_the_bundle_text_gates(self):
        self.assertEqual(frontmatter_violations(CONFORMING_SAMPLE, BUNDLE), [])
        self.assertEqual(frontmatter_value(CONFORMING_SAMPLE, "name"), BUNDLE)
        self.assertEqual(first_heading(CONFORMING_SAMPLE), HEADING)
        self.assertEqual(plain_word_span_findings(CONFORMING_SAMPLE), [])
        self.assertEqual(host_port_findings(CONFORMING_SAMPLE), [])
        self.assertIn(DEV_URL_PLACEHOLDER, CONFORMING_SAMPLE)

    def test_heading_and_name_detectors_bite(self):
        self.assertEqual(first_heading("---\nname: x\n---\n\n# Chrome UI Relay\n"), "Chrome UI Relay")
        self.assertIsNone(first_heading("---\nname: x\n---\n\n## Chrome-UI-Relay\n"))
        self.assertEqual(frontmatter_value("---\nname: chrome-relay\n---\n", "name"), "chrome-relay")
        self.assertIsNone(frontmatter_value("# no frontmatter\n", "name"))

    def test_plain_word_span_detector_bites_on_spans_and_spares_plain_words_and_fences(self):
        self.assertEqual(plain_word_span_findings("Never pipe through `grep`.\n"), [(1, "grep")])
        self.assertEqual(len(plain_word_span_findings("Use `head -5` or `tail`.\n")), 2)
        self.assertEqual(plain_word_span_findings("Never piped through grep, head or tail.\n"), [])
        self.assertEqual(plain_word_span_findings("Narrowed with `jq`; a `header` field.\n"), [])

    def test_host_port_detector_bites_on_hosts_with_ports_and_spares_placeholders(self):
        for bad in ("Open `http://localhost:5173`.", "The relay held 127.0.0.1:9224.",
                    "Open `https://app.example.com:8443/`."):
            with self.subTest(bad=bad):
                self.assertEqual(len(host_port_findings(bad)), 1)
        for good in ("Open `<dev-url>`.", "Enable it at `chrome://inspect/#remote-debugging`.",
                     "Only `default` uses 9224; others hash into 9225–10224.",
                     'A port collision ("code 48").', "Set `CHROME_DEVTOOLS_AXI_PORT`."):
            with self.subTest(good=good):
                self.assertEqual(host_port_findings(good), [])

    def test_units_merge_a_lead_in_with_its_list_and_split_paragraphs_and_items(self):
        text = ("Lead-in with:\n\n- one;\n- two.\n\nNext paragraph.\n\n"
                "1. Step one.\n   - nested.\n2. Step two.\n\n## Head\n\n```\nx\ny\n```\n")
        self.assertEqual(units(text), ["lead-in with: - one; - two.", "next paragraph.",
                                       "1. step one. - nested.", "2. step two.", "## head",
                                       "x y"])


class OpenStepGateTest(_RealSkillCase):
    """Negative gate 1 (§S2, AC): no ``chrome-devtools-axi open`` shown as a step — a code span
    or a fenced line, outside a prohibition clause."""

    def test_the_skill_shows_no_open_step(self):
        self.assertEqual(shown_form_findings(self.real_text(), OPEN_STEP), [])

    def test_detector_spares_the_conforming_sample_and_its_governed_open(self):
        self.assertEqual(shown_form_findings(CONFORMING_SAMPLE, OPEN_STEP), [])
        self.assertIn("never run `npx -y chrome-devtools-axi open <dev-url>`", CONFORMING_SAMPLE)

    def test_detector_bites_on_a_fenced_open_line(self):
        text = "Navigate:\n\n```bash\nnpx -y chrome-devtools-axi open <dev-url>\n```\n"
        self.assertEqual(shown_form_findings(text, OPEN_STEP),
                         [(4, "npx -y chrome-devtools-axi open <dev-url>")])

    def test_detector_bites_on_an_ungoverned_span_a_prohibition_governs_only_its_clause(self):
        text = "Do not stop: run `npx -y chrome-devtools-axi  open <dev-url>`.\n"
        self.assertEqual(len(shown_form_findings(text, OPEN_STEP)), 1)
        self.assertEqual(len(shown_form_findings(
            "Then run `chrome-devtools-axi open <dev-url>`.\n", OPEN_STEP)), 1)

    def test_detector_spares_other_verbs_and_prose_mentions(self):
        for good in ("Run `npx -y chrome-devtools-axi newpage <dev-url>`.\n",
                     "The tool's chrome-devtools-axi open verb navigates the selected tab.\n",
                     "It never uses `chrome-devtools-axi open`.\n",
                     "```\n# never run npx -y chrome-devtools-axi open <dev-url>\n```\n"):
            with self.subTest(good=good):
                self.assertEqual(shown_form_findings(good, OPEN_STEP), [])

    def test_detector_joins_backslash_continued_fenced_lines_and_bites_on_a_continued_open(self):
        text = ("Navigate:\n\n```bash\nCHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> \\\n"
                "  npx -y chrome-devtools-axi \\\n  open <dev-url>\n```\n")
        self.assertEqual(shown_form_findings(text, OPEN_STEP),
                         [(4, "CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> "
                              "npx -y chrome-devtools-axi open <dev-url>")])

    def test_detector_spares_a_continued_open_a_prohibition_governs_and_unjoined_lines(self):
        for good in ("```\n# never run npx -y chrome-devtools-axi \\\n  open <dev-url>\n```\n",
                     "```\nnpx -y chrome-devtools-axi pages\nopen <dev-url>\n```\n",
                     "```\nnpx -y chrome-devtools-axi pages \\\n```\n\n```\nopen <dev-url>\n```\n"):
            with self.subTest(good=good):
                self.assertEqual(shown_form_findings(good, OPEN_STEP), [])


class PipedOutputGateTest(_RealSkillCase):
    """Negative gate 2 (§S7, AC): no ``chrome-devtools-axi`` output shown piped through grep,
    head, tail or ``jq``, or redirected away."""

    def test_the_skill_shows_no_piped_or_redirected_output(self):
        self.assertEqual(shown_form_findings(self.real_text(), PIPED_OUTPUT), [])

    def test_detector_spares_the_conforming_sample(self):
        self.assertEqual(shown_form_findings(CONFORMING_SAMPLE, PIPED_OUTPUT), [])

    def test_detector_bites_on_pipes_and_redirects(self):
        for bad in ("```\nnpx -y chrome-devtools-axi pages | grep about\n```\n",
                    "Run `npx -y chrome-devtools-axi pages | head -20`.\n",
                    "Run `npx -y chrome-devtools-axi pages | tail -5`.\n",
                    "Run `npx -y chrome-devtools-axi pages | jq .`.\n",
                    "Run `npx -y chrome-devtools-axi snapshot > /tmp/snap.txt`.\n",
                    "Run `npx -y chrome-devtools-axi pages >>log`.\n",
                    "Run `npx -y chrome-devtools-axi pages 2>/dev/null`.\n",
                    "Run `npx -y chrome-devtools-axi pages &> /dev/null`.\n"):
            with self.subTest(bad=bad):
                self.assertEqual(len(shown_form_findings(bad, PIPED_OUTPUT)), 1)

    def test_detector_bites_on_any_single_pipe_after_the_tool(self):
        for bad in ("Run `npx -y chrome-devtools-axi pages | sed -n 1p`.\n",
                    "Run `npx -y chrome-devtools-axi snapshot | awk '{print $1}'`.\n",
                    "```\nnpx -y chrome-devtools-axi pages | wc -l\n```\n",
                    "Run `npx -y chrome-devtools-axi pages|less`.\n",
                    "Run `npx -y chrome-devtools-axi closepage <id> | cat`.\n"):
            with self.subTest(bad=bad):
                self.assertEqual(len(shown_form_findings(bad, PIPED_OUTPUT)), 1)

    def test_detector_bites_on_a_dollar_paren_capture_of_the_tool(self):
        for bad in ("Run `tabs=$(npx -y chrome-devtools-axi pages)`.\n",
                    "```\necho \"$(CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> npx -y "
                    "chrome-devtools-axi pages)\"\n```\n"):
            with self.subTest(bad=bad):
                self.assertEqual(len(shown_form_findings(bad, PIPED_OUTPUT)), 1)

    def test_detector_bites_on_a_redirect_with_no_space_before_it(self):
        for bad in ("Run `npx -y chrome-devtools-axi pages>/dev/null`.\n",
                    "Run `npx -y chrome-devtools-axi pages>>log`.\n",
                    "Run `npx -y chrome-devtools-axi pages&>/dev/null`.\n",
                    "```\nnpx -y chrome-devtools-axi newpage <dev-url>>/tmp/out\n```\n"):
            with self.subTest(bad=bad):
                self.assertEqual(len(shown_form_findings(bad, PIPED_OUTPUT)), 1)

    def test_detector_bites_on_a_backslash_continued_pipe(self):
        text = "```bash\nnpx -y chrome-devtools-axi pages \\\n  | sed -n 1p\n```\n"
        self.assertEqual(shown_form_findings(text, PIPED_OUTPUT),
                         [(2, "npx -y chrome-devtools-axi pages | sed -n 1p")])

    def test_detector_spares_kept_output_and_governed_examples(self):
        for good in ("Run `npx -y chrome-devtools-axi pages 2>&1`.\n",
                     "Run `npx -y chrome-devtools-axi newpage <dev-url>`.\n",
                     "It is never piped: never `npx -y chrome-devtools-axi pages | grep x`.\n",
                     "Read `grep x file | wc -l` elsewhere.\n"):
            with self.subTest(good=good):
                self.assertEqual(shown_form_findings(good, PIPED_OUTPUT), [])

    def test_detector_spares_or_or_placeholders_and_the_skills_own_call_forms(self):
        for good in ("Run `npx -y chrome-devtools-axi stop || true`.\n",
                     "Run `npx -y chrome-devtools-axi closepage <id>`.\n",
                     "```\nCHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> npx -y chrome-devtools-axi "
                     "newpage <dev-url>\n```\n",
                     "Every call is `npx -y chrome-devtools-axi <verb>`.\n",
                     "```\nnpx -y chrome-devtools-axi selectpage <id> \\\n  2>&1\n```\n",
                     "```\n# never run npx -y chrome-devtools-axi pages \\\n  | sed -n 1p\n```\n"):
            with self.subTest(good=good):
                self.assertEqual(shown_form_findings(good, PIPED_OUTPUT), [])


#: A fenced call carrying every token of ``CALL_TOKENS`` — the conforming half of gate 3's proof.
_FULL_CALL = ("CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> "
              "CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000 npx -y chrome-devtools-axi pages")


def _fenced(*lines: str) -> str:
    return "A call:\n\n```bash\n" + "\n".join(lines) + "\n```\n"


class BridgeWaitTokensGateTest(_RealSkillCase):
    """Negative gate 3 (CR-MDB-076 AC, §S2–§S3): every fenced line running
    ``chrome-devtools-axi`` carries ``CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1``,
    ``CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN>`` and ``CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000``,
    each exactly."""

    def test_every_fenced_call_in_the_skill_carries_the_three_exact_tokens(self):
        text = self.real_text()
        self.assertTrue([n for n, content, prefix in shown(text)
                         if prefix is None and _RUNS_TOOL.search(content)],
                        "CR-MDB-076 §S3: the skill shows its calls as fenced commands")
        self.assertEqual(missing_call_token_findings(text), [])

    def test_the_tokens_are_the_three_the_spec_names(self):
        self.assertEqual(CALL_TOKENS, ("CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1",
                                       "CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN>",
                                       "CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000"))

    def test_detector_spares_a_full_call_the_conforming_sample_and_a_continued_full_call(self):
        self.assertEqual(missing_call_token_findings(_fenced(_FULL_CALL)), [])
        self.assertEqual(missing_call_token_findings(CONFORMING_SAMPLE), [])
        continued = _fenced("CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 \\",
                            "  CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> \\",
                            "  CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000 \\",
                            "  npx -y chrome-devtools-axi stop")
        self.assertEqual(missing_call_token_findings(continued), [])

    def test_detector_bites_on_a_fenced_call_lacking_any_one_token(self):
        for token in CALL_TOKENS:
            with self.subTest(token=token):
                line = " ".join(w for w in _FULL_CALL.split() if w != token)
                self.assertEqual(missing_call_token_findings(_fenced(line)), [(4, line, (token,))])

    def test_detector_bites_on_the_skills_present_two_token_call(self):
        line = ("CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> "
                "npx -y chrome-devtools-axi pages")
        self.assertEqual(missing_call_token_findings(_fenced(line)),
                         [(4, line, ("CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000",))])

    def test_detector_bites_on_a_wrong_value_of_any_token(self):
        for good, bad in (("CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000",
                           "CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=60000"),
                          ("CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000",
                           "CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120s"),
                          ("CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000",
                           "CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=1200000"),
                          ("CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1", "CHROME_DEVTOOLS_AXI_AUTO_CONNECT=0"),
                          ("CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN>",
                           "CHROME_DEVTOOLS_AXI_SESSION=default")):
            with self.subTest(bad=bad):
                line = _FULL_CALL.replace(good, bad)
                self.assertEqual(missing_call_token_findings(_fenced(line)), [(4, line, (good,))])

    def test_detector_bites_on_a_backslash_continued_call_lacking_a_token(self):
        text = _fenced("CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 \\",
                       "  CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> \\",
                       "  CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=60000 \\",
                       "  npx -y chrome-devtools-axi pages")
        self.assertEqual(missing_call_token_findings(text), [(
            4, "CHROME_DEVTOOLS_AXI_AUTO_CONNECT=1 CHROME_DEVTOOLS_AXI_SESSION=<PROJECT_TOKEN> "
               "CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=60000 npx -y chrome-devtools-axi pages",
            ("CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=120000",))])

    def test_detector_reports_each_failing_fenced_line_once(self):
        bare = "npx -y chrome-devtools-axi stop"
        self.assertEqual(missing_call_token_findings(_fenced(_FULL_CALL, bare, bare)),
                         [(5, bare, CALL_TOKENS), (6, bare, CALL_TOKENS)])

    def test_detector_spares_code_spans_comments_and_lines_not_running_the_tool(self):
        for good in ("Every call is `npx -y chrome-devtools-axi <verb>`.\n",
                     "Run `npx -y chrome-devtools-axi pages` with the three variables.\n",
                     _fenced("# never run npx -y chrome-devtools-axi open <dev-url>"),
                     _fenced("npx -y chrome-devtools-mcp@latest"),
                     _fenced("echo CHROME_DEVTOOLS_AXI_BRIDGE_TIMEOUT_MS=60000")):
            with self.subTest(good=good):
                self.assertEqual(missing_call_token_findings(good), [])


if __name__ == "__main__":
    unittest.main()
