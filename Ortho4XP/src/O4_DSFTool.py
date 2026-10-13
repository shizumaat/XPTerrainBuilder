"""THE ONE LAUNCHER of X-Plane's ``DSFTool`` (issues #560, #591).

Every DSFTool run in the engine goes through :func:`run`: the pack dump
and encode (``auto_patch_v2.airport.dsf_write``) and the overlay step's
two conversions (``O4_Overlay_Utils``).  It WAITS for the child, bounds
it with a time limit, and turns every way the tool can fail — a non-zero
exit, a signal death, the time limit — into :class:`DsfToolError` whose
message is the real cause.  It lives beside the other ``O4_`` modules so
a tile step can use it without importing the airport package.
"""
from __future__ import annotations

import signal
import subprocess

import O4_Console_Encoding as _console
import O4_External_Writes as _external_writes
import O4_UI_Utils as _ui

__all__ = ["DsfToolError", "exit_in_words", "run"]

#: How the DSFTool child is NAMED when its output path is declared to an
#: armed shared-repo write guard (#159).
_WRITER_NAME = "DSFTool"


class DsfToolError(RuntimeError):
    """DSFTool did not do what it was asked: it exited non-zero, was killed
    by a signal (a crash), ran past its time limit, or wrote nothing.  The
    message is the real cause in plain words (#560)."""

    #: ``True`` when DSFTool was stopped at its time limit.
    timed_out = False
    #: ``True`` when DSFTool was killed by a signal.
    crashed = False


def exit_in_words(returncode: int) -> str:
    """``"crashed (SIGSEGV)"`` for a signal death, else ``"failed (exit N)"``."""
    if returncode < 0:
        try:
            return f"crashed ({signal.Signals(-returncode).name})"
        except ValueError:
            return f"crashed (signal {-returncode})"
    return f"failed (exit {returncode})"


def run(args: list[str], *, writes: str | None = None,
        declares: str | None = None, timeout: float | None = None) -> str:
    """Run DSFTool to its end and return what it printed.

    ``writes`` is the path the child writes and ``declares`` the path an
    armed guard is asked about (default: ``writes`` — they differ when the
    child writes a temp file beside its destination).  Raises
    :class:`DsfToolError` when the tool exits non-zero, dies on a signal or
    is still running after ``timeout`` seconds (it is then stopped)."""
    # A SPAWN IS A WRITE DECLARATION (#159, RULINGS 2026-09-30bs).  DSFTool
    # rewrites the SERVING PACK under the owner's ``Custom Scenery`` (the
    # 2026-09-15av class: lane v2vmmcshore's tile build rewrote the live
    # VHHH pack) and dumps into the shared ``Airport_mod_cache``, and
    # neither write passes the harness's Python-level guard because the
    # writer is a child process.  Declaring the output path means the child
    # is never started when an armed guard refuses it, and the refusal is
    # RECORDED, so swallowing it fails the run.
    if writes is not None:
        _external_writes.declare_external_write(declares or writes,
                                                writer=_WRITER_NAME)
    # DSFTool is a native tool: its messages (echoing the paths it was
    # given) are in the ANSI code page on Windows, UTF-8 elsewhere, and a
    # path in any other spelling must not turn its failure into a
    # UnicodeDecodeError (#419).  The launch keywords make it posix_spawn,
    # never fork (O4_UI_Utils.external_tool_keyword_arguments).
    try:
        proc = subprocess.run(args, capture_output=True, timeout=timeout,
                              **_console.native_tool_pipe(),
                              **_ui.external_tool_keyword_arguments())
    except subprocess.TimeoutExpired:
        error = DsfToolError(f"{' '.join(args[:2])} did not finish within "
                             f"{timeout:g} s and was stopped")
        error.timed_out = True
        raise error from None
    if proc.returncode != 0:
        said = (proc.stderr or proc.stdout).strip()[:400]
        error = DsfToolError(
            f"{' '.join(args[:2])} {exit_in_words(proc.returncode)}"
            + (f": {said}" if said else ""))
        error.crashed = proc.returncode < 0
        raise error
    return proc.stdout or ""
