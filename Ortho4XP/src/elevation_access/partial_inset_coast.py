"""Partial-inset coast: the pixels of a mostly-fill inset the base keeps (#2271).

A provider that answers the sea with a constant fill (FABDEM and
Copernicus serve 0 m, :mod:`elevation_access.provider_fill` masks it as
nodata) hands an airport a PARTIAL inset: real ground over the island
and nodata over the sea.  Where that inset covers the airport poorly the
pixels it does hold at the airport are its COASTLINE, and the coastline
is where the provider's water edit is least trustworthy: NSAS (Ofu) kept
a 30 m fringe at -6.1 .. -4.0 m under mid-runway while the base DEM read
8.0 / 3.8 / 7.6 m there, and the bake laid a 13 m pit into the runway's
production DEM (the runway trend and a service road followed it).

THE RULE.  On an inset whose provider fill was masked (the fetch's
``provider_fill`` record) and whose true coverage is below the airport
coverage threshold the caller passes, a valid pixel is REFUSED (becomes
nodata for the bake, so the base DEM models it, exactly as it models the
sea beyond it) when

1. it stands BELOW SEA LEVEL (< 0 m) where the base DEM reads LAND
   (> 0 m) -- the provider's sea edit leaking onto land its own water
   mask did not catch; or
2. it lies within ``COAST_RING_PIXELS`` native pixels (8-connected) of a
   pixel refused by (1) AND stands BELOW the base there -- the
   transition that leak drags down (NSAS: 1 .. 4 m over a base of
   7 .. 9 m beside the -6 m fringe).

The coastline next to the fill ALONE is never refused: measured, an
erosion of every coastline pixel standing below the base cut LPMA's
runway platform out of its inset (law-true rows 4,795 -> 9,969,
``runway_step`` 0 -> 8), and one standing anywhere cut NSFQ's cliff-top
runway (3 -> 186).  A coast whose provider reads no sub-sea land keeps
its inset byte for byte.

A well-covered inset, and every inset without a masked provider fill
(lidar, a full-coverage DEM), is never judged: its pixels bake as
before, byte for byte.  The rule reads the raster and the base only, so
it is the same on every build and needs no file write.
"""
from __future__ import annotations

import json

import numpy

__all__ = ["COAST_RING_PIXELS", "refuse_partial_coast"]

#: How many native pixels beside a refused sub-sea pixel are judged.
COAST_RING_PIXELS = 1


def _partial_fill_cover(sidecar_meta, cover_threshold):
    """The inset's true coverage when its sidecar records a masked
    provider fill and that coverage is below ``cover_threshold``, else
    ``None`` (the inset is not judged)."""
    record = (sidecar_meta or {}).get("provider_fill")
    if not isinstance(record, dict):
        return None
    try:
        cover = float(record.get("valid_fraction"))
    except (TypeError, ValueError):
        return None
    return cover if cover < float(cover_threshold) else None


def _dilate8(mask, rings):
    """``mask`` grown by ``rings`` pixels, 8-connected (the raster frame
    is not a neighbour)."""
    grown = mask.copy()
    for _ in range(max(int(rings), 0)):
        padded = numpy.pad(grown, 1, mode="constant", constant_values=False)
        rows, columns = grown.shape
        step = grown.copy()
        for dr in (0, 1, 2):
            for dc in (0, 1, 2):
                step |= padded[dr:dr + rows, dc:dc + columns]
        grown = step
    return grown


def _untrusted_coast_cells(values, nodata, base_values, base_nodata=None):
    """``(refused, sub_sea)``: boolean arrays shaped like ``values`` --
    the valid pixels the rule refuses, and those of them refused for
    standing below sea level where the base reads land.  ``base_values``
    is the base DEM at the same posts; its ``base_nodata`` cells never
    read as land."""
    values = numpy.asarray(values)
    base_values = numpy.asarray(base_values)
    valid = numpy.isfinite(values)
    if nodata is not None:
        valid &= values != nodata
    base_land = numpy.isfinite(base_values) & (base_values > 0.0)
    if base_nodata is not None:
        base_land &= base_values != base_nodata
    sub_sea = valid & (values < 0.0) & base_land
    below_base = valid & numpy.isfinite(base_values) & (values < base_values)
    if base_nodata is not None:
        below_base &= base_values != base_nodata
    refused = sub_sea | (below_base & _dilate8(sub_sea, COAST_RING_PIXELS))
    return refused, sub_sea


def _sidecar_meta(inset_path):
    """The fetch's sidecar (``<icao>_<code>.json``) beside ``inset_path``,
    or ``{}``."""
    if not inset_path or not inset_path.endswith(".tif"):
        return {}
    try:
        with open(inset_path[:-4] + ".json", "r", encoding="utf-8") as handle:
            meta = json.load(handle)
    except (OSError, ValueError):
        return {}
    return meta if isinstance(meta, dict) else {}


def _base_at_posts(inset, base_dem):
    """The base DEM's working grid read (nearest post) at every post of
    ``inset``; both carry tile-relative node frames."""
    rows, columns = inset.alt_dem.shape
    x = inset.x0 + numpy.arange(columns) * (
        (inset.x1 - inset.x0) / max(columns - 1, 1))
    y = inset.y1 - numpy.arange(rows) * (
        (inset.y1 - inset.y0) / max(rows - 1, 1))
    x_step = (base_dem.x1 - base_dem.x0) / (base_dem.nxdem - 1)
    y_step = (base_dem.y1 - base_dem.y0) / (base_dem.nydem - 1)
    base_columns = numpy.clip(numpy.rint((x - base_dem.x0) / x_step),
                              0, base_dem.nxdem - 1).astype(int)
    base_rows = numpy.clip(numpy.rint((base_dem.y1 - y) / y_step),
                           0, base_dem.nydem - 1).astype(int)
    return base_dem.alt_dem[numpy.ix_(base_rows, base_columns)]


def refuse_partial_coast(inset, base_dem, inset_path, cover_threshold):
    """Apply THE RULE to the decoded ``inset`` in place (its refused
    pixels become ``inset.nodata``) and return the record
    ``{"cover", "refused", "sub_sea"}``, or ``None`` when the inset is not
    judged or nothing was refused.  Idempotent: an inset already judged
    returns its first record untouched (the bake may run twice on one
    decoded raster)."""
    if hasattr(inset, "coast_refusal"):
        return inset.coast_refusal
    inset.coast_refusal = None
    cover = _partial_fill_cover(_sidecar_meta(inset_path), cover_threshold)
    if cover is None or getattr(inset, "alt_dem", None) is None:
        return None
    refused, sub_sea = _untrusted_coast_cells(
        inset.alt_dem, inset.nodata, _base_at_posts(inset, base_dem),
        base_dem.nodata)
    if not refused.any():
        return None
    inset.alt_dem[refused] = inset.nodata
    inset.coast_refusal = {"cover": round(cover, 4),
                           "refused": int(refused.sum()),
                           "sub_sea": int(sub_sea.sum())}
    return inset.coast_refusal
