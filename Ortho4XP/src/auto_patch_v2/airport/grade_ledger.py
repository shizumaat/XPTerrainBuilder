"""THE AT-GRADE READ MADE IN WORKERS, CHARGED AS ONE CORE CHARGES IT (issue
#362; owner RULINGS 2026-10-04x (4)).

``obj8_grade.memo_union`` keeps three things on the build's ``ResourceCache``
that later passes read: the memos (``grade_memo`` / ``cover_memo`` /
``clip_memo`` — the basin pass and the second planar pass take their hits
there) and the stats (``cache.grade``: every request is a ``call``, the first
request of a ``(resource, planes)`` key is a ``union`` charged with the
vertices of the component clips it was FIRST to make).  A reader that runs in
a work-pool worker fills the worker's cache instead, so this module carries
the read across:

* in the worker, one TASK's :class:`Ledger` (:func:`begin` / :func:`end`): the
  requests it made, in order, and every memo entry it made;
* in the build's process, :func:`replay`: the tasks' requests are walked in the
  order one core makes them, and each is answered as ``memo_union`` answers it
  there — a ``call``; on the first request of a key the worker's entry enters
  the memo, the component clips nobody had made enter ``clip_memo`` and are
  the vertices charged.  Two workers that made the same entry made the same
  value; it is charged once, where one core charges it.

So ``cache.grade`` (calls, unions, vertices, resources), the three memos and
the fallback rungs of the unions inside an entry are what one core leaves.
The requests replayed are the two the pooled readers make — the cover read
and the polygons-only at-grade read; a LINEWORK request is not replayable
(:class:`Unreplayable`) and its reader stays on one core.  The vertex BUDGET
is not replayed either: a cache whose budget is armed is read on one core
(``reader_work`` asks :func:`replayable`).
"""
from __future__ import annotations

import dataclasses as _dc
import itertools
import typing as _t

from . import frame_entry as _fe
from .obj8_grade import LATER, POLYS, GradeStats

__all__ = ["Ledger", "Recorder", "Unreplayable", "begin", "end", "made", "replay",
           "replayable"]


class Unreplayable(LookupError):
    """A task's at-grade requests cannot be charged from a ledger (module
    doc); its reader is read on one core."""


@_dc.dataclass
class Ledger:
    """One task's at-grade read: ``touches`` — ``(cover, key, placement
    id)`` per request, in order; ``memos`` — ``(cover, key, the polygons,
    seconds, fallback rungs)`` per memo entry made; ``clips`` — ``(clip
    key, the clip, vertices)`` per component clip made; ``rungs`` — the
    fallback rungs of the entries made, which the task's own count must
    not carry twice."""

    touches: list = _dc.field(default_factory=list)
    memos: list = _dc.field(default_factory=list)
    clips: list = _dc.field(default_factory=list)
    rungs: dict = _dc.field(default_factory=dict)

    def own_rungs(self, total: _t.Mapping) -> dict:
        """The task's fallback rungs without its entries' (``total``: every
        rung the task took)."""
        return _minus(total, self.rungs)


@_dc.dataclass
class Recorder(GradeStats):
    """A worker's ``cache.grade``: the stats, and every request kept."""

    touches: list = _dc.field(default_factory=list)
    _rungs: dict = _dc.field(default_factory=dict)

    def asked(self, cover: bool, linework: bool, key: tuple, placement: str) -> None:
        self._rungs = _fe.rung_counts()
        self.touches.append([cover, linework, key, placement, None, None])

    def charge(self, resource: str, vertices: int, seconds: float) -> None:
        super().charge(resource, vertices, seconds)
        row = self.touches[-1]                 # the request that made the entry
        row[4], row[5] = seconds, _minus(_fe.rung_counts(), self._rungs)


def _minus(now: _t.Mapping, then: _t.Mapping) -> dict:
    """Rung counts taken since ``then``."""
    out = {}
    for site, (grid, buf) in now.items():
        g0, b0 = then.get(site, (0, 0))
        if grid - g0 or buf - b0:
            out[site] = (grid - g0, buf - b0)
    return out


def _add(into: dict, rungs: _t.Mapping) -> None:
    for site, (grid, buf) in rungs.items():
        g0, b0 = into.get(site, (0, 0))
        into[site] = (g0 + grid, b0 + buf)


# ── the worker's half ────────────────────────────────────────────────────

def begin(cache) -> tuple[int, int, int]:
    """Open one task's ledger on a worker's cache; the mark :func:`end` takes."""
    if not isinstance(cache.grade, Recorder):
        cache.grade = Recorder()
    cache.grade.touches = []
    return (len(cache.grade_memo), len(cache.cover_memo), len(cache.clip_memo))


def end(cache, mark: tuple[int, int, int]) -> Ledger:
    """The ledger of the task opened at ``mark``.  Raises
    :class:`Unreplayable` for a request or an entry :func:`replay` does not
    answer (module doc)."""
    rows, cache.grade.touches = cache.grade.touches, []
    led = Ledger()
    how: dict[tuple, tuple] = {}
    for cover, linework, key, placement, seconds, rungs in rows:
        if linework:
            raise Unreplayable(f"a linework read of {key[0]}")
        led.touches.append((cover, key, placement))
        if seconds is not None:
            how[(cover, key)] = (seconds, rungs)
            _add(led.rungs, rungs)
    for cover, memo, n0 in ((False, cache.grade_memo, mark[0]), (True, cache.cover_memo, mark[1])):
        for key, val in itertools.islice(memo.items(), n0, None):
            if not cover:
                if val is None or val[0] is not LATER:
                    raise Unreplayable(f"a linework entry of {key[0]}")
                val = val[1]
            led.memos.append((cover, key, val, *how.get((cover, key), (0.0, {}))))
    for ck, val in itertools.islice(cache.clip_memo.items(), mark[2], None):
        if ck[3] is True:
            raise Unreplayable(f"a linework clip of {ck[0]}")
        led.clips.append((ck, val, int(cache.components(ck[0])[ck[1]].tris.shape[0]) * 3))
    return led


# ── the build's half ─────────────────────────────────────────────────────

def replayable(cache) -> bool:
    """May a reader of this cache be charged from ledgers?  Not while the
    vertex budget is armed: a read past it REFUSES on one core, and no
    worker knows where the build's count stands."""
    return not cache.grade.vertex_budget and not cache.grade.over_budget


def made(ledgers: _t.Iterable[Ledger]) -> tuple[dict, dict]:
    """Every entry the workers made: ``({(cover, key): (polygons, seconds,
    rungs)}, {clip key: (clip, vertices)})`` — the first of equal makings."""
    memos: dict = {}
    clips: dict = {}
    for led in ledgers:
        for cover, key, val, seconds, rungs in led.memos:
            memos.setdefault((cover, key), (val, seconds, rungs))
        for ck, val, nv in led.clips:
            clips.setdefault(ck, (val, nv))
    return memos, clips


def replay(cache, ledgers: _t.Sequence[Ledger], entries: tuple[dict, dict], *,
           once: bool = False) -> None:
    """Answer the ``ledgers``' requests on the build's cache, in the order
    given, as ``memo_union`` answers them on one core (module doc).
    ``entries`` is :func:`made` over EVERY ledger the pool returned (an
    entry a task hit may have been made by another task of its worker).
    ``once``: a placement is asked for once over all the ledgers, as a
    reader that keeps its own answer per placement asks.

    Nothing is written before every request is known to be answerable: a
    missing entry raises :class:`Unreplayable` with the cache untouched."""
    st = cache.grade
    memos, clips = entries
    cmemo = cache.clip_memo
    new_memo: tuple[dict, dict] = ({}, {})
    new_clip: dict = {}
    charges: list[tuple] = []
    calls = 0
    seen: set = set()
    for led in ledgers:
        for cover, key, placement in led.touches:
            if once:
                if placement in seen:
                    continue
                seen.add(placement)
            calls += 1
            memo = cache.cover_memo if cover else cache.grade_memo
            if key in memo or key in new_memo[cover]:
                continue
            try:
                val, seconds, rungs = memos[(cover, key)]
                nv = 0
                for ci, plane in key[1]:
                    if not cover and (key[0], ci, plane, True) in cmemo:
                        continue               # a full read's clip answers it
                    ck = (key[0], ci, plane, False if cover else POLYS)
                    if ck in cmemo or ck in new_clip:
                        continue
                    new_clip[ck], n = clips[ck]
                    nv += n
            except KeyError:
                raise Unreplayable(f"no worker returned its entry of {key[0]}") from None
            new_memo[cover][key] = val if cover else (LATER, val)
            charges.append((key[0], nv, seconds, rungs))
    cmemo.update(new_clip)
    cache.grade_memo.update(new_memo[0])
    cache.cover_memo.update(new_memo[1])
    st.calls += calls
    for resource, nv, seconds, rungs in charges:
        st.charge(resource, nv, seconds)
        _fe.add_rung_counts(rungs)
