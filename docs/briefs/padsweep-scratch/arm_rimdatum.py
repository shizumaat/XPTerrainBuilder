"""arm_rimdatum.py <v2_solve_replay args> — INTERVENTION ARM (scratch, never a build): a HELD pad with a welded rim
and NO vertex of its own takes one of its welded rim vertices as its datum column (today: no datum column, not
held — model/platform.datum_vertices), so the hold rows put its whole rim on one level.  Everything else is the tree."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path("/Users/noah/XPTerrainBuilder/.claude/worktrees/padsweep/Ortho4XP")


def install():
    import auto_patch_v2.model.platform as MP
    import auto_patch_v2.constraints.platform as CP
    orig = MP.datum_vertices
    seen = {}

    def datum_vertices(planar, law, air=None):
        out = dict(orig(planar, law, air))
        if not MP.HELD:
            return out
        if air is None:
            air = MP.stage_air_vertices(planar, law)
        air = set(air)
        own = {}
        for f in planar.faces.values():
            r = str(f.ref)
            if r in MP.HELD and r not in out:
                vs = own.setdefault(r, set())
                for ring in (f.ring, *f.holes):
                    vs.update(planar.ring_vertices(ring))
        struct = MP.structure_vertices(planar, law)
        for ref in sorted(own):
            vs = own[ref]
            weld = vs & air
            if weld and not (vs - weld - struct) and len(weld) == len(vs):
                out[ref] = min(weld)
        new = sorted(r for r in own if r in out)
        if seen.get("n") != len(new):
            seen["n"] = len(new)
            print(f"  ARM rimdatum: {len(new)} pad(s) with no own vertex take a rim datum: {new[:40]}", flush=True)
        return out

    MP.datum_vertices = datum_vertices
    CP.datum_vertices = datum_vertices
    orig_hs = CP.hold_sets

    def hold_sets(planar, law):
        return [(p, dv, [o for o in w if o != dv], n, r) for p, dv, w, n, r in orig_hs(planar, law)]
    CP.hold_sets = hold_sets


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location("v2_solve_replay", ROOT / "tools" / "v2_solve_replay.py")
    rep = importlib.util.module_from_spec(spec)
    sys.modules["v2_solve_replay"] = rep
    spec.loader.exec_module(rep)
    install()
    sys.argv = ["v2_solve_replay.py", *sys.argv[1:]]
    sys.exit(rep.main())
