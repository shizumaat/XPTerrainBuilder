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
import json
import os
import re
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


def test_the_near_miss_frontage_law_is_one_authority(cg):
    """Cycle-5 item 6: the census family and the solve's law edges must
    recognize ONE population.  The radius, the role set and the budget all
    live in ``auto_patch.config``; the solver module re-exports them.  The
    role tuple is spelled as strings there (config cannot import
    ``layout``), so a ROLE_* rename would silently un-scope the law — this
    is what makes that loud."""
    from auto_patch.config import (BUILDING_FRONTAGE_NEAR_MISS_M,
                                   NEAR_MISS_FRONTAGE_SOFT_ROLES,
                                   near_miss_frontage_budget, APRON_MAX_GRADE)
    from auto_patch.layout import (ROLE_APRON, ROLE_JUNCTION,
                                   ROLE_SERVICE_JUNCTION)
    from auto_patch.elevation_per_surface.route_profile import anchors
    assert NEAR_MISS_FRONTAGE_SOFT_ROLES == (
        ROLE_APRON, ROLE_JUNCTION, ROLE_SERVICE_JUNCTION), (
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
    while their host was the 4 % groundside tunnel ramp whose vertices they
    are."""
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


def test_a_MISSING_canonical_tile_cfg_REFUSES(build_mod, tmp_path):
    """Never synthesize defaults: a made-up provider and ZL build a tile
    nobody asked for and exit 0 — the silently-smaller-layout trap."""
    lane = tmp_path / "lane" / "zOrtho4XP_+30+031"
    with pytest.raises(SystemExit) as exc:
        build_mod.provision_tile_cfg(30, 31, lane,
                                     source_root=tmp_path / "empty_main")
    msg = str(exc.value)
    assert "REFUSING" in msg and "Ortho4XP_+30+031.cfg" in msg
    assert "2026-08-12b" in msg, "the refusal cites the ruling it enforces"
    assert not (lane / "Ortho4XP_+30+031.cfg").exists(), (
        "the refusal wrote NOTHING — a defaults file left behind would be "
        "the next lane's canonical source")


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
    provision AFTER it would record a source the build never used."""
    src = inspect.getsource(build_mod.build_tile)
    assert src.index("provision_tile_cfg(") < src.index("read_from_config()"), (
        "provision the input BEFORE the engine reads it")
    assert "tile_cfg_provenance" in src, "and hand it back for the frame"
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


def _ritual(env, *args):
    return subprocess.run([str(RITUAL), *args], env=env,
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
                 "SHARED_DATA_DIRS", "DATA_REPO"):
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
    assert "require_no_swallowed_write_block(guard.blocked)" in src, (
        "the detector must read THIS run's guard record")
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
    assert len(host_rows) == len(ring_rows), (
        "one geometry judged twice is the premise of this twin")
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
        "crown_spine"}


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
