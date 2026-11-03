"""A PACK FLOOR OF A FLAT-BUILT GROUP'S BLOCK FOLLOWS THE BLOCK (owner O-F5,
2026-11-03T15:01Z, #1717; spec ``docs/specs/flat-airside-terminal-20261103.md``
§3 row 17).

A sunken road's floor (Law B, ``constraints/structures``) is the plate's own
``y`` at its object's DEFAULT draw: ``base + y`` with ``base`` the terrain at
the placement plus its ``OBJECT_AGL`` (or the ``OBJECT_MSL`` elevation).
The object stage does not draw a flat-built group's objects there: it seats
the group at its block's level, so the plate stands at ``D - t + y`` -- the
block's datum column ``D``, less the group's stand-side foot plane ``t``
(``planar/flat_group``).  A pin at the default draw is a fixed anchor the
block's own interval cannot move (MEASURED LFPG T2: a 2A-2C sunken road
pinned at 106.9 m closed the group's interval).  :func:`follower` answers,
for a tunnel whose objects stand in a flat-built group's block, the
``(datum column, offset)`` pair that holds each floor vertex at
``z_v - z_D = z - base - t`` instead.
"""
from __future__ import annotations

from ..model.constraints import Linear, Row, Source

__all__ = ["follower", "follow_rows"]


def _base(o, airport) -> "float | None":
    if str(getattr(o, "kind", "OBJECT")) == "OBJECT_MSL":
        return float(o.y_offset_m)
    try:
        z = float(airport.dem.z(*o.xy))
    except Exception:  # noqa: BLE001 -- off the raster
        return None
    return z + float(o.y_offset_m) if z == z else None


def follower(planar, law, airport, tn) -> "tuple[int, float] | None":
    """``(datum column, base + t)`` for tunnel ``tn`` when its first object
    stands on a held block of a flat-built group, else ``None``."""
    from shapely.geometry import Point, Polygon

    from ..model.planar import plane_origin_ref, platform_ref_of
    from ..model.platform import datum_vertices
    held = getattr(planar.registries, "held", None) or {}
    if not tn.objects or not any(r.get("flat_group") for r in held.values()):
        return None
    objs = {o.id: o for o in (getattr(airport, "dsf_objects", ()) or ())}
    o = objs.get(tn.objects[0])
    if o is None:
        return None
    # the FLOOR's own place (a pack's anchor may stand far from its
    # geometry, the shared-datum authoring): the footprint, else the axis
    geo = tn.footprint if len(tn.footprint) >= 3 else tn.axis
    if not geo:
        return None
    xs = [float(p[0]) for p in geo]
    ys = [float(p[1]) for p in geo]
    pt = Point(sum(xs) / len(xs), sum(ys) / len(ys))
    blk = None
    for f in planar.faces.values():
        if f.role != "building":
            continue
        ref = plane_origin_ref(platform_ref_of(str(f.ref)))
        rec = (held.get(ref) or {}).get("flat_group")
        if not rec:
            continue
        ring = [planar.vertices[v].xy for v in planar.ring_vertices(f.ring)]
        if Polygon(ring).buffer(0.0).covers(pt):
            blk = (ref, float(rec.get("y_plane") or 0.0))
            break
    if blk is None:
        return None
    dv = datum_vertices(planar, law, fills=True).get(blk[0])
    base = _base(o, airport)
    if dv is None or base is None:
        return None
    return int(dv), base + blk[1]


def follow_rows(v: int, z: float, fol: "tuple[int, float]", src: Source) -> list[Row]:
    """The two-sided row ``z_v - z_D = z - (base + t)``."""
    dv, off = fol
    d = float(z) - off
    return [Linear(((int(v), 1.0), (dv, -1.0)), None, d, src),
            Linear(((int(v), -1.0), (dv, 1.0)), None, -d, src)]
