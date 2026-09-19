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
   tile nobody asked for and exit 0.  And where the globals have nothing
   to give (``default_website`` is excluded from the global config by
   construction, because production supplies the provider per BUILD from
   the app's job), the entry NO LONGER REFUSES: owner ruling
   2026-08-31d makes the per-tile cfg OPTIONAL — the tile runs on the
   user's global settings, the IMAGERY half (steps 3 masks + 4 tile)
   stands down by name, and the GEOMETRY half (steps 1 vector + 2 mesh,
   with the levelled-roads sidecar) builds, because that is the surface
   every lane measures.  ``imagery_capability`` is the ONE place that
   decision is made and ``resolve_tile_frame`` the ONE frame resolver;
   ``tools/run_tile_mesh_only.py`` imports both, so the two tile entries
   cannot provision from two sources or refuse on two conditions.  The
   build's own record says which halves ran (``frame["imagery"]``,
   ``frame["tile_steps_run"]``) and which steps were skipped, with the
   reason (``frame["steps_skipped"]`` — an explicit recorded skip under
   ``run_tile_steps``' step contract, never a silently shorter plan), so
   a geometry-only tile can never read as a full one.  (Before 31d this
   refusal made the SPJC ``-13-078`` tile — an owner acceptance site —
   unbuildable in every lane.)
4. **A tile build with no CIFP.**  ``run_auto_patch_generation`` only calls
   the generator when it can resolve a CIFP directory; the dev config
   ships ``cifp_data_path`` EMPTY, so a whole-tile build there produces a
   tile with NO auto_patch surfaces at all and still exits 0.  ``--tile``
   loads the three X-Plane install paths from the owner's app config and
   aborts before any work if none resolve.
5. **A patch with no sidecar.**  Without it every census silently falls back
   to the context-free frame, so a build that writes none REFUSES (only
   ``allow_no_sidecar`` — a caller's explicit act — proceeds).  The v1
   emitter's contributor probe (``diagnose_missing_sidecar``) went with the
   v1 builder on 2026-09-17: v2's sidecar register is closed by design and
   written by its own emitter, so there is no swallowed contributor to name.

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
* THE SOLVE MODEL IS RETIRED (owner RULINGS 2026-09-13bh): ``solve_model``
  was v1's solver switch and nothing in v2 reads it, so there is no
  ``solve_model`` record in ``<tag>.frame.json`` or ``<tag>.result.json``
  any more.  The artifact-ledger variant key keeps a CONSTANT
  ``solve_model=iterative`` component (:data:`SOLVE_MODEL`) so every arm
  stored before the retirement still keys and is still served.
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
or that the write audit flagged CONTAMINATED is never stored.  The tree
hash and dirty flag are RE-CHECKED at store time (the key was cut at
START, and a worker-pool child that outlives its parent can finish after
source edits land — the 2026-08-28 LEMD poisoned-key precedent): a
mismatch refuses the store loudly, stamps ``contaminated_key`` into the
frame, and never re-keys.

Consolidated from (and replacing): ``tools/full_airport_build.py``,
``scratchpad/integrate/build.sh``, ``scratchpad/refpull_interim/arm.sh``
and ``arm.py``, ``scratchpad/reltiles/run_release_tile.py`` and
``buildtile.sh``.
"""
from __future__ import annotations

import argparse
import dataclasses
import dataclasses as _dc
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: THE AUTO-PATCH ENGINE — a CONSTANT since the owner retired v1 (RULINGS
#: 2026-09-13au).  It keeps the spelling ``--engine v2`` recorded, so a
#: frame.json or an artifact-ledger variant key written before the
#: retirement still reads and still keys the same arm.
ENGINE = "v2"

#: THE SOLVE MODEL — a CONSTANT since the owner retired ``solve_model``
#: (RULINGS 2026-09-13bh): v1's solver switch, which nothing in v2 reads.
#: It survives ONLY as the artifact-ledger variant component, keeping the
#: spelling every stored arm was keyed with, so a control that exists is
#: never rebuilt (BUILD ECONOMY, CLAUDE.md).
SOLVE_MODEL = "iterative"

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
    REFRESH_TS_FORMAT, ledgered_refresh_paths, redirected_scopes,
    record_reconciliation,
    install_snapshot, install_relpath, pack_roots_for_tile,
    LOCK_ARTIFACT_SUFFIX, LOCK_FILE_OPS, is_lock_artifact,
    LIB_INDEX_ARTIFACT_RE, LIB_INDEX_FILE_OPS, is_library_index_artifact,
    SharedRepoWriteBlocked, SharedRepoWriteGuard,
    report_unauthorised_writes, _DEGRADED_OPTIONS,
    require_no_swallowed_write_block, mirror_tree_as_overlay,
    BuildInputScope, contaminating_writes, tiles_named_in, airports_named_in,
    tile_input_scope, mod_cache_pack_of, mod_cache_packs_naming,
    require_no_unauthorised_writes,
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


#: Frame keys that became a str enum on 2026-09-18 (RULINGS 18c/18e) and
#: whose LEGACY scalar must compare equal to its mode: a lane cfg still
#: saying ``airport_elevation_insets=True`` against an app cfg saying
#: ``ICAO`` is the SAME frame, not a divergence refusal (spec §A.5 row 27).
MODE_VALUED_FRAME_KEYS = ("airport_elevation_insets",)


def _normalized_frame_value(key: str, value):
    if key not in MODE_VALUED_FRAME_KEYS or value is None:
        return value
    try:
        from auto_patch.selection import normalize_mode

        return normalize_mode(value, key)
    except Exception:
        return value


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
    return _normalized_frame_value(key, mine)


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
        thine = _normalized_frame_value(k, theirs.get(k))
        if mine != thine:
            out[k] = (mine, thine)
    return out


def neighbour_cells_of(tile) -> list:
    """The cold-neighbour cells this tile's CLASS-S airports would need.

    Read through the engine's own selector, so the harness asks exactly
    the question the build asks (spec §C.3: one function, one apt.dat).
    """
    import O4_Vector_Map as VMAP

    VMAP.derive_auto_patch_selection(tile)
    return list(getattr(tile, "boundary_neighbours", ()) or ())


def inset_selection_record(root, icao, owner_cfg=OWNER_APP_CFG) -> dict:
    """``{"mode": ..., "admitted": ...}`` for the airport being built."""
    mode = _normalized_frame_value(
        "airport_elevation_insets",
        frame_surface_keys(root, owner_cfg).get("airport_elevation_insets"))
    try:
        from auto_patch.selection import mode_admits

        admitted = bool(mode_admits(str(icao).upper(), mode or "ICAO"))
    except Exception:
        admitted = None
    return {"mode": mode, "admitted": admitted}


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

    ITS KEY SET IS FROZEN.  This dict is hashed WHOLE into the artifact
    ledger's corpus stamp (``artifact_ledger.corpus_stamp``:
    ``"dem_cache": _sha_of(cache)``), so ADDING A KEY HERE RE-KEYS EVERY
    STORED ARM and rebuilds controls that already exist.  The
    per-airport inset verdict therefore does NOT live here — it is
    derived beside this call and travels in its own frame key
    (:func:`this_airports_inset_problem`).
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


def require_dem_frame(state: dict, *, allow_degraded: bool = False,
                     requested=(), inset_problem=None) -> None:
    """The zero-DEM and cold-cache refusals.

    * NO base raster ⇒ the loader either downloads mid-measurement or hands
      back an ALL-ZERO surface; a whole build then "succeeds" while grading
      every shape toward a zero-elevation world (KCLT's end-around taxiway
      measured 85 m below the runway end before the mechanism was found).
    * NO cached airports layer ⇒ no smoothing masks, so the surface stays
      unsmoothed and diverges from production.
    * NO cached insets ⇒ the base surface only, when production insets here.

    AN AUTHORISED REFRESH OF THE NAMING SCOPE IS NOT A REFUSAL (measured
    2026-09-15: ``build_airport.py KDFW --tile 32 -97 --refresh-data
    osm_layers,dem`` — the neighbour tile KDFW's pack reaches into — was
    refused HERE, before any refresh could run, naming the very two
    scopes the command had authorised).  Each problem carries the scope
    that fixes it; when that scope is authorised the problem is NAMED as
    something this run will DERIVE, the run proceeds to the derivation
    (:func:`refresh_stale_osm_layers`, :func:`refresh_tile_dem`) and the
    frame is RE-JUDGED afterwards with nothing authorised — so a refresh
    that failed to warm the frame still refuses, just later and with the
    reason known.
    """
    requested = set(requested or ())
    problems, deferred = [], []
    def _name(scope, text):
        (deferred if scope in requested else problems).append((scope, text))
    if not state["base_raster"]:
        _name("dem",
            f"NO base raster for {state['tile_stem']} in Elevation_data — "
            f"the DEM loader would DOWNLOAD it mid-measurement (a "
            f"shared-repo write as a build side effect, which owner ruling "
            f"e9daef5 forbids) or hand back an ALL-ZERO surface.  "
            f"Deliberate fetch: --refresh-data dem")
    if not state["airports_layer"]:
        _name("osm_layers",
            f"NO cached airports OSM layer for tile "
            f"{state['tile'][0]:+d}{state['tile'][1]:+d} — airport smoothing "
            f"masks are unavailable and the surface stays UNSMOOTHED "
            f"(production smooths at apt_smoothing_pix=8), and the build "
            f"would run an overpass QUERY to fill it.  Deliberate fetch: "
            f"--refresh-data osm_layers")
    if not state["airport_insets"]:
        _name("dem",
            f"NO cached airport elevation insets for {state['tile_stem']} — "
            f"the build would grade against the BASE surface while "
            f"production grades against the inset-baked one.  Deliberate "
            f"fetch: --refresh-data dem  (or "
            f"tools/fetch_airport_elevation_insets.py, which writes the "
            f"same shared cache).")
    elif inset_problem:
        # THE PER-AIRPORT COLD FRAME (session ruling 2026-09-17 (3)): the
        # directory is there but THIS airport's inset is missing, or was
        # cut for a box that no longer contains what it needs.  Building
        # anyway grades on the base surface where the inset should have
        # been — the same silent degradation the whole-tile miss above
        # refuses — so it is named here too, and ``--allow-degraded-dem``
        # accepts it KNOWINGLY, authorising no write.
        _name("dem", inset_problem[1])
    for scope, text in deferred:
        print(f"  [harness] COLD, and this run's --refresh-data {scope} "
              f"DERIVES it before the build (re-judged afterwards): {text}")
    if problems and not allow_degraded:
        raise SystemExit(
            "REFUSING: the DEM frame is COLD, and a cold frame degrades "
            "SILENTLY (log line only) into a different surface:\n  - "
            + "\n  - ".join(t for _s, t in problems)
            + "\nWarm the cache, or pass --allow-degraded-dem to measure in "
              "the degraded frame KNOWINGLY (it is recorded either way).  "
              "Never quote a DEM elevation from a degraded frame.")
    for _s, p in problems:
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


def missing_shared_artifacts(root, lat, lon, icao=None, state=None,
                             inset_problem=None) -> list:
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
    # ``state`` and ``inset_problem`` are passed in by the CLI so the
    # per-airport check — which parses the cached airports layer — runs
    # ONCE per build.  Called without them, this derives both itself.
    if state is None:
        state = dem_cache_state(root, lat, lon)
    if inset_problem is None and icao:
        inset_problem = this_airports_inset_problem(state, lat, lon, icao)
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
    out.extend(unverified_inset_negatives(state, lat, lon))
    if inset_problem is not None:
        (kind, text) = inset_problem
        out.append(("dem",
                    f"Elevation_data/**/{state['tile_stem']}_airport_insets/"
                    f"{icao}_*.tif [{kind}]", text))
    out.extend(schema_stale_osm_layers(root, lat, lon))
    out.extend(missing_pack_dsf_dumps(root, lat, lon, icao))
    return out


def this_airports_inset_problem(state, lat, lon, icao):
    """THE PER-AIRPORT INSET REFUSAL (session ruling 2026-09-17 (3)).

    A present ``_airport_insets`` directory says nothing about whether
    THIS airport has an inset in it, or whether the one there was cut for
    a box that still contains what the airport needs today.  Until now
    the frame check tested only ``os.path.isdir``, so a MISSING or STALE
    inset for the airport being built read as a warm frame — and the
    build then either graded on the base surface or RE-CUT the inset
    mid-measurement, which is a shared-repo write as a build side effect
    (ruling e9daef5 forbids it).

    THE RE-CUT RULE is the engine's own — required today not contained in
    the box REQUESTED at cut time
    (``O4_Airport_Elevation_Insets.airport_inset_frame_problem``,
    imported and never copied, the same function
    ``dem_production.frame_state`` calls).  The APP re-cuts such an inset
    automatically (owner 2026-09-17 (2)); the harness REFUSES and names
    the inset, both boxes and ``--refresh-data dem``.
    ``--allow-degraded-dem`` covers it like the rest and authorises NO
    write.

    Measured over the whole corpus 2026-09-17
    (``tools/inset_coverage_census.py``): 215 of 565 rasters are stale by
    this rule, and NONE of them belongs to a battery airport.
    """
    if not state["airport_insets"] or not icao:
        return None         # the whole-tile miss is already named above
    if not state["airports_layer"]:
        # The required box comes from the cached airports layer; with no
        # layer the build is already refused for it, and asking here
        # would run an overpass QUERY.
        return None
    try:
        import O4_Airport_Elevation_Insets as INSETS
        import O4_Config_Utils as CFG
        import O4_OSM_Utils as OSM
        import O4_Vector_Map as VMAP
        tile = CFG.Tile(lat, lon, "")
        tile.read_from_config()
        layer = OSM.OSM_layer()
        OSM.OSM_queries_to_OSM_layer(VMAP.AIRPORTS_QUERIES, layer, lat, lon,
                                     ["all"], cached_suffix="airports")
        dico = VMAP.build_airports_dico(tile, layer)
        boxes = INSETS._airport_bounding_boxes(tile, dico)
        required = next((box for key, box in boxes.items()
                         if str(key).upper() == str(icao).upper()), None)
        if required is None:
            return None     # no boundary for it: nothing is required
        return INSETS.airport_inset_frame_problem(lat, lon, icao, required)
    except Exception as exc:
        print(f"  [harness] per-airport inset check skipped ({exc!r})")
        return None


def missing_pack_dsf_dumps(root, lat, lon, icao) -> list:
    """THE PACK DSF TEXT-DUMP REFUSAL (RULINGS 2026-09-15ar).

    v2's read frame is the serving pack's PRISTINE tile DSF
    (``airport/dsf_write.pristine_dsf_path`` — the ``.dsf.anchor_bak``
    once the object stage has written the pack, RULINGS 2026-09-11m), and
    the loader reads it through a DSFTool ``--dsf2text`` dump cached in
    ``Airport_mod_cache/<pack>/<dsf>.<sha8>.text``.  The tag is the DSF's
    own CONTENT hash, so the moment the pack's DSF changes — the owner
    rebakes it, the object stage rewrites it — EVERY cached dump stops
    matching and the build makes a new one.

    That dump is written by a SUBPROCESS, which no Python-level write
    guard can intercept: the harness's only defence at the write is the
    lane-local ``O4_AIRPORT_MOD_CACHE_DIR`` redirect the subprocess
    inherits.  So the pre-build check is the honest one — if no dump for
    this exact DSF exists in EITHER the shared corpus or the lane-local
    overlay this run will use, the build is going to run DSFTool, and
    that is a cache regeneration, not a build side effect (ruling
    e9daef5).  Named under ``airport_mod_cache``, refused up front.

    BOTH ROOTS are asked, because the answer is "will a dump be made",
    not "is the corpus warm": ``redirect_engine_caches`` seeds the
    lane-local overlay copy-on-write FROM the shared corpus, so a dump
    present in either one is a dump the build will find.

    The predicates are the ENGINE's own — ``airport/dsf.find_text_dump``
    (the 11m naming rule, freshness and the live/pristine split),
    ``dsf_write.pristine_dsf_path``, ``airport/pack.select_pack`` and
    ``dsf.text_dump_tag`` — imported, never copied.

    ONE LIMIT, stated: only the NAMED airport's serving pack is judged.
    A ``--tile`` build's object stage reaches every pack covering the
    tile, and enumerating those needs the build's own worklist; ``icao``
    is ``None`` there and this check stands down rather than guess.
    """
    if not icao:
        return []
    for p in (Path(root) / "src", Path(root), Path(root) / "tests"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    try:
        import O4_File_Names as FNAMES
        from auto_patch_v2.airport import dsf as _dsf
        from auto_patch_v2.airport.dsf_write import pristine_dsf_path
        from auto_patch_v2.airport.pack import select_pack

        xplane_root = os.environ.get("XPLANE_ROOT") or _owner_xplane_root()
        sel = select_pack(xplane_root, icao)
        if sel is None:
            return []
        dsf_path = pristine_dsf_path(
            _dsf.dsf_path_in_pack(sel.root, int(lat), int(lon)))
        if not os.path.isfile(dsf_path):
            return []
        roots = [FNAMES.airport_mod_cache_root(),
                 str(lane_cache_root(root) / "Airport_mod_cache")]
        for mod_root in roots:
            if _dsf.find_text_dump(mod_root, sel.name, int(lat), int(lon),
                                   dsf_path=dsf_path):
                return []
        tag = _dsf.text_dump_tag(dsf_path)
    except Exception as exc:
        print(f"  [harness] pack DSF dump check skipped ({exc!r})")
        return []
    return [("airport_mod_cache",
             f"Airport_mod_cache/{sel.name}/"
             f"{os.path.basename(dsf_path)}.{tag}.text",
             f"the pack's DSF sha ({tag}) has NO cached text dump in the "
             f"shared corpus or this lane's overlay — the build would run "
             f"DSFTool --dsf2text and cache the result, a cache "
             f"regeneration and NEVER a build side effect (ruling "
             f"e9daef5).  The pack's DSF changed under the cache (the "
             f"owner rebaked it, or an object stage rewrote it), which is "
             f"exactly what happened to the VHHH pack on 2026-09-15 "
             f"(RULINGS 2026-09-15ar).  A DSFTool dump is a SUBPROCESS "
             f"write, so no Python guard can refuse it at the call")]


def xplane_install_roots() -> tuple:
    """The X-Plane install(s) this harness process could write.

    Handed to :class:`SharedRepoWriteGuard` so a write into the owner's
    install REFUSES at the call under scope ``pack_rebake`` (RULINGS
    2026-09-15av).  An explicit root, never a name-substring test: a
    fixture install under ``tmp_path`` must stay writable, and the
    suite's own install guard (``tests/conftest.py``) pins its root the
    same way.  Empty when the root cannot be resolved — the guard then
    defends the data repo only, which is the pre-2026-09-15 behaviour.
    """
    try:
        root = _owner_xplane_root()
    except Exception as exc:
        print(f"  [harness] X-Plane install guard root unresolved ({exc!r}) "
              f"— the install is NOT defended by the write guard this run")
        return ()
    return (root,) if root else ()


def _owner_xplane_root() -> str:
    """The install the harness builds against — the cfg's own answer,
    through the same read ``planar.__main__.default_inputs`` uses."""
    import O4_Config_Utils                                    # noqa: F401
    from auto_patch_v2.planar.__main__ import _cfg_value
    custom = _cfg_value("custom_scenery_dir")
    return (os.path.dirname(custom.rstrip("/")) if custom
            else os.path.expanduser("~/X-Plane 12"))


def _stamped_cache_schema(path) -> str:
    """The ``o4_tag_schema`` value stamped on a cached layer, or ``""``.

    MESSAGE ONLY — the PREDICATE is the engine's own
    (``O4_OSM_Utils._cached_osm_schema_matches``, imported never copied);
    this just reads the marker back so the refusal can say WHICH schema
    the cache on disk was written under instead of only which one the
    engine now wants.  Same two-line header read the engine does.
    """
    import bz2
    import re
    try:
        if str(path).endswith(".bz2"):
            handle = bz2.open(str(path), "rt", encoding="utf-8")
        else:
            handle = open(str(path), "r", encoding="utf-8")
        with handle:
            head = handle.readline() + handle.readline()
    except (OSError, UnicodeDecodeError):
        return ""
    found = re.search(r'o4_tag_schema="([^"]*)"', head)
    return found.group(1) if found else ""


def superseded_road_feeds(root, lat, lon) -> list:
    """The road feeds THE v2 LOADER would refuse, named before the build.

    THE MEASURED DEFECT (2026-09-15).  ``build_airport.py KDFW
    --refresh-data osm_layers`` re-derived ``+32-098_big_roads``
    (ledgered) and then DIED 54 s in, inside
    ``auto_patch_v2/airport/load.py``: "KDFW: 1 cached road feed(s) were
    written under a SUPERSEDED tag whitelist … +30-100/+33-098/
    +33-098_big_roads.osm.bz2 (o4_tag_schema 2026-07-16)".  A NEIGHBOUR
    TILE — and :func:`schema_stale_osm_layers` judged the build's own
    tile only, a limit its docstring stated and this closes.  The loader
    merges the 3x3 neighbourhood (``airport/osm.load_feed``), so the
    pre-flight must judge the same square, or a refusal the loader will
    raise is paid for with a whole build.

    EVERYTHING HERE IS THE LOADER'S OWN — ``ROAD_FEEDS`` (which feeds
    carry a whitelist), ``feed_path`` (where each lives, ``.osm.bz2``
    then ``.osm``), ``feed_tag_schema`` (the root-tag read) and
    ``ROAD_CACHE_TAG_SCHEMA`` (the version it wants).  Imported, never
    copied: a second spelling would refuse a different set than the
    loader raises on, which is worse than not checking.

    AN UNTAGGED FEED IS NAMED TOO, since RULINGS 2026-09-17t: the loader
    RAISES on a feed carrying no ``o4_tag_schema`` at all ("the same fact
    on weaker evidence"), and since 2026-09-17ad ``O4_Vector_Map.
    _airport_auto_roads_layer`` stamps the ``airport_small_roads`` cache
    it writes, so an unstamped one is a pre-fix leftover the refresh can
    clear — not the permanent state of the corpus this exemption was
    written for.  Leaving it unnamed meant the pre-flight passed and the
    loader then refused mid-build, which is the KDFW shape again.
    """
    for p in (Path(root) / "src", Path(root)):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    try:
        from auto_patch_v2.airport import osm as _v2osm
    except Exception as exc:
        print(f"  [harness] road-feed schema check skipped ({exc!r})")
        return []
    osm_root = str(Path(root) / "OSM_data")
    out = []
    for dlat in (-1, 0, 1):
        for dlon in (-1, 0, 1):
            tlat, tlon = int(lat) + dlat, int(lon) + dlon
            for feed in _v2osm.ROAD_FEEDS:
                path = _v2osm.feed_path(osm_root, tlat, tlon, feed)
                if not os.path.isfile(path):
                    continue
                schema = _v2osm.feed_tag_schema(path)
                if schema == _v2osm.ROAD_CACHE_TAG_SCHEMA:
                    continue
                schema = schema if schema is not None else "<none at all>"
                try:
                    artifact = "OSM_data/" + str(Path(path).resolve()
                                                 .relative_to(Path(osm_root)
                                                              .resolve()))
                except (OSError, ValueError):
                    artifact = path
                out.append((
                    "osm_layers", artifact,
                    f"the v2 LOADER refuses this feed: written under "
                    f"o4_tag_schema {schema}, it wants "
                    f"{_v2osm.ROAD_CACHE_TAG_SCHEMA} — the structure "
                    f"readers would silently see fewer bores (OTHH: 8 "
                    f"against 16, RULINGS 2026-09-15ar).  It is on tile "
                    f"{tlat:+d}{tlon:+d}, which this build READS: the "
                    f"loader merges the 3x3 neighbourhood.  Measured "
                    f"2026-09-15: KDFW died 54 s in on exactly this"))
    return out


def schema_stale_osm_layers(root, lat, lon) -> list:
    """THE SCHEMA-STALE CACHED LAYER REFUSAL (RULINGS 2026-09-15r + u).

    A cached OSM layer carries the tag schema it was downloaded under
    (``o4_tag_schema`` on the ``<osm`` root).  When the engine's schema
    constant moves — ``O4_Vector_Map.ROAD_CACHE_TAG_SCHEMA`` "2026-07-16"
    → "2026-09-15" for the four depth witnesses (RULINGS 2026-09-15r) —
    every cache written under the old one stops matching, and the tile
    build's background prefetch (``O4_Vector_Map.
    start_background_osm_prefetch``, which filters the layer
    specifications through exactly this predicate) RE-DOWNLOADS it and
    rewrites the shared cache MID-BUILD.  Measured: the first guarded
    build after that merge rewrote
    ``OSM_data/+40-010/+40-004/+40-004_big_roads.osm.bz2``
    (2,197,226 → 2,199,670 bytes) at 2026-09-15 09:03 and the run was
    marked CONTAMINATED after the fact (RULINGS 2026-09-15u) — the KCLT
    2026-08-05 road-feed precedent's exact shape.

    Under ruling e9daef5 that is a REFRESH, not a build side effect, so
    it is named and refused BEFORE the build, with ``--refresh-data
    osm_layers``.  An airport build never starts that prefetch, but it
    READS the same caches through ``auto_patch.osm_load.
    _load_osm_road_layer``: a stale one is missing every witness the new
    schema added (``layer`` / ``cutting`` / ``covered`` / ``embankment``,
    which ``bridges`` and ``pavement_classification`` now read), so it is
    a degraded measurement frame either way and both paths refuse.

    The layer list is the ENGINE's own
    (``O4_Vector_Map.osm_layer_warm_specifications`` — the same 5-tuples
    the prefetch filters, so the road_level gating cannot drift from it)
    and the staleness predicate is the engine's own
    (``O4_OSM_Utils._cached_osm_schema_matches``).  Nothing here is a copy.

    TWO LIMITS, stated:

    * Only the BUILD'S OWN tile is judged.  That is the only tile whose
      caches the prefetch would rewrite; a road read spans the 3x3
      neighbourhood, so a NEIGHBOUR tile's stale cache still degrades the
      read silently.  Widening the net would refuse until nine tiles are
      refreshed — an owner call, not a harness one.
    * The auto-mode merged ``airport_small_roads`` cache is NOT judged:
      it carries no schema at all (``O4_Vector_Map.py`` ~:768 recycles on
      ``isfile`` alone and ``write_to_file`` stamps nothing there), so it
      is never re-downloaded — and judging it against the road schema
      would refuse every build that has one.  That missing gate is the
      chip RULINGS 2026-09-15r already names.

    An ABSENT cache is deliberately not named here: absence is the
    caller's business above (the airports layer) and lawful for the rest.
    """
    for p in (Path(root) / "src", Path(root)):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    try:
        import O4_Config_Utils as CFG
        import O4_File_Names as FNAMES
        import O4_OSM_Utils as OSM
        import O4_Vector_Map as VMAP

        tile = CFG.Tile(int(lat), int(lon), "")
        try:
            tile.read_from_config()
        except Exception:
            pass
        specifications = VMAP.osm_layer_warm_specifications(tile)
    except Exception as exc:
        print(f"  [harness] OSM layer-schema check skipped ({exc!r})")
        return []
    out = list(superseded_road_feeds(root, lat, lon))
    named = {a for _s, a, _w in out}
    for specification in specifications:
        cached_suffix, cache_schema = specification[0], specification[4]
        if not cache_schema:
            continue            # stamps nothing, so nothing can be stale
        path = FNAMES.osm_cached(int(lat), int(lon), cached_suffix)
        if not os.path.isfile(path):
            continue
        if OSM._cached_osm_schema_matches(path, cache_schema):
            continue
        try:
            artifact = "OSM_data/" + str(
                Path(path).resolve().relative_to(
                    (Path(root) / "OSM_data").resolve()))
        except (OSError, ValueError):
            artifact = path
        stamped = _stamped_cache_schema(path)
        if artifact in named:
            continue                    # already named by the reader's own
        out.append((
            "osm_layers", artifact,
            f"the cached {cached_suffix} layer is SCHEMA-STALE — written "
            f"under {stamped or '<no schema marker>'}, the engine expects "
            f"{cache_schema}.  A tile build's background OSM prefetch "
            f"re-downloads it and REWRITES this shared file mid-build "
            f"(measured 2026-09-15 on +40-004_big_roads, RULINGS "
            f"2026-09-15u); an airport build reads it as-is and every tag "
            f"the new schema added is simply absent.  Re-cutting it is a "
            f"REFRESH, not a build side effect"))
    return out


def unverified_inset_negatives(state, lat, lon) -> list:
    """The DEGRADED-TIER refusal (owner RULINGS 2026-09-13b (2)) and the
    ONCE-PER-VERSION re-probe refusal (owner RULINGS 2026-09-15aq (4)).

    Two doors, one refusal: both name a ``no-coverage`` record the next
    pass would RE-PROBE, and a re-probe fetches into the shared data
    repo.  13b's covers a CAPABILITY-GATED provider whose record carries
    no capability stamp; 15aq's covers a CAPABILITY-FREE provider whose
    record carries another engine's version.

    A ``no-coverage`` in the inset index recorded for a CAPABILITY-GATED
    provider by a run that did not record its capabilities is UNVERIFIED:
    1.0.324's packaged engine could not decode LERC at all, returned an
    empty asset list, and the orchestration wrote "NEWZEALAND1M has no
    coverage at NZQN" — so NZQN's inset has been cut from 30 m
    COPERNICUS ever since, while 1 m LiDAR sat behind a permanent
    negative.  The engine now RE-PROBES such a record once.

    That re-probe fetches and re-cuts, which is a write into the shared
    data repo — and a build never makes one as a side effect (ruling
    e9daef5).  So a harness build REFUSES up front, names the airport and
    the provider, and names ``--refresh-data dem``.  The app's own build
    path takes the re-probe (it is the owner's machine and his data);
    the harness does not.

    The predicate is the ENGINE's own
    (``O4_Airport_Elevation_Insets.unverified_capability_negatives``) —
    imported, never copied.
    """
    if not state["airport_insets"]:
        return []           # already refused above, for the whole cache
    try:
        import O4_Airport_Elevation_Insets as INSETS
        unverified = INSETS.unverified_capability_negatives(lat, lon)
        version_stale = INSETS.version_stale_capability_free_negatives(
            lat, lon)
        running = INSETS.engine_version()
    except Exception as exc:
        print(f"  [harness] unverified-inset check skipped ({exc!r})")
        return []
    out = []
    for (icao, code, recorded) in version_stale:
        # THE ONCE-PER-VERSION RE-PROBE (owner RULINGS 2026-09-15aq (4)).
        # ``code`` declares NO required capability, so 13b's door below
        # cannot reach it; its negative would be permanent.  The TNM
        # outage of 2026-09-15 wrote 20 such false negatives across the
        # two Phoenix tiles (RULINGS 2026-09-15q).  Each engine version
        # re-asks once — which FETCHES into the shared repo, so the
        # harness refuses up front and names the flag.  The APP's own
        # build path takes the re-probe; the harness never does.
        out.append(("dem",
                    f"Elevation_data/**/{state['tile_stem']}_airport_insets/"
                    f"index.json [{icao}:{code}]",
                    f"a no-coverage negative for {code} recorded by engine "
                    f"{recorded or 'an unrecorded version'} — this engine is "
                    f"{running}, and a capability-free provider's negative "
                    f"is RE-ASKED once per version (a TNM 200 error envelope "
                    f"minted 20 false ones on the Phoenix tiles on "
                    f"2026-09-15), so the build would re-probe {code} and "
                    f"re-cut the inset mid-build"))
    for (icao, code, capabilities) in unverified:
        out.append(("dem",
                    f"Elevation_data/**/{state['tile_stem']}_airport_insets/"
                    f"index.json [{icao}:{code}]",
                    f"a no-coverage negative for {code} recorded with NO "
                    f"capability record — the run that wrote it may have "
                    f"lacked {'/'.join(capabilities).upper()} (1.0.324 did, "
                    f"and minted exactly this negative for NEWZEALAND1M at "
                    f"NZQN), so THE INSET HERE IS CUT AT A DEGRADED TIER; "
                    f"the build would re-probe {code} and re-cut the inset "
                    f"mid-build"))
    return out


def bathymetry_band_admission(tile, root, dsf_step_runs: bool) -> list:
    """The bathymetry band's entry in the missing-artifact list, for a
    TILE build — ``(scope, artifact, why)`` triples like
    :func:`missing_shared_artifacts`, empty when the band is settled.

    The band lives in the shared repo under scope ``dem``
    (``Elevation_data/**/<tile>_bathymetry_band/``: cells, the
    ``index.json`` fetch-admission stamp, the mosaic VRTs) and a tile
    build reaches it THREE times — the step-1 prefetch and the step-3
    masks under the masks gating (``masks_use_DEM_too``), and step 4's
    DSF ``sea_level`` raster under the all-provider gating.  A band that
    would fetch a cell, learn a negative or rebuild a mosaic is a
    shared-repo write mid-build; measured 2026-09-04 on +25+051 the
    write guard refused it in step 3, AFTER the vector and mesh steps
    had been paid for.  The admission predicate is the engine's own
    (``O4_Bathymetry_Band.is_cached`` — imported, never copied), judged
    for exactly the gatings the steps will use, so a cold band refuses
    up front naming ``--refresh-data dem``.

    Needs the resolved tile frame (its cfg keys decide the gating), so
    it runs at the earliest point that frame exists — inside
    ``build_tile`` before step 1 — not in ``main``'s filesystem-only
    pre-flight.  ``--allow-degraded-dem`` does not apply: this is a
    would-write refusal, and that flag authorises no write.
    """
    import O4_Bathymetry_Band as BATHYBAND
    import O4_File_Names as FNAMES

    band_dir = FNAMES.bathymetry_band_directory(tile.lat, tile.lon)
    try:
        artifact = str(Path(band_dir).resolve().relative_to(
            Path(root).resolve() / "Elevation_data"))
        artifact = f"Elevation_data/{artifact}/"
    except ValueError:
        artifact = band_dir
    out = []
    masks_setting = str(getattr(tile, "masks_use_DEM_too", "False"))
    if not BATHYBAND.is_cached(tile):
        out.append(("dem", artifact,
                    f"the coastal bathymetry band under the MASKS gating "
                    f"(masks_use_DEM_too={masks_setting}) — the step-1 "
                    f"prefetch / step-3 masks would fetch cells, record "
                    f"negatives or rebuild the mosaic mid-build"))
    if dsf_step_runs:
        # Mirror of ``O4_DSF_Utils.elevation_and_bathymetry_data``'s
        # dispatch: the band is consulted for dsf_bathymetry=True, and
        # for auto exactly when no Global Scenery donor DSF is installed.
        setting = str(getattr(tile, "dsf_bathymetry", "auto"))
        wanted = setting == "True"
        if setting == "auto":
            try:
                import O4_DSF_Utils as DSF
                wanted = not DSF._global_scenery_donor_exists(
                    tile.lat, tile.lon)
            except Exception as exc:
                print(f"  [harness] bathymetry admission: donor check "
                      f"failed ({exc!r}); judging the DSF gating anyway")
                wanted = True
        if wanted and not BATHYBAND.is_cached(tile, False, False):
            out.append(("dem", artifact,
                        f"the coastal bathymetry band under the DSF "
                        f"sea_level gating (dsf_bathymetry={setting}, all "
                        f"providers, whole shoreline) — step 4 would fetch "
                        f"cells, record negatives or rebuild the mosaic"))
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
# THE AUTHORISED OSM-LAYER REFRESH (--refresh-data osm_layers)
# ══════════════════════════════════════════════════════════════════════

def _tile_of_osm_path(path):
    """``(lat, lon)`` from an ``OSM_data/<block>/<tile>/<tile>_<feed>``
    path — the tile DIRECTORY name, which is how the corpus is laid out
    (``O4_File_Names.short_latlon``).  ``None`` when it does not parse."""
    name = Path(path).parent.name
    try:
        if len(name) != 7 or name[0] not in "+-" or name[3] not in "+-":
            return None
        return int(name[:3]), int(name[3:])
    except ValueError:
        return None


def refresh_stale_osm_layers(root, lat, lon, prog) -> dict:
    """Re-derive the SCHEMA-STALE layers :func:`schema_stale_osm_layers`
    names, under the authorisation the caller already holds.

    THE GAP THIS CLOSES (measured 2026-09-15, VMMC): ``build_airport.py
    VMMC --refresh-data osm_layers`` exited 0 in 23 s, printed "refresh
    AUTHORISED (osm_layers): …+22+113_big_roads.osm.bz2", then "refresh
    scope 'osm_layers' was authorised but wrote NOTHING — the artifact
    was already present", and the next plain build REFUSED on the same
    file.  Authorising a refresh was a no-op, because nothing in the run
    actually re-derived a PRESENT-but-stale layer: the airport path never
    starts the background prefetch at all, and where the prefetch does
    run it would have rewritten the file MID-BUILD, which is the
    contamination this whole mechanism exists to stop.  So the refresh
    gets its own derivation site, here — before the build, inside the
    scope lock, the snapshot and the armed guard, exactly like
    :func:`warm_airport_insets`.

    MOVE ASIDE, NOT DELETE, and put back on failure.  The stale file is
    renamed to ``<name>.stale-<schema>`` in its own directory, the engine
    re-derives, and then: the aside copy is removed if a schema-current
    layer came back, or renamed BACK if it did not.  Deleting outright
    would trade a stale corpus for an ABSENT one the moment a download
    fails (and this runs against Overpass), which is strictly worse —
    every later build would then refuse for a missing artifact instead of
    a stale one, with the bytes gone.  Nothing is left behind either way,
    so the corpus never accumulates ``.stale-*`` litter.

    THE DERIVATION IS THE ENGINE'S OWN.  ``O4_Vector_Map.
    start_background_osm_prefetch`` + ``wait_for_background_osm_prefetch``
    — the same pair the tile prelude
    (``prepare_tile_airports_and_dem``) calls, filtering the same
    specification 5-tuples through the same ``_layer_cache_is_current``
    predicate.  With the stale file moved aside the filter sees it
    absent and downloads it.  No copy of the download loop lives here.
    Consequence, stated: that pass also fetches any OTHER layer of this
    tile the specifications name and the corpus lacks (coastline, water)
    — lawful under the authorised scope, guarded, and hash-stamped into
    the refresh ledger with everything else.

    Returns a summary for the frame record.  Raises ``SystemExit`` when a
    layer did not come back schema-current — a refresh that silently
    achieved nothing is the defect this function was written for, and it
    must never exit 0 twice in a row.
    """
    import O4_Config_Utils as CFG                          # noqa: E402
    import O4_File_Names as FNAMES                         # noqa: E402
    import O4_OSM_Utils as OSM                             # noqa: E402
    import O4_Vector_Map as VMAP                           # noqa: E402

    stale = schema_stale_osm_layers(root, lat, lon)
    # AN ABSENT LAYER IS DERIVED TOO (2026-09-15, the cold KDFW neighbour
    # +32-097: `--refresh-data osm_layers,dem` could not warm it, because
    # only STALE layers were ever derived).  The engine's own prefetch
    # filter is "absent OR stale" already; what was missing was a REASON
    # to run it, so an absent airports layer is one.
    state = dem_cache_state(root, lat, lon)
    cold_airports = not state["airports_layer"]
    if not stale and not cold_airports:
        prog.note("refresh osm_layers: no schema-stale and no absent "
                  f"cached layer on tile {lat:+d}{lon:+d} or its 3x3 "
                  f"neighbourhood — nothing to re-derive")
        return {"tile": [int(lat), int(lon)], "layers": [], "refetched": []}

    aside = []
    for _scope, artifact, _why in stale:
        path = Path(root) / artifact
        target = Path(str(path) + ".stale-"
                      + (_stamped_cache_schema(path) or "unstamped"))
        os.replace(str(path), str(target))
        aside.append((artifact, path, target))
    prog.note(f"REFRESH osm_layers (authorised, locked, ledgered): "
              f"{len(aside)} schema-stale layer(s) moved aside on tile "
              f"{lat:+d}{lon:+d} — "
              f"{[p.name for _a, p, _t in aside]}; the engine's own prefetch "
              f"re-derives them now, which is the POINT of this run, not "
              f"a side effect")

    # EVERY TILE NAMED, not just this one: the v2 loader merges the 3x3
    # neighbourhood, so a neighbour's superseded feed is named above and
    # must be derived HERE (KDFW died 54 s in on +33-098's).  The engine
    # derives per TILE, so the pass runs once per named tile.
    tiles = {(int(lat), int(lon))}
    small_roads_tiles = set()
    for _a, path, _t in aside:
        named = _tile_of_osm_path(path)
        if named is not None:
            tiles.add(named)
            if "_airport_small_roads.osm" in path.name:
                small_roads_tiles.add(named)
    failures = []
    try:
        for tlat, tlon in sorted(tiles):
            tile = CFG.Tile(tlat, tlon, "")
            try:
                tile.read_from_config()
            except Exception:
                pass
            # the tile build's own prelude creates the tile's OSM cache
            # directory before its first query; a tile never built has none
            os.makedirs(FNAMES.osm_dir(tlat, tlon), exist_ok=True)
            # THE AIRPORTS LAYER is NOT in the prefetch specifications
            # (the tile prelude downloads it inline, then starts the
            # prefetch for the rest), so a COLD tile needs this call or
            # its airports layer stays absent and the frame stays cold.
            if not os.path.isfile(FNAMES.osm_cached(tlat, tlon, "airports")):
                prog.note(f"refresh osm_layers: deriving the ABSENT "
                          f"airports layer of tile {tlat:+d}{tlon:+d}")
                OSM.OSM_queries_to_OSM_layer(
                    VMAP.AIRPORTS_QUERIES, OSM.OSM_layer(), tlat, tlon,
                    ["all"], cached_suffix="airports")
            VMAP.start_background_osm_prefetch(tile)
            VMAP.wait_for_background_osm_prefetch()
            # THE PREFETCH DOES NOT COVER ``airport_small_roads`` — it
            # is not a tile-wide layer, so it has no prefetch
            # specification (``_osm_layer_prefetch_specifications``
            # says so in as many words), and RULINGS 2026-09-17ad left
            # that gap owed.  Its ONE production writer is called here,
            # inside the same authorisation, lock, snapshot and ledger.
            # Only for a tile whose own feed was moved aside above: this
            # refresh re-derives what it NAMED, never more.
            if (tlat, tlon) in small_roads_tiles:
                prog.note(f"refresh osm_layers: re-deriving the "
                          f"airport_small_roads cache of tile "
                          f"{tlat:+03d}{tlon:+04d} (not a tile-wide "
                          f"layer, so the prefetch never touches it)")
                VMAP._airport_auto_roads_layer_at(tlat, tlon)
    finally:
        # The verdict is read off the FILESYSTEM, never off the prefetch:
        # it runs in a daemon thread, so an exception inside it never
        # reaches this frame (the swallowed-degradation class again).
        # And it is read through the SAME function that named the layers,
        # so each one is judged against its own schema constant (roads
        # and water do not share one) and the refusal this refresh must
        # clear is literally the one re-asked.
        still_stale = {a for _s, a, _w in
                       schema_stale_osm_layers(root, lat, lon)}
        for artifact, path, target in aside:
            if path.is_file() and artifact not in still_stale:
                target.unlink()
            else:
                os.replace(str(target), str(path))
                failures.append(str(path))
    if failures:
        raise SystemExit(
            f"REFUSING: --refresh-data osm_layers re-derived NOTHING for "
            f"{len(failures)} layer(s):\n  "
            + "\n  ".join(failures)
            + f"\nThe stale cache(s) were put back, so the corpus is "
              f"exactly as it was.  A refresh that exits 0 having "
              f"achieved nothing is the VMMC defect this refuses (the "
              f"next plain build would refuse on the same artifact "
              f"again).  Check the engine's OSM download path — Overpass "
              f"reachability, the local regional extracts — and re-run.")
    if cold_airports and not dem_cache_state(root, lat, lon)["airports_layer"]:
        raise SystemExit(
            f"REFUSING: --refresh-data osm_layers did not derive the "
            f"airports layer of tile {lat:+d}{lon:+d} — the frame is "
            f"still COLD, so the build would run an overpass query "
            f"mid-measurement.  Check Overpass reachability and re-run.")
    refetched = [a for a, _p, _t in aside]
    prog.note(f"refresh osm_layers done: {len(refetched)} layer(s) "
              f"re-derived schema-current "
              f"({VMAP.ROAD_CACHE_TAG_SCHEMA}) — {refetched}")
    return {"tile": [int(lat), int(lon)],
            "layers": [a for _s, a, _w in stale], "refetched": refetched}


# ══════════════════════════════════════════════════════════════════════
# THE AUTHORISED DEM REFRESH (--refresh-data dem)
# ══════════════════════════════════════════════════════════════════════

def refresh_tile_dem(root, lat, lon, prog) -> dict:
    """Warm a COLD tile's DEM frame — base raster and airport insets —
    under the ``dem`` authorisation the caller already holds.

    THE GAP THIS CLOSES (measured 2026-09-15): ``build_airport.py KDFW
    --tile 32 -97 --refresh-data osm_layers,dem`` on the neighbour tile
    KDFW's pack reaches into was REFUSED by the cold-frame pre-flight
    before any refresh could run, naming the two scopes the command had
    just authorised — because nothing in the run derived a tile's insets
    at all.  ``--warm-insets ICAO`` existed, but its ICAOs must be
    airports OF THE TILE, which cannot be known until the airports layer
    exists; on a cold tile it does not.  So the per-ICAO entry stays for
    the airport a human names, and the TILE entry lives here.

    THE DERIVATIONS ARE THE ENGINE'S OWN, in the tile prelude's order:
    ``O4_DEM_Utils.DEM(..., info_only=True)`` (what
    ``compose_tile_dem_from_disk`` calls, and what downloads a missing
    base raster) and ``O4_Airport_Elevation_Insets.ensure_insets_for_tile
    (tile, dico_airports, refresh=True)`` — the step-1 download hook,
    over the airport dictionary built from the tile's (by now present)
    airports layer, exactly as ``prepare_tile_airports_and_dem`` does.
    Neither is copied.

    Runs AFTER :func:`refresh_stale_osm_layers` for that reason: the
    inset boxes come from the airports layer, which that pass derives.
    Raises ``SystemExit`` when the frame is still cold afterwards — a
    refresh that achieved nothing must not exit 0 (round-2's rule).
    """
    import O4_Config_Utils as CFG                          # noqa: E402
    import O4_File_Names as FNAMES                         # noqa: E402
    import O4_OSM_Utils as OSM                             # noqa: E402
    import O4_Vector_Map as VMAP                           # noqa: E402
    import O4_Airport_Elevation_Insets as INSETS           # noqa: E402

    lat, lon = int(lat), int(lon)
    state = dem_cache_state(root, lat, lon)
    if state["base_raster"] and state["airport_insets"]:
        prog.note(f"refresh dem: tile {lat:+d}{lon:+d} already has its "
                  f"base raster and its airport insets — nothing to derive")
        return {"tile": [lat, lon], "derived": []}

    tile = CFG.Tile(lat, lon, "")
    try:
        tile.read_from_config()
    except Exception:
        pass
    derived = []
    if not state["base_raster"]:
        prog.note(f"REFRESH dem (authorised, locked, ledgered): deriving "
                  f"the BASE RASTER of {state['tile_stem']} through the "
                  f"engine's own loader — a fetch here is the POINT of "
                  f"this run, not a side effect")
        import O4_DEM_Utils as DEM                          # noqa: E402
        DEM.DEM(lat, lon, getattr(tile, "custom_dem", "") or "",
                info_only=True)
        derived.append(f"Elevation_data/**/{state['tile_stem']}.hgt")

    if not state["airport_insets"]:
        airports_cache = FNAMES.osm_cached(lat, lon, "airports")
        if not os.path.isfile(airports_cache):
            raise SystemExit(
                f"REFUSING --refresh-data dem: tile {lat:+d}{lon:+d} has no "
                f"cached airports OSM layer, so the inset bounding boxes "
                f"would come from an overpass QUERY — a second, "
                f"unauthorised fetch.  Authorise osm_layers in the SAME "
                f"run (--refresh-data osm_layers,dem): that pass derives "
                f"the airports layer first, which is why it runs first.")
        layer = OSM.OSM_layer()
        OSM.OSM_queries_to_OSM_layer(VMAP.AIRPORTS_QUERIES, layer, lat, lon,
                                     ["all"], cached_suffix="airports")
        dico = VMAP.build_airports_dico(tile, layer)
        # Spec §B row 5: the refresh reads the tile's own INSET MODE like
        # any build, so it refetches the SELECTED airports, not all 17.
        from auto_patch.selection import inset_keys, resolved_inset_mode
        _mode = resolved_inset_mode(tile)
        _selected = inset_keys(dico, _mode)
        prog.note(f"REFRESH dem (authorised, locked, ledgered): deriving "
                  f"the AIRPORT INSETS of {state['tile_stem']} for "
                  f"{len(_selected)} selected (insets = {_mode}) of "
                  f"{len(dico)} airport(s) through the engine's own "
                  f"tile-prelude hook (ensure_insets_for_tile, refresh)")
        INSETS.ensure_insets_for_tile(tile, dico, refresh=True)
        derived.append(
            f"Elevation_data/**/{state['tile_stem']}_airport_insets/")

    after = dem_cache_state(root, lat, lon)
    still = [k for k in ("base_raster", "airport_insets") if not after[k]]
    if still:
        raise SystemExit(
            f"REFUSING: --refresh-data dem derived NOTHING for "
            f"{still} on tile {lat:+d}{lon:+d} — the frame is still COLD, "
            f"so the build would fetch mid-measurement or grade on an "
            f"all-zero surface.  A refresh that exits 0 having achieved "
            f"nothing is the defect this refuses.  Check provider "
            f"reachability (and, for the insets, that a provider covers "
            f"this tile at all) and re-run.")
    prog.note(f"refresh dem done: {derived}")
    return {"tile": [lat, lon], "derived": derived}


def require_refreshed_frame(root, lat, lon, requested, *, icao=None,
                            refresh_only: bool = False,
                            allow_degraded: bool = False) -> None:
    """THE RE-JUDGE, after this run's authorised refreshes.

    A refresh that did not warm what it was asked to warm must still
    refuse — just later, and with the reason known.  So the frame is
    re-asked with NOTHING authorised.

    ON A ``--refresh-only`` RUN, ONLY THE REQUESTED SCOPES DECIDE THE
    EXIT CODE (measured 2026-09-15 on the owner's own warms):
    ``KPHX --tile 33 -112 --refresh-only --refresh-data osm_layers``
    re-derived +33-112_big_roads and then exited rc 1 on three ``dem``
    items — version-stale USGS3DEP negatives nobody had asked this run
    to touch.  A tile warmed for what was ASKED is a success; a cold
    artefact in a scope this run was not authorised for is INFORMATION,
    printed with the flag that would fix it.  A normal build keeps the
    old strictness to the letter: everything must be current, because
    the build is about to read it.
    """
    missing = missing_shared_artifacts(root, lat, lon, icao)
    if not refresh_only:
        require_dem_frame(dem_cache_state(root, lat, lon),
                          allow_degraded=allow_degraded)
        require_no_implicit_refresh(missing, requested)
        return
    requested = set(requested or ())
    mine = [m for m in missing if m[0] in requested]
    others = [m for m in missing if m[0] not in requested]
    for scope, artifact, why in others:
        print(f"  [harness] still cold, in a scope this run did NOT "
              f"request — informational, not a failure: [{scope}] "
              f"{artifact}\n      {why}\n      warm it with "
              f"--refresh-only --refresh-data {scope}")
    if mine:
        raise SystemExit(
            f"REFUSING: --refresh-only was authorised for "
            f"{sorted(requested)} and {len(mine)} artifact(s) in those "
            f"scopes are STILL not current afterwards:\n  "
            + "\n  ".join(f"[{s}] {a}\n      {w}" for s, a, w in mine)
            + "\nWhatever this run DID derive is already recorded in "
              f"{REFRESH_LEDGER} (the audit runs on every exit path).  "
              f"Check provider/Overpass reachability and re-run.")


def reconcile_refresh_ledger(root, lat, lon, requested, prog,
                             meta=None) -> dict:
    """``--reconcile-ledger``: stamp the CURRENT state of artefacts a
    refresh derived but never recorded.

    THE MEASURED HOLE (2026-09-15, KPHX): the refresh moved
    +33-112_big_roads aside, the engine re-derived it (file mtime 13:48),
    and the run then exited on an unrelated refusal BEFORE the audit — so
    the corpus carries a file no ledger line explains.  Round 6's first
    fix makes that impossible going forward (the audit now runs in the
    ``finally``); this is the RECONCILIATION for the ones already on
    disk, and for any future write a crash puts beyond the audit's reach.

    A FLAG, not automatic, and deliberately so: an artefact whose newest
    ledger line predates its mtime may equally have been written by
    ANOTHER lane's authorised refresh seconds earlier, and stamping that
    silently would put this run's name on someone else's write.  The flag
    is the human saying "I know what happened here, record it".

    Scope: every artefact of the REQUESTED scopes that this tile's
    derivations own and that EXISTS — the layer caches
    ``osm_layer_warm_specifications`` names for this tile, and the 3x3
    road feeds the v2 loader reads.  Each one whose newest ledger line
    predates its mtime gets one ``reconciled`` record carrying the file's
    hash-stamp; one that is already explained is left alone.
    """
    base = corpus_base(root)
    paths = reconcilable_artifacts(root, lat, lon, requested)
    if not paths:
        prog.note("reconcile-ledger: no artefact of the requested "
                  f"scope(s) {sorted(requested)} on tile "
                  f"{lat:+d}{lon:+d} — nothing to reconcile")
        return {"checked": 0, "reconciled": []}
    done = record_reconciliation(paths, dict(meta or {}), repo=base)
    for rel in done:
        prog.note(f"LEDGER RECONCILED: {rel} — it is on disk NEWER than "
                  f"any ledger line that names it; its current hash is "
                  f"now recorded in {REFRESH_LEDGER}")
    if not done:
        prog.note(f"reconcile-ledger: all {len(paths)} artefact(s) of "
                  f"{sorted(requested)} are already explained by a ledger "
                  f"line at or after their mtime — nothing to reconcile")
    return {"checked": len(paths), "reconciled": done}


def corpus_base(root) -> Path:
    """The corpus the ledger's paths are relative to, for THIS lane.

    THE MEASURED BUG (2026-09-15, round 7).  ``reconcilable_artifacts``
    relativised against the LANE ROOT, but a lane's ``OSM_data`` is a
    SYMLINK into the shared repo, so ``Path(cache).resolve()`` lands in
    ``/Users/noah/XPTerrainBuilderData/...`` and ``relative_to(lane)``
    raised ValueError for EVERY artefact.  The list came out empty and
    ``--reconcile-ledger`` reported "no artefact of the requested
    scope(s) on tile +33-112" while the very file it exists for
    (+33-112_big_roads, re-derived 13:48, never ledgered) sat there.  The
    ledger is keyed on SHARED-REPO-relative paths (``record_refresh`` /
    ``_file_stamp``), so that is the frame to use — falling back to the
    lane root only for a corpus that genuinely is not the shared one (a
    twin's tmp root, ``--allow-private-data``).
    """
    root = Path(root)
    try:
        (root / "OSM_data").resolve().relative_to(DATA_REPO.resolve())
        return DATA_REPO.resolve()
    except (OSError, ValueError):
        return root.resolve()


def reconcilable_artifacts(root, lat, lon, requested) -> list:
    """The artefacts of ``requested`` that this tile's refresh
    derivations own AND that exist on disk, relative to
    :func:`corpus_base` — the same frame the refresh ledger uses.

    Same two sources the pre-flight judges (so a reader never has to ask
    which set is meant): the engine's own
    ``O4_Vector_Map.osm_layer_warm_specifications`` for this tile, and
    the v2 loader's own 3x3 ``ROAD_FEEDS`` square.
    """
    requested = set(requested or ())
    if "osm_layers" not in requested:
        return []
    for p in (Path(root) / "src", Path(root)):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    out, seen = [], set()
    base = corpus_base(root)

    def _add(path):
        try:
            rel = str(Path(path).resolve().relative_to(base))
        except (OSError, ValueError):
            return
        if rel in seen or not os.path.isfile(path):
            return
        seen.add(rel)
        out.append(rel)

    try:
        import O4_Config_Utils as CFG
        import O4_File_Names as FNAMES
        import O4_Vector_Map as VMAP
        tile = CFG.Tile(int(lat), int(lon), "")
        try:
            tile.read_from_config()
        except Exception:
            pass
        for spec in VMAP.osm_layer_warm_specifications(tile):
            _add(FNAMES.osm_cached(int(lat), int(lon), spec[0]))
    except Exception as exc:
        print(f"  [harness] reconcile: layer list unavailable ({exc!r})")
    try:
        from auto_patch_v2.airport import osm as _v2osm
        osm_root = str(Path(root) / "OSM_data")
        for dlat in (-1, 0, 1):
            for dlon in (-1, 0, 1):
                for feed in _v2osm.ROAD_FEEDS:
                    _add(_v2osm.feed_path(osm_root, int(lat) + dlat,
                                          int(lon) + dlon, feed))
    except Exception as exc:
        print(f"  [harness] reconcile: feed list unavailable ({exc!r})")
    return sorted(out)


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

    v2 (wired 2026-09-17): the same detector reads the v2 loader's
    ``LoadReport.dem_provenance`` — published for any DEM it composed, so
    an EMPTY one means it composed none.  Until then this refusal was
    reachable only through the v1 builder and went uncalled the moment that
    builder was deleted.
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
    import O4_Settings_Model as SETTINGS
    applied = {}
    for key, value in read_cfg(owner_cfg).items():
        if key in XPLANE_PATH_KEYS and value:
            CFG.set_global_variables(key, CFG.config_compatibility(value))
            applied[key] = value
    # THE SAME PREDICATE the engine itself refuses on
    # (``O4_Vector_Map.run_auto_patch_generation``) — imported, never a
    # second spelling: the harness refusing on a condition the engine
    # tolerated (or the reverse) is how the two drifted apart before.
    refusal = SETTINGS.cifp_refusal_reason(
        applied.get("cifp_data_path", ""),
        applied.get("custom_scenery_dir", ""))
    if refusal is not None:
        raise SystemExit("REFUSING: " + refusal)
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


def imagery_capability(tile, cfg_provenance) -> dict:
    """CAN THIS TILE'S FRAME BUILD IMAGERY? — the ONE implementation, and
    the ONE place RULINGS 2026-08-31d is expressed.

    THE RULING: *a tile entry finding no per-tile cfg DEFAULTS TO THE
    USER'S GLOBAL SETTINGS (Ortho4XP.cfg) — it does not refuse.  Refusal
    is reserved for a global config that itself lacks the required key.*

    What "required" means is per STEP, and that is the whole content of
    this function.  ``default_website`` is required by the IMAGERY half
    of a tile build (masks + textures) and by nothing else:
    ``O4_Cfg_Vars.cfg_global_tile_vars`` excludes ``default_website`` /
    ``default_zl`` / ``zone_list`` from the global config BY
    CONSTRUCTION, because production supplies them per BUILD from the
    app's job — so a lane tile that has no canonical per-tile cfg has no
    provider ANYWHERE, and the ruling says that must cost it the
    textures, not the tile.  The geometry half (vector + mesh) is the
    surface every lane measures and it needs no provider at all.

    Before 31d this raised ``SystemExit`` and the SPJC ``-13-078`` tile —
    an owner acceptance site — was unbuildable in every lane.  Nothing is
    synthesised here: a provider is never invented (that is the input
    the 2026-08-12b ruling forbids), it is simply reported ABSENT, in the
    build's own record (``result["imagery"]``, ``frame["imagery"]``), so
    a reader can never mistake a geometry-only tile for a full one.

    Returns ``{"ok", "reason", "note", "default_website", "default_zl",
    "cfg_action"}``.
    """
    site = str(getattr(tile, "default_website", "") or "")
    zl = getattr(tile, "default_zl", None)
    action = (cfg_provenance or {}).get("action", "unknown")
    if site:
        return {"ok": True, "reason": "provider resolved",
                "note": (f"imagery frame OK: provider {site!r} zl={zl} "
                         f"(per-tile cfg {action})"),
                "default_website": site, "default_zl": zl,
                "cfg_action": action}
    if action == "derived-from-global-defaults":
        why = ("this tile has NO canonical per-tile cfg, so it runs on "
               f"the user's GLOBAL config "
               f"({(cfg_provenance or {}).get('global_source')}) per "
               "owner ruling 2026-08-31d — and the global config carries "
               "no default_website / default_zl / zone_list AT ALL "
               "(O4_Cfg_Vars.cfg_global_tile_vars excludes them: "
               "production supplies the provider per BUILD from the "
               "app's job)")
    else:
        why = (f"the per-tile cfg this build ran on ({action}, "
               f"{(cfg_provenance or {}).get('cfg')}) carries no "
               f"default_website")
    return {
        "ok": False, "reason": why,
        "note": ("IMAGERY STANDS DOWN (owner ruling 2026-08-31d, a tile "
                 "entry does not refuse for a missing per-tile cfg): "
                 f"{why}.  The GEOMETRY half builds — steps 1 vector + "
                 "2 mesh, the surface every lane measures, and the "
                 "levelled-roads sidecar with it — and steps 3 masks + "
                 "4 tile are SKIPPED, recorded in this build's own "
                 "result and frame.  No provider is invented (owner "
                 "ruling 2026-08-12b): to build textures for this tile, "
                 "give it a canonical per-tile cfg in the main tree."),
        "default_website": "", "default_zl": zl, "cfg_action": action}


def resolve_tile_frame(lat: int, lon: int, build_dir, prog=None):
    """``(tile, cfg_provenance, imagery)`` — THE tile frame, for BOTH tile
    entries (``--tile`` here and ``tools/run_tile_mesh_only.py``).

    One implementation, because two arrangements of "which cfg is this
    tile running on, and what can that frame build" is exactly the
    census-wrapper defect at one remove: the two entries would provision
    from different sources and refuse on different conditions, and no
    reader of either build's record could tell.
    """
    import O4_Config_Utils as _CFG
    import O4_File_Names as _FNAMES

    custom_build_dir = _FNAMES.normalize_custom_build_dir(lat, lon,
                                                          build_dir)
    tile = _CFG.Tile(lat, lon, custom_build_dir)
    # PROVISION BEFORE THE READ: ``read_from_config`` falls back to the
    # global config in silence, and which cfg a tile ran on is a frame
    # fact that has to be recorded, not inferred.
    cfg_provenance = provision_tile_cfg(lat, lon, tile.build_dir, prog)
    tile.read_from_config()
    return tile, cfg_provenance, imagery_capability(tile, cfg_provenance)


def provision_tile_cfg(lat: int, lon: int, build_dir, prog=None,
                       source_root=None) -> dict:
    """Provision the lane build dir's per-tile cfg from the canonical
    source, and RECORD where it came from.

    OWNER RULING 2026-08-12b — "LANE INPUTS ARE PROVISIONED BY THE RITUAL,
    NEVER HAND-SEEDED".  A fresh lane build dir has no
    ``Ortho4XP_+XX+YYY.cfg``; ``Tile.read_from_config`` then falls back to
    the GLOBAL config, which by construction carries no provider — and
    the tile build used to refuse there (superseded by RULINGS
    2026-08-31d: the imagery half stands down instead, see
    :func:`imagery_capability`).  On 2026-08-12 two lanes each improvised
    a different cfg source to get past it, which is the census-wrapper
    defect re-emerging: the inconsistency, not the copy, is the harm.

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

    # THE STAMP, ON THE CANONICAL SOURCE (owner RULINGS 2026-09-18c (2)).
    # An UNSTAMPED tile cfg is a pre-1.0.352 file, which the engine MOVES
    # to ``*.pre352.bak`` on first read: a canonical cfg written before
    # the stamp existed would be retired MID-BUILD and the tile would
    # fall back to the global defaults, losing default_website /
    # default_zl / zone_list from the frame.  Stamped HERE, once, on the
    # source — so the copy below stays a BYTE copy (the invariant is
    # about never re-RENDERING the settings; a provenance line changes no
    # value), a ``present`` lane cfg is still never touched, and a
    # DERIVED cfg still carries zero override lines.  Idempotent; it does
    # change the recorded cfg sha256 against pre-18c frames.
    if src.is_file():
        try:
            _src_text = src.read_text(errors="ignore")
            if _src_text.strip() and not any(
                    line.strip().startswith("cfg_written_by=")
                    for line in _src_text.splitlines()):
                _tmp = src.with_suffix(src.suffix + ".stamp.tmp")
                _tmp.write_text(
                    _src_text
                    + ("" if _src_text.endswith("\n") else "\n")
                    + "cfg_written_by=harness\n")
                os.replace(_tmp, src)
                rec["canonical_source_stamped"] = True
        except OSError:                                # pragma: no cover
            pass

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

#: Every artifact file a run writes at its tag stem — the collision
#: surface :func:`claim_tag` must keep free.  (The ``tile_<tag>`` build
#: dir and ``<tag>.engine_caches`` overlay hang off the same stem, so a
#: free stem here means a free run.)
TAG_ARTIFACT_SUFFIXES = (".progress", ".osm", ".osm.axes.json",
                         ".result.json", ".frame.json", ".env.json",
                         ".served.json")


def tag_artifacts_present(out_dir, tag: str) -> list:
    """The artifact files already sitting at ``tag``'s stem in ``out_dir``."""
    return [f"{tag}{suffix}" for suffix in TAG_ARTIFACT_SUFFIXES
            if (Path(out_dir) / f"{tag}{suffix}").exists()]


def claim_tag(out_dir, icao: str, explicit_tag=None) -> str:
    """A run tag no other run holds — CLAIMED, never just formatted.

    The measured defect (lane/mouthweld, 2026-08-15): the auto tag was
    minute-resolution, two lawful parallel HECA arms both tagged
    ``HECA_20260815T1438``, and the second finisher silently overwrote
    the first's patch — each run logged its own body_sha but only one
    ``.osm`` survived on disk.  Parallel correctness builds are the
    owner-ruled norm (2026-08-12), so a timestamp format alone can
    never be unique: the claim is the atomic exclusive create of
    ``<tag>.progress`` (``open(..., "x")``) — whichever process creates
    it owns the tag, the loser moves to the next ``_N`` suffix.  A stem
    with ANY artifact already at it (yesterday's run at the same
    second, a ``.osm`` whose ``.progress`` was cleaned away) is
    likewise skipped, so an existing artifact path is never rewritten.

    An EXPLICIT ``--tag`` is an identity, not a template: if anything
    already sits at it the run REFUSES rather than suffixing — a report
    quoting that tag would otherwise be reading someone else's run.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if explicit_tag:
        hits = tag_artifacts_present(out_dir, explicit_tag)
        if not hits:
            try:
                with open(out_dir / f"{explicit_tag}.progress", "x"):
                    pass
                return explicit_tag
            except FileExistsError:      # lost the race to a parallel run
                hits = [f"{explicit_tag}.progress"]
        raise SystemExit(
            f"REFUSING --tag {explicit_tag}: artifact(s) already at that "
            f"stem in {out_dir}: {', '.join(hits)}.\n"
            f"  Overwriting would silently replace another run's patch "
            f"(the lane/mouthweld collision, 2026-08-15).  Pick a fresh "
            f"tag, or remove the old artifacts explicitly.")
    base = f"{icao}_{time.strftime('%Y%m%dT%H%M%S')}"
    n = 1
    while True:
        candidate = base if n == 1 else f"{base}_{n}"
        if not tag_artifacts_present(out_dir, candidate):
            try:
                with open(out_dir / f"{candidate}.progress", "x"):
                    pass
                return candidate
            except FileExistsError:      # a parallel run claimed it first
                pass
        n += 1
        if n > 10000:                                     # pragma: no cover
            raise SystemExit(f"could not claim a run tag under {base} "
                             f"after {n} attempts in {out_dir}")


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
    # ONE implementation of "what state is the code in" — the same
    # ``code_state_now`` the artifact ledger re-runs at store time, so the
    # start snapshot and the store-time re-check can never disagree on how
    # the state is measured.
    try:
        state = AL.code_state_now(root)
    except Exception as exc:                              # pragma: no cover
        state = {"code_tree_hash": f"<unavailable: {exc!r}>",
                 "git_dirty": bool(_git("status", "--porcelain"))}
    return {
        "cwd": str(root),
        "git_head": _git("rev-parse", "HEAD"),
        "git_dirty": state["git_dirty"],
        "code_tree_hash": state["code_tree_hash"],
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

    # THE OWNER'S X-PLANE INSTALL (2026-09-15, RULINGS 2026-09-15av).
    # Not a cache and not in the data repo, so nothing above reaches it —
    # but the object stage's write half rewrites the SERVING PACK there,
    # and lane v2vmmcshore's tile build of +22+113 rewrote the owner's
    # live VHHH pack DSF mid-build.  The engine's own measure-only path
    # is what stands down (``auto_patch.engine_v2.rebake_after_mesh``):
    # the placement plan is still built and reported — the measurement is
    # the product — and no pack file is written.  Rides an env variable
    # for the same reason the cache redirects do: subprocesses inherit
    # it.  An authorised ``pack_rebake`` leaves the write half enabled,
    # exactly as an authorised cache scope is left SHARED.
    if "pack_rebake" in authorised:
        skipped.append("pack_rebake")
        os.environ.pop("O4_PACK_WRITES", None)
    else:
        os.environ["O4_PACK_WRITES"] = "measure_only"

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

    if prog is not None and "pack_rebake" not in authorised:
        prog.note(
            "pack writes STOOD DOWN (O4_PACK_WRITES=measure_only): the "
            "object stage builds and reports its placement plan and writes "
            "NO file into the owner's X-Plane install — a lane never "
            "mutates it (RULINGS 2026-09-15av)")
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
        "pack_writes": ("AUTHORISED (--refresh-data pack_rebake)"
                        if "pack_rebake" in authorised
                        else "measure_only (the owner's X-Plane install is "
                             "never written by a lane)"),
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
             else SharedRepoWriteGuard(set(), root,
                                       install_roots=xplane_install_roots()))
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

# ``build_patch`` — THE v1 BUILDER — and ``diagnose_missing_sidecar`` were
# DELETED 2026-09-17 (lane v1retire round 1, ruling (f) of the stage-B brief:
# "the HARNESS survives but ... loses its v1 arms — refuse BY NAME where an
# option becomes meaningless, never leave an option inert").
#
# ``build_patch`` called ``auto_patch.pipeline.build_airport_pavement`` and
# ``auto_patch.constant_dem``; ``main`` stopped reaching it when stage A made
# v2 the only engine (RULINGS 2026-09-13az), and its only remaining callers
# were the two v1 instruments that refuse by name themselves now
# (``oracle.py``, ``who_wrote.py``).  ``diagnose_missing_sidecar`` probed
# ``auto_patch.verification`` / ``route_profile.apron_terrace`` /
# ``grade_law`` contributors of the v1 emitter's ``_write_axes_sidecar``,
# which v2 does not write: it named a culprit inside a function that no
# longer runs.  :func:`build_patch_v2` is THE builder, under the same arming
# composition, the same swallowed-refusal detectors (their in-process twins
# moved with them in ``tests/test_harness.py``), the same sidecar guarantee
# and the same result record.


V2_LAW_DIR = Path("src") / "auto_patch_v2" / "law"


def v2_law_tables_digest(root) -> dict:
    """The v2 law tables this tree solves under, hashed — PROVENANCE for
    ``frame.json`` and a component of the artifact-ledger variant key: two
    patches solved under different tables are two artifacts even at one
    code-tree hash?  No — the tables are IN the tree, so the tree hash
    already moves with them; the digest is here so a reader of the frame
    can name WHICH tables without a checkout, and so a ``--law-dir``
    arm (an alternative table set, ``auto_patch_v2 build --law-dir``) can
    never be served for the shipped-table arm if that flag is ever wired
    through this entry.  ONE implementation — the engine's own
    ``auto_patch_v2.law.law_tables_digest`` (the tile build's
    ``[provenance]`` line prints the same digest), pointed at THIS tree's
    tables (a lane's checkout, not whichever ``auto_patch_v2`` is first on
    ``sys.path``)."""
    d = Path(root) / V2_LAW_DIR
    src = str(Path(root) / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from auto_patch_v2.law import law_tables_digest   # noqa: E402
    return law_tables_digest(d)


def build_patch_v2(icao: str, root: Path, out_dir: Path, tag: str,
                   prog: Progress, allow_no_sidecar: bool = False,
                   write_guard=None, allow_degraded: bool = False) -> dict:
    """One airport through ``auto_patch_v2.pipeline.build`` → ``<out>/<tag>.osm``
    + ``<tag>.osm.axes.json`` — the v2 twin of :func:`build_patch`, under the
    SAME arming composition, the same swallowed-refusal detectors, the same
    sidecar guarantee and the same result record (every key ``build_patch``
    publishes, so ``main``'s frame, result and artifact-ledger code is one
    path for both engines — extend, never fork, RULINGS ``7e90032``).

    What differs, and is RECORDED: ``engine`` = ``"v2"``; ``law_tables`` =
    :func:`v2_law_tables_digest`; ``dem_inset_provenance`` is the v2
    loader's production-frame provenance (``LoadReport.dem_provenance``:
    the core's composed tile DEM read through the same resolution the
    mesh drapes on, M3a); ``engine_solve_model`` is ``None`` — v2 has one
    solver (HiGHS LP) and no v1 mode plumbing, so ``main``'s one-reader
    check is vacuous for it; ``anchor`` is ``None`` (v2's sidecar register
    is closed by design, M4 §5).  The v2 pipeline writes
    ``<ICAO>_auto.patch.osm`` beside ``<ICAO>.graded.json`` and
    ``<ICAO>.report.json`` into ``<out>/<tag>.v2/``; the patch and sidecar
    are then MOVED to the harness names (one artifact, two names would be
    the census-wrapper defect in a smaller costume).  A solve that is not
    optimal/feasible REFUSES to report — there is no patch, and the IIS
    is in ``<tag>.v2/<ICAO>.report.json``.
    """
    for p in (root / "src", root, root / "tests", root / "tools"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    guard, redirects = arm_shared_repo_protection(
        root, out_dir, tag, prog, write_guard=write_guard)
    from auto_patch_v2.planar.__main__ import default_inputs   # noqa: E402
    from auto_patch_v2.pipeline.build import Config, build     # noqa: E402
    from auto_patch_v2.law import Law                          # noqa: E402
    # THE PRISTINE PACK DUMP (RULINGS 2026-09-13, lane ``v2zerocrater``).
    # v2's read frame is the ``.dsf.anchor_bak`` the object stage moved
    # aside, and v2 never runs DSFTool itself — ``find_text_dump`` REFUSES
    # a dump that is not named for that exact file.  The APP's driver
    # re-dumps it (``auto_patch.engine_v2.fresh_pack_dump``); without the
    # same call here every harness ``--engine v2`` build of a pack the
    # object stage has written refuses, which is how KCLT became
    # unbuildable through the harness on 09-12 while the app built it.
    # ONE implementation, called from both entries (RULINGS ``7e90032``);
    # the dump lands in the LANE-LOCAL mod-cache overlay armed above.
    from auto_patch.engine_v2 import fresh_pack_dump            # noqa: E402
    law_tables = v2_law_tables_digest(root)
    prog.note(f"engine v2: law tables {law_tables['sha256'][:12] if law_tables['sha256'] else None} "
              f"({len(law_tables['files'])} files under {law_tables['dir']})")
    inputs = default_inputs(dem_frame="production",
                            allow_degraded_dem=allow_degraded)
    # THE REDIRECT MUST REACH v2's LOADER (RULINGS 2026-09-13q, "chip":
    # ``explain KCLT`` — and this build entry — refused on the pack-dump
    # freshness guard because ``planar.__main__.default_inputs`` resolves
    # the mod cache to the ENGINE TREE and reads no environment (a stated
    # property of that convenience entry point), so the LANE-LOCAL overlay
    # this harness just armed was ignored and the guard judged the SHARED
    # root.  The env read belongs HERE, in the harness that set it: the
    # build then reads and derives its DSF text dumps in the same
    # lane-local overlay every other derived cache lands in.
    _mod = os.environ.get("O4_AIRPORT_MOD_CACHE_DIR")
    # (``_dc.is_dataclass``: production's ``Inputs`` is a frozen dataclass;
    # a twin that stubs ``default_inputs`` hands back its own object and
    # keeps its own root, which is what that twin is asserting)
    if _mod and _dc.is_dataclass(inputs) and "airport_mod_cache" not in (
            (redirects or {}).get("left_shared_for_refresh") or ()):
        inputs = _dc.replace(inputs, mod_cache_root=_mod)
        prog.note(f"engine v2 inputs: mod cache {_mod} (the lane-local overlay)")
    law = Law.for_airport(icao)
    # ``dataclasses.is_dataclass``: the v2 twin in ``tests/test_harness.py``
    # stubs ``default_inputs`` with a dict — there is no pack to dump then.
    tile = resolve_tile_for(icao, root) if dataclasses.is_dataclass(inputs) else None
    if tile is not None:
        dump = fresh_pack_dump(inputs.xplane_root, icao, *tile)
        if dump:
            inputs = dataclasses.replace(inputs, dsf_dump_path=dump)
            prog.note(f"pack DSF dump (pristine read frame): {dump}")
    v2_dir = out_dir / f"{tag}.v2"
    lines: list = []
    t0 = time.time()
    with guard:
        res = build(icao, inputs, v2_dir, Config(), law, out=lines.append)
    dt = time.time() - t0
    for ln in lines:
        prog.note(f"  [v2] {ln}")
    require_no_swallowed_write_block(guard.blocked,
                                     allow_degraded=allow_degraded, prog=prog)
    # DETECTOR 2 over v2's OWN provenance (wired 2026-09-17, lane v1retire
    # round 1): it was called only from the v1 ``build_patch``, so deleting
    # that builder would have left "a refusal nobody calls".  v2's
    # equivalent of the null ``layout.dem_inset_provenance`` is an EMPTY
    # ``LoadReport.dem_provenance`` — the loader publishes the composed tile
    # DEM's frame for any DEM it read, so nothing means it read none.
    require_dem_prep_succeeded(
        (res.report.get("load", {}) or {}).get("dem_provenance") or None,
        allow_degraded=allow_degraded, prog=prog)
    report_guard_churn(guard, prog)
    status = res.solution.status.value
    if status not in ("optimal", "feasible") or res.paths is None:
        raise SystemExit(
            f"REFUSING to report this build: the v2 solve for {icao} ended "
            f"{status!r} ({res.solution.message}); no patch was written.  The "
            f"IIS, if diagnosed, is in {v2_dir / (icao + '.report.json')}.")
    out_dir.mkdir(parents=True, exist_ok=True)
    osm = out_dir / f"{tag}.osm"
    side = Path(str(osm) + ".axes.json")
    Path(res.paths.patch).replace(osm)
    v2_side = Path(res.paths.sidecar)
    if v2_side.exists():
        v2_side.replace(side)
    if not side.exists():
        msg = (f"NO axes sidecar was written ({side}).  Every census would "
               f"silently fall back to the context-free frame, which "
               f"OVERCOUNTS by construction — the numbers would not be "
               f"defect counts.")
        if not allow_no_sidecar:
            raise SystemExit("REFUSING to report this build: " + msg)
        prog.note("DEGRADED (accepted by flag): " + msg)
    verify = (res.report.get("verify") or {}).get("by_family")
    verify_defects = (res.report.get("verify") or {}).get("defects") or {}
    prog.note(f"built {tag} [v2] in {dt:.1f}s  ways={res.paths.ways}  "
              f"nodes={res.paths.nodes}  status={status}  -> {osm}  "
              f"sidecar={'OK' if side.exists() else 'MISSING'}  "
              f"body_sha={body_sha256(osm)[:12]}  v2-verify rows="
              f"{sum(verify.values()) if verify else 'n/a'}")
    if verify_defects:
        # a structural defect of the product (verify.DEFECT_KEYS: a RUNWAY
        # law the solve holds as a constraint, read broken on the emitted
        # surface — RULINGS 2026-09-08v) — the app driver FAILS the airport
        # on it; the harness measures and says so on every line
        prog.note("v2-verify DEFECT (the app build would fail this airport): "
                  + ", ".join(f"{k} {n}" for k, n in verify_defects.items()))
    _under = (res.report.get("verify") or {}).get("defects_under_floor") or {}
    if _under:
        # RULINGS 2026-09-14bx: DEFECT rows the materiality floor spared —
        # census violations counted in ``by_family``, never an abort
        prog.note("v2-verify DEFECT rows under the materiality floor (counted, "
                  "not fatal): " + ", ".join(
                      f"{k} {v['rows']} rows, worst {v['worst_excess_m']} m"
                      for k, v in sorted(_under.items())))
    return {
        "_layout": None,
        "icao": icao, "tag": tag, "patch": str(osm), "sidecar": str(side),
        "engine": "v2",
        "law_tables": law_tables,
        "synthetic_dem": None,
        "geometry_only": False,
        "engine_solve_model": None,
        "build_seconds": round(dt, 1), "shapes": res.paths.ways,
        "body_sha256": body_sha256(osm),
        "sidecar_present": side.exists(),
        "write_guard_armed": guard.enabled,
        "write_guard_blocked": list(guard.blocked),
        "write_guard_lock_churn": list(guard.lock_churn),
        "write_guard_library_index_churn": list(guard.library_index_churn),
        "dem_frame_effective": frame_surface_keys(root),
        # Spec §A.6 / §B row 14: WHICH airports this build's inset
        # selection admits, and whether THIS one is among them.  A
        # patched-but-not-inset airport is a legitimate recorded frame,
        # not a cold one — the harness refuses nothing new for it.
        "inset_selection": inset_selection_record(root, icao),
        "dem_inset_provenance": dict(res.report.get("load", {}).get("dem_provenance") or {}),
        "engine_cache_redirects": redirects,
        "anchor": None,
        "v2": {"dir": str(v2_dir), "report": str(v2_dir / f"{icao}.report.json"),
               "status": status, "wall_s": res.wall, "lp": res.lp_size,
               "verify_by_family": verify, "verify_defects": verify_defects,
               "ruleset": law.ruleset_key,
               "tiles": sorted(f"{tl:+03d}{tn:+04d}" for (tl, tn) in (res.pieces or {}))},
    }


def run_tile_steps(tile, plan, prog, skip_steps=None):
    """Run a tile's release steps under THE STEP CONTRACT — the engine
    pipeline's own failure convention, which the harness loop used to
    ignore (the silent-step-failure class, LEMD +40-004 2026-09-02).

    Ortho4XP step functions never raise on their own errors and never set
    ``red_flag`` for them: they print an ERROR line
    (``UI.exit_message_and_bottom_line``) and ``return 0``; a normal exit
    returns 1 (``build_masks``: a bare ``return``, i.e. ``None``).  So the
    ONLY failure signal is ``result == 0`` — exactly the predicate the
    engine path checks (``o4_engine/session.py`` ``_build_worker``), and
    exactly what the old loop discarded: a mesh step whose ``.node`` input
    was never written printed its ERROR, was reported "DONE 0.0s", every
    later step failed the same silent way, and the run exited 0 as if the
    tile had built.  Nothing downstream re-checks — the DONE note and the
    exit code ARE the measurement, so they must not lie.

    Semantics, mirroring the engine session:

    * ``red_flag`` up after a step (result 0 or not) → cancellation, not
      failure: the run stops with the red-flag message.
    * ``result == 0`` without the red flag → THE step failed: stop the
      tile at the first failed step (H1 parity), ``SystemExit`` naming it
      — never a DONE note, never rc 0.
    * a step named in ``skip_steps`` (``{name: reason}``) → an EXPLICIT
      skip, recorded and never run.  This is the hook for a frame in
      which a step is INAPPLICABLE (a geometry-only tile frame never
      emits mesh inputs): declare the skip, never let the step run into
      its own missing-input failure.  ``build_tile`` passes it for the
      IMAGERY half (steps 3 masks + 4 tile) when the frame resolves no
      provider (RULINGS 2026-08-31d, ``imagery_capability``); the
      geometry-only *airport* frame is a different entry —
      ``--geometry-only`` with ``--tile`` still refuses at the arg check.

    Returns ``(timings, skipped)``: per-step seconds for the steps that
    ran, and the recorded skip reasons.
    """
    import O4_UI_Utils as UI
    timings, skipped = {}, {}
    for name, step in plan:
        if skip_steps and name in skip_steps:
            skipped[name] = skip_steps[name]
            prog.note(f"step {name} SKIPPED — {skip_steps[name]}")
            continue
        prog.note(f"step {name} START")
        t0 = time.time()
        result = step(tile)
        dt = round(time.time() - t0, 1)
        if UI.red_flag:
            raise SystemExit(f"step {name} raised the red flag — stopping")
        if result == 0:
            timings[name] = dt
            raise SystemExit(
                f"step {name} FAILED after {dt}s — its build function "
                f"returned 0 (its ERROR line is above; Ortho4XP steps "
                f"signal failure by return value, never by exception or "
                f"red_flag).  Stopping the tile at the first failed step "
                f"(engine H1 parity).  If this step is INAPPLICABLE in "
                f"this frame, it must be an explicit recorded skip "
                f"(``skip_steps``), never an attempted run.")
        timings[name] = dt
        prog.note(f"step {name} DONE {dt}s")
    return timings, skipped


def build_tile(lat: int, lon: int, build_dir: str, prog: Progress,
               skip_steps=None, requested=None, boundary="skip") -> dict:
    """One whole tile through the four release steps, with the owner's
    X-Plane install paths applied (absorbs ``run_release_tile.py``).
    The tile's patches build with the ONE auto-patch engine, v2 (owner
    RULINGS 2026-09-13au retired v1 and its ``auto_patch_engine`` key —
    there is nothing to select and no ``--engine`` flag).  ``requested``: the
    authorised ``--refresh-data`` scopes, for the admission checks that
    need the resolved tile frame (:func:`bathymetry_band_admission`)."""
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

    # THE INPUT, PROVISIONED (owner ruling 2026-08-12b) and the frame's
    # capability resolved — ONE implementation, shared with
    # ``tools/run_tile_mesh_only.py`` (RULINGS 2026-08-31d).
    tile, cfg_provenance, imagery = resolve_tile_frame(
        lat, lon, build_dir, prog)
    prog.note(f"tile {lat:+d}{lon:+d} build_dir={tile.build_dir} "
              f"website={tile.default_website} zl={tile.default_zl} "
              f"auto_patch={tile.auto_patch} engine=v2 "
              f"modify_custom_airports={tile.modify_custom_airports} "
              f"boundary={boundary}")
    # THE BOUNDARY ANSWER (spec §C.4).  The harness is UNATTENDED, so the
    # default is SKIP-loudly and it never grows its own tile list.
    # ``neighbour`` here means "the neighbour frame must ALREADY be warm":
    # the engine's ``ensure_tile_frame`` is armed only when the session
    # hosts the build, and every fetch under the armed write guard would
    # refuse anyway — so a cold neighbour REFUSES up front, by name.
    VMAP.set_boundary_policy(boundary)
    tile.boundary_policy = boundary
    if boundary == "neighbour":
        cold = [cell for cell in neighbour_cells_of(tile)
                if not VMAP.tile_frame_is_warm(*cell)]
        if cold:
            raise SystemExit(
                "REFUSING --boundary neighbour: tile(s) "
                + ", ".join("%+03d%+04d" % c for c in cold)
                + " have a COLD frame, and the harness never downloads "
                  "implicitly.  Authorise it: build_airport.py --tile "
                  f"{cold[0][0]} {cold[0][1]} --refresh-data osm_layers,dem")
    if not imagery["ok"]:
        # RULINGS 2026-08-31d: A TILE ENTRY DOES NOT REFUSE FOR A MISSING
        # PER-TILE CFG.  It takes the user's GLOBAL settings and builds
        # what those settings can build; refusal is reserved for a global
        # config that itself lacks a key the step being run REQUIRES.
        # The provider is required by the IMAGERY half only (masks +
        # textures), so that half stands down, by name, and the geometry
        # half — the surface every lane measures — builds.
        prog.note(imagery["note"])
        UI.vprint(1, f"  [harness] {imagery['note']}")
        # ...and it stands down as an EXPLICIT RECORDED SKIP under THE
        # STEP CONTRACT (``run_tile_steps`` ``skip_steps``): steps 3 masks
        # + 4 tile are named in ``steps_skipped`` with the ruling's note
        # as the reason — never run into a provider-less failure, never
        # silently absent from the plan.  A caller's own skips (if any)
        # take precedence; the imagery half is added, not overwritten.
        skip_steps = dict(skip_steps or {})
        for name in ("3 masks", "4 tile"):
            skip_steps.setdefault(name, imagery["note"])
    # THE BAND ADMISSION (2026-09-04): a cold bathymetry band is a
    # shared-repo write the masks step (and the step-1 prefetch) would
    # make mid-build — refused HERE, before step 1 is paid for, naming
    # --refresh-data dem, exactly like the filesystem-only pre-flight
    # refuses a missing base raster.  It needs the tile frame (the cfg
    # keys decide the gating), which is why it is not in ``main``.
    band_missing = bathymetry_band_admission(
        tile, ROOT, dsf_step_runs="4 tile" not in (skip_steps or {}))
    require_no_implicit_refresh(band_missing, set(requested or ()))
    prog.note(f"bathymetry band admission: "
              f"{'SETTLED (no fetch, no write)' if not band_missing else 'AUTHORISED refresh'}")

    plan = (("1 vector", VMAP.build_poly_file),
            ("2 mesh", MESH.build_mesh),
            ("3 masks", MASK.build_masks),
            ("4 tile", TILE.build_tile))
    timings, skipped = run_tile_steps(tile, plan, prog, skip_steps=skip_steps)
    return {"tile": [lat, lon], "build_dir": tile.build_dir,
            "step_seconds": timings,
            # The steps that actually RAN (and completed — a failed step
            # raised inside ``run_tile_steps``), in plan order: never a
            # skipped one, so a geometry-only tile can never read as full.
            "steps_run": [n for n, _ in plan if n in timings],
            "steps_skipped": skipped,
            "xplane_paths": paths,
            "imagery": imagery,
            "tile_cfg_provenance": cfg_provenance,
            "tile_engine": None}


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
                    help="output tag (default <ICAO>_<yyyymmddThhmmss>, "
                         "suffixed _N if that stem is taken; an explicit "
                         "tag REFUSES to overwrite existing artifacts)")
    ap.add_argument("--patch-only", action="store_true", default=True,
                    help="build the airport patch only (the default)")
    ap.add_argument("--tile", nargs=2, type=int, metavar=("LAT", "LON"),
                    help="build the WHOLE TILE through the four release "
                         "steps instead (release defaults, owner's X-Plane "
                         "install paths)")
    ap.add_argument("--build-dir", default=None,
                    help="--tile only: the scenery pack directory")
    ap.add_argument("--boundary", choices=("skip", "neighbour"),
                    default="skip",
                    help="--tile only: what to do with an airport whose "
                         "AIRSIDE claim crosses into a 1 degree tile this "
                         "run is not building (spec insets-follow-patch-"
                         "set §C.4).  DEFAULT skip, loudly: the harness is "
                         "unattended and never grows its own tile list.  "
                         "'neighbour' means the neighbour frame must "
                         "ALREADY be warm — a cold one REFUSES naming "
                         "--refresh-data osm_layers,dem for that tile; the "
                         "harness never downloads implicitly.  Recorded in "
                         "<tag>.frame.json.")
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
    ap.add_argument("--reconcile-ledger", action="store_true",
                    help="record the CURRENT hash of every artefact of the "
                         "--refresh-data scope(s) on this tile whose newest "
                         "refresh-ledger line predates its mtime — the "
                         "reconciliation for a derivation a crash or a "
                         "later refusal put beyond the audit's reach.  "
                         "Explicit on purpose: another lane's authorised "
                         "refresh looks the same from the outside.")
    ap.add_argument("--refresh-only", action="store_true",
                    help="perform the --refresh-data scopes for the named "
                         "tile and EXIT without building.  For warming a "
                         "NEIGHBOUR tile: the v2 loader reads road layers "
                         "over the 3x3 neighbourhood, and warming one used "
                         "to mean a whole --tile build.  rc 0 only when "
                         "the frame re-judges CURRENT afterwards.")
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
    # THE ENGINE IS V2, THE ONLY ONE (owner RULINGS 2026-09-13au: v1
    # retired, the setting and the selector gone with it).  These three
    # flags were wired for v1 and are NOT wired for v2; a flag that
    # quietly does nothing is how a lane comes to believe it measured
    # something it did not, so each is refused by name.
    for flag, on in (("--dem", args.dem is not None),
                     ("--geometry-only", bool(args.geometry_only)),
                     ("--solve-capture", args.solve_capture is not None)):
        if on:
            raise SystemExit(
                f"REFUSING: {flag} is not wired for the v2 engine, which "
                f"is the only engine since v1 was retired (RULINGS "
                f"2026-09-13au) — v2 builds the airport patch on the "
                f"production DEM frame only (no constant-DEM oracle "
                f"world, no geometry-only emit, no solve-stage capture).  "
                f"Build the patch: build_airport.py {args.icao}, or the "
                f"tile: --tile LAT LON.")
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
    out_dir = Path(args.out)
    tag = claim_tag(out_dir, args.icao, args.tag)
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

    if args.refresh_only and not requested:
        raise SystemExit(
            "REFUSING --refresh-only: no --refresh-data scope is "
            "authorised, so there is nothing to refresh and nothing to "
            "record.  Name the scope(s): --refresh-data osm_layers[,dem].")
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
        # The per-airport inset check runs HERE, once, and travels in its
        # OWN frame key — never inside ``dem_cache_before``, which the
        # artifact ledger hashes whole.  A ``--tile`` run judges the whole
        # tile, so it names no single airport.
        inset_problem = this_airports_inset_problem(
            state, lat, lon, None if args.tile else args.icao)
        frame["airport_inset_problem"] = (
            {"kind": inset_problem[0], "why": inset_problem[1]}
            if inset_problem else None)
        if inset_problem:
            prog.note(f"per-airport inset {inset_problem[0].upper()}: "
                      f"{inset_problem[1]}")
        prog.note(f"DEM cache {state['tile_stem']}: base_raster="
                  f"{state['base_raster']} insets={state['airport_insets']} "
                  f"airports_layer={state['airports_layer']} "
                  f"overlay={state['tile_overlay']}")
        if args.refresh_only:
            # A WARM RUN IS NOT A MEASUREMENT (2026-09-15, round 6).  The
            # pre-flight exists to stop a BUILD reading a cold or stale
            # frame; a ``--refresh-only`` run reads nothing and builds
            # nothing.  Refusing here is what stopped
            # ``KDFW --tile 33 -98 --refresh-only --refresh-data
            # osm_layers`` before it could warm anything — 31 ``dem``
            # items (15ay's version-stale USGS3DEP negatives) nobody had
            # asked that run to touch.  Everything is judged AFTER the
            # derivations instead, by ``require_refreshed_frame``, which
            # decides the exit code on the REQUESTED scopes alone.
            prog.note("--refresh-only: the pre-flight stands down (this "
                      "run reads nothing and builds nothing); the frame "
                      "is judged AFTER the derivations, on the requested "
                      "scope(s) alone")
        elif args.dem is None:
            require_dem_frame(state, allow_degraded=args.allow_degraded_dem,
                              requested=requested,
                              inset_problem=inset_problem)
        else:
            prog.note("constant-DEM oracle build: the real DEM frame is "
                      "SUBSTITUTED, so its cache warmth cannot confound "
                      "this run (checked and recorded, not enforced)")
        # A missing artifact is a DOWNLOAD this build would perform as a
        # side effect.  Named and refused unless explicitly authorised.
        if not args.refresh_only:
            require_no_implicit_refresh(
                missing_shared_artifacts(root, lat, lon,
                                         None if args.tile else args.icao,
                                         state=state,
                                         inset_problem=inset_problem),
                requested)
    else:
        prog.note(f"WARNING: could not resolve the anchor tile for "
                  f"{args.icao} — the DEM cache state is UNKNOWN for this "
                  f"run and no elevation from it may be quoted.")

    # ── THE ENGINE (RULINGS 2026-09-03d: v2 beside v1; 2026-09-13au:
    # v1 RETIRED, so this is a CONSTANT) ──────────────────────────────
    # Recorded in the frame and keyed into the artifact ledger BEFORE any
    # engine code runs, like every other key part: the v2 law tables are
    # in the tree (the tree hash moves with them) and are named here so a
    # frame reader can say WHICH tables without a checkout.  The key part
    # keeps the same spelling it had under ``--engine v2`` — a frame or a
    # ledger entry from before the retirement still reads.
    frame["engine"] = ENGINE
    frame["law_tables"] = v2_law_tables_digest(root)
    prog.note(f"engine: {ENGINE}"
              + (f" (law tables {frame['law_tables']['sha256'][:12]})"
                 if frame["law_tables"] and frame["law_tables"]["sha256"] else ""))

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
                geometry_only=args.geometry_only,
                engine=ENGINE,
                law_tables_sha256=(frame["law_tables"] or {}).get("sha256"))}
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
    # THE OWNER'S PACKS ARE IN THE SNAPSHOT TOO (RULINGS 2026-09-15av +
    # 15bb).  Two lane tile builds rewrote live packs — VHHH's DSF at
    # 11:49:11, LEMD's DSF + provenance + 2,694 split body .obj files at
    # 12:21:43 — and BOTH runs printed "shared repo UNCHANGED", because
    # the walk covered the data repo only.  The keys are spelled
    # ``Custom Scenery/...``, which ``scope_of`` maps to ``pack_rebake``,
    # so an install write NAMES itself and marks the run exactly like a
    # corpus write.  Belt to the guard's braces: the guard refuses the
    # Python writes at the call, this catches whatever a subprocess does
    # without passing through one.
    pack_roots = (pack_roots_for_tile(lat, lon, xplane_install_roots()[0])
                  if lat is not None and xplane_install_roots() else ())
    before = shared_repo_snapshot()
    before.update(install_snapshot(pack_roots))
    prog.note(f"shared-repo snapshot: {len(before)} file(s) across "
              f"{len(SHARED_DATA_DIRS)} data dir(s) and "
              f"{len(pack_roots)} X-Plane pack(s) carrying this tile")

    # THE BUILD'S INPUT SET (2026-09-01, H6 item 6): what this run has a
    # reason to touch, so the audit below can tell a delta this build
    # could have authored from one that merely landed in its window.  The
    # harness already knows both halves — the anchor tile it resolved and
    # the airport(s) it names — so nothing new is derived here.  A run
    # whose tile did not resolve names no tile, the scope is empty, and
    # the audit keeps its old whole-window strictness.
    input_scope = BuildInputScope(
        tiles=[(lat, lon)] if lat is not None and lon is not None else (),
        icaos=[args.icao] + list(warm_insets or ()),
        label=f"{args.icao}{' --tile' if args.tile else ''}")
    prog.note(f"build input set: {input_scope.record()}")

    guard = SharedRepoWriteGuard(requested, root,
                                 enabled=not args.allow_shared_repo_writes,
                                 install_roots=xplane_install_roots())
    if guard.enabled:
        prog.note(f"shared-repo write GUARD armed: writes outside "
                  f"{sorted(requested) or 'any authorised scope'} are "
                  f"REFUSED at the call, not merely reported afterwards")
    else:
        prog.note("shared-repo write guard DISARMED by flag — writes are "
                  "detected after the fact only (the pre-fix behaviour)")

    warm_summary = None
    osm_refresh_summary = dem_refresh_summary = reconcile_summary = None
    t0 = time.time()
    # EVERYTHING FROM HERE IS INSIDE THE AUDIT'S ``finally`` (2026-09-15,
    # round 6).  It used not to be, and two things leaked, both measured
    # on the owner's own KDFW/KPHX warms:
    #   * KPHX: the refresh MOVED +33-112_big_roads aside, the engine
    #     re-derived it ("1 layer(s) re-derived", 13:48) — and the
    #     RE-JUDGE below then refused on unrelated ``dem`` items, so the
    #     run exited before the audit ever ran and there is no
    #     ``REFRESH RECORDED [osm_layers]`` line for a write that
    #     happened.  A corpus that changed without a ledger line is
    #     exactly what the ledger exists to prevent.
    #   * KDFW +33-098: the pre-flight refusal left
    #     ``.harness/locks/osm_layers.lock`` behind (holder pid 46331,
    #     dead), because the release lived only on the success path.
    # So the derivation, the re-judge and the build all sit inside one
    # try; the ``finally`` snapshots, reports, STAMPS THE LEDGER and
    # releases every lock on every exit path, refusal included.  Nothing
    # is swallowed: the finally re-raises whatever came through it.
    try:
        # THE WARM, inside everything that makes a shared-repo write
        # lawful: the scope lock is held, ``before`` is snapshotted, and
        # the guard is armed with ``dem`` authorised.
        if warm_insets:
            if lat is None:
                raise SystemExit(
                    f"REFUSING --warm-insets: the anchor tile for "
                    f"{args.icao} did not resolve, so there is no inset "
                    f"cache to warm.")
            with guard:
                warm_summary = warm_airport_insets(warm_insets, root, lat,
                                                   lon, prog)

        # THE OSM-LAYER REFRESH, in the same place and for the same
        # reason.  Before the build, so a schema-stale layer is
        # re-derived as an EXPLICIT event instead of being rewritten
        # mid-build (the contamination of RULINGS 2026-09-15u) — and so
        # this run's re-derivation lands in the before/after diff the
        # ledger stamps.
        if "osm_layers" in requested and lat is not None:
            with guard:
                osm_refresh_summary = refresh_stale_osm_layers(
                    root, lat, lon, prog)
        # THE DEM REFRESH runs SECOND, deliberately: the inset bounding
        # boxes come from the tile's airports layer, which the pass above
        # derives when it is absent (the cold-neighbour case, +32-097).
        if "dem" in requested and lat is not None:
            with guard:
                dem_refresh_summary = refresh_tile_dem(root, lat, lon, prog)
        # THE LEDGER RECONCILIATION (--reconcile-ledger), before the
        # re-judge for the same reason the audit moved: it is a RECORD of
        # what is on disk, and a later refusal must not lose it.
        if args.reconcile_ledger and lat is not None:
            with guard:
                reconcile_summary = reconcile_refresh_ledger(
                    root, lat, lon, requested, prog,
                    meta={"lane": str(root), "tag": tag,
                          "argv": sys.argv[1:]})

        # RE-JUDGED with NOTHING authorised: a refresh that did not warm
        # the frame still refuses, just later and with the reason known.
        if requested and lat is not None and args.dem is None:
            require_refreshed_frame(
                root, lat, lon, requested,
                icao=None if args.tile else args.icao,
                refresh_only=args.refresh_only,
                allow_degraded=args.allow_degraded_dem)

        if args.refresh_only:
            # THE WARM-ONLY RUN (2026-09-15).  The v2 loader reads road
            # layers over the 3x3 NEIGHBOURHOOD, so warming a neighbour
            # meant ``--tile LAT LON --refresh-data osm_layers`` — a
            # WHOLE tile build (minutes to an hour) that refuses a cold
            # DEM frame before it gets there.  This performs exactly the
            # authorised refreshes above, lets the audit below stamp the
            # ledger, and never enters a build stage.  Everything that
            # makes a shared-repo write lawful has already happened: the
            # scope lock, the snapshot, the armed guard, the re-judged
            # pre-flight.
            result = {"refresh_only": True,
                      "tile": [lat, lon] if lat is not None else None,
                      "refresh_authorised": sorted(requested),
                      "refresh_osm_layers": osm_refresh_summary,
                      "refresh_dem": dem_refresh_summary,
                      "wall_seconds": round(time.time() - t0, 1)}
            prog.note(f"REFRESH-ONLY: the authorised refresh(es) "
                      f"{sorted(requested)} are done and the frame is "
                      f"re-judged CURRENT; no build stage was entered")
        elif args.tile:
            # ``build_patch`` redirects the engine's cache roots itself;
            # the tile path never goes through it, so it does it here.
            redirects = redirect_engine_caches(out_dir, tag, prog,
                                               authorised=requested,
                                               tiles=[(lat, lon)],
                                               lane_root=root)
            with guard:                    # build_patch arms its own
                result = build_tile(
                    lat, lon,
                    args.build_dir or str(out_dir / f"tile_{tag}"), prog,
                    requested=requested, boundary=args.boundary)
            result["boundary_policy"] = args.boundary
            result["engine_cache_redirects"] = redirects
            result["engine"] = ENGINE
        else:
            # THE ONE AIRPORT PATH (v1 retired, RULINGS 2026-09-13au):
            # ``build_patch`` — the v1 twin — is unreachable from here
            # until the stage-B deletion.
            result = build_patch_v2(args.icao, root, out_dir, tag, prog,
                                    allow_no_sidecar=args.allow_no_sidecar,
                                    write_guard=guard,
                                    allow_degraded=args.allow_degraded_dem)
        result["wall_seconds"] = round(time.time() - t0, 1)
    finally:
        # The audit runs even when the build raised: a build that died
        # half-way through a download has still mutated the shared repo,
        # and that is precisely when nobody would think to look.
        after = shared_repo_snapshot()
        after.update(install_snapshot(pack_roots))
        changes = snapshot_diff(before, after)
        # ``redirected=None``: the audit asks the ENGINE's own accessors
        # now, in the process that did the building, which scopes this run
        # pointed outside the repo — a delta in one of those has no
        # possible author here (2026-09-15, the VHHH mis-attribution).
        offenders = report_unauthorised_writes(changes, requested, prog,
                                               blocked=guard.blocked,
                                               input_scope=input_scope)
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
    # EVERY delta is still named here; the CONTAMINATED verdict reads only
    # the ones this build's input set could not exclude (2026-09-01, H6
    # item 6 — the window is not the author).  ``build_input_scope`` rides
    # beside them so a later reader can re-derive every verdict.
    frame["unauthorised_writes"] = offenders
    frame["external_candidate_writes"] = [o for o in offenders
                                          if o.get("external_candidate")]
    frame["build_input_scope"] = input_scope.record()
    frame["contaminated"] = bool(contaminating_writes(offenders))
    frame["write_guard_armed"] = guard.enabled
    frame["write_guard_blocked"] = guard.blocked
    frame["write_guard_lock_churn"] = guard.lock_churn
    frame["write_guard_library_index_churn"] = guard.library_index_churn
    frame["warm_insets"] = warm_summary
    frame["refresh_osm_layers"] = osm_refresh_summary
    frame["refresh_dem"] = dem_refresh_summary
    frame["reconcile_ledger"] = reconcile_summary
    frame["allow_degraded_dem"] = bool(args.allow_degraded_dem)
    frame["dem_frame_effective"] = frame_surface_keys(root)
    frame["synthetic_dem"] = result.get("synthetic_dem")
    frame["dem_inset_provenance"] = result.get("dem_inset_provenance")
    frame["v2"] = result.get("v2")
    frame["engine_cache_redirects"] = result.get("engine_cache_redirects")
    # WHICH per-tile cfg this build ran on, and where it came from (owner
    # ruling 2026-08-12b: lane inputs are provisioned and RECORDED — the
    # two lanes that hand-seeded two different sources on 2026-08-12 left
    # nothing in either frame to compare).
    frame["tile_cfg_provenance"] = result.get("tile_cfg_provenance")
    # ``--tile --engine``: what the cfg said vs what the run built with.
    frame["tile_engine"] = result.get("tile_engine")
    # WHICH HALVES OF THE TILE THIS BUILD ACTUALLY RAN (RULINGS
    # 2026-08-31d): a frame with no imagery provider builds the
    # geometry and stands the textures down, so the record has to
    # say so — a geometry-only tile must never read as a full one.
    frame["imagery"] = result.get("imagery")
    frame["tile_steps_run"] = result.get("steps_run")
    # ...and the steps it explicitly SKIPPED, each with its reason
    # (``run_tile_steps`` ``skip_steps`` — a recorded skip, never an
    # attempted run reported DONE): under 31d the imagery half, by name.
    frame["steps_skipped"] = result.get("steps_skipped")
    # THE SOLVE MODEL IS RETIRED (RULINGS 2026-09-13bh): no frame record,
    # no per-tile re-resolve, and no one-reader check — there is one solve
    # and no key to disagree about.  The ledger variant key keeps the
    # constant :data:`SOLVE_MODEL` component so stored arms still serve.
    frame["dem_cache_after"] = (dem_cache_state(root, lat, lon)
                                if lat is not None else None)
    (out_dir / f"{tag}.frame.json").write_text(json.dumps(frame, indent=1))
    (out_dir / f"{tag}.result.json").write_text(json.dumps(
        {k: v for k, v in result.items() if not k.startswith("_")},
        indent=1, default=str))
    if args.refresh_only:
        # NOTHING WAS BUILT, so there is no artifact to store, no census
        # to point at and no patch to report — only the refresh record.
        # rc 0 depends on the RE-JUDGED pre-flight above having passed:
        # a refresh that left the frame cold or stale raised there.
        prog.note(f"EXIT {tag} rc=0 REFRESH-ONLY wall="
                  f"{result['wall_seconds']}s")
        print(f"\n  [harness] refreshed {sorted(requested)} for tile "
              f"{lat:+d}{lon:+d}; frame re-judged CURRENT; NO build ran.")
        print(f"  [harness] record: {out_dir / (tag + '.frame.json')} "
              f"(ledger lines in {REFRESH_LEDGER})")
        return 0

    # ── THE ARTIFACT LEDGER: store this arm ──────────────────────────
    # Every successful patch build pays it forward; only a request to serve
    # (--base-arm) ever reads it back, so a plain build is unchanged apart
    # from one copy of its own products.  Two runs are deliberately NOT
    # stored: one that was authorised to refresh (its corpus stamp
    # describes a corpus it then changed) and one the write audit marked
    # CONTAMINATED (serving it later would spread a corpus mutation into
    # every arm that hits the key).
    if ledger_key and not args.tile:
        # THE STORE GATE READS EVERY DELTA, external candidates included
        # (2026-09-01, H6 item 6).  The CONTAMINATED verdict is about
        # whether THIS build's numbers are trustworthy; the store gate is
        # about whether this run's CORPUS STAMP still describes the corpus
        # a later hit would be served against.  A delta outside this
        # build's input set leaves the first question alone and moves the
        # second, so the deliberately stricter of the two governs here.
        why_not = ("an authorised --refresh-data run" if requested
                   else "the run was flagged CONTAMINATED"
                   if frame["contaminated"]
                   else "the shared repo changed inside this run's window "
                        "(external-candidate delta): the corpus stamp no "
                        "longer describes the corpus a later hit would read"
                   if offenders
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
                     "argv": sys.argv[1:], "engine": ENGINE,
                     "build_seconds": result.get("build_seconds"),
                     "wall_seconds": result.get("wall_seconds"),
                     "body_sha256": result.get("body_sha256"),
                     "shapes": result.get("shapes")},
                    # THE STORE-TIME RE-CHECK: the tree was keyed at START;
                    # a worker-pool child that outlives its parent can
                    # finish after source edits land (LEMD, 2026-08-28) and
                    # would key the pre-edit hash.  The ledger recomputes
                    # and refuses the mismatch; never re-keys.
                    code_state={"root": str(root),
                                "code_tree_hash": snapshot["code_tree_hash"],
                                "git_dirty": snapshot["git_dirty"]})
                prog.note(f"artifact ledger STORED {ledger_key[:12]} "
                          f"({rec['bytes'] / 1e6:.1f} MB) — a later "
                          f"--base-arm at this tree, env and corpus serves "
                          f"this patch instead of rebuilding it")
            except AL.ContaminatedKeyError as exc:
                # Recorded in the frame like the corpus-write flag: the
                # build's artifacts stand, its ledger entry does not, and a
                # reader of the frame sees WHY without the progress log.
                frame["contaminated_key"] = {
                    "reason": str(exc), "key": ledger_key,
                    "keyed_tree": snapshot["code_tree_hash"],
                    "keyed_git_dirty": snapshot["git_dirty"],
                    "detected_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
                (out_dir / f"{tag}.frame.json").write_text(
                    json.dumps(frame, indent=1))
                prog.note(f"artifact ledger: REFUSED store — {exc}")
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
