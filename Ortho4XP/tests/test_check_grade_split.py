"""THE ``check_grade`` SPLIT IS A PURE MOVE (issue #857, B3-25;
``docs/specs/code-quality-beta3-spec.md`` §3).

``tools/check_grade.py`` is being cut into ``tools/check_grade_lib/`` (one
module per law family, the sidecar context in ``context.py``) a few
families per lane.  Each cut must change NOTHING a reader sees, so this
twin pins three things against a snapshot taken from ``main`` BEFORE the
first cut (``fixtures/check_grade_split/snapshot.json``):

1. ``LAW_FAMILIES`` — the ordered register, every ``(key, title, bucket)``
   exactly (the census, the families table and ``family_out`` all iterate
   it, so its ORDER is the contract).
2. Every top-level name ``check_grade`` exported on main is still an
   attribute of ``check_grade`` — importers (``from check_grade import X``,
   by-path loads, the census) keep working.
3. The law-true rows of every family on a committed synthetic patch
   (``fixtures/repro_mini.patch.osm`` with a sidecar carrying records for
   the sidecar-declared families the cuts move) hash to the main digest:
   the census output cannot move while this holds.

A later cut regenerates nothing: the snapshot is main's, frozen.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

cg = pytest.importorskip("check_grade")

FIXTURES = ROOT / "tests" / "fixtures"
SNAPSHOT = FIXTURES / "check_grade_split" / "snapshot.json"
EXTRA_RECORDS = FIXTURES / "check_grade_split" / "sidecar_records.json"


def _synthetic_patch(dest: Path) -> Path:
    """``repro_mini`` plus the sidecar records of the moved families."""
    osm = dest / "repro_split.patch.osm"
    shutil.copyfile(FIXTURES / "repro_mini.patch.osm", osm)
    side = json.loads((FIXTURES / "repro_mini.patch.osm.axes.json")
                      .read_text(encoding="utf-8"))
    side.update(json.loads(EXTRA_RECORDS.read_text(encoding="utf-8")))
    Path(str(osm) + ".axes.json").write_text(
        json.dumps(side), encoding="utf-8", newline="\n")
    return osm


#: A float in a row's repr, printed at 6 decimals before hashing: the libm
#: of each OS differs in the last digits (Windows CI moved one
#: ``runway_end_skirt`` row by an ulp), and a pure move changes no digit.
_FLOAT = re.compile(r"-?\d+\.\d+(?:e[-+]?\d+)?")


def _canonical(row) -> str:
    return _FLOAT.sub(lambda m: f"{float(m.group()):.6f}", repr(row))


def family_rows_digest(osm: Path) -> dict:
    """Per family: the row count and the sha256 of the rows' reprs."""
    family_out: dict = {}
    cg.run_checks_law_true(osm, family_out=family_out)
    return {key: [len(rows), hashlib.sha256(
        "\n".join(_canonical(r) for r in rows).encode("utf-8")).hexdigest()]
        for key, rows in family_out.items()}


def snapshot(tmp: Path) -> dict:
    """What the frozen snapshot records (run on main to write it)."""
    return {
        "law_families": [list(row) for row in cg.LAW_FAMILIES],
        "names": sorted(n for n in vars(cg) if not n.startswith("__")),
        "family_rows": family_rows_digest(_synthetic_patch(tmp)),
    }


@pytest.fixture(scope="module")
def frozen() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_law_families_order_and_rows_are_mains(frozen):
    assert [list(row) for row in cg.LAW_FAMILIES] == frozen["law_families"]


def test_every_name_main_exported_is_still_exported(frozen):
    missing = [n for n in frozen["names"] if not hasattr(cg, n)]
    assert missing == []


def test_every_family_row_is_mains_on_the_synthetic_patch(frozen, tmp_path):
    got = family_rows_digest(_synthetic_patch(tmp_path))
    # the moved families must actually be exercised by the patch
    for key in ("platform_rim_relief", "platform_refused", "hard_conflict",
                "pad_frontage_hold", "pad_frontage_infeasible",
                "pad_cluster_mismatch", "pad_airside_renode", "jetway_strip",
                "seam_residual", "road_coverage_join"):
        assert got[key][0] > 0, key
    assert got == frozen["family_rows"]


if __name__ == "__main__":                       # write the snapshot (main only)
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(snapshot(Path(d)), indent=1) + "\n",
                            encoding="utf-8", newline="\n")
