"""OBJ8 reading for the STRUCTURE laws (M4b; Appendix A §3 basins and
object bridges): per placed object, the hard-deck footprint(s)
(``ATTR_hard_deck`` triangles projected to the airport frame), the deck
TOP (memory ``othh-bridge-deck-datum-r12``: the seating datum is the
deck top, never the authored y = 0 plane), the deepest GENUINE solid
(thickness-gated — RULINGS 2026-08-26 §2.1: a part with no vertical
extent of its own is ground paint, never a floor witness) and the
object's BELOW-GRADE footprint (every solid triangle CLIPPED to its
portion below the admission plane — RULINGS 2026-08-26 "the cut shape is
derived from the objects themselves").

GRADE IS LOCAL.  X-Plane drapes a placement at ITS ANCHOR: a vertex
renders at ``DEM(anchor) + agl + y``.  A pack authored on one flat plane
over real relief (LEMD: one anchor for 203 placements, 30 m of relief
across them; memory ``shared-datum-pack-authoring``) has geometry whose
AUTHORED y says nothing about the ground it stands over, and a pack v1
has re-seated (``.anchor_bak`` beside 1,517 objects at LEMD + OTHH,
deltas to −35 m) even less.  So every depth here is measured against the
terrain UNDER the geometry: a solid component's plane is
``DEM(component centroid) − DEM(anchor) − agl − depth`` in the authored
frame, and its rendered elevation is what the floor law reads.  On flat
ground (OTHH: DEM 3.96 everywhere) this is exactly the authored reading.

Resolution is X-Plane's own: a pack-relative path wins, then the
library index (``lib/...`` virtual paths) — read from the pack's
Ortho4XP-only cache (``Airport_mod_cache/o4_library_index_<root>.cache``,
a pickle ``{"fingerprint", "index"}`` v1 maintains) READ-ONLY: a missing
or unreadable index leaves every library placement UNRESOLVED and
reported, never rebuilt here (the churn ruling: caches regenerate through
``--refresh-data``, never as a build side effect).  Stock ``lib/``
resources are never consumed for below-grade geometry (v1 recipe step 1).

Frames.  OBJ8 is x east, y up, z SOUTH, rotated by the placement heading
(clockwise from north) about y:  ``east = x·cos h − z·sin h``,
``north = −(x·sin h + z·cos h)``.  Every law value (the admission depth,
the thickness gate, the contact band) is an argument the caller takes
from ``law/structures.toml``; nothing numeric lives here.
"""
from __future__ import annotations

import dataclasses as _dc
import hashlib
import math
import os
import pickle
import typing as _t

import numpy as np
import shapely
from shapely import affinity as _affinity
from shapely.errors import GEOSException
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..model.frame import XY

__all__ = ["ObjGeometry", "Component", "PlacedObject", "FloorWitness", "ObjReport", "parse_obj8",
           "solid_components", "library_index_path", "read_library_index",
           "resolve_resource", "is_stock_library_resource", "placement_affine",
           "read_placed_objects", "above_grade_footprint", "at_grade_geometry", "ResourceCache",
           "HARD", "HARD_DECK"]

STOCK_LIBRARY_PREFIX = "lib/"
HARD, HARD_DECK = 1, 2


# ── the file ─────────────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class ObjGeometry:
    """One parsed OBJ8: authored vertices ``(n, 3)`` as ``(x, y, z)``;
    solid triangles ``(m, 3)`` with the hardness in force when each was
    emitted (``0`` none / ``HARD`` / ``HARD_DECK`` — the attributes set
    the state, ``ATTR_no_hard`` clears it, and it persists across
    ``TRIS``: verified on EGLL / KBNA / EDDF decks, v1 ``obj8_reader``);
    draped triangles carry no hardness.  Arrays, not tuples: an airport
    pack is millions of triangles (OTHH 9.4 M)."""

    path: str
    vertices: np.ndarray
    solid: np.ndarray
    hardness: np.ndarray
    draped: np.ndarray

    @property
    def hard_deck(self) -> np.ndarray:
        return self.solid[self.hardness == HARD_DECK]


def parse_obj8(path: str) -> ObjGeometry:
    """Parse ``VT`` / ``IDX`` / ``IDX10`` / ``TRIS`` and the draped and
    hardness attributes.  The vertex and index tables are parsed by
    numpy in C; only the ORDER-dependent lines (``TRIS`` and the
    attributes that set the state a ``TRIS`` inherits) are walked in
    Python.  Malformed lines are skipped; a triangle range past the index
    table is truncated."""
    with open(path, "rb") as fh:
        data = fh.read()
    lines = data.split(b"\n")
    vt = [ln[2:] for ln in lines if ln.startswith(b"VT")]
    verts = _floats(vt, 8)[:, :3] if vt else np.zeros((0, 3))
    idx_lines = [ln.split(None, 1)[1] for ln in lines
                 if ln.startswith(b"IDX") and len(ln.split(None, 1)) == 2]
    idx = _ints(idx_lines) if idx_lines else np.zeros(0, dtype=np.int64)
    ranges: list[tuple[int, int, bool, int]] = []
    draped = False
    hard = 0
    for ln in lines:
        c = ln[:1]
        if c != b"T" and c != b"A":
            continue
        toks = ln.split()
        if not toks:
            continue
        kw = toks[0]
        if kw == b"TRIS" and len(toks) >= 3:
            try:
                ranges.append((int(toks[1]), int(toks[2]), draped, hard))
            except ValueError:
                continue
        elif kw == b"ATTR_draped":
            draped = True
        elif kw == b"ATTR_no_draped":
            draped = False
        elif kw == b"ATTR_hard_deck":
            hard = HARD_DECK
        elif kw == b"ATTR_hard":
            hard = HARD
        elif kw == b"ATTR_no_hard":
            hard = 0
    n = int(idx.shape[0])
    nv = int(verts.shape[0])
    solid_parts: list[np.ndarray] = []
    hard_parts: list[np.ndarray] = []
    draped_parts: list[np.ndarray] = []
    for off, cnt, is_draped, h in ranges:
        lo, hi = max(0, off), min(off + cnt, n)
        hi -= (hi - lo) % 3
        if hi <= lo:
            continue
        tri = idx[lo:hi].reshape(-1, 3)
        tri = tri[(tri >= 0).all(axis=1) & (tri < nv).all(axis=1)]
        if is_draped:
            draped_parts.append(tri)
        else:
            solid_parts.append(tri)
            hard_parts.append(np.full(tri.shape[0], h, dtype=np.int8))
    solid = np.concatenate(solid_parts) if solid_parts else np.zeros((0, 3), dtype=np.int64)
    hardness = np.concatenate(hard_parts) if hard_parts else np.zeros(0, dtype=np.int8)
    drp = np.concatenate(draped_parts) if draped_parts else np.zeros((0, 3), dtype=np.int64)
    return ObjGeometry(path, verts, solid, hardness, drp)


def _floats(rows: list[bytes], width: int) -> np.ndarray:
    """``rows`` of ``width`` ASCII floats -> ``(n, width)``; rows with
    another token count are dropped (a hand-edited file)."""
    try:
        arr = np.fromstring(b" ".join(rows), sep=" ")
        if arr.shape[0] == len(rows) * width:
            return arr.reshape(-1, width)
    except ValueError:
        pass
    out = []
    for r in rows:
        toks = r.split()
        if len(toks) != width:
            continue
        try:
            out.append([float(t) for t in toks])
        except ValueError:
            continue
    return np.asarray(out, dtype=float).reshape(-1, width) if out else np.zeros((0, width))


def _ints(rows: list[bytes]) -> np.ndarray:
    try:
        return np.fromstring(b" ".join(rows), sep=" ", dtype=np.int64)
    except ValueError:
        out: list[int] = []
        for r in rows:
            for t in r.split():
                try:
                    out.append(int(t))
                except ValueError:
                    pass
        return np.asarray(out, dtype=np.int64)


@_dc.dataclass(frozen=True)
class Component:
    """One solid connected component in the authored frame: its
    triangles, y range, plan centroid ``(x, z)`` and hard-deck flag."""

    tris: np.ndarray
    min_y: float
    max_y: float
    cx: float
    cz: float
    deck: bool
    #: The component's triangle indices into ``ObjGeometry.solid`` (the
    #: deck signature reads a plate's own component's faces).
    idx: np.ndarray | None = None


def solid_components(geom: ObjGeometry) -> list[Component]:
    """The solid CONNECTED COMPONENTS, position-welded to the millimetre
    (an exporter's per-seam duplicate vertices do not shatter a wall;
    v1 ``weld_parts``)."""
    if geom.solid.shape[0] == 0:
        return []
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    keyed = np.round(geom.vertices, 3)
    _u, canon = np.unique(keyed, axis=0, return_inverse=True)
    canon = np.asarray(canon).reshape(-1)
    nk = int(canon.max()) + 1
    t = canon[geom.solid]
    rows = np.concatenate([t[:, 0], t[:, 1]])
    cols = np.concatenate([t[:, 1], t[:, 2]])
    g = coo_matrix((np.ones(rows.shape[0], dtype=np.int8), (rows, cols)), shape=(nk, nk))
    _n, label = connected_components(g, directed=False)
    tri_label = label[t[:, 0]]
    v = geom.vertices
    out: list[Component] = []
    for lab in np.unique(tri_label):
        mask = tri_label == lab
        tris = geom.solid[mask]
        pts = v[tris.reshape(-1)]
        out.append(Component(tris, float(pts[:, 1].min()), float(pts[:, 1].max()),
                             float(pts[:, 0].mean()), float(pts[:, 2].mean()),
                             bool((geom.hardness[mask] == HARD_DECK).any()),
                             np.nonzero(mask)[0]))
    return out


# ── resolution ───────────────────────────────────────────────────────────

def is_stock_library_resource(path: str) -> bool:
    """A ``lib/...`` virtual path — a stock catalogue asset the terrain
    laws never consume for BELOW-GRADE geometry (v1 recipe step 1)."""
    p = path.replace("\\", "/").lower()
    while p.startswith("./"):
        p = p[2:]
    return p.startswith(STOCK_LIBRARY_PREFIX)


def library_index_path(mod_cache_root: str, xplane_root: str) -> str:
    """Where v1 keeps the merged ``library.txt`` index for an install."""
    key = hashlib.sha1(os.path.abspath(xplane_root).encode()).hexdigest()[:16]
    return os.path.join(mod_cache_root, f"o4_library_index_{key}.cache")


def read_library_index(path: str) -> dict[str, str] | None:
    """The virtual -> physical map, READ-ONLY; ``None`` when absent or
    unreadable (never rebuilt here)."""
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as fh:
            blob = pickle.load(fh)
        index = blob.get("index") if isinstance(blob, dict) else None
        return dict(index) if isinstance(index, dict) else None
    except (OSError, pickle.UnpicklingError, EOFError, AttributeError, ValueError):
        return None


def resolve_resource(def_path: str, pack_root: str | None,
                     index: _t.Mapping[str, str] | None) -> str | None:
    """Pack-relative wins, then the library index (X-Plane's order)."""
    if pack_root:
        cand = os.path.join(pack_root, def_path)
        if os.path.isfile(cand):
            return cand
    if index:
        phys = index.get(def_path) or index.get(def_path.lower())
        if phys and os.path.isfile(phys):
            return phys
    return None


# ── placement → frame ────────────────────────────────────────────────────

def placement_affine(xy: XY, heading_deg: float) -> list[float]:
    """``shapely.affinity.affine_transform`` matrix ``[a, b, d, e, xoff,
    yoff]`` taking authored plan ``(x, z)`` to frame ``(east, north)``."""
    h = math.radians(heading_deg)
    s, c = math.sin(h), math.cos(h)
    return [c, -s, -s, -c, xy[0], xy[1]]


def _to_frame(xy: XY, heading_deg: float, x: float, z: float) -> XY:
    h = math.radians(heading_deg)
    s, c = math.sin(h), math.cos(h)
    return (xy[0] + x * c - z * s, xy[1] - (x * s + z * c))


def _clip(corners, plane_y: float, below: bool) -> list[tuple[float, float]] | None:
    """Sutherland–Hodgman clip of one triangle to ``y <= plane_y``
    (``below``) or ``y >= plane_y``, as the sub-polygon's authored
    ``(x, z)`` ring (3–4 points) or ``None``.  THE CLIP, NOT A TEST: a
    ramp panel running +1 → −6 contributes only its below part."""
    ring: list[tuple[float, float]] = []
    for i in range(3):
        cur, nxt = corners[i], corners[(i + 1) % 3]
        ci = cur[1] <= plane_y if below else cur[1] >= plane_y
        ni = nxt[1] <= plane_y if below else nxt[1] >= plane_y
        if ci:
            ring.append((cur[0], cur[2]))
        if ci != ni:
            span = nxt[1] - cur[1]
            if span == 0.0:
                continue
            f = (plane_y - cur[1]) / span
            ring.append((cur[0] + f * (nxt[0] - cur[0]), cur[2] + f * (nxt[2] - cur[2])))
    return ring if len(ring) >= 3 else None


def _union_rings(rings: list[list[tuple[float, float]]]):
    """The union of clipped-triangle rings, REPAIRED at the contribution
    (a clip of a folded or sliver triangle is invalid; one invalid member
    refuses the whole union — measured OTHH, a side-location conflict at
    the millimetre) and unioned under a snapping precision when the exact
    union still refuses."""
    if not rings:
        return None
    polys = []
    for r in rings:
        try:
            p = Polygon(r)
        except (ValueError, TypeError):
            continue
        if p.is_empty:
            continue
        if not p.is_valid:
            p = shapely.make_valid(p)
        if p.is_empty or p.area <= 1e-9:
            continue
        polys.append(p)
    if not polys:
        return None
    try:
        u = unary_union(polys)
    except GEOSException:
        try:
            u = shapely.union_all(polys, grid_size=1e-6)
        except GEOSException:
            u = unary_union([p.buffer(1e-6) for p in polys])
    if not u.is_valid:
        u = shapely.make_valid(u)
    parts = [g for g in shapely.get_parts(u) if g.geom_type == "Polygon" and g.area > 1e-9]
    if not parts:
        return None
    return unary_union(parts) if len(parts) > 1 else parts[0]


def _clip_component(v: np.ndarray, comp: Component, plane_y: float, below: bool):
    rings = []
    for t in comp.tris.tolist():
        r = _clip((v[t[0]], v[t[1]], v[t[2]]), plane_y, below)
        if r is not None:
            rings.append(r)
    return _union_rings(rings)


def _clip_both(v: np.ndarray, comp: Component, plane_y: float):
    """The component's geometry AT OR ABOVE ``plane_y`` as plan LINEWORK
    (every clipped triangle's ring as a ``LineString``) and as the union
    of the clipped polygons: ``(lines, polygons)``, either ``None``.  A
    vertical wall projects to a line of zero area, which a polygon union
    drops — and a pit's rim IS its vertical walls."""
    from shapely.geometry import LineString
    lines = []
    rings = []
    for t in comp.tris.tolist():
        r = _clip((v[t[0]], v[t[1]], v[t[2]]), plane_y, False)
        if r is None:
            continue
        rings.append(r)
        try:
            lines.append(LineString(r + [r[0]]))
        except (ValueError, TypeError):
            continue
    if not lines:
        return None, None
    u = unary_union(lines)
    return (None if u.is_empty else u), _union_rings(rings)


class ResourceCache:
    """Parse each resource ONCE; components once."""

    def __init__(self, thickness_m: float) -> None:
        self.thickness_m = thickness_m
        self._geom: dict[str, ObjGeometry | None] = {}
        self._comps: dict[str, list[Component]] = {}
        self._range: dict[str, tuple[float, float, float, float, float, float]] = {}

    def geometry(self, path: str) -> ObjGeometry | None:
        if path not in self._geom:
            try:
                self._geom[path] = parse_obj8(path)
            except OSError:
                self._geom[path] = None
        return self._geom[path]

    def components(self, path: str) -> list[Component]:
        c = self._comps.get(path)
        if c is None:
            g = self.geometry(path)
            c = solid_components(g) if g is not None else []
            self._comps[path] = c
        return c

    def genuine(self, path: str) -> list[Component]:
        """The thickness-gated components (§2.1: a decal never witnesses)."""
        return [c for c in self.components(path) if c.max_y - c.min_y >= self.thickness_m]

    def y_range(self, path: str) -> tuple[float, float, float, float, float, float]:
        """``(min_y, max_y, min_x, max_x, min_z, max_z)`` over ALL authored
        vertices — the O(n) pre-screen that decides whether a placement
        can reach below the ground at all (components are the O(n log n)
        step and run only for those that can)."""
        r = self._range.get(path)
        if r is None:
            g = self.geometry(path)
            if g is None or g.vertices.shape[0] == 0:
                r = (math.inf, -math.inf, 0.0, 0.0, 0.0, 0.0)
            else:
                v = g.vertices
                r = (float(v[:, 1].min()), float(v[:, 1].max()), float(v[:, 0].min()),
                     float(v[:, 0].max()), float(v[:, 2].min()), float(v[:, 2].max()))
            self._range[path] = r
        return r


# ── placed objects ───────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class FloorWitness:
    """One floor-carrying solid component of a placement, in the frame
    (RULINGS 2026-09-04i): ``below`` its footprint under the local
    ground, ``plate`` the deep floor plates; ``z_min`` / ``z_top`` the
    component's rendered extent, ``ground_z`` the DEM under it.  The
    rim and own-cover evidence is the whole OBJECT's
    (:func:`at_grade_geometry`), never one component's: a pit's wall
    and its floor are often separate components (LEMD CNTRL: the floor
    slab alone read 26 of 34 rim stations open)."""

    below: object                       # Polygon | MultiPolygon
    plate: object                       # Polygon | MultiPolygon
    z_min: float
    z_top: float
    ground_z: float
    plate_area_m2: float


@_dc.dataclass(frozen=True)
class PlacedObject:
    """One placement's structure reading in the airport frame.  Polygons
    are shapely (a loader, not the model).  ``solid_min_z`` is the
    RENDERED elevation of the deepest genuine solid (``DEM(anchor) + agl
    + y``); ``solid_min_depth_m`` its depth under the terrain at that
    component (negative = below); ``deck_top_z`` the rendered hard-deck
    top."""

    id: str
    path: str
    resolved: str | None
    xy: XY
    heading_deg: float
    agl_m: float
    kind: str
    anchor_z: float
    below_grade: object | None          # Polygon | MultiPolygon, frame
    plan_bbox: object | None            # the resource's plan extent in the frame
    solid_min_z: float | None
    solid_min_depth_m: float | None
    hard_deck: object | None            # Polygon | MultiPolygon, frame
    deck_top_z: float | None
    #: The floor-carrying components (04i): ``below_grade`` is the union
    #: of their ``below`` footprints.
    witnesses: tuple[FloorWitness, ...] = ()
    #: THE DECK SIGNATURE (RULINGS 2026-09-04k; ``airport/deck_signature.py``):
    #: ``"flag"`` when ``hard_deck`` came from ``ATTR_hard_deck`` (the
    #: primary signature), ``"signature"`` when the geometry read a deck
    #: plate that spans a mapped bridge way or an emitted below-grade
    #: region (``hard_deck`` / ``deck_top_z`` are then that plate's),
    #: ``"candidate"`` for a plate with no spanning evidence yet (the
    #: tunnel pass may promote one crossing its ramp), ``"family"`` for a
    #: member of a deck family carrying no plate of its own (a pier, a
    #: railing: it seats WITH its deck), ``""`` otherwise.
    deck_kind: str = ""
    #: The evidence the signature recorded for this object (04k: "evidence
    #: recorded per object"), human-readable, one line per fact.
    deck_evidence: tuple[str, ...] = ()
    #: The plate reading itself (``deck_signature.DeckPlate``) — its axis
    #: end lines and deck-top profile in the airport frame, which the
    #: re-seat's abutment law reads.  ``None`` without a plate.
    deck_plate: object | None = None


@_dc.dataclass
class ObjReport:
    """What the reader resolved and did not."""

    placements: int = 0
    resolved: int = 0
    unresolved: int = 0
    unresolved_paths: list[str] = _dc.field(default_factory=list)
    stock_placements: int = 0
    resources_parsed: int = 0
    below_grade_objects: int = 0
    hard_deck_objects: int = 0
    msl_notes: int = 0
    no_dem_at_anchor: int = 0
    buried_components: int = 0
    #: Resources with genuine, grade-reaching solids under the admission
    #: plane but NO floor plate (a skirt, not a pit): path -> (placements,
    #: deepest depth under the local ground, deepest rendered z).  Every
    #: refusal names its reason (04i).
    no_floor: dict[str, tuple[int, float, float]] = _dc.field(default_factory=dict)
    #: Resources whose floor-carrying shells pass THROUGH the ground —
    #: top more than ``contact_band_m`` above it (a building standing on
    #: the pack's flat plane over real relief: LEMD's cargo terminal, its
    #: slab 5.8 m under the local ground and its walls 15 m above it):
    #: path -> (placements, highest top above the ground, deepest depth).
    through_grade: dict[str, tuple[int, float, float]] = _dc.field(default_factory=dict)
    #: The deck signature (04k; ``deck_signature.classify``): anchor
    #: families read, families whose plate spans a bridge way (decks),
    #: families with a plate and no spanning evidence (candidates), and
    #: the per-family records.
    deck_families: int = 0
    deck_signature_families: int = 0
    deck_candidate_families: int = 0
    deck_records: tuple = ()


def read_placed_objects(placements: _t.Sequence[tuple[str, str, XY, float, float | None, str]],
                        pack_root: str | None, index: _t.Mapping[str, str] | None,
                        dem_z: _t.Callable[[float, float], float],
                        admission_depth_m: float, thickness_m: float, contact_band_m: float,
                        cache: ResourceCache | None = None, shell_reaches_grade: bool = True,
                        *, floor_plate_normal_y_min: float, rim_reaches_grade: bool = True
                        ) -> tuple[list[PlacedObject], ObjReport]:
    """``placements``: ``(id, def_path, xy, heading_deg, elevation, kind)``
    per ``OBJECT*`` row (``elevation`` is the AGL offset for
    ``OBJECT_AGL``, the MSL elevation for ``OBJECT_MSL``, ``None`` for a
    plain ``OBJECT``); ``dem_z(x, y)`` the terrain sampler.  With
    ``shell_reaches_grade`` a component witnesses below-grade geometry
    only when its rendered TOP comes up to within ``contact_band_m`` of
    the ground over it — a pit's shell meets grade by definition (v1's
    pit seed reads the ground-contact band); geometry rendered wholly
    under the terrain (LEMD: grass clumps a v1 bake left 20–44 m under
    the local ground) is buried, not a pit, and is counted in
    ``buried_components``.  ``floor_plate_normal_y_min`` is the
    near-horizontal gate on a floor plate (law ``basin.
    floor_plate_normal_y_min``); with ``rim_reaches_grade`` a floor
    witness's shell must TOP OUT within ``contact_band_m`` of the ground
    (v1's pit seed: ``PIT_SEED_MAX_ABOVE_GRADE_Y_M``) — a shell passing
    through the ground is a building, reported in ``through_grade``.
    Returns the readings and the report; an unresolved placement is
    returned with every reading ``None``."""
    cache = cache or ResourceCache(thickness_m)
    rep = ObjReport(placements=len(placements))
    out: list[PlacedObject] = []
    seen: set[str] = set()
    for oid, dpath, xy, heading, elev, kind in placements:
        agl = 0.0
        if kind == "OBJECT_AGL" and elev is not None:
            agl = float(elev)
        elif kind == "OBJECT_MSL":
            rep.msl_notes += 1
        phys = resolve_resource(dpath, pack_root, index)
        anchor_z = float(dem_z(xy[0], xy[1]))
        if phys is None:
            rep.unresolved += 1
            if dpath not in seen:
                rep.unresolved_paths.append(dpath)
            seen.add(dpath)
            out.append(PlacedObject(oid, dpath, None, xy, heading, agl, kind, anchor_z,
                                    None, None, None, None, None, None))
            continue
        rep.resolved += 1
        if phys not in seen:
            rep.resources_parsed += 1
        seen.add(phys)
        if math.isnan(anchor_z):
            rep.no_dem_at_anchor += 1
            out.append(PlacedObject(oid, dpath, phys, xy, heading, agl, kind, anchor_z,
                                    None, None, None, None, None, None))
            continue
        mat = placement_affine(xy, heading)
        stock = is_stock_library_resource(dpath)
        if stock:
            rep.stock_placements += 1
        g = cache.geometry(phys)
        below = bbox = deck = None
        smin_z = smin_d = top = None
        witnesses: list[FloorWitness] = []
        if g is not None and not stock:
            base = anchor_z + agl               # the rendered y = 0 plane
            vmin, vmax, x0, x1, z0, z1 = cache.y_range(phys)
            corners = [_to_frame(xy, heading, x, zz) for x in (x0, x1) for zz in (z0, z1)]
            bbox = Polygon(corners).convex_hull if vmin < math.inf else None
            # THE PRE-SCREEN: the deepest authored vertex under the HIGHEST
            # ground the placement's extent touches — no component of a
            # placement that fails it can be below grade anywhere
            grounds = [anchor_z] + [float(dem_z(cx, cy)) for cx, cy in corners]
            grounds = [z for z in grounds if not math.isnan(z)]
            if vmin < math.inf and base + vmin <= max(grounds) - admission_depth_m:
                deep_no_floor: tuple[float, float] | None = None
                through: tuple[float, float] | None = None
                for comp in cache.genuine(phys):
                    cx, cy = _to_frame(xy, heading, comp.cx, comp.cz)
                    local = float(dem_z(cx, cy))
                    if math.isnan(local):
                        local = anchor_z
                    # the component's rendered floor vs the ground under it
                    z_min = base + comp.min_y
                    depth = z_min - local
                    if shell_reaches_grade and base + comp.max_y < local - contact_band_m:
                        rep.buried_components += 1
                        continue
                    plane_below = local - base - admission_depth_m     # authored y
                    if comp.min_y > plane_below:
                        continue
                    if smin_z is None or z_min < smin_z:
                        smin_z, smin_d = z_min, depth
                    w = _witness(g.vertices, comp, base, local, plane_below,
                                 floor_plate_normal_y_min, mat)
                    if w is None:
                        if deep_no_floor is None or depth < deep_no_floor[0]:
                            deep_no_floor = (depth, z_min)
                        continue
                    # THE RIM REACHES GRADE (04i; v1's pit seed): a pit's
                    # shell tops out within the ground-contact band; a
                    # shell that passes through the ground is a building
                    top_above = base + comp.max_y - local
                    if rim_reaches_grade and top_above > contact_band_m:
                        if through is None or top_above > through[0]:
                            through = (top_above, depth)
                        continue
                    witnesses.append(w)
                if witnesses:
                    below = _transformed([w.below for w in witnesses], [1, 0, 0, 1, 0, 0])
                    rep.below_grade_objects += 1
                elif through is not None:
                    n, t0, d0 = rep.through_grade.get(dpath, (0, -math.inf, math.inf))
                    rep.through_grade[dpath] = (n + 1, max(t0, through[0]), min(d0, through[1]))
                elif deep_no_floor is not None:
                    n, d0, z0 = rep.no_floor.get(dpath, (0, math.inf, math.inf))
                    rep.no_floor[dpath] = (n + 1, min(d0, deep_no_floor[0]),
                                           min(z0, deep_no_floor[1]))
        if g is not None:
            tris = g.hard_deck
            if tris.shape[0]:
                v = g.vertices
                rings = [[(float(v[i][0]), float(v[i][2])) for i in t] for t in tris.tolist()]
                u = _union_rings(rings)
                if u is not None:
                    deck = _affinity.affine_transform(u, mat)
                    top = anchor_z + agl + float(v[tris.reshape(-1), 1].max())
                    rep.hard_deck_objects += 1
        out.append(PlacedObject(oid, dpath, phys, xy, heading, agl, kind, anchor_z,
                                below, bbox, smin_z, smin_d, deck, top, tuple(witnesses),
                                "flag" if deck is not None else "",
                                ("ATTR_hard_deck: the primary deck signature",)
                                if deck is not None else ()))
    return out, rep


def _witness(v: np.ndarray, comp: Component, base: float, local: float, plane_below: float,
             normal_y_min: float, mat: list[float]) -> FloorWitness | None:
    """The component's floor witness, or ``None`` when it carries no floor
    plate under the admission plane (a skirt: walls, no floor)."""
    t = comp.tris
    p0, p1, p2 = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    n = np.cross(p1 - p0, p2 - p0)
    ln = np.linalg.norm(n, axis=1)
    ok = ln > 1e-12
    ny = np.zeros(t.shape[0])
    ny[ok] = np.abs(n[ok, 1] / ln[ok])
    y_max = np.maximum(np.maximum(p0[:, 1], p1[:, 1]), p2[:, 1])
    deep = (ny >= normal_y_min) & (y_max <= plane_below)
    if not deep.any():
        return None
    plate = _union_rings([[(float(v[i][0]), float(v[i][2])) for i in tri]
                          for tri in t[deep].tolist()])
    if plate is None:
        return None
    plane_ground = local - base                       # authored y of the ground
    below = _clip_component(v, comp, plane_ground, True)
    if below is None:
        return None
    tf = _affinity.affine_transform
    plate_f = tf(plate, mat)
    return FloorWitness(tf(below, mat), plate_f, base + comp.min_y, base + comp.max_y, local,
                        float(plate_f.area))


def above_grade_footprint(o: PlacedObject, cache: ResourceCache,
                          dem_z: _t.Callable[[float, float], float], contact_band_m: float):
    """THE COVER READING for one placement: its solid geometry clipped
    ABOVE the local contact band, in the frame (``None`` when nothing
    stands above it).  EVERY solid component, thickness or not: the
    thickness gate is a FLOOR-witness gate (§2.1: a sheet is not a
    floor) and a roof sheet is cover regardless (LEMD's cargo sheds read
    0 % own cover under the gate, their roofs being single sheets).
    Computed on demand — only for placements whose ``plan_bbox`` reaches
    a candidate region."""
    if o.resolved is None or is_stock_library_resource(o.path):
        return None
    g = cache.geometry(o.resolved)
    if g is None:
        return None
    base = o.anchor_z + o.agl_m
    rings = []
    for comp in cache.components(o.resolved):
        cx, cy = _to_frame(o.xy, o.heading_deg, comp.cx, comp.cz)
        local = float(dem_z(cx, cy))
        if math.isnan(local):
            local = o.anchor_z
        plane_above = local - base + contact_band_m
        if comp.max_y >= plane_above:
            u = _clip_component(g.vertices, comp, plane_above, False)
            if u is not None:
                rings.append(u)
    return _transformed(rings, placement_affine(o.xy, o.heading_deg))


def at_grade_geometry(o: PlacedObject, cache: ResourceCache,
                      dem_z: _t.Callable[[float, float], float], contact_band_m: float):
    """THE RIM AND OWN-COVER EVIDENCE for one placement (04i rules 3 and
    4): EVERY solid component's geometry from ``contact_band_m`` under
    the local ground upward, in the frame, as ``(linework, polygons)`` —
    the linework is where the object meets the ground (a wall's rim),
    the polygons what it holds over the ground at or above grade (a lid
    flush with the ground, a roof).  Thickness or burial do not matter
    here: a buried component simply has no geometry up here.  Computed
    on demand for a candidate region's members only."""
    if o.resolved is None or is_stock_library_resource(o.path):
        return None, None
    g = cache.geometry(o.resolved)
    if g is None:
        return None, None
    base = o.anchor_z + o.agl_m
    mat = placement_affine(o.xy, o.heading_deg)
    lines, polys = [], []
    for comp in cache.components(o.resolved):
        cx, cy = _to_frame(o.xy, o.heading_deg, comp.cx, comp.cz)
        local = float(dem_z(cx, cy))
        if math.isnan(local):
            local = o.anchor_z
        plane = local - base - contact_band_m
        if comp.max_y < plane:
            continue
        ln, pg = _clip_both(g.vertices, comp, plane)
        if ln is not None:
            lines.append(_affinity.affine_transform(ln, mat))
        if pg is not None:
            polys.append(pg)
    lu = unary_union(lines) if lines else None
    return (None if lu is None or lu.is_empty else lu), _transformed(polys, mat)


def _transformed(parts: list, mat: list[float]):
    if not parts:
        return None
    u = unary_union(parts)
    if u.is_empty:
        return None
    u = _affinity.affine_transform(u, mat)
    if not u.is_valid:
        u = u.buffer(0)
    return None if u.is_empty else u
