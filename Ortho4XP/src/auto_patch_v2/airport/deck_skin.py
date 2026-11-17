"""THE GENERATED DECK'S SKIN: X-Plane's own pavement art (#2132; owner
2026-11-17: "a much higher resolution, realistic concrete, with dirt and
tire marks going across it.  Like the cliffs, can we reference some laminar
texture resources that the user will already have installed").

The cliff overlay's precedent (``O4_Cliff_Library``): read a resource of
the user's X-Plane install by its LIBRARY path, and place its texture in
the pack ONCE as a link to the install (``O4_World_Pack.share_file``:
symbolic link, else hard link, else one copy) -- never shipped, never
re-drawn.  A generated deck reads two of X-Plane's airport pavement pages:

* ``[deck_gen] concrete_pol`` -- the slab: the page's ``TEXTURE`` (a
  1024 x 2048 albedo of slabbed, stained concrete), its ``TEXTURE_NORMAL``
  and its ``SCALE`` (the metres one repeat covers), so the deck's top tiles
  exactly as an apt.dat concrete taxiway beside it does;
* ``[deck_gen] rubber_pol`` -- the tire marks: the runway rubber page's
  alpha texture (``SCALE`` 30 x 30 m), laid as a film along the carried
  route's centreline.

A page the install does not resolve (no X-Plane beside the pack or in the
app's settings, a renamed library entry) leaves the deck on the generated
atlas (``deck_texture``) -- named in the object stage's line, never a
failure.  Nothing here names an airport.

Build-time impact: one library-index read (cached) and two small text
files per object-stage write; the links cost no bytes.
"""
from __future__ import annotations

import os
import typing as _t

__all__ = ["PageArt", "install_root", "page_art", "link_name"]

_DEFAULT_SCENERY = ("Resources", "default scenery")


class PageArt(_t.NamedTuple):
    """A pavement page's art: ``albedo`` / ``normal`` absolute paths
    (``normal`` ``""`` when it has none) and ``scale_m`` = the page's
    ``SCALE`` (metres across, along one repeat)."""

    albedo: str
    normal: str
    scale_m: tuple[float, float]


def install_root(apt_path: str) -> "str | None":
    """The X-Plane install whose library the deck reads: the install the
    pack stands in (an ancestor of its ``apt.dat`` holding ``Resources/
    default scenery``), else the one the app's settings name
    (``flat_site_mode.resolve_xplane_root``: the CIFP folder's install, then
    the Custom Scenery folder's parent) -- a pack copy in a scratch tree
    reads the user's install so."""
    d = os.path.dirname(os.path.abspath(apt_path)) if apt_path else ""
    while d and os.path.dirname(d) != d:
        if os.path.isdir(os.path.join(d, *_DEFAULT_SCENERY)):
            return d
        d = os.path.dirname(d)
    try:
        from auto_patch.flat_site_mode import resolve_xplane_root
        root = resolve_xplane_root()
    except Exception:                            # never fails the pack
        return None
    return root if root and os.path.isdir(os.path.join(root, *_DEFAULT_SCENERY)) else None


def _texture_file(pol_dir: str, name: str) -> "str | None":
    """The file a page's texture row names, as X-Plane finds it: the named
    file, else its ``.dds`` twin (the pages name ``.png`` and ship DDS)."""
    path = os.path.normpath(os.path.join(pol_dir, name))
    if os.path.isfile(path):
        return path
    dds = os.path.splitext(path)[0] + ".dds"
    return dds if os.path.isfile(dds) else None


def page_art(library_path: str, xplane_root: "str | None") -> "PageArt | None":
    """The :class:`PageArt` of the draped-polygon page at ``library_path``
    in ``xplane_root``'s library, or ``None`` when it does not resolve or
    names no texture."""
    if not library_path or not xplane_root:
        return None
    try:
        from auto_patch.agp_reader import resolve_library_path
        pol = resolve_library_path(library_path, xplane_root)
    except (OSError, ValueError):
        return None
    if not pol:
        return None
    try:
        with open(pol, encoding="utf-8", errors="replace") as fh:
            rows = [ln.split() for ln in fh]
    except OSError:
        return None
    first: dict[str, list[str]] = {}
    for r in rows:
        if r and r[0] not in first:
            first[r[0]] = r
    tex, nrm, scale = first.get("TEXTURE"), first.get("TEXTURE_NORMAL"), first.get("SCALE")
    folder = os.path.dirname(pol)
    albedo = _texture_file(folder, tex[1]) if tex and len(tex) >= 2 else None
    if albedo is None or not scale or len(scale) < 3:
        return None
    normal = _texture_file(folder, nrm[-1]) if nrm and len(nrm) >= 2 else None
    try:
        sw, sh = float(scale[1]), float(scale[2])
    except ValueError:
        return None
    if sw <= 0.0 or sh <= 0.0:
        return None
    return PageArt(albedo, normal or "", (sw, sh))


def link_name(path: str) -> str:
    """``xp_<file name>``: the name the pack's link carries (the cliff
    overlay's ``xp_`` prefix: X-Plane's art, linked, never ours)."""
    return "xp_" + os.path.basename(path)
