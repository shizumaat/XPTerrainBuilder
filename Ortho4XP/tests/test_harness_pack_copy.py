"""Lane builds run the drawn test on their OWN products (owner 2026-11-06).

--pack-copy (harness + engine), the #1906 pack_rebake refusal, the one
pre-flight that lists every refresh scope, and the geometry tile DSF.
"""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools", "harness"))

import pack_copy_arm as PCA                                 # noqa: E402
from auto_patch import pack_copy as PC                      # noqa: E402


def test_copy_dir_refused_inside_install(tmp_path):
    inst = tmp_path / "X-Plane 12"
    (inst / "Custom Scenery").mkdir(parents=True)
    with pytest.raises(SystemExit, match="inside the X-Plane"):
        PCA.require_pack_copy_dir(str(inst / "Custom Scenery" / "c"), [str(inst)])
    assert PCA.require_pack_copy_dir(str(tmp_path / "c"), [str(inst)]) == \
        str(tmp_path / "c")


def test_pack_rebake_refused_for_live_pack(tmp_path):
    inst = str(tmp_path / "X-Plane 12")
    live = os.path.join(inst, "Custom Scenery", "Pack A")
    assert PCA.pack_rebake_refusal({"pack_rebake"}, [live], [inst])
    assert "#1906" in PCA.pack_rebake_refusal({"pack_rebake"}, [live], [inst])
    assert PCA.pack_rebake_refusal({"dem"}, [live], [inst]) is None
    assert PCA.pack_rebake_refusal({"pack_rebake"},
                                   [str(tmp_path / "fixture")], [inst]) is None


def test_plan_pack_roots(tmp_path):
    (tmp_path / "o4_v2_rebake_ABCD.json").write_text(json.dumps(
        {"pack_root": "/x/Pack"}))
    (tmp_path / "o4_v2_rebake_BAD.json").write_text("{")
    assert PCA.plan_pack_roots(tmp_path) == ["/x/Pack"]


def test_engine_copy_root_and_clone(tmp_path, monkeypatch):
    pack = tmp_path / "Custom Scenery" / "Pack A"
    (pack / "Earth nav data").mkdir(parents=True)
    (pack / "Earth nav data" / "f.dsf").write_bytes(b"dsf")
    monkeypatch.delenv("O4_PACK_WRITES", raising=False)
    assert PC.ensure_copy(str(pack)) is None
    monkeypatch.setenv("O4_PACK_WRITES", "measure_only")
    assert PC.copy_dir() is None
    monkeypatch.setenv("O4_PACK_WRITES", "copy:" + str(tmp_path / "copy"))
    target = PC.ensure_copy(str(pack))
    assert target == str(tmp_path / "copy" / "Pack A")
    assert (tmp_path / "copy" / "Pack A" / "Earth nav data" / "f.dsf").read_bytes() == b"dsf"
    (pack / "Earth nav data" / "f.dsf").write_bytes(b"owner")
    assert PC.ensure_copy(str(pack)) == target          # cloned once
    assert (tmp_path / "copy" / "Pack A" / "Earth nav data" / "f.dsf").read_bytes() == b"dsf"


def test_arm_pack_copy_sets_env(tmp_path, monkeypatch):
    monkeypatch.delenv("O4_PACK_WRITES", raising=False)
    rec = PCA.arm_pack_copy(str(tmp_path / "c"), "O4_PACK_WRITES")
    assert os.environ["O4_PACK_WRITES"] == "copy:" + str(tmp_path / "c")
    assert rec["dir"] == str(tmp_path / "c") and (tmp_path / "c").is_dir()
    monkeypatch.delenv("O4_PACK_WRITES")


def test_preflight_lists_every_scope():
    import build_airport as BA

    def dem():
        raise BA._scoped_exit(["dem"], "REFUSING: cold dem")

    def osm():
        raise BA._scoped_exit(["osm_layers", "airport_mod_cache"], "REFUSING: osm")

    with pytest.raises(SystemExit) as exc:
        BA.refresh_preflight([dem, lambda: None, osm])
    assert "--refresh-data airport_mod_cache,dem,osm_layers" in str(exc.value.code)
    assert "cold dem" in exc.value.code and "REFUSING: osm" in exc.value.code
    BA.refresh_preflight([lambda: None])                   # nothing: no refusal


def test_no_provider_builds_geometry_tile_dsf():
    import build_airport as BA
    assert BA.GEOMETRY_TEXTURE_MODE in BA.TEXTURE_MODES
    imagery = BA.imagery_capability(
        type("T", (), {"default_website": "", "default_zl": 16,
                       "texture_mode": BA.GEOMETRY_TEXTURE_MODE})(),
        {"action": "derived-from-global-defaults"})
    assert imagery["ok"]          # steps 3 + 4 run: the tile DSF is written
