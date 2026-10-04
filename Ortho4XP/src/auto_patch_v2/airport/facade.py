"""The ``.fac`` READER (issue #334, RULINGS 2026-10-04a (3)).

The engine admitted facades by DEF NAME (``dsf.building_role_for_def``)
and opened no ``.fac``.  This module reads the file: its CLASS and, per
wall, the objects it ATTACHES with their outward reach.  It is a pure
reader — no layout decision is taken here.

Grammar read (X-Plane "facade (.fac) file format", v800 and v1000):

* header ``A|I`` / version / ``FACADE``;
* ``RING 0|1`` (default 1: a closed ring), ``GRADED`` / ``DRAPED``,
  ``TWO_SIDED``, ``SHADER_ROOF``, ``NO_ROOF_MESH``, v800 ``ROOF``;
* ``OBJ <path>`` — the object table ``ATTACH_*`` / ``ROOF_OBJ*`` index;
* ``FLOOR <name>`` opens a floor: ``ROOF_HEIGHT h ...``,
  ``ROOF_OBJ[_HEADING] <obj> ...``, ``SEGMENT i`` / ``SEGMENT_CURVED i``
  with ``ATTACH_DRAPED|ATTACH_GRADED <obj> <x> <y> <z> <heading> ...``,
  and ``WALL <min w> <max w> <min hdg> <max hdg> <name>`` each followed
  by its ``SPELLING <segment> ...`` rows.

THE ATTACH FRAME: ``x`` outward from the wall plane, ``y`` up, ``z``
0..-segment length along the wall; the object is turned by ``heading``
about y.  Outward reach = ``x + ox cos h - oz sin h`` over the object's
``VT`` rows — measured: ``semiTrailer_40ft.obj`` at x 3.4 heading 90
reads 0.9..13.2 m (the trailer's tail at the dock), the other sign
puts it through the wall.  A library object has VARIANTS (the trailer
exports ten models and three empties under one virtual path): the reach
is the widest over all of them, because X-Plane draws any.

WHICH WALL AN EDGE GETS: the DSF's per-vertex wall index when it has
one (polygon depth 3 / 5) — "the wall-picking rules and filters are
completely ignored and the DSF wall choice is always used".  A polygon
WITHOUT one (depth 2 / 4) is given, per edge, a wall whose width range
fits the edge, "picked randomly" among several: the choice is decidable
only when every fitting wall attaches the same things, and is reported
UNDECIDED (``None``) otherwise — never assumed to be wall 0.

Position ALONG a wall is not derivable either (the spelling is picked
"randomly" among those that fit): a wall's attachments are the union
over every segment any of its spellings names, and the consumer takes
the wall's WHOLE edge.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

__all__ = ["Attachment", "Wall", "Floor", "FacadeDef", "EdgeWall",
           "parse_facade", "read_facade", "facade_class", "floor_for",
           "edge_walls", "placed_edges", "PlacedEdge", "object_variants",
           "is_vehicle",
           "LINE", "ROOFED", "LOT", "PARKING_STRUCTURE"]

LINE, ROOFED, LOT, PARKING_STRUCTURE = (
    "line", "roofed", "lot", "parking_structure")
#: RULINGS 2026-10-04a (3): a roof at or under this height is a LOT's
#: painted ground, not a building's roof.
ROOF_MIN_M = 0.5
#: Virtual-path tokens that name a VEHICLE (the trailer rule (b), and the
#: parking structure's "vehicle roof objects").
VEHICLE_TOKENS = ("lib/vehicles/", "lib/cars/", "/vehicles/", "/cars/")


def is_vehicle(obj_path: str) -> bool:
    """Whether an ``OBJ`` table entry names a vehicle."""
    p = obj_path.replace("\\", "/").lower()
    return any(t in p for t in VEHICLE_TOKENS)


@_dc.dataclass(frozen=True)
class Attachment:
    """One ``ATTACH_*`` row, with the reach read off the object."""

    kind: str                       # "draped" | "graded"
    obj: str                        # the OBJ table entry
    x_out: float
    y_up: float
    z_along: float
    heading_deg: float
    #: outward extent ``(min, max)`` in metres off the wall plane over
    #: every variant of the object; ``None`` = no variant resolved.
    reach: tuple[float, float] | None
    variants: int = 0

    @property
    def reach_m(self) -> float | None:
        return None if self.reach is None else self.reach[1]

    @property
    def vehicle(self) -> bool:
        return is_vehicle(self.obj)


@_dc.dataclass(frozen=True)
class Wall:
    """One ``WALL`` with its spellings; ``attachments`` is the union over
    every segment a spelling names, one row per ``(kind, obj)`` at its
    widest reach."""

    name: str
    min_width: float
    max_width: float
    min_heading: float
    max_heading: float
    spellings: tuple[tuple[int, ...], ...]
    attachments: tuple[Attachment, ...]
    #: the same over the ``SEGMENT_CURVED`` twins — what a BEZIER edge
    #: draws (``cargo05_L.fac``'s curved dock segment has no trailer)
    curved_attachments: tuple[Attachment, ...] = ()

    def fits(self, length_m: float) -> bool:
        """The width filter X-Plane applies when the DSF names no wall."""
        return self.min_width <= length_m <= self.max_width

    def reach_m(self, vehicles_only: bool = False, curved: bool = False) -> float:
        """The widest resolved reach on this wall (0.0 = none)."""
        r = [a.reach[1] for a in (self.curved_attachments if curved
                                  else self.attachments) if a.reach is not None
             and (a.vehicle or not vehicles_only)]
        return max(r, default=0.0)


@_dc.dataclass(frozen=True)
class Floor:
    name: str
    roof_heights: tuple[float, ...]
    roof_objects: tuple[str, ...]
    walls: tuple[Wall, ...]

    @property
    def top(self) -> float:
        return max(self.roof_heights, default=0.0)


@_dc.dataclass(frozen=True)
class FacadeDef:
    path: str
    version: int
    ring: bool
    graded: bool
    two_sided: bool
    #: a roof MESH is drawn (v1000 ``SHADER_ROOF`` without
    #: ``NO_ROOF_MESH``; v800 ``ROOF`` rows)
    roof: bool
    objects: tuple[str, ...]
    floors: tuple[Floor, ...]

    @property
    def roof_heights(self) -> tuple[float, ...]:
        return tuple(h for f in self.floors for h in f.roof_heights)


@_dc.dataclass(frozen=True)
class EdgeWall:
    """The wall of one polygon edge: ``wall`` is ``None`` when the DSF
    names none and the fitting walls (``candidates``) disagree."""

    wall: int | None
    candidates: tuple[int, ...]
    from_dsf: bool


def facade_class(fac: FacadeDef) -> str:
    """``line`` / ``roofed`` / ``lot`` / ``parking_structure`` (RULINGS
    2026-10-04a (3)): line-only = an open ring, or v800 with no roof or
    ``TWO_SIDED``, or a closed ring that draws no roof at all; roofed =
    closed with a roof above ``ROOF_MIN_M``; lot = closed with only
    ground-level roofs; parking structure = both, with vehicle roof
    objects."""
    if not fac.ring:
        return LINE
    if fac.version < 1000:
        return ROOFED if fac.roof and not fac.two_sided else LINE
    heights = fac.roof_heights
    if not fac.roof or not heights:
        return LINE
    high = any(h > ROOF_MIN_M for h in heights)
    low = any(h <= ROOF_MIN_M for h in heights)
    if high and low and any(is_vehicle(o) for f in fac.floors
                            for o in f.roof_objects):
        return PARKING_STRUCTURE
    return ROOFED if high else LOT


def floor_for(fac: FacadeDef, height_m: float) -> Floor | None:
    """"The floor whose top-most roof height best matches the requested
    height in the DSF" (the polygon's param)."""
    if not fac.floors:
        return None
    return min(fac.floors, key=lambda f: abs(f.top - height_m))


def _attached(w: Wall) -> tuple:
    return tuple(tuple((a.kind, a.obj, a.reach) for a in t)
                 for t in (w.attachments, w.curved_attachments))


def edge_walls(floor: Floor, edge_lengths_m: _t.Sequence[float],
               dsf_walls: _t.Sequence[int | None]) -> tuple[EdgeWall, ...]:
    """The wall of each edge (edge ``i`` leaves node ``i``).  A DSF wall
    index wins; without one the width filter picks, and several fitting
    walls that attach DIFFERENT things leave the edge undecided."""
    out: list[EdgeWall] = []
    n = len(floor.walls)
    for length, w in zip(edge_lengths_m, dsf_walls):
        if w is not None:
            out.append(EdgeWall(w if 0 <= w < n else None, (), True))
            continue
        cand = tuple(i for i, wl in enumerate(floor.walls) if wl.fits(length))
        same = {_attached(floor.walls[i]) for i in cand}
        out.append(EdgeWall(cand[0] if len(same) == 1 else None, cand, False))
    return tuple(out)


# ── the object table ─────────────────────────────────────────────────────

_LIBRARY_TXT: dict[str, tuple[float, dict[str, tuple[str, ...]]]] = {}


def _library_exports(lib_txt: str) -> dict[str, tuple[str, ...]]:
    """``virtual.lower() -> every physical path`` one ``library.txt``
    exports (the merged index keeps ONE path per virtual path — for the
    trailer an ``EmptyObject.obj`` under the exact-case key)."""
    try:
        mtime = os.path.getmtime(lib_txt)
    except OSError:
        return {}
    hit = _LIBRARY_TXT.get(lib_txt)
    if hit is not None and hit[0] == mtime:
        return hit[1]
    root = os.path.dirname(lib_txt)
    acc: dict[str, list[str]] = {}
    try:
        with open(lib_txt, "r", errors="replace") as fh:
            for raw in fh:
                t = raw.split()
                if len(t) < 3 or not t[0].startswith("EXPORT"):
                    continue
                if t[0] == "EXPORT_RATIO":
                    t = t[1:]
                    if len(t) < 3:
                        continue
                phys = os.path.join(root, " ".join(t[2:]).replace("\\", "/"))
                lst = acc.setdefault(t[1].replace("\\", "/").lower(), [])
                if phys not in lst:
                    lst.append(phys)
    except OSError:
        return {}
    out = {k: tuple(v) for k, v in acc.items()}
    _LIBRARY_TXT[lib_txt] = (mtime, out)
    return out


def _library_txt_of(phys: str) -> str | None:
    d = os.path.dirname(phys)
    for _ in range(12):
        cand = os.path.join(d, "library.txt")
        if os.path.isfile(cand):
            return cand
        up = os.path.dirname(d)
        if up == d:
            break
        d = up
    return None


def object_variants(name: str, fac_dir: str,
                    index: _t.Mapping[str, str] | None) -> tuple[str, ...]:
    """Every file an ``OBJ`` table entry may draw: the file beside the
    ``.fac`` wins (X-Plane's order), else every export of the virtual
    path in the library the EXISTING index resolves it into."""
    name = name.replace("\\", "/")
    local = os.path.join(fac_dir, name)
    if os.path.isfile(local):
        return (local,)
    if not index:
        return ()
    out: list[str] = []
    for key in (name, name.lower()):
        phys = index.get(key)
        if not phys:
            continue
        lib = _library_txt_of(phys)
        for p in (_library_exports(lib).get(name.lower(), ()) if lib else ()) + (phys,):
            if p not in out and os.path.isfile(p):
                out.append(p)
    return tuple(out)


def _reach(x: float, heading_deg: float, paths: _t.Sequence[str]
           ) -> tuple[float, float] | None:
    from .obj8 import parse_obj8
    h = math.radians(heading_deg)
    c, s = math.cos(h), math.sin(h)
    lo = hi = None
    for p in paths:
        try:
            v = parse_obj8(p).vertices
        except OSError:
            continue
        if v.shape[0] == 0:
            continue
        out = x + v[:, 0] * c - v[:, 2] * s
        a, b = float(out.min()), float(out.max())
        lo = a if lo is None else min(lo, a)
        hi = b if hi is None else max(hi, b)
    return None if lo is None or hi is None else (lo, hi)


# ── the file ─────────────────────────────────────────────────────────────

def parse_facade(path: str, index: _t.Mapping[str, str] | None = None
                 ) -> FacadeDef:
    """Parse one ``.fac``; ``index`` (the library index, read-only)
    resolves the ``OBJ`` table's virtual paths for the reach."""
    with open(path, "r", errors="replace") as fh:
        lines = fh.read().splitlines()
    try:
        version = int(lines[1].split()[0])
    except (IndexError, ValueError):
        version = 0
    fac_dir = os.path.dirname(path)
    ring, graded, two_sided = True, False, False
    shader_roof = no_roof_mesh = False
    v800_roof = 0
    objects: list[str] = []
    # floors as mutable records: [name, heights, roof objs, segments, walls]
    floors: list[dict[str, _t.Any]] = []
    seg: list[tuple[str, int, float, float, float, float]] | None = None
    wall: dict[str, _t.Any] | None = None

    def floor() -> dict[str, _t.Any]:
        if not floors:
            floors.append({"name": "", "heights": [], "roof_objs": [],
                           "segs": {}, "csegs": {}, "walls": []})
        return floors[-1]

    for raw in lines[3:]:
        t = raw.split()
        if not t:
            continue
        k = t[0]
        if k in ("VERTEX", "IDX", "MESH"):
            continue
        try:
            if k == "RING":
                ring = int(t[1]) != 0
            elif k == "GRADED":
                graded = True
            elif k == "DRAPED":
                graded = False
            elif k in ("TWO_SIDED", "DOUBLED"):
                two_sided = len(t) < 2 or int(t[1]) != 0
            elif k == "SHADER_ROOF":
                shader_roof = True
            elif k == "NO_ROOF_MESH":
                no_roof_mesh = True
            elif k == "ROOF":
                v800_roof += 1
            elif k == "OBJ":
                objects.append(raw.split(None, 1)[1].strip().replace("\\", "/"))
            elif k == "FLOOR":
                floors.append({"name": t[1] if len(t) > 1 else "", "heights": [],
                               "roof_objs": [], "segs": {}, "csegs": {}, "walls": []})
                seg = wall = None
            elif k == "ROOF_HEIGHT":
                floor()["heights"] += [float(x) for x in t[1:]]
            elif k in ("ROOF_OBJ", "ROOF_OBJ_HEADING"):
                oi = int(t[1])
                if 0 <= oi < len(objects):
                    floor()["roof_objs"].append(objects[oi])
            elif k == "SEGMENT":
                seg = floor()["segs"].setdefault(int(t[1]), [])
                wall = None
            elif k == "SEGMENT_CURVED":
                seg = floor()["csegs"].setdefault(int(t[1]), [])
                wall = None
            elif k in ("ATTACH_DRAPED", "ATTACH_GRADED") and seg is not None:
                row = ("draped" if k == "ATTACH_DRAPED" else "graded", int(t[1]),
                       float(t[2]), float(t[3]), float(t[4]), float(t[5]))
                if row not in seg:
                    seg.append(row)
            elif k == "WALL":
                # v1000 ``WALL min max min_hdg max_hdg name``; v800 names
                # only the width range
                spec: list[float] = []
                for x in t[1:5]:
                    try:
                        spec.append(float(x))
                    except ValueError:
                        break
                wall = {"spec": (spec + [0.0] * 4)[:4],
                        "name": t[len(spec) + 1] if len(t) > len(spec) + 1 else "",
                        "sp": []}
                floor()["walls"].append(wall)
                seg = None
            elif k == "SPELLING" and wall is not None:
                wall["sp"].append(tuple(int(x) for x in t[1:]))
        except (ValueError, IndexError):
            continue

    reach_memo: dict[tuple[int, float, float], tuple[tuple[float, float] | None, int]] = {}

    def attachment(row: tuple[str, int, float, float, float, float]) -> Attachment | None:
        kind, oi, x, y, z, h = row
        if not 0 <= oi < len(objects):
            return None
        key = (oi, x, h)
        if key not in reach_memo:
            paths = object_variants(objects[oi], fac_dir, index)
            reach_memo[key] = (_reach(x, h, paths), len(paths))
        reach, nvar = reach_memo[key]
        return Attachment(kind, objects[oi], x, y, z, h, reach, nvar)

    out_floors: list[Floor] = []
    for f in floors:
        walls: list[Wall] = []
        for w in f["walls"]:
            both: list[tuple[Attachment, ...]] = []
            for table in ("segs", "csegs"):
                best: dict[tuple[str, str], Attachment] = {}
                for si in sorted({s for sp in w["sp"] for s in sp}):
                    for row in f[table].get(si, ()):
                        a = attachment(row)
                        if a is None:
                            continue
                        old = best.get((a.kind, a.obj))
                        if old is None or (a.reach is not None and (
                                old.reach is None or a.reach[1] > old.reach[1])):
                            best[(a.kind, a.obj)] = a
                both.append(tuple(best[k] for k in sorted(best)))
            walls.append(Wall(w["name"], *w["spec"], tuple(w["sp"]), *both))
        out_floors.append(Floor(f["name"], tuple(f["heights"]),
                                tuple(f["roof_objs"]), tuple(walls)))
    # v800 draws a roof from ``ROOF`` rows or a ``SHADER_ROOF`` block
    # (``uh_metallic01.fac`` carries only the latter)
    roof = (shader_roof and not no_roof_mesh) or v800_roof > 0
    return FacadeDef(path, version, ring, graded, two_sided, roof,
                     tuple(objects), tuple(out_floors))


_PARSED: dict[str, tuple[float, FacadeDef]] = {}


def read_facade(def_path: str, pack_root: str | None,
                index: _t.Mapping[str, str] | None) -> FacadeDef | None:
    """Resolve a ``POLYGON_DEF`` (pack-relative, then the library index —
    ``obj8.resolve_resource``) and parse it once per file version;
    ``None`` = unresolved or unreadable."""
    from .obj8 import resolve_resource
    phys = resolve_resource(def_path, pack_root, index)
    if phys is None:
        return None
    try:
        mtime = os.path.getmtime(phys)
        hit = _PARSED.get(phys)
        if hit is None or hit[0] != mtime:
            hit = (mtime, parse_facade(phys, index))
            _PARSED[phys] = hit
        return hit[1]
    except OSError:
        return None


# ── a placed polygon ─────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class PlacedEdge:
    """One edge of a placed facade polygon with the wall it draws."""

    i: int
    a: tuple[float, float]
    b: tuple[float, float]
    length_m: float
    curved: bool
    wall: EdgeWall
    name: str                       # the wall's name ("" = undecided)
    attachments: tuple[Attachment, ...]


def placed_edges(fac: FacadeDef, height_m: float,
                 nodes: _t.Sequence[tuple[float, float, int | None, bool]]
                 ) -> tuple[PlacedEdge, ...]:
    """The edges of one placed polygon — ``nodes`` are ``(x, y, wall,
    curved)`` in METRES (any plane frame), edge ``i`` leaves node ``i``; a
    ring facade closes last -> first.  A zero-length edge (the repeated
    closing node of a bezier winding) is dropped."""
    floor = floor_for(fac, height_m)
    n = len(nodes)
    if floor is None or n < 2:
        return ()
    rows = []
    for i in range(n if fac.ring else n - 1):
        p, q = nodes[i], nodes[(i + 1) % n]
        length = math.hypot(q[0] - p[0], q[1] - p[1])
        if length > 1e-6:
            rows.append((i, (p[0], p[1]), (q[0], q[1]), length,
                         bool(p[3] or q[3]), p[2]))
    walls = edge_walls(floor, [r[3] for r in rows], [r[5] for r in rows])
    out = []
    for (i, a, b, length, curved, _w), ew in zip(rows, walls):
        w = floor.walls[ew.wall] if ew.wall is not None else None
        out.append(PlacedEdge(
            i, a, b, length, curved, ew, w.name if w else "",
            () if w is None else (w.curved_attachments if curved else w.attachments)))
    return tuple(out)
