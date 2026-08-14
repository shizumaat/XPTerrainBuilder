"""S1f item 1 — what is welded at the endpoints the LATE projection moved.

Reads the CONTROL patch's raw way table (every way, features included —
``check_grade._parse_osm`` drops open breaklines and non-pavement ways, and
the question here is exactly "what ELSE stands at this node"), and reports,
per moved / stationary endpoint of the 134 new ``apron|apron`` rows, which
shapes share that node.  Derives no law and counts no defects.
"""
import json
import re
import sys
from collections import Counter

_NODE_RE = re.compile(r"<node id='(-?\d+)'[^>]*lat='([-0-9.]+)' lon='([-0-9.]+)'")
_WAY_RE = re.compile(r"<way id='(-?\d+)'.*?>(.*?)</way>", re.S)
_ND_RE = re.compile(r"<nd ref='(-?\d+)'")
_TAG_RE = re.compile(r"<tag k='([^']*)' v='([^']*)'")


def load(path):
    txt = open(path).read()
    nodes = {m.group(1): (float(m.group(2)), float(m.group(3)))
             for m in _NODE_RE.finditer(txt)}
    at = {}
    for m in _WAY_RE.finditer(txt):
        wid, body = m.group(1), m.group(2)
        tags = dict(_TAG_RE.findall(body))
        label = (tags.get("o4_role") or tags.get("o4_feature")
                 or tags.get("aeroway") or tags.get("highway") or "?")
        for nid in _ND_RE.findall(body):
            at.setdefault(nid, set()).add((label, wid))
    by_ll = {}
    for nid, (la, lo) in nodes.items():
        by_ll[(f"{la:.11f}", f"{lo:.11f}")] = nid
    return nodes, at, by_ll


def main():
    ctl, join = sys.argv[1], sys.argv[2]
    nodes, at, by_ll = load(ctl)
    recs = json.load(open(join))
    moved_lbl, still_lbl = Counter(), Counter()
    moved_n, still_n = 0, 0
    pair_kind = Counter()
    for r in recs:
        kinds = []
        for e in r["ends"]:
            nid = by_ll.get((f"{e['lat']:.11f}", f"{e['lon']:.11f}"))
            labels = frozenset(l for l, _ in at.get(nid, ()))
            d = (None if e["ctl"] is None or e["mid"] is None
                 else abs(e["ctl"] - e["mid"]))
            movedq = d is not None and d > 0.005
            if movedq:
                moved_n += 1
                moved_lbl[tuple(sorted(labels))] += 1
            else:
                still_n += 1
                still_lbl[tuple(sorted(labels))] += 1
            kinds.append("MOVED" if movedq else "still")
        pair_kind[tuple(kinds)] += 1
    print(f"endpoints MOVED by the late call: {moved_n}")
    for k, v in moved_lbl.most_common(12):
        print(f"   {v:4d}  {'+'.join(k)}")
    print(f"endpoints the late call left alone: {still_n}")
    for k, v in still_lbl.most_common(12):
        print(f"   {v:4d}  {'+'.join(k)}")
    print("pair shape:", dict(pair_kind))


if __name__ == "__main__":
    main()
