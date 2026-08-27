#!/usr/bin/env python3
import sys
import os

# FIRST, before any other work: claim the multiprocessing spawn bootstrap.
# A frozen child is not a re-import — it is this executable re-exec'd as
# `Ortho4XP --multiprocessing-fork tracker_fd=.. pipe_handle=..`
# (multiprocessing.spawn.get_command_line takes its `sys.frozen` branch), so
# the "__mp_main__" guards below cannot see it.  PyInstaller's rthook only
# DEFINES multiprocessing.freeze_support as the diverter; the frozen app must
# call it, or the child falls through to the CLI dispatch at the foot of this
# file, prints USAGE and exits 0.  Its parent then blocks in
# BaseManager.start() reading an address off a pipe nobody will write, and
# the auto-patch pool dies with a bare EOFError — logged as the empty
# "parallel build unavailable (  )" before falling back to serial (2026-07-24).
# From source this is a no-op: that path spawns `python -c spawn_main(...)`
# and needs no diversion.
if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()

# Engine subprocesses are spawned WITHOUT a Popen cwd: passing one forces
# the parent off posix_spawn onto fork+exec, and a fork in a pyproj-loaded
# parent dies in the proj.db sqlite atfork handler (2026-07-16 crash
# class).  A from-source engine child therefore anchors itself here,
# post-exec, where chdir is safe — same effective directory as before.
# The __name__ guard mirrors the engine dispatch below: multiprocessing
# helpers re-import this module as "__mp_main__" with the parent's argv
# restored, and they inherit the already-corrected cwd from their parent.
if (__name__ == '__main__' and '--engine-jsonl' in sys.argv
        and not getattr(sys, 'frozen', False)):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

Ortho4XP_dir = '..' if getattr(sys, 'frozen', False) else '.'

sys.path.append(os.path.join(Ortho4XP_dir, 'src'))

# The frozen bundle carries two independent libproj copies (pyproj's wheel and
# GDAL's), each with its own proj.db: each must read the database it shipped
# with, and the user's PROJ_LIB/PROJ_DATA must not redirect either
# (docs/specs/proj-runtime-robustness-spec.md).  Runs before the first
# pyproj/osgeo import in this process; the src path above is what makes
# O4_Proj_Runtime importable here (frozen bundles carry the src modules).
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    import O4_Proj_Runtime
    O4_Proj_Runtime.pin_frozen_proj(sys._MEIPASS)
    _lib_path = os.path.join(sys._MEIPASS, "_internal")
    os.environ["DYLD_LIBRARY_PATH"] = _lib_path + ":" + os.environ.get("DYLD_LIBRARY_PATH", "")

# PROJ self-check as a CLI: exits 0 healthy / 1 broken, ahead of every heavy
# import so a broken bundle is diagnosable without loading the pipeline.
if __name__ == '__main__' and '--proj-selfcheck' in sys.argv:
    import O4_Proj_Runtime
    _proj_error = O4_Proj_Runtime.preflight()
    print(_proj_error if _proj_error else "PROJ selfcheck OK")
    sys.exit(1 if _proj_error else 0)

# One self-check per top-level process: multiprocessing helpers re-import this
# module as "__mp_main__" and --engine-worker children skip it — neither runs
# the gated pipeline-step entries, which execute only in the top-level process.
# A failure does not stop the process (browsing and the protocol still work) —
# the pipeline steps refuse via refuse_reason().
if __name__ == '__main__' and '--engine-worker' not in sys.argv:
    import O4_Proj_Runtime
    _proj_error = O4_Proj_Runtime.preflight()
    if _proj_error:
        print("ERROR: PROJ runtime self-check failed", file=sys.stderr)
        print(_proj_error, file=sys.stderr)

# JSON-lines engine transport (docs/specs/engine-protocol-multi-gui.md §5):
# a subprocess front end runs `Ortho4XP.py --engine-jsonl` and speaks the
# protocol over stdio.  Handle it here, BEFORE the core imports below, so
# the engine-only path pulls in no more than the transport needs.  (It also
# predates the retirement of the Tkinter GUI on 2026-07-26: until then a GUI
# toolkit was imported below and this dispatch had to dodge it.)  The __name__
# guard is LOAD-BEARING: multiprocessing spawn helpers (the auto-patch
# airport pool and its Manager) re-import this module as "__mp_main__"
# with the parent's argv restored — without the guard the helper becomes
# a second engine server blocked on its pipe, the Manager handshake
# never completes, and the build wedges at zero CPU (live 3-tile run,
# 2026-07-17).
if __name__ == '__main__' and '--engine-jsonl' in sys.argv:
    from o4_engine import jsonl
    if '--engine-worker' not in sys.argv:
        # Application-process engine session (a front end such as the
        # mac app drives it over the protocol): start the OSM extract
        # maintenance thread here, exactly as the Qt window does at
        # startup. Parallel-build worker children are spawned with
        # --engine-worker and must never run it (they only append
        # wants) — without this call the region index never downloads
        # and every build silently falls back to Overpass.
        try:
            import O4_OSM_Extracts as EXTRACTS
            EXTRACTS.start_background_maintenance()
        except Exception:
            pass
    # owns_process: the transport bounds this process's life — front-end
    # death (stdin EOF, SIGTERM, ppid change) stops any in-flight build
    # and exits, so no orphan engine can keep building headless.
    jsonl.serve(sys.stdin, sys.stdout, owns_process=True)
    sys.exit(0)

import O4_File_Names as FNAMES
sys.path.append(FNAMES.Provider_dir)
import O4_Imagery_Utils as IMG
import O4_Vector_Map as VMAP
import O4_Mesh_Utils as MESH
import O4_Mask_Utils as MASK
import O4_Tile_Utils as TILE
import O4_Config_Utils as CFG  # CFG imported last because it can modify other modules variables

cmd_line = "USAGE: Ortho4XP.py lat lon imagery zl (won't read a tile config)\n  OR:  Ortho4XP.py lat lon (with existing tile config file)"

# A bare invocation used to launch the Tkinter GUI from here; that GUI was
# retired 2026-07-26 (owner ruling) and this file is engine + CLI only, so
# with no arguments there is nothing to do but point at each entry point.
usage = (
    "Ortho4XP.py is the engine and command line entry point; the graphical\n"
    "interface is Ortho4XP_Qt.py (started by ./start_mac.sh on macOS or\n"
    "start_windows.bat on Windows).\n"
    "\n"
    "USAGE: Ortho4XP_Qt.py                  graphical interface\n"
    "  OR:  Ortho4XP.py lat lon imagery zl  build a tile (won't read a tile config)\n"
    "  OR:  Ortho4XP.py lat lon             build a tile (with existing tile config file)\n"
    "  OR:  Ortho4XP.py --engine-jsonl      JSON-lines engine transport over stdin/stdout,\n"
    "                                       spoken by front ends such as the mac app\n"
    "                                       (docs/specs/engine-protocol-multi-gui.md)"
)

if __name__ == '__main__':
    if len(sys.argv) == 1:  # no GUI here anymore, and nothing to build
        print(usage)
        sys.exit(0)
    if not os.path.isdir(FNAMES.Utils_dir):
        print("Missing ", FNAMES.Utils_dir, "directory, check your install. Exiting.")
        sys.exit()
    for directory in (FNAMES.Preview_dir, FNAMES.Provider_dir, FNAMES.Extent_dir, FNAMES.Filter_dir, FNAMES.OSM_dir,
                      FNAMES.Mask_dir, FNAMES.Imagery_dir, FNAMES.Elevation_dir, FNAMES.Geotiff_dir, FNAMES.Patch_dir,
                      FNAMES.Tile_dir, FNAMES.Tmp_dir):
        if not os.path.isdir(directory):
            try:
                os.makedirs(directory)
                print("Creating missing directory", directory)
            except:
                print("Could not create required directory", directory, ". Exit.")
                sys.exit()
    IMG.initialize_extents_dict()
    IMG.initialize_color_filters_dict()
    IMG.initialize_providers_dict()
    IMG.initialize_combined_providers_dict()
    # sequel is only concerned with command line
    if len(sys.argv) < 3:
        print(cmd_line); sys.exit()
    try:
        lat = int(sys.argv[1])
        lon = int(sys.argv[2])
    except:
        print(cmd_line); sys.exit()
    if len(sys.argv) == 3:
        try:
            tile = CFG.Tile(lat, lon, '')
        except Exception as e:
            print(e)
            print("ERROR: could not read tile config file."); sys.exit()
    else:
        try:
            provider_code = sys.argv[3]
            zoomlevel = int(sys.argv[4])
            tile = CFG.Tile(lat, lon, '')
            tile.default_website = provider_code
            tile.default_zl = zoomlevel
        except:
            print(cmd_line); sys.exit()
    try:
        VMAP.build_poly_file(tile)
        MESH.build_mesh(tile)
        MASK.build_masks(tile)
        TILE.build_tile(tile)
        print("Bon vol!")
    except:
        print("Crash!")