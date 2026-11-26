"""EVERY FOOTPRINT UNIT'S UNDERSIDE MAP, DERIVED ONCE AT THE PACK STAGE
(owner RULINGS 2026-11-25m; spec ``docs/specs/underside-height-map-20261125.md``
§1, census row U1; the map itself is ``geom/underside_map``).

THE POPULATION is the §16g footprint units the design surface already
derived (``Airport.clusters``, ``placement_family.plan_clusters``: one
population, §16g (9)) -- one map per cluster with a grounded part (a
FOOTLESS cluster -- a roof, a canopy, a sign -- has none: today's carriers
seat it, spec §1), keyed by the SORTED
PLACEMENT ROW IDS of its members (``Member.id``); a second cluster on the
same rows (one OBJ authoring two separate buildings) takes its cluster id
as a last key element.  A recognised COMPOSITE (25l) then joins its sheet
members into one map (``airport/underside_composite``).

THE TRIANGLES: each part's own static solid component (``Part.comp`` into
``ResourceCache.components`` of the member's file), placed by the member's
origin and heading in the airport frame, ``y`` over the member's own zero
(``Member.zero_y``) -- the frame every ``Part.base_y`` and ``Part.feet`` is
in.  Never a line or scatter part (fences never join), never an animated
or hidden-terrain triangle.  A part with ground feet (``Part.feet``) gives
the ``foot`` layer within ``[basin] contact_band_m`` of its own base; an
elevated part gives none.

THE AIRSIDE: the apt.dat pavement the TAXI NETWORK runs on (a row-110
polygon a row-1202 edge crosses; every polygon when the airport has no
network) within :data:`AIRSIDE_NEAR_M`; ``t`` is read from those stations.
A pack's apt.dat often draws its landside lots as pavement too (ELLX: the
SkyPark's lots are ``New Taxiway`` polygons); no aircraft route runs on
them.

``base`` is the unit's zero today: the median authored ``y`` of its WALLED
parts' feet (``footprint_unit._wall_base``, the one reading), which
admission S3 (a) compares ``t`` with.

CACHED WITH THE PARTITION (issue #362's companion discipline,
``partition_cache.companion``): the maps are a pure function of the
partition, the clusters, the airside and this code, so they are kept
beside the partition's cache file (:data:`SUFFIX`) and written only when
the partition is; a build that HITs reads them, a MISS derives them.

A REPORT in step 1: nothing seats, levels or grades by the maps yet."""
from __future__ import annotations

import hashlib
import math
import time
import typing as _t

import numpy as np

from ..geom import underside_map as _um

__all__ = ["AIRSIDE_NEAR_M", "SUFFIX", "LABEL", "unit_population",
           "attach_undersides", "log_line"]

#: a station within this of airside pavement is an airside contact (m)
AIRSIDE_NEAR_M = 3.0
#: the companion cache's suffix beside the partition's file; bump the
#: number when the record's shape changes
SUFFIX = ".under1"
LABEL = "undersides"


def unit_population(airport) -> list[tuple[tuple[str, ...], str, frozenset]]:
    """``(key, cluster id, part ids)`` per footprint unit with parts
    (module doc, THE POPULATION), in the clusters' order."""
    part = getattr(airport, "partition", None)
    if part is None:
        return []
    member_of = {p.pid: m.id for u in part.units for m in u.members for p in m.parts}
    out, seen = [], set()
    for c in getattr(airport, "clusters", None) or ():
        pids = frozenset(q for q in getattr(c, "pids", ()) or () if q in member_of)
        if not pids:
            continue
        key = tuple(sorted({str(member_of[q]) for q in pids}))
        if key in seen:
            key = key + (f"@{c.id}",)
        seen.add(key)
        out.append((key, str(c.id), pids))
    return out


class _Placer:
    """Each part's placed triangles and their per-triangle masks, read once
    per ``(file, component)`` and placed per member."""

    def __init__(self, cache, to_xy, normal_y_min: float, band_m: float) -> None:
        self.cache, self.to_xy = cache, to_xy
        self.normal_y_min, self.band_m = float(normal_y_min), float(band_m)
        self._authored: dict[tuple[str, int], "tuple | None"] = {}

    def _comp(self, path: str, comp: int) -> "tuple | None":
        k = (path, comp)
        if k not in self._authored:
            self._authored[k] = self._read(path, comp)
        return self._authored[k]

    def _file(self, path: str) -> "tuple | None":
        """The file's solid triangles ``(m, 3, 3)``, which are static, and
        which may be a floor -- read once per file."""
        k = (path, None)
        if k not in self._authored:
            g = self.cache.geometry(path)
            if g is None or not len(g.solid):
                self._authored[k] = None
            else:
                v = g.vertices[g.solid]
                keep = np.ones(len(v), dtype=bool)
                for flag in ("animated", "under_terrain"):
                    a = getattr(g, flag, None)
                    if a is not None and a.shape[0] == len(v):
                        keep &= ~a
                d1, d2 = v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]
                ny = d1[:, 2] * d2[:, 0] - d1[:, 0] * d2[:, 2]
                ln = np.sqrt((d1[:, 1] * d2[:, 2] - d1[:, 2] * d2[:, 1]) ** 2 + ny ** 2
                             + (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) ** 2)
                self._authored[k] = (v, keep,
                                     np.abs(ny) >= self.normal_y_min * np.maximum(ln, 1e-12))
        return self._authored[k]

    def _read(self, path: str, comp: int) -> "tuple | None":
        """Component ``comp``'s static triangles and floor flags, or the
        whole file's static solid for ``comp`` -1 (a composite's plan reads
        every face)."""
        f = self._file(path)
        if f is None:
            return None
        v, keep, floor_ok = f
        if comp < 0:
            idx = np.flatnonzero(keep)
        else:
            comps = self.cache.components(path)
            if not 0 <= comp < len(comps) or getattr(comps[comp], "animated", False) \
                    or comps[comp].idx is None:
                return None
            idx = np.asarray(comps[comp].idx)
            idx = idx[keep[idx]]
        return (v[idx], floor_ok[idx]) if len(idx) else None

    def placed(self, member, p) -> "tuple | None":
        """``(tris (n, 3, 3) east/north/y, floor_ok, foot_max)`` of part
        ``p`` of ``member`` (``None``: the member's whole static solid, no
        foot), or ``None``.  Never a line or scatter part."""
        if getattr(member, "origin", None) is None or (p is not None and (
                getattr(p, "line", False) or getattr(p, "scatter", False))):
            return None
        got = self._comp(member.authored_path, -1 if p is None else int(p.comp))
        if got is None:
            return None
        v, floor_ok = got
        ox, oy = self.to_xy(float(member.origin[1]), float(member.origin[0]))
        h = math.radians(float(member.heading_deg))
        s, c = math.sin(h), math.cos(h)
        out = np.empty_like(v, dtype=float)
        out[:, :, 0] = ox + v[:, :, 0] * c - v[:, :, 2] * s
        out[:, :, 1] = oy - (v[:, :, 0] * s + v[:, :, 2] * c)
        out[:, :, 2] = v[:, :, 1] - float(getattr(member, "zero_y", 0.0) or 0.0)
        top = (float(p.base_y) + self.band_m) if getattr(p, "feet", ()) else -np.inf
        return out, floor_ok, np.full(len(v), top)


def _routed_pavement(airport):
    """THE AIRSIDE (module doc): the union of the apt.dat pavement polygons
    the taxi network runs on, or ``None``."""
    import shapely
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union
    nodes = getattr(airport, "taxi_nodes", None) or {}
    lines = [LineString([nodes[e.a].xy, nodes[e.b].xy])
             for e in getattr(airport, "taxi_edges", ()) or ()
             if e.a in nodes and e.b in nodes and nodes[e.a].xy != nodes[e.b].xy]
    net = unary_union(lines) if lines else None
    polys = []
    for pv in getattr(airport, "pavements", ()) or ():
        if str(pv.id).startswith("dsf:") or len(pv.outer) < 3:
            continue
        g = Polygon(list(pv.outer), [list(h) for h in pv.holes if len(h) >= 3])
        g = g if g.is_valid else g.buffer(0.0)
        if not g.is_empty and (net is None or shapely.intersects(g, net)):
            polys.append(g)
    u = unary_union(polys) if polys else None
    return None if u is None or u.is_empty else u


def _near_airside(airport):
    """``near(e, n) -> bool array``: within :data:`AIRSIDE_NEAR_M` of the
    airside (:func:`_routed_pavement`; none: every station is off airside)."""
    import shapely
    air = _routed_pavement(airport)
    if air is None:
        return lambda e, n: np.zeros(len(e), dtype=bool)
    g = air.buffer(AIRSIDE_NEAR_M)
    shapely.prepare(g)
    return lambda e, n: np.asarray(shapely.contains_xy(g, e, n), dtype=bool)


def _law(law) -> tuple[float, float, float, float]:
    """``(normal_y_min, contact band, storey, wall height)`` from the law."""
    b = law.tables.structures.basin
    return (float(getattr(b, "floor_plate_normal_y_min", 0.7) or 0.7),
            float(getattr(b, "contact_band_m", 1.0) or 1.0),
            float(getattr(law.tables.structures.building_pad, "low_level_min_step_m", 3.0)
                  or 3.0),
            float(law.tables.structures.placement.chain_min_height_m))


def _layers(got: list, max_samples: "float | None" = _um.MAX_SAMPLES,
            feet: "np.ndarray | None" = None) -> "_um.Layers | None":
    got = [g for g in got if g is not None]
    if not got:
        return None
    return _um.rasterise_layers(*(np.concatenate([g[k] for g in got]) for k in range(3)),
                                max_samples=max_samples, feet=feet)


def _feet_of(airport, by_pid: dict) -> dict:
    """``{pid: (k, 3)}`` frame east/north and ``y`` of every solid part's
    ground feet (``Part.feet``: ``(lat, lon, authored y)``, already over the
    member's zero), projected in ONE batch through the frame's forward
    transform (the 1 m grid needs no entry snap)."""
    pids, rows = [], []
    for q, (_m, p) in by_pid.items():
        f = getattr(p, "feet", ()) or ()
        if f and not getattr(p, "line", False) and not getattr(p, "scatter", False):
            pids.append((q, len(f)))
            rows.extend(f)
    if not rows:
        return {}
    a = np.asarray(rows, dtype=float)
    fwd = airport.frame.transformers()[0]
    xs, ys = fwd(a[:, 1], a[:, 0])
    xyz = np.column_stack([np.asarray(xs, float), np.asarray(ys, float), a[:, 2]])
    out, at = {}, 0
    for q, k in pids:
        out[q] = xyz[at:at + k]
        at += k
    return out


def _set_layers(part, maps: dict, unit_of: dict, placer: _Placer) -> dict:
    """``{origin-set id: Layers}`` of every pack ``Unit`` whose cluster maps
    span ``terrain_shell.SHELL_MIN_PLAN_M`` or more: every member's WHOLE
    static solid (the composite test's plan, ``underside_composite``: a
    paved ground skin is often thinner than a genuine component)."""
    from .terrain_shell import SHELL_MIN_PLAN_M
    box: dict[str, list] = {}
    for m in maps.values():
        uid = unit_of.get(m.unit)
        g = m.layers
        if uid is None:
            continue
        b = box.setdefault(uid, [math.inf, math.inf, -math.inf, -math.inf])
        b[:] = [min(b[0], g.e0), min(b[1], g.n0),
                max(b[2], g.e0 + g.step * g.top.shape[1]),
                max(b[3], g.n0 + g.step * g.top.shape[0])]
    keys: dict[str, list] = {}
    for k, m in maps.items():
        keys.setdefault(unit_of.get(m.unit, ""), []).append(k)
    out = {}
    for u in part.units:
        b = box.get(str(u.id))
        if b is None or max(b[2] - b[0], b[3] - b[1]) < SHELL_MIN_PLAN_M:
            continue
        if not _may_be_composite([maps[k].layers for k in keys.get(str(u.id), ())]):
            continue
        # at 1 m whatever it costs: the composite test reads the 1 m lattice
        g = _layers([placer.placed(m, None) for m in u.members], max_samples=None)
        if g is not None:
            out[str(u.id)] = g
    return out


def _may_be_composite(layers: list) -> bool:
    """THE CHEAP PRE-TEST of a set's composite plan (DEM-free, on its
    cluster maps): their skin cells span half ``terrain_shaped.MIN_RELIEF_M``
    of relief beyond their plane.  A set that cannot model ground is never
    rasterised whole (ELLX firestation 4.1 m here, 5.7 m whole)."""
    from .terrain_shaped import MIN_RELIEF_M
    g = _um.compose(layers)
    if g is None:
        return False
    with np.errstate(invalid="ignore"):
        skin = np.isfinite(g.top) & ((g.top - g.low) <= _um.SKIN_M)
    if skin.sum() < 3:
        return False
    e, n = g.centres(*np.nonzero(skin))
    return _um.relief(e, n, g.top[skin].astype(float)) >= 0.5 * MIN_RELIEF_M


def _derive(airport, law, cache) -> dict:
    """``{"maps": {key: map}, "sets": {origin-set id: Layers}}`` of
    ``airport`` (module doc): the per-cluster maps and the plans the
    composite test reads; ``cache`` the pack's ``obj8.ResourceCache``
    (parsed files are read from it, any other is parsed)."""
    from types import SimpleNamespace

    from .footprint_unit import _wall_base
    part = getattr(airport, "partition", None)
    if part is None or getattr(airport, "frame", None) is None:
        return {"maps": {}, "sets": {}}
    ny, band, storey, wall_min = _law(law)
    placer = _Placer(cache, airport.frame.entry(), ny, band)
    near = _near_airside(airport)
    by_pid = {p.pid: (m, p) for u in part.units for m in u.members for p in m.parts}
    parts = {q: mp[1] for q, mp in by_pid.items()}
    feet = _feet_of(airport, by_pid)
    out: dict = {}
    for key, cid, pids in unit_population(airport):
        if not any(getattr(parts[q], "feet", ()) for q in pids):
            continue            # FOOTLESS: no map; today's carriers seat it (spec §1)
        fq = [feet[q] for q in sorted(pids) if q in feet]
        layers = _layers([placer.placed(*by_pid[q]) for q in sorted(pids)],
                         feet=np.concatenate(fq) if fq else None)
        if layers is None:
            continue
        m = _um.underside(layers, key, cid, near, storey)
        base = _wall_base(un := SimpleNamespace(id=cid, pids=pids), (un,), parts, wall_min, {})
        out[key] = _with(m, base=float(base))
    unit_of = {str(c.id): str(c.unit) for c in getattr(airport, "clusters", None) or ()}
    return {"maps": out, "sets": _set_layers(part, out, unit_of, placer)}


def _with(m, **kw):
    import dataclasses as _dc
    return _dc.replace(m, **kw)


def _digest(airport, law) -> str:
    """What the maps read beyond the partition's fingerprint (which keys
    this code, the law and the pack: ``partition_code.ENTRY_MODULES``):
    the clusters' part sets."""
    h = hashlib.sha256()
    for c in getattr(airport, "clusters", None) or ():
        h.update(f"{c.id}|{sorted(getattr(c, 'pids', ()) or ())}".encode())
    return h.hexdigest()


def _cached(airport, law, cache, write: bool) -> tuple[dict, str]:
    """The maps through the partition's companion cache, and ``HIT`` /
    ``MISS`` / ``OFF``."""
    from . import partition_cache as _pcache
    part = airport.partition
    root, icao = getattr(part, "pack_root", ""), getattr(part, "icao", "")
    key = _digest(airport, law)
    slot = _pcache.companion(root, icao, SUFFIX, key)
    got = _pcache.read(*slot) if slot is not None else None
    if isinstance(got, dict) and "maps" in got:
        _pcache.companion_note(LABEL, "HIT", f"{slot[0]} ({len(got['maps'])} map(s))")
        return got, "HIT"
    maps = _derive(airport, law, cache)
    held = bool(write) and _pcache.hold_companion(root, icao, SUFFIX, key, maps, LABEL)
    state = "MISS" if slot is not None or held else "OFF"
    _pcache.companion_note(LABEL, state, slot[0] if slot is not None else
                           "(held for the partition's write)" if held
                           else "(no partition cache on file)")
    return maps, state


def attach_undersides(airport, law, cache, *, write_cache: bool = False,
                      cached: bool = True):
    """``airport`` with ``undersides`` (module doc) and ``(seconds, cache
    state)``: the per-cluster maps (cached with the partition when
    ``cached``) with the recognised composites joined
    (``underside_composite.join``, read on the day's DEM)."""
    import dataclasses as _dc

    from .underside_composite import join
    t0 = time.perf_counter()
    if getattr(airport, "partition", None) is None:
        return _dc.replace(airport, undersides={}), (0.0, "OFF")
    if cached:
        got, state = _cached(airport, law, cache, write_cache)
    else:
        got, state = _derive(airport, law, cache), "OFF"
    maps = join(airport, law, got["maps"], got["sets"])
    return _dc.replace(airport, undersides=maps), (time.perf_counter() - t0, state)


def log_line(icao: str, maps: "dict | None", seconds: float = 0.0, state: str = "") -> str:
    """The build log's one line on the underside maps."""
    ms = list((maps or {}).values())
    if not ms:
        return f"[{icao}] underside maps: none"
    comp = [m for m in ms if m.composite]
    sunk = sum(len(m.interiors) for m in ms)
    return (f"[{icao}] underside maps: {len(ms)} grounded unit(s), {len(comp)} composite"
            + (" (" + ", ".join(f"{m.unit} t {m.t:+.2f}" for m in comp
                                if m.t is not None) + ")" if comp else "")
            + f", {sunk} below-grade interior(s), {seconds:.2f} s"
            + (f" (cache {state})" if state else ""))
