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

Every engine child pins its OWN console: ``--engine-worker`` and
``--lerc-decode`` are re-execs of ``Ortho4XP.py`` / ``Ortho4XP_Qt.py``,
whose module body calls this function.  A multiprocessing child (the
airport pool, its Manager, a work-pool worker) reaches it by one of two
roads: FROM SOURCE it re-imports the entry as ``__mp_main__``, which runs
the call; FROZEN it is NOT a re-import — it is the executable re-exec'd as
``--multiprocessing-fork …`` and diverted by ``multiprocessing.
freeze_support()``, never to return — so the entry files make this call
BEFORE ``freeze_support()`` and nothing else comes between (issue #362;
``--pool-selfcheck``'s ``worker`` section reads a frozen worker's text
layer and fails on any other).  A windowed bundle's worker has no console
at all (``sys.stdout is None``, recorded here as ``absent``): ``print`` to
it is a no-op, and no worker-side engine code calls a stream method
directly.  So nothing here needs to reach into a child's environment, and
it does not.

The other end of a child's console
----------------------------------
A parent that reads an engine child's console as TEXT passes
:func:`child_console_pipe` to ``subprocess`` (the tile workers in
``o4_engine.parallel``; the ``--lerc-decode`` child's four readers in
``elevation_access``): ``text=True`` alone decodes with the locale, so
the UTF-8 a worker now writes came back from a Windows parent as
``SuÃ¡rez``, and a byte cp1252 does not define (``Á`` is C3 81) ended
the reader thread.  ``tests/test_console_encoding.py`` holds it with a
cp1252 default, and holds the class from the source.

What this deliberately does NOT do
----------------------------------
**It does not touch ``os.environ``, and in particular does not set
``PYTHONIOENCODING`` for child processes.**  The first version of this
module did, as belt and braces for those re-execs.  Windows CI measured
what that costs (run 36965348610, head 769590f2): flipping a child's
stdout to UTF-8 breaks every parent that reads it as TEXT, because
``subprocess``'s ``text=True`` decodes with the *locale* encoding —
cp1252 on Windows.  Two consumers went red at once, both green on the
base commit:

* ``tests/test_schema_snapshot.py`` compared a locale-decoded dump against
  the UTF-8 snapshot and saw a mismatch it reported as a stale snapshot;
* ``tests/test_blast_index.py`` took ``UnicodeDecodeError: 'charmap'
  codec can't decode byte 0x81`` inside ``subprocess._readerthread``.

That is a census of exactly two consumers, found by accident.  Changing
what a child WRITES is a cross-cutting change whose readers must be
censused first and ruled in ONE table (owner ruling, RULINGS
2026-08-30l), so it is REPORTED, not taken here — and it is unnecessary
for #171 and #125, per the paragraph above.

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


def child_console_pipe() -> Dict[str, Any]:
    """``subprocess`` keywords for a pipe to an ENGINE child read as text.

    The child pinned its console to UTF-8 at its entry; this is the same
    encoding at the parent's end of the pipe, with the read-side error
    policy — one bad byte must not end the parent's reader.
    """
    return {"text": True, "encoding": CONSOLE_ENCODING, "errors": READ_ERRORS}


def configure_console_streams(force: bool = False) -> Dict[str, Any]:
    """Pin stdin/stdout/stderr to UTF-8 with an error policy that cannot raise.

    Idempotent: the first call in a process does the work and every later
    call returns the same record, so an entry point, ``jsonl.serve`` and a
    tool may each call it without caring who got there first.  ``force``
    re-pins the streams as they are NOW, which is what a twin needs after
    it has installed a simulated cp1252 stream.

    Returns a record of what happened to each stream — ``reconfigured``,
    ``already-utf-8``, ``absent`` (no console at all), ``no-reconfigure``
    (nothing with a code page), ``errors-only`` or ``refused``.  Callers do
    not have to read it; the twins do.

    Touches THIS process and nothing else — no environment variable, so no
    child's streams change behind its parent's back (the module docstring
    records what that cost when they did).
    """
    global _RESULT
    if _RESULT is not None and not force:
        return _RESULT
    record: Dict[str, Any] = {}
    for name in _STREAMS:
        errors = READ_ERRORS if name == "stdin" else WRITE_ERRORS
        record[name] = _pin(getattr(sys, name, None), errors)
    _RESULT = record
    return record
