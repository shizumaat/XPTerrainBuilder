"""The engine's process environment: what it must NOT hand to the
processes it starts.

macOS libmalloc reads every ``MallocStackLogging*`` variable at process
start — ``MallocStackLogging=0`` included, since presence is what it
tests — and prints a ``MallocStackLogging: …`` line to stderr in every
process that inherits one.  The engine starts one process per worker,
so a variable left in the environment that launched the app (Xcode's
memory diagnostics, a shell, ``launchctl setenv``) floods the engine
log with one line per worker (owner 2026-11-17, ``engine-stderr.log``:
7,216 "can't turn off malloc stack logging" lines in one run).  The
variables are REMOVED, never set to 0.  The Mac app strips the same
family before it launches the engine (``OrthoProcessRunner.environment``
in SceneryKit); this strip covers every other way in (the Qt window,
a terminal, the harness) and the engine's own children.
"""
import os

__all__ = ["strip_malloc_stack_logging"]

#: variable-name prefixes libmalloc's stack logging answers to; the
#: ``__XPC_`` form is how launchd forwards one into an XPC service.
MALLOC_DEBUG_PREFIXES = ("MallocStackLogging", "__XPC_MallocStackLogging")


def _fold(name):
    """Windows names environment variables case-insensitively and
    ``os.environ`` upper-cases its keys there; macOS and Linux do not."""
    return name.upper() if os.name == "nt" else name


_PREFIXES = tuple(_fold(p) for p in MALLOC_DEBUG_PREFIXES)


def strip_malloc_stack_logging(environ=None):
    """Remove every ``MallocStackLogging*`` variable from ``environ``
    (default ``os.environ``, so every later child inherits the clean
    set); answer the names removed, sorted."""
    env = os.environ if environ is None else environ
    names = sorted(k for k in list(env) if _fold(k).startswith(_PREFIXES))
    for name in names:
        del env[name]
    return names
