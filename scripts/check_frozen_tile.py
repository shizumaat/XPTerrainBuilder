#!/usr/bin/env python3
"""THE FROZEN BUILD SMOKE TEST — helper interpreter (stdlib ONLY).

Driven by ``scripts/check_frozen_tile.sh``; see that file for why this
check exists and where it sits in every release job.

TWO PASSES, ONE TOOL (``--pass tile|airport|both``, default ``both``):

1. ``tile`` — a synthetic tile with ``auto_patch=None``: the vector,
   mesh and imagery steps, a real ``.dsf`` on disk.  Wide but shallow.
2. ``airport`` — ONE REAL AIRPORT SOLVED (``auto_patch=ICAO``) inside
   the bundle: the vector step alone over the checked-in CYXY fixture
   (``Ortho4XP/tests/auto_patch_v2/fixtures/CYXY``), arranged into an
   X-Plane-shaped root.  Narrow but deep — it is the ONLY thing here
   that walks ``auto_patch_v2``'s solver, and therefore the only thing
   that would have caught the class that actually shipped broken (a
   function-level ``highspy`` import PyInstaller never saw,
   2026-09-10).  The patch and its ``.axes.json`` sidecar on disk are
   the witness: ``auto_patch.engine_v2`` FAILS the airport by name
   unless the solve came back ``optimal``/``feasible``, so a written
   patch *is* "HiGHS ran inside the bundle and the programme solved".

What this does, and why every piece of it is the way it is:

* **It builds a real tile with the frozen binary, through the shipped
  interface.**  The frozen bundle's PROJ and LERC self-checks prove it
  *imports*.  The class that has actually shipped broken is a
  function-level third-party import invisible to PyInstaller and to the
  test suite (``highspy``, 2026-09-10), a data file missing from the
  ``.spec``, or a wrong data-root/cwd resolution inside the bundle —
  none of which appear until a real build walks the code path.  So the
  binary is driven over the engine's JSON-lines protocol
  (``<binary> --engine-jsonl``), never imported: the protocol is what
  the shipping front ends use.

* **Stdlib only.**  The mac release job's own ``python3`` has no numpy
  (a redundant LERC step died on exactly that and was removed
  2026-09-17), so the helper interpreter must need nothing.  The fixture
  is therefore hand-written: a big-endian int16 ``.hgt``, bzip2'd empty
  OSM caches, a flat ``key=value`` config.

* **The fixture is generated at run time and thrown away.**  A synthetic
  data root (``ORTHO4XP_DATA_ROOT``), one synthetic elevation source, no
  X-Plane install, no shared corpus, no provider key.

* **No network.**  Imagery is off (``skip_downloads``), and every OSM
  layer the vector step would fetch is pre-seeded as an empty, valid,
  schema-stamped Overpass cache file, so ``O4_OSM_Utils`` recycles the
  cache instead of reaching Overpass.  The schema markers are read out
  of the engine source at run time (see :func:`_cache_schemas`) so a
  schema bump cannot silently turn this into a network build — and if a
  download is attempted anyway the JSONL/stderr log says so and the
  check warns loudly.

* **auto_patch is OFF in the tile pass, ON in the airport pass.**
  Since lane ``betafirstrun`` the engine REFUSES auto-patch with no
  CIFP data, and the explicit opt-out (``auto_patch=None``) is the
  documented way to build without one — that is the tile pass.  The
  airport pass satisfies the engine's own predicate instead of
  weakening it: ``O4_Settings_Model.resolve_cifp_dir`` takes a
  non-empty ``cifp_data_path`` as authoritative, and
  ``auto_patch.cifp_reader.xplane_root_from_cifp_path`` walks TWO
  levels up from it and requires a ``Custom Scenery/`` (or
  ``Resources/``) there.  So the fixture is laid out as
  ``<root>/Custom Data/CIFP/CYXY.dat`` beside
  ``<root>/Custom Scenery/CYXY Fixture/Earth nav data/apt.dat`` — a
  real X-Plane shape, no engine edit, no relaxed refusal.

* **Bounded.**  The whole check runs under a deadline enforced here,
  because coreutils ``timeout`` exists on neither the mac runner nor the
  maintainer's mac.  On any miss the child's stderr tail is printed and
  the JSONL stream plus stderr are left in the log directory for the
  job to upload.

Usage::

    check_frozen_tile.py <frozen-binary> [--pass tile|airport|both]
                         [--deadline S] [--airport-deadline S]
                         [--logs DIR] [--lat N] [--lon N] [--keep]
"""

from __future__ import annotations

import argparse
import array
import bz2
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

# ---------------------------------------------------------------------------
# Fixture geometry.  (0, 0) is open water in the Gulf of Guinea: no OSM
# features anywhere near it, so the seeded empty caches are also HONEST
# — the check is not pretending a busy tile is empty.
# ---------------------------------------------------------------------------
DEFAULT_LAT = 0
DEFAULT_LON = 0

# The SRTM3 ".hgt" geometry O4_DEM_Utils infers from the file size
# (sqrt(bytes / 2)); 1201 is upsampled to 3601 by the reader itself.
HGT_SIDE = 1201

# Every OSM layer the vector step (and the mask/bathymetry limbs it
# prefetches) can ask Overpass for, by cache suffix.  A suffix missing
# here is not fatal — it becomes a download attempt, which this check
# reports.
OSM_CACHE_SUFFIXES = (
    "airports",
    "big_roads",
    "small_roads",
    "water",
    "coastline",
    "water_basins",
)


def _signed(value: int, width: int) -> str:
    """FNAMES's own spelling: a signed decimal zero-padded AFTER the sign
    (``str.zfill``), e.g. 0 -> "+00" at width 3, -5 -> "-05"."""
    return "{:+.0f}".format(value).zfill(width)


def _round_latlon(lat: int, lon: int) -> str:
    """FNAMES.round_latlon: the 10-degree block directory name
    (``Elevation_data/<block>/``)."""
    return _signed((lat // 10) * 10, 3) + _signed((lon // 10) * 10, 4)


def _short_latlon(lat: int, lon: int) -> str:
    """FNAMES.short_latlon / long_latlon (identical spellings)."""
    return _signed(lat, 3) + _signed(lon, 4)


def _hem_latlon(lat: int, lon: int) -> str:
    """FNAMES.hem_latlon: the ``.hgt`` basename, e.g. ``N00E000``."""
    return (("N" if lat >= 0 else "S")
            + "{:.0f}".format(abs(lat)).zfill(2)
            + ("E" if lon >= 0 else "W")
            + "{:.0f}".format(abs(lon)).zfill(3))


def _cache_schemas(repo_root: str) -> list:
    """The OSM cache tag-schema markers the engine currently stamps.

    Read out of the engine source instead of hardcoded: a schema bump
    would otherwise make every seeded cache stale and quietly turn this
    offline check into an Overpass-dependent one.
    """
    wanted = (
        ("src/O4_Vector_Map.py", "ROAD_CACHE_TAG_SCHEMA"),
        ("src/O4_Vector_Map.py", "WATER_CACHE_TAG_SCHEMA"),
        ("src/O4_Mask_Utils.py", "SHALLOW_WATER_CACHE_SCHEMA"),
    )
    schemas = []
    for relative, name in wanted:
        path = os.path.join(repo_root, "Ortho4XP", relative)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
        except OSError:
            continue
        match = re.search(
            r"^%s\s*=\s*[\"']([^\"']*)[\"']" % re.escape(name),
            text,
            re.MULTILINE,
        )
        if match:
            schemas.append(match.group(1))
    return schemas


def _write_hgt(path: str) -> None:
    """A gentle north-south ramp, big-endian int16, SRTM3 geometry.

    Gentle on purpose: the mesh step inserts points by curvature, so a
    smooth surface keeps Triangle4XP's work (and this check) small,
    while still being real elevation rather than the zero plane that
    hides sign and datum mistakes.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        for row in range(HGT_SIDE):
            altitude = 100 + (row * 60) // HGT_SIDE
            values = array.array("h", [altitude]) * HGT_SIDE
            if sys.byteorder == "little":
                values.byteswap()
            handle.write(values.tobytes())


def _write_osm_seeds(osm_dir: str, lat: int, lon: int, schemas) -> None:
    """One empty, valid, schema-stamped Overpass cache per layer.

    ``O4_OSM_Utils._cached_osm_schema_matches`` looks for
    ``o4_tag_schema="<schema>"`` anywhere in the FIRST TWO LINES, and
    its ``update_dicosm`` is line-based, not an XML parser.  But
    ``auto_patch_v2.airport.osm`` reads the SAME road caches with a real
    XML parser, and three ``o4_tag_schema`` attributes on one root tag
    is a well-formedness error there ("duplicate attribute: line 2,
    column 76", measured here 2026-09-17).  So every marker rides in a
    COMMENT on line 1 — inside the two-line window both readers'
    schema check scans, invisible to the XML parser — and the root tag
    carries exactly one.
    """
    # FNAMES.osm_cached -> OSM_dir/<10-degree block>/<tile>/<tile>_<suffix>
    directory = os.path.join(osm_dir, _round_latlon(lat, lon),
                             _short_latlon(lat, lon))
    os.makedirs(directory, exist_ok=True)
    markers = " ".join('o4_tag_schema="%s"' % s for s in schemas)
    body = (
        '<?xml version="1.0" encoding="UTF-8"?><!-- %s -->\n'
        '<osm version="0.6" generator="check_frozen_tile"%s>\n'
        "</osm>\n" % (markers,
                      (' o4_tag_schema="%s"' % schemas[0]) if schemas else "")
    )
    for suffix in OSM_CACHE_SUFFIXES:
        name = "%s_%s.osm.bz2" % (_short_latlon(lat, lon), suffix)
        with bz2.open(os.path.join(directory, name), "wt",
                      encoding="utf-8") as handle:
            handle.write(body)


CONFIG = """# Generated by scripts/check_frozen_tile.py — throwaway fixture.
# THE elevation source, pinned to this fixture's own file.  A named base
# source ("View" and the other global ones) goes through
# build_combined_raster, which consults the shipped land/ocean mask and
# hands back the 3601x3601 ZERO raster for an ocean tile whatever is on
# disk — measured here 2026-09-17: min=max=mean=0.0.  An explicit
# custom_dem path is read straight from the file, so the check knows
# exactly which elevation the bundle saw, and needs no download.
custom_dem=%(dem)s
# Imagery OFF: build_dsf still renders and writes the .dsf, it just
# queues no texture downloads (O4_Tile_Utils: skip_downloads).
skip_downloads=True
skip_converts=True
# auto_patch OFF: the engine refuses auto-patch with no CIFP data, and
# this fixture ships no X-Plane install.  The explicit opt-out builds.
auto_patch=None
cifp_data_path=
custom_scenery_dir=
# The regional-extract backend is an accelerator, never a dependency:
# with it on, the session's background maintenance thread refreshes the
# Geofabrik region index over the network on every start.  Off, so this
# check reaches no server at all.
osm_regional_extracts=False
# Nothing to download and nothing to parallelise.
road_level=0
max_build_slots=1
verbosity=1
"""


def _write_fixture(root: str, repo_root: str, lat: int, lon: int) -> str:
    data_root = os.path.join(root, "data")
    os.makedirs(data_root, exist_ok=True)
    dem = os.path.join(data_root, "Elevation_data", _round_latlon(lat, lon),
                       _hem_latlon(lat, lon) + ".hgt")
    _write_hgt(dem)
    _write_osm_seeds(os.path.join(data_root, "OSM_data"), lat, lon,
                     _cache_schemas(repo_root))
    with open(os.path.join(data_root, "Ortho4XP.cfg"), "w",
              encoding="utf-8") as handle:
        handle.write(CONFIG % {"dem": dem})
    return data_root


# ---------------------------------------------------------------------------
# The AIRPORT pass fixture: the checked-in CYXY mini-world, arranged as
# an X-Plane install.
# ---------------------------------------------------------------------------
AIRPORT_ICAO = "CYXY"
#: CYXY (Whitehorse) sits at 60.7103, -135.0678 — tile +60-136.
AIRPORT_LAT = 60
AIRPORT_LON = -136
#: Relative to ``Ortho4XP/``: the fixture the auto_patch_v2 loader twins
#: already read (a complete mini-world: apt.dat block, CIFP RWY records,
#: cropped OSM feeds, a cropped DSFTool dump, a synthetic DEM + inset).
AIRPORT_FIXTURE = os.path.join("tests", "auto_patch_v2", "fixtures",
                               AIRPORT_ICAO)

AIRPORT_CONFIG = """# Generated by scripts/check_frozen_tile.py — throwaway fixture.
# THE elevation source, pinned to the fixture's own .hgt (see the tile
# pass's config for why a named base source will not do).
custom_dem=%(dem)s
skip_downloads=True
skip_converts=True
# AUTO-PATCH ON.  This is the whole point of this pass: the vector step
# runs O4_Vector_Map.run_auto_patch_generation, which resolves the CIFP
# directory below, discovers CYXY, and drives auto_patch_v2's linear
# programme — the code path that carries the lazy highspy import.
auto_patch=ICAO
cifp_data_path=%(cifp)s
custom_scenery_dir=%(scenery)s
# Elevation insets OFF: they are the one auto-patch input that fetches
# meter-class rasters from national elevation servers.  The fixture
# carries an EMPTY insets directory so the production-frame law is
# satisfied without one (see _write_airport_fixture).
airport_elevation_insets=False
elevation_level=auto
# The regional-extract backend refreshes the Geofabrik region index over
# the network on every session start; off, so this pass reaches no
# server at all.
osm_regional_extracts=False
road_level=0
max_build_slots=1
verbosity=1
"""


def _airport_fixture_dir(repo_root):
    return os.path.join(repo_root, "Ortho4XP", AIRPORT_FIXTURE)


#: The airport pass's base elevation: CYXY's field elevation, on a very
#: gentle plane.  61 x 61 is the CHECKED-IN fixture's own geometry
#: (``O4_DEM_Utils.read_elevation_from_file`` infers the side from the
#: file size), and 700 m is the plane's value at CYXY's reference point.
AIRPORT_HGT_SIDE = 61
AIRPORT_HGT_Z0 = 700.0
#: metres per degree.  The fixture's own generator uses 2000/1000, i.e.
#: ~1.8 % — which the v2 solve handles but whose emitted surface leaves a
#: 3-row ``runway_transverse`` residual at CYXY (worst excess 0.0968 m
#: against a 0.1 m floor; measured here 2026-09-17, report
#: ``verify.defects``).  THIS PASS IS ABOUT THE BUNDLE, NOT THE GEOMETRY
#: LAW: a release must not go red because a synthetic hillside leaves a
#: 10 cm residual, so the terrain under the REAL airport is a near-plane
#: (~0.06 % , ~1 m over a 1.6 km runway).  The solve, the LP and the
#: emit still run in full — which is all the lazy-import class needs.
AIRPORT_HGT_DZ_DLAT = 60.0
AIRPORT_HGT_DZ_DLON = 30.0

#: ``auto_patch_v2.pipeline.build``'s own wording for a verify verdict.
#: The ONE narrow thing the airport pass tolerates: see the stage
#: comment in :func:`run_airport`.
VERIFY_DEFECT_MARKER = "verify found a structural DEFECT"


def _write_airport_hgt(path):
    """The airport pass's base ``.hgt``: big-endian int16, 61 x 61."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    side = AIRPORT_HGT_SIDE
    with open(path, "wb") as handle:
        for row in range(side):
            # row 0 is the NORTH edge (lat + 1), as SRTM stores it.
            latitude = AIRPORT_LAT + 1.0 - row / (side - 1.0)
            values = array.array("h")
            for column in range(side):
                longitude = AIRPORT_LON + column / (side - 1.0)
                values.append(int(round(
                    AIRPORT_HGT_Z0
                    + AIRPORT_HGT_DZ_DLAT * (latitude - (AIRPORT_LAT + 0.5))
                    + AIRPORT_HGT_DZ_DLON * (longitude - (AIRPORT_LON + 0.5)))))
            if sys.byteorder == "little":
                values.byteswap()
            handle.write(values.tobytes())


def _normalise_osm_cache(source, destination):
    """Copy an OSM cache with ONE element per line.

    ``O4_OSM_Utils.OSM_layer.update_dicosm`` is a LINE reader, not an
    XML parser: it takes the first line carrying ``<osm `` as the header
    and starts parsing at the NEXT line.  The checked-in fixture was
    written for ``auto_patch_v2.airport.osm``'s own parser and has its
    first ``<node>`` glued onto the ``<osm …>`` root tag, so the v1
    reader swallows that node with the header and then dies
    ``KeyError: '-390'`` on the first ``<nd ref=…>`` pointing at it
    (measured here, 2026-09-17).  Splitting on ``><`` is the whole fix —
    the content is untouched, and both parsers accept the result.
    """
    with bz2.open(source, "rt", encoding="utf-8") as handle:
        text = handle.read()
    with bz2.open(destination, "wt", encoding="utf-8") as handle:
        handle.write(text.replace("><", ">\n<"))


def _write_airport_fixture(root, repo_root):
    """Arrange the CYXY fixture into ``(data_root, xplane_root)``.

    Two trees, because the engine reads two:

    * the DATA root (``ORTHO4XP_DATA_ROOT``) — ``Elevation_data``,
      ``OSM_data``, ``Airport_mod_cache``, and the ``Patches`` directory
      the emitted patch lands in;
    * the X-PLANE root — ``Custom Data/CIFP`` + ``Custom Scenery``,
      laid out so ``xplane_root_from_cifp_path`` resolves (see the
      module docstring).

    The fixture's own OSM ROAD feeds are deliberately NOT copied.  They
    were written under the 2026-07-16 tag whitelist and
    ``auto_patch_v2.airport.load`` REFUSES a stale road feed by name in
    the production DEM frame (RULINGS 2026-09-15ar) — the refusal is
    correct and must not be weakened, and this check is about the
    bundle, not about the corpus.  Fresh empty seeds stamped with the
    CURRENT schema are honest (CYXY's fixture crop is a small airport
    with no motorways) and keep the pass offline.
    """
    fixture = _airport_fixture_dir(repo_root)
    if not os.path.isdir(fixture):
        raise RuntimeError(
            "the CYXY fixture is missing from this checkout: %s" % fixture)

    data_root = os.path.join(root, "data")
    xplane_root = os.path.join(root, "xplane")
    os.makedirs(data_root, exist_ok=True)

    # ---- the data root -------------------------------------------------
    # The base raster, and an EMPTY ``*_airport_insets/`` beside it.
    # Both halves of the production-frame law are measured facts here
    # (2026-09-17): ``dem_production.frame_state`` refuses a frame whose
    # insets DIRECTORY is absent, and ``_bake`` refuses one where an
    # inset FILE for this airport exists but the bake did not report it.
    # An empty directory satisfies the first and never trips the second,
    # so the frame is CONSISTENT with insets off — which is what keeps
    # this pass off the national elevation servers.  The fixture's own
    # ``CYXY_fixture.tif`` is therefore NOT copied.
    base_dem_dir = os.path.join(data_root, "Elevation_data",
                                _round_latlon(AIRPORT_LAT, AIRPORT_LON))
    os.makedirs(base_dem_dir, exist_ok=True)
    stem = _hem_latlon(AIRPORT_LAT, AIRPORT_LON)
    dem = os.path.join(base_dem_dir, stem + ".hgt")
    _write_airport_hgt(dem)
    os.makedirs(os.path.join(base_dem_dir, stem + "_airport_insets"),
                exist_ok=True)
    shutil.copytree(os.path.join(fixture, "Airport_mod_cache"),
                    os.path.join(data_root, "Airport_mod_cache"))
    osm_dir = os.path.join(data_root, "OSM_data")
    _write_osm_seeds(osm_dir, AIRPORT_LAT, AIRPORT_LON,
                     _cache_schemas(repo_root))
    # The AIRPORTS layer is the one cache whose CONTENT this pass needs:
    # O4_Vector_Map.load_airports_and_prepare_dem bails out entirely
    # (airport_layer None -> no auto-patch at all) without it, and it is
    # read with an empty cache_schema, so the fixture's own crop is
    # accepted verbatim.
    fixture_airports = os.path.join(
        fixture, "OSM_data", _round_latlon(AIRPORT_LAT, AIRPORT_LON),
        _short_latlon(AIRPORT_LAT, AIRPORT_LON),
        "%s_airports.osm.bz2" % _short_latlon(AIRPORT_LAT, AIRPORT_LON))
    if not os.path.isfile(fixture_airports):
        raise RuntimeError("the fixture has no airports OSM cache at %s"
                           % fixture_airports)
    _normalise_osm_cache(fixture_airports, os.path.join(
        osm_dir, _round_latlon(AIRPORT_LAT, AIRPORT_LON),
        _short_latlon(AIRPORT_LAT, AIRPORT_LON),
        os.path.basename(fixture_airports)))

    # ---- the X-Plane root ----------------------------------------------
    cifp = os.path.join(xplane_root, "Custom Data", "CIFP")
    os.makedirs(cifp, exist_ok=True)
    shutil.copy2(os.path.join(fixture, "CIFP", "%s.dat" % AIRPORT_ICAO),
                 os.path.join(cifp, "%s.dat" % AIRPORT_ICAO))
    shutil.copytree(os.path.join(fixture, "Custom Scenery"),
                    os.path.join(xplane_root, "Custom Scenery"))

    with open(os.path.join(data_root, "Ortho4XP.cfg"), "w",
              encoding="utf-8") as handle:
        handle.write(AIRPORT_CONFIG % {
            "dem": dem,
            "cifp": cifp,
            "scenery": os.path.join(xplane_root, "Custom Scenery"),
        })
    return data_root, xplane_root


# ---------------------------------------------------------------------------
# Driving the frozen binary over the JSONL protocol
# ---------------------------------------------------------------------------
class _Stream:
    """Collects the child's protocol lines, tees them to a log file."""

    def __init__(self, path):
        self.objects = []
        self.raw = []
        self._file = open(path, "w", encoding="utf-8")
        self._lock = threading.Lock()

    def pump(self, handle):
        for line in handle:
            with self._lock:
                self._file.write(line)
                self._file.flush()
                self.raw.append(line)
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if isinstance(message, dict):
                    self.objects.append(message)
        self._file.close()

    def events(self, name):
        with self._lock:
            return [m for m in self.objects if m.get("event") == name]

    def has(self, name):
        return bool(self.events(name))


def _tail(path, lines=60):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return "".join(handle.readlines()[-lines:])
    except OSError:
        return "(no output captured)"


def _drive(binary, work, data_root, command, jsonl_log, stderr_log,
           deadline, label, tolerated=None):
    """Run one ``build`` command through the frozen binary's protocol.

    Returns ``(stream, elapsed, failures)``.  The protocol-level
    assertions every pass shares (handshake, a step, BuildDone ok,
    RunDone, no Error) are made here; each pass adds its own on-disk
    witnesses on top.

    ``tolerated`` is an optional ``callable(error_text) -> bool``: a
    terminal error it accepts is PRINTED, not failed, and the run's
    ``error_count`` is then not held against the bundle either.  The
    airport pass uses it for the geometry law's verify verdict, which is
    a property of the fixture rather than of the frozen artifact (see
    :func:`run_airport`).  It is never a blanket pardon — every other
    terminal error still fails.
    """
    failures = []
    started = time.time()
    environment = dict(os.environ)
    environment["ORTHO4XP_DATA_ROOT"] = data_root
    environment["PYTHONHASHSEED"] = "0"
    # The bundle must find its own PROJ data whatever the shell says
    # — the same hostile environment the PROJ self-check uses.
    environment["PROJ_LIB"] = os.path.join(work, "nonexistent-proj")
    environment["PROJ_DATA"] = environment["PROJ_LIB"]

    print("   fixture data root: %s" % data_root)
    print("   driving %s --engine-jsonl (%s, steps %s, deadline %d s)"
          % (binary, label, ",".join(command.get("steps") or ["(all)"]),
             deadline))

    with open(stderr_log, "wb") as errors:
        child = subprocess.Popen(
            [binary, "--engine-jsonl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=errors,
            cwd=work,
            env=environment,
            universal_newlines=True,
            bufsize=1,
        )
        stream = _Stream(jsonl_log)
        reader = threading.Thread(target=stream.pump, args=(child.stdout,))
        reader.daemon = True
        reader.start()

        try:
            child.stdin.write(json.dumps(command) + "\n")
            child.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            failures.append(
                "the frozen binary closed its protocol pipe before the "
                "build command was accepted (%s) — a windowed bundle "
                "with no usable stdio, or an early crash" % error)

        if not failures:
            while not stream.has("RunDone"):
                if child.poll() is not None:
                    failures.append(
                        "the frozen binary exited (rc %s) before RunDone"
                        % child.returncode)
                    break
                if time.time() - started > deadline:
                    failures.append(
                        "DEADLINE: no RunDone within %d s" % deadline)
                    child.kill()
                    break
                time.sleep(0.5)

        try:
            child.stdin.close()
        except OSError:
            pass
        grace = max(5.0, deadline - (time.time() - started))
        try:
            child.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=30)
        reader.join(15)

    elapsed = time.time() - started

    if not stream.has("EngineHello"):
        failures.append("no EngineHello handshake on the protocol stream")
    else:
        hello = stream.events("EngineHello")[0]
        print("   EngineHello: Ortho4XP %s, protocol %s"
              % (hello.get("ortho4xp_version"), hello.get("protocol")))

    steps = []
    for event in stream.events("StepProgress"):
        key = event.get("step_key")
        if key and key not in steps:
            steps.append(key)
    if not steps:
        failures.append("no StepProgress events — no build step ran")
    else:
        print("   steps reported: %s" % ", ".join(steps))

    builds = stream.events("BuildDone")
    excused = 0
    if not builds:
        failures.append("no BuildDone event for the tile")
    else:
        for event in builds:
            if event.get("ok"):
                continue
            text = str(event.get("error") or "(no error text)")
            if tolerated is not None and tolerated(text):
                excused += 1
                print("   BuildDone ok=false for %+d%+04d, TOLERATED: %s"
                      % (event.get("lat"), event.get("lon"),
                         text.splitlines()[0][:200]))
                continue
            failures.append(
                "BuildDone ok=false for %+d%+04d: %s"
                % (event.get("lat"), event.get("lon"), text))

    runs = stream.events("RunDone")
    if not runs:
        failures.append("no RunDone event — the run never ended")
    else:
        errors = int(runs[-1].get("error_count") or 0)
        if errors > excused:
            failures.append("RunDone error_count=%s (%d tolerated)"
                            % (errors, excused))

    for event in stream.events("Error"):
        failures.append("engine Error event: %s" % event.get("text"))

    return stream, elapsed, failures


def _report(failures, headline, log_dir, stderr_log, jsonl_log):
    if not failures:
        return 0
    print("", file=sys.stderr)
    print("ERROR: %s" % headline, file=sys.stderr)
    for item in failures:
        print("  - %s" % item, file=sys.stderr)
    print("", file=sys.stderr)
    print("--- child stderr (tail) ---", file=sys.stderr)
    print(_tail(stderr_log), file=sys.stderr)
    print("--- protocol stream (tail) ---", file=sys.stderr)
    print(_tail(jsonl_log, 25), file=sys.stderr)
    print("full logs: %s" % log_dir, file=sys.stderr)
    return 1


def run(binary, repo_root, log_dir, lat, lon, deadline, keep):
    """PASS 1 — a synthetic tile, auto_patch OFF, a .dsf on disk."""
    os.makedirs(log_dir, exist_ok=True)
    jsonl_log = os.path.join(log_dir, "engine-jsonl.log")
    stderr_log = os.path.join(log_dir, "engine-stderr.log")
    work = tempfile.mkdtemp(prefix="frozen-tile-")
    failures = []
    try:
        data_root = _write_fixture(work, repo_root, lat, lon)
        command = {
            "cmd": "build",
            "id": 1,
            "tiles": [[lat, lon]],
            "provider": "BI",
            "zoomlevel": 16,
            "custom_build_dir": "",
            # Explicit step keys (session.build ``steps``): vector,
            # mesh and the imagery step that renders and writes the
            # .dsf.  The masks step is left out on purpose — it is
            # the one step whose coastline/bathymetry limbs fetch
            # from national elevation servers, which no release job
            # should depend on.
            "steps": ["vector", "mesh", "imagery"],
            "slots": 1,
        }
        stream, elapsed, failures = _drive(
            binary, work, data_root, command, jsonl_log, stderr_log,
            deadline, "tile %s" % _short_latlon(lat, lon))

        # ``<build dir>/Earth nav data/<block>/<tile>.dsf`` (FNAMES
        # long_latlon is itself a two-level path), and only the ACTIVATED
        # file counts: build_dsf writes ".dsf.tmp" and renames it last,
        # so a leftover .tmp is a tile that never became scenery.
        dsfs = glob.glob(os.path.join(
            data_root, "Tiles", "*", "Earth nav data", "*", "*.dsf"))
        if not dsfs:
            failures.append(
                "no .dsf written under %s — the tile produced no scenery"
                % os.path.join(data_root, "Tiles"))
        else:
            for path in dsfs:
                size = os.path.getsize(path)
                print("   wrote %s (%d bytes)"
                      % (os.path.relpath(path, data_root), size))
                if size <= 0:
                    failures.append("empty .dsf at %s" % path)

        stderr_text = _tail(stderr_log, 100000)

        # THE STANDALONE ZERO-DEM TRAP: a bundle that cannot read the
        # elevation file falls back to an all-zero raster and still
        # finishes with a .dsf.  The fixture's ramp is 100-159 m, so the
        # engine's own min/max/mean line is the witness.
        altitudes = re.search(
            r"Min altitude: (\S+) , Max altitude: (\S+)", stderr_text)
        if not altitudes:
            failures.append(
                "the build never reported the elevation range — the "
                "elevation source was not loaded at all")
        else:
            print("   elevation read: min %s, max %s"
                  % (altitudes.group(1), altitudes.group(2)))
            if float(altitudes.group(2)) <= 0.0:
                failures.append(
                    "the bundle read an ALL-ZERO elevation raster "
                    "(max %s) from a fixture whose ramp is 100-159 m — "
                    "the .hgt reader or the data root is broken"
                    % altitudes.group(2))

        # Not a failure, but it means this check silently became a
        # network build: the seeded caches went stale.
        if "Downloading OSM data for" in stderr_text:
            print("   WARNING: the build attempted an Overpass download — a "
                  "cache suffix or tag schema changed; update "
                  "OSM_CACHE_SUFFIXES / _cache_schemas in "
                  "scripts/check_frozen_tile.py.")

        print("   frozen tile build finished in %.0f s" % elapsed)
    finally:
        if keep:
            print("   fixture kept at %s" % work)
        else:
            shutil.rmtree(work, ignore_errors=True)

    return _report(failures, "the frozen bundle cannot build a tile.",
                   log_dir, stderr_log, jsonl_log)


def run_airport(binary, repo_root, log_dir, deadline, keep):
    """PASS 2 — ONE REAL AIRPORT SOLVED inside the frozen bundle.

    The vector step alone: ``include_airports`` ->
    ``run_auto_patch_generation`` -> ``auto_patch.engine_v2`` ->
    ``auto_patch_v2.pipeline.build``, which is where HiGHS is imported
    and called.  Mesh and imagery would add minutes and prove nothing
    this pass is about.
    """
    os.makedirs(log_dir, exist_ok=True)
    jsonl_log = os.path.join(log_dir, "engine-airport-jsonl.log")
    stderr_log = os.path.join(log_dir, "engine-airport-stderr.log")
    work = tempfile.mkdtemp(prefix="frozen-airport-")
    failures = []
    try:
        data_root, xplane_root = _write_airport_fixture(work, repo_root)
        print("   X-Plane fixture root: %s" % xplane_root)
        command = {
            "cmd": "build",
            "id": 1,
            "tiles": [[AIRPORT_LAT, AIRPORT_LON]],
            "provider": "BI",
            "zoomlevel": 16,
            "custom_build_dir": "",
            "steps": ["vector"],
            "slots": 1,
        }
        stream, elapsed, failures = _drive(
            binary, work, data_root, command, jsonl_log, stderr_log,
            deadline, "airport %s on tile %s"
            % (AIRPORT_ICAO, _short_latlon(AIRPORT_LAT, AIRPORT_LON)),
            tolerated=lambda text: VERIFY_DEFECT_MARKER in text)

        # ---- the auto-patch protocol events ---------------------------
        # AutoPatchBegin/Progress are emitted by the engine even though
        # the UIs fold them into the vector step's bar; their ABSENCE
        # means auto-patch never ran, which is exactly the silent
        # tile-death this pass exists to refuse.
        if not stream.has("AutoPatchBegin"):
            failures.append(
                "no AutoPatchBegin event — auto-patch never ran at all "
                "(the CIFP resolution or the airports layer failed, so "
                "the bundle's airport solver was never entered)")
        else:
            airports = stream.events("AutoPatchBegin")[0].get("airports")
            print("   AutoPatchBegin: %s" % (airports,))
        # A FAILURE AT ANY STAGE BUT ``verify`` IS FATAL HERE.  The stages
        # are engine_v2's own: ``build`` (load, classify, constrain,
        # SOLVE), ``write``, ``worker``, ``missing``, ``manifest`` — every
        # one of them is a bundle property, and the lazy-import class dies
        # in ``build``.  ``verify`` is not: it is the GEOMETRY LAW's
        # judgement of the emitted surface, i.e. a property of the fixture
        # and the law tables.  On this fixture it currently reports
        # ``runway_transverse 3`` (measured 2026-09-17 and unmoved by the
        # terrain: 4 rows on the fixture's own 1.8 % plane, 3 on a 0.06 %
        # one), and a release must not go red because a synthetic airport
        # leaves a 10 cm crown residual.  It is REPORTED, loudly, never
        # swallowed — and the solve/emit witnesses below are what make
        # this pass a guard rather than a mood.
        verify_defect = None
        for event in stream.events("AutoPatchFailed"):
            stage = str(event.get("stage") or "")
            text = str(event.get("error") or "")
            if stage == "verify":
                verify_defect = text
                continue
            failures.append(
                "AutoPatchFailed %s at stage %s: %s"
                % (event.get("airport"), stage, text))
        progress = stream.events("AutoPatchProgress")
        if progress:
            print("   AutoPatchProgress events: %d (last status %s)"
                  % (len(progress), progress[-1].get("status")))

        # ---- THE SOLVE ITSELF, from the engine's own report -----------
        # ``<data root>/tmp/auto_patch_v2/<tile>/<ICAO>/<ICAO>.report.json``
        # carries ``solve.status`` and the LP's shape.  This is the direct
        # witness that HiGHS ran INSIDE THE BUNDLE and the programme
        # solved — not an inference from a log line.
        reports = glob.glob(os.path.join(
            data_root, "tmp", "auto_patch_v2", "*", AIRPORT_ICAO,
            "%s.report.json" % AIRPORT_ICAO))
        report = None
        if not reports:
            failures.append(
                "no %s.report.json under %s — the bundle's airport "
                "pipeline never reached its own reporting stage"
                % (AIRPORT_ICAO,
                   os.path.join(data_root, "tmp", "auto_patch_v2")))
        else:
            try:
                with open(reports[0], "r", encoding="utf-8") as handle:
                    report = json.load(handle)
            except (OSError, ValueError) as error:
                failures.append("the build report %s is not readable JSON: %s"
                                % (reports[0], error))
        patch = sidecar = None
        if isinstance(report, dict):
            solve = report.get("solve") or {}
            status = str(solve.get("status") or "")
            lp = report.get("lp") or {}
            print("   solve status=%s rounds=%s wall=%ss; LP %s rows x %s "
                  "columns" % (status or "(none)", solve.get("rounds"),
                               solve.get("wall_s"), lp.get("rows"),
                               lp.get("columns")))
            if status not in ("optimal", "feasible"):
                failures.append(
                    "the solve came back %r, not optimal/feasible — the "
                    "linear programme did not solve inside the bundle"
                    % status)
            if not lp.get("rows"):
                failures.append(
                    "the report's LP has NO rows — no programme was built, "
                    "so nothing proves the solver is in the bundle")
            emit = report.get("emit") or {}
            patch = emit.get("patch")
            sidecar = emit.get("sidecar")

        # ---- the patch and its sidecar on disk ------------------------
        # On a clean verify the driver installs them into
        # ``Patches/<block>/<tile>/``; a verify defect leaves them in the
        # scratch dir the report names.  Either location counts — what is
        # asserted is that the bundle EMITTED a solved patch.
        installed = os.path.join(
            data_root, "Patches", _round_latlon(AIRPORT_LAT, AIRPORT_LON),
            _short_latlon(AIRPORT_LAT, AIRPORT_LON),
            "%s_auto.patch.osm" % AIRPORT_ICAO)
        if os.path.isfile(installed):
            patch, sidecar = installed, installed + ".axes.json"
        if not patch or not os.path.isfile(patch):
            failures.append(
                "no %s_auto.patch.osm on disk (neither installed at %s nor "
                "in the scratch dir the report names) — the frozen bundle "
                "did not emit a solved patch"
                % (AIRPORT_ICAO, installed))
            patch = None
        else:
            print("   wrote %s (%d bytes)"
                  % (os.path.relpath(patch, data_root),
                     os.path.getsize(patch)))
            if os.path.getsize(patch) <= 0:
                failures.append("empty patch at %s" % patch)
        if not sidecar:
            sidecar = (patch + ".axes.json") if patch else ""
        if not sidecar or not os.path.isfile(sidecar):
            # A patch with no sidecar degrades every census to the
            # context-free frame (CLAUDE.md); here it also means the
            # emit half never completed.
            failures.append(
                "no .axes.json sidecar beside the patch (%s) — the emit "
                "stage did not finish" % (sidecar or "(no path)"))
        else:
            try:
                with open(sidecar, "r", encoding="utf-8") as handle:
                    axes = json.load(handle)
            except (OSError, ValueError) as error:
                axes = None
                failures.append("the sidecar %s is not readable JSON: %s"
                                % (sidecar, error))
            if isinstance(axes, dict):
                print("   sidecar keys: %s"
                      % ", ".join(sorted(axes)[:12]))
                # ``ruleset`` is the key the harness census reads to know
                # which law family table judged this airport; a sidecar
                # without it is not a law-true one.
                if "ruleset" not in axes:
                    failures.append(
                        "the sidecar carries no 'ruleset' — this is not a "
                        "law-true sidecar (every census would silently "
                        "degrade)")
                if not axes.get("axes"):
                    failures.append(
                        "the sidecar carries no 'axes' — the solve "
                        "produced no graded surface")

        stderr_text = _tail(stderr_log, 200000)

        # THE LAZY-IMPORT CLASS, NAMED.  A bundle missing the extension
        # dies inside the solver at call time; without this the failure
        # would read "CYXY did not solve" instead of "the bundle omitted
        # highspy".  Reported against the stream AND the log, because a
        # worker traceback reaches only one of them.
        # ``engine_v2`` formats the exception as ``[v2] {exc}``, i.e. the
        # MESSAGE alone — a removed extension reads "No module named
        # 'highspy._core'" with no exception class in sight (measured
        # 2026-09-17 against a scratch copy of the mac freeze with
        # ``_internal/highspy`` moved aside).  Both spellings, and any
        # dynamic-library miss, are named.
        pattern = (r"(ModuleNotFoundError|ImportError|No module named|"
                   r"cannot open shared object|Library not loaded)[^\n]*")
        seen = set()
        for text in ([str(e.get("error") or "")
                      for e in stream.events("AutoPatchFailed")]
                     + [stderr_text]):
            found = re.search(pattern, text)
            if found and found.group(0).strip() not in seen:
                seen.add(found.group(0).strip())
                failures.append(
                    "THE LAZY-IMPORT CLASS: the frozen bundle is missing a "
                    "module the airport solver imports at CALL TIME (the "
                    "highspy precedent, 2026-09-10) — %s"
                    % found.group(0).strip()[:400])

        if verify_defect:
            # Not a bundle failure — see the stage comment above.
            print("   WARNING: the emitted surface did not pass the geometry "
                  "law's verify on this synthetic fixture: %s"
                  % verify_defect.strip().splitlines()[0][:300])
            print("   (the solve and the emit are what this pass guards; a "
                  "verify residual on a fixture airport is a law/fixture "
                  "matter, tracked in the lane report, not a release gate)")

        if "Downloading OSM data for" in stderr_text:
            print("   WARNING: the airport pass attempted an Overpass "
                  "download — a cache suffix or tag schema changed.")

        print("   frozen airport solve finished in %.0f s" % elapsed)
    finally:
        if keep:
            print("   fixture kept at %s" % work)
        else:
            shutil.rmtree(work, ignore_errors=True)

    return _report(
        failures,
        "the frozen bundle cannot SOLVE an airport (%s)." % AIRPORT_ICAO,
        log_dir, stderr_log, jsonl_log)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", help="the frozen executable under test")
    parser.add_argument("--pass", dest="which", default="both",
                        choices=("tile", "airport", "both"),
                        help="which pass(es) to run (default both)")
    parser.add_argument("--deadline", type=int, default=300,
                        help="seconds for the TILE pass (default 300)")
    parser.add_argument("--airport-deadline", type=int, default=300,
                        help="seconds for the AIRPORT pass (default 300)")
    parser.add_argument("--logs", default="frozen-tile-logs",
                        help="directory for the JSONL + stderr logs")
    parser.add_argument("--lat", type=int, default=DEFAULT_LAT)
    parser.add_argument("--lon", type=int, default=DEFAULT_LON)
    parser.add_argument("--keep", action="store_true",
                        help="keep the generated fixture for debugging")
    arguments = parser.parse_args(argv)

    binary = os.path.abspath(arguments.binary)
    if not os.path.isfile(binary):
        print("ERROR: no frozen binary at %s" % binary, file=sys.stderr)
        return 1
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.abspath(arguments.logs)

    status = 0
    if arguments.which in ("tile", "both"):
        print("== PASS 1/2: the frozen bundle builds a TILE ==")
        status |= run(binary, repo_root, log_dir, arguments.lat,
                      arguments.lon, arguments.deadline, arguments.keep)
    if arguments.which in ("airport", "both"):
        # Both passes always run, even when the first one failed: two
        # independent witnesses of the same bundle are worth more than
        # one, and the release job uploads both logs at once.
        print("== PASS 2/2: the frozen bundle SOLVES %s =="
              % AIRPORT_ICAO)
        status |= run_airport(binary, repo_root, log_dir,
                              arguments.airport_deadline, arguments.keep)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
