"""A ROAD OR LOT BELOW THE BUILDING'S FLOOR KEEPS ITS OWN LEVEL (owner
2026-11-04T14:53Z on #1852, verbatim: "Yes! Typically terminals have two
(or more) levels with roads and/or rails serving both stacked on top of
each other").

A groundside road or lot face that shares a pad's rim is welded to it by
identity (spec §63 (4) (ii), RULINGS 2026-10-09j): the shared vertex is a
PAD column, so the pad's plate (``pads.pad_flats``, the 1 % ceiling) and
its frontage level fit (``pads.pad_frontage_level``) hold it at the pad's
level.  MEASURED KIAH (station ``KIAH_Trainstation2`` by Terminal D
landside, pad ``building88``): the pad takes its apron frontage's 28.04 m
and the lot ``pav62#beyond1`` welded along its landside rim rode up with
it over a DEM of 24.9-26.3 m; ``--why-from`` named the pad's level row
(112 terms, dual 19.69).  The station's walls are authored down to y
-3.93, so the lot there is the building's LOWER level, not its door.

THE RULE.  A rim vertex a pad shares with a GROUNDSIDE value face is
RELEASED from that pad's plane — it follows its own road / lot / ground
rules — where

* THE OBJECT SAYS SO (the witness): a WALLED part
  (``[placement] chain_min_height_m``) standing on the pad has its base
  authored more than ``[cockpit] visual_m`` below the pad's zero
  (``Part.base_y``) and its footprint within ``[design] pad_frontage_m``
  of the vertex, and no floor-level walled part on the pad stands nearer
  to it (a door at floor level keeps its frontage); or
* THE GROUND SAYS SO, where no pack part stands on the pad at all (the
  fallback): the frontage STRETCH (a run of consecutive such rim
  vertices) stands on DEM more than ``[cockpit] visual_m`` below the
  DEM of the pad's seat, its AIRSIDE frontage (``pads.pad_frontage``;
  the §28 (6) datum, owner RULINGS 2026-09-18c (1)).  A pad that fronts
  nothing airside stands on its own DEM datum and releases nothing.

A landing, a lower or upper level and their banks already stand at the
level their object states, and a held block or a contact-led platform is
one HARD plane (a stepped one gets its lower level from
``planar/low_level``): none of them is released.

A vertex several pads share is released only when every one of them
releases it.  A vertex airside pavement shares is never released: airside
is king, and the pad's door onto the apron is its seat (§20).

ONE DERIVATION, read by ``cluster_pad.plane_groups`` (the plate every
plane row is priced over) and ``pads._pad_rows`` (its per-face pairs);
``pipeline/publication`` publishes each released vertex's drop under the
pad's level as its ``pad_relief`` so ``verify/pads.pad_flat`` reads the
plate on its level plane, as it does an authored relief.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Point, Polygon
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import cockpit, is_rigid_role, is_value_role, role_side
from ..model.airport import Airport
from ..model.map_memo import per_map
from ..model.planar import PlanarMap, is_bank_ref, platform_ref_of

__all__ = ["released_vertices", "released_offsets", "STATS"]

#: what the last derivation released, by reason (the design report line)
STATS: dict[str, int] = {}
_MEMO: dict[int, tuple[_t.Any, dict]] = {}


def _walled_parts(airport: Airport, law: Law, to_xy) -> list[tuple[Polygon, float]]:
    """``(frame footprint, base y)`` of every walled, non-line pack part."""
    part = getattr(airport, "partition", None)
    if part is None:
        return []
    wall_min = float(law.tables.structures.placement.chain_min_height_m)
    out: list[tuple[Polygon, float]] = []
    for u in part.units:
        for m in u.members:
            for p in m.parts:
                if getattr(p, "line", False) or float(p.height_m or 0.0) < wall_min:
                    continue
                for rg in (p.rings or ()):
                    if len(rg) < 3:
                        continue
                    g = Polygon([to_xy(lon, lat) for lat, lon in rg])
                    g = g if g.is_valid else g.buffer(0.0)
                    if not g.is_empty:
                        out.append((g, float(p.base_y)))
    return out


def _groundside_shared(planar: PlanarMap, law: Law) -> tuple[set[int], set[int]]:
    """``(vertices of a groundside value face, vertices of an airside value
    face)`` — the weld population and the vertices never released."""
    ground: set[int] = set()
    air: set[int] = set()
    for f in planar.faces.values():
        if is_rigid_role(law, f.role) or not is_value_role(law, f.role):
            continue
        side = role_side(law, f.role)
        if side not in ("groundside", "airside"):
            continue
        vs = {v for r in (f.ring, *f.holes) for v in planar.ring_vertices(r)}
        (ground if side == "groundside" else air).update(vs)
    return ground, air


def _median_dem(planar: PlanarMap, vs: _t.Iterable[int]) -> float | None:
    """The median planar ``dem_z`` over ``vs`` (``None`` with no sample)."""
    z = sorted(float(planar.vertices[v].dem_z) for v in vs
               if planar.vertices[v].dem_z is not None)
    return z[len(z) // 2] if z else None


def _stretches(ring: _t.Sequence[int], keep: set[int]) -> list[list[int]]:
    """Maximal runs of consecutive ``ring`` vertices in ``keep`` (cyclic)."""
    n = len(ring)
    if not n or not any(v in keep for v in ring):
        return []
    if all(v in keep for v in ring):
        return [list(ring)]
    start = next(i for i in range(n) if ring[i] not in keep)
    runs: list[list[int]] = []
    cur: list[int] = []
    for k in range(1, n + 1):
        v = ring[(start + k) % n]
        if v in keep:
            cur.append(v)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return runs


def released_vertices(planar: PlanarMap, law: Law, airport: Airport | None
                      ) -> frozenset[int]:
    """The pad rim vertices a lower-level road or lot keeps (module doc)."""
    if airport is None or not getattr(planar, "faces", None):
        return frozenset()
    memo = per_map(_MEMO, planar)
    key = (id(law), id(airport))
    if key in memo:
        return memo[key]
    from .pads import _pad_polys, frontage_radius_m, is_lower_level, pad_frontage
    from ..model.platform import datum_vertices
    from .platform import hold_sets, plane_sets
    bar = float(cockpit(law).visual_m)
    reach = frontage_radius_m(law)
    ground, air = _groundside_shared(planar, law)
    # a held block's welded contact or datum column is HELD hard by its
    # frontage hold (``platform.hold_sets``): never the plate's to release
    for _r, dv, hw, _n, _k in hold_sets(planar, law):
        air.update(hw)
        air.add(dv)
    weld = ground - air
    lands = planar.registries.landings
    # a HELD block or a contact-led PLATFORM is one HARD plane
    # (``platform.platform_plane_rows`` / the frontage hold): its lower
    # level is ``planar/low_level``'s, never a release from the plate
    hard = set(datum_vertices(planar, law)) | {r for r, _c, _v in plane_sets(planar, law)}
    front = pad_frontage(planar, law) if weld else {}
    parts = _walled_parts(airport, law, airport.frame.entry()) if weld else []
    tree = STRtree([g for g, _y in parts]) if parts else None
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    keep: dict[int, bool] = {}           # vertex -> released by every pad so far
    n_wit = n_dem = 0
    read: set[int] = set()
    for fid, ref, group, poly in _pad_polys(planar, law):
        read.add(fid)
        rim = [v for v in group if v in weld]
        if (not rim or is_bank_ref(ref) or is_lower_level(ref)
                or platform_ref_of(str(ref)) in lands
                or platform_ref_of(str(ref)) in hard):
            # a landing, a lower or upper level and their banks already
            # stand at the level their object states (``platform.landing_rows``)
            for v in rim:
                keep[v] = False
            continue
        on = ([parts[int(i)] for i in tree.query(poly, predicate="intersects")]
              if tree is not None else [])
        on = [(g, y) for g, y in on if g.intersection(poly).area > 0.0]
        rel: set[int] = set()
        if on:
            low = [g for g, y in on if y < -bar]
            floor = [g for g, y in on if y >= -bar]
            for v in rim if low else ():
                pt = Point(*xy[v])
                d_low = min(g.distance(pt) for g in low)
                if d_low > reach:
                    continue
                if floor and min(g.distance(pt) for g in floor) < d_low:
                    continue                     # a door at floor level
                rel.add(v)
            n_wit += len(rel)
        else:
            datum = _median_dem(planar, (v for c in front.get(fid, {}).values()
                                         for v in c))
            ring = list(planar.ring_vertices(planar.faces[fid].ring))
            for run in _stretches(ring, set(rim)) if datum is not None else ():
                fd = _median_dem(planar, run)
                if fd is not None and fd - datum < -bar:
                    rel.update(run)
            n_dem += len(rel)
        for v in rim:
            keep[v] = keep.get(v, True) and v in rel
    # a pad the polygon read skipped (a sliver rim) releases nothing
    for fid, f in planar.faces.items():
        if fid not in read and is_rigid_role(law, f.role):
            for r in (f.ring, *f.holes):
                for v in planar.ring_vertices(r):
                    if v in keep:
                        keep[v] = False
    out = frozenset(v for v, k in keep.items() if k)
    STATS.clear()
    STATS.update({"witness": n_wit, "dem_fallback": n_dem, "released": len(out)})
    memo[key] = out
    return out


def released_offsets(planar: PlanarMap, law: Law, airport: Airport | None, z
                     ) -> dict[int, float]:
    """``released vertex -> its solved drop under its pad's LEVEL`` (the
    median of the plate's own solved vertices), published with the pad's
    relief so the pad's flatness readers take the plate on its level
    plane: the lower level is the building's, as an authored relief is."""
    out_v = released_vertices(planar, law, airport)
    if not out_v or z is None:
        return {}
    from .cluster_pad import plane_groups
    got: dict[int, float] = {}
    for _gid, _ref, group, fids in plane_groups(planar, law, airport):
        zs = sorted(float(z[v]) for v in group if v < len(z))
        if not zs:
            continue
        level = zs[len(zs) // 2]
        for q in fids:
            f = planar.faces[q]
            for r in (f.ring, *f.holes):
                for v in planar.ring_vertices(r):
                    if v in out_v and v < len(z) and v not in got:
                        got[v] = float(z[v]) - level
    return got
