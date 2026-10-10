"""seatspec: compare an arm dir with the base dir — P classes (pads67 pclass logic), platform datums moved, hard_conflict by tier.
usage: cmp_arm.py BASE_DIR ARM_DIR [ICAO]"""
import json, sys, collections
B, A = sys.argv[1], sys.argv[2]; ICAO = sys.argv[3] if len(sys.argv) > 3 else 'HECA'
PR = json.load(open(f'/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pads67/pairs_{ICAO}.json'))['pairs']
pair = {(p['pad_ref'], p['gs_ref']): p for p in PR}
def classes(D):
    E = json.load(open(f'{D}/edge.json' if D != B or not __import__('os').path.exists(f'{D}/edge_base.json') else f'{D}/edge_base.json'))
    G = json.load(open(f'{D}/emit/{ICAO}.graded.json')); side = {f"{f['role']}:{f['ref']}": f.get('side') for f in G['faces']}
    out = collections.Counter(); m = collections.Counter(); rows = []
    for r in E['runs']:
        out[r['cls']] += 1; m[r['cls']] += r['length_m']
        if r['cls'] != 'P': continue
        cs = [c for c in r['cells'] if c['kind'] == 'pavement' and c['dist_m'] <= E['standoff_m'] and abs(c['off_m'] if c['touching'] else c['step_m']) > E['off_m']]
        c = max(cs, key=lambda c: abs(c['off_m'] if c['touching'] else c['step_m'])); ref = c['cell'].split(':', 1)[1]
        pr = pair.get((r['pad'], ref)) or pair.get((r['pad'], ref.split('#')[0])) or pair.get((r['pad'].split('/')[0], ref.split('/')[0]))
        air = side.get(c['cell']) == 'airside'
        k = 'GAP' if ref.startswith('gap:') else ('T28' if pr and abs(pr['step']) > 2.4 else 'ARMED' if pr else ('AIR-TOUCH' if air and c['touching'] else 'AIR-NEAR' if air else 'GS-TOUCH' if c['touching'] else 'GS-NEAR'))
        out['P:' + k] += 1; m['P:' + k] += r['length_m']; rows.append((k, r['pad'], c['cell'], round(c['off_m'] if c['touching'] else c['step_m'], 2), r['site'], r['length_m']))
    return out, m, rows
def axes(D):
    return json.load(open(f'{D}/emit/{ICAO}_auto.patch.osm.axes.json'))
cb, mb, rb = classes(B); ca, ma, ra = classes(A)
print('CLASSES (runs / m)  base -> arm')
for k in sorted(set(cb) | set(ca)): print(f"  {k:12s} {cb[k]:4d} / {round(mb[k]):5d}  ->  {ca[k]:4d} / {round(ma[k]):5d}")
xb, xa = axes(B), axes(A)
pb = {p['ref']: p for p in xb.get('platforms', [])}; pa = {p['ref']: p for p in xa.get('platforms', [])}
mv = [(r, pb[r].get('datum'), pa[r].get('datum')) for r in pb if r in pa and pb[r].get('datum') is not None and pa[r].get('datum') is not None and abs(pb[r]['datum'] - pa[r]['datum']) > 0.02]
print(f"PLATFORM DATUMS moved > 0.02 m: {len(mv)} of {len(pb)}", sorted(mv, key=lambda t: -abs(t[1] - t[2]))[:12])
print('  misfit/widened arm:', [(r, pa[r].get('misfit_m'), (pa[r].get('weld_widened') or {}).get('delta_pct'), pa[r].get('reach_unreached')) for r in pa if (pa[r].get('misfit_m') or 0) > 0.0 or pa[r].get('weld_widened')])
hb = collections.Counter(r.get('tier') for r in xb.get('hard_conflict', [])); ha = collections.Counter(r.get('tier') for r in xa.get('hard_conflict', []))
print('HARD_CONFLICT by tier base -> arm:', dict(hb), '->', dict(ha))
print('ARM P rows (worst 10):'); [print('  ', r) for r in sorted(ra, key=lambda r: -abs(r[3]))[:10]]
print('AIR rows arm:'); [print('  ', r) for r in sorted(ra, key=lambda r: -abs(r[3])) if r[0].startswith('AIR')]
print('AIR rows base:', len([r for r in rb if r[0].startswith('AIR')]))
