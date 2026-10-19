"""THE BAND RISER RECORD (owner RULINGS 2026-10-19a / 19i, #951; spec
``docs/specs/band-road-wall-joint-spec.md``): the ref a band's riser face
carries (``planar/band_riser`` mints it) and the one reading of the map's
risers every consumer shares — the bending cut (``solve/wall_cut``), the row
release (``constraints/band_riser``) and the declared wall
(``pipeline/band_road_wall``)."""
from __future__ import annotations

from .planar import is_osm_ribbon_ref

__all__ = ["RISER_SUFFIX", "is_band_riser_ref", "band_risers"]

#: owner RULINGS 2026-10-19a / 19i (#951): the ref suffix of a band's RISER
#: face — the strip of a runway / taxi safety-area band within one weld
#: spacing of a mapped-road ribbon inside it (``planar/band_riser``).
RISER_SUFFIX = ":riser"


def is_band_riser_ref(ref) -> bool:
    """A band riser face's ref (:data:`RISER_SUFFIX`)."""
    return str(ref or "").endswith(RISER_SUFFIX)


def band_risers(pm) -> list[tuple[int, frozenset[int], frozenset[int]]]:
    """``(face id, lower, upper)`` per band riser face: ``lower`` its ring
    vertices an OSM ribbon face carries (the road's kerb), ``upper`` the
    rest (the band line one weld spacing off).  Derived from the map, in
    face-id order; empty without a riser."""
    ids = [f.id for f in pm.faces.values()
           if f.role == "graded_strip" and is_band_riser_ref(f.ref)]
    if not ids:
        return []
    rib: set[int] = set()
    for f in pm.faces.values():
        if is_osm_ribbon_ref(f.ref):
            for cyc in (f.ring, *f.holes):
                rib.update(pm.ring_vertices(cyc))
    out = []
    for fid in sorted(ids):
        f = pm.faces[fid]
        vs = {v for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)}
        out.append((fid, frozenset(vs & rib), frozenset(vs - rib)))
    return out
