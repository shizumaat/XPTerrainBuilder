"""THE REAL-ROOTS AUDIT GUARD: no test writes the real X-Plane install
or the app state of the real data folder (the 2026-11-11 Convert lane).

Two measured leaks the suite's monkeypatch guards did not see:
``logs/world_pack.log`` of the real data folder held 21 pytest
``install`` lines (``world_commands.write_log`` writes
``FNAMES.data_path("logs")``, a lane worktree's mount of the real
folder), and a Qt test of 2026-10-26 linked two pytest folders into the
real Custom Scenery.  A monkeypatch guard sees only the names it patches;
a reference bound before it (``from os import replace``), ``shutil``'s
``dir_fd`` walk or a C writer (``sqlite3.connect``) pass it by.  An audit
hook (``sys.addaudithook``) is called by the interpreter itself for every
one of them, BEFORE the operation runs, so raising there means the write
never happened.

* :func:`write_targets` -- the paths an audit event would write (pure).
* :func:`violation` -- the first of them inside a protected root and
  outside every exempt folder, resolved through links (pure).
* :func:`arm` -- install the hook (once per process; it cannot be
  removed) with the protected roots and the exempt folders.
* :data:`blocked` -- what the hook refused since the test began, so a
  refusal the code under test swallowed still fails that test.

The protected roots are named by ``conftest`` (``_real_roots``): the
X-Plane install and the World / Convert state of each real data folder.
"""
from __future__ import annotations

import os
import sys
import threading

__all__ = ["RealRootWrite", "write_targets", "violation", "arm", "blocked",
           "state"]


class RealRootWrite(RuntimeError):
    """A test tried to write inside the real X-Plane install or the real
    data folder's app state, and the audit guard stopped it first."""


_WRITE_FLAGS = (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT
                | os.O_TRUNC)
#: event -> ``(path position, its dir_fd position or None)`` of each path
#: it writes (``os.rename`` is also ``os.replace``'s event; ``os.remove``
#: also ``os.unlink``'s).  A RELATIVE path with a ``dir_fd`` names a file
#: of that open folder (``shutil.rmtree``'s walk), not of the cwd: the
#: walk's own top was read at its ``shutil.rmtree`` event.
_PATH_ARGS = {
    "os.remove": ((0, 1),), "os.rmdir": ((0, 1),), "os.mkdir": ((0, 2),),
    "os.rename": ((0, 2), (1, 3)), "os.symlink": ((1, 2),),
    "os.link": ((1, 3),), "os.truncate": ((0, None),),
    "shutil.rmtree": ((0, 1),), "shutil.move": ((0, None), (1, None)),
    "shutil.copyfile": ((1, None),), "shutil.copytree": ((1, None),),
    "sqlite3.connect": ((0, None),),
}
#: Cross-process ``.lock`` files are coordination churn, never state.
_CHURN_SUFFIXES = (".lock",)

#: Paths refused since the running test began (``conftest`` empties it).
blocked: list = []
#: ``{"roots", "exempt", "armed"}`` of this process.
state: dict = {"roots": (), "exempt": (), "armed": False}
_INSIDE = threading.local()


def _text(path):
    if isinstance(path, int) or path is None:
        return None
    try:
        path = os.fspath(path)
    except TypeError:
        return None
    if isinstance(path, bytes):
        path = path.decode("utf-8", "replace")
    return path if isinstance(path, str) and path else None


def write_targets(event: str, args: tuple) -> tuple:
    """The paths ``event`` (with its audit ``args``) would write; ``()``
    for a read, an fd or an event that writes nothing."""
    if event == "open":
        path, mode, flags = (tuple(args) + (None, None, None))[:3]
        if isinstance(mode, str):
            writes = any(c in mode for c in "wax+")
        else:
            writes = bool((flags or 0) & _WRITE_FLAGS)
        text = _text(path) if writes else None
        return (text,) if text else ()
    out = []
    for at, fd_at in _PATH_ARGS.get(event, ()):
        text = _text(args[at]) if at < len(args) else None
        dir_fd = args[fd_at] if fd_at is not None and fd_at < len(args) else None
        if not text or text == ":memory:" or (
                dir_fd is not None and not os.path.isabs(text)):
            continue
        out.append(text)
    return tuple(out)


def _inside(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def violation(paths, roots, exempt=()) -> "str | None":
    """The first of ``paths`` inside one of ``roots`` (real paths) and
    outside every ``exempt`` folder -- the path itself resolved through
    links, and its folder resolved with its own name kept (removing a
    LINK in a protected folder is a write there, wherever it points)."""
    for path in paths:
        if path.endswith(_CHURN_SUFFIXES):
            continue
        full = os.path.abspath(path)
        seen = {os.path.realpath(full),
                os.path.join(os.path.realpath(os.path.dirname(full)),
                             os.path.basename(full))}
        for real in seen:
            if any(_inside(real, folder) for folder in exempt):
                continue
            if any(_inside(real, root) for root in roots):
                return real
    return None


def _hook(event: str, args: tuple) -> None:
    if not state["armed"] or getattr(_INSIDE, "busy", False):
        return
    if event != "open" and event not in _PATH_ARGS:
        return
    _INSIDE.busy = True
    try:
        paths = write_targets(event, args)
        if event == "os.mkdir" and paths and os.path.isdir(paths[0]):
            paths = ()      # makedirs(exist_ok=True) on a folder that is there
        hit = violation(paths, state["roots"], state["exempt"]) if paths else None
    finally:
        _INSIDE.busy = False
    if hit:
        blocked.append({"path": hit, "via": event})
        raise RealRootWrite(
            f"BLOCKED by the real-roots audit guard: this test tried "
            f"{event} on '{hit}', inside the real X-Plane install or the "
            f"real data folder's app state (protected: "
            f"{', '.join(state['roots'])}).  Point the writer at tmp_path.")


def arm(roots, exempt) -> None:
    """Protect ``roots`` (outside ``exempt``) from now on in this process."""
    state["roots"] = tuple(sorted({os.path.realpath(r) for r in roots if r}))
    state["exempt"] = tuple(sorted({os.path.realpath(e) for e in exempt if e}))
    if not getattr(sys, "_o4_real_roots_hook", False):
        sys.addaudithook(_hook)
        sys._o4_real_roots_hook = True
    state["armed"] = True
