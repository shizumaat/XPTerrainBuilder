#!/usr/bin/env python3
"""USA elevation-gap census (issue #151): airports whose aerodrome footprint
has no published USGS 3DEP 1 m DEM, cross-referenced with the US
Interagency Elevation Inventory (USIEI) for other lidar holders.

The gap instrument is the TNM 1 m listing -- the discovery the engine's
USGS3DEP.elv runs -- as footprint share inside listed tile boxes; WESM work
units (published 1 m share, pending units = IN-WORK) are the second
instrument and their disagreements are printed.  Downloads cache in --out.
"""
import argparse
import concurrent.futures as cf
import csv
import json
import math
import os
import re
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Iterator

import requests
from osgeo import gdal, ogr
from shapely import wkb as shp_wkb
from shapely.affinity import scale
from shapely.geometry import MultiPoint, Polygon, box, mapping, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

ogr.UseExceptions()
gdal.UseExceptions()
WESM_URL = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/metadata/WESM.gpkg"
USIEI_URL = ("https://coast.noaa.gov/arcgis/rest/services/USInteragencyElevationInventory/"
             "USIEIv2/MapServer/2")
TNM_URL = ("https://tnmaccess.nationalmap.gov/api/v1/products?datasets={ds}"
           "&bbox={w},{s},{e},{n}&outputFormat=JSON&max=1000")
TNM_DS = {"1m": "Digital%20Elevation%20Model%20(DEM)%201%20meter",
          "lpc": "Lidar%20Point%20Cloud%20(LPC)",
          "opr": "Original%20Product%20Resolution%20(OPR)%20Digital%20Elevation%20Model%20(DEM)",
          "ned19": "National%20Elevation%20Dataset%20(NED)%201/9%20arc-second"}
WESM_FIELDS = ("workunit", "project", "ql", "collect_start", "collect_end", "lpc_pub_date",
               "lpc_category", "onemeter_category", "onemeter_reason")
PAVED = {1, 2} | set(range(20, 39)) | set(range(50, 58))
REGIONS = {"CONUS": (-125.0, 24.0, -66.5, 49.5), "AK": (-180.0, 51.0, -129.0, 72.0),
           "HI": (-161.0, 18.5, -154.5, 22.5)}
M_PER_DEG = 111_320.0
WESM_1M_PUBLISHED = {"meets", "meets with variance"}  # WESM onemeter_category values
WESM_IN_WORK = {"pending publication", "expected to meet", "under review"}


@dataclass
class Airport:
    icao: str
    name: str
    state: str = ""
    country: str = ""
    longest_m: float = 0.0
    pts: list[tuple[float, float]] = field(default_factory=list)
    boundary: list[list[tuple[float, float]]] = field(default_factory=list)
    poly: Any = None
    lat: float = 0.0
    lon: float = 0.0


def metric(geom: Any, lat: float) -> Any:
    """Equirectangular scaling: degrees -> ~metres at ``lat`` (area ratios)."""
    return scale(geom, M_PER_DEG * math.cos(math.radians(lat)), M_PER_DEG, origin=(0, 0))


def iter_airports(path: str) -> Iterator[Airport]:
    """Stream apt.dat; yields every land airport (row code 1)."""
    cur: Airport | None = None
    ring: list[tuple[float, float]] | None = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if not f:
                continue
            code = f[0]
            if code in ("1", "16", "17", "99"):
                if cur is not None:
                    yield cur
                cur = Airport(f[4], " ".join(f[5:])) if code == "1" and len(f) > 4 else None
                ring = None
                continue
            if cur is None:
                continue
            if code == "100" and len(f) >= 20:
                la1, lo1, la2, lo2 = float(f[9]), float(f[10]), float(f[18]), float(f[19])
                cur.pts += [(lo1, la1), (lo2, la2)]
                if int(f[2]) in PAVED:
                    dx = (lo2 - lo1) * math.cos(math.radians((la1 + la2) / 2))
                    cur.longest_m = max(cur.longest_m, M_PER_DEG * math.hypot(dx, la2 - la1))
            elif code in ("110", "120"):
                ring = None
            elif code == "130":
                ring = []
                cur.boundary.append(ring)
            elif code in ("111", "112", "113", "114", "115", "116") and len(f) >= 3:
                pt = (float(f[2]), float(f[1]))
                (ring if ring is not None else cur.pts).append(pt)
            elif code == "1302" and len(f) >= 3 and f[1] in ("icao_code", "state", "country"):
                setattr(cur, {"icao_code": "icao"}.get(f[1], f[1]), " ".join(f[2:]))
    if cur is not None:
        yield cur


def in_scope(a: Airport, lon: float, lat: float) -> bool:
    if (a.country and a.country.split()[0] != "USA") or a.name.startswith("[X]"):
        return False  # foreign, or closed ("[X]")
    if not a.country and re.match(r"(C[A-Z]{3}|[MT][A-Z]{3}|M[MX])", a.icao):
        return False  # untagged Canada/Mexico/Caribbean ident inside a box
    return any(w <= lon <= e and s <= lat <= n for w, s, e, n in REGIONS.values())


def footprint(a: Airport, buffer_m: float) -> Any:
    """Convex hull of runway ends + pavement nodes, unioned with the apt.dat
    130 boundary rings, buffered ``buffer_m`` (in a local metric frame)."""
    parts = [MultiPoint(a.pts).convex_hull] if a.pts else []
    parts += [Polygon(r).buffer(0) for r in a.boundary if len(r) >= 3]
    geom = unary_union(parts)
    cx, cy = geom.centroid.x, geom.centroid.y
    k = math.cos(math.radians(cy))
    local = scale(geom, k, 1.0, origin=(cx, cy)).buffer(buffer_m / M_PER_DEG)
    return scale(local, 1.0 / k, 1.0, origin=(cx, cy))


def load_airports(args: argparse.Namespace) -> list[Airport]:
    out = []
    for a in iter_airports(args.apt_dat):
        if a.longest_m < args.min_runway_m or not a.pts:
            continue
        lon = sum(p[0] for p in a.pts) / len(a.pts)
        lat = sum(p[1] for p in a.pts) / len(a.pts)
        if not in_scope(a, lon, lat):
            continue
        a.lon, a.lat, a.poly = lon, lat, footprint(a, args.buffer_m)
        a.pts, a.boundary = [], []
        out.append(a)
    return out


def write_gpkg(path: str, airports: list[Airport]) -> None:
    """The airport set as a GeoPackage (ICAO, name, state, longest runway, ARP, footprint)."""
    feats = [{"type": "Feature", "geometry": mapping(a.poly), "properties": {
        "icao": a.icao, "name": a.name, "state": a.state, "longest_rwy_m": round(a.longest_m),
        "lat": a.lat, "lon": a.lon}} for a in airports]
    Path(path + ".geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    gdal.VectorTranslate(path, path + ".geojson", format="GPKG", layerName="airports", accessMode="overwrite")
    os.remove(path + ".geojson")


def cached_get(url: str, cache: str, retries: int = 4) -> dict[str, Any]:
    if os.path.exists(cache):
        return json.loads(Path(cache).read_text())
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=90)
            r.raise_for_status()
            data = r.json()
            if "items" not in data:
                raise ValueError(str(data)[:200])
            Path(cache).write_text(json.dumps(data))
            return data
        except (requests.RequestException, ValueError):
            time.sleep(2 ** attempt)
    return {"error": "fetch failed", "url": url}


def project_name(title: str) -> str:
    """'USGS Lidar Point Cloud (LPC) AK_Kenai_2008_001717 2014-09-22 LAS' -> 'AK_Kenai_2008':
    drop the product prefix, then trailing tile ids, dates and formats."""
    name = re.sub(r"^USGS (?:Lidar Point Cloud(?: \(LPC\))?|OPR|Original Pro\w+ Resolution) ", "", title)
    while (m := re.search(r"[ _](?:LAS|LAZ|[\d-]{4,}|[A-Za-z0-9]*\d{3,}[A-Za-z0-9]*)$", name)) and m.start() > 0:
        name = name[:m.start()]
    return name


def tnm_coverage(a: Airport, cache_dir: str, ds: str = "1m") -> tuple[float | None, dict[str, Any]]:
    """Footprint share inside the listed tiles' bounding boxes of TNM
    dataset ``ds`` -- the engine's discovery -- and the clipped cover per project."""
    w, s, e, n = a.poly.bounds
    d = cached_get(TNM_URL.format(ds=TNM_DS[ds], w=w, s=s, e=e, n=n),
                   os.path.join(cache_dir, f"{a.icao}.{ds}.json"))
    if "items" not in d:
        return None, {}
    area = metric(a.poly, a.lat).area
    by_proj: dict[str, list[Any]] = {}
    for i in d["items"]:
        b = i.get("boundingBox")
        t = i.get("title", "")
        if "IFSAR" in t.upper():
            continue  # 5 m radar, not lidar
        proj = (re.sub(r"^USGS 1 [Mm]eter \S+ \S+ ", "", t) if ds == "1m" else "ned19" if ds == "ned19" else
                project_name(t))
        if b:
            by_proj.setdefault(proj, []).append(box(b["minX"], b["minY"], b["maxX"], b["maxY"]))
    clipped = {p: unary_union(g).intersection(a.poly) for p, g in by_proj.items()}
    cov = metric(unary_union(list(clipped.values())), a.lat).area / area if clipped else 0.0
    return cov, clipped


def wesm_join(a: Airport, lyr: Any, max_ql: int) -> tuple[float, list[dict[str, Any]]]:
    """Footprint share in QL<=max_ql units with a published 1 m DEM, and every unit met.
    WESM's NAD83 is read as WGS84; units are clipped in OGR before shapely sees them."""
    g = ogr.CreateGeometryFromWkb(a.poly.wkb)
    lyr.SetSpatialFilter(g)
    pub, units = [], []
    for feat in lyr:
        geom = feat.GetGeometryRef()
        if geom is None:
            continue
        clip = geom.Buffer(0).Intersection(g) if not geom.IsValid() else geom.Intersection(g)
        if clip is None or clip.IsEmpty():
            continue
        rec = {k: feat.GetField(k) for k in WESM_FIELDS if feat.GetFieldIndex(k) >= 0}
        m = re.search(r"(\d)", str(rec.get("ql") or ""))
        rec["ql_n"] = int(m.group(1)) if m else 99
        rec["published"] = str(rec.get("onemeter_category") or "").strip().lower() in WESM_1M_PUBLISHED
        sg = shp_wkb.loads(bytes(clip.ExportToWkb()))
        rec["share"] = round(metric(sg, a.lat).area / metric(a.poly, a.lat).area, 3)
        units.append(rec)
        if rec["ql_n"] <= max_ql and rec["published"]:
            pub.append(sg)
    cov = metric(unary_union(pub), a.lat).area / metric(a.poly, a.lat).area if pub else 0.0
    return min(cov, 1.0), units


def fetch_usiei(url: str, cache: str, offset_deg: float, page: int) -> list[dict[str, Any]]:
    if os.path.exists(cache):
        return json.loads(Path(cache).read_text())
    feats: list[dict[str, Any]] = []
    while True:
        q = (f"{url}/query?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=geojson"
             f"&maxAllowableOffset={offset_deg}&resultOffset={len(feats)}"
             f"&resultRecordCount={page}&orderByFields=OBJECTID")
        d = requests.get(q, timeout=300).json()
        batch = d.get("features", [])
        feats += batch
        if len(batch) < page:
            break
    Path(cache).write_text(json.dumps(feats))
    return feats


def usiei_link(props: dict[str, Any]) -> str:
    try:
        links = json.loads(props.get("Links") or "{}").get("links", [])
    except ValueError:
        return ""
    access = [l["link"] for l in links if l.get("linktype") == "Data Access"]
    return (access or [l.get("link", "") for l in links] or [""])[0]


def spacing_m(props: dict[str, Any]) -> float | None:
    m = re.search(r"([\d.]+)\s*m", str(props.get("pointspacing") or ""))
    return float(m.group(1)) if m else None


def classify(a: Airport, args: argparse.Namespace, cov1m: float, proj1m: dict[str, Any],
             lpc: dict[str, Any], ned19: float | None, units: list[dict[str, Any]],
             feats: list[dict[str, Any]], geoms: list[Any], tree: Any) -> dict[str, Any]:
    """One gap airport: USGS in-work units, USGS LPC already listed, and the
    USIEI holders not delivered as a USGS 1 m DEM over this footprint."""
    area = metric(a.poly, a.lat).area
    inwork = [u for u in units if u["ql_n"] <= args.max_ql and not u["published"] and (
        str(u.get("onemeter_category") or "").lower() in WESM_IN_WORK
        or str(u.get("lpc_category") or "").lower() in WESM_IN_WORK)]
    keys = [(str(k).lower(), u) for u in units for k in (u.get("project"), u.get("workunit")) if k]
    unit_of = {p: next((u for k, u in keys if k in p.lower() or (len(p) > 5 and p.lower() in k)), {})
               for p in lpc}
    # a listed LPC/OPR project WESM does not name over this footprint keeps QL "?"
    good = {p: v for p, v in lpc.items() if unit_of.get(p, {}).get("ql_n", 0) <= args.max_ql}
    groups: dict[str, list[Any]] = {}
    for p, v in good.items():
        groups.setdefault(unit_of[p].get("project") or p, []).append(v)
    lpc_good = {p: metric(unary_union(v), a.lat).area / area for p, v in groups.items()}
    lpc_projects = set(lpc_good) | set(good)
    ql_of = {u.get("project"): u["ql_n"] for u in units}
    usgs_cov = metric(unary_union(list(good.values())), a.lat).area / area if good else 0.0
    usgs_has = usgs_cov >= args.cover_frac
    holders, pipeline = [], []
    for i in tree.query(a.poly, predicate="intersects"):
        p = feats[i]["properties"]
        ql, sp = p.get("qualitylevel"), spacing_m(p)
        if not (0 <= ql <= args.max_ql if ql is not None and ql < 6 else  # USIEI QL 9 = unknown
                sp is not None and sp <= args.max_spacing_m):
            continue
        alt = str(p.get("AlternateTitle") or "")
        projs = {x.strip() for x in alt.split("USGS:", 1)[1].split(",")} if "USGS:" in alt else set()
        h = {"title": str(p.get("Title") or "").strip(), "year": p.get("collectionyear"), "ql": ql,
             "spacing": p.get("pointspacing"), "owner": p.get("RecordOwner"), "status": p.get("Status"),
             "link": usiei_link(p), "projects": ",".join(sorted(projs)),
             "share": round(metric(geoms[i].intersection(a.poly), a.lat).area / area, 3)}
        if projs & set(proj1m):
            continue  # already in the USGS 1 m listing (and still a gap: partial cover)
        if str(h["status"]) not in ("Complete", "None", ""):
            pipeline.append(h)  # USGS / partner collection in progress
        else:
            h["usgs_lpc"] = bool(projs & lpc_projects)
            holders.append(h)
    other = [h for h in holders if not h["usgs_lpc"]
             and "nationalmap.gov" not in h["link"]]  # TNM-linked = USGS-delivered
    verdict = ("USGS-LPC/OPR" if usgs_has else "HOLDER" if other else "IN-WORK" if inwork or pipeline
               else "USGS-LPC/OPR" if lpc_good else "USIEI-ONLY" if holders else "NOBODY")
    best = max(other or holders, key=lambda h: (h["share"], h["year"] or 0)) if holders else {}
    if verdict != "HOLDER" and not other:
        best = {}
    def fmt(h: dict[str, Any]) -> str:
        return f"{h['title']} ({h['year']}, QL{h['ql']}, {h['owner']}, {h['status']}, {100 * h['share']:.0f}%)"
    return {"icao": a.icao, "name": a.name, "state": a.state, "longest_rwy_m": round(a.longest_m),
            "lat": round(a.lat, 5), "lon": round(a.lon, 5), "tnm_1m_pct": round(100 * cov1m, 1),
            "tnm_1m_projects": ";".join(sorted(proj1m)), "ned19_3m_pct":
                None if ned19 is None else round(100 * ned19, 1),
            "usgs_lpc_opr_ql2": "; ".join(f"{p} QL{ql_of.get(p, '?')} ({100 * v:.0f}%)"
                                         for p, v in sorted(lpc_good.items())),
            "usgs_inwork": "; ".join(f"{u.get('workunit')} QL{u['ql_n']} collect {u.get('collect_start')} "
                                     f"[{u.get('onemeter_category')}]" for u in inwork)
                           + ("; " if inwork and pipeline else "") + "; ".join(fmt(h) for h in pipeline),
            **{f"holder_{k}": best.get(k, "") for k in ("title", "year", "ql", "spacing", "owner", "status")},
            "holder_share_pct": round(100 * best["share"]) if best else "",
            "holder_link": best.get("link", ""), "holder_usgs_projects": best.get("projects", ""),
            "holders_all": " | ".join(fmt(h) + (" [USGS LPC]" if h["usgs_lpc"] else "") for h in holders),
            "verdict": verdict}


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--apt-dat", required=True)
    ap.add_argument("--wesm", required=True, help="local WESM.gpkg (download once from " + WESM_URL + ")")
    ap.add_argument("--usiei-url", default=USIEI_URL)
    for flag, typ, default, hlp in (
            ("--min-runway-m", float, 1200.0, "longest paved runway at least this"),
            ("--buffer-m", float, 300.0, "footprint buffer (engine footprint_buffer_m: 300)"),
            ("--cover-frac", float, 0.80, "gap below this share (engine INSET_MIN_AIRPORT_COVER_FRAC)"),
            ("--max-ql", int, 2, "lidar at this USGS quality level or better counts"),
            ("--max-spacing-m", float, 1.0, "or, with no QL, this nominal point spacing"),
            ("--usiei-offset-deg", float, 0.0001, "USIEI geometry generalisation"),
            ("--workers", int, 6, "parallel TNM requests")):
        ap.add_argument(flag, type=typ, default=default, help=hlp)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    cache = os.path.join(args.out, "tnm_cache")
    os.makedirs(cache, exist_ok=True)
    airports = load_airports(args)
    print(f"airports in scope: {len(airports)}", flush=True)
    write_gpkg(os.path.join(args.out, "airports.gpkg"), airports)

    def listing(ds: str, aps: list[Airport]) -> dict[str, tuple[float | None, dict[str, Any]]]:
        with cf.ThreadPoolExecutor(args.workers) as pool:
            return dict(zip((x.icao for x in aps), pool.map(lambda x: tnm_coverage(x, cache, ds), aps)))
    one = listing("1m", airports)
    failed = [k for k, v in one.items() if v[0] is None]
    gaps = [x for x in airports if one[x.icao][0] is not None and one[x.icao][0] < args.cover_frac]
    lpc, opr, ned = listing("lpc", gaps), listing("opr", gaps), listing("ned19", gaps)
    print(f"TNM: {len(gaps)} gaps, {len(failed)} listing failures {failed}", flush=True)

    wesm_ds = ogr.Open(args.wesm)  # keep the dataset alive while its layer is read
    lyr = wesm_ds.GetLayer(0)
    wesm = {x.icao: wesm_join(x, lyr, args.max_ql) for x in airports}
    feats = fetch_usiei(args.usiei_url, os.path.join(args.out, "usiei_topo.json"), args.usiei_offset_deg, 1000)
    geoms = [shape(f["geometry"]).buffer(0) if f.get("geometry") else Polygon() for f in feats]
    tree = STRtree(geoms)
    rows = []
    for x in gaps:
        usgs_other = {**lpc[x.icao][1], **{"OPR " + k: v for k, v in opr[x.icao][1].items()}}
        r = classify(x, args, one[x.icao][0] or 0.0, one[x.icao][1], usgs_other, ned[x.icao][0],
                     wesm[x.icao][1], feats, geoms, tree)
        r["wesm_1m_pct"] = round(100 * wesm[x.icao][0], 1)
        rows.append(r)
    rows.sort(key=lambda r: -r["longest_rwy_m"])
    gap_t = {x.icao for x in gaps}
    gap_w = {x.icao for x in airports if wesm[x.icao][0] < args.cover_frac}
    disagree = [f"TNM-gap/WESM-covered {len(gap_t - gap_w)}: " + " ".join(sorted(gap_t - gap_w)),
                f"WESM-gap/TNM-covered {len(gap_w - gap_t)}: " + " ".join(sorted(gap_w - gap_t))]
    cols = list(rows[0]) if rows else ["icao"]
    with open(os.path.join(args.out, "airport_gaps.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    tally = {v: sum(r["verdict"] == v for r in rows)
             for v in ("HOLDER", "USGS-LPC/OPR", "IN-WORK", "USIEI-ONLY", "NOBODY")}
    summary = (f"checked {len(airports)} | gaps (TNM 1 m < {args.cover_frac:.0%}) {len(rows)} | "
               + " | ".join(f"{k} {v}" for k, v in tally.items())
               + " | " + " | ".join(disagree))
    with open(os.path.join(args.out, "airport_gaps.md"), "w") as fh:
        fh.write(summary + "\n\n| ICAO | name | state | rwy m | TNM 1 m % | WESM % | 1/9\" % | USGS in work | "
                 "USGS LPC/OPR (QL<=2) | non-USGS-1m source | verdict |\n|---|---|---|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            src = (f"{r['holder_title']} ({r['holder_year']}, QL{r['holder_ql']}/{r['holder_spacing']}, "
                   f"{r['holder_owner']}, {r['holder_share_pct']}%) {r['holder_link']}") if r["holder_title"] else ""
            fh.write(f"| {r['icao']} | {r['name']} | {r['state']} | {r['longest_rwy_m']} | {r['tnm_1m_pct']} | "
                     f"{r['wesm_1m_pct']} | {r['ned19_3m_pct']} | {r['usgs_inwork'][:140]} | "
                     f"{r['usgs_lpc_opr_ql2'][:80]} | {src} | {r['verdict']} |\n")
    print(summary)


if __name__ == "__main__":
    main()
