"""THE BANK ANNULUS read off the tile's patch ``.osm`` files: the
``bank_foot`` and design rings (``_bank_rings_from_patches``), the annulus
between them (``bank_annulus_polygon``) and the per-region maximum
triangle areas the ``.poly`` writer hands Triangle4XP there
(``bank_annulus_region_areas``, RULINGS 2026-09-09x).

Moved out of ``O4_Mesh_Utils`` (#836): the vector step sizes the regions
when it writes the ``.poly``, the mesh step blends and audits the annulus;
a leaf both import keeps the vector step's code key off the mesh module.
"""
from __future__ import annotations

import os
from math import cos, pi

import O4_File_Names as FNAMES
import O4_OSM_Utils as OSM
import O4_UI_Utils as UI

__all__ = ["BANK_FOOT_FEATURE", "BANK_RINGS_STATS", "bank_annulus_polygon",
           "bank_annulus_region_areas"]


# THE ANNULUS IS IDENTIFIED FROM THE PATCH ``.osm`` FILES, not from the
# ``.poly``: the ``.poly`` carries no ``o4_feature``, and giving the foot
# ring a marker bit of its own would change what Triangle4XP is handed,
# which is exactly the class 09t killed the tile with.  Those are the SAME
# files ``include_patches`` reads, with the same manual-before-auto
# selection, so the two steps see the same rings.  The Z DATA still comes
# from the ``.poly`` (column 5 of the ring edges' endpoints), which is the
# only place the authored altitudes exist at this point.
#
# Everything is done in the ISOTROPIC frame ``(x * cos(lat), y)``: the
# tile-relative frame is degrees, and a ratio of plan distances in it
# would be wrong by the longitude scale at any bearing but due north.
BANK_FOOT_FEATURE = "bank_foot"


#: WHAT THE LAST :func:`_bank_rings_from_patches` READ — a report figure
#: and the input of the LOUD BAR below: ``foot_closed`` / ``foot_open``
#: ``bank_foot`` ways and ``design`` rings.  RULINGS 2026-09-13cp: the
#: 1.0.329 defect was 105 open feet and 0 closed, and NOTHING said so.
BANK_RINGS_STATS = {}


def _bank_rings_from_patches(tile):
    """The tile's patch rings, split into FOOT rings and DESIGN rings.

    Returns ``(foot_polygons, design_polygons, open_foot_lines)`` in the
    isotropic tile-relative frame, or ``None`` when the patch directory
    cannot be read.  All three are empty for a tile with no patch, and
    ``foot_polygons`` is empty for a v1 or manual patch — the caller then
    does nothing at all.

    ``open_foot_lines`` (RULINGS 2026-09-13cp) are the ``bank_foot`` ways
    that are OPEN — a ring straddling a tile seam.  They are LINEWORK, not
    a region: an open chain bounds nothing, so it never enters the annulus
    polygon, and it is never closed here by projection.  The closed
    coverage is the EMITTER's job.
    """
    from shapely import geometry, ops

    from auto_patch import selection as SELECTION
    patch_dir = FNAMES.patch_dir(tile.lat, tile.lon)
    if not os.path.exists(patch_dir):
        BANK_RINGS_STATS.clear()
        return ([], [], [])
    all_files = [f for f in os.listdir(patch_dir) if f[-10:] == ".patch.osm"]
    manual = [f for f in all_files if "_auto.patch.osm" not in f]
    auto = [f for f in all_files if "_auto.patch.osm" in f]
    manual_icao = {f[:-10].split("_")[0].upper() for f in manual}
    mode = SELECTION.resolved_auto_patch_mode(tile)
    files = list(manual)
    for name in auto:
        icao = name.replace("_auto.patch.osm", "").upper()
        if mode == "None":
            continue
        if mode == "ICAO" and not (len(icao) == 4 and icao.isalpha()):
            continue
        if icao in manual_icao:
            continue
        files.append(name)
    scalx = cos((tile.lat + 0.5) * pi / 180)
    feet, design = [], []
    open_feet = []                         # §37 (3): load-bearing runs
    for name in files:
        layer = OSM.OSM_layer()
        try:
            layer.update_dicosm(os.path.join(patch_dir, name),
                                input_tags=None, target_tags=None)
        except Exception:
            continue
        nodes = layer.dicosmn
        for wayid in layer.dicosmfirst["w"]:
            way = layer.dicosmw.get(wayid)
            if not way or len(way) < 4:
                continue
            tags = layer.dicosmtags["w"].get(wayid, {})
            closed = way[0] == way[-1]
            if not closed:
                # §37 (3): an OPEN ``bank_foot`` chain is a load-bearing
                # RUN of one boundary ring; anything else open is not a
                # ring and never was read here.
                if tags.get("o4_feature") != BANK_FOOT_FEATURE:
                    continue
            try:
                ring = [((float(nodes[n][0]) - tile.lon) * scalx,
                         float(nodes[n][1]) - tile.lat)
                        for n in (way[:-1] if closed else way)]
            except Exception:
                continue
            if not closed:
                # RULINGS 2026-09-13cp: an OPEN chain is a BREAKLINE, and
                # it is carried as LINEWORK.  It is not closed here by a
                # ``nearest_points`` projection any more — that ribbon
                # (the 09-13q-era ``_close_open_foot``) fed the blend 15
                # vertices where the closed ring fed it 33,377.  The
                # closed coverage is the EMITTER's (``emit/bank.py``).
                open_feet.append(geometry.LineString(ring))
                continue
            polygon = geometry.Polygon(ring)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if polygon.is_empty or not polygon.area:
                continue
            if tags.get("o4_feature") == BANK_FOOT_FEATURE:
                feet.append(polygon)
            else:
                design.append(polygon)
    BANK_RINGS_STATS.clear()
    BANK_RINGS_STATS.update({"foot_closed": len(feet),
                             "foot_open": len(open_feet),
                             "design": len(design)})
    return (feet, design, open_feet)


def bank_annulus_polygon(tile):
    """THE BANK ANNULUS of the tile: the ground between the patch's design
    coverage and its ``bank_foot`` rings, in the isotropic tile-relative
    frame.  An EMPTY polygon when the tile has no banked patch (which is
    the whole of the no-op path for a v1 or manual patch); ``None`` when
    the inputs cannot be read.

    A ``bank_foot`` way is one RING of the banked region.  The design
    coverage is a subset of that region, so a ring whose polygon meets the
    design coverage is an EXTERIOR ring and one that does not is a HOLE:
    ``banked = union(exteriors) - union(holes)``, and the annulus is
    ``banked - design_coverage``.  Any error in that classification leaves
    vertices to the harmonic extension, never the other way round.
    """
    from shapely import geometry, ops

    rings = _bank_rings_from_patches(tile)
    if rings is None:
        return None
    (feet, design, _open_lines) = rings
    if not feet:
        return geometry.Polygon()
    design_cov = ops.unary_union(design) if design else geometry.Polygon()
    exteriors = [p for p in feet if p.intersects(design_cov)]
    holes = [p for p in feet if not p.intersects(design_cov)]
    if not exteriors:
        return geometry.Polygon()
    banked = ops.unary_union(exteriors)
    if holes:
        banked = banked.difference(ops.unary_union(holes))
    annulus = banked.difference(design_cov)
    return annulus if not annulus.is_empty else geometry.Polygon()


# ── THE MESH MUST HAVE VERTICES TO CARRY THE BLEND ─────────────────────
# (owner RULINGS 2026-09-09x; spec docs/specs/auto-patch-v2/
#  design-surface-spec.md §13.8)
#
# THE DEFECT round 1 measured.  ``bank_annulus_blend_values`` writes the
# ruled altitude EXACTLY (4.7 mm over 11,153 annulus vertices at HECA),
# but only 40 of those vertices are FREE tile-wide: Triangle4XP puts
# essentially nothing inside the annulus, so the bank IS the ring-to-foot
# triangulation, and a triangle joining a ring vertex to a foot vertex at
# a different bank width is skewed however exact the field is (12.4 % of
# annulus triangles over 0.35 by count on the HECA transect).
#
# THE LAW.  Each connected component of the bank annulus is handed to
# Triangle as a REGION carrying a MAXIMUM TRIANGLE AREA
#
#     max_area = (w / [design] bank_triangle_divisions) ** 2
#
# with ``w`` the component's own MEDIAN BANK WIDTH — the median over the
# component's boundary of ``d_in + d_out``, the very sum the blend law
# divides by, so the region is refined in the metric the blend is ruled
# in.  A region record without a fifth field is left exactly as it was
# (see ``O4_Vector_Utils.Vector_Map.write_poly_file``): this is a per-
# region AREA ATTRIBUTE, a different Triangle facility from a constrained
# segment, so the duplicate-segment class that hung 09t is untouched.
#
# WIDTH AT THE SEED, not per annulus component.  MEASURED at HECA
# (2026-09-09): the annulus is 212 components and ONE of them holds 60 %
# of its area (2.74 km2) — the whole airport's banks, merged wherever two
# rings' feet meet, with the ground BETWEEN the bodies inside it.  A
# component median is meaningless there: it read a 319 m "bank" against a
# measured foot distance of 5.0-74.4 m.  ``w`` is therefore the LOCAL
# width at the region's own seed, ``d_in + d_out`` — the same sum the
# blend law divides by, at the same point, so the region is refined in
# exactly the metric the blend is ruled in.
#
# UNITS.  The ``.poly`` frame is tile-relative DEGREES and is anisotropic;
# every distance here is measured in the ISOTROPIC frame ``(x * scalx, y)``
# (the frame ``bank_annulus_blend_values`` rules the blend in) and the
# resulting area is divided by ``scalx`` to land back in ``.poly`` units.

def bank_annulus_region_areas(tile, seeds):
    """``{seed index: max triangle area}`` in ``.poly`` units for every
    seed of ``seeds`` (an iterable of ``(x, y)`` in the tile-relative
    degree frame) that lies inside a BANK ANNULUS.

    Empty when the tile has no banked patch, when no seed falls in an
    annulus, or when the rings cannot be read — this only ever REFINES a
    region that would otherwise be unconstrained, so a failure costs the
    round-1 mesh, never the tile.  Writes nothing.
    """
    import numpy as _np
    import shapely as _sh
    from shapely import geometry as _geom, ops as _ops

    seeds = [(float(s[0]), float(s[1])) for s in seeds]
    if not seeds:
        return {}
    try:
        from auto_patch_v2.law import tables as _law_tables
        divisions = float(_law_tables.load_default()
                          .tables.emit.design.bank_triangle_divisions)
        annulus = bank_annulus_polygon(tile)
        rings = _bank_rings_from_patches(tile)
    except Exception as error:
        UI.lvprint(
            1, "WARNING: could not size the bank annulus regions — the "
               "annulus keeps whatever triangles the mesh gives it "
               "(RULINGS 2026-09-09x):", str(error))
        return {}
    if annulus is None or annulus.is_empty or not rings or not rings[0]:
        return {}
    if not divisions >= 1.0:
        return {}
    (feet, design, _open_lines) = rings
    design_cov = _ops.unary_union(design) if design else _geom.Polygon()
    if design_cov.is_empty:
        return {}

    # ``_bank_rings_from_patches`` — and so ``bank_annulus_polygon`` — is
    # ALREADY in the isotropic frame ``(x * scalx, y)`` (it applies the
    # scale as it reads the ``.osm`` nodes), exactly as
    # ``bank_annulus_blend_values`` relies on.  Only the SEEDS, which
    # arrive in raw tile-relative degrees, are scaled here.
    scalx = cos((tile.lat + 0.5) * pi / 180)
    inner = _sh.boundary(design_cov)                # the design ring
    outer = _sh.union_all([_sh.boundary(p) for p in feet])         # the foot

    sx = _np.asarray([s[0] for s in seeds]) * scalx
    sy = _np.asarray([s[1] for s in seeds])
    points = _sh.points(_np.stack([sx, sy], axis=1))
    inside = _np.flatnonzero(_sh.contains_xy(annulus, sx, sy))
    if not inside.size:
        return {}
    here = points[inside]
    width = _sh.distance(here, inner) + _sh.distance(here, outer)
    side = width / divisions
    max_area = (side * side) / scalx            # back into .poly units
    good = _np.isfinite(max_area) & (max_area > 0.0)
    return {int(inside[k]): float(max_area[k])
            for k in _np.flatnonzero(good).tolist()}
