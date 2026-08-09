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

Usage: run_tile_mesh_only.py <latitude> <longitude>   (from the checkout root)
"""
import os
import sys

sys.path.append(os.path.join(".", "src"))

import O4_File_Names as FNAMES

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
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "harness"))
    from shared_repo_guard import (SharedRepoWriteGuard, shared_repo_snapshot,
                                   snapshot_diff, report_unauthorised_writes,
                                   require_no_swallowed_write_block)

    IMG.initialize_extents_dict()
    IMG.initialize_color_filters_dict()
    IMG.initialize_providers_dict()
    IMG.initialize_combined_providers_dict()

    latitude = int(sys.argv[1])
    longitude = int(sys.argv[2])
    tile = CFG.Tile(latitude, longitude, "")
    tile.read_from_config()
    print("build directory:", tile.build_dir)

    # Nothing is authorised: this entry has no --refresh-data of its own.
    before = shared_repo_snapshot()
    guard = SharedRepoWriteGuard(set(), os.getcwd())
    try:
        with guard:
            for step_name, step in (
                ("1 vector", VMAP.build_poly_file),
                ("2 mesh", MESH.build_mesh),
            ):
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
        offenders = report_unauthorised_writes(changes, set(), None)
    require_no_swallowed_write_block(guard.blocked)
    if offenders:
        raise SystemExit(
            "REFUSING: this mesh-only run mutated the shared data repo (paths "
            "above). Owner ruling e9daef5: warm the cache deliberately with "
            "tools/harness/build_airport.py --refresh-data <scope>.")
    print("mesh build complete", flush=True)
