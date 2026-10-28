"""§34 (12) (5) (d) THE FENCE NEEDS A WITNESS (owner RULINGS 2026-10-27z,
issue #535; narrows 2026-09-27a (4) / 10-10i (1) / 10k).

A mapped ``tunnel`` bore lying inside the airport boundary is built only
where at least one real sign shows it.  Owner 2026-10-27: "The coordinates
at KDEN do not show any tunnel there"; at SPJC the road is at ground level
under a raised walkway, so dropping the cut is more accurate than a cut.

The five witnesses, asked in this order by :func:`fence_witness`:

1. **rise** — the DEM over the bore stands ``[tunnel] terrain_rise_m``
   above its mouth chord (``structure_service._rise_m``; (5) (c) has
   already admitted such a bore before the fence is asked, so here it is
   named for completeness);
2. **road level** — a mapped road JOINED at a mouth (within ``[tunnel]
   terrain_crossing_min_m`` of it, the distance (c) reads a way as the
   approach rather than a crossing) carries a non-zero ``layer``, a
   ``bridge`` or ``tunnel`` tag or an ``incline``, or the bore itself
   carries an ``incline``;
3. **portal** — the pack stands below grade at a mouth: a part whose base
   lies deeper than ``[basin] contact_band_m`` under its object's zero (the
   ground-contact band: below it is not ground) within ``[tunnel.object]
   bore_end_tolerance_m`` of the mouth (the distance at which a mapped
   bore end IS a pack tunnel object's mouth, RULINGS 2026-09-08o), or a
   pack tunnel corridor's footprint within that distance;
4. **over** — any mapped way (road, railway, aeroway, building) other than
   a tunnel crosses the bore's INTERIOR (``terrain_crossing_min_m`` inside
   its ends), at any layer; or a pack building part AT GRADE holds
   ``terrain_cover_min_m`` of its line (the cover 10i (1) let (d) stand on).
   INSIDE A PACK BUILDING'S FOOTPRINT THE BUILDING IS THE COVER (owner
   RULINGS 2026-10-28q (3), #1338): a way crossing there, and the building
   itself, are no witness — only the bore's run outside the pack's
   footprints is read (``witness(bore, inside)``).  Several identical ways
   stacked on one line are a car park's decks and no witness either (owner
   RULINGS 2026-10-28s (4), ``structure_service.stacked_ways``);
5. **lidar** — a CREDIBLE lidar inset reads a cut along the bore
   (``channel_geometry._lidar_cut``, §45 (3) (ii)).

Measured over the seven sweep airports (scratch wrapper ``bore535.py``,
lane ``l535``): of every fence-tagged bore only SPJC -5724 and KDEN -6306
reach (d) with none of the five, so those two alone change.
"""
from __future__ import annotations

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring
from shapely.strtree import STRtree

from ..airport.deck_signature import is_bridge_way, is_tunnel_way
from ..law import Law
from .structure_service import _layer_of, _rise_m, stacked_ways

__all__ = ["fence_witness"]

#: the mapped kinds a way crossing over a bore is read as (first tag wins)
_OVER_KEYS = ("aeroway", "highway", "railway", "building")


def fence_witness(airport, law: Law, on_field, osm_ways, pack=None):
    """``f(bore) -> str | None``: the first of the five witnesses a fenced
    bore carries, named, or ``None`` when it carries none.  ``pack`` is
    the caller's ``structure_service._PackBuildings`` (one index of the
    pack's building parts, never a second reading): a part of it AT GRADE
    over the bore's line is something crossing over it."""
    tn = law.tables.structures.tunnel
    admitted = tn.admitted_values
    ways = [w for w in osm_ways if len(w.points) >= 2]
    roads = [w for w in ways if "highway" in (w.tags or {})]
    road_tree = STRtree([LineString(w.points) for w in roads]) if roads else None
    decks = stacked_ways(ways, law)             # 28s (4): a car park's decks
    over = [(g, w) for w in ways for g in (_over_geom(w),)
            if g is not None and not is_tunnel_way(w.tags or {}, admitted)
            and id(w) not in decks]
    over_tree = STRtree([g for g, _w in over]) if over else None
    portal = _Portals(airport, law, getattr(on_field, "corridor_prints", ()) or ())
    lidar = _LidarCut(airport, law)
    join_m = float(tn.terrain_crossing_min_m)

    def witness(bore, inside=None) -> str | None:
        """``inside``: the pack building footprints over the bore, where
        the building is the cover and nothing standing over the bore is a
        witness (owner RULINGS 2026-10-28q (3), #1338)."""
        ln = bore.line
        open_ln = ln if inside is None else ln.difference(inside)
        own = {id(w) for w in bore.ways}
        rise = _rise_m(airport, ln)
        if rise is not None and rise >= tn.terrain_rise_m:
            return f"rise {rise:+.2f} m over its mouth chord"
        sign = _road_sign(bore, roads, road_tree, own, join_m, admitted)
        if sign:
            return f"road level: {sign}"
        at = portal.near(bore)
        if at:
            return f"pack portal: {at}"
        crossed = _over(ln, over, over_tree, own, join_m, inside)
        if crossed:
            return "crossed over by " + ", ".join(crossed[:3])
        held = pack.at_grade_over(open_ln, tn.terrain_cover_min_m) \
            if pack is not None and not open_ln.is_empty else None
        if held:
            return f"crossed over by the pack's {held[0]} ({held[1]}) at grade"
        if lidar.cut(ln):
            return "a credible lidar inset reads a cut along it"
        return None

    return witness


def _road_sign(bore, roads, tree, own, join_m, admitted) -> str | None:
    """Witness 2: a level sign on a road joined at a mouth, or an
    ``incline`` on the bore itself."""
    for w in bore.ways:
        if "incline" in (w.tags or {}):
            return f"the bore {w.id} carries incline={w.tags['incline']}"
    for end in (bore.points[0], bore.points[-1]):
        pt = Point(end)
        for j in (tree.query(pt.buffer(join_m)) if tree is not None else ()):
            w = roads[int(j)]
            if id(w) in own or LineString(w.points).distance(pt) > join_m:
                continue
            t = w.tags or {}
            signs = [k for k, on in (("bridge", is_bridge_way(t)),
                                     ("tunnel", is_tunnel_way(t, admitted))) if on]
            if _layer_of(t, 0):
                signs.append(f"layer={_layer_of(t, 0)}")
            if "incline" in t:
                signs.append(f"incline={t['incline']}")
            if signs:
                return f"way {w.id} joined at a mouth carries " + ", ".join(signs)
    return None


def _over_geom(w):
    """A mapped way as the geometry it stands over the ground with: a
    closed building / area / apron as its footprint, anything else as its
    line; ``None`` for a kind that crosses nothing (the aerodrome)."""
    t = w.tags or {}
    kind = next((k for k in _OVER_KEYS if k in t), None)
    if kind is None or t.get("aeroway") == "aerodrome":
        return None
    area = getattr(w, "closed", False) and len(w.points) >= 4 and (
        "building" in t or t.get("area") == "yes" or t.get("aeroway") == "apron")
    try:
        g = Polygon(w.points) if area else LineString(w.points)
    except (ValueError, TypeError):
        return None
    if not g.is_valid:
        g = g.buffer(0)
    return None if g.is_empty else g


def _over(ln, over, tree, own, inside_m, inside=None) -> list[str]:
    """Witness 4: the mapped ways standing over the bore's INTERIOR — outside
    ``inside``, the pack buildings' footprints (owner RULINGS 2026-10-28q
    (3): there the building is the cover)."""
    if ln.length <= 2.0 * inside_m:
        return []
    core = substring(ln, inside_m, ln.length - inside_m)
    if inside is not None:
        core = core.difference(inside)
        if core.is_empty:
            return []
    out = []
    for j in (tree.query(core, predicate="intersects") if tree is not None else ()):
        g, w = over[int(j)]
        if id(w) in own:
            continue
        t = w.tags or {}
        kind = next(k for k in _OVER_KEYS if k in t)
        out.append(f"{w.id}[{kind}={t[kind]}]")
    return sorted(set(out))


class _Portals:
    """Witness 3: the pack's below-grade geometry at a bore's mouths."""

    def __init__(self, airport, law: Law, corridor_prints=()) -> None:
        s = law.tables.structures
        self._tol = float(s.tunnel.object.bore_end_tolerance_m)
        sunk = -float(s.basin.contact_band_m)
        self._prints = [p for p in corridor_prints if p is not None and not p.is_empty]
        self._parts: list[tuple[Polygon, str, float]] = []
        self._tree = None
        part = getattr(airport, "partition", None)
        frame = getattr(airport, "frame", None)
        if part is None or frame is None:
            return
        to_xy = frame.transformers()[0]
        for u in getattr(part, "units", ()) or ():
            for m in u.members:
                for q in m.parts:
                    if float(q.base_y) >= sunk:
                        continue
                    for r in q.rings or ():
                        poly = _ring_poly(r, to_xy)
                        if poly is not None:
                            self._parts.append((poly, str(m.resource), float(q.base_y)))
        self._tree = STRtree([p for p, _r, _b in self._parts]) if self._parts else None

    def near(self, bore) -> str | None:
        for end in (bore.points[0], bore.points[-1]):
            pt = Point(end)
            for p in self._prints:
                if p.distance(pt) <= self._tol:
                    return f"a pack tunnel corridor at {end[0]:.0f},{end[1]:.0f}"
            for j in (self._tree.query(pt.buffer(self._tol))
                      if self._tree is not None else ()):
                poly, res, base = self._parts[int(j)]
                if poly.distance(pt) <= self._tol:
                    return (f"{res} stands {base:.1f} m under its zero at "
                            f"{end[0]:.0f},{end[1]:.0f}")
        return None


def _ring_poly(ring, to_xy) -> Polygon | None:
    if len(ring) < 3:
        return None
    try:
        poly = Polygon([to_xy(lo, la) for la, lo in ring])
    except (ValueError, TypeError):
        return None
    if not poly.is_valid:
        poly = poly.buffer(0)
    return None if poly.is_empty else poly


class _LidarCut:
    """Witness 5: a credible lidar inset reads a cut along the bore — the
    channel's own reading (§45 (3) (ii)), stations ``[channel] station_m``
    apart, searched out to ``corridor_max_half_width_m``."""

    def __init__(self, airport, law: Law) -> None:
        from ..law import inset_class
        self._airport, self._law = airport, law
        ch = law.tables.structures.channel
        self._step = float(ch.station_m)
        self._cap = float(ch.corridor_max_half_width_m)
        try:
            self._credible = getattr(airport, "dem", None) is not None \
                and bool(inset_class.lidar_credible(airport, law))
        except Exception:                      # pragma: no cover - fixtures
            self._credible = False

    def cut(self, ln: LineString) -> bool:
        if not self._credible or ln.length <= 0.0:
            return False
        from .channel_geometry import _lidar_cut
        length = ln.length
        ss = [min(length, i * self._step) for i in range(int(length // self._step) + 1)]
        if ss[-1] < length:
            ss.append(length)

        def axis(s: float) -> tuple[float, float]:
            p = ln.interpolate(max(0.0, min(length, s)))
            return (p.x, p.y)

        return bool(_lidar_cut(self._airport, self._law, axis, ss, self._cap))
