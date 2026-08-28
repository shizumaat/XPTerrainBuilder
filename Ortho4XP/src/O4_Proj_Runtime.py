"""PROJ runtime pinning and self-check (docs/specs/proj-runtime-robustness-spec.md).

A frozen bundle carries TWO independent libproj copies — pyproj's wheel with
its matched ``proj.db``, and GDAL's with its own — so each library must read
the database it shipped with and the user's environment must not redirect
either.  This module pins those two search paths in frozen mode, scrubs the
hijackable environment variables, and offers a behavioral self-check whose
verdict (``PREFLIGHT_ERROR`` / :func:`refuse_reason`) lets pipeline steps
refuse instead of building a silently degraded tile.

Headless by design: only ``os``/``sys`` at module level, ``pyproj``/``osgeo``
imported inside the functions, and no UI import (callers print).
"""

from __future__ import annotations

import os
import sys

#: Diagnostic from the last :func:`preflight` call, ``None`` when healthy.
PREFLIGHT_ERROR: str | None = None

# A user machine (QGIS, PostGIS, OSGeo4W) commonly exports these globally;
# any of them can point a bundled libproj at a foreign database version.
_HIJACKABLE_VARS = (
    "PROJ_LIB",
    "PROJ_DATA",
    "PROJ_AUX_DB",
    "GDAL_DATA",
    "GDAL_DRIVER_PATH",
)


def scrub_proj_env() -> None:
    """Drop the PROJ/GDAL search-path variables and disable PROJ networking.

    ``PROJ_NETWORK=OFF`` is a determinism requirement: no grid downloads may
    happen behind a build.
    """
    for name in _HIJACKABLE_VARS:
        os.environ.pop(name, None)
    os.environ["PROJ_NETWORK"] = "OFF"


def frozen_proj_dirs(meipass: str) -> tuple[str | None, str | None]:
    """Return ``(pyproj_dir, gdal_dir)`` inside a frozen bundle.

    Each entry is the bundled PROJ data directory of that library, or ``None``
    when it carries no ``proj.db`` (the Linux job deliberately ships no GDAL).
    Pure path logic — no import of either library.
    """
    pyproj_dir: str | None = os.path.join(
        meipass, "pyproj", "proj_dir", "share", "proj"
    )
    gdal_dir: str | None = os.path.join(meipass, "osgeo", "data", "proj")
    if pyproj_dir is not None and not os.path.isfile(
        os.path.join(pyproj_dir, "proj.db")
    ):
        pyproj_dir = None
    if gdal_dir is not None and not os.path.isfile(
        os.path.join(gdal_dir, "proj.db")
    ):
        gdal_dir = None
    return pyproj_dir, gdal_dir


def pin_frozen_proj(meipass: str) -> None:
    """Point each bundled libproj at its own database (frozen mode only).

    GDAL has no pre-import Python API for search paths, so it is steered with
    ``PROJ_DATA``; pyproj's explicit ``set_data_dir`` outranks that variable
    for pyproj, so the two libraries diverge onto their own databases.  Must
    run before the first pyproj/osgeo import in the process.
    """
    scrub_proj_env()
    pyproj_dir, gdal_dir = frozen_proj_dirs(meipass)
    if gdal_dir is not None:
        os.environ["PROJ_DATA"] = gdal_dir
    if pyproj_dir is not None:
        import pyproj

        pyproj.datadir.set_data_dir(pyproj_dir)


def _diagnostic_lines() -> list[str]:
    """Version, path and environment lines for a preflight failure report.

    Every probe is guarded: the diagnostic is produced precisely when the
    PROJ runtime is broken, so no probe may raise out of it.
    """
    lines: list[str] = []
    try:
        import pyproj

        lines.append(f"  pyproj.__version__: {pyproj.__version__}")
        lines.append(f"  pyproj.proj_version_str: {pyproj.proj_version_str}")
        lines.append(f"  pyproj data dir: {pyproj.datadir.get_data_dir()}")
    except Exception as error:  # noqa: BLE001 - report, never mask
        lines.append(f"  pyproj unavailable: {error!r}")
    try:
        from osgeo import gdal, osr

        osr.UseExceptions()
        lines.append(f"  osgeo.gdal.__version__: {gdal.__version__}")
        lines.append(f"  osr.GetPROJSearchPaths(): {osr.GetPROJSearchPaths()}")
    except ImportError:
        lines.append("  osgeo: not importable (bundle without GDAL)")
    except Exception as error:  # noqa: BLE001 - report, never mask
        lines.append(f"  osgeo unavailable: {error!r}")
    lines.append(f"  sys.frozen: {getattr(sys, 'frozen', False)}")
    environment = sorted(
        (name, value)
        for name, value in os.environ.items()
        if name.startswith("PROJ_") or name.startswith("GDAL_")
    )
    if environment:
        for name, value in environment:
            lines.append(f"  env {name}={value}")
    else:
        lines.append("  env: no PROJ_*/GDAL_* variables set")
    return lines


def preflight() -> str | None:
    """Check both PROJ runtimes by behavior; return ``None`` when healthy.

    A failure returns (and stores in :data:`PREFLIGHT_ERROR`) a multi-line
    diagnostic naming the versions, data directories and environment.  An
    ``osgeo`` ImportError is not a failure — the Linux build ships no GDAL.
    """
    global PREFLIGHT_ERROR
    failures: list[str] = []
    try:
        import pyproj

        transformer = pyproj.Transformer.from_crs(4326, 3857, always_xy=True)
        easting, northing = transformer.transform(0.0, 0.0)
        # PROJ answers an unusable database with infinities rather than an
        # exception: a point that did not transform is a failure.
        if not (abs(easting) < 1e30 and abs(northing) < 1e30):
            failures.append(
                "ERROR: pyproj transform EPSG:4326 -> EPSG:3857 returned "
                f"({easting}, {northing})"
            )
    except Exception as error:  # noqa: BLE001 - this is the check
        failures.append(f"ERROR: pyproj transform failed: {error!r}")
    try:
        from osgeo import osr

        osr.UseExceptions()
    except ImportError:
        osr = None  # type: ignore[assignment]
    except Exception as error:  # noqa: BLE001 - this is the check
        osr = None  # type: ignore[assignment]
        failures.append(f"ERROR: osgeo import failed: {error!r}")
    if osr is not None:
        try:
            code = osr.SpatialReference().ImportFromEPSG(4326)
            if code != 0:
                failures.append(
                    f"ERROR: osr ImportFromEPSG(4326) returned {code}"
                )
        except Exception as error:  # noqa: BLE001 - this is the check
            failures.append(f"ERROR: osr ImportFromEPSG(4326) failed: {error!r}")
    if not failures:
        PREFLIGHT_ERROR = None
    else:
        PREFLIGHT_ERROR = "\n".join(failures + _diagnostic_lines())
    return PREFLIGHT_ERROR


def refuse_reason() -> str | None:
    """Return the diagnostic pipeline steps must refuse with, else ``None``."""
    return PREFLIGHT_ERROR
