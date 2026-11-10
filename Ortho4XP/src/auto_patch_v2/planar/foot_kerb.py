"""THE LOT AT A WALL'S FOOT STEPS DOWN FROM ITS PAD (#1950; owner RULINGS
2026-11-10a (2)): "a groundside lot at a retaining wall's foot may step down
from a building pad at their shared edge (the pad edge is a wall/kerb there,
not a graded join), so the lot lies flat at the foot".

The lot is the one ``airport/foot_lot.lots_at_foot`` puts at a wall's foot
(a lot page over the LOWER band of a wall whose low side the pack's sheets
name, #1952 R5).  Where such a lot shares an edge with a pad whose level
stands more than ``[cockpit] visual_m`` over that foot, the step is DECLARED
here, at the lot's derivation site, the fill riser's way
(``planar/fill_riser``):

* the KERB: the strip of the lot within the riser width ``max(identity
  spacing, 2 x grid)`` of the pad (``fill_riser.riser_width``), cut out of
  the lot and minted ``<pad>#kerb#strip`` with the pad's role -- a bank face
  every pad reader skips (``model.planar.is_bank_ref``) whose ref is no
  platform's, so no 1:3 bank row is minted on it
  (``constraints/platform.collar_faces``);
* its WALL: ``upper`` the pad's edge along it, ``height_m`` the pad's
  predicted level (its held datum, else its highest DEM along the edge) over
  the foot, recorded on the pad's held record (``Registries.held[pad]
  ["kerbs"]``) and read into one ``road_terrace['wall']`` record per kerb by
  ``airport/riser_wall`` -- so the pair rows across it are released, the
  bending is cut, the lot below is bounded at the kerb's height and the
  census is told the step.

Without the kerb the lot's ring carried the pad's vertices: its foot Bands
lost to the pad's plane rows and to the pavement ceiling from those vertices
(MEASURED KMCI ``dsf:objpav405``, lane l1952c: 302.1-304.9 m against a
299.82 m foot).  Geometry only; no airport is named."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.ops import unary_union

from ..geom.parts import nonempty_polygon_parts as _parts
from ..geom.valid_area import valid_area
from ..model.planar import is_bank_ref, kerb_ref
from .fill_riser import _lines, riser_width

__all__ = ["foot_kerbs"]


def _foot_walls(airport) -> list:
    """The walls a lot can stand at the foot of (``airport/foot_lot``)."""
    from ..airport.foot_lot import sheet_walls
    from ..classify.rules import load_rules
    return sheet_walls(airport, load_rules().service)


def foot_kerbs(base_regions: list, pad_regions: list, airport, law, grid: float,
               reg, counts: dict | None = None) -> tuple[list, list]:
    """``(base_regions, pad_regions)`` with every foot lot's kerb along a
    pad it meets cut out of the lot and minted beside the pads (module
    docstring)."""
    from ..airport.foot_lot import lots_at_foot
    from .landing import LOT_ROLES
    lots = {i: r.polygon for i, r in enumerate(base_regions)
            if r.role in LOT_ROLES and r.polygon is not None and not r.polygon.is_empty}
    foot: dict[int, float] = {}
    for w in (_foot_walls(airport) if lots else ()):
        for i, z in lots_at_foot(w, lots).items():
            foot[i] = min(z, foot.get(i, z))
    pads = [r for r in pad_regions if r.polygon is not None and not r.polygon.is_empty
            and not is_bank_ref(r.ref)]
    if not foot or not pads:
        return base_regions, pad_regions
    w_m = riser_width(law, grid)
    visual = float(law.tables.emit.cockpit.visual_m)
    dem = getattr(airport, "dem", None)
    cut: dict[int, _t.Any] = {}
    made: list = []
    kerbs: dict[str, list] = {}
    for i, z_foot in sorted(foot.items()):
        lot = base_regions[i].polygon
        for pad in pads:
            held = reg.held.get(str(pad.ref))
            if held is None:
                continue        # a held block's level only (its datum)
            edge = unary_union(_lines(lot.boundary.intersection(
                pad.polygon.buffer(0.5 * grid, join_style=2))))
            if edge.is_empty or edge.length < w_m:
                continue
            level = _level(held, edge, dem)
            if level is None or level - z_foot <= visual:
                continue
            K = valid_area(lot.intersection(pad.polygon.buffer(w_m, join_style=2))
                           .difference(pad.polygon))
            pieces = [q for q in _parts(K) if q.area >= max(grid * grid, 1.0)]
            if not pieces:
                continue
            lot = valid_area(lot.difference(unary_union(pieces)))
            made.extend(_dc.replace(pad, ref=kerb_ref(str(pad.ref)), polygon=q)
                        for q in pieces)
            kerbs.setdefault(str(pad.ref), []).extend(
                {"ring": [tuple(c) for c in q.exterior.coords],
                 "upper": [[tuple(c) for c in ln.coords]
                           for ln in _lines(edge.intersection(q.buffer(0.5 * grid)))],
                 "height_m": round(level - z_foot, 3)} for q in pieces)
        if lot is not base_regions[i].polygon:
            cut[i] = lot
    for ref, ks in kerbs.items():       # set, never appended: the front is memoised
        reg.held[ref] = {**reg.held[ref], "kerbs": ks}
    if counts is not None and made:
        counts["foot_kerbs"] = len(made)
        counts["foot_kerb_m2"] = round(sum(q.polygon.area for q in made), 1)
    out_base: list = []
    for i, r in enumerate(base_regions):
        if i not in cut:
            out_base.append(r)
            continue
        # a lot the kerb splits stays one ref, one region per part
        out_base.extend(_dc.replace(r, polygon=q) for q in _parts(cut[i])
                        if q.area >= max(grid * grid, 1.0))
    return out_base, list(pad_regions) + made


def _level(held: _t.Mapping, edge, dem) -> float | None:
    """The pad's predicted level: its held datum, else the highest DEM
    sample along the shared ``edge``."""
    if held.get("datum_pred") is not None:
        return float(held["datum_pred"])
    if dem is None:
        return None
    zs = []
    for ln in _lines(edge):
        n = max(1, int(ln.length // 2.0))
        for k in range(n + 1):
            p = ln.interpolate(k * ln.length / n)
            try:
                zs.append(float(dem.z(p.x, p.y)))
            except Exception:  # noqa: BLE001 — off the raster
                continue
    zs = [z for z in zs if z == z]
    return max(zs) if zs else None
