#!/usr/bin/env python3
"""THE FROZEN TILE-BUILD SMOKE TEST — helper interpreter (stdlib ONLY).

Driven by ``scripts/check_frozen_tile.sh``; see that file for why this
check exists and where it sits in every release job.

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

* **auto_patch is OFF.**  Since lane ``betafirstrun`` the engine REFUSES
  auto-patch with no CIFP data, and the explicit opt-out
  (``auto_patch=None``) is the documented way to build without one.
  A stub X-Plane tree with a synthetic apt.dat airport and a synthetic
  CIFP cycle would additionally cover the auto_patch_v2 + highspy
  lazy-import class; it is NOT cheap (a synthetic airport the v2 linear
  programme actually solves is a fixture in its own right, and a
  refusal there would block releases for a fixture bug, not a bundle
  bug).  That gap is stated in the lane report rather than papered over.

* **Bounded.**  The whole check runs under a deadline enforced here,
  because coreutils ``timeout`` exists on neither the mac runner nor the
  maintainer's mac.  On any miss the child's stderr tail is printed and
  the JSONL stream plus stderr are left in the log directory for the
  job to upload.

Usage::

    check_frozen_tile.py <frozen-binary> [--deadline S] [--logs DIR]
                         [--lat N] [--lon N] [--keep]
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

    ``O4_OSM_Utils`` accepts a cache whose first two lines carry
    ``o4_tag_schema="<schema>"`` and whose body ends with ``</osm>``; its
    reader is line-based, not an XML parser, so carrying every schema
    marker on the root tag at once is fine and keeps one seed valid for
    every layer.
    """
    # FNAMES.osm_cached -> OSM_dir/<10-degree block>/<tile>/<tile>_<suffix>
    directory = os.path.join(osm_dir, _round_latlon(lat, lon),
                             _short_latlon(lat, lon))
    os.makedirs(directory, exist_ok=True)
    markers = " ".join('o4_tag_schema="%s"' % s for s in schemas)
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<osm version="0.6" generator="check_frozen_tile" %s>\n'
        "</osm>\n" % markers
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


def run(binary, repo_root, log_dir, lat, lon, deadline, keep):
    os.makedirs(log_dir, exist_ok=True)
    jsonl_log = os.path.join(log_dir, "engine-jsonl.log")
    stderr_log = os.path.join(log_dir, "engine-stderr.log")
    work = tempfile.mkdtemp(prefix="frozen-tile-")
    started = time.time()
    failures = []
    try:
        data_root = _write_fixture(work, repo_root, lat, lon)
        environment = dict(os.environ)
        environment["ORTHO4XP_DATA_ROOT"] = data_root
        environment["PYTHONHASHSEED"] = "0"
        # The bundle must find its own PROJ data whatever the shell says
        # — the same hostile environment the PROJ self-check uses.
        environment["PROJ_LIB"] = os.path.join(work, "nonexistent-proj")
        environment["PROJ_DATA"] = environment["PROJ_LIB"]

        print("   fixture data root: %s" % data_root)
        print("   driving %s --engine-jsonl (tile %s, deadline %d s)"
              % (binary, _short_latlon(lat, lon), deadline))

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
            reader = threading.Thread(target=stream.pump,
                                      args=(child.stdout,))
            reader.daemon = True
            reader.start()

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

        # ---- the assertions -------------------------------------------
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
        if not builds:
            failures.append("no BuildDone event for the tile")
        else:
            for event in builds:
                if not event.get("ok"):
                    failures.append(
                        "BuildDone ok=false for %+d%+04d: %s"
                        % (event.get("lat"), event.get("lon"),
                           event.get("error") or "(no error text)"))

        runs = stream.events("RunDone")
        if not runs:
            failures.append("no RunDone event — the run never ended")
        elif runs[-1].get("error_count"):
            failures.append("RunDone error_count=%s"
                            % runs[-1].get("error_count"))

        for event in stream.events("Error"):
            failures.append("engine Error event: %s" % event.get("text"))

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

    if failures:
        print("", file=sys.stderr)
        print("ERROR: the frozen bundle cannot build a tile.", file=sys.stderr)
        for item in failures:
            print("  - %s" % item, file=sys.stderr)
        print("", file=sys.stderr)
        print("--- child stderr (tail) ---", file=sys.stderr)
        print(_tail(stderr_log), file=sys.stderr)
        print("--- protocol stream (tail) ---", file=sys.stderr)
        print(_tail(jsonl_log, 25), file=sys.stderr)
        print("full logs: %s" % log_dir, file=sys.stderr)
        return 1
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", help="the frozen executable under test")
    parser.add_argument("--deadline", type=int, default=300,
                        help="seconds for the whole check (default 300)")
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
    return run(binary, repo_root, os.path.abspath(arguments.logs),
               arguments.lat, arguments.lon, arguments.deadline,
               arguments.keep)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
