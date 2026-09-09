"""THE YIELDING FAMILIES (owner RULINGS 2026-09-08d (2); spec
``heca-v1-parity-spec.md`` §2, consumer census §6.1): v1's priority model
in v2's machinery — the surface families beyond the runway-connected
route graph are PREFERENCES with escalation ceilings, junior to the
runway chord fit (``constraints/runway_chord.py``) and senior to the DEM
fit; they yield where the runway demands, exactly as v1's per-edge caps
did (v1 junction max 9.1 % at HECA), instead of dragging (05C/23C) or
lifting (05L/23R +7.5 m) the runway through their redundant 1.5 %
surfaces (RULINGS 2026-09-07a, 08d).

ONE transform at assembly (:func:`yield_rows`, run by ``pipeline.shapes.
shape_constraints`` after the joint filter, never inside a generator):
every HARD ``Diff`` / ``Linear`` selected by a family named in
``emit.toml [yield] families`` (:data:`FAMILY_SELECTORS`: a generator, or
a ruling-selected subset of one — the ``taxi`` generator's short-pair box
rows, ``no_step``'s §1.1 pairs, the taxi CHAIN's hops / centreline chords
with an endpoint on a runway-family face — RULINGS 2026-09-08i-1: the
chain yields where it meets the runway so the runway comes first, 04i)
becomes a preference row —
``soft = "yield:<family>:<face>:<k>"``, ONE escalation group per row (the
apron precedent, ``constraints/apron.py``: the solver pays for exactly the
relief it uses; the group name carries the family and the face for the
report) — with the escalation CEILING of its class (``taxi_yield_max`` /
``apron_yield_max`` / ``road_yield_max``): a ``Diff``'s ceiling is that
grade; a ``Linear``'s ceiling is the metres its bound may rise, ``|bound|
× (ceiling / cap − 1)`` with ``cap`` the row's face's own longitudinal
cap.  A class whose ``<class>_yield_max`` key is ABSENT yields WITHOUT a
ceiling (owner RULINGS 2026-09-08k (3): inside a shape the apron rows are
preferences — 1 % preferred, 1.5 % the second tier, steeper where the
routes demand; a step is never lawful there).  A row whose cap already
reaches a stated ceiling has nothing to yield and stays hard.  The runway
family, the rest of the taxi CHAIN (05ac: crossings, every hop / chord
away from the runway), the reach bands, K, the runway transverse law,
pads, structures, zones, strips, seams, the flat datum and the apron 1 %
preference rows (already soft) are untouched.

THE REPORT FIGURE (:func:`yielded_rows`): per family the rows, the rows
the built surface holds above their cap (by more than the grade
materiality), the max built grade / metres over; and the published
``yielded_rows`` list (the ``relaxed_rows`` record shape: ``kind``,
``family``, ``face``, ``cap``, ``cap_after`` = the built grade,
``distance_m``, ``slack_m``, ``ll``) so the v1 oracle
(``check_grade.stamp_relaxed_rows`` with the ``yielded_by_08d`` stamp) and
v2 verify (``verify/census.mark_yielded``) count them APART from the law
rows — a yielded row is read as a VIOLATION at its cap under the law-true
reading (v1's) and as lawful yield under the other; the census reports
both.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..law import Law
from ..law.tables import role_cap, yield_ceiling, yield_law, yields
from ..model.constraints import ConstraintSet, Diff, Linear, Row, Source
from ..model.planar import PlanarMap
from .no_step import GEN as NO_STEP_GEN
from .no_step import PAIR_RULING_PREFIX
from .taxi import BOX_RULING
from .taxi import GEN as TAXI_GEN

__all__ = ["GROUP", "FAMILY_SELECTORS", "YieldStats", "yield_family", "yield_rows",
           "yielded_rows", "groundside_ramps", "RAMP_FAMILY", "runway_vertices",
           "CHAIN_MARK", "CENTRELINE_RULING", "NETWORK_YIELDS"]

#: The groundside ramp rows' family (their group ``yield:groundside_ramp:…``).
RAMP_FAMILY = "groundside_ramp"

#: The escalation-group prefix of a yielding row (``Weights.preference``
#: key, ``solve/assemble.preference_weight``): ``yield:<family>:<face>:<k>``.
GROUP = "yield"

#: The chain rulings the runway-contact family selects (``taxi.chain_ruling``
#: / ``taxi_centerlines``): a lateral hop or a centreline chord, never a
#: crossing (the runway's own cap).
CHAIN_MARK = "chain (2026-09-05aa / 05ac)"
CENTRELINE_RULING = "rulesets.taxi.longitudinal centreline"


def _chain_at_runway(r: Row, rw: _t.Container[int]) -> bool:
    if r.source.generator != TAXI_GEN:
        return False
    rl = r.source.ruling
    if rl != CENTRELINE_RULING and not (rl.endswith(CHAIN_MARK) and "crossing" not in rl):
        return False
    return any(v in rw for v in _row_ids(r))


def _row_ids(r: Row) -> tuple[int, ...]:
    if isinstance(r, Diff):
        return (r.a, r.b)
    return tuple(v for v, _c in r.terms)


#: Family name (``emit.toml [yield] families``, ``law/yield_schema.
#: YIELD_FAMILIES``) -> the predicate selecting its rows, given the set of
#: runway-family vertices.
FAMILY_SELECTORS: dict[str, _t.Callable[[Row, _t.Container[int]], bool]] = {
    "junction_mesh": lambda r, rw: r.source.generator == "junction_mesh",
    "taxi_box": lambda r, rw: r.source.generator == TAXI_GEN and r.source.ruling == BOX_RULING,
    "no_step_pairs": lambda r, rw: (r.source.generator == NO_STEP_GEN
                                    and r.source.ruling.startswith(PAIR_RULING_PREFIX)),
    "apron": lambda r, rw: r.source.generator == "apron",
    "apron_edge_portion": lambda r, rw: r.source.generator == "apron_edge_portion",
    "roads": lambda r, rw: r.source.generator == "roads",
    "taxi_chain_at_runway": _chain_at_runway,
}


def runway_vertices(pm: PlanarMap, law: Law) -> frozenset[int]:
    """Every vertex touching a runway-family face."""
    rw = set(law.tables.precedence.runway_family.members)
    return frozenset(v for v, vert in pm.vertices.items()
                     if any(pm.faces[f].role in rw for f in vert.incident_faces))


@_dc.dataclass
class YieldStats:
    """What the transform did: rows made preferences per family, rows
    left hard for having nothing to yield."""

    by_family: dict[str, int] = _dc.field(default_factory=dict)
    at_ceiling: dict[str, int] = _dc.field(default_factory=dict)
    network_hard: dict[str, int] = _dc.field(default_factory=dict)   # 08p: rows wholly on the network, left hard


def yield_family(row: Row) -> str | None:
    """The family a YIELD preference row belongs to (its group's second
    field), ``None`` for any other row."""
    g = getattr(row, "soft", None)
    if not g or not g.startswith(GROUP + ":"):
        return None
    return g.split(":", 3)[1]


def _face_of(row: Row) -> str:
    for inp in row.source.inputs:
        if inp.startswith("face:"):
            return inp[5:]
    return "-"


def _face_cap(pm: PlanarMap, law: Law, row: Row) -> float | None:
    fid = _face_of(row)
    if fid == "-":
        return None
    f = pm.faces.get(int(fid))
    if f is None:
        return None
    rc = role_cap(law, f.role, f.code_number, f.code_letter)
    return None if rc is None else rc.longitudinal


#: The family that yields on the network too (owner RULINGS 2026-09-08i-1:
#: the chain yields where it meets the runway).
NETWORK_YIELDS = frozenset({"taxi_chain_at_runway"})
#: The yield CLASSES held hard on the network come from the law table
#: (``emit.toml [yield] network_hard_classes``, the round's experiment
#: knob): the taxi class is the network's own surface law; the apron class
#: (a frontage chord between two contacts on the network spans the BODY)
#: and the road class are the body's law and yield whatever their
#: endpoints touch (08k (3): no ceiling in a shape).


def yield_rows(cs: ConstraintSet, pm: PlanarMap, law: Law,
               stats: YieldStats | None = None,
               network: _t.Container[int] = frozenset()) -> ConstraintSet:
    """The set with every selected HARD row a preference (module docstring).
    THE NETWORK IS HARD (owner RULINGS 2026-09-08p (2)): a row whose every
    vertex lies in ``network`` (``planar.shapes.network_vertices``: the
    vertices of the faces carrying a runway-connected centreline, and the
    runway's) stays hard at its law — the taxiways connect the shapes by
    ROUTE; only the runway-contact chain (:data:`NETWORK_YIELDS`) yields
    there, and only the classes ``[yield] network_hard_classes`` names are held:
    an apron chord between two contacts on the network spans the body and
    yields as the body's law.  A row with one end in a body yields (the
    body's weld to the network is a soft edge on the body's side)."""
    classes = dict(yield_law(law).families)
    hard_classes = frozenset(yield_law(law).network_hard_classes)
    fams = [(name, FAMILY_SELECTORS[name]) for name in classes if name in FAMILY_SELECTORS]
    rw = runway_vertices(pm, law) if any(n == "taxi_chain_at_runway" for n, _s in fams) else frozenset()
    st = stats if stats is not None else YieldStats()
    out: list[Row] = []
    k: dict[str, int] = {}
    for r in cs.rows():
        if not isinstance(r, (Diff, Linear)) or r.soft is not None:
            out.append(r)
            continue
        fam = next((name for name, sel in fams if sel(r, rw)), None)
        if fam is None:
            out.append(r)
            continue
        if (fam not in NETWORK_YIELDS and classes.get(fam) in hard_classes
                and all(v in network for v in _row_ids(r))):
            st.network_hard[fam] = st.network_hard.get(fam, 0) + 1
            out.append(r)
            continue
        ceil = yield_ceiling(law, fam)          # None: unbounded (08k (3))
        if isinstance(r, Diff):
            if ceil is not None and r.cap >= ceil:
                st.at_ceiling[fam] = st.at_ceiling.get(fam, 0) + 1
                out.append(r)
                continue
            ceiling = ceil
        else:
            cap = _face_cap(pm, law, r)
            bound = max(abs(x) for x in (r.lo, r.hi) if x is not None) if (
                r.lo is not None or r.hi is not None) else None
            if ceil is None:
                ceiling = None
            elif cap is None or cap >= ceil or bound is None:
                st.at_ceiling[fam] = st.at_ceiling.get(fam, 0) + 1
                out.append(r)
                continue
            else:
                ceiling = bound * (ceil / cap - 1.0)
        face = _face_of(r)
        key = f"{fam}:{face}"
        k[key] = k.get(key, 0) + 1
        out.append(_dc.replace(r, soft=f"{GROUP}:{fam}:{face}:{k[key]}", ceiling=ceiling))
        st.by_family[fam] = st.by_family.get(fam, 0) + 1
    return ConstraintSet.from_rows(out)


def groundside_ramps(pm: PlanarMap, law: Law, airport=None) -> list[Row]:
    """THE APRON EDGE RAMPS TO THE GROUNDSIDE (RULINGS 2026-09-08d (4b); spec
    heca-v1-parity §4 / §6.3 (b)): for every apron ring vertex, the nearest
    GROUNDSIDE pavement ring vertex (a value role of the groundside side)
    across the stand-off — within ``zones.adjacent_ground.groundside_cutback_m
    + identity.weld_spacing_m`` plus the snap margin, and not a shared
    vertex — takes one ``Diff`` at ``yield.groundside_ramp_max`` (5 %, v1
    ``GROUNDSIDE_MAX_GRADE``) as a PREFERENCE with no ceiling (group
    ``yield:groundside_ramp:<face>:<k>``): a step across the stand-off is
    charged like any yield, a ramp is free — the groundside (DEM fit 1/m)
    lifts or cuts to meet the apron edge and grades away at its own cap.
    A generator (``constraints.GENERATORS``): its rows are soft from birth."""
    from ..law.tables import is_structure_role, is_value_role, role_side, snap_margin_m
    from .precedence import view
    vw = view(pm, law)
    y = yield_law(law)
    reg = law.tables.precedence.roles
    # the groundside PAVEMENT only: a structure's role (a tunnel ramp, a door
    # ramp, a retaining wall — groundside value roles too) is no lot the
    # apron ramps to; its rim stands at the ground by station and its
    # descent rows are its own law (``constraints/structures.py``).  Measured
    # 2026-09-08 (lane v2shapes): six rows apron <-> tunnel_ramp rim at
    # 1.0-1.4 m lifted a ramp 8 mm over its descent law and pulled the apron
    # 0.46 m under the DEM at a door well
    ground = tuple(r for r in reg if role_side(law, r) == "groundside" and is_value_role(law, r)
                   and not is_structure_role(law, r))
    gv: dict[int, tuple[float, float]] = {}
    for f in vw.faces_of_role(ground):
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            for v in ring:
                gv[v] = vw.xy[v]
    if not gv:
        return []
    ids = sorted(gv)
    from scipy.spatial import cKDTree
    tree = cKDTree([gv[v] for v in ids])
    horizon = (law.tables.zones.adjacent_ground.groundside_cutback_m
               + law.tables.emit.identity.weld_spacing_m + snap_margin_m(law))
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    rows: list[Row] = []
    seen: set[tuple[int, int]] = set()
    for f in vw.faces_of_role(("apron",)):
        src = Source(RAMP_FAMILY, "2026-09-08d (4b): the apron edge ramps to the groundside "
                     "at yield.groundside_ramp_max (preference)", (f"face:{f.id}", f.ref))
        k = 0
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            for v in ring:
                if v in gv:
                    continue                        # a shared vertex: no stand-off here
                d, j = tree.query(vw.xy[v])
                if d > horizon or d < min_d:
                    continue
                g = ids[int(j)]
                key = (min(v, g), max(v, g))
                if key in seen:
                    continue
                seen.add(key)
                k += 1
                rows.append(Diff(v, g, y.groundside_ramp_max, float(d), src,
                                 soft=f"{GROUP}:{RAMP_FAMILY}:{f.id}:{k}", ceiling=None))
    return rows


def yielded_rows(cs: ConstraintSet, z: _t.Sequence[float], law: Law, pm: PlanarMap | None = None
                 ) -> dict[str, _t.Any]:
    """THE BUILT SURFACE AGAINST THE YIELDING FAMILIES (module docstring):
    per family the rows, the yielded rows, the max built grade / metres
    over; ``rows`` the publication list when ``pm`` is given."""
    tol_g = law.tables.emit.materiality.grade
    tol_m = law.tables.emit.materiality.elevation_m
    fams: dict[str, dict[str, _t.Any]] = {}
    pub: list[dict[str, _t.Any]] = []
    by_shape: dict[int, dict[str, _t.Any]] = {}        # 08k: the max apron grade inside each shape
    shape_of = pm.shape_of_vertex if pm is not None else {}
    worst: dict[str, list[tuple[float, dict[str, _t.Any]]]] = {}   # per family, the steepest rows
    for r in (*cs.diffs, *cs.linears):
        fam = yield_family(r)
        if fam is None:
            continue
        rec = fams.setdefault(fam, {"rows": 0, "yielded": 0, "max_grade": 0.0, "max_over_m": 0.0})
        rec["rows"] += 1
        if isinstance(r, Diff):
            if r.d <= 0.0:
                continue
            g = abs(float(z[r.a]) - float(z[r.b])) / r.d
            rec["max_grade"] = max(rec["max_grade"], g)
            if fam.startswith("apron") and shape_of:
                sid = max(shape_of.get(r.a, -1), shape_of.get(r.b, -1))   # the labelled end (08p: N is unlabelled)
                sr = by_shape.setdefault(sid, {"rows": 0, "yielded": 0, "max_grade": 0.0})
                sr["rows"] += 1
                sr["max_grade"] = max(sr["max_grade"], g)
                if g > r.cap + tol_g:
                    sr["yielded"] += 1
            if g > r.cap + tol_g:
                rec["yielded"] += 1
                rec["max_over_m"] = max(rec["max_over_m"], (g - r.cap) * r.d)
                if pm is not None:
                    row = {"kind": "diff", "family": fam, "face": _face_of(r), "cap": r.cap,
                           "cap_after": round(g, 6), "distance_m": round(r.d, 4),
                           "ll": [list(pm.vertices[v].key) for v in (r.a, r.b)]}
                    pub.append(row)
                    w = worst.setdefault(fam, [])
                    w.append((g, dict(row, shape=max(shape_of.get(r.a, -1), shape_of.get(r.b, -1)),
                                      vertices=[r.a, r.b])))
                    if len(w) > 64:
                        w.sort(key=lambda t: -t[0])
                        del w[8:]
            continue
        val = sum(c * float(z[v]) for v, c in r.terms)
        over = max(0.0, val - r.hi if r.hi is not None else 0.0,
                   r.lo - val if r.lo is not None else 0.0)
        if over > tol_m:
            rec["yielded"] += 1
            rec["max_over_m"] = max(rec["max_over_m"], over)
            if pm is not None:
                pub.append({"kind": "linear", "family": fam, "face": _face_of(r),
                            "slack_m": round(over, 4),
                            "ll": [list(pm.vertices[v].key) for v, _c in r.terms]})
    for rec in fams.values():
        rec["max_grade"] = round(rec["max_grade"], 6)
        rec["max_over_m"] = round(rec["max_over_m"], 4)
    for sr in by_shape.values():
        sr["max_grade"] = round(sr["max_grade"], 6)
    return {"families": dict(sorted(fams.items())),
            "rows": sum(v["rows"] for v in fams.values()),
            "yielded": sum(v["yielded"] for v in fams.values()),
            "by_shape": dict(sorted(by_shape.items())),
            "worst": {fam: [r for _g, r in sorted(w, key=lambda t: -t[0])[:8]]
                      for fam, w in sorted(worst.items())},
            "published": pub}
