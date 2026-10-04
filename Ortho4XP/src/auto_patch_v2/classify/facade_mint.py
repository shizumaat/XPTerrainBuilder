"""THE FACADE MINT — the graded STRIP under a facade wall's attached
vehicles / canopy, and an open-lot facade's LOT (spec §52; owner RULINGS
2026-10-04d (3) (a)-(c), master 2026-10-04; issue #334).

ONE derivation site for both, called by ``roles.classify`` beside
``ribbon_mint.mint_osm_ribbons`` — AFTER the pads, §27's airside-edge flip
and the pad set-back, BEFORE the ribbons:

* THE STRIP: per facade edge whose wall attaches something reaching at
  least ``[buildings] facade_strip_min_reach_m`` (trailers 13.2 m, an
  entrance canopy 8.1 m; stairs 2.9 m are not graded for), the edge swept
  outward by that reach, MINUS every cell standing (airside pavement and
  every pad win) and every OTHER pad's set-back.  Role
  ``groundside_pavement``, ref ``facstrip:<host pad>:<k>``.  The host is
  the pad the facade's footprint stands on (``planar/platform.
  DRAPED_FACADE_COVER``'s cover rule); a facade with no pad mints no strip.
  ROUND-2 STATE, PENDING THE MASTER'S RULING (spec §52 (6)): the strip
  takes the pad set-back from its HOST too, like every groundside cell,
  and is held at the pad's level across it (``constraints/facade_strip``).
  Row 8 ruled it welded by identity; MEASURED at SPJC, a strip sharing the
  rim of a pad stage 2 solves (``building16``) drags that pad 5 m through
  its own within-face caps.
* THE LOT: the facade's own ring minus every cell standing and every
  pad's set-back.  Role ``parking_lot``, ref ``faclot:<k>``; the existing
  lot law grades it, no level law of its own.

Neither is ever airside (minted after §27) and neither is a pavement
SOURCE: the airside region, its slice and every pad are what they were.
Both are LATE cells (``model.planar.is_late_ref``): they join the finished
map at ``planar/ribbons``' pass C and are absent from the stage-1 map."""
from __future__ import annotations

import math

import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..law import Law
from ..law.tables import snap_margin_m
from ..model.airport import Airport
from ..model.planar import FACADE_LOT_PREFIX, FACADE_STRIP_PREFIX
from .evidence import polygon_parts
from .rules import Rules

__all__ = ["mint_facade_cells", "strip_sweep", "HOST_COVER", "LOT_SOURCE",
           "STRIP_ROLE", "LOT_ROLE"]

#: the facade's footprint is a pad's when the pad covers this much of it
#: (``planar/platform.DRAPED_FACADE_COVER``, the same cover read from the
#: facade's side)
HOST_COVER = 0.5
#: ``airport/facade.LOT_SOURCE`` — spelled here because ``classify`` reads
#: ``model`` only; ``tests/auto_patch_v2/test_facade_mint.py`` holds the two equal
LOT_SOURCE = "dsf:lot:fac"
STRIP_ROLE = "groundside_pavement"
LOT_ROLE = "parking_lot"
#: the sweep starts this far INSIDE the wall, so the difference with the
#: host pad leaves the pad's own edge as the strip's inner boundary
_INSET_M = 1.0


def strip_sweep(a, b, reach_m: float, footprint: Polygon) -> Polygon | None:
    """Edge ``a -> b`` swept ``reach_m`` to the side AWAY from
    ``footprint`` (and ``_INSET_M`` into it)."""
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    if length <= 0.0 or reach_m <= 0.0:
        return None
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    nx, ny = uy, -ux
    mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
    if footprint.contains(shapely.Point(mx + nx * 0.25, my + ny * 0.25)):
        nx, ny = -nx, -ny
    return Polygon([(a[0] - nx * _INSET_M, a[1] - ny * _INSET_M),
                    (b[0] - nx * _INSET_M, b[1] - ny * _INSET_M),
                    (b[0] + nx * reach_m, b[1] + ny * reach_m),
                    (a[0] + nx * reach_m, a[1] + ny * reach_m)])


def _poly(ring, holes=()) -> Polygon | None:
    try:
        p = Polygon(ring, holes)
    except (ValueError, TypeError):
        return None
    if not p.is_valid:
        p = p.buffer(0.0)
    return p if isinstance(p, Polygon) and not p.is_empty else None


def mint_facade_cells(airport: Airport, cells: list, law: Law, rules: Rules,
                      add) -> dict[str, float]:
    """Mint the §52 strips and lots onto ``cells`` through ``add`` (the
    classifier's own cell constructor); returns the counts."""
    stats = {"facade_strips": 0, "facade_strip_m2": 0.0, "facade_lots": 0,
             "facade_lot_m2": 0.0, "facade_strip_no_host": 0,
             "facade_edges_undecided": 0}
    bs = [b for b in getattr(airport, "buildings", ()) or ()
          if getattr(b, "facade", None) is not None]
    if not bs:
        return stats
    min_reach = float(rules.buildings.facade_strip_min_reach_m)
    grid = rules.cells.snap_grid_m
    knife_m = float(law.tables.structures.building_pad.groundside_cutback_m) \
        + snap_margin_m(law)
    polys = [(c, Polygon(c.ring, c.holes)) for c in cells]
    pads = [(c, p) for c, p in polys if c.role == "building"]
    standing = unary_union([p for _c, p in polys]) if polys else Polygon()
    knives = {c.ref: p.buffer(knife_m, join_style="mitre", mitre_limit=2.0)
              for c, p in pads} if knife_m > 0.0 else {}

    def emit(geom, role: str, ref: str, kind: str, evid: dict) -> float:
        geom = shapely.set_precision(geom, grid)
        k, area = 0, 0.0
        for part in polygon_parts(geom):
            if part.area < rules.cells.min_area_m2:
                continue
            add(role, ref if k == 0 else f"{ref}#{k}", part, kind, None, None, evid)
            k += 1
            area += part.area
        return area

    n = 0
    for b in bs:
        fr = b.facade
        stats["facade_edges_undecided"] += int(fr.undecided)
        if b.source == LOT_SOURCE or min_reach <= 0.0:
            continue
        edges = [e for e in fr.edges if e.reach_m >= min_reach]
        fp = _poly(b.outer, b.holes) if edges else None
        if fp is None:
            continue
        host = max(((p.intersection(fp).area, c, p) for c, p in pads
                    if p.intersects(fp)), key=lambda t: t[0], default=None)
        if host is None or host[0] < HOST_COVER * fp.area:
            stats["facade_strip_no_host"] += len(edges)
            continue
        _a, hc, hp = host
        href = hc.ref.split("#")[0]
        others = list(knives.values())      # every pad's set-back, the host's too
        for e in edges:
            sweep = strip_sweep(e.a, e.b, e.reach_m, fp)
            if sweep is None:
                continue
            geom = sweep.difference(unary_union([standing, fp, *others]))
            # the parts on the host's edge only: a piece the cut left
            # across another cell is not this wall's ground
            parts = [q for q in polygon_parts(geom) if q.distance(hp) <= knife_m + grid]
            if not parts:
                continue
            geom = shapely.snap(unary_union(parts), hp, 2.0 * grid)
            area = emit(geom, STRIP_ROLE, f"{FACADE_STRIP_PREFIX}:{href}:{n}",
                        "facade_strip",
                        {"facade": b.id, "wall": e.wall, "reach_m": float(e.reach_m),
                         "attached": e.obj, "host": href})
            if area > 0.0:
                n += 1
                stats["facade_strips"] += 1
                stats["facade_strip_m2"] += area
                standing = unary_union([standing, geom])
    k = 0
    for b in bs:
        if b.source != LOT_SOURCE:
            continue
        fp = _poly(b.outer, b.holes)
        if fp is None:
            continue
        geom = fp.difference(unary_union([standing, *knives.values()]))
        area = emit(geom, LOT_ROLE, f"{FACADE_LOT_PREFIX}:{k}", "parking_lot",
                    {"facade": b.id, "facade_def": b.facade.def_path})
        if area > 0.0:
            k += 1
            stats["facade_lots"] += 1
            stats["facade_lot_m2"] += area
            standing = unary_union([standing, geom])
    return stats
