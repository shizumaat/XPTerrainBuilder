"""Building-EVIDENCE population of a pack's OBJ8 structure rings (R18-2).

The question this answers: for every structure the object-building
reader forms out of a scenery pack, **what evidence is there that a
BUILDING stands there** — and therefore which rings may seed a building
pad under the owner's evidence ruling (RULINGS 2026-08-11b, spec
``docs/specs/round18-heca-mesh-and-pads-spec.md`` R18-2).

Per structure it reports the two evidence sources and the gates:

* ``tall`` — the VERTICAL-STRUCTURE test: the fraction of the
  structure's own footprint hull covered by member resources whose OWN
  above-grade vertical extent reaches the evidence height.  A real
  building is tall over its own footprint; an apron slab, a jersey
  barrier and a fuel truck are not.
* ``osm``  — an intersecting OSM building / terminal / hangar footprint
  (needs ``--icao``; without it the OSM column reads ``-`` and no OSM
  claim is made, which is not the same as "no building there").
* ``name`` — the library-path vouching (hangar / terminal kits) the
  hull-fill floor already extends.
* the two pending defences, MEASURED rather than assumed: what the
  structure-span gate (``--span-sweep``) and the connector pre-filter
  would each have caught on this pack.

**It measures nothing itself.** Every number comes from the engine's own
code path — ``dsf_reader.read_dsf_object_building_evidence`` runs the
production pooling, partition and ``object_footprints.structure_ring``,
and the coverage is ``object_footprints.tall_member_coverage``, the same
function the gate calls. A private re-derivation of "how tall is it over
its own footprint" here would be the census-wrapper defect.

GUARDED. The reader resolves and parses pack objects and (with
``--icao``) loads OSM through the engine, both of which can write the
shared data repo; the run arms the harness's own composition
(``build_airport.arm_shared_repo_protection`` — the engine derived-cache
redirects plus a refuse-mode ``SharedRepoWriteGuard``) and refuses on a
swallowed block, exactly as ``tools/classify_report.py`` does.

Usage:
    venv/bin/python tools/object_pad_evidence_report.py \\
        --dsf "<pack>/Earth nav data/+30+030/+30+031.dsf" \\
        --pack-root "<pack>" [--icao HECA] \\
        [--coverage-sweep 0.01,0.05,0.1] [--height-sweep 2.5,4,6] \\
        [--span-sweep 300,500,1000] [--limit 40] [--json PATH]

BUILD-TIME IMPACT: none — a report-only tool, imported by nothing in
``src/``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time as _time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT / "src", _ROOT, _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

ARTIFACT_DIR = _ROOT / "tmp" / "object_pad_evidence"


def _harness_build_module():
    """The harness build entry, as a module — its arming composition is
    THE one implementation (owner ruling e9daef5)."""
    import importlib
    harness = _ROOT / "tools" / "harness"
    if str(harness) not in sys.path:
        sys.path.insert(0, str(harness))
    return importlib.import_module("build_airport")


def _floats(text: str) -> list[float]:
    return [float(piece) for piece in text.split(",") if piece.strip()]


def _digest(value) -> str:
    """sha256 of a JSON-canonical rendering — the identity gate an
    optimisation of the partition machinery must hold fixed.  ``repr``
    would encode float text the same way, but JSON with sorted keys is
    stable across dict-ordering churn as well."""
    import hashlib
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=repr).encode()
    ).hexdigest()


def _osm_evidence_predicate(icao: str, xplane_root: str):
    """``(predicate, n_buildings)`` over the airport's OSM buildings —
    production's own extractor and predicate builder, not a second one."""
    import auto_patch.pipeline as pipeline
    from auto_patch import apt_dat_reader as APR
    from auto_patch.layout import _airport_anchor, _projection

    apt_path = pipeline._pick_best_apt_dat_against_osm(xplane_root, icao)
    apt = APR.load_airport(apt_path, icao) if apt_path else None
    if apt is None:
        raise SystemExit(f"no apt.dat for {icao} under {xplane_root}")
    anchor = _airport_anchor(apt)
    to_m = _projection(anchor)
    nodes, ways, relations = pipeline._load_osm_airports(
        xplane_root, icao, anchor[0], anchor[1])
    return pipeline._osm_building_evidence_predicate(
        nodes, ways, relations, to_m)


def collect(dsf_path: str, pack_root: str, xplane_root: str | None,
            icao: str | None, out_dir: Path, prog=None,
            count_specs: tuple[str, ...] = ()) -> dict:
    """Read the pack's structures and join the evidence sources.

    Returns the raw record: one row per structure, plus the run's guard
    and redirect frame (a population measured on a redirected corpus is
    not comparable with one that wrote through).

    ``count_specs`` (``MODULE:ATTR``) additionally wraps named callables
    with the call counter + inclusive timer ``profile_airport_build.py
    --count`` installs — IMPORTED from it, never re-spelled, so a sink
    number quoted here and one quoted from a profiled build mean the
    same thing.  Installed AFTER the guard/redirect composition is
    armed, because importing the engine before that composition is the
    ordering it exists to prevent.  The reader this tool drives
    (``read_dsf_object_building_evidence``) is deliberately UNCACHED, so
    it is the object-partition sink's replay: the same production
    pooling/weld/contact-graph a cold build runs, measurable in one
    airport's worth of wall instead of a whole build's."""
    build_mod = _harness_build_module()
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"objevid_{os.path.basename(dsf_path).replace('.', '_')}"
    guard, redirects = build_mod.arm_shared_repo_protection(
        _ROOT, out_dir, tag, prog)

    os.environ.setdefault("O4_DSF_OBJECT_BUILDINGS", "1")
    import auto_patch.pipeline  # noqa: F401  (cycle-safe entry point)
    from auto_patch import dsf_reader, object_footprints

    counters = []
    if count_specs:
        _tools = _ROOT / "tools"
        if str(_tools) not in sys.path:
            sys.path.insert(0, str(_tools))
        from profile_airport_build import _install_counters
        # CPU seconds, not wall: this reader is a single-threaded
        # CPU-bound sink, and the optimisation lanes share one machine —
        # a wall total here reports the other lanes' load as this
        # function's cost.
        counters = _install_counters(list(count_specs), clock=_time.process_time)

    reader_started = _time.perf_counter()
    reader_cpu_started = _time.process_time()
    with guard:
        rings, evidence = dsf_reader.read_dsf_object_building_evidence(
            dsf_path, xplane_root=xplane_root)
        reader_seconds = _time.perf_counter() - reader_started
        reader_cpu_seconds = _time.process_time() - reader_cpu_started
        osm_predicate = None
        n_osm = None
        if icao:
            osm_predicate, n_osm = _osm_evidence_predicate(
                icao, xplane_root or "")
        rows = []
        for record in evidence:
            row = {
                "verdict": record.get("verdict"),
                "hull_area_m2": record.get("hull_area_m2"),
                "hull_area_degrees2": record.get("hull_area_degrees2"),
                "span_m": record.get("span_m"),
                "centroid": record.get("centroid"),
                "above_grade_extent_m": record.get("above_grade_extent_m"),
                "total_extent_m": record.get("total_extent_m"),
                "name_vouched": bool(record.get("name_vouched")),
                "evidence_name_vouched": bool(
                    record.get("evidence_name_vouched")),
                "tallest_member_extent_m": record.get(
                    "tallest_member_extent_m"),
                "hull_fill": record.get("hull_fill"),
                "tall_base_fill": record.get("tall_base_fill"),
                "vertical_evidence": bool(record.get("vertical_evidence")),
                "evidence_coverage": record.get("evidence_coverage"),
                "members": [
                    {"resource": resource,
                     "above_grade_extent_m": extent,
                     "base_area_degrees2": area}
                    for resource, extent, area in record.get("members", ())],
                "resources": record.get("resources", []),
                # Structure-walls footprints (2026-08-30e): how many
                # disjoint footprint parts this structure contributed,
                # and whether they came from its own geometry or from
                # the convex-hull fallback.
                "parts": record.get("parts"),
                "parts_source": record.get("parts_source"),
                "osm_evidence": None,
            }
            rows.append(row)
        # The OSM half, joined on the RING the reader emitted (the same
        # geometry the pipeline's gate tests).  Since the structure-walls
        # ruling (2026-08-30e) ONE admitted structure emits ``parts``
        # consecutive rings — its disjoint footprint parts — so the walk
        # consumes that many slots per row; a row is OSM-vouched when ANY
        # of its parts is.  (``parts`` is absent only for a record from a
        # reader older than that ruling, where it is 1 by construction.)
        ring_by_index = {}
        emitted = 0
        for record, row in zip(evidence, rows):
            if record.get("verdict") != "ring":
                continue
            for _ in range(int(record.get("parts") or 1)):
                ring_by_index[emitted] = row
                emitted += 1
        for index, (ring, _holes, _role) in enumerate(rings):
            row = ring_by_index.get(index)
            if row is None or osm_predicate is None:
                continue
            row["osm_evidence"] = bool(
                row["osm_evidence"]) or bool(osm_predicate(ring))
    build_mod.require_no_swallowed_write_block(guard.blocked, prog=prog)
    build_mod.report_guard_churn(guard, prog)

    from auto_patch.config import (
        DSF_OBJECT_CONNECTOR_MAX_FILL,
        DSF_OBJECT_CONNECTOR_PREFILTER,
        DSF_OBJECT_CONNECTOR_SPAN_M,
        DSF_OBJECT_EVIDENCE_MIN_COVERAGE,
        DSF_OBJECT_EVIDENCE_MIN_HEIGHT_M,
        DSF_OBJECT_MAX_STRUCTURE_SPAN_M,
    )
    return {
        "dsf": dsf_path,
        "pack_root": pack_root,
        "icao": icao,
        "rings_emitted": len(rings),
        "structures": len(evidence),
        # THE PARTITION PRODUCT, hashed.  An optimisation of the weld /
        # contact-graph / narrow-phase machinery is semantics-identical
        # exactly when these two do not move: the emitted ring set (what
        # the build consumes) and the per-structure evidence rows (what
        # the partition decided, refusals included).
        "rings_sha256": _digest(rings),
        "rows_sha256": _digest(rows),
        "reader_seconds": reader_seconds,
        "reader_cpu_seconds": reader_cpu_seconds,
        "counted": [
            {"label": counter.label,
             "calls": counter.calls,
             "seconds": counter.seconds,
             "clock": counter.clock_name}
            for counter in counters
        ],
        "osm_building_footprints": n_osm,
        "rows": rows,
        "armed": {
            "DSF_OBJECT_EVIDENCE_MIN_HEIGHT_M":
                DSF_OBJECT_EVIDENCE_MIN_HEIGHT_M,
            "DSF_OBJECT_EVIDENCE_MIN_COVERAGE":
                DSF_OBJECT_EVIDENCE_MIN_COVERAGE,
            "DSF_OBJECT_MAX_STRUCTURE_SPAN_M":
                DSF_OBJECT_MAX_STRUCTURE_SPAN_M,
            "DSF_OBJECT_CONNECTOR_PREFILTER":
                bool(DSF_OBJECT_CONNECTOR_PREFILTER),
            "DSF_OBJECT_CONNECTOR_SPAN_M": DSF_OBJECT_CONNECTOR_SPAN_M,
            "DSF_OBJECT_CONNECTOR_MAX_FILL": DSF_OBJECT_CONNECTOR_MAX_FILL,
        },
        "engine_cache_redirects": redirects,
        "write_guard_armed": guard.enabled,
        "write_guard_blocked": list(guard.blocked),
    }


def coverage_at(row: dict, height_m: float) -> float:
    """The row's tall-member coverage at an arbitrary height threshold —
    ``object_footprints.tall_member_coverage``, THE definition."""
    from auto_patch.object_footprints import tall_member_coverage
    members = [(m["resource"], m["above_grade_extent_m"],
                m["base_area_degrees2"]) for m in row.get("members", ())]
    return tall_member_coverage(
        members, row.get("hull_area_degrees2") or 0.0, height_m)


def render(record: dict, heights: list[float], coverages: list[float],
           spans: list[float], limit: int) -> None:
    rows = record["rows"]
    emitted = [r for r in rows if r["verdict"] == "ring"]
    print(f"DSF   {record['dsf']}")
    print(f"ICAO  {record['icao'] or '(no OSM arm)'}   OSM building "
          f"footprints: {record['osm_building_footprints']}")
    print(f"structures considered {record['structures']}   rings emitted "
          f"{record['rings_emitted']}")
    # Structure-walls footprints (2026-08-30e): one admitted structure
    # contributes one ring PER DISJOINT PART of its own solid geometry,
    # so ``rings emitted`` no longer equals the admitted-structure count.
    _split = [r for r in emitted if (r.get("parts") or 1) > 1]
    _fell_back = [r for r in emitted
                  if r.get("parts_source") == "hull_fallback"]
    if any(r.get("parts_source") for r in emitted):
        print(f"footprint parts: {len(emitted)} admitted structure(s) → "
              f"{sum((r.get('parts') or 1) for r in emitted)} ring(s); "
              f"{len(_split)} split into disjoint parts, "
              f"{len(_fell_back)} fell back to the convex hull")
    print(f"armed {json.dumps(record['armed'])}")
    if record.get("rings_sha256"):
        print(f"rings_sha256 {record['rings_sha256']}")
        print(f"rows_sha256  {record['rows_sha256']}")
    if record.get("reader_seconds") is not None:
        print(f"reader {record['reader_seconds']:.1f} s wall / "
              f"{record.get('reader_cpu_seconds') or 0:.1f} s CPU "
              "(uncached partition replay)")
    if record.get("counted"):
        clock = (record["counted"][0].get("clock") or "perf_counter")
        print(f"COUNTED CALLABLES (inclusive, {clock}):")
        for entry in record["counted"]:
            print(f"  {entry['seconds']:8.1f} s  {entry['calls']:9d} "
                  f"call(s)  {entry['label']}")
    print()

    print("REFUSAL LEDGER (what each existing gate already catches)")
    by_verdict: dict[str, int] = {}
    for row in rows:
        by_verdict[row["verdict"]] = by_verdict.get(row["verdict"], 0) + 1
    for verdict, count in sorted(by_verdict.items(), key=lambda kv: -kv[1]):
        print(f"  {verdict:24} {count:5}")
    print()

    print("MEMBER ABOVE-GRADE EXTENT VOCABULARY — the population the "
          "height threshold is derived from")
    by_resource: dict[str, float] = {}
    for row in emitted:
        for member in row.get("members", ()):
            by_resource[member["resource"]] = max(
                by_resource.get(member["resource"], 0.0),
                member["above_grade_extent_m"])
    ordered = sorted(by_resource.items(), key=lambda kv: kv[1])
    print(f"  {len(ordered)} distinct resources; extents around the "
          "furniture/building boundary:")
    for resource, extent in ordered:
        if 2.5 <= extent <= 8.0:
            print(f"    {extent:8.2f} m  {resource}")
    print()

    print("VERTICAL-EVIDENCE POPULATION over the emitted rings — how many "
          "the tall test alone would VOUCH")
    print("  height | vouched | + coverage floor " + " ".join(
        f"{coverage:.3f}" for coverage in coverages))
    for height in heights:
        tall = [row for row in emitted
                if row["evidence_name_vouched"]
                or (row.get("tallest_member_extent_m") or 0.0) >= height]
        cells = [
            sum(1 for row in tall
                if row["evidence_name_vouched"]
                or coverage_at(row, height) >= coverage)
            for coverage in coverages]
        print(f"  {height:6.1f} | {len(tall):7} |          " + " ".join(
            f"{c:5}" for c in cells))
    print(f"  (of {len(emitted)} emitted rings; name-vouched "
          f"{sum(1 for r in emitted if r['evidence_name_vouched'])}, "
          "and for contrast the hull-fill gate's WIDER path match vouches "
          f"{sum(1 for r in emitted if r['name_vouched'])})")
    print()

    if record["osm_building_footprints"] is not None:
        with_osm = sum(1 for r in emitted if r["osm_evidence"])
        print(f"OSM EVIDENCE over the emitted rings: {with_osm} of "
              f"{len(emitted)} intersect an OSM building footprint")
        print("  JOINT (the gate as ruled: tall OR name OR OSM) at the "
              "armed values:")
        armed_h = record["armed"]["DSF_OBJECT_EVIDENCE_MIN_HEIGHT_M"]
        armed_c = record["armed"]["DSF_OBJECT_EVIDENCE_MIN_COVERAGE"]
        admitted = [r for r in emitted
                    if r["vertical_evidence"] or r["osm_evidence"]]
        print(f"    admitted {len(admitted)} / refused "
              f"{len(emitted) - len(admitted)}  "
              f"(height {armed_h}, coverage {armed_c})")
        refused_area = sorted(
            ((r["hull_area_m2"] or 0.0), r)
            for r in emitted if r not in admitted)
        print("    largest refusals:")
        for area, row in refused_area[::-1][:limit]:
            centroid = row.get("centroid") or (0.0, 0.0)
            print(f"      {area:10.0f} m2  span {row['span_m'] or 0:7.0f} m  "
                  f"{centroid[0]:.7f},{centroid[1]:.7f}  "
                  f"cov {row['evidence_coverage'] or 0:.4f}  "
                  f"{os.path.basename((row['resources'] or ['?'])[0])}")
        print()
        print("    largest SURVIVORS (evidence source per survivor):")
        kept_area = sorted(((r["hull_area_m2"] or 0.0), r) for r in admitted)
        for area, row in kept_area[::-1][:limit]:
            centroid = row.get("centroid") or (0.0, 0.0)
            source = ("name" if row["evidence_name_vouched"]
                      else "tall" if row["vertical_evidence"] else "osm")
            print(f"      {area:10.0f} m2  span {row['span_m'] or 0:7.0f} m  "
                  f"{centroid[0]:.7f},{centroid[1]:.7f}  {source:5} "
                  f"cov {row['evidence_coverage'] or 0:.4f}  "
                  f"{os.path.basename((row['resources'] or ['?'])[0])}")
        print()

    print("STRUCTURE-SPAN GATE (O4_DSF_OBJECT_MAX_STRUCTURE_SPAN_M) — what "
          "each candidate value would catch of the emitted rings, and what "
          "the EVIDENCE GATE already catches of that")
    for span in spans:
        caught = [r for r in emitted if (r["span_m"] or 0.0) > span]
        with_ev = [r for r in caught
                   if r["vertical_evidence"] or r["osm_evidence"]]
        print(f"  > {span:7.0f} m : {len(caught):5} ring(s) caught; "
              f"{len(caught) - len(with_ev)} of them the evidence gate "
              f"ALREADY refuses, so the span gate's own marginal effect is "
              f"{len(with_ev)} ring(s) WITH building evidence — the cost")
        for row in sorted(with_ev, key=lambda r: -(r["span_m"] or 0))[:5]:
            centroid = row.get("centroid") or (0.0, 0.0)
            print(f"        cost: {row['hull_area_m2']:9.0f} m2 span "
                  f"{row['span_m']:6.0f} m tallest member "
                  f"{row.get('tallest_member_extent_m') or 0:6.2f} m at "
                  f"{centroid[0]:.7f},{centroid[1]:.7f}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsf")
    parser.add_argument("--pack-root")
    parser.add_argument("--xplane-root", default=None)
    parser.add_argument("--icao", default=None,
                        help="join the OSM building evidence for this "
                             "airport; omitted → the OSM column is '-' and "
                             "no OSM claim is made")
    parser.add_argument("--height-sweep", default="2.5,4,5,6,8")
    parser.add_argument("--coverage-sweep", default="0.002,0.01,0.05,0.1,0.25")
    parser.add_argument("--span-sweep", default="300,500,750,1000")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--count", action="append", default=[],
                        metavar="MODULE:ATTR",
                        help="also report call count + INCLUSIVE seconds "
                             "for this callable (repeatable) — the counter "
                             "profile_airport_build.py --count installs, "
                             "imported from it; the uncached reader this "
                             "tool drives is the object-partition sink's "
                             "replay")
    parser.add_argument("--json", default=None)
    parser.add_argument("--from-json", default=None,
                        help="render a previous --json dump; reads no pack, "
                             "builds nothing, arms nothing")
    arguments = parser.parse_args()

    if arguments.from_json:
        record = json.loads(Path(arguments.from_json).read_text())
    else:
        if not arguments.dsf or not arguments.pack_root:
            parser.error("--dsf and --pack-root are required "
                         "(or use --from-json)")
        xplane_root = arguments.xplane_root
        if xplane_root is None:
            from conftest import xplane_root as _xplane_root
            xplane_root = _xplane_root()
        record = collect(arguments.dsf, arguments.pack_root, xplane_root,
                         arguments.icao, ARTIFACT_DIR,
                         count_specs=tuple(arguments.count))
        if arguments.json:
            Path(arguments.json).write_text(json.dumps(record, indent=1))

    render(record, _floats(arguments.height_sweep),
           _floats(arguments.coverage_sweep),
           _floats(arguments.span_sweep), arguments.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
