"""THE COHERENCE CENSUSES — does a group stay one group, does a bridge
meet its approaches, does a frame's content stay in it (owner RULINGS
2026-10-22b..f, #1214).

Owner, KMCI 1.0.415: "The terminal is not floating but it also came
apart, is now below ground leaving interior components floating in the
air.  Bridges are under ground: it's just their ends that should be set
at ground level.  Multiple bridges have their decks separating from their
edges, they should always move as a group."  Every bar #1251 was judged
on read a body's zero against its own feet; none of these three, so the
plan passed while the sim failed.  The instruments, over the placement
plan's own rows (the ``to_dict`` shape every census here reads):

* :func:`census_group_offsets` — the bodies of ONE group (one §16g unit /
  family, or one placement of an OPEN frame — a bridge, a canopy) at
  different zeros;
* :func:`census_bridge_ends` — a free-standing deck's NEARER end more
  than ``end_tol_m`` off its approach ground, an end UNDER its approach,
  and a deck SPAN under the ground (10-22m: the other end's gap is the
  terrain's to grade, #1138, and is listed, not barred);
* :func:`census_frame_riders` — a lifted row standing in a re-seated
  frame that did not move with it, or stands under the ground.

The relations are the law's own functions (``frame_riders``,
``anchor_rule._approach_ends``), never copies.  Bars are 0.
"""
from __future__ import annotations

import collections
import typing as _t

__all__ = ["census_group_offsets", "census_bridge_ends", "census_frame_riders",
           "coherence_lines", "GROUP_TOL_M", "END_TOL_M", "RIDER_TOL_M"]

#: one group, one zero: ``[placement] split_tol_m``'s 0.3 m
GROUP_TOL_M = 0.3
#: a bridge end meets the road onto it within the visual bar
END_TOL_M = 0.5
#: a rider stays on its frame within the visual bar
RIDER_TOL_M = 0.5

Surface = _t.Callable[[float, float], "float | None"]

#: the bodies a group may lawfully hold at other zeros: §10 line segments
#: and §14a basin arcs drape by ruling
_DRAPED = ("line_segment",)


def _zero(b: _t.Mapping[str, _t.Any]) -> "float | None":
    sz = b.get("surface_z")
    if sz is None:
        return None
    return float(sz) - float(b.get("y_zero", 0.0)) + float(b.get("lift_m", 0.0) or 0.0)


def census_group_offsets(splits: _t.Sequence[_t.Mapping[str, _t.Any]],
                         open_resources: _t.AbstractSet[str] = frozenset(),
                         tol_m: float = GROUP_TOL_M) -> dict:
    """Groups whose bodies stand at more than ``tol_m`` of zero spread:
    every §16g unit / family (``family_of``) and every placement of an
    OPEN frame (``open_resources``: its member resources)."""
    groups: dict[str, list[tuple[float, str]]] = collections.defaultdict(list)
    for s in splits:
        res = str((s.get("placement") or {}).get("resource", ""))
        idx = (s.get("placement") or {}).get("index")
        for b in s.get("bodies", ()):
            z = _zero(b)
            if z is None or b.get("class") in _DRAPED or "basin rim arc" in str(
                    b.get("anchor_reason", "")):
                continue
            key = b.get("family_of") or ""
            if key:
                groups[f"unit {key}"].append((z, res))
            if res in open_resources:
                groups[f"open {res}#{idx}"].append((z, res))
    bad = []
    for k, v in groups.items():
        zs = [z for z, _r in v]
        if len(zs) >= 2 and max(zs) - min(zs) > tol_m:
            bad.append((max(zs) - min(zs), k, len(zs)))
    bad.sort(reverse=True)
    return {"groups": len(groups), "apart": len(bad), "worst": bad[:10],
            "tol_m": tol_m}


def census_bridge_ends(splits: _t.Sequence[_t.Mapping[str, _t.Any]],
                       decks: _t.Sequence[_t.Any], surface: Surface, *,
                       step_m: float, walk_max_m: float,
                       end_tol_m: float = END_TOL_M) -> dict:
    """Per free-standing deck member (``decks``: rebake ``Member``-shaped
    objects with ``resource``, ``deck_top_y``, ``deck_ends``): each END's
    offset from its APPROACH ground (the highest land reading on the
    landward walk, ``anchor_rule._approach_ends``) and the deck SPAN under
    the ground at the deck's mid-line."""
    from .anchor_rule import Datum, _approach_ends
    zeros: dict[str, list[float]] = collections.defaultdict(list)
    for s in splits:
        res = str((s.get("placement") or {}).get("resource", ""))
        for b in s.get("bodies", ()):
            z = _zero(b)
            if z is not None:
                zeros[res].append(z)
    water = getattr(surface, "water", None)
    rows, ends_off, spans_under = [], 0, 0
    for m in decks:
        ends = tuple(tuple((float(q[0]), float(q[1])) for q in ln)
                     for ln in (getattr(m, "deck_ends", None) or ()))
        top = getattr(m, "deck_top_y", None)
        zs = sorted(zeros.get(str(m.resource), ()))
        if top is None or len(ends) < 2 or not zs:
            continue
        zero = zs[len(zs) // 2]
        got = _approach_ends(Datum(float(top), (), "deck top", ends=ends,
                                   step_m=step_m, walk_max_m=walk_max_m),
                             surface, water)
        if got is None:
            continue
        offs = [zero + float(top) - g for g in got[1]]
        mid = (0.25 * sum(q[0] for ln in ends for q in ln),
               0.25 * sum(q[1] for ln in ends for q in ln))
        gm = surface(*mid)
        under = None if gm is None else zero + float(top) - float(gm)
        # 10-22m: the NEARER end is flush; the other end floats over its
        # approach by the gap the terrain must grade up (#1138) — only an
        # end UNDER its approach, or a nearest end off it, is the seat's
        n_off = (int(abs(min(offs)) > end_tol_m)
                 + sum(1 for o in offs if o < -end_tol_m and o != min(offs)))
        ends_off += n_off
        spans_under += int(under is not None and under < 0.0)
        rows.append((str(m.resource), offs, under))
    return {"bridges": len(rows), "ends_off": ends_off,
            "spans_under": spans_under, "rows": rows, "end_tol_m": end_tol_m}


def census_frame_riders(dump: _t.Any, splits: _t.Sequence[_t.Any],
                        msl_seats: _t.Sequence[_t.Mapping[str, _t.Any]],
                        surface: Surface, tol_m: float = RIDER_TOL_M) -> dict:
    """Lifted rows standing in a re-seated frame (``frame_riders``'s own
    population, read on the plan's MODEL records ``splits``) whose written
    height is off the frame-relative one, or under the ground."""
    from .frame_riders import _frames, _lift
    splits = [_as_record(q) for q in splits]
    rows = list(getattr(dump, "placements", ()) or ())
    written = {int(m["index"]): float(m["elevation"]) for m in msl_seats}
    frames = _frames(splits, rows, surface)
    split_idx = {int(q.placement.index) for q in splits}
    n = off = under = 0
    worst: list[tuple[float, str]] = []
    for i, row in enumerate(rows):
        lift = _lift(row)
        if lift <= 0.0 or i in split_idx:
            continue
        la, lo = float(row.lat), float(row.lon)
        for move, boxes in frames:
            if not any(b[0] <= la <= b[2] and b[1] <= lo <= b[3] for b in boxes):
                continue
            g = surface(la, lo)
            if g is None:
                break
            z = written.get(i, float(g) + lift)
            want = max(float(g) + lift + move, float(g))
            n += 1
            if abs(z - want) > tol_m:
                off += 1
                worst.append((z - want, str(row.def_path)))
            if z < float(g) - tol_m:
                under += 1
            break
    worst.sort(key=lambda q: -abs(q[0]))
    return {"riders": n, "off_frame": off, "under_floor": under,
            "worst": worst[:8], "tol_m": tol_m}


def _as_record(s: _t.Any) -> _t.Any:
    """A plan row (``to_dict`` shape) in the attribute shape the law's
    functions read; a model record passes through."""
    import types
    if not isinstance(s, _t.Mapping):
        return s
    pl = types.SimpleNamespace(index=int((s.get("placement") or {}).get("index", -1)))
    bodies = tuple(types.SimpleNamespace(
        surface_z=b.get("surface_z"), y_zero=float(b.get("y_zero", 0.0)),
        lift_m=float(b.get("lift_m", 0.0) or 0.0),
        plan_box=None if b.get("plan_box") is None else tuple(b["plan_box"]))
        for b in s.get("bodies", ()))
    return types.SimpleNamespace(placement=pl, bodies=bodies)


def coherence_lines(groups: "dict | None", bridges: "dict | None",
                    riders: "dict | None") -> list[str]:
    """The three bars as the lines the tools print."""
    out = ["   --- COHERENCE (owner RULINGS 2026-10-22b..f, #1214) ---"]
    if groups is not None:
        out.append(f"   group offsets: {groups['apart']} of {groups['groups']} "
                   f"group(s) with zeros spread > {groups['tol_m']:g} m (bar 0)"
                   + ("" if not groups["apart"] else "   *** VIOLATED ***"))
        for d, k, n in groups["worst"][:5]:
            out.append(f"      {d:6.2f} m  {k} ({n} bodies)")
    if bridges is not None:
        out.append(f"   bridge ends off the approach > {bridges['end_tol_m']:g} m "
                   f"(nearer end, or any end under it): "
                   f"{bridges['ends_off']}; spans under the ground: "
                   f"{bridges['spans_under']} ({bridges['bridges']} bridge(s); bar 0)"
                   + ("" if not (bridges["ends_off"] or bridges["spans_under"])
                      else "   *** VIOLATED ***"))
        for res, offs, under in bridges["rows"]:
            out.append(f"      {res.rsplit('/', 1)[-1]:28s} ends "
                       + " / ".join(f"{o:+.2f}" for o in offs)
                       + f"  far-end gap to grade (#1138) {max(offs) - min(offs):.2f} m"
                       + ("" if under is None else f"  span {under:+.2f}"))
    if riders is not None:
        out.append(f"   frame riders off their frame > {riders['tol_m']:g} m: "
                   f"{riders['off_frame']}; under the ground: {riders['under_floor']} "
                   f"(of {riders['riders']}; bar 0)"
                   + ("" if not (riders["off_frame"] or riders["under_floor"])
                      else "   *** VIOLATED ***"))
        for d, res in riders["worst"][:5]:
            out.append(f"      {d:+6.2f} m  {res}")
    return out
