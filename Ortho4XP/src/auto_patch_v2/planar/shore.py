"""§37 (11) THE SHORE DECISION (owner RULINGS 2026-09-29a, issue #72;
amends 2026-09-27a (7) and 2026-09-15f item 2).

WHERE IT IS TAKEN.  Wherever water lies inside a pavement's adjacent-ground
zone 1 or zone 2 (``law/zones.toml``: the lip, and the runway band by code /
FAA letter or the taxi band by letter): ``planar/zones`` trims the zone at
the coastline and every zone part that REACHES the water has a CONTACT — the
stretch of its boundary standing on the water line.  That contact is what
is decided, here, once (:func:`shore_verdict`).

HOW, by precedence — the first witness that speaks decides:

1. DECLARED — an OSM ``man_made=quay/pier/breakwater/seawall/groyne/dyke/
   embankment``, ``barrier=wall/retaining_wall/seawall``, ``wall=seawall/
   retaining_wall`` or ``landuse=reclaimed`` way on the contact → WALL.
2. PACK WALL — a wall-class pack object (``classify/retaining_wall``'s one
   classifier: thin, >= 2 m tall, >= 10 m long) along the shore within one
   identity spacing of the contact → WALL, at the object's height.
3. PAVEMENT — the contact lies within the lip of the pavement: the pavement
   edge IS the coastline and there is no land to slope on → WALL.
4. TERRAIN PROFILE — the DEM across the last ``shore_profile_run_m`` (10 m)
   before the water line, read at stations along the contact.  A drop of at
   least ``shore_profile_drop_m`` (2 m) taken STEEPER than the bank slope
   (1:3) within that run is a BUILT edge → WALL at that height; a profile at
   or gentler than 1:3 → NATURAL (the band ends in a 1:3 slope to the water
   line).  A station that is neither (steep, but under 2 m) is no witness.
5. DEFAULT — NATURAL, reported as a ``shore_undeclared`` row.

THE READING OF (4).  The ruling's two thresholds overlap as literal
numbers: 2 m over 10 m is 1:5, gentler than 1:3.  They are read together
as "a 2 m drop taken at a slope no bank would stand at" — a built edge is a
STEP, not a long gentle fall (the lane brief's own twin: a 2 m step within
10 m is a wall, a 1:4 fall is natural).  The profile starts AT THE
WATER'S LEVEL on the water line (the sea, 0 m — the band "ends in a 1:3
slope to the water line") and reads the DEM at 1 m steps inland; the drop
counted is the sum of its rises steeper than the bank slope, and the height
reported is the whole rise across the run.  A contact reads WALL
when at least half its stations are built, NATURAL when at least half are
gentle, and otherwise falls through to the default.

ONE derivation: ``planar/zones.zone_regions`` asks this module for every
reaching part and carries the verdict on the ``ZoneRegion``; nothing
downstream re-decides the shore.  The kinds are the two the solve already
reads (``quay`` → ``PlanarMap.quay_refs``, ``natural`` →
``natural_shore_refs``); the witness and height ride along for the report.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon

from ..law import Law
from ..law.tables import snap_margin_m

__all__ = ["SHORE_WALL_TAGS", "SHORE_WITNESSES", "ShoreVerdict", "PackWall",
           "shore_declarations", "pack_shore_walls", "shore_contact",
           "shore_profile", "shore_verdict", "BUILT_SHORE_SPILL"]

_MITRE = dict(join_style="mitre", mitre_limit=2.0)

#: §37 (11) (7) / 29a (1): the OSM tags that DECLARE a built shore.  Only
#: there, or where a later witness finds one, does the quay wall stand.
SHORE_WALL_TAGS: dict[str, frozenset] = {
    "man_made": frozenset({"quay", "pier", "breakwater", "seawall", "groyne",
                           "dyke", "embankment"}),
    "barrier": frozenset({"wall", "retaining_wall", "seawall"}),
    "wall": frozenset({"seawall", "retaining_wall"}),
    "landuse": frozenset({"reclaimed"}),
}

#: The witnesses, in precedence order (29a (1)–(5)).
SHORE_WITNESSES = ("declared", "pack_wall", "pavement", "profile", "default")

#: §37 (11) (7): the share of a zone part's coastline contact that may lie
#: beyond the lip while the part still reads "the pavement edge IS the
#: coastline" (the lip ring's mitred corners).  An ASSUMPTION, not a law.
BUILT_SHORE_SPILL = 0.1

#: The profile's station spacing along the contact, and the cap on the
#: stations one contact is read at (a long contact is read coarser, never
#: at unbounded cost).  Sampling choices, not law.
PROFILE_STATION_M = 5.0
PROFILE_MAX_STATIONS = 400
#: The level the water line stands at: the shore region is the SEA alone
#: (``planar/zones.shore_region``), and the sea's level is the mesh's
#: ``O4_Vector_Map.SEAWALL_SEA_LEVEL_M``.
SEA_LEVEL_M = 0.0
#: The profile's sample step across the run (metres).
PROFILE_STEP_M = 1.0
#: The gradient tolerance the 1:3 test is read with: the law spells the
#: bank slope ``0.33`` (``emit.design.bank_slope``), and a profile at
#: exactly 1:3 (0.333…) is "at 1:3", which the ruling makes natural.
PROFILE_SLOPE_TOL = 0.01


@_dc.dataclass(frozen=True)
class ShoreVerdict:
    """The decision for one contact (module docstring)."""

    kind: str                   # "quay" | "natural"
    witness: str                # one of :data:`SHORE_WITNESSES`
    height_m: float | None      # the wall's height where a witness states one
    contact_m: float            # the contact's length
    at: tuple[float, float] | None = None   # frame xy on the contact
    stations: int = 0           # profile stations with DEM data
    built: int = 0              # of which read a built edge
    gentle: int = 0             # of which read at or gentler than 1:3

    @property
    def undeclared(self) -> bool:
        """29a (5): the ``shore_undeclared`` row — no witness spoke."""
        return self.witness == "default"


@_dc.dataclass(frozen=True)
class PackWall:
    """One footprint piece of a wall-class pack component (frame xy)."""

    poly: Polygon
    height_m: float
    resource: str


def shore_declarations(osm_ways=()) -> tuple:
    """29a (1): the frame geometry of every loaded OSM way that DECLARES a
    built shore (:data:`SHORE_WALL_TAGS`) — a line, or a polygon for a
    closed ``landuse=reclaimed`` area (the contact lies INSIDE the
    reclaimed land, not only along its ring)."""
    out: list = []
    for w in osm_ways or ():
        tags = getattr(w, "tags", None) or {}
        if not any(tags.get(k) in vals for k, vals in SHORE_WALL_TAGS.items()):
            continue
        pts = [(float(p[0]), float(p[1])) for p in getattr(w, "points", ())]
        if len(pts) < 2:
            continue
        if tags.get("landuse") == "reclaimed" and len(pts) >= 4 and \
                pts[0] == pts[-1]:
            g = Polygon(pts)
            if not g.is_valid:
                g = g.buffer(0.0)
            if not g.is_empty:
                out.append(g)
                continue
        out.append(LineString(pts))
    return tuple(out)


def pack_shore_walls(airport, cfg=None) -> tuple[PackWall, ...]:
    """29a (2): every piece of every WALL-CLASS pack component — the one
    classifier ``classify/retaining_wall.wall_class_components`` (the §47
    addendum's retaining wall), read here against the shore instead of a
    road edge.  ``cfg`` is ``classify/rules.toml``'s ``[service]``."""
    if getattr(airport, "partition", None) is None:
        return ()
    from ..classify.retaining_wall import wall_class_components
    if cfg is None:
        from ..classify.rules import load_rules
        cfg = load_rules().service
    return tuple(PackWall(g, c.height_m, c.resource)
                 for c in wall_class_components(airport, cfg) for g in c.pieces)


def shore_contact(part, water, law: Law):
    """The stretch of a zone part's boundary standing on the water line."""
    if water is None or part is None or part.is_empty:
        return None
    c = part.boundary.intersection(water.buffer(snap_margin_m(law)))
    return None if c.is_empty or c.length <= 0.0 else c


def _dem_many(dem, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    many = getattr(dem, "z_many", None)
    if many is not None:
        return np.asarray(many(xs, ys), dtype=float)
    return np.asarray([dem.z(float(x), float(y)) for x, y in zip(xs, ys)],
                      dtype=float)


def _stations(contact) -> list[tuple[float, float, float, float]]:
    """``(x, y, tx, ty)`` stations along ``contact`` (unit tangent)."""
    parts = [g for g in shapely.get_parts(contact)
             if g.geom_type == "LineString" and g.length > 0.0]
    total = sum(g.length for g in parts)
    if total <= 0.0:
        return []
    step = max(PROFILE_STATION_M, total / PROFILE_MAX_STATIONS)
    out = []
    for g in parts:
        n = max(1, int(g.length // step))
        for i in range(n):
            s = (i + 0.5) * g.length / n
            a = g.interpolate(max(0.0, s - 0.5))
            b = g.interpolate(min(g.length, s + 0.5))
            tx, ty = b.x - a.x, b.y - a.y
            L = math.hypot(tx, ty)
            if L <= 0.0:
                continue
            p = g.interpolate(s)
            out.append((p.x, p.y, tx / L, ty / L))
    return out


def shore_profile(contact, water, dem, law: Law):
    """29a (4): read the terrain across the last run before the water line
    at stations along ``contact``.  Returns ``(stations, built, gentle,
    heights)`` — ``heights`` the whole rise across the run at each BUILT
    station."""
    if dem is None or contact is None or water is None:
        return 0, 0, 0, []
    ag = law.tables.zones.adjacent_ground
    drop_m = float(ag.shore_profile_drop_m)
    run_m = float(ag.shore_profile_run_m)
    bank = float(law.tables.emit.design.bank_slope) + PROFILE_SLOPE_TOL
    st = _stations(contact)
    if not st:
        return 0, 0, 0, []
    arr = np.asarray(st, dtype=float)
    px, py, tx, ty = arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3]
    nx, ny = -ty, tx
    # INLAND is the side of the tangent farther from the water
    probe = 1.0
    da = shapely.distance(water, shapely.points(px + nx * probe, py + ny * probe))
    db = shapely.distance(water, shapely.points(px - nx * probe, py - ny * probe))
    sgn = np.where(np.asarray(da) >= np.asarray(db), 1.0, -1.0)
    nx, ny = nx * sgn, ny * sgn
    k = max(1, int(round(run_m / PROFILE_STEP_M)))
    d = np.linspace(0.0, run_m, k + 1)
    xs = (px[:, None] + nx[:, None] * d[None, :]).ravel()
    ys = (py[:, None] + ny[:, None] * d[None, :]).ravel()
    try:
        z = _dem_many(dem, xs, ys).reshape(len(st), k + 1)
    except Exception:                                   # pragma: no cover
        return 0, 0, 0, []
    ok = np.all(np.isfinite(z[:, 1:]), axis=1)
    z = z[ok]
    # THE WATER LINE STANDS AT THE WATER'S LEVEL: the drop is the land's
    # fall TO THE WATER (the natural band "ends in a 1:3 slope to the water
    # line", the water datum pins the line there).  The shore region is the
    # SEA alone (``planar/zones.shore_region``), whose level is 0.
    z[:, 0] = SEA_LEVEL_M
    if not len(z):
        return 0, 0, 0, []
    step = run_m / k
    rise = np.diff(z, axis=1)                  # inland rise per step
    grad = rise / step
    steep = np.where(grad > bank, rise, 0.0).sum(axis=1)
    built = steep >= drop_m - 1e-9
    gentle = np.abs(grad).max(axis=1) <= bank
    heights = (z.max(axis=1) - z[:, 0])[built]
    return int(len(z)), int(built.sum()), int((gentle & ~built).sum()), \
        [float(h) for h in heights]


def shore_verdict(contact, *, pavement, water, law: Law, declared=(),
                  pack_walls: _t.Sequence[PackWall] = (), dem=None
                  ) -> ShoreVerdict:
    """THE SHORE DECISION for one contact (module docstring, 29a (1)–(5)).

    ``contact`` the zone part's boundary on the water line
    (:func:`shore_contact`); ``pavement`` the pavement union the zone
    serves; ``water`` the shore region (``planar/zones.shore_region``);
    ``declared`` :func:`shore_declarations`; ``pack_walls``
    :func:`pack_shore_walls`; ``dem`` the airport's DEM sampler."""
    L = float(contact.length) if contact is not None else 0.0
    at = None
    if contact is not None and L > 0.0:
        p = contact.interpolate(0.5, normalized=True) \
            if contact.geom_type == "LineString" else \
            shapely.get_parts(contact)[0].interpolate(0.5, normalized=True)
        at = (float(p.x), float(p.y))
    if contact is None or L <= 0.0:
        return ShoreVerdict("natural", "default", None, 0.0, at)
    ag = law.tables.zones.adjacent_ground
    lip = float(ag.lip_width_m)
    tol = snap_margin_m(law)
    # (1) DECLARED
    for g in declared or ():
        if g.distance(contact) <= lip:
            return ShoreVerdict("quay", "declared", None, L, at)
    # (2) A PACK WALL along the shore, within one identity spacing
    spacing = float(law.tables.emit.identity.min_distinct_spacing_m)
    walls = [w for w in pack_walls or () if w.poly.distance(contact) <= spacing]
    if walls:
        return ShoreVerdict("quay", "pack_wall",
                            max(w.height_m for w in walls), L, at)
    # (3) THE PAVEMENT EDGE ON THE COASTLINE, within the lip
    if pavement is not None and not pavement.is_empty:
        far = contact.difference(pavement.buffer(lip + tol, **_MITRE)).length
        if far <= BUILT_SHORE_SPILL * L:
            return ShoreVerdict("quay", "pavement", None, L, at)
    # (4) THE TERRAIN PROFILE
    n, built, gentle, heights = shore_profile(contact, water, dem, law)
    if n:
        if built * 2 >= n:
            return ShoreVerdict("quay", "profile", float(np.median(heights)),
                                L, at, n, built, gentle)
        if gentle * 2 >= n:
            return ShoreVerdict("natural", "profile", None, L, at, n, built,
                                gentle)
    # (5) DEFAULT — natural, and a ``shore_undeclared`` row
    return ShoreVerdict("natural", "default", None, L, at, n, built, gentle)
