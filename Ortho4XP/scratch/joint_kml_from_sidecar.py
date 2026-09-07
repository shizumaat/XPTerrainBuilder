"""KML of the declared terrace joints (06n + 07g label boundaries) from a built patch's sidecar."""
import json, sys
side, out = sys.argv[1], sys.argv[2]
pub = json.load(open(side))
recs = pub.get("terrace_joints") or []
kml = ['<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>HECA declared terrace joints (06n cells: white; 07g label boundaries: red > 2 m, orange > 0.5 m, green)</name>',
       '<Style id="big"><LineStyle><color>ff0000ff</color><width>5</width></LineStyle></Style>',
       '<Style id="mid"><LineStyle><color>ff00a5ff</color><width>4</width></LineStyle></Style>',
       '<Style id="small"><LineStyle><color>ff00ff00</color><width>3</width></LineStyle></Style>',
       '<Style id="cell"><LineStyle><color>ffffffff</color><width>2</width></LineStyle></Style>',
       '<Placemark><name>07e site 30.127729,31.412022</name><Point><coordinates>31.412022,30.127729,0</coordinates></Point></Placemark>']
n = 0
for k, r in enumerate(recs):
    if r.get("kind") != "apron_terrace": continue
    s = float(r.get("step_m") or 0.0)
    lab = r.get("label_boundary")
    st = "cell" if not lab else ("big" if s > 2.0 else ("mid" if s > 0.5 else "small"))
    name = f"{'label joint' if lab else '06n joint'} {k}: step {s:.2f} m, {r.get('length_m', 0):.0f} m, {'/'.join(r.get('roles', [])) if lab else 'faces ' + str(r.get('faces'))}"
    kml.append(f'<Placemark><name>{name}</name><styleUrl>#{st}</styleUrl><LineString><coordinates>' + " ".join(f"{lo:.7f},{la:.7f},0" for la, lo in r["points"]) + '</coordinates></LineString></Placemark>')
    n += 1
kml.append('</Document></kml>')
open(out, "w").write("\n".join(kml)); print("wrote", out, n, "joints")
