"""World drape tiles in the on-demand index, so the follow job sharpens
them too (#2037).

A drape (``O4_World_Drape``: a tile's photos laid over X-Plane's own
mesh, at the drape's 512 or 1024 px) is swapped into the World pack's
``textures/<tile>`` and ``terrain/<tile>`` with no build folder left
behind, and had no index rows: the follow job could never land a finer
tier over it.  :func:`register` writes them when the drape swaps in
(``world_publish._after_swap``):

* a ROWS FOLDER of the tile under the store (its rows folder) stands in
  for its build folder: its imagery manifest says ``kind: drape`` and
  names the pack's folders (``INDEX.LAYOUT_KEY``), so every row reads and
  lands the pack's textures; the converter writes there first;
* every texture of the drape is kept as the row's placeholder
  (hard-linked into the rows folder's ``placeholders/<tile>``, copied
  across volumes; never the store's own placeholders, which a full build
  of the tile owns), so a downgrade lands the drape's own file again;
* the rows themselves come from ``INDEX.rebuild`` over that folder (it
  reads a drape's ``.pol`` as it reads a ``.ter``).

The lander (``imagery_follow_land.TierLander``) treats a row of a rows
folder as a drape's (:func:`is_drape_dir`): the tile object is set up as
the drape's fetch sets it up (:func:`prepare`: no colour field, alpha
imprinted, the provider blend its World pack record says it was made
with, #2018), a WATER square (its kept file is DXT5: the water copy draws
its alpha) has that alpha imprinted into the finer tier
(:func:`water_mask`: the drape's mask, decoded by ``O4_DDS_Alpha`` and
scaled by the converter), and the converter's copy in the rows folder is
removed once landed (:func:`landed`).  When a full tile replaces the
drape, :func:`forget` removes the rows folder (the full tile's rows
replace the drape's in the index).
"""
from __future__ import annotations

import contextlib
import json
import os

import O4_Imagery_OnDemand_Index as INDEX

__all__ = ["DRAPE_KIND", "forget", "is_drape_dir", "landed", "prepare",
           "register", "water_mask"]

#: The imagery manifest's ``kind`` of a drape's rows folder.
DRAPE_KIND = "drape"


def _store() -> str:
    import O4_File_Names as FNAMES
    import O4_Imagery_Placeholder as PLACEHOLDER
    return FNAMES.data_path(PLACEHOLDER.STORE_DIR)


def _rows_dir(tile: str, store: "str | None" = None) -> str:
    """The rows folder of drape tile ``tile`` (``+53-114``)."""
    return os.path.join(store or _store(), "drapes", f"zOrtho4XP_{tile}")


def _manifest_path(folder: str, tile: str) -> str:
    return os.path.join(folder, f"Ortho4XP_{tile}_imagery.json")


def is_drape_dir(folder) -> bool:
    """Is ``folder`` a drape's rows folder (its manifest's ``kind``)?"""
    if not folder:
        return False
    tile = os.path.basename(os.path.normpath(folder)).replace("zOrtho4XP_", "")
    try:
        with open(_manifest_path(folder, tile), encoding="utf-8") as handle:
            return json.load(handle).get("kind") == DRAPE_KIND
    except (OSError, ValueError, AttributeError):
        return False


def _textures(folder: str) -> "set[str]":
    with contextlib.suppress(OSError):
        return {item.name for item in os.scandir(folder)
                if item.name.endswith(".dds") and item.is_file()}
    return set()


def _keep(src: str, dst: str) -> None:
    """``dst`` the same file as ``src``: hard-linked, else copied."""
    import shutil
    partial = dst + ".keeping"
    with contextlib.suppress(OSError):
        os.remove(partial)
    try:
        os.link(src, partial)
    except OSError:
        shutil.copy2(src, partial)
    os.replace(partial, dst)


def register(pack: str, lat: int, lon: int, index: "str | None" = None,
             store: "str | None" = None) -> int:
    """The index rows of the drape tile ``(lat, lon)`` of the World pack
    ``pack`` (see the module); returns the rows written."""
    import O4_File_Names as FNAMES
    tile = FNAMES.short_latlon(lat, lon)
    store = store or _store()
    textures = os.path.join(pack, "textures", tile)
    terrain = os.path.join(pack, "terrain", tile)
    folder = _rows_dir(tile, store)
    keep_root = os.path.join(folder, "placeholders")
    kept = os.path.join(keep_root, tile)
    os.makedirs(os.path.join(folder, "textures"), exist_ok=True)
    os.makedirs(kept, exist_ok=True)
    names = _textures(textures)
    for name in names:
        _keep(os.path.join(textures, name), os.path.join(kept, name))
    for item in list(os.scandir(kept)):         # an older drape's files
        if item.name not in names:
            with contextlib.suppress(OSError):
                os.remove(item.path)
    manifest = {"kind": DRAPE_KIND, "on_demand": True,
                INDEX.LAYOUT_KEY: {"textures_dir": textures,
                                   "terrain_dir": terrain}}
    with open(_manifest_path(folder, tile), "w", encoding="utf-8",
              newline="\n") as handle:
        json.dump(manifest, handle, indent=1)
    conn = INDEX.open_index(index)
    try:
        return INDEX.rebuild(conn, [(folder, int(lat), int(lon))],
                             placeholder_root=keep_root)
    finally:
        conn.close()


def forget(lat: int, lon: int, store: "str | None" = None) -> bool:
    """A full tile replaced the drape: its rows folder (and the drape's
    kept files) removed; ``True`` when there was one."""
    import shutil

    import O4_File_Names as FNAMES
    folder = _rows_dir(FNAMES.short_latlon(lat, lon), store)
    if not os.path.isdir(folder):
        return False
    shutil.rmtree(folder, ignore_errors=True)
    return True


def prepare(tile) -> None:
    """A drape row's tile object as ``O4_World_Drape_Fetch`` sets up its
    own: no colour field, a mask imprinted into the alpha, and the
    provider blend the drape was made with (:func:`_blend_of`), so a
    finer tier lands in the colour of the tier it replaces."""
    tile.color_harmonization = False
    tile.provider_blend = _blend_of(tile)
    tile.imprint_masks_to_dds = True


def _blend_of(tile):
    """The provider blend of the drape whose rows folder is
    ``tile.build_dir``: rebuilt from the World pack record beside the
    textures its manifest names (``O4_World_Imagery_Record``); None when
    there is none or it does not read."""
    import O4_File_Names as FNAMES
    import O4_Imagery_Provider_Blend as BLEND
    import O4_World_Imagery_Record as IREC
    name = FNAMES.short_latlon(tile.lat, tile.lon)
    try:
        with open(_manifest_path(tile.build_dir, name), encoding="utf-8") as handle:
            textures = json.load(handle)[INDEX.LAYOUT_KEY]["textures_dir"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    pack = os.path.dirname(os.path.dirname(os.path.normpath(textures)))
    record = IREC.read(pack, tile.lat, tile.lon)
    return BLEND.from_record(tile.lat, tile.lon, record.get("blend") or {})


def water_mask(tile, row: dict, til_x: int, til_y: int) -> bool:
    """A water square (its kept placeholder is DXT5): its alpha written
    where the converter imprints a mask (``FNAMES.mask_file`` in the rows
    folder's ``textures``; scaled to the tier there).  ``False``: a land
    square, nothing written."""
    import O4_DDS_Alpha as ALPHA
    import O4_File_Names as FNAMES
    from PIL import Image
    kept = row.get("placeholder_path")
    alpha = ALPHA.alpha_of(kept) if kept else None
    if alpha is None:
        return False
    path = os.path.join(tile.build_dir, "textures", FNAMES.mask_file(
        til_x, til_y, int(row["zl"]), row["provider"]))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(alpha).save(path)
    return True


def landed(built: str) -> None:
    """The converter's copy in the rows folder, once landed in the pack."""
    with contextlib.suppress(OSError):
        os.remove(built)
