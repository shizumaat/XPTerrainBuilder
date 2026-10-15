"""The patch editor's engine commands (spec patch-editor-20261015 §2,
protocol 1.12): ``patch_list``, ``patch_load``, ``patch_save``,
``patch_revert``.

Plain synchronous functions on the JSON-lines read loop (registered in
``o4_engine.jsonl``), like ``failure_report``: they read and write files in
one tile's ``Patches`` folder and nothing else — no build, no download.  A
refusal raises ``ValueError`` whose text is the user's sentence (the
transport replies ``ok: false`` with it).

What is reused, never re-spelled: patch file names and manual-patch
detection (``O4_File_Names``, the names the build's ``include_patches`` and
the driver read), the reuse gate's staleness computation
(``auto_patch.driver.auto_patch_stale_inputs``, §1.4), the law's identity
frame (the law table's ``emit.identity``) and the emitter's writing conventions
(``patch_file``).
"""
from __future__ import annotations

import os
import typing as _t

import O4_File_Names as FNAMES

from . import patch_file as PF


__all__ = ["patch_list", "patch_load", "patch_save", "patch_revert", "law_identity"]


def law_identity() -> tuple[float, int]:
    """``(min_distinct_spacing_m, coordinate_dp)`` from the checked-in law
    table — served by ``patch_load`` (the UI's snap radius, §3.3) and the
    precision ``patch_save`` writes lat/lon at; never spelled here."""
    from auto_patch_v2.law.tables import load_default
    identity = load_default().tables.emit.identity
    return float(identity.min_distinct_spacing_m), int(identity.coordinate_dp)


def _tile(tile: str) -> tuple[int, int]:
    parsed = FNAMES.parse_tile_key(tile)
    if parsed is None:
        raise ValueError(f"tile {tile!r} is not a tile name; send it as "
                         f"'+45-123' (latitude then longitude)")
    return parsed


def _patch_dir(tile: str) -> str:
    return FNAMES.patch_dir(*_tile(tile))


def _effective_patch(directory: str, icao: str) -> tuple[str, str] | None:
    """``(source, path)`` of the patch the build applies for *icao*: a
    manual patch (the editor's own ``<ICAO>_edited.patch.osm`` first, else
    the first hand-made one) over the auto patch."""
    import O4_Vector_Map as VMAP
    manual = VMAP.manual_patch_files_for(directory, icao)
    if manual:
        own = FNAMES.edited_patch_name(icao)
        return "manual", os.path.join(directory, own if own in manual else manual[0])
    auto = os.path.join(directory, FNAMES.auto_patch_name(icao))
    return ("auto", auto) if os.path.isfile(auto) else None


def patch_list(tile: str) -> dict:
    """ENGINE COMMAND ``patch_list``: the airports with a patch in *tile*'s
    Patches folder, each with the patch the build applies."""
    directory = _patch_dir(tile)
    icaos = sorted({FNAMES.patch_file_icao(f) for f in
                    (os.listdir(directory) if os.path.isdir(directory) else ())
                    if FNAMES.patch_file_icao(f)})
    airports = []
    for icao in icaos:
        found = _effective_patch(directory, icao)
        if found is None:
            continue
        source, path = found
        doc = PF.read_patch(path)
        airports.append({"icao": icao, "source": source, "path": path,
                         "bbox": doc.bbox(), "nodes": len(doc.nodes),
                         "ways": len(doc.ways)})
    return {"airports": airports}


def _staleness(tile: str, icao: str, doc: PF.PatchFile, source: str
               ) -> tuple[bool, list[str]]:
    """(§1.4) Whether today's inputs would build a different patch than the
    one the edit started from, and the stamp names that moved.  A patch
    that recorded no stamps (a hand-made file) is never stale."""
    from auto_patch.build_support import parse_patch_source, read_patch_source
    if source == "auto":
        meta = read_patch_source(doc.path)
    else:
        line = PF.recorded_stamps_line(doc.root_raw)
        meta = parse_patch_source(line) if line else None
    if not meta:
        return False, []
    import O4_Config_Utils as CFG
    import O4_Vector_Map as VMAP
    from auto_patch import driver
    from auto_patch.cifp_reader import (discover_cifp_airports,
                                        xplane_root_from_cifp_path)
    lat, lon = _tile(tile)
    t = CFG.Tile(lat, lon, "")
    t.read_from_config()
    cifp_dir = VMAP.resolve_cifp_dir_for_tile(t)
    xp_root = xplane_root_from_cifp_path(cifp_dir) if cifp_dir else None
    if xp_root is None:
        return True, ["unverifiable: no X-Plane CIFP folder is set, so the "
                      "build inputs cannot be compared"]
    stale = driver.auto_patch_stale_inputs(
        meta, doc.path, xp_root, icao, tile=t,
        cifp_file=discover_cifp_airports(cifp_dir).get(icao))
    return bool(stale), [key for key, _was, _now in stale]


def patch_load(tile: str, icao: str) -> dict:
    """ENGINE COMMAND ``patch_load``: the patch the build applies for
    *icao*, as the §2 document."""
    icao = str(icao).upper()
    found = _effective_patch(_patch_dir(tile), icao)
    if found is None:
        raise ValueError(f"{icao} has no patch in tile {tile}: build this "
                         f"tile first")
    source, path = found
    doc = PF.read_patch(path)
    stale, stale_inputs = _staleness(tile, icao, doc, source)
    spacing, dp = law_identity()
    return {"icao": icao, "source": source, "path": path, "stale": stale,
            "stale_inputs": stale_inputs, "min_distinct_spacing_m": spacing,
            "identity_dp": dp, "header": doc.header, "nodes": doc.nodes,
            "ways": doc.ways}


def _save_target(directory: str, icao: str, base_path: str) -> str:
    """Where ``patch_save`` writes: back into a hand-made manual patch the
    edit started from, else ``<ICAO>_edited.patch.osm`` (§1.2)."""
    name = os.path.basename(base_path)
    if os.path.realpath(os.path.dirname(base_path)) != os.path.realpath(directory) \
            or FNAMES.patch_file_icao(name) != icao:
        raise ValueError(f"{base_path} is not a patch of {icao} in this tile's "
                         f"Patches folder; reload the airport and save again")
    if FNAMES.is_manual_patch_name(name):
        return base_path
    return os.path.join(directory, FNAMES.edited_patch_name(icao))


def patch_save(tile: str, icao: str, base_path: str,
               nodes: _t.Sequence[_t.Sequence], ways: _t.Sequence[_t.Mapping]) -> dict:
    """ENGINE COMMAND ``patch_save``: write the edited document as a MANUAL
    patch (atomically), its header re-keyed from *base_path*'s (§1.2).
    Nodes and ways are written in the order given, tags unchanged; nothing
    is merged or moved here."""
    icao = str(icao).upper()
    directory = _patch_dir(tile)
    target = _save_target(directory, icao, base_path)
    base = PF.read_patch(base_path)
    from auto_patch_v2.emit.graded import z_decimals
    from auto_patch_v2.law.tables import load_default
    _spacing, dp = law_identity()
    text = PF.render(PF.edited_header(base.root_raw), nodes, ways, base.node_tags,
                     base.extras, identity_dp=dp, z_dp=z_decimals(load_default()))
    PF.write_atomic(target, text)
    return {"path": target, "nodes": len(nodes), "ways": len(ways)}


def patch_revert(tile: str, icao: str) -> dict:
    """ENGINE COMMAND ``patch_revert``: rename ``<ICAO>_edited.patch.osm``
    to ``….disabled`` (never deleted; a name already taken gets ``.2``,
    ``.3`` …) so the next build applies the auto patch again."""
    icao = str(icao).upper()
    path = os.path.join(_patch_dir(tile), FNAMES.edited_patch_name(icao))
    if not os.path.isfile(path):
        raise ValueError(f"{icao} has no edited patch in tile {tile} to "
                         f"revert; a hand-made patch is renamed by hand")
    target = path + ".disabled"
    n = 2
    while os.path.exists(target):
        target = f"{path}.disabled.{n}"
        n += 1
    os.rename(path, target)
    return {"disabled_path": target}
