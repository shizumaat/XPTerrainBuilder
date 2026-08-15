"""Twins for THE SOLVE MODEL — `docs/specs/constructive-solve-spec.md`,
section "Mode plumbing".

No build, no network, no shared repo: cfg files under ``tmp_path`` and the
registry read in-process.  What is under test is the PRECEDENCE (which
source decides, and what the frame then says decided) and the two places
where being wrong is invisible — a per-tile override nobody reads, and a
mode that never reaches the artifact-ledger variant key.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "harness"

sys.path.insert(0, str(ROOT / "src"))

import O4_Cfg_Vars as CV                                     # noqa: E402
import O4_Settings_Model as SM_MODEL                         # noqa: E402
import O4_Solve_Model as SM                                  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def build_mod():
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    return _load("harness_twin_build_solve_model",
                 HARNESS / "build_airport.py")


@pytest.fixture(autouse=True)
def _no_ambient_env(monkeypatch):
    """The developer's own shell must never decide a twin's answer."""
    monkeypatch.delenv(SM.ENV_VAR, raising=False)


# ══════════════════════════════════════════════════════════════════════
# §1 THE REGISTRY KEY — global + per-tile, iterative by default
# ══════════════════════════════════════════════════════════════════════

def test_the_key_is_registered_with_the_specified_values_and_default():
    spec = CV.cfg_vars[SM.CFG_KEY]
    assert spec["type"] is str
    assert tuple(spec["values"]) == SM.MODELS == ("iterative", "constructive")
    # "DEFAULT ``iterative`` until the owner rules after the A/B" — the
    # spec's words.  A default flip is an OWNER decision, not a lane's.
    assert spec["default"] == SM.DEFAULT == "iterative"
    assert set(spec["value_labels"]) == set(SM.MODELS)


def test_the_key_has_both_scopes_like_every_other_tile_var():
    """Global + per-tile comes from ONE fact: membership of
    ``cfg_tile_vars``.  Assert the fact and the two lists it feeds, so a
    later re-grouping that quietly demotes the key to app-only fails
    here rather than in a tile build that ignores its own cfg line."""
    assert SM.CFG_KEY in CV.cfg_tile_vars
    assert SM.CFG_KEY in CV.list_tile_vars
    assert CV.global_prefix + SM.CFG_KEY in CV.cfg_global_tile_vars
    assert CV.global_prefix + SM.CFG_KEY in CV.list_global_tile_vars
    assert SM.CFG_KEY not in CV.list_app_vars


def test_the_qt_settings_window_exposes_it_as_a_two_value_selector():
    setting = SM_MODEL.get_setting(SM.CFG_KEY)
    assert setting.scope == "tile"
    assert tuple(setting.values) == SM.MODELS
    assert setting.default == SM.DEFAULT
    # A label per value: the raw cfg tokens are not a menu.
    assert setting.label_for("constructive") != "constructive"


def test_the_swift_settings_layout_carries_the_same_row():
    """ENGINE OWNS THE FEATURE, the UIs only expose it — so the two
    surfaces must not drift.  The Swift layout names engine cfg vars as
    string literals that appear nowhere in Python; this is the only place
    a rename is caught."""
    layout = (ROOT.parent / "Sources" / "XPTerrainBuilder"
              / "SettingsLayout.swift")
    assert f'SettingItem("{SM.CFG_KEY}"' in layout.read_text()


# ══════════════════════════════════════════════════════════════════════
# §2 THE PRECEDENCE — env > per-tile cfg > global cfg > default
# ══════════════════════════════════════════════════════════════════════

def test_nothing_set_is_the_iterative_default():
    p = SM.provenance(environ={})
    assert (p["solve_model"], p["source"]) == ("iterative", "default")


def test_the_global_cfg_decides_when_it_is_the_only_source():
    p = SM.provenance(environ={}, global_cfg="constructive")
    assert (p["solve_model"], p["source"]) == ("constructive", "global_cfg")


def test_the_per_tile_cfg_outranks_the_global_one():
    p = SM.provenance(environ={}, tile_cfg="constructive",
                      global_cfg="iterative")
    assert (p["solve_model"], p["source"]) == ("constructive", "tile_cfg")


def test_the_env_outranks_both_cfg_scopes():
    """The lane arm's pin.  An A/B must not have to edit a cfg file the
    frame checker then reports as a divergence, nor race the other arm's
    write to it."""
    p = SM.provenance(environ={SM.ENV_VAR: "constructive"},
                      tile_cfg="iterative", global_cfg="iterative")
    assert (p["solve_model"], p["source"]) == ("constructive", "env")


def test_an_empty_value_is_no_value_and_falls_through():
    p = SM.provenance(environ={SM.ENV_VAR: "  "}, tile_cfg="",
                      global_cfg="constructive")
    assert (p["solve_model"], p["source"]) == ("constructive", "global_cfg")


def test_case_quotes_and_whitespace_are_forgiven():
    assert SM.resolve(environ={SM.ENV_VAR: " Constructive "}) == "constructive"
    assert SM.resolve(environ={}, global_cfg="'iterative'") == "iterative"


@pytest.mark.parametrize("source,kwargs", [
    ("env", {"environ": {SM.ENV_VAR: "constructiv"}}),
    ("tile_cfg", {"environ": {}, "tile_cfg": "fast"}),
    ("global_cfg", {"environ": {}, "global_cfg": "true"}),
])
def test_a_typo_raises_instead_of_silently_running_the_other_model(source,
                                                                   kwargs):
    """Defaulting around a typo would run the OTHER model and report its
    numbers under the requested model's name — a mis-attributed A/B arm,
    which no later reader can detect from the artifacts."""
    with pytest.raises(SM.SolveModelError) as exc:
        SM.provenance(**kwargs)
    assert "iterative | constructive" in str(exc.value)
    assert source.split("_")[0] in str(exc.value).lower()


def test_the_provenance_records_every_source_not_just_the_winner():
    p = SM.provenance(environ={SM.ENV_VAR: "constructive"},
                      tile_cfg="iterative")
    assert p["env"] == "constructive"
    assert p["tile_cfg"] == "iterative"
    assert p["global_cfg"] is None
    assert set(p) == {"solve_model", "source", "env", "tile_cfg", "global_cfg"}


def test_is_constructive_agrees_with_current(monkeypatch):
    monkeypatch.setenv(SM.ENV_VAR, "constructive")
    assert SM.current() == "constructive" and SM.is_constructive()
    monkeypatch.setenv(SM.ENV_VAR, "iterative")
    assert SM.current() == "iterative" and not SM.is_constructive()


# ══════════════════════════════════════════════════════════════════════
# §3 THE PER-TILE PUBLISH — a tile's cfg must reach the solve dispatch
# ══════════════════════════════════════════════════════════════════════

class _Tile:
    def __init__(self, model=None):
        if model is not None:
            setattr(self, SM.CFG_KEY, model)


def test_current_reads_the_tiles_own_value():
    assert SM.current(_Tile("constructive")) == "constructive"
    assert SM.current(_Tile()) == "iterative"


def test_tile_scope_publishes_the_tiles_model_to_the_environment():
    """The dispatch site is many frames below the driver and may be in
    another PROCESS (O4_PARALLEL_AIRPORTS).  Without the publish a
    per-tile ``solve_model=constructive`` is read by nobody and the tile
    builds iteratively, silently, with the cfg line sitting right there."""
    import os
    assert SM.ENV_VAR not in os.environ
    with SM.tile_scope(_Tile("constructive")) as scope:
        assert scope.model == "constructive"
        assert os.environ[SM.ENV_VAR] == "constructive"
        assert SM.current() == "constructive"      # what a worker inherits
    assert SM.ENV_VAR not in os.environ            # and it is restored


def test_tile_scope_never_overrides_an_arms_pin(monkeypatch):
    monkeypatch.setenv(SM.ENV_VAR, "iterative")
    with SM.tile_scope(_Tile("constructive")) as scope:
        import os
        assert scope.model == "iterative"          # precedence 1 over 2
        assert os.environ[SM.ENV_VAR] == "iterative"
    import os
    assert os.environ[SM.ENV_VAR] == "iterative"


def test_tile_scope_restores_on_an_exception():
    import os
    with pytest.raises(RuntimeError):
        with SM.tile_scope(_Tile("constructive")):
            raise RuntimeError("the build blew up")
    assert SM.ENV_VAR not in os.environ


# ══════════════════════════════════════════════════════════════════════
# §4 THE HARNESS — the frame record, from the cfg FILES
# ══════════════════════════════════════════════════════════════════════

def _cfg_tree(root: Path, global_value=None, tile_value=None):
    root.mkdir(parents=True, exist_ok=True)
    lines = ["apt_smoothing_pix=8"]
    if global_value is not None:
        lines.append(f"{SM.CFG_KEY}={global_value}")
    (root / "Ortho4XP.cfg").write_text("\n".join(lines) + "\n")
    tile = None
    if tile_value is not None:
        tile = root / "Ortho4XP_+30+031.cfg"
        tile.write_text(f"default_zl=16\n{SM.CFG_KEY}={tile_value}\n")
    return tile


def test_the_frame_record_reads_the_lanes_global_cfg(build_mod, tmp_path):
    _cfg_tree(tmp_path, global_value="constructive")
    rec = build_mod.solve_model_record(tmp_path)
    assert (rec["solve_model"], rec["source"]) == ("constructive",
                                                   "global_cfg")


def test_the_frame_record_prefers_the_provisioned_per_tile_cfg(build_mod,
                                                               tmp_path):
    """A ``--tile`` run's per-tile cfg is provisioned by the build, so the
    frame is re-resolved with it: the same ordering the engine applies."""
    tile = _cfg_tree(tmp_path, global_value="iterative",
                     tile_value="constructive")
    rec = build_mod.solve_model_record(tmp_path, tile_cfg=tile)
    assert (rec["solve_model"], rec["source"]) == ("constructive", "tile_cfg")


def test_the_frame_record_honours_the_env_over_both(build_mod, tmp_path,
                                                    monkeypatch):
    monkeypatch.setenv(SM.ENV_VAR, "iterative")
    tile = _cfg_tree(tmp_path, global_value="constructive",
                     tile_value="constructive")
    rec = build_mod.solve_model_record(tmp_path, tile_cfg=tile)
    assert (rec["solve_model"], rec["source"]) == ("iterative", "env")


def test_a_lane_with_no_solve_model_line_records_the_default(build_mod,
                                                             tmp_path):
    """Every existing cfg in the repo predates the key.  It must resolve,
    not raise, and it must resolve to what those trees have always built."""
    _cfg_tree(tmp_path)
    rec = build_mod.solve_model_record(tmp_path)
    assert (rec["solve_model"], rec["source"]) == ("iterative", "default")


def test_the_harness_and_the_engine_share_ONE_resolver(build_mod, tmp_path):
    """Not a style point: the harness resolves from the cfg FILES (before
    the engine is importable) and the engine from its loaded config, and
    ``build_airport.main`` REFUSES a build whose two answers disagree.
    That refusal is only meaningful if both go through this module."""
    src = (HARNESS / "build_airport.py").read_text()
    assert "import O4_Solve_Model as SM" in src
    assert "SM.provenance(" in src and "SM.current()" in src
    # ...and no second precedence rule anywhere in the harness: the env
    # var never appears as a STRING LITERAL there (prose naming it in a
    # comment is documentation, not a reader).
    assert f'"{SM.ENV_VAR}"' not in src and f"'{SM.ENV_VAR}'" not in src


# ══════════════════════════════════════════════════════════════════════
# §5 MODE ISOLATION — the census and the sidecar take no mode
# ══════════════════════════════════════════════════════════════════════

def test_the_census_and_the_law_library_never_read_the_mode():
    """Spec: "Censuses and sidecars identical in both modes."  The census
    entry, the law library and the patch writer must therefore contain no
    reference to the key at all — a mode-aware census would make the two
    arms incomparable in exactly the way the A/B exists to avoid."""
    for path in (HARNESS / "census.py",
                 ROOT / "tools" / "check_grade.py",
                 ROOT / "src" / "auto_patch" / "layout.py"):
        text = path.read_text()
        assert SM.CFG_KEY not in text, path
        assert SM.ENV_VAR not in text, path
