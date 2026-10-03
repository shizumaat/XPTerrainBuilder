"""§20b STAGE 1's SPLIT — which vertex the AIRSIDE problem owns, and which it
is FOREIGN to (owner RULINGS 2026-09-13dh, ordered 14an: "airside solves
first, everything else conforms"; split out of ``solve/design.py`` by the
1,500-line file law, 2026-10-02, when the pinned-groundside rule below landed).

THIS IS THE SINGLE DERIVATION SITE of stage 1's population (owner 2026-08-30l:
trim at the derivation, never per consumer).  ``solve/design.assemble`` reads
its two returns as ``drop`` / ``fixed`` and nothing re-derives them;
``solve.pin_yield.stage1_read_pins`` and ``tools/v2_solve_replay``'s
``--why-hard`` / stage-1 dump read the same set.  ``solve/design`` re-exports
:func:`stage_split`, so every importer and twin is unchanged.
"""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..model.constraints import ConstraintSet
from ..model.planar import PlanarMap
from .design_roles import (airside_stage_vertices, groundside_pin_rulings,
                           ruling_head)
from .rows import _Reduction, _reduce

__all__ = ["stage_split"]


def stage_split(planar: PlanarMap, cs: ConstraintSet, law: Law
                ) -> tuple[frozenset[int], dict[int, float]]:
    """§20b STAGE 1's SPLIT: the vertices whose columns are FOREIGN to the
    airside problem, and the dummy values they are fixed at.

    A column is AIRSIDE when any vertex mapped to it is a vertex of an
    airside-pavement face (:func:`airside_stage_vertices`) — the test is on
    the COLUMN, because a rigid ``Flat`` group welded to an apron vertex is
    ONE unknown and the airside's own weld decides it.  Every other FREE
    vertex is foreign: it is fixed (so it carries no column) and every row
    touching it is dropped (``_Rows.drop``), which is the brief's "every row
    whose every column is airside".  A vertex already FIXED — a ``Pin``, a
    threshold, a seam pin (§38) — is never foreign WHERE THE PIN IS THE
    AIRSIDE'S OWN: a constant is not a column, and the rows footed on it
    belong to stage 1 exactly as the law states them.

    A PINNED GROUNDSIDE VERTEX IS FOREIGN (owner RULINGS 2026-10-02v (1),
    issue #143; 2026-09-30aa rule 1 read for EVERY road face, not only the
    mapped-road ribbons — :func:`_groundside_pinned`).  The sentence above was
    the whole rule, and it left the groundside road one door onto the airside:
    a §37 (9) coverage-edge join pin IS a constant, so every road row footed on
    it entered the AIRSIDE problem and held the apron at the core ribbon's
    level — MEASURED 10 such rows at HECA and 21 at KCLT, every one through a
    ``roads.coverage_edge join`` pin, the worst holding an apron ring vertex
    1.00 m up at 30.13577666876, 31.41073906739.  Lane ``roadrows143`` shut
    that door ONE GENERATOR AT A TIME (``roads``, ``transverse``,
    ``pavement_cap`` and the ceiling twin: a row with airside AND groundside
    feet minted one-way on its groundside feet,
    ``constraints/roads.road_pair_side`` — which stays, because it also decides
    who FOLLOWS in stage 2).  This is the same law at stage 1's own site, so it
    holds for every generator there is and for every road face: ``road_ramp``'s
    own ramp and ceiling rows, ``road_cross_section``, and whatever is minted
    next.  The airside vertex solves FREE and the road conforms in stage 2."""
    red0 = _reduce(planar, cs, {})
    air_v = airside_stage_vertices(planar, law)
    air_cols = {int(red0.col[v]) for v in air_v if red0.col[v] >= 0}
    foreign: dict[int, float] = dict(
        _groundside_pinned(planar, cs, law, red0, air_v))
    for vid in range(len(planar.vertices)):
        col = int(red0.col[vid])
        if col < 0 or col in air_cols:
            continue
        dz = planar.vertices[vid].dem_z
        foreign[vid] = float(dz) if dz is not None else 0.0
    return frozenset(foreign), foreign


def _groundside_pinned(planar: PlanarMap, cs: ConstraintSet, law: Law,
                       red: _Reduction, air: _t.AbstractSet[int]
                       ) -> dict[int, float]:
    """THE PINNED GROUNDSIDE VERTICES §20b stage 1 is FOREIGN to, at the value
    the reduction fixed them at (owner RULINGS 2026-10-02v (1), issue #143) —
    ``{vertex: z}``.

    A pin qualifies by its ruling HEAD (``[design] groundside_pin_rulings``,
    the law's own register — there is no hand list here) and by its SIDE:

    * THE TEST IS ON THE RIGID CLASS, not the vertex, exactly as the airside
      test in :func:`stage_split` is on the COLUMN.  A pin welded into a
      ``Flat`` group that contains an airside vertex fixes that whole group —
      the apron's value is in it — so the class is AIRSIDE and keeps every
      row: that road IS the apron (the free-road ruling,
      ``roads.road_pair_side``'s ``PAIR_AIRSIDE``), and dropping the apron's
      own rows there is the one way this rule could MOVE the airside instead
      of freeing it.
    * every vertex of a qualifying class is foreign, not only the pinned one:
      the class is ONE value, so a row footed on any member of it is footed on
      the pin.

    The value is ``red.value`` — the constant the reduction itself assigned —
    so no second reading of the pin's ``z`` can drift from it.  ``assemble``
    substitutes it exactly as a ``Pin`` is substituted (``_reduce``'s
    ``setdefault``: the pin still outranks) and DROPS every row touching the
    class, which is the whole effect.  Stage 2 is untouched: the pin is a pin
    there, and ``road_ramp.welded_join_release`` between the stages still
    releases the join whose welded row cannot hold against stage 1's value."""
    heads = groundside_pin_rulings(law)
    if not heads:
        return {}
    roots = {red.find(int(p.v)) for p in cs.pins if ruling_head(p) in heads}
    if not roots:                       # no such pin: not one find over ``air``
        return {}
    roots -= {red.find(int(v)) for v in air}
    if not roots:
        return {}
    return {vid: float(red.value[vid]) for vid in range(len(planar.vertices))
            if red.find(vid) in roots}


def _welded_faces(planar: PlanarMap) -> set[int]:
    """The WELDED road faces (RULINGS 2026-09-30aa): the mapped-road
    RIBBONS (``model.planar.is_osm_ribbon_ref``) — the same predicate as
    ``constraints/roads.welded_road`` (``solve`` may not import
    ``constraints``).  Measured (lane ``roadweld100``, HECA replay): the
    rule over the apt.dat 1206 routes' own faces moves the reference
    airside (3,537 nodes, worst 1.00 m) — an owner question."""
    from ..model.planar import is_osm_ribbon_ref
    return {f.id for f in planar.faces.values()
            if f.role == "service_road" and is_osm_ribbon_ref(f.ref)}


#: the generators whose rows a WELDED road face MINTS (``constraints/
#: roads.GEN``, ``road_ramp.GEN``, ``pavement_cap.GEN``, ``ceiling.GEN``;
#: ``solve`` may not import ``constraints``, so the names are spelled here
#: and ``tests/auto_patch_v2/test_roadmint100.py`` holds them equal)
_ROAD_GENERATORS = frozenset({"roads", "road_ramp", "pavement_road_cap",
                              "pavement_ceiling"})


def _groundside_minter(planar: PlanarMap, law: Law
                       ) -> _t.Callable[[_t.Any], bool]:
    """RULINGS 2026-09-30aa rule 1: ``row -> True`` when the row names a
    ``face:N`` input whose face is a WELDED road face — the row that face
    MINTED, stage 2's whatever its columns."""
    gs = _welded_faces(planar)

    def _is(row) -> bool:
        if not gs:
            return False
        src = getattr(row, "source", None)
        # THE ROAD'S OWN GENERATORS ONLY (lane roadmint100b, measured
        # CYXY): the apron's edge-portion cap along an edge it shares with
        # a ribbon names the ribbon face as its input too, and dropping
        # those 124 APRON rows from stage 1 moved a pad-welded taxiway
        # 2.26 m at 60.70471799655, -135.07455343850 — the apron's law on
        # its own edge is stage 1's whatever face it reads
        if getattr(src, "generator", None) not in _ROAD_GENERATORS:
            return False
        for t in getattr(src, "inputs", ()) or ():
            if isinstance(t, str) and t.startswith("face:"):
                try:
                    if int(t[5:]) in gs:
                        return True
                except ValueError:
                    continue
        return False
    return _is


def stage_one_on(stage1: _t.Any, law: Law, solve1: _t.Callable, yield_heads
                 ) -> tuple:
    """§20b STAGE 1 ASSEMBLED ON THE RIBBON-FREE MAP (issue #100 round 8,
    master decision option (c); ``pipeline/stage_one_map.StageOne``, read
    duck-typed: ``solve`` may not import ``pipeline``).  Pass 1a, the
    interval, pass 1b and the jetway-strip projection run on
    ``stage1.pm`` / ``stage1.cs`` under that map's own module registries
    (``stage1.scope()``), so every stage-1 row, column, triangle and sheet
    face is the ribbon-free map's by construction.  Returns ``(solve1's
    answer, pass-1a record, released pins, levels, stage-1-read pins,
    strip report)`` with the levels, the released pins and the read pins
    carried onto the FULL map by the coordinate join (``stage1.to_full``);
    the answer itself keeps the ribbon-free ids (``hold.finish`` reads
    them)."""
    from .flex import stage_one
    from .pin_yield import stage1_read_pins
    strip_rep = None
    with stage1.scope():
        pm1, cs1, got, pass1a, yielded1 = stage_one(stage1.pm, stage1.cs, law,
                                                    stage1.hold, solve1)
        drop, levels1 = got[2], got[4]
        read1 = (stage1_read_pins(cs1, yield_heads, drop)
                 | {int(r["v"]) for r in yielded1} if yield_heads else frozenset())
        if stage1.strips:
            from .project_strip import project_strips
            strip_rep = project_strips(pm1, law, stage1.strips, levels1,
                                       got[0].z, cs1.flats)
    to = stage1.to_full
    levels = {j: z for v, z in levels1.items() if (j := to(v)) is not None}
    s1_read = frozenset(j for j in map(to, read1) if j is not None)
    released = [dict(r, v=to(r["v"]), v_stage1=int(r["v"]))
                for r in yielded1 if to(r["v"]) is not None]
    stage1.report.update(levels=len(levels1), levels_unmapped=len(levels1) - len(levels),
                         released_unmapped=len(yielded1) - len(released))
    return got, pass1a, released, levels, s1_read, strip_rep
