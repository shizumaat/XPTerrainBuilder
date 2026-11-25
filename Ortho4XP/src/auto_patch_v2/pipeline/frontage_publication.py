"""THE ``terminal_frontages`` SIDECAR KEY (RULINGS 2026-11-25g, 25h; spec
``docs/specs/terminal-frontage-split-level-20261125.md`` §2 C27, step 1).

One record per terminal-sized pack unit (``airport/unit_storey.unit_levels``
read against the map's airside and groundside pavement and its storey
shells): its airside floor, groundside floor and every groundside plane
(``levels``), the rung, the ground medians, the verdict, the landside face
in lat/lon with its length, the frontage band's vertex count (groundside
value-face vertices within ``[design] pad_frontage_m`` of the face, spec
§1.4) and the clues step 2 reads (owner 25h Q1/Q3).  Where a held pad lies
under the unit: its ref (``block``), its solved height (``block_z``, the
median of its vertices) and ``land_z`` = ``block_z`` + rise.

A REPORT key: nothing in the solve or the census reads it (step 1)."""
from __future__ import annotations

import statistics as _st
import typing as _t

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

__all__ = ["frontage_levels", "map_sides", "terminal_frontage_records"]


def map_sides(planar, law) -> tuple:
    """``(airside, groundside)``: the union of the map's airside non-building
    faces (as ``classify/storey_edge.storey_band`` reads them) and of its
    groundside value faces (``constraints/groundside.groundside_face_roles``)."""
    from ..constraints.groundside import groundside_face_roles
    from ..law.tables import role_side
    gs = set(groundside_face_roles(law))
    air, ground = [], []
    for f in planar.faces.values():
        if f.role == "building":
            continue
        side = role_side(law, f.role)
        if side != "airside" and f.role not in gs:
            continue
        g = Polygon([planar.vertices[v].xy for v in planar.ring_vertices(f.ring)],
                    [[planar.vertices[v].xy for v in planar.ring_vertices(h)]
                     for h in f.holes]).buffer(0.0)
        (air if side == "airside" else ground).append(g)
    return unary_union(air), unary_union(ground)


def frontage_levels(planar, law, airport) -> list:
    """``unit_storey.unit_levels`` over the map's sides (:func:`map_sides`)."""
    from ..airport.unit_storey import unit_levels
    if airport is None or getattr(airport, "partition", None) is None:
        return []
    air, ground = map_sides(planar, law)
    return unit_levels(airport, law, air, ground=ground,
                       shells=tuple(getattr(planar, "storey_shells", ()) or ()))


def _block(planar, plan, z) -> tuple:
    """The held pad under ``plan`` (a quarter of the smaller plan or more)
    and its solved height, else ``(None, None)``."""
    held = getattr(getattr(planar, "registries", None), "held", None) or {}
    best = (0.0, None, ())
    for f in planar.faces.values():
        if str(f.ref) not in held:
            continue
        vs = planar.ring_vertices(f.ring)
        P = Polygon([planar.vertices[v].xy for v in vs]).buffer(0.0)
        a = P.intersection(plan).area if P.intersects(plan) else 0.0
        if a >= 0.25 * min(P.area, plan.area) and a > best[0]:
            best = (a, str(f.ref), vs)
    if best[1] is None:
        return None, None
    zz = None if z is None else round(float(_st.median(float(z[v]) for v in best[2])), 3)
    return best[1], zz


def _band(planar, law, face) -> int:
    """The frontage band's vertex count (module docstring)."""
    from ..constraints.groundside import groundside_face_roles
    from ..law.tables import design as design_law
    if face.is_empty:
        return 0
    zone = face.buffer(float(design_law(law).pad_frontage_m))
    gs = set(groundside_face_roles(law))
    vs = {v for f in planar.faces.values() if f.role in gs
          for cyc in (f.ring, *f.holes) for v in planar.ring_vertices(cyc)}
    return sum(1 for v in vs if zone.contains(Point(planar.vertices[v].xy)))


def terminal_frontage_records(planar, law, airport, levels=None,
                              z: "_t.Sequence[float] | None" = None) -> list[dict]:
    """The ``terminal_frontages`` records (module docstring); ``levels``:
    :func:`frontage_levels`' answer, read here when ``None``."""
    levels = frontage_levels(planar, law, airport) if levels is None else levels
    if not levels:
        return []
    to_ll = airport.frame.transformers()[1]
    units = airport.partition.units

    def ll(pts) -> list:
        return [[round(float(a), 8), round(float(b), 8)]
                for a, b in (to_ll(x, y) for x, y in pts)]
    out = []
    for r in levels:
        block, block_z = _block(planar, r.plan, z)
        out.append({
            "unit": str(getattr(units[r.unit], "id", r.unit)),
            "plan_m2": round(float(r.plan.area), 1),
            "air_y": round(r.air_y, 2),
            "land_y": None if r.land_y is None else round(r.land_y, 2),
            "rise": round(r.rise, 2),
            "levels": [{"y": lv.y, "rise": round(lv.y - r.air_y, 2), "area_m2": lv.area_m2,
                        "parts": lv.parts, "dist_m": lv.dist_m} for lv in r.levels],
            "witness": r.witness, "g_air": r.ground[0], "g_land": r.ground[1],
            "verdict": r.verdict,
            "face_m": round(float(r.face.length), 1),
            "face_ll": [ll(g.coords) for g in getattr(r.face, "geoms", ())],
            "band_vertices": _band(planar, law, r.face),
            "block": block, "block_z": block_z,
            "land_z": None if block_z is None else round(block_z + r.rise, 3),
            "clues": dict(r.clues)})
    return out
