"""THE LIBRARY REPOSITORY'S LAYOUT (#1699 phase 2) — stdlib only; the
library's own checks and index rebuild read it from a sparse checkout.

::

    README.md  LICENSE.md  publishers.json  licences.json
    entries/<ICAO>/<pack>/<pack version>/v<N>/
        manifest.json        the match key, versions, hashes, sources
        edits.json           the user edits and role overrides
        ATTRIBUTION.txt      built from the manifest
        solved/<file>.xz     the solved patch family, xz-compressed
        edits/<file>.xz      the edited patch, when the entry has one
    index/<region>.json      per 10-degree region: every airport's entries

``<pack>`` is the pack folder's name made safe for a path (display only:
an entry is matched by its signature, never a name), ``<pack version>``
the first 12 hex of the pack signature, ``v<N>`` the entry's version
(1, 2, … — publishing an improvement adds the next one; older versions
stay).  ``<region>`` is the 10-degree group of the airport's tile
(``+40-130`` for ``+45-123``).
"""
from __future__ import annotations

import re

__all__ = ["ENTRIES", "INDEX", "MANIFEST", "EDITS", "ATTRIBUTION",
           "SOLVED", "EDITED", "PUBLISHERS", "LICENCES", "SOLVED_NAME_RE",
           "EDITED_NAME_RE", "TILE_RE", "ICAO_RE", "pack_slug", "entry_dir",
           "parse_entry_dir", "region_of", "index_path"]

ENTRIES = "entries"
INDEX = "index"
MANIFEST = "manifest.json"
EDITS = "edits.json"
ATTRIBUTION = "ATTRIBUTION.txt"
SOLVED = "solved"
EDITED = "edits"
PUBLISHERS = "publishers.json"
LICENCES = "licences.json"

#: An airport code as the engine names patches (``O4_File_Names``).
ICAO_RE = re.compile(r"^[A-Z0-9]{2,8}$")

#: A tile key, ``+45-123``.
TILE_RE = re.compile(r"^([+-]\d{2})([+-]\d{3})$")

#: The solved files an entry may carry (the patch family of
#: ``O4_Unpatched_Airports.PATCH_FAMILY`` and its companion plans), each
#: compressed: ``solved/<name>.xz``.
SOLVED_NAME_RE = re.compile(
    r"^(?P<icao>[A-Z0-9]{2,8})(?:_auto\.patch\.osm(?:\.axes\.json)?|\.graded\.json)$"
    r"|^o4_v2_rebake_(?P<plan>[A-Z0-9]{2,8})(?:~\d+)?(?:\.screen)?\.json$")

#: The edited patch an entry may carry: ``edits/<ICAO>_edited.patch.osm.xz``.
EDITED_NAME_RE = re.compile(r"^(?P<icao>[A-Z0-9]{2,8})_edited\.patch\.osm$")

_SLUG_RE = re.compile(r"[^A-Za-z0-9 ._()+-]+")


def pack_slug(name: str) -> str:
    """A pack folder name made safe as one path part (display only)."""
    slug = _SLUG_RE.sub("_", name or "").strip(" .")
    return (slug or "pack")[:96]


def entry_dir(icao: str, pack: str, signature: str, version: int) -> str:
    """``entries/<ICAO>/<pack>/<pack version>/v<N>`` (``/``-separated)."""
    return "/".join((ENTRIES, icao.upper(), pack_slug(pack),
                     signature[:12], "v%d" % int(version)))


_ENTRY_DIR_RE = re.compile(
    r"^entries/(?P<icao>[A-Z0-9]{2,8})/(?P<pack>[^/]+)/(?P<sig>[0-9a-f]{12})"
    r"/v(?P<version>[1-9]\d*)$")


def parse_entry_dir(path: str) -> dict | None:
    """``{"icao", "pack", "sig", "version"}`` of an entry folder, or
    ``None`` when ``path`` is not one."""
    m = _ENTRY_DIR_RE.match(path.strip("/"))
    if m is None or m.group("pack") in (".", ".."):
        return None
    out = m.groupdict()
    out["version"] = int(out["version"])
    return out


def region_of(tile: str) -> str:
    """The 10-degree region of a tile key: ``+45-123`` -> ``+40-130``."""
    m = TILE_RE.match(tile or "")
    if m is None:
        raise ValueError("%r is not a tile key" % tile)
    lat, lon = int(m.group(1)), int(m.group(2))
    return "%+03d%+04d" % (lat // 10 * 10, lon // 10 * 10)


def index_path(region: str) -> str:
    """``index/<region>.json``."""
    return "%s/%s.json" % (INDEX, region)
