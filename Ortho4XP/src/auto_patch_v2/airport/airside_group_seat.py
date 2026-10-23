"""A CONNECTED GROUP THAT TOUCHES AIRSIDE SITS ON THE AIRSIDE (owner RULINGS
2026-10-22q; #1214 round 4).

Owner, LFPG 1.0.418: "terminal 2 and it connecting roads and multiple
buildings appear to be seated based on a location in the center where the
trench needs to be cut, so now they're floating.  Airside should be the
priority in this case as well, any building that part of it is touch
airside should be seated so it's airside is on the ground, even if that
means some other part is sunken (or floating)."

Round 3's one zero per connected unit (``open_frame_seat.root_zeros``) was
the MEDIAN of its pieces' zeros.  A frame's share of a connected unit that
touches airside PAVEMENT (an apron, a taxiway: :func:`airside_pavement`; on
it or within :data:`TOUCH_M`) instead takes its zero from the AIRSIDE FLOOR
(:func:`floor_plane`): over the feet of its WALLED parts touching the
pavement, each foot says where the zero must be for it to stand on the
solved airside surface (``airside z - y``), and the floor is the
FOUNDATION — the lowest substantial plane of those feet, read on the feet
nearest the aircraft stands and jetways (owner RULINGS 2026-10-23b).  Round 4 took the
highest plane: KMCI's concourse walls (y -1.1) stood on the apron and the
complex sank a storey (owner, 1.0.420); the curb plane (y -5.8) is its
floor.  What then sinks or floats is the terrain's to cut or fill
(#1138).  A share touching no airside keeps round 3's zero.
"""
from __future__ import annotations

import typing as _t

__all__ = ["airside_zeros", "airside_pavement", "floor_plane", "stands_of", "STAND_M",
           "TOUCH_M",
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
#: within :data:`PLANE_BAND_M` ...
PLANE_SHARE = 0.1
PLANE_BAND_M = 1.0
#: ...and at least this many feet (or half of them, for a small share):
#: what rules out a STRAY PIECE — one wall strip of a building standing
#: in an uncut trench (LFPG 2A_1: 12 edge feet) is no airside floor
PLANE_MIN_FEET = 20


def floor_plane(zs: _t.Sequence[float]) -> "float | None":
    """THE AIRSIDE FLOOR among a group's airside-contact feet (RULINGS
    2026-10-22q as read by #1214 round 5): each foot's zero candidate is
    ``airside z - y`` (where the group's zero must be for THAT foot to
    stand on the airside), and the floor that meets the apron is the
    FOUNDATION — the LOWEST substantial plane of feet, i.e. the HIGHEST
    plane of candidates holding :data:`PLANE_SHARE` of them and
    :data:`PLANE_MIN_FEET` (or half of them) within :data:`PLANE_BAND_M`;
    its median.  The feet above it are the building's upper storeys.
    Round 4 took the highest plane of feet: KMCI's concourse walls at
    y -1.1 stood on the apron and the complex sank a storey (owner,
    1.0.420); its curb plane at y -5.8 is the floor (zero 310.7)."""
    if not zs:
        return None
    v = sorted((float(z) for z in zs), reverse=True)
    need = max(1, int(PLANE_SHARE * len(v) + 0.999999),
               min(PLANE_MIN_FEET, int(0.5 * len(v) + 0.999999)))
    j = 0
    for i in range(len(v)):
        while v[j] > v[i] + PLANE_BAND_M:
            j += 1
        if i - j + 1 >= need:
            band = [x for x in v if v[j] - PLANE_BAND_M <= x <= v[j]]
            band.sort()
            return band[len(band) // 2]
    return sorted(v)[len(v) // 2]


#: 2026-10-23b: the airside edge "closest to jetways or aircraft stands":
#: an airside-contact foot within this distance of a stand or a jetway
STAND_M = 60.0
#: the apt.dat 1300 startup kinds that are AIRCRAFT STANDS
STAND_KINDS = ("gate", "tie_down")
#: apt.dat row 1500: a jetway (its root position)
ROW_JETWAY = "1500"


def stands_of(plan: _t.Any) -> list[tuple[float, float]]:
    """The airport's aircraft STANDS and JETWAYS as ``(lat, lon)``: the
    apt.dat 1300 startups of kind :data:`STAND_KINDS` and the 1500 jetway
    rows of the pack's own ``Earth nav data/apt.dat`` (``plan.pack_root``,
    ``plan.icao``).  Empty where the pack carries none."""
    import os
    from . import apt_dat as _ad
    root = str(getattr(plan, "pack_root", "") or "")
    icao = str(getattr(plan, "icao", "") or "")
    path = os.path.join(root, "Earth nav data", "apt.dat")
    if not root or not icao or not os.path.isfile(path):
        return []
    try:
        block = _ad.read_airport_block(path, icao)
    except OSError:
        return []
    if not block:
        return []
    out = [(float(x.lat), float(x.lon)) for x in _ad.parse_airport_block(block).startups
           if x.kind in STAND_KINDS]
    for ln in block:
        t = ln.split()
        if len(t) > 2 and t[0] == ROW_JETWAY:
            try:
                out.append((float(t[1]), float(t[2])))
            except ValueError:
                pass
    return out


def _near_stand(stands: _t.Sequence[tuple[float, float]]
                ) -> "_t.Callable[[float, float], bool]":
    """``(lat, lon) -> within STAND_M of a stand`` over a 60 m grid."""
    from . import anchor_rule as _ar
    if not stands:
        return lambda la, lo: False
    lat0 = stands[0][0]
    ml, mo = _ar._m_per_deg(lat0)
    cells: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for la, lo in stands:
        x, y = la * ml, lo * mo
        cells.setdefault((int(x // STAND_M), int(y // STAND_M)), []).append((x, y))

    def near(la: float, lo: float) -> bool:
        x, y = la * ml, lo * mo
        cx, cy = int(x // STAND_M), int(y // STAND_M)
        return any((x - a) ** 2 + (y - b) ** 2 <= STAND_M * STAND_M
                   for i in (-1, 0, 1) for j in (-1, 0, 1)
                   for a, b in cells.get((cx + i, cy + j), ()))
    return near


def airside_zeros(plan: _t.Any, plan_wide: _t.Mapping[int, tuple],
                  surface: _t.Any, key_of: _t.Callable[[str, str], str],
                  own_ground: "dict[str, float] | None" = None
                  ) -> dict[str, tuple[float, int]]:
    """``key -> (zero, feet read)`` for every frame's share of a connected
    unit (``key_of(unit id, frame id)``) at least one of whose
    ground-contact feet stands on airside pavement or within
    :data:`TOUCH_M` of it: the :func:`floor_plane` of ``airside z - y``
    over the feet of its WALLED parts on the pavement or within
    :data:`TOUCH_M` of it — those within :data:`STAND_M` of an aircraft
    stand or a jetway (:func:`stands_of`) where any are, owner RULINGS
    2026-10-23b — in the frame's own authored frame.  ``own_ground``,
    when given, is filled with every share's OWN-GROUND zero: the median
    of ``ground - y`` over all its feet.  Line objects (their feet are
    drape stations) are not read."""
    roles = getattr(surface, "roles", None)
    if roles is None or not plan_wide:
        return {}
    from . import anchor_rule as _ar
    airside_role = airside_pavement(surface)
    feet: list[tuple[str, float, float, float, bool, str]] = []
    from ..law import Law
    # the WALLED parts (``[placement] chain_min_height_m``): a foundation or
    # a curb wall meets the apron; a floor slab, a sign or a bollard does not
    wall_min = float(Law.load().tables.structures.placement.chain_min_height_m)
    for u in plan.units:
        for m in u.members:
            for p in m.parts:
                seat = plan_wide.get(p.pid)
                if not seat or not seat[0] or getattr(p, "line", False):
                    continue
                k = key_of(seat[0], str(u.id))
                walled = float(getattr(p, "height_m", 0.0) or 0.0) >= wall_min
                for f in getattr(p, "feet", ()) or ():
                    feet.append((k, float(f[0]), float(f[1]), float(f[2]), walled,
                                 str(m.id)))
    if not feet:
        return {}
    pts: list[tuple[float, float]] = []
    for _k, la, lo, _y, _w, _m in feet:
        ml, mo = _ar._m_per_deg(la)
        pts.extend(_probes(la, lo, ml, mo))
    got = roles.roles_many([q[0] for q in pts], [q[1] for q in pts])
    n = len(_probes(0.0, 0.0, 1.0, 1.0))
    acc: dict[str, list[float]] = {}
    at_stand: dict[str, list[float]] = {}
    _stands = stands_of(plan)
    has_stands = bool(_stands)
    near = _near_stand(_stands)
    ground: dict[str, list[float]] = {}
    for i, (k, la, lo, y, walled, _mid) in enumerate(feet):
        g = surface(la, lo)
        if g is not None:
            ground.setdefault(k, []).append(float(g) - y)
        if not walled:
            continue
        hit = next((j for j in range(n) if airside_role(got[i * n + j])), None)
        if hit is None:
            continue
        z = surface(*pts[i * n + hit])
        if z is not None:
            acc.setdefault(k, []).append(float(z) - y)
            if near(la, lo):
                at_stand.setdefault(k, []).append(float(z) - y)
    out = {}
    for k, zs in acc.items():
        # 2026-10-23b: the plane the STAND-SIDE feet hold — "the airside
        # edge of buildings closest to jetways or aircraft stands must sit
        # on the apron" — else every airside-contact foot
        # with stands in the airport but too few stand-side feet in this
        # share (a stray wall end near a stand) there is no witness, and
        # the share keeps round 3's zero
        near_zs = at_stand.get(k) or []
        if has_stands:
            if len(near_zs) < PLANE_MIN_FEET:
                continue
            zs = near_zs
        z = floor_plane(zs)
        if z is not None:
            out[k] = (z, len(zs))
    if own_ground is not None:
        for k, zs in ground.items():
            zs.sort()
            own_ground[k] = zs[len(zs) // 2]
    return out
