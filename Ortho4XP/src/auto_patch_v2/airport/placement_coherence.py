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
  than ``end_tol_m`` off the ground at its end line, an end UNDER it,
  and a deck SPAN under the ground (10-22m: the other end's gap is the
  terrain's to grade, #1138, and is listed, not barred);
* :func:`census_frame_riders` — a lifted row standing in a re-seated
  frame that did not move with it, or stands under the ground.

The relations are the law's own functions (``frame_riders``,
``bridge_approach``), never copies.  Bars are 0.
"""
from __future__ import annotations

import collections
import typing as _t

__all__ = ["census_group_offsets", "census_bridge_ends", "census_frame_riders",
           "plan_body_zero", "coherence_lines", "GROUP_TOL_M", "END_TOL_M", "RIDER_TOL_M"]

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


def plan_body_zero(b: _t.Mapping[str, _t.Any]) -> "float | None":
    """Where a plan body (its ``to_dict`` row) puts the AUTHORED zero in
    world height: the design surface at its anchor, minus its intended
    zero, plus the lift its row keeps; ``None`` off every graded face.
    The censuses here and the patch editor's object inspector (#1702)
    read the seat through this one function."""
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
            z = plan_body_zero(b)
            if z is None or b.get("class") in _DRAPED or "basin rim arc" in str(
                    b.get("anchor_reason", "")):
                continue
            key = b.get("family_of") or ""
            if key:
                # one zero per unit PER FRAME: two frames chained into one
                # unit keep their authored relation, each at its own lift
                # (#1214 round 3, RULINGS 2026-10-22o)
                pl = s.get("placement") or {}
                fr = f"{float(pl.get('lat', 0.0)):.6f},{float(pl.get('lon', 0.0)):.6f}"
                groups[f"unit {key} frame {fr}"].append((z, res))
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
                       step_m: float, walk_max_m: float = 0.0,
                       end_tol_m: float = END_TOL_M, touch_m: float = 0.0) -> dict:
    """Per free-standing BRIDGE (``decks``: ``(unit, member)`` pairs of the
    rebake plan, or bare members; a unit's decks whose rings touch at
    ``touch_m`` are one bridge, ``free_bridge_seat.bridge_groups``): each
    END's offset from the ground AT its end line and the deck SPAN under
    the ground at the deck's mid-line.  The ends are read by the seat's own
    function (``deck_end_read.deck_end_reads``: the ground the end meets,
    the plate's own top on it); an end abutting another deck of its bridge
    is no land end and never barred.  A deck the law holds at its AUTHORED
    CLEARANCE (no embankment at either end, RULINGS 2026-10-22p) is listed
    and never barred."""
    import types
    from .deck_end_read import deck_end_reads
    from .free_bridge_seat import _abuts, _rings_local, bridge_groups
    from .placement_family import frame_is_bridge
    zeros: dict[str, list[float]] = collections.defaultdict(list)
    for s in splits:
        res = str((s.get("placement") or {}).get("resource", ""))
        for b in s.get("bodies", ()):
            z = plan_body_zero(b)
            if z is not None:
                zeros[res].append(z)
    by_unit: dict[int, tuple[_t.Any, list]] = {}
    for item in decks:
        u, m = item if isinstance(item, tuple) else (None, item)
        if getattr(m, "deck_top_y", None) is None or len(getattr(m, "deck_ends", None) or ()) < 2 \
                or not zeros.get(str(m.resource)):
            continue
        by_unit.setdefault(id(u) if u is not None else id(m), (u, []))[1].append(m)
    rows, ends_off, spans_under = [], 0, 0
    for u, ms in by_unit.values():
        origin = tuple(u.anchor) if u is not None else (
            float(ms[0].deck_ends[0][0][0]), float(ms[0].deck_ends[0][0][1]))
        agl = float(getattr(u, "agl_m", 0.0) or 0.0) if u is not None else 0.0
        all_deck = u is None or frame_is_bridge(u)
        staged = [types.SimpleNamespace(m=m) for m in ms]
        ringed = not all_deck and all(len(getattr(m, "deck_ring", None) or ()) >= 3
                                      for m in ms)
        groups = (bridge_groups(staged, origin, touch_m) if ringed
                  else [[i] for i in range(len(ms))])
        rings = _rings_local(staged, origin) if ringed else []
        for group in groups:
            offs_land: list[float] = []
            for i in group:
                m = ms[i]
                zs = sorted(zeros[str(m.resource)])
                zero = zs[len(zs) // 2]
                r = deck_end_reads(m, surface, origin=origin, agl_m=agl, step_m=step_m,
                                   walk_max_m=walk_max_m, all_deck=all_deck)
                if r is None:
                    continue
                clearance = r.clearance is not None
                offs = [zero + e.top - e.ground for e in r.ends]
                land = [o for e, o in zip(r.ends, offs, strict=True)
                        if not (rings and _abuts(e.line, [rings[j] for j in group if j != i],
                                                 origin, touch_m))]
                if not clearance:
                    offs_land.extend(land)
                ends = tuple(tuple((float(q[0]), float(q[1])) for q in ln) for ln in m.deck_ends)
                mid = (0.25 * sum(q[0] for ln in ends[:2] for q in ln),
                       0.25 * sum(q[1] for ln in ends[:2] for q in ln))
                gm = surface(*mid)
                under = None if gm is None else zero + float(m.deck_top_y) - float(gm)
                spans_under += int(under is not None and under < 0.0)
                rows.append((str(m.resource), offs, under, clearance))
            # 10-22m: the NEAREST land end of the bridge is flush; every
            # other end floats over its approach by the gap the terrain must
            # grade up (#1138) — only an end UNDER its approach, or a nearest
            # end off it, is the seat's
            if offs_land:
                lo = min(offs_land)
                ends_off += int(abs(lo) > end_tol_m) + sum(
                    1 for o in offs_land if o < -end_tol_m and o != lo)
    return {"bridges": len(rows), "ends_off": ends_off,
            "spans_under": spans_under, "rows": rows, "end_tol_m": end_tol_m}


def census_frame_riders(dump: _t.Any, splits: _t.Sequence[_t.Any],
                        msl_seats: _t.Sequence[_t.Mapping[str, _t.Any]],
                        surface: Surface, tol_m: float = RIDER_TOL_M,
                        authored_seats: _t.Sequence[_t.Mapping[str, _t.Any]] = ()) -> dict:
    """Lifted rows standing in a re-seated frame (``frame_riders``'s own
    population, read on the plan's MODEL records ``splits``) whose written
    height is off the frame-relative one, or under the ground.
    ``authored_seats``: the rebake plan's (an adapted row's frame is
    measured from its record, as the writer measures it)."""
    from .adapted_riders import authored_zeros
    from .frame_riders import _frames, _lift
    splits = [_as_record(q) for q in splits]
    rows = list(getattr(dump, "placements", ()) or ())
    written = {int(m["index"]): float(m["elevation"]) for m in msl_seats}
    frames = _frames(splits, rows, surface, authored_zeros(authored_seats))
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
        for res, offs, under, clear in bridges["rows"]:
            out.append(f"      {res.rsplit('/', 1)[-1]:28s} ends "
                       + " / ".join(f"{o:+.2f}" for o in offs)
                       + ("  AUTHORED CLEARANCE (22p): end gaps listed for #1138"
                          if clear else
                          f"  far-end gap to grade (#1138) {max(offs) - min(offs):.2f} m")
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
