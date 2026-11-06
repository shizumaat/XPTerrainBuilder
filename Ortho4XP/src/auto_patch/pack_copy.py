"""The object stage writing into a pack COPY (owner 2026-11-06T00:09Z).

``O4_PACK_WRITES=copy:<DIR>`` (set by ``tools/harness/build_airport.py
--pack-copy DIR``): the placement write targets ``<DIR>/<pack name>``, an
APFS clone of the serving pack the harness made before the build, and
never the pack in the X-Plane install.  The pack is still READ where it
is installed (its library, its art, its pristine DSF are the same bytes in
the clone); the art / forest / optimise stages and the sibling-pack write,
which would touch the installed packs, stand down.  The app sets nothing.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

__all__ = ["copy_dir", "ensure_copy"]

_COPY_PREFIX = "copy:"


def copy_dir() -> str | None:
    """The pack-copy directory this build writes into, else ``None``."""
    value = os.environ.get("O4_PACK_WRITES", "")
    return value[len(_COPY_PREFIX):] or None if value.startswith(_COPY_PREFIX) else None


def _copy_root(pack_root: str) -> str | None:
    """``<copy dir>/<pack name>`` for ``pack_root``, else ``None``."""
    base = copy_dir()
    if not base:
        return None
    return os.path.join(base, os.path.basename(os.path.normpath(pack_root)))


def ensure_copy(pack_root: str) -> str | None:
    """``_copy_root(pack_root)``, cloned from the installed pack on first
    use (APFS ``clonefile`` through ``cp -c`` on macOS: no bytes are
    copied until one is rewritten; a real copy elsewhere).  ``None``
    when no pack copy is armed."""
    target = _copy_root(pack_root)
    if target is None or os.path.isdir(target):
        return target
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if sys.platform == "darwin":
        subprocess.run(["cp", "-cR", pack_root, target], check=True)
    else:
        shutil.copytree(pack_root, target, symlinks=True)
    return target
