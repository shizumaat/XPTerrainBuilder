"""THE WALL-CLASS CLASSIFIER — which pack components are WALL-CLASS.

A pack component is WALL-CLASS when it is thin, tall and long enough
(``[service] retaining_wall_max_width_m`` / ``_min_height_m`` /
``_min_length_m``, read from the ``cfg`` the CALLER supplies), and its
resource does not name a fence (RULINGS 2026-09-29h, Q-72b).  A THICK
component is wall-class too where it retains its own height — slender for
its height, standing on the ground, and the ground stepping across it by
that height (#715, #1197, :func:`_retains_its_height`).

THE ONE implementation, read by three layers: ``classify/retaining_wall``
(§47's wall along a road edge), ``planar/shore`` (RULINGS 2026-09-29a (2):
a wall along the shore) and ``airport/road_ramp`` (RULINGS 2026-10-03c,
#291: the wall between the airside level and a lower lot).

WHY IT LIVES HERE (issue #303).  It was ``classify/retaining_wall``'s,
but ``airport`` may not read ``classify``
(``tests/auto_patch_v2/test_model.py::test_dependency_direction``), and
``airport/road_ramp`` is its third reader.  Nothing about it is a
``classify`` concept: it reads the AIRPORT's own pack partition and a
config record handed to it, so its whole dependency set is ``model`` —
at or below ``airport`` already.  ``classify/retaining_wall`` re-exports
it, so every caller's import path is unchanged.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t
import unicodedata as _ud

from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..model.airport import Airport
from .wall_sheets import airside_union, hung_wall, low_side_y, obj_top_y, paved_faces, sheets_of

__all__ = ["WallComponent", "NOT_WALL_RESOURCE_WORDS", "wall_class_components",
           "retaining_sides"]


@_dc.dataclass(frozen=True)
class WallComponent:
    """One WALL-CLASS pack component (module docstring: thin, tall, long):
    its footprint pieces (frame xy), its solid height and its source.
    ``retains`` — the component RETAINS ITS OWN HEIGHT
    (:func:`_retains_its_height`): owner RULINGS 2026-10-15a (2) — "the
    wall is the step", a declared terrace for the roads and lots below it
    (``airport/road_ramp``)."""

    pieces: tuple
    height_m: float
    resource: str
    comp: int
    retains: bool = False
    #: the height it RETAINS (#1158): its solid height, or its depth under
    #: its own zero where it stands proud (:func:`_depth_under_zero`), or its
    #: top over the ground on its low side where its footing is authored
    #: below that ground (RULINGS 2026-11-09a (14)); 0.0 where it retains none
    retained_m: float = 0.0
    #: the part's extent ABOVE its object's zero (``base_y + height``,
    #: #1633: the wall's top as seated), ``None`` where the reading has none
    top_y: float | None = None
    #: the ABSOLUTE elevation of the object's zero as it sits — its DEM at
    #: the placement origin plus the authored ``agl`` (``obj8.PlacedObject``'s
    #: rendered reading), ``None`` without a DEM there or for a member
    #: standing on a converted MSL zero (#1661: ``airport/wall_top``)
    seat_z: float | None = None
    #: the placement: its ``(lat, lon)`` origin and the member it places
    #: (``airport/wall_top`` reads the member's triangles), ``None`` unread
    origin: tuple | None = _dc.field(default=None, compare=False)
    member: _t.Any = _dc.field(default=None, compare=False, repr=False)
    #: the authored ``y`` the RETAINED face reaches up to (#1139: its zero,
    #: the parapet above retaining nothing); ``None`` where the face it
    #: retains runs to its top (:func:`_retains_its_height`)
    retained_top_y: float | None = None
    #: what witnessed the ground on its low side (#1952): ``"dem"`` — the
    #: step across it in the DEM (:func:`_retains_its_height`), ``"sheets"``
    #: — the pack's own co-linear sheets (``airport/wall_sheets``, read only
    #: where the DEM shows no step), ``""`` where it retains nothing
    low_side_source: str = ""
    #: a ``"sheets"`` wall's COMPOSITE: every sheet's footprint (frame xy),
    #: its own pieces' among them (``airport/wall_shade``: no pad from any)
    sheets: tuple = _dc.field(default=(), compare=False, repr=False)
    #: a ``"sheets"`` wall's side witness: per piece, the index of its long
    #: face (``wall_sides._wall_faces``) with airside pavement beside it —
    #: the UPPER face — or ``None`` (``wall_sheets.paved_faces``)
    paved_face: tuple = ()


#: RULINGS 2026-09-29h (Q-72b): a FENCE is not a wall.  A footprint cannot
#: tell a fence from a retaining or sea wall (TFFJ ``beach_fence.obj``:
#: 92 m, 2.38 m, thin), so the pack's own resource name decides: a
#: component whose resource basename names one of these is never wall-class.
#: Read in the languages the installed packs are named in (#1197: LEMD's
#: ``…LEMDzaun.obj`` is a 739 m fence, *Zaun*): German, French, Italian,
#: Vietnamese (*hàng rào*), Swedish and Spanish fence and railing words.  A
#: word that is also a common name part stays out (``valla``: Vallarta,
#: Valladolid; ``cerca``: "near").  The words are plain ASCII: a name is
#: compared with its accents folded (``Clôture`` -> ``cloture``).
NOT_WALL_RESOURCE_WORDS = ("fence", "railing", "guardrail", "zaun", "cloture",
                           "recinzione", "hangrao", "staket", "baranda",
                           "gelander", "gelaender", "ringhiera")


def _not_a_wall(resource: str) -> bool:
    base = str(resource or "").replace("\\", "/").rsplit("/", 1)[-1].lower()
    base = "".join(ch for ch in _ud.normalize("NFKD", base)
                   if not _ud.combining(ch))
    return any(w in base for w in NOT_WALL_RESOURCE_WORDS)


def wall_class_components(airport: Airport, cfg) -> list[WallComponent]:
    """THE WALL-CLASS CLASSIFIER, the one implementation: every pack
    component that is thin, at least ``retaining_wall_min_height_m`` tall
    and at least ``retaining_wall_min_length_m`` long.  Read by
    :func:`retaining_pieces` (a wall along a road edge) and by
    ``planar/shore`` (a wall along the shore — owner RULINGS 2026-09-29a
    (2)).  Retaining / sea-wall classes only: a fence resource is never
    wall-class (RULINGS 2026-09-29h, Q-72b)."""
    part = getattr(airport, "partition", None)
    if part is None:
        return []
    to_xy = airport.frame.entry()
    out: list[WallComponent] = []
    paved: list = []            # the apt.dat airside union, read once on demand
    for u in part.units:
        got: list[WallComponent] = []
        for m in u.members:
            # 29h (Q-72b): a fence is no wall -- unless its GEOMETRY is a
            # retaining wall's (#2054: KLAX ``Fence_Terminal_1.obj``)
            fence = _not_a_wall(m.resource)
            if fence and not _buried_solid(m, cfg):
                continue
            seat = None
            for p in m.parts:
                if not p.rings or getattr(p, "line", False) or \
                        p.height_m < float(cfg.retaining_wall_min_height_m):
                    continue
                polys = []
                for rg in p.rings:
                    if len(rg) < 3:
                        continue
                    g = Polygon([to_xy(lon, lat) for lat, lon in rg])
                    if not g.is_valid:
                        g = g.buffer(0.0)
                    if not g.is_empty and g.geom_type == "Polygon":
                        polys.append(g)
                if not polys:
                    continue
                whole = unary_union(polys)
                if whole.length <= 0.0:
                    continue
                # the COMPONENT is judged thin and long; its PIECES are
                # judged against the road (or the shore) one by one
                wide = 2.0 * whole.area / whole.length
                if sum(g.length for g in polys) / 2.0 < \
                        float(cfg.retaining_wall_min_length_m):
                    continue
                by = getattr(p, "base_y", None)
                top_y = None if by is None else float(by) + float(p.height_m)
                if seat is None:
                    seat = _seat_z(airport, u, m, to_xy)
                # #1139 / RULINGS 2026-11-09a (14): an object that IS one wall
                # (its only part) may retain only what stands under its zero,
                # or only what stands over the ground on its low side
                one = len(m.parts) == 1
                depth = _depth_under_zero(p) if one else None
                retained = _retains_its_height(
                    airport, whole, wide, float(p.height_m), cfg, depth,
                    seat + top_y if one and _hangs_from_zero(top_y, seat, cfg) else None,
                ) if _stands_on_ground(p) else 0.0
                buried = False
                if not retained and one and depth is not None and \
                        _stands_on_ground(p) and _buried_solid(m, cfg):
                    retained = _buried_step(airport, whole, wide, float(p.height_m),
                                            depth, cfg)
                    buried = retained > 0.0
                if fence and not retained:
                    continue                # a fence retaining nothing is no wall
                retains = retained > 0.0
                # the face a depth retains reaches its zero, not its top; so
                # does a buried wall's (#2054: its zero is the upper ground)
                kept_top = 0.0 if retains and depth is not None and (buried or (
                    retained == depth and retained != float(p.height_m))) else None
                source, sheet = ("dem" if retains else ""), None
                if not retains and hung_wall(p, one, top_y, seat, cfg):
                    sheet = _sheet_wall(airport, u, m, p, tuple(polys), cfg, to_xy, paved)
                if sheet is not None:
                    retained, top_y, sheet = sheet[0], sheet[1], sheet[2:]
                    retains, source = True, "sheets"
                if wide > float(cfg.retaining_wall_max_width_m) and not retains:
                    continue
                got.append(WallComponent(tuple(polys), float(p.height_m),
                                         m.resource, int(p.comp), retains,
                                         float(retained), top_y, seat,
                                         _origin(u, m), m, kept_top, source,
                                         *(sheet or ())))
        out.extend(_one_wall_per_composite(got, u, to_xy, cfg))
    return out


_BURIED: dict[str, bool] = {}


def _buried_solid(member, cfg) -> bool:
    """#2054 (owner 2026-11-13 15:33Z / 15:36Z): whether ``member``'s OBJ
    reads a RETAINING WALL by its geometry and texture
    (``airport/line_solidity.kind_of``: authored at least
    ``line_retaining_buried_min_m`` under its zero, solid over it),
    whatever its name; memoised per file."""
    path = str(getattr(member, "authored_path", "") or "")
    if not path or getattr(cfg, "line_retaining_buried_min_m", None) is None:
        return False
    if path not in _BURIED:
        from .line_solidity import RETAINING_WALL, kind_of, obj_solidity
        sol = obj_solidity(path)
        _BURIED[path] = sol is not None and kind_of(sol, cfg) == RETAINING_WALL
    return _BURIED[path]


def _buried_step(airport: Airport, whole, wide: float, height: float,
                 depth: float, cfg) -> float:
    """THE BURIED WITNESS (#2054; owner 2026-11-13 15:33Z: "the wall marks
    where the drop is, and should be seated so its bottom is at the lowest
    point"): a thin one-part wall the author drew below its zero
    (:func:`_buried_solid`) retains the STEP the ground takes across it
    (:func:`_step_across`, the witness's own reading) when that is at least
    ``retaining_wall_min_height_m`` and within its buried face
    (``retaining_wall_step_max_fraction`` of ``depth``) -- the low side's
    ground stands on its buried face, not at its foot.  MEASURED KLAX
    ``Fence_Terminal_1.obj`` (8.00 m solid, 4.20 m under its zero): the
    ground steps 2.84 m across it (90th percentile at the 8 m ring), under
    the 0.75 x 4.20 m the depth witness needs.  0.0 where it retains none."""
    ring_m = getattr(cfg, "retaining_wall_step_ring_m", None)
    hi = getattr(cfg, "retaining_wall_step_max_fraction", None)
    dem = getattr(airport, "dem", None)
    if ring_m is None or hi is None or dem is None or wide > float(cfg.retaining_wall_max_width_m):
        return 0.0
    step = _step_across(dem, whole, wide, max(float(ring_m), height))
    if step is None or not float(cfg.retaining_wall_min_height_m) <= step <= float(hi) * depth:
        return 0.0
    return float(step)


def _sheet_wall(airport: Airport, unit, member, part, pieces: tuple, cfg, to_xy,
                paved: list) -> tuple | None:
    """THE THIRD WITNESS (#1952, owner RULINGS 2026-11-09a (14)): a gate-G
    wall (``airport/wall_sheets``) whose side witness S holds and whose
    sheets name the ground on its low side retains its OBJ top less that
    ground, when that is at least ``retaining_wall_min_height_m`` and under
    its solid height — ``(retained, top_y, sheet footprints, paved
    faces)``; ``None`` otherwise (it retains nothing, as before)."""
    if not paved:
        paved.append(airside_union(airport))
    faces = paved_faces(pieces, paved[0], cfg)
    if faces is None:
        return None
    sheets = sheets_of(unit, (member.id, int(part.comp)), to_xy, cfg)
    low = low_side_y(sheets)
    top = None if low is None else obj_top_y(member, _origin(unit, member), to_xy)
    if top is None:
        return None
    kept = top - low
    if not float(cfg.retaining_wall_min_height_m) <= kept < float(part.height_m):
        return None
    return kept, top, tuple(s.poly for s in sheets), faces


def _one_wall_per_composite(comps: list[WallComponent], unit, to_xy, cfg
                            ) -> list[WallComponent]:
    """R1 (#1952): the sheets of a composite are ONE wall, carried by the
    gate-G wall with the largest footprint among them; every other
    component of ``unit`` whose part is one of its sheets is absorbed."""
    walls = sorted((c for c in comps if c.low_side_source == "sheets"),
                   key=lambda c: -sum(g.area for g in c.pieces))
    taken: set = set()
    for c in walls:
        if (c.member.id, c.comp) in taken:
            continue
        taken.update(s.key for s in sheets_of(unit, (c.member.id, c.comp), to_xy, cfg)
                     if s.key != (c.member.id, c.comp))
    return [c for c in comps if (getattr(c.member, "id", None), c.comp) not in taken]


def _seat_z(airport: Airport, unit, member, to_xy) -> float | None:
    """The absolute elevation of ``member``'s zero as it sits
    (:attr:`WallComponent.seat_z`): the DEM at its origin plus the unit's
    authored ``agl``; ``None`` for a member on a converted MSL zero."""
    dem = getattr(airport, "dem", None)
    org = _origin(unit, member)
    if dem is None or org is None or float(getattr(member, "zero_y", 0.0) or 0.0) != 0.0:
        return None
    lat, lon = org
    import numpy as np

    from .dem import dem_z_many
    x, y = to_xy(float(lon), float(lat))
    z = float(dem_z_many(dem, np.array([x]), np.array([y]))[0])
    if not math.isfinite(z):
        return None
    return z + float(getattr(unit, "agl_m", 0.0) or 0.0)


def _origin(unit, member) -> tuple | None:
    """The placement's ``(lat, lon)`` origin, ``None`` when unread."""
    org = getattr(member, "origin", None) or getattr(unit, "anchor", None)
    return None if org is None else tuple(org)


#: the share of a wall's outline that must step by its height: the 90th
#: percentile of the across-wall steps (a retaining wall's ends and returns
#: retain nothing; KATL ``muro_concreto5`` steps 7-9 m over its south run)
ACROSS_PERCENTILE = 90.0


def _stands_on_ground(part) -> bool:
    """False for an ELEVATED part — the partition found no ground feet for
    it (``Part.feet`` empty: its base stands more than ``[rebake]
    elevated_base_m`` above its contact structure, RULINGS 2026-09-09s
    (2)).  A wall retains the ground at its foot; a part with no foot (a
    band of glass on an upper storey, a garage's upper parapet) retains
    nothing, whatever the ground does beside it (#1197: KATL ``Vidrios.obj``
    comp 17, glass 12.51 m tall standing 3.00 m up its object, read a 10.97
    m step off the slope beside the terminal).  A part record that carries
    no ``feet`` field at all says nothing, and stands."""
    feet = getattr(part, "feet", None)
    return feet is None or len(feet) > 0


def _depth_under_zero(part) -> float | None:
    """How far a part reaches UNDER its object's zero (``-base_y``), or
    ``None`` for a part standing on it.  A retaining wall's zero is the
    upper ground it holds (KATL ``muro_concreto5``: y −9.70 .. +0.95), so
    this is the face it retains; the rest of its height stands proud — a
    parapet (#1139, KATL ``muro_ladrillo``: 16.64 m solid, 10.52 m under
    its zero, the ground stepping 11.08 m across it)."""
    by = getattr(part, "base_y", None)
    return -float(by) if by is not None and float(by) < 0.0 else None


def _retains_its_height(airport: Airport, whole, wide: float, height: float, cfg,
                        depth: float | None = None, top_abs: float | None = None) -> float:
    """A WALL THAT RETAINS ITS OWN HEIGHT (owner RULINGS 2026-10-15a (2),
    issue #715): slender for its height (``wide <= height x
    retaining_wall_thick_width_per_height``: KATL's 10.65 m concrete
    retaining wall is 3.46 m thick) AND the ground stepping ACROSS it by
    ``retaining_wall_step_min_fraction`` .. ``_max_fraction`` of its height
    (the step equals the wall: #507, RULINGS 2026-10-03c) — read every 2 m
    round a ring outside its footprint, half its height out (at least
    ``retaining_wall_step_ring_m``: a lidar DEM smears a 10 m step over
    3-5 m either side): each ring point against the point as far out on the
    FAR side of the wall (through its nearest wall point, ``wide`` across),
    the :data:`ACROSS_PERCENTILE` of the absolute differences — the wall's
    retaining run, not its ends.  ACROSS, never round the ring: a long wall
    on a slope rises along itself without retaining anything (the ring's
    10th-90th percentile spread admitted 56 thin HECA strips that way).  A
    facade or a building on level ground has no step; a building on a
    slope is not slender.  MEASURED (dry census, registered captures):
    KATL ``muro_concreto5`` 10.65 m and ``muro_concreto`` 12.01 m admitted
    (#715); see ``docs/briefs/katl714-notes.md`` (#715) for the sweep airports.

    THE HEIGHT IT RETAINS (#1139): its solid height, or its ``depth`` under
    its own zero (:func:`_depth_under_zero`) where it stands proud of the
    upper ground — the step matches either.  The depth is read only for a
    placed object that IS one wall (its only part): read for every part it
    admitted 73 HECA, 32 EDDF and 22 KLAX building parts (facades on a
    slope stand under their zero too); read for single-part objects it
    admits KATL ``muro_ladrillo`` alone over the 33 registered captures.
    Slenderness is judged on the solid height, as before.

    THE HEIGHT OVER ITS LOW SIDE (owner RULINGS 2026-11-09a (14), #1952):
    "a retaining wall's height is what it retains above the ground on its
    low side, not its full modelled solid height (which includes the part
    authored below ground)" — ``top_abs`` (its top as it sits, absolute)
    less the ground on its low side (:func:`_kept_above_low_side`), read
    for the same one-wall objects as the depth, and only where part of the
    solid stands under that ground (a footing).

    Returns the height it retains (the solid height, else the depth, else
    the height over its low side — the first the step matches), 0.0 where
    it retains none."""
    per = getattr(cfg, "retaining_wall_thick_width_per_height", None)
    lo = getattr(cfg, "retaining_wall_step_min_fraction", None)
    hi = getattr(cfg, "retaining_wall_step_max_fraction", None)
    ring_m = getattr(cfg, "retaining_wall_step_ring_m", None)
    dem = getattr(airport, "dem", None)
    if per is None or lo is None or hi is None or ring_m is None or dem is None:
        return 0.0
    if wide > height * float(per):
        return 0.0
    ring = max(float(ring_m), height)
    step = _step_across(dem, whole, wide, ring)
    if step is None:
        return 0.0
    kept = None if top_abs is None else \
        _kept_above_low_side(dem, whole, wide, ring, float(top_abs), height)
    return next((h for h in (height, depth, kept) if h is not None and h > 0.0
                 and float(lo) * h <= step <= float(hi) * h), 0.0)


def _hangs_from_zero(top_y: float | None, seat: float | None, cfg) -> bool:
    """A wall whose top stands within ``retaining_wall_clear_step_m`` of its
    object's zero, seated: the zero of a retaining wall is the upper ground
    it holds (:func:`_depth_under_zero`), so its face hangs from there down
    past the low side's ground to its footing (KMCI's border wall, y -14.0
    .. -0.9; KATL ``muro_concreto5``, -9.70 .. +0.95).  A part standing far
    over its zero is a building's (LEMD ``OldTerminal_FSX-T2SL4``: a 16 m
    facade, its top 15.4 m over its zero) and its height over the low side
    is never read (RULINGS 2026-11-09a (14))."""
    return top_y is not None and seat is not None and \
        float(top_y) <= float(cfg.retaining_wall_clear_step_m)


def _kept_above_low_side(dem, whole, wide: float, ring_m: float, top_abs: float,
                         height: float) -> float | None:
    """THE HEIGHT A WALL RETAINS OVER THE GROUND ON ITS LOW SIDE (RULINGS
    2026-11-09a (14)): ``top_abs`` less the median of the LOWER reading of
    each across pair (:func:`_across_pairs`, the witness's own samples),
    or ``None`` where that is not under its solid ``height`` (nothing of it
    is authored below ground) or not above zero (its top stands under the
    ground)."""
    import numpy as np

    from .dem import dem_z_many
    near, _wall, far = _across_pairs(whole, wide, ring_m)
    if len(near) < 4:
        return None
    low = np.fmin(dem_z_many(dem, near[:, 0], near[:, 1]),
                  dem_z_many(dem, far[:, 0], far[:, 1]))
    low = low[np.isfinite(low)]
    if low.size < 4:
        return None
    kept = float(top_abs) - float(np.median(low))
    return kept if 0.0 < kept < float(height) else None


def _across_pairs(whole, wide: float, ring_m: float):
    """THE ACROSS SAMPLES (:func:`_retains_its_height`): every 2 m round a
    ring ``ring_m`` outside ``whole``, the ring point, its nearest wall
    point and the point as far out on the FAR side (through that wall
    point, ``wide`` across) — three ``(n, 2)`` arrays."""
    import numpy as np
    from shapely.ops import nearest_points
    grown = whole.buffer(ring_m)
    near, wall, far = [], [], []
    for g in getattr(grown, "geoms", [grown]):
        for t in np.arange(0.0, g.exterior.length, 2.0):
            p = g.exterior.interpolate(float(t))
            q = nearest_points(whole, p)[0]
            dx, dy = q.x - p.x, q.y - p.y
            n = (dx * dx + dy * dy) ** 0.5
            if n <= 1e-9:
                continue
            k = (wide + ring_m) / n
            near.append((p.x, p.y))
            wall.append((q.x, q.y))
            far.append((q.x + dx * k, q.y + dy * k))
    return (np.asarray(near, dtype=float).reshape(-1, 2),
            np.asarray(wall, dtype=float).reshape(-1, 2),
            np.asarray(far, dtype=float).reshape(-1, 2))


def _step_across(dem, whole, wide: float, ring_m: float) -> float | None:
    """The median DEM step across ``whole`` (see :func:`_retains_its_height`)."""
    import numpy as np

    from .dem import dem_z_many
    near, _wall, far = _across_pairs(whole, wide, ring_m)
    if len(near) < 4:
        return None
    a = dem_z_many(dem, near[:, 0], near[:, 1])
    b = dem_z_many(dem, far[:, 0], far[:, 1])
    d = np.abs(a - b)
    d = d[np.isfinite(d)]
    return float(np.percentile(d, ACROSS_PERCENTILE)) if d.size >= 4 else None


def retaining_sides(airport: Airport, wall: WallComponent, cfg, step_m: float):
    """THE TWO SIDES OF A RETAINING WALL (#1158): ``(upper, lower, ring)``
    — the bands ``ring`` wide beside ``wall``'s footprint (the witness's
    own ring, :func:`_retains_its_height`) where the ground across it
    steps by more than ``step_m``, on the high side and on the low side.
    Read at the witness's own across samples: a sample whose ground stands
    ``step_m`` under the far one is LOWER, over it UPPER, else neither (a
    wall's ends and returns).  Each sample owns the 2 m of band from the
    wall out to its ring point.  Empty bands without a DEM.

    A wall whose low side the pack's sheets name (#1952,
    ``low_side_source == "sheets"``): the DEM is no witness of it, so its
    sides are its side witness's (:func:`_sheet_sides`)."""
    import numpy as np
    from shapely.geometry import LineString

    from .dem import dem_z_many
    if getattr(wall, "low_side_source", "") == "sheets":
        return _sheet_sides(wall)
    whole = unary_union(wall.pieces)
    ring = max(float(cfg.retaining_wall_step_ring_m), float(wall.height_m))
    dem = getattr(airport, "dem", None)
    if dem is None or whole.is_empty or whole.length <= 0.0:
        return Polygon(), Polygon(), ring
    wide = 2.0 * whole.area / whole.length
    near, foot, far = _across_pairs(whole, wide, ring)
    if len(near) == 0:
        return Polygon(), Polygon(), ring
    d = (dem_z_many(dem, near[:, 0], near[:, 1])
         - dem_z_many(dem, far[:, 0], far[:, 1]))
    band = whole.buffer(ring).difference(whole)

    def _side(mask):
        rays = [LineString([tuple(foot[i]), tuple(near[i])]).buffer(1.0, cap_style="flat")
                for i in np.flatnonzero(mask)]
        return unary_union(rays).intersection(band) if rays else Polygon()

    with np.errstate(invalid="ignore"):
        return _side(d > step_m), _side(d < -step_m), ring


def _sheet_sides(wall):
    """``(upper, lower, ring)`` of a wall whose low side the pack's sheets
    name (#1952, R3): per piece, the band beside the face its side witness
    found the airside pavement along (``WallComponent.paved_face``) and
    the band beside the other, ``ring`` = ``wall_smear_m`` of the height it
    retains wide (``airport/wall_sides``' own bands)."""
    from ..model.wall_reach import wall_smear_m
    from .wall_sides import _face_band, _wall_faces
    ring = wall_smear_m(float(wall.retained_m or wall.height_m))
    up, lo = [], []
    for i, g in enumerate(wall.pieces):
        faces = _wall_faces(g)
        k = wall.paved_face[i] if i < len(wall.paved_face) else None
        if faces is None or k is None:
            continue
        up.append(_face_band(faces[k], g, ring))
        lo.append(_face_band(faces[1 - k], g, ring))
    u = unary_union(up) if up else Polygon()
    v = unary_union(lo) if lo else Polygon()
    both = u.intersection(v)
    return (u.difference(both), v.difference(both), ring) if not both.is_empty else (u, v, ring)
