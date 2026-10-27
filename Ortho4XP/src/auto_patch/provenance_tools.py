"""THE PATCH FRESHNESS GATE'S TOOLCHAIN HALF (owner Q158, 2026-10-26): ONE
digest of what an airport patch is built WITH that is not the engine's own
source, stamped on every patch as ``o4_tools``.

WHY.  The gate keyed on ``o4_engine`` (``O4_Version.version``), which
moves on every engine build, so every release rebuilt every airport's patch
even when the patch build's code (``o4_code``, ``provenance_code``) had not
changed.  ``o4_code`` covers the Python source and the law tables; what it
cannot see is the toolchain those run on.  ``o4_tools`` is that toolchain,
so a new toolchain still rebuilds every airport, and a release that leaves
both alone rebuilds none.

WHAT IS DIGESTED.
  * the bundled native tools the build runs (:data:`NATIVE_TOOLS`), by
    CONTENT — a reinstalled identical binary keeps the patch;
  * the version of every third-party library the patch build's import
    closure imports (:data:`PATCH_LIBRARIES`; ``tests/test_patch_code_
    closure.py`` fails on one the closure imports and this list omits);
  * the Python version (major.minor.micro).

A tool or library that is missing reads as ``absent``: it is still part of
the digest, so installing it later changes the stamp.
"""
from __future__ import annotations

import hashlib
import importlib
import os
import platform
import sys

__all__ = ["NATIVE_TOOLS", "PATCH_LIBRARIES", "toolchain_fingerprint",
           "toolchain_parts"]

#: The bundled executables (``Utils/<platform>/``) the patch build and the
#: tile core it runs through call: DSFTool reads and rewrites the pack DSFs,
#: Triangle4XP meshes the tile the patch is seated on.
NATIVE_TOOLS: tuple[str, ...] = ("DSFTool", "Triangle4XP")

#: Every third-party top-level module the patch build's import closure
#: (``provenance_code.PATCH_CODE_MODULES``) imports, sorted.  Held by
#: ``tests/test_patch_code_closure.py``.
PATCH_LIBRARIES: tuple[str, ...] = (
    "PIL",
    "certifi",
    "curl_cffi",
    "highspy",
    "ispc_texcomp",
    "keyring",
    "laspy",
    "numpy",
    "osgeo",
    "osmium",
    "pyproj",
    "requests",
    "rtree",
    "scipy",
    "shapely",
    "skfmm",
    "tifffile",
    "truststore",
)

_CHUNK = 1 << 20


def _platform_dir() -> tuple[str, str]:
    """``(Utils sub-folder, executable suffix)`` — the same choice
    ``O4_Mesh_Utils`` and ``O4_Overlay_Utils`` make."""
    if "dar" in sys.platform:
        return "mac", ""
    if "win" in sys.platform:
        return "win", ".exe"
    return "lin", ""


def _tool_identity(path: str) -> str:
    """``sha256`` of the file at ``path``, or ``absent``."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(_CHUNK), b""):
                digest.update(chunk)
    except OSError:
        return "absent"
    return digest.hexdigest()


def _distributions() -> dict:
    try:
        from importlib import metadata
        return metadata.packages_distributions()
    except Exception:
        return {}


def _library_version(name: str, distributions: dict) -> str:
    """The installed distribution's version, read without importing the
    library; else (a frozen engine may ship no metadata) the module's
    ``__version__`` (or ``version``), else ``unversioned``; ``absent`` when
    it will not import."""
    try:
        from importlib import metadata
        versions = sorted(metadata.version(dist)
                          for dist in set(distributions.get(name, ())))
        if versions:
            return ",".join(versions)
    except Exception:
        pass
    try:
        module = sys.modules.get(name) or importlib.import_module(name)
    except Exception:
        return "absent"
    for attr in ("__version__", "version"):
        value = getattr(module, attr, None)
        if isinstance(value, str) and value:
            return value
    return "unversioned"


def toolchain_parts(utils_dir: str | None = None) -> list[str]:
    """The lines :func:`toolchain_fingerprint` digests, readable — the
    first place to look when a patch rebuilt for ``o4_tools``."""
    if utils_dir is None:
        import O4_File_Names as FNAMES
        utils_dir = FNAMES.Utils_dir
    folder, suffix = _platform_dir()
    parts = ["python " + platform.python_version()]
    for tool in NATIVE_TOOLS:
        parts.append("tool %s %s" % (tool, _tool_identity(
            os.path.join(utils_dir, folder, tool + suffix))))
    distributions = _distributions()
    for name in PATCH_LIBRARIES:
        parts.append("lib %s %s" % (name, _library_version(name,
                                                             distributions)))
    return parts


_FINGERPRINT: str | None = None


def toolchain_fingerprint() -> str:
    """THE ``o4_tools`` STAMP (16 hex), taken once per process."""
    global _FINGERPRINT
    if _FINGERPRINT is None:
        text = "\n".join(toolchain_parts())
        _FINGERPRINT = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return _FINGERPRINT
