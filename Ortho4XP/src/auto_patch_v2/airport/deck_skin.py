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

Build-time impact: one library-index lookup (the caller's, cached) and two small text
files per object-stage write; the links cost no bytes.
"""
from __future__ import annotations

import os
import typing as _t

#: ``(virtual library path, X-Plane root) -> physical file | None``
Resolver = _t.Callable[[str, str], "str | None"]

__all__ = ["PageArt", "Resolver", "install_root", "page_art", "link_name", "texture_file",
           "laminar_first"]

_DEFAULT_SCENERY = ("Resources", "default scenery")


class PageArt(_t.NamedTuple):
    """A pavement page's art: ``albedo`` / ``normal`` absolute paths
    (``normal`` ``""`` when it has none) and ``scale_m`` = the page's
    ``SCALE`` (metres across, along one repeat).  The page's material
    rows the object repeats (spec 2132-design section 4; ``""`` where the
    page has none): ``weather`` its ``WEATHER`` map (absolute path: the
    rain / snow look), ``decal_lib`` its ``DECAL_LIB`` library path
    (verbatim: the close-up grain) and ``surface`` its ``SURFACE`` (the
    hard-deck surface name, ``concrete`` / ``asphalt``)."""

    albedo: str
    normal: str
    scale_m: tuple[float, float]
    weather: str = ""
    decal_lib: str = ""
    surface: str = ""
    #: the page draws the wet look of what lies under it (a film: paint,
    #: rubber) -- its ``WEATHER_TRANSPARENT`` row
    weather_transparent: bool = False


def install_root(apt_path: str) -> "str | None":
    """The X-Plane install whose library the deck reads: the install the
    pack stands in (an ancestor of its ``apt.dat`` holding ``Resources/
    default scenery``), else the one the app's settings name
    (``cifp.xplane_root_from_config``: the CIFP folder's install, then the
    Custom Scenery folder's parent) -- a pack copy in a scratch tree reads
    the user's install so."""
    d = os.path.dirname(os.path.abspath(apt_path)) if apt_path else ""
    while d and os.path.dirname(d) != d:
        if os.path.isdir(os.path.join(d, *_DEFAULT_SCENERY)):
            return d
        d = os.path.dirname(d)
    try:
        import O4_Config_Utils as _cfg

        from .cifp import xplane_root_from_config
        root = xplane_root_from_config(_cfg)
    except Exception:                            # never fails the pack
        return None
    return root if root and os.path.isdir(os.path.join(root, *_DEFAULT_SCENERY)) else None


def texture_file(pol_dir: str, name: str) -> "str | None":
    """The file a page's texture row names, as X-Plane finds it: the named
    file, else its ``.dds`` twin (the pages name ``.png`` and ship DDS)."""
    path = os.path.normpath(os.path.join(pol_dir, name))
    if os.path.isfile(path):
        return path
    dds = os.path.splitext(path)[0] + ".dds"
    return dds if os.path.isfile(dds) else None


def page_art(library_path: str, xplane_root: "str | None",
             resolve: "Resolver | None") -> "PageArt | None":
    """The :class:`PageArt` of the draped-polygon page at ``library_path``
    in ``xplane_root``'s library, or ``None`` when it does not resolve or
    names no texture.  ``resolve(virtual path, root)`` is the caller's
    library-index lookup (the object stage hands in X-Plane's merged
    ``library.txt`` index); ``None`` resolves nothing."""
    if not library_path or not xplane_root or resolve is None:
        return None
    try:
        pol = resolve(library_path, xplane_root)
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
    albedo = texture_file(folder, tex[1]) if tex and len(tex) >= 2 else None
    if albedo is None or not scale or len(scale) < 3:
        return None
    normal = texture_file(folder, nrm[-1]) if nrm and len(nrm) >= 2 else None
    try:
        sw, sh = float(scale[1]), float(scale[2])
    except ValueError:
        return None
    if sw <= 0.0 or sh <= 0.0:
        return None
    wm, dcl, srf = first.get("WEATHER"), first.get("DECAL_LIB"), first.get("SURFACE")
    weather = texture_file(folder, wm[-1]) if wm and len(wm) >= 2 else None
    decal = dcl[1] if dcl and len(dcl) >= 2 and _resolves(resolve, dcl[1], xplane_root) else ""
    return PageArt(albedo, normal or "", (sw, sh), weather or "", decal,
                   srf[1] if srf and len(srf) >= 2 else "", "WEATHER_TRANSPARENT" in first)


def _resolves(resolve: Resolver, library_path: str, root: str) -> bool:
    """Whether the install's library resolves ``library_path`` -- the
    witness that this X-Plane reads the page's ``DECAL_LIB`` (12.1+), so
    an object may carry it (spec 2132-design section 6)."""
    try:
        return bool(resolve(library_path, root))
    except (OSError, ValueError):
        return False


def link_name(path: str) -> str:
    """``xp_<file name>``: the name the pack's link carries (the cliff
    overlay's ``xp_`` prefix: X-Plane's art, linked, never ours)."""
    return "xp_" + os.path.basename(path)


def laminar_first(resolve: "Resolver | None") -> Resolver:
    """A resolver that reads X-Plane's OWN library first -- each
    ``Resources/default scenery/*/library.txt`` -- and ``resolve`` (the
    merged index) only for what Laminar does not export: the deck draws
    the art the user has installed with X-Plane, never a third-party
    pack's override of it (ESSA 2026-11-17: an airport pack's
    REGION-limited ``lib/airport/lines/1_single_taxi.lin`` won the merged
    index, which knows no regions)."""
    import glob

    from .obj8 import library_exports

    def look(path: str, root: str) -> "str | None":
        for lib in sorted(glob.glob(os.path.join(root, *_DEFAULT_SCENERY, "*", "library.txt"))):
            for phys in library_exports(lib).get(path.lower(), ()):
                if os.path.isfile(phys):
                    return phys
        return resolve(path, root) if resolve is not None else None
    return look
