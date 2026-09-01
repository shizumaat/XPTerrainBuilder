"""Pytest configuration shared by all tests.

* Adds the project's ``src/`` directory to ``sys.path`` so tests can
  import the O4 modules directly without installing the package.
* Provides the airport-discovery + ship-mode toggle helpers used by
  the integration test suites (overlap, junction invariants, grade,
  geometry, …) so airports are not hard-coded in any test file.

Environment variables (per user 2026-04-30):
* ``O4_TEST_TILE=lat,lon`` — discover every airport whose runways
  fall in that 1°×1° tile via the project's CIFP scanner.  This
  matches "all airports in the tile being built".
* ``O4_TEST_AIRPORTS=ICAO1,ICAO2,…`` — explicit ICAO list, takes
  precedence over ``O4_TEST_TILE`` when both are set.
* ``O4_SHIP_MODE=1`` — skip every integration test (used at
  shipping time when tests should not run).  All test modules
  collect normally but each item is marked skip.
* ``XPLANE_ROOT`` — X-Plane install path used by every test that
  needs CIFP / DEM / apt.dat data.  Defaults to
  ``/Users/noah/X-Plane 12``.

When neither ``O4_TEST_TILE`` nor ``O4_TEST_AIRPORTS`` is set, the
discovery returns an empty list and parametrised integration tests
collect zero items.  This is intentional: the project should not
ship a hidden hard-coded list of canonical airports — every run
must be explicit about what it tests against.
"""
import json
import os
import sys
from typing import List, Optional

# No test may reach the network: the parallel-build OpenStreetMap cache
# warmer (o4_engine.parallel) is disabled suite-wide; tests that exercise
# the warmer itself delete this variable and stub the download modules.
os.environ.setdefault("O4_DISABLE_OSM_WARMER", "1")

# No test may reach the platform secret store either: provider-session
# code paths (O4_Authenticated_Sessions.load_credentials/load_api_key)
# lazily import ``keyring``, and on a machine with real stored sign-ins
# that walks into the macOS Keychain — 2026-07-23 the suite blocked four
# xdist workers on "Python wants to access your keychain" dialogs.  A
# backend-less fake is installed BEFORE anything imports keyring: every
# lookup reports "no usable store", which is exactly what headless tests
# must see.  Tests exercising the store itself install their own fakes
# on top (and monkeypatch restores this one afterwards).
import types as _types


class _NoKeychainInTests:
    """Stand-in backend advertising itself as keyring's fail backend."""


_NoKeychainInTests.__module__ = "keyring.backends.fail"


def _make_fake_keyring():
    fake_errors = _types.ModuleType("keyring.errors")

    class KeyringError(Exception):
        pass

    class PasswordDeleteError(KeyringError):
        pass

    fake_errors.KeyringError = KeyringError
    fake_errors.PasswordDeleteError = PasswordDeleteError

    fake = _types.ModuleType("keyring")
    fake.errors = fake_errors
    fake.get_keyring = lambda: _NoKeychainInTests()

    def _no_store(*_args, **_kwargs):
        raise KeyringError("test suite: platform secret store is off-limits")

    fake.get_password = _no_store
    fake.set_password = _no_store
    fake.delete_password = _no_store
    return fake, fake_errors


_fake_keyring, _fake_keyring_errors = _make_fake_keyring()
sys.modules["keyring"] = _fake_keyring
sys.modules["keyring.errors"] = _fake_keyring_errors

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def xplane_root() -> str:
    return os.environ.get("XPLANE_ROOT", "/Users/noah/X-Plane 12")


# ══════════════════════════════════════════════════════════════════════
# THE SYNTHETIC EMITTED PATCH — one writer, every law-reader twin
# ══════════════════════════════════════════════════════════════════════
# A census twin needs an emitted patch AND its axes sidecar: without the
# sidecar ``run_checks_law_true`` refuses, and with a hand-built one that
# drops a key the twin judges a different law than the build ran (both
# frame errors this repo has had were exactly that).  Writing that pair
# by hand in each test file is the census-wrapper defect at fixture
# scale, so it is written HERE, once.
#
# Coordinates are METRES about ``(lat0, lon0)``, which is the frame
# ``check_grade._ll_to_m_factory`` reconstructs from the sidecar anchor.
SYNTHETIC_PATCH_M_PER_DEG = 111320.0


def write_synthetic_patch(tmp_path, ways, *, sidecar=None,
                          name: str = "patch.osm",
                          lat0: float = 0.0, lon0: float = 0.0):
    """Write a minimal emitted patch + ``.axes.json`` sidecar; return the
    ``.osm`` path.

    ``ways`` — an iterable of dicts::

        {"role": "service_road",       # the ``role`` tag the law reads
         "ring": [(x_m, y_m, z_m), …], # per-node, in metres/altitude
         "ref": "SVC1",                # optional
         "closed": True,               # rings close, breaklines do not
         "o4_feature": "crown_spine",  # optional OPEN feature way
         "tags": {...}}                # optional extra way tags

    Elevations are emitted as per-node ``alt_abs``, the form production
    writes and ``check_grade._derive_per_vertex_elevations`` reads.

    ``sidecar`` — extra law keys (``axes_exact``, ``crown_drops``,
    ``ruleset``, …) merged over ``{"anchor": [lat0, lon0], "ruleset":
    "icao"}``.  Every key travels through
    ``check_grade.law_context_from_sidecar``; nothing here parses it.
    """
    node_lines, way_lines = [], []
    nid, wid = 0, -1
    for spec in ways:
        ring = list(spec["ring"])
        nids = []
        for (x, y, z) in ring:
            nid -= 1
            lat = lat0 + y / SYNTHETIC_PATCH_M_PER_DEG
            lon = lon0 + x / SYNTHETIC_PATCH_M_PER_DEG
            node_lines.append(
                f"  <node id='{nid}' action='modify' visible='true' "
                f"lat='{lat:.11f}' lon='{lon:.11f}'>\n"
                f"    <tag k='alt_abs' v='{float(z):.2f}' />\n"
                f"  </node>")
            nids.append(nid)
        seq = nids + ([nids[0]] if spec.get("closed", True) else [])
        body = "".join(f"    <nd ref='{n}' />\n" for n in seq)
        tags = {"role": spec.get("role", ""),
                "aeroway": spec.get("aeroway", spec.get("role", "")),
                "ref": spec.get("ref", "")}
        if spec.get("o4_feature"):
            tags["o4_feature"] = spec["o4_feature"]
        tags.update(spec.get("tags") or {})
        tag_lines = "".join(f"    <tag k='{k}' v='{v}' />\n"
                            for k, v in tags.items() if v != "")
        way_lines.append(
            f"  <way id='{wid}' action='modify' visible='true'>\n"
            f"{body}{tag_lines}  </way>")
        wid -= 1
    osm = tmp_path / name
    osm.write_text("<?xml version='1.0' encoding='UTF-8'?>\n"
                   "<osm version='0.6'>\n"
                   + "\n".join(node_lines) + "\n"
                   + "\n".join(way_lines) + "\n</osm>\n")
    side = {"anchor": [lat0, lon0], "ruleset": "icao"}
    side.update(sidecar or {})
    (tmp_path / (name + ".axes.json")).write_text(json.dumps(side))
    return osm


def synthetic_patch_ll(x_m: float, y_m: float, *,
                       lat0: float = 0.0, lon0: float = 0.0):
    """The ``(lat, lon)`` of a synthetic-patch metre coordinate — used to
    spell sidecar geometry (axes, crown drops) in the SAME frame the
    ways were written in."""
    return (lat0 + y_m / SYNTHETIC_PATCH_M_PER_DEG,
            lon0 + x_m / SYNTHETIC_PATCH_M_PER_DEG)


def xplane_available() -> bool:
    root = xplane_root()
    return (os.path.isdir(root)
            and os.path.isdir(os.path.join(root, "Custom Data", "CIFP")))


import functools


@functools.lru_cache(maxsize=None)
def _build_cached(icao: str, compute_elevations: bool,
                  tile_lat, tile_lon):
    """Build one airport layout, memoised for the worker's session.

    A full ``build_airport_pavement`` is the dominant cost of the suite
    (each airport ~30-60 s of geometry + elevation solve), and many
    test modules each need the SAME layout.  This single shared cache
    replaces the per-module ``_LAYOUT_CACHE`` dicts (and the modules
    that rebuilt per-test) so every (icao, params) combination is built
    AT MOST ONCE per worker process.  Combined with ``--dist loadgroup``
    + the per-airport ``xdist_group`` assigned in
    ``pytest_collection_modifyitems`` below, all of an airport's tests
    run on one worker → exactly one build per airport per run.

    The per-tile DEM is built INSIDE (so the cache key stays hashable) via
    ``_load_airport_dem(tile_center)`` — the SMOOTHED (apt_smoothing_pix=8)
    surface that production ships, the SAME one the grade test uses.
    Previously this used a RAW ``O4DEM(... fill_nodata='to zero')``, which
    produces a different surface (more terrain-extrema rect splits → e.g.
    SPLP 259 vs 250 shapes) than what X-Plane renders.  Unifying on the
    smoothed DEM makes every per-tile build (grade / compare_target /
    tile_cut) production-accurate AND identical for a given tile, so they
    all share ONE cached build per tile.

    NOTE: callers treat the returned layout as READ-ONLY — it is shared
    across every test for that airport.  Do not mutate it in place.
    """
    from auto_patch.pipeline import build_airport_pavement
    if tile_lat is not None and tile_lon is not None:
        from auto_patch.elevation import _load_airport_dem
        dem = _load_airport_dem(tile_lat + 0.5, tile_lon + 0.5)
        return build_airport_pavement(
            icao, xplane_root(), compute_elevations=compute_elevations,
            tile_dem=dem, current_tile_lat=tile_lat,
            current_tile_lon=tile_lon)
    return build_airport_pavement(
        icao, xplane_root(), compute_elevations=compute_elevations)


def cached_airport_layout(icao: str, *, compute_elevations: bool = True,
                          tile_lat=None, tile_lon=None):
    """Session-cached ``build_airport_pavement`` shared by all test
    modules.  See :func:`_build_cached`.  Treat the result as read-only.
    """
    return _build_cached(icao, compute_elevations, tile_lat, tile_lon)


def is_tile_seam_vertex(layout, x: float, y: float,
                        tol_m: Optional[float] = None) -> bool:
    """True if local-metre point ``(x, y)`` lies on a tile-cut seam.

    ``tile_cut`` slices every shape crossing an integer lat/lon tile
    boundary, buffering each integer line by ``half_width_m`` so the
    surviving (current-tile) shape edges land ~that far off the line
    (``_SEAM_LINE_TOL_M`` covers the offset).  Such a vertex is
    sourced by the tile cut — NOT by an apt.dat corner or pavement
    edge — so the junction-vertex source / push-outside invariants
    exempt it (the seam position is fixed by the cut and the seam
    altitude is terrain-pinned for cross-tile stitching).
    """
    import math
    from auto_patch.layout import R_EARTH
    from auto_patch.tile_cut import _SEAM_LINE_TOL_M
    if tol_m is None:
        tol_m = _SEAM_LINE_TOL_M
    lat, lon = layout.m_to_ll(x, y)
    d_lat_m = math.radians(abs(lat - round(lat))) * R_EARTH
    d_lon_m = (math.radians(abs(lon - round(lon)))
               * R_EARTH * math.cos(math.radians(lat)))
    return min(d_lat_m, d_lon_m) <= tol_m


# Baseline airports (user 2026-05-16): these run unconditionally on
# every invariant / grade / overlap test, providing CI coverage for
# the canonical geometry classes we need to support:
#
#   * SPJC — apron-heavy, multi-ref diagonal stubs, sloped runway,
#     hand-drawn target available for structural regression.
#   * SPLP — single runway with built-up threshold pad, multi-tile
#     output, sloped runway with seam anchors.  Target available.
#   * CYXY — multi-runway crossings (D crosses 14R/32L and 14L/32R),
#     chart-level E-D junction, parallel taxi E with diagonal stub
#     E and primary-parallel south extension into the apron.
#
# Adding KBNA / HECA to this list once Phase-1 baselines are stable
# would expand coverage to (4) terminal-heavy taxi network with
# multiple intersecting parallels, and (5) wide-runway desert
# airport with extensive aprons.
#
# Hand-drawn target comparison stays SPJC/SPLP-only — those are the
# regression-gate fixtures.  Invariant tests apply universally.
_BASELINE_AIRPORTS: tuple = ("SPJC", "SPLP", "CYXY")


def baseline_airports() -> tuple:
    """Return the canonical baseline airport list every invariant
    test should run against unconditionally.  See module-level
    ``_BASELINE_AIRPORTS`` for the rationale."""
    return _BASELINE_AIRPORTS


_AIRPORTS_CACHE: Optional[List[str]] = None


def airports_under_test() -> List[str]:
    """Resolved ICAO list for parametrised integration tests.

    Cached for the lifetime of the pytest session.  See module
    docstring for the env-var contract.
    """
    global _AIRPORTS_CACHE
    if _AIRPORTS_CACHE is not None:
        return _AIRPORTS_CACHE
    explicit = os.environ.get("O4_TEST_AIRPORTS", "").strip()
    if explicit:
        _AIRPORTS_CACHE = sorted({
            a.strip().upper()
            for a in explicit.split(",")
            if a.strip()})
        return _AIRPORTS_CACHE
    tile_str = os.environ.get("O4_TEST_TILE", "").strip()
    if tile_str:
        try:
            parts = [int(p.strip()) for p in tile_str.split(",")]
            assert len(parts) == 2
            lat, lon = parts
        except (ValueError, AssertionError):
            _AIRPORTS_CACHE = []
            return _AIRPORTS_CACHE
        _AIRPORTS_CACHE = _discover_airports_in_tile(lat, lon)
        return _AIRPORTS_CACHE
    _AIRPORTS_CACHE = []
    return _AIRPORTS_CACHE


def _discover_airports_in_tile(lat: int, lon: int) -> List[str]:
    """Return sorted ICAOs whose runways fall in the 1°×1° tile.

    Uses the same CIFP scanner the build pipeline uses
    (``O4_Cifp_Reader.discover_cifp_airports`` +
    ``parse_cifp_file`` + ``airport_in_tile``) to ensure tests run
    against the exact airport set the build pipeline would touch.
    """
    cifp_path = os.path.join(xplane_root(), "Custom Data", "CIFP")
    if not os.path.isdir(cifp_path):
        return []
    from auto_patch.cifp_reader import (
        discover_cifp_airports, parse_cifp_file, airport_in_tile)
    found: List[str] = []
    for icao, filepath in discover_cifp_airports(cifp_path).items():
        # Only test against true 4-letter ICAOs (mirror the build
        # pipeline's ICAO mode).
        if not (len(icao) == 4 and icao.isalpha()):
            continue
        runways = parse_cifp_file(filepath)
        if runways and airport_in_tile(runways, lat, lon):
            found.append(icao)
    return sorted(found)


# ══════════════════════════════════════════════════════════════════════
# THE SHARED DATA REPO IS NOT A TEST SCRATCH DIR (owner ruling e9daef5)
# ══════════════════════════════════════════════════════════════════════
# /Users/noah/XPTerrainBuilderData is THE corpus every lane MOUNTS.  A test
# that writes into it changes what every other lane measures, and nothing
# in a pytest report says so.
#
# THE MEASURED LEAK (2026-08-06).  ``tests/test_dsf_texture_modes.py``
# decodes the DSF it emits into ``tmp_path`` with
# ``tools/decode_dsf_terrain_table.decode_dsf``, which caches DSFTool's
# text dump under ``FNAMES.Default_dsf_cache_dir`` — the SHARED repo — in a
# directory keyed by the sha1 of the DSF's ABSOLUTE path.  Under
# ``tmp_path`` that path is different every run, so every run of those four
# tests minted a new cache directory that nothing would ever read again:
# 529 of the 530 directories in the shared ``Default_DSF_cache`` were this
# leak, one tile (``+50+010``, the synthetic fixture) over three weeks.
#
# Four fixes, because they close different holes:
#   1. THE REDIRECT (below) — the dump cache points at the worker's own
#      tmp dir for the whole session, so no test can author that cache at
#      all, whether or not it remembers to monkeypatch.  It rides an ENV
#      VARIABLE (``O4_DSF_CACHE_DIR``), read inside
#      ``O4_File_Names._apply_data_root``, so a module RELOAD recomputes
#      the redirect instead of undoing it.
#   2. THE OVERLAY (below) — ``Airport_mod_cache`` is fingerprint-keyed
#      DERIVED cache: a tree whose keys drift from what the shared corpus
#      is warm for REWRITES its sidecars.  The suite points the whole root
#      (``O4_AIRPORT_MOD_CACHE_DIR``) at a per-worker tmp overlay that
#      SYMLINKS every shared file, so reads stay warm and writes land
#      lane-local.
#   3. THE PER-TEST GUARD (below) — the harness's own
#      ``SharedRepoWriteGuard`` around EVERY test, in refuse mode: a
#      shared-repo write fails the test that made it, with a traceback
#      naming the writer.  Enforced per test, not asserted per session.
#   4. THE DETECTOR (below) — a session-scoped before/after snapshot of the
#      shared repo, so the NEXT unknown leak class is loud instead of
#      silent, including the ones no Python-level guard can see (a
#      subprocess's own writes).  It reuses
#      ``tools/harness/build_airport.py``'s own snapshot and scope register
#      (one implementation — the harness already answers "which artifact
#      class is this path" for builds).

#: The harness module, loaded AT MOST ONCE per worker process.  The audit
#: fixture below is per-TEST, and re-``exec_module``-ing a 1,800-line module
#: five thousand times would make the instrument the dominant cost of the
#: run it is supposed to observe.
_HARNESS_BUILD_MOD = None


def _harness_build_module():
    """``tools/harness/build_airport.py``, loaded by path.

    The harness owns the shared-repo snapshot, the scope register and the
    scope→description text.  A second copy here is the census-wrapper
    defect in a different costume."""
    global _HARNESS_BUILD_MOD
    if _HARNESS_BUILD_MOD is not None:
        return _HARNESS_BUILD_MOD
    import importlib.util
    path = os.path.normpath(os.path.join(
        _HERE, "..", "tools", "harness", "build_airport.py"))
    spec = importlib.util.spec_from_file_location(
        "conftest_harness_build_airport", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _HARNESS_BUILD_MOD = mod
    return mod


#: Refresh scopes the SUITE may warm.  EMPTY, and that is the point: the
#: suite writes NOTHING into the shared corpus, so every touched path is a
#: defect the detector fails on.
#:
#: WHY IT EMPTIED (suite-corpus-clean lane, 2026-08-08).  It used to carry
#: ``airport_mod_cache`` and ``dem`` as standing allowances.  What that
#: bought, measured: a guarded HECA harness build was REFUSED after suite
#: tests rewrote ``Airport_mod_cache`` paths — an SPJC cache path in the
#: blocked list of a HECA build, 646 s wasted — because "the suite may
#: warm it" and "no other lane may be measuring right now" are different
#: claims and only the first was written down.  The two scopes are now
#: structurally unreachable instead of authorised: the mod cache is a
#: lane-local copy-on-write overlay (fixture below), and an inset the suite
#: would have to CUT is refused loudly rather than warmed — a privately
#: cut inset is a private measurement frame (warm-vs-cold has moved
#: terrain 12 m), which is the two-corpora defect itself.
_SUITE_MAY_WARM: dict = {}


def unauthorised_shared_writes(changes: dict, scope_of) -> list:
    """The pure half of the detector: ``[(relpath, scope)]`` for every
    shared-repo path the suite is NOT allowed to have touched.

    Split out from the fixture so it has a known-answer twin
    (``tests/test_harness.py`` §8) — an instrument without one is not an
    instrument (RULINGS 2026-08-06, "Instrument truth is law").
    """
    touched = sorted(set(changes.get("added", ()))
                     | set(changes.get("modified", ()))
                     | set(changes.get("removed", ())))
    return [(p, scope_of(p)) for p in touched
            if scope_of(p) not in _SUITE_MAY_WARM]


#: Where the session redirected the DSFTool dump cache to.  Module-level
#: because a MODULE RELOAD undoes the redirect and the reloader has to be
#: able to put it back — see :func:`reapply_dsf_dump_cache_redirect`.
_LANE_DSF_CACHE_DIR = None


def reapply_dsf_dump_cache_redirect():
    """Re-point ``O4_File_Names.Default_dsf_cache_dir`` at this session's
    lane-local directory.  Call after ANY ``importlib.reload`` of
    ``O4_File_Names``.

    WHY THIS EXISTS (cycle-8 chore; the 12th standing suite red).  Cycle
    7.5 landed the redirect as a session fixture, and the guard in
    ``tests/test_harness.py`` still failed a full-suite run — with the
    guard's own message saying the cache "is already redirected
    session-wide above", which the assertion falsified.  The mechanism:
    ``tests/test_data_root.py`` reloads ``O4_File_Names`` after every one
    of its tests, the reload re-executes ``_apply_data_root()``, and that
    recomputes ``Default_dsf_cache_dir`` as ``<cwd>/Default_DSF_cache`` —
    which in a lane worktree is the SHARED REPO mount.  Every test that
    decoded a DSF afterwards on that xdist worker authored into the shared
    corpus again (the ``b5079c60`` directory the c8base battery
    disclosed).  Verdict (a) BUG, in the redirect: a session-scoped
    assignment cannot survive a module reload, and the fix is to make the
    reload put it back rather than to forbid reloading.
    """
    if _LANE_DSF_CACHE_DIR is None:
        return None
    import O4_File_Names as FNAMES
    FNAMES.Default_dsf_cache_dir = _LANE_DSF_CACHE_DIR
    return _LANE_DSF_CACHE_DIR


@pytest.fixture(scope="session", autouse=True)
def _dsf_dump_cache_is_lane_local(tmp_path_factory):
    """THE REDIRECT: no test may author the shared DSFTool dump cache.

    THE ENV VARIABLE IS THE REDIRECT; the direct assignment and
    :func:`reapply_dsf_dump_cache_redirect` are the belt.
    ``O4_DSF_CACHE_DIR`` is read inside ``O4_File_Names._apply_data_root``,
    which EVERY recompute path runs (a module reload, ``set_data_root``) —
    so the redirect survives them by construction rather than by whoever
    reloaded remembering to put it back.  The measured hole it closes: the
    dump written by the DSFTool SUBPROCESS, which no Python-level guard
    can intercept (``Default_DSF_cache/2e32f218/+50+010.dsf.tmp.text``,
    audit arm 2026-08-08).
    """
    global _LANE_DSF_CACHE_DIR
    try:
        import O4_File_Names as FNAMES
    except Exception:                                   # pragma: no cover
        yield
        return
    previous = FNAMES.Default_dsf_cache_dir
    previous_env = os.environ.get("O4_DSF_CACHE_DIR")
    _LANE_DSF_CACHE_DIR = str(tmp_path_factory.mktemp("default_dsf_cache"))
    os.environ["O4_DSF_CACHE_DIR"] = _LANE_DSF_CACHE_DIR
    FNAMES.Default_dsf_cache_dir = _LANE_DSF_CACHE_DIR
    try:
        yield
    finally:
        _LANE_DSF_CACHE_DIR = None
        if previous_env is None:
            os.environ.pop("O4_DSF_CACHE_DIR", None)
        else:
            os.environ["O4_DSF_CACHE_DIR"] = previous_env
        FNAMES.Default_dsf_cache_dir = previous


#: Where the session mirrored the shared ``Airport_mod_cache`` to.  Module
#: level for the same reason as the dump cache above: the twins read it.
_LANE_AIRPORT_MOD_CACHE_DIR = None


def mirror_tree_as_overlay(source_root: str, overlay_root: str) -> dict:
    """Delegates to the harness's single implementation (moved into
    tools/harness/shared_repo_guard.py 2026-08-11 so the harness build
    entry's per-run engine-cache redirect and this suite overlay share
    ONE mirror — the census-wrapper precedent, owner ruling e9daef5).

    Renamed with the mirror itself 2026-08-12: it seeds COPY-ON-WRITE
    (clonefile) rather than symlinks, because the engine's sidecar writers
    truncate the cache path in place and followed the links straight into
    the shared corpus."""
    return _harness_build_module().mirror_tree_as_overlay(
        source_root, overlay_root)


@pytest.fixture(scope="session", autouse=True)
def _airport_mod_cache_is_a_lane_local_overlay(tmp_path_factory):
    """THE OVERLAY: no test may author the shared per-pack sidecar cache.

    ``Airport_mod_cache`` holds fingerprint- and version-keyed DERIVED
    caches (``o4_object_*``, ``o4_dsf_*``, the library index).  A tree
    whose cache keys drift from what the shared corpus is warm for
    REWRITES them — which is not hypothetical: an SPJC cache path rewritten
    by the suite refused a concurrent guarded HECA build on 2026-08-08
    (646 s).  The zero an audit measures from a key-matching tree is state,
    not structure, so the redirect is unconditional.

    Per WORKER (``tmp_path_factory`` is worker-private under xdist), and
    instant in practice: 1,131 files / 22 GB apparent seeded in 0.10 s for
    ~420 KB of real disk, because a clone shares its blocks until written
    (measured 2026-08-12 on the real corpus).
    """
    global _LANE_AIRPORT_MOD_CACHE_DIR
    try:
        harness = _harness_build_module()
    except Exception as exc:                            # pragma: no cover
        print(f"[conftest] mod-cache overlay unavailable: {exc!r}")
        yield
        return
    shared = os.path.join(harness.DATA_REPO, "Airport_mod_cache")
    overlay = str(tmp_path_factory.mktemp("airport_mod_cache"))
    mirror_tree_as_overlay(shared, overlay)
    previous_env = os.environ.get("O4_AIRPORT_MOD_CACHE_DIR")
    os.environ["O4_AIRPORT_MOD_CACHE_DIR"] = overlay
    _LANE_AIRPORT_MOD_CACHE_DIR = overlay
    try:
        yield
    finally:
        _LANE_AIRPORT_MOD_CACHE_DIR = None
        if previous_env is None:
            os.environ.pop("O4_AIRPORT_MOD_CACHE_DIR", None)
        else:
            os.environ["O4_AIRPORT_MOD_CACHE_DIR"] = previous_env


#: Where the session mirrored the shared OSM regional-extract store to.
#: Module level for the same reason as the two caches above: the twins
#: read it.
_LANE_OSM_EXTRACT_STORE_DIR = None


@pytest.fixture(scope="session", autouse=True)
def _osm_regional_extract_store_is_a_lane_local_overlay(tmp_path_factory):
    """THE THIRD OVERLAY: no test may author the shared OSM clip store.

    THE MEASURED LEAK (attributed 2026-09-01, hard4 lane).  Eight
    orphaned ``clip_-012-0078_69d512e41ade-part0.osm.pbf.tmp-<pid>-<tid>
    .osm.pbf`` files sit in
    ``<repo>/OSM_data/_regional_extracts/clips`` — 11.3 MB each, one per
    run that touched SPJC's region, the newest stamped 08:40:49 inside
    the 08:37:40-08:59:05 window of the 2026-09-01 full suite whose
    session detector errored on ALL EIGHTEEN xdist workers.

    HOW IT GETS PAST EVERYTHING.  ``O4_OSM_Extracts._cut_clip`` hands the
    part paths to ``O4_OSM_Extract_Filter.cut_clip_parts_with_osmium``,
    which writes ``<part>.tmp-<pid>-<tid>.osm.pbf`` beside the part and
    then renames it into place.  The writer is the osmium-tool
    SUBPROCESS, so the per-test ``SharedRepoWriteGuard`` — a Python-level
    guard — never sees the bytes land; only the Python ``os.replace``
    is refused, and ``_clip_for_query``'s broad ``except Exception``
    swallows that refusal ("Clipped OSM cache unavailable … filtering the
    full extracts") and the build carries on.  So the clip never
    completes, the cache key never serves, and every later run re-cuts
    and re-orphans another 11.3 MB.  Exactly the blind spot the session
    detector's own message names: "written by a SUBPROCESS or a C
    extension".

    THE SHAPE OF THE FIX is the mod cache's, for the same reasons: a
    COPY-ON-WRITE read-through overlay keeps the warm clips and region
    extracts readable (a cold store would make every OSM query re-cut
    for real) while every write — the subprocess's tmp file included —
    lands lane-local.  ``STORE_DIRECTORY`` is module-level and
    documented mutable for exactly this ("Module-level and mutable so
    tests monkeypatch it at a tmp_path"), and ``_store_path`` reads it
    at CALL time, so the assignment reaches every path in the module.
    Nothing reloads ``O4_OSM_Extracts``, and its store is derived from
    ``FNAMES.OSM_dir`` at ITS OWN import, so the data-root reloads in
    ``tests/test_data_root.py`` cannot recompute it out from under us
    the way they did the DSF dump cache.
    """
    global _LANE_OSM_EXTRACT_STORE_DIR
    try:
        harness = _harness_build_module()
        import O4_OSM_Extracts as EXTRACTS
    except Exception as exc:                            # pragma: no cover
        print(f"[conftest] extract-store overlay unavailable: {exc!r}")
        yield
        return
    shared = EXTRACTS.STORE_DIRECTORY
    overlay = str(tmp_path_factory.mktemp("osm_regional_extracts"))
    if os.path.isdir(shared):
        mirror_tree_as_overlay(shared, overlay)
    previous = EXTRACTS.STORE_DIRECTORY
    EXTRACTS.STORE_DIRECTORY = overlay
    _LANE_OSM_EXTRACT_STORE_DIR = overlay
    try:
        yield
    finally:
        _LANE_OSM_EXTRACT_STORE_DIR = None
        EXTRACTS.STORE_DIRECTORY = previous


@pytest.fixture(scope="session", autouse=True)
def _the_shared_data_repo_survives_the_suite():
    """THE DETECTOR: fail the session if a test wrote into the shared repo.

    Cheap by measurement: the full walk is 3,430 files in ~11 ms, twice per
    worker.  Attribution is per-session, not per-test — under ``-n auto``
    every worker sees every worker's writes — so the failure names the
    PATHS and says how to attribute them (re-run the suspect module with
    ``-n0``).  Its one blind spot, stated rather than discovered: a write
    from a LATER session-teardown finalizer than this one lands after the
    closing snapshot.  Verified end-to-end 2026-08-06 — a write during a
    test errors the session (exit 1) naming path and scope.  ``O4_ALLOW_SHARED_REPO_WRITES=1`` downgrades it to a printed
    report for the rare deliberate case (a corpus refresh under the
    harness's own ``--refresh-data``, which records its own ledger entry).
    """
    try:
        harness = _harness_build_module()
    except Exception as exc:                            # pragma: no cover
        print(f"[conftest] shared-repo detector unavailable: {exc!r}")
        yield
        return
    repo = harness.DATA_REPO
    if not os.path.isdir(repo):
        yield
        return
    before = harness.shared_repo_snapshot(repo)
    try:
        yield
    finally:
        changes = harness.snapshot_diff(
            before, harness.shared_repo_snapshot(repo))
        unlawful = unauthorised_shared_writes(changes, harness.scope_of)
        if unlawful:
            lines = [
                f"THE TEST SUITE WROTE INTO THE SHARED DATA REPO {repo}.",
                "Owner ruling e9daef5: it is THE corpus every lane mounts; "
                "a test that writes there changes what every other lane "
                "measures, and no pytest report says so.",
                f"{len(unlawful)} unauthorised path(s):",
            ]
            for path, scope in unlawful[:20]:
                lines.append(f"  [{scope or 'unscoped'}] {path}")
            if len(unlawful) > 20:
                lines.append(f"  … and {len(unlawful) - 20} more")
            lines += [
                "THE SUITE HAS NO STANDING WRITE ALLOWANCE: every scope is "
                "unauthorised, so this is a leak, never a registered one.",
                "FIX: point the writer at tmp_path (the DSFTool dump cache "
                "and the per-pack Airport_mod_cache root are already "
                "redirected session-wide above).",
                "WHAT GOT PAST WHAT: the per-test guard refuses every "
                "PYTHON-level shared-repo write at its call site, so a path "
                "reaching here was written by a SUBPROCESS or a C "
                "extension, or outside a test (a session fixture window).",
                "ATTRIBUTION: this snapshot is per-SESSION, and under "
                "-n auto every worker sees every worker's writes — re-run "
                "the suspect module with -n0 to attribute it.",
                "Deliberate refresh? Do it through "
                "tools/harness/build_airport.py --refresh-data <scope>, "
                "which locks, snapshots and ledgers it "
                "(O4_ALLOW_SHARED_REPO_WRITES=1 silences this detector).",
            ]
            message = "\n".join(lines)
            if os.environ.get("O4_ALLOW_SHARED_REPO_WRITES", "0") == "1":
                print("\n[conftest] " + message)
            else:
                pytest.fail(message, pytrace=False)


# ══════════════════════════════════════════════════════════════════════
# THE PER-TEST GUARD, AND THE PER-TEST WRITE AUDIT
# ══════════════════════════════════════════════════════════════════════
# The detector above is per-SESSION: it says the suite wrote, never WHICH
# test wrote.  Under ``-n auto`` every worker sees every worker's writes,
# so attribution costs a ``-n0`` re-run of a suspect module.  Both fixtures
# below wrap each test in the harness's own :class:`SharedRepoWriteGuard`,
# which attributes the write to the test that made it — they differ only in
# what happens next, so EXACTLY ONE of them installs (see
# :func:`_per_test_guard_mode`; two stacked guards would double-record and
# make the inner one's restore order matter):
#
#   * REFUSE (the default, permanent): the write raises at its call site,
#     failing that test with a traceback naming the writer.
#   * AUDIT (``O4_SUITE_WRITE_AUDIT=1``): RECORD-ONLY — it observes and
#     lets the write proceed, because a blocking guard would change test
#     outcomes and enumerate the offenders of a different suite.  Output
#     goes to ``${O4_SUITE_WRITE_AUDIT_OUT}.${PYTEST_XDIST_WORKER-master}``
#     — one file per worker, so concurrent appends never interleave a line.

def shared_repo_write_audit_rows(nodeid: str, guard) -> list:
    """The pure half of the audit: one row per write ``guard`` observed.

    Split out from the fixture for the same reason
    :func:`unauthorised_shared_writes` was — an instrument without a
    known-answer twin is not an instrument (RULINGS 2026-08-06); the twin
    is ``tests/test_harness.py`` §8.  ``kind`` separates a real
    unauthorised-class write from the two ruled churn classes the guard
    lets through (``.lock`` coordination state, the derived library-index
    sidecar), which are not corpus mutations and must not be counted as
    offenders.
    """
    rows = []
    for kind, entries in (("blocked", getattr(guard, "blocked", ())),
                          ("lock_churn", getattr(guard, "lock_churn", ())),
                          ("lib_index_churn",
                           getattr(guard, "library_index_churn", ()))):
        for entry in entries or ():
            row = {"nodeid": nodeid, "kind": kind,
                   "path": entry.get("path"), "scope": entry.get("scope")}
            if "via" in entry:
                row["via"] = entry["via"]
            if "op" in entry:
                row["op"] = entry["op"]
            rows.append(row)
    return rows


def _suite_write_audit_out() -> str:
    """This worker's audit file.  ``master`` when xdist is not in play."""
    worker = os.environ.get("PYTEST_XDIST_WORKER", "master")
    return f"{os.environ['O4_SUITE_WRITE_AUDIT_OUT']}.{worker}"


def pytest_configure(config):
    """Refuse the audit arm at SESSION START if it has nowhere to write.

    Discovering the missing path at the first offending test would throw
    away everything measured before it — and under xdist, on a worker
    whose error is easy to miss."""
    if os.environ.get("O4_SUITE_WRITE_AUDIT", "0") != "1":
        return
    out = os.environ.get("O4_SUITE_WRITE_AUDIT_OUT", "").strip()
    if not out or not os.path.isabs(out):
        raise pytest.UsageError(
            "O4_SUITE_WRITE_AUDIT=1 needs O4_SUITE_WRITE_AUDIT_OUT set to "
            f"an ABSOLUTE path for the per-test JSONL rows (got {out!r}); "
            "each worker appends to <path>.<worker>.")


def _per_test_guard_mode():
    """Which per-test guard installs around every test: ONE decision.

    ``"audit"`` (record-only), ``"refuse"`` (the permanent guard), or
    ``None`` (neither).  The audit arm WINS over
    ``O4_ALLOW_SHARED_REPO_WRITES``: it is the instrument that measures
    what the suite writes, and it prevents nothing anyway.
    """
    if os.environ.get("O4_SUITE_WRITE_AUDIT", "0") == "1":
        return "audit"
    if os.environ.get("O4_ALLOW_SHARED_REPO_WRITES", "0") == "1":
        return None
    return "refuse"


@pytest.fixture(autouse=True)
def _no_test_writes_the_shared_repo():
    """THE PER-TEST GUARD: a shared-repo write fails ITS OWN test.

    The property is ENFORCED per test rather than asserted per session
    (owner ruling e9daef5).  What that changes, concretely: the session
    detector reports a path and hands you a ``-n0`` re-run to find the
    author, while this raises ``SharedRepoWriteBlocked`` inside the
    writing call, so the traceback IS the attribution — and the corpus
    still has what it had before the test ran.

    ``allow_library_index=False`` (spec §8.2 R-e): with the mod-cache
    overlay in place nothing should reach the sidecar's real path, so the
    harness build's allowance for it would only ever hide a bypass here.
    The ``.lock`` allowance stands — cross-process coordination state is
    not corpus data, and refusing it makes concurrent-safe cache READS
    impossible.
    """
    if _per_test_guard_mode() != "refuse":
        yield
        return
    try:
        harness = _harness_build_module()
    except Exception as exc:                            # pragma: no cover
        print(f"[conftest] shared-repo guard unavailable: {exc!r}")
        yield
        return
    repo = harness.DATA_REPO
    if not os.path.isdir(repo):
        yield
        return
    # ``root`` is the ENGINE dir: its mounted data-dir symlinks are half
    # the guard's prefix set (a lane writes ``OSM_data/...`` relative,
    # through a symlink, never mentioning the repo path at all).
    with harness.SharedRepoWriteGuard(
            set(), root=os.path.dirname(_HERE), repo=repo,
            allow_library_index=False):
        yield


@pytest.fixture(autouse=True)
def _shared_repo_write_audit(request):
    """Record every shared-repo write THIS test makes (audit arm only)."""
    if _per_test_guard_mode() != "audit":
        yield
        return
    try:
        harness = _harness_build_module()
    except Exception as exc:                            # pragma: no cover
        print(f"[conftest] write audit unavailable: {exc!r}")
        yield
        return
    repo = harness.DATA_REPO
    if not os.path.isdir(repo):
        yield
        return
    # ``root`` is the ENGINE dir: its mounted data-dir symlinks are half
    # the guard's prefix set (a lane writes ``OSM_data/...`` relative,
    # through a symlink, never mentioning the repo path at all).
    guard = harness.SharedRepoWriteGuard(
        set(), root=os.path.dirname(_HERE), repo=repo, record_only=True)
    with guard:
        yield
    rows = shared_repo_write_audit_rows(request.node.nodeid, guard)
    if not rows:
        return
    out = _suite_write_audit_out()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


# ══════════════════════════════════════════════════════════════════════
# THE X-PLANE INSTALL IS NOT A TEST SCRATCH DIR EITHER (2026-08-09)
# ══════════════════════════════════════════════════════════════════════
# Everything above protects the SHARED DATA REPO; nothing protected the
# real X-Plane install at ``xplane_root()`` — which tests legitimately
# READ (CIFP, apt.dat, Custom Scenery pack originals) and must never
# WRITE: it is production state, owned by X-Plane and the owner's app,
# and the suite has no lawful write into it at all.
#
# THE MEASURED INCIDENT (2026-08-09).  A test in
# ``tests/test_post_mesh.py`` called ``monkeypatch.undo()`` MID-TEST,
# which tore down its own ``phase_two_harness`` fixture's patches — the
# ``FNAMES.patch_dir`` redirect into ``tmp_path`` AND the DSFTool stub.
# ``post_mesh.rebake_dsf_objects`` then read the REAL ``+35-081``
# worklist from the production Patches directory, ran the real KCLT pack
# against a 2-triangle synthetic mesh, found every anchor outside it,
# and its reversion pass restored 49 pack ``.obj`` files from their
# ``.anchor_bak`` backups and rewrote the pack's
# ``.o4_reanchor_provenance.json`` — with ``shutil.copy2`` preserving
# mtimes, so the damage left no recent-mtime trace.
#
# The guard below is the shared-repo per-test guard's shape on the
# install: reads untouched, any write under the install refuses at the
# call site with a traceback naming the writer.  There is deliberately
# no audit arm, no allowance register and no env override — unlike the
# shared repo there is no ``--refresh-data`` analogue here, because no
# test write into the install is ever lawful.

class XPlaneInstallWriteBlocked(RuntimeError):
    """A test tried to write inside the X-Plane install, and the guard
    stopped it."""


#: The install guard CLASS, built AT MOST ONCE per worker — lazily,
#: because subclassing needs :func:`_harness_build_module` and conftest
#: must still import on a tree where the harness is broken.
_XPLANE_GUARD_CLS = None


def _xplane_guard_class():
    """The install write guard, INHERITING the harness's interceptor.

    ``SharedRepoWriteGuard.__enter__`` owns the patching machinery —
    ``builtins.open`` / ``os.open`` in writing modes, the rename /
    replace / remove / unlink / rmdir / mkdir / makedirs / truncate
    family, the mkdir-on-an-existing-dir no-op allowance, the two-path
    checks.  A second copy of that machinery is the census-wrapper
    defect, so this class overrides ONLY the predicate (any path under
    the install root) and the refusal (its own exception, naming the
    install), and inherits the rest.
    """
    global _XPLANE_GUARD_CLS
    if _XPLANE_GUARD_CLS is not None:
        return _XPLANE_GUARD_CLS
    harness = _harness_build_module()

    class _XPlaneInstallWriteGuard(harness.SharedRepoWriteGuard):
        def __init__(self, install_root: str):
            # Deliberately NOT calling super().__init__: the parent wires
            # refresh scopes, repo prefixes and churn registers that have
            # no install analogue.  The inherited __enter__/__exit__ read
            # exactly these attributes.
            self.install_root = install_root
            self._roots = tuple(sorted({os.path.abspath(install_root),
                                        os.path.realpath(install_root)}))
            self.enabled = True
            self.blocked: list = []
            self._saved: dict = {}

        def _violation(self, path, op=None):
            try:
                s = os.fspath(path)
            except TypeError:
                return None                    # an fd, not a path
            if not isinstance(s, (str, bytes)):
                return None
            if isinstance(s, bytes):
                s = s.decode("utf-8", "replace")
            ap = s if os.path.isabs(s) else os.path.abspath(s)
            for root in self._roots:
                if ap == root or ap.startswith(root + os.sep):
                    return os.path.relpath(ap, root), None
            return None

        def _refuse(self, rel, scope, how):
            self.blocked.append({"path": rel, "via": how})
            raise XPlaneInstallWriteBlocked(
                f"BLOCKED: this test tried to {how} '{rel}' inside the "
                f"X-PLANE INSTALL ({self.install_root}).  The install is "
                f"production state: tests READ it (CIFP, apt.dat, pack "
                f"originals) and never write it.  The measured incident "
                f"(2026-08-09): a monkeypatch.undo() mid-test dropped the "
                f"phase-two harness's own redirects and the reversion "
                f"pass restored 49 real KCLT pack .obj files from their "
                f".anchor_bak backups, mtime-preserved, traceless.\n"
                f"FIX: point the writer at tmp_path — redirect patch_dir "
                f"/ the pack root the way phase_two_harness does, or "
                f"build a synthetic install under tmp_path and point "
                f"XPLANE_ROOT at it.")

    _XPLANE_GUARD_CLS = _XPlaneInstallWriteGuard
    return _XPLANE_GUARD_CLS


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Stash each phase's report on the item, so the install guard's
    teardown can tell "the refusal already failed the test" from "the
    refusal was swallowed" — only the latter needs its own failure."""
    outcome = yield
    report = outcome.get_result()
    setattr(item, "_o4_report_" + report.when, report)


@pytest.fixture(autouse=True)
def _no_test_writes_the_xplane_install(request):
    """THE INSTALL GUARD: a write into the X-Plane install fails ITS OWN
    test, with a traceback naming the writer.

    Pinned to ``xplane_root()`` AT SETUP — before any test-local
    monkeypatching — so a test that builds a synthetic install under
    ``tmp_path`` and points ``XPLANE_ROOT`` at it stays free to write
    there while the REAL install stays guarded.  Armed even when the
    install is absent: a write would otherwise CREATE the default path.
    Reads stay allowed — e.g. ``tests/test_object_anchor.py::
    test_kclt_eight_bake_pool_end_to_end`` reads the KCLT pack's
    ``.anchor_bak`` originals.

    After the test, a refusal the test SWALLOWED (the engine's broad
    ``except Exception`` shape — the same hole
    ``require_no_swallowed_write_block`` closes for harness builds)
    fails the test too: the write was still prevented, but a green test
    that tried is the incident with better luck.
    """
    try:
        guard_cls = _xplane_guard_class()
    except Exception as exc:                            # pragma: no cover
        print(f"[conftest] X-Plane install guard unavailable: {exc!r}")
        yield None
        return
    guard = guard_cls(xplane_root())
    with guard:
        yield guard
    if not guard.blocked:
        return
    for phase in ("setup", "call"):
        report = getattr(request.node, "_o4_report_" + phase, None)
        if report is not None and report.failed:
            return      # the refusal already failed the test at its call
    lines = "\n".join(f"  - BLOCKED {b['via']} '{b['path']}'"
                      for b in guard.blocked)
    pytest.fail(
        f"the X-Plane install write guard blocked {len(guard.blocked)} "
        f"write(s) during this test and the test did not fail — "
        f"something caught the refusal and carried on (the engine's "
        f"broad ``except Exception`` shape):\n{lines}\n"
        f"The install is intact; the test is not.  Point the writer at "
        f"tmp_path.", pytrace=False)


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    """Per-airport xdist grouping + optional ship-mode skip.

    MUST run before xdist's own ``pytest_collection_modifyitems`` (remote.py),
    which converts the ``xdist_group`` marker into the ``@group`` nodeid suffix
    the loadgroup scheduler keys on.  Without ``tryfirst`` our hook runs AFTER
    xdist's, so the marker isn't present when xdist reads it → no grouping → each
    airport rebuilds on every worker (CYXY/SPJC/SPLP were each built ~14×/run).

    Under ``--dist loadgroup`` (set in ``pytest.ini``), tests sharing an
    ``xdist_group`` run on the SAME worker.  Assigning every airport-
    parametrised test the group ``<icao>`` makes all of an airport's
    tests land on one worker, so the shared :func:`cached_airport_layout`
    builds each airport exactly once per run (instead of once per worker
    that happened to pick up one of its tests).
    """
    for item in items:
        icao = item.callspec.params.get("icao") if hasattr(
            item, "callspec") else None
        if isinstance(icao, str) and icao:
            item.add_marker(pytest.mark.xdist_group(icao))

    if os.environ.get("O4_SHIP_MODE", "0") == "1":
        skip_marker = pytest.mark.skip(
            reason="O4_SHIP_MODE=1 (tests disabled for shipping)")
        for item in items:
            item.add_marker(skip_marker)


@pytest.fixture()
def stricter_lot_cap(monkeypatch):
    """Hold ``groundside_pavement``'s cap at the 5 % walking-surface value.

    THE LATERAL-CONTIGUITY ABSORPTION PRECONDITION.  A road stretch is
    absorbed into a neighbour only where that neighbour's class is
    STRICTER than the road's own (``binding = [r for r in runs if
    r[2] < own_cap]``).  Since the owner's 2026-08-12 ruling put a lot
    ON the road limit, a road beside a LOT no longer binds — so a scene
    written to exercise the ABSORPTION MACHINERY has to supply a
    genuinely stricter host.  Tests of the ruling itself (a road beside
    a lot binds nothing) must NOT use this fixture.

    IT IS THE LAW THAT BINDS, NOT THE SHAPING.  ``groundside`` shapes
    lots at 5 % (the margin that keeps the emitted field inside the
    law), and it is tempting to read that as "the lot is strict again,
    drop this fixture".  It is not: the station caps come from
    ``ROLE_GRADE_LIMITS``, which is the road limit, so the binding test
    reads 8 % vs 8 % however the limiters are tuned.

    Returns a callable, not a patch: the fixtures that reload
    ``auto_patch.config`` rebind ``ROLE_GRADE_LIMITS`` to a fresh dict,
    so the patch has to be applied AFTER the reload, from inside the
    class fixture's body.  BOTH tables are patched — ``grade_law``
    imported the role table at MODULE level, so after a reload the
    station caps and the absorb-target lookup read two different
    objects, and patching one gives a split-brain run (binding fires at
    5 %, the target lookup compares against 8 %, nothing absorbs).
    """
    def _apply():
        from auto_patch import config as cfg
        from auto_patch import grade_law as gl
        for table in (cfg.ROLE_GRADE_LIMITS, gl.ROLE_GRADE_LIMITS):
            monkeypatch.setitem(table, "groundside_pavement",
                                cfg.GROUNDSIDE_MAX_GRADE)
    return _apply
