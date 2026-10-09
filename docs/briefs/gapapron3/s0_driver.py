"""gapapron2 S0 driver (arm_driver.py + the __main__ guard + two knobs).
usage: s0_driver.py base|arm EVIDENCE.json EXCLUDE(comma refs or -) PROTO(0|1) <v2_solve_replay args...>
 EXCLUDE: apron-classed pieces taken OUT of the class (they stay late pieces / are dropped in base)
 PROTO=1: THE CANDIDATE RULE — pass 1a (the runway's unpulled profile) is solved without the rows that
          touch a gap-apron part's own vertices; pass 1b carries them, under the runway Bands of pass 1a
"""
import dataclasses as _dc
import json
import sys

sys.path[:0] = ["src", ".", "tools"]

if __name__ == "__main__":
    mode, ev_path, excl, proto = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1"
    EX = set() if excl == "-" else set(excl.split(","))
    APRON = {r["ref"] for r in json.load(open(ev_path))
             if r["class_08c_with_s37_share"].startswith("APRON")} - EX
    print(f"[s0_driver] mode {mode} proto {proto}: {len(APRON)} pieces -> stage-1 apron: {sorted(APRON)}")

    import auto_patch_v2.classify as _pkg
    from auto_patch_v2.law.tables import role_side
    from auto_patch_v2.model.planar import is_gap_ref

    _orig = _pkg.classify

    def _classify(airport, law, rules=None, cache=None):
        cl = _orig(airport, law, rules, cache=cache)
        cells, k, dropped = [], 0, 0
        for c in cl.cells:
            if c.ref in APRON:
                cells.append(_dc.replace(
                    c, role="apron", side=role_side(law, "apron"), kind="gap_apron",
                    ref=f"gapapron:{k}",
                    evidence={**dict(c.evidence), "gap_apron": 1.0, "gap_ref": c.ref}))
                k += 1
            elif mode == "base" and is_gap_ref(c.ref):
                dropped += 1
            else:
                cells.append(c)
        cells = [_dc.replace(c, id=i) for i, c in enumerate(cells)]
        print(f"[s0_driver] classify: {k} re-spelled as apron, {dropped} late pieces dropped, {len(cells)} cells")
        return _dc.replace(cl, cells=tuple(cells))

    _pkg.classify = _classify

    if proto:
        from auto_patch_v2.constraints import no_step as _ns
        from auto_patch_v2.model.constraints import ConstraintSet
        from auto_patch_v2.solve.pin_yield import row_vertices
        _strip, _derive = _ns.HoldPass.strip, _ns.HoldPass.derive

        def _own(self):
            own, other = set(), set()
            pm = self.planar
            for f in pm.faces.values():
                tgt = own if str(f.ref).startswith("gapapron:") else other
                for ring in (f.ring, *f.holes):
                    tgt.update(pm.ring_vertices(ring))
            return own - other

        def strip(self, cs):
            base = _strip(self, cs)
            own = _own(self)
            src = base if base is not None else cs
            keep, gone = [], []
            for r in src.rows():
                (gone if any(int(v) in own for v in row_vertices(r)) else keep).append(r)
            self._gap_rows = gone
            print(f"[s0_driver] PROTO pass 1a: {len(own)} gap-apron own vertices, {len(gone)} rows withheld to pass 1b")
            if base is None and not gone:
                return None
            return ConstraintSet.from_rows(keep)

        def derive(self, cs1a, z1a, rw_cols):
            out = _derive(self, cs1a, z1a, rw_cols)
            gone = getattr(self, "_gap_rows", [])
            if out is None:
                print("[s0_driver] PROTO: no hold interval — pass 1b not derived")
                return None
            return ConstraintSet.from_rows([*out.rows(), *gone])

        _ns.HoldPass.strip, _ns.HoldPass.derive = strip, derive

    import v2_solve_replay as _r
    sys.argv = [sys.argv[0], *sys.argv[5:]]
    raise SystemExit(_r.main())
