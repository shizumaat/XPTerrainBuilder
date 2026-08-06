"""THE BUILD ENTRY — the one way to build an airport or a tile for measurement.

    venv/bin/python tools/harness/build_airport.py ICAO [--tag NAME]
        [--patch-only | --tile LAT LON] [--out DIR] [--dem CONST_M]
        [--allow-degraded-dem] [--allow-no-sidecar] [--no-ledger]
        [--refresh-data SCOPE[,SCOPE...]] [--break-stale-lock]
        [--allow-private-data]

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
* the patch body sha256 (``tail -n +3``: the provenance stamp makes the raw
  file hash useless for A/B identity).

Consolidated from (and replacing): ``tools/full_airport_build.py``,
``scratchpad/integrate/build.sh``, ``scratchpad/refpull_interim/arm.sh``
and ``arm.py``, ``scratchpad/reltiles/run_release_tile.py`` and
``buildtile.sh``.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: THE shared data repo (owner ruling e9daef5).  Every lane mounts it; no
#: lane redownloads or regenerates a cache into a private corpus.
DATA_REPO = Path(os.environ.get("O4_DATA_REPO",
                                "/Users/noah/XPTerrainBuilderData"))
HARNESS_STATE = DATA_REPO / ".harness"
LOCK_DIR = HARNESS_STATE / "locks"
REFRESH_LEDGER = HARNESS_STATE / "refresh_ledger.jsonl"

#: The owner's production app config — the one the shipped app runs with.
#: It lives IN the shared data repo, which is the point: the config and the
#: corpus it describes travel together.
OWNER_APP_CFG = DATA_REPO / "Ortho4XP.cfg"

#: The data directories a lane mounts from the shared repo.  Products
#: (Patches, Tiles, Previews, tmp) are deliberately NOT here — every tile
#: build writes its emitted patches into Patches/, so sharing it would put
#: one lane's geometry into another lane's build.
SHARED_DATA_DIRS = ("OSM_data", "Elevation_data", "Airport_mod_cache",
                    "Geotiffs", "Masks", "Default_DSF_cache", "Orthophotos")

#: The REGENERABLE artifact classes, most specific prefix first.  A build
#: may regenerate any of these implicitly today; under the ruling it may
#: not, so each one is a named ``--refresh-data`` scope instead.
REFRESH_SCOPES = (
    ("osm_roadfeed", "OSM_data/_airport_road_feed",
     "the per-airport ROAD FEED sidecar.  THE NAMED PRECEDENT: a KCLT "
     "road-feed refresh ran as a tile-build side effect on 2026-08-05 "
     "01:47-01:55 and silently changed campaign hashes — every later "
     "build read a different feed and nobody was told"),
    ("osm_layers", "OSM_data",
     "cached OSM layers and regional extracts (overpass downloads)"),
    ("dem", "Elevation_data",
     "base DEM rasters and airport elevation insets (provider downloads)"),
    ("airport_mod_cache", "Airport_mod_cache",
     "third-party apt.dat pack indexes and sidecars"),
    ("dsf_cache", "Default_DSF_cache",
     "DSFTool text dumps of X-Plane's default scenery"),
    ("masks", "Masks", "water/coastline mask rasters"),
    ("orthophotos", "Orthophotos", "downloaded imagery tiles"),
    ("geotiffs", "Geotiffs", "user-supplied geotiff sources"),
)

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


def scope_of(relpath: str):
    """The ``--refresh-data`` scope a shared-repo path belongs to, most
    specific prefix first.  ``None`` for a path outside every scope."""
    rel = str(relpath)
    for name, prefix, _why in REFRESH_SCOPES:
        if rel == prefix or rel.startswith(prefix + "/"):
            return name
    return None


def scope_description(name: str) -> str:
    for scope, _prefix, why in REFRESH_SCOPES:
        if scope == name:
            return why
    return "(unknown scope)"


def shared_repo_snapshot(repo=None) -> dict:
    """``{relative path: (size, mtime_ns)}`` for every file in the shared
    repo's data directories.

    A FULL walk on purpose: the whole surface is ~2.7 k files and the walk
    costs ~10 ms, so there is no reason to sample and then argue about what
    a coarse tripwire missed.  Completeness is the point — the guarantee is
    "this build wrote nothing into the shared repo", and a partial snapshot
    cannot make it.
    """
    repo = Path(repo or DATA_REPO)
    snap = {}
    for name in SHARED_DATA_DIRS:
        top = repo / name
        if not top.is_dir():
            continue
        for dirpath, _dirnames, filenames in os.walk(top):
            for fn in filenames:
                p = Path(dirpath) / fn
                try:
                    st = p.stat()
                except OSError:
                    continue
                snap[str(p.relative_to(repo))] = (st.st_size, st.st_mtime_ns)
    return snap


def snapshot_diff(before: dict, after: dict) -> dict:
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(k for k in (set(after) & set(before))
                      if after[k] != before[k])
    return {"added": added, "modified": modified, "removed": removed}


def _file_stamp(repo: Path, rel: str, max_hash_bytes: int = 64 * 1024 * 1024):
    """Hash-stamp one file.  Small files get a sha256; a multi-gigabyte
    imagery tile gets size+mtime, because hashing it would cost more than
    the refresh did and the identity question it answers is the same."""
    p = repo / rel
    try:
        st = p.stat()
    except OSError:
        return {"path": rel, "missing": True}
    out = {"path": rel, "size": st.st_size, "mtime_ns": st.st_mtime_ns}
    if st.st_size <= max_hash_bytes:
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        out["sha256"] = h.hexdigest()
    else:
        out["sha256"] = None
        out["note"] = "too large to hash; size+mtime stamped instead"
    return out


class RefreshLock:
    """A shared-repo write lock, one per scope.

    REFUSE-AND-REPORT, never block (ruling e9daef5 §3).  A lane that waits
    silently on another lane's download looks like a hung build, and a lane
    that ignores the lock races a half-written cache into every other lane's
    next measurement.  A dead holder is reported with its lane and pid and
    needs ``--break-stale-lock`` — never broken automatically, because
    "the pid is gone" and "the write finished" are different facts.
    """

    def __init__(self, scope: str, lane: str, break_stale: bool = False):
        self.scope = scope
        self.lane = lane
        self.break_stale = break_stale
        self.path = LOCK_DIR / f"{scope}.lock"
        self.held = False

    def _payload(self) -> dict:
        return {"scope": self.scope, "lane": self.lane, "pid": os.getpid(),
                "host": os.uname().nodename,
                "started": time.strftime("%Y-%m-%dT%H:%M:%S")}

    @staticmethod
    def _alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def acquire(self) -> "RefreshLock":
        LOCK_DIR.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                         0o644)
        except FileExistsError:
            try:
                holder = json.loads(self.path.read_text())
            except Exception:
                holder = {}
            pid = int(holder.get("pid") or -1)
            alive = self._alive(pid) if pid > 0 else False
            if alive or not self.break_stale:
                raise SystemExit(
                    f"REFUSING: another lane holds the '{self.scope}' "
                    f"refresh lock on the shared repo.\n"
                    f"  holder: lane={holder.get('lane')!r} pid={pid} "
                    f"host={holder.get('host')!r} since "
                    f"{holder.get('started')} "
                    f"({'ALIVE' if alive else 'DEAD — stale lock'})\n"
                    f"  lock:   {self.path}\n"
                    + ("  Wait for it and re-run.  The harness never blocks "
                       "silently on a shared-repo write: a lane waiting on "
                       "another lane's download is indistinguishable from a "
                       "hung build."
                       if alive else
                       "  The holder is gone, but a dead pid does not mean "
                       "the write COMPLETED — the cache may be half-written. "
                       "Inspect it, then re-run with --break-stale-lock."))
            self.path.unlink()
            print(f"  [harness] broke STALE '{self.scope}' lock (holder pid "
                  f"{pid} is gone, --break-stale-lock given)")
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                         0o644)
        with os.fdopen(fd, "w") as fh:
            json.dump(self._payload(), fh)
        self.held = True
        return self

    def release(self) -> None:
        if self.held:
            try:
                self.path.unlink()
            except OSError:
                pass
            self.held = False

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
        return False


def record_refresh(scope: str, changes: dict, meta: dict,
                   repo=None) -> dict:
    """Append ONE hash-stamped refresh event to the shared repo's ledger.

    "Exactly once, as an explicit logged event" (ruling §2) needs a record
    that outlives the session: the ledger lives in the SHARED repo, so the
    next lane to wonder why a cache changed reads the answer there instead
    of reconstructing it from three lanes' scratchpads.
    """
    repo = Path(repo or DATA_REPO)
    stamps = [_file_stamp(repo, rel)
              for rel in (changes["added"] + changes["modified"])]
    record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "scope": scope,
              "added": len(changes["added"]),
              "modified": len(changes["modified"]),
              "removed": changes["removed"], "files": stamps, **meta}
    REFRESH_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(REFRESH_LEDGER, "a") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        fh.write(json.dumps(record) + "\n")
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    return record


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


class SharedRepoWriteBlocked(RuntimeError):
    """A build tried to write the shared data repo outside an authorised
    ``--refresh-data`` scope, and the guard stopped it."""


class SharedRepoWriteGuard:
    """THE PREVENTER (fix cycle 2 item 4).

    The detector below is the backstop; this is the lock.  It refuses the
    write AT THE CALL, from inside the build process, naming the path, the
    scope, and the flag that would authorise it — so the offending write
    surfaces with a traceback pointing at the code that made it, instead of
    as a filename in an after-the-fact diff.

    WHY A PREVENTER WAS NEEDED.  ``report_unauthorised_writes`` used to
    carry the line "the harness cannot PREVENT a write inside the engine
    without touching ``src/``".  That was true of a *filesystem* lock and
    false of the interpreter: the harness calls ``build_airport_pavement``
    IN PROCESS, so it owns the same ``builtins.open`` and ``os`` the engine
    will use.  The re-baseline settled the question by catching two LIVE
    instances — ``OSM_data/_airport_road_feed/CYXY_road_feed.cache`` and
    ``SPLP_road_feed.cache``, written by the CYXY and SPLP builds — after
    the fact, from six concurrent runs whose before/after snapshots each
    saw BOTH writes.  Detection alone therefore produced a
    ``contaminated=True`` flag that was CROSS-ATTRIBUTED across lanes and a
    corpus that had already changed under everyone.  Only refusing at the
    call site attributes the write to its author and leaves the corpus
    intact.

    SCOPE, stated honestly.  This intercepts writes issued through the
    Python level: ``builtins.open`` in a writing mode, ``os.open`` with a
    writing flag, and the rename/replace/unlink/mkdir family.  A write
    performed inside a C extension's own file handling (GDAL, a bare
    ``numpy.memmap``) does not pass through these, which is exactly why the
    before/after snapshot audit STAYS: prevent what can be prevented,
    detect the remainder.  Defence in depth, not one mechanism claimed to
    be complete.

    ALWAYS-ALLOWED: the harness's own state directory (``.harness/`` — the
    refresh ledger and the lock files), and every path under an authorised
    scope.  Reads are never touched.
    """

    #: ``os.open`` flags that mean "this call can modify the file".
    _WRITE_FLAGS = (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT
                    | os.O_TRUNC)

    def __init__(self, requested, root, repo=None, enabled: bool = True):
        self.requested = set(requested or ())
        self.repo = Path(repo or DATA_REPO)
        self.enabled = bool(enabled)
        self.blocked: list = []
        # Cheap textual prefixes: the shared repo itself, and this lane's
        # mount points (which are SYMLINKS into it, so a relative
        # ``OSM_data/...`` write never mentions the repo path at all).
        # ABSOLUTE on both sides — the candidate path is abspath'd before
        # the compare, so a relative prefix would never match and the guard
        # would pass everything while looking installed.
        lane = Path(root).resolve()
        self._prefixes = tuple(
            str(p) for p in
            [self.repo.resolve() / d for d in SHARED_DATA_DIRS]
            + [lane / d for d in SHARED_DATA_DIRS])
        self._saved: dict = {}

    # ── the predicate ────────────────────────────────────────────────
    def _violation(self, path):
        """``(rel, scope)`` if writing ``path`` is forbidden, else None."""
        try:
            s = os.fspath(path)
        except TypeError:
            return None                        # an fd, not a path
        if not isinstance(s, (str, bytes)):
            return None
        if isinstance(s, bytes):
            s = s.decode("utf-8", "replace")
        ap = s if os.path.isabs(s) else os.path.abspath(s)
        if not ap.startswith(self._prefixes):
            return None                        # cheap reject: the hot path
        try:                                   # follow the lane's symlinks
            real = Path(ap).resolve()
            rel = str(real.relative_to(self.repo.resolve()))
        except (OSError, ValueError):
            return None                        # not in the shared repo
        if rel.startswith(".harness"):
            return None                        # the harness's own state
        scope = scope_of(rel)
        if scope in self.requested:
            return None
        return rel, scope

    def _refuse(self, rel, scope, how):
        self.blocked.append({"path": rel, "scope": scope, "via": how})
        raise SharedRepoWriteBlocked(
            f"BLOCKED: this build tried to {how} '{rel}' in the SHARED data "
            f"repo ({self.repo}), which no --refresh-data scope authorises.\n"
            f"  scope: {scope or '<outside every named scope>'}"
            + (f"\n  {scope_description(scope)}" if scope else "")
            + f"\nOwner ruling e9daef5: a cache regeneration is an EXPLICIT, "
              f"locked, hash-stamped event — never a build side effect. Every "
              f"other lane reads this corpus.\n"
              f"To do it deliberately, re-run with: --refresh-data "
              f"{scope or ','.join(sorted(s for s, _p, _w in REFRESH_SCOPES))}")

    # ── installation ─────────────────────────────────────────────────
    def __enter__(self):
        if not self.enabled:
            return self
        import builtins
        import shutil
        guard = self

        real_open, real_os_open = builtins.open, os.open
        self._saved = {"open": real_open, "os_open": real_os_open}

        def _open(file, mode="r", *a, **kw):
            if any(c in mode for c in "wxa+"):
                hit = guard._violation(file)
                if hit:
                    guard._refuse(hit[0], hit[1], "open for writing")
            return real_open(file, mode, *a, **kw)

        def _os_open(path, flags, *a, **kw):
            if flags & guard._WRITE_FLAGS:
                hit = guard._violation(path)
                if hit:
                    guard._refuse(hit[0], hit[1], "os.open for writing")
            return real_os_open(path, flags, *a, **kw)

        builtins.open, os.open = _open, _os_open

        # The mutating path operations.  ``src``-side arguments are checked
        # too for the two-path calls: a rename OUT of the repo destroys the
        # cached artifact just as surely as one into it.
        for name, n_paths in (("rename", 2), ("replace", 2), ("remove", 1),
                              ("unlink", 1), ("rmdir", 1), ("mkdir", 1),
                              ("makedirs", 1), ("truncate", 1)):
            real = getattr(os, name, None)
            if real is None:
                continue
            self._saved[name] = real

            def _wrap(*a, _real=real, _n=n_paths, _nm=name, **kw):
                for p in a[:_n]:
                    hit = guard._violation(p)
                    if hit:
                        guard._refuse(hit[0], hit[1], f"os.{_nm}")
                return _real(*a, **kw)

            setattr(os, name, _wrap)

        # shutil's copy family opens through ``builtins.open`` on CPython,
        # but ``move`` can fall through to ``os.rename`` on the same device
        # and ``copytree`` builds directories first — both already covered
        # above.  Nothing further to patch; recorded so the next reader does
        # not re-derive it.
        del shutil
        return self

    def __exit__(self, *exc):
        if not self.enabled:
            return False
        import builtins
        if "open" in self._saved:
            builtins.open = self._saved.pop("open")
        if "os_open" in self._saved:
            os.open = self._saved.pop("os_open")
        for name, real in self._saved.items():
            setattr(os, name, real)
        self._saved = {}
        return False


def report_unauthorised_writes(changes: dict, requested: set,
                               prog) -> list:
    """Every shared-repo write this build made outside an authorised scope.

    THE BACKSTOP.  :class:`SharedRepoWriteGuard` refuses these at the call
    site now; this still runs, because the guard covers the Python level
    and a C extension's own file handling does not pass through it.  A
    write that reaches here got past the lock, so it is named with its
    path, its scope, and a CONTAMINATED marker on the run — a corpus that
    changed mid-build is not the corpus the run started on, and its numbers
    are not comparable with the ones before it.
    """
    offenders = []
    for kind in ("added", "modified", "removed"):
        for rel in changes[kind]:
            scope = scope_of(rel)
            if scope in requested:
                continue
            offenders.append({"path": rel, "kind": kind, "scope": scope})
    if not offenders:
        prog.note("shared repo UNCHANGED by this build (full-surface "
                  "before/after snapshot) — no side-effect mutation")
        return offenders
    prog.note(f"!! SHARED-REPO SIDE EFFECT: this build wrote "
              f"{len(offenders)} path(s) NOBODY authorised — owner ruling "
              f"e9daef5 forbids exactly this.  The run is CONTAMINATED: "
              f"every lane's next build reads the changed corpus.")
    by_scope: dict = {}
    for o in offenders:
        by_scope.setdefault(o["scope"] or "<outside every scope>",
                            []).append(o)
    for scope, items in sorted(by_scope.items(), key=lambda kv: str(kv[0])):
        prog.note(f"   [{scope}] {len(items)} path(s); "
                  f"e.g. {items[0]['kind']} {items[0]['path']}")
        if scope in {s for s, _p, _w in REFRESH_SCOPES}:
            prog.note(f"      {scope_description(scope)}")
    prog.note(f"   Re-run with --refresh-data "
              f"{','.join(sorted({str(o['scope']) for o in offenders}))} "
              f"to make this an EXPLICIT, locked, hash-stamped refresh.")
    return offenders


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
                write_guard=None) -> dict:
    """One airport → ``<out>/<tag>.osm`` + its ``.axes.json`` sidecar.

    ``write_guard`` — a :class:`SharedRepoWriteGuard` (or ``None`` for the
    default: nothing authorised, guard ARMED).  It is armed HERE, not in
    ``main``, because ``main`` is not the only entry that builds:
    ``tools/harness/oracle.py`` and ``tools/harness/who_wrote.py`` both
    call this function directly, and those are the entries a lane actually
    runs most.  Arming in the CLI only would have left every oracle and
    every authorship trace free to regenerate the shared corpus — the
    precise hole the road-feed precedent went through.
    """
    for p in (root / "src", root, root / "tests", root / "tools"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    from conftest import xplane_root                      # noqa: E402
    from auto_patch.pipeline import build_airport_pavement  # noqa: E402
    from auto_patch import config as ap_cfg               # noqa: E402
    # The sidecar is gated on this: without it every census silently
    # degrades to the context-free frame.
    ap_cfg.LOG_VERBOSITY = max(1, getattr(ap_cfg, "LOG_VERBOSITY", 0))

    kw = {"compute_elevations": True}
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

    guard = write_guard if write_guard is not None else SharedRepoWriteGuard(
        set(), root)
    t0 = time.time()
    with guard:
        layout = build_airport_pavement(icao, xplane_root(), **kw)
    dt = time.time() - t0
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
        "build_seconds": round(dt, 1), "shapes": len(layout.shapes),
        "body_sha256": body_sha256(osm),
        "sidecar_present": side.exists(),
        "write_guard_armed": guard.enabled,
        "write_guard_blocked": list(guard.blocked),
        "dem_frame_effective": frame_surface_keys(root),
        "dem_inset_provenance": getattr(layout, "dem_inset_provenance", None),
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
    tile.read_from_config()
    prog.note(f"tile {lat:+d}{lon:+d} build_dir={tile.build_dir} "
              f"website={tile.default_website} zl={tile.default_zl} "
              f"auto_patch={tile.auto_patch} "
              f"modify_custom_airports={tile.modify_custom_airports}")
    if not tile.default_website:
        raise SystemExit(
            "REFUSING: tile config resolves to an EMPTY default_website — "
            "step 4 would produce provider-less texture names.")

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
            "step_seconds": timings, "xplane_paths": paths}


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
                         "KNOWINGLY (recorded in the env snapshot)")
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
    ap.add_argument("--allow-private-data", action="store_true",
                    help="build against a PRIVATE data corpus instead of "
                         "the shared repo, KNOWINGLY (recorded); its "
                         "numbers are not comparable with any other lane's")
    args = ap.parse_args(argv)
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

    t0 = time.time()
    try:
        if args.tile:
            with guard:                    # build_patch arms its own
                result = build_tile(
                    lat, lon,
                    args.build_dir or str(out_dir / f"tile_{tag}"), prog)
        else:
            result = build_patch(args.icao, root, out_dir, tag, prog,
                                 const_dem=args.dem,
                                 allow_no_sidecar=args.allow_no_sidecar,
                                 write_guard=guard)
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
                                      "argv": sys.argv[1:]})
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
    frame["dem_frame_effective"] = frame_surface_keys(root)
    frame["synthetic_dem"] = result.get("synthetic_dem")
    frame["dem_inset_provenance"] = result.get("dem_inset_provenance")
    frame["dem_cache_after"] = (dem_cache_state(root, lat, lon)
                                if lat is not None else None)
    (out_dir / f"{tag}.frame.json").write_text(json.dumps(frame, indent=1))
    (out_dir / f"{tag}.result.json").write_text(json.dumps(
        {k: v for k, v in result.items() if not k.startswith("_")},
        indent=1, default=str))
    prog.note(f"EXIT {tag} rc=0 wall={result['wall_seconds']}s")
    print(f"\n  [harness] artifacts in {out_dir}: {tag}.osm(+.axes.json), "
          f"{tag}.env.json, {tag}.frame.json, {tag}.result.json, "
          f"{tag}.progress")
    print(f"  [harness] next: venv/bin/python tools/harness/census.py "
          f"{out_dir / (tag + '.osm')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
