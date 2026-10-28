"""§34 (12) THE TWO DERIVATIONS A CORRIDOR IS JUDGED BY (owner RULINGS
2026-09-15f item 1; Fable 2026-09-15i; spec §34 (12)) — lane
`v2vmmcshore`.

Two readings, both pure functions of the law and the classification, and
both used at exactly one site in :mod:`auto_patch_v2.planar.structures`:

* :func:`airside_cut_roles` — clause (3)'s protected set: the airside
  roles a corridor may never cut;
* the faces of that set ONE corridor must stop short of — since issue
  #971 (owner 2026-10-19, "tunnel mouths should always stop at the
  pavement") read in ``planar/structure_mouth.mouth_stops``, which also
  withdrew the "portal's own pavement" exemption for the taxi family and
  the pavement over the bore.

CLAUSE (1) IS WITHDRAWN (Fable 2026-09-15; RULINGS 2026-09-15w).  Round
1 read it as "a tunnel is built only where its bore passes under a cover
class" and measured the price at LEMD by dry pair: **54 tunnels → 16**,
the 38 lost being exactly owner 2026-09-12ab's "Build them" population —
a mapped tunnel whose mouth stands on the field is built, mouth and
ramp, whether or not its bore passes under an airport surface.  That is
an owner ruling, and (1) reversed it by the side door.  ADMISSION IS BY
THE MOUTH (§29 (1), ``mouth_standoff_m``); what stops VMMC's seafront
line is (2)–(4), and the code for (1) is DELETED rather than gated.

They live beside ``structures.py`` rather than in it for the reason
``structure_approach.py`` and ``structure_deck.py`` do: that file stands
at its 1,000-line budget (``tests/auto_patch_v2/test_planar.py::
test_import_and_budget``).
"""
from __future__ import annotations

import math
import typing as _t

import shapely
from shapely.geometry import LineString, Polygon

from ..law import Law
from ..law.tables import is_structure_role, is_value_role, role_side
from .structure_approach import carriageway_width_m, under_cover

if _t.TYPE_CHECKING:  # annotations only (PEP 563 is on)
    from ..model.airport import Airport

__all__ = ["airside_cut_roles", "deck_witness_for", "stacked_ways",
           "decked_exclusion", "owner_kept", "pad_relief_m",
           "parts", "SURFACE_LINE_KINDS", "terrain_tunnel_witness", "knee_nodes"]


def terrain_tunnel_witness(airport, law: Law, on_field, osm_ways):
    """§34 (12) (5) A BORE THAT ENTERS A BUILDING IS THE BUILDING'S RAMP,
    NOT A TERRAIN TUNNEL (owner RULINGS 2026-09-16d) — the reading ONE
    bore is admitted or refused by, as ``f(bore) -> (built, reason)``.

    Owner 2026-09-16: "There should be no tunnels cut at VMMC because all
    of the roads are above ground, all the bridges/overpasses/ramps are
    handled by elevated roads provided by the sim, they don't need any
    trenches cut."

    (a) A bore whose MAPPED END stands inside a BUILDING footprint, an
    underground parking or a ``covered=yes`` structure is that building's
    own ramp — the object or the sim carries it — and is NOT built; a PACK
    building's footprint counts like an OSM one (owner RULINGS 2026-09-27a
    (3), :class:`_PackBuildings`).
    (b) A mapped bridge / overpass / ramp over ordinary ground is the
    SIM'S ELEVATED ROAD: it is not a crossing at grade, so it is no
    witness at all here (and §34 (12) (4) already withholds its deck).
    (c) A TERRAIN TUNNEL passes UNDER something at grade, by any of four
    witnesses — the classified cover (pavement, a pad, a roofed
    corridor's footprint) for ``terrain_cover_min_m``; a mapped road or
    railway AT GRADE crossing the bore's INTERIOR; the DEM standing
    ``terrain_rise_m`` over the bore above the line between its own two
    mouth grounds (#65);
    or the bore's own ``layer`` at or under ``terrain_layer_max``, which
    is OSM's statement that it runs below what it crosses.
    (d) An OSM ``tunnel`` bore lying INSIDE THE AIRPORT BOUNDARY is a
    terrain tunnel ONLY where it carries ONE of the five witnesses of
    :func:`planar.structure_fence.fence_witness` — a rise, a road-level
    sign at a mouth, a pack portal, anything crossing over it, a lidar cut
    on a credible inset (owner RULINGS 2026-10-27z, issue #535, narrowing
    2026-09-27a (4)); with none it is NOT built (SPJC -5724, the road at
    ground level under a raised walkway; KDEN -6306, no tunnel there).
    Pavement painted over it (the classified cover less the building
    pads, ``FieldRegion.roofed_run_m``) and the bore's own
    ``layer`` are the tag's, not witnesses (owner RULINGS 2026-10-28p (4),
    #1338: NZWN's multi-storey car park maps its ground level as
    ``layer=-1`` tunnels under its own pavement; they were cut to -3.1 m).
    (e) THE PACK'S OPEN PASSAGE OUTRANKS COVER, A CROSSING, A RISE, A
    NEGATIVE LAYER AND THE FENCE (owner RULINGS 2026-10-10q, issue #548;
    extends 10i (1) / 10k, issue #522; the layer since #710): where an ELEVATED pack part stands over a mapped
    bore's carriageway with clear space beneath and no pack part at
    grade covers its line (:meth:`_PackBuildings.passage`), the tag is
    the road's passage under that part, at grade, and nothing is cut —
    asked FIRST, after (a), of every mapped bore.  MEASURED at KCLT: a
    313 m ``service`` bore under the terminal read 273.0 m of cover (the
    terminal's own pad) and +0.55 .. +0.82 m of ground over its mouth
    chord, under a road deck 6 m over the terminal's zero with nothing at
    grade.
    A NEGATIVE ``layer`` IS NOT SENIOR TO IT (owner sim read of app
    1.0.394, issue #710, narrowing 10q's layer clause): OSM's ``layer`` is
    relative to what the way crosses, and under an elevated part with
    clear space beneath ``layer=-1`` says only that the road runs below
    THAT part.  MEASURED at HECA: -20899 / -19181 / -3949 (``layer`` -1,
    under ``T3_road``'s viaduct, ``concrete_2`` 2.63 m over the
    carriageway, nothing at grade) were built as one 7.5 m trench at
    30.1127618, 31.3974461 where the owner reads "the road is on the
    ground, going below an elevated road deck, not below ground"; no
    other bore at the seven sweep airports reads both a passage and a
    negative layer.

    THE LAST TWO ARE §34 (12) (4)'S OWN WITNESSES, in the form a BORE
    takes them: (4) (i) reads a tag, (4) (ii) reads the DEM against the
    abutments of the thing in question — for a deck its span's, for a
    bore its two mouths'.  MEASURED at VMMC (lane `v2vmmcbore`): the nine
    car-park ramps under Taipa read cover 0.0 m, no crossing, rise +0.00
    .. +0.33 m and NO layer; the three real Macau road tunnels read
    +1.10 / +1.36 / +10.53 m of ground over them, two ``primary`` roads
    across them and ``layer`` -1 / -2.  Nothing had to be tuned between
    them.

    ``on_field`` is the ``FieldRegion`` §29 (1) gated the mouths with —
    the SAME cover, never a second union — and it carries the airport the
    DEM is sampled from.  A witness with no cover tree and no DEM claims
    nothing and every bore is built, which is what a caller with no
    classification means.
    """
    from shapely.geometry import LineString, Point, Polygon
    from shapely.strtree import STRtree
    from ..airport.deck_signature import is_enclosure_way, is_tunnel_way
    tn = law.tables.structures.tunnel

    # (a) the enclosures — closed rings only; a tag on an open way states
    # no footprint to stand inside
    encl: list[tuple[Polygon, str, object]] = []
    for w in osm_ways:
        if not getattr(w, "closed", False) or len(w.points) < 4:
            continue
        why = is_enclosure_way(w.tags or {}, tn.enclosure_parking_values)
        if not why:
            continue
        try:
            poly = Polygon(w.points)
        except (ValueError, TypeError):
            continue
        if poly.is_valid and not poly.is_empty:
            encl.append((poly, why, w.id))
    encl_tree = STRtree([p for p, _w, _i in encl]) if encl else None
    # (a) EXTENDED TO THE PACK (owner RULINGS 2026-09-27a (3), issue #12
    # Q-12b): a bore entering a PACK building unit is refused like one
    # entering an OSM building
    pack_bldg = _PackBuildings(airport, law,
                               getattr(on_field, "corridor_prints", ()) or (),
                               getattr(on_field, "corridor_objects", ()) or ())

    # (b)/(c) the roads and railways AT GRADE.  A `bridge` way, or one at
    # `layer >= 1`, is the sim's elevated road and is not a crossing.
    grade: list[tuple[LineString, object]] = []
    for w in osm_ways:
        t = w.tags or {}
        if len(w.points) < 2 or ("highway" not in t and "railway" not in t):
            continue
        if is_tunnel_way(t, tn.admitted_values):
            continue
        if str(t.get("bridge", "")).strip().lower() not in ("", "no"):
            continue
        if _layer_of(t, 0) >= 1:
            continue
        grade.append((LineString(w.points), w))
    # STACKED WAYS ARE A CAR PARK'S DECKS (owner RULINGS 2026-10-28s (4))
    decks = stacked_ways([w for _ln, w in grade], law)
    grade = [(ln, w) for ln, w in grade if id(w) not in decks]
    grade_tree = STRtree([ln for ln, _w in grade]) if grade else None

    # (d) THE FENCE (owner RULINGS 2026-09-27a (4), issue #5; NARROWED by
    # 2026-10-27z, issue #535): an OSM ``tunnel`` bore lying INSIDE the
    # airport boundary (apt.dat row 130) is a terrain tunnel where one of
    # the five witnesses shows it.  Outside the fence the four witnesses
    # of (c) apply as before.  (a)'s refusal runs FIRST: a bore entering a
    # building is that building's ramp inside the fence too; (e)'s runs
    # second.
    from .structure_fence import fence_witness
    fence = _fence_of(airport)
    fenced = fence_witness(airport, law, on_field, osm_ways, pack_bldg)

    def witness(bore) -> tuple[bool, str]:
        ln = bore.line
        ids = "+".join(str(w.id) for w in bore.ways)
        for end in (bore.points[0], bore.points[-1]):
            pt = Point(end)
            for j in (encl_tree.query(pt, predicate="within")
                      if encl_tree is not None else ()):
                _p, why, wid = encl[int(j)]
                return False, (f"bore {ids} ENTERS AN ENCLOSURE at "
                               f"{end[0]:.0f},{end[1]:.0f} — way {wid} {why}: it is "
                               f"that structure's own ramp, not a terrain tunnel "
                               f"(§34 (12) (5) (a))")
            hit = pack_bldg.at(end)
            if hit is not None:
                res, uid, top = hit
                return False, (f"bore {ids} ENTERS A PACK BUILDING at "
                               f"{end[0]:.0f},{end[1]:.0f} — {res} ({uid}) stands "
                               f"{top:.1f} m over its zero there: it is that "
                               f"building's own ramp, not a terrain tunnel "
                               f"(§34 (12) (5) (a) extended, owner RULINGS "
                               f"2026-09-27a (3))")
        cover = on_field.cover_run_m(ln) if on_field is not None else 0.0
        lay = _layer_of_bore(bore)
        below = lay is not None and lay <= tn.terrain_layer_max
        rise = _rise_m(airport, ln)
        # THE PACK'S OPEN PASSAGE IS ASKED FIRST (owner RULINGS 2026-10-10q):
        # over the cover, crossing, rise and layer witnesses — a negative
        # ``layer`` under an elevated part says only that the road runs
        # below that part (#710)
        if _osm_tunnel(bore, tn.admitted_values):
            width = max(carriageway_width_m(w.tags or {}, law) for w in bore.ways)
            over = pack_bldg.passage(ln, width, tn.terrain_cover_min_m)
            if over is not None:
                res, uid, base = over
                return False, (f"bore {ids} PASSES UNDER AN ELEVATED PACK PART AT "
                               f"GRADE ({ln.length:.0f} m; classified cover "
                               f"{cover:.1f} m, ground "
                               f"{'unreadable' if rise is None else f'{rise:+.2f} m'} "
                               f"over its mouth chord, layer "
                               f"{'none' if lay is None else lay}) — {res} ({uid}) "
                               f"stands over its carriageway with {base:.1f} m of "
                               f"clear space beneath and no pack part at grade: the "
                               f"tag is the road's passage under it, not a terrain "
                               f"tunnel (§34 (12) (5), owner RULINGS 2026-10-10q, "
                               f"#710)")
        # (d) INSIDE THE FENCE THE TAG IS NOT ITS OWN WITNESS (owner RULINGS
        # 2026-10-28p (4), Q243 "a", #1338): pavement painted over a tagged
        # tunnel — the classified cover less its ROOFED half (a pad) — and
        # the tag's own ``layer`` do not show it; it needs one of 27z's
        # witnesses (``fence_witness``)
        tagged_in_fence = fence is not None and _osm_tunnel(bore, tn.admitted_values) \
            and fence.covers(ln)
        # INSIDE A PACK BUILDING'S FOOTPRINT THE BUILDING IS THE COVER (owner
        # RULINGS 2026-10-28q (3), Q249 "a", #1338): a road mapped across a
        # fenced tagged bore there, and the building over it, show no tunnel —
        # every witness that reads what stands over the bore reads it OUTSIDE
        # the pack's footprints (NZWN: the multi-storey car park's own decks
        # crossed its layer -1 ground floor)
        inside = pack_bldg.cover_on(ln) if tagged_in_fence else None
        open_ln = ln if inside is None else ln.difference(inside)
        roofed = on_field.roofed_run_m(open_ln) if tagged_in_fence and \
            hasattr(on_field, "roofed_run_m") and not open_ln.is_empty else 0.0
        if cover >= tn.terrain_cover_min_m and (
                not tagged_in_fence or roofed >= tn.terrain_cover_min_m):
            return True, (f"under the classified cover for {cover:.1f} m"
                          + (f" ({roofed:.1f} m roofed)" if tagged_in_fence else ""))
        if below and not tagged_in_fence:
            return True, f"the bore carries layer {lay}"
        crossed = _crossings(ln, grade, grade_tree, bore, tn.terrain_crossing_min_m,
                             inside)
        if crossed:
            return True, ("under " + ", ".join(crossed[:3]) + " at grade")
        if rise is not None and rise >= tn.terrain_rise_m:
            return True, f"the ground over it stands {rise:+.2f} m above its mouth chord"
        if tagged_in_fence:
            seen = fenced(bore, inside)
            if seen:
                return True, (f"an OSM tunnel inside the airport boundary, "
                              f"witnessed by {seen} (§34 (12) (5) (d), owner "
                              f"RULINGS 2026-10-27z)")
            return False, (f"bore {ids} IS TAGGED A TUNNEL INSIDE THE AIRPORT "
                           f"BOUNDARY WITH NO WITNESS ({ln.length:.0f} m; cover "
                           f"{cover:.1f} m and layer "
                           f"{'none' if lay is None else lay} are the tag's own, "
                           f"28p (4); ground "
                           f"{'unreadable' if rise is None else f'{rise:+.2f} m'} "
                           f"over its mouth chord, no level sign on a road joined "
                           f"at a mouth, no pack portal, nothing crossing over "
                           f"it, no lidar cut) — the road stays at grade (§34 "
                           f"(12) (5) (d), owner RULINGS 2026-10-27z, #535)")
        return False, (f"bore {ids} PASSES UNDER NOTHING AT GRADE "
                       f"({ln.length:.0f} m; cover {cover:.1f} m, no road or railway "
                       f"across it, ground "
                       f"{'unreadable' if rise is None else f'{rise:+.2f} m'} over its "
                       f"mouth chord, layer {'none' if lay is None else lay}) — the sim's "
                       f"elevated roads carry it (§34 (12) (5) (c))")

    return witness


class _PackBuildings:
    """§34 (12) (5) (a) EXTENDED TO THE PACK (owner RULINGS 2026-09-27a
    (3), ratifying Q-12b; lane ``tunnelwitness2``): the pack's BUILDING
    footprints a bore's mapped end may stand inside.

    THE UNIT OUTLINE FROM THE PLAN: the footprint rings of the load
    partition's parts (``Part.rings`` — the same outlines §16g's clusters
    and pads are made of), kept where the part is a BUILDING there:

    * its solid rises ``[placement] chain_min_height_m`` or more above the
      object's zero (``base_y + height_m``) — §16g (10) (4)'s own number
      for a WALLED body, read here as how far the building stands over the
      ground at the end.  A per-body "walled" test cannot be used: OTHH's
      multi-storey car park ``OTHH_Terminal_Parking_000`` is stacked 0.67 m
      floor slabs (base 0.52 / 3.45 m), every one a LEAF by that test, and
      it is the building Q-12b names.  MEASURED over the OTHH / SPJC / HECA /
      GEML captures: the ends it holds read 4.1 m (the car park) and 6.2 m
      (``OTHH_Emiri_Terminal_17``); the sunk trench / portal geometry the
      real tunnels end in reads 0.8 m (HECA ``concrete_3``, base -1.84) and
      -11 .. -13 m (GEML ``GEML_Misc2``, base -19 / -26);
    * its member is not a DECK by the object stage's own verdict
      (``placement_family.member_is_deck`` — HECA's ``T3_road``): a bore
      under a deck passes under it, it does not enter it;
    * the member is not a pack TUNNEL OBJECT read as a corridor
      (``corridor_objects``, the placement ids of the roofed corridors
      ``build_structures`` hands the field region) and the end does not
      stand in one's footprint (``corridor_prints``): that mouth is the
      object's by §33's precedence (RULINGS 2026-09-05n-3), and its 20 m
      bounding solid (OTHH ``tunnel middle - east``, base -15 m) is the
      tunnel, not a building.

    Line and scatter parts never count.  A caller with no partition (the
    fixtures, ``explain``) refuses nothing here."""

    def __init__(self, airport, law: Law, corridor_prints=(),
                 corridor_objects=()) -> None:
        from shapely.geometry import box
        from shapely.strtree import STRtree
        from ..airport.placement_family import member_is_deck
        self._items: list = []
        part = getattr(airport, "partition", None)
        self._tree = None
        self._corr = None
        if part is None or not getattr(part, "units", ()):
            return
        thr = float(law.tables.structures.placement.chain_min_height_m)
        #: §13 (1)'s own number for an ELEVATED part (``[rebake]
        #: elevated_base_m``): what :meth:`passage` calls clear space
        self._elevated = float(law.tables.structures.rebake.elevated_base_m)
        skip = set(corridor_objects)
        boxes = []
        for u in part.units:
            for m in u.members:
                if getattr(m, "scatter", False) or member_is_deck(m) \
                        or m.id in skip:
                    continue
                for q in m.parts:
                    if q.line or getattr(q, "scatter", False) or not q.rings:
                        continue
                    top = float(q.base_y) + float(getattr(q, "height_m", 0.0))
                    if top < thr:
                        continue
                    # indexed by each RING's own bounds: ``Part.box`` is the
                    # plan box of the solid and a ring can stand past it
                    # (OTHH ``tunnel south west 2``: 16 m beyond, where -5214
                    # ends)
                    for r in q.rings:
                        if len(r) < 3:
                            continue
                        la = [c[0] for c in r]
                        lo = [c[1] for c in r]
                        boxes.append(box(min(la), min(lo), max(la), max(lo)))
                        self._items.append((r, m.resource, u.id, top,
                                            float(q.base_y)))
        if not boxes:
            return
        self._tree = STRtree(boxes)
        self._to_xy, self._to_ll = airport.frame.transformers()
        prints = [p for p in corridor_prints if p is not None and not p.is_empty]
        self._corr = STRtree(prints) if prints else None

    def at(self, xy):
        """``(resource, unit id, top)`` of the tallest pack building whose
        footprint holds the frame point ``xy``, or ``None``."""
        from shapely.geometry import Point, Polygon
        if self._tree is None:
            return None
        pt = Point(xy)
        if self._corr is not None and len(self._corr.query(pt, predicate="intersects")):
            return None
        lat, lon = self._to_ll(*xy)
        best = None
        for j in self._tree.query(Point(lat, lon)):
            r, res, uid, top, _base = self._items[int(j)]
            if best is not None and top <= best[2]:
                continue
            poly = self._footprint(r)
            if poly is not None and poly.contains(pt):
                best = (res, uid, top)
        return best

    def _footprint(self, ring):
        """One indexed ring as a valid frame polygon, or ``None``."""
        from shapely.geometry import Polygon
        try:
            poly = Polygon([self._to_xy(lo, la) for la, lo in ring])
        except (ValueError, TypeError):
            return None
        return poly if poly.is_valid else poly.buffer(0)

    def passage(self, line, width_m: float, cover_min_m: float):
        """§34 (12) (5) (e) THE PACK'S OPEN PASSAGE (owner RULINGS 2026-10-10i
        (1) / 10q, issues #522 / #548): ``(resource, unit id, base)`` of the lowest ELEVATED pack
        building part standing over the bore's CARRIAGEWAY — ``line``
        widened to the road's own ``width_m`` — when NO part at grade
        covers the bore's line for ``cover_min_m``; else ``None``.

        An elevated part (its lowest authored ``y`` above ``[rebake]
        elevated_base_m``) with nothing under it leaves clear space
        beneath: it is not cover, and the road it spans runs at grade.
        MEASURED at KCLT's -11194 (a 9.9 m ``service`` bore, DEM falling
        224.46 -> 223.95 m along it): two roof sheets and a wall of the
        terminal link at 3.1 .. 3.7 m over the carriageway, drawn 0.1 ..
        0.6 m off the mapped line, nothing at grade — and two ramps with
        a trench 9.47 m deep were built there.  SPJC's -5724 has no pack
        part within 60 m and stays (d)'s.  A part AT GRADE over the line
        is cover, and the witnesses of (c) / (d) are asked (the building a
        bore ENDS in is (a)'s)."""
        corridor = line.buffer(width_m / 2.0, cap_style="flat")
        if corridor.is_empty:
            return None
        best = None
        for poly, res, uid, base in self._touching(corridor):
            if base <= self._elevated:
                if line.intersection(poly).length >= cover_min_m:
                    return None                   # a pack part at grade: cover
            elif best is None or base < best[2]:
                best = (res, uid, base)
        return best

    def at_grade_over(self, line, cover_min_m: float):
        """``(resource, unit id)`` of a pack building part AT GRADE (its
        lowest ``y`` at or under ``[rebake] elevated_base_m``) whose
        footprint holds ``cover_min_m`` of the bore's ``line`` — the
        pack's form of (d)'s "anything crossing over the bore" (owner
        RULINGS 2026-10-27z; the cover 10i (1) let (d) stand on) — or
        ``None``."""
        for poly, res, uid, base in self._touching(line):
            if base <= self._elevated and line.intersection(poly).length >= cover_min_m:
                return res, uid
        return None

    def cover_on(self, line):
        """The union of the pack building footprints ``line`` meets, or
        ``None`` (owner RULINGS 2026-10-28q (3): there the building is the
        cover)."""
        from shapely.ops import unary_union
        polys = [poly for poly, _r, _u, _b in self._touching(line)]
        return unary_union(polys) if polys else None

    def _touching(self, geom):
        """``(footprint, resource, unit id, base)`` of every indexed part
        whose footprint meets the frame geometry ``geom``.  The query box
        is read from its BOUNDS, never an ``exterior``: a bore line that
        folds back on itself buffers to a MultiPolygon, which has none
        (#1361, measured at CYYC)."""
        from shapely.geometry import box
        if self._tree is None or geom.is_empty:
            return
        x0, y0, x1, y1 = geom.bounds
        ll = [self._to_ll(x, y) for x, y in ((x0, y0), (x0, y1), (x1, y0), (x1, y1))]
        la, lo = [c[0] for c in ll], [c[1] for c in ll]
        for j in self._tree.query(box(min(la), min(lo), max(la), max(lo))):
            r, res, uid, _top, base = self._items[int(j)]
            poly = self._footprint(r)
            if poly is not None and poly.intersects(geom):
                yield poly, res, uid, base


def _fence_of(airport):
    """The airport boundary (apt.dat row 130) as one polygon — every
    ``boundaries`` entry, holes kept — or ``None`` with none."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys = []
    for b in getattr(airport, "boundaries", ()) or ():
        try:
            p = Polygon(b.outer, list(b.holes))
        except (ValueError, TypeError):
            continue
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty:
            polys.append(p)
    return unary_union(polys) if polys else None


def _osm_tunnel(bore, admitted) -> bool:
    """Every way of the bore chain is a MAPPED ``tunnel`` way — never a
    bore §34 (5) synthesised under an aeroway bridge (``o4_underpass``)."""
    from ..airport.deck_signature import is_tunnel_way
    from .structure_underpass import UNDERPASS_TAG
    return all(is_tunnel_way(w.tags or {}, admitted)
               and UNDERPASS_TAG not in (w.tags or {}) for w in bore.ways)


def _layer_of(tags, default=None):
    try:
        return int(str(tags.get("layer")))
    except (TypeError, ValueError):
        return default


def _layer_of_bore(bore):
    """The bore chain's LOWEST mapped ``layer``, or ``None`` when no way
    carries one (which is not zero — an untagged way makes no statement)."""
    vals = [v for v in (_layer_of(w.tags or {}) for w in bore.ways) if v is not None]
    return min(vals) if vals else None


def stacked_ways(ways, law: Law) -> set[int]:
    """``id`` of every way STACKED with another on one line — several ways
    sharing both end points that never stand further apart than ``[tunnel]
    stacked_spread_frac`` of the shorter one's length are a car park's own
    DECKS, not independent roads crossing a tagged tunnel, and none of them
    is a witness that it exists (owner RULINGS 2026-10-28s (4), Q252 "a",
    #1338; NZWN: the garage's three unclassified ramps across its layer -1
    ground floor).  A way the feeds carry twice — the SAME vertices, read
    in either direction — is one road mapped twice, never two decks
    (MEASURED LFPG: the big- and small-roads feeds both carry -48615 /
    -19838), so each such group is read as one line."""
    from shapely.geometry import LineString, Point
    from shapely.strtree import STRtree
    weld = float(law.tables.emit.identity.weld_spacing_m)
    frac = float(law.tables.structures.tunnel.stacked_spread_frac)
    same: dict[tuple, list] = {}
    for w in ways:
        pts = tuple((round(x, 2), round(y, 2)) for x, y in w.points)
        if len(pts) >= 2:
            same.setdefault(min(pts, pts[::-1]), []).append(w)
    lines = [(LineString(k), grp) for k, grp in same.items()]
    lines = [(ln, grp) for ln, grp in lines if ln.length > 0.0]
    if len(lines) < 2:
        return set()
    starts = STRtree([Point(ln.coords[0]) for ln, _w in lines])
    out: set[int] = set()
    for i, (ln, w) in enumerate(lines):
        a, b = Point(ln.coords[0]), Point(ln.coords[-1])
        for j in starts.query(a.buffer(weld)).tolist() + starts.query(b.buffer(weld)).tolist():
            if j == i:
                continue
            o, og = lines[int(j)]
            oa, ob = Point(o.coords[0]), Point(o.coords[-1])
            ends_meet = (oa.distance(a) <= weld and ob.distance(b) <= weld) or \
                (oa.distance(b) <= weld and ob.distance(a) <= weld)
            if ends_meet and ln.hausdorff_distance(o) <= frac * min(ln.length, o.length):
                out.update(id(x) for x in (*w, *og))
    return out


def _crossings(ln, grade, tree, bore, min_inside_m, inside=None):
    """The mapped at-grade ways crossing the bore's INTERIOR, named.  A
    way meeting it at a mouth is the APPROACH, not a crossing — the same
    distinction §34 (12) (4) draws between a deck over the span and one
    over the approach walk.  A crossing inside ``inside`` (the pack
    buildings' footprints, owner RULINGS 2026-10-28q (3)) is none."""
    from shapely.geometry import Point
    own = {id(w) for w in bore.ways}
    out: list[str] = []
    for j in (tree.query(ln, predicate="intersects") if tree is not None else ()):
        g, w = grade[int(j)]
        if id(w) in own:
            continue
        x = ln.intersection(g)
        if x.is_empty:
            continue
        pieces = list(x.geoms) if hasattr(x, "geoms") else [x]
        for p in pieces:
            if p.geom_type != "Point":
                continue
            s = ln.project(Point(p.coords[0]))
            if inside is not None and inside.intersects(Point(p.coords[0])):
                continue
            if min_inside_m < s < ln.length - min_inside_m:
                t = w.tags or {}
                out.append(f"{w.id}[{t.get('highway') or t.get('railway')}]")
                break
    return sorted(set(out))


def _rise_m(airport, ln):
    """How far the DEM anywhere OVER the bore stands above THE LINE BETWEEN
    ITS TWO MOUTH GROUNDS — the bore's form of §34 (12) (4) (ii).

    Issue #65 (owner RULINGS 2026-09-27a, lane ``tunnelwitness2``): this
    read the rise against the MEAN of the two ends, so a bore under
    ground that merely SLOPES read half its own fall as a hill — SPJC's
    -5724 (DEM 21.97 -> 21.44 m, monotone) came out "+0.27 m", and any
    bore falling 1.0 m or more along a plane passed ``terrain_rise_m``
    0.5 with nothing over it.  The chord between the mouth grounds is the
    ground a trench would follow; only ground standing ABOVE that chord
    is ground the bore passes under."""
    dem = getattr(airport, "dem", None)
    if dem is None or ln.length <= 0.0:
        return None
    n = max(4, int(ln.length // 5.0))
    zs = []
    for i in range(n + 1):
        p = ln.interpolate(ln.length * i / n)
        z = float(dem.z(p.x, p.y))
        if z != z:                                     # NaN: no witness
            return None
        zs.append(z)
    return max(z - (zs[0] + (zs[-1] - zs[0]) * i / n) for i, z in enumerate(zs))


def pad_relief_m(airport: Airport, poly: Polygon) -> float:
    """The DEM relief across a pad's ring (a flat pad is ground; a pad on
    relief is a levelled plane).  ONE implementation, in
    ``airport/skirt.ring_relief_m`` (spec §22 C4).  It lives here, beside
    §34 (12)'s two readings, only for ``structures.py``'s 1,000-line
    budget; ``structures`` re-exports it under its old private name."""
    from ..airport.skirt import ring_relief_m
    return ring_relief_m(lambda x, y: float(airport.dem.z(x, y)), poly.exterior.coords)



def airside_cut_roles(law: Law) -> tuple[str, ...]:
    """§34 (12) (3) THE AIRSIDE ROLE SET A CORRIDOR NEVER CUTS (owner
    RULINGS 2026-09-15f item 1; Fable 2026-09-15i).

    Every AIRSIDE role that carries a surface of its own — the runway
    family, the parallels, the stubs, the cross-connectors, the junctions
    and the aprons — read from ``precedence.toml`` (``side = "airside"``,
    ``value = true``, not a structure), never typed out here.  Before
    §34 (12) only the runway family was exempt from a corridor cut
    (08-07 ruling 4), so VMMC's seafront car-park bore knifed code-E
    junction ``pav5`` into six faces at 3.58–4.50 m against the 6.10 m
    field.  ``ramp_cuts_runway_family = false`` keeps its name and its
    value; what widened is the population it protects.

    The PAD (``building``) is deliberately NOT here: a pad is protected by
    ``tunnel.ramp_crosses_pad``, which STOPS the ramp at the pad's edge
    rather than refusing the corridor, and that machinery
    (``structure_geometry.pad_hit``) is unchanged."""
    return tuple(r for r in law.tables.precedence.roles
                 if role_side(law, r) == "airside" and is_value_role(law, r)
                 and not is_structure_role(law, r) and r != "building")


def deck_witness_for(airport, law: Law, under_ways):
    """§34 (12) (4) AS RULED (owner RULINGS 2026-09-15ap): the witness
    ``f(deck_way, deck_polygon, covered_end) -> (tag, cut_m, severs)``
    one corridor's decks are weighed with.

    ``under_ways`` are the corridor's OWN ways — its mapped ``tunnel=yes``
    bore chain.

    **WITNESS (i) READS THE CORRIDOR, NOT THE SPAN** (§34 (12) (4)
    AMENDED (2); owner RULINGS 2026-09-16f).  It asks whether ANY way of
    the bore chain the deck crosses carries ``tunnel=yes`` or
    ``layer <= -1``.  The owner checked the two decks the span reading
    dropped — shape 981 = ``bridge_deck:-5305`` at 40.4788711, -3.5787587
    and shape 988 = ``bridge_deck:-15293`` at 40.4659974, -3.5811339 —
    and both span REAL CUTS; the DEM witness read -0.57 / -1.46 m there
    against sloping abutments, and (i) as written asked the untagged
    approach the span happens to stand over.  The narrowness existed ONLY
    to keep VMMC's seafront decks out, and §34 (12) (5) now keeps the
    seafront bores themselves out: at VMMC no OSM car-park bore is built,
    so no deck of one can be weighed.  Witness (ii) reads the
    production DEM — the SAME sampler the structures run reads — under the
    span and at the deck's two abutments ``[bridge] deck_abutment_m``
    along the deck each way (the deck end where it is shorter), and asks
    whether the ground under the span is ``deck_cut_witness_m`` below
    their mean.  Either witness severs; neither, and the deck stands over
    ordinary ground beyond the trench (§34.5 (6)).

    A tag absent because the road feed predates the 2026-09-15 tag schema
    is neither yes nor no, and needs no special case: (i) is simply not
    satisfied and (ii) decides alone, which is what the ruling says.
    """
    from shapely.geometry import LineString, Point
    from shapely.ops import nearest_points
    br = law.tables.structures.bridge
    reach, floor = br.deck_abutment_m, br.deck_cut_witness_m
    lines = [(LineString(w.points), w) for w in under_ways
             if len(getattr(w, "points", ()) or ()) >= 2]

    def _tag_of(w) -> str | None:
        tags = w.tags or {}
        if str(tags.get("tunnel", "")).lower() in ("yes", "building_passage",
                                                   "covered"):
            return "tunnel=yes"
        try:
            if int(str(tags.get("layer"))) <= -1:
                return f"layer={tags.get('layer')}"
        except (TypeError, ValueError):
            pass
        return None

    # §34 (12) (4) AMENDED (2): the CORRIDOR's witness, taken ONCE per
    # corridor rather than per span — the chain is the same for every
    # deck this corridor is weighed against.
    chain_tag = next((t for t in (_tag_of(w) for _ln, w in lines) if t), None)

    def witness(deck_way, dpoly, _covered_end):
        tag = chain_tag
        cut = None
        pts = list(getattr(deck_way, "points", ()) or ())
        if len(pts) >= 2 and lines:
            deck = LineString(pts)
            near = min((ln for ln, _w in lines), key=lambda b: b.distance(deck))
            on_deck, _on = nearest_points(deck, near)
            st = deck.project(on_deck)
            a, b = max(0.0, st - reach), min(deck.length, st + reach)
            z = [float(airport.dem.z(p.x, p.y)) for p in
                 (deck.interpolate(st), deck.interpolate(a), deck.interpolate(b))]
            if all(v == v for v in z):                    # no NaN
                cut = (z[1] + z[2]) / 2.0 - z[0]
        return tag, cut, bool(tag) or (cut is not None and cut >= floor)

    return witness


#: §33 (6) B AMENDED (3) (c): the CUT-LINE kinds that are SURFACE ELEMENTS
#: — the taxi centreline network and the road centrelines.  A
#: ``runway_profile`` line is not among them: a runway is never cut by a
#: corridor (the knife's 08-07 ruling 4 exemption), so trimming its axis
#: would state a law nothing else states.
SURFACE_LINE_KINDS: tuple[str, ...] = ("taxi_centerline", "road_centerline")


def knee_nodes(cut_lines, chords, grid: float) -> list:
    """EVERY PROFILE KNEE IS A VERTEX ON EVERY EDGE THAT CROSSES IT (spec
    §34 (7): a ramp's emitted cross-chords stand "only where the route
    bends or the profile breaks" — so each one IS a break of the designed
    surface across the ramp's whole width).

    ``chords`` are the ramps' emitted cross-chords (left ring vertex ->
    right ring vertex, one per kept station).  A surface line (a road or
    taxi centreline) the arrangement nodes LENGTHWISE through a ramp
    splits its face in two, and the shared edge carried no vertex where
    the profile breaks: its level ran straight from one end of the ramp to
    the other while both outer edges followed the knee (measured at OTHH's
    corridor under the terminal, issue #449: the centre 0.87 m over the
    edges at the flat -> climb knee).  The line now carries a point where
    it crosses each cross-chord, so the split faces share the knee."""
    chords = [c for c in chords if c is not None and not c.is_empty]
    if not chords:
        return list(cut_lines)
    tree = shapely.STRtree(chords)
    out: list = []
    for cl in cut_lines:
        if cl.kind not in SURFACE_LINE_KINDS or len(cl.points) < 2:
            out.append(cl)
            continue
        ln = LineString(cl.points)
        at = [ln.project(pt) for j in tree.query(ln, predicate="intersects")
              for pt in shapely.get_parts(ln.intersection(chords[int(j)]))
              if pt.geom_type == "Point"]
        if not at:
            out.append(cl)
            continue
        own = [0.0]
        for a, b in zip(cl.points[:-1], cl.points[1:]):
            own.append(own[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        pts = list(zip(own, cl.points))
        for d in sorted(at):
            if all(abs(d - o) > grid for o, _p in pts):
                q = ln.interpolate(d)
                pts.append((d, (float(q.x), float(q.y))))
        pts.sort(key=lambda t: t[0])
        out.append(type(cl)(cl.kind, cl.ref, tuple(p for _d, p in pts), cl.code_letter))
    return out


def decked_exclusion(cut_lines, tunnels, footprints, cells, polys, cut_roles,
                     grid: float, stats):
    """§33 (6) B AMENDED (3) (c) SURFACE ELEMENTS OVER AN OBJECT-DECKED
    TRENCH RIDE THE OBJECT (owner RULINGS 2026-09-15br) — the
    classification's cut lines with every piece INSIDE an object-decked
    outline removed, plus the report of what each outline excluded.

    The OBJECT-DECKED outlines are picked out of ``tunnels`` /
    ``footprints`` here: a tunnel whose id starts with
    ``structure_geometry.OBJECT_CUT_PREFIX`` IS a signature-B shell, and a
    signature-B shell is admitted only WITH its flush ``HARD_DECK`` cover
    (``airport/object_cut.py``), so "the object provides a hard deck"
    (owner 15br) is exactly that test — no second spelling of the
    signature.  Returns the trimmed cut lines and writes its own report
    into ``stats`` (``StructureStats.decked_*``).

    THE MECHANISM THIS REMOVES is the one RULINGS 2026-09-15bp attributed
    at VHHH: ``TUNNEL2_DONE`` runs 1,110 m LENGTHWISE under the taxiway
    system, the taxiway's painted centreline crosses its trench, the
    arrangement nodes that centreline straight through the trench rings,
    and ``constraints/taxi.taxi_centerlines`` then prices an edge from an
    AIRSIDE vertex to a FLOOR-RING vertex pinned at the authored floor
    (``tunnel.object.mouth_depth = floor_slab``).  The taxi network
    propagated that seed to 525 of 1,079 airside vertices within 200 m,
    worst −6.460 m — and no wall can touch it, because the row does not
    care where the wall stands.  The ruling's cure is that the centreline
    ENDS AT THE RIM on each side: the object's deck carries the pavement
    over the trench, so the terrain solve never sees it.

    ONE derivation, not a veto per consumer (RULINGS 2026-08-30l): every
    reader downstream — ``constraints/taxi.taxi_centerlines``,
    ``constraints.stretches``, ``constraints.routes``,
    ``constraints/transverse.axes``, ``constraints/apron``'s spine
    proximity read, ``solve/design``'s taxi profile,
    ``planar/shapes``'s stations — reads the breaklines the map holds,
    and the map holds what these lines make.

    The PAVEMENT limb of (3) (c) needs no edit and is MEASURED here
    instead: ``build_structures``'s knife already takes every
    non-runway-family airside cell's area inside the footprint, so the
    ``pavement_m2`` reported per outline is what it takes.  A
    RUNWAY-family cell is exempt from that knife (08-07 ruling 4) and is
    NAMED rather than silently cut."""
    from shapely.ops import unary_union as _u
    from .structure_geometry import OBJECT_CUT_PREFIX
    pairs = [(t.id, f) for t, f in zip(tunnels, footprints)
             if str(t.id).startswith(OBJECT_CUT_PREFIX)]
    if not pairs:
        return list(cut_lines)
    outlines = [f for _ref, f in pairs]
    region = _u(list(outlines))
    per: list[dict] = []
    pav_total = 0.0
    for ref, outline in pairs:
        pav = 0.0
        for c, p in zip(cells, polys):
            if c.role not in cut_roles or not p.intersects(outline):
                continue
            a = p.intersection(outline).area
            if a <= 0.0:
                continue
            if c.role in _RUNWAY_FAMILY:
                stats.decked_runway_family.append(
                    f"{ref}: runway-family cell {c.role}/{c.ref} stands {a:,.0f} m2 inside "
                    f"the outline — the knife's 08-07 ruling 4 exemption, NOT cut")
                continue
            pav += a
        pav_total += pav
        per.append({"ref": ref, "open_m2": float(outline.area), "pavement_m2": float(pav),
                    "centreline_m": 0.0, "road_m": 0.0})
    out: list = []
    cl_m = rd_m = 0.0
    for cl in cut_lines:
        if cl.kind not in SURFACE_LINE_KINDS or len(cl.points) < 2:
            out.append(cl)
            continue
        ln = LineString(cl.points)
        if not ln.intersects(region):
            out.append(cl)
            continue
        inside = ln.intersection(region).length
        if cl.kind == "taxi_centerline":
            cl_m += inside
        else:
            rd_m += inside
        for entry, outline in zip(per, outlines):
            d = ln.intersection(outline).length
            if d > 0.0:
                entry["centreline_m" if cl.kind == "taxi_centerline" else "road_m"] += float(d)
        rest = ln.difference(region)
        for g in getattr(rest, "geoms", [rest]):
            if g.geom_type != "LineString" or g.length < grid or len(g.coords) < 2:
                continue
            out.append(type(cl)(cl.kind, cl.ref,
                                tuple((float(x), float(y)) for x, y in g.coords),
                                cl.code_letter))
    stats.decked_outlines = len(outlines)
    stats.decked_centreline_m = float(cl_m)
    stats.decked_road_m = float(rd_m)
    stats.decked_pavement_m2 = float(pav_total)
    for e in per:
        stats.decked_excluded.append(
            f"{e['ref']}: an OPEN object-decked trench of {e['open_m2']:,.0f} m2 — the surface "
            f"elements over it RIDE THE OBJECT and are excluded from the terrain solve "
            f"(§33 (6) B AMENDED (3) (c)): pavement {e['pavement_m2']:,.0f} m2 cut, taxi "
            f"centreline {e['centreline_m']:,.1f} m and road centreline {e['road_m']:,.1f} m "
            f"trimmed at the rim")
    return out


def owner_kept(cell: tuple, tunnels, keep) -> bool:
    """Whether a pending structure cell's owning tunnel survived the
    overlap refusals — MOVED VERBATIM from ``planar/structures.py`` (that
    file stands at its 1,000-line budget, ``tests/auto_patch_v2/
    test_planar.py::test_import_and_budget``); no behaviour moved."""
    ids = {t.id for t, k in zip(tunnels, keep) if k}
    return cell[3] in ids


def parts(geom) -> list[Polygon]:
    """The non-degenerate polygon parts of ``geom`` — MOVED VERBATIM from
    ``planar/structures.py`` for the same budget reason."""
    import shapely
    if geom is None or geom.is_empty:
        return []
    return [g for g in shapely.get_parts(geom) if g.geom_type == "Polygon" and g.area > 1e-6]


#: the two roles the knife never cuts (08-07 ruling 4) — stated once here
#: for :func:`decked_exclusion`'s report; ``planar/structures`` keeps its
#: own ``RUNWAY_FAMILY`` for the knife itself.
_RUNWAY_FAMILY = ("runway", "runway_crossing")
