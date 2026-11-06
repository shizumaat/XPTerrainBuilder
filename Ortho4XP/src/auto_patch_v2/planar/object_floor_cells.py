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

import dataclasses as _dc
import typing as _t

import shapely
from shapely.ops import unary_union

from ..airport.object_floor import (FLOOR_REF, FLOOR_WALL_REF, floor_portals,
                                   read_object_floors)

__all__ = ["add_object_floor_cells", "floor_mouths", "not_floors", "object_floor_stage"]

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


def object_floor_stage(airport, objects, cache, law, corridors, tstats) -> tuple[list, list]:
    """``(floors, corridors)``: every trench object's floor read ONCE
    (``airport/object_floor``), the axis corridors they supersede dropped (a
    split shell's floor read as a corridor), their placements claimed out of
    the basin intake like a shell's, the refusals noted, and every pack
    portal on a floor pinned at that floor's own height (``tstats`` is
    updated in place).  ``planar.build.build`` and the ``--stage
    structures`` replay share it."""
    msl = {o.id: o.y_offset_m for o in airport.dsf_objects if o.kind == "OBJECT_MSL"}
    shells = frozenset(o for c in corridors if c.id.startswith("object-cut:") for o in c.objects)
    floors, notes = read_object_floors(objects, cache, law, msl, shells=shells)
    floor_ids = {i for f in floors for i in (f.object_id, *f.covers)}
    if floor_ids:
        corridors = [c for c in corridors if not (set(c.objects) & floor_ids)]
        tstats.shell_claimed = tuple(sorted(set(tstats.shell_claimed) | floor_ids))
    tstats.refused.extend(n for n in notes if not n.startswith("object floor"))
    tstats.portals = floor_portals(tstats.portals, floors)
    return floors, list(corridors)


def floor_mouths(tunnels: _t.Sequence, floors: _t.Sequence, law) -> tuple[list, list[str]]:
    """``(tunnels, notes)``: every mapped bore whose MOUTH stands within
    ``bore_end_tolerance_m`` of a trench object's floor seats its mouth at
    that floor's own height at the nearest footprint point ("mouths seat at
    that floor", owner 2026-11-06) — over the bore law, the survey's road
    and the mouth-at-pavement slide alike (EGLL 11 west mouth: the lidar
    road under the portal pinned 16.16 where 11b's floor stands 17.16, and
    the drawn 11 / 11a stood 1.02 m over the cut).  Every other tunnel as
    it was."""
    from shapely.geometry import Point
    from shapely.ops import nearest_points

    from ..airport.object_floor import floor_z_at
    if not floors:
        return list(tunnels), []
    tol = float(law.tables.structures.tunnel.object.bore_end_tolerance_m)
    out, notes = [], []
    for tn in tunnels:
        if getattr(tn, "source", "") != "osm" or not tn.axis:
            out.append(tn)
            continue
        m = Point(tn.axis[0])
        best = min(((f.footprint.distance(m), f) for f in floors), key=lambda t: t[0])
        if best[0] > tol:
            out.append(tn)
            continue
        f = best[1]
        q = nearest_points(f.footprint, m)[0]
        z = float(floor_z_at(f.faces, [q.x], [q.y], edge_m=0.5)[0])
        if z != z:
            out.append(tn)
            continue
        note = (f"{tn.id}: the mouth {best[0]:.1f} m from {f.id} seats at that floor "
                f"{z:.2f} (was {tn.mouth_z:.2f}; #1903 'mouths seat at that floor')")
        out.append(_dc.replace(tn, mouth_z=z, notes=(*tn.notes, note)))
        notes.append(note)
    return out, notes


def not_floors(records: _t.Sequence, floors: _t.Sequence) -> list:
    """``records`` (sunken roads, door wells — any reading with
    ``objects``) less those reading a trench object's floor or cover: the
    object's own floor is the cut there, read ONCE (KBNA
    ``Metropolitan-part2``: the sunken-road reading cut its plate's lowest
    y, 173.30, outside the floor's footprint, 0.38 m under the floor)."""
    ids = {pid for f in floors for pid, _r, _z in f.seats}
    return [r for r in records if not (set(getattr(r, "objects", ()) or ()) & ids)]
