"""THE APRON-ON-TAXIWAY CENSUS (lane lkbna15, #2112 / #2134): every APRON
cell of a capture's classification that carries a taxi centreline and holds
no stand, with the rule that made it apron.

Owner 2026-11-17 (#2112, KBNA): "There is no apron near the bridges at
KBNA, only taxiway, so any apron classed pavement there is wrong."  The
census reads the CAPTURED classification (``cap["cl"]``, the tree the
capture was taken on — say so when quoting it) and writes one JSON per
airport:

* ``taxi_m`` — taxi centreline length inside the cell (+1 m), from the
  classification's own ``taxi_centerline`` cut lines;
* stands — 1300 startups and OSM ``aeroway=parking_position|stand`` points
  inside the cell (+2 m); a cell holding one is NOT listed;
* ``reason`` — the rung that made it apron, from the cell's evidence:
  §40 (2) OSM apron cover, §27 airside-edge flip, apron-named source, the
  open default, §59 gap apron;
* ``cover`` — the §40 (2) cell cover where that rung fired;
* ``name_taxi`` — the shipped taxi-name rule (``evidence.taxi_name_match``)
  run on the source description with ``_`` / ``/`` read as separators and
  a ``.pol`` suffix dropped (a pack page path such as
  ``Taxiways/KBNA_Taxiway-H.pol``); ``shipped_name`` — the rule as shipped.

A cell with no centreline is listed only when its source names a taxiway.

    venv/bin/python tools/apron_census.py ICAO CAPTURE.pkl OUT.json

Twin: ``tests/test_apron_census.py``.
"""
from __future__ import annotations

import gzip
import json
import pickle
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

__all__ = ["apron_reason", "pack_name_taxi", "census"]


def apron_reason(ev, ref: str) -> str:
    """The rung that made a cell apron, from its evidence."""
    if ref.startswith("gapapron"):
        return "gap_apron(§59)"
    if ev.get("user_role"):
        return "user_role"
    if ev.get("apron_cover_refused_corridor"):
        return "§40(2) OSM apron cover refuses corridor"
    if ev.get("airside_edge_flip"):
        return f"§27 airside-edge flip (was {ev.get('airside_edge_was')})"
    if ev.get("apron_named"):
        return "apron-named source"
    if "apron_evidence" in ev:
        return "open default: " + str(ev["apron_evidence"])[:60]
    return f"other(kind={ev.get('kind')})"


def pack_name_taxi(desc: str, rules) -> str:
    """The taxi-name rule on a description read with ``_`` / ``/`` as
    separators and a ``.pol`` suffix dropped; ``''`` when it names none."""
    from auto_patch_v2.classify.evidence import taxi_name_match
    d = desc[:-4] if desc.lower().endswith(".pol") else desc
    m = taxi_name_match(re.sub(r"[_/]", " ", d), rules)
    return f"{m[0]} {m[1]}".strip() if m else ""


def census(icao: str, airport, cl) -> dict:
    """The census record of one classification (module doc)."""
    from auto_patch_v2.classify import load_rules
    from auto_patch_v2.classify.evidence import taxi_name_match
    from shapely.geometry import LineString, Point, Polygon
    from shapely.strtree import STRtree
    rules = load_rules()
    to_ll = airport.frame.transformers()[1]
    taxi = [LineString(c.points) for c in cl.cut_lines
            if c.kind == "taxi_centerline" and len(c.points) > 1]
    tt = STRtree(taxi) if taxi else None
    pts = [Point(s.xy) for s in (airport.startups or ())]
    for w in airport.osm_ways:
        if w.tags.get("aeroway") in ("parking_position", "stand"):
            pts += [Point(p) for p in w.points]
    st = STRtree(pts) if pts else None
    src = {s.id: s for s in (getattr(cl, "sources", None) or ())}
    rows, n_apron, a_apron = [], 0, 0.0
    for c in cl.cells:
        if c.role != "apron":
            continue
        p = Polygon(c.ring, c.holes)
        p = p if p.is_valid else p.buffer(0.0)
        n_apron += 1
        a_apron += p.area
        pb = p.buffer(1.0)
        tl = sum(taxi[i].intersection(pb).length for i in tt.query(pb)) if tt is not None else 0.0
        stands = len(st.query(p.buffer(2.0), predicate="contains")) if st is not None else 0
        s = src.get(c.ref.split("#")[0]) or src.get(c.ref)
        desc = getattr(s, "description", "") or ""
        nt = pack_name_taxi(desc, rules)
        if stands or (tl <= 1.0 and not nt):
            continue
        lat, lon = to_ll(*p.representative_point().coords[0])
        rows.append(dict(id=c.id, ref=c.ref, area=round(p.area), taxi_m=round(tl, 1),
                         width=round(p.area / max(tl, 1.0), 1),
                         reason=apron_reason(c.evidence, c.ref), desc=desc,
                         name_taxi=nt, shipped_name=bool(taxi_name_match(desc, rules)),
                         cover=round(float(c.evidence.get("cell_apron_cover", -1)), 2),
                         ll=[round(lat, 6), round(lon, 6)]))
    return dict(icao=icao, n_apron=n_apron, area_apron=round(a_apron), rows=rows)


def main(argv: list[str]) -> int:
    icao, path, out = argv
    with (gzip.open if path.endswith(".gz") else open)(path, "rb") as fh:
        cap = pickle.load(fh)
    if "cl" not in cap or "airport" not in cap:
        print(f"{icao}: {path} carries no classification (an older capture format)")
        return 1
    rec = dict(census(icao, cap["airport"], cap["cl"]), path=path)
    Path(out).write_text(json.dumps(rec))
    print(icao, rec["n_apron"], len(rec["rows"]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
