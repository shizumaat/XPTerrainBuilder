"""§37 (6) THE ROAD RAMP'S ROWS (Fable 2026-09-13; owner RULINGS
2026-09-13j item 5, ruled 2026-09-13aj).

The DERIVATION is ``airport/road_ramp.py`` — it reads the DEM along the
road's own route, which is an M1 producer's job (M0 §1: a constraints
module imports ``law`` and ``model`` only) — and the pipeline publishes it
as ``PlanarMap.road_ramp_z``.  THIS module is the generator: one DESIGN
TARGET per governed vertex at the design-target weight (``[design] law``,
the weight every law row is priced at) and one HARD CEILING a
``[cockpit] visual_m`` above it, so smoothness can never lift the road
back onto the airside fill — the mechanism 13aj measured holding KCLT's
``dsf:pol51`` +9.71 m above its own ``preferred_road_z`` target with NO
row binding it.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..geom.ramp_grade import built_grade, least_grade
from ..law import Law
from ..law.tables import family, role_cap
from ..model.airport import Airport
from ..model.constraints import Band, ConstraintSet, Linear, Pin, Row, Source
from ..model.planar import PlanarMap

__all__ = ["GEN", "RULING", "RULING_CEILING", "JOIN_RULING",
           "CONTACT_RULING", "road_ramp_rows", "road_join_rows",
           "road_contact_rows", "reach_seed_rewrite", "BANK_RULING",
           "between_levels_rewrite", "airside_joins", "welded_join_release",
           "terrace_rewrite", "terrace_profile", "wall_terrace_rows",
           "wall_release",
           "WALL_LOT_RULING"]

GEN = "road_ramp"
#: The ruling HEAD of the DESIGN TARGET (everything before the first
#: parenthesis is what ``solve.design.ruling_head`` reads).
RULING = ("roads.groundside_road ramp to the DEM "
          "(owner 2026-09-13j item 5; spec §37 (6))")
#: The ruling HEAD of the HARD CEILING — registered in ``[design]
#: hard_rulings``, so the ceiling is a CONSTRAINT of the active set and
#: not one more weight in the contest the objective already won (13aj).
RULING_CEILING = ("roads.groundside_road ramp ceiling "
                  "(owner 2026-09-13j item 5; spec §37 (6))")
#: §37 (9) THE COVERAGE-EDGE JOIN's ruling head (owner RULINGS
#: 2026-09-13be): the patch's road takes the CORE ribbon's altitude where
#: its way leaves the coverage — an EQUALITY, because the two surfaces are
#: one road and the pilot drives across the join.
JOIN_RULING = ("roads.coverage_edge join "
               "(owner 2026-09-13be; spec §37 (9))")
#: §37 (10) (1) THE AIRSIDE CONTACT WITHIN REACH (owner RULINGS
#: 2026-09-13cs item 5): a ONE-WAY hard ceiling against the airside
#: edge's OWN columns — the road ramps away from the level the solve
#: gives that face, and never pulls it (airside is king).
CONTACT_RULING = ("roads.groundside_road airside contact "
                  "(owner 2026-09-13cs item 5; spec §37 (10))")


def _run_grade(level: float, ends: _t.Iterable[tuple[float, float]],
               design: float, cap: float, lane: float) -> float:
    """THE GRADE A STAGE-2 RAMP IS BUILT AT (owner RULINGS 2026-10-09c
    (2b); ``geom/ramp_grade``): ``ends`` is ``(distance from the level the
    road leaves, the level that stands there)`` at each END of its run.
    The design grade, unless the road would then stand off one of them —
    then the smallest grade that brings it to every end, and the cap where
    even the cap does not.  An end inside one lane width asks nothing."""
    need = max((least_grade([(d, t - level)]) or 0.0 for d, t in ends if d >= lane),
               default=0.0)
    return built_grade(need, design, cap) or cap


def _far_end(run: _t.Sequence[tuple[float, float]], lane: float
             ) -> list[tuple[float, float]]:
    """The END of a run of ``(distance, level)``: the vertices within one
    lane width of the farthest."""
    far = max((d for d, _l in run), default=0.0)
    return [(d, t) for d, t in run if d >= far - lane]


def road_ramp_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """The DESIGN TARGET (a one-vertex equality, priced at ``[design] law``
    with every other law row) and the HARD CEILING (a ``Band`` at
    ``target + [cockpit] visual_m``, hard through ``[design]
    hard_rulings``) for every groundside-road vertex §37 (6) governs.

    Reads ``PlanarMap.road_ramp_z`` — the channel :func:`with_road_ramp`
    publishes in the pipeline's target-channel order.  A map without it
    (an older capture, a probe that skipped the publisher) mints NOTHING,
    exactly as the taxi and apron trends do: the derivation has one site.
    """
    targets = getattr(planar, "road_ramp_z", None) or {}
    if not targets:
        return []
    vis = float(law.tables.emit.cockpit.visual_m)
    rows: list[Row] = []
    for v in sorted(targets):
        t = float(targets[v])
        ref = next((planar.faces[f].ref for f in planar.vertices[v].incident_faces
                    if planar.faces[f].ref), "")
        src = Source(GEN, RULING, (f"vertex:{v}", ref))
        rows.append(Linear(((v, 1.0),), t, t, src))
        rows.append(Band(v, None, t + vis,
                         Source(GEN, RULING_CEILING, (f"vertex:{v}", ref))))
    return rows


def road_contact_rows(planar: PlanarMap, law: Law, airport: Airport
                      ) -> list[Row]:
    """§37 (10) (1): for every road vertex whose route END contacts an
    airside face within ``[road_contact] contact_reach_m``, ONE row

        ``z[v] - (1-u)·z[a] - u·z[b] <= cap · s``

    — the road stands at most its own longitudinal cap above the AIRSIDE
    EDGE's own level after ``s`` metres of route from the contact.  At the
    contact itself (``s = 0``) that is the airside's level exactly.

    ONE-WAY (``follows=(v,)``, the ruling registered in ``[design]
    one_way_rulings``): the road vertex keeps its column, the two airside
    vertices enter the right-hand side lagged, so a road can never lift or
    sink the pavement it meets — AIRSIDE IS KING.

    NOT HARD, and the reason is MEASURED, not preference: ``solve/design``
    carries ONE ``shift`` vector, and the augmented Lagrangian's
    ``shift[hard_i] = mu / rho`` OVERWRITES the one-way lag of any row
    that is in both registers — the row then reads ``z[v] <= cap·s -
    mu/rho`` with its leaders GONE.  Registered in both, this row drove
    HECA's roads to ``z - DEM = -108 m`` and minted 63,170 within-shape
    rows (arm 2).  It is priced at the law weight with every other law
    row; the §37 (6) ramp ceiling above it stays the hard one.

    Reads ``PlanarMap.road_contact_edge``; a map without the channel mints
    nothing (the derivation has one site)."""
    edges = getattr(planar, "road_contact_edge", None) or {}
    if not edges:
        return []
    roles = family(law, "road_cross_section").roles
    caps = [role_cap(law, r).longitudinal for r in roles if role_cap(law, r)]
    if not caps:
        return []
    cap = min(caps)
    rows: list[Row] = []
    for v in sorted(edges):
        a, b, u, s = edges[v]
        ref = next((planar.faces[f].ref for f in planar.vertices[v].incident_faces
                    if planar.faces[f].ref), "")
        rows.append(Linear(((v, 1.0), (a, -(1.0 - u)), (b, -u)),
                           None, cap * float(s),
                           Source(GEN, CONTACT_RULING, (f"vertex:{v}", ref)),
                           follows=(v,)))
    return rows


#: OWNER RULINGS 2026-10-03c (#291): the LOT AT A WALL'S FOOT follows its
#: building's pad — registered in ``[design] one_way_rulings`` (the lot
#: vertex follows, the pad leads: the lot never lifts or sinks the pad).
WALL_LOT_RULING = ("structures.wall_terrace lot level "
                   "(owner 2026-10-03c; issue #291)")


def wall_terrace_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """OWNER RULINGS 2026-10-03c: per declared wall terrace
    (``PlanarMap.road_terrace['wall']``, derived once by
    ``airport/road_ramp.wall_terraces``), one ONE-WAY row per lot vertex at
    the wall's foot, ``z[lot] - z[pad] = 0`` at the law weight — the lot is
    graded flat to its building's level (the pad leads, ``follows=(lot,)``).
    The lot's and the pad's columns are groundside / pad (stage 2), so the
    row is stage 2's and the airside is untouched.  A map without the
    channel mints nothing."""
    walls = (getattr(planar, "road_terrace", None) or {}).get("wall") or {}
    rows: list[Row] = []
    seen: set[int] = set()
    for k in sorted(walls):
        rec = walls[k]
        for lv, pv in rec.get("pairs") or ():
            if lv in seen:
                continue
            seen.add(lv)
            rows.append(Linear(((int(lv), 1.0), (int(pv), -1.0)), 0.0, 0.0,
                               Source("wall_terrace", WALL_LOT_RULING,
                                      (f"vertex:{lv}", str(rec.get("label", "")))),
                               follows=(int(lv),)))
    return rows


def wall_release(planar: PlanarMap, law: Law, cs: ConstraintSet
                 ) -> tuple[ConstraintSet, dict[str, _t.Any]]:
    """OWNER RULINGS 2026-10-03c (#291): THE WALL IS THE STEP — between
    §20b's stages, every stage-2 pair row (``Diff``, multi-term ``Linear``)
    whose vertices STRADDLE a declared wall terrace's line (two of them on
    either side, the segment between them crossing the wall) is withdrawn:
    the step across the wall is the declared ``wall_terrace`` joint's
    (``pipeline/publication.wall_terrace_joints``), not a grade the road or
    the lot must climb.  Only the wall's own line is read — a row that does
    not cross it is untouched.

    MEASURED HECA arm (sw1018 capture): ``route3``'s kerb is shared with
    lot ``dsf:objpav394`` and ``metal_strip_2.obj`` comp 117 stands 0.8 m
    inside the lot edge; with the terrace target at the apron level
    (104.02 m) the road held at 101.89 m — the road-family longitudinal
    pairs and the lot's within-shape pairs across the wall to lot vertices
    at 100.8 m priced the 3.1 m wall as a grade."""
    walls = (getattr(planar, "road_terrace", None) or {}).get("wall") or {}
    rep: dict[str, _t.Any] = {"walls": len(walls), "released": 0}
    if not walls:
        return cs, rep
    from shapely.geometry import LineString, Point, Polygon
    from shapely.strtree import STRtree
    polys = []
    for _k, r in sorted(walls.items()):
        if len(r.get("line") or ()) >= 4:
            g = Polygon(r["line"])
            polys.append(g if g.is_valid else g.buffer(0.0))
    if not polys:
        return cs, rep
    ltree = STRtree(polys)
    reach = max(max(r["height_m"] for r in walls.values()) * 4.0, 20.0)
    zone = STRtree([g.buffer(reach) for g in polys])
    near = {v for v, vx in planar.vertices.items()
            if len(zone.query(Point(vx.xy), predicate="intersects"))}
    xy = {v: planar.vertices[v].xy for v in near}

    # only a pair with its LOW end on a wall's lot side is the wall's step
    # (a road's own longitudinal chord past a bent wall is not)
    low = {v for r in walls.values() for v in (r.get("lower") or ())}

    def crosses(vs) -> bool:
        vs = [v for v in vs if v in xy]
        for i, a in enumerate(vs):
            for b in vs[i + 1:]:
                if (a in low) == (b in low):
                    continue
                seg = LineString([xy[a], xy[b]])
                if len(ltree.query(seg, predicate="intersects")):
                    return True
        return False
    diffs = []
    for r in cs.diffs:
        if r.a in xy and r.b in xy and crosses((r.a, r.b)):
            rep["released"] += 1
            continue
        diffs.append(r)
    linears = []
    for r in cs.linears:
        vs = [v for v, _c in r.terms]
        if len(vs) >= 2 and sum(v in xy for v in vs) >= 2 and crosses(vs):
            rep["released"] += 1
            continue
        linears.append(r)
    if not rep["released"]:
        return cs, rep
    return _dc.replace(cs, diffs=tuple(diffs), linears=tuple(linears)), rep


def airside_joins(planar: PlanarMap, law: Law) -> frozenset[int]:
    """THE JOINS ON AIRSIDE (lane ``joinyield128``, issue #128 / #143; owner
    RULINGS 2026-09-30be — the apron cap is HARD everywhere — under the free-
    road ruling and airside-is-king: "Why would a road EVER move airside?
    It should be welded to airside"): the §37 (9) join vertices that lie
    on a §20b STAGE-1 (airside pavement) face — on its ring or inside it.

    Such a vertex is AIRSIDE, not road: it takes the airside's solved value
    and the road conforms to it, so it is NOT pinned at the core ribbon's
    level (:func:`road_join_rows` mints no ``Pin`` for it — never in the
    solve, so never in a stage-1 or stage-2 pin yield either).  After the
    solve the pipeline publishes it as a yielded join
    (``emit/road_join.with_pin_yield``'s ``withheld``): the core ribbon
    takes the airside's level there, beyond its budget, like every join
    the ribbon yields (RULINGS 2026-09-27a (10)).

    MEASURED (HECA, capture ``hardhold128``, branch ``rwyband128``): the
    ribbon pinned ``pav37|route3`` v7903 at 99.83 m, 5.62 m over the hard-
    capped apron stage 1 solves there; the stage-1 yield released it to
    94.21 m and stage 2's rewrite (which re-reads the UN-yielded set)
    re-pinned it — a 6.97 m apron|apron cliff at 30.11658, 31.41098."""
    joins = getattr(planar, "road_coverage_join", None) or {}
    if not joins:
        return frozenset()
    from ..law.tables import airside_stage_roles
    air = airside_stage_roles(law)
    return frozenset(
        v for v in joins
        if any(planar.faces[f].role in air
               for f in planar.vertices[v].incident_faces))


def road_join_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """§37 (9): one ``Pin`` per road vertex at a coverage exit, at the core
    ribbon's own altitude just outside (``PlanarMap.road_coverage_join``,
    derived in ``emit/road_join.py``).  A map without the channel mints
    nothing — the derivation has one site.  A join on AIRSIDE
    (:func:`airside_joins`) mints nothing: the airside's value is its."""
    joins = getattr(planar, "road_coverage_join", None) or {}
    rows: list[Row] = []
    held = airside_joins(planar, law)
    for v in sorted(joins):
        if v in held:
            continue
        ref = next((planar.faces[f].ref for f in planar.vertices[v].incident_faces
                    if planar.faces[f].ref), "")
        rows.append(Pin(v, float(joins[v]),
                        Source(GEN, JOIN_RULING, (f"vertex:{v}", ref))))
    return rows


def reach_seed_rewrite(planar: PlanarMap, law: Law, cs: ConstraintSet,
                       levels: _t.Mapping[int, float]
                       ) -> tuple[ConstraintSet, dict[str, _t.Any]]:
    """THE STAGE-2 REWRITE of the groundside road (§20b's
    ``stage2_rewrite``): the reach seed (27a (11), :func:`_reach_seed`)
    and then the between-levels road (29x, :func:`between_levels_rewrite`)
    — both read stage 1's solved airside levels as constants.  The report
    carries the seed's keys and the between-levels report under
    ``between_levels``."""
    cs, rep = _reach_seed(planar, law, cs, levels)
    # 10-03b BEFORE 29x: a ribbon vertex between two pavements at different
    # levels still takes the LOWER one (rule 8 of 30aa: 29x stands)
    cs, rep["terrace"] = terrace_rewrite(planar, law, cs, levels)
    cs, rep["wall_release"] = wall_release(planar, law, cs)
    cs, rep["between_levels"] = between_levels_rewrite(planar, law, cs, levels)
    cs, rep["welded_join"] = welded_join_release(planar, law, cs, levels)
    return cs, rep


def terrace_profile(terrace: _t.Mapping[str, _t.Mapping],
                    levels: _t.Mapping[int, float],
                    floor: _t.Mapping[int, float], cap: float,
                    anchors: _t.Mapping[int, float] | None = None, *,
                    design: float | None = None, lane: float = 0.0
                    ) -> tuple[dict[int, float], dict[str, _t.Any]]:
    """OWNER RULINGS 2026-10-03b: THE RIBBON'S PROFILE, per route, from
    ``PlanarMap.road_terrace`` (``airport/road_ramp.road_terrace``) and
    stage 1's solved levels.

    * a BORDERED vertex (``foot``) takes its foot's level — the pavement it
      runs beside, read as a stage-1 constant (a one-way weld: the pavement
      leads, nothing airside moves);
    * a run between two bordered stations of ONE route — a pad's frontage,
      or a stretch inside the airport between two pavements — runs
      STRAIGHT between their two levels (it never climbs away from the
      pavements it links);
    * a run beyond the LAST bordered station of its route, past any pad
      frontage that continues it (held flat), is BARE: it climbs from that
      level toward its own §37 (6) target ``floor`` (the road exit, 29y /
      10-02v (1)) — ``clip(floor, L - g·d, L + g·d)``, ``g`` the grade the
      exit is BUILT at: ``design`` (``[road_contact] ramp_grade``; ``cap``
      when not given), steepened toward ``cap`` only where the bare run is
      too short for the design grade to reach the road's target by its end,
      and then by the least grade that does (RULINGS 2026-10-09c (2b),
      :func:`_run_grade`);
    * a route with no levelled foot keeps its targets;
    * an ``anchors`` vertex — a §37 (9) COVERAGE-EDGE JOIN, where the core's
      levelled road takes over — is never governed, and every vertex of its
      route reaches it inside ``clip(target, z_a - cap·d, z_a + cap·d)`` —
      AT THE CAP, never the design grade: the clip is two-sided, a pin's
      FEASIBILITY envelope (a road may not stand farther from the join it
      must reach than its cap allows), not a ramp; at the design grade it
      cut a road climbing away from its join on lawful 6-8 % ground down
      to 5 % (spec §37 (6a) (v), RULINGS 2026-10-09d (2); KCLT
      ``road_cross_section`` 767 -> 800).  The join's ramp is the bare
      exit's one-sided run above, its end level the pin.
      MEASURED HECA replay: ``small_roads:-20210`` welded to apron ``pav37``
      at 89.6 m four metres from its join pinned at 96.89 m — a 12.98 m
      hard conflict of the ramp ceiling against the pin).

    Returns ``{v: target}`` for every vertex it governs and the report."""
    foot = terrace.get("foot") or {}
    pad = terrace.get("pad") or {}
    own = terrace.get("own") or {}
    station = terrace.get("station") or {}
    rep: dict[str, _t.Any] = {"bordered": 0, "linked": 0, "pad_held": 0,
                              "bare": 0, "unlevelled": 0, "routes": 0,
                              "max_cut_m": 0.0, "max_link_grade": 0.0,
                              "bare_steepened": 0, "max_bare_grade": 0.0,
                              "bare_runs": 0}
    bare: dict[tuple[int, bool], tuple[float, list[tuple[float, int, float]]]] = {}
    anchors = anchors or {}
    lev: dict[int, float] = {}
    for v, (a, b, u, _ref) in foot.items():
        if a in levels and b in levels:
            lev[v] = (1.0 - u) * float(levels[a]) + u * float(levels[b])
        else:
            rep["unlevelled"] += 1
    by_route: dict[int, list[tuple[float, int]]] = {}
    for v, (r, s_) in station.items():
        by_route.setdefault(int(r), []).append((float(s_), int(v)))
    out: dict[int, float] = {}
    for r, items in sorted(by_route.items()):
        items.sort()
        known = [(s_, lev[v]) for s_, v in items if v in lev]
        if not known:
            continue
        rep["routes"] += 1
        ks = [k[0] for k in known]
        # the pad frontage beyond each end of the levelled stretch, held flat
        lo_s, hi_s = ks[0], ks[-1]
        for s_, v in reversed([it for it in items if it[0] < ks[0]]):
            if v in pad:
                lo_s = s_
            else:
                break
        for s_, v in [it for it in items if it[0] > ks[-1]]:
            if v in pad:
                hi_s = s_
            else:
                break
        import bisect
        for s_, v in items:
            if v in lev:
                out[v] = lev[v]
                rep["bordered"] += 1
                continue
            if v in own and v in pad:
                continue        # #291: a 1206 / DSF road is its pad's frontage
            i = bisect.bisect_left(ks, s_)
            if 0 < i < len(ks):
                (s0, z0), (s1, z1) = known[i - 1], known[i]
                t = (s_ - s0) / (s1 - s0) if s1 > s0 else 0.0
                out[v] = z0 + t * (z1 - z0)
                rep["linked"] += 1
                if s1 > s0:
                    rep["max_link_grade"] = max(rep["max_link_grade"],
                                                abs(z1 - z0) / (s1 - s0))
                continue
            if v in own:
                continue        # #291: a 1206 / DSF road's unbordered run is its own
            z_e = known[0][1] if i == 0 else known[-1][1]
            d = (lo_s - s_) if i == 0 else (s_ - hi_s)
            if d <= 0.0:
                out[v] = z_e
                rep["pad_held"] += 1
                continue
            fl = anchors.get(v, floor.get(v))   # a join's level is its pin's
            if fl is None:
                continue
            bare.setdefault((r, i == 0), (z_e, []))[1].append((d, v, float(fl)))
            rep["bare"] += 1
    g0 = cap if design is None else design
    for _key, (z_e, run) in sorted(bare.items()):
        g = _run_grade(z_e, _far_end([(d, fl) for d, _v, fl in run], lane), g0, cap, lane)
        rep["bare_steepened"] += g > g0 + 1e-9
        rep["bare_runs"] += 1
        rep["max_bare_grade"] = max(rep["max_bare_grade"], g)
        for d, v, fl in run:
            out[v] = min(max(fl, z_e - g * d), z_e + g * d)
    by_anchor: dict[int, list[tuple[float, float]]] = {}
    for v, za in anchors.items():
        if v in station:
            r, s_ = station[v]
            by_anchor.setdefault(int(r), []).append((float(s_), float(za)))
            out.pop(v, None)
    rep["anchored"] = 0
    for v in list(out):
        r, s_ = station[v]
        for sa, za in by_anchor.get(int(r), ()):
            d = abs(float(s_) - sa)
            t = min(max(out[v], za - cap * d), za + cap * d)
            if abs(t - out[v]) > 1e-9:
                out[v] = t
                rep["anchored"] += 1
    for v, t in out.items():
        fl = floor.get(v)
        if fl is not None and float(fl) - t > rep["max_cut_m"]:
            rep["max_cut_m"] = float(fl) - t
    rep["max_cut_m"] = round(rep["max_cut_m"], 3)
    rep["max_link_grade"] = round(rep["max_link_grade"], 4)
    return out, rep


def terrace_rewrite(planar: PlanarMap, law: Law, cs: ConstraintSet,
                    levels: _t.Mapping[int, float]
                    ) -> tuple[ConstraintSet, dict[str, _t.Any]]:
    """OWNER RULINGS 2026-10-03b (#100): THE STAGE-2 REWRITE of a ROAD's
    (ribbon, 1206 corridor, DSF page — #291) §37 (6) DESIGN TARGET and HARD
    CEILING to the terrace profile (:func:`terrace_profile`) — called between §20b's stages with
    ``levels`` = stage 1's solved airside columns, so every bordered level
    is a constant and the rows stay stage 2's: AIRSIDE IS UNTOUCHED BY
    CONSTRUCTION.  The target is the vertex's §37 (6) row (``lo = hi =``
    the profile) and the ceiling ``profile + [cockpit] visual_m`` — the
    ceiling FOLLOWS the target down into the cut, so the terrain is cut to
    the road and the road is never held up the hill by its old ceiling."""
    terr = getattr(planar, "road_terrace", None) or {}
    if not terr or not terr.get("station") or not levels:
        return cs, {"governed": 0}
    roles = family(law, "road_cross_section").roles
    caps = [role_cap(law, r).longitudinal for r in roles if role_cap(law, r)]
    if not caps:
        return cs, {"governed": 0}
    cap = min(caps)
    vis = float(law.tables.emit.cockpit.visual_m)

    def _vertex(src: Source) -> int | None:
        tag = src.inputs[0] if src.inputs else ""
        return int(tag[7:]) if tag.startswith("vertex:") else None

    floor: dict[int, float] = {}
    for r in cs.linears:
        if r.source.generator == GEN and r.source.ruling == RULING:
            v = _vertex(r.source)
            if v is not None and r.hi is not None:
                floor[v] = float(r.hi)
    joins = {p.v: float(p.z) for p in cs.pins
             if p.source.generator == GEN and p.source.ruling == JOIN_RULING}
    # a MEET (``road_terrace``'s ``meet``: the road within a lane width of
    # a groundside lot / pavement page) keeps its own §37 (6) target and anchors
    # the profile like a join — the other road leads there
    for v in terr.get("meet") or {}:
        if v in floor and v not in joins:
            joins[v] = floor[v]
    prof, rep = terrace_profile(
        terr, levels, floor, cap, joins,
        design=float(law.tables.emit.road_contact.ramp_grade),
        lane=float(law.tables.emit.road_profile.lane_width_m))
    # a BAND-KERB vertex (``road_terrace``'s ``kerb``) carries no §37 (6)
    # row — the band leads there — and gets ONE: the terrace level as the
    # same law-weight design target, never a ceiling (the band's own rows
    # stay the hard ones).  A bare kerb has no floor and gets nothing.
    kerb = terr.get("kerb") or {}
    add = {v: z for v, z in prof.items() if v in kerb and v not in floor}
    prof = {v: z for v, z in prof.items() if v in floor}
    rep["governed"] = len(prof) + len(add)
    rep["kerb"] = len(add)
    if not prof and not add:
        return cs, rep
    linears = []
    for r in cs.linears:
        if r.source.generator == GEN and r.source.ruling == RULING:
            v = _vertex(r.source)
            if v in prof:
                r = _dc.replace(r, lo=prof[v], hi=prof[v])
        linears.append(r)
    for v in sorted(add):
        ref = next((planar.faces[f].ref for f in planar.vertices[v].incident_faces
                    if planar.faces[f].role in roles), "")
        linears.append(Linear(((v, 1.0),), add[v], add[v],
                              Source(GEN, RULING, (f"vertex:{v}", ref))))
    bands = []
    for r in cs.bands:
        if r.source.generator == GEN and r.source.ruling == RULING_CEILING:
            v = _vertex(r.source)
            if v in prof and r.hi is not None:
                r = _dc.replace(r, hi=prof[v] + vis)
        bands.append(r)
    return _dc.replace(cs, linears=tuple(linears), bands=tuple(bands)), rep


def welded_join_release(planar: PlanarMap, law: Law, cs: ConstraintSet,
                        levels: _t.Mapping[int, float]
                        ) -> tuple[ConstraintSet, list[dict]]:
    """THE JOIN WELDED TO AIRSIDE YIELDS TO IT (issue #143 item 2, lane
    ``roadrows143``; owner 2026-09-30 Q-97/Q-100 "Why would a road EVER
    move airside? It should be welded to airside and then grading DEM to
    maintain its cap"; RULINGS 2026-09-27a (10), 2026-10-01a).

    Called between §20b's stages with ``levels`` = stage 1's solved
    airside columns.  A road row welded to airside is ONE-WAY on its
    groundside feet (``roads.road_pair_side``) and never reaches stage 1,
    so stage 1 no longer reads — and no longer yields — a §37 (9) join pin
    standing on such a foot.  Stage 2 holds the airside vertex at stage 1's
    value; a join pin there whose own road row cannot hold against that
    constant (``|row| > bound + hard_tol_m`` with the pin at its ribbon
    value) would leave a constant violated row — the road spike lane
    ``joinyield128`` measured at HECA v28332 (ribbon 100.755 m, 5.3 m from
    apron v7898 at 91.98 m).  That pin is RELEASED to a design target at
    its own value (``solve.pin_yield.release_pins``'s form), so the road
    takes its cap FROM the weld; the record joins the solve's
    ``pin_yield`` and the core ribbon yields to the level the patch
    carries (``emit/road_join.with_pin_yield``).  Only rows whose every
    other foot stage 1 levelled are read — a row through a free groundside
    vertex is the road's own grading problem.

    ONE HOP, and the second hop is an OPEN residual: KCLT's coverage edge
    carries join v10783 0.71 m behind the welded join v10782, never welded
    itself, and it still holds the road 0.88 m over the apron 1.4 m away
    (``pavement_over_road_cap`` at 35.204173, -80.939746).  A reach over
    the road's hard pair rows released it but was REFUTED at HECA: it
    walks rows the §5a LP itself relaxes (``road_cross_section`` 1.12 m
    over a 0.04 m bound at v10443|v10444) and released v10705/v10706 that
    were held lawfully (``hard_conflict`` 113 -> 136).

    Returns the rewritten set and one record per released pin
    (``v``, ``pinned_m``, the worst ``excess`` of its welded rows)."""
    joins = {p.v: p for p in cs.pins
             if p.source.generator == GEN and p.source.ruling == JOIN_RULING}
    if not joins or not levels:
        return cs, []
    tol = float(law.tables.emit.design.hard_tol_m)
    worst: dict[int, float] = {}

    def _feet(fv) -> tuple[int, ...]:
        return (int(fv),) if isinstance(fv, int) else tuple(int(v) for v in fv)

    def _check(v: int, others: _t.Iterable[int], miss: float) -> None:
        if all(o in levels for o in others) and miss > tol:
            worst[v] = max(worst.get(v, 0.0), miss)

    for r in cs.diffs:
        fv = getattr(r, "follows", None)
        if fv is None:
            continue
        for v in _feet(fv):
            if v not in joins:
                continue
            other = r.b if r.a == v else r.a
            if other not in levels:
                continue
            za = float(joins[v].z) if r.a == v else float(levels[r.a])
            zb = float(joins[v].z) if r.b == v else float(levels[r.b])
            _check(v, (other,), abs(za - zb) - float(r.cap) * float(r.d))
    for r in cs.linears:
        fv = getattr(r, "follows", None)
        if fv is None:
            continue
        fs = _feet(fv)
        if len(fs) != 1 or fs[0] not in joins:
            continue
        v = fs[0]
        others = [t for t, _c in r.terms if t != v]
        if not others or not all(o in levels for o in others):
            continue
        val = sum(c * (float(joins[v].z) if t == v else float(levels[t]))
                  for t, c in r.terms)
        miss = max((float(r.lo) - val) if r.lo is not None else 0.0,
                   (val - float(r.hi)) if r.hi is not None else 0.0)
        _check(v, others, miss)
    if not worst:
        return cs, []
    keep = []
    targets = []
    for p in cs.pins:
        if p.v in worst and p.v in joins:
            targets.append(Linear(((p.v, 1.0),), float(p.z), float(p.z),
                                  p.source))
        else:
            keep.append(p)
    recs = [{"v": int(v),
             "xy": tuple(float(c) for c in planar.vertices[v].xy),
             "pinned_m": round(float(joins[v].z), 4),
             "z_m": round(float(joins[v].z), 4), "excess_m": 0.0,
             "welded_miss_m": round(m, 4), "stage": "2w"}
            for v, m in sorted(worst.items())]
    return (_dc.replace(cs, pins=tuple(keep),
                        linears=tuple(cs.linears) + tuple(targets)), recs)


def _reach_seed(planar: PlanarMap, law: Law, cs: ConstraintSet,
                levels: _t.Mapping[int, float]
                ) -> tuple[ConstraintSet, dict[str, _t.Any]]:
    """OWNER RULINGS 2026-09-27a (11) (Q-22): A REACH CONTACT WITHIN ONE
    LANE WIDTH SEEDS THE RAMP FROM STAGE 1's SOLVED APRON LEVEL, LIKE A
    TOUCHING ONE.

    Called BETWEEN §20b's two stages (``solve.design.solve_design``'s
    ``stage2_rewrite``), with ``levels`` = stage 1's solved airside
    columns: for every vertex ``PlanarMap.road_reach_seed`` names
    (``(a, b, u, s)``, published by ``airport/road_ramp.with_road_ramp``)
    the seed is ``z_edge - g * s`` with ``z_edge = (1-u)·L[a] + u·L[b]``
    and ``g`` the grade the ramp is BUILT at — the design grade
    ``[road_contact] ramp_grade``, steepened toward the road cap only where
    the vertices that contact governs end before the design grade has come
    down to their own targets (RULINGS 2026-10-09c (2b), :func:`_run_grade`),
    and the vertex's §37 (6) DESIGN TARGET and HARD CEILING (``+ visual_m``)
    are raised to it where it stands above them — ``max(target, seed)``,
    the same higher envelope a touching mouth makes.  Both terms are
    cap-Lipschitz in the route station, so a section still cannot tilt
    (§37 (8)).  A seed whose edge stage 1 did not level is skipped and
    counted.  Returns the rewritten set and the report (``seeded``,
    ``raised``, ``max_raise_m``, ``unlevelled``)."""
    seed = getattr(planar, "road_reach_seed", None) or {}
    rep: dict[str, _t.Any] = {"seeded": len(seed), "raised": 0,
                              "max_raise_m": 0.0, "unlevelled": 0,
                              "worst": None}
    if not seed:
        return cs, rep
    roles = family(law, "road_cross_section").roles
    caps = [role_cap(law, r).longitudinal for r in roles if role_cap(law, r)]
    if not caps:
        return cs, rep
    cap = min(caps)
    vis = float(law.tables.emit.cockpit.visual_m)

    def _vertex(src: Source) -> int | None:
        tag = src.inputs[0] if src.inputs else ""
        return int(tag[7:]) if tag.startswith("vertex:") else None

    target = {_vertex(r.source): float(r.hi) for r in cs.linears
              if r.source.generator == GEN and r.source.ruling == RULING}
    runs: dict[tuple, list[tuple[float, int]]] = {}
    for v, (a, b, u, s) in seed.items():
        if a not in levels or b not in levels:
            rep["unlevelled"] += 1
            continue
        runs.setdefault((a, b, u), []).append((float(s), v))
    design = float(law.tables.emit.road_contact.ramp_grade)
    lane = float(law.tables.emit.road_profile.lane_width_m)
    lift: dict[int, float] = {}
    rep["steepened"] = 0
    for (a, b, u), run in sorted(runs.items()):
        z_e = (1.0 - u) * float(levels[a]) + u * float(levels[b])
        # a target at or above the contact asks nothing of the ramp
        g = _run_grade(z_e, _far_end([(s, min(z_e, target[v])) for s, v in run
                                      if v in target], lane), design, cap, lane)
        rep["steepened"] += g > design + 1e-9
        for s, v in run:
            lift[v] = z_e - g * s
    if not lift:
        return cs, rep

    linears = []
    for r in cs.linears:
        if r.source.generator == GEN and r.source.ruling == RULING:
            v = _vertex(r.source)
            if v in lift and lift[v] > float(r.hi):
                dz = lift[v] - float(r.hi)
                rep["raised"] += 1
                if dz > rep["max_raise_m"]:
                    rep["max_raise_m"] = dz
                    rep["worst"] = v
                r = _dc.replace(r, lo=lift[v], hi=lift[v])
        linears.append(r)
    bands = []
    for r in cs.bands:
        if r.source.generator == GEN and r.source.ruling == RULING_CEILING:
            v = _vertex(r.source)
            if v in lift and r.hi is not None and lift[v] + vis > float(r.hi):
                r = _dc.replace(r, hi=lift[v] + vis)
        bands.append(r)
    rep["max_raise_m"] = round(rep["max_raise_m"], 4)
    return _dc.replace(cs, linears=tuple(linears), bands=tuple(bands)), rep


#: OWNER RULINGS 2026-09-29x: the one bank from the road's far kerb to the
#: HIGHER pavement's edge.  Its head is ONE-WAY (``[design]
#: one_way_rulings``): the strip vertex follows, the road and the pavement
#: foot lead.  The zone generator's own ``GEN`` so every zone reader sees it.
BANK_RULING = ("zones.adjacent_ground between-levels bank "
               "(owner RULINGS 2026-09-29x, Q-97 (b))")
_ZONE_GEN = "zones"
_ZONE_HEAD = "zones.adjacent_ground"


def between_levels_rewrite(planar: PlanarMap, law: Law, cs: ConstraintSet,
                           levels: _t.Mapping[int, float]
                           ) -> tuple[ConstraintSet, dict[str, _t.Any]]:
    """OWNER RULINGS 2026-09-29x (Q-97 (b), issue #97): A GROUNDSIDE ROAD
    BETWEEN TWO AIRSIDE PAVEMENTS AT DIFFERENT LEVELS TAKES THE LOWER
    PAVEMENT'S LEVEL, AND ONE BANK RISES FROM ITS FAR KERB TO THE HIGHER.

    Between §20b's stages, off ``PlanarMap.road_between_levels``
    (``airport/road_ramp.between_levels``) and stage 1's solved levels:

    * per road vertex, the two feet read ``zA``/``zB``; where they differ
      by more than ``[cockpit] visual_m`` the §37 (6) DESIGN TARGET becomes
      ``min(zA, zB)`` and the HARD CEILING ``min + visual_m``;
    * a strip vertex whose foot is on the HIGHER pavement loses every zone
      row and takes ONE bank row — ``z_s = z_r + (z_foot - z_r)·w/(w+d)``,
      the plane from the road vertex to the pavement edge (the cut-back
      strip lies inside ``w``);
    * a strip vertex on the LOWER side keeps its band (mandatory-down from
      its pavement to the road) and loses only a floor keyed on the HIGHER
      pavement's edge, which would lift it above the road.

    The taxiways are stage 1's constants here: nothing airside moves."""
    bl = getattr(planar, "road_between_levels", None) or {}
    rep: dict[str, _t.Any] = {"road": 0, "applied": 0, "strip_high": 0,
                              "strip_low": 0,
                              "strip_low_dropped": 0, "unlevelled": 0,
                              "max_step_m": 0.0, "bank_over_slope": 0,
                              "max_bank_slope": 0.0}
    road = bl.get("road") or {}
    strip = bl.get("strip") or {}
    rep["road"] = len(road)
    if not road:
        return cs, rep
    vis = float(law.tables.emit.cockpit.visual_m)
    bank = float(law.tables.emit.design.bank_slope)

    def z_of(foot):
        a, b, u, _ref = foot
        if a not in levels or b not in levels:
            return None
        return (1.0 - u) * float(levels[a]) + u * float(levels[b])

    low: dict[int, float] = {}
    high_ref: dict[int, str] = {}
    for r, (fa, fb) in road.items():
        za, zb = z_of(fa), z_of(fb)
        if za is None or zb is None:
            rep["unlevelled"] += 1
            continue
        if abs(za - zb) <= vis:
            continue
        low[r] = min(za, zb)
        high_ref[r] = fa[3] if za > zb else fb[3]
        rep["max_step_m"] = max(rep["max_step_m"], abs(za - zb))
    rep["applied"] = len(low)
    if not low:
        return cs, rep
    high_vs: dict[str, set[int]] = {}
    for f in planar.faces.values():
        ref = f.ref.split("+")[0]
        if ref in set(high_ref.values()):
            high_vs.setdefault(ref, set()).update(
                v for cyc in (f.ring, *f.holes) for v in planar.ring_vertices(cyc))
    high_s: dict[int, tuple] = {}
    low_s: dict[int, str] = {}
    low_plane: dict[int, tuple] = {}
    for s_, (r, foot, w, d) in strip.items():
        if r not in low:
            continue
        if foot[3] == high_ref[r]:
            high_s[s_] = (r, foot, w, d)
        else:
            low_s[s_] = high_ref[r]
            low_plane[s_] = (r, foot, w, d)

    def _vertex(src: Source) -> int | None:
        tag = src.inputs[0] if src.inputs else ""
        return int(tag[7:]) if tag.startswith("vertex:") else None

    linears = []
    for row in cs.linears:
        src = row.source
        if src.generator == GEN and src.ruling == RULING:
            v = _vertex(src)
            if v in low:
                row = _dc.replace(row, lo=low[v], hi=low[v])
        elif (src.generator == _ZONE_GEN
              and src.ruling.split(" (")[0].strip() == _ZONE_HEAD):
            v = _vertex(src)
            if v in high_s:
                continue                      # the bank row replaces the band
            if v in low_s and any(t in high_vs.get(low_s[v], ())
                                  for t, _c in row.terms if t != v):
                rep["strip_low_dropped"] += 1
                continue
        linears.append(row)
    for s_, (r, (a, b, u, _ref), w, d) in sorted(high_s.items()):
        lam = w / (w + d)
        linears.append(Linear(((s_, 1.0), (r, -(1.0 - lam)),
                               (a, -(1.0 - u) * lam), (b, -u * lam)),
                              0.0, 0.0,
                              Source(_ZONE_GEN, BANK_RULING,
                                     (f"vertex:{s_}", f"road:{r}")),
                              follows=s_))
        zf = z_of((a, b, u, _ref))
        if zf is not None:
            sl = abs(zf - low[r]) / max(w + d, 1e-6)
            rep["max_bank_slope"] = max(rep["max_bank_slope"], sl)
            if sl > bank + 1e-9:
                rep["bank_over_slope"] += 1
    rep["strip_high"] = len(high_s)
    # THE LOW SIDE STAYS MANDATORY-DOWN FROM ITS PAVEMENT TO THE ROAD (29x):
    # a CEILING at the plane from the road vertex to the lower foot — both
    # at the lower level.  The zone band cannot state it where the lower
    # pavement carries no zone class (29ad: HECA's ``objpav115`` apron
    # piece), and without it the strip between the road and that apron
    # stood on its DEM 2.14 m above both (measured, replay arm 1 of 29ad).
    for s_, (r, (a, b, u, _ref), w, d) in sorted(low_plane.items()):
        lam = w / (w + d)
        linears.append(Linear(((s_, 1.0), (r, -(1.0 - lam)),
                               (a, -(1.0 - u) * lam), (b, -u * lam)),
                              None, 0.0,
                              Source(_ZONE_GEN, BANK_RULING,
                                     (f"vertex:{s_}", f"road:{r}")),
                              follows=s_))
    rep["strip_low"] = len(low_plane)
    bands = []
    for row in cs.bands:
        if row.source.generator == GEN and row.source.ruling == RULING_CEILING:
            v = _vertex(row.source)
            if v in low:
                row = _dc.replace(row, hi=low[v] + vis)
        bands.append(row)
    rep["max_step_m"] = round(rep["max_step_m"], 3)
    rep["max_bank_slope"] = round(rep["max_bank_slope"], 3)
    return _dc.replace(cs, linears=tuple(linears), bands=tuple(bands)), rep
