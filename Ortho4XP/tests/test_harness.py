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

def _grade_gate_src() -> str:
    return (Path(__file__).parent / "test_pavement_grade.py").read_text()


def test_the_acceptance_gate_reads_the_one_law_frame():
    """The gate hand-mirrored ``_write_axes_sidecar``'s payload out of the
    layout — sixty lines of axes, anchor, seam pins, mesh, crown field,
    pair caps and terrace joints.  It never passed ``ruleset``, so KCLT
    built under FAA law was judged under ICAO.  One reader now."""
    src = _grade_gate_src()
    assert "run_checks_law_true(" in src, (
        "the acceptance gate must take its law frame from "
        "check_grade.run_checks_law_true, not assemble kwargs")
    code = _code_only(src)
    for key in ("taxi_axes_exact_ll", "junction_mesh_edges_ll",
                "seam_pins_ll", "crown_drops_ll", "crown_centerline_ll",
                "pair_caps_ll", "terrace_joints_ll"):
        assert key not in code, (
            f"the acceptance gate still assembles {key!r} itself — that is "
            f"a second instrument describing the same population")


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
