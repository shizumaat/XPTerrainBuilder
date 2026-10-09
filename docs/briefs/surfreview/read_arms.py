"""surfreview reader: two patches (CONTROL, ARM) — every gap group's span and
node identity, the basin rim ways' nodes and levels, and which non-gap way
groups differ (airside_value_delta.read_refs is the reader).
usage: read_arms.py CONTROL.osm ARM.osm [MAIN.osm]"""
import sys
sys.path[:0] = ["tools", "src", "."]
from airside_value_delta import read_refs  # noqa: E402


def groups(path):
    return read_refs(path)


def main(ctl, arm, main=None):
    A, B = groups(ctl), groups(arm)
    M = groups(main) if main else None
    print(f"groups: control {len(A)}  arm {len(B)}")
    changed, same = [], 0
    for key in sorted(set(A) | set(B)):
        a, b = A.get(key), B.get(key)
        if a == b:
            same += 1
            continue
        if a is None or b is None:
            changed.append((key, "only in " + ("arm" if a is None else "control"), None, None))
            continue
        both = set(a) & set(b)
        moved = sorted((abs(a[k] - b[k]), k) for k in both if abs(a[k] - b[k]) > 0.005)
        changed.append((key, f"nodes {len(a)}->{len(b)}", len(moved),
                        (round(moved[-1][0], 3), moved[-1][1]) if moved else None))
    print(f"identical groups {same}; differing {len(changed)}")
    gap_ch = [c for c in changed if str(c[0][1]).startswith("gap")]
    other = [c for c in changed if not str(c[0][1]).startswith("gap")]
    print(f"  gap groups differing: {len(gap_ch)}; non-gap: {len(other)}")
    for c in changed:
        print("   ", c)
    # the three basin parts and the rims
    def span(G, ref):
        for (role, r), nodes in G.items():
            if r == ref:
                zs = list(nodes.values())
                return (role, len(zs), round(min(zs), 2), round(max(zs), 2))
        return None
    for ref in ("gap:1/s3", "gap:2/s1", "gap:1/s4", "gap:1/s1", "gap:2/s7", "gap:2/s7#1"):
        print(f"  {ref}: control {span(A, ref)}  arm {span(B, ref)}")
    for ref in ("basin_wall:0", "basin_wall:3", "basin_wall:4", "basin_wall:5", "basin_wall:6"):
        for name, G in (("control", A), ("arm", B), ("main", M)):
            if G is None:
                continue
            for (role, r), nodes in G.items():
                if r == ref and role in (None, "", "structure_rim") or (r == ref and role != "retaining_wall"):
                    zs = sorted(nodes.values())
                    low = [z for z in zs if z < 3.5]
                    print(f"  {ref} [{role}] {name}: nodes {len(zs)} min {zs[0]:.2f} max {zs[-1]:.2f} below 3.5: {len(low)} {low[:6]}")


if __name__ == "__main__":
    main(*sys.argv[1:])
