"""padreview2 C: every unit DECK print in a capture's pack partition, read exactly as planar/landing.py reads it —
the deck's lowest authored y (the band's foot under the landed rule) — and classed under F1 / F1b:
  foot  : -BAND_M <= y_land <= +BAND_M  (a landing is minted)
  below : y_land < -BAND_M              (landing_below_unit, R-L)
  above : y_land > +BAND_M              (landing_above_unit, F1b)
usage: venv/bin/python decks.py CAPTURE.pkl"""
import pickle, sys
sys.path.insert(0, "src")
from auto_patch_v2.planar import landing as L
from auto_patch_v2.airport import bridge_family as bf
with open(sys.argv[1], "rb") as fh:
    cap = pickle.load(fh)
icao, airport = cap["icao"], cap["airport"]
part = getattr(airport, "partition", None)
if part is None:
    print(icao, "NO PARTITION in capture"); sys.exit(0)
n_deck = sum(1 for u in part.units for m in u.members if getattr(m, "deck_kind", "") in ("flag", "signature"))
prints = L._prints(part)
print(f"{icao}: units {len(part.units)}, deck members {n_deck}, deck prints {len(prints)}")
cls = {"foot": 0, "below": 0, "above": 0, "none": 0}
for p in prints:
    pieces = bf.landing_pieces(p, L.BAND_M)
    if not pieces:
        cls["none"] += 1; continue
    ys = [y for _r, y in pieces]
    y_land = min(ys)
    ally = [y for t in p.ys for y in t]
    k = "foot" if -L.BAND_M <= y_land <= L.BAND_M else ("below" if y_land < -L.BAND_M else "above")
    cls[k] += 1
    u = part.units[p.unit]
    print(f"  unit {p.unit:4d} members {len(u.members):4d}  {k:5s} y_land {y_land:+7.2f}  authored y {min(ally):+7.2f}..{max(ally):+7.2f}  pieces {len(pieces):4d}  {p.key}")
print(icao, "classes", cls)
