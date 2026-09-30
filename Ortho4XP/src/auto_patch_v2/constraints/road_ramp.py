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
import heapq
import math
import typing as _t

from ..law import Law
from ..law.tables import family, role_cap
from ..model.airport import Airport
from ..model.constraints import Band, ConstraintSet, Linear, Pin, Row, Source
from ..model.planar import PlanarMap

__all__ = ["GEN", "RULING", "RULING_CEILING", "JOIN_RULING",
           "CONTACT_RULING", "road_ramp_rows", "road_join_rows",
           "road_contact_rows", "reach_seed_rewrite", "BANK_RULING",
           "between_levels_rewrite", "road_contact_rewrite"]

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


def road_join_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """§37 (9): one ``Pin`` per road vertex at a coverage exit, at the core
    ribbon's own altitude just outside (``PlanarMap.road_coverage_join``,
    derived in ``emit/road_join.py``).  A map without the channel mints
    nothing — the derivation has one site."""
    joins = getattr(planar, "road_coverage_join", None) or {}
    rows: list[Row] = []
    # RULINGS 2026-09-30aa rule 2 (owner 30z (1)): the join is the ROAD's
    # level — a vertex a WELDED road (the mapped-road ribbon) SHARES with
    # the airside (a mouth on the exit station) is the airside's and takes
    # no road pin.  Measured (lane roadweld100, HECA roadmint100 replay):
    # this pin on apron vertex 30.1291193,31.4129393 (ribbon
    # service_road#1482) was the worst mover's binding row (+4.04 m).
    # (The 1206 routes' own join pins on apron — HECA pav37 / pav132, 5
    # vertices — are the reference's; an owner question.)
    from .roads import road_lead, welded_road
    memo: dict[int, bool] = {}
    for v in sorted(joins):
        if road_lead(planar, law, v, memo) and any(
                welded_road(planar.faces[f])
                for f in planar.vertices[v].incident_faces):
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
    cs, rep["contact"] = road_contact_rewrite(planar, law, cs, levels)
    return cs, rep


def road_contact_rewrite(planar: PlanarMap, law: Law, cs: ConstraintSet,
                         levels: _t.Mapping[int, float]
                         ) -> tuple[ConstraintSet, dict[str, _t.Any]]:
    """THE ROAD WELDED TO THE AIRSIDE, BETWEEN §20b's STAGES (spec-author
    RULINGS 2026-09-30aa rules 5-7; owner 29y, 30z (1)).

    Stage 1's levelled AIRSIDE contacts of a road (its LEADS,
    ``constraints/roads.road_lead``) are constants here.  From them the
    road's own graph (the planar edges among road-face vertices) gives
    every road vertex its CEILING ``U(r) = min over contacts (L + cap·s)``
    — the highest a road climbing from its LOWER contact at exactly the
    road cap can stand (rule 6, 29y: the terrain is cut, the road never
    climbs faster).

    * the §37 (6) design target and its hard ceiling are clamped to ``U``
      (rule 5: the ramp profile runs from the contact);
    * a two-foot row from a contact ``h`` to a road vertex ``r`` whose
      LOWER bound on ``z_r`` stands above ``U(r)`` is a run too short to
      reach ``h``: that bound is RELEASED (the row keeps its upper side)
      and the pair is reported — ``road_contact_step`` (rule 7), never an
      airside move, never a rerouted way.

    Returns the rewritten set and ``{"ceilinged", "clamped", "released":
    [(h, r, need_z), ...]}`` (``need_z`` = the released floor of ``z_r``) —
    the caller reads the step off the solved surface."""
    from .roads import road_family_roles, road_lead
    rep: dict[str, _t.Any] = {"ceilinged": 0, "clamped": 0, "released": []}
    roads = set(road_family_roles(law))
    caps = [role_cap(law, r).longitudinal for r in roads if role_cap(law, r)]
    if not caps or not levels:
        return cs, rep
    cap = min(caps)
    nodes: set[int] = set()
    for f in (getattr(planar, "faces", None) or {}).values():
        if f.role in roads:
            for cyc in (f.ring, *f.holes):
                nodes.update(planar.ring_vertices(cyc))
    memo: dict[int, bool] = {}
    leads = {v: float(levels[v]) for v in nodes
             if v in levels and road_lead(planar, law, v, memo)}
    if not leads:
        return cs, rep
    adj: dict[int, list[tuple[int, float]]] = {}
    for e in planar.edges.values():
        if e.a in nodes and e.b in nodes:
            d = math.dist(planar.vertices[e.a].xy, planar.vertices[e.b].xy)
            adj.setdefault(e.a, []).append((e.b, d))
            adj.setdefault(e.b, []).append((e.a, d))
    ceil: dict[int, float] = {}
    heap = [(z, v) for v, z in leads.items()]
    heapq.heapify(heap)
    while heap:
        z, v = heapq.heappop(heap)
        if v in ceil:
            continue
        ceil[v] = z
        for w, d in adj.get(v, ()):
            if w not in ceil:
                heapq.heappush(heap, (z + cap * d, w))
    road_v = {v for v in ceil if v not in leads}
    if not road_v:
        return cs, rep
    vis = float(law.tables.emit.cockpit.visual_m)
    tol = float(law.tables.emit.materiality.elevation_m)

    def _vertex(src: Source) -> int | None:
        tag = src.inputs[0] if src.inputs else ""
        return int(tag[7:]) if tag.startswith("vertex:") else None

    def _release(a: int, ca: float, b: int, cb: float, lo, hi):
        """``lo <= ca·z_a + cb·z_b <= hi`` with one foot a lead ``h`` and
        the other a road vertex ``r``: ``(lo', hi', (h, r, bound))`` with
        the side that holds ``z_r`` UP released where it cannot be met."""
        if a in leads and b in road_v:
            h, ch, r, cr = a, ca, b, cb
        elif b in leads and a in road_v:
            h, ch, r, cr = b, cb, a, ca
        else:
            return None
        if abs(abs(cr) - 1.0) > 1e-9 or abs(abs(ch) - 1.0) > 1e-9:
            return None
        rest = ch * leads[h]
        # the bound on z_r: cr·z_r in [lo - rest, hi - rest]
        if cr > 0:
            if lo is None or (lo - rest) <= ceil[r] + tol:
                return None
            return (None, hi, (h, r, lo - rest))
        if hi is None or -(hi - rest) <= ceil[r] + tol:
            return None
        return (lo, None, (h, r, -(hi - rest)))

    released: list[tuple[int, int, float]] = []
    diffs: list = []
    linears = list()
    for row in cs.diffs:
        got = None if row.soft is not None else _release(row.a, 1.0, row.b, -1.0, -row.cap * row.d, row.cap * row.d)
        if got is None:
            diffs.append(row)
            continue
        lo, hi, rec = got
        released.append(rec)
        linears.append(Linear(((row.a, 1.0), (row.b, -1.0)), lo, hi, row.source,
                              follows=getattr(row, "follows", None)))
    for row in cs.linears:
        src = row.source
        if src.generator == GEN and src.ruling == RULING and len(row.terms) == 1:
            v = _vertex(src)
            if v in road_v and row.lo is not None and row.lo > ceil[v]:
                row = _dc.replace(row, lo=ceil[v], hi=ceil[v])
                rep["clamped"] += 1
        elif len(row.terms) == 2:
            (a, ca), (b, cb) = row.terms
            got = _release(a, ca, b, cb, row.lo, row.hi)
            if got is not None:
                lo, hi, rec = got
                released.append(rec)
                row = _dc.replace(row, lo=lo, hi=hi)
        linears.append(row)
    bands = []
    for b_ in cs.bands:
        src = b_.source
        if (src.generator == GEN and src.ruling == RULING_CEILING
                and b_.v in road_v and b_.hi is not None
                and b_.hi > ceil[b_.v] + vis):
            b_ = _dc.replace(b_, hi=ceil[b_.v] + vis)
            rep["ceilinged"] += 1
        bands.append(b_)
    rep["released"] = sorted(set(released))
    return _dc.replace(cs, diffs=tuple(diffs), linears=tuple(linears),
                       bands=tuple(bands)), rep


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
