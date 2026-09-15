"""THE OPEN CHANNEL'S TWO LAW FAMILIES (spec §45 C14; owner RULINGS
2026-09-15i) — lane ``v2channel``.

``channel_floor_at_declaration`` — the emitted floor equals the RECORD's
own profile (± the materiality floor).  ``channel_crest_at_edge`` — an
emitted crest vertex equals the adjacent governed cell's emitted level
(± the same), which is what ``crest = "design"`` MEANS: the crest is the
solved surface at the corridor edge and never ``DEM(x, y)``.

Both read the SIDECAR's ``channel_facilities`` record — the same
``Channel.floor_z(s)`` the generator stated the pin with
(``pipeline/publication.channel_facilities`` publishes it per station).
A second arithmetic here is exactly the drift §24 (5) had to go back and
fix; there is one, and this module does not own it.
"""
from __future__ import annotations

import math

from .frame import Patch, Row, Shape, row

__all__ = ["channel_floor_at_declaration", "channel_crest_at_edge",
           "FAMILY_FLOOR", "FAMILY_CREST", "FLOOR_REF", "WALL_REF"]

FAMILY_FLOOR = "channel_floor_at_declaration"
FAMILY_CREST = "channel_crest_at_edge"

#: The refs ``planar/channel.py`` writes.  A ``tunnel_trench`` face whose
#: ref begins ``basin_floor:`` is a BASIN's and is judged by §24's family
#: (``verify/structures._basin_floors`` keys on that prefix), so the two
#: populations never mix.
FLOOR_REF = "channel_floor:"
WALL_REF = "channel_wall:"

#: The materiality both families judge at (§45 C14: "± 0.01").
TOL_M = 0.01


def _floors(p: Patch) -> list[Shape]:
    return [sh for sh in p.shapes
            if sh.role == "tunnel_trench" and sh.ref.startswith(FLOOR_REF)]


def _crests(p: Patch) -> list[Shape]:
    return [sh for sh in p.shapes
            if sh.role == "retaining_wall" and sh.ref.startswith(WALL_REF)]


def _records(p: Patch) -> list[dict]:
    recs = (p.publication or {}).get("channel_facilities") or []
    return [r for r in recs if isinstance(r, dict)]


def _profile_of(rec: dict) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    for item in rec.get("floor_profile") or ():
        try:
            la, lo, z = float(item[0]), float(item[1]), float(item[2])
        except (TypeError, ValueError, IndexError):
            continue
        out.append((la, lo, z))
    return out


def _declared_at(p: Patch, prof: list[tuple[float, float, float]],
                 lat: float, lon: float) -> float | None:
    """The record's floor over a point: the two NEAREST profile stations,
    interpolated between them — the stations are the axis's own, so
    "nearest two" is "the segment this vertex stands over"."""
    if not prof:
        return None
    x, y = p.to_m(lat, lon)
    d = []
    for la, lo, z in prof:
        px, py = p.to_m(la, lo)
        d.append((math.hypot(px - x, py - y), z))
    d.sort()
    if len(d) == 1 or d[0][0] <= 1e-9:
        return d[0][1]
    d0, z0 = d[0]
    d1, z1 = d[1]
    t = d0 / max(d0 + d1, 1e-9)
    return z0 + (z1 - z0) * t


def channel_floor_at_declaration(p: Patch) -> list[Row]:
    """§45 (3): every emitted channel-floor vertex stands at the record's
    own profile.  A row here means the solve moved the floor off the
    datum the channel DECLARED — the pack's plate, the credible lidar's
    DTM, or the deck top less ``bridge.clearance_m``."""
    recs = _records(p)
    if not recs:
        return []
    by_id = {str(r.get("id") or ""): _profile_of(r) for r in recs}
    tol = float(p.law.tables.emit.materiality.elevation_m)
    out: list[Row] = []
    for sh in _floors(p):
        key = "channel:" + sh.ref[len(FLOOR_REF):].split("#")[0]
        prof = by_id.get(key)
        if not prof:
            continue
        for k, v in enumerate(sh.ids):
            lat, lon = p.ll[v]
            want = _declared_at(p, prof, lat, lon)
            if want is None:
                continue
            got = float(sh.z[k])
            if abs(got - want) <= tol + 1e-9:
                continue
            out.append(row(FAMILY_FLOOR, ("tunnel_trench",) * 2, "airside",
                           abs(got - want), None, None, None, sh.xy[k], sh.xy[k],
                           sh.key, None, lat=lat, lon=lon,
                           out_of_scope=(f"{key}: the emitted floor {got:.2f} stands "
                                         f"{got - want:+.2f} m off the record's declared "
                                         f"profile {want:.2f}")))
    return out


def channel_crest_at_edge(p: Patch) -> list[Row]:
    """§45 (5): a channel's crest IS the governed cell's emitted level at
    the corridor edge.

    An emitted crest vertex the governed ground SHARES is one node and
    one value by construction; the population judged here is the crest
    vertex that stands within the identity spacing of a governed,
    non-structure ring vertex WITHOUT sharing its id — the case where the
    weld did not join them and a step could hide.  A crest vertex on bare
    adjacent ground has no governed neighbour and is not judged: §19 and
    the zone laws govern it, and (5) forbids the DEM here."""
    recs = _records(p)
    if not recs:
        return []
    tol = float(p.law.tables.emit.materiality.elevation_m)
    reach = float(p.law.tables.emit.identity.weld_spacing_m)
    structure = {"tunnel_trench", "retaining_wall", "tunnel_ramp", "door_ramp",
                 "wall_corridor_ramp", "garage_ramp"}
    ground: list[tuple[float, float, float, Shape, int]] = []
    for sh in p.shapes:
        if sh.role in structure or p.cap(sh) is None:
            continue
        for v, (x, y) in zip(sh.ids, sh.xy):
            ground.append((x, y, float(p.z[v]), sh, v))
    if not ground:
        return []
    out: list[Row] = []
    for sh in _crests(p):
        for v, (x, y) in zip(sh.ids, sh.xy):
            best = None
            for gx, gy, gz, gsh, gv in ground:
                if gv == v:
                    best = None
                    break                       # shared node: one value
                d = math.hypot(gx - x, gy - y)
                if d <= reach and (best is None or d < best[0]):
                    best = (d, gz, gsh, (gx, gy))
            if best is None:
                continue
            _d, gz, gsh, (gx0, gy0) = best
            got = float(p.z[v])
            if abs(got - gz) <= tol + 1e-9:
                continue
            lat, lon = p.ll[v]
            out.append(row(FAMILY_CREST, ("retaining_wall", gsh.role), "airside",
                           abs(got - gz), None, None, round(_d, 3),
                           (x, y), (gx0, gy0), sh.key, gsh.key,
                           lat=lat, lon=lon,
                           out_of_scope=(f"{sh.ref}: the crest {got:.2f} stands "
                                         f"{got - gz:+.2f} m off the governed "
                                         f"{gsh.role} it edges ({gz:.2f})")))
    return out
