"""A ONE-MOUTHED SHORT BORE IS A ROAD AT GRADE UNDER THE BUILDING (owner
RULINGS 2026-11-16h, #2079; with 2026-09-13bm (ii) "a tunnel with one
mouth is never right").

A MAPPED bore (every way a ``tunnel`` way, none synthesised) whose built
mouth's floor stands deeper than the bore can climb back out of at the
ramp cap — ``length × ramp_max_grade < mouth depth`` — to an UNOPENED far
end (no structure built there opens it, no pack object took it, and the
road does not go on underground from it or within the shortest lawful
ramp beyond it) where a mapped road LEAVES
AT GRADE is not built: no cut, no ramp; the road stays at grade under
the building.  Measured at RJTT bores -6785 / -6784
(53 / 58 m under building69): the SW mouth cut 7.50 m deep, the NE
mouth refused against the building pad, a 13.6–14.6 % through-grade
against the 10 % cap.

Applied by ``structures.build_structures`` in its "built whole or not at
all" loop (Law C), beside the sibling refusal: one pass, one refusal list.
"""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..model.frame import XY
from .structure_service import _layer_of, _osm_tunnel

__all__ = ["bore_end", "short_bore_refusal"]

#: two ends closer than this are one end (``structure_service._SAME_END_M``'s scale)
_SAME_END_M = 1.0


def _near(a: XY, b: XY, tol: float = _SAME_END_M) -> bool:
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def bore_end(m) -> tuple[int, int]:
    """``(id(bore), 0 | 1)``: which mapped end of its bore mouth ``m`` opens
    (the nearer end — a plate may have moved the mouth along the bore)."""
    p0, p1 = m.bore.points[0], m.bore.points[-1]
    d0 = math.hypot(m.xy[0] - p0[0], m.xy[1] - p0[1])
    d1 = math.hypot(m.xy[0] - p1[0], m.xy[1] - p1[1])
    return id(m.bore), 0 if d0 <= d1 else 1


def _ways_at(end: XY, osm_ways, own_ids: set, admitted) -> tuple[str | None, bool]:
    """``(the id of a mapped road or railway AT GRADE — no tunnel, no
    bridge, ``layer`` < 1 — with a node at ``end`` or ``None``, whether
    another TUNNEL way has a node there)``: the bore going on underground
    is no end at all (``bore_continuation``'s case)."""
    from ..airport.deck_signature import is_tunnel_way
    road, under = None, False
    for w in osm_ways:
        t = w.tags or {}
        if w.id in own_ids or len(w.points) < 2 or ("highway" not in t and "railway" not in t):
            continue
        if not any(_near(p, end) for p in w.points):
            continue
        if is_tunnel_way(t, admitted):
            under = True
        elif str(t.get("bridge", "")).strip().lower() in ("", "no") \
                and (_layer_of(t, 0) or 0) < 1 and road is None:
            road = str(w.id)
    return road, under


def _why_unopened(end: XY, ids: str, own_id: str, dropped, no_portal, refused) -> str:
    """Why no mouth stands at ``end``, in the admission's or the build's
    own words."""
    for wids, xy, d in dropped or ():
        if wids == ids and _near(xy, end):
            return f"off the field by {d:.0f} m (§29 (1))"
    for why in no_portal or ():
        if why and f"bore {ids}" in why:
            return why
    for why in refused or ():
        w = str(why)
        if w.startswith("tunnel:") and not w.startswith(own_id + ":") \
                and all(i in w.split(":", 2)[1] for i in ids.split("+")):
            return w
    return "no mouth admitted there"


def short_bore_refusal(tunnel, group, law: Law, osm_ways: _t.Sequence,
                       opened: _t.Collection[tuple[int, int]], dropped=(),
                       no_portal=(), refused=(), under_ends=(),
                       pad_ends: _t.Mapping[tuple[int, int], str] | None = None) -> str | None:
    """The refusal text for ``tunnel`` (built from ``group``) under RULINGS
    2026-11-16h, or ``None`` when it stands.  ``opened`` are the bore ends
    (:func:`bore_end`) a built structure opens or a pack object took;
    ``dropped`` / ``no_portal`` are the admission's own reports
    (``structure_approach.mouths``) and ``refused`` the build's, naming
    why an end opened none; ``under_ends`` the bore ends whose road goes
    on underground within the shortest lawful ramp (``bore_continuation``,
    recorded by ``mouths``): the road there is in its cut, not at grade.
    ``pad_ends`` maps the bore ends whose own mouth was refused standing
    against a BUILDING PAD to that pad's ref: only such an end is the
    owner's "flat road passing under the building" (master narrowing of
    16h, 2026-11-16: an off-field end, an end with no portal witness or no
    mouth, or a far mouth refused for any other reason — ramp cannot top
    out, slid past the road's end, bend, overlap — keeps today's
    behaviour)."""
    if group is None or group.corridor is not None or not group.members:
        return None
    if getattr(tunnel, "portal_seat", None):
        return None          # a pack portal states the mouth: authored, not a read
    depth = float(tunnel.mouth_dem_z) - float(tunnel.mouth_z)
    if not math.isfinite(depth) or depth <= 0.0:
        return None
    tn = law.tables.structures.tunnel
    parts = []
    for m in group.members:
        b = m.bore
        if not _osm_tunnel(b, tn.admitted_values):
            return None
        _bid, near_i = bore_end(m)
        far_i = 1 - near_i
        far = b.points[-1] if far_i else b.points[0]
        if (id(b), far_i) in opened or (id(b), far_i) in under_ends:
            return None      # two-mouthed, or the road stays below beyond the far end
        own = {w.id for w in b.ways}
        road, under = _ways_at(far, osm_ways, own, tn.admitted_values)
        if road is None or under:
            return None      # nothing leaves the far end at grade, or the bore goes on
        pad = (pad_ends or {}).get((id(b), far_i))
        if pad is None:
            return None      # the far mouth did not stand under a building: not 16h
        cap = tn.rail_ramp_max_grade if any("railway" in (w.tags or {}) for w in b.ways) \
            else tn.ramp_max_grade
        length = float(b.line.length)
        if length * cap >= depth:
            return None      # it can climb out at the cap: built as before
        ids = "+".join(str(w.id) for w in b.ways)
        parts.append(f"bore {ids} {length:.0f} m needs {100.0 * depth / length:.1f} % "
                     f"(cap {100.0 * cap:.0f} %) to climb from its {depth:.2f} m mouth floor "
                     f"to its unopened end at {far[0]:.0f},{far[1]:.0f} "
                     f"({_why_unopened(far, ids, tunnel.id, dropped, no_portal, refused)}), "
                     f"under building pad {pad}, where road {road} leaves at grade")
    return (f"{tunnel.id}: ONE-MOUTHED SHORT BORE — " + "; ".join(parts)
            + " — not built: no cut, no ramp, the road stays at grade under the "
              "building (owner RULINGS 2026-11-16h, #2079)")
