"""WHICH FILES A TILE BUNDLE CARRIES (#1699 phase 1; the census is
``docs/specs/tile-bundle-phase1-census.md``).

Everything the scenery-file step (step 3) and the object stage read that
the vector, mesh and masks steps wrote, and nothing else:

* ``build/`` — the mesh (``Data<tile>.mesh``), the airport polygons the
  scenery-file step reads (``Data<tile>.apt``), the airports the tile
  was built without (``o4_unpatched_airports.json``, which the build's
  closing warnings and the vector step's retry rule read), and the
  scenery-file step's own data inputs (``Data<tile>.dsf_inputs.npz``,
  ``O4_DSF_Data_Inputs`` — the export computes it; it is not a build
  output);
* ``patches/`` — each airport's solved patch, its graded surface, its
  object plan and screen record, and the object-anchor worklist: the
  object stage's whole input, and the vector step's outputs;
* ``masks/`` — the water masks the scenery-file step textures with.

NOT carried: the vector step's elevation grid and triangulation inputs
(``O4_Step_Reuse.bundle_absent_outputs`` — only the mesh step reads
them), the editor sidecar (``*.axes.json``, which the app rebuilds),
logs, imagery, and anything of a scenery pack.
"""
from __future__ import annotations

import os
import re

import O4_Step_Reuse as REUSE

__all__ = ["PATCH_FILE_RE", "BUILD_FILES", "files", "forbidden", "destination"]

#: The patch-folder files a bundle carries.
PATCH_FILE_RE = re.compile(
    r"^(?:[A-Za-z0-9]{2,8}_auto\.patch\.osm"
    r"|[A-Za-z0-9]{2,8}\.graded\.json"
    r"|o4_v2_rebake_[A-Za-z0-9]{2,8}(?:~\d+)?(?:\.screen)?\.json"
    r"|o4_object_anchor_worklist\.json)$")

#: The build-folder files a bundle carries, besides the mesh.
BUILD_FILES = ("o4_unpatched_airports.json",)

#: Extensions a bundle may never hold: imagery and scenery-pack files.
_FORBIDDEN = (".dds", ".jpg", ".jpeg", ".ter", ".obj", ".agp", ".fac",
              ".for", ".lin", ".pol", ".str", ".dsf", ".alt", ".node",
              ".poly", ".tif", ".bz2")


def files(tile) -> list:
    """``[(name in the bundle, local path)]`` for ``tile``, sorted."""
    import O4_File_Names as FNAMES
    out = [("build/" + os.path.basename(FNAMES.mesh_file(
        tile.build_dir, tile.lat, tile.lon)),
        FNAMES.mesh_file(tile.build_dir, tile.lat, tile.lon))]
    apt = FNAMES.apt_file(tile)
    if os.path.isfile(apt):
        out.append(("build/" + os.path.basename(apt), apt))
    for name in BUILD_FILES:
        path = os.path.join(tile.build_dir, name)
        if os.path.isfile(path):
            out.append(("build/" + name, path))
    for prefix, folder, keep in (
            ("patches/", FNAMES.patch_dir(tile.lat, tile.lon),
             PATCH_FILE_RE.match),
            ("masks/", FNAMES.mask_dir(tile.lat, tile.lon), lambda n: True)):
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            names = []
        out += [(prefix + n, os.path.join(folder, n)) for n in names
                if keep(n) and os.path.isfile(os.path.join(folder, n))]
    absent = set(REUSE.bundle_absent_outputs(tile))
    return sorted(pair for pair in out if pair[1] not in absent)


def forbidden(name: str) -> bool:
    """Whether a bundle member ``name`` is a kind no bundle may carry
    (imagery, a pack's files, a raw download, the elevation grid)."""
    return name.lower().endswith(_FORBIDDEN)


def destination(tile, name: str) -> str:
    """Where the bundle member ``name`` lands on this machine."""
    import O4_File_Names as FNAMES
    folder, _sep, base = name.partition("/")
    if not base or "/" in base or base in ("", ".", ".."):
        raise ValueError("bundle member %r is not a plain file name" % name)
    root = {"build": tile.build_dir,
            "patches": FNAMES.patch_dir(tile.lat, tile.lon),
            "masks": FNAMES.mask_dir(tile.lat, tile.lon)}.get(folder)
    if root is None:
        raise ValueError("bundle member %r is outside build/, patches/, "
                         "masks/" % name)
    return os.path.join(root, base)
