"""AN ADMITTED UNIT WRITTEN WHOLE AT ITS UNDERSIDE ZERO (owner RULINGS
2026-11-25m (4), 25n (2)/(3); spec ``docs/specs/underside-height-map-20261125.md``
§2 S1-S3, step 2; census rows U13, U15-U17).

A footprint unit whose underside map (``airport/unit_underside``) the
admission test passes (``underside_admission.admit``: a recognised
COMPOSITE welded to airside, or MIS-ZEROED with the ground confirming) is
written WHOLE before the mesh: every row of its map as ``OBJECT_MSL`` with
the frame's ``y = 0`` at ``z0 = D - t`` -- ``D`` the level of the pad its
ground contacts stand on (its AIRSIDE contacts first: 25n Q2, a building
touching airside is welded to it) read as the object stage reads a pad
(the median over every face of the ref, ``pad_block_seat.pad_levels`` on
the graded surface's ``building`` faces), ``t`` the floor those contacts
stand at.  A composite whose ``t`` agrees with today's base within
``underside_admission.COHERENT_M`` keeps today's zero ``D - base``: the
two zeros are one (S3 (a), identity).

ONE SEAT PER ROW: the rows go into the rebake's ``exclude`` -- the pack
partition drops them (no body split, no per-body anchor, no unit vote,
touch, carry or post-mesh re-seat: U15-U17's bypass) -- and their records
(seat :data:`SEAT`, ``terrain_shaped.row_seats`` writes them) into
``authored_seats``.  S2: a row of no map (a footless roof, a canopy) whose
plan box stands half or more inside the unit's ground-contact plan rides
it, at ``z0`` plus its lift over the unit's own.

DOUBT KEEPS TODAY'S SEAT (13r; S3, S5): a coherent unit (nothing to
change), a unit off every pad, a row another seat already holds
(``taken``: kept walls and pits, plates, floors, models, shells, portals),
a row carrying a deck of a deck family or a walled plate, a converted
``OBJECT_MSL`` row (``zero_y``), a unit whose rows carry parts of a
grounded unit outside its map (one row cannot take two zeros), and a
unit whose rows disagree on their lift.

Nothing here names a pack, a resource or an airport."""
from __future__ import annotations

import typing as _t

import numpy as np

from .terrain_shaped import UNDERSIDE_SEAT as SEAT
from .underside_admission import COHERENT_M, admit

__all__ = ["SEAT", "ADMITTED", "contact_samples", "unit_pad", "whole_refusal",
           "unit_zero", "seat_records", "log_line"]

#: the verdicts written whole (S3 (b), (c)); (a) coherent stays on today's
#: path: its zero is today's by definition
ADMITTED = ("mis-zeroed", "composite")
#: the most ground contacts a unit's pad lookup reads
SAMPLES_MAX = 64
#: the least share of a rider's plan box inside the unit's plan (S2)
RIDER_SHARE = 0.5
#: the deck kinds of a deck family (S5: never written whole by a building)
_DECK_KINDS = ("flag", "signature")


def contact_samples(m: _t.Any) -> tuple[np.ndarray, np.ndarray]:
    """Up to :data:`SAMPLES_MAX` frame points of ``m``'s ground contacts,
    its airside stations first (25n Q2: the airside it touches sets D)."""
    g = m.layers
    ii, jj = np.nonzero(m.plan & np.isfinite(g.foot))
    e, n = g.centres(ii, jj)
    air = np.asarray(m.airside, dtype=bool)
    if air.any():
        e, n = m.e[air], m.n[air]
    k = max(1, -(-len(e) // SAMPLES_MAX))
    return e[::k], n[::k]


def unit_pad(m: _t.Any, pads: _t.Sequence[_t.Any], to_ll: _t.Callable
             ) -> tuple["str | None", "float | None"]:
    """``(pad ref, D)``: the pad holding the plurality of ``m``'s sampled
    contacts (:func:`contact_samples`; ``placement_family.pad_plurality``,
    folded over every face of its ref) and its level, the median of its
    heights (``pad_block_seat.pad_levels``: the one pad datum rule the
    object stage seats on); ``(None, None)`` off every pad."""
    from .pad_block_seat import pad_levels
    from .placement_family import pad_plurality
    e, n = contact_samples(m)
    if not len(e) or not pads:
        return None, None
    cc = [(*to_ll(float(x), float(y)), 0.0, 0.0) for x, y in zip(e, n, strict=True)]
    p = pad_plurality(cc, pads)
    if p is None:
        return None, None
    lv = pad_levels(pads, [p.ref]).get(p.ref)
    return (str(p.ref), None if lv is None else float(lv))


def _clusters_of_rows(airport) -> dict[str, set[str]]:
    """``{row id: the cluster ids holding a part of it}``."""
    part = getattr(airport, "partition", None)
    if part is None:
        return {}
    row_of = {p.pid: str(m.id) for u in part.units for m in u.members for p in m.parts}
    out: dict[str, set[str]] = {}
    for c in getattr(airport, "clusters", None) or ():
        for q in getattr(c, "pids", ()) or ():
            if q in row_of:
                out.setdefault(row_of[q], set()).add(str(c.id))
    return out


def whole_refusal(m: _t.Any, rows: _t.Sequence[str], by_id: _t.Mapping[str, _t.Any],
                  taken: _t.AbstractSet[str], clusters_of: _t.Mapping[str, set],
                  mapped: _t.AbstractSet[str]) -> "str | None":
    """Why ``m``'s rows cannot be written whole (module doc, DOUBT), or
    ``None``.  ``mapped``: the cluster ids carrying a map (a grounded
    unit); ``clusters_of``: :func:`_clusters_of_rows`."""
    mine = set(str(m.unit).split("+"))
    lifts = set()
    for r in rows:
        o = by_id.get(r)
        if o is None:
            return "row not loaded"
        if r in taken or str(getattr(o, "path", "")) in taken:
            return "row seated by another rule"
        if str(getattr(o, "deck_kind", "") or "") in _DECK_KINDS:
            return "deck family"
        if getattr(o, "walled_plate", None) is not None:
            return "walled plate"
        if float(getattr(o, "zero_y", 0.0) or 0.0) != 0.0:
            return "converted MSL row"
        if (clusters_of.get(r, set()) - mine) & mapped:
            return "row shared with another grounded unit"
        lifts.add(round(float(getattr(o, "agl_m", 0.0) or 0.0), 3))
    if len(lifts) > 1:
        return "rows disagree on their lift"
    return None


def unit_zero(m: _t.Any, verdict: str, D: float) -> float:
    """``z0`` of an admitted map (module doc): ``D - t``; a composite whose
    ``t`` agrees with today's base keeps today's zero ``D - base``."""
    base = float(m.base or 0.0)
    if verdict == "composite" and abs(float(m.t) - base) < COHERENT_M:
        return D - base
    return D - float(m.t)


def _plan_polygon(m: _t.Any, widen_m: float):
    """``m``'s ground-contact plan ``P`` as one frame polygon, widened."""
    from shapely.geometry import box
    from shapely.ops import unary_union
    g = m.layers
    ii, jj = np.nonzero(m.plan)
    e, n = g.centres(ii, jj)
    h = 0.5 * g.step
    cells = [box(x - h, y - h, x + h, y + h) for x, y in zip(e, n, strict=True)]
    return unary_union(cells).buffer(float(widen_m)) if cells else None


def _riders(m: _t.Any, objects: _t.Sequence[_t.Any], free: _t.AbstractSet[str],
            widen_m: float) -> list:
    """S2: the rows of ``free`` (no map, not taken) whose plan box stands
    :data:`RIDER_SHARE` or more inside ``m``'s plan widened by ``widen_m``."""
    from shapely import prepare
    plan, bx = None, None
    out = []
    for o in objects:
        b = getattr(o, "plan_bbox", None)
        if str(o.id) not in free or b is None or b.area <= 0.0:
            continue
        if plan is None:
            plan = _plan_polygon(m, widen_m)
            if plan is None:
                return []
            prepare(plan)
            bx = plan.bounds
        x0, y0, x1, y1 = b.bounds
        if x1 < bx[0] or x0 > bx[2] or y1 < bx[1] or y0 > bx[3]:
            continue
        if b.intersection(plan).area >= RIDER_SHARE * b.area:
            out.append(o)
    return out


def seat_records(airport: _t.Any, pads: _t.Sequence[_t.Any],
                 objects: _t.Sequence[_t.Any], taken: _t.AbstractSet[str],
                 widen_m: float) -> tuple[list[dict[str, _t.Any]], list[dict[str, _t.Any]]]:
    """``(records, report)``: one ``RebakePlan.authored_seats`` record per
    row of every admitted unit and its riders (module doc), and one report
    row per unit S3 admits (its ``z0``, or why it was still refused).
    ``pads``: the graded surface's object pads
    (``placement_read.pads_rims_from_graded_doc``); ``taken``: the rows
    another seat already holds; ``widen_m``: a rider's touch reach."""
    from .underside_composite import dem_many
    maps = [m for m in (getattr(airport, "undersides", None) or {}).values()
            if not m.footless]
    if not maps or not objects:
        return [], []
    to_ll = airport.frame.transformers()[1]
    many = dem_many(airport.dem)
    by_id = {str(o.id): o for o in objects}
    clusters_of = _clusters_of_rows(airport)
    mapped = {u for m in maps for u in str(m.unit).split("+")}
    in_maps = {str(r) for m in maps for r in m.key if not str(r).startswith("@")}
    free = {k for k in by_id if k not in in_maps and k not in taken}
    held: set[str] = set()
    out: list[dict[str, _t.Any]] = []
    report: list[dict[str, _t.Any]] = []
    for m in sorted(maps, key=lambda q: q.key):
        rows = [str(r) for r in m.key if not str(r).startswith("@")]
        pad, D = unit_pad(m, pads, to_ll)
        verdict, det = admit(m, D, np.asarray(many(m.e, m.n), dtype=float))
        if verdict not in ADMITTED or D is None:
            continue
        rep = {"unit": m.unit, "row": rows[0], "rows": len(rows), "pad": pad,
               "D": round(D, 3), "t": round(float(m.t), 3),
               "base": round(float(m.base or 0.0), 3), "verdict": verdict, **det}
        why = whole_refusal(m, rows, by_id, taken | held, clusters_of, mapped)
        if why is not None:
            report.append({**rep, "refused": why})
            continue
        z0 = round(unit_zero(m, verdict, D), 3)
        lift = float(getattr(by_id[rows[0]], "agl_m", 0.0) or 0.0)
        riders = _riders(m, objects, free - held, widen_m)
        rid = {str(o.id) for o in riders}
        for o in [by_id[r] for r in rows] + riders:
            own = float(getattr(o, "agl_m", 0.0) or 0.0)
            held.add(str(o.id))
            out.append({"id": str(o.id), "resource": str(o.path), "datum": "terrain",
                        "seat": SEAT, "unit": str(m.unit)[:120], "pad": pad, "zero": z0,
                        "elevation": round(z0 + own - lift, 3),
                        **({"rider": True} if str(o.id) in rid else {})})
        report.append({**rep, "z0": z0, "riders": len(riders)})
    return out, report


def log_line(icao: str, report: _t.Sequence[_t.Mapping[str, _t.Any]]) -> str:
    """The build log's line on the units written whole."""
    took = [r for r in report if "refused" not in r]
    refused: dict[str, int] = {}
    for r in report:
        if "refused" in r:
            refused[r["refused"]] = refused.get(r["refused"], 0) + 1
    return (f"[{icao}] underside seat: {len(took)} unit(s) written whole "
            f"({sum(int(r['rows']) + int(r.get('riders', 0)) for r in took)} row(s))"
            + (": " + ", ".join(f"{str(r['unit'])[:24]} z0 {r['z0']:.2f} on {r['pad']}"
                                for r in took[:6]) if took else "")
            + (f"; refused {sum(refused.values())}: "
               + ", ".join(f"{k} {v}" for k, v in sorted(refused.items()))
               if refused else ""))
