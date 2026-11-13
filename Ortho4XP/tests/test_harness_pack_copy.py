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

import pack_copy_arm as PCA  # noqa: E402
from auto_patch import pack_copy as PC  # noqa: E402


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
        {"pack_root": "/x/Pack"}), encoding="utf-8", newline="\n")
    (tmp_path / "o4_v2_rebake_BAD.json").write_text("{", encoding="utf-8", newline="\n")
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
    # setenv, not delenv(raising=False): it records the variable's state
    # even when absent, so the teardown removes what arm_pack_copy wrote.
    # (A closing monkeypatch.delenv recorded the ARMED value and restored
    # it: every later test on the worker saw a pack copy armed, and its
    # pack writes were refused, #2041.)
    monkeypatch.setenv("O4_PACK_WRITES", "")
    rec = PCA.arm_pack_copy(str(tmp_path / "c"), "O4_PACK_WRITES")
    assert os.environ["O4_PACK_WRITES"] == "copy:" + str(tmp_path / "c")
    assert rec["dir"] == str(tmp_path / "c") and (tmp_path / "c").is_dir()


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


# ── #2041: a pack-copy build never writes the installed pack ──────────────

def _symlinked_install(tmp_path):
    """An install whose pack is a SYMLINK into a library (the Orbx case),
    with a symlinked folder inside it too."""
    lib = tmp_path / "Library" / "Pack T"
    (lib / "Earth nav data").mkdir(parents=True)
    (lib / "Earth nav data" / "f.dsf").write_bytes(b"dsf")
    shared = tmp_path / "Library" / "shared"
    shared.mkdir()
    (shared / "o.obj").write_bytes(b"obj")
    (lib / "objects").mkdir()
    os.symlink(shared, lib / "objects" / "tile")
    scen = tmp_path / "X-Plane 12" / "Custom Scenery"
    scen.mkdir(parents=True)
    os.symlink(lib, scen / "Pack T")
    return scen / "Pack T", tmp_path / "Library"


def _snapshot(tree):
    return sorted((str(p), p.stat().st_mtime_ns) for p in tree.rglob("*"))


def test_symlinked_pack_copy_is_a_real_tree(tmp_path, monkeypatch):
    pack, lib = _symlinked_install(tmp_path)
    before = _snapshot(lib)
    monkeypatch.setenv("O4_PACK_WRITES", "copy:" + str(tmp_path / "copy"))
    target = PC.ensure_copy(str(pack))
    assert not os.path.islink(target)
    assert PC._links_in(target) == []
    assert os.path.realpath(target).startswith(
        os.path.realpath(tmp_path / "copy") + os.sep)
    assert open(os.path.join(target, "objects", "tile", "o.obj"),
                "rb").read() == b"obj"
    # every engine writer passes write_guard(root) as allow_live_install
    from auto_patch_v2.airport import placement_write as PW
    body = type("F", (), {"resource": "objects/tile/o__b0.obj",
                          "text": "I\n800\nOBJ\n"})()
    PW.write_files(target, [body], allow_live_install=PC.write_guard(target))
    assert os.path.isfile(os.path.join(target, "objects", "tile", "o__b0.obj"))
    assert _snapshot(lib) == before                  # the install untouched


def test_write_guard_refuses_install_roots(tmp_path, monkeypatch):
    pack, lib = _symlinked_install(tmp_path)
    monkeypatch.delenv("O4_PACK_WRITES", raising=False)
    assert PC.write_guard(str(pack)) is True          # the app: as before
    monkeypatch.setenv("O4_PACK_WRITES", "copy:" + str(tmp_path / "copy"))
    with pytest.raises(PermissionError, match="#2041"):
        PC.write_guard(str(pack))                     # the installed pack
    # the pre-#2041 copy: a LINK to the installed pack inside the copy dir
    (tmp_path / "copy").mkdir()
    stale = tmp_path / "copy" / "Pack T"
    os.symlink(pack, stale)
    with pytest.raises(PermissionError, match="#2041"):
        PC.write_guard(str(stale))
    target = PC.ensure_copy(str(pack))                # replaced by a real tree
    assert target == str(stale) and not os.path.islink(target)
    assert PC.write_guard(target) is True


def test_engine_pack_writers_pass_the_copy_guard():
    """Every engine pack write decides ``allow_live_install`` through
    ``pack_copy`` (``write_guard`` or ``copy_dir()``), never a literal
    ``True``: a literal is a write that a pack-copy build cannot stop."""
    import re
    src = os.path.join(HERE, "..", "src")
    bad = []
    for root, _dirs, names in os.walk(src):
        if os.sep + "auto_patch_v2" in root:          # the writers themselves
            continue
        for name in names:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            for m in re.finditer(r"allow_live_install\s*=\s*(\S+)", text):
                if not re.match(r"_copy\.(write_guard|copy_dir)\(", m.group(1)):
                    line = text.count("\n", 0, m.start()) + 1
                    bad.append(f"{os.path.relpath(path, src)}:{line}: "
                               f"{m.group(0)}")
    assert not bad, "pack writes that bypass pack_copy (#2041):\n" + "\n".join(bad)
