"""THE BANK'S TOE IS ON THE GROUND: one loop for every graded-ground family
whose toe meets the lidar.

* THE OLD-DEM FILL (owner RULINGS 2026-11-06a (2); #1915; spec
  ``docs/specs/old-dem-fill-spec.md`` §2 (3): "its TOE vertices carry the
  ground datum (z = DEM, the toe is on current ground)").  A fill-bank piece
  (``planar/fill_bank``) carries the weak ground datum at the fill's level
  on every vertex (``solve/design_ground``), and the bending term rounds a
  steep embankment's toe and crest off it: MEASURED on the FHSH capture,
  the bank's ring stood up to 4.1 m off its fill, its toe 3.2 m over the
  DEM the core mesh meets there.  So every vertex of a bank piece that
  stands on the patch's open edge (an edge with no face beyond it: the toe,
  or the stand-off gap beside a road terrace) and belongs to bank pieces
  alone is pinned at its sampled level — the fill's, which is the DEM's at
  the toe and the terrace's beside a road.  Its crest, shared with the zone
  bands, keeps the zone law.
* A DECK STACK'S GROUND (#1971; spec ``interchange-levels-v2-20261113.md``
  §3.3 R4): the same rule on ``planar/stack_ground``'s pieces, on the
  stack's TOE only (the edge of ``airport/deck_stack.ground_footprint``'s
  outline): its stand-off gaps beside a road ribbon or the floor's void
  band are held by the stack's own rows (R1 / R2), and there the sampled
  level is the raw DEM, not the neighbour's.

* A DECK STACK'S BANK BESIDE ITS OWN RUN-ON ROAD FOLLOWS THE ROAD (#2116 R2
  E): a stack-ground vertex (on no toe pin) within the stand-off reach of a
  road ribbon its own GRADED end seeds (the ribbon its ``StackEnd.path``
  runs on, or an ``access`` way) is bound to the ribbon's edge at its
  nearest point, ``|z_bank - z_road| <= bank_slope x distance`` — the
  ``constraints/gap_follow`` form, one-way (the road leads, the bank
  follows).  The DEM toe stays on the footprint outline only.

No airport is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Linear, Pin, Row, Source
from ..model.planar import PlanarMap, is_agp_bank_ref, is_fill_bank_ref, is_stack_ground_ref

__all__ = ["fill_toe_pins", "GEN", "RULING", "STACK_RULING"]

GEN = "fill_toe_pins"
RULING = "zones.adjacent_ground old-DEM fill toe"
STACK_RULING = "RULINGS 2026-11-13g / 2026-11-11b: a deck stack's ground meets the lidar at its toe"
#: #2116 R2 E: a stack's bank beside its own run-on road follows the road
ROAD_RULING = "#2116 R2 E: a deck stack's bank beside its own run-on road follows the road"
#: #2090 C3: an AGP plate's bank meets the lidar at its toe
AGP_RULING = "#2090 C3: an AGP plate's bank meets the lidar at its toe"


def _stack_toe(planar: PlanarMap, law: Law, airport: Airport):
    """``xy -> bool``: on a stack's toe (its ground outline's edge, off the
    floor's keep), within the identity grid."""
    import shapely

    from ..geom.deck_ground import ground_footprint
    from ..model.deck_stack import live_stacks
    stacks = live_stacks(tuple(getattr(airport, "deck_stacks", ()) or ()), planar)
    if not stacks:
        return lambda _xy: False
    grid = float(law.tables.emit.identity.min_distinct_spacing_m)
    lines = []
    for st in stacks:
        fp = ground_footprint(st, law)
        lines.append(fp["outline"].boundary.difference(fp["keep"].buffer(grid)))
    toe = shapely.union_all(lines).buffer(grid)
    shapely.prepare(toe)
    return lambda xy: bool(shapely.contains_xy(toe, xy[0], xy[1]))


def _agp_toe(planar: PlanarMap, law: Law, airport: Airport):
    """``xy -> bool``: off every built AGP plate by more than the identity
    grid (a bank vertex on the plate's own edge is no toe)."""
    import shapely

    from ..geom.agp_plate import built_plates
    plates = built_plates(getattr(planar, "agp_groups", ()) or getattr(airport, "agp_groups", ()))
    if not plates:
        return lambda _xy: False
    grid = float(law.tables.emit.identity.min_distinct_spacing_m)
    near = shapely.union_all([poly for _g, _p, poly in plates]).buffer(2.0 * grid)
    shapely.prepare(near)
    return lambda xy: not bool(shapely.contains_xy(near, xy[0], xy[1]))


def fill_toe_pins(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """One hard pin per open-edge vertex of a bank family's toe (docstring)."""
    rows: list[Row] = []
    seen: set[int] = set()
    for is_ref, ruling, toe in ((is_fill_bank_ref, RULING, None),
                                (is_stack_ground_ref, STACK_RULING, _stack_toe),
                                (is_agp_bank_ref, AGP_RULING, _agp_toe)):
        bank = {f.id for f in planar.faces.values() if is_ref(f.ref)}
        if not bank:
            continue
        on_toe = toe(planar, law, airport) if toe is not None else None
        for e in planar.edges.values():
            if (e.left_face is None) == (e.right_face is None):
                continue
            if (e.left_face if e.left_face is not None else e.right_face) not in bank:
                continue
            for v in (e.a, e.b):
                vx = planar.vertices[v]
                if v in seen or vx.dem_z is None or not set(vx.incident_faces) <= bank:
                    continue
                if on_toe is not None and not on_toe(vx.xy):
                    continue
                seen.add(v)
                rows.append(Pin(v, float(vx.dem_z), Source(GEN, ruling, (f"vertex:{v}",))))
    rows += _bank_road_rows(planar, law, airport, seen)
    return rows


def _seeded_ribbons(planar: PlanarMap, st, step: float) -> dict[int, str]:
    """Face id -> way id label of every road ribbon one of ``st``'s GRADED
    ends seeds: the ribbon its path runs on, or an ``access`` way's."""
    from ..geom.deck_ground import path_line
    from ..model.deck_ends import way_of_ref
    from ..model.planar import ROAD_ROLES
    lines = []
    access: set[int] = set()
    for e in st.graded_ends():
        line = path_line(e, float(e.run) + step)
        if line is not None:
            lines.append(line.buffer(0.5))
        access.update(int(w) for w in e.access)
    if not lines and not access:
        return {}
    import shapely
    from shapely.geometry import Polygon
    zone = shapely.union_all(lines) if lines else None
    out: dict[int, str] = {}
    for fid, f in planar.faces.items():
        if f.role not in ROAD_ROLES:
            continue
        w = way_of_ref(f.ref)
        if (w is not None and w in access) or (
                zone is not None and len(f.ring) >= 3 and zone.intersects(Polygon(
                    [planar.vertices[v].xy for v in planar.ring_vertices(f.ring)]))):
            out[fid] = str(f.ref)
    return out


def _bank_road_rows(planar: PlanarMap, law: Law, airport: Airport, pinned: set[int]) -> list[Row]:
    """#2116 R2 E (module doc): one follow row per stack-ground vertex
    within the stand-off reach of a ribbon its own stack's end seeds."""
    import numpy as np

    from ..model.deck_stack import live_stacks
    from ..model.planar import STACK_GROUND_PREFIX
    from .gap_follow import reach_m
    stacks = live_stacks(tuple(getattr(airport, "deck_stacks", ()) or ()), planar)
    if not stacks:
        return []
    slope = float(law.tables.emit.design.bank_slope)
    step = float(law.tables.structures.bridge.abutment_sample_step_m)
    reach = reach_m(law, pad=True)
    rows: list[Row] = []
    done: set[int] = set()
    for st in stacks:
        ribbons = _seeded_ribbons(planar, st, step)
        if not ribbons:
            continue
        mine = STACK_GROUND_PREFIX + st.id + ":"
        own = {fid for fid, f in planar.faces.items() if str(f.ref).startswith(mine)}
        bank = [v for fid in own for v in planar.ring_vertices(planar.faces[fid].ring)]
        bank = sorted({v for v in bank if v not in pinned and v not in done
                       and set(planar.vertices[v].incident_faces) <= own})
        if not bank:
            continue
        bxy = np.array([planar.vertices[v].xy for v in bank], float)
        best = np.full(len(bank), np.inf)
        foot: list = [None] * len(bank)
        for fid, ref in ribbons.items():
            ring = list(planar.ring_vertices(planar.faces[fid].ring))
            ring.append(ring[0])
            for a, b in zip(ring, ring[1:]):
                pa, pb = np.array(planar.vertices[a].xy), np.array(planar.vertices[b].xy)
                ab = pb - pa
                ll = float(ab @ ab)
                if ll <= 1e-12:
                    continue
                t = np.clip(((bxy - pa) @ ab) / ll, 0.0, 1.0)
                d = np.hypot(*(bxy - (pa + t[:, None] * ab)).T)
                for k in np.flatnonzero((d < best) & (d <= reach)).tolist():
                    best[k] = d[k]
                    foot[k] = (a, b, float(t[k]), ref)
        for k, v in enumerate(bank):
            if foot[k] is None or best[k] <= 0.0:
                continue
            a, b, t, ref = foot[k]
            cap = slope * float(best[k])
            terms = [(v, 1.0)] + [(u, -c) for u, c in ((a, 1.0 - t), (b, t)) if c > 1e-9]
            rows.append(Linear(tuple(terms), -cap, cap,
                               Source(GEN, ROAD_RULING, (st.id, f"vertex:{v}", ref)), follows=v))
            done.add(v)
    return rows
