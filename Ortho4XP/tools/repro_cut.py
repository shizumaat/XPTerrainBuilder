"""THE REPRO CUTTER — a defect site becomes a seconds-fast fixture.

    venv/bin/python tools/repro_cut.py ICAO --coord LAT LON --radius M
        [--patch PATH] [--out DIR] [--pin SPEC ...] [--pins-from FILE]
        [--margin M] [--copy-osm] [--allow-degraded-dem]
    venv/bin/python tools/repro_cut.py --run FIXTURE_DIR [--json OUT]

Run it from ``Ortho4XP/``.  Spec: ``docs/specs/repro-cutter-spec.md``.

WHY.  RULINGS 2026-08-12, "THE OWNER'S ARTIFACT IS THE ATTRIBUTION
BASELINE": a bug report implies the owner already built the tile, so root
cause reads THAT artifact and never a rebuilt base arm — and the FIX LOOP
iterates against an extracted synthetic repro that reproduces the defect's
numbers in seconds.  This is that extractor.  ``--cut`` never triggers a
build; it reads the shipped patch, the apt.dat it names in its own
provenance, and the DEM the build frame recorded.

THE PIN TABLE IS THE CONTRACT.  A fixture is not "the site" — it is a
claim that a NAMED MEASUREMENT survives the cut.  Every pin is a number
the caller measured on the artifact; ``--cut`` re-measures each one on the
SOURCE patch and REFUSES a pin the artifact does not actually carry (rail
R5), so a fixture can never be built around a number nobody checked.
``--run`` re-measures the same pins on the freshly built fixture patch and
reports REPRODUCED / DIVERGED per pin.  A DIVERGED fixture is a reported
result, never a silently accepted repro.

ONE INSTRUMENT.  Pins are measured through ``tools/harness/census.py``'s
own ``census_one`` (which is ``check_grade.run_checks_law_true`` plus the
sidecar law context) — this file enumerates no law family, applies no
exemption and re-derives no grade.  The census-wrapper precedent (root
``CLAUDE.md``) is what a private copy of that frame costs.

OUT OF SCOPE IN v1: MESH-SIDE classes (the R18-1b class — anything whose
value is produced by Triangle4XP rather than by the patch/solver
pipeline).  A pin naming one refuses (rail R1).  Patch and solver classes
only.

WHAT THE FIXTURE CONTAINS
    repro.json          manifest: source sha, coord, radius, window, pins
                        (each with the value measured on the SOURCE), the
                        DEM provenance, the OSM manifest, the run env
    apt.dat             the sliced airport block — the pipeline's input
    reference.patch.osm the sliced emitted shapes + welded neighbours,
      + .axes.json      with the sidecar slice (SAME anchor: axes/routes
                        are anchor-relative metres, so re-anchoring would
                        invalidate the very context the census needs)
    dem.npz             the DEM window (base + the inset subdems that
                        overlap it), cropped lane-local, never a corpus
                        write
    osm/                a read-through symlink overlay of the corpus OSM
                        tiles this airport reads (``--copy-osm`` copies
                        the referenced tile files instead of linking)
    xplane/             a symlink farm X-Plane root: the real install's
                        Custom Data / Resources / pack, with the SLICED
                        apt.dat in the pack's place
    run/                the last ``--run``'s fresh patch + census

REFUSAL RAILS (a fixture that cannot carry a law's context refuses with
the reason, rather than producing a number that looks like a repro):
    R1  a pin naming a mesh-side family              (out of v1 scope)
    R2  the disc + margin crosses a tile boundary    (tile-boundary class)
    R3  the patch is not this ICAO's                 (cross-airport claim)
    R4  a pin's site lies outside the disc
    R5  a pin the SOURCE artifact does not carry
    R6  no ``.axes.json`` beside the patch           (context-free census)
    R7  the disc selects no shape, or no apt.dat geometry
    R8  a DEM window with no inset provenance        (--allow-degraded-dem)

Cross-refs: ``tools/build_target_osm.py`` (the near-fit this extends —
its standalone ``build_airport_pavement`` call and its per-tile DEM
discipline are reused verbatim), ``tools/harness/shared_repo_guard.py``
(the write law: armed for the whole ``--run``), ``tools/INDEX.md``.
"""
from __future__ import annotations

import argparse
import bz2
import json
import math
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent          # Ortho4XP/
HARNESS = ROOT / "tools" / "harness"

#: Families whose value is produced MESH-side (Triangle4XP), not by the
#: patch/solver pipeline a fixture replays.  Out of v1 scope, per spec.
MESH_SIDE_FAMILIES = frozenset({"plane_gradient"})

#: Sidecar keys that are plain coordinate geometry and may be subset by
#: the window without disturbing any cross-key index.  Everything else is
#: carried VERBATIM — ``axes_exact``'s route ordinal indexes
#: ``routes_exact`` positionally, so subsetting either would silently
#: repoint every axis at the wrong route.
SIDECAR_GEOMETRY_KEYS = {
    "mesh_edges":   "pairs",     # [[[la,lo],[la,lo]], ...]
    "pair_caps":    "pairs+v",   # [[la,lo],[la,lo],budget]
    "crown_drops":  "point+v",   # [la,lo,drop]
    "crown_centerline": "point",  # [la,lo]
    "seam_pins":    "point",     # [la,lo]
    "disconnected_rings": "ring",  # [[la,lo], ...]
}

#: apt.dat row grammar (X-Plane 1100/1200 spec).  A CONTOUR NODE row
#: belongs to whatever block it follows; a block is its header plus every
#: following node row.
APT_NODE_ROWS = {111, 112, 113, 114, 115, 116}
APT_BLOCK_HEADERS = {110, 120, 130}
#: Rows that ARE a single point: keep when the point is in the window.
APT_POINT_ROWS = {20, 1201, 1300, 1500, 1501}
#: Rows that ride on the preceding 1202/1206 edge.
APT_EDGE_ATTR_ROWS = {1204}

DEFAULT_MARGIN_M = 400.0
#: Convergence-guard materiality floors (auto_patch/CLAUDE.md §3): a
#: residual below these is PASS-with-residual, never a divergence.
DEFAULT_TOL = {"m": 0.01, "pct": 0.01, "count": 0.0}


class ReproRefusal(RuntimeError):
    """A fixture that cannot carry the claim, refused with the reason."""


# ─────────────────────────────────────────────────────────────────────
# Pure geometry / parsing helpers (twinned; no I/O, no environment)
# ─────────────────────────────────────────────────────────────────────

R_EARTH = 6378137.0


def ll_to_m_factory(lat0: float, lon0: float):
    """``(lat, lon) -> (x, y)`` metres about ``(lat0, lon0)``.

    The same spherical convention as ``PavementLayout.ll_to_m`` — the
    frame the sidecar's anchor names.
    """
    coslat = math.cos(math.radians(lat0))

    def ll_to_m(lat: float, lon: float):
        return ((lon - lon0) * math.radians(1.0) * R_EARTH * coslat,
                (lat - lat0) * math.radians(1.0) * R_EARTH)
    return ll_to_m


def point_in_window(lat: float, lon: float, window) -> bool:
    """``window`` is ``(lat_min, lat_max, lon_min, lon_max)``."""
    la0, la1, lo0, lo1 = window
    return la0 <= lat <= la1 and lo0 <= lon <= lo1


def segment_hits_window(a, b, window) -> bool:
    """True when the lat/lon segment ``a-b`` touches the window rect.

    Cheap and conservative: endpoint-in, or the segment's own bbox
    overlapping the window on both axes AND the window's centre line
    being crossed.  A false POSITIVE only widens the slice (a bigger
    fixture), which is the safe direction; a false negative would drop
    geometry the law needs.
    """
    if point_in_window(a[0], a[1], window) or point_in_window(b[0], b[1],
                                                              window):
        return True
    la0, la1, lo0, lo1 = window
    sla0, sla1 = min(a[0], b[0]), max(a[0], b[0])
    slo0, slo1 = min(a[1], b[1]), max(a[1], b[1])
    return not (sla1 < la0 or sla0 > la1 or slo1 < lo0 or slo0 > lo1)


def window_of(points, margin_m: float, lat_ref: float):
    """The lat/lon window covering ``points`` grown by ``margin_m``."""
    if not points:
        raise ReproRefusal("R7: no geometry to window")
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    dlat = margin_m / (R_EARTH * math.radians(1.0))
    dlon = margin_m / (R_EARTH * math.radians(1.0)
                       * max(1e-9, math.cos(math.radians(lat_ref))))
    return (min(lats) - dlat, max(lats) + dlat,
            min(lons) - dlon, max(lons) + dlon)


def disc_window(lat: float, lon: float, radius_m: float, margin_m: float):
    return window_of([(lat, lon)], radius_m + margin_m, lat)


@dataclass
class Pin:
    """One caller-supplied measured number the fixture must reproduce."""
    raw: str
    kind: str                       # family | row | total
    family: Optional[str]
    metric: str
    value: float
    tol: float
    at: Optional[tuple] = None      # (lat, lon) for kind == "row"
    near_m: float = 3.0
    source_value: Optional[float] = None
    source_n: Optional[int] = None


_PIN_RE = re.compile(
    r"^(?P<kind>family|row|total):"
    r"(?P<sel>[^:]+):"
    r"(?P<metric>[A-Za-z_]+)"
    r"=(?P<value>-?[0-9.]+)"
    r"(?:\s*(?:\+/-|~)\s*(?P<tol>[0-9.]+))?$")

_ROW_SEL_RE = re.compile(
    r"^(?P<family>[A-Za-z_]+)@(?P<lat>-?[0-9.]+),(?P<lon>-?[0-9.]+)"
    r"(?:/(?P<near>[0-9.]+))?$")

FAMILY_METRICS = {"count", "worst_m", "worst_grade_pct"}
ROW_METRICS = {"magnitude_m", "grade_pct", "count"}
TOTAL_METRICS = {"lawtrue", "adjudicated", "airside_for_acceptance"}


def parse_pin(spec: str) -> Pin:
    """``KIND:SELECTOR:METRIC=VALUE[+/-TOL]`` -> :class:`Pin`.

    Three kinds, all measured over the rows whose SITE lies in the cut
    disc, so the identical pin evaluates on the source patch and on the
    fixture patch:

        family:transverse:count=24
        family:transverse:worst_m=3.3595+/-0.01
        row:transverse@35.20342,-80.94468/3:grade_pct=39.02+/-0.05
        total:adjudicated:n=388

    Default tolerance is the materiality floor (0.01 m / 0.01 pp);
    counts are exact.
    """
    m = _PIN_RE.match(spec.strip())
    if not m:
        raise ReproRefusal(
            f"unparseable pin {spec!r}.  Grammar: "
            f"family:<FAM>:<count|worst_m|worst_grade_pct>=V[+/-T] | "
            f"row:<FAM>@LAT,LON[/NEAR_M]:<magnitude_m|grade_pct|count>"
            f"=V[+/-T] | total:<lawtrue|adjudicated|"
            f"airside_for_acceptance>=V[+/-T]")
    kind, sel, metric = m["kind"], m["sel"], m["metric"]
    value = float(m["value"])
    at = None
    near_m = 3.0
    if kind == "family":
        family = sel
        if metric not in FAMILY_METRICS:
            raise ReproRefusal(
                f"pin {spec!r}: family metric must be one of "
                f"{sorted(FAMILY_METRICS)}")
    elif kind == "row":
        rm = _ROW_SEL_RE.match(sel)
        if not rm:
            raise ReproRefusal(
                f"pin {spec!r}: row selector must be FAMILY@LAT,LON[/NEAR_M]")
        family = rm["family"]
        at = (float(rm["lat"]), float(rm["lon"]))
        if rm["near"]:
            near_m = float(rm["near"])
        if metric not in ROW_METRICS:
            raise ReproRefusal(
                f"pin {spec!r}: row metric must be one of {sorted(ROW_METRICS)}")
    else:
        family = None
        if sel not in TOTAL_METRICS or metric != "n":
            raise ReproRefusal(
                f"pin {spec!r}: total pins are total:<{'|'.join(sorted(TOTAL_METRICS))}>:n=V")
        metric = sel
    if m["tol"] is not None:
        tol = float(m["tol"])
    elif metric in ("count", "lawtrue", "adjudicated", "airside_for_acceptance"):
        tol = DEFAULT_TOL["count"]
    elif metric.endswith("_pct"):
        tol = DEFAULT_TOL["pct"]
    else:
        tol = DEFAULT_TOL["m"]
    if family is not None and family in MESH_SIDE_FAMILIES:
        raise ReproRefusal(
            f"R1: pin {spec!r} names the MESH-SIDE family {family!r}.  Its "
            f"value is produced by Triangle4XP, not by the patch/solver "
            f"pipeline a fixture replays — mesh-side classes are OUT of "
            f"repro-cutter v1 scope (spec, 'Honesty rails').")
    return Pin(raw=spec.strip(), kind=kind, family=family, metric=metric,
               value=value, tol=tol, at=at, near_m=near_m)


def refuse_tile_boundary(lat: float, lon: float, radius_m: float,
                         margin_m: float) -> None:
    """R2 — a disc straddling an integer degree cannot carry its class.

    Tile-boundary effects (the seam pins, the per-tile DEM cut) are
    produced by TWO tile builds meeting; one fixture has one tile.
    """
    la0, la1, lo0, lo1 = disc_window(lat, lon, radius_m, margin_m)
    if math.floor(la0) != math.floor(la1) or math.floor(lo0) != math.floor(lo1):
        raise ReproRefusal(
            f"R2: the disc at ({lat}, {lon}) r={radius_m:g} m "
            f"(+{margin_m:g} m margin) crosses a TILE BOUNDARY "
            f"(lat {math.floor(la0)}..{math.floor(la1)}, "
            f"lon {math.floor(lo0)}..{math.floor(lo1)}).  A tile-boundary "
            f"effect is produced by two tile builds meeting; a fixture has "
            f"one tile and cannot carry it.  Move the coordinate inland or "
            f"shrink the radius.")


# ─────────────────────────────────────────────────────────────────────
# The emitted-patch reader/writer (text-faithful: nothing is re-derived)
# ─────────────────────────────────────────────────────────────────────

_NODE_OPEN = re.compile(r"<node id='(-?\d+)'[^>]*lat='([-0-9.]+)' "
                        r"lon='([-0-9.]+)'")
_WAY_OPEN = re.compile(r"<way id='(-?\d+)'")
_ND_REF = re.compile(r"<nd ref='(-?\d+)'")
_TAG_KV = re.compile(r"<tag k='([^']*)' v='([^']*)'")


@dataclass
class PatchDoc:
    """A patch .osm held as its own text blocks — never re-derived."""
    prologue: list = field(default_factory=list)   # xml decl + <osm ...>
    epilogue: list = field(default_factory=list)   # </osm>
    node_lines: dict = field(default_factory=dict)  # nid -> [lines]
    node_ll: dict = field(default_factory=dict)     # nid -> (lat, lon)
    way_lines: dict = field(default_factory=dict)   # wid -> [lines]
    way_nids: dict = field(default_factory=dict)    # wid -> [nid]
    way_tags: dict = field(default_factory=dict)    # wid -> {k: v}
    order: list = field(default_factory=list)       # [("node"|"way", id)]


def read_patch(path: Path) -> PatchDoc:
    """Parse a patch .osm into blocks, preserving every line verbatim."""
    doc = PatchDoc()
    lines = Path(path).read_text().splitlines()
    i = 0
    while i < len(lines) and "<osm " not in lines[i]:
        doc.prologue.append(lines[i])
        i += 1
    if i < len(lines):
        doc.prologue.append(lines[i])
        i += 1
    cur = None          # ("node"|"way", id)
    buf: list = []
    for line in lines[i:]:
        s = line.strip()
        if s.startswith("</osm"):
            doc.epilogue.append(line)
            continue
        m = _NODE_OPEN.search(line)
        if m and s.startswith("<node"):
            if cur:
                _flush(doc, cur, buf)
            nid = m.group(1)
            doc.node_ll[nid] = (float(m.group(2)), float(m.group(3)))
            cur, buf = ("node", nid), [line]
            if s.endswith("/>"):
                _flush(doc, cur, buf)
                cur, buf = None, []
            continue
        m = _WAY_OPEN.search(line)
        if m and s.startswith("<way"):
            if cur:
                _flush(doc, cur, buf)
            cur, buf = ("way", m.group(1)), [line]
            doc.way_nids[m.group(1)] = []
            doc.way_tags[m.group(1)] = {}
            continue
        if cur is None:
            continue
        buf.append(line)
        if cur[0] == "way":
            nd = _ND_REF.search(line)
            if nd:
                doc.way_nids[cur[1]].append(nd.group(1))
            tg = _TAG_KV.search(line)
            if tg:
                doc.way_tags[cur[1]][tg.group(1)] = tg.group(2)
        if s.startswith("</node>") or s.startswith("</way>"):
            _flush(doc, cur, buf)
            cur, buf = None, []
    if cur:
        _flush(doc, cur, buf)
    return doc


def _flush(doc: PatchDoc, cur, buf) -> None:
    kind, ident = cur
    (doc.node_lines if kind == "node" else doc.way_lines)[ident] = list(buf)
    doc.order.append((kind, ident))


def select_ways(doc: PatchDoc, center, radius_m: float) -> tuple:
    """``(seed_wids, kept_wids)`` — THE EXTRACTION CLOSURE.

    A way is a SEED when any of its vertices lies within ``radius_m`` of
    ``center`` (a disc hit).  A way is KEPT when it is a seed or shares
    at least one node id with a seed — ONE ring of welded adjacency.

    Shared node ids are the ONLY record of a weld in an emitted patch
    (``layout.to_osm`` interns every vertex through the canonical-point
    registry and then T-welds nid-level), so dropping a way that shares a
    nid would delete the weld evidence the grade law reads — the chain
    would not stay closed.  Pure: no I/O, no environment.
    """
    lat0, lon0 = center
    ll_to_m = ll_to_m_factory(lat0, lon0)
    seeds = set()
    for wid, nids in doc.way_nids.items():
        for nid in nids:
            ll = doc.node_ll.get(nid)
            if ll is None:
                continue
            x, y = ll_to_m(ll[0], ll[1])
            if x * x + y * y <= radius_m * radius_m:
                seeds.add(wid)
                break
    seed_nids = set()
    for wid in seeds:
        seed_nids.update(doc.way_nids[wid])
    kept = set(seeds)
    for wid, nids in doc.way_nids.items():
        if wid in kept:
            continue
        if seed_nids.intersection(nids):
            kept.add(wid)
    return seeds, kept


def write_patch_slice(doc: PatchDoc, kept_wids, out: Path,
                      extra_root_attrs: dict) -> dict:
    """Emit the kept ways plus every node they reference, verbatim.

    Returns ``{"ways", "nodes"}``.  The ``<osm>`` root keeps the source's
    whole provenance block (so ``census`` reports the frame the artifact
    was built in) and gains the ``o4_repro_*`` attributes naming the cut.
    """
    keep_nids = set()
    for wid in kept_wids:
        keep_nids.update(doc.way_nids[wid])
    root = list(doc.prologue)
    if root:
        add = " ".join(f"{k}='{v}'" for k, v in sorted(extra_root_attrs.items()))
        root[-1] = root[-1].replace(">", " " + add + ">", 1)
    body: list = []
    for kind, ident in doc.order:
        if kind == "node" and ident in keep_nids:
            body.extend(doc.node_lines[ident])
        elif kind == "way" and ident in kept_wids:
            body.extend(doc.way_lines[ident])
    text = "\n".join(root + body + (doc.epilogue or ["</osm>"])) + "\n"
    out.write_text(text)
    return {"ways": len(kept_wids), "nodes": len(keep_nids)}


def slice_sidecar(sidecar: dict, window) -> dict:
    """The sidecar slice: geometry keys subset to the window, rest verbatim.

    ``anchor`` and ``ruleset`` are carried UNCHANGED — ``run_checks``
    reprojects every context list through that anchor and adjudicates
    under that ruleset, so a re-anchored fixture would be measured in a
    different frame than the artifact it claims to reproduce.  Only the
    keys in :data:`SIDECAR_GEOMETRY_KEYS` are subset; ``axes``/``routes``/
    ``axes_exact``/``routes_exact`` ride verbatim because
    ``axes_exact``'s route ordinal indexes ``routes_exact`` POSITIONALLY.
    """
    out = {}
    for key, value in sidecar.items():
        shape = SIDECAR_GEOMETRY_KEYS.get(key)
        if shape is None or not isinstance(value, list):
            out[key] = value
            continue
        out[key] = [e for e in value if _sidecar_entry_in(e, shape, window)]
    return out


def _sidecar_entry_in(entry, shape: str, window) -> bool:
    try:
        if shape == "point":
            return point_in_window(entry[0], entry[1], window)
        if shape == "point+v":
            return point_in_window(entry[0], entry[1], window)
        if shape in ("pairs", "pairs+v"):
            a, b = entry[0], entry[1]
            return segment_hits_window(a, b, window)
        if shape == "ring":
            return any(point_in_window(p[0], p[1], window) for p in entry)
    except (TypeError, IndexError):
        return True                      # keep what we cannot classify
    return True


# ─────────────────────────────────────────────────────────────────────
# The apt.dat slice
# ─────────────────────────────────────────────────────────────────────

def read_airport_block(apt_path: Path, icao: str) -> tuple:
    """``(file_header_lines, block_lines)`` for ``icao``.

    Mirrors ``apt_dat_reader._read_airport_block``'s block grammar: an
    airport block opens on row 1/16/17 and runs to the next one (or 99).
    """
    header: list = []
    block: list = []
    in_block = False
    seen_first_airport = False
    with open(apt_path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            toks = line.split()
            code = toks[0] if toks else ""
            if code in ("1", "16", "17"):
                seen_first_airport = True
                if in_block:
                    break
                in_block = (len(toks) > 4 and toks[4].upper() == icao.upper())
                if in_block:
                    block.append(line)
                continue
            if code == "99":
                if in_block:
                    break
                continue
            if in_block:
                block.append(line)
            elif not seen_first_airport:
                header.append(line)
    if not block:
        raise ReproRefusal(
            f"R3: no airport block for {icao} in {apt_path} — the patch's "
            f"own provenance names this file, so either the patch is not "
            f"{icao}'s or the install changed under it.")
    return header, block


def slice_apt_block(block: list, window) -> tuple:
    """``(kept_lines, stats)`` — the apt.dat rows whose geometry is in view.

    Block grammar (X-Plane 1100/1200): a 110/120/130 HEADER owns every
    following 111-116 node row (a 110 may carry several contours — holes
    — so the block ends only at the next non-node row).  Kept when any of
    its nodes, or any of its segments, touches the window.

    Runways (row 100) are kept whole when their centreline touches the
    window: the strip, RESA and abeam-longitudinal laws are defined
    against the WHOLE runway, so half a runway is a different law.

    The 1200 taxi network is kept by edge: a 1202/1206 survives when
    either endpoint node is in view, and every node a surviving edge
    references is kept even if it lies outside.  Everything not
    geometric (the header row, flow rules, metadata) rides verbatim.
    """
    kept: list = []
    stats = {"blocks_in": 0, "blocks_kept": 0, "runways_in": 0,
             "runways_kept": 0, "edges_in": 0, "edges_kept": 0,
             "points_in": 0, "points_kept": 0}
    # pass 1 — split into records
    records: list = []          # (kind, lines, payload)
    i = 0
    while i < len(block):
        toks = block[i].split()
        code = int(toks[0]) if toks and toks[0].lstrip("-").isdigit() else -1
        if code in APT_BLOCK_HEADERS:
            lines = [block[i]]
            pts = []
            j = i + 1
            while j < len(block):
                t2 = block[j].split()
                c2 = int(t2[0]) if t2 and t2[0].lstrip("-").isdigit() else -1
                if c2 not in APT_NODE_ROWS:
                    break
                lines.append(block[j])
                try:
                    pts.append((float(t2[1]), float(t2[2])))
                except (IndexError, ValueError):
                    pass
                j += 1
            records.append(("block", lines, pts))
            i = j
            continue
        if code == 100:
            try:
                pts = [(float(toks[9]), float(toks[10])),
                       (float(toks[18]), float(toks[19]))]
            except (IndexError, ValueError):
                pts = []
            records.append(("runway", [block[i]], pts))
        elif code in (1202, 1206):
            attrs = [block[i]]
            j = i + 1
            while j < len(block):
                t2 = block[j].split()
                c2 = int(t2[0]) if t2 and t2[0].lstrip("-").isdigit() else -1
                if c2 not in APT_EDGE_ATTR_ROWS:
                    break
                attrs.append(block[j])
                j += 1
            records.append(("edge", attrs, (toks[1], toks[2])
                            if len(toks) > 2 else None))
            i = j
            continue
        elif code == 1201:
            try:
                records.append(("taxinode", [block[i]],
                                (toks[4], (float(toks[1]), float(toks[2])))))
            except (IndexError, ValueError):
                records.append(("verbatim", [block[i]], None))
        elif code in APT_POINT_ROWS:
            try:
                records.append(("point", [block[i]],
                                (float(toks[1]), float(toks[2]))))
            except (IndexError, ValueError):
                records.append(("verbatim", [block[i]], None))
        else:
            records.append(("verbatim", [block[i]], None))
        i += 1

    # pass 2 — decide edges, then the taxi nodes they need
    node_ll = {p[0]: p[1] for k, _l, p in records if k == "taxinode" and p}
    needed_nodes = set()
    edge_keep = {}
    for idx, (kind, lines, payload) in enumerate(records):
        if kind != "edge":
            continue
        stats["edges_in"] += 1
        keep = False
        if payload:
            for nid in payload:
                ll = node_ll.get(nid)
                if ll and point_in_window(ll[0], ll[1], window):
                    keep = True
                    break
        edge_keep[idx] = keep
        if keep:
            stats["edges_kept"] += 1
            needed_nodes.update(payload or ())

    # pass 3 — emit
    for idx, (kind, lines, payload) in enumerate(records):
        if kind == "verbatim":
            kept.extend(lines)
        elif kind == "block":
            stats["blocks_in"] += 1
            hit = any(point_in_window(p[0], p[1], window) for p in payload)
            if not hit and len(payload) > 1:
                hit = any(segment_hits_window(payload[k], payload[k + 1],
                                              window)
                          for k in range(len(payload) - 1))
            if hit:
                stats["blocks_kept"] += 1
                kept.extend(lines)
        elif kind == "runway":
            stats["runways_in"] += 1
            if len(payload) == 2 and segment_hits_window(payload[0],
                                                         payload[1], window):
                stats["runways_kept"] += 1
                kept.extend(lines)
        elif kind == "edge":
            if edge_keep.get(idx):
                kept.extend(lines)
        elif kind == "taxinode":
            nid, ll = payload
            if nid in needed_nodes or point_in_window(ll[0], ll[1], window):
                kept.extend(lines)
        elif kind == "point":
            stats["points_in"] += 1
            if point_in_window(payload[0], payload[1], window):
                stats["points_kept"] += 1
                kept.extend(lines)
    if stats["blocks_kept"] == 0 and stats["runways_kept"] == 0:
        raise ReproRefusal(
            "R7: the window selects NO apt.dat geometry (0 pavement blocks, "
            "0 runways).  A fixture with no input cannot rebuild the site.")
    return kept, stats


# ─────────────────────────────────────────────────────────────────────
# The measurement — ONE instrument (tools/harness/census.py)
# ─────────────────────────────────────────────────────────────────────

def _load_census():
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    import census                                     # noqa: E402
    return census


def census_rows(patch: Path, tmp_dir: Path) -> tuple:
    """``(report, rows)`` from ``census_one`` — every law-true row itemised.

    Nothing here re-derives a grade, enumerates a family or applies an
    exemption: ``census_one`` is ``check_grade.run_checks_law_true`` plus
    the sidecar law context, and ``--rows-json`` is its own itemisation.
    """
    census = _load_census()
    cg = census.load_check_grade()
    rows_out = tmp_dir / "rows.json"
    rep = census.census_one(patch, cg, top=0, rows_out=rows_out)
    rows = json.loads(rows_out.read_text())
    return rep, rows.get("rows", rows if isinstance(rows, list) else [])


def rows_in_disc(rows, center, radius_m: float):
    """Law-true rows whose SITE lies within the cut disc.

    The disc — not the fixture's extent — is the population every pin is
    measured over, which is what lets one pin string evaluate identically
    on the whole source patch and on the fixture.
    """
    lat0, lon0 = center
    ll_to_m = ll_to_m_factory(lat0, lon0)
    out = []
    for r in rows:
        lat, lon = r.get("lat"), r.get("lon")
        if lat is None or lon is None:
            continue
        x, y = ll_to_m(lat, lon)
        if x * x + y * y <= radius_m * radius_m:
            out.append(r)
    return out


def refuse_pins_outside_disc(pins, lat: float, lon: float,
                             radius_m: float) -> None:
    """R4 — a pin the fixture does not contain can never be reproduced."""
    ll_to_m = ll_to_m_factory(lat, lon)
    for p in pins:
        if p.at is None:
            continue
        d = math.hypot(*ll_to_m(p.at[0], p.at[1]))
        if d > radius_m:
            raise ReproRefusal(
                f"R4: pin {p.raw!r} sites at {p.at} — {d:.1f} m from the cut "
                f"centre, outside the {radius_m:g} m disc.  A pin the "
                f"fixture does not contain can never be reproduced.")


def verify_pins_against_source(pins, rep: dict, rows, center,
                               radius_m: float, label: str = "the source"):
    """R5 — every pin is re-measured on the SOURCE artifact and must match.

    A pin nobody checked would make the fixture's REPRODUCED meaningless:
    a fixture built around a number the artifact does not carry reports
    REPRODUCED exactly when it agrees with a fiction.  Each pin's measured
    source value is stamped onto the pin (and into ``repro.json``) so the
    manifest carries the evidence, not the claim.
    """
    for p in pins:
        value, n = measure_pin(p, rep, rows, center)
        p.source_value, p.source_n = (None if value != value
                                      else round(value, 4)), n
        if value != value or abs(value - p.value) > p.tol:
            raise ReproRefusal(
                f"R5: pin {p.raw!r} is NOT a measured number of {label}.  "
                f"The census over the {radius_m:g} m disc reports "
                f"{p.source_value!r} ({n} matching row(s)), pinned "
                f"{p.value!r} +/-{p.tol!r}.  Measure it on the artifact "
                f"first (tools/harness/census.py --rows-json).")
    return pins


def measure_pin(pin: Pin, rep: dict, rows, center) -> tuple:
    """``(value, n_matched)`` for one pin against one census.  Pure."""
    if pin.kind == "total":
        if pin.metric == "lawtrue":
            return float(rep["lawtrue"]["total"]), rep["lawtrue"]["total"]
        if pin.metric == "adjudicated":
            n = rep["adjudication"]["adjudicated_total"]
            return float(n), n
        n = rep["adjudicated_airside_for_acceptance"]
        return float(n), n
    fam = [r for r in rows if r["family"] == pin.family]
    if pin.kind == "row":
        ll_to_m = ll_to_m_factory(pin.at[0], pin.at[1])
        near = []
        for r in fam:
            x, y = ll_to_m(r["lat"], r["lon"])
            if math.hypot(x, y) <= pin.near_m:
                near.append(r)
        fam = near
    if pin.metric == "count":
        return float(len(fam)), len(fam)
    key = "magnitude_m" if pin.metric in ("worst_m", "magnitude_m") \
        else "grade_pct"
    vals = [r[key] for r in fam if r.get(key) is not None]
    if not vals:
        return float("nan"), 0
    return float(max(vals)), len(fam)


# ─────────────────────────────────────────────────────────────────────
# The DEM window
# ─────────────────────────────────────────────────────────────────────

def crop_dem(dem, window):
    """``dict`` describing ``dem`` cropped to ``window`` (tile-relative).

    Cropping is honest about its edges: ``x0..y1`` are set to the CROPPED
    extent, so ``alt_strict`` answers ``nodata`` outside the window
    instead of silently clamping to an edge value the artifact never saw.
    That is why the window is grown by ``--margin`` beyond the kept
    geometry.
    """
    import numpy as np
    la0, la1, lo0, lo1 = window
    # tile-relative degrees, the frame dem.x0..y1 live in
    tx0, tx1 = lo0 - dem.lon, lo1 - dem.lon
    ty0, ty1 = la0 - dem.lat, la1 - dem.lat
    nx, ny = dem.nxdem, dem.nydem
    def _col(x):
        return (x - dem.x0) / (dem.x1 - dem.x0) * (nx - 1)
    def _row(y):
        return (dem.y1 - y) / (dem.y1 - dem.y0) * (ny - 1)
    c0 = max(0, int(math.floor(_col(tx0))))
    c1 = min(nx - 1, int(math.ceil(_col(tx1))))
    r0 = max(0, int(math.floor(_row(ty1))))
    r1 = min(ny - 1, int(math.ceil(_row(ty0))))
    if c1 <= c0 or r1 <= r0:
        raise ReproRefusal(
            f"R7: the DEM window is empty against this raster "
            f"(cols {c0}..{c1}, rows {r0}..{r1}) — the site is outside the "
            f"DEM the build frame recorded.")
    sub = np.array(dem.alt_dem[r0:r1 + 1, c0:c1 + 1], dtype="float32")
    px = (dem.x1 - dem.x0) / (nx - 1)
    py = (dem.y1 - dem.y0) / (ny - 1)
    return {
        "alt_dem": sub,
        "x0": dem.x0 + c0 * px, "x1": dem.x0 + c1 * px,
        "y1": dem.y1 - r0 * py, "y0": dem.y1 - r1 * py,
        "lat": int(dem.lat), "lon": int(dem.lon),
        "nodata": float(dem.nodata),
        "elevation_level": str(getattr(dem, "elevation_level", "auto")),
        "source_path": str(getattr(dem, "source_path", "")),
    }


def dem_from_window(rec, subdems):
    """A real ``O4_DEM_Utils.DEM`` wearing the cropped window.

    Built with ``__new__`` and field assignment so the SAMPLING MATH is
    the engine's own (``alt_nostrict`` / ``alt_composite`` bound methods),
    not a copy that could drift from it.
    """
    sys.path.insert(0, str(ROOT / "src")) if str(ROOT / "src") not in sys.path \
        else None
    from O4_DEM_Utils import DEM
    d = DEM.__new__(DEM)
    d.alt_dem = rec["alt_dem"]
    d.nydem, d.nxdem = d.alt_dem.shape
    d.x0, d.x1 = float(rec["x0"]), float(rec["x1"])
    d.y0, d.y1 = float(rec["y0"]), float(rec["y1"])
    d.lat, d.lon = int(rec["lat"]), int(rec["lon"])
    d.nodata = rec["nodata"]
    d.epsg = 4326
    d.elevation_level = rec["elevation_level"]
    d.source_path = rec["source_path"]
    d.baked_query_active = False
    d.subdems = list(subdems)
    d.alt = d.alt_composite if d.subdems else d.alt_nostrict
    d.alt_vec = d.alt_vec_composite if d.subdems else d.alt_vec_nostrict
    return d


def save_dem_window(dem, window, out: Path) -> dict:
    """Crop base + every overlapping inset subdem; save lane-local."""
    import numpy as np
    base = crop_dem(dem, window)
    subs = []
    for sd in getattr(dem, "subdems", None) or ():
        try:
            subs.append(crop_dem(sd, window))
        except ReproRefusal:
            continue                     # inset does not reach this window
    payload = {"base_" + k: v for k, v in base.items()}
    payload["n_sub"] = np.array(len(subs))
    for i, s in enumerate(subs):
        for k, v in s.items():
            payload[f"sub{i}_{k}"] = v
    np.savez_compressed(out, **payload)
    return {
        "shape": list(base["alt_dem"].shape),
        "subdems": len(subs),
        "subdem_sources": [s["source_path"] for s in subs],
        "base_source": base["source_path"],
        "min_m": float(np.min(base["alt_dem"])),
        "max_m": float(np.max(base["alt_dem"])),
    }


def load_dem_window(path: Path):
    import numpy as np
    z = np.load(path, allow_pickle=False)

    def _rec(prefix):
        return {
            "alt_dem": z[prefix + "alt_dem"],
            "x0": float(z[prefix + "x0"]), "x1": float(z[prefix + "x1"]),
            "y0": float(z[prefix + "y0"]), "y1": float(z[prefix + "y1"]),
            "lat": int(z[prefix + "lat"]), "lon": int(z[prefix + "lon"]),
            "nodata": float(z[prefix + "nodata"]),
            "elevation_level": str(z[prefix + "elevation_level"]),
            "source_path": str(z[prefix + "source_path"]),
        }
    subs = [dem_from_window(_rec(f"sub{i}_"), [])
            for i in range(int(z["n_sub"]))]
    return dem_from_window(_rec("base_"), subs)


# ─────────────────────────────────────────────────────────────────────
# THE CUT
# ─────────────────────────────────────────────────────────────────────

def default_patch_for(icao: str) -> Path:
    """The SHIPPED artifact — the owner's build (RULINGS 2026-08-12)."""
    sys.path.insert(0, str(HARNESS)) if str(HARNESS) not in sys.path else None
    from shared_repo_guard import DATA_REPO
    hits = sorted((DATA_REPO / "Patches").glob(
        f"*/*/{icao.upper()}_auto.patch.osm"))
    if not hits:
        raise ReproRefusal(
            f"R3: no shipped artifact for {icao} under {DATA_REPO}/Patches.  "
            f"The owner's artifact IS the attribution baseline (RULINGS "
            f"2026-08-12) — this tool never triggers a build.  Pass "
            f"--patch to name one explicitly.")
    if len(hits) > 1:
        raise ReproRefusal(
            f"R3: {len(hits)} shipped artifacts for {icao} "
            f"({', '.join(str(h) for h in hits)}) — a cross-tile airport "
            f"must be cut from ONE named patch (--patch).")
    return hits[0]


def _unquote(v: str) -> str:
    from urllib.parse import unquote
    return unquote(v)


def root_attrs(doc: PatchDoc) -> dict:
    line = doc.prologue[-1] if doc.prologue else ""
    return {m.group(1): m.group(2)
            for m in re.finditer(r"(\w+)='([^']*)'", line)}


def cut(icao: str, lat: float, lon: float, radius_m: float, *,
        patch: Optional[Path] = None, out: Optional[Path] = None,
        pins=(), margin_m: float = DEFAULT_MARGIN_M,
        copy_osm: bool = False, allow_degraded_dem: bool = False,
        quiet: bool = False) -> Path:
    """Extract the fixture.  Reads only; writes only under ``out``."""
    t0 = time.time()
    icao = icao.upper()
    pins = [p if isinstance(p, Pin) else parse_pin(p) for p in pins]
    refuse_tile_boundary(lat, lon, radius_m, margin_m)          # R2

    src = Path(patch) if patch else default_patch_for(icao)
    sidecar_path = Path(str(src) + ".axes.json")
    if not sidecar_path.is_file():
        raise ReproRefusal(                                     # R6
            f"R6: no sidecar beside {src}.  Without .axes.json every census "
            f"silently degrades to the context-free frame that OVERCOUNTS "
            f"(memory 'check-grade-needs-law-true-frame') — a fixture cut "
            f"in that frame would pin numbers the law never produced.")
    doc = read_patch(src)
    attrs = root_attrs(doc)
    if attrs.get("o4_provenance_icao", icao).upper() != icao:
        raise ReproRefusal(                                     # R3
            f"R3: {src} is {attrs.get('o4_provenance_icao')}'s patch, not "
            f"{icao}'s.  A fixture carries ONE airport; a cross-airport "
            f"claim cannot be cut.")
    sidecar = json.loads(sidecar_path.read_text())

    refuse_pins_outside_disc(pins, lat, lon, radius_m)          # R4

    seeds, kept = select_ways(doc, (lat, lon), radius_m)
    if not kept:
        raise ReproRefusal(                                     # R7
            f"R7: the {radius_m:g} m disc at ({lat}, {lon}) selects NO shape "
            f"in {src.name}.  Nothing to reproduce.")

    out_dir = Path(out) if out else (ROOT / "tmp" / "repro"
                                     / f"{icao}_{lat:.5f}_{lon:.5f}_"
                                       f"r{int(radius_m)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run").mkdir(exist_ok=True)

    # THE WINDOW IS THE DISC + MARGIN, not the extent of the kept shapes.
    # A welded neighbour can be a 128,000 m2 apron reaching across the
    # airport, so windowing on the kept geometry made the input slice
    # (and the build) grow with the biggest neighbour rather than with
    # the radius the caller asked for — measured 2026-08-12 at KCLT: a
    # 300 m disc produced a 522-shape, 78 s fixture.  The reference slice
    # still carries those neighbours WHOLE (the weld evidence); only the
    # apt.dat and DEM windows are bounded.
    window = disc_window(lat, lon, radius_m, margin_m)

    ref = out_dir / "reference.patch.osm"
    counts = write_patch_slice(doc, kept, ref, {
        "o4_repro_source": str(src),
        "o4_repro_coord": f"{lat:.8f},{lon:.8f}",
        "o4_repro_radius_m": f"{radius_m:g}",
    })
    Path(str(ref) + ".axes.json").write_text(
        json.dumps(slice_sidecar(sidecar, window)))

    # apt.dat slice — the pipeline's actual input
    apt_src = Path(_unquote(attrs.get("o4_apt_dat", "")))
    if not apt_src.is_file():
        raise ReproRefusal(
            f"R3: the patch names apt.dat {apt_src} in its own provenance "
            f"and it is not on disk — the install moved under the artifact.")
    header, block = read_airport_block(apt_src, icao)
    kept_rows, apt_stats = slice_apt_block(block, window)
    apt_out = out_dir / "apt.dat"
    apt_out.write_text("\n".join(header + kept_rows + ["99"]) + "\n")

    # the fixture X-Plane root: a symlink farm with the SLICED apt.dat
    xp_root = _build_xplane_root(out_dir, apt_src, apt_out)

    # the OSM inputs this airport reads, pinned (and optionally copied)
    osm_manifest = _stage_osm(out_dir, lat, lon, copy_osm)

    # the DEM window, from the source the build frame records
    tile_lat, tile_lon = int(math.floor(lat)), int(math.floor(lon))
    dem_info = _stage_dem(out_dir, tile_lat, tile_lon, window, str(xp_root),
                          allow_degraded_dem)

    # R5 — every pin re-measured on the SOURCE artifact
    rep, rows = census_rows(src, out_dir / "run")
    disc_rows = rows_in_disc(rows, (lat, lon), radius_m)
    verify_pins_against_source(pins, rep, disc_rows, (lat, lon), radius_m,
                               label=src.name)

    manifest = {
        "tool": "repro_cut.py",
        "version": 1,
        "cut_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cut_wall_s": round(time.time() - t0, 2),
        "icao": icao,
        "coord": [lat, lon],
        "radius_m": radius_m,
        "margin_m": margin_m,
        "window": list(window),
        "tile": [tile_lat, tile_lon],
        "source": {
            "patch": str(src),
            "sha256": _sha256(src),
            "sidecar_sha256": _sha256(sidecar_path),
            "provenance": {k: _unquote(v) for k, v in attrs.items()
                           if k.startswith("o4_")},
        },
        "extraction": {
            "seed_ways": len(seeds), "kept_ways": counts["ways"],
            "welded_neighbours": counts["ways"] - len(seeds),
            "nodes": counts["nodes"], "apt_dat": apt_stats,
        },
        "dem": dem_info,
        "osm": osm_manifest,
        "xplane_root": str(xp_root),
        "run_env": {
            "O4_FORCE_APT_DAT": str(apt_out),
            "ORTHO4XP_DATA_ROOT": None,
            "note": "OSM_dir is repointed at the fixture's osm/ overlay in "
                    "process; every other input resolves as production, "
                    "read-only.",
        },
        "pins": [_pin_json(p) for p in pins],
        "source_census": {
            "lawtrue_total": rep["lawtrue"]["total"],
            "adjudicated_total": rep["adjudication"]["adjudicated_total"],
            "rows_in_disc": len(disc_rows),
            "ruleset": rep["ruleset_active"],
        },
    }
    (out_dir / "repro.json").write_text(json.dumps(manifest, indent=2))
    if not quiet:
        _print_cut(manifest, out_dir)
    return out_dir


def _pin_json(p: Pin) -> dict:
    return {"pin": p.raw, "kind": p.kind, "family": p.family,
            "metric": p.metric, "value": p.value, "tol": p.tol,
            "at": list(p.at) if p.at else None, "near_m": p.near_m,
            "source_value": p.source_value, "source_rows": p.source_n}


def _sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_xplane_root(out_dir: Path, apt_src: Path, apt_slice: Path) -> Path:
    """A symlink farm rooted at ``out_dir/xplane``.

    ``Custom Data`` (CIFP) and ``Resources`` link straight at the install;
    the pack that owns ``apt_src`` is mirrored file-by-file as symlinks
    (so its DSF is read warm) with the SLICED apt.dat put in place of the
    real one.  Nothing in the install is written.
    """
    sys.path.insert(0, str(HARNESS)) if str(HARNESS) not in sys.path else None
    from shared_repo_guard import mirror_tree_as_symlinks
    xp = out_dir / "xplane"
    if xp.exists():
        shutil.rmtree(xp)
    xp.mkdir(parents=True)
    # <install>/Custom Scenery/<pack>/Earth nav data/apt.dat
    end = apt_src.parent
    pack = end.parent
    install = pack.parent.parent if pack.parent.name == "Custom Scenery" \
        else pack.parent
    for top in ("Custom Data", "Resources", "Global Scenery"):
        s = install / top
        if s.is_dir():
            os.symlink(s, xp / top)
    dst_pack = xp / "Custom Scenery" / pack.name
    mirror_tree_as_symlinks(str(pack), str(dst_pack))
    target = dst_pack / end.name / "apt.dat"
    if target.is_symlink() or target.exists():
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(apt_slice.resolve(), target)
    return xp


def _stage_osm(out_dir: Path, lat: float, lon: float,
               copy_osm: bool) -> dict:
    """Stage the corpus OSM tree the airport reads, and PIN what it used.

    A read-through symlink overlay by default (warm reads, any write
    lane-local — the same mechanism the suite uses for the mod cache);
    ``--copy-osm`` copies the tile files the airport actually reads
    (``airports`` over the 3x3 neighbourhood, plus the roads layers) so
    the fixture carries the bytes rather than a reference to them.
    """
    sys.path.insert(0, str(HARNESS)) if str(HARNESS) not in sys.path else None
    sys.path.insert(0, str(ROOT / "src")) if str(ROOT / "src") not in sys.path \
        else None
    from shared_repo_guard import DATA_REPO, mirror_tree_as_symlinks
    import O4_File_Names as FNAMES
    src = Path(FNAMES.OSM_dir)
    if not src.is_dir():
        src = DATA_REPO / "OSM_data"
    dst = out_dir / "osm"
    if dst.exists():
        shutil.rmtree(dst)
    made = mirror_tree_as_symlinks(str(src), str(dst))
    referenced = []
    ilat, ilon = int(math.floor(lat)), int(math.floor(lon))
    for dla in (-1, 0, 1):
        for dlo in (-1, 0, 1):
            for suffix in ("airports", "big_roads", "small_roads"):
                if suffix != "airports" and (dla or dlo):
                    continue
                p = Path(FNAMES.osm_cached(ilat + dla, ilon + dlo, suffix))
                rel = os.path.relpath(p, src)
                here = dst / rel
                entry = {"suffix": suffix, "tile": [ilat + dla, ilon + dlo],
                         "path": str(p), "present": p.is_file()}
                if p.is_file():
                    st = p.stat()
                    entry.update(bytes=st.st_size, mtime=st.st_mtime)
                    if copy_osm and here.is_symlink():
                        here.unlink()
                        shutil.copy2(p, here)
                        entry["carried"] = "copy"
                    else:
                        entry["carried"] = "symlink"
                referenced.append(entry)
    return {"overlay": str(dst), "linked": made, "referenced": referenced,
            "mode": "copy" if copy_osm else "symlink-overlay"}


def _stage_dem(out_dir: Path, tile_lat: int, tile_lon: int, window,
               xplane_root: str, allow_degraded: bool) -> dict:
    """Compose the production DEM once, crop the window, save lane-local."""
    sys.path.insert(0, str(ROOT / "src")) if str(ROOT / "src") not in sys.path \
        else None
    from auto_patch.elevation import _load_airport_dem
    dem = _load_airport_dem(tile_lat + 0.5, tile_lon + 0.5,
                            xplane_root=xplane_root)
    if dem is None:
        raise ReproRefusal(
            "R8: the standalone DEM path returned no surface for tile "
            f"{tile_lat},{tile_lon}.  Warm it with a production build or "
            "tools/fetch_airport_elevation_insets.py before cutting.")
    info = save_dem_window(dem, window, out_dir / "dem.npz")
    info["tile"] = [tile_lat, tile_lon]
    info["inset_provenance"] = getattr(dem, "airport_inset_provenance", None)
    if not info["subdems"] and not allow_degraded:
        raise ReproRefusal(                                     # R8
            f"R8: the DEM window carries ZERO inset subdems.  Warm-vs-cold "
            f"insets have moved terrain 12 m (memory "
            f"'dem-inset-cache-shifts-measurements'), so a fixture cut on "
            f"the bare base raster measures a different surface than the "
            f"artifact.  Warm the cache (build_airport.py --refresh-data "
            f"dem) or accept the worse measurement explicitly with "
            f"--allow-degraded-dem (which authorises NO write).")
    info["degraded_accepted"] = bool(not info["subdems"])
    return info


# ─────────────────────────────────────────────────────────────────────
# THE RUN
# ─────────────────────────────────────────────────────────────────────

def run(fixture_dir: Path, *, quiet: bool = False,
        json_out: Optional[Path] = None) -> dict:
    """Build the fixture and report every pin REPRODUCED / DIVERGED."""
    fixture_dir = Path(fixture_dir)
    manifest = json.loads((fixture_dir / "repro.json").read_text())
    icao = manifest["icao"]
    lat, lon = manifest["coord"]
    radius_m = manifest["radius_m"]
    tile_lat, tile_lon = manifest["tile"]
    run_dir = fixture_dir / "run"
    run_dir.mkdir(exist_ok=True)

    sys.path.insert(0, str(HARNESS)) if str(HARNESS) not in sys.path else None
    from shared_repo_guard import (SharedRepoWriteGuard, shared_repo_snapshot,
                                   snapshot_diff, report_unauthorised_writes,
                                   require_no_swallowed_write_block)
    from build_airport import redirect_engine_caches
    redirect_engine_caches(str(run_dir), "repro")
    os.environ["O4_FORCE_APT_DAT"] = str(fixture_dir / "apt.dat")

    sys.path.insert(0, str(ROOT / "src")) if str(ROOT / "src") not in sys.path \
        else None
    import O4_File_Names as FNAMES
    FNAMES.OSM_dir = str(fixture_dir / "osm")

    before = shared_repo_snapshot()
    guard = SharedRepoWriteGuard(set(), str(ROOT))
    t0 = time.time()
    with guard:
        dem = load_dem_window(fixture_dir / "dem.npz")
        from auto_patch.pipeline import build_airport_pavement
        layout = build_airport_pavement(
            icao, str(fixture_dir / "xplane"), compute_elevations=True,
            tile_dem=dem, current_tile_lat=tile_lat,
            current_tile_lon=tile_lon)
        fresh = run_dir / f"{icao}_repro.patch.osm"
        layout.to_osm(str(fresh))
    build_s = time.time() - t0
    changes = snapshot_diff(before, shared_repo_snapshot())
    unauthorised = report_unauthorised_writes(changes, set())
    require_no_swallowed_write_block(guard.blocked)

    rep, rows = census_rows(fresh, run_dir)
    disc_rows = rows_in_disc(rows, (lat, lon), radius_m)
    results = []
    for pj in manifest["pins"]:
        p = parse_pin(pj["pin"])
        value, n = measure_pin(p, rep, disc_rows, (lat, lon))
        ok = (value == value) and abs(value - p.value) <= p.tol
        results.append({
            "pin": p.raw, "pinned": p.value, "tol": p.tol,
            "source_value": pj.get("source_value"),
            "fixture_value": None if value != value else round(value, 4),
            "fixture_rows": n,
            "delta": None if value != value else round(value - p.value, 4),
            "verdict": "REPRODUCED" if ok else "DIVERGED",
        })
    out = {
        "fixture": str(fixture_dir), "icao": icao,
        "coord": [lat, lon], "radius_m": radius_m,
        "build_wall_s": round(build_s, 2),
        "total_wall_s": round(time.time() - t0, 2),
        "shapes": len(layout.shapes),
        "patch": str(fresh),
        "census": {
            "lawtrue_total": rep["lawtrue"]["total"],
            "adjudicated_total": rep["adjudication"]["adjudicated_total"],
            "rows_in_disc": len(disc_rows),
            "ruleset": rep["ruleset_active"],
        },
        "shared_repo": {"blocked": len(guard.blocked),
                        "lock_churn": len(guard.lock_churn),
                        "unauthorised": len(unauthorised),
                        "changed": sum(len(changes.get(k, ()))
                                       for k in ("changed", "added",
                                                 "removed"))},
        "pins": results,
        "verdict": ("REPRODUCED" if results
                    and all(r["verdict"] == "REPRODUCED" for r in results)
                    else "DIVERGED" if results else "NO PINS"),
    }
    if json_out:
        Path(json_out).write_text(json.dumps(out, indent=2))
    if not quiet:
        _print_run(out)
    return out


# ─────────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────────

def _print_cut(m: dict, out_dir: Path) -> None:
    e = m["extraction"]
    print(f"=== REPRO CUT {m['icao']} @ ({m['coord'][0]}, {m['coord'][1]}) "
          f"r={m['radius_m']:g} m ===")
    print(f"  source   {m['source']['patch']}")
    print(f"           sha {m['source']['sha256'][:16]}  built "
          f"{m['source']['provenance'].get('o4_provenance_built')}  "
          f"engine {m['source']['provenance'].get('o4_engine')}")
    print(f"  shapes   {e['seed_ways']} in the disc + "
          f"{e['welded_neighbours']} welded neighbour(s) = {e['kept_ways']} "
          f"way(s), {e['nodes']} node(s)")
    a = e["apt_dat"]
    print(f"  apt.dat  {a['blocks_kept']}/{a['blocks_in']} pavement block(s), "
          f"{a['runways_kept']}/{a['runways_in']} runway(s), "
          f"{a['edges_kept']}/{a['edges_in']} taxi edge(s)")
    d = m["dem"]
    print(f"  DEM      window {d['shape'][0]}x{d['shape'][1]} px, "
          f"{d['subdems']} inset subdem(s), "
          f"{d['min_m']:.2f}..{d['max_m']:.2f} m")
    print(f"  OSM      {m['osm']['mode']}, "
          f"{sum(1 for r in m['osm']['referenced'] if r['present'])}"
          f"/{len(m['osm']['referenced'])} referenced tile file(s) present")
    print(f"  census   source law-true {m['source_census']['lawtrue_total']}, "
          f"adjudicated {m['source_census']['adjudicated_total']}, "
          f"{m['source_census']['rows_in_disc']} row(s) in the disc "
          f"(ruleset {m['source_census']['ruleset']})")
    print(f"  PINS ({len(m['pins'])}), each verified against the SOURCE:")
    for p in m["pins"]:
        print(f"    {p['pin']:<58} source={p['source_value']} "
              f"({p['source_rows']} row(s))")
    print(f"  -> {out_dir}   ({m['cut_wall_s']:.1f} s)")
    print(f"  run it:  venv/bin/python tools/repro_cut.py --run {out_dir}")


def _print_run(o: dict) -> None:
    print(f"=== REPRO RUN {o['icao']} @ ({o['coord'][0]}, {o['coord'][1]}) "
          f"r={o['radius_m']:g} m ===")
    print(f"  built    {o['shapes']} shape(s) in {o['build_wall_s']:.1f} s "
          f"(total {o['total_wall_s']:.1f} s incl. census)")
    print(f"  census   law-true {o['census']['lawtrue_total']}, adjudicated "
          f"{o['census']['adjudicated_total']}, "
          f"{o['census']['rows_in_disc']} row(s) in the disc")
    sr = o["shared_repo"]
    print(f"  [guard]  shared repo {'UNCHANGED' if not sr['changed'] else 'CHANGED (' + str(sr['changed']) + ')'}"
          f"  blocked={sr['blocked']} lock_churn={sr['lock_churn']}")
    print("  PIN TABLE")
    print(f"    {'pin':<52} {'pinned':>10} {'source':>10} {'fixture':>10} "
          f"{'delta':>9}  verdict")
    for r in o["pins"]:
        print(f"    {r['pin']:<52} {r['pinned']:>10} "
              f"{str(r['source_value']):>10} {str(r['fixture_value']):>10} "
              f"{str(r['delta']):>9}  {r['verdict']}")
    print(f"  VERDICT  {o['verdict']}")


# ─────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="repro_cut.py",
        description="Cut a defect site out of a shipped patch into a "
                    "seconds-fast fixture, and replay it.")
    ap.add_argument("icao", nargs="?", help="airport of the defect site")
    ap.add_argument("--coord", nargs=2, type=float, metavar=("LAT", "LON"))
    ap.add_argument("--radius", type=float, metavar="M")
    ap.add_argument("--patch", default=None,
                    help="source artifact (default: the shipped patch)")
    ap.add_argument("--out", default=None, help="fixture directory")
    ap.add_argument("--pin", action="append", default=[],
                    help="a measured number the fixture must reproduce "
                         "(repeatable); see parse_pin's grammar")
    ap.add_argument("--pins-from", default=None,
                    help="JSON file: a list of pin strings")
    ap.add_argument("--margin", type=float, default=DEFAULT_MARGIN_M)
    ap.add_argument("--copy-osm", action="store_true")
    ap.add_argument("--allow-degraded-dem", action="store_true")
    ap.add_argument("--run", default=None, metavar="FIXTURE_DIR")
    ap.add_argument("--json", default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    try:
        if args.run:
            out = run(Path(args.run), quiet=args.quiet,
                      json_out=Path(args.json) if args.json else None)
            return 0 if out["verdict"] == "REPRODUCED" else 1
        if not (args.icao and args.coord and args.radius):
            ap.error("cut mode needs ICAO --coord LAT LON --radius M")
        pins = list(args.pin)
        if args.pins_from:
            pins.extend(json.loads(Path(args.pins_from).read_text()))
        cut(args.icao, args.coord[0], args.coord[1], args.radius,
            patch=Path(args.patch) if args.patch else None,
            out=Path(args.out) if args.out else None,
            pins=pins, margin_m=args.margin, copy_osm=args.copy_osm,
            allow_degraded_dem=args.allow_degraded_dem, quiet=args.quiet)
        return 0
    except ReproRefusal as exc:
        print(f"REFUSED — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
