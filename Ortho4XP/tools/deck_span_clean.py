"""LIBRARY of ``tools/deck_probe.py --span-clean`` (walled-multibridge-frames
spec W8, ``walled_span_clean``): NOTHING OF THE PAVEMENT INSIDE A WALLED
SPAN'S CUT, off a ``--solved-out`` pickle.

For every pack deck of ``PlanarMap.decks`` whose frame models walls on both
sides of the road under it (``planar/deck_bridge._walled_trench``; the K2
pair at the edge of the frame's floor), the span's cut is its floor strip
(between the walls' inner faces, inside the ring).  Every map vertex
strictly inside that strip that belongs to a pavement face (the rolled-on
airside roles, the apron, the zones, the at-grade deck plan), to a building
pad, or to a centreline / edge breakline is a row: the faces under a span
are the trench's only (floor, wall stand-off, bank).  Pure: reads the
pickle's map; writes nothing.
"""
from __future__ import annotations

__all__ = ["span_clean"]

#: the strip is read this far inside its edge (its rim vertices stand on it)
INSET_M = 0.05
#: breakline kinds that are pavement linework
LINE_KINDS = ("taxi_centerline", "runway_profile", "road_centerline")


def _bad_roles(law) -> set[str]:
    from auto_patch_v2.law.tables import rolled_on_roles
    return set(rolled_on_roles(law)) | {"building", "apron"}


def span_clean(pm, law) -> list[dict]:
    """One record per walled pack deck: ``{object, strip_m2, rows, roles,
    lines, worst_at}`` (module doc)."""
    from auto_patch_v2.planar.deck_bridge import _walled_trench, deck_polygon
    from shapely import prepared
    from shapely.geometry import Point
    bad = _bad_roles(law)
    gap = float(law.tables.structures.tunnel.wall_gap_m)
    v_role: dict[int, set[str]] = {}
    for f in pm.faces.values():
        if f.role in bad or str(f.ref).startswith("zone"):
            # the face's rings are EDGE cycles: their vertices are the map's
            for v in {u for ring in (f.ring, *f.holes) for u in pm.ring_vertices(ring)}:
                v_role.setdefault(int(v), set()).add(str(f.role))
    v_line: dict[int, str] = {}
    for b in (getattr(pm, "breaklines", None) or {}).values():
        if b.kind in LINE_KINDS:
            for v in b.vertices(pm):
                v_line[int(v)] = b.kind
    out: list[dict] = []
    for db in getattr(pm, "decks", ()) or ():
        got = _walled_trench(db, gap)
        if got is None:
            continue
        strip = got[0].intersection(deck_polygon(db)).buffer(-INSET_M)
        if strip.is_empty:
            continue
        pp = prepared.prep(strip)
        rows, roles, lines = [], set(), set()
        for v, vx in pm.vertices.items():
            if not pp.contains(Point(vx.xy)):
                continue
            r, ln = v_role.get(int(v)), v_line.get(int(v))
            if r or ln:
                rows.append(int(v))
                roles |= r or set()
                if ln:
                    lines.add(ln)
        out.append({"object": db.object_id, "strip_m2": round(strip.area, 1),
                    "rows": len(rows), "roles": sorted(roles), "lines": sorted(lines),
                    "vertices": rows[:12]})
    return out
