"""The auto-patch-v2 OBJECT STAGE after the mesh: ``rebake_after_mesh``
(the end of ``O4_Mesh_Utils.build_mesh``), the pack art checks, the
placement writes, the pack journal and the unpatched-pack restore.

Split out of ``engine_v2`` (#836): that module builds the patch (the v2
solve) in the VECTOR step; this one runs in the MESH step over the plans
and the graded surface the patch build left beside the patch.  It imports
nothing of the solve, so the mesh step's code key no longer holds it.
"""
from __future__ import annotations

import os
import re
import time
import traceback
import typing as _t


# ══════════════════════════════════════════════════════════════════════════
# THE OBJECT STAGE AFTER THE MESH (RULINGS 2026-09-04i 04f-1;
# THE SEAT RETIRED 2026-09-12s, spec §8)
# ══════════════════════════════════════════════════════════════════════════
# The retired v1 Phase 2 (``post_mesh.rebake_dsf_objects``) ran at the END
# of ``O4_Mesh_Utils.build_mesh`` / ``sort_mesh``; since v1 went (RULINGS
# 2026-09-13au) that hook routes HERE, unconditionally.  What runs here is the PLACEMENT
# path and nothing else: over the tile build's own ``o4_v2_rebake_<ICAO>.
# json`` plans — BUILT HERE from the patch build's screen sidecar and the
# cached partition (owner RULINGS 2026-10-04x (1), ``object_plan.from_screen``)
# — and a sampler of the built mesh, every object is cut,
# re-anchored and placed ON the terrain (``airport/placement_*.py``).
# NO SEAT IS COMPUTED and no authored vertex is rewritten — v1's vertex
# re-bake (``_decision_from_seats`` -> ``object_rebake.apply``, the
# ``o4_v2_rebake_result_*`` sidecars) is a refuted mechanism, DELETED.
# The pack's ``.obj.anchor_bak`` survives as the RESTORE (spec §10): a
# pack authored under the seat is put back before the placement writes.
# ``modify_custom_airports`` is honoured exactly as v1 honours it: OFF =
# measure-only, nothing is written.

#: RULINGS 2026-09-09w (3): the pipeline's own plan file names —
#: ``o4_v2_rebake_<ICAO>.json`` (``model.rebake.PLAN_FILENAME``) and
#: nothing else in the patch directory.  A tool's
#: ``o4_v2_rebake_<ICAO>.seat.json`` is NOT a plan.
_PLAN_NAME_RE = re.compile(r"^o4_v2_rebake_(?!result_)[A-Za-z0-9]{2,8}\.json$")

#: Verbosity of the one line the ``modify_custom_airports`` stand-down
#: prints (issue #42).  ABOVE the default (``O4_UI_Utils.verbosity`` 1), so
#: the owner's console stays clean when the box is unchecked while ``-v2``
#: still records which switch stood the stage down.
_STAND_DOWN_VERBOSITY = 2


# ── THE PLACEMENT PATH (owner RULINGS 2026-09-11b / 11e (3)) ─────────────
# THE ONLY OBJECT STAGE (owner RULINGS 2026-09-12s, spec §8: the seat is
# RETIRED — deleted, not gated, and with it the ``[rebake] placement``
# key that used to choose between them).  X-Plane places every object on
# the terrain under its own anchor: NO SEAT IS COMPUTED and no authored
# vertex is rewritten — the plan is built (conversions for every MSL/AGL
# row, splits with coarsened bodies and placed anchors), the cut files
# are written into the pack's ``objects/`` under new names, the DSF is
# edited, encoded, verified and backed up, the READ path's text-dump
# cache is refreshed and the placement plan lands beside the patch.

def mesh_placement_sampler(mesh_path: str,
                           bounds: tuple[float, float, float, float]):
    """The BUILT MESH as the placement stage reads it: ``sample(lat, lon)
    -> (z, is_water) | None`` with ``.many`` over the same grid index
    (RULINGS 2026-09-12g), ``None`` outside every retained triangle and
    for a non-finite height.  ONE adapter for the app
    (:func:`rebake_after_mesh`) and the replay instrument
    (``tools/obj8_split_report.py --mesh``, lane seat610): the dry run on
    the graded surface cannot see a body seated against mesh ground that
    slopes under one building (#625), so the instrument reads the same
    mesh the app seated on, through the same adapter."""
    import math
    from .mesh_sampler import MeshElevationSampler, OutsideMeshError
    sampler = MeshElevationSampler(mesh_path, bounds)

    def _sample(lat: float, lon: float, _s=sampler):
        try:
            s = _s.sample_at(lat, lon)
        except OutsideMeshError:
            return None
        z = float(s.elevation_metres)
        return (z, bool(s.is_water)) if math.isfinite(z) else None

    def _sample_many(lats, lons, _s=sampler):
        """The same grid index, one call for a whole batch.  Point-for-
        point identical to ``_sample`` — the non-finite guard included."""
        out = []
        for s in _s.sample_many(lats, lons):
            if s is None:
                out.append(None)
                continue
            z = float(s.elevation_metres)
            out.append((z, bool(s.is_water)) if math.isfinite(z) else None)
        return out

    _sample.many = _sample_many
    return _sample


def _placement_surface(mesh_sample):
    """The placement stage's design surface over a mesh sampler
    (RULINGS 2026-09-12g (2)).

    Two things the bare closure this replaced did not do, both measured
    on the shipped 1.0.320 LEMD frame:

    * ``.many`` — ``placement_geom.surface_many`` batches only when the
      sampler carries it, so 103,479 of the stage's 302,532 queries were
      taking the per-point fallback and the vectorised reading §16b was
      designed on was never taken by the app.  Here it is, backed by
      ``MeshElevationSampler.sample_many`` through ``mesh_sample.many``
      (and by a plain loop when the sampler offers none, so a graded or
      synthetic sampler still satisfies the protocol).
    * a ``(lat, lon)`` MEMO — 165,114 of those 302,532 queries were
      unique; 45 % were exact repeats.  The memo is keyed on the float
      pair as given, so a repeat is a repeat only when it is bit-equal,
      and no answer can differ from the sampler's own.
    """
    memo: dict[tuple[float, float], float | None] = {}
    #: §16e / R12 amendment 1: THE WATER BIT, beside the height.  The mesh
    #: is a datum at 0.00 over water and half of OTHH's Bridge_01 stands
    #: over the canal, so a datum's stations must be able to discard a
    #: sample on water — the SAME discard the retired seat's
    #: ``_plate_reading`` / ``_abutment_grade`` made.  It rides the
    #: surface callable as ``.water``, the way ``.roles`` and ``.many``
    #: do, so no caller between here and ``anchor_rule`` grows an
    #: argument; it is asked only at a datum's stations (OTHH: 1,033
    #: points of the stage's 336,003).
    wmemo: dict[tuple[float, float], bool] = {}
    batch = getattr(mesh_sample, "many", None)

    def _surface(lat: float, lon: float):
        key = (lat, lon)
        if key in memo:
            return memo[key]
        s = mesh_sample(lat, lon)
        z = None if s is None else float(s[0])
        memo[key] = z
        return z

    def _surface_many(lats, lons):
        lats = list(lats)
        lons = list(lons)
        answers: list[float | None] = [None] * len(lats)
        wanted: list[int] = []
        want_lat: list[float] = []
        want_lon: list[float] = []
        for index, (lat, lon) in enumerate(zip(lats, lons)):
            key = (lat, lon)
            if key in memo:
                answers[index] = memo[key]
            else:
                wanted.append(index)
                want_lat.append(lat)
                want_lon.append(lon)
        if wanted:
            if batch is not None:
                sampled = batch(want_lat, want_lon)
            else:
                sampled = [mesh_sample(a, o)
                           for a, o in zip(want_lat, want_lon)]
            for index, lat, lon, s in zip(wanted, want_lat, want_lon,
                                          sampled):
                z = None if s is None else float(s[0])
                memo[(lat, lon)] = z
                answers[index] = z
        return answers

    def _water(lat: float, lon: float) -> bool:
        key = (lat, lon)
        hit = wmemo.get(key)
        if hit is None:
            s = mesh_sample(lat, lon)
            hit = bool(s[1]) if (s is not None and len(s) > 1) else False
            wmemo[key] = hit
        return hit

    _surface.many = _surface_many
    _surface.water = _water
    return _surface


# ── MISSING ART (owner RULINGS 2026-10-06c, issue #433) ──────────────────
# X-Plane drops a WHOLE pack when its DSF declares one definition it
# cannot find.  Before the object stage reads or rewrites a pack's DSF the
# declared definitions are resolved (``auto_patch_v2.airport.pack_art``);
# a pack that fails is NAMED — one log line, one ``PackMissingArt`` event —
# and the DSF is written without the missing definitions ONLY when the
# user accepted that: the build request's ``missing_art="omit"``, or the
# pack's record already holding the acceptance of THIS pristine DSF and
# THIS missing set.  Nothing is omitted silently, and a harness / lane
# build (measure-only) only reports.

#: the build request's ``missing_art`` keyword for an in-process build
#: (``"omit"`` | ``"leave"`` | ``None`` = warn and leave the pack as it is;
#: a worker child carries it on its tile configuration instead)
MISSING_ART_POLICY: str | None = None


def set_missing_art_policy(policy: str | None) -> None:
    """The session's setter (``o4_engine.session.build``)."""
    global MISSING_ART_POLICY
    MISSING_ART_POLICY = policy if policy in ("omit", "leave") else None


class _PackArt(_t.NamedTuple):
    """One pack's missing-art verdict for one tile's DSF."""

    pack_name: str
    dsf_path: str
    missing: tuple        # ``pack_art.MissingDef`` rows; () = all installed
    omit: bool            # the user accepted building without them
    stale: bool           # the live DSF carries an omission that no longer holds
    current: bool = False  # the live DSF already carries THIS omission


def _pack_art(pack_root: str, lat: int, lon: int, *, read_only: bool,
              policy: str | None) -> "_PackArt | None":
    """THE CHECK for one pack's tile DSF, or ``None`` when there is nothing
    to judge (no DSF, no dump, no library index, a pack X-Plane does not
    load or this engine does not write).  ``read_only`` never runs
    DSFTool: the cached dump or nothing."""
    import O4_File_Names as FNAMES
    import O4_Scenery_Packs as _SP
    from auto_patch_v2.airport import backup_state as _bs
    from auto_patch_v2.airport import dsf as _dsf2
    from auto_patch_v2.airport import pack_art as _pa
    from auto_patch_v2.airport.dsf_write import pristine_dsf_path
    from auto_patch_v2.airport.file_hash import sha256_file
    from . import agp_reader as _agp
    from . import dsf_reader as _DSFR
    from .post_mesh import _is_protected_scenery_root

    if (not pack_root or not os.path.isdir(pack_root)
            or _is_protected_scenery_root(pack_root)
            or not _SP.pack_enabled(pack_root)):
        return None
    dsf_path = _dsf2.dsf_path_in_pack(pack_root, lat, lon)
    if not os.path.isfile(dsf_path):
        return None
    pack_name = os.path.basename(os.path.normpath(pack_root))
    mod_root = FNAMES.airport_mod_cache_root()
    pristine = pristine_dsf_path(dsf_path)
    dump_path = (_dsf2.find_text_dump(mod_root, pack_name, lat, lon, pristine)
                 if read_only else _DSFR.ensure_dsf_text_path(
                     pristine, _dsf2.mod_cache_dir(mod_root, pack_name)))
    if not dump_path:
        return None
    xroot = os.path.dirname(os.path.dirname(os.path.abspath(pack_root)))
    # the merged index, rebuilt when stale (a cache-version bump, #950),
    # not the read-only sidecar: the art check must not judge by an old one
    index = _agp.get_library_index(xroot)
    missing = _pa.missing_definitions(
        pack_root, dump_path, index, lambda: _agp.other_export_names(xroot))
    if missing is None:
        return None
    entry = _bs.dsf_entry(_bs.read_record(dsf_path), os.path.basename(dsf_path))
    recorded = isinstance(entry.get("omitted_art"), dict)
    current = bool(recorded and missing
                   and _pa.accepted(entry, sha256_file(pristine), missing))
    omit = False
    if missing and _pa.can_omit(missing) and policy != "leave":
        omit = policy == "omit" or current
    stale = recorded and not (omit and current)
    return _PackArt(pack_name, dsf_path, tuple(missing), omit, stale,
                    current)


def _announce_pack_art(art: "_PackArt", pack_root: str, lat: int, lon: int,
                       state: str, error: str = "") -> None:
    """The one log line and the one ``PackMissingArt`` event of a pack
    that fails the check."""
    import O4_UI_Utils as UI
    from auto_patch_v2.airport import pack_art as _pa
    UI.vprint(0, "  " + _pa.log_line(art.pack_name, art.missing)
              + {"omitted": " — written WITHOUT them, as you accepted "
                            "(the original DSF is kept as its backup)",
                 "failed": f" — the DSF without them could not be written "
                           f"({error})"}.get(state, ""))
    UI.pack_missing_art(pack=art.pack_name, pack_root=pack_root, lat=lat,
                        lon=lon, state=state, error=error,
                        **_pa.summary(art.missing))


def _write_art_only(art: "_PackArt", pack_root: str, icao: str = "") -> None:
    """Write the pack DSF with NO edit of this airport's but the art
    decision: without ``art.missing`` when the user accepted, with
    everything back when an earlier omission no longer holds.  Every
    airport's recorded placement edits are re-applied (#25's composition);
    the dump cache is refreshed as the object stage refreshes it."""
    import O4_File_Names as FNAMES
    from auto_patch_v2.airport import dsf as _dsf2
    from auto_patch_v2.airport import dsf_write as _dw
    from auto_patch_v2.model.placement import (BACKUP_SUFFIX, PlacementPlan,
                                               Provenance)
    from . import dsf_reader as _DSFR
    plan = PlacementPlan("", art.pack_name, pack_root, art.dsf_path,
                         art.dsf_path + BACKUP_SUFFIX,
                         Provenance("", _engine_version(), "", {}))
    # #598: a no-op outside a build's object stage (the user's command)
    from auto_patch_v2.airport import pack_journal as _pj
    _pj.snapshot(pack_root, art.dsf_path)
    _dw.write_pack(pack_root, plan, _DSFR._dsftool_path() or "DSFTool",
                   allow_live_install=True, engine_version=_engine_version(),
                   omit=art.missing if art.omit else ())
    _DSFR.ensure_dsf_text_path(art.dsf_path, _dsf2.mod_cache_dir(
        FNAMES.airport_mod_cache_root(), art.pack_name))


def omit_missing_art(pack_root: str, lat: int, lon: int) -> dict:
    """THE OFFER, ACCEPTED outside a build (the ``omit_missing_art``
    command): re-check the pack and write its DSF without what is still
    missing.  Returns the ``PackMissingArt`` fields, ``state`` saying what
    happened (``"omitted"`` | ``"failed"`` | ``"none"`` — nothing missing
    any more).  Never raises."""
    import O4_UI_Utils as UI
    from auto_patch_v2.airport import pack_art as _pa
    out = {"pack": os.path.basename(os.path.normpath(pack_root or "")),
           "pack_root": pack_root, "lat": int(lat), "lon": int(lon),
           "state": "none", "error": ""}
    art = None
    try:
        art = _pack_art(pack_root, int(lat), int(lon), read_only=False,
                        policy="omit")
        if art is None or not art.missing:
            return out
        out.update(_pa.summary(art.missing))
        if not art.omit:
            raise RuntimeError("a terrain definition cannot be omitted")
        _write_art_only(art, pack_root)
        out["state"] = "omitted"
    except Exception as exc:
        out["state"], out["error"] = "failed", str(exc)
        UI.vprint(2, traceback.format_exc())
    if art is not None and art.missing:
        _announce_pack_art(art, pack_root, int(lat), int(lon), out["state"],
                           out["error"])
    return out


def _art_stage(plan_, tile, *, writes: bool, place: bool) -> "_PackArt | None":
    """The missing-art step of ONE airport's pack, ahead of its object
    stage.  Returns the verdict for the placement write to carry, or
    ``None`` when there is nothing to say or do.

    When no placement write follows (``place`` False, or a read-only
    run) the step is finished here: the art decision is written when it
    changes the DSF, and the pack is named.  Otherwise
    :func:`_art_after_place` finishes it with what the write did — the
    event never claims an omission before it is on disk."""
    policy = getattr(tile, "missing_art", None) or MISSING_ART_POLICY
    try:
        art = _pack_art(getattr(plan_, "pack_root", "") or "", tile.lat,
                        tile.lon, read_only=not writes, policy=policy)
    except Exception as exc:
        # the check never costs an airport its object stage
        import O4_UI_Utils as UI
        UI.vprint(1, f"  [pack] missing-art check skipped ({exc})")
        UI.vprint(2, traceback.format_exc())
        return None
    if art is None or not (art.missing or art.stale):
        return None
    if not writes:
        if art.missing:                 # a harness / measure-only run REPORTS
            _announce_pack_art(art, plan_.pack_root, tile.lat, tile.lon,
                               "found")
        return art
    if not place:
        _art_after_place(art, plan_, tile, written=False)
    return art


def _art_after_place(art: "_PackArt", plan_, tile, *, written: bool) -> None:
    """Finish the missing-art step once the placement write is done (or
    did not happen: ``written`` False).  A write that did not carry the
    decision is made here alone — unless the live DSF already carries
    exactly this omission — then the pack is named with what is on
    disk: ``"omitted"`` | ``"failed"`` | ``"found"`` (left as it is)."""
    state, error = "found", ""
    if written:
        state = "omitted" if art.omit else "found"
    elif (art.omit and not art.current) or art.stale:
        try:
            _write_art_only(art, plan_.pack_root)
            state = "omitted" if art.omit else "found"
        except Exception as exc:
            if art.omit:
                state, error = "failed", str(exc)
            import O4_UI_Utils as UI
            UI.vprint(2, traceback.format_exc())
    elif art.omit:
        state = "omitted"               # already on disk, as accepted
    if art.missing:
        _announce_pack_art(art, plan_.pack_root, tile.lat, tile.lon, state,
                           error)


def _place_objects(plan_, law, mesh_sample, tile, patch_dir: str,
                   write_enabled: bool, measure_only: bool,
                   omit: _t.Sequence = ()) -> dict:
    """One airport's placement write (RULINGS 2026-09-11e (3)).  Returns
    the counts; raises nothing the caller does not already catch.
    ``omit`` is the missing art the user accepted to build without
    (:func:`_art_stage`); the DSF write drops it."""
    import O4_File_Names as FNAMES
    import O4_UI_Utils as UI
    from auto_patch_v2.airport import dsf as _dsf2
    from auto_patch_v2.airport import placement_write as _pw
    from . import dsf_reader as _DSFR

    pack_name = os.path.basename(os.path.normpath(plan_.pack_root))
    dsf_path = _dsf2.dsf_path_in_pack(plan_.pack_root, tile.lat, tile.lon)
    if not os.path.isfile(dsf_path):
        UI.vprint(1, f"  [v2 placement] {plan_.icao}: no DSF at {dsf_path}; skipped")
        return {}
    cache = _dsf2.mod_cache_dir(FNAMES.airport_mod_cache_root(), pack_name)
    # the PRISTINE dump (§3.4, RULINGS 2026-09-11m): ONE resolver, and
    # the cache entry is keyed on that file's CONTENT
    from auto_patch_v2.airport.dsf_write import pristine_dsf_path
    dump_path = _DSFR.ensure_dsf_text_path(pristine_dsf_path(dsf_path), cache)
    if not dump_path:
        UI.vprint(1, f"  [v2 placement] {plan_.icao}: no DSF text dump; skipped")
        return {}
    dump = _dsf2.read_dump(dump_path)

    _surface = _placement_surface(mesh_sample)

    # §6's CLASS RULE reads the emitted surface (lane v2planfix): without
    # the pads and rims ``classify_body`` can never answer ``building`` or
    # ``basin``, and the shipped path passed NEITHER — every shipped body
    # fell through to ``other`` while ``tools/obj8_split_report.py``,
    # deriving them from the same file, classified both.  ONE derivation,
    # ``placement_plan.pads_rims_from_graded``, two callers.
    from auto_patch_v2.airport import placement_plan as _pp
    from auto_patch_v2.airport import placement_boxes as _pb
    pads, rims = (), ()
    decks: tuple = ()                                               # §49
    jetway_strips: tuple = ()          # jetway-strip spec §4 (C17), #31
    drape, drape_law = {}, None        # owner RULINGS 2026-10-14d (1)
    _gd = None
    from auto_patch_v2.model.rebake import graded_surface_path
    graded = graded_surface_path(patch_dir, plan_.icao)
    if os.path.isfile(graded):
        try:
            import json as _json
            with open(graded, encoding="utf-8") as _fh:
                _gd = _json.loads(_fh.read())
            pads, rims = _pp.pads_rims_from_graded_doc(_gd)
            decks = _pp.decks_from_graded_doc(_gd)                  # §49
            jetway_strips = tuple((_gd.get("provenance") or {})
                                  .get("jetway_strips") or ())
            # §17 (owner RULINGS 2026-09-12am (2)): the FACE ROLE under a
            # point, off the SAME parsed document — what says whether a
            # foot stands where the aircraft ROLLS.  §9's anchor reads it
            # through the sampler (``surface.roles`` beside
            # ``surface.many``): a body every foot of which stands on
            # rolled-on pavement keeps the MEDIAN of its feet instead of
            # its low-side one.  Without this the shipped path would take
            # the low-side rule everywhere while the dry-run tool took the
            # median — the v2planfix defect over again.
            from auto_patch_v2.law import tables as _T
            _surface.roles = _pb.graded_roles_from_doc(
                _gd, rank=lambda r: _T.authority_rank(law, r))
            _surface.rolled_on = frozenset(_T.rolled_on_roles(law))
            UI.vprint(1, f"  [v2 placement] {plan_.icao}: design surface "
                         f"{len(pads)} object pad(s), {len(rims)} structure "
                         f"rim(s), {len(_surface.roles.faces)} graded face(s) "
                         f"for the §17 motion rule")
        except Exception as exc:                   # a malformed surface
            UI.vprint(1, f"  [v2 placement] {plan_.icao}: {os.path.basename(graded)} "
                         f"unreadable ({exc}) — pads/rims unavailable")
    else:
        UI.vprint(1, f"  [v2 placement] {plan_.icao}: no {os.path.basename(graded)} "
                     "beside the patch — no body can classify as building or basin")
    # owner RULINGS 2026-10-14d (1): the base slabs over sloping ground DRAPE
    # (their up faces laid on this surface); a failure here drapes nothing
    # and never costs the pads above
    if _gd is not None:
        try:
            from auto_patch_v2.airport import slab_drape as _sd
            drape, drape_law, _drows = _sd.drape_for_graded(plan_, _gd, law, _surface)
            for _r in _drows:
                UI.vprint(1, f"  [v2 placement] {plan_.icao}: base slab "
                             f"{_r.resource} c{_r.comp} {_r.open_m2:,.0f} m2 at "
                             f"{_r.lat:.6f}, {_r.lon:.6f}: ground relief "
                             f"{_r.relief_m:.2f} m -> "
                             + ("DRAPED" if _r.drape else "rigid")
                             + ("" if _r.touches else " (no wall: drape side)"))
        except Exception as exc:
            drape, drape_law = {}, None
            UI.vprint(1, f"  [v2 placement] {plan_.icao}: base-slab drape read "
                         f"failed ({exc}) — no slab drapes")

    from auto_patch_v2.law.tables import law_tables_digest
    digest = str(law_tables_digest().get("sha256") or "")
    plan, files, ss = _pw.build_plan(
        plan_, dump, _surface, icao=plan_.icao, pack_name=pack_name,
        pack_root=plan_.pack_root, dsf_path=dsf_path,
        split_tol_m=law.tables.structures.placement.split_tol_m,
        elevated_base_m=law.tables.structures.rebake.elevated_base_m,
        line_segment_m=law.tables.structures.placement.line_segment_m,
        line_stations_max=law.tables.structures.rebake.line_object_stations_max,
        line_ratio=law.tables.structures.rebake.line_object_ratio,
        line_max_h=law.tables.structures.rebake.line_object_max_h,
        foot_band_m=law.tables.structures.basin.contact_band_m,
        coarsen_reach_m=law.tables.structures.placement.coarsen_reach_m,
        contact_eps_m=law.tables.structures.placement.contact_eps_m,
        rigid_reach_m=law.tables.structures.placement.rigid_reach_m,
        # (A), owner RULINGS 2026-09-12ap: the height a cross-member
        # §16c (7) bind may move a body off its OWN ground.
        bind_ground_m=law.tables.emit.cockpit.visual_m,
        # #610/#625: a body under ONE roof with the cluster is bound past
        # that test while the step at its feet is under the terrace floor
        # (a weld, RULINGS 2026-09-30i); a terrace-sized step is the
        # terrain's to adapt and is reported, not seated
        roof_bind_m=law.tables.emit.terrace.pad_terrace_floor_m,
        # §16f (7) (owner RULINGS 2026-09-13bj item 1): the footprint-union
        # area above which a family is a CLUSTER and seats as one unit.
        cluster_min_m2=law.tables.structures.placement.cluster_pad_min_m2,
        # §16g (owner RULINGS 2026-09-13bo): the FOOTPRINT UNIT and the
        # only cut (the HECA elevated-rail connector class).
        touch_m=law.tables.structures.placement.footprint_touch_m,
        connector_span_m=law.tables.structures.placement.connector_span_m,
        # §16g (10) (4) (owner RULINGS 2026-09-14ah): only a WALLED body
        # links a unit — a floor slab, a plate, a deck or a canopy is a
        # LEAF, seated on its own ground and never a link.
        chain_min_height_m=law.tables.structures.placement.chain_min_height_m,
        # RULINGS 2026-10-14p (3) (#709): a building's small pieces ride its walls
        piece_reach_m=law.tables.structures.placement.piece_reach_m,
        # S6 CONTENTS (issue #30 / #10): a leaf inside a walled host is the
        # host's CONTENTS and rides the host's unit (never decomposed apart)
        contents_min_fraction=(law.tables.structures.placement
                               .contents_min_fraction),
        # §16g (10) (4) AMENDED (owner RULINGS 2026-09-27a (1), #69): a
        # roof/floor SHEET overlapping two walled bodies links them
        sheet_chain_min_fraction=(law.tables.structures.placement
                                  .sheet_chain_min_fraction),
        # §16g (10) (9) (2) (owner RULINGS 2026-09-14az): the unit seated
        # on a pad takes the pad's LOW side, not its median
        low_side=bool(getattr(law.tables.structures.placement,
                              'pad_between_aprons', False)),
        # §16g (5) (owner RULINGS 2026-09-13cb): "on ground" is only where
        # the terrain at the anchor already IS the unit's datum
        hard_tol_m=law.tables.emit.design.hard_tol_m,
        # §16e (6): the deck end line's LANDWARD WALK to the graded face
        # the deck connects to (RULINGS 2026-09-13v).
        abutment_step_m=law.tables.structures.bridge.abutment_sample_step_m,
        abutment_walk_max_m=law.tables.structures.bridge.abutment_walk_max_m,
        pads=pads, rims=rims,
        # §49: the emitted deck faces are a datum for the bodies on them
        decks=decks,
        deck_on_fraction=law.tables.structures.deck.on_fraction,
        deck_edge_m=law.tables.structures.deck.edge_m,
        deck_under_m=law.tables.structures.deck.under_m,
        # 10-01k Q1 (#162): a FEET-verdict post base over a graded apron
        # is seated by baking its own TILT, capped by this
        seat_tilt_max_deg=float(
            law.tables.structures.placement.seat_tilt_max_deg),
        # RULINGS 2026-10-14p (1) (#708): a shared frame tilts as one, gently
        frame_tilt_max_deg=float(
            law.tables.structures.placement.frame_tilt_max_deg),
        # 14g (2)/(3): an authored placement our ground asks nothing of
        # is kept (an AGL row stays AGL; a split that moves nothing is not made)
        authored_keep_tol_m=float(
            law.tables.structures.placement.authored_keep_tol_m),
        # jetway-strip spec §4 (C17): the riders' population and strips
        jetway_strips=jetway_strips,
        # a CLAMPED GATE is a clamp within D of the rider (#31)
        jetway_strip_m=float(law.tables.emit.design.jetway_strip_m),
        drape=drape, drape_law=drape_law,
        engine_version=_engine_version(), law_digest=digest,
        write_cuts=bool(write_enabled and not measure_only))
    c = dict(plan.counts())
    # §6's CLASSES ride out with the counts (lane v2planfix): they are the
    # only reading that says whether the pads and rims above were seen at
    # all — with none, every body reads ``class_other``.
    c.update({k: int(v) for k, v in ss.counts.items() if k.startswith("class_")})
    if not write_enabled or measure_only:
        UI.vprint(1, f"  [v2 placement] {plan_.icao}: MEASURE ONLY — "
                     f"{c['conversions']} conversion(s), {c['splits']} split(s) into "
                     f"{c['bodies']} body file(s), {c['kept']} kept; nothing written")
        return c
    from auto_patch_v2.airport.backup_state import (BackupUnproven,
                                                    SUPERSEDED_INFIX as
                                                    _BS_SUPERSEDED,
                                                    UNRECOGNISED_INFIX as
                                                    _BS_UNRECOGNISED)
    try:
        res = _pw.apply_plan(
            plan, files, _DSFR._dsftool_path() or "DSFTool", patch_dir=patch_dir,
            allow_live_install=True,
            refresh_dump=lambda p, _c=cache: _DSFR.ensure_dsf_text_path(p, _c),
            engine_version=_engine_version(), law_digest=digest, omit=omit)
    except BackupUnproven as exc:
        # §12a (4): ONE line, at verbosity 0.  NOTHING in the pack was
        # touched — not the DSF, not an object, not a cut file: a pack
        # half-written against a DSF we may not touch is torn geometry.
        UI.vprint(0, f'  [v2 placement] PACK NOT TOUCHED: "{pack_name}" — '
                     f'{exc}')
        return {}
    # §12a (4): ONE line per pack per build when the rule had to act;
    # NOTHING on the normal path (D3 / D4, O1 / O2).
    _adopted = list(res.restore.adopted)
    _unproven = list(res.restore.unproven)
    if res.dsf is not None:
        for note in res.dsf.notes:
            UI.vprint(0, f'  [v2 placement] PACK UPDATED: "{pack_name}" — {note}')
        if res.dsf.composed_airports:
            # #25: one pack DSF serving two airports (TNCM + TFFG) — the
            # sibling's recorded edits were re-applied beside this one's
            UI.vprint(1, f"  [v2 placement] {plan_.icao}: "
                         f"{os.path.basename(res.dsf.dsf_path)} also carries "
                         f"{', '.join(res.dsf.composed_airports)} — their "
                         f"recorded placements were re-applied with this "
                         f"airport's"
                         + (f"; {len(res.dsf.orphaned_bodies)} orphaned body "
                            f"file(s) removed" if res.dsf.orphaned_bodies
                            else ""))
    if _adopted or _unproven:
        UI.vprint(0, f'  [v2 placement] PACK UPDATED: "{pack_name}" — '
                     f'{len(_adopted)} file(s) of yours were kept as installed '
                     f'(their old backups are now *{_BS_SUPERSEDED}<date>)'
                     + (f'; {len(_unproven)} object(s) could not be proven and '
                        f'their bytes were kept as *{_BS_UNRECOGNISED}<date>'
                        if _unproven else ''))
    UI.vprint(1, f"  [v2 placement] {plan_.icao}: "
                 f"{len(res.restore.restored)}/{len(res.restore.backups)} object(s) "
                 f"restored from .anchor_bak, {c['conversions']} placement(s) "
                 f"converted to on-ground, {c['splits']} split into "
                 f"{len(res.files_written)} body file(s), {c['kept']} kept whole; "
                 f"DSF rewritten (backup {os.path.basename(res.dsf.backup_path)}, "
                 f"round trip {'ok' if res.dsf.report.ok else 'FAILED'}), dump cache "
                 f"{'refreshed' if res.dump_refreshed else 'not refreshed'} -> "
                 f"{os.path.basename(res.plan_path)}")
    out = dict(res.counts)
    out.update({k: v for k, v in c.items() if k.startswith("class_")})
    out["packs_written"] = 1
    return out


def _engine_version() -> str:
    try:
        from . import provenance as _prov
        return str(_prov.engine_version() or "")
    except Exception:
        return ""


def restore_stopped_build(build_dir: str, lat: int, lon: int) -> list:
    """A BUILD THAT DID NOT COMPLETE PUTS THE SCENERY PACKS BACK (owner
    decision 2026-10-12, #598): every pack file the object stage of that
    build rewrote is as it was BEFORE the build — the seating that
    matches the scenery still active, not the pristine pack.  Called
    when a build is stopped, and before a tile's next build when the last
    one was killed (``pack_journal``).

    Returns one sentence per pack that could NOT be put back (also said
    as a warning); silent and read-free when the build rewrote no pack.
    Never raises."""
    import O4_File_Names as FNAMES
    import O4_UI_Utils as UI
    from auto_patch_v2.airport import pack_journal as _pj
    unproven: list = []
    try:
        tile_name = FNAMES.short_latlon(lat, lon)
        if not _pj.pending(build_dir, tile_name):
            return unproven
        done = _pj.replay(build_dir, tile_name, allow_live_install=True)
        for out in done:
            pack = os.path.basename(os.path.normpath(out.pack_root))
            if out.state == _pj.UNPROVEN:
                text = (f"The scenery pack {pack} was changed by the build "
                        f"that did not finish and could not be put back as "
                        f"it was: {out.reason} Its objects may float or "
                        f"sink until the tile is built again.")
                unproven.append(text)
                UI.loud_warning("   " + text)
            else:
                UI.vprint(0, f"  [v2 rebake] pack {pack} "
                             f"{os.path.basename(out.dsf_path)} is back as it "
                             f"was before the build that did not finish")
    except Exception as exc:
        text = (f"The scenery packs changed by the build that did not finish "
                f"could not be put back as they were ({exc}). Their objects "
                f"may float or sink until the tile is built again.")
        unproven.append(text)
        UI.loud_warning("   " + text)
        UI.vprint(2, traceback.format_exc())
    return unproven


def discard_pack_journal(build_dir: str, lat: int, lon: int) -> None:
    """The build COMPLETED: its pack writes stand (#598)."""
    import O4_File_Names as FNAMES
    from auto_patch_v2.airport import pack_journal as _pj
    _pj.discard(build_dir, FNAMES.short_latlon(lat, lon))


def _pack_journalled(stage):
    """The object stage of one tile's build, with the pack files it
    rewrites kept as they were until the build completes (#598): a
    journal an earlier build left is that build never completing — it is
    put back first — and every pack write of ``stage`` is journalled."""
    import functools

    @functools.wraps(stage)
    def journalled(tile) -> dict:
        import O4_File_Names as FNAMES
        from auto_patch_v2.airport import pack_journal as _pj
        restore_stopped_build(tile.build_dir, tile.lat, tile.lon)
        _pj.begin(tile.build_dir, FNAMES.short_latlon(tile.lat, tile.lon))
        try:
            return stage(tile)
        finally:
            _pj.end()
    return journalled


@_pack_journalled
def rebake_after_mesh(tile) -> dict:
    """Run the PLACEMENT stage for every airport v2 patched on ``tile``
    against the mesh just built (see the section comment).  Never raises
    (the mesh hook wraps it too); returns the counts for the summary."""
    import glob
    import O4_File_Names as FNAMES
    import O4_UI_Utils as UI
    from auto_patch_v2.law import Law
    from auto_patch_v2.model import rebake as _rb
    from .post_mesh import (_is_protected_scenery_root, _mesh_is_newer_than_alt,
                            object_anchor_worklist_path)

    counts = {"airports": 0, "airports_failed": 0, "packs_written": 0}
    # RULINGS 2026-10-12d, BEFORE every gate and every early return below:
    # an unpatched airport has no plan here (it was set aside with its
    # patch), a tile whose every airport failed has no plan at all, and
    # the placement loop would otherwise RE-APPLY the unpatched airport's
    # recorded edits when it writes a sibling served by the same DSF.
    # Silent and read-free when the tile has no unpatched airport.
    restored = restore_unpatched_packs(tile)
    if restored["restored"] or restored["recomposed"]:
        counts["packs_restored"] = restored["restored"] + restored["recomposed"]
    # THE USER'S SWITCH IS A STAND-DOWN, NOT A MEASURE-ONLY ARM (owner
    # ruling RULINGS 2026-09-18a (3), BETA2 GEN-1; issue #42).  When the
    # user unchecks "Modify custom airports" the whole placement stage is
    # skipped: no pack DSF dump into the mod cache, no placement plan, no
    # ``[v2 placement]`` output.  The env arms further down
    # (``O4_PACK_WRITES=measure_only``, the ``DSF_OBJECT_REANCHOR`` kill
    # switch) exist precisely to KEEP the measurement while standing the
    # writes down, so they do NOT take this return.
    #
    # ISSUE #42, THE SECOND HALF: THE STAND-DOWN IS ALSO SILENT, AND IT
    # COMES FIRST.  The 09-18a arm sat BELOW the plan glob and the two
    # mesh tests, so a build with the box unchecked still printed
    # ``[v2 rebake] STALE MESH …`` (at verbosity 0, so always), ``[v2
    # rebake] mesh not found …``, or ``[v2 rebake] failed: …`` from the
    # wrapper when the worklist path itself raised — the owner's report on
    # build 350 ("if the box is not checked, nothing in the airport should
    # be modified, so why any ``[v2 rebake]`` lines?").  A stage that is
    # standing down reads no mesh, so it has nothing to say about one:
    # the gate is now the FIRST statement of the stage, above every other
    # read and every other print, and its own line is ``vprint(2)`` — the
    # console at default verbosity carries NO ``[v2 rebake]`` line at all,
    # while ``-v2`` still names the switch for anyone debugging.
    if not getattr(tile, "modify_custom_airports", True):
        UI.vprint(_STAND_DOWN_VERBOSITY,
                  "  [v2 rebake] modify_custom_airports is off — "
                  "placement stage skipped entirely (no pack is read, "
                  "dumped or written, no placement plan is computed)")
        return counts
    try:
        patch_dir = os.path.dirname(object_anchor_worklist_path(tile))
        # RULINGS 2026-09-09w (3): the engine loads ITS OWN plan files only.
        # ``o4_v2_rebake_*.json`` also matched a tool's output beside them
        # (``tools/v2_rebake_replay.py`` writes ``o4_v2_rebake_<ICAO>.seat.
        # json``), which the loader then tried to read as a plan.
        # A SCREEN SIDECAR IS A PLAN NOT YET BUILT (owner RULINGS 2026-10-04x
        # (1)): the worklist is every plan file and every sidecar's plan,
        # in the plan files' own order.
        from auto_patch_v2.airport import object_plan as _oplan
        from auto_patch_v2.airport import rebake_screen as _rscreen
        found = glob.glob(os.path.join(patch_dir, "o4_v2_rebake_*.json"))
        screens = {p[:-len(".screen.json")] + ".json": p for p in found
                   if _oplan.SCREEN_NAME_RE.match(os.path.basename(p))}
        plans = sorted({p for p in found
                        if _PLAN_NAME_RE.match(os.path.basename(p))} | set(screens))
        if not plans:
            return counts
        mesh_path = FNAMES.mesh_file(tile.build_dir, tile.lat, tile.lon)
        if not os.path.isfile(mesh_path):
            UI.vprint(1, f"  [v2 rebake] mesh not found at {mesh_path}; placement skipped")
            return counts
        if not _mesh_is_newer_than_alt(tile, mesh_path):
            UI.vprint(0, "  [v2 rebake] STALE MESH: the mesh predates the tile's .alt — "
                         "placement SKIPPED; rebuild the mesh after the elevation step")
            return counts
        # the user's switch stood the whole stage down above; what is left
        # here are the ENV arms, which keep the measurement
        measure_only = False
        # v1's engine-wide kill switch (``O4_DSF_OBJECT_REANCHOR=0`` "leaves
        # every pack byte-identical"; function-local import so tests drive
        # it): the placement plan is still built and reported — the
        # measurement is the product — but nothing is written.
        # THE LANE STAND-DOWN (owner ruling e9daef5 + the lane protocol;
        # measured 2026-09-15, RULINGS 2026-09-15av).  The write half
        # below targets the SERVING PACK, which lives in the owner's
        # X-Plane install — outside the shared data repo, so neither the
        # shared-repo write guard nor the harness's cache redirects ever
        # covered it.  Lane v2vmmcshore's harness TILE build of +22+113
        # rewrote the OWNER'S live VHHH pack DSF (6,390 placements) at
        # 11:49 and re-dumped it at 11:52, and the flag surfaced on a
        # DIFFERENT lane's concurrent build.  The harness sets
        # ``O4_PACK_WRITES=measure_only`` on every lane build; the APP
        # sets nothing and writes exactly as before, and an owner-
        # authorised ``--refresh-data pack_rebake`` clears it.  Measure-
        # only keeps the MEASUREMENT whole — the placement plan is still
        # built, classified and reported; only the writes stand down.
        if os.environ.get("O4_PACK_WRITES") == "measure_only":
            measure_only = True
            UI.vprint(0,
                "  [v2 rebake] LANE BUILD (O4_PACK_WRITES=measure_only): the "
                "placement plan is measured and recorded and NO pack file is "
                "written — a lane never mutates the owner's X-Plane install "
                "(RULINGS 2026-09-15av).  --refresh-data pack_rebake is the "
                "owner's act.")
        from .config import DSF_OBJECT_REANCHOR
        write_enabled = bool(DSF_OBJECT_REANCHOR)
        if not write_enabled:
            UI.vprint(1, "  [v2 rebake] DSF_OBJECT_REANCHOR is off — the placement plan "
                         "is measured and recorded, no pack file is written")
        written_packs: set[str] = set()
        ran_packs: set[str] = set()
        t_stage = time.monotonic()
        reuse = _stage_reuse(tile, mesh_path)
        for plan_path in plans:
            icao = "?"
            try:
                screen = plan_ = None
                if plan_path in screens:
                    screen = _rscreen.read(screens[plan_path])
                    icao = screen.icao
                else:
                    with open(plan_path) as fh:
                        plan_ = _rb.RebakePlan.from_json(fh.read())
                    icao = plan_.icao
                # A PLAN WHOSE PATCH IS NOT IN THIS MESH IS NEVER PLACED
                # (lane ``othhjunction``, #13/#15): the plan is the auto
                # patch's design surface; a manual patch, the mode filter
                # or a boundary skip means the mesh was built WITHOUT that
                # surface, and placing (splitting, rewriting the pack DSF)
                # against it seats objects on ground that is not there.
                # ONE admission test, the patch ingest's own.
                from . import selection as _SELECTION
                not_applied = _SELECTION.auto_patch_not_applied(
                    tile, icao, patch_dir=patch_dir)
                if not_applied:
                    UI.vprint(0, f"  [v2 rebake] {icao}: placement SKIPPED — its "
                                 f"auto patch is not in this mesh ({not_applied})")
                    counts["airports_skipped_unapplied"] = \
                        counts.get("airports_skipped_unapplied", 0) + 1
                    continue
                law = Law.for_airport(icao)
                if screen is not None:
                    plan_ = _oplan.from_screen(
                        screen, plan_path, patch_dir, law, say=UI.vprint,
                        mod_cache_root=FNAMES.airport_mod_cache_root())
                    if plan_ is None:
                        counts["airports_skipped_stale_plan"] = \
                            counts.get("airports_skipped_stale_plan", 0) + 1
                        continue
                # #433: THE PACK'S MISSING ART, before its DSF is read or
                # rewritten — and whether or not anything is placed
                writes = bool(write_enabled and not measure_only)
                art = _art_stage(plan_, tile, writes=writes,
                                 place=bool(plan_.units))
                if not plan_.units:
                    UI.vprint(1, f"  [v2 rebake] {icao}: no unit to place "
                                 f"({len(plan_.skipped)} resource(s) skipped at plan time)")
                    counts["airports"] += 1
                    continue
                if not os.path.isdir(plan_.pack_root) or \
                        _is_protected_scenery_root(plan_.pack_root):
                    UI.vprint(1, f"  [v2 rebake] {icao}: pack {plan_.pack_root} is not a "
                                 "writable Custom Scenery pack — placement skipped")
                    counts["airports"] += 1
                    continue
                # A DISABLED PACK IS NEVER REWRITTEN (owner RULINGS
                # 2026-09-18 17b/c: "its files are not rewritten"; §12a
                # (3) row 15).  v1 had this test (``object_rebake.py``
                # :1339) and the v2 write path had none, so a plan JSON
                # left beside the patch from before the user disabled a
                # pack would still have been classified, adopted,
                # restored and written.
                import O4_Scenery_Packs as _SP
                if not _SP.pack_enabled(plan_.pack_root):
                    UI.vprint(1, f"  [v2 rebake] {icao}: pack "
                                 f"{os.path.basename(os.path.normpath(plan_.pack_root))}"
                                 " is DISABLED in scenery_packs.ini — "
                                 "nothing is read, classified or written")
                    counts["airports"] += 1
                    continue
                omit = art.missing if art is not None and art.omit else ()

                # THE PLACEMENT PATH (11e (3); the ONLY object stage
                # since 2026-09-12s) — no seat is computed; served from
                # the airport's record when nothing it reads changed (#879)
                def _compute(plan_=plan_, law=law, omit=omit):
                    return _place_objects(
                        plan_, law,
                        mesh_placement_sampler(mesh_path, plan_.bounds()),
                        tile, patch_dir, write_enabled, measure_only,
                        omit=omit)
                pc = {}
                served = reuse.reused if reuse is not None else 0
                try:
                    recipe = _reuse_recipe(reuse, plan_, tile, patch_dir,
                                           writes=(write_enabled, measure_only),
                                           omit=omit)
                    pc = (reuse.run(icao, _reuse_folder(plan_), recipe, _compute)
                          if recipe is not None else _compute())
                finally:
                    # #433: the art decision, finished with what the
                    # placement write did (a raise wrote nothing)
                    if art is not None and writes:
                        _art_after_place(art, plan_, tile, written=bool(
                            pc.get("packs_written")))
                counts["airports"] += 1
                for k, v in pc.items():
                    if k in ("packs_written",):
                        continue
                    counts["placement_" + k] = counts.get("placement_" + k, 0) + int(v)
                if pc.get("packs_written"):
                    written_packs.add(plan_.pack_root)
                    if reuse is None or reuse.reused == served:
                        ran_packs.add(plan_.pack_root)
            except Exception as exc:
                counts["airports_failed"] += 1
                UI.vprint(1, f"  [v2 rebake] {icao}: placement failed ({exc}); continuing")
                UI.vprint(2, traceback.format_exc())
        counts["packs_written"] = len(written_packs)
        if reuse is not None:
            reuse.finish()
            counts["airports_reused"] = reuse.reused
            UI.vprint(1, f"  [v2 rebake] object stage: {reuse.reused} airport(s) "
                         f"reused, {reuse.ran} ran "
                         f"({time.monotonic() - t_stage:.1f} s)")
        for pr in sorted(ran_packs):
            UI.vprint(1, f"  [v2 rebake] pack {os.path.basename(pr)} was modified "
                         "(originals kept as .anchor_bak) — restart X-Plane, objects are cached")
    except Exception as exc:
        UI.vprint(1, f"  [v2 rebake] failed: {exc}")
        UI.vprint(2, traceback.format_exc())
    return counts


def reuse_enabled(environ=None) -> bool:
    """THE OBJECT STAGE REUSE'S SWITCH (#879): on unless
    ``O4_OBJECT_STAGE_REUSE=0`` (``object_stage_reuse.ENV_SWITCH``).  Read
    here, not in ``auto_patch_v2`` (which reads no environment), and handed
    to the reuse as ``on``."""
    from auto_patch_v2.airport.object_stage_reuse import ENV_SWITCH
    env = os.environ if environ is None else environ
    return str(env.get(ENV_SWITCH, "1")).strip() != "0"


def _stage_reuse(tile, mesh_path: str):
    """The object stage's reuse for this tile's run (#879,
    ``airport/object_stage_reuse``), or ``None`` when it cannot be set up
    (every airport then runs, as before)."""
    try:
        import O4_File_Names as FNAMES
        import O4_Object_Stage_Code as _osc
        import O4_UI_Utils as UI
        from auto_patch_v2.airport import object_stage_reuse as _osr
        from auto_patch_v2.airport import pack_journal as _pj
        from auto_patch_v2.pipeline import xplat as _xplat
        tile_name = FNAMES.short_latlon(tile.lat, tile.lon)
        return _osr.StageReuse(
            tile_name, mesh_path, code=_osc.runtime_digest(),
            env=_xplat.environment(),
            exclude_dirs=(_pj.path_for(tile.build_dir, tile_name),),
            cache_root=FNAMES.airport_mod_cache_root(), on=reuse_enabled(),
            say=lambda line: UI.vprint(1, line))
    except Exception:
        return None


def _reuse_folder(plan_) -> str:
    """Where an airport's object-stage record is kept: its pack's mod-cache
    folder, beside the partition and the v2 stage records."""
    import O4_File_Names as FNAMES
    from auto_patch_v2.airport import dsf as _dsf2
    return _dsf2.mod_cache_dir(FNAMES.airport_mod_cache_root(),
                               os.path.basename(os.path.normpath(plan_.pack_root)))


def _reuse_recipe(reuse, plan_, tile, patch_dir: str, *, writes: tuple,
                  omit: _t.Sequence) -> "dict | None":
    """One airport's reuse key (``object_stage_reuse.airport_recipe``), or
    ``None``: no reuse, or a key that could not be taken (it runs)."""
    if reuse is None:
        return None
    try:
        return reuse.airport_recipe(plan_, tile.lat, tile.lon, patch_dir,
                                    writes=writes, omit=omit,
                                    engine=_engine_version())
    except Exception:
        return None


def _pack_stand_down(tile) -> str:
    """Why no pack file may be written by this build, or ``""`` — the
    object stage's three switches, in one place for the unpatched-airport
    restore (the placement loop below words its own lines)."""
    from .config import DSF_OBJECT_REANCHOR
    if not getattr(tile, "modify_custom_airports", True):
        return '"Modify custom airports" is off'
    if os.environ.get("O4_PACK_WRITES") == "measure_only":
        return "this is a lane build (O4_PACK_WRITES=measure_only)"
    if not DSF_OBJECT_REANCHOR:
        return "DSF_OBJECT_REANCHOR is off"
    return ""


def restore_unpatched_packs(tile, scenery_dir: str | None = None) -> dict:
    """AN AIRPORT LEFT WITHOUT A PATCH GETS ITS ORIGINAL PACK BACK (owner
    RULINGS 2026-10-12d).  For every airport this tile is built without
    (``O4_Unpatched_Airports.read``), every pack DSF of this tile an
    earlier build re-seated for it is restored
    (``unpatched_pack.restore_airport``); a restore that cannot be done
    or proven is NAMED on that airport's record and in the log.

    The packs are found from the engine's own write records
    (``object_rebake.modified_packs``) — the airport's plan was set aside
    with its patch.  A disabled pack and a pack inside the base simulator
    are never touched; an airport no record names is a no-op.  Returns
    ``{"restored": n, "recomposed": n, "unproven": n}``.  Never raises."""
    import O4_File_Names as FNAMES
    import O4_Scenery_Packs as _SP
    import O4_UI_Utils as UI
    import O4_Unpatched_Airports as UNPATCHED
    from auto_patch_v2.airport import unpatched_pack as _up
    from . import dsf_reader as _DSFR
    from . import object_rebake as _OR
    from .post_mesh import _is_protected_scenery_root

    counts = {_up.RESTORED: 0, _up.RECOMPOSED: 0, _up.UNPROVEN: 0}
    try:
        unpatched = [rec["icao"] for rec in UNPATCHED.read(tile)]
        if not unpatched:
            return counts
        if scenery_dir is None:
            import O4_Config_Utils as CFG
            scenery_dir = getattr(CFG, "custom_scenery_dir", "") or ""
        tile_name = FNAMES.short_latlon(tile.lat, tile.lon)
        stand_down = _pack_stand_down(tile)
        for pack in _OR.modified_packs(scenery_dir, tile_name):
            pack_root = pack["pack_path"]
            if _is_protected_scenery_root(pack_root) \
                    or not _SP.pack_enabled(pack_root):
                continue
            for record_path in _OR._v2_record_paths(pack_root):
                dsf_path = os.path.join(os.path.dirname(record_path),
                                        tile_name + ".dsf")
                for icao in sorted(set(unpatched)
                                   & set(_up.seated_airports(dsf_path))):
                    if stand_down:
                        out = _up.Outcome(_up.UNPROVEN, dsf_path, reason=(
                            "it was not restored because " + stand_down))
                    else:
                        try:
                            out = _up.restore_airport(
                                pack_root, dsf_path, icao,
                                _DSFR._dsftool_path() or "DSFTool",
                                allow_live_install=True,
                                engine_version=_engine_version())
                        except Exception as exc:
                            out = _up.Outcome(_up.UNPROVEN, dsf_path,
                                              reason=str(exc))
                    counts[out.state] = counts.get(out.state, 0) + 1
                    if out.state == _up.UNPROVEN:
                        text = (
                            f"The scenery pack {pack['pack_name']} was changed "
                            f"by an earlier build for this airport's graded "
                            f"ground and could not be put back to its "
                            f"original: {out.reason} Its objects may float or "
                            f"sink there.")
                        UNPATCHED.note_pack(
                            tile, icao, text, pack=str(pack["pack_name"]),
                            reason=str(out.reason))
                        UI.loud_warning(f"   {icao}: {text}")
                    elif out.state != _up.NONE:
                        kept = (f"; {', '.join(out.kept)} keep their placements"
                                if out.kept else "")
                        UI.vprint(0, f"  [v2 rebake] {icao}: left without a "
                                     f"patch — pack {pack['pack_name']} "
                                     f"{tile_name}.dsf is back to its original "
                                     f"for this airport ("
                                     f"{len(out.bodies_removed)} split "
                                     f"bod(ies) removed{kept})")
    except Exception as exc:
        UI.vprint(1, f"  [v2 rebake] unpatched-airport pack restore failed: {exc}")
        UI.vprint(2, traceback.format_exc())
    return counts
