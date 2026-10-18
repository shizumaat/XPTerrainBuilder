"""Which build steps of a tile can be REUSED as they are (#615).

Owner 2026-10-12: a rebuild whose only change is the texture mode or the
imagery should not rebuild the vector data, the airport patches or the
mesh — "just the DSF".  Each of the three steps before the scenery-file
step (``vector``, ``mesh``, ``masks``) therefore records the inputs it
was built from and the files it wrote; the next build skips the step,
by name, when both are as recorded.

WHAT A STEP'S INPUTS ARE.  The settings it reads — the step's own list in
``O4_Cfg_Vars`` (``list_vector_vars`` / ``list_mesh_vars`` /
``list_mask_vars``) plus ``custom_dem`` / ``fill_nodata``, and the
app-level settings that choose its data — the engine's version, the
digest of the code the step runs through (``O4_Step_Code``), the auto-patch configuration digest, and what the step
before it HANDS ON (#837): the CONTENT of the files it wrote and the
inputs it read, its own code left out.  The vector step adds the data it read that can change without a
setting: the tile's OSM cache files, its cached airport elevation
insets, the pack order and state ``scenery_packs.ini`` gives (its
content, the tile's own pack left out), and for each airport patch the
apt.dat / CIFP files its own freshness stamp names and its pack DSFs as
the build's INPUT — the pristine pack, never the file the mesh step's
object stage rewrote: a file a build wrote must not make that build's own
earlier steps stale.  None of the texture settings (``list_dsf_vars``, the imagery
source, zoom and zone list) is an input of any of the three — they are
read only by the scenery-file step (``O4_DSF_Utils``,
``O4_Imagery_Utils``, ``O4_Airport_Fade_Masks``,
``O4_Default_Terrain_Map``).  The one exception is ``ratio_water``,
which the masks step reads to pick its inland-water grey level, so it is
an input of the masks step.

EARLY CUTOFF (#837).  A step's ``previous`` is the predecessor's output
CONTENT (``provenance.content_identity_list``: path, size, sha256 — an
airport patch read without the stamps that only name the run that wrote
it, ``provenance.PER_RUN_STAMP_KEYS``) together with the predecessor's
own inputs minus its code digest.  A vector step that reran because its
code changed and wrote the same bytes leaves the mesh and the masks
reusable: no code a step's output depends on can change without changing
that step's own code key or the content its predecessor wrote.  The
predecessor's inputs stay in the chain because a later step reads some
of them directly (the mesh bakes the elevation insets the vector step
keys on).  Outputs are identified by content: a file whose path, size
and mtime are as recorded is not read again (the hit path costs stats);
any other is digested, so a touched file with the same bytes is no
change.

A RECORD COUNTS ONLY ONCE ITS BUILD COMPLETED.  A step that ran writes a
PENDING record; the scenery-file step's completion commits it
(:func:`commit`).  A step that starts running discards its own committed record and
the pending records of itself and every later step (:func:`forget_from`);
a later step's committed record stays, and is reused only when its own
files are as it recorded them and its predecessor handed on the same
content — a stopped build cannot leave a record that matches files it
replaced.
A build stopped after its mesh step puts the scenery packs back
(``O4_Stopped_Build``) and commits nothing: the next build reruns.

``O4_STEP_REUSE=0`` turns reuse off (every selected step runs).

Never raises: a record that cannot be read or written means "run the
step", the behaviour before this module existed.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import urllib.parse

import O4_File_Names as FNAMES

__all__ = ["REUSABLE_STEPS", "stale_reason", "predicted_reuse", "record",
           "reused", "commit", "forget_from", "reused_label"]

# 2026-10-14: pack DSFs keyed as the build's input and scenery_packs.ini
# by content (#615 self-invalidation); a 2026-10-13 record reads as none.
# 2026-10-18: ``code`` is the step's own closure digest (#836).
# 2026-10-18b: outputs by content, ``previous`` = what the predecessor
# hands on (#837); a 2026-10-18 record reads as none — reruns once.
SCHEMA = "2026-10-18b"

#: the steps whose output can be reused, in build order
REUSABLE_STEPS = ("vector", "mesh", "masks")

#: app-level settings that choose the data the vector step reads
_VECTOR_APP_VARS = ("osm_regional_extracts", "base_elevation_source",
                    "custom_scenery_dir", "auto_patch_boundary",
                    "cifp_data_path")


def _record_path(tile) -> str:
    return os.path.join(
        tile.build_dir,
        "Ortho4XP_" + FNAMES.short_latlon(tile.lat, tile.lon) + "_steps.json")


def _identity(paths) -> str:
    from auto_patch import provenance
    return provenance.identity_list(paths)


def _read(tile) -> dict:
    try:
        with open(_record_path(tile), encoding="utf-8") as handle:
            doc = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        return {}
    return doc


def _write(tile, doc: dict) -> None:
    if not tile.build_dir or not os.path.isdir(tile.build_dir):
        return                      # no build directory: nothing to stamp
    path = _record_path(tile)
    doc = dict(doc, schema=SCHEMA)
    try:
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(doc, handle, indent=1, sort_keys=True)
        os.replace(temporary, path)
    except OSError:
        pass


def _setting(tile, name):
    """A setting's live value: the tile's, else the app's module global."""
    if hasattr(tile, name):
        return getattr(tile, name)
    try:
        import O4_Cfg_Vars as CFGVARS
        import O4_Config_Utils as CFG
        module = CFGVARS.cfg_vars.get(name, {}).get("module")
        holder = getattr(CFG, module) if module else CFG
        return getattr(holder, name, None)
    except Exception:
        return None


def _step_settings(step: str) -> tuple:
    import O4_Cfg_Vars as CFGVARS
    own = {"vector": CFGVARS.list_vector_vars,
           "mesh": CFGVARS.list_mesh_vars,
           # ratio_water: the masks step's inland-water grey level.
           "masks": CFGVARS.list_mask_vars + ["ratio_water"]}[step]
    names = list(own) + list(CFGVARS.list_other_vars)
    if step == "vector":
        names += list(_VECTOR_APP_VARS)
    return tuple(names)


def _patch_files(tile) -> list:
    return sorted(glob.glob(os.path.join(
        FNAMES.patch_dir(tile.lat, tile.lon), "*.osm")))


def _stamped_paths(value: str) -> list:
    """The file paths an ``identity_list`` stamp names."""
    paths = []
    for item in str(value or "").split(";"):
        head = item.split("|", 1)[0]
        if head and head not in ("none", "?"):
            paths.append(urllib.parse.unquote(head))
    return paths


def _patch_inputs(tile) -> dict:
    """For each airport patch, the identity of the apt.dat and CIFP files
    its own freshness stamp names, and of its pack DSFs AS THE BUILD'S
    INPUT.

    The mesh step's object stage REWRITES those pack DSFs after this
    record is cut, so their live identity never matches at the next build
    (#615, app 1.0.391: every OTHH rebuild reran the vector step).  The
    input is the pack as installed — ``provenance.pack_dsf_identity_list``,
    the rule the patch freshness gate already uses for the same reason:
    the pristine backup's size+mtime when the live file is this app's
    own write, the live file's when the user replaced the pack."""
    from auto_patch import provenance
    from auto_patch.build_support import read_patch_source
    inputs = {}
    for patch in _patch_files(tile):
        meta = read_patch_source(patch) or {}
        fresh = meta.get("freshness") or {}
        named = [meta.get("apt_dat"), meta.get("apt_dat_borrowed")]
        named += _stamped_paths(fresh.get("o4_cifp"))
        inputs[os.path.basename(patch)] = {
            "files": _identity([p for p in named if p]),
            "pack_dsfs": provenance.pack_dsf_identity_list(
                _stamped_paths(fresh.get("o4_dsf")))}
    return inputs


def _scenery_packs_state(tile) -> str:
    """What the vector step reads from ``scenery_packs.ini``: the enabled
    packs in order and the disabled ones — not the file's size and mtime,
    which the app's own pack reconcile and X-Plane's launch rewrite with
    nothing changed for this tile.  The tile's own pack (the folder this
    build writes, which the app lists when it installs it) is left out:
    the build's own install must not make its earlier steps stale."""
    import O4_Scenery_Packs as PACKS
    ini = os.path.join(str(_setting(tile, "custom_scenery_dir") or ""),
                       PACKS.INI_FILENAME)
    if not os.path.isfile(ini):
        return "absent"
    own = {FNAMES.tile_dir(tile.lat, tile.lon),
           os.path.basename(os.path.normpath(str(tile.build_dir or "")))}
    enabled, disabled = PACKS.parse_ini(ini)
    text = json.dumps([[n for n in enabled if n not in own],
                       sorted(n for n in disabled if n not in own)])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _osm_files(tile) -> list:
    folder = FNAMES.osm_dir(tile.lat, tile.lon)
    try:
        return sorted(os.path.join(folder, name) for name in os.listdir(folder)
                      if not name.endswith((".tmp", ".part", ".lock")))
    except OSError:
        return []


def _inset_files(tile) -> list:
    """The airport elevation insets cached for the tile — a neighbour's
    build can add one, and the vector and mesh steps both bake them."""
    import O4_Airport_Elevation_Insets as INSETS
    return INSETS.list_cached_inset_dems(tile.lat, tile.lon)


def _code_identity(step: str) -> dict:
    """The engine half of ``step``'s key: its version, the digest of the
    code ``step`` runs through (``O4_Step_Code``, #836 — the step's own
    import closure and the law tables, not the whole tree; the whole-tree
    digest only when the step's cannot be had), and the auto-patch
    configuration."""
    import O4_Step_Code as STEPCODE
    from auto_patch import provenance, provenance_code
    return {"engine": provenance.engine_version(),
            "code": STEPCODE.step_digest(step) or provenance_code.code_digest(),
            "auto_patch_cfg": provenance.config_digest()}


def _inputs(tile, step: str, previous_digest: str, osm_files=None) -> dict:
    """``osm_files``: the OSM cache files the vector step found when it
    ran (None: list them now).  A file a LATER step fetched into the
    folder (the masks step's reef and tidal-flat layers) is not one the
    vector step read, and does not make it stale."""
    inputs = {"step": step, "previous": previous_digest,
              "settings": {name: repr(_setting(tile, name))
                           for name in _step_settings(step)}}
    inputs.update(_code_identity(step))
    if step == "vector":
        inputs["osm"] = _identity(
            _osm_files(tile) if osm_files is None else osm_files)
        inputs["scenery_packs"] = _scenery_packs_state(tile)
        inputs["patches"] = _patch_inputs(tile)
        inputs["insets"] = _identity(_inset_files(tile))
    return inputs


def _digest(inputs: dict) -> str:
    text = json.dumps(inputs, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _journalled_dsfs(tile) -> list:
    try:
        from auto_patch_v2.airport import pack_journal
        return pack_journal.journalled_dsfs(
            tile.build_dir, FNAMES.short_latlon(tile.lat, tile.lon))
    except Exception:
        return []


def _output_files(tile, step: str, pack_dsfs=()) -> list:
    if step == "vector":
        files = [FNAMES.input_node_file(tile), FNAMES.input_poly_file(tile),
                 FNAMES.apt_file(tile), FNAMES.alt_file(tile)]
        files += _patch_files(tile)
    elif step == "mesh":
        # The pack DSFs the mesh step's object stage rewrote: a pack put
        # back or reinstalled since needs the objects seated again.
        files = [FNAMES.mesh_file(tile.build_dir, tile.lat, tile.lon)]
        files += list(pack_dsfs)
    else:
        folder = FNAMES.mask_dir(tile.lat, tile.lon)
        try:
            files = [os.path.join(folder, n) for n in os.listdir(folder)]
        except OSError:
            files = []
    return files


def _outputs(tile, step: str, pack_dsfs=(), known=()) -> list:
    """``step``'s output files by content; ``known``: the rows recorded
    for them, whose digests a file with an unchanged stat keeps."""
    from auto_patch import provenance
    return provenance.content_identity_list(
        _output_files(tile, step, pack_dsfs), known)


def _outputs_digest(rows) -> str:
    from auto_patch import provenance
    return provenance.content_identity_digest(rows)


def _handed_on(entry: dict) -> str:
    """What a step hands the next one: its output content and its inputs
    without its code digest (a change of code reaches the next step only
    through the files it writes)."""
    inputs = {k: v for k, v in (entry.get("inputs") or {}).items()
              if k != "code"}
    return _digest({"outputs": entry.get("outputs_digest"),
                    "inputs": inputs})


def _previous_digest(doc: dict, step: str) -> str:
    """The predecessor's :func:`_handed_on` — this build's record of it
    (it ran, or was reused, in this build), else the last completed
    build's."""
    index = REUSABLE_STEPS.index(step)
    if index == 0:
        return ""
    before = REUSABLE_STEPS[index - 1]
    entry = ((doc.get("pending") or {}).get(before)
             or (doc.get("committed") or {}).get(before))
    if not entry or not entry.get("outputs_digest"):
        return "absent"
    return _handed_on(entry)


def stale_reason(tile, step: str) -> str | None:
    """None when ``step`` can be reused for ``tile``; else why not, in a
    few words for the log ("the mesh settings changed")."""
    if step not in REUSABLE_STEPS:
        return "not a reusable step"
    if os.environ.get("O4_STEP_REUSE", "1") == "0":
        return "reuse is off (O4_STEP_REUSE=0)"
    try:
        doc = _read(tile)
        entry = (doc.get("committed") or {}).get(step)
        if not entry:
            return "no record of a completed build"
        live = _inputs(tile, step, _previous_digest(doc, step),
                       entry.get("osm_files"))
        recorded = entry.get("inputs") or {}
        for key in sorted(set(live) | set(recorded)):
            if live.get(key) != recorded.get(key):
                return _changed_words(key, live.get(key), recorded.get(key))
        rows = _outputs(tile, step, entry.get("pack_dsfs") or (),
                        entry.get("outputs") or ())
        if _outputs_digest(rows) != entry.get("outputs_digest"):
            return "its output files changed or are missing"
        return None
    except Exception as error:                    # never fatal: just run it
        return "its record could not be checked (%s)" % (error,)


def predicted_reuse(tile, steps=REUSABLE_STEPS) -> tuple:
    """The planned ``steps`` a build starting now will reuse: each one
    current, and every reusable step planned before it reused too (a
    step that runs drops the records after it)."""
    reused_steps = []
    for step in REUSABLE_STEPS:
        if step not in steps:
            continue
        if stale_reason(tile, step) is not None:
            break
        reused_steps.append(step)
    return tuple(reused_steps)


def _changed_words(key, live, recorded) -> str:
    if key == "settings" and isinstance(live, dict):
        names = sorted(n for n in set(live) | set(recorded or {})
                       if live.get(n) != (recorded or {}).get(n))
        return "setting changed: " + ", ".join(names[:4])
    return {"previous": "the step before it changed its files or inputs",
            "engine": "the engine version changed",
            "code": "the engine code changed",
            "auto_patch_cfg": "the auto-patch configuration changed",
            "osm": "the OpenStreetMap data changed",
            "scenery_packs": "scenery_packs.ini changed",
            "patches": "an airport's apt.dat, CIFP or pack changed",
            "insets": "the airport elevation insets changed"}.get(
                key, key + " changed")


def record(tile, step: str) -> None:
    """``step`` ran and succeeded: write its PENDING record."""
    if step not in REUSABLE_STEPS:
        return
    try:
        doc = _read(tile)
        pending = dict(doc.get("pending") or {})
        inputs = _inputs(tile, step, _previous_digest(doc, step))
        pack_dsfs = _journalled_dsfs(tile) if step == "mesh" else []
        rows = _outputs(tile, step, pack_dsfs)
        pending[step] = {"inputs": inputs, "digest": _digest(inputs),
                         "osm_files": _osm_files(tile) if step == "vector"
                         else None,
                         "pack_dsfs": pack_dsfs,
                         "outputs": rows,
                         "outputs_digest": _outputs_digest(rows)}
        doc["pending"] = pending
        _write(tile, doc)
    except Exception:
        pass


def reused(tile, step: str) -> None:
    """``step`` was reused: carry its committed record into this build's
    pending set, so the steps after it chain onto it."""
    doc = _read(tile)
    entry = (doc.get("committed") or {}).get(step)
    if entry:
        doc["pending"] = dict(doc.get("pending") or {}, **{step: entry})
        _write(tile, doc)


def forget_from(tile, step: str) -> None:
    """``step`` is about to run: its committed record no longer describes
    its files, and no pending record of it or a later step is this
    build's.  A later step's committed record stays (early cutoff, #837):
    it is reused only when its own files are as it recorded them and this
    build's ``step`` hands on what it was built from."""
    if step not in REUSABLE_STEPS:
        return
    doc = _read(tile)
    if not doc:
        return
    later = REUSABLE_STEPS[REUSABLE_STEPS.index(step):]
    committed = {k: v for k, v in (doc.get("committed") or {}).items()
                 if k != step}
    pending = {k: v for k, v in (doc.get("pending") or {}).items()
               if k not in later}
    _write(tile, dict(doc, committed=committed, pending=pending))


def commit(tile) -> None:
    """The build COMPLETED (the scenery-file step's last act): this
    build's pending records become the ones the next build reads."""
    doc = _read(tile)
    pending = doc.get("pending") or {}
    if not pending:
        return
    committed = dict(doc.get("committed") or {}, **pending)
    _write(tile, {"committed": committed, "pending": {}})


def reused_label(step_label: str) -> str:
    """The progress label of a reused step."""
    return "%s · reused (unchanged since the last build)" % (step_label,)
