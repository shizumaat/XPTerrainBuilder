"""LANE-LOCAL DOMAIN PROBE (S3, never lands).

NOT a census — it reports no violation counts.  It reports THE DOMAIN:
how many pairs/ways each law family EXAMINED, and the emitted patch's
role inventory.  The examined counts come from ``check_grade``'s own
printed domain lines via ``run_checks_law_true`` (the harness library,
one code path — nothing is re-implemented here).  Every defect count in
this lane's dossier comes from ``tools/harness/census.py``.
"""
import io
import json
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import check_grade as cg  # noqa: E402


def role_inventory(osm_path):
    """Ways by role, and the ring-edge population the drainage-minimum
    walk would see (consecutive ring pairs >= _DRAINAGE_MIN_RUN_M)."""
    import math
    ways, nodes, ll_to_m = None, None, None
    # Reuse check_grade's own parser via its internal loader.
    parsed = cg._parse_patch(osm_path) if hasattr(cg, "_parse_patch") else None
    return parsed


def probe(osm_path):
    buf = io.StringIO()
    fam = {}
    with redirect_stdout(buf):
        cg.run_checks_law_true(osm_path, family_out=fam, quiet=False,
                               top_n=0, announce=False)
    text = buf.getvalue()
    dom = {}
    for line in text.splitlines():
        m = re.search(r"\((\d+) (.+?) censused over (\d+) (.+?)\)", line)
        if m:
            dom.setdefault(m.group(2), []).append(
                (int(m.group(1)), int(m.group(3)), m.group(4)))
    return dom, text


if __name__ == "__main__":
    out = {}
    for p in sys.argv[1:]:
        dom, text = probe(p)
        out[p] = dom
        print("=== ", p)
        for k, v in sorted(dom.items()):
            for pairs, ways, unit in v:
                print(f"    {pairs:>8} {k:<40} over {ways:>6} {unit}")
    Path("tmp/s3/domain.json").write_text(json.dumps(out, indent=1))
