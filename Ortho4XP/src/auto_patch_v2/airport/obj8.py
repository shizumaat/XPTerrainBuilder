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
import time
import typing as _t

import numpy as np
import shapely
from shapely import affinity as _affinity
from shapely.errors import GEOSException
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from ..model.frame import XY

__all__ = ["ObjGeometry", "Component", "PlacedObject", "FloorWitness", "ObjReport", "parse_obj8",
           "solid_components", "library_index_path", "read_library_index",
           "resolve_resource", "is_stock_library_resource", "placement_affine",
           "read_placed_objects", "above_grade_footprint", "at_grade_geometry", "ResourceCache",
           "area_fraction_above", "GradeStats",
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
    # keyword lines may be INDENTED (XPlane2Blender writes ``\tTRIS\t0 30``
    # under an LOD; HECA's Tai Models pack: 479 buildings read as "no
    # genuine solid" and none was seated, 2026-09-04) — strip each line
    lines = [ln.strip() for ln in data.split(b"\n")]
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
    # THE COMPONENTS ARE READ IN ONE SORT (11ak (4)), not one MASK OVER
    # EVERY TRIANGLE PER COMPONENT: a pack's clutter object publishes
    # thousands of components over tens of thousands of triangles, and
    # the mask form is quadratic in the two — measured at OTHH, 20 s of
    # the plan stage inside this loop alone.  Sorting once and splitting
    # at the label boundaries does the same work in O(n log n), and the
    # components come out in the same (ascending-label) order.
    order = np.argsort(tri_label, kind="stable")
    lab_sorted = tri_label[order]
    cuts = np.flatnonzero(lab_sorted[1:] != lab_sorted[:-1]) + 1
    hard_deck = geom.hardness == HARD_DECK
    out: list[Component] = []
    for idx in np.split(order, cuts):
        tris = geom.solid[idx]
        pts = v[tris.reshape(-1)]
        out.append(Component(tris, float(pts[:, 1].min()), float(pts[:, 1].max()),
                             float(pts[:, 0].mean()), float(pts[:, 2].mean()),
                             bool(hard_deck[idx].any()), idx))
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


from .obj8_clip import (_clip, _union_rings, _split_at_plane,  # noqa: E402
                        _bulk_polys, _clip_component, _clip_both)
from .obj8_grade import GradeStats, above_clip, both_clip  # noqa: E402
from .obj8_grade import memo_union as _memo_union          # noqa: E402
from .obj8_grade import planes as _planes                  # noqa: E402

class ResourceCache:
    """Parse each resource ONCE; components once."""

    def __init__(self, thickness_m: float) -> None:
        self.thickness_m = thickness_m
        #: RULINGS 2026-09-13bp (i)/(ii): the at-grade / above-grade clip
        #: and union depend only on ``(resource, the components' planes)``,
        #: never on where the placement stands — memoised HERE, per
        #: RESOURCE, in the object's own frame, with the placement affine
        #: applied afterwards.  The placement-keyed caches that used to
        #: hold one ~25 MB transformed geometry per placement are gone.
        self.grade_memo: dict = {}
        self.cover_memo: dict = {}
        #: the second level: one COMPONENT's clip at one plane
        self.clip_memo: dict = {}
        self.grade = GradeStats()
        self._geom: dict[str, ObjGeometry | None] = {}
        self._comps: dict[str, list[Component]] = {}
        self._range: dict[str, tuple[float, float, float, float, float, float]] = {}
        self._bounds: dict[str, np.ndarray] = {}
        #: ``airport/skirt.py``'s per-resource readings (spec §22): the
        #: skirt is read by classify, the planar pass and the re-seat
        #: plan, and the pack is parsed ONCE for all three.
        self.skirt: dict[str, object] = {}
        #: ``airport/basin_witness.py``'s ONE reading of the pack's placed
        #: objects (owner RULINGS 2026-09-10ax (2): the basin admission
        #: runs FIRST, at classify time, and the planar pass reuses it —
        #: the pack is read once, not twice).
        self.placed: dict[str, object] = {}

    # ── the SMALL derived readings, carried across a cached partition ──
    #    (lane ``v2cost2``, owner RULINGS 2026-09-14v).  The parsed
    #    geometry is never cached — it is the 985 MB the recipe rule
    #    refuses — but the per-resource READINGS derived from it are
    #    kilobytes and are what classify would otherwise re-derive: the
    #    skirt readings (each one a plan ``union_all`` over the
    #    resource's triangles) and the two numpy summaries.  Pure in the
    #    pack and the law, which is exactly what the partition cache's
    #    fingerprint pins.
    def derived_state(self) -> dict:
        """The per-resource readings worth storing (note above).  Never
        ``_geom`` / ``_comps`` (the parse) and never ``placed`` (the
        caller holds those objects itself)."""
        return {"skirt": dict(self.skirt), "range": dict(self._range),
                "bounds": dict(self._bounds)}

    def restore_derived(self, state: dict | None) -> int:
        """Put :meth:`derived_state` back on a fresh cache; returns how
        many readings were restored.  Unknown keys are ignored, so an
        older payload restores what it has."""
        if not state:
            return 0
        n = 0
        for key, memo in (("skirt", self.skirt), ("range", self._range),
                          ("bounds", self._bounds)):
            got = state.get(key)
            if got:
                memo.update(got)
                n += len(got)
        return n

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

    def component_bounds(self, path: str) -> np.ndarray:
        """``(n, 4)`` authored plan bounds ``(x0, x1, z0, z1)`` per component
        — the window pre-select of the cover readings (RULINGS
        2026-09-08b/c: a car-park well's cover read off a 3,000-component
        terminal without walking every component)."""
        b = self._bounds.get(path)
        if b is None:
            g = self.geometry(path)
            comps = self.components(path)
            if g is None or not comps:
                b = np.zeros((0, 4))
            else:
                v = g.vertices
                rows = []
                for c in comps:
                    pts = v[c.tris.reshape(-1)]
                    rows.append((float(pts[:, 0].min()), float(pts[:, 0].max()),
                                 float(pts[:, 2].min()), float(pts[:, 2].max())))
                b = np.asarray(rows, dtype=float).reshape(-1, 4)
            self._bounds[path] = b
        return b

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
    #: RULINGS 2026-09-06f (970): the share of the component's solid face
    #: area standing ABOVE the contact band (a tower, a vent in the pit —
    #: cover or protrusion, never the rim) and how high its top reaches
    #: over the local ground; 0 when the shell tops out in the band.
    protrusion_fraction: float = 0.0
    protrusion_top_m: float = 0.0
    #: The plate faces' own deepest authored y (RULINGS 2026-09-08b/c: a
    #: door well's SILL — the floor the ramp descends to; ``z_min`` is the
    #: whole component's, a kerb under the plate included).
    plate_y_min: float = 0.0
    plate_y_max: float = 0.0
    #: THE SHELL'S OUTER PLAN FOOTPRINT (spec §24 (4), owner RULINGS
    #: 2026-09-13g): the WHOLE component in plan — the outer wall face at
    #: the TOP of its walls — not ``below``'s clip at the component's own
    #: ground plane.  ``below`` is clipped at ONE plane (the DEM at the
    #: component's centroid), so every part of the shell that stands above
    #: that plane is missing from it: at LEMD's T4S pit the clip drops the
    #: modelled road ramp as it climbs and leaves 11 of the rim ring's 59
    #: nodes standing 6–15 m from any wall.  The region is built from this.
    #: ``None`` only on a record made before §24 (4) (a fixture): readers
    #: fall back to ``below``.
    outer: object = None                # Polygon | MultiPolygon | None
    #: Which component of the resource witnessed — the ramp reader
    #: (:func:`ramp_decks`) needs the shell's own faces, not the object's.
    comp_index: int = -1


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
    #: RULINGS 2026-09-09w (1): the genuine components ``admission_depth_m``
    #: under their OWN ground (into ``ResourceCache.components``) in a
    #: placement with a FLOOR WITNESS — with none it is no facility.
    below_grade_comps: tuple[int, ...] = ()
    #: THE BURIED PLATES (spec §24 (7) (a)): floor witnesses of components
    #: whose shell never reaches grade.  They SEED no pit — a buried shell
    #: has no rim — but where one lies inside a region another placement's
    #: shell admitted, the region pass takes it as a floor witness of that
    #: pit (OTHH ``Dewatering_02_LOD0_001``'s 2,998 m2 slab inside
    #: ``_002``'s basin:6).  Never part of ``below_grade``/``witnesses``.
    buried: tuple[FloorWitness, ...] = ()


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
    #: EVERY BURIED COMPONENT NAMED (spec §24 (7) (a)): one line per
    #: component whose shell never reaches grade — resource, component
    #: index, plate area, top and floor depth against the ground under it
    #: — instead of the silent ``buried_components`` tally that hid
    #: OTHH's 2,998 m2 basin floor slab.
    buried_named: list[str] = _dc.field(default_factory=list)
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
    #: Resources ADMITTED with solids above the contact band (RULINGS
    #: 2026-09-06f (970): the rim is the ground-contact ring; a tower or a
    #: vent of the same component is a protrusion up to
    #: ``rim_protrusion_max_fraction`` of its face area): path ->
    #: (placements, largest face-area fraction above the band, highest top).
    rim_protrusions: dict[str, tuple[int, float, float]] = _dc.field(default_factory=dict)
    #: Resources refused as DATUM RELIEF (RULINGS 2026-09-09ag, spec
    #: §13): the component's floor stands less than
    #: ``authored_depth_min_m`` under the placement's OWN render datum
    #: (``anchor_z + agl``), so its depth is the datum sitting under the
    #: terrain and not authored — a pack laid out as ONE FLAT PLANE over
    #: real relief (LEMD, Aerosoft, 32 m under the terminal), never a
    #: facility:
    #: path -> (placements, deepest datum drop, deepest depth read,
    #: shallowest AUTHORED depth under the placement's own datum).
    datum_relief: dict[str, tuple[int, float, float, float]] = _dc.field(default_factory=dict)
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
                        *, floor_plate_normal_y_min: float, rim_reaches_grade: bool = True,
                        rim_protrusion_max_fraction: float = 0.0,
                        authored_depth_min_m: float = 0.0
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
    through the ground is a building, reported in ``through_grade`` —
    UNLESS the solids above the band are a PROTRUSION (RULINGS
    2026-09-06f (970): the rim is the shell's ground-contact ring; a
    control tower or a vent standing in the pit is cover, never the rim):
    the component's solid face area above the band plane (each triangle
    clipped there, 3-D area) at most ``rim_protrusion_max_fraction`` of
    its total still witnesses, the share recorded on the witness and in
    ``rim_protrusions``.  Returns the readings and the report; an
    unresolved placement is returned with every reading ``None``."""
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
        below = bbox = deck = smin_z = smin_d = top = None
        witnesses: list[FloorWitness] = []
        buried_wits: list[FloorWitness] = []
        deep_comps: list[int] = []
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
                datum_note: tuple[float, float, float] | None = None
                through: tuple[float, float] | None = None
                protruding: tuple[float, float] | None = None
                for ci, comp in enumerate(cache.components(phys)):
                    if comp.max_y - comp.min_y < cache.thickness_m:
                        continue            # a decal never witnesses (§2.1)
                    cx, cy = _to_frame(xy, heading, comp.cx, comp.cz)
                    local = float(dem_z(cx, cy))
                    if math.isnan(local):
                        local = anchor_z
                    # the component's rendered floor vs the ground under it
                    z_min = base + comp.min_y
                    depth = z_min - local
                    # THE DEPTH IS AUTHORED (RULINGS 2026-09-09ag, spec
                    # §13): a below-grade facility is a SUNKEN SOLID, so its
                    # floor stands ``authored_depth_min_m`` under the
                    # placement's OWN render datum as well as under the
                    # local ground.  When the datum sits UNDER the terrain,
                    # at-datum geometry reads "below grade" without ever
                    # having been sunk — a pack authored as ONE FLAT PLANE
                    # over real relief (LEMD, Aerosoft, 32 m under the
                    # terminal: a ground-floor slab authored 0.5 m under its
                    # own y = 0 reading 15 m under the local ground).  It is
                    # then not a deep part either, so nothing downstream
                    # (the basin region, the below-grade seat skip, the
                    # plate seat) sees it.  A datum ABOVE the ground never
                    # relaxes the gate — the ground still governs there (a
                    # pit dug through a rise is measured from the rise).
                    if base - z_min < authored_depth_min_m:
                        if datum_note is None or local - base > datum_note[0]:
                            datum_note = (local - base, depth, base - z_min)
                        continue
                    if depth <= -admission_depth_m:   # 09w (1): a PART
                        deep_comps.append(ci)
                    plane_below = local - base - admission_depth_m     # authored y
                    # THE BURIED SKIP IS A PIT-SEED TEST, NEVER A SUPPRESSION
                    # (spec §24 (7) (a), owner RULINGS 2026-09-14n item 1 /
                    # 2026-09-14p): a component whose whole shell stands under
                    # the ground cannot SEED a pit — it has no rim at grade —
                    # but its deep horizontal plate still WITNESSES DEPTH
                    # wherever it lies inside a region another placement's
                    # shell admitted.  At OTHH the 2,998 m2 floor slab of
                    # ``OTHH_Dewatering_02_LOD0_001.obj`` is exactly that: a
                    # SIBLING of the shell that founds basin:6, dropped here
                    # silently, leaving the pit witnessing 879 of 4,330 m2.
                    # So the plate is kept aside (``buried``) for the region
                    # pass to pick up, and every skipped component is NAMED
                    # with its area and depth.
                    if shell_reaches_grade and base + comp.max_y < local - contact_band_m:
                        rep.buried_components += 1
                        bw = _witness(g.vertices, comp, base, local, plane_below,
                                      floor_plate_normal_y_min, mat, ci) \
                            if comp.min_y <= plane_below else None
                        rep.buried_named.append(
                            f"{os.path.basename(dpath)}#{ci}: "
                            + (f"floor plate {bw.plate_area_m2:.0f} m2 " if bw is not None
                               else "no floor plate, ")
                            + f"top {base + comp.max_y - local:+.2f} m / floor {depth:+.2f} m "
                              f"vs the ground under it — the shell never reaches grade "
                              f"(buried, > contact_band_m {contact_band_m}): no pit SEED"
                            + (", plate offered to any region that admits it (§24 (7) (a))"
                               if bw is not None else ""))
                        if bw is not None:
                            buried_wits.append(bw)
                        continue
                    if comp.min_y > plane_below:
                        continue
                    if smin_z is None or z_min < smin_z:
                        smin_z, smin_d = z_min, depth
                    w = _witness(g.vertices, comp, base, local, plane_below,
                                 floor_plate_normal_y_min, mat, ci)
                    if w is None:
                        if deep_no_floor is None or depth < deep_no_floor[0]:
                            deep_no_floor = (depth, z_min)
                        continue
                    # THE RIM REACHES GRADE (04i; v1's pit seed): a pit's
                    # shell tops out within the ground-contact band; a
                    # shell that passes through the ground is a building
                    top_above = base + comp.max_y - local
                    if rim_reaches_grade and top_above > contact_band_m:
                        # ...unless what stands above the band is a
                        # PROTRUSION of the shell (2026-09-06f: LEMD85's
                        # tower over a 27,000 m2 floor plate, 3.4 % of its
                        # face area) — the contact ring is still the rim
                        frac = area_fraction_above(g.vertices, comp,
                                                   local - base + contact_band_m)
                        if frac > rim_protrusion_max_fraction:
                            if through is None or top_above > through[0]:
                                through = (top_above, depth)
                            continue
                        w = _dc.replace(w, protrusion_fraction=frac, protrusion_top_m=top_above)
                        protruding = (frac, top_above)
                    witnesses.append(w)
                if witnesses:
                    below = _transformed([w.below for w in witnesses], [1, 0, 0, 1, 0, 0])
                    rep.below_grade_objects += 1
                    if protruding is not None:
                        n, f0, t0 = rep.rim_protrusions.get(dpath, (0, 0.0, 0.0))
                        rep.rim_protrusions[dpath] = (n + 1, max(f0, protruding[0]),
                                                      max(t0, protruding[1]))
                elif through is not None:
                    n, t0, d0 = rep.through_grade.get(dpath, (0, -math.inf, math.inf))
                    rep.through_grade[dpath] = (n + 1, max(t0, through[0]), min(d0, through[1]))
                elif datum_note is not None:
                    n, dr0, dp0, a0 = rep.datum_relief.get(
                        dpath, (0, -math.inf, math.inf, math.inf))
                    rep.datum_relief[dpath] = (n + 1, max(dr0, datum_note[0]),
                                               min(dp0, datum_note[1]),
                                               min(a0, datum_note[2]))
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
                                if deck is not None else (), None,
                                tuple(sorted(set(deep_comps))) if witnesses else (),
                                tuple(buried_wits)))
    return out, rep


def area_fraction_above(v: np.ndarray, comp: Component, plane_y: float) -> float:
    """The share of the component's solid FACE AREA (3-D) lying above the
    authored plane ``y = plane_y`` — each triangle clipped at the plane:
    an apex above two feet below keeps ``ta·tb`` of its area (the
    similar triangle at the apex, ``t`` the edge fraction to the plane),
    two apexes above one foot below keep ``1 − ta·tb`` of it (the
    2026-09-06f protrusion measure).  0 for a component with no area."""
    t = comp.tris
    p0, p1, p2 = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    full = 0.5 * np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1)
    total = float(full.sum())
    if total <= 0.0:
        return 0.0
    h = np.stack([p0[:, 1], p1[:, 1], p2[:, 1]], axis=1) - plane_y
    above = h > 0.0
    n_above = above.sum(axis=1)
    out = np.where(n_above == 3, full, 0.0)
    for k, one_above in ((1, True), (2, False)):
        sel = n_above == k
        if not sel.any():
            continue
        hs = h[sel]
        # the lone vertex (above for k = 1, below for k = 2) and its two feet
        lone = np.argmax(hs > 0.0, axis=1) if one_above else np.argmax(hs <= 0.0, axis=1)
        idx = np.arange(hs.shape[0])
        ha = hs[idx, lone]
        hb = hs[idx, (lone + 1) % 3]
        hc = hs[idx, (lone + 2) % 3]
        share = (ha / (ha - hb)) * (ha / (ha - hc))
        out[sel] = full[sel] * (share if one_above else 1.0 - share)
    return float(out.sum() / total)


def _plan_footprint(v: np.ndarray, comp: Component):
    """THE COMPONENT'S WHOLE PLAN FOOTPRINT in authored coordinates (spec
    §24 (4)): every triangle of the shell, unclipped — what the object
    covers on the ground, wall tops and ramp decks included."""
    return _union_rings([[(float(v[i][0]), float(v[i][2])) for i in tri]
                         for tri in comp.tris.tolist()])


def _witness(v: np.ndarray, comp: Component, base: float, local: float, plane_below: float,
             normal_y_min: float, mat: list[float], comp_index: int = -1) -> FloorWitness | None:
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
    y_min = np.minimum(np.minimum(p0[:, 1], p1[:, 1]), p2[:, 1])
    whole = _plan_footprint(v, comp)
    return FloorWitness(tf(below, mat), plate_f, base + comp.min_y, base + comp.max_y, local,
                        float(plate_f.area), plate_y_min=float(y_min[deep].min()),
                        plate_y_max=float(y_max[deep].max()),
                        outer=None if whole is None else tf(whole, mat),
                        comp_index=comp_index)


def _authored_bbox(xy: XY, heading_deg: float, within) -> tuple[float, float, float, float]:
    """The frame window's bounds taken back to the authored frame
    ``(x0, x1, z0, z1)`` — the placement affine is an involution."""
    h = math.radians(heading_deg)
    s_, c_ = math.sin(h), math.cos(h)
    x0, y0, x1, y1 = within.bounds
    xs, zs = [], []
    for ex, ny in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        dx, dy = ex - xy[0], ny - xy[1]
        xs.append(c_ * dx - s_ * dy)
        zs.append(-s_ * dx - c_ * dy)
    return min(xs), max(xs), min(zs), max(zs)


def _windowed(v: np.ndarray, comp: Component, box: tuple[float, float, float, float] | None
              ) -> Component | None:
    """``comp`` restricted to the triangles whose plan bounding box
    overlaps the authored window ``box`` (``None`` when none does); its y
    range stays the whole component's."""
    if box is None:
        return comp
    ax0, ax1, az0, az1 = box
    px = v[comp.tris][:, :, 0]
    pz = v[comp.tris][:, :, 2]
    m = ((px.max(axis=1) >= ax0) & (px.min(axis=1) <= ax1)
         & (pz.max(axis=1) >= az0) & (pz.min(axis=1) <= az1))
    if not m.any():
        return None
    return Component(comp.tris[m], comp.min_y, comp.max_y, comp.cx, comp.cz, comp.deck)


def _components_near(cache: "ResourceCache", o: "PlacedObject", within
                     ) -> tuple[list[tuple[int, Component]],
                                tuple[float, float, float, float] | None]:
    """The components whose plan bounds overlap the window WITH THEIR
    INDEX in the resource's component list (the index is half the memo
    key of RULINGS 2026-09-13bp (i)), and the window's authored bbox (all
    of them, ``None``, without a window)."""
    comps = list(enumerate(cache.components(o.resolved)))
    if within is None:
        return comps, None
    box = _authored_bbox(o.xy, o.heading_deg, within)
    b = cache.component_bounds(o.resolved)
    if b.shape[0] != len(comps):
        return comps, box
    m = (b[:, 1] >= box[0]) & (b[:, 0] <= box[1]) & (b[:, 3] >= box[2]) & (b[:, 2] <= box[3])
    return [c for c, k in zip(comps, m.tolist()) if k], box


def above_grade_footprint(o: PlacedObject, cache: ResourceCache,
                          dem_z: _t.Callable[[float, float], float], contact_band_m: float,
                          within=None):
    """THE COVER READING for one placement: its solid geometry clipped
    ABOVE the local contact band, in the frame (``None`` when nothing
    stands above it).  EVERY solid component, thickness or not: the
    thickness gate is a FLOOR-witness gate (§2.1: a sheet is not a
    floor) and a roof sheet is cover regardless (LEMD's cargo sheds read
    0 % own cover under the gate, their roofs being single sheets).
    Computed on demand — only for placements whose ``plan_bbox`` reaches
    a candidate region; ``within`` (a frame polygon) restricts the read to
    the triangles near it (RULINGS 2026-09-08b/c: a car-park well's cover
    read off a 150,000-triangle terminal in milliseconds)."""
    if o.resolved is None or is_stock_library_resource(o.path):
        return None
    g = cache.geometry(o.resolved)
    if g is None:
        return None
    base = o.anchor_z + o.agl_m
    mat = placement_affine(o.xy, o.heading_deg)
    comps, box = _components_near(cache, o, within)
    if within is None:
        # ── RULINGS 2026-09-13bp (i): read ONCE per (resource, planes) ──
        keyed = _planes(o, comps, dem_z, base, contact_band_m, True, _to_frame)
        return _place(_memo_union(cache, cache.cover_memo, o, g, comps, keyed,
                                  above_clip), mat)
    rings = []
    for _ci, comp in comps:
        cx, cy = _to_frame(o.xy, o.heading_deg, comp.cx, comp.cz)
        local = float(dem_z(cx, cy))
        if math.isnan(local):
            local = o.anchor_z
        plane_above = local - base + contact_band_m
        if comp.max_y >= plane_above:
            comp = _windowed(g.vertices, comp, box)
            if comp is None:
                continue
            u = _clip_component(g.vertices, comp, plane_above, False)
            if u is not None:
                rings.append(u)
    return _transformed(rings, mat)


def at_grade_geometry(o: PlacedObject, cache: ResourceCache,
                      dem_z: _t.Callable[[float, float], float], contact_band_m: float,
                      select: _t.Callable[[Component], bool] | None = None, within=None):
    """THE RIM AND OWN-COVER EVIDENCE for one placement (04i rules 3 and
    4): EVERY solid component's geometry from ``contact_band_m`` under
    the local ground upward, in the frame, as ``(linework, polygons)`` —
    the linework is where the object meets the ground (a wall's rim),
    the polygons what it holds over the ground at or above grade (a lid
    flush with the ground, a roof).  Thickness or burial do not matter
    here: a buried component simply has no geometry up here.  Computed
    on demand for a candidate region's members only.  ``select`` keeps
    only the components it accepts (RULINGS 2026-09-08b/c: a door well's
    own shell read apart from the building it is attached to)."""
    if o.resolved is None or is_stock_library_resource(o.path):
        return None, None
    g = cache.geometry(o.resolved)
    if g is None:
        return None, None
    base = o.anchor_z + o.agl_m
    mat = placement_affine(o.xy, o.heading_deg)
    lines, polys = [], []
    comps, box = _components_near(cache, o, within)
    if select is None and within is None:
        # ── RULINGS 2026-09-13bp (i): read ONCE per (resource, planes) ──
        keyed = _planes(o, comps, dem_z, base, contact_band_m, False, _to_frame)
        both = _memo_union(cache, cache.grade_memo, o, g, comps, keyed, both_clip)
        if both is None:
            return None, None
        lu, pu = both
        tf = _affinity.affine_transform
        return (None if lu is None else tf(lu, mat)), _place(pu, mat)
    for _ci, comp in comps:
        if select is not None and not select(comp):
            continue
        cx, cy = _to_frame(o.xy, o.heading_deg, comp.cx, comp.cz)
        local = float(dem_z(cx, cy))
        if math.isnan(local):
            local = o.anchor_z
        plane = local - base - contact_band_m
        if comp.max_y < plane:
            continue
        comp = _windowed(g.vertices, comp, box)
        if comp is None:
            continue
        ln, pg = _clip_both(g.vertices, comp, plane)
        if ln is not None:
            lines.append(_affinity.affine_transform(ln, mat))
        if pg is not None:
            polys.append(pg)
    lu = unary_union(lines) if lines else None
    return (None if lu is None or lu.is_empty else lu), _transformed(polys, mat)


def _place(u, mat: list[float]):
    """One LOCAL-frame union taken to the placement's frame (the second
    half of RULINGS 2026-09-13bp (i)): the rigid placement affine commutes
    with the union, so the union is done once per resource and only this
    is paid per placement."""
    if u is None:
        return None
    u = _affinity.affine_transform(u, mat)
    if not u.is_valid:
        u = u.buffer(0)
    return None if u.is_empty else u


def _transformed(parts: list, mat: list[float]):
    if not parts:
        return None
    u = unary_union(parts)
    return None if u.is_empty else _place(u, mat)

