"""The Qt tile pane's scenery-order row (O4_Qt_Mesh_Order, #1729) on a
synthetic Custom Scenery.  Offscreen, no engine, no network."""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from test_mesh_order import LAT, LON, _ini, _install, _pack  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def _settle(qapp, until, seconds=5.0):
    deadline = time.time() + seconds
    while time.time() < deadline and not until():
        qapp.processEvents()
        time.sleep(0.02)
    qapp.processEvents()


def test_hidden_tile_warns_and_move_tile_above_fixes_it(qapp, tmp_path):
    import O4_Qt_Mesh_Order as QTMESH
    csd, build = _install(tmp_path)
    _pack(csd, "Airport Mesh")
    _ini(csd, "Airport Mesh", "zOrtho4XP_+39-077")
    row = QTMESH.MeshOrderRow()
    row.show()
    row.check((LAT, LON), build, str(csd))
    hidden_row, hidden_label = row.lines["hidden_by"]
    _settle(qapp, lambda: row.isVisible())
    assert hidden_row.isVisible()
    assert hidden_label.text() == "⚠ Hidden in X-Plane by “Airport Mesh”"
    assert "above it in X-Plane's scenery order" in hidden_label.toolTip()
    move = [b for b in hidden_row.findChildren(QTMESH.QPushButton)
            if b.text() == "Move Tile Above"][0]
    move.click()
    hides_row, hides_label = row.lines["hides"]
    _settle(qapp, lambda: hides_row.isVisible())
    assert not hidden_row.isVisible()
    assert hides_label.text() == "⚠ Hides the ground of “Airport Mesh”"
    rows = (csd / "scenery_packs.ini").read_text(encoding="utf-8")
    assert rows.index("zOrtho4XP_+39-077") < rows.index("Airport Mesh")


def test_nothing_shows_while_all_is_well(qapp, tmp_path):
    import O4_Qt_Mesh_Order as QTMESH
    csd, build = _install(tmp_path)
    _ini(csd, "zOrtho4XP_+39-077")
    row = QTMESH.MeshOrderRow()
    row.show()
    row.check((LAT, LON), build, str(csd))
    _settle(qapp, lambda: False, seconds=0.5)
    assert not row.isVisible()
    row.clear()
    assert not row.isVisible()
