"""THE GROUP'S LOWER LEVEL IS HELD AT THE GROUP'S ZERO (#1214 round 7; owner
RULINGS 2026-10-23b/e, implemented as 2026-10-23f; ``planar/group_low``).

A held pad graded as its group's lower level (record ``witness`` =
``group``) stands where the object stage will seat the group: at the
group's zero -- the stand-side airside floor,
``airside_group_seat.airside_zeros``' ``floor_plane`` of ``airside z - y``
over the group's stand-side walls -- plus the pad's own foot plane
``y_feet``.  Its pad's datum is NOT that zero (LFPG T2: the trench pads'
datums are the apron beside them, 103.2-104.1 m; the stands' apron is
105.2 m).

Each witness the record carries (a stand-side foot: frame xy, authored y)
reads the airside the way the object stage does: the foot, else the first
of its four :data:`TOUCH_M` probes standing on airside pavement (the
rolled-on roles), and there the design surface's own triangle
(``face_index.FaceIndex.terms_at``: the barycentric row over three
vertices).

* :func:`group_level_rows` (the generator, ``platform.landing_rows``):
  one vertex ``d`` of the level is tied to the MEAN of the witnesses'
  ``airside z - y`` plus ``y_feet``, every other vertex rigid to ``d``.
  The witnesses are the feet in their floor's band (``planar/group_low``):
  the object stage's floor is the highest dense plane of candidates, and
  the mean of every stand-side foot reads it a metre low (MEASURED LFPG
  T2: 104.2 m against 105.2).  The tie reads stage 1's vertices only (:func:`witness_terms`), and
  between the stages :func:`group_level_rewrite` replaces it by a PIN at
  the same mean read on stage 1's solved levels, so the airside never
  moves for the level.

The level is not on stage 1's map (``planar/group_low.stage_one``), so the
airside never follows it.  The rows' input is ``low_level:<ref>``, the one
row ``constraints/riser`` lets span the riser.
"""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..model.constraints import Linear, Row, Source
from ..model.planar import PlanarMap

__all__ = ["TOUCH_M", "LANDING_INPUT", "witness_index", "witness_terms",
           "group_level_rows", "group_level_rewrite"]

#: the object stage's airside touch (``airside_group_seat.TOUCH_M``)
TOUCH_M = 1.0
#: the input id a lower level's rows carry (``constraints/riser``'s
#: ``LANDING_INPUT_PREFIX``)
LANDING_INPUT = "low_level:"
_PROBES = ((0.0, 0.0), (1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0))


def witness_index(planar: PlanarMap, law: Law
                  ) -> "tuple[_t.Any, frozenset[str], frozenset[int]]":
    """``(face index, airside pavement roles, stage 1's vertices)`` the
    witnesses are read on -- stage 1's population (``model/platform.
    stage_air_vertices`` and each held block's datum column, the set
    ``solve/design_roles.airside_stage_vertices`` solves first)."""
    from ..law import tables as _T
    from ..model.platform import datum_vertices, stage_air_vertices
    from .face_index import FaceIndex
    s1 = set(stage_air_vertices(planar, law))
    s1.update(datum_vertices(planar, law, s1).values())
    return FaceIndex(planar, law), frozenset(_T.rolled_on_roles(law)), frozenset(s1)


def witness_terms(rec: _t.Mapping[str, _t.Any], index: "tuple[_t.Any, frozenset[str], _t.Any]",
                  keep: "_t.Container[int] | None" = None
                  ) -> list[tuple[tuple[tuple[int, float], ...], float]]:
    """``[(row, foot y)]`` of every witness of ``rec`` that stands on
    airside pavement or within :data:`TOUCH_M` of it: the barycentric row
    of its triangle over stage 1's vertices only, renormalised -- a vertex
    a pad shares with the apron is stage 2's, and a tie naming it would
    pull the airside to the level (MEASURED LFPG replay: a hall pad's apron
    rose 0.74 m); a witness reading none of stage 1's is dropped.  ``keep``
    (default: stage 1's vertices) narrows the vertices read."""
    fi, rolled, s1 = index
    s1 = s1 if keep is None else keep
    out = []
    for (x, y), yf in zip(rec.get("air_xy") or (), rec.get("air_y") or (), strict=True):
        for dx, dy in _PROBES:
            p = (float(x) + dx * TOUCH_M, float(y) + dy * TOUCH_M)
            if fi.role_at(p) in rolled:
                t = [(int(v), float(w)) for v, w in fi.terms_at(p) or () if int(v) in s1]
                tot = sum(w for _v, w in t)
                if t and tot > 0.0:
                    out.append((tuple((v, w / tot) for v, w in t), float(yf)))
                break
    return out


def _rigid(vs: _t.Sequence[int], d: int, src: Source) -> list[Row]:
    rows: list[Row] = []
    for v in vs:
        if int(v) != d:
            rows.append(Linear(((int(v), 1.0), (d, -1.0)), None, 0.0, src))
            rows.append(Linear(((int(v), -1.0), (d, 1.0)), None, 0.0, src))
    return rows


def _tie(d: int, wt: _t.Sequence[tuple[tuple[tuple[int, float], ...], float]],
         y_feet: float, src: Source) -> list[Row]:
    """``z_d - mean(sum w z) = y_feet - mean(y)`` over the witnesses ``wt``
    (``[(barycentric row, foot y)]``), both sides."""
    acc: dict[int, float] = {}
    for terms, _y in wt:
        for v, w in terms:
            acc[int(v)] = acc.get(int(v), 0.0) + float(w) / len(wt)
    rhs = float(y_feet) - sum(y for _r, y in wt) / len(wt)
    tie = ((d, 1.0), *((a, -c) for a, c in sorted(acc.items()) if a != d))
    return [Linear(tie, None, rhs, src), Linear(tuple((q, -c) for q, c in tie), None, -rhs, src)]


def group_level_rows(ref: str, vs: _t.Sequence[int], rec: _t.Mapping[str, _t.Any],
                     src: Source, index: "tuple[_t.Any, frozenset[str]]") -> list[Row]:
    """The rows holding the lower level ``ref`` (its vertices ``vs``) at
    the witnesses' mean ``airside z - y`` plus its foot plane, rigid
    (module docstring); ``[]`` where no witness stands on the airside."""
    wt = witness_terms(rec, index)
    if not wt or not vs:
        return []
    d = int(vs[0])
    return [*_tie(d, wt, float(rec["y_feet"]), src), *_rigid(vs, d, src)]


def group_level_rewrite(planar: PlanarMap, law: Law, cs: _t.Any,
                        levels: _t.Mapping[int, float]) -> "tuple[_t.Any, dict]":
    """BETWEEN THE STAGES (bound in ``road_ramp.reach_seed_rewrite``, the
    one stage-2 rewrite every caller binds): ``cs`` with every group lower
    level's tie (its rows naming more than two vertices) replaced by ``d``
    PINNED at the witnesses' mean ``airside z - y`` on stage 1's solved
    airside ``levels`` plus ``y_feet``.  A vertex stage 1 levelled is a
    constant of stage 2, but the door pads' blend releases some of stage
    1's own (``door_pad.blend_release``): a tie naming one pulled a hall
    pad's apron 0.99 m (MEASURED LFPG replay), a pin pulls none.  The
    report is ``{"levels": {ref: (zero, witnesses read)}}``."""
    import dataclasses as _dc
    lands = getattr(getattr(planar, "registries", None), "landings", None) or {}
    recs = {r: v for r, v in lands.items()
            if v.get("kind") == "low_level" and v.get("air_xy")}
    if not recs or not cs.linears:
        return cs, {"levels": {}}
    index = witness_index(planar, law)
    tie = {f"{LANDING_INPUT}{r}": r for r in recs}
    out, rep, done = [], {}, set()
    for row in cs.linears:
        ins = getattr(row.source, "inputs", ()) or ()
        ref = tie.get(str(ins[0])) if ins else None
        if ref is None or len(row.terms) <= 2:
            out.append(row)
            continue
        if ref in done:
            continue                                  # the tie's other side
        cands = [sum(w * float(levels[v]) for v, w in terms) - y
                 for terms, y in witness_terms(recs[ref], index, levels)]
        if not cands:
            out.append(row)                           # no witness stage 1 read: the tie
            continue
        done.add(ref)
        z0 = sum(cands) / len(cands)
        d = int(row.terms[0][0])
        lv = z0 + float(recs[ref]["y_feet"])
        rep[ref] = (round(z0, 3), len(cands))
        out.append(Linear(((d, 1.0),), None, lv, row.source))
        out.append(Linear(((d, -1.0),), None, -lv, row.source))
    return _dc.replace(cs, linears=tuple(out)), {"levels": rep}
