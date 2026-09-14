"""The Ortho4XP ``.osm`` patch adapter (plan §1 row 7; Appendix A §5).

WHAT THE MESH READS (``src/O4_Vector_Map.py:2639-2826``, Appendix A §5):
way ``altitude`` / ``node_altitudes`` / ``cst_alt_abs``, node ``alt_abs``
(overrides the way), ``role`` only for the seawall/flood admission, and
the sidecar key ``road_bridge_decks``.  ``ref``, ``shapeID`` and
``aeroway`` are NOT read by the mesh — they are census inputs.

THE PATCH v2 WRITES:
  * one closed way per face ring, tags ``aeroway`` (the role register),
    ``role``, ``ref``, ``shapeID`` (= face id), ``code_letter`` /
    ``code_number`` where the face carries a class, ``o4_single_poly=1``
    on runway rings (the census's station-scoped lateral law, user
    2026-07-08), node ``alt_abs`` per vertex;
  * one closed way per UNCOVERED HOLE, tagged ``o4_feature=gap_interior_ring``
    exactly as v1 so the census keeps it out of the ring laws and the
    mesh still constrains it (``include_patches`` inserts every closed
    way as a ring; ``_parse_osm`` routes the feature class to
    ``feature_out``).  A hole the faces INSIDE it already cover (by AREA,
    at ``emit.terrace.hole_cover_eps`` — the planar map's normal case:
    the hole IS the faces inside it) is NOT written: the ring would be a
    coincident duplicate carrying the parent's shapeID, which read in the
    sim as "shapeID 718 gap_interior_ring" over what is apron 730 (owner,
    OTHH 2026-09-04).  Neither is a hole narrower than
    ``emit.terrace.strip_min_width_m`` (RULINGS 2026-09-14g item 5: the
    92 %-covered, 1.6 m-wide HECA hole that shipped as a constrained ring
    across ``service_road:route4``).  A hole that is neither KEEPS its
    ring — a real void is never lost;
  * one closed way per STRUCTURE RIM (``emit.graded.RIM_KIND``; RULINGS
    2026-09-06b (1)): the void face's exterior at the ground, tagged
    ``o4_feature=structure_rim`` with the structure's ``ref`` — a
    constrained ring the mesh makes the wall up to (no wall face);
  * one closed way per BANK FOOT ring (``emit.bank.BANK_KIND``; owner
    RULINGS 2026-09-09e, spec §9), tagged ``o4_feature=bank_foot``: the
    ring ON THE DEM outside every patch-boundary ring, which the mesh
    triangulates the 1:3 bank up to (no vertex between them).  Role-less
    articulation geometry, skipped by both censuses;
  * one open way per ``runway_profile`` breakline tagged
    ``o4_feature=crown_spine`` — the ridge the census's ``runway_crown``
    reader measures the declared drops against (a ``DUMMY`` constrained
    line in the mesh; its chords are already ring edges of the runway
    halves, so the mesh's colinear re-dicing folds it);
  * node ids: ONE node per surface vertex — a coordinate is ONE node
    (the stacked-nodes family is impossible by construction);
  * lat/lon at ``identity_dp``; ``alt_abs`` is the surface's ONE
    quantisation (``GradedSurface`` z at the materiality precision).

THE SIDECAR (``<patch>.axes.json``) carries ONLY the census inputs v2
has, keys ⊆ :data:`SIDECAR_KEYS` (Appendix A §5): ``ruleset``; ``axes``
(every published centreline: ``[[lat, lon]…], cL, cT, ordinal,
is_service`` — the transverse walk and the spine membership);
``stretches`` (every taxi centreline STRETCH with its cap and letter,
RULINGS 2026-09-04t-3 — the per-stretch pair law v2 verify re-composes);
``crown_drops`` (``[lat, lon, drop]`` per runway-family vertex);
``airside_no_step_edges`` (``{a, b, budget_m}`` — the pairs the solver
priced, the census prices the same list); the always-empty
``terrace_joints`` / ``basin_facilities`` / ``road_bridge_decks``
(v2 has none: the mesh reads the last).  Nothing else: v1's 24 MB SPJC
sidecar was instrument-only (Appendix B §1).

The v1 census (``tools/harness/census.py``) is the ORACLE over this
output until ``verify/`` is proven equal on three airports (plan §1
``verify`` row).
"""
from __future__ import annotations

import dataclasses as _dc
import json
import math
import typing as _t
from pathlib import Path
from xml.sax.saxutils import escape

import shapely

from ..law.model import Law
from ..law.tables import role_cap
from .graded import z_decimals
from .surface import GradedSurface

__all__ = ["SIDECAR_KEYS", "PatchPaths", "write_patch", "render_patch",
           "render_sidecar", "tile_of_face", "write_tile_pieces",
           "WeldReport", "shore_edges_of", "weld_to_shore", "merge_sub_spacing"]

#: A lat/lon pair, as everything emit-side spells it.
LL_T = _t.Tuple[float, float]

#: THE SEAM-BAND TEST (§38 (3)/13an (c)) and the shore weld's own metric
#: (§39 (1)): metres per degree of latitude in the emitted frame.
_M_PER_DEG_LAT = 111_320.0

#: The sidecar keys v2 publishes, and nothing else (Appendix A §5).
SIDECAR_KEYS: tuple[str, ...] = (
    "ruleset", "axes", "routes", "runway_end_skirt", "crown_drops",
    # §40 (2) as amended (owner RULINGS 2026-09-13dd): each runway's own
    # axis and HALF WIDTH, and the shoulder cap — the line beyond which a
    # runway-family vertex is a SHOULDER vertex and is priced at
    # ``shoulder_transverse_max`` instead of the runway's 1.5 %.  The v1
    # census reads the line the generator drew and never re-derives it
    # from the runway RINGS, which a shoulder fattens.
    "runway_axes", "shoulder_transverse_max",
    "road_bridge_decks", "terrace_joints", "basin_facilities",
    "road_coverage_join",  # §37 (9) (RULINGS 2026-09-13be): the core ribbon's altitude at each coverage exit
    "road_route_frame",  # §37 (7) (RULINGS 2026-09-13av): the road pair law's route frame (``pipeline/publication``)
    "airside_no_step_edges", "pad_pavement_no_step_edges", "mesh_edges",
    "pair_caps", "seam_pins", "station_caps",
    "pair_caps", "seam_pins", "station_caps", "stretches",
    # §38 (3)/(5) (owner RULINGS 2026-09-13ah/13an): the tile-seam band's
    # own half width, so the census's ``bank_across_seam`` reads "inside
    # the band" from the law the BUILD ran under and never from a
    # constant of its own
    "seam_half_width_m",
    "tunnel_objects",   # RULINGS 2026-09-05k-1: the object corridors (``pipeline/publication.tunnel_objects``)
    "taxi_route_pairs",  # RULINGS 2026-09-05ab: taxi within-shape pairs priced over the centreline route (``taxi.taxi_pair_routes``)
    "face_holes",  # RULINGS 2026-09-05ae(1): each face's holes by shapeID — the oracle's visibility polygon (``publication.face_holes_ll``)
    "design",         # RULINGS 2026-09-08t/v: the design surface's residual per family (replaces ``law_tiers``)
    "design_target",  # RULINGS 2026-09-08t/v: one record per law row the surface missed — the census's ``design_target`` heading
    "pad_relief",  # owner RULINGS 2026-09-11j (spec §11a (2)/(4)): per pad vertex, the metres the terrain stands above the pad's LEVEL — the relief a body's authored feet ask for.  The pad's flatness READER measures on the level plane with these subtracted (``verify/pads.relief_offsets``); without them every relief pad reads as a plane-residual row.
    "eat_rects",  # spec §36 (owner RULINGS 2026-09-13j item 2): one record per ACCEPTED end-around-taxiway rect — end, runway, the regulation value and the vertices it pinned (``pipeline/publication`` off the final constraint set).  The census's ``eat_ceiling`` family prices exactly this list, so a vertex the rect law withdrew is never reported (lockstep)
    # §39 (1)/(2) THE HAIRLINE LAW (owner RULINGS 2026-09-13bk): the
    # FOREIGN constrained water edges the shore weld ran against, as
    # ``[lat1, lon1, lat2, lon2]`` — the population the ``hairline_pair``
    # census prices every emitted ring edge against, so the instrument and
    # the law read one water witness and never two.
    "shore_edges",
    "apron_tier",  # RULINGS 2026-09-06w: the tiered apron law priced (preferred / max / fan) — the oracle's cap for apron rows (``publication.apron_tier``)
    "pad_cluster_mismatch",  # §16g (10) (3) (owner RULINGS 2026-09-14x): the CRITICAL defect set — a pad more than half claimed by two clusters, or a cluster that is more than half of two pads.  "Pads must match building clusters ... exactly"; empty is the bar (``pipeline/publication`` off ``constraints.cluster_pad.pad_cluster_mismatch``)
    "cluster_pads",  # §30 (4) (owner RULINGS 2026-09-13bj item 1): one record per TERMINAL CLUSTER — its members, the emitted `building` faces its footprint union stands on, the ONE level the solve gave that plane, and the apron vertices the reach targeted (with how many reached it).  The object stage's §16g seats the cluster on this level (``pipeline/publication.cluster_pads``)
)

#: Feature class of a hole ring (v1 vocabulary the census and mesh read).
HOLE_FEATURE = "gap_interior_ring"
#: The structure rim's feature tag (a role-less closed way; the census
#: skips it as it skips the hole rings — ``check_grade.ROLE_LESS_FEATURE_CLASSES``).
RIM_FEATURE = "structure_rim"
#: THE BANK FOOT (``emit.bank.BANK_KIND``; owner RULINGS 2026-09-09e, spec
#: §9): the ring ON THE DEM outside a patch-boundary ring, a closed
#: constrained way the mesh triangulates the 1:3 bank up to.  Role-less
#: like the rim and for the same reason: it IS the terrain, it carries no
#: grade law, and the census skips it
#: (``check_grade.ROLE_LESS_FEATURE_CLASSES``).
BANK_FEATURE = "bank_foot"
#: Feature class of the runway ridge open way.
RIDGE_FEATURE = "crown_spine"
#: THE TERRAIN EDGE (owner RULINGS 2026-09-10b/10c; spec §19.3 C12): the
#: boundary an adjacent-ground ring was ENDED at — a rim road or a crest —
#: as a value-less open way over boundary vertices that already exist (the
#: ``crown_spine`` precedent: its chords are ring edges already, and the
#: mesh's colinear re-dicing folds them).  Role-less, census-skipped: it
#: records where the patch stops and the DEM's own slope takes over.
EDGE_FEATURE = "terrain_edge"
#: Breakline kinds emitted as open ways (the others are ring edges already).
_OPEN_WAY_KINDS = {"runway_profile": RIDGE_FEATURE,
                   "terrain_edge": EDGE_FEATURE}


@_dc.dataclass(frozen=True)
class PatchPaths:
    """Where a patch landed."""

    patch: Path
    sidecar: Path
    graded: Path
    ways: int
    nodes: int
    bytes_patch: int
    bytes_sidecar: int


def _fmt(v: float, dp: int) -> str:
    return f"{v:.{dp}f}"


def _q(v: object) -> str:
    """A single-quoted XML attribute — the v1 census's tag regex reads
    ``k='…' v='…'`` (single quotes) and nothing else."""
    return "'" + escape(str(v), {"'": "&apos;", '"': "&quot;"}) + "'"


def _hole_cover(surface: GradedSurface, law: Law):
    """``(hole ring ids) -> bool`` — is this hole ALREADY CONSTRAINED, so
    that emitting its ring would only duplicate what is there?

    RULINGS 2026-09-14g item 5.  Until 2026-09-14 the test was a ring-EDGE
    superset: the hole was suppressed only when every one of its edges was
    already an edge of some face ring (or of a structure rim).  That FAILS
    OPEN on a hole the inner faces cover by AREA but not edge-for-edge —
    HECA way -10231, hole 1 of ``cross_connector:pav115``, 29.5 m², 1.60 m
    wide, 92.3 % covered by three inner faces, shipped as a constrained
    ring straight across ``service_road:route4`` and two zone strips (the
    owner's item 5, RULINGS 2026-09-14c).

    So the test is by AREA — the faces INSIDE the hole (plus the structure
    RIMS, which are the void faces' own rings and are emitted as their own
    constrained ways) cover at least ``1 - emit.terrace.hole_cover_eps`` of
    it — and a hole NARROWER than ``emit.terrace.strip_min_width_m`` at its
    widest place is refused outright: a hairline ring carries no transition
    and every value it holds is the min-norm solution's (the §41 (4) and
    RULINGS 2026-09-10h arguments, in the emitted frame).

    THE RING-EDGE SUPERSET TEST IS KEPT BESIDE IT, as a second sufficient
    condition, deliberately: measured at HECA, dropping it EMITTED 9 new
    rings of 245,000 m2 (``primary_parallel:dsf:objpav93`` #4/#5/#6 and
    five more, holes 10k-66k m2 whose inner faces cover 72-100 % of them
    and whose edges are ring edges throughout).  Those are a DIFFERENT
    class from the owner's item 5 — the edge test suppressing a partly
    uncovered hole — and this rule was ruled to suppress MORE, never to
    ship more.  So the two tests are OR-ed: whatever was suppressed before
    still is, plus the area-covered and the hairline classes.

    A hole none of the three catches KEEPS its ring: a real void is never
    lost.  Faces with no holes never pay for any of this."""
    if not any(f.holes for f in surface.faces):
        return lambda h, host_id=None: False
    ring_edges: set[tuple[int, int]] = set()

    def _edges(cycle) -> set[tuple[int, int]]:
        n = len(cycle)
        return {(min(cycle[i], cycle[(i + 1) % n]),
                 max(cycle[i], cycle[(i + 1) % n])) for i in range(n)}
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from shapely.strtree import STRtree
    from .graded import RIM_KIND

    eps = float(law.tables.emit.terrace.hole_cover_eps)
    width_min = float(law.tables.emit.terrace.strip_min_width_m)
    my, mx = _local_metres(surface.origin)
    xy = {v.id: (v.ll[1] * mx, v.ll[0] * my) for v in surface.vertices}

    def poly(ids) -> "Polygon | None":
        pts = [xy[i] for i in ids if i in xy]
        if len(pts) < 3:
            return None
        try:
            p = Polygon(pts)
            if not p.is_valid:
                p = p.buffer(0)
        except Exception:                                  # pragma: no cover
            return None
        return None if (p.is_empty or p.geom_type != "Polygon"
                        or p.area <= 0.0) else p

    inners: list = []
    for f in surface.faces:
        ring_edges.update(_edges(f.ring))
        p = poly(f.ring)
        if p is not None:
            inners.append((f.id, p))
    for b in surface.breaklines:
        if b.kind != RIM_KIND or len(b.vertices) < 3:
            continue
        # the rim IS a void face's exterior, emitted as its own constrained
        # ring: a pavement hole it fills is covered (the pre-2026-09-14 edge
        # test carried this case and the area test must carry it too)
        run = (b.vertices[:-1] if b.vertices[0] == b.vertices[-1]
               else b.vertices)
        ring_edges.update(_edges(run))
        p = poly(run)
        if p is not None:
            inners.append((None, p))
    tree = STRtree([p for _i, p in inners]) if inners else None

    def covered(h, host_id=None) -> bool:
        if _edges(h) <= ring_edges:
            return True                  # every edge already constrained
        hp = poly(h)
        if hp is None:
            return True                  # degenerate: no ring to emit
        if 2.0 * float(shapely.maximum_inscribed_circle(hp, 0.01).length) \
                < width_min:
            return True                  # the hairline class
        if tree is None:
            return False
        inside = []
        for j in tree.query(hp):
            fid, p = inners[int(j)]
            # a face is INSIDE the hole, never the host whose hole it is:
            # the host's own ring polygon (its holes filled) contains the
            # hole entirely, so an overlap test alone would call every
            # hole of a thin host covered by its host
            if fid is not None and fid == host_id:
                continue
            if p.area > hp.area * 1.001:
                continue
            try:
                if hp.contains(p.representative_point()):
                    inside.append(p)
            except Exception:                              # pragma: no cover
                continue
        if not inside:
            return False
        try:
            return unary_union(inside).intersection(hp).area >= (1.0 - eps) * hp.area
        except Exception:                                  # pragma: no cover
            return False

    return covered


def render_patch(surface: GradedSurface, law: Law,
                 header: _t.Mapping[str, str] | None = None,
                 face_tags: _t.Mapping[int, _t.Mapping[str, str]] | None = None
                 ) -> tuple[str, int, int]:
    """``(text, ways, nodes)`` — the ``.osm`` document.  ``face_tags``:
    extra way tags per face id (``o4_grade_law_cap`` on a road bound to a
    stricter contiguous class)."""
    dp = surface.identity_dp
    zdp = z_decimals(law)
    reg = law.tables.precedence.roles
    lines: list[str] = ["<?xml version='1.0' encoding='UTF-8'?>"]
    attrs = {"version": "0.6", "upload": "false",
             "generator": "auto_patch_v2", "o4_engine": "auto_patch_v2/M2",
             "o4_ruleset": surface.ruleset, "o4_icao": surface.icao}
    attrs.update(header or {})
    lines.append("<osm " + " ".join(f"{k}={_q(v)}"
                                    for k, v in attrs.items()) + ">")
    nid_of: dict[int, int] = {}
    for v in surface.vertices:
        nid = -(v.id + 1)
        nid_of[v.id] = nid
        lines.append(f"  <node id='{nid}' action='modify' visible='true' "
                     f"lat='{_fmt(v.ll[0], dp)}' lon='{_fmt(v.ll[1], dp)}'>")
        lines.append(f"    <tag k='alt_abs' v='{_fmt(v.z, zdp)}' />")
        lines.append("  </node>")
    wid = -10000
    n_ways = 0

    def way(ids: _t.Sequence[int], tags: list[tuple[str, str]], closed: bool) -> None:
        nonlocal wid, n_ways
        wid -= 1
        n_ways += 1
        lines.append(f"  <way id='{wid}' action='modify' visible='true'>")
        seq = list(ids) + ([ids[0]] if closed else [])
        for v in seq:
            lines.append(f"    <nd ref='{nid_of[v]}' />")
        for k, val in tags:
            lines.append(f"    <tag k={_q(k)} v={_q(val)} />")
        lines.append("  </way>")

    from .graded import RIM_KIND
    hole_cover = _hole_cover(surface, law)

    for f in surface.faces:
        spec = reg.get(f.role)
        extra = dict((face_tags or {}).get(f.id) or {})
        role = f.role
        if spec is not None and spec.oracle_role is not None:
            # THE ORACLE ALIAS (precedence.toml ``oracle_role``): the v1
            # census reads ``role`` from its own register, so an aliased
            # role is written under the name it judges, ``class`` names
            # the v2 role, and ``o4_grade_law_cap`` carries the v2 cap —
            # which the census composes as a MINIMUM with the alias's
            # cap, so it prices exactly the v2 table.
            role = spec.oracle_role
            extra["class"] = f.role
            rc = role_cap(law, f.role, f.code_number, f.code_letter)
            # THE ORACLE'S OWN CAP (``oracle_cap``, RULINGS 2026-09-08u (2)):
            # a structure ramp is priced in the PAIR frame at the ramp law's
            # ceiling, not at its face's longitudinal cap — the oracle reads
            # a 2.5 m-wide ramp's ring diagonals, which the face law does
            # not bound (measured: 181 lawful OTHH wall-corridor rows at
            # 8.2 % against the service_road alias's 8 %).  v2 verify keeps
            # the face cap and stays the stricter instrument.
            longitudinal = spec.oracle_cap if spec.oracle_cap is not None else \
                (None if rc is None else rc.longitudinal)
            if longitudinal is not None:
                prior = extra.get("o4_grade_law_cap")
                cap = longitudinal if prior is None else min(longitudinal, float(prior))
                extra["o4_grade_law_cap"] = f"{cap:g}"
            if spec.oracle_law is not None:
                # THE ORACLE'S LAW OVERRIDE (``oracle_law``): the v1 census
                # prices ``o4_grade_law=<law>`` at ROLE_GRADE_LIMITS[<law>]
                # composed with the cap tag — a door ramp under tunnel_ramp
                # reads service_road's 8 % (spec othh-terminal-ramps §4)
                extra["o4_grade_law"] = spec.oracle_law
        tags = [("aeroway", spec.aeroway if spec else "apron"),
                ("ref", f.ref), ("role", role), ("shapeID", str(f.id))]
        if f.code_letter:
            tags.append(("code_letter", f.code_letter))
        if f.code_number is not None:
            tags.append(("code_number", str(f.code_number)))
        if f.role == "runway":
            tags.append(("o4_single_poly", "1"))
        for k, val in sorted(extra.items()):
            tags.append((k, val))
        way(f.ring, tags, True)
        for h in f.holes:
            if hole_cover(h, f.id):
                continue     # covered, or a hairline that can carry nothing
            way(h, [("o4_feature", HOLE_FEATURE), ("shapeID", str(f.id))], True)
    from .bank import BANK_KIND
    for b in surface.breaklines:
        if b.kind == BANK_KIND and len(b.vertices) >= 3:
            # THE BANK FOOT (09e): closed where the whole ring is on this
            # tile piece, an open constrained chain where it is split
            closed = b.vertices[0] == b.vertices[-1]
            way(b.vertices[:-1] if closed else b.vertices,
                [("o4_feature", BANK_FEATURE), ("ref", b.ref)], closed)
            continue
        if b.kind == RIM_KIND and len(b.vertices) >= 3:
            # the rim: closed where the run is the whole ring (the first
            # vertex repeated), an open constrained chain where a tile
            # piece holds only part of it
            closed = b.vertices[0] == b.vertices[-1]
            way(b.vertices[:-1] if closed else b.vertices,
                [("o4_feature", RIM_FEATURE), ("ref", b.ref.split("@")[0])], closed)
            continue
        feat = _OPEN_WAY_KINDS.get(b.kind)
        if feat is None or len(b.vertices) < 2:
            continue
        way(b.vertices, [("o4_feature", feat), ("ref", b.ref)], False)
    lines.append("</osm>")
    return "\n".join(lines) + "\n", n_ways, len(surface.vertices)


#: §39 (1) THE HAIRLINE LAW — the shore weld's report.
@_dc.dataclass
class WeldReport:
    """What :func:`weld_to_shore` did (one line in the build log)."""

    shore_edges: int = 0
    candidates: int = 0
    snapped: int = 0
    dropped: int = 0
    projected: int = 0
    stranded: int = 0
    merged: int = 0
    worst_mm_before: float = 0.0
    worst_at: tuple[float, float] | None = None

    def line(self, icao: str) -> str:
        at = "" if self.worst_at is None else \
            f" (worst {self.worst_mm_before:.4f} mm at " \
            f"{self.worst_at[0]:.7f},{self.worst_at[1]:.7f})"
        return (f"[{icao}] shore weld (§39 (1)): {self.shore_edges} foreign water "
                f"edges, {self.candidates} vertices inside the spacing — "
                f"{self.snapped} snapped onto a water vertex, {self.dropped} "
                f"dropped off the shore line, {self.projected} projected onto "
                f"it, {self.stranded} left beside it; {self.merged} "
                f"sub-spacing segment(s) merged"
                + at)


def _local_metres(origin: LL_T) -> tuple[float, float]:
    """``(m per deg lat, m per deg lon)`` at ``origin`` — the LINEAR frame
    the mesh itself reasons in (``O4_Vector_Utils.scalx``: tile-relative
    degrees with the longitude axis scaled by ``cos(lat)``).  §39's whole
    point is that a straight line HERE is a straight line in the ``.poly``
    the mesh writes; a straight line in the tmerc metres frame is NOT."""
    lat0 = float(origin[0])
    return (_M_PER_DEG_LAT,
            _M_PER_DEG_LAT * max(math.cos(math.radians(lat0)), 1.0e-6))


def shore_edges_of(dem, surface: GradedSurface, pad_m: float = 5.0,
                   seawall: bool = True) -> list[tuple[LL_T, LL_T]]:
    """§39 (i) THE ONE WITNESS (owner RULINGS 2026-09-13cg): the FOREIGN
    constrained edges THE MESH WILL CONSTRAIN near this patch, in lat/lon.

    Round 1 read ``dem.water(...)`` — ``TileWater``, whose sea limb is
    :func:`sea_area_from_coastline`'s POLYGONISATION.  That is the right
    witness for "is this vertex wet" and the wrong one for a hairline: the
    mesh constrains ``include_sea``'s raw coastline LINES instead, and the
    two differ by micrometres.  VMMC measured the cost — a ``bank_foot``
    vertex left 0.0025 mm from the SEA line, slenderness 4,004,066, box A's
    slivers 137,718 -> 296,037 (13cg).  So the sea and inland limbs now come
    from ``O4_Vector_Map.cached_constrained_shore`` through
    ``dem.shore(...)``: ONE derivation, shared with the mesh, cache-only.

    THE SEAWALL LIMB joins them (``seawall=True``): ``insert_seawalls``
    writes a ``SEAWALL_MARKER`` breakline 0.5 m outside the patch coverage
    wherever it meets water (``O4_Vector_Map.seawall_breaklines``), and six
    VMMC bank stations sat 481-501 mm from it — astride the identity bar,
    invisible to a weld that could not see the wall.  It is derived here
    from the SAME function, over this surface's own face union.

    Only edges within ``pad_m`` of the surface's bounding box are
    returned: nothing further out can be inside the identity spacing.
    ``dem`` without the accessor falls back to ``dem.water(...)``'s
    polygons, which is what a pre-13cg caller had.
    """
    lats = [v.ll[0] for v in surface.vertices]
    lons = [v.ll[1] for v in surface.vertices]
    if not lats:
        return []
    mlat, mlon = _local_metres(surface.origin)
    dla, dlo = pad_m / mlat, pad_m / mlon
    la0, la1 = min(lats) - dla, max(lats) + dla
    lo0, lo1 = min(lons) - dlo, max(lons) + dlo
    tiles = sorted({(int(math.floor(la)), int(math.floor(lo)))
                    for la, lo in zip(lats, lons)})
    chains: list[list[LL_T]] = []
    shore_fn = getattr(dem, "shore", None)
    water_fn = getattr(dem, "water", None)
    for (tla, tlo) in tiles:
        if callable(shore_fn):
            try:
                lines = shore_fn(tla, tlo)
            except Exception:                            # pragma: no cover
                lines = []
            for coords in lines or ():
                chains.append([(float(c[1]) + tla, float(c[0]) + tlo)
                               for c in coords])
            if lines:
                continue
        if not callable(water_fn):
            continue
        try:
            w = water_fn(tla, tlo)
        except Exception:                                # pragma: no cover
            w = None
        for poly in (getattr(w, "polys", None) or ()):
            for ring in [poly.exterior, *poly.interiors]:
                chains.append([(c[1] + w.lat, c[0] + w.lon)
                               for c in ring.coords])
    if seawall:
        chains.extend(_seawall_chains(surface, chains, tiles))
    out: list[tuple[LL_T, LL_T]] = []
    seen: set[tuple[LL_T, LL_T]] = set()
    for chain in chains:
        for i in range(len(chain) - 1):
            a, b = chain[i], chain[i + 1]
            if a == b:
                continue
            if max(a[0], b[0]) < la0 or min(a[0], b[0]) > la1:
                continue
            if max(a[1], b[1]) < lo0 or min(a[1], b[1]) > lo1:
                continue
            key = (a, b) if a <= b else (b, a)
            if key in seen:
                continue
            seen.add(key)
            out.append((a, b))
    return out


def _seawall_chains(surface: GradedSurface, water_chains: list[list[LL_T]],
                    tiles: list[tuple[int, int]]) -> list[list[LL_T]]:
    """THE SEAWALL LIMB (§39 (i)): ``O4_Vector_Map.seawall_breaklines``
    over this surface's own face union, so the wall the mesh will insert
    is a foreign edge the weld can see.  ``insert_seawalls`` runs the same
    function on ``include_patches``' role-scoped union; the full face union
    used here is its documented superset (``seawall_admission_area``'s own
    fallback), which can only place the wall FURTHER out — never nearer,
    so no station is left astride the bar by this approximation.  Any
    failure returns nothing: the wall is a refinement of a refinement."""
    try:
        from shapely.geometry import MultiLineString, Polygon
        from shapely.ops import unary_union
        import O4_Vector_Map as VMAP
    except Exception:                                    # pragma: no cover
        return []
    if not tiles or not water_chains:
        return []
    tla, tlo = tiles[0]
    vs = {v.id: v for v in surface.vertices}
    faces = []
    for f in surface.faces:
        pts = [(vs[i].ll[1] - tlo, vs[i].ll[0] - tla) for i in f.ring
               if i in vs]
        if len(pts) >= 3:
            try:
                poly = Polygon(pts)
                if poly.is_valid and not poly.is_empty:
                    faces.append(poly)
            except Exception:                            # pragma: no cover
                continue
    if not faces:
        return []
    water_lines = []
    for chain in water_chains:
        if len(chain) >= 2:
            water_lines.append([(lo - tlo, la - tla) for la, lo in chain])
    try:
        coverage = unary_union(faces)
        water_area = MultiLineString(water_lines).buffer(0.0)
        if water_area.is_empty:
            water_area = MultiLineString(water_lines)
        walls = VMAP.seawall_breaklines(coverage, water_area, tla)
    except Exception:                                    # pragma: no cover
        return []
    return [[(float(c[1]) + tla, float(c[0]) + tlo) for c in coords]
            for coords in (walls or ()) if len(coords) >= 2]


def _seg_reading(p: tuple[float, float], a: tuple[float, float],
                 b: tuple[float, float]) -> tuple[float, float]:
    """``(distance, parameter)`` of ``p`` against segment ``a→b``, planar."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L <= 0.0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy)), t


def weld_to_shore(surface: GradedSurface, law: Law,
                  edges: _t.Sequence[tuple[LL_T, LL_T]],
                  report: "WeldReport | None" = None) -> GradedSurface:
    """§39 (1) NO EDGE BESIDE ANOTHER — the SHORE WELD, at the one site
    every emitted ring passes through.

    THE DEFECT IT REMOVES (owner RULINGS 2026-09-13bk; measured here at
    LEMD 40.4762773, −3.5456742): the bank foot ring follows the water
    line because ``emit/bank.py`` cuts the banked region BY the water, so
    its vertices ARE the water polygon's — but the ring is then chord-split
    at ``bank_chord_max_m`` in the FRAME (tmerc metres), while the mesh
    constrains the water edge as a straight segment in tile-relative
    DEGREES.  A straight line in one frame is not a straight line in the
    other: over a 74.5 m water edge the two separate by 0.0676 mm in the
    middle while sharing both endpoints exactly.  Triangle4XP must recover
    both segments and fills that hairline wedge with a Steiner cascade —
    2,301,676 triangles under 0.1 m² and a tile X-Plane would not load.

    THE LAW, in order, for every emitted vertex within
    ``emit.identity.min_distinct_spacing_m`` of a foreign edge:

    * within the spacing of one of that edge's OWN VERTICES → SNAPPED onto
      it exactly (the 11-dp identity join then makes them ONE node: water
      is a datum and already carries the vertex);
    * otherwise standing in the INTERIOR of the edge, with both of its
      neighbours on the shore too → DROPPED: it is a chord split of a line
      the water already constrains, and the segment it split survives as
      the water's own.  Only a vertex belonging to exactly ONE emitted
      sequence is dropped — a shared vertex would leave a T-junction.
    * otherwise → left where it is and COUNTED as ``stranded``, so a
      genuine near-parallel run is reported rather than silently moved
      half a metre.  The ``hairline_pair`` census and the mesh pre-flight
      price exactly what is left.
    """
    rep = report if report is not None else WeldReport()
    rep.shore_edges = len(edges)
    if not edges or not surface.vertices:
        return surface
    spacing = float(law.tables.emit.identity.min_distinct_spacing_m)
    dp = int(surface.identity_dp)
    mlat, mlon = _local_metres(surface.origin)
    la0, lo0 = float(surface.origin[0]), float(surface.origin[1])

    def xy(ll: _t.Sequence[float]) -> tuple[float, float]:
        return ((float(ll[1]) - lo0) * mlon, (float(ll[0]) - la0) * mlat)

    segs = [(xy(a), xy(b), a, b) for a, b in edges]
    # the foreign VERTICES, keyed at the identity precision
    fverts: dict[tuple[float, float], LL_T] = {}
    for _, _, a, b in segs:
        for q in (a, b):
            fverts.setdefault((round(q[0], dp), round(q[1], dp)), q)
    fxy = [xy(q) for q in fverts.values()]
    fll = list(fverts.values())

    from scipy.spatial import cKDTree
    vtree = cKDTree(fxy) if fxy else None
    # a coarse cell index over the segments: spacing is 0.5 m, cells 8 m
    CELL = 8.0
    grid: dict[tuple[int, int], list[int]] = {}
    for i, (p, q, _, _) in enumerate(segs):
        for cx in range(int(min(p[0], q[0]) // CELL), int(max(p[0], q[0]) // CELL) + 1):
            for cy in range(int(min(p[1], q[1]) // CELL), int(max(p[1], q[1]) // CELL) + 1):
                grid.setdefault((cx, cy), []).append(i)

    new_ll: dict[int, LL_T] = {}
    on_shore: set[int] = set()          # within the spacing of a foreign edge
    interior: set[int] = set()          # ... of its INTERIOR, not its vertices
    nearest_seg: dict[int, int] = {}    # ... and WHICH edge, for the projection
    for v in surface.vertices:
        p = xy(v.ll)
        cx, cy = int(p[0] // CELL), int(p[1] // CELL)
        cand: set[int] = set()
        for ax in (cx - 1, cx, cx + 1):
            for ay in (cy - 1, cy, cy + 1):
                cand.update(grid.get((ax, ay), ()))
        if not cand:
            continue
        best = min((_seg_reading(p, segs[i][0], segs[i][1])[0], i) for i in cand)
        if best[0] > spacing:
            continue
        rep.candidates += 1
        on_shore.add(v.id)
        if best[0] * 1000.0 > rep.worst_mm_before:
            rep.worst_mm_before = best[0] * 1000.0
            rep.worst_at = (float(v.ll[0]), float(v.ll[1]))
        d_vert, j = (vtree.query(p) if vtree is not None else (1.0e9, -1))
        if d_vert <= spacing:
            q = fll[int(j)]
            if (round(v.ll[0], dp), round(v.ll[1], dp)) != (round(q[0], dp), round(q[1], dp)):
                new_ll[v.id] = (float(q[0]), float(q[1]))
                rep.snapped += 1
            continue
        interior.add(v.id)
        nearest_seg[v.id] = best[1]

    if not on_shore:
        return surface

    # how many emitted sequences each vertex belongs to: a vertex two rings
    # share cannot be dropped from one of them (a T-junction is the same
    # class of defect one dimension down)
    seqs: list[tuple[str, int, list[int]]] = []
    for f in surface.faces:
        seqs.append(("ring", f.id, list(f.ring)))
        for hi, h in enumerate(f.holes):
            seqs.append((f"hole{hi}", f.id, list(h)))
    for b in surface.breaklines:
        seqs.append(("break", b.id, list(b.vertices)))
    degree: dict[int, int] = {}
    for _, _, ids in seqs:
        for i in set(ids):
            degree[i] = degree.get(i, 0) + 1

    def prune(ids: list[int], closed: bool) -> list[int]:
        n = len(ids)
        if n < (4 if closed else 3):
            return ids
        out: list[int] = []
        for k, i in enumerate(ids):
            if i in interior and degree.get(i, 0) == 1:
                prv = ids[k - 1] if (closed or k > 0) else None
                nxt = ids[(k + 1) % n] if (closed or k + 1 < n) else None
                if prv in on_shore and nxt in on_shore:
                    rep.dropped += 1
                    continue
            out.append(i)
        if len(out) < (3 if closed else 2):
            return ids
        return out

    dropped_from: dict[tuple[str, int], list[int]] = {}
    for what, oid, ids in seqs:
        closed = what != "break"
        kept = prune(ids, closed)
        if len(kept) != len(ids):
            dropped_from[(what, oid)] = kept
    rep.stranded = sum(1 for i in interior
                       if any(i in ids for _, _, ids in seqs))
    # a dropped vertex is still counted stranded above only if it survived;
    # recompute against what the prune kept
    kept_any: set[int] = set()
    for what, oid, ids in seqs:
        kept_any.update(dropped_from.get((what, oid), ids))
    stranded = interior & kept_any
    # THE THIRD BRANCH (owner RULINGS 2026-09-13bt (5') / 13cg (i)): a
    # vertex that could be neither snapped onto a foreign vertex nor
    # dropped is PROJECTED ONTO the foreign edge and adopted as a point of
    # it.  It lands ON the line the mesh constrains, so the mesher splits
    # that segment there and no wedge exists — where standing 0.48 m
    # BESIDE it (VMMC's six seawall-adjacent stations, 481-501 mm) leaves
    # exactly the pair §39 forbids.  The projection is taken in the
    # emitted DEGREE frame, which is the frame the ``.poly`` is straight
    # in: taking it in the tmerc metres frame is the LEMD defect itself.
    vll = {v.id: v.ll for v in surface.vertices}
    for i in sorted(stranded):
        k = nearest_seg.get(i)
        if k is None:
            continue
        (ax, ay), (bx, by), a_ll, b_ll = segs[k]
        px, py = xy(vll[i])
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        if L <= 0.0:
            continue
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
        new_ll[i] = (a_ll[0] + (b_ll[0] - a_ll[0]) * t,
                     a_ll[1] + (b_ll[1] - a_ll[1]) * t)
        rep.projected += 1
    rep.stranded = len(stranded) - rep.projected

    if not new_ll and not dropped_from:
        return surface

    faces = []
    for f in surface.faces:
        ring = tuple(dropped_from.get(("ring", f.id), list(f.ring)))
        holes = tuple(tuple(dropped_from.get((f"hole{hi}", f.id), list(h)))
                      for hi, h in enumerate(f.holes))
        faces.append(_dc.replace(f, ring=ring, holes=holes)
                     if ring != f.ring or holes != f.holes else f)
    breaks = []
    for b in surface.breaklines:
        run = dropped_from.get(("break", b.id))
        breaks.append(_dc.replace(b, vertices=tuple(run)) if run is not None else b)
    live = {i for f in faces for i in f.ring} | \
        {i for f in faces for h in f.holes for i in h} | \
        {i for b in breaks for i in b.vertices}
    verts = tuple(_dc.replace(v, ll=new_ll[v.id]) if v.id in new_ll else v
                  for v in surface.vertices if v.id in live)
    return _dc.replace(surface, vertices=verts, faces=tuple(faces),
                       breaklines=tuple(breaks))


def merge_sub_spacing(surface: GradedSurface, law: Law,
                      report: "WeldReport | None" = None) -> GradedSurface:
    """§39 (iii) THE IDENTITY JOIN MERGES, IT NEVER WRITES, A SUB-SPACING
    SEGMENT (owner RULINGS 2026-09-13cg (iii)).

    ``emit.identity.min_distinct_spacing_m`` says two DISTINCT vertices are
    never closer than 0.5 m, and the emitter was writing them anyway:
    measured on the round-1 arms, LEMD 932 constrained segments under the
    spacing, KCLT 1,635, VMMC 1,631, the shortest **5.6 micrometres** at
    35.2153165, -80.9285365.  Every one is a segment Triangle4XP must
    recover and cascades off — KCLT's 2.7913 mm water sliver carried
    481,602 triangles under 0.1 m^2 (13bu) — and every one is the law's own
    identity join not having been applied.

    THE MERGE, at the one site the ring writer is: two vertices adjacent in
    an emitted sequence and closer than the spacing are ONE vertex.  The
    SENIOR keeps its coordinate and nothing moves: seniority is (1) the
    vertex more sequences share — merging away a junction would tear the
    rings that meet there — then (2) the lower id, so the choice is
    deterministic and replay-stable.  A ring that would fall below three
    vertices keeps them all: a triangle is the smallest thing the mesh can
    constrain, and collapsing it would delete a face.

    Runs AFTER :func:`weld_to_shore`, whose projection can itself bring two
    vertices together on the shore line.
    """
    rep = report if report is not None else WeldReport()
    spacing = float(law.tables.emit.identity.min_distinct_spacing_m)
    if spacing <= 0.0 or not surface.vertices:
        return surface
    mlat, mlon = _local_metres(surface.origin)
    la0, lo0 = float(surface.origin[0]), float(surface.origin[1])
    vll = {v.id: v.ll for v in surface.vertices}

    def xy(ll: _t.Sequence[float]) -> tuple[float, float]:
        return ((float(ll[1]) - lo0) * mlon, (float(ll[0]) - la0) * mlat)

    seqs: list[tuple[str, int, list[int], bool]] = []
    for f in surface.faces:
        seqs.append(("ring", f.id, list(f.ring), True))
        for hi, h in enumerate(f.holes):
            seqs.append((f"hole{hi}", f.id, list(h), True))
    for b in surface.breaklines:
        seqs.append(("break", b.id, list(b.vertices), False))
    degree: dict[int, int] = {}
    for _w, _o, ids, _c in seqs:
        for i in set(ids):
            degree[i] = degree.get(i, 0) + 1

    parent: dict[int, int] = {}

    def find(x: int) -> int:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    pxy = {i: xy(ll) for i, ll in vll.items()}
    for _w, _o, ids, closed in seqs:
        n = len(ids)
        if n < 2:
            continue
        span = n if closed else n - 1
        for k in range(span):
            a, b = find(ids[k]), find(ids[(k + 1) % n])
            if a == b:
                continue
            pa, pb = pxy[a], pxy[b]
            if math.hypot(pa[0] - pb[0], pa[1] - pb[1]) >= spacing:
                continue
            keep, drop = ((a, b) if (degree.get(a, 0), -a) >= (degree.get(b, 0), -b)
                          else (b, a))
            parent[drop] = keep
    remap = {i: find(i) for i in vll}
    if all(t == i for i, t in remap.items()):
        return surface

    def collapse(ids: list[int], closed: bool) -> list[int]:
        out: list[int] = []
        for i in ids:
            t = remap[i]
            if out and out[-1] == t:
                continue
            out.append(t)
        if closed and len(out) > 1 and out[0] == out[-1]:
            out.pop()
        if len(out) < (3 if closed else 2):
            return ids                     # never collapse a face away
        return out

    faces = []
    for f in surface.faces:
        ring = tuple(collapse(list(f.ring), True))
        holes = tuple(tuple(collapse(list(h), True)) for h in f.holes)
        faces.append(_dc.replace(f, ring=ring, holes=holes)
                     if ring != f.ring or holes != f.holes else f)
    breaks = []
    for b in surface.breaklines:
        run = collapse(list(b.vertices), False)
        breaks.append(_dc.replace(b, vertices=tuple(run))
                      if tuple(run) != b.vertices else b)
    live = {i for f in faces for i in f.ring} | \
        {i for f in faces for h in f.holes for i in h} | \
        {i for b in breaks for i in b.vertices}
    verts = tuple(v for v in surface.vertices if v.id in live)
    rep.merged = len(surface.vertices) - len(verts)
    return _dc.replace(surface, vertices=verts, faces=tuple(faces),
                       breaklines=tuple(breaks))


def render_sidecar(law: Law, sidecar: _t.Mapping[str, _t.Any] | None) -> dict:
    """The sidecar document: the given keys (⊆ ``SIDECAR_KEYS``) plus
    ``ruleset`` and the always-empty declarations."""
    doc: dict[str, _t.Any] = {"ruleset": law.ruleset_key,
                              "terrace_joints": [], "basin_facilities": [],
                              "road_bridge_decks": []}
    for k, v in (sidecar or {}).items():
        if k not in SIDECAR_KEYS:
            raise ValueError(f"sidecar key {k!r} is not in SIDECAR_KEYS")
        doc[k] = v
    return doc


def write_patch(surface: GradedSurface, law: Law, out_dir: str | Path,
                sidecar: _t.Mapping[str, _t.Any] | None = None,
                header: _t.Mapping[str, str] | None = None,
                face_tags: _t.Mapping[int, _t.Mapping[str, str]] | None = None
                ) -> PatchPaths:
    """Write ``<out_dir>/<ICAO>_auto.patch.osm``, its ``.axes.json``
    sidecar (keys ⊆ :data:`SIDECAR_KEYS`; a key outside the register is
    an error) and ``<ICAO>.graded.json``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    text, n_ways, n_nodes = render_patch(surface, law, header, face_tags)
    patch = out / f"{surface.icao}_auto.patch.osm"
    patch.write_text(text)
    side = Path(str(patch) + ".axes.json")
    side.write_text(json.dumps(render_sidecar(law, sidecar), separators=(",", ":")))
    graded = out / f"{surface.icao}.graded.json"
    graded.write_text(surface.to_json(z_dp=z_decimals(law)))
    return PatchPaths(patch, side, graded, n_ways, n_nodes,
                      patch.stat().st_size, side.stat().st_size)


def _in_seam_band(ll: _t.Sequence[float], half_m: float) -> bool:
    """THE SEAM-BAND TEST (§38 (3)/13an (c)) — the band's own definition,
    in the emitted frame: a point within ``half_width_m`` of an integer
    graticule line.  Metres are converted at the point's own latitude, so
    the reading is the band's, not a degree approximation."""
    lat, lon = float(ll[0]), float(ll[1])
    if abs(lat - round(lat)) * _M_PER_DEG_LAT <= half_m:
        return True
    scale = _M_PER_DEG_LAT * max(math.cos(math.radians(lat)), 1.0e-6)
    return abs(lon - round(lon)) * scale <= half_m


def tile_of_face(surface: GradedSurface, face) -> tuple[int, int]:
    """The 1° tile holding a face: the mean of its ring vertices (a face
    never straddles a tile line — the seam band is cut out of the map —
    so the mean of points inside one square is inside it)."""
    import math
    vs = {v.id: v for v in surface.vertices}
    lat = sum(vs[i].ll[0] for i in face.ring) / len(face.ring)
    lon = sum(vs[i].ll[1] for i in face.ring) / len(face.ring)
    return int(math.floor(lat)), int(math.floor(lon))


def write_tile_pieces(surface: GradedSurface, law: Law, out_dir: str | Path,
                      sidecar: _t.Mapping[str, _t.Any] | None = None,
                      header: _t.Mapping[str, str] | None = None,
                      face_tags: _t.Mapping[int, _t.Mapping[str, str]] | None = None
                      ) -> dict[tuple[int, int], PatchPaths]:
    """One patch per tile the surface touches, at the mesh's own path
    ``<out_dir>/<block>/<tile>/<ICAO>_auto.patch.osm`` (``O4_File_Names.
    patch_dir``: ``Patches/-20-080/-13-077/``), each carrying only the
    faces on that tile's side of the seam band, their vertices and the
    breakline runs inside them; the sidecar is the whole airport's (the
    census's axes and pairs are geometric, the tile filter is on faces).
    A single-tile surface writes one piece, identical to ``write_patch``.

    NO PIECE CARRIES A VERTEX INSIDE THE SEAM BAND (§38 (3)/13an (c); owner
    RULINGS 2026-09-13an).  The band is DRAPED DEM — no face lives in it —
    but a BREAKLINE could still run through it, and one did: bank foot chain
    ``bank:2`` (way −10046) followed a ~1.6 mm crack between the two collars
    0.0237 m east of the meridian, this function split it by
    ``floor(lon)`` with no seam test and wrote it verbatim into tile
    −13−077, and Triangle4XP — forbidden by ``-Y`` from splitting the OUTER
    border 2.37 cm away — split THAT segment 16,298 times instead (23,994
    triangles under 1e-5 m²; the SPLP texture tear).  A breakline run is
    therefore cut at the band as well as at the tile line, and the refusal
    is COUNTED so a chain that should never have been derived there
    (``emit/bank.py`` cuts the bank by the band at its own site) is visible
    rather than silently trimmed."""
    import math
    half = float(law.tables.emit.seam.half_width_m)
    by_tile: dict[tuple[int, int], list] = {}
    for f in surface.faces:
        by_tile.setdefault(tile_of_face(surface, f), []).append(f)
    vs = {v.id: v for v in surface.vertices}
    out: dict[tuple[int, int], PatchPaths] = {}
    for (lat, lon), faces in sorted(by_tile.items()):
        keep = {i for f in faces for i in f.ring} | \
            {i for f in faces for h in f.holes for i in h}
        # breakline stations INSIDE a face (the runway ridge's profile
        # stations are not ring vertices) travel with their tile, so the
        # piece's crown spine keeps the stations the census reads against
        for b in surface.breaklines:
            keep |= {i for i in b.vertices
                     if (int(math.floor(vs[i].ll[0])), int(math.floor(vs[i].ll[1]))) == (lat, lon)
                     and not _in_seam_band(vs[i].ll, half)}
        verts = tuple(v for v in surface.vertices if v.id in keep)
        bls = []
        for b in surface.breaklines:
            run = [i for i in b.vertices
                   if i in keep and not _in_seam_band(vs[i].ll, half)]
            if len(run) >= 2:
                bls.append(_dc.replace(b, vertices=tuple(run)))
        piece = _dc.replace(surface, vertices=verts, faces=tuple(faces),
                            breaklines=tuple(bls))
        block = f"{(lat // 10) * 10:+03d}{(lon // 10) * 10:+04d}"
        tile = f"{lat:+03d}{lon:+04d}"
        hdr = dict(header or {})
        hdr["o4_tile"] = tile
        out[(lat, lon)] = write_patch(piece, law, Path(out_dir) / block / tile,
                                      sidecar, hdr, face_tags)
    return out
