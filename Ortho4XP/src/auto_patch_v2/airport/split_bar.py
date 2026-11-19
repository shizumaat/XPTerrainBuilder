"""A PLACEMENT IS SPLIT ONLY WHERE ITS BODIES' SEATS DIFFER BY MORE THAN THE
GROUND BAR (owner RULINGS 2026-11-19j).

Owner, 2026-11-19T01:35Z: "use our 0.5m rule, not 5cm... within 0.5m the
terrain should be able to adapt to any discrepancies and keep the objects
as authored."  The 0.5 m is the ground visibility bar of RULINGS 09-12y
(the lanes' 10-15 bar: pavement 0.05 m, ground 0.5 m), ``[placement]
split_bar_m``.

:func:`keep_whole` runs ONCE, last in ``placement_plan.build_splits`` --
after the touch pass and the deck warp, over the FINAL bodies, so the seat
spread it reads is the one the stage would write.  Per placement record
of two or more bodies, its spread S = max - min of the bodies' zeros
(``surface_z - y_zero``, the world height of the authored y = 0 plane):

* S > the bar: the split stands (counted ``split_bar_split``);
* otherwise the placement is written WHOLE -- ONE body, ONE file, every
  component at its authored place -- at ONE zero Z, and every body of it
  moves by ``Z - its zero`` (at most the bar).

Z is the zero of the ANCHOR body: the senior body (a ground body, most
ground-contact feet, then the first) among the HELD bodies when there are
any, else among all.  A body is HELD where its zero is shared with ANOTHER
placement: a touching group (``touch_seat``'s ``shared_bodies``: "a
terminal or cluster group always seats as one unit"), a §16g unit or 22o
group (its ``family`` seats bodies of another record), a carrier of
another record's rider, a piece riding another record's or a unit's file.
The held bodies of one placement must agree (within :data:`SAME_ZERO_M`);
where they do not, the placement belongs to two groups at two zeros and
stays split (listed, ``held_disagree``) -- no group is moved here.

A placement whose seat is more than a zero stays as it is (counted by why):
a seat TILT (10-01k Q1, 18h (4)), a deck WARP (#2144) or plate BAND
(#2112), a DRAPED slab (14d (1)), a plate-kind member (a split-level
building's zero is its lower floor's datum), a row-held ``OBJECT_MSL``
body (#1903), a bridge cluster (§16e (3)), a body read on no surface, or
unequal authored lifts (14g (1)).

THE GROUND SIDE.  Nothing re-grades the terrain here: the design surface
was solved before the stage, and the whole placement must stand on it
within the bar.  Each candidate's ground-contact feet are read before and
after (``float = zero + authored y - ground``); where writing it whole
would leave a foot floating or buried more than the bar, and worse than
its own seat left it, the split stands (``split_bar_ground``, listed in
the table's ``ground`` rows) -- the terrain cannot absorb that.

The merged record is CUT AGAIN (``placement_file.recut``, written even as
one body) and every rider's ``merged_into`` that named one of its old
files follows the one new file.  Nothing here names an airport, a pack or
a resource.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from .placement_boxes import hull_of
from .placement_geom import GEOM_PTS_MAX, thin_points
from .placement_motion import ground_contact_feet
from .placement_targets import _zero    # the body's zero (``tilt_float`` reads it too)

__all__ = ["law_of", "keep_whole", "REASON", "SAME_ZERO_M"]

#: two held zeros closer than this are one zero (the plan's rounding)
SAME_ZERO_M = 1e-3
#: the whole body's reason
REASON = "whole: seats within {bar:g} m, at {z:.2f} (RULINGS 2026-11-19j)"


@_dc.dataclass(frozen=True)
class _BarLaw:
    """``[placement] split_bar_m`` and the feet tolerance the ground check
    reads (``[placement] split_tol_m``)."""

    bar_m: float
    contact_tol_m: float = 0.0


def law_of(placement: _t.Any) -> "_BarLaw | None":
    """The pass's law from a ``[placement]`` table; ``None`` (disarmed)
    where ``split_bar_m`` is absent or not positive."""
    bar = float(getattr(placement, "split_bar_m", 0.0) or 0.0)
    if bar <= 0.0:
        return None
    return _BarLaw(bar, float(getattr(placement, "split_tol_m", 0.0) or 0.0))


def _stays(rec: _t.Any, m: _t.Any, args: "tuple | None") -> str:
    """Why ``rec`` keeps its seat whatever its spread, or ``""``."""
    bs = rec.bodies
    if args is None:
        return "uncut"
    if getattr(m, "plate_kind", ""):
        return "plate"
    if args[2]:
        return "drape"
    checks = (("off_surface", lambda b: b.anchor.surface_z is None),
              ("tilt", lambda b: getattr(getattr(b, "seat", None), "applied", False)),
              ("warp", lambda b: bool(getattr(b, "warp", ()))),
              ("band", lambda b: getattr(b, "band", None) is not None),
              ("msl", lambda b: getattr(b, "msl_z", None) is not None),
              ("bridge", lambda b: bool(b.bridge_of)))
    for why, hit in checks:
        if any(hit(b) for b in bs):
            return why
    if len({round(float(b.lift_m or 0.0), 3) for b in bs}) > 1:
        return "lift"
    return ""


class _Links:
    """Which bodies share their zero with ANOTHER record (module doc)."""

    def __init__(self, splits: _t.Sequence[_t.Any], frames: _t.Sequence[str],
                 shared: _t.AbstractSet[tuple[str, int]]):
        self.shared = shared
        self.file_rec: dict[tuple[str, str], int] = {}
        self.fam: dict[tuple[str, str], set[int]] = {}
        for ri, rec in enumerate(splits):
            for b in rec.bodies:
                self.file_rec[(frames[ri], str(b.new_resource))] = ri
                if b.anchor.family:
                    self.fam.setdefault((frames[ri], str(b.anchor.family)), set()).add(ri)
        self.ridden: set[tuple[str, str]] = set()
        for ri, rec in enumerate(splits):
            for b in rec.bodies:
                c = self.file_rec.get((frames[ri], str(b.merged_into or "")))
                if c is not None and c != ri:
                    self.ridden.add((frames[ri], str(b.merged_into)))

    def held(self, ri: int, frame: str, rec: _t.Any, b: _t.Any) -> bool:
        """Is body ``b`` of record ``ri`` seated with another record?"""
        if (str(rec.placement_id), int(b.body_id)) in self.shared:
            return True
        if b.anchor.family and len(self.fam.get((frame, str(b.anchor.family)), ())) > 1:
            return True
        if (frame, str(b.new_resource)) in self.ridden:
            return True
        into = str(b.merged_into or "")
        return bool(into) and self.file_rec.get((frame, into), -1) != ri


def _senior(bodies: _t.Sequence[_t.Any], idx: _t.Iterable[int]) -> int:
    """The anchor body among ``idx``: a ground body before an elevated one,
    then the most ground-contact feet, then the first."""
    return min(idx, key=lambda j: (bool(bodies[j].elevated), -len(bodies[j].feet), j))


def _whole(rec: _t.Any, m: _t.Any, k: int, z: float, bar: float) -> _t.Any:
    """``rec``'s bodies as ONE body: body ``k`` (seated at ``z``) holding
    every component, part and foot of the others, its file renamed."""
    from .placement_file import named_body  # R1: the one file-name rule
    bs = rec.bodies
    a = bs[k]
    why = REASON.format(bar=bar, z=z)
    anchor = _dc.replace(a.anchor, reason=f"{why}; was: {a.anchor.reason}")
    body = _dc.replace(
        a, components=tuple(sorted({c for b in bs for c in b.components})),
        pids=tuple(sorted({p for b in bs for p in b.pids})),
        feet=tuple(f for b in bs for f in b.feet),
        cut_components=tuple(sorted({c for b in bs for c in b.cut_components})),
        tris=tuple(t for b in bs for t in b.tris), elevated=False,
        elevated_members=sum(int(b.elevated_members) for b in bs),
        plan_box=hull_of(b.plan_box for b in bs if b.plan_box is not None),
        geom_box=hull_of(b.geom_box for b in bs if b.geom_box is not None),
        foot_boxes=tuple(fb for b in bs for fb in b.foot_boxes),
        geom_pts=thin_points([q for b in bs for q in b.geom_pts], GEOM_PTS_MAX))
    return named_body(m, body, anchor=anchor)


def _ground(rec: _t.Any, z: float, surface: _t.Any, law: _BarLaw,
            band_m: float) -> tuple:
    """``(worst float before, after, worst burial before, after)`` of the
    record's ground-contact feet, each body at its own zero before and at
    ``z`` after (``+`` floats)."""
    fb = fa = bb = ba = 0.0
    if surface is None:
        return fb, fa, bb, ba
    for b in rec.bodies:
        zb = _zero(b)
        for f in ground_contact_feet(b.feet or (), band_m, law.contact_tol_m):
            g = surface(float(f[0]), float(f[1]))
            if g is None:
                continue
            before, after = zb + float(f[2]) - float(g), z + float(f[2]) - float(g)
            fb, fa = max(fb, before), max(fa, after)
            bb, ba = max(bb, -before), max(ba, -after)
    return fb, fa, bb, ba


def _decide(ri: int, rec: _t.Any, frame: str, m: _t.Any, args: "tuple | None",
            links: _Links, bar: float) -> tuple[str, "tuple[int, float] | None", float]:
    """``(verdict, (anchor body, Z) | None, spread)`` for one record."""
    why = _stays(rec, m, args)
    if why:
        return why, None, 0.0
    bs = rec.bodies
    zs = [_zero(b) for b in bs]
    s = max(zs) - min(zs)
    if s > bar:
        return "split", None, s
    held = [j for j, b in enumerate(bs) if links.held(ri, frame, rec, b)]
    if held and max(zs[j] for j in held) - min(zs[j] for j in held) > SAME_ZERO_M:
        return "held_disagree", None, s
    k = _senior(bs, held or range(len(bs)))
    return "whole", (k, zs[k]), s


def keep_whole(splits: _t.Sequence[_t.Any], plan: _t.Any, counts: dict, *,
               law: _BarLaw, surface: _t.Any = None,
               cut_log: "_t.Mapping[int, tuple] | None" = None, write: bool = False,
               shared: _t.Iterable[tuple[str, int]] = (),
               band_m: float = 0.0) -> tuple[list, dict]:
    """``(splits, table)``: every placement within the bar written whole
    (module doc).  ``cut_log`` is ``placement_file._cut_and_file``'s;
    ``shared`` the touch pass's ``shared_bodies``; ``surface`` the ground
    the feet are read on (``None``: no ground check) and ``band_m`` the
    plan's foot band (``[basin] contact_band_m``)."""
    from .placement_file import recut
    splits = list(splits)
    members = {m.id: (u, m) for u in plan.units for m in u.members}
    frames = [str(members[r.placement_id][0].id) if r.placement_id in members else ""
              for r in splits]
    links = _Links(splits, frames, {(str(p), int(b)) for p, b in shared})
    cut_log = cut_log or {}
    table: dict = {"whole": [], "held_disagree": [], "moved": [], "ground": []}
    names: dict[tuple[str, str], str] = {}

    def add(k: str, v: int = 1) -> None:
        counts[k] = counts.get(k, 0) + v
    for ri, rec in enumerate(splits):
        if len(rec.bodies) < 2 or rec.placement_id not in members:
            continue
        m = members[rec.placement_id][1]
        args = cut_log.get(ri)
        verdict, seat, s = _decide(ri, rec, frames[ri], m, args, links, law.bar_m)
        if verdict == "held_disagree":
            table["held_disagree"].append((rec.index, str(rec.resource), round(s, 3)))
        if verdict != "whole":
            add(f"split_bar_{verdict}")
            continue
        k, z = seat
        g = _ground(rec, z, surface, law, band_m)
        if (g[1] > law.bar_m and g[1] > g[0] + SAME_ZERO_M) or \
                (g[3] > law.bar_m and g[3] > g[2] + SAME_ZERO_M):
            table["ground"].append((rec.index, str(rec.resource), *(round(q, 3) for q in g)))
            add("split_bar_ground")
            continue
        new = recut(_dc.replace(rec, bodies=(_whole(rec, m, k, z, law.bar_m),)),
                    (args[0], True, args[2], args[3]), write, counts)
        if new is None:
            add("split_bar_recut_refused")
            continue
        _record(table, rec, z, s)
        for b in rec.bodies:
            names[(frames[ri], str(b.new_resource))] = str(new.bodies[0].new_resource)
        add("split_bar_whole")
        add("split_bar_bodies_joined", len(rec.bodies) - 1)
        splits[ri] = new
    _follow(splits, frames, names, counts)
    if table["moved"]:
        add("split_bar_bodies_moved", len(table["moved"]))
    return splits, table


def _record(table: dict, rec: _t.Any, z: float, s: float) -> None:
    """One whole record's rows: the placement and its moved bodies."""
    table["whole"].append((rec.index, str(rec.resource), len(rec.bodies),
                           round(s, 3), round(z, 3)))
    for b in rec.bodies:
        if abs(z - _zero(b)) > SAME_ZERO_M:
            table["moved"].append((rec.index, int(b.body_id), str(b.new_resource),
                                   round(_zero(b), 3), round(z, 3)))


def _follow(splits: list, frames: _t.Sequence[str],
            names: _t.Mapping[tuple[str, str], str], counts: dict) -> None:
    """Every ``merged_into`` naming a file a whole record no longer writes
    names the one file it now writes."""
    n = 0
    for ri, rec in enumerate(splits):
        bs = []
        for b in rec.bodies:
            to = names.get((frames[ri], str(b.merged_into or "")))
            bs.append(_dc.replace(b, merged_into=to) if to and to != b.merged_into else b)
        k = sum(1 for a, b in zip(rec.bodies, bs, strict=True) if a is not b)
        if k:
            splits[ri] = _dc.replace(rec, bodies=tuple(bs))
            n += k
    if n:
        counts["split_bar_riders_renamed"] = counts.get("split_bar_riders_renamed", 0) + n
