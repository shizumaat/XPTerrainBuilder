"""Build aligned 2 m tiles per airport: RGB ortho, lidar DEM, slope, coarse-DEM slope."""
import glob, json, math, os, re, sys
import numpy as np
from osgeo import gdal
from scipy import ndimage
gdal.UseExceptions()
ROOT = '/mnt/user-data/uploads/XPTerrainBuilderData'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tiles')
os.makedirs(OUT, exist_ok=True)
R = 6378137.0

def jpg_vrt(path):
    m = re.search(r'/(\d+)_(\d+)_([A-Za-z0-9]+?)(\d\d)\.jpg$', path)
    y, x, z = int(m.group(1)), int(m.group(2)), int(m.group(4))
    n = 2 ** z; span = 2 * math.pi * R
    x0 = x / n * span - math.pi * R; x1 = (x + 16) / n * span - math.pi * R
    y0 = math.pi * R - y / n * span; y1 = math.pi * R - (y + 16) / n * span
    v = '/vsimem/' + os.path.basename(path) + '.vrt'
    gdal.Translate(v, path, format='VRT', outputSRS='EPSG:3857', outputBounds=[x0, y0, x1, y1])
    return v

def slope_deg(dem, dx, dy, sigma=1.0):
    d = ndimage.gaussian_filter(dem, sigma) if sigma else dem
    gy, gx = np.gradient(d, dy, dx)
    return np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)

def warp_to(src, ds_ref, alg):
    gt = ds_ref.GetGeoTransform(); W, H = ds_ref.RasterXSize, ds_ref.RasterYSize
    b = [gt[0], gt[3] + gt[5] * H, gt[0] + gt[1] * W, gt[3]]
    o = gdal.Warp('/vsimem/w.tif', src, outputBounds=b, width=W, height=H, dstSRS='EPSG:4326',
                  resampleAlg=alg, dstNodata=-32768 if alg != 'cubic' else 0, multithread=True)
    a = o.ReadAsArray(); o = None; gdal.Unlink('/vsimem/w.tif'); return a

def build(icao, lidar, orthos, coarse=None, res_m=2.0):
    src = gdal.Open(lidar)
    gt = src.GetGeoTransform()
    lat = gt[3] + gt[5] * src.RasterYSize / 2
    mx = 111320 * math.cos(math.radians(lat)); my = 110574
    dxd, dyd = res_m / mx, res_m / my
    W = int(src.RasterXSize * gt[1] / dxd); H = int(src.RasterYSize * -gt[5] / dyd)
    b = [gt[0], gt[3] - H * dyd, gt[0] + W * dxd, gt[3]]
    g = gdal.Warp('/vsimem/g.tif', src, outputBounds=b, width=W, height=H, resampleAlg='average',
                  srcNodata=-32768, dstNodata=-32768)
    dem = g.ReadAsArray().astype(np.float32)
    valid = dem > -1000
    demf = np.where(valid, dem, np.nanmean(np.where(valid, dem, np.nan)) if valid.any() else 0)
    # synthetic 30 m DEM: block-average lidar to 30 m, back to 2 m bilinear
    c = gdal.Warp('/vsimem/c.tif', g, xRes=30 / mx, yRes=30 / my, resampleAlg='average', srcNodata=-32768)
    syn = warp_to(c, g, 'bilinear').astype(np.float32)
    real = warp_to(coarse, g, 'bilinear').astype(np.float32) if coarse else None
    vrts = [jpg_vrt(p) for p in orthos]
    rgb = warp_to(vrts, g, 'cubic').astype(np.uint8)  # (3,H,W)
    rgbvalid = rgb.max(0) > 0
    out = dict(rgb=np.moveaxis(rgb, 0, 2), dem=demf, valid=valid & rgbvalid,
               slope=slope_deg(demf, res_m, res_m),
               syn_slope=slope_deg(np.where(syn > -1000, syn, demf), res_m, res_m, 0),
               gt=np.array([b[0], dxd, 0, b[3], 0, -dyd]))
    if real is not None:
        out['real_slope'] = slope_deg(np.where(real > -1000, real, demf), res_m, res_m, 0)
        out['real_dem'] = real
    np.savez_compressed(os.path.join(OUT, icao + '.npz'), **out)
    for v in vrts: gdal.Unlink(v)
    g = c = None; gdal.Unlink('/vsimem/g.tif'); gdal.Unlink('/vsimem/c.tif')
    print(icao, H, W, 'valid %.2f' % out['valid'].mean(), 'steep>15 %.3f' % (out['slope'][out['valid']] > 15).mean(), flush=True)

if __name__ == '__main__':
    spec = json.load(open(sys.argv[1], encoding='utf-8'))
    for icao, s in spec.items():
        if os.path.exists(os.path.join(OUT, icao + '.npz')): continue
        try: build(icao, s['lidar'], s['orthos'], s.get('coarse'))
        except Exception as e: print(icao, 'FAILED', e, flush=True)
