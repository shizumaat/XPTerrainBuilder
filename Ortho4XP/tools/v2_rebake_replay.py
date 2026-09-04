#!/usr/bin/env python
"""Offline replay of the auto-patch-v2 RE-SEAT (RULINGS 2026-09-04i 04f-1)
— the post-mesh half without a tile build, and the pack's current bake
state without a build at all.

    venv/bin/python tools/v2_rebake_replay.py seat PLAN.json MESH [--filter TOKEN]
    venv/bin/python tools/v2_rebake_replay.py disk PACK_ROOT [--filter TOKEN]

``seat`` reads a tile build's ``o4_v2_rebake_<ICAO>.json`` plan (or the
pipeline's ``<ICAO>.rebake.json``) and a built ``Data+XX+YYY.mesh``, seats
every unit exactly as ``auto_patch.engine_v2.rebake_after_mesh`` would
(``auto_patch_v2.emit.rebake.seat`` over v1's ``MeshElevationSampler``),
prints the counts, the largest seats and every unit matching ``--filter``
(member seats, witnesses, water, outliers), and writes
``PLAN.seat.json`` beside the plan.  It NEVER writes a pack.

``disk`` walks a scenery pack for ``<obj>.anchor_bak`` backups and prints,
per resource matching ``--filter``, the live-minus-authored vertex ``y``
delta on disk and v1's provenance record (decision kind, anchor ground,
seat datum, delta) — the "before" reading of any re-seat.  Read-only.

Twins: ``tests/auto_patch_v2/test_m6a_rebake.py`` (the seat law),
``tests/test_engine_v2_rebake.py`` (the hook the ``seat`` half mirrors).
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))


def cmd_seat(args: argparse.Namespace) -> int:
    from auto_patch.mesh_sampler import MeshElevationSampler, OutsideMeshError
    from auto_patch_v2.emit import rebake as R
    from auto_patch_v2.law import Law
    with open(args.plan) as fh:
        plan = R.RebakePlan.from_json(fh.read())
    law = Law.for_airport(plan.icao)
    print(f"{plan.icao} plan: {dict(plan.counts)} skipped {len(plan.skipped)}")
    print("  skip reasons:", collections.Counter(
        r.split(" (")[0].split(":")[0] for _, r in plan.skipped).most_common(6))
    sampler = MeshElevationSampler(args.mesh, plan.bounds())

    def sample(lat: float, lon: float):
        try:
            m = sampler.sample_at(lat, lon)
        except OutsideMeshError:
            return None
        return (float(m.elevation_metres), bool(m.is_water))

    res = R.seat(plan, sample, law)
    print("seat:", res.counts())
    baked = sorted((u for u in res.units if u.bakes), key=lambda u: -abs(u.delta_m))
    print("largest seats:")
    for u in baked[:args.top]:
        founding = [m for m in u.members if not m.note.startswith("inherits")]
        print(f"  {u.unit_id} n={len(u.resources)} anchor_ground={u.anchor_ground_m:.2f} "
              f"delta={u.delta_m:+.3f} founding="
              + ", ".join(f"{os.path.basename(m.resource)[:32]} {m.delta_m if m.delta_m is None else round(m.delta_m, 2)} w={m.witnesses} water={m.water}"
                          for m in founding[:3]) + (f"  {u.findings[0]}" if u.findings else ""))
    if args.filter:
        for u in res.units:
            if any(args.filter in r for r in u.resources):
                print(f"{u.unit_id} n={len(u.resources)} datum={u.datum} anchor_ground={u.anchor_ground_m} "
                      f"delta={u.delta_m} held={u.held} skip={u.skip_reason} findings={u.findings}")
                for m in u.members:
                    print(f"     {os.path.basename(m.resource):48s} {m.datum:8s} delta={m.delta_m if m.delta_m is None else round(m.delta_m, 3)} "
                          f"w={m.witnesses} water={m.water} off={m.off_mesh} out={m.outliers} {m.note}")
    ds = [u.delta_m for u in baked]
    if ds:
        print(f"baked deltas: median {statistics.median(ds):+.3f} max |{max(ds, key=abs):+.3f}| over {len(ds)} units")
    out = os.path.splitext(args.plan)[0] + ".seat.json"
    with open(out, "w") as fh:
        json.dump(res.to_dict(), fh, indent=1, default=str)
    print("->", out)
    return 0


def cmd_disk(args: argparse.Namespace) -> int:
    from auto_patch_v2.airport import obj8
    root = args.pack_root
    prov: dict = {}
    pp = os.path.join(root, ".o4_reanchor_provenance.json")
    if os.path.isfile(pp):
        with open(pp) as fh:
            prov = json.load(fh).get("objects", {})
    n_bak = baked = 0
    rows = []
    for d, _, fs in os.walk(root):
        for f in fs:
            if not f.endswith(".anchor_bak"):
                continue
            n_bak += 1
            bak = os.path.join(d, f)
            live = bak[:-len(".anchor_bak")]
            rel = os.path.relpath(live, root)
            if not os.path.isfile(live):
                continue
            try:
                ga, gl = obj8.parse_obj8(bak), obj8.parse_obj8(live)
            except (OSError, ValueError):
                continue
            if ga.vertices.shape != gl.vertices.shape or ga.vertices.shape[0] == 0:
                continue
            dy = gl.vertices[:, 1] - ga.vertices[:, 1]
            if abs(dy).max() > 1e-6:
                baked += 1
            if args.filter and args.filter not in rel:
                continue
            e = prov.get(rel, {})
            rows.append((rel, float(dy.min()), float(dy.max()), e.get("decision_kind"),
                         e.get("anchor_ground_m"), e.get("seat_datum_m"), e.get("delta_m")))
    print(f"{root}: anchor_bak files {n_bak}, live != backup {baked}, provenance entries {len(prov)}")
    for rel, lo, hi, kind, ag, seat, delta in sorted(rows):
        print(f"  {rel:62s} dy[{lo:+8.4f},{hi:+8.4f}] {kind} anchor_ground={ag} seat={seat} delta={delta}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seat", help="seat a plan against a built mesh (no write)")
    s.add_argument("plan")
    s.add_argument("mesh")
    s.add_argument("--filter", default="", help="print every unit whose resources contain this")
    s.add_argument("--top", type=int, default=12)
    s.set_defaults(fn=cmd_seat)
    d = sub.add_parser("disk", help="a pack's current bake state (read-only)")
    d.add_argument("pack_root")
    d.add_argument("--filter", default="")
    d.set_defaults(fn=cmd_disk)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
