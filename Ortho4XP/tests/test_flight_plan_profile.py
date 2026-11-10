"""The flight manager's plan reading (spec flight-manager-and-world-20261110
§6.1, lane F1a): alternate, times, speeds and levels from SimBrief (XML and
JSON), altitudes from ``.fms`` and ``.lnmpln``, and the automatic list of
X-Plane's ``Output/FMS plans/`` (owner RULINGS 2026-11-10g).

The SimBrief fixture is SYNTHETIC (spec U7): SimBrief's field names, values
invented.  No network, no real X-Plane folder (``tmp_path`` only).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Flight_Plan as FP  # noqa: E402
import pytest  # noqa: E402

PLANS = os.path.join(os.path.dirname(__file__), "fixtures", "flight_plan")


def _read(name):
    return FP.read_plan_file(os.path.join(PLANS, name))


@pytest.mark.parametrize("name", ["simbrief_ofp_full.xml", "simbrief_ofp_full.json"])
def test_simbrief_alternate_times_and_speed(name):
    plan = _read(name)
    assert [w.ident for w in plan.waypoints] == ["ENGM", "TOC", "TOD", "ENBR"]
    assert [w.t_s for w in plan.waypoints] == [0.0, 900.0, 2400.0, 3300.0]
    assert [w.alt_ft for w in plan.waypoints] == [681.0, 24000.0, 24000.0, 170.0]
    # the first of several planned alternates
    assert plan.alternate == FP.Waypoint("ENZV", 58.8767, 5.63778, 29.0, None)
    assert plan.ete_s == 3300.0
    assert plan.cruise_ms == pytest.approx(280 * 1852 / 3600)
    assert plan.cruise_alt_ft == 24000.0


def test_xml_and_json_answers_read_the_same():
    xml, js = _read("simbrief_ofp_full.xml"), _read("simbrief_ofp_full.json")
    assert xml._replace(source="") == js._replace(source="")


def test_a_plan_without_the_new_fields_says_none():
    plan = _read("simbrief_ofp.xml")
    assert (plan.alternate, plan.ete_s, plan.cruise_ms, plan.cruise_alt_ft) == (
        None, None, None, None)
    # the destination takes no time when the answer has none
    assert plan.waypoints[-1].t_s is None


def test_simbrief_json_refusal_says_why():
    with pytest.raises(FP.FlightPlanError) as exc:
        FP.parse_plan_text('{"fetch": {"status": "Error: Unknown UserID"}}', "")
    assert str(exc.value) == "SimBrief: Unknown UserID"
    with pytest.raises(FP.FlightPlanError):
        FP.parse_simbrief_json("[1, 2]")
    with pytest.raises(FP.FlightPlanError):
        FP.parse_simbrief_json("{not json")


def test_fms_and_lnmpln_altitudes():
    assert [w.alt_ft for w in _read("short_hop_v11.fms").waypoints] == [0.0] * 4
    assert [w.alt_ft for w in _read("transpacific_v3.fms").waypoints] == [
        0.0, 35000.0, 35000.0, 0.0]
    lnm = _read("atlantic.lnmpln")
    assert lnm.cruise_alt_ft == 37000.0
    assert [w.alt_ft for w in lnm.waypoints] == [13.0, 37000.0, 83.0]
    assert all(w.t_s is None for w in lnm.waypoints)


def _fms(folder, name, origin, destination, mtime):
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("I\n1100 Version\nADEP %s\nADES %s\nNUMENR 2\n"
                 "1 %s ADEP 0.000000 47.0 -122.0\n1 %s ADES 0.000000 45.5 -122.5\n"
                 % (origin, destination, origin, destination))
    os.utime(path, (mtime, mtime))
    return path


def test_list_fms_plans_newest_first(tmp_path):
    folder = tmp_path / "Output" / "FMS plans"
    folder.mkdir(parents=True)
    old = _fms(str(folder), "AAAABBBB.fms", "AAAA", "BBBB", 1_700_000_000)
    new = _fms(str(folder), "CCCCDDDD.FMS", "CCCC", "DDDD", 1_700_000_500)
    (folder / "aircraft.xml").write_text("<x/>", encoding="utf-8", newline="\n")
    (folder / "empty.fms").write_text("I\n1100 Version\nNUMENR 0\n", encoding="utf-8", newline="\n")
    (folder / "sub.fms").mkdir()
    rows = FP.list_fms_plans(FP.fms_plans_dir(str(tmp_path)))
    assert rows == [
        {"path": new, "name": "CCCCDDDD", "origin": "CCCC", "destination": "DDDD",
         "modified_at": 1_700_000_500},
        {"path": old, "name": "AAAABBBB", "origin": "AAAA", "destination": "BBBB",
         "modified_at": 1_700_000_000},
    ]
    assert FP.list_fms_plans(str(tmp_path / "missing")) == []


def test_the_commands(tmp_path):
    from o4_engine import flight_commands as FC

    folder = tmp_path / "Output" / "FMS plans"
    folder.mkdir(parents=True)
    path = _fms(str(folder), "AAAABBBB.fms", "AAAA", "BBBB", 1_700_000_000)
    assert [r["path"] for r in FC.flight_plans_list(str(tmp_path))["plans"]] == [path]
    assert FC.flight_plans_list("") == {"plans": []}
    wire = FC.flight_plan_read(os.path.join(PLANS, "simbrief_ofp_full.xml"))
    assert (wire["origin"], wire["destination"], wire["ete_s"]) == ("ENGM", "ENBR", 3300.0)
    assert wire["alternate"]["ident"] == "ENZV"
    assert wire["waypoints"][1] == {"ident": "TOC", "lat": 60.3, "lon": 9.8,
                                    "alt_ft": 24000.0, "t_s": 900.0}
    assert wire["route_km"] > 0
    with pytest.raises(FP.FlightPlanError):
        FC.flight_plan_read(str(tmp_path / "nothing.fms"))


def test_the_command_table_serves_them():
    from o4_engine import flight_commands as FC

    table = FC.flight_plan_handlers()
    assert set(table) == {"flight_plans_list", "flight_plan_read"}
    import inspect

    from o4_engine import jsonl
    assert "flight_plan_handlers()" in inspect.getsource(jsonl._build_handlers)


WIRE = os.path.join(os.path.dirname(__file__), "fixtures", "flight_plan_wire.json")


def _wire_doc():
    from o4_engine import flight_commands as FC

    def plan(name):
        return {**FC.flight_plan_read(os.path.join(PLANS, name)), "source": name}
    rows = [{"path": "/X-Plane 12/Output/FMS plans/%s.fms" % n, "name": n,
             "origin": n[:4], "destination": n[4:], "modified_at": t}
            for n, t in (("CCCCDDDD", 1_700_000_500), ("AAAABBBB", 1_700_000_000))]
    return {"_comment": "Written by tests/test_flight_plan_profile.py "
                        "(REGENERATE_FLIGHT_WIRE=1); decoded by "
                        "Tests/SceneryKitTests/FlightWireTests.swift.",
            "flight_plans_list": {"plans": rows},
            "flight_plan_read": plan("simbrief_ofp_full.xml"),
            "flight_plan_read_fms": plan("short_hop_v11.fms")}


def test_the_wire_fixture():
    """The Swift twin decodes what the engine answers (one shared file)."""
    import json

    doc = json.loads(json.dumps(_wire_doc()))
    if os.environ.get("REGENERATE_FLIGHT_WIRE"):
        with open(WIRE, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
    with open(WIRE, encoding="utf-8") as fh:
        assert json.load(fh) == doc
