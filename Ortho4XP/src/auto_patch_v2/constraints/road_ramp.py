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

from ..law import Law
from ..law.tables import family, role_cap
from ..model.airport import Airport
from ..model.constraints import Band, ConstraintSet, Linear, Pin, Row, Source
from ..model.planar import PlanarMap

__all__ = ["GEN", "RULING", "RULING_CEILING", "JOIN_RULING",
           "CONTACT_RULING", "road_ramp_rows", "road_join_rows",
           "road_contact_rows", "reach_seed_rewrite", "BANK_RULING",
           "between_levels_rewrite", "airside_joins", "welded_join_release"]

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
    cs, rep["between_levels"] = between_levels_rewrite(planar, law, cs, levels)
    cs, rep["welded_join"] = welded_join_release(planar, law, cs, levels)
    return cs, rep


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
    the seed is ``z_edge - cap * s`` with ``z_edge = (1-u)·L[a] + u·L[b]``,
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
    lift: dict[int, float] = {}
    for v, (a, b, u, s) in seed.items():
        if a not in levels or b not in levels:
            rep["unlevelled"] += 1
            continue
        lift[v] = ((1.0 - u) * float(levels[a]) + u * float(levels[b])
                   - cap * float(s))
    if not lift:
        return cs, rep

    def _vertex(src: Source) -> int | None:
        tag = src.inputs[0] if src.inputs else ""
        return int(tag[7:]) if tag.startswith("vertex:") else None

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
