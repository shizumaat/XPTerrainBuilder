"""LARGE DRAPED GROUND TEXTURES A PACK LAYS OVER ITS AIRPORT (issue #1962).

Owner (2026-11-08, RULINGS 2026-11-09a (3)): "Identify them by the fact
they primarily cover non-pavement areas, and add it as an option the user
can choose to hide or not."  Some packs paint the whole airfield's ground
with a few huge draped polygons — a painted ground image, a tiled grass
sheet — that hide our imagery as completely as a photo does, yet are no
machine-named photo grid (``pack_drape_grid``).  This module is their
WITNESS; the hiding is the same omission as the photos'
(``dsf_write.write_pack(drapes=)``), offered as its own row of the pack's
adjustments, unchecked, never automatic (``drape_stage.GROUND``).

THE WITNESS — a ``POLYGON_DEF`` of the pack's tile DSF is a ground sheet
when ALL of these hold, read from the files and the placements, never
from a name:

1. it is the PACK'S OWN ``DRAPED_POLYGON`` file (a library polygon —
   the stock signs, markings and pavement — is never one);
2. it carries NO ``SURFACE`` (pavement, or grass and dirt with their
   bumps: the ground the aircraft rolls on, which the author drew on
   purpose) and is NOT ``WEATHER_TRANSPARENT`` (a see-through overlay);
3. it is NOT A TILE OF A MACHINE-NAMED PHOTO GRID
   (``pack_drape_grid.grid_indices``): those are the photo rule's, hidden
   or kept whole by it — a blended photo grid kept there is never offered
   again here (#1946);
4. it lies over one of the pack's airports (``pack_drapes.airport_boxes``);
5. COVERAGE: its polygons (holes taken out) cover at least
   :data:`MIN_AREA_M2`, and more than :data:`MIN_GROUND_SHARE` of that
   lies OFF PAVEMENT — off the airport's paved runways and pavement
   (apt.dat rows 100 and 110 with a paved or transparent surface) and the
   pack's own paved draped polygons (``SURFACE asphalt``/``concrete``).
   A painted apron, a concrete grunge layer or a marking lies on
   pavement and is never one.

MEASURED 2026-11-09 on the installed packs (issues #1962 #1946): SCEL's
two painted ground images (1,668 ha each, 90-94 % off pavement), its
904 ha grass sheet (70 % off: it lies under the pack's 273 ha of paved
art and runways) and 14 earth, verge and car-park patches pass (17 in
all); its painted cargo apron (34 % off) and furrowed concrete (0 %) do
not.  SAWH's and SAWO's grass sheets (405 ha, 283 ha, 92-95 % off) pass;
LGSR and LFKC offer nothing (their photos are grids; LFKC's grass
carries a SURFACE).
"""
from __future__ import annotations

import typing as _t

from .pack_art import MissingDef, _lines

__all__ = ["MIN_AREA_M2", "MIN_GROUND_SHARE", "ground_sheets"]

#: the least ground (square metres) a sheet covers: ten hectares
MIN_AREA_M2 = 100_000.0
#: the share of a sheet that must lie off pavement ("primarily")
MIN_GROUND_SHARE = 0.5
#: apt.dat surface code of a transparent (pack-drawn) pavement
_TRANSPARENT = 15


def _shape(windings, to_m):
    """One DSF polygon (outer winding, then holes) as a valid polygon in
    metres, or ``None``."""
    from shapely.geometry import Polygon
    rings = [[to_m(x, y) for x, y, _r in w] for w in windings if len(w) >= 3]
    if not rings:
        return None
    g = Polygon(rings[0], rings[1:]).buffer(0)
    return g if not g.is_empty else None


def _apt_pavement(apt_path: str, to_m) -> list:
    """The airport's paved runways and pavement (rows 100 and 110 with a
    paved or transparent surface) in metres."""
    from O4_Airport_Rank import is_paved
    from shapely.geometry import Polygon

    from . import apt_dat as _ad
    from .pack_trees_clear import _rect
    out: list = []
    for icao in _ad.airports_in(apt_path) if apt_path else ():
        try:
            apt = _ad.parse_airport_block(_ad.read_airport_block(apt_path, icao))
        except (ValueError, IndexError, TypeError):
            continue
        for rw in apt.runways:
            if is_paved(rw.surface) or rw.surface == _TRANSPARENT:
                r = _rect(to_m(rw.ends[0][2], rw.ends[0][1]),
                          to_m(rw.ends[1][2], rw.ends[1][1]), rw.width_m / 2, 0.0)
                out += [Polygon(r)] if r else []
        for pv in apt.pavements:
            if ((is_paved(pv.surface) or pv.surface == _TRANSPARENT)
                    and pv.rings and len(pv.rings[0]) >= 3):
                out.append(Polygon([to_m(*p) for p in pv.rings[0]],
                                   [[to_m(*p) for p in r] for r in pv.rings[1:]
                                    if len(r) >= 3]).buffer(0))
    return out


def ground_sheets(pack_root: str, source: str | _t.Sequence[str],
                  apt_paths: _t.Sequence[str],
                  areas: _t.Sequence[tuple]) -> tuple[MissingDef, ...]:
    """THE WITNESS over one pristine DSF dump (a path or its rows): every
    polygon definition that is a large draped ground texture over one of
    ``areas`` (the airports of ``apt_paths``), as the ``MissingDef`` rows
    the omission takes (``uses``: its polygons)."""
    from shapely.geometry import box
    from shapely.ops import unary_union

    from . import pack_drapes as _pd
    from .obj8 import resolve_resource
    from .pack_drape_grid import grid_indices
    from .pack_trees_clear import _frame, _polygon_blocks
    if not areas:
        return ()
    lines = list(_lines(source))
    photos = _pd.photo_layers(pack_root, lines, areas)        # (3)
    grid = grid_indices(photos.layers)
    to_m = _frame((areas[0][1] + areas[0][3]) / 2)[0]
    airport = unary_union([box(*to_m(a[0], a[1]), *to_m(a[2], a[3]))
                           for a in areas])
    heads: dict[int, dict] = {}
    for i, path in enumerate(photos.defs):
        if i in photos.uses and path.lower().endswith(".pol") and i not in grid:
            local = resolve_resource(path.replace("\\", "/"), pack_root, {})
            heads[i] = _pd.pol_header(local) if local else {}   # (1)
    shapes: dict[int, list] = {}
    for _s, _e, idx, _p, _tail, windings in _polygon_blocks(lines):
        g = _shape(windings, to_m) if idx in heads else None
        if g is not None:
            shapes.setdefault(idx, []).append(g)
    paved = unary_union([g for a in apt_paths for g in _apt_pavement(a, to_m)]
                        + [g for i, h in heads.items() if _pd.paved_header(h)
                           for g in shapes.get(i, ())])
    out: list[MissingDef] = []
    for i, h in sorted(heads.items()):
        if (i not in shapes or "DRAPED_POLYGON" not in h or "SURFACE" in h
                or "WEATHER_TRANSPARENT" in h):
            continue                                            # (1), (2)
        sheet = unary_union(shapes[i])
        if not sheet.intersects(airport) or sheet.area < MIN_AREA_M2:
            continue                                            # (4), (5)
        off = sheet.area - sheet.intersection(paved).area
        if off > MIN_GROUND_SHARE * sheet.area:
            out.append(MissingDef("polygon", i, photos.defs[i], len(shapes[i])))
    return tuple(out)

