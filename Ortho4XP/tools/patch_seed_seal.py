"""DOES THIS PATCH'S INTERP_ALT SEEDING SEAL? — offline, in seconds.

``run_tile_mesh_only.py`` answers it in ~2 minutes and only as a whole
tile; the question itself is a property of the PATCH FILES ALONE.  This
entry reads the closed ways of every ``*.patch.osm`` in a patch directory
through production's own ``O4_OSM_Utils.OSM_layer``, inserts them into a
real ``O4_Vector_Utils.Vector_Map`` with ``insert_way(check=True)`` under
``O4_Vector_Map.PATCH_RING_MARKER``, seeds them exactly as
``include_patches`` seeds (``ops.polygonize`` over the ring boundaries,
``interp_alt_seed_point`` per face, the coverage test), and runs the
engine's OWN ``audit_interp_alt_seed_sealing`` on the result.

IT DERIVES NOTHING AND MEASURES NO LAW: every predicate, marker and
tolerance is imported from the engine.  A PASS here is not a mesh run —
the tile carries roads, coastlines and the other INTERP_ALT encoders, and
``seed_interp_alt_subcells`` runs later on all of them; what it settles is
the class this entry was written for (RULINGS 2026-09-09i, lane
``v2seedseal``): a patch whose own rings mint a face too small or too thin
to hold a locatable seed, which refuses the tile.  Runway ways carrying
``altitude_high`` are skipped exactly as their `cplx_way` branch is not
reproduced here; they are straight quads and mint no slivers.

Usage (from the checkout root):

    venv/bin/python tools/patch_seed_seal.py Patches/+30+030/+30+031
    venv/bin/python tools/patch_seed_seal.py Patches/+30+030/+30+031 --faces

``--faces`` lists the faces that were refused a seed, smallest first, with
their area in square metres — which is the attribution half: a refused
face names the near-coincident ways that minted it.

Exit code 0 when every seed is sealed, 1 when the audit refuses.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy

SRC = os.path.join(os.getcwd(), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import O4_OSM_Utils as OSM  # noqa: E402
import O4_Vector_Map as VMAP  # noqa: E402
import O4_Vector_Utils as VECT  # noqa: E402
from shapely import geometry, ops, prepared  # noqa: E402


def tile_origin(patch_dir: str) -> tuple[int, int]:
    """``.../Patches/+30+030/+30+031`` -> ``(30, 31)``."""
    name = os.path.basename(os.path.normpath(patch_dir))
    return int(name[:3]), int(name[3:])


def closed_rings(patch_dir: str, lat: int, lon: int) -> list:
    """Every closed patch way, in tile-relative degrees, as
    ``(file, way id, tags, coordinates)`` — read exactly as
    ``include_patches`` reads them."""
    out = []
    for pfile in sorted(os.listdir(patch_dir)):
        if not pfile.endswith(".patch.osm"):
            continue
        layer = OSM.OSM_layer()
        layer.update_dicosm(os.path.join(patch_dir, pfile),
                            input_tags=None, target_tags=None)
        dw, dn = layer.dicosmw, layer.dicosmn
        df, dt = layer.dicosmfirst, layer.dicosmtags
        waylist = (tuple(df["w"].intersection(dt["w"]))
                   + tuple(df["w"].difference(dt["w"])))
        for wayid in waylist:
            way = (numpy.array([dn[n] for n in dw[wayid]], dtype=float)
                   - numpy.array([[lon, lat]]))
            tags = dt["w"].get(wayid, {})
            if "altitude_high" in tags:
                continue
            if not (way[0] == way[-1]).all():
                continue
            out.append((pfile, wayid, tags, way))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("patch_dir")
    parser.add_argument("--faces", action="store_true",
                        help="list the faces refused a seed, smallest first")
    args = parser.parse_args(argv)

    lat, lon = tile_origin(args.patch_dir)
    vector_map = VECT.Vector_Map()
    polygons = []
    for _pfile, _wayid, _tags, way in closed_rings(args.patch_dir, lat, lon):
        try:
            polygon = geometry.Polygon(way)
        except Exception:
            continue
        if not (polygon.is_valid and polygon.area):
            continue
        vector_map.insert_way(
            numpy.hstack([way, numpy.zeros((len(way), 1))]),
            VMAP.PATCH_RING_MARKER, check=True)
        polygons.append(polygon)
    if not polygons:
        print("no closed patch ways in", args.patch_dir)
        return 0

    covered = prepared.prep(ops.unary_union(polygons))
    seeds, refused = [], []
    boundaries = ops.unary_union([p.boundary for p in polygons])
    for face in ops.polygonize(boundaries):
        seed_point = VMAP.interp_alt_seed_point(face)
        if seed_point is None:
            refused.append(face)
            continue
        if covered.contains(seed_point):
            seeds.append(numpy.array(seed_point.coords[0]))
    vector_map.seeds.setdefault("INTERP_ALT", []).extend(seeds)
    print(f"{len(polygons)} closed ring(s), {len(seeds)} seed(s), "
          f"{len(refused)} face(s) refused a seed")

    if args.faces and refused:
        square_metres = VMAP._SQ_M_PER_SQ_DEG
        for face in sorted(refused, key=lambda f: f.area)[:50]:
            print("   refused  area %.4e m2  %d vertex(es)  at %s"
                  % (face.area * square_metres,
                     len(face.exterior.coords) - 1,
                     face.representative_point().wkt))

    try:
        VMAP.audit_interp_alt_seed_sealing(vector_map)
    except VMAP.UnsealedInterpAltSeed as refusal:
        print("REFUSED:", refusal)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
