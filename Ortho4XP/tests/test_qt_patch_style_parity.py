"""The patch overlay's role→class map, colours, draw order and legend are
the same in both apps (#1244: the Mac app is the authority).  Parses the
Swift sources; offscreen, no network."""

import os
import re
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_Patch_Geometry as GEO  # noqa: E402
import O4_Qt_Patch_Overlay as OV  # noqa: E402


def _swift(rel):
    with open(os.path.join(_ROOT, "Sources", rel), encoding="utf-8") as f:
        return f.read()


def _dict_block(src, name):
    body = src.split(f"static let {name}", 1)[1].split("= [", 1)[1].split("]", 1)[0]
    return dict(re.findall(r'"(\w+)":\s*\.(\w+)', body))


def test_role_and_aeroway_maps_match_mac():
    doc = _swift("SceneryKit/PatchDocument.swift")
    assert GEO._ROLE_CLASSES == _dict_block(doc, "roleClasses")
    assert GEO._AEROWAY_CLASSES == _dict_block(doc, "aerowayClasses")


def _hexa(color):
    return (color.red() << 16 | color.green() << 8 | color.blue(), round(color.alphaF(), 2))


def _parse(h):
    if h == "nil":
        return None
    parts = [p.strip() for p in h.removeprefix("hex(").removesuffix(")").split(",")]
    return (int(parts[0], 16), float(parts[1]) if len(parts) > 1 else 1.0)


def test_colours_widths_match_mac():
    src = _swift("XPTerrainBuilder/PatchOverlay.swift")
    rows = re.findall(r"case \.(\w+): PatchStyle\(fill: (nil|hex\([^)]*\)), "
                      r"stroke: (hex\([^)]*\)), "
                      r"width: ([\d.]+)", src)
    assert {r[0] for r in rows} == set(OV.STYLES)
    for cls, fill, stroke, width in rows:
        qfill, qstroke, qwidth, _ = OV.STYLES[cls]
        assert (None if qfill is None else _hexa(qfill)) == _parse(fill), cls
        assert _hexa(qstroke) == _parse(stroke), cls
        assert qwidth == float(width), cls


def test_draw_order_and_legend_match_mac():
    src = _swift("XPTerrainBuilder/PatchOverlay.swift")
    order = re.search(r"drawOrder: \[PatchStyleClass\] = \[([^\]]*)\]", src).group(1)
    assert GEO.DRAW_ORDER == tuple(re.findall(r"\.(\w+)", order))
    legend = re.search(r"ForEach\(\[PatchStyleClass(\.[^\]]*)\]", src).group(1)
    assert [k for k, _ in OV._LEGEND] == re.findall(r"\.(\w+)", legend)
    labels = dict(re.findall(r'case \.(\w+): "([^"]+)"', src))
    for key, label in OV._LEGEND:
        assert label == labels.get(key, key), key
