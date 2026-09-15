"""THE HARNESS TWINS — the assertions that keep the standard test harness
from drifting back into per-lane copies.

Every test here exists because a hand-written copy of harness machinery
produced a wrong number in this repo.  They are cheap (no build, no
X-Plane, no network) and they run in the normal suite.

* §1 THE CENSUS IS ONE CODE PATH — the family register covers every family
  ``run_checks`` emits, the recorded families PARTITION the returned lists,
  every law keyword is produced by the single sidecar reader, and the CLI
  has no private copy of that reader.
* §2 THE SIDECAR CONTRACT — every key the emitter writes is classified as
  either law input or evidence.  A newly emitted key that no reader
  consumes fails here instead of being silently dropped by every census.
* §3 THE BUILD ENTRY REFUSES — the wrong-cwd, missing-venv/OSM_data and
  no-sidecar paths raise loudly rather than degrading.
* §4 THE LANE RITUAL — the worktree script mounts the WHOLE shared data
  repo (enumerated, never hard-coded), keeps only lane PRODUCTS local, and
  refuses teardown while a child process or a shared lock holds the tree.
* §5 THE SHARED DATA REPO (owner ruling e9daef5) — a private corpus is
  refused, an implicit download is refused and names its ``--refresh-data``
  scope, a shared-repo write outside an authorised scope is reported as a
  ruling violation, and the refresh lock refuses-and-reports on contention
  instead of blocking or racing.
* §6b THE LOCK AND LIBRARY-INDEX ALLOWANCES, AND THE SWALLOWED
  DEGRADATION — the engine's own cross-process ``.lock`` file and its
  derived ``Airport_mod_cache`` library-index sidecar pass the write guard
  (coordination state and derived cache; neither is corpus data) while a
  real data write beside either still refuses; and a degradation the
  engine CAUGHT — a blocked write, or a layout with no DEM provenance —
  refuses instead of exiting 0 on a silently smaller layout.
* §6c ONE GUARD, TWO ENTRIES — the write law has exactly ONE definition
  (``harness/shared_repo_guard.py``); ``build_airport.py`` re-exports the
  guard module's own objects and ``run_tile_mesh_only.py`` arms them, in
  the order that makes the audit mean something.
* §6d THE GUARD FOLLOWS THE BUILD, NOT THE ENTRY — ``tools/classify_report.py``
  builds an airport in process, so it arms the SAME composition
  (``arm_shared_repo_protection``: redirects + refuse-mode guard) and
  refuses a swallowed refusal; its ``--from-json`` render path builds
  nothing and arms nothing.
"""
from __future__ import annotations

import importlib.util
import hashlib
import inspect
import math
import json
import os
import re
import shutil
import subprocess
import types
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "harness"

sys.path.insert(0, str(ROOT / "src"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cg():
    return _load("harness_twin_check_grade", ROOT / "tools" / "check_grade.py")


@pytest.fixture(scope="module")
def census_mod():
    return _load("harness_twin_census", HARNESS / "census.py")


@pytest.fixture(scope="module")
def build_mod():
    return _load("harness_twin_build", HARNESS / "build_airport.py")


@pytest.fixture(scope="module")
def guard_mod(build_mod):
    """THE shared-repo write law itself (§6c), the module ``build_mod``
    re-exports.

    A test that REDIRECTS the law's own globals — ``DATA_REPO``,
    ``LOCK_DIR``, ``REFRESH_LEDGER`` — must patch them HERE, in the module
    whose functions read them: ``build_airport`` holds re-exported
    references, and rebinding one of those changes nothing
    :class:`RefreshLock` or :func:`record_refresh` will look at.  Patching
    the wrong one does not fail loudly either — it silently runs the test
    against the REAL shared repo (both of these did, on the move: a lock
    file and a ledger record landed in ``/Users/noah/XPTerrainBuilderData``
    before the fixture existed).
    """
    import importlib
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    return importlib.import_module("shared_repo_guard")


@pytest.fixture(autouse=True)
def _hermetic_lane_cache_root(tmp_path, monkeypatch):
    """The DERIVED cache roots are LANE-PERSISTENT (perf P2, Lane A) —
    ``<lane>/tmp/engine_caches/`` by default, which is the CHECKOUT when a
    twin calls the redirect.  Persistence is the whole point of the
    feature and hermetic tests are the whole point of a twin, so every
    test in this file derives into ITS OWN ``tmp_path`` instead.  A twin
    that asserts the DEFAULT location deletes the variable itself
    (``monkeypatch.delenv``) and passes an explicit ``lane_root``."""
    monkeypatch.setenv("O4_LANE_CACHE_ROOT", str(tmp_path / "lane_caches"))


#: A real emitted patch that ships in the tree — enough to exercise every
#: family reader without building anything.
FIXTURE_PATCH = ROOT / "tests" / "fixtures" / "SPJC_target.osm"


# ══════════════════════════════════════════════════════════════════════
# §0 THE BLAST INDEX NAMES THE HARNESS SUITES A FIXTURE REACHES
# ══════════════════════════════════════════════════════════════════════


def test_blast_lists_the_grade_suite_for_runway_segments(tmp_path):
    """2026-08-20: a lane edited runway_segments.py and gap_fill.py, ran
    the blast-listed sweep (472 passed) and never ran this file's
    neighbours test_pavement_grade.py / test_single_graph_acceptance.py —
    they reach those modules through ``conftest.cached_airport_layout``,
    not an import.  The index must record that reach, in its own group,
    and the sweep selector must emit it."""
    blast = _load("harness_twin_blast", ROOT.parent / "tools" / "blast.py")
    shards = blast.build(str(tmp_path / "idx"))
    for src, test in (("auto_patch/pavement/runway_segments.py",
                       "test_pavement_grade.py"),
                      ("auto_patch/gap_fill.py",
                       "test_single_graph_acceptance.py")):
        rel = blast.SRC_PREFIX + src
        card = shards["modules"][rel]
        fx = card["tests_via_fixture"]
        assert blast.TESTS_PREFIX + test in fx, (src, test)
        assert "cached_airport_layout" in fx[blast.TESTS_PREFIX + test]
        assert any(l.startswith("TESTS VIA CONFTEST FIXTURE") and test in l
                   for l in blast.render(rel, shards))
        sel = blast.select_tests({rel: {"anything"}}, shards)
        assert blast.TESTS_PREFIX + test in sel["clauses"]["fixture"]
        assert blast.TESTS_PREFIX + test in sel["selected"]


# ══════════════════════════════════════════════════════════════════════
# §1 THE CENSUS IS ONE CODE PATH
# ══════════════════════════════════════════════════════════════════════

def test_the_family_register_names_every_family_run_checks_emits(cg):
    """The exact defect: a lane's private census enumerated 12 of the law
    families by hand and reported 9, so nine families of violations were
    invisible in an integration report.  Nothing enumerates families any
    more — ``run_checks`` fills ``family_out`` itself — and this asserts
    the register and the emitter agree in BOTH directions."""
    family_out: dict = {}
    cg.run_checks(FIXTURE_PATCH, top_n=0, quiet=True, family_out=family_out)
    recorded = {k for k in family_out if not k.startswith("_")}
    registered = {key for key, _title, _bucket in cg.LAW_FAMILIES}
    assert recorded == registered, (
        f"family register drift: emitted-but-unregistered "
        f"{sorted(recorded - registered)}, registered-but-never-emitted "
        f"{sorted(registered - recorded)}.  Add the new check to "
        f"check_grade.LAW_FAMILIES in its emission position.")


def test_the_register_is_ordered_by_bucket_and_has_no_duplicates(cg):
    keys = [k for k, _t, _b in cg.LAW_FAMILIES]
    assert len(keys) == len(set(keys)), "duplicate family key in the register"
    buckets = {b for _k, _t, b in cg.LAW_FAMILIES}
    assert buckets <= {"within", "cross", "steps"}, (
        f"unknown result bucket(s) {buckets - {'within', 'cross', 'steps'}}")


def test_the_recorded_families_partition_the_returned_lists(cg):
    """The census reads per-family rows; the suite reads the three returned
    lists.  If those two views ever disagree the harness and the acceptance
    gate are measuring different populations — the failure mode this repo
    calls 'two instruments, one assumed population'."""
    family_out: dict = {}
    within, cross, steps = cg.run_checks(
        FIXTURE_PATCH, top_n=0, quiet=True, family_out=family_out)
    for bucket, returned in (("within", within), ("cross", cross),
                             ("steps", steps)):
        rebuilt = [row
                   for key, _title, b in cg.LAW_FAMILIES if b == bucket
                   for row in family_out[key]]
        assert len(rebuilt) == len(returned), (
            f"{bucket}: families sum to {len(rebuilt)} rows but run_checks "
            f"returned {len(returned)} — a family is double-counted, "
            f"missing, or lands in the wrong bucket")
        assert all(a is b for a, b in zip(rebuilt, returned)), (
            f"{bucket}: family rows are not the returned rows in order — "
            f"the register's ORDER no longer matches the emission order")


def test_every_version_deferred_family_is_a_registered_family(cg):
    """DEFERRED ADJUDICATION (owner ruling RULINGS d48bc0a).

    A deferral names a family the acceptance verdict must not adjudicate.  A
    deferred key that is NOT a family key would silently defer nothing — the
    verdict would look adjudicated-clean while the rows kept counting — and a
    deferred key that was silently DROPPED instead of reported is the
    census-wrapper defect.  Both halves are pinned here.
    """
    registered = {key for key, _title, _bucket in cg.LAW_FAMILIES}
    assert set(cg.VERSION_DEFERRED_FAMILIES) <= registered, (
        f"version-deferred key(s) "
        f"{sorted(set(cg.VERSION_DEFERRED_FAMILIES) - registered)} name no "
        f"law family — the deferral would exclude nothing")
    assert cg.VERSION_DEFERRED_FAMILIES, (
        "the deferral register is empty; RULINGS d48bc0a defers the interior "
        "drainage-minimum family — an empty register silently re-adjudicates "
        "it")
    for why in cg.VERSION_DEFERRED_FAMILIES.values():
        assert cg.DEFERRED_ADJUDICATION_RULING in why, (
            "every deferral must carry its owner-ruling citation in the "
            "text the reports print")


def test_the_adjudication_split_is_exhaustive_and_reports_the_deferred(cg):
    """The split must PARTITION: adjudicated + deferred = every row.  A
    deferral that quietly removed rows from BOTH numbers would be the
    'quarantine' the owner outlawed wearing an accounting hat."""
    deferred_key = sorted(cg.VERSION_DEFERRED_FAMILIES)[0]
    other = next(k for k, _t, _b in cg.LAW_FAMILIES
                 if k not in cg.VERSION_DEFERRED_FAMILIES)

    class _W:
        tags = {"role": "apron"}

    class _Row:
        way_a = way_b = _W()
    rows = [(deferred_key, _Row()), (deferred_key, _Row()),
            (other, _Row()), (other, _Row()), (other, _Row())]
    adj = cg.adjudication(rows)
    assert adj["deferred_total"] == 2 and adj["adjudicated_total"] == 3
    assert adj["deferred_total"] + adj["adjudicated_total"] == len(rows)
    assert adj["deferred_families"][deferred_key]["n"] == 2
    assert adj["ruling"] == cg.DEFERRED_ADJUDICATION_RULING
    assert adj["pass"] is False
    # ...and a patch whose ONLY rows are deferred is a PASS with the rows
    # still visible — the whole point of the ruling.
    only_deferred = cg.adjudication([(deferred_key, _Row())])
    assert only_deferred["pass"] is True
    assert only_deferred["deferred_total"] == 1


# ── THE TUNNEL-TRENCH DECLARED-STEP LAW (spec docs/specs/
# tunnel-trench-law-and-basin-floor-spec.md §1.4) ────────────────────
# The defect these pin: the ``tunnel_trench`` role has no
# ``ROLE_GRADE_LIMITS`` entry, so the by-law node-split trench wall priced
# as a step at EVERY contact — 90.7 % of LEMD's 12,253 census rows and
# 95.7 % of OTHH's 5,871.  The fix is an exemption bounded by the
# facility's OWN declared floor→rim drop, NOT a blanket "skip the role",
# which would blind the census to a trench born 51 m too deep.

_TWIN_ANCHOR = (25.27, 51.61)   # OTHH-ish; any anchor works


def _trench_patch(tmp_path: Path, *, pavement_elev: float,
                  facility: dict, name: str = "TRENCH") -> Path:
    """A two-square patch: a DECLARED trench floor plate at 0.0 m beside a
    junction plate at ``pavement_elev``, sharing a contact edge, plus the
    ``basin_facilities`` sidecar record that declares the pit."""
    import math
    r = 6378137.0
    cos0 = math.cos(math.radians(_TWIN_ANCHOR[0]))

    def ll(x, y):
        return (_TWIN_ANCHOR[0] + math.degrees(y / r),
                _TWIN_ANCHOR[1] + math.degrees(x / (r * cos0)))

    nodes, ways, nid = [], [], [0]

    def square(x0, side, alt, tags):
        ns = []
        for (x, y) in ((x0, 0.0), (x0 + side, 0.0),
                       (x0 + side, side), (x0, side)):
            nid[0] -= 1
            lat, lon = ll(x, y)
            nodes.append((str(nid[0]), lat, lon, alt))
            ns.append(str(nid[0]))
        nid[0] -= 1
        ways.append((str(nid[0]), ns + [ns[0]], tags))

    # The pit floor plate, emitted AT the declared floor, and the pavement
    # it cut — 0.3 m away, inside the step law's contact tolerance and
    # clear of the stacked-node law (distinct coordinates).
    square(0.0, 20.0, facility["floor_m"],
           {"role": "tunnel_trench", "shapeID": "T1"})
    square(20.3, 20.0, pavement_elev, {"role": "junction", "shapeID": "J1"})

    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm version='0.6' generator='trench-twin'>"]
    for n, lat, lon, alt in nodes:
        out.append(f"  <node id='{n}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                   f"<tag k='alt_abs' v='{alt:.2f}' /></node>")
    for wid, nids, tags in ways:
        out.append(f"  <way id='{wid}'>")
        out += [f"    <nd ref='{n}' />" for n in nids]
        out += [f"    <tag k='{k}' v='{v}' />" for k, v in tags.items()]
        out.append("  </way>")
    out.append("</osm>")
    osm = tmp_path / f"{name}_auto.patch.osm"
    osm.write_text("\n".join(out) + "\n")
    Path(str(osm) + ".axes.json").write_text(json.dumps({
        "anchor": list(_TWIN_ANCHOR),
        "ruleset": "icao",
        "basin_facilities": [facility],
    }))
    return osm


def _facility(*, floor_m: float, drop_m: float, body_depth_m: float,
              solid_minimum_y_m: float) -> dict:
    return {
        "resources": ["twin/Pit_01.obj"],
        "anchor_longitude_latitude": [_TWIN_ANCHOR[1], _TWIN_ANCHOR[0]],
        "floor_m": floor_m,
        "rim_law_m": floor_m + drop_m,
        "body_depth_m": body_depth_m,
        "solid_minimum_y_m": solid_minimum_y_m,
    }


def _families(cg, osm) -> dict:
    fo: dict = {}
    cg.run_checks_law_true(osm, family_out=fo, quiet=True)
    return fo


def test_a_declared_trench_wall_of_its_own_drop_prices_no_row(cg, tmp_path):
    """§1.4 (a): a wall step of exactly the DECLARED drop D is the geometry
    the trench law cut — it prices zero rows."""
    fo = _families(cg, _trench_patch(
        tmp_path, pavement_elev=12.0,
        facility=_facility(floor_m=0.0, drop_m=12.0,
                           body_depth_m=12.0, solid_minimum_y_m=-12.0)))
    steps = fo["vertex_to_edge_step"] + fo["mid_edge_step"]
    assert steps == [], (
        f"a declared 12.0 m trench wall priced {len(steps)} step row(s) — "
        f"the declared-step exemption did not bind")
    assert fo["basin_floor_declaration"] == [], (
        "a facility whose floor matches its own body depth must declare "
        "nothing")


def test_a_trench_wall_past_its_declared_drop_prices_the_excess(cg,
                                                                tmp_path):
    """§1.4 (b): D + 1 m prices, and the EXCESS the report accumulates is
    the 1 m past the declaration — not the whole 13 m wall."""
    osm = _trench_patch(
        tmp_path, pavement_elev=13.0,
        facility=_facility(floor_m=0.0, drop_m=12.0,
                           body_depth_m=12.0, solid_minimum_y_m=-12.0))
    fo = _families(cg, osm)
    steps = fo["vertex_to_edge_step"] + fo["mid_edge_step"]
    assert steps, "a 13.0 m step against a declared 12.0 m drop must report"
    assert all(abs(s.step_m - 13.0) < 0.05 for s in steps), (
        "the row must carry the MEASURED step; the allowance is not "
        "subtracted from the measurement")
    # ...and the same patch with the declaration REMOVED prices every row
    # at the bare 0.5 m step law, which is what the exemption relaxes.
    bare: dict = {}
    cg.run_checks(osm, **dict(cg.LAW_TRUE_KNOBS),
                  **{k: v for k, v in
                     cg.law_context_from_sidecar(osm).items()
                     if k != "basin_facilities"},
                  quiet=True, top_n=0, family_out=bare)
    assert len(bare["vertex_to_edge_step"] + bare["mid_edge_step"]) >= \
        len(steps), (
        "removing the declaration must never REDUCE the rows — the "
        "exemption only relaxes")


def test_a_trench_born_below_its_own_body_still_reports(cg, tmp_path):
    """§1.4 (c) — THE LEMD CLASS.  A facility whose floor sits 50 m below
    its declared rim under a 7 m body is a DECLARATION defect: the
    exemption above would otherwise let a facility license its own
    absurdity, since the wall it declared is the wall it cut."""
    fo = _families(cg, _trench_patch(
        tmp_path, pavement_elev=51.5,
        facility=_facility(floor_m=0.0, drop_m=51.5,
                           body_depth_m=7.016, solid_minimum_y_m=-50.0)))
    rows = fo["basin_floor_declaration"]
    assert len(rows) == 1, (
        f"the LEMD-class facility reported {len(rows)} row(s) — a trench "
        f"born 51.5 m below its own rim under a 7.02 m body must never be "
        f"silent")
    assert abs(rows[0].de_m - 42.984) < 0.01, rows[0].de_m
    assert "Pit_01.obj" in cg._label(rows[0].way_a), (
        "the row must name the resource that claimed the floor")


# ── AMENDMENT 1 (2026-08-25): THE ALLOWANCE IS PER PART ─────────────
# The band is TERRAIN-TRUE — each part samples the DEM at its own
# centroid — so a facility declares ONE floor and MANY rims.  Pricing
# every wall contact against the flat ``rim_law_m`` charges the ground's
# own relief as excess: measured at LEMD_a4, an emitted rim of
# 592.64-595.24 against a 593.03 law value reported +930 lawful wall
# rows, worst 9.23 m.  OTHH never exposed it (flat DEM there: the
# emitted rim IS the law value).

def test_a_wall_on_SLOPING_ground_prices_no_row(cg, tmp_path):
    """Amendment 1 item 3, first half.  The pavement side stands 2.2 m
    ABOVE the facility's flat law rim — lawful, because that is where the
    ground is and the part published exactly that.  Under the flat drop
    it reported; under the per-part allowance it prices zero."""
    facility = _facility(floor_m=0.0, drop_m=12.0,
                         body_depth_m=12.0, solid_minimum_y_m=-12.0)
    facility["emitted_rim_parts_m"] = [11.4, 12.0, 14.2]
    fo = _families(cg, _trench_patch(
        tmp_path, pavement_elev=14.2, facility=facility))
    steps = fo["vertex_to_edge_step"] + fo["mid_edge_step"]
    assert steps == [], (
        f"a 14.2 m wall against a PUBLISHED 14.2 m rim part priced "
        f"{len(steps)} row(s) — the per-part allowance did not bind")


def test_a_part_past_its_own_published_rim_prices_the_excess(cg, tmp_path):
    """Amendment 1 item 3, second half, and item 1's second sentence:
    excess beyond the part's OWN drop still reports in full.  Here the
    contact emits 1 m deeper than the deepest rim this facility ever
    published, so the row is back — the allowance can never exceed what
    was declared for that part."""
    facility = _facility(floor_m=0.0, drop_m=12.0,
                         body_depth_m=12.0, solid_minimum_y_m=-12.0)
    facility["emitted_rim_parts_m"] = [11.4, 12.0, 14.2]
    fo = _families(cg, _trench_patch(
        tmp_path, pavement_elev=15.2, facility=facility))
    steps = fo["vertex_to_edge_step"] + fo["mid_edge_step"]
    assert steps, (
        "a 15.2 m contact against a deepest published part of 14.2 m "
        "must report — the per-part allowance is not a blanket exemption")
    assert all(abs(step.step_m - 15.2) < 0.05 for step in steps), (
        "the row carries the MEASURED step; the allowance is not "
        "subtracted from the measurement")
    excess = 15.2 - 14.2
    assert abs(excess - 1.0) < 1e-9


def test_the_per_part_allowance_never_widens_the_flat_one(cg, tmp_path):
    """A part BELOW the facility's law rim holds the facility to what it
    actually emitted there: the published part replaces the flat drop, it
    is not max'd with it."""
    facility = _facility(floor_m=0.0, drop_m=12.0,
                         body_depth_m=12.0, solid_minimum_y_m=-12.0)
    facility["emitted_rim_parts_m"] = [8.0]
    fo = _families(cg, _trench_patch(
        tmp_path, pavement_elev=10.0, facility=facility))
    steps = fo["vertex_to_edge_step"] + fo["mid_edge_step"]
    assert steps, (
        "a 10.0 m contact against a single published 8.0 m part must "
        "report, even though the facility's FLAT declared drop is 12.0 m")


def test_a_facility_that_published_no_parts_keeps_the_flat_drop(cg,
                                                                tmp_path):
    """The no-op half of Amendment 1: an artifact built before it — or a
    cut that seated no band — carries no per-part list and is judged
    exactly as before."""
    facility = _facility(floor_m=0.0, drop_m=12.0,
                         body_depth_m=12.0, solid_minimum_y_m=-12.0)
    assert "emitted_rim_parts_m" not in facility
    fo = _families(cg, _trench_patch(
        tmp_path, pavement_elev=12.0, facility=facility))
    assert fo["vertex_to_edge_step"] + fo["mid_edge_step"] == []
    facility_empty = dict(facility)
    facility_empty["emitted_rim_parts_m"] = []
    fo_empty = _families(cg, _trench_patch(
        tmp_path, pavement_elev=12.0, facility=facility_empty,
        name="TRENCH2"))
    assert fo_empty["vertex_to_edge_step"] + fo_empty["mid_edge_step"] == []


def test_the_emitter_publishes_the_parts_the_census_joins_on(cg):
    """ONE population, both readers (the census-wrapper lesson): the key
    the emitter writes is the key the census reads."""
    import inspect
    from auto_patch import object_terrain_assembly as assembly
    source = inspect.getsource(assembly.build_tunnel_layout_shapes)
    assert '"emitted_rim_parts_m"' in source
    assert "emitted_rim_parts_m" in inspect.getsource(
        cg._basin_facilities_declared)


def test_a_patch_with_no_basin_reads_exactly_as_before(cg):
    """The no-op half: the fixture patch declares no basin, so the law
    keyword changes nothing about what it measures."""
    a = cg.run_checks(FIXTURE_PATCH, top_n=0, quiet=True)
    b = cg.run_checks(FIXTURE_PATCH, top_n=0, quiet=True,
                      basin_facilities=None)
    assert [len(x) for x in a] == [len(x) for x in b]


def test_the_declared_plate_roles_are_the_engines_own(cg):
    """ONE role set, both sides: the census's declared-plate roles are
    ``config.DECLARED_TERRAIN_PLATE_ROLES`` itself (the literal in
    ``check_grade`` is only the no-engine CLI fallback), and every role in
    it is a role the engine EMITS."""
    from auto_patch.config import DECLARED_TERRAIN_PLATE_ROLES
    from auto_patch import layout
    assert set(cg._DECLARED_PLATE_ROLES) == set(DECLARED_TERRAIN_PLATE_ROLES)
    emitted = {v for k, v in vars(layout).items()
               if k.startswith("ROLE_") and isinstance(v, str)}
    assert set(DECLARED_TERRAIN_PLATE_ROLES) <= emitted, (
        f"declared-plate role(s) "
        f"{sorted(set(DECLARED_TERRAIN_PLATE_ROLES) - emitted)} are not "
        f"emitted by layout.py")


def test_the_near_miss_frontage_law_is_one_authority(cg):
    """Cycle-5 item 6: the census family and the solve's law edges must
    recognize ONE population.  The radius, the role set and the budget all
    live in ``auto_patch.config``; the solver module re-exports them.  The
    role tuple is spelled as strings there (config cannot import
    ``layout``), so a ROLE_* rename would silently un-scope the law — this
    is what makes that loud.  ``service_junction`` is deliberately absent:
    R7b clause 2 (RULINGS 2026-08-15, the sink ruling) removed roads from
    the soft-role set — a road never welds to a building."""
    from auto_patch.config import (BUILDING_FRONTAGE_NEAR_MISS_M,
                                   NEAR_MISS_FRONTAGE_SOFT_ROLES,
                                   near_miss_frontage_budget, APRON_MAX_GRADE)
    from auto_patch.layout import ROLE_APRON, ROLE_JUNCTION
    from auto_patch.elevation_per_surface.route_profile import anchors
    assert NEAR_MISS_FRONTAGE_SOFT_ROLES == (
        ROLE_APRON, ROLE_JUNCTION), (
        "the near-miss frontage role set no longer matches the ROLE_* "
        "constants — the solve and the census now scope the law differently")
    assert anchors.BUILDING_FRONTAGE_NEAR_MISS_M == \
        BUILDING_FRONTAGE_NEAR_MISS_M, (
        "the solver module carries its own near-miss radius again — that is "
        "the two-copies defect the migration to config.py closed")
    assert near_miss_frontage_budget(7.0) == APRON_MAX_GRADE * 7.0
    assert "frontage_near_miss" in {k for k, _t, _b in cg.LAW_FAMILIES}, (
        "the near-miss frontage law binds in the solve but no census family "
        "measures it — enforcing it could only read as within_shape noise")


def test_family_out_is_a_pure_no_op_when_absent(cg):
    """A census must never change what it measures."""
    a = cg.run_checks(FIXTURE_PATCH, top_n=0, quiet=True)
    b = cg.run_checks(FIXTURE_PATCH, top_n=0, quiet=True, family_out={})
    assert [len(x) for x in a] == [len(x) for x in b]


def test_every_law_keyword_is_produced_by_the_single_sidecar_reader(cg):
    """``law_context_from_sidecar`` must produce every law keyword
    ``run_checks`` accepts.  A keyword it does not produce is a keyword
    every reader will forget — that is exactly how ``terrace_joints_ll``
    (a whole law family's exemptions) went missing from a lane census."""
    numeric_knobs = {"osm_path", "max_grade_pct", "proximity_m",
                     "edge_search_m", "edge_step_m", "top_n", "quiet",
                     "family_out"}
    law_kwargs = set(inspect.signature(cg.run_checks).parameters) - \
        numeric_knobs
    produced = set(cg.SIDECAR_LAW_KEYS.values())
    assert law_kwargs == produced, (
        f"sidecar reader drift: run_checks accepts {sorted(law_kwargs - produced)} "
        f"that the sidecar reader never supplies; reader supplies "
        f"{sorted(produced - law_kwargs)} that run_checks does not accept.")


def _code_only(src: str) -> str:
    """Source with comments and string literals removed — prose that MENTIONS
    a key must not read as a second parser of it."""
    import io
    import tokenize
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        out.append(tok.string)
    return " ".join(out)


def test_the_cli_has_no_private_copy_of_the_sidecar_reader(cg):
    """The CLI used to parse the sidecar inline; every lane then copied that
    block and each copy lost a different key.  There is one reader now."""
    src = inspect.getsource(cg.main)
    assert "law_context_from_sidecar" in src, (
        "check_grade.main must read its law frame through "
        "law_context_from_sidecar")
    code = _code_only(src)
    for key in ("axes_exact", "terrace_joints", "crown_centerline",
                "seam_pins", "pair_caps"):
        assert key not in code, (
            f"check_grade.main handles the sidecar key {key!r} itself — "
            f"that is a second reader, which is the defect")


#: The private check functions every lane's census wrapper monkeypatched.
#: Naming one from outside ``check_grade`` is the wrapping approach itself.
PRIVATE_CHECKS = ("_check_within_shape", "_check_plane_gradient",
                  "_check_transverse_grade", "_check_lateral_contiguity",
                  "_check_stacked_nodes", "_check_cross_shape_proximity",
                  "_check_vertex_to_edge_step", "_check_edge_midpoint_step",
                  "_check_strip_seam_tears", "_check_adjacent_ground_edges")


def test_the_census_never_enumerates_families_itself(census_mod):
    """The harness census must get its families from the law reader, not
    from a list of its own."""
    src = Path(inspect.getfile(census_mod)).read_text()
    assert "LAW_FAMILIES" in src, "census must iterate the register"
    named = [n for n in PRIVATE_CHECKS if n in src]
    assert not named, (
        f"the census names private check function(s) {named} — that is the "
        f"monkeypatch-and-enumerate approach every lane copy used, and how "
        f"nine families were lost from an integration report")
    assert "setattr(" not in src, "the census monkeypatches the law reader"


def test_the_law_true_run_refuses_a_patch_with_no_sidecar(cg, tmp_path):
    """A context-free run OVERCOUNTS by construction (memory
    ``check-grade-needs-law-true-frame``: 588 rows vs 0 actionable at
    KCLT).  It must never be reachable by accident."""
    bare = tmp_path / "no_sidecar.osm"
    bare.write_text("<osm version='0.6'></osm>")
    with pytest.raises(FileNotFoundError):
        cg.run_checks_law_true(bare)


def test_the_side_partition_is_the_laws_own_and_reports_mixed(cg):
    """Two different airside/groundside partitions exist in this tree and
    they disagree.  The census uses the LAW's (``_is_groundside``); a
    census that used ``geom_guard._AIRSIDE_ROLES`` was counting a different
    population.  This pins the divergence so a future merge is deliberate."""
    from auto_patch.geom_guard import _AIRSIDE_ROLES
    guard_airside = set(_AIRSIDE_ROLES)
    law_groundside = set(cg._GROUNDSIDE_ROLES)
    assert guard_airside & law_groundside == {"service_junction"}, (
        "the geom-guard and grade-law role partitions no longer disagree "
        "exactly on service_junction — re-read both before changing "
        "check_grade.row_side")

    class _W:
        def __init__(self, role):
            self.tags = {"role": role}

    class _Row:
        def __init__(self, a, b):
            self.way_a, self.way_b = _W(a), _W(b)
    assert cg.row_side(_Row("apron", "runway")) == "airside"
    assert cg.row_side(_Row("service_road", "groundside_pavement")) == \
        "groundside"
    assert cg.row_side(_Row("apron", "service_road")) == "mixed"


def test_the_object_pad_role_is_registered_at_every_role_keyed_site(cg):
    """THE ``object_pad`` REGISTRATION TWIN (per-cluster-object-seating
    spec §5.4, object-reseat-threshold spec §2.3: "the role literal
    ``object_pad`` is NEW and wire-adjacent: it must be registered in
    ``ROLE_GRADE_LIMITS`` AND in the harness law-family machinery in the
    same change").

    The precedent this pins is the ols_cut sweep, quoted in
    ``verification._NON_SOURCE_PAVEMENT_ROLES``: that role WAS wired into
    ``SOFT_RECEIVER_ROLES`` / ``AEROWAY_FOR_ROLE`` / ``ROLE_GRADE_LIMITS``
    and NOT into the source-adjacency set, and flipping its gate on fired
    a false invariant at three airports on lawful cuts.  "Every role-keyed
    site has to be enumerated for a new role" — so every site is asserted
    here, from the ONE literal in the registry."""
    from auto_patch import verification as _verification
    from auto_patch.config import ROLE_GRADE_LIMITS
    from auto_patch.layout import (
        AEROWAY_FOR_ROLE, ROLE_OBJECT_PAD, SOFT_RECEIVER_ROLES)

    assert ROLE_OBJECT_PAD == "object_pad"
    assert ROLE_OBJECT_PAD in ROLE_GRADE_LIMITS
    assert ROLE_GRADE_LIMITS[ROLE_OBJECT_PAD] is None, (
        "a pad's outer face is a BENCH by law (relief cap over the margin "
        "ring); a within-shape pavement cap would mint a violation "
        "against every lawful pad")
    assert ROLE_OBJECT_PAD in SOFT_RECEIVER_ROLES, (
        "pavement wins absolutely (PAD LAW clause 2/3) — that IS the "
        "soft-receiver contract")
    assert AEROWAY_FOR_ROLE.get(ROLE_OBJECT_PAD) == "aerodrome"
    assert ROLE_OBJECT_PAD in _verification._NON_SOURCE_PAVEMENT_ROLES, (
        "a pad is off-source BY LAW — clause 2 differences it against the "
        "pavement union — so check_source_adjacency must not judge it "
        "(the ols_cut lesson, verbatim)")


def test_the_object_pad_role_adds_no_law_family_and_mints_no_row(cg):
    """The other half of the registration: what the CENSUS does with a
    pad.  ``ROLE_GRADE_LIMITS[object_pad] is None`` is the registration —
    it puts the role on ``check_grade``'s skip list, so a pad is excluded
    from the within-shape, cross-shape and step families alike, exactly
    as ``graded_strip`` / ``ols_cut`` / ``boundary`` are.

    And it adds NO family: ``LAW_FAMILIES`` is the register of CHECKS
    ``run_checks`` emits, and pads add no check.  A family key with no
    producer behind it would be a family the census reports and nothing
    can ever populate — the mirror image of the nine families a lane's
    census wrapper LOST, and just as untrue."""
    class _W:
        def __init__(self, **tags):
            self.tags = dict(tags)

    pad = _W(role="object_pad")
    apron = _W(role="apron")
    assert cg._role_grade_limit(pad, 0.015) is None, (
        "the pad must be on the law's skip list, or every bench face is a "
        "within-shape violation")
    assert cg._pair_grade_limit(pad, apron, 0.015) is None
    assert cg._pair_grade_limit(apron, pad, 0.015) is None
    assert "object_pad" not in {key for key, _t, _b in cg.LAW_FAMILIES}, (
        "object_pad is a ROLE, not a law family — registering it as a "
        "family would mint a census row nothing produces")
    # …and it is not silently swept into the groundside partition either:
    # a pad is terrain, on neither side of the airside/groundside split.
    assert "object_pad" not in cg._GROUNDSIDE_ROLES


def test_a_role_less_interior_ring_is_judged_at_its_hosts_cap(cg):
    """L-1 (spec ``tunnel-ramp-cut-boundaries-spec.md`` §3): a role-less
    ``shape_interior_ring`` — the hole ruling 4's ramp cut leaves in the
    pavement — is judged at its HOST shape's role, cap and SIDE, not at the
    caller's airside default.  OTHH's two rings (-12315/-12316) minted 78
    step + 9 within-shape rows purely by falling through to 1.5 %/airside
    while their host was the groundside tunnel ramp whose vertices they are
    (4 % then, 8 % since RULINGS 2026-09-12m -- this twin is about the
    host-cap CLAUSE, not the number)."""
    class _W:
        def __init__(self, **tags):
            self.tags = dict(tags)

    ring = _W(o4_feature="shape_interior_ring", o4_host_role="tunnel_ramp")
    host = _W(role="tunnel_ramp")
    junction = _W(role="junction")

    # The ONE cap resolver and the ONE side partition both answer HOST.
    assert cg.law_role(ring) == "tunnel_ramp"
    assert cg._role_grade_limit(ring, 0.015) == \
        cg._role_grade_limit(host, 0.015), (
            "the ring must hold exactly its host's cap")
    assert cg._role_grade_limit(ring, 0.015) > 0.015, (
        "the ring is still being judged at the caller's airside default")
    assert cg._is_groundside(ring) is True
    # …so the designed airside/groundside wall exempts the ring↔junction
    # step the ramp cut creates, exactly as it exempts host↔junction.
    assert cg._airside_groundside_pair(ring, junction) is True

    # An UNRESOLVED ring is left exactly as parsed — no host, no change.
    orphan = _W(o4_feature="shape_interior_ring")
    assert cg.law_role(orphan) is None
    assert cg._role_grade_limit(orphan, 0.015) == 0.015

    # SCOPE: only the interior-RING classes are judged at the host.  A
    # ``gap_drainage_spine`` is a breakline, and stamping its host role for
    # the LAW minted a phantom drainage-minimum row on the frame of record
    # — it keeps host resolution for REPORTING only.
    spine = _W(o4_feature="gap_drainage_spine",
               o4_host_role="service_junction")
    assert cg.law_role(spine) is None
    assert cg.effective_role(spine) == "service_junction"
    assert "gap_drainage_spine" not in cg.HOST_CAP_FEATURE_CLASSES
    assert set(cg.HOST_CAP_FEATURE_CLASSES) <= set(
        cg.ROLE_LESS_FEATURE_CLASSES), (
            "a host-capped class that is not a registered role-less class "
            "is a class no host resolver ever stamps")


def test_the_law_role_is_read_through_one_accessor(cg):
    """The L-1 twin.  The CLI, the census and the pytest fixtures share ONE
    code path only as long as the law's THREE role readers all ask
    ``law_role``.  A reader that goes back to ``tags.get("role")`` silently
    re-judges interior rings at the airside default on whichever path it
    sits — the census-wrapper defect wearing a different hat."""
    for fn in (cg._role_grade_limit, cg._is_groundside,
               cg._airside_groundside_pair):
        code = _code_only(inspect.getsource(fn))
        assert "law_role" in code, (
            f"{fn.__name__} must resolve a way's role through law_role")
        assert 'tags . get ( "role" )' not in code \
            and "tags . get ( 'role' )" not in code, (
                f"{fn.__name__} reads the raw role tag beside law_role — "
                f"that is a second law-role resolver")
    # Hosts are resolved ONCE, in run_checks, before any check runs — so
    # every path that reaches a check has the stamps.
    rc = _code_only(inspect.getsource(cg.run_checks))
    assert "resolve_feature_hosts" in rc, (
        "run_checks must resolve feature hosts; without it law_role has "
        "nothing to read and the rings fall back to the airside default")
    assert rc.index("resolve_feature_hosts") < min(
        rc.index(n) for n in PRIVATE_CHECKS if n in rc), (
            "feature hosts must be resolved BEFORE the first check runs")


# ══════════════════════════════════════════════════════════════════════
# §1b NO FAMILY WALK LOSES A SURFACE TO A ROLE MIGRATION
# ══════════════════════════════════════════════════════════════════════
# THE DEFECT (S3 dossier, RULINGS 2026-08-13b "OTHH −639 ADJUDICATED:
# CENSUS BLINDNESS").  A law family's domain is a role set.  The corridor
# round re-roled ~15.5 km of landside pavement perimeter out of
# ``groundside_pavement`` and into ``service_junction`` / ``service_road``
# — and one domain set (``grade_law._DRAINAGE_MIN_GROUNDSIDE_ROLES``,
# feeding ``check_grade._DRAINAGE_MIN_ROLES``) named only the old role.
# The walk stopped reading 15.5 km of surface, the count fell by 750 rows,
# and the fall was quoted as an improvement.  Structurally silent, exactly
# as the R19 typo was: an empty walk and a compliant walk report the same
# zero.
#
# WHY A SWEEP AND NOT A LIST.  A hand-listed set of "the sets that matter"
# is the census-wrapper defect in miniature — it covers what its author
# remembered.  This walks EVERY module-level role set in the law and the
# census and applies one rule that has no exceptions today:
#
#     a role set that admits ``groundside_pavement`` admits the whole
#     landside PAVEMENT family it can be re-roled into — ``service_road``
#     and ``service_junction``.
#
# The rule is directional on purpose.  A road-family set (``ROAD_ROLES``,
# ``_WELD_HUB_ROLES``, ``NEAR_MISS_FRONTAGE_SOFT_ROLES``) that names the
# service roles WITHOUT ``groundside_pavement`` is a deliberate scope, not
# a migration casualty: nothing re-roles pavement INTO
# ``groundside_pavement``.  Only the migration direction is asserted.
_MIGRATION_SOURCE_ROLE = "groundside_pavement"
_MIGRATION_TARGET_ROLES = frozenset({"service_road", "service_junction"})


def _role_sets_of(mod) -> dict:
    """``{name: frozenset}`` for every module-level set/frozenset/tuple of
    strings that names at least one EMITTED role literal."""
    import auto_patch.layout as LAY
    emitted = {getattr(LAY, n) for n in dir(LAY) if n.startswith("ROLE_")
               and isinstance(getattr(LAY, n), str)}
    out = {}
    for name in dir(mod):
        val = getattr(mod, name, None)
        if not isinstance(val, (set, frozenset, tuple, list)):
            continue
        if not val or not all(isinstance(v, str) for v in val):
            continue
        if not (set(val) & emitted):
            continue
        out[name] = frozenset(val)
    return out


def test_no_role_set_admits_groundside_pavement_without_the_road_family(cg):
    """The S3 blindness class, swept.

    Every law/census role set that reads landside pavement must read the
    roles that pavement is re-roled INTO.  A new set that names
    ``groundside_pavement`` alone fails here in the commit that adds it,
    instead of silently halving a census three rounds later.
    """
    import auto_patch.grade_law as GL

    offenders = []
    for mod, label in ((GL, "grade_law"), (cg, "check_grade")):
        for name, roles in _role_sets_of(mod).items():
            if _MIGRATION_SOURCE_ROLE not in roles:
                continue
            missing = _MIGRATION_TARGET_ROLES - roles
            if missing:
                offenders.append(f"{label}.{name} misses {sorted(missing)}")
    assert not offenders, (
        "role-migration blindness: these domain sets read "
        f"{_MIGRATION_SOURCE_ROLE!r} but not the roles it is re-roled into "
        f"— {offenders}.  A surface that changes role must not leave a "
        f"family's walk (RULINGS 2026-08-13b, the OTHH −639 verdict)")


#: Role literals a census WALK may name that are not ``layout.ROLE_*``
#: constants — each reachable on an emitted patch, each with its source.
#: A literal that is NOT here and NOT a ROLE_* value cannot match any way,
#: so a walk naming it reads nothing while looking like coverage.
_READABLE_NON_ROLE_LITERALS = {
    # ROLE_TERMINAL was renamed to ROLE_BUILDING (user 2026-06-12);
    # ``layout`` keeps the alias on READ paths for pre-rename patches on
    # disk, and a census reads patches from disk.
    "terminal",
    # Apron sub-role: aeroway=parking_position/stand/gate pavement
    # (``pavement_classification._STAND_AEROWAY``, ``terminals.py``).
    "stand",
    # Hangar pad seats (``config`` s81 / ``strip_seam_law``).
    "hangar_pad",
}


def _census_walk_set_names(cg) -> set:
    """The names ``check_grade`` uses as a WALK DOMAIN — every identifier
    on the right of a ``<way>.role in`` / ``not in`` test.  Detected from
    the source, so a new walk cannot opt out of the sweep by not being
    listed anywhere."""
    src = inspect.getsource(cg)
    pat = re.compile(
        r"(?:\.role|law_role\([^)]*\)|effective_role\([^)]*\))\s+"
        r"(?:not\s+)?in\s+([A-Za-z_][A-Za-z_0-9]*)")
    return set(pat.findall(src))


def test_every_role_a_census_WALK_names_is_a_role_the_engine_EMITS(cg):
    """The R19 twin, generalised past the one set it was written for.

    ``_DRAINAGE_MIN_ROLES`` used to read ``("apron", "stand", "groundside",
    "parking")`` — literals this engine has never emitted, so the
    groundside half of §B3 could not fire.  An unreachable literal in a
    walk set LOOKS like coverage and is worth nothing; the emitted-role
    join is the only thing that tells the two apart.

    Scoped to WALK sets (``_census_walk_set_names``), which is where an
    unreachable literal costs rows.  The law's role→rule DISPATCH sets are
    deliberately wider: ``grade_law._ADJACENT_TAXIWAY_ROLES`` names the
    family alias ``"taxiway"`` so a caller may ask the law about the
    taxiway family without naming four role values, and nothing walks it.
    """
    import auto_patch.layout as LAY

    emitted = {getattr(LAY, n) for n in dir(LAY) if n.startswith("ROLE_")
               and isinstance(getattr(LAY, n), str)}
    emitted |= _READABLE_NON_ROLE_LITERALS
    # ...AND THE ROLES v2 EMITS (v2 is the only engine, RULINGS
    # 2026-09-13au).  ``layout``'s ROLE_ constants are v1's vocabulary and
    # do not name v2's structure roles (``wall_corridor_ramp``,
    # ``garage_ramp``, ``door_ramp``), which the emitter writes and
    # ``ramp_in_road`` walks.  Read from v2's own law register, so this
    # stays the emitted-role JOIN the twin is about and never a
    # hand-written exemption list.
    from auto_patch_v2.law import tables as _V2T
    emitted |= set(_V2T.governed_roles(_V2T.load_default()))
    unreachable = {}
    for name in sorted(_census_walk_set_names(cg)):
        roles = getattr(cg, name, None)
        if not isinstance(roles, (set, frozenset, tuple, list)):
            continue
        if not roles or not all(isinstance(r, str) for r in roles):
            continue
        dead = sorted(set(roles) - emitted)
        if dead:
            unreachable[f"check_grade.{name}"] = dead
    assert not unreachable, (
        f"census walks name role literals the engine never emits: "
        f"{unreachable}.  An unreachable literal is not coverage — it is "
        f"the fix-cycle-2 item-5 defect (verdict (d), BROKEN INSTRUMENT)")


def test_every_retired_law_really_left_its_familys_walk(cg):
    """RETIREMENT IS RECORDED, AND THE RECORD IS CHECKED.

    A law the owner withdraws stops producing rows — and so does a walk
    that goes blind.  The output is the same zero, which is how §B3's
    landside half lost 11,932 rows across the five baseline airports
    without anyone noticing (RULINGS 2026-08-13b).  Days later the owner
    withdrew that same half (RULINGS 2026-08-14, "DRAINAGE RULING SCOPE
    CLARIFIED").  ``check_grade.RETIRED_LAWS`` is the difference between
    those two zeros, and this asserts the register is TRUE rather than
    decorative: the surfaces it says were withdrawn are really absent
    from the family's walk, and the family it names is really a family.

    Note the key shape: a retired law may be one HALF of a family's
    domain (the apron half of ``drainage_minimum`` did NOT retire), so
    these keys are deliberately not family keys.
    """
    registered = {key for key, _title, _bucket in cg.LAW_FAMILIES}
    assert cg.RETIRED_LAWS, (
        "the retirement register is empty; RULINGS 2026-08-14 withdrew "
        "the landside half of the drainage minimum — an empty register "
        "makes that zero indistinguishable from a blind walk")
    for key, entry in cg.RETIRED_LAWS.items():
        fam = entry["family"]
        assert fam in registered or fam is None, (
            f"{key!r} names {fam!r}, which is no law family")
        assert cg.RETIRED_LAW_RULING in entry["why"], (
            f"{key!r} carries no owner ruling")
        assert entry["roles"], f"{key!r} withdraws no surface"
        # THE FAMILY'S OWN WALK, found from ITS OWN SOURCE — never a
        # hand-written pointer in the register, which would be one more
        # copy to drift.  Scoped to that walk on purpose: these roles are
        # retired from ONE law, and they must stay in every other
        # family's domain (asserted by the twin below).
        fn = getattr(cg, f"_check_{fam}", None)
        assert fn is not None, (
            f"{key!r} names family {fam!r} but there is no _check_{fam} to "
            f"read a walk set out of — the register cannot be checked")
        src = inspect.getsource(fn)
        names = set(re.findall(
            r"\.role\s+(?:not\s+)?in\s+([A-Za-z_][A-Za-z_0-9]*)", src))
        assert names, f"_check_{fam} walks no role set"
        for name in sorted(names):
            roles = getattr(cg, name, None)
            if not isinstance(roles, (set, frozenset)):
                continue
            still = sorted(set(entry["roles"]) & set(roles))
            assert not still, (
                f"{key!r} calls {still} RETIRED, but its own walk "
                f"check_grade.{name} still reads them — a withdrawn law "
                f"that keeps firing")


def test_the_retired_landside_roles_are_still_READ_by_the_other_families(cg):
    """The retirement must not be allowed to re-import the blindness.

    ``service_road`` / ``service_junction`` / ``groundside_pavement``
    leave the DRAINAGE walk by law.  They must stay in every other
    family's domain — that is the S7 half-1 restoration, and it is what
    makes the drainage zero readable as a law and not as a symptom.
    """
    import auto_patch.layout as LAY

    retired = set(cg.RETIRED_LAWS["drainage_minimum::groundside"]["roles"])
    assert retired <= set(LAY.GROUNDSIDE_ROLES)
    assert retired <= set(cg._GROUNDSIDE_ROLES), (
        "a retired-from-drainage role fell out of the SIDE partition too")
    assert retired <= set(cg._STRIP_PAVEMENT_ROLES), (
        "a retired-from-drainage role fell out of the strip weld domain")
    assert set(cg._ROAD_FAMILY_ROLES) <= retired | {"service_road",
                                                    "service_junction"}


# ══════════════════════════════════════════════════════════════════════
# §2 THE SIDECAR CONTRACT
# ══════════════════════════════════════════════════════════════════════

def test_every_emitted_sidecar_key_is_classified(cg):
    """The sidecar is the contract.  Read the keys the EMITTER writes
    straight out of ``layout._write_axes_sidecar`` and require each to be
    classified as law input or evidence — so a new emitted field can never
    be silently ignored by every reader in the tree."""
    from auto_patch.layout import PavementLayout
    src = inspect.getsource(PavementLayout._write_axes_sidecar)
    body = src.split("data = {", 1)[1]
    emitted = set(re.findall(r'^\s*"([a-z_]+)":', body, re.M))
    assert len(emitted) >= 10, (
        f"only parsed {sorted(emitted)} out of the sidecar writer — the "
        f"parse broke, not the contract")
    classified = set(cg.SIDECAR_LAW_KEYS) | set(cg.SIDECAR_EVIDENCE_KEYS)
    assert emitted <= classified, (
        f"sidecar key(s) {sorted(emitted - classified)} are emitted but "
        f"classified nowhere: add them to check_grade.SIDECAR_LAW_KEYS "
        f"(if run_checks must consume them) or SIDECAR_EVIDENCE_KEYS.")


def test_the_evidence_reader_reports_unknown_keys(cg, tmp_path):
    osm = tmp_path / "p.osm"
    osm.write_text("<osm version='0.6'></osm>")
    (tmp_path / "p.osm.axes.json").write_text(json.dumps(
        {"anchor": [1.0, 2.0], "ruleset": "faa", "a_brand_new_field": 7}))
    ev = cg.sidecar_evidence(osm)
    assert ev["unknown_keys"] == ["a_brand_new_field"]


def test_the_declared_ruleset_is_never_confused_with_the_active_one(cg,
                                                                   tmp_path):
    """A patch predating the FAA/ICAO split has no ruleset key; reporting
    the DEFAULT as if it were declared would present an assumption as a
    measurement."""
    osm = tmp_path / "p.osm"
    osm.write_text("<osm version='0.6'></osm>")
    (tmp_path / "p.osm.axes.json").write_text(json.dumps({"anchor": None}))
    fo: dict = {}
    cg.run_checks_law_true(osm, family_out=fo)
    assert fo["_ruleset_declared"] is None
    assert fo["_ruleset_active"], "an active ruleset must always be named"


# ══════════════════════════════════════════════════════════════════════
# §3 THE BUILD ENTRY REFUSES
# ══════════════════════════════════════════════════════════════════════

def test_the_build_entry_refuses_a_cwd_without_venv_and_osm_data(build_mod,
                                                                 tmp_path):
    """The wrong-cwd trap: an auto_patch build from a directory without
    ``venv/`` and ``OSM_data/`` exits 0 with a silently SMALLER layout —
    it has faked a speedup and a defect drop more than once."""
    with pytest.raises(SystemExit) as exc:
        build_mod.require_build_cwd(tmp_path)
    assert "OSM_data" in str(exc.value)


def test_the_build_entry_accepts_the_real_tree(build_mod):
    assert build_mod.require_build_cwd(ROOT) == ROOT


def test_the_build_entry_refuses_an_unwarmed_elevation_cache(build_mod,
                                                             tmp_path):
    """The standalone DEM path degrades to the BASE surface (no insets, no
    airport smoothing) with only a log warning — warm-vs-cold cache has
    moved terrain 12 m mid-session.  The harness turns that warning into a
    refusal, so a lane cannot quote an elevation from a degraded frame."""
    state = build_mod.dem_cache_state(tmp_path, 30, 31)
    assert not state["base_raster"]
    assert not state["airports_layer"]
    with pytest.raises(SystemExit):
        build_mod.require_dem_frame(state, allow_degraded=False)
    # ...and the escape hatch is explicit, never silent.
    build_mod.require_dem_frame(state, allow_degraded=True)


def test_the_build_entry_sets_the_sidecar_verbosity(build_mod):
    """The build entry raises the verbosity, and must keep doing so.

    This was load-bearing until 2026-08-05: ``_write_axes_sidecar`` was
    gated on ``config.LOG_VERBOSITY > 0``, so without it the patch had NO
    sidecar and every census silently degraded to the context-free frame
    — the single most expensive silent degradation in this tree.  The gate
    is gone (item 1) and the sidecar is now unconditional; the verbosity
    is still set here for the per-phase build chatter the harness reports,
    and belt-and-braces on a contract this expensive to lose is cheap."""
    src = Path(inspect.getfile(build_mod)).read_text()
    assert "O4_LOG_VERBOSITY" in src


# ── LANE INPUTS ARE PROVISIONED, NEVER HAND-SEEDED (owner 2026-08-12b) ──
#
# A fresh lane build dir has no per-tile cfg, ``Tile.read_from_config``
# falls back to the GLOBAL config (which by construction carries no
# ``default_website``: O4_Cfg_Vars excludes the per-tile vars from it), and
# the tile build refuses at the provider check.  Two lanes improvised two
# DIFFERENT cfg sources past that wall on 2026-08-12 — the inconsistency is
# the defect, not the copy.

def test_the_canonical_tile_cfg_is_the_RITUALS_OWN_source(build_mod):
    """ONE source, and it is the one ``lane_worktree.sh`` already clones
    ``Ortho4XP.cfg`` and ``Patches/`` from — not a second hierarchy
    invented at the build entry, and not the shared data repo (whose
    owner app config has no per-tile keys to give)."""
    src = build_mod.canonical_tile_cfg(30, 31)
    assert src == build_mod.MAIN_ENGINE_TREE / "Tiles" / \
        "zOrtho4XP_+30+031" / "Ortho4XP_+30+031.cfg"
    assert str(build_mod.MAIN_ENGINE_TREE).endswith("/Ortho4XP")
    assert build_mod.DATA_REPO not in src.parents, (
        "the per-tile cfg is a build INPUT from the main tree, not corpus "
        "data — provisioning it out of the shared repo would make every "
        "lane's tile frame depend on a directory the ritual keeps LOCAL")
    ritual = (ROOT / "tools" / "harness" / "lane_worktree.sh").read_text()
    assert 'O4_MAIN_REPO' in ritual and 'O4_MAIN_REPO' in \
        inspect.getsource(build_mod)[:20000], (
        "one environment override moves both, or the ritual and the build "
        "entry provision from two different trees")


def test_the_per_tile_cfg_is_PROVISIONED_when_absent(build_mod, tmp_path):
    """Byte-equal to the canonical source, with the provenance recorded."""
    source_root = tmp_path / "main"
    canon = source_root / "Tiles" / "zOrtho4XP_+30+031" / \
        "Ortho4XP_+30+031.cfg"
    canon.parent.mkdir(parents=True)
    canon.write_text("default_website=Arc\ndefault_zl=16\n")
    lane = tmp_path / "lane" / "zOrtho4XP_+30+031"

    rec = build_mod.provision_tile_cfg(30, 31, lane, source_root=source_root)

    dest = lane / "Ortho4XP_+30+031.cfg"
    assert rec["action"] == "provisioned"
    assert dest.read_bytes() == canon.read_bytes(), "a BYTE copy, not a render"
    assert not dest.is_symlink(), (
        "a real file: the lane may rewrite its own input, and a link would "
        "write the main tree")
    assert rec["cfg"] == str(dest) and rec["canonical_source"] == str(canon)
    assert rec["sha256"] == hashlib.sha256(canon.read_bytes()).hexdigest(), (
        "the frame records WHICH cfg the build ran on, hashed — two lanes "
        "on two sources left nothing in either frame to compare")


def test_a_MISSING_canonical_tile_cfg_DERIVES_from_global_defaults(
        build_mod, tmp_path):
    """OWNER RULING 2026-08-14 — "A TILE WITHOUT A PER-TILE CFG USES
    GLOBAL DEFAULTS".  The refusal this twin used to assert AMENDS into a
    derivation: per-tile cfg is an OVERRIDE of globals in the engine's own
    reader, so "no per-tile cfg" is a defined state, not an error.

    What the twin still enforces is the 2026-08-12b substance the ruling
    keeps: ONE canonical source, provisioned by the ritual, RECORDED — and
    nothing SYNTHESIZED (the derived file overrides nothing at all).
    """
    source_root = tmp_path / "main"
    source_root.mkdir()
    gcfg = source_root / "Ortho4XP.cfg"
    gcfg.write_text("mesh_zl=19\nroad_level=1\n")
    lane = tmp_path / "lane" / "zOrtho4XP_+30+031"

    said = []

    class _Prog:
        def note(self, m):
            said.append(m)

    rec = build_mod.provision_tile_cfg(30, 31, lane, _Prog(),
                                       source_root=source_root)

    dest = lane / "Ortho4XP_+30+031.cfg"
    assert rec["action"] == "derived-from-global-defaults"
    assert dest.is_file(), "the ritual PROVISIONS one instead of refusing"
    assert rec["global_source"] == str(gcfg)
    assert rec["global_sha256"] == \
        hashlib.sha256(gcfg.read_bytes()).hexdigest(), (
        "the frame records WHICH globals this tile inherited, hashed")
    assert rec["sha256"] == hashlib.sha256(dest.read_bytes()).hexdigest(), (
        "and the derived file's own sha — a derived input nobody can hash "
        "afterwards is a hand-seed with extra steps")
    # NOTHING synthesized: every non-comment line would be an override,
    # and an override nobody chose is the made-up-provider trap.
    body = [ln for ln in dest.read_text().splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    assert body == [], (
        "a DERIVED cfg carries zero override lines: that IS the global "
        "defaults under the engine's reader, and writing the global values "
        "out would FREEZE a snapshot that stops tracking them")
    assert str(gcfg) in dest.read_text() and rec["global_sha256"] in \
        dest.read_text(), "the file itself says what it was derived from"
    # LOUD, by ruling.
    said = "\n".join(said)
    assert "DERIVED-FROM-GLOBAL-DEFAULTS" in said and "2026-08-14" in said, (
        "a tile running on defaults nobody chose for it must be visible in "
        "the log, not only in the frame")
    # WHICH globals the engine will actually read is recorded too: the
    # derivation defers to them, so a frame naming only the canonical file
    # would describe a different population than the build ran on.  Here
    # they differ by construction (a tmp canonical vs this tree's own), so
    # the divergence must be SAID, not merely recorded.
    assert rec["engine_global_source"] == \
        str(build_mod.engine_global_cfg())
    assert rec["engine_global_sha256"] != rec["global_sha256"]
    assert "DERIVATION FRAME DIVERGES" in said
    # A SECOND run over the same build dir sees an ordinary lane input —
    # and must still report that it was derived, not chosen.
    again = build_mod.provision_tile_cfg(30, 31, lane,
                                         source_root=source_root)
    assert again["action"] == "present" and again["was_derived"] is True


def test_a_MISSING_global_cfg_TOO_still_REFUSES(build_mod, tmp_path):
    """The derivation's floor: with no globals either there are no
    DEFAULTS to derive from, only invention — and a made-up provider and
    ZL build a tile nobody asked for and exit 0."""
    lane = tmp_path / "lane" / "zOrtho4XP_+30+031"
    with pytest.raises(SystemExit) as exc:
        build_mod.provision_tile_cfg(30, 31, lane,
                                     source_root=tmp_path / "empty_main")
    msg = str(exc.value)
    assert "REFUSING" in msg and "Ortho4XP_+30+031.cfg" in msg
    assert "2026-08-12b" in msg and "2026-08-14" in msg, (
        "the refusal cites both the ruling it enforces and the one that "
        "amended it")
    assert not (lane / "Ortho4XP_+30+031.cfg").exists(), (
        "the refusal wrote NOTHING — a defaults file left behind would be "
        "the next lane's canonical source")


def test_a_DERIVED_cfg_reads_IDENTICALLY_to_the_global_config(build_mod,
                                                              tmp_path):
    """THE derivation's whole claim, through the ENGINE'S OWN reader:
    a tile that reads the derived per-tile cfg and a tile that falls back
    to the global config end up with the SAME value for every tile var.

    Asserted against ``O4_Config_Utils`` itself, never a re-implementation
    of its semantics — the census-wrapper defect is what a second copy of
    a reader costs.
    """
    import O4_Config_Utils as CFG
    from O4_Cfg_Vars import list_tile_vars

    source_root = tmp_path / "main"
    source_root.mkdir()
    # The REAL global config this tree runs on — same file the engine
    # loaded at import, so "global defaults" means one thing here.
    gcfg = source_root / "Ortho4XP.cfg"
    gcfg.write_bytes(Path(CFG.global_cfg_file).read_bytes())
    lane = tmp_path / "lane" / "zOrtho4XP_+30+031"
    rec = build_mod.provision_tile_cfg(30, 31, lane, source_root=source_root)
    assert rec["action"] == "derived-from-global-defaults"

    derived = CFG.Tile(30, 31, str(tmp_path / "unused_a") + "/")
    derived.read_from_config(config_file=rec["cfg"])
    globals_only = CFG.Tile(30, 31, str(tmp_path / "unused_b") + "/")
    globals_only.read_from_config(use_global=True)

    differs = {v for v in list_tile_vars
               if getattr(derived, v) != getattr(globals_only, v)}
    assert not differs, (
        f"the derived per-tile cfg changed {sorted(differs)} — it must "
        f"OVERRIDE nothing: the ruling says a tile without a per-tile cfg "
        f"uses the global defaults, not defaults plus a surprise")


def test_an_EXISTING_lane_tile_cfg_is_NEVER_overwritten(build_mod, tmp_path):
    """A lane deliberately building at another provider/ZL owns its input;
    replacing it would be a frame change with no log line."""
    source_root = tmp_path / "main"
    canon = source_root / "Tiles" / "zOrtho4XP_+30+031" / \
        "Ortho4XP_+30+031.cfg"
    canon.parent.mkdir(parents=True)
    canon.write_text("default_website=Arc\ndefault_zl=16\n")
    lane = tmp_path / "lane" / "zOrtho4XP_+30+031"
    lane.mkdir(parents=True)
    mine = lane / "Ortho4XP_+30+031.cfg"
    mine.write_text("default_website=BI\ndefault_zl=17\n")

    rec = build_mod.provision_tile_cfg(30, 31, lane, source_root=source_root)

    assert rec["action"] == "present"
    assert rec["was_derived"] is False, (
        "a cfg an earlier run DERIVED still reads as 'present' later — the "
        "frame must not downgrade 'this tile is on global defaults' to "
        "'the lane's own cfg' without saying so")
    assert mine.read_text() == "default_website=BI\ndefault_zl=17\n"
    assert rec["sha256"] == hashlib.sha256(mine.read_bytes()).hexdigest(), (
        "the frame records the cfg the build ACTUALLY ran on, not the one "
        "it would have provisioned")


def test_provisioning_INTO_the_canonical_location_copies_nothing(build_mod,
                                                                 tmp_path):
    """A build in the main tree IS the canonical location — it must not
    copy a file onto itself, and it still records what it ran on."""
    source_root = tmp_path / "main"
    canon = source_root / "Tiles" / "zOrtho4XP_+30+031" / \
        "Ortho4XP_+30+031.cfg"
    canon.parent.mkdir(parents=True)
    canon.write_text("default_website=Arc\ndefault_zl=16\n")
    rec = build_mod.provision_tile_cfg(30, 31, canon.parent,
                                       source_root=source_root)
    assert rec["action"] == "is_canonical_source"
    assert rec["sha256"] == hashlib.sha256(canon.read_bytes()).hexdigest()


def test_the_tile_path_PROVISIONS_before_it_READS_the_config(build_mod):
    """SOURCE twin on the ORDER, which is the whole mechanism:
    ``read_from_config`` silently falls back to the global config, so a
    provision AFTER it would record a source the build never used.  The
    order now lives in ``resolve_tile_frame`` — the ONE frame resolver
    both tile entries call (RULINGS 2026-08-31d) — and ``build_tile``
    reaches it through that function, not by arranging it again."""
    src = inspect.getsource(build_mod.resolve_tile_frame)
    assert src.index("provision_tile_cfg(") < src.index("read_from_config()"), (
        "provision the input BEFORE the engine reads it")
    tile_src = inspect.getsource(build_mod.build_tile)
    assert "resolve_tile_frame(" in tile_src
    assert "provision_tile_cfg(" not in tile_src, (
        "one resolver, not a second arrangement of the same two calls")
    assert "tile_cfg_provenance" in tile_src, "and hand it back for the frame"
    whole = Path(inspect.getfile(build_mod)).read_text()
    assert 'frame["tile_cfg_provenance"] = result.get("tile_cfg_provenance")' \
        in whole, ("the provenance reaches frame.json — an unrecorded "
                   "provisioned input is a hand-seed with extra steps")


def test_warming_an_inset_without_the_dem_scope_refuses(build_mod):
    """``--warm-insets`` FETCHES into the shared data repo, so it is the
    act ``--refresh-data`` exists to authorise (ruling e9daef5).  The
    refusal fires before the cwd check and before the ledger re-exec, so
    nothing is built and nothing is locked."""
    with pytest.raises(SystemExit) as exc:
        build_mod.main(["KMCI", "--warm-insets", "KMCI"])
    assert "--refresh-data dem --warm-insets KMCI" in str(exc.value)


def test_the_warm_touches_exactly_the_airports_named(build_mod, monkeypatch,
                                                     tmp_path):
    """The one-airport scope, mechanically.  A whole-tile build would
    refresh every void inset on the tile against a one-airport
    authorisation; this pass hands ``ensure_airport_insets`` the named
    airport's bounding box and NOTHING else."""
    import O4_Airport_Elevation_Insets as INSETS
    import O4_File_Names as FNAMES
    import O4_OSM_Utils as OSM
    import O4_Vector_Map as VMAP

    airports_cache = tmp_path / "N39W095_airports.osm.bz2"
    airports_cache.write_bytes(b"")
    monkeypatch.setattr(FNAMES, "osm_cached",
                        lambda lat, lon, suffix: str(airports_cache))
    monkeypatch.setattr(OSM, "OSM_layer", lambda *a, **kw: object())
    monkeypatch.setattr(OSM, "OSM_queries_to_OSM_layer",
                        lambda *a, **kw: None)
    monkeypatch.setattr(VMAP, "build_airports_dico", lambda *a, **kw: {})
    monkeypatch.setattr(
        INSETS, "_airport_bounding_boxes",
        lambda tile, dico: {"KMCI": (-94.75, 39.25, -94.66, 39.34),
                            "KFLV": (-94.94, 39.33, -94.88, 39.39)})
    monkeypatch.setattr(INSETS, "select_provider_definitions",
                        lambda *a, **kw: [{"code": "USGS3DEP"}])
    monkeypatch.setattr(INSETS, "parse_airport_elevation_level",
                        lambda level: None)
    called = {}

    def _ensure(lat, lon, boxes, definitions, resolution_m,
                refresh=False, fetch_counter=None, **kw):
        called["boxes"] = dict(boxes)
        called["tile"] = (lat, lon)
        called["refresh"] = refresh
        if fetch_counter is not None:
            fetch_counter[0] += 1

    monkeypatch.setattr(INSETS, "ensure_airport_insets", _ensure)

    summary = build_mod.warm_airport_insets(
        ["KMCI"], ROOT, 39, -95, build_mod.Progress(tmp_path / "p.progress"))

    assert list(called["boxes"]) == ["KMCI"]      # never the neighbour's
    assert called["tile"] == (39, -95)
    # A named airport is an explicit decision, so the pass re-queries
    # instead of consulting the cache — a DURABLE no-coverage negative
    # cached from a transient discovery outage (TNM 504, measured
    # 2026-08-11) would otherwise be unrecoverable.
    assert called["refresh"] is True
    assert summary["airports"] == ["KMCI"] and summary["fetch_attempts"] == 1

    # An airport of ANOTHER tile refuses: this run's lock and snapshot
    # cover the tile it resolved, and nothing else.
    with pytest.raises(SystemExit) as exc:
        build_mod.warm_airport_insets(
            ["HECA"], ROOT, 39, -95,
            build_mod.Progress(tmp_path / "p2.progress"))
    assert "not an airport of tile" in str(exc.value)


# ══════════════════════════════════════════════════════════════════════
# §4 THE LANE RITUAL
# ══════════════════════════════════════════════════════════════════════

RITUAL = HARNESS / "lane_worktree.sh"


def test_the_ritual_script_is_executable():
    assert RITUAL.exists(), "tools/harness/lane_worktree.sh is missing"
    assert os.access(RITUAL, os.X_OK), "lane_worktree.sh is not executable"


def test_the_ritual_mounts_the_whole_shared_data_repo():
    """Owner ruling e9daef5: ONE shared data repo, every lane MOUNTS it.

    The mount list is ENUMERATED from the repo at run time, never
    hard-coded — a data dir the ritual forgets becomes a private cache by
    omission, which is the failure the ruling names.  A copied cache is
    worse still: it warms independently, and warm-vs-cold inset state has
    moved a measured elevation by 12 m here."""
    src = RITUAL.read_text()
    assert re.search(r'^DATA_REPO="\$\{O4_DATA_REPO:-([^}]*)\}"', src, re.M), (
        "the ritual must resolve the shared data repo (O4_DATA_REPO with a "
        "default)")
    assert "data_dirs()" in src and "for entry in \"$DATA_REPO\"/*/" in src, (
        "the mounted data dirs must be ENUMERATED from the shared repo, "
        "not hard-coded — an omitted dir is a private cache")
    req = re.search(r'^REQUIRED_DATA_DIRS="([^"]*)"', src, re.M)
    assert req and set(req.group(1).split()) >= {
        "OSM_data", "Elevation_data", "Airport_mod_cache"}, (
        "OSM_data, Elevation_data and Airport_mod_cache are the floor: "
        "without them the road/corridor/DEM paths silently no-op")
    never = re.search(r'^NEVER_MOUNT="([^"]*)"', src, re.M)
    assert never and set(never.group(1).split()) == {
        "Patches", "Tiles", "Previews", "tmp"}, (
        f"NEVER_MOUNT is {never and never.group(1)!r}: these are lane "
        f"PRODUCTS, and sharing them would let one lane's output enter "
        f"another lane's build")
    assert re.search(r'mount_link "\$d" "\$DATA_REPO/\$d"', src), (
        "data dirs must be SYMLINKED into the shared repo")
    engine = re.search(r'^ENGINE_LINKS="([^"]*)"', src, re.M)
    assert engine and set(engine.group(1).split()) == {"venv"}, (
        "only venv comes from the main engine tree; everything else is data "
        "and comes from the shared repo")


def test_the_ritual_keeps_patches_lane_local_with_its_reason():
    """Patches is the ONE clone, and the justification has to be in the
    file: every tile build writes {ICAO}_auto.patch.osm into Patches/<tile>/
    (auto_patch.driver), so it is a lane's OUTPUT.  Sharing it would let one
    lane's emitted geometry enter another lane's build."""
    src = RITUAL.read_text()
    clone = re.search(r'^CLONE_DIRS="([^"]*)"', src, re.M)
    assert clone and set(clone.group(1).split()) == {"Patches"}
    assert "cp -R" in src, "CLONE_DIRS entries must be copied"
    assert "WRITES" in src and "Patches" in src, (
        "the file must say WHY Patches is lane-local")
    files = re.search(r'^CLONE_FILES="([^"]*)"', src, re.M)
    assert files and "Ortho4XP.cfg" in files.group(1), (
        "Ortho4XP.cfg must be CLONED into a lane worktree: it is untracked, "
        "so a fresh worktree has none, and Tile.read_from_config() then "
        "falls back to constructor defaults — a surface production never "
        "builds, announced by one log line")


def test_the_ritual_refuses_a_real_directory_where_a_mount_belongs():
    """A REAL data directory in a lane tree is a private cache — the one
    thing the ruling forbids — so the ritual must refuse it rather than
    silently leave it in place."""
    src = RITUAL.read_text()
    assert "PRIVATE CACHE" in src and "e9daef5" in src, (
        "the refusal must name the private cache and the ruling")
    assert "OFF-REPO" in src, (
        "`check` must catch a symlink that resolves OUTSIDE the shared "
        "repo — a different corpus reads as a working mount")


def test_the_ritual_refuses_teardown_while_the_tree_is_busy():
    src = RITUAL.read_text()
    assert "lsof" in src or "pgrep" in src, (
        "teardown must check for live child processes holding the tree")
    assert "worktree remove" in src


def test_the_ritual_shell_is_syntactically_valid():
    r = subprocess.run(["/bin/sh", "-n", str(RITUAL)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_the_ritual_makes_the_tool_index_reachable():
    """Owner ruling 7e90032: the index is THE consultation surface, and a
    tool absent from it is treated as absent.  A lane that cannot READ it
    consults nothing and forks the near-fit — measured 2026-08-06: 30 of
    58 worktrees on this machine had no ``tools/INDEX.md`` at all (their
    refs predate it), and this file's own index twin fails in every one."""
    src = RITUAL.read_text()
    assert re.search(r'^INDEX_REL="tools/INDEX\.md"', src, re.M), (
        "the ritual must name the index it makes reachable")
    assert "index_state up" in src and "index_state check" in src, (
        "`up` must materialise the index and `check` must audit it")
    assert "chmod 444" in src, (
        "a mirrored index is READ-ONLY: the tracked file at the repo root "
        "is the one a promotion edits, and two writable copies would "
        "diverge silently")
    assert "7e90032" in src, "the refusal must cite the ruling it enforces"
    assert re.search(r'grep -v -E "\^tools/\(INDEX\\\.md\)\?\$"', src), (
        "the untracked audit must allow the index mirror — otherwise `up` "
        "refuses the tree it just prepared")


def _tiny_repo(tmp_path):
    """A miniature main repo + shared data repo the ritual can run on.

    Returns ``(main, data, env, ref_without_index)`` where the repo's FIRST
    commit has no ``tools/INDEX.md`` — the old-worktree case the fix has to
    degrade gracefully into."""
    main = tmp_path / "main"
    (main / "Ortho4XP" / "venv").mkdir(parents=True)
    (main / "Ortho4XP" / "keep").write_text("engine\n")
    (main / "Ortho4XP" / "Ortho4XP.cfg").write_text("apt_smoothing_pix=8\n")
    # The real repo ignores the cloned config and the lane's Patches
    # output; without that the ritual's own untracked audit would flag the
    # tree it just prepared, and this twin would be testing the fixture.
    (main / ".gitignore").write_text(
        "Ortho4XP/Ortho4XP.cfg\nOrtho4XP/Patches/\nOrtho4XP/venv\n")
    data = tmp_path / "data"
    for d in ("OSM_data", "Elevation_data", "Airport_mod_cache"):
        (data / d).mkdir(parents=True)
    env = dict(os.environ,
               O4_MAIN_REPO=str(main), O4_DATA_REPO=str(data),
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")

    def git(*args):
        r = subprocess.run(("git", "-C", str(main)) + args, env=env,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return r.stdout.strip()

    # The real repo's shape, exactly: Patches/ is gitignored as a whole,
    # and ONE shipped patch inside it is force-added and TRACKED.
    (main / "Ortho4XP" / "Patches" / "+39-078").mkdir(parents=True)
    (main / "Ortho4XP" / "Patches" / "+39-078" / "2W2_runways.patch.osm"
     ).write_text("<osm version='0.6'></osm>\n")

    git("init", "-q")
    git("add", "-A")
    git("add", "-f", "Ortho4XP/Patches/+39-078/2W2_runways.patch.osm")
    git("commit", "-qm", "engine only, no tool index")
    old_ref = git("rev-parse", "HEAD")
    (main / "tools").mkdir()
    (main / "tools" / "INDEX.md").write_text("# Tool index\n\ncensus.py\n")
    git("add", "-A")
    git("commit", "-qm", "the tool index lands")
    return main, data, env, old_ref


def _ritual(env, *args, cwd=None):
    return subprocess.run([str(RITUAL), *args], env=env, cwd=cwd,
                          capture_output=True, text=True)


def test_the_ritual_mirrors_the_index_into_a_worktree_that_predates_it(
        tmp_path):
    """THE KNOWN-ANSWER TWIN for the fix: a lane checked out at a ref
    without the index gets a READ-ONLY mirror of the main tree's, `check`
    agrees, a drifted mirror reads STALE (never a refusal — a lane adding
    its own index row differs from main by design), and `down` takes the
    mirror away rather than reporting it as uncommitted lane work."""
    main, _data, env, old_ref = _tiny_repo(tmp_path)
    index = main / "tools" / "INDEX.md"

    up = _ritual(env, "up", "lane1", old_ref)
    assert up.returncode == 0, up.stdout + up.stderr
    mirror = main / ".claude" / "worktrees" / "lane1" / "tools" / "INDEX.md"
    assert mirror.is_file(), (
        f"no index mirrored into the lane:\n{up.stdout}\n{up.stderr}")
    assert mirror.read_text() == index.read_text()
    assert not os.access(mirror, os.W_OK), "the mirror must be read-only"
    assert "MIRRORED" in up.stdout

    ok = _ritual(env, "check", "lane1")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "mirrored" in ok.stdout and "STALE" not in ok.stdout

    index.write_text("# Tool index\n\ncensus.py\nA_NEWLY_PROMOTED_TOOL.py\n")
    stale = _ritual(env, "check", "lane1")
    assert "STALE" in stale.stdout, (
        "a mirror that no longer matches the main tree hides a promoted "
        "tool, and an absent tool gets forked")
    assert stale.returncode == 0, "stale is REPORTED, never a refusal"

    down = _ritual(env, "down", "lane1")
    assert down.returncode == 0, down.stdout + down.stderr
    assert not (main / ".claude" / "worktrees" / "lane1").exists()


def test_teardown_puts_back_the_tracked_shipped_patch(tmp_path):
    """`down` removes the lane-local ``Patches`` CLONE — and that clone
    contains a TRACKED file (``Patches/`` is gitignored as a whole, but
    ``Ortho4XP/Patches/+39-078/2W2_runways.patch.osm`` is force-added).
    Deleting it leaves a tracked deletion, ``git worktree remove`` then
    refuses "contains modified or untracked files", and the lane is left
    HALF torn down: mounts gone, worktree still registered.  Measured on a
    real lane 2026-08-06 (58 worktrees were lingering on this machine)."""
    main, _data, env, _old = _tiny_repo(tmp_path)
    shipped = ("Ortho4XP/Patches/+39-078/2W2_runways.patch.osm")
    up = _ritual(env, "up", "lane3", "HEAD")
    assert up.returncode == 0, up.stdout + up.stderr
    wt = main / ".claude" / "worktrees" / "lane3"
    assert (wt / shipped).is_file(), "the clone must carry the shipped patch"

    down = _ritual(env, "down", "lane3")
    assert down.returncode == 0, (
        f"teardown refused:\n{down.stdout}\n{down.stderr}")
    assert not wt.exists(), "the worktree is still registered after down"


def test_the_ritual_never_overwrites_a_tracked_index(tmp_path):
    """A lane PROMOTING a tool edits the tracked ``tools/INDEX.md`` in its
    own worktree — that edit is the deliverable.  The ritual must report
    the difference and leave the file alone."""
    main, _data, env, _old = _tiny_repo(tmp_path)
    up = _ritual(env, "up", "lane2", "HEAD")
    assert up.returncode == 0, up.stdout + up.stderr
    tracked = main / ".claude" / "worktrees" / "lane2" / "tools" / "INDEX.md"
    assert os.access(tracked, os.W_OK), (
        "a tracked index must stay writable — the lane's own promotion "
        "edits it")
    tracked.write_text("# Tool index\n\ncensus.py\nmy_new_tool.py\n")
    again = _ritual(env, "up", "lane2", "HEAD")
    assert again.returncode == 0, again.stdout + again.stderr
    assert "my_new_tool.py" in tracked.read_text(), (
        "the ritual overwrote a TRACKED index — that is a lane's promotion "
        "commit destroyed by its own setup script")
    assert "DIFFERS" in again.stdout


def test_the_ritual_accepts_an_existing_worktree_by_path(tmp_path):
    """Worktrees do not all live under $MAIN_REPO/.claude/worktrees —
    Claude Code chip sessions create theirs NESTED at
    <repo>/Ortho4XP/.claude/worktrees/<name>, and on 2026-08-27 a lane
    had to smuggle one into the ritual as a ../../ relative NAME.
    up/check/down now resolve NAME or PATH through ``git worktree list``
    (the registry both kinds live in), never a hard-coded parent dir.
    The known-answer twin: mount-into-existing by relative PATH, resolve
    the same nested tree by bare NAME, refuse a plain directory and the
    main repo itself, tear down by absolute PATH."""
    main, data, env, _old = _tiny_repo(tmp_path)
    chip = main / "Ortho4XP" / ".claude" / "worktrees" / "chip-lane"
    r = subprocess.run(
        ["git", "-C", str(main), "worktree", "add", "-q", str(chip),
         "HEAD"], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

    # `up` by RELATIVE PATH completes the ritual in the EXISTING worktree.
    up = _ritual(env, "up", os.path.relpath(chip, tmp_path), cwd=tmp_path)
    assert up.returncode == 0, up.stdout + up.stderr
    assert "build-ready on the SHARED corpus" in up.stdout
    assert os.path.realpath(chip / "Ortho4XP" / "OSM_data") == \
        os.path.realpath(data / "OSM_data"), (
        "the corpus was not mounted into the path-addressed worktree")

    # bare NAME resolves the SAME nested worktree via `git worktree list`
    # — not a fresh (missing) $WT_ROOT/chip-lane.
    chk = _ritual(env, "check", "chip-lane")
    assert chk.returncode == 0, chk.stdout + chk.stderr
    assert "no worktree at" not in chk.stderr

    # A directory git does not register is refused, loudly.
    plain = tmp_path / "plain"
    plain.mkdir()
    ref = _ritual(env, "check", str(plain))
    assert ref.returncode == 2
    assert "not a registered worktree" in ref.stderr

    # The main repo is never a lane.
    slf = _ritual(env, "check", str(main))
    assert slf.returncode == 2
    assert "MAIN repository" in slf.stderr

    # A REF makes no sense against an existing tree at its own checkout.
    wref = _ritual(env, "up", str(chip), "HEAD")
    assert wref.returncode == 2
    assert "PATH form" in wref.stderr

    # `down` by ABSOLUTE PATH removes the nested worktree.
    down = _ritual(env, "down", str(chip))
    assert down.returncode == 0, down.stdout + down.stderr
    assert not chip.exists()


# ══════════════════════════════════════════════════════════════════════
# §5 THE SHARED DATA REPO (owner ruling e9daef5)
# ══════════════════════════════════════════════════════════════════════

def _fake_lane(tmp_path, repo, dirs=("OSM_data", "Elevation_data")):
    """A lane tree whose data dirs are symlinks into ``repo``."""
    lane = tmp_path / "lane"
    lane.mkdir(exist_ok=True)
    for d in dirs:
        (repo / d).mkdir(parents=True, exist_ok=True)
        (lane / d).symlink_to(repo / d)
    return lane


def test_a_private_data_corpus_is_refused(build_mod, tmp_path, monkeypatch):
    """Two lanes on two corpora do not measure the same thing, and nothing
    in a build log says which corpus was used."""
    repo = tmp_path / "shared"
    monkeypatch.setattr(build_mod, "DATA_REPO", repo)
    lane = tmp_path / "private_lane"
    (lane / "OSM_data").mkdir(parents=True)          # a REAL dir, not a mount
    mounts = build_mod.data_mounts(lane)
    assert mounts["OSM_data"]["present"] and not mounts["OSM_data"]["shared"]
    with pytest.raises(SystemExit) as exc:
        build_mod.require_shared_data(mounts)
    assert "e9daef5" in str(exc.value) and "lane_worktree.sh" in str(exc.value)
    # ...and the override is explicit, never silent.
    build_mod.require_shared_data(mounts, allow_private=True)


def test_a_mounted_corpus_passes(build_mod, tmp_path, monkeypatch):
    repo = tmp_path / "shared"
    monkeypatch.setattr(build_mod, "DATA_REPO", repo)
    lane = _fake_lane(tmp_path, repo)
    mounts = build_mod.data_mounts(lane)
    assert mounts["OSM_data"]["shared"] and mounts["Elevation_data"]["shared"]
    build_mod.require_shared_data(mounts)


def test_every_refresh_scope_prefix_is_a_shared_data_dir(build_mod):
    """A scope pointing at a directory the harness does not snapshot would
    authorise writes it cannot see."""
    for scope, prefix, why in build_mod.REFRESH_SCOPES:
        top = prefix.split("/")[0]
        assert top in build_mod.SHARED_DATA_DIRS, (
            f"scope {scope!r} covers {prefix!r}, which is outside the "
            f"snapshotted data dirs — its writes would be invisible")
        assert why.strip(), f"scope {scope!r} has no explanation"


def test_the_road_feed_scope_is_the_named_precedent(build_mod):
    """The KCLT road-feed refresh ran as a tile-build side effect and
    silently changed campaign hashes.  It must be its OWN scope, matched
    before the general OSM one, so authorising an overpass download does
    not silently authorise a feed regeneration too."""
    order = [sc for sc, _p, _w in build_mod.REFRESH_SCOPES]
    assert order.index("osm_roadfeed") < order.index("osm_layers"), (
        "the road-feed prefix must be matched BEFORE the general OSM_data "
        "prefix, or every road-feed write is attributed to osm_layers")
    assert build_mod.scope_of(
        "OSM_data/_airport_road_feed/KCLT_road_feed.cache") == "osm_roadfeed"
    assert build_mod.scope_of("OSM_data/+30+030/x.osm.bz2") == "osm_layers"
    assert build_mod.scope_of("Patches/+30+031/x.osm") is None
    assert "KCLT" in build_mod.scope_description("osm_roadfeed")


def test_an_implicit_download_is_refused_and_names_its_scope(build_mod):
    """A build must never fetch into the shared repo as a side effect."""
    missing = [("dem", "Elevation_data/**/N30E031.hgt", "the base raster"),
               ("osm_layers", "OSM_data/**/+30+031_airports.osm.bz2",
                "the airports layer")]
    with pytest.raises(SystemExit) as exc:
        build_mod.require_no_implicit_refresh(missing, set())
    msg = str(exc.value)
    assert "e9daef5" in msg and "KCLT road-feed" in msg
    assert "--refresh-data dem,osm_layers" in msg, (
        "the refusal must hand back the exact flag that authorises it")
    # Authorised scopes pass through.
    build_mod.require_no_implicit_refresh(missing, {"dem", "osm_layers"})
    # A partially-authorised set still refuses the rest.
    with pytest.raises(SystemExit) as exc2:
        build_mod.require_no_implicit_refresh(missing, {"dem"})
    assert "--refresh-data osm_layers" in str(exc2.value)


def test_a_degraded_tier_inset_refuses_and_names_the_scope(
        build_mod, tmp_path, monkeypatch):
    """THE DEGRADED-TIER REFUSAL (owner RULINGS 2026-09-13b (2)).

    The engine now RE-PROBES a no-coverage negative that a run without
    the LERC decoder may have minted (1.0.324 minted exactly one for
    NEWZEALAND1M at NZQN).  That re-probe fetches and re-cuts an inset —
    a write into the shared data repo — so a harness build refuses it up
    front, says WHY (the inset is cut at a degraded tier), and names
    ``--refresh-data dem``.  The predicate is the ENGINE's own.
    """
    import O4_Airport_Elevation_Insets as INSETS

    state = {"tile_stem": "S46E168", "airport_insets": True}
    monkeypatch.setattr(
        INSETS, "unverified_capability_negatives",
        lambda lat, lon: [("NZQN", "NEWZEALAND1M", ["lerc"])])
    missing = build_mod.unverified_inset_negatives(state, -46, 168)
    assert len(missing) == 1
    (scope, artifact, why) = missing[0]
    assert scope == "dem"
    assert "S46E168_airport_insets/index.json" in artifact
    assert "NZQN:NEWZEALAND1M" in artifact
    assert "DEGRADED TIER" in why and "LERC" in why
    with pytest.raises(SystemExit) as exc:
        build_mod.require_no_implicit_refresh(missing, set())
    assert "--refresh-data dem" in str(exc.value)
    # Authorised, it passes — the explicit, locked, ledgered act.
    build_mod.require_no_implicit_refresh(missing, {"dem"})
    # A verified corpus refuses nothing.
    monkeypatch.setattr(
        INSETS, "unverified_capability_negatives", lambda lat, lon: [])
    assert build_mod.unverified_inset_negatives(state, -46, 168) == []


# ══════════════════════════════════════════════════════════════════════
# THE SCHEMA-STALE CACHED ROAD LAYER (RULINGS 2026-09-15r + u)
# ══════════════════════════════════════════════════════════════════════

def _write_schema_stamped_layer(path, schema):
    """A cached OSM layer in the shape ``OSM_layer.write_to_file`` emits —
    the marker the engine reads back lives on the ``<osm`` root tag."""
    import bz2
    path.parent.mkdir(parents=True, exist_ok=True)
    with bz2.open(str(path), "wt", encoding="utf-8") as handle:
        handle.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                     '<osm version="0.6" o4_tag_schema="%s">\n'
                     '</osm>\n' % schema)


def test_a_schema_stale_road_layer_refuses_and_names_osm_layers(
        build_mod, tmp_path, monkeypatch):
    """A cached road layer written under an OLD tag schema is a REFRESH.

    When ``ROAD_CACHE_TAG_SCHEMA`` moved "2026-07-16" → "2026-09-15"
    (RULINGS 2026-09-15r), the first guarded build afterwards rewrote
    ``+40-004_big_roads.osm.bz2`` mid-build (2,197,226 → 2,199,670 bytes)
    and the run was only marked CONTAMINATED afterwards (RULINGS
    2026-09-15u).  Under ruling e9daef5 that re-download is an explicit,
    locked, hash-stamped event — so it is named and refused UP FRONT.
    """
    import O4_File_Names as FNAMES
    import O4_Vector_Map as VMAP

    root = tmp_path / "lane"
    osm = root / "OSM_data"
    monkeypatch.setattr(FNAMES, "OSM_dir", str(osm))
    # road_level >= 2 so BOTH tile-wide road layers are in the engine's
    # own specification list (the list this check consumes).
    monkeypatch.setattr(VMAP, "resolved_road_level", lambda tile: (2, False))
    cache = Path(FNAMES.osm_cached(40, -4, "big_roads"))

    # 1. STALE: written under the previous schema.
    _write_schema_stamped_layer(cache, "2026-07-16")
    missing = build_mod.schema_stale_osm_layers(root, 40, -4)
    assert len(missing) == 1, missing
    scope, artifact, why = missing[0]
    assert scope == "osm_layers"
    assert artifact == "OSM_data/+40-010/+40-004/+40-004_big_roads.osm.bz2"
    assert "SCHEMA-STALE" in why
    assert "2026-07-16" in why and VMAP.ROAD_CACHE_TAG_SCHEMA in why, (
        "the refusal must name the schema on disk AND the one the engine "
        "wants — otherwise it cannot be acted on")
    with pytest.raises(SystemExit) as exc:
        build_mod.require_no_implicit_refresh(missing, set())
    assert "--refresh-data osm_layers" in str(exc.value)
    # Explicitly authorised, it passes: the locked, ledgered act.
    build_mod.require_no_implicit_refresh(missing, {"osm_layers"})
    # And it reaches the build's single pre-flight list, not just its own
    # function — the airport path and the --tile path share that call.
    monkeypatch.setattr(build_mod, "dem_cache_state", lambda *a: {
        "tile_stem": "N40W004", "base_raster": True, "airport_insets": True,
        "airports_layer": True})
    monkeypatch.setattr(build_mod, "unverified_inset_negatives",
                        lambda *a: [])
    assert build_mod.missing_shared_artifacts(root, 40, -4) == missing

    # 2. CURRENT: the engine's own schema — named by nothing.
    _write_schema_stamped_layer(cache, VMAP.ROAD_CACHE_TAG_SCHEMA)
    assert build_mod.schema_stale_osm_layers(root, 40, -4) == []

    # 3. ABSENT: absence is not staleness (the airports layer owns that
    #    refusal; an absent big_roads cache is lawful).
    cache.unlink()
    assert build_mod.schema_stale_osm_layers(root, 40, -4) == []


class _Notes:
    """A ``Progress`` stand-in: the refresh narrates through ``.note``."""

    def __init__(self):
        self.lines = []

    def note(self, msg):
        self.lines.append(msg)


def _osm_layer_fixture(tmp_path, monkeypatch, schema):
    """A tmp data root whose tile +40-004 holds one road layer stamped
    with ``schema``.  Returns ``(root, cache_path)``."""
    import O4_File_Names as FNAMES
    import O4_Vector_Map as VMAP

    root = tmp_path / "lane"
    monkeypatch.setattr(FNAMES, "OSM_dir", str(root / "OSM_data"))
    monkeypatch.setattr(VMAP, "resolved_road_level", lambda tile: (1, False))
    cache = Path(FNAMES.osm_cached(40, -4, "big_roads"))
    _write_schema_stamped_layer(cache, schema)
    return root, cache


def _mock_engine_fetch(monkeypatch, calls):
    """Stand in for the ENGINE's one download entry, at the engine's own
    function — ``O4_OSM_Utils.OSM_queries_to_OSM_layer``, which is what
    ``start_background_osm_prefetch``'s worker calls.  Writes a cache
    stamped with the schema it was asked for, exactly as the real one
    does, and records the call.  No network anywhere in this file."""
    import O4_File_Names as FNAMES
    import O4_OSM_Utils as OSM

    def _fetch(queries, layer, lat, lon, tags_of_interest,
               cached_suffix=None, node_tags_of_interest=None,
               cache_schema="", **kw):
        calls.append((cached_suffix, cache_schema))
        _write_schema_stamped_layer(
            Path(FNAMES.osm_cached(lat, lon, cached_suffix)), cache_schema)
        return 1

    monkeypatch.setattr(OSM, "OSM_queries_to_OSM_layer", _fetch)


def test_an_authorised_osm_refresh_RE_DERIVES_a_present_but_stale_layer(
        build_mod, tmp_path, monkeypatch):
    """THE VMMC GAP (measured 2026-09-15, owner-authorised run).

    ``build_airport.py VMMC --refresh-data osm_layers`` exited 0 in 23 s
    reporting "refresh scope 'osm_layers' was authorised but wrote
    NOTHING — the artifact was already present", and the next plain build
    REFUSED on the same schema-stale file: authorising the refresh was a
    no-op, because the engine's recycle path keeps a file that is
    PRESENT, and the airport path never starts the prefetch at all.  The
    refresh therefore gets its own derivation site — move the stale layer
    aside, let the ENGINE re-derive it, verify, and put it back if it did
    not.
    """
    import O4_Vector_Map as VMAP

    root, cache = _osm_layer_fixture(tmp_path, monkeypatch, "2026-07-16")
    stale_bytes = cache.read_bytes()
    calls = []
    _mock_engine_fetch(monkeypatch, calls)
    prog = _Notes()

    summary = build_mod.refresh_stale_osm_layers(root, 40, -4, prog)

    assert [c for c in calls if c[0] == "big_roads"] == [
        ("big_roads", VMAP.ROAD_CACHE_TAG_SCHEMA)], (
        "the ENGINE's fetch entry must be invoked exactly once for the "
        "stale layer, with the schema the engine now wants")
    assert summary["refetched"] == [
        "OSM_data/+40-010/+40-004/+40-004_big_roads.osm.bz2"]
    assert cache.read_bytes() != stale_bytes, "the layer was re-derived"
    assert list(cache.parent.glob("*.stale-*")) == [], (
        "the moved-aside copy must not be left behind as corpus litter")
    assert any("moved aside" in line for line in prog.lines)

    # THE POINT: the plain build that refused now passes its pre-flight.
    monkeypatch.setattr(build_mod, "dem_cache_state", lambda *a: {
        "tile_stem": "N40W004", "base_raster": True, "airport_insets": True,
        "airports_layer": True})
    monkeypatch.setattr(build_mod, "unverified_inset_negatives",
                        lambda *a: [])
    assert build_mod.missing_shared_artifacts(root, 40, -4) == []
    build_mod.require_no_implicit_refresh(
        build_mod.missing_shared_artifacts(root, 40, -4), set())


def test_a_current_schema_layer_is_not_touched_by_the_refresh(
        build_mod, tmp_path, monkeypatch):
    """A refresh re-derives what is STALE and nothing else — the corpus is
    not re-downloaded because a flag was passed."""
    import O4_Vector_Map as VMAP

    root, cache = _osm_layer_fixture(
        tmp_path, monkeypatch, VMAP.ROAD_CACHE_TAG_SCHEMA)
    before = cache.read_bytes()
    calls = []
    _mock_engine_fetch(monkeypatch, calls)

    summary = build_mod.refresh_stale_osm_layers(root, 40, -4, _Notes())
    assert summary["refetched"] == [] and calls == []
    assert cache.read_bytes() == before


def test_an_UNAUTHORISED_run_refuses_and_leaves_the_stale_layer_untouched(
        build_mod, tmp_path, monkeypatch):
    """Without ``--refresh-data osm_layers`` nothing is moved, nothing is
    fetched, and the build refuses — the refresh is the ONLY thing that
    may re-derive a shared artifact (ruling e9daef5)."""
    root, cache = _osm_layer_fixture(tmp_path, monkeypatch, "2026-07-16")
    before = cache.read_bytes()
    calls = []
    _mock_engine_fetch(monkeypatch, calls)

    missing = build_mod.schema_stale_osm_layers(root, 40, -4)
    with pytest.raises(SystemExit) as exc:
        build_mod.require_no_implicit_refresh(missing, set())
    assert "--refresh-data osm_layers" in str(exc.value)
    assert calls == [], "an unauthorised run must fetch NOTHING"
    assert cache.read_bytes() == before
    assert list(cache.parent.glob("*.stale-*")) == []


def test_a_refresh_that_re_derived_NOTHING_refuses_and_restores(
        build_mod, tmp_path, monkeypatch):
    """The VMMC failure mode must never exit 0 again.

    When the engine's pass brings no schema-current layer back (Overpass
    unreachable, no covering extract), the stale cache is put back —
    leaving the corpus exactly as it was, rather than trading a stale
    artifact for an ABSENT one — and the run refuses.
    """
    import O4_OSM_Utils as OSM

    root, cache = _osm_layer_fixture(tmp_path, monkeypatch, "2026-07-16")
    before = cache.read_bytes()
    monkeypatch.setattr(OSM, "OSM_queries_to_OSM_layer",
                        lambda *a, **kw: 0)          # every fetch fails

    with pytest.raises(SystemExit) as exc:
        build_mod.refresh_stale_osm_layers(root, 40, -4, _Notes())
    assert "re-derived NOTHING" in str(exc.value)
    assert "+40-004_big_roads.osm.bz2" in str(exc.value)
    assert cache.read_bytes() == before, "the stale cache must be restored"
    assert list(cache.parent.glob("*.stale-*")) == []


def test_the_write_guard_REFUSES_a_bz2_layer_write(build_mod, tmp_path):
    """THE bz2 HOLE (measured 2026-09-15).

    ``bz2`` binds ``builtins.open`` at IMPORT time, so patching
    ``builtins.open`` alone left every ``.osm.bz2`` cache write —
    i.e. the whole ``osm_layers`` scope — invisible to the preventer.
    Measured before the fix: this write completed with ``blocked == []``.
    """
    import bz2

    repo = tmp_path / "repo"
    (repo / "OSM_data" / "+40-010" / "+40-004").mkdir(parents=True)
    lane = tmp_path / "lane"
    lane.mkdir()
    target = (repo / "OSM_data" / "+40-010" / "+40-004"
              / "+40-004_big_roads.osm.bz2")
    before = bz2._builtin_open

    with pytest.raises(build_mod.SharedRepoWriteBlocked) as exc:
        with build_mod.SharedRepoWriteGuard(set(), lane, repo=repo):
            with bz2.open(str(target), "wt", encoding="utf-8") as handle:
                handle.write("<osm/>")
    assert "+40-004_big_roads.osm.bz2" in str(exc.value)
    assert "osm_layers" in str(exc.value)
    assert not target.exists(), "the guard must PREVENT, not just report"
    assert bz2._builtin_open is before, (
        "the guard must restore bz2's captured open on exit")

    # Authorised, the same write proceeds — the refresh this flag exists
    # to carry.
    with build_mod.SharedRepoWriteGuard({"osm_layers"}, lane, repo=repo):
        with bz2.open(str(target), "wt", encoding="utf-8") as handle:
            handle.write("<osm/>")
    with bz2.open(str(target), "rt", encoding="utf-8") as handle:
        assert handle.read() == "<osm/>"
    assert bz2._builtin_open is before


def test_the_snapshot_sees_every_write(build_mod, guard_mod, tmp_path,
                                       monkeypatch):
    """The audit's guarantee is 'this build wrote NOTHING into the shared
    repo'.  A sampled snapshot cannot make that claim, so the walk is
    full — ~2.7 k files, ~10 ms."""
    repo = tmp_path / "shared"
    monkeypatch.setattr(build_mod, "DATA_REPO", repo)
    monkeypatch.setattr(guard_mod, "DATA_REPO", repo)
    deep = repo / "OSM_data" / "a" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    (deep / "keep.txt").write_text("x")
    before = build_mod.shared_repo_snapshot(repo)
    (deep / "written_by_the_build.cache").write_text("new")
    (deep / "keep.txt").write_text("CHANGED")
    changes = build_mod.snapshot_diff(before,
                                      build_mod.shared_repo_snapshot(repo))
    assert changes["added"] == ["OSM_data/a/b/c/d/written_by_the_build.cache"]
    assert changes["modified"] == ["OSM_data/a/b/c/d/keep.txt"]


def test_an_unauthorised_write_is_reported_and_contaminates_the_run(
        build_mod, tmp_path):
    notes = []

    class _P:
        def note(self, m):
            notes.append(m)

    changes = {"added": ["OSM_data/_airport_road_feed/KCLT_road_feed.cache"],
               "modified": [], "removed": []}
    offenders = build_mod.report_unauthorised_writes(changes, set(), _P())
    assert offenders and offenders[0]["scope"] == "osm_roadfeed"
    blob = "\n".join(notes)
    assert "CONTAMINATED" in blob and "e9daef5" in blob
    assert "--refresh-data osm_roadfeed" in blob
    # Authorised: silent about violations, because there is none.
    notes.clear()
    assert build_mod.report_unauthorised_writes(
        changes, {"osm_roadfeed"}, _P()) == []


def test_a_clean_build_is_reported_as_leaving_the_repo_untouched(build_mod):
    notes = []

    class _P:
        def note(self, m):
            notes.append(m)
    empty = {"added": [], "modified": [], "removed": []}
    assert build_mod.report_unauthorised_writes(empty, set(), _P()) == []
    assert "UNCHANGED" in notes[0]


def test_the_refresh_lock_refuses_and_reports_never_blocks(build_mod,
                                                           guard_mod,
                                                           tmp_path,
                                                           monkeypatch):
    """Ruling §3: concurrent lanes never race a regeneration.  Blocking is
    not the answer either — a lane waiting on another lane's download is
    indistinguishable from a hung build."""
    monkeypatch.setattr(guard_mod, "LOCK_DIR", tmp_path / "locks")
    first = build_mod.RefreshLock("dem", lane="lane-A").acquire()
    try:
        with pytest.raises(SystemExit) as exc:
            build_mod.RefreshLock("dem", lane="lane-B").acquire()
        msg = str(exc.value)
        assert "lane-A" in msg and "ALIVE" in msg
        assert "never blocks silently" in msg
        # A different scope is independent.
        other = build_mod.RefreshLock("osm_layers", lane="lane-B").acquire()
        other.release()
    finally:
        first.release()
    # Released: the next lane gets it.
    build_mod.RefreshLock("dem", lane="lane-C").acquire().release()


def test_a_stale_lock_is_reported_and_never_broken_automatically(
        build_mod, guard_mod, tmp_path, monkeypatch):
    """A dead pid does NOT mean the write completed — the cache may be
    half-written, which is worse than no cache."""
    monkeypatch.setattr(guard_mod, "LOCK_DIR", tmp_path / "locks")
    (tmp_path / "locks").mkdir()
    (tmp_path / "locks" / "dem.lock").write_text(json.dumps(
        {"scope": "dem", "lane": "dead-lane", "pid": 2 ** 22,
         "host": "h", "started": "2026-08-05T01:47:00"}))
    with pytest.raises(SystemExit) as exc:
        build_mod.RefreshLock("dem", lane="me").acquire()
    msg = str(exc.value)
    assert "stale lock" in msg and "--break-stale-lock" in msg
    assert "does not mean the write COMPLETED" in msg
    lock = build_mod.RefreshLock("dem", lane="me", break_stale=True).acquire()
    lock.release()


def test_a_refresh_is_hash_stamped_into_the_shared_ledger(build_mod,
                                                          guard_mod,
                                                          tmp_path,
                                                          monkeypatch):
    """"Exactly once, as an explicit logged event" needs a record that
    outlives the session, in the SHARED repo where the next lane will
    look."""
    repo = tmp_path / "shared"
    (repo / "Elevation_data").mkdir(parents=True)
    (repo / "Elevation_data" / "N30E031.hgt").write_text("raster")
    ledger = repo / ".harness" / "refresh_ledger.jsonl"
    monkeypatch.setattr(guard_mod, "DATA_REPO", repo)
    monkeypatch.setattr(guard_mod, "REFRESH_LEDGER", ledger)
    rec = build_mod.record_refresh(
        "dem", {"added": ["Elevation_data/N30E031.hgt"], "modified": [],
                "removed": []},
        {"lane": "L", "tag": "T"}, repo=repo)
    assert rec["scope"] == "dem" and rec["added"] == 1
    stamp = rec["files"][0]
    assert stamp["sha256"] == hashlib.sha256(b"raster").hexdigest()
    assert stamp["size"] == 6
    on_disk = json.loads(ledger.read_text().strip())
    assert on_disk["lane"] == "L" and on_disk["files"][0]["sha256"] == \
        stamp["sha256"]


def test_the_data_mounts_are_recorded_on_every_build(build_mod):
    """Which corpus a build used must be readable from its artifacts —
    otherwise the question is unanswerable a day later."""
    src = Path(inspect.getfile(build_mod)).read_text()
    assert '"data_mounts": mounts' in src
    assert '"shared_repo_writes"' in src and '"contaminated"' in src


def test_the_audit_runs_even_when_the_build_raises(build_mod):
    """A build that died half-way through a download has still mutated the
    shared repo — and that is exactly when nobody thinks to look."""
    src = inspect.getsource(build_mod.main)
    body = src[src.index("locks = ["):]
    assert "finally:" in body, (
        "the shared-repo write audit must run in a finally: block")
    assert body.index("finally:") < body.index(
        "report_unauthorised_writes"), (
        "the audit must be INSIDE the finally, not after the try")


# ══════════════════════════════════════════════════════════════════════
# §6 THE INDEX IS THE CONSULTATION SURFACE
# ══════════════════════════════════════════════════════════════════════

INDEX = ROOT.parent / "tools" / "INDEX.md"


def test_every_harness_entry_is_in_the_tool_index():
    """Owner ruling (RULINGS 7e90032, consult-before-create): a tool absent
    from the index is treated as absent, and every new tool lands WITH its
    index entry in the same commit."""
    assert INDEX.exists(), "tools/INDEX.md is missing"
    text = INDEX.read_text()
    for entry in sorted(p.name for p in HARNESS.iterdir()
                        if p.suffix in (".py", ".sh")):
        assert entry in text, (
            f"tools/harness/{entry} is not listed in tools/INDEX.md — "
            f"a tool absent from the index is treated as absent")


# ══════════════════════════════════════════════════════════════════════
# §6 THE AUTHORSHIP TRACER — who_wrote.py
# ══════════════════════════════════════════════════════════════════════
# The tool that attributed the constant-DEM oracle's "DEM as a hard
# authority" class to a named pass.  Its two load-bearing pieces are pure
# functions over a write history, so they are testable without a build —
# which is the point: the expensive half is the build, the half that can be
# WRONG is the bookkeeping.

WHO = _load("who_wrote", HARNESS / "who_wrote.py")


class TestIntroducingWrite:
    """``introducing_write`` must name the AUTHOR, not the last carrier.

    Every value in this repo is rewritten several times after it is
    authored (the final projection's writeback rewrites almost everything).
    Reporting the last writer names the carrier and hides the pass that
    actually put the value there — the mistake this function exists to
    avoid.
    """

    def test_empty_history_has_no_author(self):
        assert WHO.introducing_write([]) is None

    def test_the_author_is_the_first_write_after_the_last_clean_one(self):
        history = [
            (0, 10, "solve.py:1:solved_clean"),
            (4, 10, "groundside.py:2:THE_AUTHOR"),
            (4, 10, "emit_decimate.py:3:carrier"),
            (4, 10, "solve.py:4:projection_carrier"),
        ]
        assert WHO.introducing_write(history)[2] == "groundside.py:2:THE_AUTHOR"

    def test_a_value_reintroduced_after_a_clean_write_reattributes(self):
        """A pass that CLEARS the condition and a later pass that brings it
        back: the author is the later one, not the first ever."""
        history = [
            (3, 9, "a.py:1:early"),
            (0, 9, "b.py:2:cleaned_it"),
            (2, 9, "c.py:3:BROUGHT_IT_BACK"),
            (2, 9, "d.py:4:carrier"),
        ]
        assert WHO.introducing_write(history)[2] == "c.py:3:BROUGHT_IT_BACK"

    def test_never_clean_falls_back_to_the_first_write(self):
        history = [(1, 4, "a.py:1:first"), (1, 4, "b.py:2:later")]
        assert WHO.introducing_write(history)[2] == "a.py:1:first"


class TestAuthorshipProbe:
    """The probe must RECORD without changing the value, and must put the
    field back — an instrument that mutates its subject is not one."""

    def _shape_cls(self):
        class _Shape:
            node_altitudes = None

            def __init__(self, role="apron"):
                self.role = role
                self.ref = ""
                self.polygon = None
                self.node_altitudes = None
        return _Shape

    def test_it_records_every_write_and_returns_the_value_unchanged(self):
        cls = self._shape_cls()
        probe = WHO.AuthorshipProbe(cls, dem_m=1.0).install()
        try:
            s = cls()
            s.node_altitudes = [5.0, 5.0, 5.0]
            s.node_altitudes = [1.0, 5.0, 1.0]
            assert list(s.node_altitudes) == [1.0, 5.0, 1.0]
        finally:
            probe.uninstall()
        history = probe.by_shape[id(s)]
        assert [h[0] for h in history] == [0, 2], (
            "the probe must count DEM-matching values per write")

    def test_uninstall_restores_the_field(self):
        cls = self._shape_cls()
        probe = WHO.AuthorshipProbe(cls, dem_m=1.0).install()
        assert isinstance(cls.__dict__["node_altitudes"], property)
        probe.uninstall()
        assert not isinstance(cls.__dict__.get("node_altitudes"), property)

    def test_the_role_filter_scopes_recording(self):
        cls = self._shape_cls()
        probe = WHO.AuthorshipProbe(cls, dem_m=1.0,
                                    roles=["service_junction"]).install()
        try:
            keep, drop = cls("service_junction"), cls("apron")
            keep.node_altitudes = [1.0]
            drop.node_altitudes = [1.0]
        finally:
            probe.uninstall()
        assert id(keep) in probe.by_shape
        assert id(drop) not in probe.by_shape


class TestFootprintProbe:
    """The FOOTPRINT history — ``who_wrote.py --footprint``.

    The value tracer cannot answer "which pass put pavement over this
    spot": a point outside every shape has no vertex to trace, and the
    absorb / merge / re-role family writes a POLYGON, never an altitude.
    This probe is that reader, and the three things that can be wrong in
    it are bookkeeping, not geometry: it must not mutate its subject, it
    must report TRANSITIONS (not every write), and it must not confuse a
    ``dataclasses.replace`` re-minting with a pass that grew a footprint.
    """

    def _shape_cls(self):
        class _Shape:
            def __init__(self, role="apron", polygon=None):
                self.role = role
                self.ref = ""
                self.polygon = polygon
        return _Shape

    @staticmethod
    def _sq(n):
        from shapely.geometry import Polygon
        return Polygon([(0, 0), (n, 0), (n, n), (0, n)])

    def test_it_records_transitions_and_leaves_the_ring_unchanged(self):
        cls = self._shape_cls()
        probe = WHO.FootprintProbe(cls, [(5.0, 5.0)]).install()
        try:
            s = cls(polygon=self._sq(1))       # birth, OUT
            s.polygon = self._sq(1)            # unchanged — NOT a transition
            s.polygon = self._sq(10)           # grew IN
            s.polygon = self._sq(20)           # still in — NOT a transition
            s.polygon = self._sq(1)            # shrank OUT
            assert s.polygon.area == 1.0, "the probe must not touch the ring"
        finally:
            probe.uninstall()
        rows = probe.rows["5.0,5.0"]
        assert [(r["event"], r["covered"]) for r in rows] == [
            ("grew", True), ("shrank", False)], (
            "only the writes that CHANGED coverage are rows; a birth "
            "outside the point is not one")
        assert rows[0]["area_m2"] == 100.0 and rows[0]["role"] == "apron"

    def test_a_birth_that_already_covers_is_labelled_birth(self):
        """``dataclasses.replace`` mints a new instance for an unchanged
        ring all over this pipeline.  A reader that called that "grew"
        would name the copier as the pass that put pavement there."""
        cls = self._shape_cls()
        probe = WHO.FootprintProbe(cls, [(5.0, 5.0)]).install()
        try:
            cls(polygon=self._sq(10))
        finally:
            probe.uninstall()
        rows = probe.rows["5.0,5.0"]
        assert len(rows) == 1 and rows[0]["event"] == "birth"
        assert rows[0]["covered"] is True

    def test_two_instances_keep_separate_histories(self):
        cls = self._shape_cls()
        probe = WHO.FootprintProbe(cls, [(5.0, 5.0)]).install()
        try:
            a = cls("apron", self._sq(10))              # birth IN
            b = cls("groundside_pavement", self._sq(1))  # birth OUT
            b.polygon = self._sq(10)                     # grew IN
            del a
        finally:
            probe.uninstall()
        rows = probe.rows["5.0,5.0"]
        assert [r["role"] for r in rows] == [
            "apron", "groundside_pavement"]
        assert len({r["instance"] for r in rows}) == 2, (
            "instances are tracked by object identity, never by a "
            "coordinate join")

    def test_uninstall_restores_the_field(self):
        cls = self._shape_cls()
        probe = WHO.FootprintProbe(cls, [(0.0, 0.0)]).install()
        assert isinstance(cls.__dict__["polygon"], property)
        probe.uninstall()
        assert not isinstance(cls.__dict__.get("polygon"), property)

    def test_it_records_on_the_REAL_unhashable_BuiltShape(self):
        """THE REGRESSION THIS CLASS EXISTS FOR.

        ``BuiltShape`` is a plain ``@dataclass``, so Python sets
        ``__hash__ = None``.  A ``WeakKeyDictionary``-keyed probe raises
        ``TypeError`` on every single write — inside the "instrumentation
        never breaks a build" guard, which turns it into an instrument
        that records NOTHING and says so nowhere (measured: a whole HECA
        build, zero rows).  A hand-rolled hashable stand-in cannot catch
        that, so this twin uses the engine's own class.
        """
        from shapely.geometry import Polygon        # noqa: PLC0415
        BuiltShape = pytest.importorskip(
            "auto_patch.layout", reason="engine src not importable").BuiltShape
        assert BuiltShape.__hash__ is None, (
            "the trap this test guards is dataclass unhashability; if "
            "BuiltShape became hashable, re-derive the probe's keying")
        probe = WHO.FootprintProbe(BuiltShape, [(5.0, 5.0)]).install()
        try:
            s = BuiltShape(polygon=self._sq(1), role="apron")
            s.polygon = self._sq(10)
            assert s.polygon.area == 100.0
        finally:
            probe.uninstall()
        assert probe.rows["5.0,5.0"], (
            "the probe recorded NOTHING on the class it exists to "
            "instrument")
        assert probe.rows["5.0,5.0"][-1]["event"] == "grew"
        assert isinstance(Polygon, type)

    def test_a_reused_object_id_is_not_joined_to_the_dead_shape(self):
        """Ids ARE reused within one build.  A bare ``id()`` map would
        continue a dead shape's coverage state into an unrelated new
        one — the join error that makes an attribution wrong rather
        than missing."""
        cls = self._shape_cls()
        probe = WHO.FootprintProbe(cls, [(5.0, 5.0)]).install()
        try:
            a = cls("apron", self._sq(10))          # birth IN
            key = id(a)
            probe._state[key][0] = lambda: None     # simulate a dead referent
            b = cls("groundside_pavement", self._sq(10))
            probe._state[key] = probe._state.pop(key)
            # force the id collision the guard must survive
            probe._record(b, self._sq(10))
            del a, b
        finally:
            probe.uninstall()
        rows = probe.rows["5.0,5.0"]
        assert rows[0]["role"] == "apron"
        assert any(r["role"] == "groundside_pavement" and r["event"] == "birth"
                   for r in rows), (
            "a stale id entry must yield a FRESH instance, never a "
            "continuation of the dead shape's state")

    def test_no_probe_point_records_nothing(self):
        cls = self._shape_cls()
        probe = WHO.FootprintProbe(cls, []).install()
        try:
            cls(polygon=self._sq(10))
        finally:
            probe.uninstall()
        assert probe.rows == {} and probe._step == 0

    def test_the_final_section_reads_the_layout_by_shape_index(self):
        """``final`` is the emitted answer the change list has to end at,
        and its index IS the ``shapeID`` tag ``layout.to_osm`` writes."""
        cls = self._shape_cls()
        probe = WHO.FootprintProbe(cls, [(5.0, 5.0)])
        layout = types.SimpleNamespace(shapes=[cls("apron", self._sq(1)),
                                              cls("apron", self._sq(10))])
        hist = probe.footprint_history(layout)
        assert hist["5.0,5.0"]["final"] == [
            {"shapeID": 1, "role": "apron", "ref": "", "area_m2": 100.0}]


class TestAuthorMoveDump:
    """``--author-dump`` must carry the JOIN KEYS the aggregate cannot.

    The printed displacement census keeps 40 worst rows.  The question
    "are the vertices this pass re-authors the SAME vertices some other
    writer seeded from the DEM" is a per-vertex join, so the dump must
    carry the moving write's FULL site, the vertex's origin writer, and
    its DEM-origin writer — and must never change the classification the
    aggregate reports (one instrument, one population).
    """

    class _Shape:
        node_altitudes = None

        def __init__(self, role="apron"):
            self.role = role
            self.ref = ""
            self.polygon = None
            self.node_altitudes = None

    #: the three writes' call sites, in order — the probe reads them
    #: through ``call_site``, which filters to engine frames and so
    #: reports "" under pytest.
    SITES = ["seeder.py:1:the_dem_seeder",
             "solve.py:2:the_solve",
             "finalize.py:3:mover_writeback"]

    def _run(self, dump):
        real = WHO.call_site
        seq = iter(self.SITES)
        WHO.call_site = lambda *a, **k: next(seq, self.SITES[-1])
        try:
            probe = WHO.AuthorshipProbe(
                self._Shape, dem_m=1.0, authors=("mover",),
                solve_site="the_solve", dump_moves=dump).install()
            try:
                s = self._Shape()
                # the DEM seeder, then the solve, then the second author
                s.node_altitudes = [1.0, 1.0]      # seeded ON the DEM
                s.node_altitudes = [10.0, 20.0]    # <- "the_solve" writes
                s.node_altitudes = [10.0, 25.0]    # <- "mover" moves one
            finally:
                probe.uninstall()
        finally:
            WHO.call_site = real
        return probe, s

    def test_the_dump_records_the_moving_site_and_both_origins(self, tmp_path):
        probe, s = self._run(True)
        layout = types.SimpleNamespace(shapes=[s])
        out = tmp_path / "moves.jsonl"
        info = probe.write_move_dump(layout, out)
        recs = [json.loads(l) for l in out.read_text().splitlines()]
        moves = [r for r in recs if r["kind"] == "move"]
        assert info["moves"] == len(moves) == 1
        m = moves[0]
        assert m["k"] == 1 and m["before"] == 20.0 and m["after"] == 25.0
        assert m["class"] == "untouched", (
            "the solve wrote it and nothing else touched it — this is the "
            "second-author class")
        assert m["site"] == self.SITES[2], "the FULL moving site is carried"
        assert m["origin"] == self.SITES[0], "the vertex's origin writer"
        assert m["dem_origin"] == self.SITES[0], (
            "the vertex sat on the constant DEM at its first write — the "
            "DEM-origin writer is the overlay's join key")
        shapes = [r for r in recs if r["kind"] == "shape"]
        assert len(shapes) == 1 and shapes[0]["shape_index"] == 0
        assert shapes[0]["sites"] == self.SITES

    def test_the_dump_does_not_change_the_aggregate(self):
        off, _ = self._run(False)
        on, _ = self._run(True)
        assert off.author_report()[1] == on.author_report()[1] != {}, (
            "the per-vertex dump is a second READER of one population, "
            "never a second instrument")

    def test_the_aggregate_reports_the_hand_computed_displacement(self):
        """The PRINTED displacement census had no known-answer twin at
        all — only the dump did.  Known answer for the three writes
        above: the mover changes index 1 from 20.0 to 25.0, |d| = 5.0 m,
        and index 0 does not move (0.0 < the 0.01 m materiality)."""
        probe, _ = self._run(False)
        rows, totals = probe.author_report()
        assert rows == [{"author": "mover", "class": "untouched",
                         "role": "apron", "n_moved": 1,
                         "max_m": 5.0, "p50_m": 5.0}]
        assert totals == {("mover", "untouched"):
                          {"n_moved": 1, "max_m": 5.0}}


class TestDemAuthorshipCensus:
    """The IN-MEMORY half of the DEM census — ``dem_authorship``.

    It had no known-answer twin: only ``introducing_write`` (the pure
    function it calls) did, so the per-shape row assembly around it — the
    role, the counts, the filter that drops shapes with no on-DEM vertex —
    was untested.
    """

    class _Shape:
        node_altitudes = None

        def __init__(self, role="apron", ref=""):
            self.role = role
            self.ref = ref
            self.polygon = None
            self.node_altitudes = None

    SITES = ["seed.py:1:THE_SEEDER",
             "solve.py:2:cleaned_it",
             "ground.py:3:THE_AUTHOR",
             "final.py:4:carrier"]

    def _probe(self):
        real = WHO.call_site
        seq = iter(self.SITES)
        WHO.call_site = lambda *a, **k: next(seq, self.SITES[-1])
        try:
            probe = WHO.AuthorshipProbe(self._Shape, dem_m=1.0).install()
            try:
                on = self._Shape("service_junction", "SJ")
                on.node_altitudes = [1.0, 9.0]     # seeded: 1 on the DEM
                on.node_altitudes = [8.0, 9.0]     # cleaned: 0 on the DEM
                on.node_altitudes = [1.0, 1.0]     # THE AUTHOR: 2 back on
                on.node_altitudes = [1.0, 1.0]     # a carrier
                off = self._Shape("apron", "AP")
                off.node_altitudes = [7.0, 7.0]    # never on the DEM
            finally:
                probe.uninstall()
        finally:
            WHO.call_site = real
        return probe, on, off

    def test_rows_name_the_author_and_drop_shapes_with_no_on_dem_vertex(self):
        probe, on, off = self._probe()
        layout = types.SimpleNamespace(shapes=[on, off])
        rows, by_author = probe.dem_authorship(layout)
        assert len(rows) == 1, "the apron never sits on the DEM"
        r = rows[0]
        assert (r["shape"], r["role"], r["ref"]) == (0, "service_junction",
                                                     "SJ")
        assert (r["on_dem"], r["n"], r["writes"]) == (2, 2, 4)
        assert r["introduced_by"] == self.SITES[2], (
            "the first write after the last write with a zero count — not "
            "the carrier that wrote the same values afterwards")
        assert by_author == {("service_junction", self.SITES[2]): 2}

    def test_the_shape_key_is_the_layout_index_the_emitted_tag_carries(self):
        """``shape`` is the index in ``layout.shapes``, which is what
        ``layout.to_osm`` writes as the way's ``shapeID`` — the emitted
        join key.  A row keyed on anything else joins to nothing."""
        probe, on, off = self._probe()
        layout = types.SimpleNamespace(shapes=[off, on])
        rows, _ = probe.dem_authorship(layout)
        assert rows[0]["shape"] == 1


class TestNodeHistory:
    """``--at X,Y`` — the mode with no twin at all.

    It is the instrument that diffs two constant-DEM worlds write by
    write, so a compression bug there silently deletes the very step the
    two worlds first disagree at.
    """

    class _Shape:
        node_altitudes = None

        def __init__(self, ring, role="apron", ref="R"):
            from shapely.geometry import Polygon
            self.role = role
            self.ref = ref
            self.polygon = Polygon(ring)
            self.node_altitudes = None

    def _history(self):
        probe = WHO.AuthorshipProbe(self._Shape, dem_m=None,
                                    at=[(10.0, 0.0)], tol=0.05).install()
        try:
            s = self._Shape([(0, 0), (10, 0), (10, 10)])
            # ring = [(0,0), (10,0), (10,10), (0,0)] — the traced point is
            # ring index 1, so the history is that index's value stream.
            s.node_altitudes = [1.0, 2.0, 3.0, 1.0]
            s.node_altitudes = [1.0, 2.0, 4.0, 1.0]   # index 1 UNCHANGED
            s.node_altitudes = [1.0, 9.0, 4.0, 1.0]
        finally:
            probe.uninstall()
        return probe.node_history()

    def test_it_reports_only_the_changes_at_the_traced_coordinate(self):
        hist = self._history()
        assert list(hist) == ["10.0,0.0"]
        changes = hist["10.0,0.0"]
        assert [c["value"] for c in changes] == [2.0, 9.0], (
            "the middle write left ring index 1 at 2.0 and must compress "
            "out; only the two CHANGES are the history")
        assert [c["step"] for c in changes] == [2, 4], (
            "``step`` is the ordinal of EVERY assignment the probe saw, "
            "the dataclass field's own ``= None`` included (step 1 here) "
            "— so a gap in the printed steps is a compressed-out write OR "
            "a None write, and the number is not an index into the values")
        assert all(c["role"] == "apron" and c["ref"] == "R"
                   for c in changes)

    def test_a_coordinate_outside_the_tolerance_records_nothing(self):
        probe = WHO.AuthorshipProbe(self._Shape, dem_m=None,
                                    at=[(10.0, 1.0)], tol=0.05).install()
        try:
            s = self._Shape([(0, 0), (10, 0), (10, 10)])
            s.node_altitudes = [1.0, 2.0, 3.0, 1.0]
        finally:
            probe.uninstall()
        assert probe.node_history() == {"10.0,1.0": []}


def test_who_wrote_builds_through_the_harness_entry_only():
    """It must not grow a private build: the whole point of a lane tool
    living in tools/harness is that it inherits the entry's refusals."""
    src = (HARNESS / "who_wrote.py").read_text()
    assert "HB.build_patch(" in src
    assert "build_airport_pavement(" not in src, (
        "who_wrote.py must build through tools/harness/build_airport.py, "
        "never by calling the pipeline directly")


def test_the_probe_values_survive_uninstall():
    """The report is taken AFTER the build, and uninstall happens in the
    build's ``finally``.  A probe that parks values in a private alias
    reports zero findings once the field is restored — measured: an
    authorship census that should have named 291 vertices printed 0."""
    class _Shape:
        node_altitudes = None

        def __init__(self):
            self.role = "apron"
            self.ref = ""
            self.polygon = None
            self.node_altitudes = None

    probe = WHO.AuthorshipProbe(_Shape, dem_m=1.0).install()
    s = _Shape()
    s.node_altitudes = [1.0, 2.0]
    probe.uninstall()
    assert list(s.node_altitudes) == [1.0, 2.0], (
        "values written through the probe must survive uninstall")

# §5 THE ACCEPTANCE GATE READS THE SAME LAW
# ══════════════════════════════════════════════════════════════════════
# ``tests/test_pavement_grade.py`` IS the acceptance gate (docs/RULINGS.md
# "absolute-zero acceptance": app builds require zero adjudicated law
# violations on the battery airports).  A gate that assembles its own law
# frame is the census-wrapper defect wearing a different hat — and it had
# already drifted exactly the same way.

#: EVERY test module that counts law violations against a built patch.
#: Each must reach the law through ``check_grade``'s single reader; a
#: private assembler in ANY of them is the census-wrapper defect, and the
#: guard was armed on only the first one while the second carried a live
#: instance of it (``_law_true_rows`` hand-built the kwargs and dropped
#: ``fan_ramp_zones_ll``, so declared fan-ramp zones were judged as
#: violations).
GUARDED_LAW_READERS = ("test_pavement_grade.py", "test_constant_dem_oracle.py")


def _grade_gate_src(name: str = "test_pavement_grade.py") -> str:
    return (Path(__file__).parent / name).read_text()


def _sidecar_law_kwargs() -> tuple:
    """The law keywords ``law_context_from_sidecar`` assembles, read from
    its source — so a NEW sidecar law key enrols in this guard the moment
    the single reader learns it, with no second list to maintain here."""
    src = inspect.getsource(
        _load("harness_twin_check_grade",
              ROOT / "tools" / "check_grade.py").law_context_from_sidecar)
    keys = set(re.findall(r'ctx\["(\w+_ll)"\]', src))
    assert "terrace_joints_ll" in keys and "fan_ramp_zones_ll" in keys, (
        f"the sidecar law-keyword scrape found {sorted(keys)} — "
        f"law_context_from_sidecar no longer assigns ctx[...] by literal, "
        f"so this guard is reading nothing")
    return tuple(sorted(keys))


@pytest.mark.parametrize("module", GUARDED_LAW_READERS)
def test_the_acceptance_gate_reads_the_one_law_frame(module):
    """The gate hand-mirrored ``_write_axes_sidecar``'s payload out of the
    layout — sixty lines of axes, anchor, seam pins, mesh, crown field,
    pair caps and terrace joints.  It never passed ``ruleset``, so KCLT
    built under FAA law was judged under ICAO.  One reader now.

    ``test_constant_dem_oracle.py`` grew the SAME defect independently
    (``_law_true_rows``, which dropped ``fan_ramp_zones_ll``), which is
    why the guard is a list rather than one file.
    """
    src = _grade_gate_src(module)
    assert "run_checks_law_true(" in src, (
        f"{module} must take its law frame from "
        f"check_grade.run_checks_law_true, not assemble kwargs")
    code = _code_only(src)
    # The historical spellings of the hand-built payload, kept so a revert
    # to the old gate code is caught by name.
    legacy = ("taxi_axes_exact_ll", "junction_mesh_edges_ll")
    for key in _sidecar_law_kwargs() + legacy:
        assert key not in code, (
            f"{module} still assembles {key!r} itself — that is a second "
            f"instrument describing the same population")


def test_the_faa_fixture_is_in_the_acceptance_battery():
    """KCLT is the campaign's FAA fixture and was absent from the default
    battery ENTIRELY, so the FAA half of the region-ruleset split had no
    acceptance test — the FAA-only drainage-minimum family (1,099 KCLT
    rows in the test-phase census) could not be seen here at all."""
    import os
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    for var in ("O4_TEST_AIRPORTS", "O4_TEST_TILE"):
        assert not os.environ.get(var, "").strip(), (
            f"{var} is set — the DEFAULT battery is what this twin asserts")
    import test_pavement_grade as gate
    assert "KCLT" in gate._GRADE_TEST_AIRPORTS, (
        f"the FAA fixture is not in the default battery: "
        f"{gate._GRADE_TEST_AIRPORTS}")
    assert "HECA" in gate._GRADE_TEST_AIRPORTS


# ══════════════════════════════════════════════════════════════════════
# §6 THE FRAME KEYS AND THE WRITE GUARD (fix cycle 2, item 4)
# ══════════════════════════════════════════════════════════════════════
# Two halves of one property: a run's numbers are only comparable with
# another run's if (a) both graded the SAME surface and (b) neither
# CHANGED the corpus underneath the other.

def test_the_install_paths_are_dem_frame_keys(build_mod):
    """``cifp_data_path`` / ``custom_scenery_dir`` shape the SURFACE.

    They were classified as "install-location settings, never law gates".
    They select which apt.dat/CIFP corpus is read, and the airport
    elevation INSET is cut against the footprint mask derived from it — so
    two lanes on two installs grade two different inset surfaces while
    every frame check reports agreement.
    """
    for key in ("cifp_data_path", "custom_scenery_dir"):
        assert key in build_mod.DEM_FRAME_KEYS, (
            f"{key} shapes the inset surface via the airport footprint "
            f"mask; it is a DEM frame key, not a file location")
    assert "custom_overlay_src" not in build_mod.DEM_FRAME_KEYS, (
        "overlays are consumed after the patch and touch no inset — "
        "widening the frame beyond its mechanism makes it noise")


def test_an_UNSET_install_path_is_not_a_frame_divergence(build_mod, tmp_path):
    """Empty means "the harness supplies the owner's", not "a different
    corpus".  Every lane worktree ships these empty, so treating empty as
    a divergence would refuse every build in the repo for a difference
    that does not exist at run time."""
    owner = tmp_path / "owner.cfg"
    owner.write_text("cifp_data_path=/X/CIFP\ncustom_scenery_dir=/X/CS\n"
                     "apt_smoothing_pix=8\n")
    lane = tmp_path / "lane"
    lane.mkdir()
    (lane / "Ortho4XP.cfg").write_text(
        "cifp_data_path=\ncustom_scenery_dir=\napt_smoothing_pix=8\n")
    assert build_mod.cfg_frame_diff(lane, owner_cfg=owner) == {}
    eff = build_mod.frame_surface_keys(lane, owner_cfg=owner)
    assert eff["cifp_data_path"] == "/X/CIFP", (
        "the frame record must carry the EFFECTIVE value — which corpus "
        "cut the insets is a question asked of numbers already in a report")


def test_a_DIFFERENT_install_path_IS_a_frame_divergence(build_mod, tmp_path):
    owner = tmp_path / "owner.cfg"
    owner.write_text("cifp_data_path=/X/CIFP\ncustom_scenery_dir=/X/CS\n")
    lane = tmp_path / "lane"
    lane.mkdir()
    (lane / "Ortho4XP.cfg").write_text(
        "cifp_data_path=/OTHER/CIFP\ncustom_scenery_dir=/X/CS\n")
    diff = build_mod.cfg_frame_diff(lane, owner_cfg=owner)
    assert set(diff) == {"cifp_data_path"}
    assert diff["cifp_data_path"] == ("/OTHER/CIFP", "/X/CIFP")


def test_the_write_guard_BLOCKS_an_unauthorised_shared_repo_write(
        build_mod, tmp_path):
    """THE PREVENTER, on the named precedent's own path.

    The re-baseline caught ``OSM_data/_airport_road_feed/*_road_feed.cache``
    written by two live builds and could only report it afterwards — from
    six concurrent runs whose snapshots each saw both writes, so the
    contamination flag was cross-attributed and the corpus had already
    changed under every lane.  Refusing at the call attributes the write to
    its author and leaves the corpus intact.
    """
    repo = tmp_path / "repo"
    (repo / "OSM_data" / "_airport_road_feed").mkdir(parents=True)
    lane = tmp_path / "lane"
    lane.mkdir()
    target = repo / "OSM_data" / "_airport_road_feed" / "CYXY_road_feed.cache"

    with pytest.raises(build_mod.SharedRepoWriteBlocked) as exc:
        with build_mod.SharedRepoWriteGuard(set(), lane, repo=repo):
            open(target, "w").write("regenerated mid-build")
    assert "CYXY_road_feed.cache" in str(exc.value)
    assert "osm_roadfeed" in str(exc.value)
    assert "--refresh-data" in str(exc.value), (
        "the refusal must name the flag that would authorise it")
    assert not target.exists(), "the guard must prevent, not just report"


def test_the_write_guard_ALLOWS_an_authorised_scope(build_mod, tmp_path):
    repo = tmp_path / "repo"
    (repo / "OSM_data" / "_airport_road_feed").mkdir(parents=True)
    lane = tmp_path / "lane"
    lane.mkdir()
    target = repo / "OSM_data" / "_airport_road_feed" / "CYXY_road_feed.cache"
    with build_mod.SharedRepoWriteGuard({"osm_roadfeed"}, lane, repo=repo):
        open(target, "w").write("explicitly authorised")
    assert target.read_text() == "explicitly authorised"


def test_the_write_guard_RECORD_ONLY_records_AND_lets_the_write_through(
        build_mod, tmp_path):
    """RECORD-ONLY, on the same path the preventer refuses above.

    The suite write audit (``tests/conftest.py::_shared_repo_write_audit``)
    has to enumerate what the suite writes TODAY: a guard that blocked
    would change test outcomes and enumerate the offenders of a different
    suite.  So the entry lands in ``blocked`` exactly as in refuse mode —
    same path, same scope, same ``via`` — and the call proceeds.
    """
    repo = tmp_path / "repo"
    (repo / "OSM_data" / "_airport_road_feed").mkdir(parents=True)
    lane = tmp_path / "lane"
    lane.mkdir()
    target = repo / "OSM_data" / "_airport_road_feed" / "CYXY_road_feed.cache"
    guard = build_mod.SharedRepoWriteGuard(set(), lane, repo=repo,
                                           record_only=True)
    with guard:                                   # no exception escapes
        open(target, "w").write("observed, not prevented")
    assert target.read_text() == "observed, not prevented", (
        "record-only must let the intercepted call PROCEED")
    assert guard.blocked == [{
        "path": "OSM_data/_airport_road_feed/CYXY_road_feed.cache",
        "scope": "osm_roadfeed",
        "via": "open for writing"}]


def test_the_write_guard_allows_noop_ensure_dir_but_blocks_creation(
        build_mod, tmp_path):
    """``makedirs(existing, exist_ok=True)`` mutates nothing — the engine
    ensure-dirs its cache paths on every tile build, and refusing the
    no-op made warm tile builds impossible through a mounted repo
    (first hit: the 2026-08-07 release tile, ``Elevation_data/+30+030``).
    Creating a directory that does NOT exist is a real mutation and must
    still refuse."""
    repo = tmp_path / "repo"
    existing = repo / "Elevation_data" / "+30+030"
    existing.mkdir(parents=True)
    lane = tmp_path / "lane"
    lane.mkdir()
    with build_mod.SharedRepoWriteGuard(set(), lane, repo=repo):
        os.makedirs(existing, exist_ok=True)      # no-op: allowed
        with pytest.raises(build_mod.SharedRepoWriteBlocked):
            os.makedirs(repo / "Elevation_data" / "+31+031")
    assert not (repo / "Elevation_data" / "+31+031").exists(), (
        "the guard must prevent, not just report")


def test_the_write_guard_leaves_reads_and_lane_products_alone(
        build_mod, tmp_path):
    """Reads are never touched, and ``Patches``/``Tiles`` are lane OUTPUT —
    guarding them would break every build."""
    repo = tmp_path / "repo"
    (repo / "OSM_data").mkdir(parents=True)
    (repo / "OSM_data" / "layer.osm").write_text("cached")
    lane = tmp_path / "lane"
    (lane / "Patches").mkdir(parents=True)
    with build_mod.SharedRepoWriteGuard(set(), lane, repo=repo):
        assert open(repo / "OSM_data" / "layer.osm").read() == "cached"
        open(lane / "Patches" / "out.osm", "w").write("lane product")
    assert (lane / "Patches" / "out.osm").exists()


def test_the_write_guard_follows_the_lane_mount_symlinks(build_mod, tmp_path):
    """A lane writes ``OSM_data/...`` RELATIVE, through a symlink into the
    shared repo — the path string never mentions the repo at all, which is
    exactly how a textual check would miss every real case."""
    repo = tmp_path / "repo"
    (repo / "OSM_data" / "_airport_road_feed").mkdir(parents=True)
    lane = tmp_path / "lane"
    lane.mkdir()
    (lane / "OSM_data").symlink_to(repo / "OSM_data")
    guard = build_mod.SharedRepoWriteGuard(set(), lane, repo=repo)
    hit = guard._violation(
        str(lane / "OSM_data" / "_airport_road_feed" / "X_road_feed.cache"))
    assert hit == ("OSM_data/_airport_road_feed/X_road_feed.cache",
                   "osm_roadfeed")


def test_the_write_guard_REFUSES_a_write_through_an_overlay_symlink(
        build_mod, tmp_path):
    """THE GUARD HOLE, measured three times on 2026-08-12.

    A lane-local overlay entry that is a SYMLINK into the shared repo is a
    shared-repo write: ``open(entry, "wb")`` follows the link and truncates
    the corpus file.  The guard compared the OPEN path — lane-local,
    outside every prefix — matched nothing, and every such run reported
    ``blocked: []``.  It was not lenient; it was structurally blind, which
    is why nobody found it by reading it.

    So the predicate judges the RESOLVED path.  Delete the resolution from
    ``_violation`` and this test fails — that mutation is the point of it.
    The overlay's copy-on-write seeding removes the condition; this removes
    the DEPENDENCE on it having been removed.
    """
    repo = tmp_path / "repo"
    (repo / "Airport_mod_cache" / "PACK").mkdir(parents=True)
    shared = repo / "Airport_mod_cache" / "PACK" / "o4_object_footprints.cache"
    shared.write_bytes(b"warm shared sidecar")

    lane = tmp_path / "lane"
    # Deliberately NOT under a lane mount name: the overlay lives beside
    # the build's artifacts, so no prefix of the guard's mentions it.
    overlay = lane / "CYXY.engine_caches" / "Airport_mod_cache" / "PACK"
    overlay.mkdir(parents=True)
    entry = overlay / "o4_object_footprints.cache"
    entry.symlink_to(shared)

    guard = build_mod.SharedRepoWriteGuard(set(), lane, repo=repo)
    with pytest.raises(build_mod.SharedRepoWriteBlocked) as exc:
        with guard:
            open(entry, "wb").write(b"truncated through the link")
    assert "Airport_mod_cache/PACK/o4_object_footprints.cache" in str(exc.value)
    assert guard.blocked and guard.blocked[0]["path"] == (
        "Airport_mod_cache/PACK/o4_object_footprints.cache"), (
        "the refusal must name the path in the SHARED repo, not the "
        "lane-local string the writer used")
    assert shared.read_bytes() == b"warm shared sidecar", (
        "the guard must prevent, not just report")


def test_the_resolving_guard_leaves_a_REAL_overlay_entry_alone(
        build_mod, tmp_path):
    """The other half of the same predicate: a copy-on-write overlay entry
    is a real lane-local file, resolves lane-local, and must NOT refuse.

    Without this, "resolve everything" could be satisfied by refusing the
    lawful overlay write too — which would make the fixed overlay
    unusable and send the next lane back to symlinks.
    """
    repo = tmp_path / "repo"
    (repo / "Airport_mod_cache" / "PACK").mkdir(parents=True)
    shared = repo / "Airport_mod_cache" / "PACK" / "o4_object_footprints.cache"
    shared.write_bytes(b"warm shared sidecar")

    lane = tmp_path / "lane"
    overlay = lane / "CYXY.engine_caches" / "Airport_mod_cache"
    made = build_mod.mirror_tree_as_overlay(
        str(repo / "Airport_mod_cache"), str(overlay))
    assert made["files"] == 1
    entry = overlay / "PACK" / "o4_object_footprints.cache"

    guard = build_mod.SharedRepoWriteGuard(set(), lane, repo=repo)
    with guard:
        assert open(entry, "rb").read() == b"warm shared sidecar"  # warm read
        open(entry, "wb").write(b"rebuilt lane-local")
    assert guard.blocked == [], (
        "a copy-on-write overlay write is lane-local and must pass clean")
    assert entry.read_bytes() == b"rebuilt lane-local"
    assert shared.read_bytes() == b"warm shared sidecar"


def test_the_write_guard_restores_every_hook_it_installed(build_mod, tmp_path):
    """An instrument that leaks its own monkeypatches poisons the process
    it was supposed to observe."""
    import builtins
    before = (builtins.open, os.open, os.rename, os.replace, os.remove,
              os.makedirs)
    lane = tmp_path / "lane"
    lane.mkdir()
    with build_mod.SharedRepoWriteGuard(set(), lane, repo=tmp_path / "repo"):
        assert builtins.open is not before[0]
    after = (builtins.open, os.open, os.rename, os.replace, os.remove,
             os.makedirs)
    assert before == after


def test_the_detector_SURVIVES_the_preventer(build_mod):
    """Defence in depth: the guard covers the Python level, and a C
    extension's own file handling does not pass through it.  Deleting the
    after-the-fact snapshot audit because a lock exists would trade a
    complete-but-late instrument for an early-but-partial one.

    The DEFINITION moved into ``shared_repo_guard.py`` on 2026-08-08 (one
    implementation, two entries — §6c); the build entry still CALLS it and
    still contaminates its own frame on a hit, which is the half this twin
    has always been about."""
    guard_src = (HARNESS / "shared_repo_guard.py").read_text()
    assert "def report_unauthorised_writes(" in guard_src
    src = (HARNESS / "build_airport.py").read_text()
    assert "def report_unauthorised_writes(" not in src, (
        "the detector must have ONE definition — see §6c")
    assert "report_unauthorised_writes(" in src, (
        "the build entry must still CALL the detector")
    assert "shared_repo_snapshot()" in src
    assert "frame[\"contaminated\"]" in src


def test_the_write_guard_is_armed_by_the_BUILD_ENTRY_not_only_the_cli(
        build_mod):
    """``oracle.py`` and ``who_wrote.py`` call ``build_patch`` DIRECTLY.

    Arming the guard in ``main`` only would have left every oracle run and
    every authorship trace free to regenerate the shared corpus — and those
    are the entries a lane actually runs most.  ``build_patch`` therefore
    arms its own (defaulting to "nothing authorised") and ``main`` hands
    its own guard down rather than wrapping the call.

    Since 2026-08-11 the arming is ONE named composition
    (``arm_shared_repo_protection``, shared with
    ``tools/classify_report.py`` — §6d), so the default guard is asserted
    THERE; what ``build_patch`` must still do is call it and run the build
    inside what it hands back.
    """
    import inspect
    sig = inspect.signature(build_mod.build_patch)
    assert "write_guard" in sig.parameters
    src = inspect.getsource(build_mod.build_patch)
    assert "arm_shared_repo_protection(" in src, (
        "build_patch must arm the composition when its caller passes none")
    assert "with guard:" in src
    composed = inspect.getsource(build_mod.arm_shared_repo_protection)
    assert "SharedRepoWriteGuard(" in composed and "redirect_engine_caches(" \
        in composed, (
        "the composition must supply BOTH halves — the redirect closes the "
        "subprocess hole the guard cannot see, and the guard is what stops "
        "a writer reaching the corpus THROUGH the overlay")
    assert "getattr(write_guard, \"requested\"" in composed, (
        "an AUTHORISED refresh scope must be left SHARED, or the refresh is "
        "a silent no-op")


def test_every_build_result_carries_the_frame_and_guard_state(build_mod):
    """The frame record has to be IN the artifact: "which corpus cut the
    insets" is a question asked of numbers that are already in a report."""
    import inspect
    src = inspect.getsource(build_mod.build_patch)
    for key in ("write_guard_armed", "write_guard_blocked",
                "write_guard_lock_churn", "write_guard_library_index_churn",
                "dem_frame_effective"):
        assert f'"{key}"' in src, f"build_patch result omits {key}"


# ══════════════════════════════════════════════════════════════════════
# §6b THE LOCK-FILE AND LIBRARY-INDEX ALLOWANCES, AND THE
#     SWALLOWED-DEGRADATION REFUSALS
# ══════════════════════════════════════════════════════════════════════
# Landed 2026-08-07 against a MEASURED defect (``tmp/sliver_attrib``): a
# real-DEM ``build_airport.py HECA --patch-only`` had its DEM prep blocked
# by the write guard on the elevation provider's ``.lock`` file, and
# ``auto_patch.elevation._load_airport_dem``'s single ``except Exception``
# turned the refusal into a WARN line.  The build exited 0 with
# ``dem_inset_provenance: null`` and 18.5 k nodes against production's
# 34-36 k, whole roles absent.  Two halves, twinned separately: the lock
# file is coordination state and must pass, and a degradation the engine
# swallowed must never exit 0.
#
# The LIBRARY-INDEX half is the same ruling on a second artifact class,
# from the nidrepair 2026-08-07 measurement: every harness build reported
# a shared-repo side effect on
# ``Airport_mod_cache/o4_library_index_768a6b59d2781165.cache`` while its
# own ``write_guard_blocked`` was empty.  The X-Plane install's
# ``scenery_packs.ini`` had been touched OUTSIDE the guarded repo, one
# engine process rewrote the derived sidecar, and the write landed inside
# every concurrently-open snapshot window — cross-attributed to builds
# that never wrote it.  The same allowance closes the other end: a
# guarded build that is itself the first reader has its refusal swallowed
# by ``agp_reader``'s ``except Exception`` and is then rc=2'd by
# ``require_no_swallowed_write_block``.

LOCK_REL = "Elevation_data/+30+030/.lock_VIEWFINDER3_N30E031.lock"


def _lock_repo(tmp_path):
    """A fake shared repo with the elevation block directory the engine's
    base-tile lock lives in, plus an empty lane."""
    repo = tmp_path / "repo"
    (repo / "Elevation_data" / "+30+030").mkdir(parents=True)
    lane = tmp_path / "lane"
    lane.mkdir()
    return repo, lane


def test_the_guard_ALLOWS_the_engines_lock_file_and_records_the_churn(
        build_mod, tmp_path):
    """The diagnosed site: ``O4_Airport_Elevation_Insets.ensure_base_tile``
    takes an ``O4_File_Lock`` around the download-if-missing critical
    section on EVERY base-tile resolution — warm cache included, because
    the lock is what makes the cached double-check safe between concurrent
    tile builds.  Its contents are a pid and a timestamp; no measurement is
    a function of it.  Refusing it did not protect the corpus, it produced
    a DEM-less build."""
    repo, lane = _lock_repo(tmp_path)
    lock = repo / LOCK_REL
    guard = build_mod.SharedRepoWriteGuard(set(), lane, repo=repo)
    with guard:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, b"4242 2026-08-07T09:00:00\n")
        os.close(fd)
        assert lock.exists()
        os.remove(str(lock))                     # the release
    assert not lock.exists()
    ops = [c["op"] for c in guard.lock_churn]
    assert ops == ["os_open", "remove"], (
        "the allowance must RECORD every lock operation it let through — "
        "'the repo was untouched apart from the ruled lock churn' is a "
        "fact in the artifact, not a claim in a report")
    assert all(c["path"] == LOCK_REL for c in guard.lock_churn)


def test_a_REAL_data_write_beside_the_lock_STILL_refuses(build_mod, tmp_path):
    """The allowance must not become a door.  The base raster lives in the
    SAME directory as the lock that guards it, so this is the write the
    lock exists to serialise — and it is exactly what owner ruling e9daef5
    forbids as a build side effect."""
    repo, lane = _lock_repo(tmp_path)
    raster = repo / "Elevation_data" / "+30+030" / "N30E031.hgt"
    with build_mod.SharedRepoWriteGuard(set(), lane, repo=repo) as guard:
        with pytest.raises(build_mod.SharedRepoWriteBlocked) as exc:
            os.open(str(raster), os.O_CREAT | os.O_WRONLY)
        with pytest.raises(build_mod.SharedRepoWriteBlocked):
            open(raster, "wb").write(b"downloaded mid-measurement")
    assert "N30E031.hgt" in str(exc.value)
    assert "dem" in str(exc.value), "the refusal must name the refresh scope"
    assert not raster.exists(), "the guard must prevent, not just report"
    assert guard.lock_churn == []


def test_the_lock_allowance_is_scoped_to_the_lock_PRIMITIVES_own_calls(
        build_mod, tmp_path):
    """NARROWEST MATCH: ``hold_file_lock`` creates the file with
    ``os.open`` and removes it — nothing else.  A ``builtins.open`` of a
    ``.lock`` path, or a rename ONTO one, is not lock handling: it is a
    corpus write wearing a lock's name, and it still refuses."""
    repo, lane = _lock_repo(tmp_path)
    lock = repo / LOCK_REL
    other = tmp_path / "elsewhere.dat"
    other.write_text("payload")
    with build_mod.SharedRepoWriteGuard(set(), lane, repo=repo):
        with pytest.raises(build_mod.SharedRepoWriteBlocked):
            open(lock, "w").write("not the lock primitive")
        with pytest.raises(build_mod.SharedRepoWriteBlocked):
            os.rename(str(other), str(lock))
    assert not lock.exists()


def test_the_ENGINES_OWN_lock_primitive_passes_the_armed_guard(
        build_mod, tmp_path):
    """THE KNOWN-ANSWER TWIN (RULINGS 2026-08-06, instrument truth): the
    allowance is asserted against the real ``O4_File_Lock.hold_file_lock``,
    not against this test's idea of what it does.  If the primitive ever
    changes how it names or writes its lock, this fails here instead of
    silently degrading a real-DEM build again."""
    import O4_File_Lock
    repo, lane = _lock_repo(tmp_path)
    target = repo / "Elevation_data" / "+30+030" / ".lock_VIEWFINDER3_N30E031"
    guard = build_mod.SharedRepoWriteGuard(set(), lane, repo=repo)
    with guard:
        with O4_File_Lock.hold_file_lock(str(target)) as acquired:
            assert acquired
            assert Path(str(target) + ".lock").exists()
    assert not Path(str(target) + ".lock").exists()
    assert [c["op"] for c in guard.lock_churn] == ["os_open", "remove"]


def test_lock_churn_in_the_after_snapshot_is_not_CONTAMINATION(build_mod):
    """The backstop half: a lock file visible in the before/after snapshot
    means a holder died inside its critical section — it is named, because
    it blocks the next lane until it goes stale, but the corpus did not
    change and the run is not contaminated."""
    notes = []
    prog = types.SimpleNamespace(note=notes.append)
    changes = {"added": [LOCK_REL, "Elevation_data/+30+030/N30E031.hgt"],
               "modified": [], "removed": []}
    offenders = build_mod.report_unauthorised_writes(changes, set(), prog)
    assert [o["path"] for o in offenders] == [
        "Elevation_data/+30+030/N30E031.hgt"]
    assert any("lock churn" in n for n in notes), (
        "lock churn must be REPORTED, never silently dropped")


# ── the library-index allowance ──────────────────────────────────────

#: The sidecar the nidrepair frames named, in the writer's own naming:
#: 16 hex of ``sha1(xplane_root)``, directly under the cache directory.
LIB_INDEX_REL = ("Airport_mod_cache/"
                 "o4_library_index_0123456789abcdef.cache")


def _index_repo(tmp_path):
    """A fake shared repo with the ``Airport_mod_cache`` directory the
    library-index sidecar lives in, plus an empty lane."""
    repo = tmp_path / "repo"
    (repo / "Airport_mod_cache").mkdir(parents=True)
    lane = tmp_path / "lane"
    lane.mkdir()
    return repo, lane


def test_the_guard_ALLOWS_the_library_index_sidecar_and_records_the_churn(
        build_mod, tmp_path):
    """The diagnosed site: ``agp_reader._write_library_index_sidecar``
    writes a ``.o4_library_index_*.tmp`` sibling and ``os.replace``s it
    onto the cache name.  The file is a byte-deterministic function of the
    X-Plane install — which lives OUTSIDE the guarded repo — so whichever
    process first notices ``scenery_packs.ini`` changed rewrites it, and
    refusing that write neither protects the corpus nor stops it being
    cross-attributed to every concurrent build."""
    import tempfile
    repo, lane = _index_repo(tmp_path)
    cache_dir = repo / "Airport_mod_cache"
    final = repo / LIB_INDEX_REL
    guard = build_mod.SharedRepoWriteGuard(set(), lane, repo=repo)
    with guard:
        fd, tmp = tempfile.mkstemp(dir=str(cache_dir),
                                   prefix=".o4_library_index_",
                                   suffix=".tmp")
        with os.fdopen(fd, "wb") as sidecar_file:
            sidecar_file.write(b"pickled index")
        os.replace(tmp, str(final))
    assert final.read_bytes() == b"pickled index"
    assert guard.blocked == []
    ops = [c["op"] for c in guard.library_index_churn]
    assert ops == ["os_open", "replace", "replace"], (
        "the allowance must RECORD every operation it let through, both "
        "paths of the rename included — 'the repo was untouched apart "
        "from the ruled index churn' is a fact in the artifact")
    assert guard.library_index_churn[-1]["path"] == LIB_INDEX_REL


def test_the_ENGINES_OWN_library_index_writer_passes_the_armed_guard(
        build_mod, tmp_path):
    """THE KNOWN-ANSWER TWIN (RULINGS 2026-08-06, instrument truth): the
    allowance is asserted against the real
    ``agp_reader._write_library_index_sidecar``, not against this test's
    idea of what it does.  If that writer ever changes its naming or its
    calls, this fails HERE — instead of re-flagging every harness build as
    CONTAMINATED, or having its refusal swallowed by the writer's own
    ``except Exception`` and rc=2'ing a good build."""
    from auto_patch import agp_reader
    repo, lane = _index_repo(tmp_path)
    sidecar = repo / LIB_INDEX_REL
    guard = build_mod.SharedRepoWriteGuard(set(), lane, repo=repo)
    with guard:
        agp_reader._write_library_index_sidecar(
            str(sidecar), "f" * 40, {"lib/x": "/y"})
    assert sidecar.exists(), (
        "the writer swallows its own exceptions, so a refused write is "
        "visible only as a MISSING sidecar")
    assert guard.blocked == []
    assert [c["op"] for c in guard.library_index_churn] == [
        "os_open", "replace", "replace"]


def test_a_REAL_Airport_mod_cache_write_STILL_refuses(build_mod, tmp_path):
    """The allowance must not become a door into the cache directory.
    Three ways past it, all refused: the right name reached by the wrong
    call, another cache under the same scope, and the right basename one
    directory deeper."""
    repo, lane = _index_repo(tmp_path)
    sidecar = repo / LIB_INDEX_REL
    apt_index = repo / "Airport_mod_cache/Global Airports/apt_index.cache"
    nested = repo / "Airport_mod_cache/sub" / os.path.basename(LIB_INDEX_REL)
    with build_mod.SharedRepoWriteGuard(set(), lane, repo=repo) as guard:
        with pytest.raises(build_mod.SharedRepoWriteBlocked) as exc:
            open(sidecar, "w").write("not the sidecar writer")
        with pytest.raises(build_mod.SharedRepoWriteBlocked):
            os.open(str(apt_index), os.O_CREAT | os.O_WRONLY)
        with pytest.raises(build_mod.SharedRepoWriteBlocked):
            os.open(str(nested), os.O_CREAT | os.O_WRONLY)
    assert "airport_mod_cache" in str(exc.value), (
        "the refusal must name the refresh scope")
    assert not sidecar.exists() and not apt_index.exists()
    assert not nested.exists(), "the guard must prevent, not just report"
    assert guard.library_index_churn == []


def test_the_library_index_allowance_is_WITHDRAWN_when_asked(
        build_mod, tmp_path):
    """``allow_library_index=False`` (suite-corpus-clean spec §8.2 R-e).

    The allowance is right for a HARNESS build — the X-Plane install
    changes under it and the sidecar is derived from that install.  It is
    wrong for the SUITE, which points the whole cache root at a lane-local
    overlay: nothing should reach the sidecar's real path there, so a call
    that does is a BYPASS, and an allowance would turn it into a silent
    shared write.  Same path, same call, both modes — the only difference
    is the parameter.
    """
    repo, lane = _index_repo(tmp_path)
    sidecar = repo / LIB_INDEX_REL

    allowed = build_mod.SharedRepoWriteGuard(set(), lane, repo=repo)
    with allowed:
        os.close(os.open(str(sidecar), os.O_CREAT | os.O_WRONLY))
    assert [c["op"] for c in allowed.library_index_churn] == ["os_open"]
    assert allowed.blocked == []
    sidecar.unlink()

    refused = build_mod.SharedRepoWriteGuard(set(), lane, repo=repo,
                                             allow_library_index=False)
    with refused:
        with pytest.raises(build_mod.SharedRepoWriteBlocked) as exc:
            os.open(str(sidecar), os.O_CREAT | os.O_WRONLY)
    assert refused.library_index_churn == []
    assert [b["path"] for b in refused.blocked] == [LIB_INDEX_REL]
    assert "airport_mod_cache" in str(exc.value), (
        "the refusal must name the refresh scope like any other")
    assert not sidecar.exists(), "the guard must prevent, not just report"


def test_the_lock_allowance_STANDS_when_the_index_one_is_withdrawn(
        build_mod, tmp_path):
    """The two allowances are independent.  Refusing coordination state
    does not protect the corpus — it makes concurrent-safe cache READS
    impossible, which is how a real-DEM HECA build came back with no DEM
    at all."""
    repo, lane = _lock_repo(tmp_path)
    lock = repo / LOCK_REL
    guard = build_mod.SharedRepoWriteGuard(set(), lane, repo=repo,
                                           allow_library_index=False)
    with guard:
        os.close(os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        os.remove(str(lock))
    assert guard.blocked == []
    assert [c["op"] for c in guard.lock_churn] == ["os_open", "remove"]


def test_library_index_churn_in_the_after_snapshot_is_not_CONTAMINATION(
        build_mod):
    """THE MEASURED DEFECT, replayed: the nidrepair 2026-08-07 frames each
    carried ``write_guard_blocked: []`` and a modified
    ``o4_library_index_768a6b59d2781165.cache`` — a write neither build's
    guarded code made, minted CONTAMINATED by the snapshot alone."""
    notes = []
    prog = types.SimpleNamespace(note=notes.append)
    measured = "Airport_mod_cache/o4_library_index_768a6b59d2781165.cache"
    offenders = build_mod.report_unauthorised_writes(
        {"added": [], "modified": [measured], "removed": []}, set(), prog)
    assert offenders == []
    assert not any("SHARED-REPO SIDE EFFECT" in n for n in notes)
    assert any("library-index churn" in n for n in notes), (
        "index churn must be REPORTED, never silently dropped")

    notes.clear()
    apt_index = "Airport_mod_cache/Global Airports/apt_index.cache"
    offenders = build_mod.report_unauthorised_writes(
        {"added": [], "modified": [measured, apt_index], "removed": []},
        set(), prog)
    assert [o["path"] for o in offenders] == [apt_index], (
        "the allowance covers ONE derived file, not its whole scope")


# ── THE WINDOW-ATTRIBUTION INSTRUMENT (2026-09-01, H6 item 6) ────────
#
# The audit diffs the WHOLE shared repo across a build's wall-clock
# window and used to attribute every delta in it to that build.  A window
# is not an author: builds run concurrently by ruling, and the
# library-index allowance was this same defect solved once for one file.
# These twins pin the generalised label: NAMED always, CONTAMINATED only
# when the build's own input set cannot exclude it.

_H6_OTHER_TILE = "Elevation_data/+40+000/N40E003_airport_insets/LEMD.tif"
_H6_MY_TILE = "Elevation_data/+30+030/N30E031.hgt"


def test_a_delta_outside_the_input_set_is_named_but_NOT_contamination(
        build_mod):
    """THE MEASURED CLASS, generalised.  A HECA build (tile +30+031) sees
    a LEMD inset appear in its window.  It cannot have written it — the
    path names a tile HECA does not read and its own guard blocked
    nothing — so it is NAMED as an external candidate and the run is not
    flagged CONTAMINATED on it."""
    notes = []
    prog = types.SimpleNamespace(note=notes.append)
    scope = build_mod.BuildInputScope(tiles=[(30, 31)], icaos=["HECA"])
    offenders = build_mod.report_unauthorised_writes(
        {"added": [_H6_OTHER_TILE], "modified": [], "removed": []},
        set(), prog, blocked=[], input_scope=scope)
    assert [o["path"] for o in offenders] == [_H6_OTHER_TILE], (
        "the delta must still be NAMED — nothing is dropped")
    assert offenders[0]["external_candidate"] is True
    assert build_mod.contaminating_writes(offenders) == []
    blob = "\n".join(notes)
    assert "external-candidate" in blob
    assert "SHARED-REPO SIDE EFFECT" not in blob, (
        "the CONTAMINATED verdict line must not be printed")
    assert "UNCHANGED" in blob, (
        "a run whose only deltas are external candidates reports its own "
        "corpus untouched")


def test_a_delta_INSIDE_the_input_set_still_CONTAMINATES(build_mod):
    """The other half, and the one that keeps the law: the KCLT road-feed
    precedent's own artifact class, at the build's own airport."""
    notes = []
    prog = types.SimpleNamespace(note=notes.append)
    scope = build_mod.BuildInputScope(tiles=[(35, -81)], icaos=["KCLT"])
    mine = "OSM_data/_airport_road_feed/KCLT_road_feed.cache"
    offenders = build_mod.report_unauthorised_writes(
        {"added": [mine], "modified": [], "removed": []},
        set(), prog, blocked=[], input_scope=scope)
    assert offenders[0]["external_candidate"] is False
    assert build_mod.contaminating_writes(offenders) == offenders
    assert "CONTAMINATED" in "\n".join(notes)


def test_a_GUARD_BLOCKED_run_externalises_NOTHING(build_mod):
    """THE WHOLE-RUN VETO.  A build whose guard blocked a write did reach
    for the corpus; nothing appearing in its window may then be handed to
    a hypothetical other process, however far away the path is."""
    prog = types.SimpleNamespace(note=lambda m: None)
    scope = build_mod.BuildInputScope(tiles=[(30, 31)], icaos=["HECA"])
    offenders = build_mod.report_unauthorised_writes(
        {"added": [_H6_OTHER_TILE], "modified": [], "removed": []},
        set(), prog, blocked=[{"path": _H6_MY_TILE, "scope": "dem"}],
        input_scope=scope)
    assert offenders[0]["external_candidate"] is False
    assert build_mod.contaminating_writes(offenders) == offenders


def test_no_input_scope_keeps_the_old_whole_window_strictness(build_mod):
    """THE DEFAULT IS UNCHANGED.  Every entry that passes no scope — and
    an EMPTY scope, which can exclude nothing — gets the pre-2026-09-01
    behaviour to the letter."""
    prog = types.SimpleNamespace(note=lambda m: None)
    changes = {"added": [_H6_OTHER_TILE], "modified": [], "removed": []}
    for scope in (None, build_mod.BuildInputScope()):
        offenders = build_mod.report_unauthorised_writes(
            changes, set(), prog, input_scope=scope)
        assert build_mod.contaminating_writes(offenders) == offenders, (
            "an absent or empty input set must not downgrade anything")


def test_an_UNSCOPABLE_path_is_never_external(build_mod):
    """"Not provably external" IS the predicate.  A path naming neither a
    tile nor an airport cannot be excluded, so it is not."""
    scope = build_mod.BuildInputScope(tiles=[(30, 31)], icaos=["HECA"])
    for rel in ("Geotiffs/user_supplied.tif",
                "OSM_data/_regional_extracts/egypt-latest.osm.pbf"):
        assert build_mod.tiles_named_in(rel) == set()
        assert scope.covers(rel), f"{rel} must not be externalised"


def test_both_tile_spellings_are_read_and_the_NEIGHBOURS_are_in_scope(
        build_mod):
    """The corpus uses two spellings — ``N30E031.hgt`` in the DEM tree and
    ``+30+031`` everywhere else — and a build reads past its own tile at
    the seams.  A scoping rule that knew one spelling would call half the
    corpus unscopable; one that knew no neighbours would externalise a
    real seam write."""
    assert build_mod.tiles_named_in(_H6_MY_TILE) == {(30, 30), (30, 31)}
    assert build_mod.tiles_named_in(
        "Masks/+30+030/+30+031/6704_9648.png") == {(30, 30), (30, 31)}
    assert build_mod.tiles_named_in(
        "Airport_mod_cache/Nimbus/+35-081.dsf.8828b7db.text") == {(35, -81)}
    assert build_mod.tiles_named_in(
        "Elevation_data/-20-080/S13W078_airport_insets/SPJC.tif") == {
            (-20, -80), (-13, -78)}
    scope = build_mod.BuildInputScope(tiles=[(30, 31)])
    assert scope.covers("Elevation_data/+30+030/N31E032.hgt"), (
        "a NEIGHBOUR tile is in scope — the seam passes read it")
    assert not scope.covers("Elevation_data/+40+000/N40E003.hgt")


def test_the_airport_scoping_reads_the_road_feed_by_ICAO(build_mod):
    """The road feed carries no tile in its name; without the ICAO rule it
    would be unscopable and every concurrent lane's feed would contaminate
    every other lane — which is exactly what the guard caught live at CYXY
    and SPLP."""
    assert build_mod.airports_named_in(
        "OSM_data/_airport_road_feed/CYXY_road_feed.cache") == "CYXY"
    assert build_mod.airports_named_in(_H6_MY_TILE) is None
    scope = build_mod.BuildInputScope(tiles=[(35, -81)], icaos=["KCLT"])
    assert scope.covers("OSM_data/_airport_road_feed/KCLT_road_feed.cache")
    assert not scope.covers(
        "OSM_data/_airport_road_feed/CYXY_road_feed.cache")


# ── THE PACK RULE (2026-09-14, lane meshscope) ────────────────────────
# Measured 2026-09-13: a +40-004 LEMD ``run_tile_mesh_only.py`` run, its
# own ``guard.blocked`` EMPTY, failed rc 1 as CONTAMINATED on 117
# ``Airport_mod_cache/c_EGY - 100_airport - HECA Cairo (Tai Models)/…``
# paths (+ 1 OTHH path) a concurrent lane's object stage wrote.  The
# mesh-only entry passed NO input scope, and even with one the paths are
# hash-keyed (``o4_object_partition_<hash>.cache``) — they name no tile,
# so the tile rule alone calls them unscopable.  The PACK is the scope
# they carry; the entry now passes the same ``BuildInputScope`` the
# build entry does, derived through ONE factory.

_HECA_PACK = "c_EGY - 100_airport - HECA Cairo (Tai Models)"
_LEMD_PACK = "Aerosoft - LEMD Madrid - 1 - Airport"
_MS_OTHER_PACK_HASHED = (f"Airport_mod_cache/{_HECA_PACK}/"
                         "o4_object_exclusions_02ffb16efa76df0f.cache")
_MS_MY_PACK_HASHED = (f"Airport_mod_cache/{_LEMD_PACK}/"
                      "o4_object_pad_frame_04edbf141805d34c.cache")
_MS_MY_TILE = "Elevation_data/+40-010/N40W004.hgt"


def _mesh_scope(build_mod, **kw):
    return build_mod.BuildInputScope(
        tiles=[(40, -4)], icaos=["LEMD"], packs={_LEMD_PACK}, **kw)


def test_an_out_of_scope_PACK_sidecar_in_the_window_is_an_EXTERNAL_candidate(
        build_mod):
    """THE MEASURED CLASS: the HECA pack's hash-keyed sidecar, during a
    +40-004 run whose guard blocked nothing → NAMED, external, rc 0."""
    assert build_mod.mod_cache_pack_of(_MS_OTHER_PACK_HASHED) == _HECA_PACK
    assert build_mod.mod_cache_pack_of(_MS_MY_TILE) is None
    notes = []
    prog = types.SimpleNamespace(note=notes.append)
    offenders = build_mod.report_unauthorised_writes(
        {"added": [], "modified": [_MS_OTHER_PACK_HASHED], "removed": []},
        set(), prog, blocked=[], input_scope=_mesh_scope(build_mod))
    assert [o["path"] for o in offenders] == [_MS_OTHER_PACK_HASHED]
    assert offenders[0]["external_candidate"] is True
    assert build_mod.contaminating_writes(offenders) == []
    build_mod.require_no_unauthorised_writes(offenders, entry="mesh-only")
    assert "external-candidate" in "\n".join(notes)
    # the other airport's tile-named dump is external under the TILE rule
    assert not _mesh_scope(build_mod).covers(
        f"Airport_mod_cache/{_HECA_PACK}/+30+031.dsf.text")


def test_an_IN_scope_path_in_the_window_still_CONTAMINATES(build_mod):
    """Both halves of the input set keep the law: the run's own tile, and
    its own pack's hash-keyed sidecar."""
    scope = _mesh_scope(build_mod)
    for mine in (_MS_MY_TILE, _MS_MY_PACK_HASHED,
                 "OSM_data/+40-010/+40-004/+40-004_airports.osm.bz2",
                 "OSM_data/_airport_road_feed/LEMD_road_feed.cache"):
        offenders = build_mod.report_unauthorised_writes(
            {"added": [mine], "modified": [], "removed": []},
            set(), types.SimpleNamespace(note=lambda m: None),
            blocked=[], input_scope=scope)
        assert offenders[0]["external_candidate"] is False, mine
        with pytest.raises(SystemExit):
            build_mod.require_no_unauthorised_writes(offenders,
                                                     entry="mesh-only")


def test_a_scope_that_names_NO_packs_keeps_the_old_strictness(build_mod):
    """``packs=None`` (every pre-2026-09-14 caller) — a hash-keyed pack
    sidecar is unscopable and contaminates exactly as before; and a
    guard-blocked run externalises nothing even with packs scoped."""
    old = build_mod.BuildInputScope(tiles=[(40, -4)], icaos=["LEMD"])
    assert old.covers(_MS_OTHER_PACK_HASHED)
    assert old.record()["packs"] is None
    offenders = build_mod.report_unauthorised_writes(
        {"added": [_MS_OTHER_PACK_HASHED], "modified": [], "removed": []},
        set(), types.SimpleNamespace(note=lambda m: None),
        blocked=[{"path": _MS_MY_TILE, "via": "open", "scope": "dem"}],
        input_scope=_mesh_scope(build_mod))
    assert offenders[0]["external_candidate"] is False


def test_unknown_airports_keep_every_road_feed_in_scope(build_mod):
    """A tile entry that could not enumerate its airports (no cached
    airports layer) passes ``icaos=None``: a road feed is then unscopable,
    never external — the conservative direction.  ``()`` still means "no
    airport in scope"."""
    feed = "OSM_data/_airport_road_feed/OTHH_road_feed.cache"
    assert build_mod.BuildInputScope(tiles=[(40, -4)], icaos=None).covers(feed)
    assert not build_mod.BuildInputScope(tiles=[(40, -4)], icaos=()).covers(
        feed)
    assert build_mod.BuildInputScope(tiles=[(40, -4)], icaos=None).record()[
        "icaos"] is None


def test_tile_input_scope_derives_its_packs_from_the_shared_repo(
        build_mod, tmp_path):
    """The ONE factory: a pack is in scope iff its cache dir names the tile
    or a seam neighbour; the tile and its ICAOs ride along unchanged."""
    root = tmp_path / "Airport_mod_cache"
    for pack, names in {
            _HECA_PACK: ["+30+031.dsf.text",
                         "o4_object_exclusions_02ffb16efa76df0f.cache"],
            _LEMD_PACK: ["+40-004.dsf.00b7681e.text"],
            "Global Airports": ["+30+031.dsf.text", "+41-005.dsf.text"],
            "Empty Pack": [],
            }.items():
        (root / pack).mkdir(parents=True)
        for n in names:
            (root / pack / n).write_text("")
    (root / "stray_file").write_text("")
    packs = build_mod.mod_cache_packs_naming({(40, -4), (41, -5)},
                                             repo=tmp_path)
    assert packs == {_LEMD_PACK, "Global Airports"}
    scope = build_mod.tile_input_scope(40, -4, ["LEMD"], repo=tmp_path)
    rec = scope.record()
    assert rec["tiles"] == [[40, -4]] and rec["icaos"] == ["LEMD"]
    assert rec["packs"] == sorted(packs)
    assert rec["label"] == "tile +40-004"
    assert not scope.covers(_MS_OTHER_PACK_HASHED)
    assert scope.covers(_MS_MY_PACK_HASHED)
    assert scope.covers(f"Airport_mod_cache/Global Airports/"
                        f"o4_object_partition_0000000000000000.cache")
    assert build_mod.mod_cache_packs_naming(set(), repo=tmp_path) == set()
    assert build_mod.mod_cache_packs_naming({(40, -4)},
                                            repo=tmp_path / "nowhere") == set()


def test_the_mesh_only_entry_passes_the_SHARED_tile_scope_and_its_blocked_set():
    """The entry derives its scope through the one factory and hands the
    audit BOTH halves the label needs: the scope and its own blocked set
    (without ``blocked=guard.blocked`` a guard-blocked run would
    externalise)."""
    src = MESH_ONLY.read_text()
    assert "tile_input_scope(" in src
    assert "tile_icao_candidates(" in src
    assert "input_scope=input_scope" in src
    assert "blocked=guard.blocked" in src
    assert src.index("tile_input_scope(") < src.index("shared_repo_snapshot()"), (
        "the scope is derived BEFORE the window opens")
    assert "class BuildInputScope" not in src


def test_the_refusal_reads_the_label_through_the_ONE_helper(build_mod):
    """``require_no_unauthorised_writes`` must not carry its own reading of
    the label — a second copy of ``not o['external_candidate']`` is the
    census-wrapper shape."""
    external = [{"path": _H6_OTHER_TILE, "kind": "added", "scope": "dem",
                 "external_candidate": True}]
    build_mod.require_no_unauthorised_writes(external, entry="mesh-only")
    mine = [dict(external[0], external_candidate=False)]
    with pytest.raises(SystemExit):
        build_mod.require_no_unauthorised_writes(mine, entry="mesh-only")
    src = (HARNESS / "shared_repo_guard.py").read_text()
    assert src.count("external_candidate\")") <= 2, (
        "the label must be interpreted in contaminating_writes and the "
        "report, nowhere else")


def test_the_build_entry_stamps_the_scope_and_the_split_into_the_frame():
    """A verdict a later reader cannot re-derive is not evidence."""
    src = (HARNESS / "build_airport.py").read_text()
    assert 'frame["build_input_scope"]' in src
    assert 'frame["external_candidate_writes"]' in src
    assert 'frame["contaminated"] = bool(contaminating_writes(offenders))' \
        in src, "the CONTAMINATED verdict must read the ONE helper"
    assert "input_scope=input_scope" in src and "blocked=guard.blocked" in src


# ── the swallowed-degradation refusals ───────────────────────────────

def test_a_swallowed_write_block_REFUSES_and_names_write_and_hatches(
        build_mod):
    blocked = [{"path": "Elevation_data/+30+030/N30E031.hgt", "scope": "dem",
                "via": "os.open for writing"}]
    with pytest.raises(SystemExit) as exc:
        build_mod.require_no_swallowed_write_block(blocked)
    msg = str(exc.value)
    assert "N30E031.hgt" in msg, "the refusal must NAME the blocked write"
    assert "dem" in msg
    assert "--refresh-data" in msg
    assert "--allow-degraded-dem" in msg
    assert "AUTHORISES NO WRITE" in msg, (
        "accepting a worse measurement and changing everyone's data are "
        "different acts, and the refusal has to say so")


def test_the_swallowed_block_refusal_is_relaxed_ONLY_by_the_flag(build_mod):
    notes = []
    prog = types.SimpleNamespace(note=notes.append)
    blocked = [{"path": LOCK_REL, "scope": "dem", "via": "os.open"}]
    build_mod.require_no_swallowed_write_block(blocked, allow_degraded=True,
                                               prog=prog)
    assert any("DEGRADED" in n for n in notes), (
        "a degradation accepted by flag is RECORDED, exactly as the "
        "cold-DEM one is")
    build_mod.require_no_swallowed_write_block([])       # nothing blocked


def test_a_layout_with_NO_dem_provenance_refuses(build_mod):
    """DETECTOR 2, independent of the guard: ``pipeline`` writes
    ``dem_inset_provenance = None`` only when the build had no DEM OBJECT
    AT ALL — the state both ``tmp/sliver_attrib`` arms carry."""
    with pytest.raises(SystemExit) as exc:
        build_mod.require_dem_prep_succeeded(None)
    msg = str(exc.value)
    assert "dem_inset_provenance" in msg
    assert "--allow-degraded-dem" in msg
    build_mod.require_dem_prep_succeeded({"insets": [], "raw": True})
    build_mod.require_dem_prep_succeeded(None, allow_degraded=True)


def _stub_layout(provenance):
    class _L:
        dem_inset_provenance = provenance
        shapes: list = []
        anchor = None

        def to_osm(self, path):
            Path(path).write_text("<?xml version='1.0'?>\n<!--stamp-->\n"
                                  "<osm></osm>\n")
            Path(str(path) + ".axes.json").write_text("{}")
    return _L()


def _run_build_patch(build_mod, monkeypatch, tmp_path, *, engine, **kw):
    """Drive ``build_patch`` with a stub engine, so the whole refusal path
    runs in-process (no X-Plane, no network, no build)."""
    repo, lane = _lock_repo(tmp_path)
    pipeline = types.ModuleType("auto_patch.pipeline")
    pipeline.build_airport_pavement = engine
    conftest_stub = types.ModuleType("conftest")
    conftest_stub.xplane_root = lambda: str(tmp_path / "xplane")
    monkeypatch.setitem(sys.modules, "auto_patch.pipeline", pipeline)
    monkeypatch.setitem(sys.modules, "conftest", conftest_stub)
    out = tmp_path / "out"
    prog = build_mod.Progress(out / "twin.progress")
    guard = build_mod.SharedRepoWriteGuard(set(), lane, repo=repo)
    return build_mod.build_patch("HECA", lane, out, "twin", prog,
                                 write_guard=guard, allow_no_sidecar=True,
                                 **kw), out, repo


def test_a_GUARD_BLOCKED_PREP_the_engine_swallowed_never_exits_0(
        build_mod, monkeypatch, tmp_path):
    """THE DEFECT ITSELF, end to end and in-process: the engine attempts a
    shared-repo write, the guard refuses it, the engine's own
    ``except Exception`` swallows the refusal and returns a DEM-less
    layout.  Before this twin that combination exited 0 and a lane spent
    two builds measuring it."""
    def engine(icao, xplane_root, **kw):
        try:                       # elevation._load_airport_dem's shape
            os.open(str(tmp_path / "repo" / "Elevation_data" / "+30+030"
                        / "N30E031.hgt"), os.O_CREAT | os.O_WRONLY)
        except Exception:
            pass                   # ← the whole defect, in one line
        return _stub_layout(None)

    with pytest.raises(SystemExit) as exc:
        _run_build_patch(build_mod, monkeypatch, tmp_path, engine=engine)
    msg = str(exc.value)
    assert "N30E031.hgt" in msg
    assert "--allow-degraded-dem" in msg
    assert not (tmp_path / "out" / "twin.osm").exists(), (
        "a DEM-less patch must never land in the output directory, where a "
        "later census would pick it up by name")


def test_the_same_build_PROCEEDS_and_is_RECORDED_under_the_flag(
        build_mod, monkeypatch, tmp_path):
    def engine(icao, xplane_root, **kw):
        try:
            os.open(str(tmp_path / "repo" / "Elevation_data" / "+30+030"
                        / "N30E031.hgt"), os.O_CREAT | os.O_WRONLY)
        except Exception:
            pass
        return _stub_layout(None)

    result, out, _repo = _run_build_patch(build_mod, monkeypatch, tmp_path,
                                          engine=engine, allow_degraded=True)
    assert (out / "twin.osm").exists()
    assert result["write_guard_blocked"], (
        "the degradation is RECORDED in the artifact, as the cold-DEM one is")
    assert result["dem_inset_provenance"] is None
    assert "DEGRADED" in (out / "twin.progress").read_text()


def test_a_CLEAN_build_that_only_took_a_LOCK_is_reported_normally(
        build_mod, monkeypatch, tmp_path):
    """The other side of the same coin: the lock allowance must let a real
    build through, and the churn is recorded rather than being either
    silent or fatal."""
    def engine(icao, xplane_root, **kw):
        lock = tmp_path / "repo" / LOCK_REL
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        os.remove(str(lock))
        return _stub_layout({"insets": [{"provider": "COPERNICUSGLO30"}],
                             "raw": False})

    result, out, _repo = _run_build_patch(build_mod, monkeypatch, tmp_path,
                                          engine=engine)
    assert (out / "twin.osm").exists()
    assert result["write_guard_blocked"] == []
    assert [c["op"] for c in result["write_guard_lock_churn"]] == [
        "os_open", "remove"]
    assert result["dem_inset_provenance"]["raw"] is False


def test_the_refusals_are_WIRED_IN_not_merely_defined(build_mod):
    """A refusal nobody calls is a comment.  ``build_patch`` runs both
    detectors before it writes anything, ``main`` hands the flag down and
    covers the ``--tile`` path (which never enters ``build_patch``), and
    the frame artifact records the flag and the churn."""
    import inspect
    bp = inspect.getsource(build_mod.build_patch)
    assert "require_no_swallowed_write_block(" in bp
    assert "require_dem_prep_succeeded(" in bp
    assert bp.index("require_dem_prep_succeeded(") < bp.index("to_osm("), (
        "the refusal must come BEFORE the patch is written")
    assert "allow_degraded" in inspect.signature(
        build_mod.build_patch).parameters
    main_src = inspect.getsource(build_mod.main)
    assert "allow_degraded=args.allow_degraded_dem" in main_src
    assert "require_no_swallowed_write_block(" in main_src, (
        "--tile does not go through build_patch and would keep the hole")
    for key in ('frame["write_guard_lock_churn"]',
                'frame["write_guard_library_index_churn"]',
                'frame["allow_degraded_dem"]'):
        assert key in main_src, f"the frame artifact omits {key}"


# ══════════════════════════════════════════════════════════════════════
# §6c ONE GUARD, TWO ENTRIES
# ══════════════════════════════════════════════════════════════════════
# Landed 2026-08-08 against a MEASURED defect: two ``run_tile_mesh_only.py``
# runs (tiles +30+031 and -13-078) silently rewrote five files inside the
# shared data repo — two airport-inset ``index.json``/``complete.json``
# pairs and a bathymetry-band ``index.json`` — while all 13 guarded
# ``build_airport.py`` runs of the same session reported the repo
# UNCHANGED.  The write law was armed by one entry and not the other.
#
# It is ONE implementation now (``harness/shared_repo_guard.py``), and
# what these twins pin is that it STAYS one: a second copy is the
# census-wrapper defect (root CLAUDE.md), invisible until two entries
# disagree about what the corpus is allowed to do.

GUARD = HARNESS / "shared_repo_guard.py"
MESH_ONLY = ROOT / "tools" / "run_tile_mesh_only.py"

#: The mesh-only entry's arming sequence, in the order it must appear.
#: Order is the point: a snapshot taken after the build, a prefetch joined
#: after the guard came down, or a detector run before the audit each
#: reports a clean run over a corpus that changed.
_MESH_ARMING_ORDER = (
    'if __name__ == "__main__":',
    "from shared_repo_guard import",
    "shared_repo_snapshot()",
    "SharedRepoWriteGuard(",
    "with guard:",
    "join_prefetches()",
    "finally:",
    "snapshot_diff(",
    "report_unauthorised_writes(",
    "require_no_swallowed_write_block(",
)


def test_exactly_ONE_file_under_tools_defines_the_write_guard():
    """The whole point of the module.  Anything that re-declares the guard
    is a second law, and two lanes then measure two corpora."""
    definers = sorted(p for p in (ROOT / "tools").rglob("*.py")
                      if "class SharedRepoWriteGuard" in p.read_text())
    assert definers == [GUARD], (
        f"the shared-repo write guard must have exactly ONE definition "
        f"({GUARD.relative_to(ROOT)}); found "
        f"{[str(p.relative_to(ROOT)) for p in definers]}")


def test_the_build_entry_IMPORTS_the_guard_and_defines_none_of_it():
    src = (HARNESS / "build_airport.py").read_text()
    assert "from shared_repo_guard import" in src, (
        "the build entry must import THE guard, not carry one")
    assert "class SharedRepoWriteGuard" not in src


def test_the_loaded_build_module_IS_the_guard_module_not_a_copy(build_mod):
    """Identity, not merely equality of names: ``build_mod.*`` and the
    guard module must be the SAME objects, so a change to the law reaches
    every caller of either spelling at once."""
    import importlib
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    guard_mod = importlib.import_module("shared_repo_guard")
    assert Path(guard_mod.__file__).resolve() == GUARD.resolve()
    for name in ("SharedRepoWriteGuard", "SharedRepoWriteBlocked",
                 "shared_repo_snapshot", "snapshot_diff", "scope_of",
                 "scope_description", "is_lock_artifact",
                 "is_library_index_artifact", "RefreshLock",
                 "record_refresh", "report_unauthorised_writes",
                 "require_no_swallowed_write_block", "REFRESH_SCOPES",
                 "SHARED_DATA_DIRS", "DATA_REPO", "BuildInputScope",
                 "tile_input_scope", "mod_cache_pack_of",
                 "mod_cache_packs_naming"):
        assert getattr(build_mod, name) is getattr(guard_mod, name), (
            f"build_airport.{name} is not the guard module's own object — "
            f"a re-export that copies is the census-wrapper defect")


def test_the_mesh_only_entry_ARMS_the_guard_in_the_right_ORDER():
    src = MESH_ONLY.read_text()
    positions = []
    for token in _MESH_ARMING_ORDER:
        assert token in src, (
            f"the mesh-only entry does not {token!r} — the 2026-08-08 "
            f"defect is exactly an entry that skipped one of these")
        positions.append(src.index(token))
    assert positions == sorted(positions), (
        f"the mesh-only arming sequence is out of order: "
        f"{dict(zip(_MESH_ARMING_ORDER, positions))}")
    assert "require_no_swallowed_write_block(guard.blocked," in src, (
        "the detector must read THIS run's guard record")
    # THE RULED OVERRIDE (2026-09-10): the mesh-only entry carries the same
    # --allow-degraded-dem the build entry does — a degraded frame accepted
    # KNOWINGLY, on the record — and it must reach the detector rather than
    # be parsed and dropped, which would silently restore the refusal.
    assert "--allow-degraded-dem" in src, (
        "the mesh-only entry must offer the ruled degraded-frame override")
    assert "allow_degraded=allow_degraded" in src, (
        "the override must be PASSED to the swallowed-block detector")
    assert src.index("--allow-degraded-dem") < src.index(
        "require_no_swallowed_write_block(guard.blocked,"), (
        "the flag must be read before the detector runs")
    assert "--refresh-data" in src and "e9daef5" in src, (
        "the refusal must name the deliberate act and cite its ruling")


def test_the_mesh_only_entry_DEFINES_none_of_the_law():
    src = MESH_ONLY.read_text()
    for definition in ("class SharedRepoWriteGuard", "def shared_repo_snapshot",
                       "def snapshot_diff", "def report_unauthorised_writes",
                       "def require_no_swallowed_write_block",
                       "def scope_of", "def is_lock_artifact"):
        assert definition not in src, (
            f"{definition} is a SECOND copy of the write law")


def test_the_mesh_only_arming_is_inside_the_spawn_guard():
    """macOS spawn re-imports the main module: a worker that armed the
    guard, or audited the repo, would refuse and report on the parent's
    behalf.  Everything new therefore sits under ``__main__``."""
    src = MESH_ONLY.read_text()
    main_at = src.index('if __name__ == "__main__":')
    for token in _MESH_ARMING_ORDER[1:]:
        assert src.index(token) > main_at, (
            f"{token!r} runs at import time — every spawned worker would "
            f"arm and audit")


def test_the_mesh_only_entry_has_no_refresh_mechanism_of_its_own():
    """Refreshes are ``build_airport.py --refresh-data``: locked,
    hash-stamped, recorded.  A second way to authorise a shared-repo write
    is a second law (ruling e9daef5)."""
    src = MESH_ONLY.read_text()
    assert "RefreshLock" not in src and "record_refresh" not in src
    assert "add_argument" not in src, "the CLI stays two positional args"


# ══════════════════════════════════════════════════════════════════════
# §6d THE GUARD FOLLOWS THE BUILD, NOT THE ENTRY
# ══════════════════════════════════════════════════════════════════════
# Landed 2026-08-11 against a MEASURED defect of the same shape as §6c's,
# one tool further out: ``tools/classify_report.py`` BUILDS an airport and
# armed neither half of the protection, and two adjudication runs wrote ten
# files into the shared corpus (``Airport_mod_cache`` sidecars and DSFTool
# dumps under ``+35-081`` and ``+39-095``) while every guarded build of the
# same session reported the repo unchanged — and cross-attributed a
# CONTAMINATED flag onto an unrelated lane's run.
#
# The second measured fact, and the reason the redirect is not enough on
# its own: the mod-cache overlay was SYMLINK-SEEDED, and an unguarded
# writer wrote THROUGH the symlinks into the shared file (seeding is
# copy-on-write since 2026-08-12).  Redirect and guard are
# one composition (``arm_shared_repo_protection``), and these twins pin
# that this tool arms it rather than a private arrangement of the parts.

CLASSIFY = ROOT / "tools" / "classify_report.py"


@pytest.fixture(scope="module")
def classify_mod():
    return _load("harness_twin_classify", CLASSIFY)


class _StubLayout:
    """What ``build_airport_pavement`` hands back, shadow keys only."""

    pavement_score_summary = {"mode": "shadow", "shapes": 1, "agree": 1,
                              "disagree": 0, "low": 0, "reliability": {}}
    pavement_score_decisions = [{"legacy": "APRON", "winner": "APRON"}]


def _fake_corpus(tmp_path, monkeypatch, guard_mod, classify_mod):
    """A fake shared repo, wired into EVERY module that reads the global.

    ``guard_mod.DATA_REPO`` is what a default-constructed guard defends;
    the BUILD ENTRY's ``DATA_REPO`` is what the mod-cache overlay is seeded
    from.  Patching one and not the other runs the test against the REAL
    corpus (the ``guard_mod`` fixture's docstring records that happening),
    and the build entry to patch is the instance ``classify_report``
    ITSELF imports — this file's ``build_mod`` fixture loads a second copy
    under another name, whose globals nothing in the tool ever reads.
    """
    repo = tmp_path / "repo"
    (repo / "Airport_mod_cache" / "packA").mkdir(parents=True)
    (repo / "Airport_mod_cache" / "packA" / "warm.cache").write_bytes(b"warm")
    (repo / "Elevation_data").mkdir(parents=True)
    monkeypatch.setattr(guard_mod, "DATA_REPO", repo)
    monkeypatch.setattr(classify_mod._harness_build_module(),
                        "DATA_REPO", repo)
    monkeypatch.delenv("ORTHO4XP_DATA_ROOT", raising=False)
    import O4_File_Names as FNAMES
    monkeypatch.setattr(FNAMES, "_data_root_override", None)
    return repo


def _patch_engine_build(monkeypatch, fn):
    """Replace the engine entry ``classify_report`` calls."""
    import auto_patch.pipeline as pipeline
    monkeypatch.setattr(pipeline, "build_airport_pavement", fn)


def test_the_classify_entry_ARMS_the_composition_and_defines_none_of_it():
    """SOURCE twin, §6c's own test applied to the third entry."""
    src = CLASSIFY.read_text()
    assert "arm_shared_repo_protection" in src, (
        "the classify entry must arm the harness's OWN composition — it "
        "builds an airport, and an unguarded build wrote the corpus twice "
        "on 2026-08-11")
    assert "require_no_swallowed_write_block" in src, (
        "a refusal the engine swallowed is itself the finding")
    for definition in ("class SharedRepoWriteGuard",
                       "def arm_shared_repo_protection",
                       "def redirect_engine_caches",
                       "def require_no_swallowed_write_block",
                       "def mirror_tree_as_overlay",
                       "def mirror_tree_as_symlinks",
                       "os.environ[\"O4_DSF_CACHE_DIR\"]",
                       "os.environ[\"O4_AIRPORT_MOD_CACHE_DIR\"]",
                       "os.environ[\"O4_MASKS_DIR\"]"):
        assert definition not in src, (
            f"{definition} is a SECOND copy of the write law / the redirect")
    assert "e9daef5" in src, "the guarded path must cite its ruling"
    row = [ln for ln in INDEX.read_text().splitlines()
           if "tools/classify_report.py`" in ln]
    assert row and "arm_shared_repo_protection" in row[0], (
        "the index row must state that this tool's build path is guarded — "
        "the next lane reaches for it from the index, and 'does it touch "
        "the corpus' is exactly what it needs to know before running it")


def test_the_classify_build_path_ARMS_guard_AND_redirect(
        classify_mod, guard_mod, tmp_path, monkeypatch):
    """BEHAVIOURAL twin: both halves are live DURING the build call.

    Asserted from inside the engine entry — a redirect or a guard that is
    only installed in the caller's imagination is exactly the class the
    session detector kept catching.
    """
    import builtins
    repo = _fake_corpus(tmp_path, monkeypatch, guard_mod, classify_mod)
    seen = {}
    # The suite's OWN autouse guard already replaced ``builtins.open``, so
    # "open is patched" proves nothing here; what must be true is that THIS
    # CALL installed another interception on top of it.
    outer_open = builtins.open

    def _fake_build(icao, xplane_root, **kw):
        seen["icao"] = icao
        seen["guard_live"] = builtins.open is not outer_open
        seen["dsf"] = os.environ.get("O4_DSF_CACHE_DIR")
        seen["mod"] = os.environ.get("O4_AIRPORT_MOD_CACHE_DIR")
        return _StubLayout()

    _patch_engine_build(monkeypatch, _fake_build)
    # The DERIVED roots are LANE-PERSISTENT (perf P2): pin them into
    # ``tmp_path`` so the twin stays hermetic instead of deriving into the
    # checkout's own ``tmp/engine_caches``.
    lane_cache = tmp_path / "lanecache"
    monkeypatch.setenv("O4_LANE_CACHE_ROOT", str(lane_cache))
    entry = _cache_env_entry_values()
    try:
        report = classify_mod.build_report("KCLT", "/X-Plane",
                                           out_dir=tmp_path / "out")
    finally:
        _restore_cache_env(entry)

    base = tmp_path / "out" / "classify_KCLT.engine_caches"
    assert seen["icao"] == "KCLT"
    assert seen["guard_live"], (
        "the build ran OUTSIDE the write guard — the overlay alone does "
        "not save you: writers wrote THROUGH the seeded symlinks, and the "
        "guard is what catches whatever the seeding does not")
    assert seen["dsf"] == str(lane_cache / "Default_DSF_cache"), (
        "the DSFTool SUBPROCESS inherits the environment; that is the only "
        "handle on a write no Python-level guard can see")
    overlay = lane_cache / "Airport_mod_cache"
    assert seen["mod"] == str(overlay)
    assert report["write_guard_armed"] is True
    assert report["write_guard_blocked"] == []
    assert report["engine_cache_redirects"]["base"] == str(base)
    assert report["summary"]["shapes"] == 1 and len(report["decisions"]) == 1

    # Item 2: REAL directories, COPY-ON-WRITE files.  A symlinked
    # DIRECTORY would send every write inside it back into the shared
    # corpus; a symlinked FILE did exactly that until 2026-08-12, because
    # the sidecar writers truncate the path in place.
    assert overlay.is_dir() and not overlay.is_symlink()
    pack = overlay / "packA"
    assert pack.is_dir() and not pack.is_symlink()
    entry = overlay / "packA" / "warm.cache"
    shared = repo / "Airport_mod_cache" / "packA" / "warm.cache"
    assert not entry.is_symlink() and entry.read_bytes() == shared.read_bytes()
    with open(entry, "wb") as handle:
        handle.write(b"rebuilt by the writer's own pattern")
    assert shared.read_bytes() != b"rebuilt by the writer's own pattern"


def test_the_classify_build_path_REFUSES_a_shared_corpus_write(
        classify_mod, guard_mod, tmp_path, monkeypatch):
    """A corpus write attempted DURING the build is refused at the call.

    The measured writes were mod-cache sidecars and DSFTool dumps; an
    inset is used here because it is the scope no redirect covers, so it
    can only be the guard that stops it.
    """
    repo = _fake_corpus(tmp_path, monkeypatch, guard_mod, classify_mod)
    target = repo / "Elevation_data" / "N30E031.hgt"

    def _writing_build(icao, xplane_root, **kw):        # pragma: no cover
        open(target, "w").write("regenerated mid-build")
        return _StubLayout()

    _patch_engine_build(monkeypatch, _writing_build)
    entry = _cache_env_entry_values()
    try:
        with pytest.raises(guard_mod.SharedRepoWriteBlocked) as exc:
            classify_mod.build_report("KCLT", "/X-Plane",
                                      out_dir=tmp_path / "out")
    finally:
        _restore_cache_env(entry)
    assert "N30E031.hgt" in str(exc.value) and "dem" in str(exc.value)
    assert "--refresh-data" in str(exc.value)
    assert not target.exists(), "the guard must prevent, not just report"


def test_the_classify_build_path_REFUSES_a_SWALLOWED_refusal(
        classify_mod, guard_mod, tmp_path, monkeypatch):
    """The engine catches the refusal and returns anyway — rc must not be 0.

    ``auto_patch.elevation._load_airport_dem`` wraps production's whole DEM
    prep in one ``except Exception``, so a blocked write becomes a WARN and
    a silently degraded layout.  A classification report built on that
    layout is not production's frame either.
    """
    repo = _fake_corpus(tmp_path, monkeypatch, guard_mod, classify_mod)
    target = repo / "Elevation_data" / "N30E031.hgt"

    def _swallowing_build(icao, xplane_root, **kw):
        try:
            open(target, "w").write("regenerated mid-build")
        except Exception:                     # the engine's own fallback
            pass
        return _StubLayout()

    _patch_engine_build(monkeypatch, _swallowing_build)
    entry = _cache_env_entry_values()
    try:
        with pytest.raises(SystemExit) as exc:
            classify_mod.build_report("KCLT", "/X-Plane",
                                      out_dir=tmp_path / "out")
    finally:
        _restore_cache_env(entry)
    assert "N30E031.hgt" in str(exc.value)
    assert "REFUSING" in str(exc.value)


def test_the_classify_from_json_path_ARMS_NOTHING(
        classify_mod, tmp_path, monkeypatch):
    """``--from-json`` builds nothing, so it guards nothing (item 3).

    It must not import the harness, must not move the cache environment,
    and must not create the build path's artifact directory — a render is
    a render.
    """
    def _boom():                                        # pragma: no cover
        raise AssertionError("the render path armed the build machinery")

    monkeypatch.setattr(classify_mod, "_harness_build_module", _boom)
    monkeypatch.setattr(classify_mod, "ARTIFACT_DIR", tmp_path / "artifacts")
    monkeypatch.setenv("O4_PAVEMENT_SCORE_V2", "shadow")
    dump = tmp_path / "dump.json"
    dump.write_text(json.dumps({"airports": [
        {"icao": "KCLT", "summary": _StubLayout.pavement_score_summary,
         "decisions": list(_StubLayout.pavement_score_decisions)}]}))

    entry = _cache_env_entry_values()
    assert classify_mod.main(["--from-json", str(dump)]) == 0
    assert _cache_env_entry_values() == entry, (
        "the render path moved the engine cache redirect")
    assert not (tmp_path / "artifacts").exists(), (
        "a render leaves no build artifacts")


# ══════════════════════════════════════════════════════════════════════
# §7 THE MAGNITUDE BANDS (census --magnitude-bands)
# ══════════════════════════════════════════════════════════════════════
# Promoted 2026-08-06 (RULINGS 7e90032, promote-on-reuse): two lanes had
# bucketed census rows by |de| by hand — the c6attr ownership ranking and
# the c6tip frame of record ("0.1-1 m 13,711 = 45.1 %, 1-10 m 11,143 =
# 36.7 %, 82 % is in-band airside solver residual").  A hand copy of that
# bucketing is the census-wrapper defect at one remove: it re-states the
# population's shape, so a band that silently drops rows misroutes the
# work the ranking is FOR.


class _BandRow:
    """A census row with a known magnitude and an airside role pair."""

    class _W:
        def __init__(self, role):
            self.tags = {"role": role}

    def __init__(self, de, role="apron"):
        self.de_m = de
        self.way_a = self._W(role)
        self.way_b = self._W(role)


def test_the_magnitude_bands_partition_the_population(census_mod, cg):
    """KNOWN-ANSWER TWIN.  Ten rows straddling every default edge, two per
    band by construction — and the bands must sum to the census total, or
    the table is describing a different population than the number above
    it (the two-instruments trap inside one report)."""
    mags = [0.0, 0.005, 0.01, 0.099, 0.1, 0.9, 1.0, 9.99, 10.0, 250.0]
    rows = [("within_shape", _BandRow(m)) for m in mags]
    rep = census_mod.magnitude_bands(rows, cg)
    assert [b["label"] for b in rep["bands"]] == [
        "<0.01", "0.01-0.1", "0.1-1", "1-10", ">=10"]
    assert [b["n"] for b in rep["bands"]] == [2, 2, 2, 2, 2]
    assert sum(b["n"] for b in rep["bands"]) == rep["total"] == len(rows)
    assert rep["bands"][-1]["worst_m"] == 250.0
    assert rep["bands"][0]["below_materiality"] is True, (
        "the sub-0.01 m tail is the convergence guard's floor and must be "
        "its own band, never mixed into a real one")
    assert rep["bands"][2]["airside"] == 2
    assert rep["by_family"]["within_shape"]["0.1-1"] == 2


def test_a_row_lands_in_exactly_one_band_at_every_edge(census_mod, cg):
    """Edge semantics, pinned: a row ON an edge belongs to the band ABOVE
    it (``lo <= x < hi``), and the top band is open."""
    for mag, expected in ((0.01, "0.01-0.1"), (0.1, "0.1-1"),
                          (1.0, "1-10"), (10.0, ">=10"),
                          (0.009999, "<0.01")):
        rep = census_mod.magnitude_bands(
            [("within_shape", _BandRow(mag))], cg)
        hit = [b["label"] for b in rep["bands"] if b["n"]]
        assert hit == [expected], f"{mag} m landed in {hit}, not {expected}"


def test_the_band_edges_are_configurable_and_validated(census_mod, cg):
    assert census_mod.parse_band_edges(None) == (0.01, 0.1, 1.0, 10.0)
    assert census_mod.parse_band_edges("") == (0.01, 0.1, 1.0, 10.0)
    assert census_mod.parse_band_edges("0.5, 5") == (0.5, 5.0)
    assert census_mod.band_labels((0.5, 5.0)) == ["<0.5", "0.5-5", ">=5"]
    rep = census_mod.magnitude_bands(
        [("within_shape", _BandRow(m)) for m in (0.4, 0.6, 6.0)],
        cg, edges=(0.5, 5.0))
    assert [b["n"] for b in rep["bands"]] == [1, 1, 1]
    for bad in ("1,0.5", "0.1,0.1", "-1", "0", "1,x"):
        with pytest.raises(SystemExit):
            census_mod.parse_band_edges(bad)


def test_the_bands_carry_the_laws_own_deferred_split(census_mod, cg):
    """Instruments report, the law adjudicates (RULINGS d48bc0a).  A band
    table that folded the version-deferred rows into its counts would
    re-adjudicate them in a footnote."""
    deferred_key = sorted(cg.VERSION_DEFERRED_FAMILIES)[0]
    other = next(k for k, _t, _b in cg.LAW_FAMILIES
                 if k not in cg.VERSION_DEFERRED_FAMILIES)
    rows = [(deferred_key, _BandRow(0.5)), (other, _BandRow(0.5)),
            (other, _BandRow(5.0))]
    rep = census_mod.magnitude_bands(rows, cg)
    band = next(b for b in rep["bands"] if b["label"] == "0.1-1")
    assert (band["n"], band["deferred"], band["adjudicated"]) == (2, 1, 1)
    assert sum(b["deferred"] for b in rep["bands"]) == \
        cg.adjudication(rows)["deferred_total"], (
        "the band table and the adjudication split must agree on the "
        "deferred population — two readers, one population")


def test_the_bands_never_re_run_a_check(census_mod):
    """The bands are a second READER of the rows the census already has.
    A band section that re-ran the law would be a second instrument, and
    two instruments on one assumed population is this repo's dominant
    analysis failure."""
    src = inspect.getsource(census_mod.magnitude_bands)
    for forbidden in ("run_checks", "load_check_grade", "_parse_osm"):
        assert forbidden not in src, (
            f"magnitude_bands calls {forbidden} — it must only read the "
            f"rows census_one already produced")


def test_the_band_flag_runs_through_the_census_cli(census_mod, tmp_path):
    """END TO END through the one code path: the CLI flag, the law-true
    frame, the JSON report.  A flag that only works when called as a
    function is a flag no lane will use."""
    osm = tmp_path / "p.osm"
    osm.write_text("<osm version='0.6'></osm>")
    (tmp_path / "p.osm.axes.json").write_text(json.dumps({"anchor": None}))
    out = tmp_path / "census.json"
    assert census_mod.main([str(osm), "--magnitude-bands",
                            "--json", str(out), "--quiet"]) == 0
    rep = json.loads(out.read_text())
    mb = rep["magnitude_bands"]
    assert mb["edges_m"] == [0.01, 0.1, 1.0, 10.0]
    assert len(mb["bands"]) == 5 and mb["total"] == rep["lawtrue"]["total"]
    # ...and custom edges arrive intact.
    assert census_mod.main([str(osm), "--magnitude-bands", "0.05,5",
                            "--json", str(out), "--quiet"]) == 0
    assert json.loads(out.read_text())["magnitude_bands"]["edges_m"] == \
        [0.05, 5.0]
    # ...and without the flag the section is absent, not empty.
    assert census_mod.main([str(osm), "--json", str(out), "--quiet"]) == 0
    assert "magnitude_bands" not in json.loads(out.read_text())


def test_the_census_flag_is_in_the_tool_index():
    """Every promotion lands WITH its index row, in the same commit."""
    text = INDEX.read_text()
    assert "--magnitude-bands" in text, (
        "the promoted flag is not in tools/INDEX.md — a tool (or a flag "
        "that replaces a lane script) absent from the index is treated as "
        "absent, and gets written by hand again")


# ══════════════════════════════════════════════════════════════════════
# §8 THE SUITE DOES NOT WRITE INTO THE SHARED DATA REPO (ruling e9daef5)
# ══════════════════════════════════════════════════════════════════════
# Measured 2026-08-06: 529 of the 530 directories in the shared
# ``Default_DSF_cache`` were minted by ``tests/test_dsf_texture_modes.py``
# — ``decode_dsf`` caches DSFTool's dump under a key derived from the
# DSF's absolute path, and those tests emit into ``tmp_path``, so every
# run created a directory nothing would ever read again.  It never failed
# anything: the corpus every lane mounts just grew.
#
# Closed structurally 2026-08-08 (suite-corpus-clean lane): both writable
# cache roots are ENV-OVERRIDDEN to lane-local homes (so a module reload
# recomputes the redirect instead of undoing it, and a SUBPROCESS's write
# lands there too), the mod-cache root is a COPY-ON-WRITE read-through
# overlay (warm reads, lane-local writes even under a truncate-in-place
# writer — symlink seeding was not, 2026-08-12), every test runs inside a
# refusing
# ``SharedRepoWriteGuard``, and the allowance register is EMPTY.  The twins
# below are the known answers for each of those.

def _conftest():
    sys.path.insert(0, str(Path(__file__).parent))
    import conftest
    return conftest


def test_the_dsf_dump_cache_is_not_the_shared_repo_during_tests(build_mod):
    """THE REDIRECT, asserted live inside a running test."""
    import O4_File_Names as FNAMES
    cache = Path(FNAMES.Default_dsf_cache_dir).resolve()
    repo = Path(build_mod.DATA_REPO).resolve()
    assert repo not in cache.parents and cache != repo, (
        f"the DSFTool dump cache points into the shared data repo "
        f"({cache}) while tests run — this is the leak that minted 529 "
        f"junk directories there")


def test_the_osm_clip_store_is_not_the_shared_repo_during_tests(build_mod):
    """THE THIRD REDIRECT, asserted live inside a running test.

    The leak this closes is the osmium-tool SUBPROCESS's clip tmp file
    (``_regional_extracts/clips/<clip>-part0.osm.pbf.tmp-<pid>-<tid>``),
    which no Python-level guard can intercept: eight of them, 11.3 MB
    each, were sitting in the shared corpus when this landed, and the
    newest was written inside a full suite whose session detector then
    errored on all eighteen workers.  See the conftest fixture for the
    full mechanism.
    """
    import O4_OSM_Extracts as EXTRACTS
    store = Path(EXTRACTS.STORE_DIRECTORY).resolve()
    repo = Path(build_mod.DATA_REPO).resolve()
    assert repo not in store.parents and store != repo, (
        f"the OSM regional-extract store points into the shared data "
        f"repo ({store}) while tests run — the osmium subprocess writes "
        f"its clip tmp file there and no Python guard can see it")


def test_the_airport_mod_cache_root_honours_its_env_override(
        tmp_path, monkeypatch):
    """KNOWN-ANSWER TWIN for the accessor (spec §8.2 R-b), all four states.

    The cwd-following arm is the load-bearing one:
    ``dsf_reader.airport_mod_cache_dir``'s docstring marks it legacy
    behaviour that must never be cached at import time, and an override
    that froze it would move every pack sidecar of every build that
    chdirs.
    """
    import O4_File_Names as FNAMES
    monkeypatch.setattr(FNAMES, "_data_root_override", None)
    monkeypatch.delenv("ORTHO4XP_DATA_ROOT", raising=False)

    overlay = str(tmp_path / "overlay")
    monkeypatch.setenv("O4_AIRPORT_MOD_CACHE_DIR", overlay)
    assert FNAMES.airport_mod_cache_root() == overlay

    monkeypatch.delenv("O4_AIRPORT_MOD_CACHE_DIR")
    assert FNAMES.airport_mod_cache_root() == FNAMES.data_path(
        "Airport_mod_cache")
    monkeypatch.chdir(tmp_path)
    assert FNAMES.airport_mod_cache_root() == str(
        tmp_path / "Airport_mod_cache"), "resolved at CALL time, per cwd"

    # An explicitly chosen data root is the more specific instruction:
    # lifting one cache family out of it would split the root.
    monkeypatch.setenv("O4_AIRPORT_MOD_CACHE_DIR", overlay)
    monkeypatch.setenv("ORTHO4XP_DATA_ROOT", str(tmp_path / "chosen"))
    assert FNAMES.airport_mod_cache_root() == str(
        tmp_path / "chosen" / "Airport_mod_cache")


def test_the_mod_cache_overlay_seeds_COPY_ON_WRITE_not_symlinks(tmp_path):
    """KNOWN-ANSWER TWIN for the overlay's pure core (spec §8.4), on the
    property the whole scheme rests on.

    THE MEASURED DEFECT (2026-08-12, three times in one session — two SQ2
    classify runs, the r18 KMCI overlay, the r20 parallel arms, seven OTHH
    sidecars rewritten).  This overlay used to seed FILE SYMLINKS, on the
    argument that the sidecar writers ``os.replace`` a temp file onto the
    name and so REPLACE the link.  Some do.  The ones that matter open the
    path as ``open(path, "wb")`` — a truncate IN PLACE, which follows the
    link and empties the SHARED file.  So the arm that decides this test is
    the truncating write: the overlay entry must change and the source must
    come back byte-identical.  Restore symlink seeding and that arm fails.

    Directories stay REAL for the same reason they always were (a
    symlinked directory sends every write inside it into the corpus), and
    the warm READ arm is the overlay's whole purpose — an overlay that is
    safe but cold is a different measurement, not a cleaner one.
    """
    conftest = _conftest()
    source = tmp_path / "shared"
    (source / "sub").mkdir(parents=True)
    (source / "empty").mkdir()
    (source / "top.cache").write_bytes(b"warm")
    (source / "sub" / "inner.cache").write_bytes(b"deep")
    overlay = tmp_path / "overlay"

    made = conftest.mirror_tree_as_overlay(str(source), str(overlay))
    assert made["dirs"] == 2 and made["files"] == 2
    assert made["cloned"] + made["copied"] == 2, (
        "every seeded file is either a clone or a real copy — there is no "
        "third, cheaper seeding mode that keeps the guarantee")
    assert (overlay / "sub").is_dir() and not (overlay / "sub").is_symlink()
    assert (overlay / "empty").is_dir()

    # NOT LINKS OF ANY KIND: not a symlink (which a write follows), and not
    # a hardlink (whose inode a truncating write empties just as thoroughly).
    for rel in ("top.cache", "sub/inner.cache"):
        assert not (overlay / rel).is_symlink(), f"{rel} seeded as a symlink"
        assert (overlay / rel).stat().st_ino != (source / rel).stat().st_ino, (
            f"{rel} shares the shared file's INODE — a hardlink does not "
            f"survive truncate-in-place either")

    # WARM READS — the overlay's purpose.
    assert (overlay / "top.cache").read_bytes() == b"warm"
    assert (overlay / "sub" / "inner.cache").read_bytes() == b"deep"

    # THE DECIDING ARM: the engine's actual write pattern.
    before = (source / "top.cache").stat()
    with open(overlay / "top.cache", "wb") as handle:
        handle.write(b"rebuilt in place")
    assert (overlay / "top.cache").read_bytes() == b"rebuilt in place"
    assert (source / "top.cache").read_bytes() == b"warm", (
        "open(path, 'wb') TRUNCATES IN PLACE — with symlink seeding it "
        "followed the link and emptied the shared corpus file")
    after = (source / "top.cache").stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size,
                                                    after.st_mtime_ns)

    # …and the ``os.replace`` writers, which were always safe, still are.
    (overlay / "fresh.tmp").write_bytes(b"replaced")
    os.replace(str(overlay / "fresh.tmp"), str(overlay / "sub" / "inner.cache"))
    assert (overlay / "sub" / "inner.cache").read_bytes() == b"replaced"
    assert (source / "sub" / "inner.cache").read_bytes() == b"deep"

    missing = conftest.mirror_tree_as_overlay(
        str(tmp_path / "absent"), str(tmp_path / "overlay2"))
    assert missing["dirs"] == 0 and missing["files"] == 0
    assert (tmp_path / "overlay2").is_dir(), (
        "a corpus with no cache yet is a lawful state, not an error")


def test_the_overlay_seeding_offers_NO_symlink_mode(build_mod):
    """SOURCE twin: the defect was a seeding mode, so the fix is the
    absence of one.  A fallback that symlinks "when cloning is
    unavailable" would reintroduce the whole class on the first machine
    that took it, and silently — the write-through leaves no log line."""
    src = inspect.getsource(build_mod.mirror_tree_as_overlay)
    assert "os.symlink" not in src, (
        "no symlink seeding, not even as a fallback: a mode that cannot "
        "keep the guarantee is the defect, not a cheaper overlay")
    assert "os.link" not in src, (
        "a hardlink shares the inode, and the measured writers truncate "
        "IN PLACE — it protects nothing")
    assert "clonefile" in src and "copyfile" in src, (
        "clone first, real copy as the lawful fallback")


def _cache_env_entry_values():
    return {k: os.environ.get(k) for k in ("O4_DSF_CACHE_DIR",
                                           "O4_AIRPORT_MOD_CACHE_DIR",
                                           "O4_MASKS_DIR")}


def _restore_cache_env(entry):
    """Put the SESSION's redirect back and recompute from it.

    This test runs inside the suite whose session fixtures own those two
    variables; leaving them pointed at a ``tmp_path`` would re-break the
    redirect for every later test on this worker — the exact reload class
    ``conftest.reapply_dsf_dump_cache_redirect`` exists for.
    """
    for key, value in entry.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    import O4_File_Names as FNAMES
    FNAMES._apply_data_root()


# ══════════════════════════════════════════════════════════════════════
# §6e-bis THE LANE-PERSISTENT DERIVED-CACHE ROOT (perf P2, Lane A)
#
# THE MEASURED DEFECT (2026-08-13): the redirect was per-RUN, so everything
# the engine derived inside a lane build was thrown away with the run.  At
# HECA that is `_compute_dsf_object_buildings` — 66.6 s of OBJ8 parse and
# O(n²) contact-graph partition, re-run by every lane build forever (OTHH
# ~455 s).  Seeding from the shared corpus does not save it: the pack's own
# `.obj` files are IN the footprint fingerprint and the Phase-2 y-bake
# rewrites them AFTER that run's sidecar is written, so the shared sidecar
# is stale for anyone who comes later (HECA: sidecar 07:03, 376 of 568
# `.obj` rewritten 07:14).  What makes run 2 hit is run 1's OWN sidecar
# still existing.
# ══════════════════════════════════════════════════════════════════════

def test_the_lane_cache_root_is_per_worktree_and_env_overridable(
        tmp_path, monkeypatch, build_mod):
    """KNOWN-ANSWER TWIN for the root itself — pure, no environment state
    beyond the one variable it publishes."""
    monkeypatch.delenv("O4_LANE_CACHE_ROOT", raising=False)
    lane = tmp_path / "worktreeA" / "Ortho4XP"
    other = tmp_path / "worktreeB" / "Ortho4XP"
    assert build_mod.lane_cache_root(lane) == lane / "tmp" / "engine_caches"
    assert build_mod.lane_cache_root(other) != build_mod.lane_cache_root(lane), (
        "ONE ROOT PER WORKTREE: two lanes sharing a derived cache would be "
        "two lanes on one private corpus, which is the ruling e9daef5 "
        "forbids in the other direction")

    monkeypatch.chdir(tmp_path)
    assert build_mod.lane_cache_root() == (
        tmp_path / "tmp" / "engine_caches"), (
        "with no lane named the BUILD CWD is the lane — the build entry "
        "has already refused any other cwd")

    monkeypatch.setenv("O4_LANE_CACHE_ROOT", str(tmp_path / "elsewhere"))
    assert build_mod.lane_cache_root(lane) == tmp_path / "elsewhere", (
        "the override is the twins' seam and a lane's escape hatch")


def test_the_persistent_derived_root_is_REUSED_across_runs(
        tmp_path, monkeypatch, build_mod):
    """THE INTERVENTION, in miniature: two runs, two DIFFERENT ``--out``
    tags, ONE derived-cache root — and what run 1 derived is still there
    for run 2, while the masks overlay stays per-run."""
    import O4_File_Names as FNAMES
    repo = tmp_path / "repo"
    (repo / "Airport_mod_cache" / "packA").mkdir(parents=True)
    (repo / "Airport_mod_cache" / "packA" / "warm.cache").write_bytes(b"warm")
    (repo / "Masks").mkdir(parents=True)
    monkeypatch.setattr(build_mod, "DATA_REPO", repo)
    monkeypatch.setattr(FNAMES, "_data_root_override", None)
    monkeypatch.delenv("ORTHO4XP_DATA_ROOT", raising=False)
    lane = tmp_path / "lane"
    monkeypatch.setenv("O4_LANE_CACHE_ROOT", str(lane / "tmp"
                                                 / "engine_caches"))

    entry = _cache_env_entry_values()
    try:
        rec1 = build_mod.redirect_engine_caches(tmp_path / "out", "RUN1")
        derived = Path(rec1["derived_base"])
        # RUN 1 derives a sidecar the shared corpus does not have.
        made = Path(rec1["airport_mod_cache"]) / "packA" / "derived.cache"
        made.write_bytes(b"66.6 seconds of contact-graph partition")

        rec2 = build_mod.redirect_engine_caches(tmp_path / "out", "RUN2")
        assert rec2["derived_base"] == str(derived), (
            "the derived root does not move with the run's tag")
        assert rec2["dsf_dump_cache"] == rec1["dsf_dump_cache"]
        assert rec2["airport_mod_cache"] == rec1["airport_mod_cache"]
        assert made.read_bytes() == b"66.6 seconds of contact-graph partition", (
            "RUN 2 SEES RUN 1's WORK — this is the entire feature; the "
            "re-seed must not clobber a lane-derived entry")
        assert rec2["mod_cache_seeded"]["files"] == 0, (
            "an already-seeded overlay re-seeds nothing (mirror_tree_as_"
            "overlay's lexists skip), so the warm corpus is not re-cloned "
            "every run either")

        # THE MASKS STAY PER-RUN: corpus data the engine rewrites per tile,
        # not a fingerprinted derived cache.
        assert rec1["masks"] == str(tmp_path / "out" / "RUN1.engine_caches"
                                    / "Masks")
        assert rec2["masks"] == str(tmp_path / "out" / "RUN2.engine_caches"
                                    / "Masks")
        assert rec1["masks"] != rec2["masks"]

        # AND IT IS STILL LANE-LOCAL: nothing under the derived root
        # resolves into the shared corpus, and the shared sidecar is
        # byte-untouched.
        assert repo not in derived.parents and derived.is_relative_to(lane)
        assert (repo / "Airport_mod_cache" / "packA"
                / "warm.cache").read_bytes() == b"warm"
        assert not (repo / "Airport_mod_cache" / "packA"
                    / "derived.cache").exists(), (
            "a lane's derived cache NEVER lands in the shared repo — "
            "owner ruling e9daef5, and the reason the overlay is "
            "copy-on-write rather than symlinked")
    finally:
        _restore_cache_env(entry)


def test_the_persistent_root_is_OFF_when_a_caller_asks_for_per_run(
        tmp_path, monkeypatch, build_mod):
    """``persistent=False`` restores the pre-P2 per-run root — the escape
    a caller that needs run isolation takes, spelled once."""
    import O4_File_Names as FNAMES
    repo = tmp_path / "repo"
    (repo / "Airport_mod_cache").mkdir(parents=True)
    monkeypatch.setattr(build_mod, "DATA_REPO", repo)
    monkeypatch.setattr(FNAMES, "_data_root_override", None)
    monkeypatch.delenv("ORTHO4XP_DATA_ROOT", raising=False)

    entry = _cache_env_entry_values()
    try:
        rec = build_mod.redirect_engine_caches(tmp_path / "out", "T7",
                                               persistent=False)
        base = tmp_path / "out" / "T7.engine_caches"
        assert rec["derived_base"] == str(base) == rec["base"]
        assert rec["derived_persistent"] is False
        assert rec["dsf_dump_cache"] == str(base / "Default_DSF_cache")
        assert rec["airport_mod_cache"] == str(base / "Airport_mod_cache")
    finally:
        _restore_cache_env(entry)


def test_the_harness_build_redirects_engine_caches_lane_local(
        tmp_path, monkeypatch, build_mod):
    """KNOWN-ANSWER TWIN for the build entry's engine-cache redirect.

    The measured hole (KCLT 2026-08-11): the DSFTool SUBPROCESS wrote its
    dump into the shared repo while the write guard was armed — no
    Python-level guard can intercept a subprocess — and the run was
    flagged CONTAMINATED.  The redirect rides ENV VARIABLES for that exact
    reason: a subprocess inherits them.
    """
    import O4_File_Names as FNAMES
    repo = tmp_path / "repo"
    (repo / "Airport_mod_cache" / "packA").mkdir(parents=True)
    (repo / "Airport_mod_cache" / "packA" / "warm.cache").write_bytes(b"warm")
    monkeypatch.setattr(build_mod, "DATA_REPO", repo)
    monkeypatch.setattr(FNAMES, "_data_root_override", None)
    monkeypatch.delenv("ORTHO4XP_DATA_ROOT", raising=False)

    entry = _cache_env_entry_values()
    try:
        rec = build_mod.redirect_engine_caches(tmp_path / "out", "T1",
                                               prog=None, authorised=())
        base = tmp_path / "out" / "T1.engine_caches"
        assert rec["base"] == str(base)
        # The two FINGERPRINTED roots are LANE-PERSISTENT (perf P2); the
        # per-run ``base`` still names the masks overlay.
        derived = tmp_path / "lane_caches"
        assert rec["derived_base"] == str(derived)
        assert rec["derived_persistent"] is True

        dump = derived / "Default_DSF_cache"
        assert os.environ["O4_DSF_CACHE_DIR"] == str(dump)
        assert rec["dsf_dump_cache"] == str(dump) and dump.is_dir()

        overlay = derived / "Airport_mod_cache"
        seeded = overlay / "packA" / "warm.cache"
        shared = repo / "Airport_mod_cache" / "packA" / "warm.cache"
        assert not seeded.is_symlink(), (
            "COPY-ON-WRITE seeding: a symlink is followed by the sidecar "
            "writers' truncate-in-place, straight into the shared file")
        assert seeded.read_bytes() == shared.read_bytes(), (
            "reads stay WARM on the shared sidecars")
        assert rec["mod_cache_seeded"] == {"dirs": 1, "files": 1,
                                           "cloned": 1, "copied": 0}

        # THE BELT: the engine was already imported, and
        # ``Default_dsf_cache_dir`` is computed at import time.
        assert FNAMES.Default_dsf_cache_dir == os.environ["O4_DSF_CACHE_DIR"]
        assert FNAMES.airport_mod_cache_root() == str(overlay)
        assert rec["left_shared_for_refresh"] == []
    finally:
        _restore_cache_env(entry)


def test_the_redirect_leaves_an_authorised_refresh_scope_shared(
        tmp_path, monkeypatch, build_mod):
    """An AUTHORISED refresh must land in the shared repo — redirecting it
    would turn the refresh into a silent no-op, so that half is skipped and
    creates NOTHING."""
    import O4_File_Names as FNAMES
    repo = tmp_path / "repo"
    (repo / "Airport_mod_cache" / "packA").mkdir(parents=True)
    (repo / "Airport_mod_cache" / "packA" / "warm.cache").write_bytes(b"warm")
    monkeypatch.setattr(build_mod, "DATA_REPO", repo)
    monkeypatch.setattr(FNAMES, "_data_root_override", None)
    monkeypatch.delenv("ORTHO4XP_DATA_ROOT", raising=False)

    entry = _cache_env_entry_values()
    try:
        # ARM 1: every scope authorised — nothing is redirected at all.
        rec = build_mod.redirect_engine_caches(
            tmp_path / "o1", "T2",
            authorised={"dsf_cache", "airport_mod_cache", "masks"})
        assert rec["left_shared_for_refresh"] == ["airport_mod_cache",
                                                  "dsf_cache", "masks"]
        assert rec["dsf_dump_cache"] is None and \
            rec["airport_mod_cache"] is None and rec["masks"] is None
        assert not (tmp_path / "o1" / "T2.engine_caches").exists(), (
            "a skipped half creates NOTHING")
        assert _cache_env_entry_values() == entry, (
            "no env variable moved: the refresh writes the SHARED repo")

        # ARM 2: only the dump cache is authorised — the mod cache and the
        # masks still redirect, the dump cache is left alone.
        rec2 = build_mod.redirect_engine_caches(
            tmp_path / "o2", "T3", authorised={"dsf_cache"})
        overlay = tmp_path / "lane_caches" / "Airport_mod_cache"
        masks = tmp_path / "o2" / "T3.engine_caches" / "Masks"
        assert rec2["left_shared_for_refresh"] == ["dsf_cache"]
        assert rec2["dsf_dump_cache"] is None
        assert rec2["airport_mod_cache"] == str(overlay)
        assert os.environ["O4_AIRPORT_MOD_CACHE_DIR"] == str(overlay)
        assert rec2["mod_cache_seeded"] == {"dirs": 1, "files": 1,
                                            "cloned": 1, "copied": 0}
        assert not (overlay / "packA" / "warm.cache").is_symlink()
        assert rec2["masks"] == str(masks)
        assert os.environ["O4_MASKS_DIR"] == str(masks)
        assert os.environ.get("O4_DSF_CACHE_DIR") == entry["O4_DSF_CACHE_DIR"]
        assert not (tmp_path / "lane_caches" / "Default_DSF_cache").exists()
    finally:
        _restore_cache_env(entry)


# ══════════════════════════════════════════════════════════════════════
# §6f THE MASKS ROOT IS LANE-LOCAL (owner ruling 2026-08-12b)
#
# THE MEASURED DEFECT: a HECA lane tile arm refused rc=1 — the masks step's
# legacy cleanup (``O4_Mask_Utils.delete_old_masks_in_tile``) tried to
# ``os.remove`` 16 SHARED ``Masks/+30+030/+30+031/*.png``, the write guard
# blocked all 16, and a bare ``except: pass`` swallowed every refusal so
# the stage read clean.  Every lane tile build on a warm tile refused that
# way.  Same two halves as the mod cache — an env-overridable root read at
# CALL TIME, and a copy-on-write overlay seeded from the shared subtree —
# plus the swallow site narrowed to the class it meant.
# ══════════════════════════════════════════════════════════════════════

def test_the_masks_root_honours_its_env_override(tmp_path, monkeypatch):
    """KNOWN-ANSWER TWIN for the accessor, all four states.

    The same shape as the mod cache's twin, because it is the same law:
    the override is the IMPLICIT root's, and an explicitly chosen data
    root (the packaged app's) stays the more specific instruction.
    """
    import O4_File_Names as FNAMES
    monkeypatch.setattr(FNAMES, "_data_root_override", None)
    monkeypatch.delenv("ORTHO4XP_DATA_ROOT", raising=False)

    overlay = str(tmp_path / "lane_masks")
    monkeypatch.setenv("O4_MASKS_DIR", overlay)
    assert FNAMES.masks_root() == overlay
    assert FNAMES.mask_dir(30, 31) == os.path.join(
        overlay, FNAMES.long_latlon(30, 31)), (
        "every mask path is the accessor plus the tile's own subtree")

    monkeypatch.delenv("O4_MASKS_DIR")
    assert FNAMES.masks_root() == FNAMES.data_path("Masks")
    monkeypatch.chdir(tmp_path)
    assert FNAMES.masks_root() == str(tmp_path / "Masks"), (
        "resolved at CALL time, per cwd — never captured at import")

    monkeypatch.setenv("O4_MASKS_DIR", overlay)
    monkeypatch.setenv("ORTHO4XP_DATA_ROOT", str(tmp_path / "chosen"))
    assert FNAMES.masks_root() == str(tmp_path / "chosen" / "Masks")


def test_the_masks_redirect_SURVIVES_a_module_RELOAD(tmp_path, monkeypatch):
    """THE ENV-AT-CALL-TIME PROPERTY, on the path that broke the DSF dump
    cache before it: a reload recomputed the module globals and silently
    re-pointed the cache at the shared repo.  Nothing here is computed at
    import, so there is nothing for a reload to undo."""
    import importlib
    import O4_File_Names as FNAMES
    entry = _cache_env_entry_values()
    try:
        monkeypatch.setattr(FNAMES, "_data_root_override", None)
        monkeypatch.delenv("ORTHO4XP_DATA_ROOT", raising=False)
        overlay = str(tmp_path / "lane_masks")
        monkeypatch.setenv("O4_MASKS_DIR", overlay)
        assert FNAMES.masks_root() == overlay
        importlib.reload(FNAMES)
        assert FNAMES.masks_root() == overlay, (
            "a module reload must not be able to un-redirect a lane")
        assert FNAMES.Mask_dir == overlay
    finally:
        _restore_cache_env(entry)


def test_the_Mask_dir_NAME_is_served_by_the_one_accessor(tmp_path,
                                                         monkeypatch):
    """The back-compat alias is not a SECOND spelling of the path.

    ``Mask_dir`` is read by the two entry points' working-directory
    bootstrap and by the app driver's ``getattr(FNAMES, name)`` loop.  Were
    it still a module global assigned in ``_apply_data_root``, it would be
    a call site that BYPASSES the accessor — the defect class the ruling
    names — live for exactly as long as nobody recomputed it.  PEP 562
    ``__getattr__`` serves it from :func:`masks_root` instead.
    """
    import O4_File_Names as FNAMES
    monkeypatch.setattr(FNAMES, "_data_root_override", None)
    monkeypatch.delenv("ORTHO4XP_DATA_ROOT", raising=False)
    monkeypatch.setenv("O4_MASKS_DIR", str(tmp_path / "lane_masks"))
    assert FNAMES.Mask_dir == str(tmp_path / "lane_masks")
    assert getattr(FNAMES, "Mask_dir", None) == str(tmp_path / "lane_masks")
    monkeypatch.setenv("O4_MASKS_DIR", str(tmp_path / "other"))
    assert FNAMES.Mask_dir == str(tmp_path / "other"), (
        "served at ATTRIBUTE-ACCESS time; a captured global would be stale")
    assert "Mask_dir" not in vars(FNAMES), (
        "no module global to go stale beside the accessor")
    with pytest.raises(AttributeError):
        FNAMES.Mask_dir_typo_that_does_not_exist


def test_NO_engine_module_spells_the_masks_path_itself():
    """SOURCE twin: one resolution point, threaded everywhere.

    A module that joined ``data_path("Masks")`` — or the ``Mask_dir``
    alias — onto its own path would read and delete the SHARED rasters
    while the lane thinks it is redirected, and nothing in a log line
    would say so.
    """
    offenders = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        if path.name == "O4_File_Names.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in (r'data_path\(\s*["\']Masks["\']',
                        r'\bMask_dir\b'):
            if re.search(pattern, text):
                offenders.append(f"{path.name} ({pattern})")
    assert offenders == [], (
        f"{offenders} build a masks path outside O4_File_Names.masks_root — "
        f"every mask read/write/delete goes through FNAMES.mask_dir()")


def test_the_masks_overlay_is_seeded_by_the_ONE_implementation(build_mod):
    """SOURCE twin, the same idiom as
    ``test_the_overlay_seeding_offers_NO_symlink_mode``: there is no
    masks-only seeding mode.  A symlinked mask entry is the truncate-
    through defect (#15) with a PNG on the end of it — and the guard is
    structurally blind to it, because the opened path is lane-local."""
    src = inspect.getsource(build_mod.redirect_engine_caches)
    assert "mirror_tree_as_overlay" in src and 'O4_MASKS_DIR' in src, (
        "the masks half seeds through the ONE overlay implementation")
    assert "os.symlink" not in src and "os.link" not in src, (
        "no symlink/hardlink seeding for masks either — the mask rasters "
        "are rewritten in place by the masks step")


def test_the_masks_overlay_is_seeded_PER_TILE_IN_SCOPE(tmp_path, monkeypatch,
                                                       build_mod):
    """KNOWN-ANSWER TWIN for the redirect's masks half: warm reads, real
    lane-local files, clone/copy counts reported, and the seed scoped to
    the tile the build was asked for (the whole root when none is named)."""
    import O4_File_Names as FNAMES
    repo = tmp_path / "repo"
    wanted = repo / "Masks" / FNAMES.long_latlon(30, 31)
    other = repo / "Masks" / FNAMES.long_latlon(22, 113)
    wanted.mkdir(parents=True)
    other.mkdir(parents=True)
    (wanted / "3000_5000.png").write_bytes(b"warm mask")
    (other / "9999_1111.png").write_bytes(b"another tile")
    monkeypatch.setattr(build_mod, "DATA_REPO", repo)
    monkeypatch.setattr(FNAMES, "_data_root_override", None)
    monkeypatch.delenv("ORTHO4XP_DATA_ROOT", raising=False)

    entry = _cache_env_entry_values()
    try:
        rec = build_mod.redirect_engine_caches(tmp_path / "out", "T4",
                                               tiles=[(30, 31)])
        masks = tmp_path / "out" / "T4.engine_caches" / "Masks"
        assert rec["masks"] == str(masks)
        assert os.environ["O4_MASKS_DIR"] == str(masks)
        assert rec["masks_subtrees"] == [FNAMES.long_latlon(30, 31)]
        assert rec["masks_seeded"] == {"dirs": 0, "files": 1,
                                       "cloned": 1, "copied": 0}, (
            "the counts are reported like the mod cache's — a corpus that "
            "fell back to real copies is a number in the build record")

        seeded = masks / FNAMES.long_latlon(30, 31) / "3000_5000.png"
        assert seeded.read_bytes() == b"warm mask", "reads stay WARM"
        assert not seeded.is_symlink() and seeded.stat().st_ino != (
            wanted / "3000_5000.png").stat().st_ino
        assert not (masks / FNAMES.long_latlon(22, 113)).exists(), (
            "only the tile IN SCOPE is seeded")

        # THE ACCESSOR AGREES with the redirect — the engine reads the
        # overlay, not the corpus.
        assert FNAMES.mask_dir(30, 31) == str(
            masks / FNAMES.long_latlon(30, 31))

        # No tile named: the conservative superset, the whole root.
        rec2 = build_mod.redirect_engine_caches(tmp_path / "out2", "T5")
        assert rec2["masks_subtrees"] == [""]
        assert rec2["masks_seeded"]["files"] == 2
    finally:
        _restore_cache_env(entry)


def _mask_squares(tile):
    """The exact squares ``delete_old_masks_in_tile`` walks."""
    import O4_Geo_Utils as GEO
    import O4_File_Names as FNAMES
    (x_min, y_min) = GEO.wgs84_to_orthogrid(tile.lat + 1, tile.lon,
                                            tile.mask_zl)
    (x_max, y_max) = GEO.wgs84_to_orthogrid(tile.lat, tile.lon + 1,
                                            tile.mask_zl)
    return [FNAMES.legacy_mask(x, y)
            for x in range(x_min, x_max + 1, 16)
            for y in range(y_min, y_max + 1, 16)]


def test_the_legacy_cleanup_deletes_ONLY_the_lane_local_clones(
        tmp_path, monkeypatch, build_mod):
    """THE REFUSED HECA ARM, in miniature and offline.

    Shared masks in one tree, the lane's copy-on-write overlay seeded from
    it, the redirect armed: the cleanup must empty the OVERLAY and leave
    every shared raster byte-identical.  Before the ruling this loop was
    16 ``os.remove`` calls against everyone's corpus.
    """
    import O4_File_Names as FNAMES
    import O4_Mask_Utils as MASK
    tile = types.SimpleNamespace(lat=30, lon=31, mask_zl=14)
    shared = tmp_path / "repo" / "Masks" / FNAMES.long_latlon(30, 31)
    shared.mkdir(parents=True)
    squares = _mask_squares(tile)
    assert squares, "the fixture must exercise a non-empty square walk"
    for name in squares:
        (shared / name).write_bytes(b"shared raster " + name.encode())

    monkeypatch.setattr(FNAMES, "_data_root_override", None)
    monkeypatch.delenv("ORTHO4XP_DATA_ROOT", raising=False)
    entry = _cache_env_entry_values()
    try:
        monkeypatch.setattr(build_mod, "DATA_REPO", tmp_path / "repo")
        build_mod.redirect_engine_caches(tmp_path / "out", "T6",
                                         tiles=[(30, 31)])
        dest_dir = FNAMES.mask_dir(tile.lat, tile.lon)
        assert all(os.path.isfile(os.path.join(dest_dir, n))
                   for n in squares), "the overlay seeded the whole square"

        MASK.delete_old_masks_in_tile(tile, dest_dir)

        assert not any(os.path.isfile(os.path.join(dest_dir, n))
                       for n in squares), (
            "the cleanup ran for real on the lane-local clones")
        for name in squares:
            assert (shared / name).read_bytes() == (
                b"shared raster " + name.encode()), (
                "the SHARED raster is byte-untouched — this is the whole "
                "ruling")
    finally:
        _restore_cache_env(entry)


def test_the_narrowed_cleanup_SURFACES_anything_but_a_missing_file(
        tmp_path, monkeypatch):
    """The swallow site: a missing mask stays silent, ANY other failure is
    logged.  The bare ``except: pass`` turned 16 guard refusals into a
    clean-looking stage; a swallowed refusal must never read as one."""
    import O4_Mask_Utils as MASK
    tile = types.SimpleNamespace(lat=30, lon=31, mask_zl=14)
    logged = []
    monkeypatch.setattr(MASK.UI, "lvprint",
                        lambda level, *args: logged.append(
                            " ".join(str(a) for a in args)))

    # ARM 1: nothing to delete — expected, and silent.
    MASK.delete_old_masks_in_tile(tile, str(tmp_path / "empty"))
    assert logged == [], "a missing mask is the normal case"

    # ARM 2: the guard's own refusal class (a RuntimeError, NOT an
    # OSError) — the class the bare except swallowed.
    class SharedRepoWriteBlocked(RuntimeError):
        pass

    def refuse(path):
        raise SharedRepoWriteBlocked(f"REFUSED os.remove {path}")

    # The module's OWN ``os`` reference, never the global module: a
    # process-wide ``os.remove`` patch is a booby trap for whatever else
    # runs in this worker.
    monkeypatch.setattr(MASK, "os",
                        types.SimpleNamespace(remove=refuse, path=os.path))
    MASK.delete_old_masks_in_tile(tile, str(tmp_path / "shared"))
    assert len(logged) == len(_mask_squares(tile)) and logged, (
        "every refusal surfaces, one line each")
    assert all("could not delete the existing mask" in line
               and "REFUSED os.remove" in line for line in logged)


def test_the_engine_cache_redirect_is_in_the_tool_index():
    """Every promotion lands WITH its index row, in the same commit."""
    text = INDEX.read_text()
    for token in ("O4_DSF_CACHE_DIR", "engine_cache_redirects",
                  "O4_MASKS_DIR", "tile_cfg_provenance"):
        assert token in text, (
            f"{token} is not in tools/INDEX.md — a redirect absent from the "
            f"index is treated as absent, and the next lane hand-forks it")


def test_the_per_test_guard_and_the_mod_cache_overlay_are_LIVE(build_mod):
    """THE ENFORCEMENT, asserted live inside a running test.

    Same style as the dump-cache live assert above, and for the same
    reason: a redirect or a guard that is installed only in the fixture's
    own imagination is exactly what the session detector kept catching.
    """
    import builtins
    import io
    conftest = _conftest()
    if conftest._per_test_guard_mode() != "refuse":     # pragma: no cover
        pytest.skip("the permanent guard is off in this run "
                    "(O4_SUITE_WRITE_AUDIT / O4_ALLOW_SHARED_REPO_WRITES)")
    assert builtins.open is not io.open, (
        "the per-test shared-repo write guard is not installed — every "
        "test is free to write the corpus every lane mounts")
    overlay = os.environ.get("O4_AIRPORT_MOD_CACHE_DIR")
    assert overlay, "the mod-cache overlay sets the env var for the session"
    resolved = Path(overlay).resolve()
    repo = Path(build_mod.DATA_REPO).resolve()
    assert repo not in resolved.parents and resolved != repo, (
        f"the per-pack sidecar cache points into the shared data repo "
        f"({resolved}) while tests run")


def test_the_shared_repo_detector_flags_a_test_written_cache(build_mod):
    """KNOWN-ANSWER TWIN for the detector's pure half, on the real path
    the leak took."""
    conftest = _conftest()
    changes = {
        "added": ["Default_DSF_cache/322b7f2a/+50+010.dsf.tmp.text",
                  "Airport_mod_cache/somepack/o4_object_footprints.cache"],
        "modified": ["Elevation_data/N30E031.hgt"],
        "removed": [],
    }
    hits = conftest.unauthorised_shared_writes(changes, build_mod.scope_of)
    assert hits == [
        ("Airport_mod_cache/somepack/o4_object_footprints.cache",
         "airport_mod_cache"),
        ("Default_DSF_cache/322b7f2a/+50+010.dsf.tmp.text", "dsf_cache"),
        ("Elevation_data/N30E031.hgt", "dem"),
    ], (
        "ALL THREE are unauthorised now: the suite has no standing write "
        "allowance, so a mod-cache sidecar and a cut inset are leaks in "
        "exactly the way the DSF dump cache always was")
    assert conftest.unauthorised_shared_writes(
        {"added": [], "modified": [], "removed": []},
        build_mod.scope_of) == []
    # a concurrent guarded build's lock churn is never the suite's write
    # (2026-09-05: it errored the session against the last collected test)
    assert conftest.unauthorised_shared_writes(
        {"added": ["Elevation_data/dem.lock"], "modified": [],
         "removed": ["Airport_mod_cache/.harness/refresh.lock"]},
        build_mod.scope_of) == []
    assert conftest.is_lock_churn("Elevation_data/dem.lock")
    assert not conftest.is_lock_churn("Elevation_data/N30E031.hgt")


def test_the_suite_has_no_standing_write_allowance(build_mod):
    """THE REGISTER IS EMPTY, and that is the assertion.

    It used to carry ``airport_mod_cache`` and ``dem`` with reasons, and
    the reasons were true — the writes were derived-cache warming, not
    corpus edits.  What they cost anyway, measured 2026-08-08: a guarded
    HECA harness build refused mid-suite with an SPJC cache path in its
    blocked list, 646 s wasted, because "the suite may warm it" and "no
    other lane is measuring right now" are different claims and only the
    first was written down.  An allowance is now a defect by construction:
    every scope is unauthorised, and the redirects make the two former
    entries unreachable rather than permitted.
    """
    conftest = _conftest()
    assert conftest._SUITE_MAY_WARM == {}, (
        "the suite writes NOTHING into the shared corpus; a new entry here "
        "re-opens the concurrency trap this lane closed")
    for scope, _prefix, _why in build_mod.REFRESH_SCOPES:
        assert scope not in conftest._SUITE_MAY_WARM
    conftest_src = (Path(__file__).parent / "conftest.py").read_text()
    assert "646 s" in conftest_src, (
        "the register records WHY it emptied — a bare empty dict invites "
        "the next lane to refill it")


def test_the_detector_uses_the_harness_snapshot_not_a_copy(build_mod):
    conftest_src = (Path(__file__).parent / "conftest.py").read_text()
    assert "shared_repo_snapshot" in conftest_src and \
        "snapshot_diff" in conftest_src and "scope_of" in conftest_src, (
        "the detector must use the harness's own snapshot and scope "
        "register — a private copy is the census-wrapper defect")
    mirror_src = inspect.getsource(build_mod.mirror_tree_as_overlay)
    assert conftest_src.count("os.walk") == 0 and \
        mirror_src.count("os.walk") == 1, (
        "conftest walks NO tree at all since the mod-cache overlay's "
        "mirror moved into shared_repo_guard.py (2026-08-11): a walk in "
        "conftest is either a private mirror fork or conftest "
        "snapshotting the shared repo itself — both are the "
        "census-wrapper defect")
    assert "e9daef5" in conftest_src, "the failure must cite its ruling"


def test_the_write_audit_rows_are_one_row_per_observed_write():
    """KNOWN-ANSWER TWIN for the per-test audit's pure core.

    The audit answers what the session detector cannot — WHICH test wrote
    — so its row builder gets the same treatment as the detector's own
    pure half: a guard carrying one blocked entry and one lock-churn entry
    yields exactly two rows, each keeping its ``kind``.  Collapsing the
    two kinds would report the ruled ``.lock`` churn as an offender and
    send a redirect round after coordination state.
    """
    conftest = _conftest()
    guard = types.SimpleNamespace(
        blocked=[{"path": "Airport_mod_cache/pack/o4_object_x.cache",
                  "scope": "airport_mod_cache",
                  "via": "open for writing"}],
        lock_churn=[{"path": LOCK_REL, "op": "os_open"}],
        library_index_churn=[])
    rows = conftest.shared_repo_write_audit_rows(
        "tests/test_x.py::test_y", guard)
    assert len(rows) == 2
    assert [r["kind"] for r in rows] == ["blocked", "lock_churn"]
    assert {r["nodeid"] for r in rows} == {"tests/test_x.py::test_y"}
    assert rows[0]["path"] == "Airport_mod_cache/pack/o4_object_x.cache"
    assert rows[0]["scope"] == "airport_mod_cache"
    assert rows[0]["via"] == "open for writing"
    assert (rows[1]["path"], rows[1]["op"]) == (LOCK_REL, "os_open")
    assert conftest.shared_repo_write_audit_rows(
        "tests/test_x.py::test_y",
        types.SimpleNamespace(blocked=[], lock_churn=[],
                              library_index_churn=[])) == []


# ══════════════════════════════════════════════════════════════════════
# THE X-PLANE INSTALL GUARD (tests/conftest.py, 2026-08-09)
# ══════════════════════════════════════════════════════════════════════
# The suite-corpus-clean lane closed the SHARED REPO; the install at
# ``conftest.xplane_root()`` had no guard at all, and a test that dropped
# its own redirects (``monkeypatch.undo()`` mid-test) restored 49 real
# KCLT pack .obj files from their .anchor_bak backups — mtime-preserved,
# so nothing on disk said so.  The twins below are the known answers for
# the guard that closes it.


def test_the_xplane_install_guard_BLOCKS_the_incidents_own_call(tmp_path):
    """``shutil.copy2`` onto a pack ``.obj`` — the reversion pass's own
    call — must refuse at the call site and leave the target untouched,
    while the ``.anchor_bak`` READ feeding it stays lawful."""
    conftest = _conftest()
    install = tmp_path / "X-Plane 12"
    pack = install / "Custom Scenery" / "pack"
    pack.mkdir(parents=True)
    live = pack / "thing.obj"
    live.write_text("re-anchored")
    backup = pack / "thing.obj.anchor_bak"
    backup.write_text("original")

    guard_cls = conftest._xplane_guard_class()
    with pytest.raises(conftest.XPlaneInstallWriteBlocked) as exc:
        with guard_cls(str(install)):
            shutil.copy2(str(backup), str(live))
    assert "thing.obj" in str(exc.value)
    assert "tmp_path" in str(exc.value), "the refusal must name the fix"
    assert live.read_text() == "re-anchored", (
        "the guard must prevent, not just report")


def test_the_xplane_install_guard_leaves_reads_and_outside_writes_free(
        tmp_path):
    conftest = _conftest()
    install = tmp_path / "X-Plane 12"
    (install / "Custom Data").mkdir(parents=True)
    inside = install / "Custom Data" / "cycle_info.txt"
    inside.write_text("readable")
    guard_cls = conftest._xplane_guard_class()
    with guard_cls(str(install)):
        assert inside.read_text() == "readable"       # reads untouched
        os.makedirs(str(install / "Custom Data"),
                    exist_ok=True)                    # ensure-dir no-op
        outside = tmp_path / "products"
        os.makedirs(str(outside))                     # real write, outside
        (outside / "patch.osm").write_text("lane product")
    assert (outside / "patch.osm").read_text() == "lane product"


def test_the_xplane_install_guard_covers_the_rename_family(tmp_path):
    """The provenance rewrite went through ``os.replace``-shaped calls,
    not only ``open`` — the whole inherited mutating family must refuse,
    and creating a directory that does NOT exist is a real mutation."""
    conftest = _conftest()
    install = tmp_path / "X-Plane 12"
    install.mkdir()
    target = install / ".o4_reanchor_provenance.json"
    target.write_text("{}")
    staged = tmp_path / "staged.json"
    staged.write_text('{"rewritten": true}')
    guard_cls = conftest._xplane_guard_class()
    with guard_cls(str(install)):
        with pytest.raises(conftest.XPlaneInstallWriteBlocked):
            os.replace(str(staged), str(target))
        with pytest.raises(conftest.XPlaneInstallWriteBlocked):
            os.remove(str(target))
        with pytest.raises(conftest.XPlaneInstallWriteBlocked):
            os.mkdir(str(install / "new_dir"))
    assert target.read_text() == "{}"
    assert staged.exists()
    assert not (install / "new_dir").exists()


def test_the_xplane_install_guard_is_LIVE(_no_test_writes_the_xplane_install):
    """THE ENFORCEMENT, asserted live inside a running test — same style
    as the shared-repo live assert above.  The probe entry is OURS, so it
    is cleared afterwards: the fixture's own teardown otherwise reads it
    as a swallowed refusal and fails this test for proving the guard
    works."""
    conftest = _conftest()
    guard = _no_test_writes_the_xplane_install
    assert guard is not None, "the install guard did not arm"
    probe = os.path.join(conftest.xplane_root(), ".o4_install_guard_probe")
    try:
        with pytest.raises(conftest.XPlaneInstallWriteBlocked):
            open(probe, "a")
    finally:
        if os.path.exists(probe):             # only if the guard is DOWN
            os.remove(probe)
    assert guard.blocked
    assert guard.blocked[-1]["path"] == ".o4_install_guard_probe"
    guard.blocked.clear()


class TestEmittedOnDem:
    """The EMITTED frame of "sits exactly on the constant DEM".

    The in-memory DEM-authorship census and the emitted patch are two
    FRAMES of one question — HECA read 16,019 in memory and shipped 938,
    the two decimators sitting between them — and the c5auth dossier had
    to carry a hand-written FRAME WARNING because only one frame had an
    instrument.  Both now come out of ``who_wrote``, so a number always
    arrives with its frame; and the STRANDED subset (an on-DEM vertex
    sharing a way with a law-valued one) is separated from a shape lying
    wholly flat on the DEM, because only the former can mint a
    within-shape law row.
    """

    #: THE KNOWN ANSWER, computed by hand from this file (DEM = 1 m,
    #: emitted tolerance 0.005 m):
    #:
    #:   nodes  -1 -3 -4 -7 ON the DEM;  -2 (90) and -6 (42) OFF it;
    #:          -5 carries NO ``alt_abs`` at all  →  total = 4 of 7
    #:   -10001 gp   sid 11  hits -1        , also holds -2 OFF  → STRANDED
    #:   -10002 gp   no sid  hits -3 -4     , nothing OFF        → vertex-flat
    #:   -10003 bldg no sid  NO valued ref  , altitude TAG = 1   → tag-only
    #:   -10004 bldg sid 12  hits -7        , also holds -6 OFF  → STRANDED,
    #:                                        altitude TAG = 1   → tag-only
    #:                       (TAG on the DEM, vertices NOT — discriminating)
    #:   -10005 apron sid 13 hits -7 -4     , nothing OFF        → vertex-flat,
    #:                       altitude TAG = 90 (OFF the DEM — the other
    #:                       discriminating direction)
    PATCH = """<?xml version='1.0' encoding='UTF-8'?>
<osm version='0.6' generator='t'>
  <node id='-1' lat='1.0' lon='1.0'><tag k='alt_abs' v='1.00' /></node>
  <node id='-2' lat='1.0' lon='1.0'><tag k='alt_abs' v='90.00' /></node>
  <node id='-3' lat='1.0' lon='1.0'><tag k='alt_abs' v='1.00' /></node>
  <node id='-4' lat='1.0' lon='1.0'><tag k='alt_abs' v='1.00' /></node>
  <node id='-5' lat='1.0' lon='1.0' />
  <node id='-6' lat='1.0' lon='1.0'><tag k='alt_abs' v='42.00' /></node>
  <node id='-7' lat='1.0' lon='1.0'><tag k='alt_abs' v='1.00' /></node>
  <way id='-10001'>
    <nd ref='-1' /><nd ref='-2' /><nd ref='-1' />
    <tag k='role' v='groundside_pavement' />
    <tag k='ref' v='groundside' />
    <tag k='shapeID' v='11' />
  </way>
  <way id='-10002'>
    <nd ref='-3' /><nd ref='-4' /><nd ref='-3' />
    <tag k='role' v='groundside_pavement' />
  </way>
  <way id='-10003'>
    <nd ref='-5' /><nd ref='-5' />
    <tag k='role' v='building' />
    <tag k='altitude' v='1.00' />
  </way>
  <way id='-10004'>
    <nd ref='-6' /><nd ref='-7' /><nd ref='-6' />
    <tag k='role' v='building' />
    <tag k='altitude' v='1.00' />
    <tag k='shapeID' v='12' />
  </way>
  <way id='-10005'>
    <nd ref='-7' /><nd ref='-4' /><nd ref='-7' />
    <tag k='role' v='apron' />
    <tag k='altitude' v='90.00' />
    <tag k='shapeID' v='13' />
  </way>
</osm>
"""

    #: shape 11 and shape 13 are in the census; shape 12 deliberately is
    #: NOT, and way -10002 carries no ``shapeID`` at all — the two ways a
    #: join can miss.
    AUTHORSHIP = [
        {"shape": 11, "role": "groundside_pavement", "on_dem": 1, "n": 2,
         "introduced_by": "seeder.py:1:THE_SEEDER"},
        {"shape": 13, "role": "apron", "on_dem": 2, "n": 2,
         "introduced_by": "solve.py:2:THE_SOLVE"},
    ]

    def _patch(self, tmp_path):
        p = tmp_path / "patch.osm"
        p.write_text(self.PATCH)
        return p

    def _rep(self, tmp_path, **kw):
        return WHO.emitted_on_dem(self._patch(tmp_path), 1.0, **kw)

    # ── the counts ───────────────────────────────────────────────────
    def test_counts_distinct_nodes_and_attributes_them_to_way_roles(
            self, tmp_path):
        rep = self._rep(tmp_path)
        assert rep["nodes"] == 7 and rep["ways"] == 5
        assert rep["total"] == 4, (
            "-1, -3, -4 and -7 sit on the DEM; -2 (90) and -6 (42) do not; "
            "-5 carries no alt_abs")
        assert rep["by_role"] == {"groundside_pavement": 3, "apron": 2,
                                  "building": 1}, (
            "a shared vertex is counted once per referencing way: -7 is in "
            "both -10004 and -10005")

    def test_stranded_is_the_on_dem_vertex_beside_an_off_dem_one(
            self, tmp_path):
        rep = self._rep(tmp_path)
        assert rep["stranded"] == 2, (
            "-1 (beside -2 in way -10001) and -7 (beside -6 in -10004); "
            "-10002 and -10005 carry no off-DEM vertex at all")
        assert rep["stranded_by_role"] == {"groundside_pavement": 1,
                                           "building": 1}
        assert rep["n_mixed_ways"] == 2
        assert rep["mixed_ways"][0]["ref"] == "groundside"

    # ── flat_ways vs flat_way_tag (the mislabel this fixture pins) ────
    def test_flat_ways_counts_vertices_not_the_way_tag(self, tmp_path):
        """``flat_ways`` promised "a whole shape flat on the DEM" and
        counted the way-level ``altitude`` TAG instead — a per-vertex
        claim the code never checked (HEAZ read 19 such ways where only
        2 are vertex-flat).  Both populations are now reported, each
        under a name that says what it counts."""
        rep = self._rep(tmp_path)
        assert rep["flat_ways"] == {"groundside_pavement": 1, "apron": 1}, (
            "-10002 (refs -3,-4) and -10005 (refs -7,-4) have every "
            "alt_abs-carrying ref on the DEM; -10005 does so while its "
            "way TAG says 90 m")
        assert rep["flat_way_tag"] == {"building": 2}, (
            "-10003 and -10004 carry altitude=1.00; -10004's vertices are "
            "NOT all on the DEM (-6 is at 42 m) and -10003 has no valued "
            "vertex at all")
        assert "building" not in rep["flat_ways"]
        assert "apron" not in rep["flat_way_tag"]

    def test_a_way_with_no_valued_vertex_is_not_vertex_flat(self, tmp_path):
        """Way -10003's only ref carries no ``alt_abs``.  "All of nothing
        is on the DEM" is vacuously true and would have made every
        unvalued way flat — the count requires at least one valued ref."""
        rep = self._rep(tmp_path)
        assert rep["flat_ways"].get("building") is None

    # ── the by-writer join: three states, all of them LOUD ────────────
    def test_the_join_reports_its_numbers_and_attributes_the_hits(
            self, tmp_path):
        rep = self._rep(tmp_path, authorship=self.AUTHORSHIP,
                        authorship_source="dem_authorship")
        j = rep["by_writer_join"]
        assert j["requested"] is True and j["source"] == "dem_authorship"
        assert j["authorship_rows"] == 2 and j["authorship_keyed"] == 2
        assert j["ways_with_shapeid"] == 3 and j["ways"] == 5
        assert j["on_dem_ways"] == 4, "-10003 has no on-DEM vertex"
        assert (j["joined_ways"], j["joined_vertices"]) == (2, 3), (
            "-10001 (shape 11, 1 hit) and -10005 (shape 13, 2 hits)")
        assert (j["unjoined_ways"], j["unjoined_vertices"]) == (2, 3), (
            "-10002 carries no shapeID (2 hits); -10004's shape 12 is not "
            "in the census (1 hit)")
        got = {(r["role"], r["introduced_by"]): r["n"]
               for r in rep["by_writer"]}
        assert got == {
            ("groundside_pavement", "seeder.py:1:THE_SEEDER"): 1,
            ("apron", "solve.py:2:THE_SOLVE"): 2,
            ("groundside_pavement", "?NOT-IN-AUTHORSHIP?"): 2,
            ("building", "?NOT-IN-AUTHORSHIP?"): 1}
        assert sum(got.values()) == sum(rep["by_role"].values()), (
            "every on-DEM vertex hit is attributed to exactly one bucket")

    def test_a_join_that_matches_nothing_says_so_with_numbers(
            self, tmp_path):
        """The named defect: rows supplied, ZERO shapeIDs matched, and the
        report printed nothing — indistinguishable from not asking."""
        rep = self._rep(tmp_path,
                        authorship=[{"shape": 999,
                                     "introduced_by": "nowhere.py:1:x"}],
                        authorship_source="dem_authorship")
        j = rep["by_writer_join"]
        assert j["requested"] is True
        assert j["authorship_rows"] == 1 and j["joined_ways"] == 0
        assert j["on_dem_ways"] == 4 and j["unjoined_vertices"] == 6
        assert rep["by_writer"], (
            "a failed join must still report the counts, in the "
            "?NOT-IN-AUTHORSHIP? bucket — never an empty section")
        assert all(r["introduced_by"] == "?NOT-IN-AUTHORSHIP?"
                   for r in rep["by_writer"])

    def test_not_requested_is_a_different_state_from_a_failed_join(
            self, tmp_path):
        rep = self._rep(tmp_path)
        assert rep["by_writer_join"]["requested"] is False
        assert rep["by_writer"] == []
        empty = self._rep(tmp_path, authorship=[])
        assert empty["by_writer_join"]["requested"] is True, (
            "an EMPTY row list is 'asked and found nothing', which must "
            "not read the same as 'never asked'")
        assert empty["by_writer_join"]["authorship_rows"] == 0

    # ── the frame stamp ──────────────────────────────────────────────
    def test_every_number_carries_its_frame(self, tmp_path):
        rep = self._rep(tmp_path)
        assert rep["frame"] == "EMITTED"
        assert rep["tol_m"] == WHO._EMIT_TOL
        assert rep["world"] == "constant DEM 1 m"

    def test_the_printed_report_carries_the_frame_and_both_flat_counts(
            self, tmp_path, capsys):
        WHO.print_emitted_on_dem(self._rep(tmp_path,
                                           authorship=self.AUTHORSHIP))
        out = capsys.readouterr().out
        assert "frame: EMITTED patch" in out
        assert "world: constant DEM 1 m" in out
        assert "NOT the in-memory layout count" in out
        assert "VERTICES all sit on the DEM" in out
        assert "ALTITUDE TAG is on the DEM" in out
        assert "joined=2" in out and "unjoined=2" in out
        assert "law-valued" not in out, (
            "the code checks alt_abs, not the law — the label may not "
            "claim a finding the law layer owns")

    def test_a_failed_join_prints_loudly(self, tmp_path, capsys):
        WHO.print_emitted_on_dem(
            self._rep(tmp_path, authorship=[{"shape": 999}]))
        out = capsys.readouterr().out
        assert "JOIN EMPTY" in out and "0 of 4 on-DEM way(s)" in out

    def test_no_authorship_prints_not_requested(self, tmp_path, capsys):
        WHO.print_emitted_on_dem(self._rep(tmp_path))
        out = capsys.readouterr().out
        assert "NOT REQUESTED" in out and "JOIN EMPTY" not in out

    # ── the SECOND instrument (RULINGS 2026-08-06 point 4) ────────────
    def test_an_independent_reader_agrees_on_every_count(self, tmp_path):
        """A second reader over the same file, written against a different
        XML API (DOM, not iterparse) and a different loop shape.  The
        load-bearing quantities are integers, so materiality is exact
        equality — one instrument's arithmetic cannot be checked by
        itself."""
        from xml.dom import minidom
        doc = minidom.parse(str(self._patch(tmp_path)))
        alt = {}
        for nd in doc.getElementsByTagName("node"):
            v = [t for t in nd.getElementsByTagName("tag")
                 if t.getAttribute("k") == "alt_abs"]
            alt[nd.getAttribute("id")] = (float(v[0].getAttribute("v"))
                                          if v else None)
        on = {i for i, a in alt.items() if a is not None and abs(a - 1.0) <= 5e-3}
        by_role, stranded, flat, flat_tag = {}, set(), {}, {}
        for w in doc.getElementsByTagName("way"):
            refs = {nd.getAttribute("ref")
                    for nd in w.getElementsByTagName("nd")}
            tags = {t.getAttribute("k"): t.getAttribute("v")
                    for t in w.getElementsByTagName("tag")}
            role = tags.get("role", "?")
            hits = refs & on
            valued = {r for r in refs if alt.get(r) is not None}
            if "altitude" in tags and abs(float(tags["altitude"]) - 1.0) <= 5e-3:
                flat_tag[role] = flat_tag.get(role, 0) + 1
            if valued and valued == hits:
                flat[role] = flat.get(role, 0) + 1
            if hits:
                by_role[role] = by_role.get(role, 0) + len(hits)
                if valued - hits:
                    stranded |= hits
        rep = self._rep(tmp_path)
        assert len(on) == rep["total"]
        assert by_role == rep["by_role"]
        assert len(stranded) == rep["stranded"]
        assert flat == rep["flat_ways"]
        assert flat_tag == rep["flat_way_tag"]

    def test_the_emitted_frame_is_reachable_without_a_build(self, tmp_path):
        """``--emitted-patch`` is a pure file read: no ICAO, no build cwd."""
        p = self._patch(tmp_path)
        assert WHO.main(["--emitted-patch", str(p), "--dem", "1"]) == 0


class TestWhoJsonAuthorshipLoader:
    """``--who-json`` must never degrade to silence.

    THE DEFECT: the loader was ``json.loads(...).get("dem_authorship")``.
    Any report whose rows were not at exactly that TOP-LEVEL key returned
    ``None``; ``emitted_on_dem`` then built ``by_writer`` only ``if
    intro_of`` and the printer emitted the section only ``if by_writer``,
    so a whole attribution vanished with no line of output — the same
    output as never asking for it.
    """

    ROWS = [{"shape": 4, "introduced_by": "a.py:1:writer"}]

    def test_the_top_level_key_is_read(self):
        rows, src, top = WHO.authorship_rows_from_report(
            {"icao": "X", "dem_authorship": self.ROWS})
        assert rows == self.ROWS and src == "dem_authorship"
        assert top == ["dem_authorship", "icao"]

    def test_a_bare_list_of_rows_is_read(self):
        rows, src, _ = WHO.authorship_rows_from_report(self.ROWS)
        assert rows == self.ROWS and src == "<list>"

    def test_rows_nested_one_level_are_found_and_the_key_named(self):
        rows, src, _ = WHO.authorship_rows_from_report(
            {"meta": {"icao": "X"}, "report": {"dem_authorship": self.ROWS}})
        assert rows == self.ROWS and src == "report.dem_authorship", (
            "the nested case returned None and every downstream count "
            "silently vanished")

    def test_no_rows_is_reported_as_such_not_as_none(self):
        rows, src, top = WHO.authorship_rows_from_report(
            {"icao": "X", "author_displacement": []})
        assert rows == [] and src is None, (
            "an empty LIST plus a None source is 'asked, found nothing' — "
            "the caller can say so; None rows could not be told from "
            "'never asked'")
        assert top == ["author_displacement", "icao"]

    def test_the_shape_key_may_be_spelled_three_ways(self):
        for key in ("shape", "shape_index", "shapeID"):
            rows, src, _ = WHO.authorship_rows_from_report(
                [{key: 7, "introduced_by": "w"}])
            assert src == "<list>", key
            assert WHO._shape_key_of(rows[0]) == "7", key

    def test_the_cli_names_the_source_and_the_row_count(self, tmp_path,
                                                        capsys):
        patch = tmp_path / "p.osm"
        patch.write_text(TestEmittedOnDem.PATCH)
        who = tmp_path / "who.json"
        who.write_text(json.dumps(
            {"wrapper": {"dem_authorship": TestEmittedOnDem.AUTHORSHIP}}))
        assert WHO.main(["--emitted-patch", str(patch), "--dem", "1",
                         "--who-json", str(who)]) == 0
        out = capsys.readouterr().out
        assert "2 authorship row(s) from 'wrapper.dem_authorship'" in out
        assert "joined=2" in out

    def test_the_cli_says_so_when_the_who_json_carries_no_rows(
            self, tmp_path, capsys):
        patch = tmp_path / "p.osm"
        patch.write_text(TestEmittedOnDem.PATCH)
        who = tmp_path / "who.json"
        who.write_text(json.dumps({"icao": "X", "author_worst": []}))
        assert WHO.main(["--emitted-patch", str(patch), "--dem", "1",
                         "--who-json", str(who)]) == 0
        out = capsys.readouterr().out
        assert "no 'dem_authorship'-shaped rows found" in out
        assert "JOIN EMPTY" in out


# ── THE AXIS FRAME (--frame own|base) ────────────────────────────────

def _sidecar_patch(tmp_path):
    """A minimal patch + sidecar carrying two TAXI and one SERVICE axis."""
    osm = tmp_path / "frame.osm"
    osm.write_text("<?xml version='1.0'?>\n<osm version='0.6'>\n</osm>\n")
    (tmp_path / "frame.osm.axes.json").write_text(json.dumps({
        "axes_exact": [
            [[[0.0, 0.0], [0.0, 0.001]], [0.015], 0, False],
            [[[0.0, 0.0], [0.001, 0.0]], [0.015], 1, False],
            [[[0.0, 0.0], [0.001, 0.001]], [0.08], 2, True],   # service
        ],
        "ruleset": "icao",
    }))
    return osm


def test_the_own_frame_is_the_default_and_touches_nothing(census_mod, cg,
                                                          tmp_path):
    """Default runs must pass NO axis override at all — the base frame is
    opt-in, and a frame that silently altered the default would be the
    census-wrapper defect with a flag on it."""
    osm = _sidecar_patch(tmp_path)
    overrides, stamp = census_mod._axis_frame_override(osm, cg, "own")
    assert overrides == {}
    assert stamp["frame"] == "own"


def test_the_base_frame_drops_exactly_the_service_axes(census_mod, cg,
                                                       tmp_path):
    """The base frame removes the SERVICE axes and nothing else, and says
    so in numbers (3 -> 2) rather than leaving it to the reader."""
    osm = _sidecar_patch(tmp_path)
    overrides, stamp = census_mod._axis_frame_override(osm, cg, "base")
    assert stamp == {"frame": "base", "axes_total": 3, "axes_kept": 2}
    kept = overrides["taxi_axes_ll"]
    assert len(kept) == 2
    assert not any(bool(e[4]) for e in kept), "a service axis survived"
    full = cg.law_context_from_sidecar(osm, announce=False)["taxi_axes_ll"]
    assert kept == [e for e in full if not e[4]], (
        "the base frame is not a SUBSET of the patch's own frame — it must "
        "remove axes, never rewrite them")


def test_the_frame_is_always_stamped_in_the_report(census_mod):
    """RULINGS 2026-08-06 binding point 3: every reported number carries
    its frame.  A base-frame census that read like an own-frame one is the
    two-instruments trap by construction."""
    src = Path(inspect.getfile(census_mod)).read_text()
    assert '"axis_frame": frame_stamp' in src


# ── THE ROW ITEMISATION (--rows-json) ────────────────────────────────
#
# The dump's whole claim is that it is the census's OWN population,
# itemised — not a second measurement of the same patch.  Every twin here
# is that claim in one form or another, because a row dump that drifted
# from the counts beside it would be the census-wrapper defect reborn at
# row level: two instruments, one assumed population.

def _censused_with_rows(census_mod, cg, tmp_path):
    """The shipped fixture patch, censused once with the row dump on."""
    osm = tmp_path / "rows.osm"
    osm.write_bytes(FIXTURE_PATCH.read_bytes())
    (tmp_path / "rows.osm.axes.json").write_text(json.dumps({"anchor": None}))
    out = tmp_path / "rows.json"
    rep = census_mod.census_one(osm, cg, top=5, rows_out=out)
    return rep, json.loads(out.read_text())


def test_the_row_dump_is_the_reports_own_population(census_mod, cg,
                                                    tmp_path):
    """KNOWN ANSWER: the dump's length is the report's own law-true total,
    and its class tally IS the report's class table — recomputed from the
    rows, never copied."""
    rep, dump = _censused_with_rows(census_mod, cg, tmp_path)
    assert dump["n_rows"] == len(dump["rows"]) == rep["lawtrue"]["total"]
    assert rep["lawtrue"]["total"] > 0, (
        "the fixture stopped producing rows — this twin would pass vacuously")
    from collections import Counter as _C
    tally = _C(f"{r['family']}::{r['roles']}" for r in dump["rows"])
    assert dict(tally.most_common()) == rep["classes"]


def test_the_row_dump_carries_the_laws_own_side_split(census_mod, cg,
                                                      tmp_path):
    """Same for the side partition — the number "airside is king" is
    applied to must be re-derivable from the rows alone."""
    rep, dump = _censused_with_rows(census_mod, cg, tmp_path)
    from collections import Counter as _C
    sides = _C(r["side"] for r in dump["rows"])
    for side in ("airside", "groundside", "mixed", "unknown"):
        assert sides.get(side, 0) == rep["lawtrue"][side]
    assert (sides.get("airside", 0) + sides.get("mixed", 0)
            == rep["lawtrue"]["airside_for_acceptance"])


def test_the_row_dump_agrees_with_the_worst_table_row_for_row(census_mod,
                                                              cg, tmp_path):
    """The dump is emitted from the SAME magnitude-sorted list the worst-N
    table is sliced from, so the table must be its prefix — one ordering,
    one severity accessor."""
    rep, dump = _censused_with_rows(census_mod, cg, tmp_path)
    n = len(rep["worst"])
    assert n > 0
    for a, b in zip(rep["worst"], dump["rows"][:n]):
        assert (a["family"], a["roles"], a["side"], a["magnitude_m"]) == \
               (b["family"], b["roles"], b["side"], b["magnitude_m"])


def test_the_row_dump_is_stamped_with_its_frame(census_mod, cg, tmp_path):
    """RULINGS 2026-08-06 binding point 3.  Two dumps taken in different
    axis frames must not be joinable without it showing."""
    _rep, dump = _censused_with_rows(census_mod, cg, tmp_path)
    assert dump["axis_frame"]["frame"] == "own"
    assert dump["law_true_knobs"] and "provenance" in dump


def test_no_row_dump_is_written_unless_asked(census_mod, cg, tmp_path):
    """Inertness: the default census must not grow a file."""
    osm = tmp_path / "plain.osm"
    osm.write_bytes(FIXTURE_PATCH.read_bytes())
    (tmp_path / "plain.osm.axes.json").write_text(json.dumps({"anchor": None}))
    census_mod.census_one(osm, cg, top=1)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "plain.osm", "plain.osm.axes.json"]


def test_several_patches_get_one_dump_each(census_mod, cg, tmp_path):
    """A single --rows-json over N patches used to be a footgun in every
    lane script that grew one: the last patch silently wins."""
    a, b = tmp_path / "a.osm", tmp_path / "b.osm"
    for p in (a, b):
        p.write_bytes(FIXTURE_PATCH.read_bytes())
        p.with_suffix(".osm.axes.json").write_text(
            json.dumps({"anchor": None}))
    out = tmp_path / "dump.json"
    assert census_mod.main([str(a), str(b), "--quiet",
                            "--rows-json", str(out)]) == 0
    assert (tmp_path / "dump.a.json").exists()
    assert (tmp_path / "dump.b.json").exists()


def test_row_record_spells_a_row_the_way_the_class_table_keys_it(cg,
                                                                 census_mod):
    """KNOWN ANSWER on a hand-built row, because the shipped fixture's
    rows happen to be same-role pairs — on that patch a role pair spelled
    in the wrong ORDER would still tally correctly, and the dump would
    only diverge from the class table on real airports.  The class table's
    key is ``family::sorted(roles)``; the dump must use the same spelling
    or the two cannot be joined."""
    class _W:
        def __init__(self, role, wid):
            self.tags, self.wid = {"role": role}, wid

    class _Row:
        de_m = -0.42
        distance_m = 10.0
        grade_pct = 4.2
        cap_pct = 1.0
        pt_a, pt_b = (1.234, 5.678), (9.0, 10.0)
        lat, lon = 30.1, 31.4
        out_of_scope = None

        def __init__(self):
            self.way_a, self.way_b = _W("service_junction", 7), _W("apron", 3)

    rec = census_mod.row_record(cg, "within_shape", _Row())
    assert rec["roles"] == "apron|service_junction", (
        "the dump spells the role pair differently from the class table")
    assert rec["side"] == "mixed" and rec["magnitude_m"] == 0.42
    assert rec["site_m"] == [[1.23, 5.68], [9.0, 10.0]]
    assert rec["way_a"] == 7 and rec["way_b"] == 3


# ══════════════════════════════════════════════════════════════════════
# §9 THE SITE CENSUS (--sites) — rows amplify, sites do not
# ══════════════════════════════════════════════════════════════════════
#
# WHY THESE TWINS EXIST.  A site count is about to be a HEADLINE number:
# the owner's "why does the battery still read thousands of defects" is
# answered partly by amplification — one over-cap region on one apron
# mints hundreds of edge-granularity rows (HECA's way -12407 alone carries
# ~800).  An instrument that produces a headline needs a KNOWN-ANSWER TWIN
# (RULINGS 2026-08-06, "Instrument truth is law", binding point 1), and a
# clustering that quietly dropped or double-counted rows would put a
# smaller, friendlier number in front of the owner with nothing catching
# it — the census-wrapper defect one level up.


class _SiteRow:
    """A census row with known family, ways, endpoints and magnitude."""

    class _W:
        def __init__(self, wid, role):
            self.wid, self.tags = wid, {"role": role}

    def __init__(self, de, wa, wb, pa, pb, role="apron", excess=None,
                 lat=30.0, lon=31.0):
        self.de_m = de
        self.way_a = self._W(wa, role)
        self.way_b = self._W(wb, role)
        self.pt_a, self.pt_b = pa, pb
        self.excess_pct = excess
        self.out_of_scope = None
        self.lat, self.lon = lat, lon


def _two_known_sites():
    """TWO sites by construction, one joined each way the rule allows.

    SITE A — THE AMPLIFIER: three rows on ONE way (``-1``), deliberately
    1 km apart so nothing but the SHARED WAY ID can join them.  Worst
    0.9 m, so it is sim-visible.

    SITE B — THE WELD: two rows on DIFFERENT ways (``-2``/``-3``) that
    meet at a shared canonical node — their nearest endpoints are 0.2 m
    apart, inside the census's own 0.5 m weld tolerance.  Worst 0.02 m,
    so it is NOT sim-visible: the two sites differ in every reported
    dimension, which is what makes a mix-up detectable.
    """
    return [
        ("within_shape", _SiteRow(0.2, "-1", "-1", (0.0, 0.0), (10.0, 0.0))),
        ("within_shape", _SiteRow(0.4, "-1", "-1", (500.0, 0.0),
                                  (510.0, 0.0))),
        ("within_shape", _SiteRow(0.9, "-1", "-1", (1000.0, 0.0),
                                  (1010.0, 0.0), excess=3.5)),
        ("within_shape", _SiteRow(0.02, "-2", "-2", (2000.0, 0.0),
                                  (2010.0, 0.0))),
        ("within_shape", _SiteRow(0.01, "-3", "-3", (2010.2, 0.0),
                                  (2020.0, 0.0))),
    ]


def test_two_known_sites_cluster_by_way_and_by_weld(census_mod, cg):
    """KNOWN-ANSWER TWIN: count, membership, amplification, visibility."""
    rows = _two_known_sites()
    sec = census_mod.cluster_sites(rows, cg)
    assert sec["sites"] == 2, (
        f"expected exactly 2 sites, got {sec['sites']} — "
        f"{[(s['family'], s['rows']) for s in sec['all_sites']]}")
    by_worst = sec["all_sites"]           # sorted worst-first
    a, b = by_worst[0], by_worst[1]

    # MEMBERSHIP — which rows landed where, not just how many.
    assert a["row_indices"] == [0, 1, 2] and a["ways"] == ["-1"]
    assert b["row_indices"] == [3, 4] and b["ways"] == ["-2", "-3"]

    # AMPLIFICATION — the number the whole section exists for.
    assert (a["rows"], b["rows"]) == (3, 2)
    assert sec["amplification"] == 2.5          # 5 rows / 2 sites
    assert sec["rows_per_site"]["median"] == 2.5
    assert sec["rows_per_site"]["max"] == 3

    # VISIBILITY — one of each, at the stated default constant.
    assert sec["visibility_m"] == census_mod.DEFAULT_SITE_VISIBILITY_M == 0.05
    assert a["worst_m"] == 0.9 and a["sim_visible"] is True
    assert b["worst_m"] == 0.02 and b["sim_visible"] is False
    assert sec["sites_visible"] == 1
    assert a["worst_grade_excess_pct"] == 3.5
    assert b["worst_grade_excess_pct"] is None, (
        "a step-shaped site has no grade excess and must report None, "
        "never 0 — a zero would read as 'exactly at cap'")


def test_a_site_never_spans_two_law_families(census_mod, cg):
    """The rule keys on the FAMILY first.  Two different laws firing on
    the same shape are two findings with two owners: a runway-strip tear
    and an apron over-cap on one apron edge do not get fixed by one
    change, and merging them would hide one of them inside the other's
    row count."""
    rows = _two_known_sites()
    # Same way, same coordinates as site A's first row — different law.
    rows.append(("cross_shape", _SiteRow(0.7, "-1", "-1", (0.0, 0.0),
                                         (10.0, 0.0))))
    sec = census_mod.cluster_sites(rows, cg)
    assert sec["sites"] == 3
    fams = sorted(s["family"] for s in sec["all_sites"])
    assert fams == ["cross_shape", "within_shape", "within_shape"]
    a = next(s for s in sec["all_sites"] if s["family"] == "cross_shape")
    assert a["rows"] == 1, "the decoy joined a site of another family"


def test_the_adjacency_tolerance_is_the_censuss_own_constant(census_mod, cg):
    """"never a new proximity semantic": the tolerance IS the census's
    stamped law-true knob (the solver's weld tolerance), read from the
    module rather than re-typed — and a pair just outside it does not
    join, which is what proves the number is actually being applied."""
    tol = cg.LAW_TRUE_KNOBS["proximity_m"]
    assert tol == cg.SHARED_VERTEX_TOL_M
    sec = census_mod.cluster_sites(_two_known_sites(), cg)
    assert sec["adjacency_tol_m"] == tol
    assert "SHARED_VERTEX_TOL_M" in sec["adjacency_tol_source"]

    def _pair(gap):
        return [("within_shape", _SiteRow(0.5, "-2", "-2", (0.0, 0.0),
                                          (10.0, 0.0))),
                ("within_shape", _SiteRow(0.5, "-3", "-3", (10.0 + gap, 0.0),
                                          (20.0, 0.0)))]
    assert census_mod.cluster_sites(_pair(tol * 0.5), cg)["sites"] == 1
    assert census_mod.cluster_sites(_pair(tol * 2.0), cg)["sites"] == 2, (
        "two rows further apart than the weld tolerance were welded — the "
        "tolerance is not being applied, or a wider one crept in")


def test_the_clustering_does_not_depend_on_row_order(census_mod, cg):
    """A headline number that changes when the rows arrive in a different
    order is not a measurement.  The canonical-node registry is built in
    sorted coordinate order for exactly this reason."""
    rows = _two_known_sites()
    a = census_mod.cluster_sites(rows, cg)
    b = census_mod.cluster_sites(list(reversed(rows)), cg)
    assert a["sites"] == b["sites"]
    assert sorted(s["rows"] for s in a["all_sites"]) == \
        sorted(s["rows"] for s in b["all_sites"])
    assert sorted(s["worst_m"] for s in a["all_sites"]) == \
        sorted(s["worst_m"] for s in b["all_sites"])


def test_the_visibility_threshold_is_a_knob(census_mod, cg):
    """The 5 cm constant is an ASSUMPTION, not a law — so it moves, and
    the report says which value produced the flags."""
    rows = _two_known_sites()
    loose = census_mod.cluster_sites(rows, cg, visibility_m=0.001)
    tight = census_mod.cluster_sites(rows, cg, visibility_m=1.0)
    assert loose["sites_visible"] == 2 and tight["sites_visible"] == 0
    assert loose["visibility_m"] == 0.001
    assert "0.001 m of relief" in loose["visibility_note"]


def test_the_sites_never_re_run_a_check(census_mod):
    """The sites are a second READER of the rows the census already has.
    A section that re-ran the law would be a second instrument, and two
    instruments on one assumed population is this repo's dominant analysis
    failure."""
    src = inspect.getsource(census_mod.cluster_sites)
    for forbidden in ("run_checks", "load_check_grade", "_parse_osm"):
        assert forbidden not in src, (
            f"cluster_sites calls {forbidden} — it must only read the rows "
            f"census_one already produced")


def _sites_of_the_fixture(census_mod, cg, tmp_path, **kw):
    osm = tmp_path / "sites.osm"
    osm.write_bytes(FIXTURE_PATCH.read_bytes())
    (tmp_path / "sites.osm.axes.json").write_text(json.dumps({"anchor": None}))
    rep = census_mod.census_one(osm, cg, top=5, want_sites=True, **kw)
    return rep, rep["sites"]


def test_the_site_rows_union_IS_the_censuss_own_population(census_mod, cg,
                                                           tmp_path):
    """THE LOCKSTEP TWIN.  The sites must PARTITION ``all_rows``: every
    row in exactly one site, no row invented.  This is the same claim
    ``--rows-json`` makes and for the same reason — a site table that
    dropped rows would report a smaller, friendlier headline than the
    total printed directly above it."""
    out = tmp_path / "sites.json"
    rep, sec = _sites_of_the_fixture(census_mod, cg, tmp_path, sites_out=out)
    dump = json.loads(out.read_text())
    total = rep["lawtrue"]["total"]
    assert total > 0, "the fixture stopped producing rows — twin vacuous"
    assert sec["total_rows"] == total
    seen = []
    for s in dump["sites"]:
        assert s["rows"] == len(s["row_indices"])
        seen.extend(s["row_indices"])
    assert sorted(seen) == list(range(total)), (
        "the site membership is not a partition of the census's rows")
    assert sum(s["rows"] for s in dump["sites"]) == total == dump["n_rows"]
    assert dump["n_sites"] == sec["sites"] == len(dump["sites"])


def test_the_per_site_splits_agree_with_the_reports_own(census_mod, cg,
                                                        tmp_path):
    """Two readers, one population (RULINGS 2026-08-06, point 4 as scoped
    2026-08-06): the sides and the adjudication split summed over the
    sites must equal the numbers the report prints, because both come from
    the law's own accessors over the same rows."""
    rep, sec = _sites_of_the_fixture(census_mod, cg, tmp_path)
    sites = sec["all_sites"] if "all_sites" in sec else None
    assert sites is None, (
        "the report dict must not carry every site — it is the --sites-json "
        "payload and would bloat every census JSON")
    # Re-derive from the dump-free report: the by-family table and the
    # aggregate counts are what a reader sees.
    assert sum(d["rows"] for d in sec["by_family"].values()) == \
        rep["lawtrue"]["total"]
    assert sum(d["sites"] for d in sec["by_family"].values()) == sec["sites"]
    assert sec["sites_adjudicated"] <= sec["sites"]
    assert sec["sites_visible_adjudicated"] <= sec["sites_visible"]
    for key in sec["by_family"]:
        assert key in dict((k, t) for k, t, _b in cg.LAW_FAMILIES), (
            f"site family {key!r} is not a registered law family")


def test_the_adjudication_split_per_site_is_the_laws_own(census_mod, cg):
    """A site's adjudicated / deferred / out-of-scope counts come from
    ``check_grade.adjudication`` applied to that site's own rows — never a
    second copy of the deferred register (RULINGS d48bc0a)."""
    deferred_key = sorted(cg.VERSION_DEFERRED_FAMILIES)[0]
    rows = [(deferred_key, _SiteRow(0.5, "-9", "-9", (0.0, 0.0), (5.0, 0.0))),
            ("within_shape", _SiteRow(0.5, "-8", "-8", (99.0, 0.0),
                                      (105.0, 0.0)))]
    sec = census_mod.cluster_sites(rows, cg)
    assert sec["sites"] == 2
    defer = next(s for s in sec["all_sites"] if s["family"] == deferred_key)
    real = next(s for s in sec["all_sites"] if s["family"] == "within_shape")
    assert (defer["deferred"], defer["adjudicated"]) == (1, 0)
    assert (real["deferred"], real["adjudicated"]) == (0, 1)
    assert sec["sites_adjudicated"] == 1, (
        "a site made entirely of version-deferred rows counted as an "
        "adjudicated defect — instruments report, the law adjudicates")
    assert sum(s["adjudicated"] for s in sec["all_sites"]) == \
        cg.adjudication(rows)["adjudicated_total"]


def test_the_site_flag_runs_through_the_census_cli(census_mod, cg, tmp_path):
    """END TO END through the one code path: the flags, the law-true
    frame, the JSON report, the dump.  A flag that only works when called
    as a function is a flag no lane will use."""
    osm = tmp_path / "cli.osm"
    osm.write_bytes(FIXTURE_PATCH.read_bytes())
    (tmp_path / "cli.osm.axes.json").write_text(json.dumps({"anchor": None}))
    out, dump = tmp_path / "c.json", tmp_path / "s.json"
    assert census_mod.main([str(osm), "--sites", "--sites-json", str(dump),
                            "--json", str(out), "--quiet"]) == 0
    rep = json.loads(out.read_text())
    sec = rep["sites"]
    assert sec["sites"] > 0 and sec["total_rows"] == rep["lawtrue"]["total"]
    assert sec["visibility_m"] == 0.05
    assert json.loads(dump.read_text())["n_sites"] == sec["sites"]
    # ...the visibility knob arrives from the command line...
    assert census_mod.main([str(osm), "--sites", "--site-visibility", "5",
                            "--json", str(out), "--quiet"]) == 0
    assert json.loads(out.read_text())["sites"]["visibility_m"] == 5.0
    # ...--sites-json alone implies the section (a dump with no counts
    # beside it is the two-instruments trap by omission)...
    assert census_mod.main([str(osm), "--sites-json", str(dump),
                            "--json", str(out), "--quiet"]) == 0
    assert "sites" in json.loads(out.read_text())
    # ...and without either flag the section is absent, not empty.
    assert census_mod.main([str(osm), "--json", str(out), "--quiet"]) == 0
    assert "sites" not in json.loads(out.read_text())


def test_no_site_dump_is_written_unless_asked(census_mod, cg, tmp_path):
    """Inertness: a default census must not grow a file."""
    osm = tmp_path / "plain.osm"
    osm.write_bytes(FIXTURE_PATCH.read_bytes())
    (tmp_path / "plain.osm.axes.json").write_text(
        json.dumps({"anchor": None}))
    census_mod.census_one(osm, cg, top=1, want_sites=True)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "plain.osm", "plain.osm.axes.json"]


def test_several_patches_get_one_site_dump_each(census_mod, cg, tmp_path):
    """A single --sites-json over N patches would silently keep the last
    — the footgun every lane script that grew a dump has hit."""
    a, b = tmp_path / "a.osm", tmp_path / "b.osm"
    for p in (a, b):
        p.write_bytes(FIXTURE_PATCH.read_bytes())
        p.with_suffix(".osm.axes.json").write_text(
            json.dumps({"anchor": None}))
    out = tmp_path / "sd.json"
    assert census_mod.main([str(a), str(b), "--quiet",
                            "--sites-json", str(out)]) == 0
    assert (tmp_path / "sd.a.json").exists()
    assert (tmp_path / "sd.b.json").exists()


def test_the_site_flag_is_in_the_tool_index():
    """Every promotion lands WITH its index row, in the same commit."""
    text = INDEX.read_text()
    for token in ("--sites", "--site-visibility", "--sites-json"):
        assert token in text, (
            f"{token} is not in tools/INDEX.md — a flag absent from the "
            f"index is treated as absent, and gets written by hand again")


# ══════════════════════════════════════════════════════════════════════
# §10 THE MATERIALITY FLOOR — a floor may only relax what it can measure
# ══════════════════════════════════════════════════════════════════════
#
# WHY THESE TWINS EXIST.  The floor is the first mechanism in this campaign
# whose JOB is to make a headline number smaller (owner RULINGS 2026-08-07:
# "we don't need to be grading to less than 0.5m").  Every other instrument
# here is guarded against under-reporting by accident; this one
# under-reports ON PURPOSE, under stated conditions, and the only thing
# standing between "the owner's ruling" and "the census quietly stopped
# counting things" is that those conditions are exactly the ruled ones and
# that nothing it takes out disappears.  So: known answers at both sides of
# every constant, the guard halves proven to fire INDEPENDENTLY (a guard
# that only ever fires together with the floor is a guard nobody has
# tested), the runway exemption, the counted-never-dropped label locked to
# its register, and the host-siding proven inert on the LAW.


class _FloorRow:
    """A census row with the fields the floor reads, and nothing else.

    Deliberately NOT a ``check_grade.Violation``: these twins must fail if
    the floor starts reading a field the real rows do not carry, and the
    dataclass would supply defaults for exactly that mistake."""

    class _W:
        def __init__(self, wid, role):
            self.wid, self.tags = wid, {"role": role}

    def __init__(self, *, de=None, grade=None, excess=None, dist=None,
                 step=None, wa="-1", wb=None, pa=(0.0, 0.0), pb=(10.0, 0.0),
                 role="apron", out_of_scope=None):
        if step is not None:
            self.step_m = step
            self.way_v = self._W(wa, role)
            self.way_e = self._W(wb if wb is not None else wa, role)
            self.vert_pt, self.proj_pt = pa, pb
        else:
            self.de_m = de
            self.grade_pct = grade
            self.excess_pct = excess
            self.distance_m = dist
            self.way_a = self._W(wa, role)
            self.way_b = self._W(wb if wb is not None else wa, role)
            self.pt_a, self.pt_b = pa, pb
        self.out_of_scope = out_of_scope
        self.lat, self.lon = 30.0, 31.0


def _graded(n, *, grade, excess, dist, role="apron", wid="-1", x0=0.0):
    """``n`` graded rows on ONE way — one site by the shared-way rule.

    ``de`` is the row's whole elevation difference (grade x span) so the
    ``min(de, ...)`` clamp in ``row_excess_m`` is not what is being tested;
    each row's EXCESS is ``excess/100 x dist`` metres."""
    return [("within_shape",
             _FloorRow(de=grade / 100.0 * dist, grade=grade, excess=excess,
                       dist=dist, role=role, wa=wid,
                       pa=(x0 + 1000.0 * i, 0.0),
                       pb=(x0 + 1000.0 * i + dist, 0.0)))
            for i in range(n)]


def _one_site(census_mod, cg, rows):
    sec = census_mod.cluster_sites(rows, cg)
    assert sec["sites"] == 1, (
        f"fixture built {sec['sites']} sites, not 1 — the floor twin would "
        f"be testing the clustering instead")
    return sec, sec["all_sites"][0]


# ── the knobs are the ruled ones, and they are named ────────────────

def test_the_floor_constants_are_the_ruled_values_and_cite_the_ruling(
        cg, census_mod):
    """Owner RULINGS 2026-08-07, four parts.  A constant that drifts from
    the ruling silently re-adjudicates the whole battery, and a constant
    with no citation is one nobody can check against the ruling."""
    assert cg.MATERIALITY_FLOOR_M == 0.5
    assert cg.MATERIALITY_SHARP_STEP_M == 0.15
    assert cg.MATERIALITY_SHARP_GRADE_CAP_MULTIPLE == 2.0
    assert cg.MATERIALITY_RUNWAY_FAMILY_ROLES == frozenset(
        {"runway", "runway_crossing"}), (
        "the runway family is the repo's own definition — flex_audit."
        "RUNWAY_ROLES and the '# runway family' head of layout."
        "AUTHORITY_PRECEDENCE — not a set invented for this floor")
    assert "2026-08-07" in cg.MATERIALITY_FLOOR_RULING
    assert "0.5" in cg.MATERIALITY_FLOOR_RULING
    # Every knob is READ by the site census — a constant nothing consumes
    # is a constant that documents a law nobody applies.
    reader = inspect.getsource(census_mod)
    for token in ("MATERIALITY_FLOOR_M", "MATERIALITY_SHARP_STEP_M",
                  "MATERIALITY_SHARP_GRADE_CAP_MULTIPLE",
                  "MATERIALITY_RUNWAY_FAMILY_ROLES",
                  "MATERIALITY_SUB_FLOOR_LABEL",
                  "MATERIALITY_UNMEASURED_FAMILIES",
                  "MATERIALITY_ACCUMULATION_RULE"):
        assert token in reader, (
            f"{token} is defined but never read — a knob nothing consumes")


def test_no_floor_constant_is_written_twice(census_mod):
    """The census must READ the knobs, never re-type them: a second copy of
    0.5 is how a report and a law stop agreeing (the census-wrapper defect
    in miniature)."""
    src = inspect.getsource(census_mod.cluster_sites)
    for literal in ("0.5", "0.15", "2.0"):
        assert f"= {literal}" not in src, (
            f"cluster_sites contains a bare {literal} — read the knob from "
            f"check_grade instead")
    assert "cg.MATERIALITY_FLOOR_M" in src
    assert "cg.MATERIALITY_SUB_FLOOR_LABEL" in src


# ── row_excess_m: the accumulation's own arithmetic ─────────────────

def test_row_excess_m_is_the_excess_not_the_magnitude(cg):
    """THE distinction the whole floor rests on.  A 3.2 m rise over 200 m
    of 1.5 %-capped taxiway is a 3.2 m MAGNITUDE and a 0.2 m EXCESS; the
    owner's sentence is about the second number."""
    r = _FloorRow(de=3.2, grade=1.6, excess=0.1, dist=200.0)
    assert cg.row_magnitude(r) == 3.2
    assert cg.row_excess_m(r) == pytest.approx(0.2)
    assert cg.row_cap_pct(r) == pytest.approx(1.5)


def test_row_excess_m_never_exceeds_the_whole_elevation_difference(cg):
    """The near-miss frontage law reports ``excess_pct=100`` as a SENTINEL
    (there is no lawful grade across a sliver), so the product overshoots.
    A row can never be more unlawful than its whole |de|."""
    r = _FloorRow(de=0.4, grade=13.3, excess=100.0, dist=3.0)
    assert cg.row_excess_m(r) == pytest.approx(0.4)


def test_row_excess_m_handles_the_cap_zero_and_step_shapes(cg):
    """Two shapes carry their whole quantity in ``de_m``: a cap-0 law that
    reports ``grade_pct == 0`` (the drainage-spine dam) and a row priced
    over zero run (the terrace ACTUAL step).  Both are their own excess."""
    dam = _FloorRow(de=0.79, grade=0.0, excess=0.0, dist=38.0)
    assert cg.row_excess_m(dam) == pytest.approx(0.79)
    joint = _FloorRow(de=0.6, grade=0.0, excess=0.0, dist=0.0)
    assert cg.row_excess_m(joint) == pytest.approx(0.6)
    assert cg.row_excess_m(_FloorRow(step=0.22)) == pytest.approx(0.22)


def test_an_unmeasured_family_funds_nothing_and_is_never_floored(census_mod,
                                                                 cg):
    """``lateral_contiguity`` prices a CAP: its ``de_m`` is ``eff - cap``, a
    bare decimal, over no span at all.  Summing 0.03 into a METRE
    accumulation would put a units mix-up inside the headline — 3
    percentage points reading as 3 centimetres — so the family funds
    nothing AND the site stays actionable: a floor may only relax what it
    can measure."""
    assert "lateral_contiguity" in cg.MATERIALITY_UNMEASURED_FAMILIES
    row = _FloorRow(de=0.03, grade=8.0, excess=3.0, dist=0.0, role="service_road")
    assert cg.row_excess_m(row, "lateral_contiguity") == 0.0
    assert cg.row_excess_m(row) == pytest.approx(0.03), (
        "without the family key the accessor must not guess — the caller "
        "that has the key is the one that may exclude it")
    sec, site = _one_site(census_mod, cg, [("lateral_contiguity", row)])
    assert site["accumulation_m"] == 0.0
    assert site["actionable"] is True
    assert site["actionable_reasons"] == ["unmeasured"]
    assert site["unmeasured_families"] == ["lateral_contiguity"]
    assert sec["sites_sub_floor"] == 0


# ── (1) THE FLOOR ───────────────────────────────────────────────────

def test_a_site_under_the_floor_is_sub_floor_and_over_it_is_actionable(
        census_mod, cg):
    """KNOWN ANSWER at both sides of 0.5 m.  Each row here carries 0.1 m of
    excess at 1.5 x its cap, so nothing but the ACCUMULATION can decide —
    the sharp guard is deliberately quiet on both arms."""
    under = _graded(3, grade=1.5, excess=0.5, dist=20.0)
    sec, site = _one_site(census_mod, cg, under)
    assert site["accumulation_m"] == pytest.approx(0.3)
    assert site["actionable"] is False
    assert site["disposition"] == cg.MATERIALITY_SUB_FLOOR_LABEL
    assert site["sharp_step_rows"] == 0 and site["sharp_grade_rows"] == 0
    assert (sec["sites_actionable"], sec["sites_sub_floor"]) == (0, 1)

    over = _graded(5, grade=1.5, excess=0.5, dist=20.0)
    sec2, site2 = _one_site(census_mod, cg, over)
    assert site2["accumulation_m"] == pytest.approx(0.5)
    assert site2["actionable"] is True
    assert site2["actionable_reasons"] == ["accumulation"], (
        "the floor arm must be decided by ACCUMULATION alone — a guard "
        "firing here would make the floor twin vacuous")
    assert (sec2["sites_actionable"], sec2["sites_sub_floor"]) == (1, 0)


def test_the_accumulation_is_funded_by_adjudicated_rows_only(census_mod, cg):
    """A version-deferred or out-of-scope row is NOT a defect (RULINGS
    d48bc0a, and the 2026-08-06 ONE-graph classes).  It may not push a site
    over the floor — that would let a deferred family mint actionability
    for a family that has none."""
    deferred_key = sorted(cg.VERSION_DEFERRED_FAMILIES)[0]
    rows = _graded(3, grade=1.5, excess=0.5, dist=20.0)
    padding = [(deferred_key,
                _FloorRow(de=9.0, grade=1.5, excess=0.5, dist=1000.0,
                          wa="-1", pa=(0.0, 0.0), pb=(1000.0, 0.0)))]
    sec = census_mod.cluster_sites(rows + padding, cg)
    real = next(s for s in sec["all_sites"] if s["family"] == "within_shape")
    assert real["accumulation_m"] == pytest.approx(0.3)
    assert real["actionable"] is False
    defer = next(s for s in sec["all_sites"] if s["family"] == deferred_key)
    assert defer["accumulation_m"] == 0.0 and defer["actionable"] is False
    assert defer["disposition"] == "not_adjudicated", (
        "a site made only of deferred rows is neither actionable nor "
        "SUB-FLOOR: the floor never adjudicated it at all")
    assert sec["sites_sub_floor"] == 1


def test_an_out_of_scope_row_cannot_fund_or_sharpen_a_site(census_mod, cg):
    """Same rule for the out-of-scope classes, and for the GUARD as well as
    the sum: a row the law never governed cannot be the sharp bump that
    keeps a site actionable."""
    rows = _graded(2, grade=1.5, excess=0.5, dist=20.0)
    rows.append(("within_shape",
                 _FloorRow(de=4.0, grade=9.0, excess=7.5, dist=44.0, wa="-1",
                           pa=(50.0, 0.0), pb=(94.0, 0.0),
                           out_of_scope="disconnected_ring")))
    sec, site = _one_site(census_mod, cg, rows)
    assert site["rows"] == 3 and site["adjudicated"] == 2
    assert site["out_of_scope"] == 1
    assert site["accumulation_m"] == pytest.approx(0.2)
    assert site["sharp_grade_rows"] == 0
    assert site["actionable"] is False


# ── (2) THE SHARP GUARD, each half proven to fire alone ─────────────

def test_the_step_guard_fires_alone_at_its_own_constant(census_mod, cg):
    """"We don't want any sharp bumps."  A site of small steps accumulates
    nothing, so only the STEP half can keep it actionable — and the twin
    brackets the constant: 0.15 m trips, 0.14 m does not."""
    def _steps(h):
        return [("vertex_to_edge_step", _FloorRow(step=h, wa="-7")),
                ("vertex_to_edge_step", _FloorRow(step=0.10, wa="-7",
                                                  pa=(5.0, 0.0),
                                                  pb=(6.0, 0.0)))]
    sec, site = _one_site(census_mod, cg, _steps(cg.MATERIALITY_SHARP_STEP_M))
    assert site["accumulation_m"] == pytest.approx(0.25)
    assert site["accumulation_m"] < cg.MATERIALITY_FLOOR_M
    assert site["actionable"] is True
    assert site["actionable_reasons"] == ["sharp_step"]
    assert site["sharp_step_rows"] == 1
    assert site["worst_step_m"] == pytest.approx(cg.MATERIALITY_SHARP_STEP_M)
    assert site["sharp_grade_rows"] == 0, (
        "a step row carries no grade and no cap — it must not also trip "
        "the steepness half, or the two halves are one test")

    _sec, below = _one_site(census_mod, cg,
                            _steps(cg.MATERIALITY_SHARP_STEP_M - 0.01))
    assert below["actionable"] is False
    assert below["disposition"] == cg.MATERIALITY_SUB_FLOOR_LABEL


def test_the_steepness_guard_fires_alone_at_its_own_multiple(census_mod, cg):
    """A 4 cm defect at DOUBLE its cap stays actionable on steepness alone
    — 2.0 x trips, 1.95 x does not — and it contributes nothing worth
    accumulating, so the floor half cannot be what decided it."""
    def _rows(grade, cap):
        return _graded(2, grade=grade, excess=grade - cap, dist=1.0)
    sec, site = _one_site(census_mod, cg, _rows(4.0, 2.0))
    assert site["accumulation_m"] == pytest.approx(0.04)
    assert site["actionable"] is True
    assert site["actionable_reasons"] == ["sharp_grade"]
    assert site["sharp_grade_rows"] == 2
    assert site["worst_cap_multiple"] == pytest.approx(2.0)
    assert site["sharp_step_rows"] == 0, (
        "a graded pair is not a step: distance_m > 0, so row_step_m must "
        "report None")

    _s2, below = _one_site(census_mod, cg, _rows(3.9, 2.0))
    assert below["worst_cap_multiple"] == pytest.approx(1.95)
    assert below["actionable"] is False


def test_a_cap_of_zero_is_exceeded_by_any_grade(cg):
    """A law that allows NO grade (cap 0, or the near-miss sentinel's
    negative cap) cannot be compared by a multiple.  Any grade at all is
    over it; no grade at all is not."""
    assert cg.row_is_sharp(
        _FloorRow(de=0.4, grade=13.3, excess=100.0, dist=3.0)) == "grade"
    assert cg.row_is_sharp(
        _FloorRow(de=0.79, grade=0.0, excess=0.0, dist=38.0)) is None, (
        "a cap-0 dam reports grade 0: there is no grade to be twice, and "
        "its whole shortfall is already in the accumulation")


# ── (3) THE RUNWAY EXEMPTION ────────────────────────────────────────

@pytest.mark.parametrize("role", ["runway", "runway_crossing"])
def test_a_runway_family_site_is_never_floored(census_mod, cg, role):
    """Owner RULINGS 2026-08-07 part 3: reg-derived precision governs the
    runway family (CIFP threshold values, RUNWAY_END_GRADE, the FAA
    vertical-curve K-factors), and "0.5 m is close enough" is not a
    statement anyone made about a runway profile.  The SAME rows that are
    sub-floor on an apron are actionable here."""
    rows = _graded(3, grade=1.5, excess=0.5, dist=20.0, role=role)
    sec, site = _one_site(census_mod, cg, rows)
    assert site["accumulation_m"] == pytest.approx(0.3)
    assert site["accumulation_m"] < cg.MATERIALITY_FLOOR_M
    assert site["runway_family"] is True
    assert site["runway_family_roles"] == [role]
    assert site["actionable"] is True
    assert site["actionable_reasons"] == ["runway_family"]
    assert sec["sites_sub_floor"] == 0

    apron = _graded(3, grade=1.5, excess=0.5, dist=20.0, role="apron")
    _s, control = _one_site(census_mod, cg, apron)
    assert control["runway_family"] is False and control["actionable"] is False


def test_one_runway_row_exempts_the_whole_site(census_mod, cg):
    """"ANY site CONTAINING a runway-family role" — the exemption is a
    property of the SITE, not of each row, because a site is one place and
    a place beside a runway is graded to the runway's precision."""
    rows = _graded(2, grade=1.5, excess=0.5, dist=20.0, role="apron")
    rows.append(("within_shape",
                 _FloorRow(de=0.01, grade=1.5, excess=0.5, dist=0.7,
                           wa="-1", wb="-9", role="apron",
                           pa=(30.0, 0.0), pb=(30.7, 0.0))))
    rows[-1][1].way_b.tags["role"] = "runway"
    sec, site = _one_site(census_mod, cg, rows)
    assert site["runway_family_roles"] == ["runway"]
    assert site["actionable"] is True


# ── (5) THE SUB-FLOOR LABEL — counted, never dropped ────────────────

def test_the_sub_floor_label_is_locked_to_its_register(census_mod, cg):
    """The counted-never-dropped convention (VERSION_DEFERRED_FAMILIES /
    OUT_OF_SCOPE_CLASSES / the wall_foot_ll and disconnected_ring
    precedents): the label a report prints and the reason it prints beside
    it come from ONE register, so moving the floor moves a documented
    number instead of making evidence disappear."""
    assert cg.MATERIALITY_SUB_FLOOR_LABEL in cg.MATERIALITY_SUB_FLOOR_CLASSES
    sec, site = _one_site(census_mod, cg,
                          _graded(3, grade=1.5, excess=0.5, dist=20.0))
    assert sec["sub_floor_label"] == cg.MATERIALITY_SUB_FLOOR_LABEL
    assert set(sec["sub_floor_classes"]) == set(cg.MATERIALITY_SUB_FLOOR_CLASSES)
    entry = sec["sub_floor_classes"][cg.MATERIALITY_SUB_FLOOR_LABEL]
    assert entry["n"] == sec["sites_sub_floor"] == 1
    assert entry["why"] == cg.MATERIALITY_SUB_FLOOR_CLASSES[
        cg.MATERIALITY_SUB_FLOOR_LABEL]
    # …and the site is still fully carried, not a bare count.
    assert sec["sub_floor_rows"] == site["rows"] == 3
    assert sec["sub_floor_adjudicated_rows"] == 3
    assert sec["sub_floor_worst_m"] == site["worst_m"]
    assert site["row_indices"] == [0, 1, 2]


def test_the_floor_partitions_the_adjudicated_sites(census_mod, cg,
                                                    tmp_path):
    """ACTIONABLE + SUB-FLOOR == ADJUDICATED, on a real emitted patch.  A
    site that is neither has been dropped — which is the one thing the
    label exists to prevent — and ``census_one`` refuses rather than
    printing a smaller, friendlier headline."""
    rep, sec = _sites_of_the_fixture(census_mod, cg, tmp_path)
    assert sec["sites_adjudicated"] > 0, "fixture went clean — twin vacuous"
    assert sec["sites_actionable"] + sec["sites_sub_floor"] == \
        sec["sites_adjudicated"]
    assert sec["sites_actionable"] <= sec["sites_adjudicated"] <= sec["sites"]
    assert sec["sites_actionable_visible"] <= sec["sites_actionable"]
    assert sum(d["actionable_sites"] for d in sec["by_family"].values()) == \
        sec["sites_actionable"]
    assert sum(d["sub_floor_sites"] for d in sec["by_family"].values()) == \
        sec["sites_sub_floor"]


def test_the_census_refuses_a_floor_that_drops_a_site(census_mod, cg,
                                                      tmp_path, monkeypatch):
    """The refusal is IN PRODUCTION, not only in this twin."""
    real = census_mod.cluster_sites

    def _lossy(*a, **k):
        sec = real(*a, **k)
        sec["sites_actionable"] = max(0, sec["sites_actionable"] - 1)
        return sec
    monkeypatch.setattr(census_mod, "cluster_sites", _lossy)
    osm = tmp_path / "lossy.osm"
    osm.write_bytes(FIXTURE_PATCH.read_bytes())
    (tmp_path / "lossy.osm.axes.json").write_text(json.dumps({"anchor": None}))
    with pytest.raises(SystemExit) as e:
        census_mod.census_one(osm, cg, top=1, want_sites=True)
    assert "does not partition the adjudicated sites" in str(e.value)


def test_the_floor_knobs_ride_in_every_site_report(census_mod, cg):
    """A site table taken at one floor is not comparable with one taken at
    another, so the constants and the summation travel WITH the counts —
    the ``SITE_RULE`` / ``visibility_note`` convention one level up."""
    sec, _site = _one_site(census_mod, cg,
                           _graded(3, grade=1.5, excess=0.5, dist=20.0))
    assert sec["floor_m"] == cg.MATERIALITY_FLOOR_M
    assert sec["sharp_step_m"] == cg.MATERIALITY_SHARP_STEP_M
    assert sec["sharp_grade_cap_multiple"] == \
        cg.MATERIALITY_SHARP_GRADE_CAP_MULTIPLE
    assert sec["runway_family_roles"] == ["runway", "runway_crossing"]
    assert sec["accumulation_rule"] == cg.MATERIALITY_ACCUMULATION_RULE
    assert sec["floor_ruling"] == cg.MATERIALITY_FLOOR_RULING


def test_the_floor_flags_are_in_the_tool_index():
    """Every promotion lands WITH its index row, in the same commit."""
    text = INDEX.read_text()
    for token in ("actionable", "materiality floor", "sub_floor"):
        assert token in text, (
            f"{token!r} is not in tools/INDEX.md — the headline the site "
            f"census now reports is undiscoverable")


# ══════════════════════════════════════════════════════════════════════
# §10b ROLE-LESS FEATURE WAYS SIDE WITH THEIR HOST (lead 2026-08-07)
# ══════════════════════════════════════════════════════════════════════
#
# The class this removes: an ``o4_feature`` way with no ``role`` tag —
# HECA's 232-way population (shape_interior_ring 92, gap_interior_ring 88,
# gap_drainage_spine 49, crown_spine 3) — falls through
# ``_role_grade_limit`` to the CALLER's default cap and through
# ``_is_groundside`` to AIRSIDE, whatever its host actually is.  On the
# frame of record every such row was hosted by a ``service_junction``, an
# 8 % GROUNDSIDE surface, and reported as an airside 1.5 % violation.

_HOST_SIDING_OSM = """<?xml version='1.0' encoding='UTF-8'?>
<osm version='0.6' generator='harness-twin'>
  <node id='-1' lat='30.50000000000' lon='31.50000000000'>
    <tag k='alt_abs' v='10.00' /></node>
  <node id='-2' lat='30.50000000000' lon='31.50020000000'>
    <tag k='alt_abs' v='10.00' /></node>
  <node id='-3' lat='30.50018000000' lon='31.50020000000'>
    <tag k='alt_abs' v='%(alt)s' /></node>
  <node id='-4' lat='30.50018000000' lon='31.50000000000'>
    <tag k='alt_abs' v='10.00' /></node>
  <way id='-10'>
    <nd ref='-1' /><nd ref='-2' /><nd ref='-3' /><nd ref='-4' /><nd ref='-1' />
    <tag k='role' v='%(role)s' />
    <tag k='shapeID' v='H1' />
  </way>
  <way id='-11'>
    <nd ref='-1' /><nd ref='-2' /><nd ref='-3' /><nd ref='-4' /><nd ref='-1' />
    <tag k='o4_feature' v='shape_interior_ring' />
  </way>
</osm>
"""


def _host_fixture(tmp_path, role="apron", name="host", alt="11.20"):
    osm = tmp_path / f"{name}.osm"
    osm.write_text(_HOST_SIDING_OSM % {"role": role, "alt": alt})
    Path(str(osm) + ".axes.json").write_text(json.dumps({"anchor": None}))
    return osm


def _rows_of(cg, osm):
    fams: dict = {}
    cg.run_checks_law_true(osm, family_out=fams, quiet=True, top_n=0)
    return [(k, r) for k, _t, _b in cg.LAW_FAMILIES
            for r in fams.get(k, [])]


def test_a_role_less_ring_takes_its_hosts_role_and_side(cg, tmp_path):
    """The ruling: "they take the ROLE AND SIDE of their HOST shape".  With
    a GROUNDSIDE host the ring's rows must read groundside — the class this
    fix exists to delete is exactly "airside by default"."""
    rows = _rows_of(cg, _host_fixture(tmp_path, role="service_junction",
                                      alt="13.50"))
    ring = [(k, r) for k, r in rows
            if "-11" in {getattr(getattr(r, "way_a", None), "wid", None),
                         getattr(getattr(r, "way_v", None), "wid", None)}]
    assert ring, "the fixture stopped minting a row on the ring — twin vacuous"
    for _k, r in ring:
        assert cg.row_roles(r) == ("service_junction", "service_junction"), (
            "the ring reported '?' — the host was not resolved")
        assert cg.row_side(r) == "groundside", (
            "the ring is still airside-by-default; the whole class the "
            "ruling names is back")


def test_the_host_stamp_never_touches_the_law(cg, tmp_path):
    """THE INERTNESS CLAIM, proven rather than asserted.  The spec this
    lands under is ADJUDICATION-ONLY, so the host stamp must not reach
    ``_role_grade_limit`` (the cap) or ``_is_groundside`` (which GATES the
    cross-boundary step checks).  Same patch, hosts resolved: identical
    rows, identical families, identical magnitudes."""
    osm = _host_fixture(tmp_path, role="service_junction", alt="13.50")
    fams: dict = {}
    cg.run_checks_law_true(osm, family_out=fams, quiet=True, top_n=0)
    hosts = fams["_feature_hosts"]
    assert hosts["-11"]["host_way"] == "-10"
    assert hosts["-11"]["host_source"] == "shared_nodes"
    assert hosts["-11"]["duplicate"] is True
    ways = cg._parse_osm(osm)[1]
    ring = next(w for w in ways if w.wid == "-11")
    assert ring.tags.get("role") is None and ring.role == "", (
        "resolve_feature_hosts wrote the ROLE tag — that is law input "
        "(the cap resolver, the side partition, the drainage-minimum and "
        "strip-pavement role sets all read it) and moves the population")
    assert cg._is_groundside(ring) is False, (
        "the LAW's own side partition followed the report; only row_side "
        "may")


def test_a_duplicate_ring_is_adjudicated_out_never_dropped(cg, tmp_path):
    """"One geometry, one row set."  The ring carries the host's whole
    vertex set, so the host's rows ARE the row set and the ring's are the
    duplicate: MARKED, and still counted in their family."""
    osm = _host_fixture(tmp_path, role="apron")
    rows = _rows_of(cg, osm)
    def _wid(r, *names):
        for n in names:
            w = getattr(r, n, None)
            if w is not None:
                return w.wid
        return None
    host_rows = [r for _k, r in rows if _wid(r, "way_a", "way_v") == "-10"]
    ring_rows = [r for _k, r in rows if _wid(r, "way_a", "way_v") == "-11"]
    assert host_rows and ring_rows, "the fixture must double-count today"
    # THE COUNTS ARE NO LONGER EQUAL, and that is a REPORTED ASYMMETRY, not
    # a fixture bug (RULINGS 2026-08-21c): the host is role ``apron`` and so
    # prices its INTERIOR at 5 %, while the role-LESS duplicate ring is not
    # an apron and keeps the strict cap — one geometry, two laws.  The claim
    # this twin exists for is unaffected and is asserted in full below: the
    # ring's rows are MARKED, the host's SURVIVE, and nothing is dropped.
    # Whether a role-less duplicate should inherit its host's cap is an
    # owner question docketed by the compose lane, not a fix made here.
    assert all(r.out_of_scope == "role_less_host_duplicate"
               for r in ring_rows)
    assert all(r.out_of_scope is None for r in host_rows), (
        "the HOST's rows are the row set — they must survive")
    adj = cg.adjudication(rows)
    assert adj["out_of_scope_total"] == len(ring_rows)
    assert adj["adjudicated_total"] == len(rows) - len(ring_rows)
    assert "role_less_host_duplicate" in adj["out_of_scope_classes"]
    # COUNTED, NEVER DROPPED: the family still reports every row.
    assert adj["out_of_scope_classes"]["role_less_host_duplicate"]["n"] == \
        len(ring_rows)


def test_the_duplicate_class_is_in_the_out_of_scope_register(cg):
    """One authority for the class and its reason, like every other
    adjudication register in this module."""
    why = cg.OUT_OF_SCOPE_CLASSES["role_less_host_duplicate"]
    assert "one geometry, one row set" in why.lower()
    assert cg.ROLE_LESS_HOST_RULING in why
    assert set(cg.ROLE_LESS_FEATURE_CLASSES) == {
        "shape_interior_ring", "gap_interior_ring", "gap_drainage_spine",
        "crown_spine",
        # THE STRUCTURE RIM (RULINGS 2026-09-06b (1); auto_patch_v2
        # ``emit.osm_adapter.RIM_FEATURE``): the at-grade ring round a
        # below-grade structure's void, in place of the retired wall band.
        "structure_rim",
        # THE BANK FOOT (owner RULINGS 2026-09-09e; auto_patch_v2
        # ``emit.osm_adapter.BANK_FEATURE``): the ring ON THE DEM outside
        # every patch-boundary ring, which the mesh triangulates the 1:3
        # bank up to.  It IS the terrain: no grade law of its own and no
        # host, so it is registered role-less and stays out of
        # ``HOST_CAP_FEATURE_CLASSES``.
        "bank_foot",
        # THE TERRAIN EDGE (owner RULINGS 2026-09-10b/10c, spec §19.3 C12;
        # auto_patch_v2 ``emit.osm_adapter.EDGE_FEATURE``): the open way
        # recording where an adjacent-ground ring was ENDED — at a rim
        # road or a crest.  Role-less for the crown spine's reason: its
        # chords ARE ring edges of the faces it bounds, it carries no
        # grade law of its own, and out of ``HOST_CAP_FEATURE_CLASSES``
        # because it is not a host's hole boundary.
        "terrain_edge",
        # THE APRON INTERIOR LATTICE (spec heca-apron-round2 Amendment 1
        # §1b).  Role-less for the spines' reason: it is an OPEN
        # constrained breakline inside an apron face, so a phantom
        # closing pseudo-edge across the apron would mint artifact pairs
        # the solver never constrained.  It is deliberately NOT in
        # ``HOST_CAP_FEATURE_CLASSES`` — that set is interior RINGS,
        # judged at their host's cap because they ARE the host's own
        # hole boundary.  A lattice is not a ring and does not duplicate
        # its host's geometry (it is the interior the host had no
        # vertices for), so the duplicate adjudication never fires on
        # it; its law is its own registered family,
        # ``apron_lattice_membrane``, which prices each published edge
        # against the budget the SOLVE priced it at.
        "apron_lattice",
        # APRON SPINE STATIONS (spec heca-apron-round3 §1).  Role-less
        # and open for the lattice's reason, and NOT a host-cap class
        # for the same reason: a station is the interior of a taxi
        # crossing the apron never had a vertex for, not a copy of any
        # host's geometry.  Its law is the lattice's own registered
        # family — one membrane, one family.
        "apron_spine_station"}
    assert "apron_lattice" not in cg.HOST_CAP_FEATURE_CLASSES
    assert "apron_spine_station" not in cg.HOST_CAP_FEATURE_CLASSES


def test_a_partial_host_is_not_a_duplicate(cg, tmp_path):
    """The ruling's clause is "where their geometry DUPLICATES a host
    way's".  A ring welded from two shapes' vertices is not that: it is
    sided with its majority host and stays adjudicated, because no single
    host's rows cover it."""
    osm = tmp_path / "partial.osm"
    text = _HOST_SIDING_OSM % {"role": "apron", "alt": "11.20"}
    # A fifth vertex on the ring that NO role-carrying way owns: the ring
    # is now welded from more than its majority host, so the host's rows
    # cannot cover it.
    text = text.replace(
        "  <way id='-10'>",
        "  <node id='-5' lat='30.50009000000' lon='31.50030000000'>"
        "<tag k='alt_abs' v='9.00' /></node>\n  <way id='-10'>")
    text = text.replace(
        "<nd ref='-4' /><nd ref='-1' />\n    <tag k='o4_feature'",
        "<nd ref='-4' /><nd ref='-5' /><nd ref='-1' />\n    "
        "<tag k='o4_feature'")
    osm.write_text(text)
    Path(str(osm) + ".axes.json").write_text(json.dumps({"anchor": None}))
    fams: dict = {}
    cg.run_checks_law_true(osm, family_out=fams, quiet=True, top_n=0)
    h = fams["_feature_hosts"]["-11"]
    assert h["host_way"] == "-10" and h["duplicate"] is False
    assert h["shared_nodes"] == 4 and h["n_nodes"] == 5
    ring = [r for k, _t, _b in cg.LAW_FAMILIES for r in fams.get(k, [])
            if getattr(getattr(r, "way_a", None), "wid", None) == "-11"
            or getattr(getattr(r, "way_v", None), "wid", None) == "-11"]
    assert ring, "twin vacuous"
    assert all(r.out_of_scope is None for r in ring), (
        "a partial host is not a duplicate — its rows stay adjudicated")


def test_the_host_resolution_is_deterministic(cg, tmp_path):
    """A host that depends on dict iteration order is not a measurement.
    Ties break on the emitter's OWN airside-first precedence
    (``layout.AUTHORITY_RANK``), then on the way id."""
    osm = _host_fixture(tmp_path, role="apron")
    seen = set()
    for _ in range(3):
        fams: dict = {}
        cg.run_checks_law_true(osm, family_out=fams, quiet=True, top_n=0)
        seen.add(json.dumps(fams["_feature_hosts"], sort_keys=True))
    assert len(seen) == 1
    assert cg._authority_rank("runway") < cg._authority_rank("apron")
    assert cg._authority_rank("apron") < cg._authority_rank(None)


# ══════════════════════════════════════════════════════════════════════
# §11 THE CONSTRAINED-PAIR DOMAIN KEEPS EVERY RING EDGE (R19-5)
# ══════════════════════════════════════════════════════════════════════
#
# The class this removes: ``iter_shape_grade_constraints``'s LOCKSTEP
# CONSUMPTION branch — a soft airside shape whose sidecar carries baked
# ``pair_caps`` was constrained at EXACTLY the baked pairs, so a ring edge
# the bake never selected (a post-projection insert, a weld) left the
# constrained-pair domain entirely and the census carried NO ROW for it,
# however steep it was.  The docstring has always promised "ring edges
# always kept".  Measured on the owner's 2026-08-12 HECA artifact: 628
# ring edges of graded soft shapes silently unconstrained, among them
# apron -10629's 148.4 % over 8.49 m and 55.6 % over 22.39 m — the two
# worst defects in the airport, with zero census rows.

_RING_EDGE_OSM = """<?xml version='1.0' encoding='UTF-8'?>
<osm version='0.6' generator='harness-twin'>
  <node id='-1' lat='30.50000000000' lon='31.50000000000'>
    <tag k='alt_abs' v='10.00' /></node>
  <node id='-2' lat='30.50000000000' lon='31.50052000000'>
    <tag k='alt_abs' v='10.00' /></node>
  <node id='-3' lat='30.50045000000' lon='31.50052000000'>
    <tag k='alt_abs' v='10.00' /></node>
  <node id='-4' lat='30.50045000000' lon='31.50000000000'>
    <tag k='alt_abs' v='10.00' /></node>
  <node id='-5' lat='30.50022500000' lon='31.50000000000'>
    <tag k='alt_abs' v='%(insert_alt)s' /></node>
  <way id='-10'>
    <nd ref='-1' /><nd ref='-2' /><nd ref='-3' /><nd ref='-4' />
    <nd ref='-5' /><nd ref='-1' />
    <tag k='role' v='apron' />
    <tag k='shapeID' v='R1' />
  </way>
</osm>
"""

# The four ORIGINAL corners of the ring above; node -5 is the INSERT the
# solver's pair-cap bake never saw (it sits mid-way along the -4→-1 edge).
_RING_CORNERS = {
    "-1": (30.50000000000, 31.50000000000),
    "-2": (30.50000000000, 31.50052000000),
    "-3": (30.50045000000, 31.50052000000),
    "-4": (30.50045000000, 31.50000000000),
}


def _ring_edge_fixture(tmp_path, insert_alt="13.00", baked=True):
    """An apron ring with one post-projection INSERT (-5) and a sidecar
    whose ``pair_caps`` bake covers only the four original corners."""
    osm = tmp_path / "ringedge.osm"
    osm.write_text(_RING_EDGE_OSM % {"insert_alt": insert_alt})
    caps = []
    if baked:
        ks = sorted(_RING_CORNERS)
        for i, ka in enumerate(ks):
            for kb in ks[i + 1:]:
                caps.append([list(_RING_CORNERS[ka]),
                             list(_RING_CORNERS[kb]), 0.60])
    Path(str(osm) + ".axes.json").write_text(json.dumps({
        "anchor": [30.50022500000, 31.50026000000], "pair_caps": caps}))
    return osm


def _within_rows(cg, osm):
    fams: dict = {}
    cg.run_checks_law_true(osm, family_out=fams, quiet=True, top_n=0)
    return fams.get("within_shape", [])


def _constrained_ring_edges(cg, osm):
    """The RING-EDGE keys the constrained-pair domain actually carries,
    read through the census's own law context (one code path)."""
    ctx = cg.law_context_from_sidecar(osm, announce=False)
    nodes, ways = cg._parse_osm(osm)
    ll_to_m = cg._ll_to_m_factory(nodes, anchor=tuple(ctx["anchor"]))
    cons = cg.iter_shape_grade_constraints(
        ways, nodes, ll_to_m, 0.015,
        seam_nids=cg._seam_nids(nodes),
        pair_caps_ll=ctx.get("pair_caps_ll"))
    have = {frozenset((c.nid_a, c.nid_b)) for c in cons}
    w = next(w for w in ways if w.wid == "-10")
    ring = w.nids[:-1]
    want = {frozenset((ring[i], ring[(i + 1) % len(ring)]))
            for i in range(len(ring))}
    return want, have


def test_the_bake_never_removes_a_ring_edge_from_the_domain(cg, tmp_path):
    """R19-5, the domain half: with a bake covering only the four original
    corners, the insert's TWO ring edges (-4→-5, -5→-1) are still
    constrained.  The bake is a pair SELECTION over the body; the physical
    boundary edge is the one pair no selection may remove."""
    want, have = _constrained_ring_edges(
        cg, _ring_edge_fixture(tmp_path, baked=True))
    missing = want - have
    assert not missing, (
        f"ring edge(s) {sorted(map(sorted, missing))} left the "
        f"constrained-pair domain — the census can carry no row for them "
        f"however steep they are (HECA -10629's 148 % edge, measured)")
    # …and the UNBAKED reading of the same ring is the same ring-edge set,
    # so the fix did not merely widen one path: both agree on the boundary.
    want_nb, have_nb = _constrained_ring_edges(
        cg, _ring_edge_fixture(tmp_path, baked=False))
    assert want_nb <= have_nb
    assert want == want_nb


def test_a_steep_unbaked_ring_edge_mints_its_census_row(cg, tmp_path):
    """The instrument half: the domain fix has to reach the CENSUS, not
    just the pair iterator.  A 3 m step over the ~25 m insert edge is a
    ~12 % apron edge; before R19-5 the law-true census reported nothing."""
    steep = _within_rows(cg, _ring_edge_fixture(tmp_path, insert_alt="13.00"))
    assert steep, (
        "the census carries NO within-shape row for a 3 m step on an "
        "apron ring edge — the R19-5 class, exactly")
    assert max(r.de_m for r in steep) >= 2.99
    # The twin is not vacuous the other way either: a FLAT insert on the
    # identical geometry mints nothing.
    flat = _within_rows(cg, _ring_edge_fixture(tmp_path, insert_alt="10.00"))
    assert not flat, "the fixture flags a lawful flat ring — twin is noise"


def test_a_within_shape_row_points_at_its_pair_not_its_shape(cg, tmp_path):
    """R19-5, the site half: a within-shape row reports the PAIR MIDPOINT.
    Every other family's lat/lon is the offending way's ring centroid
    (``run_checks._way_latlon``) — on a 1.2 km apron ring that puts a
    148 % edge hundreds of metres from where it is, which is why the HECA
    attribution had to re-derive its sites by hand."""
    osm = _ring_edge_fixture(tmp_path, insert_alt="13.00")
    rows = _within_rows(cg, osm)
    nodes, ways = cg._parse_osm(osm)
    w = next(w for w in ways if w.wid == "-10")
    lls = [nodes[n] for n in w.nids[:-1]]
    centroid = (sum(p[0] for p in lls) / len(lls),
                sum(p[1] for p in lls) / len(lls))
    row = max(rows, key=lambda r: r.de_m)
    # The row's two endpoints are known: -5 and one of its ring neighbours.
    mids = {((nodes["-5"][0] + nodes[k][0]) / 2.0,
             (nodes["-5"][1] + nodes[k][1]) / 2.0) for k in ("-4", "-1")}
    assert any(abs(row.lat - m[0]) < 1e-9 and abs(row.lon - m[1]) < 1e-9
               for m in mids), (
        f"the row reports ({row.lat},{row.lon}); expected one of "
        f"{sorted(mids)} — the pair midpoint")
    assert abs(row.lat - centroid[0]) > 1e-9, (
        "the row still reports the SHAPE centroid")
    # Other families keep the shape centroid — this is a within-shape rule,
    # not a global re-siting.
    fams: dict = {}
    cg.run_checks_law_true(osm, family_out=fams, quiet=True, top_n=0)
    for key, _t, _b in cg.LAW_FAMILIES:
        if key == "within_shape":
            continue
        for r in fams.get(key, []):
            assert r.lat is not None


# ══════════════════════════════════════════════════════════════════════
# §12 THE RUN TAG IS CLAIMED, NEVER FORMATTED (lane/mouthweld 2026-08-15)
# ══════════════════════════════════════════════════════════════════════
#
# The measured defect: the auto tag was minute-resolution, two lawful
# PARALLEL HECA arms (a fix arm and its O4_SVC_MOUTH_PROX_ANCHOR=0
# control) both tagged ``HECA_20260815T1438``, and the second finisher
# silently overwrote the first's patch — each run logged its own
# body_sha (06358baf9c5e / 3053349c0b26) but only one ``.osm`` survived
# on disk.  Parallel correctness builds are the owner-ruled norm
# (2026-08-12), so the tag must be a CLAIM (atomic exclusive create of
# ``<tag>.progress``), not a timestamp format.

def test_two_runs_started_in_the_same_minute_get_distinct_tags(
        build_mod, tmp_path, monkeypatch):
    """The collision itself: with the clock FROZEN (stricter than the
    same minute — the same second), two claims yield two distinct tags,
    and every artifact stem the run writes stays distinct with them."""
    monkeypatch.setattr(build_mod.time, "strftime",
                        lambda fmt, *a: "20260815T143800")
    t1 = build_mod.claim_tag(tmp_path, "HECA")
    t2 = build_mod.claim_tag(tmp_path, "HECA")
    assert t1 != t2, "two runs in the same second share a tag — the " \
                     "second finisher overwrites the first (mouthweld)"
    assert t1 == "HECA_20260815T143800"
    assert t2 == "HECA_20260815T143800_2"
    for suffix in build_mod.TAG_ARTIFACT_SUFFIXES:
        assert (tmp_path / f"{t1}{suffix}") != (tmp_path / f"{t2}{suffix}")
    # The claim is the .progress file, atomically created by each winner.
    assert (tmp_path / f"{t1}.progress").exists()
    assert (tmp_path / f"{t2}.progress").exists()


def test_the_auto_tag_is_seconds_resolution(build_mod, tmp_path):
    """Minute resolution was the defect's precondition — the format half
    of the fix is asserted on the REAL clock, no freezing."""
    tag = build_mod.claim_tag(tmp_path, "HECA")
    assert re.fullmatch(r"HECA_\d{8}T\d{6}", tag), (
        f"auto tag {tag!r} is not <ICAO>_<yyyymmddThhmmss>")


def test_a_stem_with_any_leftover_artifact_is_never_reused(
        build_mod, tmp_path, monkeypatch):
    """The .progress claim alone would miss a stem whose .progress was
    cleaned away but whose .osm survives — exactly the artifact an
    overwrite destroys.  ANY artifact at the stem disqualifies it."""
    monkeypatch.setattr(build_mod.time, "strftime",
                        lambda fmt, *a: "20260815T143800")
    (tmp_path / "HECA_20260815T143800.osm").write_text("<osm/>")
    tag = build_mod.claim_tag(tmp_path, "HECA")
    assert tag == "HECA_20260815T143800_2"
    assert (tmp_path / "HECA_20260815T143800.osm").read_text() == "<osm/>"


def test_an_explicit_tag_refuses_rather_than_overwrites(
        build_mod, tmp_path):
    """--tag is an identity, not a template: suffixing it would make the
    report quote a tag that names a DIFFERENT run's artifacts, so an
    occupied explicit stem is a refusal, and the refusal names the
    artifact in the way."""
    assert build_mod.claim_tag(tmp_path, "HECA", "mytag") == "mytag"
    with pytest.raises(SystemExit) as exc:
        build_mod.claim_tag(tmp_path, "HECA", "mytag")
    assert "mytag" in str(exc.value)
    assert ".progress" in str(exc.value)
    # ...and a leftover artifact with no live claim refuses just the same.
    (tmp_path / "oldtag.osm").write_text("<osm/>")
    with pytest.raises(SystemExit) as exc:
        build_mod.claim_tag(tmp_path, "HECA", "oldtag")
    assert "oldtag.osm" in str(exc.value)


# ═════════════════════════════════════════════════════════════════════
# THE DECLARED-STEP REGISTER — ONE POPULATION, TWO PRODUCERS
# (spec docs/specs/lemd-rim-and-stations-spec.md Amendment 2, 2026-08-28)
#
# The basin trench's pan↔rim boundary is the trench law's own designed
# step — the declared-terrace class — so the emitter PUBLISHES it into
# the census's existing ``terrace_joints`` register instead of anything
# claiming a role-based blanket exemption.  These twins pin that the two
# readers stay one population, and that an UNPUBLISHED joint fails here
# rather than passing in the sim.
# ═════════════════════════════════════════════════════════════════════

def test_the_declared_step_register_has_exactly_two_producers():
    """A third producer, or a second copy of one, is the census-wrapper
    defect in miniature."""
    import auto_patch.layout as LY
    src = Path(inspect.getsourcefile(LY)).read_text()
    i = src.index('"terrace_joints":')
    window = src[i:i + 400]
    assert "_terrace_joints_sidecar(self)" in window
    assert "_basin_wall_joints_sidecar(self)" in window
    assert src.count('"terrace_joints":') == 1, (
        "a second producer of the register would be two populations")


def test_the_basin_wall_joint_is_a_JOINT_not_a_role_exemption():
    """The ruling is explicit: extend the register, NEVER a role-based
    blanket exemption.  A wall joint is a line plus a declared step, read
    by the register's own reader."""
    import auto_patch.object_terrain_assembly as OTA
    rows = OTA.basin_wall_joints_sidecar(object())
    assert rows == [], "a layout with no basin must declare nothing"
    src = inspect.getsource(OTA.basin_wall_joints_sidecar)
    assert '"points"' in src and '"step_m"' in src


def test_the_register_reader_consumes_the_basin_wall_rows(cg):
    """``_terrace_joints_to_m`` is the ONE reader; a basin wall row must
    go through it unchanged, exactly like an apron terrace row."""
    rows = [{"points": [[30.0, 31.0], [30.0, 31.001]], "step_m": 12.72,
             "kind": "basin_trench_wall", "faced": True}]
    out = cg._terrace_joints_to_m(rows, lambda la, lo: (la * 1e5, lo * 1e5))
    assert len(out) == 1
    assert out[0][1] == pytest.approx(12.72)


def test_one_wall_gets_ONE_allowance_never_the_SUM(cg):
    """Two declared-step readers can now speak about the same contact —
    the joint register and the facility's own floor→rim drop.  Summing
    them would hand one wall twice its height and blind a trench born a
    metre too deep, so they are MAX'd.  Strictly stricter than the sum:
    this can only ever ADD rows, never hide one."""
    src = inspect.getsource(cg._declared_step_allowance)
    assert "+" not in src.split("return")[-1], (
        "the two declared-step readers are being SUMMED")
    joints = [([(0.0, -10.0), (0.0, 10.0)], 8.0)]

    class _W:
        role = "tunnel_trench"
        tags = {"role": "tunnel_trench"}
        ref = ""
    # the floor entry is the published (min, max) BAND since RULINGS
    # 2026-09-10ba (a tilted rim gives a tilted floor)
    basin = [((0.0, 0.0), 12.0, (), None, None, None, None, (12.0,))]
    both = cg._declared_step_allowance(joints, basin, -1.0, 0.0, 1.0, 0.0,
                                       _W(), _W(), 0.0, 12.0)
    assert both == pytest.approx(12.0), (
        f"expected max(8.0, 12.0) = 12.0, got {both}")
    joint_only = cg._declared_step_allowance(joints, [], -1.0, 0.0, 1.0,
                                             0.0, _W(), _W(), 0.0, 12.0)
    assert joint_only == pytest.approx(8.0)
    neither = cg._declared_step_allowance([], [], -1.0, 0.0, 1.0, 0.0,
                                          _W(), _W(), 0.0, 12.0)
    assert neither == 0.0


def test_both_step_checks_go_through_the_one_allowance(cg):
    """A step reader that forgets one of the two declarations is exactly
    how the 1,932 LEMD wall rows priced."""
    for fn in (cg._check_vertex_to_edge_step, cg._check_edge_midpoint_step):
        src = inspect.getsource(fn)
        assert "_declared_step_allowance(" in src, fn.__name__
        assert "_basin_declared_drop(" not in src, (
            f"{fn.__name__} still reads a declaration directly")


# ═════════════════════════════════════════════════════════════════════
# AMENDMENT 3 — A BELOW-GRADE WALL UNDER CARRIED GROUND DOES NOT SEVER
# A ROUTE (spec docs/specs/lemd-rim-and-stations-spec.md Amendment 3)
#
# The route/strip terrace twins exist because a SURFACE terrace crossing
# a taxi path is impassable.  A declared ``basin_trench_wall`` arc whose
# crossing point lies inside a below-grade region a pad/shell CARRIES is
# not on the movement surface — the route rides the shell above it.  The
# SAME arc on open ground still prices: that severance is real.
# ═════════════════════════════════════════════════════════════════════

_A3_JOINT_LL = [[30.0, 31.0], [30.0, 31.001], [30.0, 31.002]]


def _a3_axes():
    """One taxi axis crossing BOTH segments of the joint above, in the
    metre frame ``_a3_to_m`` defines."""
    return [([(-5.0, 0.0), (-5.0, 400.0)], None)]


def _a3_to_m(la, lo):
    return ((lo - 31.0) * 1e5, (la - 30.0) * 1e5)


def _a3_row(carried, kind="basin_trench_wall"):
    row = {"points": list(_A3_JOINT_LL), "step_m": 12.718, "kind": kind,
           "faced": True}
    if carried is not None:
        row["carried"] = carried
    return row


def _a3_run(cg, row):
    joints_m = cg._terrace_joints_to_m([row], _a3_to_m)
    flags = cg._terrace_joint_carried_flags([row])
    # the axis must actually cross, or the twin proves nothing
    axes = [([( -5.0, joints_m[0][0][0][1]),
              (5.0, joints_m[0][0][0][1])], None)]
    return cg._check_terrace_joint_crosses_route(
        joints_m, None, axes, carried_flags=flags)


def test_a_declared_wall_under_a_CARRIED_span_severs_no_route(cg):
    assert _a3_run(cg, _a3_row([True, True, True])) == []


def test_the_same_wall_on_OPEN_ground_still_prices(cg):
    rows = _a3_run(cg, _a3_row([False, False, False]))
    assert rows, "an uncarried wall crossing a route must price in full"
    assert rows[0].de_m == pytest.approx(12.718)


def test_a_wall_running_OFF_the_shell_prices_at_the_segment_it_leaves(cg):
    """Both endpoints of the crossed segment must be carried — a wall
    that leaves the shell severs the route exactly where it leaves."""
    rows = _a3_run(cg, _a3_row([True, False, False]))
    assert rows, "the uncarried stretch must still price"


def test_an_APRON_TERRACE_joint_is_never_exempted(cg):
    """The conditional is scoped to the basin wall KIND: an apron
    terrace carries no shell and is judged exactly as before, even if a
    stray ``carried`` field appears on its row."""
    rows = _a3_run(cg, _a3_row([True, True, True], kind="apron_terrace"))
    assert rows, "an apron terrace joint must never take the exemption"


def test_a_row_with_NO_flags_reads_all_false(cg):
    """Every patch built before the amendment — and every apron terrace
    row — is judged exactly as before."""
    assert cg._terrace_joint_carried_flags([_a3_row(None)]) == [
        [False, False, False]]
    rows = _a3_run(cg, _a3_row(None))
    assert rows


def test_malformed_flags_never_grant_an_exemption(cg):
    """A flag list that does not align with the points is not a
    declaration; it reads all-False rather than blinding the check."""
    assert cg._terrace_joint_carried_flags(
        [_a3_row([True])]) == [[False, False, False]]
    assert cg._terrace_joint_carried_flags(
        [_a3_row("yes")]) == [[False, False, False]]


def test_the_carried_flags_are_INDEX_ALIGNED_with_the_joints(cg):
    """The two readers walk the same rows in the same order; a row one
    skips and the other keeps would mis-attribute every exemption."""
    rows = [_a3_row([True, True, True]),
            {"points": [[30.0, 31.0]], "step_m": 1.0},   # dropped: <2 pts
            _a3_row([False, False, False])]
    joints = cg._terrace_joints_to_m(rows, _a3_to_m)
    flags = cg._terrace_joint_carried_flags(rows)
    assert len(joints) == len(flags) == 2
    assert flags[0] == [True, True, True]
    assert flags[1] == [False, False, False]


def test_both_terrace_twins_take_the_flags(cg):
    for fn in (cg._check_terrace_joint_crosses_route,
               cg._check_terrace_joint_in_runway_strip):
        assert "carried_flags" in inspect.signature(fn).parameters, (
            fn.__name__)
    src = inspect.getsource(cg.run_checks)
    assert src.count("carried_flags=terrace_carried") == 2


# ── RULINGS 2026-08-31d: PER-TILE CONFIGS ARE OPTIONAL ──────────────────
#
# "A tile entry finding no per-tile cfg DEFAULTS TO THE USER'S GLOBAL
# SETTINGS — it does not refuse.  Refusal is reserved for a global config
# that itself lacks the required key."  What "required" means is per STEP:
# ``default_website`` is required by the imagery half and by nothing else,
# so a frame without one builds the GEOMETRY (the surface every lane
# measures) and stands the textures down BY NAME.  Before this, the SPJC
# -13-078 tile — an owner acceptance site — was unbuildable in every lane.

class _FakeTile:
    def __init__(self, site="", zl=16):
        self.default_website = site
        self.default_zl = zl


def test_a_resolved_provider_builds_the_whole_tile(build_mod):
    cap = build_mod.imagery_capability(_FakeTile("Arc"),
                                       {"action": "provisioned"})
    assert cap["ok"] and cap["default_website"] == "Arc"


def test_no_provider_anywhere_STANDS_IMAGERY_DOWN_and_does_not_refuse(
        build_mod):
    """The 31d case: no per-tile cfg, so the tile runs on the user's
    global settings — which carry no provider BY CONSTRUCTION."""
    cap = build_mod.imagery_capability(
        _FakeTile(""), {"action": "derived-from-global-defaults",
                        "global_source": "/x/Ortho4XP.cfg"})
    assert cap["ok"] is False
    assert "global" in cap["reason"]
    assert "STANDS DOWN" in cap["note"] and "2026-08-31d" in cap["note"]
    # …and it is a NOTE, not an exit: nothing in the resolver raises.
    assert isinstance(cap, dict)


def test_a_provider_is_never_INVENTED(build_mod):
    """Owner ruling 2026-08-12b survives 31d: the entry reports the
    provider ABSENT, it does not pick one."""
    cap = build_mod.imagery_capability(_FakeTile(""), {"action": "x"})
    assert cap["default_website"] == ""
    src = inspect.getsource(build_mod.imagery_capability)
    for invented in ("BI", "Arc", "GO2", "USA2"):
        assert f'"{invented}"' not in src, invented


def test_the_geometry_half_runs_and_the_imagery_half_is_skipped(build_mod):
    """The step list is scoped by the capability, and the build RECORDS
    which halves ran — a geometry-only tile must never read as a full
    one."""
    src = inspect.getsource(build_mod.build_tile)
    # the imagery half is scoped OUT by name, as a recorded skip under
    # THE STEP CONTRACT (§3b) — never a silently shorter plan
    assert 'if not imagery["ok"]:' in src
    assert 'skip_steps.setdefault(name, imagery["note"])' in src
    assert 'run_tile_steps(tile, plan, prog, skip_steps=skip_steps)' in src
    assert '"steps_run": [n for n, _ in plan if n in timings]' in src
    assert '"steps_skipped": skipped' in src
    src = inspect.getsource(build_mod)
    assert 'frame["imagery"] = result.get("imagery")' in src
    assert 'frame["tile_steps_run"] = result.get("steps_run")' in src
    assert 'frame["steps_skipped"] = result.get("steps_skipped")' in src


def test_the_old_provider_REFUSAL_is_gone(build_mod):
    """Deleted, not gated (29f) — the refusal 31d overturns is not in the
    source at all."""
    src = inspect.getsource(build_mod)
    assert "EMPTY default_website" not in src


def test_BOTH_tile_entries_share_ONE_frame_resolver(build_mod):
    """Two arrangements of "which cfg is this tile on, and what can it
    build" is the census-wrapper defect at one remove."""
    from pathlib import Path as _P
    assert callable(build_mod.resolve_tile_frame)
    entry = (_P(build_mod.__file__).resolve().parents[1]
             / "run_tile_mesh_only.py").read_text()
    assert "from build_airport import resolve_tile_frame" in entry
    assert "resolve_tile_frame(" in entry
    # the mesh-only entry runs steps 1-2, which need no provider at all
    assert "steps 1-2 need no provider, continuing" in entry


# ── THE OUT-OF-PYTEST BUILD PATH (2026-09-01, lane hard5) ─────────────
# The mod-cache overlay and the per-test write guard are pytest FIXTURES.
# A plain ``venv/bin/python probe.py`` doing ``import conftest;
# cached_airport_layout(...)`` — the attribution-probe idiom — armed
# NEITHER, built against the SHARED ``Airport_mod_cache`` and wrote
# ``Airport_mod_cache/SPLP Test/o4_object_footprints_-13-078.cache``
# into it, flagging two other lanes' concurrent arms CONTAMINATED.
# ``conftest.arm_lane_local_derived_caches`` closes it AT THE ONE SITE
# every layout build passes through.

def test_every_layout_build_arms_the_derived_cache_redirect():
    """``_build_cached`` — the single ``build_airport_pavement`` call site
    the whole suite and every probe share — arms the redirect first."""
    conftest = _conftest()
    src = inspect.getsource(conftest._build_cached)
    assert "arm_lane_local_derived_caches()" in src, (
        "the arming left the one path every out-of-pytest probe takes — "
        "that is exactly how the shared Airport_mod_cache got written")
    # ...and it runs BEFORE the builder is even imported (the engine
    # resolves its cache roots at import/call time).
    assert (src.index("arm_lane_local_derived_caches()")
            < src.index("from auto_patch.pipeline import")), (
        "arming after the import/build is arming after the write")


def test_arming_yields_to_a_fixture_or_the_harness(monkeypatch):
    """When something already owns the redirect (the session fixture, or
    ``build_airport.py``'s own), arming is a NO-OP — one authority."""
    conftest = _conftest()
    monkeypatch.setenv("O4_AIRPORT_MOD_CACHE_DIR", "/somewhere/lane/local")
    assert conftest.arm_lane_local_derived_caches() is False
    assert os.environ["O4_AIRPORT_MOD_CACHE_DIR"] == "/somewhere/lane/local"


def test_arming_redirects_off_the_shared_corpus(monkeypatch, build_mod):
    """With nothing armed, the redirect lands OUTSIDE the shared data
    repo and the overlay is seeded from it (warm reads, lane-local
    writes) — the fixture's own guarantee, on the probe path."""
    conftest = _conftest()
    monkeypatch.delenv("O4_AIRPORT_MOD_CACHE_DIR", raising=False)
    monkeypatch.delenv("O4_DSF_CACHE_DIR", raising=False)
    monkeypatch.setattr(conftest, "_LANE_AIRPORT_MOD_CACHE_DIR", None,
                        raising=False)
    assert conftest.arm_lane_local_derived_caches() is True
    overlay = os.environ["O4_AIRPORT_MOD_CACHE_DIR"]
    dsf = os.environ["O4_DSF_CACHE_DIR"]
    repo = os.path.realpath(build_mod.DATA_REPO)
    for path in (overlay, dsf):
        assert not os.path.realpath(path).startswith(repo + os.sep), (
            f"{path} is INSIDE the shared data repo — the redirect "
            f"redirects nothing")
        assert os.path.isdir(path)
    # Seeded from the shared root, so reads stay warm.
    shared = os.path.join(build_mod.DATA_REPO, "Airport_mod_cache")
    if os.path.isdir(shared):
        assert len(os.listdir(overlay)) == len(os.listdir(shared))
    # Idempotent once armed.
    assert conftest.arm_lane_local_derived_caches() is False


# ══════════════════════════════════════════════════════════════════════
# §3b THE TILE STEP LOOP NEVER LIES (silent-step-failure class: LEMD
#     +40-004, 2026-09-02 — a mesh step whose .node input was never
#     written printed its ERROR, was reported "DONE 0.0s", and the run
#     exited 0)
# ══════════════════════════════════════════════════════════════════════

class _StepProg:
    def __init__(self):
        self.notes = []

    def note(self, msg):
        self.notes.append(msg)


def _fresh_flags():
    import O4_UI_Utils as UI
    UI.red_flag = False
    UI.is_working = False
    return UI


def test_a_step_returning_0_stops_the_tile_at_that_step(build_mod):
    """Ortho4XP step functions signal failure ONLY by ``return 0`` after
    printing their ERROR — never by exception, never by red_flag.  The
    runner must stop the tile there (engine H1 parity): no DONE note, no
    later step, rc != 0."""
    _fresh_flags()
    prog = _StepProg()
    ran = []
    plan = (("1 vector", lambda t: ran.append("vector") or 1),
            ("2 mesh", lambda t: 0),
            ("3 masks", lambda t: ran.append("masks") or 1))
    with pytest.raises(SystemExit) as exc:
        build_mod.run_tile_steps(object(), plan, prog)
    assert "2 mesh" in str(exc.value) and "FAILED" in str(exc.value)
    assert ran == ["vector"], "the failed step must be the LAST to run"
    assert not any("2 mesh DONE" in n for n in prog.notes), \
        "a failed step must never be reported DONE"


def test_the_masks_convention_a_bare_return_is_success(build_mod):
    """``build_masks``' normal exit is a bare ``return`` (None): the
    failure predicate is ``result == 0`` exactly, never falsiness."""
    _fresh_flags()
    prog = _StepProg()
    plan = (("1 vector", lambda t: 1),
            ("3 masks", lambda t: None),
            ("4 tile", lambda t: 1))
    timings, skipped = build_mod.run_tile_steps(object(), plan, prog)
    assert sorted(timings) == ["1 vector", "3 masks", "4 tile"]
    assert skipped == {}
    assert sum("DONE" in n for n in prog.notes) == 3


def test_a_red_flagged_step_is_a_cancellation_not_a_failure(build_mod,
                                                            monkeypatch):
    """A red-flagged step also returns 0 — the engine session reports
    that as stopped, not failed, and so does the runner."""
    UI = _fresh_flags()
    monkeypatch.setattr(UI, "red_flag", False)

    def cancelled(tile):
        UI.red_flag = True
        return 0

    with pytest.raises(SystemExit) as exc:
        build_mod.run_tile_steps(object(), (("2 mesh", cancelled),),
                                 _StepProg())
    assert "red flag" in str(exc.value)
    assert "FAILED" not in str(exc.value)


def test_a_declared_skip_is_recorded_and_never_run(build_mod):
    """An INAPPLICABLE step (mesh in a geometry-only tile frame) is an
    explicit recorded skip — the step function is never called, so it
    can never run into its own missing-input failure."""
    _fresh_flags()
    prog = _StepProg()
    ran = []
    plan = (("1 vector", lambda t: ran.append("vector") or 1),
            ("2 mesh", lambda t: ran.append("mesh") or 0),
            ("3 masks", lambda t: ran.append("masks") or 1))
    reason = "geometry-only frame: step 1 emits no mesh inputs"
    timings, skipped = build_mod.run_tile_steps(
        object(), plan, prog, skip_steps={"2 mesh": reason})
    assert ran == ["vector", "masks"]
    assert skipped == {"2 mesh": reason}
    assert "2 mesh" not in timings
    assert any("2 mesh SKIPPED" in n for n in prog.notes)


def test_imagery_not_ok_RECORDS_steps_3_and_4_as_skipped_and_never_runs_them(
        build_mod, monkeypatch, tmp_path):
    """RULINGS 2026-08-31d meets THE STEP CONTRACT: a frame with no
    imagery provider stands the imagery half down as an EXPLICIT RECORDED
    SKIP — ``build_tile`` names steps 3 masks + 4 tile in
    ``steps_skipped`` with the ruling's note as the reason, their step
    functions are never called, ``steps_run`` carries only the geometry
    half, and the result still carries ``imagery`` for the frame."""
    import sys as _sys
    _fresh_flags()
    for m in ("O4_Imagery_Utils", "O4_Vector_Map", "O4_Mesh_Utils",
              "O4_Mask_Utils", "O4_Tile_Utils"):
        __import__(m)
    IMG = _sys.modules["O4_Imagery_Utils"]
    for init in ("initialize_extents_dict", "initialize_color_filters_dict",
                 "initialize_providers_dict",
                 "initialize_combined_providers_dict"):
        monkeypatch.setattr(IMG, init, lambda: None)
    ran = []
    monkeypatch.setattr(_sys.modules["O4_Vector_Map"], "build_poly_file",
                        lambda t: ran.append("1 vector") or 1)
    monkeypatch.setattr(_sys.modules["O4_Mesh_Utils"], "build_mesh",
                        lambda t: ran.append("2 mesh") or 1)
    monkeypatch.setattr(_sys.modules["O4_Mask_Utils"], "build_masks",
                        lambda t: ran.append("3 masks"))
    monkeypatch.setattr(_sys.modules["O4_Tile_Utils"], "build_tile",
                        lambda t: ran.append("4 tile") or 1)
    monkeypatch.setattr(build_mod, "apply_xplane_install_paths",
                        lambda: {})

    class _Tile:
        # A tile frame has coordinates: ``build_tile`` judges the
        # bathymetry band admission on it before step 1 (2026-09-04);
        # with no ``masks_use_DEM_too`` the band is not wanted — settled.
        lat, lon = 40, -4
        build_dir = str(tmp_path)
        default_website, default_zl = "", 16
        auto_patch = modify_custom_airports = True

    prov = {"action": "derived-from-global-defaults",
            "global_source": "/x/Ortho4XP.cfg", "cfg": None}
    imagery = build_mod.imagery_capability(_Tile(), prov)
    assert imagery["ok"] is False
    monkeypatch.setattr(build_mod, "resolve_tile_frame",
                        lambda lat, lon, bd, prog: (_Tile(), prov, imagery))
    prog = _StepProg()
    result = build_mod.build_tile(40, -4, str(tmp_path), prog)
    assert ran == ["1 vector", "2 mesh"], "the imagery half must NEVER run"
    assert result["steps_run"] == ["1 vector", "2 mesh"]
    assert result["steps_skipped"] == {"3 masks": imagery["note"],
                                       "4 tile": imagery["note"]}
    assert sorted(result["step_seconds"]) == ["1 vector", "2 mesh"]
    assert result["imagery"] is imagery
    assert any("3 masks SKIPPED" in n for n in prog.notes)
    assert any("4 tile SKIPPED" in n for n in prog.notes)
    assert not any("3 masks DONE" in n or "4 tile DONE" in n
                   for n in prog.notes)
    # ...and a caller's own skip is added to, never overwritten by, the
    # imagery half.
    ran.clear()
    result = build_mod.build_tile(40, -4, str(tmp_path), _StepProg(),
                                  skip_steps={"2 mesh": "caller's reason"})
    assert ran == ["1 vector"]
    assert result["steps_skipped"] == {"2 mesh": "caller's reason",
                                       "3 masks": imagery["note"],
                                       "4 tile": imagery["note"]}
    assert result["steps_run"] == ["1 vector"]


# ══════════════════════════════════════════════════════════════════════
# §12 THE V2 ENGINE THROUGH THE SAME ENTRY (2026-09-04; v1 RETIRED
# 2026-09-13au, so ``--engine`` is gone and v2 is the only path)
# ══════════════════════════════════════════════════════════════════════
# RULINGS 2026-09-03d: v2 is built beside v1.  RULINGS 2026-09-13au: v1 is
# retired — the setting, the selector and the harness flag go, v2 builds
# and measures through THIS entry (tool discipline 7e90032): same
# refusals, same guard, same ledger, same frame — plus the engine and the
# law-table digest recorded and keyed, at their pre-retirement spellings.

def test_the_build_entry_has_no_engine_flag(build_mod, monkeypatch, tmp_path):
    """STAGE A of the v1 retirement (RULINGS 2026-09-13au): there is no
    engine to select, so ``--engine`` is not an argument any more — argparse
    refuses it (exit 2) rather than a lane believing it chose something."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        build_mod.main(["CYXY", "--engine", "v2", "--no-ledger"])
    assert exc.value.code == 2


def test_the_build_entry_refuses_the_flags_v2_does_not_wire(build_mod):
    """A flag that quietly did nothing on the v2 path is how a lane comes
    to believe it measured something it did not (the --solve-capture /
    --tile precedent).  ``--dem``, ``--geometry-only`` and
    ``--solve-capture`` were wired for v1 only; each refuses BY NAME,
    before the cwd check and before the ledger re-exec."""
    for extra in (["--dem", "-500"],
                  ["--geometry-only"], ["--solve-capture", "/tmp/cap"]):
        with pytest.raises(SystemExit) as exc:
            build_mod.main(["CYXY", *extra])
        assert f"REFUSING: {extra[0]} is not wired" in str(exc.value), extra


def test_the_build_entry_admits_a_tile_run(build_mod, monkeypatch, tmp_path):
    """``--tile`` is WIRED (2026-09-04, lane v2app; the engine is v2 by
    retirement since 2026-09-13au).  The by-name refusals must not fire;
    the run proceeds to the cwd check like any tile run (which refuses
    HERE, from a non-engine cwd, with ITS message — proof the gate above
    was passed, not that a tile was built)."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        build_mod.main(["OTHH", "--tile", "25", "51", "--no-ledger"])
    assert "is not wired" not in str(exc.value)
    assert "REFUSING" in str(exc.value)


def test_the_engine_constant_keys_every_build_as_v2(build_mod):
    """The frame field and the artifact-ledger variant part keep the
    spelling ``--engine v2`` wrote (RULINGS 2026-09-13au): a frame or a
    stored arm from before the retirement still reads and still keys the
    same artifact."""
    assert build_mod.ENGINE == "v2"
    assert not hasattr(build_mod, "apply_engine_override"), \
        "the --engine override went with the flag"


def test_the_engine_is_keyed_into_the_artifact_ledger_only_for_v2(build_mod):
    """Two artifacts at one tree/corpus (v1's patch, v2's patch) must never
    be served for each other — and every v1 key ever stored must stay a
    HIT (a control that exists is never rebuilt, BUILD ECONOMY)."""
    AL = build_mod.AL
    v1 = AL.build_variant()
    assert "engine" not in v1
    assert AL.build_variant(engine="v1",
                            law_tables_sha256="deadbeef") == v1, \
        "a v1 arm keys exactly as before --engine existed"
    v2 = AL.build_variant(engine="v2",
                          law_tables_sha256="deadbeef")
    assert v2["engine"] == "v2" and v2["law_tables_sha256"] == "deadbeef"
    corpus = {"sha256": "c0ffee"}
    assert AL.artifact_key("tree", "CYXY", {}, corpus, v1) != \
        AL.artifact_key("tree", "CYXY", {}, corpus, v2)
    v2b = AL.build_variant(engine="v2",
                           law_tables_sha256="0badf00d")
    assert AL.artifact_key("tree", "CYXY", {}, corpus, v2) != \
        AL.artifact_key("tree", "CYXY", {}, corpus, v2b), \
        "a different law-table set is a different artifact"


def test_the_v2_law_table_digest_names_every_table_and_moves_with_bytes(
        build_mod, tmp_path):
    real = build_mod.v2_law_tables_digest(ROOT)
    law_dir = ROOT / build_mod.V2_LAW_DIR
    assert real["files"] == sorted(p.name for p in law_dir.glob("*.toml"))
    assert real["sha256"] and len(real["sha256"]) == 64
    copy = tmp_path / build_mod.V2_LAW_DIR
    copy.mkdir(parents=True)
    for p in law_dir.glob("*.toml"):
        (copy / p.name).write_bytes(p.read_bytes())
    assert build_mod.v2_law_tables_digest(tmp_path)["sha256"] == real["sha256"]
    first = sorted(copy.glob("*.toml"))[0]
    first.write_bytes(first.read_bytes() + b"\n# one byte more\n")
    assert build_mod.v2_law_tables_digest(tmp_path)["sha256"] != real["sha256"]
    assert build_mod.v2_law_tables_digest(tmp_path / "nowhere")["sha256"] is None


def _stub_v2_pipeline(monkeypatch, *, status="optimal", sidecar=True):
    """The v2 pipeline as three stub modules: ``build`` writes the patch
    the real adapter writes (``<ICAO>_auto.patch.osm`` + ``.axes.json``)
    and returns the fields ``build_patch_v2`` reads."""
    import types

    class _Status:
        def __init__(self, v): self.value = v

    class _Sol:
        def __init__(self, v):
            self.status = _Status(v); self.message = f"stub {v}"

    class _Paths:
        def __init__(self, patch, side):
            self.patch, self.sidecar = patch, side
            self.ways, self.nodes = 3, 9

    class _Res:
        pass

    def build(icao, inputs, out_dir, config=None, law=None, out=print):
        out(f"[{icao}] stub build")
        d = Path(out_dir); d.mkdir(parents=True, exist_ok=True)
        patch = d / f"{icao}_auto.patch.osm"
        patch.write_text("<osm/>")
        side = Path(str(patch) + ".axes.json")
        if sidecar:
            side.write_text("{}")
        (d / f"{icao}.report.json").write_text("{}")
        r = _Res()
        r.solution = _Sol(status)
        r.paths = _Paths(patch, side) if status == "optimal" else None
        r.report = {"load": {"dem_provenance": {"frame": "production"}},
                    "verify": {"by_family": {"strip_seam_tear": 0}}}
        r.wall = {"total": 0.1}; r.lp_size = {"rows_ub": 1}; r.pieces = None
        return r

    class _Law:
        ruleset_key = "icao"

        @classmethod
        def for_airport(cls, icao): return cls()

    mods = {
        "auto_patch_v2": types.ModuleType("auto_patch_v2"),
        "auto_patch_v2.planar": types.ModuleType("auto_patch_v2.planar"),
        "auto_patch_v2.planar.__main__": types.ModuleType("auto_patch_v2.planar.__main__"),
        "auto_patch_v2.pipeline": types.ModuleType("auto_patch_v2.pipeline"),
        "auto_patch_v2.pipeline.build": types.ModuleType("auto_patch_v2.pipeline.build"),
        "auto_patch_v2.law": types.ModuleType("auto_patch_v2.law"),
    }
    # The law-table DIGEST is the engine's own (one implementation, the
    # harness delegates): captured from the real package before the stub
    # replaces it on sys.modules.
    from auto_patch_v2.law import law_tables_digest as _real_digest
    mods["auto_patch_v2.planar.__main__"].default_inputs = \
        lambda **kw: {"stub_inputs": kw}
    mods["auto_patch_v2.pipeline.build"].build = build
    mods["auto_patch_v2.pipeline.build"].Config = lambda: None
    mods["auto_patch_v2.law"].Law = _Law
    mods["auto_patch_v2.law"].law_tables_digest = _real_digest
    for name, m in mods.items():
        monkeypatch.setitem(sys.modules, name, m)


def _run_build_patch_v2(build_mod, monkeypatch, tmp_path, **kw):
    repo, lane = _lock_repo(tmp_path)
    out = tmp_path / "out"
    prog = build_mod.Progress(out / "twin.progress")
    guard = build_mod.SharedRepoWriteGuard(set(), lane, repo=repo)
    return build_mod.build_patch_v2("CYXY", lane, out, "twin", prog,
                                    write_guard=guard, **kw), out


def test_build_patch_v2_publishes_every_build_patch_key_and_records_the_engine(
        build_mod, monkeypatch, tmp_path):
    """ONE frame/result/ledger path for both engines: the v2 result carries
    every key ``build_patch`` publishes (the twin above enumerates the
    frame-and-guard ones; the rest are read by ``main`` by name), plus
    ``engine`` and the law-table digest; the patch lands under the
    harness names, the v2 products under ``<tag>.v2/``."""
    import inspect
    import re
    _stub_v2_pipeline(monkeypatch)
    result, out = _run_build_patch_v2(build_mod, monkeypatch, tmp_path)
    ret = inspect.getsource(build_mod.build_patch).rsplit("return {", 1)[1]
    v1_keys = set(re.findall(r'"([a-z_0-9]+)":', ret)) - {"elevation_m", "world",
                                                          "is_synthetic", "source"}
    assert v1_keys >= {"patch", "sidecar", "body_sha256", "shapes",
                       "dem_inset_provenance", "engine_solve_model"}
    missing = v1_keys - set(result)
    assert not missing, f"build_patch_v2 result omits {sorted(missing)}"
    assert result["engine"] == "v2"
    assert "sha256" in result["law_tables"]
    assert result["patch"] == str(out / "twin.osm") and (out / "twin.osm").exists()
    assert result["sidecar_present"] and (out / "twin.osm.axes.json").exists()
    assert (out / "twin.v2" / "CYXY.report.json").exists()
    assert not (out / "twin.v2" / "CYXY_auto.patch.osm").exists(), \
        "moved, not copied — one artifact, one name"
    assert result["write_guard_armed"] and result["engine_solve_model"] is None
    assert result["dem_inset_provenance"] == {"frame": "production"}
    assert result["v2"]["status"] == "optimal"
    assert result["v2"]["verify_by_family"] == {"strip_seam_tear": 0}


def test_build_patch_v2_refuses_an_infeasible_solve_and_a_missing_sidecar(
        build_mod, monkeypatch, tmp_path):
    _stub_v2_pipeline(monkeypatch, status="infeasible")
    with pytest.raises(SystemExit) as exc:
        _run_build_patch_v2(build_mod, monkeypatch, tmp_path)
    assert "infeasible" in str(exc.value) and "REFUSING" in str(exc.value)
    _stub_v2_pipeline(monkeypatch, sidecar=False)
    with pytest.raises(SystemExit) as exc:
        _run_build_patch_v2(build_mod, monkeypatch, tmp_path / "b")
    assert "sidecar" in str(exc.value)
    result, _out = _run_build_patch_v2(build_mod, monkeypatch, tmp_path / "c",
                                       allow_no_sidecar=True)
    assert result["sidecar_present"] is False


def test_main_dispatches_the_v2_engine_through_the_same_frame_and_ledger_path():
    """Source-level: ``main`` calls ``build_patch_v2`` on the ONE airport
    path (v1 retired, RULINGS 2026-09-13au), keys the engine constant and
    the law digest into the artifact-ledger variant, and stamps both into
    ``frame.json`` — no second frame, no second store, and no selector."""
    src = (HARNESS / "build_airport.py").read_text()
    assert "result = build_patch_v2(" in src
    assert "args.engine" not in src, "the --engine selector is retired"
    assert 'frame["engine"] = ENGINE' in src
    assert 'frame["law_tables"]' in src
    assert "engine=ENGINE," in src and "law_tables_sha256=" in src
    assert src.count("AL.store_build(") == 1, "one store, one engine"


# ── CAP BY EDGE PORTION (owner RULINGS 2026-09-04t-2) ─────────────────────
# A junction / road stamped ``o4_grade_law='apron'`` takes the apron cap on
# the portion ALONG the apron (a long shared run) only; a mouth keeps its
# own cap.  The oracle's reading (``check_grade.mark_apron_edge_portions``)
# and v2's law table carry ONE value for "long".

def _portion_patch(tmp_path: Path, *, far_grade: float, run_grade: float,
                   mouth_grade: float, name: str = "PORTION") -> Path:
    """An apron square (100 m) with a junction ALONG its whole east edge
    (40 m wide, shared run 100 m >= 1.5 widths: a long edge) and a
    junction joining its south edge across 20 m (20 m wide, shared 20 m
    < 1.5 widths: a mouth).  Both junctions are stamped
    ``o4_grade_law='apron'`` + letter D as v1 stamps them.  ``run_grade``
    is the grade along the shared run, ``far_grade`` along the long
    junction's far (off-apron) edge, ``mouth_grade`` along the mouth
    junction's length."""
    import math
    r = 6378137.0
    cos0 = math.cos(math.radians(_TWIN_ANCHOR[0]))

    def ll(x, y):
        return (_TWIN_ANCHOR[0] + math.degrees(y / r),
                _TWIN_ANCHOR[1] + math.degrees(x / (r * cos0)))

    nodes: dict = {}
    order: list = []
    nid = [0]

    def node(x, y, alt):
        key = (round(x, 3), round(y, 3))
        if key not in nodes:
            nid[0] -= 1
            lat, lon = ll(x, y)
            nodes[key] = (str(nid[0]), lat, lon, alt)
            order.append(key)
        return nodes[key][0]

    ways = []

    def way(pts_alt, tags):
        ns = [node(x, y, a) for (x, y, a) in pts_alt]
        nid[0] -= 1
        ways.append((str(nid[0]), ns + [ns[0]], tags))

    run_top = run_grade * 100.0
    # the apron: flat except its east edge, which follows the shared run
    way([(0, 0, 0.0), (100, 0, 0.0), (100, 100, run_top), (0, 100, 0.0)],
        {"role": "apron", "shapeID": "A1", "ref": "apron1"})
    # the long junction: shares (100,0)-(100,100); far edge at far_grade
    way([(100, 0, 0.0), (140, 0, 0.0), (140, 100, far_grade * 100.0), (100, 100, run_top)],
        {"role": "junction", "shapeID": "J1", "ref": "pav1", "code_letter": "D",
         "o4_grade_law": "apron"})
    # the mouth junction: shares (40,0)-(60,0) only; 80 m long southward
    way([(40, -80, -mouth_grade * 80.0), (60, -80, -mouth_grade * 80.0), (60, 0, 0.0), (40, 0, 0.0)],
        {"role": "junction", "shapeID": "J2", "ref": "pav2", "code_letter": "D",
         "o4_grade_law": "apron"})
    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm version='0.6' generator='portion-twin'>"]
    for key in order:
        n, lat, lon, alt = nodes[key]
        out.append(f"  <node id='{n}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                   f"<tag k='alt_abs' v='{alt:.2f}' /></node>")
    for wid, nids, tags in ways:
        out.append(f"  <way id='{wid}'>")
        out += [f"    <nd ref='{n}' />" for n in nids]
        out += [f"    <tag k='{k}' v='{v}' />" for k, v in tags.items()]
        out.append("  </way>")
    out.append("</osm>")
    osm = tmp_path / f"{name}_auto.patch.osm"
    osm.write_text("\n".join(out) + "\n")
    Path(str(osm) + ".axes.json").write_text(json.dumps({
        "anchor": list(_TWIN_ANCHOR), "ruleset": "icao"}))
    return osm


def test_the_apron_cap_binds_the_shared_portion_only_and_a_mouth_keeps_its_own(cg, tmp_path):
    """04t-2: the long junction's far edge at 1.2 % (over the apron's 1 %,
    under its own 1.5 %) and the mouth at 1.2 % price NO row; the shared
    run at 1.2 % prices a junction row at the APRON cap."""
    fo = _families(cg, _portion_patch(tmp_path, far_grade=0.012, run_grade=0.009,
                                      mouth_grade=0.012, name="P1"))
    rows = fo.get("within_shape") or []
    assert not [v for v in rows if v.way_a.tags.get("role") == "junction"], [
        (v.way_a.ref, round(v.grade_pct, 2), v.cap_pct) for v in rows]
    fo2 = _families(cg, _portion_patch(tmp_path, far_grade=0.009, run_grade=0.012,
                                       mouth_grade=0.009, name="P2"))
    j = [v for v in (fo2.get("within_shape") or []) if v.way_a.tags.get("role") == "junction"]
    assert j and {v.cap_pct for v in j} == {1.0} and {v.way_a.ref for v in j} == {"pav1"}


def test_the_marker_reads_long_runs_by_the_one_ratio(cg, tmp_path):
    osm = _portion_patch(tmp_path, far_grade=0.0, run_grade=0.0, mouth_grade=0.0, name="P3")
    nodes, ways = cg._parse_osm(osm)
    f = cg._ll_to_m_factory(nodes, anchor=_TWIN_ANCHOR)
    assert cg.mark_apron_edge_portions(ways, nodes, f) == 2
    by_ref = {w.ref: w for w in ways}
    assert len(by_ref["pav1"].apron_portion_runs) == 1 and \
        len(by_ref["pav1"].apron_portion_runs[0]) == 2
    assert by_ref["pav2"].apron_portion_runs == ()
    assert by_ref["apron1"].apron_portion_runs is None
    # the same value in v2's law table (one law, two readers)
    from auto_patch.config import APRON_EDGE_PORTION_MIN_WIDTH_RATIO
    import tomllib
    emit = tomllib.loads((ROOT / "src" / "auto_patch_v2" / "law" / "emit.toml").read_text())
    assert emit["within_shape"]["apron_edge_portion_min_width_ratio"] == \
        APRON_EDGE_PORTION_MIN_WIDTH_RATIO == cg._APRON_EDGE_PORTION_RATIO


# ── RECT STRETCH CAPS (lane v2integ 2026-09-05; RULINGS 2026-09-04t-3 / 04y) ──

def _rs_ll(x: float, y: float) -> Tuple[float, float]:
    """The rect-stretch twins' metres -> lat/lon about ``_TWIN_ANCHOR``."""
    import math
    r = 6378137.0
    cos0 = math.cos(math.radians(_TWIN_ANCHOR[0]))
    return (_TWIN_ANCHOR[0] + math.degrees(y / r),
            _TWIN_ANCHOR[1] + math.degrees(x / (r * cos0)))


def _rect_stretch_patch(tmp_path: Path, *, step_grade: float, stretch_cap,
                        name: str = "RS", relaxed_rows=None) -> Path:
    """A 200 m x 40 m ``cross_connector`` (letter F, 1.5 %) whose two
    west-edge vertices (0,0)-(0,40) are level and whose east edge rises
    ``step_grade`` over the 200 m; a sidecar STRETCH of cap ``stretch_cap``
    runs along the north edge (0,40)-(200,40) — both its nodes are ring
    nodes — or none when ``stretch_cap`` is None."""
    import math
    r = 6378137.0
    cos0 = math.cos(math.radians(_TWIN_ANCHOR[0]))

    def ll(x, y):
        return (_TWIN_ANCHOR[0] + math.degrees(y / r),
                _TWIN_ANCHOR[1] + math.degrees(x / (r * cos0)))

    rise = step_grade * 200.0
    pts = [(0.0, 0.0, 0.0), (200.0, 0.0, rise), (200.0, 40.0, rise), (0.0, 40.0, 0.0)]
    out = ["<?xml version='1.0' encoding='UTF-8'?>", "<osm version='0.6' generator='rs-twin'>"]
    for k, (x, y, a) in enumerate(pts):
        lat, lon = ll(x, y)
        out.append(f"  <node id='-{k + 1}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                   f"<tag k='alt_abs' v='{a:.2f}' /></node>")
    out.append("  <way id='-10'>")
    out += [f"    <nd ref='-{k + 1}' />" for k in range(4)] + ["    <nd ref='-1' />"]
    out += ["    <tag k='role' v='cross_connector' />", "    <tag k='shapeID' v='1' />",
            "    <tag k='ref' v='pav1' />", "    <tag k='code_letter' v='F' />", "  </way>", "</osm>"]
    osm = tmp_path / f"{name}_auto.patch.osm"
    osm.write_text("\n".join(out) + "\n")
    side = {"anchor": list(_TWIN_ANCHOR), "ruleset": "icao"}
    if stretch_cap is not None:
        la0, lo0 = ll(0.0, 40.0)
        la1, lo1 = ll(200.0, 40.0)
        side["stretches"] = [[[[la0, lo0], [la1, lo1]], stretch_cap, "B", "taxi1"]]
    if relaxed_rows is not None:
        side["relaxed_rows"] = relaxed_rows
    Path(str(osm) + ".axes.json").write_text(json.dumps(side))
    return osm


def _rs_relaxed(kind: str, **rec) -> list:
    """One ``relaxed_rows`` record on the rect-stretch north edge
    (0,40)-(200,40), in the shape ``pipeline.build.relaxed_publication``
    writes."""
    la0, lo0 = _rs_ll(0.0, 40.0)
    la1, lo1 = _rs_ll(200.0, 40.0)
    base = {"kind": kind, "family": "apron", "ruling": "apron cap; relaxed by 04t(1)",
            "face": 1, "slack_m": rec.pop("slack_m", 0.0), "ll": [[la0, lo0], [la1, lo1]]}
    base.update(rec)
    return [base]


def test_a_relaxed_row_is_priced_at_its_relaxed_cap_and_reported_under_the_heading(cg, tmp_path):
    """04x-2 (spawner, RULINGS 2026-09-04x): a row the last resort relaxed
    is LAWFUL at its relaxed cap.  The north-edge pair rises 2.5 % over
    200 m against F's 1.5 %: with the sidecar naming that pair relaxed to
    ``cap_after`` 2.6 % the row is stamped ``relaxed_by_04t1`` and leaves
    the adjudicated count (reported, never dropped); at ``cap_after`` 2.0 %
    it is over even its relaxed cap and stays a violation; the pairs the
    relaxation never named (south edge, diagonals) are untouched either
    way."""
    def north(fo):
        # the (0,40)-(200,40) edge: 200 m at 2.5 %, both endpoints at y = 40
        # (the south edge is the same length and grade at y = 0)
        return [v for v in (fo.get("within_shape") or [])
                if abs(v.distance_m - 200.0) < 0.01 and abs(v.grade_pct - 2.5) < 0.01
                and min(v.pt_a[1], v.pt_b[1]) > 20.0]
    fo0 = _families(cg, _rect_stretch_patch(tmp_path, step_grade=0.025, stretch_cap=None, name="RX0"))
    rows0 = [(k, r) for k, rs in fo0.items() if isinstance(rs, list) for r in rs]
    assert len(north(fo0)) == 1 and north(fo0)[0].out_of_scope is None
    fo1 = _families(cg, _rect_stretch_patch(
        tmp_path, step_grade=0.025, stretch_cap=None, name="RX1",
        relaxed_rows=_rs_relaxed("diff", cap=0.015, cap_after=0.026, distance_m=200.0, slack_m=2.2)))
    rows1 = [(k, r) for k, rs in fo1.items() if isinstance(rs, list) for r in rs]
    assert len(rows1) == len(rows0), "counted, never dropped"
    n1 = north(fo1)
    assert len(n1) == 1 and n1[0].out_of_scope == cg.RELAXED_OUT_OF_SCOPE
    assert all(r.out_of_scope is None for _k, r in rows1 if r is not n1[0])
    adj = cg.adjudication(rows1)
    assert adj["out_of_scope_classes"][cg.RELAXED_OUT_OF_SCOPE]["n"] == 1
    assert adj["adjudicated_total"] == cg.adjudication(rows0)["adjudicated_total"] - 1
    # over even the relaxed cap: a violation still
    fo2 = _families(cg, _rect_stretch_patch(
        tmp_path, step_grade=0.025, stretch_cap=None, name="RX2",
        relaxed_rows=_rs_relaxed("diff", cap=0.015, cap_after=0.020, distance_m=200.0, slack_m=1.0)))
    assert north(fo2)[0].out_of_scope is None
    # the solve's OWN distance prices the relaxed budget (a route pair's d is
    # the route distance): 2.1 % over the record's 250 m = 5.25 m ≥ the 5 m
    # rise — lawful, though 2.1 % over the direct 200 m would not be
    fo2b = _families(cg, _rect_stretch_patch(
        tmp_path, step_grade=0.025, stretch_cap=None, name="RX2b",
        relaxed_rows=_rs_relaxed("diff", cap=0.015, cap_after=0.021, distance_m=250.0, slack_m=1.5)))
    assert north(fo2b)[0].out_of_scope == cg.RELAXED_OUT_OF_SCOPE
    # a PAD plane: both endpoints on one relaxed pad at slope 2.6 % — lawful;
    # at 2.0 % — not
    fo3 = _families(cg, _rect_stretch_patch(
        tmp_path, step_grade=0.025, stretch_cap=None, name="RX3",
        relaxed_rows=_rs_relaxed("pad", slope=0.026, extent_m=200.0)))
    assert north(fo3)[0].out_of_scope == cg.RELAXED_OUT_OF_SCOPE
    fo4 = _families(cg, _rect_stretch_patch(
        tmp_path, step_grade=0.025, stretch_cap=None, name="RX4",
        relaxed_rows=_rs_relaxed("pad", slope=0.020, extent_m=200.0)))
    assert north(fo4)[0].out_of_scope is None
    # the register carries the class and its ruling; the sidecar reader carries the key
    why = cg.OUT_OF_SCOPE_CLASSES[cg.RELAXED_OUT_OF_SCOPE]
    assert "04t(1)" in why and "04x-2" in why
    assert cg.SIDECAR_LAW_KEYS["relaxed_rows"] == "relaxed_rows"
    ctx = cg.law_context_from_sidecar(_rect_stretch_patch(
        tmp_path, step_grade=0.025, stretch_cap=None, name="RX5",
        relaxed_rows=_rs_relaxed("diff", cap=0.015, cap_after=0.026, distance_m=200.0)))
    assert len(ctx["relaxed_rows"]) == 1


def test_a_rect_pair_on_a_looser_stretch_reads_that_stretchs_cap(cg, tmp_path):
    """04y on a PLANE shape: a 2.5 % rise along the north edge is a row at
    F's 1.5 % with no stretch, and NO row when the sidecar says those two
    nodes lie on a B (3 %) stretch — the generator's ``compose_pairs``
    reading (LEMD 2026-09-05: 40 rows on B stretches through E/F
    connectors read at the face cap by this reader alone).  The pairs OFF
    the stretch (the diagonals, the south edge) keep the face cap: with the
    east edge lifted they still price at 1.5 %."""
    fo = _families(cg, _rect_stretch_patch(tmp_path, step_grade=0.025, stretch_cap=None, name="RS0"))
    rows0 = [v for v in (fo.get("within_shape") or []) if v.way_a.tags.get("role") == "cross_connector"]
    assert rows0 and {v.cap_pct for v in rows0} == {1.5}
    fo = _families(cg, _rect_stretch_patch(tmp_path, step_grade=0.025, stretch_cap=0.03, name="RS1"))
    rows1 = [v for v in (fo.get("within_shape") or []) if v.way_a.tags.get("role") == "cross_connector"]
    # the north-edge pair (200 m, 5 m rise) is now lawful at 3 %; every
    # other over-cap pair (south edge, diagonals) still reads at 1.5 %
    assert not [v for v in rows1 if abs(v.distance_m - 200.0) < 0.01 and v.cap_pct == 3.0], rows1
    assert rows1 and {v.cap_pct for v in rows1} == {1.5}
    assert len(rows1) == len(rows0) - 1, (len(rows0), len(rows1))
    # a stretch no looser than the face changes nothing
    fo = _families(cg, _rect_stretch_patch(tmp_path, step_grade=0.025, stretch_cap=0.015, name="RS2"))
    rows2 = [v for v in (fo.get("within_shape") or []) if v.way_a.tags.get("role") == "cross_connector"]
    assert len(rows2) == len(rows0)


# ── THE WITHDRAWN CHORD LAW (RULINGS 2026-09-05aa/ab/ac) ────────────

def test_the_withdrawn_taxi_chord_law_is_registered_and_stamped_from_the_sidecar(
        census_mod, cg, tmp_path):
    """A taxi-family chord row on a patch whose sidecar carries
    ``taxi_route_pairs`` is stamped ``WITHDRAWN_TAXI_CHORD_OUT_OF_SCOPE``
    — registered in ``OUT_OF_SCOPE_CLASSES`` (the heading and its why
    come from the one register), counted in its family and reported
    under the heading, never adjudicated; a mixed pair (a pad frontage),
    an apron pair, a row already out of scope, and a v1 patch (no key)
    are untouched.  The taxi family is read from the v2 law tables."""
    key = cg.WITHDRAWN_TAXI_CHORD_OUT_OF_SCOPE
    assert key in cg.OUT_OF_SCOPE_CLASSES
    assert cg.OUT_OF_SCOPE_CLASSES[key].startswith("withdrawn law (05aa)")
    assert "taxi_route_pairs" in cg.SIDECAR_EVIDENCE_KEYS
    taxi = census_mod.taxi_family_roles()
    assert "stub" in taxi and "apron" not in taxi and "building" not in taxi
    osm = tmp_path / "p.osm"
    osm.write_text("<osm version='0.6'></osm>")
    rows = [
        _FloorRow(de=1.0, grade=2.0, excess=0.5, dist=50.0, role="stub", wa="1"),
        _FloorRow(de=1.0, grade=2.0, excess=0.5, dist=50.0, role="junction", wa="2"),
        _FloorRow(de=1.0, grade=2.0, excess=0.5, dist=50.0, role="apron", wa="3"),
        _FloorRow(de=1.0, grade=2.0, excess=0.5, dist=50.0, role="stub", wa="4",
                  out_of_scope=cg.RELAXED_OUT_OF_SCOPE),
    ]
    mixed = _FloorRow(de=1.0, grade=2.0, excess=0.5, dist=50.0, role="stub", wa="5")
    mixed.way_b = _FloorRow._W("6", "building")
    rows.append(mixed)
    fam = {"within_shape": rows}
    # a v1 patch: no key, nothing stamped
    (tmp_path / "p.osm.axes.json").write_text(json.dumps({"axes": []}))
    got = census_mod.stamp_withdrawn_taxi_chords(osm, cg, fam)
    assert got == {"stamped": 0, "by_roles": {}, "key_present": False}
    assert [r.out_of_scope for r in rows] == [None, None, None, cg.RELAXED_OUT_OF_SCOPE, None]
    # a v2 patch under the route law
    (tmp_path / "p.osm.axes.json").write_text(json.dumps({"axes": [], "taxi_route_pairs": []}))
    got = census_mod.stamp_withdrawn_taxi_chords(osm, cg, fam)
    assert got["key_present"] and got["stamped"] == 2
    assert got["by_roles"] == {"stub|stub": 1, "junction|junction": 1}
    assert got["short_priced"] == 0 and got["min_m"] == census_mod.withdrawn_chord_min_m()
    assert [r.out_of_scope for r in rows] == [key, key, None, cg.RELAXED_OUT_OF_SCOPE, None]
    adj = cg.adjudication([("within_shape", r) for r in rows])
    assert adj["out_of_scope_classes"][key]["n"] == 2
    assert adj["out_of_scope_classes"][key]["why"] == cg.OUT_OF_SCOPE_CLASSES[key]
    assert adj["adjudicated_total"] == 2          # the apron pair and the frontage pair
    assert not cg.row_adjudicated("within_shape", rows[0])
    # THE FLOOR (RULINGS 2026-09-06p (3)): a 7 m stub|stub chord is PRICED,
    # a 700 m one stamped withdrawn — the floor is the law table's
    # ``emit.within_shape.withdrawn_chord_min_m``, never a literal here
    min_m = census_mod.withdrawn_chord_min_m()
    assert 7.0 < min_m < 700.0
    short = _FloorRow(de=0.5, grade=7.0, excess=5.5, dist=7.0, role="stub", wa="7")
    long_ = _FloorRow(de=10.5, grade=1.5, excess=0.5, dist=700.0, role="stub", wa="8")
    at_floor = _FloorRow(de=1.0, grade=2.0, excess=0.5, dist=min_m, role="stub", wa="9")
    fam2 = {"within_shape": [short, long_, at_floor]}
    got = census_mod.stamp_withdrawn_taxi_chords(osm, cg, fam2)
    assert got["stamped"] == 2 and got["short_priced"] == 1
    assert got["short_by_roles"] == {"stub|stub": 1}
    assert short.out_of_scope is None and long_.out_of_scope == key and at_floor.out_of_scope == key
    assert cg.row_adjudicated("within_shape", short)
    assert not cg.row_adjudicated("within_shape", long_)


def test_the_no_step_rate_reader_reads_a_declared_joint_as_a_step(cg):
    """APRON TERRACE LOCKSTEP for the §1.2 rate reader (RULINGS 06n / 07g):
    a ring station triple whose segment crosses a DECLARED joint reads the
    joint's step, not a grade-change rate — HECA 2026-09-07: 23 rows up
    to 9.2 m, every one a triple straddling a declared 8–9 m joint."""
    import math
    lat0, lon0 = 30.0, 31.0
    cos0 = math.cos(math.radians(lat0))

    def ll(x, y):
        return (lat0 + math.degrees(y / cg.R_EARTH), lon0 + math.degrees(x / (cg.R_EARTH * cos0)))
    ring = [(0, 0), (30, 0), (60, 0), (90, 0), (90, 30), (90, 60), (60, 60), (30, 60), (0, 60), (0, 30)]
    nodes = {f"n{k}": ll(x, y) for k, (x, y) in enumerate(ring)}
    nids = list(nodes)
    elevs = [100.0] * 4 + [105.0] * 6          # a 5 m step on n3–n4, and back down on n9–n0
    way = cg.Way("w1", "apron", "apron", "apron", nids + [nids[0]], elevs + [elevs[0]], {})
    ll_to_m = cg._ll_to_m_factory(nodes)
    rows, n_st, _ = cg._check_airside_no_step_rate([way], [], nodes, ll_to_m)
    assert n_st > 0 and rows, "an undeclared 5 m step must read as a rate breach"
    joint = cg._terrace_joints_to_m([{"points": [ll(80.0, 15.0), ll(100.0, 15.0)], "step_m": 5.0},
                                     {"points": [ll(-10.0, 15.0), ll(10.0, 15.0)], "step_m": 5.0}], ll_to_m)
    rows_j, _, _ = cg._check_airside_no_step_rate([way], [], nodes, ll_to_m, terrace_joints_m=joint)
    assert not rows_j, [(v.de_m, v.pt_a, v.pt_b) for v in rows_j]
    elsewhere = cg._terrace_joints_to_m([{"points": [ll(40.0, -10.0), ll(40.0, 10.0)], "step_m": 5.0}], ll_to_m)
    rows_e, _, _ = cg._check_airside_no_step_rate([way], [], nodes, ll_to_m, terrace_joints_m=elsewhere)
    assert len(rows_e) == len(rows), "a joint elsewhere forgives nothing"


def test_terrace_joint_route_never_prices_a_service_axis(cg):
    """RULINGS 2026-09-08k (lane v2shapes): a joint across a SERVICE road is
    the owner's ruled separator — ``_check_terrace_joint_crosses_route``
    reads the axis's ``is_service`` slot and prices only taxi routes."""
    joint = [([(0.0, -10.0), (0.0, 10.0)], 1.5)]
    taxi = [([(-20.0, 0.0), (20.0, 0.0)], [0.015], 0.015, 0, False)]
    service = [([(-20.0, 0.0), (20.0, 0.0)], [0.08], 0.08, 1, True)]
    assert len(cg._check_terrace_joint_crosses_route(joint, None, taxi)) == 1
    assert cg._check_terrace_joint_crosses_route(joint, None, service) == []
    assert len(cg._check_terrace_joint_crosses_route(joint, None, service + taxi)) == 1


# ── THE STRUCTURE-RAMP ORACLE LAW (RULINGS 2026-09-08u (2); spec
# docs/specs/auto-patch-v2/othh-terminal-ramps-spec.md §7b) ───────────
# The defect these pin: v2's structure ramps (a basement door's ramp, a
# kerb-wall corridor's climb) are emitted under the oracle alias
# ``role=tunnel_ramp``, and their law was ``service_road`` — 8 %, the
# largest cap v1 knew.  A lawful ramp steepened to the ramp law's 10 %
# ceiling at an airside stop then read as a within-shape violation: 181
# groundside rows at OTHH, every one at 8.2 %, against v2 verify's 0.
# The law name ``structure_ramp`` (v1 ``config.STRUCTURE_RAMP_MAX_GRADE``
# = the v2 ``cutout.wall_corridor.max_ramp_grade``) is what the emitter
# now writes, with ``o4_grade_law_cap`` at the same ceiling.

def _ramp_patch(tmp_path: Path, *, grade: float, run_m: float = 25.0,
                law: str = "structure_ramp", cap: str = "0.1",
                name: str = "RAMP") -> Path:
    """One ``run_m``-long ``door_ramp`` face climbing at ``grade``,
    tagged exactly as ``emit/osm_adapter`` writes it."""
    import math
    r = 6378137.0
    cos0 = math.cos(math.radians(_TWIN_ANCHOR[0]))

    def ll(x, y):
        return (_TWIN_ANCHOR[0] + math.degrees(y / r),
                _TWIN_ANCHOR[1] + math.degrees(x / (r * cos0)))

    # A WEDGE, so exactly ONE vertex pair runs at ``grade``: the climb
    # A→B.  The third vertex stands 12 m across at the foot, far enough
    # that B→C reads 9.5 % even when the climb is 10.5 % — a rectangle
    # would price the same one law four times (two edges, two diagonals)
    # and say nothing more.
    ring = ((0.0, 0.0, 0.0), (run_m, 0.0, grade * run_m), (0.0, 12.0, 0.0))
    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm version='0.6' generator='ramp-twin'>"]
    ids = []
    for i, (x, y, alt) in enumerate(ring):
        lat, lon = ll(x, y)
        ids.append(str(-(i + 1)))
        out.append(f"  <node id='{ids[-1]}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                   f"<tag k='alt_abs' v='{alt:.3f}' /></node>")
    out.append("  <way id='-100'>")
    out += [f"    <nd ref='{n}' />" for n in ids + [ids[0]]]
    for k, v in (("aeroway", "taxiway"), ("ref", "door1"),
                 ("role", "tunnel_ramp"), ("shapeID", "1"),
                 ("class", "door_ramp"), ("o4_grade_law", law),
                 ("o4_grade_law_cap", cap)):
        out.append(f"    <tag k='{k}' v='{v}' />")
    out.append("  </way>")
    out.append("</osm>")
    osm = tmp_path / f"{name}_auto.patch.osm"
    osm.write_text("\n".join(out) + "\n")
    Path(str(osm) + ".axes.json").write_text(json.dumps({
        "anchor": list(_TWIN_ANCHOR), "ruleset": "icao"}))
    return osm


def test_a_structure_ramp_is_priced_at_the_ramp_laws_ceiling(cg, tmp_path):
    """RULINGS 2026-09-08u (2): the oracle reads a ``door_ramp`` /
    ``wall_corridor_ramp`` pair at ``max_ramp_grade`` 10 % — OTHH's 8.2 %
    climbs are lawful and price nothing; a ramp past the ceiling still
    reports.  The number is the ENGINE's: v1's ``STRUCTURE_RAMP_MAX_GRADE``
    is asserted equal to v2's ``cutout.wall_corridor.max_ramp_grade`` by
    ``tests/auto_patch_v2/test_law_tables.py``."""
    from auto_patch.config import ROLE_GRADE_LIMITS, STRUCTURE_RAMP_MAX_GRADE

    assert ROLE_GRADE_LIMITS["structure_ramp"] == STRUCTURE_RAMP_MAX_GRADE == 0.10
    lawful = _families(cg, _ramp_patch(tmp_path, grade=0.082, name="OK"))
    assert lawful["within_shape"] == [], (
        f"an 8.2 % structure ramp priced {len(lawful['within_shape'])} "
        f"within-shape row(s) — the OTHH class, 181 of them")
    steep = _families(cg, _ramp_patch(tmp_path, grade=0.105, name="STEEP"))
    assert len(steep["within_shape"]) == 1, (
        f"a 10.5 % ramp priced {len(steep['within_shape'])} row(s): the "
        f"ceiling must still BIND")
    assert steep["within_shape"][0].cap_pct == pytest.approx(10.0), (
        "the row must be priced at the RAMP law (10 %), not at the road 8 % "
        "the tunnel ramp and the service road now share (RULINGS 2026-09-12m)")
    # and the old law is what minted them: the same 8.2 % ramp under
    # service_road's 8 % reports
    old = _families(cg, _ramp_patch(tmp_path, grade=0.082, law="service_road",
                                    cap="0.08", name="OLD"))
    assert len(old["within_shape"]) == 1


# ══════════════════════════════════════════════════════════════════════
# THE PAD'S RELIEF TARGET — one pad, one level plane, two readers
# (owner RULINGS 2026-09-11j; ratified 11l (2); spec §11a (2)/(4))
# ══════════════════════════════════════════════════════════════════════
# A pad under an OBJ8 body whose ground-contact feet are authored at
# different ``y`` is NOT flat and must not be: X-Plane drapes the whole
# body at one anchor, so the terrain under every foot has to stand at
# ``level + (y_foot − y_zero)``.  The solve prices it flat ON ITS LEVEL
# PLANE (``constraints/pad_relief``, ``Diff.rel``) and publishes the
# per-vertex offsets as the sidecar key ``pad_relief``.
#
# THE TWIN: the in-build reader (``verify/pads.pad_flat``) and the
# HARNESS reader (``check_grade``'s ``within_shape`` / ``plane_gradient``
# families) must make the SAME reading of the SAME emitted pad — zero
# rows with the key, the designed steps priced without it.  Round 2 landed
# the key; round 3 taught the harness to read it, and this is what stops
# the two instruments drifting again (the census-wrapper defect class).

_PAD_RELIEF = (0.0, 1.2, 2.4, 1.2)      # metres above the pad's level


def _relief_pad_geometry(side: float = 20.0):
    """A square ``building`` pad at the twin anchor, its four vertices
    emitted at ``level + offset``: ``[(lat, lon, z, offset), …]``."""
    import math
    r = 6378137.0
    cos0 = math.cos(math.radians(_TWIN_ANCHOR[0]))
    level = 100.0
    corners = ((0.0, 0.0), (side, 0.0), (side, side), (0.0, side))
    out = []
    for (x, y), off in zip(corners, _PAD_RELIEF):
        lat = _TWIN_ANCHOR[0] + math.degrees(y / r)
        lon = _TWIN_ANCHOR[1] + math.degrees(x / (r * cos0))
        out.append((lat, lon, level + off, off))
    return out


def _relief_pad_patch(tmp_path: Path, *, publish: bool, name: str) -> Path:
    """The pad as an emitted patch, with or without the ``pad_relief``
    sidecar key (``publish=False`` is an older build's patch)."""
    pts = _relief_pad_geometry()
    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm version='0.6' generator='pad-relief-twin'>"]
    nids = []
    for i, (lat, lon, z, _off) in enumerate(pts):
        n = str(-1 - i)
        nids.append(n)
        out.append(f"  <node id='{n}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                   f"<tag k='alt_abs' v='{z:.2f}' /></node>")
    out.append("  <way id='-99'>")
    out += [f"    <nd ref='{n}' />" for n in nids + [nids[0]]]
    out += ["    <tag k='role' v='building' />",
            "    <tag k='shapeID' v='P1' />",
            "  </way>", "</osm>"]
    osm = tmp_path / f"{name}_auto.patch.osm"
    osm.write_text("\n".join(out) + "\n")
    side = {"anchor": list(_TWIN_ANCHOR), "ruleset": "icao"}
    if publish:
        side["pad_relief"] = [[lat, lon, off] for lat, lon, _z, off in pts]
    Path(str(osm) + ".axes.json").write_text(json.dumps(side))
    return osm


def _verify_relief_pad(publish: bool):
    """The SAME pad read by the in-build instrument: ``pad_flat`` rows."""
    from auto_patch_v2.law import Law
    from auto_patch_v2.verify.frame import Patch, Shape
    from auto_patch_v2.verify.pads import pad_flat
    pts = _relief_pad_geometry()
    law = Law.for_airport("ZZZZ")
    lat0, lon0 = _TWIN_ANCHOR
    p = Patch(law, lat0, lon0, {}, {}, {}, (), (),
              {"pad_relief": [[lat, lon, off]
                              for lat, lon, _z, off in pts]} if publish else {})
    xy = {i: p.to_m(lat, lon) for i, (lat, lon, _z, _o) in enumerate(pts)}
    z = {i: zz for i, (_la, _lo, zz, _o) in enumerate(pts)}
    ll = {i: (lat, lon) for i, (lat, lon, _z, _o) in enumerate(pts)}
    sh = Shape(0, "building", "building:1", tuple(xy),
               tuple(xy[i] for i in xy), tuple(z[i] for i in z))
    p = _dc_replace_patch(p, xy=xy, z=z, ll=ll, shapes=(sh,))
    return pad_flat(p)


def _dc_replace_patch(p, **kw):
    import dataclasses
    return dataclasses.replace(p, **kw)


def _pad_families(cg, osm) -> dict:
    fo: dict = {}
    cg.run_checks_law_true(osm, family_out=fo, quiet=True)
    return fo


def test_a_relief_pad_reads_zero_through_both_instruments(cg, tmp_path):
    """11l (2): with ``pad_relief`` published, the pad's designed relief
    is read on its LEVEL PLANE — the harness census prices no
    ``within_shape`` / ``plane_gradient`` row and the in-build
    ``verify/pads.pad_flat`` returns no row.  ONE pad, ONE level, TWO
    readers that agree by construction."""
    fo = _pad_families(cg, _relief_pad_patch(tmp_path, publish=True,
                                             name="PADREL"))
    assert len(fo.get("within_shape", [])) == 0, fo.get("within_shape")
    assert len(fo.get("plane_gradient", [])) == 0, fo.get("plane_gradient")
    assert _verify_relief_pad(publish=True) == []


def test_without_the_key_both_instruments_price_the_same_relief(cg, tmp_path):
    """The key is what does it, in BOTH readers: strip ``pad_relief`` and
    the same emitted pad prices rows on both sides — so an older patch
    reads exactly as it did before 11j, and neither instrument is quietly
    ignoring the relief on its own."""
    fo = _pad_families(cg, _relief_pad_patch(tmp_path, publish=False,
                                             name="PADRAW"))
    assert len(fo.get("within_shape", [])) > 0
    assert _verify_relief_pad(publish=False) != []


def test_the_pad_relief_key_is_registered_as_law_input(cg):
    """The sidecar contract is ONE table (``SIDECAR_LAW_KEYS``): a reader
    that forgot to register the key would silently degrade every census
    to the pre-11j frame, which is the census-wrapper defect class."""
    assert cg.SIDECAR_LAW_KEYS["pad_relief"] == "pad_relief_ll"
    import inspect
    assert "pad_relief_ll" in inspect.signature(cg.run_checks).parameters


def test_the_relief_offsets_join_by_coordinate_in_both_readers(cg):
    """Both readers join the published rows to vertices BY COORDINATE —
    the sidecar carries lat/lon, never the build's vertex ids."""
    pts = _relief_pad_geometry()
    nodes = {str(-1 - i): (lat, lon) for i, (lat, lon, _z, _o) in enumerate(pts)}
    got = cg._pad_relief_by_nid(nodes, [[lat, lon, off]
                                        for lat, lon, _z, off in pts])
    assert [got[str(-1 - i)] for i in range(len(pts))] == list(_PAD_RELIEF)


# ══════════════════════════════════════════════════════════════════════
# §7 THE COCKPIT BLOCK IS ONE CODE PATH AND ONE PARTITION
# (owner RULINGS 2026-09-12x/12y; design-surface-spec §31 (6),
#  object-placement-spec §17 — lane ``v2cockpit``)
# ══════════════════════════════════════════════════════════════════════
# The block is a CLASSIFICATION of rows the census already has.  Two
# things can silently break it and both are pinned here: a law family
# added without a cockpit class (its rows would fall into REPORT and the
# owner would never see them), and a bucket rule that drops or
# double-counts a row (the two-instruments trap inside one report).

class _CkWay:
    def __init__(self, role):
        self.tags = {"role": role}


class _CkStep:
    """A step row of the shape ``row_magnitude`` / ``row_roles`` read."""

    def __init__(self, role_a, role_b, step_m, *, lat=None, lon=None,
                 distance_m=0.2):
        self.way_v = _CkWay(role_a)
        self.way_e = _CkWay(role_b)
        self.step_m = step_m
        self.distance_m = distance_m
        self.lat = lat
        self.lon = lon


def _ck_geometry(cg, *, ring_deg=0.01, runway_ll=((-0.009, 0.0),
                                                  (0.009, 0.0))):
    """A synthetic §31 (2) frame: ONE boundary ring around (0,0) and ONE
    runway axis (2 km, running north-south through the origin by default),
    in the same metre projection the census uses.

    The APPROACH CORRIDOR is built by the SAME class the engine's mouth
    gate reads (``auto_patch_v2.law.approach_corridor``, owner RULINGS
    2026-09-12al) from the same two law numbers — never a disc, and never
    a second corridor written here."""
    import math

    def ll_to_m(lat, lon):
        return (lon * 111320.0 * math.cos(math.radians(lat)),
                lat * 110540.0)
    ring = [ll_to_m(a, b) for a, b in
            ((-ring_deg, -ring_deg), (-ring_deg, ring_deg),
             (ring_deg, ring_deg), (ring_deg, -ring_deg))]
    law = cg.cockpit_law()
    axes = [(ll_to_m(*runway_ll[0]), ll_to_m(*runway_ll[1]), "RW")]
    return {"boundary_rings": [ring],
            "runway_axes": axes,
            "corridor": cg._ApproachCorridor(axes, law["approach_m"],
                                             law["approach_half_width_m"]),
            # §29 (7) THE RUNWAY LATERAL BAND (RULINGS 2026-09-13bm (ii)):
            # the fixture frame carries every term the real
            # ``cockpit_geometry`` builds, or the twin measures a census
            # the census never runs.
            "runway_band": cg._RunwayViewBand(
                axes, law["runway_view_half_width_m"]),
            "ll_to_m": ll_to_m}


def test_the_cockpit_law_keys_come_from_the_tables(cg):
    """§31 (1)/(2): the three numbers are LAW, read through
    ``auto_patch_v2.law.tables.cockpit`` — never a literal in an
    instrument."""
    law = cg.cockpit_law(refresh=True)
    assert law["motion_step_m"] == 0.05
    assert law["visual_m"] == 0.5
    assert law["approach_km"] == 5.0
    assert law["approach_m"] == 5000.0
    # the ROLLED-ON set is derived from precedence.toml, so it carries the
    # runway family, the taxi family and the apron — and NOT a pad, a road
    # or a car park (§31 (3): landside is visual only)
    assert {"runway", "runway_crossing", "apron", "primary_parallel",
            "stub"} <= law["rolled_on"]
    assert not (law["rolled_on"]
                & {"building", "parking_lot", "service_road",
                   "groundside_pavement", "graded_strip"})


def test_every_law_family_declares_a_cockpit_class(cg):
    """A family registered in ``LAW_FAMILIES`` with no ``cockpit`` key in
    ``families.toml`` would classify silently as REPORT — the census-
    wrapper defect wearing a reading rule's hat.  ``cockpit_law`` refuses
    instead; this asserts the register is total TODAY."""
    from auto_patch_v2.law.cockpit_schema import COCKPIT_CLASSES
    law = cg.cockpit_law(refresh=True)
    for key, _title, _bucket in cg.LAW_FAMILIES:
        assert key in law["family_class"], key
        # THE REGISTER IS THE LAW'S OWN (RULINGS 2026-09-13): a literal
        # tuple here was a SECOND copy of ``COCKPIT_CLASSES``, and adding
        # the ``sentinel`` class moved one without the other.
        assert law["family_class"][key] in COCKPIT_CLASSES, key


def test_a_step_over_the_motion_threshold_on_apron_is_critical_motion(cg):
    law = cg.cockpit_law(refresh=True)
    row = _CkStep("apron", "apron", 0.06)
    b, why = cg.cockpit_classify("vertex_to_edge_step", row, law=law)
    assert (b, why) == (cg.COCKPIT_MOTION, "step_on_pavement")
    # ...and under it, the same row is REPORT: centimetres are not a goal
    b2, _ = cg.cockpit_classify("vertex_to_edge_step",
                                _CkStep("apron", "apron", 0.04), law=law)
    assert b2 == cg.COCKPIT_REPORT


def test_a_spanned_step_family_row_is_a_slope_and_is_report(cg):
    """THE SPAN RULE (owner RULINGS 2026-09-12ad, round 2).  The SAME
    height difference is a discontinuity between welded neighbours and a
    RAMP over 81 m of taxiway — grade, judged by its cap.  Round 1 classed
    both as critical motion and LEMD's block read 452; every one of them
    was spanned.

    The tolerance is the law's own weld spacing
    (``emit.instrument.step_contact_tol_m``), never a number typed here."""
    law = cg.cockpit_law(refresh=True)
    weld = law["weld_tol_m"]
    assert weld == 1.0

    # 2.69 m on apron: WELDED it is the worst thing on the field...
    near = _CkStep("apron", "junction", 2.69, distance_m=weld * 0.5)
    assert cg.cockpit_classify("airside_no_step", near, law=law) == (
        cg.COCKPIT_MOTION, "step_on_pavement")
    # ...SPANNED over 81 m it is a 3.3 % ramp, and REPORT — named as what
    # the rule moved, never folded into an anonymous total
    far = _CkStep("apron", "junction", 2.69, distance_m=81.1)
    assert cg.cockpit_classify("airside_no_step", far, law=law) == (
        cg.COCKPIT_REPORT, "spanned_over_motion")
    # the boundary itself: AT the weld spacing is still welded
    at = _CkStep("apron", "junction", 2.69, distance_m=weld)
    assert cg.cockpit_classify("airside_no_step", at, law=law)[0] == \
        cg.COCKPIT_MOTION

    # the VISUAL side reads the same way: 1 m of tear spread over 20 m of
    # strip is a 5 % slope and reported; the same 1 m at a joint is
    # critical.  (Spread it over 3 m instead and it is a CLIFF —
    # ``test_a_spanned_row_steeper_than_the_bank_is_a_cliff``, §31 (7).)
    geo = _ck_geometry(cg)
    here = {"lat": 0.001, "lon": 0.001}
    span = _CkStep("graded_strip", "graded_strip", 1.0, distance_m=20.0,
                   **here)
    assert cg.cockpit_classify("strip_seam_tear", span, law=law,
                               geometry=geo) == (cg.COCKPIT_REPORT,
                                                 "spanned_over_visual")
    weld_row = _CkStep("graded_strip", "graded_strip", 8.27,
                       distance_m=weld * 0.2, **here)
    assert cg.cockpit_classify("strip_seam_tear", weld_row, law=law,
                               geometry=geo) == (cg.COCKPIT_VISUAL, "taxi")


def test_a_spanned_row_steeper_than_the_bank_is_a_cliff(cg):
    """§31 (7) THE CLIFF ESCAPE (owner RULINGS 2026-09-12af).  12ad sent
    every spanned row to REPORT and LEMD's 8.27 m tear over 3.01 m went
    with it — a 275 % slope, which is a cliff by any reading.  A spanned
    row steeper than the design surface's OWN BANK is a cut or a rise, not
    ground, and is judged as though it were welded."""
    law = cg.cockpit_law(refresh=True)
    geo = _ck_geometry(cg)
    here = {"lat": 0.001, "lon": 0.001}

    # LEMD's own row: 8.27 m over 3.01 m = 275 %, back as CRITICAL VISUAL
    tear = _CkStep("graded_strip", "graded_strip", 8.27, distance_m=3.01,
                   **here)
    assert cg.cockpit_classify("strip_seam_tear", tear, law=law,
                               geometry=geo) == (cg.COCKPIT_VISUAL, "cliff")
    # LEMD's other row: 2.69 m over 81.1 m = 3.3 %, still a slope
    ramp = _CkStep("apron", "junction", 2.69, distance_m=81.1)
    assert cg.cockpit_classify("airside_no_step", ramp, law=law) == (
        cg.COCKPIT_REPORT, "spanned_over_motion")
    # ON ROLLED-ON PAVEMENT a cliff is MOTION: no aircraft rolls a 1:3
    assert cg.cockpit_classify(
        "airside_no_step", _CkStep("apron", "junction", 2.0, distance_m=3.0),
        law=law, geometry=geo) == (cg.COCKPIT_MOTION, "cliff")
    # EXACTLY the bank is the bank, and the bank is ground: 3.3 m over
    # 10 m is 1:3 and REPORT.  The comparison is strict, on purpose.
    flush = _CkStep("graded_strip", "graded_strip", 3.3, distance_m=10.0,
                    **here)
    assert cg.cockpit_classify("strip_seam_tear", flush, law=law,
                               geometry=geo) == (cg.COCKPIT_REPORT,
                                                 "spanned_over_visual")
    # the escape restores the BUCKET, never the threshold: 0.4 m over
    # 1.1 m is a 36 % cliff and still under visual_m, still invisible
    small = _CkStep("graded_strip", "graded_strip", 0.4, distance_m=1.1,
                    **here)
    assert cg.cockpit_classify("strip_seam_tear", small, law=law,
                               geometry=geo)[0] == cg.COCKPIT_REPORT
    # ...and a cliff out of view is still out of view
    far = _CkStep("graded_strip", "graded_strip", 8.27, distance_m=3.01,
                  lat=0.18, lon=0.0)
    assert cg.cockpit_classify("strip_seam_tear", far, law=law,
                               geometry=geo) == (cg.COCKPIT_REPORT,
                                                 "beyond_view")


def test_the_cliff_grade_is_the_design_surfaces_own_bank(cg):
    """§31 (7): ``[cockpit] cliff_grade`` holds a DOTTED LAW PATH, not a
    number — the bank slope already IS the line between ground and a wall,
    and a second copy of 0.33 could drift from the first.  Change the bank
    and the cliff line follows."""
    from auto_patch_v2.law import tables as T
    law_t = T.load_default()
    assert law_t.tables.emit.cockpit.cliff_grade == "emit.design.bank_slope"
    assert T.cliff_grade(law_t) == law_t.tables.emit.design.bank_slope
    assert cg.cockpit_law(refresh=True)["cliff_grade"] == \
        law_t.tables.emit.design.bank_slope
    # and the loader REFUSES a path that names no grade
    import dataclasses
    from auto_patch_v2.law.cockpit_schema import check_cockpit
    from auto_patch_v2.law.model import LawError
    bad = dataclasses.replace(law_t.tables.emit.cockpit,
                              cliff_grade="emit.design.no_such_key")
    with pytest.raises(LawError):
        check_cockpit(bad, law_t.tables.families, LawError, law_t.tables)


def test_a_forbidden_grade_break_carries_no_span_test(cg):
    """§31 (1)'s second motion clause is a RATE law: the row exists only
    because the runway/taxi curve law was exceeded, so its own bound IS
    the threshold and 12ad's span rule does not reach it (a curve is a
    long thing by definition — a span test would delete the family)."""
    law = cg.cockpit_law(refresh=True)
    for d in (0.1, 500.0):
        assert cg.cockpit_classify(
            "raoa", _CkStep("runway", "runway", 0.02, distance_m=d),
            law=law) == (cg.COCKPIT_MOTION, "grade_break")
    # ...and off rolled-on pavement a rate row is REPORT — it is the
    # graded strip's own arc law and nothing rolls there
    assert cg.cockpit_classify(
        "strip_arc", _CkStep("graded_strip", "graded_strip", 3.0,
                             distance_m=100.0), law=law)[0] == \
        cg.COCKPIT_REPORT
    # unless the same row is ALSO a CLIFF, which every family can be
    # since 12aj (c): 3 m over 5 m of strip is a wall, and the pilot sees
    # walls wherever they stand
    assert cg.cockpit_classify(
        "strip_arc", _CkStep("graded_strip", "graded_strip", 3.0,
                             distance_m=5.0), law=law) == (
        cg.COCKPIT_VISUAL, "cliff")


def test_the_same_step_on_a_car_park_is_report(cg):
    """§31 (3): LANDSIDE IS VISUAL ONLY.  The aircraft does not roll on a
    car park, so its 0.06 m step is invisible-and-report, not critical."""
    law = cg.cockpit_law(refresh=True)
    b, why = cg.cockpit_classify(
        "vertex_to_edge_step", _CkStep("parking_lot", "parking_lot", 0.06),
        law=law)
    assert (b, why) == (cg.COCKPIT_REPORT, "under_visual")
    # a MIXED pair is not rolled-on either: both sides must be
    b2, _ = cg.cockpit_classify(
        "vertex_to_edge_step", _CkStep("apron", "parking_lot", 0.06),
        law=law)
    assert b2 == cg.COCKPIT_REPORT


def test_a_visual_float_inside_the_boundary_is_critical_and_under_it_is_report(cg):
    law = cg.cockpit_law(refresh=True)
    geo = _ck_geometry(cg)
    at_home = {"lat": 0.001, "lon": 0.001}          # inside the ring
    b, why = cg.cockpit_classify(
        "mid_edge_step",
        _CkStep("building", "groundside_pavement", 0.6, **at_home),
        law=law, geometry=geo)
    assert (b, why) == (cg.COCKPIT_VISUAL, "taxi")
    b2, why2 = cg.cockpit_classify(
        "mid_edge_step",
        _CkStep("building", "groundside_pavement", 0.4, **at_home),
        law=law, geometry=geo)
    assert (b2, why2) == (cg.COCKPIT_REPORT, "under_visual")


def test_a_terrace_far_from_every_runway_is_report(cg):
    """§31 (2): the APPROACH range.  0.6 m of terrace 20 km from the
    airport is over the visual threshold and still invisible — nobody is
    looking at it."""
    law = cg.cockpit_law(refresh=True)
    geo = _ck_geometry(cg)
    far = {"lat": 0.18, "lon": 0.0}                 # ~20 km north
    b, why = cg.cockpit_classify(
        "terrace_actual_step",
        _CkStep("building", "groundside_pavement", 0.6, **far),
        law=law, geometry=geo)
    assert (b, why) == (cg.COCKPIT_REPORT, "beyond_view")
    # ...and the SAME row 2 km out, inside the approach corridor, is seen
    near = {"lat": 0.018, "lon": 0.0}
    b2, why2 = cg.cockpit_classify(
        "terrace_actual_step",
        _CkStep("building", "groundside_pavement", 0.6, **near),
        law=law, geometry=geo)
    assert (b2, why2) == (cg.COCKPIT_VISUAL, "approach")


def test_a_row_with_no_coordinate_is_in_view(cg):
    """A defect whose place the census cannot name is never dismissed for
    being far away, and the block counts how many there were."""
    law = cg.cockpit_law(refresh=True)
    geo = _ck_geometry(cg)
    b, why = cg.cockpit_classify(
        "mid_edge_step", _CkStep("building", "groundside_pavement", 0.9),
        law=law, geometry=geo)
    assert (b, why) == (cg.COCKPIT_VISUAL, "unlocated")


def test_the_cockpit_buckets_partition_the_census_rows(cg):
    """THE PARTITION.  Every row lands in exactly one bucket, and the
    three buckets add to the population handed in — the claim the whole
    block rests on, asserted in production too (``cockpit_block``
    raises)."""
    rows_by_family = {
        "vertex_to_edge_step": [_CkStep("apron", "apron", 0.06),
                                _CkStep("apron", "apron", 0.01),
                                # SPANNED: a 3 m rise over 90 m of apron is
                                # a slope (12ad) and lands in REPORT
                                _CkStep("apron", "apron", 3.0,
                                        distance_m=90.0),
                                _CkStep("parking_lot", "parking_lot", 0.9,
                                        lat=0.001, lon=0.001)],
        # NOT building|building: that pair holds the registered
        # ``building_to_building`` step exemption and is LAWFUL geometry,
        # which the block filters before classifying (asserted below).
        "mid_edge_step": [_CkStep("building", "groundside_pavement", 0.4,
                                  lat=0.001, lon=0.001),
                          _CkStep("building", "building", 9.9,
                                  lat=0.001, lon=0.001)],
        # a 4 m rise over 200 m of runway is a 2 % SLOPE: grade, REPORT.
        # (Over 2 m it would be a cliff and CRITICAL MOTION — 12aj (c),
        # twinned in test_the_cliff_escape_reaches_every_family.)
        "within_shape": [_CkStep("runway", "runway", 4.0, distance_m=200.0)],
        "raoa": [_CkStep("runway", "runway", 0.02, distance_m=60.0)],
        "wall_in_runway_strip": [_CkStep("retaining_wall", "runway", 9.0,
                                         distance_m=100.0)],
    }
    c = cg.cockpit_block(rows_by_family, geometry=_ck_geometry(cg))
    # the LAW's own step exemption is applied first and counted, never
    # silently dropped: a building-to-building step is lawful geometry
    n = sum(len(v) for v in rows_by_family.values()) - 1
    assert c["step_exempt_rows"] == 1
    assert c["rows"] == n
    assert (c[cg.COCKPIT_MOTION]["n"] + c[cg.COCKPIT_VISUAL]["n"]
            + c[cg.COCKPIT_REPORT]["n"]) == n
    assert c[cg.COCKPIT_MOTION]["n"] == 2      # the apron step, the raoa row
    assert c[cg.COCKPIT_VISUAL]["n"] == 1      # the car-park 0.9 m, in view
    # a `grade` row (within_shape) and a `keepout` row are REPORT however
    # large: §31 (4), and neither is a cut, a rise or a step
    assert set(c[cg.COCKPIT_REPORT]["by_family"]) == {
        "vertex_to_edge_step", "mid_edge_step", "within_shape",
        "wall_in_runway_strip"}
    # the span rule's own count is REPORTED, never anonymous
    assert c[cg.COCKPIT_REPORT]["reasons"]["spanned_over_motion"] == 1
    # and the lines render without a coordinate, a family or a count
    # going missing
    txt = "\n".join(cg.cockpit_block_lines(c))
    assert "CRITICAL motion: 2" in txt and "CRITICAL visual: 1" in txt
    # a critical bucket NAMES what its rows are, from the reason tally —
    # never a subtraction (round 3 printed "5 a forbidden grade BREAK" for
    # 5 cliffs because the line took `n - welded` instead of the tally)
    assert "1 a forbidden grade BREAK" in txt
    assert "1 a WELDED step between two rolled-on faces" in txt
    for k in cg.COCKPIT_REASON_TEXT:
        assert k in {"step_on_pavement", "grade_break", "cliff", "taxi",
                     "approach", "unlocated"}
    assert "REPORT: 5 row(s)" in txt
    assert "1 would be over the motion threshold" in txt


def test_the_cockpit_block_refuses_a_broken_partition(cg, monkeypatch):
    """A classifier that returned a bucket outside the register would drop
    rows from the report while the census beside it still counted them."""
    monkeypatch.setattr(cg, "cockpit_classify",
                        lambda *a, **k: ("nowhere", "?"))
    with pytest.raises(Exception):
        cg.cockpit_block({"mid_edge_step": [_CkStep("apron", "apron", 1.0)]})


def test_the_census_and_the_cli_print_one_cockpit_block(cg, census_mod):
    """ONE CODE PATH: the harness census renders the block through
    ``check_grade.cockpit_block_lines``, and ``check_grade``'s own CLI
    calls the same two functions — no second formatting of the same
    numbers (the census-wrapper defect class)."""
    src = (ROOT / "tools" / "harness" / "census.py").read_text()
    assert "cockpit_block_lines(" in src and "cg.cockpit_block(" in src
    assert "COCKPIT (" not in src, (
        "the census formats the block itself instead of calling "
        "check_grade.cockpit_block_lines")
    cli = (ROOT / "tools" / "check_grade.py").read_text()
    assert cli.count("def cockpit_block_lines") == 1
    assert "cockpit_block_lines(cockpit_block(families))" in cli, (
        "check_grade's CLI must print the block from the same run's "
        "family_out, first")
    assert callable(census_mod.print_report)


def test_the_object_stage_reads_the_same_three_law_keys():
    """§17: the placement censuses price at the SAME ``[cockpit]`` keys the
    terrain census does.  Two stages, one frame — a second copy of 0.05 /
    0.5 / 5.0 is the defect."""
    from auto_patch_v2.airport import placement_carrier as PC
    c = PC.cockpit_block(v15={"carried_float_gt": 1, "float_tol_m": 0.5,
                              "carried_worst": [(0.9, "roof.obj", "wall.obj")],
                              "footed_float_gt": 0, "carried_over_refused": 0,
                              "refused_ground_off": [(0.2, "x.obj")]})
    assert c["motion_step_m"] == 0.05 and c["visual_m"] == 0.5
    assert c["approach_km"] == 5.0
    assert c["critical_visual_n"] == 1
    txt = "\n".join(PC.cockpit_block_lines(c))
    assert "COCKPIT CRITICAL visual: 1" in txt
    # the refusal set under the threshold is REPORT, never dropped
    assert "refused carrier" in txt


# ══════════════════════════════════════════════════════════════════════
# §7b THE THREE READER DEFECTS (owner RULINGS 2026-09-12aj, round 4)
# ══════════════════════════════════════════════════════════════════════
# All three were found by the cockpit block pointing at a place, a scout
# going there, and the place being wrong.  Each is pinned at the reader,
# not at the block: an instrument that cannot say WHERE, or that halves
# the span its own number is taken over, or that reads the ring a pair
# was walked on instead of the faces that meet there, will mislead the
# next attribution the same way.

def test_a_rate_row_carries_its_own_midpoint_not_its_rings_centroid(cg):
    """(a), the strong form — on the reader's own output.

    A ring whose vertices span hundreds of metres has ONE centroid; a
    rate row found on it has a place of its own.  Built here as a
    synthetic ring so the two are far apart on purpose (that separation
    IS the defect: 560 m at LEMD)."""
    inv_calls = []

    class _LLM:
        def __call__(self, lat, lon):
            return (lon * 1000.0, lat * 1000.0)

        def inverse(self, x, y):
            inv_calls.append((x, y))
            return (y / 1000.0, x / 1000.0)

    ll = _LLM()
    lat, lon = cg._rate_row_site(ll, (100.0, 200.0), (300.0, 600.0))
    assert (lat, lon) == pytest.approx((0.4, 0.2))
    assert len(inv_calls) == 2
    # a projection with no inverse degrades to "no coordinate", never to
    # a wrong one
    assert cg._rate_row_site(lambda a, b: (0.0, 0.0), (0.0, 0.0),
                             (1.0, 1.0)) == (None, None)
    # and the census's own projection round-trips
    f = cg._ll_to_m_factory({"1": (40.49, -3.59)}, anchor=(40.49, -3.59))
    x, y = f(40.4946510, -3.5903587)
    back = f.inverse(x, y)
    assert back == pytest.approx((40.4946510, -3.5903587), abs=1e-9)


def test_a_rate_rows_span_is_the_separation_its_de_is_taken_over(cg):
    """(b) ``de_m`` spans a -> c = ``dp + dn``; ``distance_m`` published
    the HALF span ``0.5*(dp + dn)``, which is the rate law's averaging
    term and not the row's geometry.  Every implied grade therefore read
    2x — LEMD's five apron rate rows printed 0.37-0.46 and are really
    0.20-0.23, so the cliff rule promoted five slopes it should not have.

    Both the block's WELD test and its SLOPE/CLIFF rule read
    ``distance_m``; this pins the three readers that build it."""
    src = (ROOT / "tools" / "check_grade.py").read_text()
    assert "distance_m=0.5 * (dp + dn)" not in src
    assert "span = 0.5 * (dp + dn)" not in src
    # the ALLOWANCE keeps the half span — it is the rate law's own term
    assert src.count("* 0.5 * (dp + dn)") == 3, (
        "the three rate readers price their allowance at the half span "
        "(the law's averaging term); only distance_m changed")
    assert src.count("distance_m=dp + dn") == 3
    # ...and on a real patch: no rate row's published span is under the
    # straight-line separation of its own endpoints, and every one of
    # them carries a coordinate of its own rather than its ring's
    # centroid (the (a) defect, asserted on the same population)
    import math
    fam: dict = {}
    cg.run_checks(FIXTURE_PATCH, top_n=0, quiet=True, family_out=fam,
                  **cg.LAW_TRUE_KNOBS)
    seen = 0
    for key in ("airside_no_step", "strip_arc", "raoa"):
        for r in fam.get(key, ()) or ():
            if r.way_a is not r.way_b or r.pt_a is None:
                continue
            seen += 1
            sep = math.hypot(r.pt_a[0] - r.pt_b[0], r.pt_a[1] - r.pt_b[1])
            # ``airside_no_step``'s station coordinate is ARC LENGTH along
            # the polyline, so its span is at least the chord.  The other
            # two project onto an axis (the runway's, the RAOA's), so
            # theirs can fall a little under it — what must never happen
            # again is the HALF span, and 0.55x is the bound that says so
            # whatever the obliquity.
            floor = sep - 1e-6 if key == "airside_no_step" else 0.55 * sep
            assert float(r.distance_m) >= floor, (
                f"{key}: distance_m {r.distance_m} against a straight-line "
                f"separation {sep} of its own endpoints — the half-span "
                f"defect (12aj (b))")
            assert r.lat is not None and r.lon is not None, (
                f"{key}: a rate row with no coordinate falls back to its "
                f"RING CENTROID (12aj (a))")
    assert seen, "the fixture carries no rate row — the twin proves nothing"


def test_a_shared_vertex_reads_the_senior_face_not_the_ring(cg):
    """(c) ``row_roles`` read the RING a pair was walked on, so a
    within-shape pair on LEMD's pad ``building12`` reported
    ``building|building`` — although its vertex is SHARED with apron
    ``pav12`` and the law's own answer to who owns a shared value is the
    SENIOR face.  The block's rolled-on test therefore called the 81 %
    rise in front of four heavy stands "landside, visual only"."""
    class _W:
        def __init__(self, role):
            self.tags = {"role": role}

    class _Row:
        way_a = _W("building")
        way_b = _W("building")
        de_m = 1.22
        distance_m = 1.498
        lat = lon = None
        role_a = role_b = None

    r = _Row()
    assert cg.row_roles(r) == ("building", "building")
    # ...and once run_checks has stamped the faces that meet there
    r.role_a = r.role_b = "apron"
    assert cg.row_roles(r) == ("apron", "apron")
    # the stamp is the SENIOR face by the emitter's own authority rank,
    # which is where "apron beats building" comes from — not a literal
    assert cg._authority_rank("apron") < cg._authority_rank("building")


def test_the_cliff_escape_reaches_every_family(cg):
    """(c) The escape lived inside the ``step`` branch, so the two
    SHARPEST readings of LEMD's T4S wall could not be cliffs at all:
    ``within_shape`` and ``cross_shape`` are class ``grade``, and a grade
    class meant REPORT however steep.  A cut is a cut whichever family
    found it."""
    law = cg.cockpit_law(refresh=True)
    geo = _ck_geometry(cg)

    class _W:
        def __init__(self, role):
            self.tags = {"role": role}

    def _row(fam_roles, de, dist, lat=None, lon=None, faces=None):
        class _R:
            pass
        r = _R()
        r.way_a, r.way_b = _W(fam_roles[0]), _W(fam_roles[1])
        r.de_m, r.distance_m = de, dist
        r.lat, r.lon = lat, lon
        r.role_a, r.role_b = (faces or (None, None))
        return r

    # LEMD's own two rows, at their true numbers
    wall = _row(("building", "building"), 1.22, 1.498, faces=("apron", "apron"))
    assert cg.cockpit_classify("within_shape", wall, law=law,
                               geometry=geo) == (cg.COCKPIT_MOTION, "cliff")
    cross = _row(("apron", "apron"), 1.20, 0.499)
    assert cg.cockpit_classify("cross_shape", cross, law=law,
                               geometry=geo) == (cg.COCKPIT_MOTION, "cliff")
    # a grade row that is a SLOPE is still REPORT, however big
    assert cg.cockpit_classify(
        "within_shape", _row(("apron", "apron"), 3.0, 200.0), law=law,
        geometry=geo) == (cg.COCKPIT_REPORT, "grade")
    # off rolled-on pavement a grade cliff is VISUAL, and only over
    # visual_m: the escape restores the bucket, never the threshold
    assert cg.cockpit_classify(
        "within_shape", _row(("parking_lot", "parking_lot"), 1.0, 1.0,
                             lat=0.001, lon=0.001),
        law=law, geometry=geo) == (cg.COCKPIT_VISUAL, "cliff")
    assert cg.cockpit_classify(
        "within_shape", _row(("parking_lot", "parking_lot"), 0.4, 1.0,
                             lat=0.001, lon=0.001),
        law=law, geometry=geo)[0] == cg.COCKPIT_REPORT
    # and LEMD's five rate rows, at their TRUE span, are slopes again
    for de, span in ((1.22, 5.49), (1.22, 5.99), (1.27, 5.49),
                     (1.23, 5.99), (1.28, 6.10)):
        assert cg.cockpit_classify(
            "airside_no_step", _row(("apron", "apron"), de, span),
            law=law, geometry=geo) == (cg.COCKPIT_REPORT,
                                       "spanned_over_motion")


# ══════════════════════════════════════════════════════════════════════
# §38 THE TILE SEAM IS A PIN — the two census families
# (owner RULINGS 2026-09-13ah / 13am / 13an; spec design-surface-spec §38)
# ══════════════════════════════════════════════════════════════════════
# The instruments must prove themselves: a patch WITH the defect reports
# it and a patch WITHOUT it reports nothing.  Before §38 the census had no
# patch-edge-vs-DEM family at all and could not see SPLP's 3.430 m seam
# berm; ``strip_seam_tear`` read 0 over it.

_SEAM_LAT = -12.1660000
_SEAM_LON = -77.0            # the meridian the airport crosses
_SEAM_HALF_M = 5.0


def _seam_patch(tmp_path, *, name, pin_dem, pin_z, bank_offset_m,
                half_width_m=_SEAM_HALF_M, role="runway"):
    """A two-node patch on one seam band edge plus one ``bank_foot`` chain
    ``bank_offset_m`` from the meridian.  ``pin_dem`` is what the sidecar
    publishes for the band-edge vertex, ``pin_z`` what the patch emits."""
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(_SEAM_LAT))
    d_edge = half_width_m / m_per_deg_lon
    edge_lon = _SEAM_LON - d_edge                 # the WEST band edge
    b_lon = _SEAM_LON - bank_offset_m / m_per_deg_lon
    # a CLOSED ring (the parser reads elevations off shape ways) whose two
    # eastern corners sit on the band edge and are the published pins
    west = edge_lon - 30.0 / m_per_deg_lon
    nodes = [(-1, _SEAM_LAT, edge_lon, pin_z),
             (-2, _SEAM_LAT + 0.0002, edge_lon, pin_z),
             (-5, _SEAM_LAT + 0.0002, west, pin_z),
             (-6, _SEAM_LAT, west, pin_z),
             (-3, _SEAM_LAT, b_lon, 40.0),
             (-4, _SEAM_LAT + 0.0001, b_lon, 40.0),
             (-7, _SEAM_LAT + 0.0002, b_lon, 40.0)]
    ways = [(-100, [-1, -2, -5, -6, -1], {"role": role, "shapeID": "S1"}),
            # THREE nodes: ``_parse_osm`` drops a way under three
            (-101, [-3, -4, -7], {"o4_feature": "bank_foot"})]
    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm version='0.6' generator='seam-twin'>"]
    for n, lat, lon, alt in nodes:
        out.append(f"  <node id='{n}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                   f"<tag k='alt_abs' v='{alt:.2f}' /></node>")
    for wid, nids, tags in ways:
        out.append(f"  <way id='{wid}'>")
        out += [f"    <nd ref='{n}' />" for n in nids]
        out += [f"    <tag k='{k}' v='{v}' />" for k, v in tags.items()]
        out.append("  </way>")
    out.append("</osm>")
    osm = tmp_path / f"{name}_auto.patch.osm"
    osm.write_text("\n".join(out) + "\n")
    Path(str(osm) + ".axes.json").write_text(json.dumps({
        "anchor": [_SEAM_LAT, _SEAM_LON],
        "ruleset": "icao",
        "seam_pins": [[round(_SEAM_LAT, 11), round(edge_lon, 11), pin_dem],
                      [round(_SEAM_LAT + 0.0002, 11), round(edge_lon, 11),
                       pin_dem]],
        "seam_half_width_m": half_width_m,
    }))
    return osm


def test_a_seam_pin_on_its_dem_prices_no_seam_residual(cg, tmp_path):
    fo = _families(cg, _seam_patch(tmp_path, name="onthedem",
                                   pin_dem=54.50, pin_z=54.50,
                                   bank_offset_m=60.0))
    assert fo["seam_residual"] == [], (
        "a seam vertex AT its published DEM sample must price nothing — "
        "a Pin holds exactly, so a row here is emitted surface")


def test_a_seam_pin_off_its_dem_prices_the_residual(cg, tmp_path):
    """The SPLP class, at its own worst number: vertex 1408 emitted at
    51.07 where the DEM is 54.50 (RULINGS 2026-09-13am (6))."""
    fo = _families(cg, _seam_patch(tmp_path, name="offthedem",
                                   pin_dem=54.50, pin_z=51.07,
                                   bank_offset_m=60.0))
    rows = fo["seam_residual"]
    assert len(rows) == 2, (
        f"2 published pins off their DEM priced {len(rows)} row(s)")
    assert abs(rows[0].de_m - 3.43) < 0.01, (
        f"the residual read {rows[0].de_m:.3f} m, not the 3.43 m the "
        f"emitted surface stands off its published pin")


def test_a_patch_with_no_seam_key_reads_exactly_as_before(cg, tmp_path):
    osm = _seam_patch(tmp_path, name="nokey", pin_dem=54.50, pin_z=51.07,
                      bank_offset_m=1.0)
    side = Path(str(osm) + ".axes.json")
    data = json.loads(side.read_text())
    del data["seam_pins"], data["seam_half_width_m"]
    side.write_text(json.dumps(data))
    fo = _families(cg, osm)
    assert fo["seam_residual"] == [] and fo["bank_across_seam"] == [], (
        "a patch predating §38 declares no seam and must price neither "
        "family — v1's own output goes through this reader")


def test_a_bank_foot_inside_the_band_is_a_defect(cg, tmp_path):
    """13an: chain ``bank:2`` sat 0.0237 m off the meridian and Triangle4XP
    split it 16,298 times against the unsplittable tile border."""
    fo = _families(cg, _seam_patch(tmp_path, name="bankin",
                                   pin_dem=54.50, pin_z=54.50,
                                   bank_offset_m=0.0237))
    assert len(fo["bank_across_seam"]) == 3, (
        f"a bank chain 0.0237 m from the meridian priced "
        f"{len(fo['bank_across_seam'])} row(s), not its 3 nodes")


def test_a_bank_foot_clear_of_the_band_is_not(cg, tmp_path):
    fo = _families(cg, _seam_patch(tmp_path, name="bankout",
                                   pin_dem=54.50, pin_z=54.50,
                                   bank_offset_m=_SEAM_HALF_M + 1.0))
    assert fo["bank_across_seam"] == [], (
        "a bank foot OUTSIDE the band is the lawful bank the airport is "
        "entitled to — the family must not price it")


def test_both_seam_families_carry_a_cockpit_class(cg):
    """A new family with no cockpit key does not load (``families.toml``
    header).  This asserts the two §38 families are IN the law table as
    well as in the register, and that the classes are the ones §38 (5)
    asks for: ``seam_residual`` a STEP (so the cockpit rule gives it
    CRITICAL motion on the rolled-on roles and visual elsewhere from ONE
    threshold pair) and ``bank_across_seam`` a KEEPOUT (presence in a
    region, not a height)."""
    import tomllib
    from pathlib import Path as _P
    table = tomllib.loads((_P(cg.__file__).resolve().parents[1]
                           / "src/auto_patch_v2/law/families.toml").read_text())
    for key in ("seam_residual", "bank_across_seam"):
        assert key in table, f"{key} is a census family with no law entry"
        assert key in {k for k, _t, _b in cg.LAW_FAMILIES}
    assert table["seam_residual"]["cockpit"] == "step"
    assert table["bank_across_seam"]["cockpit"] == "keepout"


# ── §39 (2) THE HAIRLINE LAW (owner RULINGS 2026-09-13bk) ──────────────

#: The LEMD site, verbatim from the shipped ``Data+40-004.poly`` of app
#: 1.0.327: the OSM WATER edge (marker 1) and the two TMERC-frame chord
#: splits the bank foot ring (marker 15) laid on it, 0.0594 mm off the
#: mesh's own straight line and exactly parallel to it.
_HAIR_A = (40.47647780, -3.54580410)
_HAIR_B = (40.47587640, -3.54541440)
_HAIR_S1 = (40.47627733349, -3.54567419923)
_HAIR_S2 = (40.47607686682, -3.54554429923)


def _hairline_patch(tmp_path, *, name, ring, shore=True):
    """A four-node apron ring plus a ``bank_foot`` chain over ``ring``,
    with the tile's foreign water edge published as ``shore_edges``."""
    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm version='0.6' generator='hairline-twin'>"]
    far = [(40.4750, -3.5480), (40.4750, -3.5460),
           (40.4752, -3.5460), (40.4752, -3.5480)]
    nid = 0
    ids_ring, ids_chain = [], []
    for lat, lon in far:
        nid -= 1
        ids_ring.append(nid)
        out.append(f"  <node id='{nid}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                   f"<tag k='alt_abs' v='600.00' /></node>")
    for lat, lon in ring:
        nid -= 1
        ids_chain.append(nid)
        out.append(f"  <node id='{nid}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                   f"<tag k='alt_abs' v='600.00' /></node>")
    out.append("  <way id='-100'>")
    out += [f"    <nd ref='{n}' />" for n in ids_ring + [ids_ring[0]]]
    out += ["    <tag k='role' v='apron' />", "    <tag k='shapeID' v='S1' />"]
    out.append("  </way>")
    out.append("  <way id='-101'>")
    out += [f"    <nd ref='{n}' />" for n in ids_chain]
    out.append("    <tag k='o4_feature' v='bank_foot' />")
    out.append("  </way>")
    out.append("</osm>")
    osm = tmp_path / f"{name}_auto.patch.osm"
    osm.write_text("\n".join(out) + "\n")
    side = {"ruleset": "icao", "anchor": [_HAIR_A[0], _HAIR_A[1]]}
    if shore:
        side["shore_edges"] = [[_HAIR_A[0], _HAIR_A[1], _HAIR_B[0], _HAIR_B[1]]]
    Path(str(osm) + ".axes.json").write_text(json.dumps(side))
    return osm


def test_the_lemd_hairline_is_priced(cg, tmp_path):
    """The instrument proves itself on the geometry that made the defect:
    a bank foot laid on the water line through the tmerc-frame chord
    splits, 0.0594 mm off it and 0.000 deg from parallel."""
    fo = _families(cg, _hairline_patch(
        tmp_path, name="hairline",
        ring=[_HAIR_A, _HAIR_S1, _HAIR_S2, _HAIR_B]))
    rows = fo["hairline_pair"]
    assert rows, ("the LEMD pair — 25 of which made 2.30 M sliver "
                  "triangles — must price at least one row")
    assert min(r.distance_m for r in rows) < 5.0e-4, (
        f"the worst gap read {min(r.distance_m for r in rows):.6f} m, not "
        f"the sub-millimetre hairline")


def test_the_welded_ring_prices_nothing(cg, tmp_path):
    """§39 (1)'s output: the chord splits gone, the ring SHARING the
    water edge's own two vertices.  Two edges that share their endpoints
    are one chain, not a pair."""
    fo = _families(cg, _hairline_patch(
        tmp_path, name="welded", ring=[_HAIR_A, _HAIR_B]))
    assert fo["hairline_pair"] == [], (
        "a ring welded onto the water's own vertices is the LAWFUL "
        "shore and must price nothing")


def test_a_patch_with_no_shore_key_prices_no_water_row(cg, tmp_path):
    """A patch predating §39 declares no water witness; the family then
    prices ring-vs-ring only — v1's own output goes through this reader."""
    fo = _families(cg, _hairline_patch(
        tmp_path, name="noshore", shore=False,
        ring=[_HAIR_A, _HAIR_S1, _HAIR_S2, _HAIR_B]))
    assert fo["hairline_pair"] == []


def test_hairline_pair_is_critical_unconditionally(cg):
    """§39 (2): a LOAD-TIME and TEXTURE defect, not a height — there is no
    threshold to price it against and no view test to pass."""
    import tomllib
    from pathlib import Path as _P
    table = tomllib.loads((_P(cg.__file__).resolve().parents[1]
                           / "src/auto_patch_v2/law/families.toml").read_text())
    assert table["hairline_pair"]["cockpit"] == "unmeshable"
    assert "hairline_pair" in {k for k, _t, _b in cg.LAW_FAMILIES}
    law = cg.cockpit_law(refresh=True)
    bucket, why = cg.cockpit_classify(
        "hairline_pair",
        cg.Violation(grade_pct=0.0, excess_pct=0.0, distance_m=24.8,
                     de_m=0.4999, way_a=None, way_b=None, pt_a=(0.0, 0.0),
                     pt_b=(0.0, 0.0), elev_a=0.0, elev_b=0.0),
        law=law)
    assert (bucket, why) == (cg.COCKPIT_VISUAL, "unmeshable")


# ── §37 (9) THE COVERAGE-EDGE JOIN (owner RULINGS 2026-09-13be) ─────────

_JOIN_LAT, _JOIN_LON = 35.2077398, -80.9290045     # KCLT way 10826 station 0


def _road_join_patch(tmp_path, *, name, ribbon, emitted):
    """A four-node service-road ring whose eastern kerbs sit at the patch's
    COVERAGE EDGE, with the core ribbon's altitude published for them
    (sidecar ``road_coverage_join``).  ``emitted`` is what the patch
    carries there, ``ribbon`` what the core levels the road to just
    outside."""
    m_lon = 111_320.0 * math.cos(math.radians(_JOIN_LAT))
    west = _JOIN_LON - 20.0 / m_lon
    nodes = [(-1, _JOIN_LAT, _JOIN_LON, emitted),
             (-2, _JOIN_LAT + 0.00007, _JOIN_LON, emitted),
             (-3, _JOIN_LAT + 0.00007, west, emitted),
             (-4, _JOIN_LAT, west, emitted)]
    ways = [(-100, [-1, -2, -3, -4, -1],
             {"role": "service_road", "shapeID": "R1", "ref": "dsf:polX"})]
    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm version='0.6' generator='road-join-twin'>"]
    for n, lat, lon, alt in nodes:
        out.append(f"  <node id='{n}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                   f"<tag k='alt_abs' v='{alt:.2f}' /></node>")
    for wid, nids, tags in ways:
        out.append(f"  <way id='{wid}'>")
        out += [f"    <nd ref='{n}' />" for n in nids]
        out += [f"    <tag k='{k}' v='{v}' />" for k, v in tags.items()]
        out.append("  </way>")
    out.append("</osm>")
    osm = tmp_path / f"{name}_auto.patch.osm"
    osm.write_text("\n".join(out) + "\n")
    Path(str(osm) + ".axes.json").write_text(json.dumps({
        "anchor": [_JOIN_LAT, _JOIN_LON],
        "ruleset": "faa",
        "road_coverage_join": [[round(_JOIN_LAT, 11), round(_JOIN_LON, 11), ribbon],
                               [round(_JOIN_LAT + 0.00007, 11),
                                round(_JOIN_LON, 11), ribbon]],
    }))
    return osm


def test_a_road_meeting_the_core_ribbon_prices_no_join_row(cg, tmp_path):
    """§37 (9): a road AT the ribbon's altitude where its way leaves the
    coverage prices nothing — the join is a Pin and a pin holds."""
    fo = _families(cg, _road_join_patch(tmp_path, name="joined",
                                        ribbon=203.48, emitted=203.48))
    assert fo["road_coverage_join"] == [], (
        "a road vertex at its published ribbon altitude must price nothing")


def test_a_road_standing_over_the_core_ribbon_prices_the_join(cg, tmp_path):
    """THE MEASURED CLASS (RULINGS 2026-09-13be): at KCLT way 10826 station
    0 the patch's kerb stood 2.36 m over the core ribbon it joins, and no
    other family could see it — the patch is lawful on its own side and the
    ribbon is not in the patch at all."""
    fo = _families(cg, _road_join_patch(tmp_path, name="stepped",
                                        ribbon=203.48, emitted=205.84))
    rows = fo["road_coverage_join"]
    assert len(rows) == 2, rows
    assert max(cg.row_magnitude(r) for r in rows) == pytest.approx(2.36, abs=0.01)


def test_a_patch_with_no_join_key_reads_exactly_as_before(cg, tmp_path):
    """Every patch built before §37 (9) carries no key and prices no row."""
    osm = _road_join_patch(tmp_path, name="nokey", ribbon=203.48, emitted=205.84)
    side = Path(str(osm) + ".axes.json")
    data = json.loads(side.read_text())
    data.pop("road_coverage_join")
    side.write_text(json.dumps(data))
    assert _families(cg, osm)["road_coverage_join"] == []


def test_the_join_family_is_registered_and_law_declared(cg):
    """The family is in ``LAW_FAMILIES``, its key is LAW INPUT, and
    ``families.toml`` declares it (the census cannot omit a family)."""
    assert "road_coverage_join" in {k for k, _t, _b in cg.LAW_FAMILIES}
    assert cg.SIDECAR_LAW_KEYS.get("road_coverage_join") == "road_coverage_join_ll"
    import sys as _sys
    _sys.path.insert(0, str(Path(cg.__file__).resolve().parents[1] / "src"))
    from auto_patch_v2.law import Law
    fam = Law.load().tables.families["road_coverage_join"]
    assert fam.cockpit == "step" and fam.solver == "pin"
    assert set(fam.roles) == {"service_road", "service_junction"}


# ══════════════════════════════════════════════════════════════════════
# §34 (10) THE ROAD MARGIN IS GENERAL — the ``ramp_in_road`` guard
# (owner RULINGS 2026-09-14bb / 14bc / 14bd; spec design-surface-spec
# §34 (10))
# ══════════════════════════════════════════════════════════════════════
# The family is a GUARD on ``planar/wall_corridor_ramps.road_true_edge``
# and reads 0 at OTHH before and after, so it must prove itself on a
# patch that DOES carry the defect: both directions, or the zero means
# nothing (the §B3 blind-walk lesson).

_RIR_LAT = 25.2660000
_RIR_LON = 51.6110000


def _ramp_road_patch(tmp_path, *, name, ramp_inset_m):
    """A 8 x 40 m ``service_road`` ribbon with a ``wall_corridor_ramp``
    beside it whose near edge stands ``ramp_inset_m`` INSIDE the ribbon
    (negative = short of it).  Two nodes of the ramp ring are the ones
    §34 (10) prices."""
    mlat = 111_320.0
    mlon = 111_320.0 * math.cos(math.radians(_RIR_LAT))

    def at(dx_m, dy_m):
        return (_RIR_LAT + dy_m / mlat, _RIR_LON + dx_m / mlon)
    # the road: x 0..40, y 0..8
    r = [at(0.0, 0.0), at(40.0, 0.0), at(40.0, 8.0), at(0.0, 8.0)]
    # the ramp: x 5..35, from y = -20 up to y = ramp_inset_m
    top = ramp_inset_m
    p = [at(5.0, -20.0), at(35.0, -20.0), at(35.0, top), at(5.0, top)]
    nodes, ways = [], []
    nid = -1
    for ring, tags in ((r, {"role": "service_road", "shapeID": "R1"}),
                       (p, {"role": "wall_corridor_ramp", "shapeID": "P1"})):
        ids = []
        for lat, lon in ring:
            nodes.append((nid, lat, lon, 3.96))
            ids.append(nid)
            nid -= 1
        ways.append((nid, ids + [ids[0]], tags))
        nid -= 1
    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm version='0.6' generator='ramp-in-road-twin'>"]
    for n, lat, lon, alt in nodes:
        out.append(f"  <node id='{n}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                   f"<tag k='alt_abs' v='{alt:.2f}' /></node>")
    for wid, nids, tags in ways:
        out.append(f"  <way id='{wid}'>")
        out += [f"    <nd ref='{n}' />" for n in nids]
        out += [f"    <tag k='{k}' v='{v}' />" for k, v in tags.items()]
        out.append("  </way>")
    out.append("</osm>")
    osm = tmp_path / f"{name}_auto.patch.osm"
    osm.write_text("\n".join(out) + "\n")
    Path(str(osm) + ".axes.json").write_text(json.dumps({
        "anchor": [_RIR_LAT, _RIR_LON], "ruleset": "icao"}))
    return osm


def test_a_ramp_stopping_at_the_road_edge_prices_no_ramp_in_road(cg, tmp_path):
    """The lawful case §34 (10) asks for: the ramp ends AT the road's
    edge.  Its top vertices are welded onto the ribbon's boundary, which
    is not inside it."""
    fo = _families(cg, _ramp_road_patch(tmp_path, name="attheedge",
                                        ramp_inset_m=0.0))
    assert fo["ramp_in_road"] == [], (
        "a ramp ending at the road edge is the law, not a defect")


def test_a_ramp_stopping_short_of_the_road_prices_nothing_either(cg, tmp_path):
    fo = _families(cg, _ramp_road_patch(tmp_path, name="short",
                                        ramp_inset_m=-2.0))
    assert fo["ramp_in_road"] == []


def test_a_ramp_reaching_the_road_centreline_is_a_defect(cg, tmp_path):
    """The OTHH class the ruling was written on: the ramp's top reached
    the CENTRELINE of an 8 m road — one lane of carriageway cut away."""
    fo = _families(cg, _ramp_road_patch(tmp_path, name="centreline",
                                        ramp_inset_m=4.0))
    rows = fo["ramp_in_road"]
    assert len(rows) == 2, (
        f"the ramp's two top vertices stand 4 m inside the ribbon; the "
        f"family priced {len(rows)} row(s)")
    assert all(abs(r.de_m - 4.0) < 0.05 for r in rows), (
        [r.de_m for r in rows])


def test_a_ramp_vertex_within_the_weld_tolerance_is_on_the_edge(cg, tmp_path):
    """The line is the census's OWN weld tolerance — the law's "these two
    vertices are one node" predicate — never a proximity semantic
    invented for this family."""
    fo = _families(cg, _ramp_road_patch(
        tmp_path, name="welded", ramp_inset_m=cg.SHARED_VERTEX_TOL_M * 0.5))
    assert fo["ramp_in_road"] == []
    fo2 = _families(cg, _ramp_road_patch(
        tmp_path, name="past", ramp_inset_m=cg.SHARED_VERTEX_TOL_M * 2.0))
    assert len(fo2["ramp_in_road"]) == 2


def test_ramp_in_road_is_registered_and_keeps_out(cg):
    """A family absent from ``LAW_FAMILIES`` or from ``families.toml``
    does not load; and §34 (10) prices PRESENCE, so the cockpit class is
    ``keepout`` — one vertex inside the ribbon is the whole defect."""
    from auto_patch_v2.law import tables as _T
    assert "ramp_in_road" in {k for k, _t, _b in cg.LAW_FAMILIES}
    fams = _T.load_default().tables.families
    assert fams["ramp_in_road"].cockpit == "keepout"
    # the RAMP family the walk reads is the LAW's structure roles, never a
    # second spelling of them
    law = _T.load_default()
    assert set(cg._RAMP_ROLES) == {r for r in _T.governed_roles(law)
                                   if _T.is_structure_role(law, r)}


# ══════════════════════════════════════════════════════════════════════
# §34 (5) (b) THE COVERED EXTENT OF AN UNDERPASS INCLUDES THE TAXIWAY'S
# STRIP — the ``ramp_in_strip`` guard (Fable 2026-09-15; RULINGS
# 2026-09-15h; owner 15e item 7; spec design-surface-spec §34 (5) (b))
# ══════════════════════════════════════════════════════════════════════
# The airside sibling of ``ramp_in_road``.  It must prove itself in BOTH
# directions on a patch that carries the defect, and it must prove the
# two readings that were MEASURED rather than chosen: the face's HOLES
# (without them LEMD's ``pav61`` blob reported 52 rows up to 220 m from
# any kerb, inside its own 144,429 m2 void) and the PAVEMENT SOLID's
# subtraction (the region is the BAND, so ``de_m`` can never exceed the
# class's own half width).

_RIS_LAT = 40.4611623
_RIS_LON = -3.5444804


def _ramp_strip_patch(tmp_path, *, name, ramp_gap_m, code_letter="E",
                      hole=False):
    """A 40 x 20 m code-E ``junction`` with a ``tunnel_ramp`` whose near
    edge stands ``ramp_gap_m`` out from the taxiway's south kerb.  The
    code-E graded strip is 19.0 m, so a gap under 19 m puts the ramp's
    two near vertices inside the strip.  With ``hole`` the taxiway ring
    is a LOOP around a 60 x 60 m void and the ramp stands in the middle
    of it — LEMD ``pav61``'s class, which is NOT a graded strip."""
    mlat = 111_320.0
    mlon = 111_320.0 * math.cos(math.radians(_RIS_LAT))

    def at(dx_m, dy_m):
        return (_RIS_LAT + dy_m / mlat, _RIS_LON + dx_m / mlon)
    if hole:
        pav = [at(-40.0, -40.0), at(40.0, -40.0), at(40.0, 40.0), at(-40.0, 40.0)]
        holes = [[at(-30.0, -30.0), at(30.0, -30.0), at(30.0, 30.0), at(-30.0, 30.0)]]
        ramp = [at(-5.0, -5.0), at(5.0, -5.0), at(5.0, 5.0), at(-5.0, 5.0)]
    else:
        pav = [at(0.0, 0.0), at(40.0, 0.0), at(40.0, 20.0), at(0.0, 20.0)]
        holes = []
        y = -ramp_gap_m
        ramp = [at(5.0, y - 30.0), at(35.0, y - 30.0), at(35.0, y), at(5.0, y)]
    nodes, ways = [], []
    nid = -1

    def add(ring, tags):
        nonlocal nid
        ids = []
        for lat, lon in ring:
            nodes.append((nid, lat, lon, 577.80))
            ids.append(nid)
            nid -= 1
        ways.append((nid, ids + [ids[0]], tags))
        nid -= 1
    add(pav, {"role": "junction", "aeroway": "taxiway",
              "code_letter": code_letter, "shapeID": "T1"})
    add(ramp, {"role": "tunnel_ramp", "aeroway": "taxiway",
               "ref": "tunnel_ramp", "shapeID": "P1"})
    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm version='0.6' generator='ramp-in-strip-twin'>"]
    for n, lat, lon, alt in nodes:
        out.append(f"  <node id='{n}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                   f"<tag k='alt_abs' v='{alt:.2f}' /></node>")
    for wid, nids, tags in ways:
        out.append(f"  <way id='{wid}'>")
        out += [f"    <nd ref='{n}' />" for n in nids]
        out += [f"    <tag k='{k}' v='{v}' />" for k, v in tags.items()]
        out.append("  </way>")
    out.append("</osm>")
    osm = tmp_path / f"{name}_auto.patch.osm"
    osm.write_text("\n".join(out) + "\n")
    side = {"anchor": [_RIS_LAT, _RIS_LON], "ruleset": "icao"}
    if holes:
        side["face_holes"] = {"T1": [[[lat, lon] for lat, lon in holes[0]]]}
    Path(str(osm) + ".axes.json").write_text(json.dumps(side))
    return osm


def test_a_ramp_beyond_the_strip_prices_no_ramp_in_strip(cg, tmp_path):
    """The lawful case §34 (5) (b) asks for: the mouth opens BEYOND the
    strip and the ramp descends outside it."""
    fo = _families(cg, _ramp_strip_patch(tmp_path, name="beyondstrip",
                                         ramp_gap_m=21.0))
    assert fo["ramp_in_strip"] == [], (
        "a ramp descending outside the strip is the law, not a defect")


def test_a_ramp_inside_the_strip_is_a_defect(cg, tmp_path):
    """The owner's LEMD class (15e item 7): the trench opened 15.5 m from
    a kerb whose code-E strip is 19.0 m."""
    fo = _families(cg, _ramp_strip_patch(tmp_path, name="instrip",
                                         ramp_gap_m=15.5))
    rows = fo["ramp_in_strip"]
    assert len(rows) == 2, (
        f"the ramp's two near vertices stand 15.5 m from a 19.0 m strip's "
        f"kerb; the family priced {len(rows)} row(s)")
    # the band is 19.0 m wide and the vertex sits 15.5 m into it, so it is
    # 3.5 m short of the band's OUTER edge
    assert all(abs(r.de_m - 3.5) < 0.05 for r in rows), [r.de_m for r in rows]


def test_the_strip_half_width_is_the_zone_law_s_own(cg, tmp_path):
    """ONE derivation with ``planar/zones`` and with
    ``planar/structure_underpass.strip_half_width_m`` — never a number
    spelled twice.  A code-C taxiway's strip is 12.5 m, so the same
    15.5 m gap is LAWFUL there and a defect at code E."""
    from auto_patch_v2.law import tables as _T
    from auto_patch_v2.planar.structure_underpass import strip_half_width_m
    from auto_patch_v2.classify.roles import Cell
    law = _T.load_default()
    for cl in ("A", "B", "C", "D", "E", "F"):
        cell = Cell(0, "junction", "x", (), (), None, cl, "airside", "pav", {})
        assert (cg._strip_half_width_m("junction", None, cl)
                == strip_half_width_m(law, cell)
                == _T.zone2_half_width_m(law, "junction", None, cl))
    assert cg._strip_half_width_m("junction", None, "E") == 19.0
    assert cg._strip_half_width_m("junction", None, "C") == 12.5
    # a role no zone band is built around declares no strip at all
    assert cg._strip_half_width_m("apron", None, None) == 0.0
    assert cg._strip_half_width_m("service_road", None, None) == 0.0
    fo = _families(cg, _ramp_strip_patch(tmp_path, name="codec",
                                         ramp_gap_m=15.5, code_letter="C"))
    assert fo["ramp_in_strip"] == [], (
        "15.5 m clears a code-C taxiway's 12.5 m strip")


def test_a_ramp_in_a_taxiway_loop_s_void_is_not_in_its_strip(cg, tmp_path):
    """THE FRAME IS THE SOLID (the ``zone_on_pavement`` frame).  The
    first arm read ring-blind and reported 52 LEMD rows, every one inside
    ``cross_connector:pav61``'s own 144,429 m2 HOLE and up to 220 m from
    any kerb — the ground inside a taxiway loop is lawful adjacent
    ground, not that taxiway's graded strip."""
    fo = _families(cg, _ramp_strip_patch(tmp_path, name="loopvoid",
                                         ramp_gap_m=0.0, hole=True))
    assert fo["ramp_in_strip"] == [], (
        "a ramp 25 m inside a taxiway loop's void is not in its strip")


def test_a_ramp_vertex_within_the_weld_tolerance_is_on_the_strip_edge(cg, tmp_path):
    """The line is the census's OWN weld tolerance, exactly as for
    ``ramp_in_road`` — never a proximity semantic invented here."""
    hw = 19.0
    fo = _families(cg, _ramp_strip_patch(
        tmp_path, name="stripweld",
        ramp_gap_m=hw - cg.SHARED_VERTEX_TOL_M * 0.5))
    assert fo["ramp_in_strip"] == []
    fo2 = _families(cg, _ramp_strip_patch(
        tmp_path, name="strippast",
        ramp_gap_m=hw - cg.SHARED_VERTEX_TOL_M * 2.0))
    assert len(fo2["ramp_in_strip"]) == 2


def test_ramp_in_strip_is_registered_and_keeps_out(cg):
    """A family absent from ``LAW_FAMILIES`` or from ``families.toml``
    does not load; and §34 (5) (b) prices PRESENCE, so the cockpit class
    is ``keepout``."""
    from auto_patch_v2.law import tables as _T
    assert "ramp_in_strip" in {k for k, _t, _b in cg.LAW_FAMILIES}
    fams = _T.load_default().tables.families
    assert fams["ramp_in_strip"].cockpit == "keepout"
    assert fams["ramp_in_strip"].pairs == "within"


# ══════════════════════════════════════════════════════════════════════
# §33 (6) THE PACK'S STRUCTURE OBJECTS ARE THE CUT GEOMETRY — the
# ``object_cut_offset`` / ``object_cut_depth`` guards (owner RULINGS
# 2026-09-15e items 1/3/4/6 and 2026-09-15g; Fable 2026-09-15j; lane
# `v2objcut`)
# ══════════════════════════════════════════════════════════════════════
# Both families are GUARDS on ``airport/object_cut.py``'s reading and are
# meant to read 0 on a lawful build, so they must prove themselves on a
# patch that DOES carry each defect — both directions, or the zero means
# nothing (the §B3 blind-walk lesson, the ``ramp_in_road`` precedent
# above).

_OC_LAT = 22.3030675
_OC_LON = 113.9070568


def _object_cut_patch(tmp_path, *, name, ramp_out_m, floor_z, authored_floor):
    """A 30 x 120 m object WALL LINE published in the sidecar, with a
    ``tunnel_ramp`` face inside it whose two far vertices stand
    ``ramp_out_m`` OUTSIDE the wall line (negative = inside), emitted at
    ``floor_z`` against the object's ``authored_floor``."""
    mlat = 111_320.0
    mlon = 111_320.0 * math.cos(math.radians(_OC_LAT))

    def at(dx_m, dy_m):
        return (_OC_LAT + dy_m / mlat, _OC_LON + dx_m / mlon)
    outline = [at(0.0, 0.0), at(120.0, 0.0), at(120.0, 30.0), at(0.0, 30.0)]
    # the ramp: x 10..110, y 5 .. 25 + ramp_out_m (25 + 5 = the wall line)
    top = 25.0 + ramp_out_m
    ramp = [at(10.0, 5.0), at(110.0, 5.0), at(110.0, top), at(10.0, top)]
    nodes, ways = [], []
    nid = -1
    ids = []
    for lat, lon in ramp:
        nodes.append((nid, lat, lon, floor_z))
        ids.append(nid)
        nid -= 1
    ways.append((nid, ids + [ids[0]],
                 {"role": "tunnel_ramp", "ref": "tunnel_ramp:object-cut:t5@0",
                  "aeroway": "taxiway", "shapeID": "OC1"}))
    nid -= 1
    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm version='0.6' generator='object-cut-twin'>"]
    for n, lat, lon, alt in nodes:
        out.append(f"  <node id='{n}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                   f"<tag k='alt_abs' v='{alt:.2f}' /></node>")
    for wid, nids, tags in ways:
        out.append(f"  <way id='{wid}'>")
        out += [f"    <nd ref='{n}' />" for n in nids]
        out += [f"    <tag k='{k}' v='{v}' />" for k, v in tags.items()]
        out.append("  </way>")
    out.append("</osm>")
    osm = tmp_path / f"{name}_auto.patch.osm"
    osm.write_text("\n".join(out) + "\n")
    Path(str(osm) + ".axes.json").write_text(json.dumps({
        "anchor": [_OC_LAT, _OC_LON], "ruleset": "icao",
        "object_cuts": [{
            "id": "object-cut:t5@0", "signature": "B",
            "resource": "tunnel/tunnel5_done.obj", "objects": ["1"],
            "floor_m": authored_floor, "depth_m": 6.011,
            "outline_ll": [[la, lo] for la, lo in outline],
            "ramp_refs": ["tunnel_ramp:object-cut:t5@0"],
            "wall_ref": "tunnel_wall:object-cut:t5@0"}]}))
    return osm


def test_a_cut_inside_its_object_prices_no_object_cut_offset(cg, tmp_path):
    """The lawful case §33 (6) asks for: the emitted trench lies inside
    the wall line the pack's object drew."""
    fo = _families(cg, _object_cut_patch(tmp_path, name="inside",
                                         ramp_out_m=-3.0, floor_z=1.31,
                                         authored_floor=1.31))
    assert fo["object_cut_offset"] == [], (
        "a cut inside its object's wall line is the law, not a defect")
    assert fo["object_cut_depth"] == []


def test_a_cut_outside_its_object_is_a_defect(cg, tmp_path):
    """The VHHH class the ruling was written on: 25 of ramp way −11078's
    42 vertices stood outside ``tunnel5_done.obj``, the worst 76.25 m
    away, because the corridor was the OSM bore's."""
    fo = _families(cg, _object_cut_patch(tmp_path, name="outside",
                                         ramp_out_m=9.0, floor_z=1.31,
                                         authored_floor=1.31))
    rows = fo["object_cut_offset"]
    assert len(rows) == 2, (
        f"the ramp's two far vertices stand 4 m outside the wall line; the "
        f"family priced {len(rows)} row(s)")
    assert all(abs(r.de_m - 4.0) < 0.05 for r in rows), [r.de_m for r in rows]


def test_the_offset_bar_is_the_spec_bar(cg, tmp_path):
    """0.5 m is the spec's own bar for ``object_cut_offset``; a vertex
    inside it is the emitter's snap, not a cut leaving its object."""
    fo = _families(cg, _object_cut_patch(
        tmp_path, name="snap", ramp_out_m=5.0 + cg.OBJECT_CUT_OFFSET_M * 0.5,
        floor_z=1.31, authored_floor=1.31))
    assert fo["object_cut_offset"] == []
    fo2 = _families(cg, _object_cut_patch(
        tmp_path, name="past", ramp_out_m=5.0 + cg.OBJECT_CUT_OFFSET_M * 3.0,
        floor_z=1.31, authored_floor=1.31))
    assert len(fo2["object_cut_offset"]) == 2


def test_a_shallow_cut_is_an_object_cut_depth_row(cg, tmp_path):
    """The owner's VHHH site: the floor came out at DEM − ``bore_datum_m``
    = 2.23 against the object's AUTHORED 1.31, 0.92 m too shallow.  The
    authored depth overrides ``bore_datum_m``."""
    fo = _families(cg, _object_cut_patch(tmp_path, name="shallow",
                                         ramp_out_m=-3.0, floor_z=2.23,
                                         authored_floor=1.31))
    rows = fo["object_cut_depth"]
    assert len(rows) == 1, f"one row per cut that misses the bar, not {len(rows)}"
    assert abs(rows[0].de_m - 0.92) < 0.02, rows[0].de_m
    assert fo["object_cut_offset"] == [], "the plan half is unaffected"


def test_the_depth_bar_is_the_spec_bar(cg, tmp_path):
    fo = _families(cg, _object_cut_patch(
        tmp_path, name="atbar", ramp_out_m=-3.0,
        floor_z=1.31 + cg.OBJECT_CUT_DEPTH_M * 0.5, authored_floor=1.31))
    assert fo["object_cut_depth"] == []


def test_a_patch_with_no_object_cuts_prices_neither_family(cg, tmp_path):
    """Every airport whose pack authors no cut geometry reads exactly as
    it did before §33 (6): the sidecar key is absent and both families
    are empty, never a crash and never a fabricated row."""
    osm = _object_cut_patch(tmp_path, name="nokey", ramp_out_m=9.0,
                            floor_z=9.99, authored_floor=1.31)
    side = Path(str(osm) + ".axes.json")
    data = json.loads(side.read_text())
    data.pop("object_cuts")
    side.write_text(json.dumps(data))
    fo = _families(cg, osm)
    assert fo["object_cut_offset"] == []
    assert fo["object_cut_depth"] == []


def test_the_object_cut_families_are_registered(cg):
    """A family absent from ``LAW_FAMILIES`` or from ``families.toml``
    does not load (the census cannot omit a family); §33 (6)'s plan half
    prices PRESENCE outside a region, so its cockpit class is
    ``keepout``."""
    from auto_patch_v2.law import tables as _T
    names = {k for k, _t, _b in cg.LAW_FAMILIES}
    assert "object_cut_offset" in names
    assert "object_cut_depth" in names
    fams = _T.load_default().tables.families
    assert fams["object_cut_offset"].cockpit == "keepout"
    assert fams["object_cut_depth"].cockpit == "step"
    # the sidecar key is declared on BOTH sides — the emitter publishes it
    # and the census reads it under the same name
    from auto_patch_v2.emit import osm_adapter as _oa
    assert "object_cuts" in _oa.SIDECAR_KEYS
    assert cg.SIDECAR_LAW_KEYS["object_cuts"] == "object_cuts_ll"


# ══════════════════════════════════════════════════════════════════════
# §34 (13) (1) A STRUCTURE RAMP IS GRADED ALONG ITS AXIS (Fable
# 2026-09-15; RULINGS 2026-09-15u; spec design-surface-spec §34 (13) (1))
# ══════════════════════════════════════════════════════════════════════
# ONE derivation, two readers: the engine's
# `auto_patch_v2.verify.within.ring_route_m` and the census's
# `_ring_route_m` (imported from it, with a literal no-engine fallback).
# The reading can only RELAX, so the twin proves both directions: a
# straight ramp is untouched, a CURVED one is priced along its axis, and
# a ramp genuinely over cap along that axis still reports.

_RRA_LAT = 40.4947697
_RRA_LON = -3.5829037


def _ramp_axis_patch(tmp_path, *, name, stations, fall_m, half_w=1.75):
    """A `tunnel_ramp` ribbon whose CENTRELINE follows `stations`
    (metre offsets from the site) and whose elevation falls `fall_m`
    linearly from the first station to the last.  The ring is written the
    way `planar/structure_geometry.geometry` writes one: down the left
    side, back up the right."""
    mlat = 111_320.0
    mlon = 111_320.0 * math.cos(math.radians(_RRA_LAT))

    def at(dx_m, dy_m):
        return (_RRA_LAT + dy_m / mlat, _RRA_LON + dx_m / mlon)
    n = len(stations)
    left, right, zs = [], [], []
    for k, (x, y) in enumerate(stations):
        if k == 0:
            ux, uy = stations[1][0] - x, stations[1][1] - y
        else:
            ux, uy = x - stations[k - 1][0], y - stations[k - 1][1]
        L = math.hypot(ux, uy) or 1.0
        nx, ny = -uy / L, ux / L
        left.append(at(x + nx * half_w, y + ny * half_w))
        right.append(at(x - nx * half_w, y - ny * half_w))
        zs.append(600.0 - fall_m * k / (n - 1))
    ring = left + list(reversed(right))
    alts = zs + list(reversed(zs))
    nodes, ids = [], []
    nid = -1
    for (lat, lon), z in zip(ring, alts):
        nodes.append((nid, lat, lon, z))
        ids.append(nid)
        nid -= 1
    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm version='0.6' generator='ramp-axis-twin'>"]
    for nd, lat, lon, alt in nodes:
        out.append(f"  <node id='{nd}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                   f"<tag k='alt_abs' v='{alt:.2f}' /></node>")
    out.append(f"  <way id='{nid}'>")
    out += [f"    <nd ref='{i}' />" for i in ids + [ids[0]]]
    for k, v in (("role", "tunnel_ramp"), ("ref", "tunnel_ramp"),
                 ("aeroway", "taxiway"), ("shapeID", "RA1")):
        out.append(f"    <tag k='{k}' v='{v}' />")
    out.append("  </way>")
    out.append("</osm>")
    osm = tmp_path / f"{name}_auto.patch.osm"
    osm.write_text("\n".join(out) + "\n")
    Path(str(osm) + ".axes.json").write_text(json.dumps({
        "anchor": [_RRA_LAT, _RRA_LON], "ruleset": "icao"}))
    return osm


def _straight(n, span):
    return [(span * k / (n - 1), 0.0) for k in range(n)]


def _quarter_arc(n, radius):
    """A quarter circle: route = pi*r/2, chord = r*sqrt(2) — the shape
    LEMD's -10853 has (143.5 m of axis across a 99.25 m chord)."""
    return [(radius * math.sin(math.pi / 2 * k / (n - 1)),
             radius * (1 - math.cos(math.pi / 2 * k / (n - 1))))
            for k in range(n)]


def test_ring_route_m_is_the_walk_and_never_shorter_than_the_chord():
    """The derivation itself, and the ONE property the whole reading
    rests on: a polyline between two of its own points is never shorter
    than the chord, so §34 (13) (1) can only RELAX."""
    from auto_patch_v2.verify.within import ring_route_m
    sq = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    assert ring_route_m(sq, 0, 1) == pytest.approx(10.0)
    assert ring_route_m(sq, 0, 2) == pytest.approx(20.0)   # min of two 20s
    assert ring_route_m(sq, 0, 3) == pytest.approx(10.0)   # the short way
    assert ring_route_m(sq, 2, 2) == 0.0
    for i in range(4):
        for j in range(4):
            chord = math.dist(sq[i], sq[j])
            assert ring_route_m(sq, i, j) >= chord - 1e-9


def test_the_census_and_the_engine_read_one_ring_route(cg):
    """ONE derivation, two readers — never a second spelling (the
    census-wrapper precedent).  `check_grade._ring_route_m` IS the
    engine's function unless the engine is absent."""
    from auto_patch_v2.verify.within import ring_route_m
    assert cg._ring_route_m is ring_route_m
    arc = _quarter_arc(9, 60.0)
    for i in (0, 3, 8):
        for j in (0, 4, 8):
            assert cg._ring_route_m(arc, i, j) == pytest.approx(
                ring_route_m(arc, i, j))


def test_a_straight_ramp_is_unchanged_by_the_axis_reading(cg, tmp_path):
    """The axis of a straight ramp IS its chord, so the reading must not
    move a single row: a straight ramp over its cap still reports."""
    fo = _families(cg, _ramp_axis_patch(
        tmp_path, name="straightover", stations=_straight(9, 100.0),
        fall_m=12.0))                       # 12 % over 100 m, cap 8 %
    rows = [r for r in fo["within_shape"]
            if abs(r.distance_m - 100.0) < 1.0]
    assert rows, "a straight ramp at 12 % must still report"
    assert all(r.grade_pct > 8.0 for r in rows)


def test_a_curved_ramp_is_priced_along_its_axis_not_its_chord(cg, tmp_path):
    """LEMD's own shape (owner 15e item 5): ramp way -10853 fell 8.250 m
    over a 99.25 m PLAN CHORD — 8.31 %, over its 8 % cap — where its axis
    runs 143.5 m, which is 5.75 % and lawful.  A quarter arc of radius
    91.4 m has the same ratio (route 143.5 m, chord 129.2 m ... the exact
    numbers do not matter; the LAW does): the fall that is over cap
    across the chord and under it along the axis prices NO row."""
    n, radius = 13, 91.4
    arc = _quarter_arc(n, radius)
    route = sum(math.dist(arc[k], arc[k + 1]) for k in range(n - 1))
    chord = math.dist(arc[0], arc[-1])
    assert route > chord * 1.05, (route, chord)
    fall = 0.5 * (0.08 * route + 0.08 * chord)   # over the chord, under the axis
    assert fall / chord > 0.08 and fall / route < 0.08
    fo = _families(cg, _ramp_axis_patch(
        tmp_path, name="curvedlawful", stations=arc, fall_m=fall))
    long_rows = [r for r in fo["within_shape"] if r.distance_m > chord * 0.9]
    assert long_rows == [], (
        "a ramp inside its cap along its own axis prices no mouth-to-top "
        f"row: {[(r.distance_m, r.grade_pct) for r in long_rows]}")
    # and the reading never blinds a ramp that IS over cap along the axis
    fo2 = _families(cg, _ramp_axis_patch(
        tmp_path, name="curvedover", stations=arc, fall_m=0.12 * route))
    over = [r for r in fo2["within_shape"] if r.distance_m > chord * 0.9]
    assert over, "an over-cap axis grade must still report"
    # the END-TO-END pair is reported over the AXIS run, not the chord
    # (the other long pairs are between interior stations, whose own
    # axis runs are legitimately shorter)
    assert max(r.distance_m for r in over) > chord, (
        f"the reported span is the AXIS run: max "
        f"{max(r.distance_m for r in over):.1f} m vs chord {chord:.1f} m")
    assert max(r.distance_m for r in over) == pytest.approx(route, rel=0.02)
