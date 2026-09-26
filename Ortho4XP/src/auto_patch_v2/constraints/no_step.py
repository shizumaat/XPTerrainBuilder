"""AIRSIDE NO-STEP generator (family ``airside_no_step``, RULINGS
2026-08-27 "no steps in airside pavement", CLARIFIED by 2026-09-04o /
04q-1: the pairs are formed ALONG PAVEMENT and priced over the ROUTE).

Two terms, one law:

* §1.1 ROUTE-DISTANCE pairs: for every airside vertex, ``emit.no_step.k``
  law edges to its nearest airside vertices BY ROUTE DISTANCE through the
  taxi network (``planar.routes``) within ``emit.no_step.window_m`` ROUTE
  metres, each a ``Diff`` whose bound is ``Σ cap_e · len_e`` along that
  path — the path's own caps, so an apron↔taxiway pair carries the
  taxiway's cap on the taxiway stretch and the apron's on the apron
  stretch, never the apron's 1 % over a plan chord (04q-1; measured
  trigger CYXY apron 156, `why-report-cyxy.md`).  A pair with no pavement
  path inside the window DOES NOT EXIST (04o: "aircraft can't travel
  straight across the grass").  ``emit.no_step.metric`` must read
  ``"route"`` — the chord metric is the refuted reading and is refused.
  The solver publishes exactly these pairs (:func:`no_step_edges`,
  sidecar ``airside_no_step_edges`` with ``budget_m`` and the ROUTE
  ``dist_m``) and the census prices the same list — one law, one
  population.
* §1.2 RATE OF CHANGE along every airside ring sequence (wrap-around
  triples included, as the census walks them): the grade change across a
  station may not outrun the aerodrome's vertical-curve rate
  (``rulesets.strip.arc_rate`` — ONE constant, the strip family's,
  never a second number), a three-term ``Linear`` row
  ``|(z_c − z_b)/dn − (z_b − z_a)/dp| ≤ rate · (dp + dn)/2 + q·(1/dp + 1/dn)``.
  The second term is THE RATE READER'S OWN BLIND SPOT
  (``emit.instrument.coarse_noise_m``; v1 ``_rate_reader_blind_spot``):
  a ring SEQUENCE is the instrument's walk, not a travel path — at a
  ring corner beside a crowned ridge the exact rate is unsatisfiable at
  1–3 m spacings (measured CYXY 02/20: crown floor + rate + direct pair
  form an IIS), and the reader itself cannot distinguish such a station
  from rounding.  Bound in the instrument's frame, stated once here.

THE REACH BANDS (04o; v1 ``reach_band_unified`` as a v2 constraint):
the runway thresholds' CIFP values propagated along every route at the
path caps give each airside vertex a floor and a ceiling
(``planar.routes.reach``), minted as ``Band`` rows under
``model.constraints.REACH_GENERATOR`` — the solver cannot place a vertex
outside what any route from the thresholds allows.  They are the
envelope the hard path rows already imply; the law-ordered solve
withdraws them once a tier yields (``solve/tiers.py``).

THE POPULATION is derived from the tables (03i): the airside VALUE roles
that are governed and not rigid — a pad is a flat group levelled by its
contact and is never a no-step endpoint of its own (v1
``enclaves.ENCLAVE_AIRSIDE_ROLES`` is the same set by other means).

THE PAD↔PAVEMENT PAIRS (RULINGS 2026-09-04r, under 03h/03i + 04o; M5's
chord population refuted at HECA: 1,181 tier-8 rows, the one population
still chord-priced, m5b-report §5): a pad is a flat group LEVELLED BY
ITS CONTACT, so its only law edge to pavement is the CONTACT EDGE — the
vertices its rim shares with airside pavement — priced at the pavement's
own caps along the pavement route.  ``pad_pavement_edges``: for every
ATTACHED pad, from each contact vertex the K nearest pavement vertices
BY ROUTE within the window, the pad's own group never a partner (one
flat value against itself) and never spending the K; each pair
``Σ cap·len`` along its path exactly as a pavement pair.  A DETACHED pad
(no contact) has NO pairs — a DEM-levelled flat group (03h).  The pad's
BODY vertices are never an endpoint: free-standing pad↔pavement chords
do not exist.  A contact vertex a groundside lot shares is the lot's
(09-01g).  Published under the sidecar key ``pad_pavement_no_step_edges``
as the pairs the pavement list does not already carry (the contact
vertex is itself a pavement vertex, so its own K-nearest are in
``airside_no_step_edges``; the v1 oracle's proximity join is why the key
stays separate, M5 §3), priced by v2 verify by identity.  The row's tier
is the contact's owner (the apron), never the pad's: the pad pairs are
apron law.
"""
from __future__ import annotations

from ..law import Law, LawError
from ..law.tables import is_rigid_role, is_value_role, role_cap, role_side
from ..model.airport import Airport
from ..model.constraints import REACH_GENERATOR, Band, Diff, Linear, Row, Source
from ..model.planar import PlanarMap
from .routes import reach, route_neighbours, routes
from .precedence import View, view
from .runway_profile import threshold_pins

__all__ = ["no_step_roles", "rigid_airside_roles", "no_step_pairs",
           "no_step_rate", "no_step_edges", "pad_only_vertices", "pad_contacts",
           "pad_pavement_edges", "rate_rows_for_chain", "reach_bands",
           "reach_band_values"]

GEN = "no_step"
#: The §1.1 pair rows' ruling prefix (both the pavement and the pad-contact
#: pairs): the yielding transform selects them by it (``constraints/yielding.py``).
PAIR_RULING_PREFIX = "airside_no_step §1.1"


def no_step_roles(law: Law) -> frozenset[str]:
    """Airside, value-carrying, governed, not rigid (03i)."""
    reg = law.tables.precedence.roles
    return frozenset(r for r in reg
                     if role_side(law, r) == "airside" and is_value_role(law, r)
                     and role_cap(law, r) is not None and not is_rigid_role(law, r))


def rigid_airside_roles(law: Law) -> frozenset[str]:
    """Airside, value-carrying, governed, RIGID (a pad) — the pad side
    of the pad↔pavement pairs."""
    reg = law.tables.precedence.roles
    return frozenset(r for r in reg
                     if role_side(law, r) == "airside" and is_value_role(law, r)
                     and role_cap(law, r) is not None and is_rigid_role(law, r))


def _airside_vertices(vw: View, roles: frozenset[str]) -> dict[int, float]:
    """Vertex -> strictest airside cap over its no-step faces."""
    out: dict[int, float] = {}
    for f in vw.faces_of_role(roles):
        c = vw.caps[f.id]
        if c is None:
            continue
        for v in vw.rings[f.id]:
            out[v] = min(out.get(v, c[0]), c[0])
        for h in vw.holes[f.id]:
            for v in h:
                out[v] = min(out.get(v, c[0]), c[0])
    return out


def no_step_edges(planar: PlanarMap, law: Law, airport: Airport | None = None
                  ) -> list[tuple[int, int, float, float]]:
    """``(a, b, cap, route distance)`` per published PAVEMENT pair — K
    nearest per airside vertex BY ROUTE within the window (route metres),
    deduplicated; ``cap`` is the PATH cap ``budget / route distance`` so
    ``Diff.bound_m`` is exactly ``Σ cap_e · len_e`` along the path
    (04q-1).  The list the oracle prices (``budget_m`` = the bound,
    ``dist_m`` = the route); unchanged by the pad pairs."""
    ns = law.tables.emit.no_step
    if ns.metric != "route":
        raise LawError(f"emit.no_step.metric = {ns.metric!r}: only \"route\" is lawful "
                       "(RULINGS 2026-09-04o — a chord metric is the refuted reading)")
    # ONE READ PER MAP (jetway-strip spec §5 bar 5): the generator, the
    # strip's strike set and the publication all ask for the same list on
    # the same frozen map; a two-entry identity memo keeps it one route walk
    # (HECA ~1 s each).  The caller gets a copy.
    key = (id(planar), id(law), id(airport))
    for k, pm, lw, ap, got in _EDGES_MEMO:
        if k == key and pm is planar and lw is law and ap is airport:
            return list(got)
    out = _no_step_edges(planar, law, airport, ns)
    _EDGES_MEMO.append((key, planar, law, airport, tuple(out)))
    del _EDGES_MEMO[:-2]
    return out


_EDGES_MEMO: list[tuple] = []


def _no_step_edges(planar: PlanarMap, law: Law, airport: Airport | None, ns
                   ) -> list[tuple[int, int, float, float]]:
    vw = view(planar, law)
    caps = _airside_vertices(vw, no_step_roles(law))
    g = routes(planar, law, airport)
    out: list[tuple[int, int, float, float]] = []
    for a, b, d, bud in route_neighbours(g, caps, ns.window_m, ns.k, targets=caps):
        if d <= 0.0:
            continue
        out.append((a, b, bud / d, d))
    return out


def reach_band_values(planar: PlanarMap, law: Law, airport: Airport
                      ) -> dict[int, tuple[float, float]]:
    """Vertex -> ``(floor, ceiling)`` from the threshold pins along the
    routes (``planar.routes.reach``); empty when no runway carries a
    CIFP threshold."""
    pins = threshold_pins(planar, law, airport)
    if not pins:
        return {}
    return reach(routes(planar, law, airport), pins)


def reach_bands(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """THE REACH BANDS as ``Band`` rows (module docstring); a vertex whose
    floor exceeds its ceiling is skipped — the pins already contradict
    along the routes and the path rows will say so."""
    src = Source(REACH_GENERATOR, "reach band: threshold values along taxi routes "
                 "at the path caps (2026-09-04o)", ())
    rows: list[Row] = []
    for v, (lo, hi) in sorted(reach_band_values(planar, law, airport).items()):
        if lo <= hi:
            rows.append(Band(v, lo, hi, src))
    return rows


def pad_only_vertices(planar: PlanarMap, law: Law) -> dict[int, float]:
    """Vertex -> cap for every PAD-ONLY airside vertex: a rigid face's
    vertex touching rigid faces and nothing else (a pad vertex shared
    with airside pavement is that pavement's; one shared with a
    groundside lot is the lot's — a mixed pad, 09-01g: the terrace in
    the stand-off is lawful; measured SPJC: pairing it minted 7.2 m
    building|groundside_pavement rows)."""
    vw = view(planar, law)
    rigid = {r for r in law.tables.precedence.roles if is_rigid_role(law, r)}
    pav = _airside_vertices(vw, no_step_roles(law))
    return {v: c for v, c in _airside_vertices(vw, rigid_airside_roles(law)).items()
            if v not in pav and all(planar.faces[f].role in rigid
                                    for f in vw.vertex_faces[v])}


def pad_contacts(planar: PlanarMap, law: Law) -> dict[int, list[int]]:
    """Pad face id -> its CONTACT vertices, sorted: the rim vertices
    shared with airside pavement (the no-step roles), and — RULINGS
    2026-09-05ab — the rim vertices a ``frontage_near_miss`` row binds
    to an airside soft vertex (``pads.frontage_contacts``: the pad's
    doorway onto the route graph, ``routes`` CONTACT).  A pad with none
    is DETACHED and absent.  A rim vertex a groundside lot shares and no
    airside pavement does is the lot's (09-01g) and is no contact."""
    from .pads import frontage_contacts
    vw = view(planar, law)
    pav = _airside_vertices(vw, no_step_roles(law))
    rigid = {r for r in law.tables.precedence.roles if is_rigid_role(law, r)}
    near: dict[int, set[int]] = {}
    for e, j, pid, _d, _cap, _sf in frontage_contacts(planar, law):
        if e in pav:
            near.setdefault(pid, set()).add(j)
    out: dict[int, list[int]] = {}
    for f in vw.faces_of_role(rigid):
        seen: set[int] = set(near.get(f.id, ()))
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            seen.update(v for v in ring if v in pav)
        if seen:
            out[f.id] = sorted(seen)
    return out


def pad_pavement_edges(planar: PlanarMap, law: Law,
                       pavement: list[tuple[int, int, float, float]] | None = None,
                       airport: Airport | None = None
                       ) -> list[tuple[int, int, float, float]]:
    """``(contact vertex, pavement vertex, path cap, route distance)`` —
    THE PAD↔PAVEMENT PAIRS through the contact (module docstring, 04r):
    for every attached pad, from each contact vertex the K nearest
    pavement vertices by route inside the window, the pad's own vertices
    excluded, ``cap = budget / d`` so ``Diff.bound_m = Σ cap_e·len_e``
    along the path; pairs the pavement list (``pavement``, computed when
    not given) already carries are not repeated.  Detached pads: none."""
    contacts = pad_contacts(planar, law)
    if not contacts:
        return []
    ns = law.tables.emit.no_step
    vw = view(planar, law)
    pav = _airside_vertices(vw, no_step_roles(law))
    own: dict[int, set[int]] = {}
    for fid, cvs in contacts.items():
        group: set[int] = set(vw.rings[fid])
        for h in vw.holes[fid]:
            group.update(h)
        for v in cvs:
            own.setdefault(v, set()).update(group)
    have = {(a, b) for a, b, _c, _d in (pavement if pavement is not None
                                          else no_step_edges(planar, law, airport))}
    g = routes(planar, law, airport)
    out: list[tuple[int, int, float, float]] = []
    for a, b, d, bud in route_neighbours(g, sorted(own), ns.window_m, ns.k,
                                         targets=pav, exclude=own):
        if d <= 0.0 or (a, b) in have:
            continue
        out.append((a, b, bud / d, d))
    return out


def no_step_pairs(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """§1.1 as ``Diff`` rows: the pavement pairs, then the pad↔pavement
    pairs through the contact (04r; apron law rows by the vertex rule)."""
    src = Source(GEN, "airside_no_step §1.1 route pairs (2026-08-27, 04o/04q-1)", ())
    src_pad = Source(GEN, "airside_no_step §1.1 pad contact↔pavement route pairs "
                     "(2026-09-04r)", ())
    pav = no_step_edges(planar, law, airport)
    return ([Diff(a, b, cap, d, src) for a, b, cap, d in pav]
            + [Diff(a, b, cap, d, src_pad)
               for a, b, cap, d in pad_pavement_edges(planar, law, pav, airport)])


def rate_rows_for_chain(vw: View, chain: list[int], rate: float, src: Source,
                        closed: bool, q: float = 0.0) -> list[Row]:
    """Three-term rate rows over consecutive triples of ``chain``; ``q``
    is the reader's rounding quantum (its blind spot ``q·(1/dp+1/dn)``)."""
    idx = list(range(len(chain)))
    if closed:
        idx = idx + [0, 1]
    rows: list[Row] = []
    for k in range(1, len(idx) - 1):
        a, b, c = chain[idx[k - 1]], chain[idx[k]], chain[idx[k + 1]]
        if len({a, b, c}) < 3:
            continue
        dp, dn = vw.dist(a, b), vw.dist(b, c)
        if dp < 1e-6 or dn < 1e-6:
            continue
        bound = rate * 0.5 * (dp + dn) + q * (1.0 / dp + 1.0 / dn)
        terms = ((c, 1.0 / dn), (b, -(1.0 / dn + 1.0 / dp)), (a, 1.0 / dp))
        rows.append(Linear(terms, -bound, bound, src))
    return rows


def no_step_rate(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """§1.2 along every airside ring (wrap triples included)."""
    vw = view(planar, law)
    r = law.ruleset.strip.arc_rate
    rate = r.grade / r.per_m
    # the reader's blind spot LESS the one emit quantum: the LP sits on
    # its bounds, and a bound that spends the whole envelope is broken
    # by the 0.01 m rounding it is then read at (measured CYXY: 17 rate
    # rows 0.1 mm over, all at the bound)
    q = law.tables.emit.instrument.coarse_noise_m - law.tables.emit.materiality.elevation_m
    rows: list[Row] = []
    for f in vw.faces_of_role(no_step_roles(law)):
        src = Source(GEN, "airside_no_step §1.2 rate (2026-08-27)",
                     (f"face:{f.id}", f.ref))
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            if len(ring) >= 3:
                rows.extend(rate_rows_for_chain(vw, ring, rate, src, True, q))
    return rows
