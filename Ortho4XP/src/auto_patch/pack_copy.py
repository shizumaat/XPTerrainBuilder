"""The object stage writing into a pack COPY (owner 2026-11-06T00:09Z).

``O4_PACK_WRITES=copy:<DIR>`` (set by ``tools/harness/build_airport.py
--pack-copy DIR``): the placement write targets ``<DIR>/<pack name>``, an
APFS clone of the serving pack the harness made before the build, and
never the pack in the X-Plane install.  The pack is still READ where it
is installed (its library, its art, its pristine DSF are the same bytes in
the clone); the art / forest / optimise stages and the sibling-pack write,
which would touch the installed packs, stand down.  The app sets nothing.

THE COPY IS A REAL TREE (#2041).  An installed pack is often a SYMLINK
into a library on another volume (``Custom Scenery/Orbx_… ->
/Volumes/…/Airports/Orbx_…``).  ``cp -R`` of a symlink operand copies the
LINK, so the "copy" pointed back at the installed pack and the KNUQ
companion write of a +37-123 lane build landed its DSF and 13 bodies in
the owner's install.  The clone now copies the pack's resolved directory
with every symlink followed, and :func:`write_guard` — what every engine
pack writer passes as ``allow_live_install`` — refuses any write root
that does not resolve inside the copy dir while a copy is armed.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

import O4_UI_Utils as UI

__all__ = ["copy_dir", "ensure_copy", "write_guard"]

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


def _inside(path: str, root: str) -> bool:
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def _links_in(tree: str) -> list:
    """Every symlink under ``tree`` (a write through one leaves the copy)."""
    found = []
    for root, dirs, files in os.walk(tree):
        found += [os.path.join(root, n) for n in dirs + files
                  if os.path.islink(os.path.join(root, n))]
    return found


def write_guard(pack_root: str) -> bool:
    """``allow_live_install`` for an engine pack write rooted at
    ``pack_root``.  With no copy armed (the app) it is ``True``, as
    before.  With a copy armed the root must resolve inside the copy dir
    and hold no symlink, else ``PermissionError``: a lane build never
    writes the installed pack, whichever airport on the tile asks."""
    base = copy_dir()
    if base is None:
        return True
    links = _links_in(pack_root) if os.path.isdir(pack_root) else []
    if not _inside(pack_root, base) or links or os.path.islink(pack_root):
        raise PermissionError(
            f"REFUSING a pack write outside the pack copy (#2041): "
            f"{pack_root!r} resolves to {os.path.realpath(pack_root)!r}, "
            f"not inside {base!r}"
            + (f" ({len(links)} symlink(s) inside, e.g. {links[0]!r})"
               if links else ""))
    return True


def ensure_copy(pack_root: str) -> str | None:
    """``_copy_root(pack_root)``, cloned from the installed pack on first
    use (APFS ``clonefile`` through ``cp -c`` on macOS: no bytes are
    copied until one is rewritten on the same volume; a real copy across
    volumes or elsewhere).  The pack's RESOLVED directory is copied with
    every symlink followed (#2041), and the result is checked by
    :func:`write_guard`.  ``None`` when no pack copy is armed."""
    target = _copy_root(pack_root)
    if target is None:
        return None
    if os.path.islink(target):
        os.unlink(target)             # a pre-#2041 copy: the link only
    if not os.path.isdir(target):
        source = os.path.realpath(pack_root)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if sys.platform == "darwin":
            subprocess.run(["cp", "-cRL", source, target], check=True,
                           **UI.external_tool_keyword_arguments())
        else:
            shutil.copytree(source, target, symlinks=False)
    write_guard(target)
    return target
