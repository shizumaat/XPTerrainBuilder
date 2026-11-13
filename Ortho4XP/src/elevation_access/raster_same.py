"""Is a re-fetched elevation raster the one already cached? (#2050)

Owner RULINGS 2026-11-13o: elevation data goes years between updates, so
a refresh that fetches the same surface must change NOTHING — not the
cached file, not its mtime, not the stamps that name it (the inset
completion stamp, every patch's ``o4_dem``).  The fetch loop asks
:func:`same_raster` before it lands a new raster on the cache: equal
within :data:`TOLERANCE_M`, the cached file is kept and the new one
discarded, and the kept path is noted (:func:`note_kept`) so a ledgered
refresh can record "unchanged" (``build_airport.py --refresh-data``).

Equal means: the same grid (size, geotransform, projection, band count),
the same no-data posts, and every valid post within the tolerance.  Any
doubt — GDAL absent, a file unreadable — answers ``False`` (the new
raster lands, as before).
"""
from __future__ import annotations

__all__ = ["TOLERANCE_M", "same_raster", "note_kept", "kept_unchanged"]

#: The materiality floor for elevation (CLAUDE.md convergence guards).
TOLERANCE_M = 0.01

#: Cache paths a re-fetch found unchanged in this process, in order.
_KEPT: list[str] = []


def _grid(ds) -> tuple:
    return (ds.RasterXSize, ds.RasterYSize, ds.RasterCount,
            tuple(round(v, 12) for v in ds.GetGeoTransform()),
            ds.GetProjection())


def same_raster(new_path: str, cached_path: str,
                tol_m: float = TOLERANCE_M) -> bool:
    """True when ``new_path`` holds the surface ``cached_path`` holds."""
    try:
        import numpy as np
        from .gdal_support import gdal, has_gdal
        if not has_gdal:
            return False
        new, old = gdal.Open(new_path), gdal.Open(cached_path)
        if new is None or old is None or _grid(new) != _grid(old):
            return False
        for index in range(1, new.RasterCount + 1):
            nb, ob = new.GetRasterBand(index), old.GetRasterBand(index)
            if nb.GetNoDataValue() != ob.GetNoDataValue():
                return False
            a = nb.ReadAsArray().astype("float64")
            b = ob.ReadAsArray().astype("float64")
            nodata = nb.GetNoDataValue()
            va = np.isfinite(a) & ((a != nodata) if nodata is not None else True)
            vb = np.isfinite(b) & ((b != nodata) if nodata is not None else True)
            if not np.array_equal(va, vb):
                return False
            if va.any() and float(np.max(np.abs(a[va] - b[va]))) > tol_m:
                return False
        return True
    except Exception:
        return False


def note_kept(cached_path: str) -> None:
    """Record that a re-fetch of ``cached_path`` changed nothing."""
    _KEPT.append(cached_path)


def kept_unchanged() -> list[str]:
    """Every cache path :func:`note_kept` recorded in this process."""
    return list(_KEPT)
