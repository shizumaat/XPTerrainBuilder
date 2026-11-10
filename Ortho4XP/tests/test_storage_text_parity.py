"""Settings > Storage's budget and installed-tiles words are the same in
both apps (``O4_Storage_Text`` and ``Sources/SceneryKit/StorageText.swift``),
and every figure reaches a line."""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Storage_Text as TEXT  # noqa: E402
import pytest  # noqa: E402

SWIFT = (Path(__file__).resolve().parents[2] / "Sources" / "SceneryKit"
         / "StorageText.swift")


def _camel(name: str) -> str:
    head, *rest = name.lower().split("_")
    return head + "".join(part.title() for part in rest)


@pytest.mark.skipif(not SWIFT.is_file(), reason="no app tree")
def test_swift_says_what_python_says():
    swift = dict(re.findall(r'public static let (\w+) = "((?:[^"\\]|\\.)*)"',
                            SWIFT.read_text(encoding="utf-8")))
    python = {_camel(name): getattr(TEXT, name) for name in TEXT.__all__
              if isinstance(getattr(TEXT, name), str)}
    assert swift == python


def test_lines_fill_every_slot():
    line, warning = TEXT.budget_lines({
        "budget_bytes": 100e9, "used_bytes": 120e9, "floor_bytes": 140e9,
        "recommended_bytes": 210e9, "under_floor": True})
    assert "120.00 GB of 100.00 GB" in line and "210.00 GB" in warning
    assert "{" not in line + warning
    assert TEXT.budget_lines({"budget_bytes": 0, "used_bytes": 1e9})[1] == ""
    lines = TEXT.installed_lines({"measured": True, "local_count": 12,
                                  "local_bytes": 9.78e9, "linked": [
                                      {"volume": "Ortho8TB", "count": 140,
                                       "mounted": False}]})
    assert lines == ["12 folder(s) on this disk: 9.78 GB",
                     "140 linked to Ortho8TB (not connected), not measured"]
    assert TEXT.ondemand_warning({"over_at_floor": True, "floor_bytes": 2e9,
                                  "cap_bytes": 1e9}).startswith("Your on-demand")
