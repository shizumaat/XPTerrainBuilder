#!/usr/bin/env python3
"""TROUBLE MAP — the law-true rows of a built patch as a JOSM-readable .osm.

    venv/bin/python tools/trouble_osm.py --patch P.osm --rows ROWS.json \
        [--sidecar P.osm.axes.json] [--icao ICAO] --out DIR \
        [--cluster LAT LON] [--context-ways N] [--no-seniority]

    venv/bin/python tools/trouble_osm.py --visual FINDINGS.json --out DIR \
        [--icao ICAO]                       # the VISUAL-DEFECT layer

THE QUESTION IT ANSWERS is the owner's, not an instrument's: *show me where
the trouble is, in context, in something I can open*.  A census table names
counts, ``census_rows_diff`` names moved rows and ``arm_site_read`` answers
one coordinate — none of them puts a chord on a map next to the pavement it
crosses, which is what deciding between remedies needs.

THE VISUAL LAYER (``--visual``, added 2026-08-24) answers the OTHER half of
that question, the half a census cannot reach at all: *the law says this
patch is clean and the owner says it looks wrong — show me WHERE*.  A defect
the law no longer prices emits no row, so the row-driven map above is blind
to it by construction.  ``--visual`` therefore takes a FINDINGS file instead
of a rows dump — the same verbatim contract, a different producer — and
writes ``<ICAO>_visual.osm``.  Its classes are VISUAL, not legal:

  interior_bump   an apron whose ring acquired relief a movement-surface cap
                  would not have permitted (amplitude over a 50 m window,
                  p95 ring slope, the raw DEM under the worst bump).
  cliff_step      a step a viewer reads as a wall: two shapes meeting within
                  metres at different values, a band-clamped node beside an
                  un-clamped neighbour, or a short ring edge carrying a
                  metre-class drop.
  road_break      a road ring edge or road shape carrying a break, and the
                  spine-less road pieces where nothing holds a profile.
  owner_site      a place the OWNER named in an in-sim report, carrying the
                  read that was done there.
  context_apron   a ring drawn as geometry only, so a class above is read
                  against the pavement it sits on.  Carries no measurement.

Every finding is a dict with ``cls``, ``kind`` (``node`` / ``edge`` /
``ring``), its coordinates, and a free ``tags`` map written through
unchanged.  This file still MEASURES NOTHING: it neither computes an
amplitude nor decides a class — the producer does, and names itself in the
file's ``generator``/``arms`` header, which is copied onto every element so
a reader can never lose which arms a number came from.

**IT MEASURES NOTHING AND DERIVES NO LAW.**  Every row, grade, cap, side and
site is read VERBATIM out of a ``harness/census.py --rows-json`` dump;
geometry comes from the harness library's own ``check_grade._parse_osm``; the
metre frame is ``check_grade._ll_to_m_factory``'s formula and ``R_EARTH``,
inverted about the sidecar's own ``anchor`` so a row's ``site_m`` lands back
on the coordinates it came from EXACTLY (the projection is analytic and
invertible — no proximity join, memory ``canonical-identity-join``).  The
class thresholds are ``grade_law.APRON_BODY_CHORD_MAX_M``,
``grade_law.APRON_INTERIOR_CAP`` and ``config.BUILDING_REACH_CORRIDOR_M``,
IMPORTED, never re-spelled.  A private re-count here would be the
census-wrapper defect (CLAUDE.md).

WHAT THE CLASSES MEAN, and their precedence (first match wins).  They are
derived from ROW FIELDS ONLY, so they are a READING AID, never a law verdict:

  transverse        the ``transverse`` family (cross-corridor grade).
  weld_cluster      chord <= ``WELD_CLUSTER_MAX_CHORD_M`` inside a declared
                    ``--cluster`` disc — the sub-metre, tens-of-x-cap class.
  long_spine_chord  chord > ``APRON_BODY_CHORD_MAX_M`` whose baked
                    ``pair_caps`` family ends ``:spine``.
  long_ring_edge    chord > ``APRON_BODY_CHORD_MAX_M`` otherwise.
  frontage_gt5pct   an apron row over 5 % — the seat/anchor docket.
  frontage_chord    an apron row within the body gate at a strict cap.
  short_strict      any other row within the body gate at a strict cap.
  other             everything else.

``baked_family`` is an ENRICHMENT tag, present only where the row's endpoints
key EXACTLY onto a ``pair_caps`` entry in the sidecar's own frame (measured
~65 % of HECA's within-shape rows — the census re-walks the EMITTED ring
while ``pair_caps`` froze the SOLVER's, so a miss is information, not an
error).  Its absence is never inferred as "not a spine".

Output ids are NEGATIVE (JOSM's convention for not-yet-uploaded data) and the
file carries a ``<bounds>`` so JOSM zooms to the airport on open.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape, quoteattr

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import check_grade as cg                                       # noqa: E402

from auto_patch.config import BUILDING_REACH_CORRIDOR_M        # noqa: E402
from auto_patch.grade_law import (                             # noqa: E402
    APRON_BODY_CHORD_MAX_M, APRON_INTERIOR_CAP)

#: A weld-cluster row is a sub-metre-to-few-metre chord: the class measured at
#: SPJC (-12.021394,-77.110990), 42 of 58 >2x rows on chords <= 5 m.
WELD_CLUSTER_MAX_CHORD_M = 5.0
#: Default radius of a declared ``--cluster`` disc.
WELD_CLUSTER_RADIUS_M = 60.0
#: The grade above which a kept apron row is a seat/anchor docket item.
FRONTAGE_HOT_GRADE_PCT = 5.0

CLASSES = ("long_spine_chord", "long_ring_edge", "short_strict",
           "frontage_chord", "frontage_gt5pct", "weld_cluster",
           "transverse", "other")

#: The VISUAL classes (``--visual``).  A reading aid for a defect the law
#: does not price, never a law verdict — see the module docstring.
VISUAL_CLASSES = ("owner_site", "interior_bump", "cliff_step", "road_break",
                  "context_apron")


# ── frame ────────────────────────────────────────────────────────────

def m_to_ll_factory(anchor: Tuple[float, float]):
    """The analytic INVERSE of ``check_grade._ll_to_m_factory`` about the same
    anchor, with the same ``R_EARTH``.  Exact to float precision, so a row's
    ``site_m`` returns to the lat/lon the census projected it from."""
    lat0, lon0 = float(anchor[0]), float(anchor[1])
    cos0 = math.cos(math.radians(lat0))

    def _f(x: float, y: float) -> Tuple[float, float]:
        lon = lon0 + math.degrees(float(x) / (cg.R_EARTH * cos0))
        lat = lat0 + math.degrees(float(y) / cg.R_EARTH)
        return lat, lon
    return _f


def sidecar_anchor(sidecar: Optional[dict],
                   nodes: Dict[str, Tuple[float, float]]
                   ) -> Tuple[float, float]:
    """The BUILDER's projection anchor, exactly as the census takes it; the
    node mean only when a patch carries no sidecar (``check_grade``'s own
    fallback, same formula)."""
    if sidecar:
        a = sidecar.get("anchor")
        if a and len(a) >= 2:
            return float(a[0]), float(a[1])
    if not nodes:
        return 0.0, 0.0
    return (sum(v[0] for v in nodes.values()) / len(nodes),
            sum(v[1] for v in nodes.values()) / len(nodes))


# ── classification (row fields only) ─────────────────────────────────

def baked_family_index(sidecar: Optional[dict], anchor) -> Dict[tuple, str]:
    """``{(cm-quantised endpoint pair): pair_caps family}`` in the census's
    own metre frame, so the join is EXACT arithmetic on both sides rather
    than a distance search."""
    out: Dict[tuple, str] = {}
    if not sidecar:
        return out
    lat0, lon0 = anchor
    cos0 = math.cos(math.radians(lat0))

    def _m(lat, lon):
        return (math.radians(lon - lon0) * cg.R_EARTH * cos0,
                math.radians(lat - lat0) * cg.R_EARTH)

    for r in (sidecar.get("pair_caps") or ()):
        if not r or len(r) < 4:
            continue
        try:
            a = _m(float(r[0][0]), float(r[0][1]))
            b = _m(float(r[1][0]), float(r[1][1]))
        except (TypeError, ValueError, IndexError):
            continue
        out.setdefault(_pair_key(a, b), str(r[3]))
    return out


def _pair_key(a, b) -> tuple:
    ka = (round(float(a[0]), 2), round(float(a[1]), 2))
    kb = (round(float(b[0]), 2), round(float(b[1]), 2))
    return (ka, kb) if ka <= kb else (kb, ka)


def classify(row: dict, baked: Optional[str],
             cluster: Optional[Tuple[float, float]]) -> str:
    """The class of one row, from its OWN fields.  See the module docstring
    for what each name means; first match wins."""
    fam = row.get("family") or ""
    if fam == "transverse":
        return "transverse"
    d = float(row.get("distance_m") or 0.0)
    roles = row.get("roles") or ""
    grade = row.get("grade_pct")
    cap = row.get("cap_pct")
    if (cluster is not None and 0.0 < d <= WELD_CLUSTER_MAX_CHORD_M
            and _in_cluster(row, cluster)):
        return "weld_cluster"
    if d > APRON_BODY_CHORD_MAX_M:
        if baked and baked.endswith(":spine"):
            return "long_spine_chord"
        return "long_ring_edge"
    strict = cap is not None and float(cap) < APRON_INTERIOR_CAP * 100.0
    if "apron" in roles:
        if grade is not None and float(grade) > FRONTAGE_HOT_GRADE_PCT:
            return "frontage_gt5pct"
        if strict and d <= BUILDING_REACH_CORRIDOR_M:
            return "frontage_chord"
    if strict:
        return "short_strict"
    return "other"


def _in_cluster(row: dict, cluster: Tuple[float, float]) -> bool:
    lat, lon = row.get("lat"), row.get("lon")
    if lat is None or lon is None:
        return False
    dy = (float(lat) - cluster[0]) * 111_320.0
    dx = ((float(lon) - cluster[1]) * 111_320.0
          * math.cos(math.radians(cluster[0])))
    return math.hypot(dx, dy) <= WELD_CLUSTER_RADIUS_M


# ── OSM XML ──────────────────────────────────────────────────────────

class OsmWriter:
    """Minimal JOSM-readable OSM XML.  Negative ids, ``action='modify'`` never
    set (nothing here is an edit of real OSM data), one ``<bounds>``."""

    def __init__(self) -> None:
        self._nodes: List[str] = []
        self._ways: List[str] = []
        self._nid = 0
        self._wid = 0
        self._lat = [90.0, -90.0]
        self._lon = [180.0, -180.0]

    def node(self, lat: float, lon: float, tags: Optional[dict] = None) -> int:
        self._nid -= 1
        self._lat[0] = min(self._lat[0], lat)
        self._lat[1] = max(self._lat[1], lat)
        self._lon[0] = min(self._lon[0], lon)
        self._lon[1] = max(self._lon[1], lon)
        t = _tags_xml(tags)
        self._nodes.append(
            f"  <node id='{self._nid}' visible='true' "
            f"lat='{lat:.11f}' lon='{lon:.11f}'"
            + (">\n" + t + "  </node>\n" if t else " />\n"))
        return self._nid

    def way(self, nids: List[int], tags: Optional[dict] = None) -> int:
        self._wid -= 1
        nd = "".join(f"    <nd ref='{i}' />\n" for i in nids)
        self._ways.append(
            f"  <way id='{self._wid}' visible='true'>\n{nd}"
            f"{_tags_xml(tags)}  </way>\n")
        return self._wid

    def dumps(self, generator: str) -> str:
        if self._lat[0] > self._lat[1]:          # nothing was written
            self._lat, self._lon = [0.0, 0.0], [0.0, 0.0]
        return (
            "<?xml version='1.0' encoding='UTF-8'?>\n"
            f"<osm version='0.6' generator={quoteattr(generator)}>\n"
            f"  <bounds minlat='{self._lat[0]:.11f}' "
            f"minlon='{self._lon[0]:.11f}' maxlat='{self._lat[1]:.11f}' "
            f"maxlon='{self._lon[1]:.11f}' />\n"
            + "".join(self._nodes) + "".join(self._ways) + "</osm>\n")


def _tags_xml(tags: Optional[dict]) -> str:
    if not tags:
        return ""
    out = []
    for k, v in tags.items():
        if v is None:
            continue
        out.append(f"    <tag k={quoteattr(str(k))} "
                   f"v={quoteattr(escape(str(v)))} />\n")
    return "".join(out)


# ── build ────────────────────────────────────────────────────────────

def build(patch: Path, rows_json: Path, out_dir: Path,
          sidecar_path: Optional[Path] = None, icao: str = "",
          cluster: Optional[Tuple[float, float]] = None,
          context_ways: int = 5, seniority: bool = True) -> dict:
    dump = json.loads(rows_json.read_text())
    rows = dump["rows"] if isinstance(dump, dict) else dump
    nodes, ways = cg._parse_osm(patch)
    sidecar = None
    sc_path = sidecar_path or Path(str(patch) + ".axes.json")
    if sc_path.exists():
        sidecar = json.loads(sc_path.read_text())
    anchor = sidecar_anchor(sidecar, nodes)
    m_to_ll = m_to_ll_factory(anchor)
    baked = baked_family_index(sidecar, anchor)

    # THE FAMILIES WE MAP: the airside rows plus the groundside rows of the
    # SAME families, so the file stays readable (the brief's own scoping).
    air_families = {r.get("family") for r in rows
                    if r.get("side") == "airside"}
    keep = [r for r in rows
            if r.get("side") == "airside"
            or (r.get("family") in air_families
                and r.get("side") == "groundside")]

    w = OsmWriter()
    counts: Dict[str, int] = {c: 0 for c in CLASSES}
    per_side: Dict[str, int] = {}
    offenders: Dict[str, int] = {}

    for r in keep:
        site = r.get("site_m")
        if not site or len(site) < 2:
            continue
        key = _pair_key(site[0], site[1])
        fam_baked = baked.get(key)
        cls = classify(r, fam_baked, cluster)
        counts[cls] = counts.get(cls, 0) + 1
        per_side[r.get("side") or "?"] = per_side.get(r.get("side") or "?", 0) + 1
        wid = r.get("way_a")
        if wid and r.get("side") == "airside":
            offenders[wid] = offenders.get(wid, 0) + 1
        a = w.node(*m_to_ll(site[0][0], site[0][1]))
        b = w.node(*m_to_ll(site[1][0], site[1][1]))
        w.way([a, b], {
            "trouble": "row",
            "class": cls,
            "family": r.get("family"),
            "roles": r.get("roles"),
            "side": r.get("side"),
            "cap_pct": _num(r.get("cap_pct")),
            "grade_pct": _num(r.get("grade_pct")),
            "de_m": _num(r.get("magnitude_m")),
            "chord_m": _num(r.get("distance_m")),
            "way_ref": wid,
            "baked_family": fam_baked,
        })

    # HOT SPOTS — one node per declared cluster centroid, carrying the rows
    # it holds and their worst |de| (both read from the rows, not measured).
    hotspots = []
    if cluster is not None:
        inside = [r for r in keep if _in_cluster(r, cluster)]
        if inside:
            hotspots.append(("weld_cluster", cluster, inside))
    top_way = max(offenders.items(), key=lambda kv: kv[1])[0] if offenders \
        else None
    if top_way:
        rws = [r for r in keep if r.get("way_a") == top_way
               and (r.get("distance_m") or 0) > APRON_BODY_CHORD_MAX_M]
        if rws:
            rws2 = sorted(rws, key=lambda r: -(r.get("magnitude_m") or 0))[:20]
            lat = sum(float(r["lat"]) for r in rws2) / len(rws2)
            lon = sum(float(r["lon"]) for r in rws2) / len(rws2)
            hotspots.append((f"long_chord_way_{top_way}", (lat, lon), rws2))
    for name, (lat, lon), rws in hotspots:
        w.node(lat, lon, {
            "trouble": "hotspot",
            "hotspot": name,
            "rows": len(rws),
            "worst_de_m": _num(max((r.get("magnitude_m") or 0) for r in rws)),
            "worst_grade_pct": _num(max((r.get("grade_pct") or 0)
                                        for r in rws)),
        })

    # CONTEXT — the rings of the top-N offending ways, geometry only, so the
    # chords are readable against their own pavement.
    top = [k for k, _ in sorted(offenders.items(), key=lambda kv: -kv[1])
           ][:max(0, context_ways)]
    by_wid = {getattr(x, "wid", None): x for x in ways}
    ctx = 0
    for wid in top:
        way = by_wid.get(wid)
        if way is None:
            continue
        nids = [nodes[n] for n in getattr(way, "nids", []) if n in nodes]
        if len(nids) < 2:
            continue
        ids = [w.node(la, lo) for (la, lo) in nids]
        w.way(ids, {"context": "apron", "way_ref": wid,
                    "role": getattr(way, "role", "") or None})
        ctx += 1

    # SENIORITY — the staged solve's own partition, verbatim from the sidecar.
    sen = 0
    if seniority and sidecar:
        for r in (sidecar.get("apron_seniority") or ()):
            if not r or len(r) < 3:
                continue
            w.node(float(r[0]), float(r[1]),
                   {"trouble": "seniority", "apron_seniority": str(r[2])})
            sen += 1

    out_dir.mkdir(parents=True, exist_ok=True)
    name = (icao or patch.stem.split("_")[0]).upper()
    dest = out_dir / f"{name}_trouble.osm"
    dest.write_text(w.dumps(f"trouble_osm.py {patch.name}"))
    return {"icao": name, "path": str(dest), "rows": len(keep),
            "classes": counts, "sides": per_side, "context_ways": ctx,
            "seniority_nodes": sen,
            "hotspots": [h[0] for h in hotspots],
            "baked_join": f"{sum(1 for r in keep if _pair_key(*r['site_m'][:2]) in baked)}/{len(keep)}"
            if keep else "0/0"}


def _num(v):
    if v is None:
        return None
    f = float(v)
    return f"{f:.4f}".rstrip("0").rstrip(".") or "0"


# ── the VISUAL layer ─────────────────────────────────────────────────

def build_visual(findings_json: Path, out_dir: Path, icao: str = "") -> dict:
    """``<ICAO>_visual.osm`` from a VISUAL FINDINGS file.

    The findings file is ``{"icao", "generator", "arms": {...},
    "findings": [{"cls", "kind", "lat", "lon", ["lat2","lon2"|"ll"],
    "tags": {...}}, ...]}``.  Every value is written through VERBATIM —
    this function decides no class and computes no number; ``arms`` and
    ``generator`` are stamped onto each element so a reader cannot lose
    which arms a number was measured between."""
    doc = json.loads(findings_json.read_text())
    findings = doc.get("findings") or []
    name = (icao or doc.get("icao") or findings_json.stem.split("_")[0]).upper()
    arms = doc.get("arms") or {}
    arm_tags = {f"arm_{k}": v for k, v in arms.items()}
    gen = doc.get("generator") or findings_json.name

    w = OsmWriter()
    counts: Dict[str, int] = {}
    skipped = 0
    for f in findings:
        cls = str(f.get("cls") or "other")
        kind = str(f.get("kind") or "node")
        tags = dict(f.get("tags") or {})
        tags.update({"trouble": "visual", "class": cls, "source": gen})
        tags.update(arm_tags)
        if kind == "ring":
            ll = f.get("ll") or []
            if len(ll) < 2:
                skipped += 1
                continue
            ids = [w.node(float(a), float(b)) for a, b in ll]
            w.way(ids, tags)
        elif kind == "edge":
            if f.get("lat") is None or f.get("lat2") is None:
                skipped += 1
                continue
            a = w.node(float(f["lat"]), float(f["lon"]))
            b = w.node(float(f["lat2"]), float(f["lon2"]))
            w.way([a, b], tags)
        else:
            if f.get("lat") is None:
                skipped += 1
                continue
            w.node(float(f["lat"]), float(f["lon"]), tags)
        counts[cls] = counts.get(cls, 0) + 1

    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{name}_visual.osm"
    dest.write_text(w.dumps(f"trouble_osm.py --visual {findings_json.name}"))
    return {"icao": name, "path": str(dest), "findings": len(findings),
            "written": sum(counts.values()), "skipped": skipped,
            "classes": counts, "arms": arms, "generator": gen}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Law-true rows of a built patch as a JOSM-readable .osm")
    ap.add_argument("--patch", type=Path)
    ap.add_argument("--rows", type=Path,
                    help="a harness/census.py --rows-json dump of THAT patch")
    ap.add_argument("--visual", type=Path,
                    help="a VISUAL FINDINGS json — writes <ICAO>_visual.osm "
                         "instead of the row map (see the module docstring)")
    ap.add_argument("--sidecar", type=Path,
                    help="default: <patch>.axes.json")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--icao", default="")
    ap.add_argument("--cluster", nargs=2, type=float, metavar=("LAT", "LON"),
                    help="declare a weld-cluster centre for the class + a "
                         "hotspot node")
    ap.add_argument("--context-ways", type=int, default=5)
    ap.add_argument("--no-seniority", action="store_true")
    a = ap.parse_args(argv)
    if a.visual is not None:
        if not a.visual.exists():
            print(f"trouble_osm: no such findings file {a.visual}")
            return 2
        rep = build_visual(a.visual, a.out, icao=a.icao)
        print(f"  [trouble/visual] {rep['icao']}: {rep['written']} finding(s)"
              f" -> {rep['path']}")
        print("    classes: "
              + ", ".join(f"{k}={v}" for k, v in rep["classes"].items()))
        for k, v in (rep["arms"] or {}).items():
            print(f"    arm {k}: {v}")
        if rep["skipped"]:
            print(f"    SKIPPED {rep['skipped']} finding(s) with no geometry")
        return 0
    if a.patch is None or a.rows is None:
        print("trouble_osm: --patch and --rows are required without --visual")
        return 2
    if not a.patch.exists():
        print(f"trouble_osm: no such patch {a.patch}")
        return 2
    if not a.rows.exists():
        print(f"trouble_osm: no such rows dump {a.rows}")
        return 2
    rep = build(a.patch, a.rows, a.out, sidecar_path=a.sidecar, icao=a.icao,
                cluster=tuple(a.cluster) if a.cluster else None,
                context_ways=a.context_ways, seniority=not a.no_seniority)
    print(f"  [trouble] {rep['icao']}: {rep['rows']} row(s) -> {rep['path']}")
    print(f"    classes: "
          + ", ".join(f"{k}={v}" for k, v in rep["classes"].items() if v))
    print(f"    sides: {rep['sides']}  context ways: {rep['context_ways']}  "
          f"seniority nodes: {rep['seniority_nodes']}  "
          f"baked-family join: {rep['baked_join']}")
    if rep["hotspots"]:
        print(f"    hotspots: {', '.join(rep['hotspots'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
