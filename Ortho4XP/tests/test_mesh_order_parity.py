"""Both apps show the scenery-order warning in the same words (#1729):
the Mac app's ``TileMeshOrder.swift`` repeats ``O4_Mesh_Order``'s lines
and details and ``O4_Qt_Mesh_Order.BUTTONS``' titles.  Static reads; no PySide6."""

from pathlib import Path

import O4_Mesh_Order as MESH

SWIFT = (Path(__file__).resolve().parents[2] / "Sources" / "SceneryKit"
         / "TileMeshOrder.swift").read_text(encoding="utf-8")
ROW = (Path(__file__).resolve().parents[2] / "Sources" / "XPTerrainBuilder"
       / "TileMeshOrderRow.swift").read_text(encoding="utf-8")


def test_details_and_line_prefixes_match():
    for text in (MESH.HIDDEN_BY_DETAIL, MESH.HIDES_DETAIL):
        assert '"%s"' % text in SWIFT
    reply = {"hidden_by": ["A", "B"], "hides": ["C"]}
    lines = [line for _kind, line, _detail in MESH.warning_lines(reply)]
    assert lines == ["Hidden in X-Plane by “A” and 1 more",
                     "Hides the ground of “C”"]
    assert '"Hidden in X-Plane by " + Self.names' in SWIFT
    assert '"Hides the ground of " + Self.names' in SWIFT
    assert '"\\(quoted) and \\(packs.count - 1) more"' in SWIFT


def test_buttons_match_the_qt_row():
    """Read statically: importing the Qt module here would start Qt
    outside the offscreen suites."""
    qt = (Path(__file__).resolve().parents[1] / "src"
          / "O4_Qt_Mesh_Order.py").read_text(encoding="utf-8")
    for (title, action, which) in (
            ("Move Tile Above", "raise", "first"),
            ("Disable Scenery", "disable", "first"),
            ("Show Its Ground", "lower", "last")):
        assert '("%s", "%s", "%s")' % (title, action, which) in qt
        assert '"%s"' % title in SWIFT
        assert '"%s"' % action in ROW
