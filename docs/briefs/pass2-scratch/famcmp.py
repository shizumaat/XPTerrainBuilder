"""pass2 scratch: census family table across arms. usage: famcmp.py NAME:rows.json ... """
import json
import sys
from collections import Counter

if __name__ == '__main__':
    arms = [a.split(':', 1) for a in sys.argv[1:]]
    cs, adj, crit = {}, {}, {}
    for n, p in arms:
        rows = json.load(open(p))['rows']
        cs[n] = Counter(r['family'] for r in rows if r['side'] == 'airside')
        j = json.load(open(p.replace('.rows.json', '.json')))
        adj[n] = j['adjudicated_airside_for_acceptance']
        ck = j.get('cockpit') or {}
        crit[n] = {k: (v if not isinstance(v, (list, dict)) else None) for k, v in ck.items()}
        rr = ck.get('rows')
        if isinstance(rr, dict):
            crit[n] = {k: (len(v) if isinstance(v, list) else v) for k, v in rr.items()}
        elif isinstance(rr, list):
            c = Counter((r.get('class') or r.get('severity') or r.get('kind'), r.get('family')) for r in rr)
            crit[n] = dict(Counter(k[0] for k in c.elements()))
            crit[n]['by_family'] = {f'{k[0]}:{k[1]}': v for k, v in c.items()}
    names = [n for n, _ in arms]
    print('adjudicated airside', {n: adj[n] for n in names})
    for f in sorted(set().union(*cs.values())):
        v = [cs[n][f] for n in names]
        if len(set(v)) > 1:
            print(f'  {f}: ' + ' / '.join(map(str, v)))
    for n in names:
        print('CRIT', n, {k: v for k, v in crit[n].items() if k != 'by_family'})
    bf = [crit[n].get('by_family', {}) for n in names]
    for k in sorted(set().union(*bf)):
        v = [b.get(k, 0) for b in bf]
        if len(set(v)) > 1:
            print(f'  {k}: ' + ' / '.join(map(str, v)))
