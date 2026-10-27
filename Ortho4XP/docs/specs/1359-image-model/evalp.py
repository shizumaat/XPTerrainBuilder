"""Pavement outline + tunnel portal + named-site probes on held-out airports."""
import json, os, sys
import numpy as np
from scipy import ndimage
from PIL import Image
_argv = sys.argv; sys.argv = sys.argv[:1]
import evalm as E
sys.argv = _argv
HERE = E.HERE; TD = E.TD
SITES = {  # issue sites: (lat, lon, what the owner/sim says is there)
    'KDIJ': [(43.73959, -111.10158, 'CIFP RW04 threshold (#1358)'), (43.7360349, -111.1070718, 'apt.dat rwy 04 end, 594 m SW of CIFP (#1358)')],
    'NZWN': [(-41.328982258, 174.813874159, 'phantom tunnel ramp, owner: no tunnel (#1337)'), (-41.329986226, 174.813713002, 'phantom tunnel ramp, owner: no tunnel (#1337)')],
    'LGAV': [(37.943947839, 23.951564905, 'taxiway sunk into tunnel_ramp pit; owner: flat (#1331)')],
}
R = 12  # px = 24 m probe radius
def disk(a, r, c, R=R):
    H, W = a.shape; rr, cc = np.ogrid[-R:R + 1, -R:R + 1]; m = rr ** 2 + cc ** 2 <= R * R
    r0, c0 = max(r - R, 0), max(c - R, 0); sub = a[r0:r + R + 1, c0:c + R + 1]
    return sub[m[r0 - (r - R):m.shape[0] - ((r + R + 1) - min(r + R + 1, H)), c0 - (c - R):m.shape[1] - ((c + R + 1) - min(c + R + 1, W))]]
if __name__ == '__main__':
    cfg = json.load(open(sys.argv[1], encoding='utf-8')); out = {}
    rng = np.random.default_rng(1)
    for icao in cfg['airports']:
        d = dict(np.load(os.path.join(TD, icao + '.npz'))); o = np.load(os.path.join(HERE, 'osm', icao + '.npz'))
        H, W = d['valid'].shape; res = {}
        region = d['valid'].copy(); m = np.zeros_like(region); m[int(.2 * H):int(.8 * H), int(.2 * W):int(.8 * W)] = 1; region &= m.astype(bool)
        pv = E.predict(os.path.join(HERE, cfg['pave']), d)
        gtp = o['pave'].astype(bool)
        res['pavement'], pm = E.metrics(pv, gtp, region)
        E.overlay(d['rgb'], gtp, pm, os.path.join(HERE, 'out', f'{icao}_pave.png'))
        st = E.predict(os.path.join(HERE, 'rgb.pt'), d)
        lid = d['slope'] if cfg.get('lidar', True) and icao != 'LGAV' else None
        # portals: OSM tunnel endpoints in the valid area vs random valid control points
        P = [(int(round(y)), int(round(x))) for x, y in o['portals']] if len(o['portals']) else []
        P = [(r, c) for r, c in P if R <= r < H - R and R <= c < W - R and d['valid'][r, c]]
        if P:
            ctrl = []
            while len(ctrl) < 200:
                r, c = rng.integers(R, H - R), rng.integers(R, W - R)
                if d['valid'][r, c]: ctrl.append((r, c))
            ps = [disk(st, r, c).max() for r, c in P]; cs = [disk(st, r, c).max() for r, c in ctrl]
            auc = np.mean([[p > q for q in cs] for p in ps])
            res['portals'] = dict(n=len(P), model_peak_mean=round(float(np.mean(ps)), 3), ctrl_peak_mean=round(float(np.mean(cs)), 3), model_auc=round(float(auc), 3))
            if lid is not None:
                pl = [disk(lid, r, c).max() for r, c in P]; cl = [disk(lid, r, c).max() for r, c in ctrl]
                res['portals']['lidar_max_slope_mean'] = round(float(np.mean(pl)), 1)
                res['portals']['lidar_auc'] = round(float(np.mean([[p > q for q in cl] for p in pl])), 3)
                res['portals']['lidar_says_cut_frac'] = round(float(np.mean([v > 25 for v in pl])), 2)
                res['portals']['model_says_cut_frac'] = round(float(np.mean([v > .5 for v in ps])), 2)
        sites = []
        for lat, lon, what in SITES.get(icao, []):
            r, c = E.latlon_rc(d, lat, lon)
            s = dict(site=what, model_steep_peak=round(float(disk(st, r, c).max()), 2), model_pave=round(float(disk(pv, r, c, 3).mean()), 2))
            if lid is not None: s['lidar_max_slope_deg'] = round(float(disk(lid, r, c).max()), 1)
            sites.append(s)
            box = (max(r - 250, 0), r + 250, max(c - 250, 0), c + 250)
            E.overlay(d['rgb'], (lid > 10) if lid is not None else np.zeros((H, W), bool), E.clean(st >= .5), os.path.join(HERE, 'out', f'{icao}_site{len(sites)}_steep.png'), box)
            E.overlay(d['rgb'], gtp, E.clean(pv >= .5), os.path.join(HERE, 'out', f'{icao}_site{len(sites)}_pave.png'), box)
        if sites: res['sites'] = sites
        out[icao] = res; print(icao, json.dumps(res), flush=True)
    json.dump(out, open(os.path.join(HERE, 'out', 'metrics_pave_portal.json'), 'w', encoding='utf-8'), indent=1)
