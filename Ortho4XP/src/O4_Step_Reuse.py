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
app-level settings that choose its data — the
digest of the code the step runs through (``O4_Step_Code``), the auto-patch
configuration digest, and what the step before it HANDS ON (#837): the
CONTENT of the files it wrote and the inputs it read, its own code left
out.  The vector step adds the data it read that can change without a
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
change.  The vector step's outputs include the sidecars the mesh step
reads beside the .node/.poly (#1377): ``o4_levelled_roads.json`` and the
object-anchor worklist, the latter read without the ``dsf_mtime`` the
object stage's own pack rewrite moves.

A STEP'S RECORD COUNTS WHEN THE STEP ENDS (#838, owner RULINGS
2026-10-17a Q3).  A step that ran and succeeded writes its record at once
(:func:`record`): its outputs are on disk and are a function of its
inputs whatever happens later, so a build stopped at any later point
resumes from the first step that did not finish.  The rules that make
that safe:

- a step that starts running discards its own record first
  (:func:`forget_from`), so a step stopped half-way leaves none — its
  files may be half rewritten;
- a later step's record stays, and is reused only when its own files are
  as it recorded them and its predecessor's record hands on what it was
  built from (early cutoff above) — the ``previous`` chain carries each
  predecessor's inputs, so no step chains onto a record of another lineage;
- the mesh step's record lists, as its outputs, the pack DSFs its object
  stage rewrote (``pack_dsfs``, journalled).  A Stop puts those packs back
  (``O4_Stopped_Build``), which changes their content, so the next build
  reruns the mesh step and reuses the vector step (whose input is the
  pristine pack, ``provenance.pack_dsf_input_identity``);
- the record file is replaced whole (temporary file + ``os.replace``): a
  process killed while writing it leaves the record as it was, and one
  that cannot be read reads as no record.

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
           "forget_from", "reused_label", "edit_only_changes",
           "committed_entry"]

# 2026-10-14: pack DSFs keyed as the build's input and scenery_packs.ini
# by content (#615 self-invalidation); a 2026-10-13 record reads as none.
# 2026-10-18: ``code`` is the step's own closure digest (#836).
# 2026-10-18b: outputs by content, ``previous`` = what the predecessor
# hands on (#837); a 2026-10-18 record reads as none — reruns once.
# 2026-10-26: the vector step's outputs add the sidecars the mesh step
# reads (#1377); a 2026-10-18b record reads as none — reruns once.
# 2026-10-26b: and the z-provenance log (O4_ZProv, #1323).
SCHEMA = "2026-10-26b"

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


# Keys a record written by an older engine may hold that are no longer
# part of a step's key: ``engine`` (the engine version, #1248 — a release
# that leaves a step's code alone must not rebuild it; the ``code``
# digest already covers a change).  Compared without them, so such a
# record is still reused.
_RETIRED_KEYS = ("engine",)


def _code_identity(step: str) -> dict:
    """The engine half of ``step``'s key: the digest of the code ``step``
    runs through (``O4_Step_Code``, #836 — the step's own import closure
    and the law tables, not the whole tree; the whole-tree digest only
    when the step's cannot be had), and the auto-patch configuration.
    Not the engine version (#1248): ``code`` already changes with it."""
    import O4_Step_Code as STEPCODE
    from auto_patch import provenance, provenance_code
    return {"code": STEPCODE.step_digest(step) or provenance_code.code_digest(),
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


def _worklist_path(tile) -> str:
    from auto_patch import post_mesh
    return post_mesh.object_anchor_worklist_path(tile)


def _output_files(tile, step: str, pack_dsfs=()) -> list:
    if step == "vector":
        # The sidecars the vector step writes for the mesh step to read
        # (#1377): the levelled roads the bank blend keeps off, and the
        # object-anchor worklist the object stage seats from.  A changed
        # sidecar under an unchanged .node/.poly is a changed input of
        # the mesh step.  (``o4_unpatched_airports.json`` is not one: no
        # mesh code reads it, and the masks step writes it too.)  And the
        # z-provenance log a height-only patch edit replays (#1323).
        import O4_ZProv as ZPROV
        node_file = FNAMES.input_node_file(tile)
        files = [node_file, FNAMES.input_poly_file(tile),
                 FNAMES.apt_file(tile), FNAMES.alt_file(tile),
                 ZPROV.zprov_file(node_file),
                 os.path.join(tile.build_dir, FNAMES.LEVELLED_ROADS_SIDECAR)]
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


#: Worklist keys that name the run, not the content: an entry's
#: ``dsf_mtime`` is the live pack DSF's, which the mesh step's object
#: stage rewrites, and the object stage reads the current DSF regardless
#: (``post_mesh`` module doc, amendment A5).
_WORKLIST_PER_RUN_KEYS = ("dsf_mtime",)


def _worklist_row(path: str, known=()) -> list:
    """The worklist's ``content_identity_list`` row, its content read
    without :data:`_WORKLIST_PER_RUN_KEYS` (and its size that of what is
    hashed): a vector step that reran after the object stage rewrote a
    pack writes the same worklist."""
    from auto_patch import provenance
    recorded = {row[0]: row for row in known or ()
                if isinstance(row, (list, tuple)) and len(row) == 4}
    try:
        stat = os.stat(path)
        row = recorded.get(path)
        if row and row[2] == stat.st_mtime_ns and row[3] != "missing":
            return list(row)
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle)
    except ValueError:
        return provenance.content_identity_list([path])[0]
    except OSError:
        return [path, -1, -1, "missing"]
    if isinstance(doc, dict):
        doc = dict(doc, airports=[
            {k: v for k, v in entry.items()
             if k not in _WORKLIST_PER_RUN_KEYS}
            if isinstance(entry, dict) else entry
            for entry in doc.get("airports") or ()])
    text = json.dumps(doc, sort_keys=True).encode("utf-8")
    return [path, len(text), stat.st_mtime_ns,
            hashlib.sha256(text).hexdigest()]


def _outputs(tile, step: str, pack_dsfs=(), known=()) -> list:
    """``step``'s output files by content; ``known``: the rows recorded
    for them, whose digests a file with an unchanged stat keeps."""
    from auto_patch import provenance
    rows = provenance.content_identity_list(
        _output_files(tile, step, pack_dsfs), known)
    if step == "vector":
        rows.append(_worklist_row(_worklist_path(tile), known))
    return rows


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
    """The predecessor's :func:`_handed_on`: its record — this build's
    when it ran in this build (:func:`record` at its end), else the one
    it was reused on or, when it was not planned, the last one written."""
    index = REUSABLE_STEPS.index(step)
    if index == 0:
        return ""
    entry = (doc.get("committed") or {}).get(REUSABLE_STEPS[index - 1])
    if not entry or not entry.get("outputs_digest"):
        return "absent"
    return _handed_on(entry)


#: The remedies of an unpatched airport that a plain rebuild answers
#: (``O4_Tile_Failures.REMEDIES``): the warning tells the user to build
#: the tile again, so the next build must try that airport again.
_RETRY_REMEDIES = ("retry", "network", "later", "rebuild_later")


def _airports_to_retry(tile) -> list:
    """The airports the tile on disk was built WITHOUT for a cause a
    rebuild answers (issue #1352: a reused vector step never tried an
    airport whose elevation was missing again, while its warning said
    "build the tile again")."""
    import O4_Tile_Failures as FAIL
    import O4_Unpatched_Airports as UNPATCHED
    names = []
    for rec in UNPATCHED.read(tile):
        code = FAIL.code_for_stage(rec.get("stage"), rec.get("code"))
        entry = FAIL.CATALOGUE.get(code)
        if entry is not None and entry.remedy in _RETRY_REMEDIES:
            names.append(str(rec.get("icao") or "?"))
    return names


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
            return "no record of a finished run of it"
        retry = _airports_to_retry(tile) if step == "vector" else []
        if retry:
            return "airport(s) left without a patch last time: " + \
                ", ".join(retry[:4])
        live = _inputs(tile, step, _previous_digest(doc, step),
                       entry.get("osm_files"))
        recorded = {k: v for k, v in (entry.get("inputs") or {}).items()
                    if k not in _RETIRED_KEYS}
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


def committed_entry(tile, step: str) -> dict:
    """``step``'s committed record (``{}`` when there is none)."""
    return dict((_read(tile).get("committed") or {}).get(step) or {})


def edit_only_changes(tile) -> tuple:
    """``(patch files, None)`` when the ONLY change since the vector step
    last ran is the content of those airport patch files — every vector
    input key and every other output row is as recorded (#1323, the
    height-edit fast path's admission, spec §3A.2 / §8 item 3); else
    ``(None, why)`` in a few words."""
    if os.environ.get("O4_STEP_REUSE", "1") == "0":
        return None, "reuse is off (O4_STEP_REUSE=0)"
    try:
        doc = _read(tile)
        entry = (doc.get("committed") or {}).get("vector")
        if not entry:
            return None, "no record of a finished vector step"
        retry = _airports_to_retry(tile)
        if retry:
            return None, ("airport(s) left without a patch last time: "
                          + ", ".join(retry[:4]))
        live = _inputs(tile, "vector", _previous_digest(doc, "vector"),
                       entry.get("osm_files"))
        recorded = entry.get("inputs") or {}
        for key in sorted(set(live) | set(recorded)):
            if live.get(key) != recorded.get(key):
                return None, _changed_words(key, live.get(key),
                                            recorded.get(key))
        known = {row[0]: row for row in entry.get("outputs") or ()}
        rows = {row[0]: row for row in _outputs(tile, "vector", (),
                                                entry.get("outputs") or ())}
        if set(rows) != set(known):
            return None, "a patch file was added or removed"
        patches = set(_patch_files(tile))
        changed = sorted(path for path, row in rows.items()
                         if (row[1], row[3]) != (known[path][1],
                                                 known[path][3]))
        if not changed:
            return None, "no patch file changed"
        others = [p for p in changed if p not in patches]
        if others:
            return None, ("a vector output other than a patch changed (%s)"
                          % os.path.basename(others[0]))
        return changed, None
    except Exception as error:                    # never fatal: just run it
        return None, "the record could not be checked (%s)" % (error,)


def record(tile, step: str, osm_files=None) -> None:
    """``step`` ran and succeeded, its outputs on disk: its record is the
    one the next build reads (#838) — written now, not at the build's end.
    ``osm_files``: the vector step's OSM inputs when it did not list them
    itself (the height-edit fast path keeps the run's own list)."""
    if step not in REUSABLE_STEPS:
        return
    try:
        doc = _read(tile)
        if step == "vector" and osm_files is None:
            osm_files = _osm_files(tile)
        inputs = _inputs(tile, step, _previous_digest(doc, step), osm_files)
        pack_dsfs = _journalled_dsfs(tile) if step == "mesh" else []
        rows = _outputs(tile, step, pack_dsfs)
        committed = dict(doc.get("committed") or {})
        committed[step] = {"inputs": inputs, "digest": _digest(inputs),
                           "osm_files": osm_files if step == "vector"
                           else None,
                           "pack_dsfs": pack_dsfs,
                           "outputs": rows,
                           "outputs_digest": _outputs_digest(rows)}
        _write(tile, {"committed": committed})
    except Exception:
        pass


def forget_from(tile, step: str) -> None:
    """``step`` is about to run: its record no longer describes its files
    (a Stop may leave them half rewritten).  A later step's record stays
    (early cutoff, #837): it is reused only when its own files are as it
    recorded them and this build's ``step`` hands on what it was built
    from."""
    if step not in REUSABLE_STEPS:
        return
    doc = _read(tile)
    if not doc:
        return
    committed = {k: v for k, v in (doc.get("committed") or {}).items()
                 if k != step}
    _write(tile, {"committed": committed})


def reused_label(step_label: str) -> str:
    """The progress label of a reused step."""
    return "%s · reused (unchanged since the last build)" % (step_label,)
