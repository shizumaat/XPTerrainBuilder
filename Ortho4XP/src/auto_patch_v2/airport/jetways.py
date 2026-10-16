"""THE JETWAYS THE SCENERY DECLARES (owner RULINGS 2026-10-16b (1): a
terminal building served by jetways has its pad expanded to include them;
"the jetways the scenery declares — apt.dat or the pack").

Two sources, in this order, never an airport-specific number:

* the airport's OWN apt.dat 1500 rows (X-Plane 12 jetways: root lat/lon,
  tunnel heading, tunnel length): a rectangle from the root along the
  tunnel, ``[building_pad] jetway_half_width_m`` either side, the tunnel's
  length plus ``jetway_cab_m``;
* where the apt.dat declares none, the PACK's own jetway placements — a
  resource whose path names ``[building_pad] jetway_token`` — at their own
  plan footprint (an ``.agp``'s TILE / CROP_POLY, ``riders.
  agp_footprint_xy``; an ``.obj``'s plan extent, the hull of every
  authored vertex).

Returns data; the pad derivation (``classify/evidence._pads``) attaches
each jetway to the pad it serves.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

__all__ = ["DeclaredJetway", "declared_jetways", "JETWAYS"]

XY = tuple[float, float]

#: what the last :func:`declared_jetways` read (the report)
JETWAYS: dict[str, _t.Any] = {}


@_dc.dataclass(frozen=True)
class DeclaredJetway:
    """One declared jetway: its ROOT (where it meets the terminal) and its
    plan footprint (an unclosed ring in the airport frame)."""

    source: str                    # "apt.dat" | "pack"
    root: XY
    ring: tuple[XY, ...]


def _apt_rows(path: str, icao: str) -> list[tuple[float, float, float, float]]:
    """``(lat, lon, tunnel heading deg, tunnel length m)`` per 1500 row of
    ``icao``'s block in the apt.dat at ``path``."""
    out: list[tuple[float, float, float, float]] = []
    inblk = False
    try:
        with open(path, "r", encoding="latin-1", errors="replace") as fh:
            for ln in fh:
                t = ln.split()
                if not t:
                    continue
                if t[0] in ("1", "16", "17"):
                    inblk = len(t) > 4 and t[4] == icao
                elif inblk and t[0] == "1500" and len(t) >= 8:
                    try:
                        out.append((float(t[1]), float(t[2]), float(t[6]), float(t[7])))
                    except ValueError:
                        continue
    except OSError:
        return []
    return out


def _rect(root: XY, heading_deg: float, length: float, half: float) -> tuple[XY, ...]:
    th = math.radians(heading_deg)
    ux, uy = math.sin(th), math.cos(th)          # heading clockwise from north
    px, py = -uy, ux
    x0, y0 = root
    x1, y1 = x0 + ux * length, y0 + uy * length
    return ((x0 + px * half, y0 + py * half), (x1 + px * half, y1 + py * half),
            (x1 - px * half, y1 - py * half), (x0 - px * half, y0 - py * half))


def _obj_extent(cache, o) -> tuple[XY, ...] | None:
    """An ``.obj`` jetway's PLAN EXTENT at its placement: the convex hull of
    EVERY authored vertex (the tunnel and cab are animated geometry, so the
    solid static footprint is the rotunda alone — measured 9 m2 per OTHH
    jetway)."""
    from shapely.geometry import MultiPoint
    from . import obj8 as _obj8
    geom = cache.geometry(o.resolved_path)
    if geom is None or geom.vertices.shape[0] < 3:
        return None
    a = _obj8.placement_affine(o.xy, o.heading_deg)
    pts = [(a[0] * x + a[1] * z + a[4], a[2] * x + a[3] * z + a[5])
           for x, z in geom.vertices[:, [0, 2]].tolist()]
    hull = MultiPoint(pts).convex_hull
    return tuple(hull.exterior.coords)[:-1] if hull.geom_type == "Polygon" else None


def declared_jetways(airport, law, cache=None) -> list[DeclaredJetway]:
    """Every jetway the scenery declares (module docstring)."""
    bp = law.tables.structures.building_pad
    JETWAYS.clear()
    JETWAYS.update({"source": None, "found": 0, "no_footprint": 0})
    if bp.jetway_half_width_m is None or bp.jetway_token is None:
        return []
    pack = getattr(airport, "pack", None)
    out: list[DeclaredJetway] = []
    rows = _apt_rows(getattr(pack, "apt_dat_path", "") or "", airport.icao)
    if rows:
        enter = airport.frame.entry()
        for lat, lon, hdg, length in rows:
            root = enter(lon, lat)
            out.append(DeclaredJetway("apt.dat", root, _rect(
                root, hdg, float(length) + float(bp.jetway_cab_m or 0.0),
                float(bp.jetway_half_width_m))))
    else:
        from .riders import agp_footprint_xy
        tok = str(bp.jetway_token).lower()
        JETWAYS["no_footprint"] = 0
        for o in airport.dsf_objects:
            if tok not in str(o.path).lower() or not o.resolved_path:
                continue
            ring = None
            if o.resolved_path.lower().endswith(".agp"):
                ring = agp_footprint_xy(o.resolved_path, o.xy, o.heading_deg)
            elif cache is not None:
                ring = _obj_extent(cache, o)
            if ring and len(ring) >= 3:
                out.append(DeclaredJetway("pack", tuple(o.xy), tuple(ring)))
            else:
                JETWAYS["no_footprint"] += 1
    JETWAYS.update({"source": out[0].source if out else None, "found": len(out)})
    return out
