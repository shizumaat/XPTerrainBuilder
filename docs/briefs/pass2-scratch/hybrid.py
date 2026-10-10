"""pass2 scratch: HYBRID patch = patch G's geometry + sidecar with patch Z's elevations (by 11-dp lat/lon key).
usage: hybrid.py G.osm Z.osm OUT.osm  — prints the node-set comparison; copies G's .axes.json beside OUT."""
import re
import shutil
import sys

if __name__ == '__main__':
    g, z, out = sys.argv[1:4]
    node = re.compile(r"<node id='(-?\d+)'[^>]*lat='([-\d.]+)' lon='([-\d.]+)'")
    alt = re.compile(r"<tag k='alt_abs' v='([-\d.]+)' />")

    def read(p):
        zs, cur = {}, None
        ways = 0
        for ln in open(p):
            m = node.search(ln)
            if m:
                cur = (m.group(2), m.group(3))
                continue
            if cur is not None:
                a = alt.search(ln)
                if a:
                    zs[cur] = a.group(1)
                    cur = None
            if '<way ' in ln:
                ways += 1
        return zs, ways
    zg, wg = read(g)
    zz, wz = read(z)
    only_g, only_z = set(zg) - set(zz), set(zz) - set(zg)
    moved = sum(1 for k in zg if k in zz and abs(float(zg[k]) - float(zz[k])) > 0.02)
    print(f'nodes G {len(zg)} Z {len(zz)} only-G {len(only_g)} only-Z {len(only_z)}; ways {wg} / {wz}; '
          f'common nodes differing > 0.02 m: {moved}')
    cur = None
    n = 0
    with open(out, 'w') as fo:
        for ln in open(g):
            m = node.search(ln)
            if m:
                cur = (m.group(2), m.group(3))
            elif cur is not None and alt.search(ln):
                if cur in zz and zz[cur] != zg[cur]:
                    ln = alt.sub(f"<tag k='alt_abs' v='{zz[cur]}' />", ln)
                    n += 1
                cur = None
            fo.write(ln)
    shutil.copy(g + '.axes.json', out + '.axes.json')
    print(f'wrote {out}: {n} elevations replaced')
