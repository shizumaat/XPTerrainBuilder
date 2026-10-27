"""THE PACK'S DRAPED PAVEMENT, as DEM prep reads it (#1208, owner RULINGS
2026-10-27d: inside the airport boundary only runways and pavement stay
flat).

A custom pack authors much of its pavement as draped ``.pol`` pages in its
tile DSF, not as apt.dat row-110 polygons: measured at VHHH, 55 % of the
patch's aprons on the hill east of the terminals are ``dsf:pol`` pages.
The build reads them in ``load.load_with_report``; DEM prep's flat-site
stamp has to keep the same pavement at Z0, so this module reads the SAME
pages with the SAME admission: the pristine tile DSF's cached text dump
(``dsf.find_text_dump``), the pavement gate (``dsf.pavement_gate`` — a
``SOURCE`` page or a ``SHEET``) resolved through the pack and the library
index, and the airport's own-extent admission
(``identity.dsf_pavement_admission_m`` about the apt.dat extent).

Never raises for a missing dump: no dump is no pages (the build itself
refuses a stale dump by name; DEM prep is not the place to say it twice).
"""
from __future__ import annotations

import os
import typing as _t

from . import dsf as _dsf
from . import dsf_write as _dw
from . import obj8 as _obj8

__all__ = ["pavement_pages"]


def pavement_pages(pack_root: str, pack_name: str, tile_lat: int, tile_lon: int,
                   to_xy: _t.Callable[[float, float], tuple[float, float]],
                   own_extent, mod_cache_root: str | None,
                   xplane_root: str | None) -> list:
    """The pack DSF's pavement pages admitted for this airport, as shapely
    polygons in the airport frame (``to_xy``: ``(lon, lat) -> (x, y)``).
    ``own_extent`` is ``load._own_extent``'s answer (``None`` admits
    every page)."""
    from shapely.geometry import Polygon

    if not (pack_root and pack_name and mod_cache_root):
        return []
    pack_dsf = _dw.pristine_dsf_path(
        _dsf.dsf_path_in_pack(pack_root, tile_lat, tile_lon))
    dump_path = _dsf.find_text_dump(mod_cache_root, pack_name, tile_lat,
                                    tile_lon, dsf_path=pack_dsf)
    if not dump_path or not os.path.isfile(dump_path):
        return []
    index = (_obj8.read_library_index(
        _obj8.library_index_path(mod_cache_root, xplane_root))
        if xplane_root else None)
    gate = _dsf.pavement_gate(
        lambda p: _obj8.resolve_resource(p, pack_root, index))
    admitted = (_dsf.SOURCE, _dsf.SHEET)
    dump = _dsf.read_dump(dump_path, lambda p: gate(p)[0] in admitted)
    out = []
    for poly in dump.polygons:
        if gate(poly.def_path)[0] not in admitted or len(poly.windings[0]) < 3:
            continue
        shape = Polygon([to_xy(lo, la) for lo, la in poly.windings[0]],
                        [[to_xy(lo, la) for lo, la in h]
                         for h in poly.windings[1:] if len(h) >= 3])
        if not shape.is_valid:
            shape = shape.buffer(0)
        if shape.is_empty:
            continue
        if own_extent is not None and not own_extent.intersects(shape):
            continue
        out.append(shape)
    return out
