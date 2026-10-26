"""THE EDIT CACHE's lifetime (#1323; owner RULINGS 2026-10-26h Q148, spec
``docs/specs/incremental-patch-edit-spec.md`` §8.1).

Owner, verbatim: "Add a per tile config setting in expert that lets the
user choose to save more data for faster rebuilds when editing. By default
save every tile only while the app is running, then clear them when the
app quits."

Every build keeps its tile's edit cache (``<build_dir>/fast_path/``, what
``O4_Patch_Fast_Path`` reads) and lists the folder here, in ONE session
list per front end: ``<state>/session-<front end pid>.list``.  When the
session ends the listed folders of every tile whose ``keep_edit_cache`` is
off are deleted:

- the app's engine (``--engine-jsonl``) ends its session when its front end
  goes away — end of input or the parent's death, which is what an app quit
  is; a ``shutdown`` command or a terminate signal is an engine restart
  inside a running app and keeps the list (the next engine of the same app
  appends to it);
- an in-process front end (the Qt app), the CLI and the harness end theirs
  when the process exits;
- an engine's child processes inherit the list (``O4_EDIT_CACHE_LIST``)
  and never end it;
- a list whose front end died without ending it (a crash) is swept by the
  next session to begin.

Never raises: a cache that cannot be listed or cleared costs a fast
rebuild, never a build.
"""
from __future__ import annotations

import atexit
import json
import os
import shutil

__all__ = ["CACHE_DIR_NAME", "LIST_ENV", "cache_dir", "begin_session",
           "register", "end_session", "sweep_orphans"]

#: the tile's edit cache folder, inside its build directory
CACHE_DIR_NAME = "fast_path"
#: the session list a child engine process inherits
LIST_ENV = "O4_EDIT_CACHE_LIST"
#: where the session lists live (tests point it at a temporary folder)
STATE_ENV = "O4_EDIT_CACHE_STATE_DIR"

_owned: dict = {}               # {"path": ..., "pid": ...} when this process owns one


def cache_dir(build_dir: str) -> str:
    """A tile's edit cache folder."""
    return os.path.join(build_dir, CACHE_DIR_NAME)


def _state_dir() -> str:
    return os.environ.get(STATE_ENV) or os.path.join(
        os.path.expanduser("~"), ".ortho4xp", "edit_cache")


def _list_path(frontend_pid: int) -> str:
    return os.path.join(_state_dir(), "session-%d.list" % frontend_pid)


def begin_session(frontend_pid: int | None = None) -> str:
    """The session list this process writes to.  The first call in a
    process that inherited none makes it the list's OWNER for
    ``frontend_pid`` (default: this process, which then ends the session
    at exit) and sweeps the lists crashed front ends left behind."""
    inherited = os.environ.get(LIST_ENV)
    if inherited:
        return inherited
    pid = int(frontend_pid or os.getpid())
    path = _list_path(pid)
    os.environ[LIST_ENV] = path
    _owned.update(path=path, pid=pid)
    if pid == os.getpid():
        atexit.register(end_session)
    sweep_orphans()
    return path


def register(tile) -> None:
    """``tile``'s edit cache was written: list it in this session."""
    try:
        path = begin_session()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        line = json.dumps({"dir": cache_dir(tile.build_dir),
                           "lat": tile.lat, "lon": tile.lon,
                           "custom_build_dir": getattr(
                               tile, "custom_build_dir", "") or ""})
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def _tile_keeps(entry: dict) -> bool:
    """The tile's ``keep_edit_cache`` as its config reads now."""
    try:
        import O4_Config_Utils as CFG
        tile = CFG.Tile(int(entry["lat"]), int(entry["lon"]),
                        entry.get("custom_build_dir") or "")
        tile.read_from_config()
        return bool(getattr(tile, "keep_edit_cache", False))
    except Exception:
        return False


def _clear_list(path: str) -> int:
    """Delete the listed caches of the tiles that do not keep theirs, then
    the list; the number of folders deleted."""
    try:
        with open(path, encoding="utf-8") as handle:
            entries = [json.loads(line) for line in handle if line.strip()]
    except (OSError, ValueError):
        entries = []
    cleared = 0
    for entry in {e.get("dir"): e for e in entries if e.get("dir")}.values():
        folder = entry["dir"]
        if os.path.basename(folder) != CACHE_DIR_NAME or _tile_keeps(entry):
            continue
        if os.path.isdir(folder):
            shutil.rmtree(folder, ignore_errors=True)
            cleared += 1
    try:
        os.remove(path)
    except OSError:
        pass
    return cleared


def end_session() -> int:
    """This process's front end is gone: clear its session (owner only)."""
    path = _owned.pop("path", None)
    _owned.pop("pid", None)
    if not path:
        return 0
    return _clear_list(path)


def sweep_orphans() -> int:
    """Clear every session list whose front end is no longer running."""
    import O4_Process_Liveness as PROC
    folder = _state_dir()
    try:
        names = os.listdir(folder)
    except OSError:
        return 0
    cleared = 0
    for name in names:
        if not (name.startswith("session-") and name.endswith(".list")):
            continue
        try:
            pid = int(name[len("session-"):-len(".list")])
        except ValueError:
            continue
        if pid == _owned.get("pid") or PROC.pid_is_alive(pid) is not False:
            continue
        cleared += _clear_list(os.path.join(folder, name))
    return cleared
