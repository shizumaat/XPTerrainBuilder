"""THE RETAINING WALL'S SEAT: its zero on the ground it retains (#1934 R3;
owner RULINGS 2026-11-16d, 2026-11-13u (1); spec ``docs/specs/1934-R3.md``).

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
    """One retaining wall's plate: its placement id, the authored ``y`` its
    retained face reaches (the height put on the upper ground) and the
    stations (frame xy) on that ground."""

    oid: str
    top_y: float
    stations: tuple
    resource: str = ""


def _upper_stations(face, grid_m: float, step_m: float) -> list:
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


def retaining_seats(airport, cfg, grid_m: float, step_m: float,
                    taken: _t.Container[str] = frozenset(),
                    comps=None) -> tuple[_RetainingSeat, ...]:
    """Every retaining wall of ``airport``'s pack the rule seats (module
    doc), one record per placement.  ``cfg`` is ``classify/rules.toml``'s
    ``[service]`` record (the wall-class law), supplied by the caller;
    ``comps`` the wall-class components when the caller has them."""
    dem = getattr(airport, "dem", None)
    if cfg is None or dem is None or getattr(airport, "partition", None) is None:
        return ()
    from ..model.wall_reach import wall_smear_m
    from .wall_class import wall_class_components
    from .wall_sides import _upper_index, _wall_faces, _walled_plate_ids
    if comps is None:
        comps = wall_class_components(airport, cfg)
    clear = float(getattr(cfg, "retaining_wall_clear_step_m", 0.0) or 0.0)
    plated = _walled_plate_ids(airport)
    by_id: dict[str, _RetainingSeat] = {}
    for w in comps:
        oid = str(getattr(getattr(w, "member", None), "id", "") or "")
        h = float(w.retained_m or w.height_m)
        if not oid or oid in taken or oid in plated or not w.retains \
                or w.retained_top_y is None or h <= clear:
            continue
        smear = wall_smear_m(h)
        pts: list = list(by_id[oid].stations) if oid in by_id else []
        for i, g in enumerate(w.pieces):
            faces = _wall_faces(g)
            k = None if faces is None else _upper_index(dem, w, i, faces, smear)
            if k is not None:
                pts.extend(_upper_stations(faces[k], grid_m, step_m))
        if pts:
            by_id[oid] = _RetainingSeat(oid, float(w.retained_top_y), tuple(pts),
                                       str(w.resource or ""))
    return tuple(by_id[k] for k in sorted(by_id))
