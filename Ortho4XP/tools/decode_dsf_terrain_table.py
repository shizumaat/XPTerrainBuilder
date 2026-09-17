#!/usr/bin/env python3
"""Decode an emitted DSF's terrain-definition table and per-patch summary.

Runs the bundled ``DSFTool --dsf2text`` on a ``.dsf`` file (7z handled by
DSFTool) and prints:

  * the ``TERRAIN_DEF`` table in index order, and
  * a per-patch line of ``(terrain index, terrain path, flags, plane count,
    triangle count)``.

It is the verification companion to the ``texture_mode`` writer work
(``docs/specs/texture-mode-spec.md``, work package 2): tests use
:func:`decode_dsf` to assert an emitted DSF's terrain table and patch
attributes; a human can run it from the command line on any DSF.

The DSFTool location and the ``--dsf2text`` conversion cache are reused from
``src/auto_patch/dsf_reader.py`` (``_dsftool_path`` / ``ensure_dsf_text_path``)
so this tool honours the same binary discovery and mtime-keyed text cache as
the rest of the pipeline.

Usage::

    python tools/decode_dsf_terrain_table.py <path/to/tile.dsf>

Exit status is non-zero when DSFTool is unavailable or the DSF cannot be
converted.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import NamedTuple

# Make ``src`` importable when run as a standalone script.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import O4_File_Names as FNAMES
from auto_patch.dsf_reader import _dsftool_path, ensure_dsf_text_path


class PatchSummary(NamedTuple):
    """One physical/overlay terrain patch decoded from a DSF text dump."""

    terrain_index: int
    terrain_path: str
    flags: int
    plane_count: int
    triangle_count: int


class DsfTerrainDump(NamedTuple):
    """Decoded terrain table and patch list for a single DSF."""

    terrain_paths: list
    patches: list  # list[PatchSummary]


def _primitive_triangle_count(primitive_type: int, vertex_count: int) -> int:
    """Number of triangles a primitive of ``vertex_count`` vertices yields.

    Type 0 = independent triangles (``n // 3``); types 1 (strip) and 2 (fan)
    both yield ``n - 2`` triangles (0 when fewer than three vertices).
    """
    if primitive_type == 0:
        return vertex_count // 3
    if primitive_type in (1, 2):
        return max(0, vertex_count - 2)
    return 0


def decode_text_lines(lines) -> DsfTerrainDump:
    """Decode an iterable of DSFTool ``--dsf2text`` lines.

    Grammar (mirrors ``O4_Default_Terrain_Map``)::

        TERRAIN_DEF <path>
        BEGIN_PATCH <terrainIdx> <nearLOD> <farLOD> <flags> <coordDepth>
        BEGIN_PRIMITIVE <0|1|2>
        PATCH_VERTEX <lon> <lat> ...
        END_PRIMITIVE
        END_PATCH
    """
    terrain_paths: list = []
    patches: list = []

    patch_terrain_index = -1
    patch_flags = 0
    patch_plane_count = 0
    patch_triangle_count = 0
    primitive_type = -1
    primitive_vertex_count = 0

    def _flush_primitive() -> None:
        nonlocal patch_triangle_count
        if primitive_type >= 0:
            patch_triangle_count += _primitive_triangle_count(
                primitive_type, primitive_vertex_count)

    for raw in lines:
        if raw.startswith("PATCH_VERTEX"):
            primitive_vertex_count += 1
            continue
        if raw.startswith("TERRAIN_DEF"):
            tokens = raw.strip().split(maxsplit=1)
            terrain_paths.append(
                tokens[1].strip() if len(tokens) > 1 else "")
            continue
        if raw.startswith("BEGIN_PATCH"):
            tokens = raw.split()
            try:
                patch_terrain_index = int(tokens[1])
                patch_flags = int(tokens[4])
                patch_plane_count = int(tokens[5])
            except (IndexError, ValueError):
                patch_terrain_index = -1
                patch_flags = 0
                patch_plane_count = 0
            patch_triangle_count = 0
            primitive_type = -1
            primitive_vertex_count = 0
            continue
        if raw.startswith("BEGIN_PRIMITIVE"):
            tokens = raw.split()
            try:
                primitive_type = int(tokens[1])
            except (IndexError, ValueError):
                primitive_type = -1
            primitive_vertex_count = 0
            continue
        if raw.startswith("END_PRIMITIVE"):
            _flush_primitive()
            primitive_type = -1
            primitive_vertex_count = 0
            continue
        if raw.startswith("END_PATCH"):
            if primitive_type >= 0 and primitive_vertex_count:
                _flush_primitive()
            path = (
                terrain_paths[patch_terrain_index]
                if 0 <= patch_terrain_index < len(terrain_paths)
                else "")
            patches.append(PatchSummary(
                terrain_index=patch_terrain_index,
                terrain_path=path,
                flags=patch_flags,
                plane_count=patch_plane_count,
                triangle_count=patch_triangle_count,
            ))
            patch_terrain_index = -1
            patch_flags = 0
            patch_plane_count = 0
            patch_triangle_count = 0
            primitive_type = -1
            primitive_vertex_count = 0
            continue

    return DsfTerrainDump(terrain_paths=terrain_paths, patches=patches)


def dsf_text_path(dsf_path: str) -> str:
    """DSFTool ``--dsf2text`` dump of ``dsf_path``, cached per DSF.

    The dump (and DSFTool's ``.raw`` raster sidecars) go to a per-DSF
    subdirectory of ``FNAMES.Default_dsf_cache_dir`` — never next to the
    DSF, which may live inside a scenery pack that ships to X-Plane, and
    never shared between two DSFs that merely have the same tile basename
    (distinct DSFs decoded concurrently would race on one cache file and
    serve each other's dump on mtime luck).
    """
    import hashlib

    dump_dir = os.path.join(
        FNAMES.Default_dsf_cache_dir,
        hashlib.sha1(
            os.path.abspath(dsf_path).encode("utf-8")).hexdigest()[:8])
    os.makedirs(dump_dir, exist_ok=True)
    text_path = ensure_dsf_text_path(dsf_path, cache_dir=dump_dir)
    if text_path is None:
        raise FileNotFoundError(
            f"Could not produce a DSFTool text dump for {dsf_path!r} "
            "(missing DSF, missing DSFTool binary, or conversion error).")
    return text_path


def decode_dsf(dsf_path: str) -> DsfTerrainDump:
    """Run DSFTool on ``dsf_path`` and decode its terrain table + patches.

    Raises ``FileNotFoundError`` if DSFTool is unavailable or the DSF cannot
    be converted to text.  The text dump (and DSFTool's ``.raw`` raster
    sidecars) go to a per-DSF subdirectory of
    ``FNAMES.Default_dsf_cache_dir`` — never next to the DSF, which may
    live inside a scenery pack that ships to X-Plane, and never shared
    between two DSFs that merely have the same tile basename (distinct
    DSFs decoded concurrently would race on one cache file and serve
    each other's dump on mtime luck).
    """
    text_path = dsf_text_path(dsf_path)
    with open(text_path, "r", encoding="utf-8", errors="replace") as handle:
        return decode_text_lines(handle)


def dsftool_available() -> bool:
    """True when the bundled DSFTool binary is present (for test skips)."""
    return _dsftool_path() is not None


# ── water-datum audit (--water-datum-audit) ─────────────────────────────

#: THE ONE IMPLEMENTATION of "is this terrain drawn by the water shader" is
#: the engine's own — the writer filters on it and this audit measures it, so
#: the two can never disagree (the census-wrapper precedent).
from O4_Default_Terrain_Map import is_water_terrain  # noqa: E402


def _metre_factors(lat_deg: float):
    """(metres per degree lon, metres per degree lat) about ``lat_deg``."""
    import math

    return (111320.0 * math.cos(math.radians(lat_deg)), 110540.0)


def _tri_area_m2(tri, mx, my) -> float:
    (ax, ay), (bx, by), (cx, cy) = (
        (v[0] * mx, v[1] * my) for v in tri)
    return abs((bx - ax) * (cy - ay) - (cx - ax) * (by - ay)) / 2.0


class _MeshWaterLocator:
    """WHAT DOES THE MESH SAY AT THIS POINT — land, inland water, or sea?

    A DSF vertex coordinate is NOT the mesh coordinate: ``O4_DSF_Utils``
    quantises every node into a 16-bit per-pool quadtree cell (~1.5 m at
    this latitude) and ``O4_Bathymetry.recut_water_tris`` inserts nodes the
    mesh never had, so a coordinate join between the two artifacts is
    unsound in both directions.  The sound join is CONTAINMENT: the mesh's
    own water triangles indexed spatially, queried by the DSF triangle's
    centroid.

    The MEDIT parse and the water-bit mask are ``tools/mesh_region_tris``'s
    own and the land/inland/sea collapse is the engine's own
    ``O4_DSF_Utils.remap_water_tri_type`` — both imported, never re-spelled
    (the census-wrapper precedent).
    """

    def __init__(self, mesh_path: str) -> None:
        from shapely.geometry import Polygon
        from shapely.strtree import STRtree

        if _HERE not in sys.path:
            sys.path.insert(0, _HERE)
        import mesh_region_tris as MRT
        from O4_DSF_Utils import remap_water_tri_type

        (_nv, lon, lat, _z, tri, att) = MRT._read_mesh_attributed(mesh_path)
        polygons = []
        self._classes = []
        for i in range(len(att)):
            if not att[i] & MRT.WATER_BITS:
                continue
            ring = [(lon[n], lat[n]) for n in tri[3 * i: 3 * i + 3]]
            polygons.append(Polygon(ring))
            # use_masks_for_inland False: keep the inland class distinct —
            # this is a READ, not the writer's routing decision.
            self._classes.append(
                remap_water_tri_type(att[i], False, MRT.WATER_BITS))
        self._tree = STRtree(polygons) if polygons else None
        self.water_triangles = len(polygons)

    def classify(self, lon: float, lat: float) -> str:
        """``"sea"`` / ``"inland"`` / ``"land"`` at ``(lon, lat)``."""
        from shapely.geometry import Point

        if self._tree is None:
            return "land"
        hits = self._tree.query(Point(lon, lat), predicate="intersects")
        if not len(hits):
            return "land"
        classes = {self._classes[int(h)] for h in hits}
        return "sea" if 2 in classes else "inland"


def water_datum_audit(
    text_path: str,
    flag_m: float = 0.05,
    top: int = 10,
    near=None,
    mesh_path: str | None = None,
    site_grid_deg: float = 0.002,
    band_depth: int | None = None,
):
    """IS EVERY WATER-*RENDERED* TRIANGLE FLAT AT THE SEA'S DATUM?

    The mesh-side half of this question is
    ``mesh_region_tris.py --water-audit`` (does a water-BIT triangle carry a
    raised vertex).  This is the DSF-side half plus the JOIN, and it exists
    because the two populations are not the same set: a mesh LAND triangle
    can still be emitted with a water TERRAIN, in which case the mesh law is
    satisfied and X-Plane still draws water up a bank (owner sim read at
    OTHH, 2026-09-17).

    Over every triangle of the emitted DSF whose terrain is drawn by the
    water shader (:func:`is_water_terrain`), reports — split by the emitting
    BAND (the patch's coordinate depth, which is the emitter's own
    signature: ``O4_DSF_Utils`` writes 7 planes for a mesh-water triangle
    and 5 for a default-landclass patch) — how many stand above ``flag_m``,
    their ground area, the maximum height and the worst distinct SITES.

    THE JOIN IS THE BAND, and it is exact: the 5-plane band exists only
    because ``emit_physical_default_land`` writes it, and that function is
    called only for a mesh triangle whose type is 0 — LAND.  So a
    water-terrain triangle in the 5-plane band is by construction a DSF
    water triangle that is NOT a water-bit triangle of the mesh: the paint
    escaping the mesh's water datum.  ``mesh_path`` adds the independent
    check over the RAISED population only (:class:`_MeshWaterLocator`),
    which also separates lawful raised INLAND water from raised SEA.

    ``near`` is ``(lat, lon, radius_m)``.  Returns the payload dict; prints
    it.  Reads only; writes nothing.
    """
    import collections
    import math

    from O4_Default_Terrain_Map import _primitive_triangles

    locator = _MeshWaterLocator(mesh_path) if mesh_path else None

    terrain_paths: list = []
    patch_water = False
    patch_path = ""
    patch_depth = 0
    primitive_type = -1
    primitive_vertices: list = []

    bands = collections.defaultdict(lambda: {
        "triangles": 0, "raised": 0, "area_m2": 0.0, "raised_area_m2": 0.0,
        "max_z_m": 0.0,
    })
    raised_sites: list = []
    mx = my = None

    def _consider(tri):
        nonlocal mx, my
        if band_depth is not None and patch_depth != band_depth:
            return
        zmax = max(v[2] for v in tri)
        lon_c = sum(v[0] for v in tri) / 3.0
        lat_c = sum(v[1] for v in tri) / 3.0
        if mx is None:
            (mx, my) = _metre_factors(lat_c)
        if near is not None:
            (nlat, nlon, radius) = near
            dx = (lon_c - nlon) * mx
            dy = (lat_c - nlat) * my
            if math.hypot(dx, dy) > radius:
                return
        row = bands[(patch_path, patch_depth)]
        area = _tri_area_m2(tri, mx, my)
        row["triangles"] += 1
        row["area_m2"] += area
        row["max_z_m"] = max(row["max_z_m"], zmax)
        if zmax > flag_m:
            row["raised"] += 1
            row["raised_area_m2"] += area
            raised_sites.append(
                [zmax, lat_c, lon_c, patch_path, patch_depth, area, None])

    def _flush_primitive():
        if patch_water and primitive_type >= 0:
            for tri in _primitive_triangles(primitive_type, primitive_vertices):
                _consider(tri)
        primitive_vertices.clear()

    with open(text_path, "r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            if raw.startswith("PATCH_VERTEX"):
                if not patch_water or primitive_type < 0:
                    continue
                tokens = raw.split()
                try:
                    primitive_vertices.append(
                        (float(tokens[1]), float(tokens[2]),
                         float(tokens[3])))
                except (IndexError, ValueError):
                    continue
                continue
            if raw.startswith("TERRAIN_DEF"):
                tokens = raw.strip().split(maxsplit=1)
                terrain_paths.append(
                    tokens[1].strip() if len(tokens) > 1 else "")
                continue
            if raw.startswith("BEGIN_PATCH"):
                tokens = raw.split()
                try:
                    index = int(tokens[1])
                    patch_depth = int(tokens[5])
                except (IndexError, ValueError):
                    index = -1
                    patch_depth = 0
                patch_path = (
                    terrain_paths[index]
                    if 0 <= index < len(terrain_paths) else "")
                patch_water = is_water_terrain(patch_path)
                primitive_type = -1
                primitive_vertices.clear()
                continue
            if raw.startswith("BEGIN_PRIMITIVE"):
                tokens = raw.split()
                try:
                    primitive_type = int(tokens[1])
                except (IndexError, ValueError):
                    primitive_type = -1
                primitive_vertices.clear()
                continue
            if raw.startswith("END_PRIMITIVE"):
                _flush_primitive()
                primitive_type = -1
                continue
            if raw.startswith("END_PATCH"):
                if primitive_type >= 0 and primitive_vertices:
                    _flush_primitive()
                patch_water = False
                patch_path = ""
                patch_depth = 0
                primitive_type = -1
                primitive_vertices.clear()
                continue

    # The mesh's verdict over the RAISED population only (the quantisation
    # note in _MeshWaterLocator is why it is not run over all of them).
    mesh_classes = collections.Counter()
    mesh_class_area = collections.Counter()
    if locator is not None:
        for entry in raised_sites:
            verdict = locator.classify(entry[2], entry[1])
            entry[6] = verdict
            mesh_classes[(entry[4], verdict)] += 1
            mesh_class_area[(entry[4], verdict)] += entry[5]

    # Distinct sites: the worst triangle per ``site_grid_deg`` cell.
    best_per_cell: dict = {}
    for entry in raised_sites:
        cell = (round(entry[1] / site_grid_deg), round(entry[2] / site_grid_deg))
        if cell not in best_per_cell or entry[0] > best_per_cell[cell][0]:
            best_per_cell[cell] = entry
    sites = sorted(best_per_cell.values(), key=lambda e: -e[0])[:top]

    default_land_band = sum(
        row["raised"] for ((_path, depth), row) in bands.items() if depth == 5)
    default_land_area = sum(
        row["raised_area_m2"] for ((_path, depth), row) in bands.items()
        if depth == 5)
    totals = {
        "triangles": sum(r["triangles"] for r in bands.values()),
        "raised": sum(r["raised"] for r in bands.values()),
        "raised_area_m2": sum(r["raised_area_m2"] for r in bands.values()),
        "max_z_m": max((r["max_z_m"] for r in bands.values()), default=0.0),
        "raised_on_land_band": default_land_band,
        "raised_on_land_band_area_m2": default_land_area,
        # THE ACCEPTANCE NUMBER when a mesh is given, and band-free: a
        # water-terrain triangle standing above the datum on ground the MESH
        # calls land.  (Raised INLAND water is lawful — each body keeps its
        # own level — so a tile-wide "all water at 0" bar would be wrong.)
        "raised_on_mesh_land": sum(
            count for ((_d, verdict), count) in mesh_classes.items()
            if verdict == "land"),
    }
    payload = {
        "text_path": text_path, "flag_m": flag_m, "near": near,
        "mesh": mesh_path, "totals": totals,
        "bands": {f"{path}|depth{depth}": dict(row)
                  for ((path, depth), row) in sorted(bands.items())},
        "raised_mesh_class": {
            f"depth{depth}|{verdict}": {
                "triangles": count,
                "area_m2": mesh_class_area[(depth, verdict)]}
            for ((depth, verdict), count) in sorted(mesh_classes.items())},
        "sites": [
            {"max_z_m": z, "lat": lat, "lon": lon, "terrain": path,
             "depth": depth, "area_m2": area, "mesh_class": verdict}
            for (z, lat, lon, path, depth, area, verdict) in sites],
    }

    print(f"water-datum audit — DSF dump {text_path}")
    print(f"  water-terrain triangles {totals['triangles']:,}; "
          f"above {flag_m} m: {totals['raised']:,} "
          f"({totals['raised_area_m2']:,.0f} m2, max {totals['max_z_m']:.3f} m)")
    for key, row in sorted(payload["bands"].items()):
        print(f"  [{key}] tris {row['triangles']:,}, raised {row['raised']:,}"
              f", raised area {row['raised_area_m2']:,.0f} m2"
              f", max {row['max_z_m']:.3f} m")
    print("  JOIN (the band is the join — the 5-plane band is written only by "
          "emit_physical_default_land, i.e. only for a mesh LAND triangle): "
          f"water drawn on the LAND band and raised: "
          f"{default_land_band:,} triangle(s), {default_land_area:,.0f} m2")
    if locator is not None:
        print(f"  mesh check over the raised population "
              f"({locator.water_triangles:,} mesh water triangles indexed):")
        for key, row in sorted(payload["raised_mesh_class"].items()):
            print(f"    {key}: {row['triangles']:,} triangle(s), "
                  f"{row['area_m2']:,.0f} m2")
    for site in payload["sites"]:
        print(f"    site {site['lat']:.6f}, {site['lon']:.6f}  "
              f"z {site['max_z_m']:.3f} m  {site['terrain']} "
              f"depth{site['depth']}"
              + ("" if site["mesh_class"] is None
                 else f"  mesh={site['mesh_class']}"))
    return payload


def _format_report(dump: DsfTerrainDump) -> str:
    out = ["TERRAIN_DEF table ({} entries):".format(len(dump.terrain_paths))]
    for index, path in enumerate(dump.terrain_paths):
        out.append("  [{:>3}] {}".format(index, path))
    out.append("")
    out.append("Patches ({} total):".format(len(dump.patches)))
    out.append("  {:>5}  {:>5}  {:>5}  {:>6}  {}".format(
        "idx", "flag", "plane", "tris", "terrain"))
    for patch in dump.patches:
        out.append("  {:>5}  {:>5}  {:>5}  {:>6}  {}".format(
            patch.terrain_index, patch.flags, patch.plane_count,
            patch.triangle_count, patch.terrain_path))
    return "\n".join(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dsf_path", help="path to a .dsf file to decode")
    parser.add_argument(
        "--water-datum-audit", action="store_true",
        help="instead of the terrain table, audit every WATER-RENDERED "
             "triangle's altitude: counts, area, max height and worst sites "
             "per emitting band, and (with --mesh) the JOIN against the "
             "mesh's own water-bit triangles")
    parser.add_argument(
        "--water-flag", type=float, default=0.05, metavar="M",
        help="a water-terrain vertex above this is RAISED (default 0.05)")
    parser.add_argument(
        "--mesh", metavar="MESH",
        help="built .mesh of the same tile, for the mesh/DSF water JOIN")
    parser.add_argument(
        "--near", nargs=3, type=float, metavar=("LAT", "LON", "RADIUS_M"),
        help="restrict the audit to a site")
    parser.add_argument(
        "--band-depth", type=int, metavar="N",
        help="restrict to patches of this coordinate depth (5 = the "
             "default-landclass LAND band, 7 = the mesh-water band)")
    parser.add_argument(
        "--top", type=int, default=10, help="how many distinct sites to name")
    parser.add_argument(
        "--json", metavar="OUT.json", help="write the payload as JSON")
    args = parser.parse_args(argv)

    if not dsftool_available():
        print("ERROR: bundled DSFTool binary not found; cannot decode.",
              file=sys.stderr)
        return 2
    if args.water_datum_audit:
        try:
            text_path = dsf_text_path(args.dsf_path)
        except FileNotFoundError as exc:
            print("ERROR: {}".format(exc), file=sys.stderr)
            return 2
        payload = water_datum_audit(
            text_path, flag_m=args.water_flag, top=args.top,
            near=(tuple(args.near) if args.near else None),
            mesh_path=args.mesh, band_depth=args.band_depth)
        if args.json:
            import json

            with open(args.json, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        return 0
    try:
        dump = decode_dsf(args.dsf_path)
    except FileNotFoundError as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 2
    print(_format_report(dump))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
