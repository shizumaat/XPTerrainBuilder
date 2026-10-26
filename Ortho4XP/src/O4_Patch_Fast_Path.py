"""FAST PATH A: a height-only patch edit skips the vector step (#1323, spec
``docs/specs/incremental-patch-edit-spec.md`` §3A; owner RULINGS
2026-10-26h Q150: it starts by itself on "Rebuild tile", with a log line).

When the only change since the vector step last ran is the CONTENT of one or
more airport patch files, and that change is HEIGHT-ONLY — the same nodes at
the same coordinates, the same ways, relations and tags, only node
``alt_abs`` values differ, each present before and after — then a full
vector step would write the same ``.poly``, ``.alt``, ``.apt`` and sidecar
and the same ``.node`` but for the z of the nodes those heights reach (spec
§3A.3: no pass of the step reads a patch node's height except
``include_patches``, and topology never reads z).  Those z values are
replayed from the z-provenance log the last full step wrote
(``O4_ZProv``) and rewritten in place; every other byte of the ``.node`` is
kept.  The vector step is then recorded as run, and the mesh, masks and
scenery-file steps run as they would after it.

Anything else, or any doubt, builds the vector step in full and says why
(spec §3A.4): a non-height change, ``alt_abs`` added or removed, a missing
log or copy of the patch as built (``fast_path/prev/``, cleared when the
app quits unless the tile's ``keep_edit_cache`` is on — ``O4_Edit_Cache``),
an airport the last build left without a patch, any other input or output
change, reuse off, an iterated mesh.

The patch copies are taken when the vector step is recorded
(:func:`after_step_recorded`), so they are the patch AS BUILT.  The step
decision (:func:`step_decision`) is the one the app session and
``tools/profile_tile_build.py --reuse`` both use.
"""
from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field

import O4_Edit_Cache as EDITCACHE
import O4_File_Names as FNAMES
import O4_Step_Reuse as REUSE
import O4_UI_Utils as UI
import O4_ZProv as ZPROV

__all__ = ["FastPathResult", "prev_dir", "height_only_diff",
           "try_height_edit", "after_step_recorded", "step_decision",
           "UPDATED_LABEL"]

#: the progress label of a vector step the fast path updated
UPDATED_LABEL = "%s · updated for a height edit"


@dataclass
class FastPathResult:
    """What :func:`try_height_edit` did.  ``relevant``: a patch-only change
    was found, so a refusal is worth a log line."""
    applied: bool
    why: str | None = None
    relevant: bool = False
    patches: list = field(default_factory=list)
    heights_changed: int = 0
    nodes_rewritten: int = 0
    seconds: float = 0.0


def prev_dir(tile) -> str:
    """Where the patches as last built are kept (part of the edit cache)."""
    return os.path.join(EDITCACHE.cache_dir(tile.build_dir), "prev")


def _layer(path: str):
    """The patch as ``include_patches`` reads it (the same parser)."""
    import O4_OSM_Utils as OSM
    layer = OSM.OSM_layer()
    if not layer.update_dicosm(path, input_tags=None, target_tags=None):
        raise ValueError("could not read %s" % os.path.basename(path))
    return layer


def height_only_diff(old_path: str, new_path: str):
    """``(node ids whose alt_abs changed, None)`` when ``new_path`` differs
    from ``old_path`` in node ``alt_abs`` values only, as the vector step
    parses them; else ``(None, why)``.  The ids are the parser's own, the
    ones the z-provenance log names."""
    try:
        old, new = _layer(old_path), _layer(new_path)
    except Exception as error:
        return None, str(error)
    if old.dicosmn != new.dicosmn:
        return None, "a patch node moved, or was added or removed"
    if (old.dicosmw != new.dicosmw or old.dicosmfirst != new.dicosmfirst
            or old.dicosmr != new.dicosmr
            or old.dicosmrorig != new.dicosmrorig):
        return None, "a patch way or relation changed"
    for kind in ("w", "r"):
        if old.dicosmtags[kind] != new.dicosmtags[kind]:
            return None, "a patch way's tags changed"
    old_tags, new_tags = old.dicosmtags["n"], new.dicosmtags["n"]
    if set(old_tags) != set(new_tags):
        return None, "a patch node's tags were added or removed"
    changed = []
    for node, tags in old_tags.items():
        other = new_tags[node]
        if set(tags) != set(other):
            return None, "a patch node tag (alt_abs?) was added or removed"
        for key, value in tags.items():
            if other[key] != value:
                if key != "alt_abs":
                    return None, "a patch node tag other than alt_abs changed"
                changed.append(node)
    return sorted(set(changed)), None


def _base_values(edited: dict):
    """The replay's ``base_value``: an edited patch's new ``alt_abs`` as
    ``include_patches`` stores it (into an array of the recorded dtype,
    then widened), else the recorded value."""
    import numpy

    def base_value(src, recorded):
        (patch, node, dtype) = src
        tags = edited.get(patch)
        if tags is None:
            return recorded
        text = tags[node]["alt_abs"]
        return float(numpy.dtype(dtype).type(float(text)))
    return base_value


def _rewrite_node_file(node_file: str, new_z: dict) -> int:
    """Rewrite the z of the nodes in ``new_z`` in ``write_node_file``'s own
    ``{z:.9f}``, every other byte copied; the number of lines that changed.
    Raises ``ValueError`` on a node the file does not hold."""
    with open(node_file, encoding="utf-8", newline="") as handle:
        lines = handle.read().split("\n")
    direct = all(lines[n].split(" ", 1)[0] == str(n)
                 for n in new_z if 0 < n < len(lines))
    index = None if direct else {
        line.split(" ", 1)[0]: k for k, line in enumerate(lines[1:], 1)}
    changed = 0
    for node, z in new_z.items():
        k = node if direct else index.get(str(node))
        if k is None or not (0 < k < len(lines)):
            raise ValueError("node %d is not in the .node file" % node)
        parts = lines[k].split(" ")
        if len(parts) != 4 or parts[0] != str(node):
            raise ValueError("node %d's line is not a vector node line" % node)
        line = "%s %s %s %s" % (parts[0], parts[1], parts[2], f"{z:.9f}")
        if line != lines[k]:
            lines[k] = line
            changed += 1
    if changed:
        temporary = node_file + ".tmp"
        with open(temporary, "w", encoding="utf-8", newline="") as handle:
            handle.write("\n".join(lines))
        os.replace(temporary, node_file)
    return changed


def _refuse(why: str, relevant: bool = True) -> FastPathResult:
    return FastPathResult(applied=False, why=why, relevant=relevant)


def try_height_edit(tile) -> FastPathResult:
    """Apply a height-only patch edit to the vector step's products without
    running it (module docstring), or refuse and say why.  Never raises."""
    t0 = time.time()
    try:
        if getattr(tile, "iterate", 0):
            return _refuse("an iterated mesh (iterate > 0)", False)
        (changed, why) = REUSE.edit_only_changes(tile)
        if changed is None:
            return _refuse(why, False)
        node_file = FNAMES.input_node_file(tile)
        events = ZPROV.read_events(ZPROV.zprov_file(node_file))
        if events is None:
            return _refuse("the last vector step left no z-provenance log")
        edited, heights = {}, 0
        for path in changed:
            name = os.path.basename(path)
            before = os.path.join(prev_dir(tile), name)
            if not os.path.isfile(before):
                return _refuse(
                    "no copy of %s as last built (the edit cache is cleared "
                    "when the app quits unless the tile's keep_edit_cache "
                    "is on)" % name)
            (nodes, why) = height_only_diff(before, path)
            if nodes is None:
                return _refuse("%s: %s" % (name, why))
            heights += len(nodes)
            edited[name] = _layer(path).dicosmtags["n"]
        new_z = ZPROV.replay(events, _base_values(edited))
        if UI.red_flag:
            return _refuse("stopped", False)
        rewritten = _rewrite_node_file(node_file, new_z)
        ZPROV.write_events(ZPROV.zprov_file(node_file), events)
        _remember(tile, [os.path.basename(p) for p in changed])
        REUSE.record(tile, "vector", osm_files=REUSE.committed_entry(
            tile, "vector").get("osm_files"))
    except Exception as error:
        return _refuse("the fast path failed (%s)" % (error,))
    result = FastPathResult(
        applied=True, relevant=True,
        patches=[os.path.basename(p) for p in changed],
        heights_changed=heights, nodes_rewritten=rewritten,
        seconds=time.time() - t0)
    UI.vprint(
        0, "\nVector data for tile %s: UPDATED FOR A HEIGHT-ONLY PATCH EDIT "
           "(%s: %d node height(s) changed; %d vector node height(s) "
           "rewritten in %.1f s). The vector map was not rebuilt (#1323); "
           "the mesh, masks and scenery file are built from it as after a "
           "full vector step."
        % (FNAMES.short_latlon(tile.lat, tile.lon), ", ".join(result.patches),
           heights, rewritten, result.seconds))
    return result


def _remember(tile, names=None) -> None:
    """Copy the tile's manual patches (``names`` only, when given) into
    ``prev/`` as built, and list the edit cache in this session."""
    folder = prev_dir(tile)
    os.makedirs(folder, exist_ok=True)
    patch_dir = FNAMES.patch_dir(tile.lat, tile.lon)
    try:
        current = sorted(n for n in os.listdir(patch_dir)
                         if FNAMES.is_manual_patch_name(n))
    except OSError:
        current = []
    for name in (names if names is not None else current):
        temporary = os.path.join(folder, name + ".tmp")
        shutil.copyfile(os.path.join(patch_dir, name), temporary)
        os.replace(temporary, os.path.join(folder, name))
    if names is None:
        for name in os.listdir(folder):
            if name not in current:
                os.remove(os.path.join(folder, name))
    EDITCACHE.register(tile)


def after_step_recorded(tile, step: str) -> None:
    """``step`` was recorded as run, or reused as current: for the vector
    step the patches on disk are the ones it was built from — keep them
    for the next height edit.  Never raises."""
    if step != "vector":
        return
    try:
        _remember(tile)
    except OSError:
        pass


def step_decision(tile, step: str):
    """THE reuse decision for one reusable step: ``("reused", None)`` when
    it is current, ``("updated", FastPathResult)`` when the height-edit
    fast path brought the vector step up to date, else ``("run", why)``
    with the step's old record dropped (``O4_Step_Reuse.forget_from``)."""
    why = REUSE.stale_reason(tile, step)
    if why is None:
        after_step_recorded(tile, step)
        return "reused", None
    if step == "vector":
        result = try_height_edit(tile)
        if result.applied:
            return "updated", result
        if result.relevant:
            UI.vprint(1, "   Height-edit fast path not taken: %s." % result.why)
    REUSE.forget_from(tile, step)
    return "run", why
