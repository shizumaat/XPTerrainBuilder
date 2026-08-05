"""THE BUILD ENTRY — the one way to build an airport or a tile for measurement.

    venv/bin/python tools/harness/build_airport.py ICAO [--tag NAME]
        [--patch-only | --tile LAT LON] [--out DIR] [--dem CONST_M]
        [--allow-degraded-dem] [--allow-no-sidecar] [--no-ledger]

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

WHAT IT RECORDS, always, next to the patch:

* ``<tag>.env.json`` — the environment snapshot: every ``O4_*`` variable,
  cwd, git HEAD + dirty flag, the ledger's code-tree hash, the X-Plane
  root, and the cfg-frame comparison.
* ``<tag>.frame.json`` — the DEM/inset cache state BEFORE the build and the
  layout's own ``dem_inset_provenance`` AFTER it, plus every
  ``[pav-builder]`` line the build emitted.  Quote no elevation without it.
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
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: The owner's production app config — the one the shipped app runs with.
OWNER_APP_CFG = Path("/Users/noah/XPTerrainBuilderData/Ortho4XP.cfg")

#: The X-Plane INSTALL paths a whole-tile build needs.  These are
#: install-location settings, never law gates.
XPLANE_PATH_KEYS = ("cifp_data_path", "custom_scenery_dir",
                    "custom_overlay_src")

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
)


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


def cfg_frame_diff(root, owner_cfg=OWNER_APP_CFG) -> dict:
    """Compare the DEM-surface keys of this tree's config with the owner's.

    Returns ``{key: (ours, theirs)}`` for every key that disagrees.  An
    absent owner config yields ``{}`` with ``owner_cfg_present`` False — a
    machine without the app installed cannot be held to it, and the env
    snapshot records that fact rather than pretending the frames matched.
    """
    ours = read_cfg(Path(root) / "Ortho4XP.cfg")
    theirs = read_cfg(owner_cfg)
    if not theirs:
        return {}
    return {k: (ours.get(k), theirs.get(k))
            for k in DEM_FRAME_KEYS
            if k in theirs and ours.get(k) != theirs.get(k)}


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
            f"the DEM loader would download mid-measurement or hand back an "
            f"ALL-ZERO surface.  Copy the tile's .hgt in from "
            f"XPTerrainBuilderData.")
    if not state["airports_layer"]:
        problems.append(
            f"NO cached airports OSM layer for tile "
            f"{state['tile'][0]:+d}{state['tile'][1]:+d} — airport smoothing "
            f"masks are unavailable and the surface stays UNSMOOTHED "
            f"(production smooths at apt_smoothing_pix=8).")
    if not state["airport_insets"]:
        problems.append(
            f"NO cached airport elevation insets for {state['tile_stem']} — "
            f"the build would grade against the BASE surface while "
            f"production grades against the inset-baked one.  Warm it with "
            f"tools/fetch_airport_elevation_insets.py or a production "
            f"tile build.")
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
                allow_no_sidecar: bool = False) -> dict:
    """One airport → ``<out>/<tag>.osm`` + its ``.axes.json`` sidecar."""
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
    if const_dem is not None:
        from auto_patch.constant_dem import ConstantDEM   # noqa: E402
        kw["tile_dem"] = ConstantDEM(float(const_dem))
        prog.note(f"CONSTANT-DEM world: {const_dem} m (oracle build — this "
                  f"is a DEM SOURCE substitution, not a law gate)")

    t0 = time.time()
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
        "build_seconds": round(dt, 1), "shapes": len(layout.shapes),
        "body_sha256": body_sha256(osm),
        "sidecar_present": side.exists(),
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
    ap.add_argument("--dem", type=float, default=None,
                    help="build against a CONSTANT DEM of this elevation "
                         "(the oracle world — see tools/harness/oracle.py)")
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
    args = ap.parse_args(argv)

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

    if args.tile:
        lat, lon = args.tile
    else:
        tile = resolve_tile_for(args.icao, root)
        lat, lon = tile if tile else (None, None)

    frame = {"dem_cache_before": None, "requested_constant_dem": args.dem}
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

    t0 = time.time()
    if args.tile:
        result = build_tile(lat, lon,
                            args.build_dir or str(out_dir / f"tile_{tag}"),
                            prog)
    else:
        result = build_patch(args.icao, root, out_dir, tag, prog,
                             const_dem=args.dem,
                             allow_no_sidecar=args.allow_no_sidecar)
    result["wall_seconds"] = round(time.time() - t0, 1)

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
