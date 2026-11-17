"""THE LARGE STRUCTURES TWO PACKS BOTH DRAW near an airport (issue #2145).

Owner (2026-11-17T19:15Z): "we should add the offer for the user to hide
large overlapping elements … Chudoba Dubai, and OMDB TaiModels both of
which model the train and it's stations.  We want the user to be able to
pick which one to keep … Default would be to prefer the airport pack."

THE READING (pure: dump text in, pairs out; no pack is written here):

* THE REGION — each airport of the airport pack's apt.dat: its authored
  boundary (row 130, outer ring), else the box of its runways and
  pavement (``pack_drapes.airport_boxes``), grown by :data:`REACH_M`
  (1 km, owner 2026-11-17T19:08Z: the overlay packs within 1 km of the
  boundary).
* THE STRUCTURES — every ``OBJECT*`` row (``.obj``: the plan hull of its
  solid triangles, ``skirt.footprint``, placed by ``obj8.placement_affine``;
  ``.agp``: its own footprint, ``riders.agp_footprint_xy``) and every
  BUILDING facade polygon (``.fac`` of ``facade.facade_class`` roofed or
  parking structure — a fence or wall ring encloses ground it does not
  cover; its first winding) of a pack's tile DSF that touches the region and covers
  at least ``[building_pad] min_area_m2`` — the law's floor below which a
  footprint is not a building of its own.  Draped polygons, lines and
  networks are not structures (a network's width lives in its ``.net``;
  not read in this round).
* THE OVERLAP — two packs' structures whose plan intersection covers at
  least :data:`SHARE` of the SMALLER one's plan: the same thing drawn
  twice.  Each side's rows in any such overlap are what hiding that side
  removes (:class:`HideRow`, the key ``dsf_row_hide`` matches).

Nothing here names an airport or a pack.  Build-time impact: none (the
offer runs after a tile is built, ``auto_patch.overlap_stage``).
"""
from __future__ import annotations

import collections
import typing as _t

import shapely
from shapely.geometry import Polygon
from shapely.strtree import STRtree

from .anchor_rule import _m_per_deg

__all__ = ["REACH_M", "SHARE", "HideRow", "Structure", "OverlapPair",
           "Frame", "airport_regions", "structures", "overlaps"]

#: how far beyond the airport boundary a structure counts (metres; owner
#: 2026-11-17T19:08Z "within 1 km of the boundary")
REACH_M = 1000.0
#: the share of the smaller footprint two structures must both cover to be
#: one structure drawn twice (issue #2145 brief: "≥ 50 % of the smaller's
#: plan")
SHARE = 0.5


class HideRow(_t.NamedTuple):
    """One placement row of a pack DSF: its resource and its anchor (an
    object's position, a facade's first point)."""

    resource: str
    lon: float
    lat: float


class Structure(_t.NamedTuple):
    """One large structure of one pack inside the region."""

    pack: str
    kind: str              # "object" | "facade"
    row: HideRow
    poly: _t.Any           # plan footprint (Polygon / MultiPolygon), metres

    @property
    def area_m2(self) -> float:
        return float(self.poly.area)


class OverlapPair(_t.NamedTuple):
    """Two packs that draw the same large structures."""

    packs: tuple[str, str]                  # sorted pack names
    rows: tuple[tuple[HideRow, ...], tuple[HideRow, ...]]   # per pack
    count: int                              # overlapping structure pairs
    area_m2: float                          # their shared plan area

    def summary(self) -> str:
        """One line for the offer: who draws what twice."""
        a, b = self.packs
        return (f"{a} and {b} both draw {self.count} large structure"
                f"{'s' if self.count != 1 else ''} near the airport "
                f"({_what(self.rows[0])} / {_what(self.rows[1])}; "
                f"{self.area_m2:,.0f} m² overlap)")


def _what(rows: _t.Sequence[HideRow]) -> str:
    """``"115 placements: facades 60, objects/metro 30"``: the count and
    the folders most of them come from."""
    dirs = collections.Counter(r.resource.rsplit("/", 1)[0] if "/" in r.resource
                               else r.resource for r in rows)
    top = ", ".join(f"{d} {n}" for d, n in dirs.most_common(3))
    return f"{len(rows)} placement{'s' if len(rows) != 1 else ''}" + (
        f": {top}" if top else "")


class Frame(_t.NamedTuple):
    """Metres east / north of ``(lon0, lat0)`` (one scale for the region)."""

    lon0: float
    lat0: float

    def xy(self, lon: float, lat: float) -> tuple[float, float]:
        mlat, mlon = _m_per_deg(self.lat0)
        return ((lon - self.lon0) * mlon, (lat - self.lat0) * mlat)

    def lonlat_box(self, poly: Polygon) -> tuple[float, float, float, float]:
        """``poly``'s bounds back in degrees ``(w, s, e, n)``."""
        mlat, mlon = _m_per_deg(self.lat0)
        x0, y0, x1, y1 = poly.bounds
        return (self.lon0 + x0 / mlon, self.lat0 + y0 / mlat,
                self.lon0 + x1 / mlon, self.lat0 + y1 / mlat)


def airport_regions(apt_path: str) -> list[tuple[Frame, Polygon]]:
    """One ``(frame, region)`` per airport of ``apt_path``: its boundary
    (else its runway/pavement box) grown by :data:`REACH_M`."""
    from . import apt_dat as _ad
    out = []
    for icao in _ad.airports_in(apt_path) if apt_path else ():
        block = _ad.read_airport_block(apt_path, icao)
        try:
            apt = _ad.parse_airport_block(block) if block else None
        except (ValueError, IndexError):
            apt = None
        if apt is None:
            continue
        ring = list(apt.boundaries[0].rings[0]) if apt.boundaries else []
        pts = ring or ([(e[2], e[1]) for r in apt.runways for e in r.ends]
                       + [p for pv in apt.pavements for p in pv.rings[0]])
        if not pts:
            continue
        w, s = min(p[0] for p in pts), min(p[1] for p in pts)
        e, n = max(p[0] for p in pts), max(p[1] for p in pts)
        ring = ring or [(w, s), (e, s), (e, n), (w, n)]
        fr = Frame((w + e) / 2.0, (s + n) / 2.0)
        poly = Polygon([fr.xy(lo, la) for lo, la in ring]).buffer(0)
        if poly.is_empty:
            continue
        out.append((fr, poly.buffer(REACH_M)))
    return out


def _rows(lines: _t.Iterable[str], bounds: tuple[float, float, float, float]
          ) -> tuple[list, list]:
    """``(objects, facades)`` of a DSF dump inside ``bounds`` (degrees):
    ``(resource, lon, lat, heading)`` and ``(resource, [(lon, lat)…])``."""
    w, s, e, n = bounds
    odefs: list[str] = []
    pdefs: list[str] = []
    objs, facs = [], []
    poly_def = None
    ring: list = []
    in_first = False
    for ln in lines:
        c = ln[:6]
        if c == "OBJECT":
            t = ln.split()
            if t[0] == "OBJECT_DEF":
                odefs.append(t[1] if len(t) > 1 else "")
            elif len(t) >= 5:
                lon, lat = float(t[2]), float(t[3])
                if w <= lon <= e and s <= lat <= n:
                    objs.append((odefs[int(t[1])], lon, lat, float(t[4])))
        elif c == "POLYGO":
            if ln.startswith("POLYGON_POINT") and in_first:
                t = ln.split()
                ring.append((float(t[1]), float(t[2])))
            elif ln.startswith("POLYGON_DEF"):
                pdefs.append(ln.split(None, 1)[1].strip())
        elif c == "BEGIN_":
            if ln.startswith("BEGIN_POLYGON"):
                d = pdefs[int(ln.split()[1])]
                poly_def = d if d.lower().endswith(".fac") else None
                ring, in_first = [], False
            elif ln.startswith("BEGIN_WINDING") and poly_def is not None:
                in_first = not ring
        elif c == "END_WI":
            in_first = False
        elif c == "END_PO":
            if poly_def is not None and len(ring) >= 3 and any(
                    w <= lo <= e and s <= la <= n for lo, la in ring):
                facs.append((poly_def, ring))
            poly_def = None
    return objs, facs


def _plan(path: str, cache, min_area_m2: float):
    """A resolved ``.obj``'s plan footprint in its authored ``(x, z)``
    frame (``skirt.footprint``: the union of its solid triangles, never a
    hull — one ``.obj`` often draws many buildings), memoised per resource
    on ``cache``; ``None`` under ``min_area_m2`` (its hull, read first,
    rules out the small ones cheaply)."""
    memo = cache.__dict__.setdefault("overlap_plan", {})
    if path not in memo:
        geom = cache.geometry(path)
        got = None
        if geom is not None and geom.solid.shape[0]:
            hull = shapely.convex_hull(shapely.multipoints(
                geom.vertices[geom.solid.reshape(-1)][:, [0, 2]]))
            if hull.area >= min_area_m2:
                from .skirt import footprint
                got = footprint(cache, path)
        memo[path] = got if got is not None and got.area >= min_area_m2 else None
    return memo[path]


def _object_poly(path: str, cache, xy, hdg: float, min_area_m2: float):
    """The placed plan footprint of a resolved ``.obj`` / ``.agp``."""
    if path.lower().endswith(".agp"):
        from .riders import agp_footprint_xy
        ring = agp_footprint_xy(path, xy, hdg)
        return Polygon(ring) if ring and len(ring) >= 3 else None
    plan = _plan(path, cache, min_area_m2)
    if plan is None:
        return None
    from shapely import affinity

    from .obj8 import placement_affine
    return affinity.affine_transform(plan, placement_affine(xy, hdg))


def _roofed(path: str | None, cache) -> bool:
    """A facade that is a BUILDING (``facade.facade_class`` roofed or a
    parking structure) — never a fence, a wall or a lot, whose ring
    encloses ground it does not cover.  Memoised per file on ``cache``."""
    if not path:
        return False
    memo = cache.__dict__.setdefault("overlap_roofed", {})
    if path not in memo:
        from . import facade as _fac
        try:
            fac = _fac.parse_facade(path)
        except (OSError, ValueError, IndexError):
            fac = None
        # a v800 closed single-sided ring is a building too: its roof is
        # often a ``ROOF_SCALE`` the reader does not count as ``ROOF``
        memo[path] = fac is not None and (
            _fac.facade_class(fac) in (_fac.ROOFED, _fac.PARKING_STRUCTURE)
            or (fac.version < 1000 and fac.ring and not fac.two_sided))
    return memo[path]


def structures(pack: str, lines: _t.Iterable[str], frame: Frame,
               region: Polygon, min_area_m2: float,
               resolve: _t.Callable[[str], str | None], cache
               ) -> list[Structure]:
    """The pack's large structures touching ``region`` (module doc).
    ``resolve`` maps a DSF resource to its file (``None``: unreadable,
    skipped); ``cache`` is an ``obj8.ResourceCache``."""
    out: list[Structure] = []
    objs, facs = _rows(lines, frame.lonlat_box(region))
    for res, lon, lat, hdg in objs:
        if not res.lower().endswith((".obj", ".agp")):
            continue
        path = resolve(res)
        poly = (_object_poly(path, cache, frame.xy(lon, lat), hdg, min_area_m2)
                if path else None)
        if poly is not None and poly.area >= min_area_m2 and poly.intersects(region):
            out.append(Structure(pack, "object", HideRow(res, lon, lat), poly))
    for res, ring in facs:
        if not _roofed(resolve(res), cache):
            continue
        poly = Polygon([frame.xy(lo, la) for lo, la in ring]).buffer(0)
        if poly.area >= min_area_m2 and poly.intersects(region):
            out.append(Structure(pack, "facade",
                                 HideRow(res, ring[0][0], ring[0][1]), poly))
    return out


def overlaps(by_pack: _t.Mapping[str, _t.Sequence[Structure]],
             share: float = SHARE) -> list[OverlapPair]:
    """Every pair of packs whose structures overlap (module doc), largest
    shared area first."""
    names = sorted(n for n, v in by_pack.items() if v)
    out = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            pair = _pair(a, b, by_pack[a], by_pack[b], share)
            if pair is not None:
                out.append(pair)
    return sorted(out, key=lambda p: -p.area_m2)


def _pair(a: str, b: str, sa: _t.Sequence[Structure], sb: _t.Sequence[Structure],
          share: float) -> OverlapPair | None:
    tree = STRtree([s.poly for s in sb])
    ra: dict[HideRow, None] = {}
    rb: dict[HideRow, None] = {}
    count, area = 0, 0.0
    for s in sa:
        for j in tree.query(s.poly):
            t = sb[int(j)]
            inter = s.poly.intersection(t.poly).area
            if inter >= share * min(s.area_m2, t.area_m2) > 0.0:
                ra[s.row] = rb[t.row] = None
                count += 1
                area += inter
    if not count:
        return None
    return OverlapPair((a, b), (tuple(ra), tuple(rb)), count, area)

