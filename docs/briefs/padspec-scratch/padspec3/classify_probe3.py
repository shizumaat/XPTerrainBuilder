"""padspec3 scratch probe — §56 on the REAL classify (extends pads56/classify_probe.py).

Arms (`--arm`): `today` = the landed code (4 (b) keeps wall-extended routes);
`absorb_all` = 4 (b) deleted (wall_extended=None); `nosimp` = rule 2b and the
absorption both disarmed (the rule-2 base, for the gap-piece attribution).

Prints, on top of the pads56 probe's numbers:
(a) per same-id pad that GROWS under rule 2b: the added area split into hole
    fill / closing fill / straightening residue, and its overlap with other
    units' rule-2 outlines;
(b) per absorbing pad: the added area split into absorbed road / deck shade /
    airside cell / other pad / the rest (stand-off + notch fill);
    the site's road cells and pad vertices; the kept routes' retaining pieces.
usage (from Ortho4XP/): venv/bin/python <this> ICAO CAPTURE.pkl --arm today
       [--site LAT LON R] [--base-cells OUT.pkl] [--diff-gaps BASE.pkl] [unit-id ...]
"""
from __future__ import annotations
import argparse, dataclasses as dc, pickle, sys, time
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pads56"))
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from auto_patch_v2.airport import frame_entry as fe
from auto_patch_v2.airport.obj8 import ResourceCache
from auto_patch_v2.classify import classify, load_rules, roles
from auto_patch_v2.classify import road_absorb as ra
from auto_patch_v2.classify import retaining_wall as rw
from auto_patch_v2.geom import deck_shades
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import pad_outline, role_side
from auto_patch_v2.planar.cluster import clusters as derive_clusters
from classify_probe import outlines  # pads56 probe, reused


def nv(g):
    return len(g.exterior.coords) - 1 + sum(len(h.coords) - 1 for h in g.interiors)


def poly(c):
    return Polygon(c.ring, c.holes)


def growth_split(t, s, close_m):
    """(a): what the rule-2b growth of a same-id pad is made of."""
    added = s.difference(t)
    if added.is_empty:
        return None
    holes = unary_union([Polygon(h) for h in t.interiors]) if t.interiors else Polygon()
    closing = t.buffer(close_m).buffer(-close_m).difference(t)
    hole_fill = added.intersection(holes).area
    close_fill = added.difference(holes).intersection(closing).area
    rest = added.area - hole_fill - close_fill
    return dict(added=added.area, hole_fill=hole_fill, close_fill=close_fill, dp_rest=rest, geom=added)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("icao"); ap.add_argument("pkl", type=Path)
    ap.add_argument("--arm", default="today", choices=("today", "absorb_all", "nosimp"))
    ap.add_argument("--site", nargs=3, type=float, default=None)
    ap.add_argument("--base-cells", type=Path, default=None, help="pickle the arm's cells here")
    ap.add_argument("--diff-gaps", type=Path, default=None, help="a cells pickle to diff gap cells against")
    ap.add_argument("--skip-a", action="store_true")
    ap.add_argument("units", nargs="*")
    a = ap.parse_args()
    icao = a.icao
    cap = pickle.load(a.pkl.open("rb")); airport = cap["airport"]
    law = Law.for_airport(icao)
    airport = dc.replace(airport, clusters=derive_clusters(airport, law))
    po = pad_outline(law)
    if not a.skip_a:
        t, c0, _ = outlines(airport, law, None)
        s, c1, st = outlines(airport, law, po)
        print(f"[{icao}] (a) pads {c0['pads']} -> {c1['pads']}; vertices {c1['outline_vertices_in']} -> "
              f"{c1['outline_vertices_out']} over {c1['outline_simplified']}")
        others = {k: v for k, v in t.items()}
        print("  same-id growth (> 0.5 %) split: id, +%, added m2 = hole_fill / close_fill / dp_rest; over other units m2; joined")
        for k in sorted(s, key=lambda k: -(s[k].area / t[k].area) if k in t else 0):
            if k not in t or s[k].area <= 1.005 * t[k].area:
                continue
            g = growth_split(t[k], s[k], po.close_m)
            if g is None:
                continue
            ov = sum(g["geom"].intersection(others[j]).area for j in others if j != k and others[j].intersects(g["geom"]))
            joined = st.get(k, {}).get("outline_joined_from") or []
            print(f"    {k:18s} +{100 * (s[k].area / t[k].area - 1):6.1f} %  {g['added']:8.0f} = {g['hole_fill']:7.0f} / "
                  f"{g['close_fill']:7.0f} / {g['dp_rest']:6.0f}; other units {ov:6.1f}; joined {joined if len(joined) > 1 else '-'}")
        for k in a.units:
            if k in st:
                print(f"  {k}: {st[k]} holes {len(s[k].interiors)} area {s[k].area:,.0f}")
    # (b) the real classify
    rules = load_rules()
    cache = lambda: ResourceCache(law.tables.structures.basin.min_solid_thickness_m, fe.quantum(law))
    real = roles.pad_outline
    from auto_patch_v2.classify import evidence as _ev
    real_ev = _ev.pad_outline
    if a.arm == "nosimp":
        off = lambda l: dc.replace(real(l), close_m=0.0, chord_m=0.0, hole_min_m2=0.0, road_absorb_m=0.0)
        roles.pad_outline = off; _ev.pad_outline = off   # the mint reads evidence's import
    seen = {}
    real_abs = ra.absorb_near_roads
    def spy(cells, law_, outline, **kw):
        if a.arm == "absorb_all":
            kw["wall_extended"] = None
        seen.update(kw, cells=list(cells)); return real_abs(cells, law_, outline, **kw)
    ra.absorb_near_roads = spy
    real_ext = rw.road_extension
    def spy_ext(pieces, ribbon, lane_m):
        seen["pieces"] = list(pieces); return real_ext(pieces, ribbon, lane_m)
    rw.road_extension = spy_ext
    t0 = time.perf_counter(); arm = classify(airport, law, rules, cache=cache())
    ra.absorb_near_roads = real_abs; roles.pad_outline = real; rw.road_extension = real_ext
    _ev.pad_outline = real_ev
    absorbed = {k: list(v) for k, v in ra.ROADS_ABSORBED.items()}; kept = list(ra.ROADS_KEPT)
    print(f"[{icao}] (b) arm {a.arm}: classify {time.perf_counter() - t0:.0f} s; cells {len(arm.cells)}; "
          f"roads absorbed {sum(map(len, absorbed.values()))} into {len(absorbed)} pads; kept {len(kept)}; "
          f"gap pieces {sum(1 for c in arm.cells if roles.is_late_cell(c))}; pads {sum(1 for c in arm.cells if c.role == 'building')}")
    pre = seen.get("cells", [])
    pre_by = {c.ref: c for c in pre}
    to_xy = airport.frame.entry()
    shades = deck_shades(getattr(airport, "partition", None), to_xy)
    airside = unary_union([poly(c) for c in pre if c.side == "airside"]) if pre else Polygon()
    gone = {r for v in absorbed.values() for r in v}
    print("  absorbing pads: ref: n roads; area +%; vertices; added m2 = road / shade / airside / other pad / rest")
    for p, v in absorbed.items():
        a0 = poly(pre_by[p]); a1 = next(poly(c) for c in arm.cells if c.ref == p and c.role == "building")
        added = a1.difference(a0)
        roads_u = unary_union([poly(pre_by[r]) for r in v if r in pre_by])
        on_road = added.intersection(roads_u).area
        on_shade = added.difference(roads_u).intersection(shades).area if shades is not None and not shades.is_empty else 0.0
        on_air = added.difference(roads_u).intersection(airside).area
        other = [poly(c) for c in pre if c.role == "building" and c.ref != p and poly(c).intersects(added)]
        on_pad = added.difference(roads_u).intersection(unary_union(other)).area if other else 0.0
        rest = added.area - on_road - on_shade - on_air - on_pad
        print(f"    {p:12s}: {len(v):2d}; {a0.area:9,.0f} -> {a1.area:9,.0f} (+{100 * (a1.area / a0.area - 1):4.1f} %); v {nv(a0):4d} -> {nv(a1):4d}; "
              f"{added.area:6.0f} = {on_road:6.0f} / {on_shade:5.0f} / {on_air:5.0f} / {on_pad:5.0f} / {rest:6.0f}  {v if len(v) <= 6 else str(len(v)) + ' roads'}")
    we = seen.get("wall_extended")
    print(f"  kept {len(kept)}: ", [(r, p, w) for r, p, w in kept][:20])
    if kept and we is not None and not we.is_empty and a.arm == "today":
        # which retaining pieces extend the kept routes
        pieces = seen.get("pieces", []); lane_m = float(rules.service.retaining_wall_reach_m)
        if pieces:
            for r, p, w in kept:
                g = pre_by.get(r)
                if g is None or w != ra.KEPT_WALL:
                    continue
                gp = poly(g)
                near = [(rp.resource.split('/')[-1], round(rp.poly.distance(gp), 1), round(rp.height_m, 1)) for rp in pieces if rp.poly.distance(gp) <= lane_m + 1.0]
                print(f"    {r}: area {gp.area:5.0f} m2, in extension {gp.intersection(we).area:5.1f} m2; pieces {near[:4]}")
    if a.site:
        lat, lon, R = a.site; pt = Point(to_xy(lon, lat))
        fam = {"service_road", "service_junction"}
        near0 = [c for c in pre if c.role in fam and poly(c).distance(pt) <= R]
        near1 = [c for c in arm.cells if c.role in fam and poly(c).distance(pt) <= R]
        print(f"  site: road cells {len(near0)} -> {len(near1)}; left {sorted(c.ref for c in near1)}; "
              f"left area {sum(poly(c).area for c in near1):,.0f} m2, vertices {sum(len(c.ring) for c in near1)}")
        for c in arm.cells:
            if c.role == "building" and poly(c).distance(pt) <= 1.0:
                print(f"  site pad {c.ref}: vertices {len(c.ring) + sum(map(len, c.holes))} holes {len(c.holes)} area {poly(c).area:,.0f}")
        byrole = {}
        for c in arm.cells:
            if poly(c).distance(pt) <= R:
                byrole.setdefault(c.role, [0, 0]); byrole[c.role][0] += 1; byrole[c.role][1] += len(c.ring) + sum(map(len, c.holes))
        print("  site cells by role (n, vertices):", dict(sorted(byrole.items(), key=lambda kv: -kv[1][1])))
    if a.base_cells:
        pickle.dump([(c.role, c.ref, c.ring, c.holes, c.side) for c in arm.cells], a.base_cells.open("wb"))
    if a.diff_gaps:
        base = pickle.load(a.diff_gaps.open("rb"))
        bgap = {(r, ref): Polygon(ring, holes) for r, ref, ring, holes, _s in base if str(ref).startswith("gap:")}
        agap = {(c.role, c.ref): poly(c) for c in arm.cells if str(c.ref).startswith("gap:")}
        pads_arm = [(c.ref, poly(c)) for c in arm.cells if c.role == "building"]
        bpads = {ref: Polygon(ring, holes) for r, ref, ring, holes, _s in base if r == "building"}
        print(f"  gap cells {len(bgap)} -> {len(agap)}; lost {len(set(bgap) - set(agap))}, new {len(set(agap) - set(bgap))}")
        if a.site:
            for k in sorted(set(bgap) - set(agap)):
                g = bgap[k]
                if g.distance(pt) > R * 2:
                    continue
                cover = [(ref, round(g.intersection(pp).area, 1)) for ref, pp in pads_arm if pp.intersects(g)]
                grew = [(ref, round(pp.area - bpads[ref].area)) for ref, pp in pads_arm if ref in bpads and pp.intersects(g)]
                print(f"    lost {k} area {g.area:,.0f} m2 at {g.distance(pt):.0f} m: covered by pads {cover}; those pads grew {grew}")


if __name__ == "__main__":
    main()
