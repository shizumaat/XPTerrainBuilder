"""The patch editor's heavy read commands answered in ONE spawned worker
process (issue #753), for a front end that runs the engine in its own
process — the Qt app.

Reading an airport pack's buildings (``pack_objects``: the OBJ8 parse and a
convex hull per solid part) takes seconds and holds Python's interpreter
lock for most of them; on a thread of the GUI's process it made the GUI's
10 ms timer late by 0.54-0.55 s at HECA (0.9 s once), and three reads at
once (the box moved twice) answered the wanted box after 56.6 s.  Here it runs in a worker process of
the engine's own work pool (``auto_patch_v2.airport.pool.WorkPool``,
``isolate=True``: spawn, started on the first call, bounded teardown, dies
with its parent), so the GUI thread only waits on a pipe.  The command's
session cache lives in the worker: a re-open of the same box is answered
from it.

The worker sees the caller's configuration: every config variable
(``O4_Cfg_Vars.cfg_vars``) is read in the caller at each call and set in
the worker before the command runs — the Qt app sets some in memory only
(the X-Plane folder from its preferences).

Which commands go here was measured (lane qtstall753, HECA, GUI timer
lateness while the command ran on a thread): ``pack_objects`` 0.46-0.9 s;
``pack_outlines`` 6 ms and ``terrain_sample`` 73 ms stay on threads
(``mesh_crop`` was not measured: no built tile in the lane).
"""
from __future__ import annotations

import threading
import typing as _t

__all__ = ["COMMANDS", "CommandProcess", "Superseded", "config_snapshot"]

#: The commands a :class:`CommandProcess` answers.
COMMANDS = frozenset({"pack_objects"})

#: Seconds without an answer before the worker is declared stuck.
STALL_S = 300.0

_MISSING = object()


class Superseded(RuntimeError):
    """A queued call its caller no longer wanted when its turn came."""


def _owner(cfg, spec: dict):
    """The module a config variable lives in (``O4_Config_Utils`` itself,
    or the module its ``"module"`` entry names, as ``set_global_variables``
    resolves it)."""
    return getattr(cfg, spec["module"], None) if "module" in spec else cfg


def config_snapshot() -> dict:
    """``{name: value}`` of every config variable as THIS process holds it."""
    import O4_Config_Utils as CFG
    out = {}
    for name, spec in CFG.cfg_vars.items():
        owner = _owner(CFG, spec)
        value = getattr(owner, name, _MISSING) if owner is not None else _MISSING
        if value is not _MISSING:
            out[name] = value
    return out


def _apply_config(values: _t.Mapping) -> None:
    import O4_Config_Utils as CFG
    for name, value in values.items():
        spec = CFG.cfg_vars.get(name)
        owner = _owner(CFG, spec) if spec is not None else None
        if owner is not None:
            setattr(owner, name, value)


def _handler(name: str) -> _t.Callable[..., _t.Any]:
    if name == "pack_objects":
        from .pack_objects import pack_objects
        return pack_objects
    raise ValueError(f"The worker process has no {name} command.")


def answer(_state, task: tuple) -> _t.Any:
    """The worker's task: ``(fn, kwargs, config)`` → ``fn(**kwargs)`` under
    the caller's config (a command's own error is raised as it is: the
    caller reads its sentence)."""
    fn, kwargs, config = task
    _apply_config(config)
    return fn(**kwargs)


class CommandProcess:
    """One worker process answering :data:`COMMANDS` (module doc).  Calls
    are serial (one worker); :meth:`call` blocks the calling thread — call
    it from a worker thread, never the GUI's.  :meth:`close` is bounded and
    idempotent; a call after it starts a new worker."""

    def __init__(self, out: _t.Callable[[str], None] = print,
                 stall_s: float = STALL_S) -> None:
        self._out, self._stall = out, float(stall_s)
        self._lock = threading.Lock()
        self._pool = None

    def _open(self):
        from auto_patch_v2.airport.pool import WorkPool
        if self._pool is None or not self._pool.parallel:
            self._pool = WorkPool(workers=1, isolate=True, out=self._out,
                                  stall_s=self._stall, bound="isolated")
        return self._pool

    def call(self, name: str, still_wanted: _t.Callable[[], bool] | None = None,
             **kwargs) -> _t.Any:
        """The command's reply, computed in the worker (:meth:`run`)."""
        return self.run(_handler(name), what=name, still_wanted=still_wanted, **kwargs)

    def run(self, fn: _t.Callable[..., _t.Any], what: str = "",
            still_wanted: _t.Callable[[], bool] | None = None, **kwargs) -> _t.Any:
        """``fn(**kwargs)`` in the worker — ``fn`` a module-level function
        of an importable module (it crosses by name).  Its own error is
        raised here; a worker that died or stopped answering is a
        ``RuntimeError`` with a sentence, and the next call starts afresh.

        Calls queue for the one worker; ``still_wanted()`` is asked when
        this call's turn comes, and ``False`` skips the work (a
        :class:`Superseded` error) — a box the editor has moved on from is
        never read behind the box it now wants."""
        what = what or getattr(fn, "__name__", "command")
        task = (fn, dict(kwargs), config_snapshot())
        with self._lock:
            if still_wanted is not None and not still_wanted():
                raise Superseded(f"{what}: no longer wanted.")
            pool = self._open()
            got = pool.try_map(answer, [task], what=what)
            if got is None:
                why = pool.reason or "it did not start"
                self._pool = None
                raise RuntimeError(f"The {what} worker process stopped ({why}); "
                                   "try again.")
            return got[0]

    def pids(self) -> list[int]:
        """The worker's process id (none before the first call)."""
        pool = self._pool
        return pool.pids() if pool is not None else []

    def close(self) -> None:
        """Stop the worker (bounded: ``pool.TEARDOWN_S`` plus the signals)."""
        pool, self._pool = self._pool, None
        if pool is not None:
            pool.close()
