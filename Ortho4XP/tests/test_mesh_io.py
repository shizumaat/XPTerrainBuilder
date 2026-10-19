"""The one numpy ``.mesh`` reader/writer and the Triangle text readers
(mesh-io-spec §3, RULINGS 2026-10-17c; ported from OrthoStudio XP's
``tests/test_mesh_file.py`` / ``test_mesh_triangle_io.py``, adapted).

The per-line reader and writer they replace are kept HERE as the oracles
(spec §3: "the legacy function is kept in the test module as the oracle"):
the ``.mesh`` stays a text file, byte-identical, and every array a consumer
reads stays equal field by field and dtype by dtype.
"""

import os
import re
from math import isfinite

import numpy as np
import pytest

import O4_Mesh_IO as MESH_IO
import O4_Mesh_Utils
import O4_Num_Text as NUMTEXT
import O4_Triangle_IO as TRI_IO

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "mesh",
                       "synthetic_fan_three_triangles.mesh")

SAMPLE = (
    "MeshVersionFormatted 2\n"
    "Dimension 3\n"
    "\n"
    "Vertices\n"
    "4\n"
    "5.117254700000000 43.605783099999996 0.000596498252070 0\n"
    "5.117222000000000 43.605866200000001 0.000596801106090 0\n"
    "5.000000000000000 43.000000000000000 0.000000000000000 0\n"
    "6.000000000000000 44.000000000000000 -0.012345678901234 0\n"
    "\n"
    "Normals\n"
    "4\n"
    "0.06 -0.11 0\n"
    "-0.00 0.00 0\n"
    "1.00 -1.00 0\n"
    "0.50 0.25 0\n"
    "\n"
    "Triangles\n"
    "2\n"
    "1 2 3 0\n"
    "2 3 4 128\n"
)


@pytest.fixture(params=[False, True], ids=["fromstring", "split"])
def number_parsing(request, monkeypatch):
    """Every reader test runs both ways: numpy's C parser and the token
    split Windows uses (``O4_Num_Text.SPLIT_TOKENS``)."""
    monkeypatch.setattr(NUMTEXT, "SPLIT_TOKENS", request.param)
    return request.param


pytestmark = pytest.mark.usefixtures("number_parsing")


################################################################################
# The oracles: the per-line functions as they stood at 104c3cb14.

def _legacy_attribute(text):
    try:
        return int(text)
    except ValueError:
        pass
    value = float(text)
    if isfinite(value) and abs(value - round(value)) <= 1e-6:
        return int(round(value))
    return 0


def legacy_read_mesh_file(mesh_file):
    f = open(mesh_file, "r", encoding="ascii", newline="\n")
    mesh_version = float(f.readline().strip().split()[-1])
    for _ in range(3):
        f.readline()
    nbr_nodes = int(f.readline())
    node_coords = np.zeros(5 * nbr_nodes)
    for i in range(nbr_nodes):
        node_coords[5 * i:5 * i + 3] = [float(x) for x in f.readline().split()[:3]]
    node_coords[2::5] *= 100000
    for _ in range(3):
        f.readline()
    for i in range(nbr_nodes):
        node_coords[5 * i + 3:5 * i + 5] = [float(x) for x in f.readline().split()[:2]]
    for _ in range(2):
        f.readline()
    nbr_tris = int(f.readline())
    tri_idx = np.zeros(3 * nbr_tris, dtype=np.uint32)
    tri_types = np.zeros(nbr_tris, dtype=np.uint32)
    for i in range(nbr_tris):
        columns = f.readline().split()
        tri_idx[3 * i:3 * i + 3] = [int(x) - 1 for x in columns[:3]]
        tri_types[i] = _legacy_attribute(columns[3])
    f.close()
    return (mesh_version, nbr_nodes, node_coords, nbr_tris, tri_idx, tri_types)


def legacy_write_mesh(mesh_file_name, vertices, ele_file_name, lon, lat):
    f_ele = open(ele_file_name, "r", encoding="ascii", newline="\n")
    nbr_vert = len(vertices) // 6
    nbr_tri = int(f_ele.readline().split()[0])
    f = open(mesh_file_name, "w", encoding="ascii", newline="\n")
    f.write("MeshVersionFormatted 2\nDimension 3\n\nVertices\n")
    f.write(str(nbr_vert) + "\n")
    for i in range(nbr_vert):
        f.write("{:.15f}".format(vertices[6 * i] + lon) + " "
                + "{:.15f}".format(vertices[6 * i + 1] + lat) + " "
                + "{:.15f}".format(vertices[6 * i + 2] / 100000) + " 0\n")
    f.write("\nNormals\n" + str(nbr_vert) + "\n")
    for i in range(nbr_vert):
        f.write("{:.2f}".format(vertices[6 * i + 3]) + " "
                + "{:.2f}".format(vertices[6 * i + 4]) + " 0\n")
    f.write("\nTriangles\n" + str(nbr_tri) + "\n")
    for _ in range(nbr_tri):
        columns = f_ele.readline().split()[1:]
        if len(columns) > 3:
            columns[3] = str(_legacy_attribute(columns[3]))
        f.write(" ".join(columns) + "\n")
    f_ele.close()
    f.close()


def _assert_same_tuple(new, old):
    assert new[0] == old[0] and new[1] == old[1] and new[3] == old[3]
    for got, want in ((new[2], old[2]), (new[4], old[4]), (new[5], old[5])):
        assert got.dtype == want.dtype
        assert got.tobytes() == want.tobytes()


################################################################################
# read_mesh


@pytest.mark.parametrize("text", [SAMPLE, open(FIXTURE, encoding="ascii").read()],
                         ids=["sample", "fixture"])
def test_read_mesh_equals_the_legacy_reader(tmp_path, text):
    path = tmp_path / "Data+43+005.mesh"
    path.write_text(text, encoding="ascii", newline="\n")
    _assert_same_tuple(O4_Mesh_Utils.read_mesh_file(str(path)),
                       legacy_read_mesh_file(str(path)))


def test_read_mesh_accepts_a_real_attribute_and_crlf(tmp_path):
    text = SAMPLE.replace("2 3 4 128\n", "2 3 4 16.0\n1 3 4 1.4375\n")
    text = text.replace("Triangles\n2\n", "Triangles\n3\n")
    path = tmp_path / "real.mesh"
    path.write_text(text, encoding="ascii", newline="\n")
    _assert_same_tuple(O4_Mesh_Utils.read_mesh_file(str(path)),
                       legacy_read_mesh_file(str(path)))
    crlf = tmp_path / "crlf.mesh"
    crlf.write_bytes(text.replace("\n", "\r\n").encode("ascii"))
    _assert_same_tuple(O4_Mesh_Utils.read_mesh_file(str(crlf)),
                       legacy_read_mesh_file(str(path)))
    assert list(MESH_IO.read_mesh(str(crlf)).attributes) == [0, 16, 0]


@pytest.mark.parametrize("mutation", [
    lambda t: t.replace("Normals\n4\n", "Normals\n3\n"),
    lambda t: t.replace("Triangles\n2\n", "Triangles\n3\n"),
    lambda t: t.replace("MeshVersionFormatted", "Mesh"),
    lambda t: t.replace("\nNormals\n", "\nNormal\n"),
])
def test_malformed_meshes_are_refused(tmp_path, mutation):
    path = tmp_path / "bad.mesh"
    path.write_text(mutation(SAMPLE), encoding="ascii", newline="\n")
    with pytest.raises(ValueError):
        MESH_IO.read_mesh(str(path))


def test_stock_ortho4xp_two_column_normals_are_read(tmp_path):
    """Stock Ortho4XP writes ``nx ny`` per normal; a neighbour tile it built
    is read by the step 2.5 masks like the per-line reader did (#939)."""
    stock = re.sub(r"(?m)^(\S+ \S+) 0$", r"\1", SAMPLE)
    assert "0.06 -0.11\n-0.00 0.00\n1.00 -1.00\n0.50 0.25\n" in stock
    path = tmp_path / "stock.mesh"
    path.write_text(stock, encoding="ascii", newline="\n")
    _assert_same_tuple(O4_Mesh_Utils.read_mesh_file(str(path)),
                       legacy_read_mesh_file(str(path)))
    ours = tmp_path / "ours.mesh"
    ours.write_text(SAMPLE, encoding="ascii", newline="\n")
    assert np.array_equal(MESH_IO.read_mesh(str(path)).coords,
                          MESH_IO.read_mesh(str(ours)).coords)


################################################################################
# write_mesh


def _ele(path, attribute_texts, n_vertices, rng):
    with open(path, "w", encoding="ascii", newline="\n") as handle:
        handle.write("%d 3 1\n" % len(attribute_texts))
        for index, text in enumerate(attribute_texts):
            (a, b, c) = rng.integers(1, n_vertices + 1, size=3)
            handle.write("%4d    %d  %d  %d    %s\n" % (index + 1, a, b, c, text))
        handle.write("# Generated by a test\n")


def test_write_mesh_reproduces_the_legacy_bytes(tmp_path):
    rng = np.random.default_rng(7)
    n = 3000
    vertices = np.empty((n, 6))
    vertices[:, :2] = rng.random((n, 2)) * 1.02 - 0.01
    vertices[:, 2] = rng.normal(300, 400, n)
    vertices[:, 3:5] = rng.normal(0, 0.3, (n, 2))
    vertices[:, 5] = vertices[:, 2]
    vertices[:5, :5] = [[0.0, -0.0, -0.0, -0.004, 0.005]] * 5  # signs, ties
    texts = ["0", "16", "16.0", "1.4375", "10", "nan", "128", "16.0000001"]
    ele = tmp_path / "Data.1.ele"
    _ele(ele, texts * 400, n, rng)
    want = tmp_path / "want.mesh"
    got = tmp_path / "got.mesh"
    legacy_write_mesh(str(want), vertices.ravel(), str(ele), -136, 60)
    MESH_IO.write_mesh(str(got), vertices.ravel(), str(ele), -136, 60)
    assert got.read_bytes() == want.read_bytes()
    assert not [p for p in os.listdir(tmp_path) if ".tmp" in p]


def test_write_mesh_reproduces_the_fixture(tmp_path):
    mesh = MESH_IO.read_mesh(FIXTURE)
    vertices = np.zeros((len(mesh.coords), 6))
    vertices[:, 0] = mesh.coords[:, 0] - 10
    vertices[:, 1] = mesh.coords[:, 1] - 50
    vertices[:, 2] = mesh.coords[:, 2]
    ele = tmp_path / "f.1.ele"
    with open(ele, "w", encoding="ascii", newline="\n") as handle:
        handle.write("%d 3 1\n" % len(mesh.triangles))
        for i, (tri, attr) in enumerate(zip(mesh.triangles + 1, mesh.attributes)):
            handle.write("%d %d %d %d %d\n" % (i + 1, *tri, attr))
    out = tmp_path / "out.mesh"
    MESH_IO.write_mesh(str(out), vertices.ravel(), str(ele), 10, 50)
    want = tmp_path / "legacy.mesh"
    legacy_write_mesh(str(want), vertices.ravel(), str(ele), 10, 50)
    assert out.read_bytes() == want.read_bytes()


################################################################################
# Triangle text files


def test_node_text_round_trips_header_and_trailer(tmp_path):
    path = tmp_path / "Data.1.node"
    path.write_text("3  2  4  0\n"
                    "   1    0.5   0.25   12.5   0.1  -0.2   12.0\n"
                    "   2    0.75   0.5   13   0   0   13\n"
                    "   3    1e-05   1   -2.5   0   0   -2.5\n"
                    "# Generated by Triangle4XP -pq10\n", encoding="ascii", newline="\n")
    nodes = TRI_IO.read_node_text(str(path))
    assert nodes.header_line == "3  2  4  0\n"
    assert nodes.trailer_line == "# Generated by Triangle4XP -pq10\n"
    assert list(nodes.ids) == [1, 2, 3] and nodes.values.shape == (3, 6)
    assert nodes.xy[2].tolist() == [1e-05, 1.0]
    out = tmp_path / "out.node"
    TRI_IO.write_node_text(str(out), nodes.header_line, nodes.values,
                           nodes.trailer_line)
    want = nodes.header_line + "".join(
        str(i + 1) + " " + " ".join("{:.15f}".format(x) for x in row) + "\n"
        for i, row in enumerate(nodes.values)) + nodes.trailer_line
    assert out.read_text(encoding="ascii") == want
    assert TRI_IO.read_node_count(str(path)) == 3


def test_ele_vertex_numbers_stay_strict_integers(tmp_path):
    path = tmp_path / "bad.1.ele"
    path.write_text("1 3 1\n1 1.5 2 3 8\n", encoding="ascii", newline="\n")
    with pytest.raises(ValueError):
        TRI_IO.read_ele_text(str(path))


def test_ele_real_attributes_follow_the_one_law(tmp_path):
    texts = ["0", "16", "16.0", "16.0000001", "10", "1.4375", "0.5", "-2.25",
             "nan", "inf"]
    path = tmp_path / "a.1.ele"
    path.write_text("%d 3 1\n" % len(texts) + "".join(
        "%d 1 2 3 %s\n" % (i + 1, t) for i, t in enumerate(texts)),
        encoding="ascii", newline="\n")
    elements = TRI_IO.read_ele_text(str(path))
    (attrs, integral) = TRI_IO.triangle_attributes(elements.attributes[:, 0])
    want = [O4_Mesh_Utils.read_triangle_attribute(t) for t in texts]
    assert list(zip(attrs.tolist(), integral.tolist())) == want


def test_poly_segments_skip_the_empty_node_section(tmp_path):
    path = tmp_path / "Data.poly"
    path.write_text("0 2 1 0\n\n3 1\n1 1 2 15\n2 2 3 8\n3 3 1 15\n"
                    "\n1\n1 0.500000000000000 0.500000000000000\n"
                    "\n2\n1 0.1 0.2 1\n2 0.3 0.4 8 1e-08\n", encoding="ascii", newline="\n")
    (segments, markers) = TRI_IO.read_poly_segments(str(path))
    assert segments.tolist() == [[1, 2], [2, 3], [3, 1]]
    assert markers.tolist() == [15, 8, 15]


def test_split_and_fromstring_parse_bit_for_bit():
    rng = np.random.default_rng(3)
    values = np.concatenate([rng.normal(0, 1e3, 5000), rng.random(5000)])
    text = " ".join("%.17g" % v for v in values) + "\n"
    a = NUMTEXT.parse_numbers(text.encode(), split=False)
    b = NUMTEXT.parse_numbers(text.encode(), split=True)
    assert a.tobytes() == b.tobytes() == values.tobytes()
