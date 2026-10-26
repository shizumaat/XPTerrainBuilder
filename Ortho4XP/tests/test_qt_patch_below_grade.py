"""Below-grade striping in the patch view (issue #1319).

Both apps hatch the fill of a below-grade shape: 45° bands in the role's
colour at a second alpha, clipped to the shape, beneath its stroke.  The
role list is kept once per app — the Mac's ``PatchWay.belowGradeRoles``
(``Sources/SceneryKit/PatchDocument.swift``) and the Qt app's
``BELOW_GRADE_ROLES`` (``O4_Qt_Patch_Geometry.py``) — and twin-asserted
here, against each other and against the engine's own role table.

Offscreen (``QT_QPA_PLATFORM=offscreen``), no network, no engine.
"""

import math
import os
import re
import sys
import tomllib
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_Patch_Overlay as OVERLAY  # noqa: E402
from auto_patch_v2.emit.graded import FLOOR_ROLES  # noqa: E402
from O4_Qt_Patch_Geometry import BELOW_GRADE_ROLES, below_grade  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QImage, QPainter, QPainterPath  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PRECEDENCE = ROOT / "Ortho4XP" / "src" / "auto_patch_v2" / "law" / "precedence.toml"


def _swift(path: str, pattern: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    match = re.search(pattern, text, re.S)
    assert match, f"{pattern!r} not found in {path}"
    return match.group(1)


def test_role_list_is_the_same_in_both_apps():
    body = _swift("Sources/SceneryKit/PatchDocument.swift",
                  r"static let belowGradeRoles: \[String\] = \[(.*?)\]")
    assert tuple(re.findall(r'"([a-z_]+)"', body)) == BELOW_GRADE_ROLES


def test_role_list_is_the_engines_structure_floors():
    with open(PRECEDENCE, "rb") as f:
        roles = tomllib.load(f)["roles"]
    for role in BELOW_GRADE_ROLES:
        assert roles[role].get("structure") is True, role
    assert set(FLOOR_ROLES) <= set(BELOW_GRADE_ROLES)


def test_legend_label_is_the_same_in_both_apps():
    label = _swift("Sources/XPTerrainBuilder/PatchOverlay.swift",
                   r'static let belowGradeLabel = "([^"]+)"')
    assert label == OVERLAY.BELOW_GRADE_LABEL


def test_below_grade_reads_role_or_the_emitters_class():
    assert below_grade({"role": "tunnel_ramp", "aeroway": "taxiway"})
    assert below_grade({"role": "tunnel_ramp", "class": "wall_corridor_ramp"})
    assert below_grade({"role": "tunnel_trench", "aeroway": "apron"})
    assert not below_grade({"role": "apron", "aeroway": "apron"})
    assert not below_grade({"role": "groundside_pavement", "class": "parking_lot"})


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _square(x0: float, y0: float, side: float) -> QPainterPath:
    path = QPainterPath()
    path.addRect(x0, y0, side, side)
    return path


def test_hatch_alternates_inside_a_ramp_and_not_inside_an_apron(qapp):
    image = QImage(160, 80, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    OVERLAY.paint_styled(painter, [("taxiway", True, _square(10, 10, 60), True),
                                   ("apron", True, _square(90, 10, 60), False)])
    painter.end()

    # Band centres sit at x + y = period/4 (mod period); gap centres half a
    # period on.  Two pixels on one row, a half period apart along x.
    period = 2 * OVERLAY.HATCH_BAND * math.sqrt(2)
    y = 40
    k = math.ceil((10 + y - period / 4) / period) + 1
    band_x = round(period / 4 + k * period - y)
    gap_x = round(band_x + period / 2)
    assert 15 < band_x < gap_x < 65

    def alpha(x: int) -> int:
        return image.pixelColor(x, y).alpha()

    assert alpha(band_x) > alpha(gap_x) > 0
    assert alpha(band_x + 80) == alpha(gap_x + 80) > 0
    ramp_row = {alpha(x) for x in range(15, 65)}
    apron_row = {alpha(x) for x in range(95, 145)}
    assert len(ramp_row) >= 2 and len(apron_row) == 1
