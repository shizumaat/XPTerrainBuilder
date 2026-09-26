"""The tile-edge skip line says WHOSE decision it was (issue #45).

THE DEFECT (owner report, app 1.0.352, tile +40-077): with "Airports on
a tile edge" set to *Ask me every time* no dialog appeared, and the only
trace was a console line blaming a choice the owner had not made —

    Auto-patch: 1 airport(s) reach into 1 tile(s) this build is not
    building (+40-076); their patches are SKIPPED by your boundary
    choice.

Attributed (lane ``appcopy``, measured on the owner's install): the
app's boundary preflight took 20.1 s for that one tile — seven airports
x three full scans of the ~500 MB Global Airports apt.dat — and batched
over five tiles it exceeded ``BuildModel.boundaryPreflightTimeoutSeconds
= 60``.  The app gave up, enqueued with NO policy, and the engine's
unattended default (skip) applied.  KHZL is class S (crossing 1,353 m
into +40-076), so the dialog WOULD have asked: the answer simply never
arrived.

The cost is fixed at its single site (``apt_dat`` block index,
``tests/auto_patch_v2/test_apt_dat_index.py``).  This file pins the
narration: an unattended default must never be reported as the user's
choice.  Headless, no network, no corpus.
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import O4_Vector_Map as VMAP                                 # noqa: E402
from auto_patch import selection as SEL                      # noqa: E402


def _tile():
    return SimpleNamespace(lat=40, lon=-77)


@pytest.fixture(autouse=True)
def no_process_answer(monkeypatch):
    monkeypatch.setattr(VMAP, "BOUNDARY_POLICY", None, raising=False)


def _setting(monkeypatch, value):
    monkeypatch.setattr(VMAP.CFG, "auto_patch_boundary", value,
                        raising=False)


# ---------------------------------------------------------------------
# 1. WHERE THE ANSWER CAME FROM
# ---------------------------------------------------------------------
@pytest.mark.parametrize("setting,expected", [
    ("Ask", ("skip", "unattended")),
    ("Skip patch", ("skip", "setting")),
    ("Build adjacent", ("neighbour", "setting")),
    ("", ("skip", "unattended")),          # unset reads as the default
])
def test_the_setting_alone_is_never_called_an_answer(monkeypatch, setting,
                                                     expected):
    _setting(monkeypatch, setting)
    assert VMAP.boundary_policy_and_source(_tile()) == expected


def test_an_answer_this_run_is_an_answer(monkeypatch):
    """Whatever the setting says, the dialog's reply wins and IS the
    user's choice."""
    _setting(monkeypatch, "Ask")
    monkeypatch.setattr(VMAP, "BOUNDARY_POLICY", "neighbour", raising=False)
    assert VMAP.boundary_policy_and_source(_tile()) == ("neighbour",
                                                        "answer")

    tile = _tile()
    tile.boundary_policy = "skip"
    assert VMAP.boundary_policy_and_source(tile) == ("skip", "answer")


def test_rederiving_a_tile_does_not_relabel_the_engines_own_default(
        monkeypatch):
    """``derive_auto_patch_selection`` lands the resolved policy ON the
    tile.  A second derivation must not read that back as the user
    having answered."""
    _setting(monkeypatch, "Ask")
    tile = _tile()
    tile.boundary_policy = "skip"
    tile.boundary_policy_source = "unattended"
    assert VMAP.boundary_policy_and_source(tile) == ("skip", "unattended")


def test_the_policy_itself_is_unchanged(monkeypatch):
    """``resolved_boundary_policy`` is the same function it was — this
    fix moves no build decision, only what the build SAYS."""
    for setting in ("Ask", "Skip patch", "Build adjacent", ""):
        _setting(monkeypatch, setting)
        assert (VMAP.resolved_boundary_policy(_tile())
                == VMAP.boundary_policy_and_source(_tile())[0])


# ---------------------------------------------------------------------
# 2. THE LINE
# ---------------------------------------------------------------------
@pytest.fixture
def one_class_s_airport(monkeypatch, tmp_path):
    """+40-077 as the owner built it: KHZL crossing into a cold +40-076."""
    monkeypatch.setattr(VMAP, "resolve_cifp_dir_for_tile",
                        lambda tile: str(tmp_path))
    monkeypatch.setattr(VMAP, "resolved_auto_patch_mode",
                        lambda tile: "ICAO")
    monkeypatch.setattr(VMAP, "manual_patch_icaos", lambda tile: set())
    monkeypatch.setattr(SEL, "resolved_inset_mode", lambda tile: "None")

    def fake_skipper(lat, lon, is_cold=None, reach_m=None, record=None):
        def decide(icao, runways, candidate=None):
            record.append((icao, "S", [(40, -76)], 1353.0))
            return "SKIPPED (+40-076)"
        return decide

    monkeypatch.setattr(SEL, "boundary_skipper", fake_skipper)
    monkeypatch.setattr(
        SEL, "select_patch_airports",
        lambda tile, cifp, mode, manual_icaos=None, boundary=None:
        [boundary("KHZL", {}, None)] and [])
    return _tile()


def test_an_unattended_default_is_not_reported_as_the_users_choice(
        one_class_s_airport, monkeypatch, capsys):
    """THE DEFECT, pinned."""
    _setting(monkeypatch, "Ask")

    VMAP.derive_auto_patch_selection(one_class_s_airport)

    out = capsys.readouterr().out
    assert "reach into 1 tile(s)" in out and "+40-076" in out
    assert "by your boundary choice" not in out
    assert "no answer to the tile-edge question reached this build" in out
    assert "unattended default (skip) applied" in out
    # and it tells the user what to do about it
    assert "build these tiles again" in out
    assert one_class_s_airport.boundary_policy_source == "unattended"


def test_a_remembered_skip_still_reads_as_the_users_choice(
        one_class_s_airport, monkeypatch, capsys):
    _setting(monkeypatch, "Skip patch")

    VMAP.derive_auto_patch_selection(one_class_s_airport)

    out = capsys.readouterr().out
    assert "SKIPPED by your boundary choice." in out
    assert "no answer" not in out
    assert one_class_s_airport.boundary_policy_source == "setting"


def test_an_answered_skip_still_reads_as_the_users_choice(
        one_class_s_airport, monkeypatch, capsys):
    _setting(monkeypatch, "Ask")
    monkeypatch.setattr(VMAP, "BOUNDARY_POLICY", "skip", raising=False)

    VMAP.derive_auto_patch_selection(one_class_s_airport)

    out = capsys.readouterr().out
    assert "SKIPPED by your boundary choice." in out
    assert one_class_s_airport.boundary_policy_source == "answer"


def test_build_adjacent_skips_nothing_and_says_nothing(
        one_class_s_airport, monkeypatch, capsys):
    _setting(monkeypatch, "Build adjacent")

    VMAP.derive_auto_patch_selection(one_class_s_airport)

    out = capsys.readouterr().out
    assert "SKIPPED" not in out
    assert one_class_s_airport.boundary_policy == "neighbour"
