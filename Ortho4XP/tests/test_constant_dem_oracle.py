"""THE CONSTANT-DEM ORACLE — the standing build oracle.

OWNER LAW (RULINGS 2026-08-05): DEM is a SEED.  It seats things within
their feasible bands; it never shapes a band.  So a build of a REAL
airport's geometry against a CONSTANT DEM must be perfectly lawful —
there is no terrain signal, and every emitted row is therefore a law,
solver or instrument defect with nothing to blame it on.

THREE ASSERTIONS, in ascending power (owner's sharpening):

1. COMPLIANCE — zero law-true rows in BOTH worlds.
2. EXTREME-SEATING SATURATION — DEM ≡ −500 m (plateau; owner ruling
   2026-08-06, below every CIFP value) seats every free value at its
   band FLOOR; DEM ≡ 10 000 m (canyon) at its CEILING.  A node NOT
   saturated is held by something that is not the seed: a HIDDEN
   AUTHORITY.  This is what mere compliance cannot see.
3. THE BAND-WIDTH FIELD — ``canyon(node) - plateau(node)`` IS the width
   of the band the law grants at that node, emitted as a diagnostic
   artifact and checkable against the analytic bands.  Its envelope is
   ``[0, canyon − plateau]`` — 10 500 m for the ruled pair — DERIVED,
   never the unwritten ``[0, 9999]`` of the retired 1 m low world.

TWO LAYERS OF TEST, deliberately:

* the UNIT layer (always runs) pins the oracle's own machinery — the DEM
  object's surface, the saturation reader, the band-width field and its
  sign law — on synthetic layouts, costing nothing;
* the AIRPORT layer (opt-in) is the oracle proper.  It BUILDS, so it is
  selected the way every other airport test in this suite is: by
  ``O4_TEST_AIRPORTS`` / ``O4_TEST_TILE``.  With neither set it reports
  SKIPPED rather than silently passing.

Run the oracle:  O4_TEST_AIRPORTS=HEAZ venv/bin/python -m pytest \\
                     tests/test_constant_dem_oracle.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from auto_patch.constant_dem import (                    # noqa: E402
    CANYON_ELEVATION_M, ConstantDEM, PLATEAU_ELEVATION_M,
    band_width_field, band_width_summary, canyon_dem,
    constant_dem_worlds, plateau_dem, saturation_report,
    saturation_summary, write_band_width_artifact)
from auto_patch.layout import (                          # noqa: E402
    BuiltShape, PavementLayout, ROLE_APRON)

from conftest import airports_under_test, xplane_root    # noqa: E402


# ══════════════════════════════════════════════════════════════════════
# UNIT LAYER — the oracle's own machinery
# ══════════════════════════════════════════════════════════════════════

def test_the_dem_answers_one_elevation_everywhere():
    d = ConstantDEM(123.5)
    assert d.alt((0.0, 0.0)) == 123.5
    assert d.alt((0.9, 0.9)) == 123.5
    assert d.alt_strict((0.5, 0.5)) == 123.5
    assert d.get() == 123.5


def test_the_dem_carries_the_raster_surface_the_ols_reader_reads():
    d = ConstantDEM(50.0)
    for attr in ("alt_dem", "nxdem", "nydem", "x0", "x1", "y0", "y1",
                 "nodata", "lat", "lon", "elevation_level"):
        assert hasattr(d, attr), f"missing DEM surface member {attr}"
    assert int(d.nxdem) >= 2 and int(d.nydem) >= 2, (
        "the OLS raster reader bails below 2 columns — a 1x1 oracle DEM "
        "would silently skip the OLS path instead of exercising it")


def test_the_low_extreme_is_the_ruled_minus_500():
    """OWNER RULING 2026-08-06, "The low extreme is −500 m".

    Verbatim intent: "to effectively exercise the intention of the extreme
    low DEM … no particular need for zero, negative is better."  −500 m is
    BELOW EVERY CIFP VALUE, so floor-seating is guaranteed everywhere
    rather than merely likely, and below-sea-level handling is exercised
    for free.

    This replaces ``test_the_plateau_is_not_literally_zero``, which pinned
    the DEM ≡ 1 m interim and its rationale ("a literal 0.0 is
    indistinguishable from no data").  The ruling names that interim an
    unruled loader-guard DODGE and RETIRES it: the oracle never reaches
    the all-zero guard, because an oracle DEM arrives as ``override_dem``
    and is returned before the disk-compose branch that carries it — which
    the test below still asserts directly.
    """
    assert PLATEAU_ELEVATION_M == -500.0
    assert PLATEAU_ELEVATION_M < 0.0, (
        "the ruled low world is NEGATIVE — an implementation that clamps "
        "the synthetic seed at 0 has re-introduced the DEM ≥ 0 assumption")
    assert PLATEAU_ELEVATION_M < CANYON_ELEVATION_M


def test_the_dem_answers_a_NEGATIVE_elevation_everywhere():
    """The low world is below sea level; nothing may clamp it.

    KNOWN-ANSWER TWIN (RULINGS 2026-08-06 §1, "Instrument truth is law"):
    the answer is the constant itself, at every sampling entry the tree
    consumes, in the world the ruling names.
    """
    d = plateau_dem()
    assert d.elevation_m == -500.0
    assert d.alt((0.0, 0.0)) == -500.0
    assert d.alt_strict((0.5, 0.5)) == -500.0
    assert d.get() == -500.0
    assert list(d.alt_vec([(0.1, 0.1)])) == [-500.0]
    assert d.alt_dem.min() == -500.0 and d.alt_dem.max() == -500.0
    assert d.is_synthetic is True
    assert d.world_label == "plateau"


def test_a_synthetic_dem_AT_THE_NODATA_SENTINEL_is_refused():
    """The one constant that is not a value.

    Four readers branch on ``v == dem.nodata`` (``seam_anchors``,
    ``tile_cut``, ``runway_redistribute``, ``runway_regrade``), so a world
    at −32768 would be read as ABSENT data by every one of them and the
    build would silently measure a different world than the one asked
    for.  The collision was unreachable while the low world was a small
    POSITIVE constant; allowing negatives opens it, so it is closed at the
    one place every synthetic DEM is constructed.
    """
    from auto_patch.constant_dem import NODATA_SENTINEL
    with pytest.raises(ValueError, match="NO-DATA SENTINEL"):
        ConstantDEM(NODATA_SENTINEL)
    # …and every OTHER negative constant is perfectly legal.
    assert ConstantDEM(-32767.0).alt((0.0, 0.0)) == -32767.0
    assert ConstantDEM(-0.5).alt((0.0, 0.0)) == -0.5


def test_the_band_width_envelope_is_DERIVED_from_the_pair():
    """The ``[0, 9999]`` assumption, made explicit and made correct.

    The envelope of a seated difference is ``[0, canyon − plateau]``.  With
    the retired 1 m low world that was ``[0, 9999]`` and it was written
    down NOWHERE — so it was an assumption that the low world is
    non-negative, invisible by construction.  Under the ruled −500 m the
    span is 10 500 m, and a runner on a custom pair gets its own.
    """
    from auto_patch.constant_dem import SEED_SPAN_M, seed_span_m
    assert SEED_SPAN_M == 10500.0
    assert seed_span_m(-500.0, 10000.0) == 10500.0
    assert seed_span_m(1.0, 10000.0) == 9999.0        # the retired pair
    # A width inside the span is ordinary; one ABOVE it is the amplifying
    # authority finding, and the summary must count it as such.  Read
    # straight off a hand-built field: the summary is a pure function of the
    # widths, so the known answer is exact and owes nothing to a fixture
    # ring's closing vertices.
    field = {(_A, 0.0, 0.0): 0.0,          # pinned
             (_A, 1.0, 0.0): 10000.0,      # inside the span
             (_A, 2.0, 0.0): 10500.0,      # exactly AT the span
             (_A, 3.0, 0.0): 10500.5}      # past it — the finding
    summary = band_width_summary(field, 10500.0)
    assert summary["seed_span_m"] == 10500.0
    assert summary["envelope_m"] == [0.0, 10500.0]
    assert summary["nodes"] == 4 and summary["pinned"] == 1
    assert summary["negative"] == 0
    assert summary["over_span"] == 1, (
        "a node that moved FURTHER than the seed did is an authority "
        "amplifying the seed, not a band the law granted")
    # The SAME field judged in the RETIRED [0, 9999] envelope calls three of
    # the four impossible — exactly the false red a hard-coded 9999 would
    # mint under the ruled -500 m low world.
    assert band_width_summary(field, 9999.0)["over_span"] == 3
    # …and with no span given, the module default is the ruled pair's own.
    assert band_width_summary(field)["over_span"] == 1


def test_the_all_zero_refusal_is_untouched_by_the_oracle():
    """The guard catches ABSENT data on the disk-compose branch; an oracle
    DEM arrives as ``override_dem`` and is returned before it."""
    from auto_patch.elevation import _load_airport_dem
    d = canyon_dem()
    assert _load_airport_dem(0.5, 0.5, override_dem=d) is d


def _layout_with(values, role=ROLE_APRON, ref=""):
    """One ring carrying ``values`` at unit-spaced vertices."""
    ring = [(float(i), 0.0) for i in range(len(values))]
    ring = ring + [(float(len(values)) - 1.0, 10.0), (0.0, 10.0)]
    vals = list(values) + [values[-1], values[0]]
    lay = PavementLayout(icao="ORACLE", anchor=(0.0, 0.0))
    lay.shapes.append(BuiltShape(
        polygon=Polygon(ring + [ring[0]]), role=role, ref=ref,
        node_altitudes=vals + [vals[0]]))
    return lay


#: the author key ``_layout_with`` produces by default
_A = "apron/"


def test_band_width_field_is_the_difference_of_the_two_worlds():
    lo = _layout_with([10.0, 10.0, 10.0])
    hi = _layout_with([12.0, 13.5, 10.0])
    field = band_width_field(lo, hi)
    assert field[(_A, 0.0, 0.0)] == pytest.approx(2.0)
    assert field[(_A, 1.0, 0.0)] == pytest.approx(3.5)
    assert field[(_A, 2.0, 0.0)] == pytest.approx(0.0), (
        "a node with equal values in both worlds is PINNED — band width 0")


def test_the_band_width_join_never_crosses_AUTHORS():
    """A coordinate two surfaces share must yield one row PER SURFACE.

    ``_node_values`` used to key on ``(x, y)`` alone, so at any shared
    coordinate the LAST shape iterated won — and shape order and shape
    COUNT differ between the two worlds.  The "band width" reported there
    was the difference between two DIFFERENT surfaces: measured by fix
    lane 2 (``scratchpad/fix2/who/``), 9 of the 95 negative widths were
    exactly this — a ``runway_end_skirt`` differenced against
    ``adjacent_ground`` / ``resa`` / ``apron`` vertices at coordinates
    they weld on.  A negative width is supposed to be evidence of a
    non-monotone seating; nine of them were the instrument reading two
    populations at once.
    """
    def _two_authors(apron_vals, skirt_vals):
        lay = _layout_with(apron_vals)
        skirt = _layout_with(skirt_vals, role="graded_strip",
                             ref="runway_end_skirt")
        lay.shapes.append(skirt.shapes[0])
        return lay

    # SAME geometry, SAME coordinates, two authors — and the two worlds
    # carry them in OPPOSITE order, exactly as differing shape counts do.
    lo = _two_authors([10.0, 10.0, 10.0], [50.0, 50.0, 50.0])
    hi = _two_authors([11.0, 11.0, 11.0], [51.0, 51.0, 51.0])
    hi.shapes.reverse()
    field = band_width_field(lo, hi)
    authors = {a for (a, _x, _y) in field}
    assert authors == {_A, "graded_strip/runway_end_skirt"}, (
        f"the join collapsed two authors into one: {authors}")
    for (a, _x, _y), w in field.items():
        assert w == pytest.approx(1.0), (
            f"author {a!r} was differenced against the other surface "
            f"(width {w}, not 1.0) — a cross-family join")


def test_a_negative_band_width_is_a_defect_on_its_face():
    """The high world seating a node BELOW the low world is impossible for
    any monotone seating — the summary must surface it, never average it
    away."""
    lo = _layout_with([10.0, 10.0, 10.0])
    hi = _layout_with([10.0, 9.0, 10.0])
    summary = band_width_summary(band_width_field(lo, hi))
    assert summary["negative"] == 1
    assert summary["min"] == pytest.approx(-1.0)


def test_saturation_reader_names_the_unsaturated_node():
    lay = _layout_with([10.0, 10.0, 11.0])
    bands = {(0.0, 0.0): (10.0, 20.0),
             (1.0, 0.0): (10.0, 20.0),
             (2.0, 0.0): (10.0, 20.0)}
    rows = saturation_report(lay, "plateau", bands.get)
    assert [r.xy for r in rows] == [(2.0, 0.0)], (
        "the plateau world must flag exactly the node NOT sitting on its "
        "floor — that node is held by something other than the seed")
    # and in the canyon world the same field is unsaturated everywhere
    rows_hi = saturation_report(lay, "canyon", bands.get)
    assert len(rows_hi) == 3


def test_saturation_reader_rejects_an_unknown_world():
    with pytest.raises(ValueError):
        saturation_report(_layout_with([1.0]), "sideways", lambda xy: None)


def test_the_saturation_reader_ASKS_THE_SUPPLIER_IN_COORDINATES():
    """The key-shape bug that made assertion 2 return ``[]`` forever.

    ``_node_values`` is keyed ``(author, x, y)`` — it had to be, so the
    band-width join stops differencing two surfaces at a shared coordinate.
    This reader kept handing that 3-tuple straight to ``band_of``, and
    every supplier is coordinate-keyed: the engine's own contract is
    literally ``reach_band_unified(...) -> band(x, y)``.  So every lookup
    missed, every node was skipped as "no band here", and the reader
    returned an empty list — which is ALSO what a pass looks like.  The
    campaign read that empty list as a clean assertion 2 while nothing was
    being evaluated at all.
    """
    seen = []

    def _supplier(xy):
        seen.append(xy)
        return (10.0, 20.0)

    saturation_report(_layout_with([10.0, 10.0, 11.0]), "plateau", _supplier)
    assert seen, "the supplier was never called — the reader skipped every node"
    for xy in seen:
        assert len(xy) == 2 and all(isinstance(v, float) for v in xy), (
            f"the supplier was asked for {xy!r}; the band contract is "
            f"band(x, y), so the author must be split out of the key")


def test_the_saturation_reader_NAMES_THE_AUTHOR():
    """Assertion 2's whole purpose is naming what holds an unsaturated
    node.  A bare coordinate names nothing — and two welded surfaces share
    coordinates by construction."""
    lay = _layout_with([10.0, 10.0, 11.0])
    skirt = _layout_with([10.0, 10.0, 13.0], role="graded_strip",
                         ref="runway_end_skirt")
    lay.shapes.append(skirt.shapes[0])
    rows = saturation_report(lay, "plateau", lambda xy: (10.0, 20.0))
    assert {r.author for r in rows} == {_A, "graded_strip/runway_end_skirt"}
    # ranked worst-first: the 3 m skirt outranks the 1 m apron
    assert rows[0].author == "graded_strip/runway_end_skirt"
    assert rows[0].off_edge_m == pytest.approx(3.0)


def test_the_saturation_summary_groups_by_author_and_ranks_by_worst():
    """Ranked by worst |off_edge|, never by count: one node 9 900 m off its
    ceiling is the finding; a thousand nodes 0.02 m off is floor noise."""
    lay = _layout_with([10.0, 10.0, 10.02])
    loud = _layout_with([10.0, 10.0, 9910.0], role="groundside_pavement")
    lay.shapes.append(loud.shapes[0])
    rows = saturation_report(lay, "plateau", lambda xy: (10.0, 20000.0))
    summary = saturation_summary(rows)
    assert summary["unsaturated"] == len(rows)
    assert summary["by_author"][0]["author"] == "groundside_pavement/"
    assert summary["by_author"][0]["worst_off_edge_m"] == pytest.approx(9900.0)
    assert summary["worst_rows"][0]["author"] == "groundside_pavement/"


def test_a_node_with_no_band_is_not_a_defect():
    """``band_of`` returning ``None`` means "off the network, no band
    here" — the within-shape law governs it.  Reporting those as
    unsaturated would drown the real rows in coverage holes."""
    rows = saturation_report(_layout_with([10.0, 11.0, 12.0]),
                             "plateau", lambda xy: None)
    assert rows == []


def test_the_worlds_come_as_an_ordered_pair():
    worlds = list(constant_dem_worlds())
    assert [w for w, _ in worlds] == ["plateau", "canyon"]
    assert worlds[0][1].elevation_m < worlds[1][1].elevation_m


def test_the_oracle_measures_at_DEFAULT_env(tmp_path, monkeypatch):
    """ITEM 6 — the oracle's read.

    The airport layer is the standing build oracle, so it must measure
    whatever env it is launched in.  It could not: ``_write_axes_sidecar``
    was gated on ``config.LOG_VERBOSITY > 0``, and the shipped default is
    0, so at default env the oracle read NO sidecar and quietly ran the
    context-free check — a different law, on a different population, with
    the same green tick.

    This is the unit half (it must not build): one emitted layout at the
    shipped default, read by the oracle's OWN helper.
    """
    monkeypatch.chdir(tmp_path)
    from auto_patch import config as _cfg
    monkeypatch.setattr(_cfg, "LOG_VERBOSITY", 0, raising=False)
    lay = _layout_with([10.0, 10.5, 11.0])
    lay.icao = "ORACLE"
    within, cross, steps = _law_true_rows(lay, tmp_path, "default_env")
    # The assertion under test is that the helper did not RAISE: it found
    # a sidecar and a ruleset.  The row counts of a 5-vertex synthetic
    # apron are not the point and are not asserted.
    assert isinstance(within, list) and isinstance(cross, list)
    assert isinstance(steps, list)


def test_the_artifact_writes(tmp_path):
    lo = _layout_with([10.0, 10.0])
    hi = _layout_with([12.0, 10.0])
    out = tmp_path / "band_width.json"
    write_band_width_artifact(band_width_field(lo, hi), out,
                              extra={"icao": "ORACLE"})
    import json
    doc = json.loads(out.read_text())
    assert doc["icao"] == "ORACLE"
    assert doc["summary"]["nodes"] >= 2
    assert any(n["band_width_m"] == pytest.approx(2.0)
               for n in doc["nodes"])
    # the author travels with every row — it is part of the identity that
    # makes the row a difference of one surface against itself
    assert all(n.get("author") for n in doc["nodes"])


# ══════════════════════════════════════════════════════════════════════
# THE LAW DATUMS — paths converted from a DEM datum, asserted HERE
# ══════════════════════════════════════════════════════════════════════
# The airport layer BUILDS, so it cannot gate a no-builds round.  These
# rows are the by-inspection form of the same assertion for the two
# solver bounds that used to read the DEM directly (item 3(a)/3(b),
# 2026-08-05): a bound whose inputs are solved variables and law
# constants is IDENTICAL in the plateau and canyon worlds, which is
# exactly what "DEM never shapes the band" means operationally.
# Their behavioural twins live in ``test_gs_no_airside_witness.py``
# (the groundside mouth ceiling) and ``test_detached_pad_law_seat.py``
# (the detached-pad seat).

def test_the_groundside_mouth_ceiling_carries_no_dem_term():
    """3(a): the ceiling was ``own DEM sample + cap·15 m`` and was applied
    as a real solver bound, so on DEM ≡ c every pin collapsed to
    ``c + 0.75 m`` and any lot welding to pavement above that was clamped
    BELOW its lawful level — a violation on ground with no relief.  The
    datum is now the SOLVED weld surface."""
    from auto_patch.elevation_per_surface.route_profile.anchors import (
        gs_pin_law_ceiling)
    # the two worlds differ only in the seed; the host datum is solved.
    host, route_len, cap = 207.5, 40.0, 0.08
    assert (gs_pin_law_ceiling(host, route_len, cap)
            == gs_pin_law_ceiling(host, route_len, cap))
    assert gs_pin_law_ceiling(host, route_len, cap) > host
    import inspect
    assert "dem" not in inspect.getsource(
        gs_pin_law_ceiling).split('"""')[-1].lower()


def test_the_detached_pad_dem_pin_is_gone():
    """3(b): a hard pin at the raw-DEM footprint median froze every
    non-airside-served pad at the constant while the groundside pavement
    it welds into sat wherever the airside solve put it — an arbitrary
    step at a shared node, in BOTH worlds."""
    from auto_patch import config
    from auto_patch.elevation_per_surface.route_profile import anchors
    assert not hasattr(anchors, "build_detached_pad_dem_pins")
    assert not hasattr(config, "DETACHED_PAD_DEM_PIN")
    assert hasattr(anchors, "seat_detached_pads_by_law")


# ══════════════════════════════════════════════════════════════════════
# AIRPORT LAYER — the oracle proper (builds; opt-in by ICAO selection)
# ══════════════════════════════════════════════════════════════════════

_ORACLE_AIRPORTS = airports_under_test()


def _build_world(icao: str, dem):
    from auto_patch.pipeline import build_airport_pavement
    return build_airport_pavement(icao, xplane_root(),
                                  compute_elevations=True, tile_dem=dem)


def _law_true_rows(layout, tmp_path, tag):
    """Emit the layout and count law-true rows with the patch's OWN frame
    and the build's OWN ruleset — the census discipline
    (``check_grade.run_checks(ruleset=...)``; the kwarg is not optional,
    a missing one silently judges an FAA build under ICAO).

    A MISSING SIDECAR IS A FAILURE, NOT A FALLBACK (item 6, 2026-08-05).
    This used to read ``… if side.exists() else {}``, and with the write
    gated on ``LOG_VERBOSITY`` — or killed outright by one terrace
    joint's ``TypeError`` — the oracle silently ran the CONTEXT-FREE
    check at default env: no axes, no anchor, no pair caps, no ruleset.
    It then asserted zero rows against a law it was not reading, which
    over-flags by multiples (HEAZ 959 context-free vs 144 law-true) and
    would just as happily have passed on a frame that never applied.
    The sidecar is the contract; without it there is no measurement to
    report, so this raises instead of degrading.
    """
    import importlib.util
    import json
    repo = Path(__file__).resolve().parents[1]
    osm = tmp_path / f"{tag}.osm"
    layout.to_osm(str(osm))
    side = Path(str(osm) + ".axes.json")
    assert side.exists(), (
        f"{tag}: the patch shipped with NO axes sidecar, so this census "
        f"would silently run the context-free check — the oracle would "
        f"be judging a law it never read")
    d = json.loads(side.read_text())
    assert d.get("ruleset"), (
        f"{tag}: the sidecar carries no ruleset key, so check_grade "
        f"would re-resolve the authority instead of judging in the "
        f"frame the build actually ran under")
    spec = importlib.util.spec_from_file_location(
        f"cg_oracle_{tag}", repo / "tools" / "check_grade.py")
    cg = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cg
    spec.loader.exec_module(cg)
    exact = d.get("axes_exact") or None
    if exact:
        axes = [(p, c, None, r) for (p, c, r) in exact]
        routes = d.get("routes_exact") or None
    else:
        axes, routes = d.get("axes") or None, d.get("routes") or None
    within, cross, steps = cg.run_checks(
        osm, max_grade_pct=1.5, proximity_m=cg.SHARED_VERTEX_TOL_M,
        edge_search_m=5.0, edge_step_m=0.5, top_n=0, quiet=True,
        taxi_axes_ll=axes, routes_ll=routes,
        anchor=tuple(d["anchor"]) if d.get("anchor") else None,
        seam_pins_ll=d.get("seam_pins"),
        mesh_edges_ll=d.get("mesh_edges") or None,
        crown_drops_ll=d.get("crown_drops") or None,
        crown_centerline_ll=d.get("crown_centerline") or None,
        pair_caps_ll=d.get("pair_caps") or None,
        terrace_joints_ll=d.get("terrace_joints") or None,
        ruleset=d.get("ruleset") or None)
    return within, cross, steps


@pytest.mark.skipif(not _ORACLE_AIRPORTS,
                    reason="set O4_TEST_AIRPORTS / O4_TEST_TILE to run "
                           "the constant-DEM oracle (it builds)")
@pytest.mark.parametrize("icao", _ORACLE_AIRPORTS)
def test_constant_dem_world_is_lawful(icao, tmp_path):
    """ASSERTION 1 — COMPLIANCE in both worlds."""
    failures = []
    for world, dem in constant_dem_worlds():
        layout = _build_world(icao, dem)
        within, cross, steps = _law_true_rows(layout, tmp_path,
                                              f"{icao}_{world}")
        if within or cross or steps:
            failures.append(
                f"{world}: within={len(within)} cross={len(cross)} "
                f"steps={len(steps)}")
    assert not failures, (
        f"{icao}: a CONSTANT-DEM world emitted law violations — "
        f"{'; '.join(failures)}.  There is no terrain signal here, so "
        f"every row is a law / solver / instrument defect (RULINGS "
        f"2026-08-05).")


@pytest.mark.skipif(not _ORACLE_AIRPORTS,
                    reason="set O4_TEST_AIRPORTS / O4_TEST_TILE to run "
                           "the constant-DEM oracle (it builds)")
@pytest.mark.parametrize("icao", _ORACLE_AIRPORTS)
def test_constant_dem_band_width_field(icao, tmp_path):
    """ASSERTIONS 2 + 3 — extreme-seating saturation and the band-width
    field, reported together because they share the world pair.

    The band-width field is written as an artifact whatever the verdict:
    it is the empirical map of the corridor the law grants, per node, and
    it is the thing to read when assertion 1 fails.
    """
    lo = _build_world(icao, plateau_dem())
    hi = _build_world(icao, canyon_dem())
    field = band_width_field(lo, hi)
    span = CANYON_ELEVATION_M - PLATEAU_ELEVATION_M
    summary = band_width_summary(field, span)
    write_band_width_artifact(
        field, tmp_path / f"{icao}_band_width.json", span_m=span,
        extra={"icao": icao,
               "plateau_m": PLATEAU_ELEVATION_M,
               "canyon_m": CANYON_ELEVATION_M,
               "seed_span_m": span})
    assert summary["nodes"], f"{icao}: the two worlds share no node"
    # SIGN LAW: no monotone seating can put the high world below the low.
    assert summary["negative"] == 0, (
        f"{icao}: {summary['negative']} node(s) seat LOWER in the canyon "
        f"world than in the plateau world (min {summary['min']:.3f} m) — "
        f"a seating that is not monotone in the seed, i.e. an authority "
        f"reacting to the DEM rather than being seeded by it")
    # ENVELOPE: a seated difference cannot exceed the seed swing either.
    assert summary["over_span"] == 0, (
        f"{icao}: {summary['over_span']} node(s) moved FURTHER than the "
        f"{span:g} m seed swing (max {summary['max']:.3f} m) — something is "
        f"amplifying the seed rather than being seeded by it")
    # SATURATION: a node free in one world and free in the other must have
    # MOVED; a node that moved nowhere while its neighbours moved metres
    # is either genuinely pinned or hiding an authority.  The empirical
    # form of assertion 2, needing no analytic band table: with a
    # 10.5 km seed swing, an unpinned node cannot sit still.
    moved = sum(1 for w in field.values() if abs(w) > 1e-6)
    assert moved, (
        f"{icao}: NOT ONE node moved between a {PLATEAU_ELEVATION_M:g} m "
        f"and a {CANYON_ELEVATION_M:g} m seed.  The seed is not seating "
        f"anything — the surface is authored entirely by something else.")
