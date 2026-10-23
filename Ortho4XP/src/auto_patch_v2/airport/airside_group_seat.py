"""A CONNECTED GROUP THAT TOUCHES AIRSIDE SITS ON THE AIRSIDE (owner RULINGS
2026-10-22q; #1214 round 4).

Owner, LFPG 1.0.418: "terminal 2 and it connecting roads and multiple
buildings appear to be seated based on a location in the center where the
trench needs to be cut, so now they're floating.  Airside should be the
priority in this case as well, any building that part of it is touch
airside should be seated so it's airside is on the ground, even if that
means some other part is sunken (or floating)."

Round 3's one zero per connected unit (``open_frame_seat.root_zeros``) was
the MEDIAN of its pieces' zeros over their parts: T2's central block over
its road trench outvoted the halls that stand on the apron.  A frame's
share of a connected unit that touches airside PAVEMENT (an apron, a
taxiway: :func:`airside_pavement`; on it or within :data:`TOUCH_M`)
instead takes its zero from the AIRSIDE FLOOR (:func:`floor_plane`): over
those airside-contact feet, each foot says where the zero must be for it
to stand on the solved airside surface (``airside z - y``), and the floor
the aircraft side meets is the highest plane of feet; the deeper feet of a
sunken level — a basement, a road trench's walls — then sink, the parts
standing over lower ground float, and both are the terrain's to cut or
fill (#1138).  A share touching no airside keeps round 3's zero.
"""
from __future__ import annotations

import typing as _t

__all__ = ["airside_zeros", "airside_pavement", "floor_plane", "TOUCH_M",
           "AIRSIDE_SOURCE", "PLANE_SHARE", "PLANE_BAND_M"]

#: 22o / 22q: "touch or lie within 1 m of airside pavement or an apron"
TOUCH_M = 1.0
#: the source word a group seated here publishes
AIRSIDE_SOURCE = "airside contact"


def _probes(la: float, lo: float, ml: float, mo: float
            ) -> list[tuple[float, float]]:
    d_la, d_lo = TOUCH_M / ml, TOUCH_M / mo
    return [(la, lo), (la + d_la, lo), (la - d_la, lo), (la, lo + d_lo), (la, lo - d_lo)]


def airside_pavement(surface: _t.Any) -> "_t.Callable[[str | None], bool]":
    """22q's "airside pavement or an apron": the ROLLED-ON roles
    (``law.tables.rolled_on_roles`` — apron, taxiways, junctions, runway;
    ``surface.rolled_on`` where the stage attached it).  A building pad and
    the graded strip are airside by side but are not pavement."""
    rolled = getattr(surface, "rolled_on", None)
    if rolled is None:
        from ..law import Law
        from ..law import tables as _T
        rolled = frozenset(_T.rolled_on_roles(Law.load()))
    return lambda r: bool(r) and r in rolled


#: a PLANE of the airside-contact feet holds at least this share of them,
#: within :data:`PLANE_BAND_M` (the few feet of a stair or a sump are none)
PLANE_SHARE = 0.1
PLANE_BAND_M = 1.0


def floor_plane(zs: _t.Sequence[float]) -> "float | None":
    """THE AIRSIDE FLOOR among a group's airside-contact feet: each foot's
    zero candidate is ``airside z - y`` (where the group's zero must be for
    THAT foot to stand on the airside), and the floor the aircraft side
    meets is the HIGHEST plane of feet — the LOWEST plane of candidates
    holding :data:`PLANE_SHARE` of them within :data:`PLANE_BAND_M`; its
    median.  The feet of a sunken level (a basement, the walls of a road
    trench under the terminal) stand deeper and read higher candidates:
    LFPG T2's halls read 104-106, its trench walls 110-113, and the median
    of all of them floated the halls 5-7 m."""
    if not zs:
        return None
    v = sorted(float(z) for z in zs)
    need = max(1, int(PLANE_SHARE * len(v) + 0.999999))
    j = 0
    for i in range(len(v)):
        while v[j] < v[i] - PLANE_BAND_M:
            j += 1
        if i - j + 1 >= need:
            band = [x for x in v if v[j] <= x <= v[j] + PLANE_BAND_M]
            return band[len(band) // 2]
    return v[len(v) // 2]


def airside_zeros(plan: _t.Any, plan_wide: _t.Mapping[int, tuple],
                  surface: _t.Any, key_of: _t.Callable[[str, str], str],
                  own_ground: "dict[str, float] | None" = None
                  ) -> dict[str, tuple[float, int]]:
    """``key -> (zero, feet read)`` for every frame's share of a connected
    unit (``key_of(unit id, frame id)``) at least one of whose
    ground-contact feet stands on airside pavement or within
    :data:`TOUCH_M` of it: the :func:`floor_plane` of ``airside z - y``
    over those feet, in the frame's own authored frame.  ``own_ground``,
    when given, is filled with every share's OWN-GROUND zero: the median
    of ``ground - y`` over all its feet.  Line objects (their feet are
    drape stations) are not read."""
    roles = getattr(surface, "roles", None)
    if roles is None or not plan_wide:
        return {}
    from . import anchor_rule as _ar
    airside_role = airside_pavement(surface)
    feet: list[tuple[str, float, float, float]] = []
    for u in plan.units:
        for m in u.members:
            for p in m.parts:
                seat = plan_wide.get(p.pid)
                if not seat or not seat[0] or getattr(p, "line", False):
                    continue
                k = key_of(seat[0], str(u.id))
                for f in getattr(p, "feet", ()) or ():
                    feet.append((k, float(f[0]), float(f[1]), float(f[2])))
    if not feet:
        return {}
    pts: list[tuple[float, float]] = []
    for _k, la, lo, _y in feet:
        ml, mo = _ar._m_per_deg(la)
        pts.extend(_probes(la, lo, ml, mo))
    got = roles.roles_many([q[0] for q in pts], [q[1] for q in pts])
    n = len(_probes(0.0, 0.0, 1.0, 1.0))
    acc: dict[str, list[float]] = {}
    ground: dict[str, list[float]] = {}
    for i, (k, la, lo, y) in enumerate(feet):
        g = surface(la, lo)
        if g is not None:
            ground.setdefault(k, []).append(float(g) - y)
        hit = next((j for j in range(n) if airside_role(got[i * n + j])), None)
        if hit is None:
            continue
        z = surface(*pts[i * n + hit])
        if z is not None:
            acc.setdefault(k, []).append(float(z) - y)
    out = {}
    for k, zs in acc.items():
        z = floor_plane(zs)
        if z is not None:
            out[k] = (z, len(zs))
    if own_ground is not None:
        for k, zs in ground.items():
            zs.sort()
            own_ground[k] = zs[len(zs) // 2]
    return out
