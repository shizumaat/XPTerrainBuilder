"""THE EXCLUSION WITNESS: is a pack's placement drawn at all (#2063)?

X-Plane draws a pack's objects unless a pack drawn ABOVE it excludes them:
a DSF header ``sim/exclude_obj west/south/east/north`` removes the objects
of every LOWER-priority pack whose placement lies in that box.  At KRNT the
Renton pack (``scenery_packs.ini`` row 857) excludes three boxes over the
Seattle pack's (row 868) aircraft and fuselage there, and the Seattle pack
in turn excludes Orbx's KSEA buildings: rows nobody sees.  Adopting and
rewriting them changes nothing the pilot sees and measures a model the
sim never draws (round 1's +7.93 m "FLOAT" was one of them).

THE RULE.  :func:`boxes_above` reads the ``sim/exclude_obj`` boxes of every
ENABLED pack above a given one in X-Plane's priority order
(``O4_Scenery_Packs.load_order``) that has a DSF for the tile -- the
PRISTINE DSF (``backup_state.pristine_dsf_path``), header only
(``O4_DSF_Header.dsf_property_pairs``; the box parse is
``O4_Overlay_Pack.exclusion_boxes``).  A header that cannot be read reads
as no exclusion: a row in doubt is treated as drawn.  A pack BELOW never
excludes this one's rows.
"""
from __future__ import annotations

import os
import typing as _t

__all__ = ["Exclusion", "boxes_above", "excluder_of"]

#: one exclusion box: ``(excluding pack name, (west, south, east, north))``
Exclusion = _t.Tuple[str, _t.Tuple[float, float, float, float]]


def boxes_above(pack_root: str, lat: int, lon: int) -> list[Exclusion]:
    """The ``sim/exclude_obj`` boxes of every enabled pack X-Plane draws
    above ``pack_root`` with a DSF for tile ``(lat, lon)``, highest
    priority first.  ``[]`` when the pack is not under a scenery folder or
    nothing above it excludes objects."""
    import O4_DSF_Header as _DSFH
    import O4_Overlay_Pack as _OP
    import O4_Scenery_Packs as _SP

    from .backup_state import pristine_dsf_path
    from .dsf import dsf_path_in_pack
    scenery = os.path.dirname(os.path.normpath(pack_root))
    if not os.path.isdir(scenery):
        return []
    me = os.path.basename(os.path.normpath(pack_root))
    out: list[Exclusion] = []
    for name in _SP.load_order(scenery):
        if name == me:
            break
        dsf = dsf_path_in_pack(os.path.join(scenery, name), lat, lon)
        if not os.path.isfile(dsf):
            continue
        pairs = _DSFH.dsf_property_pairs(pristine_dsf_path(dsf))
        out.extend((name, b) for b in _OP.exclusion_boxes(pairs, "sim/exclude_obj"))
    return out


def excluder_of(boxes: _t.Sequence[Exclusion], lon: float, lat: float) -> str | None:
    """The name of the first pack in ``boxes`` whose box holds
    ``(lon, lat)`` (edges included), or ``None``: the row is drawn."""
    for name, (west, south, east, north) in boxes:
        if west <= lon <= east and south <= lat <= north:
            return name
    return None
