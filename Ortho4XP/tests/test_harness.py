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
* §4 THE LANE RITUAL — the worktree script symlinks (never copies) the four
  shared data dirs, clones Patches, and refuses teardown while a child
  process holds the tree.
"""
from __future__ import annotations

import importlib.util
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
    """``_write_axes_sidecar`` is gated on ``config.LOG_VERBOSITY > 0``.
    Without it the patch has NO sidecar and every census silently degrades
    to the context-free frame — the single most expensive silent
    degradation in this tree."""
    src = Path(inspect.getfile(build_mod)).read_text()
    assert "O4_LOG_VERBOSITY" in src


# ══════════════════════════════════════════════════════════════════════
# §4 THE LANE RITUAL
# ══════════════════════════════════════════════════════════════════════

RITUAL = HARNESS / "lane_worktree.sh"


def test_the_ritual_script_is_executable():
    assert RITUAL.exists(), "tools/harness/lane_worktree.sh is missing"
    assert os.access(RITUAL, os.X_OK), "lane_worktree.sh is not executable"


def test_the_ritual_symlinks_and_never_copies_the_shared_dirs():
    """Elevation_data must be a SYMLINK: a copied inset cache is a SECOND
    cache that warms independently, and warm-vs-cold has already moved a
    measured elevation by 12 m.  Patches, by contrast, must be CLONED —
    a lane writing patches into the shared dir corrupts every other lane."""
    src = RITUAL.read_text()
    link = re.search(r'^LINK_DIRS="([^"]*)"', src, re.M)
    clone = re.search(r'^CLONE_DIRS="([^"]*)"', src, re.M)
    assert link and clone, "the ritual must declare LINK_DIRS and CLONE_DIRS"
    assert set(link.group(1).split()) == {
        "venv", "OSM_data", "Airport_mod_cache", "Elevation_data"}, (
        f"LINK_DIRS is {link.group(1)!r}: all four shared dirs must be "
        f"SYMLINKED — a copied Elevation_data is a second inset cache that "
        f"warms independently, and warm-vs-cold has moved terrain 12 m")
    assert set(clone.group(1).split()) == {"Patches"}, (
        f"CLONE_DIRS is {clone.group(1)!r}: Patches must be CLONED (lanes "
        f"WRITE there) and nothing else may be")
    files = re.search(r'^CLONE_FILES="([^"]*)"', src, re.M)
    assert files and "Ortho4XP.cfg" in files.group(1), (
        "Ortho4XP.cfg must be CLONED into a lane worktree: it is untracked, "
        "so a fresh worktree has none, and Tile.read_from_config() then "
        "falls back to constructor defaults — a surface production never "
        "builds, announced by one log line")
    assert re.search(r'ln -s "\$MAIN_ENGINE/\$d"', src), (
        "LINK_DIRS entries must be created with ln -s")
    assert "cp -R" in src, "CLONE_DIRS entries must be copied"


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
# §5 THE INDEX IS THE CONSULTATION SURFACE
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
