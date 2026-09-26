"""§42 OBJECT-BASED PAVEMENT IS A SOURCE (owner RULINGS 2026-09-13cv) —
the pack's DRAPED OBJ8 ground polygons, read as pavement source geometry
beside the apt.dat 110 polygons and the ``.pol`` POLYGON_DEF pages.

THE DEFECT (RULINGS 2026-09-13cu, HECA).  ``Airport/ground/
Concrete_Polygon_1.obj`` is a draped OBJ8 ground polygon — 1,137 vertices
all at local Y = 0, 379 triangles, 29 disjoint bodies, 580,331 m² — placed
once at the pack origin.  X-Plane drapes it onto the mesh correctly and it
can never float, so the object stage rightly skips it (``no genuine solid
component``); but the LAYOUT never saw it either, because pavement sources
were apt.dat 110 polygons and ``.pol`` pages only.  The owner's apron at
30.1235047, 31.4160956 (body 6, 25,012 m²) therefore drapes on raw mesh at
95.09 while the mapped apron ``pav132`` is graded 82 m away.

WHAT IS ADMITTED (§42 (1), and one measured amendment).  A placed OBJ8
whose geometry is DRAPED-ONLY (no solid triangle: a solid is the building
path's business), every draped vertex within ``draped_y_tol_m`` of Y = 0,
covering at least ``object_pavement_min_m2``, is object-based pavement.
Its footprint is the union of its draped triangles, transformed by the
placement (origin, heading), split into DISJOINT BODIES; each body is one
source polygon.

THE AMENDMENT, AND THE MEASUREMENT THAT FORCED IT (lane ``v2drapedsrc``,
HECA 1.0.329 frame).  §42 (1) as written admits every draped Y = 0 page,
and at HECA that is 27 placements / 937 bodies / **31,892,813 m²** — three
times the airport — because a pack's draped pages are not only its
pavement: ``Airport/Hangar_Tower/AO.obj`` (7,753,162 m²) and three more
``AO``/``ao`` pages are baked AMBIENT-OCCLUSION SHADOWS, ``ground/d1..d9``
(6.4 M m²) are dirt decals, and ``ground/asphalt_white.obj`` (435 bodies)
and ``ground/car_parking.obj`` (249) are the painted markings ON the
pavement.  Grading the ground under a shadow is not §42's intent.  The
discriminator is the pack's own declaration, and v1's ground-paint reader
(``auto_patch/dsf_reader._is_pavement_object``, the ruled gate behind
``o4_object_pavements_<tile>.cache``) already states it: the object must
declare ``ATTR_layer_group_draped`` in a PAVEMENT layer group
(``object_pavement_layer_groups``) at an offset no greater than
``object_pavement_max_layer_offset``, and carry no decorative token in its
basename.  A shadow declares no draped layer group at all; a decal
declares ``markings``; a painted marking declares ``runways +2`` (it is
drawn OVER the pavement, and says so).  With the gate HECA admits 8
placements / 221 bodies / 5,688,974 m² — the pack's actual concrete and
asphalt, ``Concrete_Polygon_1.obj`` among them at exactly the 29 bodies /
580,331 m² RULINGS 13cu counted.  The gate is LAW (``[load]`` in
``law/structures.toml``), so relaxing it is one law edit and one measured
arm, not a code change.

COST.  The layer group and the texture name are read from the file HEADER
(the bytes before the first vertex), so the 528 unique resources of a HECA
pack are screened in 0.01 s and only the ~10 survivors are parsed
(0.39 s).  Parsing every placed object to find the draped ones costs 6.0 s
at HECA and is not done.
"""
from __future__ import annotations

import dataclasses as _dc
import os
import typing as _t

import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..model.frame import XY
from . import frame_entry as _fe
from . import obj8 as _obj8

__all__ = ["Placement", "DrapedBody", "ResourceRow", "ObjectPavementReport",
           "header_facts", "draped_footprint", "hard_plane_footprint",
           "read_object_pavements"]

#: How far into the file the header facts are looked for.  An OBJ8 header
#: (``I``/``800``/``OBJ``, the textures, the attributes, ``POINT_COUNTS``)
#: is a few hundred bytes; the scan stops at the first geometry line
#: whatever the size.
_HEADER_BYTES = 8192
_GEOMETRY_KEYWORDS = (b"VT", b"VLINE", b"VLIGHT", b"IDX", b"IDX10", b"TRIS")


@_dc.dataclass(frozen=True)
class Placement:
    """One placed object, as the loader already read it."""

    id: str
    def_path: str            # the DSF's resource path (the description)
    resolved_path: str       # the OBJ8 file it resolves to
    xy: XY                   # the placement origin in the airport frame
    heading_deg: float


@_dc.dataclass(frozen=True)
class DrapedBody:
    """One disjoint body of one placement's draped footprint, in the
    airport frame.  ``resource`` is the DSF resource path (§42 (1): the
    body's description); ``texture`` the pack's ``TEXTURE_DRAPED`` page
    (its evidence)."""

    placement_id: str
    resource: str
    texture: str
    polygon: Polygon


@_dc.dataclass(frozen=True)
class ResourceRow:
    """The census of one admitted resource (§42 (3))."""

    resource: str
    texture: str
    placements: int
    bodies: int
    area_m2: float
    layer_group: str
    layer_offset: int
    #: what the pack authored, BEFORE the pads took their share (§42 (1)):
    #: the number RULINGS 13cu counted (HECA Concrete_Polygon_1: 29 /
    #: 580,331 m2)
    raw_bodies: int = 0
    raw_area_m2: float = 0.0


@_dc.dataclass
class ObjectPavementReport:
    """What the draped read saw, admitted and refused."""

    resources_seen: int = 0          # unique resolved resources screened
    resources_admitted: int = 0
    placements: int = 0
    bodies: int = 0
    area_m2: float = 0.0
    #: bodies (and m²) the building pads took back — §42 (1) "pads win"
    pad_clipped_bodies: int = 0
    pad_clipped_m2: float = 0.0
    rows: list[ResourceRow] = _dc.field(default_factory=list)
    #: refusal reason -> resources refused for it
    refused: dict[str, int] = _dc.field(default_factory=dict)

    def line(self) -> str:
        if not self.bodies and not self.resources_seen:
            return ""
        head = (f"object_pavements {self.bodies} bodies / {self.area_m2:,.0f} m2 "
                f"from {self.resources_admitted} of {self.resources_seen} "
                f"draped resource(s)")
        if self.pad_clipped_bodies:
            head += (f"; pads took {self.pad_clipped_m2:,.0f} m2 from "
                     f"{self.pad_clipped_bodies} body(ies)")
        return head

    def resource_lines(self) -> list[str]:
        return [f"    {r.resource}  [{r.texture or 'no texture'}] "
                f"{r.bodies} body(ies) / {r.area_m2:,.0f} m2 "
                f"(authored {r.raw_bodies} / {r.raw_area_m2:,.0f} m2; "
                f"layer {r.layer_group}+{r.layer_offset}, "
                f"{r.placements} placement(s))"
                for r in self.rows]


def header_facts(path: str) -> tuple[tuple[str, int] | None, str]:
    """``((layer group, offset) | None, draped texture)`` read from the
    file HEADER — the bytes before the first geometry line.  This is the
    whole pre-screen: a resource with no pavement draped layer group is
    never parsed."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(_HEADER_BYTES)
    except OSError:
        return None, ""
    group: tuple[str, int] | None = None
    texture = ""
    for raw in head.split(b"\n"):
        toks = raw.strip().split()
        if not toks:
            continue
        kw = toks[0]
        if kw in _GEOMETRY_KEYWORDS:
            break
        if kw == b"ATTR_layer_group_draped" and len(toks) >= 2:
            try:
                off = int(toks[2]) if len(toks) >= 3 else 0
            except ValueError:
                off = 0
            group = (toks[1].decode("ascii", "replace").lower(), off)
        elif kw == b"TEXTURE_DRAPED" and len(toks) >= 2:
            texture = toks[1].decode("utf-8", "replace")
    return group, texture


def draped_footprint(geom: _obj8.ObjGeometry, y_tol_m: float):
    """The union of an object's DRAPED triangles in its own plan frame
    ``(x, z)``, or ``None`` when it has no draped triangle or a draped
    vertex stands further than ``y_tol_m`` off Y = 0 (a draped skirt
    authored above the ground is not a ground polygon).

    An object's SOLID geometry is not read here and does not disqualify
    it: a placement that is both a solid body and a draped apron is a pad
    AND a source, and the two never double-count because the pads are
    subtracted from the bodies (§42 (1), ``read_object_pavements``).
    This is where v1's ground-paint reader stopped
    (``dsf_reader._is_pavement_object`` refuses any solid triangle)."""
    if not geom.draped.shape[0]:
        return None
    v = geom.vertices
    ys = v[geom.draped.reshape(-1), 1]
    if not ys.size or float(abs(ys).max()) > y_tol_m:
        return None
    tris = v[geom.draped][:, :, [0, 2]]
    # The triangles are built and dissolved IN BULK.  A draped page is a
    # TRIANGULATION — the triangles tile their footprint and do not
    # overlap — so ``coverage_union_all`` dissolves them by their shared
    # edges instead of intersecting every pair: measured over HECA's
    # eight pages (379-2,000 triangles each) 0.34 s -> 0.23 s for the
    # same eight areas to the square metre.  A page whose triangles are
    # NOT a clean coverage (an exporter's T-vertices, a self-overlap)
    # makes the coverage union refuse or return an invalid geometry, and
    # the general union does the work.
    rings = np.concatenate([tris, tris[:, :1, :]], axis=1)
    polys = shapely.polygons(shapely.linearrings(
        rings.reshape(-1, 2),
        indices=np.repeat(np.arange(rings.shape[0]), 4)))
    polys = polys[shapely.is_valid(polys) & (shapely.area(polys) > 0.0)]
    if not polys.size:
        return None
    try:
        u = shapely.coverage_union_all(polys)
        if not u.is_valid:
            raise ValueError("not a coverage")
    except Exception:
        u = unary_union(list(polys))
    if not u.is_valid:
        u = u.buffer(0)
    return None if u.is_empty else u


def _ground_plane_candidate(path: str, y_tol_m: float) -> bool:
    """The §42 (1b) pre-screen, streamed: ``False`` at the FIRST vertex
    standing more than ``y_tol_m`` off Y = 0 (a building says so in its
    first few ``VT`` lines, so almost every resource is refused within
    one read block), else whether the file says ``ATTR_hard`` anywhere.
    Only a candidate is parsed."""
    hard = False
    try:
        with open(path, "rb") as fh:
            for raw in fh:
                if raw.startswith(b"VT"):
                    toks = raw.split()
                    try:
                        if abs(float(toks[2])) > y_tol_m:
                            return False
                    except (IndexError, ValueError):
                        return False
                elif not hard and raw.startswith(b"ATTR_hard"):
                    hard = True
    except OSError:
        return False
    return hard


def hard_plane_footprint(geom: _obj8.ObjGeometry, y_tol_m: float):
    """§42 (1b) THE HARD GROUND PLANE: the union of ALL of an object's
    triangles in its own plan frame when every one of them stands within
    ``y_tol_m`` of Y = 0 and at least one solid triangle is ``ATTR_hard``
    — else ``None``.

    A pack that authors its apron as a SOLID zero-thickness hard plane
    (NLWF ``pavement/vele_apron.obj``: no ``ATTR_layer_group_draped``,
    every vertex at Y = 0, 73 of 79 triangles hard) declares no draped
    layer group, so the §42 (1) amended gate reads it as a shadow.  It is
    not one: a shadow is not hard, and X-Plane rolls aircraft on a hard
    surface.  Anything with a vertex off the ground (a building floor
    with walls, a deck) is not a plane and stays the pad path's."""
    if not geom.solid.shape[0] or not bool((geom.hardness != 0).any()):
        return None
    tris = (np.concatenate([geom.solid, geom.draped])
            if geom.draped.shape[0] else geom.solid)
    ys = geom.vertices[tris.reshape(-1), 1]
    if not ys.size or float(abs(ys).max()) > y_tol_m:
        return None
    return draped_footprint(_dc.replace(geom, draped=tris), y_tol_m)


def read_object_pavements(placements: _t.Sequence[Placement], law,
                          pad_union=None
                          ) -> tuple[list[DrapedBody], ObjectPavementReport]:
    """Every object-pavement BODY of a pack's placements, in the airport
    frame, and the census.  ``pad_union`` is the union of the solid
    objects' ``building`` pads: §42 (1) "pads win where they overlap", so
    it is subtracted from each body before it is split.

    Each resource is screened by its header and parsed AT MOST ONCE; the
    footprint is unioned once per RESOURCE, in the object's own frame, and
    only the placement affine is paid per placement (the memoisation
    RULINGS 2026-09-13bp (i) made law for the structure reads)."""
    lw = law.tables.structures.load
    rep = ObjectPavementReport()
    groups = frozenset(g.lower() for g in lw.object_pavement_layer_groups)
    tokens = tuple(t.lower() for t in lw.object_pavement_skip_tokens)

    def refuse(reason: str) -> None:
        rep.refused[reason] = rep.refused.get(reason, 0) + 1

    # ── per RESOURCE: the header screen, then one parse and one union ──
    footprints: dict[str, tuple[object, str, tuple[str, int]]] = {}
    seen: set[str] = set()
    for pl in placements:
        path = pl.resolved_path
        if not path or path in seen:
            continue
        seen.add(path)
        rep.resources_seen += 1
        base = os.path.basename(pl.def_path).lower()
        if any(t in base for t in tokens):
            refuse("decorative name")
            continue
        group, texture = header_facts(path)
        if group is None:
            # §42 (1b): a HARD ground plane declares itself by being one
            u = None
            if (lw.object_pavement_hard_planes
                    and _ground_plane_candidate(path, lw.draped_y_tol_m)):
                try:
                    u = hard_plane_footprint(_obj8.parse_obj8(path),
                                             lw.draped_y_tol_m)
                except (OSError, ValueError):
                    u = None
            if u is None:
                refuse("no draped layer group")
                continue
            if u.area < lw.object_pavement_min_m2:
                refuse(f"under {lw.object_pavement_min_m2:g} m2")
                continue
            footprints[path] = (u, texture, ("hard_plane", 0))
            continue
        if group[0] not in groups:
            refuse(f"layer group {group[0]}")
            continue
        if group[1] > lw.object_pavement_max_layer_offset:
            refuse(f"layer offset +{group[1]} (an overlay)")
            continue
        try:
            geom = _obj8.parse_obj8(path)
        except (OSError, ValueError):
            refuse("unparsable")
            continue
        u = draped_footprint(geom, lw.draped_y_tol_m)
        if u is None:
            refuse("draped geometry off Y = 0")
            continue
        if u.area < lw.object_pavement_min_m2:
            refuse(f"under {lw.object_pavement_min_m2:g} m2")
            continue
        footprints[path] = (u, texture, group)

    # ── per PLACEMENT: the affine, the pads, the disjoint bodies ───────
    out: list[DrapedBody] = []
    rows: dict[str, ResourceRow] = {}
    for pl in placements:
        got = footprints.get(pl.resolved_path or "")
        if got is None:
            continue
        u, texture, group = got
        # §51 (4) row 14 — ENTRY
        placed = _fe.enter([u], _obj8.placement_affine(pl.xy, pl.heading_deg),
                           _fe.quantum(law))[0]
        if placed is None:
            continue
        raw_n = sum(1 for g in getattr(placed, "geoms", (placed,))
                    if g.geom_type == "Polygon" and g.area > 0.0)
        raw_a = placed.area
        if pad_union is not None and not pad_union.is_empty:
            before = placed.area
            placed = placed.difference(pad_union)
            if placed.is_empty:
                rep.pad_clipped_bodies += 1
                rep.pad_clipped_m2 += before
                continue
            if before - placed.area > 1e-9:
                rep.pad_clipped_bodies += 1
                rep.pad_clipped_m2 += before - placed.area
        bodies = [g for g in getattr(placed, "geoms", (placed,))
                  if g.geom_type == "Polygon" and g.area > 0.0]
        n, area = 0, 0.0
        for body in bodies:
            out.append(DrapedBody(pl.id, pl.def_path, texture, body))
            n += 1
            area += body.area
        if not n:
            continue
        row = rows.get(pl.def_path)
        rows[pl.def_path] = ResourceRow(
            pl.def_path, texture,
            (row.placements if row else 0) + 1,
            (row.bodies if row else 0) + n,
            (row.area_m2 if row else 0.0) + area,
            group[0], group[1],
            (row.raw_bodies if row else 0) + raw_n,
            (row.raw_area_m2 if row else 0.0) + raw_a)
    rep.rows = sorted(rows.values(), key=lambda r: -r.area_m2)
    rep.resources_admitted = len(rep.rows)
    rep.placements = sum(r.placements for r in rep.rows)
    rep.bodies = len(out)
    rep.area_m2 = sum(r.area_m2 for r in rep.rows)
    return out, rep
