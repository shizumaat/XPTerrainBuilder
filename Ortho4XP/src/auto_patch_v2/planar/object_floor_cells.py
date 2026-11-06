"""THE OBJECT FLOOR AS CELLS (#1903, owner 2026-11-06T00:07Z; reader
``airport/object_floor``): each trench object's floor footprint enters the
map as ONE cut face (role ``tunnel_trench``, ref ``object_floor:<id>``), its
ring densified every ``tunnel.object.wall_sample_m`` so the ring carries the
floor's own profile, and a VOID band (role ``retaining_wall``, ref
``object_floor_wall:<id>``, never a surface) half a
``wall_face_max_thickness_m`` wide around it: the floor's ring and the rim
are two rings, and the mesh makes the wall between them where the pack's
own walls stand.

The footprint is SENIOR to every other structure cell over it — the
object's floor owns the ground inside its footprint, so a mapped bore's
ramp or another reader's trench is trimmed back to the footprint's rim
(the single derivation site of "who owns the ground here").  It cuts the
pavement like every structure (the knife), never the runway family.
"""
from __future__ import annotations

import typing as _t

import shapely
from shapely.ops import unary_union

from ..airport.object_floor import FLOOR_REF, FLOOR_WALL_REF

__all__ = ["add_object_floor_cells"]

_RUNWAY_FAMILY = ("runway", "runway_crossing")


def _parts(geom) -> list:
    if geom is None or geom.is_empty:
        return []
    return [g for g in shapely.get_parts(geom)
            if g.geom_type == "Polygon" and g.area > 0.25]


def add_object_floor_cells(floors: _t.Sequence, law, new_cells: list, footprints: list,
                           hull_knives: list, keepouts: list, cells, polys,
                           notes: list[str]) -> int:
    """Append every object floor's cut face and void band to ``new_cells``
    (``(role, ref, polygon, owner id)``), its outer outline to the knives
    and keep-outs, and trim every structure cell already there to it.
    Returns how many floors entered the map."""
    if not floors:
        return 0
    ob = law.tables.structures.tunnel.object
    band_m = 0.5 * float(ob.wall_face_max_thickness_m)
    runway = unary_union([p for p, c in zip(polys, cells, strict=False)
                          if c.role in _RUNWAY_FAMILY])
    n = 0
    for fl in floors:
        foot = fl.footprint
        if not runway.is_empty:
            foot = foot.difference(runway.buffer(band_m, join_style="mitre"))
        parts = _parts(foot)
        if not parts:
            notes.append(f"{fl.id}: the floor stands wholly on the runway family — not cut")
            continue
        foot = unary_union(parts)
        outer = foot.buffer(band_m, join_style="mitre")
        # the floor owns the ground inside its outline: trim what is there
        kept = []
        for role, ref, part, tid in new_cells:
            if part.intersects(outer):
                for q in _parts(part.difference(outer)):
                    kept.append((role, ref, q, tid))
            else:
                kept.append((role, ref, part, tid))
        new_cells[:] = kept
        for k, q in enumerate(parts):
            dense = shapely.segmentize(q, float(ob.wall_sample_m))
            new_cells.append(("tunnel_trench", fl.id + (f"#{k}" if k else ""), dense, fl.id))
        wall_ref = FLOOR_WALL_REF + fl.id[len(FLOOR_REF):]
        for k, q in enumerate(_parts(outer.difference(foot))):
            new_cells.append(("retaining_wall", wall_ref + (f"#{k}" if k else ""), q, fl.id))
        for q in _parts(outer):
            footprints.append(q)
            hull_knives.append(q)
            keepouts.append(q)
        notes.append(f"{fl.id}: the floor's footprint {foot.area:.0f} m2 is the cut "
                     f"(floor {fl.floor_z:.2f}), its rim {band_m:.1f} m outside it")
        n += 1
    return n
