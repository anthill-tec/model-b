"""A scripted interactive terminal for in-process installer runs
(CR-MDB-036 §S3/§S7/§S8).

The installer only prompts when ``sys.stdin.isatty()`` is true and
``--yes`` is absent, so a subprocess with a piped stdin can never reach
an interactive offer. :func:`run_installer_interactive` instead drives
``modelb_axi.cli.main`` in-process with:

- ``sys.stdin`` replaced by a fake TTY whose ``readline`` (which the
  builtin ``input()`` falls back to for a non-console stdin) answers from
  a *responder*: a function of the text the installer printed since the
  previous read — i.e. the prompt and whatever led up to it;
- ``sys.stdout`` / ``sys.stderr`` captured into one shared transcript;
- ``os.environ`` REPLACED (``clear=True``) by the caller's sandbox env —
  ``HOME``, ``PATH`` and ``PI_CODING_AGENT_DIR`` always pinned — so no
  run reads the real ``~/.pi`` or ``~/.crucible`` and every executable it
  could launch is a sandbox shim.

Every read is recorded as ``(chunk, answer)`` so a test can prove an
offer WAS made (a read whose chunk names it) as well as what happened
after the answer. Stdlib only; not a test module.
"""

import contextlib
import io
import os
import sys
from dataclasses import dataclass, field
from unittest import mock

PROCEED_PROMPT = "Proceed with installation"

class _Transcript:
    def __init__(self):
        self.text = ""

class _CaptureStream(io.TextIOBase):
    def __init__(self, transcript: _Transcript):
        super().__init__()
        self._transcript = transcript
        self.captured = ""

    def write(self, s):
        self.captured += s
        self._transcript.text += s
        return len(s)

    def writable(self):
        return True

    def isatty(self):
        return False

class _ScriptedTTY(io.TextIOBase):
    def __init__(self, transcript: _Transcript, responder):
        super().__init__()
        self._transcript = transcript
        self._pos = 0
        self._responder = responder
        self.reads: list[tuple[str, str]] = []

    def isatty(self):
        return True

    def readable(self):
        return True

    def readline(self, size: int | None = -1):
        chunk = self._transcript.text[self._pos:]
        self._pos = len(self._transcript.text)
        answer = self._responder(chunk)
        self.reads.append((chunk, answer))
        return answer + "\n"

    def read(self, size: int | None = -1):
        return self.readline()

@dataclass
class InteractiveResult:
    returncode: int
    stdout: str
    stderr: str
    reads: list = field(default_factory=list)

    def offers_naming(self, needle: str) -> list[tuple[str, str]]:
        """The reads whose prompt chunk names ``needle``."""
        return [(chunk, answer) for chunk, answer in self.reads if needle in chunk]

def last_line(chunk: str) -> str:
    lines = [ln for ln in chunk.splitlines() if ln.strip()]
    return lines[-1] if lines else ""

def make_responder(rules, default: str = "n"):
    """Answer ``y`` to the installer's ``Proceed with installation?``
    gate, then the first ``(predicate, answer)`` rule whose predicate
    accepts the chunk, else ``default`` (never an implicit yes)."""
    def respond(chunk: str) -> str:
        if PROCEED_PROMPT in last_line(chunk):
            return "y"
        for predicate, answer in rules:
            if predicate(chunk):
                return answer
        return default
    return respond

def run_installer_interactive(argv, env: dict, responder) -> InteractiveResult:
    """Run ``modelb_axi.cli.main(argv)`` in-process on a scripted TTY
    under exactly ``env``. ``SystemExit`` (e.g. an argparse rejection)
    becomes the return code."""
    for required in ("HOME", "PATH", "PI_CODING_AGENT_DIR"):
        if required not in env:
            raise AssertionError(f"sandbox env must pin {required}")
    from modelb_axi.cli import main

    transcript = _Transcript()
    out = _CaptureStream(transcript)
    err = _CaptureStream(transcript)
    tty = _ScriptedTTY(transcript, responder)
    with mock.patch.dict(os.environ, env, clear=True), \
            mock.patch.object(sys, "stdin", tty), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(argv))
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 2)
    return InteractiveResult(code, out.captured, err.captured, list(tty.reads))
