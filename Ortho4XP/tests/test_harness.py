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


def test_the_snapshot_sees_every_write(build_mod, tmp_path, monkeypatch):
    """The audit's guarantee is 'this build wrote NOTHING into the shared
    repo'.  A sampled snapshot cannot make that claim, so the walk is
    full — ~2.7 k files, ~10 ms."""
    repo = tmp_path / "shared"
    monkeypatch.setattr(build_mod, "DATA_REPO", repo)
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
                                                           tmp_path,
                                                           monkeypatch):
    """Ruling §3: concurrent lanes never race a regeneration.  Blocking is
    not the answer either — a lane waiting on another lane's download is
    indistinguishable from a hung build."""
    monkeypatch.setattr(build_mod, "LOCK_DIR", tmp_path / "locks")
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
        build_mod, tmp_path, monkeypatch):
    """A dead pid does NOT mean the write completed — the cache may be
    half-written, which is worse than no cache."""
    monkeypatch.setattr(build_mod, "LOCK_DIR", tmp_path / "locks")
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
                                                          tmp_path,
                                                          monkeypatch):
    """"Exactly once, as an explicit logged event" needs a record that
    outlives the session, in the SHARED repo where the next lane will
    look."""
    repo = tmp_path / "shared"
    (repo / "Elevation_data").mkdir(parents=True)
    (repo / "Elevation_data" / "N30E031.hgt").write_text("raster")
    ledger = repo / ".harness" / "refresh_ledger.jsonl"
    monkeypatch.setattr(build_mod, "DATA_REPO", repo)
    monkeypatch.setattr(build_mod, "REFRESH_LEDGER", ledger)
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
    complete-but-late instrument for an early-but-partial one."""
    src = (HARNESS / "build_airport.py").read_text()
    assert "def report_unauthorised_writes(" in src
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
    """
    import inspect
    sig = inspect.signature(build_mod.build_patch)
    assert "write_guard" in sig.parameters
    src = inspect.getsource(build_mod.build_patch)
    assert "SharedRepoWriteGuard(" in src, (
        "build_patch must arm a guard when its caller passes none")
    assert "with guard:" in src


def test_every_build_result_carries_the_frame_and_guard_state(build_mod):
    """The frame record has to be IN the artifact: "which corpus cut the
    insets" is a question asked of numbers that are already in a report."""
    import inspect
    src = inspect.getsource(build_mod.build_patch)
    for key in ("write_guard_armed", "write_guard_blocked",
                "dem_frame_effective"):
        assert f'"{key}"' in src, f"build_patch result omits {key}"


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
    assert hits == [("Default_DSF_cache/322b7f2a/+50+010.dsf.tmp.text",
                     "dsf_cache")], (
        "the DSF dump cache is the one the suite must never author; the "
        "mod-cache and inset writes are the registered, explained "
        "exceptions")
    assert conftest.unauthorised_shared_writes(
        {"added": [], "modified": [], "removed": []},
        build_mod.scope_of) == []


def test_every_suite_warm_scope_is_a_real_scope_with_a_reason(build_mod):
    """An allowance that names no real scope allows nothing (and hides
    what it meant to allow); one without a reason is a shrug."""
    conftest = _conftest()
    scopes = {s for s, _p, _w in build_mod.REFRESH_SCOPES}
    for scope, why in conftest._SUITE_MAY_WARM.items():
        assert scope in scopes, (
            f"{scope!r} is not a harness refresh scope — the detector "
            f"would never see a path classified as it")
        assert len(why.split()) >= 6, f"{scope!r} allowance has no reason"
    assert "dsf_cache" not in conftest._SUITE_MAY_WARM, (
        "the DSFTool dump cache is the measured leak; allowing it would "
        "re-open exactly the hole this section closes")


def test_the_detector_uses_the_harness_snapshot_not_a_copy():
    conftest_src = (Path(__file__).parent / "conftest.py").read_text()
    assert "shared_repo_snapshot" in conftest_src and \
        "snapshot_diff" in conftest_src and "scope_of" in conftest_src, (
        "the detector must use the harness's own snapshot and scope "
        "register — a private copy is the census-wrapper defect")
    assert "os.walk" not in conftest_src, (
        "conftest walks the shared repo itself — that is the private copy")
    assert "e9daef5" in conftest_src, "the failure must cite its ruling"


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
