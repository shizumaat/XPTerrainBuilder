"""THE DECK STACK'S ROWS (#1971; spec ``interchange-levels-20261113.md``
§3.7, §3.8).  The floor itself is an object floor
(``constraints/object_floor`` pins it); this generator states the rest of a
stack (``Airport.deck_stacks``, ``model/deck_stack``), every row under the
hard-deck bridge's ONE ruling head (``edge_deck.RIGID``: one zero, flush at
both end lines — RULINGS 2026-10-30a):

* each END LINE: every road vertex (``ROAD_ROLES``, on no structure face)
  within two ``[bridge] abutment_sample_step_m`` of a station stands at the
  stack's zero + the plate's top there, within ``deck_flush_m`` — the road
  grades to the deck's end by its own law, the deck never tilts;
* the WALLS' TOP: a vertex of the floor's void band's outer ring along a
  wall line stands in ``[zero + crest - [cockpit] visual_m, zero + crest]``
  — never over the wall's top, at most half a metre under it;
* UNDER A DECK: a vertex inside a deck piece's ring and off the floor stays
  under the plate there (``zero + plate y - deck_flush_m``) — no ground
  through a deck.  No face is minted for a deck; nothing here cuts.

A vertex two end lines claim at heights more than ``deck_flush_m`` apart is
refused by both (two road ends meeting in plan, §4).  With no stack the
generator returns ``[]``.
"""
from __future__ import annotations

import numpy as np

from ..geom.lowest_face import floor_z_at
from ..law import Law
from ..law.tables import is_structure_role
from ..model.airport import Airport
from ..model.constraints import Band, Row, Source
from ..model.planar import ROAD_ROLES, PlanarMap
from .edge_deck import RIGID

__all__ = ["GEN", "deck_stack_rows"]

GEN = "deck_stack"


def _xy(planar: PlanarMap, ids) -> np.ndarray:
    return np.array([planar.vertices[v].xy for v in ids], float).reshape(-1, 2)


def _road_vertices(planar: PlanarMap, law: Law) -> list[int]:
    """Vertices of a road face standing on no structure face."""
    out = []
    for v, vx in planar.vertices.items():
        roles = [planar.faces[f].role for f in vx.incident_faces if f in planar.faces]
        if any(r in ROAD_ROLES for r in roles) and not any(is_structure_role(law, r)
                                                           for r in roles):
            out.append(v)
    return out


def _ref_vertices(planar: PlanarMap, ref: str) -> set[int]:
    out: set[int] = set()
    for f in planar.faces.values():
        if f.ref.split("#")[0] == ref:
            out.update(planar.ring_vertices(f.ring))
            for h in getattr(f, "holes", ()) or ():
                out.update(planar.ring_vertices(h))
    return out


def _seg_dist(p: np.ndarray, line: np.ndarray) -> np.ndarray:
    """Each point's distance to the polyline ``line``."""
    best = np.full(len(p), np.inf)
    for a, b in zip(line[:-1], line[1:], strict=True):
        e = b - a
        L2 = float(e @ e) or 1e-12
        t = np.clip(((p - a) @ e) / L2, 0.0, 1.0)
        best = np.minimum(best, np.hypot(*(p - (a + t[:, None] * e)).T))
    return best


def deck_stack_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """The stacks' end-line, rim and ceiling rows (module doc)."""
    stacks = tuple(getattr(airport, "deck_stacks", ()) or ())
    if not stacks:
        return []
    br = law.tables.structures.bridge
    flush = float(br.deck_flush_m)
    reach = 2.0 * float(br.abutment_sample_step_m)
    visual = float(law.tables.emit.cockpit.visual_m)
    thick = float(law.tables.structures.tunnel.object.wall_face_max_thickness_m)
    roads = _road_vertices(planar, law)
    rxy = _xy(planar, roads)
    rows: list[Row] = []
    for st in stacks:
        floor_vs = _ref_vertices(planar, st.floor_ref)
        if not floor_vs:
            continue                    # the floor never entered the map
        z0 = float(st.zero_z)
        # THE END LINES: vertex -> [(z, deck)]
        claims: dict[int, list[tuple[float, str, str]]] = {}
        for d in st.decks:
            for side, line, top in (("a", d.end_a, d.top_a), ("b", d.end_b, d.top_b)):
                if not line or not len(roads):
                    continue
                pts = np.asarray(line, float)
                near = np.min(np.hypot(rxy[:, None, 0] - pts[None, :, 0],
                                       rxy[:, None, 1] - pts[None, :, 1]), axis=1) <= reach
                for k in np.flatnonzero(near).tolist():
                    claims.setdefault(roads[k], []).append(
                        (z0 + float(top), d.object_id, f"{d.object_id}#{d.piece} end {side}"))
        ends: dict[int, str] = {}
        for v, cl in sorted(claims.items()):
            zs = [c[0] for c in cl]
            if max(zs) - min(zs) > flush:
                continue                # two road ends meet in plan (§4): refused
            z, oid, part = cl[0]
            ends[v] = oid
            rows.append(Band(v, z - flush, z + flush, Source(GEN, RIGID, (st.id, oid, part))))
        # THE WALLS' TOP along the wall lines
        crest = z0 + float(st.crest_y)
        band = sorted(_ref_vertices(planar, st.wall_ref) - floor_vs)
        if band and st.rim:
            bxy = _xy(planar, band)
            d_rim = np.min([_seg_dist(bxy, np.asarray(r, float)) for r in st.rim], axis=0)
            src = Source(GEN, RIGID, (st.id, st.walls_id, "the walls' top"))
            rows.extend(Band(v, crest - visual, crest, src)
                        for v, dd in zip(band, d_rim.tolist(), strict=True) if dd <= thick)
        # UNDER A DECK: never over its plate
        import shapely
        from shapely.geometry import Polygon
        allv = [v for v in planar.vertices if v not in floor_vs]
        axy = _xy(planar, allv)
        for d in st.decks:
            ring = Polygon(d.ring)
            inside = shapely.contains_xy(ring, axy[:, 0], axy[:, 1]) if len(allv) else []
            ks = [k for k in np.flatnonzero(inside).tolist() if ends.get(allv[k]) != d.object_id]
            if not ks:
                continue
            plate = np.asarray(d.plate, float).reshape(-1, 3, 3)
            ys = floor_z_at(plate, axy[ks, 0], axy[ks, 1], edge_m=0.5)
            lo = float(plate[:, :, 2].min()) if len(plate) else 0.0
            src = Source(GEN, RIGID, (st.id, d.object_id, f"#{d.piece} under the deck"))
            for k, y in zip(ks, ys.tolist(), strict=True):
                rows.append(Band(allv[k], None, z0 + (y if y == y else lo) - flush, src))
    return rows
