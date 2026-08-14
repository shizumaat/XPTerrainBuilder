"""THE BUILD ENTRY — the one way to build an airport or a tile for measurement.

    venv/bin/python tools/harness/build_airport.py ICAO [--tag NAME]
        [--patch-only | --tile LAT LON] [--out DIR] [--dem CONST_M]
        [--allow-degraded-dem] [--allow-no-sidecar] [--no-ledger]
        [--refresh-data SCOPE[,SCOPE...]] [--break-stale-lock]
        [--allow-private-data] [--base-arm | --from-ledger]
        [--no-artifact-ledger]

Run it from ``Ortho4XP/`` (or a lane worktree set up with
``tools/harness/lane_worktree.sh``).  Every lane builds through THIS entry;
a lane-private build wrapper is a defect (see CLAUDE.md, "The standard test
harness").

WHAT IT REFUSES, LOUDLY — each of these has silently degraded a real
measurement in this repo, and every one of them exits 0 without the check:

1. **Wrong cwd.**  ``auto_patch`` builds only run correctly from a
   directory holding ``venv/`` AND ``OSM_data/``.  Elsewhere the build
   exits 0 with a silently SMALLER layout: a fake speedup and a fake
   defect drop at once.
2. **A cold DEM frame.**  The standalone airport path runs production's own
   DEM prep (``elevation._load_airport_dem`` →
   ``O4_Vector_Map.compose_tile_dem_from_disk``), but it DEGRADES to the
   base surface — no airport smoothing, no elevation insets — with only a
   log line when the caches are cold.  Warm-vs-cold has moved measured
   terrain 12 m.  The harness turns that log line into a refusal.
3. **A drifted config frame.**  The DEM/inset surface is shaped by cfg keys
   (``apt_smoothing_pix``, ``airport_elevation_*``, ``elevation_level``,
   ``custom_dem``, ``working_grid_arc_seconds``).  Production runs the
   owner's app config; a dev tree runs its own.  Every key that shapes the
   surface is compared against the owner's config and a divergence is
   refused by name — so a lane's per-airport patch is measured in the same
   frame the shipped tile is built in.  (This closes the inset-coverage
   frame gap ``tools/full_airport_build.py`` carried unstated.)
3b. **A hand-seeded lane input.**  A fresh lane build dir has no per-tile
   ``Ortho4XP_+XX+YYY.cfg``; ``Tile.read_from_config`` then falls back to the
   GLOBAL config, which carries no ``default_website`` at all, and the build
   refuses at the provider check.  Two lanes improvised two DIFFERENT cfg
   sources to get past that on 2026-08-12 — the census-wrapper defect at one
   remove.  ``--tile`` now PROVISIONS it: a byte copy from the ritual's own
   canonical source (``<main engine tree>/Tiles/zOrtho4XP_+XX+YYY/``, where
   ``lane_worktree.sh`` clones ``Ortho4XP.cfg`` and ``Patches/`` from),
   recorded with its sha256 in ``<tag>.frame.json`` under
   ``tile_cfg_provenance``.  An existing lane cfg is never overwritten.  A
   MISSING canonical source no longer refuses: it DERIVES the per-tile cfg
   from the canonical GLOBAL ``Ortho4XP.cfg`` — a file with zero override
   lines, which is what "the global defaults" IS in the engine's own reader
   — recorded as ``derived-from-global-defaults`` with the global source's
   sha256 and printed loudly (owner ruling 2026-08-14, a tile without a
   per-tile cfg uses global defaults; 2026-08-12b's substance kept: one
   canonical source, ritual-provisioned, never hand-seeded, recorded).
   Nothing is SYNTHESIZED either way — a made-up provider and ZL build a
   tile nobody asked for and exit 0, so where the globals have nothing to
   give (``default_website`` is excluded from the global config by
   construction) the provider check below still refuses, naming the
   derivation.
4. **A tile build with no CIFP.**  ``run_auto_patch_generation`` only calls
   the generator when it can resolve a CIFP directory; the dev config
   ships ``cifp_data_path`` EMPTY, so a whole-tile build there produces a
   tile with NO auto_patch surfaces at all and still exits 0.  ``--tile``
   loads the three X-Plane install paths from the owner's app config and
   aborts before any work if none resolve.
5. **A patch with no sidecar.**  ``O4_LOG_VERBOSITY=1`` is set here, because
   ``layout._write_axes_sidecar`` is gated on it — and without the sidecar
   every census silently falls back to the context-free frame.  The writer
   also builds its whole dict inside ONE bare ``except Exception: pass``, so
   a single failing contributor discards the entire sidecar in silence:
   when that happens, ``diagnose_missing_sidecar`` calls each contributor
   separately, un-swallowed, and the refusal names the culprit and its
   traceback.  It diagnoses and never repairs — a harness that patched the
   emitter would be inventing the frame it exists to measure.

6. **A PRIVATE data corpus.**  Owner ruling e9daef5 makes ONE shared data
   repo mandatory (``/Users/noah/XPTerrainBuilderData``): every lane mounts
   it, no lane keeps a private cache.  Two lanes on two corpora do not
   measure the same thing, and nothing in a build log says which corpus
   was used.  Every data dir is resolved and recorded; a private one is
   refused (``--allow-private-data`` proceeds knowingly).
7. **An implicit download or cache regeneration.**  A build must NEVER
   mutate the shared repo as a side effect — the KCLT road-feed refresh
   that ran inside a tile build on 2026-08-05 01:47-01:55 and silently
   changed campaign hashes is the named precedent.  Two mechanisms:

   * BEFORE the build, every artifact this run needs and the repo lacks is
     named and refused, with the exact ``--refresh-data`` scope that would
     fetch it deliberately;
   * AFTER the build, a FULL before/after snapshot of the shared repo's
     data dirs (~2.7 k files, ~10 ms) reports every path the build wrote.
     Writes inside an authorised scope are hash-stamped into the shared
     ledger; writes outside one are reported as a ruling violation and the
     run is marked CONTAMINATED, because the corpus changed under it.

   ``--refresh-data SCOPE`` is the explicit override: it takes a per-scope
   LOCK in the shared repo (refuse-and-report on contention, never a
   silent block, never a race), performs the refresh exactly once, and
   appends a hash-stamped record to
   ``<data repo>/.harness/refresh_ledger.jsonl``.

   The guard's own LOCK-FILE allowance is in :func:`is_lock_artifact`: a
   ``.lock`` sibling is cross-process COORDINATION STATE, never corpus
   data, and only the two calls the engine's lock primitive makes on one
   (exclusive create, removal) pass.  Its LIBRARY-INDEX allowance is in
   :func:`is_library_index_artifact`: the ``Airport_mod_cache`` sidecar is
   DERIVED CACHE, a byte-deterministic function of the X-Plane install,
   and the process that rewrites it after the install changes is often
   not the build the snapshot attributes it to.
8. **A DEGRADED BUILD THE ENGINE SWALLOWED.**  A refusal the build catches
   is not a refusal.  ``auto_patch.elevation._load_airport_dem`` runs
   production's whole DEM prep inside ONE ``except Exception``, so a write
   the guard blocked (item 7) becomes a WARN line, ``dem_inset_provenance``
   comes back ``None`` — no DEM object at all — and the build exits 0 on a
   silently smaller layout (measured 2026-08-07 at HECA: 18.5 k nodes
   against production's 34-36 k, with ``retaining_wall`` / ``ols_cut`` /
   ``crown_spine`` / ``gap_interior_ring`` entirely absent).  Two
   independent detectors close it, and either one refuses: any write the
   guard blocked during a build that nevertheless returned, and a build
   whose layout carries NO DEM provenance.  ``--allow-degraded-dem``
   proceeds knowingly and records it — it authorises no write.

THE SYNTHETIC WORLDS (``--dem CONST_M``).  ``--dem`` substitutes an
``auto_patch.constant_dem.ConstantDEM`` for the tile surface — the same
seam Ortho4XP's own ``tile.dem`` uses.  It is a DEM SOURCE substitution and
never a law gate: no rule changes, only which surface answers ``alt()``.
The ruled pair is ``--dem -500`` (low: everything seats at its band FLOOR)
and ``--dem 10000`` (high: everything seats at its CEILING); NEGATIVES ARE
LEGAL AND RULED (RULINGS 2026-08-06, "The low extreme is −500 m" — below
every CIFP value, so floor-seating is guaranteed and below-sea-level
handling is exercised for free).  The loader's all-zero refusal is
untouched by this and is never reached: it guards the DISK-COMPOSE branch,
where zero means the base raster is ABSENT, while a synthetic DEM arrives
as ``override_dem`` and is returned before it.  The world is recorded in
``<tag>.result.json`` and ``<tag>.frame.json`` under ``synthetic_dem`` —
a census row from a −500 m world is not comparable with a real-DEM one,
so which world it was must be IN the artifact.

WHAT IT RECORDS, always, next to the patch:

* ``<tag>.env.json`` — the environment snapshot: every ``O4_*`` variable,
  cwd, git HEAD + dirty flag, the ledger's code-tree hash, the X-Plane
  root, and the cfg-frame comparison.
* ``<tag>.frame.json`` — the DEM/inset cache state BEFORE the build and the
  layout's own ``dem_inset_provenance`` AFTER it; the resolved DATA MOUNTS
  (which corpus every data dir actually came from); and the shared-repo
  write audit.  Quote no elevation without it.
* ``<tag>.progress`` — START / step / EXIT stamps (the ``.progress``
  convention) so a lead can audit liveness without touching the run.
* ``engine_cache_redirects`` (in ``<tag>.result.json`` and
  ``<tag>.frame.json``) — every build re-points the engine's two WRITABLE
  derived-cache roots lane-local, under the LANE-PERSISTENT
  ``<lane>/tmp/engine_caches/`` (:func:`lane_cache_root`; the masks
  overlay stays per-run under ``<out>/<tag>.engine_caches/``):
  the DSFTool dump cache (``O4_DSF_CACHE_DIR``) and the per-pack
  ``Airport_mod_cache`` root (``O4_AIRPORT_MOD_CACHE_DIR``, a
  COPY-ON-WRITE read-through overlay: APFS ``clonefile`` seeding, so a
  writer that truncates a cache in place cannot reach the shared file —
  symlink seeding let exactly that through, measured three times on
  2026-08-12).  It is the pytest suite's own
  mechanism, and it closes the hole item 7's guard cannot see: the DSFTool
  SUBPROCESS writes its dump itself (measured KCLT 2026-08-11,
  ``Airport_mod_cache/zOrtho4XP_+35-081/+35-081.dsf.8828b7db.text``, run
  flagged CONTAMINATED).  A scope this run is AUTHORISED to refresh
  (``--refresh-data airport_mod_cache`` / ``dsf_cache``) is deliberately
  NOT redirected — an authorised refresh must land in the shared repo.
* the patch body sha256 (``tail -n +3``: the provenance stamp makes the raw
  file hash useless for A/B identity).

THE BASE-ARM ARTIFACT LEDGER (``--base-arm`` / ``--from-ledger``, 2026-08-12,
spec ``docs/specs/blast-sweep-and-artifact-ledger-spec.md`` BS2).  The run
ledger remembers whether a build PASSED; it forgets what it PRODUCED, so
base arms at identical trees were rebuilt 2-4x across lanes this session at
7-10 min each.  Every successful patch build now also STORES its patch,
sidecar, frame, env and result in ``~/.ortho4xp/artifact_ledger`` (outside
the shared data repo, gitignored, size-capped LRU), content-addressed by
(code-tree hash, ICAO, the O4_* env the run ledger keys on, CORPUS STAMP,
build variant).  ``--base-arm`` asks for that artifact instead of a build:
on a hit it is copied in byte-identically behind a loud provenance line
naming the original build, its timestamp and its duration; on a miss the
line NAMES the component that moved.  A corpus-stamp mismatch is always a
miss — a changed corpus is a different measurement (the KCLT road-feed
precedent) — and the combination with ``--no-ledger`` (a timing run),
``--tile`` or ``--refresh-data`` is refused.  The store implementation is
``tools/harness/artifact_ledger.py``; a run that was authorised to refresh
or that the write audit flagged CONTAMINATED is never stored.

Consolidated from (and replacing): ``tools/full_airport_build.py``,
``scratchpad/integrate/build.sh``, ``scratchpad/refpull_interim/arm.sh``
and ``arm.py``, ``scratchpad/reltiles/run_release_tile.py`` and
``buildtile.sh``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# THE SHARED-REPO WRITE LAW lives in ONE module beside this one
# (``shared_repo_guard.py``, owner ruling e9daef5): the write guard, its
# lock-file and library-index allowances, the snapshot/diff audit, the
# swallowed-refusal detector, and the refresh scopes, locks and ledger.
# ``tools/run_tile_mesh_only.py`` arms the SAME implementation — a second
# copy of any of it is a defect (the census-wrapper precedent, root
# CLAUDE.md).  Re-exported here, unchanged, so every name this entry has
# always published (``build_mod.*`` in the twins, ``HB.*`` in oracle.py)
# stays published and IS the guard module's own object.
_HARNESS_DIR = str(Path(__file__).resolve().parent)
if _HARNESS_DIR not in sys.path:
    sys.path.insert(0, _HARNESS_DIR)
import artifact_ledger as AL                             # noqa: E402
from shared_repo_guard import (                          # noqa: E402,F401
    DATA_REPO, HARNESS_STATE, LOCK_DIR, REFRESH_LEDGER, SHARED_DATA_DIRS,
    REFRESH_SCOPES, scope_of, scope_description, shared_repo_snapshot,
    snapshot_diff, _file_stamp, RefreshLock, record_refresh,
    LOCK_ARTIFACT_SUFFIX, LOCK_FILE_OPS, is_lock_artifact,
    LIB_INDEX_ARTIFACT_RE, LIB_INDEX_FILE_OPS, is_library_index_artifact,
    SharedRepoWriteBlocked, SharedRepoWriteGuard,
    report_unauthorised_writes, _DEGRADED_OPTIONS,
    require_no_swallowed_write_block, mirror_tree_as_overlay,
)

#: The owner's production app config — the one the shipped app runs with.
#: It lives IN the shared data repo, which is the point: the config and the
#: corpus it describes travel together.
OWNER_APP_CFG = DATA_REPO / "Ortho4XP.cfg"

#: THE MAIN ENGINE TREE — where a lane's build INPUTS are cloned FROM.
#:
#: This is not a new hierarchy: it is the ritual's own
#: (``lane_worktree.sh``: ``MAIN_REPO="${O4_MAIN_REPO:-...}"``,
#: ``MAIN_ENGINE="$MAIN_REPO/Ortho4XP"``, ``CLONE_FILES="Ortho4XP.cfg"``),
#: spelled with the same environment override so one setting moves both.
#: The division of labour is deliberate and already law: the SHARED DATA
#: REPO holds the corpus and the owner's production app config
#: (:data:`OWNER_APP_CFG`, the FRAME every lane's cfg is validated
#: against); the MAIN TREE holds the build INPUTS a lane starts from
#: (``Ortho4XP.cfg``, ``Patches/``, and now the per-tile cfg).
MAIN_ENGINE_TREE = Path(os.environ.get(
    "O4_MAIN_REPO", "/Users/noah/XPTerrainBuilder")) / "Ortho4XP"

#: The X-Plane INSTALL paths a whole-tile build needs.
XPLANE_PATH_KEYS = ("cifp_data_path", "custom_scenery_dir",
                    "custom_overlay_src")

#: THE FRAME-SHAPING SUBSET of the install paths (fix cycle 2 item 4).
#:
#: These were commented "install-location settings, never law gates", and
#: that is exactly backwards.  They select WHICH apt.dat/CIFP corpus the
#: build reads, and the airport ELEVATION INSET is cut against the airport
#: FOOTPRINT MASK derived from that corpus — so two lanes pointed at
#: different scenery installs do not merely find their files in different
#: places, they grade against DIFFERENT INSET SURFACES.  That is the
#: definition of a DEM frame key, and it is the mechanism the re-baseline
#: identified.  ``custom_overlay_src`` stays out: overlays are consumed
#: after the patch and touch no inset.
XPLANE_FRAME_PATH_KEYS = ("cifp_data_path", "custom_scenery_dir")

#: Every cfg key that shapes the DEM/inset SURFACE a build grades against.
#: A divergence between the dev tree's config and the owner's app config
#: means the lane is measuring a surface production never renders.
DEM_FRAME_KEYS = (
    "elevation_level", "elevation_coastline_band_km", "base_elevation_source",
    "custom_dem", "fill_nodata", "working_grid_arc_seconds",
    "apt_smoothing_pix", "apt_smoothing_auto",
    "airport_elevation_insets", "airport_elevation_level",
    "airport_elevation_providers", "airport_elevation_inset_margin_m",
    "airport_elevation_inset_feather_m", "airport_inset_water",
) + XPLANE_FRAME_PATH_KEYS


# ══════════════════════════════════════════════════════════════════════
# REFUSALS
# ══════════════════════════════════════════════════════════════════════

def require_build_cwd(root) -> Path:
    """The build-cwd law.  Refuses rather than degrading."""
    root = Path(root)
    missing = [d for d in ("venv", "OSM_data") if not (root / d).is_dir()]
    if missing:
        raise SystemExit(
            f"REFUSING: build root {root} lacks {' and '.join(missing)}.  "
            f"An auto_patch build from here exits 0 with a silently SMALLER "
            f"layout (fake speedup, fake defect drop).  Run from Ortho4XP/ "
            f"in the main tree, or set the lane worktree up with "
            f"tools/harness/lane_worktree.sh (which symlinks both).")
    return root


def read_cfg(path) -> dict:
    """Flat ``key=value`` config reader (comments and blanks skipped)."""
    out: dict = {}
    p = Path(path)
    if not p.is_file():
        return out
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def effective_frame_value(key: str, ours: dict, theirs: dict):
    """The value that will ACTUALLY shape this build's surface for ``key``.

    For most frame keys that is simply the lane's own cfg value.  The two
    X-Plane install paths are different, and the difference is the whole
    reason adding them was not a one-line change:

        The dev tree and every lane worktree ship ``cifp_data_path`` and
        ``custom_scenery_dir`` EMPTY.  Empty does not mean "a different
        corpus" — it means UNSET, and the harness then supplies the
        owner's: ``build_tile`` copies them in through
        ``apply_xplane_install_paths``, and ``build_patch`` passes the
        resolved X-Plane root to ``build_airport_pavement`` directly.

    So an empty lane value is NOT a frame divergence, and refusing on it
    would refuse every lane build in the repo for a difference that does
    not exist at run time.  A NON-EMPTY value that disagrees with the
    owner's IS a divergence, and a serious one: it points the build at a
    different apt.dat/CIFP corpus, which cuts a different airport footprint
    mask, which bakes a DIFFERENT ELEVATION INSET.  That build grades a
    surface production never renders — silently, with no log line.
    """
    mine = ours.get(key)
    if key in XPLANE_FRAME_PATH_KEYS and not (mine or "").strip():
        return theirs.get(key)           # unset ⇒ the harness supplies it
    return mine


def cfg_frame_diff(root, owner_cfg=OWNER_APP_CFG) -> dict:
    """Compare the DEM-surface keys of this tree's config with the owner's.

    Returns ``{key: (ours, theirs)}`` for every key whose EFFECTIVE value
    (see :func:`effective_frame_value`) disagrees.  An absent owner config
    yields ``{}`` with ``owner_cfg_present`` False — a machine without the
    app installed cannot be held to it, and the env snapshot records that
    fact rather than pretending the frames matched.
    """
    ours = read_cfg(Path(root) / "Ortho4XP.cfg")
    theirs = read_cfg(owner_cfg)
    if not theirs:
        return {}
    out = {}
    for k in DEM_FRAME_KEYS:
        if k not in theirs:
            continue
        mine = effective_frame_value(k, ours, theirs)
        if mine != theirs.get(k):
            out[k] = (mine, theirs.get(k))
    return out


def frame_surface_keys(root, owner_cfg=OWNER_APP_CFG) -> dict:
    """The EFFECTIVE value of every DEM-frame key, for the frame record.

    Recorded whether or not it diverges: "which corpus cut the insets this
    build graded against" is a question later readers ask about numbers
    that are already in a report, and the answer has to be IN the artifact.
    """
    ours = read_cfg(Path(root) / "Ortho4XP.cfg")
    theirs = read_cfg(owner_cfg)
    return {k: effective_frame_value(k, ours, theirs) for k in DEM_FRAME_KEYS}


def require_cfg_frame(root, *, allow_degraded: bool = False,
                      owner_cfg=OWNER_APP_CFG) -> dict:
    diff = cfg_frame_diff(root, owner_cfg)
    if diff and not allow_degraded:
        lines = "\n  ".join(f"{k}: this tree={o!r}  production={t!r}"
                            for k, (o, t) in sorted(diff.items()))
        raise SystemExit(
            f"REFUSING: {len(diff)} DEM-frame config key(s) diverge from the "
            f"owner's production app config ({owner_cfg}):\n  {lines}\n"
            f"The surface this build grades against would not be the surface "
            f"the shipped tile is built on.  Align Ortho4XP.cfg, or pass "
            f"--allow-degraded-dem to measure in the divergent frame "
            f"KNOWINGLY (it is recorded in the env snapshot either way).")
    return diff


def _tile_stem(lat: int, lon: int) -> str:
    ns = "S" if lat < 0 else "N"
    ew = "W" if lon < 0 else "E"
    return f"{ns}{abs(int(lat)):02d}{ew}{abs(int(lon)):03d}"


def dem_cache_state(root, lat: int, lon: int) -> dict:
    """Filesystem-only report of the DEM/inset cache warmth for one tile.

    Pure path inspection: importable and testable without loading Ortho4XP,
    and it never triggers a network fetch (a fetch inside a measurement is
    itself a confound).
    """
    root = Path(root)
    stem = _tile_stem(lat, lon)
    elev = root / "Elevation_data"
    osm = root / "OSM_data"
    base = sorted(str(p.relative_to(root))
                  for p in elev.glob(f"*/{stem}*")
                  if p.is_file() and p.suffix.lower() in (".hgt", ".tif",
                                                          ".zip"))
    insets = sorted(str(p.relative_to(root))
                    for p in elev.glob(f"*/{stem}_airport_insets"))
    overlay = sorted(str(p.relative_to(root))
                     for p in elev.glob(f"*/{stem}_tile_overlay"))
    # OSM_data/<block>/<tile>/<tile>_airports.osm.bz2 — the cached airports
    # LAYER.  Without it the standalone DEM prep has no smoothing masks and
    # the surface stays unsmoothed (production smooths at apt_smoothing_pix).
    short = _short_latlon(lat, lon)
    airports = sorted(str(p.relative_to(root))
                      for p in osm.glob(f"*/{short}/{short}_airports*"))
    return {
        "tile": [int(lat), int(lon)],
        "tile_stem": stem,
        "base_raster": bool(base),
        "base_raster_files": base[:4],
        "airport_insets": bool(insets),
        "airport_inset_dirs": insets[:4],
        "tile_overlay": bool(overlay),
        "airports_layer": bool(airports),
        "airports_layer_files": airports[:4],
    }


def _short_latlon(lat: int, lon: int) -> str:
    return f"{int(lat):+03d}{int(lon):+04d}"


def require_dem_frame(state: dict, *, allow_degraded: bool = False) -> None:
    """The zero-DEM and cold-cache refusals.

    * NO base raster ⇒ the loader either downloads mid-measurement or hands
      back an ALL-ZERO surface; a whole build then "succeeds" while grading
      every shape toward a zero-elevation world (KCLT's end-around taxiway
      measured 85 m below the runway end before the mechanism was found).
    * NO cached airports layer ⇒ no smoothing masks, so the surface stays
      unsmoothed and diverges from production.
    * NO cached insets ⇒ the base surface only, when production insets here.
    """
    problems = []
    if not state["base_raster"]:
        problems.append(
            f"NO base raster for {state['tile_stem']} in Elevation_data — "
            f"the DEM loader would DOWNLOAD it mid-measurement (a "
            f"shared-repo write as a build side effect, which owner ruling "
            f"e9daef5 forbids) or hand back an ALL-ZERO surface.  "
            f"Deliberate fetch: --refresh-data dem")
    if not state["airports_layer"]:
        problems.append(
            f"NO cached airports OSM layer for tile "
            f"{state['tile'][0]:+d}{state['tile'][1]:+d} — airport smoothing "
            f"masks are unavailable and the surface stays UNSMOOTHED "
            f"(production smooths at apt_smoothing_pix=8), and the build "
            f"would run an overpass QUERY to fill it.  Deliberate fetch: "
            f"--refresh-data osm_layers")
    if not state["airport_insets"]:
        problems.append(
            f"NO cached airport elevation insets for {state['tile_stem']} — "
            f"the build would grade against the BASE surface while "
            f"production grades against the inset-baked one.  Deliberate "
            f"fetch: --refresh-data dem  (or "
            f"tools/fetch_airport_elevation_insets.py, which writes the "
            f"same shared cache).")
    if problems and not allow_degraded:
        raise SystemExit(
            "REFUSING: the DEM frame is COLD, and a cold frame degrades "
            "SILENTLY (log line only) into a different surface:\n  - "
            + "\n  - ".join(problems)
            + "\nWarm the cache, or pass --allow-degraded-dem to measure in "
              "the degraded frame KNOWINGLY (it is recorded either way).  "
              "Never quote a DEM elevation from a degraded frame.")
    for p in problems:
        print(f"  [harness] DEGRADED DEM FRAME (accepted by flag): {p}")


# ══════════════════════════════════════════════════════════════════════
# THE SHARED DATA REPO (owner ruling e9daef5)
# ══════════════════════════════════════════════════════════════════════

def data_mounts(root) -> dict:
    """Where each data directory of ``root`` actually resolves to.

    Recorded on every build.  Two lanes on two corpora do not measure the
    same thing, and the difference is invisible in a build log: a private
    ``Elevation_data`` warms on its own schedule, and warm-vs-cold inset
    state has already moved measured terrain by 12 m here.
    """
    root = Path(root)
    out = {}
    for name in SHARED_DATA_DIRS:
        p = root / name
        if not p.exists():
            out[name] = {"present": False, "shared": False,
                         "realpath": None, "symlink": False}
            continue
        real = p.resolve()
        try:
            real.relative_to(DATA_REPO.resolve())
            shared = True
        except ValueError:
            shared = False
        out[name] = {"present": True, "shared": shared,
                     "realpath": str(real), "symlink": p.is_symlink()}
    return out


def require_shared_data(mounts: dict, *, allow_private: bool = False) -> None:
    """Refuse a build whose data does not come from the shared repo."""
    private = [n for n, m in mounts.items() if m["present"] and not m["shared"]]
    if private and not allow_private:
        lines = "\n  ".join(f"{n} -> {mounts[n]['realpath']}" for n in private)
        raise SystemExit(
            f"REFUSING: {len(private)} data directory/directories are a "
            f"PRIVATE corpus, not a mount of {DATA_REPO}:\n  {lines}\n"
            f"Owner ruling e9daef5: one shared data repo across lanes is "
            f"MANDATORY — no lane redownloads or regenerates caches.  A "
            f"private corpus warms on its own schedule, so its builds are "
            f"not comparable with any other lane's.\n"
            f"Fix: tools/harness/lane_worktree.sh up <LANE>   (it mounts "
            f"every data dir the repo holds).  --allow-private-data "
            f"proceeds KNOWINGLY and records it.")
    for n in private:
        print(f"  [harness] PRIVATE DATA (accepted by flag): {n} -> "
              f"{mounts[n]['realpath']}")


def missing_shared_artifacts(root, lat, lon) -> list:
    """Named artifacts this build NEEDS that the shared repo does not have.

    Each one is something the engine would silently download or regenerate
    mid-build — a shared-repo mutation as a build side effect, which the
    ruling forbids.  Returned as (scope, artifact, why) so the refusal can
    name the artifact and the exact flag that authorises fetching it.

    This is the honest half: it names what can be checked from the
    filesystem BEFORE the build.  Staleness that only the engine can judge
    (a road-feed fingerprint, a changed query box) is caught by the
    post-build write audit instead — a mutation, not a prediction.
    """
    state = dem_cache_state(root, lat, lon)
    out = []
    if not state["base_raster"]:
        out.append(("dem", f"Elevation_data/**/{state['tile_stem']}.hgt",
                    "the base DEM raster — the loader would DOWNLOAD it "
                    "mid-build, or hand back an all-zero surface"))
    if not state["airport_insets"]:
        out.append(("dem",
                    f"Elevation_data/**/{state['tile_stem']}_airport_insets/",
                    "the airport elevation insets — the build would fetch "
                    "them, or grade on the base surface while production "
                    "grades on the inset-baked one"))
    if not state["airports_layer"]:
        out.append(("osm_layers",
                    f"OSM_data/**/{_short_latlon(lat, lon)}_airports.osm.bz2",
                    "the cached airports OSM layer — the build would run an "
                    "overpass QUERY, and without it the DEM prep has no "
                    "smoothing masks"))
    return out


def require_no_implicit_refresh(missing: list, requested: set) -> None:
    """The refusal.  A build must never mutate the shared repo as a side
    effect (ruling §2) — so a missing artifact stops the build and names
    the flag that would fetch it, instead of being fetched silently."""
    unauthorised = [m for m in missing if m[0] not in requested]
    if not unauthorised:
        for scope, artifact, why in missing:
            print(f"  [harness] refresh AUTHORISED ({scope}): {artifact}")
        return
    scopes = sorted({s for s, _a, _w in unauthorised})
    lines = "\n  ".join(f"[{s}] {a}\n      {w}" for s, a, w in unauthorised)
    raise SystemExit(
        f"REFUSING: {len(unauthorised)} artifact(s) are MISSING from the "
        f"shared data repo, and building would fetch or regenerate them as "
        f"a SIDE EFFECT:\n  {lines}\n"
        f"Owner ruling e9daef5: downloads and cache regenerations write "
        f"into the shared repo EXACTLY ONCE, as EXPLICIT logged events — "
        f"never as a build side effect.  The KCLT road-feed refresh that "
        f"ran inside a tile build on 2026-08-05 and silently changed "
        f"campaign hashes is the precedent this forbids.\n"
        f"To fetch them deliberately (locked, hash-stamped, recorded in "
        f"{REFRESH_LEDGER}):\n"
        f"    --refresh-data {','.join(scopes)}")


# ══════════════════════════════════════════════════════════════════════
# THE EXPLICIT INSET WARM (--warm-insets, round-13 spec AMENDMENT)
# ══════════════════════════════════════════════════════════════════════
# An airport build NEVER fetches an inset: its DEM comes from
# ``auto_patch.elevation._load_airport_dem`` →
# ``O4_Vector_Map.compose_tile_dem_from_disk``, which is pure disk state
# by design.  ``ensure_airport_insets`` is reached only from a TILE
# build — so the one instrument for "this airport's inset is void, refetch
# it" was either a whole-tile build (which refreshes every void inset on
# the tile, against a one-airport authorisation) or the standalone fetch
# tool (which writes the shared repo outside the lock and the ledger).
# Both are unlawful for a one-airport need, so the parameter lives HERE,
# inside the machinery that already locks the scope, snapshots the repo,
# arms the write guard and stamps the ledger.
#
# It is deliberately NOT a fix for the ``is_cached`` size>0 gate (a
# non-empty but INVALID raster still lets a tile pass skip the whole
# fetch); it is the explicit override for airports a human names, and the
# gate is a recorded ledger item.

def warm_airport_insets(icaos, root, lat, lon, prog) -> dict:
    """Fetch/refresh the elevation insets of exactly the named airports.

    Runs the production pass (``O4_Airport_Elevation_Insets.
    ensure_airport_insets``) over a bounding-box map filtered to
    ``icaos``, so R13-1's void-record archiving and the border-aware
    mosaic happen for those airports and NOBODY else's cache moves.  The
    tile completion stamp is deliberately not written: this pass settled
    a named subset, and a stamp claiming the whole tile settled would
    make the next build skip airports this run never looked at.

    ``refresh=True``, because a human naming an airport IS the decision
    this flag exists to carry: the pass re-queries and re-fetches instead
    of consulting the cache, negatives included.  Measured 2026-08-11 on
    the first KMCI warm — the TNM discovery API answered 504 (an outage,
    not an answer), the strategy reported no coverage, and the index took
    a DURABLE ``USGS3DEP: no-coverage`` for the airport; without a
    refresh, every later warm would skip the provider and hand back the
    30 m global fallback forever.

    The caller owns the law: the scope lock, the before/after snapshot
    and the armed write guard are already held.  Returns a summary for
    the frame record.
    """
    for p in (root / "src", root, root / "tests", root / "tools"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import O4_Config_Utils as CFG                          # noqa: E402
    import O4_File_Names as FNAMES                         # noqa: E402
    import O4_OSM_Utils as OSM                             # noqa: E402
    import O4_Vector_Map as VMAP                           # noqa: E402
    import O4_Airport_Elevation_Insets as INSETS           # noqa: E402

    tile = CFG.Tile(lat, lon, "")
    try:
        tile.read_from_config()
    except Exception:
        pass
    # The airport dictionary comes from the CACHED OSM layer — the same
    # chain production and the standalone DEM prep run, and network-free
    # because the harness already refuses a build without that cache.
    airports_cache = FNAMES.osm_cached(lat, lon, "airports")
    if not os.path.isfile(airports_cache):
        raise SystemExit(
            f"REFUSING --warm-insets: no cached airports OSM layer for "
            f"{lat:+d}{lon:+d}, so the inset bounding boxes would come "
            f"from an overpass QUERY — a second unauthorised fetch.  "
            f"Warm it with --refresh-data osm_layers first.")
    airport_layer = OSM.OSM_layer()
    OSM.OSM_queries_to_OSM_layer(
        VMAP.AIRPORTS_QUERIES, airport_layer, lat, lon, ["all"],
        cached_suffix="airports")
    dico_airports = VMAP.build_airports_dico(tile, airport_layer)
    boxes = INSETS._airport_bounding_boxes(tile, dico_airports)
    wanted = {icao: box for icao, box in boxes.items() if icao in icaos}
    missing = sorted(set(icaos) - set(wanted))
    if missing:
        raise SystemExit(
            f"REFUSING --warm-insets: {missing} is not an airport of tile "
            f"{lat:+d}{lon:+d} (its inset cache lives on another tile, and "
            f"this run's lock and snapshot cover THIS one).  Airports "
            f"here: {sorted(boxes)[:12]}...")
    definitions = INSETS.select_provider_definitions(
        getattr(tile, "airport_elevation_providers", "auto"))
    resolution_m = INSETS.parse_airport_elevation_level(
        getattr(tile, "airport_elevation_level", "auto"))
    fetch_counter = [0]
    prog.note(f"WARM INSETS (authorised, locked, ledgered): "
              f"{sorted(wanted)} on tile {lat:+d}{lon:+d} via "
              f"{[d['code'] for d in definitions]} — a fetch here is the "
              f"POINT of this run, not a side effect")
    INSETS.ensure_airport_insets(lat, lon, wanted, definitions,
                                 resolution_m, refresh=True,
                                 fetch_counter=fetch_counter)
    summary = {"airports": sorted(wanted), "fetch_attempts": fetch_counter[0],
               "insets": {}}
    for icao in sorted(wanted):
        for definition in definitions:
            path = FNAMES.airport_inset_dem(lat, lon, icao,
                                            definition["code"])
            if os.path.isfile(path):
                summary["insets"][os.path.basename(path)] = round(
                    INSETS.inset_valid_fraction(path), 6)
    prog.note(f"warm-insets done: {fetch_counter[0]} fetch attempt(s), "
              f"valid fraction(s) {summary['insets'] or 'NONE CACHED'}")
    return summary


# ══════════════════════════════════════════════════════════════════════
# THE SWALLOWED-DEGRADATION REFUSALS (2026-08-07) — DETECTOR 2
# ══════════════════════════════════════════════════════════════════════
# Detector 1 (``require_no_swallowed_write_block``) reads the write
# guard's own record and lives with the rest of the shared-repo write law
# in ``shared_repo_guard.py``; this one reads the BUILT LAYOUT.  They
# close the same hole from opposite ends on purpose — a single detector
# here is a single point of silence, and this class of defect is
# invisible in a build log by construction (it exits 0).

def require_dem_prep_succeeded(provenance, *, allow_degraded: bool = False,
                               prog=None) -> None:
    """DETECTOR 2 — the built layout carries NO DEM provenance at all.

    Independent of detector 1 and of the pre-build cache check, and it
    reads the OUTPUT rather than the cause: ``pipeline`` sets
    ``layout.dem_inset_provenance`` to
    ``provenance.dem_provenance_from_dem(dem)`` for any DEM object and to
    ``None`` only when there was NO DEM — the exact state the swallowed
    prep failure leaves behind (both arms of ``tmp/sliver_attrib`` carry
    ``dem_inset_provenance: null``).  It therefore also catches a prep that
    died for a reason the guard never saw.

    A DEM-less build is never a measurement: with ``compute_elevations``
    on, every seed the solve would take from terrain is simply absent.
    """
    if provenance is not None:
        return
    msg = ("this build's layout carries NO DEM provenance "
           "(dem_inset_provenance is null), which pipeline writes ONLY when "
           "the build had no DEM OBJECT AT ALL — the DEM prep failed and "
           "auto_patch.elevation._load_airport_dem's single "
           "'except Exception' turned it into a WARN line.  Every elevation "
           "in the patch was solved without terrain, and the layout comes "
           "out silently smaller (HECA 2026-08-07: 18.5 k nodes against "
           "production's 34-36 k).")
    if not allow_degraded:
        if prog is not None:
            prog.note("EXIT rc=1 REFUSED: " + msg)
        raise SystemExit("REFUSING to report this build: " + msg + "\n"
                         + "The build log's '[pav-builder] WARN: "
                           "production-parity DEM prep failed' line names "
                           "the cause.\n" + _DEGRADED_OPTIONS)
    if prog is not None:
        prog.note("DEGRADED (accepted by --allow-degraded-dem): " + msg)
    print("  [harness] DEGRADED BUILD (accepted by flag): " + msg)


def apply_xplane_install_paths(owner_cfg=OWNER_APP_CFG) -> dict:
    """Copy the X-Plane install paths out of the owner's app config into the
    live ``O4_Config_Utils`` globals — the ONLY thing taken from it.

    Why mandatory for a tile build: ``run_auto_patch_generation`` calls the
    generator only when it can resolve a CIFP directory (from
    ``cifp_data_path``, else autodetected under ``custom_scenery_dir``).
    The dev tree ships both EMPTY, so a whole-tile build there silently
    produces a tile with NO auto_patch surfaces (measured on +30+031: zero
    auto-patch phases, 40.1 MB mesh vs 44.5, 11.5 MB DSF vs 12.5).
    """
    import O4_Config_Utils as CFG
    applied = {}
    for key, value in read_cfg(owner_cfg).items():
        if key in XPLANE_PATH_KEYS and value:
            CFG.set_global_variables(key, CFG.config_compatibility(value))
            applied[key] = value
    if not applied.get("cifp_data_path") and \
            not applied.get("custom_scenery_dir"):
        raise SystemExit(
            "REFUSING: no CIFP directory and no Custom Scenery directory "
            "resolve — auto_patch generation would be SKIPPED and the tile "
            "would build with no airport surfaces at all, exiting 0.")
    return applied


def tile_cfg_stem(lat: int, lon: int) -> str:
    """``+30+031``, spelled by the engine's own ``O4_File_Names``.

    Imported at CALL time (never at module import) so this entry keeps
    working before the engine is on ``sys.path`` — and so the tile-cfg
    NAME can never drift from the name the engine looks for, which is the
    whole failure mode a hand-copied input has.
    """
    if str(ROOT / "src") not in sys.path:
        sys.path.append(str(ROOT / "src"))
    import O4_File_Names as FNAMES
    return FNAMES.short_latlon(lat, lon)


def canonical_tile_cfg(lat: int, lon: int, source_root=None) -> Path:
    """THE per-tile cfg a lane's build dir is provisioned FROM.

    ``<main engine tree>/Tiles/zOrtho4XP_+XX+YYY/Ortho4XP_+XX+YYY.cfg`` —
    the ritual's own canonical source (:data:`MAIN_ENGINE_TREE`), the same
    place ``lane_worktree.sh`` clones ``Ortho4XP.cfg`` and ``Patches/``
    from.  Deliberately NOT the shared data repo and NOT the owner's app
    config: ``default_website`` / ``default_zl`` / ``zone_list`` are
    PER-TILE variables and ``O4_Cfg_Vars`` excludes them from the global
    config by construction, so the owner's app cfg has no such keys to
    give (and production supplies them per BUILD, from the app's job —
    ``o4_driver``'s ``job["provider"]`` / ``job["zl"]``).
    """
    root = Path(source_root) if source_root is not None else MAIN_ENGINE_TREE
    stem = tile_cfg_stem(lat, lon)
    return root / "Tiles" / f"zOrtho4XP_{stem}" / f"Ortho4XP_{stem}.cfg"


def canonical_global_cfg(source_root=None) -> Path:
    """THE global ``Ortho4XP.cfg`` a DERIVED per-tile cfg comes from.

    Same tree as :func:`canonical_tile_cfg` — the one ``lane_worktree.sh``
    clones into every lane — so "the global defaults" names ONE file for
    every lane, not whatever each lane's cwd happens to resolve
    (``FNAMES.data_path("Ortho4XP.cfg")``) at import time.
    """
    root = Path(source_root) if source_root is not None else MAIN_ENGINE_TREE
    return root / "Ortho4XP.cfg"


def engine_global_cfg() -> Path:
    """The global cfg THIS PROCESS's engine actually reads.

    ``O4_Config_Utils.global_cfg_file`` is ``FNAMES.data_path(
    "Ortho4XP.cfg")``, which in a source checkout resolves against the
    CWD — so it is the LANE's clone, not the canonical main-tree file the
    derivation is recorded against.  The ritual clones one from the other,
    so they normally agree; when they do not, a derived cfg would be
    RECORDED against one set of defaults and RUN on another, which is the
    two-instruments-one-population defect in a single line of provenance.
    Both are recorded, and a divergence is said out loud.
    """
    if str(ROOT / "src") not in sys.path:
        sys.path.append(str(ROOT / "src"))
    import O4_File_Names as FNAMES
    return Path(FNAMES.data_path("Ortho4XP.cfg"))


#: What a DERIVED per-tile cfg contains: NOTHING but a comment header.
#:
#: Chosen from the engine's own cfg semantics, not from taste
#: (``O4_Config_Utils``):
#:
#: * module import sets every tile var to its registry default and then
#:   applies the GLOBAL ``Ortho4XP.cfg`` over it;
#: * ``Tile.__init__`` seeds ``self.<var>`` for every ``list_tile_vars``
#:   entry FROM those module globals;
#: * ``read_from_config`` then applies only the keys the per-tile file
#:   actually CONTAINS — it is an OVERRIDE layer, exactly as the owner's
#:   ruling says.
#:
#: So a per-tile cfg with ZERO override lines is, key for key, the global
#: defaults — provably, with no snapshot to go stale.  Writing the global
#: values out instead would FREEZE them into a lane input: a later change
#: to the canonical global cfg would stop reaching this tile, which is the
#: hand-seeded-input defect wearing the ritual's clothes.  Comment lines
#: are skipped by both readers (``line[0] == "#"``), so the header is
#: engine-invisible by construction and says, at the file, what it is.
#:
#: NOT a zero-byte file, deliberately: an empty file is indistinguishable
#: from a truncated write, and the next human to open it learns nothing.
#: The line that identifies a DERIVED cfg on a LATER run, when it reads
#: as an ordinary ``present`` lane input.
DERIVED_CFG_MARKER = "# DERIVED PER-TILE CONFIG"

DERIVED_CFG_HEADER = """\
# DERIVED PER-TILE CONFIG — owner ruling 2026-08-14, "A TILE WITHOUT A
# PER-TILE CFG USES GLOBAL DEFAULTS".  No canonical per-tile cfg existed
# for this tile, so the ritual provisioned this one instead of refusing.
#
# It carries ZERO override lines ON PURPOSE.  The engine reads a per-tile
# cfg as an OVERRIDE of the globals (Tile.__init__ seeds every tile var
# from the global config; read_from_config applies only the keys present
# here), so "no keys" IS "the global defaults" — and nothing is frozen
# here to drift from them later.
#
#   global source : {src}
#   sha256        : {sha}
#   provisioned   : {when} by tools/harness/build_airport.py
#
# Written by the ritual, never hand-seeded (ruling 2026-08-12b).  The
# engine's own step 4 (O4_Tile_Utils.build_tile -> tile.write_to_config)
# materialises the full tile-var set over this file once a build gets
# that far; from then on this cfg is the lane's OWN input and is never
# overwritten by provisioning again.
"""


def provision_tile_cfg(lat: int, lon: int, build_dir, prog=None,
                       source_root=None) -> dict:
    """Provision the lane build dir's per-tile cfg from the canonical
    source, and RECORD where it came from.

    OWNER RULING 2026-08-12b — "LANE INPUTS ARE PROVISIONED BY THE RITUAL,
    NEVER HAND-SEEDED".  A fresh lane build dir has no
    ``Ortho4XP_+XX+YYY.cfg``; ``Tile.read_from_config`` then falls back to
    the GLOBAL config, which by construction carries no ``default_website``
    — and the tile build refuses with "EMPTY default_website".  On
    2026-08-12 two lanes each improvised a different cfg source to get
    past it, which is the census-wrapper defect re-emerging: the
    inconsistency, not the copy, is the harm.

    Four outcomes, all recorded:

    * ``provisioned`` — a byte copy of the canonical cfg, with its sha256;
    * ``derived-from-global-defaults`` — there is NO canonical per-tile
      cfg for this tile, so one is derived from the canonical GLOBAL
      ``Ortho4XP.cfg`` (OWNER RULING 2026-08-14, "A TILE WITHOUT A
      PER-TILE CFG USES GLOBAL DEFAULTS", amending the refusal this
      function used to raise).  The derived file carries zero override
      lines — see :data:`DERIVED_CFG_HEADER` for why that IS the global
      defaults under the engine's own cfg semantics.  Recorded with the
      global source's path and sha256 AND the derived file's own sha256,
      and printed loudly: a tile built on defaults nobody chose per-tile
      must be visible in the log and in ``frame.json``, which is what
      keeps the 2026-08-12b substance (one canonical source, ritual-
      provisioned, recorded) intact under the amendment;
    * ``present`` — the build dir already has one; it is NEVER overwritten
      (a lane deliberately building at another provider/ZL owns its own
      input, and silently replacing it would be a second frame change no
      log line mentions).  Its own sha256 is recorded, so the frame says
      WHICH cfg the build ran on either way;
    * ``is_canonical_source`` — the build dir IS the canonical location
      (a build in the main tree); nothing to copy.

    A missing canonical per-tile cfg used to REFUSE.  It no longer does
    (2026-08-14) — but the reason it did still holds and shapes the
    derivation: nothing here may SYNTHESIZE a value.  A made-up provider
    or ZL would build a tile nobody asked for and exit 0.  The derived
    cfg therefore invents nothing: it overrides nothing, and the tile
    runs on exactly what the global config says.  Where the globals
    genuinely have nothing to give — ``default_website`` / ``default_zl``
    / ``zone_list`` are excluded from the global config BY CONSTRUCTION
    (``O4_Cfg_Vars.cfg_global_tile_vars``) because production supplies
    them per BUILD from the app's job — the downstream provider check
    still refuses, and says so naming this derivation.  A missing GLOBAL
    config refuses: with neither file there is no "defaults" to derive
    from, only invention.
    """
    stem = tile_cfg_stem(lat, lon)
    dest = Path(build_dir) / f"Ortho4XP_{stem}.cfg"
    src = canonical_tile_cfg(lat, lon, source_root)
    rec = {"cfg": str(dest), "canonical_source": str(src),
           "action": None, "sha256": None}

    is_source = (dest.is_file() and src.is_file()
                 and dest.resolve() == src.resolve())
    if is_source:
        rec["action"] = "is_canonical_source"
        rec["sha256"] = hashlib.sha256(dest.read_bytes()).hexdigest()
    elif dest.is_file():
        rec["action"] = "present"
        rec["sha256"] = hashlib.sha256(dest.read_bytes()).hexdigest()
        # A cfg an EARLIER run of this build dir DERIVED reads as
        # "present" on every later run — true, but it would quietly
        # downgrade "this tile is on global defaults" to "the lane's own
        # cfg" in the frame.  The marker travels in the file, so say so.
        try:
            rec["was_derived"] = DERIVED_CFG_MARKER in dest.read_text(
                errors="ignore")
        except OSError:                                # pragma: no cover
            rec["was_derived"] = None
    elif not src.is_file():
        # OWNER RULING 2026-08-14 — the refusal that stood here amends
        # into a DERIVATION.  Per-tile cfg is an OVERRIDE of globals in
        # the engine's own reader, so "no per-tile cfg" is a legitimate
        # state with a defined meaning: the global defaults.
        gsrc = canonical_global_cfg(source_root)
        if not gsrc.is_file():
            raise SystemExit(
                f"REFUSING: this build dir has no per-tile config "
                f"({dest}), the canonical per-tile source does not exist "
                f"({src}), and neither does the canonical GLOBAL config "
                f"({gsrc}).\n"
                f"  With no globals there are no DEFAULTS to derive from "
                f"— only invention, and a synthesized provider and ZL "
                f"build a tile nobody asked for and exit 0.\n"
                f"  Fix: restore the main tree's Ortho4XP.cfg (the ritual "
                f"clones it into every lane: tools/harness/"
                f"lane_worktree.sh up NAME) — owner rulings 2026-08-12b "
                f"(inputs are provisioned, never hand-seeded) and "
                f"2026-08-14 (a tile without a per-tile cfg uses global "
                f"defaults).")
        gsha = hashlib.sha256(gsrc.read_bytes()).hexdigest()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(DERIVED_CFG_HEADER.format(
            src=gsrc, sha=gsha,
            when=time.strftime("%Y-%m-%dT%H:%M:%S")))
        rec["action"] = "derived-from-global-defaults"
        rec["global_source"] = str(gsrc)
        rec["global_sha256"] = gsha
        rec["sha256"] = hashlib.sha256(dest.read_bytes()).hexdigest()
        # WHICH globals the engine will actually read (see
        # engine_global_cfg): recorded beside the canonical one, never
        # instead of it.
        try:
            eff = engine_global_cfg()
            rec["engine_global_source"] = str(eff)
            rec["engine_global_sha256"] = (
                hashlib.sha256(eff.read_bytes()).hexdigest()
                if eff.is_file() else None)
        except Exception as exc:                       # pragma: no cover
            rec["engine_global_source"] = None
            rec["engine_global_sha256"] = f"unresolved: {exc!r}"
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())       # BYTE copy, never a render
        rec["action"] = "provisioned"
        rec["sha256"] = hashlib.sha256(dest.read_bytes()).hexdigest()

    if prog is not None:
        if rec["action"] == "derived-from-global-defaults":
            # LOUD, by ruling: this tile is running on defaults nobody
            # chose FOR IT, and the log is where that has to be visible.
            prog.note(
                f"per-tile cfg DERIVED-FROM-GLOBAL-DEFAULTS: {dest} "
                f"(sha256 {rec['sha256'][:12]}) — no canonical per-tile "
                f"cfg exists ({src}), so this tile runs on the GLOBAL "
                f"config {rec['global_source']} (sha256 "
                f"{rec['global_sha256'][:12]}) with ZERO per-tile "
                f"overrides.  Owner ruling 2026-08-14: a tile without a "
                f"per-tile cfg uses global defaults.")
            if (rec.get("engine_global_sha256")
                    and rec["engine_global_sha256"] != gsha):
                prog.note(
                    f"per-tile cfg DERIVATION FRAME DIVERGES: this process's "
                    f"engine reads {rec['engine_global_source']} (sha256 "
                    f"{rec['engine_global_sha256'][:12]}), NOT the canonical "
                    f"{gsrc} the derivation is recorded against — the tile "
                    f"would run on defaults the frame does not name.  "
                    f"Re-run tools/harness/lane_worktree.sh up on this lane "
                    f"to re-clone the canonical global cfg.")
        else:
            prog.note(
                f"per-tile cfg {rec['action'].upper()}: {dest} "
                f"(sha256 {rec['sha256'][:12]}, canonical source {src})"
                + ("  — byte copy from the ritual's own canonical source; "
                   "a hand-seeded lane input is the defect owner ruling "
                   "2026-08-12b names."
                   if rec["action"] == "provisioned" else
                   ("  — the lane's OWN cfg, left untouched"
                    + ("; it was DERIVED from global defaults by an "
                       "earlier run (ruling 2026-08-14), not chosen for "
                       "this tile."
                       if rec.get("was_derived") else "."))
                   if rec["action"] == "present" else
                   "  — this build dir IS the canonical location."))
    return rec


# ══════════════════════════════════════════════════════════════════════
# RECORDING
# ══════════════════════════════════════════════════════════════════════

class Progress:
    """The ``.progress`` convention: START / step / EXIT stamps a lead can
    tail to audit liveness without touching the run."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def note(self, msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
        with open(self.path, "a") as fh:
            fh.write(line + "\n")
        print(f"  [harness] {msg}", flush=True)


def env_snapshot(root: Path, cfg_diff: dict) -> dict:
    def _git(*args):
        try:
            return subprocess.run(["git", "-C", str(root), *args],
                                  capture_output=True, text=True,
                                  timeout=20).stdout.strip()
        except Exception:
            return ""
    try:
        sys.path.insert(0, str(root / "tools"))
        from run_with_ledger import code_tree_hash
        tree_hash = code_tree_hash(str(root))
    except Exception as exc:                              # pragma: no cover
        tree_hash = f"<unavailable: {exc!r}>"
    return {
        "cwd": str(root),
        "git_head": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "code_tree_hash": tree_hash,
        "o4_env": {k: v for k, v in sorted(os.environ.items())
                   if k.startswith("O4_")},
        "xplane_root": os.environ.get("XPLANE_ROOT", "/Users/noah/X-Plane 12"),
        "owner_cfg_present": OWNER_APP_CFG.is_file(),
        "dem_frame_cfg_divergence": {k: {"ours": o, "production": t}
                                     for k, (o, t) in cfg_diff.items()},
        "python": sys.version.split()[0],
    }


def body_sha256(osm: Path) -> str:
    """sha256 of the patch BODY — the provenance stamp (first two lines)
    makes the raw file hash differ on every build, so byte-identity A/Bs
    must hash the body."""
    lines = Path(osm).read_bytes().split(b"\n")
    return hashlib.sha256(b"\n".join(lines[2:])).hexdigest()


def mask_overlay_subtrees(tiles=()):
    """The ``Masks/`` subtree(s) to seed, as paths relative to the masks
    root: ONE per tile in scope, or ``[""]`` (the whole root) when the
    caller names no tile.

    The relative spelling is ``O4_File_Names.long_latlon`` ITSELF, never a
    second copy of it — the mask corpus is laid out ``Masks/+30+030/
    +30+031/``, and a harness that spelled that rule again would seed an
    overlay the engine then reads past (a cold masks stage that looks like
    a warm one).  The whole-root default is the conservative superset for
    the entries that do not know their tile (``repro_cut``,
    ``classify_report``); the corpus is small enough (~32 MB, ~170 files,
    all clonefile-seeded) that the difference is noise.
    """
    tiles = list(tiles or ())
    if not tiles:
        return [""]
    if str(ROOT / "src") not in sys.path:
        sys.path.append(str(ROOT / "src"))
    import O4_File_Names as FNAMES
    return [FNAMES.long_latlon(int(lat), int(lon)) for lat, lon in tiles]


#: THE LANE-PERSISTENT DERIVED-CACHE ROOT's subdirectory inside a lane.
#: ``tmp/`` is already the lane's own product area (root CLAUDE.md: "Lane
#: products (``Patches``, ``Tiles``, ``Previews``, ``tmp``) stay
#: lane-local"), so nothing new about the corpus law is being claimed here.
LANE_CACHE_SUBDIR = ("tmp", "engine_caches")


def lane_cache_root(lane_root=None) -> Path:
    """WHERE A LANE'S DERIVED CACHES LIVE ACROSS RUNS (perf P2, Lane A).

    THE MEASURED DEFECT (2026-08-13, P1's cost table).  The redirect below
    is per-RUN — ``<out>/<tag>.engine_caches/`` — so everything the engine
    DERIVES inside a lane build is thrown away when the run ends.  At HECA
    that is ``_compute_dsf_object_buildings``: 66.6 s of OBJ8 parse +
    O(n²) contact-graph partition, re-run by every lane build forever
    (OTHH ~455 s, KCLT ~18 s).  The COW seeding does not save it, because
    the SHARED sidecar is stale for the lane: the pack's own ``.obj``
    files enter the footprint fingerprint, and the Phase-2 y-bake rewrites
    them AFTER the sidecar for that same run was written — so a run
    invalidates the sidecar it just wrote (measured at HECA: sidecar
    07:03, 376 of 568 ``.obj`` rewritten 07:14, fingerprint
    ``d6b89fe7`` vs the lane's ``78a5f07d``).  The next run at the SAME
    tree bakes byte-identically (``object_rebake._rewrite_y_tokens``
    keeps the mtime on an identical rewrite), so run 2 hits — but only if
    run 1's sidecar still EXISTS.  A persistent root is what makes it
    exist.

    STILL LANE-LOCAL, so the corpus law (owner ruling e9daef5) is
    untouched: this is the lane's own ``tmp/`` product area, one root per
    WORKTREE, never the shared repo and never another lane's.
    ``O4_LANE_CACHE_ROOT`` overrides the location (the twins' seam, and
    the escape for a lane that wants a per-run root back).

    STALENESS IS SAFE BY CONSTRUCTION, which is why a persistent clone may
    shadow a later shared refresh: every artifact under these two roots is
    CONTENT-KEYED — the object/pavement/classification sidecars carry the
    input fingerprint they were computed under (``dsf_reader
    ._object_footprint_sidecar``) and the DSFTool dump carries the DSF's
    own hash in its file name.  A stale clone therefore never answers
    WRONG; at worst it fails to match and the reader recomputes.  The
    MASKS root is deliberately NOT persisted: masks are corpus DATA the
    engine rewrites per tile, not a fingerprinted derived cache, so they
    keep their per-run overlay.
    """
    override = os.environ.get("O4_LANE_CACHE_ROOT")
    if override:
        return Path(override)
    return Path(lane_root or Path.cwd()).joinpath(*LANE_CACHE_SUBDIR)


def redirect_engine_caches(out_dir, tag, prog=None, authorised=(), tiles=(),
                           lane_root=None, persistent=True):
    """Point the engine's THREE WRITABLE data roots lane-local.

    THE MEASURED DEFECT (2026-08-11, the round-9 KCLT acceptance build).
    The shared-repo write guard was armed and the build still wrote
    ``Airport_mod_cache/zOrtho4XP_+35-081/+35-081.dsf.8828b7db.text`` into
    the shared repo: the DSFTool SUBPROCESS writes its dump directly, so no
    Python-level guard can intercept it, and only the post-build snapshot
    caught it — the run was flagged CONTAMINATED.

    THE MECHANISM IS THE PYTEST SUITE'S OWN (``tests/conftest.py``),
    pointed at this tag's artifact area: ``O4_DSF_CACHE_DIR`` for the
    DSFTool dump cache (read inside ``O4_File_Names._apply_data_root``, so
    a module reload recomputes the redirect instead of undoing it) and
    ``O4_AIRPORT_MOD_CACHE_DIR`` for the per-pack sidecar cache, seeded as
    a COPY-ON-WRITE READ-THROUGH overlay (:func:`mirror_tree_as_overlay`
    — real dirs, clonefile-seeded files: warm reads, and a write lands
    lane-local even when the writer TRUNCATES IN PLACE, which is what the
    engine's sidecar writers do and what symlink seeding did not survive
    (measured 2026-08-12, seven OTHH sidecars)).  A
    subprocess inherits the environment, which is precisely why the
    redirect rides env variables and not an assignment.

    THE MASKS ROOT joined them 2026-08-12b (owner ruling: lane mask writes
    land lane-local).  Masks are corpus DATA rather than a derived cache,
    which is why they were not here before — but the engine treats the
    masks directory as a per-tile scratch it rewrites: a lane tile build
    on a warm tile refused rc=1 because
    ``O4_Mask_Utils.delete_old_masks_in_tile`` tried to ``os.remove`` 16
    SHARED ``Masks/+30+030/+30+031/*.png`` and the guard blocked all 16
    (which the engine then swallowed under a bare ``except: pass``).  Same
    two halves as the mod cache: ``O4_MASKS_DIR`` (read at call time in
    ``O4_File_Names.masks_root``) plus a copy-on-write overlay seeded from
    the shared subtree of the TILE(S) IN SCOPE (``tiles`` — an iterable of
    ``(lat, lon)``; the whole root when the caller names none), so the
    masks step's reads stay warm and its deletes and rewrites land on
    lane-local clones.

    THE AUTHORISED-REFRESH SKIP.  A scope this run may refresh
    (``--refresh-data airport_mod_cache`` / ``dsf_cache`` / ``masks``) is
    NOT redirected, and its half creates nothing: an authorised refresh
    must land in the SHARED repo, so redirecting it would turn the refresh
    into a silent no-op.  The skip is recorded instead.

    THE DERIVED CACHES PERSIST ACROSS RUNS (perf P2, 2026-08-13).  The two
    FINGERPRINTED roots — the DSFTool dump cache and the per-pack mod cache
    — land under :func:`lane_cache_root` (``<lane>/tmp/engine_caches/``,
    one per WORKTREE) instead of ``<out>/<tag>.engine_caches/``, so what a
    run derives is still there for the next one; ``persistent=False``
    restores the per-run root.  The MASKS root stays per-run: masks are
    corpus data the engine rewrites per tile, not a fingerprinted cache.
    Everything else about the law is unchanged — still lane-local, still
    COW-seeded from the shared corpus, an authorised refresh scope still
    left SHARED.

    Owner ruling e9daef5 (one shared data repo; a build never mutates it
    as a side effect).
    """
    authorised = set(authorised or ())
    base = Path(out_dir) / f"{tag}.engine_caches"
    derived_base = lane_cache_root(lane_root) if persistent else base
    skipped = []
    dsf_dir = mod_dir = masks_dir = None
    seeded = masks_seeded = None

    if "dsf_cache" in authorised:
        skipped.append("dsf_cache")
    else:
        dsf_dir = derived_base / "Default_DSF_cache"
        dsf_dir.mkdir(parents=True, exist_ok=True)
        os.environ["O4_DSF_CACHE_DIR"] = str(dsf_dir)

    if "airport_mod_cache" in authorised:
        skipped.append("airport_mod_cache")
    else:
        mod_dir = derived_base / "Airport_mod_cache"
        # ``DATA_REPO`` bare on purpose: the module global is what a twin
        # monkeypatches to point the seed at a fake corpus.
        seeded = mirror_tree_as_overlay(str(DATA_REPO / "Airport_mod_cache"),
                                        str(mod_dir))
        os.environ["O4_AIRPORT_MOD_CACHE_DIR"] = str(mod_dir)

    if "masks" in authorised:
        skipped.append("masks")
    else:
        masks_dir = base / "Masks"
        masks_seeded = {"dirs": 0, "files": 0, "cloned": 0, "copied": 0}
        for rel in mask_overlay_subtrees(tiles):
            part = mirror_tree_as_overlay(
                str(DATA_REPO / "Masks" / rel) if rel
                else str(DATA_REPO / "Masks"),
                str(masks_dir / rel) if rel else str(masks_dir))
            for key in masks_seeded:
                masks_seeded[key] += part[key]
        os.environ["O4_MASKS_DIR"] = str(masks_dir)

    # THE BELT.  ``build_patch``'s direct callers (oracle.py, who_wrote.py)
    # may already have imported the engine, and ``Default_dsf_cache_dir``
    # is computed at import; ``_apply_data_root`` recomputes it from the
    # environment (the mod-cache root is read at call time and needs no
    # nudge).
    fnames = sys.modules.get("O4_File_Names")
    if fnames is not None:
        fnames._apply_data_root()

    if os.environ.get("ORTHO4XP_DATA_ROOT") and prog is not None:
        prog.note("WARNING: ORTHO4XP_DATA_ROOT is set, so the "
                  "O4_AIRPORT_MOD_CACHE_DIR and O4_MASKS_DIR overrides are "
                  "INERT (O4_File_Names.airport_mod_cache_root / "
                  "masks_root: an explicitly chosen data root is the more "
                  "specific instruction) — the per-pack sidecar cache and "
                  "the masks stay under that root.")

    if prog is not None:
        prog.note(
            f"engine derived-cache roots redirected LANE-LOCAL under "
            f"{derived_base}"
            + (" (LANE-PERSISTENT: reused across runs, so what this build "
               "derives is still there for the next one — the P1 finding "
               "that HECA re-ran _compute_dsf_object_buildings, 66.6 s, "
               "every lane build; masks stay per-run under "
               f"{base})" if persistent else " (per-run)")
            + ": "
            f"dump cache={dsf_dir or 'SHARED (authorised refresh)'}, "
            f"mod cache={mod_dir or 'SHARED (authorised refresh)'}"
            + (f" (overlay seeded copy-on-write: {seeded['files']} file(s) "
               f"— {seeded['cloned']} cloned, {seeded['copied']} copied — "
               f"{seeded['dirs']} dir(s))" if seeded is not None else "")
            + f", masks={masks_dir or 'SHARED (authorised refresh)'}"
            + (f" (overlay seeded copy-on-write: {masks_seeded['files']} "
               f"file(s) — {masks_seeded['cloned']} cloned, "
               f"{masks_seeded['copied']} copied — {masks_seeded['dirs']} "
               f"dir(s); subtrees={mask_overlay_subtrees(tiles)})"
               if masks_seeded is not None else "")
            + ".  This closes the DSFTool SUBPROCESS dump hole the write "
              "guard cannot see (KCLT 2026-08-11, run flagged CONTAMINATED) "
              "and the masks step's rewrite of the SHARED mask rasters "
              "(HECA tile arm 2026-08-12, 16 blocked removes)."
            + (f"  Left SHARED for the authorised refresh: {sorted(skipped)} "
               f"— a redirect there would make the refresh a silent no-op."
               if skipped else ""))

    return {
        "base": str(base),
        "derived_base": str(derived_base),
        "derived_persistent": bool(persistent),
        "dsf_dump_cache": (str(dsf_dir) if dsf_dir is not None else None),
        "airport_mod_cache": (str(mod_dir) if mod_dir is not None else None),
        "mod_cache_seeded": seeded,
        "masks": (str(masks_dir) if masks_dir is not None else None),
        "masks_seeded": masks_seeded,
        "masks_subtrees": mask_overlay_subtrees(tiles),
        "left_shared_for_refresh": sorted(skipped),
    }


def arm_shared_repo_protection(root, out_dir, tag, prog=None,
                               write_guard=None, tiles=()):
    """THE ARMING COMPOSITION, in ONE place: ``(guard, redirects)``.

    Every entry that calls the engine IN PROCESS needs both halves, in this
    order, and a hand-assembled second arrangement of them is the
    census-wrapper defect at one remove — it looks armed and covers one
    hole.  MEASURED 2026-08-11 (lane/smallq): ``tools/classify_report.py``
    built two airports with NEITHER half and wrote ten files into the
    shared corpus (mod-cache sidecars and DSFTool dumps under ``+35-081``
    and ``+39-095``); the same session's guarded builds reported the repo
    unchanged.  Nor does the overlay alone save you: when it was symlink-
    seeded, an unguarded writer wrote THROUGH the links, and the guard
    could not see it either (both halves fixed 2026-08-12 —
    :func:`mirror_tree_as_overlay` seeds copy-on-write and
    :class:`SharedRepoWriteGuard` judges the RESOLVED path).

    TWO PHASES, deliberately not one context manager:

    * the REDIRECT must happen BEFORE the engine is imported
      (``O4_File_Names.Default_dsf_cache_dir`` is computed at import), and
      it rides env variables so the DSFTool SUBPROCESS inherits it;
    * the GUARD is armed only around the BUILD CALL — it is handed back
      un-entered.  Arming it across the engine import would refuse imports
      the write law never meant to cover, and the callers differ in what
      they do between the two moments.

    ``write_guard`` — an already-configured :class:`SharedRepoWriteGuard`
    (its authorised scopes are what the redirect leaves SHARED), or
    ``None`` for the default: nothing authorised, guard ARMED.

    Owner ruling e9daef5 (one shared data repo; a build never mutates it
    as a side effect).
    """
    redirects = redirect_engine_caches(
        out_dir, tag, prog, authorised=getattr(write_guard, "requested", None),
        tiles=tiles, lane_root=root)
    guard = (write_guard if write_guard is not None
             else SharedRepoWriteGuard(set(), root))
    return guard, redirects


def report_guard_churn(guard, prog=None) -> None:
    """Record the two ALLOWED churn classes on a finished guard.

    Neither is corpus data — the engine's cross-process ``.lock`` files are
    coordination state and the library-index sidecar is derived cache — but
    "the repo was untouched apart from the ruled churn" is only a claim
    worth making if the churn is written down.  Shared by every entry that
    arms the guard, so no entry reports a quieter run than another.
    """
    if prog is None:
        return
    if guard.lock_churn:
        prog.note(f"lock churn allowed (coordination state, never corpus "
                  f"data): {len(guard.lock_churn)} operation(s), e.g. "
                  f"{guard.lock_churn[0]['op']} "
                  f"{guard.lock_churn[0]['path']}")
    if guard.library_index_churn:
        prog.note(f"library-index churn allowed (derived install-index "
                  f"cache, never corpus data): "
                  f"{len(guard.library_index_churn)} operation(s), e.g. "
                  f"{guard.library_index_churn[0]['op']} "
                  f"{guard.library_index_churn[0]['path']}")


# ══════════════════════════════════════════════════════════════════════
# THE BUILDS
# ══════════════════════════════════════════════════════════════════════

def diagnose_missing_sidecar(layout) -> str:
    """Name the contributor that killed the sidecar.

    ``layout._write_axes_sidecar`` builds its whole dict inside one
    ``try: ... except Exception: pass``.  ONE contributor raising therefore
    discards the ENTIRE sidecar — axes, anchor, seam pins, crown field,
    pair caps, terrace joints, ruleset — and the only symptom is that every
    later census silently degrades to the context-free frame.  This calls
    each contributor separately, un-swallowed, so the failure has an
    address instead of a silence.  It DIAGNOSES; it never repairs (a
    harness that patched the emitter would be inventing the frame it is
    supposed to measure).
    """
    import traceback
    from auto_patch import verification as V
    from auto_patch.elevation_per_surface.route_profile import apron_terrace
    from auto_patch import grade_law

    probes = [
        ("axes", lambda: V.taxi_axes_ll(layout)),
        ("routes", lambda: V.taxi_routes_ll(layout)),
        ("axes_exact/routes_exact", lambda: V.taxi_axes_exact_ll(layout)),
        ("mesh_edges", lambda: V.junction_mesh_edges_ll(layout)),
        ("terrace_joints",
         lambda: apron_terrace.terrace_joints_sidecar(layout)),
        ("terrace_certificates",
         lambda: apron_terrace.terrace_certificates_sidecar(layout)),
        ("ruleset", lambda: grade_law.ruleset_of(layout)),
    ]
    lines = ["  sidecar contributor probe (each called separately, "
             "exceptions NOT swallowed):"]
    culprits = []
    for name, fn in probes:
        try:
            fn()
            lines.append(f"    OK     {name}")
        except Exception:
            culprits.append(name)
            tb = traceback.format_exc().strip().splitlines()
            lines.append(f"    RAISED {name}:")
            lines.extend(f"      {t}" for t in tb[-4:])
    if not culprits:
        lines.append("    every contributor succeeded — the sidecar was "
                     "gated OFF instead (config.LOG_VERBOSITY <= 0) or the "
                     "write itself failed.")
    else:
        lines.append(f"    => {culprits} discarded the WHOLE sidecar "
                     f"through layout._write_axes_sidecar's bare "
                     f"'except Exception: pass'.")
    return "\n".join(lines)


def build_patch(icao: str, root: Path, out_dir: Path, tag: str,
                prog: Progress, const_dem=None,
                allow_no_sidecar: bool = False,
                write_guard=None, allow_degraded: bool = False,
                solve_capture=None, geometry_only: bool = False) -> dict:
    """One airport → ``<out>/<tag>.osm`` + its ``.axes.json`` sidecar.

    ``write_guard`` — a :class:`SharedRepoWriteGuard` (or ``None`` for the
    default: nothing authorised, guard ARMED), composed with the engine
    cache redirect by :func:`arm_shared_repo_protection` — the ONE arming
    composition, shared with ``tools/classify_report.py``.  It is armed
    HERE, not in ``main``, because ``main`` is not the only entry that
    builds:
    ``tools/harness/oracle.py`` and ``tools/harness/who_wrote.py`` both
    call this function directly, and those are the entries a lane actually
    runs most.  Arming in the CLI only would have left every oracle and
    every authorship trace free to regenerate the shared corpus — the
    precise hole the road-feed precedent went through.

    ``allow_degraded`` — the ``--allow-degraded-dem`` semantics, and for
    the same reason: the two swallowed-degradation refusals fire HERE so
    that a direct caller gets them too, and a direct caller therefore
    needs the same knowing-override its own CLI advertises.  The
    degradation is refused BEFORE the patch is written: an ``.osm`` from a
    DEM-less build sitting in the output directory is exactly the artifact
    a later census picks up by name, so the flag is also what keeps it.
    """
    for p in (root / "src", root, root / "tests", root / "tools"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    # THE ARMING COMPOSITION (redirect now, guard around the build call),
    # before the engine is imported and for the same reason the guard is
    # armed HERE rather than in ``main``: ``oracle.py`` and ``who_wrote.py``
    # call this function directly, and the DSFTool subprocess a direct call
    # spawns writes the shared corpus just as a CLI build's does.
    guard, redirects = arm_shared_repo_protection(
        root, out_dir, tag, prog, write_guard=write_guard)
    from conftest import xplane_root                      # noqa: E402
    from auto_patch.pipeline import build_airport_pavement  # noqa: E402
    from auto_patch import config as ap_cfg               # noqa: E402
    # SOLVE-STAGE CAPTURE (perf P2 instrument 1), armed HERE and not in
    # ``main``: the env key is the engine module's own constant, and
    # importing the engine before ``arm_shared_repo_protection`` has run
    # is the very ordering the composition above exists to prevent.  The
    # capture is a pure reader at the solve boundary — the patch this
    # build writes is unaffected (the byte-identity acceptance is the
    # proof), so no build number is conditional on it.
    if solve_capture is not None:
        from auto_patch.solve_capture import CAPTURE_ENV  # noqa: E402
        os.environ[CAPTURE_ENV] = str(Path(solve_capture).resolve())
        prog.note(f"SOLVE-STAGE CAPTURE armed -> {solve_capture} "
                  f"(per-airport subdirectory); replay with "
                  f"tools/solve_cut.py --replay")
    # The sidecar is gated on this: without it every census silently
    # degrades to the context-free frame.
    ap_cfg.LOG_VERBOSITY = max(1, getattr(ap_cfg, "LOG_VERBOSITY", 0))

    kw = {"compute_elevations": not geometry_only}
    if geometry_only:
        # GEOMETRY-ONLY (owner request 2026-08-14): the pipeline's own
        # documented ``compute_elevations=False`` mode — plan geometry
        # emitted for VISUAL INSPECTION, no solved surface.  Never a
        # measurement: a census of this patch would count a surface that
        # was never built.  The artifact-ledger variant key carries the
        # flag, so a solved arm can never be served from this one.
        prog.note("GEOMETRY-ONLY build (compute_elevations=False): "
                  "visual-inspection artifact — NOT a measurement; "
                  "never census this patch for grade defects")
    synthetic = None
    if const_dem is not None:
        # THE SYNTHETIC PATH, EXPLICIT (owner ruling 2026-08-05 §3: the
        # loader's all-zero refusal stays for PRODUCTION data and gains an
        # explicit synthetic path for the oracle — "the guard catches
        # absent data, not constant data").  Nothing here is a law gate and
        # no rule changes: the ONLY difference from a production build is
        # which surface answers ``alt()``.  The constant is whatever the
        # caller asked for, NEGATIVES INCLUDED — the ruled low world is
        # −500 m (RULINGS 2026-08-06) and the DEM ≡ 1 m interim it
        # supersedes was a dodge around a guard this path never reaches.
        from auto_patch.constant_dem import (              # noqa: E402
            ConstantDEM, PLATEAU_ELEVATION_M, CANYON_ELEVATION_M)
        synthetic = ConstantDEM(float(const_dem))
        kw["tile_dem"] = synthetic
        ruled = {PLATEAU_ELEVATION_M: "the ruled LOW world (plateau: every "
                                      "free value seats at its band FLOOR)",
                 CANYON_ELEVATION_M: "the ruled HIGH world (canyon: every "
                                     "free value seats at its band CEILING)"}
        prog.note(f"SYNTHETIC CONSTANT-DEM world: {synthetic.elevation_m:g} m "
                  f"[{synthetic.world_label}] — "
                  f"{ruled.get(synthetic.elevation_m, 'a custom constant')}.  "
                  f"This is an EXPLICIT DEM SOURCE SUBSTITUTION, not a law "
                  f"gate: no rule changes, only which surface answers alt().")
        if synthetic.elevation_m < 0:
            prog.note(f"  below sea level by {-synthetic.elevation_m:g} m — "
                      f"exercised deliberately (RULINGS 2026-08-06, 'The low "
                      f"extreme is −500 m').  The real DEM frame's cache "
                      f"warmth is irrelevant here; the loader's all-zero "
                      f"guard is never reached, because an oracle DEM "
                      f"arrives as override_dem.")

    t0 = time.time()
    with guard:
        layout = build_airport_pavement(icao, xplane_root(), **kw)
    dt = time.time() - t0
    # THE SWALLOWED-DEGRADATION REFUSALS, before anything is written: the
    # engine catches the guard's refusal and returns a DEM-less layout with
    # rc=0 (module docstring, item 8).  Two detectors, one from the guard's
    # record and one from the layout itself.
    require_no_swallowed_write_block(guard.blocked,
                                     allow_degraded=allow_degraded, prog=prog)
    if not geometry_only:
        # A geometry-only build NEVER solves against terrain, so absent DEM
        # provenance is its lawful state, not a swallowed degradation — the
        # rail's own message ("every elevation was solved without terrain")
        # cannot occur when nothing is solved.  The swallowed-write check
        # above still runs: a blocked corpus write is unlawful either way.
        require_dem_prep_succeeded(
            getattr(layout, "dem_inset_provenance", None),
            allow_degraded=allow_degraded, prog=prog)
    report_guard_churn(guard, prog)
    out_dir.mkdir(parents=True, exist_ok=True)
    osm = out_dir / f"{tag}.osm"
    layout.to_osm(str(osm))
    side = Path(str(osm) + ".axes.json")
    if not side.exists():
        why = diagnose_missing_sidecar(layout)
        msg = (f"NO axes sidecar was written ({side}).  Every census would "
               f"silently fall back to the context-free frame, which "
               f"OVERCOUNTS by construction — the numbers would not be "
               f"defect counts.\n{why}")
        if not allow_no_sidecar:
            raise SystemExit(
                "REFUSING to report this build: " + msg
                + "\nPass --allow-no-sidecar to keep the patch anyway "
                  "(recorded loudly); it is measurable only in the bare "
                  "frame until the writer above is fixed.")
        prog.note("DEGRADED (accepted by flag): " + msg)
    prog.note(f"built {tag} in {dt:.1f}s  shapes={len(layout.shapes)}  "
              f"-> {osm}  sidecar={'OK' if side.exists() else 'MISSING'}  "
              f"body_sha={body_sha256(osm)[:12]}")
    return {
        # ``_layout`` is the live object, for in-process consumers (the
        # oracle reads node values off it through
        # ``constant_dem._node_values`` rather than re-parsing the patch —
        # a second reader of the same thing is a second chance to be wrong).
        # ``_``-prefixed keys are stripped before any JSON dump.
        "_layout": layout,
        "icao": icao, "tag": tag, "patch": str(osm), "sidecar": str(side),
        # The synthetic world, recorded ON THE BUILD.  A census row from a
        # −500 m world and one from a real-DEM build are not comparable,
        # and "which world" must be IN the artifact, not in the tag string
        # a later reader has to parse (frame stamps, RULINGS 2026-08-06).
        "synthetic_dem": (None if synthetic is None else
                          {"elevation_m": synthetic.elevation_m,
                           "world": synthetic.world_label,
                           "is_synthetic": True,
                           "source": synthetic.source_path}),
        "geometry_only": bool(geometry_only),
        "build_seconds": round(dt, 1), "shapes": len(layout.shapes),
        "body_sha256": body_sha256(osm),
        "sidecar_present": side.exists(),
        "write_guard_armed": guard.enabled,
        "write_guard_blocked": list(guard.blocked),
        "write_guard_lock_churn": list(guard.lock_churn),
        "write_guard_library_index_churn": list(guard.library_index_churn),
        "dem_frame_effective": frame_surface_keys(root),
        "dem_inset_provenance": getattr(layout, "dem_inset_provenance", None),
        "engine_cache_redirects": redirects,
        "anchor": (list(layout.anchor) if layout.anchor is not None else None),
    }


def build_tile(lat: int, lon: int, build_dir: str, prog: Progress) -> dict:
    """One whole tile through the four release steps, with the owner's
    X-Plane install paths applied (absorbs ``run_release_tile.py``)."""
    sys.path.append(str(ROOT / "src"))
    import O4_File_Names as FNAMES
    import O4_UI_Utils as UI
    sys.path.append(FNAMES.Provider_dir)
    import O4_Imagery_Utils as IMG
    import O4_Vector_Map as VMAP
    import O4_Mesh_Utils as MESH
    import O4_Mask_Utils as MASK
    import O4_Tile_Utils as TILE
    import O4_Config_Utils as CFG

    IMG.initialize_extents_dict()
    IMG.initialize_color_filters_dict()
    IMG.initialize_providers_dict()
    IMG.initialize_combined_providers_dict()

    paths = apply_xplane_install_paths()
    prog.note(f"X-Plane install paths applied: {sorted(paths)}")

    custom_build_dir = FNAMES.normalize_custom_build_dir(lat, lon, build_dir)
    tile = CFG.Tile(lat, lon, custom_build_dir)
    # THE INPUT, PROVISIONED (owner ruling 2026-08-12b) — before the read,
    # because ``read_from_config`` silently falls back to the global config
    # when the per-tile cfg is absent, and the global config carries no
    # provider at all.  Recorded on the build, never hand-seeded.
    cfg_provenance = provision_tile_cfg(lat, lon, tile.build_dir, prog)
    tile.read_from_config()
    prog.note(f"tile {lat:+d}{lon:+d} build_dir={tile.build_dir} "
              f"website={tile.default_website} zl={tile.default_zl} "
              f"auto_patch={tile.auto_patch} "
              f"modify_custom_airports={tile.modify_custom_airports}")
    if not tile.default_website:
        if cfg_provenance["action"] == "derived-from-global-defaults":
            # The 2026-08-14 amendment removed the missing-cfg refusal, and
            # this is where its LIMIT shows: default_website / default_zl /
            # zone_list are excluded from the global config BY CONSTRUCTION
            # (O4_Cfg_Vars.cfg_global_tile_vars), because production
            # supplies them per BUILD from the app's job.  "Global
            # defaults" therefore has no provider to give, and picking one
            # here would be the synthesized input both rulings forbid.
            raise SystemExit(
                "REFUSING: tile config resolves to an EMPTY "
                "default_website — step 4 would produce provider-less "
                "texture names.\n"
                f"  This tile has NO canonical per-tile cfg, so its cfg "
                f"was DERIVED from the global defaults "
                f"({cfg_provenance['global_source']}, sha256 "
                f"{cfg_provenance['global_sha256'][:12]}) per owner ruling "
                f"2026-08-14 — and the global config carries no "
                f"default_website / default_zl / zone_list AT ALL: "
                f"O4_Cfg_Vars.cfg_global_tile_vars excludes those three by "
                f"construction, because production supplies them per BUILD "
                f"from the app's job (o4_driver job['provider'] / "
                f"job['zl']).\n"
                "  So the derivation got the tile past the missing-cfg "
                "refusal and stopped HERE, at the one setting global "
                "defaults cannot supply.  Fix, at the canonical source and "
                "never lane-side: build the tile once in the main tree (or "
                "copy its cfg there from the app's own build), so every "
                "lane provisions the SAME provider and ZL — owner ruling "
                "2026-08-12b.")
        raise SystemExit(
            "REFUSING: tile config resolves to an EMPTY default_website — "
            "step 4 would produce provider-less texture names.  The "
            f"per-tile cfg this build ran on was {cfg_provenance['action']} "
            f"({cfg_provenance['cfg']}, canonical source "
            f"{cfg_provenance['canonical_source']}): it carries no "
            f"provider, so the canonical source needs fixing at ITS "
            f"location — never patched lane-side (owner ruling "
            f"2026-08-12b).")

    timings = {}
    for name, step in (("1 vector", VMAP.build_poly_file),
                       ("2 mesh", MESH.build_mesh),
                       ("3 masks", MASK.build_masks),
                       ("4 tile", TILE.build_tile)):
        prog.note(f"step {name} START")
        t0 = time.time()
        step(tile)
        timings[name] = round(time.time() - t0, 1)
        prog.note(f"step {name} DONE {timings[name]}s")
        if UI.red_flag:
            raise SystemExit(f"step {name} raised the red flag — stopping")
    return {"tile": [lat, lon], "build_dir": tile.build_dir,
            "step_seconds": timings, "xplane_paths": paths,
            "tile_cfg_provenance": cfg_provenance}


def resolve_tile_for(icao: str, root: Path):
    """The integer tile an airport sits in — needed for the DEM-frame check
    BEFORE paying for the build.  Read straight out of the airport's apt.dat
    block (first runway/helipad/seaplane row), never from a build: a
    geometry-only build to find out where an airport is would be a second
    pass over the same question.
    """
    import math
    for p in (root / "src", root, root / "tests"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    try:
        from conftest import xplane_root
        from auto_patch.apt_dat_reader import (find_airport_apt_dat,
                                               _read_airport_block)
        path = find_airport_apt_dat(xplane_root(), icao)
        if not path:
            return None
        for line in (_read_airport_block(path, icao) or []):
            toks = line.split()
            if not toks:
                continue
            if toks[0] == "100" and len(toks) > 11:       # land runway
                return (int(math.floor(float(toks[9]))),
                        int(math.floor(float(toks[10]))))
            if toks[0] in ("101", "102") and len(toks) > 3:  # water/heli
                return (int(math.floor(float(toks[2]))),
                        int(math.floor(float(toks[3]))))
    except Exception as exc:
        print(f"  [harness] could not resolve {icao}'s tile: {exc!r}")
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("icao", help="ICAO code (or the tile's label with --tile)")
    ap.add_argument("--tag", default=None,
                    help="output tag (default <ICAO>_<yyyymmddThhmm>)")
    ap.add_argument("--patch-only", action="store_true", default=True,
                    help="build the airport patch only (the default)")
    ap.add_argument("--tile", nargs=2, type=int, metavar=("LAT", "LON"),
                    help="build the WHOLE TILE through the four release "
                         "steps instead (release defaults, owner's X-Plane "
                         "install paths)")
    ap.add_argument("--build-dir", default=None,
                    help="--tile only: the scenery pack directory")
    ap.add_argument("--out", type=Path, default=Path("/tmp/harness"),
                    help="output directory (default /tmp/harness)")
    ap.add_argument("--dem", type=float, default=None, metavar="CONST_M",
                    help="build against a SYNTHETIC CONSTANT DEM of this "
                         "elevation — the oracle world (see "
                         "tools/harness/oracle.py).  An explicit DEM SOURCE "
                         "substitution, never a law gate.  NEGATIVES ARE "
                         "LEGAL and are the point: the ruled low world is "
                         "-500 (RULINGS 2026-08-06, 'The low extreme is "
                         "-500 m'), below every CIFP value, so floor-seating "
                         "is guaranteed and below-sea-level handling is "
                         "exercised.  The high world is 10000.  The only "
                         "refused value is the no-data sentinel -32768.")
    ap.add_argument("--allow-degraded-dem", action="store_true",
                    help="proceed with a cold cache / divergent cfg frame, "
                         "or with a DEGRADATION THE ENGINE SWALLOWED (a "
                         "write the shared-repo guard blocked, or a build "
                         "whose layout carries no DEM provenance at all), "
                         "KNOWINGLY (recorded in the env snapshot and in "
                         "<tag>.frame.json).  It authorises NO write.")
    ap.add_argument("--allow-no-sidecar", action="store_true",
                    help="keep a patch whose axes sidecar failed to write; "
                         "it is measurable only in the BARE frame, which "
                         "overcounts and is never a defect count")
    ap.add_argument("--no-ledger", action="store_true",
                    help="skip the run ledger (only for a run whose output "
                         "is a TIME — those must never be ledger-replayed)")
    ap.add_argument("--refresh-data", default="",
                    help="comma-separated scopes this run is AUTHORISED to "
                         "fetch/regenerate into the SHARED data repo "
                         "(locked, hash-stamped, recorded).  'all' "
                         "authorises every scope.  Scopes: "
                         + ", ".join(s for s, _p, _w in REFRESH_SCOPES))
    ap.add_argument("--warm-insets", default="",
                    help="comma-separated ICAOs whose airport elevation "
                         "INSET this run fetches/refreshes before the build "
                         "(an airport build otherwise never reaches the "
                         "fetch: its DEM prep is pure disk state).  Valid "
                         "ONLY with --refresh-data dem, and it warms exactly "
                         "the airports named — the rest of the tile's cache "
                         "is not touched")
    ap.add_argument("--break-stale-lock", action="store_true",
                    help="break a refresh lock whose holder process is gone "
                         "— a dead pid does NOT mean the write completed, "
                         "so inspect the cache first")
    ap.add_argument("--allow-shared-repo-writes", action="store_true",
                    help="DISARM the shared-repo write guard: let the build "
                         "write unauthorised scopes and only report it "
                         "afterwards.  For diagnosing what a build wants to "
                         "write; the corpus every other lane reads changes "
                         "under them if you use it.")
    ap.add_argument("--base-arm", action="store_true",
                    help="this build is a BASE ARM (a reference side, not "
                         "the change under test): serve it from the ARTIFACT "
                         "LEDGER when one was already built at this exact "
                         "code tree, ICAO, O4_* env and CORPUS STAMP, instead "
                         "of rebuilding it.  Implies --from-ledger.  Refused "
                         "for timing runs (--no-ledger) and for --tile.")
    ap.add_argument("--from-ledger", action="store_true",
                    help="serve a stored artifact if the key hits (the "
                         "--base-arm behaviour, on its own)")
    ap.add_argument("--no-artifact-ledger", action="store_true",
                    help="neither serve NOR store the artifact ledger entry "
                         "for this run")
    ap.add_argument("--allow-private-data", action="store_true",
                    help="build against a PRIVATE data corpus instead of "
                         "the shared repo, KNOWINGLY (recorded); its "
                         "numbers are not comparable with any other lane's")
    ap.add_argument("--geometry-only", action="store_true",
                    help="build the plan geometry only "
                         "(compute_elevations=False, the pipeline's own "
                         "documented mode) for VISUAL INSPECTION — never "
                         "a measurement, never censused; the artifact-"
                         "ledger variant key records it")
    ap.add_argument("--solve-capture", type=Path, default=None,
                    metavar="DIR",
                    help="also write a SOLVE-STAGE CAPTURE per airport into "
                         "DIR/<ICAO>/ (perf P2 instrument 1) — the phases 1-4 "
                         "product at the solve boundary, replayable with "
                         "tools/solve_cut.py --replay without rebuilding "
                         "phases 1-4.  The build itself is unchanged")
    args = ap.parse_args(argv)
    if args.geometry_only and args.tile:
        raise SystemExit(
            "REFUSING: --geometry-only with --tile is not wired — "
            "build_tile runs the engine through another entry and the "
            "flag would silently do nothing.  Build the airport directly.")
    if args.geometry_only and args.solve_capture is not None:
        raise SystemExit(
            "REFUSING: --geometry-only never reaches the solve boundary, "
            "so --solve-capture would silently capture nothing.")
    if args.solve_capture is not None and args.tile:
        # A flag that quietly does nothing is how a lane ends up believing
        # it captured something: ``build_tile`` runs the engine through a
        # different entry, so the airport-path arming above never fires.
        raise SystemExit(
            "REFUSING: --solve-capture with --tile is not wired in v1.  "
            "Capture the airport directly (build_airport.py ICAO "
            "--solve-capture DIR), or arm O4_SOLVE_CAPTURE in the "
            "environment of the tile build knowingly — every airport the "
            "tile builds then writes its own DIR/<ICAO>/ capture.")
    all_scopes = {sc for sc, _p, _w in REFRESH_SCOPES}
    requested = set()
    if args.refresh_data:
        requested = ({s.strip() for s in args.refresh_data.split(",")
                      if s.strip()})
        if "all" in requested:
            requested = set(all_scopes)
        unknown = requested - all_scopes
        if unknown:
            raise SystemExit(
                f"REFUSING: unknown --refresh-data scope(s) "
                f"{sorted(unknown)}.  Known scopes: {sorted(all_scopes)}")
    # ── THE ARTIFACT LEDGER'S REFUSALS (BS2) ─────────────────────────
    # Each combination below would turn a served artifact into a claim it
    # cannot support.  They are refused rather than silently ignored: a
    # flag that quietly does nothing is how a lane ends up believing it
    # measured something it did not.
    from_ledger = args.base_arm or args.from_ledger
    if from_ledger and args.no_ledger:
        raise SystemExit(
            "REFUSING: --base-arm/--from-ledger with --no-ledger.  "
            "--no-ledger exists for runs whose OUTPUT IS A TIME, and a "
            "stored artifact has no wall time to give you — replaying one "
            "would report a build that happened on another day as this "
            "run's measurement.  Time a base arm by BUILDING it (single-run "
            "wall times swing +-25 %: tools/check_build_time.py --runs N).")
    if from_ledger and args.tile:
        raise SystemExit(
            "REFUSING: --base-arm/--from-ledger with --tile.  The ledger "
            "stores PATCH builds (patch + sidecar + frame); a tile's product "
            "is a whole scenery pack, and serving a patch in its place would "
            "be a different artifact under the same name.")
    if from_ledger and args.no_artifact_ledger:
        raise SystemExit(
            "REFUSING: --base-arm/--from-ledger with --no-artifact-ledger.  "
            "The second switches OFF the store the first asks to be served "
            "from, so the run would quietly rebuild while reporting that it "
            "was asked for a base arm — a flag that silently does nothing is "
            "how a lane comes to believe it measured something it did not.")
    if from_ledger and args.refresh_data:
        raise SystemExit(
            "REFUSING: --base-arm/--from-ledger with --refresh-data.  A "
            "refresh CHANGES the corpus the key is stamped against, so the "
            "arm you would serve was measured on a corpus this run is about "
            "to replace.  Refresh first, then take the base arm.")

    warm_insets = [icao.strip() for icao in args.warm_insets.split(",")
                   if icao.strip()]
    if warm_insets and "dem" not in requested:
        raise SystemExit(
            f"REFUSING: --warm-insets {warm_insets} FETCHES into the shared "
            f"data repo, which is exactly the act --refresh-data authorises "
            f"(owner ruling e9daef5: downloads are explicit, locked, "
            f"hash-stamped events, never a build side effect).\n"
            f"    --refresh-data dem --warm-insets {','.join(warm_insets)}")

    root = require_build_cwd(Path.cwd())

    # LEDGER WRAP (owner 2026-07-18): correctness runs go through the
    # persistent cross-session ledger, so a build another session already
    # did at this exact tree state + argv + O4_* env is REPORTED, not
    # repeated.  Done by re-exec rather than by asking every caller to
    # remember the prefix — the ledger is not optional discipline.
    # NEVER wrap a run whose OUTPUT IS A TIME: a replay would report a
    # stale number as a measurement.  ``--no-ledger`` is that escape.
    if not args.no_ledger and not os.environ.get("O4_HARNESS_IN_LEDGER"):
        env = dict(os.environ, O4_HARNESS_IN_LEDGER="1")
        label = f"harness-build-{args.tag or args.icao}"
        cmd = [sys.executable, str(root / "tools" / "run_with_ledger.py"),
               "--label", label, "--",
               sys.executable, os.path.abspath(__file__), *sys.argv[1:]]
        return subprocess.run(cmd, env=env, cwd=str(root)).returncode

    if root.resolve() != ROOT.resolve():
        print(f"  [harness] NOTE: cwd tree {root} is not this script's tree "
              f"{ROOT} — the build will use {root}.")
    tag = args.tag or f"{args.icao}_{time.strftime('%Y%m%dT%H%M')}"
    out_dir = Path(args.out)
    prog = Progress(out_dir / f"{tag}.progress")
    prog.note(f"START {tag} argv={' '.join(sys.argv[1:])}")

    cfg_diff = require_cfg_frame(root, allow_degraded=args.allow_degraded_dem)
    if cfg_diff:
        prog.note(f"DEGRADED CFG FRAME (accepted by flag): "
                  f"{sorted(cfg_diff)}")

    # ── ONE SHARED DATA REPO (ruling e9daef5) ────────────────────────
    mounts = data_mounts(root)
    require_shared_data(mounts, allow_private=args.allow_private_data)
    shared_n = sum(1 for m in mounts.values() if m["shared"])
    prog.note(f"data corpus: {shared_n}/{len(mounts)} dir(s) mounted from "
              f"{DATA_REPO}"
              + (f"; PRIVATE: "
                 f"{[n for n, m in mounts.items() if m['present'] and not m['shared']]}"
                 if shared_n != len(mounts) else ""))
    if requested:
        prog.note(f"REFRESH AUTHORISED for scope(s) {sorted(requested)} — "
                  f"this run may write into the SHARED repo, under lock, "
                  f"hash-stamped into {REFRESH_LEDGER}")

    if args.tile:
        lat, lon = args.tile
    else:
        tile = resolve_tile_for(args.icao, root)
        lat, lon = tile if tile else (None, None)

    frame = {"dem_cache_before": None, "requested_constant_dem": args.dem,
             "data_repo": str(DATA_REPO), "data_mounts": mounts,
             "refresh_authorised": sorted(requested)}
    if lat is not None:
        state = dem_cache_state(root, lat, lon)
        frame["dem_cache_before"] = state
        prog.note(f"DEM cache {state['tile_stem']}: base_raster="
                  f"{state['base_raster']} insets={state['airport_insets']} "
                  f"airports_layer={state['airports_layer']} "
                  f"overlay={state['tile_overlay']}")
        if args.dem is None:
            require_dem_frame(state, allow_degraded=args.allow_degraded_dem)
        else:
            prog.note("constant-DEM oracle build: the real DEM frame is "
                      "SUBSTITUTED, so its cache warmth cannot confound "
                      "this run (checked and recorded, not enforced)")
        # A missing artifact is a DOWNLOAD this build would perform as a
        # side effect.  Named and refused unless explicitly authorised.
        require_no_implicit_refresh(
            missing_shared_artifacts(root, lat, lon), requested)
    else:
        prog.note(f"WARNING: could not resolve the anchor tile for "
                  f"{args.icao} — the DEM cache state is UNKNOWN for this "
                  f"run and no elevation from it may be quoted.")

    snapshot = env_snapshot(root, cfg_diff)
    (out_dir / f"{tag}.env.json").write_text(json.dumps(snapshot, indent=1))
    prog.note(f"env snapshot: HEAD={snapshot['git_head'][:9]} "
              f"dirty={snapshot['git_dirty']} "
              f"tree={str(snapshot['code_tree_hash'])[:12]} "
              f"O4_*={sorted(snapshot['o4_env']) or 'NONE'}")

    # ── THE ARTIFACT LEDGER (BS2): the key, then the serve ───────────
    # Computed HERE because every component is known BEFORE any engine code
    # runs — the code tree, the ICAO, the O4_* env, the corpus this build
    # would read and the request variant — and because a served arm must
    # skip the build entirely, guard and redirect included: it writes
    # nothing, so there is nothing to guard.
    ledger_key = ledger_parts = None
    if not args.no_artifact_ledger and not args.tile:
        stamp_frame = dict(frame, dem_frame_effective=frame_surface_keys(root))
        ledger_parts = {
            "tree": snapshot["code_tree_hash"], "icao": args.icao,
            "env": AL.key_env(), "corpus": AL.corpus_stamp(stamp_frame, root),
            "variant": AL.build_variant(
                const_dem=args.dem,
                allow_degraded_dem=args.allow_degraded_dem,
                allow_no_sidecar=args.allow_no_sidecar,
                geometry_only=args.geometry_only)}
        ledger_key = AL.artifact_key(
            ledger_parts["tree"], args.icao, ledger_parts["env"],
            ledger_parts["corpus"], ledger_parts["variant"])
        prog.note(f"artifact-ledger key {ledger_key[:12]} "
                  f"(corpus {ledger_parts['corpus']['sha256'][:12]}, "
                  f"store {AL.store_dir()})")
    if from_ledger and ledger_key:
        record, why = AL.lookup(ledger_key, ledger_parts)
        if record is None:
            prog.note(f"artifact ledger {why} — BUILDING this arm")
        else:
            written = AL.serve(record, out_dir, tag)
            prog.note(AL.provenance_line(record, written))
            served_sha = body_sha256(Path(written["patch"]))
            if served_sha != record.get("body_sha256"):
                raise SystemExit(
                    f"REFUSING: the served patch's body sha256 "
                    f"{served_sha[:16]} is not the {str(record.get('body_sha256'))[:16]} "
                    f"the ledger recorded for this key — the store is not "
                    f"serving what it stored.  Rebuild this arm.")
            (out_dir / f"{tag}.served.json").write_text(json.dumps(
                {"served_from_artifact_ledger": True, "key": ledger_key,
                 "key_parts": ledger_parts, "store": str(AL.store_dir()),
                 "original": {k: record.get(k) for k in
                              ("tag", "lane", "stored_at_iso",
                               "build_seconds", "wall_seconds",
                               "body_sha256", "shapes")},
                 "written": written, "served_at":
                     time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "note": "The patch, sidecar and frame are BYTE-IDENTICAL "
                         "copies of that build's; no engine code ran here, "
                         "so this run has no wall time of its own."},
                indent=1, default=str))
            prog.note(f"EXIT {tag} rc=0 SERVED (no build)")
            print(f"\n  [harness] artifacts in {out_dir}: {tag}.osm"
                  f"(+.axes.json), {tag}.frame.json, {tag}.env.json, "
                  f"{tag}.served.json  — served, not built")
            print(f"  [harness] next: venv/bin/python tools/harness/census.py "
                  f"{out_dir / (tag + '.osm')}")
            return 0

    os.environ.setdefault("O4_LOG_VERBOSITY", "1")   # the sidecar gate

    # LOCK FIRST, then snapshot: a concurrent lane's authorised refresh
    # landing between the two would be attributed to this build.
    locks = [RefreshLock(sc, lane=str(root),
                         break_stale=args.break_stale_lock).acquire()
             for sc in sorted(requested)]
    if locks:
        prog.note(f"holding shared-repo refresh lock(s): "
                  f"{[lk.scope for lk in locks]}")
    before = shared_repo_snapshot()
    prog.note(f"shared-repo snapshot: {len(before)} file(s) across "
              f"{len(SHARED_DATA_DIRS)} data dir(s)")

    guard = SharedRepoWriteGuard(requested, root,
                                 enabled=not args.allow_shared_repo_writes)
    if guard.enabled:
        prog.note(f"shared-repo write GUARD armed: writes outside "
                  f"{sorted(requested) or 'any authorised scope'} are "
                  f"REFUSED at the call, not merely reported afterwards")
    else:
        prog.note("shared-repo write guard DISARMED by flag — writes are "
                  "detected after the fact only (the pre-fix behaviour)")

    # THE WARM, before the build's DEM prep and inside everything that
    # makes a shared-repo write lawful: the scope lock is held, ``before``
    # is snapshotted, and the guard is armed with ``dem`` authorised.  A
    # failure here must not be swallowed into a quietly inset-less build,
    # so it is deliberately outside the try/finally that follows.
    warm_summary = None
    if warm_insets:
        if lat is None:
            raise SystemExit(
                f"REFUSING --warm-insets: the anchor tile for {args.icao} "
                f"did not resolve, so there is no inset cache to warm.")
        with guard:
            warm_summary = warm_airport_insets(warm_insets, root, lat, lon,
                                               prog)

    t0 = time.time()
    try:
        if args.tile:
            # ``build_patch`` redirects the engine's cache roots itself;
            # the tile path never goes through it, so it does it here.
            redirects = redirect_engine_caches(out_dir, tag, prog,
                                               authorised=requested,
                                               tiles=[(lat, lon)],
                                               lane_root=root)
            with guard:                    # build_patch arms its own
                result = build_tile(
                    lat, lon,
                    args.build_dir or str(out_dir / f"tile_{tag}"), prog)
            result["engine_cache_redirects"] = redirects
        else:
            result = build_patch(args.icao, root, out_dir, tag, prog,
                                 const_dem=args.dem,
                                 allow_no_sidecar=args.allow_no_sidecar,
                                 write_guard=guard,
                                 allow_degraded=args.allow_degraded_dem,
                                 solve_capture=args.solve_capture,
                                 geometry_only=args.geometry_only)
        result["wall_seconds"] = round(time.time() - t0, 1)
    finally:
        # The audit runs even when the build raised: a build that died
        # half-way through a download has still mutated the shared repo,
        # and that is precisely when nobody would think to look.
        changes = snapshot_diff(before, shared_repo_snapshot())
        offenders = report_unauthorised_writes(changes, requested, prog)
        for sc in sorted(requested):
            in_scope = {k: [r for r in v if scope_of(r) == sc]
                        for k, v in changes.items()}
            if any(in_scope.values()):
                rec = record_refresh(sc, in_scope,
                                     {"lane": str(root), "tag": tag,
                                      "argv": sys.argv[1:],
                                      # WHAT was warmed, named: a reader
                                      # asking why an inset changed gets
                                      # the airports, not just a flag.
                                      "warm_insets": warm_insets})
                prog.note(f"REFRESH RECORDED [{sc}]: +{rec['added']} "
                          f"~{rec['modified']} file(s), hash-stamped into "
                          f"{REFRESH_LEDGER}")
            else:
                prog.note(f"refresh scope '{sc}' was authorised but wrote "
                          f"NOTHING — the artifact was already present, or "
                          f"the build never reached it")
        for lk in locks:
            lk.release()

    frame["shared_repo_writes"] = changes
    frame["unauthorised_writes"] = offenders
    frame["contaminated"] = bool(offenders)
    frame["write_guard_armed"] = guard.enabled
    frame["write_guard_blocked"] = guard.blocked
    frame["write_guard_lock_churn"] = guard.lock_churn
    frame["write_guard_library_index_churn"] = guard.library_index_churn
    frame["warm_insets"] = warm_summary
    frame["allow_degraded_dem"] = bool(args.allow_degraded_dem)
    frame["dem_frame_effective"] = frame_surface_keys(root)
    frame["synthetic_dem"] = result.get("synthetic_dem")
    frame["dem_inset_provenance"] = result.get("dem_inset_provenance")
    frame["engine_cache_redirects"] = result.get("engine_cache_redirects")
    # WHICH per-tile cfg this build ran on, and where it came from (owner
    # ruling 2026-08-12b: lane inputs are provisioned and RECORDED — the
    # two lanes that hand-seeded two different sources on 2026-08-12 left
    # nothing in either frame to compare).
    frame["tile_cfg_provenance"] = result.get("tile_cfg_provenance")
    frame["dem_cache_after"] = (dem_cache_state(root, lat, lon)
                                if lat is not None else None)
    (out_dir / f"{tag}.frame.json").write_text(json.dumps(frame, indent=1))
    (out_dir / f"{tag}.result.json").write_text(json.dumps(
        {k: v for k, v in result.items() if not k.startswith("_")},
        indent=1, default=str))
    # ── THE ARTIFACT LEDGER: store this arm ──────────────────────────
    # Every successful patch build pays it forward; only a request to serve
    # (--base-arm) ever reads it back, so a plain build is unchanged apart
    # from one copy of its own products.  Two runs are deliberately NOT
    # stored: one that was authorised to refresh (its corpus stamp
    # describes a corpus it then changed) and one the write audit marked
    # CONTAMINATED (serving it later would spread a corpus mutation into
    # every arm that hits the key).
    if ledger_key and not args.tile:
        why_not = ("an authorised --refresh-data run" if requested
                   else "the run was flagged CONTAMINATED" if frame["contaminated"]
                   else None)
        if why_not:
            prog.note(f"artifact ledger: NOT stored — {why_not}")
        else:
            try:
                rec = AL.store_build(
                    ledger_key, ledger_parts,
                    {"patch": result.get("patch"),
                     "sidecar": result.get("sidecar"),
                     "frame": str(out_dir / f"{tag}.frame.json"),
                     "env": str(out_dir / f"{tag}.env.json"),
                     "result": str(out_dir / f"{tag}.result.json")},
                    {"tag": tag, "lane": str(root), "icao": args.icao,
                     "argv": sys.argv[1:],
                     "build_seconds": result.get("build_seconds"),
                     "wall_seconds": result.get("wall_seconds"),
                     "body_sha256": result.get("body_sha256"),
                     "shapes": result.get("shapes")})
                prog.note(f"artifact ledger STORED {ledger_key[:12]} "
                          f"({rec['bytes'] / 1e6:.1f} MB) — a later "
                          f"--base-arm at this tree, env and corpus serves "
                          f"this patch instead of rebuilding it")
            except Exception as exc:                  # never fail a good build
                prog.note(f"artifact ledger: NOT stored ({exc!r})")

    # ``--tile`` does not go through ``build_patch``, so detector 1 runs
    # here for it (detector 2 needs the layout, which a tile build never
    # returns).  AFTER the artifacts on purpose: a tile build's forensics
    # are its step timings and its write audit, and those must survive the
    # refusal — the patch path refuses earlier, before it can leave a
    # DEM-less ``.osm`` where a census would find it.
    if args.tile:
        require_no_swallowed_write_block(
            guard.blocked, allow_degraded=args.allow_degraded_dem, prog=prog)
    prog.note(f"EXIT {tag} rc=0 wall={result['wall_seconds']}s")
    print(f"\n  [harness] artifacts in {out_dir}: {tag}.osm(+.axes.json), "
          f"{tag}.env.json, {tag}.frame.json, {tag}.result.json, "
          f"{tag}.progress")
    print(f"  [harness] next: venv/bin/python tools/harness/census.py "
          f"{out_dir / (tag + '.osm')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
