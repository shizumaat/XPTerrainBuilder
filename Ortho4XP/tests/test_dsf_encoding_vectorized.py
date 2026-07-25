"""Byte-identity guards for the vectorized DSF encoding loops.

The GEOD pool writes and the CMDS PATCH TRIANGLE runs in ``build_dsf`` were
rewritten from per-word ``struct.pack`` loops to numpy views.  Two guards:

* a property test of ``_patch_triangle_commands`` against a naive struct
  reference, across the chunk boundaries (0, 1, 254, 255, 256, 510, 511 ...)
  that a tiny synthetic mesh can never reach;
* a synthetic-tile A/B against the pre-vectorization commit (pinned
  ``c2c46a2``), reusing the harness from ``test_dsf_texture_modes``.

Headless: no network, no X-Plane install.
"""
import importlib.util
import os
import queue
import struct
import subprocess
import sys

import numpy
import pytest

import O4_DSF_Utils as DSF

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_dsf_texture_modes as T  # noqa: E402

# Last commit with the per-word struct.pack encoding loops.
_BASE_COMMIT = "c2c46a2"


# ── property test: _patch_triangle_commands vs struct reference ─────────

def _reference_cmds(vals, opcode, words_per_cmd):
    """The historical encoding, transcribed: full 255-count commands, then
    one remainder command (cross-pool counts pairs, not words)."""
    out = b""
    full = len(vals) // words_per_cmd
    for j in range(full):
        out += struct.pack("<B", opcode) + struct.pack("<B", 255)
        for v in vals[j * words_per_cmd : (j + 1) * words_per_cmd]:
            out += struct.pack("<H", v)
    rem = len(vals) % words_per_cmd
    count = rem if words_per_cmd == 255 else rem // 2
    if count:
        payload = count if words_per_cmd == 255 else 2 * count
        out += struct.pack("<B", opcode) + struct.pack("<B", count)
        for v in vals[full * words_per_cmd : full * words_per_cmd + payload]:
            out += struct.pack("<H", v)
    return out


@pytest.mark.parametrize("opcode,words_per_cmd", [(23, 255), (24, 510)])
@pytest.mark.parametrize(
    "n", [0, 2, 6, 254, 255, 256, 508, 510, 512, 1020, 1023, 2551])
def test_patch_triangle_commands_matches_struct_reference(
        opcode, words_per_cmd, n):
    if words_per_cmd == 510:
        n -= n % 2  # cross-pool data is always (pool, pos) pairs
    rng = numpy.random.default_rng(seed=n + words_per_cmd)
    vals = rng.integers(0, 65536, size=n).astype(numpy.uint16)
    got = DSF._patch_triangle_commands(vals, opcode, words_per_cmd)
    want = _reference_cmds([int(v) for v in vals], opcode, words_per_cmd)
    assert got == want


# ── synthetic-tile A/B vs the pre-vectorization commit ──────────────────

def _load_base_module(tmp_path):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        toplevel = subprocess.check_output(
            ["git", "-C", here, "rev-parse", "--show-toplevel"],
            text=True).strip()
        base_src = subprocess.check_output(
            ["git", "-C", toplevel, "show",
             _BASE_COMMIT + ":Ortho4XP/src/O4_DSF_Utils.py"],
            text=True)
    except (subprocess.SubprocessError, OSError):
        return None
    base_path = str(tmp_path / "O4_DSF_Utils_prevec.py")
    with open(base_path, "w") as handle:
        handle.write(base_src)
    spec = importlib.util.spec_from_file_location(
        "O4_DSF_Utils_prevec", base_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_full_ortho_byte_identical_to_prevectorized(tmp_path, monkeypatch):
    base = _load_base_module(tmp_path)
    if base is None:
        pytest.skip("could not load pre-vectorization O4_DSF_Utils "
                    "(git show failed)")

    def _build(module, sub):
        build_dir = T._prepare_build_dir(tmp_path / sub)
        T._write_mesh(build_dir, T._LAND_AND_SEA_VERTS, T._LAND_AND_SEA_TRIS)
        monkeypatch.setattr(
            module, "extract_elevation_and_bathymetry_data",
            lambda lat, lon: (b"", b""))
        tile = T._make_tile(build_dir, "full_ortho")
        rc = module.build_dsf(tile, queue.Queue())
        assert rc == 1
        with open(T._emitted_dsf(build_dir), "rb") as handle:
            return handle.read()

    (tmp_path / "edited").mkdir()
    (tmp_path / "prevec").mkdir()
    edited_bytes = _build(DSF, "edited")
    base_bytes = _build(base, "prevec")
    assert edited_bytes == base_bytes, (
        "full_ortho DSF bytes changed vs pre-vectorization commit "
        f"(edited={len(edited_bytes)}B, base={len(base_bytes)}B)")
