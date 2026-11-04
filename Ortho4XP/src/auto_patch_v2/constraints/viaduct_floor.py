"""THE R6 VIADUCT ROAD'S FLOOR IS LEVEL B UNDER THE SOLVED APRON BESIDE IT
(owner RULINGS 2026-11-03b Q342 a: "where no object sets level B's height,
it keeps a constant depth under the airside level beside it"; 2026-11-03c
(2) Q368 a: "KPHX T4 south road one continuous lowered stretch"; #1808).

``planar/viaduct_road`` plans each covered run's floor from the RAW DEM of
the apron near it (``_apron_level``) and the generator used to pin every
station at that plan.  Two runs on one road planned that way stand at two
levels, and the run-through between them (``planar/structure_overlap``)
takes the lower floor on one half only, so the run's other half kept its
own and the road stepped where the halves meet (MEASURED KPHX capture
b2lvl: 336.07 against 333.68, a 2.39 m step inside the merged cut).

THE RULE, as a bore's mouth is tied to its solved cap (``structures``'s
datum equality, 2026-09-15h; the run-through's per-cut tie, 483c64057 as
restored by 26a6f872b): each covered RUN is one cut with ONE datum — its two
halves (siblings meeting capless at the run's midpoint) are one level.
Every floor vertex of both halves stands ``[tunnel] mouth_depth_m`` (the
planner's own depth) under the mean SOLVED surface of the airside apron
beside the run, and each half's climb runs straight from that floor to the
top its plan reached.  Two runs a run-through joins keep a datum each: the
floor steps where the airside beside them steps (coordinator correction
2026-11-03, Q342 a), and is one platform where it does not.

THE AIRSIDE BESIDE IT is read at every station of the run's level
stretch: the airside apron-family face nearest the station (a terminal pad,
an apron) within ``[tunnel] viaduct_apron_reach_m``, at its stage-1 level —
a held pad's datum column (``model/platform.datum_vertices``: the pad is one
level), else that face's stage-1 vertex nearest the station.  The run's
witness is the mean of those levels.  MEASURED KPHX (capture b2lvl solved
on main a1c59365c): both T4 runs read the terminal pad's two pieces' datums
(343.60 / 344.13, ``building15`` / ``building15#1``), floor 336.37 for both
— one platform; the planner's raw-DEM median had read 341.18 beside run 0
and 343.57 beside run 1.

Stage 1 drops every row touching the floor (``solve/design_stage.
stage_split``), so the apron never follows the road; stage 2 holds the
floor at the apron stage 1 solved.  Each floor vertex is tied on its own
(#1717 S1's lesson, ``group_level._pin_rigid``: one rigid chain loses whole
to the cheapest conflict on it), one value per station the structure pass
holds laterally level.  Three vertices are never tied:

* a vertex stage 1 solves (the airside's own: a row naming it would pull
  the apron to the road — MEASURED LFPG on main: the plan's pin on the T2
  run's top vertices shared with apron ``dsf:pol459`` held it 4 m under
  its level, 1,111 apron frontage-chord rows relaxed);
* a TILE-SEAM vertex and its station (the seam is a pin everything grades
  to, RULINGS 2026-09-13ah; it keeps the plan's value — MEASURED KPHX run 1
  at lon −112.0000: 0.30 m under the tied floor across the seam band);
* nothing climbs where a half opens onto LEVEL B (a lower level's face at
  its far end, Q340 a: the region runs through) — it stays at the floor.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import apron_roles, role_side
from ..model.constraints import Linear, Pin, Row, Source
from ..model.planar import PlanarMap
from ..model.structures import Tunnel

__all__ = ["viaduct_floor_rows", "is_viaduct_half", "HALF_PREFIX"]

#: an R6 half's tunnel id prefix: ``planar/viaduct_road.ID_PREFIX`` + ``:``
#: (a twin holds the two equal; the planar module is not imported here, so
#: the constraint stage's code key stays the constraint stage's)
HALF_PREFIX = "viaduct-road:"

#: the generator (the rows are the structure pass's, ``structures.GEN``) and
#: the hard head the floor tie is held by (``[design] hard_rulings``
#: registers ``tunnel.mouth_depth_m``: a datum equality is a constraint of
#: the active set, never a weight contest)
_GEN = "structures"
_RULING = ("tunnel.mouth_depth_m (R6 floor under the solved apron beside it; owner RULINGS "
           "2026-11-03b Q342 a, 2026-11-03c (2) Q368 a; #1808)")
#: two stations closer than this along a half's profile are one station
_TOL_M = 0.5
#: the station step the airside beside a run is read at (``viaduct_road``'s)
_STEP_M = 5.0

Stations = _t.Mapping[str, _t.Sequence[tuple[float, _t.Sequence[int]]]]


def is_viaduct_half(tn) -> bool:
    """Whether structure ``tn`` is one half of an R6 run."""
    return str(getattr(tn, "id", "")).startswith(HALF_PREFIX)


def viaduct_floor_rows(planar: PlanarMap, law: Law, tunnels: _t.Sequence[Tunnel],
                       stations: Stations) -> list[Row]:
    """The floor and climb rows of every R6 half in ``stations`` (``tunnel
    id -> [(s, vertex ids)]``, the ramp's station groups; module doc)."""
    halves = [tn for tn in tunnels if tn.id in stations and is_viaduct_half(tn)]
    if not halves:
        return []
    s1, datum = _stage_one(planar, law)
    aprons = _apron_faces(planar, law, s1, datum)
    depth = float(law.tables.structures.tunnel.mouth_depth_m)
    reach = float(law.tables.structures.tunnel.viaduct_apron_reach_m)
    rows: list[Row] = []
    # a TILE-SEAM vertex keeps its pin, and so does the station it stands
    # on (owner RULINGS 2026-09-13ah: the seam is an anchor everything
    # grades to; ``constraints/seams``); a vertex two halves share is tied once
    seam = frozenset(int(v) for v in getattr(planar, "seam_vertices", ()) or ())
    # a vertex stage 1 solves is the airside's: no floor row names it (the
    # row would enter stage 1 and pull the apron to the road)
    done: set[int] = set(s1)
    for comp in _runs(halves):
        ws = _witness(planar, aprons, [_level_run(tn) for tn in comp], reach)
        if not ws:
            rows.extend(_fallback_pins(comp, stations))
            continue
        src = Source(_GEN, _RULING, tuple(t.id for t in comp))
        for tn in comp:
            st = _stations(planar, tn, stations[tn.id])
            level = _opens_onto_level_b(planar, tn, st)
            st = [(s_, vs) for s_, vs in st if not seam.intersection(vs)]
            rows.extend(_half_rows(tn, st, ws, depth, src, done, level))
    return rows


def _stations(planar: PlanarMap, tn: Tunnel, groups
              ) -> list[tuple[float, list[int]]]:
    """The half's stations as the structure pass ties them: its ramp
    faces' station groups (each one ``Flat``, laterally level), joined
    where two faces' groups share a vertex, each at its vertices' mean
    station along the axis — one value per joined station, or the
    ``Flat`` rows and the ties would contradict each other."""
    parent: dict[int, int] = {}

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for _s, vs in groups:
        vs = [int(v) for v in vs]
        for v in vs:
            parent.setdefault(v, v)
        for v in vs[1:]:
            parent[find(v)] = find(vs[0])
    axis = LineString(tn.axis)
    joined: dict[int, list[int]] = {}
    for v in sorted(parent):
        joined.setdefault(find(v), []).append(v)
    out = []
    for vs in joined.values():
        s = sum(axis.project(Point(planar.vertices[v].xy)) for v in vs) / len(vs)
        out.append((s, vs))
    return sorted(out)


def _half_rows(tn: Tunnel, stations, ws: _t.Sequence[int], depth: float, src: Source,
               done: set[int], level: bool = False) -> list[Row]:
    """One half's rows: every level station's vertices at the apron mean
    less ``depth``; every climb station's on the straight line from that
    floor (the level's end) to the plan's top, ``t`` of the way along it —
    none where the half opens onto level B (``level``: it stays at the
    floor to its end).  ``done``: vertices not to tie (tied already, or
    stage 1's), grown."""
    s_f, top = _profile_ends(tn)
    if level:
        s_f, top = float(tn.top_s), None
    n = float(len(ws))
    out: list[Row] = []
    for s, vs in stations:
        s = min(float(s), float(tn.top_s))
        t = 0.0 if top is None or s <= s_f + _TOL_M else \
            min(1.0, (s - s_f) / max(top[0] - s_f, 1e-9))
        for v in vs:
            if v in done:
                continue
            done.add(v)
            if t >= 1.0:
                out.append(Pin(v, float(top[1]), src))
                continue
            # z_v − (1 − t)·mean(w) = t·z_top − (1 − t)·depth, both sides
            terms = ((v, 1.0), *((int(w), -(1.0 - t) / n) for w in ws))
            rhs = (t * float(top[1]) if top is not None else 0.0) - (1.0 - t) * depth
            out.append(Linear(terms, None, rhs, src))
            out.append(Linear(tuple((a, -c) for a, c in terms), None, -rhs, src))
    return out


def _opens_onto_level_b(planar: PlanarMap, tn: Tunnel, stations) -> bool:
    """Whether the half's far end opens onto a LOWER LEVEL (a face whose
    platform is a lower level, ``model/planar.plane_origin_ref`` — the
    test ``model/platform.stage_air_vertices`` reads): the road runs on at
    level B there, so it does not climb (owner RULINGS 2026-11-03b Q340 a,
    the region runs through; its run-outs climb from the region's edge).
    MEASURED LFPG (capture lfpg6, main a1c59365c): the T2 R6 run climbed
    9.97 m to its top against the corridor's level B at 97.59 beside it."""
    from ..model.planar import plane_origin_ref, platform_ref_of
    if not stations:
        return False
    s_end = max(s for s, _vs in stations)
    for s, vs in stations:
        if s < s_end - 3.0 * _TOL_M:
            continue
        for v in vs:
            for fid in planar.vertices[v].incident_faces:
                r = platform_ref_of(planar.faces[fid].ref)
                if plane_origin_ref(r) != r:
                    return True
    return False


def _profile_ends(tn: Tunnel) -> tuple[float, "tuple[float, float] | None"]:
    """``(where the level ends, (s, z) of the climb's top or None)`` off the
    half's planned profile (``viaduct_road._half``: level, then one climb)."""
    prof = [(float(s), float(z)) for s, z in (tn.profile or ())]
    if not prof:
        return float(tn.top_s), None
    z0 = prof[0][1]
    s_f = max(s for s, z in prof if abs(z - z0) <= 1e-6)
    last = prof[-1]
    return s_f, (None if abs(last[1] - z0) <= 1e-6 or last[0] <= s_f + _TOL_M else last)


def _level_run(tn: Tunnel) -> LineString:
    """The half's level stretch along its axis (from the run's midpoint)."""
    ax = LineString(tn.axis)
    s_f, _top = _profile_ends(tn)
    return substring(ax, 0.0, max(min(s_f, ax.length), min(1.0, ax.length)))


def _stage_one(planar: PlanarMap, law: Law) -> "tuple[frozenset[int], dict[str, int]]":
    """``(stage 1's vertices, {held ref: datum column})``: its airside
    faces' vertices and every held pad's datum column (the population
    ``group_level.witness_index`` reads)."""
    from ..model.platform import datum_vertices, stage_air_vertices
    s1 = set(stage_air_vertices(planar, law))
    datum = datum_vertices(planar, law, s1)
    s1.update(datum.values())
    return frozenset(s1), datum


def _apron_faces(planar: PlanarMap, law: Law, keep: _t.AbstractSet[int],
                 datum: _t.Mapping[str, int]
                 ) -> list[tuple[Polygon, tuple[int, ...], tuple[int, ...]]]:
    """Every airside apron-family face as ``(polygon, its stage-1 ring
    vertices, its pad's datum columns)``: a held pad's level is its datum
    column, and a pad cut into pieces is the one pad they were cut from
    (``model/planar.pad_base_ref``), its level every piece's datum."""
    from ..model.planar import pad_base_ref, platform_ref_of
    roles = apron_roles(law)
    pads: dict[str, list[int]] = {}
    for ref, v in datum.items():
        pads.setdefault(pad_base_ref(ref), []).append(int(v))
    out = []
    for f in planar.faces.values():
        if f.role not in roles or role_side(law, f.role) != "airside":
            continue
        ring = planar.ring_vertices(f.ring)
        vs = tuple(v for v in ring if v in keep)
        base = pad_base_ref(platform_ref_of(f.ref))
        ds = tuple(sorted(pads.get(base, ())))
        if len(ring) < 3 or not (vs or ds):
            continue
        poly = Polygon([planar.vertices[v].xy for v in ring])
        out.append((poly if poly.is_valid else poly.buffer(0.0), vs, ds))
    return out


def _witness(planar: PlanarMap, aprons, runs: _t.Sequence[LineString], reach: float
             ) -> list[int]:
    """The airside beside ``runs`` (module doc): at every station, the
    nearest apron-family face within ``reach``, its pad's datum columns or
    its stage-1 vertex nearest the station."""
    if not aprons:
        return []
    tree = STRtree([p for p, _vs, _d in aprons])
    out: set[int] = set()
    for run in runs:
        n = max(2, int(run.length // _STEP_M) + 1)
        for k in range(n):
            q = run.interpolate(run.length * k / (n - 1))
            poly, vs, ds = aprons[int(tree.nearest(q))]
            if poly.distance(q) > reach:
                continue
            if ds:
                out.update(ds)
            elif vs:
                out.add(min(vs, key=lambda v: q.distance(Point(planar.vertices[v].xy))))
    return sorted(out)


def _runs(halves: _t.Sequence[Tunnel]) -> list[list[Tunnel]]:
    """The halves grouped by run: a run's two halves share their mouth
    point, the run's midpoint (``viaduct_road._half``)."""
    runs: dict[tuple[float, float], list[Tunnel]] = {}
    for tn in halves:
        runs.setdefault((round(tn.axis[0][0], 2), round(tn.axis[0][1], 2)), []).append(tn)
    return [sorted(c, key=lambda t: t.id) for _k, c in sorted(runs.items())]


def _fallback_pins(comp, stations: Stations) -> list[Row]:
    """No apron beside the platform on the map: the planned profile, pinned
    per station (the plan the planner made; never silently unbuilt)."""
    from ..model.structures import profile_z
    out: list[Row] = []
    for tn in comp:
        src = Source(_GEN, "cutout.sunken_road: the floor = the planned R6 profile per station "
                     "(no apron vertex beside it on the map)", (tn.id,))
        for s, vs in stations[tn.id]:
            z = profile_z(tn.profile, min(float(s), float(tn.top_s)))
            out.extend(Pin(int(v), z, src) for v in vs)
    return out
