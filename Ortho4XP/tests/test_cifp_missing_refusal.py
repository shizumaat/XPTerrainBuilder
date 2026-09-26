"""The CIFP-missing auto_patch skip is FATAL, not a warning (beta plan §1 B2).

Until 2026-09-17 ``run_auto_patch_generation`` printed a loud banner when
``auto_patch`` was enabled but no CIFP path resolved, then carried on: the
tile finished with exit 0 and every runway, taxiway and apron draped over
the raw DEM.  It now raises through the EXISTING
``AutoPatchBuildFailure`` path (step 1 returns 0 → ``BuildDone(ok=False)``
→ nonzero exit), with no new protocol event.  An explicitly disabled
auto-patch still builds.

Headless: no network and no X-Plane install required.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Vector_Map as VMAP  # noqa: E402
import O4_Settings_Model as SETTINGS  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402
from auto_patch.driver import AutoPatchBuildFailure  # noqa: E402


class _Recorder:
    """Stand-in for AUTOPATCH.generate_auto_patches."""

    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))


def _stub_generate(monkeypatch):
    """Keep the log file untouched and record generation calls.

    The road-feed schema pre-check (``ensure_auto_patch_road_feeds``,
    RULINGS 2026-09-17ad / the +46+006 neighbour-feed abort) runs on the
    generation path just before ``generate_auto_patches`` and reads —
    and may re-derive — the shared OSM corpus for nine tiles.  Headless
    here: it is recorded, never run (#35: the bare ``SimpleNamespace``
    tile had no ``.lat`` for it to read), and answers with an empty
    :class:`~O4_Vector_Map.RoadFeedPrecheck` — nothing derived, nothing
    left stale.
    """
    monkeypatch.setattr(UI, "log", False)
    recorder = _Recorder()
    monkeypatch.setattr(VMAP.AUTOPATCH, "generate_auto_patches", recorder)
    recorder.road_feed_tiles = []

    def _record_road_feeds(tile):
        # The stub must return what the real pre-check returns: the
        # caller reads ``.stale`` off it and hands it to
        # ``generate_auto_patches`` (issue #24).  Nothing is stale here —
        # nothing was read.
        recorder.road_feed_tiles.append(tile)
        return VMAP.RoadFeedPrecheck([], [])

    monkeypatch.setattr(VMAP, "ensure_auto_patch_road_feeds",
                        _record_road_feeds)
    return recorder


def _no_cifp(monkeypatch):
    monkeypatch.setattr(VMAP.CFG, "cifp_data_path", "")
    monkeypatch.setattr(VMAP.CFG, "custom_scenery_dir", "")


# ── the engine refusal ────────────────────────────────────────────────

def test_refuses_when_cifp_missing(monkeypatch):
    recorder = _stub_generate(monkeypatch)
    _no_cifp(monkeypatch)
    tile = types.SimpleNamespace(auto_patch="All")

    with pytest.raises(AutoPatchBuildFailure) as excinfo:
        VMAP.run_auto_patch_generation(tile, None, {})

    assert recorder.calls == []
    assert "cifp_data_path" in str(excinfo.value)
    assert excinfo.value.failures[0]["stage"] == "config"


def test_refuses_when_cifp_path_is_not_a_directory(monkeypatch, tmp_path):
    """A typo must refuse, never silently fall back to another corpus."""
    recorder = _stub_generate(monkeypatch)
    monkeypatch.setattr(VMAP.CFG, "cifp_data_path", str(tmp_path / "nope"))
    monkeypatch.setattr(VMAP.CFG, "custom_scenery_dir", "")
    tile = types.SimpleNamespace(auto_patch="ICAO")

    with pytest.raises(AutoPatchBuildFailure) as excinfo:
        VMAP.run_auto_patch_generation(tile, None, {})

    assert recorder.calls == []
    assert "is not a directory" in str(excinfo.value)


@pytest.mark.parametrize("auto_patch", ["None", False])
def test_builds_when_auto_patch_off(monkeypatch, capsys, auto_patch):
    """An explicit auto_patch=None config still builds — no refusal."""
    recorder = _stub_generate(monkeypatch)
    _no_cifp(monkeypatch)
    tile = types.SimpleNamespace(auto_patch=auto_patch)

    VMAP.run_auto_patch_generation(tile, None, {})

    assert recorder.calls == []
    assert "WARNING" not in capsys.readouterr().out


def test_generates_when_cifp_present(monkeypatch, capsys, tmp_path):
    recorder = _stub_generate(monkeypatch)
    monkeypatch.setattr(VMAP.CFG, "cifp_data_path", str(tmp_path))
    monkeypatch.setattr(VMAP.CFG, "custom_scenery_dir", "")
    tile = types.SimpleNamespace(auto_patch="All")

    VMAP.run_auto_patch_generation(tile, None, {})

    assert len(recorder.calls) == 1
    assert recorder.calls[0][0][1] == str(tmp_path)
    # The feeds are made current BEFORE generation reads them.
    assert recorder.road_feed_tiles == [tile]
    assert "WARNING" not in capsys.readouterr().out


def test_autodetects_cifp_under_custom_scenery(monkeypatch, tmp_path):
    """An EMPTY cifp_data_path still resolves X-Plane's stock corpus."""
    recorder = _stub_generate(monkeypatch)
    root = tmp_path / "X-Plane 12"
    (root / "Custom Scenery").mkdir(parents=True)
    cifp = root / "Resources" / "default data" / "CIFP"
    cifp.mkdir(parents=True)
    monkeypatch.setattr(VMAP.CFG, "cifp_data_path", "")
    monkeypatch.setattr(
        VMAP.CFG, "custom_scenery_dir", str(root / "Custom Scenery"))
    tile = types.SimpleNamespace(auto_patch="ICAO")

    VMAP.run_auto_patch_generation(tile, None, {})

    assert len(recorder.calls) == 1
    assert recorder.calls[0][0][1] == str(cifp)


# ── the shared predicate (one spelling, four call sites) ───────────────

def test_resolve_cifp_dir_prefers_navigraph(tmp_path):
    root = tmp_path / "X-Plane 12"
    (root / "Custom Scenery").mkdir(parents=True)
    (root / "Resources" / "default data" / "CIFP").mkdir(parents=True)
    navigraph = root / "Custom Data" / "CIFP"
    navigraph.mkdir(parents=True)

    assert SETTINGS.resolve_cifp_dir(
        "", str(root / "Custom Scenery")) == str(navigraph)


def test_cifp_refusal_reason_none_when_auto_patch_off():
    assert SETTINGS.cifp_refusal_reason("", "", "None") is None


def test_cifp_refusal_reason_names_the_key():
    reason = SETTINGS.cifp_refusal_reason("", "", "ICAO")
    assert reason is not None
    assert "cifp_data_path" in reason
    assert "auto_patch=None" in reason


def test_xplane_install_problem(tmp_path):
    assert SETTINGS.xplane_install_problem("") is not None
    assert SETTINGS.xplane_install_problem(str(tmp_path / "gone")) is not None

    root = tmp_path / "X-Plane 12"
    (root / "Custom Scenery").mkdir(parents=True)
    # Custom Scenery alone is NOT enough: the stock CIFP corpus is what
    # makes auto-patching possible without a Navigraph subscription.
    problem = SETTINGS.xplane_install_problem(str(root))
    assert problem is not None and "CIFP" in problem

    (root / "Resources" / "default data" / "CIFP").mkdir(parents=True)
    assert SETTINGS.xplane_install_problem(str(root)) is None
