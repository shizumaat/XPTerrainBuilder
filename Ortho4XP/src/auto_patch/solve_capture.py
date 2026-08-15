"""SOLVE-STAGE CAPTURE — freeze phases 1-4's product, replay 5+6 alone.

The perf phase's repro cutter (charter ``docs/specs/perf-phase-charter.md``,
spec ``docs/specs/perf-p2-instruments-and-cache-spec.md`` Lane B item 1).
``tools/solve_cut.py`` is the CLI; this module is the engine half.

WHY.  A HECA airport build is ~560 s, of which the SOLVE STAGE (phases
[5] elevations + [6] feature emit) is ~420 s and phases 1-4 the rest.
Every solver iteration paid for phases 1-4 again to look at the same
input.  Capturing the solve boundary once turns each later iteration
into a replay of the part that is actually under test.

THE BOUNDARY is ``pipeline.solve_and_finalize`` — the split point
verified against the code (``finalize.compute_elevations_and_repair_
geometry`` is its first call).  ``build_airport_pavement`` builds the
call's kwargs ONCE, hands that same dict here, and then calls with it,
so the captured set and the called set cannot drift.

WHAT IS CAPTURED.  Everything the tail READS and phases 1-4 produced:
the layout (with its canonical-point registry, centerlines, pavement
records and unions), the ``Airport`` block, the OSM nodes/ways the
build loaded, ``apron_candidates``, the tile DEM handle when the driver
supplied one, the tile lat/lon, and the narrow-strip carve count.

WHAT IS **NOT** CAPTURED, and why that is safe:

``to_m``      a closure over the anchor.  Rebuilt at replay as
              ``pipeline._projection(layout.anchor)`` — the same
              construction phase 1 used (``anchor = _airport_anchor(apt)``
              then ``to_m = _projection(anchor)``, and ``layout.anchor``
              IS that anchor), so the rebuilt projection is the captured
              one, not an approximation of it.
``_progress`` the build's progress reporter.  Its own module docstring
              is the warrant: "output-only: it never touches geometry or
              elevations, so the emitted OSM patch is byte-identical
              whether or not progress is enabled."  Rebuilt from
              ``progress.for_build``.
``_build_features``
              the build-time model's inputs.  The tail reads them in
              exactly one place — the ``record_build`` call that is the
              last act before the return — so nulling them cannot move
              a vertex, and a replay MUST null them: a replayed wall is
              not a build wall, and writing one into
              ``~/.ortho4xp/auto_patch_build_times`` would poison every
              baseline derived from it.

THE ENV IS PART OF THE FRAME.  ``O4_*`` flags change what the solve
does, so the capture records them and the replay REFUSES on drift
(``--allow-env-drift`` to override, recorded).  This snapshot is the
capture's provenance, NOT the run ledger's key — ``run_with_ledger.
relevant_env()`` remains the single implementation of that.

NOT A DEFECT CUTTER.  ``tools/repro_cut.py`` is the sibling instrument:
it cuts a SITE out of a shipped patch and rebuilds it as a small
synthetic airport (fast, but auto_patch is not local, so it reproduces a
direction rather than an equality).  This one cuts a STAGE out of a
whole build and keeps the airport entire — slower, but exact: the
acceptance is a byte-identical patch body.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import pickle
import time
from pathlib import Path

#: Arm the capture by pointing this at a directory.  Unset (the
#: default) makes :func:`maybe_capture` a single ``os.environ`` lookup.
CAPTURE_ENV = "O4_SOLVE_CAPTURE"

#: Bump when the captured key set changes — an older capture then
#: refuses at replay instead of filling a parameter with a default.
#:
#: v2 (RULINGS 2026-08-14 "THE SOLVE CAPTURE HAS A BOUNDARY LEAK AT
#: DEM-DERIVED STATE"): the capture carries the composed airport DEM
#: (``elevation._DEM_CACHE``) and the build's X-Plane root.  A v1
#: capture on the AIRPORT path (``tile_dem is None``) let phases 5-6
#: call ``elevation._load_airport_dem`` at REPLAY time and read
#: whatever the shared caches held THEN — at OTHH the replay's DEM was
#: not the build's (relief 3.71→3.12 m, pads 145→191).  Every v1
#: capture therefore refuses rather than default-filling.
CAPTURE_VERSION = 2

STATE_NAME = "solve_capture.pkl.gz"
MANIFEST_NAME = "solve_capture.json"

#: The tail kwargs that are pickled verbatim.
PICKLED_KEYS = ("layout", "apt", "nodes", "ways", "apron_candidates",
                "tile_dem")
#: The tail kwargs that are plain JSON-able scalars (also pickled, so
#: the state file alone is sufficient; the manifest carries them for a
#: human reader).
SCALAR_KEYS = ("icao", "xplane_root", "current_tile_lat",
               "current_tile_lon", "compute_elevations", "_n_strip",
               "_build_started_at")
#: Rebuilt at replay rather than captured — see the module docstring.
DERIVED_KEYS = ("to_m", "_progress", "_build_features")
#: DEM-derived boundary state (capture v2) — not tail kwargs, but state
#: phases 5-6 CONSUME (the capture's contract: "the phases 1-4 product
#: at the boundary" includes everything the tail reads).  ``dem_cache``
#: is ``elevation._DEM_CACHE`` — the composed per-tile airport DEM the
#: build's own process holds (forced through ``_load_airport_dem``, the
#: same entry phases 5-6 use, so build and capture share ONE object).
#: The flat-site / sea-exclusion products are DERIVED from this DEM (the
#: flat-site substitution runs INSIDE the DEM composition; the
#: sea-exclusion percentiles read the composed raster), so carrying the
#: DEM plus the build's X-Plane root (``set_build_xplane_root`` at
#: replay) reconstructs them provably byte-equal from the same pack
#: files — the ruling's sanctioned alternative to pickling each product.
STATE_KEYS = ("dem_cache",)

#: Env keys that describe the CAPTURE, not the solve, so a difference in
#: them is not frame drift.
ENV_DRIFT_EXEMPT = frozenset({CAPTURE_ENV, "O4_ROUND_TAG"})


class CaptureError(RuntimeError):
    """A capture could not be written, or a capture cannot be replayed."""


def _env_snapshot() -> dict:
    return {k: v for k, v in sorted(os.environ.items())
            if k.startswith("O4_") and k not in ENV_DRIFT_EXEMPT}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def maybe_capture(tail: dict) -> Path | None:
    """Write a capture of ``tail`` iff :data:`CAPTURE_ENV` is set.

    ``tail`` is the very kwargs dict ``build_airport_pavement`` then
    calls ``solve_and_finalize`` with — passing the same object is what
    makes capture-vs-call drift impossible.

    Multi-airport runs (a tile build) capture EACH airport into its own
    ``<dir>/<ICAO>/`` subdirectory, so a tile capture is a set of
    per-airport captures rather than a last-one-wins overwrite.
    """
    dest = os.environ.get(CAPTURE_ENV)
    if not dest:
        return None
    return write_capture(tail, Path(dest) / str(tail["icao"]).upper())


def _dem_boundary_state(tail: dict) -> dict:
    """``elevation._DEM_CACHE`` as phases 5-6 will read it — forced warm.

    On the AIRPORT path (``tile_dem is None``) the tail's first DEM read
    (``finalize`` / ``elevation._compute_elevations``) composes the tile
    DEM through ``elevation._load_airport_dem`` and memoises it.  Capture
    runs BEFORE the tail, so the memo may be cold here: composing it now,
    through the SAME entry with the build's own root, hands the build the
    identical object via the memo — the capture is still a pure reader of
    the boundary (the build would have composed exactly this).

    On the TILE path the DEM rides ``tile_dem`` (already pickled) and the
    memo is snapshotted as-is (usually empty).
    """
    import math as _math
    from . import elevation as _elevation
    layout = tail["layout"]
    keys = set()
    if getattr(layout, "anchor", None) is not None:
        lat0, lon0 = layout.anchor
        keys.add((int(_math.floor(float(lat0))),
                  int(_math.floor(float(lon0)))))
        if (tail.get("compute_elevations")
                and tail.get("tile_dem") is None):
            _elevation._load_airport_dem(
                float(lat0), float(lon0),
                xplane_root=tail.get("xplane_root"))
    if (tail.get("current_tile_lat") is not None
            and tail.get("current_tile_lon") is not None):
        keys.add((int(tail["current_tile_lat"]),
                  int(tail["current_tile_lon"])))
    # Only the tiles THIS airport reads ride the capture — a process-wide
    # snapshot would drag other airports' composed rasters (a tile build
    # captures each airport in turn) into every capture.
    return {k: _elevation._DEM_CACHE[k] for k in sorted(keys)
            if k in _elevation._DEM_CACHE}


def write_capture(tail: dict, dest: Path) -> Path:
    """Serialize the solve-boundary state of ``tail`` into ``dest``."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    state = {k: tail[k] for k in PICKLED_KEYS + SCALAR_KEYS}
    state["dem_cache"] = _dem_boundary_state(tail)
    t0 = time.time()
    blob = dest / STATE_NAME
    try:
        with gzip.open(blob, "wb", compresslevel=1) as fh:
            pickle.dump(state, fh, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as exc:                       # pragma: no cover
        raise CaptureError(
            f"solve-stage capture failed to serialize {tail.get('icao')}: "
            f"{type(exc).__name__}: {exc}.  The capture is an instrument, "
            f"not a build input — re-run without {CAPTURE_ENV} to build.")
    layout = tail["layout"]
    manifest = {
        "capture_version": CAPTURE_VERSION,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "boundary": "auto_patch.pipeline.solve_and_finalize",
        "state_file": STATE_NAME,
        "state_sha256": _sha256(blob),
        "state_bytes": blob.stat().st_size,
        "capture_seconds": round(time.time() - t0, 2),
        "anchor": list(layout.anchor) if layout.anchor else None,
        "counts": {
            "shapes": len(layout.shapes),
            "osm_nodes": len(tail["nodes"] or ()),
            "osm_ways": len(tail["ways"] or ()),
            "apron_candidates": len(tail["apron_candidates"] or ()),
        },
        "tile_dem": None if tail["tile_dem"] is None
                    else type(tail["tile_dem"]).__name__,
        # v2: the composed airport DEM(s) riding the capture, named per
        # 1° tile key for the human reader (the state file carries the
        # objects themselves).
        "dem_cache": sorted(f"{k[0]:+03d}{k[1]:+04d}"
                            for k in state["dem_cache"]),
        "env": _env_snapshot(),
        **{k: tail[k] for k in SCALAR_KEYS},
    }
    (dest / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return dest


def read_manifest(src: Path) -> dict:
    """The capture manifest at ``src`` (a capture directory)."""
    src = Path(src)
    path = src / MANIFEST_NAME
    if not path.exists():
        raise CaptureError(
            f"{src} is not a solve capture: no {MANIFEST_NAME}.  A capture "
            f"is written by a build armed with {CAPTURE_ENV} "
            f"(harness: build_airport.py --solve-capture DIR).")
    return json.loads(path.read_text())


def env_drift(manifest: dict) -> dict:
    """``{key: (captured, live)}`` for every ``O4_*`` flag that moved.

    The solve reads these; a replay under a different set is measuring a
    different law, so the tool refuses on a non-empty result.
    """
    was = dict(manifest.get("env") or {})
    now = _env_snapshot()
    keys = set(was) | set(now)
    return {k: (was.get(k), now.get(k))
            for k in sorted(keys) if was.get(k) != now.get(k)}


def load_capture(src: Path) -> tuple[dict, dict]:
    """Rebuild the full ``solve_and_finalize`` kwargs from a capture.

    Returns ``(tail_kwargs, manifest)``.  The derived members are
    reconstructed here (see the module docstring): ``to_m`` from the
    layout anchor, ``_progress`` from ``progress.for_build``, and
    ``_build_features`` forced to ``None`` so a replay can never write
    the build-time model.
    """
    src = Path(src)
    manifest = read_manifest(src)
    got = int(manifest.get("capture_version", -1))
    if got != CAPTURE_VERSION:
        raise CaptureError(
            f"capture version {got} != {CAPTURE_VERSION} — the captured key "
            f"set changed since this capture was taken.  Re-capture; a "
            f"replay that default-filled a missing key would silently be a "
            f"different solve.")
    blob = src / manifest.get("state_file", STATE_NAME)
    if not blob.exists():
        raise CaptureError(f"capture state file missing: {blob}")
    have = _sha256(blob)
    if have != manifest.get("state_sha256"):
        raise CaptureError(
            f"capture state {blob} does not match its manifest sha "
            f"({have[:12]} vs {str(manifest.get('state_sha256'))[:12]}) — "
            f"the fixture was modified after it was cut.")
    with gzip.open(blob, "rb") as fh:
        state = pickle.load(fh)
    missing = [k for k in PICKLED_KEYS + SCALAR_KEYS + STATE_KEYS
               if k not in state]
    if missing:
        raise CaptureError(f"capture is missing {missing}")

    from . import pipeline as _pipeline
    from . import progress as _progress_mod
    layout = state["layout"]
    if layout.anchor is None:
        raise CaptureError(
            "captured layout has no anchor — to_m cannot be rebuilt")
    # ── v2: install the DEM-derived boundary state (the leak's fix) ──
    # The replay's phases 5-6 must read the BUILD's DEM, not whatever the
    # shared caches compose at replay time.  Installing the captured
    # objects into ``elevation._DEM_CACHE`` makes ``_load_airport_dem``
    # return them without touching disk; recording the build's X-Plane
    # root (as ``build_airport_pavement`` did at phase 0) makes every
    # flat-site / pack read inside the tail resolve against the same
    # install the build read.
    from . import elevation as _elevation
    from . import flat_site_mode as _flat_site_mode
    _flat_site_mode.set_build_xplane_root(state["xplane_root"])
    for _k, _dem in (state["dem_cache"] or {}).items():
        _elevation._DEM_CACHE[_k] = _dem
    tail = {k: state[k] for k in PICKLED_KEYS + SCALAR_KEYS}
    tail["to_m"] = _pipeline._projection(layout.anchor)
    tail["_progress"] = _progress_mod.for_build(
        state["icao"], compute_elevations=state["compute_elevations"])
    # NEVER a build-time-model write from a replay (module docstring).
    tail["_build_features"] = None
    return tail, manifest


def replay(src: Path):
    """Run phases [5]+[6] from the capture at ``src``; return the layout.

    The caller owns the shared-repo write guard and the emit — this is
    the solve, nothing else.
    """
    from . import pipeline as _pipeline
    tail, _manifest = load_capture(src)
    return _pipeline.solve_and_finalize(**tail)
