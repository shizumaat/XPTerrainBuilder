"""A QPainter never paints over a temporary device (#2004 CI segfault).

``QPainter(QImage(...))`` hands the painter an image nothing holds: Python
frees it and the painter writes into freed memory.  Ubuntu's offscreen Qt
suite crashed on exactly that in ``test_qt_live_preview.py`` (runs
42915398276 and 42922505498).  The device must be bound to a name first.
"""
from __future__ import annotations

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOTS = (os.path.join(HERE, "..", "src"), HERE)
TEMPORARY_DEVICE = re.compile(
    r"QPainter\(\s*Q(?:Image|Pixmap|Picture|Bitmap)\(")


def test_no_painter_is_built_over_a_temporary_device():
    hits = []
    for root in ROOTS:
        for folder, _dirs, files in os.walk(root):
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8") as handle:
                    for number, line in enumerate(handle, 1):
                        if TEMPORARY_DEVICE.search(line):
                            hits.append(f"{os.path.relpath(path, HERE)}:{number}")
    hits = [h for h in hits if not h.startswith("test_painter_device_held.py")]
    assert hits == [], hits
