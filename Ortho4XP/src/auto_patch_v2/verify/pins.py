"""The three families v2 ``verify`` reads WITHOUT geometry: two PINS the
solve published and one PATCH-INTRINSIC floor (issue #186).

``seam_residual`` (§38 (5)) and ``road_coverage_join`` (§37 (9)) are the
same reading twice over: the solve publishes a value per vertex it PINNED
— the vertex's own tile DEM sample at a seam, the core ribbon's altitude
at a coverage exit — and the family prices the EMITTED elevation against
it.  A pin holds exactly, so a row means the surface left the value the
solve held, and that is the only way either family can speak.  The join
is the canonical lat/lon identity (:data:`JOIN_DP`), never a proximity
match: the same rule ``check_grade._check_seam_residual`` /
``_check_road_coverage_join`` join on.

``sentinel_elevation`` reads no witness at all — it is the SHIP-SIDE net
under the whole patch (RULINGS 2026-09-13m, lane ``v2zerocrater``: KCLT
shipped 20 apron vertices at exactly z = 0.00 over 217 m ground because
that piece of the design sheet reached the least-squares solve carrying
only homogeneous rows, whose minimiser is 0).  Patch-intrinsic on
purpose, priced against a ROBUST floor and never the minimum — the crater
IS the minimum.

WHY VERIFY OWES THESE THREE A READER AT ALL (issue #186): all three read
the DESIGN surface the solve produced, which is exactly what ``verify``
is handed (``pipeline/build.census_frame(surf, …)``), and all three
witnesses are on the ``Patch``: the two pin lists are sidecar keys
``Patch.publication`` carries (the ``eat_ceiling`` precedent), and the
sentinel floor is the patch's own elevations.  The parity holes they left
were #108's class, not a structural blindness.

ONE ACCESSOR PER READING (issue #191, the census-wrapper precedent): the
two pin families share :func:`_by_ll` and :func:`_pin_rows`; a third pin
family extends ``_pin_rows``, it does not fork it.
"""
from __future__ import annotations

import typing as _t

from .frame import Patch, Row, Shape, row

__all__ = ["FAMILY_SEAM_RESIDUAL", "FAMILY_ROAD_COVERAGE_JOIN",
           "FAMILY_SENTINEL", "JOIN_DP", "SENTINEL_FLOOR_PCTL",
           "SENTINEL_MIN_NODES", "ROAD_JOIN_TOL_M", "seam_residual",
           "road_coverage_join", "sentinel_elevation", "sentinel_floor_m"]

FAMILY_SEAM_RESIDUAL = "seam_residual"
FAMILY_ROAD_COVERAGE_JOIN = "road_coverage_join"
FAMILY_SENTINEL = "sentinel_elevation"

#: The canonical identity the pin lists join on — ``check_grade``'s own
#: ``round(lat, 7)`` (memory ``canonical-identity-join``).  A pin the patch
#: does not carry is silently absent: a tile PIECE carries only its own
#: side's vertices.  The twin asserts the two readers join at one dp.
JOIN_DP = 7

#: §37 (9) reads the coverage join at ``check_grade._ROAD_JOIN_TOL_M``.
#: The join is a PIN and a pin holds exactly, so anything above this is
#: surface.  No law key states it; the twin asserts the two readers agree.
ROAD_JOIN_TOL_M = 0.05

#: The robust floor the sentinel drop is measured from: the patch's
#: 5th-percentile emitted elevation, never its MINIMUM
#: (``check_grade.SENTINEL_FLOOR_PCTL``).
SENTINEL_FLOOR_PCTL = 5.0

#: Below this many valued nodes a percentile is not a ground band at all
#: (a fixture, a one-ring probe patch): the family reports nothing
#: (``check_grade.SENTINEL_MIN_NODES``).
SENTINEL_MIN_NODES = 20


def _seam_tol_m(p: Patch) -> float:
    """§38 (5) reads the seam at the SAME elevation quantum the emitted
    surface carries (``emit.materiality.elevation_m``), so a row is surface
    and never rounding.  Read from the law, never a literal here."""
    return float(p.law.tables.emit.materiality.elevation_m)


def _by_ll(p: Patch) -> dict[tuple[float, float], tuple[float, Shape]]:
    """THE IDENTITY INDEX both pin families join through: the emitted
    elevation and the shape carrying it, per canonical coordinate.

    Walks the ROLE-CARRYING rings only (``p.shapes``), which is the ``ways``
    population ``check_grade`` walks; the first shape to claim a coordinate
    keeps it, as ``setdefault`` does there."""
    out: dict[tuple[float, float], tuple[float, Shape]] = {}
    for sh in p.shapes:
        for vid in sh.ids:
            ll = p.ll.get(vid)
            if ll is None or vid not in p.z:
                continue
            out.setdefault((round(float(ll[0]), JOIN_DP),
                            round(float(ll[1]), JOIN_DP)),
                           (float(p.z[vid]), sh))
    return out


def _pin_rows(p: Patch, key: str, family: str, tol_m: float) -> list[Row]:
    """One row per published pin whose EMITTED elevation stands off the
    value the solve pinned by more than ``tol_m``.

    A record is ``[lat, lon, value]``; a 2-element record publishes no
    value to price against and reports nothing (a pre-§38 sidecar)."""
    pins = p.publication.get(key) or ()
    if not pins:
        return []
    by_ll = _by_ll(p)
    if not by_ll:
        return []
    out: list[Row] = []
    for rec in pins:
        if not isinstance(rec, _t.Sequence) or len(rec) < 3 or rec[2] is None:
            continue
        try:
            lat, lon, held = float(rec[0]), float(rec[1]), float(rec[2])
        except (TypeError, ValueError):
            continue
        got = by_ll.get((round(lat, JOIN_DP), round(lon, JOIN_DP)))
        if got is None:
            continue
        z, sh = got
        if abs(z - held) <= tol_m:
            continue
        xy = p.to_m(lat, lon)
        out.append(row(family, (sh.role,), p.side(sh.role), abs(z - held),
                       None, None, None, xy, xy, sh.ref, sh.ref,
                       lat=lat, lon=lon))
    out.sort(key=lambda r: -float(r["magnitude_m"]))
    return out


def seam_residual(p: Patch) -> list[Row]:
    """§38 (5) SEAM RESIDUAL: a seam band-edge vertex OFF its own DEM.

    The seam is an ANCHOR "like CIFP thresholds that everything else grades
    to" (owner RULINGS 2026-09-13ah / 13am / 13an), held as a ``Pin``, and
    the sidecar publishes ``seam_pins`` = ``[lat, lon, the vertex's own
    tile's DEM sample]``.  Before §38 the census had no patch-edge-vs-DEM
    family and could not see SPLP's berm: 123 of 150 seam vertices off
    their DEM, worst 3.430 m, a 3 m ridge 10 m wide along the seam through
    the runway strip, with ``strip_seam_tear`` reading 0."""
    return _pin_rows(p, "seam_pins", FAMILY_SEAM_RESIDUAL, _seam_tol_m(p))


def road_coverage_join(p: Patch) -> list[Row]:
    """§37 (9) THE COVERAGE-EDGE JOIN (owner RULINGS 2026-09-13be): a road
    vertex where the patch's road meets the CORE's levelled ribbon stands
    off the ribbon's own altitude there.

    The core's ``include_roads`` levelling is REMOVED inside the patch
    coverage + 6 m, so the patch owns the road inside and the core owns it
    outside, and nothing made them agree: at KCLT way 10826 station 0 the
    patch's kerb stood 2.36 m over the ribbon across 7.9 m of road — a step
    the driver takes at the airport gate, which no other family can see
    (the patch is lawful on its own side of the edge and the core ribbon is
    not in the patch at all).  The value is LAW INPUT, published per pinned
    vertex as ``road_coverage_join`` = ``[lat, lon, the ribbon altitude]``."""
    return _pin_rows(p, "road_coverage_join", FAMILY_ROAD_COVERAGE_JOIN,
                     ROAD_JOIN_TOL_M)


def sentinel_floor_m(p: Patch) -> tuple[float, float] | None:
    """``(the 5th-percentile elevation, the floor below it)``, or ``None``
    when the patch carries fewer than :data:`SENTINEL_MIN_NODES` valued
    nodes — a fixture, not a ground band.

    One vertex, one value: the elevations are taken per VERTEX ID (the
    identity the patch is written at), so a vertex on three rings weighs
    once, exactly as ``check_grade``'s ``by_nid`` does."""
    zs = sorted(float(p.z[vid]) for vid in
                {vid for sh in p.shapes for vid in sh.ids} if vid in p.z)
    if len(zs) < SENTINEL_MIN_NODES:
        return None
    idx = max(0, min(len(zs) - 1,
                     int(round((SENTINEL_FLOOR_PCTL / 100.0) * (len(zs) - 1)))))
    pctl = zs[idx]
    return pctl, pctl - float(p.law.tables.emit.cockpit.sentinel_drop_m)


def sentinel_elevation(p: Patch) -> list[Row]:
    """SENTINEL ELEVATION: an emitted vertex more than
    ``emit.cockpit.sentinel_drop_m`` below the patch's own 5th-percentile
    elevation (RULINGS 2026-09-13m, lane ``v2zerocrater``).

    A no-data value or a homogeneous least-squares block's 0.0 is not
    geometry.  The engine now refuses to emit such a piece (``solve/design``
    §9c, the level belt); this is the net under the SHIP, so the class can
    never leave the patch silently again whatever mints it.  CRITICAL at
    any airport it touches.  One row per offending vertex, the magnitude
    how far under the percentile it sits."""
    got = sentinel_floor_m(p)
    if got is None:
        return []
    pctl, floor = got
    best: dict[int, Shape] = {}
    for sh in p.shapes:
        for vid in sh.ids:
            if vid in p.z and float(p.z[vid]) < floor:
                best.setdefault(vid, sh)
    out: list[Row] = []
    for vid, sh in best.items():
        la, lo = p.ll.get(vid, (None, None))
        xy = p.xy.get(vid)
        out.append(row(FAMILY_SENTINEL, (sh.role,), p.side(sh.role),
                       pctl - float(p.z[vid]), None, None, None, xy, xy,
                       sh.ref, sh.ref, lat=la, lon=lo))
    out.sort(key=lambda r: -float(r["magnitude_m"]))
    return out
