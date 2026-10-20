"""THE PACK'S OPEN RAMP OBJECTS AT THE BORE'S MOUTH (#1028 Q31; owner
2026-10-20 answer 41) — which open descending plates
(``airport/sunken_roads``, ``RampCorridor.open_ramp``) set a tunnel's mouth,
and the OSM mouths they replace.

Owner: "Pack open-portal objects set the tunnel mouth only where the ground
doesn't already carry the cutting, and never inside a taxiway strip."  The
first gate is read where the plate is profiled (``sunken_roads._one_ramp``
callers: the DEM within ``open_dem_carries_m`` of the floor along the whole
ramp); this module holds the second gate and the two readings that follow:

* :func:`admitted_open_ramps` — the ONE derivation site (``planar/build``,
  before any consumer — channels, basins, structures — reads the groups):
  the two filters below, in order;
* :func:`open_ramps_off_strip` — an open ramp whose footprint meets a runway
  or taxiway STRIP (the cell ⊕ ``structure_underpass.strip_half_width_m``,
  the one derivation ``verify/keepout.ramp_in_strip`` prices) is refused;
* :func:`open_ramps_unclaimed` — one another object reading already governs
  is that reading's;
* :func:`open_ramp_precedence` — an OSM mouth standing in an admitted open
  ramp is the object's (05n-3)."""
from __future__ import annotations

import typing as _t

from shapely.ops import unary_union

from ..classify.roles import TAXI_FAMILY, is_runway_shoulder
from ..law import Law
from ..law.reference_code import ref_status, status_by_ref
from .object_corridor import mouth_covered_by
from .structure_approach import standing_cover
from .structure_underpass import strip_half_width_m

__all__ = ["admitted_open_ramps", "strip_region", "open_ramps_off_strip", "open_ramps_unclaimed",
           "open_ramp_precedence"]

_RUNWAY_FAMILY = ("runway", "runway_crossing")
_MITRE = dict(join_style="mitre", mitre_limit=2.0)


def _is_open(g) -> bool:
    return bool(getattr(g.corridor, "open_ramp", False))


def strip_region(polys: _t.Sequence, cells: _t.Sequence, law: Law, status_of):
    """The RUNWAY and TAXIWAY strips: every runway- or taxi-family cell (a
    runway shoulder manufactures no region, §40 (4)) grown by its class's
    strip half width — ``None`` when the field has none."""
    out = []
    for p, c in zip(polys, cells, strict=True):
        if c.role not in _RUNWAY_FAMILY and c.role not in TAXI_FAMILY:
            continue
        if is_runway_shoulder(c):
            continue
        hw = strip_half_width_m(law, c, ref_status(status_of, c.ref))
        out.append(p.buffer(hw, **_MITRE) if hw > 0.0 else p)
    return unary_union(out) if out else None


def open_ramps_off_strip(extra_groups: list, strip, refused: list) -> list:
    """NEVER INSIDE A TAXIWAY STRIP (owner 2026-10-20 answer 41; 19e/19q
    forbid cutting a strip): an open ramp whose footprint meets ``strip``
    (:func:`strip_region`) over any area is refused, named; the OSM mouths
    there stand as before."""
    if strip is None:
        return list(extra_groups)
    out = []
    for g in extra_groups:
        if _is_open(g):
            a = g.corridor.footprint.intersection(strip).area
            if a > 1e-6:
                refused.append(f"{g.tid}: the open ramp object meets a runway or "
                                     f"taxiway strip over {a:.0f} m2 (#1028 answer 41: "
                                     f"never inside a taxiway strip)")
                continue
        out.append(g)
    return out


def open_ramps_unclaimed(extra_groups: list, corridors: _t.Sequence, refused: list) -> list:
    """An OPEN ramp object another object reading already governs — a
    tunnel wall or shell corridor whose footprint it meets, or that reads
    one of its placements — is that reading's, never read twice: the open
    group is dropped, named."""
    feet = [c.footprint for c in corridors]
    read = {o for c in corridors for o in (getattr(c, "objects", ()) or ())}
    out = []
    for g in extra_groups:
        c = g.corridor
        if _is_open(g) and (any(c.footprint.intersects(f) for f in feet)
                            or read & set(c.objects or ())):
            refused.append(f"{g.tid}: the open ramp object is already a tunnel "
                                 f"corridor's (#1028 Q31: one object reading)")
            continue
        out.append(g)
    return out


def admitted_open_ramps(extra_groups: _t.Sequence, corridors: _t.Sequence, classification,
                        airport, law: Law, refused: list) -> list:
    """The door, sunken-road and wall-corridor groups with every OPEN ramp
    that is not its own removed, named in ``refused``: one another object
    reading governs (:func:`open_ramps_unclaimed`), and one that meets a
    runway or taxiway strip (:func:`open_ramps_off_strip`).  Every other
    group passes untouched, in order."""
    out = open_ramps_unclaimed(list(extra_groups), corridors, refused)
    if not any(_is_open(g) for g in out):
        return out
    cells, _gap, polys = standing_cover(classification)
    strip = strip_region(polys, cells, law, status_by_ref(getattr(airport, "runways", ())))
    return open_ramps_off_strip(out, strip, refused)


def open_ramp_precedence(mouth_list: list, extra_groups: _t.Sequence, tn, stats) -> list:
    """THE PACK'S OPEN RAMP IS THE BORE'S MOUTH (owner #1028 Q31: "objects
    around a tunnel take priority for defining the size, shape, depth and
    location of tunnel trenches"; 05n-3 per mouth): an OSM mouth standing in
    an admitted OPEN group's footprint ⊕ ``bore_end_tolerance_m`` is that
    object's and builds no OSM ramp; the rest stand."""
    opens = [g.corridor for g in extra_groups if _is_open(g)]
    if not opens:
        return mouth_list
    kept = []
    for m in mouth_list:
        cid = mouth_covered_by(m.xy, opens, tn.object.bore_end_tolerance_m)
        if cid is None:
            kept.append(m)
            continue
        stats.mouths_replaced_by_object += 1
        stats.bore_precedence.append(f"mouth of bore {'+'.join(str(i) for i in m.ways)}: "
                                     f"inside the open pack ramp {cid} — the object's "
                                     f"(#1028 Q31)")
    return kept
