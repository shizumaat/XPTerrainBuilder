import sys
def objs(f, pred):
    defs=[]; out=[]
    for line in open(f,errors='replace'):
        if line.startswith('OBJECT_DEF'):
            defs.append(line.split(None,1)[1].strip())
        elif line.startswith('OBJECT'):
            p=line.split(); name=defs[int(p[1])]
            if pred(name):
                kind=p[0]; lon=float(p[2]); lat=float(p[3])
                if kind=='OBJECT': elev=None; hdg=float(p[4])
                else: elev=float(p[4]); hdg=float(p[5])
                out.append((kind,name.split('/')[-1],lon,lat,elev,hdg))
    return out
if __name__=='__main__':
    for f in sys.argv[1:]:
        print("==",f.split("/")[-2][:12] if "/" in f else "", f.split('/')[-1])
        for o in objs(f, lambda n: 'tunnel' in n.lower()):
            print("  %-10s %-26s %.9f %.9f %s" % (o[0],o[1],o[2],o[3],o[4]))
