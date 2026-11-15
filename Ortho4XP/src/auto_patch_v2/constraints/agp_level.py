"""THE AGP GROUP'S DATUM, READ ONCE BETWEEN THE STAGES (#2090; spec
``2090-agp-group-groundside-spec.md`` A4 / A5).

The pack stage predicts a group's datum on the DEM (``model/agp_group.
AgpGroup.zero_pred``: the DEM at the governor's ground point plus the chain
step).  That prediction fixes GEOMETRY only — where a plate stands, which
floor a deck joins.  The exact datum is the design surface's: between the
two stages (bound last in ``road_ramp.reach_seed_rewrite``, the one stage-2
rewrite every caller binds) :func:`datum_rewrite` reads ``z_gov``, stage 1's
triangle under the governor's ground point (``face_index.FaceIndex.
terms_at``, as ``group_level.witness_terms``), and ``delta = z_gov - DEM``.
Every row a group's geometry minted — ``Source.inputs`` holding the group
id ``agp:<row>``, or the id of a deck stack whose ``datum_group`` is the
group — has its bounds moved by ``delta``.  Where the triangle is not all
stage 1's, ``delta = 0`` (noted ``agp_datum_unread``).  No second solve.

AFTER THE SOLVE :func:`_final_zero` (through :func:`published_groups`) is
the only reader of a group's datum or
a joined stack's zero (the graded surface's ``agp_groups``, the bridge
rows, the rebake plan's kept decks).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from ..law import Law
from ..model.agp_group import AgpGroup, group_of_input
from ..model.planar import PlanarMap

__all__ = ["REPORT_KEY", "datum_rewrite", "published_groups"]

#: the stage-2 report's key (``DesignReport.reach_seed[REPORT_KEY]``)
REPORT_KEY = "agp_level"


def _read(fi, levels: _t.Mapping[int, float], xy) -> float | None:
    """The design surface's z at ``xy`` on stage 1's ``levels``: its
    triangle's barycentric row, every corner stage 1's; ``None`` else."""
    terms = fi.terms_at((float(xy[0]), float(xy[1])))
    if not terms or any(int(v) not in levels for v, _w in terms):
        return None
    tot = sum(float(w) for _v, w in terms)
    if tot <= 0.0:
        return None
    return sum(float(w) * float(levels[int(v)]) for v, w in terms) / tot


def _tagged(row, gid_of_stack: _t.Mapping[str, str]) -> str | None:
    """The group a row names (its inputs: the group id, or a joined
    stack's id), or ``None``."""
    for t in getattr(row.source, "inputs", ()) or ():
        g = group_of_input(t) or gid_of_stack.get(str(t))
        if g is not None:
            return g
    return None


def datum_rewrite(planar: PlanarMap, law: Law, cs: _t.Any,
                  levels: _t.Mapping[int, float]) -> "tuple[_t.Any, dict]":
    """``(cs with every group-tagged Band / Pin moved by its delta,
    report)`` (module doc).  The report is ``{"groups": {gid: {"z_gov",
    "delta", "unread", "stage1": [member rows on stage 1's faces],
    "moved": n}}}``."""
    groups = [g for g in getattr(planar, "agp_groups", ()) or () if g.governor]
    if not groups:
        return cs, {"groups": {}}
    from .face_index import FaceIndex
    fi = FaceIndex(planar, law)
    rep: dict[str, dict] = {}
    delta: dict[str, float] = {}
    for g in groups:
        gm = g.member(g.governor)
        z = _read(fi, levels, gm.ground_xy)
        unread = z is None or g.dem_gov is None
        d = 0.0 if unread else float(z) - float(g.dem_gov)
        delta[g.id] = d
        rep[g.id] = {"z_gov": None if unread else round(float(z), 4),
                     "dem_gov": None if g.dem_gov is None else round(float(g.dem_gov), 4),
                     "delta": round(d, 4), "unread": bool(unread),
                     "why": "agp_datum_unread: the governor's triangle is not all stage 1's"
                     if unread else "",
                     "stage1": sorted(m.row for m in g.members if m.row != g.governor
                                      and _read(fi, levels, m.ground_xy) is not None),
                     "moved": 0}
    stacks = {str(st.id): str(st.datum_group)
              for st in getattr(planar, "bridge_stacks", None) or ()
              if getattr(st, "datum_group", None)}

    def _move(rows, shift):
        out = []
        for r in rows:
            g = _tagged(r, stacks)
            if g is None or g not in delta or delta[g] == 0.0:
                out.append(r)
                continue
            rep[g]["moved"] += 1
            out.append(shift(r, delta[g]))
        return tuple(out)
    bands = _move(cs.bands, lambda r, d: _dc.replace(
        r, lo=None if r.lo is None else r.lo + d, hi=None if r.hi is None else r.hi + d))
    pins = _move(cs.pins, lambda r, d: _dc.replace(r, z=r.z + d))
    if not any(v["moved"] for v in rep.values()):
        return cs, {"groups": rep}
    return _dc.replace(cs, bands=bands, pins=pins), {"groups": rep}


def _final_zero(group: AgpGroup, report: "_t.Mapping | None") -> dict[str, _t.Any]:
    """AFTER THE SOLVE, the one reader of a group's datum (A5): ``{"z_gov",
    "delta", "unread", "datum": {row: z}}`` — each member's datum is its
    predicted zero plus the group's delta.  An unpredicted group (no
    governor) reads ``None`` throughout."""
    r = ((report or {}).get("groups") or {}).get(group.id) or {}
    d = float(r.get("delta") or 0.0)
    datum = {}
    for m in group.members:
        z = group.zero_pred(m.row)
        datum[m.row] = None if z is None else round(z + d, 4)
    z_gov = r.get("z_gov")
    if z_gov is None and group.governor is not None:
        z_gov = datum.get(group.governor)
    return {"z_gov": z_gov, "delta": round(d, 4), "unread": bool(r.get("unread", True)),
            "datum": datum, "stage1": list(r.get("stage1") or ())}


def published_groups(groups: _t.Sequence[AgpGroup], report: "_t.Mapping | None"
                     ) -> list[dict[str, _t.Any]]:
    """The graded surface's ``agp_groups`` (A5): per group its id, governor,
    ``z_gov``, ``delta``, per member its row, index, resource, ground point,
    datum and whether it reads as airside or stands on stage 1's faces
    (A7: never moved), the joins with their votes, the deck joins and the
    plates."""
    out = []
    for g in groups:
        fz = _final_zero(g, report)
        out.append({
            "id": g.id, "governor": g.governor, "why": g.why,
            "z_gov": fz["z_gov"], "delta": fz["delta"], "unread": fz["unread"],
            "members": [{"row": m.row, "index": m.index, "resource": m.resource,
                         "ground": [m.ground_ll[0], m.ground_ll[1]],
                         "step": m.step, "datum": fz["datum"].get(m.row),
                         "airside": m.row in g.airside,
                         "stage1": m.row in fz["stage1"],
                         "airside_m": None if not math.isfinite(m.airside_m)
                         else m.airside_m} for m in g.members],
            "joins": [{"a": j.a, "b": j.b, "step": j.step, "votes": j.votes,
                       "rival": j.rival, "contact": list(j.contact_ll)} for j in g.joins],
            "deck_joins": [dict(d) if isinstance(d, _t.Mapping) else _record(d, fz)
                           for d in g.deck_joins],
            "plates": [dict(p) if isinstance(p, _t.Mapping) else _record(p, fz)
                       for p in g.plates]})
    return out


def _record(x: _t.Any, fz: _t.Mapping) -> dict:
    """A deck join's / plate's published record (its own ``published``)."""
    pub = getattr(x, "published", None)
    return pub(float(fz["delta"])) if callable(pub) else {}
