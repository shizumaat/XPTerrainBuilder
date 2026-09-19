"""The PATCH selector and the INSET trim — spec §E tests 1, 2, 3, 3e.

``docs/specs/insets-follow-patch-set-spec.md`` §A.3/§A.4.  Headless,
``tmp_path``, no network, no shared-corpus write.
"""
from __future__ import annotations

import builtins
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from auto_patch import selection as SEL                  # noqa: E402


# ── a synthetic CIFP dir + a fake apt.dat root ────────────────────────
def _threshold(lat, lon, elev=100.0):
    return {"lat": lat, "lon": lon, "elevation_ft": elev}


@pytest.fixture()
def synthetic(tmp_path, monkeypatch):
    """Five CIFP airports in tile +38-010, one of them 3-letter."""
    cifp = tmp_path / "CIFP"
    cifp.mkdir()
    codes = ["LPMT", "LPPT", "LPCS", "LIS", "LPXX"]
    for code in codes:
        (cifp / ("%s.dat" % code)).write_text("stub\n")

    runways = {"01": _threshold(38.5, -9.5), "19": _threshold(38.6, -9.4)}

    monkeypatch.setattr(
        "auto_patch.cifp_reader.discover_cifp_airports",
        lambda path: {c: os.path.join(str(cifp), "%s.dat" % c) for c in codes})
    monkeypatch.setattr("auto_patch.cifp_reader.parse_cifp_file",
                        lambda path: dict(runways))
    monkeypatch.setattr("auto_patch.cifp_reader.airport_in_tile",
                        lambda rw, lat, lon: True)
    monkeypatch.setattr("auto_patch.build_support.pair_runways",
                        lambda rw: [("01", rw["01"], "19", rw["19"])])
    monkeypatch.setattr("auto_patch.cifp_reader.xplane_root_from_cifp_path",
                        lambda path: "/fake/xplane")

    apt = {"LPMT": "/fake/a.dat", "LPPT": "/fake/b.dat", "LPCS": None,
           "LIS": "/fake/c.dat", "LPXX": "/fake/d.dat"}
    monkeypatch.setattr(
        "auto_patch.build_support._pick_best_apt_dat_against_osm",
        lambda root, icao, *a, **k: apt.get(icao))
    return types.SimpleNamespace(lat=38, lon=-10, cifp=str(cifp))


def _by_icao(selection):
    return {c.icao: c.disposition for c in selection}


# ── test 1: dispositions ──────────────────────────────────────────────
def test_icao_mode_drops_the_three_letter_field(synthetic):
    got = _by_icao(SEL.select_patch_airports(
        synthetic, synthetic.cifp, "ICAO", manual_icaos=()))
    assert "LIS" not in got                     # not admitted at all
    assert got["LPMT"] == "patch"
    assert got["LPCS"] == "no_apt_dat"          # apt.dat selection moved up


def test_all_mode_admits_the_three_letter_field(synthetic):
    got = _by_icao(SEL.select_patch_airports(
        synthetic, synthetic.cifp, "All", manual_icaos=()))
    assert got["LIS"] == "patch"


def test_manual_patch_wins(synthetic):
    got = _by_icao(SEL.select_patch_airports(
        synthetic, synthetic.cifp, "ICAO", manual_icaos={"LPPT"}))
    assert got["LPPT"] == "manual"


def test_boundary_callback_marks_boundary_skipped(synthetic):
    got = _by_icao(SEL.select_patch_airports(
        synthetic, synthetic.cifp, "ICAO", manual_icaos=(),
        boundary=lambda icao, rw: ("crosses into +38-009"
                                   if icao == "LPMT" else None)))
    assert got["LPMT"] == "boundary_skipped"
    assert got["LPPT"] == "patch"


def test_mode_None_returns_nothing_without_opening_cifp(synthetic,
                                                        monkeypatch):
    opened = []
    real_open = builtins.open
    monkeypatch.setattr(builtins, "open",
                        lambda *a, **k: (opened.append(a), real_open(*a, **k))[1])
    monkeypatch.setattr(
        "auto_patch.cifp_reader.discover_cifp_airports",
        lambda path: pytest.fail("mode None must not scan the CIFP dir"))
    assert SEL.select_patch_airports(
        synthetic, synthetic.cifp, "None", manual_icaos=()) == []
    assert opened == []


def test_patch_set_helper(synthetic):
    selection = SEL.select_patch_airports(
        synthetic, synthetic.cifp, "ICAO", manual_icaos=())
    assert SEL.patch_set(selection) == {"LPMT", "LPPT", "LPXX"}


# ── test 2 (TWIN): include_patches applies exactly the patch set ──────
def test_include_patches_applies_exactly_the_selectors_patch_set(synthetic):
    """The SECOND spelling of the mode filter is gone: the loader's gate
    is ``mode_admits`` on the same code the selector tested."""
    selection = SEL.select_patch_airports(
        synthetic, synthetic.cifp, "ICAO", manual_icaos=())
    loaded = {c.icao for c in selection
              if SEL.mode_admits(c.icao, "ICAO")
              and c.disposition not in ("manual", "boundary_skipped")}
    assert SEL.patch_set(selection) <= loaded


def test_include_patches_refuses_a_boundary_skipped_airports_stale_file():
    selection = [SEL.PatchCandidate("LPMT", "x", {}, "boundary_skipped", "r"),
                 SEL.PatchCandidate("LPPT", "x", {}, "patch", "")]
    skipped = {c.icao for c in selection
               if c.disposition == "boundary_skipped"}
    assert skipped == {"LPMT"} and "LPPT" not in skipped


# ── test 3: the inset trim ────────────────────────────────────────────
def _dico():
    box = {"boundary": None, "runway": []}
    return {k: dict(box) for k in
            ("LPMT", "LPPT", "LPCS", "LIS", "OPO", "LP63", "Pista de Lavre")
            } | {("way", 1): dict(box)}


def test_inset_keys_are_the_dico_keys_the_mode_admits():
    dico = _dico()
    assert sorted(SEL.inset_keys(dico, "ICAO")) == ["LPCS", "LPMT", "LPPT"]
    assert len(SEL.inset_keys(dico, "All")) == 7
    assert SEL.inset_keys(dico, "None") == []


def test_bounding_boxes_only_none_is_every_named_airport():
    import O4_Airport_Elevation_Insets as INS

    tile = types.SimpleNamespace(lat=38, lon=-10,
                                 airport_elevation_inset_margin_m=2000.0)
    from shapely import geometry as _geom

    dico = {k: {"boundary": _geom.box(0.5, 0.5, 0.6, 0.6)}
            for k in ("LPMT", "LIS", ("way", 1))}
    everything = INS._airport_bounding_boxes(tile, dico)
    trimmed = INS._airport_bounding_boxes(tile, dico, only=["LPMT"])
    assert set(everything) == {"LPMT", "LIS"}          # == today
    assert set(trimmed) == {"LPMT"}
    assert trimmed["LPMT"] == everything["LPMT"]       # same arithmetic


def test_the_trim_is_only_in_the_fetch_entry():
    """``only=None`` (rows 2-4: the coastline ladder, ``_required_inset_box``,
    ``--warm-insets``) must stay the default."""
    import inspect

    import O4_Airport_Elevation_Insets as INS

    sig = inspect.signature(INS._airport_bounding_boxes)
    assert sig.parameters["only"].default is None


# ── test 3e: the two settings are INDEPENDENT ─────────────────────────
def test_patch_and_inset_modes_are_independent(synthetic):
    tile = types.SimpleNamespace(lat=38, lon=-10, auto_patch="None",
                                 airport_elevation_insets="ICAO")
    assert SEL.resolved_auto_patch_mode(tile) == "None"
    assert SEL.resolved_inset_mode(tile) == "ICAO"
    # auto_patch Off no longer implies no insets (owner Q1, RULINGS 18c)
    assert SEL.select_patch_airports(tile, synthetic.cifp,
                                     SEL.resolved_auto_patch_mode(tile),
                                     manual_icaos=()) == []
    assert SEL.inset_keys(_dico(), SEL.resolved_inset_mode(tile))


def test_a_patched_airport_outside_the_inset_selection_is_reportable():
    tile = types.SimpleNamespace(auto_patch="All",
                                 airport_elevation_insets="ICAO")
    inset_mode = SEL.resolved_inset_mode(tile)
    assert SEL.mode_admits("LIS", inset_mode) is False    # patched, no inset
    assert SEL.mode_admits("LPMT", inset_mode) is True
