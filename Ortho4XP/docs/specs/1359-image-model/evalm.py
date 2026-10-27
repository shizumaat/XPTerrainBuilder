"""Evaluate trained models + baselines on held-out airports. Writes metrics JSON and overlay PNGs."""
import json, os, sys, glob
import numpy as np, torch
from scipy import ndimage
from PIL import Image
sys.argv += [] ; import importlib
HERE = os.path.dirname(os.path.abspath(__file__)); TD = os.path.join(HERE, 'tiles')
_argv = sys.argv; sys.argv = sys.argv[:1]
import train as T  # reuse UNet / norm (train parses args at import)
sys.argv = _argv

def predict(model_path, d, chan='syn_slope'):
    ck = torch.load(model_path, weights_only=False)
    net = T.UNet(ck['cin']); net.load_state_dict(ck['state']); net.eval()
    x = T.norm_rgb(d['rgb'], d['valid'])
    if ck['coarse']: x = np.concatenate([x, (d[chan][..., None] / 15.0).astype(np.float32)], 2)
    H, W = x.shape[:2]; S, O = 512, 64
    out = np.zeros((H, W), np.float32); cnt = np.zeros((H, W), np.float32)
    with torch.no_grad():
        for r in list(range(0, max(H - S, 0), S - 2 * O)) + [max(H - S, 0)]:
            for c in list(range(0, max(W - S, 0), S - 2 * O)) + [max(W - S, 0)]:
                xx = torch.from_numpy(np.ascontiguousarray(x[r:r + S, c:c + S])).permute(2, 0, 1)[None].float()
                h, w = xx.shape[2] // 8 * 8, xx.shape[3] // 8 * 8
                p = torch.sigmoid(net(xx[..., :h, :w]))[0, 0].numpy()
                out[r:r + h, c:c + w] += p; cnt[r:r + h, c:c + w] += 1
    return out / np.maximum(cnt, 1)

def boundary(m):
    return m ^ ndimage.binary_erosion(m, iterations=1)

def bf(pred, gt, region, tol):
    bp, bg = boundary(pred) & region, boundary(gt) & region
    if bg.sum() == 0 or bp.sum() == 0: return 0, 0, 0
    dg = ndimage.distance_transform_edt(~bg); dp = ndimage.distance_transform_edt(~bp)
    P = (dg[bp] <= tol).mean(); R = (dp[bg] <= tol).mean()
    return P, R, 2 * P * R / (P + R + 1e-9)

def clean(m, min_px=25):
    m = ndimage.binary_opening(m, iterations=1)
    lab, n = ndimage.label(m); sz = ndimage.sum(m, lab, range(1, n + 1))
    return np.isin(lab, 1 + np.flatnonzero(sz >= min_px))

def metrics(prob_or_mask, gt, region, thr=0.5):
    pm = clean(prob_or_mask >= thr) if prob_or_mask.dtype != bool else clean(prob_or_mask)
    tp = (pm & gt & region).sum(); fp = (pm & ~gt & region).sum(); fn = (~pm & gt & region).sum()
    P = tp / (tp + fp + 1e-9); R = tp / (tp + fn + 1e-9)
    res = dict(px_P=P, px_R=R, px_F=2 * P * R / (P + R + 1e-9), IoU=tp / (tp + fp + fn + 1e-9))
    for tol_m in (4, 10):
        p, r, f = bf(pm, gt, region, tol_m / 2)
        res[f'edge{tol_m}m_P'], res[f'edge{tol_m}m_R'], res[f'edge{tol_m}m_F'] = p, r, f
    return {k: round(float(v), 3) for k, v in res.items()}, pm

def latlon_rc(d, lat, lon):
    gt = d['gt']; return int((lat - gt[3]) / gt[5]), int((lon - gt[0]) / gt[1])

def overlay(rgb, gt, pm, path, box=None):
    im = rgb.copy().astype(np.float32)
    bg, bp = ndimage.binary_dilation(boundary(gt)), ndimage.binary_dilation(boundary(pm))
    im[bg] = im[bg] * .3 + np.array([255, 255, 0]) * .7      # lidar truth edges: yellow
    im[bp] = im[bp] * .3 + np.array([255, 0, 255]) * .7      # model edges: magenta
    if box: r0, r1, c0, c1 = box; im = im[r0:r1, c0:c1]
    Image.fromarray(im.clip(0, 255).astype(np.uint8)).save(path)

if __name__ == '__main__':
    cfg = json.load(open(sys.argv[1], encoding='utf-8'))
    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    allres = {}
    for icao in cfg['airports']:
        d = dict(np.load(os.path.join(TD, icao + '.npz')))
        H, W = d['valid'].shape
        region = d['valid'].copy(); m = np.zeros_like(region); m[int(.2 * H):int(.8 * H), int(.2 * W):int(.8 * W)] = 1; region &= m.astype(bool)
        gt = clean(d['slope'] > cfg['thr'])
        res = {}
        # baselines
        for ct in (4, 6, 8):
            res[f'coarse_syn30m_{ct}deg'], _ = metrics(d['syn_slope'] > ct, gt, region)
            if 'real_slope' in d: res[f'coarse_real_{ct}deg'], _ = metrics(d['real_slope'] > ct, gt, region)
        lum = ndimage.gaussian_filter(d['rgb'].astype(np.float32).mean(2), 1.5)
        g = np.hypot(ndimage.sobel(lum, 0), ndimage.sobel(lum, 1)); thr = np.percentile(g[region], 100 - 100 * gt[region].mean())
        res['classic_sobel'], _ = metrics(ndimage.binary_closing(g > thr, iterations=2), gt, region)
        probs = {}
        for name, mp in cfg['models'].items():
            pr = predict(os.path.join(HERE, mp), d); probs[name] = pr
            res[name], pm = metrics(pr, gt, region)
            if 'real_slope' in d and torch.load(os.path.join(HERE, mp), weights_only=False)['coarse']:
                pr2 = predict(os.path.join(HERE, mp), d, 'real_slope'); probs[name + '_realdem'] = pr2
                res[name + '_realdem'], _ = metrics(pr2, gt, region)
            overlay(d['rgb'], gt, pm, os.path.join(HERE, 'out', f'{icao}_{name}.png'))
        np.savez_compressed(os.path.join(HERE, 'out', f'{icao}_probs.npz'), **probs)
        res['steep_frac'] = round(float(gt[region].mean()), 3)
        allres[icao] = res
        print(icao, json.dumps(res), flush=True)
    json.dump(allres, open(os.path.join(HERE, 'out', 'metrics.json'), 'w', encoding='utf-8'), indent=1)
