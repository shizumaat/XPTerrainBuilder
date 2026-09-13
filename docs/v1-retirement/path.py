import ast,json,os,sys
from collections import deque
from pathlib import Path
ROOT=Path('/Users/noah/XPTerrainBuilder/Ortho4XP'); SRC=ROOT/'src'
mods={}
def mod_for(p):
    q=p.relative_to(SRC); parts=list(q.parts)
    if parts[-1]=='__init__.py': parts=parts[:-1]
    else: parts[-1]=parts[-1][:-3]
    return '.'.join(parts)
for f in SRC.rglob('*.py'): mods[mod_for(f)]=f
def imports_of(f,pkg):
    try:t=ast.parse(f.read_text(encoding='utf-8',errors='replace'))
    except Exception:return []
    out=[];pp=pkg.split('.');base=pp if f.name=='__init__.py' else pp[:-1]
    for n in ast.walk(t):
        if isinstance(n,ast.Import):
            for a in n.names: out.append((a.name,n.lineno))
        elif isinstance(n,ast.ImportFrom):
            if n.level:
                b=base[:len(base)-(n.level-1)] if n.level>1 else base
                nm='.'.join(b+([n.module] if n.module else []))
            else: nm=n.module or ''
            out.append((nm,n.lineno))
            for a in n.names: out.append((nm+'.'+a.name,n.lineno))
    return out
def resolve(nm):
    p=nm.split('.')
    while p:
        c='.'.join(p)
        if c in mods: return c
        p.pop()
    return None
CUT=set()
for line in open(os.environ['CUTFILE']):
    line=line.strip()
    if line and not line.startswith('#'):
        a,b=line.split(); CUT.add((a,b))
SEEDS=json.load(open(sys.argv[1]))
prev={s:None for s in SEEDS}; q=deque(SEEDS)
while q:
    m=q.popleft()
    for nm,ln in imports_of(mods[m],m):
        r=resolve(nm)
        if r and r not in prev and (m,r) not in CUT:
            prev[r]=(m,ln); q.append(r)
for tgt in sys.argv[2:]:
    if tgt not in prev: print(tgt,"UNREACHED"); continue
    chain=[];c=tgt
    while prev.get(c): p,ln=prev[c]; chain.append(f"{c} <-{p}:{ln}"); c=p
    chain.append(f"{c} (SEED)")
    print(tgt,"::"," | ".join(chain))
