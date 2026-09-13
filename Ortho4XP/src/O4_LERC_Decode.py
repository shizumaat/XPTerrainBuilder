"""THE LERC DECODER — one implementation, three callers.

LERC-compressed elevation assets (New Zealand's 1 m lidar COGs, the
ArcGIS elevation tile pyramids) must be decoded OUT OF PROCESS: the
``imagecodecs`` LERC decoder and the ``osgeo`` shared libraries abort the
process when both are loaded (a native symbol clash, reproduced on macOS
with the Homebrew GDAL and the imagecodecs wheels).  So the decode never
shares a process with GDAL — but it does share ITS CODE with every
caller, which is what this module is.

It imports ``numpy``, ``tifffile`` and ``imagecodecs`` AT MODULE LEVEL
and imports NO GDAL, deliberately on both counts:

* module level, so PyInstaller's static scan SEES the codecs and the
  frozen bundle carries them (the ``highspy`` precedent: a
  function-level third-party import is invisible to the freeze AND to
  the suite, and the engine shipped without it);
* no GDAL, so importing this module in the child is safe.

Three callers, one code path:

* from source — ``O4_Airport_Elevation_Insets`` spawns
  ``sys.executable <this file> IN OUT``;
* frozen — the same module spawns ``sys.executable --lerc-decode IN
  OUT``, which ``Ortho4XP.py`` dispatches (early, before the heavy
  imports) into :func:`main` here.  Before this the packaged engine had
  NO decoder at all and silently degraded NZ's 1 m DEM to the base tier
  (owner RULINGS 2026-09-12as (3));
* the suite — :func:`decode_tiff` / :func:`decode_blobs` called
  directly.

``IN`` a FILE is the GeoTIFF decode (``OUT`` is a ``.npy``; the
georeferencing tags go to stdout as JSON).  ``IN`` a DIRECTORY is the
blob decode: every ``*.lerc`` in it becomes ``OUT/<name>.npy``.
"""
from __future__ import annotations

import json
import os
import sys

import numpy
import imagecodecs
import tifffile

#: The ArcGIS elevation tile grid: 256x256 samples, the service serving a
#: 257x257 array whose last row/column is the neighbour's shared edge.
_TILE = 256

#: What an ArcGIS LERC tile's masked (no-data) samples become.
_TILE_NODATA = -32768.0


def decode_tiff(tiff_path: str, npy_path: str) -> dict:
    """Decode a LERC-compressed GeoTIFF to ``npy_path``.

    :returns: ``{"scale": [...], "tiepoint": [...]}`` — the
        ModelPixelScale / ModelTiepoint tags the caller georeferences
        the array with.
    """
    with tifffile.TiffFile(tiff_path) as tif:
        page = tif.pages[0]
        numpy.save(npy_path, page.asarray())
        return {
            "scale": list(page.tags["ModelPixelScaleTag"].value),
            "tiepoint": list(page.tags["ModelTiepointTag"].value),
        }


def decode_blob(blob: bytes) -> numpy.ndarray:
    """One raw LERC blob as a ``(256, 256)`` float32 array."""
    mask = None
    try:
        decoded = imagecodecs.lerc_decode(blob, masks=True)
        if isinstance(decoded, tuple):
            (values, mask) = decoded
        else:
            values = decoded
    except TypeError:
        values = imagecodecs.lerc_decode(blob)
    values = numpy.asarray(values, dtype=numpy.float32)
    values = values.reshape(values.shape[-2], values.shape[-1])
    if mask is not None:
        mask = numpy.asarray(mask, dtype=bool).reshape(values.shape)
        values[~mask] = _TILE_NODATA
    # ArcGIS elevation tiles carry a one-sample shared edge (257x257 for
    # a 256 grid): crop to the tile proper.
    return values[:_TILE, :_TILE]


def decode_blobs(blob_directory: str, npy_directory: str) -> int:
    """Decode every ``*.lerc`` in ``blob_directory`` into ``.npy`` files.

    :returns: how many blobs were decoded.
    """
    decoded = 0
    for name in sorted(os.listdir(blob_directory)):
        if not name.endswith(".lerc"):
            continue
        with open(os.path.join(blob_directory, name), "rb") as handle:
            blob = handle.read()
        numpy.save(os.path.join(npy_directory, name[:-5] + ".npy"),
                   decode_blob(blob))
        decoded += 1
    return decoded


def main(argv) -> int:
    """``[--lerc-decode] IN OUT`` — the file / directory kind of ``IN``
    picks the decode; the GeoTIFF decode prints its tags as JSON."""
    args = [a for a in argv if a != "--lerc-decode"]
    if len(args) != 2:
        print("usage: --lerc-decode IN OUT", file=sys.stderr)
        return 2
    source, destination = args
    if os.path.isdir(source):
        decode_blobs(source, destination)
    else:
        print(json.dumps(decode_tiff(source, destination)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
