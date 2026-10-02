"""THE CONSOLE IS UTF-8, EVERYWHERE, OR IT IS A DEFECT (issues #171, #125).

One derivation site for the text layer of this process's standard streams.
Nothing else in the engine, the CLI entries or ``tools/`` may configure an
encoding on ``sys.stdout``/``sys.stderr``/``sys.stdin``: they call
:func:`configure_console_streams` and inherit it.

Why
---
Python picks a stream encoding from the *locale*, and on Windows that is
the ANSI code page — cp1252 for a Western install.  The repo's house
spelling is mathematical (``Δ``, ``ε``, ``≥``, ``→``, ``Σ``, ``∩``), and
none of those characters exist in cp1252, so a console write of one is not
mojibake, it is an exception:

* **#171** — ``tools/obj8_split_report.py --help`` raises
  ``UnicodeEncodeError: 'charmap' codec can't encode character 'ε'`` and
  exits rc 1 on a Windows console.  It is a CLASS, not a line: 39 of the
  80 argparse-bearing tools carry a non-cp1252 character in a string
  literal, and ANY of them can die on its own help text.
* **#125** — the FROZEN Windows engine writes its stderr in cp1252, so
  ``Adolfo Suárez Madrid-Barajas`` reaches the app's console drawer and
  ``logs/engine-stderr.log`` as ``Adolfo Su?rez``.  That log is the file
  bug reports ask users for, and `§`/`—` (which cp1252 *does* carry) hid
  how wrong the stream was: the bytes decoded as UTF-8 are undecodable.

Both are the same defect at the same layer, and both are fixed by pinning
the text layer rather than by spelling the house style away.

What this does
--------------
``encoding="utf-8"`` on all three streams, and — the part that matters as
much — an ``errors`` policy that can never raise:

* writes use ``backslashreplace``: a character the stream cannot carry
  comes out as ``\\u03b5``, which NAMES the codepoint.  Lossless in the
  sense that matters for a log: the reader can recover what was written.
  ``replace`` would spend it on ``?``.
* reads use ``replace``: the JSONL command stream must not die on one bad
  byte from a front end.

``PYTHONIOENCODING`` is ``setdefault``-ed so that CHILD processes inherit
the same text layer — the engine re-execs itself as ``--engine-worker``
and ``--lerc-decode`` children, and a frozen Windows exe has no ``-X
utf8`` to hand them.  ``setdefault`` (the ``PYTHONHASHSEED`` precedent in
``Ortho4XP_Qt.py``) so an explicitly chosen value still wins — which is
what lets a twin reproduce #171 by exporting ``PYTHONIOENCODING=cp1252``
and still measure a child's own streams.

What this deliberately does NOT do
----------------------------------
It does not set ``PYTHONUTF8``/UTF-8 mode.  That would change the default
encoding of every ``open()`` in every child, i.e. the *file* layer, which
#92 (RULINGS 17g) already pins explicitly at each writer and reader.  The
console and the corpus are different acts.

It does not replace a stream object it cannot reconfigure.  ``pytest``'s
capture objects and ``io.StringIO`` have no byte layer to mis-encode, and
swapping ``sys.stdout`` out from under a test harness buys a crash class
to fix a crash class.  Such a stream is recorded as skipped, with why.
"""

from __future__ import annotations

import io
import os
import sys
from typing import Any, Dict, Optional

#: The text encoding every console stream is pinned to.
CONSOLE_ENCODING = "utf-8"

#: Write-side error policy: never raises, and NAMES the codepoint it could
#: not carry (``ε``) instead of spending it on ``?``.
WRITE_ERRORS = "backslashreplace"

#: Read-side error policy: never raises; one bad byte from a front end
#: must not end the JSONL read loop.
READ_ERRORS = "replace"

#: What children are told, unless the environment already chose.
CHILD_IO_ENCODING = f"{CONSOLE_ENCODING}:{WRITE_ERRORS}"

_STREAMS = ("stdin", "stdout", "stderr")

# Set once per process; :func:`configure_console_streams` is idempotent so
# that an entry point, a tool and ``jsonl.serve`` can each call it.
_RESULT: Optional[Dict[str, Any]] = None


def _pin(stream: Any, errors: str) -> str:
    """Pin one stream's text layer.  Returns what happened, never raises."""
    if stream is None:
        # A frozen windowed build (``console=False``) has no standard
        # streams at all; pythonw.exe is the same shape.
        return "absent"
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        # pytest capture, io.StringIO, a front end's own wrapper: no byte
        # layer, so no code page to get wrong.
        return "no-reconfigure"
    try:
        if (getattr(stream, "encoding", None) or "").lower().replace("_", "-") \
                in ("utf-8", "utf8") and getattr(stream, "errors", None) == errors:
            return "already-utf-8"
    except Exception:
        pass
    try:
        reconfigure(encoding=CONSOLE_ENCODING, errors=errors)
        return "reconfigured"
    except (ValueError, io.UnsupportedOperation, OSError, AttributeError) as exc:
        # A detached or binary-mode stream.  The errors policy alone is
        # still worth having: it is what turns a crash into a legible
        # escape.
        try:
            reconfigure(errors=errors)
            return f"errors-only ({type(exc).__name__})"
        except Exception:
            return f"refused ({type(exc).__name__})"


def configure_console_streams(force: bool = False) -> Dict[str, Any]:
    """Pin stdin/stdout/stderr to UTF-8 with an error policy that cannot raise.

    Idempotent: the first call in a process does the work and every later
    call returns the same record, so an entry point, ``jsonl.serve`` and a
    tool may each call it without caring who got there first.  ``force``
    re-pins the streams as they are NOW, which is what a twin needs after
    it has installed a simulated cp1252 stream.

    Returns a record of what happened to each stream — ``reconfigured``,
    ``already-utf-8``, ``absent`` (no console at all), ``no-reconfigure``
    (nothing with a code page), ``errors-only`` or ``refused`` — plus the
    ``PYTHONIOENCODING`` the children will see.  Callers do not have to
    read it; the twins do.
    """
    global _RESULT
    if _RESULT is not None and not force:
        return _RESULT
    record: Dict[str, Any] = {}
    for name in _STREAMS:
        errors = READ_ERRORS if name == "stdin" else WRITE_ERRORS
        record[name] = _pin(getattr(sys, name, None), errors)
    # Children inherit the same text layer; an explicit choice still wins.
    os.environ.setdefault("PYTHONIOENCODING", CHILD_IO_ENCODING)
    record["PYTHONIOENCODING"] = os.environ["PYTHONIOENCODING"]
    _RESULT = record
    return record
