"""LOCAL PATHS OUT OF A BUNDLE, AND BACK IN (#1699 phase 1).

The files a tile build writes name the machine that built them: the
patches' provenance stamps name the apt.dat, the CIFP file, the pack DSF
and the elevation insets they were read from; the object plans name the
pack's objects; the step records name every input file.  A bundle
carries none of those paths (design: "with local paths stripped").  On
export every one is replaced by a TOKEN naming the root it lies under
(:func:`roots`); on import each token is spelled with this machine's own
root, and a pack the user keeps under another folder name is renamed on
the way in (:func:`detokenise`, ``renames``).

A path appears in three spellings — as is, URL-quoted with ``/`` kept
(``o4_apt_dat``), and URL-quoted whole (``o4_dsf``, the identity lists) —
and each spelling has its own token, so the import writes the same
spelling with its own root.  A JSON file is rewritten through its parsed
strings (escapes are the JSON writer's), a patch only in its first two
lines (the XML declaration and the ``<osm …>`` stamps — the patch BODY,
which ``rebake_screen.patch_body_sha256`` hashes, is never touched).
:func:`leftovers` is the export's last check: a bundle text that still
holds a local root or the home folder is refused.
"""
from __future__ import annotations

import json
import os
import urllib.parse

__all__ = ["TOKENS", "roots", "tokenise_text", "detokenise_text",
           "transform_file_bytes", "leftovers"]

#: The token names, outermost root last (a longer root is replaced first).
TOKENS = ("build", "patches", "masks", "mod_cache", "custom_scenery",
          "xplane", "data")

#: The spellings of a path, by token suffix.
_SPELLINGS = {
    "": lambda p: p,
    "q": lambda p: urllib.parse.quote(p, safe="/"),
    "qq": lambda p: urllib.parse.quote(p, safe=""),
}

#: The data root's folders a build names (``O4_File_Names``).
_DATA_DIRS = ("OSM_dir", "Elevation_dir", "Imagery_dir", "Geotiff_dir",
              "Patch_dir", "Tile_dir", "Tmp_dir", "Overlay_dir",
              "Default_dsf_cache_dir")


def roots(tile, custom_scenery_dir: str, xplane_root: str | None) -> list:
    """``[(token, absolute root)]`` of THIS machine for ``tile``, longest
    root first — each root as given and as its real path (the data
    folders of a lane are links into the shared data repo)."""
    import O4_File_Names as FNAMES
    pairs = []

    def add(token: str, path: str | None) -> None:
        if not path:
            return
        for spelled in {os.path.normpath(path), os.path.realpath(path)}:
            if len(spelled) > 1:
                pairs.append((token, spelled))

    add("build", tile.build_dir)
    add("patches", FNAMES.patch_dir(tile.lat, tile.lon))
    add("masks", FNAMES.mask_dir(tile.lat, tile.lon))
    add("mod_cache", FNAMES.airport_mod_cache_root())
    add("custom_scenery", custom_scenery_dir)
    add("xplane", xplane_root)
    for name in _DATA_DIRS:
        folder = getattr(FNAMES, name, "")
        if folder:
            base = os.path.basename(os.path.normpath(folder))
            add("data/" + base, folder)
            real = os.path.realpath(folder)
            if os.path.basename(real) == base:     # a linked data folder:
                add("data", os.path.dirname(real))  # its own data root
    add("data", FNAMES.current_data_root())
    return sorted(set(pairs), key=lambda pair: (-len(pair[1]), pair[0]))


def _token(name: str, suffix: str) -> str:
    return "{%s%s}" % (name, "|" + suffix if suffix else "")


def tokenise_text(text: str, pairs) -> str:
    """``text`` with every root of ``pairs`` (in each spelling) replaced
    by its token."""
    for name, root in pairs:
        for suffix, spell in _SPELLINGS.items():
            spelled = spell(root)
            if spelled in text:
                text = text.replace(spelled, _token(name, suffix))
    return text


def detokenise_text(text: str, pairs, renames=None) -> str:
    """The inverse of :func:`tokenise_text` with THIS machine's roots
    (``pairs``: one root per token); ``renames`` maps a pack folder name
    the bundle names to the one installed here."""
    for old, new in (renames or {}).items():
        for suffix, spell in _SPELLINGS.items():
            text = text.replace(_token("custom_scenery", suffix) + spell("/" + old),
                                _token("custom_scenery", suffix) + spell("/" + new))
    for name, root in pairs:
        for suffix, spell in _SPELLINGS.items():
            text = text.replace(_token(name, suffix), spell(root))
    return text


def _walk_strings(value, change):
    if isinstance(value, str):
        return change(value)
    if isinstance(value, list):
        return [_walk_strings(item, change) for item in value]
    if isinstance(value, dict):
        return {change(k) if isinstance(k, str) else k: _walk_strings(v, change)
                for k, v in value.items()}
    return value


def _osm_head(data: bytes, change) -> bytes:
    lines = data.split(b"\n")
    head = [change(line.decode("utf-8")).encode("utf-8") for line in lines[:2]]
    return b"\n".join(head + lines[2:])


def transform_file_bytes(name: str, data: bytes, change) -> bytes:
    """``data`` of the bundle file ``name`` with ``change`` applied to its
    path-bearing text: a JSON file's strings, a patch's first two lines,
    nothing in a binary file."""
    if name.endswith(".json"):
        doc = json.loads(data.decode("utf-8"))
        out = _walk_strings(doc, change)
        return (json.dumps(out, sort_keys=False, indent=1) + "\n").encode("utf-8") \
            if out != doc else data
    if name.endswith(".osm"):
        return _osm_head(data, change)
    return data


def leftovers(data: bytes, pairs, extra=()) -> list:
    """The local roots (and ``extra`` paths, the home folder) still named
    in ``data``, in any spelling — a bundle holding one is refused."""
    found = []
    for root in [r for _n, r in pairs] + list(extra):
        for spell in _SPELLINGS.values():
            if spell(root).encode("utf-8") in data:
                found.append(root)
                break
    return sorted(set(found))
