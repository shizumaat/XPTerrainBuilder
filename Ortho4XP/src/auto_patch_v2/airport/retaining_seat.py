"""THE RETAINING WALL'S SEAT: its FOOTING on the lowest ground beside its
LOW face (owner RULINGS 2026-11-20m, KLAX; replaces the 16d reading below;
#1934 R3, 2026-11-13u (1); spec ``docs/specs/1934-R3.md``).

20m, verbatim: "Retaining wall here ... between apron and road, should be
seated at the lowest road level, about 2m lower, so it's partially
submerged".  RULED: a wall-type object standing on a level break between
higher pavement and a lower road seats at the lowest level beside it (the
road), its upper side partly buried; it never pulls either pavement.  So
the plate of a wall standing on its ground (no ``sunk_frame`` reading:
a sunk frame's wall keeps the upper-ground plate below, 16l / 16n) is its
FOOTING ``y`` (its lowest static extent, ``top_y - height_m``) on the
stations a grid step outside its LOW face, the ones within the ground bar
(``[placement] split_bar_m``) of the lowest ground along it; the wall's
upper part stands into the higher side's ground.
MEASURED KLAX ``Fence_Terminal_1.obj`` (y -4.20 .. +3.80): the 16d plate
put its footing at 30.87 on the road at 32.6 (test-568 replay), 1.0.562's
connected group at 34.54; 20m puts it on the road.

THE 16d READING IT REPLACES (kept for the record):

A retaining wall's zero is the upper ground it holds
(``wall_class._depth_under_zero``): its retained face reaches down from
there past the low side's ground to a footing authored under it.  The
object stage's generic rule (``anchor_rule._generic_anchor``) knows none of
that and seats a body by its FEET -- the median of ``surface - y`` over
them -- so a wall whose only feet are its footing stands that footing on the
ground under its own plan: the zero rises by the footing's depth.  MEASURED
KLAX ``Fence_Terminal_1.obj`` (y -4.20 .. +3.80, the buried witness, 2.84 m
retained; owner 2026-11-16 14:32Z "still seated at apron level, I expected
it to be about 2 to 3 m lower"): bottom drawn at 34.54, zero 38.74, the
apron 35.2-35.9 beside its upper face.

THE RULE.  A wall-class component that RETAINS and whose retained face
reaches a stated height of its own (``WallComponent.retained_top_y``: its
zero for a depth or buried witness) is seated by a PLATE DATUM: that height
on the solved surface ``grid`` outside its UPPER face (``wall_sides``' own
face and side reading), every ``step`` along it -- the 16d "upper side stays
flush with the wall's top".  Its footing goes where that puts it (13u (1):
a footing under the low side's ground stays buried; no ground is dug to
show it).  A member another rule already seats (``taken``: a tunnel wall's
crest, a basin, an authored seat, a walled plate, a mouth wing, a re-read
entrance face) is never entered, and a wall too low to be read as two
levels (``[service] retaining_wall_clear_step_m``) keeps its seat.

THE ONE SEAT PATH (#2120 R2 W3).  A block too thick or too bent for
``wall_sides._wall_faces`` to name two long faces (an L or U block, a road
block 20 m wide) is seated on the ring round its footprint
(``[service] retaining_wall_step_ring_m`` out), its HIGH side only: the
stations whose ground stands within ``retaining_wall_clear_step_m`` of the
ring's 90th percentile.  Every member of the wall's placement FRAME (its
partition unit: one origin, one lift -- a road block's plate and parapet
rows beside its walls) rides the same plate: the author drew them in one
frame, so one seat moves them together (16u).

NO LAW CONSTANT LIVES HERE: the grid and the step are the caller's
(``emit.identity.min_distinct_spacing_m``,
``structures.bridge.abutment_sample_step_m`` -- the crest plate's own
stations, ``pipeline/rebake_inputs.plate_stations``)."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

__all__ = ["RETAINING_PLATE", "retaining_seats"]

#: the plate kind of a retaining wall's seat (``anchor_rule.datum_of``)
RETAINING_PLATE = "retaining"


@_dc.dataclass(frozen=True)
class _RetainingSeat:
    """One retaining wall's plate: its placement id, the authored ``y`` put
    on the ground (its FOOTING, 20m) and the stations (frame xy) on that
    ground (the low side's)."""

    oid: str
    y: float
    stations: tuple
    resource: str = ""


def _face_stations(face, grid_m: float, step_m: float) -> list:
    """Points ``grid_m`` outside ``face`` (outward is its right:
    ``wall_sides._wall_faces``), every ``step_m`` along it, ends included."""
    off = face.offset_curve(-float(grid_m), join_style="mitre", mitre_limit=2.0)
    out: list = []
    for ln in getattr(off, "geoms", [off]):
        if ln.is_empty or ln.length <= 0.0:
            continue
        n = max(1, int(np.ceil(ln.length / float(step_m))))
        out.extend(tuple(ln.interpolate(float(t)).coords[0])
                   for t in np.linspace(0.0, ln.length, n + 1))
    return out


def _ring_points(whole, ring: float) -> np.ndarray:
    """Points every ``ring`` metres round ``whole`` grown by ``ring``."""
    grown = whole.buffer(ring)
    pts: list = []
    for g in getattr(grown, "geoms", [grown]):
        n = max(4, int(np.ceil(g.exterior.length / ring)))
        pts.extend(g.exterior.interpolate(float(t)).coords[0]
                   for t in np.linspace(0.0, g.exterior.length, n, endpoint=False))
    return np.asarray(pts, dtype=float).reshape(-1, 2)


def _side_ring(dem, pieces, ring: float, clear: float, low: bool) -> list:
    """The ring stations round ``pieces`` (:func:`_ring_points`) on the
    HIGH side (ground within ``clear`` of the ring's 90th percentile) or,
    ``low``, the LOW side (within ``clear`` of its 10th)."""
    from shapely.ops import unary_union

    from .dem import dem_z_many
    xy = _ring_points(unary_union(list(pieces)), ring)
    if not len(xy):
        return []
    z = dem_z_many(dem, xy[:, 0], xy[:, 1])
    ok = np.isfinite(z)
    if not ok.any():
        return []
    if low:
        lo = float(np.percentile(z[ok], 10.0))
        return [tuple(p) for p in xy[ok & (z <= lo + clear)]]
    hi = float(np.percentile(z[ok], 90.0))
    return [tuple(p) for p in xy[ok & (z >= hi - clear)]]


def _lowest(dem, pts: list, clear: float) -> list:
    """The stations of ``pts`` at the LOWEST level beside the wall (20m):
    ground within ``clear`` of the least; every station where none reads."""
    from .dem import dem_z_many
    if not pts:
        return pts
    xy = np.asarray(pts, dtype=float).reshape(-1, 2)
    z = dem_z_many(dem, xy[:, 0], xy[:, 1])
    ok = np.isfinite(z)
    if not ok.any():
        return pts
    lo = float(z[ok].min())
    return [tuple(p) for p in xy[ok & (z <= lo + clear)]]


def _frame_of(airport) -> dict:
    """Placement id -> the ids of every member of its partition unit."""
    out: dict = {}
    for u in getattr(getattr(airport, "partition", None), "units", ()) or ():
        ids = tuple(str(m.id) for m in getattr(u, "members", ()) or ())
        out.update({i: ids for i in ids})
    return out


def retaining_seats(airport, cfg, grid_m: float, step_m: float,
                    taken: _t.Container[str] = frozenset(),
                    comps=None, level_m: float = 0.0) -> tuple[_RetainingSeat, ...]:
    """Every retaining wall of ``airport``'s pack the rule seats (module
    doc), one record per placement.  ``cfg`` is ``classify/rules.toml``'s
    ``[service]`` record (the wall-class law), supplied by the caller;
    ``comps`` the wall-class components when the caller has them;
    ``level_m`` the band that is ONE level at the lowest ground beside a
    wall (``[placement] split_bar_m``, the 12y ground bar; 0 = the clear
    step)."""
    dem = getattr(airport, "dem", None)
    if cfg is None or dem is None or getattr(airport, "partition", None) is None:
        return ()
    from ..model.wall_reach import wall_smear_m
    from .wall_class import wall_class_components
    from .wall_sides import _upper_index, _wall_faces, _walled_plate_ids
    if comps is None:
        comps = wall_class_components(airport, cfg)
    clear = float(getattr(cfg, "retaining_wall_clear_step_m", 0.0) or 0.0)
    ring = getattr(cfg, "retaining_wall_step_ring_m", None)
    plated = _walled_plate_ids(airport)
    by_id: dict[str, _RetainingSeat] = {}
    for w in comps:
        oid = str(getattr(getattr(w, "member", None), "id", "") or "")
        h = float(w.retained_m or w.height_m)
        if not oid or oid in taken or oid in plated or not w.retains \
                or w.retained_top_y is None or h <= clear:
            continue
        # 20m: a wall on its ground seats its footing on the low side; a
        # SUNK frame's wall (``sunk_frame``: drawn down from the author's
        # ground, 16l / 16n) keeps its upper ground
        low = not getattr(w, "sunk_rule", "") and w.top_y is not None
        smear = wall_smear_m(h)
        pts: list = list(by_id[oid].stations) if oid in by_id else []
        for i, g in enumerate(w.pieces):
            faces = _wall_faces(g)
            k = None if faces is None else _upper_index(dem, w, i, faces, smear)
            if k is not None:
                pts.extend(_face_stations(faces[1 - k] if low else faces[k],
                                          grid_m, step_m))
        if not pts and ring is not None:
            pts = _side_ring(dem, w.pieces, float(ring), clear, low)
        if low:
            pts = _lowest(dem, pts, float(level_m) if level_m > 0.0 else clear)
        if pts:
            y = float(w.top_y) - float(w.height_m) if low else float(w.retained_top_y)
            by_id[oid] = _RetainingSeat(oid, y, tuple(pts), str(w.resource or ""))
    # the wall's frame rides its plate: every other member of its placement
    # unit no other rule seats (one origin, one lift: one seat)
    frame = _frame_of(airport)
    for oid, seat in list(by_id.items()):
        for k in frame.get(oid, ()):
            if k not in by_id and k not in taken and k not in plated:
                by_id[k] = _dc.replace(seat, oid=k)
    return tuple(by_id[k] for k in sorted(by_id))
