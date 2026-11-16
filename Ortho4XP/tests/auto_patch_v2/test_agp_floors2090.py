"""#2090 spec Part D: an ``.agp`` piece's floors are read once per pack
version through ``<mod cache>/<pack>/o4_agp_floors.cache``
(``airport/agp_floors``): a hit, a hit where only the mtime moved and the
content did not, a miss where the content changed, and an unwritable cache
folder that just computes."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE / "tools"))

from auto_patch_v2.airport import agp_floors as AF  # noqa: E402


def _quad_obj(path: Path, y: float) -> None:
    pts = [(-5.0, y, -5.0), (5.0, y, -5.0), (5.0, y, 5.0), (-5.0, y, 5.0)]
    vt = "".join(f"VT {x} {yy} {z} 0 1 0 0 0\n" for x, yy, z in pts)
    idx = [0, 1, 2, 0, 2, 3]
    path.write_text(f"I\n800\nOBJ\n\nTEXTURE x.png\nPOINT_COUNTS 4 0 0 6\n{vt}"
                    + "".join(f"IDX {i}\n" for i in idx) + "TRIS 0 6\n",
                    encoding="utf-8", newline="\n")


def _pack(tmp_path: Path) -> tuple[Path, Path, Path]:
    pack = tmp_path / "Custom Scenery" / "Some Pack"
    (pack / "Earth nav data").mkdir(parents=True)
    (pack / "Objects").mkdir()
    obj = pack / "Objects" / "piece.obj"
    _quad_obj(obj, 3.45)
    mc = tmp_path / "Airport_mod_cache"
    mc.mkdir()
    return pack, obj, mc


def _count_parses(monkeypatch) -> list:
    calls: list = []
    real = AF._parse_floors

    def spy(path, flat):
        calls.append(path)
        return real(path, flat)
    monkeypatch.setattr(AF, "_parse_floors", spy)
    return calls


def test_a_second_read_is_a_hit(tmp_path, monkeypatch):
    AF._forget()
    pack, obj, mc = _pack(tmp_path)
    calls = _count_parses(monkeypatch)
    a = AF.floors_of(str(obj), 0.9, str(mc))
    assert a.dtype == np.float32 and a.shape == (2, 3, 3)
    assert np.allclose(a[:, :, 1], 3.45)
    assert AF.flush() == 1
    assert (mc / "Some Pack" / AF.CACHE_NAME).is_file()
    AF._forget()                                   # a new process: read the file
    b = AF.floors_of(str(obj), 0.9, str(mc))
    assert np.array_equal(a, b) and len(calls) == 1


def test_a_moved_stat_with_the_same_content_is_a_hit(tmp_path, monkeypatch):
    AF._forget()
    pack, obj, mc = _pack(tmp_path)
    calls = _count_parses(monkeypatch)
    AF.floors_of(str(obj), 0.9, str(mc))
    AF.flush()
    AF._forget()
    st = os.stat(obj)
    os.utime(obj, (st.st_atime, st.st_mtime + 100.0))
    AF.floors_of(str(obj), 0.9, str(mc))
    assert len(calls) == 1


def test_a_content_change_is_a_miss(tmp_path, monkeypatch):
    AF._forget()
    pack, obj, mc = _pack(tmp_path)
    calls = _count_parses(monkeypatch)
    AF.floors_of(str(obj), 0.9, str(mc))
    AF.flush()
    AF._forget()
    _quad_obj(obj, 6.75)                           # same size, new content
    st = os.stat(obj)
    os.utime(obj, (st.st_atime, st.st_mtime + 100.0))
    b = AF.floors_of(str(obj), 0.9, str(mc))
    assert len(calls) == 2 and np.allclose(b[:, :, 1], 6.75)
    # another ``flat`` is another key
    AF.floors_of(str(obj), 0.95, str(mc))
    assert len(calls) == 3


def test_an_unwritable_cache_folder_just_computes(tmp_path, monkeypatch):
    AF._forget()
    pack, obj, mc = _pack(tmp_path)
    (mc / "Some Pack").write_text("not a folder", encoding="utf-8", newline="\n")
    a = AF.floors_of(str(obj), 0.9, str(mc))
    assert a.shape == (2, 3, 3)
    assert AF.flush() == 0                         # the write refused: dropped
    AF._forget()
    assert AF.floors_of(str(obj), 0.9, str(mc)).shape == (2, 3, 3)


def test_no_pack_or_no_mod_cache_computes(tmp_path):
    AF._forget()
    obj = tmp_path / "loose.obj"
    _quad_obj(obj, 1.0)
    assert AF.floors_of(str(obj), 0.9, str(tmp_path)).shape == (2, 3, 3)
    assert AF.flush() == 0


def test_the_guard_scopes_the_floor_cache_to_its_pack():
    import importlib
    sys.path.insert(0, str(HERE / "tools" / "harness"))
    G = importlib.import_module("shared_repo_guard")
    assert G.mod_cache_pack_of(f"Airport_mod_cache/Some Pack/{AF.CACHE_NAME}") == "Some Pack"
    assert AF.CACHE_NAME in G.PACK_CACHE_FAMILIES
