"""THE ROADS AT AN AGP PLATE (#2090 C3 P2 / C3c; spec
``2090-agp-group-groundside-spec.md`` amendment C): :func:`plate_road_levels`
-- THE ONE selection of the at-grade road vertices inside a built plate (off
every joined or riding deck's ring), read by the plate's rows (``constraints/
agp_plate``) and by the road ramp's seeds (``airport/deck_ends.
deck_end_seeds``).

In ``model`` (it reads ``geom``, ``law`` and ``model``) so both the
``constraints`` and the ``airport`` layers may import it, the form of
``model/deck_ends``.  Nothing here names an airport.
"""
from __future__ import annotations

import typing as _t

from ..geom.agp_plate import built_plates, inside_plates, under_rings
from ..law.tables import is_structure_role
from .planar import ROAD_ROLES

__all__ = ["plate_groups", "riding_rings", "plate_road_levels"]


def plate_groups(planar, airport) -> tuple:
    """The AGP groups the planar stage carries (else the airport's)."""
    return tuple(getattr(planar, "agp_groups", ()) or getattr(airport, "agp_groups", ()) or ())


def riding_rings(planar, airport) -> list:
    """C3c: the plan rings of every joined or riding kept deck."""
    from .deck_stack import KEPT, live_stacks
    return [d.ring for st in live_stacks(tuple(getattr(airport, "deck_stacks", ()) or ()), planar)
            if st.kind == KEPT and getattr(st, "datum_group", "") for d in st.decks if d.ring]


def _ways(airport) -> dict[int, dict]:
    ways = getattr(airport, "osm_ways_mapped", None) or getattr(airport, "osm_ways", ()) or ()
    return {int(w.id): dict(w.tags or {}) for w in ways}


def _at_grade(tags: _t.Mapping[str, str]) -> bool:
    if tags.get("bridge", "no") not in ("", "no") or tags.get("tunnel", "no") not in ("", "no"):
        return False
    try:
        return int(str(tags.get("layer", "0")).strip() or 0) == 0
    except ValueError:
        return True


def plate_road_levels(planar, law, airport, listed: "list | None" = None
                      ) -> dict[int, tuple[float, str]]:
    """P2's ONE selection: ``{v: (L, group id)}`` of every at-grade road
    vertex inside a built plate, off every joined or riding deck's ring
    (C3c); a vertex of a way at another layer is listed in ``listed``."""
    from .deck_ends import way_of_ref
    plates = built_plates(plate_groups(planar, airport))
    if not plates:
        return {}
    roads = []
    for v, vx in planar.vertices.items():
        faces = [planar.faces[f] for f in vx.incident_faces if f in planar.faces]
        if any(f.role in ROAD_ROLES for f in faces) and not any(
                is_structure_role(law, f.role) for f in faces):
            roads.append((v, vx.xy))
    got = inside_plates(roads, plates)
    under = under_rings([(v, planar.vertices[v].xy) for v in got], riding_rings(planar,
                                                                                 airport))
    tags = _ways(airport)
    out: dict[int, tuple[float, str]] = {}
    for v, (gid, p) in got.items():
        if v in under:
            continue
        ws = {way_of_ref(planar.faces[f].ref) for f in planar.vertices[v].incident_faces
              if f in planar.faces and planar.faces[f].role in ROAD_ROLES}
        if any(w is not None and not _at_grade(tags.get(int(w), {})) for w in ws):
            if listed is not None:
                listed.append(v)
            continue
        out[v] = (float(p.level), gid)
    return out
