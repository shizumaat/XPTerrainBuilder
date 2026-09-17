"""TWIN — the EXACT projection dump and its comparer (lane ``xplatspread``).

RULINGS 2026-09-17d could only BRACKET the platform spread of
``Frame.to_xy`` as "(5e-7, 5e-5) m", inferred from digests.  Owner Q 17d-1
(option A: the canonical vertex identity moves into the metre domain; "can
we simply standardize everything to the nearest 1 mm?") has to be answered
against the real distribution, so this instrument reports EXACT values.

Four ways it could silently lie instead of failing, one test each:

1. the join is not exact (a nearest-neighbour join would report a spread
   that is really the join's own error);
2. the STRADDLE count is wrong at a boundary — it is the whole number the
   owner's grid choice rests on, and the interesting case is exactly the
   tie, where ``round``'s banker's rule and a snap's ``floor(v/g + 0.5)``
   disagree;
3. the hook is not byte-neutral when off (a wrapper that "just records"
   still replaces the frame's own function, and 17d's whole finding is a
   last-ulp effect);
4. the comparer needs a third-party package (the mac release runner's
   bare python3 has none).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from auto_patch_v2.pipeline import xplat

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))


def _dump(rows, name="mac", quantise=0.0, solved=None):
    """A dump payload carrying ``rows`` as ``(lon, lat, x, y)`` floats."""
    out = {
        "icao": "CYXY",
        "env": {"machine": name, "platform": name},
        "quantise_m": quantise,
        "recorded": [[float(lon).hex(), float(lat).hex(),
                      float(x).hex(), float(y).hex()]
                     for lon, lat, x, y in rows],
        "counts": {"recorded": len(rows)},
    }
    if solved is not None:
        out["solved_z"] = [[float(x).hex(), float(y).hex(), float(z).hex()]
                           for x, y, z in solved]
    return out


# ------------------------------------------------------- the arithmetic

def test_the_join_is_exact_and_never_proximity():
    """Two dumps whose INPUTS differ in the last ulp share no coordinate:
    the join key is the exact input, so such a row simply does not join —
    it must never be paired with its neighbour and reported as a spread."""
    a = _dump([(1.0, 2.0, 100.0, 200.0)])
    b = _dump([(1.0 + 2 ** -52, 2.0, 100.5, 200.0)], name="linux")
    lines = xplat.compare_projection({"mac": a, "linux": b})
    joined = [ln for ln in lines if "recorded (n=" in ln]
    assert joined == [] or "n=0" in joined[0], (
        "a row whose INPUT differs must not join: %s" % joined)


def test_a_platform_against_itself_has_zero_spread_and_no_straddles():
    rows = [(0.1 * k, 0.2 * k, 12.3456789 * k, -98.7654321 * k)
            for k in range(1, 200)]
    a = _dump(rows)
    lines = xplat.compare_projection({"mac": a, "mac2": _dump(rows, "mac2")})
    text = "\n".join(lines)
    assert "max 0.000e+00" in text, text
    for grid in ("0.0001", "0.001", "0.01"):
        assert "%s m:0" % grid in text, (grid, text)


def test_the_straddle_count_is_the_snap_boundary_and_not_bankers_rounding():
    """THE NUMBER THE OWNER'S GRID CHOICE RESTS ON.  Three pairs at the
    1 mm grid: one that cannot straddle (both inside the same cell), one
    that must (either side of a boundary by less than the grid), and one
    exactly ON a boundary, where Python's banker's ``round`` would call
    0.0005 -> 0 and 0.0015 -> 2, i.e. report a straddle that a snap does
    not make."""
    grid = 1e-3
    assert xplat._snap(0.0005, grid) == 1, "a snap takes the tie UP"
    assert xplat._snap(0.0015, grid) == 2
    assert round(0.0005 / grid) == 0, (
        "the precedent: banker's rounding would disagree with the snap")
    pairs = [
        (0.00012, 0.00013),      # same cell, no straddle
        (0.00049, 0.00051),      # either side of the 0.5-cell boundary
        (0.0012345, 0.0012347),  # same cell again
    ]
    got = xplat._straddles(pairs)
    assert got["0.001"] == 1, got
    assert got["0.01"] == 0, got
    # …and at the 0.1 mm grid the SAME pair does not straddle: both snap
    # to multiple 5.  A finer grid is not monotonically worse; what
    # matters is where the boundaries fall relative to the spread.
    assert got["0.0001"] == 0, got


def test_a_coordinate_straddles_when_EITHER_axis_does():
    """The number an identity join would actually lose is per VERTEX, not
    per axis: x agreeing does not save a vertex whose y straddles."""
    a = _dump([(1.0, 2.0, 5.00049, 7.0)])
    b = _dump([(1.0, 2.0, 5.00049, 7.00051)], name="linux")
    lines = xplat.compare_projection({"mac": a, "linux": b})
    text = "\n".join(lines)
    assert "straddles x  0.0001 m:0 0.001 m:0 0.01 m:0 0.5 m:0" in text, text
    assert "straddles COORD 0.0001 m:1 0.001 m:1 0.01 m:0 0.5 m:0 of 1" \
        in text, text
    # …and it NAMES the coordinate, because the census's question is
    # whether the handful that straddle the grids the pipeline already
    # snaps to are where the stages first diverge.
    assert "straddle @0.001 m  2.000000000,1.000000000" in text, text


def test_the_decade_histogram_buckets_by_magnitude():
    rows_a, rows_b = [], []
    for k, delta in enumerate((0.0, 1e-9, 5e-7, 3e-5)):
        rows_a.append((float(k), 0.0, 100.0, 0.0))
        rows_b.append((float(k), 0.0, 100.0 + delta, 0.0))
    lines = xplat.compare_projection({"mac": _dump(rows_a),
                                      "linux": _dump(rows_b, "linux")})
    text = "\n".join(lines)
    assert "0:1" in text and "1e-9:1" in text and "1e-7:1" in text \
        and "1e-5:1" in text, text


def test_the_bands_report_the_spread_against_distance_from_the_origin():
    """A last-ulp effect grows with the coordinate's magnitude; the bands
    are how a CYXY measurement is scaled to a hub, so they must key on the
    RADIUS and carry the per-band maximum."""
    rows_a, rows_b = [], []
    for k, r in enumerate((100.0, 700.0, 6000.0)):
        rows_a.append((float(k), 0.0, r, 0.0))
        rows_b.append((float(k), 0.0, r + r * 1e-9, 0.0))
    lines = xplat.compare_projection({"mac": _dump(rows_a),
                                      "linux": _dump(rows_b, "linux")})
    bands = [ln for ln in lines if ln.strip().startswith("r ")]
    assert len(bands) == 3, bands
    assert "1.000e-07" in bands[0] and "7.000e-07" in bands[1] \
        and "6.000e-06" in bands[2], bands


def test_the_solved_z_is_straddle_counted_on_the_same_grids():
    """The VERTICAL axis of the owner's question.  The z table joins on
    the vertex's xy, which is exact only in the quantised arm — so the
    comparer must report how many rows actually joined."""
    a = _dump([], solved=[(10.0, 20.0, 615.123), (11.0, 21.0, 7.0)])
    b = _dump([], name="linux",
              solved=[(10.0, 20.0, 615.1235), (11.0, 21.0, 7.0)])
    lines = xplat.compare_projection({"mac": a, "linux": b})
    text = "\n".join(lines)
    assert "SOLVED z (n=2 joined of [2, 2])" in text, text
    assert "straddles z  0.0001 m:1 0.001 m:1 0.01 m:0 0.5 m:0 of 2" \
        in text, text


def test_the_grids_include_the_two_the_pipeline_ALREADY_SNAPS_TO():
    """Identity census, main ``2fb0799f``: the planar arrangement is noded
    at ``emit.identity.min_distinct_spacing_m`` = 0.5 m
    (``planar/overlay.py:360-362, 441, 476``) and classify slices its
    pavement at ``[cells] snap_grid_m`` = 0.01 m
    (``classify/rules.toml:8``).  Those two are where a nanometre PROJ
    difference can already become a DECISION, so the straddle table must
    price them beside the owner's candidate quanta — and it must read them
    off the RAW projection, not a quantised arm."""
    assert 0.5 in xplat.GRIDS and 1e-2 in xplat.GRIDS
    assert 1e-4 in xplat.GRIDS and 1e-3 in xplat.GRIDS
    law = open(os.path.join(_ROOT, "Ortho4XP", "src", "auto_patch_v2",
                            "law", "emit.toml"), encoding="utf-8").read()
    assert "min_distinct_spacing_m  = 0.5" in law, (
        "the 0.5 m grid is the planar arrangement's, taken from law — if "
        "this moved, the straddle table prices the wrong lattice")
    rules = open(os.path.join(_ROOT, "Ortho4XP", "src", "auto_patch_v2",
                              "classify", "rules.toml"), encoding="utf-8").read()
    assert "snap_grid_m" in rules and "0.01" in rules


def test_the_expectation_scales_CYXY_to_a_hub():
    """The spec has to see what each quantum buys at hub size; CYXY is the
    only airport CI can build, so the count is projected by N."""
    rows_a, rows_b = [], []
    for k in range(100):
        rows_a.append((float(k), 0.0, 1000.0, 0.0))
        rows_b.append((float(k), 0.0, 1000.0 + 1e-5, 0.0))
    lines = xplat.compare_projection({"mac": _dump(rows_a),
                                      "linux": _dump(rows_b, "linux")})
    text = "\n".join(lines)
    assert "what each quantum buys" in text, text
    # s = 5e-6 (mean over the two axes: 1e-5 on x, 0 on y) -> p = 2s/q
    assert "q=0.001    p=1.000e-02" in text, text
    assert "N*50=5000" in text, text
    assert "[measured" in text, text


def _cons(rows, name="mac"):
    return {"icao": "CYXY", "env": {"machine": name, "platform": name},
            "quantise_m": 1e-3, "recorded": [], "counts": {},
            "constraint_rows": sorted(
                "%s\t%s" % (k, " ".join(float(v).hex() for v in vals))
                for k, vals in rows)}


def test_a_duplicate_constraint_KEY_is_grouped_not_overwritten():
    """THE BUG THE CONTROL CAUGHT.  Two faces put the same generator's row
    on the same vertex pair with different caps, so a key is NOT unique.
    Indexing by key and keeping the last pairs arbitrary members of a
    duplicate group: two runs of ONE mac came out 10.8 m apart (measured
    2026-09-17) before the groups were compared as sorted sets."""
    rows = [("diff|pavement_ceiling|r|1,2|3,4", (0.015, 40.0)),
            ("diff|pavement_ceiling|r|1,2|3,4", (0.015, 51.0)),
            ("diff|taxi|r|9,9|8,8", (0.015, 7.0))]
    lines = xplat.compare_projection({"mac": _cons(rows),
                                      "linux": _cons(rows, "linux")})
    text = "\n".join(lines)
    assert "CONSTRAINT ROW VALUES ([3, 3] rows, 0 unmatched keys)" in text, text
    assert "pavement_ceiling             n 2       differ 0       " \
        "max|d| 0.000e+00" in text, text


def test_a_real_constraint_value_difference_is_named_by_generator():
    a = [("diff|taxi|plane_gradient|1,2|3,4", (0.015, 7.0)),
         ("diff|no_step|rate|5,6|7,8", (0.02, 3.0))]
    b = [("diff|taxi|plane_gradient|1,2|3,4", (0.015, 7.0)),
         ("diff|no_step|rate|5,6|7,8", (0.02, 3.0004))]
    lines = xplat.compare_projection({"mac": _cons(a),
                                      "linux": _cons(b, "linux")})
    text = "\n".join(lines)
    assert "taxi                         n 1       differ 0" in text, text
    assert "no_step                      n 1       differ 1       " \
        "max|d| 4.000e-04" in text, text
    assert "@ no_step/rate" in text, text


def test_a_row_present_on_one_side_only_is_UNMATCHED_not_silently_dropped():
    a = [("diff|taxi|r|1,2|3,4", (0.015, 7.0)),
         ("diff|taxi|r|9,9|8,8", (0.015, 7.0))]
    b = [("diff|taxi|r|1,2|3,4", (0.015, 7.0))]
    lines = xplat.compare_projection({"mac": _cons(a),
                                      "linux": _cons(b, "linux")})
    assert any("1 unmatched keys" in ln for ln in lines), lines


def test_the_constraint_table_is_written_ONLY_in_the_quantised_arm():
    """Unquantised, the geometry key differs in the last ulp on two
    platforms and nothing would join — a multi-megabyte file that answers
    nothing.  The gate is the quantum, read off the module."""
    source = open(os.path.join(_ROOT, "Ortho4XP", "src", "auto_patch_v2",
                               "pipeline", "xplat.py"),
                  encoding="utf-8").read()
    assert "if constraints is not None and final_pm is not None and _PROJ_Q:" \
        in source
    xplat.arm_projection(0.0)
    try:
        assert "constraint_rows" not in xplat.projection_payload(
            "CYXY", constraints=object(), final_pm=object())
    finally:
        xplat.disarm_projection()


def test_a_mixed_quantum_comparison_is_called_out():
    lines = xplat.compare_projection(
        {"mac": _dump([], quantise=0.0),
         "linux": _dump([], name="linux", quantise=1e-3)})
    assert any("WARNING" in ln and "DIFFERENT quanta" in ln
               for ln in lines), lines


# --------------------------------------------------------- the plumbing

def test_the_hook_returns_the_FRAMES_OWN_function_when_not_armed():
    """Byte-neutrality by construction, not by a no-op wrapper: 17d's
    finding is a last-ulp effect, and an extra float round-trip through a
    wrapper is exactly the class of change that could move one."""
    import importlib
    from auto_patch_v2.model.frame import Frame
    # by module path: ``auto_patch_v2.airport.load`` the NAME is the
    # package's re-exported ``load`` FUNCTION, not this module.
    _load = importlib.import_module("auto_patch_v2.airport.load")

    frame = Frame("CYXY", (60.7095, -135.0678), 11)
    xplat.disarm_projection()
    assert xplat.projection_armed() is False
    base = frame.transformers()[0]
    got = _load._vector_to_xy(frame)
    assert got.__qualname__ == base.__qualname__ == "Frame.transformers.<locals>.to_xy"
    assert got(-135.0, 60.7) == base(-135.0, 60.7)

    xplat.arm_projection()
    try:
        wrapped = _load._vector_to_xy(frame)
        assert wrapped is not base
        # ARMED, the VALUES are still the frame's own — recording is a
        # read.  (The quantised arm below is the one that alters them, and
        # it is never reachable from the shipped path.)
        assert wrapped(-135.0, 60.7) == base(-135.0, 60.7)
        payload = xplat.projection_payload("CYXY", frame=frame)
        assert payload["counts"]["recorded"] == 1
        assert payload["quantise_m"] == 0.0
        lon_hex, lat_hex, x_hex, y_hex = payload["recorded"][0]
        assert float.fromhex(lon_hex) == -135.0
        assert float.fromhex(lat_hex) == 60.7
        assert (float.fromhex(x_hex), float.fromhex(y_hex)) \
            == base(-135.0, 60.7)
    finally:
        xplat.disarm_projection()


def test_the_quantised_arm_snaps_and_says_so():
    import importlib
    from auto_patch_v2.model.frame import Frame
    _load = importlib.import_module("auto_patch_v2.airport.load")

    frame = Frame("CYXY", (60.7095, -135.0678), 11)
    xplat.arm_projection(1e-3)
    try:
        wrapped = _load._vector_to_xy(frame)
        x, y = wrapped(-135.0, 60.7)
        assert abs(x * 1000 - round(x * 1000)) < 1e-6, x
        assert abs(y * 1000 - round(y * 1000)) < 1e-6, y
        assert xplat.projection_payload("CYXY")["quantise_m"] == 1e-3
    finally:
        xplat.disarm_projection()


def test_the_probe_lattice_reaches_hub_scale_and_is_exactly_representable():
    """The lattice is how CYXY's spread is scaled to a hub, so its inputs
    must be bit-identical on every platform (exact binary offsets) and it
    must reach past a large hub's half-extent."""
    from auto_patch_v2.model.frame import Frame

    for d in xplat._LATTICE_DEG:
        assert float(d).hex() == float(d).hex()
        assert d == 0.0 or abs(d) * 2 ** 20 == int(abs(d) * 2 ** 20), d
    assert max(xplat._LATTICE_DEG) * 111320.0 > 13000.0, "must reach ~14 km"
    frame = Frame("CYXY", (60.7095, -135.0678), 11)
    probe = xplat.probe_projection(frame)
    assert len(probe["forward"]) == len(xplat._LATTICE_DEG) ** 2
    assert len(probe["inverse"]) == len(xplat._LATTICE_M) ** 2
    # the origin projects to (0, 0)
    origin = [r for r in probe["forward"]
              if float.fromhex(r[0]) == -135.0678
              and float.fromhex(r[1]) == 60.7095]
    assert origin and abs(float.fromhex(origin[0][2])) < 1e-6


def test_the_quantum_is_a_schema_flag_and_is_off_by_default():
    from auto_patch_v2.pipeline.build import Config
    assert Config().xplat_quantise_m == 0.0
    wrapper = open(os.path.join(_ROOT, "Ortho4XP", "src", "auto_patch",
                                "engine_v2.py"), encoding="utf-8").read()
    assert "O4_V2_XPLAT_QUANTISE_M" in wrapper and \
        "xplat_quantise_m=" in wrapper
    source = open(os.path.join(_ROOT, "Ortho4XP", "src", "auto_patch_v2",
                               "pipeline", "build.py"),
                  encoding="utf-8").read()
    assert "_xplat.arm_projection(cfg.xplat_quantise_m)" in source
    assert 'f"{icao}.xproj.json"' in source


def test_the_interventional_arm_is_never_a_release_gate():
    """A measurement arm that could turn a release red would be a defect:
    the second solve's status is printed and discarded."""
    script = open(os.path.join(_ROOT, "scripts", "check_frozen_tile.py"),
                  encoding="utf-8").read()
    assert "PASS 2b (instrument, NOT a gate)" in script
    assert "second = run_airport(" in script
    assert "status |= run_airport(\n" in script or \
        "status |= run_airport(" in script
    # the gating call is the FIRST one; the arm's result never joins it
    assert "status |= second" not in script
    assert "%s.xproj.json" in script, "the dump must be copied out"


def test_compare_projection_runs_without_any_third_party_package(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    rows = [(0.1 * k, 0.2 * k, 1000.0 + k, 2000.0 + k) for k in range(50)]
    a.write_text(json.dumps(_dump(rows)))
    shifted = [(lon, lat, x + 4e-5, y) for lon, lat, x, y in rows]
    b.write_text(json.dumps(_dump(shifted, "linux")))
    script = os.path.join(_ROOT, "scripts", "check_frozen_tile.py")
    env = dict(os.environ)
    env["PYTHONNOUSERSITE"] = "1"
    done = subprocess.run(
        [sys.executable, "-S", script, "--compare-projection",
         "mac=%s" % a, "linux=%s" % b],
        capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
    assert "recorded (n=50 joined)" in done.stdout, done.stdout
    assert "straddles COORD" in done.stdout, done.stdout
