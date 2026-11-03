"""#1707 O4: "Optimise pack" makes a placed pack object's textures lighter
in NEW files beside the vendor's (``<stem>.o4opt.dds``): an uncompressed
DDS and a huge PNG compressed, a big texture only small props use halved,
byte-identical copies read once — and the object copies name them.
Headless; the sizes are scaled down (``BIG_PX`` / ``HUGE_PX``).
"""
from __future__ import annotations

import os
import struct
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import O4_DDS_Encode as ENC  # noqa: E402
import O4_DDS_File as DDSF  # noqa: E402
from auto_patch_v2.airport import pack_optimise as PO  # noqa: E402
from auto_patch_v2.airport.pack_optimise import objcopy as OC  # noqa: E402
from auto_patch_v2.airport.pack_optimise import textures as TX  # noqa: E402
from test_pack_optimise_swap import obj  # noqa: E402

pytestmark = pytest.mark.skipif(not ENC.ispc_available(), reason="needs ispc_texcomp")


def rgb_dds(w: int, h: int) -> bytes:
    """An uncompressed 24-bit DDS (no mips)."""
    head = bytearray(128)
    head[:4] = b"DDS "
    struct.pack_into("<7I", head, 4, 124, 0x100F, h, w, w * 3, 0, 1)
    struct.pack_into("<2I4s5I", head, 76, 32, 0x40, b"\0\0\0\0", 24,
                     0xFF0000, 0xFF00, 0xFF, 0)
    pix = (np.arange(w * h * 3) % 251).astype(np.uint8).tobytes()
    return bytes(head) + pix


def dxt1_dds(w: int) -> bytes:
    rgba = np.zeros((w, w, 4), np.uint8)
    rgba[..., 0] = 200
    rgba[..., 3] = 255
    return ENC.encode_dds(rgba, "bc1")


@pytest.fixture
def small(monkeypatch):
    monkeypatch.setattr(TX, "BIG_PX", 32)
    monkeypatch.setattr(TX, "HUGE_PX", 64)


def _obj_with(tex: str, size: float = 2.0) -> str:
    return obj((0, size), (0, 1), (0, 1)).replace("TEXTURE car.png", f"TEXTURE {tex}")


def _pack(tmp_path, files):
    root = tmp_path / "p"
    for rel, data in files.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            f.write_bytes(data)
        else:
            f.write_text(data, encoding="utf-8", newline="")
    return root


def test_the_plan(tmp_path, small):
    from PIL import Image
    root = _pack(tmp_path, {"o/raw.dds": rgb_dds(16, 16), "o/big.dds": dxt1_dds(32),
                            "o/twin.dds": dxt1_dds(32), "o/shared.dds": dxt1_dds(32),
                            "o/A.obj": _obj_with("raw.dds"),
                            "o/B.obj": _obj_with("big.png"),      # the .dds is drawn
                            "o/C.obj": _obj_with("twin.dds"),
                            "o/D.obj": _obj_with("shared.dds"),
                            "o/E.obj": _obj_with("shared.dds", size=20.0)})
    (root / "o" / "shared.dds").write_bytes(dxt1_dds(32)[:-1] + b"\x01")
    Image.new("RGBA", (64, 64), (1, 2, 3, 255)).save(root / "o" / "huge.png")
    (root / "o" / "F.obj").write_text(_obj_with("huge.png"), encoding="utf-8", newline="")
    objs = [(f"o/{n}.obj", 20.0 if n == "E" else 2.0) for n in "ABCDEF"]
    tex, rw = TX.plan_textures(str(root), objs)
    assert tex["o/raw.dds"] == {"act": "encode", "halve": False, "to": "o/raw.o4opt.dds"}
    assert tex["o/big.dds"] == {"act": "halve", "halve": True, "to": "o/big.o4opt-half.dds"}
    assert tex["o/huge.png"] == {"act": "encode", "halve": True, "to": "o/huge.o4opt-half.dds"}
    assert "o/shared.dds" not in tex and "o/twin.dds" not in tex, \
        "a big prop shares it; a twin is read as its first copy"
    assert rw["o/A.obj"] == {"raw.dds": "raw.o4opt.dds"}
    assert rw["o/B.obj"] == {"big.png": "big.o4opt-half.dds"}
    assert rw["o/C.obj"] == {"twin.dds": "big.o4opt-half.dds"}, "byte-identical: one file"
    assert "o/D.obj" not in rw and "o/E.obj" not in rw


def test_the_written_textures(tmp_path, small):
    root = _pack(tmp_path, {"o/raw.dds": rgb_dds(16, 16), "o/big.dds": dxt1_dds(32)})
    TX.write_texture(str(root), "o/raw.dds", {"act": "encode", "halve": False,
                                               "to": "o/raw.o4opt.dds"})
    TX.write_texture(str(root), "o/big.dds", {"act": "halve", "halve": True,
                                               "to": "o/big.o4opt-half.dds"})
    (w, h, fmt), levels = DDSF.split_levels((root / "o" / "raw.o4opt.dds").read_bytes())
    assert (w, h, fmt, len(levels)) == (16, 16, "bc1", 5)
    (w, h, fmt), levels = DDSF.split_levels((root / "o" / "big.o4opt-half.dds").read_bytes())
    assert (w, h, fmt, len(levels)) == (16, 16, "bc1", 5), "the first mip dropped"
    assert TX.vram_bytes(str(root / "o" / "raw.o4opt.dds")) < TX.vram_bytes(
        str(root / "o" / "raw.dds"))
    out = root / "o" / "raw.o4opt.dds"
    assert out.stat().st_mtime_ns == (root / "o" / "raw.dds").stat().st_mtime_ns
    data = out.read_bytes()
    os.utime(out, ns=((root / "o" / "raw.dds").stat().st_atime_ns,
                      (root / "o" / "raw.dds").stat().st_mtime_ns))
    TX.write_texture(str(root), "o/raw.dds", {"act": "encode", "halve": False,
                                               "to": "o/raw.o4opt.dds"})
    assert out.read_bytes() == data, "a current file is not written again"


def test_the_recipe_names_the_textures_in_the_copies(tmp_path, small):
    root = _pack(tmp_path, {"o/raw.dds": rgb_dds(16, 16), "o/A.obj": _obj_with("raw.dds")})
    lines = ["OBJECT_DEF o/A.obj\n", "OBJECT 0 1 2 3\n"]
    recipe = PO.build_recipe(str(root), lines, None)
    assert recipe["objects"]["o/A.obj"] == {"specular": None, "lod": None,
                                            "tex": {"raw.dds": "raw.o4opt.dds"}}
    gen = PO.write_generated(str(root), recipe)
    assert gen == ["o/raw.o4opt.dds", "o/A.o4opt.obj"]
    copy = (root / "o" / "A.o4opt.obj").read_text(encoding="utf-8")
    assert "TEXTURE\traw.o4opt.dds" in copy
    vendor = (root / "o" / "A.obj").read_text(encoding="utf-8")
    assert "TEXTURE raw.dds" in vendor, "the vendor file stays"
    assert sorted(PO.remove_generated(str(root), gen)) == sorted(gen)
    assert OC.copy_path("o/A.obj") == "o/A.o4opt.obj"
