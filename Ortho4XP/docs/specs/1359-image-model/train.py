"""Train a small U-Net: ortho RGB (+ optional coarse-DEM slope) -> lidar steep-face mask (slope > THR)."""
import argparse, glob, os, time
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F
p = argparse.ArgumentParser()
p.add_argument('--test', default='KDIJ,NZWN,EGFF,KTRK,LGAV')
p.add_argument('--coarse', action='store_true')
p.add_argument('--iters', type=int, default=2500)
p.add_argument('--patch', type=int, default=192)
p.add_argument('--bs', type=int, default=8)
p.add_argument('--out', default='model.pt')
p.add_argument('--thr', type=float, default=10.0)
p.add_argument('--target', default='steep')
a = p.parse_args()
torch.set_num_threads(int(os.environ.get('NT','4'))); torch.manual_seed(0); rng = np.random.default_rng(0)
TD = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tiles')

def norm_rgb(rgb, valid):
    x = rgb.astype(np.float32)
    m = x[valid].mean(0); s = x[valid].std(0) + 1e-3
    return (x - m) / s

def load(icao):
    d = np.load(os.path.join(TD, icao + '.npz'))
    v = d['valid']; x = norm_rgb(d['rgb'], v)
    chans = [x]
    if a.coarse: chans.append((d['syn_slope'][..., None] / 15.0).astype(np.float32))
    if a.target == 'pave':
        y = np.load(os.path.join(os.path.dirname(TD), 'osm', icao + '.npz'))['pave'].astype(np.float32)
    else:
        y = (d['slope'] > a.thr).astype(np.float32)
    return np.concatenate(chans, 2), y, v.astype(np.float32)

class Block(nn.Module):
    def __init__(s, i, o):
        super().__init__(); s.c = nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(True),
                                               nn.Conv2d(o, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(True))
    def forward(s, x): return s.c(x)
class UNet(nn.Module):
    def __init__(s, cin, w=(24, 48, 96, 192)):
        super().__init__()
        s.e = nn.ModuleList([Block(cin, w[0])] + [Block(w[i], w[i + 1]) for i in range(len(w) - 1)])
        s.u = nn.ModuleList([nn.ConvTranspose2d(w[i + 1], w[i], 2, stride=2) for i in range(len(w) - 1)])
        s.d = nn.ModuleList([Block(2 * w[i], w[i]) for i in range(len(w) - 1)])
        s.h = nn.Conv2d(w[0], 1, 1)
    def forward(s, x):
        sk = []
        for i, b in enumerate(s.e):
            x = b(x)
            if i < len(s.e) - 1: sk.append(x); x = F.max_pool2d(x, 2)
        for i in reversed(range(len(s.u))):
            x = s.d[i](torch.cat([s.u[i](x), sk[i]], 1))
        return s.h(x)

if __name__ == '__main__':
    test = set(a.test.split(','))
    names = sorted(os.path.basename(f)[:-4] for f in glob.glob(TD + '/*.npz') if '_' not in os.path.basename(f))
    train = [n for n in names if n not in test]
    print('train', train, flush=True)
    data = [load(n) for n in train]
    pos = [np.argwhere(y[::8, ::8] > 0) * 8 for _, y, _ in data]
    cin = data[0][0].shape[2]
    net = UNet(cin); opt = torch.optim.AdamW(net.parameters(), 2e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 2e-3, total_steps=a.iters)
    print('params', sum(p.numel() for p in net.parameters()), flush=True)
    P = a.patch; t0 = time.time(); run = 0; start = 0
    if os.path.exists(a.out + '.ckpt'):
        ck = torch.load(a.out + '.ckpt', weights_only=False); net.load_state_dict(ck['state']); opt.load_state_dict(ck['opt']); sched.load_state_dict(ck['sched']); start = ck['it'] + 1; print('resume', start)
    for it in range(start, a.iters):
        xs, ys, vs = [], [], []
        while len(xs) < a.bs:
            x, y, v = data[rng.integers(len(data))]
            i = next(j for j in range(len(data)) if data[j][0] is x)
            if rng.random() < .5 and len(pos[i]):
                pr, pc = pos[i][rng.integers(len(pos[i]))]
                r = int(np.clip(pr - rng.integers(P), 0, x.shape[0] - P)); c = int(np.clip(pc - rng.integers(P), 0, x.shape[1] - P))
            else:
                r = rng.integers(0, x.shape[0] - P); c = rng.integers(0, x.shape[1] - P)
            vv = v[r:r + P, c:c + P]
            if vv.mean() < 0.7: continue
            xx, yy = x[r:r + P, c:c + P], y[r:r + P, c:c + P]
            k = rng.integers(4)
            xx, yy, vv = np.rot90(xx, k), np.rot90(yy, k), np.rot90(vv, k)  # note: shadows rotate too (aug for sun azimuth)
            if rng.random() < .5: xx, yy, vv = xx[:, ::-1], yy[:, ::-1], vv[:, ::-1]
            xx = xx.copy()
            xx[..., :3] = xx[..., :3] * rng.uniform(.8, 1.2, 3) + rng.normal(0, .15, 3)  # colour jitter
            xs.append(xx); ys.append(yy.copy()); vs.append(vv.copy())
        X = torch.from_numpy(np.stack(xs)).permute(0, 3, 1, 2).float()
        Y = torch.from_numpy(np.stack(ys))[:, None]; V = torch.from_numpy(np.stack(vs))[:, None]
        lo = net(X)
        pw = torch.tensor(3.0)
        loss = (F.binary_cross_entropy_with_logits(lo, Y, reduction='none', pos_weight=pw) * V).sum() / V.sum()
        opt.zero_grad(); loss.backward(); opt.step(); sched.step()
        run = .98 * run + .02 * loss.item() if it else loss.item()
        if it % 100 == 0: print(it, round(run, 4), round(time.time() - t0), 's', flush=True)
        if it % 250 == 0 and it: torch.save(dict(state=net.state_dict(), opt=opt.state_dict(), sched=sched.state_dict(), it=it, cin=cin, coarse=a.coarse, thr=a.thr), a.out + '.ckpt')
    torch.save(dict(state=net.state_dict(), cin=cin, coarse=a.coarse, thr=a.thr, target=a.target), a.out)
    print('saved', a.out, round(time.time() - t0), 's')
