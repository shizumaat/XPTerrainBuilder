"""ISSUE #10 [HECA-5]: THE CONTENTS-APART CENSUS — every written body
whose PART IDS the plan-wide §16g map puts in a footprint unit, against
that unit's datum.

A unit is ONE rigid object at ONE zero (§16g (2)); its contents (S6, the
windows, doors, glass and floors of a terminal) are in it by part id, so
a written body whose own zero ``surface_z - y_zero`` stands off the
unit's datum is a piece of the building rendered at another level — the
owner's "missing interiors / levels separated" read.  The census reads
the SAME map the stage seated by (``SplitSet.plan_wide``) and the
records' own anchors; it re-derives nothing.

The rule that seated each such body is named from its anchor reason, so
the residue is attributed by mechanism: a carrier at another level
(``carried``), §16c (7)'s contact cluster (``cluster``), the body's own
ground (``own_surface`` / ``low_side_foot`` / ``own_ground``), a line
object's segment (``line_segment``, §10 / 11f (2) by design), or a unit
seat of another unit or block (``unit_seat``)."""
from __future__ import annotations

import collections
import typing as _t

__all__ = ["census_unit_levels", "census_unit_levels_lines", "seat_rule"]

_RULES = (("§16g unit", "unit_seat"), ("footless_carried_by_unit", "unit_carry"),
          ("carried by", "carried"), ("footless_own_ground", "own_ground"),
          ("low-side foot", "low_side_foot"), ("line segment", "line_segment"),
          ("§16c (7)", "cluster"), ("surface at the body's zero", "own_surface"))


def seat_rule(reason: str) -> str:
    """The seating rule an anchor reason names (first match wins)."""
    for key, name in _RULES:
        if str(reason).startswith(key) or (key == "§16c (7)" and key in reason):
            return name
    return "other"


def census_unit_levels(ss: _t.Any, *, visual_m: float = 0.5,
                       top: int = 10) -> dict:
    """Per body with unit pids: the unit holding most of them, its datum,
    and the body's offset; rolled up by rule and by unit."""
    pw = getattr(ss, "plan_wide", None) or {}
    datum: dict[str, float] = {}
    for row in pw.values():
        if row[1] is not None:
            datum.setdefault(str(row[0]), float(row[1]))
    n = 0
    off: list[tuple[float, str, str, str, float, float]] = []
    for s in ss.all:
        for b in s.bodies:
            hit = collections.Counter(str(pw[q][0]) for q in b.pids if q in pw)
            if not hit:
                continue
            uid = max(sorted(hit), key=lambda k: hit[k])
            a = b.anchor
            if a.surface_z is None or uid not in datum:
                continue
            n += 1
            d = float(a.surface_z) - float(a.y_zero) - datum[uid]
            if abs(d) > visual_m:
                off.append((d, uid, b.new_resource or s.resource,
                            seat_rule(a.reason), a.lat, a.lon))
    by_rule: dict[str, list[float]] = {}
    by_unit: dict[str, list[float]] = {}
    for d, uid, _r, rule, _la, _lo in off:
        by_rule.setdefault(rule, []).append(abs(d))
        by_unit.setdefault(uid, []).append(abs(d))
    off.sort(key=lambda q: -abs(q[0]))
    return {"bodies": n, "visual_m": visual_m, "off": len(off),
            "off_gt_2m": sum(1 for q in off if abs(q[0]) > 2.0),
            "worst": off[:top],
            "by_rule": {k: (len(v), max(v)) for k, v in
                        sorted(by_rule.items(), key=lambda kv: -len(kv[1]))},
            "by_unit": {k: (len(v), max(v)) for k, v in
                        sorted(by_unit.items(), key=lambda kv: -len(kv[1]))[:top]}}


def census_unit_levels_lines(c: _t.Mapping[str, _t.Any]) -> list[str]:
    out = [f"CONTENTS APART (issue #10): {c['bodies']} body(ies) whose parts "
           f"are a §16g unit's; {c['off']} stand more than {c['visual_m']:g} m "
           f"off their unit's datum ({c['off_gt_2m']} > 2 m)"]
    if c["by_rule"]:
        out.append("  by seating rule: " + ", ".join(
            f"{k} {n} (worst {w:.2f} m)" for k, (n, w) in c["by_rule"].items()))
    for k, (n, w) in c["by_unit"].items():
        out.append(f"    {k}: {n} (worst {w:.2f} m)")
    for d, uid, res, rule, la, lo in c["worst"]:
        out.append(f"    {d:+7.2f} m  {uid}  {str(res).rsplit('/', 1)[-1]}  "
                   f"[{rule}]  {la:.6f},{lo:.6f}")
    return out
