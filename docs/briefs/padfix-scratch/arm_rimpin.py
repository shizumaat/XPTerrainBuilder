"""arm_rimpin.py <v2_solve_replay args> — INTERVENTION ARM (scratch, never a build): every rim / ramp-top vertex of an
OBJECT-FRAMED door well that the governed ground shares is PINNED at the well's own ground datum (Tunnel.top_ground_z,
the level its framed plane was derived against) — today such a vertex carries the pavement's solved value.  The one
variable; everything else is the tree."""
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("PF_ROOT", "/Users/noah/XPTerrainBuilder/.claude/worktrees/padfix/Ortho4XP"))


def install():
    import auto_patch_v2.constraints as C
    from auto_patch_v2.constraints import structures as ST
    from auto_patch_v2.constraints.precedence import view
    from auto_patch_v2.model.constraints import Pin, Source
    orig = ST.structures

    def structures(planar, law, airport):
        rows = list(orig(planar, law, airport))
        vw = view(planar, law)
        sroles = ("tunnel_ramp", ST.DOOR_RAMP_REF, *ST.WALL_CORRIDOR_ROLES, "retaining_wall")
        walls = ST.wall_faces_of(planar, planar.structures)
        ramps = ST.ramp_faces_of(planar, planar.structures)
        pinned = {r.v for r in rows if isinstance(r, Pin)}
        n = 0
        for tn in planar.structures:
            if not (tn.pinched and tn.source == "door" and tn.top_ground_z is not None):
                continue
            vs = {v for f in (*walls.get(tn.id, ()), *ramps.get(tn.id, ())) for v in planar.ring_vertices(f.ring)}
            src = Source(ST.GEN, "ARM cutout.door: the shared rim at the well's ground datum", (tn.id,))
            for v in sorted(vs - pinned):
                if any(planar.faces[f].role not in sroles and vw.caps[f] is not None for f in vw.vertex_faces[v]):
                    rows.append(Pin(v, float(tn.top_ground_z), src)); n += 1
        print(f"  ARM rimpin: {n} shared rim / ramp-top vertices pinned at their well's ground datum", flush=True)
        return rows

    C.GENERATORS = tuple((k, structures if k == "structures" else g) for k, g in C.GENERATORS)


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
