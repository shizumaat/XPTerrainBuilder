"""A DRAPED-PAVEMENT OVERLAY IS PAVEMENT EVIDENCE (owner ruling 2026-11-04,
"1598. Yes"; #1598).

An installed overlay pack can draw an airport's pavement where the
airport's own pack does not: at KATL ``AEP Overlays`` drapes
``Asphalt_Top_Plain.pol`` over the hilltop lot a Nimbus building stands on
(33.628679, -84.429899), and the Nimbus pack's nearest pavement page is
21 m off, so the lot was never graded.  The ruling: such a pack is read as
PAVEMENT EVIDENCE only -- its objects are never seated or written.

THE WITNESS IS THE PACK'S OWN CONTENT, never its name.  A pack is read when

* it is a tile candidate beside the airport's pack (``pack_local.
  tile_candidates``: enabled, not the serving pack, no apt.dat, a DSF for
  the tile) whose DSF defines a draped pavement ``.pol``
  (:func:`dump_candidates`, the pavement gate on its definitions); and
* at least one of its admitted pavement pages MEETS the airport's own
  pavement (apt.dat runways and row 110, the pack's pages and §42 bodies).

What it adds (owner 2026-11-04, "Accept recommendations"): only what the
airport's own pavement does not cover, and only INSIDE THE AIRPORT -- each
page clipped to the boundary (row 130, else the runway and pavement
outline: ``load.airport_region``), MINUS the own pavement and the pages
drawn over it (dump order is draw order), opened by ``[identity]
overlay_pavement_sliver_m`` (an edge mismatch between the two packs is no
pavement); a piece is kept when it TOUCHES the own pavement (within
``[identity] weld_spacing_m``) or is LINKED to it by a mapped road whose
chain touches both (:func:`road_links`; owner 2026-11-04), or touches a
piece so connected (DEM prep's stamp reads no roads: touch only).  Inside, the
mapped roads cut it (``classify/evidence``: the roads become road ribbons,
the pieces between them separate lots -- overlay pages only).  Each piece is a ``dsf:overlay<k>`` source
(``model.airport.OVERLAY_PREFIX``) with its page's surface, one source per
page; classification scores it as it scores a pack page, but keeps it only
as a LOT or a ROAD and never flips it to apron by edge contact
(``classify/airside_edge.keep_overlay_groundside`` / ``airside_edge_flip``).
Every pre-existing polygon keeps its id and its shape.
"""
from __future__ import annotations

import os
import typing as _t

from O4_DSF_Header import dsf_polygon_defs

from ..model.airport import OVERLAY_PREFIX
from . import dsf as _dsf
from .pack_local import tile_candidates

__all__ = ["OVERLAY_PREFIX", "dump_candidates", "held_pieces", "load_pavements",
           "road_links"]



def _defines_pavement(path: str, gate) -> bool:
    """Does the DSF define a ``.pol`` the pavement gate admits?  A DSF whose
    definitions cannot be read is a candidate (the dump decides)."""
    defs = dsf_polygon_defs(path)
    if defs is None:
        return True
    return any(d.lower().endswith(".pol") and gate(d)[0] == _dsf.SOURCE for d in defs)


def _gate(root: str, index):
    from . import obj8 as _obj8
    return _dsf.pavement_gate(lambda p: _obj8.resolve_resource(p, root, index))


def dump_candidates(main_root: str, lat: int, lon: int, index=None) -> list[str]:
    """The tile candidates whose DSF defines a draped pavement ``.pol``:
    the packs the pre-build refresh dumps (``engine_v2.fresh_pack_dump``)
    and the load reads.  ``index`` is the library index (``None``: a
    ``.pol`` the name alone does not settle reads as its name says)."""
    return [r for r in tile_candidates(main_root, lat, lon)
            if _defines_pavement(_dsf.dsf_path_in_pack(r, lat, lon), _gate(r, index))]


def _read_pack_pages(root: str, lat: int, lon: int, mod_cache_root: str, read
                    ) -> tuple[str, list] | None:
    """``(dump path, read(dump path))`` for a candidate pack, or ``None``
    when its PRISTINE tile dump is not in the mod cache (made before the
    build, never here)."""
    from .dsf_write import pristine_dsf_path
    dsf_path = pristine_dsf_path(_dsf.dsf_path_in_pack(root, lat, lon))
    dump = _dsf.find_text_dump(mod_cache_root, os.path.basename(os.path.normpath(root)),
                               lat, lon, dsf_path=dsf_path)
    if not dump:
        return None
    return dump, read(dump)


def road_links(osm_ways, own, region, law):
    """The mapped roads that LINK a piece to the airport (owner 2026-11-04:
    "the hilltop lot has a road running down the hill that should touch the
    airport pavement"): the carriageways (``road_ways.ribbon_half_width_m``)
    of the at-grade road-feed ways (``model.planar.OSM_RIBBON_FEEDS``)
    inside ``region``, merged into connected chains, keeping the chains
    that touch ``own``.  One shapely geometry, or ``None``."""
    from shapely.ops import unary_union

    from ..geom.parts import polygon_parts_with_area
    from ..model.planar import OSM_RIBBON_FEEDS
    from .road_ways import ribbon_half_width_m, road_ways
    if own is None or region is None:
        return None
    lanes = [ln.buffer(ribbon_half_width_m(w.tags, law), cap_style="flat")
             for w, ln in road_ways(osm_ways)
             if getattr(w, "kind", "") in OSM_RIBBON_FEEDS and ln.intersects(region)]
    if not lanes:
        return None
    touch = own.buffer(float(law.tables.emit.identity.weld_spacing_m))
    chains = [c for c in polygon_parts_with_area(unary_union(lanes).intersection(region))
              if c.intersects(touch)]
    return unary_union(chains) if chains else None


def _evidence(pages: _t.Sequence[tuple[_t.Any, _t.Any]], own, region, law,
              links=None) -> list[tuple[_t.Any, _t.Any]]:
    """The pieces one overlay pack adds (module doc): ``pages`` is its
    ``(shapely polygon, tag)`` pavement pages, ``own`` the airport's own
    pavement and runways, ``region`` its boundary (``load.airport_region``),
    ``links`` the road chains touching ``own`` (:func:`road_links`).
    Returns ``(piece, tag of its page)``; empty when no page meets ``own``."""
    from ..geom.parts import polygon_parts_with_area
    if not pages or own is None or own.is_empty or region is None or region.is_empty:
        return []
    ident = law.tables.emit.identity
    if not any(p.intersects(own) for p, _tag in pages):
        return []
    w = float(ident.overlay_pavement_sliver_m)
    touch = own.buffer(float(ident.weld_spacing_m))
    cand, taken = [], own
    # each page keeps what is its own: a page drawn later lies on top
    # (dump order is draw order), so the pages are taken last first
    for page, tag in reversed(pages):
        rest = page.intersection(region).difference(taken)
        taken = taken.union(page)
        if w > 0 and not rest.is_empty:
            rest = rest.buffer(-w, join_style="mitre").buffer(
                w, join_style="mitre").intersection(rest)
        cand.extend((piece, tag) for piece in polygon_parts_with_area(rest))
    # connected to the airport: touching its pavement, linked by a road, or
    # touching a piece already connected (an overlay lot beside an overlay
    # road beside the apron) -- to the fixpoint
    keep = [False] * len(cand)
    grow = True
    while grow:
        grow = False
        for i, (piece, _tag) in enumerate(cand):
            if keep[i]:
                continue
            if piece.intersects(touch) or (links is not None and piece.intersects(links)):
                keep[i] = grow = True
                touch = touch.union(piece.buffer(float(ident.weld_spacing_m)))
    return [c for c, k in zip(cand, keep, strict=True) if k]


def load_pavements(main_root: str, tile: tuple[int, int], mod_cache_root: str | None,
                   index, read_pages: _t.Callable[[str, str], list], own, region, law,
                   osm_ways=(), say: _t.Callable[[str], None] = lambda _m: None) -> list:
    """The overlay pieces as the load mints them: ``dsf:overlay<k>``
    ``Pavement`` records (module doc).  ``index`` is the library index;
    ``read_pages(dump, root)`` is the
    load's own page reader (``load._DsfPolygons``: the pavement gate and
    the admission extent); ``own`` the airport's pavement and runways so
    far and ``region`` its boundary, as shapely geometries; ``osm_ways``
    the mapped ways (:func:`road_links`).  A candidate
    with no made dump is named and skipped."""
    import dataclasses as _dc

    from shapely.geometry import Polygon
    if not (main_root and mod_cache_root):
        return []
    out: list = []
    links = road_links(osm_ways, own, region, law)
    for root in dump_candidates(main_root, *tile, index=index):
        name = os.path.basename(os.path.normpath(root))
        got = _read_pack_pages(root, *tile, mod_cache_root, lambda d, r=root: read_pages(d, r))
        if got is None:
            say(f"  [overlay-pavement] {name}: no text dump of its tile DSF in the "
                "mod cache -- not read")
            continue
        pages = []
        for pav in got[1]:
            p = Polygon(pav.outer, [h for h in pav.holes if len(h) >= 3])
            p = p if p.is_valid else p.buffer(0)
            if not p.is_empty:
                pages.append((p, pav))
        pieces = _evidence(pages, own, region, law, links)
        for piece, pav in pieces:
            out.append(_dc.replace(
                pav, id=f"{OVERLAY_PREFIX}{len(out)}",
                outer=tuple((float(x), float(y)) for x, y in piece.exterior.coords[:-1]),
                holes=tuple(tuple((float(x), float(y)) for x, y in r.coords[:-1])
                            for r in piece.interiors)))
        if pieces:
            say(f"  [overlay-pavement] {name}: {len(pieces)} piece(s), "
                f"{sum(p.area for p, _pv in pieces):,.0f} m2 of pavement the airport's "
                "own pack does not draw")
    return out



def held_pieces(main_root: str, tile_lat: int, tile_lon: int, to_xy, own_extent,
                mod_cache_root: str | None, xplane_root: str | None, own,
                region, law) -> list:
    """The overlay pieces as DEM prep's flat-site stamp holds them (RULINGS
    2026-10-27d: the pavement the build grades stays flat): shapely
    polygons, read through ``pack_pavement.pavement_pages`` (``own`` is
    the shapely union the stamp already holds, ``region`` the airport's
    boundary, ``load.airport_region``)."""
    from . import obj8 as _obj8
    from .pack_pavement import pavement_pages
    if not (main_root and mod_cache_root):
        return []
    index = (_obj8.read_library_index(_obj8.library_index_path(mod_cache_root, xplane_root))
             if xplane_root else None)
    out = []
    for root in dump_candidates(main_root, tile_lat, tile_lon, index):
        pages = pavement_pages(root, os.path.basename(os.path.normpath(root)),
                               tile_lat, tile_lon, to_xy, own_extent,
                               mod_cache_root, xplane_root)
        out.extend(p for p, _tag in _evidence([(p, None) for p in pages], own, region, law))
    return out
