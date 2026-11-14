"""#2063 round 2 (``2063-round2-spec.md`` steps 1, 2, 4): what a companion
pack may adopt.

* THE EXCLUSION WITNESS (``airport/exclusion``): a row inside a
  ``sim/exclude_obj`` box of a pack X-Plane draws ABOVE the companion is
  never drawn and never adopted (``companion._drawn``); a pack BELOW never
  excludes it.
* THE SERVED-AIRPORT CLAIM (``object_window.own_claim(served=...)``,
  ``served_airports``): an airport the pack serves without defining it
  (#1630) claims its read area like the pack's own apt.dat airports.
* THE ``also`` WITNESS, TIGHTENED (``companion._feet``): an anchor outside
  the airport is admitted only when EVERY ground-contact foot of its file
  stands inside.
"""
from __future__ import annotations

import os
import types

import O4_DSF_Binary as DSFB
import O4_World_Pack as WP
from auto_patch_v2.airport import companion as C
from auto_patch_v2.airport import exclusion as X
from auto_patch_v2.airport import object_window as W
from auto_patch_v2.model.frame import Frame
from shapely.geometry import Point, box

LAT, LON = 47, -123


def _pack(scenery, name, props=()):
    path = os.path.join(scenery, name, WP.dsf_relpath(LAT, LON))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = DSFB.placeholder_bytes(LAT, LON, "WorldEditor")
    if props:
        data = DSFB.rewrite(data, props=lambda pairs: pairs + list(props))
    with open(path, "wb") as fh:
        fh.write(data)
    return os.path.join(scenery, name)


def _ini(scenery, *names):
    with open(os.path.join(scenery, "scenery_packs.ini"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("I\n1000 Version\nSCENERY\n\n" + "".join(
            f"SCENERY_PACK Custom Scenery/{n}/\n" for n in names))


EXCL = ("sim/exclude_obj", "-122.21/47.49/-122.20/47.50")


def _world(tmp_path):
    scenery = os.path.join(str(tmp_path), "X-Plane", "Custom Scenery")
    upper = _pack(scenery, "a upper airport", [EXCL])
    lower = _pack(scenery, "b lower companion",
                  [("sim/exclude_obj", "-122.30/47.40/-122.29/47.41")])
    _ini(scenery, "a upper airport", "b lower companion")
    return upper, lower


def _row(lon, lat, path="o/plane.obj"):
    return types.SimpleNamespace(def_path=path, lon=lon, lat=lat, heading_deg=0.0,
                                 elevation=None, kind="OBJECT")


def test_a_higher_packs_exclusion_box_is_read_a_lower_one_is_not(tmp_path):
    upper, lower = _world(tmp_path)
    got = X.boxes_above(lower, LAT, LON)
    assert got == [("a upper airport", (-122.21, 47.49, -122.20, 47.50))]
    assert X.boxes_above(upper, LAT, LON) == []       # the lower pack's box never
    assert X.excluder_of(got, -122.205, 47.495) == "a upper airport"
    assert X.excluder_of(got, -122.215, 47.495) is None


def test_a_row_under_a_higher_packs_exclusion_is_not_adopted(tmp_path):
    _upper, lower = _world(tmp_path)
    said = []
    rows = [(0, _row(-122.205, 47.495)), (1, _row(-122.215, 47.495))]
    kept = C._drawn(rows, lower, LAT, LON, "b lower companion", said.append)
    assert [i for i, _pl in kept] == [1]
    assert said == ["  [companion] b lower companion: 1 row(s) under a upper "
                    "airport's exclusion — not drawn, left alone"]


def test_an_unreadable_header_reads_as_no_exclusion(tmp_path):
    scenery = os.path.join(str(tmp_path), "X-Plane", "Custom Scenery")
    upper = os.path.join(scenery, "a upper airport")
    path = os.path.join(upper, WP.dsf_relpath(LAT, LON))
    os.makedirs(os.path.dirname(path))
    with open(path, "wb") as fh:
        fh.write(b"not a dsf")
    lower = _pack(scenery, "b lower companion")
    _ini(scenery, "a upper airport", "b lower companion")
    assert X.boxes_above(lower, LAT, LON) == []


APT = """I
1200 synthetic
1 100 0 0 ZQQC Charlie
100 45.00 1 0 0.25 1 2 0 09 47.5300 -122.3100 0 0 3 0 0 0 27 47.5300 -122.2900 0 0 3 0 0 0
99
"""


def _apt(tmp_path):
    from auto_patch_v2.airport import apt_dat as A
    p = os.path.join(str(tmp_path), "apt.dat")
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(APT)
    return p, A.parse_airport_block(A.read_airport_block(p, "ZQQC"))


def test_a_served_airport_claims_its_read_area(tmp_path):
    _p, served = _apt(tmp_path)
    to_xy = Frame("ZQQB", (47.5, -122.20), 9).transformers()[0]
    claim = W.own_claim(None, (47.5, -122.20), to_xy, 1000.0, 0.05, served=(served,))
    assert claim.contains(Point(*to_xy(-122.30, 47.53)))      # on its runway
    assert not claim.contains(Point(*to_xy(-122.20, 47.50)))  # this airport
    assert W.own_claim(None, (47.5, -122.20), to_xy, 1000.0, 0.05) is None


def test_served_airports_are_the_ones_select_pack_gives_this_pack(tmp_path, monkeypatch):
    import O4_Airport_Apt_Identity as ident
    from auto_patch_v2.airport import pack as P
    p, _served = _apt(tmp_path)
    scenery = os.path.join(str(tmp_path), "X-Plane", "Custom Scenery")
    root = _pack(scenery, "b lower companion")
    other = _pack(scenery, "c other")

    def e(code, la, lo):
        return types.SimpleNamespace(code=code, lat=la, lon=lo)
    monkeypatch.setattr(ident, "tile_apt_dat_airports", lambda *a, **k: [
        e("ZQQB", 47.5, -122.2), e("ZQQC", 47.53, -122.30),
        e("ZQQD", 47.53, -122.30), e("ZQQF", 49.9, -122.3)])
    picks = {"ZQQC": root, "ZQQD": other, "ZQQF": root}
    monkeypatch.setattr(P, "select_pack", lambda xp, code, law=None: types.SimpleNamespace(
        root=picks.get(code, other), apt_dat_path=p))
    got = W.served_airports(root, "ZQQB", LAT, LON, (47.5, -122.2))
    # ZQQB is this airport; ZQQD is served by another pack; ZQQF is far away
    assert len(got) == 1 and got[0].reference_point()[0] == 47.53


def _obj(path, verts):
    tris = [(i, i + 1, i + 2) for i in range(len(verts) - 2)]
    idx = [i for t in tris for i in t]
    out = ["I", "800", "OBJ", "", "TEXTURE\tt.dds",
           f"POINT_COUNTS\t{len(verts)} 0 0 {len(idx)}", ""]
    out += [f"VT\t{x:.3f} {y:.3f} {z:.3f}\t0 1 0\t0 0" for x, y, z in verts]
    out += [f"IDX\t{q}" for q in idx]
    out += ["", f"TRIS\t0 {len(idx)}"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(out) + "\n")


def test_also_reads_every_ground_contact_foot(tmp_path, monkeypatch):
    """A file anchored outside whose every low vertex stands inside is
    admitted; one with a wheel outside is not (round 2 read the box centre
    and admitted both)."""
    scenery = os.path.join(str(tmp_path), "X-Plane", "Custom Scenery")
    main = _pack(scenery, "a main")
    root = _pack(scenery, "b lower companion")
    os.makedirs(os.path.join(root, "o"))
    # two aircraft 30 m apart, wheels at y=0, a fuselage vertex at y=2
    _obj(os.path.join(root, "o", "in.obj"), [(100, 0, 0), (101, 0, 0), (100, 0, 1),
                                               (130, 0, 0), (131, 0, 1), (115, 2, 0)])
    _obj(os.path.join(root, "o", "out.obj"), [(100, 0, 0), (101, 0, 0), (100, 0, 1),
                                                (300, 0, 0), (301, 0, 1), (200, 2, 0)])
    assert len(C._feet(os.path.join(root, "o", "in.obj"), 1.0)) == 5   # no fuselage
    fr = Frame("ZQQB", (47.5, -122.2), 9)
    x0, y0 = fr.transformers()[0](-122.2, 47.5)
    monkeypatch.setattr(C, "_region", lambda a: box(x0 + 50, y0 - 50, x0 + 200, y0 + 50))
    monkeypatch.setattr(C, "dump_candidates", lambda *a, **k: [root])
    monkeypatch.setattr(C._dsf, "find_text_dump", lambda *a, **k: "dump")
    monkeypatch.setattr(C._dsf, "read_dump", lambda *a, **k: types.SimpleNamespace(
        placements=[_row(-122.2, 47.5, "o/in.obj"), _row(-122.2, 47.5, "o/out.obj")]))
    monkeypatch.setattr(C, "served_airports", lambda *a, **k: ())
    ap = types.SimpleNamespace(pack=types.SimpleNamespace(pack_root=main), frame=fr,
                               icao="ZQQB")
    found = C.find(ap, "cache", LAT, LON, margin_m=1000.0, band_m=1.0)
    assert [[pl.def_path for _i, pl in c.rows] for c in found] == [["o/in.obj"]]
