"""AN ELEVATED DECK TOUCHING TWO BUILDINGS AT TWO LEVELS IS WARPED, NOT
STEPPED (#2144 P2, spec ``sim-review/2144-spec.md`` §4 P2; design-surface
spec §49 (5) "THE BODY IS SHEARED, NOT STEPPED"; owner 2026-11-17T18:47Z:
"cut them at points where they touch buildings so they can stay flat inside
the buildings, then take the slope between").

:func:`warp_decks` runs ONCE, after the touch pass (``touch_seat``), over
the FINAL bodies.

WHO.  The ELEVATED DECK of a CONNECTED GROUP (owner RULINGS 2026-10-22o/q:
the bodies a 22o group zero seated, ``open_frame_seat.GROUP_REASON``): its
members of class ``deck``, flagged ``elevated``, or standing more than half
of their sampled plan (``geom_pts``) at least ``walled_m`` over their zero --
a deck on piers -- with what rides them (``merged_into``), when their
sampled plan together is LONG: at least :data:`DECK_MIN_LENGTH_M` along its
principal axis and :data:`DECK_ELONGATION` times its spread across it (a
raised door or a sign on a wall is no deck).  Refused whole,
and counted: a deck holding a class-A airside hard deck (22n: flush, banded
by #2112), a deck-plate band or a basin.  A member whose seat tilt is baked
or whose file holds an ``ANIM`` block is left out of the warp (counted).

NODES.  BUILDING CONTACT: a footed body of the SAME FRAME (plan unit: one
anchor, one authored datum -- across two frames no authored relation says
where the deck meets the building, ``touch_graph``'s cross-frame rule),
outside the deck, with a part at least ``walled_m`` tall, whose part ring
comes within ``reach_m`` of a deck part's ring in plan with the two parts'
DRAWN height spans no more than ``touch_graph.VETO_M`` apart (a deck
passing over a roof touches nothing).  Its value ``D = its zero - the
deck's zero``; its polygons are its part rings.  THE DECK'S TWO ENDS
(spec P2 (ii)): the ends of the deck's plan along its principal axis, each
read over the deck's own sampled plan (``geom_pts``) and ground-contact
feet (``Body.feet``) within :data:`END_M` of it.  An end that LANDS -- its
feet at the authored ground (within ``walled_m`` of the deck's zero) and
the deck's own surface there no more than ``walled_m`` over them (a ramp
that comes down to the ground; never a roof strip's lowest points) -- is a
GRADED END, ``D = surface under its
feet - (deck zero + their authored y)`` (median); an end standing higher
(on piers, or abutting another structure) is HELD where it is, ``D = 0``,
so the field never drifts past the last node.  A deck whose nodes do not
differ by more than ``float_tol_m`` is left alone.

FIELD.  ``obj8_warp.Field``: exactly ``D_k`` inside node k, the
inverse-distance blend between, so the deck is flat inside every building
it enters and takes the straight grade between two.

GRADE CAP.  The field's steepest gradient over the group's own plan
(sampled every :data:`GRID_M`) may not exceed ``grade_max`` (the rail ramp
cap, ``[tunnel] rail_ramp_max_grade``, and never above ``[deck]
shear_max_grade``); over it the group is not warped, keeps the zero its
group gave it, and is listed.

FEET.  After the warp a group member's ground-contact foot floating more
than ``float_tol_m`` over the surface is counted (``warp_feet_floating``)
and listed; the terrain is never regraded for a pier.

Nothing here names an airport, a pack or a resource.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from .open_frame_seat import GROUP_REASON, unit_root
from .placement_file import named_body
from .placement_targets import _zero

__all__ = ["law_of", "warp_decks", "GRID_M", "END_M", "DECK_MIN_LENGTH_M",
           "DECK_ELONGATION"]

#: the grade cap's sampling step over the group's plan, metres
GRID_M = 2.0
#: at most about this many grade samples per deck (the step widens)
GRID_MAX_PTS = 20000
#: a deck end is read over what lies within this of it along the axis, m
END_M = 6.0
#: a deck is at least this long along its principal axis, m ...
DECK_MIN_LENGTH_M = 30.0
#: ... and this many times as long as its spread across it
DECK_ELONGATION = 3.0
#: the classes that never warp (a basin's members are its pit's)
_REFUSED_CLASSES = ("basin",)
#: a class-A airside hard deck's reason (22n: flush; ``airside_deck_seat``)
_AIRSIDE = "airside deck"


@_dc.dataclass(frozen=True)
class _WarpLaw:
    """``grade_max`` (the rail ramp cap, no steeper than ``[deck]
    shear_max_grade``), the contact ``reach_m``, ``walled_m`` (what makes
    a BUILDING), the materiality ``tol_m`` and the foot float bar."""

    grade_max: float
    reach_m: float
    walled_m: float
    tol_m: float
    float_tol_m: float


def law_of(structures: _t.Any) -> "_WarpLaw | None":
    """The warp law of ``law.tables.structures``; ``None`` (disarmed) where
    ``[deck] shear`` is off or a key predates this rule."""
    from .open_frame_seat import TOUCH_M
    try:
        deck, tunnel, pl = structures.deck, structures.tunnel, structures.placement
        if not bool(deck.shear):
            return None
        return _WarpLaw(min(float(tunnel.rail_ramp_max_grade), float(deck.shear_max_grade)),
                       float(TOUCH_M), float(pl.chain_min_height_m),
                       float(pl.authored_keep_tol_m), float(pl.split_tol_m))
    except AttributeError:
        return None


# ── reading the bodies ──────────────────────────────────────────────────

def _root(reason: str) -> str:
    """The 22o group a body's standing seat names, or ""."""
    head = str(reason).split("; was:", 1)[0]
    if not head.startswith(GROUP_REASON + " fu:"):
        return ""
    return unit_root(head[len(GROUP_REASON) + 1:].split(" ", 1)[0])


def _parts(m: _t.Any, b: _t.Any) -> list:
    by = {p.comp: p for p in m.parts}
    return [by[c] for c in b.components if c in by]


_ANIM_MEMO: dict[str, bool] = {}


def _has_anim(m: _t.Any) -> bool:
    """Whether the member's pristine file holds an ``ANIM`` block."""
    from .placement_cut import pristine_path
    try:
        path = pristine_path(m)
    except (OSError, ValueError, AttributeError):
        return True
    if path not in _ANIM_MEMO:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                _ANIM_MEMO[path] = any(ln.lstrip().startswith("ANIM_begin") for ln in fh)
        except OSError:
            _ANIM_MEMO[path] = True
    return _ANIM_MEMO[path]


@_dc.dataclass
class _Piece:
    """One final body as the warp reads it."""

    key: tuple[int, int]
    frame: str
    name: str
    zero: float
    parts: list
    footed: bool
    walled: bool
    body: _t.Any
    member: _t.Any
    #: its part polygons in local metres, read once (:func:`_polys_of`)
    polys: "list | None" = None


def _pieces(splits: _t.Sequence[_t.Any], members: _t.Mapping, walled_m: float) -> list:
    out = []
    for i, rec in enumerate(splits):
        um = members.get(rec.placement_id)
        if um is None:
            continue
        u, m = um
        for j, b in enumerate(rec.bodies):
            z = _zero(b)
            ps = _parts(m, b)
            if z is None:
                continue          # a SEGMENT body names no whole part: still a piece
            out.append(_Piece((i, j), str(u.id), str(b.new_resource), z, ps, bool(b.feet),
                              any(float(p.height_m) >= walled_m and not p.line for p in ps),
                              b, m))
    return out


def _elevated(pc: _Piece, walled_m: float) -> bool:
    """A deck on piers: class ``deck``, flagged elevated, or more than half
    of its sampled plan at least ``walled_m`` over its zero."""
    b = pc.body
    if b.body_class == "deck" or getattr(b, "elevated", False):
        return True
    g = getattr(b, "geom_pts", ()) or ()
    if not g:
        return False
    y0 = float(b.anchor.y_zero)
    return sum(1 for q in g if float(q[2]) - y0 >= walled_m) * 2 > len(g)


def _groups(pieces: _t.Sequence[_Piece], walled_m: float) -> dict[str, list[int]]:
    """``{frame|22o root: piece indices}`` -- each group's ELEVATED members
    and, carried through ``merged_into`` (in its frame), what rides them."""
    groups: dict[str, list[int]] = {}
    for k, pc in enumerate(pieces):
        r = _root(pc.body.anchor.reason)
        if r and _elevated(pc, walled_m):
            groups.setdefault(f"{pc.frame}|{r}", []).append(k)
    by_file = {(pc.frame, pc.name): k for k, pc in enumerate(pieces)}
    owner = {k: g for g, ks in groups.items() for k in ks}
    grew = True
    while grew:
        grew = False
        for k, pc in enumerate(pieces):
            c = str(getattr(pc.body, "merged_into", "") or "")
            if k in owner or not c:
                continue
            g = owner.get(by_file.get((pc.frame, c), -1))
            if g is not None:
                groups[g].append(k)
                owner[k] = g
                grew = True
    return groups


def _is_long(pieces: _t.Sequence[_Piece], ks: _t.Sequence[int], xy: _t.Callable) -> bool:
    """The deck's sampled plan is long (module doc)."""
    pts = np.asarray([xy(float(q[0]), float(q[1])) for k in ks
                      for q in getattr(pieces[k].body, "geom_pts", ()) or ()])
    if pts.shape[0] < 3:
        return False
    c = pts - pts.mean(axis=0)
    _u, _s, vt = np.linalg.svd(c, full_matrices=False)
    along, across = c @ vt[0], c @ vt[1]
    length = float(along.max() - along.min())
    spread = float(across.max() - across.min())
    return length >= DECK_MIN_LENGTH_M and length >= DECK_ELONGATION * spread


def _refusal(pieces: _t.Sequence[_Piece], ks: _t.Sequence[int]) -> str:
    """Why the whole deck is refused, or ""."""
    for k in ks:
        b = pieces[k].body
        if b.body_class in _REFUSED_CLASSES:
            return "basin"
        if _AIRSIDE in str(b.anchor.reason).split("; was:", 1)[0]:
            return "airside_deck"
        if getattr(b, "band", None) is not None:
            return "plate_band"
    return ""


def _left_out(pc: _Piece) -> str:
    """Why one deck member is not warped (it keeps the deck's zero), or ""."""
    if getattr(pc.body.seat, "applied", False):
        return "seat_tilt"
    if _has_anim(pc.member):
        return "anim"
    return ""


# ── geometry in local metres ────────────────────────────────────────────

def _polys(parts: _t.Sequence[_t.Any], xy: _t.Callable) -> list:
    """Each part's plan polygons in local metres (its box where it has no
    ring), with the part."""
    from shapely.geometry import Polygon
    from shapely.geometry import box as _box
    out = []
    for p in parts:
        gs = [Polygon([xy(la, lo) for la, lo in rg]) for rg in (p.rings or ()) if len(rg) >= 3]
        if not gs:
            (x0, y0), (x1, y1) = xy(p.box[0], p.box[1]), xy(p.box[2], p.box[3])
            gs = [_box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))]
        for g in gs:
            g = g if g.is_valid else g.buffer(0.0)
            if not g.is_empty:
                out.append((g, p))
    return out


def _polys_of(pc: _Piece, xy: _t.Callable) -> list:
    """:func:`_polys` of a piece, read once."""
    if pc.polys is None:
        pc.polys = _polys(pc.parts, xy)
    return pc.polys


def _span(zero: float, p: _t.Any) -> tuple[float, float]:
    lo = zero + float(p.base_y)
    return lo, lo + float(p.height_m)


def _nodes(pieces: _t.Sequence[_Piece], ks: _t.Sequence[int], xy: _t.Callable,
           law: _WarpLaw) -> list:
    """The group's BUILDING CONTACTS: ``(D relative to the group zero,
    shapely footprint, piece index)``."""
    from shapely.strtree import STRtree

    from .touch_graph import VETO_M
    inside = set(ks)
    deck = [(g, p, k) for k in ks for g, p in _polys_of(pieces[k], xy)]
    if not deck:
        return []
    tree = STRtree([g for g, _p, _k in deck])
    z0 = float(np.median([pieces[k].zero for k in ks]))
    out = []
    frame = pieces[ks[0]].frame
    from shapely.geometry import box as _box
    bx = np.asarray([g.bounds for g, _p, _k in deck])
    dbox = _box(bx[:, 0].min() - law.reach_m, bx[:, 1].min() - law.reach_m,
                bx[:, 2].max() + law.reach_m, bx[:, 3].max() + law.reach_m)
    for c, pc in enumerate(pieces):
        if (c in inside or pc.frame != frame or not (pc.footed and pc.walled)
                or pc.body.body_class in ("deck", "basin", "line_segment")
                or getattr(pc.body, "merged_into", "")):
            continue
        polys = _polys_of(pc, xy)
        if not any(dbox.intersects(g) for g, _p in polys):
            continue
        touch = False
        for g, p in polys:
            for di in tree.query(g, predicate="dwithin", distance=law.reach_m).tolist():
                dg, dp, dk = deck[di]
                (a0, a1), (b0, b1) = _span(pieces[dk].zero, dp), _span(pc.zero, p)
                if max(a0, b0) - min(a1, b1) <= VETO_M:
                    touch = True
                    break
            if touch:
                break
        if touch:
            from shapely.ops import unary_union
            out.append((pc.zero - z0, unary_union([g for g, _p in polys]), c))
    return out


def _end_nodes(pieces: _t.Sequence[_Piece], ks: _t.Sequence[int], xy: _t.Callable,
               surface: _t.Callable, z0: float, walled_m: float) -> list:
    """The deck's two ENDS (module doc): ``(D, footprint, -1)`` each."""
    from shapely.geometry import MultiPoint
    cells, feet = [], []
    for k in ks:
        pc = pieces[k]
        dz = pc.zero - z0 - float(pc.body.anchor.y_zero)
        cells += [(*xy(float(q[0]), float(q[1])), float(q[2]) + dz)
                  for q in getattr(pc.body, "geom_pts", ()) or ()]
        feet += [(*xy(float(la), float(lo)), float(y) + dz, float(la), float(lo))
                 for la, lo, y in pc.body.feet or ()]
    if len(cells) < 2:
        return []
    c = np.asarray(cells)
    mid = c[:, :2].mean(axis=0)
    _u, _s, vt = np.linalg.svd(c[:, :2] - mid, full_matrices=False)
    ax = vt[0]
    sc = (c[:, :2] - mid) @ ax
    out = []
    for end in (sc.min(), sc.max()):
        near = np.abs(sc - end) <= END_M
        top = float(np.max(c[near, 2]))
        fe = [f for f in feet if abs((np.asarray(f[:2]) - mid) @ ax - end) <= END_M]
        foot = [(f, surface(f[3], f[4])) for f in fe]
        foot = [(f, g) for f, g in foot if g is not None]
        # it LANDS: its feet there stand at the authored ground (within
        # ``walled_m`` of the deck's zero) and its surface comes down to them
        foot = [(f, g) for f, g in foot if abs(f[2]) <= walled_m]
        if foot and top - min(f[2] for f, _g in foot) <= walled_m:
            d = float(np.median([g - z0 - f[2] for f, g in foot]))
            pts = [f[:2] for f, _g in foot]
        else:
            d = 0.0
            pts = [tuple(p) for p in c[near, :2]]
        out.append((d, MultiPoint(pts).convex_hull.buffer(0.5), -1))
    return out


def _merged(nodes: _t.Sequence[tuple], tol_m: float) -> list:
    """Nodes of one value (within ``tol_m``) as ONE node, their footprints
    unioned: an inverse-distance blend counts every node, so a cluster of
    touching buildings on one level would otherwise outweigh a single end
    and bunch the grade at it; one node per level keeps the blend between
    two levels the straight grade."""
    from shapely.ops import unary_union
    out: list[list] = []
    for d, g, c in sorted(nodes, key=lambda n: n[0]):
        if out and abs(d - out[-1][0]) <= tol_m:
            out[-1][1].append(g)
            out[-1][2].append(c)
            continue
        out.append([d, [g], [c]])
    return [(float(np.median([d])), unary_union(gs), cs[0]) for d, gs, cs in out]


def _field_xy(nodes: _t.Sequence[tuple]) -> _t.Any:
    from .obj8_warp import Field
    return Field([(d, tuple(tuple(map(tuple, np.asarray(r.exterior.coords)))
                            for r in getattr(g, "geoms", [g])))
                  for d, g, _c in nodes])


def _steepest(nodes: _t.Sequence[tuple], pieces: _t.Sequence[_Piece],
              ks: _t.Sequence[int], xy: _t.Callable) -> float:
    """The field's steepest gradient over the group's own plan."""
    from shapely import contains_xy
    from shapely.ops import unary_union
    plan = unary_union([g for k in ks for g, _p in _polys_of(pieces[k], xy)]).buffer(1.0)
    x0, y0, x1, y1 = plan.bounds
    step = max(GRID_M, math.sqrt(plan.area / GRID_MAX_PTS))
    gx, gy = np.meshgrid(np.arange(x0, x1 + step, step), np.arange(y0, y1 + step, step))
    gx, gy = gx.ravel(), gy.ravel()
    keep = contains_xy(plan, gx, gy)
    if not keep.any():
        return 0.0
    f = _field_xy(nodes)
    dx, dy = f.grad(gx[keep], gy[keep])
    return float(np.max(np.hypot(dx, dy)))


def _to_frame(rec: _t.Any, xy_inv: _t.Callable) -> _t.Callable:
    """local metres -> the placement's authored ``(x, z)``
    (``placement_file.authored_offset``'s map)."""
    from .anchor_rule import _m_per_deg
    ml, mo = _m_per_deg(float(rec.lat))
    h = math.radians(float(rec.heading))
    s, c = math.sin(h), math.cos(h)

    def f(x: float, y: float) -> tuple[float, float]:
        la, lo = xy_inv(x, y)
        e, n = (lo - float(rec.lon)) * mo, (la - float(rec.lat)) * ml
        return (round(e * c - n * s, 4), round(-e * s - n * c, 4))
    return f


def _frame_nodes(rec: _t.Any, nodes: _t.Sequence[tuple], d_off: float,
                 xy_inv: _t.Callable) -> tuple:
    to = _to_frame(rec, xy_inv)
    out = []
    for d, g, _c in nodes:
        rings = tuple(tuple(to(x, y) for x, y in np.asarray(r.exterior.coords))
                      for r in getattr(g, "geoms", [g]))
        out.append((round(float(d) - d_off, 4), rings))
    return tuple(out)


# ── the pass ────────────────────────────────────────────────────────────

def warp_decks(splits: _t.Sequence[_t.Any], plan: _t.Any, counts: dict, *,
               law: _WarpLaw, surface: "_t.Callable | None" = None,
               cut_log: "_t.Mapping[int, tuple] | None" = None,
               write: bool = False) -> tuple[list, list]:
    """``(splits, table)``: every connected group touching buildings at two
    levels warped (module doc); one table row per group it read."""
    from .touch_graph import local_metres
    from .touch_seat import _recut, _renamed_riders
    splits = list(splits)
    before = list(splits)
    members = {m.id: (u, m) for u in plan.units for m in u.members}
    pieces = _pieces(splits, members, law.walled_m)
    if not pieces:
        return splits, []
    a0 = pieces[0].body.anchor
    la0, lo0 = float(a0.lat), float(a0.lon)
    xy = local_metres(la0, lo0)
    ml, mo = 111132.0, 111320.0 * math.cos(math.radians(la0))

    def xy_inv(x: float, y: float) -> tuple[float, float]:
        return la0 + y / ml, lo0 + x / mo
    table: list = []
    changed: set[int] = set()
    for gid, ks in sorted(_groups(pieces, law.walled_m).items()):
        if not _is_long(pieces, ks, xy):
            continue
        z0 = float(np.median([pieces[k].zero for k in ks]))
        nodes = _nodes(pieces, ks, xy, law)
        feet = (_end_nodes(pieces, ks, xy, surface, z0, law.walled_m)
                if surface is not None else [])
        ds = [d for d, _g, _c in nodes + feet]
        if len(ds) < 2 or max(ds) - min(ds) <= law.float_tol_m:
            continue
        nodes = _merged(nodes + feet, law.tol_m)
        row = {"group": gid, "bodies": len(ks), "zero": round(z0, 3),
               "nodes": [[round(d, 3), pieces[c].name] for d, _g, c in nodes if c >= 0],
               "feet": len(feet),
               "feet_d": [round(min(d for d, _g, _c in feet), 3),
                          round(max(d for d, _g, _c in feet), 3)] if feet else []}
        table.append(row)
        why = _refusal(pieces, ks)
        if not why:
            g = _steepest(nodes, pieces, ks, xy)
            row["grade"] = round(g, 4)
            if g > law.grade_max:
                why = "grade"
        if why:
            row["refused"] = why
            counts[f"warp_refused_{why}"] = counts.get(f"warp_refused_{why}", 0) + 1
            continue
        for k in ks:
            pc = pieces[k]
            out = _left_out(pc)
            if out:
                counts[f"warp_left_out_{out}"] = counts.get(f"warp_left_out_{out}", 0) + 1
                row.setdefault("left_out", []).append([pc.name, out])
                continue
            i, j = pc.key
            rec = splits[i]
            warp = _frame_nodes(rec, nodes, pc.zero - z0, xy_inv)
            bs = list(rec.bodies)
            bs[j] = named_body(pc.member, bs[j], warp=warp)
            splits[i] = _dc.replace(rec, bodies=tuple(bs))
            changed.add(i)
        n_out = len(row.get("left_out", ()))
        counts["deck_warped"] = counts.get("deck_warped", 0) + len(ks) - n_out
        counts["deck_warp_groups"] = counts.get("deck_warp_groups", 0) + 1
        if surface is not None:
            row["feet_floating"] = _floating(pieces, ks, nodes, xy, surface, law, z0)
            row["feet_floating_before"] = len(_floating(pieces, ks, (), xy, surface, law, z0))
            if row["feet_floating"]:
                counts["warp_feet_floating"] = (counts.get("warp_feet_floating", 0)
                                                + len(row["feet_floating"]))
    if changed:
        frames = [str(members[r.placement_id][0].id) if r.placement_id in members else ""
                  for r in splits]
        names = _recut(splits, frames, before, changed, cut_log or {}, write, counts)
        _renamed_riders(splits, frames, names)
    return splits, table


def _floating(pieces: _t.Sequence[_Piece], ks: _t.Sequence[int], nodes: _t.Sequence[tuple],
              xy: _t.Callable, surface: _t.Callable, law: _WarpLaw, z0: float) -> list:
    """The warped members' ground-contact feet floating more than the bar:
    ``(lat, lon, float m)``, worst first."""
    f = _field_xy(nodes)
    out = []
    for k in ks:
        pc = pieces[k]
        for la, lo, y in pc.body.feet or ():
            x, yy = xy(float(la), float(lo))
            d = float(f.at(np.asarray([x]), np.asarray([yy]))[0]) - (pc.zero - z0)
            s = surface(float(la), float(lo))
            if s is None:
                continue
            fl = pc.zero + float(y) - float(pc.body.anchor.y_zero) + d - float(s)
            if fl > law.float_tol_m:
                out.append((round(float(la), 7), round(float(lo), 7), round(fl, 3)))
    return sorted(out, key=lambda t: -t[2])
