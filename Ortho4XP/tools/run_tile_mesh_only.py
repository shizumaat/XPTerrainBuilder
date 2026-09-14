"""Headless vector + mesh build (steps 1 and 2 only, no masks/textures).

Same initialisation as ``tools/run_tile_build.py`` (which see for why the
tile config must be loaded explicitly), but stops after the mesh step.
This is the loop for consumer-side mesh changes: it needs only
Elevation_data, OSM_data caches and Patches — no imagery.

IT ARMS THE SHARED-REPO WRITE GUARD (owner ruling e9daef5), the same
single implementation ``tools/harness/build_airport.py`` uses
(``tools/harness/shared_repo_guard.py``).  Measured 2026-08-08: two
UNGUARDED runs here (+30+031 and -13-078) silently rewrote five
inset/bathymetry manifests in the shared data repo while all 13 guarded
``build_airport.py`` runs of the same session reported it UNCHANGED.  A
warm corpus must cost ZERO writes: an unauthorised one refuses at the
call, the run audits a full before/after snapshot of the repo, the
bathymetry prefetch is joined before the guard comes down, and a refusal
the engine swallowed fails the run.  This tool has NO refresh mechanism
of its own and never will — a COLD tile is warmed deliberately with
``tools/harness/build_airport.py --refresh-data <scope>``, under a lock
and hash-stamped into the shared refresh ledger.

Usage: run_tile_mesh_only.py <latitude> <longitude> [first_step]
[--patches-as-is] [--allow-degraded-dem] (from the checkout root).
``--allow-degraded-dem`` is the SAME ruled override the build entry
carries (2026-09-10): a write the guard blocked and the engine swallowed
is accepted KNOWINGLY, on the record, for this run only — it authorises
NO write, and an unauthorised write that landed anyway still fails the
run.  Use it when the blocked write is a manifest the frame did not
depend on (the run's own log says what the frame actually resolved).
THE WINDOW IS NOT THE AUTHOR (2026-09-14, RULINGS 2026-09-01): the
run passes its INPUT SET — ``shared_repo_guard.tile_input_scope``, the
same ``BuildInputScope`` the build entry uses — so a delta a concurrent
lane wrote OUTSIDE it (another tile's DEM / OSM / masks, another
airport's road feed, a mod-cache PACK that has cached nothing for this
tile or its neighbours) while this run's own guard blocked nothing is
NAMED as an EXTERNAL CANDIDATE and does not fail the run; an in-scope
delta still refuses (rc 1, CONTAMINATED).  ``--patches-as-is`` (2026-09-04, v2 M2 mesh
A/B): step 1 does NOT resolve the X-Plane install paths, so auto_patch
generation is skipped and the ``Patches/`` files ALREADY ON DISK are meshed
exactly as they are — the deliberate measurement of a given patch's
mesh-apply cost (constrained edges, step 1/2 wall), never a trap: the
flag is explicit, the run prints it, and a run without it still refuses
when no install resolves.  ``first_step`` is 1 (default, vector then mesh)
or 2 -- the MESH REPLAY: step 2 alone, on the ``.node`` / ``.poly`` /
``.weight`` / ``.alt`` inputs already sitting in the build directory.
That is the loop for a change in the mesh CONSUMER itself (round 15's
degenerate-attribute containment), where re-running step 1 would rewrite
the very inputs under test: copy a build's four input files into a
lane-local build directory beside its ``Ortho4XP_+XX+YYY.cfg`` and the
replay meshes exactly the geometry that build meshed.  Step 1 in a
checkout that resolves no X-Plane root skips auto_patch entirely and
still exits 0 (the same trap ``harness/build_airport.py --tile``
refuses), so a patch-dependent input can only be reproduced this way.
"""
import os
import sys

sys.path.append(os.path.join(".", "src"))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "harness"))

# THE REDIRECT MUST PRECEDE THE ENGINE IMPORT (measured 2026-08-12, round
# 18).  Arming the write guard is not enough here: the auto_patch driver
# runs a ProcessPool, and a worker process has no guard — a +30+031
# mesh-only run wrote EIGHT ``Airport_mod_cache/*/o4_object_footprints_*``
# sidecars into the shared corpus with ``guard.blocked`` EMPTY, and only
# the post-run snapshot caught it (the run was flagged CONTAMINATED).
# Redirecting the engine's two writable derived-cache roots rides env
# variables, so the workers and the DSFTool subprocess inherit it, and
# ``O4_File_Names.Default_dsf_cache_dir`` is computed AT IMPORT — hence
# before the imports below.  Same single implementation as the build
# entry (``build_airport.redirect_engine_caches``); a second arrangement
# of the two halves is the defect this closes.
from build_airport import redirect_engine_caches  # noqa: E402

_CACHE_REDIRECTS = redirect_engine_caches(
    os.path.join(os.getcwd(), "tmp", "run_tile_mesh_only"), "mesh_only")

import O4_File_Names as FNAMES  # noqa: E402

sys.path.append(FNAMES.Provider_dir)
import O4_Imagery_Utils as IMG
import O4_Vector_Map as VMAP
import O4_Mesh_Utils as MESH
import O4_Config_Utils as CFG
import O4_Bathymetry_Band as BATHYBAND

# The auto_patch driver uses a ProcessPool; macOS spawn re-imports the
# main module, so an unguarded body re-runs the ENTIRE build in every
# worker (see run_tile_build.py).  The write guard and the audit belong
# in here for the same reason: a worker must never arm or audit.
if __name__ == "__main__":
    # (the harness dir is already on sys.path — the redirect above needs
    # it BEFORE the engine import)
    from shared_repo_guard import (SharedRepoWriteGuard, shared_repo_snapshot,
                                   snapshot_diff, report_unauthorised_writes,
                                   require_no_swallowed_write_block,
                                   require_no_unauthorised_writes,
                                   tile_input_scope)
    from build_airport import apply_xplane_install_paths

    IMG.initialize_extents_dict()
    IMG.initialize_color_filters_dict()
    IMG.initialize_providers_dict()
    IMG.initialize_combined_providers_dict()

    patches_as_is = "--patches-as-is" in sys.argv
    # THE RULED OVERRIDE, same single implementation the build entry uses
    # (the swallowed-block detector's own ``allow_degraded``): accept a
    # measurement in a frame the guard degraded, KNOWINGLY and on the
    # record.  It AUTHORISES NO WRITE — an unauthorised write that landed
    # anyway still fails the run through ``require_no_unauthorised_writes``.
    allow_degraded = "--allow-degraded-dem" in sys.argv
    argv = [a for a in sys.argv[1:]
            if a not in ("--patches-as-is", "--allow-degraded-dem")]
    latitude = int(argv[0])
    longitude = int(argv[1])
    first_step = int(argv[2]) if len(argv) > 2 else 1
    if first_step not in (1, 2):
        raise SystemExit("first_step must be 1 (vector+mesh) or 2 (mesh)")
    if first_step == 1:
        # THE EMPTY-CIFP TRAP, closed here too (measured 2026-08-12,
        # round 18).  ``run_auto_patch_generation`` only calls the
        # generator when it can resolve a CIFP directory, and the dev
        # tree ships ``cifp_data_path`` and ``custom_scenery_dir``
        # EMPTY — so step 1 printed "[flat-site] mode ON but no X-Plane
        # root resolved", skipped auto_patch entirely, and MESHED
        # WHATEVER PATCH FILES WERE ALREADY ON DISK.  In a lane worktree
        # those are whatever was copied in: a +30+031 mesh acceptance
        # run for round 18 meshed a patch built 2026-08-05 under a
        # different tree and reported it as the round's own surface.
        # ``harness/build_airport.py --tile`` has refused this since it
        # was written; the mesh-only entry inherits the SAME single
        # implementation rather than a second arrangement of it, and it
        # refuses identically when nothing resolves.
        if patches_as_is:
            print("--patches-as-is: auto_patch generation SKIPPED; meshing "
                  "the Patches/ files on disk as they are", flush=True)
        else:
            applied = apply_xplane_install_paths()
            print("X-Plane install paths applied:", sorted(applied))
    print("engine cache redirects:", _CACHE_REDIRECTS)
    # THE TILE FRAME, through the SHARED resolver (RULINGS 2026-08-31d):
    # the per-tile cfg is provisioned and recorded exactly as
    # ``build_airport.py --tile`` records it, and a tile with none runs
    # on the user's GLOBAL settings rather than refusing.  This entry
    # runs steps 1-2 only, which need no imagery provider at all, so a
    # frame with no provider is simply NOTED here — the geometry (and
    # the levelled-roads sidecar step 1 writes) is exactly what this
    # entry exists to produce.
    from build_airport import resolve_tile_frame
    tile, cfg_provenance, imagery = resolve_tile_frame(
        latitude, longitude, "")
    print("per-tile cfg:", cfg_provenance.get("action"),
          cfg_provenance.get("cfg"))
    if not imagery["ok"]:
        print("imagery frame:", imagery["reason"],
              "- steps 1-2 need no provider, continuing")
    print("build directory:", tile.build_dir)

    # THE RUN'S INPUT SET (2026-09-14, RULINGS 2026-09-01 "the window is
    # not the author"): the SAME ``BuildInputScope`` the build entry
    # passes, derived for a whole tile through the one shared factory —
    # this tile and its seam neighbours in both spellings, the road feeds
    # of the airports the engine's own per-tile dictionary names (read
    # off the CACHED airports layer, network-free; ``None`` when there
    # is no cache, which keeps every road feed in scope), and the mod-
    # cache packs that have cached anything for those tiles.  Measured
    # 2026-09-13: a +40-004 LEMD run with ``guard.blocked`` EMPTY failed
    # rc 1 as CONTAMINATED on 117 hash-keyed HECA-pack sidecars + 1 OTHH
    # path a concurrent lane's object stage wrote — none of them a path
    # this run reads.  With the scope they are named as EXTERNAL
    # CANDIDATES (rc 0); an in-scope write still refuses.
    def _tile_icaos():
        from auto_patch import flat_site_mode as _fsm
        return _fsm.tile_icao_candidates(
            _fsm._dico_airports_from_cache(tile)) or None
    try:
        tile_icaos = _tile_icaos()
    except Exception as exc:                # noqa: BLE001 — scope, not law
        print(f"tile airports NOT enumerated ({exc!r}): every road feed "
              f"stays in scope", flush=True)
        tile_icaos = None
    input_scope = tile_input_scope(
        latitude, longitude, tile_icaos,
        label=f"mesh-only {latitude:+03d}{longitude:+04d}")
    print("build input set:", input_scope.record(), flush=True)

    # Nothing is authorised: this entry has no --refresh-data of its own.
    before = shared_repo_snapshot()
    guard = SharedRepoWriteGuard(set(), os.getcwd())
    try:
        with guard:
            for step_name, step in (
                ("1 vector", VMAP.build_poly_file),
                ("2 mesh", MESH.build_mesh),
            )[first_step - 1:]:
                print(f"=== step {step_name} ===", flush=True)
                result = step(tile)
                if not result:
                    raise SystemExit(
                        f"step {step_name} FAILED (returned {result})")
            # The band prefetch (started inside step 1) must not outlive the
            # guard window: steps 1-2 never reach the masks step that joins
            # it, and the S13W078 band index.json measured on 2026-08-08 was
            # written by exactly that thread, after "mesh build complete".
            BATHYBAND.join_prefetches()
    finally:
        # The audit runs even when a step raised — a build that died
        # halfway has still changed the corpus every other lane reads.
        changes = snapshot_diff(before, shared_repo_snapshot())
        # ``blocked`` MUST ride along: a run whose own guard blocked
        # anything externalises NOTHING (the whole-run veto).
        offenders = report_unauthorised_writes(
            changes, set(), None, blocked=guard.blocked,
            input_scope=input_scope)
    if allow_degraded:
        print("--allow-degraded-dem: a guard-blocked write is ACCEPTED as a "
              "degraded frame for this run (it authorises no write)")
    require_no_swallowed_write_block(guard.blocked,
                                     allow_degraded=allow_degraded)
    require_no_unauthorised_writes(offenders, entry="mesh-only")
    print("mesh build complete", flush=True)
