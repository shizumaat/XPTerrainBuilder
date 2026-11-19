"""WHETHER A SCENERY PACK CAN BE WRITTEN, and making it so (#2174).

A pack unzipped from some archives arrives with its folders read-only
(``dr-xr-xr-x``) while the files inside are writable.  Every pack write
of a build (the pack lock, the flatten removal's temporary file, a DSF
or body file written beside its original) creates a NEW file in one of
those folders, so every one of them fails — and before #2174 the pack
lock reported that as "another write held its lock for 900 s".

* :func:`readonly_folders` — the pack's folders a write cannot create a
  file in.  Portable: ``os.access`` on every folder, then a probe file in
  the folders a write always uses (the pack root, its ``Earth nav data``
  and DSF folders), because on Windows ``os.access`` ignores a folder's
  access-control list.
* :func:`make_writable` — the user's "Make writable": adds the OWNER'S
  write permission (``u+w``) to the pack's folders and files, nothing
  else, and only for a pack directly inside a ``Custom Scenery`` folder
  that is not X-Plane's own.  POSIX only (Windows keeps its ACLs: the
  refusal says where to change them).
* :class:`PackReadOnlyError` — a pack write refused because the pack is
  read-only (a ``PermissionError``, so every writer's handling of a
  refused write applies).
"""
from __future__ import annotations

import os
import stat
import tempfile
import typing as _t

__all__ = ["PackReadOnlyError", "readonly_folders", "make_writable",
           "relative_folders"]

#: the folder X-Plane's scenery packs live in; nothing else is changed
CUSTOM_SCENERY = "Custom Scenery"
#: X-Plane's own airports pack (X-Plane 12 and 11 names): never changed
_DEFAULT_PACKS = ("*GLOBAL_AIRPORTS*", "Global Airports")


class PackReadOnlyError(PermissionError):
    """A pack write refused at once: the pack's folders are read-only."""

    def __init__(self, pack_root: str, folders: _t.Sequence[str] = (),
                 detail: str = "") -> None:
        self.pack_root = pack_root
        self.folders = list(folders)
        name = os.path.basename(os.path.normpath(pack_root))
        where = ", ".join(relative_folders(pack_root, self.folders)[:3])
        super().__init__(
            f"{name!r} is read-only (as it was downloaded)"
            + (f": {where}" if where else "")
            + (f" ({detail})" if detail else "")
            + "; nothing was written")


def relative_folders(pack_root: str, folders: _t.Iterable[str]) -> list[str]:
    """``folders`` as the user reads them: inside the pack, which is named."""
    name = os.path.basename(os.path.normpath(pack_root))
    out = []
    for f in folders:
        rel = os.path.relpath(f, pack_root)
        out.append(name if rel == "." else os.path.join(name, rel))
    return out


def _probe(folder: str) -> bool:
    """A file can be created (and removed) in ``folder``."""
    try:
        fd, path = tempfile.mkstemp(prefix=".o4_write_probe_", dir=folder)
    except OSError:
        return False
    os.close(fd)
    try:
        os.remove(path)
    except OSError:
        pass
    return True


def _write_folders(pack_root: str) -> list[str]:
    """The folders every pack write uses: the root, ``Earth nav data`` and
    its DSF folders."""
    nav = os.path.join(pack_root, "Earth nav data")
    out = [pack_root]
    if os.path.isdir(nav):
        out.append(nav)
        out += sorted(e.path for e in os.scandir(nav)
                      if e.is_dir(follow_symlinks=False))
    return out


def readonly_folders(pack_root: str) -> list[str]:
    """The pack's folders a write cannot create a file in, in walk order
    (``[]``: writable, or no such folder).  Never raises."""
    if not pack_root or not os.path.isdir(pack_root):
        return []
    try:
        bad = [d for d, _dirs, _files in os.walk(pack_root)
               if not os.access(d, os.W_OK)]
        seen = set(bad)
        bad += [d for d in _write_folders(pack_root)
                if d not in seen and not _probe(d)]
    except OSError:
        return [pack_root]
    return bad


def _refusal(pack_root: str) -> str:
    """Why :func:`make_writable` must not touch ``pack_root``, or ``""``."""
    root = os.path.abspath(pack_root or "")
    if os.name == "nt":
        return ("on Windows, clear the folder's Read-only setting in its "
                "Properties (or give your account Write permission there)")
    if not os.path.isdir(root):
        return "the pack folder is not there"
    if os.path.basename(os.path.dirname(root)) != CUSTOM_SCENERY:
        return f"only a pack directly inside {CUSTOM_SCENERY!r} is changed"
    if (os.path.basename(root) in _DEFAULT_PACKS
            or "Resources" in root.split(os.sep)):
        return "X-Plane's own scenery is never changed"
    return ""


def make_writable(pack_root: str) -> list[str]:
    """Add the owner's write permission (``u+w``) to every folder and
    file of ``pack_root`` that lacks it; a symbolic link is never followed
    or changed.  Returns the paths changed.  Raises ``PermissionError``
    with the user's sentence when the pack may not be changed."""
    why = _refusal(pack_root)
    if why:
        raise PermissionError(why)
    changed: list[str] = []

    def add(path: str) -> None:
        st = os.lstat(path)
        if stat.S_ISLNK(st.st_mode) or st.st_mode & stat.S_IWUSR:
            return
        os.chmod(path, stat.S_IMODE(st.st_mode) | stat.S_IWUSR)
        changed.append(path)

    add(pack_root)
    for folder, dirs, files in os.walk(pack_root):
        for name in dirs + files:            # a folder before os.walk enters it
            add(os.path.join(folder, name))
    return changed
