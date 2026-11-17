"""The text of a refused engine command: what failed, where, and why.

A command that raises answers ``{"ok": false, "error": ...}``; the app
prints the error as "Build refused: ...".  1.0.553 printed only
"Error -3 while decompressing data: incorrect header check" -- no file,
no step, no cause.  The cause was the engine's own executable, re-signed
on disk after the engine started: a frozen engine reads each module it
imports late from its executable by offset, so every late import failed
with that zlib error.  :func:`command_error_text` names the exception,
the file and line it was raised at, the engine step (the deepest engine
frame) and, when the engine's executable changed since start, says so.
"""
from __future__ import annotations

import os
import sys
import traceback
from typing import Optional, Tuple

__all__ = ["DETAILED_COMMANDS", "command_error_text"]


def _executable_stamp(path: Optional[str] = None) -> Optional[Tuple[int, int, int]]:
    """``(inode, size, mtime_ns)`` of the frozen engine's executable;
    ``None`` when not frozen or unreadable."""
    if path is None:
        if not getattr(sys, "frozen", False):
            return None
        path = sys.executable
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_ino, st.st_size, st.st_mtime_ns)


#: The executable as this process found it at start (import time: the
#: JSONL transport imports this module before the first command).
_START_STAMP = _executable_stamp()


def _executable_changed(start=None, now=None) -> bool:
    """True when the engine's executable is no longer the file it
    started from (rebuilt, re-signed or replaced on disk)."""
    start = _START_STAMP if start is None else start
    if start is None:
        return False
    now = _executable_stamp() if now is None else now
    return now is not None and now != start


def _where(exc: BaseException) -> Tuple[str, str]:
    """``("file:line in function", engine step)`` of ``exc``: its
    innermost frame, and the deepest frame in the engine's own code."""
    frames = traceback.extract_tb(exc.__traceback__)
    if not frames:
        return "", ""
    last = frames[-1]
    where = "%s:%d in %s" % (os.path.basename(last.filename), last.lineno,
                             last.name)
    step = ""
    for frame in reversed(frames):
        name = frame.filename.replace("\\", "/")
        if "/o4_engine/" in name or "/O4_" in name or "/auto_patch" in name:
            step = "%s.%s" % (
                os.path.splitext(os.path.basename(name))[0], frame.name)
            break
    return where, step


#: Commands whose refusal is printed as a console line ("Build
#: refused: ..."), not shown as a sentence the engine wrote for the
#: user: they carry the type, the place and the step.
DETAILED_COMMANDS = frozenset({"build", "enqueue_build"})


def command_error_text(command: str, exc: BaseException,
                       changed: Optional[bool] = None) -> str:
    """The reply error of ``command``, which raised ``exc``: its text
    (other commands' errors are sentences the apps show as they are);
    for :data:`DETAILED_COMMANDS` also the command, the exception's type,
    where it was raised and the engine step; for every command the
    changed-executable cause when it applies."""
    text = str(exc)
    if command in DETAILED_COMMANDS:
        where, step = _where(exc)
        text = "%s failed: %s: %s" % (command, type(exc).__name__, exc)
        if where:
            text += " (at %s" % where
            text += "; step %s)" % step if step else ")"
    if _executable_changed() if changed is None else changed:
        text += (" -- the engine's program file changed on disk after it "
                 "started (the app was rebuilt or replaced while open): "
                 "quit the app and open it again.")
    return text
