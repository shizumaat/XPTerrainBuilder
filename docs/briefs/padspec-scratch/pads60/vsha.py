"""pads60 scratch: sha256 of the graded vertex array (levels) and of the whole file; body sha of the patch beside it if given."""
import json, sys, hashlib
for p in sys.argv[1:]:
    raw = open(p, "rb").read(); d = json.loads(raw)
    vs = json.dumps(d["vertices"], sort_keys=True).encode()
    print(hashlib.sha256(vs).hexdigest()[:12], "vertices", len(d["vertices"]), "faces", len(d["faces"]), "file", hashlib.sha256(raw).hexdigest()[:12], p[-50:])
