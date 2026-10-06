"""THE PACK STAGE'S POOLED WORK — what a work-pool worker derives from its
own parse of one pack resource (issue #362; owner RULINGS 2026-10-04x (4)).

Two units of work, each a function of ONE resource file, the law and (for
the second) the placements of it — never of the airport, the DEM or another
resource — so a worker reads the ``.obj`` itself and returns the small
record the partition keeps:

* :func:`resource_reads` — the per-RESOURCE readings ``_build_member`` asks
  for: the elevated-deck reading, the base profile and the below-zero
  (skirt) reading.  :func:`read_resources_ahead` puts them on
  ``ResourceCache.pre``; each reader's own derivation site takes its answer
  from there at the moment the serial loop would have derived it, so the
  member loop, its ``counts`` / ``skipped`` and every memo fill in today's
  order.
* :func:`member_attrs` — per placed MEMBER, the feet, footprint outline and
  solid height of each of its parts (``contact.part_attrs``).
  :func:`part_attrs_ahead` returns them per member for
  ``contact.partition(attrs=…)``; the placed points and triangles stay in
  the parent, which places them itself for the contact passes.

Nothing here decides anything: with no pool both ``*_ahead`` functions
return empty-handed and the serial code derives the same records.

A worker holds ONE resource at a time (:class:`PackWorker`): tasks are
grouped by resource, and the parse is dropped when the next resource
arrives, so a worker's memory is its largest resource and not the pack.
"""
from __future__ import annotations

import os
import typing as _t

from . import contact as _contact
from . import deck_signature as _deck
from . import obj8 as _obj8
from . import scatter as _scatter
from . import skirt as _skirt
from .pool import WorkPool

__all__ = ["PackWorker", "setup", "open_pool", "resource_reads",
           "read_resources_ahead", "member_attrs", "part_attrs_ahead",
           "placement_reads", "placements_ahead"]


class PackWorker:
    """One worker's state: the law, and a ``ResourceCache`` holding the
    resource it is working on (built as ``pipeline/build.pack_stage``
    builds the build's own: same thickness, same input quantum)."""

    def __init__(self, law, thickness_m: float, quantum_m) -> None:
        self.law = law
        self._mk = (thickness_m, quantum_m)
        self._path: str | None = None
        self._cache: _obj8.ResourceCache | None = None

    def cache_for(self, path: str) -> _obj8.ResourceCache:
        if path != self._path or self._cache is None:
            self._cache = _obj8.ResourceCache(*self._mk)
            self._path = path
        return self._cache


def setup(law, thickness_m: float, quantum_m) -> PackWorker:
    """The pool's per-worker setup."""
    return PackWorker(law, thickness_m, quantum_m)


def open_pool(law, cache: _obj8.ResourceCache, **kw) -> WorkPool:
    """A work pool whose workers read the pack as ``cache`` does."""
    return WorkPool(setup, (law, cache.thickness_m, cache.input_quantum_m), **kw)


def _weight(path: str) -> float:
    try:
        return float(os.path.getsize(path))
    except OSError:
        return 0.0


# ── the per-resource readings ────────────────────────────────────────────

def resource_reads(state: PackWorker, path: str) -> dict:
    """``{kind: reading}`` of one resource — ``deck``, ``base``, ``skirt``,
    each present only where it was derived.  A reading that raises is
    simply absent: the serial loop derives it and raises in its own place,
    if it asks at all."""
    cache, law = state.cache_for(path), state.law
    out: dict = {}
    g = cache.geometry(path)
    if g is None:
        return out
    try:
        out["deck"] = _deck.elevated_deck(cache, path, law)
    except Exception:
        pass
    try:
        out["base"] = _obj8.derive_base_profile(g, cache.components(path), law)
    except Exception:
        pass
    try:
        # the skirt is never asked of a scatter resource, and only of one
        # with below-zero geometry (``skirt._read``'s own pre-screen)
        if (law.tables.structures.skirt.seat_low_side and g.solid.shape[0]
                and cache.y_range(path)[0] < -1e-9
                and not _scatter.is_scatter(cache, path, law)):
            out["skirt"] = _skirt.below_zero_reading(cache, path, law)
    except Exception:
        pass
    return out


def read_resources_ahead(pool: WorkPool | None, cache: _obj8.ResourceCache,
                         paths: _t.Iterable[str]) -> int:
    """Have ``pool`` derive :func:`resource_reads` for ``paths`` (the
    resolved resources the member loop is about to build) and put them on
    ``cache.pre``.  Returns how many resources were read ahead (0 with no
    pool: the loop derives everything itself)."""
    if pool is None or not pool.parallel:
        return 0
    todo = [p for p in dict.fromkeys(paths) if p not in cache.base]
    got = pool.try_map(resource_reads, todo, weights=[_weight(p) for p in todo],
                       what="pack partition: resource readings", unit="resources")
    if got is None:
        return 0
    deck_memo = getattr(cache, "deck_pier", None) or {}
    for path, reads in zip(todo, got):
        for kind, r in reads.items():
            held = {"deck": deck_memo, "base": cache.base, "skirt": cache.skirt}[kind]
            if path not in held:
                cache.pre[(kind, path)] = r
    return len(todo)


# ── the per-member part readings ─────────────────────────────────────────

def member_attrs(state: PackWorker, task: tuple) -> list:
    """``contact.member_attrs`` for every placement of ONE resource:
    ``task = (path, params, [(placement, component indices, is_line,
    is_scatter), …])`` → one list of part readings per placement."""
    path, params, rows = task
    cache = state.cache_for(path)
    geom = cache.geometry(path)
    comps = cache.components(path)
    return [_contact.member_attrs((o, geom, [(k, comps[k]) for k in cis]),
                                  is_line, is_scat, *params)
            for o, cis, is_line, is_scat in rows]


def part_attrs_ahead(pool: WorkPool | None,
                     members: _t.Sequence["_contact.MemberGeometry"],
                     line_members: _t.Collection[int],
                     scatter_members: _t.Collection[int],
                     foot_band_m: float, foot_samples_max: int,
                     station_span_m: float, stations_max: int) -> list | None:
    """Per member, its parts' ``(feet, rings, solid_h)`` derived by
    ``pool`` — the ``attrs`` of ``contact.partition`` — or ``None`` with no
    pool (the placing derives them itself).  The arguments are
    ``contact.placed_parts``' own."""
    if pool is None or not pool.parallel or not members:
        return None
    params = (foot_band_m, foot_samples_max, station_span_m, stations_max)
    lines, scat = set(line_members), set(scatter_members)
    by_path: dict[str, list[int]] = {}
    for mi, (o, _geom, _comps) in enumerate(members):
        by_path.setdefault(o.resolved, []).append(mi)
    tasks = [(path, params,
              [(members[mi][0], tuple(k for k, _c in members[mi][2]),
                mi in lines, mi in scat and mi not in lines) for mi in mis])
             for path, mis in by_path.items()]
    got = pool.try_map(member_attrs, tasks, weights=[_weight(t[0]) for t in tasks],
                       what="pack partition: part outlines", unit="resources")
    if got is None:
        return None
    out: list = [None] * len(members)
    for mis, rows in zip(by_path.values(), got):
        for mi, row in zip(mis, rows):
            out[mi] = row
    return out


# ── the per-placement readings (``obj8.read_placed_objects``) ────────────

def _by_resource(paths: _t.Sequence[str]) -> dict[str, list[int]]:
    """Positions grouped by resource, first appearance first."""
    out: dict[str, list[int]] = {}
    for k, path in enumerate(paths):
        out.setdefault(path, []).append(k)
    return out


def placement_reads(state: PackWorker, task: tuple) -> list:
    """``obj8.read_placement`` for every placement job of ONE resource:
    ``task = (path, read law, [job, …])`` → ``[(PlacedObject, report), …]``."""
    path, law, jobs = task
    cache = state.cache_for(path)
    return [_obj8.read_placement(cache, job, law) for job in jobs]


def placements_ahead(pool: WorkPool | None, jobs: _t.Sequence[tuple],
                     law: "_obj8.ReadLaw") -> list | None:
    """``[obj8.read_placement(job)]`` in job order from ``pool``, or
    ``None`` — the ``ahead`` of ``obj8.read_placed_objects``.  The jobs
    carry their own DEM samples; a worker reads the resource itself."""
    if pool is None or not pool.parallel or not jobs:
        return None
    groups = _by_resource([job[2] for job in jobs])
    tasks = [(path, law, [jobs[k] for k in ks]) for path, ks in groups.items()]
    got = pool.try_map(placement_reads, tasks,
                       weights=[len(t[2]) * _weight(t[0]) for t in tasks],
                       what="reading the pack's objects", unit="resources")
    if got is None:
        return None
    out: list = [None] * len(jobs)
    for ks, rows in zip(groups.values(), got):
        for k, row in zip(ks, rows):
            out[k] = row
    return out
