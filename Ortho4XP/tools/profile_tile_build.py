"""Wall-clock sampling profiler for a whole tile build (steps 1-4:
vector, mesh, masks, imagery/DSF).

Companion to ``tools/profile_airport_build.py`` (which profiles the
auto_patch pipeline only).  Runs the same initialisation as
``tools/run_tile_build.py`` — provider dictionaries, per-tile config —
then executes the four build steps while a background thread samples
EVERY Python thread's stack through ``sys._current_frames()`` each
``--interval`` seconds (default 0.05 s).  Because it samples wall time,
step totals match the production ``~/.ortho4xp/tile_build_times``
numbers; parallel stages (imagery download and convert workers, the
DSF writer thread, the vector-step OSM prefetch thread) report
THREAD-seconds, which can exceed wall seconds.

Time spent inside external binaries (Triangle4XP, the mesh sorter)
appears as the main thread blocked reading the subprocess pipe — it is
reported under that call site, not lost.

Report sections, written to ``--out``
(default /tmp/tile_<short_latlon>_profile.txt):
  1. Exact wall seconds per step (timed around each step call).
  2. Per step: top functions by inclusive and by leaf (self-time)
     thread-seconds, main thread and worker threads listed separately.

WHAT IT REFUSES: a tile build with NO CIFP.  ``run_auto_patch_generation``
only calls the generator when it can resolve a CIFP directory, and the dev
tree and every lane worktree ship ``cifp_data_path`` EMPTY — so a profile
run here produced a tile with NO auto_patch surfaces at all, exited 0, and
was profiled as if it were a release tile (the P1 caveat).  The refusal is
``tools/harness/build_airport.py``'s own
:func:`~build_airport.apply_xplane_install_paths`, IMPORTED, not copied:
it loads the owner's three X-Plane install paths into the live
``O4_Config_Utils`` globals and aborts before any work if neither a CIFP
directory nor a Custom Scenery directory resolves.  A second, slightly
different copy of a harness refusal is the census-wrapper defect (root
CLAUDE.md).

IT ARMS THE SHARED-REPO WRITE GUARD, like every other build entry
(``tools/harness/shared_repo_guard.py``, the single implementation).  It
did NOT until 2026-08-13 (perf P3 lane T), which was a real hole and not
a documentation slip: this profiler runs the SAME four steps as
``harness/build_airport.py --tile``, including the auto_patch driver's
ProcessPool — the exact writer that put eight
``Airport_mod_cache/*/o4_object_footprints_*`` sidecars into the shared
corpus from ``run_tile_mesh_only.py`` on 2026-08-12 with
``guard.blocked`` EMPTY.  Both halves are armed here for the same reason
they are armed there: ``redirect_engine_caches`` at module scope (BEFORE
the engine import — ``O4_File_Names`` computes its cache dirs at import,
and subprocesses inherit only the environment), then the guard, the
before/after snapshot audit, the bathymetry-prefetch join, and the
swallowed-refusal detector.  A profile taken on a corpus the profile
itself changed measures a frame no other lane can be compared with.

``--count MODULE:ATTR`` (repeatable) wraps a named callable with a call
counter and an INCLUSIVE ``perf_counter`` timer, exactly as
``tools/profile_airport_build.py`` does — the counter class is IMPORTED
from it, never re-spelled.  ``ATTR`` may be dotted
(``O4_Vector_Utils:Vector_Map.insert_edge``) to reach a method.  This is
the only number a claim may quote: the sampler over-attributes inside
GIL-heavy loops, and on this tile's vector step it roughly DOUBLES the
step (measured, lane T) — pass ``--no-sample`` for a measurement run and
keep the sampler for distribution reads.

This profiler measures wall time, so it is never run through the run
ledger; the refusal is the only harness law it needs.

Usage:
    venv/bin/python tools/profile_tile_build.py <lat> <lon>
        [--build-dir DIR] [--provider CODE] [--zl N]
        [--steps vector,mesh,masks,imagery] [--interval 0.05]
        [--count MODULE:ATTR ...] [--no-sample] [--out PATH]
"""

import argparse
import collections
import os
import sys
import threading
import time

os.environ.setdefault("O4_LOG_VERBOSITY", "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

# THE EMPTY-CIFP REFUSAL, imported from THE build entry (one
# implementation — see the module docstring).  Importing build_airport
# pulls in no engine module; ``apply_xplane_install_paths`` imports
# ``O4_Config_Utils`` itself, at call time.
_HARNESS_DIR = os.path.join(ROOT, "tools", "harness")
if _HARNESS_DIR not in sys.path:
    sys.path.insert(0, _HARNESS_DIR)
from build_airport import (apply_xplane_install_paths,  # noqa: E402
                           provision_tile_cfg,
                           redirect_engine_caches)

# THE REDIRECT MUST PRECEDE THE ENGINE IMPORT (run_tile_mesh_only.py's
# header carries the measurement).  The engine modules are imported inside
# main(), so module scope is early enough — and it must not be later:
# O4_File_Names computes Default_dsf_cache_dir AT IMPORT, and the
# auto_patch driver's pool workers inherit only the environment.
_CACHE_REDIRECTS = redirect_engine_caches(
    os.path.join(os.getcwd(), "tmp", "profile_tile_build"), "tile_profile")

from shared_repo_guard import (SharedRepoWriteGuard,  # noqa: E402
                               shared_repo_snapshot, snapshot_diff,
                               report_unauthorised_writes,
                               require_no_swallowed_write_block,
                               require_no_unauthorised_writes)
# The call counter, IMPORTED from the airport profiler — one
# implementation of "--count MODULE:ATTR" for both profilers.
_TOOLS_DIR = os.path.join(ROOT, "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
from profile_airport_build import (census_report_lines,  # noqa: E402
                                   install_census_counters)

STEP_ORDER = ("vector", "mesh", "masks", "imagery")


def _short_path(filename):
    if filename.startswith(ROOT):
        return os.path.relpath(filename, ROOT)
    marker = os.sep + "site-packages" + os.sep
    if marker in filename:
        return "site-packages/" + filename.split(marker, 1)[1]
    return filename


class AllThreadSampler(threading.Thread):
    """Samples every live Python thread's stack until ``stop()``.

    Counters are keyed by (step, role, function) where role is "main"
    or "worker"; one count = one thread observed there for one sample
    tick, so counts convert to THREAD-seconds via the per-sample
    duration.
    """

    def __init__(self, main_thread_id, current_step, interval):
        super().__init__(daemon=True)
        self.main_thread_id = main_thread_id
        self.current_step = current_step  # one-element mutable list
        self.interval = interval
        self.ticks = 0
        self.inclusive = collections.Counter()  # (step, role, fn) -> n
        self.leaf = collections.Counter()       # (step, role, site) -> n
        self.thread_ticks = collections.Counter()  # (step, role) -> n
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        own_id = threading.get_ident()
        while not self._stop_event.is_set():
            step = self.current_step[0]
            if step is not None:
                for thread_id, frame in sys._current_frames().items():
                    if thread_id == own_id:
                        continue
                    role = ("main" if thread_id == self.main_thread_id
                            else "worker")
                    self._record(step, role, frame)
                self.ticks += 1
            time.sleep(self.interval)

    def _record(self, step, role, frame):
        self.thread_ticks[(step, role)] += 1
        seen = set()
        leaf_site = None
        depth = 0
        while frame is not None and depth < 200:
            code = frame.f_code
            short = _short_path(code.co_filename)
            key = f"{short}:{code.co_name}"
            if leaf_site is None:
                leaf_site = f"{short}:{frame.f_lineno} {code.co_name}"
            if key not in seen:
                seen.add(key)
                self.inclusive[(step, role, key)] += 1
            frame = frame.f_back
            depth += 1
        if leaf_site is not None:
            self.leaf[(step, role, leaf_site)] += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lat", type=int)
    parser.add_argument("lon", type=int)
    parser.add_argument("--build-dir", default="",
                        help="custom build directory (as in run_tile_build; "
                             "the tile's own zOrtho4XP_... dir is normalized "
                             "to its parent so neighbor lookups keep working)")
    parser.add_argument("--provider", default="",
                        help="override default_website (else tile config)")
    parser.add_argument("--zl", type=int, default=0,
                        help="override default_zl (else tile config)")
    parser.add_argument("--steps", default="vector,mesh,masks,imagery",
                        help="comma list, subset of vector,mesh,masks,imagery")
    parser.add_argument("--interval", type=float, default=0.05)
    parser.add_argument("--count", action="append", default=[],
                        metavar="MODULE:ATTR",
                        help="call count + INCLUSIVE perf_counter seconds "
                             "for this callable (repeatable; ATTR may be "
                             "dotted to reach a method).  THE number a "
                             "claim quotes — the sampler over-attributes.")
    parser.add_argument("--count-inputs", action="append", default=[],
                        metavar="MODULE:ATTR",
                        help="DUPLICATE-WORK CENSUS on this callable: calls, "
                             "DISTINCT input fingerprints, duplicate calls "
                             "and their seconds (inputs priced BY VALUE; an "
                             "input with no value rule makes the call "
                             "UNFINGERPRINTABLE — counted, never guessed).  "
                             "Repeatable")
    parser.add_argument("--count-inputs-identity", action="append", default=[],
                        metavar="MODULE:ATTR",
                        help="the same census with a type:id() fallback for "
                             "objects with no value rule; those duplicates "
                             "are reported in their OWN column and mean only "
                             "'the same object again'.  Repeatable")
    parser.add_argument("--count-clock", choices=("wall", "cpu"), default="wall",
                        help="counters' clock: wall = time.perf_counter "
                             "(default); cpu = time.process_time (use when "
                             "other lanes hold the machine)")
    parser.add_argument("--no-sample", action="store_true",
                        help="do not run the stack sampler.  The sampler "
                             "roughly DOUBLES this tile's vector step "
                             "(pure-Python hot loop, measured lane T "
                             "2026-08-13), so a --count measurement run "
                             "must not carry it.")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    unknown = [s for s in steps if s not in STEP_ORDER]
    if unknown:
        raise SystemExit(f"unknown steps: {unknown}")

    import O4_File_Names as FNAMES
    import O4_UI_Utils as UI  # noqa: F401  (imported for side effects)

    sys.path.append(FNAMES.Provider_dir)
    import O4_Imagery_Utils as IMG
    import O4_Vector_Map as VMAP
    import O4_Mesh_Utils as MESH
    import O4_Mask_Utils as MASK
    import O4_Tile_Utils as TILE
    import O4_Config_Utils as CFG
    import O4_Bathymetry_Band as BATHYBAND

    # Installed before ``step_fn`` binds anything: a counter on a step
    # function itself must be the object the loop calls.
    _clock = time.process_time if args.count_clock == "cpu" else time.perf_counter
    counters = install_census_counters(
        count=args.count, count_inputs=args.count_inputs,
        count_inputs_identity=args.count_inputs_identity, clock=_clock)

    out_path = args.out or "/tmp/tile_%s_profile.txt" % FNAMES.short_latlon(
        args.lat, args.lon)

    IMG.initialize_extents_dict()
    IMG.initialize_color_filters_dict()
    IMG.initialize_providers_dict()
    IMG.initialize_combined_providers_dict()

    # Before ANY step: the owner's X-Plane install paths, or the refusal.
    # Same call, same order as harness/build_airport.py's build_tile —
    # without it the profiled tile silently carries no auto_patch surfaces.
    xplane_paths = apply_xplane_install_paths()
    print("X-Plane install paths applied:", sorted(xplane_paths))

    tile = CFG.Tile(
        args.lat, args.lon,
        FNAMES.normalize_custom_build_dir(args.lat, args.lon,
                                          args.build_dir),
    )
    # LANE INPUTS ARE PROVISIONED, NEVER HAND-SEEDED (owner ruling
    # 2026-08-12b), and the destination is the TILE'S OWN ``build_dir``,
    # not the ``--build-dir`` argument: with no argument the argument is
    # empty and the tile derives its own path, so provisioning against
    # the argument writes the cfg into the CWD and the run still dies on
    # 'EMPTY default_website'.  Without this a fresh lane worktree has no
    # per-tile cfg at all, ``read_from_config`` falls back to the global
    # config, and a synthesized default would be worse — a tile profiled
    # at a provider and ZL nobody chose, exiting 0.  Same function, same
    # byte copy, same canonical source as ``build_airport.py --tile``; a
    # second copy of that rule here would be the census-wrapper defect.
    _cfg_record = provision_tile_cfg(args.lat, args.lon, tile.build_dir)
    tile.read_from_config()
    if args.provider:
        tile.default_website = args.provider
    if args.zl:
        tile.default_zl = args.zl
    print("build directory:", tile.build_dir)
    print("default_website:", tile.default_website,
          "default_zl:", tile.default_zl)
    if not tile.default_website:
        raise SystemExit("empty default_website — pass --provider")

    step_fn = {
        "vector": VMAP.build_poly_file,
        "mesh": MESH.build_mesh,
        "masks": MASK.build_masks,
        "imagery": TILE.build_tile,
    }

    current_step = [None]
    sampler = AllThreadSampler(
        threading.get_ident(), current_step, args.interval)
    if not args.no_sample:
        sampler.start()

    print("engine cache redirects:", _CACHE_REDIRECTS)
    # Nothing is authorised: this entry has no --refresh-data of its own.
    before = shared_repo_snapshot()
    guard = SharedRepoWriteGuard(set(), os.getcwd())

    step_wall = {}
    t_run = time.time()
    try:
        with guard:
            for step in STEP_ORDER:
                if step not in steps:
                    continue
                print(f"=== step {step} ===", flush=True)
                current_step[0] = step
                t0 = time.time()
                result = step_fn[step](tile)
                step_wall[step] = time.time() - t0
                current_step[0] = None
                print(f"=== step {step} done in {step_wall[step]:.1f} s "
                      f"(result {result}) ===", flush=True)
                if result == 0:
                    print("step failed — stopping here")
                    break
            # The band prefetch starts inside step 1 and is joined by the
            # masks step; a vector-only profile never reaches it, and the
            # thread would otherwise write the corpus after the guard came
            # down (measured 2026-08-08, the S13W078 band index.json).
            BATHYBAND.join_prefetches()
    finally:
        # The audit runs even when a step raised: a run that died halfway
        # has still changed the corpus every other lane reads.
        changes = snapshot_diff(before, shared_repo_snapshot())
        offenders = report_unauthorised_writes(changes, set(), None)
    # The two detectors fire at the END of main(), AFTER the report is on
    # disk: a profile that refuses before writing its report throws away
    # the measurement it just paid minutes for, and the refusal is about
    # the CORPUS, not about the numbers.
    total_wall = time.time() - t_run
    if sampler.is_alive():
        sampler.stop()
        sampler.join(timeout=2.0)

    # One sampler tick observed every live thread once; convert counts to
    # thread-seconds through the measured tick duration.
    per_tick = total_wall / max(sampler.ticks, 1)

    def secs(n):
        return n * per_tick

    lines = [
        "tile %s build profile: %.1f s wall, %d sample ticks "
        "(%.1f ms/tick)" % (
            FNAMES.short_latlon(args.lat, args.lon), total_wall,
            sampler.ticks, per_tick * 1000.0),
        "provider %s ZL%s, build dir %s" % (
            tile.default_website, tile.default_zl, tile.build_dir),
        # The auto_patch frame this profile was taken in — a report that
        # does not say which install paths resolved cannot be told apart
        # from one taken on an auto_patch-less tile.
        "X-Plane install paths: %s" % (
            ", ".join("%s=%s" % kv for kv in sorted(xplane_paths.items()))
            or "(none)"),
        # WHICH per-tile cfg this profile read, and where it came from —
        # two runs on two cfg sources are two populations.
        "tile cfg: %s (%s, sha256 %s)" % (
            _cfg_record.get("cfg"), _cfg_record.get("action"),
            (_cfg_record.get("sha256") or "-")[:12]),
        "",
        "== Wall seconds per step (exact) ==",
    ]
    for step in STEP_ORDER:
        if step in step_wall:
            lines.append("  %8.1f s  %s" % (step_wall[step], step))

    if counters:
        lines.append("")
        lines.append("   (sampler %s — these are THE quotable numbers)"
                     % ("OFF" if args.no_sample else "ON, so they carry its "
                        "overhead"))
        # ONE report block for both profilers — imported, never re-spelled.
        lines.extend(census_report_lines(counters))

    for step in STEP_ORDER:
        if step not in step_wall:
            continue
        for role in ("main", "worker"):
            ticks = sampler.thread_ticks.get((step, role), 0)
            if not ticks:
                continue
            lines.append("")
            lines.append("== %s / %s threads: %.1f thread-seconds ==" % (
                step, role, secs(ticks)))
            lines.append("  -- top 30 inclusive --")
            rows = [(n, key) for (s, r, key), n in sampler.inclusive.items()
                    if s == step and r == role]
            for n, key in sorted(rows, reverse=True)[:30]:
                if secs(n) < 1.0:
                    break
                lines.append("  %8.1f s  %s" % (secs(n), key))
            lines.append("  -- top 20 leaf (self-time) --")
            rows = [(n, site) for (s, r, site), n in sampler.leaf.items()
                    if s == step and r == role]
            for n, site in sorted(rows, reverse=True)[:20]:
                if secs(n) < 1.0:
                    break
                lines.append("  %8.1f s  %s" % (secs(n), site))

    report = "\n".join(lines) + "\n"
    with open(out_path, "w") as handle:
        handle.write(report)
    print(report)
    print("report written to", out_path)

    require_no_swallowed_write_block(guard.blocked)
    require_no_unauthorised_writes(offenders, entry="tile profile")


if __name__ == "__main__":
    main()
