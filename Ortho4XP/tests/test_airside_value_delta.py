"""Twin for ``tools/airside_value_delta.py`` — the whole-patch AIRSIDE
VALUE read an airside-frozen lane is adjudicated on.

What must hold, and why each one is here rather than left to a reviewer:

* the CLI's JSON **is** the library entry's result (the two-instruments
  trap: a printed number and a dumped number that can drift are two
  instruments describing one population);
* every role set is IMPORTED from the law's own modules, never re-spelled
  (the census-wrapper precedent, RULINGS ``7e90032``);
* the join is the CANONICAL 11-decimal lat/lon spelling — a node present
  in one arm only is ADDED/REMOVED, never MOVED, or every densification
  reads as a phantom pull;
* the two frames really are two populations, and the solve-owned one is
  the subset — quoting one number for both is the failure this tool's
  docstring names;
* the road-weld split classifies by the ROAD FAMILY the census itself
  publishes;
* a node with no emitted altitude is reported, never counted as 0.0;
* the index entry exists (a tool absent from ``tools/INDEX.md`` is treated
  as absent).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


def _load():
    spec = importlib.util.spec_from_file_location(
        "avd_twin", ROOT / "tools" / "airside_value_delta.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["avd_twin"] = mod
    spec.loader.exec_module(mod)
    return mod


avd = _load()


# ── a two-node-per-way synthetic patch in the emitter's own dialect ───
def _patch(path: Path, ways) -> Path:
    """``ways`` = [(role, [(lat, lon, alt|None), ...]), ...]."""
    nodes, body, nid = [], [], -1
    seen: dict = {}
    for role, pts in ways:
        refs = []
        for (la, lo, alt) in pts:
            key = (f"{la:.11f}", f"{lo:.11f}")
            if key not in seen:
                seen[key] = nid
                if alt is None:
                    nodes.append(
                        f"<node id='{nid}' lat='{la:.11f}' lon='{lo:.11f}'/>")
                else:
                    nodes.append(
                        f"<node id='{nid}' lat='{la:.11f}' lon='{lo:.11f}'>"
                        f"<tag k='alt_abs' v='{alt}'/></node>")
                nid -= 1
            refs.append(seen[key])
        nds = "".join(f"<nd ref='{r}'/>" for r in refs + [refs[0]])
        body.append(f"<way id='{nid}'>{nds}"
                    f"<tag k='role' v='{role}'/></way>")
        nid -= 1
    path.write_text("<?xml version='1.0'?><osm version='0.6'>"
                    + "".join(nodes) + "".join(body) + "</osm>", encoding="utf-8", newline="")
    return path


#: One apron (airside pavement, stage A) and one service_road
#: (groundside), sharing NOTHING; plus a graded_strip, which is airside in
#: the ROW-SIDE frame and absent from the SOLVE-OWNED one.
def _arms(tmp_path, apron_alt_b, strip_alt_b):
    a = _patch(tmp_path / "a.osm", [
        ("apron", [(1.0, 1.0, 10.0), (1.0, 1.001, 10.0), (1.001, 1.0, 10.0)]),
        ("graded_strip", [(2.0, 2.0, 20.0), (2.0, 2.001, 20.0),
                          (2.001, 2.0, 20.0)]),
        ("service_road", [(3.0, 3.0, 30.0), (3.0, 3.001, 30.0),
                          (3.001, 3.0, 30.0)]),
    ])
    b = _patch(tmp_path / "b.osm", [
        ("apron", [(1.0, 1.0, apron_alt_b), (1.0, 1.001, 10.0),
                   (1.001, 1.0, 10.0)]),
        ("graded_strip", [(2.0, 2.0, strip_alt_b), (2.0, 2.001, 20.0),
                          (2.001, 2.0, 20.0)]),
        ("service_road", [(3.0, 3.0, 31.0), (3.0, 3.001, 30.0),
                          (3.001, 3.0, 30.0)]),
    ])
    return a, b


def test_the_role_sets_are_imported_not_respelled():
    from auto_patch_v2.law import Law
    from auto_patch_v2.law.tables import airside_stage_roles
    from auto_patch_v2.solve.design import airside_stage_roles as solve_split
    from tools.harness.law_support.roles import GROUNDSIDE_ROLES
    gs, solve_air, road = avd.role_sets()
    assert gs == frozenset(GROUNDSIDE_ROLES)
    # the set the staged solve itself splits by (``solve/design.py``
    # ``stage_roles=``), not a look-alike
    assert solve_split is airside_stage_roles
    assert solve_air == airside_stage_roles(Law.for_airport("XXXX"))
    # the pad conforms in stage 2 (v1's frame counted it; v2's does not)
    assert "building" not in solve_air and "runway" in solve_air
    assert road == frozenset({"service_road", "service_junction"})
    # the two frames are two populations, and one contains the other
    assert not (solve_air & gs)
    assert "graded_strip" not in solve_air and "graded_strip" not in gs


def test_a_moved_airside_value_is_reported_in_both_frames(tmp_path):
    a, b = _arms(tmp_path, apron_alt_b=10.5, strip_alt_b=20.0)
    res = avd.compare(a, b)
    assert res["frames"]["solve-owned"]["n_moved"] == 1
    assert res["frames"]["solve-owned"]["worst_dz_m"] == pytest.approx(0.5)
    assert res["frames"]["row-side"]["n_moved"] == 1


def test_a_moved_soft_receiver_is_ROW_SIDE_ONLY(tmp_path):
    """``graded_strip`` is airside to the census's row_side and is NOT a
    solve variable — the whole reason two frames are printed."""
    a, b = _arms(tmp_path, apron_alt_b=10.0, strip_alt_b=21.0)
    res = avd.compare(a, b)
    assert res["frames"]["row-side"]["n_moved"] == 1
    assert res["frames"]["solve-owned"]["n_moved"] == 0
    assert res["frames"]["solve-owned"]["worst_dz_m"] == 0.0


def test_a_groundside_move_is_in_neither_frame(tmp_path):
    a, b = _arms(tmp_path, apron_alt_b=10.0, strip_alt_b=20.0)
    res = avd.compare(a, b)          # only the service_road moved
    assert res["frames"]["row-side"]["n_moved"] == 0
    assert res["frames"]["solve-owned"]["n_moved"] == 0


def test_sub_materiality_is_not_a_move(tmp_path):
    a, b = _arms(tmp_path, apron_alt_b=10.005, strip_alt_b=20.0)
    assert avd.compare(a, b)["frames"]["solve-owned"]["n_moved"] == 0
    assert avd.compare(a, b, tol_m=0.001)[
        "frames"]["solve-owned"]["n_moved"] == 1


def test_an_added_vertex_is_never_a_moved_value(tmp_path):
    """The canonical join: a node only one arm carries is ADDED/REMOVED.
    Folding it in would make every densification read as a pull."""
    a = _patch(tmp_path / "a.osm", [
        ("apron", [(1.0, 1.0, 10.0), (1.0, 1.002, 10.0), (1.002, 1.0, 10.0)]),
    ])
    b = _patch(tmp_path / "b.osm", [
        ("apron", [(1.0, 1.0, 10.0), (1.0, 1.001, 10.0), (1.0, 1.002, 10.0),
                   (1.002, 1.0, 10.0)]),
    ])
    f = avd.compare(a, b)["frames"]["solve-owned"]
    assert f["b_only"] == 1 and f["a_only"] == 0
    assert f["n_moved"] == 0 and f["worst_dz_m"] == 0.0


def test_the_road_weld_split_is_the_road_family(tmp_path):
    """A node an apron ring AND a road ring both claim is the channel a
    groundside pull travels; one with no road contact is adoption."""
    shared = (1.0, 1.0)
    a = _patch(tmp_path / "a.osm", [
        ("apron", [shared + (10.0,), (1.0, 1.001, 10.0), (1.001, 1.0, 10.0)]),
        ("service_junction", [shared + (10.0,), (0.999, 1.0, 10.0),
                              (0.999, 1.001, 10.0)]),
    ])
    b = _patch(tmp_path / "b.osm", [
        ("apron", [shared + (10.4,), (1.0, 1.001, 10.0), (1.001, 1.0, 10.0)]),
        ("service_junction", [shared + (10.4,), (0.999, 1.0, 10.0),
                              (0.999, 1.001, 10.0)]),
    ])
    f = avd.compare(a, b)["frames"]["solve-owned"]
    assert f["n_moved"] == 1
    assert f["welded_to_road"] == 1 and f["no_road_contact"] == 0
    assert f["moved"][0]["welded_to_road"] is True


def test_a_node_with_no_altitude_is_reported_never_zero(tmp_path):
    a = _patch(tmp_path / "a.osm", [
        ("apron", [(1.0, 1.0, None), (1.0, 1.001, 10.0), (1.001, 1.0, 10.0)]),
    ])
    b = _patch(tmp_path / "b.osm", [
        ("apron", [(1.0, 1.0, 10.0), (1.0, 1.001, 10.0), (1.001, 1.0, 10.0)]),
    ])
    f = avd.compare(a, b)["frames"]["solve-owned"]
    assert f["n_no_value"] == 1
    assert f["n_moved"] == 0 and f["worst_dz_m"] == 0.0


def test_the_cli_json_IS_the_library_result(tmp_path, capsys):
    a, b = _arms(tmp_path, apron_alt_b=10.5, strip_alt_b=21.0)
    out = tmp_path / "res.json"
    assert avd.main([str(a), str(b), "--json", str(out)]) == 0
    capsys.readouterr()
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(
        json.dumps(avd.compare(a, b)))


def test_a_missing_input_is_REFUSED_not_guessed(tmp_path, capsys):
    a, _b = _arms(tmp_path, apron_alt_b=10.0, strip_alt_b=20.0)
    assert avd.main([str(a), str(tmp_path / "nope.osm")]) == 2
    assert "REFUSED" in capsys.readouterr().err


def test_the_tool_is_in_the_index():
    idx = (ROOT.parent / "tools" / "INDEX.md").read_text(encoding="utf-8")
    assert "Ortho4XP/tools/airside_value_delta.py" in idx, (
        "a tool absent from tools/INDEX.md is treated as absent")


def test_family_split_is_the_laws_and_the_runway_is_senior():
    """Flat-pad spec §4 / C21 (RULINGS 2026-09-30f): every moved node is
    read into ONE family — runway > strip > taxi > apron > other — from the
    law's own role sets (never re-spelled), so the runway bar (0) is read
    off the same pass."""
    avd = _load()
    fams = avd.airside_families()
    assert "runway" in fams["runway"] and "junction" in fams["taxi"]
    assert "apron" in fams["apron"] and "building" not in fams["apron"]
    assert avd.family_of(("junction", "runway"), fams) == "runway"
    assert avd.family_of(("apron", "stub"), fams) == "taxi"
    assert avd.family_of(("apron", "building"), fams) == "apron"
    assert avd.family_of(("building",), fams) == "other"


#: The sweep references the recorded result was read on (``frames.py list
#: SPJC``, lane ``reference``).  They live in the shared data repo, so the
#: twin skips where no corpus is mounted (every CI runner).
_REFERENCE = Path("/Users/noah/XPTerrainBuilderData/.harness/frames/reference")


@pytest.mark.skipif(not (_REFERENCE / "sw1028_SPJC.osm").is_file(),
                    reason="registered SPJC sweep frames not mounted")
def test_the_recorded_SPJC_sweep_result_is_reproduced():
    """Issue #353's acceptance: sw1027 -> sw1028 at SPJC read 5 ROW-SIDE
    movers at 0.05-0.06 m (ribbon-kerb ``graded_strip`` + ``service_road``
    welds, stage-2 settling), solve-owned 0, runway 0, +12 added nodes —
    and a patch against itself reads zero in both frames."""
    a, b = _REFERENCE / "sw1027_SPJC.osm", _REFERENCE / "sw1028_SPJC.osm"
    res = avd.compare(a, b, tol_m=0.02)["frames"]
    row, own = res["row-side"], res["solve-owned"]
    assert row["n_moved"] == 5 and row["welded_to_road"] == 5
    assert sorted(m["dz_m"] for m in row["moved"]) == pytest.approx(
        [0.05, 0.05, 0.06, 0.06, 0.06])
    assert set(row["families"]) == {"strip"}
    assert (row["a_only"], row["b_only"]) == (0, 12)
    assert own["n_moved"] == 0 and (own["a_only"], own["b_only"]) == (0, 0)
    for f in avd.compare(b, b, tol_m=0.0)["frames"].values():
        assert (f["n_moved"], f["a_only"], f["b_only"]) == (0, 0, 0)


# ── --by-ref: the movers PER ROLE AND REF ──────────────────────────────
def _ref_patch(path: Path, ways) -> Path:
    """``ways`` = [(role, ref, [(lat, lon, alt), ...]), ...]."""
    nodes, body, nid, seen = [], [], -1, {}
    for role, ref, pts in ways:
        refs = []
        for la, lo, alt in pts:
            key = (f"{la:.11f}", f"{lo:.11f}")
            if key not in seen:
                seen[key] = nid
                nodes.append(f"<node id='{nid}' lat='{la:.11f}' lon='{lo:.11f}'>"
                             f"<tag k='alt_abs' v='{alt}'/></node>")
                nid -= 1
            refs.append(seen[key])
        nds = "".join(f"<nd ref='{r}'/>" for r in refs + [refs[0]])
        body.append(f"<way id='{nid}'>{nds}<tag k='role' v='{role}'/>"
                    f"<tag k='ref' v='{ref}'/></way>")
        nid -= 1
    path.write_text("<?xml version='1.0'?><osm version='0.6'>" + "".join(nodes)
                    + "".join(body) + "</osm>", encoding="utf-8", newline="")
    return path


def _sq(lat, z):
    return [(lat, 31.0, z), (lat, 31.001, z), (lat + 0.001, 31.001, z)]


def test_by_ref_names_the_shape_that_moved_and_its_levels(tmp_path, capsys):
    a = _ref_patch(tmp_path / "a.osm", [
        ("building", "building26", _sq(30.0, 90.79)),
        ("building", "building7", _sq(30.1, 50.0)),
        ("service_road", "route3", _sq(30.2, 92.0)),
        ("apron", "pav1", _sq(30.3, 80.0))])
    b = _ref_patch(tmp_path / "b.osm", [
        ("building", "building26", _sq(30.0, 93.94)),
        ("building", "building7", _sq(30.1, 50.005)),          # under the floor
        ("apron", "pav1", _sq(30.3, 80.0)),
        ("groundside_pavement", "gap:0", _sq(30.4, 91.0))])
    t = avd.by_ref(a, b, 0.02)
    assert [r["ref"] for r in t["building"]["moved"]] == ["building26"]
    row = t["building"]["moved"][0]
    assert (row["moved"], row["joined"], row["worst_m"]) == (3, 3, 3.15)
    assert row["a_m"] == [90.79, 90.79] and row["b_m"] == [93.94, 93.94]
    # a group one arm lacks is ABSENT, never a mover
    assert t["service_road"] == {"moved": [], "absent_in_b": ["route3"], "absent_in_a": []}
    assert t["groundside_pavement"]["absent_in_a"] == ["gap:0"]
    assert t["apron"]["moved"] == []
    # the CLI's JSON carries the same table
    out = tmp_path / "o.json"
    assert avd.main([str(a), str(b), "--tol", "0.02", "--by-ref", "--json", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["by_ref"] == json.loads(json.dumps(t))
    assert "building26" in capsys.readouterr().out


def test_by_ref_is_in_the_index_row():
    idx = (ROOT.parent / "tools" / "INDEX.md").read_text(encoding="utf-8")
    row = next(ln for ln in idx.splitlines() if "tools/airside_value_delta.py" in ln)
    assert "--by-ref" in row


# ── THE STRUCTURE FRAME (lane pads65) ────────────────────────────────
def _rim_patch(path: Path, rim_z: float, ramp_z: float) -> Path:
    """An apron, a ``tunnel_ramp`` face and a role-less ``structure_rim``
    breakline (``ref`` ``tunnel_wall:3``) — the emitter's own dialect."""
    def nd(i, la, lo, z):
        return (f"<node id='{i}' lat='{la:.11f}' lon='{lo:.11f}'>"
                f"<tag k='alt_abs' v='{z}'/></node>")
    nodes = [nd(-1, 1.0, 1.0, 10.0), nd(-2, 1.0, 1.001, 10.0), nd(-3, 1.001, 1.0, 10.0),
             nd(-4, 2.0, 2.0, ramp_z), nd(-5, 2.0, 2.001, ramp_z), nd(-6, 2.001, 2.0, ramp_z),
             nd(-7, 3.0, 3.0, rim_z), nd(-8, 3.0, 3.001, rim_z), nd(-9, 3.001, 3.0, 3.96)]
    def way(i, refs, tags):
        return (f"<way id='{i}'>" + "".join(f"<nd ref='{r}'/>" for r in refs)
                + "".join(f"<tag k='{k}' v='{v}'/>" for k, v in tags) + "</way>")
    ways = [way(-20, [-1, -2, -3, -1], [("role", "apron")]),
            way(-21, [-4, -5, -6, -4], [("role", "tunnel_ramp")]),
            way(-22, [-7, -8, -9], [("o4_feature", "structure_rim"),
                                    ("ref", "tunnel_wall:3")])]
    path.write_text("<?xml version='1.0'?><osm version='0.6'>" + "".join(nodes)
                    + "".join(ways) + "</osm>", encoding="utf-8", newline="")
    return path


def test_a_fallen_wall_rim_is_a_STRUCTURE_mover_the_solve_owned_frame_cannot_see(tmp_path):
    """MEASURED at OTHH (lane pads65): 28 ``structure_rim`` vertices of three
    ramp portals fell up to 1.31 m and the solve-owned frame read 0 movers —
    a rim breakline carries no role.  The structure frame reads the rim by
    its kind and a structure role's own face beside it."""
    a = _rim_patch(tmp_path / "a.osm", 3.96, 2.60)
    b = _rim_patch(tmp_path / "b.osm", 2.61, 2.60)
    res = avd.compare(a, b, 0.02)
    assert res["frames"]["solve-owned"]["n_moved"] == 0
    st = res["frames"]["structure"]
    assert st["n_both"] == 6 and st["n_moved"] == 2
    assert set(st["families"]) == {"structure_rim:tunnel_wall"}
    assert st["worst_dz_m"] == pytest.approx(1.35)
    b2 = _rim_patch(tmp_path / "b2.osm", 3.96, 2.50)          # the ramp moves
    st2 = avd.compare(a, b2, 0.02)["frames"]["structure"]
    assert set(st2["families"]) == {"tunnel_ramp"} and st2["n_moved"] == 3


def test_the_structure_roles_are_the_laws(tmp_path):
    from auto_patch_v2.law import Law
    from auto_patch_v2.law.tables import is_structure_role
    law = Law.for_airport("XXXX")
    assert is_structure_role(law, "tunnel_ramp") and not is_structure_role(law, "apron")
    got = avd.read_structure(_rim_patch(tmp_path / "a.osm", 3.96, 2.60))
    assert {k for ks, _z in got.values() for k in ks} == {
        "tunnel_ramp", "structure_rim:tunnel_wall"}


def test_the_structure_frame_is_in_the_index_row():
    idx = (ROOT.parent / "tools" / "INDEX.md").read_text(encoding="utf-8")
    row = next(ln for ln in idx.splitlines() if "tools/airside_value_delta.py" in ln)
    assert "STRUCTURE frame" in row
