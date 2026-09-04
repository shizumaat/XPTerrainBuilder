"""Benchmark driver: runs each arm in a fresh subprocess, R runs, appends JSON lines to results.jsonl."""
import json, subprocess, sys, time, os
P = "/Users/noah/XPTerrainBuilder/Ortho4XP/venv/bin/python"
HERE = os.path.dirname(os.path.abspath(__file__))
sizes = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [5000, 15000, 50000, 150000]
runs = int(sys.argv[2]) if len(sys.argv) > 2 else 3
arms_f = ["highs_lp_phase1", "highs_lp_l1", "highs_raw_phase1", "admm_1e-4", "osqp_default", "osqp_polish",
          "osqp_1e-4_polish", "osqp_1e-6_polish"]
arms_i = ["highs_lp_phase1", "highs_raw_phase1", "osqp_default", "osqp_1e-6_polish", "iis_deletion_seeded"]
out = open(os.path.join(HERE, "results.jsonl"), "a")
for n in sizes:
    for kind, arms in (("f", arms_f), ("i", arms_i)):
        inst = os.path.join(HERE, f"inst/{kind}{n}.npz")
        for arm in arms:
            for r in range(runs):
                t0 = time.time()
                try:
                    p = subprocess.run([P, os.path.join(HERE, "run_one.py"), inst, arm], capture_output=True, text=True, timeout=1800)
                    line = [l for l in p.stdout.splitlines() if l.startswith("RESULT ")]
                    rec = json.loads(line[-1][7:]) if line else dict(arm=arm, inst=inst, n=n, status="NO_RESULT", stderr=p.stderr[-500:])
                except subprocess.TimeoutExpired:
                    rec = dict(arm=arm, inst=inst, n=n, status="TIMEOUT_1800")
                rec["run"] = r; rec["kind"] = kind; rec["wall_subprocess"] = time.time() - t0
                out.write(json.dumps(rec, default=str) + "\n"); out.flush()
                print(f"{n:>7} {kind} {arm:22s} run{r} t={rec.get('t_solve', float('nan')):8.3f}s rss={rec.get('rss_peak_mb', float('nan')):7.1f}MB "
                      f"viol={rec.get('viol', {}).get('max', float('nan')):.2e} obj={rec.get('obj', float('nan'))} status={rec.get('status')}", flush=True)
