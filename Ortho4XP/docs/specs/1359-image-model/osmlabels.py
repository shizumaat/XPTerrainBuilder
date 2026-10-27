"""Rasterize OSM airport pavement (runway/taxiway/apron) and tunnel portals onto each airport's 2 m grid."""
import bz2, glob, json, math, os, re, xml.etree.ElementTree as ET
import numpy as np
from PIL import Image, ImageDraw
ROOT = '/mnt/user-data/uploads/XPTerrainBuilderData/OSM_data'
TD = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tiles')
DEFW = {'runway': 30.0, 'taxiway': 15.0}

def parse(files):
    ways = []
    for f in files:
        nodes = {}
        for ev, el in ET.iterparse(bz2.open(f)):
            if el.tag == 'node': nodes[el.get('id')] = (float(el.get('lat')), float(el.get('lon')))
            elif el.tag == 'way':
                tags = {t.get('k'): t.get('v') for t in el.findall('tag')}
                ways.append(([nodes[n.get('ref')] for n in el.findall('nd') if n.get('ref') in nodes], tags)); el.clear()
    return ways

def width(tags, kind):
    try: return float(re.findall(r'[\d.]+', tags.get('width', ''))[0])
    except Exception: return DEFW[kind]

for npz in sorted(glob.glob(TD + '/*.npz')):
    icao = os.path.basename(npz)[:-4]
    d = np.load(npz); gt = d['gt']; H, W = d['valid'].shape
    lat0, lon0 = gt[3] + gt[5] * H, gt[0]; lat1, lon1 = gt[3], gt[0] + gt[1] * W
    files = set()
    for la in {math.floor(lat0), math.floor(lat1)}:
        for lo in {math.floor(lon0), math.floor(lon1)}:
            t = '%+03d%+04d' % (la, lo); T = '%+03d%+04d' % (la // 10 * 10, lo // 10 * 10)
            files |= set(glob.glob(f'{ROOT}/{T}/{t}/{t}_*.osm.bz2'))
    ways = parse(sorted(files))
    rc = lambda ll: ((ll[1] - gt[0]) / gt[1], (ll[0] - gt[3]) / gt[5])
    im = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(im)
    portals = []; nrw = 0
    for refs, tags in ways:
        pts = [rc(ll) for ll in refs]
        if len(pts) < 2: continue
        aw = tags.get('aeroway')
        if aw in ('runway', 'taxiway', 'apron'):
            closed = refs[0] == refs[-1] and len(refs) > 3
            if aw == 'apron' or (closed and aw != 'runway') or (closed and aw == 'runway' and 'width' not in tags):
                if closed: dr.polygon(pts, fill=1)
            else:
                wpx = width(tags, aw) / 2.0
                dr.line(pts, fill=1, width=max(1, int(round(wpx))), joint='curve')
            nrw += aw == 'runway'
        if tags.get('tunnel') in ('yes',) and tags.get('highway') or tags.get('tunnel') == 'yes' and tags.get('railway'):
            for p in (pts[0], pts[-1]):
                if 0 <= p[0] < W and 0 <= p[1] < H: portals.append(p)
    pave = np.array(im, np.uint8)
    np.savez_compressed(os.path.join(os.path.dirname(TD), 'osm', icao + '.npz'), pave=pave, portals=np.array(portals))
    print(icao, 'runways', nrw, 'pave %.3f' % pave.mean(), 'portals', len(portals), flush=True)
