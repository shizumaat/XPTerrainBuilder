"""PAD BINDING ROUTES — the sidecar, the single implementation, the tool.

Spec: ``docs/specs/pad-binding-routes-spec.md`` §3 twins 2, 4 and 5.  The
ENGINE CAPTURE twin (§3.1) lives with its fixture family in
``tests/test_seat_band_and_coupler.py``; the KEY-CLASSIFICATION twin (§3.3)
already exists in ``tests/test_harness.py`` and is untouched.

WHAT THIS ROUND IS.  Answering "show me the calculated route for
building25's pad at HECA" used to require a full in-process rebuild,
because the reach band is live solver state and ``trace_reach_route.py``
deliberately reads the LIVE band (a re-derivation offline is a second
engine, and being one is how that tool became wrong once already).  So the
engine PUBLISHES, at emit time, the route evidence it already computed,
and the tool gains a mode that renders the published record.  Publication
only — no law changes, no second engine.

Hermetic: ``tmp_path``, hand-written sidecars, no build, no network.
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(scope="module")
def trace():
    """``tools/trace_reach_route.py``, loaded by path.

    Loaded as a MODULE rather than shelled out so the refusals below are
    asserted on the real ``SystemExit`` messages rather than on stderr
    scraping — and so twin 4 can compare function objects."""
    path = ROOT / "tools" / "trace_reach_route.py"
    spec = importlib.util.spec_from_file_location("trace_reach_route_twin",
                                                  path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════════════════════
# §3.2 THE SIDECAR WRITE TWIN
# ══════════════════════════════════════════════════════════════════════

def _sidecar(layout, tmp_path):
    p = tmp_path / "p.osm"
    layout._write_axes_sidecar(str(p))
    return json.loads((tmp_path / "p.osm.axes.json").read_text())


def test_the_sidecar_publishes_pad_binding_routes_unconditionally(tmp_path):
    """A layout that never solved carries no ``_pad_binding_routes`` at
    all, and the sidecar still publishes the key — in the §1.6 DEGRADED
    shape.  Three states must stay distinguishable to a reader:
    ``nodespace: null`` (the capture could not run), a stamped nodespace
    with ``records: []`` (it ran, no pads), and an ABSENT key (the patch
    predates the publication)."""
    from auto_patch.layout import PavementLayout
    data = _sidecar(PavementLayout(icao="ZZZZ", anchor=(30.0, 31.0)),
                    tmp_path)
    assert "pad_binding_routes" in data, (
        "the key is written unconditionally — an absent key must mean "
        "'predates the publication', and nothing else")
    assert data["pad_binding_routes"] == {"nodespace": None, "records": []}


def test_the_sidecar_carries_the_capture_verbatim(tmp_path):
    from auto_patch.layout import PavementLayout
    lay = PavementLayout(icao="ZZZZ", anchor=(30.0, 31.0))
    box = {"nodespace": "n=17",
           "records": [{"pad": "building25", "seat_m": 22.5,
                        "off_network": False,
                        "sides": {"ceiling": {"anchor_node": 3}}}]}
    lay._pad_binding_routes = box
    assert _sidecar(lay, tmp_path)["pad_binding_routes"] == box


def test_the_key_is_classified_as_evidence():
    """§1.5.  EVIDENCE, deliberately: the census REPORTS the routes and
    adjudicates nothing from them.  (``tests/test_harness.py`` is the twin
    that makes an unclassified key fail; this states the SIDE it is on.)"""
    spec = importlib.util.spec_from_file_location(
        "pad_routes_twin_check_grade", ROOT / "tools" / "check_grade.py")
    cg = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cg
    spec.loader.exec_module(cg)
    assert "pad_binding_routes" in cg.SIDECAR_EVIDENCE_KEYS
    assert "pad_binding_routes" not in cg.SIDECAR_LAW_KEYS


# ══════════════════════════════════════════════════════════════════════
# §3.4 THE SINGLE-IMPLEMENTATION TWIN
# ══════════════════════════════════════════════════════════════════════

def test_the_tool_has_no_private_walk(trace):
    """One walk, two consumers.  The tool's ``walk_to_anchor`` /
    ``spine_edge_budget`` ARE production's objects — not copies, not
    wrappers — and no private ``def`` survives in the tool.

    This is the ruling ``7e90032`` clause with teeth: a forked near-fit is
    a second opinion about which route bound a node, and the engine's
    published record and the tool's report would then disagree about the
    same build."""
    from auto_patch.elevation_per_surface import building_feasibility as BF
    assert trace.walk_to_anchor is BF.walk_to_anchor
    assert trace.spine_edge_budget is BF.spine_edge_budget
    src = inspect.getsource(trace)
    assert "def _walk_to_anchor" not in src
    assert "def _edge_budget" not in src
    assert "walk_to_anchor" in BF.__all__
    assert "spine_edge_budget" in BF.__all__


def test_the_sidecar_mode_does_not_import_the_solver():
    """§2.1's hard property: ``--from-sidecar`` reads JSON and writes a
    render.  Importing the tool must not drag the engine in — a mode that
    needs the solver importable is a mode that cannot run beside a broken
    tree, which is exactly when a reader wants it."""
    import subprocess
    code = ("import sys; sys.path.insert(0, %r);"
            "import importlib.util as u;"
            "s = u.spec_from_file_location('t', %r);"
            "m = u.module_from_spec(s); s.loader.exec_module(m);"
            "print('auto_patch.elevation_per_surface.building_feasibility'"
            " in sys.modules)"
            % (str(ROOT / "src"),
               str(ROOT / "tools" / "trace_reach_route.py")))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True)
    assert out.stdout.strip() == "False", out.stderr


# ══════════════════════════════════════════════════════════════════════
# §3.5 THE TOOL SIDECAR-MODE TWIN — hermetic
# ══════════════════════════════════════════════════════════════════════

#: One pad, two sides, one route each — the shape §1.4 publishes.
_RECORD = {
    "pad": "building25",
    "seat_m": 22.5,
    "off_network": False,
    "sides": {
        "ceiling": {"anchor_node": 41, "anchor_ll": [30.1, 31.1],
                    "anchor_value_m": 24.0, "route_budget_m": 1.25,
                    "plan_len_m": 250.0, "route_complete": True,
                    "route_ll": [[30.1, 31.1], [30.11, 31.12],
                                 [30.12, 31.13]],
                    "frontage_ll": [30.12, 31.13],
                    "band_floor_m": 21.0, "band_ceiling_m": 25.25},
        "floor": {"anchor_node": 77, "anchor_ll": [30.2, 31.2],
                  "anchor_value_m": 20.0, "route_budget_m": 0.75,
                  "plan_len_m": 150.0, "route_complete": False,
                  "route_ll": [[30.2, 31.2], [30.15, 31.16]],
                  "frontage_ll": [30.12, 31.14],
                  "band_floor_m": 19.25, "band_ceiling_m": 26.0},
    },
}
_OTHER = {"pad": "building9", "seat_m": 8.0, "off_network": True}


def _write_sidecar(tmp_path, box, name="HECA_auto.patch.osm"):
    patch = tmp_path / name
    patch.write_text("<osm version='0.6'></osm>")
    (tmp_path / (name + ".axes.json")).write_text(json.dumps(
        {"anchor": [30.0, 31.0], "ruleset": "icao",
         **({} if box is None else {"pad_binding_routes": box})}))
    return patch


def _run(trace, monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["trace_reach_route.py"] + argv)
    return trace.main()


def test_the_kml_render_carries_both_routes(trace, tmp_path, monkeypatch,
                                            capsys):
    """(a) the KML carries both route coordinate strings and the anchor
    placemark fields — the answer, on a map, with no build."""
    patch = _write_sidecar(tmp_path, {"nodespace": "n=1200",
                                      "records": [_RECORD, _OTHER]})
    out = tmp_path / "routes.kml"
    assert _run(trace, monkeypatch,
                ["--from-sidecar", str(patch), "--out", str(out)]) == 0
    kml = out.read_text()
    # every hop of every chain, in KML's own lon,lat,0 spelling
    for (la, lo) in (_RECORD["sides"]["ceiling"]["route_ll"]
                     + _RECORD["sides"]["floor"]["route_ll"]):
        assert f"{lo:.7f},{la:.7f},0" in kml
    assert "anchor node 41" in kml and "anchor node 77" in kml
    assert "complete=True" in kml and "complete=False" in kml
    assert "building25" in kml
    # the off-network pad renders as a single placemark SAYING SO
    assert "building9 OFF-NETWORK" in kml
    # ... and the report names the incompleteness rather than hiding it
    assert "ROUTE INCOMPLETE" in capsys.readouterr().out


def test_the_osm_render_carries_the_tags(trace, tmp_path, monkeypatch):
    """(b) the OSM ways carry the §2.2 tags, with negative ids."""
    patch = _write_sidecar(tmp_path, {"nodespace": "n=1200",
                                      "records": [_RECORD]})
    out = tmp_path / "routes.osm"
    assert _run(trace, monkeypatch,
                ["--from-sidecar", str(patch), "--out", str(out)]) == 0
    osm = out.read_text()
    for tag in ('k="pad_binding_route" v="ceiling"',
                'k="pad_binding_route" v="floor"',
                'k="pad" v="building25"',
                'k="anchor_node" v="41"',
                'k="route_budget_m" v="1.2500"',
                'k="plan_len_m" v="250.0000"',
                'k="route_complete" v="true"',
                'k="route_complete" v="false"',
                'k="band_floor_m" v="21.0000"',
                'k="band_ceiling_m" v="25.2500"'):
        assert tag in osm, tag
    assert '<node id="-1"' in osm and '<way id="-1"' in osm
    # a VIEWER artifact, never scenery: no sidecar is written beside it
    assert not (tmp_path / "routes.osm.axes.json").exists()


def test_a_patch_without_the_key_is_refused_by_name(trace, tmp_path,
                                                    monkeypatch):
    """(c) the refusal names the FACT and the REMEDY.  A render that just
    came out empty would read as "this pad has no route", which is a
    different and false statement."""
    patch = _write_sidecar(tmp_path, None)
    with pytest.raises(SystemExit) as exc:
        _run(trace, monkeypatch, ["--from-sidecar", str(patch),
                                  "--out", str(tmp_path / "r.kml")])
    assert "predates route publication" in str(exc.value)
    assert "rebuild" in str(exc.value).lower()


def test_the_ref_filter_is_honoured(trace, tmp_path, monkeypatch, capsys):
    """(d) ``--ref`` filters the published pads; a ref that matches nothing
    NAMES the refs that exist rather than rendering silence."""
    patch = _write_sidecar(tmp_path, {"nodespace": "n=1200",
                                      "records": [_RECORD, _OTHER]})
    out = tmp_path / "one.kml"
    assert _run(trace, monkeypatch,
                ["--from-sidecar", str(patch), "--ref", "building25",
                 "--out", str(out)]) == 0
    kml = out.read_text()
    assert "building25" in kml and "building9" not in kml

    with pytest.raises(SystemExit) as exc:
        _run(trace, monkeypatch, ["--from-sidecar", str(patch),
                                  "--ref", "building404",
                                  "--out", str(tmp_path / "none.kml")])
    assert "building25" in str(exc.value) and "building9" in str(exc.value)


def test_a_patch_osm_out_path_is_refused(trace, tmp_path, monkeypatch):
    """(e) the patch loader globs ``*.patch.osm``.  A render that can be
    loaded as scenery is a render that eventually will be, so the writer
    refuses the name — this is a viewer artifact."""
    patch = _write_sidecar(tmp_path, {"nodespace": "n=1200",
                                      "records": [_RECORD]})
    with pytest.raises(SystemExit) as exc:
        _run(trace, monkeypatch, ["--from-sidecar", str(patch), "--out",
                                  str(tmp_path / "x.patch.osm")])
    assert "patch.osm" in str(exc.value)
    assert not (tmp_path / "x.patch.osm").exists()


def test_a_null_nodespace_renders_nothing_and_says_why(trace, tmp_path,
                                                       monkeypatch, capsys):
    """§2.1: ``nodespace: null`` is the capture-unavailable FACT.  Nothing
    is rendered, and the reason is printed — an empty KML would be the
    silence this whole round exists to remove."""
    patch = _write_sidecar(tmp_path, {"nodespace": None, "records": []})
    out = tmp_path / "r.kml"
    assert _run(trace, monkeypatch,
                ["--from-sidecar", str(patch), "--out", str(out)]) == 0
    assert not out.exists()
    assert "CAPTURE COULD NOT RUN" in capsys.readouterr().out


def test_an_empty_record_list_says_so(trace, tmp_path, monkeypatch, capsys):
    patch = _write_sidecar(tmp_path, {"nodespace": "n=1200", "records": []})
    assert _run(trace, monkeypatch,
                ["--from-sidecar", str(patch),
                 "--out", str(tmp_path / "r.kml")]) == 0
    assert "recorded no pads" in capsys.readouterr().out


def test_the_sidecar_mode_refuses_the_build_modes(trace, tmp_path,
                                                  monkeypatch):
    """Mutually exclusive with the build modes (§2.1) — and the refusal
    says which flag conflicted, so the reader is not left guessing which
    half of their command line was ignored."""
    patch = _write_sidecar(tmp_path, {"nodespace": "n=1", "records": []})
    with pytest.raises(SystemExit) as exc:
        _run(trace, monkeypatch, ["HECA", "--from-sidecar", str(patch)])
    assert "ICAO" in str(exc.value)
    with pytest.raises(SystemExit) as exc:
        _run(trace, monkeypatch, ["--from-sidecar", str(patch),
                                  "--inverted-pairs"])
    assert "--inverted-pairs" in str(exc.value)


def test_the_axes_json_path_is_accepted_directly(trace, tmp_path,
                                                 monkeypatch):
    """§2.1: both spellings, because both are what a reader has in hand."""
    patch = _write_sidecar(tmp_path, {"nodespace": "n=1200",
                                      "records": [_RECORD]})
    out = tmp_path / "r.kml"
    assert _run(trace, monkeypatch,
                ["--from-sidecar", str(patch) + ".axes.json",
                 "--out", str(out)]) == 0
    assert "building25" in out.read_text()
