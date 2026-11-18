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

A ROAD OVERPASS deck (lkden5, owner KDEN 2026-11-18T01:11Z "seat the rail
bridge object a little lower so the end here didn't float"): a ``deck``
body the overpass seat put on the road beneath (RULINGS 2026-10-30f (5)) is
a deck of its own -- no 22o group seats it, and it is no class-A airside
hard deck though its seat reason reads "airside deck" -- whose CROSSING is a
node at ``D = 0`` over the road-beneath stations (``plate_stations``: the
clearance the seat read stays), and whose LANDING ENDS grade as below.
MEASURED at KDEN ``Train_Bridge_1`` b0 (a 500 m rail deck seated flush at
1630.20 over its road): its NE end line read +1.89 m over the drawn ground
(39.839766,-104.674007); warped it reads +0.09, grade 3.5 %.  THE
OVERPASS MOVES AS ONE (lkden7, owner KDEN 2026-11-18T19:29Z "moved to the
right spot, but left some pieces floating, should move as a group"): its
group is EVERY overpass deck body of the placement (the deck and its pier
bodies, which the overpass seat put at the one zero), with what rides them
(``merged_into``) and every other body of its frame the same seat placed
that touches the deck -- the rails and pieces of a sibling placement at the
same anchor; before, each deck body was a group of its own, and the piers,
the rails over them and the loose rail pieces kept the unwarped zero
(KDEN ``Train_Bridge_1`` b4 / ``_Tracks`` b21 stood +3.3 m over the warped
rails of b0 / b17 at 39.839152,-104.674323).

NODES.  BUILDING CONTACT (owner RULINGS 2026-11-17t: "a deck touching two
buildings at different zeros follows both", whichever frame or 22o group
the building stands in -- of a frame whose zero relates to the deck's: one
placed at the SAME ANCHOR, the authored relation of two frames being their
anchor's ground plus each one's ``OBJECT_AGL`` lift; across two anchors no
authored relation says where they meet, ``touch_graph``'s cross-frame
rule): a BUILDING is the bodies of one placement outside
the deck (less what rides the deck, ``merged_into`` a deck member or its
group, and the deck's OWN connected unit -- same frame, same 22o root --
whose bodies touching the deck RIDE it, warped with it), footed and with a
part at least ``walled_m`` tall among them; it touches where one of its
bodies' part rings comes within ``reach_m`` of a deck part's ring in plan
with the two parts' DRAWN height spans no more than ``touch_graph.VETO_M``
apart (a deck passing over a roof touches nothing).  Its value ``D = the
touching bodies' zero - the deck's zero`` (median), less the two frames'
lifts apart; its CONTACT is each
touching deck part's plan within ``reach_m`` of the building.  THE DECK'S
TWO ENDS
(spec P2 (ii)): the ends of the deck's plan along its principal axis, each
read over the deck's own sampled plan (``geom_pts``) and ground-contact
feet (``Body.feet``) within :data:`END_M` of it.  An end that LANDS -- its
feet at the authored ground (within ``walled_m`` of the deck's zero) and
the deck's own surface there no more than ``walled_m`` over them (a ramp
that comes down to the ground; never a roof strip's lowest points) -- is a
GRADED END, ``D = surface under its
feet - (deck zero + their authored y)`` (median); an end standing higher
(on piers, or abutting another structure) is no node: past its last node
the track holds that node's ``D``.  A deck whose nodes do not
differ by more than ``float_tol_m`` is left alone.

FIELD (owner 2026-11-17T23:33Z: "if the rail is being sloped, shouldn't
the piers never need to be much taller?").  The deck's TRACK: its
CENTRELINE (the plan's cells walked from one end, their centroid every
:data:`TRACK_BIN_M` along it), each node FLAT over the stretch of the line
its footprint covers, ``D`` LINEAR IN DISTANCE ALONG THE LINE between two
consecutive nodes and held past the last; a point takes ``D`` at its
nearest station (``obj8_warp.Track``).  So the deck is flat inside every
building it enters, takes the straight grade between two along its own
curve, and a pier under it stands near its authored height.

BEND (owner 2026-11-18T00:32Z, RULINGS 2026-11-17t (3): "As long it's
under rail cap, yes").  Between two nodes the track follows the drawn
ground under it, offset by the authored pier height -- the L1 fit to its
feet's ``T = ground - (deck zero + authored y)`` -- each segment under the
rail cap and its grade changing by at most ``1/[deck]
track_vertical_radius_m`` per metre (a vertical curve; a node reads
grade 0), the nodes untouched (``airport/deck_track_bend``).  Where the
ground falls faster than the cap the track keeps the capped grade; the
ground GRADING under it (an embankment or cut) is not built yet.

GRADE CAP.  The track's steepest grade, along it vertex to vertex, may
not exceed ``grade_max`` (the rail ramp
cap, ``[tunnel] rail_ramp_max_grade``, and never above ``[deck]
shear_max_grade``); over it the group is not warped, keeps the zero its
group gave it, and is listed.

FEET (owner 2026-11-17T20:43Z: "a pier foot may stretch by at most
3 m").  After the warp a group member's ground-contact foot floating more
than ``float_tol_m`` over the surface has its bottom vertices lowered to
the surface by at most ``[deck] pier_foot_stretch_max_m``
(``obj8_warp.Foot``; counted ``warp_feet_stretched``); one still floating
past the bar is counted (``warp_feet_floating``) and listed.  Sinking is
free; the terrain is never regraded for a pier.

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

#: the centreline's raster step over the group's plan, metres
GRID_M = 2.0
#: at most about this many raster cells per deck (the step widens)
GRID_MAX_PTS = 20000
#: the centreline's vertex spacing along the deck, metres
TRACK_BIN_M = 4.0
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
#: a ROAD OVERPASS's (RULINGS 2026-10-30f (5)): the same seat's reason, its
#: zero on the road beneath -- no airside deck, a deck held over a crossing
_OVERPASS = "the road beneath the overpass"


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
    #: the most a floating pier foot is lowered (``[deck]
    #: pier_foot_stretch_max_m``); 0 lists it only
    stretch_max_m: float = 0.0
    #: the track's vertical-curve radius (``[deck]
    #: track_vertical_radius_m``); 0 keeps the straight grade between nodes
    radius_m: float = 0.0


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
                       float(pl.authored_keep_tol_m), float(pl.split_tol_m),
                       float(getattr(deck, "pier_foot_stretch_max_m", 0.0)),
                       float(getattr(deck, "track_vertical_radius_m", 0.0)))
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
    #: its frame's authored datum: the unit's anchor ``(lat, lon)`` and
    #: ``OBJECT_AGL`` lift
    datum: tuple = (0.0, 0.0, 0.0)
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
                              b, m, (round(float(u.anchor[0]), 7), round(float(u.anchor[1]), 7),
                                     float(getattr(u, "agl_m", 0.0) or 0.0))))
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
    return sum(1 for q in g if float(q[2]) >= walled_m) * 2 > len(g)   # authored y over zero


def _overpass_seated(pc: _Piece) -> bool:
    """A body the overpass seat placed (10-30f (5)), whatever its class."""
    return _OVERPASS in str(pc.body.anchor.reason).split("; was:", 1)[0]


def _is_overpass(pc: _Piece) -> bool:
    """A deck body the overpass seat put on the road beneath (10-30f (5))."""
    return (pc.body.body_class == "deck" and _overpass_seated(pc)
            and bool(getattr(pc.member, "plate_stations", ())))


def _groups(pieces: _t.Sequence[_Piece], walled_m: float) -> dict[str, list[int]]:
    """``{frame|22o root: piece indices}`` -- each group's ELEVATED members
    and, carried through ``merged_into`` (in its frame), what rides them; a
    ROAD OVERPASS is a group of its own -- every overpass deck body of
    its placement (``frame|overpass:<placement>``), held over the road it
    spans, its landing ends graded (lkden5); its piers and deck pieces
    move as one (lkden7, owner KDEN 2026-11-18T19:29Z "should move as a
    group")."""
    groups: dict[str, list[int]] = {}
    for k, pc in enumerate(pieces):
        r = _root(pc.body.anchor.reason)
        if r and _elevated(pc, walled_m):
            groups.setdefault(f"{pc.frame}|{r}", []).append(k)
        elif _is_overpass(pc):
            groups.setdefault(f"{pc.frame}|overpass:{pc.key[0]}", []).append(k)
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
        head = str(b.anchor.reason).split("; was:", 1)[0]
        if _AIRSIDE in head and _OVERPASS not in head:
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


def _contact(pc: _Piece, polys: _t.Sequence[tuple], tree: _t.Any, deck: _t.Sequence[tuple],
             pieces: _t.Sequence[_Piece], reach_m: float) -> list:
    """Where ``pc`` touches the deck: each deck part ring within ``reach_m``
    of one of its part rings in plan, the two DRAWN height spans no more
    than ``touch_graph.VETO_M`` apart -- that deck part's plan within
    ``reach_m`` of the building part."""
    from .touch_graph import VETO_M
    out = []
    for g, p in polys:
        for di in tree.query(g, predicate="dwithin", distance=reach_m).tolist():
            dg, dp, dk = deck[di]
            (a0, a1), (b0, b1) = _span(pieces[dk].zero, dp), _span(pc.zero, p)
            if max(a0, b0) - min(a1, b1) <= VETO_M:
                part = dg.intersection(g.buffer(reach_m))
                out.append(part if not part.is_empty else g)
    return out


def _nodes(pieces: _t.Sequence[_Piece], ks: _t.Sequence[int], xy: _t.Callable,
           law: _WarpLaw) -> tuple[list, list]:
    """``(nodes, riders)``: the group's BUILDING CONTACTS ``(D relative to
    the group zero, shapely contact, piece index)``, one per building, and
    the bodies of its own connected unit that touch it (module doc)."""
    from shapely.geometry import box as _box
    from shapely.ops import unary_union
    from shapely.strtree import STRtree
    inside = set(ks)
    deck = [(g, p, k) for k in ks for g, p in _polys_of(pieces[k], xy)]
    if not deck:
        return [], []
    tree = STRtree([g for g, _p, _k in deck])
    z0 = float(np.median([pieces[k].zero for k in ks]))
    frame, datum = pieces[ks[0]].frame, pieces[ks[0]].datum
    own = {_root(pieces[k].body.anchor.reason) for k in ks} - {""}
    over = any(_is_overpass(pieces[k]) for k in ks)
    rides = {pieces[k].name for k in ks} | own
    bx = np.asarray([g.bounds for g, _p, _k in deck])
    dbox = _box(bx[:, 0].min() - law.reach_m, bx[:, 1].min() - law.reach_m,
                bx[:, 2].max() + law.reach_m, bx[:, 3].max() + law.reach_m)
    buildings: dict[int, list[int]] = {}
    riders = []
    for c, pc in enumerate(pieces):
        m = str(getattr(pc.body, "merged_into", "") or "")
        if (c in inside or pc.body.body_class in ("deck", "basin", "line_segment")
                or (m and (m in rides or unit_root(m) in rides))):
            continue
        polys = _polys_of(pc, xy)
        if not any(dbox.intersects(g) for g, _p in polys):
            continue
        if pc.frame == frame and (_root(pc.body.anchor.reason) in own
                                  or (over and _overpass_seated(pc))):
            if _contact(pc, polys, tree, deck, pieces, law.reach_m):
                riders.append(c)
            continue
        if pc.datum[:2] == datum[:2]:
            buildings.setdefault(pc.key[0], []).append(c)
    out = []
    for cs in buildings.values():
        if not (any(pieces[c].footed for c in cs) and any(pieces[c].walled for c in cs)):
            continue
        hit, where = [], []
        for c in cs:
            at = _contact(pieces[c], _polys_of(pieces[c], xy), tree, deck, pieces, law.reach_m)
            if at:
                hit.append(c)
                where += at
        if hit:
            # the two frames' authored relation: one anchor, their lifts apart
            out.append((float(np.median([pieces[c].zero - pieces[c].datum[2] for c in hit]))
                        - (z0 - datum[2]), unary_union(where), hit[0]))
    return out, riders


def _end_nodes(pieces: _t.Sequence[_Piece], ks: _t.Sequence[int], xy: _t.Callable,
               surface: _t.Callable, z0: float, walled_m: float) -> list:
    """The deck's LANDING ENDS (module doc): ``(D, footprint, -1)`` each."""
    from shapely.geometry import MultiPoint
    cells, feet = [], []
    for k in ks:
        pc = pieces[k]
        dz = pc.zero - z0          # an authored y stands at zero + y
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
            out.append((d, MultiPoint([f[:2] for f, _g in foot]).convex_hull.buffer(0.5), -1))
    return out


def _centreline(plan: _t.Any) -> _t.Any:
    """The deck's CENTRELINE: the plan rastered every :data:`GRID_M` (wider
    past :data:`GRID_MAX_PTS` cells) and walked cell to cell from its first
    end (the low end of its principal axis; a gap in the plan -- a station
    between two deck pieces -- is jumped straight from the nearest cell
    reached); the shortest walk from that end's middle to the middle of the
    end farthest along it, resampled
    every :data:`TRACK_BIN_M` and smoothed -- so a curving deck's line
    follows its curve and a side piece hanging off it is no part of it."""
    from shapely import contains_xy, points
    from shapely.geometry import LineString
    from shapely.strtree import STRtree
    x0, y0, x1, y1 = plan.bounds
    h = max(GRID_M, math.sqrt(plan.area / GRID_MAX_PTS))
    gx, gy = np.meshgrid(np.arange(x0, x1 + h, h), np.arange(y0, y1 + h, h))
    ok = contains_xy(plan, gx, gy)
    cells = np.column_stack([gx[ok], gy[ok]])
    if cells.shape[0] < 2:
        return None
    rc = {(int(r), int(c)): i for i, (r, c) in enumerate(np.argwhere(ok))}
    mid = cells.mean(axis=0)
    _u, _s, vt = np.linalg.svd(cells - mid, full_matrices=False)
    sc = (cells - mid) @ vt[0]
    dist = np.full(cells.shape[0], np.inf)
    pred = np.full(cells.shape[0], -1)
    start = _middle(cells, np.flatnonzero(sc <= sc.min() + h))
    dist[start] = 0.0
    _walk(dist, pred, [(0.0, start)], rc, h)
    while not np.isfinite(dist).all():
        seen = np.flatnonzero(np.isfinite(dist))
        left = np.flatnonzero(~np.isfinite(dist))
        (iu, ir), gap = STRtree(points(cells[seen])).query_nearest(
            points(cells[left]), return_distance=True, all_matches=False)
        b = int(np.argmin(gap))
        i, j = int(left[iu[b]]), int(seen[ir[b]])
        dist[i], pred[i] = float(dist[j] + gap[b]), j
        _walk(dist, pred, [(float(dist[i]), i)], rc, h)
    path = [_middle(cells, np.flatnonzero(dist >= dist.max() - 2 * h))]
    while pred[path[-1]] >= 0:
        path.append(int(pred[path[-1]]))
    if len(path) < 2:
        return None
    raw = LineString(cells[path[::-1]])
    st = np.append(np.arange(0.0, raw.length, TRACK_BIN_M), raw.length)
    pts = np.asarray([raw.interpolate(float(q)).coords[0] for q in st])
    for _r in range(2):
        if pts.shape[0] > 2:
            pts[1:-1] = (pts[:-2] + pts[1:-1] + pts[2:]) / 3.0
    return LineString(pts)


def _middle(cells: np.ndarray, band: np.ndarray) -> int:
    """The cell of ``band`` nearest its centroid (an end's middle)."""
    return int(band[np.argmin(np.hypot(*(cells[band] - cells[band].mean(axis=0)).T))])


def _walk(dist: np.ndarray, pred: np.ndarray, heap: list, rc: dict, h: float) -> None:
    """Distances along the rastered plan from ``heap``'s cells, cell to
    cell over the 8 neighbours (``rc``: ``(row, col)`` -> cell), in place,
    each cell's predecessor in ``pred``."""
    import heapq
    at = {i: q for q, i in rc.items()}
    heapq.heapify(heap)
    while heap:
        d, i = heapq.heappop(heap)
        if d > dist[i]:
            continue
        r, c = at[i]
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                j = rc.get((r + dr, c + dc))
                if j is not None and (dr or dc):
                    w = d + h * math.hypot(dr, dc)
                    if w < dist[j]:
                        dist[j], pred[j] = w, i
                        heapq.heappush(heap, (w, j))


def _crossing_nodes(pieces: _t.Sequence[_Piece], ks: _t.Sequence[int],
                    xy: _t.Callable) -> list:
    """An overpass deck's CROSSING: ``(0, the road-beneath stations, -1)`` --
    the deck holds the zero the overpass seat read there (10-30f (5): its
    clearance over the road), so its landing ends grade away from it."""
    from shapely.geometry import MultiPoint
    out, seen = [], set()
    for k in ks:
        if not _is_overpass(pieces[k]) or id(pieces[k].member) in seen:
            continue
        seen.add(id(pieces[k].member))
        st = [xy(float(la), float(lo)) for la, lo, *_z in pieces[k].member.plate_stations]
        if st:
            out.append((pieces[k].zero - float(np.median([pieces[j].zero for j in ks])),
                        MultiPoint(st).convex_hull.buffer(GRID_M), -1))
    return out


def _station_span(line: _t.Any, g: _t.Any, plan: _t.Any) -> tuple[float, float]:
    """The stretch of the centreline a node's footprint covers: its part
    over the deck's plan (else its own) projected on the line."""
    import shapely
    part = g.intersection(plan)
    part = g if part.is_empty else part
    xy = shapely.get_coordinates(shapely.segmentize(part, GRID_M))
    st = shapely.line_locate_point(line, shapely.points(xy))
    return float(st.min()), float(st.max())


def _knots(spans: _t.Sequence[tuple], tol_m: float) -> list:
    """``[(station, D)]`` -- each node flat over its stretch, in order along
    the track; two overlapping stretches of different ``D`` part at their
    overlap's middle, :data:`TRACK_BIN_M` apart."""
    out: list[list[float]] = []
    for lo, hi, d in sorted(spans, key=lambda t: (t[0] + t[1]) / 2.0):
        if out and lo <= out[-1][0]:
            if abs(d - out[-1][1]) <= tol_m:
                out[-1][0] = max(out[-1][0], hi)
                continue
            m = (lo + out[-1][0]) / 2.0
            out[-1][0] = max(out[-2][0] if len(out) > 1 else -np.inf, m - TRACK_BIN_M / 2.0)
            lo = max(m + TRACK_BIN_M / 2.0, out[-1][0] + 1e-3)
        out += [[lo, d], [max(lo, hi), d]]
    return [(s, d) for s, d in out]


def _track(nodes: _t.Sequence[tuple], pieces: _t.Sequence[_Piece], ks: _t.Sequence[int],
           xy: _t.Callable, law: _WarpLaw, feet: _t.Sequence[tuple] = (),
           report: "dict | None" = None) -> "np.ndarray | None":
    """The deck's TRACK in local metres, ``[[x, y, D], ...]``: its
    centreline, each node flat over the stretch it covers and ``D`` linear
    in distance along the line between two (FIELD in the module doc) --
    bent between two to the ``feet`` ``[(x, y, T)]`` under the rail cap
    where ``law.radius_m`` arms it (BEND; ``deck_track_bend``), its
    report into ``report``."""
    from shapely.ops import unary_union
    plan = unary_union([g for k in ks for g, _p in _polys_of(pieces[k], xy)]).buffer(
        law.reach_m + GRID_M)
    line = _centreline(plan)
    if line is None:
        return None
    kn = _knots([(*_station_span(line, g, plan), d) for d, g, _c in nodes], law.tol_m)
    ks_, kd = np.asarray([k[0] for k in kn]), np.asarray([k[1] for k in kn])
    v = np.asarray(line.coords)
    vs = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(v, axis=0).T))])
    st = np.unique(np.concatenate([vs, np.clip(ks_, 0.0, line.length)]))
    pts = np.asarray([line.interpolate(float(q)).coords[0] for q in st])
    d = np.interp(st, ks_, kd)
    if feet and law.radius_m > 0.0:
        import shapely

        from .deck_track_bend import bend
        fa = np.asarray(feet, float)
        fs = shapely.line_locate_point(line, shapely.points(fa[:, :2]))
        d, rep = bend(st, d, kn, list(zip(fs.tolist(), fa[:, 2].tolist(), strict=True)),
                      grade_max=law.grade_max - 1e-6, radius_m=law.radius_m,
                      stretch_m=law.stretch_max_m)
        if report is not None:
            report.update(rep)
    return np.column_stack([pts, d])


def _field(track: "np.ndarray | None") -> _t.Any:
    from .obj8_warp import Field
    if track is None or len(track) < 2:
        return Field(())
    return Field((("track", tuple(map(tuple, track))),))


def _grade(track: np.ndarray) -> float:
    """The track's steepest grade: ``|dD|`` over the distance along it,
    vertex to vertex."""
    run = np.hypot(*np.diff(track[:, :2], axis=0).T)
    rise = np.abs(np.diff(track[:, 2]))
    keep = run > 1e-6
    return float((rise[keep] / run[keep]).max()) if keep.any() else 0.0


def _ll_frame(rec: _t.Any) -> _t.Callable:
    """``(lat, lon)`` -> the placement's authored ``(x, z)``
    (``placement_file.authored_offset``'s map)."""
    from .anchor_rule import _m_per_deg
    ml, mo = _m_per_deg(float(rec.lat))
    h = math.radians(float(rec.heading))
    s, c = math.sin(h), math.cos(h)

    def f(la: float, lo: float) -> tuple[float, float]:
        e, n = (lo - float(rec.lon)) * mo, (la - float(rec.lat)) * ml
        return (round(e * c - n * s, 4), round(-e * s - n * c, 4))
    return f


def _to_frame(rec: _t.Any, xy_inv: _t.Callable) -> _t.Callable:
    """local metres -> the placement's authored ``(x, z)``."""
    g = _ll_frame(rec)
    return lambda x, y: g(*xy_inv(x, y))


def _frame_track(rec: _t.Any, track: np.ndarray, d_off: float,
                 xy_inv: _t.Callable) -> tuple:
    """The track as an ``obj8_warp.Track`` in the placement's authored
    frame, ``D`` relative to its own zero."""
    to = _to_frame(rec, xy_inv)
    return (("track", tuple((*to(float(x), float(y)), round(float(d) - d_off, 4))
                            for x, y, d in track)),)


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
    groups = _groups(pieces, law.walled_m)
    grouped = {k for ks in groups.values() for k in ks}
    for gid, ks in sorted(groups.items()):
        if not _is_long(pieces, ks, xy):
            continue
        z0 = float(np.median([pieces[k].zero for k in ks]))
        nodes, riders = _nodes(pieces, ks, xy, law)
        riders = [c for c in riders if c not in grouped]   # warped by its own group
        nodes = nodes + _crossing_nodes(pieces, ks, xy)
        feet = (_end_nodes(pieces, ks, xy, surface, z0, law.walled_m)
                if surface is not None else [])
        ds = [d for d, _g, _c in nodes + feet]
        if len(ds) < 2 or max(ds) - min(ds) <= law.float_tol_m:
            continue
        nodes = nodes + feet
        row = {"group": gid, "bodies": len(ks), "zero": round(z0, 3),
               "nodes": [[round(d, 3), pieces[c].name] for d, _g, c in nodes if c >= 0],
               "feet": len(feet),
               "feet_d": [round(min(d for d, _g, _c in feet), 3),
                          round(max(d for d, _g, _c in feet), 3)] if feet else []}
        table.append(row)
        why = _refusal(pieces, ks)
        allk = list(ks) + riders
        out_of = {k: _left_out(pieces[k]) for k in allk} if not why else {}
        warped = [k for k in allk if not out_of.get(k)]
        bent: dict = {}
        track = (_track(nodes, pieces, ks, xy, law,
                        _targets(pieces, warped, xy, surface, z0)
                        if surface is not None else (), bent)
                 if not why else None)
        if not why and track is None:
            why = "no_track"
        if not why:
            g = _grade(track)
            row["grade"] = round(g, 4)
            if g > law.grade_max:
                why = "grade"
        if why:
            row["refused"] = why
            counts[f"warp_refused_{why}"] = counts.get(f"warp_refused_{why}", 0) + 1
            continue
        if bent.get("bent"):
            row["bend"] = bent
            counts["warp_track_bent"] = counts.get("warp_track_bent", 0) + bent["bent"]
        if bent.get("tight"):
            counts["warp_bend_tight"] = counts.get("warp_bend_tight", 0) + bent["tight"]
        if bent.get("infeasible"):
            counts["warp_bend_infeasible"] = (counts.get("warp_bend_infeasible", 0)
                                              + bent["infeasible"])
        ks = allk
        row["riders"] = len(riders)
        stretch = (_stretches(pieces, warped, track, xy, surface, law, z0)
                   if surface is not None else {})
        for k in ks:
            pc = pieces[k]
            if out_of[k]:
                why = out_of[k]
                counts[f"warp_left_out_{why}"] = counts.get(f"warp_left_out_{why}", 0) + 1
                row.setdefault("left_out", []).append([pc.name, why])
                continue
            i, j = pc.key
            rec = splits[i]
            warp = (_frame_track(rec, track, pc.zero - z0, xy_inv)
                    + _frame_feet(rec, stretch.get(k, ())))
            if stretch.get(k):
                counts["warp_feet_stretched"] = (counts.get("warp_feet_stretched", 0)
                                                 + len(stretch[k]))
                row["feet_stretched"] = row.get("feet_stretched", 0) + len(stretch[k])
            bs = list(rec.bodies)
            bs[j] = named_body(pc.member, bs[j], warp=warp)
            splits[i] = _dc.replace(rec, bodies=tuple(bs))
            changed.add(i)
        counts["deck_warped"] = counts.get("deck_warped", 0) + len(warped)
        counts["deck_warp_groups"] = counts.get("deck_warp_groups", 0) + 1
        if surface is not None:
            row["feet_floating"] = _floating(pieces, warped, track, xy, surface, law, z0)
            row["feet_floating_before"] = sum(
                1 for *_r, fl in _foot_floats(pieces, warped, None, xy, surface, z0)
                if fl > law.float_tol_m)
            # a member left out of the warp keeps its seat: its feet as seated
            row["feet_floating_left_out"] = sum(
                1 for *_r, fl in _foot_floats(pieces, [k for k in ks if out_of[k]], None,
                                              xy, surface, z0)
                if fl > law.float_tol_m)
            if row["feet_floating"]:
                counts["warp_feet_floating"] = (counts.get("warp_feet_floating", 0)
                                                + len(row["feet_floating"]))
    if changed:
        frames = [str(members[r.placement_id][0].id) if r.placement_id in members else ""
                  for r in splits]
        names = _recut(splits, frames, before, changed, cut_log or {}, write, counts)
        _renamed_riders(splits, frames, names)
    return splits, table


def _foot_floats(pieces: _t.Sequence[_Piece], ks: _t.Sequence[int],
                 track: "np.ndarray | None", xy: _t.Callable, surface: _t.Callable,
                 z0: float) -> _t.Iterator[tuple]:
    """``(k, lat, lon, authored y, float m)`` of every ground-contact foot
    of the members under the field of ``track`` (+ floats, - buried)."""
    f = _field(track)
    for k in ks:
        pc = pieces[k]
        for la, lo, y in pc.body.feet or ():
            x, yy = xy(float(la), float(lo))
            d = float(f.at(np.asarray([x]), np.asarray([yy]))[0]) - (pc.zero - z0)
            s = surface(float(la), float(lo))
            if s is None:
                continue
            yield (k, float(la), float(lo), float(y),
                   pc.zero + float(y) + d - float(s))


def _targets(pieces: _t.Sequence[_Piece], ks: _t.Sequence[int], xy: _t.Callable,
             surface: _t.Callable, z0: float) -> list:
    """``[(x, y, T)]``: each ground-contact foot of the members in local
    metres with the ``D`` that stands it on the ground at its authored
    height, ``T = ground - (z0 + y)`` (BEND in the module doc)."""
    return [(*xy(la, lo), -fl) for _k, la, lo, _y, fl
            in _foot_floats(pieces, ks, None, xy, surface, z0)]


def _stretches(pieces: _t.Sequence[_Piece], ks: _t.Sequence[int], track: np.ndarray,
               xy: _t.Callable, surface: _t.Callable, law: _WarpLaw, z0: float) -> dict:
    """``{k: ((lat, lon, authored y, drop), ...)}``: each floating foot's
    lowering, at most ``law.stretch_max_m`` (FEET in the module doc)."""
    out: dict[int, list] = {}
    if law.stretch_max_m <= 0.0:
        return out
    for k, la, lo, y, fl in _foot_floats(pieces, ks, track, xy, surface, z0):
        if fl > law.float_tol_m:
            out.setdefault(k, []).append((la, lo, y, round(min(fl, law.stretch_max_m), 3)))
    return out


def _frame_feet(rec: _t.Any, feet: _t.Sequence[tuple]) -> tuple:
    """The feet as ``obj8_warp.Foot`` items in the placement's authored
    frame (the bottom band is the foot's own authored y, 1 cm deep)."""
    g = _ll_frame(rec)
    return tuple(("foot", *g(la, lo), round(y + 0.01, 4), drop) for la, lo, y, drop in feet)


def _floating(pieces: _t.Sequence[_Piece], ks: _t.Sequence[int], track: np.ndarray,
              xy: _t.Callable, surface: _t.Callable, law: _WarpLaw, z0: float) -> list:
    """The warped members' ground-contact feet still floating more than the
    bar after their stretch: ``(lat, lon, float m)``, worst first."""
    out = []
    for _k, la, lo, _y, fl in _foot_floats(pieces, ks, track, xy, surface, z0):
        left = fl - (min(fl, law.stretch_max_m) if fl > law.float_tol_m else 0.0)
        if left > law.float_tol_m:
            out.append((round(la, 7), round(lo, 7), round(left, 3)))
    return sorted(out, key=lambda t: -t[2])
