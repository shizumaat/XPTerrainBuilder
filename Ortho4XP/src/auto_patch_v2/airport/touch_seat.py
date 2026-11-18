"""TOUCHING BUILDINGS: ONE GROUP, ONE RIGID SEAT, AT THE LOWER (spec
2110-R3 §1.1 / §2; owner RULINGS 2026-11-16k, 16u, 16v; #2110; narrows
2026-10-22o).

Owner, 21:35:15Z (16u): "Touching buildings should form an object group so
they seat together ... if they were authored at different levels they stay
that way."  (16v): "amounts less than a meter can probably just be seated
at the lower and let the other sink slightly under ground, which is better
than floating.  If they're more than 2m difference it's intentional and
they should have different pads".

:func:`seat_touching` runs ONCE, at the end of
``placement_plan.build_splits``, over the FINAL bodies — after every pass
has seated them — and moves a group RIGIDLY: every non-fixed member takes
ONE zero, its authored offsets kept; nothing is levelled or split.  The
groups are ``touch_graph``'s.  Per group, over its BUILDINGS' zeros (the
votes), S = max - min:

* S <= ``tol_m``: nothing;
* S <= :data:`SEAT_MAX_M`: the group takes the LOWEST vote — no building
  rises; a member under it keeps its seat (2.2, I1), and a follower
  more than :data:`SEAT_MAX_M` over it too (16v's "less than a meter"),
  with what rides it — a piece riding a group member with evidence moves
  with its carrier.  A SMALL LOW
  MEMBER (a building under ``min_share`` of the group's building footprint,
  alone within :data:`LOW_BAND_M` of the lowest vote) does not vote and
  keeps its seat;
* S <= :data:`PADS_MIN_M`: no move — listed for the case-by-case reading
  (16v "1-2 m: judgement");
* larger: SEPARATE PADS — no move; listed with the level the terrain would
  need under each member for the rigid group (the planar pad grammar
  grades between; R3 changes none of it).

THE RULES OF 2026-11-18h (owner, #2129: "only fix problem spots"):

* (4) before anything else, a SEAT TILT that floats a foot as written is
  undone and its frame seats level at its no-float zero
  (``tilt_float.untilt_floating``); what rides it moves with it.  A tilted
  body is no longer FIXED here: it is a node like any other;
* (2) a DECK STACKED ON WALLS (``stacked_deck.stacked_on``) rides those
  walls at its authored relative height, whatever the gap: it and its
  unit take no vote, and move to the walls' final zero;
* (3) a connector between two separately seated buildings is the deck
  warp's (``deck_profile``), after this pass.

A rider of a moved body that is in no group moves by the same amount.  The
moved records are CUT AGAIN (``placement_file.recut``) and every rider's
``merged_into`` follows its carrier's new file name.  No moved body: no
change, no writes.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from . import connector_warp as _cw
from . import stacked_deck as _sd
from . import tilt_float as _tf
from . import touch_graph as _tg
from .open_frame_seat import at_zero, group_key, unit_root
from .placement_file import recut

__all__ = ["Fixed", "law_of", "seat_touching", "REASON",
           "SEAT_MAX_M", "PADS_MIN_M", "LOW_BAND_M"]

#: 16v: a spread under this seats the group at its lower member
SEAT_MAX_M = 1.0
#: 16v: a spread over this is intentional — separate pads
PADS_MIN_M = 2.0
#: §2.2: the band over the lowest vote a SMALL LOW MEMBER stands alone in
LOW_BAND_M = 0.3
#: the moved body's reason (``drawn_site_plan`` reads its ``fu:N:M``)
REASON = "one touching group {root} at {z:.2f} (RULINGS 2026-11-16u/v)"
#: rule (2)'s reason: a deck stacked on walls rides them
_STACK_REASON = "rides the walls {walls} it stands on at {z:.2f} (RULINGS 2026-11-18h (2))"
#: rule (4)'s, for a body riding a levelled tilted frame
_LEVEL_RIDER_REASON = "rides its carrier, levelled at {z:.2f} (RULINGS 2026-11-18h (4))"


@_dc.dataclass(frozen=True)
class _TouchLaw:
    """``[placement] touch_gap_m`` (§1.2), the materiality ``tol_m``
    (``authored_keep_tol_m``), ``touch_seat_min_share`` (§2.2) and
    ``chain_min_height_m`` (what makes a body a BUILDING)."""

    touch_m: float
    tol_m: float
    min_share: float
    walled_m: float
    #: rule (2)'s bearing tolerance and the feet rule (4) reads:
    #: ``[placement] split_tol_m`` (0 where the table predates it)
    contact_tol_m: float = 0.0


@_dc.dataclass(frozen=True)
class Fixed:
    """What the pass may not move beyond the bodies themselves (§1.3
    FIXED): ``frames`` (plan unit id -> why: an open frame, an airside
    deck, a bridge, a free bridge, a terrain-adapted member), ``afloat``
    (#1896: files kept over water) and ``led`` (#1201: the walled-plate-led
    ``group_key``s)."""

    frames: _t.Mapping[str, str] = _dc.field(default_factory=dict)
    afloat: _t.AbstractSet[str] = frozenset()
    led: _t.AbstractSet[str] = frozenset()


def law_of(placement: _t.Any) -> "_TouchLaw | None":
    """The touch law of a ``[placement]`` table; ``None`` (disarmed) where
    ``touch_gap_m`` is absent or not positive."""
    t = float(getattr(placement, "touch_gap_m", 0.0) or 0.0)
    if t <= 0.0:
        return None
    return _TouchLaw(t, float(placement.authored_keep_tol_m),
                    float(placement.touch_seat_min_share),
                    float(placement.chain_min_height_m),
                    float(getattr(placement, "split_tol_m", 0.0) or 0.0))


def _mark_fixed(nodes: list, splits: _t.Sequence[_t.Any], members: _t.Mapping,
                fixed: Fixed) -> None:
    """Each node's §1.3 FIXED reason, or none."""
    led_recs = {n.key[0] for n in nodes
                if "walled plate's datum" in str(splits[n.key[0]].bodies[n.key[1]]
                                                 .anchor.reason)}
    for n in nodes:
        rec = splits[n.key[0]]
        b = rec.bodies[n.key[1]]
        m = members[rec.placement_id][1]
        gate = fixed.frames.get(n.frame, "")
        n.fixed = (
            f"plate_{m.plate_kind}" if getattr(m, "plate_kind", "") else
            "afloat" if n.name in fixed.afloat else
            "walled_plate_led" if (n.key[0] in led_recs or
                                   group_key(n.unit, n.frame) in fixed.led) else
            "isolated" if getattr(b.anchor, "isolated", "") else
            gate if gate and not (n.kind == _tg.CONNECTOR and n.carrier) else "")
    by_name = {(n.frame, n.name): n for n in nodes}
    for _ in range(len(nodes)):
        moved = False
        for n in nodes:
            if n.fixed or not n.carrier:
                continue
            c = by_name.get((n.frame, n.carrier))
            if c is not None and c.fixed:
                n.fixed, moved = "carrier_fixed", True
            elif c is None and n.carrier and not n.carrier.startswith("fu:"):
                b = splits[n.key[0]].bodies[n.key[1]]
                if not getattr(b, "merged_into_written", True):
                    n.fixed, moved = "carrier_kept_whole", True
                else:
                    n.fallback, n.carrier = n.carrier, ""     # unresolved: (c)
        if not moved:
            break


def _root(nodes: list, blds: list[int], g: list[int]) -> str:
    """The group's name in a moved body's reason: the §16g unit of its
    lowest building that has one (``drawn_site_plan`` reads a ``fu:N:M``
    as a GROUP; a file name there would read as a rider), else any
    member's, else the lowest building's file."""
    for i in list(blds) + sorted(g):
        if nodes[i].unit or nodes[i].family:
            return nodes[i].unit or nodes[i].family
    return nodes[blds[0]].name


def _seat(nodes: list, g: list[int], pairs: _t.Mapping, law: _TouchLaw,
          ride: _t.AbstractSet[int] = frozenset()) -> dict:
    """One group's decision (§2.2): its class, ``Z``, the members that
    move to it and the listings.  ``ride``: the stacked decks and their
    units (rule (2)), which take no vote and no group move."""
    blds = [i for i in g if nodes[i].kind == _tg.BUILDING and i not in ride]
    if not blds:
        return {"frame": nodes[g[0]].frame, "root": _root(nodes, sorted(g), g), "S": 0.0,
                "Z": round(min(nodes[i].zero for i in g), 3), "bodies": len(g),
                "buildings": 0, "small_low": [], "step": 0.0, "moves": {},
                "kept_low": 0, "kept_high": 0, "class": "flat"}
    low = min(nodes[i].zero for i in blds)
    near = [i for i in blds if nodes[i].zero <= low + LOW_BAND_M]
    total = sum(nodes[i].area for i in blds)
    small = [near[0]] if (len(near) == 1 and len(blds) > 1 and total > 0.0
                          and nodes[near[0]].area < law.min_share * total) else []
    votes = [nodes[i].zero for i in blds if i not in small]
    z, s = min(votes), max(votes) - min(votes)
    root = _root(nodes, sorted((i for i in blds if i not in small),
                               key=lambda i: nodes[i].zero), g)
    steps = [d for (i, j), d in pairs.items() if i in g and j in g]
    out = {"frame": nodes[g[0]].frame, "root": root, "S": round(s, 3), "Z": round(z, 3),
           "bodies": len(g), "buildings": len(blds), "small_low": [nodes[i].name for i in small],
           "step": round(max(steps, default=0.0), 3), "moves": {}, "kept_low": 0,
           "kept_high": 0}
    out["class"] = ("flat" if s <= law.tol_m else "seat" if s <= SEAT_MAX_M
                    else "judge" if s <= PADS_MIN_M else "pads")
    if out["class"] == "pads":
        out["pads"] = [(nodes[i].name, round(z + nodes[i].bottom(), 3)) for i in blds]
    if out["class"] != "seat":
        return out
    by_name = {(nodes[i].frame, nodes[i].name): i for i in g}
    keep = set(small) | (set(ride) & set(g))
    for i in g:
        n = nodes[i]
        rides = n.kind == _tg.CONNECTOR and (n.frame, n.carrier) in by_name
        if n.zero < z - law.tol_m:
            out["kept_low"] += 1                      # 2.2: no member rises
            keep.add(i)
        elif n.kind != _tg.BUILDING and not rides and n.zero > z + SEAT_MAX_M:
            out["kept_high"] += 1                     # 16v: past a metre, no seat
            keep.add(i)
    for _ in range(len(g)):
        # (b): a connector carried with evidence keeps with a kept carrier
        grew = {i for i in g if i not in keep and nodes[i].kind == _tg.CONNECTOR
                and by_name.get((nodes[i].frame, nodes[i].carrier)) in keep}
        if not grew:
            break
        keep |= grew
    for i in g:
        if i not in keep and abs(nodes[i].zero - z) > 1e-6:
            out["moves"][i] = z
    return out


def _zero_of(b: _t.Any) -> float:
    return float(b.anchor.surface_z) - float(b.anchor.y_zero)


def _riders(splits: _t.Sequence[_t.Any], frames: _t.Sequence[str],
            moved: dict[tuple[int, int], float], skip: set[tuple[int, int]],
            tol_m: float) -> dict[tuple[int, int], float]:
    """§2.3: every body riding a moved body (``merged_into``, evidence or
    not) — a body of no group, a node or not (a carried file of orphan
    geometry has no part) — moved by the same amount, riders of riders
    too; never a body ``skip`` names (a group member, a FIXED one), an
    isolated one, nor a footed one upward (a seat-tilted rider moves with
    its carrier, RULINGS 2026-11-18h (4))."""
    name_delta: dict[tuple[str, str], float] = {}
    for (ri, j), z in moved.items():
        b = splits[ri].bodies[j]
        name_delta[(frames[ri], str(b.new_resource))] = z - _zero_of(b)
    out: dict[tuple[int, int], float] = {}
    for _ in range(64):
        grew = False
        for ri, rec in enumerate(splits):
            for j, b in enumerate(rec.bodies):
                k = (ri, j)
                d = name_delta.get((frames[ri], str(b.merged_into or "")))
                if (d is None or k in moved or k in out or k in skip
                        or b.anchor.surface_z is None
                        or getattr(b.anchor, "isolated", "") or (b.feet and d > tol_m)):
                    continue
                out[k], grew = _zero_of(b) + d, True
                name_delta[(frames[ri], str(b.new_resource))] = d
        if not grew:
            break
    return out


def _apply(splits: list, members: _t.Mapping, targets: dict[tuple[int, int], float],
           roots: dict[tuple[int, int], str],
           whys: "_t.Mapping[tuple[int, int], str] | None" = None) -> set[int]:
    """Every target zero applied (``open_frame_seat.at_zero``, the file
    renamed) with its reason (``whys``, else :data:`REASON` of its group's
    ``roots``); the records changed."""
    whys = whys or {}
    per: dict[int, dict[tuple[float, str], list]] = {}
    for (ri, j), z in targets.items():
        why = whys.get((ri, j)) or REASON.format(root=roots.get((ri, j), ""), z=z)
        per.setdefault(ri, {}).setdefault((z, why), []).append(j)
    for ri, by_z in per.items():
        rec = splits[ri]
        m = members[rec.placement_id][1]
        for (z, why), js in by_z.items():
            ids = {id(rec.bodies[j]) for j in js}
            rec = at_zero(rec, m, z, lambda b, _ids=ids: id(b) in _ids, why)
        splits[ri] = rec
    return set(per)


def _recut(splits: list, frames: _t.Sequence[str], before: list, changed: set[int],
           cut_log: _t.Mapping, write: bool, counts: dict) -> dict[tuple[str, str], str]:
    """The changed records cut again; ``{(frame, old file): new file}`` of
    every body that moved.  A record the cut no longer writes stays as it
    was."""
    names: dict[tuple[str, str], str] = {}
    for ri in sorted(changed):
        args = cut_log.get(ri)
        new = recut(splits[ri], args, write, counts) if args is not None else None
        if new is None:
            counts["touch_recut_refused"] = counts.get("touch_recut_refused", 0) + 1
            splits[ri] = before[ri]
            continue
        splits[ri] = new
        now = {b.body_id: b.new_resource for b in new.bodies}
        for b in before[ri].bodies:
            if now.get(b.body_id, b.new_resource) != b.new_resource:
                names[(frames[ri], b.new_resource)] = now[b.body_id]
    return names


def _renamed_riders(splits: list, frames: _t.Sequence[str],
                    names: _t.Mapping[tuple[str, str], str]) -> int:
    """Every ``merged_into`` naming a moved file of its frame follows it;
    the count."""
    n = 0
    for ri, rec in enumerate(splits):
        bs = tuple(_dc.replace(b, merged_into=names[(frames[ri], b.merged_into)])
                   if (frames[ri], b.merged_into) in names else b for b in rec.bodies)
        k = sum(1 for a, b in zip(rec.bodies, bs, strict=True) if a is not b)
        if k:
            splits[ri] = _dc.replace(rec, bodies=bs)
            n += k
    return n


def _unit_rows_left(unit_seats: _t.Sequence[tuple], moved_units: dict[str, float],
                    tol_m: float) -> list:
    """§3: the §16g (5) row seats (``ss.unit_seats``) of a moved unit that
    keep the unit's old zero — counted and listed, never moved here."""
    out = []
    for s in unit_seats:
        uid = unit_root(s[5]) if len(s) > 5 else ""
        if uid in moved_units and abs(float(s[4]) - moved_units[uid]) > tol_m:
            out.append((uid, round(float(s[4]), 3), round(moved_units[uid], 3)))
    return out


def seat_touching(splits: _t.Sequence[_t.Any], plan: _t.Any,
                  plan_wide: _t.Mapping[int, tuple], counts: dict, *,
                  law: _TouchLaw, fixed: "Fixed | None" = None,
                  cut_log: "_t.Mapping[int, tuple] | None" = None,
                  write: bool = False, unit_seats: _t.Sequence[tuple] = (),
                  surface: _t.Any = None, band_m: float = 0.0
                  ) -> tuple[list, dict]:
    """``(splits, table)``: the touching groups of the final bodies seated
    (module doc).  ``cut_log`` is ``placement_file._cut_and_file``'s (each
    written record's cut args by its index); ``write`` the stage's;
    ``surface`` / ``band_m`` the ground and foot band rule (4) reads a
    tilted frame's feet on (``None``: no tilt is re-read)."""
    splits = list(splits)
    before = list(splits)
    members = {m.id: (u, m) for u in plan.units for m in u.members}
    frames = [str(members[r.placement_id][0].id) if r.placement_id in members else ""
              for r in splits]
    level, level_rows = _tf.untilt_floating(
        splits, members, surface, band_m=band_m, contact_tol_m=law.contact_tol_m,
        tol_m=law.tol_m, sink_max_m=SEAT_MAX_M, counts=counts)
    level_changed = {ri for ri, _j in level}
    if level:
        lr = _riders(before, frames, level, set(level), law.tol_m)
        level_changed |= _apply(splits, members, lr, {}, {
            k: _LEVEL_RIDER_REASON.format(z=z) for k, z in lr.items()})
    nodes = _tg.read_nodes(splits, members, plan_wide, law.walled_m)
    _mark_fixed(nodes, splits, members, fixed or Fixed())
    _tg.footprint_areas(nodes)
    pairs, cross = _tg.touch_pairs(nodes, law.touch_m)
    by_name = {(n.frame, n.name): i for i, n in enumerate(nodes)}
    groups = _tg.groups_of(nodes, pairs, by_name)
    stack = _sd.stacked_on(nodes, pairs, lambda n: splits[n.key[0]].bodies[n.key[1]],
                           walled_m=law.walled_m, tol_m=law.contact_tol_m or law.tol_m,
                           kind_building=_tg.BUILDING)
    units = {d: _sd.unit_of(nodes, d, set(stack.values()), law.tol_m) for d in stack}
    rows = [_seat(nodes, g, pairs, law, {i for u in units.values() for i in u})
            for g in groups]
    moves = {nodes[i].key: z for r in rows for i, z in r["moves"].items()}
    roots = {nodes[i].key: r["root"] for r in rows for i in r["moves"]}
    stacked, whys = _stack_moves(nodes, stack, units, moves)
    moves.update(stacked)
    skip = {nodes[i].key for g in groups for i in g} | {n.key for n in nodes if n.fixed}
    riders = _riders(splits, frames, moves, skip, law.tol_m)
    by_file = {(frames[ri], str(splits[ri].bodies[j].new_resource)): (ri, j)
               for ri, j in {**moves, **riders}}
    for k in sorted(riders):
        c = by_file.get((frames[k[0]], str(splits[k[0]].bodies[k[1]].merged_into)))
        roots[k] = roots.get(c, splits[c[0]].bodies[c[1]].new_resource if c else "")
    targets = {**moves, **riders}
    node_t = {i: targets[n.key] for i, n in enumerate(nodes) if n.key in targets}
    pre = list(splits)
    changed = _apply(splits, members, targets, roots, whys) | level_changed
    names = _recut(splits, frames, before, changed, cut_log or {}, write, counts)
    renamed = _renamed_riders(splits, frames, names)
    moved_units = {nodes[i].unit: z for i, z in node_t.items()
                   if nodes[i].unit and nodes[i].kind == _tg.BUILDING}
    left = _unit_rows_left(unit_seats, moved_units, law.tol_m)
    made = _steps_made(nodes, pairs, node_t, law.tol_m)
    table = _table(rows, targets, cross, left, pre)
    table["fixed"] = _fixed_counts(nodes)
    table["fixed_steps"] = made
    table["inside_steps"] = _inside_steps(nodes, pairs, groups, rows, node_t, law.tol_m)
    table["tilt_levelled"] = level_rows
    table["connectors"] = _cw.bridges(
        nodes, pairs, lambda n: splits[n.key[0]].bodies[n.key[1]],
        lambda k: node_t.get(k, nodes[k].zero), stacked=set(stack), tol_m=law.tol_m,
        building=_tg.BUILDING, connector=_tg.CONNECTOR)
    table["stacked"] = [(nodes[d].name, nodes[s].name, round(nodes[d].zero, 3),
                         round(stacked.get(nodes[d].key, nodes[d].zero), 3))
                        for d, s in sorted(stack.items())]
    _count(counts, nodes, rows, moves, riders, cross, renamed, left)
    if stack:
        counts["touch_stacked_decks"] = counts.get("touch_stacked_decks", 0) + len(stack)
    if made:
        counts["touch_fixed_steps_made"] = counts.get("touch_fixed_steps_made", 0) + len(made)
    return splits, table


def _stack_moves(nodes: list, stack: _t.Mapping[int, int], units: _t.Mapping[int, list],
                 moves: _t.Mapping[tuple, float]) -> tuple[dict, dict]:
    """Rule (2): ``({body key: zero}, {body key: reason})`` -- each stacked
    deck and its unit at its support's final zero (a support that is
    itself a stacked deck resolved first), its authored offsets kept."""
    out: dict = {}
    whys: dict = {}

    def final(i: int, depth: int = 0) -> float:
        n = nodes[i]
        if n.key in out:
            return out[n.key]
        if i in stack and depth < len(nodes):
            return final(stack[i], depth + 1)
        return moves.get(n.key, n.zero)
    for d, s in sorted(stack.items()):
        z = final(s)
        for k in units[d]:
            t = z + nodes[k].zero - nodes[d].zero
            if abs(t - nodes[k].zero) > 1e-6:
                out[nodes[k].key] = t
                whys[nodes[k].key] = _STACK_REASON.format(walls=nodes[s].name, z=t)
    return out, whys


def _steps_made(nodes: list, pairs: _t.Mapping, targets: dict, tol_m: float) -> list:
    """The touching pairs a move OPENED against a body the pass may not move
    (a FIXED one, or a follower it kept): listed, worst first."""
    out = []
    for i, j in pairs:
        if (i in targets) == (j in targets):
            continue
        d = abs(targets.get(i, nodes[i].zero) - targets.get(j, nodes[j].zero))
        if d > tol_m and abs(nodes[i].zero - nodes[j].zero) <= tol_m:
            out.append((round(d, 3), nodes[i].name, nodes[j].name,
                        nodes[i].fixed or nodes[j].fixed or "kept"))
    return sorted(out, reverse=True)


def _inside_steps(nodes: list, pairs: _t.Mapping, groups: list, rows: list,
                  targets: dict, tol_m: float) -> list:
    """I2 / B4: the touching pairs left more than ``tol_m`` apart INSIDE a
    group the pass seated — a member it kept (a small low member, a far
    follower) against one it moved."""
    of = {i: k for k, g in enumerate(groups) if rows[k]["class"] == "seat" for i in g}
    out = []
    for i, j in pairs:
        if i in of and of.get(j) == of[i]:
            d = abs(targets.get(i, nodes[i].zero) - targets.get(j, nodes[j].zero))
            if d > tol_m:
                out.append((round(d, 3), nodes[i].name, nodes[j].name))
    return sorted(out, reverse=True)


def _table(rows: list, targets: dict, cross: list, left: list,
           before: _t.Sequence[_t.Any]) -> dict:
    moved = []
    for (ri, j), z in sorted(targets.items()):
        rec = before[ri]
        b = rec.bodies[j]
        moved.append((rec.index, b.body_id, str(b.new_resource),
                       "footed" if b.feet else "footless", round(_zero_of(b), 3), round(z, 3)))
    for r in rows:
        r["moves"] = len(r["moves"])
    return {"groups": rows, "moved": moved,
            "cross_frame": [(round(d, 3), a, b) for d, a, b in cross[:50]],
            "cross_frame_pairs": len(cross), "unit_rows_left": left}


def _fixed_counts(nodes: _t.Sequence[_t.Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for n in nodes:
        if n.fixed:
            out[n.fixed] = out.get(n.fixed, 0) + 1
    return out


def _count(counts: dict, nodes: list, rows: list, moves: dict, riders: dict,
           cross: list, renamed: int, left: list) -> None:
    def add(k: str, v: int) -> None:
        if v:
            counts[k] = counts.get(k, 0) + v
    for c in ("flat", "seat", "judge", "pads"):
        add(f"touch_groups_{c}", sum(1 for r in rows if r["class"] == c))
    add("touch_bodies_moved", len(moves))
    add("touch_riders_moved", len(riders))
    add("touch_small_low", sum(len(r["small_low"]) for r in rows))
    add("touch_follower_kept_low", sum(r["kept_low"] for r in rows))
    add("touch_follower_kept_high", sum(r["kept_high"] for r in rows))
    add("touch_cross_frame_pairs", len(cross))
    add("touch_riders_renamed", renamed)
    add("touch_unit_rows_left", len(left))
    for n in nodes:
        if n.fixed:
            add(f"touch_fixed_{n.fixed}", 1)
