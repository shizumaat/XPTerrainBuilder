"""reverify scratch: every HELD pad's datum against the apron level on its rim, one arm or BASE -> ARM.
usage: datum.py ARM_DIR ICAO [BASE_DIR]
Rim = the pad's building-face vertices that are also vertices of an AIRSIDE apron face (graded.json).  Reads
datum - rim (min..max, median), flags a datum outside [min - 0.05, max + 0.05]; pads with no shared apron rim are
counted apart.  With BASE_DIR: old -> new datum for pads on a shared sheet (>= 2 held pads on one apron ref)."""
import collections
import json
import sys


def load(D, icao):
    g = json.load(open(f'{D}/emit/{icao}.graded.json'))
    ax = json.load(open(f'{D}/emit/{icao}_auto.patch.osm.axes.json'))
    return g, {p['ref']: p for p in ax.get('platforms', []) if p.get('datum') is not None}


def main():
    A, icao = sys.argv[1:3]
    B = sys.argv[3] if len(sys.argv) > 3 else None
    g, pa = load(A, icao)
    pb = load(B, icao)[1] if B else {}
    z = {r[0]: r[3] for r in g['vertices']}
    apron_of = collections.defaultdict(set)
    for f in g['faces']:
        if f['role'] == 'apron' and f.get('side', 'airside') == 'airside':
            for u in set(f['ring']) | {u for h in f['holes'] for u in h}:
                apron_of[u].add(f['ref'].split('#')[0])
    rim = collections.defaultdict(dict)
    for f in g['faces']:
        if f['role'] == 'building':
            ref = f['ref'].split('#')[0]
            for u in set(f['ring']) | {u for h in f['holes'] for u in h}:
                for a in apron_of.get(u, ()):
                    rim[ref].setdefault(a, set()).add(u)
    sheet = collections.defaultdict(list)
    for ref in pa:
        for a in rim.get(ref, {}):
            sheet[a].append(ref)
    out, norim = [], 0
    for ref, p in sorted(pa.items()):
        vs = set().union(*rim[ref].values()) if rim.get(ref) else set()
        if not vs:
            norim += 1
            continue
        zs = sorted(z[u] for u in vs)
        lo, hi, med = zs[0], zs[-1], zs[len(zs) // 2]
        d = p['datum']
        gap = 0.0 if lo - 0.05 <= d <= hi + 0.05 else (d - hi if d > hi else d - lo)
        shared = max(len(sheet[a]) for a in rim[ref])
        out.append((abs(gap), ref, d, lo, hi, med, gap, shared, sorted(rim[ref])[0], pb.get(ref, {}).get('datum')))
    bad = [t for t in out if t[0] > 0]
    print(f'HELD PADS {len(pa)}: with an airside apron rim {len(out)}, without {norim}; datum OUTSIDE its rim\'s apron '
          f'range by > 0.05 m: {len(bad)}' + (f' (worst {max(bad)[6]:+.2f} m at {max(bad)[1]})' if bad else ''))
    for t in sorted(bad, reverse=True)[:12]:
        print(f'  OFF {t[1]:14s} datum {t[2]:8.2f} | apron on rim {t[3]:.2f}..{t[4]:.2f} | {t[6]:+.2f} | {t[8]}')
    sh = [t for t in out if t[7] >= 2]
    print(f'PADS ON A SHARED SHEET (>= 2 held pads on one apron): {len(sh)} on '
          f'{len({t[8] for t in sh})} sheets' + ('   ref: base datum -> arm datum | apron on rim min..max | datum - median' if sh else ''))
    for t in sorted(sh, key=lambda t: (t[8], t[1])):
        old = f'{t[9]:8.2f} ->' if t[9] is not None else '       ? ->'
        print(f'  {t[8]:26s} {t[1]:14s} {old} {t[2]:8.2f} | {t[3]:.2f}..{t[4]:.2f} | {t[2] - t[5]:+.2f}' + ('  OFF' if t[0] else ''))


if __name__ == '__main__':
    main()
