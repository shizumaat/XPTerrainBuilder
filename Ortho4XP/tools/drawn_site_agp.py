"""AN ``.agp`` ROW AS X-PLANE DRAWS IT, for ``drawn_site.py`` (#2090).

An ``.agp`` placement is a rigid group of OBJ8 pieces seated on the drawn
ground under ONE point, its ``GROUND_PT`` (``auto_patch_v2.airport.
agp_pieces`` places them; this module only hands them to the site reader).
Before this, ``drawn_site`` resolved ``.obj`` rows only, and KDEN's
terminal complex -- one ``Jeppesen_Concourse.agp`` row -- read "no placed
solid reaches any site".

Each piece becomes a row-like record the reader measures like any other:
``kind`` ``OBJECT_AGL`` with ``elevation`` its ``OBJ_DELTA`` height, and
``ground_lat`` / ``ground_lon`` the group's ground point, where
``drawn_site.measure_site`` reads the mesh the datum comes from.  Also:
``pack_dir`` resolves a bare pack name (``--pack "c_USA - 100_airport -
KDEN ..."``) under Custom Scenery.
"""
from __future__ import annotations

import dataclasses as _dc
import os


@_dc.dataclass(frozen=True)
class PiecePlacement:
    """One piece of a written ``.agp`` row, shaped like a DSF placement."""

    def_path: str
    lon: float
    lat: float
    heading_deg: float
    elevation: float
    ground_lat: float
    ground_lon: float
    agp: str
    kind: str = "OBJECT_AGL"


def pieces(p, root: str, index) -> list[tuple[PiecePlacement, str]]:
    """``(piece, folder its def_path resolves in)`` for every piece of the
    ``.agp`` row ``p`` (pack-first, then the library ``index``); ``[]``
    for any other row or an unreadable file."""
    if not p.def_path.lower().endswith(".agp") or p.kind == "OBJECT_MSL":
        return []
    from auto_patch_v2.airport import agp_pieces as _ap
    from auto_patch_v2.airport import obj8 as _obj8
    phys = _obj8.resolve_resource(p.def_path, root, index)
    agp = _ap.read_agp(phys) if phys else None
    if agp is None:
        return []
    glon, glat = _ap.ground_point(agp, p.lon, p.lat, p.heading_deg)
    lift = float(p.elevation or 0.0) if p.kind == "OBJECT_AGL" else 0.0
    return [(PiecePlacement(os.path.basename(pc.obj), pc.lon, pc.lat, pc.heading_deg,
                            pc.height + lift, glat, glon, p.def_path),
             os.path.dirname(pc.obj))
            for pc in _ap.placed_pieces(agp, p.lon, p.lat, p.heading_deg)]


def pack_dir(pack: str, custom_scenery: str) -> str:
    """``pack`` as given when it is a folder, else the folder of that name
    under ``custom_scenery`` (a bare pack name)."""
    if os.path.isdir(pack) or not custom_scenery:
        return pack
    cand = os.path.join(custom_scenery, pack)
    return cand if os.path.isdir(cand) else pack
