"""surfreview ARM RIMFOLLOW (spec §60 review, B1): a gap part beside a
below-grade structure follows its RIM, never its floor / ramp / wall void.

Two interventions on the last stage's generator (`constraints/gap_follow`):
 (1) the below-grade family — `emit/graded.FLOOR_ROLES` (tunnel_trench,
     tunnel_ramp, door_ramp, wall_corridor_ramp, garage_ramp) and the wall
     void `planar/basins.WALL_ROLE` (retaining_wall) — binds NO follow row;
 (2) an unknown vertex lying ON a basin's rim (the wall void face's exterior
     ring) is PINNED to the rim's level interpolated between its fixed rim
     neighbours along the ring (the rim is a declared step; a part flush on
     it meets it at its level, as a part flush on an apron does).
usage: arm_rimfollow.py <v2_solve_replay args...>"""
import dataclasses as _dc
import sys

sys.path[:0] = ["src", ".", "tools"]

if __name__ == "__main__":
    from auto_patch_v2.constraints import gap_follow as gf
    from auto_patch_v2.emit.graded import FLOOR_ROLES
    from auto_patch_v2.model.constraints import Linear, Source
    from auto_patch_v2.pipeline import late_stage as ls
    from auto_patch_v2.planar.basins import WALL_ROLE

    FAMILY = frozenset(FLOOR_ROLES) | {WALL_ROLE}
    _orig = gf.gap_follow_rows

    def _ring_vertices(planar, face):
        """The exterior ring of ``face`` as an ordered vertex cycle."""
        E = planar.edges
        ring = list(face.ring)
        if not ring:
            return []
        out = []
        e0 = E[ring[0]]
        e1 = E[ring[1]] if len(ring) > 1 else e0
        start = e0.a if e0.b in (e1.a, e1.b) else e0.b
        cur = start
        for eid in ring:
            e = E[eid]
            out.append(cur)
            cur = e.b if e.a == cur else e.a
        return out

    def _rim_pins(planar, fixed):
        V = planar.vertices
        rows, n = [], 0
        for f in planar.faces.values():
            if f.role != WALL_ROLE or not str(f.ref).startswith("basin_wall"):
                continue
            cyc = _ring_vertices(planar, f)
            m = len(cyc)
            if m < 3:
                continue
            fixed_idx = [i for i, v in enumerate(cyc) if v in fixed]
            if len(fixed_idx) < 2:
                continue
            for i, v in enumerate(cyc):
                if v in fixed:
                    continue
                # nearest fixed rim vertex before and after along the cycle
                prev = max((j for j in fixed_idx if j < i), default=max(fixed_idx))
                nxt = min((j for j in fixed_idx if j > i), default=min(fixed_idx))
                def _d(p, q):
                    (x0, y0), (x1, y1) = V[p].xy, V[q].xy
                    return ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
                # walk distances along the cycle
                def _walk(a, b):
                    d, k = 0.0, a
                    while k != b:
                        k2 = (k + 1) % m
                        d += _d(cyc[k], cyc[k2]); k = k2
                    return d
                da, db = _walk(prev, i), _walk(i, nxt)
                za, zb = float(fixed[cyc[prev]]), float(fixed[cyc[nxt]])
                t = da / (da + db) if (da + db) > 0 else 0.0
                z = (1.0 - t) * za + t * zb
                rows.append(Linear(((v, 1.0),), z, z,
                                   Source("gap_follow", "ARM: a part vertex on a structure rim takes the rim's level", (f"{f.role}:{f.ref}",))))
                n += 1
        return rows, n

    def _arm(planar, law, fixed, part_stations=None):
        view = _dc.replace(planar, faces={k: f for k, f in planar.faces.items()
                                          if f.role not in FAMILY})
        dropped = len(planar.faces) - len(view.faces)
        rows, rep = _orig(view, law, fixed, part_stations)
        pins, n = _rim_pins(planar, fixed)
        rep["arm_rimfollow"] = {"faces_excluded": dropped, "rim_pins": n}
        print(f"[arm_rimfollow] below-grade faces excluded as follow neighbours: {dropped}; "
              f"rim pins: {n}; follow rows {rep['rows']}")
        return [*rows, *pins], rep

    gf.gap_follow_rows = _arm
    ls.gap_follow_rows = _arm
    import v2_solve_replay as _r
    raise SystemExit(_r.main())
