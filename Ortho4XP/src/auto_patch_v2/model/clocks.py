"""THE SUB-STAGE CLOCKS (#2206, fastest-pipeline spec item 6a): one record
per design-surface stage solve (``solve/design._solve_stage``) and one lap
per planar sub-step (``planar/build.build``), so a build's report says
where its solve and planar seconds went without a profiler.

Clocks only: nothing here is read by geometry, a digest or a product, and
a build with or without a collector open is byte-identical.  The build
opens ONE collector around its solves (:func:`collecting`); a solve with
none open records nothing.  :func:`tag` names the purpose of the solves it
encloses (a pin-yield trial, pass 1b) — appended to each record's label.
"""
from __future__ import annotations

import contextlib
import time
import typing as _t

from . import pulse as _pulse

__all__ = ["collecting", "note", "tag", "label", "Laps", "PARTS", "summary", "keep", "take"]

_SINKS: list[list[dict]] = []
_TAGS: list[str] = []


@contextlib.contextmanager
def collecting() -> _t.Iterator[list[dict]]:
    """Inside, every :func:`note` lands in the yielded list (the innermost
    collector only)."""
    recs: list[dict] = []
    _SINKS.append(recs)
    try:
        yield recs
    finally:
        _SINKS.remove(recs)


def note(rec: dict) -> None:
    """Keep one clock record (dropped when no collector is open)."""
    if _SINKS:
        _SINKS[-1].append(rec)


@contextlib.contextmanager
def tag(what: str) -> _t.Iterator[None]:
    """The solves inside carry ``what`` in their label."""
    _TAGS.append(what)
    try:
        yield
    finally:
        _TAGS.pop()


def label(base: str) -> str:
    """``base`` with the open tags, ``/``-joined."""
    return "/".join((base, *_TAGS)) if _TAGS else base


class Laps:
    """Named laps of one running step: :meth:`lap` books the seconds since
    the previous lap (or the start) under ``name`` (summed when repeated).

    ``announce`` (#2206, the classify stage): :meth:`section` names the
    section that STARTS and says so on ``model.pulse`` as ``"<announce>:
    <name>"``, so the heartbeat of a long stage names its section (the
    app read "classifying the airport" for eighteen minutes at KSDL);
    :meth:`close` books the last one and gives the pulse back."""

    def __init__(self, announce: str | None = None) -> None:
        self._t = time.perf_counter()
        self.laps: dict[str, float] = {}
        self._announce = announce
        self._open: str | None = None
        self._prev = _pulse.current()

    def lap(self, name: str) -> None:
        now = time.perf_counter()
        self.laps[name] = self.laps.get(name, 0.0) + (now - self._t)
        self._t = now

    def section(self, name: str) -> None:
        """Book the open section and open ``name``."""
        if self._open is None:
            self._t = time.perf_counter()
        else:
            self.lap(self._open)
        self._open = name
        if self._announce:
            _pulse.tick(f"{self._announce}: {name}")

    def close(self) -> None:
        """Book the open section; the pulse says what it said before."""
        if self._open is not None:
            self.lap(self._open)
            self._open = None
        if self._announce:
            _pulse.tick(*self._prev) if self._prev else _pulse.clear()

    def as_dict(self) -> dict[str, float]:
        return {k: round(v, 3) for k, v in self.laps.items()}

    def line(self, top: int = 8) -> str:
        """The ``top`` dearest laps, dearest first, and the total."""
        rows = sorted(self.laps.items(), key=lambda kv: (-kv[1], kv[0]))
        return ", ".join(f"{k} {v:.1f} s" for k, v in rows[:top]) + \
            f" (total {sum(self.laps.values()):.1f} s)"


#: step -> its last finished :class:`Laps` in this process (:func:`keep`)
_KEPT: dict[str, Laps] = {}


def keep(step: str, laps: Laps) -> None:
    """Hold ``laps`` as ``step``'s last run, for :func:`take`."""
    _KEPT[step] = laps


def take(step: str) -> Laps | None:
    """``step``'s last run, removed — none when the step did not run since
    (a stage the stage cache served reports no older run's clocks)."""
    return _KEPT.pop(step, None)


#: the timed parts of one stage-solve record, in their order
PARTS = ("assemble_s", "lp_s", "qp_s", "projection_s", "report_s")


def summary(recs: _t.Iterable[dict]) -> dict[str, dict]:
    """Per label: the solves, their widest column count and each part's
    seconds summed (the phase ledger's ``solve.<label>.<part>`` entries)."""
    out: dict[str, dict] = {}
    for r in recs:
        s = out.setdefault(str(r.get("label", "")),
                           {"solves": 0, "columns": 0, **{p: 0.0 for p in PARTS},
                            "total_s": 0.0})
        s["solves"] += 1
        s["columns"] = max(s["columns"], int(r.get("columns", 0)))
        for p in (*PARTS, "total_s"):
            s[p] = round(s[p] + float(r.get(p, 0.0)), 3)
    return out
