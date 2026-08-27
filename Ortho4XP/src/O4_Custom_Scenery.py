"""Survey of the packages installed in X-Plane's Custom Scenery folder.

What OTHER scenery already covers a tile is a question every front end
asks — the map draws it, the tile inspector names it — so the answer
lives engine-side, toolkit-free, and is consumed in-process by the Qt UI
exactly as the macOS application consumes its own scanner
(``Sources/SceneryKit/InstallationScanner.swift``).  This is that
scanner reduced to what a map and a tile inspector actually draw:
coverage, kind, status, and the pack's own airports.

Cheap by construction — one directory listing per pack plus one walk of
its ``Earth nav data`` tree; nothing is opened except a pack's own
``apt.dat``, which airport packs keep to a handful of rows.  Ortho4XP's
own installed tiles are NOT packs here: they are the front end's built
squares already, and drawing them twice is what the exclusions below
prevent.

``Global Airports`` is skipped outright: it is Laminar's, it covers the
whole globe, and its 35 000 airports are what
:mod:`O4_Airport_Index` already serves.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Iterator, Optional, Sequence, Set, Tuple

import O4_File_Names as FNAMES

__all__ = [
    "PackAirport",
    "SceneryPack",
    "PACK_KINDS",
    "disabled_pack_names",
    "iter_packs",
    "scan_packs",
    "packs_covering",
]

# Pack kinds, mirroring the macOS app's PackKind (Sources/SceneryKit/
# Models.swift) so the two front ends classify the same install the same
# way.  Classification is CONTENT-first; the name only breaks ties.
PACK_KINDS = ("airport", "ortho", "mesh", "landmark", "library", "other")

# Laminar's own packs, which never draw as third-party scenery.
_SKIPPED_PACKS = frozenset({"Global Airports"})

# Our own entries in Custom Scenery: per-tile links (zOrtho4XP_±XX±YYY),
# grouped-build links (zOrtho4XP_<dir>) and the shared overlay link.
_OURS_RE = re.compile(r"^(zOrtho4XP_|yOrtho4XP_Overlays$)")

_DSF_RE = re.compile(r"^([+-]\d{2})([+-]\d{3})\.dsf$", re.IGNORECASE)


@dataclass(frozen=True)
class PackAirport:
    """One airport a pack ships, as its ``apt.dat`` declares it."""

    icao: str
    name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class SceneryPack:
    """One entry of Custom Scenery, as far as a map needs it.

    ``path`` is the Custom Scenery entry itself (the identity X-Plane and
    the user see); ``content_root`` is where its files actually are — the
    two differ whenever the entry is a symlink, and READS must use the
    latter.
    """

    name: str
    path: str
    content_root: str
    #: "enabled" | "disabled" (SCENERY_PACK_DISABLED in scenery_packs.ini)
    status: str = "enabled"
    kind: str = "other"
    tiles: frozenset = field(default_factory=frozenset)
    airports: tuple = ()

    def covers(self, lat: int, lon: int) -> bool:
        return (int(lat), int(lon)) in self.tiles

    def dsf_path(self, lat: int, lon: int) -> str:
        """Where this pack's DSF for the tile would live."""
        return os.path.join(
            self.content_root,
            "Earth nav data",
            FNAMES.long_latlon(int(lat), int(lon)) + ".dsf",
        )

    def dsf_modified(self, lat: int, lon: int) -> Optional[float]:
        """mtime of this pack's DSF for the tile, or None if absent."""
        try:
            return os.path.getmtime(self.dsf_path(lat, lon))
        except OSError:
            return None


def disabled_pack_names(scenery_dir: str) -> Set[str]:
    """Pack folder names marked ``SCENERY_PACK_DISABLED``.

    A disabled pack sits in Custom Scenery but X-Plane never loads it, so
    it is reported — dimmed — rather than hidden.
    """
    disabled: Set[str] = set()
    ini_path = os.path.join(scenery_dir or "", "scenery_packs.ini")
    try:
        with open(ini_path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line.startswith("SCENERY_PACK_DISABLED"):
                    continue
                rest = line.split(None, 1)[1] if " " in line else ""
                if rest:
                    disabled.add(os.path.basename(rest.strip().rstrip("/\\")))
    except OSError:
        pass
    return disabled


def _pack_tiles(content_root: str) -> frozenset:
    """(lat, lon) of every ``Earth nav data`` DSF the pack ships.

    The tree is two levels deep by X-Plane's own convention
    (``±X0±Y00/±XX±YYY.dsf``), so this is a listing of the nav-data folder
    plus one listing per decade folder — never a full-pack walk.
    """
    nav = os.path.join(content_root, "Earth nav data")
    tiles = set()
    try:
        groups = os.listdir(nav)
    except OSError:
        return frozenset()
    for group in groups:
        group_dir = os.path.join(nav, group)
        try:
            names = os.listdir(group_dir)
        except OSError:
            continue
        for name in names:
            match = _DSF_RE.match(name)
            if match is not None:
                tiles.add((int(match.group(1)), int(match.group(2))))
    return frozenset(tiles)


def _pack_airports(content_root: str) -> tuple:
    """The pack's own airports, via THE apt.dat parser.

    A custom airport pack's ``apt.dat`` holds one airport or a few, so it
    is streamed straight through :func:`O4_Airport_Index.iter_airports`
    with no cache — the index cache exists for the 35 000-row Global
    Airports file, not for these.
    """
    apt_dat = os.path.join(content_root, "Earth nav data", "apt.dat")
    if not os.path.isfile(apt_dat):
        return ()
    try:
        import O4_Airport_Index as APT

        return tuple(
            PackAirport(entry.code, entry.name, entry.lat, entry.lon)
            for entry in APT.iter_airports(apt_dat)
        )
    except Exception:
        return ()


def _terrain_probe(content_root: str) -> Tuple[bool, bool]:
    """(has .ter scenery, holds photo-tile quantities of images).

    Ortho packs ship roughly one image per ``.ter`` — Ortho4XP in
    ``textures/``, others beside the ``.ter`` in ``terrain/`` — while an
    elevation mesh ships hundreds of ``.ter`` over a handful of textures.
    Capped listings: the answer is a ratio, not a census.
    """
    ter_count = 0
    image_count = 0
    for folder in ("terrain", "textures"):
        try:
            names = os.listdir(os.path.join(content_root, folder))
        except OSError:
            continue
        for name in names[:500]:
            lower = name.lower()
            if lower.endswith(".ter"):
                ter_count += 1
            elif lower.endswith((".dds", ".png", ".jpg", ".jpeg")):
                image_count += 1
    photo = image_count >= 20 or (image_count >= 5 and image_count >= ter_count)
    return (ter_count > 0, photo)


def _classify(name: str, content_root: str, tiles: frozenset,
              airports: tuple) -> str:
    """Pack kind, CONTENT first — the name only breaks ties.

    Mirrors ``SceneryPack.kind`` in the macOS app: name guessing alone
    misfiles orthos that carry no "ortho" in their name.
    """
    if os.path.isfile(os.path.join(content_root, "library.txt")) and not tiles:
        return "library"
    if airports:
        return "airport"
    if not tiles:
        return "other"
    lower = name.lower()
    (has_terrain, photo_textured) = _terrain_probe(content_root)
    if has_terrain:
        if photo_textured:
            return "ortho"
        return "ortho" if ("ortho" in lower or "photo" in lower) else "mesh"
    # No .ter content: an overlay pack (landmarks, roads) unless the name
    # says mesh.  The macOS scanner reads the sample DSF's overlay flag
    # here; a DSF is 7-zipped and decoding one per pack is not a price a
    # map redraw can pay, so the name is the tie-breaker on its own.
    return "mesh" if "mesh" in lower else "landmark"


def iter_packs(scenery_dir: str,
               exclude_roots: Sequence[str] = ()) -> Iterator[tuple]:
    """Yield ``(done, total, pack_or_None)`` for every Custom Scenery entry.

    Incremental so a live UI can show progress over the whole listing —
    the shape :func:`O4_Scenery_Links.iter_installed_tiles` established.
    ``pack`` is None for entries that are not third-party scenery: our own
    tile and overlay links, Laminar's packs, and anything whose resolved
    root is under ``exclude_roots`` (the caller's built-tile folders — a
    built tile is already ITS own square on the map).
    """
    if not scenery_dir or not os.path.isdir(scenery_dir):
        return
    disabled = disabled_pack_names(scenery_dir)
    excluded = {
        os.path.realpath(root) for root in exclude_roots if root
    }
    entries = sorted(os.listdir(scenery_dir))
    total = len(entries)
    for done, entry in enumerate(entries, start=1):
        pack = None
        path = os.path.join(scenery_dir, entry)
        if (entry not in _SKIPPED_PACKS
                and not _OURS_RE.match(entry)
                and os.path.isdir(path)):
            content_root = os.path.realpath(path)
            if content_root not in excluded:
                tiles = _pack_tiles(content_root)
                airports = _pack_airports(content_root)
                if tiles or airports:
                    pack = SceneryPack(
                        name=entry,
                        path=path,
                        content_root=content_root,
                        status=("disabled" if entry in disabled
                                else "enabled"),
                        kind=_classify(entry, content_root, tiles, airports),
                        tiles=tiles,
                        airports=airports,
                    )
        yield done, total, pack


def scan_packs(scenery_dir: str, exclude_roots: Sequence[str] = ()) -> list:
    """:func:`iter_packs` drained — the third-party packs, in name order."""
    return [
        pack
        for _done, _total, pack in iter_packs(scenery_dir, exclude_roots)
        if pack is not None
    ]


def packs_covering(packs: Sequence[SceneryPack], lat: int,
                   lon: int) -> list:
    """The packs whose DSF coverage includes the tile, in name order."""
    return [pack for pack in packs if pack.covers(lat, lon)]
