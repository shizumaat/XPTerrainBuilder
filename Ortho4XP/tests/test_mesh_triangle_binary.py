"""Binary Triangle4XP exchange (``-b``, O4_TRIANGLE_IO=binary) — mesh-io-spec
§4, RULINGS 2026-10-17a Q6 / 17c.  Ported from OrthoStudio XP's
``tests/test_mesh_triangle_io.py`` (binary round trips, text == binary
sidecar twin, ``-b`` refuses ``-r``), adapted.

The twin is the admission gate: on the same input, text mode and binary
mode decode to identical doubles and ints, and the ``.mesh`` written from
either is byte-identical.  It runs where the platform's Triangle4XP carries
``-b`` and is skipped (with the reason) elsewhere.
"""

import math
import os
import subprocess
import sys

import numpy as np
import pytest

import O4_File_Names as FNAMES
import O4_Mesh_IO as MESH_IO
import O4_Triangle_Binary as TRI_BIN
import O4_Triangle_IO as TRI_IO

_PLATFORM = ("mac" if sys.platform == "darwin"
             else "win" if sys.platform.startswith("win") else "lin")
#: CI also builds Triangle4XP from Utils/src with the runner's own compiler
#: on Linux and Windows and points this at it; a binary named here that
#: lacks -b is an error, never a skip.
BINARY_ENV = "O4_TRIANGLE4XP_TEST_BINARY"
TRIANGLE4XP = os.environ.get(BINARY_ENV) or os.path.join(
    FNAMES.Utils_dir, _PLATFORM,
    "Triangle4XP.exe" if _PLATFORM == "win" else "Triangle4XP")
if os.environ.get(BINARY_ENV) and not TRI_BIN.binary_capable(TRIANGLE4XP):
    raise RuntimeError(f"{BINARY_ENV}={TRIANGLE4XP} does not carry -b")
needs_binary = pytest.mark.skipif(
    not TRI_BIN.binary_capable(TRIANGLE4XP),
    reason=f"{TRIANGLE4XP} does not carry -b yet (admission: all three binaries)")


################################################################################
# Python layouts


def test_node_and_ele_binary_round_trip(tmp_path):
    rng = np.random.default_rng(1)
    points = rng.random((30, 3))
    TRI_BIN.write_node_binary(tmp_path / "a.node", points)
    nodes = TRI_BIN.read_node(tmp_path / "a.node")
    assert nodes.values.tobytes() == points.tobytes()
    assert nodes.ids.tolist() == list(range(1, 31)) and nodes.header_line is None
    triangles = rng.integers(1, 31, size=(12, 3))
    attributes = rng.integers(0, 256, size=(12, 1)).astype(float)
    TRI_BIN.write_ele_binary(tmp_path / "a.ele", triangles, attributes)
    elements = TRI_BIN.read_ele(tmp_path / "a.ele")
    assert np.array_equal(elements.triangles, triangles)
    assert elements.attributes.tobytes() == attributes.tobytes()


def test_poly_binary_carries_holes_and_regions_as_triangle_reads_them(tmp_path):
    poly = tmp_path / "Data.poly"
    poly.write_text("0 2 1 0\n\n3 1\n1 1 2 15\n2 2 3 8\n3 3 1 15\n"
                    "\n1\n1 0.500000000000000 0.250000000000000\n"
                    "\n2\n1 0.1 0.2 1\n2 0.3 0.4 8 1e-08\n",
                    encoding="ascii", newline="\n")
    (holes, regions) = TRI_BIN.read_poly_holes_regions(poly)
    assert holes.tolist() == [[0.5, 0.25]]
    # no area field: Triangle's text reader takes the attribute as the area
    assert regions.tolist() == [[0.1, 0.2, 1.0, 1.0], [0.3, 0.4, 8.0, 1e-08]]
    TRI_BIN.write_poly_binary(tmp_path / "Data.b.poly", poly)
    data = (tmp_path / "Data.b.poly").read_bytes()
    assert data[:8] == TRI_BIN.POLY_MAGIC
    head = np.frombuffer(data[8:8 + 28], dtype="=i4")
    assert head.tolist() == [0, 2, 0, 0, 1, 3, 1]


def test_truncated_and_foreign_files_are_refused(tmp_path):
    TRI_BIN.write_node_binary(tmp_path / "a.node", np.zeros((4, 3)))
    data = (tmp_path / "a.node").read_bytes()
    (tmp_path / "short.node").write_bytes(data[:-3])
    with pytest.raises(TRI_IO.TriangleFormatError):
        TRI_BIN.read_node_binary(tmp_path / "short.node")
    with pytest.raises(TRI_IO.TriangleFormatError):
        TRI_BIN.read_ele_binary(tmp_path / "a.node")


@pytest.mark.parametrize("value, requested", [
    (None, True), ("text", False), (" Text ", False), ("binary", True), ("1", True)])
def test_the_flag_is_on_unless_text(monkeypatch, value, requested):
    if value is None:
        monkeypatch.delenv(TRI_BIN.TRIANGLE_IO_ENV, raising=False)
    else:
        monkeypatch.setenv(TRI_BIN.TRIANGLE_IO_ENV, value)
    assert TRI_BIN.binary_requested() is requested


def test_binary_io_needs_the_flag_a_capable_binary_and_no_refine(tmp_path, monkeypatch):
    capable = tmp_path / "Triangle4XP"
    capable.write_bytes(b"\x00ELF..." + TRI_BIN.POLY_MAGIC + b"...")
    stock = tmp_path / "Triangle4XP_stock"
    stock.write_bytes(b"\x00ELF... no switch here")
    monkeypatch.setenv(TRI_BIN.TRIANGLE_IO_ENV, "binary")
    assert TRI_BIN.use_binary_io(str(capable), refine=False)
    assert not TRI_BIN.use_binary_io(str(capable), refine=True)
    assert not TRI_BIN.use_binary_io(str(stock), refine=False)
    assert not TRI_BIN.use_binary_io(str(tmp_path / "missing"), refine=False)
    monkeypatch.setenv(TRI_BIN.TRIANGLE_IO_ENV, "text")
    assert not TRI_BIN.use_binary_io(str(capable), refine=False)


################################################################################
# The admission twin: the real Triangle4XP, text vs binary


def _square_inputs(directory, rng, n_inner=60):
    corners = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    xy = np.vstack([corners, rng.random((n_inner, 2))])
    alt = rng.random(len(xy)) * 1000.0
    with open(directory / "s.node", "w", encoding="ascii", newline="\n") as handle:
        handle.write(f"{len(xy)} 2 1 0\n")
        for i, ((x, y), z) in enumerate(zip(xy, alt)):
            handle.write(f"{i + 1} {x:.9f} {y:.9f} {z:.9f}\n")
    with open(directory / "s.poly", "w", encoding="ascii", newline="\n") as handle:
        handle.write("0 2 1 0\n\n4 1\n1 1 2 0\n2 2 3 0\n3 3 4 1\n4 4 1 1\n")
        handle.write("\n0\n\n2\n1 0.500000000000000 0.500000000000000 1\n")
        handle.write("2 0.250000000000000 0.250000000000000 8 0.001\n")


def _run(switches, alt, weight, poly, lat=43.0):
    lat_to_m = math.pi * 6378137 / 180
    args = [TRIANGLE4XP, switches, f"{lat_to_m * math.cos(math.radians(lat)):.9g}",
            f"{lat_to_m:.9g}", "11", "11", "-0.01", "-0.01", "1.01", "1.01",
            "-32768", "2", str(alt), str(weight), str(poly)]
    return subprocess.run(args, capture_output=True, text=True, check=False)


@needs_binary
def test_text_and_binary_modes_agree_and_write_the_same_mesh(tmp_path):
    rng = np.random.default_rng(5)
    alt = tmp_path / "s.alt"
    weight = tmp_path / "s.weight"
    (rng.random((11, 11)) * 100).astype(np.float32).tofile(alt)
    np.ones((1001, 1001), dtype=np.float32).tofile(weight)
    (tmp_path / "text").mkdir()
    (tmp_path / "bin").mkdir()
    _square_inputs(tmp_path / "text", np.random.default_rng(6))
    _square_inputs(tmp_path / "bin", np.random.default_rng(6))
    switches = "-pq10AauYBQS500000"
    res = _run(switches, alt, weight, tmp_path / "text" / "s.poly")
    assert res.returncode == 0, res.stdout
    binary_poly = TRI_BIN.binary_inputs(str(tmp_path / "bin" / "s.node"),
                                        str(tmp_path / "bin" / "s.poly"))
    res = _run(switches.replace("QS", "QbS"), alt, weight, binary_poly)
    assert res.returncode == 0, res.stdout
    TRI_BIN.adopt_binary_outputs(binary_poly, str(tmp_path / "bin" / "s.1.node"),
                                 str(tmp_path / "bin" / "s.1.ele"))
    text_nodes = TRI_IO.read_node_text(tmp_path / "text" / "s.1.node")
    bin_nodes = TRI_BIN.read_node(tmp_path / "bin" / "s.1.node")
    assert text_nodes.values.tobytes() == bin_nodes.values.tobytes()
    text_ele = TRI_IO.read_ele_text(tmp_path / "text" / "s.1.ele")
    bin_ele = TRI_BIN.read_ele(tmp_path / "bin" / "s.1.ele")
    assert np.array_equal(text_ele.triangles, bin_ele.triangles)
    assert text_ele.attributes.tobytes() == bin_ele.attributes.tobytes()
    assert text_ele.n_triangles > 60
    meshes = []
    for (arm, nodes) in (("text", text_nodes), ("bin", bin_nodes)):
        out = tmp_path / arm / "s.mesh"
        MESH_IO.write_mesh(str(out), nodes.values[:, :6].ravel(),
                           str(tmp_path / arm / "s.1.ele"), 5, 43)
        meshes.append(out.read_bytes())
    assert meshes[0] == meshes[1]


@needs_binary
def test_binary_refuses_refine(tmp_path):
    res = _run("-rb", tmp_path / "a.alt", tmp_path / "a.weight", tmp_path / "x.node")
    assert res.returncode != 0
    assert "-b" in res.stdout and "-r" in res.stdout


def _post_processed(directory, stem):
    """Rewrite ``<stem>.node`` as ``post_process_nodes_altitudes`` does: in
    the encoding Triangle4XP wrote it (binary stays binary)."""
    path = str(directory / (stem + ".node"))
    nodes = TRI_BIN.read_node(path)
    if nodes.header_line is None:
        TRI_BIN.write_node_binary(path, nodes.values[:, :6])
    else:
        TRI_IO.write_node_text(path, nodes.header_line, nodes.values[:, :6],
                               nodes.trailer_line)
    return nodes.values[:, :6]


@needs_binary
def test_iterate_refines_a_binary_mesh_to_the_text_mesh(tmp_path):
    """The ``iterate`` cfg var refines the previous run's ``Data.N.node`` /
    ``.N.ele`` with ``-r``, which Triangle4XP reads as text only: a binary
    previous run is converted at that consumer, and iterate 1 under binary
    IO writes the very ``.mesh`` it writes under text IO."""
    rng = np.random.default_rng(5)
    alt = tmp_path / "s.alt"
    weight = tmp_path / "s.weight"
    (rng.random((11, 11)) * 100).astype(np.float32).tofile(alt)
    np.ones((1001, 1001), dtype=np.float32).tofile(weight)
    switches = "-pq10AauYBQS500000"
    meshes = []
    for arm in ("text", "bin"):
        directory = tmp_path / arm
        directory.mkdir()
        _square_inputs(directory, np.random.default_rng(6))
        if arm == "text":
            res = _run(switches, alt, weight, directory / "s.poly")
        else:
            poly = TRI_BIN.binary_inputs(str(directory / "s.node"),
                                         str(directory / "s.poly"))
            res = _run(switches.replace("QS", "QbS"), alt, weight, poly)
            TRI_BIN.adopt_binary_outputs(poly, str(directory / "s.1.node"),
                                         str(directory / "s.1.ele"))
        assert res.returncode == 0, res.stdout
        _post_processed(directory, "s.1")
        assert TRI_BIN.refine_inputs_as_text(
            str(directory / "s.1.node"), str(directory / "s.1.ele")) is (arm == "bin")
        res = _run("-pq10ruYBQS500000", alt, weight, directory / "s.1.poly")
        assert res.returncode == 0, res.stdout
        vertices = _post_processed(directory, "s.2")
        out = directory / "s.mesh"
        MESH_IO.write_mesh(str(out), vertices.ravel(), str(directory / "s.2.ele"), 5, 43)
        meshes.append(out.read_bytes())
    assert meshes[0].count(b"\n") > 200
    assert meshes[0] == meshes[1]
