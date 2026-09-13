import ast, json, sys
from pathlib import Path
ROOT = Path('/Users/noah/XPTerrainBuilder/Ortho4XP'); SRC = ROOT/'src'
mods={}
def mod_for(p):
    q=p.relative_to(SRC); parts=list(q.parts)
    if parts[-1]=='__init__.py': parts=parts[:-1]
    else: parts[-1]=parts[-1][:-3]
    return '.'.join(parts)
for f in SRC.rglob('*.py'): mods[mod_for(f)]=f
def imports_of(f, pkg):
    try: t=ast.parse(f.read_text(encoding='utf-8',errors='replace'))
    except Exception: return set()
    out=set(); pp=pkg.split('.'); isinit=f.name=='__init__.py'
    base=pp if isinit else pp[:-1]
    for n in ast.walk(t):
        if isinstance(n,ast.Import):
            for a in n.names: out.add(a.name)
        elif isinstance(n,ast.ImportFrom):
            if n.level:
                b=base[:len(base)-(n.level-1)] if n.level>1 else base
                nm='.'.join(b+([n.module] if n.module else []))
            else: nm=n.module or ''
            out.add(nm)
            for a in n.names: out.add(nm+'.'+a.name)
    return out
def resolve(name):
    parts=name.split('.')
    while parts:
        c='.'.join(parts)
        if c in mods: return c
        parts.pop()
    return None
import os as _os
CUT=set()
for line in open(_os.environ['CUTFILE']):
    line=line.strip()
    if not line or line.startswith('#'): continue
    a,b=line.split()
    CUT.add((a,b))
SEEDS = json.load(open(sys.argv[1]))
seen=set(); origin={}
queue=[(s,'SEED') for s in SEEDS]
while queue:
    m,src=queue.pop()
    origin.setdefault(m,set()).add(src)
    if m in seen: continue
    seen.add(m)
    for imp in imports_of(mods[m], m):
        r=resolve(imp)
        if r and (m,r) not in CUT: queue.append((r,m))
alla=sorted(m for m in mods if m=='auto_patch' or m.startswith('auto_patch.'))
keep=[m for m in alla if m in seen]; dele=[m for m in alla if m not in seen]
print("KEEP",len(keep),"DELETE",len(dele))
def loc(m):
    f=mods[m]; return len(f.read_text(errors='replace').splitlines()), f.stat().st_size, str(f.relative_to(ROOT))
kl=sum(loc(m)[0] for m in keep); dl=sum(loc(m)[0] for m in dele)
kb=sum(loc(m)[1] for m in keep); db=sum(loc(m)[1] for m in dele)
print(f"KEEP lines {kl} bytes {kb}; DELETE lines {dl} bytes {db}")
print("\n== KEEP ==")
for m in keep:
    l,b,p=loc(m); print(f"{p}\t{l}\t{sorted(origin[m])}")
print("\n== DELETE ==")
for m in dele:
    l,b,p=loc(m); print(f"{p}\t{l}\t{b}")
json.dump({'keep':keep,'delete':dele,'origin':{k:sorted(v) for k,v in origin.items()}},open('/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/g2.json','w'),indent=1)
