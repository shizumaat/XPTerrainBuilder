"""The v2 auto-patch pipeline as STUB modules — the one stub both driver
suites build through (promoted from ``test_auto_patch_engine_dispatch`` on
its second use, 2026-09-15: ``test_auto_patch_freshness`` needs the same
stub since v1 was retired, RULINGS 2026-09-15c).

``stub_v2_pipeline(monkeypatch)`` installs ``auto_patch_v2.{airport.load,
pipeline.build, law}`` stand-ins in ``sys.modules`` so ``auto_patch.
engine_v2.build_write_verify_one_v2`` runs its REAL body — the stamp
header (``_stamp_header``), the placement ``os.replace`` into ``Patches/``,
the provenance line, the verify log — over a ``build`` that writes what
the real adapter writes into ``out_dir`` (patch + sidecar, the driver's
header attributes rendered on the ``<osm>`` root) and returns the fields
the adapter reads.  The real pipeline is the harness's closing test.
"""
import json
import sys
import types
from pathlib import Path


def stub_v2_pipeline(monkeypatch, *, status="optimal", pieces_tiles=None, raise_exc=None):
    """The v2 pipeline as stub modules.  ``build`` writes what the real
    adapter writes into ``out_dir`` (and, for ``pieces_tiles``, one piece
    per tile at the adapter's own ``<block>/<tile>/`` path) and returns
    the fields ``build_write_verify_one_v2`` reads."""
    class _Status:
        def __init__(self, v): self.value = v

    class _Sol:
        def __init__(self, v):
            self.status = _Status(v); self.message = f"stub {v}"

    class _Paths:
        def __init__(self, patch, side, ways):
            self.patch, self.sidecar, self.ways, self.nodes = patch, side, ways, ways * 3

    class _Res:
        rebake_plan = None   # the M6a pipeline result field (5890bfa0)

    class _Config:
        def __init__(self, header_extra=None): self.header_extra = header_extra

    class _Inputs:
        def __init__(self, **kw): self.kw = kw

    class _Law:
        ruleset_key = "icao"

        @classmethod
        def for_airport(cls, icao): return cls()

    calls = {}

    def build(icao, inputs, out_dir, config=None, law=None, out=print):
        calls["inputs"] = inputs.kw
        calls["header_extra"] = dict(config.header_extra or {})
        if raise_exc is not None:
            raise raise_exc
        for stage in ("load", "planar", "constraints", "solve"):
            out(f"[{icao}] {stage} 0.10 s  stub")
        d = Path(out_dir); d.mkdir(parents=True, exist_ok=True)

        def _write(where, ways, tag):
            where.mkdir(parents=True, exist_ok=True)
            patch = where / f"{icao}_auto.patch.osm"
            hdr = " ".join(f"{k}='{v}'" for k, v in calls["header_extra"].items())
            patch.write_text(f"<?xml version='1.0'?>\n<osm generator='auto_patch_v2' "
                             f"o4_stub='{tag}' {hdr}>\n</osm>\n")
            side = Path(str(patch) + ".axes.json")
            side.write_text(json.dumps({"ruleset": "icao", "axes": [], "tag": tag}))
            return _Paths(patch, side, ways)

        r = _Res()
        r.solution = _Sol(status)
        r.paths = _write(d, 5, "whole") if status == "optimal" else None
        r.pieces = None
        if status == "optimal" and pieces_tiles:
            r.pieces = {}
            for n, (la, lo) in enumerate(pieces_tiles):
                block = f"{(la // 10) * 10:+03d}{(lo // 10) * 10:+04d}"
                r.pieces[(la, lo)] = _write(d / block / f"{la:+03d}{lo:+04d}",
                                            10 + n, f"piece{la:+03d}{lo:+04d}")
        r.report = {
            "load": {"dem_provenance": {"frame": "production",
                                        "tile:N30E031": "host-seeded: grid 2x2, "
                                        "insets=OTHH:lidar"}},
            "solve": {"status": status, "message": f"stub {status}",
                      "iis": [{"row": "z[1]-z[2] <= 0.01", "generator": "taxi_long",
                               "ruling": "08-21b", "inputs": ["e1"]}]},
            "verify": {"by_family": {"strip_seam_tear": 1, "transverse": 0},
                       "rows": {"strip_seam_tear": [{"family": "strip_seam_tear",
                                                     "site": [30.1, 31.2]}]}},
        }
        r.wall = {"total": 0.4}
        r.lp_size = {"rows": 1}
        (d / f"{icao}.report.json").write_text(json.dumps(r.report))
        return r

    mods = {
        "auto_patch_v2": types.ModuleType("auto_patch_v2"),
        "auto_patch_v2.airport": types.ModuleType("auto_patch_v2.airport"),
        "auto_patch_v2.airport.load": types.ModuleType("auto_patch_v2.airport.load"),
        "auto_patch_v2.pipeline": types.ModuleType("auto_patch_v2.pipeline"),
        "auto_patch_v2.pipeline.build": types.ModuleType("auto_patch_v2.pipeline.build"),
        "auto_patch_v2.law": types.ModuleType("auto_patch_v2.law"),
    }
    mods["auto_patch_v2.airport.load"].Inputs = _Inputs
    mods["auto_patch_v2.pipeline.build"].build = build
    mods["auto_patch_v2.pipeline.build"].Config = _Config
    mods["auto_patch_v2.law"].Law = _Law
    mods["auto_patch_v2.law"].law_tables_digest = lambda law_dir=None: {
        "dir": "stub", "files": ["emit.toml"], "sha256": "feedfacecafebeef" * 4}
    for name, m in mods.items():
        monkeypatch.setitem(sys.modules, name, m)
    return calls
