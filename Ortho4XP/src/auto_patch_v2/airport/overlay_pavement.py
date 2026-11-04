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
  pavement (apt.dat row 110 and the pack's pages and §42 bodies).

What it adds is only what the airport's own pavement does not cover: each
page MINUS the own pavement and the pages drawn over it (dump order is draw
order), opened by ``[identity]
overlay_pavement_sliver_m`` (an edge mismatch between the two packs is no
pavement), each remaining piece kept when it meets the boundary (row 130) or
lies within ``overlay_pavement_reach_m`` of the own pavement.  Each piece
is a ``dsf:overlay<k>`` source polygon with its page's surface, one source
per page as the pack's own pages are; classification judges it exactly as it judges a pack
page (``classify/evidence._dsf_pavements``), roles by the shared scorer.
Every pre-existing polygon keeps its id and its shape.
"""
from __future__ import annotations

import os
import typing as _t

from O4_DSF_Header import dsf_polygon_defs

from . import dsf as _dsf
from .pack_local import tile_candidates

__all__ = ["OVERLAY_PREFIX", "dump_candidates", "held_pieces", "load_pavements"]

#: the id prefix of an overlay piece (``dsf:`` -- classify's page gates)
OVERLAY_PREFIX = "dsf:overlay"


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


def _evidence(pages: _t.Sequence[tuple[_t.Any, _t.Any]], own, boundary, law
             ) -> list[tuple[_t.Any, _t.Any]]:
    """The pieces one overlay pack adds (module doc): ``pages`` is its
    ``(shapely polygon, tag)`` pavement pages, ``own`` the airport's own
    pavement union, ``boundary`` its row-130 union or ``None``.  Returns
    ``(piece, tag of the page covering most of it)``; empty when no page
    meets ``own``."""
    from ..geom.parts import polygon_parts_with_area
    if not pages or own is None or own.is_empty:
        return []
    ident = law.tables.emit.identity
    if not any(p.intersects(own) for p, _tag in pages):
        return []
    w = float(ident.overlay_pavement_sliver_m)
    reach = own.buffer(float(ident.overlay_pavement_reach_m))
    out, taken = [], own
    # each page keeps what is its own: a page drawn later lies on top
    # (dump order is draw order), so the pages are taken last first
    for page, tag in reversed(pages):
        rest = page.difference(taken)
        taken = taken.union(page)
        if w > 0 and not rest.is_empty:
            rest = rest.buffer(-w, join_style="mitre").buffer(
                w, join_style="mitre").intersection(rest)
        for piece in polygon_parts_with_area(rest):
            if piece.intersects(reach) or (boundary is not None
                                           and piece.intersects(boundary)):
                out.append((piece, tag))
    return out


def _union(items):
    """The union of ``Pavement`` / ``Boundary`` records (outer + holes);
    ``None`` with none."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys = []
    for it in items:
        if len(it.outer) < 3:
            continue
        p = Polygon(it.outer, [h for h in it.holes if len(h) >= 3])
        polys.append(p if p.is_valid else p.buffer(0))
    return unary_union(polys) if polys else None


def load_pavements(main_root: str, tile: tuple[int, int], mod_cache_root: str | None,
                   index, read_pages: _t.Callable[[str, str], list], own: _t.Sequence,
                   boundaries: _t.Sequence, law,
                   say: _t.Callable[[str], None] = lambda _m: None) -> list:
    """The overlay pieces as the load mints them: ``dsf:overlay<k>``
    ``Pavement`` records (module doc).  ``index`` is the library index;
    ``read_pages(dump, root)`` is the
    load's own page reader (``load._DsfPolygons``: the pavement gate and
    the admission extent); ``own`` the airport's pavement records so far.
    A candidate with no made dump is named and skipped."""
    import dataclasses as _dc

    from shapely.geometry import Polygon
    if not (main_root and mod_cache_root):
        return []
    own_u, bnd = _union(own), _union(boundaries)
    out: list = []
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
        pieces = _evidence(pages, own_u, bnd, law)
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
                boundaries: _t.Sequence, law) -> list:
    """The overlay pieces as DEM prep's flat-site stamp holds them (RULINGS
    2026-10-27d: the pavement the build grades stays flat): shapely
    polygons, read through ``pack_pavement.pavement_pages`` (``own`` is
    the shapely union the stamp already holds)."""
    from . import obj8 as _obj8
    from .pack_pavement import pavement_pages
    if not (main_root and mod_cache_root):
        return []
    index = (_obj8.read_library_index(_obj8.library_index_path(mod_cache_root, xplane_root))
             if xplane_root else None)
    bnd, out = _union(boundaries), []
    for root in dump_candidates(main_root, tile_lat, tile_lon, index):
        pages = pavement_pages(root, os.path.basename(os.path.normpath(root)),
                               tile_lat, tile_lon, to_xy, own_extent,
                               mod_cache_root, xplane_root)
        out.extend(p for p, _tag in _evidence([(p, None) for p in pages], own, bnd, law))
    return out
