"""§34 (12) THE TWO DERIVATIONS A CORRIDOR IS JUDGED BY (owner RULINGS
2026-09-15f item 1; Fable 2026-09-15i; spec §34 (12)) — lane
`v2vmmcshore`.

Two readings, both pure functions of the law and the classification, and
both used at exactly one site in :mod:`auto_patch_v2.planar.structures`:

* :func:`airside_cut_roles` — clause (3)'s protected set: the airside
  roles a corridor may never cut;
* :func:`airside_stops` — the faces of that set ONE corridor must stop
  short of, its own decked and mouth-standing pavement excluded.

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

import typing as _t

from shapely.geometry import LineString, Polygon

from ..law import Law
from ..law.tables import is_structure_role, is_value_role, role_side
from .structure_approach import under_cover

__all__ = ["airside_cut_roles", "airside_stops", "deck_witness_for",
           "osm_stops", "pad_relief_m", "terrain_tunnel_witness"]


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
    own ramp — the object or the sim carries it — and is NOT built.
    (b) A mapped bridge / overpass / ramp over ordinary ground is the
    SIM'S ELEVATED ROAD: it is not a crossing at grade, so it is no
    witness at all here (and §34 (12) (4) already withholds its deck).
    (c) A TERRAIN TUNNEL passes UNDER something at grade, by any of four
    witnesses — the classified cover (pavement, a pad, a roofed
    corridor's footprint) for ``terrain_cover_min_m``; a mapped road or
    railway AT GRADE crossing the bore's INTERIOR; the DEM standing
    ``terrain_rise_m`` over the bore above the mean at its own two ends;
    or the bore's own ``layer`` at or under ``terrain_layer_max``, which
    is OSM's statement that it runs below what it crosses.

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
    grade_tree = STRtree([ln for ln, _w in grade]) if grade else None

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
        cover = on_field.cover_run_m(ln) if on_field is not None else 0.0
        if cover >= tn.terrain_cover_min_m:
            return True, f"under the classified cover for {cover:.1f} m"
        lay = _layer_of_bore(bore)
        if lay is not None and lay <= tn.terrain_layer_max:
            return True, f"the bore carries layer {lay}"
        crossed = _crossings(ln, grade, grade_tree, bore, tn.terrain_crossing_min_m)
        if crossed:
            return True, ("under " + ", ".join(crossed[:3]) + " at grade")
        rise = _rise_m(airport, ln)
        if rise is not None and rise >= tn.terrain_rise_m:
            return True, f"the ground over it stands {rise:+.2f} m above its own ends"
        return False, (f"bore {ids} PASSES UNDER NOTHING AT GRADE "
                       f"({ln.length:.0f} m; cover {cover:.1f} m, no road or railway "
                       f"across it, ground "
                       f"{'unreadable' if rise is None else f'{rise:+.2f} m'} over its "
                       f"own ends, layer {'none' if lay is None else lay}) — the sim's "
                       f"elevated roads carry it (§34 (12) (5) (c))")

    return witness


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


def _crossings(ln, grade, tree, bore, min_inside_m):
    """The mapped at-grade ways crossing the bore's INTERIOR, named.  A
    way meeting it at a mouth is the APPROACH, not a crossing — the same
    distinction §34 (12) (4) draws between a deck over the span and one
    over the approach walk."""
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
            if min_inside_m < s < ln.length - min_inside_m:
                t = w.tags or {}
                out.append(f"{w.id}[{t.get('highway') or t.get('railway')}]")
                break
    return sorted(set(out))


def _rise_m(airport, ln):
    """How far the DEM anywhere OVER the bore stands above the mean of the
    DEM at its two mapped ends — the bore's form of §34 (12) (4) (ii)."""
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
    return max(zs) - (zs[0] + zs[-1]) / 2.0


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


def airside_stops(cells, polys, cut_roles, decked, mouth_pts, grid: float):
    """§34 (12) (3) A CORRIDOR NEVER CUTS AIRSIDE PAVEMENT — the faces one
    corridor must STOP SHORT of, as ``[(polygon, ref)]`` for
    ``structure_geometry.pad_hit`` (owner RULINGS 2026-09-15f item 1 as
    AMENDED, Fable 2026-09-15; RULINGS 2026-09-15w).

    IT STOPS SHORT, IT IS NOT REFUSED.  The ruling's own words: "it
    becomes an underpass where the pavement is authored as a deck or a
    pack corridor covers it, otherwise it STOPS SHORT of the pavement —
    at VMMC the OSM car-park bore stops at pav5".  The stop is the
    existing station-truncation loop in ``structures.build_structures``,
    the same one ``ramp_crosses_pad`` has always used; a corridor with no
    room left refuses there, by that loop's own message.

    TWO EXCLUSIONS, both the ruling's.  ``decked`` are this corridor's own
    deck polygons — "the pavement is the DECK of an underpass (§34 (5))"
    — so every §34 (5) underpass, LEMD F-6 and KCLT taxiway U, is
    untouched.  And the pavement the corridor's own MOUTH stands on is
    not a cut: (3) is about a bore that CROSSES a pavement, and a
    corridor whose mouth stands on an apron does not cross it, it ENDS in
    it — that is what a portal is, and 08-07 ruling 4's cut is how the
    portal is opened.

    THE CALLER SCOPES IT TO OSM-DERIVED CORRIDORS.  A PACK-STATED
    corridor (§33 (6) signatures A/B/C — ``tunnel_objects``, wall
    corridors, plates) is authored geometry and its crossing of airside
    IS an underpass by authorship: measured at OTHH, applying (3) to them
    refused three terminal tunnels (``tunnel middle - east`` / ``- west``,
    ``tunnel south west 2``) against aprons ``pav32`` / ``pav30``.
    """
    from shapely.ops import unary_union
    keep = unary_union(list(decked)) if decked else None
    out = []
    for p, c in zip(polys, cells):
        if c.role not in cut_roles or c.kind == "structure":
            continue
        if any(p.dwithin(q, grid) for q in mouth_pts):
            continue                      # the portal's own pavement
        if keep is not None and p.within(keep.buffer(grid)):
            continue                      # this corridor's own deck
        out.append((p, c.ref))
    return out


def osm_stops(corridor, group, cells, polys, pads, pad_tree, cut_roles,
              deck_ivals, obj_ivals, grid: float, wall_kind: str):
    """``(stops, tree)`` for ``structure_geometry.pad_hit`` — what ONE
    corridor's ramp must stop short of (§34 (12) (3) as amended).

    A PACK-STATED corridor (``corridor is not None``) or a wall corridor
    keeps the building pads alone, exactly as before: it is authored
    geometry and its crossing of airside IS an underpass by authorship
    (measured at OTHH — bound by (3) it refused three terminal tunnels
    against aprons ``pav32`` / ``pav30``).  An OSM-derived corridor adds
    :func:`airside_stops`.
    """
    from shapely.geometry import Point
    from shapely.strtree import STRtree
    if corridor is not None or group.kind == wall_kind:
        return pads, pad_tree
    stops = pads + airside_stops(
        cells, polys, cut_roles,
        [d[3] for d in deck_ivals] + [d[3] for d in obj_ivals],
        [Point(m.xy) for m in (group.members or ())] or [Point(group.mouth)],
        grid)
    return stops, (STRtree([p for p, _r in stops]) if stops else None)


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
