#!/usr/bin/env python3
"""Recipe for the frozen vector -> mesh -> DSF reference fixture (#856, B3-24).

The inherited ``O4_*`` vector, mesh and DSF stages had no frozen reference:
a change there was gated by "one tile builds and looks right"
(``docs/specs/code-quality-beta3-spec.md`` §6).  This tool writes a tiny
SYNTHETIC window through the engine's own stage functions, and
``tests/test_mesh_dsf_oracle.py`` replays every stage against the committed
bytes.  No corpus, no imagery, no network: the window is hand-made.

The window (tile ``+45+007``, tile-relative coordinates):

* a 0.02 deg x 0.02 deg frame, ``[0.40, 0.42]^2``, DUMMY edges;
* one inland WATER square and one flat PATCH RING square (the
  ``PATCH_RING_MARKER`` ``include_patches`` stamps, altitude 112.5 m) with
  a free DUMMY run inside it, each square with its region seed, written by
  ``O4_Vector_Utils.Vector_Map`` exactly as step 1 writes ``.node``/``.poly``;
* a 1 arc-second DEM over the frame plus a 36-px margin (145 x 145 posts,
  values exact in float32), the ``.alt`` raster Triangle4XP samples;
* Triangle4XP run with ``build_mesh``'s own switch and argument builders
  (``triangle_switches``, ``triangle4xp_command``), binary exchange files;
* ``post_process_nodes_altitudes`` + ``write_mesh_file`` -> ``.mesh``;
* ``build_dsf`` twice -> ``full_ortho.dsf`` and ``default_xplane.dsf``
  (the MD5 footer included).  The Global Scenery elevation / bathymetry
  raster is stubbed to empty and ``default_xplane`` reads a two-terrain
  synthetic landclass map (the same stubs ``test_dsf_texture_modes`` uses).

Every committed file and its sha256 is in ``MANIFEST.json``.  Triangle4XP
is the one step expected to differ by platform (#875: FMA contraction in
the platform's compiler).  Its committed ``.1.node`` / ``.1.ele`` feed every
downstream twin, so the mesh and DSF twins run everywhere; the Triangle twin
compares against the digests pinned for the platform AND binary that made
them (``triangle`` in the manifest).

Usage (from ``Ortho4XP/``)::

    venv/bin/python tools/fixtures/make_mesh_dsf_fixture.py --check
    venv/bin/python tools/fixtures/make_mesh_dsf_fixture.py --write --reason "why"
    venv/bin/python tools/fixtures/make_mesh_dsf_fixture.py --pin-platform --reason "why"

``--check`` (the default) regenerates into a temporary directory and lists
every file whose bytes moved; exit 1 on any.  ``--write`` regenerates the
committed fixture: a change that MUST move the bytes does this in the same
PR and states the reason, recorded in the manifest's history (the
ratchet-baseline discipline).  ``--pin-platform`` runs this machine's
Triangle4XP on the committed inputs and records its digests for this
platform and binary; where steps 2-3, replayed on the committed Triangle
outputs, do not reproduce the committed bytes on this platform, it records
this platform's own digests too (``platform_files``) — the measured,
stated exception, never a silent tolerance.  No fixture file changes.
"""

from __future__ import annotations

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.  Twin: ``tests/test_console_encoding.py``.
import os as _o4os  # noqa: E401,E402
import sys as _o4sys

_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.dirname(_o4os.path.abspath(__file__)))), "src"))
import O4_Console_Encoding as _o4console  # noqa: E402

_o4console.configure_console_streams()

import argparse  # noqa: E402
import datetime  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import queue  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import numpy  # noqa: E402
import O4_Default_Terrain_Map as DTM  # noqa: E402
import O4_DSF_Utils as DSF  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_Mesh_Utils as MESH  # noqa: E402
import O4_Triangle_Binary as TRI_BIN  # noqa: E402
import O4_Vector_Map as VMAP  # noqa: E402
import O4_Vector_Utils as VECT  # noqa: E402

ORTHO4XP = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
FIXTURE_DIR = os.path.join(ORTHO4XP, "tests", "fixtures", "mesh_dsf")
MANIFEST = "MANIFEST.json"
#: The committed fixture's size budget (spec §6: files, not only digests,
#: when they total 2 MB or less).
SIZE_BUDGET = 2 * 1024 * 1024

LAT, LON = 45, 7
STEM = "Data" + FNAMES.short_latlon(LAT, LON)
FRAME = (0.40, 0.42)              # tile-relative, both axes
POSTING = 1.0 / 3600              # 1 arc-second
MARGIN_PX = 36                    # the margin the mesh step expects
WATER_RING = (0.403, 0.409)
PATCH_RING = (0.411, 0.417)
PATCH_ALT = 112.5                 # exact in binary
PATCH_INTERIOR_RUN = ((0.4125, 0.4130, 0.0), (0.4140, 0.4145, 0.0),
                      (0.4155, 0.4150, 0.0))
MIN_ANGLE = 10
CURVATURE_TOL = 1.0
LIMIT_STEINER = "S500000"
DSF_MODES = ("full_ortho", "default_xplane")

INPUTS = (STEM + ".node", STEM + ".poly", STEM + ".alt")
TRIANGLE_OUTPUTS = (STEM + ".1.node", STEM + ".1.ele")
MESH_OUTPUT = STEM + ".mesh"


def platform_key():
    """``mac`` / ``win`` / ``lin`` — the ``Utils/<dir>`` naming."""
    if sys.platform == "darwin":
        return "mac"
    if sys.platform.startswith("win"):
        return "win"
    return "lin"


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def triangle_binary():
    """This platform's Triangle4XP (``O4_Mesh_Utils.Triangle4XP_cmd``)."""
    return MESH.Triangle4XP_cmd.strip()


################################################################################
# Stage 0: the synthetic inputs (vector stage writer + DEM raster)


def _square(lo, hi, z, per_side=4):
    """A closed counter-clockwise square way, ``per_side`` segments a side,
    as the ``(x, y, z)`` rows ``Vector_Map.insert_way`` takes."""
    steps = [lo + (hi - lo) * k / per_side for k in range(per_side)]
    ring = ([(x, lo) for x in steps] + [(hi, y) for y in steps]
            + [(hi - (x - lo), hi) for x in steps]
            + [(lo, hi - (y - lo)) for y in steps] + [(lo, lo)])
    return numpy.array([(x, y, z) for (x, y) in ring])


def write_vector_inputs(directory):
    """``Data+45+007.node`` / ``.poly`` through the step-1 writer."""
    vector_map = VECT.Vector_Map()
    vector_map.insert_way(_square(*FRAME, 0.0), "DUMMY", check=True)
    vector_map.insert_way(_square(*WATER_RING, 0.0), "WATER", check=True)
    vector_map.insert_way(_square(*PATCH_RING, PATCH_ALT),
                          VMAP.PATCH_RING_MARKER, check=True)
    # A free DUMMY run inside the patch (the orthogrid / gluing nodes a
    # real patch interior holds): the R18-1b solve has vertices to value.
    vector_map.insert_way(numpy.array(PATCH_INTERIOR_RUN), "DUMMY",
                          check=True)
    vector_map.seeds["WATER"] = [numpy.array([sum(WATER_RING) / 2] * 2)]
    vector_map.seeds["INTERP_ALT"] = [numpy.array([sum(PATCH_RING) / 2] * 2)]
    vector_map.snap_to_grid(9)
    vector_map.write_node_file(os.path.join(directory, STEM + ".node"))
    vector_map.write_poly_file(os.path.join(directory, STEM + ".poly"))


def dem_window():
    """The raster's geometry, in the attributes ``triangle4xp_command`` reads."""
    margin = MARGIN_PX * POSTING
    n = int(round((FRAME[1] - FRAME[0]) / POSTING)) + 2 * MARGIN_PX + 1
    return SimpleNamespace(nxdem=n, nydem=n, x0=FRAME[0] - margin,
                           y0=FRAME[0] - margin, x1=FRAME[1] + margin,
                           y1=FRAME[1] + margin, nodata=-32768)


def dem_values(dem):
    """A bowl, a ramp and diagonal ridges on the integer post grid; every
    value is a multiple of 1/16 m under 2^11, so exact in float32 and
    identical on any platform."""
    (j, i) = numpy.meshgrid(numpy.arange(dem.nxdem), numpy.arange(dem.nydem))
    bowl = ((i - 70) ** 2 + (j - 80) ** 2) // 4
    ramp = 3 * i + j
    ridges = 24 * numpy.abs((i + j) % 24 - 12)
    return (100.0 + (bowl + ramp + ridges) / 16.0).astype(numpy.float32)


def write_dem(directory):
    dem = dem_window()
    dem_values(dem).tofile(os.path.join(directory, STEM + ".alt"))
    return dem


################################################################################
# Stage 1: Triangle4XP (the platform-dependent step)


def run_triangle(directory, binary=None):
    """Mesh the window as ``build_mesh`` does: its switch and argument
    builders, BINARY exchange files (``-b``, the default since RULINGS
    2026-10-17a Q6 — raw little-endian doubles, so no platform's text
    formatting or line endings enter the bytes), the outputs adopted onto
    the names step 2 reads.  Returns the completed process."""
    binary = binary or triangle_binary()
    if not TRI_BIN.binary_capable(binary):
        raise RuntimeError(f"{binary} does not carry -b (binary exchange)")
    stem = os.path.join(directory, STEM)
    numpy.ones((1001, 1001), dtype=numpy.float32).tofile(stem + ".weight")
    switches = MESH.triangle_switches(MIN_ANGLE, "A", "Q", "", "b",
                                      LIMIT_STEINER)
    command = MESH.triangle4xp_command(
        binary, switches, LAT, dem_window(), CURVATURE_TOL, stem + ".alt",
        stem + ".weight", TRI_BIN.binary_inputs(stem + ".node",
                                                stem + ".poly"))
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                check=False)
        if result.returncode == 0:
            TRI_BIN.adopt_binary_outputs(command[-1], stem + ".1.node",
                                         stem + ".1.ele")
    finally:
        # The weight map is 4 MB of ones; the ``.1.poly`` (switch ``-p``)
        # is read by nothing downstream.
        for leftover in (stem + ".weight", stem + ".1.poly"):
            if os.path.exists(leftover):
                os.remove(leftover)
    return result


################################################################################
# Stages 2-3: post-processing + .mesh, then the DSF writer


def mesh_tile(directory):
    """The stub tile carrying what steps 2 and 3 read."""
    tile = SimpleNamespace(
        lat=LAT, lon=LON, build_dir=directory, iterate=0,
        water_smoothing=2, sea_smoothing_mode="zero",
        mesh_zl=17, default_zl=16, default_website="BI", cover_zl=18,
        cover_extent=1, cover_airports_with_highres="False", zone_list=[],
        use_masks_for_inland=False, water_tech="XP12",
        normal_map_strength=1, imprint_masks_to_dds=False, ratio_water=0.3,
        ratio_bathy=1.0, terrain_casts_shadows=True,
        use_decal_on_terrain=False, overlay_lod=40000, mask_zl=14,
        texture_mode="full_ortho", airport_ortho_fade_width=1000.0,
        grouped=False)
    return tile


def run_mesh_stage(directory):
    """``post_process_nodes_altitudes`` + ``write_mesh_file`` on the
    Triangle outputs in ``directory`` (rewrites its ``.1.node`` in place,
    as a build does); returns the ``.mesh`` path."""
    tile = mesh_tile(directory)
    vertices = MESH.post_process_nodes_altitudes(tile)
    MESH.write_mesh_file(tile, vertices)
    return FNAMES.mesh_file(directory, LAT, LON)


def synthetic_terrain_map():
    """Two projected landclass terrains split at the window's middle."""
    (lo, hi) = (LON + FRAME[0], LON + FRAME[1])
    (south, north) = (LAT + FRAME[0], LAT + FRAME[1])
    mid = (lo + hi) / 2
    tris = [((lo, south), (mid, south), (mid, north)),
            ((lo, south), (mid, north), (lo, north)),
            ((mid, south), (hi, south), (hi, north)),
            ((mid, south), (hi, north), (mid, north))]
    terrain_map = DTM.DefaultTerrainMap(
        ["lib/g10/terrain10/grass.ter", "lib/g10/terrain10/asphalt.ter"],
        tris, [0, 0, 1, 1])
    terrain_map._projected_cache = {0: True, 1: True}
    return terrain_map


@contextmanager
def dsf_stubs():
    """The hermetic stubs: no Global Scenery donor DEM / bathymetry, a
    synthetic landclass map for ``default_xplane``."""
    saved = (DSF.elevation_and_bathymetry_data,
             DSF.extract_elevation_and_bathymetry_data,
             DTM.DefaultTerrainMap.__dict__["from_tile"])
    terrain_map = synthetic_terrain_map()
    DSF.elevation_and_bathymetry_data = lambda tile: (b"", b"")
    DSF.extract_elevation_and_bathymetry_data = lambda lat, lon: (b"", b"")
    DTM.DefaultTerrainMap.from_tile = classmethod(
        lambda cls, lat, lon: terrain_map)
    try:
        yield
    finally:
        (DSF.elevation_and_bathymetry_data,
         DSF.extract_elevation_and_bathymetry_data) = saved[:2]
        DTM.DefaultTerrainMap.from_tile = saved[2]


def run_dsf_stage(directory, mode):
    """``build_dsf`` on ``directory``'s ``.mesh`` in ``mode``; returns the
    emitted DSF's bytes (the ``.dsf.tmp`` the writer leaves, MD5 footer
    included).  ``directory`` must hold the ``.mesh`` only: the build dir
    is a fresh subdirectory per mode."""
    build_dir = os.path.join(directory, "build_" + mode)
    emitted = FNAMES.dsf_file(build_dir, LAT, LON) + ".tmp"
    os.makedirs(os.path.dirname(emitted))
    os.makedirs(os.path.join(build_dir, "textures"))
    shutil.copyfile(FNAMES.mesh_file(directory, LAT, LON),
                    FNAMES.mesh_file(build_dir, LAT, LON))
    tile = mesh_tile(build_dir)
    tile.texture_mode = mode
    with dsf_stubs():
        rc = DSF.build_dsf(tile, queue.Queue())
    if rc != 1:
        raise RuntimeError(f"build_dsf({mode}) returned {rc}")
    with open(emitted, "rb") as handle:
        return handle.read()


################################################################################
# The whole recipe, the manifest, and the check


DOWNSTREAM = (MESH_OUTPUT,) + tuple(mode + ".dsf" for mode in DSF_MODES)


def committed_names():
    return INPUTS + TRIANGLE_OUTPUTS + DOWNSTREAM


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def replay_downstream(source, work):
    """Steps 2-3 on ``source``'s inputs and Triangle outputs, run in the
    empty directory ``work``; returns ``{name: bytes}`` for the ``.mesh``
    and each DSF.  The Triangle outputs are READ from ``source``, so a
    platform whose mesher differs (#875) still replays these stages on the
    frozen mesh."""
    for name in INPUTS + TRIANGLE_OUTPUTS:
        shutil.copyfile(os.path.join(source, name), os.path.join(work, name))
    with open(run_mesh_stage(work), "rb") as handle:
        out = {MESH_OUTPUT: handle.read()}
    for mode in DSF_MODES:
        out[mode + ".dsf"] = run_dsf_stage(work, mode)
    return out


def generate(directory, binary=None):
    """Write every fixture file into ``directory``; returns the file names."""
    write_vector_inputs(directory)
    write_dem(directory)
    result = run_triangle(directory, binary)
    if result.returncode:
        raise RuntimeError("Triangle4XP failed:\n" + result.stdout
                           + result.stderr)
    work = os.path.join(directory, "_work")
    os.makedirs(work)
    try:
        for (name, data) in replay_downstream(directory, work).items():
            with open(os.path.join(directory, name), "wb") as handle:
                handle.write(data)
    finally:
        shutil.rmtree(work)
    return committed_names()


def read_manifest(directory=FIXTURE_DIR):
    with open(os.path.join(directory, MANIFEST), encoding="utf-8") as handle:
        return json.load(handle)


def write_manifest(manifest, directory=FIXTURE_DIR):
    with open(os.path.join(directory, MANIFEST), "w", encoding="utf-8",
              newline="\n") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")


def expected_sha256(manifest, name):
    """The digest ``name`` must reproduce on THIS platform: the committed
    file's, unless ``--pin-platform`` recorded the platform's own (#875)."""
    override = manifest.get("platform_files", {}).get(platform_key(), {})
    return override.get(name, manifest["files"][name])


def expected_triangle_hashes(manifest, binary=None):
    """The ``.1.node`` / ``.1.ele`` digests pinned for this platform's
    ``binary``, or ``None`` when that platform and binary were never
    pinned (a different binary is a different mesher)."""
    pin = manifest.get("triangle", {}).get(platform_key())
    binary = binary or triangle_binary()
    if (not pin or not os.path.isfile(binary)
            or pin["binary_sha256"] != sha256_file(binary)):
        return None
    return pin["outputs"]


def _triangle_pin(binary, directory):
    return {"binary": os.path.relpath(os.path.abspath(binary),
                                      ORTHO4XP).replace(os.sep, "/"),
            "binary_sha256": sha256_file(binary),
            "outputs": {name: sha256_file(os.path.join(directory, name))
                        for name in TRIANGLE_OUTPUTS}}


def _history(manifest, reason):
    return manifest.get("history", []) + [{
        "date": datetime.date.today().isoformat(),
        "platform": platform_key(), "reason": reason}]


def check(binary=None):
    """Regenerate in a temporary directory; returns ``(moved, notes)``:
    the names whose bytes moved, and what could not be judged here."""
    manifest = read_manifest()
    (moved, notes) = ([], [])
    pinned = expected_triangle_hashes(manifest, binary)
    with tempfile.TemporaryDirectory(prefix="mesh_dsf_check_") as scratch:
        write_vector_inputs(scratch)
        write_dem(scratch)
        moved += [name for name in INPUTS
                  if sha256_file(os.path.join(scratch, name))
                  != manifest["files"][name]]
        if pinned is None:
            notes.append(f"Triangle4XP is not pinned for {platform_key()} "
                         "and this binary: run --pin-platform")
        elif run_triangle(scratch, binary).returncode:
            moved += list(TRIANGLE_OUTPUTS)
        else:
            moved += [name for name in TRIANGLE_OUTPUTS
                      if sha256_file(os.path.join(scratch, name))
                      != pinned[name]]
        work = os.path.join(scratch, "_work")
        os.makedirs(work)
        out = replay_downstream(FIXTURE_DIR, work)
        moved += [name for name in DOWNSTREAM
                  if sha256_bytes(out[name])
                  != expected_sha256(manifest, name)]
    return (moved, notes)


def write(reason, binary=None):
    """Regenerate the committed fixture and record the reason."""
    path = os.path.join(FIXTURE_DIR, MANIFEST)
    old = read_manifest() if os.path.isfile(path) else {}
    binary = binary or triangle_binary()
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    names = generate(FIXTURE_DIR, binary)
    files = {name: sha256_file(os.path.join(FIXTURE_DIR, name))
             for name in names}
    total = sum(os.path.getsize(os.path.join(FIXTURE_DIR, name))
                for name in names)
    if total > SIZE_BUDGET:
        raise RuntimeError(f"fixture is {total} bytes, over the "
                           f"{SIZE_BUDGET}-byte budget (spec section 6)")
    manifest = {
        "issue": "#856 (B3-24), code-quality-beta3-spec.md section 6",
        "recipe": "Ortho4XP/tools/fixtures/make_mesh_dsf_fixture.py",
        "files": files,
        "total_bytes": total,
        # A new fixture drops every other platform's pins: they were taken
        # on the old inputs.
        "triangle": {platform_key(): _triangle_pin(binary, FIXTURE_DIR)},
        "platform_files": {},
        "history": _history(old, reason),
    }
    write_manifest(manifest)
    return manifest


def pin_platform(reason, binary=None):
    """Pin THIS platform: its Triangle4XP's output digests on the committed
    inputs and, only where steps 2-3 replayed on the committed Triangle
    outputs do not reproduce the committed bytes here, this platform's own
    digests.  The reason goes in the history; no fixture file changes."""
    manifest = read_manifest()
    binary = binary or triangle_binary()
    with tempfile.TemporaryDirectory(prefix="mesh_dsf_pin_") as scratch:
        for name in INPUTS:
            shutil.copyfile(os.path.join(FIXTURE_DIR, name),
                            os.path.join(scratch, name))
        result = run_triangle(scratch, binary)
        if result.returncode:
            raise RuntimeError("Triangle4XP failed:\n" + result.stdout)
        manifest.setdefault("triangle", {})[platform_key()] = _triangle_pin(
            binary, scratch)
        work = os.path.join(scratch, "_work")
        os.makedirs(work)
        out = replay_downstream(FIXTURE_DIR, work)
    differs = {name: sha256_bytes(data) for (name, data) in out.items()
               if sha256_bytes(data) != manifest["files"][name]}
    platforms = manifest.setdefault("platform_files", {})
    if differs:
        platforms[platform_key()] = differs
    else:
        platforms.pop(platform_key(), None)
    manifest["history"] = _history(manifest, reason)
    write_manifest(manifest)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true",
                        help="regenerate in a temp dir and list moved files "
                             "(default)")
    action.add_argument("--write", action="store_true",
                        help="regenerate the committed fixture")
    action.add_argument("--pin-platform", action="store_true",
                        help="pin this platform's Triangle4XP outputs, and "
                             "its own step 2-3 digests where they differ")
    parser.add_argument("--reason",
                        help="why the bytes move (--write, --pin-platform)")
    parser.add_argument("--triangle", help="Triangle4XP binary to run "
                                           "(default: this platform's)")
    args = parser.parse_args(argv)
    if (args.write or args.pin_platform) and not args.reason:
        parser.error("--write and --pin-platform need --reason")
    if args.write:
        manifest = write(args.reason, args.triangle)
        print(f"wrote {len(manifest['files'])} files, "
              f"{manifest['total_bytes']} bytes, to {FIXTURE_DIR}")
        return 0
    if args.pin_platform:
        manifest = pin_platform(args.reason, args.triangle)
        print(json.dumps({
            "triangle": manifest["triangle"][platform_key()],
            "platform_files": manifest["platform_files"].get(
                platform_key(), {})}, indent=2))
        return 0
    (moved, notes) = check(args.triangle)
    for name in moved:
        print(f"MOVED {name}")
    for note in notes:
        print(f"NOTE {note}")
    print("fixture reproduces" if not moved else
          f"{len(moved)} file(s) moved: regenerate with --write --reason "
          "only if the change MUST move them")
    return 1 if moved else 0


if __name__ == "__main__":
    sys.exit(main())
