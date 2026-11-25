"""THE INSET BOX GROWS OVER A PACK'S TERRAIN OBJECTS (issue #2272).

The rule and the cap are ``auto_patch_v2.airport.terrain_model_extent``'s;
this is the fetch side that feeds them: the installed airport packs over
the tile (``O4_Airport_Elevation_Insets._airport_pack_dsf_paths``, the
footprint scan's own pack list), each pack's PRISTINE tile DSF
(``backup_state.pristine_dsf_path``) through the shared DSF text cache
(``auto_patch.dsf_reader``), pack-local resources only.  Each object's
outline is kept per file version in the pack's ``Airport_mod_cache``
folder (:data:`KEPT_NAME`, under ``terrain_model_extent.gates_key``), so a
build asks a pack's large objects once -- written only where no armed
shared-repo guard refuses it (``shared_repo_guard.GUARDED_PYTHON_ONLY_RE``).

Called by the ONE fetch entry,
``O4_Airport_Elevation_Insets.ensure_insets_for_tile``; never raises (a
failed read leaves the boxes as they were, named on the console).
"""
from __future__ import annotations

import json
import os

import O4_UI_Utils as UI

__all__ = ["KEPT_NAME", "grow_boxes"]

#: the kept outlines of one pack (``{"gates": key, "files": {path:
#: [mtime_ns, size, outline | None]}}``)
KEPT_NAME = "o4_terrain_outlines.json"


class _Kept:
    """One pack's kept outlines: read once, asked per file version,
    written back only when something new was asked."""

    def __init__(self, pack_root, gates):
        from auto_patch.dsf_reader import airport_mod_cache_dir
        folder = airport_mod_cache_dir(pack_root)
        self.path = folder and os.path.join(folder, KEPT_NAME)
        self.gates, self.files, self.dirty = gates, {}, False
        try:
            with open(self.path, encoding="utf-8") as fh:
                got = json.load(fh)
            if got.get("gates") == gates and isinstance(got.get("files"), dict):
                self.files = got["files"]
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def __call__(self, path):
        from auto_patch_v2.airport import terrain_model_extent as TX
        try:
            st = os.stat(path)
        except OSError:
            return None
        row = self.files.get(path)
        if (isinstance(row, list) and len(row) == 3
                and row[:2] == [st.st_mtime_ns, st.st_size]):
            return row[2]
        got = TX.outline(path)
        self.files[path] = [st.st_mtime_ns, st.st_size, got]
        self.dirty = True
        return got

    def save(self):
        if not (self.dirty and self.path):
            return
        from elevation_access.downloads import _write_refused_by_armed_guard
        if _write_refused_by_armed_guard(self.path):
            return              # a guarded harness run: asked again next time
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                json.dump({"gates": self.gates, "files": self.files}, fh)
            os.replace(tmp, self.path)
        except OSError as error:
            UI.vprint(2, "   Airport insets: terrain outlines not kept (%s)" % error)


def _pack_models(xplane_root, tile, aerodromes):
    """Every terrain object the airport packs over the tile place near an
    aerodrome (``terrain_model_extent.ModelBox`` list)."""
    import O4_Airport_Elevation_Insets as INSETS
    from auto_patch.dsf_reader import _load_dsf_text, _read_dsf_object_placements
    from auto_patch_v2.airport import terrain_model_extent as TX
    from auto_patch_v2.airport.backup_state import pristine_dsf_path
    from auto_patch_v2.airport.obj8 import is_stock_library_resource, resolve_resource

    inner = (tile.lon + 1e-6, tile.lat + 1e-6,
             tile.lon + 1 - 1e-6, tile.lat + 1 - 1e-6)
    models = []
    for dsf in INSETS._airport_pack_dsf_paths(xplane_root, inner):
        pack_root = os.path.dirname(os.path.dirname(os.path.dirname(dsf)))
        lines = _load_dsf_text(pristine_dsf_path(dsf))
        if not lines:
            continue
        rows = TX.nearby(_read_dsf_object_placements(
            lines, lambda p: not is_stock_library_resource(p)),
            aerodromes.values())
        if not rows:
            continue
        kept = _Kept(pack_root, TX.gates_key())
        models += TX.plan_boxes(
            rows, lambda d, root=pack_root: resolve_resource(d, root, None),
            kept)
        kept.save()
    return models


def grow_boxes(tile, dico_airports, boxes):
    """``boxes`` (``{airport: (west, south, east, north)}``, the fetch's
    request) with each airport's box grown over the terrain objects
    standing near its aerodrome (``terrain_model_extent.admit``).  The
    same dict, untouched, when no object is admitted."""
    try:
        import O4_Airport_Elevation_Insets as INSETS
        from auto_patch_v2.airport import terrain_model_extent as TX
        root = INSETS._xplane_root_for_package_footprints()
        if not root or not boxes:
            return boxes
        aerodromes = INSETS._airport_bounding_boxes(
            tile, dico_airports, only=list(boxes), margin_m=0.0)
        models = _pack_models(root, tile, aerodromes)
    except Exception as error:
        UI.vprint(1, "   Airport insets: terrain objects not read (%s: %s) "
                     "- the inset boxes keep the aerodrome reach."
                  % (type(error).__name__, error))
        return boxes
    if not models:
        return boxes
    pad_m = (float(getattr(tile, "airport_elevation_inset_feather_m", 60.0))
             + INSETS.INSET_FETCH_PAD_M)
    tile_box = (tile.lon, tile.lat, tile.lon + 1.0, tile.lat + 1.0)
    by_airport = {}
    for m in models:
        by_airport.setdefault(TX.nearest(m, aerodromes), []).append(m)
    out = dict(boxes)
    for airport, own in sorted(by_airport.items()):
        box, admitted, left = TX.admit(own, aerodromes[airport], boxes[airport],
                                       tile_box, pad_m)
        out[airport] = box
        if admitted:
            UI.vprint(1, "   Airport insets: %s box grown over %d terrain "
                         "object(s) of its pack (%s)."
                      % (airport, len(admitted), ", ".join(sorted(
                          {os.path.basename(m.resource) for m in admitted}))))
        for m, why in left:
            UI.vprint(1, "   Airport insets: %s terrain object %s at "
                         "(%.5f, %.5f) left out of the inset box: %s."
                      % (airport, m.resource, m.lat, m.lon, why))
    return out
