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


# ---------------------------------------------------------------------------
# THE SYSTEM TRUST STORE (issue #121, lane win121)
# ---------------------------------------------------------------------------
# The frozen bundle speaks HTTPS through TWO stacks.  GDAL's libcurl is built
# on Schannel (Windows) and reads the OPERATING SYSTEM's root store; Python's
# ``ssl`` — i.e. ``requests``, which fetches the Viewfinderpanoramas base DEM
# and probes the Copernicus cells — reads certifi's bundled file.  A machine
# whose antivirus or corporate proxy re-signs HTTPS with a root installed in
# the SYSTEM store only then gets a good inset (GDAL) over a failed base
# (requests): the #121 shape.  ``truststore`` points Python's ``ssl`` at the
# system store too, so both stacks trust exactly what the OS trusts.
#
# ONE site: the frozen entries call this right after :func:`pin_frozen_proj`,
# in every process of the bundle (the engine, its workers, the LERC child),
# before any HTTPS is made.  Never a global environment variable.
TRUST_STORE_STATE: str = "not attempted"


def trust_system_certificate_store() -> str:
    """Make Python's ``ssl`` verify against the OS trust store.

    Returns (and records in :data:`TRUST_STORE_STATE`) ``"injected"``,
    ``"unavailable: ..."`` or ``"failed: ..."``.  Never raises: a bundle
    without the wheel says so on stderr — stdout may be the JSONL protocol
    — and keeps certifi, which is exactly the pre-fix behaviour.
    """
    global TRUST_STORE_STATE
    try:
        import truststore
    except Exception as error:                        # pragma: no cover
        TRUST_STORE_STATE = "unavailable: %s" % (error,)
    else:
        try:
            truststore.inject_into_ssl()
            TRUST_STORE_STATE = "injected"
        except Exception as error:
            TRUST_STORE_STATE = "failed: %s: %s" % (type(error).__name__,
                                                    error)
    if TRUST_STORE_STATE != "injected":
        try:
            sys.stderr.write(
                "WARNING: HTTPS verification uses the bundled certifi roots, "
                "not the system trust store (truststore %s); a proxy or "
                "antivirus that re-signs HTTPS will fail Python downloads.\n"
                % TRUST_STORE_STATE)
        except Exception:
            pass
    return TRUST_STORE_STATE


def tls_selfcheck(url: str) -> dict:
    """Fetch ``url`` through BOTH HTTPS stacks of this process.

    The frozen ``--tls-selfcheck URL`` CLI (``--no-truststore`` skips the
    injection, the before-arm).  ``requests`` is the stack
    :func:`trust_system_certificate_store` changes; GDAL's ``/vsicurl/``
    is the control it must leave alone.
    """
    result = {"url": url, "truststore": TRUST_STORE_STATE}
    try:
        import requests

        response = requests.get(url, timeout=30)
        result["requests"] = "ok %d (%d bytes)" % (response.status_code,
                                                   len(response.content))
        result["requests_ok"] = response.status_code == 200
    except Exception as error:
        result["requests"] = "%s: %s" % (type(error).__name__, error)
        result["requests_ok"] = False
    try:
        from osgeo import gdal

        gdal.UseExceptions()
        handle = gdal.VSIFOpenL("/vsicurl/" + url, "rb")
        data = gdal.VSIFReadL(1, 1 << 20, handle)
        gdal.VSIFCloseL(handle)
        result["gdal"] = "ok (%d bytes)" % len(data or b"")
        result["gdal_ok"] = bool(data)
    except Exception as error:
        result["gdal"] = "%s: %s" % (type(error).__name__, error)
        result["gdal_ok"] = False
    return result


def tls_selfcheck_main(argv: list[str]) -> int:
    """``--tls-selfcheck URL [--out FILE]``: exit 0 when ``requests``
    fetched the URL.  The verdict is written to FILE as JSON as well,
    because the Windows app is a windowed bundle whose stdout may go
    nowhere."""
    import json

    url = argv[argv.index("--tls-selfcheck") + 1]
    result = tls_selfcheck(url)
    text = json.dumps(result, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w", encoding="utf-8",
                  newline="\n") as handle:
            handle.write(text + "\n")
    try:
        print(text)
    except Exception:
        pass
    return 0 if result.get("requests_ok") else 1
