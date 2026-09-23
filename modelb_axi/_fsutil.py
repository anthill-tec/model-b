"""Atomic file writes for every package write site (CR-MDB-033 §S2).

:func:`atomic_write` writes ``data`` to a temp file in the SAME directory
as the destination (so :func:`os.replace` is a same-filesystem rename),
flushes and fsyncs it, sets its mode, then replaces the destination. A
reader therefore sees either the prior file or the complete new one, never
a torn write.

Mode (§S2 "atomic writes change no file's permissions"): ``tempfile``
creates files 0600, so the mode is always set explicitly on the temp file
BEFORE the replace — the caller's ``mode`` when given (assets carry their
source mode, including the executable bit), otherwise the mode a plain
``open(path, "w")`` would produce, ``0o666 & ~umask``.

Failure: if anything fails once the temp file exists, the temp file is
removed and the error re-raised — the prior destination is left
byte-identical and nothing is left behind. Stdlib only.
"""

import contextlib
import os
import tempfile
from pathlib import Path


def _umask_default_mode() -> int:
    """The mode a plain file creation gets under the current umask.

    The umask can only be read by setting it, so it is set and restored
    immediately; the process umask is unchanged on return."""
    current = os.umask(0)
    os.umask(current)
    return 0o666 & ~current


def atomic_write(path: Path, data: bytes, mode: int | None = None) -> None:
    """Atomically replace ``path`` with ``data`` (temp file + ``os.replace``).

    ``mode`` is applied to the temp file before the replace; ``None`` means
    the umask default (``0o666 & ~umask``), never ``tempfile``'s 0600. The
    parent directory must already exist. On any failure the temp file is
    removed and the original exception propagates."""
    path = Path(path)
    final_mode = _umask_default_mode() if mode is None else mode
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
    )
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_name, final_mode)
        os.replace(tmp_name, path)
    except BaseException:
        # Already gone only if the replace itself completed.
        with contextlib.suppress(FileNotFoundError):
            os.remove(tmp_name)
        raise
