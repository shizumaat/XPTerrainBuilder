"""THE YIELDING FAMILIES (owner RULINGS 2026-09-08d (2); spec
``heca-v1-parity-spec.md`` §2, consumer census §6.1): v1's priority model
in v2's machinery — the surface families beyond the runway-connected
route graph are PREFERENCES with escalation ceilings, junior to the
runway chord fit (``constraints/runway_chord.py``) and senior to the DEM
fit; they yield where the runway demands, exactly as v1's per-edge caps
did (v1 junction max 9.1 % at HECA), instead of dragging (05C/23C) or
lifting (05L/23R +7.5 m) the runway through their redundant 1.5 %
surfaces (RULINGS 2026-09-07a, 08d).

ONE transform at assembly (:func:`yield_rows`, run by ``pipeline.territory.
territory_constraints`` after the joint filter, never inside a
generator): every HARD ``Diff`` / ``Linear`` selected by a family named
in ``emit.toml [yield] families`` (:data:`FAMILY_SELECTORS`: a generator,
or a ruling-selected subset of one — the ``taxi`` generator's short-pair
box rows, ``no_step``'s §1.1 pairs) becomes a preference row —
``soft = "yield:<family>:<face>:<k>"``, ONE escalation group per row (the
apron precedent, ``constraints/apron.py``: the solver pays for exactly the
relief it uses; the group name carries the family and the face for the
report) — with the escalation CEILING of its class (``taxi_yield_max`` /
``apron_yield_max`` / ``road_yield_max``): a ``Diff``'s ceiling is that
grade; a ``Linear``'s ceiling is the metres its bound may rise, ``|bound|
× (ceiling / cap − 1)`` with ``cap`` the row's face's own longitudinal
cap.  A row whose cap already reaches its class ceiling has nothing to
yield and stays hard.  The runway family, the taxi CHAIN (05ac: centreline
+ lateral hops + crossings), the reach bands, K, the runway transverse
law, pads, structures, zones, strips, seams, the flat datum and the apron
1 % preference rows (already soft) are untouched.

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
from ..law.tables import role_cap, yield_ceiling, yield_law
from ..model.constraints import ConstraintSet, Diff, Linear, Row, Source
from ..model.planar import PlanarMap
from .no_step import GEN as NO_STEP_GEN
from .no_step import PAIR_RULING_PREFIX
from .taxi import BOX_RULING
from .taxi import GEN as TAXI_GEN

__all__ = ["GROUP", "FAMILY_SELECTORS", "YieldStats", "yield_family", "yield_rows",
           "yielded_rows", "groundside_ramps", "RAMP_FAMILY"]

#: The groundside ramp rows' family (their group ``yield:groundside_ramp:…``).
RAMP_FAMILY = "groundside_ramp"

#: The escalation-group prefix of a yielding row (``Weights.preference``
#: key, ``solve/assemble.preference_weight``): ``yield:<family>:<face>:<k>``.
GROUP = "yield"

#: Family name (``emit.toml [yield] families``, ``law/yield_schema.
#: YIELD_FAMILIES``) -> the predicate selecting its rows.
FAMILY_SELECTORS: dict[str, _t.Callable[[Row], bool]] = {
    "junction_mesh": lambda r: r.source.generator == "junction_mesh",
    "taxi_box": lambda r: r.source.generator == TAXI_GEN and r.source.ruling == BOX_RULING,
    "no_step_pairs": lambda r: (r.source.generator == NO_STEP_GEN
                                and r.source.ruling.startswith(PAIR_RULING_PREFIX)),
    "apron": lambda r: r.source.generator == "apron",
    "apron_edge_portion": lambda r: r.source.generator == "apron_edge_portion",
    "roads": lambda r: r.source.generator == "roads",
}


@_dc.dataclass
class YieldStats:
    """What the transform did: rows made preferences per family, rows
    left hard for having nothing to yield."""

    by_family: dict[str, int] = _dc.field(default_factory=dict)
    at_ceiling: dict[str, int] = _dc.field(default_factory=dict)


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


def yield_rows(cs: ConstraintSet, pm: PlanarMap, law: Law,
               stats: YieldStats | None = None) -> ConstraintSet:
    """The set with every selected HARD row a preference (module docstring)."""
    fams = [(name, FAMILY_SELECTORS[name]) for name in yield_law(law).families
            if name in FAMILY_SELECTORS]
    st = stats if stats is not None else YieldStats()
    out: list[Row] = []
    k: dict[str, int] = {}
    for r in cs.rows():
        if not isinstance(r, (Diff, Linear)) or r.soft is not None:
            out.append(r)
            continue
        fam = next((name for name, sel in fams if sel(r)), None)
        if fam is None:
            out.append(r)
            continue
        ceil = yield_ceiling(law, fam)
        if isinstance(r, Diff):
            if ceil is None or r.cap >= ceil:
                st.at_ceiling[fam] = st.at_ceiling.get(fam, 0) + 1
                out.append(r)
                continue
            ceiling = ceil
        else:
            cap = _face_cap(pm, law, r)
            bound = max(abs(x) for x in (r.lo, r.hi) if x is not None) if (
                r.lo is not None or r.hi is not None) else None
            if ceil is None or cap is None or cap >= ceil or bound is None:
                st.at_ceiling[fam] = st.at_ceiling.get(fam, 0) + 1
                out.append(r)
                continue
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
    from ..law.tables import is_value_role, role_side, snap_margin_m
    from .precedence import view
    vw = view(pm, law)
    y = yield_law(law)
    reg = law.tables.precedence.roles
    ground = tuple(r for r in reg if role_side(law, r) == "groundside" and is_value_role(law, r))
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
            if g > r.cap + tol_g:
                rec["yielded"] += 1
                rec["max_over_m"] = max(rec["max_over_m"], (g - r.cap) * r.d)
                if pm is not None:
                    pub.append({"kind": "diff", "family": fam, "face": _face_of(r), "cap": r.cap,
                                "cap_after": round(g, 6), "distance_m": round(r.d, 4),
                                "ll": [list(pm.vertices[v].key) for v in (r.a, r.b)]})
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
    return {"families": dict(sorted(fams.items())),
            "rows": sum(v["rows"] for v in fams.values()),
            "yielded": sum(v["yielded"] for v in fams.values()),
            "published": pub}
