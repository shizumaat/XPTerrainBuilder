"""``mesh_crop`` — the last build's terrain mesh around an airport, for the
patch editor's 3D preview "Last build" (protocol 1.12,
``docs/specs/patch-editor-20261015.md`` §2, §5).

The ``Data<tile>.mesh`` in the tile's build folder (the request's
``build_dir``, spec §2 amendment (b), else ``Tiles/``) is read by the ONE
``.mesh`` parser, ``auto_patch/mesh_sampler`` (its one-entry parse cache
keyed by path, mtime and size), and the triangles with a vertex inside the
bbox are returned, re-indexed: ``vertices_f64_b64`` (lon, lat, elevation m)
triples and ``triangles_u32_b64``.  This is the surface X-Plane loads; it
does not follow edits until the tile is rebuilt.

A mesh that is not there is an error sentence saying why: never built, or
deleted by the file cleanup level (``cleaning_level`` > 2 removes it after
the DSF is written, ``O4_Tile_Utils``).  Read-only.
"""
from __future__ import annotations

import base64
import os
import typing as _t

import numpy as np

import O4_File_Names as FNAMES

__all__ = ["mesh_crop"]


def _b64(a: np.ndarray, dtype: str) -> str:
    return base64.b64encode(np.ascontiguousarray(a, dtype=dtype).tobytes()).decode("ascii")


def _missing_reason(tile: str, build_dir: str, lat: int, lon: int) -> str:
    import O4_UI_Utils as UI
    dsf = FNAMES.dsf_file(build_dir, lat, lon)
    if not os.path.isfile(dsf):
        return (f"Tile {tile} has not been built in {build_dir}, so there is no last "
                "build to show.")
    level = int(getattr(UI, "cleaning_level", 0) or 0)
    why = (f"the file cleanup level is {level}, which deletes the mesh once the scenery "
           "is written" if level > 2 else
           "the mesh was deleted after the build (file cleanup level 3 does that)")
    return (f"Tile {tile} was built, but its mesh is not in {build_dir}: {why}. Set "
            "the cleanup level to 2 or lower and rebuild the tile to see the last build.")


def mesh_crop(tile: str, bbox: _t.Sequence[float], build_dir: str | None = None) -> dict:
    """The §2 reply: the built mesh's triangles touching ``bbox``."""
    from auto_patch import mesh_sampler as _mesh

    parsed = FNAMES.parse_tile_key(tile)
    if parsed is None:
        raise ValueError(f"mesh_crop: {tile!r} is not a tile key like +45-123.")
    lat, lon = parsed
    try:
        s, w, n, e = (float(v) for v in bbox)
    except (TypeError, ValueError):
        raise ValueError("mesh_crop: bbox must be [min_lat, min_lon, max_lat, max_lon] "
                         "in degrees.") from None
    folder = build_dir or FNAMES.build_dir(lat, lon, "")
    path = FNAMES.mesh_file(folder, lat, lon)
    if not os.path.isfile(path):
        raise ValueError(_missing_reason(tile, folder, lat, lon))
    vertices, triangles, _attrs = _mesh._read_mesh_cached(path)
    inside = ((vertices[:, 0] >= w) & (vertices[:, 0] <= e)
              & (vertices[:, 1] >= s) & (vertices[:, 1] <= n))
    keep = triangles[inside[triangles].any(axis=1)]
    used, inverse = np.unique(keep.reshape(-1), return_inverse=True)
    return {"mesh_path": path,
            "vertices_f64_b64": _b64(vertices[used], "<f8"),
            "triangles_u32_b64": _b64(inverse.reshape(-1, 3), "<u4")}
